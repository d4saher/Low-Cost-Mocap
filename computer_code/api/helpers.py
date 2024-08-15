import concurrent.futures
import requests
import numpy as np
from scipy import linalg, optimize, signal
import cv2 as cv
from scipy.spatial.transform import Rotation
import copy
import json
import os
import time
import numpy as np
import cv2 as cv
import paho.mqtt.client as mqtt
from KalmanFilter import KalmanFilter
from Singleton import Singleton

from drones.drone import Drone
from CameraStream import CameraStream

@Singleton
class Cameras:

    def __init__(self):
        dirname = os.path.dirname(__file__)
        filename = os.path.join(dirname, "camera-params.json")
        f = open(filename)
        self.camera_params = json.load(f)

        self.is_capturing_points = False

        self.is_triangulating_points = False
        self.camera_poses = None
        self.camera_positions = None
        self.camera_directions = None

        self.is_locating_objects = False

        self.to_world_coords_matrix = None

        self.drone_armed = []

        self.num_objects = None

        self.kalman_filter = None

        self.socketio = None
        self.ser = None

        self.serialLock = None

        #MQTT client configuration
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect("localhost", 1883, 60)
        self.mqtt_client.loop_start()

        self.num_cameras = 4
        self.image_points = [None] * self.num_cameras
        self.frame_ready = False
        self.processing_interval = 0.1
        self.last_processing_time = time.time()

    def set_socketio(self, socketio):
        self.socketio = socketio
    
    def set_ser(self, ser):
        self.ser = ser

    def set_serialLock(self, serialLock):
        self.serialLock = serialLock

    def set_num_objects(self, num_objects):
        self.num_objects = num_objects
        self.drone_armed = [False for i in range(0, self.num_objects)]

    def get_frame_is_ready(self):
        return self.frame_ready
    
    def edit_settings(self, exposure, gain):
        self.cameras.exposure = [exposure] * self.num_cameras
        self.cameras.gain = [gain] * self.num_cameras

    def _camera_read(self):

        start_time = time.time()
        frames = []

        for i, data in enumerate(self.image_points):
            #if data and data['points']:
                #print(f"Camara {i+1}: {data['points']} at {data['timestamp']}")
            frames.append(self.generate_frame_with_points(i, data))
                        
        #Capturing points for camera pose and live triangulation
        if self.is_capturing_points:
            
            #if any(np.all(image_point['points'][0] != [None, None]) for image_point in self.image_points):
            if (any(np.all(point[0] != [None,None]) for point in self.image_points)):
                if self.is_capturing_points and not self.is_triangulating_points:
                    #self.socketio.emit("image-points", [x['points'][0] for x in self.image_points if x and 'points' in x])
                    self.socketio.emit("image-points", [x[0] for x in self.image_points])

                elif self.is_triangulating_points:
                    errors, object_points, frames = find_point_correspondance_and_object_points(self.image_points, self.camera_poses, frames)

                    # convert to world coordinates
                    for i, object_point in enumerate(object_points):
                        new_object_point = np.array([[-1,0,0],[0,-1,0],[0,0,1]]) @ object_point
                        new_object_point = np.concatenate((new_object_point, [1]))
                        new_object_point = np.array(self.to_world_coords_matrix) @ new_object_point
                        new_object_point = new_object_point[:3] / new_object_point[3]
                        new_object_point[1], new_object_point[2] = new_object_point[2], new_object_point[1]
                        object_points[i] = new_object_point

                    objects = []
                    filtered_objects = []
                    if self.is_locating_objects:
                        objects = locate_objects(object_points, errors)
                        filtered_objects = self.kalman_filter.predict_location(objects)
                    
                        if len(filtered_objects) != 0:
                            drones = Drone.existing_drones()
                            #print("Filtered Objects: ", len(filtered_objects))
                            for filtered_object in filtered_objects:
                                drone_index = filtered_object['droneIndex']
                                if drone_index < len(drones):
                                    #if drones[drone_index].is_armed():
                                        filtered_object["heading"] = round(filtered_object["heading"], 4)
                                        position = filtered_object["pos"].tolist()
                                        velocity = filtered_object["vel"].tolist()
                                        heading = filtered_object["heading"]
                                        drones[drone_index].update_position_and_velocity(position, velocity, heading)

                            
                        for filtered_object in filtered_objects:
                            filtered_object["vel"] = filtered_object["vel"].tolist()
                            filtered_object["pos"] = filtered_object["pos"].tolist()
                    
                    self.socketio.emit("object-points", {
                        "object_points": object_points.tolist(), 
                        "errors": errors.tolist(), 
                        "objects": [{k:(v.tolist() if isinstance(v, np.ndarray) else v) for (k,v) in object.items()} for object in objects], 
                        "filtered_objects": filtered_objects
                    })

        self.image_points = [None] * self.num_cameras
        self.frame_ready = False

        end_time = time.time()
        #print(f"Execution time without threads: {end_time - start_time} seconds")
        
        return frames

    def get_frames(self):
        frames = self._camera_read()
        valid_frames = [frame for frame in frames if frame is not None and isinstance(frame, np.ndarray)]
        if valid_frames:
            return np.hstack(valid_frames)
        else:
            return None
    

    def start_capturing_points(self):
        self.is_capturing_points = True
        self.mqtt_client.publish("tb-tracker/is_capturing_points", "true")

    def stop_capturing_points(self):
        self.is_capturing_points = False
        self.mqtt_client.publish("tb-tracker/is_capturing_points", "false")

    def start_trangulating_points(self, camera_poses):
        self.is_capturing_points = True
        self.mqtt_client.publish("tb-tracker/is_capturing_points", "true")
        self.is_triangulating_points = True
        self.camera_poses = camera_poses
        self.kalman_filter = KalmanFilter(self.num_objects)

    def stop_trangulating_points(self):
        self.is_capturing_points = False
        self.mqtt_client.publish("tb-tracker/is_capturing_points", "false")
        self.is_triangulating_points = False
        self.camera_poses = None

    def start_locating_objects(self):
        self.is_locating_objects = True
        self.mqtt_client.publish("tb-tracker/is_capturing_points", "true")

    def stop_locating_objects(self):
        self.is_locating_objects = False
        self.mqtt_client.publish("tb-tracker/is_capturing_points", "false")
    
    def get_camera_params(self, camera_num):
        return {
            "intrinsic_matrix": np.array(self.camera_params[camera_num]["intrinsic_matrix"]),
            "distortion_coef": np.array(self.camera_params[camera_num]["distortion_coef"]),
            "rotation": self.camera_params[camera_num]["rotation"]
        }
    
    def set_camera_params(self, camera_num, intrinsic_matrix=None, distortion_coef=None):
        if intrinsic_matrix is not None:
            self.camera_params[camera_num]["intrinsic_matrix"] = intrinsic_matrix
        
        if distortion_coef is not None:
            self.camera_params[camera_num]["distortion_coef"] = distortion_coef

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected with result code {rc}")

        client.subscribe("tb-tracker/cam_1/points")
        client.subscribe("tb-tracker/cam_2/points")
        client.subscribe("tb-tracker/cam_3/points")
        client.subscribe("tb-tracker/cam_4/points")

    def on_message(self, client, userdata, msg):
        # Identificar de qué cámara provienen los puntos
        camera_id = None
        if msg.topic == "tb-tracker/cam_1/points":
            camera_id = 0
        elif msg.topic == "tb-tracker/cam_2/points":
            camera_id = 1
        elif msg.topic == "tb-tracker/cam_3/points":
            camera_id = 2
        elif msg.topic == "tb-tracker/cam_4/points":
            camera_id = 3

        if camera_id is not None:
            # Decodificar el mensaje y extraer los puntos
            data = json.loads(msg.payload.decode())
            points = data.get("points", [None, None])
            timestamp = data.get("timestamp", None)

            # Almacenar los puntos en la posición correspondiente del array
            # self.image_points[camera_id] = {
            #     'points': points,
            #     'timestamp': timestamp
            # }

            self.image_points[camera_id] = points
            
            if all(data is not None for data in self.image_points):
                # if any(np.all(image_point['points'][0] != [None, None]) for image_point in self.image_points):
                #     print(self.image_points)
                self.frame_ready = True
            
            # if points[0] != [None, None]:
            #print(f"Received points from cam_{camera_id + 1}: {points}")
        

    def generate_frame_with_points(self, camera_index, image_points):
        # Tamaño cuadrado original (640x640 píxeles)
        square_size = 640
        
        # Tamaño deseado (320x240 píxeles)
        output_width = 320
        output_height = 320

        # Crear una imagen negra de 320x240 píxeles
        frame = np.zeros((output_height, output_width, 3), dtype=np.uint8)

        # if data and data['points']:
        if image_points != None:
            # Calcular el padding aplicado a la imagen cuadrada original (ay será 80 en este caso)
            ax = (square_size - 640) // 2  # En este caso, ax será 0
            ay = (square_size - 480) // 2  # En este caso, ay será 80

            # Calcular factores de escala para convertir de 640x640 a 320x240
            scale_x = output_width / square_size
            scale_y = output_height / square_size

            # Dibujar los puntos en la imagen escalada
            #if data["points"] != []:
            #for point in data["points"]:
            for point in image_points:
                if len(point) == 2 and point != [None, None]:
                    # Ajustar las coordenadas del punto según el padding y escalar a la nueva resolución
                    x = int((point[0] + ax) * scale_x)
                    y = int((point[1] ) * scale_y)
                    
                    # Verificar que las coordenadas están dentro de los límites de la imagen de salida
                    if 0 <= x < output_width and 0 <= y < output_height:
                        cv.circle(frame, (x, y), 2, (0, 255, 0), -1)  # Puntos verdes
                    else:
                        print(f"Point {point} out of bounds after scaling for camera {camera_index + 1}")

        return frame

