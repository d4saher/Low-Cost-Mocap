import cv2
import numpy as np
import os
import glob
import json
import time
import getch
from pseyepy import Camera, cam_count

MAX_DECIMALS = 8

def round_values(matrix, decimals=MAX_DECIMALS):
    return np.round(matrix, decimals).tolist()

# Get the number of available cameras
num_cameras = cam_count()
print(f"Number of cameras detected: {num_cameras}")

# Initialize all cameras
cams = Camera(fps=60, resolution=Camera.RES_LARGE)

def capture_images(cam_index, cams, num_images=30):
    output_dir = f'cam_{cam_index}'

    # Create the directory if it does not exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Wait 5 seconds before starting the capture loop
    print("Waiting 5 seconds before starting image capture...")
    time.sleep(5)

    # Discard the first frame
    cams.read()
    
    for i in range(num_images):
        print(f'Capturing image {i} for camera {cam_index}')
        frame, timestamp = cams.read(cam_index)
        #frame = frames[cam_index]  # Get frame for the specific camera
        
        # Save the frame
        filename = os.path.join(output_dir, f'image_{i}.jpg')
        cv2.imwrite(filename, frame)
        time.sleep(0.5)  # Wait half a second between captures

    print(f"Image capture completed for camera {cam_index}.")

def calibrate_camera(cam_index):
    cam_images_folder_name = f'cam_{cam_index}'
    cam_images_folder_name_calibrated = f'{cam_images_folder_name}_c'
    if not os.path.exists(cam_images_folder_name_calibrated):
        os.makedirs(cam_images_folder_name_calibrated)

    # Define the dimensions of the chessboard (5x6 inner squares)
    CHECKERBOARD = (5, 6)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    objpoints = []
    imgpoints = []

    # Definir los puntos 3D del chessboard en el espacio del chessboard y multiplicar por el tamaño de los recuadros
    objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)

    images = glob.glob(f'./{cam_images_folder_name}/*.jpg')
    processed_images = 0
    successful_images = 0

    for fname in images[1:]:  # Skip the first image
        img = cv2.imread(fname)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Enhance the contrast and brightness of the image
        gray = cv2.equalizeHist(gray)

        ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)

        if ret:
            objpoints.append(objp)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners2)
            img = cv2.drawChessboardCorners(img, CHECKERBOARD, corners2, ret)
            successful_images += 1

        new_frame_name = os.path.join(cam_images_folder_name_calibrated, os.path.basename(fname))
        cv2.imwrite(new_frame_name, img)
        processed_images += 1

    print(f"Total images processed for camera {cam_index}: {processed_images}")
    print(f"Images with detected corners for camera {cam_index}: {successful_images}")

    if len(objpoints) > 0 and len(imgpoints) > 0:
        h, w = img.shape[:2]
        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

        # Redondear valores a 8 decimales
        mtx = round_values(mtx, MAX_DECIMALS)
        dist = round_values(dist, MAX_DECIMALS)

        print("Camera matrix : \n")
        print(mtx)
        print("distortion coefficients : \n")
        print(dist)

        return {
            "intrinsic_matrix": mtx,
            "distortion_coef": dist,
            "rotation": 0
        }
    else:
        print("Not enough reference points found to perform calibration.")
        return None

camera_params = []

for cam_index in range(num_cameras):
    print(f"Press space to start capturing images for camera {cam_index}")
    
    # Wait for space key
    while getch.getch() != ' ':
        pass
    
    capture_images(cam_index, cams, num_images=30)  # Capture 30 images (first will be discarded)

    params = calibrate_camera(cam_index)
    if params is not None:
        camera_params.append(params)

# Save camera parameters to JSON
with open('camera-params.json', 'w') as json_file:
    json.dump(camera_params, json_file, indent=4)

# Clean up
cams.end()
print("Camera parameters saved to camera-params.json.")

