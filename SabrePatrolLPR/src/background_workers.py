import os
import time
import shutil
import threading
import subprocess
from datetime import datetime
from src.config import CONFIG_DIR
from src.db_manager import DBManager

class BackgroundWorkers:
    def __init__(self, config, drive_path="Z:\\"):
        self.config = config
        # Target drive path logic
        self.truenas_drive_letter = drive_path if os.name == 'nt' else "./archive"
        self._run_flag = True
        self.db = DBManager()

        # Local source directory where ALPR Engine saves images
        self.local_images_dir = os.path.join(CONFIG_DIR, "images")
        os.makedirs(self.local_images_dir, exist_ok=True)

        # Thread
        self.offload_thread = threading.Thread(target=self.offload_loop, daemon=True)

    def start(self):
        self.offload_thread.start()

    def stop(self):
        self._run_flag = False

    def _map_truenas(self):
        """Attempts to map the TrueNAS SMB share using net use on Windows."""
        if os.name != 'nt':
            print("SMB mapping skipped (not Windows).")
            return None

        ip = self.config.get("truenas_ip", "")
        user = self.config.get("truenas_user", "")
        password = self.config.get("truenas_password", "")

        if not ip:
            return None

        unc_path = f"\\\\{ip}\\LPR_Archive"
        drive_letter = "Z:" # Target drive letter

        try:
            # Check if mapped
            if not os.path.exists(drive_letter):
                # Execute securely without shell=True, and pipe the password via stdin to hide it from process lists
                cmd = ["net", "use", drive_letter, unc_path, f"/user:{user}", "*"]
                # Use DEVNULL for outputs to prevent logging, pass password via input
                subprocess.run(cmd, input=f"{password}\n", text=True, shell=False, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"{drive_letter}\\"
        except subprocess.CalledProcessError as e:
            print(f"Failed to map TrueNAS SMB share: {e}")
            return None

    def offload_loop(self):
        """Runs periodically to shift ALL local ALPR images older than 60 mins to TrueNAS."""
        while self._run_flag:
            try:
                target_path = self._map_truenas()
                # Fallback for testing/non-Windows
                if not target_path and os.name != 'nt':
                    target_path = self.truenas_drive_letter
                    os.makedirs(target_path, exist_ok=True)

                # If target_path is None, the VPN or TrueNAS is unreachable. Skip offload.
                if target_path:
                    current_time = time.time()
                    moved_files = {}

                    for filename in os.listdir(self.local_images_dir):
                        if filename.endswith(".jpg"):
                            filepath = os.path.join(self.local_images_dir, filename)
                            file_age_seconds = current_time - os.path.getmtime(filepath)

                            # Shift files older than 60 minutes
                            if file_age_seconds > 3600:
                                dest_path = os.path.join(target_path, filename)
                                try:
                                    # Atomic shift across drives
                                    shutil.move(filepath, dest_path)
                                    moved_files[filepath] = dest_path
                                    print(f"Offloaded {filename} to TrueNAS.")
                                except Exception as e:
                                    print(f"Failed to offload {filename}: {e}")

                    # Update SQLite database to point to the new paths on the Z: drive
                    for old_path, new_path in moved_files.items():
                        try:
                            self.db.update_image_paths(old_path, new_path)
                        except Exception as db_err:
                            print(f"Failed to update SQLite path for {old_path}: {db_err}")

            except Exception as e:
                print(f"Offload error: {e}")

            # Run offload check every 10 mins
            time.sleep(600)
