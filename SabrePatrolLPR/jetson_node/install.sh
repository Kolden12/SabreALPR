#!/bin/bash
echo "Installing Sabre Patrol LPR Jetson Node (TensorRT Native)..."

# Ensure JetPack dependencies
sudo apt update
sudo apt install -y python3-pip python3-opencv

# jetson-inference and jetson-utils are expected to be installed via:
# https://github.com/dusty-nv/jetson-inference/blob/master/docs/building-repo-2.md
# or via the L4T containers.

pip3 install -r requirements.txt

# Create models directory
mkdir -p models

sudo mkdir -p /opt/SabrePatrolLPR/jetson_node
sudo cp -r * /opt/SabrePatrolLPR/jetson_node/
sudo cp sabrelpr.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sabrelpr
sudo systemctl start sabrelpr

echo "Installation Complete."
echo "Note: Ensure .engine files are placed in /opt/SabrePatrolLPR/jetson_node/models/"
