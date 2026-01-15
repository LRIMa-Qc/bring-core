import time
import logging
from typing import Set

from config import BAUDRATE, METRICS_PORT
from logging_setup import setup_logging
from metrics.metrics import start_metrics_server
from serial.bridge import SerialBridge
from mqtt.bridge import MQTTBridge
from camera.streamer import CameraStreamer
from runtime.logger import RuntimeLogger

log = logging.getLogger("main")

def main():
    setup_logging()
    start_metrics_server(port=METRICS_PORT)

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
                payload = payload[::-1]
                topic = f"device/{dtype:02X}"
                mqtt_bridge.publish(topic, payload.hex())

                if dtype in verbose_devices:
                    log.info("Device %02X payload=%s", dtype, payload.hex())

            time.sleep(0.01)
    finally:
        camera.stop()
        mqtt_bridge.close()
        serial_bridge.close()
        log.info("Shutdown complete")

if __name__ == "__main__":
    main()
