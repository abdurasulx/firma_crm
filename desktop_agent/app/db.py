"""
Mahalliy SQLite qatlami — hozircha CRM backend bilan bog'lanmagan
(birinchi bosqich). Omborlar va ularga biriktirilgan kameralar shu yerda
saqlanadi.
"""
import os
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


def _default_db_path() -> str:
    """PyInstaller `--onefile` bilan build qilingan holatda `__file__`
    har bir ishga tushirishda YANGI, vaqtinchalik `_MEI*` papkaga (masalan
    `...\\Temp\\_MEI102202\\app\\db.py`) ochiladi — shuning uchun avvalgi
    kod (`dirname(dirname(__file__))`) asosida DB yo'li har safar dastur
    qayta ochilganda BOSHQA joyga ko'rsatib, barcha sozlamalar (login,
    skaner turi, sinxronlangan omborlar) yo'qolib ketardi. Doimiy
    (foydalanuvchi profili ichidagi) papkadan foydalanish shart."""
    if getattr(sys, "frozen", False):
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(base, "StockFirmAgent")
    else:
        data_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "agent_data.db")


DB_PATH = _default_db_path()


def recordings_root_dir() -> str:
    """Video yozuvlari saqlanadigan asosiy papka — `.exe`ning o'zi bilan
    bir joyda (foydalanuvchi so'ragan: "exe oldida saved_videos" — DB/
    sozlamalar kabi yashirin `%LOCALAPPDATA%` ichida emas, balki dastur
    qayerga o'rnatilgan/ko'chirilgan bo'lsa, o'sha yerda, osongina
    topiladigan joyda). Rivojlanish (frozen bo'lmagan) rejimida loyiha
    ildizi ishlatiladi."""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "saved_videos")
    os.makedirs(path, exist_ok=True)
    return path


def recordings_dir_for_date(date_str: str) -> str:
    """`saved_videos/<YYYY-MM-DD>/` — har kun uchun alohida papka, video
    fayllarni sana bo'yicha topish/tozalash oson bo'lishi uchun."""
    path = os.path.join(recordings_root_dir(), date_str)
    os.makedirs(path, exist_ok=True)
    return path

SCHEMA = """
CREATE TABLE IF NOT EXISTS warehouses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    remote_id INTEGER NULL UNIQUE,
    nomi TEXT NOT NULL,
    manzil TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cameras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL CHECK(role IN ('ombor', 'skaner')),
    warehouse_id INTEGER NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    connection_type TEXT NOT NULL CHECK(connection_type IN ('usb', 'rtsp', 'hid')),
    usb_index INTEGER NULL,
    rtsp_url TEXT NULL,
    rtsp_username TEXT NULL,
    rtsp_password TEXT NULL,
    mic_device_name TEXT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # Eski (remote_id'siz) bazalar uchun yumshoq migratsiya
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(warehouses)").fetchall()]
        if "remote_id" not in cols:
            conn.execute("ALTER TABLE warehouses ADD COLUMN remote_id INTEGER NULL")

        # Eski bazalarda `cameras.connection_type` CHECK cheklovi 'hid'ni
        # bilmasligi mumkin (qo'lda skaner qo'shilgunga qadar yaratilgan
        # bazalar) — SQLite'da CHECK cheklovini ALTER qilib bo'lmaydi,
        # shuning uchun jadval qayta quriladi (ma'lumotlar saqlanib qoladi).
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='cameras'"
        ).fetchone()
        if row and "'hid'" not in row["sql"]:
            conn.executescript("""
                ALTER TABLE cameras RENAME TO cameras_old;
                CREATE TABLE cameras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL CHECK(role IN ('ombor', 'skaner')),
                    warehouse_id INTEGER NULL REFERENCES warehouses(id) ON DELETE CASCADE,
                    connection_type TEXT NOT NULL CHECK(connection_type IN ('usb', 'rtsp', 'hid')),
                    usb_index INTEGER NULL,
                    rtsp_url TEXT NULL,
                    rtsp_username TEXT NULL,
                    rtsp_password TEXT NULL,
                    mic_device_name TEXT NULL,
                    created_at TEXT NOT NULL
                );
                INSERT INTO cameras (id, role, warehouse_id, connection_type, usb_index, rtsp_url, rtsp_username, rtsp_password, created_at)
                SELECT id, role, warehouse_id, connection_type, usb_index, rtsp_url, rtsp_username, rtsp_password, created_at FROM cameras_old;
                DROP TABLE cameras_old;
            """)

        # `mic_device_name` — ombor kamerasiga (ixtiyoriy) mikrofon
        # biriktirish uchun (92-qadam, ovoz yozish). Yuqoridagi to'liq
        # jadval-qayta-qurish yo'lidan o'tmagan (allaqachon 'hid'ga ega)
        # eski bazalar uchun oddiy ADD COLUMN yetarli.
        cam_cols = [r["name"] for r in conn.execute("PRAGMA table_info(cameras)").fetchall()]
        if "mic_device_name" not in cam_cols:
            conn.execute("ALTER TABLE cameras ADD COLUMN mic_device_name TEXT NULL")


# ── Sozlamalar (server URL, agent token) ─────────────────────────────────

def get_setting(key: str, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


@dataclass
class Warehouse:
    id: int
    nomi: str
    manzil: str
    remote_id: Optional[int] = None


@dataclass
class Camera:
    id: int
    role: str
    warehouse_id: Optional[int]
    connection_type: str
    usb_index: Optional[int]
    rtsp_url: Optional[str]
    rtsp_username: Optional[str]
    rtsp_password: Optional[str]
    mic_device_name: Optional[str] = None


# ── Omborlar ──────────────────────────────────────────────────────────────

def list_warehouses():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM warehouses ORDER BY nomi").fetchall()
        return [Warehouse(r["id"], r["nomi"], r["manzil"], r["remote_id"]) for r in rows]


def create_warehouse(nomi: str, manzil: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO warehouses (nomi, manzil, created_at) VALUES (?, ?, ?)",
            (nomi.strip(), manzil.strip(), datetime.now().isoformat()),
        )


def update_warehouse(warehouse_id: int, nomi: str, manzil: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE warehouses SET nomi = ?, manzil = ? WHERE id = ?",
            (nomi.strip(), manzil.strip(), warehouse_id),
        )


def delete_warehouse(warehouse_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM warehouses WHERE id = ?", (warehouse_id,))


def sync_warehouses_from_remote(remote_omborlar: list):
    """CRM'dan kelgan omborlar ro'yxatini (`[{'id','nomi','manzil'}, ...]`)
    mahalliy bazaga `remote_id` bo'yicha upsert qiladi. Qo'lda (remote_id'siz)
    qo'shilgan omborlarga tegilmaydi. CRM'da o'chirilgan (endi ro'yxatda
    yo'q) omborlar ham mahalliy bazadan o'chiriladi (kamerasi bilan birga)."""
    with get_conn() as conn:
        remote_ids = [o["id"] for o in remote_omborlar]
        for o in remote_omborlar:
            existing = conn.execute(
                "SELECT id FROM warehouses WHERE remote_id = ?", (o["id"],)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE warehouses SET nomi = ?, manzil = ? WHERE id = ?",
                    (o["nomi"], o.get("manzil") or "", existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO warehouses (remote_id, nomi, manzil, created_at) VALUES (?, ?, ?, ?)",
                    (o["id"], o["nomi"], o.get("manzil") or "", datetime.now().isoformat()),
                )
        if remote_ids:
            placeholders = ",".join("?" * len(remote_ids))
            conn.execute(
                f"DELETE FROM warehouses WHERE remote_id IS NOT NULL AND remote_id NOT IN ({placeholders})",
                remote_ids,
            )
        else:
            conn.execute("DELETE FROM warehouses WHERE remote_id IS NOT NULL")


# ── Kameralar ─────────────────────────────────────────────────────────────
# Ombor (role='ombor') — bitta omborga BIR NECHTA kamera biriktirilishi
# mumkin (ba'zilari USB, ba'zilari RTSP orqali) — shuning uchun to'liq CRUD
# (list/add/update/delete) taqdim etiladi. Skaner (role='skaner') esa
# hamon bitta qurilma — u yagona (get/save) funksiyalar bilan qoladi.

def list_cameras_for_warehouse(warehouse_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cameras WHERE role = 'ombor' AND warehouse_id = ? ORDER BY created_at",
            (warehouse_id,),
        ).fetchall()
        return [_row_to_camera(r) for r in rows]


def list_all_ombor_cameras():
    """Barcha omborlarga biriktirilgan barcha kameralar (firma bo'ylab) —
    voqea-video yozish xizmati (`camera_recorder_service.py`) ishga
    tushganda har bir kamera uchun aylanma-bufer oqim ochish uchun."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cameras WHERE role = 'ombor' ORDER BY warehouse_id, created_at",
        ).fetchall()
        return [_row_to_camera(r) for r in rows]


def get_camera(camera_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,)).fetchone()
        return _row_to_camera(row)


