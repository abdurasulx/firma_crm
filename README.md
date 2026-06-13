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

**StockFirm CRM** — har bir firma o'z subdomeni (`firma.stockfirm.uz`) orqali mustaqil ishlaydigan, to'liq izolyatsiyalangan multi-tenant SaaS tizimi. Ombor, yetkazib berish, savdo, nasiya va billing — hammasi bitta platformada.

---

## ✨ Imkoniyatlar

### 👥 Rollar tizimi (RBAC)

| Rol | Vazifalari |
|-----|-----------|
| **Superadmin** | Barcha firmalar, tariflar, billing boshqaruvi |
| **Ega** | Firma ichidagi to'liq nazorat, hisobotlar |
| **Pazanda** | Mahsulot ishlab chiqarish, yuklamalar |
| **Yetkazib beruvchi** | Savdo, zaxira, GPS joylashuv, offline rejim |
| **Savdogar** | Shartnomali nasiya savdo, PDF shartnoma, PWA |

---

### 📦 Ombor va zaxira
- Har bir yetkazib beruvchidagi mahsulotlar alohida kuzatiladi
- Ishlab chiqarishdan qabul qilish va yuklamalarni tasdiqlash
- Kam zaxira ogohlantirishi (`min_miqdori` chegarasi)
- StockHistory — to'liq audit

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
| Backend | Python 3.11, Django 5.1, Django Channels |
| Frontend | HTML5, CSS3, Vanilla JS, Chart.js, Leaflet.js |
| PWA | Service Worker, IndexedDB, Web App Manifest |
| Real-time | WebSocket (ASGI), Django Channels |
| To'lov | Click.uz Payment Gateway |
| Xarita | Leaflet.js + OpenStreetMap / CartoDB |
| DB | SQLite (dev) / MySQL (prod) |
| Deploy | Nginx wildcard subdomain, Daphne ASGI |

---

## 🏗️ Loyiha strukturasi

```
firma_crm/
├── crm/                        # Django root (manage.py)
│   ├── crm/                    # Settings, URLs, ASGI
│   ├── main/                   # Asosiy CRM ilovasi
│   │   ├── services/
│   │   │   ├── credit_service.py   # Nasiya interpolatsiya logikasi
│   │   │   ├── billing_service.py  # SaaS billing
│   │   │   ├── stock_service.py
│   │   │   └── auth_service.py
│   │   ├── templates/
│   │   ├── nasiya_views.py         # Kredit to'lovlar
│   │   ├── nasiya_models.py
│   │   ├── views.py                # Savdogar moduli ham shu yerda
│   │   ├── models.py
│   │   ├── signals.py              # Telegram xabar signallari
│   │   └── test_service_flows.py   # 30 ta unit test
│   ├── landing/                # Landing + Superadmin panel
│   │   ├── views.py            # super_billing, super_companies
│   │   └── templates/landing/
│   └── static/
│       ├── sw.js               # Service Worker
│       ├── manifest.json       # PWA manifest
│       ├── icons/              # PWA ikonkalar (192, 512)
│       └── js/
│           └── location-db.js  # IndexedDB GPS queue
├── deploy/
│   └── nginx/starify.conf      # Nginx wildcard subdomain config
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
python manage.py test main.test_service_flows
# 29 passed, 1 skipped
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
