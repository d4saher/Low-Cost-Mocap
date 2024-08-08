import cv2 as cv
import numpy as np
import os
import json

from Singleton import Singleton
from pseyepy import Camera as PseyeCamera

@Singleton
class Camera:
    def __init__(self):
        self.camera = PseyeCamera(fps=60, resolution=PseyeCamera.RES_LARGE, gain=10, exposure=100)
        dirname = os.path.dirname(__file__)
        filename = os.path.join(dirname, "camera-params.json")
        f = open(filename)

        self.camera_params = json.load(f)

    def _camera_read(self):
        frame, timestamp = self.camera.read()
        processed_frame = self.process_frame(frame)
        return processed_frame

    def get_frame(self):
        return self._camera_read()

    def get_camera_params(self):
        params = self.camera_params
        return {
            "intrinsic_matrix": np.array(params["intrinsic_matrix"]),
            "distortion_coef": np.array(params["distortion_coef"]),
            "rotation": params["rotation"]
        }

    def process_frame(self, frame):
        params = self.get_camera_params()
        frame = np.rot90(frame, k=params["rotation"])
        frame = make_square(frame)
        frame = cv.undistort(frame, params["intrinsic_matrix"], params["distortion_coef"])
        frame = cv.GaussianBlur(frame, (9, 9), 0)
        kernel = np.array([[-2, -1, -1, -1, -2],
                            [-1, 1, 3, 1, -1],
                            [-1, 3, 4, 3, -1],
                            [-1, 1, 3, 1, -1],
                            [-2, -1, -1, -1, -2]])
        frame = cv.filter2D(frame, -1, kernel)
        frame = cv.cvtColor(frame, cv.COLOR_RGB2BGR)
        return frame

def make_square(img):
    x, y, _ = img.shape
    size = max(x, y)
    new_img = np.zeros((size, size, 3), dtype=np.uint8)
    ax,ay = (size - img.shape[1])//2,(size - img.shape[0])//2
    new_img[ay:img.shape[0]+ay,ax:ax+img.shape[1]] = img

    # Pad the new_img array with edge pixel values
    # Apply feathering effect
    feather_pixels = 8
    for i in range(feather_pixels):
        alpha = (i + 1) / feather_pixels
        new_img[ay - i - 1, :] = img[0, :] * (1 - alpha)  # Top edge
        new_img[ay + img.shape[0] + i, :] = img[-1, :] * (1 - alpha)  # Bottom edge

    return new_img