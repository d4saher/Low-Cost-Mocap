#!/bin/bash

# Actualiza los paquetes e instala el servidor SSH
sudo apt update
sudo apt install -y openssh-server

# Habilita e inicia el servicio SSH
sudo systemctl enable ssh
sudo systemctl start ssh

# Configura el archivo sshd_config para permitir autenticación por contraseña
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
sudo sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config

# Reinicia el servicio SSH para aplicar los cambios
sudo systemctl restart ssh

# Configura el firewall para permitir conexiones SSH y al puerto 5000
sudo ufw allow ssh
sudo ufw allow 5000

sudo ufw --force enable

echo "Configuración SSH completada. Ahora puedes conectarte mediante SSH."

# Instala las dependencias necesarias
sudo apt-get install -y python3 python3-pip git libusb-1.0-0-dev python3-tk python3.8-venv



