# StockFirm CRM - Loyiha Imkoniyatlari

Ushbu hujjat **StockFirm CRM** tizimining texnik imkoniyatlari, funksional modullari va arxitektura xususiyatlari haqida to'liq ma'lumot beradi.

## 1. Umumiy tavsif
StockFirm CRM — ishlab chiqarish, omborxona, yetkazib berish va savdo jarayonlarini avtomatlashtirish uchun mo'ljallangan enterprise-grade korporativ boshqaruv tizimi. Multi-tenant (ko'p tarmoqli) arxitektura asosida qurilgan SaaS platform bo'lib, har bir firma o'z subdomeni orqali mustaqil ishlaydi.

## 2. Asosiy Modullar

### 📦 Ombor va Zaxira Boshqaruvi
*   **Structured Stock Tracking**: Har bir mahsulot bo'yicha aniq qoldiqlar hisobi.
*   **DeliveryStock**: Har bir yetkazib beruvchi (dastavchik) qo'lidagi mahsulotlarni alohida zaxira sifatida kuzatish.
*   **StockHistory**: Zaxiradagi barcha o'zgarishlarning to'liq auditi (kim, qachon, qancha miqdor qo'shdi yoki ayirdi).
*   **Approval System**: Ishlab chiqarishdan mahsulot qabul qilish (`MiqdorQoshish`) va yetkazib beruvchiga yuklash (`YuklamaSorov`) jarayonlarini tasdiqlash tizimi.
*   **Kam zaxira ogohlantirishi**: `min_miqdori` chegarasidan past tushgan mahsulotlar haqida dashboard-da real-vaqt ogohlantirishlari.

### 👥 Foydalanuvchilar va Xavfsizlik
*   **Rollar tizimi**:
    *   **Ega (Admin)**: To'liq nazorat, hisobotlar va tizim sozlamalari.
    *   **Pazanda (Cook)**: Mahsulot ishlab chiqarish va yuklamalarni shakllantirish.
    *   **Yetkazib beruvchi (Delivery)**: Savdo qilish va o'z zaxirasini boshqarish.
*   **Xavfsiz Autentifikatsiya**: Parollarni zamonaviy heshlash (Django default hashing) tizimi orqali himoyalangan saqlash.
*   **Modern UI**: Har bir rol uchun moslashtirilgan, responsive va zamonaviy interfeys.

### 📊 Analitika va Dashboard
*   **Real-time Dashboard**: Kunlik va oylik savdo hajmi, past zaxirali mahsulotlar va faol foydalanuvchilar statistikasi.
*   **Savdo Tahlili**: `Savdo.summa` orqali sof daromad va aylanma tahlili.
*   **AI Forecast API**: Mahsulotlarga bo'lgan talabni prognozlash va do'konlar bo'yicha tavsiyalar berish (`Analytics Service`). Pandas/NumPy asosida lokal ishlaydi — tashqi API kerak emas.
*   **Hisobotlar**: Yillik, oylik, haftalik va kunlik filtrlash, xodim bo'yicha saralash, Excel eksport.
*   **Xavfsiz ma'lumotlar**: Maxfiy fieldlar (masalan, `Savdo.smm`) bilan ishlashda qat'iy xavfsizlik qoidalari.

### 💰 Savdo va Mijozlar
*   **Sotuv jarayoni**: Mahsulotlarni mijozlarga sotish va avtomatik zaxiradan chegirish.
*   **Nasiya Savdo**: Qarzga berilgan mahsulotlar hisobi, qisman to'lovlarni kuzatib borish, muddati o'tganlarni ajratish.
*   **Mijozlar Bazasi**: Mijozlar (do'konlar) kontaktlari va ularning savdo tarixi.
*   **Qaytarish tizimi**: Qaytarilgan mahsulotlarni hisobga olish va zaxiraga qaytarish.

### 🗺️ Real-vaqt Xaritasi
*   **Yetkazib beruvchilar joylashuvi**: GPS orqali real-vaqtda kuzatish.
*   **Savdo nuqtalari xaritasi**: Mijozlar va savdo joylarining vizual ko'rinishi.
*   **Marshrut tarixi**: Har bir yetkazib beruvchining harakatlanish tarixini ko'rish.
*   **WebSocket ping**: 30 soniyada bir marta joylashuvni yangilash.

### 🤖 Telegram Bot Integratsiyasi
*   **Savdo bildirish nomalari**: To'lov tasdiqlanganda firma egasiga avtomatik Telegram xabar yuborish.
*   **Xavfsiz ulash**: HMAC-SHA256 asosida Telegram ID ni tekshirish, spoofing-dan himoya.
*   **Tarif bilan bog'liq**: Faqat tarifda bot yoqilgan bo'lsa ishlaydi.

### 💳 Tarif va To'lov Tizimi (SaaS Billing)
*   **Standart tariflar**: Admin tomonidan belgilangan tariflar (Plan modeli).
*   **Maxsus tarif quruvchi**: Foydalanuvchi o'zi kerakli imkoniyatlarni tanlaydi va narx avtomatik hisoblanadi.
*   **Free Trial**: 30 kunlik sinov muddati (backup-dan tashqari barcha imkoniyatlar bepul).
*   **Click to'lov integratsiyasi**: Click.uz orqali onlayn to'lov qilish (USD → UZS konvertatsiya).
*   **Admin billing paneli**: Superadmin firmalarning to'lov holatini boshqarish, tariflarni tasdiqlash.

#### Tarif imkoniyatlari nazorati (Feature Gating):

| Holat | Asosiy CRM | AI Analytics | Xarita | Backup | Telegram Bot |
|---|---|---|---|---|---|
| **To'langan** | ✅ | Tarifga qarab | Tarifga qarab | Tarifga qarab | Tarifga qarab |
| **To'lanmagan** | ✅ (Grace period ichida) | ❌ Ko'rinadi, kirsa bloklanadi | ❌ Ko'rinadi, kirsa bloklanadi | ❌ Bloklanadi | ❌ Yuborilmaydi |
| **Free Trial** | ✅ | ✅ | ✅ | ❌ Bloklanadi | ✅ |
| **Grace period tugagan** | ❌ Sayt to'liq bloklanadi | ❌ | ❌ | ❌ | ❌ |

*   **Grace Period**: Tarif tasdiqlangandan keyin 5 kun to'lov muddati + 3 kun kechikish muddati. Jami 8 kun ichida to'lov qilinmasa sayt to'liq bloklanadi (`suspended.html`).
*   **Markazlashtirilgan tekshiruv**: Barcha view-lar `plan_utils.py` dagi `company_has_access()` funksiyasidan foydalanadi.

### 💾 Ma'lumotlar Zaxirasi (Backup)
*   **Eksport formati**: ZIP arxiv (JSON + media fayllar).
*   **Zaxira turlari**: Kunlik ($30/oy), Haftalik ($15/oy), Oylik ($5/oy).
*   **Ma'lumotlarni tiklash**: ZIP fayldan ma'lumotlarni import qilish (`update_or_create`).
*   **Trial cheklovi**: Sinov muddatida backup va restore mavjud emas.

### 🔔 Real-vaqt Bildirishnomalar
*   **WebSocket**: Django Channels orqali yangi savdo, sorov tasdiqlash kabi hodisalar haqida darhol xabar berish.
*   **Notification Queue**: Bir vaqtda maksimum 3 ta bildirishnoma, 4 soniyalik animatsiya.

## 3. Texnik Arxitektura

*   **Backend**: Django (Python) frameworki, Django Channels (WebSocket).
*   **Multi-tenant**: Subdomain asosida firma ajratish (`CompanyMiddleware`).
*   **Service Layer**: Biznes mantiq (business logic) viewlardan alohida `services/` qatlamiga chiqarilgan.
*   **Plan Utils**: Tarif va to'lov tekshiruvlari `plan_utils.py` da markazlashtirilgan.
*   **Frontend**: Zamonaviy CSS (Vanilla), Inter shriftlari va FontAwesome ikonkalari ishlatilgan responsive dizayn.
*   **Database**: SQLite3 (development), PostgreSQL/MySQL ga osongina ko'chirish mumkin.
*   **To'lov**: Click.uz payment gateway integratsiyasi.
*   **Xarita**: Leaflet.js + OpenStreetMap.
*   **Cache**: Django cache framework (valyuta kursi uchun 12 soatlik kesh).

## 4. Foydalanuvchi Interfeysi Xususiyatlari
*   **Responsive Sidebar**: Mobil va desktop qurilmalar uchun moslashuvchan menyu, yig'ish/ochish funksiyasi.
*   **Instant Search**: Hodimlar va mahsulotlar bo'yicha AJAX yordamida tezkor qidiruv.
*   **Image Previews**: Foydalanuvchi va mahsulot rasmlarini yuklashda real-vaqt rejimida oldindan ko'rish.
*   **Modern Cards & Grids**: Ma'lumotlarni o'qish uchun qulay va premium dizayndagi elementlar.
*   **Chart.js grafiklar**: Haftalik sotuvlar va mahsulotlar statistikasi.
*   **Online kuryerlar paneli**: Sidebar-da hozirda onlayn yetkazib beruvchilar ro'yxati.

---
*Ushbu hujjat tizimning hozirgi holatidagi imkoniyatlarini aks ettiradi. Oxirgi yangilanish: 2026-03-29*
