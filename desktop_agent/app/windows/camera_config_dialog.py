"""Kamera sozlash dialogi — USB yoki RTSP, jonli ko'rinish bilan.

Bitta dialog uch holat uchun ham ishlatiladi:
  - Ombor kamerasi — YANGI qo'shish (role='ombor', warehouse_id=<id>,
    camera_id=None). Bir omborga bir nechta kamera biriktirilishi mumkin
    (ba'zilari USB, ba'zilari RTSP orqali) — shuning uchun bu har safar
    saqlanganda YANGI kamera qo'shadi, mavjudlarini o'chirmaydi.
  - Ombor kamerasi — MAVJUDINI tahrirlash (role='ombor', camera_id=<id>).
  - Skaner kamerasi (role='skaner', warehouse_id=None) — hamon bitta,
    qurilma sifatida (tahrirlash = qayta yozish).
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QRadioButton, QButtonGroup, QGroupBox, QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from .. import db
from ..camera_utils import UsbDetectWorker, CameraPreviewWorker, build_rtsp_url
from ..audio_utils import list_mic_devices


class CameraConfigDialog(QDialog):
    def __init__(self, role: str, warehouse_id: int | None, title: str, parent=None, camera_id: int | None = None):
        super().__init__(parent)
        self.role = role
        self.warehouse_id = warehouse_id
        self.camera_id = camera_id
        self.setWindowTitle(title)
        self.setMinimumWidth(480)

        self._usb_worker: UsbDetectWorker | None = None
        self._preview_worker: CameraPreviewWorker | None = None

        layout = QVBoxLayout(self)

        # Ulanish turi
        type_box = QGroupBox("Ulanish turi")
        type_layout = QHBoxLayout(type_box)
        self.radio_usb = QRadioButton("USB kamera")
        self.radio_rtsp = QRadioButton("RTSP (IP-kamera)")
        self.radio_usb.setChecked(True)
        self.type_group = QButtonGroup(self)
        self.type_group.addButton(self.radio_usb)
        self.type_group.addButton(self.radio_rtsp)
        type_layout.addWidget(self.radio_usb)
        type_layout.addWidget(self.radio_rtsp)

        # "Qo'lda skaner" (HID/klaviatura-emulyatsiya qiluvchi pistolet
        # shaklidagi skaner) — faqat skaner kamerasi sozlanganda ma'noli,
        # ombor (video kuzatuv) kamerasi uchun tegishli emas.
        self.radio_hid = None
        if role == "skaner":
            self.radio_hid = QRadioButton("Qo'lda skaner (USB, klaviatura kabi)")
            self.type_group.addButton(self.radio_hid)
            type_layout.addWidget(self.radio_hid)
            self.radio_hid.toggled.connect(self._update_mode_visibility)
        layout.addWidget(type_box)

        # USB blok
        self.usb_box = QGroupBox("USB kamera tanlash")
        usb_layout = QVBoxLayout(self.usb_box)
        usb_row = QHBoxLayout()
        self.usb_combo = QComboBox()
        self.usb_detect_btn = QPushButton("Kameralarni aniqlash")
        self.usb_detect_btn.clicked.connect(self._detect_usb)
        usb_row.addWidget(self.usb_combo, 1)
        usb_row.addWidget(self.usb_detect_btn)
        usb_layout.addLayout(usb_row)
        layout.addWidget(self.usb_box)

        # RTSP blok
        self.rtsp_box = QGroupBox("RTSP manzil")
        rtsp_layout = QVBoxLayout(self.rtsp_box)
        self.rtsp_url_input = QLineEdit()
        self.rtsp_url_input.setPlaceholderText("rtsp://192.168.1.10:554/stream1")
        rtsp_layout.addWidget(QLabel("Manzil (URL)"))
        rtsp_layout.addWidget(self.rtsp_url_input)

        cred_row = QHBoxLayout()
        self.rtsp_user_input = QLineEdit()
        self.rtsp_user_input.setPlaceholderText("Login")
        self.rtsp_pass_input = QLineEdit()
        self.rtsp_pass_input.setPlaceholderText("Parol")
        self.rtsp_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        cred_row.addWidget(self.rtsp_user_input)
        cred_row.addWidget(self.rtsp_pass_input)
        rtsp_layout.addLayout(cred_row)
        layout.addWidget(self.rtsp_box)

        # Preview
        preview_row = QHBoxLayout()
        self.test_btn = QPushButton("Ulanishni tekshirish (jonli ko'rinish)")
        self.test_btn.clicked.connect(self._toggle_preview)
        preview_row.addWidget(self.test_btn)
        layout.addLayout(preview_row)

        self.preview_label = QLabel("Ko'rinish shu yerda chiqadi")
        self.preview_label.setFixedHeight(220)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFrameShape(QFrame.Shape.Box)
        self.preview_label.setStyleSheet("background:#111; color:#888;")
        layout.addWidget(self.preview_label)

        self.hid_info_label = QLabel(
            "Qo'lda skaner (pistolet shaklidagi) uchun qo'shimcha sozlash kerak emas — "
            "kompyuterga USB orqali ulang, u klaviatura kabi ishlaydi. Saqlagandan so'ng, "
            "dastur ochiq turgan davomida (hech qanday menyu ochmasdan, boshqa oyna "
            "fokusda bo'lsa ham) istalgan payt skanerlansa, kod avtomatik qabul qilinadi."
        )
        self.hid_info_label.setWordWrap(True)
        self.hid_info_label.setStyleSheet(
            "background:#eff6ff; border:1px solid #bfdbfe; color:#1e40af; "
            "border-radius:8px; padding:12px;"
        )
        self.hid_info_label.setVisible(False)
        layout.addWidget(self.hid_info_label)

        # Mikrofon — faqat ombor kamerasi uchun ma'noli (video audit
        # yozuvlariga ovoz qo'shish, ixtiyoriy). Qaysidir kameraning o'z
        # mikrofoni bo'lmasa — "Yo'q" tanlansa yetarli, video baribir
        # ovozsiz yoziladi (muammo emas).
        self.mic_box = None
        self.mic_combo = None
        if role == "ombor":
            self.mic_box = QGroupBox("Mikrofon (ixtiyoriy — video yozuvlariga ovoz qo'shish uchun)")
            mic_layout = QHBoxLayout(self.mic_box)
            self.mic_combo = QComboBox()
            self.mic_combo.addItem("Yo'q", None)
            for name in list_mic_devices():
                self.mic_combo.addItem(name, name)
            mic_refresh_btn = QPushButton("Yangilash")
            mic_refresh_btn.clicked.connect(self._refresh_mics)
            mic_layout.addWidget(self.mic_combo, 1)
            mic_layout.addWidget(mic_refresh_btn)
            layout.addWidget(self.mic_box)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color:#b91c1c;")
        layout.addWidget(self.status_label)

        # Tugmalar
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Saqlash")
        self.save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Bekor qilish")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.radio_usb.toggled.connect(self._update_mode_visibility)
        self._update_mode_visibility()
        self._load_existing()

    # ── Yordamchi ──────────────────────────────────────────────────────

    def _update_mode_visibility(self):
        is_hid = bool(self.radio_hid and self.radio_hid.isChecked())
        is_usb = self.radio_usb.isChecked() and not is_hid
        self.usb_box.setVisible(is_usb)
        self.rtsp_box.setVisible(not is_usb and not is_hid)
        self.test_btn.setVisible(not is_hid)
        self.preview_label.setVisible(not is_hid)
        self.hid_info_label.setVisible(is_hid)
        self._stop_preview()

    def _load_existing(self):
        if self.role == "ombor":
            cam = db.get_camera(self.camera_id) if self.camera_id else None
        else:
            cam = db.get_scanner_camera()
        if not cam:
            return
        if cam.connection_type == "usb":
            self.radio_usb.setChecked(True)
            if cam.usb_index is not None:
                self.usb_combo.clear()
                self.usb_combo.addItem(f"USB Kamera #{cam.usb_index}", cam.usb_index)
        elif cam.connection_type == "hid":
            if self.radio_hid:
                self.radio_hid.setChecked(True)
        else:
            self.radio_rtsp.setChecked(True)
            self.rtsp_url_input.setText(cam.rtsp_url or "")
            self.rtsp_user_input.setText(cam.rtsp_username or "")
            self.rtsp_pass_input.setText(cam.rtsp_password or "")
        if self.mic_combo is not None and cam.mic_device_name:
            index = self.mic_combo.findData(cam.mic_device_name)
            if index >= 0:
                self.mic_combo.setCurrentIndex(index)
            else:
                self.mic_combo.addItem(cam.mic_device_name, cam.mic_device_name)
                self.mic_combo.setCurrentIndex(self.mic_combo.count() - 1)
        self._update_mode_visibility()

    def _refresh_mics(self):
        if self.mic_combo is None:
            return
        current = self.mic_combo.currentData()
        self.mic_combo.clear()
        self.mic_combo.addItem("Yo'q", None)
        for name in list_mic_devices():
            self.mic_combo.addItem(name, name)
        if current:
            index = self.mic_combo.findData(current)
            if index >= 0:
                self.mic_combo.setCurrentIndex(index)

    # ── USB aniqlash ───────────────────────────────────────────────────

    def _detect_usb(self):
        self.status_label.setText("")
        self.usb_detect_btn.setEnabled(False)
        self.usb_detect_btn.setText("Qidirilmoqda...")
        self._usb_worker = UsbDetectWorker()
        self._usb_worker.finished_ok.connect(self._on_usb_detected)
        self._usb_worker.start()

    def _on_usb_detected(self, indices: list):
        self.usb_detect_btn.setEnabled(True)
        self.usb_detect_btn.setText("Kameralarni aniqlash")
        self.usb_combo.clear()
        if not indices:
            self.status_label.setText("Hech qanday USB kamera topilmadi.")
            return
        for i in indices:
            self.usb_combo.addItem(f"USB Kamera #{i}", i)

    # ── Preview ────────────────────────────────────────────────────────

    def _toggle_preview(self):
        if self._preview_worker is not None:
            self._stop_preview()
            self.test_btn.setText("Ulanishni tekshirish (jonli ko'rinish)")
            return

        self.status_label.setText("")
        if self.radio_usb.isChecked():
            if self.usb_combo.currentData() is None:
                self.status_label.setText("Avval 'Kameralarni aniqlash' orqali kamerani tanlang.")
                return
            source, is_rtsp = self.usb_combo.currentData(), False
        else:
            url = self.rtsp_url_input.text().strip()
            if not url:
                self.status_label.setText("RTSP manzilini kiriting.")
                return
            source = build_rtsp_url(url, self.rtsp_user_input.text().strip(), self.rtsp_pass_input.text().strip())
            is_rtsp = True

        self._preview_worker = CameraPreviewWorker(source, is_rtsp=is_rtsp)
        self._preview_worker.frame_ready.connect(self._on_frame)
        self._preview_worker.error.connect(self._on_preview_error)
        self._preview_worker.start()
        self.test_btn.setText("To'xtatish")

    def _on_frame(self, qimage):
        pixmap = QPixmap.fromImage(qimage).scaled(
            self.preview_label.width(), self.preview_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(pixmap)

    def _on_preview_error(self, message: str):
        self.status_label.setText(message)
        self._stop_preview()
        self.test_btn.setText("Ulanishni tekshirish (jonli ko'rinish)")

    def _stop_preview(self):
        if self._preview_worker is not None:
            self._preview_worker.frame_ready.disconnect(self._on_frame)
            self._preview_worker.error.disconnect(self._on_preview_error)
            self._preview_worker.stop()
            self._preview_worker = None
        self.preview_label.setText("Ko'rinish shu yerda chiqadi")
        self.preview_label.setPixmap(QPixmap())

    # ── Saqlash ────────────────────────────────────────────────────────

    def _save(self):
        if self.radio_hid and self.radio_hid.isChecked():
            connection_type, kwargs = "hid", {}
        elif self.radio_usb.isChecked():
            usb_index = self.usb_combo.currentData()
            if usb_index is None:
                QMessageBox.warning(self, "Xato", "Avval USB kamerani aniqlab, tanlang.")
                return
            connection_type, kwargs = "usb", {"usb_index": usb_index}
        else:
            url = self.rtsp_url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "Xato", "RTSP manzilini kiriting.")
                return
            connection_type = "rtsp"
            kwargs = {
                "rtsp_url": url,
                "rtsp_username": self.rtsp_user_input.text().strip(),
                "rtsp_password": self.rtsp_pass_input.text().strip(),
            }

        if self.role == "ombor":
            if self.mic_combo is not None:
                kwargs["mic_device_name"] = self.mic_combo.currentData()
            if self.camera_id:
                db.update_camera(self.camera_id, connection_type, **kwargs)
            else:
                db.add_camera_for_warehouse(self.warehouse_id, connection_type, **kwargs)
        else:
            db.save_scanner_camera(connection_type, **kwargs)

        self._stop_preview()
        self.accept()

    def closeEvent(self, event):
        self._stop_preview()
        super().closeEvent(event)