def calculate_reprojection_errors(image_points, object_points, camera_poses):
    errors = np.array([])
    for image_points_i, object_point in zip(image_points, object_points):
        error = calculate_reprojection_error(image_points_i, object_point, camera_poses)
        if error is None:
            continue
        errors = np.concatenate([errors, [error]])

    return errors


def calculate_reprojection_error(image_points, object_point, camera_poses):
    cameras = Cameras.instance()

    image_points = np.array(image_points)
    none_indicies = np.where(np.all(image_points == None, axis=1))[0]
    image_points = np.delete(image_points, none_indicies, axis=0)
    camera_poses = np.delete(camera_poses, none_indicies, axis=0)

    if len(image_points) <= 1:
        return None

    image_points_t = image_points.transpose((0,1))

    errors = np.array([])
    for i, camera_pose in enumerate(camera_poses):
        if np.all(image_points[i] == None, axis=0):
            continue
        projected_img_points, _ = cv.projectPoints(
            np.expand_dims(object_point, axis=0).astype(np.float32), 
            np.array(camera_pose["R"], dtype=np.float64), 
            np.array(camera_pose["t"], dtype=np.float64), 
            cameras.get_camera_params(i)["intrinsic_matrix"], 
            np.array([])
        )
        projected_img_point = projected_img_points[:,0,:][0]
        errors = np.concatenate([errors, (image_points_t[i]-projected_img_point).flatten() ** 2])
    
    return errors.mean()


