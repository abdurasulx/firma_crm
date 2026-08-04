# UPDATE NEW VERSION — Kamchiliklar va tuzatish rejasi

> Audit sanasi: 2026-07-20. Tizim tahlili asosida aniqlangan kamchiliklar ro'yxati.
> Eslatma: Production eski versiyada PostgreSQL'da ishlaydi — SQLite masalasi faqat lokal dev muhitiga tegishli, shuning uchun rejaga kiritilmadi.

## 🔴 Jiddiy (xavfsizlik) — birinchi navbatda

### 1. Click to'lov maxfiy kaliti kodda ochiq
- **Fayl:** `crm/main/click_views.py:13`
- **Muammo:** `CLICK_SECRET_KEY = os.getenv('CLICK_SECRET_KEY', 'HaLZ1bWlBHY')` — haqiqiy secret key fallback sifatida repoda. `CLICK_MERCHANT_ID` va `CLICK_SERVICE_ID` ham hardcoded.
- **Tuzatish:** Click kabinetida kalitni almashtirish, koddan fallback'ni olib tashlash (env yo'q bo'lsa xato ko'tarish). `crm/crm/settings.py:28` dagi `SECRET_KEY` fallback'i uchun ham xuddi shunday.

### 2. DEBUG default True va ALLOWED_HOSTS='*'
- **Fayl:** `crm/crm/settings.py:31-33`
- **Muammo:** `.env` tushib qolsa production stack-trace'lar bilan ochilib qoladi.
- **Tuzatish:** default `DEBUG=False`, `ALLOWED_HOSTS` productionda aniq ro'yxat bo'lishi majburiy.

### 3. Production xavfsizlik sozlamalari yo'q
- **Fayl:** `crm/crm/settings.py`
- **Muammo:** `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT` umuman yo'q — cookie'lar HTTP orqali ham yuborilishi mumkin.
- **Tuzatish:** `DEBUG=False` bo'lganda bularni yoqish.

### 4. Desktop Agent API'da `user_id` mijozdan olinadi
- **Fayl:** `crm/main/agent_api_views.py:82,120`
- **Muammo:** Kompaniya tokeni bo'lgan har qanday stansiya istalgan xodim nomidan so'rovlarni ko'rishi va "qabul qildim" bosishi mumkin — badge-skan tasdig'i serverda tekshirilmaydi.
- **Tuzatish:** `agent_badge_scan` muvaffaqiyatida qisqa muddatli sessiya-token qaytarish, keyingi endpointlarda `user_id` o'rniga shu tokenni talab qilish.

### 5. db.sqlite3, __pycache__, log fayllar git'da
- **Muammo:** Real DB (parol hash'lar, mijoz ma'lumotlari), `__pycache__/`, `*.log` fayllar repoda kuzatiladi.
- **Tuzatish:** `.gitignore`ga qo'shish, `git rm --cached` bilan chiqarish, tarixdan tozalashni ko'rib chiqish.

## 🟠 Muhim (arxitektura / ishonchlilik)

### 6. CompanyMiddleware har so'rovda billing sync qiladi
- **Fayl:** `crm/main/middleware.py:49`
- **Muammo:** `sync_company_lifecycle(company)` har requestda + `SESSION_SAVE_EVERY_REQUEST=True` — har request 2-3 qo'shimcha DB operatsiya.
- **Tuzatish:** lifecycle syncni cache (masalan 5-10 daqiqa) yoki cron'ga ko'chirish.

### 7. views.py monoliti va qo'lda rol tekshiruvi
- **Fayl:** `crm/main/views.py` (2641 qator, 42 view, 74 joyda `request.user.type == ...`)
- **Muammo:** bitta joyda unutilgan tekshiruv = ruxsatsiz kirish.
- **Tuzatish:** `@role_required('ega', ...)` decorator/mixin joriy qilish, viewlarni modullarga bo'lish.

### 8. Login'da rate-limit / lockout yo'q
- **Muammo:** subdomain'lar ochiq, parol brute-force'dan himoya yo'q.
- **Tuzatish:** `django-axes` yoki cache-based throttle qo'shish.

### 9. Pul summalari float'da
- **Fayl:** `crm/main/click_views.py:62` (va boshqa moliyaviy joylarni tekshirish)
- **Tuzatish:** `Decimal`ga o'tkazish.

## 🟡 Kichikroq

- **Sessiya muddati:** 7 kun + brauzer yopilganda tugamaydi (`settings.py:213-219`) — moliyaviy tizim uchun uzoq; hech bo'lmaganda 'ega' roli uchun qisqartirish.
- **USD kursi fallback:** `click_views.py:46` da 12500 qotib qolgan — eskirgan; env'dan olish yoki oxirgi cache'langan qiymatni saqlash.
- **CHANNEL_LAYERS ikki marta aniqlangan:** `settings.py:82-106` — qarama-qarshi mantiq, bittasini qoldirish.
- **Test qamrovi tor:** 30 test asosan service-flow'lar; billing/Click webhook va rol-huquq tekshiruvlari uchun test yo'q — eng xavfli joylar aynan shular.

## Bajarish tartibi (tavsiya)

1. Secret'larni almashtirish va fallback'larni olib tashlash (№1)
2. db.sqlite3 va keraksiz fayllarni git'dan chiqarish (№5)
3. Production cookie/HTTPS/DEBUG sozlamalari (№2, №3)
4. Agent API'da xodim tasdig'ini serverda majburiy qilish (№4)
5. Middleware billing sync optimizatsiyasi (№6)
6. Rol decorator + login throttle (№7, №8)
7. Decimal, sessiya, USD kursi, CHANNEL_LAYERS, testlar (№9 va 🟡)
