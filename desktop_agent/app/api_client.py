"""CRM REST API bilan aloqa."""
from urllib.parse import urlparse

import requests

TIMEOUT = 10
# Barcha StockFirm mijozlari bitta umumiy domenda ishlaydi (faqat
# subdomen farq qiladi) — shuning uchun foydalanuvchidan to'liq URL
# so'ramasdan, faqat firma nomini (subdomenni) so'rab, qolganini shu
# yerdan qurib olamiz.
BASE_DOMAIN = "stockfirm.uz"


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def normalize_server_url(raw: str) -> str:
    """Foydalanuvchi kiritgan qiymatni to'liq server manziliga aylantiradi.
    Oddiy holatda faqat firma nomi/subdomeni kiritiladi (masalan
    "birzumda") — shundan `https://birzumda.stockfirm.uz` avtomatik
    quriladi. Agar allaqachon to'liq manzil kiritilgan bo'lsa (`://` bor —
    masalan mahalliy/test server uchun) — o'zgarishsiz qoldiriladi."""
    raw = (raw or "").strip()
    if "://" in raw:
        return raw.rstrip("/")
    return f"https://{raw}.{BASE_DOMAIN}"


def subdomain_from_server_url(server_url: str) -> str:
    """Server manzilidan firma subdomenini ajratib oladi (masalan
    `https://birzumda.stockfirm.uz` -> `birzumda`) — xuddi CRM'ning o'zi
    (`CompanyMiddleware`, `host.split('.')[0]`) qanday aniqlasa, xuddi
    shunday. Foydalanuvchi buni alohida maydonga qo'lda kiritmasligi
    uchun — server manzilining o'zida allaqachon bor."""
    host = urlparse(server_url.strip()).hostname or ""
    return host.split(".")[0] if host else ""


def parse_server_input(raw: str) -> tuple[str, str]:
    """"Firma nomi" maydoniga kiritilgan matnni `(server_url, subdomain)`
    juftligiga aylantiradi.

    Oddiy holat — faqat firma nomi kiritiladi (masalan "birzumda") —
    production manzili (`https://birzumda.stockfirm.uz`) avtomatik
    quriladi, subdomen ham shu nomning o'zi.

    Mahalliy/test server IP yoki "localhost" bo'lsa (masalan
    `http://127.0.0.1:8000`), manzilning o'zida firma nomi yo'q —
    subdomenni undan ajratib bo'lmaydi. Shuning uchun bunday hollarda
    "<subdomen>@<manzil>" formati qo'llab-quvvatlanadi, masalan:
    "birzumda@http://127.0.0.1:8000"."""
    raw = (raw or "").strip()
    if "@" in raw:
        subdomain_part, url_part = raw.split("@", 1)
        url_part = url_part.strip()
        if "://" not in url_part:
            url_part = "http://" + url_part
        return url_part.rstrip("/"), subdomain_part.strip()

    server_url = normalize_server_url(raw)
    return server_url, subdomain_from_server_url(server_url)


