import ssl
import time
from time import sleep

import paho.mqtt.client as mqtt
from aliot.aliot_obj import AliotObj
from gpiozero import LED, Robot

# ROBOT


class Bring:
    def __init__(self):
        self.robot = Robot(left=(13, 19), right=(12, 18))

    def forward(self, _=None):
        self.robot.forward(0.5)

    def backward(self, _=None):
        self.robot.backward(0.5)

    def left(self, _=None):
        self.robot.left(0.5)

    def right(self, _=None):
        self.robot.right(0.5)

    def stop(self, _=None):
        self.robot.stop()


# CONNECTION

BROKER = "0fa1404b7c15491b90830564ce2ee08e.s1.eu.hivemq.cloud"
PORT = 8883
USERNAME = "hivemq.webclient.1762814726293"
PASSWORD = ":X7x@1C20*MBrO.fHmds"
TOPIC = "bring/action"


robot = Bring()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("✅ Connected successfully!")
        client.subscribe(TOPIC)
        print(f"📡 Subscribed to topic: {TOPIC}")
    else:
        print(f"❌ Connection failed with code {reason_code}")


def on_message(client, userdata, message):
    cmd = message.payload.decode().lower()
    print(f"📩 {message.topic}: {cmd}")

    if cmd == "forward":
        robot.forward()
    elif cmd == "backward":
        robot.backward()
    elif cmd == "left":
        robot.left()
    elif cmd == "right":
        robot.right()
    elif cmd == "stop":
        robot.stop()
    else:
        print(f"⚠️ Unknown command: {cmd}")


# Use the new callback API version (required for Paho v2)
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

# Set login credentials
client.username_pw_set(USERNAME, PASSWORD)

# Enable TLS encryption
client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS)
client.tls_insecure_set(False)  # optional, set to True for debugging only

# Assign callbacks
client.on_connect = on_connect
client.on_message = on_message

# Connect securely
client.connect(BROKER, PORT, 60)

# Keep listening for messages
client.loop_forever()
