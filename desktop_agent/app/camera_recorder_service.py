"""Ombor kameralari uchun "voqea atrofida video (va ixtiyoriy ovoz) yozish"
xizmati.

Vision hujjatidagi talab: har bir ombor kamerasi tasdiqlashdan
PRE_SECONDS soniya oldin — so'rov yopilgandan POST_SECONDS soniya
keyingacha video yozadi. Buni amalga oshirish uchun har bir sozlangan
ombor kamerasi uchun DOIMIY fon oqimida ishlaydigan aylanma bufer
(`_OmborCameraBufferWorker`) ochiladi — bufer oxirgi BUFFER_SECONDS
soniyalik kadrlarni (vaqt belgisi bilan) saqlab turadi. "Voqea"
boshlanganda (`start_event`) hech narsa darhol yozilmaydi — faqat
boshlanish vaqti PRE_SECONDS orqaga suriladi va eslab qolinadi. Voqea
tugaganda (`stop_event`) POST_SECONDS kutib, keyin buferdan
[boshlanish-PRE_SECONDS; hozir] oralig'idagi barcha kadrlar
`cv2.VideoWriter` bilan mp4 fayliga yoziladi.

Agar kameraga mikrofon ham biriktirilgan bo'lsa (`Camera.mic_device_name`)
— xuddi shu oraliqdagi audio ham (`audio_utils.MicBufferWorker`) yoziladi
va `ffmpeg` orqali videoga birlashtiriladi (mux). `ffmpeg` topilmasa yoki
mikrofon sozlanmagan bo'lsa — video ovozsiz saqlanadi (xato emas,
xavfsiz pasayish — foydalanuvchi bilan kelishilgan qaror).

Ombor kameralari sozlanmagan bo'lsa (`db.list_all_ombor_cameras()` bo'sh)
— bu xizmat hech narsa qilmaydi, chaqiruvlar xavfsiz no-op bo'ladi.
"""
import os
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime

import cv2
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from . import db
from .audio_utils import MicBufferWorker
from .camera_utils import build_rtsp_url

PRE_SECONDS = 5
POST_SECONDS = 5
BUFFER_SECONDS = 60  # PRE_SECONDS + eng uzun kutilgan voqea davomiyligi uchun yetarli zaxira
CAPTURE_FPS = 12


def find_ffmpeg() -> str | None:
    """Video+audio birlashtirish (mux) uchun `ffmpeg`ni topadi:
    (1) `imageio-ffmpeg` pip kutubxonasi bilan birga o'rnatilgan tayyor
    ffmpeg binary'si (endi standart yo'l — foydalanuvchi qo'lda hech
    narsa joylashtirmasligi kerak, PyInstaller build vaqtida shu binary
    exe ichiga qo'shib qo'yiladi), (2) `.exe` bilan bir papkadagi
    `ffmpeg.exe` (qo'lda joylashtirilgan bo'lsa — orqaga moslik uchun
    hamon qo'llab-quvvatlanadi), (3) PyInstaller onefile ichiga boshqa
    yo'l bilan ilova qilingan bo'lsa, (4) tizim PATH'idagi `ffmpeg`.
    Hech biri topilmasa `None` — chaqiruvchi video-only fallback qiladi
    (xato emas)."""
    try:
        import imageio_ffmpeg
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and os.path.isfile(bundled):
            return bundled
    except Exception:  # noqa: BLE001 — topilmasa keyingi variantlarga o'tamiz
        pass

    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe"))
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(os.path.join(meipass, "ffmpeg.exe"))
    else:
        candidates.append(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "ffmpeg.exe",
        ))
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return shutil.which("ffmpeg")


