"""Dastur har ishga tushganda ko'rsatiladigan qurilma-tekshiruv sahifasi.

Foydalanuvchi so'rovi bo'yicha (159-qadamdan keyin) — endi faqat DB
sozlamasi borligini emas, balki **haqiqiy jonli ulanishni** tekshiradi:
printer (Windows spooler holati), tarozi (allaqachon fonda ishlab
turgan `ScaleService`dan so'raladi), skaner kamerasi va ombor
kamera(lar)i (kadr olib ko'rish). Barcha qurilmalar chindan ham onlayn
bo'lsagina davom etish mumkin — birortasi nosoz bo'lsa, "Davom etish"
o'rniga "Sozlamalarga o'tish" ko'rsatiladi, u yerda tuzatilgach qayta
tekshirish orqali davom etiladi.

**Muhim (topilgan real bug)**: tarozi tekshiruvi avval o'zining alohida
COM-port ulanishini ochardi — lekin `ScaleService` dastur ochilgan
zahotidan (`MainWindow.__init__`) shu portni ALLAQACHON fonda ushlab
turadi. Ikkita joy bir vaqtda bitta COM portni ochishga urinsa, Windows
"Access is denied" xatosi beradi (real sinovda aynan shu aniqlandi) —
shuning uchun tekshiruv endi ALOHIDA ulanish ochmaydi, balki
`ScaleService.is_connected()` orqali MAVJUD ulanishning holatidan
so'raydi."""
import time

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import pyqtSignal, QTimer, QThread

from .. import db
from ..label_printer_service import list_printers

OK_STYLE = "color:#059669; font-weight:700;"
WARN_STYLE = "color:#b45309; font-weight:700;"
CHECKING_STYLE = "color:#64748b; font-weight:700;"

# Barcha qurilmalar muvaffaqiyatli tekshirilgach, avtomatik davom etish
# uchun qisqa kutish (odam kutib turmasa ham stansiya o'zi ishga tushadi).
AUTO_CONTINUE_SECONDS = 5

# Tarozi hali birinchi o'qishni yubormagan bo'lishi mumkin (ulanish
# yangi boshlangan) — shuncha vaqtgacha `ScaleService.is_connected()`ni
# qayta-qayta so'raymiz, keyin "javob yo'q" deb hisoblaymiz.
SCALE_PROBE_SECONDS = 3.0

# Kamera(lar) hali birinchi kadrni chiqarmagan bo'lishi mumkin (worker
# yangi boshlangan) — shuncha vaqtgacha kutib qayta so'raymiz.
CAMERA_PROBE_SECONDS = 3.0


def _check_printer_live():
    name = db.get_setting("label_printer_name", "") or ""
    if not name:
        return False, "Sozlanmagan — Sozlamalar sahifasida tanlang."
    try:
        installed = list_printers()
    except Exception:  # noqa: BLE001 — Windows printer API muammosi tekshiruvni to'xtatmasin
        installed = []
    if installed and name not in installed:
        return False, f"\"{name}\" endi Windows'da topilmadi — qayta tanlang."
    try:
        import win32print
        handle = win32print.OpenPrinter(name)
        try:
            info = win32print.GetPrinter(handle, 2)
            status = info.get("Status", 0)
            # PRINTER_STATUS_OFFLINE=0x80, PRINTER_STATUS_ERROR=0x2 — Windows
            # spooler bergan bitmask (win32print konstantalari).
            if status & 0x80:
                return False, f"\"{name}\" oflayn — kabel/quvvatni tekshiring."
            if status & 0x2:
                return False, f"\"{name}\" xato holatida."
        finally:
            win32print.ClosePrinter(handle)
    except Exception as exc:  # noqa: BLE001
        return False, f"\"{name}\" bilan bog'lanib bo'lmadi: {exc}"
    return True, f"Ulangan: {name}"


def _check_scale_live(scale_checker):
    # Firma ERP sozlamasida "tarozi shart emas" deb belgilangan bo'lsa —
    # ulanish umuman qidirilmaydi/talab qilinmaydi, startup darhol "OK"
    # deb hisoblaydi (`Company.tarozi_majburiy`, login/sinxronlashda
    # mahalliy sozlamaga yoziladi).
    if not db.get_setting("tarozi_majburiy", "1"):
        return True, "Tarozi shart emas (firma sozlamasida o'chirilgan)."
    port = (db.get_setting("scale_com_port", "") or "").strip()
    if not port:
        return False, "Sozlanmagan — Sozlamalar sahifasida COM portni tanlang."
    if scale_checker is None:
        return False, "Tarozi xizmati mavjud emas."
    deadline = time.monotonic() + SCALE_PROBE_SECONDS
    while time.monotonic() < deadline:
        if scale_checker():
            return True, f"Ulangan ({port})"
        time.sleep(0.2)
    return False, f"{port} portidan javob kelmadi (tarozi o'chiqmi?)."