def bundle_adjustment(image_points, camera_poses, socketio):
    cameras = Cameras.instance()

    def params_to_camera_poses(params):
        focal_distances = []
        num_cameras = int((params.size-1)/7)+1
        camera_poses = [{
            "R": np.eye(3),
            "t": np.array([0,0,0], dtype=np.float32)
        }]
        focal_distances.append(params[0])
        for i in range(0, num_cameras-1):
            focal_distances.append(params[i*7+1])
            camera_poses.append({
                "R": Rotation.as_matrix(Rotation.from_rotvec(params[i*7 + 2 : i*7 + 3 + 2])),
                "t": params[i*7 + 3 + 2 : i*7 + 6 + 2]
            })

        return camera_poses, focal_distances

    def residual_function(params):
        camera_poses, focal_distances = params_to_camera_poses(params)
        for i in range(0, len(camera_poses)):
            intrinsic = cameras.get_camera_params(i)["intrinsic_matrix"]
            intrinsic[0, 0] = focal_distances[i]
            intrinsic[1, 1] = focal_distances[i]
            # cameras.set_camera_params(i, intrinsic)
        object_points = triangulate_points(image_points, camera_poses)
        errors = calculate_reprojection_errors(image_points, object_points, camera_poses)
        errors = errors.astype(np.float32)
        socketio.emit("camera-pose", {"camera_poses": camera_pose_to_serializable(camera_poses)})
        
        return errors

    focal_distance = cameras.get_camera_params(0)["intrinsic_matrix"][0,0]
    init_params = np.array([focal_distance])
    for i, camera_pose in enumerate(camera_poses[1:]):
        rot_vec = Rotation.as_rotvec(Rotation.from_matrix(camera_pose["R"])).flatten()
        focal_distance = cameras.get_camera_params(i)["intrinsic_matrix"][0,0]
        init_params = np.concatenate([init_params, [focal_distance]])
        init_params = np.concatenate([init_params, rot_vec])
        init_params = np.concatenate([init_params, camera_pose["t"].flatten()])

    res = optimize.least_squares(
        residual_function, init_params, verbose=2, loss="huber", ftol=1E-2
    )
    return params_to_camera_poses(res.x)[0]
    

