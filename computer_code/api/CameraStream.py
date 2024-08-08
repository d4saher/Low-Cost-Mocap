import cv2
import threading
import time
import requests
import numpy as np

class CameraStream:
    def __init__(self, url):
        self.url = url
        self.frame = None
        self.running = True
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.start()

    def update(self):
        stream = requests.get(self.url, stream=True)
        bytes_data = b''
        for chunk in stream.iter_content(chunk_size=1024):
            bytes_data += chunk
            a = bytes_data.find(b'\xff\xd8')
            b = bytes_data.find(b'\xff\xd9')
            if a != -1 and b != -1:
                jpg = bytes_data[a:b + 2]
                bytes_data = bytes_data[b + 2:]
                self.frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if not self.running:
                break

    def get_frame(self):
        return self.frame

    def stop(self):
        self.running = False
        self.thread.join()
        self.capture.release()
