<div align="center">
  <h1>🌟 Firma CRM - Enterprise Management System</h1>
  <p>
    <strong>Ishlab chiqarish, omborxona, yetkazib berish va savdo jarayonlarini avtomatlashtirish uchun mo'ljallangan korporativ boshqaruv tizimi.</strong>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django" />
    <img src="https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
    <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="JavaScript" />
    <img src="https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white" alt="CSS3" />
  </p>
</div>

---

## 📋 Loyiha Haqida

**Firma CRM** — bu kompaniyaning ichki va tashqi savdo jarayonlarini, zaxiralarni va xodimlar faoliyatini real-vaqt rejimida boshqarish imkonini beruvchi to'liq avtomatlashtirilgan tizim. U ishlab chiqarishdan tortib, to mahsulot mijozga yetib borguncha bo'lgan barcha bosqichlarni qamrab oladi.

## ✨ Asosiy Imkoniyatlar (Features)

*   📦 **Ombor va Zaxira Boshqaruvi:** Har bir mahsulot bo'yicha aniq qoldiqlar hisobi, zaxiradagi o'zgarishlarning to'liq auditi (kim, qachon, qancha?).
*   🚚 **Yetkazib berish (Delivery Stock):** Har bir yetkazib beruvchi (dastavchik) dagi mahsulotlarni alohida zaxira sifatida kuzatish va nazorat qilish.
*   📊 **Analitika va Dashboard:**
    *   Kunlik va oylik savdo hajmi.
    *   Past zaxirali mahsulotlar ogohlantirishi.
    *   Foyda, aylanma va Nasiya savdolarni avtomatik hisoblash.
    *   Mashina o'rganish (Forecast API) yordamida talabni prognozlash.
*   👥 **Rolga asoslangan tizim (RBAC):** Ega (Admin), Pazanda (Cook), Yetkazib beruvchi (Delivery) rollari uchun alohida ruxsatnomalar va interfeyslar.
*   💰 **Nasiya Savdo:** Qarzga berilgan mahsulotlar hisobi, to'lovlarni tizimli ravishda kuzatib borish.
*   🔍 **Zamonaviy UI (Modern UI):** Mobil va desktop qurilmalariga to'liq moslashgan Responsive interfeys, tezkor qidiruv (AJAX) va real-vaqtda rasmlarni yuklash (Image Preview).

---

## 🚀 Texnologiyalar Steki (Tech Stack)

### **Backend:**
*   Python 3.x
*   Django (Web Framework)
*   Django ORM (Database Management)

### **Frontend:**
*   HTML5 / CSS3 (Vanilla & Custom Animations)
*   JavaScript (ES6, AJAX, Fetch API)
*   Google Fonts (Inter), FontAwesome Icons

### **Database:**
*   SQLite3 (Development uchun)
*   Boshqa Ma'lumotlar bazalariga osongina moslashtirilishi mumkin (PostgreSQL/MySQL).

---

## 🏗️ Arxitektura (Loyiha Strukturasi)

Loyihada biznes logika va ko'rinishlar (views) ajratilgan "Service Layer" yondashuvidan foydalanilgan:

```text
firma_crm/
├── crm/                    # Asosiy Django loyihasi
│   ├── main/               # Asosiy CRM ilovasi (App)
│   │   ├── services/       # Biznes logikalar va API
│   │   ├── templates/      # HTML shablonlar
│   │   ├── static/         # CSS, JS, Rasmlar
│   │   ├── views.py        # Controllerlar
│   │   └── models.py       # Ma'lumotlar bazasi jadvallari
│   ├── manage.py           # Loyihani boshqarish scripti
│   ├── requirements.txt    # Kerakli kutubxonalar ro'yxati
│   └── IMKONIYATLAR.md     # Loyiha imkoniyatlari bayoni
```

---

## 🛠️ O'rnatish va Ishga Tushirish (Installation & Setup)

Loyihani o'z kompyuteringizda ishga tushirish uchun quyidagi qadamlarni bajaring:

### 1-qadam: Repozitoriyni yuklab oling
```bash
git clone <repo-url>
cd firma_crm/crm
```

### 2-qadam: Virtual muhit (Virtual Environment) yarating va faollashtiring
```bash
python -m venv venv
# Linux/macOS uchun:
source venv/bin/activate
# Windows uchun:
venv\Scripts\activate
```

### 3-qadam: Kerakli kutubxonalarni o'rnating
```bash
pip install -r requirements.txt
```

### 4-qadam: Migratsiyalarni amalga oshiring
```bash
python manage.py migrate
```

### 5-qadam: Superfoydalanuvchi yarating (Optional)
```bash
python manage.py createsuperuser
```

### 6-qadam: Serverni ishga tushiring
```bash
python manage.py runserver
```
Loyihaga brauzerdan quyidagi manzil orqali kiring: `http://127.0.0.1:8000/`

---

## 🔐 Standart Rollar (Credentials)

Test uchun quyidagi foydalanuvchilardan foydalanishingiz mumkin (`info.txt` ma'lumotlariga asosan):

| Foydalanuvchi   | Rol (Vazifasi)         | Parol        |
| :---            | :---                   | :---         |
| **banda**       | Ega (Admin)            | `bandacap`   |
| **abdurasulx1** | Ega (Admin)            | `andijonim`  |
| **rafiq2008**   | Pazanda / Dastavchik   | `rafiq2008##`|

*(Izoh: Ishlab chiqarish - Production muhitida ushbu parollarni zudlik bilan almashtiring!)*

---

## 🤝 Hamkorlik (Contributing)

Agar ushbu loyihaga o'z hissangizni qo'shmoqchi bo'lsangiz:
1. `Fork` qiling
2. O'zgartirishlar uchun yangi `branch` yarating (`git checkout -b feature/YangiImkoniyat`)
3. O'zgarishlarni `commit` qiling (`git commit -m 'Yangi imkoniyat qo'shild'`)
4. Branchga `push` qiling (`git push origin feature/YangiImkoniyat`)
5. `Pull Request` oching

---

<div align="center">
  <p>Loyihani yanada takomillashtirish bo'yicha takliflaringiz bo'lsa, muallif bilan bog'laning!</p>
</div>
