"""Bitta omborga biriktirilgan BIR NECHTA kamerani (ba'zilari USB,
ba'zilari RTSP orqali) ro'yxat ko'rinishida boshqarish dialogi."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QWidget,
)

from .. import db
from .camera_config_dialog import CameraConfigDialog


class WarehouseCamerasDialog(QDialog):
    def __init__(self, warehouse: db.Warehouse, parent=None):
        super().__init__(parent)
        self.warehouse = warehouse
        self.setWindowTitle(f"Kameralar — {warehouse.nomi}")
        self.setMinimumSize(560, 360)

        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        desc = QLabel(
            "Bu omborga bir nechta kamera biriktirish mumkin — ba'zilari "
            "USB, ba'zilari RTSP orqali."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#666;")
        header_row.addWidget(desc, 1)
        add_btn = QPushButton("+ Yangi kamera")
        add_btn.clicked.connect(self._add_camera)
        header_row.addWidget(add_btn)
        layout.addLayout(header_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Ulanish", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        close_btn = QPushButton("Yopish")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.refresh()

    def refresh(self):
        cameras = db.list_cameras_for_warehouse(self.warehouse.id)
        self.table.setRowCount(len(cameras))
        for row, cam in enumerate(cameras):
            if cam.connection_type == "usb":
                label = f"USB Kamera #{cam.usb_index}"
            else:
                label = f"RTSP: {cam.rtsp_url}"
            self.table.setItem(row, 0, QTableWidgetItem(label))
            self.table.setCellWidget(row, 1, self._build_row_actions(cam))

    def _build_row_actions(self, cam: db.Camera) -> QWidget:
        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        edit_btn = QPushButton("Tahrirlash")
        edit_btn.clicked.connect(lambda _, c=cam.id: self._edit_camera(c))
        actions_layout.addWidget(edit_btn)

        delete_btn = QPushButton("O'chirish")
        delete_btn.clicked.connect(lambda _, c=cam.id: self._delete_camera(c))
        actions_layout.addWidget(delete_btn)

        return actions

    def _add_camera(self):
        dialog = CameraConfigDialog(
            role="ombor", warehouse_id=self.warehouse.id,
            title=f"Yangi kamera — {self.warehouse.nomi}", parent=self,
        )
        if dialog.exec():
            self.refresh()

    def _edit_camera(self, camera_id: int):
        dialog = CameraConfigDialog(
            role="ombor", warehouse_id=self.warehouse.id, camera_id=camera_id,
            title=f"Kamerani tahrirlash — {self.warehouse.nomi}", parent=self,
        )
        if dialog.exec():
            self.refresh()

    def _delete_camera(self, camera_id: int):
        confirm = QMessageBox.question(self, "Tasdiqlash", "Bu kamerani o'chirmoqchimisiz?")
        if confirm == QMessageBox.StandardButton.Yes:
            db.delete_camera(camera_id)
            self.refresh()
