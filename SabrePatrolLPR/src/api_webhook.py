import os
import base64
import requests
import threading
import json
from datetime import datetime

class WebhookIntegration:
    def __init__(self, webhook_url, unit_id, drive_path="Z:\\"):
        self.webhook_url = webhook_url
        self.unit_id = unit_id
        # Fallback for testing environment
        self.drive_path = drive_path if os.name == 'nt' else "./"

    def encode_image(self, image_path):
        """Returns base64 encoded string of image if it exists."""
        if not os.path.exists(image_path):
            return ""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Failed to encode image {image_path}: {e}")
            return ""

    def send_payload(self, read_data, is_hit):
        """Executes the HTTP POST request in a separate thread."""
        def task():
            try:
                # Extract date from timestamp to match image naming convention (YYYYMMDD)
                timestamp_str = read_data.get('timestamp', '')
                date_str = ""
                if timestamp_str:
                    try:
                        # Assumes format "2026-04-09 13:45:01"
                        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        date_str = dt.strftime("%Y%m%d")
                    except Exception:
                        date_str = timestamp_str.split(' ')[0].replace('-', '')

                plate = read_data.get('plate', '')
                color_img_path = os.path.join(self.drive_path, f"{date_str}_{plate}_Color.jpg")
                ir_img_path = os.path.join(self.drive_path, f"{date_str}_{plate}_IR.jpg")

                color_b64 = self.encode_image(color_img_path)
                ir_b64 = self.encode_image(ir_img_path)

                payload = {
                    "unit_id": self.unit_id,
                    "timestamp": timestamp_str,
                    "plate": plate,
                    "state": read_data.get('state', ''),
                    "confidence": read_data.get('confidence', 100.0),
                    "vehicle_data": {
                        "color": read_data.get('color', ''),
                        "make": read_data.get('make', ''),
                        "model": read_data.get('model', '')
                    },
                    "is_watchlist_hit": is_hit,
                    "images": {
                        "color_base64": color_b64,
                        "ir_base64": ir_b64
                    }
                }

                headers = {'Content-Type': 'application/json'}
                response = requests.post(self.webhook_url, data=json.dumps(payload), headers=headers, timeout=10)

                if response.status_code not in (200, 201, 202):
                    print(f"Webhook error: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Error sending webhook payload: {e}")

        # Dispatch async to avoid blocking main thread
        thread = threading.Thread(target=task, daemon=True)
        thread.start()
