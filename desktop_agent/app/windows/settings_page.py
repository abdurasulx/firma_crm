from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox,
)
from PyQt6.QtCore import QThread, QTimer, pyqtSignal

from .. import db
from ..api_client import station_login, station_login_by_qr, fetch_omborlar, parse_server_input, ApiError, send_logout
from ..label_printer_service import list_printers, LabelPrintWorker
from .camera_config_dialog import CameraConfigDialog


class _ApiCallWorker(QThread):
    """Login/sinxronlash so'rovlarini fon oqimida bajaradi — to'g'ridan-
    to'g'ri asosiy oqimda chaqirilsa, server sekin javob bersa yoki
    umuman ulanmasa, butun ilova muzlab qolardi (68-qadamda tuzatilgan
    skanerlash muammosi bilan bir xil turkumdagi xavf)."""
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    # Token eskirgan/bekor qilingan (401) — faqat MAVJUD tokendan
    # foydalanadigan so'rovlar (masalan `fetch_omborlar` sinxronlash)
    # uchun ma'noli; login urinishidagi 401 ("parol xato") bilan
    # aralashtirilmasligi kerak — shu sabab chaqiruvchi tomon o'zi
    # tanlab ulaydi (barcha worker'larga avtomatik emas).
    token_invalid = pyqtSignal()

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        # Eski worker obyekti tezda yangisi bilan almashtirilganda GC uni
        # C++ oqimi hali to'liq join bo'lmasdan o'chirib yubormasligi uchun.
        self.finished.connect(self.wait)

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
        except ApiError as exc:
            if exc.status_code == 401:
                self.token_invalid.emit()
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 — kutilmagan xato butun ilovani yiqitmasin
            self.failed.emit(f"Kutilmagan xato: {exc}")
        else:
            self.succeeded.emit(result)


