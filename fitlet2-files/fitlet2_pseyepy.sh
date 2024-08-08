#!/bin/bash

# Crea el directorio tb-tracker si no existe
mkdir -p ~/tb-tracker/

# Crea y activa el entorno virtual
python3 -m venv ~/tb-tracker/camera-venv

if [ -f ~/tb-tracker/camera-venv/bin/activate ]; then
    source ~/tb-tracker/camera-venv/bin/activate

    # Instala las dependencias dentro del entorno virtual
    pip install numpy Pillow h5py cython flask opencv-python

    # Clona el repositorio y realiza la instalación
    git clone https://github.com/d4saher/pseyepy.git ~/tb-tracker/pseyepy
    cd ~/tb-tracker/pseyepy
    python3 setup.py install

    echo "Pseyepy y sus dependencias instalados."
else
    echo "Error: No se pudo crear el entorno virtual."
fi

# Crear un archivo de reglas udev
sudo bash -c 'cat <<EOF > /etc/udev/rules.d/50-usb-permissions.rules
SUBSYSTEM=="usb", MODE="0664", GROUP="plugdev"
EOF'

# Recargar las reglas y retrigger los eventos
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Reglas udev actualizadas y eventos retriggered."

sudo usermod -aG plugdev $USER