def _check_scanner_camera_live(scanner_checker):
    cam = db.get_scanner_camera()
    if not cam:
        return False, "Sozlanmagan — Sozlamalar sahifasida ulang."
    if scanner_checker is None:
        return False, "Skaner xizmati mavjud emas."
    deadline = time.monotonic() + CAMERA_PROBE_SECONDS
    while time.monotonic() < deadline:
        if scanner_checker():
            return True, f"Ulangan ({cam.connection_type})"
        time.sleep(0.2)
    return False, "Kameradan/skanerdan kadr kelmayapti."


def _check_ombor_cameras_live(ombor_checker):
    cams = db.list_all_ombor_cameras()
    if not cams:
        return False, "Hech qanday ombor kamerasi sozlanmagan."
    if ombor_checker is None:
        return False, "Kamera xizmati mavjud emas."
    total = len(cams)
    deadline = time.monotonic() + CAMERA_PROBE_SECONDS
    working = 0
    while time.monotonic() < deadline:
        working, total = ombor_checker()
        if working == total:
            break
        time.sleep(0.3)
    if working == total:
        return True, f"{working}/{total} ta kamera ulangan"
    return False, f"Faqat {working}/{total} ta kamera javob berdi."


class _DeviceProbeWorker(QThread):
    """Barcha qurilmalarni fon oqimida (asosiy oynani bloklamasdan)
    tekshiradi. `scale_checker`/`scanner_checker`/`ombor_checker` —
    mos ravishda `ScaleService.is_connected`, `ScannerService.
    is_camera_connected`, `CameraRecorderService.connected_camera_count`
    (MainWindow'da allaqachon fonda ishlab turgan xizmatlar) — ALOHIDA
    (raqobatlashuvchi) qurilma ulanishi hech qachon OCHILMAYDI. Sabab:
    bitta COM port/kamerani ikkinchi joy bir vaqtda ochishga urinsa,
    odatda ishlamay qoladi yoki xato beradi (real sinovda ikkalasi ham
    aniqlangan — tarozi uchun "Access is denied", skaner kamerasi uchun
    esa "ishlab turgan narsa checkpointdan o'tolmayabdi")."""
    finished_probe = pyqtSignal(dict)

    def __init__(self, scale_checker=None, scanner_checker=None, ombor_checker=None):
        super().__init__()
        self._scale_checker = scale_checker
        self._scanner_checker = scanner_checker
        self._ombor_checker = ombor_checker

    def run(self):
        result = {}
        result["printer"] = _check_printer_live()
        result["scale"] = _check_scale_live(self._scale_checker)
        result["scanner_camera"] = _check_scanner_camera_live(self._scanner_checker)
        result["ombor_cameras"] = _check_ombor_cameras_live(self._ombor_checker)
        self.finished_probe.emit(result)


