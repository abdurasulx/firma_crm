<div align="center">
  <h1>🏭 StockFirm CRM — Enterprise SaaS Management System</h1>
  <p>
    <strong>Ishlab chiqarish, ombor, yetkazib berish, savdogar va savdo jarayonlarini avtomatlashtiruvchi multi-tenant SaaS platforma.</strong>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" />
    <img src="https://img.shields.io/badge/Django-5.1-092E20?style=for-the-badge&logo=django&logoColor=white" />
    <img src="https://img.shields.io/badge/PWA-ready-5A0FC8?style=for-the-badge&logo=pwa&logoColor=white" />
    <img src="https://img.shields.io/badge/WebSocket-Channels-010101?style=for-the-badge&logo=socketdotio&logoColor=white" />
    <img src="https://img.shields.io/badge/Click.uz-Payment-0066CC?style=for-the-badge" />
    <img src="https://img.shields.io/badge/Leaflet.js-Map-199900?style=for-the-badge&logo=leaflet&logoColor=white" />
  </p>
</div>

---

## 📋 Loyiha haqida

**StockFirm CRM** — har bir firma o'z subdomeni (`firma.stockfirm.uz`) orqali mustaqil ishlaydigan, to'liq izolyatsiyalangan multi-tenant SaaS tizimi. Ishlab chiqarish (BOM/retsept + QR-serial kuzatuv), ombor, yetkazib berish, savdo, nasiya, ish haqi/payroll va billing — hammasi bitta platformada. Ixtiyoriy qo'shimcha sifatida — omborda o'rnatiladigan **Desktop Agent** (PyQt6 kiosk dastur) orqali badge/QR skanerlash, ishlab chiqarish nazorati va yorliq chop etish.

---

## ✨ Imkoniyatlar

### 👥 Rollar tizimi (RBAC)

| Rol | Vazifalari |
|-----|-----------|
| **Superadmin** | Barcha firmalar, tariflar, billing boshqaruvi |
| **Ega** | Firma ichidagi to'liq nazorat, hisobotlar, QR/payroll sozlamalari |
| **Ishlab chiqaruvchi (Pazanda)** | Retsept (BOM) asosida ishlab chiqarish, xom ashyo so'rovi, QR-kuzatuv |
| **Omborchi** | Ombor kirim/chiqim, kamera nazorati |
| **Yetkazib beruvchi** | Yuklama olish (QR skanerlab yoki GPS-tasdiqlab), savdo, GPS joylashuv, offline rejim |
| **Savdogar** | Shartnomali nasiya savdo, PDF shartnoma, PWA |
| **Desktop Agent** (stansiya hisobi) | Omborda o'rnatilgan kiosk qurilma — o'z login/paroli bilan |

---

