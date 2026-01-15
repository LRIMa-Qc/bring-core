import logging
import paho.mqtt.client as mqtt
from config import MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, MQTT_SUB_TOPIC

log = logging.getLogger("mqtt")

class MQTTBridge:
    def __init__(self, serial_bridge):
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
            log.info("Connecting to MQTT broker %s:%d", MQTT_BROKER, MQTT_PORT)
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
            payload = msg.payload.decode()
            if len(payload) % 2 == 0:
                self.serial.write_hex(payload)
        except Exception as e:
            log.error("MQTT message handling failed: %s", e)

    def publish(self, topic: str, payload: str):
        try:
            self.client.publish(topic, payload)
        except Exception:

    def close(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