class _OmborCameraBufferWorker(QThread):
    """Bitta ombor kamerasidan doimiy fon rejimida kadr o'qib, oxirgi
    BUFFER_SECONDS soniyalik aylanma buferda (vaqt belgisi bilan birga)
    saqlaydi. Bufer ikkita oqim (bu worker va uni o'qiydigan yozuvchi)
    tomonidan bir vaqtda ishlatilgani uchun `threading.Lock` bilan
    himoyalangan."""
    error = pyqtSignal(str)

    def __init__(self, camera):
        super().__init__()
        self.camera = camera
        self._running = False
        self._lock = threading.Lock()
        self._buffer: deque = deque()  # (monotonic_ts, frame)
        self.frame_size: tuple | None = None
        # Startup qurilma-tekshiruvi (176-177-qadamlar) shu orqali
        # "haqiqatan ham kadr olayaptimi" deb bilib oladi — ALOHIDA
        # kamera ulanishi ochmasdan (bir kamerani ikki joy bir vaqtda
        # ochishga urinsa odatda ishlamay qoladi).
        self.last_frame_at = 0.0

    def run(self):
        is_rtsp = self.camera.connection_type == "rtsp"
        if is_rtsp:
            source = build_rtsp_url(
                self.camera.rtsp_url, self.camera.rtsp_username or "", self.camera.rtsp_password or "",
            )
            cap = cv2.VideoCapture(source)
        else:
            cap = cv2.VideoCapture(self.camera.usb_index, cv2.CAP_DSHOW)

        if not cap.isOpened():
            self.error.emit(f"Ombor kamerasiga ulanib bo'lmadi (kamera #{self.camera.id}).")
            return

        interval = 1.0 / CAPTURE_FPS
        self._running = True
        while self._running:
            ok, frame = cap.read()
            if not ok:
                self.error.emit(f"Ombor kamerasidan tasvir kelmayapti (kamera #{self.camera.id}).")
                break
            if self.frame_size is None:
                h, w = frame.shape[:2]
                self.frame_size = (w, h)
            now = time.monotonic()
            self.last_frame_at = now
            with self._lock:
                self._buffer.append((now, frame))
                cutoff = now - BUFFER_SECONDS
                while self._buffer and self._buffer[0][0] < cutoff:
                    self._buffer.popleft()
            self.msleep(int(interval * 1000))

        cap.release()

    def stop(self):
        self._running = False
        self.wait(2000)

    def frames_from(self, since_ts: float):
        """`since_ts`dan (monotonic) keyingi barcha (vaqt, freym) juftliklari,
        vaqt bo'yicha tartiblangan holda."""
        with self._lock:
            return [item for item in self._buffer if item[0] >= since_ts]


