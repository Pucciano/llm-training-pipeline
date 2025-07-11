#!/bin/bash
#set -euo pipefail

echo '=================================================================='
echo 'Initial setup'
echo '------------------------------------------------------------------'

# Set ENV variables
export APT_INSTALL="apt-get install -y --no-install-recommends"
export PIP_INSTALL="python -m pip --no-cache-dir install --upgrade"
export GIT_CLONE="git clone --depth 10"
export DEBIAN_FRONTEND="noninteractive"

# Update apt
sudo apt update
sudo apt upgrade -y

echo '=================================================================='
echo 'Installing Tools'
echo '------------------------------------------------------------------'

sudo $APT_INSTALL \
apt-transport-https \
apt-utils \
build-essential \
bzip2 \
ca-certificates \
cifs-utils \
curl \
dialog \
dkms \
ffmpeg \
gcc \
git \
git-lfs \
gnupg \
iputils-ping \
joe \
jq \
libboost-all-dev \
libsm6 \
libssl-dev \
libxext6 \
make \
nano \
openssh-client \
pkg-config \
rsync \
sudo \
tar \
unrar \
unzip \
wget \
zip \
zlib1g \
make \
perl

echo '=================================================================='
echo 'Installing Linux Kernel Headers'
echo '------------------------------------------------------------------'
sudo $APT_INSTALL \
linux-headers-$(uname -r)

echo '=================================================================='
echo 'Installing Python'
echo '------------------------------------------------------------------'

# Installing python3.12 and pip
sudo $APT_INSTALL \
python3.12 \
python3.12-dev \
python3.12-venv \
python3-pip \
python3-distutils-extra

# Add symlink so python and python3 commands use same python3.12 executable
sudo ln -sfn /usr/bin/python3.12 /usr/local/bin/python3
sudo ln -sfn /usr/bin/python3.12 /usr/local/bin/python

# Grant access for pip to install in ~/.local
sudo chmod -R a+rwx ${HOME}/.local

echo '=================================================================='
echo 'Installing CUDA packages'
echo '------------------------------------------------------------------'

# Based on https://developer.nvidia.com/cuda-toolkit-archive
# Based on https://docs.nvidia.com/deeplearning/cudnn/install-guide/index.html

sudo wget -q \
https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/cuda-ubuntu2404.pin \
-O /etc/apt/preferences.d/cuda-ubuntu2404.pref

sudo wget -q \
https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb \
-O /tmp/cuda-keyring_1.1-1_all.deb
sudo dpkg -i /tmp/cuda-keyring_1.1-1_all.deb
sudo apt-get update

sudo $APT_INSTALL nvidia-driver-570 \
nvidia-fabricmanager-570 \
cuda-toolkit-12-8 \
nvtop \
nvidia-modprobe \
nvidia-settings \
libnvidia-egl-wayland1 \
cuda-toolkit-12-config-common \
cuda-toolkit-config-common \
libnvidia-container-tools \
libnvidia-container1 \
nvidia-container-toolkit \
nvidia-container-toolkit-base \
libnccl-dev \
libnccl2 \
libxnvctrl0 \
libcudnn9-cuda-12

export PATH=$PATH:/usr/local/cuda/bin
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
export CUDA_HOME=/usr/local/cuda

echo '=================================================================='
# Cleanup
echo 'Cleanup'
echo '------------------------------------------------------------------'

sudo rm -f /tmp/cuda-keyring_1.1-1_all.deb
sudo apt-get clean