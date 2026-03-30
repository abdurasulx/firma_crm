<div align="center">
  <h1>🏭 StockFirm CRM - Enterprise Management System</h1>
  <p>
    <strong>Ishlab chiqarish, omborxona, yetkazib berish va savdo jarayonlarini avtomatlashtirish uchun mo'ljallangan SaaS korporativ boshqaruv tizimi.</strong>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django" />
    <img src="https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
    <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="JavaScript" />
    <img src="https://img.shields.io/badge/WebSocket-010101?style=for-the-badge&logo=socketdotio&logoColor=white" alt="WebSocket" />
    <img src="https://img.shields.io/badge/Leaflet-199900?style=for-the-badge&logo=leaflet&logoColor=white" alt="Leaflet" />
  </p>
</div>

---

## 📋 Loyiha Haqida

**StockFirm CRM** — bu kompaniyaning ichki va tashqi savdo jarayonlarini, zaxiralarni va xodimlar faoliyatini real-vaqt rejimida boshqarish imkonini beruvchi to'liq avtomatlashtirilgan SaaS platforma. Multi-tenant arxitektura asosida qurilgan bo'lib, har bir firma o'z subdomeni (`firma.stockfirm.uz`) orqali mustaqil ishlaydi.

## ✨ Asosiy Imkoniyatlar (Features)

### 📦 Ombor va Zaxira Boshqaruvi
*   Har bir mahsulot bo'yicha aniq qoldiqlar hisobi va to'liq audit (StockHistory).
*   Har bir yetkazib beruvchi (dastavchik) dagi mahsulotlarni alohida zaxira sifatida kuzatish (DeliveryStock).
*   Ishlab chiqarishdan qabul qilish va yuklamalarni tasdiqlash tizimi.
*   Kam zaxira ogohlantirishi — `min_miqdori` chegarasidan past tushgan mahsulotlar dashboard-da ko'rsatiladi.

### 👥 Rolga Asoslangan Tizim (RBAC)
| Rol | Vazifalari |
|-----|-----------|
| **Ega (Admin)** | To'liq nazorat, hisobotlar, tarif boshqaruvi, backup |
| **Pazanda (Cook)** | Mahsulot ishlab chiqarish, yuklamalar |
| **Yetkazib beruvchi (Delivery)** | Savdo qilish, zaxira boshqarish, GPS joylashuv |

### 📊 Analitika va Hisobotlar
*   **Real-time Dashboard**: Kunlik/oylik savdo hajmi, daromad, faol xodimlar.
*   **AI Forecast API**: Talabni prognozlash va do'konlar bo'yicha tavsiyalar (Pandas/NumPy — 100% lokal).
*   **Professional Hisobotlar**: Yillik, oylik, haftalik, kunlik filtrlash + Excel eksport.
*   **Chart.js grafiklar**: Haftalik sotuvlar va mahsulotlar statistikasi.

### 💰 Savdo va Mijozlar
*   Mahsulotlarni sotish va avtomatik zaxiradan chegirish.
*   **Nasiya Savdo**: Qarzga berish, qisman to'lovlar, muddati o'tgan qarzlarni kuzatish.
*   Mijozlar bazasi va savdo tarixi.
*   Qaytarilgan mahsulotlarni hisobga olish.

### 🗺️ Real-vaqt Xaritasi
*   GPS orqali yetkazib beruvchilarni real-vaqtda kuzatish.
*   Savdo nuqtalari va marshrut tarixini vizualizatsiya qilish.
*   Leaflet.js + OpenStreetMap integratsiyasi.

### 🤖 Telegram Bot
*   To'lov tasdiqlanganda firma egasiga avtomatik xabar yuborish.
*   HMAC-SHA256 asosida xavfsiz Telegram ID tekshiruvi.

### 💳 SaaS Billing Tizimi

**Tariflar:**
*   Standart tariflar (admin belgilaydi) yoki maxsus tarif quruvchi (foydalanuvchi tanlaydi).
*   30 kunlik bepul sinov muddati (Free Trial) — backupdan tashqari hammasi ishlaydi.
*   Click.uz orqali onlayn to'lov (USD → UZS avtomatik konvertatsiya).

**Feature Gating:**

