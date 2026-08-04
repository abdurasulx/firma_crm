"""Butun dastur bo'ylab (hech qanday menyu/sahifa ochmasdan) doimiy
ishlaydigan fon skaner xizmati.

Foydalanuvchi so'ragan xatti-harakat: xodim istalgan payt (dastur qaysi
sahifada ochiq bo'lishidan qat'iy nazar) shaxsiy QR (badge)ini skanerga
ko'rsatsa, kod shu firmaga tegishli bo'lib chiqsa, ma'lumoti darhol
chiqishi kerak — alohida "Skaner" menyusiga kirish shart emas.

Sozlangan kamera turiga qarab ikki xil ishlaydi:
  - **HID (qo'lda skaner)**: `keyboard` kutubxonasi orqali **butun
    kompyuter bo'ylab** (nafaqat shu dastur ichida — Windows darajasida,
    qaysi oyna fokusda bo'lishidan qat'iy nazar) klaviatura hodisalarini
    kuzatadi. Bu ataylab shunday qilingan: foydalanuvchi ko'pincha
    telefonida (yoki brauzerda) ko'rsatilgan QR kodni skanerlaydi —
    o'sha payt StockFirm Desktop Agent oynasi fokusda bo'lishi shart
    emas, xuddi GTA'dagi cheat-kod kabi, dastur qaysi oynada ekaningizga
    qaramasdan kodni "eshitib" oladi. Hodisalar iste'mol qilinmaydi
    (bloklab qo'yilmaydi) — ular fokusdagi oynaga (masalan brauzerga)
    ham odatdagidek yetib boradi, biz faqat qo'shimcha ravishda kuzatib
    turamiz.
  - **USB/RTSP (kamera)**: fon rejimida doimiy QR-aniqlash ishga tushadi
    (`QRScanWorker`), foydalanuvchi hech qanday sahifa ochmasa ham.
"""
import time

import keyboard
from PyQt6.QtCore import QObject, pyqtSignal

from . import db
from .camera_utils import QRScanWorker, build_rtsp_url

# Belgilar orasida shuncha vaqt (ms) o'tsa — bu yangi ketma-ketlik
# boshlanishi deb hisoblanadi (avvalgi bufer tashlab yuboriladi).
HID_MAX_KEY_GAP_MS = 60
# Ko'pgina qo'lda skanerlar kodni "Enter" bilan emas, "Tab" bilan
# tugatadigan qilib sozlangan bo'ladi (forma-navigatsiya uslubi) —
# real qurilmada aynan shu tasdiqlandi (debug orqali). Shuning uchun
# ikkalasi ham tugatuvchi tugma sifatida qabul qilinadi.
HID_TERMINATOR_KEYS = {"enter", "tab"}
# XodimBadge.kod / ProductionMaterialRequest.kod — uuid4() (36 belgi,
# chiziqchalar bilan) — shuning uchun bu chegara odatiy tez yozilgan
# matndan (masalan parol) ham xavfsiz farq qiladi.
HID_MIN_CODE_LENGTH = 20


class ScannerService(QObject):
    code_scanned = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scan_worker: QRScanWorker | None = None
        self._hid_hook = None
        self._hid_buffer = ""
        self._hid_last_time = 0.0
        # Oxirgi jonli kadr qachon kelgani — `is_camera_connected()` shu
        # orqali "haqiqatan ham ishlayaptimi" deb bilib oladi, startup
        # qurilma-tekshiruvi (176-177-qadamlar) ALOHIDA (raqobatlashuvchi)
        # kamera ulanishi ochmasligi uchun — bitta kamerani ikkinchi joy
        # bir vaqtda ochishga urinsa, odatda ishlamay qoladi/xato beradi.
        self._last_frame_at = 0.0
        self.reload()

    def reload(self):
        """Skaner sozlamasi o'zgarganda (masalan qayta sozlanganda)
        chaqiriladi — eski worker/hookni to'xtatib, yangisini boshlaydi."""
        self._stop_camera_worker()
        cam = db.get_scanner_camera()
        if cam is None:
            self._uninstall_hid_hook()
            return
        if cam.connection_type == "hid":
            self._install_hid_hook()
            return

        self._uninstall_hid_hook()
        source = cam.usb_index if cam.connection_type == "usb" else cam.rtsp_url
        is_rtsp = cam.connection_type == "rtsp"
        if is_rtsp:
            source = build_rtsp_url(cam.rtsp_url, cam.rtsp_username or "", cam.rtsp_password or "")
        self._scan_worker = QRScanWorker(source, is_rtsp=is_rtsp)
        self._scan_worker.qr_detected.connect(self.code_scanned.emit)
        self._scan_worker.frame_ready.connect(self._on_frame_ready)
        self._scan_worker.start()

    def _on_frame_ready(self, _frame):
        self._last_frame_at = time.monotonic()

    def is_camera_connected(self, within_seconds: float = 3.0) -> bool:
        """Skaner kamerasi (yoki HID qo'lda skaner) haqiqatan ham
        ishlayotganini bildiradi — startup qurilma-tekshiruvi shu orqali
        so'raydi, ALOHIDA kamera ulanishi ochmaydi."""
        cam = db.get_scanner_camera()
        if cam is None:
            return False
        if cam.connection_type == "hid":
            return self._hid_hook is not None
        return (time.monotonic() - self._last_frame_at) < within_seconds

    def stop(self):
        self._stop_camera_worker()
        self._uninstall_hid_hook()

    def _stop_camera_worker(self):
        if self._scan_worker is not None:
            self._scan_worker.qr_detected.disconnect(self.code_scanned.emit)
            self._scan_worker.stop()
            self._scan_worker = None

    def _install_hid_hook(self):
        if self._hid_hook is None:
            self._hid_hook = keyboard.hook(self._on_key_event)

    def _uninstall_hid_hook(self):
        if self._hid_hook is not None:
            keyboard.unhook(self._hid_hook)
            self._hid_hook = None
        self._hid_buffer = ""

    def _on_key_event(self, event):
        """`keyboard` kutubxonasining o'z (Qt bilan bog'liq bo'lmagan) fon
        oqimida chaqiriladi — shuning uchun bu yerda hech qanday widgetga
        to'g'ridan-to'g'ri tegilmaydi, faqat `code_scanned` signali
        chiqariladi (PyQt bunday signalni boshqa oqimdan xavfsiz asosiy
        oqimga uzatadi)."""
        if event.event_type != keyboard.KEY_DOWN:
            return

        now = time.monotonic() * 1000
        if event.name in HID_TERMINATOR_KEYS:
            if len(self._hid_buffer) >= HID_MIN_CODE_LENGTH:
                kod = self._hid_buffer
                self._hid_buffer = ""
                self.code_scanned.emit(kod)
            else:
                self._hid_buffer = ""
            return

        char = event.name if event.name and len(event.name) == 1 else None
        if char:
            if now - self._hid_last_time > HID_MAX_KEY_GAP_MS:
                self._hid_buffer = ""
            self._hid_buffer += char
            self._hid_last_time = now