class SettingsPage(QWidget):
    """Har bir Desktop Agent o'rnatilishi (stansiya) o'zining shaxsiy
    login/paroli bilan ERP'ga kiradi — ERP'dagi "Hodimlar" bo'limida
    "Desktop Agent" turida yaratilgan hisob orqali. Bitta firma bir nechta
    stansiyani shu tarzda alohida-alohida boshqarishi mumkin."""

    # `_sync_worker` (mavjud tokendan foydalanadigan `fetch_omborlar`)
    # 401 qaytarsa — token boshqa joyda bekor qilingan, `MainWindow`
    # heartbeatdagi bilan bir xil avtomatik logout oqimini ishga tushiradi.
    session_expired = pyqtSignal()

    def __init__(self, on_synced=None, on_scanner_changed=None, on_login_succeeded=None, on_scale_changed=None,
                 on_recheck_devices=None, on_logout=None, parent=None):
        super().__init__(parent)
        self.on_synced = on_synced
        self.on_scanner_changed = on_scanner_changed
        self.on_scale_changed = on_scale_changed
        self.on_login_succeeded = on_login_succeeded
        self.on_recheck_devices = on_recheck_devices
        self.on_logout = on_logout
        self._login_worker: _ApiCallWorker | None = None
        self._sync_worker: _ApiCallWorker | None = None
        self._logout_worker: _ApiCallWorker | None = None
        self._connecting_timer = QTimer(self)
        self._connecting_timer.setInterval(400)
        self._connecting_timer.timeout.connect(self._tick_connecting_animation)
        self._connecting_dots = 0
        layout = QVBoxLayout(self)

        title_row = QHBoxLayout()
        title = QLabel("Sozlamalar — ERP bilan bog'lash")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        title_row.addWidget(title)
        title_row.addStretch(1)
        # Qurilma-tekshiruv sahifasidan "Sozlamalarga o'tish" bosilgach
        # (176-qadam) — muammo tuzatilgach shu tugma orqali qayta
        # tekshirishga qaytiladi (`_on_startup_open_settings`ga qarang).
        recheck_btn = QPushButton("🔄 Qurilmalarni qayta tekshirish")
        recheck_btn.clicked.connect(lambda: self.on_recheck_devices and self.on_recheck_devices())
        title_row.addWidget(recheck_btn)
        layout.addLayout(title_row)

        # QR kod orqali login — endi standart usul (145-qadam). Qurilma
        # hali login qilinmagan bo'lsa, qo'lda login/parol maydonlari
        # o'rniga shu xabar ko'rsatiladi — stansiya kamerasi (yoki HID
        # skaner) allaqachon login holatidan mustaqil ishlab turibdi
        # (`ScannerService`), shuning uchun QR kod har qanday paytda
        # skanerlanishi mumkin.
        self.qr_prompt_label = QLabel(
            "📷 Qurilmani ro'yxatdan o'tkazish uchun administratordan "
            "so'rang: ERP'da Profil sahifasida \"Desktop Agent QR-login\" "
            "kartasidagi QR kodni shu stansiya kamerasiga (yoki HID "
            "skaneriga) ko'rsating — avtomatik tizimga kirasiz."
        )
        self.qr_prompt_label.setWordWrap(True)
        self.qr_prompt_label.setStyleSheet(
            "color:#0f172a; background:#eff6ff; border:1px solid #bfdbfe; "
            "border-radius:8px; padding:14px; font-weight:600;"
        )
        layout.addWidget(self.qr_prompt_label)

        self.manual_toggle_btn = QPushButton("Qo'lda login/parol bilan kirish")
        self.manual_toggle_btn.setFlat(True)
        self.manual_toggle_btn.setStyleSheet("text-align:left; color:#2563eb; border:none;")
        self.manual_toggle_btn.clicked.connect(self._toggle_manual_login)
        layout.addWidget(self.manual_toggle_btn)

        self.manual_login_container = QWidget()
        manual_layout = QVBoxLayout(self.manual_login_container)
        manual_layout.setContentsMargins(0, 8, 0, 0)

        desc = QLabel(
            "Firmangiz nomini (do'kon yaratilganda tanlangan manzil qismi, "
            "masalan \"birzumda\") va ERP'da (Hodimlar > Yangi hodim "
            "qo'shish > \"Desktop Agent\") yaratilgan login/parolni "
            "kiriting. (Test/lokal server — IP yoki localhost — uchun "
            "\"<firma nomi>@<manzil>\" formatida kiriting, masalan "
            "birzumda@http://127.0.0.1:8000.)"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#666;")
        manual_layout.addWidget(desc)

        manual_layout.addWidget(QLabel("Firma nomi"))
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("masalan: birzumda")
        manual_layout.addWidget(self.server_input)

        manual_layout.addWidget(QLabel("Stansiya logini"))
        self.username_input = QLineEdit()
        manual_layout.addWidget(self.username_input)

        manual_layout.addWidget(QLabel("Parol"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        manual_layout.addWidget(self.password_input)

        login_btn_row = QHBoxLayout()
        self.login_btn = QPushButton("Kirish")
        self.login_btn.clicked.connect(self._login)
        login_btn_row.addWidget(self.login_btn)
        login_btn_row.addStretch(1)
        manual_layout.addLayout(login_btn_row)

        self.manual_login_container.setVisible(False)
        layout.addWidget(self.manual_login_container)

        sync_row = QHBoxLayout()
        self.sync_btn = QPushButton("Sinxronlash")
        self.sync_btn.clicked.connect(self._sync)
        sync_row.addWidget(self.sync_btn)
        sync_row.addStretch(1)
        # Faqat login qilingan holatda ko'rinadi (`_show_synced_view`/
        # `show_login_required` shu ko'rinishni boshqaradi) — stansiyani
        # boshqa xodim/firma uchun qayta ishlatish uchun.
        self.logout_btn = QPushButton("🚪 Chiqish")
        self.logout_btn.setStyleSheet("color:#b91c1c;")
        self.logout_btn.clicked.connect(self._logout)
        self.logout_btn.setVisible(False)
        sync_row.addWidget(self.logout_btn)
        layout.addLayout(sync_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        scanner_title = QLabel("Skaner")
        scanner_title.setStyleSheet("font-size:16px; font-weight:700; margin-top:20px;")
        layout.addWidget(scanner_title)

        scanner_desc = QLabel(
            "Xodim shaxsiy QR (badge)ini ko'rsatishi uchun ishlatiladigan "
            "kamera yoki qo'lda (pistolet shaklidagi) USB skaner. Sozlangach, "
            "dastur ochiq turgan davomida hech qanday menyu ochmasdan — hatto "
            "boshqa oyna (masalan brauzer) fokusda bo'lsa ham — istalgan payt "
            "skanerlansa, ma'lumot avtomatik chiqadi."
        )
        scanner_desc.setWordWrap(True)
        scanner_desc.setStyleSheet("color:#666;")
        layout.addWidget(scanner_desc)

        self.scanner_status_label = QLabel("")
        self.scanner_status_label.setStyleSheet("font-weight:600;")
        layout.addWidget(self.scanner_status_label)

        scanner_configure_btn = QPushButton("Skanerni sozlash")
        scanner_configure_btn.clicked.connect(self._configure_scanner)
        layout.addWidget(scanner_configure_btn)

        # ── Tarozi (CAS CI-200A va shu formatga mos boshqalar, RS232) ────
        scale_title = QLabel("Tarozi")
        scale_title.setStyleSheet("font-size:16px; font-weight:700; margin-top:20px;")
        layout.addWidget(scale_title)

        scale_desc = QLabel(
            "Xom ashyo tortilganda tarozi qiymati avtomatik to'ldirilishi "
            "uchun — tarozi ulangan COM portni kiriting (masalan COM4). "
            "Bo'sh qoldirilsa, vaznni qo'lda kiritish davom etadi."
        )
        scale_desc.setWordWrap(True)
        scale_desc.setStyleSheet("color:#666;")
        layout.addWidget(scale_desc)

        scale_row = QHBoxLayout()
        self.scale_com_combo = QComboBox()
        self.scale_refresh_btn = QPushButton("Yangilash")
        self.scale_refresh_btn.clicked.connect(self._refresh_scale_ports)
        self.scale_save_btn = QPushButton("Saqlash")
        self.scale_save_btn.clicked.connect(self._save_scale_settings)
        scale_row.addWidget(self.scale_com_combo, 1)
        scale_row.addWidget(self.scale_refresh_btn)
        scale_row.addWidget(self.scale_save_btn)
        layout.addLayout(scale_row)

        scale_capacity_desc = QLabel(
            "Tarozining maksimal sig'imi (kg) — tarozilar turlicha bo'ladi "
            "(20/30/60 kg va h.k.). Kerakli xom ashyo miqdori shu sig'imdan "
            "oshsa, tortish avtomatik bir necha ketma-ket porsiyaga "
            "bo'linadi (masalan 45 kg, 30 kg sig'imli tarozida — avval 30 "
            "kg, keyin 15 kg). Bo'sh qoldirilsa, cheklovsiz (bitta "
            "tortishda) so'raladi."
        )
        scale_capacity_desc.setWordWrap(True)
        scale_capacity_desc.setStyleSheet("color:#666; margin-top:8px;")
        layout.addWidget(scale_capacity_desc)

        scale_capacity_row = QHBoxLayout()
        self.scale_capacity_input = QLineEdit()
        self.scale_capacity_input.setPlaceholderText("Masalan: 30")
        self.scale_capacity_save_btn = QPushButton("Saqlash")
        self.scale_capacity_save_btn.clicked.connect(self._save_scale_capacity)
        scale_capacity_row.addWidget(self.scale_capacity_input, 1)
        scale_capacity_row.addWidget(self.scale_capacity_save_btn)
        layout.addLayout(scale_capacity_row)

        # ── Etiketka printeri (XPrinter XP-365B va h.k. — TSPL) ──────────
        printer_title = QLabel("Etiketka printeri (QR chop etish)")
        printer_title.setStyleSheet("font-size:16px; font-weight:700; margin-top:20px;")
        layout.addWidget(printer_title)

        printer_desc = QLabel(
            "Miqdor qo'shish tasdiqlangach chop etiladigan Serial QR "
            "yorliqlari uchun (masalan XPrinter XP-365B). Windows'ga "
            "o'rnatilgan printerlardan birini tanlang. Kenglik/balandlik/"
            "oralig'ini QO'LLANILAYOTGAN plyonka (etiketka) o'lchamiga "
            "moslab kiriting — plyonka boshqa o'lchamga almashtirilsa, "
            "shu yerda qiymatlarni yangilash kifoya, kod o'zgartirish "
            "kerak emas."
        )
        printer_desc.setWordWrap(True)
        printer_desc.setStyleSheet("color:#666;")
        layout.addWidget(printer_desc)

        printer_row = QHBoxLayout()
        self.printer_combo = QComboBox()
        self.printer_refresh_btn = QPushButton("Yangilash")
        self.printer_refresh_btn.clicked.connect(self._refresh_printers)
        printer_row.addWidget(self.printer_combo, 1)
        printer_row.addWidget(self.printer_refresh_btn)
        layout.addLayout(printer_row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Kenglik (mm)"))
        self.label_width_input = QLineEdit()
        self.label_width_input.setPlaceholderText("40")
        size_row.addWidget(self.label_width_input)
        size_row.addWidget(QLabel("Balandlik (mm)"))
        self.label_height_input = QLineEdit()
        self.label_height_input.setPlaceholderText("30")
        size_row.addWidget(self.label_height_input)
        size_row.addWidget(QLabel("Oraliq (mm)"))
        self.label_gap_input = QLineEdit()
        self.label_gap_input.setPlaceholderText("2")
        size_row.addWidget(self.label_gap_input)
        layout.addLayout(size_row)

        printer_btn_row = QHBoxLayout()
        self.printer_save_btn = QPushButton("Saqlash")
        self.printer_save_btn.clicked.connect(self._save_printer_settings)
        self.printer_test_btn = QPushButton("Sinov chop etish")
        self.printer_test_btn.clicked.connect(self._test_print)
        printer_btn_row.addWidget(self.printer_save_btn)
        printer_btn_row.addWidget(self.printer_test_btn)
        printer_btn_row.addStretch(1)
        layout.addLayout(printer_btn_row)

        self.printer_status_label = QLabel("")
        layout.addWidget(self.printer_status_label)

        self._print_worker: LabelPrintWorker | None = None

        layout.addStretch(1)
        self._load()
        self._refresh_scanner_status()
        self._refresh_printers()
        self._load_printer_settings()
        self._refresh_scale_ports()
        self._load_scale_capacity()

    def _load(self):
        self.server_input.setText(db.get_setting("server_input_raw", "") or db.get_setting("server_url", ""))
        self.username_input.setText(db.get_setting("station_username", ""))
        station_name = db.get_setting("station_name", "")
        company_name = db.get_setting("company_name", "")
        if db.get_setting("agent_token", "") and station_name:
            self.status_label.setStyleSheet("color:#059669;")
            self.status_label.setText(f"Kirilgan: {station_name} ({company_name})")
        self._update_login_ui_state()

    def _toggle_manual_login(self):
        visible = not self.manual_login_container.isVisible()
        self.manual_login_container.setVisible(visible)
        self.manual_toggle_btn.setText(
            "Qo'lda kirishni yopish" if visible else "Qo'lda login/parol bilan kirish"
        )

    def _update_login_ui_state(self):
        """QR kod — standart usul. Stansiya login qilingan bo'lsa, QR
        taklifi va qo'lda kirish bo'limi butunlay yashiriladi (endi
        kerak emas); login qilinmagan bo'lsa — QR taklifi ko'rinadi,
        qo'lda kirish esa ixtiyoriy (yig'ilgan) holatda qoladi."""
        logged_in = bool(db.get_setting("agent_token", ""))
        self.qr_prompt_label.setVisible(not logged_in)
        self.manual_toggle_btn.setVisible(not logged_in)
        self.logout_btn.setVisible(logged_in)
        if logged_in:
            self.manual_login_container.setVisible(False)
            self.manual_toggle_btn.setText("Qo'lda login/parol bilan kirish")

    def _start_connecting_animation(self, base_text: str):
        """Server bilan aloqa boshlanganda (qo'lda yoki QR orqali login,
        sinxronlash) chaqiriladi — foydalanuvchi hech narsa osilib
        qolmaganini ko'rishi uchun "Ulanmoqda..." matni nuqtalar bilan
        animatsiya qilinadi, javob kelguncha (muvaffaqiyat/xato) davom
        etadi."""
        self._connecting_base_text = base_text
        self._connecting_dots = 0
        self.status_label.setStyleSheet("color:#666;")
        self.status_label.setText(base_text)
        self._connecting_timer.start()

    def _tick_connecting_animation(self):
        self._connecting_dots = (self._connecting_dots + 1) % 4
        self.status_label.setText(self._connecting_base_text + "." * self._connecting_dots)

    def _stop_connecting_animation(self):
        self._connecting_timer.stop()

    def start_qr_login(self, subdomain: str, qr_payload: str, server_url: str):
        """`MainWindow`dagi global skaner `AGENTQR|...` kodini aniqlaganda
        chaqiradi — natija xuddi qo'lda login (`_on_login_succeeded`/
        `_on_login_failed`) bilan bir xil ishlov beriladi, shuning uchun
        UI holati (status_label, keyingi qadamlar) farqsiz yangilanadi."""
        db.set_setting("server_url", server_url)
        self._start_connecting_animation("QR kod orqali kirilmoqda")
        self._login_worker = _ApiCallWorker(station_login_by_qr, server_url, subdomain, qr_payload)
        self._login_worker.succeeded.connect(self._on_login_succeeded)
        self._login_worker.failed.connect(self._on_login_failed)
        self._login_worker.start()

    def _login(self):
        raw_input = self.server_input.text().strip()
        server_url, subdomain = parse_server_input(raw_input)
        username = self.username_input.text().strip()
        password = self.password_input.text()

        db.set_setting("server_input_raw", raw_input)
        db.set_setting("server_url", server_url)
        db.set_setting("station_username", username)

        self.login_btn.setEnabled(False)
        self._start_connecting_animation("Kirilmoqda")

        self._login_worker = _ApiCallWorker(station_login, server_url, subdomain, username, password)
        self._login_worker.succeeded.connect(self._on_login_succeeded)
        self._login_worker.failed.connect(self._on_login_failed)
        self._login_worker.start()

    def _on_login_succeeded(self, result: dict):
        self._stop_connecting_animation()
        self.login_btn.setEnabled(True)
        db.set_setting("agent_token", result["token"])
        db.set_setting("station_name", result["station_name"])
        db.set_setting("company_name", result["company"])
        self.password_input.clear()

        self.status_label.setStyleSheet("color:#059669;")
        self.status_label.setText(f"Kirildi: {result['station_name']} ({result['company']})")
        self._update_login_ui_state()

        if self.on_login_succeeded:
            self.on_login_succeeded()

    def _on_login_failed(self, message: str):
        self._stop_connecting_animation()
        self.login_btn.setEnabled(True)
        self.status_label.setStyleSheet("color:#b91c1c;")
        self.status_label.setText(message)

    def show_login_required(self):
        """Boshqa kompyuterda qayta login qilingani uchun bu stansiya
        tokeni serverda bekor qilingach (`MainWindow._handle_token_invalid`)
        chaqiriladi — foydalanuvchiga qaytadan kirish kerakligini
        ko'rsatadi, parol maydonini tozalaydi."""
        self.password_input.clear()
        self.status_label.setStyleSheet("color:#b91c1c;")
        self.status_label.setText("Sessiya yopildi — qaytadan kiring.")
        self._update_login_ui_state()

    def _logout(self):
        """Foydalanuvchi o'zi "Chiqish"ni bosganda — stansiya boshqa
        xodim/firma uchun qayta ishlatilishi kerak bo'lganda (masalan
        smena almashinuvi). Serverga "oflayn" xabari best-effort
        yuboriladi (`send_logout`) — natijasidan qat'i nazar mahalliy
        token darhol tozalanadi, chunki xodim uchun asosiysi shu
        qurilmada endi hech kim uning nomidan ish qila olmasligi."""
        if not db.get_setting("agent_token", ""):
            return
        reply = QMessageBox.question(
            self, "Chiqish",
            "Rostdan ham tizimdan chiqmoqchimisiz? Keyingi ishlatishda "
            "qaytadan login qilish kerak bo'ladi.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        self.logout_btn.setEnabled(False)
        worker = _ApiCallWorker(send_logout, server_url, token)
        worker.succeeded.connect(self._on_logout_finished)
        worker.failed.connect(lambda _msg: self._on_logout_finished(None))
        self._logout_worker = worker
        worker.start()

    def _on_logout_finished(self, _result):
        self.logout_btn.setEnabled(True)
        db.set_setting("agent_token", "")
        db.set_setting("station_name", "")
        db.set_setting("company_name", "")
        if self.on_logout:
            self.on_logout()
        self.status_label.setStyleSheet("color:#666;")
        self.status_label.setText("Tizimdan chiqdingiz.")
        self._update_login_ui_state()

    def _sync(self):
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        if not token:
            self.status_label.setStyleSheet("color:#b91c1c;")
            self.status_label.setText("Avval login/parol bilan kiring.")
            return

        self.sync_btn.setEnabled(False)
        self.status_label.setStyleSheet("color:#666;")
        self.status_label.setText("Sinxronlanmoqda...")

        self._sync_worker = _ApiCallWorker(fetch_omborlar, server_url, token)
        self._sync_worker.succeeded.connect(self._on_sync_succeeded)
        self._sync_worker.failed.connect(self._on_sync_failed)
        self._sync_worker.token_invalid.connect(self.session_expired.emit)
        self._sync_worker.start()

    def _on_sync_succeeded(self, result: tuple):
        self.sync_btn.setEnabled(True)
        omborlar, company_name = result
        db.sync_warehouses_from_remote(omborlar)
        self.status_label.setStyleSheet("color:#059669;")
        self.status_label.setText(f"'{company_name}' — {len(omborlar)} ta ombor sinxronlandi.")
        if self.on_synced:
            self.on_synced()

    def _on_sync_failed(self, message: str):
        self.sync_btn.setEnabled(True)
        self.status_label.setStyleSheet("color:#b91c1c;")
        self.status_label.setText(message)

    def _refresh_scanner_status(self):
        cam = db.get_scanner_camera()
        if cam is None:
            self.scanner_status_label.setText("Holat: skaner hali sozlanmagan")
        elif cam.connection_type == "usb":
            self.scanner_status_label.setText(f"Holat: USB Kamera #{cam.usb_index} biriktirilgan")
        elif cam.connection_type == "hid":
            self.scanner_status_label.setText("Holat: Qo'lda skaner (USB, klaviatura kabi) biriktirilgan")
        else:
            self.scanner_status_label.setText(f"Holat: RTSP ({cam.rtsp_url}) biriktirilgan")

    def _configure_scanner(self):
        dialog = CameraConfigDialog(role="skaner", warehouse_id=None,
                                     title="Skanerni sozlash", parent=self)
        if dialog.exec():
            self._refresh_scanner_status()
            if self.on_scanner_changed:
                self.on_scanner_changed()

    # ── Tarozi ────────────────────────────────────────────────────────

    def _refresh_scale_ports(self):
        import serial.tools.list_ports

        current = self.scale_com_combo.currentText()
        self.scale_com_combo.clear()
        self.scale_com_combo.addItem("(tanlanmagan)", "")
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for port in ports:
            self.scale_com_combo.addItem(port, port)

        saved = db.get_setting("scale_com_port", "")
        target = current if current and current != "(tanlanmagan)" else saved
        if target:
            idx = self.scale_com_combo.findData(target)
            if idx >= 0:
                self.scale_com_combo.setCurrentIndex(idx)

    def _save_scale_settings(self):
        db.set_setting("scale_com_port", self.scale_com_combo.currentData() or "")
        if self.on_scale_changed:
            self.on_scale_changed()

    def _load_scale_capacity(self):
        self.scale_capacity_input.setText(db.get_setting("scale_max_capacity_kg", ""))

    def _save_scale_capacity(self):
        raw = self.scale_capacity_input.text().strip().replace(",", ".")
        if raw:
            try:
                value = float(raw)
                if value <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "Xato", "Sig'im musbat son bo'lishi kerak (masalan 30).")
                return
            db.set_setting("scale_max_capacity_kg", str(value))
        else:
            db.set_setting("scale_max_capacity_kg", "")
        if self.on_scale_changed:
            self.on_scale_changed()

    # ── Etiketka printeri ─────────────────────────────────────────────

    def _refresh_printers(self):
        current = self.printer_combo.currentText()
        self.printer_combo.clear()
        try:
            names = list_printers()
        except Exception as exc:  # noqa: BLE001 — Windows printer subsystem xatosi bo'lsa ham sahifa ochilaveradi
            self.printer_status_label.setStyleSheet("color:#b91c1c;")
            self.printer_status_label.setText(f"Printerlar ro'yxatini olishda xato: {exc}")
            return
        self.printer_combo.addItems(names)
        saved = db.get_setting("label_printer_name", "")
        target = saved if saved in names else current
        if target:
            index = self.printer_combo.findText(target)
            if index >= 0:
                self.printer_combo.setCurrentIndex(index)

    def _load_printer_settings(self):
        self.label_width_input.setText(db.get_setting("label_width_mm", "40"))
        self.label_height_input.setText(db.get_setting("label_height_mm", "30"))
        self.label_gap_input.setText(db.get_setting("label_gap_mm", "2"))

    def _read_label_size(self):
        try:
            width = float(self.label_width_input.text().strip().replace(",", "."))
            height = float(self.label_height_input.text().strip().replace(",", "."))
            gap = float(self.label_gap_input.text().strip().replace(",", "."))
        except ValueError:
            return None
        if width <= 0 or height <= 0 or gap < 0:
            return None
        return width, height, gap

    def _save_printer_settings(self):
        printer_name = self.printer_combo.currentText().strip()
        if not printer_name:
            self.printer_status_label.setStyleSheet("color:#b91c1c;")
            self.printer_status_label.setText("Avval printer tanlang.")
            return
        size = self._read_label_size()
        if size is None:
            self.printer_status_label.setStyleSheet("color:#b91c1c;")
            self.printer_status_label.setText("Kenglik/balandlik/oraliq son bo'lishi kerak.")
            return
        width, height, gap = size

        db.set_setting("label_printer_name", printer_name)
        db.set_setting("label_width_mm", f"{width:g}")
        db.set_setting("label_height_mm", f"{height:g}")
        db.set_setting("label_gap_mm", f"{gap:g}")
        self.printer_status_label.setStyleSheet("color:#059669;")
        self.printer_status_label.setText(f"Saqlandi: {printer_name} ({width:g}x{height:g} mm, oraliq {gap:g} mm)")

    def _test_print(self):
        printer_name = self.printer_combo.currentText().strip()
        if not printer_name:
            self.printer_status_label.setStyleSheet("color:#b91c1c;")
            self.printer_status_label.setText("Avval printer tanlang.")
            return
        size = self._read_label_size()
        if size is None:
            self.printer_status_label.setStyleSheet("color:#b91c1c;")
            self.printer_status_label.setText("Kenglik/balandlik/oraliq son bo'lishi kerak.")
            return
        width, height, gap = size

        self.printer_test_btn.setEnabled(False)
        self.printer_status_label.setStyleSheet("color:#666;")
        self.printer_status_label.setText("Sinov etiketkasi chop etilmoqda...")

        label = {"qr_data": "https://stockfirm.uz/p/test/"}
        self._print_worker = LabelPrintWorker(printer_name, [label], width, height, gap)
        self._print_worker.succeeded.connect(self._on_test_print_succeeded)
        self._print_worker.failed.connect(self._on_test_print_failed)
        self._print_worker.start()

    def _on_test_print_succeeded(self, count: int):
        self.printer_test_btn.setEnabled(True)
        self.printer_status_label.setStyleSheet("color:#059669;")
        self.printer_status_label.setText("Sinov etiketkasi printerga yuborildi ✓")

    def _on_test_print_failed(self, message: str):
        self.printer_test_btn.setEnabled(True)
        self.printer_status_label.setStyleSheet("color:#b91c1c;")
        self.printer_status_label.setText(message)
