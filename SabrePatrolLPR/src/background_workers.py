import os
import time
import shutil
import threading
import subprocess
from datetime import datetime

class BackgroundWorkers:
    def __init__(self, config, drive_path="Z:\\", results_file="results.txt"):
        self.config = config
        self.drive_path = drive_path
        self.results_file = os.path.join(drive_path, results_file)
        self._run_flag = True

        # Load verified reads to track what NOT to delete during cleanup
        self.verified_images = set()

        # Threads
        self.cleanup_thread = threading.Thread(target=self.cleanup_loop, daemon=True)
        self.offload_thread = threading.Thread(target=self.offload_loop, daemon=True)

    def start(self):
        self.cleanup_thread.start()
        self.offload_thread.start()

    def stop(self):
        self._run_flag = False

    def update_verified_images(self):
        """Parse the results.txt file to collect verified image patterns."""
        self.verified_images.clear()
        if not os.path.exists(self.results_file):
            return

        try:
            with open(self.results_file, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 6:
                        timestamp_str = parts[0].strip()
                        plate = parts[1].strip()
                        # Extract date
                        try:
                            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                            date_str = dt.strftime("%Y%m%d")
                        except Exception:
                            date_str = timestamp_str.split(' ')[0].replace('-', '')

                        # Add expected prefixes
                        self.verified_images.add(f"{date_str}_{plate}")
        except Exception as e:
            print(f"Error reading verified images: {e}")

    def cleanup_loop(self):
        """Runs periodically to delete unverified .jpg files older than 5 minutes."""
        while self._run_flag:
            self.update_verified_images()

            try:
                current_time = time.time()
                for filename in os.listdir(self.drive_path):
                    if filename.endswith(".jpg"):
                        filepath = os.path.join(self.drive_path, filename)

                        # Check age
                        file_age_seconds = current_time - os.path.getmtime(filepath)
                        if file_age_seconds > 300: # 5 minutes

                            # Check if verified
                            is_verified = False
                            for verified_pattern in self.verified_images:
                                # Add underscore to ensure exact plate match (e.g., prevent ABC matching ABC123)
                                if filename.startswith(verified_pattern + "_"):
                                    is_verified = True
                                    break

                            if not is_verified:
                                try:
                                    os.remove(filepath)
                                    print(f"Cleaned up unverified image: {filename}")
                                except Exception as e:
                                    print(f"Failed to delete {filename}: {e}")

            except Exception as e:
                print(f"Cleanup error: {e}")

            # Run cleanup every minute
            time.sleep(60)

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
        drive_letter = "T:" # Target drive letter

        try:
            # Check if mapped
            if not os.path.exists(drive_letter):
                # Execute securely without shell=True to avoid command injection with passwords
                cmd = ["net", "use", drive_letter, unc_path, f"/user:{user}", password]
                # Use DEVNULL to prevent password logging
                subprocess.run(cmd, shell=False, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"{drive_letter}\\"
        except subprocess.CalledProcessError as e:
            print("Failed to map TrueNAS SMB share.")
            return None

    def offload_loop(self):
        """Runs periodically to shift verified hits older than 60 mins to TrueNAS."""
        while self._run_flag:
            try:
                target_path = self._map_truenas()
                # Fallback for testing/non-Windows
                if not target_path and os.name != 'nt':
                    target_path = "./archive"
                    os.makedirs(target_path, exist_ok=True)

                if target_path:
                    current_time = time.time()
                    for filename in os.listdir(self.drive_path):
                        if filename.endswith(".jpg"):
                            # Only shift verified images (others are handled by cleanup)
                            is_verified = False
                            for verified_pattern in self.verified_images:
                                if filename.startswith(verified_pattern + "_"):
                                    is_verified = True
                                    break

                            if is_verified:
                                filepath = os.path.join(self.drive_path, filename)
                                file_age_seconds = current_time - os.path.getmtime(filepath)

                                if file_age_seconds > 3600: # 60 minutes
                                    dest_path = os.path.join(target_path, filename)
                                    try:
                                        shutil.move(filepath, dest_path) # Atomic shift across mapped drives
                                        print(f"Offloaded {filename} to TrueNAS.")
                                    except Exception as e:
                                        print(f"Failed to offload {filename}: {e}")
            except Exception as e:
                print(f"Offload error: {e}")

            # Run offload check every hour (3600s), polling every 10 mins for now
            time.sleep(600)
