import cv2
import time
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage

class VideoStreamThread(QThread):
    # Emits (qt_image_color, raw_cv_color, raw_cv_ir)
    new_frame_signal = pyqtSignal(QImage, object, object)
    error_signal = pyqtSignal(str)

    def __init__(self, camera_config):
        super().__init__()
        self._run_flag = True
        self.camera_config = camera_config
        self.fps_limit = 15
        self.color_url, self.ir_url = self._get_stream_urls()

    def _get_stream_urls(self):
        model = self.camera_config.get("model", "")
        ip = self.camera_config.get("ip", "")
        if model == "VSR-20":
            # Per user: Stream1 is IR, Stream2 is Color
            return f"rtsp://{ip}:554/stream2", f"rtsp://{ip}:554/stream1"
        elif model == "VSR-40":
            return f"http://{ip}:8080/camcolor", f"http://{ip}:8080/camir"
        return "", ""

    def run(self):
        if not self.color_url or not self.ir_url:
            self.error_signal.emit("Invalid camera configuration.")
            return

        cap_color = cv2.VideoCapture(self.color_url)
        cap_ir = cv2.VideoCapture(self.ir_url)

        cap_color.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap_ir.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        frame_delay = 1.0 / self.fps_limit

        while self._run_flag:
            start_time = time.time()

            ret_color, cv_color = cap_color.read()
            ret_ir, cv_ir = cap_ir.read()

            if ret_color and ret_ir:
                # Convert the Color image to PyQt format for the UI
                rgb_image = cv2.cvtColor(cv_color, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)

                # Emit QT image for UI, and raw CV frames for ALPR engine
                self.new_frame_signal.emit(qt_image.copy(), cv_color, cv_ir)
            else:
                self.error_signal.emit("Stream disconnected, attempting reconnect...")
                cap_color.release()
                cap_ir.release()
                time.sleep(2)
                cap_color = cv2.VideoCapture(self.color_url)
                cap_ir = cv2.VideoCapture(self.ir_url)
                cap_color.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap_ir.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Throttle to 15 FPS max
            elapsed = time.time() - start_time
            if elapsed < frame_delay:
                time.sleep(frame_delay - elapsed)

        cap_color.release()
        cap_ir.release()

    def stop(self):
        self._run_flag = False
        self.wait()
