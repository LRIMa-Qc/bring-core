import threading
import time
import logging
import glob
import sys
from typing import Optional, Set

import cv2
import paho.mqtt.client as mqtt
import requests
import serial

BAUDRATE = 9600

MQTT_BROKER = "206.167.46.66"
MQTT_PORT = 1883
MQTT_USERNAME = "dev"
MQTT_PASSWORD = "lrimalrima"
MQTT_SUB_TOPIC = "device/write"

CAMERA_URL = "http://206.167.46.66:3000/camera/frame"
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 10


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bridge")


class SerialBridge:
    def __init__(self, baudrate: int):
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.port: Optional[str] = None

    def connect(self):
        if self.ser and self.ser.is_open:
            return
        for port in sorted(glob.glob("/dev/ttyACM*")):
            try:
                ser = serial.Serial(port, self.baudrate, timeout=1)
                time.sleep(1)
                self.ser = ser
                self.port = port
                log.info("Serial connected port=%s baud=%d", port, self.baudrate)
                return
            except Exception:
                continue
        log.warning("No ACM serial device available")

    def write_hex(self, hex_data: str):
        if not self.ser or not self.ser.is_open:
            return
        try:
            self.ser.write(bytes.fromhex(hex_data))
        except Exception as e:
            log.error("Serial write failed: %s", e)
            self._drop()

    def read_packet(self):
        if not self.ser or not self.ser.is_open:
            return None
        try:
            if self.ser.in_waiting < 2:
                return None
            header = self.ser.read(2)
            dtype = header[0]
            total_size = header[1]
            payload_len = total_size - 2
            if payload_len < 0:
                return None
            payload = self.ser.read(payload_len)
            return dtype, payload
        except Exception as e:
            log.error("Serial read failed: %s", e)
            self._drop()
            return None

    def _drop(self):
        try:
            if self.ser:
                self.ser.close()
        except Exception:
            pass
        self.ser = None
        self.port = None

    def close(self):
        self._drop()


class MQTTBridge:
    def __init__(self, serial_bridge: SerialBridge):
        self.serial = serial_bridge
        self.client = mqtt.Client()
        self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def connect(self):
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            log.info("MQTT connecting broker=%s:%d", MQTT_BROKER, MQTT_PORT)
        except Exception as e:
            log.error("MQTT connection failed: %s", e)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info("MQTT connected")
            client.subscribe(MQTT_SUB_TOPIC)
        else:
            log.error("MQTT connect failed rc=%d", rc)

    def on_disconnect(self, client, userdata, rc):
        log.warning("MQTT disconnected rc=%d", rc)

    def on_message(self, client, userdata, msg):
        try:
            hex_data = msg.payload.decode()
            if len(hex_data) % 2 != 0:
                return
            self.serial.write_hex(hex_data)
        except Exception as e:
            log.error("MQTT message handling failed: %s", e)

    def publish(self, topic: str, payload: str):
        try:
            self.client.publish(topic, payload)
        except Exception as e:
            log.error("MQTT publish failed: %s", e)

    def close(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass


class CameraStreamer(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.running = True

    def run(self):
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

        if not cap.isOpened():
            log.error("Camera open failed index=%d", CAMERA_INDEX)
            return

        interval = 1.0 / CAMERA_FPS
        log.info("Camera started")

        while self.running:
            start = time.time()
            ret, frame = cap.read()
            if ret:
                try:
                    _, jpg = cv2.imencode(".jpg", frame)
                    requests.post(
                        CAMERA_URL,
                        data=jpg.tobytes(),
                        headers={"Content-Type": "image/jpeg"},
                        timeout=0.2,
                    )
                except Exception:
                    pass
            time.sleep(max(0, interval - (time.time() - start)))

        cap.release()

    def stop(self):
        self.running = False


class RuntimeLogger(threading.Thread):
    def __init__(self, enabled_devices: Set[int]):
        super().__init__(daemon=True)
        self.enabled_devices = enabled_devices

    def run(self):
        while True:
            line = sys.stdin.readline().strip()
            if not line:
                continue
            parts = line.split()
            if parts[0] == "log" and len(parts) >= 2:
                cmd = parts[1]
                ids = [int(x, 16) for x in parts[2:]]
                if cmd == "add":
                    self.enabled_devices.update(ids)
                    log.info("Logging enabled for %s", [f"{x:02X}" for x in ids])
                elif cmd == "remove":
                    self.enabled_devices.difference_update(ids)
                    log.info("Logging disabled for %s", [f"{x:02X}" for x in ids])
                elif cmd == "list":
                    log.info("Logging devices: %s", [f"{x:02X}" for x in self.enabled_devices])


def main():
    serial_bridge = SerialBridge(BAUDRATE)
    mqtt_bridge = MQTTBridge(serial_bridge)
    mqtt_bridge.connect()

    camera = CameraStreamer()
    camera.start()

    verbose_devices: Set[int] = set()
    RuntimeLogger(verbose_devices).start()

    log.info("Main loop started")

    try:
        while True:
            if not serial_bridge.ser:
                serial_bridge.connect()
                time.sleep(1)
                continue

            packet = serial_bridge.read_packet()
            if packet:
                dtype, payload = packet
                inverted = payload[::-1]
                topic = f"device/{dtype:02X}"
                mqtt_bridge.publish(topic, inverted.hex())

                if dtype in verbose_devices:
                    log.info(
                        "Device %02X payload=%s",
                        dtype,
                        inverted.hex(),
                    )
            time.sleep(0.01)
    finally:
        camera.stop()
        mqtt_bridge.close()
        serial_bridge.close()
        log.info("Shutdown complete")


if __name__ == "__main__":
    main()

