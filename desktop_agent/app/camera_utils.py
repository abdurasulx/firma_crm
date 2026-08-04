"""
Kamera bilan ishlash: USB kameralarni aniqlash, RTSP manzil qurish,
va jonli ko'rinish (preview) uchun fon oqimi (background thread).
"""
import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

MAX_USB_PROBE = 6


def detect_usb_cameras(max_index: int = MAX_USB_PROBE):
    """Kompyuterga ulangan USB kameralarni indekslari bo'yicha aniqlaydi.

    Har bir indeksni ochib ko'rish sekin (kamera drayveri javob berguncha
    kutadi) — shuning uchun UI'ni bloklamaslik uchun bu funksiya alohida
    oqimda (`UsbDetectWorker`) chaqiriladi.
    """
    found = []
    for index in range(max_index):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        try:
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    found.append(index)
        finally:
            cap.release()
    return found


def build_rtsp_url(url: str, username: str = "", password: str = "") -> str:
    """Login/parolni RTSP URL ichiga joylashtiradi (masalan
    rtsp://192.168.1.10:554/stream1 -> rtsp://user:pass@192.168.1.10:554/stream1),
    agar URL ichida allaqachon login bo'lmasa va username/password berilgan bo'lsa.
    """
    url = (url or "").strip()
    if not username and not password:
        return url
    if "@" in url.split("://", 1)[-1]:
        return url  # URL ichida allaqachon login bor
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    return f"{scheme}://{username}:{password}@{rest}"


def frame_to_qimage(frame) -> QImage:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w
    return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()


class UsbDetectWorker(QThread):
    """USB kameralarni fon oqimida aniqlaydi (UI muzlab qolmasligi uchun)."""
    finished_ok = pyqtSignal(list)

    def run(self):
        found = detect_usb_cameras()
        self.finished_ok.emit(found)


class CameraPreviewWorker(QThread):
    """Berilgan manba (USB indeks yoki RTSP URL)dan jonli kadrlarni o'qib,
    signal orqali UI'ga uzatadi."""
    frame_ready = pyqtSignal(QImage)
    error = pyqtSignal(str)

    def __init__(self, source, is_rtsp: bool = False):
        super().__init__()
        self._source = source
        self._is_rtsp = is_rtsp
        self._running = False

    def run(self):
        cap_source = self._source if self._is_rtsp else int(self._source)
        cap = cv2.VideoCapture(cap_source) if self._is_rtsp else cv2.VideoCapture(cap_source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.error.emit("Kameraga ulanib bo'lmadi. Manzil/login/parolni tekshiring.")
            return

        self._running = True
        while self._running:
            ok, frame = cap.read()
            if not ok:
                self.error.emit("Kameradan tasvir kelmayapti (ulanish uzilgan bo'lishi mumkin).")
                break
            self.frame_ready.emit(frame_to_qimage(frame))
            self.msleep(66)  # ~15 fps — preview uchun yetarli, protsessorni band qilmaydi

        cap.release()

    def stop(self):
        self._running = False
        self.wait(2000)


class QRScanWorker(QThread):
    """Berilgan manbadan jonli kadr o'qib, QR kod qidiradi. Topilganda
    `qr_detected` signalini yuboradi (bir xil kod ketma-ket bir necha
    kadrda o'qilsa ham, `debounce_seconds` davomida faqat bir marta)."""
    frame_ready = pyqtSignal(QImage)
    qr_detected = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, source, is_rtsp: bool = False, debounce_seconds: float = 3.0):
        super().__init__()
        self._source = source
        self._is_rtsp = is_rtsp
        self._debounce_seconds = debounce_seconds
        self._running = False

    def run(self):
        import time

        cap_source = self._source if self._is_rtsp else int(self._source)
        cap = cv2.VideoCapture(cap_source) if self._is_rtsp else cv2.VideoCapture(cap_source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.error.emit("Skaner kamerasiga ulanib bo'lmadi.")
            return

        detector = cv2.QRCodeDetector()
        last_kod = None
        last_time = 0.0

        self._running = True
        while self._running:
            ok, frame = cap.read()
            if not ok:
                self.error.emit("Skaner kamerasidan tasvir kelmayapti.")
                break

            self.frame_ready.emit(frame_to_qimage(frame))

            try:
                data, _, _ = detector.detectAndDecode(frame)
            except cv2.error:
                data = ""

            now = time.monotonic()
            if data:
                # Desktop Agent QR-login kodi (statik ekran/qog'ozdagi kod,
                # AGENTQR|... bilan boshlanadi) debounce'dan chetlashtiriladi —
                # login urinishi muvaffaqiyatsiz bo'lsa (masalan server
                # ulanmagan), foydalanuvchi bir necha soniya ichida qayta
                # skanerlab qayta urinishi kerak, "bir xil kod — e'tiborsiz"
                # qoidasi bunga to'sqinlik qilmasligi kerak.
                is_login_qr = data.startswith("AGENTQR|")
                if is_login_qr or data != last_kod or (now - last_time) > self._debounce_seconds:
                    last_kod = data
                    last_time = now
                    self.qr_detected.emit(data)

            self.msleep(66)

        cap.release()

    def stop(self):
        self._running = False
        self.wait(2000)
