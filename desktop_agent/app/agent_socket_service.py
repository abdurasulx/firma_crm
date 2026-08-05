"""Desktop Agent uchun real-vaqtli WebSocket xizmati.

ERP'da allaqachon mavjud `/ws/notifications/` kanaliga ulanadi — xuddi
brauzer dashboardi ulanadigani kabi, faqat Django sessiyasi o'rniga
stansiya tokeni (`?token=...` query-param) orqali autentifikatsiya
qiladi (`main/consumers.py::NotificationConsumer`, 91-qadam). Server
tomonda biror narsa o'zgarsa (masalan ombor qo'shilsa) va bu
`event='ombor_changed'` bilan yuborilsa — shu xabar shu yerga ham
yetib keladi, Desktop Agent hech qanday qo'lda "Sinxronlash" tugmasini
bosmasdan, o'zi darhol yangilanadi.

Ulanish uzilsa (server o'chib qolsa, tarmoq muammosi) — avtomatik
qayta ulanishga harakat qiladi (bir necha soniyalik orqaga chekinish
bilan), foydalanuvchi hech narsa qilishi shart emas.
"""
import time

import websocket
from PyQt6.QtCore import QThread, pyqtSignal

RECONNECT_DELAY_SECONDS = 5


def _to_ws_url(server_url: str) -> str:
    """`https://birzumda.stockfirm.uz` -> `wss://birzumda.stockfirm.uz`,
    `http://127.0.0.1:8000` -> `ws://127.0.0.1:8000`."""
    if server_url.startswith("https://"):
        return "wss://" + server_url[len("https://"):]
    if server_url.startswith("http://"):
        return "ws://" + server_url[len("http://"):]
    return server_url


class AgentSocketWorker(QThread):
    """Fon oqimida doimiy ishlaydigan WebSocket mijozi. Har bir kelgan
    JSON xabar `notification_received` signali orqali uzatiladi — UI
    (asosiy) oqimda xavfsiz qabul qilinadi (PyQt bunday signalni
    boshqa oqimdan avtomatik navbatga qo'yadi)."""
    notification_received = pyqtSignal(dict)

    def __init__(self, server_url: str, token: str):
        super().__init__()
        self._server_url = server_url
        self._token = token
        self._running = False
        self._ws: websocket.WebSocketApp | None = None

    def run(self):
        self._running = True
        ws_url = _to_ws_url(self._server_url).rstrip("/") + f"/ws/notifications/?token={self._token}"

        while self._running:
            try:
                self._ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=self._on_message,
                    on_error=lambda ws, error: None,
                )
                self._ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception:  # noqa: BLE001 — ulanish xatosi butun dasturni yiqitmasin
                pass
            if self._running:
                time.sleep(RECONNECT_DELAY_SECONDS)

    def _on_message(self, ws, message: str):
        try:
            import json
            data = json.loads(message)
        except (ValueError, TypeError):
            return
        if isinstance(data, dict):
            self.notification_received.emit(data)

    def stop(self):
        self._running = False
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:  # noqa: BLE001
                pass
        self.wait(3000)
