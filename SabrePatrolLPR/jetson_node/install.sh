#!/bin/bash
echo "Installing Sabre Patrol LPR Jetson Node..."
sudo apt update
sudo apt install -y python3-pip python3-opencv
pip3 install -r requirements.txt
sudo mkdir -p /opt/SabrePatrolLPR/jetson_node
sudo cp -r * /opt/SabrePatrolLPR/jetson_node/
sudo cp sabrelpr.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sabrelpr
sudo systemctl start sabrelpr
echo "Installation Complete."
