# Sabre Patrol LPR - Windows MDT Client

This directory contains the tactical user interface for the Sabre Patrol LPR system. It is a lightweight Windows application designed for law enforcement MDTs. It connects to the Jetson Edge Node to receive instant alerts and displays live video feeds directly from the cameras.

## Installation

There are two ways to get the MDT Client running on your machine:

### Method 1: Pre-compiled Installer (Recommended)
This is the easiest method. You do not need to deal with source code or `.iss` files.

1. Go to the GitHub repository page.
2. Click on the **Actions** tab at the top.
3. Click on the most recent successful workflow run (look for the green checkmark).
4. Scroll to the bottom of the summary page to the **Artifacts** section.
5. Download the `SabreALPR-Tactical-Installer` archive.
6. Extract the zip file and run `SabrePatrolLPR_Setup.exe`.
7. Follow the installation wizard. It will create a shortcut on your Desktop.

### Method 2: Compile from Source (Advanced)
If you downloaded the source code ZIP and only see `installer.iss`, you must compile the application yourself.

1. Install [Python 3.10+](https://www.python.org/downloads/).
2. Open a command prompt or PowerShell in the `mdt_client` directory.
3. Install dependencies: `pip install -r requirements.txt` and `pip install pyinstaller`
4. Build the executable: `pyinstaller SabrePatrolLPR.spec`
5. Download and install [Inno Setup 6](https://jrsoftware.org/isdl.php).
6. Double-click the `installer.iss` file to open it in Inno Setup.
7. Click the **Compile** button (or press Ctrl+F9).
8. The final `SabrePatrolLPR_Setup.exe` will be generated inside the `Output/` folder.

## Initial Setup & Configuration

Before the system will detect plates, you must configure the connection to the Jetson Node and your cameras.

1. Launch the application.
2. In the top menu bar, click **File > Settings**.
3. **General Settings:**
    *   **Unit ID:** Enter your vehicle identifier (e.g., `Patrol-42`).
    *   **Jetson Node IP:** Enter the local network IP address of your Jetson Orin Nano (e.g., `192.168.1.50`). *This must be correct for the system to receive plate reads.*
4. **Camera Management:**
    *   Select your camera model (`VSR-20` or `VSR-40`) from the dropdown.
    *   Enter the IP address of the camera.
    *   Click **Add Camera**. You can add up to 4 cameras.
5. **TrueNAS SMB Settings:**
    *   Enter the IP address of your TrueNAS server (e.g., `192.168.5.100` on VLAN 5).
    *   Enter your SMB Username and Password. The Jetson node uses these to securely offload archived reads every hour.
6. **Watchlist (Hotlist):**
    *   Click **Upload Watchlist to Jetson Node**.
    *   Select your local `watchlist.csv` file containing the license plates you want to alert on. This file will be pushed to the Jetson for processing.
7. Click **Save Settings**. The application will automatically push these configurations to the Jetson node.

## UI Overview

*   **Top Left (Live Feed):** Displays the direct color video feed from Camera 1.
*   **Top Right (Verified Capture):** Displays the high-resolution cropped image of the last verified license plate read.
*   **Middle Banner:** Flashes large tactical data (PLATE, STATE, MAKE, MODEL, COLOR) when a read occurs. Turns red and sounds a siren for a Hotlist hit.
*   **Bottom Table:** A scrolling history of the last 10 verified reads.

## Troubleshooting

*   **No Live Video:** Ensure the MDT is on the same network as the cameras and that the Camera IP is entered correctly in Settings.
*   **No Plate Reads Appearing:** Ensure the **Jetson Node IP** is correct in settings, and verify the Jetson is powered on and the `sabrelpr` service is running.
*   **Failed to Upload Watchlist:** Ensure you have saved the Jetson IP in the settings *before* attempting to click the upload button.