class _CheckRow(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        self.icon = QLabel("⏳")
        self.icon.setStyleSheet("font-size:18px;")
        layout.addWidget(self.icon)
        text_col = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight:700; font-size:14px;")
        self.detail_label = QLabel("Tekshirilmoqda...")
        self.detail_label.setStyleSheet(CHECKING_STYLE)
        text_col.addWidget(title_label)
        text_col.addWidget(self.detail_label)
        layout.addLayout(text_col, 1)

    def set_result(self, ok: bool, detail: str):
        self.icon.setText("✅" if ok else "⚠️")
        self.detail_label.setText(detail)
        self.detail_label.setStyleSheet(OK_STYLE if ok else WARN_STYLE)


class StartupCheckPage(QWidget):
    """Ishga tushishda barcha qurilmalarni (printer, tarozi, kameralar)
    jonli tekshiradi. Barchasi onlayn bo'lsa — "Davom etish" (avtomatik
    sanoq bilan). Birortasi nosoz bo'lsa — "Sozlamalarga o'tish" tugmasi
    (`open_settings_requested`), u yerda tuzatilgach `refresh()` orqali
    qayta tekshiriladi."""
    continue_requested = pyqtSignal()
    open_settings_requested = pyqtSignal()

    def __init__(self, scale_checker=None, scanner_checker=None, ombor_checker=None, parent=None):
        super().__init__(parent)
        self._scale_checker = scale_checker
        self._scanner_checker = scanner_checker
        self._ombor_checker = ombor_checker
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(18)

        self.title = QLabel("Qurilmalar tekshirilmoqda...")
        self.title.setStyleSheet("font-size:20px; font-weight:800;")
        layout.addWidget(self.title)

        self.desc = QLabel(
            "Dastur ishga tushishidan oldin barcha qurilmalar (printer, tarozi, "
            "kameralar) bilan haqiqatan ham bog'lanib ko'riladi."
        )
        self.desc.setWordWrap(True)
        self.desc.setStyleSheet("color:#666;")
        layout.addWidget(self.desc)

        self._rows_container = QVBoxLayout()
        layout.addLayout(self._rows_container)
        self.row_printer = _CheckRow("Etiketka printeri")
        self.row_scale = _CheckRow("Tarozi")
        self.row_scanner_cam = _CheckRow("Xodim skaneri kamerasi")
        self.row_ombor_cam = _CheckRow("Ombor kamera(lar)i")
        for row in (self.row_printer, self.row_scale, self.row_scanner_cam, self.row_ombor_cam):
            self._rows_container.addWidget(row)

        layout.addStretch(1)

        self.continue_btn = QPushButton()
        self.continue_btn.setFixedHeight(42)
        self.continue_btn.clicked.connect(self._continue_now)
        layout.addWidget(self.continue_btn)

        self.settings_btn = QPushButton("⚙ Sozlamalarga o'tish")
        self.settings_btn.setFixedHeight(42)
        self.settings_btn.setStyleSheet(
            "background:#0f172a; color:white; font-weight:700; border:none; border-radius:8px;"
        )
        self.settings_btn.clicked.connect(self.open_settings_requested.emit)
        self.settings_btn.setVisible(False)
        layout.addWidget(self.settings_btn)

        self._seconds_left = AUTO_CONTINUE_SECONDS
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick_countdown)

        self._probe_worker: _DeviceProbeWorker | None = None
        self._all_ok = False

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def _tick_countdown(self):
        self._seconds_left -= 1
        if self._seconds_left <= 0:
            self._continue_now()
            return
        self._update_button_text()

    def _update_button_text(self):
        self.continue_btn.setText(f"Davom etish ({self._seconds_left})")

    def _continue_now(self):
        self._countdown_timer.stop()
        self.continue_requested.emit()

    def refresh(self):
        """Tekshiruvni qaytadan (jonli) boshlaydi — masalan Sozlamalardan
        qaytilganda, qurilma tuzatilgandan keyin qayta chaqiriladi.

        Agar tekshiruv ALLAQACHON ishlab turgan bo'lsa — hech narsa
        qilmaydi (Qt ba'zan bitta haqiqiy ko'rsatish uchun `showEvent`ni
        bir necha marta chaqirishi mumkin — bu holatda qayta boshlash
        deyarli tugagan tekshiruv natijalarini "Tekshirilmoqda..."
        holatiga qaytarib, foydalanuvchiga hech qachon natija
        ko'rsatmay qolar edi)."""
        if self._probe_worker is not None and self._probe_worker.isRunning():
            return
        self._countdown_timer.stop()
        self._all_ok = False
        self.continue_btn.setVisible(False)
        self.settings_btn.setVisible(False)
        self.title.setText("Qurilmalar tekshirilmoqda...")
        for row in (self.row_printer, self.row_scale, self.row_scanner_cam, self.row_ombor_cam):
            row.icon.setText("⏳")
            row.detail_label.setText("Tekshirilmoqda...")
            row.detail_label.setStyleSheet(CHECKING_STYLE)

        old = self._probe_worker
        if old is not None and old.isRunning():
            old.wait()
        self._probe_worker = _DeviceProbeWorker(
            scale_checker=self._scale_checker,
            scanner_checker=self._scanner_checker,
            ombor_checker=self._ombor_checker,
        )
        self._probe_worker.finished_probe.connect(self._on_probe_finished)
        self._probe_worker.start()

    def _on_probe_finished(self, result: dict):
        printer_ok, printer_detail = result["printer"]
        scale_ok, scale_detail = result["scale"]
        scanner_ok, scanner_detail = result["scanner_camera"]
        ombor_ok, ombor_detail = result["ombor_cameras"]

        self.row_printer.set_result(printer_ok, printer_detail)
        self.row_scale.set_result(scale_ok, scale_detail)
        self.row_scanner_cam.set_result(scanner_ok, scanner_detail)
        self.row_ombor_cam.set_result(ombor_ok, ombor_detail)

        self._all_ok = printer_ok and scale_ok and scanner_ok and ombor_ok
        if self._all_ok:
            self.title.setText("✅ Barcha qurilmalar onlayn")
            self.continue_btn.setVisible(True)
            self.settings_btn.setVisible(False)
            self._seconds_left = AUTO_CONTINUE_SECONDS
            self._update_button_text()
            self._countdown_timer.start()
        else:
            self.title.setText("⚠️ Ba'zi qurilmalar bilan bog'lanib bo'lmadi")
            self.continue_btn.setVisible(False)
            self.settings_btn.setVisible(True)
