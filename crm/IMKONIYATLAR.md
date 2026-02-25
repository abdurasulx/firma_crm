# Firma CRM - Loyiha Imkoniyatlari

Ushbu hujjat "Firma CRM" tizimining texnik imkoniyatlari, funksional modullari va arxitektura xususiyatlari haqida to'liq ma'lumot beradi.

## 1. Umumiy tavsif
Firma CRM — ishlab chiqarish, omborxona, yetkazib berish va savdo jarayonlarini avtomatlashtirish uchun mo'ljallangan enterprise-grade korporativ boshqaruv tizimi. Tizim ko'p rolli foydalanishga asoslangan va real-vaqt rejimida ma'lumotlar almashinuvini ta'minlaydi.

## 2. Asosiy Modullar

### 📦 Ombor va Zaxira Boshqaruvi
*   **Structured Stock Tracking**: Har bir mahsulot bo'yicha aniq qoldiqlar hisobi.
*   **DeliveryStock**: Har bir yetkazib beruvchi (dastavchik) qo'lidagi mahsulotlarni alohida zaxira sifatida kuzatish.
*   **StockHistory**: Zaxiradagi barcha o'zgarishlarning to'liq auditi (kim, qachon, qancha miqdor qo'shdi yoki ayirdi).
*   **Approval System**: Ishlab chiqarishdan mahsulot qabul qilish (`MiqdorQoshish`) va yetkazib beruvchiga yuklash (`YuklamaSorov`) jarayonlarini tasdiqlash tizimi.

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
*   **Forecast API**: Mahsulotlarga bo'lgan talabni prognozlash va do'konlar bo'yicha tavsiyalar berish (`Analytics Service`).
*   **Xavfsiz ma'lumotlar**: Maxfiy fieldlar (masalan, `Savdo.smm`) bilan ishlashda qat'iy xavfsizlik qoidalari.

### 💰 Savdo va Mijozlar
*   **Sotuv jarayoni**: Mahsulotlarni mijozlarga sotish va avtomatik zaxiradan chegirish.
*   **Nasiya Savdo**: Qarzga berilgan mahsulotlar hisobi va to'lovlarni kuzatib borish.
*   **Mijozlar Bazasi**: Mijozlar (do'konlar) kontaktlari va ularning savdo tarixi.

## 3. Texnik Arxitektura

*   **Backend**: Django (Python) frameworki.
*   **Service Layer**: Biznes mantiq (business logic) viewlardan alohida `services/` qatlamiga chiqarilgan, bu kodning qayta ishlatilishi va test qilinishini osonlashtiradi.
*   **Frontend**: Zamonaviy CSS (Vanilla), Inter shriftlari va FontAwesome ikonkalari ishlatilgan responsive dizayn.
*   **Database**: Ma'lumotlar butunligini ta'minlash uchun `atomic transactions` va xorijiy kalitlar (ForeignKeys) to'g'ri sozlangan.

## 4. Foydalanuvchi Interfeysi Xususiyatlari
*   **Responsive Sidebar**: Mobil va desktop qurilmalar uchun moslashuvchan menyu.
*   **Instant Search**: Hodimlar va mahsulotlar bo'yicha AJAX yordamida tezkor qidiruv.
*   **Image Previews**: Foydalanuvchi va mahsulot rasmlarini yuklashda real-vaqt rejimida oldindan ko'rish (preview).
*   **Modern Cards & Grids**: Ma'lumotlarni o'qish uchun qulay va premium dizayndagi elementlar.

---
*Ushbu hujjat tizimning hozirgi holatidagi imkoniyatlarini aks ettiradi.*
