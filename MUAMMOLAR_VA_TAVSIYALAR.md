# Firma CRM — Aniqlangan muammolar va tuzatish tavsiyalari

> Tayyorlangan sana: 2026-08-06
> Ushbu hujjat kod bo'yicha to'liq tahlil asosida tuzilgan. Click integratsiyasiga oid masalalar bu yerga kiritilmagan (alohida ko'rib chiqilgan).
> **Holat (2026-08-06):** #1, #2, #3 amalga oshirildi (commitlar: `31f49d7e`, `71f0b986`, `4d14d207`). #4 bo'yicha `crm/main/tests_warehouse.py` qo'shildi (boshlang'ich qadam, davom ettirilishi mumkin). #5 va #6 kod o'zgarishi talab qilmaydi — qo'lda tekshirish/eslatma sifatida qoldiriladi.

---

## 1. [YUQORI, BAJARILDI] Fayl yuklashda tekshiruv yo'q

**Qayerda:** `crm/main/views.py` — 1552-1553, 1743, 2086-2087, 2134, 2328, 2569-2573 qatorlar

**Muammo:** `request.FILES.get('contract_pdf')`, `signed_contract_scan`, `customer_passport_image` kabi fayllar hech qanday kengaytma, hajm yoki MIME-tur tekshiruvisiz to'g'ridan-to'g'ri saqlanadi. `ImageField`lar Pillow orqali avtomatik tekshiriladi, lekin oddiy `FileField`lar (masalan `contract_pdf`) himoyasiz — zararli fayl `.pdf` nomi bilan yuklanishi mumkin.

**Boshqa funksiyalarga ta'sir qilmaydigan tuzatish:**
Alohida yordamchi funksiya yozib, faqat shu fayl qabul qiluvchi joylarda chaqiring — mavjud kodni o'zgartirmaysiz, faqat qo'shasiz:

```python
# crm/main/utils.py (yangi yoki mavjud faylga qo'shing)
import os
from django.core.exceptions import ValidationError

def validate_uploaded_file(f, allowed_ext=('.pdf', '.jpg', '.jpeg', '.png'), max_mb=10):
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in allowed_ext:
        raise ValidationError(f"Ruxsat etilmagan fayl turi: {ext}")
    if f.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Fayl hajmi {max_mb}MB dan katta")
```

Har bir fayl qabul qilingan joyda (masalan 1552-qator atrofida) faylni saqlashdan oldin bittagina qator qo'shasiz:

```python
contract_pdf = request.FILES.get('contract_pdf')
if contract_pdf:
    validate_uploaded_file(contract_pdf, allowed_ext=('.pdf',))
    ...  # mavjud kod o'zgarmaydi
```

Bu — **qo'shimcha qatlam**, mavjud logikani buzmaydi, faqat noto'g'ri fayl kelsa xatolik qaytaradi.

---

## 2. [YUQORI, BAJARILDI] Xatolarni yashiruvchi `except:` bloklari

**Qayerda:** `crm/main/backup_views.py:198-201` (asosiy misol), shuningdek `agent_api_views.py`, `billing_service.py`, `hisobot_views.py`, `parser.py`, `desktop_agent/app/rls1100b_service.py`

```python
try:
    os.remove(temp_path)
except:
    pass
```

**Muammo:** Yalang'och `except:` HAR QANDAY xatoni (hatto `KeyboardInterrupt`, `SystemExit`) yutib yuboradi. Bu xatoliklarni topishni imkonsiz qiladi — masalan fayl qulflangan yoki ruxsat yo'q bo'lsa, hech qanday iz qolmaydi.

**Boshqa funksiyalarga ta'sir qilmaydigan tuzatish:**
Faqat `except:` ni `except Exception:` ga almashtiring va logging qo'shing — bu xulq-atvorni o'zgartirmaydi (xato baribir "yutiladi"), faqat uni log faylga yozib qoladi:

```python
import logging
logger = logging.getLogger(__name__)

try:
    os.remove(temp_path)
except Exception as e:
    logger.warning(f"Vaqtinchalik faylni o'chirib bo'lmadi: {temp_path}, xato: {e}")
```

Bu o'zgarish **1 qatorlik va izolyatsiyalangan** — dastur xulqi bir xil qoladi (xato ilgari ham "bosilib" ketardi), faqat endi diagnostika imkoni paydo bo'ladi. Har bir joyni alohida, bittalab tuzatish tavsiya etiladi — hammasini birdan o'zgartirish o'rniga.

---

## 3. [O'RTA, BAJARILDI] Desktop Agent HTTP (shifrlanmagan) ulanishga ruxsat beradi

**Qayerda:** `desktop_agent/app/api_client.py:51-60`, `agent_socket_service.py:27-30`

**Muammo:** Agar server manzili `http://` bilan sozlansa, WebSocket ham `ws://` (shifrlanmagan) ishlatiladi. Xato konfiguratsiya bilan ishlab chiqarish serveriga `http://` orqali ulansa, tokenlar ochiq tarmoqda yuboriladi.

**Tuzatish (ehtiyot bilan, chunki lokal dev rejimi buzilmasligi kerak):**
Faqat production subdomain (`*.stockfirm.uz`) uchun HTTPS majburlashni qo'shing, lokal `127.0.0.1`/`localhost` uchun HTTP qoldiring:

```python
def normalize_server_url(url: str) -> str:
    if "127.0.0.1" in url or "localhost" in url:
        return url  # lokal dev — o'zgarishsiz
    if url.startswith("http://"):
        return url.replace("http://", "https://", 1)
    return url
```

Bu funksiyani faqat URL saqlash bosqichida (`settings_page.py` yoki konfiguratsiya qabul qiluvchi joyda) chaqirasiz — qolgan kodga tegmaysiz, shuning uchun scanner/scale/printer kabi boshqa xizmatlar ta'sirlanmaydi.

---

## 4. [PAST, QISMAN BOSHLANDI] Test qariyb yo'q

**Holat:** Faqat 2 ta test fayli bor (`tests.py`, `test_service_flows.py`). `warehouse_views.py`, `production_views.py`, `agent_api_views.py` kabi katta va tez-tez o'zgaruvchi modullarga test yozilmagan.

**Tavsiya (boshqa hech narsaga tegmaydi — faqat yangi fayllar qo'shiladi):**
Mavjud kodni o'zgartirmasdan, yangi test fayllari qo'shish orqali boshlang:
- `crm/main/tests_warehouse.py` — ombor kirim/chiqim asosiy stsenariylari
- `crm/main/tests_production.py` — ishlab chiqarish vazifalarining tasdiqlash oqimi (bu modul hozir eng ko'p "Fix:" commit olgan joy)

Testlar mavjud funksiyalarga hech qanday ta'sir qilmaydi, faqat kelajakdagi o'zgarishlarda regressiyalarni erta ushlab qoladi.

---

## 5. [PAST] `0066_backfill_baza_tannarx.py` migratsiyasi

**Holat:** Ma'lumotlarni orqaga to'ldiruvchi (backfill) migratsiya — odatda bunday migratsiyalarni orqaga qaytarish qiyin bo'ladi.

**Tavsiya:** Hech narsani o'zgartirish shart emas — faqat kelajakda shu migratsiyani `rollback` qilish zarurati tug'ilsa, avval ma'lumotlar bazasidan zaxira nusxa (backup) olib, keyin qo'lda tekshirib chiqish kerakligini yodda tuting.

---

## 6. [PAST] Ombor/ishlab chiqarish moduli beqaror

**Holat:** `f77a8ff2` commitidan keyin bir necha kun ichida 6+ ta ketma-ket "Fix:" commit shu modulga tegishli bo'lgan (ombor kirim-chiqim, ishlab chiqarish vazifalari).

**Tavsiya:** Kod o'zgarishi talab qilinmaydi — bu modulni keyingi relizdan oldin qo'lda batafsil sinab ko'rish tavsiya etiladi (ayniqsa dona/litr birlikdagi vazifalar va AJAX orqali ishlaydigan qismlar).

---

## Amalga oshirish tartibi bo'yicha tavsiya

Har bir tuzatishni **alohida commit** sifatida, bittalab kiritish tavsiya etiladi:
1. Avval #2 (except: → except Exception: + log) — eng xavfsiz, chunki xulq-atvor o'zgarmaydi
2. Keyin #1 (fayl yuklash tekshiruvi) — yangi validatsiya, testdan o'tkazib ko'rish kerak
3. #3 (HTTPS majburlash) — desktop agent'ni qayta build qilishni talab qiladi, ehtiyotkorlik bilan
4. #4 va #5-6 — vaqt topilganda, kod o'zgarishisiz bajariladigan ishlar
