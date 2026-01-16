import threading
import time
import logging
import cv2
import requests

log = logging.getLogger("camera")

CAMERA_URL = "http://206.167.46.66:3000/camera/frame"
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 10
RETRY_DELAY = 2  # seconds before retrying if camera fails


class CameraStreamer(threading.Thread):
    """Continuously streams camera frames, reconnecting if the camera fails."""

    def __init__(self):
        super().__init__(daemon=True)
        self.running = True

    def run(self):
        while self.running:
            cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

            if not cap.isOpened():
                log.warning("Camera failed to open index=%d, retrying in %ds", CAMERA_INDEX, RETRY_DELAY)
                time.sleep(RETRY_DELAY)
                continue

            log.info("Camera started successfully")

            interval = 1.0 / CAMERA_FPS
            while self.running and cap.isOpened():
                start_time = time.time()
                ret, frame = cap.read()
                if not ret:
                    log.warning("Camera read failed, reconnecting...")
                    break  # exit inner loop to reconnect

                try:
                    _, jpg = cv2.imencode(".jpg", frame)
                    requests.post(
                        CAMERA_URL,
                        data=jpg.tobytes(),
                        headers={"Content-Type": "image/jpeg"},
                        timeout=0.2,
                    )
                except Exception as e:
                    log.warning("Failed to send frame: %s", e)

                # maintain framerate
                elapsed = time.time() - start_time
                time.sleep(max(0, interval - elapsed))

            cap.release()
            log.info("Camera released, retrying in %ds", RETRY_DELAY)
            time.sleep(RETRY_DELAY)

    def stop(self):
        self.running = False
