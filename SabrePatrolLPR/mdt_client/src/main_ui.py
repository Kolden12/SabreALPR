import sys
import os
import platform
import websocket
import json
import base64

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QAction,
    QFrame, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSlot, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPixmap, QImage
from PyQt5.QtMultimedia import QSound
from src.settings_ui import SettingsDialog
from src.config import load_config
from src.video_stream import VideoStreamThread
import os
import sys

def get_asset_path(filename):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, "assets", filename)

class WSClientThread(QThread):
    new_read_signal = pyqtSignal(dict, bool, str, str) # data, is_hit, ir_b64, color_b64

    def __init__(self, jetson_ip):
        super().__init__()
        self.jetson_ip = jetson_ip
        self.run_flag = True

    def run(self):
        url = f"ws://{self.jetson_ip}:8000/ws"
        while self.run_flag:
            try:
                self.ws = websocket.WebSocketApp(url,
                                          on_message=self.on_message,
                                          on_error=self.on_error,
                                          on_close=self.on_close)
                self.ws.run_forever()
            except Exception as e:
                import time
                time.sleep(2)

    def on_message(self, ws, message):
        try:
            payload = json.loads(message)
            if payload.get("type") == "new_read":
                self.new_read_signal.emit(
                    payload["data"],
                    payload["is_hit"],
                    payload["ir_image_b64"],
                    payload["color_image_b64"]
                )
        except Exception as e:
            print(f"WS Parse Error: {e}")

    def on_error(self, ws, error):
        pass

    def on_close(self, ws, close_status_code, close_msg):
        pass

    def stop(self):
        self.run_flag = False
        if hasattr(self, 'ws'):
            self.ws.close()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sabre Patrol LPR Windows Suite v1.0")
        self.resize(1920, 1080)
        self.config = load_config()
        self.video_thread = None
        self.ws_thread = None

        self.init_ui()
        self.init_services()

        try:
            self.ding_sound = QSound(get_asset_path("ding.wav"))
            self.siren_sound = QSound(get_asset_path("siren.wav"))
        except:
            pass # Handle missing audio gracefully if QtMultimedia fails

    def init_services(self):
        cameras = self.config.get("cameras", [])
        if cameras:
            cam1 = cameras[0]
            self.video_thread = VideoStreamThread(cam1)
            self.video_thread.new_frame_signal.connect(self.handle_new_frame)
            self.video_thread.error_signal.connect(self.handle_video_error)
            self.video_thread.start()

        jetson_ip = self.config.get("jetson_ip", "192.168.1.50")
        if jetson_ip:
            self.ws_thread = WSClientThread(jetson_ip)
            self.ws_thread.new_read_signal.connect(self.handle_new_read)
            self.ws_thread.start()

    def init_ui(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        top_layout = QHBoxLayout()
        video_container = QVBoxLayout()

        self.video_label = QLabel("Live Video Stream")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.video_label.setMinimumSize(960, 500)
        video_container.addWidget(self.video_label)

        top_layout.addLayout(video_container, stretch=1)

        self.capture_label = QLabel("Last Verified Capture")
        self.capture_label.setAlignment(Qt.AlignCenter)
        self.capture_label.setStyleSheet("background-color: #222; color: white;")
        self.capture_label.setMinimumSize(960, 540)
        top_layout.addWidget(self.capture_label, stretch=1)

        main_layout.addLayout(top_layout, stretch=5)

        self.hit_banner = QLabel("WAITING FOR DETECTIONS")
        self.hit_banner.setAlignment(Qt.AlignCenter)
        banner_font = QFont("Arial", 36, QFont.Bold)
        self.hit_banner.setFont(banner_font)
        self.hit_banner.setStyleSheet("background-color: #333; color: white; padding: 10px;")
        self.hit_banner.setMinimumHeight(100)
        main_layout.addWidget(self.hit_banner, stretch=1)

        self.history_table = QTableWidget(0, 6)
        self.history_table.setHorizontalHeaderLabels([
            "Timestamp", "Plate", "State", "Color", "Make", "Model"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setAlternatingRowColors(True)
        table_font = QFont("Arial", 14)
        self.history_table.setFont(table_font)

        main_layout.addWidget(self.history_table, stretch=4)

    @pyqtSlot(QImage, object, object)
    def handle_new_frame(self, qt_image, cv_color, cv_ir):
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            self.video_label.width(), self.video_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)

    @pyqtSlot(str)
    def handle_video_error(self, error_msg):
        self.video_label.setText(f"Video Error:\n{error_msg}")

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_():
            self.config = load_config()
            if self.video_thread is not None:
                self.video_thread.stop()
            if self.ws_thread is not None:
                self.ws_thread.stop()
            self.init_services()

    def update_hit_banner(self, plate, state, color, make, model, is_hit=False):
        text = f"PLATE: {plate} | STATE: {state} | COLOR: {color} | MAKE: {make} | MODEL: {model}"
        self.hit_banner.setText(text)
        if is_hit:
            self.hit_banner.setStyleSheet("background-color: red; color: white; padding: 10px;")
        else:
            self.hit_banner.setStyleSheet("background-color: green; color: white; padding: 10px;")

    @pyqtSlot(dict, bool, str, str)
    def handle_new_read(self, read_data, is_hit, ir_b64, color_b64):
        self.update_hit_banner(
            read_data['plate'], read_data['state'],
            read_data['color'], read_data['make'],
            read_data['model'], is_hit
        )

        self.add_history_entry(
            read_data['timestamp'], read_data['plate'],
            read_data['state'], read_data['color'],
            read_data['make'], read_data['model']
        )

        if hasattr(self, 'siren_sound') and hasattr(self, 'ding_sound'):
            if is_hit:
                self.siren_sound.play()
            else:
                self.ding_sound.play()

        if color_b64:
            try:
                img_data = base64.b64decode(color_b64)
                image = QImage.fromData(img_data)
                pixmap = QPixmap.fromImage(image)
                self.capture_label.setPixmap(pixmap.scaled(
                    self.capture_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                ))
            except Exception as e:
                self.capture_label.setText("Image Corrupted")
        else:
            self.capture_label.setText("No Image Received")

    def closeEvent(self, event):
        if self.video_thread is not None:
            self.video_thread.stop()
        if self.ws_thread is not None:
            self.ws_thread.stop()
        super().closeEvent(event)

    def add_history_entry(self, timestamp, plate, state, color, make, model):
        self.history_table.insertRow(0)
        self.history_table.setItem(0, 0, QTableWidgetItem(timestamp))
        self.history_table.setItem(0, 1, QTableWidgetItem(plate))
        self.history_table.setItem(0, 2, QTableWidgetItem(state))
        self.history_table.setItem(0, 3, QTableWidgetItem(color))
        self.history_table.setItem(0, 4, QTableWidgetItem(make))
        self.history_table.setItem(0, 5, QTableWidgetItem(model))

        if self.history_table.rowCount() > 10:
            self.history_table.removeRow(10)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
