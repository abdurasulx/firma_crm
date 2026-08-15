"""Saler Agent — ERP REST API bilan aloqa.

Bu fayl `desktop_agent/app/api_client.py`dan MUSTAQIL — savdogar
stansiyasi faqat sotuv uchun kerak bo'lgan kichik funksiyalar to'plamiga
ega (login, badge skanerlash, mahsulot izlash, sotuvni yakunlash,
heartbeat/logout). Ombor/kamera/tarozi/ishlab chiqarish bilan bog'liq
hech narsa yo'q — ular `desktop_agent`ga tegishli, bu yerga
ko'chirilmagan."""
from urllib.parse import urlparse

import requests

TIMEOUT = 10
BASE_DOMAIN = "stockfirm.uz"


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _enforce_https_for_production(url: str) -> str:
    if "127.0.0.1" in url or "localhost" in url:
        return url
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def normalize_server_url(raw: str) -> str:
    raw = (raw or "").strip()
    if "://" in raw:
        return _enforce_https_for_production(raw.rstrip("/"))
    return f"https://{raw}.{BASE_DOMAIN}"


def subdomain_from_server_url(server_url: str) -> str:
    host = urlparse(server_url.strip()).hostname or ""
    return host.split(".")[0] if host else ""


def parse_server_input(raw: str) -> tuple[str, str]:
    raw = (raw or "").strip()
    if "@" in raw:
        subdomain_part, url_part = raw.split("@", 1)
        url_part = url_part.strip()
        if "://" not in url_part:
            url_part = "http://" + url_part
        return _enforce_https_for_production(url_part.rstrip("/")), subdomain_part.strip()
    server_url = normalize_server_url(raw)
    return server_url, subdomain_from_server_url(server_url)


def _handle_error_response(resp):
    if resp.status_code in (401, 403, 404, 400):
        try:
            raise ApiError(resp.json().get("detail", "So'rov bajarilmadi."), status_code=resp.status_code)
        except ValueError:
            raise ApiError("So'rov bajarilmadi.", status_code=resp.status_code)
    if resp.status_code not in (200, 201):
        raise ApiError(f"Server xatosi (HTTP {resp.status_code}).")


def _request(method: str, server_url: str, token: str | None, path: str,
             params: dict | None = None, data: dict | None = None, json_body: dict | None = None) -> dict:
    if not server_url:
        raise ApiError("Server manzili kiritilmagan.")
    url = server_url.rstrip("/") + path
    headers = {"Authorization": f"Token {token}"} if token else {}
    try:
        resp = requests.request(method, url, params=params, data=data, json=json_body, headers=headers, timeout=TIMEOUT)
    except requests.exceptions.ConnectionError:
        raise ApiError(f"Serverga ulanib bo'lmadi: {url}")
    except requests.exceptions.Timeout:
        raise ApiError("Serverdan javob kutish vaqti tugadi.")
    except requests.exceptions.RequestException as exc:
        raise ApiError(f"So'rov xatosi: {exc}")

    _handle_error_response(resp)
    try:
        return resp.json()
    except ValueError:
        raise ApiError("Serverdan noto'g'ri javob keldi (JSON emas).")


def station_login(server_url: str, subdomain: str, username: str, password: str) -> dict:
    """Stansiya login/parol orqali shaxsiy token oladi (mavjud
    `/api/agent/login/` — faqat `type='desktop_agent'` hisoblar uchun
    ishlaydi, xuddi asosiy Desktop Agent'dagidek)."""
    if not subdomain or not username or not password:
        raise ApiError("Firma nomi, login va parol kiritilishi shart.")
    return _request("POST", server_url, None, "/api/agent/login/", data={
        "subdomain": subdomain, "username": username, "password": password,
    })


def scan_badge(server_url: str, token: str, kod: str) -> dict:
    """Savdogar shaxsiy QR badge'ini (yoki HID skaner bilan) skanerlaganda
    — kim ekanini aniqlaydi va sessiya-token beradi (universal `/api/agent/
    scan/` endpointi, `type='badge'` javobi kutiladi)."""
    data = _request("GET", server_url, token, "/api/agent/scan/", params={"kod": kod})
    if data.get("type") not in (None, "badge"):
        raise ApiError("Bu QR/shtrix-kod xodim badge'i emas.")
    return data


def lookup_mahsulot(server_url: str, token: str, kod: str) -> dict:
    """Shtrix-kod bo'yicha savdogar sotadigan mahsulotni topadi."""
    return _request("GET", server_url, token, "/api/agent/saler/mahsulot/", params={"kod": kod})


def finalize_sale(server_url: str, token: str, session_token: str, oluvchining_ismi: str, st: str, items: list) -> dict:
    """Savatni yakuniy sotuv sifatida saqlaydi. `items`:
    `[{"mahsulot_id": int, "miqdor": float}, ...]`."""
    return _request("POST", server_url, token, "/api/agent/saler/sotuv/", json_body={
        "session_token": session_token, "oluvchining_ismi": oluvchining_ismi, "st": st, "items": items,
    })


def send_heartbeat(server_url: str, token: str) -> dict:
    return _request("POST", server_url, token, "/api/agent/heartbeat/", data={})


def send_logout(server_url: str, token: str) -> dict:
    return _request("POST", server_url, token, "/api/agent/logout/", data={})
