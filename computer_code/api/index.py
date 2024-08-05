from helpers import camera_pose_to_serializable, calculate_reprojection_errors, bundle_adjustment, Cameras, triangulate_points
from KalmanFilter import KalmanFilter

from flask import Flask, Response, request
import cv2 as cv
import numpy as np
import json
from scipy import linalg
import logging

from flask_socketio import SocketIO
import copy
import time
import serial
import threading
from ruckig import InputParameter, OutputParameter, Result, Ruckig
from flask_cors import CORS
import json

from drones.drone import Drone
from drones.esp32_drone import Esp32Drone
from drones.tello_drone import TelloDrone

serialLock = threading.Lock()

#ser = serial.Serial("/dev/cu.usbserial-02X2K2GE", 1000000, write_timeout=1, )

ser = None

app = Flask(__name__)
CORS(app, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins='*')

#Main logger configuration
logger = logging.getLogger('werkzeug')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.ERROR) # Deactivate werkzeug logs

cameras_init = False

num_objects = 2

# drones = [
#     #Esp32Drone(0, ser, serialLock),
#     TelloDrone(1),
# ]

tello_drone = TelloDrone(0)

def silence_logs(func):
    def wrapper(*args, **kwargs):
        log = logging.getLogger('werkzeug')
        previous_level = log.level
        log.setLevel(logging.ERROR)
        try:
            return func(*args, **kwargs)
        finally:
            log.setLevel(previous_level)
    return wrapper

@app.route("/api/drones", methods=["GET"])
def get_drones():
    return json.dumps({
        "drones": [drone.to_dict() for drone in Drone.get_all_drones()]
    })

