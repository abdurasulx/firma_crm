from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox,
)
from PyQt6.QtCore import QThread, QTimer, pyqtSignal

from .. import db
from ..api_client import fetch_omborlar, ApiError
from .warehouse_cameras_dialog import WarehouseCamerasDialog

RECONNECT_RETRY_MS = 5000


class _SyncWorker(QThread):
    """Omborlar ro'yxatini serverdan fon oqimida oladi — asosiy oqimda
    to'g'ridan-to'g'ri chaqirilsa, server sekin javob bersa yoki umuman
    ulanmasa, butun ilova muzlab qolardi (xuddi 68-qadamda tuzatilgan
    skanerlash muammosi kabi)."""
    succeeded = pyqtSignal(list, str, bool)
    failed = pyqtSignal(str)

    def __init__(self, server_url: str, token: str):
        super().__init__()
        self._server_url = server_url
        self._token = token
        # Eski worker obyekti tezda yangisi bilan almashtirilganda GC uni
        # C++ oqimi hali to'liq join bo'lmasdan o'chirib yubormasligi uchun.
        self.finished.connect(self.wait)

    def run(self):
        try:
            omborlar, company_name, tarozi_majburiy = fetch_omborlar(self._server_url, self._token)
        except ApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 — kutilmagan xato butun ilovani yiqitmasin
            self.failed.emit(f"Kutilmagan xato: {exc}")
        else:
            self.succeeded.emit(omborlar, company_name, bool(tarozi_majburiy))


