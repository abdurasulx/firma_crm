# StockFirm CRM uchun kerakli skillar

Bu fayl loyiha bilan ishlaydigan dasturchi yoki AI agent uchun qisqa amaliy yo'riqnoma. Maqsad: kodga kirishdan oldin qaysi bilimlar kerakligini, qaysi fayllarga qarashni va o'zgarishlarni qanday tekshirishni tez eslatish.

## Loyiha konteksti

- Loyiha: `StockFirm CRM`, ishlab chiqarish, ombor, savdo, yetkazib berish, billing va hisobotlarni boshqaruvchi multi-tenant SaaS tizim.
- Stack: Python, Django 5.1, Django Channels, SQLite/MySQL, vanilla JavaScript, Chart.js, Leaflet.js, Telegram Bot API, Click.uz, pandas/numpy.
- Asosiy papka: `crm/`.
- Django app-lar: `main` asosiy CRM logikasi, `landing` landing va ro'yxatdan o'tish oqimi.
- Virtual muhitlar va build natijalarini o'zgartirmang: `.venv/`, `vwin/`, `crm/venv/`, `crm/staticfiles/`.

## Enabled UI/Template skilllar

Quyidagi skilllar loyiha ustida ishlaganda faol yo'nalish sifatida qo'llansin. Ular Codex curated skill repozitoriyasida tayyor paket sifatida topilmadi, shu sababli bu faylda loyiha-local qoida ko'rinishida yoqildi.

### django-template-engineer

- Django template inheritance, include/partial, context processor va URL reverse patternlarini yaxshi bilish.
- Template o'zgartirganda `request.company`, user role, feature flag va plan cheklovlarini hisobga olish.
- Reusable fragmentlarni mavjud template strukturasiga mos joylashtirish; viewdan templatega keraksiz katta obyekt yubormaslik.
- Form, message va validation holatlarini Uzbek UI matnlari bilan izchil ko'rsatish.

### tailwind-designer

- Agar Tailwind mavjud yoki keyin qo'shilsa, utility classlarni CRMga mos, zich va ishga yo'naltirilgan UI uchun ishlatish.
- Rang, spacing, responsive grid va state classlarda yagona design tilini saqlash.
- Tailwind ishlatilmayotgan sahifalarda mavjud CSS patternini buzmasdan, Tailwindga o'xshash tizimli spacing/typography qarorlarini qo'llash.
- Dashboard, jadval, form va modal elementlarda o'qilishi, kontrast va mobil moslashuvni birinchi o'ringa qo'yish.

### ui-refactor

- UI refactor faqat kerakli sahifa yoki oqim doirasida bo'lsin; biznes logika bilan aralashtirmang.
- Takrorlangan template bloklari, buttonlar, status badge, empty state va table actionlarni partialga ajratish mumkin.
- Har bir refactorda role-based visibility, feature gating, CSRF, form method va URL nomlari saqlansin.
- Refactor natijasida layout shift, matn sig'masligi yoki mobile overflow paydo bo'lmasligi tekshirilsin.

### motion-ui

- Animatsiya faqat foydalanuvchi holatni tushunishi uchun ishlatilsin: loading, save success, panel open/close, notification, validation.
- CRM ish muhiti uchun harakatlar sokin, qisqa va chalg'itmaydigan bo'lishi kerak.
- `prefers-reduced-motion` hisobga olinsin.
- WebSocket notification, dashboard card update va modal transitionlarda motion qo'shilsa, performance va accessibility buzilmasin.

## Django va multi-tenant skill

- Subdomain asosida tenant aniqlashni tushunish kerak: `main.middleware.CompanyMiddleware`.
- `request.company` deyarli barcha biznes oqimlarida muhim. Query yozganda `company` bo'yicha ajratishni unutmaslik kerak.
- Landing, admin va tenant URL yo'naltirishlari farqli: `landing.urls`, `crm.admin_urls`, `main.urls`.
- Custom user modeli ishlatiladi: `AUTH_USER_MODEL = 'main.User'`.
- Bir xil username turli firmalarda bo'lishi mumkin, shuning uchun autentifikatsiyada `company` konteksti saqlanishi kerak.

