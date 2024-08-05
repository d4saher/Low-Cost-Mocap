import time
import json

from drones.drone import Drone

class Esp32Drone(Drone):
    def __init__(self, index, serial, serial_lock):
        super().__init__(index)
        self.serial = serial
        self.serial_lock = serial_lock

        Drone.add_drone(self)
    
    def sarm(self, armed):
        serial_data = {"armed": armed}
        with self.serial_lock:
            self.serial.write(f"{str(self.index)}{json.dumps(serial_data)}".encode('utf-8'))
        time.sleep(0.01)
    
    def set_pid(self, pid):
        serial_data = {"pid": [float(x) for x in pid]}
        with self.serial_lock:
            self.serial.write(f"{str(self.index)}{json.dumps(serial_data)}".encode('utf-8'))
        time.sleep(0.01)
    
    def set_setpoint(self, setpoint):
        serial_data = {"setpoint": [float(x) for x in setpoint]}
        with self.serial_lock:
            self.serial.write(f"{str(self.index)}{json.dumps(serial_data)}".encode('utf-8'))
        time.sleep(0.01)
    
    def set_trim(self, trim):
        serial_data = {"trim": [int(x) for x in trim]}
        with self.serial_lock:
            self.serial.write(f"{str(self.index)}{json.dumps(serial_data)}".encode('utf-8'))
        time.sleep(0.01)

    def update_position_and_velocity(self, position, velocity, heading):
        serial_data = {
            "pos": [round(x, 4) for x in position] + [heading],
            "vel": [round(x, 4) for x in velocity]
        }
        with self.serial_lock:
            self.serial.write(f"{str(self.index)}{json.dumps(serial_data)}".encode('utf-8'))
        time.sleep(0.001)