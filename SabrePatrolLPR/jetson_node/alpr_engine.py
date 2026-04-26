import os
import cv2
import time
import uuid
import logging
from datetime import datetime
import threading
import numpy as np

# Check if we are in a Jetson environment or mocking
try:
    import jetson.inference
    import jetson.utils
except ImportError:
    try:
        from mock_jetson import inference_mod as inference
        from mock_jetson import utils_mod as utils
        import sys
        from types import ModuleType
        if 'jetson' not in sys.modules:
            jetson = ModuleType("jetson")
            sys.modules["jetson"] = jetson
        else:
            jetson = sys.modules["jetson"]
        jetson.inference = inference
        jetson.utils = utils
        sys.modules["jetson.inference"] = inference
        sys.modules["jetson.utils"] = utils
    except ImportError:
        logging.warning("Jetson libraries not found and mock_jetson failed to load.")

from db_manager import DBManager
from config import CONFIG_DIR

# Paths to the TensorRT .engine models
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
DET_MODEL_PATH = os.path.join(MODEL_DIR, "yolov8-tiny.engine")
LPR_MODEL_PATH = os.path.join(MODEL_DIR, "lprnet.engine")
VMMR_MODEL_PATH = os.path.join(MODEL_DIR, "vmmr.engine")
COLOR_MODEL_PATH = os.path.join(MODEL_DIR, "color.engine")