## Model va ORM skill

- Asosiy modellar: `Company`, `Plan`, `PlanRequest`, `User`, `Mahsulot`, `DeliveryStock`, `StockHistory`, `Savdo`, `Nasiya`, `BillingPaymentLink`, `ClickTransaction`.
- Migratsiyalar ko'p va ishlab turgan domenlarga ta'sir qilishi mumkin. Model o'zgarsa, migratsiyani alohida tekshiring.
- Pul qiymatlarida `Decimal` ishlating, float bilan billing hisoblamang.
- Ombor va savdo o'zgarishlarida `transaction.atomic()` va `select_for_update()` ishlatiladigan mavjud patternlarga amal qiling.

## Service layer skill

- Biznes logikani view ichiga tiqmasdan, mavjud service fayllarga joylash afzal:
  - `main/services/stock_service.py` - ombor, yuklama, zaxira tarixi.
  - `main/services/billing_service.py` - tarif, payment link, lifecycle.
  - `main/services/auth_service.py` - user yaratish va auth oqimlari.
  - `main/services/credit_service.py` - nasiya/savdogar kredit oqimlari.
  - `main/services/demand.py`, `recommendations.py`, `parser.py` - analytics.
- View faqat request/response, form validatsiya va template/API natijasini boshqarishi kerak.

## Billing, trial va feature gating skill

- Tarif va ruxsat tekshiruvlarining markazi: `main/plan_utils.py`.
- Company lifecycle: `sync_company_lifecycle()` orqali trial, setup mode, overdue payment va active holatlar boshqariladi.
- Trial davrda ko'p featurelar ochiq, lekin backup odatda yopiq.
- To'lov holatini viewlarda qo'lda `payment_status == 'paid'` deb takrorlamang; helper/service funksiyalaridan foydalaning.
- `setup_mode`, `is_on_trial`, `trial_expires_at`, `next_payment_date`, `payment_status` maydonlari bir-biriga bog'liq.

## Click.uz integratsiyasi skill

- Click webhook fayli: `main/click_views.py`.
- Imzo tekshiruvi: `check_sign()`.
- `prepare` va `complete` bosqichlari idempotent bo'lishi kerak.
- `BillingPaymentLink` statuslari (`created`, `opened`, `paid`, `failed`) noto'g'ri qayta ishlatilmasligi kerak.
- Click endpointlar middleware orqali tenant cheklovidan o'tkaziladi: `/api/click`.
- Integratsiyani o'zgartirganda `simulate_click` management command va service testlarini tekshiring.

## Ombor, ishlab chiqarish va savdo skill

- Ombor miqdorlari `Mahsulot.miqdori`, yetkazib beruvchi qoldig'i esa `DeliveryStock` orqali yuritiladi.
- Legacy `YetkazibBeruvchi.mahsulotlar` string formati ham bor; eski oqimlar sinmasligi uchun ehtiyot bo'ling.
- Har bir muhim zaxira o'zgarishi `StockHistory`ga yozilishi kerak.
- Tasdiqlash oqimlarida race condition oldini olish uchun `select_for_update()` patternini saqlang.
- Qaytarish, nasiya va savdo operatsiyalari mahsulot qoldig'iga ta'sir qilishi mumkin.

## Nasiya va savdogar skill

- Nasiya viewlar: `main/nasiya_views.py`, model/utilitylar: `main/nasiya_models.py`, `main/credit_utils.py`, `main/services/credit_service.py`.
- Kredit muddatlari, kechikish jarimasi, oldindan to'lov chegirmasi va contract matnlari `Company` sozlamalariga bog'liq.
- To'lov grafigi va qarzdorlik statuslarida sana bilan ishlaganda `timezone.now()` va `Asia/Tashkent` kontekstini hisobga oling.

## Realtime, xarita va notification skill

