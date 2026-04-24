# Sabre Patrol LPR Windows Suite (v1.0)

Sabre Patrol LPR is a distributed Automatic License Plate Recognition (ALPR) system designed specifically for law enforcement Mobile Data Terminals (MDTs), primarily targeting the 2020 Ford Interceptor environment.

## Architecture Overview

To maximize performance in a vehicular environment, the suite utilizes a split-compute architecture:

1. **Nvidia Jetson Orin Nano (Backend Node):** Acts as the compute powerhouse. It runs a headless Python/FastAPI service that connects to the cameras, performs hardware-accelerated (TensorRT/CUDA) YOLO object detection and PaddleOCR inference, checks against local watchlists, and manages background data offloading (TrueNAS/SMB) and Orna CAD API Webhooks.
2. **Windows 10/11 MDT (Frontend Client):** Acts as the tactical interface. It runs a lightweight PyQt5 application that pulls live video feeds directly from the cameras to save bandwidth, and listens via WebSockets to instantly display verified hits, alerts, and high-resolution captures from the Jetson.

## General Download & Setup Instructions

### 1. Download
Clone this repository to your local machine:
```bash
git clone https://github.com/your-org/SabrePatrolLPR.git
```
Alternatively, download the latest Release `.zip` from the Releases page.

### 2. Jetson Node Installation (Compute)
1. Transfer the `jetson_node/` directory to your Nvidia Jetson Orin Nano.
2. Run the provided automated install script to configure dependencies and set up the background service.
3. See [jetson_node/README.md](./jetson_node/README.md) for detailed instructions.

### 3. MDT Client Installation (UI)
1. On your Windows MDT, locate the compiled `SabrePatrolLPR_Installer.exe` (generated via Inno Setup).
2. Run the installer to deploy the application and create a desktop shortcut.
3. Open the application, navigate to **File > Settings**, and configure your Jetson IP, Camera feeds, TrueNAS credentials, and upload your Hotlist.
4. See [mdt_client/README.md](./mdt_client/README.md) for detailed end-user instructions.

## System Requirements
*   **Edge Node:** Nvidia Jetson Orin Nano (JetPack 5.x+, Ubuntu 20.04+)
*   **MDT Client:** Windows 10 or 11
*   **Network:** UniFi Site Magic VPN (or similar) bridging VLAN 5 for TrueNAS SMB access.
*   **Cameras:** VSR-20 (RTSP) or VSR-40 (HTTP) units.