class _ClipWriterWorker(QThread):
    """Bitta voqea uchun bitta kamera klipini yozadi: `stop_signaled`
    o'rnatilishini kutadi, so'ng yana POST_SECONDS kutadi (buferga oxirgi
    kadrlar to'planishi uchun), keyin [start_ts; hozir] oralig'idagi
    kadrlarni mp4 fayliga yozadi. Agar `mic_worker` berilgan bo'lsa,
    xuddi shu oraliqdagi audio ham yozilib, `ffmpeg` orqali videoga
    birlashtiriladi (topilmasa — video ovozsiz saqlanadi)."""
    saved = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, buffer_worker: _OmborCameraBufferWorker, start_ts: float, out_path: str,
                 mic_worker: MicBufferWorker | None = None):
        super().__init__()
        self._buffer_worker = buffer_worker
        self._mic_worker = mic_worker
        self._start_ts = start_ts
        self._out_path = out_path
        self._stop_event = threading.Event()

    def signal_stop(self):
        self._stop_event.set()

    def run(self):
        # Voqea tugashini (yoki xavfsizlik uchun maksimal 5 daqiqani) kutamiz.
        self._stop_event.wait(timeout=300)
        time.sleep(POST_SECONDS)

        frames = self._buffer_worker.frames_from(self._start_ts)
        if not frames or self._buffer_worker.frame_size is None:
            self.failed.emit("Kameradan kadr olinmadi — video yozilmadi.")
            return

        video_tmp_path = self._out_path + ".video.mp4"
        w, h = self._buffer_worker.frame_size
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(video_tmp_path, fourcc, CAPTURE_FPS, (w, h))
        try:
            for _, frame in frames:
                if frame.shape[1::-1] != (w, h):
                    frame = cv2.resize(frame, (w, h))
                writer.write(frame)
        finally:
            writer.release()

        final_path = self._mux_with_audio(video_tmp_path)
        self.saved.emit(final_path)

    def _mux_with_audio(self, video_tmp_path: str) -> str:
        """Mikrofon sozlangan bo'lsa audio yozadi va `ffmpeg` orqali
        videoga birlashtiradi. Har qanday bosqichda audio/ffmpeg
        muvaffaqiyatsiz bo'lsa — video-only fayl saqlanadi (xatosiz,
        jimgina pasayish)."""
        if self._mic_worker is None:
            os.replace(video_tmp_path, self._out_path)
            return self._out_path

        audio_tmp_path = self._out_path + ".audio.wav"
        has_audio = self._mic_worker.write_wav_from(self._start_ts, audio_tmp_path)
        if not has_audio:
            os.replace(video_tmp_path, self._out_path)
            return self._out_path

        ffmpeg_path = find_ffmpeg()
        if not ffmpeg_path:
            # ffmpeg topilmasa — audio alohida .wav sifatida saqlanadi
            # (yo'qotilmaydi), video esa ovozsiz o'z nomi bilan saqlanadi.
            os.replace(video_tmp_path, self._out_path)
            return self._out_path

        try:
            # `CREATE_NO_WINDOW` — aks holda ffmpeg (konsol dasturi)
            # ishga tushganda qora konsol oynasi bir zumga chaqib
            # chiqadi (kiosk-rejim uchun noqulay) — jarayon fonda,
            # ko'rinmasdan ishlaydi.
            subprocess.run(
                [
                    ffmpeg_path, "-y",
                    "-i", video_tmp_path,
                    "-i", audio_tmp_path,
                    "-c:v", "copy", "-c:a", "aac", "-shortest",
                    self._out_path,
                ],
                check=True, capture_output=True, timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            os.remove(video_tmp_path)
            os.remove(audio_tmp_path)
            return self._out_path
        except Exception:  # noqa: BLE001 — mux muvaffaqiyatsiz bo'lsa video-only fallback
            if os.path.exists(self._out_path):
                try:
                    os.remove(self._out_path)
                except OSError:
                    pass
            os.replace(video_tmp_path, self._out_path)
            return self._out_path


class CameraRecorderService(QObject):
    """Barcha ombor kameralarini boshqaradi — foydalanuvchiga ko'rinmaydi,
    butun dastur bo'ylab fonda ishlaydi (xuddi `ScannerService` kabi).
    Sozlangan ombor kamerasi bo'lmasa, xizmat shunchaki hech narsa
    qilmaydi (barcha metodlar xavfsiz no-op)."""

    clip_saved = pyqtSignal(str, str)  # (event_id, fayl_yo'li)
    clip_failed = pyqtSignal(str, str)  # (event_id, xabar)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buffer_workers: dict[int, _OmborCameraBufferWorker] = {}
        self._mic_workers: dict[int, MicBufferWorker] = {}
        self._active_writers: dict[str, list[_ClipWriterWorker]] = {}
        self.reload()

    def reload(self):
        """Sozlangan ombor kameralari ro'yxati DB'dan qayta o'qiladi —
        sozlamalar o'zgarganda (kamera qo'shilgan/o'chirilgan) chaqiriladi."""
        self.stop()
        for cam in db.list_all_ombor_cameras():
            worker = _OmborCameraBufferWorker(cam)
            worker.start()
            self._buffer_workers[cam.id] = worker
            if cam.mic_device_name:
                mic_worker = MicBufferWorker(cam.mic_device_name)
                mic_worker.start()
                self._mic_workers[cam.id] = mic_worker

    def stop(self):
        for worker in self._buffer_workers.values():
            worker.stop()
        self._buffer_workers.clear()
        for mic_worker in self._mic_workers.values():
            mic_worker.stop()
        self._mic_workers.clear()

    def connected_camera_count(self, within_seconds: float = 3.0) -> tuple[int, int]:
        """(jonli ishlayotgan, jami sozlangan) — startup qurilma-tekshiruvi
        shu orqali so'raydi, ALOHIDA kamera ulanishi ochmasdan."""
        total = len(self._buffer_workers)
        working = sum(
            1 for w in self._buffer_workers.values()
            if (time.monotonic() - w.last_frame_at) < within_seconds
        )
        return working, total

    def start_event(self, event_id: str, warehouse_id: int | None, reason: str):
        """Voqea (masalan tarozi tekshiruvi yoki QR skaneri) boshlanganda
        chaqiriladi. `warehouse_id=None` bo'lsa — hozircha aniq ombor
        noma'lum bo'lgani uchun (masalan xom ashyo so'rovlari muayyan
        omborga bog'lanmagan) BARCHA sozlangan ombor kameralari uchun
        yoziladi."""
        if not self._buffer_workers:
            return  # hech qanday ombor kamerasi sozlanmagan — no-op

        cameras = [
            w for w in self._buffer_workers.values()
            if warehouse_id is None or w.camera.warehouse_id == warehouse_id
        ]
        if not cameras:
            return

        start_ts = time.monotonic() - PRE_SECONDS
        warehouses = {wh.id: wh.nomi for wh in db.list_warehouses()}
        writers = []
        for buf_worker in cameras:
            wh_nomi = warehouses.get(buf_worker.camera.warehouse_id, "ombor")
            camera_label = self._camera_label(buf_worker.camera)
            out_path = self._build_out_path(wh_nomi, camera_label, reason)
            mic_worker = self._mic_workers.get(buf_worker.camera.id)
            writer = _ClipWriterWorker(buf_worker, start_ts, out_path, mic_worker=mic_worker)
            writer.saved.connect(lambda path, eid=event_id: self.clip_saved.emit(eid, path))
            writer.failed.connect(lambda msg, eid=event_id: self.clip_failed.emit(eid, msg))
            writer.start()
            writers.append(writer)
        self._active_writers[event_id] = writers

    def stop_event(self, event_id: str):
        """Voqea tugaganda (masalan so'rov tasdiqlangan/rad etilgan)
        chaqiriladi — har bir tegishli klip yozuvchisiga to'xtash
        signalini beradi (yozuvchi o'zi yana POST_SECONDS kutib, keyin
        faylni saqlab, o'zi tugaydi)."""
        writers = self._active_writers.pop(event_id, None)
        if not writers:
            return
        for writer in writers:
            writer.signal_stop()

    @staticmethod
    def _camera_label(camera) -> str:
        """"Kamera 1", "Kamera 2" — DB'dagi ichki `id` o'rniga, shu
        ombordagi kameralar orasidagi tartib raqami (foydalanuvchi
        so'ragan, tushunarli nomlash uchun: DB id'lari tasodifiy/katta
        bo'lishi mumkin, "kamera1"/"kamera2" esa har doim 1dan boshlanadi)."""
        if camera.warehouse_id is None:
            return f"kamera{camera.id}"
        cams = db.list_cameras_for_warehouse(camera.warehouse_id)
        for idx, c in enumerate(cams, start=1):
            if c.id == camera.id:
                return f"kamera{idx}"
        return f"kamera{camera.id}"

    @staticmethod
    def _build_out_path(warehouse_nomi: str, camera_label: str, reason: str) -> str:
        safe_nomi = "".join(c if c.isalnum() else "_" for c in warehouse_nomi).strip("_") or "ombor"
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        ts = now.strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_nomi}_{camera_label}_{reason}_{ts}.mp4"
        return os.path.join(db.recordings_dir_for_date(date_str), filename)