def triangulate_point(image_points, camera_poses):
    image_points = np.array(image_points)
    cameras = Cameras.instance()
    none_indicies = np.where(np.all(image_points == None, axis=1))[0]
    image_points = np.delete(image_points, none_indicies, axis=0)
    camera_poses = np.delete(camera_poses, none_indicies, axis=0)

    if len(image_points) <= 1:
        return [None, None, None]

    Ps = [] # projection matricies

    for i, camera_pose in enumerate(camera_poses):
        RT = np.c_[camera_pose["R"], camera_pose["t"]]
        P = cameras.camera_params[i]["intrinsic_matrix"] @ RT
        Ps.append(P)

    # https://temugeb.github.io/computer_vision/2021/02/06/direct-linear-transorms.html
    def DLT(Ps, image_points):
        A = []

        for P, image_point in zip(Ps, image_points):
            A.append(image_point[1]*P[2,:] - P[1,:])
            A.append(P[0,:] - image_point[0]*P[2,:])
            
        A = np.array(A).reshape((len(Ps)*2,4))
        B = A.transpose() @ A
        U, s, Vh = linalg.svd(B, full_matrices = False)
        object_point = Vh[3,0:3]/Vh[3,3]

        return object_point

    object_point = DLT(Ps, image_points)

    return object_point


def triangulate_points(image_points, camera_poses):
    object_points = []
    for image_points_i in image_points:
        object_point = triangulate_point(image_points_i, camera_poses)
        object_points.append(object_point)
    
    return np.array(object_points)


def find_point_correspondance_and_object_points(image_points, camera_poses, frames):
    cameras = Cameras.instance()

    image_points = copy.deepcopy(image_points) # copy because image_points may be ocuppied by on_message

    for image_points_i in image_points:
        try:
            image_points_i.remove([None, None])
        except:
            pass


    # for image_points_i in image_points:
    #     try:
    #         print(image_points_i)
    #         image_points_i.remove([None, None])
    #     except:
    #         pass

    # [object_points, possible image_point groups, image_point from camera]
    correspondances = [[[i]] for i in image_points[0]]

    Ps = [] # projection matricies
    for i, camera_pose in enumerate(camera_poses):
        RT = np.c_[camera_pose["R"], camera_pose["t"]]
        P = cameras.camera_params[i]["intrinsic_matrix"] @ RT
        Ps.append(P)

    root_image_points = [{"camera": 0, "point": point} for point in image_points[0]]

    for i in range(1, len(camera_poses)):
        epipolar_lines = []
        for root_image_point in root_image_points:
            F = cv.sfm.fundamentalFromProjections(Ps[root_image_point["camera"]], Ps[i])
            line = cv.computeCorrespondEpilines(np.array([root_image_point["point"]], dtype=np.float32), 1, F)
            scaled_line = scale_epipolar_line(line)

            epipolar_lines.append(line[0,0].tolist())
            frames[i] = drawlines(frames[i], scaled_line[0])

        not_closest_match_image_points = np.array(image_points[i])
        points = np.array(image_points[i])

        for j, [a, b, c] in enumerate(epipolar_lines):
            distances_to_line = np.array([])
            print(f"Camera {i} - Line {j}: {a}x + {b}y + {c} = 0")
            print(f"Points: {points}")
            if len(points) != 0:
                distances_to_line = np.abs(a*points[:,0] + b*points[:,1] + c) / np.sqrt(a**2 + b**2) ## ERROR

            possible_matches = points[distances_to_line < 5].copy()

            # Commenting out this code produces more points, but more garbage points too
            # delete closest match from future consideration
            # if len(points) != 0:
            #     points = np.delete(points, np.argmin(distances_to_line), axis=0)

            # sort possible matches from smallest to largest
            distances_to_line = distances_to_line[distances_to_line < 5]
            possible_matches_sorter = distances_to_line.argsort()
            possible_matches = possible_matches[possible_matches_sorter]
    
            if len(possible_matches) == 0:
                for possible_group in correspondances[j]:
                    possible_group.append([None, None])
            else:
                not_closest_match_image_points = [row for row in not_closest_match_image_points.tolist() if row != possible_matches.tolist()[0]]
                not_closest_match_image_points = np.array(not_closest_match_image_points)
                
                new_correspondances_j = []
                for possible_match in possible_matches:
                    temp = copy.deepcopy(correspondances[j])
                    for possible_group in temp:
                        possible_group.append(possible_match.tolist())
                    new_correspondances_j += temp
                correspondances[j] = new_correspondances_j

        for not_closest_match_image_point in not_closest_match_image_points:
            root_image_points.append({"camera": i, "point": not_closest_match_image_point})
            temp = [[[None, None]] * i]
            temp[0].append(not_closest_match_image_point.tolist())
            correspondances.append(temp)

    object_points = []
    errors = []
    for image_points in correspondances:
        object_points_i = triangulate_points(image_points, camera_poses)

        if np.all(object_points_i == None):
            continue

        errors_i = calculate_reprojection_errors(image_points, object_points_i, camera_poses)

        object_points.append(object_points_i[np.argmin(errors_i)])
        errors.append(np.min(errors_i))

    return np.array(errors), np.array(object_points), frames

