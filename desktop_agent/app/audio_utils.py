"""Ombor kamerasiga (ixtiyoriy) biriktirilgan mikrofondan ovoz yozish —
video bilan bir xil "voqea atrofida aylanma bufer" naqshi bilan
(`camera_recorder_service.py::_OmborCameraBufferWorker`ga o'xshash,
faqat audio uchun).

Har bir ombor kamerasiga alohida mikrofon biriktirilishi mumkin
(masalan kameraning o'z ichidagi mikrofoni). Agar biriktirilmagan bo'lsa
yoki qurilma xato bersa — xavfsiz tarzda "ovozsiz" davom etiladi, video
baribir yoziladi (foydalanuvchi bilan kelishilgan qaror: "qaysidir
kamerani o'zini mikrofoni yo'q bo'lsa muammo emas")."""
import threading
import time
import wave

import sounddevice as sd
from PyQt6.QtCore import QThread, pyqtSignal

SAMPLE_RATE = 44100
CHANNELS = 1
CHUNK_SECONDS = 0.5
BUFFER_SECONDS = 60  # video buferi (camera_recorder_service.BUFFER_SECONDS) bilan bir xil


def list_mic_devices() -> list[str]:
    """Kirish (mikrofon) qurilmalari nomlari ro'yxati — Sozlamalarda
    tanlash uchun. Xato bo'lsa (masalan audio drayveri yo'q) bo'sh
    ro'yxat qaytadi — dastur ochilishini to'xtatmaydi."""
    try:
        devices = sd.query_devices()
    except Exception:
        return []
    seen: list[str] = []
    for d in devices:
        if d.get("max_input_channels", 0) > 0 and d["name"] not in seen:
            seen.append(d["name"])
    return seen


def _find_device_index_by_name(name: str):
    try:
        devices = sd.query_devices()
    except Exception:
        return None
    for i, d in enumerate(devices):
        if d["name"] == name and d.get("max_input_channels", 0) > 0:
            return i
    return None


class MicBufferWorker(QThread):
    """Bitta mikrofondan doimiy fon rejimida audio bo'laklarini o'qib,
    oxirgi BUFFER_SECONDS soniyalik aylanma buferda (vaqt belgisi bilan)
    saqlaydi."""
    error = pyqtSignal(str)

    def __init__(self, device_name: str):
        super().__init__()
        self.device_name = device_name
        self._running = False
        self._lock = threading.Lock()
        self._buffer: list = []  # [(monotonic_ts, ndarray)]

    def run(self):
        device_index = _find_device_index_by_name(self.device_name)
        if device_index is None:
            self.error.emit(f"Mikrofon topilmadi: {self.device_name}")
            return

        blocksize = int(SAMPLE_RATE * CHUNK_SECONDS)
        self._running = True
        try:
            with sd.InputStream(
                device=device_index, channels=CHANNELS, samplerate=SAMPLE_RATE,
                blocksize=blocksize, dtype="int16",
            ) as stream:
                while self._running:
                    data, _overflowed = stream.read(blocksize)
                    now = time.monotonic()
                    with self._lock:
                        self._buffer.append((now, data.copy()))
                        cutoff = now - BUFFER_SECONDS
                        while self._buffer and self._buffer[0][0] < cutoff:
                            self._buffer.pop(0)
        except Exception as exc:  # noqa: BLE001 — mikrofon xatosi videoni to'xtatmasin
            self.error.emit(f"Mikrofondan ovoz olishda xato ({self.device_name}): {exc}")

    def stop(self):
        self._running = False
        self.wait(2000)

    def chunks_from(self, since_ts: float):
        with self._lock:
            return [c for c in self._buffer if c[0] >= since_ts]

    def write_wav_from(self, since_ts: float, out_path: str) -> bool:
        """[since_ts; hozir] oralig'idagi audio bo'laklarini WAV fayliga
        yozadi. Hech qanday bo'lak topilmasa `False` qaytaradi (audio
        yo'q — chaqiruvchi video-only fallback qiladi)."""
        chunks = self.chunks_from(since_ts)
        if not chunks:
            return False
        with wave.open(out_path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # int16 = 2 bayt
            wf.setframerate(SAMPLE_RATE)
            for _, data in chunks:
                wf.writeframes(data.tobytes())
        return True
