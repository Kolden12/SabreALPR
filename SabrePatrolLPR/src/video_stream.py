import cv2
import time
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage

class VideoStreamThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    error_signal = pyqtSignal(str)

    def __init__(self, camera_config):
        super().__init__()
        self._run_flag = True
        self.camera_config = camera_config
        self.stream_url = self._get_stream_url()

    def _get_stream_url(self):
        model = self.camera_config.get("model", "")
        ip = self.camera_config.get("ip", "")
        if model == "VSR-20":
            return f"rtsp://{ip}:554/stream1"
        elif model == "VSR-40":
            return f"http://{ip}:8080/camcolor"
        return ""

    def run(self):
        if not self.stream_url:
            self.error_signal.emit("Invalid camera configuration.")
            return

        cap = cv2.VideoCapture(self.stream_url)
        # Reduce buffer size to minimize latency
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        while self._run_flag:
            ret, cv_img = cap.read()
            if ret:
                # Convert the image to format suitable for PyQt
                rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                # Must copy the image so the memory isn't garbage collected when OpenCV replaces the frame
                # Scale it down a bit to ensure it fits the UI smoothly (scaled in UI via QPixmap)
                self.change_pixmap_signal.emit(qt_image.copy())
            else:
                self.error_signal.emit("Stream disconnected, attempting reconnect...")
                cap.release()
                time.sleep(2) # Wait before reconnecting
                cap = cv2.VideoCapture(self.stream_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Shut down capture
        cap.release()

    def stop(self):
        self._run_flag = False
        self.wait()
