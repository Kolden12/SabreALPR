import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QGroupBox, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox
)
from src.config import load_config, save_config

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sabre Patrol LPR Settings")
        self.resize(500, 600)
        self.config = load_config()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # General Settings Group
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout()
        self.unit_id_input = QLineEdit()
        general_layout.addRow("Unit ID:", self.unit_id_input)
        general_group.setLayout(general_layout)
        layout.addWidget(general_group)

        # Camera Management Group
        cam_group = QGroupBox("Camera Management (Max 4)")
        cam_layout = QVBoxLayout()

        # Add Camera Form
        add_cam_layout = QHBoxLayout()
        self.cam_model_combo = QComboBox()
        self.cam_model_combo.addItems(["VSR-20", "VSR-40"])
        self.cam_ip_input = QLineEdit()
        self.cam_ip_input.setPlaceholderText("IP Address")
        self.add_cam_btn = QPushButton("Add Camera")
        self.add_cam_btn.clicked.connect(self.add_camera)

        add_cam_layout.addWidget(self.cam_model_combo)
        add_cam_layout.addWidget(self.cam_ip_input)
        add_cam_layout.addWidget(self.add_cam_btn)
        cam_layout.addLayout(add_cam_layout)

        # Camera List
        self.cam_table = QTableWidget(0, 3)
        self.cam_table.setHorizontalHeaderLabels(["Model", "IP Address", "Action"])
        self.cam_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        cam_layout.addWidget(self.cam_table)

        cam_group.setLayout(cam_layout)
        layout.addWidget(cam_group)

        # TrueNAS / SMB Group
        nas_group = QGroupBox("TrueNAS SMB Settings")
        nas_layout = QFormLayout()
        self.nas_ip_input = QLineEdit()
        self.nas_user_input = QLineEdit()
        self.nas_pass_input = QLineEdit()
        self.nas_pass_input.setEchoMode(QLineEdit.Password)

        nas_layout.addRow("TrueNAS IP:", self.nas_ip_input)
        nas_layout.addRow("SMB Username:", self.nas_user_input)
        nas_layout.addRow("SMB Password:", self.nas_pass_input)
        nas_group.setLayout(nas_layout)
        layout.addWidget(nas_group)

        # Save/Cancel Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def load_settings(self):
        self.unit_id_input.setText(self.config.get("unit_id", ""))
        self.nas_ip_input.setText(self.config.get("truenas_ip", ""))
        self.nas_user_input.setText(self.config.get("truenas_user", ""))
        self.nas_pass_input.setText(self.config.get("truenas_password", ""))

        for cam in self.config.get("cameras", []):
            self.add_camera_to_table(cam["model"], cam["ip"])

    def add_camera(self):
        if self.cam_table.rowCount() >= 4:
            QMessageBox.warning(self, "Limit Reached", "You can only add up to 4 cameras.")
            return

        model = self.cam_model_combo.currentText()
        ip = self.cam_ip_input.text().strip()

        if not ip:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid IP address.")
            return

        # Check if already exists
        for row in range(self.cam_table.rowCount()):
            if self.cam_table.item(row, 1).text() == ip:
                QMessageBox.warning(self, "Duplicate", "This camera IP is already added.")
                return

        self.add_camera_to_table(model, ip)
        self.cam_ip_input.clear()

    def add_camera_to_table(self, model, ip):
        row = self.cam_table.rowCount()
        self.cam_table.insertRow(row)

        self.cam_table.setItem(row, 0, QTableWidgetItem(model))
        self.cam_table.setItem(row, 1, QTableWidgetItem(ip))

        del_btn = QPushButton("Remove")
        del_btn.clicked.connect(lambda: self.remove_camera(row))
        self.cam_table.setCellWidget(row, 2, del_btn)

    def remove_camera(self, row):
        self.cam_table.removeRow(row)
        # Update remove buttons to point to correct row
        for i in range(self.cam_table.rowCount()):
            del_btn = self.cam_table.cellWidget(i, 2)
            del_btn.clicked.disconnect()
            del_btn.clicked.connect(lambda _, r=i: self.remove_camera(r))

    def save_settings(self):
        self.config["unit_id"] = self.unit_id_input.text().strip()
        self.config["truenas_ip"] = self.nas_ip_input.text().strip()
        self.config["truenas_user"] = self.nas_user_input.text().strip()
        self.config["truenas_password"] = self.nas_pass_input.text().strip()

        cameras = []
        for row in range(self.cam_table.rowCount()):
            model = self.cam_table.item(row, 0).text()
            ip = self.cam_table.item(row, 1).text()
            cameras.append({"model": model, "ip": ip})

        self.config["cameras"] = cameras

        save_config(self.config)
        self.accept()
