import time

import paho.mqtt.client as mqtt
import serial

ser = serial.Serial("/dev/ttyACM0", baudrate=9600, timeout=1)
time.sleep(2)

print("Listening on ttyACM0...")

BROKER = "206.167.46.66"
PORT = 1883
TOPIC = "raw"


def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    print(f"{msg.topic}: {msg.payload}")


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)
client.loop_forever()


while True:
    data = ser.read(3)
    if data:
        print("RAW:", data)
        print("HEX:", data.hex())
