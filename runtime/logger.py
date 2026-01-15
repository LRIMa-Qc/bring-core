import threading
import sys
import logging
from typing import Set

log = logging.getLogger("runtime")

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
            cmd = parts[1] if len(parts) > 1 else None
            ids = [int(x, 16) for x in parts[2:]]

            if parts[0] != "log":
                continue

            if cmd == "add":
                self.enabled_devices.update(ids)
            elif cmd == "remove":
                self.enabled_devices.difference_update(ids)

            log.info("Logging devices: %s",
                     [f"{x:02X}" for x in self.enabled_devices])
