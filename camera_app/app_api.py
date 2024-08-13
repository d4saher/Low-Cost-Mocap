import numpy as np
import cv2 as cv
import time
import paho.mqtt.client as mqtt
import json
import os
import threading
from flask import Flask, Response

from camera import Camera

app = Flask(__name__)

CAMERA_ID = "cam_1"

is_capturing_points = False

client = mqtt.Client()

dev = True

last_frame = None
frame_lock = threading.Lock() 

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")

    client.subscribe("tb-tracker/is_capturing_points")

def on_message(client, userdata, msg):
    global is_capturing_points
    camera = Camera.instance()
    if msg.topic == "tb-tracker/is_capturing_points" and json.loads(msg.payload.decode()) != is_capturing_points:
        is_capturing_points = json.loads(msg.payload.decode())
        camera.set_is_capturing_points(is_capturing_points)

def send_points(points, timestamp):
    
    if points == [[None, None]]:
        points = []

    #print(f"Sending points: {points}")
    topic = f"tb-tracker/{CAMERA_ID}/points"
    payload = {
        "timestamp": timestamp,
        "points": points
    }

    client.publish(topic, json.dumps(payload))

def capture_frames():
    global last_frame
    camera = Camera.instance()
    while True:
        frame, image_points, timestamp = camera.get_frame()
        send_points(image_points, timestamp)
        time.sleep(0.05)
        with frame_lock:
            last_frame = frame
        # Si está en modo de desarrollo, mostrar el frame en una ventana
        if dev and frame is not None:
            cv.imshow("Camera", frame)
            if cv.waitKey(1) & 0xFF == ord('q'):
                break

@app.route('/video_feed')
def video_feed():
    camera = Camera.instance()
    print("Video feed")

    def gen(camera):
        print("Generating frames")
        global last_frame
        while True:
            frame, image_points, timestamp = camera.get_frame()
            send_points(image_points, timestamp)

            if frame is not None:
                ret, buffer = cv.imencode('.jpg', frame)
                frame = buffer.tobytes()

                # Genera un flujo HTTP con el frame codificado
                yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                
    # Devuelve el stream de video en el endpoint /video_feed
    return Response(gen(camera), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == "__main__":

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("localhost", 1883, 60)

    client.loop_start()

    # Inicia el bucle de captura de frames en un hilo separado
    # capture_thread = threading.Thread(target=capture_frames)
    # capture_thread.daemon = True
    # capture_thread.start()

    app.run(host="0.0.0.0", port=5001, debug=True)


    # while True:
    #     frame, image_points, timestamp = camera.get_frame()
    #     print(image_points)
        
    #     send_points(image_points, timestamp)

    #     if dev:
    #         cv.imshow("Camera", frame)
    #         if cv.waitKey(1) & 0xFF == ord('q'):
    #             break

