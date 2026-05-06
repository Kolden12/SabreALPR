import sys
import os
import websocket
import json
import requests
import time

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QAction,
    QFrame, QScrollArea, QPushButton, QDialog, QTabWidget,
    QGridLayout, QProgressBar
)
from PyQt5.QtCore import Qt, pyqtSlot, QThread, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QFont, QPixmap, QImage
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt5.QtCore import QUrl

from src.settings_ui import SettingsDialog
from src.config import load_config
from src.video_stream import VideoStreamThread

def get_asset_path(filename):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, "assets", filename)

class ImageDownloader(QObject):
    finished = pyqtSignal(QImage)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.manager = QNetworkAccessManager()
        self.manager.finished.connect(self.handle_finished)

    def start(self):
        self.manager.get(QNetworkRequest(QUrl(self.url)))

    def handle_finished(self, reply):
        if reply.error() == QNetworkReply.NoError:
            image = QImage.fromData(reply.readAll())
            self.finished.emit(image)
        reply.deleteLater()

class PlateCard(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, data, jetson_ip):
        super().__init__()
        self.data = data
        self.jetson_ip = jetson_ip
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedHeight(150)
        self.setStyleSheet("""
            PlateCard {
                background-color: #2c2c2c;
                border: 2px solid #444;
                border-radius: 8px;
                margin: 2px;
            }
            PlateCard:hover {
                border: 2px solid #0078d7;
            }
        """)

        layout = QHBoxLayout(self)

        # Thumbnail
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(200, 130)
        self.thumb_label.setStyleSheet("background-color: black;")
        self.thumb_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.thumb_label)

        # Metadata
        info_layout = QVBoxLayout()
        plate_font = QFont("Segoe UI", 24, QFont.Bold)
        self.plate_label = QLabel(data.get('plate', 'UNKNOWN'))
        self.plate_label.setFont(plate_font)
        self.plate_label.setStyleSheet("color: #ffffff;")
        info_layout.addWidget(self.plate_label)

        meta_font = QFont("Segoe UI", 12)
        meta_text = f"{data.get('timestamp', '')} | {data.get('camera_id', 'CAM-1')}"
        self.meta_label = QLabel(meta_text)
        self.meta_label.setFont(meta_font)
        self.meta_label.setStyleSheet("color: #aaaaaa;")
        info_layout.addWidget(self.meta_label)

        layout.addLayout(info_layout, stretch=1)

        # Hit Indicator
        if data.get('is_hit'):
            self.setStyleSheet(self.styleSheet() + "PlateCard { border: 2px solid red; background-color: #4a1a1a; }")

        self.downloader = None
        self.load_thumbnail()

    def load_thumbnail(self):
        img_url = f"http://{self.jetson_ip}:8000{self.data.get('image_url', '')}"
        self.downloader = ImageDownloader(img_url)
        self.downloader.finished.connect(self.set_image)
        self.downloader.start()

    def set_image(self, image):
        pixmap = QPixmap.fromImage(image)
        self.thumb_label.setPixmap(pixmap.scaled(self.thumb_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def mousePressEvent(self, event):
        self.clicked.emit(self.data)

class VerificationModal(QDialog):
    def __init__(self, data, jetson_ip, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Verify Plate: {data.get('plate')}")
        self.resize(1000, 700)
        self.setStyleSheet("background-color: #1a1a1a; color: white;")

        layout = QVBoxLayout(self)

        self.img_label = QLabel("Loading High-Res Crop...")
        self.img_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.img_label, stretch=1)

        info_label = QLabel(f"PLATE: {data.get('plate')} | CONFIDENCE: {data.get('confidence', 0):.1f}% | TIME: {data.get('timestamp')}")
        info_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)

        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(50)
        close_btn.setStyleSheet("background-color: #d9534f; font-weight: bold;")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        self.downloader = None
        self.load_image(data, jetson_ip)

    def load_image(self, data, jetson_ip):
        url = f"http://{jetson_ip}:8000{data.get('image_url', '')}"
        self.downloader = ImageDownloader(url)
        self.downloader.finished.connect(self.set_image)
        self.downloader.start()

    def set_image(self, image):
        pixmap = QPixmap.fromImage(image)
        self.img_label.setPixmap(pixmap.scaled(950, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation))

class WSClientThread(QThread):
    new_alert_signal = pyqtSignal(dict)

    def __init__(self, jetson_ip):
        super().__init__()
        self.jetson_ip = jetson_ip
        self.run_flag = True

    def run(self):
        url = f"ws://{self.jetson_ip}:8000/alerts"
        while self.run_flag:
            try:
                self.ws = websocket.WebSocketApp(url,
                                          on_message=self.on_message)
                self.ws.run_forever()
            except Exception:
                time.sleep(2)

    def on_message(self, ws, message):
        try:
            payload = json.loads(message)
            if payload.get("type") == "alert":
                self.new_alert_signal.emit(payload["data"])
        except Exception as e:
            print(f"WS Parse Error: {e}")

    def stop(self):
        self.run_flag = False
        if hasattr(self, 'ws'):
            self.ws.close()

class StatusWorker(QThread):
    status_received = pyqtSignal(dict)

    def __init__(self, jetson_ip):
        super().__init__()
        self.jetson_ip = jetson_ip
        self.running = True

    def run(self):
        while self.running:
            try:
                resp = requests.get(f"http://{self.jetson_ip}:8000/api/status", timeout=2)
                if resp.status_code == 200:
                    self.status_received.emit(resp.json())
            except Exception as e:
                self.status_received.emit({"error": str(e)})
            time.sleep(5)

    def stop(self):
        self.running = False

class HistoryWorker(QThread):
    history_received = pyqtSignal(list)

    def __init__(self, jetson_ip):
        super().__init__()
        self.jetson_ip = jetson_ip

    def run(self):
        try:
            resp = requests.get(f"http://{self.jetson_ip}:8000/api/history", timeout=5)
            if resp.status_code == 200:
                self.history_received.emit(resp.json())
        except:
            pass

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SABRE PATROL MDT v2.0")
        self.resize(1600, 900)
        self.config = load_config()
        self.video_thread = None
        self.ws_thread = None
        self.status_worker = None
        self.jetson_ip = self.config.get("jetson_ip", "192.168.1.50")

        self.init_ui()
        self.init_services()

    def init_ui(self):
        central_widget = QTabWidget()
        self.setCentralWidget(central_widget)

        # Tab 1: Dashboard
        self.dash_tab = QWidget()
        dash_layout = QHBoxLayout(self.dash_tab)

        # Left: Gallery
        gallery_container = QWidget()
        gallery_layout = QVBoxLayout(gallery_container)
        gallery_layout.addWidget(QLabel("RECENT DETECTIONS"))

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.gallery_widget = QWidget()
        self.gallery_vbox = QVBoxLayout(self.gallery_widget)
        self.gallery_vbox.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.gallery_widget)
        gallery_layout.addWidget(self.scroll_area)

        dash_layout.addWidget(gallery_container, stretch=1)

        # Right: Video & Controls
        control_container = QWidget()
        control_layout = QVBoxLayout(control_container)

        self.video_label = QLabel("LIVE STREAM")
        self.video_label.setStyleSheet("background-color: black;")
        self.video_label.setFixedSize(800, 450)
        self.video_label.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(self.video_label)

        # Status Card
        self.status_card = QFrame()
        self.status_card.setStyleSheet("background-color: #222; border-radius: 10px;")
        status_layout = QGridLayout(self.status_card)

        status_layout.addWidget(QLabel("JETSON TEMP:"), 0, 0)
        self.temp_label = QLabel("N/A")
        status_layout.addWidget(self.temp_label, 0, 1)

        status_layout.addWidget(QLabel("GPU LOAD:"), 1, 0)
        self.gpu_bar = QProgressBar()
        status_layout.addWidget(self.gpu_bar, 1, 1)

        status_layout.addWidget(QLabel("CAM STATUS:"), 2, 0)
        self.cam_status_label = QLabel("DISCONNECTED")
        status_layout.addWidget(self.cam_status_label, 2, 1)

        control_layout.addWidget(self.status_card)

        # IR Kill Switch
        self.ir_btn = QPushButton("IR KILL SWITCH")
        self.ir_btn.setFixedHeight(80)
        self.ir_btn.setStyleSheet("background-color: #5bc0de; font-size: 20pt; font-weight: bold;")
        self.ir_btn.clicked.connect(self.toggle_ir)
        control_layout.addWidget(self.ir_btn)

        dash_layout.addWidget(control_container, stretch=1)

        central_widget.addTab(self.dash_tab, "LPR DASHBOARD")

        # Menubar for Settings
        menubar = self.menuBar()
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        menubar.addAction(settings_action)

    def init_services(self):
        # Video
        cameras = self.config.get("cameras", [])
        if cameras:
            self.video_thread = VideoStreamThread(cameras[0])
            self.video_thread.new_frame_signal.connect(self.handle_new_frame)
            self.video_thread.start()

        # WebSocket
        self.ws_thread = WSClientThread(self.jetson_ip)
        self.ws_thread.new_alert_signal.connect(self.handle_new_alert)
        self.ws_thread.start()

        # Status Worker
        self.status_worker = StatusWorker(self.jetson_ip)
        self.status_worker.status_received.connect(self.handle_status_update)
        self.status_worker.start()

        # History
        self.history_worker = HistoryWorker(self.jetson_ip)
        self.history_worker.history_received.connect(self.handle_history_received)
        self.history_worker.start()

    def handle_history_received(self, history):
        for event in reversed(history):
            self.add_plate_card(event)

    @pyqtSlot(dict)
    def handle_new_alert(self, data):
        self.add_plate_card(data)

    def add_plate_card(self, data):
        card = PlateCard(data, self.jetson_ip)
        card.clicked.connect(self.show_verification)
        self.gallery_vbox.insertWidget(0, card)

    def show_verification(self, data):
        modal = VerificationModal(data, self.jetson_ip, self)
        modal.exec_()

    @pyqtSlot(dict)
    def handle_status_update(self, status):
        if "error" in status:
            self.cam_status_label.setText("JETSON OFFLINE")
            return

        jetson = status.get('jetson', {})
        # Thermal
        temp = jetson.get('thermals', {}).get('AO', 0)
        self.temp_label.setText(f"{temp}°C")
        # GPU
        gpu_load = jetson.get('gpu', {}).get('val', 0)
        self.gpu_bar.setValue(int(gpu_load))
        # Cameras
        cams = status.get('cameras', [])
        if cams:
            cam_txt = ", ".join([f"{c['camera_id']}: {c['status']}" for c in cams])
            self.cam_status_label.setText(cam_txt)

    def toggle_ir(self):
        # Fire and forget or use a QThread if needed, but for a single POST this might be okay-ish.
        # Still, let's use a lambda with QTimer to avoid blocking if the request is fast.
        def do_toggle():
            try:
                requests.post(f"http://{self.jetson_ip}:8000/api/cmd/ir_kill", timeout=2)
            except:
                pass
        QTimer.singleShot(0, do_toggle)
        self.ir_btn.setStyleSheet("background-color: #d9534f; font-size: 20pt; font-weight: bold;")
        QTimer.singleShot(2000, lambda: self.ir_btn.setStyleSheet("background-color: #5bc0de; font-size: 20pt; font-weight: bold;"))

    @pyqtSlot(QImage, object, object)
    def handle_new_frame(self, qt_image, cv_color, cv_ir):
        pixmap = QPixmap.fromImage(qt_image)
        self.video_label.setPixmap(pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_():
            self.config = load_config()
            # Restart
            self.close()
            os.execl(sys.executable, sys.executable, *sys.argv)

    def closeEvent(self, event):
        if self.status_worker:
            self.status_worker.stop()
            self.status_worker.wait()
        if self.ws_thread:
            self.ws_thread.stop()
            self.ws_thread.wait()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