def scale_epipolar_line(line, scale_factor=0.5):
    # Recuperar los coeficientes de la línea
    a, b, c = line[0, 0, 0], line[0, 0, 1], line[0, 0, 2]
    
    # Escalar los coeficientes
    a_scaled = a * scale_factor
    b_scaled = b * scale_factor
    c_scaled = c * scale_factor
    
    # Devolver la línea escalada en el mismo formato que la original
    return np.array([[[a_scaled, b_scaled, c_scaled]]])

def locate_objects(object_points, errors):
    dist1 = 0.095
    dist2 = 0.15

    distance_matrix = np.zeros((object_points.shape[0], object_points.shape[0]))
    already_matched_points = []
    objects = []

    for i in range(0, object_points.shape[0]):
        for j in range(0, object_points.shape[0]):
            distance_matrix[i,j] = np.sqrt(np.sum((object_points[i] - object_points[j])**2))

    for i in range(0, object_points.shape[0]):
        if i in already_matched_points:
            continue
        
        distance_deltas = np.abs(distance_matrix[i] - dist1)
        num_matches = distance_deltas < 0.025
        matches_index = np.where(distance_deltas < 0.025)[0]
        if np.sum(num_matches) >= 2:
            for possible_pair in cartesian_product(matches_index, matches_index):
                pair_distance = np.sqrt(np.sum((object_points[possible_pair[0]] - object_points[possible_pair[1]])**2))
                
                # if the pair isnt the correct distance apart
                if np.abs(pair_distance - dist2) > 0.025:
                    continue

                best_match_1_i = possible_pair[0]
                best_match_2_i = possible_pair[1]

                already_matched_points.append(i)
                already_matched_points.append(best_match_1_i)
                already_matched_points.append(best_match_2_i)

                location = (object_points[best_match_1_i]+object_points[best_match_2_i])/2
                error = np.mean([errors[i], errors[best_match_1_i], errors[best_match_2_i]])

                heading_vec = object_points[best_match_1_i] - object_points[best_match_2_i]
                heading_vec /= linalg.norm(heading_vec)
                heading = np.arctan2(heading_vec[1], heading_vec[0])

                heading = heading - np.pi if heading > np.pi/2 else heading
                heading = heading + np.pi if heading < -np.pi/2 else heading

                # determine drone index based on which side third light is on
                drone_index = 0 if (object_points[i] - location)[1] > 0 else 1

                objects.append({
                    "pos": location,
                    "heading": -heading,
                    "error": error,
                    "droneIndex": drone_index
                })

                break
    
    return objects


def numpy_fillna(data):
    data = np.array(data, dtype=object)
    # Get lengths of each row of data
    lens = np.array([len(i) for i in data])

    # Mask of valid places in each row
    mask = np.arange(lens.max()) < lens[:,None]

    # Setup output array and put elements from data into masked positions
    out = np.full((mask.shape[0], mask.shape[1], 2), [None, None])
    out[mask] = np.concatenate(data)
    return out
        

def drawlines(img1,lines):
    r,c,_ = img1.shape
    for r in lines:
        color = tuple(np.random.randint(0,255,3).tolist())
        x0,y0 = map(int, [0, -r[2]/r[1] ])
        x1,y1 = map(int, [c, -(r[2]+r[0]*c)/r[1] ])
        img1 = cv.line(img1, (x0,y0), (x1,y1), color,1)
    return img1


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


def camera_pose_to_serializable(camera_poses):
    for i in range(0, len(camera_poses)):
        camera_poses[i] = {k: v.tolist() for (k, v) in camera_poses[i].items()}

    return camera_poses

def cartesian_product(x, y):
    return np.array([[x0, y0] for x0 in x for y0 in y])

def add_white_border(image, border_size):
    height, width = image.shape[:2]
    bordered_image = cv.copyMakeBorder(image, border_size, border_size, border_size, border_size, cv.BORDER_CONSTANT, value=[255, 255, 255])
    return bordered_image