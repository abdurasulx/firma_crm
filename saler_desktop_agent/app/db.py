"""Saler Agent — mahalliy sozlamalarni saqlash.

Bu dastur juda kichik (login ma'lumotlari + token, xolos) — to'liq
SQLite sxemasi shart emas, oddiy JSON fayl yetarli. `desktop_agent/app/
db.py`ga tegilmagan, mustaqil."""
import json
import os

APPDATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SalerAgent")
SETTINGS_PATH = os.path.join(APPDATA_DIR, "settings.json")

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    os.makedirs(APPDATA_DIR, exist_ok=True)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            _cache = {}
    else:
        _cache = {}
    return _cache


def get_setting(key: str, default: str = "") -> str:
    return _load().get(key, default)


def set_setting(key: str, value: str) -> None:
    data = _load()
    data[key] = value
    os.makedirs(APPDATA_DIR, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
