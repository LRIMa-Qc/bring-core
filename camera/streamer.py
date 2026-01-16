import threading
import time
import logging
import cv2
import requests

log = logging.getLogger("camera")

CAMERA_URL = "http://206.167.46.66:3000/camera/frame"  # your Elysia backend
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
RETRY_DELAY = 2  # seconds before retrying

class CameraStreamer(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.running = True
        self.cap = None

    def run(self):
        while self.running:
            # Try to open camera
            if self.cap is None or not self.cap.isOpened():
                self.cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                self.cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                if not self.cap.isOpened():
                    log.warning("Camera failed to open, retrying in 2s...")
                    self.cap.release()
                    self.cap = None
                    time.sleep(RETRY_DELAY)
                    continue
                log.info("Camera started successfully")

            ret, frame = self.cap.read()
            if not ret:
                log.warning("Failed to read frame, reconnecting...")
                self.cap.release()
                self.cap = None
                time.sleep(RETRY_DELAY)
                continue

            # Encode frame as JPEG
            _, jpeg = cv2.imencode(".jpg", frame)

            # POST frame to backend
            try:
                requests.post(
                    CAMERA_URL,
                    data=jpeg.tobytes(),
                    headers={"Content-Type": "image/jpeg"},
                    timeout=0.2,
                )
            except Exception as e:
                log.warning("Failed to send frame: %s", e)

            time.sleep(1 / CAMERA_FPS)

    def stop(self):
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
