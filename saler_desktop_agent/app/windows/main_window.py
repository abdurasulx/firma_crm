"""Saler Agent — asosiy oyna: login, xodim (savdogar) identifikatsiyasi
(badge skanerlash), shtrix-kod orqali savat va sotuvni yakunlash.

Bu dastur ombor/ishlab chiqarish/tarozi/kamera bilan ISHLAMAYDI — faqat
sotuv uchun (foydalanuvchi talabi: "savdo agenti omborni oldida ishlaydi,
unga yuklama va boshqa narsalar kerak emas"). `desktop_agent/`ga
tegilmagan, mustaqil dastur."""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal

from .. import db
from ..api_client import (
    ApiError, station_login, scan_badge, lookup_mahsulot, finalize_sale,
    send_heartbeat, send_logout, parse_server_input,
)

HEARTBEAT_INTERVAL_MS = 25_000


class _ApiCallWorker(QThread):
    """Har qanday tarmoq chaqiruvini fon oqimida bajaradi — asosiy oqimda
    to'g'ridan-to'g'ri chaqirilsa, server sekin javob bersa butun dastur
    muzlab qolardi."""
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self.finished.connect(self.wait)

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
        except ApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 — kutilmagan xato dasturni yiqitmasin
            self.failed.emit(f"Kutilmagan xato: {exc}")
        else:
            self.succeeded.emit(result)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StockFirm — Saler Agent")
        self.resize(900, 640)

        self._cart: dict[int, dict] = {}  # mahsulot_id -> {nomi, narxi, miqdor, birlik}
        self._session_token: str | None = None
        self._savdogar_name: str | None = None
        self._workers: list[QThread] = []

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self._build_login_page()
        self._build_sale_page()

        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        if server_url and token:
            self.server_url = server_url
            self.token = token
            self.stack.setCurrentIndex(1)
            self._start_heartbeat()
        else:
            self.server_url = ""
            self.token = ""
            self.stack.setCurrentIndex(0)

    # ── Login sahifasi ────────────────────────────────────────────────

    def _build_login_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(80, 80, 80, 80)
        layout.setSpacing(14)

        title = QLabel("Saler Agent — Stansiya login")
        title.setStyleSheet("font-size:20px; font-weight:800;")
        layout.addWidget(title)

        self.firma_input = QLineEdit()
        self.firma_input.setPlaceholderText("Firma nomi (masalan: safiya)")
        layout.addWidget(self.firma_input)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Login")
        layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Parol")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._do_login)
        layout.addWidget(self.password_input)

        self.login_btn = QPushButton("Kirish")
        self.login_btn.clicked.connect(self._do_login)
        layout.addWidget(self.login_btn)

        self.login_status = QLabel("")
        self.login_status.setWordWrap(True)
        self.login_status.setStyleSheet("color:#b91c1c; font-weight:700;")
        layout.addWidget(self.login_status)

        layout.addStretch(1)
        self.stack.addWidget(page)  # index 0

    def _do_login(self):
        server_url, subdomain = parse_server_input(self.firma_input.text())
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            self.login_status.setText("Login va parolni kiriting.")
            return
        self.login_btn.setEnabled(False)
        self.login_status.setStyleSheet("color:#64748b; font-weight:700;")
        self.login_status.setText("Kirilmoqda...")
        worker = _ApiCallWorker(station_login, server_url, subdomain, username, password)
        worker.succeeded.connect(lambda result: self._on_login_succeeded(result, server_url))
        worker.failed.connect(self._on_login_failed)
        self._workers.append(worker)
        worker.start()

    def _on_login_succeeded(self, result: dict, server_url: str):
        self.login_btn.setEnabled(True)
        token = result.get("token")
        if not token:
            self.login_status.setText("Server javobida token topilmadi.")
            return
        self.server_url = server_url
        self.token = token
        db.set_setting("server_url", server_url)
        db.set_setting("agent_token", token)
        self.password_input.clear()
        self.login_status.setText("")
        self.stack.setCurrentIndex(1)
        self._start_heartbeat()

    def _on_login_failed(self, message: str):
        self.login_btn.setEnabled(True)
        self.login_status.setStyleSheet("color:#b91c1c; font-weight:700;")
        self.login_status.setText(message)

    # ── Sotuv sahifasi ───────────────────────────────────────────────

    def _build_sale_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        self.employee_label = QLabel("Xodim badge'ini skanerlang — ish sessiyasi hali boshlanmagan.")
        self.employee_label.setStyleSheet("font-size:15px; font-weight:800;")
        header_row.addWidget(self.employee_label, 1)
        self.logout_btn = QPushButton("Stansiyadan chiqish")
        self.logout_btn.clicked.connect(self._station_logout)
        header_row.addWidget(self.logout_btn)
        layout.addLayout(header_row)

        self.badge_input = QLineEdit()
        self.badge_input.setPlaceholderText("Xodim badge'ini shu yerga skanerlang...")
        self.badge_input.returnPressed.connect(self._handle_badge_scan)
        layout.addWidget(self.badge_input)

        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Mahsulot shtrix-kodini skanerlang...")
        self.barcode_input.setEnabled(False)
        self.barcode_input.returnPressed.connect(self._handle_barcode_scan)
        layout.addWidget(self.barcode_input)

        self.cart_table = QTableWidget(0, 5)
        self.cart_table.setHorizontalHeaderLabels(["Nomi", "Miqdor", "Narxi", "Summa", ""])
        self.cart_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cart_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.cart_table, 1)

        bottom_row = QHBoxLayout()
        self.customer_input = QLineEdit()
        self.customer_input.setPlaceholderText("Mijoz ismi (ixtiyoriy)")
        bottom_row.addWidget(self.customer_input, 1)

        self.pay_naqd_btn = QPushButton("Naqd")
        self.pay_naqd_btn.setCheckable(True)
        self.pay_naqd_btn.setChecked(True)
        self.pay_karta_btn = QPushButton("Karta")
        self.pay_karta_btn.setCheckable(True)
        self.pay_naqd_btn.clicked.connect(lambda: self._set_pay_type("naqd"))
        self.pay_karta_btn.clicked.connect(lambda: self._set_pay_type("karta"))
        bottom_row.addWidget(self.pay_naqd_btn)
        bottom_row.addWidget(self.pay_karta_btn)
        layout.addLayout(bottom_row)

        self._pay_type = "naqd"

        finish_row = QHBoxLayout()
        self.total_label = QLabel("Umumiy: 0 so'm")
        self.total_label.setStyleSheet("font-size:18px; font-weight:800;")
        finish_row.addWidget(self.total_label, 1)
        self.finish_btn = QPushButton("Sotuvni yakunlash")
        self.finish_btn.setStyleSheet(
            "background:#10b981; color:white; font-weight:800; padding:10px 18px; border-radius:8px; border:none;"
        )
        self.finish_btn.setEnabled(False)
        self.finish_btn.clicked.connect(self._finalize_sale)
        finish_row.addWidget(self.finish_btn)
        layout.addLayout(finish_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.stack.addWidget(page)  # index 1
        self._set_session_active(False)

    def _set_pay_type(self, val: str):
        self._pay_type = val
        self.pay_naqd_btn.setChecked(val == "naqd")
        self.pay_karta_btn.setChecked(val == "karta")

    def _start_heartbeat(self):
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(HEARTBEAT_INTERVAL_MS)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._heartbeat_timer.start()
        self._send_heartbeat()

    def _send_heartbeat(self):
        worker = _ApiCallWorker(send_heartbeat, self.server_url, self.token)
        self._workers.append(worker)
        worker.start()

    # ── Xodim (savdogar) identifikatsiyasi ──────────────────────────

    def _handle_badge_scan(self):
        kod = self.badge_input.text().strip()
        self.badge_input.clear()
        if not kod:
            return
        self.status_label.setText("Tekshirilmoqda...")
        worker = _ApiCallWorker(scan_badge, self.server_url, self.token, kod)
        worker.succeeded.connect(self._on_badge_resolved)
        worker.failed.connect(lambda msg: self.status_label.setText(f"✗ {msg}"))
        self._workers.append(worker)
        worker.start()

    def _on_badge_resolved(self, info: dict):
        if info.get("user_type") != "savdogar":
            self.status_label.setText(
                f"✗ {info.get('tuliq_ismi', '')} — savdogar emas ({info.get('lavozim', '')})."
            )
            return
        if not info.get("is_active", True):
            self.status_label.setText(f"✗ {info.get('tuliq_ismi', '')} — hisob faol emas.")
            return
        self._session_token = info["session_token"]
        self._savdogar_name = info.get("tuliq_ismi") or info.get("username", "")
        self.status_label.setText(f"✓ Xush kelibsiz, {self._savdogar_name}!")
        self._set_session_active(True)
        self.barcode_input.setFocus()

    def _set_session_active(self, active: bool):
        self.barcode_input.setEnabled(active)
        self.finish_btn.setEnabled(active and bool(self._cart))
        if active:
            self.employee_label.setText(f"Sotuvchi: {self._savdogar_name}")
        else:
            self.employee_label.setText("Xodim badge'ini skanerlang — ish sessiyasi hali boshlanmagan.")
            self._cart.clear()
            self._refresh_cart_table()

    # ── Savat (shtrix-kod) ───────────────────────────────────────────

    def _handle_barcode_scan(self):
        kod = self.barcode_input.text().strip()
        self.barcode_input.clear()
        if not kod:
            return
        worker = _ApiCallWorker(lookup_mahsulot, self.server_url, self.token, kod)
        worker.succeeded.connect(self._on_mahsulot_found)
        worker.failed.connect(lambda msg: self.status_label.setText(f"✗ {msg}"))
        self._workers.append(worker)
        worker.start()

    def _on_mahsulot_found(self, info: dict):
        mid = info["id"]
        if mid in self._cart:
            self._cart[mid]["miqdor"] += 1
        else:
            self._cart[mid] = {
                "nomi": info["nomi"], "narxi": info["narxi"], "miqdor": 1, "birlik": info.get("birlik", ""),
            }
        self.status_label.setText(f"✓ {info['nomi']} savatga qo'shildi.")
        self._refresh_cart_table()

    def _remove_from_cart(self, mahsulot_id: int):
        self._cart.pop(mahsulot_id, None)
        self._refresh_cart_table()

    def _refresh_cart_table(self):
        self.cart_table.setRowCount(len(self._cart))
        total = 0.0
        for row, (mid, item) in enumerate(self._cart.items()):
            summa = item["miqdor"] * item["narxi"]
            total += summa
            self.cart_table.setItem(row, 0, QTableWidgetItem(item["nomi"]))
            self.cart_table.setItem(row, 1, QTableWidgetItem(f"{item['miqdor']:g} {item['birlik']}"))
            self.cart_table.setItem(row, 2, QTableWidgetItem(f"{item['narxi']:,.0f}"))
            self.cart_table.setItem(row, 3, QTableWidgetItem(f"{summa:,.0f}"))
            remove_btn = QPushButton("O'chirish")
            remove_btn.clicked.connect(lambda _, m=mid: self._remove_from_cart(m))
            self.cart_table.setCellWidget(row, 4, remove_btn)
        self.total_label.setText(f"Umumiy: {total:,.0f} so'm")
        self.finish_btn.setEnabled(bool(self._cart) and self._session_token is not None)

    # ── Sotuvni yakunlash ────────────────────────────────────────────

    def _finalize_sale(self):
        if not self._cart or not self._session_token:
            return
        items = [{"mahsulot_id": mid, "miqdor": item["miqdor"]} for mid, item in self._cart.items()]
        oluvchi = self.customer_input.text().strip() or "Mijoz"
        self.finish_btn.setEnabled(False)
        self.status_label.setText("Saqlanmoqda...")
        worker = _ApiCallWorker(
            finalize_sale, self.server_url, self.token, self._session_token, oluvchi, self._pay_type, items,
        )
        worker.succeeded.connect(self._on_sale_finalized)
        worker.failed.connect(self._on_sale_failed)
        self._workers.append(worker)
        worker.start()

    def _on_sale_finalized(self, result: dict):
        self.status_label.setText(f"✓ Sotuv saqlandi — {result.get('summa', 0):,.0f} so'm.")
        self._cart.clear()
        self.customer_input.clear()
        self._refresh_cart_table()
        self._set_pay_type("naqd")
        self.barcode_input.setFocus()

    def _on_sale_failed(self, message: str):
        self.finish_btn.setEnabled(True)
        self.status_label.setText(f"✗ {message}")

    # ── Stansiyadan chiqish ──────────────────────────────────────────

    def _station_logout(self):
        confirm = QMessageBox.question(
            self, "Chiqish", "Stansiyadan chiqmoqchimisiz? Keyingi ishlatishda qaytadan login qilish kerak bo'ladi.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        worker = _ApiCallWorker(send_logout, self.server_url, self.token)
        worker.finished.connect(lambda: None)
        self._workers.append(worker)
        worker.start()
        db.set_setting("agent_token", "")
        if hasattr(self, "_heartbeat_timer"):
            self._heartbeat_timer.stop()
        self._session_token = None
        self._savdogar_name = None
        self._set_session_active(False)
        self.stack.setCurrentIndex(0)

    def closeEvent(self, event):
        if self.token:
            worker = _ApiCallWorker(send_logout, self.server_url, self.token)
            worker.start()
            worker.wait(1500)
        super().closeEvent(event)