class WarehouseListPage(QWidget):
    """Omborlar ro'yxati — qo'lda "Sinxronlash" tugmasi endi yo'q (91-qadam).
    Dasturga kirishi bilan avtomatik ravishda: (1) mahalliy keshdagi
    ro'yxat darhol ko'rsatiladi, (2) fonda serverdan yangilanadi ("Tekshirilmoqda..."
    ko'rinishi bilan). Shundan keyin har safar serverda biror narsa
    o'zgarganda (`MainWindow`ning WebSocket xizmati orqali, real-vaqtda)
    yana avtomatik qayta tekshiriladi va faqat HAQIQIY o'zgarish bo'lsagina
    jadval yangilanadi (keraksiz miltillashning oldini olish uchun). Bu
    yerda yangi ombor yaratish/tahrirlash yo'q — ombor nomi/manzili ERP
    tomonida boshqariladi, mahalliy dastur faqat har bir ombor uchun
    kamera(lar)ni biriktiradi."""

    def __init__(self, on_cameras_changed=None, parent=None):
        super().__init__(parent)
        self._sync_worker: _SyncWorker | None = None
        self._on_cameras_changed = on_cameras_changed

        # "Ulanmoqda.../Qayta ulanmoqda..." animatsiyasi (`settings_page.py`dagi
        # bilan bir xil naqsh) — foydalanuvchi so'ragan: server bilan
        # aloqa yo'q bo'lganda o'lik xato matni o'rniga, tizim jonli
        # ko'rinib, o'zi qayta-qayta urinib tursin.
        self._connecting_timer = QTimer(self)
        self._connecting_timer.setInterval(400)
        self._connecting_timer.timeout.connect(self._tick_connecting_animation)
        self._connecting_dots = 0
        self._connecting_base_text = ""
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(lambda: self.sync_from_server(silent=False))

        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        title = QLabel("Omborlar")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        header_row.addWidget(title)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color:#666; margin-bottom:6px;")
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nomi", "Manzil", "Kameralar", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self.empty_label = QLabel(
            "Hali hech qanday ombor topilmadi. Avval Sozlamalar sahifasida "
            "login qiling — omborlar avtomatik yuklanadi."
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet(
            "color:#64748b; font-size:13px; padding:24px; background:#f8fafc; "
            "border-radius:10px; margin-top:8px;"
        )
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        # 1) Mahalliy keshdagi ro'yxat darhol ko'rinadi (agar bo'lsa).
        self.refresh()
        # 2) Fonda darhol serverdan yangilanadi — "loading preview".
        self.sync_from_server(silent=False)

    def refresh(self):
        warehouses = db.list_warehouses()
        self.table.setRowCount(len(warehouses))
        self.table.setVisible(bool(warehouses))
        self.empty_label.setVisible(not warehouses)
        for row, wh in enumerate(warehouses):
            nomi_display = f"{wh.nomi}  [ERP]" if wh.remote_id else wh.nomi
            self.table.setItem(row, 0, QTableWidgetItem(nomi_display))
            self.table.setItem(row, 1, QTableWidgetItem(wh.manzil))

            cameras = db.list_cameras_for_warehouse(wh.id)
            if not cameras:
                status = "Kamera ulanmagan"
            else:
                usb_count = sum(1 for c in cameras if c.connection_type == "usb")
                rtsp_count = sum(1 for c in cameras if c.connection_type == "rtsp")
                parts = []
                if usb_count:
                    parts.append(f"{usb_count} USB")
                if rtsp_count:
                    parts.append(f"{rtsp_count} RTSP")
                status = ", ".join(parts)
            self.table.setItem(row, 2, QTableWidgetItem(status))

            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            cam_btn = QPushButton("Kameralar")
            cam_btn.clicked.connect(lambda _, w=wh: self._manage_cameras(w))
            actions_layout.addWidget(cam_btn)

            delete_btn = QPushButton("O'chirish")
            delete_btn.clicked.connect(lambda _, w=wh: self._delete_warehouse(w))
            actions_layout.addWidget(delete_btn)

            self.table.setCellWidget(row, 3, actions)

    def _delete_warehouse(self, warehouse: db.Warehouse):
        confirm = QMessageBox.question(
            self, "Tasdiqlash",
            f"'{warehouse.nomi}' omborini o'chirmoqchimisiz? Unga bog'langan barcha kameralar ham o'chadi.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            db.delete_warehouse(warehouse.id)
            self.refresh()
            if self._on_cameras_changed:
                self._on_cameras_changed()  # ombor bilan birga uning kameralari ham o'chdi

    def _manage_cameras(self, warehouse: db.Warehouse):
        dialog = WarehouseCamerasDialog(warehouse, parent=self)
        dialog.exec()
        self.refresh()
        if self._on_cameras_changed:
            self._on_cameras_changed()

    def sync_from_server(self, silent: bool = True):
        """Omborlar ro'yxatini serverdan qayta tekshiradi. Qo'lda tugma
        endi yo'q — bu (a) sahifa ochilganda avtomatik, va (b) `MainWindow`
        WebSocket orqali `event='ombor_changed'` xabarini olganda
        chaqiriladi. `silent=True` bo'lsa (WS orqali chaqirilganda) hech
        qanday "Tekshirilmoqda..." matni ko'rsatilmaydi — foydalanuvchi
        buni sezmasligi kerak, faqat haqiqiy o'zgarish bo'lsa jadval
        jimgina yangilanadi."""
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        if not token:
            return  # hali login qilinmagan — urinishning ma'nosi yo'q

        if not silent:
            self._start_connecting_animation("Tekshirilmoqda")

        old = self._sync_worker
        if old is not None and old.isRunning():
            old.wait()
        self._sync_worker = _SyncWorker(server_url, token)
        self._sync_worker.succeeded.connect(
            lambda omborlar, name, tarozi_majburiy: self._on_sync_succeeded(omborlar, name, tarozi_majburiy, silent),
        )
        self._sync_worker.failed.connect(lambda msg: self._on_sync_failed(msg, silent))
        self._sync_worker.start()

    def _on_sync_succeeded(self, omborlar: list, company_name: str, tarozi_majburiy: bool, silent: bool):
        before = {(w.remote_id, w.nomi, w.manzil) for w in db.list_warehouses()}
        db.sync_warehouses_from_remote(omborlar)
        db.set_setting("tarozi_majburiy", "1" if tarozi_majburiy else "")
        after = {(w.remote_id, w.nomi, w.manzil) for w in db.list_warehouses()}

        if before != after:
            self.refresh()

        if not silent:
            self._stop_connecting_animation()
            self._reconnect_timer.stop()
            self.status_label.setStyleSheet("color:#059669;")
            self.status_label.setText(f"'{company_name}' — {len(omborlar)} ta ombor.")

    def _on_sync_failed(self, message: str, silent: bool):
        if silent:
            return  # fon rejimidagi tekshiruv — xatoni ko'rsatib, foydalanuvchini bezovta qilmaymiz
        # O'lik xato matni o'rniga — animatsiyali "qayta ulanmoqda" holati,
        # va `RECONNECT_RETRY_MS`dan keyin avtomatik qayta urinish
        # (muvaffaqiyatli bo'lguncha yoki sahifa yopilguncha davom etadi) —
        # kiosk hech qachon o'lik xato bilan abadiy osilib qolmasligi kerak.
        self._start_connecting_animation(f"⚠ {message} — qayta ulanmoqda")
        self._reconnect_timer.start(RECONNECT_RETRY_MS)

    def _start_connecting_animation(self, base_text: str):
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