class ALPREngineThread(threading.Thread):
    new_read_callbacks = []

    def __init__(self):
        super().__init__()
        self._run_flag = True
        try:
            self.db = DBManager()
        except Exception as e:
            logging.error(f"Failed to initialize DBManager: {e}")
            self.db = None
        self.frame_queue = []
        self.recent_plates = {} # For 30s deduplication cache

        self.net_det = None
        self.net_lpr = None
        self.net_vmmr = None
        self.net_color = None

        # Ensure local image save directory exists
        self.images_dir = os.path.join(CONFIG_DIR, "images")
        os.makedirs(self.images_dir, exist_ok=True)

    def _initialize_models(self):
        """Loads models lazily inside the thread."""
        try:
            logging.info("Initializing Jetson-Inference TensorRT models...")

            # Initialize detectNet (YOLOv8-tiny)
            self.net_det = jetson.inference.detectNet(argv=[
                f"--model={DET_MODEL_PATH}",
                "--threshold=0.40"
            ])

            # Initialize lprNet
            self.net_lpr = jetson.inference.lprNet(argv=[
                f"--model={LPR_MODEL_PATH}"
            ])

            # Initialize imageNet for VMMR and Color
            self.net_vmmr = jetson.inference.imageNet(argv=[
                f"--model={VMMR_MODEL_PATH}"
            ])

            self.net_color = jetson.inference.imageNet(argv=[
                f"--model={COLOR_MODEL_PATH}"
            ])

            logging.info("Jetson-Inference models initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to load ALPR AI models locally: {e}")

    def enqueue_frames(self, cuda_color, cuda_ir):
        # Keep queue short to prevent memory leak / lag
        if len(self.frame_queue) < 5:
            self.frame_queue.append((cuda_color, cuda_ir))

    def clean_dedup_cache(self):
        now = time.time()
        # Remove plates stored more than 30 seconds ago
        self.recent_plates = {p: t for p, t in self.recent_plates.items() if now - t < 30}

    def _determine_color(self, cuda_color, det):
        if self.net_color is None:
            return "Unknown"
        try:
            # Crop the vehicle for color classification
            # We expand the plate box significantly to get the vehicle body
            width = det.Right - det.Left
            height = det.Bottom - det.Top

            # Vehicles are usually wider than the plate, and above/around it
            # Expand by 3x width and 2x height
            left = max(0, det.Left - width)
            top = max(0, det.Top - height)
            right = min(cuda_color.width, det.Right + width)
            bottom = min(cuda_color.height, det.Bottom + height)

            roi = (left, top, right, bottom)
            cuda_vehicle = jetson.utils.cudaCrop(cuda_color, roi)

            class_idx, conf = self.net_color.Classify(cuda_vehicle)
            return self.net_color.GetClassDesc(class_idx)
        except Exception as e:
            logging.error(f"Color Inference Error: {e}")
            return "Unknown"

    def _determine_vmmr(self, cuda_color, det):
        if self.net_vmmr is None:
            return "UnknownState", "UnknownMake", "UnknownModel"

        try:
            # Crop the vehicle for VMMR
            width = det.Right - det.Left
            height = det.Bottom - det.Top
            left = max(0, det.Left - width)
            top = max(0, det.Top - height)
            right = min(cuda_color.width, det.Right + width)
            bottom = min(cuda_color.height, det.Bottom + height)

            roi = (left, top, right, bottom)
            cuda_vehicle = jetson.utils.cudaCrop(cuda_color, roi)

            class_idx, conf = self.net_vmmr.Classify(cuda_vehicle)
            class_desc = self.net_vmmr.GetClassDesc(class_idx)

            parts = class_desc.split('_')
            if len(parts) >= 3:
                return parts[0], parts[1], parts[2]
            return class_desc, "Unknown", "Unknown"

        except Exception as e:
            logging.error(f"VMMR Inference Error: {e}")

        return "UnknownState", "UnknownMake", "UnknownModel"

    def run(self):
        # Initialize models when the thread actually starts execution
        self._initialize_models()

        while self._run_flag:
            if not self.frame_queue:
                time.sleep(0.01)
                continue

            cuda_color, cuda_ir = self.frame_queue.pop(0)

            if self.net_det is None or self.net_lpr is None:
                continue

            # Stage 1: Detection (detectNet) on IR frame
            try:
                detections = self.net_det.Detect(cuda_ir, overlay='none')

                for det in detections:
                    if det.Confidence > 0.40:
                        # Stage 2: OCR via lprNet on cropped plate
                        roi = (det.Left, det.Top, det.Right, det.Bottom)
                        cuda_plate = jetson.utils.cudaCrop(cuda_ir, roi)

                        plate_text, ocr_conf = self.net_lpr.Recognize(cuda_plate)
                        plate_text = plate_text.upper().replace(" ", "").replace("-", "")

                        if ocr_conf > 0.50:
                            self.clean_dedup_cache()
                            if plate_text in self.recent_plates:
                                continue

                            self.recent_plates[plate_text] = time.time()

                            # Stage 3 & 4: Classifications
                            state, make, model = self._determine_vmmr(cuda_color, det)
                            color = self._determine_color(cuda_color, det)

                            ts_obj = datetime.now()
                            ts_str = ts_obj.strftime("%Y-%m-%d %H:%M:%S")
                            prefix = ts_obj.strftime("%Y%m%d%H%M%S") + f"_{plate_text}"

                            ir_path = os.path.join(self.images_dir, f"{prefix}_IR.jpg")
                            color_path = os.path.join(self.images_dir, f"{prefix}_Color.jpg")

                            # Save images locally (Convert CUDA to Numpy for OpenCV)
                            # Note: In real scenarios, you might want to save the crop or full frame
                            np_plate = jetson.utils.cudaToNumpy(cuda_plate)
                            np_color = jetson.utils.cudaToNumpy(cuda_color)

                            cv2.imwrite(ir_path, np_plate)
                            cv2.imwrite(color_path, np_color)

                            # Insert to local SQLite
                            if self.db:
                                gps_coords = "0.0000, 0.0000"
                                self.db.insert_read(
                                    plate_text, ocr_conf * 100.0, ts_str, gps_coords,
                                    ir_path, color_path, state, make, model, color
                                )

                            # Watchlist Check
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
                            for cb in self.new_read_callbacks:
                                try:
                                    cb(read_data, is_hit)
                                except Exception as e:
                                    logging.error(f"Callback error: {e}")
                            logging.info(f"Verified read emitted: {plate_text}")

            except Exception as e:
                logging.error(f"ALPR Engine Error: {e}", exc_info=True)

    @classmethod
    def connect_signal(cls, callback):
        cls.new_read_callbacks.append(callback)

    def stop(self):
        self._run_flag = False
        # Explicitly clear contexts to help with GPU resource release
        self.net_det = None
        self.net_lpr = None
        self.net_vmmr = None
        self.net_color = None
