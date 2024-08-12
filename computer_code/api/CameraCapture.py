import cv2
import threading
import time

class CameraCapture(threading.Thread):
    def __init__(self, camera_id):
        threading.Thread.__init__(self)
        self.camera_id = camera_id
        print(f"CameraCapture: {self.camera_id}")
        self.cap = cv2.VideoCapture(camera_id)
        self.frame = None
        self.ret = False
        self.stopped = False

    def run(self):
        while not self.stopped:
            #print(f"CameraCapture: {self.camera_id}")
            self.ret, self.frame = self.cap.read()
            if not self.ret:
                print(f"CameraCapture: {self.camera_id} failed to read frame")

    def stop(self):
        self.stopped = True
        self.cap.release()

    def get_frame(self):
        return self.ret, self.frame
