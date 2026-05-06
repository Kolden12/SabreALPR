import os
import time
import logging
import requests

# Jetson imports
try:
    import jetson.inference
    import jetson.utils
except ImportError:
    from mock_jetson import inference_mod as inference
    from mock_jetson import utils_mod as utils
    import sys
    from types import ModuleType
    if 'jetson' not in sys.modules:
        jetson = ModuleType("jetson")
        sys.modules["jetson"] = jetson
    jetson.inference = inference
    jetson.utils = utils

from db_manager import DBManager

# Paths
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
LPR_MODEL_PATH = os.path.join(MODEL_DIR, "lprnet.engine")
NVME_BASE_DIR = os.getenv("NVME_BASE_DIR", "/mnt/nvme/sabre_data/crops")
PROCESSED_DIR = os.path.join(NVME_BASE_DIR, "processed")

class WatcherService:
    def __init__(self):
        self.db = DBManager()
        self.net_lpr = None
        self.running = True

    def _init_lpr(self):
        if self.net_lpr is None:
            try:
                logging.info(f"Loading LPRNet model: {LPR_MODEL_PATH}")
                self.net_lpr = jetson.inference.lprNet(argv=[f"--model={LPR_MODEL_PATH}"])
            except Exception as e:
                logging.error(f"Failed to load LPRNet: {e}")

    def run(self):
        self._init_lpr()
        logging.info("Watcher Service started. Monitoring database for unprocessed crops...")

        while self.running:
            events = self.db.get_unprocessed_events()
            if not events:
                time.sleep(1)
                continue

            for event_id, camera_id, high_res_path, thumbnail_path in events:
                try:
                    self.process_event(event_id, high_res_path)
                except Exception as e:
                    logging.error(f"Error processing event {event_id}: {e}")

            time.sleep(0.5)

    def process_event(self, event_id, img_path):
        if not os.path.exists(img_path):
            logging.warning(f"Image not found: {img_path}")
            # Mark as processed with error? For now just skip
            self.db.update_processed_event(event_id, "IMAGE_NOT_FOUND", 0, False)
            return

        # Load image
        img = jetson.utils.loadImage(img_path)

        # Run OCR
        plate_text, confidence = self.net_lpr.Recognize(img)
        plate_text = plate_text.upper().replace(" ", "").replace("-", "")

        # Check Hot List
        is_hit = self.db.check_hot_list(plate_text)

        # Move image to processed folder
        filename = os.path.basename(img_path)
        new_path = os.path.join(PROCESSED_DIR, filename)
        os.rename(img_path, new_path)

        # Update DB
        self.db.update_processed_event(event_id, plate_text, confidence * 100.0, is_hit, high_res_path=new_path)

        logging.info(f"Processed event {event_id}: {plate_text} (Hit: {is_hit})")

        if is_hit:
            self.trigger_alert(event_id, plate_text, is_hit, new_path)

    def trigger_alert(self, event_id, plate_text, is_hit, img_path):
        # Map path to URL
        image_url = img_path.replace("/mnt/nvme/sabre_data/crops", "/crops")
        # We need a way to communicate back to the FastAPI process to broadcast via WebSocket.
        # Since they are separate services, we could use a Redis pub/sub or just have the
        # MDT poll, but the requirement is WebSocket (/alerts).
        # For this implementation, let's assume we can import the broadcast function
        # or use a simple HTTP call to ourselves, OR runs in the same process.

        # If running in same process, we can use a global queue.
        # Given the instruction to have a "Watcher service", let's make it a background thread in main.py
        # or a separate process that hits a local internal endpoint.

        # Let's go with the internal endpoint for decoupling.
        try:
            payload = {
                "type": "alert",
                "data": {
                    "event_id": event_id,
                    "plate": plate_text,
                    "is_hit": is_hit,
                    "image_url": image_url
                }
            }
            requests.post("http://localhost:8000/internal/broadcast", json=payload)
        except Exception as e:
            logging.error(f"Failed to trigger alert broadcast: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    watcher = WatcherService()
    watcher.run()
