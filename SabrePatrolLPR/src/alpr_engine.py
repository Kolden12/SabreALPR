import os
import cv2
import time
import uuid
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal
from src.db_manager import DBManager
from src.config import CONFIG_DIR

# Optional: Add dummy/placeholder paths for YOLO models, to be replaced by user
YOLO_DET_MODEL_PATH = "yolo11n.pt"
YOLO_CLS_MODEL_PATH = "yolov8n-cls.pt" # Placeholder for VMMR/State classifier

# Initialize global engines safely
import easyocr
try:
    from ultralytics import YOLO
    det_model = YOLO(YOLO_DET_MODEL_PATH)
    cls_model = YOLO(YOLO_CLS_MODEL_PATH)
    reader = easyocr.Reader(['en'], gpu=True) # Will fallback to CPU if no CUDA
except Exception as e:
    print(f"Warning: Failed to load ALPR AI models locally: {e}")
    det_model = None
    cls_model = None
    reader = None

class ALPREngineThread(QThread):
    new_read_signal = pyqtSignal(dict, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run_flag = True
        self.db = DBManager()
        self.frame_queue = []
        self.recent_plates = {} # For 30s deduplication cache

        # Ensure local image save directory exists
        self.images_dir = os.path.join(CONFIG_DIR, "images")
        os.makedirs(self.images_dir, exist_ok=True)

    def enqueue_frames(self, cv_color, cv_ir):
        # Keep queue short to prevent memory leak / lag
        if len(self.frame_queue) < 5:
            self.frame_queue.append((cv_color.copy(), cv_ir.copy()))

    def clean_dedup_cache(self):
        now = time.time()
        # Remove plates stored more than 30 seconds ago
        self.recent_plates = {p: t for p, t in self.recent_plates.items() if now - t < 30}

    def _determine_color(self, cv_color, box):
        try:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            # Expand bounding box slightly for color context (vehicle body)
            h, w = cv_color.shape[:2]
            cx1, cy1 = max(0, x1 - 50), max(0, y1 - 50)
            cx2, cy2 = min(w, x2 + 50), min(h, y2 + 50)

            crop = cv_color[cy1:cy2, cx1:cx2]
            if crop.size == 0:
                return "Unknown"

            # Basic dominant color detection using mean
            mean_color = cv2.mean(crop)
            b, g, r = mean_color[0], mean_color[1], mean_color[2]

            # Simple thresholding logic for basic colors
            if r > 180 and g > 180 and b > 180: return "White"
            if r < 80 and g < 80 and b < 80: return "Black"
            if r > 150 and g < 100 and b < 100: return "Red"
            if b > 150 and r < 100 and g < 100: return "Blue"
            if r > 150 and g > 150 and b < 100: return "Yellow"
            if g > 150 and r < 100 and b < 100: return "Green"
            if abs(r - g) < 30 and abs(g - b) < 30 and r > 80: return "Silver/Grey"

            return "Other"
        except Exception:
            return "Unknown"

    def _determine_vmmr(self, cv_color, box):
        if cls_model is None:
            return "UnknownState", "UnknownMake", "UnknownModel"

        try:
            # Crop the color frame using the detected coordinates
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # Expand the crop slightly to capture the vehicle context
            h, w = cv_color.shape[:2]
            cx1, cy1 = max(0, x1 - 200), max(0, y1 - 200)
            cx2, cy2 = min(w, x2 + 200), min(h, y2 + 200)

            vehicle_crop = cv_color[cy1:cy2, cx1:cx2]
            if vehicle_crop.size == 0:
                return "UnknownState", "UnknownMake", "UnknownModel"

            # Run classifier inference
            results = cls_model(vehicle_crop, verbose=False)

            # Assuming a custom trained cls model that returns strings like "TX_Ford_Explorer"
            if results and len(results) > 0:
                top_class_idx = results[0].probs.top1
                top_class_name = results[0].names[top_class_idx]

                parts = top_class_name.split('_')
                if len(parts) >= 3:
                    return parts[0], parts[1], parts[2]
                return top_class_name, "Unknown", "Unknown"

        except Exception as e:
            print(f"VMMR Error: {e}")

        return "UnknownState", "UnknownMake", "UnknownModel"

    def run(self):
        while self._run_flag:
            if not self.frame_queue:
                time.sleep(0.05)
                continue

            cv_color, cv_ir = self.frame_queue.pop(0)

            if det_model is None or reader is None:
                continue

            # Stage 1: Detection (YOLO11n) on IR frame
            try:
                results = det_model(cv_ir, verbose=False)
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        conf = float(box.conf[0])
                        # E.g., class 0 = license_plate (assuming a custom trained yolo11n.pt, or standard if it supports it)
                        # We trigger on confidence > 0.80 per user requirement
                        if conf > 0.80:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])

                            # Stage 2: OCR on crop
                            plate_crop = cv_ir[y1:y2, x1:x2]
                            if plate_crop.size == 0:
                                continue

                            ocr_results = reader.readtext(plate_crop)
                            if ocr_results:
                                # Get the highest confidence text
                                text_data = max(ocr_results, key=lambda x: x[2])
                                plate_text = text_data[1].upper().replace(" ", "").replace("-", "")
                                ocr_conf = float(text_data[2])

                                # Process only if OCR confidence > 0.70
                                if ocr_conf > 0.70:
                                    self.clean_dedup_cache()
                                    if plate_text in self.recent_plates:
                                        continue # Skip, recently seen

                                    self.recent_plates[plate_text] = time.time()

                                    # Stage 3 & 4: Classifications
                                    state, make, model = self._determine_vmmr(cv_color, box)
                                    color = self._determine_color(cv_color, box)

                                    ts_obj = datetime.now()
                                    ts_str = ts_obj.strftime("%Y-%m-%d %H:%M:%S")
                                    prefix = ts_obj.strftime("%Y%m%d%H%M%S") + f"_{plate_text}"

                                    ir_path = os.path.join(self.images_dir, f"{prefix}_IR.jpg")
                                    color_path = os.path.join(self.images_dir, f"{prefix}_Color.jpg")

                                    # Save images locally
                                    cv2.imwrite(ir_path, plate_crop)
                                    cv2.imwrite(color_path, cv_color)

                                    # Insert to local SQLite
                                    # GPS placeholder
                                    gps_coords = "0.0000, 0.0000"

                                    self.db.insert_read(
                                        plate_text, ocr_conf * 100.0, ts_str, gps_coords,
                                        ir_path, color_path, state, make, model, color
                                    )

                                    # Mock Watchlist Check (UI and API logic handles actual routing, but we send the flag)
                                    import csv
                                    is_hit = False
                                    if os.path.exists("watchlist.csv"):
                                        with open("watchlist.csv", 'r', encoding='utf-8') as f:
                                            for row in csv.reader(f):
                                                if len(row) > 0 and row[0].strip().upper() == plate_text:
                                                    is_hit = True
                                                    break

                                    read_data = {
                                        "timestamp": ts_str,
                                        "plate": plate_text,
                                        "state": state,
                                        "color": color,
                                        "make": make,
                                        "model": model,
                                        "confidence": ocr_conf * 100.0,
                                        "ir_path": ir_path,
                                        "color_path": color_path
                                    }

                                    # Emit to UI
                                    self.new_read_signal.emit(read_data, is_hit)

            except Exception as e:
                print(f"ALPR Engine Error: {e}")

    def stop(self):
        self._run_flag = False
        self.wait()
