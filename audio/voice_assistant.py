import os
import io
import base64
import random
import threading
from collections import deque
import logging

import numpy as np
import pvporcupine
import pyaudio
import sounddevice as sd
import soundfile as sf
import requests

from hardware_serial.bridge import SerialBridge  # reuse SerialBridge

log = logging.getLogger("voice_assistant")


class VoiceAssistant(threading.Thread):
    """Voice Assistant system running in its own thread"""
    audio_lock = threading.Lock()

    def __init__(self, access_key: str, serial_bridge: SerialBridge):
        super().__init__(daemon=True)
        self.serial = serial_bridge
        self.serial.connect()

        keyword_path = os.path.abspath("bring.ppn")
        if not os.path.exists(keyword_path):
            raise FileNotFoundError(f"Missing PPN file: {keyword_path}")

        self.porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=[keyword_path],
        )

        self.pa = pyaudio.PyAudio()
        self.porcupine_rate = self.porcupine.sample_rate
        self.hardware_rate = 48000
        self.resample_factor = self.hardware_rate // self.porcupine_rate

        log.info("VoiceAssistant ready | HW: %dHz | Resample: 1/%d",
                 self.hardware_rate, self.resample_factor)

        self.set_idle()
        self.running = True

    # ---------------- LED STATES ---------------- #
    def set_idle(self):
        self.serial.write_rgb(0, 100, 0)

    def set_recording(self):
        self.serial.write_rgb(100, 0, 0)

    def set_processing(self):
        self.serial.write_rgb(0, 0, 100)

    def set_answering(self):
        self.serial.write_rgb(100, 0, 0)

    # ---------------- UI SOUND ---------------- #
    def play_ui_sound(self, filename: str):
        if not os.path.exists(filename):
            return
        try:
            data, fs = sf.read(filename)
            sd.play(data, fs)
            sd.wait()
        except Exception as e:
            log.warning("UI sound error: %s", e)

    # ---------------- WAKE WORD ---------------- #
    def detect_wake_word(self) -> bool:
        chunk_size = self.porcupine.frame_length * self.resample_factor
        stream = self.pa.open(
            rate=self.hardware_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=chunk_size,
        )
        self.set_idle()
        log.info("Listening for wake word...")
        try:
            while self.running:
                pcm = stream.read(chunk_size, exception_on_overflow=False)
                pcm = np.frombuffer(pcm, dtype=np.int16)
                pcm_16khz = pcm[::self.resample_factor]
                if self.porcupine.process(pcm_16khz) >= 0:
                    stream.stop_stream()
                    stream.close()
                    return True
        except Exception:
            stream.stop_stream()
            stream.close()
        return False

    # ---------------- RECORDING ---------------- #
    def record_audio(self):
        self.set_recording()
        log.info("Recording...")
        self.play_ui_sound("start.wav")

        sample_rate = 48000
        blocksize = 2048
        silence_threshold = 0.035
        max_silence = 2.0
        max_duration = 15.0

        audio_buffer = deque()
        silence_time = 0
        total_time = 0
        recording_started = False

        def callback(indata, frames, time_info, status):
            nonlocal silence_time, total_time, recording_started
            audio_buffer.append(indata.copy())
            rms = np.sqrt(np.mean(indata ** 2))
            if rms > silence_threshold:
                recording_started = True
                silence_time = 0
            elif recording_started:
                silence_time += frames / sample_rate
            total_time += frames / sample_rate

        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=blocksize,
            callback=callback,
        ):
            while silence_time < max_silence and total_time < max_duration and self.running:
                sd.sleep(100)

        self.play_ui_sound("stop.wav")

        if not audio_buffer:
            self.set_idle()
            return None

        audio = np.concatenate(audio_buffer)
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio *= 0.9 / peak
        return audio, sample_rate

    # ---------------- AI PROCESSING ---------------- #
    def process_with_ai(self, wav_path: str):
        self.set_processing()
        log.info("Processing audio via AI...")

        stop_music = threading.Event()
        #
        def waiting_music_loop():
            musics = [
                os.path.join("waiting_musics", f)
                for f in os.listdir("waiting_musics")
                if f.endswith((".wav", ".flac"))
            ]
            if not musics:
                return

            while not stop_music.is_set():
                music_file = random.choice(musics)
                try:
                    data, fs = sf.read(music_file, dtype="float32")
                    with audio_lock:
                        sd.play(data, fs)
                    while sd.get_stream().active and not stop_music.is_set():
                        sd.sleep(100)
                    sd.stop()
                except Exception as e:
                    log.warning("Waiting music error: %s", e)

        music_thread = threading.Thread(target=waiting_music_loop, daemon=True)
        music_thread.start()

        try:
            with open(wav_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode()

            response = requests.post(
                "http://206.167.46.66:3000/ia/chat/audio",
                json={"content": audio_b64},
                timeout=60,
            )

            stop_music.set()
            sd.stop()
            music_thread.join()

            if not response.ok:
                log.warning("Server error")
                self.set_idle()
                return

            audio_out_b64 = response.json().get("content")
            if not audio_out_b64:
                self.set_idle()
                return

            data, sr = sf.read(io.BytesIO(base64.b64decode(audio_out_b64)), dtype="int16")
            self.set_answering()
            self.play_ui_sound("ready.wav")
            sd.play(data, sr)
            sd.wait()
            self.set_idle()

        except Exception as e:
            log.warning("AI processing error: %s", e)
            self.set_idle()

    # ---------------- MAIN LOOP ---------------- #
    def run(self):
        while self.running:
            if self.detect_wake_word():
                result = self.record_audio()
                if result:
                    audio, sr = result
                    sf.write("audio.wav", audio, sr, subtype="PCM_16")
                    self.process_with_ai("audio.wav")

    def stop(self):
        self.running = False
        self.serial.close()
        self.pa.terminate()
        self.porcupine.delete()