| Holat | Asosiy CRM | AI Analytics | Xarita | Backup | Telegram Bot |
|---|---|---|---|---|---|
| **To'langan** | ✅ | Tarifga qarab | Tarifga qarab | Tarifga qarab | Tarifga qarab |
| **To'lanmagan** | ✅ | ❌ Sidebar-da ko'rinadi, kirsa bloklanadi | ❌ Ko'rinadi, kirsa bloklanadi | ❌ | ❌ |
| **Free Trial** | ✅ | ✅ | ✅ | ❌ | ✅ |

### 💾 Ma'lumotlar Zaxirasi (Backup)
*   ZIP arxiv (JSON + media fayllar) formatida eksport.
*   Kunlik, haftalik yoki oylik zaxiralash rejimi.
*   ZIP fayldan tiklash (`update_or_create` — dublikat oldini oladi).

### 🔔 Real-vaqt Bildirishnomalar
*   Django Channels (WebSocket) orqali darhol xabar berish.
*   Yangi savdo, sorov tasdiqlash va boshqa hodisalar.

---

## 🚀 Texnologiyalar Steki

### **Backend:**
*   Python 3.x, Django, Django Channels (WebSocket)
*   Django ORM, Service Layer arxitekturasi
*   Markazlashtirilgan tarif tekshiruvi (`plan_utils.py`)

### **Frontend:**
*   HTML5 / CSS3 (Vanilla & Custom Animations)
*   JavaScript (ES6, AJAX, Fetch API, WebSocket)
*   Chart.js, Leaflet.js, Google Fonts (Inter), FontAwesome

### **Infratuzilma:**
*   SQLite3 (development) / PostgreSQL (production)
*   Click.uz Payment Gateway
*   Multi-tenant (subdomain-based)

---

## 🏗️ Loyiha Strukturasi

```text
firma_crm/
├── crm/                        # Asosiy Django loyihasi
│   ├── crm/                    # Django settings, admin_urls
│   ├── main/                   # Asosiy CRM ilovasi
│   │   ├── services/           # Biznes logikalar (stock, analytics)
│   │   ├── api/                # REST API endpointlar
│   │   ├── templates/          # HTML shablonlar
│   │   ├── static/             # CSS, JS, Rasmlar
│   │   ├── plan_utils.py       # Tarif va to'lov tekshiruvlari
│   │   ├── middleware.py       # Multi-tenant, feature gating
│   │   ├── context_processors.py # Template kontekst
│   │   ├── analytics.py        # AI Analytics API
│   │   ├── analytics_views.py  # Analytics dashboard
│   │   ├── map_views.py        # Xarita view-lar
│   │   ├── backup_views.py     # Backup va restore
│   │   ├── click_views.py      # Click to'lov integratsiyasi
│   │   ├── hisobot_views.py    # Hisobotlar
│   │   ├── nasiya_views.py     # Nasiya savdolar
│   │   ├── bot_logic.py        # Telegram bot
│   │   ├── views.py            # Asosiy controllerlar
│   │   └── models.py           # Ma'lumotlar bazasi modellari
│   ├── landing/                # Landing page va admin panel
│   ├── manage.py
│   ├── requirements.txt
│   └── IMKONIYATLAR.md         # Loyiha imkoniyatlari bayoni
└── README.md
```

---

## 🛠️ O'rnatish va Ishga Tushirish

### 1-qadam: Repozitoriyni yuklab oling
```bash
git clone <repo-url>
cd firma_crm/crm
```

### 2-qadam: Virtual muhit yarating
```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate          # Windows
```

### 3-qadam: Kutubxonalarni o'rnating
```bash
pip install -r requirements.txt
```

### 4-qadam: Migratsiyalarni amalga oshiring
```bash
python manage.py migrate
```

### 5-qadam: Superfoydalanuvchi yarating
```bash
python manage.py createsuperuser
```

### 6-qadam: Serverni ishga tushiring
```bash
python manage.py runserver
```

Brauzerda: `http://<subdomain>.localhost:8000/`
Admin panel: `http://admin.localhost:8000/`

---

## 🤝 Hamkorlik (Contributing)

1. `Fork` qiling
2. Yangi `branch` yarating (`git checkout -b feature/YangiImkoniyat`)
3. O'zgarishlarni `commit` qiling (`git commit -m 'Yangi imkoniyat qo'shildi'`)
4. `Push` qiling (`git push origin feature/YangiImkoniyat`)
5. `Pull Request` oching

---

<div align="center">
  <p>Loyihani yanada takomillashtirish bo'yicha takliflaringiz bo'lsa, muallif bilan bog'laning!</p>
</div>
