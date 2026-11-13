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
# Boshqa indikatorlar "Weight :" so'zisiz yuboradi (masalan
# "ST,GS,+  1.234kg") — asosiy naqsh mos kelmasa, qatordagi "<son> kg"
# shaklidagi qiymat olinadi.
FALLBACK_WEIGHT_PATTERN = re.compile(r"([-+]?\s*\d+(?:\.\d+)?)\s*kg", re.IGNORECASE)
LINE_SPLIT_PATTERN = re.compile(rb"[\r\n]+")
RECONNECT_DELAY_SECONDS = 5


def parse_weight_line(text: str) -> float | None:
    """Tarozi yuborgan bitta qatordan vaznni (kg) ajratib oladi; qator
    vazn bo'lmasa `None`."""
    match = WEIGHT_PATTERN.search(text) or FALLBACK_WEIGHT_PATTERN.search(text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(" ", ""))
    except ValueError:
        return None


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
        # Diagnostika holati (`diagnose()`): "javob kelmadi" degan bitta
        # umumiy xabar o'rniga aniq sabab ko'rsatish uchun — port
        # ochilmadimi, ochildi-yu hech narsa kelmayaptimi, yoki nimadir
        # kelyapti-yu vazn sifatida tushunilmayaptimi.
        self.port_open = False
        self.open_error = ""
        self.bytes_received = 0
        self.last_raw_line = ""

    def run(self):
        self._running = True
        buffer = b""
        while self._running:
            try:
                with serial.Serial(self._com_port, baudrate=BAUD_RATE, timeout=1) as ser:
                    self.port_open = True
                    self.open_error = ""
                    while self._running:
                        chunk = ser.read(256)
                        if not chunk:
                            continue
                        self.bytes_received += len(chunk)
                        buffer += chunk
                        # Ba'zi tarozilar qatorni faqat "\r" bilan tugatadi.
                        parts = LINE_SPLIT_PATTERN.split(buffer)
                        buffer = parts.pop()
                        for line in parts:
                            self._handle_line(line)
                        if len(buffer) > 4096:  # tugatuvchisiz oqim — xotira o'smasin
                            buffer = buffer[-256:]
            except Exception as exc:  # noqa: BLE001 — port band/uzilgan bo'lishi mumkin, keyinroq qayta uriniladi
                self.open_error = str(exc)
            self.port_open = False
            if self._running:
                time.sleep(RECONNECT_DELAY_SECONDS)

    def _handle_line(self, line: bytes):
        try:
            text = line.decode(errors="ignore")
        except Exception:  # noqa: BLE001
            return
        if text.strip():
            self.last_raw_line = text.strip()[:60]
        value = parse_weight_line(text)
        if value is not None:
            self.last_reading_at = time.monotonic()
            self.weight_changed.emit(value)

    def diagnose(self) -> str:
        """Tarozidan vazn kelmayotgan bo'lsa — nega ekanini odam tilida."""
        port = self._com_port
        if not self.port_open:
            if self.open_error:
                low = self.open_error.lower()
                if "denied" in low or "permission" in low:
                    return f"{port} portini boshqa dastur band qilgan — o'sha dasturni yoping."
                if "filenotfound" in low or "cannot find" in low:
                    return f"{port} porti topilmadi — USB-COM kabel ulanganini tekshiring yoki Sozlamalarda portni qayta tanlang."
                return f"{port} portini ochib bo'lmadi: {self.open_error[:80]}"
            return f"{port} portiga ulanilmoqda..."
        if self.bytes_received == 0:
            return (
                f"{port} porti ochildi, lekin tarozidan hech qanday signal kelmayapti — tarozi yoqilganini, "
                "kabel tarozining RS232 chiqishiga ulanganini va tarozida uzluksiz yuborish (stream) rejimi "
                "yoqilganini tekshiring."
            )
        if self.last_reading_at == 0.0:
            sample = f" (kelgan: \"{self.last_raw_line}\")" if self.last_raw_line else ""
            return (
                f"{port} portidan ma'lumot kelyapti, lekin vazn sifatida o'qib bo'lmadi{sample} — "
                f"tarozi tezligi {BAUD_RATE} baud ekanini tekshiring."
            )
        return f"{port}: tarozidan signal uzilib qoldi — kabel va quvvatni tekshiring."

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

    def diagnose(self) -> str:
        """Tarozi ulanmagan deb topilganda — aniq sabab (qurilma-tekshiruv
        sahifasida ko'rsatiladi)."""
        if self._worker is None:
            return "Tarozi sozlanmagan."
        return self._worker.diagnose()
