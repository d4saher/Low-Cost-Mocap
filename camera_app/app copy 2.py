import numpy as np
import cv2 as cv
import time
import paho.mqtt.client as mqtt
import json
import os

from camera import Camera

CAMERA_ID = "cam_1"

dirname = os.path.dirname(__file__)
filename = os.path.join(dirname, "camera-params.json")
f = open(filename)

camera_params = json.load(f)

camera = cv.VideoCapture(0)

is_capturing_points = False

dev = True

def get_frame():
    ret, frame = camera.read()
    if ret:
        processed_frame = process_frame(frame)
    return processed_frame, time.time()

def process_frame(frame):
    """
    Process the given frame

    :param frame: The frame to process
    :type frame: numpy.ndarray

    :rtype: numpy.ndarray
    """

    params = get_camera_params()
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

def get_camera_params():
    params = camera_params
    return {
        "intrinsic_matrix": np.array(params["intrinsic_matrix"]),
        "distortion_coef": np.array(params["distortion_coef"]),
        "rotation": params["rotation"]
    }

def send_points(points, timestamp):
    if not points:
        return

    client = mqtt.Client()
    client.connect("localhost", 1883, 60)

    topic = f"raspberrypi/{CAMERA_ID}/points"
    payload = {
        "timestamp": timestamp,
        "points": points
    }

    client.publish(topic, json.dumps(payload))
    client.disconnect()

if __name__ == "__main__":
    while True:
        frame, timestamp = get_frame()

        cv.imshow("Camera", frame)

        if cv.waitKey(1) & 0xFF == ord('q'):
            break

    camera.release()
    cv.destroyAllWindows()
