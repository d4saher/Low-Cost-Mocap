
## 1. Build Armbian for Rock 4 C+ and Install to MicroSD

By default Debian and Ubuntu builds for Rock 4 C+ don't have pseye3 cam modules on their Kernel so I had to build an Armian.
This was done on a virtual machine with Ubuntu.

https://www.okdo.com/de/getting-started/get-started-with-the-rock-4c-linux-mainline/

Once the image is built, it is written with:

```bash
sudo dd if=Armbian-unofficial_24.5.0-trunk_Rockpi-4cplus_bookworm_edge_6.8.11_xfce_desktop.img of=/dev/mmcblk0 bs=4M status=progress
```

It takes approximately 10 minutes and 30 seconds.

## 2. Install pseyepy

Dependencies:

- python 3x
- numpy, cython

```bash
sudo apt install python3-numpy
pip install --break-system-packages cython3
```

- libusb

```bash
sudo apt install libusb-1.0-0-dev
```

- ffmpeg (Optional)

```bash
sudo apt install ffmpeg
```

Clone repository and install:

```bash
git clone https://github.com/bensondaled/pseyepy.git
cd pseyepy
sudo python3 setup.py install
```

## 3. Install OpenCV with SFM

SFM Dependencies:

https://docs.opencv.org/4.x/db/db8/tutorial_sfm_installation.html

- [Eigen](http://eigen.tuxfamily.org/) 3.2.2 or later. **Required**
- [GLog](https://github.com/google/glog) 0.3.1 or later. **Required**
- [GFlags](https://github.com/gflags). **Required**

```bash
sudo apt-get install libeigen3-dev libgflags-dev libgoogle-glog-dev
```

- [Ceres Solver](http://ceres-solver.org/). Needed by the reconstruction API in order to solve part of the Bundle Adjustment plus the points Intersect. If Ceres Solver is not installed on your system, the reconstruction functionality will be disabled. **Recommended**

Ceres Solver Dependencies:

```bash
# CMake
sudo apt-get install cmake
# google-glog + gflags
sudo apt-get install libgoogle-glog-dev
# BLAS & LAPACK
sudo apt-get install libatlas-base-dev
# Eigen3
sudo apt-get install libeigen3-dev
# SuiteSparse and CXSparse (optional)
# - If you want to build Ceres as a *static* library (the default)
# you can use the SuiteSparse package in the main Ubuntu package
# repository:
sudo apt-get install libsuitesparse-dev

# I installed it as "static"
# However, if you want to build Ceres as a *shared* library, you must
# add the following PPA:
sudo add-apt-repository ppa:bzindovic/suitesparse-bugfix-1319687
sudo apt-get update
sudo apt-get install libsuitesparse-dev
```

We are now ready to build, test, and install Ceres:

```bash
git clone https://ceres-solver.googlesource.com/ceres-solver
cd ceres-solver
mkdir build && cd build
cmake ..
make -j4 # Start: 13:30h, End: 14:39h
make test
sudo make install
```

Install OpenCV:

```bash
git clone https://github.com/opencv/opencv.git
git clone https://github.com/opencv/opencv_contrib.git
cd opencv
git checkout 4.x  # Make sure to use the correct version
cd ../opencv_contrib
git checkout 4.x  # Make sure to use the correct version

# As on https://github.com/opencv/opencv_contrib/blob/master/README.md :
$ cd <opencv_build_directory>
$ cmake -DOPENCV_EXTRA_MODULES_PATH=<opencv_contrib>/modules <opencv_source_directory>
$ make -j5 # Start: 15:10h, End: 19:00h
make install
```

## 4. Low-Cost-Mocap

Install node, npm, and yarn globally:

```bash
npm install --global yarn
```

Clone repository:

```bash
git clone https://github.com/jyjblrd/Low-Cost-Mocap.git
cd /Low-Cost-Mocap
```

Install API dependencies:

```bash
sudo apt install python3-scipy
sudo apt install python3-tk
sudo apt install python3-pil python3-pil.imagetk
sudo apt install python3-h5py
sudo apt install python3-flask
sudo apt install python3-flask-socketio 
sudo apt install python3-serial
# Ruckig
pip install --break-system-packages ruckig

sudo apt-get install python3-flask-cors

pip install --break-system-packages simple-websocket
```

## 5. Permissions

```bash
sudo usermod -a -G video your_user
```

### **Create a udev rule**

A more permanent and secure solution is to create a **`udev`** rule that automatically sets the appropriate permissions when the device is connected. Here’s how to do it:

1. **Create a udev rule file**:
    
    ```bash
    sudo nano /etc/udev/rules.d/50-usb-permissions.rules
    ```
    
2. **Add the following rule** (adjust the group if necessary, here **`plugdev`** is used as an example, make sure your user belongs to this group):
    
    ```makefile
    SUBSYSTEM=="usb", MODE="0664", GROUP="plugdev"
    ```
    
3. **Reload the rules and retrigger the events**:
    
    ```bash
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    ```
    
    ## 6. Execute
    
    Frontend:
    
    ```bash
    cd Low-Cost-Mocap/computer_code
    yarn run dev --host
    ```
    
    Backend:
    
    ```bash
    cd Low-Cost-Mocap/computer_code/api
    python3 index.py
    ```
