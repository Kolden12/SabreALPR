import os
import cv2
import time
import uuid
import logging
from datetime import datetime
import threading

# Import heavy ML libraries globally on main thread to avoid WinError 1114 in PyInstaller Windows
from paddleocr import PaddleOCR
from ultralytics import YOLO

from db_manager import DBManager
from config import CONFIG_DIR

# Set YOLO paths explicitly to the APPDATA config dir
YOLO_DET_MODEL_PATH = os.path.join(CONFIG_DIR, "yolo11n.onnx")
YOLO_CLS_MODEL_PATH = os.path.join(CONFIG_DIR, "yolov8n-cls.onnx")

class ALPREngineThread(threading.Thread):
    new_read_callbacks = []

    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.db = DBManager()
        self.frame_queue = []
        self.recent_plates = {} # For 30s deduplication cache

        self.det_model = None
        self.cls_model = None
        self.reader = None

        # Ensure local image save directory exists
        self.images_dir = os.path.join(CONFIG_DIR, "images")
        os.makedirs(self.images_dir, exist_ok=True)

    def _initialize_models(self):
        """Loads models lazily inside the thread."""
        try:
            logging.info("Initializing OpenCV DNN and PaddleOCR models...")

            # Initialize Native Ultralytics YOLO (Leverages TensorRT/CUDA automatically on Jetson if available)
            try:
                # Use .pt or .engine paths here. Defaults to .pt and Ultralytics handles TRT export if needed.
                # Assuming models are in config dir. We will use native YOLO paths.
                det_path = YOLO_DET_MODEL_PATH.replace('.onnx', '.pt')
                if not os.path.exists(det_path):
                    det_path = "yolo11n.pt" # Fallback to auto-download
                self.det_model = YOLO(det_path)

                cls_path = YOLO_CLS_MODEL_PATH.replace('.onnx', '.pt')
                if not os.path.exists(cls_path):
                    cls_path = "yolov8n-cls.pt" # Fallback to auto-download
                self.cls_model = YOLO(cls_path)
            except Exception as e:
                logging.error(f"Failed to load YOLO models: {e}")
                self.det_model = None
                self.cls_model = None

            # Initialize PaddleOCR
            self.reader = PaddleOCR(use_angle_cls=True, lang='en')
            logging.info("ONNX and PaddleOCR initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to load ALPR AI models locally: {e}")

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
            x1, y1, x2, y2 = map(int, box)
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
        if self.cls_model is None:
            return "UnknownState", "UnknownMake", "UnknownModel"

        try:
            # Crop the color frame using the detected coordinates
            x1, y1, x2, y2 = map(int, box)

            # Expand the crop slightly to capture the vehicle context
            h, w = cv_color.shape[:2]
            cx1, cy1 = max(0, x1 - 200), max(0, y1 - 200)
            cx2, cy2 = min(w, x2 + 200), min(h, y2 + 200)

            vehicle_crop = cv_color[cy1:cy2, cx1:cx2]
            if vehicle_crop.size == 0:
                return "UnknownState", "UnknownMake", "UnknownModel"

            # Run Native YOLO classifier inference
            import numpy as np
            results = self.cls_model(vehicle_crop, verbose=False)
            top_class_idx = int(results[0].probs.top1)

            # Assuming a generic class mapping logic here, requires your specific training names
            top_class_name = f"Class_{top_class_idx}"
            parts = top_class_name.split('_')
            if len(parts) >= 3:
                return parts[0], parts[1], parts[2]
            return top_class_name, "Unknown", "Unknown"

        except Exception as e:
            logging.error(f"VMMR Inference Error: {e}")

        return "UnknownState", "UnknownMake", "UnknownModel"

    def _process_onnx_yolo(self, frame):
        """Pre-processes frame and returns bounding boxes from ONNX output."""
        import numpy as np
        input_size = 640
        h, w = frame.shape[:2]

        # Letterbox resize
        scale = min(input_size / h, input_size / w)
        nh, nw = int(h * scale), int(w * scale)
        img_resized = cv2.resize(frame, (nw, nh))

        # Pad
        img_padded = np.full((input_size, input_size, 3), 114, dtype=np.uint8)
        img_padded[(input_size - nh) // 2:(input_size - nh) // 2 + nh,
                   (input_size - nw) // 2:(input_size - nw) // 2 + nw] = img_resized

        # Run inference using OpenCV DNN
        blob = cv2.dnn.blobFromImage(img_padded, 1.0/255.0, (input_size, input_size), swapRB=True, crop=False)
        self.det_model.setInput(blob)
        outputs = self.det_model.forward()

        predictions = np.squeeze(outputs).T # (8400, 84)

        # Filter by confidence
        # Lower confidence threshold from 0.80 to 0.40 since this is an IR license plate
        # and YOLO can predict lower confidences but still have valid plate areas.
        scores = np.max(predictions[:, 4:], axis=1)
        predictions = predictions[scores > 0.40, :]
        scores = scores[scores > 0.40]

        if len(predictions) == 0:
            return []

        class_ids = np.argmax(predictions[:, 4:], axis=1)

        # Get bounding boxes
        boxes = predictions[:, :4]

        # Rescale boxes back to original image size
        boxes[:, 0] = (boxes[:, 0] - (input_size - nw) / 2) / scale # x center
        boxes[:, 1] = (boxes[:, 1] - (input_size - nh) / 2) / scale # y center
        boxes[:, 2] = boxes[:, 2] / scale # width
        boxes[:, 3] = boxes[:, 3] / scale # height

        # Convert to xyxy
        x1 = boxes[:, 0] - boxes[:, 2] / 2
        y1 = boxes[:, 1] - boxes[:, 3] / 2
        x2 = boxes[:, 0] + boxes[:, 2] / 2
        y2 = boxes[:, 1] + boxes[:, 3] / 2

        xyxy_boxes = np.column_stack((x1, y1, x2, y2))

        # NMS - lowered score threshold from 0.80 to 0.40
        indices = cv2.dnn.NMSBoxes(xyxy_boxes.tolist(), scores.tolist(), 0.40, 0.45)

        results = []
        if len(indices) > 0:
            for i in indices.flatten():
                results.append({
                    "box": xyxy_boxes[i],
                    "conf": scores[i],
                    "class_id": class_ids[i]
                })

        return results

    def run(self):
        # Initialize models when the thread actually starts execution
        self._initialize_models()

        while self._run_flag:
            if not self.frame_queue:
                time.sleep(0.05)
                continue

            cv_color, cv_ir = self.frame_queue.pop(0)

            if self.det_model is None or self.reader is None:
                continue

            # Stage 1: Detection (YOLO11n Native) on IR frame
            try:
                results = self.det_model(cv_ir, verbose=False, conf=0.40)

                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])

                        logging.debug(f"YOLO Native detected object class {cls_id} with confidence {conf:.2f}")

                        if conf > 0.40:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])

                        # Ensure coordinates are within frame bounds to prevent empty or invalid crops
                        h, w = cv_ir.shape[:2]
                        x1 = max(0, min(x1, w - 1))
                        y1 = max(0, min(y1, h - 1))
                        x2 = max(0, min(x2, w))
                        y2 = max(0, min(y2, h))

                        # Stage 2: OCR on crop via PaddleOCR
                        plate_crop = cv_ir[y1:y2, x1:x2]
                        if plate_crop.size == 0:
                            logging.warning("YOLO detection yielded an empty crop. Skipping OCR.")
                            continue

                        ocr_results = self.reader.ocr(plate_crop, cls=False)
                        if ocr_results and ocr_results[0]:
                            # Get the highest confidence text
                            # PaddleOCR format: [[[[x, y], [x, y], [x, y], [x, y]], ('TEXT', CONFIDENCE)], ...]
                            text_data = max(ocr_results[0], key=lambda x: x[1][1])
                            plate_text = text_data[1][0].upper().replace(" ", "").replace("-", "")
                            ocr_conf = float(text_data[1][1])

                            logging.info(f"PaddleOCR read: '{plate_text}' with confidence {ocr_conf:.2f}")

                            # Process if OCR confidence > 0.50 (lowered to catch valid plates that score low)
                            if ocr_conf > 0.50:
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
                                for cb in self.new_read_callbacks:
                                    try:
                                        cb(read_data, is_hit)
                                    except Exception as e:
                                        logging.error(f"Callback error: {e}")
                                logging.info(f"Verified read emitted to UI/DB: {plate_text}")
                            else:
                                logging.debug(f"OCR string '{plate_text}' rejected (confidence {ocr_conf:.2f} <= 0.70)")

            except Exception as e:
                logging.error(f"ALPR Engine Error during processing loop: {e}", exc_info=True)

    @classmethod
    def connect_signal(cls, callback):
        cls.new_read_callbacks.append(callback)

    def stop(self):
        self._run_flag = False
        self.wait()