- Channels sozlamalari: `crm/settings.py`, `crm/asgi.py`, `main/routing.py`, `main/consumers.py`.
- Redis bo'lmasa localda `InMemoryChannelLayer` ishlatiladi.
- Yetkazib beruvchi joylashuvi `YetkazibBeruvchi.last_lat/last_lng`, `LocationHistory` va `map_views.py` orqali yuritiladi.
- Realtime xabarlar va app notificationlar uchun `main/services/notifications.py` hamda `landing/realtime.py`ni tekshiring.

## Telegram bot skill

- Bot logikasi: `main/bot_logic.py`, service runner: `crm/bot_service.py`.
- Token va domenlar `.env` orqali keladi.
- Telegram ID bog'lashda xavfsizlik tekshiruvlarini saqlang; user/company kontekstini aralashtirmang.

## Analytics va hisobot skill

- Analytics servislar: `main/services/demand.py`, `main/services/recommendations.py`, `main/services/parser.py`.
- API endpointlar: `main/api/dashboard_api.py`, `main/analytics/views.py`, `main/analytics.py`, `main/analytics_views.py`.
- Pandas/numpy optional emas: requirements ichida bor va demand forecasting uchun ishlatiladi.
- Hisobotlar va Excel eksporti: `main/hisobot_views.py`, `openpyxl`.
- Katta querylarda ORM aggregation, date filter va company filterlarini to'g'ri qo'llang.

## Frontend skill

- Frontend asosan Django template, static CSS/JS, vanilla JavaScript, Fetch API va WebSocketdan iborat.
- Chart.js grafiklar va Leaflet xaritalar mavjud patternlar bilan kengaytiriladi.
- SaaS/CRM UI zich, tushunarli va ishga yo'naltirilgan bo'lishi kerak; marketing uslubidagi ortiqcha bezaklardan qoching.
- Template o'zgartirganda role, company, feature flag va mobile layoutni tekshiring.

## Backup va restore skill

- Backup oqimlari: `main/backup_views.py`, `main/backup_utils.py`.
- ZIP ichida JSON va media fayllar bo'lishi mumkin.
- Restore paytida dublikatlardan qochish uchun mavjud `update_or_create` patternlarini saqlang.
- Trial va tarifga bog'liq backup cheklovlarini buzmaslik kerak.

## Deploy va environment skill

- Production uchun docker fayllar: root `docker-compose.yml`, `crm/Dockerfile`, `deploy/`.
- `.env.example`dan sozlamalarni o'qing; haqiqiy `.env` sirlarini javoblarda oshkor qilmang.
- DB localda SQLite, productionda MySQL yoki boshqa sozlama bo'lishi mumkin.
- `BASE_DOMAIN`, `LANDING_DOMAINS`, `CSRF_TRUSTED_ORIGINS`, `REDIS_URL`, Click va Telegram envlari muhim.

## Test va tekshirish skill

Loyiha papkasidan (`D:\firma_crm\crm`) ishlating:

```powershell
D:\firma_crm\vwin\Scripts\python.exe manage.py check
D:\firma_crm\vwin\Scripts\python.exe manage.py test main
D:\firma_crm\vwin\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Kerak bo'lsa:

```powershell
D:\firma_crm\vwin\Scripts\python.exe manage.py simulate_click prepare 1 1000
D:\firma_crm\vwin\Scripts\python.exe manage.py shell < test_analytics.py
```

## Ishlash qoidalari

- Avval mavjud patternni toping, keyin o'zgartiring.
- `company` izolatsiyasini buzadigan query qoldirmang.
- Billing, Click, stock va nasiya oqimlarida test yozish yoki mavjud testni yangilash shartga yaqin.
- `db.sqlite3`, media fayllar, loglar, virtual muhitlar va `staticfiles`ni keraksiz o'zgartirmang.
- Secret, token, Click key, Telegram token va production domen ma'lumotlarini hujjatga yozmang.
- Kodda ortiqcha refactor qilmang; o'zgarish vazifaga bevosita bog'liq bo'lsin.
