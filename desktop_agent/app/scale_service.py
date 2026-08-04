"""CAS CI-200A (va shu formatga mos boshqa) tarozi indikatorini RS232
orqali fonda o'qiydigan xizmat.

Haqiqiy uskunada sinovda aniqlangan format (null-modem kabel bilan,
9600 baud, 8N1) — tarozi uzluksiz, so'rovsiz o'zi yuboradi:

    "  Weight :   0.34kg\r\n"

Bu xizmat COM portni fon oqimida doimiy o'qiydi, har bir to'liq
qatorni parslaydi va `weight_changed(float)` signali orqali oxirgi
o'qilgan vaznni (kg) uzatadi — `EmployeeScanWidget` buni tortish
ekrani ochiq turganda tarozi qiymati maydoniga avtomatik yozadi
(qo'lda kiritish o'rniga).

Tarozi sozlanmagan bo'lsa (`scale_com_port` bo'sh) — xizmat hech
narsa qilmaydi, dastur boshqa qismlariga ta'sir qilmaydi."""
import re
import time

import serial
from PyQt6.QtCore import QThread, pyqtSignal

from . import db

BAUD_RATE = 9600
WEIGHT_PATTERN = re.compile(r"Weight\s*:\s*(-?[\d.]+)\s*kg", re.IGNORECASE)
RECONNECT_DELAY_SECONDS = 5


class ScaleReaderWorker(QThread):
    weight_changed = pyqtSignal(float)

    def __init__(self, com_port: str):
        super().__init__()
        self._com_port = com_port
        self._running = False
        # Oxirgi haqiqiy o'qish qachon kelgani — `ScaleService.is_connected()`
        # shu orqali "haqiqatan ham jonli ulanganmi" deb bilib oladi,
        # alohida (raqobatlashuvchi) COM-port ulanishisiz.
        self.last_reading_at = 0.0

    def run(self):
        self._running = True
        buffer = b""
        while self._running:
            try:
                with serial.Serial(self._com_port, baudrate=BAUD_RATE, timeout=1) as ser:
                    while self._running:
                        chunk = ser.read(256)
                        if not chunk:
                            continue
                        buffer += chunk
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            self._handle_line(line)
            except Exception:  # noqa: BLE001 — port band/uzilgan bo'lishi mumkin, keyinroq qayta uriniladi
                pass
            if self._running:
                time.sleep(RECONNECT_DELAY_SECONDS)

    def _handle_line(self, line: bytes):
        try:
            text = line.decode(errors="ignore")
        except Exception:  # noqa: BLE001
            return
        match = WEIGHT_PATTERN.search(text)
        if match:
            try:
                value = float(match.group(1))
            except ValueError:
                return
            self.last_reading_at = time.monotonic()
            self.weight_changed.emit(value)

    def stop(self):
        self._running = False
        self.wait(3000)


class ScaleService:
    """`ScannerService`/`CameraRecorderService` bilan bir xil naqsh —
    dastur ochiq turgan davomida fonda ishlaydi, sozlamalar sahifasida
    COM porti o'zgartirilganda `reload()` chaqiriladi."""

    def __init__(self, on_weight_changed=None):
        self._on_weight_changed = on_weight_changed
        self._worker: ScaleReaderWorker | None = None
        self.reload()

    def reload(self):
        if self._worker is not None:
            self._worker.stop()
            self._worker = None
        com_port = db.get_setting("scale_com_port", "").strip()
        if not com_port:
            return
        self._worker = ScaleReaderWorker(com_port)
        if self._on_weight_changed:
            self._worker.weight_changed.connect(self._on_weight_changed)
        self._worker.start()

    def stop(self):
        if self._worker is not None:
            self._worker.stop()
            self._worker = None

    def is_connected(self, within_seconds: float = 3.0) -> bool:
        """Tarozi haqiqatan ham jonli o'qilayotganini bildiradi — startup
        qurilma-tekshiruvi (176-qadam) shu orqali so'raydi, ALOHIDA COM-
        port ulanishi ochmaydi. Sabab: bitta COM portni ikkita joy bir
        vaqtda ochishga urinsa, Windows "Access is denied" xatosi beradi
        (real sinovda aynan shu aniqlandi) — bu xizmat allaqachon portni
        ushlab turgani uchun, tekshiruv shunchaki OXIRGI HAQIQIY o'qish
        qachon kelganini so'raydi."""
        if self._worker is None:
            return False
        return (time.monotonic() - self._worker.last_reading_at) < within_seconds
