from flask import Flask, render_template, Response
from pseyepy import Camera
import cv2

app = Flask(__name__)

# Inicializa la cámara con la configuración deseada
camera = Camera(fps=30, resolution=Camera.RES_LARGE)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    def gen(camera):
        while True:
            frame, _ = camera.read()
            jpeg_frame = cv2.imencode('.jpg', frame)[1].tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg_frame + b'\r\n\r\n')

    return Response(gen(camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
