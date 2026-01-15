import threading
import time
import logging
import cv2
import requests
from config import CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, CAMERA_URL
from metrics.metrics import camera_frames_sent

log = logging.getLogger("camera")

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
            log.error("Camera open failed")
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
                    camera_frames_sent.inc()
                except Exception:
                    pass
            time.sleep(max(0, interval - (time.time() - start)))

        cap.release()

    def stop(self):
        self.running = False
