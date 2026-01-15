import os
from dotenv import load_dotenv
load_dotenv()

# Serial
BAUDRATE = int(os.getenv("BAUDRATE", 9600))

# MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER", "206.167.46.66")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "dev")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "lrimalrima")
MQTT_SUB_TOPIC = os.getenv("MQTT_SUB_TOPIC", "device/write")

# Camera
CAMERA_URL = os.getenv("CAMERA_URL", "http://206.167.46.66:3000/camera/frame")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 0))
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", 640))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", 480))
CAMERA_FPS = int(os.getenv("CAMERA_FPS", 10))

# Metrics
METRICS_PORT = int(os.getenv("METRICS_PORT", 8000))
ACCESS_KEY = os.getenv("ACCESS_KEY")
if not ACCESS_KEY:
    raise ValueError("ACCESS_KEY missing in .env")

