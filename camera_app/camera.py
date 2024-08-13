import cv2 as cv
import numpy as np
import os
import json
import time

from Singleton import Singleton

@Singleton
class Camera:
    def __init__(self):
        """
        Initialize the camera
        """
        dirname = os.path.dirname(__file__)
        filename = os.path.join(dirname, "camera-params.json")
        f = open(filename)

        self.camera_params = json.load(f)

        self.cap = cv.VideoCapture(0)

        self.is_capturing_points = False

        self.dev = True

    def set_is_capturing_points(self, is_capturing_points):
        """
        Set whether the camera is capturing points

        :param is_capturing_points: Whether the camera is capturing points
        :type is_capturing_points: bool
        """
        self.is_capturing_points = is_capturing_points

    def _camera_read(self):
        ret, frame = self.cap.read()
        processed_frame = None
        if ret:
            processed_frame = self.process_frame(frame)
        return processed_frame, time.time()

    def get_frame(self):
        """
        Get the current frame from the camera

        :rtype: numpy.ndarray
        """
        frame, timestamp = self._camera_read()
        image_points = []
        if self.is_capturing_points:
            frame, image_points = self._find_dot(frame)

        return frame, image_points, timestamp

    def get_camera_params(self):
        params = self.camera_params
        return {
            "intrinsic_matrix": np.array(params["intrinsic_matrix"]),
            "distortion_coef": np.array(params["distortion_coef"]),
            "rotation": params["rotation"]
        }

    def process_frame(self, frame):
        """
        Process the given frame

        :param frame: The frame to process
        :type frame: numpy.ndarray

        :rtype: numpy.ndarray
        """

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
    

    def _find_dot(self, img):
        """
        Find dots in the given image
        
        :param img: The image to find dots in
        :type img: numpy.ndarray
        
        :rtype: numpy.ndarray
        """

        # img = cv.GaussianBlur(img,(5,5),0)
        grey = cv.cvtColor(img, cv.COLOR_RGB2GRAY)
        grey = cv.threshold(grey, 255*0.2, 255, cv.THRESH_BINARY)[1]
        contours,_ = cv.findContours(grey, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)
        img = cv.drawContours(img, contours, -1, (0,255,0), 1)

        image_points = []
        for contour in contours:
            moments = cv.moments(contour)
            if moments["m00"] != 0:
                center_x = int(moments["m10"] / moments["m00"])
                center_y = int(moments["m01"] / moments["m00"])
                cv.putText(img, f'({center_x}, {center_y})', (center_x,center_y - 15), cv.FONT_HERSHEY_SIMPLEX, 0.3, (100,255,100), 1)
                cv.circle(img, (center_x,center_y), 1, (100,255,100), -1)
                image_points.append([center_x, center_y])

        if len(image_points) == 0:
            image_points = [[None, None]]

        return img, image_points

def make_square(img):
    """
    Make the given image square by padding it with edge pixel values

    :param img: The image to make square
    :type img: numpy.ndarray

    :rtype: numpy.ndarray
    """

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