def _request(method: str, server_url: str, token: str, path: str,
             params: dict | None = None, data: dict | None = None, json_body: dict | None = None) -> dict:
    if not server_url:
        raise ApiError("Server manzili kiritilmagan.")
    if not token:
        raise ApiError("Token kiritilmagan.")

    url = server_url.rstrip("/") + path
    try:
        resp = requests.request(
            method, url, params=params, data=data, json=json_body,
            headers={"Authorization": f"Token {token}"}, timeout=TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        raise ApiError(f"Serverga ulanib bo'lmadi: {url}")
    except requests.exceptions.Timeout:
        raise ApiError("Serverdan javob kutish vaqti tugadi.")
    except requests.exceptions.RequestException as exc:
        raise ApiError(f"So'rov xatosi: {exc}")

    if resp.status_code == 401:
        try:
            raise ApiError(resp.json().get("detail", "Token noto'g'ri yoki eskirgan."), status_code=401)
        except ValueError:
            raise ApiError("Token noto'g'ri yoki eskirgan.", status_code=401)
    if resp.status_code == 404:
        raise ApiError("Topilmadi.")
    if resp.status_code == 400:
        try:
            raise ApiError(resp.json().get("detail", "Noto'g'ri so'rov."))
        except ValueError:
            raise ApiError("Noto'g'ri so'rov.")
    if resp.status_code not in (200, 201):
        raise ApiError(f"Server xatosi (HTTP {resp.status_code}).")

    try:
        return resp.json()
    except ValueError:
        raise ApiError("Serverdan noto'g'ri javob keldi (JSON emas).")


def _get(server_url: str, token: str, path: str, params: dict | None = None) -> dict:
    return _request("GET", server_url, token, path, params=params)


def _post(server_url: str, token: str, path: str, data: dict | None = None) -> dict:
    return _request("POST", server_url, token, path, data=data)


def _post_json(server_url: str, token: str, path: str, json_body: dict | None = None) -> dict:
    """`_post` kabi, lekin ro'yxat/dict kabi ichma-ich tuzilgan qiymatlarni
    (masalan `items`) to'g'ri uzatish uchun JSON tanasi bilan yuboradi —
    forma-kodlashda ro'yxatlar to'g'ri saqlanmaydi."""
    return _request("POST", server_url, token, path, json_body=json_body)


def station_login(server_url: str, subdomain: str, username: str, password: str):
    """Desktop Agent stansiyasi login/paroli orqali shaxsiy token oladi.
    Boshqa so'rovlardan farqli, bu chaqiruv hali tokensiz amalga oshiriladi.
    `server_url` va `subdomain` — `parse_server_input()` orqali "Firma
    nomi" maydonidagi bitta matndan hisoblab olinadi (caller tomonidan)."""
    if not server_url:
        raise ApiError("Server manzili kiritilmagan.")
    if not subdomain or not username or not password:
        raise ApiError("Firma nomi, login va parol kiritilishi shart.")

    url = server_url.rstrip("/") + "/api/agent/login/"
    try:
        resp = requests.post(
            url, data={"subdomain": subdomain, "username": username, "password": password}, timeout=TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        raise ApiError(f"Serverga ulanib bo'lmadi: {url}")
    except requests.exceptions.Timeout:
        raise ApiError("Serverdan javob kutish vaqti tugadi.")
    except requests.exceptions.RequestException as exc:
        raise ApiError(f"So'rov xatosi: {exc}")

    if resp.status_code in (401, 403, 404, 400):
        try:
            raise ApiError(resp.json().get("detail", "Kirish amalga oshmadi."))
        except ValueError:
            raise ApiError("Kirish amalga oshmadi.")
    if resp.status_code != 200:
        raise ApiError(f"Server xatosi (HTTP {resp.status_code}).")

    try:
        return resp.json()
    except ValueError:
        raise ApiError("Serverdan noto'g'ri javob keldi (JSON emas).")


def station_login_by_qr(server_url: str, subdomain: str, qr_payload: str):
    """Desktop Agent stansiyasi shifrlangan QR kod orqali (145-qadam)
    login qiladi — `station_login`ning QR-variant. `qr_payload` —
    veb CRM'da ko'rsatilgan `AGENTQR|<subdomain>|<shifrlangan_qism>`
    matnining uchinchi qismi (klient uni o'zgartirmasdan serverga
    yuboradi, dekriptlash faqat serverda bo'ladi)."""
    if not server_url:
        raise ApiError("Server manzili kiritilmagan.")
    if not subdomain or not qr_payload:
        raise ApiError("QR kod noto'g'ri formatda.")

    url = server_url.rstrip("/") + "/api/agent/login-by-qr/"
    try:
        resp = requests.post(
            url, data={"subdomain": subdomain, "qr_payload": qr_payload}, timeout=TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        raise ApiError(f"Serverga ulanib bo'lmadi: {url}")
    except requests.exceptions.Timeout:
        raise ApiError("Serverdan javob kutish vaqti tugadi.")
    except requests.exceptions.RequestException as exc:
        raise ApiError(f"So'rov xatosi: {exc}")

    if resp.status_code in (401, 403, 404, 400):
        try:
            raise ApiError(resp.json().get("detail", "Kirish amalga oshmadi."))
        except ValueError:
            raise ApiError("Kirish amalga oshmadi.")
    if resp.status_code != 200:
        raise ApiError(f"Server xatosi (HTTP {resp.status_code}).")

    try:
        return resp.json()
    except ValueError:
        raise ApiError("Serverdan noto'g'ri javob keldi (JSON emas).")


def verify_kiosk_unlock(server_url: str, subdomain: str, qr_payload: str):
    """Kiosk-qulfini ochish uchun `AGENTQR|...` kodini serverga tekshirtiradi
    — `station_login_by_qr`dan farqli, bu **hech qanday token yaratmaydi/
    o'zgartirmaydi**, faqat skanerlangan QR chindan ham firma egasiga
    tegishli ekanini tasdiqlaydi (yoki rad etadi). Stansiya hali tokensiz
    (login qilinmagan) ham chaqirilishi mumkin — shuning uchun boshqa
    so'rovlar kabi `Authorization` header talab qilmaydi."""
    if not server_url:
        raise ApiError("Server manzili kiritilmagan.")
    if not subdomain or not qr_payload:
        raise ApiError("QR kod noto'g'ri formatda.")

    url = server_url.rstrip("/") + "/api/agent/verify-kiosk-unlock/"
    try:
        resp = requests.post(
            url, data={"subdomain": subdomain, "qr_payload": qr_payload}, timeout=TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        raise ApiError(f"Serverga ulanib bo'lmadi: {url}")
    except requests.exceptions.Timeout:
        raise ApiError("Serverdan javob kutish vaqti tugadi.")
    except requests.exceptions.RequestException as exc:
        raise ApiError(f"So'rov xatosi: {exc}")

    if resp.status_code in (401, 403, 404, 400):
        try:
            raise ApiError(resp.json().get("detail", "QR kod tasdiqlanmadi."))
        except ValueError:
            raise ApiError("QR kod tasdiqlanmadi.")
    if resp.status_code != 200:
        raise ApiError(f"Server xatosi (HTTP {resp.status_code}).")

    try:
        return resp.json()
    except ValueError:
        raise ApiError("Serverdan noto'g'ri javob keldi (JSON emas).")


def fetch_omborlar(server_url: str, token: str):
    """CRM'dan omborlar ro'yxatini oladi. Xato bo'lsa `ApiError` ko'taradi."""
    data = _get(server_url, token, "/api/agent/omborlar/")
    return data.get("omborlar", []), data.get("company", "")


def resolve_badge(server_url: str, token: str, kod: str):
    """Skanerlangan QR kodni (XodimBadge.kod) xodim ma'lumotiga aylantiradi."""
    try:
        return _get(server_url, token, "/api/agent/badge-scan/", params={"kod": kod})
    except ApiError as exc:
        if str(exc) == "Topilmadi.":
            raise ApiError("Bu QR kod hech qanday xodimga tegishli emas.")
        raise


def scan(server_url: str, token: str, kod: str, session_token: str | None = None):
    """Universal skanerlash — skanerlangan kod xodim badge'i (`type=
    'badge'`, xuddi `resolve_badge()` kabi, sessiya boshlash uchun),
    material so'rovi QR kodi (`type='material_request'`, faqat ma'lumot
    ko'rsatish uchun), Serial QR (`type='serial'`) yoki vazifa QR kodi
    (`type='task'`, 103-qadam) bo'lishi mumkin — server o'zi farqlaydi,
    javobdagi `type` maydoniga qarab ishlatiladi. `session_token` — faol
    badge-sessiya bo'lsa yuboriladi (vazifa QR kodini kim skanerlaganini
    bildiradi uchun; boshqa turlarga ta'sir qilmaydi)."""
    params = {"kod": kod}
    if session_token:
        params["session_token"] = session_token
    try:
        return _get(server_url, token, "/api/agent/scan/", params=params)
    except ApiError as exc:
        if str(exc) == "Topilmadi.":
            raise ApiError("Bu QR kod hech qanday narsaga tegishli emas.")
        raise


def fetch_material_requests(server_url: str, token: str, session_token: str):
    """Xodim uchun kutilayotgan xom ashyo so'rovlari ro'yxati (eng eskisi
    birinchi). `session_token` — `resolve_badge()` javobidagi
    `session_token`, badge muvaffaqiyatli skanerlangandan keyin serverdan
    olinadi (mijoz `user_id`ni o'zi tanlab yubora olmaydi)."""
    data = _get(server_url, token, "/api/agent/material-requests/", params={"session_token": session_token})
    return data.get("so_rovlar", [])


def fetch_my_task_pickups(server_url: str, token: str, session_token: str):
    """Badge sessiyasi boshlanganda avtomatik chaqiriladi — ishlab
    chiqaruvchining o'ziga tayinlangan (110-qadam, o'zi yaratgan yoki ega
    biriktirgan) vazifalaridagi hali tortilmagan xom ashyo qatorlari —
    alohida vazifa-QR skanerlash shart emas."""
    data = _get(server_url, token, "/api/agent/my-task-pickups/", params={"session_token": session_token})
    return data.get("so_rovlar", [])


def acknowledge_material_request(server_url: str, token: str, request_id: int, session_token: str):
    """Xodim "Qabul qildim" tugmasini bosganda chaqiriladi — so'rovning
    `acknowledged_at`ini belgilaydi (status'ga tegmaydi)."""
    return _post(server_url, token, f"/api/agent/material-requests/{request_id}/acknowledge/",
                 data={"session_token": session_token})


def weigh_material_request(server_url: str, token: str, request_id: int, session_token: str, measured_qty: float):
    """Xom ashyo so'rovini tarozi qiymati bilan tekshiradi. Norma ichida
    bo'lsa server tomonda avtomatik tasdiqlanadi (omborchi tasdig'i
    o'rnini bosadi) — javobdagi `approved` maydoniga qarab natija
    ko'rsatiladi (`ApiError` faqat tarmoq/token xatolarida ko'tariladi,
    "normadan chetlashish" oddiy — kutilgan — natija hisoblanadi)."""
    return _post(server_url, token, f"/api/agent/material-requests/{request_id}/weigh/", data={
        "session_token": session_token, "measured_qty": measured_qty,
    })


def weigh_task_pickup(server_url: str, token: str, pickup_id: int, session_token: str, measured_qty: float):
    """`weigh_material_request`ning "Vazifalar paneli" (103-qadam) varianti
    — vazifaning bitta BOM-komponentini tarozi qiymati bilan tekshiradi.
    Agar bu vazifaning oxirgi tasdiqlanmagan komponenti bo'lsa, javobda
    `materials_ready=True` qaytadi (159-qadamdan keyin) — QR chop etish
    bu yerda emas, pazanda veb dashboardda "Ish bitdi" bosgach, KEYINGI
    badge skanida (`fetch_pending_print_batch`) sodir bo'ladi."""
    return _post(server_url, token, f"/api/agent/task-pickup/{pickup_id}/weigh/", data={
        "session_token": session_token, "measured_qty": measured_qty,
    })


def fetch_pending_print_batch(server_url: str, token: str, session_token: str):
    """Badge sessiyasi boshlanganda chaqiriladi (159-qadam) — veb
    dashboardda "Ish bitdi" bosilib, hali shu stansiyada chop etilmagan
    yorliq partiyasi bo'lsa, shuni qaytaradi (`None` — topilmasa)."""
    data = _get(server_url, token, "/api/agent/pending-print-batch/", params={"session_token": session_token})
    return data.get("batch")


def mark_batch_printed(server_url: str, token: str, session_token: str, batch_id: int):
    """Yorliqlar chop etib bo'lingach (yoki chop etadigan hech narsa
    topilmagach) chaqiriladi — shu partiya keyingi skanlarda qayta chop
    etishga taklif qilinmasligi uchun."""
    return _post(server_url, token, "/api/agent/mark-batch-printed/", data={
        "session_token": session_token, "batch_id": batch_id,
    })


def fetch_miqdor_requests(server_url: str, token: str, session_token: str):
    """Ishlab chiqaruvchi uchun kutilayotgan "miqdor qo'shish" so'rovlari
    (82-qadam) — faqat Desktop Agent stansiyasi sotib olingan firmalarda
    hosil bo'ladi."""
    data = _get(server_url, token, "/api/agent/miqdor-qoshish/", params={"session_token": session_token})
    return data.get("so_rovlar", [])


def approve_miqdor_qoshish(server_url: str, token: str, request_id: int, session_token: str):
    """Ishlab chiqaruvchi Desktop Agent'da "Tasdiqlash"ni bosganda
    chaqiriladi — zaxira oshadi, Serial/QR generatsiya bo'ladi (agar
    mahsulotda yoqilgan bo'lsa), javobda chop etish sahifasi manzili
    (`print_url`) qaytadi."""
    return _post(server_url, token, f"/api/agent/miqdor-qoshish/{request_id}/tasdiqlash/", data={
        "session_token": session_token,
    })


def scan_delivery_serial(server_url: str, token: str, session_token: str, kod: str):
    """Yetkazib beruvchi "yuklama" (yuk olish) sessiyasida har bir
    mahsulot donasining Serial QR kodini skanerlaganda chaqiriladi —
    savatga qo'shish uchun mahsulot ma'lumotini qaytaradi (hisoblash
    mijoz — Desktop Agent — tomonida saqlanadi)."""
    return _post(server_url, token, "/api/agent/yuklama/skaner/", data={
        "session_token": session_token, "kod": kod,
    })


def finalize_yuklama(server_url: str, token: str, session_token: str, items: list):
    """Yetkazib beruvchi "Yuklamani yakunlash"ni bosganda chaqiriladi —
    `items`: `[{"mahsulot_id": int, "miqdor": float}, ...]` (Desktop
    Agent'da to'plangan savat). Har bir mahsulot uchun `YuklamaSorov`
    yaratilib, darhol tasdiqlanadi (zaxira omborddan kamayadi, yetkazib
    beruvchining shaxsiy zaxirasi (`DeliveryStock`) oshadi, skanerlangan
    Seriallar 'chiqarilgan'ga o'tadi)."""
    return _post_json(server_url, token, "/api/agent/yuklama/yakunlash/", json_body={
        "session_token": session_token, "items": items,
    })


def toggle_attendance(server_url: str, token: str, session_token: str):
    """Reception — badge muvaffaqiyatli skanerlangan har safar avtomatik
    chaqiriladi (rolidan qat'iy nazar). Server shu xodimning bugungi
    holatiga qarab avtomatik kirish/chiqishni belgilaydi."""
    return _post(server_url, token, "/api/agent/davomat/", data={
        "session_token": session_token,
    })


def send_heartbeat(server_url: str, token: str):
    """Stansiya fondan (`MainWindow`da QTimer orqali, ~25 soniyada bir
    marta) chaqiriladi — hech qanday skanerlash faoliyati bo'lmasa ham
    "men hali ishlab turibman" signalini beradi, shu orqali web dashboard
    stansiyani real-vaqtda onlayn/oflayn deb ko'rsata oladi."""
    return _post(server_url, token, "/api/agent/heartbeat/", data={})


def send_logout(server_url: str, token: str):
    """Dastur tozalik bilan yopilayotganda (`MainWindow.closeEvent`)
    chaqiriladi — dashboardga "oflayn" holatini 90 soniyalik heartbeat-
    kutish oynasini kutmasdan darhol bildiradi. Best-effort: agar tarmoq
    bo'lmasa ham dastur yopilishini kechiktirmasligi kerak (chaqiruvchi
    tomonda qisqa timeout/xatoni e'tiborsiz qoldirish tavsiya etiladi)."""
    return _post(server_url, token, "/api/agent/logout/", data={})