@app.route("/api/camera-stream")
@silence_logs
def camera_stream():
    cameras = Cameras.instance()
    cameras.set_socketio(socketio)
    cameras.set_ser(ser)
    cameras.set_serialLock(serialLock)
    cameras.set_num_objects(num_objects)
    
    def gen(cameras):
        frequency = 150
        loop_interval = 1.0 / frequency
        last_run_time = 0
        i = 0

        while True:
            time_now = time.time()

            i = (i+1)%10
            if i == 0:
                socketio.emit("fps", {"fps": round(1/(time_now - last_run_time))})

            if time_now - last_run_time < loop_interval:
                time.sleep(last_run_time - time_now + loop_interval)
            last_run_time = time.time()
            frames = cameras.get_frames()
            jpeg_frame = cv.imencode('.jpg', frames)[1].tobytes()

            yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + jpeg_frame + b'\r\n')

    return Response(gen(cameras), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/api/trajectory-planning", methods=["POST"])
def trajectory_planning_api():
    data = json.loads(request.data)

    waypoint_groups = [] # grouped by continuious movement (no stopping)
    for waypoint in data["waypoints"]:
        stop_at_waypoint = waypoint[-1]
        if stop_at_waypoint:
            waypoint_groups.append([waypoint[:3*num_objects]])
        else:
            waypoint_groups[-1].append(waypoint[:3*num_objects])
    
    setpoints = []
    for i in range(0, len(waypoint_groups)-1):
        start_pos = waypoint_groups[i][0]
        end_pos = waypoint_groups[i+1][0]
        waypoints = waypoint_groups[i][1:]
        setpoints += plan_trajectory(start_pos, end_pos, waypoints, data["maxVel"], data["maxAccel"], data["maxJerk"], data["timestep"])

    return json.dumps({
        "setpoints": setpoints
    })

def plan_trajectory(start_pos, end_pos, waypoints, max_vel, max_accel, max_jerk, timestep):
    otg = Ruckig(3*num_objects, timestep, len(waypoints))  # DoFs, timestep, number of waypoints
    inp = InputParameter(3*num_objects)
    out = OutputParameter(3*num_objects, len(waypoints))

    inp.current_position = start_pos
    inp.current_velocity = [0,0,0]*num_objects
    inp.current_acceleration = [0,0,0]*num_objects

    inp.target_position = end_pos
    inp.target_velocity = [0,0,0]*num_objects
    inp.target_acceleration = [0,0,0]*num_objects

    inp.intermediate_positions = waypoints

    inp.max_velocity = max_vel*num_objects
    inp.max_acceleration = max_accel*num_objects
    inp.max_jerk = max_jerk*num_objects

    setpoints = []
    res = Result.Working
    while res == Result.Working:
        res = otg.update(inp, out)
        setpoints.append(copy.copy(out.new_position))
        out.pass_to_input(inp)

    return setpoints

@socketio.on("arm-drone")
def arm_drone(data):
    print("Arm drone")
    print(data["droneArmed"])
    print(len(Drone.existing_drones()))
    global cameras_init
    print(cameras_init)
    if not Cameras.has_instance():
        print("Cameras not initialized")
        return
    drones = Drone.existing_drones()
    for droneIndex in range(0, len(drones)):
        if data["droneArmed"][droneIndex] != drones[droneIndex].is_armed():
            drones[droneIndex].arm(data["droneArmed"][droneIndex])

    Cameras.instance().drone_armed = data["droneArmed"]

@socketio.on("set-drone-pid")
def set_drone_pid(data):
    print("Set drone PID")
    drones = Drone.existing_drones()
    drones[data['droneIndex']].set_pid(data["dronePID"])

@socketio.on("set-drone-setpoint")
def set_drone_setpoint(data):
    print("Set drone setpoint")
    drones = Drone.existing_drones()
    drones[data['droneIndex']].set_setpoint(data["droneSetpoint"])

@socketio.on("set-drone-trim")
def set_drone_trim(data):
    print("Set drone trim")
    drones = Drone.existing_drones()
    drones[data['droneIndex']].set_trim(data["droneTrim"])

@socketio.on("acquire-floor")
def acquire_floor(data):
    # Obtiene la instancia única de la clase Cameras.
    #cameras = Cameras.instance()
    
    # Obtiene los puntos del objeto del diccionario de datos recibido.
    object_points = data["objectPoints"]
    
    # Convierte object_points en un array de numpy, aplanando la lista de listas.
    object_points = np.array([item for sublist in object_points for item in sublist])

    print(object_points)

    # Inicializa listas temporales para los coeficientes de la matriz A y el vector b.
    tmp_A = []
    tmp_b = []
    
    # Llena tmp_A con las coordenadas x, y y un valor constante 1, y tmp_b con las coordenadas z.
    for i in range(len(object_points)):
        tmp_A.append([object_points[i, 0], object_points[i, 1], 1])
        tmp_b.append(object_points[i, 2])
    
    # Convierte tmp_b a una matriz columna y tmp_A a una matriz.
    b = np.matrix(tmp_b).T
    A = np.matrix(tmp_A)

    # Resuelve el sistema de ecuaciones lineales para encontrar la mejor aproximación del plano.
    fit, residual, rnk, s = linalg.lstsq(A, b)
    
    # Transpone y extrae los coeficientes del ajuste.
    fit = fit.T[0]

    # Calcula el vector normal del plano.
    plane_normal = np.array([[fit[0]], [fit[1]], [-1]])
    
    # Normaliza el vector normal.
    plane_normal = plane_normal / linalg.norm(plane_normal)
    
    # Vector normal hacia arriba.
    up_normal = np.array([[0], [0], [1]], dtype=np.float32)

    # Define el plano con los coeficientes ajustados.
    plane = np.array([fit[0], fit[1], -1, fit[2]])

    print(plane)

    # Matriz de rotación G basada en el ángulo entre el vector normal del plano y el vector hacia arriba.
    G = np.array([
        [np.dot(plane_normal.T, up_normal)[0][0], -linalg.norm(np.cross(plane_normal.T[0], up_normal.T[0])), 0],
        [linalg.norm(np.cross(plane_normal.T[0], up_normal.T[0])), np.dot(plane_normal.T, up_normal)[0][0], 0],
        [0, 0, 1]
    ])
    
    # Matriz F basada en la base ortonormal creada a partir de los vectores normalizados.
    F = np.array([plane_normal.T[0], 
                  ((up_normal - np.dot(plane_normal.T, up_normal)[0][0] * plane_normal) / linalg.norm((up_normal - np.dot(plane_normal.T, up_normal)[0][0] * plane_normal))).T[0], 
                  np.cross(up_normal.T[0], plane_normal.T[0])]).T
    
    # Calcula la matriz de rotación R.
    R = F @ G @ linalg.inv(F)

    # Ajuste manual a la matriz de rotación.
    R = R @ [[1, 0, 0], [0, -1, 0], [0, 0, 1]]  # i dont fucking know why

    # Crea una nueva matriz de transformación que incluye la rotación R y una columna de traslación nula.
    new_transform = np.array(np.vstack((np.c_[R, [0, 0, 0]], [[0, 0, 0, 1]])))

    # Aplica la nueva matriz de transformación al plano.
    transformed_plane = new_transform @ plane  # Aplicar transformación

    # Actualiza la matriz de coordenadas globales en la instancia de cámaras.
    #cameras.to_world_coords_matrix = new_transform

    # Emite un evento con la nueva matriz de transformación y los datos del plano.
    socketio.emit("to-world-coords-matrix", {
        "to_world_coords_matrix": new_transform.tolist(),
        "floor_plane": plane.tolist(),
        "transformed_floor_plane": transformed_plane.tolist()
    })

@socketio.on("set-origin")
def set_origin(data):
    cameras = Cameras.instance()

    object_point = np.array(data["objectPoint"])
    to_world_coords_matrix = np.array(data["toWorldCoordsMatrix"])

    print("Object Point:", object_point)  # Debugging print
    print("To World Coords Matrix:", to_world_coords_matrix)  # Debugging print
    
    transform_matrix = np.eye(4)

    object_point[1], object_point[2] = object_point[2], object_point[1] # i dont fucking know why
    transform_matrix[:3, 3] = -object_point

    to_world_coords_matrix = transform_matrix @ to_world_coords_matrix
    cameras.to_world_coords_matrix = to_world_coords_matrix

    socketio.emit("to-world-coords-matrix", {"to_world_coords_matrix": cameras.to_world_coords_matrix.tolist()})

@socketio.on("update-camera-settings")
def change_camera_settings(data):
    cameras = Cameras.instance()
    
    cameras.edit_settings(data["exposure"], data["gain"])

@socketio.on("capture-points")
def capture_points(data):
    start_or_stop = data["startOrStop"]
    cameras = Cameras.instance()

    if (start_or_stop == "start"):
        cameras.start_capturing_points()
        return
    elif (start_or_stop == "stop"):
        cameras.stop_capturing_points()

def rotation_matrix(axis, angle_degrees):
    angle_radians = np.radians(angle_degrees)
    if axis == 'x':
        return np.array([
            [1, 0, 0],
            [0, np.cos(angle_radians), -np.sin(angle_radians)],
            [0, np.sin(angle_radians), np.cos(angle_radians)]
        ])
    elif axis == 'y':
        return np.array([
            [np.cos(angle_radians), 0, np.sin(angle_radians)],
            [0, 1, 0],
            [-np.sin(angle_radians), 0, np.cos(angle_radians)]
        ])
    elif axis == 'z':
        return np.array([
            [np.cos(angle_radians), -np.sin(angle_radians), 0],
            [np.sin(angle_radians), np.cos(angle_radians), 0],
            [0, 0, 1]
        ])

@socketio.on("rotate-scene")
def rotate_scene(data):
    axis = data['axis']
    increment = data['increment']
    angle = 1 * increment  # 1 degree increment or decrement

    cameras = Cameras.instance()
    # Assuming to_world_coords_matrix is a 4x4 matrix
    to_world_coords_matrix = np.array(cameras.to_world_coords_matrix)

    # Extract the rotation part of the matrix
    rotation_part = to_world_coords_matrix[:3, :3]

    # Calculate the rotation matrix
    rotation = rotation_matrix(axis, angle)

    # Apply the rotation
    new_rotation_part = rotation @ rotation_part

    # Update the to_world_coords_matrix with the new rotation part
    to_world_coords_matrix[:3, :3] = new_rotation_part
    
    cameras.to_world_coords_matrix = to_world_coords_matrix

    # Emit the updated matrix back to clients
    socketio.emit("to-world-coords-matrix", {
        "to_world_coords_matrix": to_world_coords_matrix.tolist()
    })

    print("Rotated scene around {} axis by {} degrees".format(axis, angle))

# Test function to store poses as points and direction vectors for the cameras
@socketio.on("calculate-camera-positions")
def calculate_camera_positions(data):
    print("Calculte camera positions")
    cameras = Cameras.instance()
    camera_poses = data["cameraPoses"]
    to_world_coords_matrix = data["toWorldCoordsMatrix"]
    cameras.to_world_coords_matrix = to_world_coords_matrix
    print(to_world_coords_matrix)

    camera_positions = []
    camera_directions = []
    for i in range(len(camera_poses)):
        t = np.array(camera_poses[i]["t"])
        R = np.array(camera_poses[i]["R"])

        #Invert z axis (Threejs uses (x, z, y) and z is to the outside of the screen)
        t = np.array([[1,0,0],[0,-1,0],[0,0,1]]) @ t
        R = np.array([[1,0,0],[0,-1,0],[0,0,1]]) @ R

        # Convertir la posición a coordenadas homogéneas
        position_homogeneous = np.append(t, 1)
        position_transformed = to_world_coords_matrix @ position_homogeneous
        position = position_transformed[:3].tolist()

        # Calcular la dirección y transformar (sin la componente de traslación)
        direction = (R @ np.array([0, 0, 1])).tolist()
        direction_homogeneous = np.append(direction, 0)
        direction_transformed = to_world_coords_matrix @ direction_homogeneous
        direction = direction_transformed[:3].tolist()

        # Almacenar las posiciones y direcciones transformadas
        camera_positions.append(position)
        camera_directions.append(direction)

    cameras.camera_positions = camera_positions
    cameras.camera_directions = camera_directions

    print("Camera positions: ", camera_positions)

    socketio.emit("camera-positions", {
        "camera_positions": camera_positions,
        "camera_directions": camera_directions
    })

@socketio.on("calculate-camera-pose")
def calculate_camera_pose(data):
    cameras = Cameras.instance()
    image_points = np.array(data["cameraPoints"])
    image_points_t = image_points.transpose((1, 0, 2))

    camera_poses = [{
        "R": np.eye(3),
        "t": np.array([[0],[0],[0]], dtype=np.float32)
    }]

    # Lista para almacenar posiciones y direcciones de las cámaras
    camera_positions = []
    camera_directions = []

    for camera_i in range(0, cameras.num_cameras-1):
        camera1_image_points = image_points_t[camera_i]
        camera2_image_points = image_points_t[camera_i+1]
        not_none_indicies = np.where(np.all(camera1_image_points != None, axis=1) & np.all(camera2_image_points != None, axis=1))[0]
        camera1_image_points = np.take(camera1_image_points, not_none_indicies, axis=0).astype(np.float32)
        camera2_image_points = np.take(camera2_image_points, not_none_indicies, axis=0).astype(np.float32)

        F, _ = cv.findFundamentalMat(camera1_image_points, camera2_image_points, cv.FM_RANSAC, 1, 0.99999)
        E = cv.sfm.essentialFromFundamental(F, cameras.get_camera_params(0)["intrinsic_matrix"], cameras.get_camera_params(1)["intrinsic_matrix"])
        possible_Rs, possible_ts = cv.sfm.motionFromEssential(E)

        R = None
        t = None
        max_points_infront_of_camera = 0
        for i in range(0, 4):
            object_points = triangulate_points(np.hstack([np.expand_dims(camera1_image_points, axis=1), np.expand_dims(camera2_image_points, axis=1)]), np.concatenate([[camera_poses[-1]], [{"R": possible_Rs[i], "t": possible_ts[i]}]]))
            object_points_camera_coordinate_frame = np.array([possible_Rs[i].T @ object_point for object_point in object_points])

            points_infront_of_camera = np.sum(object_points[:,2] > 0) + np.sum(object_points_camera_coordinate_frame[:,2] > 0)

            if points_infront_of_camera > max_points_infront_of_camera:
                max_points_infront_of_camera = points_infront_of_camera
                R = possible_Rs[i]
                t = possible_ts[i]

        R = R @ camera_poses[-1]["R"]
        t = camera_poses[-1]["t"] + (camera_poses[-1]["R"] @ t)

        camera_poses.append({
            "R": R,
            "t": t
        })

        #Calculate camera position
        # Calcula y almacena la posición de la cámara
        position = t.flatten()
        camera_positions.append(position)

        # Calcula y almacena la dirección de la cámara
        direction = R @ np.array([0, 0, 1])
        camera_directions.append(direction)

    cameras.camera_positions = camera_positions
    cameras.camera_directions = camera_directions

    camera_poses = bundle_adjustment(image_points, camera_poses, socketio)

    object_points = triangulate_points(image_points, camera_poses)
    error = np.mean(calculate_reprojection_errors(image_points, object_points, camera_poses))

    socketio.emit("camera-pose", {"camera_poses": camera_pose_to_serializable(camera_poses)})

@socketio.on("locate-objects")
def start_or_stop_locating_objects(data):
    cameras = Cameras.instance()
    start_or_stop = data["startOrStop"]

    if (start_or_stop == "start"):
        cameras.start_locating_objects()
        return
    elif (start_or_stop == "stop"):
        cameras.stop_locating_objects()

@socketio.on("determine-scale")
def determine_scale(data):
    object_points = data["objectPoints"]
    camera_poses = data["cameraPoses"]
    actual_distance = 0.15
    observed_distances = []

    for object_points_i in object_points:
        if len(object_points_i) != 2:
            continue

        object_points_i = np.array(object_points_i)

        observed_distances.append(np.sqrt(np.sum((object_points_i[0] - object_points_i[1])**2)))

    scale_factor = actual_distance/np.mean(observed_distances)
    for i in range(0, len(camera_poses)):
        camera_poses[i]["t"] = (np.array(camera_poses[i]["t"]) * scale_factor).tolist()

    socketio.emit("camera-pose", {"error": None, "camera_poses": camera_poses})


@socketio.on("triangulate-points")
def live_mocap(data):
    cameras = Cameras.instance()
    start_or_stop = data["startOrStop"]
    camera_poses = data["cameraPoses"]
    cameras.to_world_coords_matrix = data["toWorldCoordsMatrix"]

    if (start_or_stop == "start"):
        cameras.start_trangulating_points(camera_poses)
        return
    elif (start_or_stop == "stop"):
        cameras.stop_trangulating_points()


if __name__ == '__main__':
    socketio.run(app, port=3001, debug=False, use_reloader=False)