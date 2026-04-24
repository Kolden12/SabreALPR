# Sabre Patrol LPR - Jetson Node

This directory contains the ML compute backend designed to run on an Nvidia Jetson Orin Nano. It handles hardware-accelerated ALPR inference (YOLO/PaddleOCR), watchlist checking, and TrueNAS SMB data offloading.

## Automated Installation (Recommended)

The easiest way to get the Jetson node running is to use the provided bash script.

1. Open a terminal on your Jetson Orin Nano.
2. Navigate to this directory: `cd SabrePatrolLPR/jetson_node/`
3. Make the script executable: `chmod +x install.sh`
4. Run the script: `./install.sh`

### What does the script do?
*   Updates the `apt` package manager.
*   Installs required system dependencies (`python3-pip`, `python3-opencv`).
*   Installs all required Python modules from `requirements.txt` (`fastapi`, `ultralytics`, `paddleocr`, etc.).
*   Copies the application files to `/opt/SabrePatrolLPR/jetson_node/`.
*   Installs and enables the `sabrelpr.service` systemd daemon so the ALPR engine starts automatically on boot.

## Manual Installation

If you prefer to set up the environment manually or need to troubleshoot, follow these steps:

1. **System Prep:** Ensure you are running Nvidia JetPack (Ubuntu).
2. **Install Dependencies:**
   ```bash
   sudo apt update
   sudo apt install -y python3-pip python3-opencv
   pip3 install -r requirements.txt
   ```
3. **Machine Learning Models:** The application relies on `yolo11n.pt` and `yolov8n-cls.pt`. The `ultralytics` library will attempt to auto-download these on the first run. On the Jetson, these models will automatically utilize TensorRT/CUDA for maximum performance.
4. **Run the Server:**
   ```bash
   python3 main.py
   ```
   *The server runs on port 8000 by default.*

## Managing the Service

If installed via the automated script, the application runs as a background service.

*   **Check Status:** `sudo systemctl status sabrelpr`
*   **Restart Service:** `sudo systemctl restart sabrelpr`
*   **Stop Service:** `sudo systemctl stop sabrelpr`
*   **View Live Logs:** `sudo journalctl -u sabrelpr -f`
