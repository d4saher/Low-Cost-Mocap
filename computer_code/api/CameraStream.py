
import cv2
import threading
import time
import numpy as np
from pseyepy import Camera

class CameraStream:
    def __init__(self, index):
        self.index = index
        self.camera = Camera(self.index, fps=60, resolution=Camera.RES_LARGE)
        self.frame = None
        self.running = True
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.start()

    def update(self):
        while self.running:
            self.frame, _ = self.camera.read()
            time.sleep(0.01)

    def get_frame(self):
        return self.frame

    def stop(self):
        self.running = False
        self.thread.join()
        self.capture.release()
