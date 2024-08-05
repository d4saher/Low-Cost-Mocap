

class Drone:
    _drones = []

    def __init__(self, index, ip=None, port=None):
        self.index = index
        self.ip = ip
        self.port = port
        self._check_existing_drones()

    @classmethod
    def add_drone(cls, drone):
        cls._drones.append(drone)

    @classmethod
    def get_drone(cls, index):
        return cls._drones[index]

    @classmethod
    def existing_drones(cls):
        return cls._drones

    def _check_existing_drones(self):
        if self.ip is None:
            return
        for drone in Drone.existing_drones():
            if drone.ip == self.ip:
                raise Exception("A drone with IP {} already exists".format(self.ip))
            
    def set_is_armed(self, armed):
        raise NotImplementedError("This method should be overridden by subclasses")
    
    def set_pid(self, pid):
        raise NotImplementedError("This method should be overridden by subclasses")

    def set_setpoint(self, setpoint):
        raise NotImplementedError("This method should be overridden by subclasses")
    
    def set_trim(self, trim):
        raise NotImplementedError("This method should be overridden by subclasses")
    
    def update_position_and_velocity(self, position, velocity, heading):
        raise NotImplementedError("This method should be overridden by subclasses")
