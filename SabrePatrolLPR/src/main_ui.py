import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QAction,
    QFrame, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPixmap, QImage
from PyQt5.QtMultimedia import QSound
from src.settings_ui import SettingsDialog
from src.config import load_config
from src.video_stream import VideoStreamThread
from src.data_monitor import DataMonitor
from src.api_webhook import WebhookIntegration
from src.background_workers import BackgroundWorkers
import os
import sys

def get_asset_path(filename):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, "assets", filename)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sabre Patrol LPR Windows Suite v1.0")
        self.resize(1920, 1080)
        self.config = load_config()
        self.video_thread = None
        self.init_ui()
        self.start_video_stream()

        # Audio setup
        self.ding_sound = QSound(get_asset_path("ding.wav"))
        self.siren_sound = QSound(get_asset_path("siren.wav"))

        # Webhook integration setup
        self.drive_path = "Z:\\" if os.name == 'nt' else "./"
        unit_id = self.config.get("unit_id", "SABRE-1")
        webhook_url = "https://webhook.site/68467d43-3e4e-423c-981f-4e8a28121249"
        self.webhook = WebhookIntegration(webhook_url, unit_id, self.drive_path)

        # Start data monitoring
        # Mocking Z: drive for testing locally by creating a dummy file
        self.results_path = os.path.join(self.drive_path, "results.txt")
        if not os.path.exists(self.results_path):
            with open(self.results_path, 'w') as f:
                pass

        self.data_monitor = DataMonitor(results_file=self.results_path)
        self.data_monitor.new_read_signal.connect(self.handle_new_read)

        # Start Background Workers (Cleanup and Offload)
        self.workers = BackgroundWorkers(self.config, drive_path=self.drive_path)
        self.workers.start()

    def init_ui(self):
        # Setup Menu
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Central Widget & Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- TOP ROW: Video and Image ---
        top_layout = QHBoxLayout()

        # Left: Live Video (Color) container
        video_container = QVBoxLayout()

        # Camera selector
        self.camera_selector = QComboBox()
        self.camera_selector.currentIndexChanged.connect(self.change_camera)
        self.update_camera_selector()
        video_container.addWidget(self.camera_selector)

        self.video_label = QLabel("Live Video Stream")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.video_label.setMinimumSize(960, 500)
        video_container.addWidget(self.video_label)

        top_layout.addLayout(video_container, stretch=1)

        # Right: Last Verified Capture
        self.capture_label = QLabel("Last Verified Capture")
        self.capture_label.setAlignment(Qt.AlignCenter)
        self.capture_label.setStyleSheet("background-color: #222; color: white;")
        self.capture_label.setMinimumSize(960, 540)
        top_layout.addWidget(self.capture_label, stretch=1)

        main_layout.addLayout(top_layout, stretch=5)

        # --- MIDDLE ROW: Hit Banner ---
        self.hit_banner = QLabel("WAITING FOR DETECTIONS")
        self.hit_banner.setAlignment(Qt.AlignCenter)
        banner_font = QFont("Arial", 36, QFont.Bold)
        self.hit_banner.setFont(banner_font)
        self.hit_banner.setStyleSheet("background-color: #333; color: white; padding: 10px;")
        self.hit_banner.setMinimumHeight(100)
        main_layout.addWidget(self.hit_banner, stretch=1)

        # --- BOTTOM ROW: History Table ---
        self.history_table = QTableWidget(0, 6)
        self.history_table.setHorizontalHeaderLabels([
            "Timestamp", "Plate", "State", "Color", "Make", "Model"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setAlternatingRowColors(True)
        # Font sizing for tactical display
        table_font = QFont("Arial", 14)
        self.history_table.setFont(table_font)

        main_layout.addWidget(self.history_table, stretch=4)

    def update_camera_selector(self):
        self.camera_selector.blockSignals(True)
        self.camera_selector.clear()
        cameras = self.config.get("cameras", [])
        for i, cam in enumerate(cameras):
            self.camera_selector.addItem(f"Cam {i+1} ({cam['model']}) - {cam['ip']}", cam)
        self.camera_selector.blockSignals(False)

    def change_camera(self, index):
        if index >= 0:
            cam_data = self.camera_selector.itemData(index)
            self.start_video_stream(cam_data)

    def start_video_stream(self, cam_data=None):
        if self.video_thread is not None:
            self.video_thread.stop()
            self.video_thread = None

        if cam_data is None:
            cameras = self.config.get("cameras", [])
            if not cameras:
                self.video_label.setText("No cameras configured.")
                return
            cam_data = cameras[0]

        self.video_thread = VideoStreamThread(cam_data)
        self.video_thread.change_pixmap_signal.connect(self.update_video_image)
        self.video_thread.error_signal.connect(self.handle_video_error)
        self.video_thread.start()

    @pyqtSlot(QImage)
    def update_video_image(self, qt_image):
        # Scale the image keeping aspect ratio
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
            self.update_camera_selector()
            self.start_video_stream()
            # Update Webhook unit_id
            self.webhook.unit_id = self.config.get("unit_id", "SABRE-1")
            # Update Background Workers config
            self.workers.config = self.config

    def update_hit_banner(self, plate, state, color, make, model, is_hit=False):
        text = f"PLATE: {plate} | STATE: {state} | COLOR: {color} | MAKE: {make} | MODEL: {model}"
        self.hit_banner.setText(text)
        if is_hit:
            self.hit_banner.setStyleSheet("background-color: red; color: white; padding: 10px;")
        else:
            self.hit_banner.setStyleSheet("background-color: green; color: white; padding: 10px;")

    @pyqtSlot(dict, bool)
    def handle_new_read(self, read_data, is_hit):
        # Update Hit Banner
        self.update_hit_banner(
            read_data['plate'], read_data['state'],
            read_data['color'], read_data['make'],
            read_data['model'], is_hit
        )

        # Add to history
        self.add_history_entry(
            read_data['timestamp'], read_data['plate'],
            read_data['state'], read_data['color'],
            read_data['make'], read_data['model']
        )

        # Play Audio
        if is_hit:
            self.siren_sound.play()
        else:
            self.ding_sound.play()

        # Send API Webhook
        self.webhook.send_payload(read_data, is_hit)

        # Optional: Load Last Verified Capture image from Z: drive
        # We assume the image follows the YYYYMMDD_PLATE_Color.jpg convention
        date_str = read_data['timestamp'].split(' ')[0].replace('-', '')
        img_filename = f"{date_str}_{read_data['plate']}_Color.jpg"
        img_path = os.path.join(os.path.dirname(self.results_path), img_filename)

        if os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.capture_label.width(), self.capture_label.height(),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.capture_label.setPixmap(scaled_pixmap)
            else:
                self.capture_label.setText("Image Corrupted")
        else:
            self.capture_label.setText("Waiting for Image...")

    def closeEvent(self, event):
        if self.video_thread is not None:
            self.video_thread.stop()
        if hasattr(self, 'data_monitor'):
            self.data_monitor.stop()
        if hasattr(self, 'workers'):
            self.workers.stop()
        super().closeEvent(event)

    def add_history_entry(self, timestamp, plate, state, color, make, model):
        self.history_table.insertRow(0) # Insert at top

        self.history_table.setItem(0, 0, QTableWidgetItem(timestamp))
        self.history_table.setItem(0, 1, QTableWidgetItem(plate))
        self.history_table.setItem(0, 2, QTableWidgetItem(state))
        self.history_table.setItem(0, 3, QTableWidgetItem(color))
        self.history_table.setItem(0, 4, QTableWidgetItem(make))
        self.history_table.setItem(0, 5, QTableWidgetItem(model))

        # Keep only last 10 entries
        if self.history_table.rowCount() > 10:
            self.history_table.removeRow(10)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