### 🏭 Ishlab chiqarish va QR/Serial kuzatuv
- **Retsept (BOM)** — har bir mahsulot uchun xom ashyo normasi, tannarx avtomatik hisoblanadi (komponent tannarxi + ish haqi + qo'shimcha xarajat + amortizatsiya)
- **Vazifalar paneli** — ega "bugunga 100 dona X" vazifa yaratadi, istalgan ishlab chiqaruvchi uni stansiyada band qiladi ("ochiq pul" tizimi)
- **QR/Serial granularity** — har bir mahsulot uchun 3 xil kuzatuv: `Yo'q` (oddiy miqdor), `Har biriga alohida QR` (`unit`), `Partiya QR` (`batch`, qadoqlash hajmi bilan)
- **Turi o'zgartirish oqimi** — mahsulotning QR turi o'zgartirilsa, eski ishlab chiqarish/ombor holatlari (hali yakunlanmagan vazifalar, topshirilmagan yorliqlar, QR'siz mavjud zaxira) alohida-alohida ko'rib chiqiladi, hech kim jarimaga uchramaydi
- **Og'ish/shtraf tizimi** — xom ashyo tortishdagi tolerantlik chegarasi, reja bajarilmasa shtraf (faqat haqiqiy sababkor komponent narxida)

### 💵 Ish haqi (Payroll) va KPI
- 3 xil to'lov turi (xodim darajasida ustunlik qilinadi): **Fiks oylik**, **Donabay (per-unit)**, **Sotuvdan foiz (per-sale)**
- Fiks maoshli xodimlar uchun — rejalashtirilgan/haqiqiy ishlab chiqarish farqi avtomatik moliya hisobotiga qo'shiladi/ayiriladi (ikki marta hisoblanish yo'q)
- KPI bonus qoidalari (bosqichma-bosqich, mahsulot bo'yicha), avans, oyni yopish, qolib ketgan oylik kuzatuvi
- Moliya dashboard — tushum, COGS, sof foyda, marja %, Excel eksport

### 📦 Ombor, yuklama va GPS nazorat
- Har bir yetkazib beruvchidagi mahsulotlar alohida (`DeliveryStock`) kuzatiladi
- **Ikki xil yuklama olish**: Desktop Agentda QR skanerlab (fizik nazorat) YOKI telefon kamerasi + **GPS 100 metr radiusi** orqali (agentsiz/uzoqdagi ombor uchun alternativa)
- Sotuvda ham GPS nazorati — do'kondan 100 metrdan uzoqda turib sotuv yozib bo'lmaydi
- Kam zaxira ogohlantirishi (`min_miqdori`), StockHistory — to'liq audit
- QR-siz mahsulotlarni sotish endi majburiy skanerlashsiz, oddiy miqdor bilan ishlaydi

### 🤖 Desktop Agent (PyQt6 kiosk)
- Omborga o'rnatiladigan mahalliy dastur — badge/QR skanerlab xodim sessiyasi ochadi
- Kiosk qulfi (Qt darajasida — OS'ga tegmaydi), ishlab chiqarish/yuklama/tortish/miqdor qo'shish oqimlari
- QR yorliq chop etish (TSPL, tanlangan qog'oz o'lchamiga avtomatik moslashadi), kamera orqali voqea-yozuv
- Redis o'chib qolsa ham serverga so'rovlar bloklanib qolmaydi (fon oqimida bildirishnoma)

### 💰 Nasiya savdo (Kredit tizimi)
- **Chiziqli interpolatsiya** — bracket chegarasida keskin sakrash yo'q

| Muddat | Ustama |
|--------|--------|
| 3 oy ichida | 10% |
| 6 oy ichida | 15% |
| 9 oy ichida | 20% |
| 12 oy | 30% |

- Masalan, 3 oy 1 kunda to'lansa: `10% + (15%-10%) x 1/90 = 10.06%` — 15% emas
- Yopilgan buyurtmada `savdo.summa` (o'sha vaqtdagi to'g'ri summa) saqlanadi — vaqt o'tsa ham qayta hisoblanmaydi
- Oylik to'lovlar, qisman to'lov, muddatidan o'tgan qarzlar kuzatuvi
- `relativedelta` — taqvim bo'yicha aniq oylar hisobi

### 🤝 Savdogar moduli
- Joyida turib nasiya savdo qilish (shartnoma bilan)
- PDF shartnoma generatsiya + imzolangan skan + pasport yuklash
- Shartnoma raqami race condition himoyasi (`F()` expression)
- Savdogar mahsulotlari alohida zaxira sifatida boshqariladi

### 🗺️ GPS va real-vaqt xarita (PWA)
- **Offline rejim**: IndexedDB queue — internet yo'q bo'lsa lokatsiya yig'iladi
- **Service Worker + Background Sync** (`sf-location-sync` tag)
- Tile cache (OpenStreetMap, 7 kun TTL) — oflayn xarita
- Sync pill UI: synced / pending / syncing / offline holatlari
- Manifest.json — standalone PWA o'rnatish imkoni

### 📊 Analitika va hisobotlar
- Real-time dashboard (WebSocket, Django Channels)
- AI Forecast — Pandas/NumPy, to'liq lokal
- Chart.js grafiklar, Excel eksport
- KPI ko'rsatkichlari, yetkazuvchi hisobotlari

### 💳 Billing (SaaS)
- Superadmin panelida barcha firmalar billing boshqaruvi
- Search + pagination — firmalar va to'lovlar sahifasi
- `relativedelta` bilan aniq oylik hisob
- Click.uz onlayn to'lov, manual mark-as-paid
- 30 kunlik Free Trial, feature gating

| Holat | CRM | AI | Xarita | Backup | Telegram |
|-------|-----|----|--------|--------|----------|
| To'langan | ✅ | Tarif | Tarif | Tarif | Tarif |
| To'lanmagan | ✅ | ❌ | ❌ | ❌ | ❌ |
| Free Trial | ✅ | ✅ | ✅ | ❌ | ✅ |

### 🤖 Telegram bot
- Yangi savdo va to'lov tasdiqlanganda signal orqali xabar
- HMAC-SHA256 Telegram ID tekshiruvi

### 💾 Backup
- ZIP arxiv (JSON + media) eksport/import
- Kunlik, haftalik, oylik rejim

---

## 🚀 Texnologiyalar

| Qatlam | Texnologiya |
|--------|------------|
| Backend | Python 3.11, Django 5.1, Django Channels, Django REST Framework (agent API) |
| Frontend | HTML5, CSS3, Vanilla JS, Chart.js, Leaflet.js |
| Desktop Agent | Python, PyQt6, PyInstaller (.exe), win32print (TSPL termal printer) |
| PWA | Service Worker, IndexedDB, Web App Manifest, GPS (`navigator.geolocation`) |
| Real-time | WebSocket (ASGI), Django Channels + Redis (fon oqimida, Redis o'chsa ham so'rov bloklanmaydi) |
| To'lov | Click.uz Payment Gateway |
| Xarita | Leaflet.js + OpenStreetMap / CartoDB |
| DB | SQLite (dev) / MySQL (prod) |
| Deploy | Nginx wildcard subdomain, Gunicorn/Uvicorn ASGI |

---

## 🏗️ Loyiha strukturasi

```
firma_crm/
├── crm/                            # Django root (manage.py)
│   ├── crm/                        # Settings, URLs, ASGI
│   ├── main/                       # Asosiy CRM ilovasi
│   │   ├── services/
│   │   │   ├── credit_service.py       # Nasiya interpolatsiya logikasi
│   │   │   ├── billing_service.py      # SaaS billing
│   │   │   ├── stock_service.py        # Tannarx, QR granularity migratsiyasi
│   │   │   ├── task_service.py         # Ishlab chiqarish vazifalari
│   │   │   ├── qr_service.py           # Serial/QR generatsiya, mark_serials_*
│   │   │   ├── payroll_service.py      # Fiks/donabay/foiz ish haqi, variance
│   │   │   ├── kpi_service.py          # KPI bonus qoidalari
│   │   │   ├── retsept_service.py      # BOM qatorlari
│   │   │   ├── ombor_service.py
│   │   │   └── auth_service.py
│   │   ├── templates/
│   │   ├── agent_api_views.py      # Desktop Agent REST API (DRF)
│   │   ├── production_views.py     # Vazifalar paneli, Serial ro'yxati
│   │   ├── finance_views.py        # Moliya dashboard
│   │   ├── warehouse_views.py
│   │   ├── nasiya_views.py         # Kredit to'lovlar
│   │   ├── nasiya_models.py
│   │   ├── views.py                # Sotish/dashboard/profil, savdogar moduli
│   │   ├── models.py
│   │   ├── signals.py              # Telegram xabar signallari
│   │   └── test_*.py               # 91 ta unit test (turli fayllarga bo'lingan)
│   ├── landing/                    # Landing + Superadmin panel
│   │   ├── views.py                # super_billing, super_companies
│   │   └── templates/landing/
│   └── static/
│       ├── sw.js                   # Service Worker
│       ├── manifest.json           # PWA manifest
│       ├── icons/                  # PWA ikonkalar (192, 512)
│       └── js/
│           ├── location-db.js      # IndexedDB GPS queue
│           └── camera_widget.js    # Sahifa-ichi kamera bilan rasmga olish
├── desktop_agent/                  # PyQt6 kiosk dastur (ombor stansiyasi)
│   ├── main.py
│   ├── app/
│   │   ├── api_client.py           # CRM REST API bilan aloqa
│   │   ├── db.py                   # Mahalliy SQLite (sozlamalar)
│   │   ├── label_printer_service.py  # TSPL QR yorliq chop etish
│   │   └── windows/
│   │       ├── main_window.py          # Kiosk qulfi, navigatsiya
│   │       ├── employee_scan_widget.py # Badge/QR skanerlash, barcha sessiya oqimlari
│   │       ├── warehouse_list_page.py
│   │       └── settings_page.py
│   └── StockFirmAgent.spec         # PyInstaller build konfiguratsiyasi
├── deploy/
│   └── nginx/starify.conf          # Nginx wildcard subdomain config
├── requirements.txt
└── README.md
```

---

## 🛠️ O'rnatish

### 1. Repozitoriyni klonlash
```bash
git clone https://github.com/abdurasulx/firma_crm.git
cd firma_crm/crm
```

### 2. Virtual muhit
```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows
```

### 3. Kutubxonalar
```bash
pip install -r requirements.txt
```

### 4. Migratsiya
```bash
python manage.py migrate
```

### 5. Superuser
```bash
python manage.py createsuperuser
```

### 6. Ishga tushirish
```bash
python manage.py runserver
```

- CRM: `http://<subdomain>.localhost:8000/`
- Superadmin: `http://admin.localhost:8000/`
- Landing: `http://localhost:8000/`

### 7. Testlar
```bash
python manage.py test main
# 91 test — 90 passed, 1 skipped (lokal subdomain routing talab qiladigan test)
```

---

## 🤖 Desktop Agent (ixtiyoriy, ombor stansiyasi)

Firma "Desktop Agent" tarifini olgan bo'lsa, omborda o'rnatiladigan
mahalliy PyQt6 kiosk dastur — batafsil: [`desktop_agent/README.md`](desktop_agent/README.md).

```bash
cd desktop_agent
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Har bir stansiya CRM'da "Hodimlar → Yangi hodim → Desktop Agent" orqali
yaratilgan o'z login/paroli bilan ulanadi. `.exe` yig'ish uchun:

```bash
pip install -r requirements.txt -r requirements-build.txt
pyinstaller StockFirmAgent.spec
```

---

## 🔧 Production sozlash

`.env` fayli:
```env
DEBUG=False
SECRET_KEY=your-secret-key
TELEGRAM_BOT_TOKEN=your-token
DB_ENGINE=mysql
DB_NAME=firma_crm
DB_USER=...
DB_PASSWORD=...
REDIS_URL=redis://localhost:6379/0
```

Nginx wildcard subdomain:
```nginx
server_name *.stockfirm.uz stockfirm.uz;
```

---

## 🤝 Contributing

1. `Fork` qiling
2. Branch: `git checkout -b feature/yangi-imkoniyat`
3. Commit: `git commit -m 'Yangi imkoniyat'`
4. Push: `git push origin feature/yangi-imkoniyat`
5. Pull Request oching

---

<div align="center">
  <p>Muammo yoki taklif? <a href="https://github.com/abdurasulx/firma_crm/issues">Issue oching</a></p>
</div>