def add_camera_for_warehouse(warehouse_id: int, connection_type: str, usb_index=None,
                              rtsp_url=None, rtsp_username=None, rtsp_password=None,
                              mic_device_name=None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO cameras
               (role, warehouse_id, connection_type, usb_index, rtsp_url, rtsp_username, rtsp_password, mic_device_name, created_at)
               VALUES ('ombor', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (warehouse_id, connection_type, usb_index, rtsp_url, rtsp_username, rtsp_password,
             mic_device_name, datetime.now().isoformat()),
        )


def update_camera(camera_id: int, connection_type: str, usb_index=None,
                   rtsp_url=None, rtsp_username=None, rtsp_password=None,
                   mic_device_name=None):
    with get_conn() as conn:
        conn.execute(
            """UPDATE cameras SET connection_type = ?, usb_index = ?, rtsp_url = ?,
               rtsp_username = ?, rtsp_password = ?, mic_device_name = ? WHERE id = ?""",
            (connection_type, usb_index, rtsp_url, rtsp_username, rtsp_password, mic_device_name, camera_id),
        )


def delete_camera(camera_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))


def get_scanner_camera():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM cameras WHERE role = 'skaner' LIMIT 1").fetchone()
        return _row_to_camera(row)


def save_scanner_camera(connection_type: str, usb_index=None,
                         rtsp_url=None, rtsp_username=None, rtsp_password=None):
    with get_conn() as conn:
        conn.execute("DELETE FROM cameras WHERE role = 'skaner'")
        conn.execute(
            """INSERT INTO cameras
               (role, warehouse_id, connection_type, usb_index, rtsp_url, rtsp_username, rtsp_password, created_at)
               VALUES ('skaner', NULL, ?, ?, ?, ?, ?, ?)""",
            (connection_type, usb_index, rtsp_url, rtsp_username, rtsp_password, datetime.now().isoformat()),
        )


def _row_to_camera(row) -> Optional[Camera]:
    if row is None:
        return None
    return Camera(
        id=row["id"], role=row["role"], warehouse_id=row["warehouse_id"],
        connection_type=row["connection_type"], usb_index=row["usb_index"],
        rtsp_url=row["rtsp_url"], rtsp_username=row["rtsp_username"], rtsp_password=row["rtsp_password"],
        mic_device_name=row["mic_device_name"] if "mic_device_name" in row.keys() else None,
    )
