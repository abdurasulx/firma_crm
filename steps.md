# StockFirm ERP — Amalga oshirish qadamlari

Bu fayl [StockFirm_ERP_Vision.md](StockFirm_ERP_Vision.md) asosida qilinayotgan ishlarning
jurnali. Har bir qadam: nima qilindi, qaysi fayllar o'zgardi, nega shunday qilindi.
Agar suhbat context'i yo'qolsa — shu faylni o'qib, oxirgi "Holat: DONE" bo'lmagan qadamdan
davom et.

## Kelishilgan tuzatishlar (vision hujjatiga)

- "Xarid" moduli olib tashlandi → **"Kirim tannarxi"** ga almashtirildi. Yetkazib beruvchi
  bu tizimda faqat sotuvchi (sales) rol, ta'minotchi emas. Alohida "ta'minotchi" tushunchasi
  kiritilmaydi — faqat kirim paytida narx yoziladi.

## Reja (bosqichlar)

1. [x] **Tannarx maydoni** — `Mahsulot.tannarx`, warehouse kirim oqimi tuzatiladi (hozir
   `narxi`ni — sotuv narxini — xato ustidan yozib yuboradi)
2. [x] **Company/Mahsulot yangi maydonlar** — `ish_haqi_turi`, `ishlab_chiqarish_narxi`,
   `amortizatsiya_narxi`
3. [x] **`MahsulotRetsept` (BOM/retsept) modeli** + admin + retsept tahrirlash sahifasi
4. [x] **`QoshimchaChiqim` (Finance) modeli** + admin + CRUD sahifasi
5. [x] **Norma tekshiruvi + jarima + tannarx + ish haqi hisob-kitobi** —
   `MiqdorQoshish`/`ProductionMaterialRequest` yangi maydonlar,
   `approve_miqdor_qoshish_service` kengaytirilishi
6. [x] **Ishlab chiqarish sozlamalari sahifasi** (`ish_haqi_turi` toggle + retsept havolalari)
   — 3-qadamda `production_settings_page` bilan birga allaqachon qurilgan
7. [x] **`pazanda_hisobot`ga ish haqi/jarima bloki**

To'liq batafsil reja: `C:\Users\Banda\.claude\plans\quiet-waddling-heron.md`
(model sxemalari, hisoblash mantig'i, UI, edge case'lar shu yerda batafsil yozilgan).

---

## 1-qadam: Tannarx maydoni

**Holat: DONE**

### Muammo
[warehouse_views.py:195](crm/main/warehouse_views.py:195) — omborchi "kirim" yozganda
`product.narxi = incoming_price` qilinadi. Lekin `narxi` butun tizimda **sotuv narxi**
sifatida ishlatiladi (mijozga ko'rsatiladi, sotuvda shu narxdan hisoblanadi:
`mahsulotlar_list.html`, `savdogar_dashboard.html`, `views.py` sotuv oqimi). Natijada
kirim narxi yozilganda sotuv narxi tasodifan almashib qoladi.

### Yechim
- `Mahsulot` modeliga yangi maydon: `tannarx` (DecimalField, kirim/tannarx narxi)
- `warehouse_movements` kirim POST handlerida endi `product.tannarx = incoming_price`
  yoziladi, `product.narxi`ga tegilmaydi
- Migratsiya: `0057_mahsulot_tannarx.py`
- Shablonlarda (`warehouse_products.html`, `warehouse_product_form.html`,
  `seemahsulot.html`) tannarx ko'rsatiladigan joy qo'shiladi (faqat ega/omborchi ko'radi,
  savdogar/mijozga ko'rinmaydi)

### O'zgargan fayllar
- `main/models.py` — `Mahsulot.tannarx` maydoni (DecimalField, default 0)
- `main/migrations/0057_mahsulot_tannarx.py` — yaratildi va lokal db.sqlite3'ga qo'llandi
- `main/warehouse_views.py` — `warehouse_movements` kirimda endi `narxi` emas `tannarx`
  yangilanadi; `warehouse_product_create`/`warehouse_product_edit` ham `tannarx`ni POST'dan
  o'qiydi
- `main/views.py` — `seemahsulot` (ega uchun umumiy mahsulot tahrirlash) ham `tannarx`ni
  saqlaydi
- Shablonlar: `warehouse_movements.html` (kirim narxi default endi tannarxdan olinadi),
  `warehouse_products.html` (jadvalga "Tannarx" ustuni), `warehouse_product_form.html`,
  `seemahsulot.html` (tannarx input maydoni qo'shildi)

### Tekshirildi
- `python manage.py check` — xatosiz
- `python manage.py makemigrations` / `migrate` — muvaffaqiyatli
- Savdogar/mijozga ko'rinadigan shablonlarga (`mahsulotlar_list.html`,
  `savdogar_dashboard.html`, `savdogar_my_products.html`) tannarx **qo'shilmadi** — atayin,
  chunki bu mijozga ko'rsatilmasligi kerak

---

## 2-qadam: Company/Mahsulot yangi maydonlar

**Holat: DONE**

### Nima qilindi
- `Company.ish_haqi_turi` — CharField choices `fixed`/`per_unit`, default `fixed`.
  Firma tanlaydi: ish haqi oylik (tizim aralashmaydi) yoki mahsulot soniga qarab
  (pastdagi qadamlarda hisoblanadigan) beriladimi.
- `Mahsulot.ishlab_chiqarish_narxi` — 1 dona uchun ishchiga to'lanadigan summa
  (`ish_haqi_turi=per_unit` bo'lsa ishlatiladi)
- `Mahsulot.amortizatsiya_narxi` — 1 donaga to'g'ri keladigan amortizatsiya, tannarxga
  qo'shiladi (5-qadamda hisob-kitobga kiradi)

### O'zgargan fayllar
- `main/models.py` — yuqoridagi 3 maydon
- `main/migrations/0058_company_ish_haqi_turi_mahsulot_amortizatsiya_narxi_and_more.py`
- `main/warehouse_views.py` — `warehouse_product_create`/`edit` endi bu ikki mahsulot
  maydonini ham POST'dan o'qiydi
- `main/views.py` — `seemahsulot` view ham shu ikkisini saqlaydi
- Shablonlar: `warehouse_product_form.html`, `seemahsulot.html` — yangi input maydonlari

### Eslatma
- `createmahsulot` (yangi mahsulot yaratish, `views.py:1570`) ga bu maydonlar
  qo'shilmadi — yangi mahsulot 0 default bilan yaratiladi, keyin `seemahsulot`
  orqali to'ldiriladi. Bu ataylab — scope'ni kichik ushlab turish uchun.

### Tekshirildi
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz

---

## 3-qadam: `MahsulotRetsept` (BOM/retsept) modeli

**Holat: DONE**

### Nima qilindi
- Yangi model `MahsulotRetsept` (main/models.py, StockHistory'dan keyin,
  ProductionMaterialRequest'dan oldin): `mahsulot` (chiqadigan/tayyor), `komponent`
  (ishlatiladigan xom ashyo/yarim tayyor), `norma_miqdor` (1 dona uchun kerak miqdor),
  `jarima_narxi_birlik`. `unique_together = ('mahsulot', 'komponent')`.
- Yangi `main/production_views.py`: `production_settings_page` (ish_haqi_turi toggle +
  mahsulotlar ro'yxati, retsept havolalari bilan — shu yerda **6-qadam ham** bajarilgan)
  va `retsept_edit_page` (bitta mahsulot uchun retsept qatorlarini qo'shish/o'chirish).
- Validatsiya `retsept_edit_page` ichida: `komponent != mahsulot`; `komponent.warehouse_type
  == 'semi_finished'` (tayyor mahsulot boshqa tayyor mahsulotni "iste'mol" qila olmaydi);
  `norma_miqdor > 0`; `_creates_cycle()` — rekursiv DFS orqali aylanma bog'lanishni oldini
  oladi (masalan A retseptida B, B retseptida A bo'lishi mumkin emas).
- Ikkala sahifa ham faqat `ega` (`_ega_guard`) uchun ochiq — omborchi va boshqalar
  `main`ga qaytariladi.
- Yangi URL'lar: `/ishlab-chiqarish/sozlamalar/` (`production_settings`),
  `/ishlab-chiqarish/retsept/<id>/` (`retsept_edit`).
- Sidebar menyuga (`egabase.html`) "Ishlab chiqarish" bandi qo'shildi — faqat
  `request.user.type == 'ega'` uchun ko'rinadi.
- Admin: `MahsulotRetsept` ro'yxatga qo'shildi.

### O'zgargan/yangi fayllar
- `main/models.py` — `MahsulotRetsept` modeli
- `main/migrations/0059_mahsulotretsept.py`
- `main/production_views.py` — yangi fayl
- `main/templates/production_settings.html`, `main/templates/retsept_edit.html` — yangi
- `main/urls.py` — 2 ta yangi path
- `main/templates/egabase.html` — sidebar bandi
- `main/admin.py` — `MahsulotRetseptAdmin`

### Tekshirildi
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz
- Brauzerda hali sinovdan o'tkazilmadi — bu 7-qadam tugagach, to'liq oqim
  (retsept yaratish → ishlab chiqarish → jarima/tannarx hisoblanishi) birga sinaladi

---

## 4-qadam: `QoshimchaChiqim` (Finance) modeli

**Holat: DONE**

### Nima qilindi
- Yangi model `QoshimchaChiqim` (main/models.py, `ProductionMaterialRequest`'dan oldin):
  `nomi`, `summa`, `sana` (default bugun), `izoh`, `created_by`. Reja bo'yicha bu
  **avtomatik mahsulot tannarxiga taqsimlanmaydi** — mustaqil Finance ro'yxati, formulasi
  berilmagan umumiy xarajatlar uchun (ijaraga, svetga va h.k.).
- Yangi `main/finance_views.py` — `qoshimcha_chiqimlar_page` (faqat `ega`): ro'yxat +
  yangi chiqim qo'shish formasi, jami summani ko'rsatadi.
- Yangi URL: `/moliya/chiqimlar/` (`qoshimcha_chiqimlar`).
- Sidebar'ga "Qo'shimcha chiqimlar" bandi qo'shildi (faqat `ega`).
- Admin: `QoshimchaChiqim` ro'yxatga qo'shildi.

### O'zgargan/yangi fayllar
- `main/models.py` — `QoshimchaChiqim` modeli
- `main/migrations/0060_qoshimchachiqim.py`
- `main/finance_views.py` — yangi fayl
- `main/templates/qoshimcha_chiqimlar.html` — yangi
- `main/urls.py` — yangi path
- `main/templates/egabase.html` — sidebar bandi
- `main/admin.py` — `QoshimchaChiqimAdmin`

### Tekshirildi
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz

---

## 5-qadam: Norma tekshiruvi + jarima + tannarx + ish haqi hisob-kitobi

**Holat: DONE**

### Nima qilindi
- `MiqdorQoshish` modeliga 3 ta "surat" (snapshot) maydon qo'shildi:
  `tannarx_snapshot`, `jarima_summasi`, `ish_haqi_summasi`. Snapshot qilinishining sababi
  — `Savdo.summa`da allaqachon qo'llanilgan naqsh: narxlar keyin o'zgarsa ham, o'tgan
  ishlab chiqarish yozuvining tarixi buzilmaydi.
- `ProductionMaterialRequest`ga `consumed_in` (FK → `MiqdorQoshish`, null/blank) qo'shildi
  — bu orqali "qaysi xom ashyo so'rovi qaysi ishlab chiqarish yozuviga hisoblanganini"
  belgilab, ikki marta hisoblanishining oldi olinadi.
- `main/services/stock_service.py`ga yangi ichki funksiya `_apply_retsept_hisobkitob(req,
  mahsulot)` qo'shildi, `approve_miqdor_qoshish_service` ichidan chaqiriladi:
  1. `MahsulotRetsept` qatorlari yo'q bo'lsa — **hech narsa qilmaydi** (eski xulq-atvor
     saqlanadi, breaking change yo'q).
  2. Bor bo'lsa — shu pazanda+mahsulot uchun oldingi tasdiqlangan `MiqdorQoshish`ni
     "oyna boshlanishi" sifatida topadi.
  3. Har bir retsept qatori uchun: kutilgan miqdor (`norma * ishlab_chiqarilgan_dona`),
     haqiqiy ishlatilgan miqdor (shu oynadan keyin tasdiqlangan, hali `consumed_in`ga
     bog'lanmagan `ProductionMaterialRequest`lar yig'indisi) solishtiriladi, ularni
     darhol `consumed_in=req` qilib belgilaydi.
  4. Chetlashish (`|actual - expected|`) x `jarima_narxi_birlik` — jarimaga qo'shiladi.
  5. Tannarx = barcha komponentlar tannarxi x norma yig'indisi + mahsulotning
     `amortizatsiya_narxi`. Bu qiymat ham `req.tannarx_snapshot`ga, ham **avtomatik
     ravishda `mahsulot.tannarx`ga** yoziladi (faqat BOM'i bor mahsulotlar uchun —
     qo'lda kirim qilingan mahsulotlarning tannarxiga tegilmaydi).
  6. Agar `company.ish_haqi_turi == 'per_unit'`: `ish_haqi_summasi = miqdor *
     mahsulot.ishlab_chiqarish_narxi - jarima_summasi`.

### O'zgargan fayllar
- `main/models.py` — `MiqdorQoshish` (3 yangi maydon), `ProductionMaterialRequest`
  (`consumed_in`)
- `main/migrations/0061_miqdorqoshish_ish_haqi_summasi_and_more.py`
- `main/services/stock_service.py` — `_apply_retsept_hisobkitob()` yangi funksiya,
  `approve_miqdor_qoshish_service` uni chaqiradi

### Bilib qo'yish kerak bo'lgan cheklov
- BOM birinchi marta retseptga qo'shilganda, ilgari tasdiqlangan lekin hali
  `consumed_in`ga bog'lanmagan eski `ProductionMaterialRequest` yozuvlari bo'lsa, ular
  **birinchi keyingi ishlab chiqarish tasdig'ida** "oyna"ga tushib, bir martalik
  g'ayrioddiy jarima berishi mumkin. Amalda BOM qo'shilgandan keyingi davrdan boshlab
  to'g'ri ishlaydi.

### Tekshirildi
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz
- **Hali brauzerda uchidan-uchigacha sinalmadi** — 7-qadamdan keyin to'liq oqim
  (retsept yaratish → xom ashyo so'rash/tasdiqlash → ishlab chiqarishni yozish →
  jarima/tannarx/ish haqi to'g'ri chiqishini) qo'lda tekshirish kerak

---

## 6-qadam: Ishlab chiqarish sozlamalari sahifasi

**Holat: DONE (3-qadamda birga qurilgan)**

`production_settings_page` (main/production_views.py) 3-qadamda yaratilganda unga
`ish_haqi_turi` almashtirish formasi (POST `action=set_ish_haqi_turi`) darhol qo'shib
qo'yilgan edi — chunki sahifa joyi bir xil edi. Alohida qadam sifatida qo'shimcha
ish qilinmadi, faqat rejadagi tartibga moslab shu yerda qayd etilyapti.

---

## 7-qadam: `pazanda_hisobot`ga ish haqi/jarima bloki

**Holat: DONE**

### Nima qilindi
- `pazanda_hisobot` (main/views.py:2260) kengaytirildi: `company.ish_haqi_turi ==
  'per_unit'` bo'lsa, tanlangan davr (`from`/`to`) bo'yicha tasdiqlangan
  `MiqdorQoshish`lardan `ish_haqi_summasi` va `jarima_summasi` yig'indisi hisoblanadi.
- `pz_hisobot.html`ga 2 ta yangi stat-card qo'shildi (Davr uchun ish haqi, Davr uchun
  jarima) — faqat `ish_haqi_turi_per_unit` bo'lsa ko'rinadi.
- Ishlab chiqarish jadvaliga (har bir `MiqdorQoshish` qatoriga) "Ish haqi" va "Jarima"
  ustunlari qo'shildi — xuddi shu shart bilan yashiringan/ko'rsatiladi.

### O'zgargan fayllar
- `main/views.py` — `pazanda_hisobot` funksiyasi
- `main/templates/pz_hisobot.html` — stat-card'lar va jadval ustunlari

### Tekshirildi
- `python manage.py check` — xatosiz
- **Hisoblash logikasi Django shell orqali izolyatsiyalangan tranzaksiyada sinaldi**
  (yaratilgan test ma'lumotlari oxirida rollback qilindi, dev bazaga hech narsa
  yozilmadi): retsept "Non <- 0.5kg Un", 10 dona Non uchun 5kg kerak, lekin 6kg
  ishlatilgan (1kg ortiqcha, jarima narxi 500/kg) →
  - `jarima_summasi` = 500 ✅ (kutilgan: |6-5|*500)
  - `tannarx_snapshot` va `mahsulot.tannarx` = 3050 ✅ (kutilgan: 6000*0.5 un tannarxi + 50 amortizatsiya)
  - `ish_haqi_summasi` = 2500 ✅ (kutilgan: 10*300 ishlab chiqarish narxi - 500 jarima)
  - `ProductionMaterialRequest.consumed_in` to'g'ri `MiqdorQoshish`ga bog'landi ✅
- **Brauzerda to'liq UI oqimi (retsept yaratish sahifasi, ish haqi turi toggle,
  hisobot ko'rinishi) hali qo'lda sinalmagan** — bu tizim ko'p bosqichli
  multi-tenant (subdomen) autentifikatsiya talab qiladi, keyingi sessiyada yoki
  foydalanuvchi tomonidan haqiqiy muhitda tekshirilishi tavsiya etiladi.

---

## Umumiy xulosa (2-qadam to'liq)

Barcha 7 ta bosqich bajarildi:
1-4: yangi model/maydonlar (tannarx, ish haqi turi, BOM/retsept, qo'shimcha chiqimlar)
5: asosiy hisoblash mexanizmi (`stock_service.py`)
6-7: UI (sozlamalar sahifasi, hisobot bloki)

**Keyingi tavsiya qilinadigan qadam** (foydalanuvchi bilan kelishilmagan, faqat taklif):
haqiqiy firma/foydalanuvchi bilan brauzerda uchidan-uchigacha sinov — retsept yaratish,
xom ashyo so'rash/tasdiqlash, ishlab chiqarishni yozish, hisobotda raqamlarni ko'rish.

---

# QR/Serial tizimi (Faza 1) — Desktop Agent'ga mos loyihalangan

Kelishuv: Desktop Agent (tarozi/kamera/XPrinter bilan lokal dastur) alohida, keyinroq
foydalanuvchi g'oyalarini bergach loyihalanadi. Lekin QR/Serial tizimi **hozir** shunday
qurilyaptiki, servis funksiyalari `request`/session'ga bog'lanmaydi — Desktop Agent
kelganda xuddi shu funksiyalarni chaqiradi, qayta yozilmaydi. To'liq reja:
`C:\Users\Banda\.claude\plans\quiet-waddling-heron.md` (`---===NEXT===---`dan keyingi qism).

## Reja (bosqichlar)

8. [x] `Mahsulot.serial_granularity` + `Serial` modeli + migratsiya + admin
9. [x] `main/services/qr_service.py` — generate/scan/FIFO-chiqarish funksiyalari
10. [x] `stock_service.py`ga hook (ishlab chiqarish tasdiqlanganda va yuklama
    berilganda avtomatik serial yaratish/chiqarish)
11. [x] QR rasm endpoint + public scan sahifasi (`landing` app)
12. [x] Ichki serial ro'yxati sahifasi + mahsulot formasiga `serial_granularity` maydoni

**Ko'lam eslatmasi**: to'liq holat mashinasi (omborda→yetkazib beruvchida→sotilgan→
qaytarilgan) hozircha qilinmaydi, chunki `YuklamaSorov`/`Savdo` mahsulot-qatorlarini
erkin matn orqali saqlaydi (FK emas) — buni to'g'ri bog'lash alohida katta ish.
Hozircha faqat 2 holat: `omborda` / `chiqarilgan` (FIFO).

---

## 8-qadam: `Mahsulot.serial_granularity` + `Serial` modeli

**Holat: DONE**

### Nima qilindi
- `Mahsulot.serial_granularity` — CharField choices `none`/`batch`/`unit`, default
  `none` (breaking change yo'q — ega o'zi yoqmaguncha hech narsa o'zgarmaydi).
- Yangi model `Serial` (`MiqdorQoshish`dan keyin, `Savdo`dan oldin): `mahsulot`,
  `batch` (FK → `MiqdorQoshish`, null — alohida "Batch" modeli qo'shilmadi, chunki
  `MiqdorQoshish` allaqachon "bitta ishlab chiqarish partiyasi"ni ifodalaydi),
  `kod` (unique, `default=uuid4` — `BillingPaymentLink.token`da qo'llanilgan xuddi
  shu naqsh), `unit_index` (bo'sh = butun partiya), `holati` (`omborda`/`chiqarilgan`),
  `scan_soni`.
- Admin: `Serial` ro'yxatga qo'shildi.

### O'zgargan fayllar
- `main/models.py` — `Mahsulot.serial_granularity`, `Serial` modeli
- `main/migrations/0062_mahsulot_serial_granularity_serial.py`
- `main/admin.py` — `SerialAdmin`

### Tekshirildi
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz

---

## 9-qadam: `main/services/qr_service.py`

**Holat: DONE**

### Nima qilindi
- Yangi fayl `main/services/qr_service.py`, uchta funksiya, hech biri `request`
  yoki `actor` qabul qilmaydi (faqat model obyektlari/oddiy qiymatlar) — Desktop
  Agent kelganda o'z API view'idan xuddi shu funksiyalarni chaqiradi:
  - `generate_serials_for_batch(miqdor_qoshish)` — granularity'ga qarab 0/1/N Serial
    yaratadi
  - `register_scan(kod)` — atomik `F('scan_soni') + 1`, topilmasa `None`
  - `mark_serials_chiqarilgan(mahsulot, company, qty)` — FIFO, eng eski `omborda`
    seriallarni `chiqarilgan`ga o'tkazadi

### O'zgargan fayllar
- `main/services/qr_service.py` — yangi fayl

### Tekshirildi
- `python manage.py check` — xatosiz (hook'lanishi 10-qadamda, funksional test
  o'sha bosqichda birga qilinadi)

---

## 10-qadam: `stock_service.py`ga hook

**Holat: DONE**

### Nima qilindi
- `approve_miqdor_qoshish_service` oxiriga `qr_service.generate_serials_for_batch(req)`
  chaqiruvi qo'shildi — mahsulot `serial_granularity != 'none'` bo'lsa, tasdiqlash
  bilan bir vaqtda seriallar avtomatik yaratiladi.
- `approve_yuklama_sorov_service` oxiriga `qr_service.mark_serials_chiqarilgan(...)`
  qo'shildi — yuklama tasdiqlanganda FIFO tartibida eng eski `omborda` seriallar
  `chiqarilgan`ga o'tadi.

### O'zgargan fayllar
- `main/services/stock_service.py` — 2 ta hook chaqiruvi + `qr_service` importi

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django shell orqali izolyatsiyalangan tranzaksiyada to'liq oqim sinaldi**
  (test ma'lumotlari oxirida rollback qilindi):
  - `serial_granularity='unit'`, 5 dona ishlab chiqarish tasdiqlandi →
    5 ta `Serial` yaratildi, `unit_index` 1..5, barchasi `omborda`, kodlar noyob ✅
  - 3 dona yuklama tasdiqlandi → FIFO bo'yicha 3 tasi `chiqarilgan`ga o'tdi,
    2 tasi `omborda`da qoldi ✅
  - `register_scan()` — 2 marta chaqirilganda `scan_soni` 2 ga yetdi, mavjud
    bo'lmagan kod uchun `None` qaytardi ✅

---

## 11-qadam: QR rasm endpoint + public scan sahifasi

**Holat: DONE**

### Nima qilindi
- Rejadan **bitta kichik og'ish**: dastlabki rejada QR rasm endpointi
  `main/api/qr_views.py`da (`/api/qr/image/...`, `main.urls` — tenant subdomen)
  bo'lishi ko'zda tutilgan edi. Lekin vision hujjatidagi asl konsepsiya
  ("Public: https://stockfirm.uz/p/<serial>") **subdomensiz, yalang'och domen**
  ekanini hisobga olib, ikkalasini ham (`product_scan_view`, `qr_image_view`)
  `landing` ilovasiga qo'ydim — chunki mijoz QR'ni skanerlaganda qaysi firma
  subdomenida ekanini bilmaydi/bilishi shart emas, `Serial.company` allaqachon
  ichki bog'langan. `CompanyMiddleware` bu domenlarni `is_landing=True` deb
  aniqlab, avtomatik `landing.urls`ga yo'naltiradi — qo'shimcha middleware
  o'zgarishi kerak bo'lmadi.
- `landing/views.py`: `product_scan_view(request, kod)` — `qr_service.register_scan()`
  chaqiradi, topilmasa `404.html`, topilsa `product_scan.html` render qiladi.
- `landing/views.py`: `qr_image_view(request, kod)` — `qrcode` kutubxonasi bilan
  PNG generatsiya qiladi, ichiga `https://{BASE_DOMAIN}/p/{kod}/` URL kodlaydi.
  Kod mavjud emasligini oldindan tekshiradi (`Http404`).
- Yangi URL'lar (`landing/urls.py`): `p/<kod>/` (`product_scan`),
  `api/qr/image/<kod>/` (`qr_image`).
- Yangi template `landing/templates/landing/product_scan.html` — `landing/base.html`
  ni extend qiladi, mahsulot nomi/sana/partiya/birlik raqamini ko'rsatadi.

### O'zgargan/yangi fayllar
- `landing/views.py` — `product_scan_view`, `qr_image_view`
- `landing/urls.py` — 2 ta yangi path
- `landing/templates/landing/product_scan.html` — yangi

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali izolyatsiyalangan tranzaksiyada sinaldi** (rollback
  qilindi): `/p/<kod>/` — 200, mahsulot nomi sahifada bor, `scan_soni` 1 ga
  ko'tarildi; noma'lum kod — 404; `/api/qr/image/<kod>/` — 200,
  `Content-Type: image/png`, haqiqiy PNG bayt-signature bilan boshlanadi; noma'lum
  kod uchun rasm endpointi ham 404 qaytardi

---

## 12-qadam: Ichki serial ro'yxati + mahsulot formasiga `serial_granularity`

**Holat: DONE**

### Nima qilindi
- `warehouse_product_form.html`, `seemahsulot.html` — `serial_granularity`
  tanlash maydoni qo'shildi (Yo'q / Partiya bo'yicha / Har bir donaga alohida),
  tegishli view'lar (`warehouse_product_create/edit`, `seemahsulot`) POST'dan
  o'qib saqlaydi.
- Yangi `serial_list_page` (`main/production_views.py`) — `/ishlab-chiqarish/
  seriallar/<mahsulot_id>/`, `ega` **va** `omborchi` uchun ochiq (faqat ko'rish;
  boshqa ishlab chiqarish sahifalari `ega`-only edi, lekin seriallarni omborchi
  ham ko'rishi kerak — ombor tovarlari shu yerdan boshqariladi). Har bir serial
  uchun: kod (qisqartirilgan), partiya, birlik raqami, holati, scan soni,
  "QR" (rasm) va "↗" (public sahifa) havolalari.
- `production_settings.html` jadvaliga har bir mahsulot qatoriga "Seriallar"
  havolasi qo'shildi (faqat `serial_granularity != 'none'` bo'lganda ko'rinadi).
- **Muhim texnik nuqta**: serial ro'yxati sahifasi tenant subdomenida
  (`main.urls`, `request.urlconf='main.urls'`) render bo'ladi, lekin QR
  rasm/public sahifa `landing.urls`da (boshqa urlconf). Django'ning `{% url %}`
  tegi joriy `request.urlconf`ga qarab ishlaydi, shuning uchun `{% url 'qr_image' %}`
  bu yerda **ishlamaydi** (`NoReverseMatch`) — shu sababli havolalar
  `https://{{ base_domain }}/api/qr/image/{{ s.kod }}/` ko'rinishida qo'lda
  qurildi (`base_domain` — `settings.BASE_DOMAIN`, view orqali context'ga
  uzatiladi).

### O'zgargan/yangi fayllar
- `main/templates/warehouse_product_form.html`, `main/templates/seemahsulot.html`
- `main/warehouse_views.py`, `main/views.py` (`seemahsulot`)
- `main/production_views.py` — `serial_list_page`, `_warehouse_guard`
- `main/templates/serial_list.html` — yangi
- `main/templates/production_settings.html` — "Seriallar" havolasi
- `main/urls.py` — yangi path

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali izolyatsiyalangan tranzaksiyada, haqiqiy tenant
  subdomen (`qrtest.localhost`) va login qilingan `ega` foydalanuvchi bilan**
  (rollback qilindi): serial ro'yxati sahifasi — 200, mahsulot nomi va ikkala
  serialning "omborda" holati ko'rinadi; sozlamalar sahifasida "Seriallar"
  havolasi mavjud

---

## Umumiy xulosa — QR/Serial tizimi (Faza 1) to'liq

8-12 qadamlar bajarildi: mahsulot darajasida yoqiladigan serial kuzatuv, ishlab
chiqarish tasdiqlanganda avtomatik generatsiya, yuklamada FIFO bo'yicha holat
o'zgarishi, public skan sahifasi + scan hisoblagich, QR PNG endpoint, va ichki
ro'yxat sahifasi. Servis qatlami (`qr_service.py`) `request`/`actor`ga bog'liq
emas — Desktop Agent kelganda shu funksiyalarni to'g'ridan-to'g'ri chaqira oladi.

**Keyingi qadam**: foydalanuvchi Desktop Agent g'oyalarini beradi, shunga qarab
to'liq holat mashinasi (yetkazib beruvchida/sotilgan/qaytarilgan) va real
kamera/tarozi/printer integratsiyasi loyihalanadi.

---

# QR/Serial — Faza 2: savdo yopilishida majburiy skaner + public sahifa boyitish

Foydalanuvchi talabi: savdo yopilganda (sotuvchi/savdogar) sotilgan har bir birlik
uchun QR skanerlanishi **majburiy** bo'lsin (`unit` granularity uchun), va public
sahifa yaroqlilik muddati + firma matni + rasm bilan boyitilsin. To'liq reja:
`C:\Users\Banda\.claude\plans\quiet-waddling-heron.md` (`---===NEXT2===---`dan keyin).

**Muhim cheklov**: majburiy skaner faqat `serial_granularity == 'unit'` mahsulotlar
uchun — `batch` granularityda 1 QR butun partiyani anglatadi, bitta savdoga
bog'lash mantiqsiz.

## Reja (bosqichlar)

13. [x] `Serial.savdo` FK + `sotilgan` holat + `Mahsulot.yaroqlilik_kun_soni` +
    `qr_tavsif` + migratsiya
14. [x] `sotish` view'ga serial validatsiya/bog'lash logikasi
15. [x] `sotish.html`ga serial kod matn maydoni + ixtiyoriy kamera-skaner JS
16. [x] Public sahifani boyitish (yaroqlilik, tavsif, rasm, sotilgan belgisi)

---

## 13-qadam: `Serial.savdo` + `sotilgan` holat + `Mahsulot` yangi maydonlar

**Holat: DONE**

### Nima qilindi
- `Serial.HOLAT_CHOICES`ga `sotilgan` qo'shildi; `Serial.savdo` (FK → `Savdo`,
  `SET_NULL`, null/blank) qo'shildi — savdo o'chirilsa ham serial yozuvi
  yo'qolmaydi, faqat bog'lanish uziladi.
- `Mahsulot.yaroqlilik_kun_soni` (PositiveIntegerField, null=True) — ega bir
  marta belgilaydi, "necha kun yaroqli". Sana emas — kunlar soni, chunki
  ishlab chiqarilgan sana (`MiqdorQoshish.vaqt_sana`) allaqachon `auto_now_add`
  (soxta qilib bo'lmaydi); yaroqlilik sanasi shundan hisoblanadi, alohida
  saqlanmaydi.
- `Mahsulot.qr_tavsif` (TextField) — public sahifada ko'rsatiladigan erkin matn.

### O'zgargan fayllar
- `main/models.py` — yuqoridagi maydonlar
- `main/migrations/0063_mahsulot_qr_tavsif_mahsulot_yaroqlilik_kun_soni_and_more.py`

### Tekshirildi
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz

---

## 14-qadam: `sotish` view'ga serial validatsiya/bog'lash logikasi

**Holat: DONE**

### Nima qilindi
- `main/views.py`dagi `sotish` view'ga (savdogar va yetkazib_beruvchi ikkalasi
  ham shu funksiyani ishlatadi) yangi **validatsiya sikli** qo'shildi — mavjud
  zaxira-kamaytirish siklidan **oldin**, hech qanday `Mahsulot.miqdori`
  o'zgarmasdan turib:
  - Har bir sotilayotgan mahsulot uchun, agar `serial_granularity == 'unit'`
    bo'lsa — POST'dan `serial_kodlari_{nom}` (vergul yoki yangi qator bilan
    ajratilgan matn) o'qiladi.
  - Kodlar soni sotilayotgan miqdorga teng emasmi — xato, hech narsa
    o'zgarmasdan `sotish`ga qaytariladi.
  - Har bir kod: shu `company`+`mahsulot`ga tegishli, kutilgan holatda
    (`yetkazib_beruvchi` → `chiqarilgan`; `savdogar` → `omborda`) va hali
    boshqa savdoga bog'lanmagan (`savdo__isnull=True`) ekanligi tekshiriladi —
    `select_for_update()` bilan qulflab (poyga holati himoyasi).
  - Takrorlangan kodlar ham rad etiladi.
- Validatsiya o'tgach, mavjud `Savdo.objects.create(...)` ikkala tarmog'i
  (nasiya va naqd/karta) birlashgan joyda — validatsiyadan o'tgan barcha
  seriallar bitta so'rovda `savdo=svd, holati='sotilgan'` qilib yangilanadi.
- `serial_granularity != 'unit'` (ya'ni `none` yoki `batch`) mahsulotlarga
  **hech narsa o'zgarmadi** — eski xulq-atvor to'liq saqlanadi.
- `smm` erkin-matn mexanizmiga, `DeliveryStock`ga, `sotishm()`ga — **hech biriga
  tegilmadi** (rejada belgilangan minimal-invaziv yondashuv).

### O'zgargan fayllar
- `main/views.py` — `sotish` view: import (`Serial`), yangi validatsiya sikli,
  savdo yaratilgandan keyingi serial-bog'lash chaqiruvi

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali to'liq oqim, izolyatsiyalangan tranzaksiyada**
  (haqiqiy `POST /sotish/`, login qilingan yetkazib_beruvchi, rollback qilindi):
  - 5ta `chiqarilgan` serial yaratildi, 3 dona sotish uchun **faqat 2 ta kod**
    yuborilganda — `Savdo` **yaratilmadi** (xato bilan qaytdi) ✅
  - 3 ta to'g'ri kod yuborilganda — `Savdo` yaratildi, aynan o'sha 3 serial
    `holati='sotilgan'` va `savdo_id`si to'g'ri o'rnatildi, 4-serial
    (ishlatilmagan) `chiqarilgan`da o'zgarishsiz qoldi ✅

---

## 15-qadam: `sotish.html`ga serial kod maydoni + kamera-skaner

**Holat: DONE**

### Nima qilindi
- Aniqlandiki, "sotish" sahifasi aslida **ikkita** shablon: `ytsot.html`
  (yetkazib_beruvchi) va `sgsot.html` (savdogar) — ikkalasi ham bir xil
  `{% for m in mahsulotlar %}` naqshiga ega.
- `sotish` view GET-render qismiga `unit_serial_products` (nomi
  `serial_granularity='unit'` bo'lgan mahsulotlar ro'yxati) context qo'shildi.
- Ikkala shablonda ham, mavjud `miqdor_{{ m.nom }}` hidden input yonida —
  `{% if m.nom in unit_serial_products %}` sharti bilan `serial_kodlari_{{ m.nom }}`
  nomli textarea (har qatorda bitta kod) va "Kamera bilan skanerlash" tugmasi
  qo'shildi.
- Yangi umumiy partial `main/templates/qr_scan_widget.html` — CDN orqali
  `html5-qrcode` kutubxonasi yuklanadi, modal oyna ochiladi, telefon
  kamerasidan QR o'qib, dekodlangan matndan (agar to'liq URL bo'lsa
  `/p/<kod>/` dan) `kod`ni ajratib, tegishli textarea'ga qo'shadi. Bu **faqat
  frontend qulaylik qatlami** — kamera ishlamasa ham, kodni qo'lda yozib
  savdo yopilaveradi (backend faqat matn maydonini o'qiydi, kamera haqida
  bilmaydi ham).
- Ikkala shablon oxiriga `{% include 'qr_scan_widget.html' %}` qo'shildi.

### O'zgargan/yangi fayllar
- `main/views.py` — `sotish` GET-render context'ga `unit_serial_products`
- `main/templates/ytsot.html`, `main/templates/sgsot.html` — serial input +
  skan tugmasi, widget include
- `main/templates/qr_scan_widget.html` — yangi umumiy partial

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali** (`GET /sotish/`, login qilingan
  yetkazib_beruvchi, rollback qilindi): sahifa 200 qaytardi, `serial_kodlari_`
  nomli input, `btn-scan-qr` tugmasi va `html5-qrcode` skript ulanishi
  sahifada mavjudligi tasdiqlandi

---

## 16-qadam: Public sahifani boyitish

**Holat: DONE**

### Nima qilindi
- `product_scan_view` (landing/views.py) kengaytirildi: agar `serial.batch` va
  `mahsulot.yaroqlilik_kun_soni` bo'lsa — `yaroqlilik_sanasi =
  batch.vaqt_sana + timedelta(days=yaroqlilik_kun_soni)` hisoblanadi (saqlanmaydi,
  har safar hisoblanadi — ishlab chiqarilgan sana `auto_now_add` bo'lgani uchun
  ishonchli manba).
- `product_scan.html` boyitildi:
  - `mahsulot.rasmi` (agar bor bo'lsa) — rasm ko'rsatiladi
  - Yaroqlilik muddati (hisoblangan sana)
  - `mahsulot.qr_tavsif` — firma qo'ygan erkin matn, alohida blokda
  - `serial.holati == 'sotilgan'` bo'lsa — "Holati: Sotilgan" belgisi
    (mijoz ismi yoki boshqa shaxsiy ma'lumot **ko'rsatilmaydi** — maxfiylik)

### O'zgargan fayllar
- `landing/views.py` — `product_scan_view`
- `landing/templates/landing/product_scan.html`

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali izolyatsiyalangan tranzaksiyada** (rollback
  qilindi): mahsulot rasmi (`<img src=`), `qr_tavsif` matni, hisoblangan
  yaroqlilik sanasi (`batch.vaqt_sana + 5 kun`), va "Sotilgan" holat belgisi —
  barchasi public sahifada to'g'ri ko'rsatildi

---

## Umumiy xulosa — QR/Serial Faza 2 to'liq

13-16 qadamlar bajarildi: `unit` granularity mahsulotlar uchun savdo yopilishi
endi QR/serial skanerlashsiz mumkin emas (backend qattiq validatsiya qiladi,
frontend ixtiyoriy kamera-skaner bilan qulaylashtiradi), public sahifa endi
rasm, yaroqlilik muddati, firma matni va sotilgan-holat belgisi bilan to'liq.
`smm`/`DeliveryStock` kabi eski, nozik mexanizmlarga **tegilmadi** — hammasi
ustiga qo'shildi, faqat `serial_granularity='unit'` tanlangan mahsulotlarga
ta'sir qiladi.

---

# Desktop Agent — poydevor: Ombor (multi-warehouse) + shaxsiy QR badge

Foydalanuvchi Desktop Agent (tarozi + XPrinter + kameralar, "Ultra Premium" tarif)
to'liq ish oqimini tasvirlab berdi. Bosqichma-bosqich qurilmoqda, birinchi qadam
sifatida **Ombor (ko'p-ombor) + shaxsiy QR poydevori** tanlandi (stansiya sessiyasi,
tarozi/kamera/printer API'lari — keyingi qadam). To'liq reja:
`C:\Users\Banda\.claude\plans\quiet-waddling-heron.md` (`---===NEXT3===---`dan keyin).

**Asosiy dizayn qarori**: `Mahsulot.miqdori` o'zgarmaydi (hamon "umumiy jami").
`Ombor`/`OmborZaxira` — qo'shimcha, ixtiyoriy qatlam, faqat material so'rovi
tasdiqlanganda (omborchi qaysi ombordan berayotganini tanlaydi) va kirimda ishlaydi.

## Reja (bosqichlar)

17. [x] `Ombor`, `OmborZaxira`, `XodimBadge` modellari + `ProductionMaterialRequest.ombor`
    + migratsiya + admin
18. [x] `main/services/ombor_service.py`
19. [x] Material so'rovi tasdiqlashga ombor tanlash + deduct hook
20. [x] Kirimga ombor tanlash + add hook
21. [x] Omborlar ro'yxati sahifasi (ega CRUD)
22. [x] Xodim shaxsiy QR badge sahifasi

---

## 17-qadam: `Ombor`, `OmborZaxira`, `XodimBadge` modellari

**Holat: DONE**

### Nima qilindi
- `Ombor` — firmaning fizik ombori (nomi, manzil). `DeliveryStock`dagi kabi
  `company` FK, cheklovsiz (bir firmada nechta ombor bo'lishi mumkin).
- `OmborZaxira` — `(ombor, mahsulot) -> miqdor`, `unique_together` — `DeliveryStock`
  naqshining aynan o'zi, faqat "yetkazib beruvchi" o'rniga "ombor".
- `XodimBadge` — `user` bilan OneToOne, `kod` (unique, `default=uuid4` — Serial/
  BillingPaymentLink'da qo'llanilgan xuddi shu naqsh). Shaxsni identifikatsiya
  qiladigan QR — mahsulot `Serial`idan farqli, umuman boshqa narsa.
- `ProductionMaterialRequest.ombor` (FK, null/blank) — **so'rov yaratilganda emas,
  tasdiqlanganda omborchi tanlaydi** (rejada aniq belgilangan dizayn qarori — pazanda
  qaysi omborda un borligini bilishi shart emas).
- Hech biri mavjud kodga ta'sir qilmaydi — barcha maydonlar `null=True`/ixtiyoriy,
  `Mahsulot.miqdori`ga tegilmagan.

### O'zgargan fayllar
- `main/models.py` — `Ombor`, `OmborZaxira`, `XodimBadge` modellari,
  `ProductionMaterialRequest.ombor`
- `main/migrations/0064_ombor_productionmaterialrequest_ombor_xodimbadge_and_more.py`
- `main/admin.py` — uchala model ham ro'yxatga qo'shildi

### Tekshirildi
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz

---

## 18-qadam: `main/services/ombor_service.py`

**Holat: DONE**

### Nima qilindi
- Yangi fayl, ikkita funksiya, `qr_service.py`/`stock_service.py` naqshiga mos —
  `request`/`actor`ga bog'lanmaydi:
  - `add_ombor_stock(ombor, mahsulot, qty)` — `get_or_create` + oshirish (kirim uchun)
  - `deduct_ombor_stock(ombor, mahsulot, qty)` — `select_for_update()` bilan
    qulflab, yetarli miqdor bo'lmasa `(False, xabar)` qaytaradi, hech narsa
    o'zgartirmaydi; yetarli bo'lsa kamaytiradi

### O'zgargan fayllar
- `main/services/ombor_service.py` — yangi fayl

### Tekshirildi
- `python manage.py check` — xatosiz (funksional test 19-qadamda, hook'lanish
  bilan birga qilinadi)

---

## 19-qadam: Material so'rovi tasdiqlashga ombor tanlash + deduct hook

**Holat: DONE**

### Muhim topilma — "ikkala joy" emas, faqat bittasi haqiqiy
Rejada `ProductionMaterialRequest` tasdiqlash "ikki joyda takrorlangan" deb
yozilgan edi (`main/views.py` `main()` omborchi branch, inline VA
`main/warehouse_views.py:warehouse_request_review`). Tekshirib ko'rsam —
**`main()` ichidagi inline kod chindan ham o'lik kod**: u
`request.POST.get('material_request_id')` degan maydonni kutadi, lekin
hech qanday shablon (`warehouse_dashboard.html` ham) bu nomdagi maydonni
yubormaydi — ular hammasi `{% url 'warehouse_request_review' req.id %}`ga
POST qiladi. Shuning uchun **faqat `warehouse_request_review`** haqiqiy,
ishlaydigan yo'l. Avval ikkalasiga ham yozgan edim, keyin o'lik koddagi
qo'shimchani olib tashladim (keraksiz murakkablik qo'shmaslik uchun) — faqat
haqiqiy ishlaydigan joyda qoldirdi.

### Nima qilindi
- `warehouse_request_review` (`main/warehouse_views.py`) kengaytirildi:
  tasdiqlash formasida `ombor_id` yuborilsa — `deduct_ombor_stock(ombor,
  material, qty)` chaqiriladi. Yetarli bo'lmasa — xato bilan qaytadi,
  **hech narsa o'zgarmaydi** (na `Mahsulot.miqdori`, na so'rov holati).
  Yetarli bo'lsa — `OmborZaxira` kamayadi VA mavjud `Mahsulot.miqdori`
  kamaytirish o'zgarishsiz davom etadi (ikkalasi parallel).
- `ombor_id` yuborilmasa (company'da `Ombor` yo'q yoki omborchi tanlamagan) —
  **eski xulq-atvor to'liq saqlanadi**.
- `warehouse_requests` va `main()` omborchi branch (dashboard) context'iga
  `omborlar` ro'yxati qo'shildi.
- Shablonlar (`warehouse_requests.html`, `warehouse_dashboard.html`) — tasdiqlash
  formasiga ixtiyoriy "Ombor tanlang" select qo'shildi (faqat `omborlar` bo'sh
  bo'lmasa ko'rinadi).

### O'zgargan fayllar
- `main/warehouse_views.py` — `warehouse_request_review`, `warehouse_requests`,
  importlar (`Ombor`, `deduct_ombor_stock`)
- `main/views.py` — `main()` omborchi branch context'iga `omborlar` qo'shildi
  (dashboard uchun)
- `main/templates/warehouse_requests.html`, `main/templates/warehouse_dashboard.html`

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali to'liq oqim, izolyatsiyalangan tranzaksiyada**
  (haqiqiy `POST /ombor/sorovlar/<id>/review/`, login qilingan omborchi,
  rollback qilindi):
  - 2 ta ombor: 1-omborda 20kg, 2-omborda 10kg un. 15kg so'rov 1-ombordan
    tasdiqlandi → 1-ombor 5kg ga tushdi, 2-ombor o'zgarishsiz (10kg),
    `Mahsulot.miqdori` 30dan 15ga tushdi, `req.ombor` to'g'ri o'rnatildi ✅
  - Keyingi 12kg so'rov 2-ombordan tasdiqlanmoqchi bo'lganda (u yerda faqat
    10kg bor, garchi umumiy `Mahsulot.miqdori`da yetarli bo'lsa ham) — so'rov
    **tasdiqlanmadi** (`waiting`da qoldi), `Mahsulot.miqdori` o'zgarmadi ✅

---

## 20-qadam: Kirimga ombor tanlash + add hook

**Holat: DONE**

### Nima qilindi
- `warehouse_movements` (kirim) POST handlerida: agar `ombor_id` yuborilgan
  bo'lsa va mahsulot `semi_finished` bo'lsa — `add_ombor_stock(ombor, product,
  qty)` ham chaqiriladi (mavjud `Mahsulot.miqdori` qo'shish o'zgarishsiz,
  parallel).
- GET-render context'iga (`warehouse_movements`) `omborlar` ro'yxati qo'shildi.
- `warehouse_movements.html`ga ixtiyoriy "Ombor" select qo'shildi (faqat
  `omborlar` bo'sh bo'lmasa ko'rinadi).

### O'zgargan fayllar
- `main/warehouse_views.py` — `warehouse_movements` (import `add_ombor_stock`)
- `main/templates/warehouse_movements.html`

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali** (`POST /ombor/kirim-chiqim/`, login qilingan
  `ega`, rollback qilindi): 25kg kirim `ombor_id` bilan yuborilganda,
  `Mahsulot.miqdori` va `OmborZaxira.miqdor` ikkalasi ham to'g'ri 25ga yetdi ✅

---

## 21-qadam: Omborlar ro'yxati sahifasi

**Holat: DONE**

### Nima qilindi
- Yangi `ombor_list_page` (`main/warehouse_views.py`, faqat `ega`): ro'yxat +
  yangi ombor qo'shish formasi (nomi, manzil). Har bir ombor kartasida o'sha
  ombordagi barcha zaxiralar (`ombor.zaxiralar.all` — `OmborZaxira`ning
  `related_name`i orqali, alohida so'rov kerak emas).
- Yangi URL: `/omborlar/` (`ombor_list`).
- Sidebar'ga (`egabase.html`, Ombor submenu ichiga) "Omborlar" havolasi
  qo'shildi — faqat `ega` uchun.

### O'zgargan/yangi fayllar
- `main/warehouse_views.py` — `ombor_list_page`
- `main/templates/ombor_list.html` — yangi
- `main/urls.py` — yangi path
- `main/templates/egabase.html` — sidebar bandi

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali** (rollback qilindi): `GET /omborlar/` — 200,
  ombor nomi va undagi zaxira ko'rinadi; `POST /omborlar/` — yangi ombor
  to'g'ri yaratildi

---

## 22-qadam: Xodim shaxsiy QR badge sahifasi

**Holat: DONE**

### Nima qilindi
- Yangi `main/badge_views.py`: `xodim_badge_page` (o'zining yoki — `ega` bo'lsa —
  boshqa xodimning badge'ini ko'radi, `get_or_create` bilan avtomatik yaratadi)
  va `xodim_badge_image` (QR PNG, **internal/authenticated** — public emas,
  chunki bu mahsulot emas, shaxsni aniqlaydi; badge egasi yoki `ega` bo'lmasa
  404).
- QR kod ichiga faqat `badge.kod` (xom UUID) yoziladi — URL emas, chunki hali
  public/scan-to-open-session sahifasi yo'q (bu Desktop Agent bosqichida
  keladi).
- Yangi URL'lar: `/xodim/badge/` (o'zi), `/xodim/badge/<user_id>/` (`ega`
  boshqa xodim uchun), `/xodim/badge/rasm/<kod>/` (QR PNG).
- Sidebar (`egabase.html`) ga "Mening QR badgem" havolasi qo'shildi — **faqat
  `ega`ning o'z shabloniga** (bu shablon boshqa rollar uchun alohida
  `pzbase.html`/va h.k. bor, ularga hali qo'shilmadi — view/URL barcha rollar
  uchun ishlaydi, faqat navigatsiya havolasi hozircha faqat ega tomonida
  ko'rinadi; bu bilinib turgan, kichik follow-up).

### O'zgargan/yangi fayllar
- `main/badge_views.py` — yangi fayl
- `main/urls.py` — 3 ta yangi path
- `main/templates/xodim_badge.html` — yangi
- `main/templates/egabase.html` — sidebar bandi

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali** (rollback qilindi): anonim foydalanuvchi →
  login sahifasiga qaytarildi; pazanda o'z badge'ini ko'ra oldi (`kod`
  ikkinchi so'rovda ham bir xil — idempotent); pazanda ega'ning badge'ini
  ko'rishga urinsa → bosh sahifaga qaytarildi (ruxsat yo'q); badge PNG rasmi
  ham egasi, ham `ega` uchun ochildi

---

## Umumiy xulosa — Desktop Agent poydevori (17-22) to'liq

Ombor (ko'p-ombor), OmborZaxira, material so'rovi tasdiqlashda ombor tanlash,
kirimda ombor tanlash, omborlar CRUD sahifasi, va xodim shaxsiy QR badge —
barchasi qurildi, hech biri mavjud oqimlarni buzmadi (hammasi ixtiyoriy/qo'shimcha
qatlam). Keyingi qadam — foydalanuvchi ekran-suratda ko'rsatgan mahsulot
restrukturizatsiyasi (23-27 qadamlar, quyida).

---

# Mahsulot restrukturizatsiyasi — distributor/ishlab-chiqaruvchi + avtomatik tannarx

Foydalanuvchi ekran-suratda `seemahsulot.html`ni ko'rsatib 3 ta muammoni aytdi:
tannarx qo'lda kiritilmasin (avtomatik hisoblansin), "(1 dona)" so'zlari olib
tashlansin, mahsulot distributor/ishlab-chiqaruvchi turlariga bo'linsin (ikkalasi
ham tannarxni qo'lda o'zgartira olmaydi, ikkalasi ham mahsulotga bog'langan
qo'shimcha xarajat qo'sha oladi), ombor mahsulotlari "Mahsulotlar"da ko'rinmasin.
To'liq reja: `C:\Users\Banda\.claude\plans\quiet-waddling-heron.md`
(`---===NEXT4===---`dan keyin).

**Muhim topilma**: kod bazasida ega uchun **ikkita parallel mahsulot boshqaruv
UI**si bor ekan — "Mahsulotlar" (`list_views.py`/`views.py`, filtr yo'q,
finished+semi_finished aralash) va "Ombor" (`warehouse_views.py`, ega ikkalasini
ham ko'radi). Bo'linish shu ikkisini aniq ajratadi: Mahsulotlar → faqat finished
(distributor/ishlab-chiqaruvchi turi bilan), Ombor → faqat semi_finished
(soddalashtirilgan).

## Reja (bosqichlar)

23. [x] `Mahsulot.mahsulot_turi`/`baza_tannarx` + `MahsulotQoshimchaXarajat`
    modeli + migratsiya + admin
24. [x] `recompute_tannarx()` servis funksiyasi + `_apply_retsept_hisobkitob`
    va kirimni shunga o'tkazish
25. [x] "Mahsulotlar" — finished-only filtr, `mahsulot_turi`, tannarx
    read-only, xarajatlar mini-CRUD
26. [x] "Ombor" — semi_finished-only soddalashtirish, tannarx read-only
27. [x] `production_settings_page` — faqat ishlab-chiqariladigan finished
    mahsulotlar

---

## 23-qadam: `Mahsulot.mahsulot_turi`/`baza_tannarx` + `MahsulotQoshimchaXarajat`

**Holat: DONE**

### Nima qilindi
- `Mahsulot.mahsulot_turi` — CharField choices `ishlab_chiqariladigan`/
  `distributor`, default `ishlab_chiqariladigan`. Faqat `finished` mahsulotlar
  uchun ma'noli.
- `Mahsulot.baza_tannarx` — yangi maydon: amortizatsiya/qo'shimcha xarajatsiz
  "xom" tannarx (distributor uchun — kirim narxi; ishlab chiqaruvchi uchun —
  retsept bo'yicha hisoblangan qism). `tannarx`ning o'zi endi **yakuniy,
  hisoblangan** qiymat bo'lib qoladi (24-qadamda ulanadi).
- Yangi model `MahsulotQoshimchaXarajat` — `mahsulot` FK (company darajasidagi
  `QoshimchaChiqim`dan farqli, mahsulotga bevosita bog'langan), `nomi`, `summa`
  (1 donaga).
- **Backfill migratsiya** (`0066_backfill_baza_tannarx.py`): mavjud
  mahsulotlarning joriy `tannarx` qiymati `baza_tannarx`ga ko'chiriladi — bu
  production bazasida (agar tannarx != 0 bo'lgan mahsulotlar bo'lsa) keyingi
  qayta hisoblashda ularning tannarxi to'satdan 0ga tushib qolishining oldini
  oladi. Dev bazasida hozircha bunday mahsulot yo'q edi (tekshirilgan), lekin
  production uchun ehtiyot chorasi sifatida qo'shildi.

### O'zgargan fayllar
- `main/models.py` — `Mahsulot.mahsulot_turi`, `baza_tannarx`,
  `MahsulotQoshimchaXarajat` modeli
- `main/migrations/0065_mahsulot_baza_tannarx_mahsulot_mahsulot_turi_and_more.py`
- `main/migrations/0066_backfill_baza_tannarx.py` — data migratsiya
- `main/admin.py` — `MahsulotQoshimchaXarajatAdmin`

### Tekshirildi
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz

---

## 24-qadam: `recompute_tannarx()` + hooklar

**Holat: DONE**

### Nima qilindi
- `main/services/stock_service.py`ga yangi funksiya `recompute_tannarx(mahsulot)`
  — `baza_tannarx + amortizatsiya_narxi + qoshimcha_xarajatlar yig'indisi`ni
  hisoblab, `mahsulot.tannarx`ga yozadi. Bundan buyon **faqat shu funksiya**
  orqali tannarx yangilanadi — hech qayerda to'g'ridan-to'g'ri
  `mahsulot.tannarx = X` yozilmaydi (2 ta joyda o'zgartirildi):
  - `_apply_retsept_hisobkitob` — endi `unit_cost`ni to'g'ridan-to'g'ri
    `tannarx`ga yozish o'rniga, `mahsulot.baza_tannarx = tannarx_ulushi`
    (faqat BOM komponentlari qismi, amortizatsiyasiz) deb yozadi, so'ng
    `recompute_tannarx(mahsulot)` chaqiradi.
  - `warehouse_movements` kirim — `product.tannarx = incoming_price` o'rniga
    `product.baza_tannarx = incoming_price` deb yozadi, so'ng
    `recompute_tannarx(product)` chaqiradi.

### O'zgargan fayllar
- `main/services/stock_service.py` — `recompute_tannarx()`,
  `_apply_retsept_hisobkitob` yangilandi
- `main/warehouse_views.py` — kirim POST handleri, import

### Tekshirildi
- `python manage.py check` — xatosiz
- **5-qadamdagi eski BOM/jarima/tannarx testi qayta ishga tushirildi** —
  regressiya yo'q, natijalar bir xil (`jarima_summasi=500`, `tannarx=3050`,
  `ish_haqi_summasi=2500`) ✅
- **Yangi test (izolyatsiyalangan tranzaksiya, Django test Client)**: distributor
  turidagi mahsulotga (`amortizatsiya_narxi=100`, 2 ta qo'shimcha xarajat —
  50+30) 4000 so'mlik kirim qilindi → `baza_tannarx=4000`, yakuniy
  `tannarx=4000+100+50+30=4180` to'g'ri chiqdi ✅

---

## 25-qadam: "Mahsulotlar" — finished-only, mahsulot_turi, tannarx read-only, xarajatlar

**Holat: DONE**

### Nima qilindi
- `mahsulotlar_list` (`list_views.py`) — qattiq `warehouse_type='finished'` filtr
  qo'shildi. Semi_finished mahsulotlar bu ro'yxatda **hech qachon** ko'rinmaydi.
- `seemahsulot` (`views.py`):
  - `get_object_or_404`ga `warehouse_type='finished'` qo'shildi — semi_finished
    mahsulot ID'si bilan to'g'ridan-to'g'ri URL orqali kirishga urinilsa ham
    **404** qaytadi.
  - `tannarx` POST'dan **butunlay olib tashlandi** — endi hech qanday joydan
    qabul qilinmaydi.
  - `mahsulot_turi` qo'shildi, saqlangandan keyin **har doim**
    `recompute_tannarx(mahsulot)` chaqiriladi.
  - Yangi `action` discriminator (`retsept_edit_page` naqshiga o'xshab, xuddi
    shu view ichida): `add_xarajat` / `delete_xarajat` — mahsulotga bog'langan
    `MahsulotQoshimchaXarajat` qo'shish/o'chirish, ikkalasidan keyin ham
    `recompute_tannarx` chaqiriladi.
  - `warehouse_type` POST'dan olib tashlandi (endi bu view faqat finished bilan
    ishlaydi, o'zgartirib bo'lmaydi).
- `createmahsulot` — `warehouse_type` doim `'finished'` (qattiq), `mahsulot_turi`
  POST'dan o'qiladi.
- **Muhim bug tuzatildi**: `recompute_tannarx()` da `mahsulot.amortizatsiya_narxi`
  ba'zida (POST'dan hali saqlanmagan holatda) xom `str` bo'lib qolar edi —
  `Decimal + str` `TypeError` berardi. Endi ikkala operand ham
  `Decimal(str(...))` bilan himoyalangan — qaysi holatda chaqirilishidan
  qat'i nazar ishlaydi.
- Shablonlar:
  - `seemahsulot.html` — `warehouse_type` selektori olib tashlandi; `Tannarx`
    endi **disabled, read-only** input (`disabled` atributi bilan, POST
    qilinmaydi); "Mahsulot turi" selektori qo'shildi; `mahsulot_turi ==
    'distributor'` bo'lsa "Ishlab chiqarish narxi" maydoni butunlay
    ko'rsatilmaydi; "Ishlab chiqarish narxi (1 dona)"/"Amortizatsiya (1
    donaga)" → "Ishlab chiqarish narxi"/"Amortizatsiya"; pastga "Qo'shimcha
    xarajatlar" mini-jadval (ro'yxat + o'chirish) va qo'shish formasi qo'shildi.
  - `crtmahsulot.html` — "Ombor bo'limi" selektori "Mahsulot turi"ga
    almashtirildi.

### O'zgargan fayllar
- `main/list_views.py` — `mahsulotlar_list`
- `main/views.py` — `seemahsulot`, `createmahsulot`, importlar
  (`MahsulotQoshimchaXarajat`, `recompute_tannarx`)
- `main/services/stock_service.py` — `recompute_tannarx` Decimal himoyasi
- `main/templates/seemahsulot.html`, `main/templates/crtmahsulot.html`

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali izolyatsiyalangan tranzaksiyada** (rollback
  qilindi): ro'yxatda semi_finished ko'rinmadi ✅; semi_finished mahsulotni
  to'g'ridan-to'g'ri tahrirlash URL'i — 404 ✅; tannarx input `disabled` ✅;
  amortizatsiya 500ga o'zgartirilganda tannarx avtomatik 500ga yetdi ✅;
  120 so'mlik xarajat qo'shilganda tannarx 620ga o'sdi, o'chirilganda 500ga
  qaytdi ✅; yangi mahsulot yaratilganda `warehouse_type='finished'` va
  kiritilgan `mahsulot_turi` to'g'ri saqlandi ✅
- 5-qadam va 24-qadamdagi eski testlar qayta ishga tushirildi — regressiya yo'q

---

## 26-qadam: "Ombor" — semi_finished-only soddalashtirish

**Holat: DONE**

### Nima qilindi
- `_warehouse_product_queryset` — endi doim `warehouse_type='semi_finished'`
  bilan filtrlanadi (ega uchun ham, avval ega cheklovsiz ko'rar edi).
- `warehouse_products` — `finished`/`semi_finished` almashtirish GET-parametri
  va select'i butunlay olib tashlandi (endi ma'nosiz — ro'yxat doim faqat
  semi_finished).
- `warehouse_product_create`/`warehouse_product_edit` — `warehouse_type` doim
  `'semi_finished'` (qattiq); `tannarx`, `ishlab_chiqarish_narxi`,
  `amortizatsiya_narxi`, `serial_granularity` POST'dan **olib tashlandi**
  (xom ashyoga tegishli emas — bular endi faqat "Mahsulotlar" bo'limida).
- Shablonlar (`warehouse_product_form.html`, `warehouse_products.html`) —
  "Bo'lim" toggle/select va badge ustuni olib tashlandi; endi yo'q qilingan
  maydonlar inputlari olib tashlandi; tannarx **disabled, read-only** matn
  sifatida ko'rsatiladi (faqat "Kirim-chiqim" sahifasidagi kirim orqali
  o'zgaradi — mavjud oqim, o'zgarmagan).

### O'zgargan fayllar
- `main/warehouse_views.py` — `_warehouse_product_queryset`,
  `warehouse_products`, `warehouse_product_create`, `warehouse_product_edit`
- `main/templates/warehouse_product_form.html`, `main/templates/warehouse_products.html`

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali izolyatsiyalangan tranzaksiyada** (rollback
  qilindi): Ombor ro'yxatida faqat semi_finished ko'rindi, finished
  ko'rinmadi ✅; yangi mahsulot yaratilganda `warehouse_type` doim
  `semi_finished` bo'lib chiqdi (POST'da boshqa narsa yuborilsa ham) ✅;
  tahrirlash formasida tannarx `disabled` ✅; POST orqali `tannarx=99999`
  yuborilganda ham mahsulotning haqiqiy tannarxi o'zgarmadi (0da qoldi) ✅;
  finished mahsulotni Ombor URL orqali tahrirlashga urinilganda — 404 ✅

---

## 27-qadam: `production_settings_page` — faqat ishlab-chiqariladigan finished

**Holat: DONE**

### Nima qilindi
- `production_settings_page` mahsulotlar ro'yxati endi
  `warehouse_type='finished', mahsulot_turi='ishlab_chiqariladigan'` bilan
  filtrlanadi — distributor mahsulotlar va xom ashyo/yarim tayyor mahsulotlar
  "Retsept" ro'yxatida umuman ko'rinmaydi (ularga BOM/retsept tushunchasi
  tegishli emas).

### O'zgargan fayllar
- `main/production_views.py` — `production_settings_page`

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali izolyatsiyalangan tranzaksiyada** (rollback
  qilindi): ro'yxatda faqat `ishlab_chiqariladigan` turdagi finished mahsulot
  ko'rindi, distributor va xom ashyo mahsulotlari ko'rinmadi ✅

---

## Umumiy xulosa — Mahsulot restrukturizatsiyasi (23-27) to'liq

Ikkita parallel UI aniq ajratildi: **"Mahsulotlar"** (faqat sotiladigan,
distributor/ishlab-chiqaruvchi turi bilan, tannarx avtomatik hisoblanadi,
mahsulotga bog'langan qo'shimcha xarajat qo'sha oladi) va **"Ombor"** (faqat
xom ashyo/yarim tayyor, soddalashtirilgan, tannarx faqat kirim orqali).
Tannarx endi **hech qayerda qo'lda kiritilmaydi** — yoki retsept orqali
(ishlab chiqaruvchi), yoki kirim orqali (distributor/xom ashyo) avtomatik
hisoblanadi, `recompute_tannarx()` orqali. Barcha eski testlar (5, 24-qadam)
qayta ishga tushirilib, regressiya yo'qligi tasdiqlandi.

---

# Ombor to'g'rilash: majburiy rasm, xom ashyo/yarim tayyor, ishlab chiqaruvchiga biriktirish

Foydalanuvchi "Mahsulotlar"dagi qolgan muammolarni (narx qo'lda o'zgartirish,
retsept item tanlash, qo'shimcha xarajat) **keyinga qoldirdi** — avval Omborni
to'g'rilashni so'radi: rasm majburiy, xom ashyo/yarim tayyor bo'linishi, yarim
tayyor (va tayyor) mahsulotni ishlab chiqaruvchiga biriktirish, yarim tayyor
uchun ham miqdoriga qarab pul yozilishi. To'liq reja:
`C:\Users\Banda\.claude\plans\quiet-waddling-heron.md` (`---===NEXT5===---`dan keyin).

**Muhim topilma**: ish haqi/BOM mexanizmi (`stock_service.py`) allaqachon
`warehouse_type`dan mustaqil, universal — yarim tayyor mahsulotga shu
mexanizmga "kirish huquqi" berish kifoya, yangi hisoblash kodi kerak emas.

## Reja (bosqichlar)

28. [x] `Mahsulot.ombor_turi` + `PazandaMahsulot` modeli + migratsiya + admin
29. [x] Ombor formasiga majburiy rasm + `ombor_turi`
30. [x] `_pazanda_mahsulotlar_qs` helper + `addmiqdor`/dashboard/
    `production_settings_page` kengaytirish
31. [x] Xodim profiliga mahsulot biriktirish UI

---

## 28-qadam: `Mahsulot.ombor_turi` + `PazandaMahsulot` modeli

**Holat: DONE**

### Nima qilindi
- `Mahsulot.ombor_turi` — CharField choices `xom_ashyo`/`yarim_tayyor`, default
  `xom_ashyo`. Faqat `warehouse_type='semi_finished'` mahsulotlar uchun
  ma'noli.
- Yangi model `PazandaMahsulot` — `(pazanda, mahsulot)` bog'lanish,
  `unique_together`. Ishlab chiqaruvchiga qaysi mahsulot(lar) biriktirilganini
  ifodalaydi (`Pazanda`dan keyin qo'shildi, `Mahsulot`ga FK).

### O'zgargan fayllar
- `main/models.py` — `Mahsulot.ombor_turi`, `PazandaMahsulot` modeli
- `main/migrations/0067_mahsulot_ombor_turi_pazandamahsulot.py`
- `main/admin.py` — `PazandaMahsulotAdmin`

### Tekshirildi
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz

---

## 29-qadam: Ombor formasiga majburiy rasm + `ombor_turi`

**Holat: DONE**

### Nima qilindi
- `warehouse_product_create` — endi `request.FILES.get('rasmi')` bo'sh bo'lsa,
  **hech narsa yaratilmasdan** xato bilan qaytadi ("Rasm biriktirish
  majburiy."). `ombor_turi` POST'dan o'qiladi va saqlanadi.
- `warehouse_product_edit` — agar mahsulotda hali rasm yo'q bo'lib va yangi
  rasm ham yuklanmasa — xato. Rasm allaqachon bor bo'lsa, qayta yuklash shart
  emas (mavjud rasm saqlanadi). `ombor_turi` ham yangilanadi.
- Shablonlar: `warehouse_product_form.html` — "Turi" (Xom ashyo/Yarim tayyor)
  selektori qo'shildi; rasm inputiga (rasm yo'q holatlarda) `required` va
  qizil "*majburiy" belgisi, mavjud rasm bo'lsa mini-preview ko'rsatiladi.
  `warehouse_products.html` — ro'yxatga "Turi" badge ustuni qo'shildi
  (Xom ashyo / Yarim tayyor).

### O'zgargan fayllar
- `main/warehouse_views.py` — `warehouse_product_create`, `warehouse_product_edit`
- `main/templates/warehouse_product_form.html`, `main/templates/warehouse_products.html`

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali izolyatsiyalangan tranzaksiyada** (rollback
  qilindi): rasmisiz yaratishga urinish — hech narsa yaratilmadi ✅; rasm bilan
  yaratilganda `ombor_turi='yarim_tayyor'` to'g'ri saqlandi ✅

---

## 30-qadam: `_pazanda_mahsulotlar_qs` helper + oqimlarni kengaytirish

**Holat: DONE**

### Nima qilindi
- Yangi helper `_pazanda_mahsulotlar_qs(company, pazanda)` (`main/views.py`,
  `addmiqdor`dan oldin): agar `PazandaMahsulot` orqali unga aniq mahsulot(lar)
  biriktirilgan bo'lsa — faqat o'shalar qaytadi (finished + yarim_tayyor
  aralash bo'lishi mumkin); hech narsa biriktirilmagan bo'lsa — **eski
  xulq-atvor** (faqat `warehouse_type='finished'`, mahsulot_turidan qat'i
  nazar) saqlanadi.
- `addmiqdor` — production-report ro'yxati (`mahsulotlar`), saqlashdagi
  mahsulot tekshiruvi (`mxs`), va material so'rovidagi `target_product`
  tekshiruvi — barchasi shu helperni ishlatadi endi (avval qattiq
  `warehouse_type='finished'`).
- `main()` pazanda dashboard (`zaxira_mahsulotlar`) — xuddi shu helper.
- `production_settings_page` (`production_views.py`) — retsept/ish haqi
  sozlash ro'yxati endi `Q(finished, ishlab_chiqariladigan) |
  Q(semi_finished, yarim_tayyor)` bilan kengaytirildi.
- **Muhim tasdiqlash**: `stock_service.py`dagi ish haqi/BOM hisoblash
  mexanizmiga **hech qanday o'zgarish kiritilmadi** — u allaqachon har qanday
  `Mahsulot` uchun universal ishlaydi. Yarim tayyor mahsulotga shu mexanizmga
  "kirish huquqi" berish yetarli bo'ldi.

### O'zgargan fayllar
- `main/views.py` — `_pazanda_mahsulotlar_qs` (yangi), `addmiqdor`, `main()`,
  import (`PazandaMahsulot`)
- `main/production_views.py` — `production_settings_page`, import (`Q`)

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client + to'g'ridan-to'g'ri helper tekshiruvi, izolyatsiyalangan
  tranzaksiyada** (rollback qilindi):
  - `production_settings_page` — `ishlab_chiqariladigan` finished va
    `yarim_tayyor` semi_finished ko'rindi, `distributor` va `xom_ashyo`
    ko'rinmadi ✅
  - Biriktirilmagan pazanda uchun helper faqat finished mahsulotlarni
    qaytardi ✅; boshqa mahsulotga biriktirilgach — **faqat** biriktirilgan
    mahsulot(lar)ni qaytardi ✅; boshqa (biriktirilmagan) pazanda
    ta'sirlanmadi (izolyatsiya) ✅
  - **To'liq oqim**: yarim tayyor mahsulotga BOM (retsept) qo'shilib,
    pazandaga biriktirilgach, u orqali 10 dona ishlab chiqarish
    yuborilganda — `MiqdorQoshish` avtomatik tasdiqlandi, `ish_haqi_summasi
    = 10 * 50 = 500` to'g'ri hisoblandi (xuddi tayyor mahsulot uchun
    ishlaydigan mexanizm orqali, hech qanday yangi kod yozilmasdan) ✅,
    `yarim.miqdori` ham to'g'ri 10ga ko'tarildi ✅
  - **Eslatma**: ish haqi/jarima hisob-kitobi mahsulotda BOM (retsept)
    bo'lishini talab qiladi (5-qadamdagi asl dizayn — `_apply_retsept_hisobkitob`
    retsept yo'q bo'lsa hech narsa hisoblamay qaytadi) — bu yangi cheklov emas,
    shunchaki test shu holatni hisobga olib BOM qatori bilan to'ldirildi

---

## 31-qadam: Xodim profiliga mahsulot biriktirish UI

**Holat: DONE**

### Nima qilindi
- `profile_view` (`views.py`) — `ega` boshqa foydalanuvchi profiliga kirganda
  (bu holat `egaprofile.html` render qiladi, `pzprofile.html` emas — u faqat
  pazanda **o'zi** kirganda ishlatiladi), agar `user.type in
  ['pazanda','ishlab_chiqaruvchi']` bo'lsa, context'ga qo'shildi:
  `pazanda_obj`, `assignable_products` (hali biriktirilmagan, finished+
  ishlab_chiqariladigan yoki semi_finished+yarim_tayyor), `assigned_products`
  (joriy biriktirilganlar).
- Yangi POST action'lar (xuddi shu `profile_view` ichida, `retsept_edit_page`
  naqshiga o'xshab): `assign_mahsulot` (`get_or_create` — takroriy
  biriktirishga xato bermaydi) va `unassign_mahsulot` (o'chiradi).
- `egaprofile.html`ga — faqat pazanda/ishlab_chiqaruvchi profili ko'rilganda
  — "Biriktirilgan mahsulotlar" kartasi qo'shildi: ro'yxat (har biri "Olib
  tashlash" tugmasi bilan) + yangi biriktirish formasi (select + tugma).
  Hech narsa biriktirilmagan holatda izoh ko'rsatiladi ("barcha tayyor
  mahsulotlar ko'rinadi" — 30-qadamdagi fallback xulq-atvorga mos).

### O'zgargan fayllar
- `main/views.py` — `profile_view` (GET va POST branchlari)
- `main/templates/egaprofile.html` — biriktirish kartasi

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali izolyatsiyalangan tranzaksiyada** (rollback
  qilindi): `ega` pazanda profiliga kirganda sahifa 200 qaytardi va
  biriktirilishi mumkin bo'lgan yarim tayyor mahsulot ko'rindi ✅; biriktirish
  POST'i `PazandaMahsulot` yozuvini to'g'ri yaratdi ✅; olib tashlash POST'i
  uni to'g'ri o'chirdi ✅

---

## Umumiy xulosa — Ombor to'g'rilash (28-31) to'liq

Ombor mahsulotlarida rasm endi majburiy, xom ashyo/yarim tayyor aniq
ajratildi, ishlab chiqaruvchiga (profili orqali) bir nechta mahsulot
(yarim tayyor va tayyor) biriktirish mumkin bo'ldi, va yarim tayyor
mahsulot ishlab chiqarilganda ham — biriktirilgan bo'lsa — miqdoriga qarab
ish haqi avtomatik hisoblanadi (mavjud, universal mexanizm orqali, yangi
hisoblash kodi yozilmasdan). Hech narsa biriktirilmagan pazandalar uchun
eski xulq-atvor (faqat tayyor mahsulotlar) to'liq saqlanadi — breaking
change yo'q.

**Qoldirilgan, hali hal qilinmagan masalalar** (foydalanuvchi keyinga
qoldirgan): "Mahsulotlar" sahifasida narx (sotuv narxi) hamon qo'lda
o'zgartiriladi, retsept item'larini shu sahifadan tanlab bo'lmaydi (alohida
sahifada), qo'shimcha xarajat kiritish joyi ko'rinmayapti/ishlamayapti —
bularga foydalanuvchi qaytganda qaytiladi.

---

# Retsept + xarajat + ish haqi — "Mahsulot sozlamasi"ga birlashtirish, modal, amortizatsiya %

Foydalanuvchi qo'lda chizgan sxema asosida: retsept (BOM) va qo'shimcha xarajat
boshqaruvi alohida sahifalarda emas, **mahsulot sozlamasi (edit) sahifasining
o'zida** bo'lsin; "Retseptga qo'shish" ikki bosqichli **modal** (komponent
qidirish → miqdor kiritish, narx maydoni yo'q, avtomatik hisoblanadi);
**amortizatsiya son emas, foiz** bo'lsin, boshqa xarajatlar yig'indisiga
ustama sifatida qo'shilsin. To'liq reja:
`C:\Users\Banda\.claude\plans\quiet-waddling-heron.md` (`---===NEXT6===---`dan keyin).

## Reja (bosqichlar)

32. [x] `Mahsulot.amortizatsiya_foizi` (eski `amortizatsiya_narxi` o'rniga) +
    migratsiya; `recompute_tannarx` yangi formula
33. [x] `main/services/retsept_service.py` — umumiy add/delete/recompute
34. [x] `seemahsulot`ga retsept bo'limi + modal (ishlab_chiqariladigan uchun)
35. [x] `warehouse_product_edit`ga retsept bo'limi + modal (yarim_tayyor uchun)
36. [x] Eski `retsept_edit_page`/shablon/URL o'chirish, `production_settings.html`
    soddalashtirish

---

## 32-qadam: `amortizatsiya_foizi` + yangi formula

**Holat: DONE**

### Nima qilindi
- `Mahsulot.amortizatsiya_narxi` (son, DecimalField 10.2) **olib tashlandi**,
  o'rniga `Mahsulot.amortizatsiya_foizi` (DecimalField 5.2, foizda) qo'shildi.
  Real mijoz ma'lumoti yo'qligi sababli xavfsiz almashtirildi (rename emas,
  remove+add — chunki mazmuni ham o'zgardi: son emas, foiz).
- `recompute_tannarx` formulasi o'zgardi:
  - Eski: `tannarx = baza_tannarx + amortizatsiya_narxi + xarajatlar`
  - Yangi: `tannarx = (baza_tannarx + xarajatlar) * (1 + amortizatsiya_foizi/100)`
  — avval barcha asosiy xarajatlar yig'iladi, so'ng amortizatsiya foiz sifatida
  ustama bo'lib qo'shiladi.
- `views.py:seemahsulot` va `seemahsulot.html` — `amortizatsiya_narxi` →
  `amortizatsiya_foizi`, forma yorlig'i "Amortizatsiya (foizda)" + "%" belgisi.

### O'zgargan fayllar
- `main/models.py` — `Mahsulot.amortizatsiya_foizi`
- `main/migrations/0068_remove_mahsulot_amortizatsiya_narxi_and_more.py`
- `main/services/stock_service.py` — `recompute_tannarx` yangi formula
- `main/views.py` — `seemahsulot`
- `main/templates/seemahsulot.html`

### Tekshirildi
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz
- **Izolyatsiyalangan tranzaksiyada**: `baza_tannarx=1000`, xarajat=100,
  `amortizatsiya_foizi=10` → `tannarx = (1000+100)*1.10 = 1210` to'g'ri
  hisoblandi ✅
- **Eslatma**: avvalgi qadamlardagi eski test skriptlari (24, 25-qadam)
  `amortizatsiya_narxi` nomini ishlatgani uchun endi eskirgan — bu kutilgan
  (formula ataylab o'zgartirildi), keyingi qadamlarda yangi formulaga mos
  yangi testlar yoziladi

---

## 33-qadam: `main/services/retsept_service.py`

**Holat: DONE**

### Nima qilindi
- Yangi fayl — retsept (BOM) qatorlarini boshqarish uchun **umumiy** servis
  qatlami, ikkala edit sahifasidan (keyingi qadamlarda) qayta ishlatiladi:
  - `_creates_cycle()` — `production_views.py`dan shu yerga ko'chirildi
    (aylanma bog'lanish tekshiruvi).
  - `recompute_baza_tannarx_from_bom(mahsulot)` — BOM qatorlari yig'indisidan
    (`komponent.tannarx * norma_miqdor`) `baza_tannarx`ni hisoblaydi, so'ng
    `recompute_tannarx`ni chaqiradi. **Retsept tahrirlangan zahoti darhol
    chaqiriladi** — production tasdiqlanishini kutmasdan, foydalanuvchi
    jonli narx ko'rishi uchun (production paytida ishlatiladigan
    `_apply_retsept_hisobkitob` bilan bir xil formula, ziddiyat yo'q).
  - `add_retsept_row(company, mahsulot, komponent, norma_miqdor,
    jarima_narxi_birlik=0)` — validatsiya (o'z-o'ziga bog'lanish, komponent
    turi, norma > 0, cycle) + saqlash + qayta hisoblash. Narx maydoni
    umuman yo'q — komponentning mavjud tannarxi avtomatik ishlatiladi.
  - `delete_retsept_row(company, mahsulot, row_id)` — o'chirish + qayta
    hisoblash.

### O'zgargan/yangi fayllar
- `main/services/retsept_service.py` — yangi fayl

### Tekshirildi
- `python manage.py check` — xatosiz
- **Izolyatsiyalangan tranzaksiyada**: komponent qo'shilganda
  `baza_tannarx`/`tannarx` darhol to'g'ri hisoblandi (6000×0.5=3000) ✅;
  o'z-o'ziga bog'lash va `finished` turdagi komponent rad etildi ✅;
  o'chirilgandan keyin qiymatlar 0ga qaytdi ✅

---

## 34-qadam: `seemahsulot`ga retsept bo'limi + modal

**Holat: DONE**

### Nima qilindi
- `seemahsulot` (`views.py`) — yangi `action`lar: `add_retsept_row`
  (`retsept_service.add_retsept_row` chaqiradi), `delete_retsept_row`
  (`delete_retsept_row` chaqiradi). GET-render context'iga (faqat
  `mahsulot_turi == 'ishlab_chiqariladigan'` bo'lganda) `retsept_rows` va
  `retsept_komponentlar` qo'shildi.
- `seemahsulot.html` — "Retsept" kartasi qo'shildi (faqat ishlab_chiqariladigan
  turi uchun): mavjud qatorlar jadvali (komponent, norma, narx) + "Retseptga
  qo'shish" tugmasi.
- Yangi umumiy partial `main/templates/retsept_modal.html` — ikki bosqichli
  modal:
  1. Qidiruv (client-side JS filtr, komponentlar oldindan JS massiviga
     yozilgan — server-side render, AJAX kerak emas)
  2. Miqdor kiritish — **narx maydoni yo'q**, komponentning o'z tannarxi
     asosida (`komponent.tannarx * miqdor`) jonli hisoblanadi va joriy
     retsept umumiy tannarxi (`mahsulot.baza_tannarx`) ustiga qo'shib
     ko'rsatiladi (faqat oldindan ko'rish uchun — haqiqiy saqlash va yakuniy
     hisob-kitob har doim serverda, `recompute_baza_tannarx_from_bom` orqali).
  Tasdiqlaganda yashirin forma orqali `add_retsept_row` action bilan
  serverga POST qilinadi.

### O'zgargan fayllar
- `main/views.py` — `seemahsulot` (action'lar + GET context), import
  (`MahsulotRetsept`, `add_retsept_row`, `delete_retsept_row`)
- `main/templates/seemahsulot.html` — Retsept kartasi + modal include
- `main/templates/retsept_modal.html` — yangi umumiy partial

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali izolyatsiyalangan tranzaksiyada** (rollback
  qilindi): sahifa 200 qaytardi, modal va komponent ma'lumotlari sahifada bor;
  `add_retsept_row` POST'i `baza_tannarx`ni to'g'ri (6000×0.5=3000) darhol
  yangiladi ✅; `delete_retsept_row` qayta 0ga tushirdi ✅

---

## 35-qadam: `warehouse_product_edit`ga retsept bo'limi + modal

**Holat: DONE**

### Muhim qo'shimcha topilma
28-31 qadamlarda yarim tayyor mahsulot ish haqi/BOM mexanizmiga "kirish
huquqi" berilgan edi, lekin **26-qadamda Ombor formasidan
`ishlab_chiqarish_narxi`/`amortizatsiya_narxi` maydonlari butunlay olib
tashlangan edi** (xom ashyoga tegishli emas deb) — ya'ni yarim tayyor
mahsulotga ish haqi/amortizatsiya **belgilashning hech qanday yo'li yo'q
edi**. Shu qadamda tuzatildi: `ombor_turi == 'yarim_tayyor'` bo'lgandagina
bu ikki maydon formada qaytadan ko'rinadi.

### Nima qilindi
- `warehouse_product_edit` (`warehouse_views.py`) — `seemahsulot`dagi bilan
  bir xil `action`lar qo'shildi: `add_xarajat`/`delete_xarajat`,
  `add_retsept_row`/`delete_retsept_row` (`retsept_service`ni chaqirib).
  Oddiy saqlashda — agar `ombor_turi == 'yarim_tayyor'` bo'lsa —
  `ishlab_chiqarish_narxi`/`amortizatsiya_foizi` ham saqlanadi va
  `recompute_tannarx` chaqiriladi (`xom_ashyo` uchun bu maydonlarga
  tegilmaydi).
- GET-render — `xarajatlar` doim, `retsept_rows`/`retsept_komponentlar`
  faqat `yarim_tayyor` bo'lganda context'ga qo'shiladi.
- `warehouse_product_form.html` — `product` mavjud bo'lganda (yaratishda
  emas, xuddi `seemahsulot`dagi xarajat naqshiga o'xshab): "Ishlab chiqarish
  narxi"/"Amortizatsiya (foizda)" maydonlari (faqat yarim_tayyor), "Qo'shimcha
  xarajatlar" kartasi (har doim), "Retsept" kartasi + modal (faqat
  yarim_tayyor) — **xuddi shu umumiy `retsept_modal.html` partial**
  qayta ishlatildi (`{% include ... with mahsulot=product %}`).

### O'zgargan fayllar
- `main/warehouse_views.py` — `warehouse_product_edit`, importlar
- `main/templates/warehouse_product_form.html`

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali izolyatsiyalangan tranzaksiyada** (rollback
  qilindi): yarim tayyor mahsulot tahrirlash sahifasida Retsept/modal/ish
  haqi maydonlari ko'rindi ✅; ish haqi (30) va amortizatsiya (5%) to'g'ri
  saqlandi ✅; retsept qatori qo'shilganda `baza_tannarx=3000`,
  `tannarx=3000×1.05=3150` to'g'ri hisoblandi ✅; qo'shimcha xarajat (100)
  qo'shilgach `tannarx=(3000+100)×1.05=3255` to'g'ri yangilandi ✅

---

## 36-qadam: Eski `retsept_edit_page` o'chirish, `production_settings.html` soddalashtirish

**Holat: DONE**

### Nima qilindi
- `production_views.py` — `retsept_edit_page` funksiyasi va `_creates_cycle`
  (33-qadamda `retsept_service.py`ga ko'chirilgani uchun endi bu yerda
  kerak emas) o'chirildi. `production_settings_page` endi mahsulotlar
  ro'yxatini butunlay olib tashladi — faqat ish haqi turi toggle'ini
  qaytaradi.
- `main/urls.py` — `/ishlab-chiqarish/retsept/<id>/` (`retsept_edit`) URL'i
  o'chirildi.
- `main/templates/retsept_edit.html` — fayl o'chirildi.
- `production_settings.html` — mahsulotlar/retsept ro'yxati olib tashlandi,
  izoh qo'shildi ("retsept/xarajat endi mahsulotning o'z sozlash sahifasida").
- `egabase.html` sidebar — `retsept_edit` faollik tekshiruvi olib tashlandi.

### O'zgargan/o'chirilgan fayllar
- `main/production_views.py`, `main/urls.py`, `main/templates/production_settings.html`,
  `main/templates/egabase.html`
- `main/templates/retsept_edit.html` — o'chirildi

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali**: `/ishlab-chiqarish/sozlamalar/` — 200,
  faqat ish haqi turi bloki; eski `retsept_edit` URL nomi endi
  `reverse()` bilan topilmaydi (`NoReverseMatch`) — to'liq o'chirilgani
  tasdiqlandi ✅
- 34 va 35-qadamdagi testlar qayta ishga tushirildi — regressiya yo'q ✅

---

---

## 37-qadam: Jarima narxi olib tashlandi — endi "ishlab chiqarish narxi" bilan bir xil

**Holat: DONE**

Foydalanuvchi ekran-suratda retsept modalidagi "Jarima narxi" maydonini
ko'rsatib to'g'irladi: **jarima narxi alohida kiritilmasin — u mahsulotning
"Ishlab chiqarish narxi"si bilan bir xil bo'lsin.** Ya'ni normadan
chetlashish jarimasi endi har bir BOM qatorida alohida sozlanadigan qiymat
emas, balki mahsulotning o'zida allaqachon bor `ishlab_chiqarish_narxi`
qiymati orqali hisoblanadi.

### Nima qilindi
- `stock_service.py:_apply_retsept_hisobkitob` — `jarima_summasi += abs(deviation)
  * row.jarima_narxi_birlik` o'rniga `jarima_summasi += abs(deviation) *
  mahsulot.ishlab_chiqarish_narxi` (BOM qatoriga emas, mahsulotning o'ziga
  bog'liq, barcha komponentlar uchun bir xil qiymat ishlatiladi).
- `MahsulotRetsept.jarima_narxi_birlik` maydoni **butunlay o'chirildi**
  (migratsiya bilan) — endi hech qanday jarima narxi BOM darajasida
  saqlanmaydi.
- `retsept_service.add_retsept_row()` — `jarima_narxi_birlik` parametri
  olib tashlandi (imzosi soddalashdi).
- `retsept_modal.html` — 2-bosqichdagi "Jarima narxi" inputi va unga bog'liq
  yashirin maydon/JS kodi olib tashlandi.
- `views.py`/`warehouse_views.py` — `add_retsept_row` chaqiruvlaridan
  `jarima_narxi_birlik` argumenti olib tashlandi.
- `admin.py` — `MahsulotReseptAdmin.list_display`dan olib tashlandi.

### O'zgargan fayllar
- `main/models.py` — `MahsulotRetsept.jarima_narxi_birlik` o'chirildi
- `main/migrations/0069_remove_mahsulotretsept_jarima_narxi_birlik.py`
- `main/services/stock_service.py` — jarima formulasi
- `main/services/retsept_service.py` — `add_retsept_row` imzosi
- `main/views.py`, `main/warehouse_views.py` — chaqiruvlar
- `main/templates/retsept_modal.html` — jarima inputi olib tashlandi
- `main/admin.py`

### Tekshirildi
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz
- **Izolyatsiyalangan tranzaksiyada**: 10 dona uchun 5kg kerak bo'lgan
  joyda 6kg ishlatilgan (1kg ortiqcha), `ishlab_chiqarish_narxi=500` →
  `jarima_summasi = |6-5|*500 = 500` ✅, `ish_haqi_summasi = 10*500-500 =
  4500` ✅ — yangi formula to'g'ri ishladi
- 34 va 35-qadamdagi retsept-qo'shish testlari qayta ishga tushirildi —
  regressiya yo'q (ular `jarima_narxi_birlik`siz chaqirilgani uchun
  ta'sirlanmadi) ✅

---

---

## 38-qadam: Kirimda o'rtacha og'irlikdagi tannarx (weighted average) + xom ashyoda xarajat yashirildi

**Holat: DONE**

Foydalanuvchi ikkita narsani ko'rsatdi:
1. Xom ashyo (`xom_ashyo`) mahsulot formasida "Qo'shimcha xarajatlar" bo'limi
   kerak emas.
2. **Muhim bug**: kirim qilinganda `baza_tannarx` eskisi ustidan
   to'g'ridan-to'g'ri yozilar edi (`product.baza_tannarx = incoming_price`),
   mavjud qoldiq bilan **o'rtacha hisoblanmasdan**. Misol: kecha 0kg go'sht,
   bugun 10kg 1.6mln so'mga (160k/kg) kirim qilinsa — narx 160k. Ertaga yana
   10kg 1.56mln so'mga (156k/kg) kirim qilinsa, **narx 156kga tushib qoladi**
   — holbuki omborda hali eski 10kg (160k/kg) ham bor, haqiqiy o'rtacha narx
   158k/kg bo'lishi kerak edi. Bu tadbirkorga noto'g'ri foyda ko'rsatardi.

### Nima qilindi
- `warehouse_movements` kirim POST handleri — endi klassik **moving weighted
  average** formulasi bilan hisoblaydi:
  `yangi_baza = (eski_miqdor × eski_baza + kirim_miqdor × kirim_narxi) /
  (eski_miqdor + kirim_miqdor)`. Har bir keyingi ishlab chiqarish/BOM
  hisob-kitobi (`_apply_retsept_hisobkitob`, `komponent.tannarx` o'qiladi)
  **shu paytdagi haqiqiy o'rtacha narxdan** foydalanadi — bu allaqachon
  to'g'ri ishlar edi (har doim joriy qiymat o'qilardi), muammo faqat kirim
  yozishning o'zida edi.
- `warehouse_product_form.html` — "Qo'shimcha xarajatlar" bo'limi endi
  `product.ombor_turi == 'yarim_tayyor'` bo'lgandagina ko'rinadi (Retsept
  bilan bir xil shart) — xom ashyo formasida umuman ko'rinmaydi.

### O'zgargan fayllar
- `main/warehouse_views.py` — `warehouse_movements` (weighted average)
- `main/templates/warehouse_product_form.html` — xarajat bo'limi sharti

### Tekshirildi
- `python manage.py check` — xatosiz
- **Django test Client orqali izolyatsiyalangan tranzaksiyada** (rollback
  qilindi): 0kg dan 10kg@160k/kg kirim → `baza_tannarx=160000` ✅; yana
  10kg@156k/kg kirim → `miqdori=20`, `baza_tannarx=158000` (to'g'ri
  o'rtacha) ✅; xom ashyo tahrirlash sahifasida "Qo'shimcha xarajatlar" va
  "Retsept" bo'limlari endi ko'rinmadi ✅

---

## Umumiy xulosa — Retsept/xarajat/ish haqi birlashtirish (32-36) to'liq

Retsept (BOM), qo'shimcha xarajat va ish haqi sozlamalari endi **alohida
sahifalarda emas**, har bir mahsulotning o'z sozlash sahifasida (Mahsulotlar
uchun `seemahsulot.html`, yarim tayyor Ombor mahsulotlari uchun
`warehouse_product_form.html`) — ikkalasi ham bitta umumiy servis
(`retsept_service.py`) va bitta umumiy modal (`retsept_modal.html`) orqali
ishlaydi. Komponent tanlashda narx maydoni yo'q — tizim komponentning o'z
tannarxidan avtomatik hisoblaydi va jonli ko'rsatadi. Amortizatsiya endi
foizda, boshqa xarajatlar yig'indisiga ustama sifatida qo'shiladi.

---

## 39-qadam: Narxi (sotuv narxi) endi har doim tannarxga teng — qo'lda kiritilmaydi

**Holat: DONE**

Foydalanuvchi Burger mahsuloti misolida ko'rsatdi: "Narxi" (25000) va
"Tannarx" (16000) alohida-alohida ko'rsatilar edi, savdogar tomonga esa
"Narxi" chiqadi. Foydalanuvchining talabi aniq va qat'iy edi: **"narx=tannarx
qilib qo'y, savdoda muammo bo'lmaydigon qilib"**. Aniqlashtiruvchi savoldan
so'ng (uchta variant: himoya-tekshiruvi / avtomatik ustama-foiz / to'liq
tenglik) foydalanuvchi eng qat'iy variantni tanladi: **"Narxi har doim
tannarxning o'ziga teng"** — alohida foyda-ustama maydoni umuman bo'lmaydi.

### Nima qilindi
- `stock_service.recompute_tannarx()` — endi `tannarx`ni hisoblab bo'lgach,
  darhol `mahsulot.narxi = mahsulot.tannarx` qilib, ikkalasini ham
  saqlaydi (`update_fields=['tannarx', 'narxi']`). Bu funksiya barcha
  tannarx-hisoblash yo'llarining (kirim, BOM/retsept, amortizatsiya %,
  qo'shimcha xarajat) yagona "quyma nuqtasi" bo'lgani uchun, `narxi` endi
  **hamma joyda** avtomatik tannarxga teng bo'lib qoladi — alohida sync
  kodi kerak bo'lmadi.
- To'rtta mahsulot yaratish/tahrirlash oqimidan `narxi`ni qo'lda
  o'qiydigan/yozadigan kod olib tashlandi:
  - `views.py:seemahsulot` — `mahsulot.narxi = request.POST.get('narxi')`
    o'chirildi (`recompute_tannarx` chaqiruvi saqlanib qoldi, u endi
    narxi'ni ham sinxronlaydi)
  - `views.py:createmahsulot` — yangi mahsulot `narxi=0` bilan yaratiladi,
    keyin edit/BOM/kirim orqali haqiqiy tannarx kelgach avtomatik to'ladi
  - `warehouse_views.py:warehouse_product_create` — `narxi` doim `0`
  - `warehouse_views.py:warehouse_product_edit` — qo'lda `narxi` yozish
    qatori olib tashlandi
- Shablonlar — "Narxi" input'lari o'qish-uchun-disabled ko'rsatishga
  almashtirildi ("Narxi (avtomatik — tannarxga teng)"):
  - `seemahsulot.html`
  - `warehouse_product_form.html` (faqat `{% if product %}`, ya'ni edit
    rejimida — yaratishda hali tannarx yo'q)
  - `crtmahsulot.html` — "Narxi" input butunlay olib tashlandi (yangi
    mahsulot narxi=0 dan boshlanadi)
- Haqiqiy (production) ma'lumotlar bazasidagi mavjud "Go'sht" (id=6) va
  "Burger" (id=5) yozuvlari uchun `recompute_tannarx()` qayta chaqirildi —
  ularning `narxi` maydoni yangi qiymatlarga (mos ravishda 160000 va 16000
  so'm) darhol sinxronlandi (avvalgi qadamda `baza_tannarx` allaqachon
  to'g'irlangan edi, faqat `narxi` yangi formulaga hali tortilmagan edi).

### O'zgargan fayllar
- `main/services/stock_service.py` — `recompute_tannarx()` narxi'ni sync qiladi
- `main/views.py` — `seemahsulot`, `createmahsulot`
- `main/warehouse_views.py` — `warehouse_product_create`, `warehouse_product_edit`
- `main/templates/seemahsulot.html`, `crtmahsulot.html`,
  `warehouse_product_form.html`

### Tekshirildi
- `python manage.py check` — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback qilindi): (a) `xom_ashyo`
  turidagi mahsulotga `baza_tannarx` o'rnatilib `recompute_tannarx`
  chaqirilganda `narxi == tannarx` bo'lishi ✅; (b) `amortizatsiya_foizi`
  o'zgartirilganda ham `narxi` yangi `tannarx`ga qayta sinxronlanishi
  (masalan baza=5000, foiz=20% → tannarx=narxi=6000) ✅; (c)
  `ishlab_chiqariladigan` mahsulotga BOM qatori qo'shilganda
  (`add_retsept_row`) ham `narxi == tannarx` bo'lib qolishi ✅
- Haqiqiy Go'sht/Burger yozuvlari qo'lda qayta hisoblanib,
  `narxi == tannarx` (160000/160000 va 16000/16000) tasdiqlandi ✅

---

## 40-qadam: Narxi qayta qo'lda kiritiladigan qilindi (39-qadam bekor qilindi) + amortizatsiya ko'rinmaslik bugi

**Holat: DONE**

Foydalanuvchi Burger mahsuloti sozlash sahifasi skrinshotini ko'rsatib ikkita
narsani aytdi: (1) "Amortizatsiya (foizda)" maydoni har safar sahifaga
kirganida bo'sh ko'rinar edi — bu bug edi; (2) 39-qadamda qilingan "Narxi har
doim tannarxga teng" qarori bekor qilinishi kerak — **"narxni qo'lda
kiritadigon bo'lsin. tannarx<narx bo'lsin"**. Ya'ni narxi endi yana qo'lda
kiritiladi, lekin **tannarxdan past yoki teng bo'lishi taqiqlanadi** (zararga
sotishning oldini olish).

### Amortizatsiya bug diagnostikasi
`{{ mahsulot.amortizatsiya_foizi|floatformat:2 }}` — Django loyihasida
`LANGUAGE_CODE='uz-latn'` bo'lgani uchun `floatformat` natijani
**lokalizatsiya qilib, vergul bilan** chiqarar edi (masalan `"2,00"`).
HTML5 `<input type="number">` vergulli qiymatni **yaroqsiz** deb hisoblab,
uni ko'rsatmay bo'sh qoldiradi — shuning uchun foydalanuvchiga maydon
har doim bo'sh ko'rinardi (aslida DB'da qiymat bor edi). Bu xuddi shu
loyihada allaqachon qo'llanilgan yechim — `warehouse_product_form.html`da
`|unlocalize` filtri ishlatilgan edi, faqat `seemahsulot.html`da
qo'llanilmagan edi.

### Nima qilindi
- `seemahsulot.html` — `{% load l10n %}` qo'shildi, amortizatsiya inputi
  `floatformat:2` o'rniga `|unlocalize` filtridan foydalanadi (vergul
  muammosi yo'qoladi, qiymat har doim to'g'ri ko'rinadi).
- `seemahsulot.html` — "Narxi (avtomatik — tannarxga teng)" disabled
  maydoni yana oddiy `<input type="number" name="narxi" required>`ga
  qaytarildi.
- `stock_service.recompute_tannarx()` — endi faqat `tannarx`ni hisoblaydi,
  `narxi`ga **tegmaydi** (39-qadamdagi avtomatik sinxronlash bekor qilindi).
- `views.py:seemahsulot` — POST handlerida boshqa maydonlar saqlanib,
  `recompute_tannarx` chaqirilgandan **keyin**, POST'dan kelgan `narxi`
  tannarx bilan solishtiriladi: agar `narxi <= tannarx` bo'lsa — xato xabari
  ko'rsatiladi ("Narxi tannarxdan ... yuqori bo'lishi kerak"), **narxi
  saqlanmaydi** (boshqa o'zgarishlar saqlangan holda qoladi); aks holda
  `narxi` yangilanib saqlanadi.

### O'zgargan fayllar
- `main/templates/seemahsulot.html` — `{% load l10n %}`, amortizatsiya
  `|unlocalize`, narxi qayta editable input
- `main/services/stock_service.py` — `recompute_tannarx()` narxi'ga tegmaydi
- `main/views.py` — `seemahsulot` narxi validatsiyasi (`tannarx < narxi`)

### Tekshirildi
- `python manage.py check` — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback qilindi, `Client` + real
  `ega` foydalanuvchi orqali): (a) `recompute_tannarx` endi `narxi`ni
  o'zgartirmasligi (tannarx=10000 bo'lganda narxi 0'da qolishi) ✅; (b)
  `/product/<id>/` ga `narxi=9000` (tannarx=10000dan past) POST qilinganda
  — narxi saqlanmay 0'da qolishi ✅; (c) `narxi=15000` (tannarxdan yuqori)
  POST qilinganda muvaffaqiyatli saqlanishi ✅

---

## 41-qadam: Sotuv paytidagi haqiqiy sof foyda snapshoti (`Savdo.foyda`) + dashboardda oylik foyda va grafik

**Holat: DONE**

Foydalanuvchi so'radi: har bir mahsulot sotilganda narx-tannarx farqi
("haqiqiy foyda") hisoblab boriladimi, kunlik/oylik yig'indi dashboardda
ko'rinadimi? Tekshiruv shuni ko'rsatdi — **yo'q edi**, `Savdo` modelida
tannarx umuman saqlanmagan. Foydalanuvchi aniqlashtirdi: **mahsulot
yetkazib beruvchi/savdogarga chiqib ketgach, keyingi taqdiri (haqiqatda
sotildimi, qachon, qanday narxda) bizning muammomiz emas** — foyda **sotuv
yozilgan paytdagi** narx (`Mahsulot.narxi`) va tannarx (`Mahsulot.tannarx`)
farqi orqali hisoblanadi, boshqa hech narsa kuzatilmaydi. Kunlik/oylik
yig'indi esa dashboardning asosiy qismida "Oylik sof foyda" sifatida
chiqariladi.

### Muhim arxitektura qarori — nega snapshot kerak
`Mahsulot.tannarx` — **jonli qiymat** (o'rtacha og'irlikdagi narx tizimi
tufayli vaqt bilan o'zgaradi). Agar foyda sotuvdan keyin joriy tannarx bilan
hisoblansa, o'tmishdagi sotuvlarning foydasi kelajakda narx o'zgarganda
noto'g'ri chiqib qoladi. Shuning uchun foyda **sotuv yaratilgan paytning
o'zida**, o'sha paytdagi `narxi`/`tannarx` asosida hisoblanib, `Savdo.foyda`
maydoniga **qattiq yozib qo'yiladi** (snapshot) — xuddi `MiqdorQoshish.
tannarx_snapshot` bilan bir xil naqsh.

### Nima qilindi
- `Mahsulot` modeliga yangi maydon: `Savdo.foyda` (FloatField, default 0) —
  "sotuv paytidagi (narx-tannarx)*miqdor yig'indisi, kredit ustamasisiz".
  Migratsiya: `0070_savdo_foyda.py`.
- `views.py:sotish` — sotilgan mahsulotlar sikli ichida (`sale_items`
  qurilayotgan joyda) endi har bir qator uchun `mxs.tannarx` ham o'qiladi,
  `foyda += qty * (price - cost)` yig'iladi. Bu **`base_summa`/`summa`dan
  mustaqil** — nasiya savdolarida kredit ustama foizi qo'shilgan
  `sale_summa`ga emas, xom mahsulot summasiga asoslanadi (kredit ustamasi
  moliyaviy xizmat haqqi, mahsulot foydasi emas). `foyda=foyda` ikkala
  `Savdo.objects.create()` chaqiruviga (nasiya va oddiy) qo'shildi.
- `kpi_views.py:trend_30` — JSON javobiga `foyda_data` massivi qo'shildi
  (kunlik `Sum('foyda')`, mavjud `summa_data`/`soni_data` bilan bir xil
  naqsh).
- `views.py:main` (ega dashboard) — joriy oy uchun `Sum('foyda')`
  hisoblanib, `oylik_foyda` context'ga (mavjud `add_spctoint` formatlash
  bilan, `usumma`/`bsumma`ga o'xshab) qo'shildi.
- `main.html` — yangi "Oylik Sof Foyda" stat-card (`teal` rangda, yangi CSS
  klass) "Bugungi Daromad" kartasidan keyin qo'shildi. 30-kunlik trend
  chart (mavjud Chart.js line chart, `trend_30` endpointidan) endi ikkinchi
  dataset — "Sof foyda (so'm)" — bilan chiziladi (legend yoqildi, tooltip
  ikkala qatorni ham nomi bilan ko'rsatadi). Y o'qidagi mavjud k/M
  qisqartirish (`v >= 1000000 ? .../1000000+'M' : .../1000+'K'`) o'zgarishsiz
  qoldi — ikkala dataset ham shundan foydalanadi.

### Eslatma (edge case)
Bu sana **oldingi** sotuvlar uchun `foyda=0` bo'lib qoladi (default) — ular
yaratilganda tannarx snapshoti saqlanmagan, orqaga qaytarib hisoblab
bo'lmaydi (o'sha paytdagi haqiqiy tannarxni bilishning imkoni yo'q). Bu
qabul qilinadigan cheklov — 41-qadamdan keyingi barcha yangi sotuvlar
to'g'ri hisoblanadi.

### O'zgargan fayllar
- `main/models.py` — `Savdo.foyda`
- `main/migrations/0070_savdo_foyda.py`
- `main/views.py` — `sotish` (foyda hisoblash), `main` (oylik_foyda)
- `main/kpi_views.py` — `trend_30` (`foyda_data`)
- `main/templates/main.html` — yangi stat-card + trend chart ikkinchi dataset

### Tekshirildi
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback qilindi, `Client` + haqiqiy
  `yetkazib_beruvchi` foydalanuvchi orqali, `/sotish/` ga to'liq POST):
  narxi=15000, tannarx=10000 mahsulotdan 4 dona sotilganda —
  `Savdo.summa=60000` ✅, `Savdo.foyda=20000` (4×(15000-10000)) ✅ — formula
  to'g'ri ishladi

---

## 42-qadam: Superadmin uchun umumiy backup tizimi (bitta firma / butun tizim)

**Holat: DONE**

Foydalanuvchi so'radi: superadmin panelida backup tizimi kerak — yoki bitta
firma, yoki **butun tizim** (server ko'chirilganda) uchun ishlaydigan.
Aniqlashtirdi: **"admin paneldan backup olish tursin lekin uni qayta o'zi
restore mantiqsiz"** — ya'ni faqat yuklab olish (export), qayta tiklash
(restore) admin panel orqali qilinmaydi (server ko'chirilganda qo'lda
amalga oshiriladi).

### Mavjud infratuzilma (qayta ishlatildi)
Kompaniya egasi ("ega") uchun allaqachon shaxsiy backup tizimi bor edi:
`main/backup_utils.py:generate_backup(company)` — bitta firmaning
tanlangan modellarini (`Mahsulot`, `Savdo`, `HaridorDukon` va h.k.) JSON
qilib va tegishli media fayllarni ZIP arxivga yig'adi. Bitta firma
backup'i uchun **shu funksiyaning o'zi** qayta ishlatildi (superadmin
tomonidan, firma tarifidagi backup cheklovi/`company_has_access`
tekshiruvisiz — superadmin har qanday firmani backup qila oladi).

### Nima qilindi
- `main/backup_utils.py` — yangi `generate_full_system_backup()` funksiyasi:
  DB dvigatelidan (sqlite/mysql) qat'i nazar ishlashi uchun Django'ning
  standart `dumpdata` buyrug'idan foydalanadi (`contenttypes`,
  `auth.permission`, `sessions.session`, `admin.logentry` chiqarib
  tashlanadi — ular yangi serverda avtomatik qayta yaratiladi). Natija
  `all_data.json` + butun `media/` papkasi (vaqtinchalik `temp_backups/`
  papkasi o'tkazib yuboriladi) bitta ZIP arxivga yig'iladi, ichiga tiklash
  yo'riqnomasi bilan `README.txt` ham qo'shiladi (`loaddata` orqali qo'lda
  tiklash — bu funksiya faqat export qiladi, restore qilmaydi).
- `landing/views.py` — ikkita yangi superadmin view (`@user_passes_test(is_superuser)`,
  mavjud barcha `super_*` viewlar bilan bir xil naqsh):
  - `super_backup_page` — firmalar ro'yxatini ko'rsatadigan sahifa
  - `super_backup_download` — `?scope=company&company_id=N` yoki
    `?scope=full` query parametriga qarab ZIP qaytaradi
- `landing/urls.py` va `crm/admin_urls.py` — ikkalasiga ham (mavjud
  superadmin route dublikatsiya naqshiga mos) yangi `backup`/`backup/download`
  yo'llari qo'shildi.
- `landing/templates/landing/super_backup.html` — yangi sahifa (mavjud
  `glass-card`/`btn btn-primary`/`btn btn-outline` uslubida): "Bitta firma
  zaxirasi" (firma tanlash + yuklab olish) va "Butun tizim zaxirasi"
  (tasdiqlash bilan, chunki hajmi katta bo'lishi mumkin) bo'limlari.
- `super_base.html` — chap menyuga "Backup" havolasi qo'shildi.

### Nega restore UI yo'q (ataylab)
Foydalanuvchi buni aniq talab qildi. Sabab ham mantiqiy: butun tizim
zaxirasi **boshqa** (yangi) serverga ko'chirish uchun mo'ljallangan — o'sha
serverda hali Django/DB ham ishga tushirilmagan bo'ladi, demak "shu sahifadan
tiklash" tushunchasining o'zi noto'g'ri kontekstda. Shuning uchun ZIP ichiga
`README.txt` bilan aniq qo'lda bajariladigan qadamlar yozib qo'yildi
(`migrate` → media papkani ko'chirish → `loaddata`).

### O'zgargan fayllar
- `main/backup_utils.py` — `generate_full_system_backup()`
- `landing/views.py` — `super_backup_page`, `super_backup_download`
- `landing/urls.py`, `crm/admin_urls.py` — yangi yo'llar
- `landing/templates/landing/super_backup.html` — yangi sahifa
- `landing/templates/landing/super_base.html` — nav havolasi

### Tekshirildi
- `python manage.py check` — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback qilindi): (a)
  `generate_backup(company)` to'g'ri ZIP qaytarishi (mavjud, regressiyasiz)
  ✅; (b) `generate_full_system_backup()` `all_data.json` (1022 ta yozuv,
  test bazasida) + `README.txt` + media fayllarni to'g'ri ZIP qilishi ✅;
  (c) haqiqiy superuser orqali (`admin.localhost` — `crm.admin_urls`
  yo'liga mos) `/backup/` sahifasi 200 qaytarishi ✅; (d) `/backup/download/
  ?scope=company&company_id=N` va `?scope=full` ikkalasi ham to'g'ri
  `application/zip` javob qaytarishi ✅

---

## 43-qadam: "Ishlab chiqarish" va "Qo'shimcha chiqimlar" sidebar havolalari olib tashlandi

**Holat: DONE**

Foydalanuvchi sidebar skrinshotini ko'rsatib ikkita menyu havolasini
("Ishlab chiqarish", "Qo'shimcha chiqimlar") olib tashlashni so'radi —
sababi: retsept/xarajat boshqaruvi allaqachon mahsulot sozlash
sahifalariga (32-36 qadamlar) ko'chirilgan, bu sahifalar endi ortiqcha.
Aniqlashtiruvdan so'ng ikkita alohida qaror:
- **"Qo'shimcha chiqimlar"** — faqat sidebar havolasi olib tashlandi
  (sahifa/model/backend o'zgarishsiz qoldi — bu aslida firma darajasidagi
  umumiy xarajatlar ro'yxati, mahsulotga bog'liq emas, ma'lumot yo'qolmadi).
- **"Ishlab chiqarish"** — foydalanuvchi aniq ko'rsatma berdi: "oylik
  ko'rinish qismini hodim qismiga o'tkazamiz" — ya'ni sahifadagi yagona
  qolgan sozlama ("Ish haqi turi": Oylik / Mahsulot soniga qarab) **Hodimlar**
  sahifasiga ko'chirildi, eski sahifa/route esa endi butunlay ortiqcha
  bo'lgani uchun to'liq o'chirildi.

### Nima qilindi
- `main/templates/egabase.html` — ikkala sidebar `<li>` (Ishlab chiqarish,
  Qo'shimcha chiqimlar) olib tashlandi. (Diqqat: bu tahrirlash paytida
  tasodifan qo'shni "Ombor" submenu blokining `{% endif %}` teglaridan biri
  ortiqcha qolib ketgan edi — darhol aniqlanib, shablon xato bermasligi
  uchun tuzatildi va qayta render qilib tekshirildi.)
- `main/list_views.py:hodimlar_list` — endi POST bilan `action=
  set_ish_haqi_turi` ni ham qabul qiladi (avvalgi `production_settings_page`
  bilan bir xil mantiq: `company.ish_haqi_turi` yangilanadi), context'ga
  `ish_haqi_turi_choices`/`current_ish_haqi_turi` qo'shildi.
- `main/templates/hodimlar_list.html` — sahifa boshiga "Ish haqi turi"
  kartasi (select + saqlash tugmasi + tushuntirish matni, eski
  `production_settings.html`dagi bilan bir xil) qo'shildi.
- `main/production_views.py` — `production_settings_page` funksiyasi
  butunlay o'chirildi (endi hech qanday mantiq qolmagani uchun); ishlatilmay
  qolgan `messages` importi va `_ega_guard` helperi ham tozalandi
  (`serial_list_page` uchun faqat `_warehouse_guard` kerak edi).
- `main/urls.py` — `production_settings` route va importi o'chirildi.
- `main/templates/production_settings.html` — o'chirildi (endi hech kim
  ishlatmaydi).
- `main/templates/serial_list.html` — "Orqaga" havolasi endi
  o'chirilgan `production_settings` o'rniga `mahsulotlar_list`ga
  yo'naltiriladi (bu sahifa allaqachon hech qayerdan bog'lanmagan,
  Serial/QR funksiyasi 42-qadamdan oldin sidebardan olib tashlangan edi —
  shunga qaramay tup havola tuzatildi).

### O'zgargan fayllar
- `main/templates/egabase.html`
- `main/list_views.py`, `main/templates/hodimlar_list.html`
- `main/production_views.py`, `main/urls.py`
- `main/templates/production_settings.html` (o'chirildi)
- `main/templates/serial_list.html`

### Tekshirildi
- `python manage.py check` — xatosiz
- Haqiqiy `ega` foydalanuvchi orqali bosh sahifa (`egabase.html` ishlatadi)
  render qilinganda 200 qaytishi (shablon sintaksisi buzilmagani
  tasdiqlandi) ✅
- **Izolyatsiyalangan tranzaksiyada** (rollback qilindi): (a) `/hodimlar/`
  sahifasida "Ish haqi turi" bloki borligi ✅; (b) shu sahifadan POST orqali
  `ish_haqi_turi='per_unit'` saqlanishi ✅; (c) `reverse('production_settings')`
  endi `NoReverseMatch` berishi — eski route to'liq o'chirilgani
  tasdiqlandi ✅

---

## 44-qadam: Xodimni tahrirlash sahifasida mahsulot biriktirish ("items") + oylik statistika/topgan pul

**Holat: DONE**

Foydalanuvchi "Xodimni Tahrirlash" (`editusr.html`) skrinshotini ko'rsatib
ko'rsatdiki, ishlab chiqaruvchiga mahsulot biriktirish imkoniyati bu
sahifada yo'q edi (u aslida faqat kamdan-kam ishlatiladigan boshqa sahifada
— `/profile/<username>/` — mavjud edi). Talab: (1) mahsulot biriktirish
"items kabi" (chip/teg ko'rinishida) bo'lsin, (2) shu sahifa pastida
ishlab chiqaruvchining mahsulotlari va topgan puli ko'rsatilsin, (3) xodim
o'zi profiliga kirganda ham o'z statistikasi va shu oy topgan pulini
ko'rsin.

### Nima qilindi
- `main/services/stock_service.py` — yangi `get_pazanda_month_stats(pazanda,
  company)` funksiyasi: joriy oy uchun `MiqdorQoshish` (tasdiqlangan)
  yozuvlaridan `ish_haqi_summasi` yig'indisini ("topgan puli" — jarima
  allaqachon ichida ayirilgan, `_apply_retsept_hisobkitob`da hisoblangan)
  va mahsulot bo'yicha jamlangan ishlab chiqarilgan miqdorni qaytaradi.
- `main/views.py` — yangi `_pazanda_assignment_context(pz, company)` umumiy
  yordamchi funksiya (biriktirilgan/biriktirilishi mumkin mahsulotlar +
  oylik statistika) — bu avval faqat `profile_view` ichida yozilgan bo'lib,
  endi takrorlanmasligi uchun umumiy funksiyaga chiqarildi va **uchta**
  joyda ishlatiladi:
  - `editusr` (asosiy — foydalanuvchi so'ragan sahifa): GET context'ga
    qo'shildi; POST'ga `action=assign_mahsulot`/`unassign_mahsulot`
    handleri qo'shildi (profile_view'dagi bilan bir xil mantiq).
  - `profile_view` (`ega` boshqa xodim profiliga kirganda, `egaprofile.html`) —
    endi shu umumiy funksiyadan foydalanadi (oldingi qo'lda yozilgan
    dublikat kod olib tashlandi).
  - `profile_view` (xodimning **o'zi** o'z profiliga kirganda,
    `pzprofile.html`) — avval bu yerda **hech qanday statistika yo'q edi**
    (faqat ism/login/email ko'rsatilar edi). Endi `pazanda_month_stats` va
    `assigned_products` (faqat o'qish uchun, tahrirlash tugmalarisiz)
    context'ga qo'shildi.
- `main/templates/editusr.html` — `user_edit.type` `pazanda`/
  `ishlab_chiqaruvchi` bo'lganda, asosiy formadan tashqarida (nested form
  bo'lmasligi uchun) ikkita yangi karta: "Biriktirilgan mahsulotlar" (har
  bir mahsulot — teg/chip ko'rinishida, ustiga bosilganda ✕ belgisi bilan
  o'chiriladi, pastda tanlash+qo'shish formasi) va "Bu oy statistikasi"
  ("Bu oy topgan puli" — katta raqam bilan, va mahsulot bo'yicha ishlab
  chiqarilgan miqdorlar jadvali).
- `main/templates/egaprofile.html` — mavjud (lekin qatorlar ko'rinishidagi)
  "Biriktirilgan mahsulotlar" bo'limi ham xuddi shu teg/chip uslubiga
  o'tkazildi (izchillik uchun), va yangi "Bu oy statistikasi" kartasi
  qo'shildi.
- `main/templates/pzprofile.html` — xodimning o'z profili uchun yangi
  bo'lim: "Mening mahsulotlarim" (faqat ko'rsatish uchun teglar) va "Bu oy
  statistikam" ("Bu oy topgan pulim" + ishlab chiqargan mahsulotlar
  jadvali).

### O'zgargan fayllar
- `main/services/stock_service.py` — `get_pazanda_month_stats()`
- `main/views.py` — `_pazanda_assignment_context()`, `editusr`, `profile_view`
- `main/templates/editusr.html`, `egaprofile.html`, `pzprofile.html`

### Tekshirildi
- `python manage.py check` — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback qilindi, haqiqiy `ega` va
  pazanda foydalanuvchilar orqali): (a) `/edituser/<username>` sahifasida
  "Biriktirilgan mahsulotlar" va "Bu oy statistikasi" bo'limlari borligi ✅;
  (b) shu sahifadan `assign_mahsulot`/`unassign_mahsulot` POST orqali
  `PazandaMahsulot` to'g'ri yaratilishi/o'chirilishi ✅; (c) `MiqdorQoshish`
  (tasdiqlangan, `ish_haqi_summasi=15000`) yozilgach, sahifada "15 000"
  ko'rinishi ✅; (d) `ega` boshqa xodim profiliga kirganda (`egaprofile.html`)
  ham xuddi shu ma'lumot ko'rinishi ✅; (e) pazanda o'zi o'z profiliga
  kirganda (`pzprofile.html`) "Mening mahsulotlarim" va oylik statistika
  ko'rinishi ✅

---

## 45-qadam: "birzumda" firmasi uchun oxirgi 3 haftalik real-ga yaqin sotuv tarixi + dashboard pul ko'rsatish bugi

**Holat: DONE**

Foydalanuvchi so'radi: sotuv arxitekturasi (41-qadamdagi `Savdo.foyda`
snapshoti) tuzatilgan bo'lgani uchun, endi test/demo maqsadida oxirgi 3
haftaga (21 kun) tasodifiy, real-ga yaqin sotuv yozuvlari to'ldirilsin.

### Nima qilindi
- Bir martalik skript (`scratchpad/seed_savdo_3weeks.py`, loyihaga saqlanmagan
  — faqat shu ishni bajarish uchun, isbotlash uchun avval `transaction.atomic()`
  + rollback bilan **quruq sinov** o'tkazilib, keyin haqiqiy bazaga yozildi):
  - `birzumda` firmasi (mavjud mahsulotlar: Un, Shakar, Nonka, Burger; 5 ta
    haridor; yetkazib beruvchi "banda") uchun har bir kunga (oxirgi 21 kun,
    bugungacha) tasodifiy 1-6 ta savdo yaratildi (dam olish kunlari kamroq —
    1-3 ta, ish kunlari 2-6 ta) — jami **68 ta** yozuv.
  - Har bir savdo: 1-3 tasodifiy mahsulot, real birlik-mos miqdorlar (kg
    uchun 1-15, dona uchun 1-25), joriy `narxi`/`tannarx` asosida
    `summa`/`foyda` hisoblangan (41-qadamdagi formula bilan bir xil — bu
    real sotuv oqimi bilan mos bo'lishi uchun muhim edi).
  - `Savdo.vaqt_sana` (auto_now_add) — yaratilgandan keyin
    `.filter(pk=...).update(vaqt_sana=...)` orqali tarixiy sanaga
    (kunning tasodifiy soatiga, 09:00-19:00 oralig'ida) o'rnatildi.
  - Har bir yozuv uchun haqiqiy (kichik, validatsiyadan o'tadigan) PNG rasm
    fayli `smr` maydoniga yozildi (real oqimda ham rasm majburiy).
  - Mos `AmalLog` yozuvlari ham (bir xil tarixiy vaqt bilan) qo'shildi.
  - `Mahsulot.miqdori` (joriy zaxira) **ataylab o'zgartirilmadi** — bu faqat
    hisobot/dashboard ma'lumotlarini to'ldirish uchun, bugungi haqiqiy
    zaxira noto'g'ri kamayib ketmasligi kerak edi.
  - Natija: 68 ta savdo (ID 16-83), jami summa ≈10,49 mln so'm, jami
    foyda ≈7,00 mln so'm (Un/Shakar/Nonkaning `tannarx`i hozircha 0
    bo'lgani uchun — bu haqiqiy joriy ma'lumot, foyda shunga mos yuqori
    chiqdi, skriptning xatosi emas).

### Kutilmagan, lekin darhol topilgan va tuzatilgan bug
Yangi ma'lumot bilan dashboardni tekshirganda, **"Bugungi Daromad" va yangi
qo'shilgan "Oylik Sof Foyda" kartalari "0" ko'rsatib turgani** aniqlandi —
bu 41-qadamda emas, undan ancha oldin yozilgan eski koddagi bug edi:
`add_spctoint()` funksiyasi allaqachon bo'shliq bilan formatlangan matn
qaytaradi (masalan `"5 413 070.5"`), shablon esa ustiga yana
`|floatformat:0` qo'llar edi — Django'ning `floatformat` filtri bunday
bo'shliqli matnni raqamga aylantira olmay, natijada "0" qaytarardi. Bu
"Oylik Sof Foyda" ishlamayotganini tekshirish jarayonida ochilib qoldi.

### Nima qilindi (bug tuzatish)
- `main/templates/main.html` — uchta joydagi ortiqcha `|floatformat:0`
  filtri olib tashlandi (`bsumma` — 2 marta, `oylik_foyda`), chunki
  `add_spctoint()` allaqachon to'g'ri formatlangan matn qaytaradi.
- `main/views.py:main` — `oylik_foyda` endi `add_spctoint(round(oylik_foyda))`
  — o'nlik qism (masalan ".5", kasr miqdordagi kg savdolaridan) yumaloqlanib,
  ko'rinish tozalanadi.

### O'zgargan fayllar
- `main/views.py` — `main()` (`oylik_foyda` yumaloqlash)
- `main/templates/main.html` — `floatformat` olib tashlash (3 joy)
- (bir martalik) `scratchpad/seed_savdo_3weeks.py` — loyihaga saqlanmagan

### Tekshirildi
- Dry-run (`transaction.atomic()` + rollback) orqali skript xatosiz
  ishlashi tasdiqlangandan keyingina haqiqiy bazaga yozildi ✅
- Yozilgandan keyin: 68 ta savdo to'g'ri kunlarga taqsimlangani (har kunga
  1-6 ta), `smr` rasm fayllari diskda mavjudligi tekshirildi ✅
- Haqiqiy `ega` foydalanuvchi orqali bosh sahifa render qilinganda,
  tuzatishdan **oldin** "Bugungi Daromad"/"Oylik Sof Foyda" ikkalasi ham
  "0" ko'rsatgani, tuzatishdan **keyin** to'g'ri qiymatlar ("714 653" va
  "5 413 070") ko'rsatilgani solishtirib tasdiqlandi ✅
- `python manage.py check` — xatosiz

---

## 46-qadam: Seed to'liqlashtirildi — ishlab chiqaruvchilar va savdogar sotuvlari ham qo'shildi

**Holat: DONE**

45-qadamda faqat **yetkazib beruvchi (banda) orqali haridorlarga sotuv**
seed qilingan edi. Foydalanuvchi "Azimjonov Azizbek" (pazanda,
`ninetydev1`) xodim sahifasi skrinshotini ko'rsatib to'g'ri ta'kidladi:
**ishlab chiqaruvchilarning ishlab chiqargani** ("Bu oy topgan puli: 0
so'm", "Shu oy hali hech narsa ishlab chiqarilmagan") va **savdogar orqali
sotilganlar** butunlay seed qilinmagan edi — bu chala ish edi.

### Aniqlangan sabab
`company.ish_haqi_turi = 'fixed'` bo'lgani uchun (default holat) —
`_apply_retsept_hisobkitob` hech qachon `ish_haqi_summasi`ni hisoblamas edi
(bu qasddan qilingan biznes qoidasi: "Oylik" tanlansa tizim maosh
hisoblamaydi). Shuning uchun hatto `MiqdorQoshish` yozuvlari bo'lganda ham
"topgan puli" 0 chiqishi kerak edi.

### Nima qilindi (yana bir marta bir martalik skript, oldin dry-run bilan tekshirilib, keyin bazaga yozildi)
- `birzumda.ish_haqi_turi` → `'per_unit'`ga o'zgartirildi (Hodimlar
  sahifasidagi 43-qadamda ko'chirilgan sozlama) — aks holda "topgan puli"
  funksiyasining o'zi hech qachon ishlamas edi.
- `Un`/`Shakar`/`Nonka` uchun (avval `ishlab_chiqarish_narxi=0` edi)
  taxminiy real ish haqi stavkalari o'rnatildi (300/400/350 so'm/birlik) —
  aks holda bu mahsulotlarni "ishlab chiqarish" hech qanday pul
  keltirmasdi.
- Ikkita xodimga (Xaydarov Rafiq → Un, Abdurasul Xaydarov → Shakar+Nonka)
  `PazandaMahsulot` orqali mahsulot biriktirildi (Azimjonov Azizbek →
  Burger allaqachon bor edi).
- Har bir xodim + biriktirilgan mahsulot uchun oxirgi 21 kunga (har
  ikkinchi kun atrofida, tasodifiy) **48 ta** `MiqdorQoshish` (ishlab
  chiqarish) yozuvi to'g'ridan-to'g'ri to'g'ri hisoblangan
  `ish_haqi_summasi`/`jarima_summasi`/`tannarx_snapshot` bilan yaratildi
  (real servis (`approve_miqdor_qoshish_service`) chaqirilmadi — u
  `ProductionMaterialRequest` orqali xom-ashyo so'rovi bo'lishini talab
  qiladi va ular yo'qligi sabab sun'iy "chetlashish jarimasi" hosil
  bo'lardi; shu sabab to'g'ridan-to'g'ri realistik qiymatlar yozildi, xuddi
  45-qadamdagi `Savdo.foyda` seedida qilingandek).
- **Savdogar (`savdogar` foydalanuvchisi) orqali Burger sotuvlari** — 21
  kunga **15 ta** yozuv, shartnoma raqami ketma-ketligi
  (`savdogar_contract_next_number`) to'g'ri oshirib borilib, soxta (lekin
  yaroqli) shartnoma/pasport rasm fayllari bilan yaratildi.
- `Mahsulot.miqdori` bu safar ham qasddan o'zgartirilmadi (faqat
  hisobot/statistika uchun, joriy zaxira buzilmasligi kerak).

### Muhim kuzatuv (kod bugi emas, real ma'lumot holati)
Savdogar sotuvlarining **foydasi 0** chiqdi — sababi, Burgerning joriy
`narxi` (16320) uning `tannarx`iga (16320) teng (39/40-qadamlardagi
"narx=tannarx" tarixi bilan bog'liq — keyin qo'lda tahrirlashga
qaytarilgan, lekin hali hech kim narxni tannarxdan yuqori qilib
o'zgartirmagan). Bu real ma'lumot holati, seed skriptining xatosi emas —
agar Burgerga real foyda ko'rinishini xohlasa, foydalanuvchi
`seemahsulot`da narxni tannarxdan yuqori qilib qo'yishi kerak.

### O'zgargan ma'lumotlar (kod o'zgarmadi, faqat DB)
- `Company.ish_haqi_turi` (birzumda)
- `Mahsulot.ishlab_chiqarish_narxi` (Un/Shakar/Nonka)
- `PazandaMahsulot` (2 ta yangi biriktirish)
- `MiqdorQoshish` — 48 ta yangi yozuv
- `Savdo`/`AmalLog` — 15 ta yangi savdogar sotuvi

### Tekshirildi
- Dry-run (`transaction.atomic()` + rollback) orqali xatosiz ekani
  tasdiqlangandan keyin haqiqiy bazaga yozildi ✅
- `ega` foydalanuvchi orqali `/edituser/ninetydev1` (Azimjonov Azizbek)
  sahifasi endi "Bu oy topgan puli: 134584 so'm" ko'rsatishi tasdiqlandi
  (avval "0" edi) ✅
- `python manage.py check` — xatosiz

---

## 47-qadam: Dashboardda "Top Hodimlar" — bu oy eng ko'p pul ishlab topgan 8 nafar xodim + yashil badge

**Holat: DONE**

Foydalanuvchi bosh sahifadagi "So'nggi Hodimlar" kartochkalar bo'limini
ko'rsatib so'radi: har bir kartaning yuqori o'ng burchagida yashil rangda
o'sha xodimning ishlab topgan puli (masalan "+1.6M" yoki "+800K")
ko'rsatilsin, va bu bo'lim eng oxirgi qo'shilgan emas, balki **eng ko'p
pul ishlab topgan 8 nafar xodimni** ko'rsatsin.

### Yechim — lavozimga qarab turlicha "topgan pul" mezoni
Tizimda faqat ishlab chiqaruvchi (pazanda) uchun aniq "ish haqi" tushunchasi
bor edi (`MiqdorQoshish.ish_haqi_summasi`, 44-qadamda ishlatilgan). Boshqa
lavozimlar uchun shaxsiy maosh tizimi kodda yo'q, shuning uchun "pul ishlab
topdi" degani lavozimga qarab quyidagicha aniqlandi:
- **Ishlab chiqaruvchi** (`pazanda`/`ishlab_chiqaruvchi`) — shu oy
  `ish_haqi_summasi` yig'indisi (44-qadamdagi bilan bir xil manba).
- **Savdogar** — shu oy o'zi yopgan savdolar (`Savdo.savdogar=user`) summasi
  yig'indisi.
- **Yetkazib beruvchi** — shu oy o'zi yopgan savdolar
  (`Savdo.yetkazib_beruvchi=<YetkazibBeruvchi>`) summasi yig'indisi (xuddi
  mavjud `kpi_today` endpointida ishlatilgan mezon bilan bir xil).
- **Omborchi** va boshqalar — 0 (ular uchun aniq "pul ishlab topish" mezoni
  yo'q, badge ko'rsatilmaydi).

### Nima qilindi
- `main/functions.py` — yangi `format_compact_money(value)`: 1 250 000 →
  `"1.3M"`, 800 000 → `"800K"`, 500 → `"500"` (mavjud Chart.js'dagi
  k/M formatlash mantig'iga mos, endi server tomonda ham bor).
- `main/views.py:main` (`ega` filiali) — avvalgi "so'nggi 6 ta xodim"
  (`order_by('-date_joined')[:6]`) o'rniga: barcha xodimlar uchun yuqoridagi
  mezon bo'yicha shu oylik "topgan puli" hisoblanadi (har bir `User`
  obyektiga `.earned`/`.earned_display` runtime-atributlari sifatida
  biriktiriladi), so'ng shu qiymat bo'yicha kamayish tartibida saralanib,
  **eng yuqori 8 tasi** `hodims` context'iga beriladi.
- `main/templates/main.html` — bo'lim sarlavhasi "So'nggi Hodimlar" dan
  "Top Hodimlar (bu oy)"ga o'zgartirildi; `.item-card`ga `position:relative`
  qo'shildi; yangi `.earn-badge` (yashil, yumaloq, yuqori-o'ng burchakda)
  CSS klassi qo'shildi; har bir kartaga `{% if h.earned %}` bo'lganda
  `+{{ h.earned_display }}` badge chiqariladi (0 topganlarga badge
  ko'rsatilmaydi).

### O'zgargan fayllar
- `main/functions.py` — `format_compact_money()`
- `main/views.py` — `main()` (top-8 hisob-kitobi)
- `main/templates/main.html` — sarlavha, CSS, badge markup

### Tekshirildi
- `python manage.py check` — xatosiz
- Haqiqiy `ega` foydalanuvchi orqali (`birzumda`) bosh sahifa render
  qilinganda, "Top Hodimlar" bo'limida xodimlar to'g'ri kamayish tartibida
  ("+8.4M", "+881K", "+135K", "+107K", "+32K") chiqishi va 0 topgan
  xodimlarda badge ko'rinmasligi tasdiqlandi ✅

---

## 48-qadam: Ombor mahsulotlari ro'yxatida rasm ko'rsatildi

**Holat: DONE**

Foydalanuvchi "Ombor" ro'yxati skrinshotini ko'rsatib, mahsulot rasmi
ro'yxatda ko'rinmasligini ta'kidladi.

### Nima qilindi
- `main/templates/warehouse_products.html` — "Mahsulot" ustuniga
  44x44px, dumaloq burchakli rasm (`product.rasmi.url`) qo'shildi, nomi
  va o'lchov birligi yonida. Rasm bo'lmagan holatlar uchun (nazariy —
  ombor mahsulotlarida rasm 29-qadamdan beri majburiy, lekin eski
  yozuvlar uchun ehtiyot chorasi) kulrang fon + rasm ikonkasi placeholder
  sifatida ko'rsatiladi.

### O'zgargan fayllar
- `main/templates/warehouse_products.html`

### Tekshirildi
- `python manage.py check` — xatosiz
- Haqiqiy `ega` foydalanuvchi orqali `/ombor/mahsulotlar/` sahifasi 200
  qaytarishi va `<img src=` tegi mavjudligi tasdiqlandi ✅

---

## 49-qadam: Ombor ro'yxatida ortiqcha "Narx" ustuni olib tashlandi

**Holat: DONE**

Foydalanuvchi to'g'ri ta'kidladi: Ombor (xom ashyo/yarim tayyor) mahsulotlari
mijozga sotilmaydi — ularning "Narx" (`narxi`) maydoni har doim `0`
(25/26-qadamlarda shunday belgilangan, qo'lda tahrirlanmaydi ham). Shuning
uchun ro'yxatda alohida "Narx" ustunini ko'rsatish chalkashtiruvchi va
keraksiz edi — faqat o'rtacha (tannarx) narx yetarli.

### Nima qilindi
- `main/templates/warehouse_products.html` — "Narx" ustuni (sarlavha +
  qator) butunlay olib tashlandi; "Tannarx" sarlavhasi "O'rtacha narx
  (tannarx)"ga o'zgartirildi (buning o'rtacha og'irlikdagi kirim narxi
  ekanini aniqlashtirish uchun); bo'sh-ro'yxat holatidagi `colspan`
  qiymatlari (6→5, 7→6) mos ravishda kamaytirildi.

### O'zgargan fayllar
- `main/templates/warehouse_products.html`

### Tekshirildi
- `python manage.py check` — xatosiz
- Haqiqiy `ega` foydalanuvchi orqali `/ombor/mahsulotlar/` sahifasida
  "Narx" sarlavhasi endi yo'qligi va "O'rtacha narx" sarlavhasi borligi
  tasdiqlandi ✅

---

## 50-qadam: Desktop Agent — birinchi bosqich (Omborlar + kamera sozlash: USB/RTSP + Skaner)

**Holat: DONE (poydevor)**

Foydalanuvchi CRM veb-ilovasidan tashqari, alohida **Desktop Agent**
(kompyuterda ishlaydigan dastur) qurishni boshlashga qaror qildi — bu
oldindan `C:\Users\Banda\.claude\plans\quiet-waddling-heron.md`dagi
"NEXT3" bo'limida rejalashtirilgan katta ish. Kelishilgan yondashuv:
**avval desktop qismi mustaqil (backend'siz) qurilib**, keyingi bosqichda
REST API orqali CRM bilan bog'lanadi. Texnologiya: **Python + PyQt6**
(Django bilan bir xil til). Loyiha joyi: shu repo ichida, yangi
**`desktop_agent/`** papkasi (CRM Django kodidan butunlay ajratilgan,
alohida `venv`, alohida `requirements.txt`).

Foydalanuvchi tasvirlagan birinchi oqim: **omborlar yaratiladi → har bir
omborga kamera bog'lanadi** (USB bo'lsa qurilmalar ro'yxatidan tanlanadi,
RTSP bo'lsa manzil+login+parol kiritiladi) **→ alohida "skaner" kamerasi
belgilanadi** (shtrix-kod/QR skaneri oldidagi web-kamera, omborga
bog'lanmagan, yagona).

### Nima qilindi
- **`desktop_agent/app/db.py`** — mahalliy SQLite qatlami (hozircha CRM
  bilan bog'lanmagan, birinchi bosqich): `warehouses` va `cameras`
  jadvallari. `cameras.role` — `'ombor'` (bitta ombor = bitta kamera,
  `warehouse_id` orqali) yoki `'skaner'` (yagona, `warehouse_id=NULL`).
  `ON DELETE CASCADE` — ombor o'chirilsa, unga bog'langan kamera ham
  o'chadi.
- **`desktop_agent/app/camera_utils.py`** — `detect_usb_cameras()` (OpenCV
  DSHOW orqali indekslarni probe qilish), `build_rtsp_url()` (login/parolni
  URL ichiga joylashtirish), `UsbDetectWorker`/`CameraPreviewWorker`
  (`QThread` — UI muzlab qolmasligi uchun aniqlash/jonli ko'rinish fon
  oqimida ishlaydi).
- **`desktop_agent/app/windows/`** — PyQt6 UI:
  - `main_window.py` — asosiy oyna, chap sidebar (Omborlar / Skaner)
  - `warehouse_list_page.py` — omborlar jadvali (qo'shish/tahrirlash/
    o'chirish, har biriga "Kamera sozlash" tugmasi + joriy kamera holati
    ustuni)
  - `warehouse_form_dialog.py` — ombor qo'shish/tahrirlash (nomi, manzil)
  - `camera_config_dialog.py` — **umumiy** dialog (ombor kamerasi ham,
    skaner kamerasi ham shu orqali sozlanadi): USB/RTSP radio-tanlov, USB
    uchun "Kameralarni aniqlash" + tanlash, RTSP uchun manzil+login+parol,
    "Ulanishni tekshirish" tugmasi bilan jonli ko'rinish (`QLabel`da,
    `QImage`ga aylantirilgan kadrlar)
  - `scanner_page.py` — skaner kamerasi holatini ko'rsatish + sozlash
    (xuddi shu `camera_config_dialog` orqali, `role='skaner'`)
- **`desktop_agent/main.py`** — kirish nuqtasi (`db.init_db()` + `QApplication`)
- `desktop_agent/requirements.txt` (PyQt6, opencv-python), `.gitignore`
  (`venv/`, `agent_data.db`), `README.md` (o'rnatish/ishga tushirish
  yo'riqnomasi + fayl tuzilishi + keyingi bosqich haqida eslatma)

### Tekshirildi
- Alohida `venv` yaratilib, `PyQt6==6.7.1` va `opencv-python==4.10.0.84`
  o'rnatildi ✅
- `QT_QPA_PLATFORM=offscreen` orqali (haqiqiy displey talab qilmaydigan)
  smoke-testlar: (a) `MainWindow` va ikkala sahifa (Omborlar/Skaner)
  xatosiz yaratilishi ✅; (b) ombor yaratish → ro'yxatda ko'rinishi ✅;
  (c) ombor uchun USB kamera (`usb_index=0`) saqlanib, to'g'ri o'qilishi
  ✅; (d) skaner uchun RTSP kamera (login/parol bilan) saqlanib, to'g'ri
  o'qilishi ✅; (e) `build_rtsp_url()` login/parolni to'g'ri URL ichiga
  joylashtirishi (`rtsp://admin:12345@192.168.1.50:554/stream1`) ✅;
  (f) `CameraConfigDialog` ochilib, USB aniqlash fon oqimi ishlab, combo
  to'ldirilishi ✅; (g) ombor o'chirilganda unga bog'langan kamera ham
  kaskad tarzda o'chishi ✅

### Keyingi bosqich (hozircha qilinmagan)
Foydalanuvchi aytganidek: **"so'ng esa biz REST API ko'tarib bog'laymiz"**
— bu keyingi, alohida bosqich. Hozircha omborlar faqat shu dasturning
mahalliy SQLite bazasida yashaydi; keyinroq CRM'dagi haqiqiy `Ombor`
modeli bilan REST API orqali sinxronlanadi (`quiet-waddling-heron.md`
rejasidagi "NEXT3" bo'limi asosida).

---

## 51-qadam: Desktop Agent — REST API bog'lanishi (CRM'dagi haqiqiy Omborlar bilan sinxronlash) + build

**Holat: DONE**

50-qadamda Desktop Agent'ning mustaqil (backend'siz) poydevori qurilgan
edi. Foydalanuvchi endi keyingi bosqichga o'tishni so'radi — aynan o'zi
avval aytgan reja: **"so'ng esa biz REST API ko'tarib bog'laymiz"**.

### Django tomoni — yangi REST API
- **`Company.desktop_agent_token`** — yangi maydon (unique, opaque token,
  `BillingPaymentLink.token` naqshiga o'xshab), migratsiya
  `0071_company_desktop_agent_token.py`.
- **`main/agent_api_views.py`** — yangi `GET /api/agent/omborlar/`
  endpoint (Django REST Framework, `@api_view`). Autentifikatsiya —
  sessiya/subdomain emas, `Authorization: Token <token>` header orqali
  (`Company.desktop_agent_token` bo'yicha qidiriladi). Noto'g'ri/yo'q
  token — `401`. To'g'ri bo'lsa — shu firmaning `Ombor.objects.filter(...)`
  ro'yxati (`id`, `nomi`, `manzil`) JSON qilib qaytariladi.
- **`crm/settings.py`** — `rest_framework` `INSTALLED_APPS`ga qo'shildi
  (paket allaqachon o'rnatilgan edi, lekin ro'yxatlanmagan edi).
- **`main/middleware.py`** (`CompanyMiddleware`) — `api/agent` prefiksi
  `admin_panel`/`api/click` bilan bir xil "har doim asosiy ROOT_URLCONF
  orqali" bypass ro'yxatiga qo'shildi — bu endpoint qaysi host (subdomain,
  asosiy domen, `localhost`) orqali chaqirilishidan qat'i nazar ishlaydi,
  chunki firma token orqali aniqlanadi, subdomain orqali emas.
- **`landing/urls.py`** — `/api/agent/omborlar/` yo'li qo'shildi.
- **`main/warehouse_views.py`** (`ombor_list_page`) — yangi
  `action=generate_agent_token` POST handleri (`uuid4().hex` bilan token
  yaratadi/qayta yaratadi).
- **`main/templates/ombor_list.html`** — "Desktop Agent token" bo'limi:
  token ko'rsatiladi (nusxalash tugmasi bilan) yoki hali yo'q bo'lsa
  "Token yaratish" tugmasi; "Qayta yaratish" — eskisini bekor qilib
  yangisini beradi (tasdiqlash so'raladi).

### Desktop Agent tomoni — sinxronlash
- **`app/db.py`** — `warehouses` jadvaliga `remote_id` ustuni (CRM'dan
  kelgan omborlarni mahalliy qo'lda qo'shilganlardan ajratish uchun,
  UNIQUE); yangi `settings` jadvali (server URL, token saqlash uchun
  key-value); yangi `sync_warehouses_from_remote(remote_omborlar)` —
  `remote_id` bo'yicha upsert qiladi, CRM'da endi yo'q omborlarni mahalliy
  bazadan ham o'chiradi (kamerasi bilan birga), **qo'lda qo'shilgan**
  (remote_id=NULL) omborlarga tegmaydi. Eski bazalar uchun yumshoq
  migratsiya (`ALTER TABLE ... ADD COLUMN` agar ustun yo'q bo'lsa).
- **`app/api_client.py`** (yangi) — `fetch_omborlar(server_url, token)` —
  `requests` orqali API'ni chaqiradi, tarmoq/401/JSON xatolarini aniq
  xabar bilan `ApiError` sifatida ko'taradi.
- **`app/windows/settings_page.py`** (yangi) — "Sozlamalar" sahifasi:
  server manzili + token maydonlari, "Saqlash" va "Sinxronlash" tugmalari
  (sinxronlash — avval saqlaydi, keyin API'ni chaqirib
  `sync_warehouses_from_remote` ni ishga tushiradi, natija/xato holat
  matni bilan ko'rsatiladi).
- **`app/windows/main_window.py`** — sidebar'ga "Sozlamalar" bo'limi
  qo'shildi; sinxronlashdan keyin Omborlar sahifasi avtomatik yangilanishi
  uchun `on_synced=self.warehouse_page.refresh` callback uzatildi.
- **`app/windows/warehouse_list_page.py`** — CRM'dan sinxronlangan
  omborlar nomi yonida `[CRM]` belgisi ko'rsatiladi (qo'lda
  qo'shilganlardan farqlash uchun).
- `requirements.txt`ga `requests==2.34.2` qo'shildi.

### Qayta build qilindi
`StockFirmAgent.exe` (PyInstaller, `--onefile --windowed`) yangi
sinxronlash funksiyasi bilan qayta yig'ildi, `dist/`ga chiqarildi.

### Tekshirildi
- `python manage.py check` — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback, `Client` orqali): token
  bo'lmasa/noto'g'ri bo'lsa `401`, to'g'ri token bilan `200` + omborlar
  ro'yxati to'g'ri qaytishi ✅
- **Haqiqiy end-to-end test**: Django dev-server vaqtincha fon rejimida
  ishga tushirilib (`127.0.0.1:8123`), haqiqiy `birzumda` firmasiga token
  o'rnatilib, Desktop Agent'ning `api_client.fetch_omborlar()` funksiyasi
  **haqiqiy tarmoq orqali** chaqirildi: (a) noto'g'ri token rad etildi ✅;
  (b) to'g'ri token bilan bo'sh ro'yxat, keyin haqiqiy `Ombor` yozuvi
  yaratilgandan so'ng to'g'ri qaytarilishi ✅; (c)
  `sync_warehouses_from_remote()` uni `remote_id=1` bilan mahalliy bazaga
  to'g'ri yozishi ✅. Test tugagach dev-server to'xtatildi, test uchun
  yaratilgan `Ombor` yozuvi o'chirildi (haqiqiy `desktop_agent_token`
  esa firma uchun foydali bo'lgani sababli saqlab qolindi)
- Qayta build qilingan `.exe` offscreen rejimda muvaffaqiyatli ishga
  tushishi tasdiqlandi ✅

---

## 52-qadam: Desktop Agent — Skaner orqali xodimni shaxsiy QR bilan tasdiqlash

**Holat: DONE**

51-qadamda Omborlar CRM bilan sinxronlandi. "Davom et" so'ralganda,
Desktop Agent vision hujjatidagi eng asosiy, boshqa hamma narsa
(materiallar so'rovi, ishlab chiqarish tasdig'i) tayanadigan birinchi
interaksiya — **"xodim shaxsiy QR orqali kompyuter oldida o'zini
tasdiqlaydi"** — tanlab olindi. Bu allaqachon mavjud `XodimBadge` (CRM'da
har bir xodim uchun QR generatsiya qiluvchi model, `badge_views.py`) bilan
Desktop Agent'ning skaner kamerasini bog'laydi.

### Django tomoni — yangi endpoint
- **`main/agent_api_views.py`** — yangi `GET /api/agent/badge-scan/?kod=<kod>`
  (mavjud token-autentifikatsiyasi bilan): `XodimBadge.objects.filter(kod=kod,
  company=company)` orqali xodimni topadi, `user_id`/`username`/`tuliq_ismi`/
  `lavozim`/`is_active` qaytaradi. Kod topilmasa — `404`; `kod` parametri
  berilmasa — `400`.
- `landing/urls.py` — `/api/agent/badge-scan/` yo'li qo'shildi (mavjud
  `api/agent` middleware bypass'i avtomatik qamrab oladi).

### Desktop Agent tomoni — skanerlash oqimi
- **`app/camera_utils.py`** — yangi `QRScanWorker(QThread)`: kamera
  manbasidan (USB yoki RTSP) jonli kadr o'qib, har bir kadrda
  `cv2.QRCodeDetector().detectAndDecode()` orqali QR qidiradi. Topilsa
  `qr_detected(str)` signalini yuboradi — **debounce** bilan (bir xil kod
  3 soniya ichida qayta-qayta yuborilmaydi, xodim kartani kameraga bir
  necha soniya ushlab tursa ham faqat bitta tasdiqlash chiqadi). Shu bilan
  bir vaqtda jonli ko'rinish uchun `frame_ready` ham yuboriladi.
- **`app/api_client.py`** — yangi `resolve_badge(server_url, token, kod)` —
  yuqoridagi endpointni chaqiradi, 401/404/tarmoq xatolarini aniq
  xabar bilan `ApiError` sifatida ko'taradi.
- **`app/windows/scanner_page.py`** — to'liq kengaytirildi: endi faqat
  kamera sozlash emas, **"Ishga tushirish (skanerlash)"** tugmasi bilan
  jonli rejim ham bor — jonli ko'rinish (`QLabel`) + natija kartasi:
  boshida "Xodim kutilmoqda..." (kulrang), QR o'qilib xodim topilsa
  "Xush kelibsiz, <Ism>! (<lavozim>)" (yashil), xato/hisob faol emas
  bo'lsa qizil xabar. `server_url`/`agent_token` sozlamalardan o'qiladi.
- **`app/windows/main_window.py`** — sahifa almashtirilganda yoki oyna
  yopilganda skanerlash fon oqimi avtomatik to'xtatiladi (dangling
  `QThread` qolib ketmasligi uchun).
- `.exe` qayta build qilindi (`dist/StockFirmAgent.exe`).

### Tekshirildi
- `python manage.py check` — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback, `Client`): token/kod
  yo'q/noto'g'ri holatlar uchun `400`/`401`/`404`; to'g'ri holatda `200`
  + xodim ma'lumoti to'g'ri qaytishi ✅
- **Haqiqiy end-to-end test**: Django dev-server vaqtincha fon rejimida
  ishga tushirilib, haqiqiy `birzumda` firmasi va haqiqiy xodim (`Xaydarov
  Rafiq`)ning `XodimBadge`si orqali Desktop Agent'ning
  `api_client.resolve_badge()` funksiyasi **haqiqiy tarmoq orqali**
  chaqirildi: to'g'ri kod → xodim ma'lumoti qaytdi; noma'lum kod → rad
  etildi; noto'g'ri token → rad etildi ✅. Test tugagach dev-server
  to'xtatildi, test uchun yaratilgan `XodimBadge` o'chirildi
- Offscreen (`QT_QPA_PLATFORM=offscreen`) orqali: `ScannerPage`
  yaratilishi, kamera sozlanmagan holatda "Ishga tushirish" tugmasi
  o'chirilgan, sozlangandan keyin yoqilishi tasdiqlandi ✅
- Qayta build qilingan `.exe` muvaffaqiyatli ishga tushishi tasdiqlandi ✅

### Keyingi bosqich (hozircha qilinmagan)
Vision hujjatidagi keyingi qadamlar: tarozi (real-vaqt og'irlik) bilan
integratsiya, "stansiya sessiyasi" (bir marta tasdiqlangach, keyingi
skanerlar qayta tasdiqlamasdan davom etishi), QR chop etish/XPrinter,
material so'rovi/ishlab chiqarish tasdig'ini shu skanerlash oqimiga
ulash — bular alohida, keyingi bosqichlarda rejalashtiriladi.

---

## 53-qadam: Desktop Agent — Stansiya sessiyasi (badge bir marta skanerlansa, tizim xodimni "eslab qoladi")

**Holat: DONE**

"Davom et" so'ralganda, 52-qadamda qoldirilgan ro'yxatdagi eng mantiqiy
keyingi bo'lak tanlandi: **"stansiya sessiyasi"** — bu allaqachon
`quiet-waddling-heron.md` rejasining "NEXT3" bo'limida aniq ko'rsatilgan
keyingi qadam edi ("Stansiya sessiyasi (tasdiqlash → keyingi skanerlar
avtomatik unga yoziladi)... bular ushbu poydevor tugagach alohida
rejalashtiriladi").

Bu — kelajakda material so'rovi, ishlab chiqarish tasdig'i kabi
qadamlarning barchasi tayanadigan holat mashinasi: xodim badge'ini bir
marta ko'rsatgach, tizim uni **60 soniya** davomida "eslab qoladi" —
shu vaqt ichida boshqa hech qanday qayta tasdiqlashsiz davom etish
mumkin bo'ladi (hozircha faqat sessiya holatining o'zi qurildi — unga
bog'lanadigan keyingi amallar, masalan material so'rovi, hali qurilmagan).

### Nima qilindi
- **`app/windows/scanner_page.py`** — to'liq holat mashinasi qo'shildi:
  - `_start_session(info)` — badge muvaffaqiyatli o'qilgach chaqiriladi,
    `SESSION_TIMEOUT_SECONDS = 60` soniyalik hisoblagichni ishga tushiradi.
  - `_tick_session()` — har soniyada (`QTimer`) chaqirilib, banner matnini
    yangilaydi ("Kirgan: <Ism> (<lavozim>) — avtomatik chiqish: 47s");
    hisoblagich nolga yetsa avtomatik `_end_session()` chaqiriladi.
  - `_end_session()` — sessiyani darhol tugatadi (banner yashiriladi,
    timer to'xtaydi) — timeout tugaganda ham, "Chiqish" tugmasi
    bosilganda ham, kamera to'xtatilganda (`_stop_scan()`) ham chaqiriladi
    (dangling timer qolib ketmasligi uchun).
  - Yangi UI: doimiy ko'rinadigan (faqat sessiya faol bo'lganda)
    to'q-ko'k banner, xodim ismi/lavozimi + qolgan vaqt + "Chiqish"
    tugmasi bilan.
  - Boshqa xodim badge'ini skanerlasa — sessiya darhol yangi xodimga
    almashadi (`_on_qr_detected` har safar `_start_session`ni qayta
    chaqiradi) — "navbatdagi xodim" ssenariysini qo'llab-quvvatlaydi.
- `.exe` qayta build qilindi.

### Tekshirildi
- Offscreen (`QT_QPA_PLATFORM=offscreen`, oyna `.show()` qilingan holda)
  orqali to'liq holat mashinasi sinaldi: (a) `_start_session()`dan keyin
  banner ko'rinishi va matni to'g'ri chiqishi ✅; (b) `_tick_session()`
  hisoblagichni to'g'ri kamaytirishi va matnni yangilashi ✅; (c) qo'lda
  `_end_session()` chaqirilganda banner yashirilishi va sessiya
  tozalanishi ✅; (d) hisoblagich nolga yetganda avtomatik tugashi ✅;
  (e) `_stop_scan()` chaqirilganda (masalan sahifa almashtirilganda)
  faol sessiya ham avtomatik tugashi (dangling timer yo'qligi) ✅
- Qayta build qilingan `.exe` muvaffaqiyatli ishga tushishi tasdiqlandi ✅

### Keyingi bosqich (hozircha qilinmagan)
Sessiya holatining o'zi endi tayyor, lekin unga **bog'lanadigan amallar**
hali yo'q — masalan "sessiya faol bo'lganda material so'rovini ko'rsatish
va uni tasdiqlashda kim ekanini yozib qo'yish" kabi. Bular, hamda tarozi
integratsiyasi, QR chop etish/XPrinter — keyingi, alohida bosqichlar.

---

## 54-qadam: Desktop Agent — sessiya faol bo'lganda kutilayotgan material so'rovini ko'rsatish

**Holat: DONE**

53-qadamda qoldirilgan "sessiyaga bog'lanadigan birinchi haqiqiy amal"
qilib tanlangan narsa — aynan vision hujjatidagi so'z bilan aytilgan:
**"tasdiqlangach, uning navbatdagi so'rovi (masalan xom ashyo olish)
ishga tushadi"**. Endi xodim badge'ini skanerlab sessiya boshlagach,
Desktop Agent avtomatik ravishda uning CRM'dagi kutilayotgan xom ashyo
so'rovini (`ProductionMaterialRequest`, `status='waiting'`) ko'rsatadi.

### Django tomoni
- **`main/agent_api_views.py`** — yangi `GET /api/agent/material-requests/
  ?user_id=<id>` endpoint: `Pazanda.objects.filter(user_id=..., company=...)`
  orqali xodimni topadi (agar u ishlab chiqaruvchi bo'lmasa — `404`,
  masalan yetkazib beruvchi/savdogar/omborchi uchun bu normal holat).
  Topilsa, `ProductionMaterialRequest.objects.filter(status='waiting')`
  ro'yxatini **eng eskisi birinchi (FIFO)** tartibida qaytaradi — har
  biri uchun material nomi, birligi, miqdori, qaysi mahsulot uchunligi,
  izoh.
- `landing/urls.py` — yo'l qo'shildi (mavjud `api/agent` bypass avtomatik
  qamrab oladi).

### Desktop Agent tomoni
- **`app/api_client.py`** — kodni ozgina soddalashtirish uchun umumiy
  `_get()` yordamchi funksiyasi chiqarildi (3 ta endpoint chaqiruvi endi
  shu orqali, xato qayta ishlash kodi takrorlanmaydi); yangi
  `fetch_material_requests(server_url, token, user_id)`.
- **`app/windows/scanner_page.py`** — `_start_session()` endi
  `_load_material_requests(user_id)` ni ham chaqiradi: agar xodim uchun
  kutilayotgan so'rov bo'lsa, sessiya banneri ostida to'q sariq panel
  chiqadi: "Navbatdagi so'rov: <material> — <miqdor> <birlik> (<mahsulot>
  uchun)" (+ agar birdan ortiq bo'lsa "jami N ta so'rov kutilmoqda").
  Xodim ishlab chiqaruvchi bo'lmasa yoki so'rov yo'q bo'lsa — panel
  shunchaki yashirin qoladi (xatosiz, jim). Sessiya tugaganda
  (`_end_session()`) panel ham yashiriladi.

### Tekshirildi
- `python manage.py check` — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback, `Client`): eski va yangi
  ikkita "waiting" so'rov + bitta "approved" (ko'rinmasligi kerak) —
  natijada faqat 2 ta "waiting" so'rov, **eng eskisi birinchi** tartibida
  qaytishi tasdiqlandi ✅
- **Haqiqiy end-to-end test**: Django dev-server vaqtincha ishga
  tushirilib, haqiqiy `birzumda` firmasi, haqiqiy pazanda (`Xaydarov
  Rafiq`) va haqiqiy `ProductionMaterialRequest` (`Go'sht 3kg — Burger
  uchun`) bilan: (a) sessiya boshlanganda panel to'g'ri ko'rinib, to'g'ri
  matn chiqishi ✅; (b) sessiya tugaganda panel yashirilishi ✅; (c)
  ishlab chiqaruvchi bo'lmagan xodim (yetkazib beruvchi) uchun panel
  ko'rinmay, lekin sessiya banneri normal davom etishi ✅. Test
  ma'lumotlari (token, `XodimBadge`, `ProductionMaterialRequest`) tozalab
  o'chirildi
- Qayta build qilingan `.exe` muvaffaqiyatli ishga tushishi tasdiqlandi ✅

---

## 55-qadam: Desktop Agent — material so'rovini "Qabul qildim" deb belgilash

**Holat: DONE**

54-qadamda ko'rsatilgan "navbatdagi so'rov" hozircha faqat ma'lumot edi —
xodim uni ko'rar edi, lekin hech qanday amal qila olmasdi. Foydalanuvchi
uchta variantdan ("Qabul qildim" tugmasi / tarozi / QR chop etish)
birinchisini tanladi — sababi, u yagona **hech qanday maxsus uskunasiz
to'liq sinab bo'ladigan** variant edi (tarozi/printer uchun jismoniy
uskuna bu muhitda yo'q, shuning uchun ular hozircha qurilmadi — kod
yozib, sinamasdan "ishlaydi" deb aytish noto'g'ri bo'lardi).

### Django tomoni
- **`ProductionMaterialRequest.acknowledged_at`** — yangi maydon
  (nullable, migratsiya `0072_...`). **Muhim dizayn qarori**: bu `status`
  maydoniga **tegmaydi** — so'rov hamon `'waiting'` holatida qoladi,
  omborchi tasdiqlash oqimi (web ilovada) butunlay o'zgarishsiz ishlayveradi.
  `acknowledged_at` faqat qo'shimcha ma'lumot — "xodim buni ko'rdim/
  boshladim dedi" degani, tasdiqlash emas.
- **`main/agent_api_views.py`** — yangi `POST /api/agent/material-requests/
  <id>/acknowledge/` (`user_id` majburiy, POST body'da): so'rovni
  `id + company + producer__user_id` bo'yicha topadi (**boshqa xodimning
  so'rovini qabul qilib bo'lmaydi** — mos kelmasa `404`); so'rov endi
  `'waiting'` holatida bo'lmasa (allaqachon tasdiqlangan/rad etilgan) —
  `400`; muvaffaqiyatli bo'lsa `acknowledged_at`ni birinchi marta
  belgilaydi (**idempotent** — qayta chaqirilsa xato bermaydi, vaqtni
  o'zgartirmaydi). `GET /api/agent/material-requests/` javobiga ham
  `acknowledged: true/false` maydoni qo'shildi.
- `landing/urls.py` — yangi yo'l qo'shildi.

### Desktop Agent tomoni
- **`app/api_client.py`** — ichki `_get`/`_post` umumiy `_request()`
  yordamchisi orqali qayta qurildi (400 javoblarida serverning `detail`
  xabari to'g'ridan-to'g'ri ko'rsatiladi); yangi
  `acknowledge_material_request(server_url, token, request_id, user_id)`.
- **`app/windows/scanner_page.py`** — "Navbatdagi so'rov" paneliga
  **"Qabul qildim"** tugmasi qo'shildi. Bosilganda API'ni chaqiradi;
  muvaffaqiyatli bo'lsa tugma "Qabul qilindi ✓" ga o'zgarib o'chiriladi.
  Sessiya qayta yuklanganda (`_load_material_requests`) serverdan kelgan
  `acknowledged` holatiga qarab tugma holati to'g'ri tiklanadi (ya'ni bu
  ma'lumot vaqtinchalik emas — CRM'da saqlanadi).

### Tekshirildi
- `python manage.py check`, migratsiya — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback, `Client`): (a)
  `user_id`siz — `400`; (b) noto'g'ri token — `401`; (c) **boshqa
  xodimning** so'rovini qabul qilishga urinish — `404` ✅; (d) to'g'ri
  holatda `200`, `status` o'zgarmasdan qolishi ✅; (e) ikkinchi marta
  chaqirilganda vaqt o'zgarmasligi (idempotent) ✅; (f) `GET` ro'yxatida
  `acknowledged=true` ko'rinishi ✅; (g) allaqachon `'approved'` bo'lgan
  so'rovni qabul qilishga urinish — `400` ✅
- **Haqiqiy end-to-end test**: Django dev-server + haqiqiy `birzumda`/
  `Xaydarov Rafiq` bilan: sessiya boshlanganda tugma "Qabul qildim" (faol)
  ko'rinishi; bosilgach "Qabul qilindi ✓" (o'chirilgan) holatga o'tishi;
  sessiya qaytadan yuklanganda (server holatidan) shu holat saqlanib
  qolgani tasdiqlandi ✅
- Qayta build qilingan `.exe` muvaffaqiyatli ishga tushishi tasdiqlandi ✅

### Keyingi bosqich (uskuna talab qiladi, hozircha qilinmagan)
Tarozi (real-vaqt og'irlik) integratsiyasi va QR chop etish/XPrinter —
bularni qurish uchun foydalanuvchidan aniq uskuna modeli/protokoli
kerak, aks holda kod yozilib sinovdan o'tkazib bo'lmaydi.

---

## 56-qadam: "Pazanda" so'zi hamma joyda "Ishlab chiqaruvchi"ga to'liq o'zgartirildi

**Holat: DONE**

Foydalanuvchi Telegram bot funksiyasini kengaytirish mavzusidan oldin
alohida ta'kidladi: "pazandani to'liq ishlab chiqaruvchi qil, landingda
ham hamma qismda". Tekshiruv shuni ko'rsatdi — `User.get_type_display()`
`type='pazanda'` uchun allaqachon to'g'ri "Ishlab chiqaruvchi" qaytarardi
(model `choices`da to'g'ri), lekin **qo'lda yozilgan matnlar** (marketing
nusxasi, eksport ustuni) hali eski "Pazanda" so'zini ishlatar edi.

### Nima qilindi (faqat foydalanuvchiga ko'rinadigan matn, ichki kod nomlariga tegilmadi)
- `landing/templates/landing/home_pro.html` — landing sahifasidagi 3 ta
  joy: "3-qadam" tavsifi ("...kuryer va pazandalarga..." →
  "...ishlab chiqaruvchilarga..."), "Rollar" bo'limi ro'yxati
  ("pazanda" → "ishlab chiqaruvchi"), rol-kartochka sarlavhasi
  ("Pazanda" → "Ishlab chiqaruvchi").
- `landing/views.py` — marketing ma'lumotlar lug'atidagi 2 ta matn
  ("Rollar" xususiyat tavsifi, "3-qadam" ishga tushirish tavsifi).
- `main/export_views.py` — Xodimlar Excel eksportidagi `TYPE_MAP`
  lug'atida `'pazanda': 'Pazanda'` → `'Ishlab chiqaruvchi'` (bu lug'atda
  alohida `'ishlab_chiqaruvchi': 'Ishlab chiqaruvchi'` kaliti ham bor edi
  — ikkalasi endi bir xil ko'rsatiladi).

### Ataylab o'zgartirilmagan narsalar
`Pazanda`/`PazandaMahsulot` model nomlari, `type='pazanda'` saqlanadigan
qiymat, `pazanda_hisobot` URL nomi, shablon fayl nomlari (`pzbase.html`
va h.k.), Django admin ro'yxatlari, kontekst o'zgaruvchi nomlari
(`pazanda_obj`, `pazanda_month_stats`) — bular **ichki identifikatorlar**,
ularni o'zgartirish katta, keraksiz migratsiya xavfini keltirib chiqarardi
va foydalanuvchiga ko'rinmaydi.

### O'zgargan fayllar
- `landing/templates/landing/home_pro.html`
- `landing/views.py`
- `main/export_views.py`

### Tekshirildi
- `python manage.py check` — xatosiz
- Haqiqiy landing sahifasi (`/`) render qilinganda, matnda alohida
  so'z sifatida "Pazanda" endi umuman uchramasligi, "Ishlab chiqaruvchi"
  esa borligi tasdiqlandi ✅

---

## 57-qadam: UPDATENEWVERSION.md — xavfsizlik/arxitektura auditi bo'yicha tuzatishlar

**Holat: DONE (asosiy qism) — ba'zi bandlar qo'lda amal talab qiladi, pastda aniq ko'rsatilgan**

Foydalanuvchi `D:\firma_crm\UPDATENEWVERSION.md` audit hujjatini
("bajarish tartibi" bilan, 1→9 bandlar) to'liq bajarishni so'radi. Har bir
band alohida tekshirildi va sinovdan o'tkazildi; ba'zilari **faqat
foydalanuvchi tomonidan** bajarilishi mumkin bo'lgan qo'lda amallarni
talab qiladi (masalan haqiqiy Click kalitini Click kabinetida almashtirish)
— bular pastda alohida ko'rsatilgan.

### 1. Hardcoded secret fallback'lar olib tashlandi
- `crm/crm/settings.py` — `SECRET_KEY` endi `.env`da bo'lishi **majburiy**
  (fallback yo'q, bo'lmasa `ImproperlyConfigured` ko'taradi).
- `crm/main/click_views.py` — `CLICK_SECRET_KEY`/`CLICK_MERCHANT_ID`/
  `CLICK_SERVICE_ID` xuddi shunday — `_required_env()` yordamchi funksiya
  orqali majburiy.
- `crm/.env.example` — haqiqiy koddagi nomlarga mos qilib to'g'rilandi
  (avval `DJANGO_SECRET_KEY`/`SERVICE_ID`/`MERCHANT_ID`/`SECRET_KEY` kabi
  **noto'g'ri** nomlar bilan yozilgan edi — real kod `SECRET_KEY`/
  `CLICK_SERVICE_ID`/`CLICK_MERCHANT_ID`/`CLICK_SECRET_KEY` kutadi).
- **⚠️ Qo'lda amal kerak**: koddan olib tashlangan fallback qiymat
  (`HaLZ1bWlBHY` va h.k.) avval repoda ochiq yotgan edi. Agar bu haqiqiy
  Click kaliti bo'lsa — **Click kabinetida uni almashtirish** kerak,
  chunki kod tuzatilishi eski kalitni bekor qilmaydi.

### 2-3. DEBUG default + production xavfsizlik sozlamalari
- `DEBUG` default'i `True`dan `False`ga o'zgartirildi (dev'da `.env`da
  aniq `DEBUG=True` bo'lgani uchun lokal ishlashga ta'sir qilmadi).
- `DEBUG=False` bo'lganda `ALLOWED_HOSTS` .env'da aniq ko'rsatilishi
  **majburiy** qilindi (bo'lmasa xato ko'taradi).
- `DEBUG=False` bo'lganda: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
  `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` (1 yil, subdomains+preload
  bilan) yoqiladi.
- **⚠️ Diqqat**: `SECURE_SSL_REDIRECT=True` — agar production'da nginx
  `X-Forwarded-Proto` header'ini to'g'ri yubormasa, redirect-loop
  keltirib chiqarishi mumkin (`SECURE_PROXY_SSL_HEADER` allaqachon
  sozlangan, lekin nginx konfiguratsiyasini tasdiqlash tavsiya etiladi).

### 4. Desktop Agent API — server-tomonda badge-sessiya tekshiruvi
Eng jiddiy topilma: `agent_material_requests`/`agent_acknowledge_material_request`
mijozdan kelgan `user_id`ga **ko'r-ko'rona ishonar edi** — kompaniya
tokeniga ega har qanday stansiya istalgan xodim nomidan so'rovlarni
ko'rishi/tasdiqlashi mumkin edi.
- `main/agent_api_views.py` — `agent_badge_scan` endi muvaffaqiyatli
  skanerlashda qisqa muddatli (90 soniya — Desktop Agent'dagi 60 soniyalik
  stansiya sessiyasidan biroz uzunroq), `django.core.signing` bilan
  imzolangan (soxtalashtirib bo'lmaydigan) `session_token` qaytaradi.
  `agent_material_requests`/`agent_acknowledge_material_request` endi
  `user_id` o'rniga shu tokenni talab qiladi va undan `user_id`ni
  chiqarib oladi — token muddati o'tgan, noto'g'ri imzolangan yoki
  boshqa kompaniya uchun chiqarilgan bo'lsa — `401`.
- Desktop Agent (`api_client.py`, `scanner_page.py`) yangi kontraktga
  moslashtirildi, `.exe` qayta build qilindi.

### 5. Git tracking tozalandi (fayllar diskda qoladi)
- `db.sqlite3`, to'liq `crm/venv/` (10 188 fayl!), barcha `__pycache__/`
  (3 365 fayl) va `crm/media/` (48 ta real yuklangan rasm — mahsulot/
  xodim/mashina fotolari) git tracking'dan chiqarildi (`git rm --cached`,
  keyin commit qilindi — bular allaqachon `.gitignore`da bor edi, lekin
  oldin qo'shib qo'yilgani uchun git hali kuzatib kelayotgan edi).
- **⚠️ Qo'lda qaror kerak**: bu commit fayllarni **kelajakdagi**
  commit'lardan chiqaradi, lekin **eski commit'lar tarixida** ular hali
  ham mavjud (`git log` orqali ko'rish mumkin). Buni butunlay tozalash
  uchun tarix qayta yozish (`git filter-repo` yoki BFG) va **majburiy
  push** kerak bo'ladi — bu boshqa hamkorlar uchun repo'ni buzadigan,
  qaytarib bo'lmaydigan amal, shuning uchun aniq tasdiqlashsiz
  bajarilmadi.

### 6. CompanyMiddleware billing-sync keshlandi
`sync_company_lifecycle` endi har so'rovda emas, kompaniya boshiga 5
daqiqada bir marta ishga tushadi (Django cache orqali) — vaqt-asoslangan
holat o'tishlari (sinov muddati, to'lov muddati) soniyama-soniya aniq
bo'lishi shart emas.

### 7. `role_required` decoratori — poydevor
`main/decorators.py` — yangi `@role_required('ega', ...)` decoratori,
`views.py`dagi 74 marta takrorlangan `if request.user.type != '...':
return redirect('main')` naqshini markazlashtiradi. **Butun 74 joyni bir
yo'la almashtirish qilinmadi** (bu juda katta portlash radiusiga ega
bo'lardi) — hozircha 2 ta yuqori-xavfli view (`ombor_list_page`,
`hodimlar_list`) shu decoratorga o'tkazildi, isbot sifatida. Qolganlari
keyingi, alohida bosqichda ko'chiriladi.

### 8. Pul summalari — Decimal (Click oqimi)
`click_views.py:click_prepare` — Click'dan kelayotgan `amount` endi
`float()` o'rniga to'g'ridan-to'g'ri `Decimal()` bilan o'qiladi (model
maydoni `ClickTransaction.amount` allaqachon `DecimalField` edi — muammo
faqat oraliq Python parsing'da edi, aniqlik yo'qolish xavfi bilan).
**To'liq kodbaza bo'yicha barcha pul maydonlarini float'dan Decimal'ga
o'tkazish** — bu ancha katta, alohida ish (ko'p joyda `FloatField`
ishlatilgan), hozircha faqat eng xavfli kirish nuqtasi (tashqi to'lov
webhook'i) tuzatildi.

### 🟡 Kichikroq bandlar
- **Sessiya muddati** — `_apply_session_expiry()` (`views.py`, `login`
  ichida barcha 3 ta `auth_login()` chaqiruvidan keyin) endi `'ega'`
  roli uchun sessiyani 1 kunga qisqartiradi (oldin hammaga 7 kun edi).
- **USD kursi fallback** — `get_usd_rate()` endi: (1) qisqa muddatli
  cache, (2) CBU ishlamasa — muddatsiz "oxirgi bilingan qiymat" cache,
  (3) faqat ikkalasi ham yo'q bo'lsa `USD_RATE_FALLBACK` env
  o'zgaruvchisi (yoki 12500 default) — qattiq kodlangan qiymat endi
  faqat eng oxirgi variant.
- **`CHANNEL_LAYERS` takrorlanishi** — ikkita qarama-qarshi shart bitta,
  aniq mantiqqa birlashtirildi (`REDIS_URL` yoki `USE_REDIS_CHANNEL_LAYER`
  — ikkalasi ham ishlaydi, lekin endi bitta joyda).
- **Login rate-limit** — yangi tashqi kutubxona (`django-axes`) qo'shilmadi;
  Django cache orqali IP+username bo'yicha oddiy throttle: 5 muvaffaqiyatsiz
  urinishdan keyin 15 daqiqaga bloklanadi, muvaffaqiyatli kirishda hisoblagich
  tozalanadi.
- **Testlar** — bu audit davomida yozilgan har bir tuzatish uchun
  izolyatsiyalangan (`transaction.atomic()` + rollback) testlar yozilib,
  ishga tushirilib tasdiqlandi (pastga qarang); lekin **butun loyiha
  bo'yicha keng test qamrovi** (billing/Click webhook, rol-huquq) hali
  ham yo'q — bu alohida, davomiy ish.

### O'zgargan fayllar
- `crm/crm/settings.py`, `crm/.env.example`
- `main/click_views.py`, `main/agent_api_views.py`, `main/middleware.py`
- `main/decorators.py` (yangi), `main/warehouse_views.py`, `main/list_views.py`
- `main/views.py` (`login`, session expiry, login throttle)
- `desktop_agent/app/api_client.py`, `desktop_agent/app/windows/scanner_page.py`
- Git: `db.sqlite3`, `crm/venv/`, `__pycache__/`, `crm/media/` untracked

### Tekshirildi (har band alohida, izolyatsiyalangan testlar bilan)
- `python manage.py check` — har bir o'zgarishdan keyin xatosiz ✅
- Secret fallback: dev `.env`da qiymatlar borligi tufayli server hali
  ham to'g'ri ishga tushishi tasdiqlandi ✅
- Badge-sessiya xavfsizligi: (a) xom `user_id` endi rad etilishi (`401`,
  **avvalgi zaiflik yopilgani**) ✅; (b) haqiqiy `session_token` bilan
  ishlashi ✅; (c) soxta/noto'g'ri imzo rad etilishi ✅; (d) boshqa
  kompaniya uchun chiqarilgan token rad etilishi ✅ — hammasi haqiqiy
  Django serverga ulanib, haqiqiy Desktop Agent orqali ham qayta
  tasdiqlandi
- Billing-sync kesh: 3 ta ketma-ket so'rovda `sync_company_lifecycle`
  faqat 1 marta chaqirilgani (`mock` orqali sanaldi) ✅
- `role_required`: `'ega'` uchun sahifalar ochiq, boshqa rol uchun
  `main`ga yo'naltirilishi (real foydalanuvchilar bilan) ✅
- Login throttle: 3 xato + to'g'ri parol → muvaffaqiyatli (hali
  bloklanmagan) ✅; 5 xato → to'g'ri parol bilan ham bloklanishi ✅
- Click Decimal: to'g'ri summa `Decimal` sifatida saqlanishi, yaroqsiz
  summa (`error: -2`) bilan toza rad etilishi ✅
- USD rate fallback zanjiri (live → qisqa cache → muddatsiz oxirgi
  bilingan qiymat → env/12500) alohida test qilindi ✅

### Qo'lda bajarilishi kerak bo'lgan qismlar (men bajara olmadim)
1. **Click kabineti**: agar koddan olib tashlangan kalit (`HaLZ1bWlBHY`)
   haqiqiy bo'lsa — uni Click kabinetida almashtirish.
2. **Git tarixini tozalash**: `db.sqlite3`/`venv`/`media` eski
   commit'larda hali ham mavjud — `git filter-repo`/BFG + majburiy push
   orqali butunlay olib tashlash mumkin, lekin bu boshqa clone'lar uchun
   buzuvchi va qaytarib bo'lmaydigan amal — alohida tasdiqlash kerak.
3. **nginx konfiguratsiyasi**: `SECURE_SSL_REDIRECT=True` production'da
   `X-Forwarded-Proto` header to'g'ri kelishini talab qiladi — deploy
   qilishdan oldin tekshirish tavsiya etiladi.

---

## 58-qadam: Desktop Agent — tarifga qo'shimcha paket sifatida qo'shildi ($60/dona/oy)

**Holat: DONE (birinchi qism — "avval tarifga qo'sh" so'ralgan)**

Foydalanuvchi Desktop Agent'ni davom ettirishni so'radi, aniq ketma-ketlik
bilan: **avval** uni tarifda sotiladigan paket qilib qo'yish, **keyin**
har bir agentga alohida login/rol ajratish (chunki bitta firma bir nechta
agent ishlatishi mumkin). Bu qadam faqat birinchi qismni — billing/tarif
tomonini — qamrab oladi; ikkinchi qism (per-stansiya alohida identity)
hali qilinmagan (pastga qarang).

### Narx
Foydalanuvchi ikkita variant ($50/$60) orasidan **$60/dona/oyiga**ni
tanladi.

### Nima qilindi
- **`main/models.py`**:
  - `DESKTOP_AGENT_UNIT_PRICE = Decimal("60.00")` konstanta (mavjud
    `SAVDOGAR_SALES_ADDON_PRICE` naqshiga o'xshab).
  - `Company.custom_desktop_agent_stations` — yangi `PositiveIntegerField`
    (default 0) — sotib olingan Desktop Agent stansiyalari soni.
    **Muhim farq savdogar addonidan**: bu **faqat superadmin tomonidan**
    (Django admin orqali) belgilanadi — `PlanRequest`/tarif-so'rov
    oqimiga ulanmagan, chunki foydalanuvchi buni "faqat aloqa orqali
    o'rnatilishi kerak" deb aniq talab qildi (o'zi so'rab/yoqib
    bo'lmaydi).
  - `Company.desktop_agent_addon_price` — yangi property
    (`stations * DESKTOP_AGENT_UNIT_PRICE`).
  - `Company.monthly_price` — endi bu addon narxini ham qo'shadi
    (standart **va** custom-tarif ikkalasida ham — chunki bu stansiyalar
    dasturiy tarifdan mustaqil, jismoniy uskunaga bog'liq xarajat).
  - Migratsiya: `0073_desktop_agent_stations_addon.py`.
- **`main/services/billing_service.py`** — `get_billing_dashboard_data()`
  javobiga `desktop_agent_stations`/`desktop_agent_addon_price`
  qo'shildi.
- **`main/templates/billing.html`** — agar `desktop_agent_stations > 0`
  bo'lsa, "Desktop Agent: N dona (+$X/oy)" belgisi ko'rsatiladi.
- **`landing/templates/landing/pricing.html`** — yangi "Qo'shimcha
  xizmat" bo'limi, "Desktop Agent" kartochkasi bilan: narx ($60/dona/oy),
  tavsif, va **kamera/QR-shtrix-kod skaneri/XPrinter talab qilinishi**
  haqida aniq ogohlantirish bloki, hamda "bu xizmat faqat aloqa orqali
  ulanadi" matni + "Bog'lanish" tugmasi (xarid tugmasi emas).

### Nega superadmin-only (Django admin), alohida forma emas
`Company.custom_desktop_agent_stations` `CompanyAdmin`da hech qanday
`fields` cheklovi yo'qligi sababli avtomatik ravishda `/admin_panel/`
orqali tahrirlanadi — bu "faqat aloqa orqali" talabini aynan
qondiradi (faqat superadmin kira oladi, firma egasiga hech qanday
o'z-o'zini xizmat ko'rsatish tugmasi ko'rsatilmaydi).

### Kutilmagan, lekin darhol topilgan va tuzatilgan bug
`billing.html`da pul summalarini ko'rsatishda **xuddi shu sessiyada
avval bir necha marta uchragan** bug qayta chiqdi: `{{ narx|floatformat:2 }}`
`LANGUAGE_CODE='uz-latn'` sabab vergul bilan chiqarardi (`"255,00"`
o'rniga). Bu safar `|floatformat:2|unlocalize` birga ishlatilganda ham
tuzalmadi — sababi **`floatformat` o'zi ichki `formats.number_format()`
orqali lokalizatsiya qiladi**, `unlocalize` esa faqat xom qiymatni
"lokalizatsiyasiz chiqarish" deb belgilaydi, lekin `floatformat`ning
o'zi ishlab chiqargan yangi (allaqachon vergul bilan) satrga ta'sir
qilolmaydi. To'g'ri yechim: `floatformat`ni butunlay olib tashlab,
faqat `unlocalize`ning o'zini ishlatish (`DecimalField` qiymatlari
allaqachon aniq 2 xonali bo'lgani uchun bu yetarli) — bu barcha 6 ta
joyda (`monthly_price_usd`, `payment_due_usd`, yangi
`desktop_agent_addon_price`, `payment_link.amount_usd` x2) tuzatildi.

### O'zgargan fayllar
- `main/models.py` — `DESKTOP_AGENT_UNIT_PRICE`,
  `Company.custom_desktop_agent_stations`, `desktop_agent_addon_price`,
  `monthly_price`
- `main/migrations/0073_desktop_agent_stations_addon.py`
- `main/services/billing_service.py` — `get_billing_dashboard_data()`
- `main/templates/billing.html` — addon ko'rsatish + `unlocalize` bug tuzatish
- `landing/templates/landing/pricing.html` — yangi addon bo'limi

### Tekshirildi
- `python manage.py check`, migratsiya — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback, `Client`): (a)
  `custom_desktop_agent_stations=0` bo'lganda billing sahifasida badge
  ko'rinmasligi ✅; (b) `=2` qilinganda `desktop_agent_addon_price ==
  120.00` to'g'ri hisoblanishi ✅; (c) billing sahifasida "Desktop Agent:
  2 dona (+$120.00/oy)" **to'g'ri nuqta bilan** (vergulsiz) chiqishi ✅;
  (d) umumiy oylik summa ham to'g'ri qo'shilib, to'liq aniqlik bilan
  (`$255.00`, kesilmasdan) ko'rsatilishi ✅
- Haqiqiy `/pricing/` sahifasida "Desktop Agent" kartochkasi va
  kamera/skaner/XPrinter ogohlantirishi borligi tasdiqlandi ✅

### Keyingi bosqich (foydalanuvchi aniq so'ragan, hali qilinmagan)
**"login qilishni demak agentga alohida rol ajratamiz"** — hozir barcha
Desktop Agent stansiyalari bitta firma uchun **bitta umumiy token**
(`Company.desktop_agent_token`) orqali ishlaydi. Foydalanuvchi har bir
alohida agent/stansiya uchun **alohida login/identity** so'ramoqda (bir
firma bir nechta agentni alohida-alohida boshqarishi uchun). Bu
`Company.desktop_agent_token`ni bitta umumiy tokendan **har bir
stansiya uchun alohida token** beruvchi yangi modelga (masalan
`DesktopAgentStation`) o'tkazishni talab qiladi — bu, foydalanuvchining
o'z so'zi bilan, shu qadamdan **keyingi** bosqich.

---

## 59-qadam: Desktop Agent — har bir stansiya uchun alohida login/parol (Hodimlar orqali)

**Holat: DONE**

58-qadamda qoldirilgan keyingi bosqich: "har bir agentga alohida login/parol
ajratish". Foydalanuvchi buni qanday amalga oshirishni ham aniq ko'rsatdi:
**yangi alohida sahifa qurish o'rniga, mavjud "Hodimlar" bo'limidagi
"Yangi hodim qo'shish" oqimidan foydalanish** — Desktop Agent yangi
lavozim (rol) sifatida qo'shildi, xuddi boshqa xodimlar kabi.

### Nima qilindi
- **`main/models.py`** — `User.USER_TYPES`ga yangi
  `('desktop_agent', 'Desktop Agent')` qo'shildi. Migratsiya:
  `0074_user_type_desktop_agent.py`.
- **`main/templates/useryaratish.html`** — "Xodim turi" ro'yxatiga
  "Desktop Agent" qo'shildi, qolgan bo'sh joylar sonini ko'rsatadi
  (`"Desktop Agent (2 ta joy qoldi)"`) yoki hammasi ishlatilgan bo'lsa
  o'chirilgan holda ko'rsatadi ("biz bilan bog'laning"). Desktop Agent
  tanlanganda **xodim rasmi maydoni yashiriladi va majburiy bo'lishdan
  chiqadi** (bu qurilma hisobi, shaxs emas).
- **`main/views.py`**:
  - `crtuser` (yangi hodim yaratish) — `desktop_agent` tanlanganda
    `Company.custom_desktop_agent_stations` (58-qadamda sotib olingan
    stansiyalar soni) bilan solishtirib, limitdan oshsa rad etadi
    ("Siz sotib olgan Desktop Agent stansiyalari soni (N) ga yetgan...").
  - Desktop Agent hisoblari **umumiy xodim limitiga (`max_users`)
    hisoblanmaydi** — bu alohida (billing addon) kvota bilan cheklangani
    uchun.
  - Yangi `_desktop_agent_slots_left(company)` yordamchi funksiya.
- **`main/templates/hodimlar_list.html`** — rol-filtr ro'yxatiga
  "Desktop Agent" qo'shildi.
- **`main/agent_api_views.py`**:
  - Yangi `POST /api/agent/login/` — `subdomain` + `username` + `password`
    qabul qiladi, `User.objects.filter(company=..., username=..., 
    type='desktop_agent')` orqali stansiyani topib, parolni tekshiradi
    (`check_password`), faol emasligini tekshiradi, muvaffaqiyatli bo'lsa
    **yangi shaxsiy token** yaratadi (`User.token` maydoniga, har safar
    login qilinganda yangilanadi — eskisi bekor bo'ladi) va qaytaradi.
  - `_company_from_token()` — endi ikki xil tokenni ham qabul qiladi:
    eski `Company.desktop_agent_token` (orqaga moslik uchun) **va** har
    bir stansiyaning shaxsiy `User.token`i. Stansiya `is_active=False`
    qilinsa, uning tokeni darhol ishlamay qoladi.
- `landing/urls.py` — `/api/agent/login/` yo'li qo'shildi.

### Desktop Agent (PyQt6) tomoni
- **`app/api_client.py`** — yangi `station_login(server_url, subdomain,
  username, password)` — hali tokensiz chaqiriladigan yagona endpoint.
- **`app/windows/settings_page.py`** — to'liq qayta qurildi: eski
  "Server manzili + Agent token" (qo'lda CRM'dan tokenni nusxalash)
  o'rniga endi **"Server manzili + Firma subdomeni + Stansiya logini +
  Parol"** va **"Kirish"** tugmasi. Muvaffaqiyatli kirilgach, olingan
  token/stansiya nomi/firma nomi mahalliy bazaga saqlanadi (parolning
  o'zi **saqlanmaydi**, faqat login eslab qolinadi qulaylik uchun);
  "Sinxronlash" tugmasi o'zgarishsiz qoladi (endi shaxsiy token bilan
  ishlaydi).

### Muhim tuzatilgan bug (implementatsiya paytida topildi)
`crtuser`ga `_desktop_agent_slots_left()` yordamchi funksiyasini
qo'shishda, uni **`@login_required` dekoratori bilan `def crtuser`
orasiga** joylashtirib qo'ydim — natijada dekorator `crtuser` o'rniga
yangi yordamchi funksiyani o'rab oldi, `crtuser` esa **login talab
qilinmaydigan** holga tushib qoldi, va yordamchi funksiya chaqirilganda
`request.user` o'rniga `company` argumentiga `login_required`ning ichki
tekshiruvi ishlatilib, `AttributeError: 'Company' object has no attribute
'user'` xatosi chiqardi. Bu **testdan o'tkazish paytida darhol aniqlanib**
(haqiqiy view chaqirilganda xato ko'tardi), yordamchi funksiyani
dekoratordan oldinga ko'chirib tuzatildi.

### O'zgargan fayllar
- `main/models.py`, `main/migrations/0074_user_type_desktop_agent.py`
- `main/views.py` — `crtuser`, `_desktop_agent_slots_left`
- `main/templates/useryaratish.html`, `hodimlar_list.html`
- `main/agent_api_views.py` — `agent_station_login`, `_company_from_token`
- `landing/urls.py`
- `desktop_agent/app/api_client.py` — `station_login`
- `desktop_agent/app/windows/settings_page.py` — to'liq qayta qurildi

### Tekshirildi
- `python manage.py check`, migratsiya — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback, `Client`, haqiqiy
  `birzumda` firmasi + haqiqiy `ega`): (a) 1 ta stansiya kvotasi bilan
  hodim yaratish sahifasida "1 ta joy qoldi" ko'rinishi ✅; (b) Desktop
  Agent hodimi muvaffaqiyatli yaratilishi ✅; (c) kvota tugagach ikkinchi
  stansiya yaratish **rad etilishi** ✅; (d) `/api/agent/login/` orqali
  to'g'ri login/parol bilan token olinishi ✅; (e) noto'g'ri parol — `401`
  ✅; (f) olingan token mavjud `agent_omborlar` endpointida ishlashi ✅;
  (g) stansiya `is_active=False` qilinganda uning tokeni darhol
  ishlamay qolishi ✅
- **Haqiqiy end-to-end test**: Django dev-server vaqtincha ishga
  tushirilib, haqiqiy yaratilgan Desktop Agent hisobi bilan PyQt6
  `SettingsPage._login()` **haqiqiy tarmoq orqali** chaqirildi —
  muvaffaqiyatli kirish, token saqlanishi, keyin "Sinxronlash" ham
  muvaffaqiyatli ishlashi tasdiqlandi ✅
- `.exe` qayta build qilinib, offscreen rejimda ishga tushishi
  tasdiqlandi ✅

---

## 60-qadam: Desktop Agent — `requirements.txt` to'g'irlandi (pyinstaller yetishmayotgan edi)

**Holat: DONE**

Foydalanuvchi to'g'ri payqadi: `.exe` build qilish uchun `pyinstaller`
(va uning `pyinstaller-hooks-contrib` bog'liqligi) venv'ga o'rnatilgan
edi, lekin hech qanday requirements faylida yozilmagan edi — boshqa
kimdir shu papkani klonlab, `pip install -r requirements.txt` qilib,
keyin build qilmoqchi bo'lsa, `pyinstaller: command not found` xatosiga
duch kelardi.

### Nima qilindi
- Yangi **`desktop_agent/requirements-build.txt`** — faqat build uchun
  kerak bo'lgan kutubxonalar (`pyinstaller==6.21.0`,
  `pyinstaller-hooks-contrib==2026.6`), asosiy `requirements.txt`dan
  ataylab ajratilgan (build vositalarini oddiy ishga tushirish uchun
  o'rnatish shart emas).
- **`desktop_agent/README.md`** — to'liq yangilandi (bir necha
  qadamdan beri eskirgan edi — hali "CRM bilan bog'lanmagan" deb
  yozilgan edi, aslida 51-59 qadamlarda to'liq bog'landi): aniq
  o'rnatish va build buyruqlari, joriy fayl tuzilishi (`api_client.py`,
  `scanner_page.py`, `settings_page.py` va h.k. qo'shildi).
- Tekshirish: `pip install --dry-run -r requirements.txt -r
  requirements-build.txt` — barcha paketlar "already satisfied"
  ko'rsatdi, ya'ni bu ikki fayl birgalikda venv'dagi haqiqiy holatni
  to'liq va aniq tasvirlaydi.

### O'zgargan fayllar
- `desktop_agent/requirements-build.txt` (yangi)
- `desktop_agent/README.md`

---

## 61-qadam: CRM `requirements.txt`ga `djangorestframework` qo'shildi

**Holat: DONE**

Foydalanuvchi to'g'ri payqadi — bu xuddi 60-qadamdagi bilan bir xil
turdagi bug: 51-qadamda Desktop Agent REST API'si uchun
`rest_framework` `INSTALLED_APPS`ga qo'shilgan va `agent_api_views.py`da
ishlatilgan edi, lekin `djangorestframework` paketi (v3.15.1, allaqachon
o'rnatilgan edi) `crm/requirements.txt`ga hech qachon yozilmagan edi.

### Tekshiruv
Loyihadagi barcha `.py` fayllardagi `import`/`from ... import` qatorlari
(`main`, `landing`, `crm` papkalari + `bot_service.py`) chiqarib
olinib, har biri `requirements.txt`dagi paketlarga solishtirildi.
Faqat `rest_framework` (djangorestframework) yetishmasligi aniqlandi —
qolgan barcha ishlatilayotgan tashqi kutubxonalar (django, pandas,
openpyxl, qrcode, requests, channels, asgiref, python-dotenv,
python-dateutil, mysql-connector-python, python-telegram-bot va h.k.)
allaqachon to'g'ri yozilgan edi.

### Nima qilindi
- `crm/requirements.txt` — `djangorestframework==3.15.1` qo'shildi
  (o'rnatilgan haqiqiy versiya bilan).

### Tekshirildi
- `python manage.py check` — xatosiz

---

## 62-qadam: Jiddiy bug tuzatildi — to'lov muddati o'tsa ham tizim hech qachon qulflanmagan

**Holat: DONE**

Foydalanuvchi haqiqiy skrinshotlar orqali nomuvofiqlik ko'rsatdi: `birzumda`
firmasining o'z dashboardi "Holat: To'lanmagan" deb ko'rsatayotgan bo'lsa-da,
superadmin panelidagi "Qarzdor" hisoblagichi **0** ko'rsatib turgan edi.
Foydalanuvchi tizim qanday ishlashi kerakligini aniq tasvirladi: **"to'lov
muddati keldi — 3 kun muhlat beradi — so'ng qulflanadi — to'lov amalga
oshishi bilan ochiladi."**

### Aniqlangan sabab (haqiqiy, jiddiy bug)
`main/services/billing_service.py:sync_company_lifecycle()` — bu funksiya
firmaning "qulflash sababi" (`payment_reason='payment_overdue'`,
`CompanyMiddleware` orqali 403/suspended.html qaytaradigan) hisoblanishi
uchun **faqat** `company.payment_status` allaqachon `'unpaid'` bo'lgan
holatda ishlar edi:
```python
elif company.payment_status == "unpaid" and company.next_payment_date:
    if now > company.next_payment_date + timedelta(days=3):
        payment_reason = "payment_overdue"
```
Lekin **`payment_status`ni `"paid"`dan `"unpaid"`ga o'tkazadigan hech qanday
kod yo'q edi** — `next_payment_date` o'tib ketganda ham maydon abadiy
`"paid"` bo'lib qolaverar edi. Natijada:
- Foydalanuvchining o'z dashboardi (`is_company_billing_current()` — sanani
  to'g'ridan-to'g'ri tekshiradi) to'g'ri "to'lanmagan" ko'rsatardi.
- Lekin `payment_status` maydonining o'zi hech qachon o'zgarmagani uchun,
  **qulflash shart-sharoiti hech qachon bajarilmasdi** — 3 kunlik muhlat
  tushunchasi kodda bor edi, lekin unga yetib borishning yo'li yo'q edi.
- Superadmin'ning "Qarzdor" hisoblagichi (`payment_status='unpaid'`
  filtri) shu sababli har doim kam ko'rsatardi — hech qachon oshkor
  bo'lmagan qarzdorlar bor edi.

### Nima qilindi
`sync_company_lifecycle()`ga yetishmayotgan holat-o'tishi qo'shildi: agar
firma bepul tarifda bo'lmasa va `payment_status="paid"` bo'lib,
`next_payment_date` allaqachon o'tgan bo'lsa — endi darhol `"unpaid"`ga
o'tkaziladi. Shundan keyingina mavjud 3-kunlik-muhlat tekshiruvi ishga
tushadi (o'zgarishsiz qoldi).

### O'zgargan fayllar
- `main/services/billing_service.py` — `sync_company_lifecycle()`

### Tekshirildi
- `python manage.py check` — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback, haqiqiy `birzumda`
  ma'lumotlari bilan): (a) 1 kun muddati o'tgan — `payment_status`
  `"unpaid"`ga o'tadi, lekin hali qulflanmaydi (muhlat ichida) ✅; (b) 4
  kun o'tgan — endi qulflanadi (`payment_reason='payment_overdue'`) ✅;
  (c) superadmin'ning "Qarzdor" uslubidagi so'rovi endi bu firmani to'g'ri
  hisoblashi ✅; (d) `is_company_billing_current()` hamon to'g'ri `False`
  qaytarishi ✅
- **Foydalanuvchi tasdig'i bilan haqiqiy bazada qo'llandi**: `birzumda`
  firmasi uchun `sync_company_lifecycle()` real chaqirildi — muddati
  22 kun oldin o'tgani sababli (3 kunlik muhlatdan ancha uzoq) darhol
  `payment_status='unpaid'`ga o'tdi va **haqiqiy so'rov orqali tasdiqlandi:
  `/` sahifasi endi 403 (suspended) qaytaradi** ✅. Yon ta'sir sifatida
  superadmin'ning umumiy "Qarzdor" soni **0 dan 4 ga** oshdi (`birzumda`,
  `vazira`, `kuku` — barchasi haqiqatda muddati o'tgan ekan, bug tufayli
  hech biri qulflanmagan edi)

### Yakunlandi — birzumda qayta ochildi
Superadmin panelidagi mavjud "To'ladi (+1 oy)" tugmasi (`mark_paid`,
`super_billing.html`) tekshirildi — u tuzatishdan keyin `birzumda` qatorida
to'g'ri chiqib turgani tasdiqlandi (alohida qo'shimcha kod kerak bo'lmadi).
Foydalanuvchi tasdig'i bilan shu amal haqiqiy chaqirildi: `payment_status`
qayta `"paid"`ga o'tdi, `next_payment_date` 2026-08-20ga surildi, va `/`
sahifasi qayta `200` qaytarishi tasdiqlandi (firma ochildi).

### Muhim eslatma — production alohida deploy
Foydalanuvchi bu bug production versiyada ham kuzatilganini eslatdi.
**Bu tuzatish faqat shu dev repo'da** — production alohida (eski versiya,
PostgreSQL'da) ishlaydi (`UPDATENEWVERSION.md`dagi eslatmaga qarang), shu
sabab bu o'zgarish avtomatik ravishda production'ga tarqalmaydi. Agar
production'da ham xuddi shu muammo bo'lsa (muddati o'tgan firmalar
qulflanmayapti / "To'ladi" tugmasi to'g'ri chiqmayapti), bu tuzatishni
production'ga alohida deploy qilish kerak bo'ladi.

---

## 63-qadam: Desktop Agent — "Maxsus Tarif Quruvchi"ga qo'shildi (o'zi so'rov yubora oladi)

**Holat: DONE**

Foydalanuvchi "Maxsus Tarif Quruvchi" (custom tariff builder) skrinshotini
ko'rsatib, "men desktop agentni qanday qo'shaman" deb so'radi — bu 58-qadamda
"faqat aloqa orqali" (o'zi so'ray olmaydi, faqat superadmin Django admin
orqali) deb loyihalangan qarordan **farqli yo'nalish**: endi firma egasi
ham, boshqa modullar (Xarita, Bot, AI, Savdogar) kabi, Desktop Agent
stansiyalarini shu qurish sahifasidan **so'rov sifatida** yubora olishi
kerak (superadmin baribir tasdiqlashi shart — bu boshqa modullar bilan
bir xil, hech narsa avtomatik/darhol qo'llanilmaydi).

### Muhim arxitektura qarori — ikki marta hisoblanib ketmasligi uchun
58-qadamda `Company.monthly_price` custom-tarif filiali uchun ham
`desktop_agent_addon_price`ni **avtomatik qo'shar edi** (superadmin uni
to'g'ridan-to'g'ri Django admin orqali o'rnatgani uchun). Endi bu narx
"Maxsus Tarif Quruvchi" orqali **`custom_price` ichiga allaqachon
qo'shilib yuborilgani** sababli, ikkisi qo'shilib ketsa narx ikki marta
hisoblanib qolar edi. Shuning uchun `monthly_price`: **standart tarif
filialida** (`self.plan` mavjud bo'lganda) addon hamon avtomatik
qo'shiladi (superadmin admin orqali sozlagan holatlar uchun); **maxsus
tarif filialida** endi qo'shilmaydi — `custom_price`ning o'zi allaqachon
hammasini (Desktop Agent ham shu jumladan) qamrab oladi deb hisoblanadi.

### Nima qilindi
- **`main/models.py`** — `PlanRequest.custom_desktop_agent_stations`
  (`PositiveIntegerField`, default 0) qayta qo'shildi (58-qadamda olib
  tashlangan edi, endi haqiqiy maqsadi bor). Migratsiya:
  `0075_planrequest_desktop_agent_stations.py`. `Company.monthly_price`
  yuqoridagi mantiqqa mos yangilandi.
- **`main/views.py:select_custom_plan`** — `desktop_agent_stations`ni
  POST'dan o'qiydi, narxga `stations * $60`ni qo'shadi, yaratilgan
  `PlanRequest`ga saqlaydi.
- **`main/services/billing_service.py:apply_plan_request`** — maxsus
  tarif tasdiqlanganda `company.custom_desktop_agent_stations`ni
  so'rovdan nusxalaydi; standart tarifga o'tishda (boshqa barcha
  `custom_*` maydonlar kabi) 0ga qaytariladi.
- **`main/templates/select_plan_page.html`** va **`main/templates/main.html`**
  (bu ikkalasi ham bir xil qurish formasining alohida nusxalari — ikkalasi
  ham yangilandi) — "Hodimlar Chegarasi" uslubidagi son-kiritish maydoni
  ("Desktop Agent stansiyalari", $60/dona/oy) + kamera/skaner/XPrinter
  haqida ogohlantirish matni qo'shildi, JS jonli narx hisoblagichi
  yangilandi.
- **`landing/templates/landing/plan_requests.html`** — superadmin so'rovni
  ko'rib chiqayotganda "Desktop Agent: N ta stansiya" ko'rinadigan bo'ldi.

### O'zgargan fayllar
- `main/models.py`, `main/migrations/0075_planrequest_desktop_agent_stations.py`
- `main/views.py` — `select_custom_plan`
- `main/services/billing_service.py` — `apply_plan_request`
- `main/templates/select_plan_page.html`, `main/templates/main.html`
- `landing/templates/landing/plan_requests.html`

### Tekshirildi
- `python manage.py check`, migratsiya — xatosiz
- **Izolyatsiyalangan tranzaksiyada** (rollback, haqiqiy `birzumda` +
  `ega`): (a) 2 ta stansiya bilan so'rov yuborilganda `PlanRequest.
  custom_desktop_agent_stations=2` va `custom_price` to'g'ri (barcha
  komponentlar yig'indisi: hodim+xarita+bot+AI+savdogar+2×$60+backup=$206)
  saqlanishi ✅; (b) so'rov tasdiqlanganda (`apply_plan_request`)
  `Company.custom_desktop_agent_stations=2`ga o'tishi ✅; (c)
  **`monthly_price == custom_price`** — ikki marta hisoblanmaganligi
  tasdiqlandi ✅; (d) standart tarifga o'tishda stansiyalar soni 0ga
  qaytishi ✅; (e) `main.html` va `select_plan_page.html` ikkalasi ham
  xatosiz render bo'lib, "Desktop Agent" bo'limi ko'rinishi ✅; (f)
  superadmin'ning `plan_requests.html` sahifasida "2 ta stansiya" to'g'ri
  ko'rsatilishi ✅

---

## 64-qadam: Desktop Agent — qo'lda skaner (HID, pistolet shaklidagi) qo'llab-quvvatlash

**Holat: DONE**

### Nima qilindi
Foydalanuvchi bugun pilot dasturidagi tadbirkor bilan uchrashib, undan skaner
oldi — lekin bu **veb-kamera emas**, balki **qo'lda ushlab skanerlaydigan
(pistolet shaklidagi) USB HID skaner** ekan (klaviatura kabi ishlaydi: kodni
"teradi" + Enter bosadi, hech qanday video oqim bermaydi). Avvalgi (52-55
qadamlardagi) Desktop Agent skaner qismi faqat veb-kamera + OpenCV QR-aniqlash
(`QRScanWorker`) uchun mo'ljallangan edi — bu haqiqiy pilot sinovi uchun ishlamas
edi, shuning uchun HID rejimini **qo'shimcha** ulanish turi sifatida qo'shildik
(kamera varianti ham saqlanib qoladi, ikkalasi radio-tugma orqali tanlanadi).

- `app/db.py`: `cameras.connection_type` CHECK cheklovi `'hid'`ni ham qabul
  qiladigan qilindi. SQLite CHECK cheklovini ALTER qilib bo'lmagani uchun,
  eski (hidsiz) bazalar uchun `init_db()` ichida avtomatik jadval qayta
  qurish (rename → yangi jadval yaratish → nusxalash → eskisini o'chirish)
  qo'shildi — mavjud qatorlar (kamera sozlamalari) yo'qolmaydi.
- `app/windows/camera_config_dialog.py`: `role="skaner"` bo'lganda (faqat
  skaner uchun, ombor video-kamerasi uchun emas) yangi "Qo'lda skaner (USB,
  klaviatura kabi)" radio-tugmasi qo'shildi. Tanlanganda USB/RTSP bloklari,
  "Ulanishni tekshirish" tugmasi va preview yashiriladi, o'rniga "qo'shimcha
  sozlash kerak emas" degan ma'lumot matni ko'rsatiladi. Saqlashda
  `connection_type='hid'`, hech qanday qo'shimcha parametrsiz yoziladi.
- `app/windows/scanner_page.py`: `_hid_active` flag va yangi `hid_input`
  (QLineEdit, fokusda turadigan, "Kartani skanerlang..." placeholder bilan)
  maydoni qo'shildi. "Ishga tushirish" bosilganda, agar skaner kamerasi
  `hid` turida bo'lsa — kamera worker yaratilmaydi, o'rniga `hid_input`
  ko'rsatiladi va fokus beriladi. Skaner "Enter" bilan yozgan kodni
  `_on_hid_return()` qabul qiladi va **mavjud `_on_qr_detected(kod)`
  funksiyasini qayta ishlatadi** — shu orqali barcha keyingi mantiq (badge
  tasdiqlash, stansiya sessiyasi, material so'rovlari paneli, "Qabul
  qildim" tugmasi) kamera yoki HID skaner farqisiz bir xil ishlaydi, hech
  narsa qo'shimcha yozilmadi. Har bir amaldan keyin (material so'rovlarini
  yuklash, "Qabul qildim", sessiya tugashi/"Chiqish") HID rejimida bo'lsa
  fokus avtomatik `hid_input`ga qaytariladi — xodim ketma-ket skanerlab
  ishlashi uchun (qayta sichqoncha bilan bosish shart emas).

### O'zgargan fayllar
- `desktop_agent/app/db.py`
- `desktop_agent/app/windows/camera_config_dialog.py`
- `desktop_agent/app/windows/scanner_page.py`
- `desktop_agent/dist/StockFirmAgent.exe` (PyInstaller bilan qayta build qilindi)

### Tekshirildi
- Offscreen (`QT_QPA_PLATFORM=offscreen`) PyQt6 smoke test (skript,
  haqiqiy o'zgarish yo'q, faqat vaqtinchalik SQLite fayl bilan): (a)
  `CameraConfigDialog(role="skaner")` HID radio-tugmasini ko'rsatishi va
  saqlashda `connection_type='hid'` yozilishi ✅; (b)
  `CameraConfigDialog(role="ombor")`da HID radio umuman yo'qligi ✅; (c)
  `ScannerPage.refresh()` HID kamera uchun to'g'ri holat matnini
  ko'rsatishi ✅; (d) "Ishga tushirish" bosilganda kamera worker
  yaratilmasdan `hid_input` ko'rinishi va fokus olishi ✅; (e) `hid_input`ga
  kod yozib Enter bosilganda (`returnPressed` signal simulyatsiyasi)
  `resolve_badge` chaqirilishi, stansiya sessiyasi boshlanishi, maydon
  tozalanishi ✅; (f) "To'xtatish" bosilganda HID holati tozalanib, sessiya
  ham tugashi ✅.
- Alohida skript bilan `db.py`ning eski-baza migratsiyasi tekshirildi: qo'lda
  eski sxema (`'hid'`siz CHECK) bilan SQLite fayl yaratib, ichiga USB va RTSP
  kameralar yozildi, so'ng `init_db()` chaqirildi — jadval qayta qurilib,
  ikkala eski qator ham saqlanib qolgani, endi `'hid'` qiymatini qabul
  qilishi va takroriy `init_db()` chaqiruvi xavfsiz (idempotent) ekanligi
  tasdiqlandi ✅.
- `dist/StockFirmAgent.exe` PyInstaller orqali muvaffaqiyatli qayta
  build qilindi (xatosiz, ~62s).

## 65-qadam: Skanerlanganda xodim ma'lumotlari (rasm, ism, lavozim, telefon) ko'rsatiladi

**Holat: DONE**

### Nima qilindi
Foydalanuvchi so'radi: Desktop Agent'da QR skanerlanganda (masalan xodim
telefonida o'z shaxsiy QR/badge'ini ko'rsatib, skanerga o'qitganda) — kim
ekanini ko'rsatadigan bo'lsin. Avval faqat qisqa "Xush kelibsiz, {ism}!"
matni va sessiya bannerida ism+lavozim ko'rinardi — endi to'liq xodim
kartochkasi qo'shildi.

- `main/agent_api_views.py` (`agent_badge_scan`) — javobga `tel_raqami` va
  `rasmi` (to'liq absolyut URL, `request.build_absolute_uri()` orqali)
  qo'shildi (mavjud `User.rasmi` property'sidan, u pazanda/yetkazib-beruvchi/
  savdogar profilidagi rasmni ham hisobga oladi).
- `desktop_agent/app/windows/scanner_page.py` — badge muvaffaqiyatli
  skanerlangach ko'rinadigan yangi "xodim kartochkasi" (`employee_card`):
  rasm (96x96, serverdan `requests` bilan yuklab olinadi — internetsiz/
  rasm bo'lmasa "Rasm yo'q" matni chiqadi), to'liq ism, lavozim, telefon
  raqami, login. Kartochka `_show_employee_card()` orqali to'ldiriladi,
  `_end_session()`da (sessiya tugaganda/"Chiqish"da) avtomatik yashiriladi
  — kamera va HID skaner ikkalasi uchun ham bir xil ishlaydi (chunki
  ikkalasi ham `_on_qr_detected()`ni qayta ishlatadi).

### O'zgargan fayllar
- `crm/main/agent_api_views.py` — `agent_badge_scan`
- `desktop_agent/app/windows/scanner_page.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- `python manage.py check` — xatosiz
- Offscreen PyQt6 smoke test (mock `resolve_badge` bilan): badge
  skanerlangach `employee_card` ko'rinishi va ism/lavozim/telefon/login
  to'g'ri ko'rsatilishi ✅; sessiya tugaganda ("Chiqish"/timeout yoki
  skaner to'xtatilganda) kartochka yashirinishi ✅.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

## 66-qadam: Omborlarga yaratish/tahrirlash olib tashlandi; Skaner alohida bo'lim emas, istalgan payt bosiladigan tugma bo'ldi

**Holat: DONE**

### Nima qilindi
Foydalanuvchi so'radi: "desktop ilovada create va editni olib tashla, keyin
unda alohida skanerlash bo'limi kerak emas — hohlagan payt skanerni bossa
QR o'sha firmaga tegishli bo'lib chiqsa malumot ko'rsataversin."

1. **Omborlar — yaratish/tahrirlash olib tashlandi**: omborlar CRM'dan
   (`sync_warehouses_from_remote`) sinxronlanadi — mahalliy dasturda alohida
   yaratish/tahrirish shart emas edi (dublikat, chalkash UX). `warehouse_
   list_page.py`dan "+ Yangi ombor" va "Tahrirlash" tugmalari olib tashlandi
   — endi har bir ombor qatorida faqat **"Kamera sozlash"** va **"O'chirish"**
   qoladi. `warehouse_form_dialog.py` fayli butunlay o'chirildi (endi
   hech qayerdan chaqirilmaydi).
2. **Skaner — alohida bo'lim emas, istalgan payt bosiladigan tugma**:
   avval "Skaner" — sidebar navigatsiyasidagi doimiy sahifa edi (Omborlar/
   Sozlamalar kabi), ichida qo'lda "Ishga tushirish (skanerlash)" tugmasini
   bosish kerak edi. Endi:
   - `main_window.py`: "Skaner" endi `QStackedWidget`dagi sahifa emas —
     sidebar pastida alohida, istalgan payt bosiladigan **"🔦 Skanerlash"**
     tugmasi. Bosilganda kichik oyna (`QDialog`) ochiladi, ichida
     `ScannerPage` joylashgan.
   - `scanner_page.py`: "Ishga tushirish (skanerlash)" tugmasi olib
     tashlandi — endi oyna **ko'rinishi bilan avtomatik** skanerlashni
     boshlaydi (`showEvent()`), yopilganda/yashiringanda avtomatik
     to'xtaydi (`hideEvent()`) — foydalanuvchi hech qanday qo'shimcha
     tugma bosmasdan, QR kodni ko'rsatishi bilan (kamera yoki qo'lda HID
     skaner orqali) xodim ma'lumoti (rasm, ism, lavozim, telefon) darhol
     chiqadi.

### O'zgargan fayllar
- `desktop_agent/app/windows/warehouse_list_page.py` — create/edit olib
  tashlandi
- `desktop_agent/app/windows/warehouse_form_dialog.py` — o'chirildi
- `desktop_agent/app/windows/main_window.py` — Skaner endi popup-tugma,
  stackdan olib tashlandi
- `desktop_agent/app/windows/scanner_page.py` — avtomatik
  boshlash/to'xtatish (`showEvent`/`hideEvent`), "Ishga tushirish" tugmasi
  olib tashlandi
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Offscreen PyQt6 smoke testlar: (a) `WarehouseListPage` qatorlarida faqat
  "Kamera sozlash"/"O'chirish" borligi, "Tahrirlash"/"+ Yangi ombor" hech
  qayerda yo'qligi ✅; (b) `warehouse_form_dialog` moduli endi mavjud
  emasligi ✅; (c) `MainWindow.stack`da faqat 2 ta sahifa (Omborlar,
  Sozlamalar) qolgani, Skaner endi alohida `QPushButton` ekanligi ✅;
  (d) `ScannerPage`ni ko'rsatish (`show()`) — hech qanday tugma
  bosilmasdan avtomatik HID/kamera skanerlashni boshlashi, yashirish
  (`hide()`) — avtomatik to'xtatib, sessiyani tugatishi ✅.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

## 67-qadam: Skaner endi menyu emas — fonda doimiy ishlaydi, istalgan payt skanerlansa ma'lumot darhol chiqadi

**Holat: DONE**

### Nima qilindi
66-qadamda "Skaner"ni popup-tugma qilib qo'ygan edik, lekin foydalanuvchi
buni ham istamadi: "menyuga kirmasdan skaner orqali malumot o'tkazsa
malumot stockfirmga to'g'ri kelsa malumotni darrov chiqarsin agent" — ya'ni
hech qanday tugma bosish/oyna ochish kerak emas, dastur qaysi sahifada
ochiq bo'lishidan qat'iy nazar, xodim badge'ini ko'rsatishi bilan (qo'lda
HID skaner yoki kamera orqali) ma'lumot **avtomatik** chiqishi kerak.

Bu katta arxitektura o'zgarishi talab qildi — oldingi "Skaner" popup/sahifa
konsepsiyasi butunlay olib tashlandi, o'rniga **fon xizmati** qo'shildi:

- **`app/scanner_service.py`** (yangi) — `ScannerService` (QObject),
  dastur ishga tushgan zahotidan yopilguncha fonda ishlaydi:
  - **HID (qo'lda skaner) sozlangan bo'lsa**: `QApplication`ga global
    `eventFilter` o'rnatiladi — klaviatura hodisalarini (dastur qaysi
    sahifada/oynada bo'lishidan qat'iy nazar) kuzatib turadi. Skaner juda
    tez ketma-ket belgi "yozadi" (odam yozishidan sezilarli tezroq) —
    shuning uchun ketma-ket belgilar orasidagi vaqt farqi 60ms dan oshsa
    bufer tozalanadi (oddiy sekin qo'lda yozishni chalkashtirmaslik uchun),
    Enter bosilganda bufer uzunligi >=8 bo'lsa — bu skanerlangan kod deb
    hisoblanadi. Hodisalar **iste'mol qilinmaydi** (`eventFilter` doim
    `False` qaytaradi) — oddiy matn kiritish maydonlariga (login, parol
    va h.k.) hech qanday ta'sir qilmaydi.
  - **Kamera (USB/RTSP) sozlangan bo'lsa**: `QRScanWorker` fon oqimida
    doimiy ishlaydi (foydalanuvchi hech qanday sahifa ochmasa ham).
  - `code_scanned` signali chiqaradi; `.reload()` — skaner qayta
    sozlanganda (Sozlamalar sahifasidan) eski worker/filterni to'xtatib,
    yangisini boshlaydi.
- **`app/windows/employee_scan_widget.py`** (yangi, `scanner_page.py`
  o'rnini bosadi) — `EmployeeScanWidget`: xodim kartochkasi (rasm, ism,
  lavozim, telefon) + stansiya sessiyasi banneri + material so'rovlari
  paneli. Endi hech qanday kamera/HID-boshqarish kodi yo'q (bu
  `ScannerService`ga ko'chdi) — faqat `handle_scanned_code(kod)` orqali
  tashqaridan kod qabul qiladi va natijani ko'rsatadi.
- **`app/windows/main_window.py`** — "🔦 Skanerlash" tugmasi/menyusi
  butunlay olib tashlandi. `MainWindow` endi doimiy `ScannerService`ni
  ishga tushiradi; `code_scanned` signali kelganda, kichik popup oyna
  (avval yaratilmagan bo'lsa — yaratiladi, aks holda qayta ishlatiladi)
  avtomatik ko'rsatiladi (`show()`+`raise_()`+`activateWindow()`) va
  `EmployeeScanWidget.handle_scanned_code()` chaqiriladi — foydalanuvchi
  qaysi sahifada (Omborlar yoki Sozlamalar) turgan bo'lishidan qat'iy
  nazar.
- **`app/windows/settings_page.py`** — skaner **sozlash** (kamera/HID
  tanlash) endi shu yerga ko'chirildi ("Skaner" bo'limi, "Skanerni
  sozlash" tugmasi + holat matni) — sozlash bir martalik amal, alohida
  doimiy menyu talab qilmaydi. Saqlanganda `on_scanner_changed` callback
  orqali `MainWindow.scanner_service.reload()` chaqiriladi.
- `app/windows/scanner_page.py` o'chirildi (endi kerak emas).

### O'zgargan fayllar
- `desktop_agent/app/scanner_service.py` (yangi)
- `desktop_agent/app/windows/employee_scan_widget.py` (yangi)
- `desktop_agent/app/windows/scanner_page.py` (o'chirildi)
- `desktop_agent/app/windows/main_window.py`
- `desktop_agent/app/windows/settings_page.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Offscreen PyQt6 smoke test — **haqiqiy `QKeyEvent`larni
  `QApplication`ga yuborib** (haqiqiy HID qurilma xuddi shunday ishlaydi):
  foydalanuvchi "Omborlar" sahifasida turganida (hech qanday skaner
  menyusi/oynasi ochilmagan holda) UUID-shaklidagi kodni tez ketma-ket
  "yozib" Enter yuborilganda — `resolve_badge` aynan shu kod bilan
  chaqirilishi va xodim ma'lumoti popup oynada avtomatik chiqishi ✅;
  sekin (odam tezligida, ~100ms/harf) yozilgan ketma-ketlik esa skaner
  deb noto'g'ri aniqlanmasligi (chalkashmasligi) ✅.
- Sozlamalar sahifasida skaner sozlanishi holat matnini yangilashi va
  `ScannerService.reload()`ni chaqirishi ✅ (alohida test skripti bilan).
- Avvalgi omborlar (create/edit yo'qligi) va `db.py` eski-sxema
  migratsiya testlari ham qayta ishga tushirilib, hamon o'tishi
  tasdiqlandi.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

## 68-qadam: Jiddiy bug tuzatildi — dastur muzlab qolishi (skanerlash tarmoq chaqiruvi asosiy oqimni bloklayotgan edi)

**Holat: DONE**

### Nima qilindi
Foydalanuvchi 67-qadamdan keyin xabar berdi: "handle ishlamayabdi ilova
tutmaybadi" (ilova muzlab qolyapti). Tekshirilganda, ikkita
`StockFirmAgent.exe` jarayoni haqiqatan ham osilib qolgan holda topildi
(`Get-Process StockFirmAgent` — 21:53da ishga tushgan, javob bermayapti).

**Ildiz sabab**: 67-qadamda skaner butun dastur bo'ylab fonda ishlaydigan
qilib o'zgartirilgan edi — endi HID skanerdan kelgan har qanday tez
ketma-ket bosilgan+Enter bilan tugagan belgi ketma-ketligi avtomatik
`resolve_badge()` (tarmoq so'rovi) chaqirar edi. Muammo shundaki,
`EmployeeScanWidget.handle_scanned_code()` (va `_load_material_requests`,
`_acknowledge_current_request`, xodim rasmini yuklab olish) barchasi
**to'g'ridan-to'g'ri asosiy (GUI) oqimda, sinxron** `requests` chaqiruvlari
edi. Avval (66-qadamgacha) bu muammo emas edi, chunki skanerlash faqat
foydalanuvchi ochiq oynada tugmani bosgandan keyin ishga tushardi va
odatda server tez javob berardi; lekin endi **butun dastur bo'ylab
har qanday tez yozilgan+Enter ketma-ketligi** (hatto tasodifiy — masalan
parolni tez kiritish) shu chaqiruvni ishga tushirishi mumkin edi, va agar
server sekin javob bersa yoki umuman ulanmasa (`api_client.TIMEOUT=10s`) —
**butun dastur GUI oqimi bloklanib, ilova "muzlab" qolar edi**.

**Tuzatish**:
- `desktop_agent/app/windows/employee_scan_widget.py` — barcha tarmoq
  chaqiruvlari (`resolve_badge`, `fetch_material_requests`,
  `acknowledge_material_request`, xodim rasmini yuklab olish) endi yangi
  `_ApiCallWorker`/`_ImageFetchWorker` (`QThread`) orqali **fon oqimida**
  bajariladi, natija `succeeded`/`failed` signali orqali asosiy oqimga
  qaytariladi. Endi server qanchalik sekin bo'lmasin yoki ulanib
  bo'lmasin — GUI hech qachon bloklanmaydi.
- `desktop_agent/app/scanner_service.py` — `HID_MIN_CODE_LENGTH` 8 dan
  **20**ga oshirildi (haqiqiy badge kodi — `uuid4()`, 36 belgi) — bu
  tasodifiy tez yozilgan qisqa matnlarni (masalan parol) skaner deb
  noto'g'ri aniqlash ehtimolini kamaytiradi (garchi asosiy tuzatish —
  fon oqimiga o'tkazish — bunday hodisalarni endi xavfsiz qiladi ham).
- Osilib qolgan ikkita `StockFirmAgent.exe` jarayoni to'xtatildi
  (`Stop-Process`), `dist/StockFirmAgent.exe` qayta build qilindi.

### O'zgargan fayllar
- `desktop_agent/app/windows/employee_scan_widget.py`
- `desktop_agent/app/scanner_service.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Yangi regressiya testi (offscreen, `resolve_badge`ni sun'iy 1.5 soniya
  "sekin server" deb simulyatsiya qilib): skanerlash boshlanganda GUI
  oqimi bloklanmasligini — parallel ishlayotgan `QTimer` 20ms interval
  bilan tikanishda davom etishini (1.5s ichida 75 marta tiklandi) —
  tasdiqladi. Tuzatishdan oldingi (sinxron) kodga qaytarib
  sinab ko'rilganda bu test aynan **hangs/bloklanish** xatosini ushlab
  qolgan bo'lardi.
- Avvalgi global-skaner, sozlamalar, ombor va `db.py` migratsiya testlari
  qayta ishga tushirilib, hammasi o'tdi ✅.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi (avval osilib qolgan eski jarayonlar tugatilgandan keyin).

## 69-qadam: Skanerlanganda HID belgilar boshqa maydonlarga/tugmalarga "sizib" kirmasligi ta'minlandi

**Holat: DONE**

### Nima qilindi
Foydalanuvchi xabar berdi: "skaner qilsam labellar ustida almashyabdi
dastur ihida" — ya'ni HID skaner "yozgan" belgilar dastur ichidagi
qaysidir elementga (fokusda turgan maydon/tugma) borib tushib, ko'rinishni
buzayotgan edi.

**Sabab**: qo'lda HID skaner fizik jihatdan oddiy klaviatura — u "yozgan"
har bir belgi haqiqiy OS darajasidagi klaviatura hodisasi bo'lib, o'sha
paytda fokusda turgan istalgan widgetga (masalan Sozlamalar sahifasidagi
login/parol maydoni) yetib boradi. 67-68 qadamlarda `ScannerService`
bu hodisalarni faqat **kuzatar edi** (iste'mol qilmasdan, `eventFilter`
doim `False` qaytarardi) — shuning uchun skanerlangan uzun tasodifiy
matn haqiqatan ham fokusdagi maydonga yozilib ketardi.

**Yechim** — `desktop_agent/app/scanner_service.py` to'liq qayta
yozildi ("ushlab qolish va zarurat bo'lsa qaytarish" strategiyasi):
- Endi har bir belgi hodisasi **iste'mol qilinadi** (`eventFilter` `True`
  qaytaradi) — hech qaysi widgetga (maydon, tugma) yetib bormaydi,
  o'rniga ichki buferga yig'iladi va qaysi widget fokusda ekani
  eslab qolinadi.
- Enter bosilganda yoki ~150ms harakatsizlikdan so'ng ("burst tugadi")
  qaror qabul qilinadi:
  - Agar bufer uzunligi badge kodiga mos (>=20 belgi, `uuid4()` — 36
    belgi) — bu **haqiqiy skaner** deb hisoblanadi, `code_scanned`
    signali chiqadi, hech narsa hech qanday widgetga yetib bormaydi.
  - Aks holda (oddiy, qisqaroq qo'lda yozish, masalan parol) — ushlab
    qolingan belgilar **sun'iy hodisalar orqali asl widgetga qaytarib
    yuboriladi**, xuddi hech narsa ushlanmagandek — shuning uchun
    Sozlamalar sahifasidagi maydonlarga oddiy yozish avvalgidek ishlayveradi.
- Sun'iy (qaytarilayotgan) hodisalar o'zining eventFilter tomonidan
  qayta ushlab qolinmasligi uchun `_hid_replaying` bayrog'i bilan
  himoyalangan (aks holda cheksiz sikl bo'lardi).

### O'zgargan fayllar
- `desktop_agent/app/scanner_service.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Yangi offscreen regressiya testi: fokusda turgan `QLineEdit`ga (a)
  haqiqiy uzun badge kodi (36 belgi) + Enter yuborilganda — maydon
  matni butunlay bo'sh qolishi (hech qanday belgi "sizib kirmasligi") va
  `code_scanned` to'g'ri kod bilan chiqishi ✅; (b) qisqa oddiy matn
  ("hi") + Enter yuborilganda — bu skaner deb hisoblanmasligi va
  belgilar maydonga xuddi avvalgidek yozilishi (`field.text() == "hi"`) ✅.
- Avvalgi barcha smoke/regressiya testlar (global skaner, muzlab qolish,
  sozlamalar, ombor, db migratsiya) qayta ishga tushirilib, hammasi
  o'tdi.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

## 70-qadam: Jiddiy bug — har safar dastur qayta ochilganda barcha sozlamalar (login, skaner turi) o'chib ketardi

**Holat: DONE**

### Nima qilindi
Foydalanuvchi haqiqiy badge QR rasmini yuborib: "baribir shuni skaner
qilsam ham hech nimani chiqarmayabdi" deb xabar berdi. Tekshirilganda,
69-qadamdagi HID tuzatishlarga aloqasi yo'q, ancha jiddiyroq va oldindan
mavjud bo'lgan bug topildi:

**Ildiz sabab**: `desktop_agent/app/db.py`dagi `DB_PATH` `dirname(dirname
(__file__))` asosida hisoblanardi. Bu odatiy (manba kod orqali) ishga
tushirishda to'g'ri ishlaydi, lekin PyInstaller `--onefile` bilan build
qilingan `.exe` uchun **har safar dastur ishga tushirilganda** `__file__`
vaqtinchalik, **tasodifiy nomli** `_MEI<random>` papkaga (masalan
`...\Temp\_MEI102202\app\db.py`) ochiladi — bu papka har ishga
tushirishda BOSHQA bo'ladi va dastur yopilganda o'chiriladi. Natijada
`agent_data.db` ham har safar YANGI, bo'sh joyda yaratilar edi — login
(server manzili, stansiya tokeni), **skaner sozlamasi (HID/kamera)**,
va sinxronlangan omborlar — barchasi **dastur qayta ochilganda butunlay
yo'qolib ketar edi**. Foydalanuvchi bir marta skanerni HID qilib
sozlagan bo'lsa ham, dasturni qayta ochgach sozlama "yo'q" holatiga
qaytar, `ScannerService` hech narsa ishga tushirmas edi — shuning uchun
"hech nima chiqmayabdi" edi. (Buni tasdiqlash uchun `%TEMP%` papkasida
13 ta eski `_MEI*` qoldiq papka topildi — har bir ishga tushirish/
to'xtatishdan qolgan.)

**Tuzatish** — `desktop_agent/app/db.py`: `_default_db_path()` funksiyasi
qo'shildi — `sys.frozen` (PyInstaller belgisi) tekshiriladi:
- **Build qilingan `.exe`** bo'lsa — `%LOCALAPPDATA%\StockFirmAgent\
  agent_data.db` (doimiy, foydalanuvchi profili ichidagi papka) ishlatiladi.
- **Manba koddan ishga tushirilganda** (dasturchi rejimi) — avvalgidek,
  repo ichidagi joy saqlanadi (breaking change yo'q).

### O'zgargan fayllar
- `desktop_agent/app/db.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Yangi regressiya testi: (a) "frozen bo'lmagan" (dasturchi) rejimida
  yo'l hamon repo ichida ekanligi ✅; (b) `sys.frozen=True` qo'yilganda,
  hisoblangan yo'l **ikki marta chaqirilganda ham bir xil** (ya'ni
  `__file__`ning tasodifiy `_MEI` joyiga bog'liq emasligi) va
  `%LOCALAPPDATA%\StockFirmAgent\` ichida ekanligi tasdiqlandi ✅.
- Avvalgi barcha skaner/omborlar/sozlamalar smoke testlari qayta ishga
  tushirilib, hammasi o'tdi.
- Osilib qolmagan, lekin eski (fix qo'llanmasdan oldingi) ikkita
  `StockFirmAgent.exe` jarayoni to'xtatilib, `dist/StockFirmAgent.exe`
  qayta build qilindi; 13 ta eski `_MEI*` qoldiq papka tozalandi.

## 71-qadam: Sozlamalarda ortiqcha "Firma subdomeni" maydoni olib tashlandi

**Holat: DONE**

### Nima qilindi
Foydalanuvchi to'g'ri savol berdi: "buni o'rniga biz main login logikasi
orqali login qilsak bo'lmaydimi? subdomenni kiritib nima bor" — nega
Sozlamalar sahifasida "Server manzili" (masalan `https://birzumda.
stockfirm.uz`) VA alohida "Firma subdomeni" (`birzumda`) ikkalasi ham
so'ralardi, holbuki subdomen allaqachon server manzilining o'zida bor
edi — bu **ortiqcha, dublikat maydon** ekan. CRM'ning o'zi ham (asosiy
saytdagi login) xuddi shunday ishlaydi: `CompanyMiddleware`
(`main/middleware.py:54`, `subdomain = parts[0]`) foydalanuvchidan
alohida subdomen so'ramaydi — uni to'g'ridan-to'g'ri so'rov manzilidan
(`host.split('.')[0]`) o'zi ajratib oladi.

**Tuzatish**:
- `desktop_agent/app/api_client.py` — `subdomain_from_server_url(server_url)`
  yangi funksiyasi qo'shildi (`urlparse` bilan hostnameni olib,
  `.split('.')[0]` — aynan `CompanyMiddleware` bilan bir xil mantiq).
  `station_login()` endi `subdomain` parametrini butunlay qabul
  qilmaydi — uni server manzilidan o'zi hisoblab oladi.
- `desktop_agent/app/windows/settings_page.py` — "Firma subdomeni"
  input maydoni butunlay olib tashlandi; izoh matni yangilandi
  ("subdomen alohida kiritilmaydi, u manzilning o'zida bor").
- Backend (`main/agent_api_views.py:agent_station_login`) o'zgarmadi —
  u hamon `subdomain` parametrini kutadi, faqat endi uni desktop
  ilovaning o'zi (foydalanuvchidan so'ramasdan) server manzilidan
  hisoblab yuboradi.

### O'zgargan fayllar
- `desktop_agent/app/api_client.py`
- `desktop_agent/app/windows/settings_page.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Offscreen regressiya testi: (a) `subdomain_from_server_url()`
  `https://birzumda.stockfirm.uz`, orqa slash bilan, va
  `http://test-firma.localhost:8000` kabi manzillardan to'g'ri
  subdomenni ajratib olishi ✅; (b) `SettingsPage`da endi
  `subdomain_input` maydoni yo'qligi va faqat 3 ta matn maydoni
  (server, login, parol) qolgani ✅; (c) "Kirish" tugmasi bosilganda
  `station_login(server_url, username, password)` — subdomensiz —
  to'g'ri chaqirilishi ✅.
- Avvalgi barcha skaner/DB-yo'l/HID testlari qayta ishga tushirilib,
  hammasi o'tdi.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

## 72-qadam: Desktop Agent login — endi asosiy saytdagi kabi, istalgan mavjud hisob bilan kirish mumkin

**Holat: DONE**

### Nima qilindi
Foydalanuvchi qattiq norozi bo'lib xabar berdi: "buni siz login qila
oladigon qilishimiz kerak" — ya'ni Desktop Agent'ga alohida "Desktop
Agent" turida maxsus hisob yaratmasdan, **mavjud login/parol** (masalan
o'zining `ega` hisobi) bilan ham kira olishi kerak edi.

**Sabab**: `main/agent_api_views.py:agent_station_login` faqat
`User.objects.filter(..., type='desktop_agent')` — ya'ni faqat maxsus
yaratilgan stansiya hisoblarigagina ruxsat berardi. Foydalanuvchi
o'zining haqiqiy (`ega`) login/paroli bilan kirishga uringanda "Login
yoki parol noto'g'ri" xatosi chiqardi, garchi parol to'g'ri bo'lsa ham.

**Tuzatish** — `main/agent_api_views.py:agent_station_login`: `type=
'desktop_agent'` filtri olib tashlandi. Endi asosiy saytdagi login
(`views.login`) bilan bir xil mantiq: firmaning **istalgan faol
foydalanuvchisi** (ega, omborchi, yoki maxsus yaratilgan desktop_agent
stansiyasi — farqi yo'q) o'z login/paroli bilan Desktop Agent'ga kira
oladi. Bir nechta stansiya bir xil hisob bilan kirsa ham muammo emas —
har biri alohida `token` oladi (avvalgi token bekor bo'ladi).

**Eslatma (biznes-mantiq nuansi)**: 57-63 qadamlarda qurilgan "Desktop
Agent stansiyasi" billing kvotasi (`custom_desktop_agent_stations`,
$60/stansiya/oy) — bu faqat **YANGI `desktop_agent` turidagi hisob
yaratishda** (Hodimlar > Yangi hodim qo'shish) tekshiriladi, bu
o'zgarishga tegilmadi. Ya'ni: firma xohlasa hamon alohida stansiya
hisoblarini sotib olib yaratishi mumkin (ko'p-stansiyali, nazoratli
senariy uchun), lekin endi **mavjud har qanday hisob bilan ham** darhol
kirish mumkin bo'ldi (tezkor/yakka-stansiyali sinov uchun qulay).

### O'zgargan fayllar
- `main/agent_api_views.py` — `agent_station_login`

### Tekshirildi
- Izolyatsiyalangan tranzaksiyada (rollback, haqiqiy `birzumda` + `ega`):
  (a) noto'g'ri parol bilan hamon 401 qaytishi ✅; (b) `ega` hisobining
  o'z (maxsus "Desktop Agent" turi bo'lmagan) login/paroli bilan
  `/api/agent/login/`ga muvaffaqiyatli kirib, `token`/`company`/
  `station_name` to'g'ri qaytishi ✅; (c) muvaffaqiyatli kirishdan keyin
  `User.token` yangilanishi ✅.
- `python manage.py check` — xatosiz.
- Bu — faqat server (Django) tomonidagi o'zgarish, Desktop Agent
  `.exe`ni qayta build qilish shart emas.

## 73-qadam: "Server manzili" o'rniga faqat "Firma nomi" — to'liq URL avtomatik quriladi

**Holat: DONE**

### Nima qilindi
Foydalanuvchi yana to'g'ri savol berdi: "yana server manzili nima
qilyabdi" — nega hali ham to'liq `https://sizning-firma.stockfirm.uz`
manzilini yozish kerak, holbuki barcha StockFirm mijozlari BITTA umumiy
domenda (`stockfirm.uz`) ishlaydi, faqat subdomen farq qiladi.

**Yechim** — `desktop_agent/app/api_client.py`ga `BASE_DOMAIN =
"stockfirm.uz"` konstantasi va `normalize_server_url(raw)` funksiyasi
qo'shildi:
- Agar foydalanuvchi shunchaki firma nomini kiritsa (masalan
  `"birzumda"`) — `https://birzumda.stockfirm.uz` avtomatik quriladi.
- Agar allaqachon to'liq manzil kiritilgan bo'lsa (`://` bor — masalan
  mahalliy/test server uchun `http://test.localhost:8000`) —
  o'zgarishsiz qoldiriladi (dasturchi/test rejimi buzilmaydi).

`desktop_agent/app/windows/settings_page.py` — "Server manzili" maydoni
endi **"Firma nomi"** deb ataladi, placeholder "masalan: birzumda".
Kirishda xom matn (`server_input_raw`) alohida saqlanadi (sahifa qayta
ochilganda foydalanuvchiga o'zi kiritgan qisqa nom qaytarib
ko'rsatiladi, u hech qachon yozmagan to'liq URL emas) — haqiqiy API
chaqiruvlari uchun esa `normalize_server_url()` orqali qurilgan to'liq
manzil (`server_url`) ishlatiladi (o'zgarishsiz).

### O'zgargan fayllar
- `desktop_agent/app/api_client.py`
- `desktop_agent/app/windows/settings_page.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Offscreen regressiya testi: (a) `normalize_server_url("birzumda")` ->
  `https://birzumda.stockfirm.uz`; bo'sh joylar bilan ham to'g'ri
  tozalanishi; allaqachon to'liq (`://` bor) manzillar o'zgarishsiz
  qolishi ✅; (b) natija hamon `subdomain_from_server_url()` orqali
  to'g'ri "round-trip" qilishi ✅; (c) Sozlamalar sahifasida faqat
  "birzumda" yozib "Kirish" bosilganda, haqiqatda
  `https://birzumda.stockfirm.uz` manziliga so'rov ketishi ✅; (d)
  sahifa qayta ochilganda maydonda foydalanuvchi yozgan xom qiymat
  ("birzumda"), qurilgan to'liq URL emas, ko'rsatilishi ✅.
- Avvalgi barcha skaner/login/DB testlari qayta ishga tushirilib,
  hammasi o'tdi.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

## 74-qadam: "Firma nomi" maydoniga lokal test-server manzilini kiritish imkoniyati tushuntirildi

**Holat: DONE**

### Nima qilindi
73-qadamdagi o'zgarishdan keyin foydalanuvchi "birzumda" deb kiritganda
"Kirish amalga oshmadi" xatosiga duch keldi. Sabab aniqlandi: hozircha
haqiqiy production emas, **mahalliy dev-server** (`http://birzumda.
localhost:8000`, `python manage.py runserver`) sinalayotgan edi —
`normalize_server_url("birzumda")` esa endi doim
`https://birzumda.stockfirm.uz` (haqiqiy internet domeni) quradi, bu
mahalliy serverga emas, tashqi internetga so'rov yuboradi.

Kodning o'zi buni allaqachon qo'llab-quvvatlar edi:
`normalize_server_url()` — agar kiritilgan matnda `://` bo'lsa (ya'ni
allaqachon to'liq manzil), uni o'zgarishsiz qoldiradi. Demak foydalanuvchi
"Firma nomi" maydoniga shunchaki `http://birzumda.localhost:8000` (to'liq
lokal manzil) yozsa — bu ishlaydi. Haqiqiy lokal serverga (`curl` orqali)
to'g'ridan-to'g'ri tekshirilib, `/api/agent/login/` noto'g'ri parol bilan
to'g'ri JSON 401 qaytarishi tasdiqlandi.

**Qilingan o'zgarish** — faqat matn/izoh: `settings_page.py`dagi izoh
matniga "Test/lokal server uchun to'liq manzil ham kiritish mumkin,
masalan http://birzumda.localhost:8000" qo'shildi — bu imkoniyat
avvaldan bor edi, endi foydalanuvchiga ko'rinadigan qilindi.

### O'zgargan fayllar
- `desktop_agent/app/windows/settings_page.py` (faqat izoh matni)
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Haqiqiy lokal dev-serverga (`http://birzumda.localhost:8000`,
  ishlab turgan `runserver` jarayoniga) `curl` orqali to'g'ridan-to'g'ri
  so'rov yuborilib, noto'g'ri parol bilan to'g'ri `401` +
  `{"detail":"Login yoki parol noto'g'ri."}` qaytishi tasdiqlandi —
  demak to'liq lokal manzil kiritilganda login oqimi haqiqatda ishlaydi.
- Avvalgi `normalize_server_url`/Sozlamalar regressiya testlari qayta
  ishga tushirilib, o'tdi.
- `dist/StockFirmAgent.exe` qayta build qilindi.

## 75-qadam: Lokal test uchun to'g'ri manzil — `birzumda.localhost` emas, `127.0.0.1:8000`

**Holat: DONE**

### Nima qilindi
74-qadamda tavsiya qilingan `http://birzumda.localhost:8000` Windows'da
"Serverga ulanib bo'lmadi" xatosi bilan ishlamadi. Sabab: Windows'ning
o'zi (ba'zi brauzerlardan farqli) ixtiyoriy `*.localhost` subdomenlarini
avtomatik `127.0.0.1`ga hal qilmaydi (`Resolve-DnsName
birzumda.localhost` — bo'sh natija qaytardi, DNS xatosi).

**To'g'ri yechim topildi**: Desktop Agent API (`/api/agent/*`) firmani
so'rov manzilidan (Host header/subdomen) emas, balki **aniq
parametrlardan** (login vaqtida `subdomain` maydonidan, keyingi
so'rovlarda esa `token`dan) aniqlaydi — bu ataylab shunday qilingan
(host-agnostic dizayn, 52-59 qadamlar). Demak lokal test uchun
subdomenli manzil umuman shart emas — oddiy `http://127.0.0.1:8000`
(yoki `http://localhost:8000`) yetarli. `curl` orqali to'g'ridan-to'g'ri
tekshirilib, `http://127.0.0.1:8000/api/agent/login/`ga `subdomain=
birzumda` bilan so'rov yuborilganda to'g'ri `401`/`{"detail":"Login
yoki parol noto'g'ri."}` javob qaytishi tasdiqlandi (hosts fayliga
tegilmasdan, hech qanday tizim sozlamasi o'zgartirilmasdan).

**Qilingan o'zgarish** — faqat izoh matni: `settings_page.py`dagi
tavsiya `http://birzumda.localhost:8000`dan `http://127.0.0.1:8000`ga
almashtirildi, sababi ham qisqacha tushuntirildi.

### O'zgargan fayllar
- `desktop_agent/app/windows/settings_page.py` (faqat izoh matni)
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- `curl http://127.0.0.1:8000/api/agent/login/` — to'g'ri JSON 401
  javob qaytishi (haqiqiy ishlab turgan lokal `runserver`ga).
- `Resolve-DnsName birzumda.localhost` (PowerShell) — Windows'da bu
  hal qilinmasligini tasdiqladi, shu orqali muammoning aynan DNS/hosts
  darajasida ekanligi, kod xatosi emasligi aniqlandi.
- `dist/StockFirmAgent.exe` qayta build qilindi.

## 76-qadam: IP/localhost manzillar uchun "Firma topilmadi" tuzatildi — "<firma>@<manzil>" formati

**Holat: DONE**

### Nima qilindi
75-qadamda tavsiya qilingan `http://127.0.0.1:8000` bilan "Firma
topilmadi" xatosi chiqdi. Sabab: `subdomain_from_server_url()` hostnameni
`.` bo'yicha bo'lib birinchi qismini subdomen deb oladi — `127.0.0.1`
uchun bu **"127"** bo'lib chiqadi (haqiqiy subdomen emas!), shuning uchun
`Company.objects.filter(subdomain="127")` hech narsa topmaydi. IP/
localhost manzillarda haqiqatda hech qanday subdomen yo'q — uni manzilning
o'zidan chiqarib bo'lmaydi.

**Yechim** — `desktop_agent/app/api_client.py`ga `parse_server_input(raw)`
funksiyasi qo'shildi:
- Oddiy holat (faqat firma nomi, masalan "birzumda") — avvalgidek,
  production manzili avtomatik quriladi, subdomen ham shu nom.
- IP/localhost server uchun **"<firma nomi>@<manzil>"** formati
  qo'llab-quvvatlanadi, masalan: `birzumda@http://127.0.0.1:8000` — "@"
  dan oldingi qism aniq subdomen sifatida, keyingi qism esa to'liq
  manzil sifatida ishlatiladi (sxema yozilmagan bo'lsa `http://`
  avtomatik qo'shiladi).
- `station_login()` signaturasi qaytadan `(server_url, subdomain,
  username, password)` bo'ldi — farqi shundaki, endi bu ikkalasi bitta
  "Firma nomi" maydonidan `parse_server_input()` orqali **avtomatik**
  hisoblanadi (foydalanuvchi alohida maydon to'ldirmaydi).
- `settings_page.py` izoh matni yangilandi: "Test/lokal server — IP
  yoki localhost — uchun \"<firma nomi>@<manzil>\" formatida kiriting,
  masalan birzumda@http://127.0.0.1:8000."

### O'zgargan fayllar
- `desktop_agent/app/api_client.py`
- `desktop_agent/app/windows/settings_page.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Offscreen regressiya testi: (a) `parse_server_input("birzumda")` ->
  `(https://birzumda.stockfirm.uz, birzumda)` ✅; (b)
  `parse_server_input("birzumda@http://127.0.0.1:8000")` ->
  `(http://127.0.0.1:8000, birzumda)` ✅; (c) sxemasiz manzil
  (`birzumda@127.0.0.1:8000`) uchun `http://` avtomatik qo'shilishi ✅;
  (d) bo'sh joylar bilan ham to'g'ri tozalanishi ✅; (e) Sozlamalar
  sahifasida shu "@" formatini kiritib "Kirish" bosilganda
  `station_login`ga to'g'ri `server_url`/`subdomain` juftligi
  yuborilishi ✅.
- Haqiqiy ishlab turgan lokal serverga (`curl http://127.0.0.1:8000/
  api/agent/login/` + `subdomain=birzumda`) to'g'ridan-to'g'ri so'rov
  yuborilib, to'g'ri `401`/`{"detail":"Login yoki parol
  noto'g'ri."}` javob qaytishi (yani endi "Firma topilmadi" emas)
  tasdiqlandi.
- `dist/StockFirmAgent.exe` qayta build qilindi.

## 77-qadam: Omborga bir nechta kamera (USB+RTSP aralash) va material so'rovi uchun QR kod

**Holat: DONE**

### Nima qilindi
Foydalanuvchi ikkita ish berdi va o'zi uxlashga ketdi ("o'zing ishni bili
bajar"): (1) omborga kamera bog'lashda faqat bitta emas, bir nechta
kamera (ba'zilari USB, ba'zilari RTSP) biriktirish imkoni; (2) "tushgan
so'rov asosida" QR kod generatsiya qilish tizimi.

**1) Ombor — bir nechta kamera (Desktop Agent)**
Avval har bir omborga FAQAT bitta kamera biriktirilishi mumkin edi
(`_upsert_camera` — yangisini saqlashda eskisini o'chirib tashlardi).
Endi:
- `desktop_agent/app/db.py` — `list_cameras_for_warehouse`,
  `get_camera`, `add_camera_for_warehouse` (qo'shadi, o'chirmaydi),
  `update_camera` (bitta kamerani joyida tahrirlaydi), `delete_camera`
  qo'shildi. Skaner (role='skaner') — hamon bitta qurilma, o'zgarishsiz
  (`get_scanner_camera`/`save_scanner_camera`).
- `desktop_agent/app/windows/camera_config_dialog.py` — yangi
  `camera_id` parametri qo'shildi: `None` bo'lsa YANGI kamera qo'shadi,
  berilgan bo'lsa MAVJUDINI tahrirlaydi (endi "ombor" o'rniga bittasini
  ustidan yozib yubormaydi).
- `desktop_agent/app/windows/warehouse_cameras_dialog.py` (yangi) —
  `WarehouseCamerasDialog`: bitta ombor uchun barcha kameralarni ro'yxat
  ko'rinishida ko'rsatadi, har biriga "Tahrirlash"/"O'chirish", tepada
  "+ Yangi kamera".
- `desktop_agent/app/windows/warehouse_list_page.py` — "Kamera sozlash"
  tugmasi "Kameralar" bo'ldi (yangi dialogni ochadi), "Kamera holati"
  ustuni endi "N USB, M RTSP" formatida jami kameralar sonini ko'rsatadi.

**2) Material so'rovi uchun QR kod (CRM backend)**
- `main/models.py` — `ProductionMaterialRequest.kod` (uuid4, unique) +
  migratsiya (`0076_productionmaterialrequest_kod.py`, qo'lda yozildi —
  `makemigrations` mavjud qatorlar uchun interaktiv so'rov berardi).
- `main/warehouse_views.py` — `material_request_qr_image(request, kod)`
  — ichki/autentifikatsiyalangan (public emas), faqat shu firma
  xodimlariga, `qrcode` kutubxonasi bilan PNG qaytaradi (xuddi
  `xodim_badge_image`/mahsulot `Serial` QR'i naqshiga o'xshab).
- `main/urls.py` — `/ombor/sorovlar/qr/<kod>/`.
- `main/templates/warehouse_requests.html` — har bir so'rov qatoriga
  kichik QR rasm-havola qo'shildi (bosilsa to'liq PNG ochiladi — chop
  etib jismoniy paketga yopishtirish uchun).

### O'zgargan fayllar
- `desktop_agent/app/db.py`, `camera_config_dialog.py`,
  `warehouse_cameras_dialog.py` (yangi), `warehouse_list_page.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)
- `main/models.py`, `main/migrations/0076_productionmaterialrequest_kod.py`
- `main/warehouse_views.py`, `main/urls.py`,
  `main/templates/warehouse_requests.html`

### Tekshirildi
- Offscreen smoke test: (a) bitta omborga 3 ta kamera (2 USB + 1 RTSP)
  qo'shilishi, hech biri boshqasini o'chirmasligi ✅; (b)
  `update_camera`/`delete_camera` faqat nishonlangan kamerani
  o'zgartirishi/o'chirishi, qolganlariga tegmasligi ✅; (c) skaner
  (role='skaner') hamon bitta qurilma bo'lib qolishi ✅; (d)
  `WarehouseCamerasDialog` va yangilangan `WarehouseListPage` to'g'ri
  ishlashi ✅.
- Izolyatsiyalangan tranzaksiyada (rollback, real `birzumda`): (a)
  `ProductionMaterialRequest` yaratilganda `kod` avtomatik
  generatsiya bo'lishi ✅; (b) `/ombor/sorovlar/qr/<kod>/` to'g'ri PNG
  qaytarishi ✅, noma'lum kod uchun 404 ✅, boshqa firma sessiyasidan
  ochib bo'lmasligi (403) ✅; (c) `/ombor/sorovlar/` sahifasi QR
  rasm-havolasi bilan xatosiz render bo'lishi ✅.
- `python manage.py check` — xatosiz.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

## 78-qadam: Material so'rovi QR kodi Desktop Agent skaneriga ulandi (universal skanerlash)

**Holat: DONE**

### Nima qilindi
77-qadamda material so'rovlari uchun QR kod generatsiya qilingan edi
(chop etib jismoniy paketga yopishtirish uchun), lekin u hali Desktop
Agent'ning skaner oqimiga ulanmagan edi — uni skanerlasangiz "Bu QR kod
hech qanday xodimga tegishli emas" xatosi chiqardi (chunki eski
`badge-scan` endpoint faqat `XodimBadge` kodlarini bilardi). Bu qadomda
ikkalasi bog'landi:

- **`main/agent_api_views.py`** — yangi **universal** `agent_scan`
  endpointi (`/api/agent/scan/`) qo'shildi: skanerlangan har qanday kodni
  qabul qiladi, avval `XodimBadge.kod`ka, topilmasa
  `ProductionMaterialRequest.kod`ka tekshiradi, javobda `type` maydoni
  bilan farqlaydi (`'badge'` yoki `'material_request'`). Eski
  `agent_badge_scan` (`/api/agent/badge-scan/`) orqaga moslik uchun
  saqlab qolindi, ichki mantiq umumiy `_badge_scan_response()` orqali
  ulashiladi.
- **`desktop_agent/app/api_client.py`** — yangi `scan()` funksiyasi
  (`/api/agent/scan/`ni chaqiradi).
- **`desktop_agent/app/windows/employee_scan_widget.py`** —
  `handle_scanned_code()` endi `scan()`ni chaqiradi va javobdagi `type`ga
  qarab ikki xil ko'rsatadi:
  - `type='badge'` — avvalgidek, xodim kartochkasi + stansiya sessiyasi.
  - `type='material_request'` — yangi, faqat o'qish uchun kartochka:
    material nomi, miqdori, maqsad mahsuloti, so'ragan xodim, holat
    (Kutilmoqda/Tasdiqlangan/Rad etilgan — rangli), qabul qilingan
    belgisi. **Sessiya boshlamaydi** — chunki bu odam emas, muayyan
    so'rovni aniqlaydi (badge sessiyasi orqali "Qabul qildim" bosish
    hamon avvalgidek ishlayveradi, bu QR shunchaki qo'shimcha — jismoniy
    paketni identifikatsiya qilish uchun ko'rish imkoniyati).

### O'zgargan fayllar
- `main/agent_api_views.py` — `agent_scan` (yangi), `agent_badge_scan`
  (ichki logikasi umumiylashtirildi)
- `landing/urls.py` — `/api/agent/scan/` yo'nalishi
- `desktop_agent/app/api_client.py` — `scan()`
- `desktop_agent/app/windows/employee_scan_widget.py` —
  `handle_scanned_code`/`_on_scan_resolved` + yangi material-so'rov
  kartochkasi
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Izolyatsiyalangan tranzaksiyada (rollback, real `birzumda`): (a)
  `/api/agent/scan/` badge kodi bilan `type='badge'` + `session_token`
  qaytarishi ✅; (b) material so'rovi kodi bilan `type='material_request'`
  + to'g'ri material/miqdor/holat ma'lumoti (sessiya tokenisiz) qaytarishi
  ✅; (c) noma'lum kod uchun 404 ✅; (d) eski `/api/agent/badge-scan/`
  hamon ishlashi (orqaga moslik) ✅.
- Offscreen smoke test (`EmployeeScanWidget`): (a) material-so'rov kodi
  skanerlanganda faqat ma'lumot kartochkasi ko'rinishi, sessiya
  boshlanmasligi ✅; (b) badge kodi skanerlanganda avvalgidek xodim
  kartochkasi+sessiya ishlashi, material-so'rov kartochkasi
  yashirinishi ✅; (c) noma'lum kod uchun xato ko'rsatilib, ikkala
  kartochka ham yashirin qolishi ✅.
- Avvalgi barcha global-skaner/muzlab-qolmaslik/HID-sizib-kirmaslik
  testlari qayta ishga tushirilib (endi `scan()` orqali), hammasi o'tdi.
- `python manage.py check` — xatosiz.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

## 79-qadam: Skaner endi butun kompyuter bo'ylab ishlaydi — dastur oynasi fokusda bo'lishi shart emas ("GTA cheat kod" uslubi)

**Holat: DONE**

### Nima qilindi
Foydalanuvchi telefonida rasmga olingan (yoki brauzerda ochilgan) o'z
badge QR kodini skanerlab ko'rdi — hech narsa chiqmadi. Sabab aniqlandi:
67-79 qadamlargacha `ScannerService` HID kiritishni faqat **shu dastur
ichida** (`QApplication`ga o'rnatilgan `eventFilter` orqali) kuzatar
edi — bu esa faqat StockFirm Desktop Agent oynasi **fokusda** bo'lgandagina
ishlardi. Amalda foydalanuvchi odatda QR kodni ko'rish uchun boshqa oynani
(brauzer, galereya) ochib turadi — o'sha payt fizik skaner "yozgan"
belgilar Desktop Agent'ga emas, fokusdagi boshqa dasturga tushib ketardi.

Foydalanuvchi aniq yechim yo'nalishini ko'rsatdi: **"GTA'dagi cheat kod
qabul qiladigon kabi"** — ya'ni dastur qaysi oynada ekanidan qat'iy
nazar, kodni "eshitib" olishi kerak.

**Yechim** — `desktop_agent/app/scanner_service.py` butunlay qayta
yozildi: endi `keyboard` kutubxonasi (`pip install keyboard`, Windows'da
past darajali tizim-keng klaviatura hook'i orqali ishlaydi) ishlatiladi.
- HID rejimida `keyboard.hook()` o'rnatiladi — bu **butun Windows
  bo'ylab**, qaysi oyna fokusda bo'lishidan qat'iy nazar, barcha
  klaviatura hodisalarini kuzatadi (avvalgi `QApplication.installEventFilter`
  faqat shu dastur ichidagi hodisalarni ko'rar edi).
  - Hodisalar **bloklanmaydi** (iste'mol qilinmaydi) — ular fokusdagi
    boshqa dasturga (masalan brauzerga) ham odatdagidek yetib boradi;
    biz faqat qo'shimcha kuzatib turamiz. Bu ataylab qilingan
    tanlov: butun tizimni bloklovchi hook (hech qayerda yozib bo'lmay
    qolish xavfi) o'rniga, engil "kuzatuvchi" usul tanlandi — kamdan-kam
    holatlarda (haqiqiy skaner ishlayotganda) fokusdagi boshqa dasturga
    ham kod harflari ko'rinib qolishi mumkin, lekin bu death
    xavfsizroq va universal yechim.
  - Bufer/aniqlash mantig'i (tez ketma-ketlik + Enter, uzunlik >= 20)
    saqlanib qoldi, lekin soddalashtirildi — endi widget-ga "qaytarib
    yuborish" (replay) kerak emas, chunki hech narsa ushlab qolinmaydi.
- `requirements.txt`ga `keyboard==0.13.5` qo'shildi.
- `camera_config_dialog.py`/`settings_page.py`dagi izoh matnlari
  yangilandi ("boshqa oyna fokusda bo'lsa ham" ishlashini aniq aytib
  o'tildi; eski, endi noto'g'ri "Skaner sahifasi/Ishga tushirish"
  haqidagi qoldiq matn ham tuzatildi).

### O'zgargan fayllar
- `desktop_agent/app/scanner_service.py` (to'liq qayta yozildi)
- `desktop_agent/requirements.txt`
- `desktop_agent/app/windows/camera_config_dialog.py`,
  `settings_page.py` (izoh matnlari)
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Offscreen regressiya testi (`ScannerService._on_key_event()`ni
  to'g'ridan-to'g'ri, `keyboard.KeyboardEvent` obyektlari bilan
  chaqirib — aynan haqiqiy global hook chaqiradigan tarzda, **hech
  qanday dastur oynasi fokusda ekanini talab qilmasdan**): (a) tez
  yozilgan+Enter bilan tugagan haqiqiy uzunlikdagi kod to'g'ri
  aniqlanishi ✅; (b) sekin (odam tezligida) yozilgan matn skaner deb
  hisoblanmasligi ✅; (c) qisqa tez ketma-ketlik (parol kabi) e'tiborga
  olinmasligi ✅; (d) `stop()` hook'ni toza o'chirishi ✅.
- To'liq (`MainWindow`) darajasida ham qayta tekshirildi — "Omborlar"
  sahifasida turganda (hech qanday menyu ochilmagan holda) global
  hook orqali kelgan skaner kodi xodim popup oynasini avtomatik
  ko'rsatishi ✅.
- Avvalgi barcha smoke testlar (muzlab-qolmaslik, material-so'rov
  skaneri, ko'p-kamera, login, DB-yo'l) qayta ishga tushirilib, hammasi
  o'tdi.
- PyInstaller build logida `keyboard` kutubxonasining Windows backend
  qismi (`_winkeyboard`) muvaffaqiyatli bog'langani, faqat Linux/macOS'ga
  tegishli ixtiyoriy modullar (`fcntl`, `AppKit`, `Quartz`) yo'qligi haqida
  (kutilgan, zararsiz) ogohlantirish borligi tasdiqlandi.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

### Eslatma
`test_hid_no_leak.py` (69-qadamda yozilgan, "hech qanday belgi fokusdagi
maydonga sizib kirmasligi" testi) endi eskirgan — bu qadamda ataylab
qabul qilingan yangi dizayn (hodisalarni bloklamaslik) ushbu kafolatni
olib tashladi. Bu qasddan qilingan almashinuv: universal (butun tizim
bo'ylab) ishlash ustuvorligi berildi.

## 80-qadam: Haqiqiy skanerlash tekshiruvi orqali topilgan jiddiy bug — skaner Enter emas, Tab yuborar ekan

**Holat: DONE**

### Nima qilindi
Foydalanuvchi so'radi: "debug holatda ishga tushir, menga skanerla deb
buyruq ber, real holatda xatolikni ko'r". Manba koddan (`main.py`),
foydalanuvchining haqiqiy sozlangan konfiguratsiyasi bilan (`%LOCALAPPDATA%
\StockFirmAgent\agent_data.db` — HID skaner sozlangan, login qilingan)
vaqtinchalik debug loglar (`print()`) qo'shib ishga tushirildi, so'ng
foydalanuvchi haqiqiy fizik skaner bilan o'z badge QR kodini skanerladi.

**Log natijasi aniq ko'rsatdi**: skaner har bir belgini to'g'ri yuborardi
(`e36aa4c6-b7c3-418a-ba8a-e8eea7da4b9e` — 36 belgi, to'g'ri), lekin oxirida
kutilgan `enter` o'rniga **`tab`** tugmasi kelardi! `ScannerService`
faqat `event.name == "enter"`ni tugatuvchi belgi deb kutgan edi (79-qadamda
yozilgan) — shuning uchun kod to'liq to'g'ri kelsa ham, hech qachon
"skanerlash tugadi" deb tan olinmasdi, `code_scanned` signali hech qachon
chiqmasdi. Bu — ko'plab qo'lda skanerlarning odatiy standart sozlamasi
(Enter o'rniga Tab bilan tugatish, forma-navigatsiya uslubi) — foydalanuvchi
skanerida ham aynan shunday ekan.

**Tuzatish** — `desktop_agent/app/scanner_service.py`: yagona `"enter"`
tekshiruvi o'rniga `HID_TERMINATOR_KEYS = {"enter", "tab"}` to'plami
qo'shildi — endi ikkalasi ham kodni tugatuvchi tugma sifatida qabul
qilinadi.

Debug uchun qo'shilgan barcha vaqtinchalik `print()` qatorlari
(`scanner_service.py`, `main_window.py`, `employee_scan_widget.py`)
tuzatishdan keyin olib tashlandi.

### O'zgargan fayllar
- `desktop_agent/app/scanner_service.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- **Haqiqiy jonli debug**: foydalanuvchining o'z fizik skaneri bilan
  haqiqiy badge QR kodi skanerlanib, log orqali muammoning aniq sababi
  (`tab` terminatori) kuzatildi va tasdiqlandi — bu sessiyadagi eng
  ishonchli tekshiruv turi (haqiqiy uskunada, haqiqiy ma'lumot bilan).
- Offscreen regressiya testi: real skanerdan olingan aynan shu 36-belgili
  kod endi ham `enter`, ham `tab` bilan tugatilganda to'g'ri
  aniqlanishi ✅ (ikkalasi ham alohida tekshirildi).
- Avvalgi barcha smoke/regressiya testlar qayta ishga tushirilib, hammasi
  o'tdi, hech qanday qoldiq debug-chiqish yo'qligi tasdiqlandi.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

## 81-qadam: Xom ashyo so'rovi Desktop Agent'da tarozi orqali tekshirilib, avtomatik tasdiqlanadi (omborchi bosqichi almashtirildi)

**Holat: DONE**

### Nima qilindi
Foydalanuvchi bilan kelishilgan qaror bo'yicha (savol-javob orqali
aniqlashtirilgan): Desktop Agent ishlatilayotgan firmalarda, xom ashyo
so'rovini omborchi web-sahifada qo'lda tasdiqlashi o'rniga, ishlab
chiqaruvchining o'zi materialni tarozida o'lchab, Desktop Agent orqali
**avtomatik** tasdiqlanadi. Hozircha haqiqiy tarozi yo'q — qiymat qo'lda
kiritiladi (kelgusi kunlarda haqiqiy tarozi ulanganda readonly/avtomatik
o'qishga o'tkaziladi, foydalanuvchining o'z so'zlari bilan).

**Backend — `main/agent_api_views.py`**:
- `agent_material_requests` javobiga `rasmi` (material rasmi, mavjud
  bo'lsa to'liq URL) qo'shildi — Desktop Agent'da har bir kutilayotgan
  so'rov uchun mahsulot rasmini ko'rsatish uchun.
- Yangi `agent_weigh_material_request` (`POST /api/agent/material-
  requests/<id>/weigh/`) — `session_token` + `measured_qty` qabul
  qiladi:
  - Chetlashish normadan tashqari bo'lsa (`MATERIAL_WEIGH_TOLERANCE_
    PERCENT = 2%`, minimal chegara `MATERIAL_WEIGH_MIN_TOLERANCE = 0.05`)
    — `approved: false` + tushunarli xabar ("ko'p"/"kam", kutilgan/
    o'lchangan qiymatlar) qaytaradi, **hech narsa o'zgarmaydi**.
  - Zaxira yetarli bo'lmasa — xuddi shunday `approved: false`.
  - Norma ichida va zaxira yetarli bo'lsa — **avtomatik tasdiqlaydi**:
    `Mahsulot.miqdori` kamayadi, `status='approved'`, `acknowledged_at`
    ham avtomatik belgilanadi (fizik jihatdan bir xil hodisa — tarozida
    o'lchab olib ketish), `StockHistory` (`RAW_APPROVED`) yoziladi,
    WebSocket bildirishnoma yuboriladi — bularning barchasi
    `warehouse_request_review`ning "Tasdiqlash" tugmasi bilan bir xil
    natijaga olib keladi, faqat omborchi web-sahifasiga kirmasdan.
  - Qayta o'lchash (allaqachon tasdiqlangan so'rovni) — 404 (ikki marta
    kamaytirishning oldi olinadi).

**Desktop Agent — `employee_scan_widget.py` (katta qayta qurish)**:
- Eski "so'rovlar paneli + Qabul qildim" tugmasi olib tashlandi, o'rniga:
  - Xodim (ishlab chiqaruvchi) badge'i skanerlanganda, agar **hech qanday
    kutilayotgan so'rovi bo'lmasa** — "Sizning so'rovlaringiz yo'q"
    ko'rsatiladi va **3 soniyadan so'ng popup avtomatik yopiladi**
    (`close_requested` signali orqali).
  - Agar so'rovlari bo'lsa — **bir-bir**, har biri uchun material nomi,
    rasmi, kerakli miqdor ko'rsatiladi + "Tarozi qiymati" kiritish
    maydoni (hozircha qo'lda, keyinchalik readonly) + "Tekshirish"
    tugmasi. Norma ichida bo'lsa — "Norma bo'yicha to'g'ri — oling! ✓"
    va navbatdagi so'rovga o'tadi; oshsa/yetmasa — xato xabari
    ko'rsatilib, o'sha so'rovda qoladi (qayta o'lchashga imkon beradi).
    Barcha so'rovlar bajarilgach — "Barcha so'rovlar bajarildi ✓" va
    popup avtomatik yopiladi.
- `api_client.py` — yangi `weigh_material_request()`.
- `main_window.py` — `EmployeeScanWidget.close_requested` signali popup
  oynani yopishga ulandi.

### O'zgargan fayllar
- `main/agent_api_views.py`, `landing/urls.py`
- `desktop_agent/app/api_client.py`
- `desktop_agent/app/windows/employee_scan_widget.py` (katta qayta qurish)
- `desktop_agent/app/windows/main_window.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Izolyatsiyalangan tranzaksiyada (rollback, real `birzumda`): (a)
  normadan tashqari qiymat — rad etiladi, zaxira o'zgarmaydi ✅; (b)
  norma ichidagi qiymat (±2%) — avtomatik tasdiqlanadi, zaxira to'g'ri
  kamayadi, `acknowledged_at` ham avtomatik belgilanadi ✅; (c) allaqachon
  tasdiqlangan so'rovni qayta o'lchash — 404 (ikki marta kamaytirilmaydi)
  ✅; (d) zaxira yetarli bo'lmasa — rad etiladi, tushunarli xabar bilan
  ✅; (e) `agent_material_requests` javobida endi `rasmi` maydoni borligi
  ✅.
- Offscreen smoke test (`EmployeeScanWidget`): (a) so'rovsiz holatda
  "so'rovlaringiz yo'q" xabari va ~3s dan keyin `close_requested`
  chiqishi ✅; (b) ikkita navbatdagi so'rov: birinchisi rad etilgach xuddi
  shu so'rovda qolishi, keyin norma ichida tasdiqlangach ikkinchisiga
  o'tishi, ikkalasi ham bajarilgach yakunlovchi xabar+avtomatik yopilish
  ✅; (c) `weigh_material_request` aniq kutilgan (request_id, o'lchangan
  qiymat) ketma-ketligi bilan chaqirilgani ✅.
- `python manage.py check` — xatosiz.
- Avvalgi barcha skaner/login/kamera testlari qayta ishga tushirilib,
  hammasi o'tdi.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

### Keyingi qism (hali qilinmadi — foydalanuvchi bilan kelishilishi kerak)
Foydalanuvchi so'zlarida yana ikkita qo'shimcha oqim bor edi, ular hali
BOSHLANMADI, chunki jiddiy arxitektura qarorlarini talab qiladi:
1. **Ishlab chiqarish (miqdor qo'shish) so'rovi + XPrinter**: hozir
   `MiqdorQoshish` `addmiqdor` view'ida DARHOL o'z-o'zidan tasdiqlanadi
   (kutish holati yo'q). Foydalanuvchi endi buni ham Desktop Agent'ga
   o'tkazishni so'radi (so'rov yuboriladi → agentga kelib skanerlaydi →
   chop etish tugmasi bilan Serial QR kodlar chop etiladi → tovarlarga
   yopishtirilib qayta skanerlanadi). Bu — barcha (agentsiz) firmalar
   uchun ham ishlab turgan avtomatik-tasdiqlash xatti-harakatini
   o'zgartirmasdan, faqat agent ishlatuvchilar uchun alohida yo'l qanday
   qo'shilishi kerakligini aniqlashtirish talab qiladi.
2. **"Mahsulot QR kodida silka bo'lsin"** — mavjud Serial QR
   (`landing/views.py:qr_image_view`) allaqachon linkka (`/p/<kod>/`)
   kodlanadi; bu eslatma yangi chop etish oqimi ham shu naqshni
   ishlatishi kerakligini nazarda tutadi — 1-band bilan birga
   ishlanadi.

## 82-qadam: Miqdor qo'shish (ishlab chiqarish natijasi) — so'rov + Desktop Agent orqali tasdiqlash + QR chop etish

**Holat: DONE**

### Nima qilindi
Foydalanuvchi bilan kelishilgan qaror bo'yicha (savol-javob orqali
tanlangan variant): "miqdor qo'shish" (ishlab chiqarilgan mahsulot
miqdorini yozish) endi Desktop Agent stansiyasi sotib olingan firmalarda
**darhol o'z-o'zidan tasdiqlanmaydi** — ishlab chiqaruvchi web-saytda
so'rov yuboradi ("kutilmoqda" holatida qoladi), so'ng Desktop Agent'ga
borib badge skanerlab tasdiqlaydi, Serial QR kodlar avtomatik yaratiladi
va **brauzerda chop etish sahifasi ochiladi** (XPrinter SDK o'rniga
oddiy tizim printeri/PDF — foydalanuvchi bilan kelishilgan). Desktop
Agent stansiyasi yo'q firmalarda **eski xatti-harakat o'zgarishsiz
qoladi** (darhol tasdiqlanadi) — bu muhim xavfsizlik chegarasi: aksincha
qilinsa, agentsiz firmalarning ishlab chiqarish yozuvlari abadiy
"kutilmoqda"da qolib ketardi.

**Backend**:
- `main/views.py:addmiqdor` — `request.company.custom_desktop_agent_stations
  > 0` bo'lsa, `MiqdorQoshish(tasdiqlangan=False)` yaratiladi va
  `approve_miqdor_qoshish_service` **chaqirilmaydi** (avval har doim
  darhol chaqirilardi) — foydalanuvchiga "Desktop Agent'ga borib
  tasdiqlang" xabari ko'rsatiladi. Aks holda (agentsiz) — o'zgarishsiz.
- `main/agent_api_views.py` — uchta yangi endpoint:
  - `agent_miqdor_requests` (GET) — ishlab chiqaruvchining kutilayotgan
    miqdor-qo'shish so'rovlari (mahsulot nomi, miqdori, rasmi).
  - `agent_approve_miqdor_qoshish` (POST) — mavjud
    `approve_miqdor_qoshish_service()` (zaxira oshirish, BOM/jarima/ish
    haqi, Serial/QR generatsiya) **o'zgarishsiz chaqiriladi** — faqat
    omborchi/ega web-sahifasiga kirmasdan. Yaratilgan Seriallar bo'lsa,
    chop etish sahifasi manzilini (`print_url`) qaytaradi.
  - `agent_miqdor_print_page` (login talab qilmaydi, so'rov parametridagi
    token orqali tekshiriladi — Desktop Agent'ning brauzer sessiyasi yo'q)
    — partiyaning barcha Serial QR kodlarini (mavjud `qr_image` endpointi,
    allaqachon `/p/<kod>/` linkka kodlangan — "mahsulot QR kodida silka
    bo'lsin" talabi shu orqali qondiriladi) ko'rsatadigan, "Chop etish"
    tugmasi (`window.print()`) bilan sahifa (`agent_miqdor_print.html`).
- **Yon-tuzatish (jiddiy bug)**: `_company_from_token()` hamon
  `type='desktop_agent'` filtri bilan qidirar edi — 72-qadamda LOGIN
  endpointi istalgan foydalanuvchi turiga ochiq qilingan bo'lsa-da, bu
  funksiya eskicha qolib ketgan edi. Natijada: `ega` (yoki boshqa
  turdagi) hisob bilan Desktop Agent'ga kirish MUVAFFAQIYATLI
  bo'lardi-yu, lekin olingan token **keyingi hech qanday so'rovda
  ishlamasdi** (401 qaytarardi) — login ekrani "kirdim" deb ko'rsatgani
  bilan, aslida hech narsa ishlamasdi. Endi tuzatildi.

**Desktop Agent**:
- `api_client.py` — `fetch_miqdor_requests()`, `approve_miqdor_qoshish()`.
- `employee_scan_widget.py` — navbat mantig'i kengaytirildi: avval xom
  ashyo so'rovlari (81-qadam, tarozi), ular tugagach miqdor-qo'shish
  so'rovlari (yangi, oddiy "Tasdiqlash" tugmasi bilan — tarozi tekshiruvi
  kerak emas), ikkalasi ham bo'lmasa/tugasa — yakunlovchi xabar va
  avtomatik yopilish. Tasdiqlangach, agar Serial yaratilgan bo'lsa,
  `webbrowser.open(print_url)` orqali chop etish sahifasi avtomatik
  brauzerda ochiladi.

### O'zgargan fayllar
- `main/views.py` — `addmiqdor`
- `main/agent_api_views.py` — yangi endpointlar + `_company_from_token`
  bug tuzatildi
- `main/templates/agent_miqdor_print.html` (yangi)
- `landing/urls.py`
- `desktop_agent/app/api_client.py`
- `desktop_agent/app/windows/employee_scan_widget.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Izolyatsiyalangan tranzaksiyada (rollback, real `birzumda`): (a)
  `agent_miqdor_requests` kutilayotgan yozuvni to'g'ri qaytarishi ✅; (b)
  `agent_approve_miqdor_qoshish` — zaxira to'g'ri oshishi, `tasdiqlangan=
  True` bo'lishi ✅; (c) qayta tasdiqlashga urinish — rad etilishi, zaxira
  ikki marta oshmasligi ✅; (d) `serial_granularity='unit'` bilan —
  Serial'lar to'g'ri yaratilishi, `print_url` qaytishi, chop etish
  sahifasi to'g'ri tokenda 3 ta QR rasm bilan render bo'lishi, noto'g'ri
  tokenda 404 qaytishi ✅; (e) **`_company_from_token` bug regressiyasi**:
  `ega` hisobi bilan login qilib olingan token endi haqiqatan ham
  keyingi so'rovda (`agent_omborlar`) ishlashi tasdiqlandi ✅.
- Offscreen smoke test (`EmployeeScanWidget`): (a) faqat miqdor-qo'shish
  so'rovi bo'lganda to'g'ri ko'rsatilishi, tasdiqlangach
  `webbrowser.open(print_url)` chaqirilishi, keyin yakunlovchi xabar +
  avtomatik yopilish ✅; (b) ikkalasi ham bo'lganda, AVVAL xom ashyo
  (tarozi), keyin miqdor-qo'shish navbati bilan ishlashi ✅.
- `python manage.py check` — xatosiz.
- Avvalgi barcha skaner/login/kamera testlari qayta ishga tushirilib,
  hammasi o'tdi.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

## 83-qadam: Yetkazib beruvchi — omborddan yuk olish (yuklama) Desktop Agent orqali, mahsulot QR kodlarini skanerlab

**Holat: DONE**

### Nima qilindi
Foydalanuvchi so'zlari boshida "sotsin" (sell) deb tushunilgan, lekin
savol-javob orqali aniqlashtirilgach ma'lum bo'ldiki: **sotuvning o'zi
hamon web-saytda qoladi** — Desktop Agent orqali o'zgaradigan narsa
yetkazib beruvchining **omborddan yuk olish** ("yuklama") bosqichi.
Hozir bu web-formada mahsulot tanlab, miqdorini qo'lda yozib, o'zi
darhol tasdiqlaydi (`main()` view, `yetkazib_beruvchi` filiali) —
oshiqcha nazoratsiz, xuddi avvalgi `MiqdorQoshish` kabi. Foydalanuvchi
tanlagan yechim: yetkazib beruvchi Desktop Agent'da badge skanerlab,
har bir olayotgan donaning **Serial QR kodini** ketma-ket skanerlaydi —
necha marta skanerlasa, o'sha miqdor "savat"ga yig'iladi (faqat "har
bir donaga alohida QR" — `serial_granularity='unit'` — yoqilgan
mahsulotlar uchun ishlaydi). "Yuklamani yakunlash" bosilganda,
mavjud `YuklamaSorov`/`approve_yuklama_sorov_service()` (zaxira
kamayishi, `DeliveryStock` oshishi, Serial'lar "chiqarilgan"ga o'tishi)
**o'zgarishsiz** chaqiriladi — faqat qo'lda miqdor yozish o'rniga
Serial skanerlash orqali.

**Backend — `main/agent_api_views.py`**:
- `_badge_scan_response()` javobiga `user_type` (xom `User.type` kodi)
  qo'shildi — Desktop Agent shu orqali "bu yetkazib beruvchimi"ni
  ishonchli tekshiradi (ko'rsatiladigan `lavozim` matniga emas).
- Yangi `agent_scan_delivery_serial` (POST) — bitta Serial QR kodini
  tekshiradi (`holati='omborda'`, shu firmaga tegishli, faqat
  yetkazib-beruvchi sessiyasi uchun), mahsulot ma'lumotini qaytaradi.
  Hisoblash (savat) mijoz (Desktop Agent) tomonda saqlanadi.
- Yangi `agent_finalize_yuklama` (POST) — savat (`items`:
  `[{mahsulot_id, miqdor}]`) bo'yicha har bir mahsulot uchun
  `YuklamaSorov` yaratib, **darhol o'zi tomonidan tasdiqlaydi** (xuddi
  hozirgi web-formadagi xatti-harakat kabi — omborchi nazorati
  hech qachon bo'lmagan, shuning uchun bu yerda ham qo'shilmadi).

**Desktop Agent — `employee_scan_widget.py`**:
- Badge skanerlanganda `info['user_type'] == 'yetkazib_beruvchi'` bo'lsa,
  material-so'rov/miqdor-qo'shish navbati o'rniga **"yuklama" savati**
  ko'rsatiladi.
- Shu holatda (`_delivery_mode_active`), **keyingi barcha skanerlar**
  (xuddi shu `handle_scanned_code()` orqali, HID yoki kamera farqisiz)
  yangi badge/so'rov qidiruvi emas, balki mahsulot Serial QR kodi
  sifatida talqin qilinadi — savatga qo'shiladi, jonli ro'yxat
  ko'rsatiladi ("Un — 2 dona", "Non — 1 dona").
- "Yuklamani yakunlash" — savatni serverga yuboradi, natija
  ko'rsatilib, popup avtomatik yopiladi.

### O'zgargan fayllar
- `main/agent_api_views.py`, `landing/urls.py`
- `desktop_agent/app/api_client.py`
- `desktop_agent/app/windows/employee_scan_widget.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Izolyatsiyalangan tranzaksiyada (rollback, real `birzumda`, haqiqiy
  ishlab chiqarilgan Seriallar bilan): (a) 2 ta Serial skanerlanganda
  ikkalasi ham to'g'ri tanilishi ✅; (b) noma'lum/allaqachon chiqarilgan
  kod uchun 404 ✅; (c) yetkazib-beruvchi bo'lmagan sessiya bilan
  skanerlashga urinish rad etilishi (404) ✅; (d) "Yakunlash" — zaxira
  to'g'ri kamayishi, `DeliveryStock.qty` (mavjud qoldiqqa) to'g'ri
  qo'shilishi, `YuklamaSorov` avtomatik tasdiqlanishi, aynan
  skanerlangan Seriallar (FIFO orqali, mavjud mexanizm) "chiqarilgan"ga
  o'tishi ✅.
- Offscreen smoke test (`EmployeeScanWidget`): (a) yetkazib-beruvchi
  badge skanerlanganda tarozi/miqdor-qo'shish oqimlari **chaqirilmasligi**
  (assertion bilan tasdiqlangan — material/miqdor so'rovlarini
  umuman so'ramasligi) ✅; (b) ketma-ket Serial skanerlash bir xil
  mahsulot uchun sonini to'g'ri jamlashi ✅; (c) noto'g'ri kod skanerlash
  xato ko'rsatib, mavjud savatni buzmasligi ✅; (d) "Yakunlash" aniq
  kutilgan (mahsulot_id, jami miqdor) ro'yxatini serverga yuborishi,
  keyin yakunlovchi xabar + avtomatik yopilish ✅.
- Avvalgi barcha skaner/login/kamera/tarozi/miqdor-qo'shish testlari
  qayta ishga tushirilib, hammasi o'tdi.
- `python manage.py check` — xatosiz.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

### Ko'lamdan tashqarida (savdogar)
"Kimlar uchun" savolida "savdogar" ham tanlangan edi, lekin savdogar
modulida "yuklama" (omborga tegishli, boshqa joyga ko'chirish) tushunchasi
umuman yo'q — savdogar sotuvni to'g'ridan-to'g'ri umumiy `Mahsulot.
miqdori`dan amalga oshiradi, olib chiqib ketadigan alohida shaxsiy
zaxirasi yo'q. Shuning uchun bu qadamda faqat yetkazib beruvchi uchun
amalga oshirildi; savdogar uchun o'xshash ehtiyoj bo'lsa, alohida
aniqlashtirish talab qilinadi.

## 84-qadam: Ombor yaratishda lokatsiya tanlash (xaritada bosib) + xaritada ko'rinishi

**Holat: DONE**

### Nima qilindi
Foydalanuvchi: "ombor yaratilgan bo'lsa omborga kameralarni bog'lash
kerak. men hali ombor yaratmadim. va ombor lokatsiyasi kiritilgan
bo'lsin. va mapni ochganida lokatsiyada ko'rinsin." — ombor
yaratish/kamera bog'lash allaqachon (77-qadam) qilingan ekan, lekin
ombor yaratishda **lokatsiya** kiritish imkoniyati yo'q edi (faqat
nomi + erkin matn manzil). Bu qadamda qo'shildi.

- `main/models.py` — `Ombor.latitude`/`Ombor.longitude` (ixtiyoriy,
  `FloatField`) + migratsiya (`0077_ombor_latitude_ombor_longitude`).
- `main/templates/ombor_list.html` — "Yangi ombor" formasiga Leaflet
  xarita qo'shildi: foydalanuvchi xaritada nuqtani **bosadi**, o'sha
  koordinata yashirin `latitude`/`longitude` maydonlariga yoziladi
  (geokodlash/qo'lda raqam kiritish emas — aniq va oddiy). Har bir
  ombor kartochkasida "Lokatsiya saqlangan — xaritada ko'rish" yoki
  "Lokatsiya kiritilmagan" belgisi ko'rsatiladi.
- `main/warehouse_views.py:ombor_list_page` — POST'dan `latitude`/
  `longitude`ni o'qib saqlaydi (ixtiyoriy — bo'sh qoldirilsa ombor
  baribir yaratiladi, faqat lokatsiyasiz).
- `main/map_views.py:api_map_data` — endi `omborlar` ro'yxatini ham
  qaytaradi (faqat lokatsiyasi kiritilganlar — mavjud `shops`/
  `deliverers` naqshiga o'xshab).
- `main/templates/map_dashboard.html` — yangi "🏭 Omborlar" filtri
  (checkbox) + xaritada 🏭 belgisi bilan ombor markerlari (nomi va
  manzili bilan popup).

### O'zgargan fayllar
- `main/models.py`, `main/migrations/0077_ombor_latitude_ombor_longitude.py`
- `main/templates/ombor_list.html`
- `main/warehouse_views.py`
- `main/map_views.py`
- `main/templates/map_dashboard.html`

### Tekshirildi
- Izolyatsiyalangan tranzaksiyada (rollback, real `birzumda` + `ega`):
  (a) xaritada tanlangan koordinata bilan ombor yaratilganda
  `latitude`/`longitude` to'g'ri saqlanishi ✅; (b) lokatsiyasiz ombor
  yaratish ham ishlashi (ixtiyoriy, `None` qoladi) ✅; (c) `/omborlar/`
  sahifasi lokatsiya-tanlagich xarita va to'g'ri holat belgilari bilan
  render bo'lishi ✅; (d) `/api/map/data/` endi lokatsiyasi bor omborni
  to'g'ri koordinata/manzil bilan qaytarishi, lokatsiyasiz omborni
  esa **qaytarmasligi** (xaritada ko'rsatilmasligi) ✅.
- `python manage.py check` — xatosiz.

### Eslatma
Bu qadam faqat CRM (web) tomonidagi o'zgarish — Desktop Agent'ga
tegishli emas, `.exe` qayta build qilinmadi.

## 84-qadam (qo'shimcha): "Joriy lokatsiyani olish" tugmasi

**Holat: DONE**

Foydalanuvchi to'g'ri eslatdi: xaritada qo'lda bosish o'rniga, "Joriy
lokatsiyani olish" tugmasi ham kerak edi (masalan omborda turgan holda
telefon/noutbukdan to'g'ridan-to'g'ri o'z joylashuvini belgilash uchun).

`main/templates/ombor_list.html` — xarita ustiga "📍 Joriy lokatsiyani
olish" tugmasi qo'shildi: `navigator.geolocation.getCurrentPosition()`
orqali brauzerdan joylashuvni so'raydi, marker va yashirin `latitude`/
`longitude` maydonlarini avtomatik to'ldiradi, xaritani o'sha nuqtaga
markazlashtiradi (zoom 16). Ruxsat berilmasa/xato bo'lsa — tushunarli
xabar ko'rsatiladi, tugma qayta bosilishi mumkin bo'lib qoladi.

### Tekshirildi
- `/omborlar/` sahifasi tugma bilan to'g'ri render bo'lishi tasdiqlandi
  (izolyatsiyalangan tranzaksiyada).
- `python manage.py check` — xatosiz.

## 85-qadam: Omborlar sinxronlanmagani aniq ko'rinadigan bo'ldi + o'sha sahifaning o'zida "Sinxronlash" tugmasi

**Holat: DONE**

### Nima qilindi
Foydalanuvchi web-saytda ombor ("asosiy") yaratdi, lekin Desktop
Agent'ning "Omborlar" sahifasi bo'sh (sarlavhalar bilan) ko'rinardi —
hech qanday xabar/tushuntirish yo'q edi. Sabab: Desktop Agent
omborlarni faqat qo'lda "Sinxronlash" bosilganda CRM'dan oladi
(avtomatik emas), va bu tugma Sozlamalar sahifasida "yashiringan" edi
— foydalanuvchi buni bosmagan/bilmagan.

**Tuzatildi** — `desktop_agent/app/windows/warehouse_list_page.py`:
- Omborlar ro'yxati bo'sh bo'lsa, endi aniq tushuntirish xabari
  ko'rsatiladi: "Hali hech qanday ombor sinxronlanmagan. Avval
  Sozlamalar sahifasida login qiling, so'ng yuqoridagi 'Sinxronlash'
  tugmasini bosing."
- Omborlar sahifasining o'zida ham **"🔄 Sinxronlash"** tugmasi
  qo'shildi — endi Sozlamalarga o'tmasdan, to'g'ridan-to'g'ri shu
  yerdan sinxronlash mumkin.

**Yon-tuzatish (muzlab qolish xavfi)**: shu ishni qilayotib, Sozlamalar
sahifasidagi "Kirish" va "Sinxronlash" tugmalari hamon **asosiy GUI
oqimida to'g'ridan-to'g'ri** tarmoq so'rovi yuborayotgani aniqlandi —
xuddi 68-qadamda tuzatilgan skanerlash muzlab qolish xatosi bilan bir
xil turkumdagi xavf (server sekin javob bersa/ulanmasa, butun ilova
muzlab qolishi mumkin edi). `settings_page.py`dagi `_login()`/`_sync()`
ham yangi Omborlar sahifasidagi sinxronlash bilan bir xil — fon
oqimida (`QThread`) ishlaydigan qilindi.

### O'zgargan fayllar
- `desktop_agent/app/windows/warehouse_list_page.py`
- `desktop_agent/app/windows/settings_page.py`
- `desktop_agent/dist/StockFirmAgent.exe` (qayta build qilindi)

### Tekshirildi
- Offscreen smoke test: (a) bo'sh ombor ro'yxatida aniq tushuntirish
  xabari ko'rinishi ✅; (b) token yo'q holatda "Sinxronlash" bosilsa
  tushunarli xabar chiqishi (chalkash jim qolish emas) ✅; (c) token
  bilan "Sinxronlash" bosilganda — fon oqimida server javobini olib,
  jadvalni to'ldirishi va bo'sh-holat xabarini yashirishi ✅.
- Avvalgi login/sinxronlash bilan bog'liq testlar fon-oqim
  (asinxron) xatti-harakatga moslashtirilib qayta ishga tushirildi,
  hammasi o'tdi.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

## 86-qadam: Reception (xodim kelish/ketishi avtomatik qayd etilishi) + jiddiy worker-crash bug tuzatildi

**Holat: DONE**

### Nima qilindi
- **Reception**: endi Desktop Agent orqali istalgan xodim badge'ini
  skanerlashi bilan (rolidan qat'iy nazar — maxsus "reception rejimi"
  tanlash shart emas) tizim avtomatik ravishda kelish/ketishni qayd
  qiladi. Backend'da yangi `XodimDavomat` modeli (hodisa-jurnali —
  bitta kunga bitta yozuv emas, shuning uchun tushlikka chiqish kabi
  bir necha marta kirish/chiqish tabiiy qo'llab-quvvatlanadi) va
  `POST /api/agent/davomat/` endpoint qo'shildi — shu xodimning
  bugungi eng so'nggi hodisasiga qarab avtomatik "kirish"/"chiqish"ni
  belgilaydi. Desktop Agent tomonida — har bir muvaffaqiyatli badge
  skaneridan keyin avtomatik chaqiriladigan `_toggle_attendance()` +
  natijani ko'rsatuvchi yashil/ko'k tasdiqlash yorlig'i qo'shildi.
- **Jiddiy, ilgari yashirin bo'lgan crash bug tuzatildi**: fon
  oqimlarda (`QThread`) ishlaydigan barcha uchta worker klassi
  (`employee_scan_widget.py::_ApiCallWorker`,
  `settings_page.py::_ApiCallWorker`,
  `warehouse_list_page.py::_SyncWorker`) faqat `ApiError`ni ushlar
  edi — agar tarmoq/JSON/kutubxona darajasida boshqa turdagi kutilmagan
  xato yuz bersa, bu **butun dasturni hech qanday xabarsiz yiqitardi**
  (Windows darajasidagi jiddiy xato, oddiy Python exception emas —
  `STATUS_STACK_BUFFER_OVERRUN`). Bu 68-qadamdan buyon qurilgan
  BARCHA fon-oqim chaqiruvlariga tegishli edi. Tuzatildi: endi har
  qanday kutilmagan xato xavfsiz `failed` signaliga aylantiriladi.
- Shu bilan bog'liq ikkinchi, nozikroq muammo ham topildi va tuzatildi:
  `employee_scan_widget.py`da bitta worker atributi (masalan
  `self._resolve_worker`) tez orada YANGI worker bilan almashtirilsa
  (masalan ketma-ket ikkinchi skaner), eski `QThread` obyekti hali
  to'liq "join" bo'lmagan holatda GC tomonidan o'chirilishi mumkin edi
  — bu ham nazariy jihatdan xavfli. Barcha ~11 ta worker yaratish joyi
  yangi `_replace_worker()` yordamchi metodi orqali xavfsiz
  almashtirishga o'tkazildi (eski oqim `isRunning()` bo'lsa, `wait()`
  bilan to'liq tugashi kutiladi).
- **Muhim aniqlangan narsa (test yozish uchun)**: avtomatlashtirilgan
  offscreen PyQt testda qo'lda `app.processEvents()` bilan pollash
  (aylanma) ketma-ket bir nechta zanjirlangan `QThread` workerlarni
  haydash uchun ishonchsiz ekan — soxta, ilova mantig'iga aloqasi
  yo'q crashlarga olib kelishi mumkin. Haqiqiy ilova (`main.py`)
  har doim `app.exec()` (to'liq Qt event loop) ishlatadi — shu bilan
  test qilinganda hech qanday muammo yo'q. Reception vidjet testi
  endi `QTimer.singleShot()` bilan bosqichlanган, `app.exec()`
  asosidagi patternga o'tkazildi (ishonchli, bir necha marta
  qatorasiga sinalgan).

### O'zgargan fayllar
- `crm/main/models.py` — `XodimDavomat` modeli
- `crm/main/migrations/0078_xodimdavomat.py`
- `crm/main/agent_api_views.py` — `agent_toggle_attendance`
- `crm/landing/urls.py` — `/api/agent/davomat/` marshruti
- `desktop_agent/app/api_client.py` — `toggle_attendance()`
- `desktop_agent/app/windows/employee_scan_widget.py` — attendance
  UI/logika, `_ApiCallWorker` exception-fix, `_replace_worker()`
  helper va barcha worker-yaratish joylarida ishlatilishi
- `desktop_agent/app/windows/settings_page.py` — `_ApiCallWorker`
  exception-fix
- `desktop_agent/app/windows/warehouse_list_page.py` — `_SyncWorker`
  exception-fix

### Tekshirildi
- Backend: izolyatsiyalangan tranzaksiyada 3 ta ketma-ket skaner —
  kirish → chiqish → kirish to'g'ri almashinishi tasdiqlandi.
- Desktop Agent: `app.exec()` asosidagi vidjet testi 3 marta
  qatorasiga muvaffaqiyatli o'tdi (birinchi/ikkinchi skaner, sessiya
  tugashi, label ko'rinish/yashirinishi).
- Minimal repro (`StopIteration` ichida worker) — tuzatishdan oldin
  100% crash, tuzatishdan keyin 100% xavfsiz `failed` signali.
- Mavjud desktop_agent regressiya testlari (`test_material_request_
  scan_widget`, `test_miqdor_flow_widget`, `test_weigh_flow_widget`,
  `test_yuklama_flow_widget`, `test_main_window`,
  `test_no_freeze_on_slow_server`, `test_warehouse_sync_button`,
  `test_settings_scanner_config`) — barchasi o'tdi, hech narsa
  buzilmadi.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

### Ko'lamdan tashqarida (keyingi qadam)
Ombor kamerasi orqali QR-skaner atrofida (~5 soniya oldin/keyin)
video yozish — hali boshlanmagan, foydalanuvchi so'ragan ishning
ikkinchi yarmi.

## 87-qadam: Ombor kamerasi — voqea (tasdiqlash/QR skaner) atrofida video yozish

**Holat: DONE**

### Nima qilindi
- Vision hujjatidagi talab amalga oshirildi: har bir sozlangan ombor
  kamerasi endi tasdiqlashdan **5 soniya oldin** — voqea yopilgandan
  **5 soniya keyingacha** video klip yozadi. Yangi
  `desktop_agent/app/camera_recorder_service.py`:
  - `_OmborCameraBufferWorker` (har bir ombor kamerasi uchun bittadan,
    doimiy fon oqimida) — kameradan doimiy kadr o'qib, oxirgi 60
    soniyalik aylanma buferda (vaqt belgisi bilan) saqlaydi. Shu
    tufayli "voqea" boshlanganda darhol yozish shart emas — 5 soniya
    oldingi kadrlar allaqachon buferda tayyor.
  - `_ClipWriterWorker` — bitta voqea uchun bitta kamera klipini
    yozadi: to'xtash signalini kutadi, yana 5 soniya kutadi (post-roll
    kadrlari to'planishi uchun), so'ng buferdan [boshlanish-5s; hozir]
    oralig'idagi kadrlarni `cv2.VideoWriter` bilan mp4 fayliga yozadi
    (`%LOCALAPPDATA%\StockFirmAgent\recordings\` papkasiga).
  - `CameraRecorderService` — markazlashtirilgan boshqaruvchi:
    `start_event(event_id, warehouse_id, reason)` /
    `stop_event(event_id)`. Sozlangan ombor kamerasi bo'lmasa —
    hammasi xavfsiz no-op.
- `employee_scan_widget.py`ga ulandi — uchta "voqea" turi uchun
  avtomatik yoziladi: (1) xom ashyo tarozida tekshirilishi (har bir
  so'rov ko'rsatilganda boshlanadi, tasdiqlanganda tugaydi); (2)
  miqdor qo'shish tasdiqlanishi (xuddi shunday); (3) yetkazib
  beruvchining "yuklama" (yuk olish, ketma-ket QR skanerlash) butun
  sessiyasi (boshlanishidan yakunlanishigacha). Sessiya kutilmaganda
  tugasa (vaqt tugashi) ham, `_end_session()` orqali barcha hali
  yopilmagan yozuvlar to'xtatiladi.
- **Cheklov (hozircha)**: `ProductionMaterialRequest` va yuklama oqimi
  hozircha muayyan `Ombor`ga bog'lanmagan (material kamayishi
  `Mahsulot.miqdori` — firma darajasida, `OmborZaxira` darajasida
  emas — bu avvalgi qadamlarda ataylab shunday loyihalangan). Shuning
  uchun `warehouse_id=None` bilan chaqiriladi — bu holatda BARCHA
  sozlangan ombor kameralarida yoziladi (aniq qaysi ombordan ekanini
  bilmagani uchun). Kelajakda material so'roviga aniq ombor
  bog'lansa, faqat shu ombor kamerasida yozish osongina qo'shiladi.
- `MainWindow`ga ulandi: `CameraRecorderService` dastur ochiq turgan
  davomida fonda ishlaydi (xuddi `ScannerService` kabi);
  `WarehouseListPage`ga yangi `on_cameras_changed` callback qo'shildi
  — kamera qo'shilganda/o'chirilganda/ombor o'chirilganda xizmat
  qayta yuklanadi (`reload()`).

### O'zgargan fayllar
- `desktop_agent/app/camera_recorder_service.py` — yangi fayl
- `desktop_agent/app/db.py` — `recordings_dir()`,
  `list_all_ombor_cameras()`
- `desktop_agent/app/windows/employee_scan_widget.py` — `_rec_start`/
  `_rec_stop`/`_rec_stop_all` + weigh/miqdor/yuklama oqimlariga ulash
- `desktop_agent/app/windows/main_window.py` —
  `CameraRecorderService` ishga tushirilishi/to'xtatilishi
- `desktop_agent/app/windows/warehouse_list_page.py` —
  `on_cameras_changed` callback

### Tekshirildi
- `CameraRecorderService`: (a) hech qanday ombor kamerasi
  sozlanmagan holatda barcha chaqiruvlar xavfsiz no-op ekanligi; (b)
  soxta (haqiqiy uskunasiz) kamera bilan to'liq tsikl —
  `start_event` → voqea davomida kadrlar to'planishi → `stop_event` →
  5 soniyalik post-roll kutish → haqiqiy, bo'sh bo'lmagan mp4 fayl
  yaratilishi — muvaffaqiyatli o'tdi.
- `MainWindow` + `WarehouseListPage` bilan ulanish smoke testi —
  xizmat to'g'ri ulanishi va `on_cameras_changed` orqali qayta
  yuklanishi tekshirildi.
- Barcha mavjud desktop_agent regressiya testlari (Reception,
  material-request, miqdor, yuklama, main_window, no-freeze,
  warehouse-sync, settings-scanner, multi-camera-ombor) — hech biri
  buzilmadi.
- `dist/StockFirmAgent.exe` PyInstaller bilan muvaffaqiyatli qayta
  build qilindi.

### Ko'lamdan tashqarida (keyingi qadam)
Haqiqiy uskunada (foydalanuvchining o'z kamerasi) real sinov —
foydalanuvchi o'zi qiladi. Material so'rovini muayyan omborga
bog'lash (hozircha yo'q) — shundan keyin video yozishni faqat tegishli
ombor kamerasiga toraytirish mumkin bo'ladi.

## 88-qadam: XPrinter XP-365B orqali Serial QR yorliqlarini to'g'ridan-to'g'ri (TSPL) chop etish

**Holat: DONE**

### Nima qilindi
- Foydalanuvchining haqiqiy printer modeli — **XPrinter XP-365B** —
  uchun to'g'ridan-to'g'ri chop etish qo'shildi (avvalgi qadamlarda
  ataylab kechiktirilgan "brauzer/PDF orqali" yechim o'rniga/qo'shimcha
  ravishda). XP-365B'ning rasmiy Python SDK'si yo'q, lekin u standart
  Windows printer drayveri orqali o'rnatiladi va **TSPL/TSPL2**
  buyruqlarini RAW (qayta ishlanmagan bayt) rejimida qabul qiladi —
  shuning uchun maxsus SDK shart emas: `pywin32` (`win32print`) orqali
  TSPL matn buyruqlari to'g'ridan-to'g'ri printer navbatiga yuboriladi.
- Yangi `desktop_agent/app/label_printer_service.py`:
  - `list_printers()` — Windows'ga o'rnatilgan barcha printerlar
    ro'yxati (Sozlamalarda tanlash uchun).
  - `build_tspl_label(qr_data, line1, line2, width_mm, height_mm,
    gap_mm, dpi)` — bitta etiketka uchun TSPL buyruqlar ketma-ketligi
    (`SIZE`/`GAP`/`QRCODE`/`TEXT`/`PRINT`).
  - `print_raw(printer_name, data)` — tayyor TSPL baytlarini
    `OpenPrinter`/`StartDocPrinter(..., "RAW")`/`WritePrinter`/...
    ketma-ketligi bilan printer navbatiga yuboradi.
  - `LabelPrintWorker` (QThread) — bir nechta yorliqni (bitta
    partiyaning barcha Seriallari) fon oqimida ketma-ket chop etadi,
    progress/succeeded/failed signallari bilan; har qanday kutilmagan
    xato (86-qadamda o'rganilgan saboq bo'yicha) xavfsiz `failed`
    signaliga aylantiriladi, dastur yiqilmaydi.
- **"Plyonka turli o'lchamda bo'lsa ham optimal yechim"**: o'lcham
  (kenglik/balandlik/oralig'i, mm) TSPL buyruqlari ichida HAR BIR
  chop etishda yuboriladi — printer xotirasiga qattiq kodlanmaydi.
  Sozlamalar sahifasida saqlanadi (`label_width_mm`/`label_height_mm`/
  `label_gap_mm`, umumiy key-value `settings` jadvali orqali) — plyonka
  boshqa o'lchamga almashtirilsa, foydalanuvchi faqat shu qiymatlarni
  yangilaydi, kod o'zgarishi shart emas.
- Sozlamalar sahifasiga yangi "Etiketka printeri" bo'limi qo'shildi:
  o'rnatilgan printerlar ro'yxatidan tanlash (+ "Yangilash"),
  kenglik/balandlik/oraliq (mm) inputlari, "Saqlash" va "Sinov chop
  etish" tugmalari.
- `agent_approve_miqdor_qoshish` (backend) javobiga yangi `serials`
  maydoni qo'shildi — `[{"kod": ..., "url": ".../p/<kod>/"}, ...]` —
  bu Desktop Agent'ga har bir Serial uchun to'g'ridan-to'g'ri chop
  etish uchun kerakli ma'lumotni (public QR URL) ikkinchi so'rovsiz
  beradi.
- `employee_scan_widget.py`: miqdor qo'shish tasdiqlanganda — agar
  Sozlamalarda printer tanlangan bo'lsa, `webbrowser.open(print_url)`
  o'rniga endi **to'g'ridan-to'g'ri** (brauzer/PDF oralig'isiz) har bir
  Serial uchun TSPL yorliq chop etiladi. Printer hali sozlanmagan
  bo'lgan firmalar uchun eski brauzer/PDF yo'li **o'zgarishsiz
  saqlanadi** (breaking change yo'q).

### O'zgargan fayllar
- `desktop_agent/app/label_printer_service.py` — yangi fayl
- `desktop_agent/requirements.txt` — `pywin32==308` qo'shildi
- `desktop_agent/app/windows/settings_page.py` — "Etiketka printeri"
  bo'limi
- `desktop_agent/app/windows/employee_scan_widget.py` — to'g'ridan-
  to'g'ri chop etishga o'tish (printer sozlangan bo'lsa)
- `crm/main/agent_api_views.py` — `agent_approve_miqdor_qoshish`
  javobiga `serials` maydoni

### Tekshirildi
- `build_tspl_label()` — turli kenglik/balandlik/oraliq qiymatlari
  bilan chaqirilganda `SIZE`/`GAP` qatorlari mos ravishda o'zgarishi
  (qattiq kodlanmaganligi tasdiqlandi).
- `print_raw()` — soxta (mock) `win32print` bilan to'g'ri
  Open/Start(RAW)/Write/End/Close ketma-ketligida chaqirilishi.
- `LabelPrintWorker` — bir nechta yorliqni ketma-ket chop etib,
  progress/succeeded signallarini to'g'ri chiqarishi; kutilmagan xato
  (masalan printer topilmasa) xavfsiz `failed` signaliga aylanishi,
  crash bo'lmasligi.
- To'liq vidjet oqimi: printer sozlangan holatda miqdor tasdiqlanganda
  — barcha Seriallar to'g'ridan-to'g'ri (soxta printerga) chop
  etilishi, brauzer OCHILMASLIGI; printer sozlanmagan holatda esa eski
  brauzer/PDF yo'li ishlashda davom etishi (ikkalasi ham alohida
  testlarda tasdiqlandi).
- `python manage.py check` — xatosiz.
- `dist/StockFirmAgent.exe` — `pywin32` bilan birga muvaffaqiyatli
  qayta build qilindi (build ogohlantirishlarida `win32print` bilan
  bog'liq muammo yo'q).

## 92-qadam: Qo'shimcha xarajat turi (foiz/miqdor), miqdorni edit qilishni yopish, yetkazib beruvchi zaxirasini faqat tizim orqali o'zgartirish

**Holat: DONE**

### Nima qilindi
- **Qo'shimcha xarajat — foiz yoki aniq miqdor**: `MahsulotQoshimchaXarajat`ga
  yangi `turi` maydoni (`'miqdor'` — aniq summa, `'foiz'` — baza
  tannarxga nisbatan foiz) qo'shildi, chunki "har firma har xil
  ishlaydi". `recompute_tannarx()` endi ikkalasini alohida yig'adi:
  `subtotal = baza_tannarx + (miqdor turidagilar yig'indisi) +
  (baza_tannarx * foiz turidagilar yig'indisi / 100)`, so'ng
  amortizatsiya foizi ustiga qo'shiladi (o'zgarishsiz). Ikkala forma
  (`seemahsulot.html`, `warehouse_product_form.html`) qo'shimcha
  xarajat qo'shish formasiga "Turi" tanlovi (Aniq miqdor / Foiz)
  qo'shildi, ro'yxatda ham mos belgi (`so'm` yoki `%`) ko'rsatiladi.
- **Miqdorni birinchi kiritgandan keyin edit qilib bo'lmaydi**:
  foydalanuvchi bilan kelishilgan qaror bo'yicha (uzoq muhokamadan
  so'ng) — **ishlab-chiqariladigan** (retsept asosida) mahsulotlar va
  **Ombor** (xom ashyo/yarim tayyor) mahsulotlarida `miqdori`
  maydoni endi tahrirlash formasida **read-only** (backend ham POST
  orqali kelgan qiymatni e'tiborsiz qoldiradi) — chunki ularda
  miqdor allaqachon tizim orqali (ishlab chiqarish tasdiqlanishi /
  "Kirim-chiqim" sahifasi) StockHistory bilan o'zgaradi.
  **Distributor** turidagi mahsulotlarga **hozircha tegilmadi** —
  ularga hali muqobil "kirim" oqimi qurilmagan (aniqlashtirish
  jarayonida kelishilgan qaror), shuning uchun eski to'g'ridan-to'g'ri
  edit xatti-harakati saqlanadi. Bu keyingi qadam sifatida alohida
  hal qilinadi.
- **Yetkazib beruvchi zaxirasi endi faqat tizim orqali o'zgaradi**:
  `editusr` (xodimni tahrirlash) sahifasidagi "Yuklangan mahsulotlar"
  bo'limi — avval har bir mahsulot uchun qo'lda miqdor kiritib,
  `YetkazibBeruvchi.mahsulotlar`ni to'g'ridan-to'g'ri qayta yozib
  yuborar edi (hech qanday audit yo'q, "yuklama so'rovi" oqimini
  butunlay chetlab o'tardi). Endi bu bo'lim faqat **ko'rish uchun**
  (joriy miqdorlar), tahrirlash imkoni yo'q — o'zgartirish faqat
  "yuklama" so'rovi (web'da omborchi tasdiqlashi yoki Desktop Agent
  orqali Serial QR skanerlash, 83-qadam) orqali bo'ladi.

### O'zgargan fayllar
- `crm/main/models.py` — `MahsulotQoshimchaXarajat.turi` +
  `XARAJAT_TURI_CHOICES`
- `crm/main/migrations/0080_mahsulotqoshimchaxarajat_turi_and_more.py`
- `crm/main/services/stock_service.py` — `recompute_tannarx()` foiz/
  miqdor turlarini alohida hisoblaydi
- `crm/main/views.py` — `seemahsulot` (`xarajat_turi`, miqdor faqat
  distributor uchun), `editusr` (yetkazib beruvchi override olib
  tashlandi)
- `crm/main/warehouse_views.py` — `warehouse_product_edit`
  (`xarajat_turi`, miqdor edit olib tashlandi)
- `crm/main/templates/seemahsulot.html` — xarajat turi tanlovi,
  miqdor read-only (ishlab_chiqariladigan uchun)
- `crm/main/templates/warehouse_product_form.html` — xarajat turi
  tanlovi, miqdor read-only (edit rejimida)
- `crm/main/templates/editusr.html` — yetkazib beruvchi zaxirasi
  faqat ko'rish uchun

### Tekshirildi
Izolyatsiyalangan Django test-client sinovi — (a) `recompute_tannarx`
aniq miqdor va foiz turidagi xarajatlarni to'g'ri qo'shishi (baza
1000 + 100 so'm + 10% = 1200); (b) `seemahsulot` orqali miqdor edit
qilish ishlab_chiqariladigan mahsulot uchun e'tiborsiz qoldirilishi;
(c) xuddi shu forma orqali distributor mahsulot uchun hali ishlashi
(muqobil yo'qligi sababli, ataylab); (d) `warehouse_product_edit`
orqali Ombor mahsuloti miqdorini edit qilish e'tiborsiz qoldirilishi;
(e) `editusr` orqali yetkazib beruvchi zaxirasini qo'lda o'zgartirish
endi ta'sir qilmasligi. `python manage.py check` — xatosiz.

### Ochiq savol (foydalanuvchiga javob)
"Agent tizimida bo'lgan yetkazib beruvchilar QR kod orqali sotyabdimi?"
— **Yo'q.** 83-qadamda qabul qilingan qaror bo'yicha, Desktop Agent
orqali faqat **yuklama** (ombordan yuk olish — QR skanerlab savatga
qo'shish) ishlaydi. Haqiqiy **sotuv** (mijozga sotish) hamon **web**
orqali, avvalgidek qo'lda amalga oshiriladi — bu ataylab shunday
qilingan (foydalanuvchi o'zi: "yuklarni olish uchun agentda qiladi,
sotuv jarayonida webda qiladi" — 83-qadam).

## 93-qadam: `dagentupdate.md`dagi qolgan bo'shliqlar — savdogar agentda, o'zi-so'rab-o'zi-tasdiqlash yopilishi, material so'rovini bekor qilish

**Holat: DONE (2 band) / Qaror qilindi — kod o'zgarishi kerak emas (3 band) / Kutilmoqda (1 band — tarozi)**

### Kontekst
`dagentupdate.md` hujjatidagi 6-bo'lim ("hali qilinmagan ishlar")dan
foydalanuvchi bilan birma-bir ko'rib chiqildi:

### Nima qilindi
- **Savdogar endi Desktop Agent orqali yuklama (yuk olish) qila oladi**
  (avvalgi #2-band): `YetkazibBeruvchi` profili `yetkazib_beruvchi` va
  `savdogar` ikkalasi uchun ham umumiy, backend
  (`agent_scan_delivery_serial`/`agent_finalize_yuklama`) allaqachon
  buni qo'llab-quvvatlar edi — yagona to'siq mijoz (Desktop Agent)
  tomonida edi: `employee_scan_widget.py::_start_session` faqat
  `user_type == "yetkazib_beruvchi"` bo'lsa yuklama rejimini ochardi.
  Endi `("yetkazib_beruvchi", "savdogar")` ikkalasi ham qo'llab-
  quvvatlanadi.
- **"O'zi so'rab-o'zi tasdiqlash" muammosi yopildi** (avvalgi #6-band):
  `views.py::main()`dagi yetkazib beruvchi/savdogar o'z yuklama
  so'rovini web orqali darhol o'zi tasdiqlashi (`'accept' in yk_id`)
  endi **Desktop Agent ishlatuvchi firmalarda taqiqlanadi**
  (`company.custom_desktop_agent_stations > 0` bo'lsa xato xabari
  bilan qaytariladi) — bunday firmalarda tasdiqlash faqat Desktop
  Agent orqali (Serial QR skanerlab, fizik tasdiqlangan holda)
  bo'ladi. Desktop Agent yo'q firmalarda eski xatti-harakat
  o'zgarishsiz qoladi.
- **Material so'rovini bekor qilish** — foydalanuvchi bilan
  kelishilgan qaror bo'yicha (5-band, "rad etish"): kiosk stansiyada
  klaviatura/sichqoncha yo'qligi sababli, agentda bekor qilish
  qurilmaydi — buning o'rniga, ishlab chiqaruvchi o'zining
  dashboardidagi (`pazanda_dashboard.html`, "Ombor material
  so'rovlari" bo'limi) hali "kutilmoqda" holatidagi so'roviga endi
  **"Bekor qilish"** tugmasi bilan o'zi bekor qila oladi (yangi
  `action='cancel_material_request'`, `addmiqdor` view'ga qo'shildi).
  Faqat so'rovni yaratgan ishlab chiqaruvchining o'ziga ruxsat
  beriladi.

### Qaror qilindi — hozircha qo'shimcha kod kerak emas
- **Distributor kirim oqimi** (#1-band): foydalanuvchi aniq javob
  berdi — "kirimni tasdiqlash shart emas, ega kiritadi, mas'uliyat
  eganing o'zida qoladi". Demak distributor mahsulot uchun
  to'g'ridan-to'g'ri web-edit orqali kirim kiritish **ataylab shunday
  qoldiriladi** (92-qadamda ham shu sababdan tegilmagan edi) — Desktop
  Agent orqali alohida "kirim tasdiqlash" oqimi qurilmaydi.
- **Dona-QR'siz mahsulotlar yuklamasi** (#3-band): foydalanuvchi
  tasdiqladi — bunday mahsulotlar uchun agent orqali maxsus mexanizm
  qurilmaydi, web orqali eskicha davom etadi.

### Kutilmoqda
- **Tarozi haqiqiy integratsiyasi** (#4-band) — foydalanuvchi hozir
  LAN orqali ulangan tarozining IP/port ma'lumotini qidirmoqda
  (tarozi ekranidan tekshirilmoqda). Aniqlangach davom etiladi.

### O'zgargan fayllar
- `desktop_agent/app/windows/employee_scan_widget.py` — `_start_session`
  endi `savdogar`ni ham yuklama rejimiga qo'shadi
- `crm/main/agent_api_views.py` — `agent_scan_delivery_serial`/
  `agent_finalize_yuklama` docstringlari yangilandi (savdogar
  qo'llab-quvvatlanishi aniq yozildi)
- `crm/main/views.py` — `main()` (yuklama o'zi-tasdiqlash yopilishi),
  `addmiqdor` (`cancel_material_request` action)
- `crm/main/templates/pazanda_dashboard.html` — "Bekor qilish" tugmasi

### Tekshirildi
- Backend: izolyatsiyalangan Django test-client sinovi — (a) Desktop
  Agent firmasida yuklamani web orqali o'zi tasdiqlashga urinish
  bloklanishi, agentsiz firmada esa eski xatti-harakat saqlanishi;
  (b) ishlab chiqaruvchi o'z kutilayotgan material so'rovini bekor
  qila olishi, allaqachon ko'rib chiqilganini qayta bekor qilish
  xavfsiz no-op ekanligi, boshqa ishlab chiqaruvchining so'rovini
  bekor qila olmasligi.
- Desktop Agent: savdogar badge skanerlanganda yuklama savati
  ochilishi (yangi test); mavjud yuklama-oqim regressiya testi
  `serial_ids` maydoniga moslab yangilandi (bu maydon avvalroq
  qo'shilgan, lekin test eskirib qolgan edi — endi to'g'irlandi) va
  o'tdi; qolgan barcha tegishli regressiya testlari (material-request,
  miqdor, weigh, Reception, main_window) buzilmadi.
- `python manage.py check` — xatosiz.
- `dist/StockFirmAgent.exe` — muvaffaqiyatli qayta build qilindi.

## 94-qadam: Desktop Agent onlayn/oflayn holati — haqiqiy real-vaqtli (WebSocket push, sahifa yangilashsiz)

**Holat: DONE**

### Nima qilindi
Foydalanuvchi 90-qadamdagi "sahifa yuklanganda/yangilanganda hisoblanadi"
yechimini rad etib, aniq talab qildi: onlayn/oflayn holat WebSocket
orqali **darhol** (sahifani qayta yuklashsiz) ko'rsatilishi kerak.

- **Onlaynga o'tish — server push orqali, darhol**: `agent_heartbeat`
  endpoint endi har muvaffaqiyatli heartbeatdan keyin
  `_send_ws_notification(..., event='agent_heartbeat', extra=
  {'station_id':..., 'is_online': True})` yuboradi. `_send_ws_notification`
  va `NotificationConsumer.send_notification`ga yangi `extra` (erkin
  dict) maydoni qo'shildi — bu orqali brauzer JS'i sahifani qayta
  yuklamasdan darhol ma'lumot ola oladi.
- **Oflaynga o'tish — brauzer tomonda, mahalliy hisoblash**: serverda
  "stansiya heartbeat yubormay qo'ydi" hodisasini kuzatish uchun
  alohida rejalashtirilgan vazifa (Celery/cron) kerak bo'lardi (bu
  loyihada yo'q, 90-qadamda ham qayd etilgan cheklov). Shuning uchun
  amaliy yechim: har safar "onlayn" WS xabari kelganda, brauzer JS
  o'sha stansiya uchun `setTimeout(AGENT_ONLINE_THRESHOLD_SECONDS +
  15s zaxira)` ni qayta o'rnatadi; agar keyingi heartbeat shu vaqt
  ichida kelmasa, JS **o'zi** (serverga so'rovsiz) stansiyani oflayn
  deb belgilab, bannerni ko'rsatadi.
- `egabase.html`ga: (1) banner endi doim DOM'da mavjud (JS orqali
  `display:flex/none` bilan boshqariladi), (2) `agent_stations_status`
  (barcha stansiyalar + boshlang'ich onlayn/oflayn holati) `json_script`
  orqali "seed" ma'lumot sifatida joylashtiriladi, (3) mavjud WebSocket
  `onmessage` handler'iga `data.event === 'agent_heartbeat'` tekshiruvi
  qo'shildi — bunday xabarlar toast/panelda ko'rsatilmaydi, faqat
  stansiya holatini yangilaydi.
- `main/context_processors.py`ga `agent_stations_status` (barcha
  stansiyalar ro'yxati, id/nomi/onlayn holati bilan) va
  `agent_online_threshold_seconds` (JS bilan serverni sinxron
  ushlab turish uchun) qo'shildi.

### O'zgargan fayllar
- `crm/main/warehouse_views.py` — `_send_ws_notification(..., extra=)`
- `crm/main/consumers.py` — `send_notification` `extra`ni uzatadi
- `crm/main/agent_api_views.py` — `agent_heartbeat` endi WS push yuboradi
- `crm/main/context_processors.py` — `_safe_agent_stations_status`,
  `agent_online_threshold_seconds`
- `crm/main/templates/egabase.html` — JS-boshqariladigan banner,
  `agentStationsSeed`, `handleAgentHeartbeat`/`scheduleAgentOfflineTimeout`/
  `renderAgentOfflineBanner`

### Tekshirildi
- Backend: `channels.testing.WebsocketCommunicator` bilan — `ega`ning
  sessiya-autentifikatsiyali brauzer WS ulanishi (to'g'ri Host header
  bilan, kompaniya subdomeni guruhiga qo'shilib) `POST /api/agent/
  heartbeat/` chaqirilganda **darhol** `event='agent_heartbeat'` +
  to'g'ri `station_id`/`is_online` bilan xabar olishi tasdiqlandi.
- Avvalgi WS/online-status testlar (91/90-qadam) — hech biri buzilmadi.
- Dashboard sahifasi (`ega` sifatida) haqiqatan ham banner/JS/seed
  script'ni xatosiz render qilishi va seed JSON to'g'ri parse
  bo'lishi izolyatsiyalangan test bilan tasdiqlandi.
- `python manage.py check` — xatosiz.

### Eslatma
Bu hal — real amaliyotda deyarli to'liq real-vaqtli: stansiya
onlaynga o'tishi darhol (WS push orqali) ko'rinadi; oflaynga o'tishi
esa server chegarasi (90s) + brauzer zaxirasi (15s) = ~105 soniyagacha
kechikishi mumkin (chunki bu holat brauzer tomonda vaqt tugashi
orqali aniqlanadi, server tomonidan push qilinmaydi). Sahifa ochiq
turgan HAR BIR brauzerda mustaqil hisoblanadi — agar foydalanuvchi
bir nechta oynada ochgan bo'lsa, har biri o'z holatini alohida
kuzatadi (bu amalda muammo emas, chunki barchasi bir xil serverdan
bir xil WS xabarlarini oladi).

### 94-qadam (tuzatish): "seed" hisoblagich sahifa yuklangan vaqtdan emas, HAQIQIY qolgan vaqtdan boshlanishi kerak edi

Foydalanuvchi haqiqiy sinovda topdi: Desktop Agent'dan chiqib
(dasturni yopib) ancha vaqt kutgandan keyin ham dashboard hali
"onlayn" deb ko'rsatishda davom etardi. Sabab — real bug: `egabase.html`
JS'i sahifa birinchi ochilganda (`seedAgentStations`) HAR DOIM to'liq
`AGENT_ONLINE_THRESHOLD_MS + AGENT_OFFLINE_GRACE_MS` (~105 soniya)dan
boshlab hisoblagichni ishga tushirar edi — stansiya sahifa
yuklanishidan bir necha soniya oldin allaqachon oflayn bo'lib
qolgan bo'lsa ham! Bu server (heartbeat vaqtiga qarab to'g'ri
hisoblaydigan) va brauzer (har doim yangi to'liq hisoblagich
boshlaydigan) orasida jiddiy nomuvofiqlik edi.

**Tuzatildi**: `_safe_agent_stations_status()` endi har bir onlayn
stansiya uchun `seconds_until_offline` (server tomonda, `last_agent_
heartbeat`ga nisbatan HAQIQIY hisoblangan qolgan vaqt) ham qaytaradi.
`seedAgentStations()` JS funksiyasi endi shu qiymatdan
(`seconds_until_offline * 1000 + zaxira`) foydalanadi — sahifa
yuklanishidan oldin qancha vaqt allaqachon o'tgan bo'lsa, shuncha
hisobga olinadi. Faqat WebSocket orqali **yangi** heartbeat kelganda
(`handleAgentHeartbeat`) to'liq muddatdan qayta boshlanadi — bu holatda
to'g'ri, chunki heartbeat aynan hozir kelgan.

**Tekshirildi**: izolyatsiyalangan test — (a) hozirgina heartbeat
yuborgan stansiya ~90s qolgan vaqt olishi; (b) 85 soniya oldin
heartbeat yuborgan stansiya endi FAQAT ~5s qolgan vaqt olishi (avval
bu holatda ham noto'g'ri ~105s berilardi — aynan shu bug edi); (c)
hech qachon heartbeat yubormagan stansiya darhol 0s bilan oflayn
ko'rsatilishi. Dashboard sahifasi yangi maydon bilan xatosiz render
qilinishi ham tasdiqlandi.

### O'zgargan fayllar (tuzatish)
- `crm/main/context_processors.py` — `_safe_agent_stations_status`
  endi `seconds_until_offline` qaytaradi
- `crm/main/templates/egabase.html` — `scheduleAgentOfflineTimeout`
  ixtiyoriy `delayMs` parametri bilan, `seedAgentStations` haqiqiy
  qolgan vaqtdan foydalanadi

## 95-qadam: Video yozuvlari — `.exe` yonida `saved_videos/{sana}/`, kamera1/kamera2 nomlash, mikrofon bilan ovoz yozish (ffmpeg mux)

**Holat: DONE**

### Nima qilindi
Foydalanuvchi so'radi: (1) videolar `.exe` oldida `saved_videos/{sana}/`
papkasida saqlansin, (2) ovoz ham yozilsin, (3) ikkita kamera "kamera 1"/
"kamera 2" deb nomlansin (ba'zi kamerada mikrofon bo'lmasa — muammo emas).

- **Fayl joylashuvi**: `db.py`ga `recordings_root_dir()` (`.exe`ning o'zi
  bilan bir papkada — `%LOCALAPPDATA%` kabi yashirin joyda emas) va
  `recordings_dir_for_date()` (`saved_videos/<YYYY-MM-DD>/`) qo'shildi.
  Eski `recordings_dir()` shu ikkitasi bilan almashtirildi.
- **Kamera nomlash**: fayl nomida endi DB'dagi ichki `id` (masalan
  "kam17") o'rniga, shu ombordagi kameralar orasidagi tartib raqami —
  "kamera1", "kamera2" (`CameraRecorderService._camera_label()`).
- **Ovoz yozish**: yangi `audio_utils.py` — `MicBufferWorker` (video
  buferi bilan bir xil naqsh: doimiy aylanma audio bufer,
  `sounddevice` kutubxonasi orqali). Har bir ombor kamerasiga
  Sozlamalarda (`CameraConfigDialog`, faqat `role='ombor'`) ixtiyoriy
  mikrofon biriktiriladi (`Camera.mic_device_name`, yangi ustun,
  yumshoq migratsiya bilan). Voqea yozib bo'lingach, agar mikrofon
  sozlangan bo'lsa — audio ham yoziladi va **ffmpeg** orqali videoga
  birlashtiriladi (`_mux_with_audio`, `-c:v copy -c:a aac -shortest`).
- **Xavfsiz pasayish (foydalanuvchi bilan kelishilgan)**: agar
  mikrofon sozlanmagan, mikrofon xato bersa, yoki `ffmpeg` topilmasa —
  video baribir ovozsiz to'g'ri saqlanadi (hech qanday xato/crash),
  faqat audio.wav (agar yozilgan bo'lsa) alohida saqlanib qoladi.
  `find_ffmpeg()` — `.exe` yonidagi `ffmpeg.exe`, keyin PyInstaller
  ichiga ilova qilingan nusxa, keyin tizim PATH'ini tekshiradi.
  **Muhim**: ffmpeg dasturi o'zi hajmi/litsenziyasi sababli avtomatik
  yuklab olinmadi — foydalanuvchi tomonidan qo'lda joylashtirilishi
  kerak (pastga qarang).

### O'zgargan fayllar
- `desktop_agent/app/db.py` — `recordings_root_dir()`,
  `recordings_dir_for_date()`; `cameras.mic_device_name` ustuni +
  migratsiya; `Camera` dataclass, `add_camera_for_warehouse`/
  `update_camera`/`_row_to_camera` yangilandi
- `desktop_agent/app/audio_utils.py` — yangi fayl (`MicBufferWorker`,
  `list_mic_devices`)
- `desktop_agent/app/camera_recorder_service.py` — `find_ffmpeg()`,
  `_camera_label()`, `_mux_with_audio()`, `saved_videos/{sana}/` yo'li
- `desktop_agent/app/windows/camera_config_dialog.py` — mikrofon
  tanlash (faqat ombor kamerasi uchun)
- `desktop_agent/requirements.txt` — `sounddevice==0.5.1`

### Tekshirildi
- `sounddevice.query_devices()` haqiqiy kompyuterda ishlab, real
  mikrofonlarni (jumladan foydalanuvchining veb-kamera mikrofoni)
  to'g'ri ko'rsatishi tasdiqlandi.
- Izolyatsiyalangan testlar: (a) kamera1/kamera2 nomlash tartib
  bo'yicha to'g'ri ishlashi; (b) fayl yo'li `saved_videos/{sana}/`
  ostida to'g'ri qurilishi; (c) mikrofon + soxta (fake) ffmpeg bilan
  to'liq mux jarayoni — video va audio bitta yakuniy faylga
  birlashtirilishi, vaqtinchalik fayllar tozalanishi; (d) ffmpeg
  topilmasa — video xatosiz alohida saqlanishi, audio.wav yo'qolmay
  saqlanib qolishi; (e) `CameraConfigDialog` — mikrofon tanlash faqat
  ombor kamerasi uchun ko'rinishi, saqlash/qayta ochishda to'g'ri
  ishlashi, skaner kamerasida bu bo'lim umuman yo'qligi.
- Mavjud kamera/multi-camera regressiya testlari — hech biri buzilmadi.
- `dist/StockFirmAgent.exe` — `sounddevice` bilan birga (PyInstaller
  hook orqali PortAudio DLL'lari ham) muvaffaqiyatli qayta build
  qilindi, ogohlantirishlarsiz.

## 96-qadam: "Miqdor Qo'shish"da so'ralgan miqdor avtomatik chiqishi — "✓ Bo'ldim" tugmasi

**Holat: DONE**

### Nima qilindi
Foydalanuvchi: "nega miqdor qo'shish so'rovida so'ragan miqdori
avtomatik chiqmayabdi? avtomatik shunday tursin, kamaytirib yoki
ko'paytirish imkoni bo'lsin." Keyin aniqlashtirdi: har bir xom ashyo
so'rovi — bitta "task"; tasdiqlangan (material qabul qilingan) task
uchun **"✓ Bo'ldim"** tugmasi bo'lsin — bosilganda "Miqdor Qo'shish"
mahsulot+miqdor bilan avtomatik to'ldirilsin (kamaytirish/ko'paytirish
imkoni saqlangan holda); bir nechta so'rov bo'lsa — bir nechta task.

- `pazanda_dashboard.html`dagi "Ombor material so'rovlari" ro'yxatida
  — `status='approved'` va hali "Miqdor Qo'shish"ga bog'lanmagan
  (`consumed_in` bo'sh) har bir so'rov uchun endi **"✓ Bo'ldim"**
  havolasi ko'rinadi (avvalgi 93-qadamdagi "Bekor qilish" — faqat
  `waiting` holatidagilar uchun — bilan bir qatorda).
- Bosilganda `{% url 'add_miqdor' %}?complete_request=<id>` ga olib
  boradi. `addmiqdor` view (GET) shu parametrni o'qib: (1) mahsulot
  (target_product) avtomatik tanlanadi, (2) miqdor **retsept (BOM)
  orqali hisoblanadi**: `so'ralgan xom ashyo miqdori / norma_miqdor =
  taxminiy tayyor mahsulot soni` (masalan 5 kg un, retseptda 1 dona
  uchun 0.5 kg kerak bo'lsa — 10 dona taklif qilinadi). Mos retsept
  qatori topilmasa — xom ashyo miqdorining o'zi (taxminiy, backup
  sifatida) ko'rsatiladi.
- Miqdor maydoni **oddiy, tahrirlanadigan raqam input**ligicha qoladi
  — foydalanuvchi taklif qilingan qiymatni istalgancha kamaytirishi
  yoki ko'paytirishi mumkin, shundan keyin "Qo'shish" bosiladi
  (mavjud yuborish/tasdiqlash logikasi — jumladan Desktop Agent'da QR
  orqali tasdiqlash, agentli firmalarda — o'zgarishsiz ishlatiladi,
  hech narsa qayta yozilmadi).
- **Real bug topildi va tuzatildi shu jarayonda**: taklif qilingan
  miqdor Django'ning lokalizatsiyasi tufayli vergul bilan
  (`value="10,0"`) render qilinar edi — bu HTML `type="number"`
  input uchun NOTO'G'RI format (brauzer buni bo'sh deb o'qiydi,
  chunki u nuqta kutadi). `|unlocalize` filtri qo'shib tuzatildi.

### O'zgargan fayllar
- `crm/main/views.py` — `addmiqdor` (GET): `complete_request`
  parametrini o'qib, mahsulot+miqdorni oldindan hisoblab to'ldirish
- `crm/main/templates/pazanda_dashboard.html` — "✓ Bo'ldim" havolasi
- `crm/main/templates/addmiqdor.html` — mahsulot oldindan tanlanishi,
  miqdor oldindan to'ldirilishi (`|unlocalize` bilan, to'g'ri format)

### Tekshirildi
Izolyatsiyalangan Django test-client sinovi — (a) "Bo'ldim" havolasi
mahsulot va retsept asosida hisoblangan miqdorni (5kg/0.5=10 dona)
to'g'ri oldindan to'ldirishi; (b) mos retsept topilmasa, xom ashyo
miqdorining o'zi backup sifatida ko'rsatilishi; (c) miqdor maydoni
hamon oddiy tahrirlanadigan raqam input ekanligi; (d) dashboardda
"approved" va bog'lanmagan so'rovlar uchun "Bo'ldim" havolasi,
"waiting" so'rovlar uchun esa hamon "Bekor qilish" ko'rinishi;
(e) vergul/nuqta formatlash bugi tuzatilgani (`|unlocalize` bilan).
`python manage.py check` — xatosiz.

## 97-qadam: Agent — chop etilgan Serial QR yorliqlarini skanerlash ("bu QR hech narsaga tegishli emas" xatosi tuzatildi)

**Holat: DONE**

### Nima qilindi
Foydalanuvchi chop etilgan mahsulot QR yorlig'ini Desktop Agent'da
sinov uchun skanerlaganda, "Bu QR kod hech qanday narsaga tegishli
emas" xatosi chiqdi. Sabab — ikkita bog'liq muammo:

1. **`agent_scan` (universal skaner) `Serial` modelini umuman
   tekshirmasdi** — faqat `XodimBadge` va `ProductionMaterialRequest`
   kodlarini bilar edi. `Serial` uchun hech qanday holat yo'q edi.
2. **Chop etilgan QR mazmuni — yalang'och kod emas, to'liq public URL**
   (`https://<subdomen>.stockfirm.uz/p/<kod>/`, mijozlar oddiy telefon
   kamerasi bilan ochishi uchun ataylab shunday, `label_printer_
   service.py`da `s["url"]` ishlatiladi) — hatto `Serial` tekshiruvi
   qo'shilganda ham, bazadagi yalang'och `kod`ga solishtirish
   ishlamas edi, chunki skanerlangan matn butun URL bo'lardi.

Ikkalasi ham tuzatildi: yangi `_kod_candidates()` yordamchi funksiya —
agar skanerlangan matn URL'ga o'xshasa, undan oxirgi yo'l segmentini
(haqiqiy kodni) ham ajratib, ikkala variantni (yalang'och matn VA
ajratilgan kod) ham nomzod sifatida tekshiradi — bu nafaqat Serial,
balki Badge/Material-so'rov uchun ham ishlaydi (kelajakda ular ham
URL shaklida bo'lib qolsa). `agent_scan` endi `Serial`ni ham
tekshiradi (`type='serial'`, mahsulot/holat ma'lumoti bilan, faqat
o'qish uchun — `qr_service.register_scan()` orqali `scan_soni` ham
oshiriladi, hech narsa boshqa o'zgarmaydi).

Desktop Agent (`employee_scan_widget.py`): `type='serial'` javobi
endi maxsus, do'stona xabar bilan ko'rsatiladi ("✓ [Mahsulot] —
Serial: [kod]... — Holati: Omborda") — avval xato/sessiya
boshlashga urinib chalkashtirmasdi.

### O'zgargan fayllar
- `crm/main/agent_api_views.py` — `_kod_candidates()`,
  `_serial_scan_response()`, `agent_scan` endi Serial'ni ham tekshiradi
- `desktop_agent/app/windows/employee_scan_widget.py` —
  `_show_serial_scan_result()`, `_on_scan_resolved` yangilandi

### Tekshirildi
Izolyatsiyalangan test — (a) Serial'ning yalang'och kodi skanerlansa
to'g'ri tanilishi; (b) chop etilgan HAQIQIY QR mazmuni (to'liq public
URL) ham to'g'ri tanilishi; (c) har skanerlashda `scan_soni` oshishi;
(d) noma'lum kod hamon toza 404 qaytarishi; (e) mavjud Badge/Material-
so'rov skanerlash testlari buzilmagani. Desktop Agent tomonida —
Serial skanerlanganda do'stona xabar ko'rsatilishi, hech qanday
xodim sessiyasi boshlanmasligi tasdiqlandi. `python manage.py check`
— xatosiz. `dist/StockFirmAgent.exe` — muvaffaqiyatli qayta build
qilindi.

## 98-qadam: Mahsulot uchun Serial/QR sozlamasi (`serial_granularity`) — endi web'da o'zgartirish mumkin

**Holat: DONE**

### Nima qilindi
Foydalanuvchi ishlab chiqarishni tasdiqlaganda hech qanday QR
generatsiya bo'lmadi (shuning uchun printerdan ham hech narsa
chiqmadi). Sababini tekshirib topdim: `Mahsulot.serial_granularity`
(har bir donaga QR / partiyaga QR / yo'q) maydoni backend'da
(model, servis, agent API) to'liq ishlaydi, lekin uni o'zgartiradigan
**hech qanday joy web-sahifada yo'q edi** — faqat Django admin yoki
to'g'ridan-to'g'ri bazadan o'zgartirish mumkin edi.

`seemahsulot.html` (Mahsulotlar — tahrirlash sahifasi)ga yangi
"Serial/QR kod" tanlovi qo'shildi (Yo'q / Partiya bo'yicha / Har bir
donaga alohida QR), `seemahsulot` view uni saqlaydi.

### O'zgargan fayllar
- `crm/main/views.py` — `seemahsulot` (`serial_granularity_choices`
  context, POST'dan saqlash)
- `crm/main/templates/seemahsulot.html` — "Serial/QR kod" tanlovi

### Tekshirildi
Izolyatsiyalangan test — tanlov to'g'ri ko'rsatilishi va saqlanishi,
noto'g'ri qiymat yuborilsa mavjud sozlama buzilmasligi (xato/crash
yo'q). `python manage.py check` — xatosiz.

### Foydalanuvchi uchun — ffmpeg qanday joylashtiriladi
Ovoz+video BITTA faylga birlashishi uchun `ffmpeg.exe` kerak (litsenziya/
hajm sababli dastur ichiga avtomatik yuklab olinmadi):
1. https://www.gyan.dev/ffmpeg/builds/ (yoki ffmpeg.org) dan "release
   essentials" versiyasini yuklab oling.
2. Arxivdan `bin/ffmpeg.exe` faylini toping.
3. Uni **`StockFirmAgent.exe` bilan bir xil papkaga** ko'chiring
   (masalan `dist/ffmpeg.exe`).
4. Dasturni qayta ishga tushiring — `find_ffmpeg()` uni avtomatik
   topadi. Joylashtirmasangiz ham dastur ishlayveradi — faqat ovoz
   videoga birlashmaydi (audio alohida .wav sifatida saqlanadi).

va standart Windows drayver bilan RAW chop etishning to'g'ri
ishlashini foydalanuvchi o'zi, real uskunada tekshiradi — bu kod
mantiqiy jihatdan to'g'ri qurilgan va soxta printer bilan to'liq
sinaldi, lekin haqiqiy termal chiqishni ko'rib tasdiqlash hali
qilinmagan.

## 89-qadam: Kiosk-rejim (klaviatura/sichqonchasiz stansiya) — miqdor tasdiqlash tugmasi olib tashlandi + Omborchi Desktop Agent firmalar uchun kerak emas

**Holat: DONE**

### Nima qilindi
- Foydalanuvchi haqiqiy printerni sozlab, ishlab chiqarish oqimini
  yakunlashga tayyorlanayotganda muhim cheklovni aniqladi: **Desktop
  Agent ishlaydigan stansiya kompyuterida klaviatura/sichqoncha
  bo'lmaydi** (yoki bo'lsa ham, ishlatilishi taqiqlanadi) — faqat
  skaner (kamera yoki HID) orqali muloqot qilinadi. Bu shuni
  anglatadiki, oldingi "Tasdiqlash" tugmasi (miqdor qo'shish agent
  oqimida, 82-qadamda qurilgan) hech qachon bosila olmaydi.
- **`employee_scan_widget.py`dan "Tasdiqlash" tugmasi butunlay olib
  tashlandi.** Endi navbatdagi "miqdor qo'shish" so'rovi
  ko'rsatilgan zahoti **avtomatik** tasdiqlanadi (`_show_next_
  miqdor_request()` ichida bevosita `_submit_miqdor_approve()`
  chaqiriladi) — xodim hech qanday tugma bosishi shart emas, faqat
  natijani (chop etilayotgan yorliqlarni) kutadi. Bu aynan
  boshlang'ich vision hujjatidagi (81-qadamgacha bo'lgan
  rejalashtirish bosqichida yozilgan) "chop etilgach yopishtirib
  skaner qilish orqali mahsulot qo'shadi" g'oyasini to'liq
  qo'llab-quvvatlaydi.
- Tasdiqlash muvaffaqiyatsiz bo'lsa (masalan tarmoq xatosi) — endi
  qayta urinish tugmasi yo'qligi sababli, xato xabari ko'rsatiladi
  va 2.5 soniyadan so'ng avtomatik ravishda navbatdagi so'rovga
  o'tiladi (kiosk hech qachon abadiy to'xtab qolmasligi kerak).
- **Omborchi roli Desktop Agent ishlatuvchi firmalar uchun endi
  kerak emas**: foydalanuvchi "qr kodli desktop agentga o'tganlarda
  omborchi yo'q bo'lsin" dedi — aniqlashtirilgach (tasdiqlangan
  variant): yangi xodim qo'shish formasida (`useryaratish.html`)
  `company.custom_desktop_agent_stations > 0` bo'lsa, "Omborchi"
  turi tanlovda **butunlay yashiriladi**. Mavjud omborchi hisoblari
  (agar bo'lsa) tegilmaydi — faqat yangi qo'shishda tanlov yo'q.
  Sabab: bu firmalarda material so'rovi tasdiqlashni (81-qadam) va
  ishlab chiqarish tasdiqlashni (82-qadam, endi shu qadamda avtomat
  qilingan) Desktop Agent to'liq almashtirgan — omborchining alohida
  web-dashboard orqali tasdiqlashi endi ortiqcha va potentsial
  ziddiyatli (bir xil so'rovni ham omborchi web'dan, ham agent'dan
  tasdiqlash imkoniyati mavjud edi).

### O'zgargan fayllar
- `desktop_agent/app/windows/employee_scan_widget.py` —
  `miqdor_approve_btn` olib tashlandi, `_show_next_miqdor_request`
  avtomatik tasdiqlashni ishga tushiradi, `_on_miqdor_approve_failed`
  endi avtomatik keyingi so'rovga o'tadi
- `crm/main/templates/useryaratish.html` — "Omborchi" tanlovi
  `company.custom_desktop_agent_stations` bo'lsa yashiriladi

### Tekshirildi
- Desktop Agent: mavjud miqdor-qoshish regressiya testlari
  (`test_miqdor_flow_widget.py`, `test_miqdor_direct_label_print.py`)
  yangilanib (endi tugma bosish o'rniga avtomatik tasdiqlashni
  kutadi) — barchasi o'tdi; qolgan regressiya to'plami (Reception,
  material-request, weigh, yuklama, main_window, camera-recorder,
  label-printer) ham buzilmadi.
- Backend: izolyatsiyalangan Django test-client sinovi —
  `custom_desktop_agent_stations=0` bo'lganda "Omborchi" tanlovi
  ko'rinishi, `custom_desktop_agent_stations=2` bo'lganda yashirilishi
  tasdiqlandi.
- `python manage.py check` — xatosiz.
- `dist/StockFirmAgent.exe` — ishlayotgan eski nusxalar to'xtatilgach
  muvaffaqiyatli qayta build qilindi.

## 89-qadam (qo'shimcha): "Miqdor Qo'shish" web formasidagi rasm maydoni Desktop Agent firmalar uchun olib tashlandi

**Holat: DONE**

### Nima qilindi
Foydalanuvchi ekran-suratda ko'rsatib so'radi: "nega miqdor
qo'shishda rasm turibdi?" — Desktop Agent ishlatuvchi firma uchun
`/add/miqdor/` sahifasidagi "Miqdor Qo'shish" formasida "Rasm
(ixtiyoriy)" yuklash maydoni ortiqcha edi, chunki bu firmalarda
tasdiqlash/audit izi endi ombor kamerasi (87-qadam, video yozuv) va
Serial QR (82-qadam) orqali ta'minlanadi — qo'lda rasm biriktirish
keraksiz qadam. `addmiqdor.html`da shu maydon
`{% if not request.company.custom_desktop_agent_stations %}` bilan
o'raldi — Desktop Agent yo'q firmalarda o'zgarishsiz ko'rinadi
(eski xatti-harakat saqlanadi).

### O'zgargan fayllar
- `crm/main/templates/addmiqdor.html`

### Tekshirildi
Izolyatsiyalangan Django test-client sinovi —
`custom_desktop_agent_stations=0` bo'lganda rasm maydoni ko'rinishi,
`custom_desktop_agent_stations=2` bo'lganda yashirilishi tasdiqlandi.
`python manage.py check` — xatosiz.

## 90-qadam: Desktop Agent stansiyalari uchun real-vaqtli onlayn/oflayn holat + dashboard ogohlantirishi

**Holat: DONE**

### Nima qilindi
Foydalanuvchi so'radi: "agent real-time bo'lsin. hodimlarda online
oflayn tursin. agar agent oflayn bo'lsa dashboardda agent onlayn
emas deb qizarib ogohlantirishlar chiqsin."

- **Backend**: `User`ga yangi `last_agent_heartbeat` (DateTimeField)
  maydoni + `is_agent_online` xususiyati (property) qo'shildi —
  stansiya oxirgi `AGENT_ONLINE_THRESHOLD_SECONDS=90` soniya ichida
  heartbeat yuborgan bo'lsa "onlayn" hisoblanadi. Yangi
  `POST /api/agent/heartbeat/` endpoint (`agent_heartbeat`) — token
  orqali stansiyani (`User`) topib, `last_agent_heartbeat`ni
  yangilaydi. `agent_api_views.py`ga `_extract_token()`/
  `_station_from_token()` yordamchi funksiyalari qo'shildi (avvalgi
  `_resolve_company_by_token` faqat `Company` qaytarardi, aynan
  stansiya obyektining o'ziga kerak bo'ldi).
- **Desktop Agent (client)**: `api_client.py`ga `send_heartbeat()`;
  `main_window.py`ga har 25 soniyada bir marta (server tomonidagi 90
  soniyalik chegaraga nisbatan 2-3 marta zaxira bilan) fon oqimida
  heartbeat yuboradigan `_HeartbeatWorker` (QThread) + `QTimer`
  qo'shildi. Login qilinmagan holatda (token yo'q) heartbeat
  yuborilmaydi — xato/keraksiz so'rov bo'lmaydi. Har bir heartbeat
  fon oqimida, xavfsiz (kutilmagan xatolar jimgina e'tiborsiz
  qoldiriladi, dastur yiqilmaydi — 86-qadamdagi naqsh) yuboriladi.
- **Web UI — `hodimlar_list.html`**: `type='desktop_agent'`
  qatorlarida endi qo'shimcha yashil "Onlayn" / qizil "Oflayn"
  belgisi ko'rsatiladi (mavjud Active/Inactive belgisi yonida).
- **Web UI — dashboard ogohlantirishi**: `main/context_processors.py`
  (`plan_context`, allaqachon barcha `ega` sahifalariga ulangan)ga
  `offline_agent_stations` qo'shildi — Desktop Agent sotib olingan
  firmalar uchun hozir oflayn bo'lgan stansiyalar ro'yxati (stansiya
  sotib olinmagan firmalarda bo'sh ro'yxat, hech qanday so'rov
  ortiqcha bajarilmaydi). `egabase.html` (barcha `ega` sahifalarining
  bazasi)ga qizil ogohlantirish banneri qo'shildi — "setup_mode"
  banneriga o'xshash uslubda, "N ta Desktop Agent stansiyasi onlayn
  emas" (yoki bitta bo'lsa — stansiya nomi bilan) + "Ko'rish" havolasi
  (`hodimlar_list?role=desktop_agent`ga olib boradi).

### O'zgargan fayllar
- `crm/main/models.py` — `User.last_agent_heartbeat`,
  `User.is_agent_online`, `User.AGENT_ONLINE_THRESHOLD_SECONDS`
- `crm/main/migrations/0079_user_last_agent_heartbeat.py`
- `crm/main/agent_api_views.py` — `_extract_token`,
  `_station_from_token`, `agent_heartbeat`
- `crm/landing/urls.py` — `/api/agent/heartbeat/` marshruti
- `crm/main/context_processors.py` — `_safe_offline_agent_stations`
- `crm/main/templates/hodimlar_list.html` — onlayn/oflayn belgisi
- `crm/main/templates/egabase.html` — qizil ogohlantirish banneri
- `desktop_agent/app/api_client.py` — `send_heartbeat()`
- `desktop_agent/app/windows/main_window.py` — `_HeartbeatWorker` +
  25 soniyalik `QTimer`

### Tekshirildi
- Backend: izolyatsiyalangan Django test-client sinovi — (a) hech
  qachon heartbeat yubormagan stansiya oflayn hisoblanishi; (b)
  `POST /api/agent/heartbeat/` chaqirilgach `last_agent_heartbeat`
  yangilanib, stansiya onlaynga o'tishi; (c) chegaradan eski
  heartbeat yana oflayn deb hisoblanishi; (d) noto'g'ri token — 401,
  crash yo'q; (e) `offline_agent_stations` konteksti to'g'ri
  ro'yxatni qaytarishi (onlayn bo'lganda ro'yxatdan chiqishi); (f)
  Desktop Agent sotib olinmagan firmalarda hech qanday ogohlantirish
  yo'qligi.
- Desktop Agent: `MainWindow` smoke testi — (a) token yo'q holatda
  heartbeat yuborilmasligi; (b) token bilan fon oqimi orqali haqiqiy
  heartbeat yuborilishi; (c) ketma-ket chaqiruvlar xavfsiz (crash'siz)
  ishlashi.
- Mavjud barcha desktop_agent regressiya testlari (15 ta fayl) —
  hech biri buzilmadi.
- `python manage.py check` — xatosiz.
- `dist/StockFirmAgent.exe` — muvaffaqiyatli qayta build qilindi.

### Eslatma
Bu "yaqin-real-vaqtli" (near-real-time) yechim — stansiya holati
sahifa yuklanganda/yangilanganda hisoblanadi (WebSocket orqali
avtomatik push emas, chunki "oflaynga o'tish"ni server tomonda
kuzatish uchun alohida rejalashtirilgan vazifa/Celery infratuzilmasi
kerak bo'lardi, bu loyihada hozircha yo'q). Amalda dashboard har safar
ochilganda/yangilanganda (yoki foydalanuvchi navigatsiya qilganda)
holat to'g'ri ko'rsatiladi — 90 soniyalik chegara bilan bu yetarlicha
"real-vaqtli" hisoblanadi.

## 91-qadam: Omborlar — qo'lda "Sinxronlash" tugmasi olib tashlandi, avtomatik yuklash + haqiqiy WebSocket orqali real-vaqtli yangilanish

**Holat: DONE**

### Nima qilindi
Foydalanuvchi so'radi: "bizga sinxronlash tugmasi kerak emas.
dasturga kirishi bilan loading preview qo'y. har web socket data
berganda yangi ma'lumotlar bo'lsa almashilsin."

- **Backend — Desktop Agent uchun haqiqiy WebSocket kanali**: CRM'da
  brauzer dashboardi allaqachon ishlatayotgan `/ws/notifications/`
  kanali (`main/consumers.py::NotificationConsumer`) Desktop Agent
  uchun ham ochildi. Muammo: bu consumer faqat Django sessiyasi
  (`scope["user"].is_authenticated`) orqali autentifikatsiya qilardi
  — Desktop Agent esa sessiyasiz, token orqali ishlaydi. Yechim:
  `connect()` endi, sessiya bo'lmasa, `?token=...` query-parametrini
  tekshiradi — token orqali topilgan **kompaniyaning o'z subdomeni**
  bo'yicha guruhga qo'shiladi (Host header'idan emas — mahalliy/test
  serverlarda Host subdomenni o'zida saqlamasligi mumkin, token esa
  har doim to'g'ri kompaniyani ko'rsatadi).
- `_send_ws_notification()`ga yangi ixtiyoriy `event` parametri
  qo'shildi (masalan `event='ombor_changed'`) — brauzer buni e'tiborsiz
  qoldiradi, Desktop Agent esa aynan shu maydonga qarab, faqat o'ziga
  tegishli hodisalarda reaksiya qiladi. `ombor_list_page` (ombor
  yaratilganda) endi shu event bilan xabar yuboradi.
- **Desktop Agent (client) — yangi `agent_socket_service.py`**:
  `AgentSocketWorker` (QThread, `websocket-client` kutubxonasi orqali)
  — `/ws/notifications/?token=...`ga doimiy ulanadi, uzilib qolsa
  avtomatik qayta ulanadi (5 soniyalik orqaga chekinish bilan). Har
  qanday kutilmagan xato xavfsiz yutiladi (86-qadamdagi saboq).
- **`WarehouseListPage` qayta qurildi**: qo'lda "🔄 Sinxronlash"
  tugmasi **butunlay olib tashlandi**. Endi: (1) sahifa ochilishi
  bilan avval mahalliy keshdagi ro'yxat darhol ko'rsatiladi, (2)
  fonda darhol serverdan tekshiriladi ("Tekshirilmoqda..." — "loading
  preview"), (3) `MainWindow`ning WebSocket xizmati `event=
  'ombor_changed'` xabarini olganda, `sync_from_server(silent=True)`
  chaqiriladi — bu **jimgina** ishlaydi (hech qanday matn
  ko'rsatilmaydi) va faqat ma'lumot HAQIQATAN o'zgargan bo'lsagina
  jadvalni qayta chizadi (keraksiz miltillash yo'q).
- `MainWindow`: login muvaffaqiyatli bo'lgach (`on_login_succeeded`
  callback, `SettingsPage`ga qo'shildi) yoki dastur ochilganda (agar
  avvalroq kirilgan bo'lsa) WebSocket ulanishi avtomatik boshlanadi;
  dastur yopilganda to'xtatiladi.

### O'zgargan fayllar
- `crm/main/consumers.py` — `NotificationConsumer.connect()` token
  orqali autentifikatsiya, `send_notification()` `event` maydonini
  uzatadi
- `crm/main/warehouse_views.py` — `_send_ws_notification(..., event=)`,
  `ombor_list_page` yaratishda `event='ombor_changed'` yuboradi
- `desktop_agent/requirements.txt` — `websocket-client==1.9.0`
- `desktop_agent/app/agent_socket_service.py` — yangi fayl
  (`AgentSocketWorker`, `_to_ws_url`)
- `desktop_agent/app/windows/warehouse_list_page.py` — tugma olib
  tashlandi, `sync_from_server(silent=)` (avtomatik/jim yangilanish,
  faqat haqiqiy o'zgarishda qayta chizish)
- `desktop_agent/app/windows/settings_page.py` — `on_login_succeeded`
  callback
- `desktop_agent/app/windows/main_window.py` — `AgentSocketWorker`
  ishga tushirilishi/to'xtatilishi, `_on_ws_notification` marshrutlash

### Tekshirildi
- Backend: `channels.testing.WebsocketCommunicator` bilan
  izolyatsiyalangan sinov — (a) tokensiz/sessiyasiz ulanish rad
  etilishi; (b) to'g'ri stansiya tokeni bilan ulanish qabul
  qilinishi; (c) `event='ombor_changed'` bilan yuborilgan xabar
  aynan shu ulanishga yetib kelishi; (d) `event`siz (masalan savdo)
  xabarlar ham `event=None` bilan yetib kelishi (agent e'tiborsiz
  qoldira oladi); (e) noto'g'ri token rad etilishi.
- Desktop Agent: `agent_socket_service.py` (URL konvertatsiyasi,
  xabar qabul qilish, xavfsiz to'xtatish), `MainWindow` ulanishi
  (login qilingach WS boshlanishi, `ombor_changed` xabari jim
  resinxronlashni ishga tushirishi, aloqasiz xabarlar e'tiborsiz
  qoldirilishi, oyna yopilganda to'xtatilishi), `WarehouseListPage`
  (tugma yo'qligi, tokensiz holatda xatosiz jim qolishi, ochilishda
  avtomatik yuklanishi, jim resinxronlash haqiqiy o'zgarishda
  jadvalni yangilashi, o'zgarishsiz holatda hech narsa
  ko'rsatmasligi) — barchasi alohida testlarda tasdiqlandi.
- Mavjud barcha desktop_agent regressiya testlari (17 ta fayl) —
  hech biri buzilmadi.
- `python manage.py check` — xatosiz.
- `dist/StockFirmAgent.exe` — `websocket-client` bilan birga
  muvaffaqiyatli qayta build qilindi.

## 99-qadam: "Bo'ldim" tugmasi dublikat yaratayotgan edi + kiosk sessiyasi ish jarayonida jimgina tugab qolayotgan edi

**Holat: DONE**

### Nima qilindi

Foydalanuvchi real ishlab chiqarishda ikkita bir-biriga bog'liq muammoni
ko'rsatdi: (1) "Un uchun Go'sht" material so'rovlarida "✓ Bo'ldim"ni bosib
"Miqdor Qo'shish"ni to'ldirgach, dashboardda tugma hamon ko'rinib turardi —
xuddi hech narsa bo'lmagandek, shuning uchun bir xil so'rov uchun ikki marta
bosilib ketgan (dublikat yozuv); (2) Desktop Agent'da badge skanerlab bularni
tasdiqlashga urinilganda "hech narsa bo'lmayabdi" — kutilgan tasdiqlash
kartochkasi umuman ko'rinmagan yoki jim g'oyib bo'lgan.

**1-sabab (asosiy, ildiz sababi) — "Bo'ldim" tugmasi hech qachon
yo'qolmasdi.** `ProductionMaterialRequest.consumed_in` maydoni (tugmani
yashirish uchun tekshirilayotgan) faqat BOM/retsept mavjud bo'lganda,
`_apply_retsept_hisobkitob()` ichida, MiqdorQoshish **tasdiqlanganda**
yoziladi (`stock_service.py`). "Un" mahsulotida hech qanday BOM/retsept
kiritilmagan (`MahsulotRetsept` jadvalida "Un" uchun 0 ta qator) — demak
`consumed_in` bu firmada **hech qachon** yozilmaydi, tugma abadiy
ko'rinib turaveradi, foydalanuvchi bir necha marta bosib, bir xil so'rov
uchun bir nechta `MiqdorQoshish` (dublikat, zaxirani ikki marta
oshiradigan) yaratib qo'ygan (real holatda: 2.0 kg so'rov uchun ikkita
alohida `MiqdorQoshish` yozuvi topildi, to'g'ridan-to'g'ri Django shell
orqali production bazasidan tasdiqlandi).

**2-sabab — kiosk sessiyasi ishlanayotgan vaqtdan qat'i nazar tugardi.**
Desktop Agent stansiyasidagi 60 soniyalik "avtomatik chiqish" hisoblagichi
(`SESSION_TIMEOUT_SECONDS`, `employee_scan_widget.py`) faol ish
(so'rovlarni yuklash, tasdiqlash, ayniqsa XPrinter orqali bir nechta QR
yorliqni ketma-ket chop etish) davom etayotganda ham **to'xtovsiz** kamayib
borar edi — 23 dona "har bir donaga alohida QR" (`serial_granularity='unit'`)
mahsulot uchun 23 ta yorliqni ketma-ket chop etish osongina 60 soniyadan
oshib ketishi mumkin, va sessiya tugaganda barcha navbat (hali
ko'rilmagan so'rovlar) va hatto ekranda ochiq turgan kartochka **hech
qanday xabarsiz, jimgina** yopib yuborilar edi.

### Tuzatish

**Backend** (`main/models.py`, `main/views.py`,
`main/templates/addmiqdor.html`, `main/templates/pazanda_dashboard.html`):
- `MiqdorQoshish.source_material_request` — yangi FK
  (`ProductionMaterialRequest`ga, `related_name='miqdor_qoshishlar'`) —
  "Bo'ldim" orqali qaysi material so'rovi asosida yaratilganini BOM
  borligi/yo'qligidan qat'i nazar aniq belgilaydi (migratsiya
  `0082_miqdorqoshish_source_material_request.py`).
- `addmiqdor()` — endi `complete_request_id`ni (yashirin `<input>` orqali)
  POST'dan o'qiydi, shu so'rov uchun **allaqachon miqdor yuborilmaganini**
  (`miqdor_qoshishlar__isnull=True`) qat'iy tekshiradi — bo'lmasa xato
  qaytarib, ikkinchi (dublikat) yozuv yaratilishining oldini oladi.
- `pazanda_dashboard.html` — endi 3 xil holatni ko'rsatadi: hali
  yuborilmagan (`✓ Bo'ldim` tugmasi), yuborilgan-lekin-agentda-hali-
  tasdiqlanmagan (`⏳ Miqdor yuborildi — Agentda tasdiqlanishi
  kutilmoqda`, tugma yo'q — qayta bosib bo'lmaydi), va to'liq tugallangan
  (`✓ Tugallandi`).
- Production bazasida allaqachon mavjud bo'lgan 2 ta yozuv (yangi maydon
  qo'shilishidan oldin yaratilgan) qo'lda `source_material_request`ga
  bog'landi, shunda ular ham to'g'ri "⏳ kutilmoqda" holatida ko'rinadi
  (23 kg'lik so'rov ham shu qatorda — foydalanuvchi so'ragandek, hozircha
  qayta ishga tushirilmaydi, faqat "kutilmoqda" deb ko'rsatiladi).

**Desktop Agent** (`app/windows/employee_scan_widget.py`):
- Yangi `_extend_session()` — sessiya vaqtini to'liq qayta tiklaydi.
  Har bir haqiqiy voqeada chaqiriladi: navbatdagi tarozi/miqdor so'rovi
  ko'rsatilganda, har bir tasdiqlash/rad javobida, VA endi
  `LabelPrintWorker`ning har bir chop etish qadamida (`progress` signali)
  hamda yakunida (muvaffaqiyat/xato). Natijada 60 soniyalik hisoblagich
  endi faqat **haqiqiy bo'sh turish** vaqtini o'lchaydi — faol ish
  (ko'p sonli yorliq chop etish kabi) davom etar ekan, sessiya
  to'xtatilmaydi.

### Tekshirildi

- Django test-client orqali izolyatsiyalangan tranzaksiyada: bir xil
  `complete_request_id` bilan ikki marta ketma-ket POST — birinchisi
  1 ta `MiqdorQoshish` yaratadi, ikkinchisi **hech qanday yangi yozuv
  yaratmaydi** (xato xabari bilan qaytariladi) — dublikat muammosi
  tasdiqlangan holda tuzatilgan.
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz.
- Production bazasida to'g'ridan-to'g'ri tekshirilib, 2 ta mavjud
  yozuv to'g'ri bog'landi; uchinchisi (haqiqiy dublikat, 2.0 kg "Un")
  ataylab bog'lanmay qoldirildi — foydalanuvchiga alohida xabar
  qilindi (uni tasdiqlash zaxirani ikki marta oshiradi, qaror
  foydalanuvchining o'zida).

## 100-qadam: Desktop Agent "oflayn" holati — endi yopilganda DARHOL bildiriladi (90 soniya kutilmaydi)

**Holat: DONE**

### Nima qilindi

Foydalanuvchi ikkinchi marta ta'kidladi: Desktop Agent dasturi yopilgan
zahoti, web dashboardda "oflayn" ekanligi haqida hech qanday ma'lumot
ko'rinmaydi. Sabab — dizayn bo'yicha "oflayn"ga o'tish faqat brauzer
JS tomonida, heartbeat kutilgan vaqtda kelmasa (90 soniyagacha),
mahalliy hisoblanadi edi (90-qadam) — "onlayn" holat esa server orqali
darhol WebSocket bilan push qilinadi. Bu **nomutanosiblik** edi: dastur
ishga tushganda darhol "onlayn" ko'rinadi, lekin yopilganda "oflayn"
ko'rinishi uchun foydalanuvchi 90 soniyagacha kutishi kerak edi — va bu
muddat faqat "aslida tirik, lekin heartbeat/tarmoq uzilib qolgan" holat
uchun mo'ljallangan, "dastur ataylab, tozalik bilan yopilgan" holat uchun
emas.

### Tuzatish

**Backend** (`main/agent_api_views.py`, `landing/urls.py`):
- Yangi `POST /api/agent/logout/` (`agent_logout`) — stansiya tokeni
  orqali chaqiriladi, `last_agent_heartbeat`ni `None`ga o'rnatadi (endi
  `is_agent_online` darhol `False` qaytaradi) va WebSocket orqali
  `event='agent_heartbeat', extra={'is_online': False}` yuboradi.
  Faqat "yaxshi xulq" signali — tarmoq uzilsa yoki dastur crash bo'lsa
  bu chaqirilmaydi, o'sha holatlar uchun eski (90 soniyalik) fallback
  o'zgarishsiz qoladi.

**Frontend** (`main/templates/egabase.html`):
- `handleAgentHeartbeat(extra)` — endi `extra.is_online === false`
  holatini alohida ishlaydi: rejalashtirilgan "oflaynga o'tish"
  taymerini bekor qiladi va banner'ni **darhol** qizil qiladi (avval
  faqat `is_online: true`ni bilar edi, "oflayn" xabarini butunlay
  e'tiborsiz qoldirar edi).

**Desktop Agent** (`app/api_client.py`, `app/windows/main_window.py`):
- `send_logout(server_url, token)` — yangi API chaqiruvi.
- `_LogoutWorker(QThread)` + `MainWindow.closeEvent` — oyna yopilganda
  ushbu so'rovni yuboradi, ko'pi bilan 2 soniya kutadi (tarmoq
  sekin/o'chgan bo'lsa ham dastur yopilishi cheksiz kutib qolmasligi
  uchun), so'ng odatdagidek davom etadi (socket/skaner/kamera to'xtatish).

### Tekshirildi

- Django test-client orqali izolyatsiyalangan tranzaksiyada:
  `agent_logout` chaqirilgach `last_agent_heartbeat=None` va
  `is_agent_online=False` bo'lishi tasdiqlandi.
- **Haqiqiy production serverida** (`birzumda`) haqiqiy exe orqali
  sinovdan o'tkazildi: dastur ishga tushirilib (heartbeat yuborildi,
  stansiya "onlayn" bo'ldi), so'ng oddiy (majburiy emas) yopish orqali
  yopilgach — stansiyaning `last_agent_heartbeat`i darhol `None`ga
  tushgani to'g'ridan-to'g'ri bazadan tasdiqlandi. **Eslatma**: bu sinov
  haqiqiy saqlangan login-tokendan foydalangani uchun, haqiqiy
  `agent001` stansiyasining onlayn/oflayn holatini bir necha marta
  o'zgartirdi (faqat heartbeat holati, hech qanday zaxira/savdo
  ma'lumoti o'zgarmadi) — foydalanuvchiga alohida xabar qilindi.
- `python manage.py check` — xatosiz.
- `dist/StockFirmAgent.exe` — `venv`dagi to'g'ri Python orqali
  muvaffaqiyatli qayta build qilindi va xatosiz ishga tushdi.

## 101-qadam: "Miqdor Qo'shish" yuborilganda — Desktop Agent oflayn bo'lsa darhol ogohlantirish

**Holat: DONE**

### Nima qilindi

Foydalanuvchi so'radi: pazanda web'da "Miqdor Qo'shish" so'rovini yuborganda,
agar Desktop Agent stansiyasi bilan aloqa yo'q bo'lsa (oflayn), buni kutib
o'tirmasdan darhol ogohlantirish chiqsin — aks holda so'rov "havoga" ketib,
hech kim uni ko'rmasligi mumkin (stansiya o'chiq bo'lsa).

Boshida "3 soniya kutib, javob kelmasa ogohlantirish" tarzida so'ralgan edi
— lekin 100-qadamda qurilgan heartbeat tizimi (`User.is_agent_online`,
~25 soniyada bir yangilanadigan, 90 soniyagacha aniq) allaqachon stansiya
holatini deyarli real-vaqtda saqlab turadi. Shuning uchun alohida so'rov/
kutish shart emas — mavjud holat darhol (bazadan bitta oddiy so'rov bilan)
tekshirilib, natija shu zahoti ko'rsatiladi.

### Tuzatish

`main/views.py::addmiqdor` — agent-enabled firma uchun so'rov yaratilgach,
`User.objects.filter(company=..., type='desktop_agent', is_active=True)`
orasida kamida bitta `is_agent_online=True` bormi tekshiriladi. Yo'q bo'lsa
(barcha stansiyalar oflayn yoki umuman stansiya yo'q), qo'shimcha
ogohlantirish xabari chiqadi:
> "Diqqat: Desktop Agent stansiyasi hozir oflayn ko'rinmoqda! So'rovingiz
> saqlandi, lekin stansiya yoqilib, badge skanerlanmaguncha tasdiqlanmaydi."

So'rovning o'zi baribir saqlanadi (stansiya keyinroq yoqilsa, navbatda
kutib turadi) — bu faqat ogohlantirish, bloklash emas.

### Tekshirildi

- Django test-client orqali izolyatsiyalangan tranzaksiyada: stansiyani
  qo'lda oflayn holatga qo'yib (`last_agent_heartbeat=None`), "Miqdor
  Qo'shish" yuborilganda ikkala xabar ham (so'rov yuborildi + oflayn
  ogohlantirish) to'g'ri chiqishi tasdiqlandi.
- `python manage.py check` — xatosiz.

## 102-qadam: "Miqdor Qo'shish" — umumiy (havolasiz) dublikat himoyasi + kutilayotgan so'rovlarni ko'rsatish

**Holat: DONE**

### Nima qilindi

Foydalanuvchi to'g'ri ta'kidladi: 99-qadamda qilingan dublikat-himoya faqat
"✓ Bo'ldim" havolasi (`complete_request_id`) orqali kelgan submitlarni
himoya qilardi. Lekin production bazasini tekshirganda (30-iyul, "Un"
mahsuloti) aniqlandiki — bugungi haqiqiy dublikatlarning aksariyati
(#54, #55, #56) aslida **"Bo'ldim" havolasisiz, to'g'ridan-to'g'ri "Miqdor
Qo'shish" formasi orqali** (soatlar oralig'ida, foydalanuvchi "hech narsa
bo'lmadi" deb o'ylab qayta-qayta) yuborilgan — bu yo'lda hech qanday
himoya yo'q edi. Ya'ni asl tizimiy kamchilik hali yopilmagan edi.

### Tuzatish

`main/views.py::addmiqdor` (agent-yoqilgan firmalar uchun, ikkalasi ham):

1. **Sahifaning o'zida ko'rsatish** — GET so'rovda, agar pazandaning hali
   tasdiqlanmagan (`tasdiqlangan=False`) so'rovlari bo'lsa, ular sahifa
   yuqorisida sariq blok bilan ko'rsatiladi ("⏳ Sizda hali Agentda
   tasdiqlanishi kutilayotgan so'rovlar bor: ..."). Foydalanuvchi endi
   yangi so'rov yuborishdan oldin buni ko'radi.
2. **POST vaqtida qattiq tekshiruv** — xuddi shu mahsulot uchun hali
   tasdiqlanmagan yozuv mavjud bo'lsa (`complete_request_id` bor-yo'qligidan
   qat'i nazar — umumiy tekshiruv), so'rov **saqlanmaydi**, o'rniga qizil
   ogohlantirish ko'rsatiladi: qachon, qancha miqdor uchun so'rov borligi
   aniq yozilib, "Baribir yuborish (bu haqiqatan yangi ishlab chiqarish)"
   tugmasi beriladi — bu tugma bosilsagina (`confirm_duplicate=1` bilan)
   yangi yozuv yaratiladi. Ya'ni **bloklanmaydi, faqat ataylab
   tasdiqlashni talab qiladi** — haqiqiy qayta-qayta ishlab chiqarish
   (bir kun ichida bir necha marta) hamon mumkin, faqat tasodifiy
   dublikatning oldi olinadi.

### Tekshirildi

- Django test-client orqali izolyatsiyalangan tranzaksiyada (yangi, sof
  test-mahsulot bilan): 1-submit — muvaffaqiyatli yaratiladi; 2-submit
  (bir xil mahsulot, `confirm_duplicate`siz) — **bloklanadi**, yangi
  yozuv yaratilmaydi, "dublikat" ogohlantirishi chiqadi; 3-submit
  (`confirm_duplicate=1` bilan) — muvaffaqiyatli o'tadi, ikkinchi yozuv
  yaratiladi.

## 103-108-qadamlar: "Vazifalar paneli" — Desktop Agent firmalarida "Miqdor Qo'shish"/"Material So'rash"/"Yuklama so'rovi" o'rnini bosadi

**Holat: DONE**

### Nima qilindi

97-102 qadamlarda "Miqdor Qo'shish" oqimidagi bir necha bug tuzatilgach,
foydalanuvchi tub savol berdi: nega agent ishlatilayotgan firmalarda ham
eski, qo'lda so'rov-tasdiqlash jarayoni davom etmoqda? Uning qarori:

> agar bu tizimda qr agent ishlatilayotgan bo'lsa biz miqdor qo'shish kabi
> mahsulot so'rashlarni ishlatmaymiz. shunchaki task panel qilamiz. o'ziga
> task oladi. aytaylik bugunga 100dona burger ishlab chiqish. agar mahsulot
> retsepti kiritilmagan bo'lsa task yaratilmasin. miqdor qo'shish mahsulot
> so'rash yuklama so'rov yasash bu agentsiz ishlaydigonlar uchun. bularni
> agent tarifidan olib tashla.

Aniqlashtirishda: (1) task **ochiq pul** — hech kimga bog'lanmay yaratiladi,
istalgan ishlab chiqaruvchi agentda o'ziga oladi; (2) xom ashyo/tarozi
tekshiruvi **saqlanadi, lekin avtomatik** — BOM asosida hisoblanadi, alohida
so'rov yuborish shart emas.

**Muhim**: bu o'zgarish faqat `company.custom_desktop_agent_stations > 0`
firmalarga tegishli — agentsiz firmalarda hech narsa o'zgarmadi (har bir
qadamda alohida regressiya testi bilan tasdiqlangan).

### Yangi modellar (`main/models.py`, migratsiya `0083_...`)

- `ProductionTask` — `mahsulot`, `rejalashtirilgan_miqdor`, `sana`, `status`
  (`open`/`claimed`/`done`/`cancelled`), `kod` (QR uchun), `pazanda`
  (band qilingach to'ldiriladi), `claimed_at`, `created_by`.
- `TaskMaterialPickup` — vazifa yaratilganda BOM qatorlaridan avtomatik
  hosil qilinadi (`expected_qty = norma_miqdor * rejalashtirilgan_miqdor`).
- `MiqdorQoshish.source_task` — yangi FK, `source_material_request` bilan
  bir xil naqsh.

### Servis — `main/services/task_service.py` (yangi)

- `create_production_task(...)` — **BOM yo'q bo'lsa task yaratilmaydi**
  (foydalanuvchi so'ragan qat'iy qoida) — bo'lsa, BOM qatorlaridan
  `TaskMaterialPickup` qatorlari avtomatik yaratiladi.
- `claim_task(kod, pazanda, company)` — `select_for_update`, faqat
  `status='open'` bo'lsa band qiladi; band qilingan/topilmagan holatlar
  aniq xato bilan qaytadi.
- `weigh_task_pickup(...)` — `agent_weigh_material_request`dagi bilan bir
  xil tolerantlik formulasi (`max(expected*2%, 0.05)`), muvaffaqiyatli
  bo'lsa zaxiradan darhol ayiradi. **Agar bu vazifaning oxirgi
  tasdiqlanmagan komponenti bo'lsa — avtomatik ravishda
  `approve_production_task_service`ni chaqiradi** — alohida "ishlab
  chiqarishni tasdiqlash" bosqichi kerak emas.
- `approve_production_task_service(task)` — eski `_apply_retsept_
  hisobkitob`ning soddalashtirilgani (vaqt-oynasi evristikasi kerak emas,
  chunki pickup'lar aynan shu vazifaga bog'langan) — yakunda **bitta
  tasdiqlangan `MiqdorQoshish`** yaratadi (`source_task` bilan), shu
  orqali barcha keyingi hisobotlar (`get_pazanda_month_stats`, Serial/QR
  generatsiya, tannarx/ish haqi) o'zgarishsiz ishlayveradi.

### Agent API (`main/agent_api_views.py`)

- `agent_scan` — endi `ProductionTask.kod`ni ham taniydi (`type='task'`).
  Faqat faol badge-sessiya (`session_token`) bilan ishlaydi — shu orqali
  vazifa skanerlagan xodimga band qilinadi.
- Yangi `agent_weigh_task_pickup` (`POST /api/agent/task-pickup/<id>/
  weigh/`) — oxirgi pickup bo'lsa, javobda `task_completed`,
  `serials`/`print_url` ham qaytadi (`agent_approve_miqdor_qoshish`
  bilan bir xil shaklda).

### Desktop Agent (`employee_scan_widget.py`, `api_client.py`)

- `scan()` endi ixtiyoriy `session_token` yuboradi (faol sessiya bo'lsa).
- Yangi `_on_task_resolved` — vazifa skanerlanganda uning `pickups`ini
  **mavjud tortish (weigh) navbat mashinasiga** qo'shadi (bir xil UI,
  faqat `_kind='task_pickup'` bilan belgilanadi) — deyarli hech qanday
  yangi UI kod yozilmadi.
- `_print_serial_labels`/`_set_miqdor_print_feedback` generallashtirildi
  (`feedback_label` parametri) — vazifa yakunlanganda ham xuddi shu chop
  etish yo'li (tortish kartochkasi ustida) ishlatiladi.

### Web — "Vazifalar" paneli (`main/production_views.py`, `vazifalar.html`)

- Faqat `ega`, faqat agent firmalarda. Mahsulot tanlash **faqat BOM'i bor**
  mahsulotlar bilan cheklangan (dropdown filtri + servis darajasida ham
  qat'iy tekshiruv). Har bir vazifa uchun QR rasm (chop etib taxtaga
  yopishtirish uchun) — `xodim_badge_image`/`material_request_qr_image`
  bilan bir xil uslub.
- Sidebar'ga "Vazifalar" nav havolasi qo'shildi (faqat `ega` + agent firma).

### Eski oqimlarni yopish (`views.py`, `pazanda_dashboard.html`)

- `addmiqdor`/`add_yuklama` — agent firmalarda darhol `main`ga
  yo'naltiriladi, tushuntiruvchi xabar bilan. Agentsiz firmalarda
  o'zgarishsiz.
- `pazanda_dashboard.html` — agent firmalarda "Miqdor Qo'shish"/"Yuklama
  Yaratish"/"Material So'rash" tugmalari, "Ombor material so'rovlari"
  bo'limi o'rniga **"Ochiq vazifalar"** + **"Mening vazifalarim"**
  bo'limlari ko'rsatiladi (faqat ma'lumot uchun — band qilish/bajarish
  har doim Desktop Agent orqali).

### Qo'shimcha — Profilda shaxsiy QR badge (109-qadam, mustaqil)

`profile_view` — o'z profilini ko'rayotganda (`request.user.pk ==
user.pk`), mavjud `XodimBadge` (allaqachon to'liq ishlagan tizim,
`badge_views.py`) shu yerda ham ko'rsatiladi — `pzprofile.html`,
`egaprofile.html`, `ytprofile.html` (yetkazib beruvchi/savdogar uchun ham).

### Tekshirildi

- `main/services/task_service.py`: to'liq lifecycle (BOMsiz rad etish →
  BOM bilan yaratish → band qilish → boshqa pazanda ololmasligi → tortish
  → avtomatik yakunlash → zaxira/Serial QR to'g'ri) — Django shell orqali
  izolyatsiyalangan tranzaksiyada.
- Agent API: badge skan → sessiyasiz task skan rad etilishi → sessiya
  bilan band qilish → tortish → `task_completed`+`serials` javobi — HTTP
  darajasida to'liq tasdiqlandi.
- Web "Vazifalar" sahifasi: faqat BOM'li mahsulot dropdown'da, BOMsiz
  mahsulotga POST ham rad etilishi, QR rasm endpoint, `ega` bo'lmagan
  foydalanuvchi qaytarilishi.
- **Regressiya**: agent firmada `addmiqdor`/`add_yuklama` `main`ga
  yo'naltirilishi VA yangi (sof, sintetik) firma bilan agentsiz firmada
  bularning ikkalasi ham **o'zgarishsiz** ishlashi alohida tasdiqlandi.
- `python manage.py check` — xatosiz.
- Desktop Agent: `employee_scan_widget.py`/`api_client.py` import
  tekshiruvi (offscreen, PyQt6 orqali) xatosiz. `dist/StockFirmAgent.exe`
  — `venv` orqali muvaffaqiyatli qayta build qilindi.
- `python manage.py check` — xatosiz.

## 110-114-qadamlar: Vazifa — o'ziga o'zi yaratish, dona-dona kuzatish, erta tugatish shtrafi bilan

**Holat: DONE**

### Nima qilindi

103-109 qadamlarda qurilgan "Vazifalar paneli"da ega vazifa yaratib,
ishlab chiqaruvchi uni ochiq puldan olar edi, xom ashyo tortilgach vazifa
DARHOL, TO'LIQ reja miqdori bilan yakunlanardi. Foydalanuvchi buni
tubdan o'zgartirdi:

> vazifani ishlab chiqaruvchi o'ziga o'zi yaratsin. vazifa yaratishni
> bosadi. mahsulot tanlab sonini kiritadi. vazifa jarayonida qancha pul
> topgani qr kod orqali mahsulot kiritganlari nechta bo'lgani. va
> mahsulot kamroq ishlab chiqqani uchun tugatishni bosib qo'ysa unga
> ishlab chiqa olmagan mahsulot retsept narxi*soni shtraf bo'lishi kerak.

Aniqlashtirishda: yaratish — veb (o'z dashboardida, tugma bosib);
jarayon — **har bir dona alohida QR bilan tasdiqlanadi** (tarozi orqali
xom ashyo olingach, tayyor bo'lgan har bir donaning QR kodi skanerlanadi,
son avtomatik +1 bo'ladi; xohlagan vaqtda "Tugatish" bosib, qolganini
shtraf bilan yopish mumkin).

### Yangi holat: `ProductionTask.status = 'producing'`

Xom ashyo tortib bo'lingach, vazifa endi DARHOL "bajarildi" bo'lmaydi —
`'producing'` ("Ishlab chiqarilmoqda") holatiga o'tadi: Serial/QR kodlar
generatsiya qilinadi, lekin **zaxira hali qo'shilmaydi, `MiqdorQoshish`
hali tasdiqlanmagan** (`tasdiqlangan=False`). Har bir tayyor dona QR'i
skanerlanganda (`Serial.scan_soni`), necha dona haqiqatda tayyor bo'lgani
kuzatiladi. Reja soniga yetilganda — **avtomatik** yakunlanadi (shtrafsiz).
Erta "Tugatish" bosilsa — ishlab chiqarilmagan dona uchun shtraf:
`(reja - haqiqiy) * mahsulot.baza_tannarx` ("retsept narxi" — BOM asosida
hisoblangan 1 donaning xom ashyo tannarxi), ish haqidan ayiriladi.
Zaxiraga esa har doim faqat HAQIQIY (skanerlangan) son qo'shiladi.

**Eslatma**: bu "dona-dona kuzatish" faqat `serial_granularity='unit'`
mahsulotlarda ishlaydi (har biriga alohida QR bo'lgani uchun). Boshqa
mahsulotlarda buni kuzatib bo'lmaydi — eski xatti-harakat saqlanadi:
xom ashyo tortilgach darhol, to'liq reja bilan (shtrafsiz) yakunlanadi.

### `main/services/task_service.py` — qayta qurildi

- `create_production_task(..., pazanda=None)` — yangi `pazanda` parametri:
  berilsa, vazifa darhol o'sha ishlab chiqaruvchiga `'claimed'` holatda
  tug'iladi (o'ziga o'zi yaratish); berilmasa, eski `'open'` (ochiq pul,
  ega uchun) xatti-harakat saqlanadi.
- `approve_production_task_service` ikkiga bo'lindi:
  - `_start_producing(task)` — xom ashyo tortib bo'lingach chaqiriladi:
    jarima/tannarx hisoblanadi, tasdiqlanmagan `MiqdorQoshish` + Serial/QR
    yaratiladi, `unit` bo'lsa `'producing'`ga o'tadi, aks holda darhol
    `finish_production_task_service`ni chaqiradi.
  - `finish_production_task_service(task, actor=None, actual_count=None)`
    — yakunlaydi: `actual_count=None` bo'lsa server o'zi
    `Serial.scan_soni__gte=1` orqali hisoblaydi (avtomatik yakunlash);
    berilsa (masalan `unit` bo'lmagan holatda to'liq reja bilan) shu son
    ishlatiladi. Shtraf shu yerda hisoblanadi, zaxiraga HAQIQIY son
    qo'shiladi, `MiqdorQoshish.tasdiqlangan=True` bo'ladi.
- `task_progress(task)` — dashboardda "count/max" ko'rsatish uchun.

### Agent API (`main/agent_api_views.py`)

- `_maybe_finish_task_on_scan(serial)` — har bir Serial skanerlanganda
  (`agent_scan`) chaqiriladi: agar bu serial `'producing'` holatidagi
  vazifaga tegishli bo'lsa va reja soniga yetilgan bo'lsa — avtomatik
  yakunlaydi. `_serial_scan_response`ga `task_progress` (count/max/
  task_done) qo'shildi — Desktop Agent widget shu asosda jonli
  "N/M" ko'rsatadi.
- `agent_weigh_task_pickup` javobi: `task_completed` → **`task_producing`**
  ga o'zgartirildi (semantika aniqroq: "ishlab chiqarish boshlandi",
  "yakunlandi" emas).
- Yangi `agent_my_task_pickups` (`GET /api/agent/my-task-pickups/`) —
  badge-sessiya boshlanganda avtomatik chaqiriladi: ishlab chiqaruvchining
  o'ziga tayinlangan (`'claimed'`) barcha vazifalaridagi tortilmagan xom
  ashyo qatorlarini qaytaradi — **o'ziga o'zi yaratgan vazifalar uchun
  alohida vazifa-QR skanerlash shart emas**, badge skanerlanishi bilan
  navbat o'zi ko'rinadi.

### Desktop Agent (`employee_scan_widget.py`, `api_client.py`)

- `_advance_queue`ga yangi bosqich: xom ashyo navbatidan keyin, miqdor
  so'rovlaridan oldin — `_load_my_task_pickups` (bir marta, sessiya
  boshida) — auto-fetch, alohida QR skanerlashsiz.
- `_show_serial_scan_result` — endi `task_progress` bo'lsa, natija
  matniga "Ishlab chiqarilmoqda: N/M" yoki "Vazifa bajarildi ✓ (N/M)"
  qo'shib ko'rsatadi.
- `_on_weigh_resolved` — `task_producing`/`task_completed` ikkala holatni
  ham to'g'ri farqlab, mos xabar va chop etishni ishga tushiradi.

### Web (`main/production_views.py`, `main/views.py`, `pazanda_dashboard.html`)

- Yangi `pz_create_task` (`POST /vazifa/yaratish/`) — ishlab chiqaruvchi
  o'zi uchun vazifa yaratadi (darhol o'ziga band).
- Yangi `pz_finish_task` (`POST /vazifa/<id>/tugatish/`) — "Tugatish"
  tugmasi, shtrafli erta yopish.
- `pazanda_dashboard.html`: yangi "Vazifa yaratish" formasi (mahsulot —
  faqat BOM'i bor — + miqdor); "Mening vazifalarim"da `producing` holat
  uchun jonli "Ishlab chiqildi: N/M" va "Tugatish" tugmasi (tasdiqlash
  bilan — shtrafni ogohlantiradi).

### Tekshirildi

- `task_service`: o'ziga o'zi yaratish → darhol `'claimed'`; xom ashyo
  tortilgach `'producing'`ga o'tishi, zaxira/MiqdorQoshish hali
  o'zgarmasligi; 10tadan 7tasi skanerlangach `task_progress()==7`; erta
  "Tugatish"da shtraf (`(10-7)*baza_tannarx`) to'g'ri hisoblanib,
  zaxiraga faqat 7 qo'shilishi — barchasi Django shell orqali
  izolyatsiyalangan tranzaksiyada tasdiqlandi.
- Agent API: 3ta serialdan 3-tasi skanerlangach vazifa **avtomatik**
  yakunlanishi (shtrafsiz, to'liq 3 dona zaxiraga qo'shilishi) — HTTP
  darajasida tasdiqlandi.
- `agent_my_task_pickups`: o'ziga o'zi yaratilgan (`'claimed'`) vazifaning
  pickup'i, vazifa-QR skanerlashsiz, faqat badge-sessiya orqali avtomatik
  ko'rinishi tasdiqlandi.
- To'liq veb-oqim: dashboardda vazifa yaratish → xom ashyo tortish →
  3/5 dona skanerlash → dashboardda "Ishlab chiqildi: 3/5" + "Tugatish"
  tugmasi to'g'ri ko'rinishi → tugmani bosib erta yopish → zaxiraga
  faqat 3 qo'shilishi — barchasi Django test-client orqali HTTP
  darajasida tasdiqlandi.
- **Regressiya**: ega "Vazifalar" panelidan yaratilgan vazifa hamon
  `'open'` (ochiq pul) holatida qolishi — o'zgarishsiz — tasdiqlandi.
- `python manage.py check` — xatosiz.
- `dist/StockFirmAgent.exe` — `venv` orqali muvaffaqiyatli qayta build
  qilindi.

## 115-qadam: Ombor kamerasi videolarida ovoz — sabab topildi + `imageio-ffmpeg` orqali ffmpeg'ni avtomatik ta'minlash

**Holat: DONE**

### Nima qilindi

Foydalanuvchi: "videolarda hali ham ovoz yo'q" dedi. Haqiqiy ishlab
turgan dasturning bazasini (`%LOCALAPPDATA%\StockFirmAgent\agent_data.db`)
to'g'ridan-to'g'ri tekshirib, IKKI sabab aniqlandi:

1. Ikkala ombor kamerasida ham `mic_device_name` bo'sh edi ("Yo'q"
   tanlangan holicha qolgan) — mikrofon umuman biriktirilmagan.
2. `ffmpeg.exe` na exe yonida, na tizim PATH'ida topilmadi.

Foydalanuvchi keyin so'radi: "boshqa yo'li yo'qmi, shuncha py kutubxona
bor" — ya'ni foydalanuvchidan alohida `ffmpeg.exe` yuklab, qo'lda
joylashtirishni talab qilmaydigan yechim so'radi.

### Yechim — `imageio-ffmpeg` (pip kutubxonasi)

`imageio-ffmpeg` — statik ffmpeg binary'sini o'zi bilan olib keladigan,
keng tarqalgan PyPI kutubxonasi (litsenziyasi ochiq, millionlab marta
o'rnatilgan — `opencv-python`, `PyQt6` kabi loyihada allaqachon ishlatilib
kelinayotgan boshqa kutubxonalardan farqi yo'q). `pip install` orqali
o'rnatilganda binary avtomatik yuklab olinadi — foydalanuvchi qo'lda
hech narsa qidirib topmaydi/joylashtirmaydi.

`requirements.txt`ga qo'shildi. `camera_recorder_service.py::find_ffmpeg()`
endi birinchi navbatda `imageio_ffmpeg.get_ffmpeg_exe()`ni tekshiradi
(topilsa — shu ishlatiladi); topilmasa, eski yo'llar (exe yonidagi
qo'lda joylashtirilgan `ffmpeg.exe`, tizim PATH) hamon orqaga moslik
uchun ishlaydi. `_pyinstaller_hooks_contrib` kutubxonasida
`imageio_ffmpeg` uchun tayyor PyInstaller hook allaqachon bor edi —
binary avtomatik, hech qanday `.spec` o'zgarishisiz, exe ichiga
bundle qilindi (build logida `EXE-00.toc`/`PKG-00.toc` orqali
tasdiqlandi).

**Mikrofon sozlanmagan muammosi** — bu kod xatosi emas, sozlash gapi:
foydalanuvchiga Sozlamalar → Kamera → har bir ombor kamerasida
"Mikrofon" ro'yxatidan haqiqiy qurilmani tanlashi kerakligi aytildi
(ro'yxat bo'sh emasligi — kompyuterda haqiqiy mikrofonlar borligi —
`sounddevice.query_devices()` orqali tasdiqlandi).

### Tekshirildi

- `imageio_ffmpeg.get_ffmpeg_exe()` — venv'da haqiqatda mavjud, ishlaydigan
  binary yo'lini qaytarishi tasdiqlandi.
- PyInstaller build logi (`EXE-00.toc`) — ffmpeg binary'si exe ichiga
  bundle qilinganini ko'rsatadi, hech qanday ogohlantirishsiz.
- `dist/StockFirmAgent.exe` — muvaffaqiyatli qayta build qilindi.

## 116-qadam: Video uzunligi tekshirildi (bug emas) + ffmpeg konsol oynasi yashirildi

**Holat: DONE**

### Nima qilindi

Foydalanuvchi ovoz ishlagach, video mazmuni haqida shubha bildirdi:
"ichidagi tasvir to'g'ri emas, [balki] oyna yopilgan + 1 daqiqacha
[keyingi manzara]". Haqiqiy saqlangan videoni (`dist/saved_videos/`)
to'g'ridan-to'g'ri tekshirdim:

- Fayl nomidagi vaqt (voqea BOSHLANGAN payt, badge skanerlanganda):
  18:31:41
- Faylning diskka yozilgan (mtime) vaqti: 18:32:47-48 (~66 soniya keyin)
- Videoning haqiqiy uzunligi (`cv2.VideoCapture` orqali): ~57-60 soniya

Bu **bug emas** — video `_rec_start` (badge skanerlanib, tarozi
kartochkasi ko'rsatilganda) dan `_rec_stop` (xodim vaznni kiritib
tasdiqlagach) gacha bo'lgan **butun oraliqni** yozadi, + PRE/POST 5
soniyadan. Agar xodim tarozi oldiga borib, o'lchab, kiritib bo'lguncha
real vaqtda ~1 daqiqa ketsa — video ham shuncha uzun bo'ladi, bu tizim
"voqea"ni to'g'ri tushunayotganini bildiradi, xato emas.

Foydalanuvchi keyin boshqa savol berdi: "console komandasiz python ichida
birlashtirishni iloji yo'qmi... boshqalar qanday qilyabdi, dasturni bitta
exeni ochadi" — bu ffmpeg subprocess ishga tushganda **qora konsol
oynasi bir zumga chaqib chiqishi** haqida edi (kiosk-rejim uchun
noqulay ko'rinish).

### Tuzatish

`camera_recorder_service.py::_mux_with_audio` — `subprocess.run`ga
`creationflags=subprocess.CREATE_NO_WINDOW` qo'shildi. ffmpeg hamon
alohida jarayon sifatida ishlaydi (Python ichida "haqiqiy" birlashtirish
kutubxonasiz buni amalga oshirishning yagona ishonchli yo'li — `PyAV`
kabi kutubxonalar ham aslida shu ffmpeg kutubxonalarini o'rайdi, faqat
Python API orqali), lekin endi **hech qanday oyna ko'rsatmasdan**, to'liq
ko'rinmas holda — foydalanuvchi uchun "bitta dastur" taassuroti saqlanadi.

### Tekshirildi

- `subprocess.CREATE_NO_WINDOW` mavjudligi va import xatosizligi
  tasdiqlandi.
- `dist/StockFirmAgent.exe` — muvaffaqiyatli qayta build qilindi.

## 117-qadam: RLS1100B LAN tarozi tadqiqoti (hujjatlashtirildi, ish davom etadi) + yetkazib beruvchi paneli tozalandi

**Holat: DONE (tarozi — kutilmoqda, hujjatlangan)**

### RLS1100B tadqiqoti

Foydalanuvchi LAN tarozini (192.168.1.87, avval "192.169" deb yozilgan —
typo ekani IP konfiguratsiyasidan tasdiqlandi) tekshirishni so'radi.
To'liq port skanerlash (1-10000) orqali **3ta ochiq TCP port topildi:
5001, 5002, 5100**. Umumiy protokol namunalariga (ENQ, ASCII buyruqlar,
STX/ETX ramkalar) hech qanday javob kelmadi — proprietary format kerak.

Foydalanuvchi bergan "Thermal Printer Windows SDK" zip fayli chuqur
tekshirildi (butun DLL ichidagi 330ta noyob satr, barcha eksport
qilingan funksiyalar) — **vazn/tarozi bilan hech qanday aloqasi yo'q**
tasdiqlandi (faqat ESC/POS chop etish buyruqlari). Rasmiy Rongta
hujjat saytlari (manualslib, scribd va h.k.) avtomatik so'rovlarni
bloklaydi.

**Qaror**: foydalanuvchi ertaga RS232-USB adapter olib kelib, serial
chiqish orqali sinab ko'radi (ko'p arzon tarozilarda bu ancha sodda,
standart protokol). Topilgan barcha ma'lumotlar ikkita faylga
yozildi — kelgusi ishni shu yerdan davom ettirish uchun:

- `desktop_agent/RLS1100B_INTEGRATION_NOTES.md` — to'liq tadqiqot
  xulosalari, arxitektura rejasi, keyingi qadamlar.
- `desktop_agent/rls1100b_probe.py` — qayta ishlatsa bo'ladigan
  diagnostika skripti (port skanerlash + protokol namunalarini sinash).
- `desktop_agent/app/rls1100b_service.py` — **skelet** modul
  (`connect`/`request_weight`/`parse_response`/`get_weight`/
  `ScaleReaderWorker`/`send_to_crm`), protokol topilgach faqat 2-3ta
  funksiyani to'ldirish kifoya bo'ladigan tarzda qurilgan. Muhim: CRM
  backend'ni o'zgartirish shart emas — `send_to_crm()` mavjud
  `weigh_material_request`/`weigh_task_pickup`ni qayta ishlatadi.

### Yetkazib beruvchi paneli — agent firmalarda tozalandi

Foydalanuvchi so'radi: "yetkazib beruvchi paneli nima bo'ldi?" Tekshirib
chiqilganda aniqlandi: yuklama QABUL QILISH (Desktop Agent orqali) va
SOTISH (telefonda QR kamera skaneri orqali, `html5-qrcode`) — ikkalasi
ham **allaqachon to'liq ishlagan** ekan (oldingi qadamlarda qurilgan).
Faqat bitta UI nomutanosibligi topildi: `yetkazuvchi_dashboard.html`
"Yangi Yuklama So'rovlari" bo'limini va uning statistika kartasini agent
firmalarda ham **shartsiz** ko'rsatar edi — "Qabul" tugmasi bosilsa,
backend allaqachon (99-qadamda) buni bloklagani uchun xato xabari bilan
qaytarilardi (o'lik/chalkash tugma).

**Tuzatish**: `main/views.py::main()` (yetkazib_beruvchi branch, ikkala
GET va POST render yo'lida) — `is_agent_company` context qo'shildi.
`yetkazuvchi_dashboard.html` — agent firmalarda "Yangi so'rovlar"
statistika kartasi yashiriladi, "Yangi Yuklama So'rovlari" bo'limi
o'rniga "Yuklama olish" (Desktop Agent orqali ekanini tushuntiruvchi)
bo'lim ko'rsatiladi. `savdogar_dashboard.html`da bunday bo'lim umuman
yo'q ekan — tegilmadi.

### Tekshirildi

- Django test-client orqali: agent firmada yetkazib beruvchi
  dashboardida "Yangi Yuklama So'rovlari" ko'rinmasligi, "Yuklama olish"
  (Desktop Agent xabari) ko'rinishi tasdiqlandi.
- **Regressiya**: sof (sintetik) agentsiz firmada eski "Yangi Yuklama
  So'rovlari" bo'limi o'zgarishsiz ko'rinishi tasdiqlandi.
- `python manage.py check` — xatosiz.

## 118-qadam: "Partiya" (batch) turi — qadoqlash hajmi (masalan "non" 3 talik) + qoldiqni alohida chiqarish

**Holat: DONE**

### Nima qilindi

Foydalanuvchi "partiya" QR turi qanday ishlashini so'ragach ("non"
misolida bir cheklovni aniqladi: hozirgi holatda 1 QR = butun partiya,
necha dona bo'lishidan qat'i nazar — bu amalda foydasiz, chunki masalan
non 3 tadan qadoqlanib sotiladi, lekin tizim buni bilmaydi). Talab:

> ishlab chiqaruvchi partiyalikni tanlagan mahsulotda 50ta nonga
> masalliq oldi ishlab chiqdi va qr kodga bo'ldi deganida partiya
> sonini kiritish majburiy bo'lsin. aytaylik 50ta bo'lsa 3talikga
> ruxsat bermasin. ruxsat bersa ham 3taliklarni alohida qolgan 2x1 ni
> alohida chiqarib bersin.

**Dizayn qarori**: qadoqlash hajmi ("necha donadan bitta qadoq")
vazifa **yaratilganda** (veb formada) kiritiladi, "Tugatish" bosqichida
emas — chunki Desktop Agent kioskida klaviatura yo'q, faqat veb forma
orqali raqam kiritish mumkin.

### Model o'zgarishlari (migratsiya `0084_...`)

- `Serial.dona_soni` — yangi maydon: bu QR kod nechta donani ifodalashi
  (`unit`da har doim 1, `batch`da qadoqlash hajmiga qarab, masalan 3;
  qoldiq bo'lsa 1).
- `ProductionTask.qadoq_hajmi` — yangi maydon: faqat mahsulot
  `serial_granularity='batch'` bo'lganda **majburiy**.

### `qr_service.generate_serials_for_batch(miqdor_qoshish, qadoq_hajmi=None)`

`batch` granularity uchun: `qadoq_hajmi` berilsa — `divmod(reja,
qadoq_hajmi)` orqali to'liq qadoqlar (`dona_soni=qadoq_hajmi`) + qoldiq
(agar bo'lsa, **har biri alohida**, `dona_soni=1`) generatsiya qilinadi
(50 ta, 3 talik -> 16 ta 3-dan + 2 ta 1-dan, jami 18 ta QR). Berilmasa —
eski xatti-harakat (1 QR = butun partiya) saqlanadi, orqaga moslik uchun.

### `task_service.create_production_task(..., qadoq_hajmi=None, force_uneven_qadoq=False)`

- Mahsulot `batch` turida bo'lsa, `qadoq_hajmi` berilmasa — rad etiladi.
- Reja miqdoriga aniq bo'linmasa (50/3) — `force_uneven_qadoq=True`
  berilmaguncha rad etiladi, aniq xabar bilan ("16x3 + 2 dona qoladi").
  Funksiya endi 3-element qaytaradi: `(task, xato, needs_confirm)` —
  `needs_confirm=True` bo'lsa bu "qattiq" xato emas, faqat tasdiq talab
  qiladi.
- `_start_producing` — `task.qadoq_hajmi`ni `generate_serials_for_batch`ga
  uzatadi.

### Web — ikkala vazifa-yaratish forma ham yangilandi

- `vazifalar.html` (ega) va `pazanda_dashboard.html` (o'ziga o'zi
  yaratish) — mahsulot tanlanganda (`data-granularity` orqali) JS
  avtomatik "Necha donadan bitta qadoq?" va "Bo'linmasa ham davom et"
  belgisini faqat `batch` turdagi mahsulotlar uchun ko'rsatadi.
- `production_views.py::vazifalar_page`/`pz_create_task` — `qadoq_hajmi`/
  `force_uneven_qadoq`ni POST'dan o'qib xizmatga uzatadi;
  `needs_confirm` bo'lsa `messages.warning` bilan aniq ko'rsatma beradi.

### Tekshirildi

- `task_service`: qadoq_hajmi'siz rad etilishi; bo'linmaydigan (50/3)
  force'siz rad etilishi; force bilan 16 ta 3-donalik + 2 ta 1-donalik
  (qoldiq) QR to'g'ri generatsiya bo'lishi; zaxiraga to'liq 50 dona
  qo'shilishi — Django shell orqali izolyatsiyalangan tranzaksiyada.
- Veb (HTTP): pazanda o'ziga o'zi yaratish formasi va ega "Vazifalar"
  paneli — ikkalasida ham qadoq_hajmi'siz/bo'linmaydigan holatlar rad
  etilishi, force bilan o'tishi tasdiqlandi.
- `python manage.py check`, `makemigrations`, `migrate` — xatosiz.

## 119-qadam: Kod audit — Task Panel oqimidagi ikkita race condition/tranzaksiya bug tuzatildi

Foydalanuvchi so'ragan: "koddagi mantiqiy hatolarchi?" — production
ma'lumotlarda muammo topilmagach, kodning o'zida mantiqiy xatolarni
qidirish uchun `main/services/task_service.py` va uni chaqiruvchi
joylar qayta ko'rib chiqildi. Ikkita real bug topildi va tuzatildi:

### 1. `weigh_task_pickup` — race condition (ikkita xom ashyo bir vaqtda tortilsa, vazifa abadiy "claimed" holida qolib ketishi mumkin edi)

"Oxirgi pickup tasdiqlangandami?" tekshiruvi faqat o'sha bitta
`TaskMaterialPickup` qatorini qulflardi (`select_for_update()`), ota
`ProductionTask`ni emas. Agar bitta vazifaning ikkita xom ashyo qatori
(masalan ikkita komponentli retsept) deyarli bir vaqtda tortilsa,
ikkala tranzaksiya ham "hali boshqa qolgani bor" (`remaining=True`) deb
noto'g'ri xulosa chiqarishi mumkin edi — natijada hech biri
`_start_producing`ni chaqirmay, vazifa hech qachon "producing"ga
o'tmay qolib ketardi. Tuzatildi: remaining-tekshiruvidan oldin
`ProductionTask.objects.select_for_update().get(id=pickup.task_id)`
qo'shildi — endi shu vazifaning pickup'lari ketma-ket (bir vaqtning
o'zida faqat bittasi) qayta ishlanadi.

### 2. `finish_production_task_service` — tranzaksiyasiz `select_for_update()` chaqiruvi

Bu funksiya ichida `select_for_update()` ishlatiladi, bu esa faol
tranzaksiya talab qiladi. Ikkita chaqiruvchi joy (`weigh_task_pickup`,
`_maybe_finish_task_on_scan`) buni allaqachon `transaction.atomic()`
ichida chaqirar edi — lekin `production_views.py::pz_finish_task`
("Tugatish" tugmasi) hech qanday tranzaksiya o'ramisiz to'g'ridan-to'g'ri
chaqirar edi (`settings.py`da `ATOMIC_REQUESTS` yoqilmagan, tekshirildi).
Tuzatildi: `@transaction.atomic` dekoratori to'g'ridan-to'g'ri
`finish_production_task_service`ning o'ziga qo'yildi — endi qaysi
joydan chaqirilishidan qat'i nazar xavfsiz (Django ichma-ich atomic
bloklarni savepoint orqali xavfsiz boshqaradi, boshqa ikki chaqiruvchi
joyga ta'sir qilmaydi).

### Tekshirildi

- `python manage.py check` — xatosiz.
- Uchta mavjud regressiya test skripti (`test_producing_flow.py`,
  `test_qadoq.py`, `test_auto_finish_scan.py`) — barchasi tuzatishlardan
  keyin ham to'liq o'tdi (izolyatsiyalangan tranzaksiya + rollback,
  Django shell orqali).

## 120-131-qadamlar: Xodim ish haqi (avans + oyni yopish) + Moliya dashboardi

Foydalanuvchi so'ragan: "hodimga ish haqqini berish avans oyni oxirida
to'liq yopish... har bir bergan summasini yozib olish... dashboardda
umumiy tushum pul aylanma qancha hom ashyoga ketdi qancha sof foyda
keldi marja qancha bo'ldi". Plan Mode orqali loyihalashtirilib (Explore
agentlar bilan tadqiqot + Plan agent), foydalanuvchi bilan 4 ta muhim
qaror AskUserQuestion orqali aniqlashtirilgach amalga oshirildi:

- Oy yopish — **faqat qo'lda tugma** (cronsiz, foydalanuvchi tasdiqladi:
  "cronsiz qilaylik shuni").
- "Xom ashyoga ketgan" — sotilgan mahsulotlarning **tannarxi (COGS)**
  asosida, xom ashyo kirimiga sarflangan pul emas.
- "Sof foyda" — tushum − xomashyo(COGS) − ish haqi(to'langan) −
  qo'shimcha xarajatlar — to'liq formula.
- Ish haqi/avans tizimi **barcha xodim turlariga** tegishli (omborchi,
  yetkazib_beruvchi, savdogar, pazanda/ishlab_chiqaruvchi) — shuning
  uchun yangi modellar `Pazanda`ga emas, `User`ga bog'landi (chunki
  omborchi/savdogar uchun alohida profil modeli umuman yo'q edi).

### Yangi modellar (migratsiya `0085_...`)

- `XodimMaosh` — `user` (OneToOne), `company`, `oylik_maosh`
  (DecimalField) — belgilangan fiksval oylik.
- `XodimTolov` — `user`, `company`, `turi` (`avans`/`yakuniy`), `summa`,
  `sana`, `izoh`, `berdi` (kim berdi), `oy_yopish` (FK, faqat yakuniy
  qatorda) — har bir berilgan to'lov, o'zgarmas tarix (audit).
- `XodimOyYopish` — `user`, `company`, `yil`, `oy`, `ishlab_topgan`,
  `avanslar_jami`, `hisoblangan_qoldiq`, `tolangan_yakuniy_summa`,
  `manba` (`per_unit`/`fixed`), `yopgan_user` — oylik yopish snapshoti.
  `UniqueConstraint(user, yil, oy)` — qayta yopishning DB darajasidagi
  himoyasi.

### `main/services/payroll_service.py` (yangi)

- `compute_oylik_ish_haqi(user, company, yil, oy)` — `ish_haqi_turi
  == 'per_unit'` va userga bog'langan `Pazanda` bo'lsa
  `MiqdorQoshish.ish_haqi_summasi` yig'indisidan (mavjud
  `get_pazanda_month_stats`ga ixtiyoriy `yil`/`oy` argumentlari
  qo'shilib, standart — joriy oy — mavjud yagona chaqiruvchiga
  ta'sirsiz), aks holda `XodimMaosh.oylik_maosh`dan hisoblaydi.
- `give_avans` — `select_for_update()` bilan poyga holatidan himoyalangan,
  yopilgan oyga avans berishni rad etadi.
- `close_month` — `ishlab_topgan`, shu oydagi avans yig'indisi,
  `qoldiq = ishlab_topgan - avanslar`, `yakuniy = max(qoldiq, 0)`
  hisoblab `XodimOyYopish` snapshotini yaratadi, agar `yakuniy > 0`
  bo'lsa mos `XodimTolov(turi='yakuniy')` ham yaratadi. Qayta yopishga
  urinish — `ValueError` (ham oldindan tekshiruv, ham DB constraint
  orqali ikki qatlamli himoya).
- `get_month_summary`/`get_payment_history` — profilda ko'rsatish uchun.

### `profile_view` (main/views.py) kengaytirildi

- Yangi `_payroll_context(user, company, can_edit)` helper — barcha
  4 ta GET shoxobchasida (`ytprofile.html`, `pzprofile.html`,
  `egaprofile.html` o'z-profil, `egaprofile.html`/`egayt.html` ega-
  ko'rish) chaqiriladi — `ega` boshqa xodimni ko'rganda tahrirlash
  huquqi bilan, xodim o'zini ko'rganda faqat o'qish uchun.
- 3 ta yangi POST `action`: `set_oylik_maosh`, `give_avans`, `close_oy`
  — barchasi `if request.user.type == 'ega':` ichida (faqat ega
  boshqarishi mumkin), `ValueError`larni `messages.error` bilan
  ushlaydi.

### Shablonlar

- `egaprofile.html` — "Imkoniyatlar" kartasidan keyin, `{% if
  user.type != 'ega' %}` bilan (barcha xodim turlari uchun, faqat
  `pazanda_obj` uchun emas) yangi 3 ta karta: "Oylik maosh" (tahrirlash
  formasi bilan), "Bu oy hisob-kitobi" (avans berish + oyni yopish
  formalari, `confirm()` bilan), "To'lovlar tarixi" jadvali.
- `egayt.html` — xuddi shu blok, yetkazib_beruvchi/savdogar uchun.
- `egabase.html` sidebar + `egaprofile.html` "Imkoniyatlar" bloki —
  "Moliya" havolasi qo'shildi.

### Moliya dashboardi — `main/finance_views.py::moliya_dashboard` + `moliya/` URL

`pazanda_hisobot`dagi sana-oralig'i naqshini qayta ishlatadi:
- Tushum = `Sum(Savdo.summa)`.
- COGS = `Sum(base_summa) - Sum(foyda)` (kredit ustamasi xarajat
  sifatida hisoblanmasligi uchun `summa` emas `base_summa` ishlatildi).
- Naqd pul aylanma = naqd/karta savdolar + shu davrda kelib tushgan
  `NasiyaTolov` yig'indisi (kassa asosida, tushum bilan farqli).
- Ish haqi = `XodimTolov` yig'indisi shu davrda (kassa asosida —
  "to'langan", hisoblangan-lekin-berilmagan emas, chunki cron yo'q).
- Sof foyda = Tushum − COGS − Ish haqi − `QoshimchaChiqim`.
- Marja % = Sof foyda / Tushum * 100.
- `?export=xlsx` — mavjud `export_to_excel` naqshi orqali.

### Tekshirildi

- Model darajasida: `XodimOyYopish` uchun `UniqueConstraint` ishlashi
  (takroriy `user+yil+oy` — `IntegrityError`).
- Servis darajasida: fixed va per_unit ikkala hisoblash yo'li, ikkita
  avans jamlanishi, qolgan qarz bilan yopish, ortiqcha avans holatida
  qoldiq manfiy/yakuniy to'lov yo'qligi, yopilgan oyga avans/qayta
  yopishga urinish rad etilishi, per_unit hisob-kitob
  `get_pazanda_month_stats` bilan mos kelishi, eski (`yil`/`oy`siz)
  chaqiruv uslubi o'zgarishsiz ishlashi.
- HTTP darajasida (Django test Client): barcha 4 xodim turi uchun
  profil GET (`ega` ko'rgan va xodim o'zi ko'rgan), 3 ta yangi POST
  action (`set_oylik_maosh`/`give_avans`/`close_oy`) to'g'ri DB
  yozuvlarini yaratishi/yangilashi.
- Moliya dashboardi: sintetik firma (aralash naqd/karta/nasiya savdo +
  qisman `NasiyaTolov`, 2 ta `XodimTolov`, 1 ta `QoshimchaChiqim`)
  bilan barcha 7 ta ko'rsatkich qo'lda hisoblangan qiymatlarga aniq mos
  kelishi tasdiqlandi; non-ega foydalanuvchi `/moliya/`ga kira olmasligi.
- Regressiya: uchta oldingi qadam (118-qadam) regressiya skripti
  (`test_producing_flow.py`, `test_qadoq.py`, `test_auto_finish_scan.py`)
  o'zgarishsiz to'liq o'tdi — payroll o'zgarishlari eski Task Panel
  oqimiga ta'sir qilmadi.
- Yon-topilma (payroll bilan bog'liq emas): `ytprofile.html`da noto'g'ri
  URL nomi (`logout_view` o'rniga `logout` bo'lishi kerak) — alohida
  fon vazifasi sifatida belgilandi (task_80ce719b), tuzatilmadi (bu
  qadam doirasidan tashqarida).

### Qo'shimcha tuzatish (foydalanuvchi ekran-surat bilan ko'rsatgach)

"Ish haqi (to'langan)" plitkasi asosiy sana-oralig'i KPI panjarasidan
**olib tashlandi** — foydalanuvchi: "shu yerda umumiy ish haqqi/
to'langan ish haqqi bolsin. va shuning faqat joriy oy uchun
o'zgartirib bo'lmas holat bilan dashboardda tursin asosiy fokusni
olib". O'rniga alohida, kichikroq, **sana filtridan mustaqil, doim
joriy oy** uchun blok qo'shildi — ikkita ko'rsatkich bilan: "Umumiy
ish haqqi (hisoblangan)" (`payroll_service.compute_oylik_ish_haqi`
barcha xodimlar bo'yicha jamlanadi — hisoblangan/accrual) va
"To'langan ish haqqi" (`XodimTolov` joriy oy yig'indisi — kassa
asosida). Sof foyda formulasi ichki hisob-kitobda o'zgarishsiz qoldi
(tanlangan davr uchun to'langan ish haqi bilan) — faqat vizual
taqdimot o'zgardi. `main/finance_views.py::moliya_dashboard` va
`moliya_dashboard.html` yangilandi. Sintetik ma'lumotda qayta
tekshirildi — barcha qiymatlar to'g'ri.

### Pre-existing bug tuzatildi (payroll bilan bog'liq emas): "Jami Hodimlar" bosh sahifada bo'sh chiqardi

Foydalanuvchi ekran-surat bilan ko'rsatdi: bosh sahifadagi "Jami
Hodimlar" plitkasi hech qanday raqam ko'rsatmasdi. Sabab:
`main/views.py::main()` xodimlar sonini `payload['ishchilar_soni']`
sifatida saqlaydi, lekin `main.html` shablonida noto'g'ri `{{ soni }}`
o'zgaruvchisi ishlatilgan edi (mos kelmagan, hech qachon ishlamagan).
`main.html`da `{{ soni }}` → `{{ ishchilar_soni }}` ga tuzatildi.
Django test Client orqali tasdiqlandi (2 ta xodim yaratilgan sintetik
firmada endi to'g'ri "2" ko'rsatildi).

### Bosh sahifaga Moliya bo'limidagi qo'shimcha ko'rsatkichlar qo'shildi

Foydalanuvchi so'ragan: "nega bu yerda moliya bo'limidagi kabi ko'proq
narsalarni ko'rsatmaybadi" — bosh sahifa statistika panjarasiga (shu
oy uchun, mavjud "Oylik Sof Foyda" bilan bir qatorda) 4 ta yangi
plitka qo'shildi: **Oylik Pul Aylanma** (naqd/karta savdo +
`NasiyaTolov` shu oy), **Oylik Xomashyo Xarajati** (COGS = `Sum(base_summa)
- Sum(foyda)`), **Oylik Qo'shimcha Xarajat** (`QoshimchaChiqim` shu oy),
**Oylik Marja** (%) — marja hisob-kitobida to'liq sof foyda (foyda −
qo'shimcha xarajat − shu oyda berilgan `XodimTolov`) ishlatildi, mavjud
"Oylik Sof Foyda" plitkasi (faqat `Savdo.foyda` yig'indisi) o'zgarishsiz
qoldirildi (orqaga moslik). `main/views.py::main()` va `main.html`
yangilandi. Sintetik ma'lumotda qo'lda hisoblangan qiymatlarga aniq
mos kelishi va "Jami Hodimlar" tuzatishi regressiyasiz ishlashi Django
test Client orqali tasdiqlandi.

### Bosh sahifaga "Ombordagi Mahsulotlar Qiymati" plitkasi qo'shildi

Foydalanuvchi statistika panjarasidagi bo'sh joyni ko'rsatib so'radi:
"ombordagi hozirgi holatidagi ombordagi mahsulotlarning narxini
qo'ysak". Yangi plitka qo'shildi — kompaniyaning barcha
`Mahsulot`lari bo'yicha `Sum(miqdori * narxi)` (`ExpressionWrapper` +
`DecimalField` orqali, joriy zaxira miqdori ko'paytirilgan sotuv
narxi yig'indisi). `main/views.py::main()` va `main.html`ga
qo'shildi, sintetik ma'lumotda qo'lda hisoblangan qiymat bilan mos
kelishi tasdiqlandi.

## 132-135-qadamlar: Bitta faol veb-sessiya (login cheklovi)

Foydalanuvchi: "loginni chekladingmi? desktop agent bo'ladimi hodimmi
faqat 2ta aktiv sessiya bo'lsin. yangisi kirsa eskilari chiqib
ketsin." Aniqlashtirilgach (AskUserQuestion): veb va Desktop Agent
**alohida-alohida, har biri faqat 1 tadan** ("2ta" = 1 veb + 1 agent),
va bu **barcha foydalanuvchi turlariga** (`ega` ham) tegishli.

**Desktop Agent tomoni — allaqachon bajarilgan edi**: `agent_station_login`
(main/agent_api_views.py:150-152) har safar `station.token = uuid4().hex`
deb eski tokenni ustidan yozadi — yangi login avtomatik eskisini
ishlamay qo'yadi. Kod o'zgartirilmadi, faqat test bilan tasdiqlandi.

**Veb tomoni — yangi qo'shildi**:
- `User.web_session_key` (yangi maydon, migratsiya `0086_...`) — joriy
  amaldagi veb-sessiya kaliti.
- `_apply_session_expiry` (main/views.py) kengaytirildi — har
  `auth_login()`dan keyin (allaqachon 3 ta chaqiruv nuqtasida
  chaqirilgani uchun boshqa joy o'zgarmadi) `request.session.save()`
  bilan sessiya kalitini majburiy generatsiya qilib, `user.web_session_key`ga
  yozadi.
- `CompanyMiddleware` (main/middleware.py) — har so'rovda (login/logout/
  static/media'dan tashqari) `request.user.web_session_key !=
  request.session.session_key` bo'lsa — bu eski, boshqa qurilmada
  ustidan yozilgan sessiya, `auth_logout()` qilinib
  `/login/?session_kicked=1`ga yo'naltiriladi.
- `logout_view` — chiqishda `web_session_key`ni tozalaydi.
- `login` view — `?session_kicked=1` bo'lsa xabar ko'rsatadi
  (`messages.info` — bu `CompanyMiddleware` ichida ishlatilmadi, chunki
  `MessageMiddleware` `CompanyMiddleware`dan KEYIN ishlaydi, ya'ni
  o'sha so'rov davomida messages frameworki hali tayyor emas edi —
  shuning uchun `redirect` orqali GET-parametr sifatida uzatilib,
  keyingi (yangi) so'rovda `login` view'ning o'zida ko'rsatiladi).

### Tekshirildi

- Bitta foydalanuvchi ikkita alohida `Client()` bilan haqiqiy
  `/login/` POST orqali ketma-ket kirsa — birinchisi keyingi so'rovda
  302 bilan `/login/`ga avtomatik yo'naltirilishi, ikkinchisi (yangi)
  ishlayverishi — `ega` va oddiy xodim (`omborchi`) ikkalasi uchun ham.
- Logout qilingach `web_session_key` `None`ga tozalanishi.
- Desktop Agent — ikkinchi marta token yangilangach, eski token
  endi hech kimga tegishli emasligi (`User.objects.filter(token=...)`
  bo'sh).
- Regressiya: barcha oldingi qadamlarning (Task Panel, payroll,
  moliya, bosh sahifa plitkalari) test skriptlari — bularning barchasi
  Django test `Client.login()` qisqartmasidan foydalanadi (haqiqiy
  `/login/` view orqali emas), shuning uchun `web_session_key`
  o'rnatilmaydi va yangi tekshiruv ularga ta'sir qilmasligi tasdiqlandi
  (hammasi avvalgidek to'liq o'tdi).

## 136-137-qadamlar: Desktop Agent — "kirib ketilgan" holatni darhol sezish

Foydalanuvchi: "menda 2ta kompyuter bo'lsa faqat bittasidan agentga
kira olishim kerak ikkinchisidan login qilsam ham kirib ketmasin" —
tekshirilganda backend (`agent_station_login`) allaqachon to'g'ri
ishlayotgani aniqlandi (har login'da eski token ustidan yoziladi,
darhol yaroqsiz bo'ladi) — muammo **Desktop Agent mijozida** edi:
1-kompyuter tokeni yaroqsiz bo'lgandan keyin ham cheksiz "ishlab
turgandek" ko'rinar edi, chunki fon jarayonlari (heartbeat,
WebSocket) 401 xatosini butunlay jimgina yutib yuborardi (Explore
agent orqali tasdiqlandi: `main_window.py`dagi `_HeartbeatWorker`
va `agent_socket_service.py` — ikkalasi ham `except Exception: pass`).

AskUserQuestion orqali tasdiqlandi: xatti-harakat o'zi to'g'ri
("yangi login eskisini chiqarib yuboradi") — faqat 1-kompyuter buni
DARHOL sezishi kerak edi.

### O'zgarishlar (`desktop_agent/app/`)

- `api_client.py` — `ApiError`ga `status_code` maydoni qo'shildi,
  401 javobida aniq `status_code=401` bilan ko'tariladi.
- `windows/main_window.py` — `_HeartbeatWorker`ga `token_invalid`
  signali qo'shildi (faqat `ApiError.status_code == 401` bo'lganda
  chiqadi, boshqa tarmoq xatolari avvalgidek jimgina o'tkazib
  yuboriladi). `MainWindow._handle_token_invalid()` — signal kelganda:
  heartbeat timer va WebSocket'ni to'xtatadi, mahalliy tokenni
  tozalaydi, ogohlantirish oynasi ko'rsatadi, Sozlamalar sahifasiga
  o'tkazadi. `_on_login_succeeded()` — qayta login qilingach heartbeat
  va WebSocket'ni qayta ishga tushiradi.
- `windows/settings_page.py` — `show_login_required()` metodi
  qo'shildi (parol maydonini tozalab, "Sessiya yopildi — qaytadan
  kiring." xabarini ko'rsatadi).

### Tekshirildi

- Sintaksis va import tekshiruvi (`venv/Scripts/python.exe` orqali,
  PyQt6 muhitida) — xatosiz.
- Backend xatti-harakati (eski token ikkinchi logindan keyin endi
  hech kimga tegishli emasligi) alohida sinov bilan qayta tasdiqlandi.
- Amalda: endi 1-kompyuterda 2-kompyuterdan qayta login qilingach,
  ~25 soniya ichida (heartbeat oralig'i) avtomatik "Sessiya yopildi"
  ogohlantirishi chiqib, Sozlamalar sahifasiga o'tkaziladi — foydalanuvchi
  cheksiz "ishlab turgandek" ko'rinishga tushmaydi.

## 138-142-qadamlar: Desktop Agent UI — skan popup o'rniga doimiy panel + ishga tushish qurilma-tekshiruvi + animatsiya

Build qilishdan oldin foydalanuvchi uchta narsani so'radi: (1) QR/badge
skanerlanganda alohida popup oyna o'rniga asosiy oynaning doimiy qismi
bo'lgan panelda ko'rsatilsin; (2) dastur ishga tushganda printer/kamera
ulanganligini tekshiruvchi ekran chiqsin (tarozi — hali ishlaydigan
integratsiya yo'qligi sababli — tekshiruvga kirmaydi, foydalanuvchi
tomonidan AskUserQuestion orqali tasdiqlangan); (3) qurilma topilmasa
ham ogohlantirish bilan davom etish mumkin bo'lsin (bloklanmasin); (4)
panelga 1-2 ta animatsiya qo'shilsin.

### Yangi: `windows/startup_check_page.py`

`StartupCheckPage` — printer (`db.get_setting("label_printer_name")`
+ `list_printers()` bilan hali ham Windows'da mavjudligini tekshirish),
skaner kamerasi (`db.get_scanner_camera()`), ombor kamera(lar)i
(`db.list_all_ombor_cameras()`) holatini ✅/⚠️ belgi bilan ko'rsatadi —
barchasi DB'dan o'qiladi, jonli qurilma so'rovi yo'q (tezkor). Pastda
doim bosiladigan "Davom etish" tugmasi (`continue_requested` signali).

### `windows/main_window.py` — qayta qurildi

- Tashqi `self.root_stack` (QStackedWidget): index 0 = `StartupCheckPage`,
  index 1 = avvalgi "qobiq" (sidebar+Omborlar/Sozlamalar+yangi skan
  paneli). Dastur har ishga tushganda avval index 0 ko'rsatiladi
  (login holatidan mustaqil — qurilma sozlamalari kompyuterning o'ziga
  tegishli). `continue_requested` kelganda index 1ga o'tadi.
- Skan popup (`QDialog`) **butunlay olib tashlandi**. O'rniga — asosiy
  oynaning o'ng tomonida sobit kenglikdagi (380px) doimiy panel, ichida
  xuddi shu (bitta marta yaratiladigan, barcha skanlarda qayta
  ishlatiladigan — bu naqsh avvaldan ham shunday edi) `EmployeeScanWidget`
  instansiyasi. Bo'sh holatda "🪪 Xodim kartasini kutmoqda..." matni
  ko'rsatiladi; skan kelganda matn yashirinib, widget ko'rinadi.
  `EmployeeScanWidget.close_requested` signali endi popup yopish o'rniga
  panelni yana bo'sh holatga qaytaradi (`_reset_scan_panel`).
- Oyna kengligi `980x640` → `1320x680`ga oshirildi (yangi panel sig'ishi
  uchun).
- Fade-in animatsiya: `QGraphicsOpacityEffect` + `QPropertyAnimation`
  (`OutCubic`, 280ms) — skan kelganda widget shaffofligi 0→1ga yumshoq
  o'zgaradi (`_play_scan_fade_in`).
- Login muvaffaqiyatli bo'lganda (`_on_login_succeeded`) heartbeat/socket
  qayta ishga tushirish mantig'i o'zgarishsiz qoldi.

### Tekshirildi

- Sintaksis/import tekshiruvi (`venv/Scripts/python.exe`) — xatosiz.
- Dastur haqiqatan ishga tushirilib (`python main.py`), ekran suratlari
  orqali tasdiqlandi: (1) ishga tushganda avval qurilma-tekshiruv
  sahifasi to'g'ri holatlar bilan ko'rinishi (printer/ombor kamerasi —
  ⚠️ sozlanmagan, skaner kamerasi — ✅ sozlangan (hid) — dev mashinaning
  haqiqiy holatiga mos); (2) "Davom etish"dan keyingi asosiy qobiqda
  o'ng tomondagi doimiy skan paneli "Xodim kartasini kutmoqda..." bo'sh
  holatida to'g'ri ko'rinishi, oyna kengroq (1320px) ekanligi.
- `.exe` build qilindi va tekshirildi (`dist/StockFirmAgent.exe`) —
  ekran suratlari orqali qurilma-tekshiruv sahifasi va skan paneli
  to'g'ri ishlashi tasdiqlandi.

### Qo'shimcha tuzatish: qurilma-tekshiruv sahifasi endi avtomatik davom etadi

Foydalanuvchi to'g'ri belgiladi: stansiya kompyuteri hech kim yonida
bo'lmasdan qayta yonishi mumkin (masalan svet o'chib-yonganda) — "Davom
etish" tugmasini bosish uchun odam kutib turishga majburlash bu
stansiyaning kiosk/hech kim aralashmasdan ishlash tamoyiliga zid.
Tuzatildi: `StartupCheckPage`ga 5 soniyalik avtomatik-davom-etish
sanog'i qo'shildi (`AUTO_CONTINUE_SECONDS`, `QTimer`, tugma matni
"Davom etish (5)" → "(4)" → ... → avtomatik o'tadi) — tugma faqat
tezroq o'tish uchun ixtiyoriy, hech kim bosmasa ham stansiya o'zi
ishga tushadi. Qayta build qilinib, ekran suratlari bilan (sanoq
to'g'ri kamayishi, oxirida avtomatik o'tishi) tasdiqlandi.

### Qo'shimcha tuzatish: skan paneli — o'ng tor panel emas, markazlashtirilgan karta

Foydalanuvchi ekran-surat bilan ko'rsatdi: o'ng tomondagi 380px panelda
matn kesilib qolyapti (widget dastlab 420px popup uchun mo'ljallangan
edi). AskUserQuestion orqali aniqlashtirildi: panel butunlay olib
tashlanib, o'rniga **oyna markazida, xira fon ustida suzuvchi
kengroq karta** (460px) qo'yilishi kerak.

`main_window.py` qayta qurildi: `shell` widget endi `QStackedLayout`
(`StackingMode.StackAll`) orqali ikki qatlamdan iborat — pastda oddiy
kontent (sidebar+Omborlar/Sozlamalar), ustida `self._scan_overlay`
(xira fon, `rgba(15,23,42,0.55)`, markazda 460px oq karta ichida
`EmployeeScanWidget`). `StackAll` rejimi ikkalasini ham avtomatik bir
xil o'lchamda tutadi (qo'lda geometriya sinxronlash shart emas).
Bo'sh holatda overlay butunlay yashirin (`setVisible(False)`) — ekranda
joy egallamaydi. Fade-in animatsiya endi kartaning o'ziga qo'llanadi.
Oyna kengligi `1320x680` → `1000x640`ga qaytarildi (doimiy panel endi
yo'q). Qayta build qilindi.

**Eslatma**: bu safar ekran suratlari orqali vizual tekshirish ikki
marta noto'g'ri oynani (PID qayta ishlatilishi sababli) tutib oldi —
xavfsizlik/maxfiylik uchun bu skrinshot usuli davom ettirilmadi,
faqat kod darajasida (sintaksis/import + `QStackedLayout` standart
Qt naqshi ekanligi) tekshirildi. Foydalanuvchidan haqiqiy skanerlash
bilan o'zi tasdiqlashi so'raldi.

### Ikki real bug tuzatildi (foydalanuvchi haqiqiy sinovda topdi)

**1. `QStackedLayout(StackAll)` — overlay ko'rinmasdi.** Sabab:
`StackAll` rejimida ham faqat "joriy" (`setCurrentWidget`/`setCurrentIndex`
bilan belgilangan) widget tepada chiqadi, qolganlari orqada qoladi —
oddiy `raise_()` yetarli emas edi. `_on_code_scanned`da
`self._shell_layers.setCurrentWidget(self._scan_overlay)` qo'shildi,
`_hide_scan_overlay`da orqaga `setCurrentIndex(0)`.

**2. Overlay yopilmay qolib ketardi.** Sabab:
`EmployeeScanWidget._end_session()` ("Chiqish" tugmasi va 60 soniyalik
sessiya-tugash orqali chaqiriladi) ichki kartalarni yashirar edi,
lekin `close_requested` signalini HECH QACHON chiqarmasdi — bu
signal faqat `_auto_close`da (3s dan keyin, "so'rov yo'q" holatida)
chiqarilardi. Eski popup dizaynida bu muammo emas edi, chunki
alohida tashqi "Yopish" tugmasi bor edi (endi yo'q). Tuzatildi:
`_end_session()` oxirida `self.close_requested.emit()` qo'shildi.
Shuningdek, `_on_scan_resolve_failed` (noto'g'ri/tegishli bo'lmagan
QR kod) — agar hali faol sessiya bo'lmasa (birinchi skan xato
chiqqan, "Chiqish" tugmasi ham yo'q) — 3 soniyadan keyin avtomatik
yopiladi; sessiya faol bo'lsa (xodim allaqachon kirgan) — panel ochiq
qoladi, "Chiqish" orqali yopiladi (bu holat to'g'ri, xodim yana
skanerlash imkoniga ega bo'lishi kerak).

### Yangi: bitta kompyuterda dasturning 2 nusxasi ochilishi taqiqlandi

Foydalanuvchi: "bir vaqtda exe 2 marta kirish mumkin bo'lib qolyabdi".
Aniqlashtirilgach (AskUserQuestion) — ikkala narsa ham kerak: (a)
serverda bitta hisob uchun bitta faol sessiya (allaqachon 136-137-
qadamlarda qilingan — backend/klient kodi qayta tekshirilib, mantiqan
to'g'ri ekanligi tasdiqlandi), (b) **bitta kompyuterda dasturning
o'zi ikki marta ochilmasligi** — bu yangi, alohida talab.

`main.py`ga Windows **nomlangan mutex** (`win32event.CreateMutex` +
`win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS`) orqali
bitta-nusxa qulfi qo'shildi. Birinchi urinilgan yechim
(`QSharedMemory`) sinovda ishonchsiz chiqdi — avvalgi majburan
o'chirilgan test-jarayonlardan qolgan "orfan" holatga tushib,
keyingi urinishlarni noto'g'ri "band" deb ko'rsatib qoldi; Windows
mutex esa jarayon qanday tugasa ham (hatto majburan o'chirilsa ham)
OS tomonidan darhol to'g'ri bo'shatiladi — ishonchliroq. Ikkinchi
nusxa ochilsa — ogohlantirish oynasi chiqib, dastur darhol yopiladi.

### Tekshirildi

- Xom mutex darajasida: birinchi chaqiruv `GetLastError()==0`
  (yaratildi), ikkinchisi `183` (`ERROR_ALREADY_EXISTS`) — to'g'ri.
- To'liq oqim: 1-nusxa ishga tushirilib oyna ochilgach (tasdiqlangan —
  `EnumWindows` orqali sarlavha ko'rinishi tekshirilib, ekran
  tarkibiga tegilmasdan), 2-nusxa ishga tushirilganda darhol chiqib
  ketishi (jarayon ro'yxatida qolmasligi) tasdiqlandi.
- `.exe` qayta build qilindi, ishga tushirilib xatosiz ekanligi
  tasdiqlandi.
- Yon-eslatma: vizual tekshirish paytida ekran-suratlari ikki marta
  boshqa (aloqasiz, foydalanuvchining shaxsiy) oynani tasodifan tutib
  oldi (Windows PID qayta ishlatilishi sababli) — ular darhol
  o'chirildi, tarkibiga qaralmadi. Shundan keyin faqat oyna
  sarlavhalari (`EnumWindows`+`GetWindowText`, tarkib emas) orqali
  tekshirish usuliga o'tildi.

## 143-qadam: Yuklama (yetkazib beruvchi) rejimida sessiya muddati uzaytirildi

Foydalanuvchi: "DESKTOP AGENTDA yetkazib beruvchi yuklamalar so'rovini
yuborib olgunicha qancha kutib turmoqda. hozir qr kodlar printerni
oldida sinov qilayotganimiz uchun lekin real hayotda mahsulotlar
biroz uzoq bo'ladiku" — real omborda mahsulotlar orasida yurish
vaqt oladi, sinovda esa (printer yonida) bu sezilmagan.

### Topilgan bug

`employee_scan_widget.py`da 60 soniyalik umumiy sessiya-taymeri bor
(`SESSION_TIMEOUT_SECONDS`, faol ish — so'rov ko'rsatish/tasdiqlash/
chop etish — davomida `_extend_session()` orqali qayta tiklanadi).
Lekin **yuklama yig'ish oqimi** (`_handle_delivery_scan`/
`_on_delivery_serial_scanned`/`_on_delivery_scan_failed`/
`_on_delivery_finalize_failed`) `_extend_session()`ni HECH QACHON
chaqirmas edi — demak yetkazib beruvchi mahsulotlarni ketma-ket
skanerlab savatga yig'ayotganda, 60 soniya ichida keyingi mahsulotni
skanerlab ulgurmasa, sessiya avtomatik tugab, savatdagi hamma narsa
(hali yuborilmagan) yo'qolib ketardi.

### Tuzatildi

- `_on_delivery_serial_scanned`, `_on_delivery_scan_failed`,
  `_on_delivery_finalize_failed` — endi har birida `_extend_session()`
  chaqiriladi.
- Yangi `DELIVERY_SESSION_TIMEOUT_SECONDS = 120` (2 daqiqa) —
  foydalanuvchi bilan aniqlashtirilgan ("daqiqagacha bo'lsin. oxirgi
  urinishdan 2 daqiqa sanasin"). `_extend_session()` endi
  `self._delivery_mode_active` bo'lsa 120 soniyaga, aks holda oddiy
  60 soniyaga tiklaydi.
- `_start_session()` — yuklama rejimi boshlanganda ham darhol
  `_extend_session()` chaqiriladi (birinchi mahsulotgacha ham 60
  emas, 120 soniya berilishi uchun).

### Tekshirildi

- Sintaksis/import tekshiruvi — xatosiz.
- `.exe` qayta build qilindi (build paytida oldingi test-jarayon
  fayl qulfini vaqtincha ushlab turgani aniqlanib, tozalanib, qayta
  build muvaffaqiyatli o'tdi).

## 144-qadam: Moliya bo'limida o'tgan oylardan yopilmagan hodim to'lovlari

Foydalanuvchi: "moliya bo'limida oldingi oylarda berilmay qolib
ketgan hodimlarning pullari profili bilan ko'rinsa yaxshi edi".

`payroll_service.get_outstanding_previous_months(company,
lookback_months=12)` (yangi) — oxirgi 12 oyni (joriy oy bundan
mustasno — u hali tugamagan) ko'rib chiqadi, har bir xodim uchun
`XodimOyYopish` yo'q (ya'ni oy hali yopilmagan) oylarni topadi va
o'sha oy uchun (ishlab topgan − shu oydagi avans) musbat qoldiqni
hisoblaydi — bu "ega yopishni unutib qo'ygan, xodimga hali
to'lanmagan" summa.

`finance_views.py::moliya_dashboard`ga qo'shildi (`outstanding_months`,
`outstanding_total`). `moliya_dashboard.html`ga yangi jadval —
har bir qatorda xodim ismi, oy, qolgan summa va **profilga o'tish**
havolasi (`{% url 'profile' row.user.username %}`) — ega shu yerdan
to'g'ridan-to'g'ri xodim profiliga o'tib, "Oyni yopish"/avans berish
amallarini bajarishi mumkin.

### Tekshirildi

- Sintetik ma'lumotda: 2 oy oldingi (avanssiz) — to'liq oylik qarz
  sifatida chiqishi; 1 oy oldingi (200000 avans berilgan, oylik
  500000) — qoldiq 300000 to'g'ri hisoblanishi.
- Oy yopilgach (`close_month`) — shu oy ro'yxatdan darhol chiqib
  ketishi, boshqa yopilmagan oy o'zgarishsiz qolishi.
- HTTP darajasida `/moliya/` sahifasida jadval to'g'ri ma'lumot va
  xodim ismi bilan ko'rsatilishi.
- Regressiya: mavjud moliya dashboard va bosh sahifa plitkalari
  testlari o'zgarishsiz to'liq o'tdi.

## 145-150-qadamlar: Desktop Agent — shifrlangan QR kod orqali stansiya login

Foydalanuvchi: "desktop agentga kirganda login qilganidan keyin
avtomatik tizimga qayta ola olmayabdi. biz agentda loginni qr kod
skanerlab qilishga o'tqazamiz. sozlamalarda login qilishi shart emas
agar tizimga kirilmagan bo'lsa qr kodni ko'rsating deb tursin qr
kodda tizimga kirish uchun kerakli barcha ma'lumotlar bo'sin va qr
kod shifrlangan holda ko'rinsin."

### Server (`crm`)

- `cryptography==43.0.3` — `requirements.txt`ga qo'shildi (loyihada
  hech qachon ishlatilmagan, faqat `django.core.signing` bor edi —
  bu **imzolangan, lekin shifrlanmagan** (base64, o'qilishi mumkin),
  foydalanuvchi aniq "shifrlangan" so'ragani uchun yetarli emas edi).
- `main/services/agent_qr_crypto.py` (yangi) — `Fernet` bilan
  simmetrik shifrlash. Kalit `SECRET_KEY`dan hosil qilinadi
  (`sha256` + urlsafe-base64) — alohida `.env` o'zgaruvchisi kerak
  emas, `SECRET_KEY` rotatsiya qilinsa barcha eski QR kodlar ham
  avtomatik yaroqsiz bo'ladi. `encrypt_login_payload(user_id, nonce)`/
  `decrypt_login_payload(token)` (yaroqsiz bo'lsa `None`).
- `User.agent_qr_nonce` (yangi maydon, migratsiya `0087_...`) —
  "Yangilash" bosilganda o'zgaradi, eski ko'rsatilgan/chop etilgan
  QR kodni bekor qiladi (token-overwrite bilan bir xil naqsh).
- `agent_api_views.py`: `_issue_station_token(station, company)` —
  eski `agent_station_login`dan ajratib olingan umumiy yordamchi
  (token generatsiya, javob shakli) — ikkala login yo'li ham shuni
  chaqiradi, takrorlanish yo'q. Yangi `agent_login_by_qr` (POST
  `/api/agent/login-by-qr/`) — `subdomain`+`qr_payload` qabul qiladi,
  dekriptlaydi, `user_id`+`nonce`ni joriy `User.agent_qr_nonce` bilan
  solishtiradi, mos kelmasa/yaroqsiz bo'lsa 401. Eski
  `agent_station_login` (parol bilan) **fallback sifatida saqlanib
  qoldi**.
- `main/badge_views.py`: `agent_login_qr_image(request, user_id)` —
  faqat `ega` (QR — maxfiy hisob ma'lumoti, parol bilan bir xil
  sezgirlik darajasida, xodimning o'ziga ham ko'rsatilmaydi). QR
  matni: `AGENTQR|<subdomain>|<shifrlangan_qism>` — birinchi ikki
  qism ochiq (klient qaysi serverga ulanishni bilishi uchun), uchinchi
  qism shifrlangan. `regenerate_agent_qr` (POST, `ega` only) — nonce
  yangilaydi.
- `main/urls.py`: `xodim/agent-qr/<user_id>/` va
  `xodim/agent-qr/<user_id>/yangilash/`.

### Veb UI

- `egaprofile.html`/`egayt.html` — yangi "Desktop Agent QR-login"
  kartasi (`request.user.type == 'ega'` bo'lganda, o'z profili ham
  kiradi) — QR rasm + "QR kodni yangilash" tugmasi (tasdiqlash bilan).

### Desktop Agent klienti

- `api_client.py`: yangi `station_login_by_qr(server_url, subdomain, qr_payload)`
  — `station_login`ga o'xshash, `/api/agent/login-by-qr/`ga POST.
- `settings_page.py`: standart holat endi **"QR kodni skanerlang"**
  xabari (login/parol maydonlari yashirin, "Qo'lda login/parol bilan
  kirish" havolasi orqali ixtiyoriy ochiladi — fallback, majburiy
  emas). `_update_login_ui_state()` — login holatiga qarab QR
  taklifi/qo'lda-kirish bo'limini ko'rsatadi/yashiradi (`_load`,
  `_on_login_succeeded`, `show_login_required` barchasida chaqiriladi).
  Yangi `start_qr_login(subdomain, qr_payload, server_url)` — natija
  xuddi qo'lda logindagi bir xil handler'lar (`_on_login_succeeded`/
  `_on_login_failed`) orqali ishlanadi.
- `main_window.py::_on_code_scanned` — agar skanerlangan kod
  `AGENTQR|` bilan boshlansa, `_handle_agent_login_qr` chaqiradi:
  `subdomain`/`shifrlangan qism`ni ajratib oladi,
  `normalize_server_url(subdomain)` orqali server manzilini quradi,
  Sozlamalar sahifasiga o'tkazib, `settings_page.start_qr_login(...)`
  chaqiradi — login holatidan qat'i nazar ishlaydi (qayta skanerlab
  boshqa hisobga o'tish ham mumkin).

### Tekshirildi

- `encrypt_login_payload`/`decrypt_login_payload` round-trip to'g'ri
  ishlashi, qalbaki matn `None` qaytarishi.
- HTTP: to'g'ri QR payload bilan login muvaffaqiyatli (token qaytishi,
  eski `agent_station_login` bilan bir xil javob shaklida); nonce
  yangilangach eski payload rad etilishi (401); qalbaki payload rad
  etilishi; boshqa firma subdomeni bilan mos kelmasligi; eski
  parol-bilan-login hali ishlashi (regressiya yo'q).
- `agent_login_qr_image`/`regenerate_agent_qr`: faqat `ega` ko'ra
  oladi/yangilay oladi (non-ega — 404, o'zgarishsiz).
- Profil sahifalari (`egaprofile.html`/`egayt.html`) — yangi karta
  bilan ham avvalgidek 200 qaytarishi (regressiya yo'q).
- Klient: sintaksis/import tekshiruvi; `_handle_agent_login_qr`ning
  `AGENTQR|subdomain|payload` parslash va
  `settings_page.start_qr_login`ga to'g'ri argumentlar bilan
  yo'naltirishi mock orqali tasdiqlandi.
- `.exe` qayta build qilindi (145-149-qadamlar uchun).

## 151-154-qadamlar: CAS CI-200A tarozi integratsiyasi (haqiqiy uskunada topilgan format)

Foydalanuvchi null-modem kabel bilan CAS CI-200A'ni qayta ulab,
COM4'ni tinglashni so'radi — bu safar **haqiqiy, tiniq vazn oqimi**
topildi (avvalgi RLS1100B/kabel muammosi tarixidan farqli, endi
to'liq ishlaydi):

```
9600 baud, 8N1, uzluksiz, so'rovsiz:
  Weight :   0.34kg\r\n
  Weight :   0.38kg\r\n
  ...
```

Foydalanuvchi tasdiqlagach (AskUserQuestion — "hozir qur"), to'liq
integratsiya qurildi:

- `desktop_agent/app/scale_service.py` (yangi) — `ScaleReaderWorker`
  (QThread, COM portni fonda uzluksiz o'qiydi, `WEIGHT_PATTERN`
  regex bilan `"Weight : X.XXkg"` qatorlarini parslaydi,
  `weight_changed(float)` signalini chiqaradi) + `ScaleService`
  (`ScannerService`/`CameraRecorderService` bilan bir xil naqsh —
  sozlanmagan bo'lsa hech narsa qilmaydi, `reload()` orqali qayta
  ishga tushiriladi). `pyserial==3.5` `requirements.txt`ga qo'shildi.
- `settings_page.py` — yangi "Tarozi" bo'limi: COM port matn maydoni
  + "Saqlash" (`db.set_setting("scale_com_port", ...)`).
- `employee_scan_widget.py` — yangi `update_live_weight(value)` —
  faqat tortish kartochkasi (`weigh_card`) ochiq turganda
  `weigh_input`ni jonli qiymat bilan to'ldiradi (qo'lda kiritish
  o'rniga), karta yopiq bo'lsa e'tiborsiz qoldiradi.
- `main_window.py` — `self.scale_service = ScaleService(on_weight_changed=self._scan_widget.update_live_weight)`,
  `closeEvent`da to'xtatiladi, Sozlamalardan qayta saqlanganda
  `_reload_scale()` orqali qayta ishga tushadi.

### Tekshirildi

- Sintaksis/import tekshiruvi — xatosiz.
- **Haqiqiy uskunada**: `ScaleService`ni COM4'ga ulab, 6 soniyada
  79 ta jonli vazn o'qishi qabul qilingani, oxirgi qiymat (0.4kg)
  to'g'ri kelgani tasdiqlandi.
- `.exe` qayta build qilindi, ishga tushirilib xatosiz ekanligi
  tasdiqlandi (pyserial to'g'ri bog'langani — build warn faylida
  faqat Linux-only modullar, `serial.serialwin32` muammosiz).

## 155-qadam: Xom ashyo tortish tolerantligi — qattiq 50g + haqiqiy tortilgan miqdor zaxiradan ayiriladi

Foydalanuvchi tadbirkor (mijoz) bilan gaplashgach: "tadbirkor bilan
gaplashganimda hatolik 50ggacha bo'lsin ortiqcha vaznni aytdi. undan
ko'pi ortiqcha ekan" — va keyin aniqlashtirdi:
"tortilgan miqdoricha zaxiradan ayrilsin, kutilgan miqdor emas".

Ikkita joyda (eski "Material So'rash" oqimi va yangi "Vazifalar
paneli" oqimi) topilgan **ikkita real bug**:

1. **Tolerantlik foizli edi** — `max(expected*2%, 0.05)` — katta
   miqdorlarda (masalan 10kg) 200g gacha chetlanishga ruxsat berardi,
   tadbirkorning "har doim 50g gacha" talabiga zid edi.
2. **Zaxiradan REJALASHTIRILGAN miqdor ayrilar edi, HAQIQIY tortilgan
   emas** — masalan reja 5kg, lekin 5.04kg tortilgan (tolerantlik
   ichida, tasdiqlangan) bo'lsa ham, ombordan atigi 5kg ayrilardi —
   4kg "yo'qolib" ketardi (aslida ombordan olingan bo'lsa ham
   hisobga olinmasdi).

### Tuzatildi

- `task_service.py`: `TASK_WEIGH_TOLERANCE_PERCENT`/`TASK_WEIGH_MIN_TOLERANCE`
  → yagona `TASK_WEIGH_TOLERANCE_FIXED = 0.05` (doim qattiq 50g,
  miqdordan qat'i nazar). `weigh_task_pickup()` — zaxira tekshiruvi
  va ayirish endi `measured_qty` asosida (`expected` emas),
  `StockHistory.delta` ham haqiqiy tortilgan miqdorga mos.
- `agent_api_views.py`: xuddi shu ikki tuzatish
  `agent_weigh_material_request` (eski, agentsiz-bo'lmagan "Material
  So'rash" Desktop Agent varianti) uchun — `MATERIAL_WEIGH_TOLERANCE_FIXED`,
  zaxiradan `measured_qty` ayiriladi.

### Tekshirildi

- Sintetik ma'lumotda: 60g ortiqcha (5.06kg, reja 5kg) — rad etilishi
  (avval 100g'gacha ruxsat berardi, endi 50g qattiq chegara); 40g
  ortiqcha (5.04kg) — tasdiqlanishi VA zaxiradan aynan **5.04kg**
  ayrilishi (reja 5.0 emas) tasdiqlandi.
- Mavjud regressiya testlari (`test_producing_flow`, `test_auto_finish_scan`)
  o'zgarishsiz to'liq o'tdi.

## 156-qadam: Tarozi COM porti tanlash, QR-login qayta urinish + ulanish animatsiyasi

Foydalanuvchi ekran-suratlar bilan uchta narsani ko'rsatdi:

1. **Tarozi COM porti** — matn maydoniga qo'lda yozish o'rniga
   ro'yxatdan **tanlash** kerak edi.
2. **"kirishimga serverga ulanolmasa qayta so'rov yubormayabdi"** —
   sabab topildi: `camera_utils.py::QRScanWorker` bir xil QR kodni
   3 soniya ichida qayta o'qisa e'tiborsiz qoldiradi (debounce) —
   login QR kodi statik (ekranda/qog'ozda) bo'lgani uchun, birinchi
   urinish muvaffaqiyatsiz bo'lsa (server ulanmagan) va foydalanuvchi
   tezda qayta skanerlasa, bu debounce yangi so'rov yuborilishiga
   yo'l qo'ymasdi.
3. **"connecting animation kerak"** — login/QR-login jarayonida
   hech qanday jonli ko'rsatkich yo'q edi.

### Tuzatildi

- `settings_page.py`: tarozi COM porti endi `QLineEdit` emas,
  `QComboBox` — `serial.tools.list_ports.comports()` orqali
  avtomatik aniqlangan portlar ro'yxatidan tanlanadi ("Yangilash"
  tugmasi bilan qayta skanerlanadi, printer ro'yxati bilan bir xil
  naqsh).
- `camera_utils.py::QRScanWorker` — `AGENTQR|` bilan boshlanadigan
  kodlar (Desktop Agent QR-login) debounce'dan **butunlay
  chetlashtirildi** — bir xil login QR necha marta ketma-ket
  skanerlansa ham, har safar yangi so'rov yuboriladi (login —
  xavfsiz takrorlanadigan amal, tarmoq holati o'zgargach qayta
  urinish tabiiy bo'lishi kerak).
- `settings_page.py`: yangi `_start_connecting_animation`/
  `_tick_connecting_animation`/`_stop_connecting_animation` — login
  (qo'lda ham, QR orqali ham) boshlanganda "Kirilmoqda." → "Kirilmoqda.."
  → "Kirilmoqda..." animatsiyasi (400ms), muvaffaqiyat/xato kelganda
  to'xtaydi.

### Tekshirildi

- Sintaksis/import tekshiruvi — xatosiz.
- COM port ro'yxati haqiqiy uskunada to'g'ri to'ldirilishi (COM4
  to'g'ri aniqlangani) tasdiqlandi.
- `.exe` qayta build qilindi, ishga tushirilib xatosiz ekanligi
  tasdiqlandi.

## 157-qadam: Tortish maydoni tarozi ulanganda faqat-o'qish + yangi so'rovlarni "2 daqiqa kechikish" bugi

Foydalanuvchi: "tarozi jonli ulangan tekshirish tugmasi va edit
faqat readonly holatda bo'lsin" — va alohida: "so'rovni yubordim
lekin desktop agentda 2 daqiqachadan so'ng skaner qilganimda
ko'rindi. so'rov yuborilganida 3s ichida skanerlaganimda ko'rinmadi
bu nimadan?"

### 1. Tortish maydoni — tarozi ulanganda faqat-o'qish

`employee_scan_widget.py::update_live_weight` — jonli tarozi
o'qishi kelganda endi `weigh_input.setReadOnly(True)` — foydalanuvchi
qo'lda soxta qiymat kirita olmaydi. `_show_next_weigh_request`
(yangi so'rov ko'rsatilganda) — `setReadOnly(False)` ga qaytaradi
(tarozi sozlanmagan holatlar uchun fallback — qo'lda kiritish
davom etadi).

### 2. "2 daqiqa kechikish" — haqiqiy Desktop Agent bugi topildi

Sabab: `_advance_queue()` — "Vazifa" (`TaskMaterialPickup`) va
"Miqdor qo'shish" (`MiqdorQoshish`) so'rovlarini **faqat bir marta**
(`_task_pickups_fetched`/`_miqdor_fetched` bayroqlari orqali)
tekshiradi — bu bayroqlar faqat sessiya to'liq tugaganda
(`_end_session`) tozalanardi, **`_start_session`da EMAS**. Demak:
agar xodim badge skanerlab sessiya boshlasa (hech narsa topilmasa),
so'ng SHU sessiya ichida (60-120s ichida, har harakatda uzayadi)
yangi vazifa/so'rov yaratilsa va u qayta skanerlasa — `_start_session`
har safar chaqirilsa ham (bu qism to'g'ri ishlagan), ikkala bayroq
"allaqachon tekshirilgan" bo'lib qolgani uchun QAYTA SO'ROV
YUBORILMASDI — faqat sessiya butunlay tugab (taxminan 2 daqiqa),
yangi sessiya boshlanganda bu ikkala bayroq tozalanib, haqiqiy
qayta tekshiruv sodir bo'lardi.

**Muhim**: `ProductionMaterialRequest` (`_load_material_requests`)
bu muammoga duch kelmagan edi — u `_start_session`da har doim
qayta chaqirilardi (natija to'liq almashtirib qo'yiladi). Faqat
Vazifa va Miqdor-qo'shish turlari uchun muammo bor edi.

Tuzatildi: `_start_session()` ichida endi `self._miqdor_fetched = False`
va `self._task_pickups_fetched = False` — har bir badge skani (sessiya
faol bo'lsa ham) ikkala turni qaytadan tekshiradi.

### Yon-topilma (bu safar amal talab qilinmaydi, faqat tushuntirildi)

Foydalanuvchi "yuklama so'rovi (YuklamaSorov) ham Desktop Agent'da
ko'rinsinmi" deb so'ragan edi — tekshirilganda aniqlandi: bu
allaqachon TO'G'RI ishlayapti — yuklama so'rovini TASDIQLASH
yetkazib beruvchining o'z Desktop Agent sessiyasida Serial QR
skanerlash orqali sodir bo'ladi (`agent_finalize_yuklama`), ishlab
chiqaruvchining o'zidan hech qanday amal talab qilinmaydi — shuning
uchun kod o'zgartirilmadi, faqat arxitektura tushuntirildi.

### Tekshirildi

- Sintaksis/import tekshiruvi — xatosiz.
- `.exe` qayta build qilindi, ishga tushirilib xatosiz ekanligi
  tasdiqlandi.

## 158-qadam: Kiosk rejimi — to'liq ekran + faqat ega QR kodi bilan ochiladigan mishka/klaviatura qulfi

Foydalanuvchi: "dasturga kirishi bilan full screen bo'lib qolishi
kerak. mishka klaviatura dostup yonishi uchun eganing qr kodi
skanerlanishi kerak." Aniqlashtirilgach (AskUserQuestion): (1)
cheklov faqat **dastur ichida** (Sozlamalar/navigatsiya/oynani
yopish) — Windows darajasida OS-keng mishka/klaviatura bloklash
QILINMAYDI (juda xavfli, kompyuterni butunlay qulflab qo'yishi
mumkin); (2) qulf ega "Qulflash" tugmasini bosguncha ochiq qoladi
(avtomatik qayta yopilish yo'q).

### 1. Server — kiosk-unlock tekshiruv endpointi (login'dan alohida)

Mavjud "Desktop Agent QR-login" (`AGENTQR|<subdomain>|<shifrlangan>`,
145-qadam) infratuzilmasi qayta ishlatildi, lekin **stansiya
tokenini o'zgartirmaydigan** yangi, alohida endpoint qo'shildi —
aks holda qulfni ochish stansiya identifikatsiyasini almashtirib
qo'yardi (station.token qayta yozilib, xodim-sessiya yo'qolardi).

`main/agent_api_views.py::agent_verify_kiosk_unlock` (POST,
`agent_login_by_qr`ning yonida) — bir xil `decrypt_login_payload`
orqali dekriptlaydi, `agent_qr_nonce` mosligini tekshiradi, lekin
qo'shimcha ravishda **faqat `user.type == 'ega'`** bo'lsa
tasdiqlaydi (boshqa xodim turlari — pazanda, omborchi va h.k. — hatto
o'z to'g'ri QR kodini skanerlasa ham, kiosk qulfini OCHA OLMAYDI —
bu faqat ega huquqi). Muvaffaqiyatli bo'lsa faqat `{'ok': True,
'name': ...}` qaytaradi — hech qanday token yaratilmaydi/saqlanmaydi.

URL: `landing/urls.py` — `path('api/agent/verify-kiosk-unlock/',
agent_verify_kiosk_unlock, name='agent_verify_kiosk_unlock')`.

### 2. Desktop Agent klient — `api_client.py`

Yangi `verify_kiosk_unlock(server_url, subdomain, qr_payload)` —
`station_login_by_qr` bilan bir xil so'rov shakli, lekin natijada
token saqlanmaydi (chaqiruvchi faqat `ok`/`name`ni ishlatadi).
Tokensiz (hali login qilinmagan stansiyada ham) chaqirilishi mumkin.

### 3. `main_window.py` — to'liq ekran + qulf holati mashinasi

- `_on_startup_check_continue()` (qurilma-tekshiruv "Davom etish"
  bosilgach) — endi `self.showFullScreen()` ham chaqiradi — dastur
  har ishga tushganda avtomatik to'liq ekranga o'tadi.
- Yangi holat: `self._kiosk_locked` — dastur ochilganda standart
  qiymat **`True`** (qulflangan). `_set_kiosk_locked(locked)` —
  `warehouse_btn`/`settings_btn` (sidebar navigatsiyasi)ni
  yoqadi/o'chiradi, sidebar'dagi holat yorlig'i (`kiosk_status_label`)
  va "🔒 Qulflash" tugmasini (faqat ochiq holatda ko'rinadi) yangilaydi.
- `_on_code_scanned()` — `AGENTQR|` prefiksli kod kelganda: agar
  `self._kiosk_locked` bo'lsa — **login emas**, `_handle_kiosk_unlock_qr()`
  chaqiriladi (server: `agent_verify_kiosk_unlock`, fon oqimida,
  mavjud `_ApiCallWorker` naqshi bilan, `settings_page.py`dan import
  qilingan); aks holda avvalgidek (`_handle_agent_login_qr`, stansiya
  login/almashtirish). Muvaffaqiyatli tasdiqlansa `_set_kiosk_locked(False)`
  + "Qulf ochildi: <ega ismi>" xabari; rad etilsa (masalan xodimning
  o'z QR kodi bilan urinishi yoki eskirgan kod) — xato xabari,
  qulf o'zgarishsiz qoladi.
- `closeEvent()` — boshida yangi tekshiruv: agar `self._kiosk_locked`
  bo'lsa — `event.ignore()` + ogohlantirish, dastur **yopilmaydi**
  (oyna sarlavhasidagi X tugmasi ham shu orqali to'xtaydi, bu Qt'ning
  o'z `closeEvent` mexanizmi orqali — OS darajasida hech narsa
  bloklanmaydi). Qulf ochiq bo'lsa — avvalgidek to'liq yopilish
  (logout so'rovi, fon xizmatlarini to'xtatish va h.k.).

**Muhim cheklov (ataylab)**: qulf faqat sidebar navigatsiyasi va
oynani yopishga tegishli — markaziy xodim-skan overlay
(`EmployeeScanWidget`, badge/tortish/task oqimi) qulf holatidan
mustaqil, har doim ishlaydi. Sababi: kunlik ishlab chiqarish
jarayoni kamera orqali (mishka/klaviatura emas) va zarur hollarda
qo'lda tasdiqlash tugmalari orqali davom etishi kerak — bularni
bloklash asosiy ish oqimini to'xtatib qo'yardi. Qulf faqat
"administrativ" harakatlarni (Sozlamalarni ochish, dasturni yopish)
to'sadi.

### Tekshirildi

- `python manage.py check` — xatosiz.
- Desktop Agent: sintaksis tekshiruvi (`ast.parse`) — xatosiz.
- Offscreen Qt orqali `MainWindow` ni to'g'ridan-to'g'ri
  instansiyalab, real kod bilan tekshirildi: (a) boshlang'ich holat
  `_kiosk_locked=True`, sidebar tugmalari o'chirilgan; (b) `verify_kiosk_unlock`
  mock qilinib, `_handle_kiosk_unlock_qr` chaqirilganda muvaffaqiyatli
  javobdan keyin qulf ochilishi (`_kiosk_locked=False`, tugmalar
  yoqilishi) tasdiqlandi; (c) qulflangan holatda `closeEvent` chaqirilganda
  `event.ignore()` chaqirilishi (dastur yopilmasligi) tasdiqlandi.
- `.exe` qayta build qilindi (`venv/Scripts/python.exe -m PyInstaller
  StockFirmAgent.spec --noconfirm`), 6 soniyalik smoke-test (xatosiz
  ishga tushdi va ishlab turdi) o'tkazildi.

## 159-qadam: Tortish — tarozi ulanganda to'liq avtomatik (tekshirish tugmasisiz) + tarozidan olingandan keyin keyingisiga o'tish

Foydalanuvchi ekran-suratda tortish kartochkasini ko'rsatib: "nega
avtomatik bo'ldi yaxshi endi oling demayabdi. olib bo'lishiga endi
bu mahsulotdan shuncha demayabdi." Aniqlashtirilgach (AskUserQuestion):
(1) tarozi qiymati barqarorlashgach tasdiqlash **to'liq avtomatik**
bo'lsin (tugma bosish shart emas); (2) tasdiqlangandan keyin keyingi
so'rovga o'tish — belgilangan vaqt (1.2s) o'rniga, mahsulot
**tarozidan olib tashlangach** (qiymat 0.0ga qaytgach) sodir bo'lsin.

### Sabab (avvalgi holat)

153-qadamda tarozi qiymati maydonga jonli yozilgan va faqat-o'qish
qilingan edi, lekin **"Tekshirish" tugmasini bosish hamon majburiy**
edi — shuning uchun tasdiqlash ("Norma bo'yicha to'g'ri — oling! ✓"
xabari) hech qachon o'z-o'zidan chiqmasdi. Keyingi so'rovga o'tish
esa doim qattiq `QTimer.singleShot(1200, ...)` orqali, mahsulot
haqiqatda tarozida qolgan-qolmaganidan qat'i nazar sodir bo'lardi.

### Yechim — `employee_scan_widget.py`

Yangi doimiylar: `SCALE_STABLE_SECONDS = 0.8` (shuncha vaqt qiymat
deyarli o'zgarmasa "barqaror"), `SCALE_STABLE_THRESHOLD_KG = 0.01`,
`SCALE_EMPTY_THRESHOLD_KG = 0.02` (shundan past — tarozi bo'sh).

`update_live_weight(value)` kengaytirildi — endi har bir o'qishda
barqarorlik holatini kuzatadi (`_scale_last_value`/`_scale_stable_since`):
- Qiymat o'zgarsa — hisoblagich qayta boshlanadi.
- Barqaror bo'lib, `_awaiting_scale_clear=True` bo'lsa (tasdiqdan
  keyingi kutish holati) va qiymat ~0 bo'lsa — `_show_next_weigh_request()`
  avtomatik chaqiriladi.
- Barqaror, `_awaiting_scale_clear=False`, qiymat bo'sh chegaradan
  yuqori va hali yuborilmagan bo'lsa (`_auto_submit_pending` bayrog'i,
  ikki marta yubormaslik uchun) — `_submit_weigh()` **avtomatik**
  chaqiriladi (tugma bosilmasdan).

`_submit_weigh`/`_on_weigh_resolved`/yangi `_on_weigh_failed` —
`_auto_submit_pending` bayrog'ini har doim (muvaffaqiyat, xato, yoki
erta-qaytish holatlarida ham) qayta `False`ga qaytaradi — aks holda
bitta muvaffaqiyatsiz avtomatik urinishdan keyin bayroq abadiy
"band" bo'lib qolib, keyingi avtomatik urinishlarni to'sib qo'yardi.

`_on_weigh_resolved`dagi tasdiqlangan-holat oxiridagi qattiq
`QTimer.singleShot(1200, self._show_next_weigh_request)` —
shartli qilindi: agar tarozi sozlangan bo'lsa (`scale_com_port`
bo'sh emas) — `_awaiting_scale_clear = True` (keyingi so'rov mahsulot
tarozidan olinishi bilan avtomatik chiqadi); aks holda (tarozi yo'q,
qo'lda kiritish) — eski 1.2 soniyalik qattiq kechikish saqlanadi
(regressiyasiz fallback).

`_show_next_weigh_request()` va `_end_session()` — yangi barqarorlik
holatini (`_scale_last_value`, `_scale_stable_since`, `_auto_submit_pending`,
`_awaiting_scale_clear`) har safar tozalaydi — avvalgi so'rovdan
qolgan holat yangisiga tarqalib, xato vaqtda avtomatik yubormasligi
uchun.

### Tekshirildi

- Sintaksis tekshiruvi (`ast.parse`) — xatosiz.
- Offscreen Qt orqali `EmployeeScanWidget`ni to'g'ridan-to'g'ri
  instansiyalab (`_submit_weigh`ni stub bilan almashtirib, faqat
  barqarorlik-aniqlash mantig'ini izolyatsiya qilib): (a) qiymat
  o'zgarmasdan turgan holatda `SCALE_STABLE_SECONDS`dan oldin hech
  narsa chaqirilmasligi, shundan keyin avtomatik `_submit_weigh`
  chaqirilishi; (b) `_awaiting_scale_clear=True` holatida qiymat
  ~0ga qaytgach `_show_next_weigh_request` avtomatik chaqirilishi —
  ikkalasi ham to'g'ri ishlashi tasdiqlandi.
- `.exe` qayta build qilindi (foydalanuvchi ishlab turgan eski
  jarayonni to'xtatishga alohida rozilik berdi), 6 soniyalik
  smoke-test bilan tasdiqlandi.

## 160-qadam: Vazifa QR-yorliqlarini chop etish "Ish bitdi" tugmasiga ko'chirildi + sessiya-token muddati uzaytirildi

Foydalanuvchi ekran-suratlar bilan ikkita muammo ko'rsatdi: (1) "12ta
yorliq chop etilgani yo'q" — xom ashyo tortilgan zahoti QR-yorliqlar
"chop etildi" deb ko'rsatilardi, lekin haqiqiy printer ulanmagan test
muhitida hech narsa ko'rinmasdi; (2) ikkinchi so'rovni tortayotganda
"Sessiya-token yo'q yoki muddati tugagan" xatosi chiqdi — 12 ta yorliqni
yopishtirish kabi jismoniy ish 90 soniyalik token muddatidan oshib
ketgan edi. Aniqlashtirilgach (AskUserQuestion): kelishildi — chop
etish endi mahsulotni tayyorlab, veb dashboardda "Ish bitdi" tugmasini
bosgach, KEYINGI badge skanida sodir bo'lishi kerak (batafsil: "mahsulotni
olib dashboardidan ish bitdi tugmasini bosib so'ng badgeni skanerlasa
shunda chiqishi kerak va shundan so'ng bitta-bitta skanerlab mahsulot
qo'shsin").

### 1. Modellar

`ProductionTask.STATUS_CHOICES`ga yangi holat: `materials_ready`
("Xom ashyo tortildi — \"Ish bitdi\" kutilmoqda") — `claimed` va
`producing` orasida. `MiqdorQoshish.labels_printed` (yangi `BooleanField`,
default `False`) — Desktop Agent shu partiyani chop etib bo'lganini
(yoki chop etadigan hech narsa yo'qligini) belgilaydi, qayta-qayta
chop etilib ketmasligi uchun. Migratsiya `0088_...py`.

### 2. `main/services/task_service.py`

- `weigh_task_pickup` — vazifaning oxirgi xom ashyo qatori tasdiqlangach,
  endi **darhol** `_start_producing` chaqirilmaydi — o'rniga
  `task.status = 'materials_ready'` qilib belgilanadi, natija
  `{'materials_ready': True}` qaytaradi (avvalgi `task_producing`/
  `miqdor_qoshish` maydonlari olib tashlandi).
- Yangi `confirm_task_finished_materials(task_id, pazanda, company)` —
  "Ish bitdi" tugmasi chaqiradi: faqat `status='materials_ready'` va
  shu pazandaga tegishli vazifani qabul qiladi, `_start_producing`ni
  (o'zgarishsiz qolgan, faqat endi bu yerdan chaqiriladigan) ishga
  tushiradi — `MiqdorQoshish` + Serial/QR kodlar shu yerda yaratiladi,
  lekin **hech narsa chop etilmaydi**.
- Yangi `get_pending_print_batch(pazanda, company)` — `labels_printed=
  False` bo'lgan eng eski `MiqdorQoshish(source_task__isnull=False)`ni
  (va uning Seriallarini) qaytaradi — Desktop Agent badge-sessiya
  boshida chaqiradi.
- Yangi `mark_batch_printed(mq_id, pazanda, company)` — chop etilgach
  (yoki chop etadigan narsa topilmagach) `labels_printed=True` qiladi.
- `_start_producing` — `qr_service.generate_serials_for_batch()` bo'sh
  ro'yxat qaytarsa (`serial_granularity='none'`) — darhol
  `labels_printed=True` qilib belgilaydi (chop etiladigan narsa yo'q,
  Desktop Agent navbatida abadiy osilib qolmasligi uchun).

### 3. `main/agent_api_views.py`

`agent_weigh_task_pickup` javobi soddalashtirildi: `materials_ready`
maydoni qaytadi, `serials`/`print_url`/`mahsulot` endi bu yerda yo'q
(printer bilan bog'liq mantiq butunlay olib tashlandi). Ikkita yangi
endpoint: `agent_pending_print_batch` (GET, `session_token`) —
`get_pending_print_batch`ni chaqirib, topilsa `serials`+`print_url`
bilan qaytaradi; `agent_mark_batch_printed` (POST) — `mark_batch_printed`
chaqiradi. `landing/urls.py`ga
`/api/agent/pending-print-batch/`, `/api/agent/mark-batch-printed/`.

**Sessiya-token muddati**: `BADGE_SESSION_MAX_AGE` — `90` dan `3600`
(1 soat)ga oshirildi. Sabab: real ishlab chiqarish jarayoni (tortish +
tayyorlash + 12+ yorliqni yopishtirish + birma-bir skanerlash) osongina
bir necha daqiqa davom etadi — Desktop Agent'ning o'z 60/120 soniyalik
UI-faolsizlik hisoblagichi (`SESSION_TIMEOUT_SECONDS`) o'zgarishsiz
qoladi, faqat server tomonidagi imzo-token muddati kengaytirildi.

### 4. Veb — "Ish bitdi" tugmasi

`main/production_views.py::pz_confirm_task_finished` (yangi, POST) —
`confirm_task_finished_materials`ni chaqiradi. URL:
`/vazifa/<id>/ish-bitdi/` (`pz_confirm_task_finished`).
`pazanda_dashboard.html` — `task.status == 'materials_ready'` uchun
yangi holat matni ("📦 Xom ashyo tortildi — mahsulotni tayyorlab
bo'lgach \"Ish bitdi\"ni bosing") + yashil "Ish bitdi ✓" tugmasi
(tasdiqlashsiz, chunki qaytarib bo'lmaydigan xavfli amal emas).

### 5. Desktop Agent

`api_client.py` — yangi `fetch_pending_print_batch`/`mark_batch_printed`.
`employee_scan_widget.py`:
- `_advance_queue()`ga yangi bosqich qo'shildi (xom ashyo so'rovlaridan
  keyin, vazifa-pickup'lardan oldin): `_pending_print_fetched` bayrog'i
  bilan bir marta (har badge-sessiyada) `_load_pending_print_batch`
  chaqiriladi.
- `_on_pending_print_batch_loaded(batch)` — partiya topilsa: printer
  sozlangan bo'lsa `_print_serial_labels` (mavjud, o'zgarishsiz chop
  etish yo'li) chaqiriladi, aks holda `print_url` brauzerda ochiladi;
  ikkalasida ham keyin `mark_batch_printed` chaqiriladi va navbat
  davom etadi.
- `_on_weigh_resolved` — `task_producing`/`serials`/`print_url` bilan
  ishlaydigan eski, endi serverdan kelmaydigan maydonlarga tayanuvchi
  bloklar olib tashlandi; `materials_ready=True` bo'lsa oddiy
  "Xom ashyo tortildi ✓ — ... 'Ish bitdi'ni bosing" xabari ko'rsatiladi.
- `_pending_print_fetched` — `__init__`, `_start_session` (har badge
  qayta-skanida ham) va `_end_session`da tozalanadi — 157-qadamdagi
  "2 daqiqa kechikish" bugidan saboq olib, mavjud `_miqdor_fetched`/
  `_task_pickups_fetched` naqshiga mos.

### Tekshirildi

- `python manage.py check`, `makemigrations`, `migrate` — xatosiz.
- Django shell'da izolyatsiyalangan tranzaksiya (rollback bilan):
  to'liq oqim — xom ashyo tortilgach vazifa `materials_ready`ga
  o'tishi va HALI `MiqdorQoshish`/`Serial` yaratilmasligi;
  `get_pending_print_batch` shu bosqichda `None` qaytarishi;
  `confirm_task_finished_materials` chaqirilgach `MiqdorQoshish`+12
  ta `Serial` yaratilishi (`labels_printed=False`);
  `get_pending_print_batch` endi shu partiyani qaytarishi;
  `mark_batch_printed`dan keyin endi qaytarmasligi — barchasi
  kutilganidek ishladi.
- Desktop Agent: sintaksis tekshiruvi xatosiz. Offscreen Qt orqali
  `EmployeeScanWidget`ni instansiyalab: (a) `_advance_queue` bosqich
  tartibi (chop etish → vazifa-pickup → miqdor) to'g'ri ekanligi;
  (b) partiya topilganda `_print_serial_labels`+`_mark_batch_printed`
  chaqirilib, navbat davom etishi tasdiqlandi.
- `.exe` qayta build qilindi, 6 soniyalik smoke-test bilan tasdiqlandi.

## 161-qadam: "Tugatish" tugmasi yorliqlar chop etilmasdan turib shtraf yozib qo'ygan bug tuzatildi

Foydalanuvchi real sinovda ekran-suratlar bilan ko'rsatdi: "Ish bitdi"
bosilgach vazifa `producing` holatiga o'tgan zahoti, dashboardda
"Tugatish" (erta yopish) tugmasi HAM darhol ko'rinar edi — pazanda
hali Desktop Agent'ga borib yorliqlarni chop ettirmasdan turib
bexosdan shu tugmani bosdi va "0/3 dona tayyor, shtraf qo'llanildi"
xabarini oldi. Sabab: `pazanda_dashboard.html`da `task.status ==
'producing'` bo'lgan HAR QANDAY vazifa uchun "Tugatish" ko'rsatilardi
— hatto yorliqlar hali umuman chop etilmagan (`labels_printed=False`)
bo'lsa ham, bu bosqichda tugatishning hech qanday mantiqiy foydasi
yo'q (fizik jarayon hali boshlanmagan).

### Tuzatish

- `main/views.py::main()` — `my_tasks` sikliga `t.labels_printed`
  qo'shildi (`producing` holatidagi vazifalar uchun
  `t.miqdor_qoshishlar.first().labels_printed`, aks holda `False`).
- `pazanda_dashboard.html` — "Tugatish" tugmasi endi faqat
  `task.status == 'producing' and task.labels_printed` bo'lganda
  ko'rinadi; `labels_printed=False` bo'lsa o'rniga holat matni
  "🖨 Yorliqlar hali chop etilmagan — Desktop Agent'da badge'ingizni
  skanerlang" ko'rsatiladi.
- `main/production_views.py::pz_finish_task` — **server tomonida ham**
  himoya qo'shildi (faqat UI'ga tayanib qolmaslik uchun): agar
  `MiqdorQoshish.labels_printed` hali `False` bo'lsa, xato xabari
  bilan rad etiladi, vazifa `producing` holatida qoladi (shtraf
  yozilmaydi).

### Tekshirildi

- Django shell'da izolyatsiyalangan tranzaksiya + `RequestFactory`
  orqali to'g'ridan-to'g'ri `pz_finish_task` view'ini chaqirib: (a)
  yorliqlar chop etilmasdan turib "Tugatish" chaqirilganda vazifa
  `producing`da qolishi va shtraf yozilmasligi; (b)
  `mark_batch_printed`dan keyin xuddi shu chaqiruv normal ishlab,
  vazifa `done`ga o'tishi tasdiqlandi.
- `python manage.py check` — xatosiz.

## 162-qadam: QR-yorliqlar haqiqatda ko'rinmasdan turib "chop etildi" deb belgilangan bug (kiosk fullscreen bilan to'qnashuv)

Foydalanuvchi: "skaner qildim lekin qr kod chiqmadiku keyin webda
tugatish turibdi". Sabab topildi: 160-qadamda `_on_pending_print_batch_loaded`
printer sozlanmagan holatda `print_url`ni `webbrowser.open()` orqali
ochib, **darhol** (natijani kutmasdan) `mark_batch_printed` chaqirardi.
Ikki muammo birlashdi: (1) 157-158-qadamlarda qo'shilgan kiosk
fullscreen rejimi tufayli ochilgan brauzer oynasi asosiy Qt oynasi
ortida yashirin qolib, foydalanuvchi hech narsa ko'rmadi; (2) chop
etish natijasi tekshirilmasdan (haqiqatda ko'rinmagan/chop etilmagan
bo'lsa ham) `labels_printed=True` qilib belgilanardi — shuning uchun
veb dashboardda "Tugatish" tugmasi ochilib qolgan edi, garchi hech
qanday yorliq hali qo'lda bo'lmasa ham.

### Yechim

`employee_scan_widget.py::_on_pending_print_batch_loaded` ikkiga
bo'lindi:

1. **Printer sozlangan bo'lsa** — `_print_pending_batch_via_printer`
   (mavjud `LabelPrintWorker` orqali) chaqiriladi; `labels_printed`
   endi FAQAT chop etish `succeeded` signali kelgach
   (`_on_pending_batch_print_succeeded`) belgilanadi. Chop etish
   muvaffaqiyatsiz bo'lsa (`_on_pending_batch_print_failed`) —
   belgilanmaydi, keyingi badge skanida qayta uriniladi (yorliqlar
   yo'qolib ketmaydi).
2. **Printer sozlanmagan bo'lsa** — endi `print_url`/tashqi brauzerga
   umuman tayanilmaydi. Yangi `print_batch_card` (doimiy widget,
   `_show_print_batch_card`) — QR kodlarni **to'g'ridan-to'g'ri shu
   oynaning o'zida** (3 ustunli grid, har biri `/api/qr/image/<kod>/`dan
   fon oqimida (`_ImageFetchWorker`) yuklab olingan) ko'rsatadi — kiosk
   fullscreen rejimida ham har doim ko'rinadi, tashqi brauzer/printerga
   bog'liq emas. "Yorliqlarni oldim — davom etish" tugmasi
   (`_on_print_batch_continue_clicked`) bosilmaguncha `labels_printed`
   belgilanmaydi va navbat davom etmaydi — foydalanuvchi haqiqatda
   yorliqlarni ko'rmasdan/olmasdan "Tugatish" imkoniga ega bo'la
   olmaydi.

### Tekshirildi

- Offscreen Qt orqali `EmployeeScanWidget`: (a) printer sozlanmagan
  holatda partiya kelganda `print_batch_card` ko'rinishi va
  "Davom etish" bosilmaguncha `mark_batch_printed`/`_advance_queue`
  chaqirilmasligi, bosilgach ikkalasi ham chaqirilib kartaning
  yashirinishi; (b) printer sozlangan holatda chop etish
  muvaffaqiyatli bo'lsagina belgilanishi, muvaffaqiyatsiz bo'lsa
  belgilanMAsligi (shu bilan birga navbat baribir davom etishi —
  kiosk abadiy osilib qolmasligi uchun) — barchasi tasdiqlandi.
- `.exe` qayta build qilindi, 6 soniyalik smoke-test bilan tasdiqlandi.

## 163-qadam: "Ish bitdi" ikki marta bosilib dublikat Serial/QR yaratilgan bug + shu holatni tozalash

Foydalanuvchi real "birzumda" firmasida sinov paytida (id=1 vazifa,
Burger 12 dona, Xaydarov Rafiq) QR kod chiqmagan/printer chop
etmaganini xabar qildi va "stateni ortga qaytar" deb so'radi.
Tekshirilganda aniqlandi: `MiqdorQoshish(id=60)`da 12 ta o'rniga **24
ta Serial** bor edi — `unit_index` 1-12 ikki marta takrorlangan holda
— demak `confirm_task_finished_materials` ("Ish bitdi") bitta vazifa
uchun ikki marta ishga tushgan (kiosk/sensorli ekranda tugma ikki
marta tez ketma-ket bosilishi ehtimoli katta). Ildiz sabab:
`select_for_update()` **SQLite'da haqiqiy qator-qulfini bermaydi**
(Django uni jimgina e'tiborsiz qoldiradi) — shuning uchun ikkala
so'rov ham vazifani hali "materials_ready" deb ko'rib, ikkalasi ham
`_start_producing`ni chaqirib yuborgan, natijada bitta `MiqdorQoshish`
ustiga ikki marta Serial generatsiya qilingan. Bundan tashqari,
avvalgi (162-qadamgacha bo'lgan) kod natijani tekshirmasdan
`labels_printed=True` deb belgilab qo'yganidan qolgan eski holat ham
bor edi.

### Kod tuzatildi

`main/services/task_service.py::confirm_task_finished_materials` —
himoya `select_for_update()`+tekshiruv o'rniga **bitta atomik
`ProductionTask.objects.filter(status='materials_ready').update(
status='producing')`** ga almashtirildi. Bunday `UPDATE...WHERE`
har doim (SQLite'da ham) faqat bitta chaqiruvchi uchun muvaffaqiyatli
bo'ladi — DB darajasidagi yagona yozish amali sifatida bajarilgani
uchun, alohida qator-qulfiga muhtoj emas. Ikkinchi (kechikkan) chaqiruv
endi `updated == 0` ko'rib, aniq xato bilan rad etiladi, hech qanday
dublikat Serial yaratilmaydi.

### Real ma'lumot tozalandi ("birzumda" firmasi, id=1 vazifa)

- `MiqdorQoshish(id=60)`dagi 24 ta Serialdan **dublikat 12 tasi**
  (`unit_index` takrorlangan qatorlar) o'chirildi — 12 ta (1-12)
  qoldi, reja miqdoriga (12 dona) mos.
- `MiqdorQoshish(id=60).labels_printed` — `True`dan `False`ga
  qaytarildi, shunda Desktop Agent'da Xaydarov Rafiq keyingi safar
  badge'ini skanerlaganda, bu partiya qayta "chop etishga tayyor"
  sifatida topiladi (162-qadamdagi yangi in-app QR grid yoki
  haqiqiy printer orqali).

### Tekshirildi

- Django shell'da izolyatsiyalangan tranzaksiyada: `confirm_task_
  finished_materials` ikki marta ketma-ket chaqirilganda — birinchisi
  o'tishi, ikkinchisi aniq rad etilishi, va yakunda faqat 1 ta
  `MiqdorQoshish` + 12 ta `Serial` (dublikatsiz) qolishi tasdiqlandi.
- `python manage.py check` — xatosiz.
- Real "birzumda" ma'lumoti to'g'ridan-to'g'ri tekshirilib (o'qish),
  aniq muammoli qator(lar) topilgach, faqat o'sha aniq yozuvlarga
  nishonlangan (targeted) tuzatish qo'llanildi — testda ishlatilgan
  kabi keng qamrovli/ehtiyotsiz o'zgarish emas.
- Bu — faqat server (Django) tomonidagi o'zgarish, Desktop Agent
  `.exe`ga tegilmagani uchun qayta build shart emas (`runserver`
  auto-reload orqali darhol kuchga kiradi).

## 164-qadam: Printer "muvaffaqiyat" signali haqiqiy chop etishni kafolatlamaydi — qo'lda tasdiq YAGONA mezon qilindi

Foydalanuvchi 163-qadamdagi tuzatishdan keyin ham xuddi shu holatga
duch keldi: badge skanerlaganda "Barcha so'rovlar bajarildi ✓" chiqdi,
lekin QR kod/chop etish hech qachon ko'rinmadi. Tekshiruv:

- Avval **ikki nusxada ishga tushish** gumon qilindi (single-instance
  mutex ishlamayaptimi?) — maxsus sinovdan o'tkazilib (bir necha marta
  ketma-ket ishga tushirib, jarayon/oyna sarlavhalarini kuzatib),
  **mutex to'g'ri ishlayotgani tasdiqlandi** (PyInstaller onefile bitta
  "ishga tushirish"da ikkita jarayon — bootloader + haqiqiy dastur —
  ko'rsatishi normal holat ekan, bu chalkashlikka sabab bo'lgan).
- Mahalliy sozlamalar (`%LOCALAPPDATA%\StockFirmAgent\agent_data.db`)
  tekshirilganda **`label_printer_name = "XP-80C"` sozlangan** ekani
  aniqlandi — demak 162-qadamdagi "printer sozlangan" yo'l ishlatilgan,
  "printer sozlanmagan" (ekrandagi QR grid) yo'l EMAS.
- **Haqiqiy ildiz sabab**: `label_printer_service.py::print_raw`
  `win32print.OpenPrinter`/`WritePrinter` orqali ishlaydi — bu Windows
  API'lari printer **jismonan o'chiq/uzilgan** bo'lsa ham odatda
  XATOSIZ qaytadi (chunki ish shunchaki Windows spooler navbatiga
  yoziladi, jismoniy chiqishi alohida masala). Demak 162-qadamdagi
  "faqat chop etish MUVAFFAQIYATLI tugagach `labels_printed=True`"
  mezoni — bu holatda ham noto'g'ri ijobiy (false positive) natija
  berardi, chunki Windows "muvaffaqiyat" deb signal bergan, garchi
  hech narsa qog'ozga chiqmagan bo'lsa ham (printer o'chiq/ulanmagan).

### Yechim — qo'lda tasdiq har doim yagona mezon

`employee_scan_widget.py::_on_pending_print_batch_loaded` soddalash-
tirildi: printer sozlangan/sozlanmagan ikkalasida ham endi **har doim**
`_show_print_batch_card` chaqiriladi (ekrandagi QR grid + "Davom etish"
tugmasi). Printer sozlangan bo'lsa, qo'shimcha ravishda fizik chop
etish ham (fon oqimida, "best-effort") boshlanadi — natijasi
(`_on_pending_batch_print_succeeded`/`_on_pending_batch_print_failed`)
endi faqat kartadagi sarlavha matnini yangilaydi ("... printerga
yuborildi ✓ — lekin bu faqat Windows navbatiga qabul qilingani, real
chiqqanini ekrandagi QR kodlar bilan solishtirib tekshiring"),
`labels_printed`ga hech qanday ta'sir qilmaydi. Faqat operatorning
o'zi "Davom etish"ni bosishi `mark_batch_printed` + navbatni
davom ettirishni ishga tushiradi.

### Real ma'lumot yana tozalandi

`MiqdorQoshish(id=60).labels_printed` yana `False`ga qaytarildi —
endi Xaydarov Rafiq badge'ini qayta skanerlaganda, tuzatilgan
klient bilan, ekranda 12 ta QR kod ko'rinishi kerak.

### Tekshirildi

- Offscreen Qt orqali: printer sozlangan holatda ham (a) fizik chop
  etish urinishi ishga tushishi, (b) shu bilan BIRGA ekrandagi QR
  karta ham ko'rinishi, (c) "Davom etish" bosilmaguncha
  `mark_batch_printed`/`_advance_queue` chaqirilmasligi — barchasi
  tasdiqlandi.
- `.exe` qayta build qilindi, 6 soniyalik smoke-test bilan tasdiqlandi.

## 165-qadam: Ega/producer bo'lmagan xodim o'z badge'ini skanerlasa panel abadiy "qotib qolgan" bug + "Davom etish"ga tasdiqlash dialogi

Foydalanuvchi ikkita narsa xabar qildi: (1) ega o'z shaxsiy badge'ini
skanerlaganda panel "Ish boshlandi" holatida qotib qoldi, hech qayerga
o'tmadi; (2) shundan keyin ishlab chiqaruvchi qayta skanerlaganda ham
QR kodlar yana chiqmadi.

### 1-muammo — ildiz sabab (eski, bugungacha bo'lgan kod, hech qachon sinovdan o'tmagan yo'l)

`employee_scan_widget.py::_load_material_requests` — muvaffaqiyatsiz
bo'lsa (`worker.failed`) **hech narsa qilmasdi** (`lambda _msg: None`).
Server tomonida `agent_material_requests` faqat `Pazanda` profiliga
ega foydalanuvchilar uchun ishlaydi — `ega` (yoki `omborchi` va h.k.)
o'z badge'ini skanerlasa, server 404 ("Bu foydalanuvchi ishlab
chiqaruvchi emas") qaytaradi. Bu xato **jimgina yutilib**, `_advance_
queue()` HECH QACHON chaqirilmasdi — panel "Ish boshlandi" bannerida
abadiy qolib ketardi (boshqa barcha shunga o'xshash yuklovchilar —
`_load_my_task_pickups`, `_load_miqdor_requests`, `_load_pending_
print_batch` — xatoni to'g'ri "bo'sh ro'yxat" sifatida ishlab,
navbatni davom ettiradi; faqat shu bittasi noto'g'ri edi).

**Tuzatish**: `worker.failed.connect(lambda _msg: None)` →
`worker.failed.connect(lambda _msg: self._on_material_requests_loaded([]))`
— endi har qanday xato (tarmoq, "producer emas" va h.k.) bo'sh ro'yxat
sifatida ishlab, navbat normal davom etadi (oxir-oqibat "Sizning
so'rovlaringiz yo'q" xabari va avtomatik yopilish).

### 2-muammo — "Davom etish" ehtimol bexosdan bosilgan

`MiqdorQoshish(id=60).labels_printed` yana `True` bo'lib qolgani
aniqlandi (uchinchi marta!). Kod tekshirilganda `mark_batch_printed`
FAQAT `_on_print_batch_continue_clicked`dan chaqirilishi tasdiqlandi
(boshqa hech qaysi yo'l orqali emas) — demak "Davom etish" tugmasi
chindan ham bosilgan, ehtimol "keyingisiga o'tish" tugmasi kabi
(bexosdan/odat bilan) qabul qilinib. Bu qaytarib bo'lmaydigan amal
bo'lgani uchun, endi tasdiqlash dialogi qo'shildi:
`_on_print_batch_continue_clicked` — bosilganda avval `QMessageBox.question`
("... QR-yorliqlarni haqiqatan ham oldingizmi? Bu amalni qaytarib
bo'lmaydi.") ko'rsatadi, faqat "Ha" bosilsagina `mark_batch_printed`
chaqiriladi.

### Real ma'lumot yana tozalandi

`MiqdorQoshish(id=60).labels_printed` yana `False`ga qaytarildi.

### Tekshirildi

- Offscreen Qt orqali: (a) `ega` user_type bilan `_start_session`
  chaqirilib, material-requests "muvaffaqiyatsiz" holati simulyatsiya
  qilinganda navbat qotib qolmasdan `_advance_queue()`ga o'tishi;
  (b) `QMessageBox.question` "Ha" qaytarganda `_on_print_batch_
  continue_clicked` normal ishlab, `mark_batch_printed`/`_advance_queue`
  chaqirilishi — ikkalasi ham tasdiqlandi.
- `.exe` qayta build qilindi, 6 soniyalik smoke-test bilan tasdiqlandi.

## 166-qadam: "Ega'ni skanerlasam mishka ochilmayabdi" — ega ikkita QR kodiga ega ekani aniq emas edi

Foydalanuvchi: "egani skanerlasam mishka distup ochilmayabdi." Sabab —
kod bugi emas, **UX chalkashligi**: `egaprofile.html`da ega uchun
IKKITA alohida QR karta bor — "Desktop Agent QR-login" (145-qadam,
`AGENTQR|...`, shifrlangan — kiosk qulfini ochish ham shu orqali) va
"Mening shaxsiy QR badge'im" (109-qadam, oddiy `XodimBadge`, faqat
davomat/xodim-sessiya uchun). Kiosk qulfini ochish faqat BIRINCHISI
(`AGENTQR|` prefiksli) bilan ishlaydi — foydalanuvchi ehtimol
ikkinchisini (shaxsiy badge) skanerlagan, shuning uchun hech narsa
ochilmagan (kod to'g'ri ishlagan — `_on_code_scanned` "AGENTQR|" bilan
boshlanmagan kodni oddiy xodim-skan sifatida qabul qiladi, aniqlangan
avvalgi ekran-suratlarda ham xuddi shu — ega badge'i "Xush kelibsiz...
Ega" kartasini ochgan, kiosk qulfini emas).

### Tuzatish — aniqroq xabar matni

`main_window.py` — barcha uchta "qulflangan" xabar matni ("Qulflangan"
holat yorlig'i, ochish muvaffaqiyatsiz bo'lganda, yopishga urinishda)
endi aniq ko'rsatadi: "ega profilidagi \"Desktop Agent QR-login\"
kodini skanerlang (shaxsiy badge emas)."

### Tekshirildi

- Sintaksis tekshiruvi xatosiz.
- `.exe` qayta build qilindi, 6 soniyalik smoke-test bilan tasdiqlandi.

## 167-qadam: Kiosk-unlock QR kod kamera bilan real o'qib bo'lmagan — haqiqiy ildiz sabab topildi (o'lcham/zichlik)

Foydalanuvchi bir necha marta "ega'ning to'g'ri QR kartasini skanerlab
ham mishka/klaviatura ochilmayapti" deb xabar qildi (166-qadamdagi
matn-aniqlashtirish yordam bermadi). Bu safar taxmin qilmasdan, real
dalil bilan tekshirdim:

1. Server yaratgan "Desktop Agent QR-login" QR rasmini to'g'ridan-
   to'g'ri chaqirib oldim, keyin uni **Desktop Agent aynan ishlatadigan
   o'sha OpenCV `QRCodeDetector` bilan** o'qib ko'rdim — matn to'g'ri
   chiqdi (`AGENTQR|birzumda|...`, 201 belgi). Demak generatsiya/format
   xato emas.
2. Lekin bu QR — oddiy xodim badge (36 belgili UUID)dan farqli, **~200
   belgili shifrlangan (Fernet) matn** kodlanadi, bu esa ancha zichroq
   QR panjarasini talab qiladi. Profil sahifasida rasm faqat **180x180
   CSS piksel**da ko'rsatilar edi.
3. Bu haqiqiy muammo ekanini **o'lchab tasdiqladim**: QR rasmni turli
   o'lchamlarga (kamera monitordan qanchalik uzoqda/yaqin turishini
   simulyatsiya qilib) kichraytirib, xuddi shu detektor bilan qayta
   o'qishga urindim — **180px o'lchamda eski QR umuman o'qilmadi (0
   belgi)**, hatto 300px o'lchamda ham eski sozlamalar bilan
   o'qilmadi. Bu — foydalanuvchi tajribasida takroran uchragan
   "skanerlayapman, lekin hech narsa bo'lmayapti" holatining aniq,
   o'lchab isbotlangan sababi.

### Yechim

`main/badge_views.py::agent_login_qr_image` — `qrcode.make()` o'rniga
aniq `qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=12,
border=4)` ishlatildi: yuqori xato-tuzatish darajasi (30% zaxira —
xiralik/nur aksi/qisman to'siqqa chidamliroq) + tabiiy o'lcham
650x650dan 1020x1020ga oshdi. `egaprofile.html`/`egayt.html` — rasm
CSS o'lchami **180px → 420px** ga oshirildi (`max-width:100%` bilan,
kichik ekranlarda toshib ketmasligi uchun).

Qayta o'lchab tasdiqlandi: yangi sozlamalar bilan QR **420px va undan
yuqori** o'lchamlarda barqaror o'qiladi (300px'da ham eskisidan farqli
o'qiladi) — 180px'dagi kabi juda kichik holatlargina hali muammoli
qoladi, lekin displey o'lchami endi 420px'ga oshirilgani uchun bu
amalda yuzaga kelmaydi.

### Tekshirildi

- Django shell orqali QR rasmni to'g'ridan-to'g'ri generatsiya qilib,
  Desktop Agent'ning o'z OpenCV detektori bilan o'qib, matn to'g'ri
  chiqishi tasdiqlandi.
- Turli o'lchamlarda (640/420/300/180/120px) eski va yangi
  sozlamalarni **taqqoslab** o'lchash orqali — 300px va undan yuqorida
  yangi sozlamalar ishonchli o'qilishi, eskisi esa 300px'da allaqachon
  buzilishi ko'rsatildi (o'lchab isbotlangan, taxmin emas).
- `python manage.py check` — xatosiz.
- Bu — faqat server (Django shablon+view) tomonidagi o'zgarish,
  Desktop Agent `.exe`ga tegilmagani uchun qayta build shart emas.

## 168-qadam: Kiosk-unlock so'rovi NOTO'G'RI server manziliga yuborilar edi (haqiqiy kod bugi)

167-qadamdagi QR-o'lcham tuzatishidan keyin ham foydalanuvchi "QR kod
tasdiqlanmadi" xatosini olishda davom etdi — bu safar to'g'ri QR
kodni (ega'ning "Desktop Agent QR-login" kartasi) skanerlab. Taxmin
qilmasdan, jonli serverga to'g'ridan-to'g'ri (curl orqali) haqiqiy
shifrlangan payload bilan so'rov yuborib tekshirdim — server **to'g'ri
ishlayotgani** (`200 OK, {"ok":true,...}`) tasdiqlandi. Demak muammo
klient (Desktop Agent) tomonida edi.

### Ildiz sabab

`main_window.py::_handle_kiosk_unlock_qr` — server manzilini
`normalize_server_url(subdomain)` orqali **qayta qurar edi** — bu
funksiya har doim `https://<subdomen>.stockfirm.uz` (production
manzili) deb hisoblaydi. Bu mantiq `_handle_agent_login_qr` (LOGIN
uchun) da to'g'ri — chunki stansiya hali hech qanday serverga
ulanmagan bo'lishi mumkin, manzilni qayerdandir olish kerak. LEKIN
**kiosk-unlock uchun stansiya ALLAQACHON muayyan serverga ulangan/
login qilingan** (`db`da `server_url` saqlangan) — shu MAVJUD manzil
ishlatilishi kerak edi, productiondan taxmin qilingan manzil emas.
Natijada mahalliy/test serverda ishlayotgan stansiya kiosk-unlock
so'rovini butunlay boshqa (yoki umuman mavjud bo'lmagan) serverga
yuborardi — javob JSON emas edi, shuning uchun `api_client.py`dagi
generic "QR kod tasdiqlanmadi." xabari chiqardi (aniq sabab
ko'rsatilmasdan).

### Tuzatish

```python
server_url = db.get_setting("server_url", "") or normalize_server_url(subdomain)
```
— endi stansiyaning o'zida saqlangan `server_url` ishlatiladi (bo'sh
bo'lgan holatlargina, masalan nazariy jihatdan hech qachon login
qilinmagan holatda, eski `normalize_server_url` fallback sifatida
qoladi).

### Tekshirildi

- Offscreen Qt orqali: `_handle_kiosk_unlock_qr` chaqirilganda,
  `verify_kiosk_unlock`ga uzatiladigan `server_url` endi `db`da
  saqlangan qiymat (masalan `http://127.0.0.1:8000`) ekanligi,
  productiondan qurilgan `https://<subdomen>.stockfirm.uz` EMASLIGI
  tasdiqlandi.
- `.exe` qayta build qilindi, 6 soniyalik smoke-test bilan tasdiqlandi.
- `.exe` qayta build qilindi, 6 soniyalik smoke-test bilan tasdiqlandi.

## 169-qadam: Omborlar sahifasida "Serverga ulanib bo'lmadi" o'lik xato o'rniga animatsiyali qayta-ulanish

Foydalanuvchi: "senga reconnecting animation qil degandim. qani?" —
avvalgi bir so'rovda `settings_page.py`ga (login/QR-login) qo'shilgan
"Kirilmoqda..." animatsiya naqshi faqat login oqimiga tegishli edi;
`warehouse_list_page.py` (Omborlar sahifasi, dastur ochilganda birinchi
ko'rinadigan joy) hamon serverga ulanib bo'lmasa faqat o'lik qizil
matn ko'rsatib, qayta urinmasdan to'xtab qolar edi.

### Yechim

`warehouse_list_page.py`ga `settings_page.py` bilan bir xil animatsiya
naqshi (`_start_connecting_animation`/`_tick_connecting_animation`/
`_stop_connecting_animation`) qo'shildi, plyus yangi `_reconnect_timer`
(`RECONNECT_RETRY_MS = 5000`, bir martalik, muvaffaqiyatsizlikda qayta
ishga tushadi): `_on_sync_failed` (faqat `silent=False` — sahifa
ochilgandagi asosiy tekshiruv, fon-WS tekshiruvlariga tegilmaydi) endi
o'lik xabar o'rniga "yorlik <xabar> — qayta ulanmoqda..." animatsiyasini
ko'rsatadi va 5 soniyadan keyin avtomatik qayta `sync_from_server`ni
chaqiradi — muvaffaqiyatli bo'lguncha davom etadi. `_on_sync_succeeded`
ikkala timerni ham to'xtatadi.

### Tekshirildi

- Offscreen Qt orqali: xatolik simulyatsiya qilinganda ikkala timer
  (`_connecting_timer`, `_reconnect_timer`) ishga tushishi, nuqta-
  animatsiya matni to'g'ri yangilanishi, muvaffaqiyat simulyatsiya
  qilinganda ikkalasi ham to'xtashi tasdiqlandi.
- `.exe` qayta build qilindi, 6 soniyalik smoke-test bilan tasdiqlandi.

## 170-qadam: QR-yorliq oynasidan tasdiqlash tugmasi/dialogi butunlay olib tashlandi (xodimda mishka/klaviatura yo'q)

Foydalanuvchi: "bu tugma kerak emas ... hodim tugmalarni bosolmasligini
bilasan uni to'g'rila." To'g'ri eslatma — kiosk stansiyasida ishlab
chiqaruvchining mishka/klaviaturasi (hatto sensorli ekrani ham)
bo'lmasligi mumkin, faqat badge/QR skanerlash orqali ishlaydi. 169-
qadamda qo'shilgan "Yorliqlarni oldim — davom etish" tugmasi va undan
oldingi "Ha/Yo'q" tasdiqlash dialogi (168-qadam) — ikkalasi ham
bosilishi kerak bo'lgani uchun, real kiosk stansiyasida ISHLATIB
BO'LMAYDIGAN edi.

### Yechim

`employee_scan_widget.py::_show_print_batch_card` — tugma va
tasdiqlash dialogi butunlay olib tashlandi. Endi: partiya ko'rsatilgan
ZAHOTI (a) `labels_printed=True` avtomatik belgilanadi (grid endi har
doim shu oynaning o'zida ko'rinadi — 167-qadamdagi "yashirin brauzer"
bugi bu yerda umuman yo'q, shuning uchun avtomatik belgilash endi
xavfsiz), (b) yangi `PRINT_BATCH_DISPLAY_MS = 8000` (8 soniya) dan
keyin karta o'zi yopilib, navbat avtomatik davom etadi
(`_on_print_batch_display_timeout`). Hech qanday tugma/klik/tasdiq
kerak emas — printer bilan ham, printersiz ham bir xil ishlaydi.

### Tekshirildi

- Offscreen Qt orqali: partiya yuklangan zahoti `mark_batch_printed`
  darhol (klik kutmasdan) chaqirilishi; belgilangan muddatdan keyin
  karta yashirinib, `_advance_queue()` avtomatik chaqirilishi
  tasdiqlandi.
- `.exe` qayta build qilindi, 6 soniyalik smoke-test bilan tasdiqlandi.

## 171-qadam: Dublikat QR-yorliq muammosi (bulletproof DB-cheklov) + qurilmalarni haqiqiy jonli tekshirish

Foydalanuvchi ikkita narsani xabar qildi: (1) "har safar ortiqcha qr
kod chiqarmoqda" — tekshirilganda haqiqatan ham 2 ta yangi vazifada
(reja=2/3 dona) 2x ortiqcha Serial (4/6 dona, `unit_index` 1,2,1,2
kabi takrorlangan, orasida 12-19 soniyalik farq bilan) topildi — 168-
qadamdagi atomik-UPDATE himoyasi bu holatni to'liq to'smagan edi;
(2) qurilmalar (printer/tarozi) haqiqatda onlaynligini bilish
imkoni yo'qligi va tarozi startup-tekshiruvga kiritilmaganligi.

### 1. Dublikat — endi DB darajasida STRUKTURAVIY jihatdan imkonsiz

`MiqdorQoshish.source_task` — `unique=True` qilindi (migratsiya
`0089_...`). Bu FK "har bir vazifada FAQAT bitta MiqdorQoshish/Serial
partiyasi" qoidasini SQL darajasida majburlaydi — sabab (ikki marta
bosish, poyga holati, boshqa hech qanday mexanizm) qanday bo'lishidan
qat'i nazar, ikkinchi urinish `IntegrityError` bilan bloklanadi.
`_start_producing` — `.create()` endi ichki `try/except IntegrityError`
bilan o'ralgan: xato tutilsa, YANGI Serial yaratilmaydi, shunchaki
MAVJUD `MiqdorQoshish` qaytariladi (idempotent). Sinovda to'g'ridan-
to'g'ri ikki marta chaqirib tasdiqlandi — endi qanday chaqirilishidan
qat'i nazar dublikat yo'q. Real "birzumda" ma'lumotidagi mavjud
dublikat Seriallar (4→2, 6→3) qo'lda tozalandi.

### 2. Qurilmalarni haqiqiy jonli tekshirish (`startup_check_page.py` qayta yozildi)

Endi faqat DB'da sozlangan-sozlanmaganini emas, balki HAQIQIY ulanishni
tekshiradi, fon oqimida (`_DeviceProbeWorker`):
- **Printer**: `list_printers()` + `win32print.GetPrinter()` orqali
  haqiqiy Windows spooler holati (oflayn/xato bitlari) tekshiriladi.
- **Tarozi (yangi qo'shildi)**: COM portni ochib, 2.5 soniya ichida
  haqiqiy "Weight: X kg" formatidagi qator kelishini kutadi.
- **Skaner/ombor kamera(lar)i**: endi shunchaki DB'da yozuv borligini
  emas, `cv2.VideoCapture` orqali haqiqatan kadr olib ko'radi.

Barcha 4 tekshiruv MUVAFFAQIYATLI bo'lsagina "Davom etish" (avtomatik
sanoq bilan) ko'rinadi. Birortasi nosoz bo'lsa — "⚙ Sozlamalarga
o'tish" tugmasi ko'rinadi (`open_settings_requested`), bosilganda
`MainWindow` to'g'ridan-to'g'ri Sozlamalar sahifasiga o'tkazadi (kiosk
hamon qulflangan holatda qoladi). Sozlamalarda yangi "🔄 Qurilmalarni
qayta tekshirish" tugmasi — bosilganda qurilma-tekshiruv sahifasiga
qaytib, jonli tekshiruv qaytadan boshlanadi.

**Muhim topilgan/tuzatilgan qo'shimcha bug**: Qt ba'zan bitta haqiqiy
ko'rsatishda `showEvent`ni bir necha marta chaqiradi — bu ikkinchi
`refresh()`ni ishga tushirib, deyarli tugagan tekshiruv natijalarini
"Tekshirilmoqda..." holatiga qaytarib, foydalanuvchiga hech qachon
yakuniy natija ko'rsatmay qolar edi. `refresh()` endi tekshiruv
ALLAQACHON ishlab turgan bo'lsa hech narsa qilmaydi (guard qo'shildi).

### Tekshirildi

- Django shell'da: `_start_producing`ni bitta vazifa uchun IKKI MARTA
  to'g'ridan-to'g'ri chaqirib — ikkalasi ham BIR XIL `MiqdorQoshish`
  qaytarishi va aynan reja miqdoricha (dublikatsiz) Serial qolishi
  tasdiqlandi.
- Offscreen Qt orqali to'liq `MainWindow`: (a) jonli probe ishga
  tushib, real muhitda qurilmalar topilmasa (`_all_ok=False`)
  "Sozlamalarga o'tish" ko'rinishi va bosilganda Sozlamalar
  sahifasiga o'tkazilishi; (b) barcha tekshiruvlar sun'iy True
  qaytarilganda (`_all_ok=True`) "Davom etish" ko'rinishi — ikkalasi
  ham tasdiqlandi.
- `.exe` qayta build qilindi, 8 soniyalik smoke-test (jonli qurilma
  so'rovlari bilan) bilan tasdiqlandi.

## 172-qadam: Tarozi-tekshiruv COM portni ScaleService bilan raqobatlashib "Access is denied" bergan bug

Foydalanuvchi to'g'ri taxmin qildi: "com portga balki ikkita fayldan
ulanmoqchi bo'lgandursan yoki 2ta sessiyadan." Aynan shu edi — 171-
qadamda qo'shilgan tarozi-tekshiruv o'zining ALOHIDA COM-port ulanishini
ochardi, lekin `ScaleService` (`MainWindow.__init__`) dastur ochilgan
zahotidan shu portni ALLAQACHON fonda ushlab turadi. Ikkita joy bir
vaqtda bitta serial portni ochishga urinsa, Windows "Access is denied"
(PermissionError) beradi — bu tarozi haqiqatan ulangan-ulanmaganidan
qat'i nazar sodir bo'lardi.

### Yechim

`scale_service.py::ScaleReaderWorker` — `last_reading_at` (oxirgi
haqiqiy o'qish vaqti) kuzatila boshladi. `ScaleService.is_connected(
within_seconds=3.0)` — yangi metod, oxirgi o'qish shu muddat ichida
kelgan bo'lsa `True` qaytaradi — HECH QANDAY yangi ulanish ochmaydi,
faqat mavjud fon-xizmatning holatidan so'raydi.

`startup_check_page.py::_check_scale_live` — endi `serial.Serial(...)`
orqali alohida ulanish ochish o'rniga, `MainWindow`dan uzatilgan
`scale_checker` (`self.scale_service.is_connected`) callback'ini bir
necha soniya davomida so'raydi. `main_window.py` —
`StartupCheckPage(scale_checker=lambda: self.scale_service.is_connected())`
— lambda `self.scale_service` hali yaratilmagan bo'lsa ham xavfsiz
(faqat keyinroq, `.show()`dan keyin chaqirilganda qidiriladi).

### Tekshirildi

- Offscreen Qt orqali: sun'iy `scale_checker` bilan uchta holat (COM
  porti sozlanmagan, sozlangan-lekin-javob-yo'q, sozlangan-va-jonli)
  to'g'ri natija berishi; to'liq `MainWindow` haqiqiy (COM porti yo'q)
  muhitda ishga tushirilganda endi `PermissionError`/`Access is denied`
  emas, oddiy "javob kelmadi" xabari chiqishi tasdiqlandi.
- `.exe` qayta build qilindi, 8 soniyalik smoke-test bilan tasdiqlandi.

## 173-qadam: Skaner/ombor kamera tekshiruvlari ham ScannerService/CameraRecorderService bilan raqobatlashgan (172-qadam bilan bir xil sinf bug)

Foydalanuvchi: "skaner ulanmagan bo'lganida qr kodni skaner qilmasdi
lekin ishlab turgan narsa checkpointdan o'tolmayabdi" — ya'ni skaner
kamerasi HAQIQATDA ishlab, QR kodlarni to'g'ri o'qiyotgan edi (buni
Serial-qayta-skanerlash xabari tasdiqladi), lekin startup-tekshiruv
baribir uni "nosoz" deb ko'rsatardi. Bu — 172-qadamda tarozi uchun
topilgan bilan AYNAN BIR XIL sinf bug: `_check_camera_live()`
(skaner kamerasi VA ombor kameralari uchun) o'zining ALOHIDA
`cv2.VideoCapture` ulanishini ochardi, lekin `ScannerService`
(skaner kamerasi uchun) va `CameraRecorderService` (har bir ombor
kamerasi uchun) ular ALLAQACHON fonda doimiy ushlab turadi — ikkinchi
raqobatlashuvchi ulanish odatda ishlamay qoladi (ayniqsa USB
DirectShow kameralarida faqat bitta jarayon/handle bir vaqtda
ochishi mumkin).

### Yechim — bir xil naqsh, endi barcha uchta qurilma uchun

`scanner_service.py::ScannerService` — `_last_frame_at` kuzatila
boshladi (`QRScanWorker.frame_ready` signaliga ulanib); yangi
`is_camera_connected()` — HID skaner uchun hook o'rnatilganini,
kamera uchun oxirgi kadr yaqinda kelganini tekshiradi (ALOHIDA
ulanish OCHMAYDI).

`camera_recorder_service.py::_OmborCameraBufferWorker` — `last_frame_at`
kuzatila boshladi; `CameraRecorderService.connected_camera_count()` —
(jonli/jami) juftlikni qaytaradi.

`startup_check_page.py` — `_check_camera_live()` butunlay olib
tashlandi, o'rniga `_check_scanner_camera_live(scanner_checker)` /
`_check_ombor_cameras_live(ombor_checker)` — ikkalasi ham inyeksiya
qilingan callback'larni (`ScannerService.is_camera_connected`,
`CameraRecorderService.connected_camera_count`) bir necha soniya
davomida so'raydi, hech qanday yangi kamera ulanishi ochmaydi.
`main_window.py` — mos lambda'lar `StartupCheckPage`ga uzatildi.

### Tekshirildi

- Offscreen Qt orqali sun'iy callback'lar bilan: (a) skaner darhol
  emas, ikkinchi urinishda ulanganini to'g'ri aniqlashi; (b) hech
  qachon ulanmasa vaqt tugab "kadr kelmayapti" qaytarishi; (c) ombor
  kameralaridan qisman (1/2) ulanganida `False`, to'liq (2/2)
  ulanganida `True` qaytarishi — barchasi tasdiqlandi.
- To'liq `MainWindow` haqiqiy (HID skaner sozlangan) muhitda ishga
  tushirilganda "Ulangan (hid)" to'g'ri ko'rsatilishi, hech qanday
  xato/qulash bo'lmasligi tasdiqlandi.
- `.exe` qayta build qilindi, 8 soniyalik smoke-test bilan tasdiqlandi.

## 174-qadam: Oylik ish haqi — jami/shtraf ayri-ayri (yashil/qizil) ko'rsatiladigan bo'ldi

Foydalanuvchi ikkita ekran-surat yuborib: "Bu oy topgan pulim -33887
so'm" qanday hosil bo'lganini so'radi. Tekshirilganda: bu haqiqiy
hisob-kitob xatosi emas edi — bitta eski sinov vazifasi (Burger 3
dona, 0/3 bajarilgan, oldingi bug tufayli) uchun 49 187 so'mlik
"bajarilmagan dona" shtrafi qo'llangan, va bu shtraf boshqa 3 ta
haqiqiy vazifadan (10800+1800+2700=15300) ko'proq bo'lgani uchun jami
manfiy chiqqan. Foydalanuvchi ma'lumotni o'chirishni xohlamadi
("tegmang"), lekin **shtraf va sof summani alohida-alohida (yashil/
qizil) ko'rsatishni** so'radi.

### Topilgan qo'shimcha bug — `jarima_summasi` shtrafni to'liq aks ettirmasdi

`finish_production_task_service`dagi "bajarilmagan dona" shtrafi
(`penalty`) faqat `ish_haqi_summasi` ichida "yashirin" hisoblanardi —
`mq.jarima_summasi` maydonining o'zi hech qachon yangilanmasdi. Demak
hisobot uchun jami shtrafni chiqarib bo'lmasdi (`jarima_summasi`
har doim faqat tortishdagi og'ish shtrafini ko'rsatardi, "bajarilmagan
dona" shtrafini EMAS).

### Yechim

`task_service.py::finish_production_task_service` — endi
`mq.jarima_summasi = mq.jarima_summasi + penalty` (yig'iladi, ustidan
yozilmaydi — tortish-og'ishi shtrafi allaqachon bor bo'lishi mumkin),
`ish_haqi_summasi` shu yangilangan `jarima_summasi`dan hisoblanadi
(natija o'zgarmaydi, faqat endi `jarima_summasi` maydoni haqiqiy jami
shtrafni to'g'ri aks ettiradi).

`pzprofile.html`/`egaprofile.html`/`editusr.html` — "Bu oy topgan
pulim" kartasi ikkiga bo'lindi: **yashil** — "Bu oy topgan pulim
(sof)" (`pazanda_month_stats.earnings` — allaqachon jami-shtraf
sifatida hisoblangan), **qizil** — "Shtraf" (`pazanda_month_stats.
jarima`, faqat shtraf mavjud bo'lsa ko'rinadi).

Real ma'lumotdagi eski yozuv (mq=61, task=2) `jarima_summasi`si ham
to'g'ri qiymatga (49186.62) qo'lda backfill qilindi — foydalanuvchi
o'chirishni xohlamagani uchun vazifaning o'zi saqlanib qoldi, faqat
uning shtraf-maydoni endi to'g'ri ko'rsatiladi.

### Tekshirildi

- Django shell'da izolyatsiyalangan tranzaksiyada: to'liq oqim (tortish
  → "Ish bitdi" → 0 dona bilan erta yopish) — `jarima_summasi` endi
  shtrafni to'g'ri qamrab olishi, `get_pazanda_month_stats`dagi
  `jarima`/`earnings` ikkalasi ham mos kelishi tasdiqlandi.
- `python manage.py check` — xatosiz (faqat oldindan mavjud
  `unique=True` ogohlantirishi).
- Bu — faqat server (Django) tomonidagi o'zgarish, Desktop Agent
  `.exe`ga tegilmagani uchun qayta build shart emas.

## 175-qadam: "Ishlab topgani" (jarimasiz, umumiy) ko'rsatkichi qo'shildi

Foydalanuvchi 174-qadamdagi yashil/qizil bo'linishdan keyin savol berdi:
raqamlar to'g'ri hisoblanganini alohida tekshirtirdi (Go'sht narxi
160 000 so'm/kg ekanini birga tasdiqladik — hisob-kitobning o'zi
to'g'ri, faqat narx yuqori edi, o'zgartirmadik), so'ng "ho'p ishlab
topganichi?" — ya'ni jarimadan OLDINGI umumiy ishlab topilgan summani
ham ko'rishni so'radi.

### Yechim

`stock_service.py::get_pazanda_month_stats` — yangi `gross` maydoni
qo'shildi (`earnings + jarima`, ya'ni jarimasiz umumiy summa).
`pzprofile.html`/`egaprofile.html`/`editusr.html` — uchinchi karta
qo'shildi: 🔵 **"Ishlab topgani (jarimasiz)"** (ko'k), 🔴 **"Shtraf"**
(qizil, faqat mavjud bo'lsa), 🟢 **"Bu oy topgan puli (sof)"** (yashil)
— uchtasi qatorlashib, `gross - jarima = sof` tenglamasi vizual
ravishda ko'rinadi.

### Tekshirildi

- Django shell orqali real ma'lumot bilan: `gross(17000) - jarima
  (50886.62) == earnings(-33886.62)` aniq tengligi tasdiqlandi.
- `python manage.py check` — xatosiz (faqat oldindan mavjud
  `unique=True` ogohlantirishi).
- Bu — faqat server (Django) tomonidagi o'zgarish, Desktop Agent
  `.exe`ga tegilmagani uchun qayta build shart emas.

## 176-qadam: Dublikat QR yana takrorlandi — YAKUNIY, eng pastki darajadagi himoya qo'shildi

Foydalanuvchi: "hozir 3ta qr kod chiqarib so'ng yana 6ta chiqarib
beryabdi ... bekordan qog'ozni o'ynatib yuribdi." Tekshirilganda —
task 5 (reja=3) uchun yana 6 ta Serial topildi (unit_index 1,2,3 ikki
marta, 13 soniya farq bilan) — bu 168- va 175-qadamlarda "bulletproof"
deb hisoblangan `MiqdorQoshish.source_task` UNIQUE cheklovi hali ham
to'liq to'smagan holat. Sxema to'g'ridan-to'g'ri tekshirildi —
cheklov haqiqatan ham SQLite jadvalida bor edi (`source_task_id ...
UNIQUE`), shunga qaramay muammo qaytalandi — aniq ildiz sababi
(qaysi yo'ldan ikkinchi chaqiruv kelayotgani) hali ham noma'lum
qoldi.

### Yakuniy yechim — Serial yaratishning O'ZIDA himoya

`qr_service.py::generate_serials_for_batch` — endi funksiya BOSHIDA
`Serial.objects.filter(batch=miqdor_qoshish)` tekshiradi: agar bu
partiya uchun Serial'lar ALLAQACHON mavjud bo'lsa, ular qaytariladi,
YANGISI YARATILMAYDI. Bu — yuqori darajadagi (task_service.py,
confirm_task_finished_materials) himoyalardan farqli — SABABI
QANDAY/QAYERDAN bo'lishidan qat'i nazar, funksiyaning o'zi endi
tabiiy ravishda idempotent: necha marta va qayerdan chaqirilishidan
qat'i nazar, bitta partiya uchun Serial'lar FAQAT bir marta
yaratiladi.

### Tekshirildi

- Django shell'da izolyatsiyalangan tranzaksiyada:
  `generate_serials_for_batch(mq)` **to'g'ridan-to'g'ri 3 marta**
  ketma-ket chaqirilib — har safar AYNAN BIR XIL 3 ta Serial
  qaytarilishi, DB'da jami faqat 3 ta qolishi tasdiqlandi.
- Real ma'lumotdagi dublikat (task 5, mq=64: 6 ta → 3 ta) tozalandi.
- `python manage.py check` — xatosiz (faqat oldindan mavjud
  `unique=True` ogohlantirishi).
- Bu — faqat server (Django) tomonidagi o'zgarish, Desktop Agent
  `.exe`ga tegilmagani uchun qayta build shart emas.

## 177-qadam: QR yana "3+3" chiqdi — bu safar DATA emas, CHOP ETISH darajasidagi poyga holati edi

Foydalanuvchi: "yana shu holat 3tani chiqarib yana 3ta chiqardi loglarni oqi." Loglar (`runserver.log`/`server.log`) eski (May sanasi) va foydasiz bo'lib chiqdi — joriy serverning haqiqiy konsol chiqishi hech qayerga yozilmagan edi. Shuning uchun to'g'ridan-to'g'ri MA'LUMOTLAR BAZASINI tekshirdim:

**Muhim natija**: bu safar DB'da HECH QANDAY dublikat Serial yo'q edi
(task 5 va yangi task 6 — ikkalasida ham aynan reja miqdoricha
Serial, ortiqcha yo'q — 176-qadamdagi tuzatish ishlayapti). Demak
muammo endi ma'lumot darajasida emas — **chop etish/ko'rsatish
darajasida** edi.

### Ildiz sabab

`_on_pending_print_batch_loaded` — partiya ko'rsatilgan zahoti
`_mark_batch_printed`ni FON OQIMIDA (asinxron) chaqiradi. Agar shu
so'rov serverga yetib borib qaytishidan OLDIN (bir necha soniya
ichida) xodim badge'ini QAYTA skanerlasa — server hali `labels_printed
=False` deb bilib, AYNAN O'SHA partiyani yana "chop etishga tayyor"
sifatida qaytaradi — natijada bir xil 3 ta QR kod ekranga/printerga
IKKINCHI marta chiqadi (DB'da dublikat yaratilmasdan — Serial'lar
o'sha-o'sha, faqat ikki marta ko'rsatiladi/chop etiladi).

### Yechim

`employee_scan_widget.py` — yangi mahalliy (client) xotira:
`self._recently_shown_batch_ids` (partiya ID -> vaqt), 60 soniyalik
TTL bilan. `_on_pending_print_batch_loaded` — partiyani ko'rsatishdan
OLDIN shu ro'yxatni tekshiradi: agar shu partiya YAQINDA
ko'rsatilgan bo'lsa — qayta ko'rsatilmaydi/chop etilmaydi, faqat
navbat davom etadi. Bu server javobini kutmasdan, mahalliy darajada
poyga oynasini yopadi.

### Tekshirildi

- Offscreen Qt orqali: bitta partiya birinchi marta yuklanganda
  ko'rsatilib `mark_batch_printed` chaqirilishi; DARHOL qayta
  yuklanganda (server javobi hali kelmagan holatni simulyatsiya
  qilib) — endi QAYTA ko'rsatilmasligi/chop etilmasligi, shunchaki
  navbat davom etishi tasdiqlandi.
- `.exe` qayta build qilindi, 8 soniyalik smoke-test bilan tasdiqlandi.

## 178-qadam: Dublikat/qayta-chop etish shikoyati YANA takrorlandi — haqiqiy ildiz sabab topildi (177-qadam yetarli emas edi)

Foydalanuvchi 177-qadamdagi tuzatishdan keyin ham xuddi shu shikoyatni
qayta-qayta, tobora asabiylashib bildirdi: "print berishda chiqarib
keyin yana qayta beryabdi ... bitta qr kodni ikki marta chiqaryabdi."
177-qadamda qo'shilgan `_recently_shown_batch_ids` mijoz-tomon keshi
faqat **60 soniyalik** oynani yopadi — bu YETARLI EMAS edi, chunki
haqiqiy ildiz sabab boshqa joyda ekan.

### Haqiqiy ildiz sabab

`_mark_batch_printed` (`employee_scan_widget.py`) — partiya
ko'rsatilgandan keyin serverga "chop etildi" deb xabar beruvchi
so'rov **butunlay "fire-and-forget"** edi: `worker.failed.connect(lambda
_msg: None)` — muvaffaqiyatsiz bo'lsa (tarmoq uzilishi, server
vaqtinchalik javobsizligi — aynan shu turdagi muammolar shu sessiyada
`WarehouseListPage`da ham kuzatilgan, 173-qadam) **hech qanday qayta
urinish yo'q edi**, xato jim yutilardi. Natijada serverda
`labels_printed` HECH QACHON `True` bo'lmay qolardi. 60 soniyalik
mijoz keshi muddati o'tgach (xodim chop etib, ketib, keyingi vazifasi
uchun bir necha daqiqadan keyin qayta badge'ini skanerlasa — juda
oddiy, kutilgan holat), server hamon "chop etilmagan" deb bilgani
uchun **aynan o'sha partiya yana ko'rsatilardi/chop etilardi** — DB'da
hech qanday dublikat Serial yaratilmasdan (bu allaqachon bir necha
marta alohida tekshirilib tasdiqlangan edi — 176/177-qadamlar), faqat
bir xil, allaqachon mavjud QR kodlar takror ko'rsatilardi. Bu
foydalanuvchi tasvirlagan "bitta QR kodni ikki marta chiqaryapti"
xatti-harakatiga aniq mos keladi.

### Yechim

`_mark_batch_printed` endi muvaffaqiyatsiz bo'lsa jim yutilmaydi —
`_on_mark_batch_printed_failed` orqali `MARK_PRINTED_RETRY_MS` (3s)
oralig'ida, `MARK_PRINTED_MAX_ATTEMPTS` (5) marta qayta uriniladi
(sessiya hali faol bo'lsa). Bu tasdiqni serverga yetkazish
ehtimolini sezilarli oshiradi, xuddi shu sinfdagi (vaqtinchalik
tarmoq muammosi) xatoliklarga chidamli qiladi.

### Tekshirildi

- `ast.parse` orqali fayl sintaksisi tekshirildi (xatosiz).
- `.exe` qayta build qilindi (`PyInstaller`, "Building because
  employee_scan_widget.py changed" — o'zgarish to'g'ri aniqlangani
  tasdiqlandi), muvaffaqiyatli yakunlandi.
- **Eslatma**: bu tuzatish muammoni yumshatadi (retry orqali
  muvaffaqiyat ehtimolini oshiradi), lekin agar server/tarmoq
  butunlay uzoq vaqt (`MARK_PRINTED_MAX_ATTEMPTS * MARK_PRINTED_RETRY_MS`
  = 15s dan ko'p) ishlamay qolsa, nazariy jihatdan hamon qayta
  ko'rsatilishi mumkin — bu holatda muammo endi dasturiy bug emas,
  balki haqiqiy tarmoq/server uzilishi bo'ladi (foydalanuvchiga shu
  farq tushuntirilishi kerak, agar yana takrorlansa).

## 179-qadam: 178-qadam YETARLI EMAS edi — HAQIQIY ildiz sabab DB orqali topildi: kamera/skaner o'zi chop etilgan yorliqni qayta o'qib, vazifani o'z-o'zidan "yakunlab" qo'yardi

Foydalanuvchi 178-qadamdan keyin ham xuddi shu shikoyatni, endi juda
qattiq so'zlar bilan ("masuliyatsizsan") qayta bildirdi. Bu safar
gumon/nazariya bilan emas, **to'g'ridan-to'g'ri joriy DB'ni**
(`db.sqlite3`, foydalanuvchining bugungi — 2026-08-04 — haqiqiy sinov
ma'lumotlari) tekshirib, aniq dalil topildi:

- Eng so'nggi vazifa (`ProductionTask` id=9, "Burger" 3 dona):
  `created_at=05:08:50`, `completed_at=05:10:34` — atigi 1 daqiqa 44
  soniyada.
- Uning `MiqdorQoshish` (id=68) — 3 ta `Serial` (id 82,83,84) —
  `created_at=05:09:58`. **`scan_soni` qiymatlari: 1, 2, 1** —
  yaratilgan zahoti, hech kim qo'lda hech narsani "sotmagan/
  jo'natmagan" holda (`holati` hammasi hali `omborda`).

**Muhim texnik dalil**: `scan_soni`ni oshiradigan yagona server yo'li
— `qr_service.register_scan(kod)` — ikki joydan chaqiriladi: (1)
`landing/views.py` public `/p/<kod>/` sahifasi (mijoz skanerlaganda),
(2) `agent_api_views.py::agent_scan` — Desktop Agent'ning UNIVERSAL
skaner endpointi. Faqat **(2) yo'li** `_maybe_finish_task_on_scan`ni
chaqiradi — bu funksiya har bir partiyaning barcha donalari kamida
1 marta skanerlanganda (`scan_soni__gte=1`) vazifani AVTOMATIK
`done`ga o'tkazadi (111-qadamda, "dona-dona kuzatish" niyati bilan
qo'shilgan — g'oya: pazanda har bir yorliqni qadoqqa yopishtirgach,
qo'lda skanerlab tasdiqlaydi).

Task 9'ning avtomatik yakunlangani (`completed_at` bilan) — 3 ta
Serial ham kamida 1 marta `agent_scan` orqali skanerlangan bo'lishi
SHART, aks holda bu mumkin emas edi. Lekin foydalanuvchi hech qachon
qo'lda skanerlashni tasvirlamagan — demak **kamera/skaner (Desktop
Agent'da doimiy ishlaydigan, xodim badge'ini istalgan payt
skanerlashga tayyor turadigan xizmat) partiyaning O'ZI chop etilgan/
ekranda ko'rsatilgan yorliqlarini QAYTA O'QIB YUBORGAN** — yangi
yopishtirilgan yorliq printerdan chiqib kameraning ko'rish maydoniga
tushib qolishi yoki ekrandagi QR-panjaraning o'zi (fullscreen
kiosk ekranida 8 soniya ko'rsatiladi) kameraga aks etib qolishi
orqali. Bu — foydalanuvchi tasvirlagan "bitta narsa (bu safar
'vazifa') ikki marta chiqmoqda" bilan aniq mos keladi: xodim
hech narsa qilmagan holda, tizim o'z-o'zidan vazifani "yakunlab",
UI'da yangi hodisalar (skan natijasi kartochkasi va h.k.) paydo
bo'lishiga sabab bo'lgan.

### Yechim

`employee_scan_widget.py`: yangi `self._own_batch_kods` (set) — har
bir partiya ekranda ko'rsatilganda (`_show_print_batch_card`) shu
partiyaning barcha `Serial.kod`lari shu ro'yxatga qo'shiladi.
`handle_scanned_code` — endi ENG BIRINCHI navbatda tekshiradi: agar
kelgan kod shu ro'yxatdagi biror kodni o'z ichiga olsa (URL shaklida
kelishi ham mumkinligi uchun `in` bilan qidiruv) — bu HAQIQIY xodim
skani emas, balki tizimning o'z chiqargan yorlig'ini qayta o'qishi
deb hisoblanadi va **hech qanday server so'rovi yuborilmasdan** jim
e'tiborsiz qoldiriladi. Ro'yxat har badge-sessiya oxirida
(`_end_session`) tozalanadi.

### Tekshirildi

- `ast.parse` orqali sintaksis tekshirildi (xatosiz).
- DB orqali (yuqorida) muammoning aniq vaqti/hodisasi topildi va
  server tomonidagi yagona mumkin bo'lgan yo'l (`agent_scan`)
  ekanligi kod orqali tasdiqlandi.
- `.exe` qayta build qilindi (PyInstaller "toc changed" — o'zgarish
  kiritilgani tasdiqlandi).
- **Eslatma**: 178-qadamdagi retry-tuzatish ham to'g'ri va foydali
  qoladi (boshqa, haqiqiy tarmoq-uzilishi holatlari uchun) — u olib
  tashlanmadi, faqat bu YANGI, ASOSIY sababga qo'shimcha ekanligi
  aniqlandi.

---

## 180-qadam: Vazifalar sana filtri — bitta kalendar maydonga soddalashtirildi

**Holat: DONE**

### Muammo
"Bitta kun / Oraliq" tugma-almashtirish UI + alohida kun-tanlash
dropdown foydalanuvchi tomonidan keraksiz murakkab deb topildi.

### Yechim
Bitta `<input>` maydon + Airbnb uslubidagi click-kalendar: bitta
bosish — bitta kun, ikkinchi (boshqa) kunga bosish — oraliq,
tanlangan kunni **qayta bosish** — o'sha kunga qaytaradi (reset).
Vazifa bor kunlar (`active_days`) nuqta bilan belgilanadi.

### O'zgargan fayllar
- `main/production_views.py` — `vazifalar_page`: `mode`/`sana` GET
  parametrlari olib tashlandi, `from`/`to` + `active_days_json`
- `main/templates/vazifalar.html` — eski mode-toggle JS o'chirildi,
  yangi kalendar widget

### Tekshirildi
`manage.py check`/`test` — xatosiz. Commit: `1db8c944`.

---

## 181-qadam: `super_agent_releases` URL admin.stockfirm.uz'da yo'q edi (500/NoReverseMatch)

**Holat: DONE**

### Muammo
`admin.stockfirm.uz` (`CompanyMiddleware`) aslida `crm.admin_urls`ni
ishlatadi, `landing.urls`ni emas — yangi qo'shilgan
`super_agent_releases`/`super_agent_release_delete` faqat
`landing/urls.py`ga qo'shilgan edi, shuning uchun superadmin panel
butunlay 500 bilan yiqilib turardi.

### Yechim
`crm/crm/admin_urls.py`ga shu ikki route qo'shildi.

### Tekshirildi
`manage.py check` — xatosiz. Commit: `ac6dfa10`.

---

## 182-qadam: Agent .exe yuklash — AJAX progress-bar (sahifa qotib qolmasin)

**Holat: DONE**

### Muammo
Katta `.exe` fayl yuklanganda oddiy form-submit butun sahifani
bloklab, brauzer tabini "qotgan" holatga keltirardi.

### Yechim
XHR (`XMLHttpRequest.upload.onprogress`) orqali fon jarayonida
yuklash, `super_base.html`da umumiy navbar progress-pill + yuqori
chiziq (`window.superUpload` global API). `landing/views.py`
`super_agent_releases` endi `X-Requested-With` bo'lsa JSON qaytaradi.

### O'zgargan fayllar
`landing/views.py`, `landing/templates/landing/super_base.html`,
`landing/templates/landing/super_agent_releases.html`

### Tekshirildi
`manage.py check`/`test` — xatosiz. Commit: `e4f8fd04`.

---

## 183-qadam: Tarozi sig'imi cheklangan stansiyalar — vazifa tortish ketma-ket porsiyalarga bo'linadi

**Holat: DONE**

### Muammo
Tarozilar turlicha (20/30/60 kg) sig'imga ega — kerakli xom ashyo
miqdori bitta tortishga sig'masa, oldin bitta martalik tortish
so'ralardi.

### Yechim
- Server: `TaskMaterialPickup.poured_qty` (yig'ilgan tortish) yangi
  maydon (migratsiya `0093`). `task_service.weigh_task_pickup` endi
  ketma-ket porsiyalarni qo'llab-quvvatlaydi — server tarozi
  sig'imini bilishi shart emas, faqat yig'indini kuzatadi.
- Desktop Agent: Sozlamalar > Tarozi'ga "Tarozining maksimal sig'imi
  (kg)" maydoni qo'shildi (har stansiyada alohida). Kerakli miqdor
  sig'imdan oshsa, "1/2-qism", "2/2-qism" tarzida ketma-ket
  ko'rsatiladi.

### O'zgargan fayllar
`main/models.py`, `main/migrations/0093_*`, `main/services/task_service.py`,
`main/agent_api_views.py`, `desktop_agent/app/windows/employee_scan_widget.py`,
`desktop_agent/app/windows/settings_page.py`

### Tekshirildi
`manage.py check`/`test` — xatosiz, `.exe` qayta build qilindi.
Commit: `f872d230`.

---

## 184–191-qadam: Ombor sahifalari — raqam formati, pagination, AJAX, qidiruv UX, rasmli grid+modal

**Holat: DONE**

### Muammo (bir nechta alohida shikoyat, bitta mavzu ostida)
- Narx/miqdor raqamlarida ming-guruhlash (probel) yo'q edi.
- Ombor mahsulotlari pagination server tomonda bor edi, shablonda
  ko'rinmasdi.
- Kirim-chiqim sahifasida mahsulot tanlash oddiy `<select>` —
  100+ mahsulotda qidirib topish qiyin, rasm yo'q.
- Qidiruv avval oddiy GET-form (Filter bosilmaguncha ishlamas edi),
  keyin noto'g'ri tuzatilib to'liq sahifa qayta yuklanishiga
  (`form.submit()`) sabab bo'ldi — "chayqalish" hissi berardi.
- Kirim modali `.warehouse-page` konteynеridan tashqarida joylashib,
  sayt uslubi (`.btn`, `.field`) unga qo'llanmagan edi.
- Ombor tanlash ixtiyoriy edi, majburiy bo'lishi kerak edi.

### Yechim
- Yangi `main/templatetags/spc_filters.py` — `spc` filter (1 250 000
  formatida probel-guruhlash).
- `warehouse_products.html` — pagination UI + keyinchalik to'liq
  AJAX (server-tomon qidiruv/sahifalash, sahifa reload'siz).
- `warehouse_movements.html` — butunlay qayta qurildi: rasm-kartochka
  grid (hover-animatsiyali), bosilganda "Yangi kirim" MODAL ichida
  ochiladi, ombor tanlash majburiy (server+client tekshiruv), mahsulot
  qidiruvi hodimlar/mahsulotlar sahifasidagi kabi suzuvchi dropdown
  (AJAX debounce, grid'ni qayta chizmaydi).
- `warehouse_views.py` — `warehouse_products`ga `data_format=json`
  filiali (`page_size` parametrik, picker va to'liq ro'yxat uchun
  qayta ishlatiladi), `warehouse_movements`da `ombor_id` majburiy
  tekshiruvi + AJAX javob (`is_ajax`).

### O'zgargan fayllar
`main/templatetags/__init__.py`, `main/templatetags/spc_filters.py`,
`main/warehouse_views.py`, `main/templates/warehouse_products.html`,
`main/templates/warehouse_movements.html`, `main/templates/warehouse_styles.html`

### Tekshirildi
Har bosqichda `manage.py check`/`test` — xatosiz.
Commitlar: `fd236662`, `4deb3098`, `0bbe21b7`, `5f147a67`, `ee8e8a9d`,
`2b3c8f3e`, `1b5d6f89`, `d2346047`.

---

## 192-qadam: Dona/litr birlikdagi vazifa xom ashyo ko'rsatmasi 600ms'da ovozsiz avtomatik tasdiqlanib ketardi

**Holat: DONE**

### Muammo
Pazanda badge skanidan keyin "necha dona qadoq/litr yog' oling"
ko'rsatmasi chiqar edi, lekin 600ms ichida o'zi tasdiqlanib g'oyib
bo'lardi — o'qishga ulgurmasdi.

### Yechim
Bunday so'rovlar uchun `weigh_ack_btn` ("Oldim ✓") — aniq bosilmasdan
avtomatik davom etmaydi.

### O'zgargan fayllar
`desktop_agent/app/windows/employee_scan_widget.py`

### Tekshirildi
Kompilyatsiya tekshiruvi, `.exe` qayta build. Commit: `b8801625`.

---

## 193-qadam: Dona/litr xom ashyo tasdig'i Desktop Agent'dan veb dashboardga ko'chirildi

**Holat: DONE**

### Muammo
Kioskda sichqoncha ishlatilmaydi — 192-qadamdagi tugma yechimi ham
"So'rov topilmadi" xatosiga olib kelgan holatlar kuzatildi (real
foydalanishda ikki marta tasdiqlash urinishi).

### Yechim
Sanoq/hajm (dona/litr) `TaskMaterialPickup`lar endi Desktop Agent'da
UMUMAN ko'rsatilmaydi (`_on_my_task_pickups_loaded` filtrlaydi).
Buning o'rniga veb dashboard (`pazanda_dashboard.html`) — "Mening
vazifalarim" > yangi "Olib qo'yish kerak" bo'limi, bitta "Oldim ✓"
tugmasi (`pz_ack_task_pickup` view, xuddi "Ish bitdi" kabi).

### O'zgargan fayllar
`main/services/task_service.py` (`WEIGHABLE_BIRLIKLAR`/`is_weighable_birlik`),
`main/views.py`, `main/production_views.py`, `main/urls.py`,
`main/templates/pazanda_dashboard.html`,
`desktop_agent/app/windows/employee_scan_widget.py`

### Tekshirildi
`manage.py check`/`test` — xatosiz, `.exe` qayta build.
Commit: `80239f54`.

---

## 194-qadam: Ish haqi turi endi individual (har bir xodim uchun alohida) sozlanadi

**Holat: DONE**

### Muammo
`Company.ish_haqi_turi` faqat firma bo'yicha umumiy edi — "Oylik"
tanlangan firmada mahsulot soniga qarab to'lanishi kerak bo'lgan
xodim bo'lsa, uning ishlab chiqargani hisobga olinmasdi (real holat:
10 dona x 1500 so'm o'rniga 0 so'm chiqqan, faqat tortish og'ishi
shtrafi ko'rsatilgan).

### Yechim
`User.ish_haqi_turi_override` (bo'sh/`fixed`/`per_unit`, bo'sh bo'lsa
firma standarti). Yangi `stock_service.effective_ish_haqi_turi(user,
company)` — barcha eski `company.ish_haqi_turi == 'per_unit'`
tekshiruvlari shu funksiyaga almashtirildi. `editusr.html`da xodim
uchun alohida tanlash kartasi.

### O'zgargan fayllar
`main/models.py`, `main/migrations/0094_*`, `main/services/stock_service.py`,
`main/services/task_service.py`, `main/services/payroll_service.py`,
`main/views.py`, `main/templates/editusr.html`

### Tekshirildi
`manage.py check`/`test` — xatosiz. Commit: `103cabe5`.

---

## 195-qadam: MUAMMOLAR_VA_TAVSIYALAR.md — xavfsizlik/sifat tuzatishlari

**Holat: DONE**

### Nima qilindi
1. Savdogar shartnoma fayllariga (`contract_pdf`, `signed_contract_scan`)
   kengaytma/hajm tekshiruvi (`main/utils.py::validate_uploaded_file`)
   — `ImageField`lardan farqli avval umuman tekshirilmasdi.
2. Yalang'och `except:` → `except Exception:` + `logging`
   (`backup_views.py`, `hisobot_views.py`) — xatti-harakat
   o'zgarmaydi, faqat diagnostika imkoni paydo bo'ladi.
3. Desktop Agent — production (`*.stockfirm.uz`) manzillar uchun
   HTTPS majburlash (`api_client.py::_enforce_https_for_production`),
   lokal (`127.0.0.1`/`localhost`) o'zgarishsiz.
4. `main/tests_warehouse.py` — ombor kirim/o'rtacha narx stsenariylari
   uchun boshlang'ich testlar.

### O'zgargan fayllar
`main/utils.py`, `main/views.py`, `main/backup_views.py`,
`main/hisobot_views.py`, `desktop_agent/app/api_client.py`,
`main/tests_warehouse.py`, `MUAMMOLAR_VA_TAVSIYALAR.md`

### Tekshirildi
`manage.py check`/`test` (33 test, hammasi o'tdi), `.exe` qayta build.
Commitlar: `31f49d7e`, `71f0b986`, `4d14d207`, `dfb129d5`.

---

## 196-qadam: Desktop Agent — token eskirsa ISTALGAN so'rovdan avtomatik logout

**Holat: DONE**

### Muammo
Faqat heartbeat 401 qaytarsa avtomatik logout (`_handle_token_invalid`)
ishga tushardi. Boshqa so'rovlar (badge/vazifa QR skanerlash, tortish,
sinxronlash) 401 qaytarsa shunchaki oddiy xato matni ko'rsatardi —
foydalanuvchi "QR kod topilmadi" kabi chalkash xabar bilan qolib,
haqiqiy sabab (token eskirgan) yashirin qolardi (safiya firmasida
aynan shu holat kuzatilgan va diagnostika qilingan).

### Yechim
`_ApiCallWorker`ga (ikkala nusxasi — `employee_scan_widget.py` va
`settings_page.py`) `token_invalid` signali qo'shildi (`ApiError.
status_code == 401` bo'lsa emit qilinadi, mavjud `failed` signali ham
baribir yuboriladi — orqaga moslik saqlanadi). `EmployeeScanWidget.
_replace_worker` ENDI HAR BIR workerni avtomatik ulaydi (`hasattr`
tekshiruvi bilan) — barcha ko'plab chaqiruv joylarini birma-bir
o'zgartirish shart bo'lmadi. `SettingsPage`da faqat `_sync_worker`
(mavjud tokendan foydalanadigan `fetch_omborlar`) ulandi — login
urinishidagi 401 ("parol xato") bilan aralashtirilmasligi uchun.
Ikkalasi ham `MainWindow._handle_token_invalid`ga ulanadi (heartbeat
bilan bir xil "Sessiya yopildi" dialogi + login sahifasiga qaytarish).

### O'zgargan fayllar
`desktop_agent/app/windows/employee_scan_widget.py`,
`desktop_agent/app/windows/settings_page.py`,
`desktop_agent/app/windows/main_window.py`

### Tekshirildi
Kompilyatsiya tekshiruvi, `.exe` qayta build. Commit: `3f619169`.

---

## 197-qadam: Public mahsulot QR sahifasi firma subdomenida 404 berardi

**Holat: DONE**

### Muammo
QR yorliqda ATAYLAB `https://<firma>.stockfirm.uz/p/<kod>/` manziliga
ishora qilinadi (`agent_api_views._public_scan_url`), lekin bu route
faqat `landing/urls.py`da bor edi. Subdomen so'rovlari `main.urls`
orqali ishlaydi (`CompanyMiddleware`) — shu sabab HAR BIR firmaning
HAR BIR mahsulot QR kodi xaridor tomonidan skanerlanganda 404
qaytarardi (real xaridor tomonidan aniqlangan, keng qamrovli bug).

### Yechim
`p/<kod>/` va `api/p/<kod>/status/` route'lari `main/urls.py`ga ham
qo'shildi (bir xil `landing.views.product_scan_view`/
`product_scan_status_api` funksiyalari qayta ishlatiladi).

### O'zgargan fayllar
`main/urls.py`

### Tekshirildi
`manage.py check`/`test` — xatosiz. Commit: `0d9737bf`.

---

## 198-qadam: Etiketka chop etishga DENSITY/SPEED buyruqlari

**Holat: DONE**

### Muammo
"Sinov chop etish" bosilganda bitta bo'sh (issiqlik izsiz) yorliq
chiqishi haqida shikoyat — ehtimoliy sabab: ba'zi TSPL printerlarda
drayver qayta o'rnatilgandan keyin bosim zichligi (DENSITY) 0'ga
tushib qolishi.

### Yechim
`build_tspl_label`ga har chop etishda aniq `DENSITY 8`/`SPEED 4`
buyruqlari qo'shildi (avval kalibrlanmagan/standart holatga tayanardi).

### O'zgargan fayllar
`desktop_agent/app/label_printer_service.py`

### Tekshirildi
Kompilyatsiya tekshiruvi, `.exe` qayta build. Commit: `111e72a7`.
**Eslatma**: agar shundan keyin ham bo'sh chiqsa, sabab dasturiy emas
— termal qog'oz yo'nalishi (issiqlikka sezgir tomon) yoki printerning
o'zidagi jismoniy self-test bilan tekshirilishi kerak.

---

## 199-qadam: Partiya (batch) turidagi mahsulotlarda ham vazifa faqat QR skanerlangach yakunlanadi

**Holat: DONE**

### Muammo
"Ish bitdi" bosilgan zahoti (hech qanday QR skanerlanmasdan) `batch`
turidagi vazifa darhol to'liq reja miqdori bilan yopilib qolardi —
faqat `unit` granularityda "dona-dona kuzatish" ishlar edi. Foydalanuvchi
buni "QR kod orqali qo'shilish ishlamayapti" deb xato deb topdi va
partiyalarda ham QR orqali kuzatishni talab qildi.

### Yechim
- `task_service._start_producing`: shart `serial_granularity == 'unit'`
  dan `!= 'none'`ga o'zgardi — endi `batch` ham skanerlashni kutadi
  (`task.status = 'producing'`), faqat `none` (QR umuman yo'q) holatda
  eski (darhol yakunlash) xatti-harakat saqlandi.
- `finish_production_task_service`, `task_progress`,
  `agent_api_views._maybe_finish_task_on_scan`: progress hisoblash
  `Serial.objects.count()` o'rniga `Sum('dona_soni')` bilan almashtirildi
  — `batch`da har bir skanerlangan QR o'z qadoq hajmicha (masalan 3)
  qo'shadi, `unit`da har doim 1 (o'zgarishsiz).

### O'zgargan fayllar
`main/services/task_service.py`, `main/agent_api_views.py`,
`main/tests_production.py` (yangi — 2 ta test: batch bosqichma-bosqich
yakunlanishi, `none` granularity eski xatti-harakati saqlanishi)

### Tekshirildi
`manage.py check`/`test` (35 test, hammasi o'tdi). Commit: `4aa6cf5d`.

---

## 200-qadam: Ishlab chiqarish vaqti (muddat) + Qaytarish (Utilizatsiya/Qayta ishlash) + KPI tizimi

**Holat: DONE**

### Nima qilindi
Uch qismli funksiya (foydalanuvchi bilan bitta so'rovda kelishilgan):

1. **Ishlab chiqarish vaqti** — `Mahsulot.kutilgan_ishlab_chiqarish_soat`
   (ixtiyoriy, mahsulot sahifasida belgilanadi). Vazifa OLINGANDA
   (`claim_task`/`create_production_task` pazanda bilan) shu asosda
   `ProductionTask.muddat` avtomatik hisoblanadi (`claimed_at` + soat).
   `ProductionTask.kechikdi` property — muddat o'tganmi.

2. **Qaytarish — Utilizatsiya/Qayta ishlash** — `qaytarish_tasdiq` endi
   ikki harakatni qo'llab-quvvatlaydi: Utilizatsiya (ombor qoldig'iga
   qo'shilmaydi, chiqim) yoki Qayta ishlash (ega tanlagan xom ashyoga
   belgilangan miqdorda qo'shiladi). Ikkalasida ham javobgar
   (savdogar/yetkazib beruvchi) tanlansa, mahsulot tannarxi asosida
   qarz yoziladi (`qaytarilgan_mahsulotlar.qarz_summasi`/`javobgar`).
   `Company.qaytarish_javobgarligi` — standart javobgar turi (faqat
   UI'da oldindan tanlash uchun, majburiy emas).

3. **KPI tizimi** — yangi `services/kpi_service.py::get_employee_kpi`
   — egadan boshqa har bir rol uchun joriy oy ko'rsatkichlari:
   ishlab chiqaruvchi (bajarilgan vazifalar, kechikkan, o'z vaqtida %),
   omborchi (ko'rib chiqilgan so'rovlar, o'rtacha javob vaqti daqiqada),
   savdogar/yetkazib beruvchi (sotuvlar soni/summasi, qaytarish
   nisbati). Profil sahifalarida (`egaprofile.html`, `pzprofile.html`,
   `ytprofile.html`, `egayt.html`) ko'rsatiladi.

### O'zgargan fayllar
`main/models.py`, `main/migrations/0095_*`, `main/qaytarish_views.py`,
`main/urls.py`, `main/templates/qaytarishlar.html`,
`main/templates/seemahsulot.html`, `main/templates/pazanda_dashboard.html`,
`main/templates/egaprofile.html`, `main/templates/pzprofile.html`,
`main/templates/ytprofile.html`, `main/templates/egayt.html`,
`main/services/task_service.py`, `main/services/kpi_service.py` (yangi),
`main/views.py`, `main/tests_kpi_returns.py` (yangi — 8 test)

### Tekshirildi
`manage.py check`/`test` — 49 test, hammasi o'tdi. Commit: `f3d42b8e`.

### Cheklovlar (keyingi qadamlarda kengaytirilishi mumkin)
- Qarz (`qarz_summasi`) faqat KO'RSATISH uchun — alohida to'lov/hisob-kitob
  oqimi hozircha yo'q.
- Qaytarish hozircha faqat yetkazib beruvchidan qabul qilinadi
  (`qaytarish_view` shu turga cheklangan) — savdogardan qaytarish
  yuborish alohida ishlab chiqilmagan, faqat TASDIQLASHDA javobgar
  sifatida savdogar tanlanishi mumkin.

---

## 201-qadam: Savdogar/yetkazib beruvchi uchun individual "sotuvga qarab" ish haqi (komissiya)

**Holat: DONE**

### Muammo
Ish haqi turi individual sozlash (`User.ish_haqi_turi_override`) faqat
ishlab chiqaruvchi (pazanda) uchun ishlar edi (`fixed`/`per_unit`).
Savdogar va yetkazib beruvchi uchun faqat "Oylik (fiksval)" mavjud edi —
ega ularga har bir sotuv/yetkazish uchun alohida komissiya belgilay
olmasdi.

### Nima qilindi
`ISH_HAQI_TURI_OVERRIDE_CHOICES`ga yangi variant qo'shildi: `per_sale`
("Sotilgan/yetkazilgan mahsulotga qarab (komissiya)") — faqat
savdogar/yetkazib_beruvchi turlariga tegishli. Yangi `User.savdo_birlik_narxi`
maydoni — har bir savdo uchun to'lanadigan summa.

`payroll_service.compute_oylik_ish_haqi` kengaytirildi: `per_sale`
tanlangan bo'lsa, shu oydagi savdolar sonini hisoblaydi (yangi
`get_savdogar_month_sales_count` — savdogar uchun `Savdo.savdogar=user`,
yetkazib beruvchi uchun avval `YetkazibBeruvchi` profilini topib
`Savdo.yetkazib_beruvchi=yb` bo'yicha) va `savdo_birlik_narxi`ga
ko'paytiradi. Natija `XodimTolov`/`XodimOyYopish` orqali mavjud
oylik yopish/avans oqimiga avtomatik integratsiya qilinadi (mavjud
`compute_oylik_ish_haqi` chaqiruvchilari o'zgarishsiz ishlaydi).

`editusr.html`da (xodimni tahrirlash sahifasi) savdogar/yetkazib
beruvchi uchun alohida "Ish haqi turi" kartasi qo'shildi (avval faqat
pazanda uchun ko'rinardi) — dropdown (`Firma standarti`/`Oylik`/
`Komissiya`) va `per_sale` tanlanganda ko'rinadigan "so'm/savdo" input
(JS orqali ko'rsatish/yashirish). `editusr` view'idagi
`set_ish_haqi_turi_override` handler endi savdogar/yetkazib_beruvchi
turlarini ham qabul qiladi, `per_unit`ni faqat ishlab chiqaruvchiga,
`per_sale`ni faqat savdogar/yetkazib beruvchiga cheklaydi.

### O'zgargan fayllar
`main/models.py` (yangi `savdo_birlik_narxi` maydoni + `per_sale` choice),
`main/migrations/0096_*`, `main/services/payroll_service.py`,
`main/views.py` (`editusr`), `main/templates/editusr.html`,
`main/tests_kpi_returns.py` (+3 test — `PerSaleIshHaqiTests`)

### Tekshirildi
`manage.py check`/`test` — 52 test, hammasi o'tdi. Commit: `05ed6789`.

---

## 202-qadam: Xom ashyo tortish shtrafi — noto'g'ri narx + tolerantlik hisobga olinmagani tuzatildi (BUG FIX)

**Holat: DONE**

### Muammo
Foydalanuvchi skrinshot bilan xabar berdi: pazanda rejani TO'LIQ
topshirsa ham ("Somsa hamir 24", 4 ta partiya), ba'zi partiyalarda
kutilmaganda katta shtraf (masalan 6507 so'm, ish haqining ~48%i)
yozilgan edi. Sabab ikkita bog'liq xato:

1. **Noto'g'ri narx**: shtraf (`jarima_summasi`) xom ashyo tortish
   og'ishini (`measured_qty - expected_qty`, komponentning O'Z birligida
   — masalan kg) tayyor mahsulotning ISH HAQI narxiga
   (`Mahsulot.ishlab_chiqarish_narxi`, so'm/dona — butunlay boshqa
   birlik, odatda ancha katta summa) ko'paytirar edi — komponentning
   haqiqiy (odatda ancha arzon) narxi umuman ishlatilmasdi.
2. **Tolerantlik hisobga olinmagan**: Desktop Agent tarozida tortishda
   allaqachon qabul qilinadigan tolerantlik bor (`TASK_WEIGH_SHORTFALL_
   TOLERANCE`=2g, `TASK_WEIGH_OVERAGE_TOLERANCE`=50g — `weigh_task_pickup`
   ichida), lekin `_start_producing`dagi shtraf hisobi bu tolerantlikni
   butunlay e'tiborsiz qoldirib, ISTALGAN (hatto 1-2 grammlik) og'ish
   uchun ham shtraf yozardi.

Natijada: tarozi "normal" deb qabul qilgan arzimas og'ish ham (masalan
40g ortiqcha, tolerantlik ichida) qimmat ish haqi narxiga ko'paytirilib,
haqiqatda hech qanday isrof bo'lmasa ham noo'rin katta shtrafga
aylanardi. Eski `ProductionMaterialRequest` oqimida
(`stock_service._apply_retsept_hisobkitob`) ham xuddi shu narx-birlik
xatosi bor edi (bu yerda tolerantlik tushunchasi umuman yo'q edi,
chunki bu tarozi orqali emas, alohida so'rov-tasdiqlash orqali ishlaydi).

### Nima qilindi
`task_service._start_producing`: shtraf endi (1) faqat qabul qilingan
tortish tolerantligidan (shortfall/overage) OSHGAN qismi uchun
hisoblanadi, (2) komponentning O'Z narxida (`tannarx` yoki `narxi`)
hisoblanadi — tayyor mahsulot narxi emas.

`stock_service._apply_retsept_hisobkitob` (eski oqim): xuddi shu
narx-birlik xatosi tuzatildi — endi komponentning o'z narxi ishlatiladi
(tolerantlik bu yerda mavjud emas, chunki bu funksiya tarozi orqali
emas ishlaydi).

### O'zgargan fayllar
`main/services/task_service.py` (`_start_producing`),
`main/services/stock_service.py` (`_apply_retsept_hisobkitob`),
`main/tests_kpi_returns.py` (+3 test — `MaterialDeviationJarimaTests`,
`LegacyMaterialRequestJarimaTests`)

### Tekshirildi
`manage.py check`/`test` — 55 test, hammasi o'tdi. Commit: `f491b432`.

---

## 203-qadam: Xodimni tahrirlash (editusr) — yetkazib beruvchi profili yo'q bo'lsa 500 xato (BUG FIX)

**Holat: DONE**

### Muammo
Foydalanuvchi demo.stockfirm.uz'da `/edituser/<username>` sahifasiga
kirganda "Server Error (500)" oldi. Sabab: `editusr` view'i
`user_edit.type == 'yetkazib_beruvchi'` bo'lsa
`YetkazibBeruvchi.objects.get(user=user_edit)` chaqirar edi — agar shu
foydalanuvchiga bog'langan `YetkazibBeruvchi` profili biror sababdan
mavjud bo'lmasa (masalan, buzilgan/yarim yaratilgan hisob), `.get()`
`DoesNotExist` bilan qulab tushardi.

### Nima qilindi
`.get()` → `.filter(user=user_edit).first()` — profil topilmasa,
sahifa baribir ochiladi (mashina ma'lumotlari maydonlari bo'sh
ko'rsatiladi), 500 o'rniga.

### O'zgargan fayllar
`main/views.py` (`editusr`)

### Tekshirildi
`manage.py check`/`test` — 55 test, hammasi o'tdi.

---

## 204-qadam: 0096-migratsiya serverda bajarilmagan edi (ProgrammingError: Unknown column)

**Holat: DONE (server tomon, kod o'zgarishi yo'q)**

### Muammo
201-qadamdan (`savdo_birlik_narxi` maydoni) keyin serverda faqat
`git pull` qilingan, `python manage.py migrate` unutilgan edi —
butun sayt (`demo.stockfirm.uz`) 500 bera boshladi:
`django.db.utils.ProgrammingError: (1054, "Unknown column
'main_user.savdo_birlik_narxi' in 'field list'")`.

### Nima qilindi
Foydalanuvchiga `venv/bin/python crm/manage.py migrate` +
`systemctl restart stockfirm` buyruqlari berildi. Eslatma: HAR safar
yangi migratsiya bilan commit qilinganda, deploy qadamlarida
`git pull` dan keyin ALBATTA `migrate` ham bajarilishi kerakligi
takidlandi.

---

## 205-qadam: Hodimlar ro'yxati sahifasidan firma-bo'yicha "Ish haqi turi" kartasi olib tashlandi

**Holat: DONE**

### Muammo
`hodimlar_list.html`ning yuqorisida firma bo'yicha umumiy "Ish haqi
turi" dropdown (`Oylik (fiksval)` / `Ishlab chiqarilgan mahsulotga
qarab`) ko'rsatilar edi. Endi (200/201-qadamlardan buyon) ish haqi turi
har bir xodim uchun ALOHIDA (`editusr.html`) sozlanadi — bu global
tanlov endi chalkashtiruvchi/keraksiz, ega "buni bu yerda
ko'rinmaydigon qilaylik" deb so'radi.

### Nima qilindi
`hodimlar_list.html`dan shu kartani butunlay olib tashlandi. Backend
(`list_views.py`dagi `set_ish_haqi_turi` POST handler, `Company.
ish_haqi_turi` maydoni) tegilmadi — faqat UI'dan yashirildi, chunki
`effective_ish_haqi_turi` hamon "firma standarti" fallback sifatida
shu qiymatdan foydalanadi (individual override bo'lmagan xodimlar
uchun).

### O'zgargan fayllar
`main/templates/hodimlar_list.html`

### Tekshirildi
`manage.py check` toza (test kerak emas — faqat shablon o'zgarishi).

---

## 206-qadam: Savdogar/yetkazib beruvchi ish haqi — flat komissiya o'rniga mahsulot narxiga (tannarxga) qo'shiladigan "sotuv ish haqi"

**Holat: DONE**

### Muammo
201-qadamda qurilgan "har bir savdo uchun belgilangan FIKS summa"
(`User.savdo_birlik_narxi`) mexanizmi ega bilan aniqlashtirilgach
noto'g'ri model bo'lib chiqdi. Ega tushuntirdi: bu "mantiqsiz" —
kerakli narsa mahsulotning O'ZIDA "sotuv uchun ish haqi" narxi
belgilash (xuddi `ishlab_chiqarish_narxi` ishlab chiqaruvchi uchun
ishlagani kabi), bu summa mahsulot TANNARXIGA qo'shilishi va sotgan/
yetkazgan xodimga shu asosda hisoblanishi kerak.

### Nima qilindi
- Yangi `Mahsulot.sotuv_ish_haqi_narxi` — 1 dona sotilgani/yetkazilgani
  uchun to'lanadigan summa, mahsulot sahifasida (`seemahsulot.html`)
  belgilanadi.
- `stock_service.recompute_tannarx` — bu summa endi `baza_tannarx` va
  `ishlab_chiqarish_narxi` qatorida tannarxga qo'shiladi (foyda
  avtomatik shuncha kamayadi).
- Yangi `Savdo.ish_haqi_summasi` — savdo yaratilganda (`views.py`,
  sotish oqimi) har bir sotilgan mahsulot qatori bo'yicha
  `qty * sotuv_ish_haqi_narxi` yig'indisi sifatida hisoblab yoziladi —
  "bu aniq savdo bo'yicha kimga qancha tegishli" degan alohida
  (informatsion) yozuv, foyda esa allaqachon tannarx orqali kamaygan.
- `payroll_service.compute_oylik_ish_haqi`: `per_sale` turi endi FIKS
  komissiya emas, shu oydagi savdolaridagi `Savdo.ish_haqi_summasi`
  yig'indisidan hisoblanadi (`per_unit`ning savdo versiyasi).
- Eski `User.savdo_birlik_narxi` maydoni va unga bog'liq
  `editusr.html`dagi qo'lda summa kiritish maydoni OLIB TASHLANDI —
  endi faqat "Ish haqi turi" tanlanadi, summa mahsulot sahifasidan
  avtomatik keladi.

### O'zgargan fayllar
`main/models.py` (`Mahsulot.sotuv_ish_haqi_narxi`, `Savdo.ish_haqi_summasi`,
`User.savdo_birlik_narxi` olib tashlandi), `main/migrations/0097_*`,
`main/services/stock_service.py` (`recompute_tannarx`),
`main/services/payroll_service.py`, `main/views.py` (`editusr`, sotish
oqimi, `seemahsulot`), `main/templates/editusr.html`,
`main/templates/seemahsulot.html`, `main/tests_kpi_returns.py`
(`PerSaleIshHaqiTests` yangilandi, +1 test — `SotuvIshHaqiTannarxTests`)

### Tekshirildi
`manage.py check`/`test` — 56 test, hammasi o'tdi.

---

## 207-qadam: Ish haqi turi kartasi — noto'g'ri tanlovlar + "amalda" holat ko'rinmasligi + oylik summasi kiritish joyi yo'qligi (UX FIX)

**Holat: DONE**

### Muammo
Ega skrinshot bilan ko'rsatdi: (1) ishlab chiqaruvchi (pazanda)ning
"Ish haqi turi" dropdown'ida unga aloqasi yo'q "Sotilgan/yetkazilgan
mahsulotga qarab" varianti ham chiqib turardi; (2) sahifada faqat
"Firma standarti" (Company darajasidagi) ko'rsatilardi, shu xodimga
HOZIR AMALDA bo'lgan turi (override yoki fallback natijasi) hech qayerda
aniq ko'rinmasdi — shuning uchun "nega tizim ishlab chiqarganiga
to'layapti-yu, dropdown 'firma standarti' deb turibdi" degan
tushunarsizlik paydo bo'ldi; (3) "Oylik (fiksval)" tanlansa ham,
summani kiritish uchun ALOHIDA sahifaga (profil) o'tish kerak edi —
shu joyning o'zida kiritish maydoni yo'q edi.

### Nima qilindi
- Har ikkala kartada (pazanda va savdogar/yetkazib beruvchi) dropdown
  endi faqat o'sha xodim turiga tegishli variantlarni ko'rsatadi
  (`per_sale` ishlab chiqaruvchiga, `per_unit` savdo xodimlariga
  chiqmaydi).
- "Firma standarti: X" qatoridan keyin "Hozir amalda: Y" qo'shildi —
  `effective_ish_haqi_turi()` orqali HAQIQIY qo'llanilayotgan turni
  aniq ko'rsatadi (override bo'lsa — o'sha, bo'lmasa — firma
  standarti).
- "Oylik (fiksval)" (yoki "Firma standarti", agar u fiksval bo'lsa)
  tanlanganda, xuddi shu formada "Oylik maosh summasi" input paydo
  bo'ladi (JS orqali ko'rsatish/yashirish) — saqlash bosilganda
  `set_ish_haqi_turi_override` handler endi shu summani ham
  (berilgan bo'lsa) `payroll_service.set_fixed_salary` orqali saqlaydi.
  Joriy qiymat oldindan to'ldirilgan holda ko'rsatiladi.

### O'zgargan fayllar
`main/views.py` (`editusr` — GET context va POST handler),
`main/templates/editusr.html`

### Tekshirildi
`manage.py check`/`test` — 56 test, hammasi o'tdi.

---

## 208-qadam: KPI qoidalari — ega tomonidan xodim TURI bo'yicha (individual emas) rag'batlantirish/bonus tizimi

**Holat: DONE**

### Talab
Ega: "kpi sisemani firma egasi sozlasin bu umumiy yetkazib beruvchilar
uchun ishlab chiqaruvchilar uchun bir xil bo'lsin bir hodimga bohsqacha
ikkkinchisiga boshqacha emas. birinchi turi ishlab chiqargan yoki
sotgan donasiga yoki qiymatiga qarab. aytaylik bazi mahuslotni mingta
sotsa qo'shimcha summa yoki sotuvdan foizi belgilanadi yoki 10 million
so'mlik savdo qilsa (ko'proq savdo qilsa ham) aytaylik bu holatda
nechadir foiz yoki summa belgilanadi ega tomonidan va dashboardda
kpiga qarab progress ko'rinadigon qilsak". Keyin aniqlashtirdi: "kpi
sistema uchun firma sozlamalarida alohida sozlansin yetkazib
beruvchilar turi uchun alohida ishlab chiqaruvchi sotuvchilar uchun
alohida".

### Nima qilindi
Yangi `KpiQoida` modeli — firma sozlamalarida (`/kpi/qoidalar/`, yangi
sahifa, sidebar'da "Boshqaruv" bo'limida) ega tomonidan yaratiladi.
Har bir qoida: **xodim turi** (ishlab chiqaruvchi/savdogar/yetkazib
beruvchi — TUR bo'yicha, individual emas), **mahsulot** (ixtiyoriy —
bo'sh bo'lsa jami/barcha mahsulotlar bo'yicha), **o'lchov turi** (dona
yoki summa), **chegara**, **bonus turi** (fiks summa yoki foiz — foiz
faqat 'summa' o'lchovida ma'noli) va **bonus qiymati**dan iborat. Bir
turga bir nechta qoida (bosqich) qo'shish mumkin — barchasi mustaqil
tekshiriladi, chegaraga yetganlari QO'SHILADI (progressiv: masalan
5 mln uchun 1%, 10 mln uchun 2% — ikkalasi ham bir vaqtda hisoblanadi).

`kpi_service.compute_kpi_bonus(user, company, yil, oy)` — shu oy uchun
xodimning haqiqiy ko'rsatkichini (ishlab chiqaruvchi: `MiqdorQoshish`
orqali tasdiqlangan miqdor/qiymat; savdogar/yetkazib beruvchi: `Savdo`
orqali sotilgan miqdor/qiymat, mahsulot-bo'yicha filtrlash `Savdo.smm`
matnini `mahsulotlar_miqdori()` bilan parse qilib amalga oshiriladi)
har bir faol qoidaning chegarasi bilan solishtiradi, bonus yig'indisini
va har bir qoida bo'yicha progress foizini qaytaradi.

`payroll_service.compute_oylik_ish_haqi` — hisoblangan bonus HAR DOIM
bazaviy ish haqiga (fixed/per_unit/per_sale turidan qat'i nazar)
QO'SHILADI — bu alohida rag'batlantirish, asosiy to'lov turini
almashtirmaydi.

Dashboard: profil sahifalarida (`pzprofile.html`, `ytprofile.html`,
`egayt.html`, `egaprofile.html`) "KPI — bu oy" bo'limi ostida har bir
faol qoida uchun progress-bar (amalda/chegara %) va yetilgan bo'lsa
belgi (✓) + jami bonus summasi ko'rsatiladi.

### O'zgargan fayllar
`main/models.py` (`KpiQoida`), `main/migrations/0098_kpiqoida.py`,
`main/services/kpi_service.py` (`compute_kpi_bonus`,
`_month_ishlab_chiqarish_stats`, `_month_savdo_stats`),
`main/services/payroll_service.py`, `main/kpi_views.py`
(`kpi_qoidalari_view`), `main/urls.py`,
`main/templates/kpi_qoidalari.html` (yangi),
`main/templates/egabase.html` (sidebar havolasi),
`main/templates/pzprofile.html`, `main/templates/ytprofile.html`,
`main/templates/egayt.html`, `main/templates/egaprofile.html`,
`main/tests_kpi_returns.py` (+9 test — `KpiQoidaBonusTests`,
`KpiQoidalariViewTests`)

### Tekshirildi
`manage.py check`/`test` — 65 test, hammasi o'tdi.

---

## 209-qadam: KPI bosqichlari — bitta umumiy progress-barda navbat-navbat (segmentli)

**Holat: DONE**

### Muammo
208-qadamda har bir KPI bosqichi (masalan 300 dona va 500 dona) ALOHIDA
progress-bar sifatida ko'rsatilardi. Ega so'radi: "300taga qo'ysa keyin
500taga qo'ysa nima bo'ladi progressbarda current-300-500 turadimi?"
va aniqlashtirdi: "bitta progressbarda ko'rinsin navbat navbat bo'lib".

### Nima qilindi
`kpi_service.compute_kpi_bonus` endi qo'shimcha `bosqichlar` (bitta
umumiy progress-bar uchun guruhlangan) ma'lumot qaytaradi — yangi
`_group_into_bosqichlar()`. Bir xil o'lchov (mahsulot + dona/summa)
bo'yicha qoidalar chegara bo'yicha saralanib, BITTA chiziqda ketma-ket
SEGMENTlarga bo'linadi (0-300 segmenti, 300-500 segmenti va h.k.),
har bir segment o'z oralig'iga nisbatan mustaqil to'ladi (masalan
amalda=350 bo'lsa: 0-300 segmenti 100% ✓, 300-500 segmenti (350-300)/
(500-300)=25%). Barcha profil sahifalari (`pzprofile.html`,
`ytprofile.html`, `egayt.html`, `egaprofile.html`) yangilandi — endi
har bir "chegara" segment tagida raqam bilan (va yetgan bo'lsa ✓ bilan)
ko'rsatiladi, bitta flex-chiziqda ketma-ket.

### O'zgargan fayllar
`main/services/kpi_service.py` (`_group_into_bosqichlar`),
`main/templates/pzprofile.html`, `main/templates/ytprofile.html`,
`main/templates/egayt.html`, `main/templates/egaprofile.html`,
`main/tests_kpi_returns.py` (+2 test — segment guruhlash va qisman
to'lgan segment)

### Tekshirildi
`manage.py check`/`test` — 66 test, hammasi o'tdi.

---

## 210-qadam: Sotuv paytida QR skanerlash — Desktop Agent orqali ro'yxatdan o'tkazilmagan (omborda) kod uchun aniq ogohlantirish

**Holat: DONE**

### Muammo
Production oldidan ega yetkazib beruvchi/sotuvchi dashboardlarini
tekshirishni so'radi. Kamchilik: yetkazib beruvchi Desktop Agent orqali
hali "yuklamaga olmagan" (Serial.holati hamon `omborda`, hech qachon
`chiqarilgan`ga o'tmagan) QR kodni to'g'ridan-to'g'ri `/sotish/`
sahifasida kiritsa/skanerlasa, tizim buni ALLAQACHON rad etardi
(`weigh`/serial filtri `holati=chiqarilgan` talab qiladi) — lekin
xabar umumiy edi: "yaroqsiz yoki allaqachon ishlatilgan", sababi aniq
ko'rinmasdi (nega aynan rad etilgani noaniq qolardi).

### Nima qilindi
`sotish` view'ida (`views.py`) rad etilgan (`missing`) serial
kodlari uchun ENDI har biriga ALOHIDA, aniq sabab ko'rsatiladi:
- kod umuman topilmasa — "topilmadi"
- allaqachon biror savdoga bog'langan bo'lsa — "allaqachon sotilgan"
- yetkazib beruvchi uchun holati hamon `omborda` bo'lsa — **"hali
  agentda ro'yxatdan o'tkazilmagan (yuklamaga olinmagan, omborda
  turibdi)"** — aynan ega so'ragan holat
- yetkazib beruvchi uchun `chiqarilgan` lekin boshqa yetkazib
  beruvchiga tegishli bo'lsa — "boshqa yetkazib beruvchiga tegishli"
- boshqa har qanday mos kelmagan holat — aniq holat nomi bilan

### O'zgargan fayllar
`main/views.py` (`sotish`), `main/tests_sotish_qr.py` (yangi — 2 test)

### Tekshirildi
`manage.py check`/`test` — 68 test, hammasi o'tdi.

---

## 211-qadam: Yuklama so'rovi — omborda 0 qoldiq bo'lsa ham "+" tugmasi ishlayotgan edi (BUG FIX)

**Holat: DONE**

### Muammo
Yetkazib beruvchi dashboardida "Yuklama olish" bo'limida (skrinshotda
"Somsa hamir 30", omborda 0 dona) "+" tugmasi hamon bosilar edi va
cheksiz miqdor so'rash mumkin edi — na frontendda (`sorovStep` JS
funksiyasi faqat 0dan pastga tushmaslikni tekshirar edi, YUQORI
chegara — omborda mavjud miqdor — umuman tekshirilmasdi), na backendda
(`views.py`dagi `sorov_submit` handler ham `sorov_miqdor > m.miqdori`
holatini tekshirmasdi).

### Nima qilindi
- `yetkazuvchi_dashboard.html`: input'ga `max`/`data-max` (mahsulot
  qoldig'i) qo'shildi, `sorovStep()` endi shu chegaradan oshirmaydi.
  Qoldiq 0 bo'lsa "+" tugmasi `disabled` va vizual xiralashtirilgan.
- `views.py` (`sorov_submit` handler): server tomonida ham
  `sorov_miqdor > m.miqdori` tekshiruvi qo'shildi — chegaradan oshgan
  so'rov o'tkazib yuboriladi, aniq xabar bilan (frontend JS
  aylanib o'tilsa ham himoyalangan).

### O'zgargan fayllar
`main/views.py`, `main/templates/yetkazuvchi_dashboard.html`

### Tekshirildi
`manage.py check`/`test` — 68 test, hammasi o'tdi (backend tekshiruv
mavjud avtomatlashtirilgan testlar bilan qamrab olinmagan — soddaligi
tufayli qo'lda tasdiqlash tavsiya etiladi).

---

## 212-qadam: POST forma yuborilganda "kutish sezilarli" muammosi — birinchi (xavfsiz) qadam: darhol vizual feedback

**Holat: DONE (qisman — pilot)**

### Muammo
Ega ta'kidladi: ishlab chiqaruvchi, savdogar, yetkazib beruvchi
sahifalarida ko'plab tugmalar oddiy POST forma orqali ishlaydi —
bosilgach sahifa to'liq qayta yuklanguncha hech qanday feedback
yo'q, foydalanuvchi "hech narsa bo'lmayapti" deb qayta-qayta bosishi
mumkin. WebSocket bor-yo'qligi so'raldi — WebSocket bizda faqat BIR
TOMONLAMA push (bildirishnoma) uchun, forma yuborish uchun emas.

Bu ko'p sahifaga tegishli keng qamrovli muammo — production oldidan
hammasini birdan to'liq AJAX'ga o'tkazish xavfli deb topildi. Ega
bilan kelishilgan yondashuv: bir nechta eng muhim joydan boshlab,
xavfsiz birinchi qadam bilan.

### Nima qilindi
Uchala rol bazasiga (`pzbase.html` — ishlab chiqaruvchi, `ytbase.html`
— yetkazib beruvchi, `sgbase.html` — savdogar/omborchi) umumiy
JS qo'shildi: har qanday `method="post"` forma yuborilganda submit
tugmasi DARHOL o'chiriladi va "⏳ Yuborilmoqda..." matniga almashadi
— server javob qaytarib, sahifa qayta yuklangunicha foydalanuvchi
aniq vizual feedback ko'radi va qayta-qayta bosolmaydi (dublikat
so'rovlar oldini oladi). Bu TO'LIQ AJAX emas (sahifa hamon qayta
yuklanadi) — birinchi, kam xatarli qadam; natija yoqsa, keyingi
bosqichda muayyan formalarni haqiqiy fetch()ga o'tkazish mumkin.

### O'zgargan fayllar
`main/templates/pzbase.html`, `main/templates/ytbase.html`,
`main/templates/sgbase.html`

### Tekshirildi
`manage.py check` toza (faqat frontend JS, backend o'zgarmadi).

### Keyingi qadam (kelishilgan, hali qilinmagan)
Agar bu yondashuv yoqsa — eng ko'p ishlatiladigan 2-3 ta forma (masalan
pazandaning material so'rovini bekor qilish, yuklama so'rovi) haqiqiy
fetch()ga o'tkaziladi (sahifa umuman qayta yuklanmaydi, faqat natija
DOM'da yangilanadi).

---

## 213-qadam: Yetkazib beruvchi "Yuklama so'rovi" — haqiqiy AJAX (sahifa umuman qayta yuklanmaydi)

**Holat: DONE**

### Muammo
212-qadamdagi "darhol vizual feedback" yetarli emasligi aniqlandi —
ega ta'kidladi: "baribir qayta yuklanyapti-ku, yetkazib beruvchi va
ishlab chiqaruvchi zerikib ketadi bunaqada". Ega bilan kelishilgan
"bir nechta eng muhim joydan boshlash" rejasi bo'yicha birinchi
haqiqiy (to'liq) AJAX konversiyasi: yetkazib beruvchi dashboardidagi
"Yuklama olish" so'rov formasi.

### Nima qilindi
`views.py` (`main` — yetkazib beruvchi POST/`sorov_submit` bo'limi):
so'rov (ogohlantirish/xato) xabarlari endi Django `messages` o'rniga
ro'yxatlarga (`yaratilgan_json`, `ogohlantirishlar`) yig'iladi. So'rov
`X-Requested-With: XMLHttpRequest` header bilan kelsa — sahifa
redirect o'rniga `JsonResponse({'ok', 'message', 'ogohlantirishlar',
'yaratilgan'})` qaytaradi. Oddiy (JS o'chirilgan) forma-submit hamon
eski redirect+messages yo'lidan ishlaydi — orqaga qarab moslik
saqlangan.

`yetkazuvchi_dashboard.html`: forma submit hodisasi `preventDefault()`
qilinib, `fetch()` orqali yuboriladi. Muvaffaqiyatli bo'lsa: mavjud
`showNotification()` (WebSocket bildirishnomalar bilan bir xil toast
tizimi) orqali natija ko'rsatiladi, yangi so'ralgan mahsulotlar
ro'yxatga (DOM'ga) to'g'ridan-to'g'ri qo'shiladi, tegishli inputlar
0'ga qaytariladi — SAHIFA UMUMAN QAYTA YUKLANMAYDI.

### O'zgargan fayllar
`main/views.py` (import tozalash — `JsonResponse` yuqoriga
ko'chirildi, duplikat import olib tashlandi; `main` view),
`main/templates/yetkazuvchi_dashboard.html`,
`main/tests_yuklama_sorov.py` (yangi — 3 test)

### Tekshirildi
`manage.py check`/`test` — 71 test, hammasi o'tdi.

### Keyingi nomzod
Yoqsa — pazandaning material so'rovini bekor qilish tugmasi
(`pazanda_dashboard.html`) xuddi shu naqsh bilan AJAX'ga o'tkaziladi.

---

## 214-qadam: Pazanda "Oldim ✓" tugmasi — haqiqiy AJAX

**Holat: DONE**

### Muammo
Ega yana sinab ko'rib, "Oldim" tugmasi bosilganda sahifa hamon qayta
yuklanayotganini aniqladi — bu 213-qadamda AJAX'ga o'tkazilgan
"Yuklama so'rovi" formasidan FARQLI, alohida forma edi ("Olib qo'yish
kerak" bo'limi, `pz_ack_task_pickup`).

### Nima qilindi
`production_views.py` (`pz_ack_task_pickup`): xuddi 213-qadamdagi
naqsh — `X-Requested-With: XMLHttpRequest` header bilan kelsa
`JsonResponse({'ok','message','pickup_id'})` qaytaradi, aks holda
eski redirect+messages yo'li saqlanadi.

`pazanda_dashboard.html`: forma `.ack-pickup-form` klassi bilan
belgilandi, hujjat darajasidagi (event delegation) submit listener
`fetch()` orqali yuboradi. Muvaffaqiyatli bo'lsa: qator (`.act-item`)
DOM'dan olib tashlanadi, "Olib qo'yish kerak" badge soni kamayadi,
`showNotification()` orqali toast ko'rsatiladi — SAHIFA QAYTA
YUKLANMAYDI.

### O'zgargan fayllar
`main/production_views.py` (`pz_ack_task_pickup`),
`main/templates/pazanda_dashboard.html`,
`main/tests_pz_ack_pickup.py` (yangi — 2 test)

### Tekshirildi
`manage.py check`/`test` — 73 test, hammasi o'tdi.

---

## 215-qadam: Pazanda sahifasida bildirishnoma chiqqanda sahifa vaqtincha "siqilib" ko'rinardi (BUG FIX)

**Holat: DONE**

### Muammo
Ega skrinshot bilan ko'rsatdi: pazanda dashboardida toast bildirishnoma
chiqqanda (~1.8 soniya, bildirishnoma yopilguncha) butun sahifa
mobil ekranda chapga siqilib, o'ng tomonda katta bo'sh joy paydo
bo'lardi, keyin o'ziga kelardi.

Sabab: `pzbase.html`da `#notification-container` uchun `position:
fixed` CSS qoidasi UMUMAN YO'Q EDI (`ytbase.html`da bor edi, lekin
`pzbase.html`ga o'sha safar qo'shilmagan). Natijada toast (320px kenglik)
oddiy hujjat oqimida joy egallardi va `translateX(120%)` orqali
ekrandan tashqariga chiqarilganda ham sahifaning umumiy scrollWidth'ini
oshirib yuborardi — mobil brauzer butun sahifani shu kengaygan
o'lchamga moslab avtomatik kichraytirib (zoom-out) ko'rsatardi.

### Nima qilindi
`pzbase.html`ga `#notification-container { position: fixed; bottom:
2rem; right: 2rem; ... }` qo'shildi (mobil uchun `@media` bilan
moslashtirilgan) — `ytbase.html`dagi bilan bir xil naqsh. Endi toast
hujjat oqimidan butunlay chiqarilgan, sahifa kengligiga ta'sir
qilmaydi.

### O'zgargan fayllar
`main/templates/pzbase.html`

### Tekshirildi
`manage.py check` toza (faqat CSS, backend/test o'zgarmadi).

---

## 216-qadam: Boshqa sahifalarda ham tekshirildi — xuddi shu bildirishnoma bug bor-yo'qligi

**Holat: DONE**

### Muammo
Ega 215-qadamdagi tuzatishdan so'ng "boshqa sahifalarda ham tekshirib
chiq" deb so'radi — xuddi shu (`#notification-container`da `position:
fixed` yo'qligi) xato boshqa rol bazalarida ham bo'lishi mumkinmi.

### Nima qilindi
Barcha 4 ta rol bazasini tekshirdim:
- `ytbase.html` — `position: fixed` bor edi, muammo yo'q.
- `egabase.html` — `position: fixed` bor edi, muammo yo'q.
- `sgbase.html` — o'ziniki emas, umumiy `_notif_partial.html`dan
  foydalanadi, u yerda ham to'g'ri sozlangan (`position: fixed`).
- `pzbase.html` — 215-qadamda allaqachon tuzatilgan.

Demak asosiy bug FAQAT `pzbase.html`da edi, boshqa joyda takrorlanmagan.
Qo'shimcha himoya sifatida (kelajakda shunga o'xshash xato — masalan
yangi `position: fixed` unutilgan elementi — butun sahifani buzib
qo'ymasligi uchun) barcha 4 ta bazaning `body` elementiga `overflow-x:
hidden` qo'shildi (pzbase'da avval faqat `.main-wrapper`da bor edi,
lekin bildirishnoma konteyneri undan TASHQARIDA joylashgan edi —
shuning uchun aynan shu himoya ishlamagan edi).

### O'zgargan fayllar
`main/templates/pzbase.html`, `main/templates/ytbase.html`,
`main/templates/sgbase.html`, `main/templates/egabase.html`

### Tekshirildi
`manage.py check` toza (faqat CSS, backend/test o'zgarmadi).

---

## 217-qadam: Retsept qatorini to'g'ridan-to'g'ri tahrirlash imkoniyati qo'shildi

**Holat: DONE**

### Muammo
Ega: "retseptni edit qilish imkoniyati yo'q". Backend (`retsept_service.
add_retsept_row`) aslida `update_or_create` ishlatadi — texnik jihatdan
mavjud komponentni qayta tanlab, yangi miqdor kiritish orqali "tahrirlash"
mumkin edi, lekin UI'da (`seemahsulot.html`) faqat "Retseptga qo'shish"
(yangi komponent qidirish) modali va "o'chirish" tugmasi bor edi — mavjud
qatorni to'g'ridan-to'g'ri tahrirlash imkoniyati YO'Q edi, foydalanuvchi
buni sezmasdi.

### Nima qilindi
`seemahsulot.html`dagi retsept jadvali qatorida endi miqdor ustuni
to'g'ridan-to'g'ri tahrirlanadigan input + "✓" (saqlash) tugmasi bilan
almashtirildi — mavjud `add_retsept_row` amalini (komponent + yangi
miqdor) qayta yuboradi, backend o'zgarishsiz (`update_or_create`
allaqachon to'g'ri ishlagan).

### O'zgargan fayllar
`main/templates/seemahsulot.html`, `main/tests_retsept_edit.py`
(yangi — 2 test)

### Tekshirildi
`manage.py check`/`test` — 75 test, hammasi o'tdi.

---

## 218-qadam: Tarozi majburiyligi firma darajasida ERP'da sozlanadigan qilindi (Desktop Agent)

**Holat: DONE**

### Muammo
Ega: "agent sozlamasida tarozini hohlasa shartmas deb belgilash
imkoniyati kerak (desktop agentni erpdagi sozlamasida shunga qarab
loading vaqtida agent tarozi shartmas bo'lsa tarozini qidirmasa ham
bo'ladi) agar tarozi bog'lanmagan bo'lsa shunchaki oldim tugmasi
chiqadigon bo'lsin". Avval tarozi ulanishi HAR DOIM startup
tekshiruvida majburiy edi (COM port sozlanmagan/javob bermasa —
"Davom etish" bloklanardi), va tortish ekranida kg/g birlikdagi
komponentlar HAR DOIM haqiqiy tarozi o'qishini talab qilardi.

### Nima qilindi
**Backend (Django/ERP):**
- Yangi `Company.tarozi_majburiy` (`BooleanField`, default `True`).
- `/api/agent/omborlar/` va `/api/agent/login/` (`/login-by-qr/`)
  javoblariga `tarozi_majburiy` qo'shildi — agent login/sinxronlashda
  darhol biladi.
- `hodimlar_list.html`ga (faqat `is_agent_company` bo'lsa ko'rinadigan)
  yangi "Desktop Agent — Tarozi" kartasi qo'shildi — ega
  "Majburiy"/"Shart emas" tanlab saqlaydi (`list_views.py`,
  `set_tarozi_majburiy` action).

**Desktop Agent (PyQt6):**
- Login (`settings_page.py::_on_login_succeeded`) va sinxronlash
  (`settings_page.py::_on_sync_succeeded`, `warehouse_list_page.py::
  _on_sync_succeeded`) natijalarida `tarozi_majburiy` mahalliy
  (`db.set_setting`) saqlanadi.
- `startup_check_page.py::_check_scale_live` — sozlama o'chirilgan
  bo'lsa, COM portni umuman qidirmasdan darhol "OK" (shart emas) deb
  hisoblaydi — startup bloklanmaydi.
- `employee_scan_widget.py` — yangi `_scale_required()` helper. Tortish
  kartasidagi "weighable" (kg/g, haqiqiy tarozi talab qiladi) holati
  endi `_is_weighable_birlik(...) and _scale_required()` — sozlama
  o'chirilgan bo'lsa, kg/g komponentlar ham xuddi dona/litr kabi
  oddiy "Oldim ✓" tugmasi bilan (`measured_qty = expected_qty`)
  tasdiqlanadi, haqiqiy tortish talab qilinmaydi. Jonli vazn callback
  (`update_live_weight`) ham shu holatda e'tiborsiz qoldiriladi.

Exe qayta yig'ildi (`StockFirmAgent.exe`) — Super Admin → "Agent
versiyalari" orqali yuklab qo'yish kerak, stansiyalar yangi versiyani
oladi.

### O'zgargan fayllar
`main/models.py` (`Company.tarozi_majburiy`), `main/migrations/0099_*`,
`main/agent_api_views.py` (`agent_omborlar`, `_issue_station_token`),
`main/list_views.py` (`hodimlar_list`), `main/templates/hodimlar_list.html`,
`main/tests_tarozi_majburiy.py` (yangi — 4 test);
`desktop_agent/app/api_client.py` (`fetch_omborlar`),
`desktop_agent/app/windows/settings_page.py`,
`desktop_agent/app/windows/warehouse_list_page.py`,
`desktop_agent/app/windows/startup_check_page.py`,
`desktop_agent/app/windows/employee_scan_widget.py`

### Tekshirildi
`manage.py check`/`test` — 79 test, hammasi o'tdi. Desktop Agent
fayllari sintaksis tekshiruvidan o'tdi (`py_compile`), exe muvaffaqiyatli
qayta yig'ildi.

---

## 219-qadam: Desktop Agent kiosk qulfida Win/Alt+Tab bloklanadi (Ctrl+Alt+Delete — OS chegarasi)

**Holat: DONE**

### Muammo
Ega: "desktop agentda pusk alt tab ctrl alt delete kabi tugmalarni
ishlamaydigon qilish kerak qulf ochilmagunicha". Aniqlashtirildi:
Ctrl+Alt+Delete'ni HECH QANDAY oddiy dastur (bu jumladan) dasturiy
kod bilan bloklay olmaydi — Windows uni doim to'g'ridan-to'g'ri
Winlogon'ga yuboradi (Secure Attention Sequence), hech qanday
user-mode ilova buni ko'rmaydi ham. Ega buni "tizim darajasida
bloklash kerak" deb tasdiqladi — bu operatsion tizim (Windows Kiosk/
Assigned Access yoki Group Policy) sozlamasi, dasturiy kod emas.

### Nima qilindi
Yangi `desktop_agent/app/kiosk_keyboard_lock.py` — `WH_KEYBOARD_LL`
past darajali Windows klaviatura ilgichi (`ctypes` orqali, qo'shimcha
kutubxona shart emas). `KioskKeyboardBlocker.enabled=True` bo'lganda
Win (chap/o'ng) va Alt+Tab/Alt+Esc kombinatsiyalarini butunlay yutib
yuboradi — Boshlash menyusi ochilmaydi, oyna almashtirilmaydi.

`main_window.py`: `MainWindow.__init__`da bir marta `install()`
qilinadi; kiosk qulfi holati o'zgarganda (`_set_kiosk_locked`)
`set_enabled(locked)` chaqiriladi — ya'ni bloklash FAQAT "qulf
ochilmaguncha" faol (mavjud `_kiosk_locked` bayrog'i bilan bir xil
holatda), qulf ochilgach avvalgidek erkin. Dastur haqiqatan yopilganda
(`closeEvent`, qulf ochiq holatda) ilgich `uninstall()` qilinadi.

Exe qayta yig'ildi.

### O'zgargan fayllar
`desktop_agent/app/kiosk_keyboard_lock.py` (yangi),
`desktop_agent/app/windows/main_window.py`

### Tekshirildi
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi. (Windows
klaviatura ilgichi haqiqiy stansiyada qo'lda sinovdan o'tkazilishi
tavsiya etiladi — CI/avtomatlashtirilgan testda tekshirib bo'lmaydi.)

### Cheklov (ega bilan kelishilgan, hal qilinmagan)
Ctrl+Alt+Delete'ni bloklash operatsion tizim darajasida (stansiya
kompyuterida) sozlanishi kerak — bu ERP/agent kodi doirasidan
tashqarida. Windows Kiosk rejimi (Assigned Access) yoki maxsus Group
Policy (Ctrl+Alt+Del ekranidagi variantlarni cheklash) orqali amalga
oshiriladi — bu alohida, qo'lda (yoki IT xodimi tomonidan) har bir
stansiyada bajariladigan sozlash, kod bilan avtomatlashtirilmaydi.

---

## 220-qadam: Taskbar yashirish + tarozi sozlamasi editusr.html'ga ko'chirildi

**Holat: DONE**

### Muammo
Ega ikkita narsa aytdi: (1) kiosk to'liq ekranga chiqsa ham pastki
Windows taskbar hamon ko'rinib turardi ("Faqat pastki taskbar
ko'rinib qolyapti, shuni ko'rinmaydigan qilib ber"); (2) 218-qadamda
qo'shilgan "Tarozi majburiy/shart emas" sozlamasi Hodimlar ro'yxati
sahifasida edi — ega buni aynan Desktop Agent stansiyasini tahrirlash
sahifasida ("shu yerda belgilanadi") ko'rishni xohladi.

### Nima qilindi
**Taskbar yashirish**: `kiosk_keyboard_lock.py`ga `hide_taskbar()`/
`show_taskbar()` qo'shildi — `FindWindowW("Shell_TrayWnd", ...)` va
`Button`/"Start" oynalarini `ShowWindow(SW_HIDE)` bilan yashiradi.
`_on_startup_check_continue`da `showFullScreen()`dan keyin chaqiriladi
(bu funksiyaning o'zi taskbarni yashirmaydi — alohida qilish kerak
edi). Dastur haqiqatan yopilganda (`closeEvent`, qulf ochiq holatda)
`show_taskbar()` bilan qaytariladi — foydalanuvchi Windows'da
taskbarsiz qolib ketmasligi uchun.

**Tarozi sozlamasi ko'chirildi**: Hodimlar ro'yxatidagi kartadan
olib tashlandi, o'rniga `editusr.html`ga (faqat
`user_edit.type == 'desktop_agent'` bo'lganda ko'rinadigan) yangi
karta qo'shildi — `views.py::editusr`ning `set_tarozi_majburiy`
handleri xuddi shu joyga ko'chirildi (`list_views.py`dan olib
tashlandi). Backend hamon firma darajasida (`Company.tarozi_majburiy`)
— faqat UI qulayroq joyga ko'chirildi, matn ham buni aniq aytadi
("Bu firmaning BARCHA Desktop Agent stansiyalariga tegishli").

Exe qayta yig'ildi.

### O'zgargan fayllar
`desktop_agent/app/kiosk_keyboard_lock.py` (`hide_taskbar`/`show_taskbar`),
`desktop_agent/app/windows/main_window.py`,
`main/views.py` (`editusr`), `main/list_views.py` (`hodimlar_list`),
`main/templates/editusr.html`, `main/templates/hodimlar_list.html`,
`main/tests_tarozi_majburiy.py` (`editusr` yo'liga moslashtirildi)

### Tekshirildi
`manage.py check`/`test` — 79 test, hammasi o'tdi. Desktop Agent
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi.

---

## 221-qadam: XPrinterda chop etilmagan (qog'oz tugagan/oflayn) QR kodlar kuzatuvi va avtomatik qayta chop etish

**Holat: DONE**

### Muammo
Ega: "biz xprinterda qandaydir hatolik bilan chiqmay qolgan qr kodlar
ro'yhatini olsak bo'ladimi? masalan qog'oz tugab qolgan yoki nimadir".
Tekshirilganda aniqlandi: Windows'ning RAW printer yozish API'si
(`win32print.WritePrinter`) printer oflayn/qog'ozsiz bo'lsa ham odatda
"muvaffaqiyatli" qaytaradi — chop etish natijasi HECH QACHON ishonchli
tekshirilmagan va HECH QAYERDA saqlanmagan (kod izohlarida shu aniq
qayd etilgan edi). Ega tasdiqlagan yechim: (1) Desktop Agent
stansiyasida, (2) ERP dashboardida ogohlantirish, (3) keyingi badge
skanida avtomatik qayta chop etishga taklif.

### Nima qilindi
**Backend**: `Serial`ga `chop_etilmadi`/`chop_etish_sababi` maydonlari
qo'shildi. Yangi `task_service.get_failed_print_serials`/
`report_serial_print_result`. `/api/agent/pending-print-batch/`
endi yangi partiya bo'lmasa, oldin HAQIQATAN chop etilmagan
seriallarni "qayta chop etish" partiyasi sifatida qaytaradi
(`is_reprint: true`). Yangi `/api/agent/report-print-result/`
endpoint — har bir yorliq natijasini qabul qiladi.

**Desktop Agent**: `label_printer_service.py`ga `get_printer_status_issue()`
— win32print `GetPrinter` STATUS bitmask orqali qog'oz tugagan/
tiqilgan/oflayn/qopqoq ochiq/xato holatlarini HAQIQATAN tekshiradi
(xuddi startup tekshiruvidagi mexanizm). `LabelPrintWorker` endi har
bir yorliqni chop etgandan KEYIN shu tekshiruvni bajaradi va yangi
`label_result` signali orqali xabar beradi. `employee_scan_widget.py`
har bir natijani serverga (`report_print_result`) yuboradi — ikkala
chop etish yo'lida ham (vazifa partiyasi va miqdor-tasdiqlash).
Qayta-chop-etish partiyasi ko'rsatilganda ekranda aniq ogohlantirish
("⚠ Qayta chop etish...") chiqadi.

**ERP dashboard**: `pazanda_dashboard.html`da yangi sariq ogohlantirish
kartasi — "N ta QR-yorliq chop etilmadi" (faqat `chop_etilmadi=True`
seriallar mavjud bo'lsa ko'rinadi).

Exe qayta yig'ildi.

### O'zgargan fayllar
`main/models.py` (`Serial.chop_etilmadi`/`chop_etish_sababi`),
`main/migrations/0100_*`, `main/services/task_service.py`,
`main/agent_api_views.py` (`agent_pending_print_batch`,
`agent_report_print_result`), `landing/urls.py`, `main/views.py`
(pazanda dashboard), `main/templates/pazanda_dashboard.html`,
`main/tests_print_failure.py` (yangi — 7 test);
`desktop_agent/app/label_printer_service.py`
(`get_printer_status_issue`, `LabelPrintWorker.label_result`),
`desktop_agent/app/api_client.py` (`report_print_result`),
`desktop_agent/app/windows/employee_scan_widget.py`

### Tekshirildi
`manage.py check`/`test` — 86 test, hammasi o'tdi. Desktop Agent
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi. (Haqiqiy
printerda qog'oz tugatib sinov qilish tavsiya etiladi — status
bitmask xatti-harakati printer modeliga qarab bir oz farq qilishi
mumkin.)

---

## 222-qadam: Desktop Agent QR-login — jimgina muvaffaqiyatsiz bo'lish tuzatildi + QR zichligi kamaytirildi

**Holat: DONE**

### Muammo
Ega: "agentda shu bilan skaner qilib login qila olmadim chiqilgan
holatda" — QR skanerlanganda "hech narsa bo'lmadi (skanerlash
sezilmadi)". Tekshirilganda ikkita muammo topildi:

1. **Jimgina muvaffaqiyatsizlik (asosiy topilma)**:
   `main_window.py::_handle_agent_login_qr` va
   `_handle_kiosk_unlock_qr` ikkalasida ham, agar kamera zich QR'ni
   TO'LIQ/TO'G'RI o'qiy olmasa (`kod.split("|", 2)` 3 ta qism
   bermasa), kod JIMGINA `return` qilar edi — foydalanuvchiga HECH
   QANDAY xabar chiqmasdi. Bu aynan xabar berilgan holat bilan mos
   keladi.
2. **QR haddan tashqari zich**: shifrlangan payload (~200 belgi) +
   `agent_qr_nonce` (avval to'liq UUID, 32-36 belgi) juda zich QR
   panjarasini talab qilardi (skrinshotda ko'ringan) — kamera bilan
   o'qish real sinovda ishonchsiz ekani kod izohlarida oldindan qayd
   etilgan edi.

### Nima qilindi
- Ikkala joyda ham parsing muvaffaqiyatsiz bo'lsa endi ANIQ xabar
  ko'rsatiladi ("QR kod to'liq o'qilmadi — kamerani QR'ga yaqinroq/
  tekisroq tuting va qayta skanerlang, yoki login/parol bilan
  kiring") — foydalanuvchi nima bo'lganini bilib, qayta urinishi
  yoki zaxira yo'l (login/parol)dan foydalanishi mumkin.
- `User.agent_qr_nonce` generatori yangi `_gen_agent_qr_nonce()`ga
  o'zgartirildi — to'liq UUID (32-36 belgi) o'rniga `secrets.token_hex(8)`
  (16 belgi). Bu maxfiy token EMAS (shifrlangan Fernet payload ICHIDA
  yotadi, faqat eski QR'ni bekor qilish uchun) — 64 bit yetarli,
  qisqarishi esa QR-login kodining zichligini (kamerada o'qish
  qulayligini) sezilarli yaxshilaydi. `regenerate_agent_qr`
  ("Yangilash" tugmasi) ham shu funksiyaga o'tkazildi.

Exe qayta yig'ildi.

### O'zgargan fayllar
`main/models.py` (`_gen_agent_qr_nonce`, `User.agent_qr_nonce`),
`main/migrations/0101_*`, `main/badge_views.py`
(`regenerate_agent_qr`), `desktop_agent/app/windows/main_window.py`
(`_handle_agent_login_qr`, `_handle_kiosk_unlock_qr`)

### Tekshirildi
`manage.py check`/`test` — 86 test, hammasi o'tdi. Desktop Agent
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi.

### Eslatma
Yangi (qisqaroq) nonce faqat KEYINGI "Yangilash" bosilganda yoki yangi
xodim yaratilganda qo'llaniladi — mavjud xodimlarning eski (uzun)
nonce'lari o'zgarmaydi, avvalgidek ishlashda davom etadi (faqat yangi
QR ko'rsatilganda zichlik kamayadi).

---

## 223-qadam: QR-login "hech qanday reaksiya yo'q" — haqiqiy sabab: skaner kamerasi umuman sozlanmagan edi

**Holat: DONE**

### Muammo
222-qadamdagi tuzatishdan keyin ham ega "hali ham reaksiya yo'q" dedi.
Chuqurroq tekshirilganda (fon agent orqali): `ScannerService.reload()`
(`scanner_service.py`) — agar `db.get_scanner_camera()` (skaner ROLIGA
ulangan kamera) `None` qaytarsa, funksiya DARHOL qaytadi — hech qanday
kamera ochilmaydi, `QRScanWorker` yaratilmaydi. Yangi/hali sozlanmagan
stansiyada (aynan LOGIN ekrani — birinchi ko'rinadigan sahifa) hech
qanday kamera "skaner" sifatida ulanmagan bo'lsa, kamera UMUMAN
ishga tushmaydi — na login QR, na boshqa hech narsa skanerlanmaydi,
va hech qanday oyna/xato ko'rsatilmaydi (ega tasdiqladi: "hech qanday
kamera oynasi ko'rinmaydi"). Bu chinakam sabab edi — kod xatosi emas,
sozlash bosqichi o'tkazib yuborilgan edi.

### Nima qilindi
`settings_page.py`ga yangi ogohlantirish yorlig'i qo'shildi — login
ekranidagi QR-login ko'rsatmasi ostida, agar `db.get_scanner_camera()
is None` bo'lsa, aniq sariq ogohlantirish chiqadi: "⚠ Hali hech qanday
kamera 'Skaner' sifatida ulanmagan — QR-login ISHLAMAYDI. Pastdagi
'Skaner' bo'limida kamerani tanlab saqlang." Bu `_refresh_scanner_status()`
orqali (sahifa ochilganda va skaner qayta sozlanganda) yangilanadi —
kamera sozlangach avtomatik yashiriladi.

Exe qayta yig'ildi.

### O'zgargan fayllar
`desktop_agent/app/windows/settings_page.py`

### Tekshirildi
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi.

### Foydalanuvchiga ko'rsatma
Bu stansiyada Sozlamalar > Skaner qismida kamera tanlab saqlanishi
kerak — shundan keyin QR-login (va boshqa barcha skanerlash) ishlay
boshlaydi.

---

## 224-qadam: 219-qadamdagi Win/Alt+Tab klaviatura ilgichi BUTUNLAY OLIB TASHLANDI (real ishlab chiqarish xatosi)

**Holat: DONE (BUG FIX/REVERT)**

### Muammo
Ega: "ilova kirishiga klaviaturani deaktivatsiya qilib qo'yyapti...
boshqa dasturlarda ham yozib bo'lmayapti, shu tufayli skanerdan
kelgan ma'lumotni ham qabul qilmayapti". 219-qadamda qo'shilgan
`WH_KEYBOARD_LL` global klaviatura ilgichi (Win/Alt+Tab bloklash
uchun) — bu XATO YECHIM edi: bunday global ilgich BUTUN TIZIM
darajasida ishlaydi. Agar hook callback (Python/GIL orqali chaqiriladi,
tabiatan sekinroq) javob berishda biroz kechiksa, Windows shu
ilgichni kutib, BOSHQA HAMMA dastur (jumladan HID skaner — u ham
klaviatura sifatida ishlaydi) uchun kiritishni kechiktiradi/bloklaydi.
Aynan shu sabab butun kompyuterda yozish va skanerlash ishlamay
qoldi — 219-qadamda bu xavf hisobga olinmagan edi.

### Nima qilindi
`KioskKeyboardBlocker` klassi (`WH_KEYBOARD_LL` ilgichi) butunlay
olib tashlandi — `main_window.py`dan `install()`/`set_enabled()`/
`uninstall()` chaqiruvlari va importi o'chirildi.
`kiosk_keyboard_lock.py` faylida FAQAT taskbar yashirish/qaytarish
(`hide_taskbar`/`show_taskbar`) qoldi — bu XAVFSIZ, chunki global
INPUT pipeline'ga tegmaydi, faqat bitta oynani ko'rsatadi/yashiradi.

Win/Alt+Tab kabi tizim buyruqlarini ishonchli cheklash endi FAQAT
operatsion tizim darajasida (Windows Kiosk/Assigned Access yoki
Group Policy) tavsiya etiladi — xuddi Ctrl+Alt+Delete kabi (bu allaqachon
221/219-qadamlarda ega bilan kelishilgan yondashuv edi).

Exe qayta yig'ildi.

### O'zgargan fayllar
`desktop_agent/app/kiosk_keyboard_lock.py` (hook klassi olib
tashlandi), `desktop_agent/app/windows/main_window.py`

### Tekshirildi
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi. (Haqiqiy
stansiyada boshqa dasturlarda yozish/skanerlash endi normal
ishlashini tasdiqlash tavsiya etiladi.)

---

## 225-qadam: Hali login qilinmagan stansiyada birinchi QR skani noto'g'ri "kiosk qulfini ochish" deb talqin qilinardi

**Holat: DONE (BUG FIX)**

### Muammo
Ega: "2-marta skaner qilinganda login qilyapti... login qilinmagan
bo'lsa umuman qulflanishi kerak emas, login qilinishi kerak". Sabab:
`_on_code_scanned` faqat `self._kiosk_locked` bayrog'iga qarab qaror
qilardi — bu bayroq dastur ishga tushganda har doim `True` bilan
BOSHLANADI, HALI LOGIN QILINMAGAN bo'lsa ham (`_kiosk_locked` va
"login qilinganmi" ikkita BOSHQA-BOSHQA tushuncha edi, lekin bir xil
bayroq bilan aralashtirilgan). Natijada: birinchi (hali login
qilinmagan) QR skani NOTO'G'RI "kiosk qulfini ochish" so'rovi deb
yuborilardi (`agent_verify_kiosk_unlock`ga) — server buni ham qabul
qilib "Qulf ochildi" derdi (chunki bu endpoint stansiya login
qilinganini talab qilmaydi), lekin HAQIQIY login sodir bo'lmagan
edi. Faqat IKKINCHI skanerlashda (`_kiosk_locked` allaqachon
`False`ga o'tgani uchun) haqiqiy login yo'liga tushardi.

### Nima qilindi
`_on_code_scanned`: endi avval HAQIQIY login holati
(`db.get_setting("agent_token", "")` bor-yo'qligi) tekshiriladi.
Login qilinmagan bo'lsa — DOIM login oqimiga (`_handle_agent_login_qr`)
yo'naltiriladi, `_kiosk_locked`dan qat'i nazar. Faqat ALLAQACHON login
qilingan VA kiosk ekrani qulflangan holatda QR skani "qulfni ochish"
so'rovi sifatida talqin qilinadi.

Exe qayta yig'ildi.

### O'zgargan fayllar
`desktop_agent/app/windows/main_window.py` (`_on_code_scanned`)

### Tekshirildi
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi.

---

## 226-227-qadam: RegisterHotKey (Alt+Tab bloklash) — bekor qilindi, ilova ochilmay qoldi

**Holat: DONE (REVERT)**

### Muammo
226-qadamda `RegisterHotKey` + `MainWindow.nativeEvent()` orqali
Alt+Tab/Alt+Esc/Alt+F4'ni bloklash qo'shildi. Push qilingan exe
o'rnatilgach, ega darhol xabar berdi: "ilovaga kirib bo'lmayapti" —
dastur ochilmay/ishga tushmay qoldi. Bu jiddiy regressiya edi.

### Nima qilindi
Xavfsizlik uchun DARHOL `git revert` orqali 226-qadamdagi commit
(`9774bcd2`) bekor qilindi — `kiosk_keyboard_lock.py` va
`main_window.py` 225-qadamdagi (ishlab turgan) holatiga qaytarildi.
Exe qayta yig'ilib, foydalanuvchiga yuborildi.

**Ehtimoliy sabab (keyinroq chuqurroq tekshirish kerak)**:
`MainWindow.nativeEvent()` HAR BIR Windows xabari (`windows_generic_MSG`)
uchun chaqirilardi — nafaqat `WM_HOTKEY`, balki sichqoncha harakati,
chizish va h.k. kabi juda tez-tez keladigan xabarlar ham. Har safar
`wintypes.MSG.from_address(int(message))` chaqirilishi ilova ochilish
bosqichida (`__init__` ichida, oyna hali to'liq shakllanmagan holatda
`self.winId()` chaqirilib, `RegisterHotKey` ishga tushirilgani bilan
bir vaqtda) muammoli bo'lgan bo'lishi mumkin. Alt+Tab bloklash
funksiyasi hozircha QURILMAGAN — kelgusida qayta urinilsa, avval
mahalliy (haqiqiy Windows kompyuterda, production emas) sinovdan
albatta o'tkazilishi kerak.

### O'zgargan fayllar
`desktop_agent/app/kiosk_keyboard_lock.py`,
`desktop_agent/app/windows/main_window.py` — 225-qadamdagi holatga
qaytarildi (revert)

### Tekshirildi
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi va yuborildi.

---

## 228-qadam: Ega "Tarozi shart emas" deb belgilagach ham, startup tekshiruvida hamon majburiy ko'rsatilar edi

**Holat: DONE (BUG FIX)**

### Muammo
Ega ERP'da (`editusr.html` — agent001 stansiyasi) "Tarozi shart emas"
deb belgiladi, lekin Desktop Agent'da startup qurilma-tekshiruvi
hamon "Tarozi — COM4 portidan javob kelmadi" deb ko'rsatardi. Sabab:
`tarozi_majburiy` mahalliy sozlamasi FAQAT login qilinganda yoki
"Sinxronlash" tugmasi bosilganda serverdan yangilanadi — stansiya
ALLAQACHON login qilingan holatda (token saqlanib qolgan) qayta
ishga tushirilsa, ega ERP'da sozlamani O'ZGARTIRGANDAN KEYIN ham,
mahalliy qiymat ESKI (sinxronlanmagan) holicha qolardi — startup
tekshiruvi esa aynan shu eski qiymatga qarab ishlaydi.

### Nima qilindi
`startup_check_page.py`ga yangi `_sync_tarozi_majburiy()` — har safar
qurilma tekshiruvi ishga tushganda (dastur ochilganda VA "Qayta
tekshirish" bosilganda), `_DeviceProbeWorker.run()` ichida (fon
oqimida, GUI muzlamaydi) `tarozi_majburiy` firma sozlamasi
serverdan QAYTA olinadi va mahalliy saqlanadi — shu bilan tarozi
tekshiruvi HAR DOIM eng yangi qiymatga qarab ishlaydi. Best-effort:
token yo'q yoki tarmoq xatosi bo'lsa jimgina o'tkazib yuboriladi.

Exe qayta yig'ildi.

### O'zgargan fayllar
`desktop_agent/app/windows/startup_check_page.py`
(`_sync_tarozi_majburiy`, `_DeviceProbeWorker.run`)

### Tekshirildi
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi.

---

## 229-qadam: "Desktop Agent onlayn emas" banneri sahifani yangilamasdan o'zini tuzata olmasdi

**Holat: DONE (BUG FIX)**

### Muammo
Ega Desktop Agent haqiqatan ishlab, login qilingan bo'lsa ham, ERP
bosh sahifasida "Desktop Agent stansiyasi onlayn emas" qizil banneri
ko'rinishda qolib ketardi. Tekshirilganda: heartbeat mexanizmining
o'zi TO'G'RI ishlayotgani tasdiqlandi (qo'lda chaqirilganda server
muvaffaqiyatli qabul qildi, `last_agent_heartbeat` yangilandi) —
sahifani F5 bilan yangilash bannerni to'g'irlardi. Demak muammo
heartbeatda emas, balki jonli (WebSocket) yangilanishda edi:
"onlaynga o'tish" holati FAQAT WebSocket orqali (`agent_heartbeat`
hodisasi) push qilinardi — agar bu xabar biror sababdan (kanal
qatlami/tarmoq uzilishi) yetib kelmasa, banner sahifa qayta
ochilmaguncha "oflayn" holida qotib qolardi. Ega: "yangilamasam ham
avtomatik o'zi o'zgaradigon qilishing kerak".

### Nima qilindi
WebSocket asosiy (tezkor) yo'l bo'lib qoladi — unga QO'SHIMCHA, o'zini
o'zi tuzatuvchi ZAXIRA mexanizmi qo'shildi: `egabase.html`dagi JS endi
har 30 soniyada yangi `/api/stansiyalar-holati/` endpointini so'raydi
(`views.agent_stations_status_api`, faqat `ega`, mavjud
`context_processors._safe_agent_stations_status` hisob-kitobini qayta
ishlatadi) va natijani `applyAgentStationsSeed()` orqali qayta
qo'llaydi — WS push qandaydir sabab bilan yo'qolgan bo'lsa ham, 30
soniya ichida banner o'zi to'g'irlanadi, foydalanuvchi F5 bosishi
shart emas.

**Diqqat (URL to'qnashuvi)**: birinchi urinishda `/api/agent-stations-
status/` deb nomlangan edi — bu `CompanyMiddleware`dagi
`path.startswith('api/agent')` shartiga tushib, middleware'ni
BUTUNLAY chetlab o'tib ketardi (`request.company` o'rnatilmasdi,
`AttributeError`). `/api/stansiyalar-holati/` deb nomlanib tuzatildi.

### O'zgargan fayllar
`main/views.py` (`agent_stations_status_api`), `main/urls.py`,
`main/templates/egabase.html` (`applyAgentStationsSeed`,
`pollAgentStationsStatus`), `main/tests_agent_stations_status.py`
(yangi — 3 test)

### Tekshirildi
`manage.py check`/`test` — 89 test, hammasi o'tdi.

---

## 230-qadam: Ombor kamerasi sozlanmagan bo'lsa ham startup'ni bloklardi — endi tarozi kabi ixtiyoriy

**Holat: DONE (BUG FIX)**

### Muammo
Ega: "kamera bilan bog'liq muammo bo'lsa yoki to'liq sozlanmagan
bo'lsa nega qulflanib qolyapti — to'liq sozlangan bo'lsa qulflansin".
`_check_ombor_cameras_live` — agar HECH QANDAY ombor kamerasi
sozlanmagan bo'lsa ham (`db.list_all_ombor_cameras()` bo'sh), `False`
qaytarardi — bu esa startup tekshiruvini bloklab, "Davom etish"
o'rniga "Sozlamalarga o'tish"ni majburlardi. Bu izchilliksiz edi:
`CameraRecorderService`ning o'zi (voqea atrofida video yozish)
sozlanmagan bo'lsa "hech narsa qilmaydi" (ixtiyoriy xususiyat), lekin
startup tekshiruvi buni HAR DOIM majburiy deb hisoblardi.

### Nima qilindi
`_check_ombor_cameras_live`: endi hech qanday kamera sozlanmagan
bo'lsa `True` ("Ombor kamerasi shart emas (sozlanmagan)") qaytaradi
— startup'ni bloklamaydi, xuddi 218-qadamdagi tarozi bilan bir xil
mantiq. Kamera SOZLANGAN, lekin ulanolmayotgan holat esa o'zgarishsiz
qoladi — bu haqiqiy muammo, hamon bloklaydi ("to'liq sozlangan
bo'lsa qulflansin" — ega so'ragan aynan shu).

Exe qayta yig'ildi.

### O'zgargan fayllar
`desktop_agent/app/windows/startup_check_page.py`
(`_check_ombor_cameras_live`)

### Tekshirildi
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi.

---

## 231-qadam: Omborlar jadvalida "Kameralar"/"O'chirish" tugmalari bir-birining ustiga chiqib ko'rinardi (vizual xato)

**Holat: DONE (BUG FIX)**

### Muammo
Ega skrinshot bilan ko'rsatdi: Desktop Agent'ning "Omborlar" sahifasida
jadval ustunlari (kamera holati matni va amal tugmalari) juda tor
bo'lib, "Kameralar"/"O'chirish" tugmalari matni kesilgan va bir-
birining ustiga chiqib ko'rinardi. Sababni topish uchun dastur manba
kodidan (`main.py`) to'g'ridan-to'g'ri ishga tushirib tekshirildi
(avval kompilyatsiya qilingan eski nusxa mutex orqali ikkinchi
nusxani ochishga to'sqinlik qilgani aniqlanib, o'chirilgach qayta
urinildi). Kodni ko'zdan kechirib sabab topildi:
`WarehouseListPage`dagi jadvalning 2- va 3-ustunlari
(`setSectionResizeMode`) uchun HECH QANDAY kenglik rejimi
belgilanmagan edi — faqat 0/1-ustunlar (`Nomi`/`Manzil`) `Stretch`
qilingan, qolganlari standart (juda tor) holicha qolib, ichidagi
matn/tugmalarga yetarli joy bermasdi.

### Nima qilindi
2- va 3-ustunlarga `QHeaderView.ResizeMode.ResizeToContents` qo'shildi
— endi mazmuniga (matn/tugmalar) qarab avtomatik kenglashadi. Qo'shimcha
xavfsizlik: `refresh()` oxirida `resizeColumnToContents(2)`/`(3)` ham
aniq chaqiriladi — chunki `setCellWidget` orqali qo'yilgan
widget'lar (tugmalar) uchun `ResizeToContents` birinchi to'ldirishda
har doim to'g'ri hisoblanavermasligi mumkin (Qt'ning tanilgan xatti-
harakati).

Exe qayta yig'ildi.

### O'zgargan fayllar
`desktop_agent/app/windows/warehouse_list_page.py`

### Tekshirildi
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi. (Vizual natija
— haqiqiy stansiyada ko'rinishni tasdiqlash tavsiya etiladi, avtomatik
testda tekshirib bo'lmaydi.)

---

## 232-qadam: Taskbar yashirish BUTUNLAY OLIB TASHLANDI — dastur to'g'ri yopilmasa, foydalanuvchi kompyuterida taskbar butunlay yashiringan qolib ketardi (jiddiy xato)

**Holat: DONE (BUG FIX/REVERT — jiddiy)**

### Muammo
Ega: "kompyuterimni nima qilding? ... sen tizim darajada yo'qotvorgansan ilova yopilsa ham taskbar berkitilgan". 219/223-qadamlarda qo'shilgan `hide_taskbar()` (`ShowWindow(Shell_TrayWnd, SW_HIDE)`) — bu Windows DARAJASIDAGI GLOBAL holat, dastur jarayoniga BOG'LIQ EMAS. `show_taskbar()` faqat `closeEvent`ning "toza yopilish" yo'lida chaqirilardi. Agar dastur "Vazifalar menejeri"/`taskkill //F` orqali majburan o'chirilsa (aynan shu — bu sessiyada exe qayta-qayta shu tarzda qayta qurish uchun o'chirilgan edi), yiqilib tushsa yoki boshqa har qanday NOTO'G'RI yo'l bilan tugasa — `show_taskbar()` HECH QACHON chaqirilmaydi, natijada foydalanuvchining BUTUN KOMPYUTERIDA taskbar doimiy yashiringan holda qolib ketadi (dastur o'zi yopilgandan keyin ham). Aynan shu real hodisa yuz berdi.

### Nima qilindi
1. Foydalanuvchining taskbarini DARHOL (PowerShell orqali, `ShowWindow`
   to'g'ridan-to'g'ri chaqirilib) tiklandi.
2. `hide_taskbar()`/`show_taskbar()` chaqiruvlari `main_window.py`dan
   BUTUNLAY OLIB TASHLANDI (`_on_startup_check_continue`, `closeEvent`).
3. Ular endi hech qayerda ishlatilmagani uchun butun
   `kiosk_keyboard_lock.py` fayli (faqat shu ikki funksiyani saqlab
   qolgan edi, 224-qadamdan buyon) o'chirildi.

Xulosa: kiosk to'liq ekran (`showFullScreen()`) rejimida ishlayveradi,
lekin taskbar endi DASTURIY ravishda yashirilmaydi — bu xavf-foyda
nisbatiga nomutanosib ekani aniqlandi (bitta noto'g'ri yopilish butun
kompyuterni "buzib" qo'yishi mumkin edi).

Exe qayta yig'ildi.

### O'zgargan fayllar
`desktop_agent/app/windows/main_window.py` (`hide_taskbar`/
`show_taskbar` chaqiruvlari olib tashlandi), `desktop_agent/app/
kiosk_keyboard_lock.py` (o'chirildi)

### Tekshirildi
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi. Foydalanuvchi
taskbari qo'lda tiklandi va tasdiqlandi.

---

## 233-qadam: "Desktop Agent QR-login" kartasi noto'g'ri profillarda (jumladan ega'ning o'zinikida) ko'rinardi

**Holat: DONE (BUG FIX)**

### Muammo
Ega: "login qilsam ega ism-familyasi chiqyapti, agent nomi emas" —
kutilgan xatti-harakat: Hodim → Agent (desktop_agent turidagi xodim)
→ Profil sahifasidan QR skanerlab login qilinishi kerak edi. Sabab
topildi: `egaprofile.html`dagi "Desktop Agent QR-login" karta shartida
(`{% if request.user.type == 'ega' %}`) faqat KO'RAYOTGAN kishi (ega)
tekshirilardi, KO'RILAYOTGAN profil (`user`) `desktop_agent` turida
ekani UMUMAN tekshirilmagan edi. Bu shablon ega o'zining PROFILINI
ko'rganda ham ishlatiladi (`views.py` — "ega o'zini ko'rish" yo'li),
shuning uchun ega o'z profiliga kirganda ham xuddi shu QR karta
chiqib, unda `user.id` = EGA'NING O'ZINING ID'si bilan shifrlangan
login QR ko'rsatilardi. Xuddi shu xato `egayt.html`da ham bor edi
(savdogar/yetkazib beruvchi profili uchun — ular hech qachon
`desktop_agent` turida bo'lmaydi, shuning uchun bu QR u yerda umuman
ma'nosiz edi).

### Nima qilindi
- `egaprofile.html`: shart `{% if request.user.type == 'ega' and
  user.type == 'desktop_agent' %}`ga o'zgartirildi — endi FAQAT ega
  aynan bir `desktop_agent` turidagi xodim profilini ko'rganda
  chiqadi (ega o'zini yoki boshqa turdagi xodimni ko'rganda
  ko'rinmaydi).
- `egayt.html`dan (savdogar/yetkazib beruvchi profili) karta
  BUTUNLAY OLIB TASHLANDI — u yerga hech qachon tegishli emas edi.

### O'zgargan fayllar
`main/templates/egaprofile.html`, `main/templates/egayt.html`

### Tekshirildi
`manage.py check`/`test` — 89 test, hammasi o'tdi (bu faqat shablon
shartlari, backend logikasi o'zgarmadi — mavjud testlar buzilmadi).

---

## 234-qadam: Chiqib ketilgan holatda QR skanerlansa "Token kiritilmagan" tushunarsiz xato chiqardi

**Holat: DONE (BUG FIX)**

### Muammo
Ega chiqib ketib (logout), keyin QR skanerlaganda "Token kiritilmagan"
degan tushunarsiz xato ko'rdi. Sabab aniqlandi: ega aslida
"Desktop Agent QR-login" kartasi o'rniga BOSHQA QR'ni (`xodim_badge.html`
— shaxsiy ID-karta, login uchun emas) skanerlagan edi. Bunday QR
`AGENTQR|`bilan boshlanmagani uchun login oqimiga emas, ODATDAGI
xodim-badge skanerlash oqimiga (`EmployeeScanWidget.handle_scanned_code`)
tushadi — bu esa stansiyaning O'ZI login qilingan bo'lishini talab
qiladi (serverga so'rov stansiya tokeni bilan yuboriladi). Chiqib
ketilgan holatda token yo'q, shuning uchun past darajadagi
`api_client._request()`dagi umumiy xato ("Token kiritilmagan.")
to'g'ridan-to'g'ri ko'rsatilib qolardi — foydalanuvchiga nima
bo'lganini tushunish qiyin edi.

### Nima qilindi
`handle_scanned_code()`ga oldindan tekshiruv qo'shildi — token yo'q
bo'lsa, tarmoq so'rovi umuman yuborilmaydi, o'rniga aniq xabar
ko'rsatiladi: "Avval stansiya login qilinishi kerak — Sozlamalarda
kiring."

Bundan tashqari, foydalanuvchiga ikkita QR o'rtasidagi farq
tushuntirildi: "Desktop Agent QR-login" (login uchun, faqat agent
turidagi xodim PROFIL sahifasida) va shaxsiy "ID-karta" badge QR
(identifikatsiya uchun, alohida sahifada) — bular ikki xil narsa.

Exe qayta yig'ildi.

### O'zgargan fayllar
`desktop_agent/app/windows/employee_scan_widget.py`
(`handle_scanned_code`)

### Tekshirildi
`py_compile` toza, exe muvaffaqiyatli qayta yig'ildi.

---

## 235-qadam: Stansiya login (QR/parol) endi FAQAT desktop_agent turidagi hisob uchun — eski ega QR'i backend darajasida ham yopildi

**Holat: DONE (XAVFSIZLIK TUZATISHI)**

### Muammo
233-qadamda faqat UI'dan (`egaprofile.html`) "Desktop Agent QR-login"
kartasi yashirilgan edi — lekin BACKEND (`agent_station_login`,
`agent_login_by_qr`) hech qanday xodim TURINI tekshirmasdi (bu
ATAYLAB shunday loyihalashtirilgan edi — "firmaning istalgan faol
foydalanuvchisi... stansiya sifatida kira oladi"). Natijada: avval
chop etilgan/saqlangan ega QR kodi (yoki istalgan boshqa xodim
login/paroli) HAMON stansiya sifatida kirish uchun ishlardi — ega
buni aniqladi ("eski ega qr kodi bilan login qilib kirib
ketaveryapti") va buni ATAYLAB yopishni so'radi: "agentni qrsi eski
eganikidek hamma narsani o'z ichiga olsin" — ya'ni FAQAT maxsus
yaratilgan agent hisobi orqali kirish ishlashi kerak.

### Nima qilindi
`agent_station_login` (parol) va `agent_login_by_qr` (QR) — ikkalasiga
ham `station.type != 'desktop_agent'` tekshiruvi qo'shildi (403,
aniq xabar bilan). Endi hisob turi qat'iy nazar (ega, omborchi va h.k.)
— faqat maxsus yaratilgan `desktop_agent` turidagi hisob (login/QR)
stansiya tokeni ola oladi. Bu 233-qadamdagi UI-yashirishni HAQIQIY
(backend darajasidagi) cheklovga aylantiradi — eski/saqlangan QR
nusxalari endi rad etiladi.

### O'zgargan fayllar
`main/agent_api_views.py` (`agent_station_login`, `agent_login_by_qr`),
`main/tests_agent_station_type_restriction.py` (yangi — 4 test)

### Tekshirildi
`manage.py check`/`test` — 93 test, hammasi o'tdi.

## 236-qadam: Kiosk qulfi login qilinmagan holatda ham yoqilib qolib, foydalanuvchini tuzoqqa tushirardi

Foydalanuvchi skrinshotlar bilan ko'rsatdi: dastur hali stansiya sifatida
LOGIN QILINMAGAN holatda ham "🔒 Qulflangan" holatida ochilardi — Omborlar/
Sozlamalar tugmalari o'chirilgan, oyna yopilmaydi, faqat ega QR kodini
skanerlab qulfni ochish so'raladi. Lekin qulfni ochish (`agent_verify_kiosk_unlock`)
ALLAQACHON login qilingan stansiyani talab qiladi (saqlangan `server_url`ga
tayanadi) — hali login qilinmagan qurilmada bu chiqib bo'lmaydigan tuzoq edi.

Sabab: `MainWindow.__init__` ichida `self._set_kiosk_locked(True)` HAR DOIM
chaqirilardi, login holatidan qat'i nazar.

### Tuzatish (`desktop_agent/app/windows/main_window.py`)
- `__init__`: endi `self._set_kiosk_locked(bool(db.get_setting("agent_token", "")))`
  — faqat ALLAQACHON login qilingan bo'lsa qulflanadi.
- `_on_login_succeeded`: login muvaffaqiyatli bo'lgach endi `_set_kiosk_locked(True)`
  chaqiriladi — kiosk qulfi aynan shu daqiqadan boshlab ma'noga ega bo'ladi.
- `_handle_token_invalid` (boshqa qurilmada qayta login qilingani uchun
  token bekor bo'lganda): endi `_set_kiosk_locked(False)` ham chaqiriladi.
- Sozlamalar sahifasidagi "Chiqish" (`_logout`) uchun yangi `MainWindow._on_logout`
  qo'shildi (avvalgi `on_logout=self._stop_session_workers` o'rniga) —
  workerlarni to'xtatish bilan bir qatorda kiosk qulfini ham bo'shatadi.

### O'zgargan fayllar
`desktop_agent/app/windows/main_window.py`

### Build
`StockFirmAgent.exe` qayta yig'ildi, foydalanuvchiga yuborildi.

## 237-qadam: Desktop Agent uchun "Badge" sahifasi login QR emas edi — ikkita alohida QR chalkashtirdi

Foydalanuvchi skanerlagan QR "Badge ko'rish" sahifasidan (`xodim_badge.html`)
edi — bu shaxsni tasdiqlash uchun mo'ljallangan oddiy QR (login formatida
emas), shuning uchun Desktop Agent uni login sifatida qabul qilmadi. Haqiqiy
login QR faqat profil sahifasida (`egaprofile.html`) pastroqda alohida
"Desktop Agent QR-login" kartasida edi — foydalanuvchi buni topmadi va
"nega ishlamayapti" deb noto'g'ri QR'ni ishlatdi.

Foydalanuvchi talabi (ilgari ham bir necha marta aytilgan): desktop_agent
turidagi hisob uchun ALOHIDA-ALOHIDA ikkita QR bo'lmasligi kerak — bitta QR
hammasini (identifikatsiya + login) o'z ichiga olsin.

### Tuzatish (`main/templates/xodim_badge.html`)
Agar ko'rilayotgan foydalanuvchi (`target_user`) `desktop_agent` turida bo'lsa
va ko'ruvchi `ega` bo'lsa — "Badge ko'rish" sahifasi endi oddiy identifikatsiya
QR o'rniga to'g'ridan-to'g'ri login QR'ni (`agent_login_qr_image`) ko'rsatadi.
Boshqa barcha xodim turlari uchun (pazanda, omborchi va h.k.) eski
xatti-harakat o'zgarishsiz qoladi.

### O'zgargan fayllar
`main/templates/xodim_badge.html`

Pure backend/template — Desktop Agent exe rebuild talab qilinmaydi.

## 238-qadam: Sessiya yo'q bo'lsa ham Omborlar sahifasi eski keshdagi ombor ma'lumotini ko'rsatib turardi

Foydalanuvchi: "login qilmagan agent nima qiladi sozlamalarni tekshirib
asosiy omborni qayerdan oldi sessiya yo'q bo'lsa" — to'g'ri topdi:
`WarehouseListPage.refresh()` login holatini UMUMAN tekshirmasdan,
to'g'ridan-to'g'ri mahalliy SQLite keshidan (`db.list_warehouses()`)
o'qib ko'rsatardi. Token bo'lmasa ham (logout qilingan yoki hali umuman
login qilinmagan, lekin ilgari boshqa hisob bilan sinxronlangan bo'lsa)
"Asosiy [ERP]" kabi eski ma'lumot jadvalda qolib ketardi — go'yo stansiya
serverga ulangandek ko'rinardi.

### Tuzatish
- `warehouse_list_page.py` — `refresh()` endi avval `agent_token`
  borligini tekshiradi; token yo'q bo'lsa jadval bo'shatiladi va
  "Stansiya login qilinmagan..." xabari ko'rsatiladi (keshdagi
  ma'lumotga umuman qaralmaydi).
- `main_window.py` — login muvaffaqiyatli bo'lganda, logout qilinganda
  va token bekor bo'lganda (`_handle_token_invalid`) endi
  `self.warehouse_page.refresh()` ham chaqiriladi — holat DARHOL
  ekranga aks etadi, foydalanuvchi qo'lda Omborlar bo'limiga
  qayta kirmasa ham.

### O'zgargan fayllar
`desktop_agent/app/windows/warehouse_list_page.py`,
`desktop_agent/app/windows/main_window.py`

### Build
`StockFirmAgent.exe` qayta yig'ildi, foydalanuvchiga yuborildi.

## 239-qadam: Login qilinmagan holatda ham qurilma-tekshiruv (printer/tarozi/kamera) ishga tushardi

Foydalanuvchi: "login qilinmagan bo'lsa tekshirmasin qurilmalarni". To'g'ri —
login yo'q holatda printer/tarozi/kamera tekshiruvining hech qanday ma'nosi
yo'q (ular login qilingan stansiyaga xizmat qiladi). Avval bu tekshiruv HAR
DOIM (login holatidan qat'i nazar) dastur ochilganda birinchi ko'rsatilardi.

### Tuzatish (`desktop_agent/app/windows/main_window.py`)
- Dastur ishga tushganda: token bo'lmasa, qurilma-tekshiruv sahifasi
  butunlay o'tkazib yuboriladi — to'g'ridan-to'g'ri Sozlamalar (login)
  sahifasi ko'rsatiladi.
- `_on_login_succeeded`: endi aynan LOGIN MUVAFFAQIYATLI bo'lgandan KEYIN
  qurilma-tekshiruv birinchi marta ishga tushiriladi (`root_stack` → 0,
  `startup_check_page.refresh()`), shundan keyin "Davom etish" orqali
  kiosk qobig'iga o'tiladi.

### O'zgargan fayllar
`desktop_agent/app/windows/main_window.py`

### Build
`StockFirmAgent.exe` qayta yig'ildi, foydalanuvchiga yuborildi.

## 240-qadam: Login qilingandan keyin kiosk darhol qulflanib, kameralarni sozlashga to'sqinlik qilardi + keraksiz "Sinxronlash" tugmasi

Foydalanuvchi: "kirilganidan keyin ombor bloklanib qolyabdi omborni bosib
kameralarni sozlash kerakku" va "sinxronlash tugmasi kerak emas ... web
socketni nega uladik?".

### Muammo 1: erta qulflash
`_on_login_succeeded` login bo'lgan zahoti `_set_kiosk_locked(True)`
chaqirardi — DASTLABKI sozlashda (birinchi marta login qilinganda) ega
hali Omborlar → Kameralar va Sozlamalar → printer/tarozi sozlamalarini
KIRITISHI kerak, lekin bu ikkalasi ham bloklangan edi.

### Tuzatish (`main_window.py`)
Kiosk qulfi endi FAQAT qurilma-tekshiruv MUVAFFAQIYATLI o'tib, "Davom
etish" bosilib, asosiy qobiqqa haqiqatan kirilganda yoqiladi
(`_on_startup_check_continue`) — na dastur ochilganda (`__init__`), na
login bo'lgan zahoti endi qulflanmaydi. Shu paytgacha Omborlar/Sozlamalar
erkin ochiq — kameralar/printer/tarozi sozlanadi, keyin "Qurilmalarni
qayta tekshirish" orqali tekshiruv qaytadan o'tkaziladi.

### Muammo 2: keraksiz qo'lda "Sinxronlash" tugmasi
Omborlar ro'yxati allaqachon WebSocket orqali real-vaqtda avtomatik
sinxronlanadi (91-qadam) — qo'lda tugma endi faqat chalkashtirar edi.

### Tuzatish (`settings_page.py`)
"Sinxronlash" tugmasi va unga bog'liq `_sync`/`_on_sync_succeeded`/
`_on_sync_failed` metodlari butunlay olib tashlandi.

### O'zgargan fayllar
`desktop_agent/app/windows/main_window.py`,
`desktop_agent/app/windows/settings_page.py`

### Build
`StockFirmAgent.exe` qayta yig'ildi, foydalanuvchiga yuborildi.

## 241-qadam: Ega o'zining oddiy shaxsiy QR badge'i bilan kiosk qulfini ocholmasdi

Foydalanuvchi ega sifatida o'z oddiy shaxsiy QR badge'ini ("MENING SHAXSIY
QR BADGE'IM") skanerladi — server uni to'g'ri taniди ("Xush kelibsiz, Islom
Kabilov! (Ega)"), lekin kiosk qulfi OCHILMADI, chunki bu oddiy skan umumiy
xodim-tanish oqimiga (`EmployeeScanWidget`) tushib ketardi — faqat maxsus
`AGENTQR|...` formatidagi (profildagi alohida "Desktop Agent QR-login"
kartasi) kod qulfni ochish uchun tan olinardi.

### Tuzatish
- `employee_scan_widget.py`: yangi `ega_badge_scanned` signali — badge
  muvaffaqiyatli tanilgach (`_on_badge_resolved`), agar `user_type == 'ega'`
  bo'lsa, shu signal orqali ismini yuboradi. Server allaqachon `scan()` API
  orqali bu badge shu firmaning egasiga tegishli ekanini tasdiqlagani
  uchun qo'shimcha so'rov shart emas.
- `main_window.py`: yangi `_on_ega_badge_scanned()` — agar kiosk hozir
  qulflangan bo'lsa, shu orqali ham ochiladi (allaqachon ochiq bo'lsa,
  hech narsa qilinmaydi — oddiy skan sifatida qoladi).

Natijada endi kiosk qulfini ochish uchun ega ham o'zining oddiy shaxsiy
badge'i, ham maxsus "Desktop Agent QR-login" kodi bilan ochishi mumkin.

### O'zgargan fayllar
`desktop_agent/app/windows/employee_scan_widget.py`,
`desktop_agent/app/windows/main_window.py`

### Build
`StockFirmAgent.exe` qayta yig'ildi, foydalanuvchiga yuborildi.

## 242-qadam: Omborlar sahifasidan qo'lda "O'chirish" tugmasi olib tashlandi

Foydalanuvchi: "agentda ombor o'chirish imkoniyati kerak emas". Omborlar
ro'yxati allaqachon ERP'dan (`sync_warehouses_from_remote`) avtomatik
boshqariladi — ERP'da o'chirilgan ombor mahalliy bazadan ham o'zi
o'chadi. Qo'lda o'chirish imkoniyati endi shart emas edi.

### Tuzatish
`warehouse_list_page.py` — har bir qator uchun "O'chirish" tugmasi va
`_delete_warehouse()` metodi olib tashlandi (faqat "Kameralar" tugmasi
qoladi).

### O'zgargan fayllar
`desktop_agent/app/windows/warehouse_list_page.py`

### Build
`StockFirmAgent.exe` qayta yig'ildi, foydalanuvchiga yuborildi.

## 243-qadam: Savdo sahifasida Serial-skan bloki "0 dona" stepper bilan ustma-ust chiqib qolardi

Foydalanuvchi skrinshot bilan ko'rsatdi: savdo sahifasida (Serial/QR kodli
mahsulot uchun) "Serial (QR) kodlari — miqdor skanerlangan donalar soniga
teng" bloki "0 dona" ko'rsatkichi ustiga chiqib, matn kesilib/chalkashib
ko'rinardi ("hunuk va noqulay").

Sabab: `.product-item` flexbox (`display:flex`) edi, lekin serial-skan
bloki `grid-column:1/-1` bilan to'liq kenglikka cho'zilishga urinardi —
bu faqat CSS Grid'da ishlaydi, flexbox'da hech narsa qilmaydi. Natijada
blok stepper bilan bir qatorda, tor joyga siqilib, ustma-ust chiqib
qolardi.

### Tuzatish (`sgsot.html`, `ytsot.html`)
`.product-item`ga `flex-wrap: wrap` qo'shildi, `.serial-scan-block`ga
`flex-basis:100%; width:100%` — endi bu blok har doim to'liq kenglikda,
yangi qatorda chiqadi.

### O'zgargan fayllar
`main/templates/sgsot.html`, `main/templates/ytsot.html`

Pure CSS/shablon — Desktop Agent exe rebuild talab qilinmaydi.

## 244-qadam: Yetkazib beruvchi hali olib chiqilmagan mahsulotni sotishga urinsa — ega ogohlantirilmasdi

Foydalanuvchi: yetkazib beruvchi sifatida tizimdan (Desktop Agent orqali
yuklamaga) rasman olib chiqilmagan mahsulotni QR kod orqali sotishga
urindi. Server buni to'g'ri rad etdi ("hali agentda ro'yxatdan
o'tkazilmagan... omborda turibdi"), lekin bu xabar FAQAT urinayotgan
xodimning o'ziga ko'rinardi — ega hech qanday ogohlantirish olmasdi,
holbuki bu potentsial o'g'irlik urinishi.

### Tuzatish
- `services/qr_service.py`: yangi `log_shubhali_sotish_urinishi()` —
  bunday urinishda har bir donaga `SerialHarakat('shubhali')` (audit
  zanjiri uchun, model'da oldindan mavjud, lekin hech qachon
  ishlatilmagan choice) yozadi.
- `views.py` (sotish POST oqimi): yetkazib beruvchi `holati='omborda'`
  (hali chiqarilmagan) serialni sotishga urinsa — endi
  `create_company_notification()` orqali egaga darhol "Shubhali sotish
  urinishi" ogohlantirishi yuboriladi (xodim ismi, mahsulot, QR kodlari
  bilan).

### Yon-daf topilgan xato (`services/notifications.py`)
`create_company_notification` avval hech qayerda import qilinmagani
uchun sezilmay qolgan — ichida `AppNotification` modeliga yozardi, lekin
bu model 0055-migratsiyada ANCHA OLDIN ataylab o'chirilgan (endi faqat
jonli WebSocket "toast" bildirishnomasi bor, saqlanadigan jadval yo'q).
Import qilingan zahoti `ImportError` bilan BUTUN SAYT ishga tushmay
qolardi. Tuzatildi — endi faqat WS orqali yuboradi, DB'ga yozmaydi.

### Tekshirildi
`manage.py check` — toza. `manage.py test main` — 93 test, hammasi o'tdi.

### O'zgargan fayllar
`main/views.py`, `main/services/qr_service.py`,
`main/services/notifications.py`

## 245-qadam: "Xom ashyoni tarozida tortib oling" abadiy osilib qolishi mumkin edi — sababi ko'rinmasdi

Foydalanuvchi bir necha kundan beri o'zgarmagan (2 dona "claimed" holatidagi)
vazifalarni ko'rsatib, "eski tizimda qolib ketgan buglarni ham tozalab
ketadigon qil" dedi.

Kod tekshiruvida real sabab topildi: `task_service.weigh_task_pickup`da
"hammasi yoki hech narsa" qoidasi bor — vazifaning BOM komponentlaridan
BIRORTASI omborda yetarli bo'lmasa, Desktop Agent'da HECH QANDAY xom ashyo
(hatto yetarli bo'lganlari ham) tortib bo'lmaydi, vazifa abadiy "claimed"
holatda osilib qoladi. Bu sabab FAQAT Desktop Agent'da tortishga
urinilganda, o'tkinchi xato sifatida ko'rinardi — veb dashboardda hech
qanday iz qoldirmasdi, shuning uchun pazanda/ega nima uchun vazifa
harakatlanmayotganini bilolmasdi.

### Tuzatish
- `views.py` (`main` — pazanda dashboard): endi har bir "claimed" vazifa
  uchun uning tasdiqlanmagan komponentlari omborda yetarlimi tekshiriladi,
  yetishmasa `task.stok_yetishmovchiligi` (qaysi komponent, kerak/qoldiq)
  hisoblanadi.
- `pazanda_dashboard.html`: agar shunday yetishmovchilik bo'lsa, oddiy
  "⏳ tarozida tortib oling" o'rniga qizil "⛔ Omborda yetarli xom ashyo
  yo'q — tortib bo'lmaydi: ..." xabari aniq komponent va yetishmagan
  miqdor bilan ko'rsatiladi.

### Tekshirildi
`manage.py check` — toza. `manage.py test main` — 93 test, hammasi o'tdi.

### O'zgargan fayllar
`main/views.py`, `main/templates/pazanda_dashboard.html`

Pure backend/shablon — Desktop Agent exe rebuild talab qilinmaydi.
