import socket
import threading
import time

from simple_pid import PID
from djitellopy import Tello

from drones.drone import Drone
    
class TelloDrone(Drone):
    def __init__(self, index, ip='192.168.10.1', port=8889):
        super().__init__(index, ip, port)
        self.tello = Tello()
        self.armed = False
        self.pid = None
        self.setpoint = (0, 0, 0, 0)  # Setpoint for (x, y, z, yaw)

        # Controladores PID para posición
        self.pid_x_pos = PID(1, 0.1, 0.05, setpoint=self.setpoint[0])
        self.pid_y_pos = PID(1, 0.1, 0.05, setpoint=self.setpoint[1])
        self.pid_z_pos = PID(1.5, 0.1, 0.05, setpoint=self.setpoint[2])
        self.pid_yaw_pos = PID(0.3, 0.1, 0.05, setpoint=self.setpoint[3])
        
        # Controladores PID para velocidad
        self.pid_x_vel = PID(0.2, 0.03, 0.05, setpoint=0)
        self.pid_y_vel = PID(0.2, 0.03, 0.05, setpoint=0)
        self.pid_z_vel = PID(0.3, 0.1, 0.05, setpoint=0)
        
        self.current_pos = [0, 0, 0, 0]  # Posiciones actuales (x, y, z, yaw)
        self.current_vel = [0, 0, 0]     # Velocidades actuales (x, y, z)

        self.control_thread = None
        self.stop_control_thread = threading.Event()

        Drone.add_drone(self)
    
    def set_pid(self, pid):
        print(pid)
        # Implement PID setting for Tello if applicable
        pass
    
    def set_setpoint(self, setpoint):
        self.setpoint = setpoint
    
    def set_trim(self, trim):
        # Implement trim setting for Tello if applicable
        pass

    def update_position_and_velocity(self, position, velocity, heading):
        print("New Position: " + str(position))
        print("New Velocity: " + str(velocity))
        print("New Heading: " + str(heading))
        # Add heading to position
        self.current_pos = position + [heading]
        self.current_vel = velocity
        self.current_heading = heading

    def reset_pid(self):
        # Resetear los controladores de posición
        self.pid_x_pos.reset()
        self.pid_y_pos.reset()
        self.pid_z_pos.reset()
        self.pid_yaw_pos.reset()
        # Resetear los controladores de velocidad
        self.pid_x_vel.reset()
        self.pid_y_vel.reset()
        self.pid_z_vel.reset()

    def update_pid(self):
        # Actualizar los setpoints de velocidad con los controladores de posición
        x_vel_setpoint = self.pid_x_pos(self.current_pos[0])
        y_vel_setpoint = self.pid_y_pos(self.current_pos[1])
        z_vel_setpoint = self.pid_z_pos(self.current_pos[2])
        #yaw_setpoint = self.pid_yaw_pos(self.current_pos[3])
        yaw_setpoint = 0
        
        # Actualizar los setpoints de los controladores de velocidad
        self.pid_x_vel.setpoint = x_vel_setpoint
        self.pid_y_vel.setpoint = y_vel_setpoint
        self.pid_z_vel.setpoint = z_vel_setpoint

        # Actualizar las salidas de los controladores de velocidad
        x_output = self.pid_x_vel(self.current_vel[0])
        y_output = self.pid_y_vel(self.current_vel[1])
        z_output = self.pid_z_vel(self.current_vel[2])
        
        # Enviar los comandos al dron
        # print("x_output: ", x_output, "y_output: ", y_output, "z_output: ", z_output, "yaw_setpoint: ", yaw_setpoint)
        if(self.armed):
            self.tello.send_rc_control(int(x_output), int(y_output), int(z_output), int(yaw_setpoint))

        #print("x_output: ", x_output_scaled, "y_output: ", y_output_scaled, "z_output: ", z_output_scaled, "yaw_setpoint: ", yaw_setpoint_scaled)
        # if(self.armed):
        #     #Send RC control to Tello (left/right, forward/backward, up/down, yaw)
        #     self.tello.send_rc_control(-(int(x_output_scaled)), -(int(y_output_scaled)), int(z_output_scaled), int(yaw_setpoint_scaled))
            

    def control_loop(self):
        while not self.stop_control_thread.is_set():
            self.update_pid()
            time.sleep(0.1)  # Ajusta según sea necesario

    def arm(self, armed):
        print("Connecting to Tello")
        print("Armed: ", armed)
        if armed != self.armed:
            self.armed = armed
            try:
                self.tello.connect()
            except socket.error as e:
                print("Error connecting to Tello: ", e)
                return
            if armed:
                try:
                    self.reset_pid()
                    self.tello.takeoff()
                    self.stop_control_thread.clear()
                    self.control_thread = threading.Thread(target=self.control_loop)
                    self.control_thread.start()
                except Exception as e: 
                    print("Error taking off: ", e)
            else:
                try:
                    self.tello.land()
                    self.stop_control_thread.set()
                    if self.control_thread is not None:
                        self.control_thread.join()
                except Exception as e:
                    print("Error landing: ", e)
        else:
            print("Already ", armed)

    def is_armed(self):
        return self.armed
