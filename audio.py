#!/usr/bin/env python3
import base64
import io
import os
import random
import threading
import time
from collections import deque

import numpy as np
import pvporcupine
import pyaudio
import requests
import sounddevice as sd
import soundfile as sf
import serial
from dotenv import load_dotenv


BAUDRATE = 9600
SERIAL_PORT = "/dev/ttyACM0"


# ---------------- SERIAL ---------------- #

class SerialBridge:
    def __init__(self, baudrate: int):
        self.baudrate = baudrate
        self.ser = None

    def connect(self):
        if self.ser and self.ser.is_open:
            return
        try:
            self.ser = serial.Serial(SERIAL_PORT, self.baudrate, timeout=1)
            time.sleep(1)
            print(f"[Serial] Connected to {SERIAL_PORT}")
        except Exception as e:
            print(f"[Serial] Connection failed: {e}")
            self.ser = None

    def write_rgb(self, r: int, g: int, b: int):
        if not self.ser or not self.ser.is_open:
            return
        try:
            self.ser.write(bytes([10, r, g, b]))
        except Exception as e:
            print(f"[Serial] Write failed: {e}")
            self.close()

    def close(self):
        try:
            if self.ser:
                self.ser.close()
        except Exception:
            pass
        self.ser = None


# ---------------- VOICE ASSISTANT ---------------- #

class VoiceAssistant:
    def __init__(self, access_key: str, serial_bridge: SerialBridge):
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

        print("=" * 60)
        print("Voice Assistant Ready")
        print(f"HW: {self.hardware_rate}Hz | Resampling: 1/{self.resample_factor}")
        print("=" * 60)

        self.set_idle()

    # ---------- LED STATES ---------- #

    def set_idle(self):
        self.serial.write_rgb(0, 100, 0)      # 🟢 Green (general / finished)

    def set_recording(self):
        self.serial.write_rgb(100, 0, 0)      # 🔴 Red (recording)

    def set_processing(self):
        self.serial.write_rgb(0, 0, 100)      # 🔵 Blue (processing)

    def set_answering(self):
        self.serial.write_rgb(100, 0, 0)      # 🔴 Red (answering)

    # ---------- AUDIO ---------- #

    def play_ui_sound(self, filename):
        if not os.path.exists(filename):
            return
        try:
            data, fs = sf.read(filename)
            sd.play(data, fs)
            sd.wait()
        except Exception as e:
            print(f"UI sound error: {e}")

    def _waiting_music_loop(self, stop_event):
        musics = [
            os.path.join("waiting_musics", f)
            for f in os.listdir("waiting_musics")
            if f.endswith((".wav", ".flac"))
        ]
        if not musics:
            return
        try:
            while not stop_event.is_set():
                music_file = random.choice(musics)
                data, fs = sf.read(music_file)
                sd.play(data, fs)
                for _ in range(int(len(data) / fs * 10)):
                    if stop_event.is_set():
                        sd.stop()
                        return
                    sd.sleep(100)
        except Exception:
            pass

    # ---------- WAKE WORD ---------- #

    def detect_wake_word(self):
        chunk_size = self.porcupine.frame_length * self.resample_factor
        stream = self.pa.open(
            rate=self.hardware_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=chunk_size,
        )

        self.set_idle()
        print("\nListening for wake word...")

        try:
            while True:
                pcm = stream.read(chunk_size, exception_on_overflow=False)
                pcm = np.frombuffer(pcm, dtype=np.int16)
                pcm_16khz = pcm[::self.resample_factor]

                if self.porcupine.process(pcm_16khz) >= 0:
                    stream.stop_stream()
                    stream.close()
                    return True
        except KeyboardInterrupt:
            stream.stop_stream()
            stream.close()
            return False

    # ---------- RECORDING ---------- #

    def record_audio(self):
        self.set_recording()
        print("Recording...")
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
            while silence_time < max_silence and total_time < max_duration:
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

    # ---------- AI PROCESSING ---------- #

    def process_with_ai(self, wav_path):
        self.set_processing()
        print("Processing...")

        stop_music = threading.Event()
        music_thread = threading.Thread(
            target=self._waiting_music_loop,
            args=(stop_music,),
            daemon=True,
        )
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
                print("Server error")
                self.set_idle()
                return

            audio_out_b64 = response.json().get("content")
            if not audio_out_b64:
                print("No audio returned")
                self.set_idle()
                return

            data, sr = sf.read(
                io.BytesIO(base64.b64decode(audio_out_b64)),
                dtype="int16"
            )

            # 🔴 answering
            self.set_answering()
            self.play_ui_sound("ready.wav")
            sd.play(data, sr)
            sd.wait()

            # 🟢 finished
            self.set_idle()

        except Exception as e:
            print(f"AI error: {e}")
            self.set_idle()

    # ---------- MAIN LOOP ---------- #

    def run(self):
        self.set_idle()
        try:
            while True:
                if self.detect_wake_word():
                    result = self.record_audio()
                    if result:
                        audio, sr = result
                        sf.write("audio.wav", audio, sr, subtype="PCM_16")
                        self.process_with_ai("audio.wav")
        except KeyboardInterrupt:
            print("\nShutdown requested")
        finally:
            self.serial.close()
            self.pa.terminate()
            self.porcupine.delete()


# ---------------- ENTRYPOINT ---------------- #

if __name__ == "__main__":
    load_dotenv()
    ACCESS_KEY = os.getenv("ACCESS_KEY")
    if not ACCESS_KEY:
        print("ACCESS_KEY missing in .env")
        exit(1)

    serial_bridge = SerialBridge(BAUDRATE)
    VoiceAssistant(ACCESS_KEY, serial_bridge).run()
