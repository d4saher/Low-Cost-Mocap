import sys
import cv2

from pseyepy import Camera


# Intenta inicializar la cámara con valores específicos
try:
    camera = Camera(fps=90, resolution=Camera.RES_SMALL, gain=10, exposure=100)
    frame1, timestamp1 = camera.read(1)

    #Guarda la imagen en un archivo
    cv2.imwrite("test.jpg", frame1)

except Exception as e:
    print("Error al inicializar la cámara:", str(e))
    sys.exit(1)