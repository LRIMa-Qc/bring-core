import threading
import time

import cv2
import paho.mqtt.client as mqtt
import requests
import serial

SERIAL_PORT = "/dev/ttyACM0"
BAUDRATE = 9600

MQTT_BROKER = "206.167.46.66"
MQTT_PORT = 1883
MQTT_USERNAME = "dev"
MQTT_PASSWORD = "lrimalrima"
MQTT_SUB_TOPIC = "device/write"

CAMERA_URL = "http://206.167.46.66:3000/camera/frame"
CAMERA_INDEX = 0  # usually /dev/video0, adjust if needed
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 10  # frames per second

try:
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
    time.sleep(2)
    print(f"[INFO] Connected to serial port {SERIAL_PORT} at {BAUDRATE} baud")
except Exception as e:
    print(f"[ERROR] Failed to open serial port {SERIAL_PORT}: {e}")
    raise


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[INFO] Connected to MQTT broker")
        client.subscribe(MQTT_SUB_TOPIC)
        print(f"[INFO] Subscribed to {MQTT_SUB_TOPIC}")
    else:
        print(f"[ERROR] Failed to connect to MQTT broker, return code {rc}")


def on_message(client, userdata, msg):
    try:
        hex_data = msg.payload.decode()
        if len(hex_data) % 2 != 0:
            print(f"[WARNING] Invalid hex message length: {hex_data}")
            return
        bytes_to_send = bytes.fromhex(hex_data)
        ser.write(bytes_to_send)
        print(f"[INFO] Sent to serial: {hex_data}")
    except Exception as e:
        print(f"[ERROR] Failed to send serial message: {e}")


def on_disconnect(client, userdata, rc):
    print(f"[WARNING] Disconnected from MQTT broker with code {rc}")


client = mqtt.Client()
client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
except Exception as e:
    print(f"[ERROR] Failed to connect to MQTT broker: {e}")
    raise


def camera_loop():
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera /dev/video{CAMERA_INDEX}")
        return

    print(f"[INFO] Camera thread started on /dev/video{CAMERA_INDEX}")

    interval = 1.0 / CAMERA_FPS
    while True:
        print("[INFO] Sending an image")
        start_time = time.time()
        ret, frame = cap.read()
        if not ret:
            continue

        # Encode as JPEG
        _, jpg = cv2.imencode(".jpg", frame)

        try:
            requests.post(
                CAMERA_URL,
                data=jpg.tobytes(),
                headers={"Content-Type": "image/jpeg"},
                timeout=0.2,
            )
        except Exception:
            pass

        elapsed = time.time() - start_time
        time.sleep(max(0, interval - elapsed))


cam_thread = threading.Thread(target=camera_loop, daemon=True)
cam_thread.start()

print("[INFO] Starting main loop...")
try:
    while True:
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)

            dtype = data[0]  # first byte is topic
            payload_bytes = data[1:]  # remaining bytes is data

            # invert payload bytes (legacy)
            inverted_bytes = payload_bytes[::-1]

            # TODO: Noah ts

            hex_payload = inverted_bytes.hex()
            topic = f"device/{dtype:02X}"
            client.publish(topic, hex_payload)
            print(f"[INFO] Published {len(data)} bytes to {topic}: {hex_payload}")

except KeyboardInterrupt:
    print("[INFO] Stopping program (KeyboardInterrupt)")
finally:
    client.loop_stop()
    client.disconnect()
    ser.close()
    print("[INFO] Clean exit")
