import glob
import time
import logging
from typing import Optional

import serial

log = logging.getLogger("serial")

class SerialBridge:
    def __init__(self, baudrate: int):
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.port: Optional[str] = None

    def connect(self):
        if self.ser and self.ser.is_open:
            return

        for port in sorted(glob.glob("/dev/ttyACM*")):
            log.info(f"Found serial {port}")
            try:
                self.ser = serial.Serial(port, self.baudrate, timeout=1)
                self.port = port
                time.sleep(1)
                log.info("Connected serial port=%s baud=%d", port, self.baudrate)
                return
            except Exception as e:
                log.error(f"An error occured when trying to connect to serial port: {e}")
                continue

        log.warning("No serial device found")

    def write_hex(self, hex_data: str):
        if not self.ser:
            return
        try:
            self.ser.write(bytes.fromhex(hex_data))
        except Exception as e:
            log.error("Serial write failed: %s", e)
            self._drop()
    def write_rgb(self, r: int, g: int, b: int):
        """
        Send RGB LED command.
        Protocol: [0x0A, R, G, B]
        """
        if not self.ser or not self.ser.is_open:
            return
        try:
            self.ser.write(bytes([0x0A, r & 0xFF, g & 0xFF, b & 0xFF]))
        except Exception as e:
            log.error("RGB write failed: %s", e)
            self._drop()
    def read_packet(self):
        if not self.ser or self.ser.in_waiting < 2:
            return None
        try:
            header = self.ser.read(2)
            dtype, total_size = header
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
        finally:
            self.ser = None
            self.port = None

    def close(self):
        self._drop()
