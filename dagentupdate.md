# Desktop Agent Update — Tizimning hozirgi holati va yangi yo'nalish

> Sana: 2026-07-30. Bu hujjat AI-agent (yoki yangi dasturchi) loyihaga kirishganda
> Desktop Agent bilan bog'liq **hozirgi holatni** to'liq tushunishi va **yangi
> o'zgarishlar** qaysi yo'nalishda ketayotganini bilishi uchun tayyorlangan.
> Asosiy manbalar: `crm/main/agent_api_views.py`, `crm/main/models.py`,
> `desktop_agent/`, `steps.md`, `StockFirm_ERP_Vision.md`, `UPDATENEWVERSION.md`.

---

## 1. Katta rasm — ikki xil ish uslubi

Tizim bitta kod bazasida **ikki rejimda** ishlaydi. Rejim firma darajasida
`Company.custom_desktop_agent_stations` maydoni bilan aniqlanadi:

| | **Agentsiz firma** (`stations == 0`) | **Agentli firma** (`stations > 0`) |
|---|---|---|
| So'rov tasdiqlash | Web-dashboardda (omborchi/ega qo'lda bosadi) | Desktop Agent'da QR skanerlash orqali |
| Omborchi roli | Ishlatiladi | **Kerak emas — umuman ishlatilmaydi** |
| Fizik nazorat | Yo'q (ishonchga asoslangan) | Tarozi, skaner, kamera — fizik hozirlik tasdiqlanadi |
| Narx | Tarif bo'yicha | + $60/oy har bir stansiya uchun (`DESKTOP_AGENT_UNIT_PRICE`) |

Kod ichida rejim tekshiruvi namunasi — `views.addmiqdor` (~`views.py:1984`):
agentli firmada "miqdor qo'shish" darhol tasdiqlanmaydi, ishlab chiqaruvchi
Desktop Agent'ga borib badge skanerlab tasdiqlashi kerak; agentsiz firmada
eski oqim (darhol tasdiqlash) o'zgarishsiz qoladi.

---

## 2. Mahsulot ikki tur — distributor va ishlab chiqarish

`Mahsulot` modeli (`models.py:262`) allaqachon ikki o'qda bo'linadi:

1. **`mahsulot_turi`** (faqat `warehouse_type='finished'` uchun ma'noli):
   - `ishlab_chiqariladigan` — retsept (BOM, `MahsulotRetsept`) asosida
     ishlab chiqariladi; tannarx retseptdan hisoblanadi.
   - `distributor` — tayyor sotib olinadi; `baza_tannarx` = kirim narxi.
2. **`warehouse_type`**:
   - `finished` — tayyor mahsulotlar ombori (sotuvga chiqadigan).
   - `semi_finished` — ombor mahsulotlari; ular o'z navbatida `ombor_turi`
     bilan `xom_ashyo` / `yarim_tayyor`ga bo'linadi.

Tannarx zanjiri: `baza_tannarx` (kirim yoki retsept) + `MahsulotQoshimchaXarajat`
(miqdor yoki foiz) + `amortizatsiya_foizi` → `tannarx` (avtomatik, qo'lda
tahrirlanmaydi).

**Holat:** ishlab chiqarish oqimi (retsept, material so'rovi, tasdiqlash,
serial/QR, tannarx snapshot) yaxshi ishlab turibdi. Distributor oqimi hozircha
faqat model darajasida — **kirim (qabul qilish) oqimi Desktop Agent'ga hali
ulangani yo'q** (pastdagi "Keyingi qadamlar"ga qarang).

---

## 3. Desktop Agent — nima u va qanday ishlaydi

`desktop_agent/` — PyQt6 asosidagi mahalliy Windows dastur
(`pyinstaller` bilan `StockFirmAgent.exe`ga yig'iladi). Ulanadigan qurilmalar:

- **Skaner web-kamerasi** — QR/shtrix-kodlarni o'qiydi (`scanner_service.py`).
- **Ombor kameralari** (USB yoki RTSP, har omborga biriktiriladi) — video
  audit uchun (`camera_recorder_service.py`, `warehouse_cameras_dialog.py`).
- **Tarozi** — hozircha qiymat qo'lda kiritiladi, kelgusida avtomatik
  (`MATERIAL_WEIGH_TOLERANCE_PERCENT = 2%`, min 0.05).
- **XPrinter** — Serial QR yorliqlarini TSPL orqali to'g'ridan-to'g'ri chop
  etadi (`label_printer_service.py`); sozlanmagan bo'lsa brauzer print sahifasi
  (`agent_miqdor_print_page`) ishlatiladi.

**Asosiy g'oya:** stansiya bir marta ishga tushirilgach **klaviatura va
sichqonchasiz** ishlatiladi — barcha interaksiya QR skanerlash orqali.

### 3.1 Autentifikatsiya (ikki qatlam)

1. **Stansiya tokeni** — `/api/agent/login/` (`agent_station_login`):
   subdomain + login/parol → shaxsiy `User.token` (har loginda yangilanadi).
   Firmaning istalgan faol hisobi kira oladi. Eski umumiy
   `Company.desktop_agent_token` orqaga moslik uchun saqlangan.
   Stansiya soni `custom_desktop_agent_stations` bilan cheklanadi
   (`_desktop_agent_slots_left`, `views.py:1560`).
2. **Xodim sessiyasi** — xodim o'z **badge QR** kartasini (`XodimBadge.kod`)
   skanerga ko'rsatadi → server imzolangan qisqa muddatli `session_token`
   qaytaradi (`signing.dumps`, 90 soniya; agent tomonda sessiya 60 soniya).
   Keyingi barcha amal-endpointlar `user_id`ni mijozdan olmaydi — faqat shu
   tokendan chiqaradi (UPDATENEWVERSION.md №4 xavfsizlik tuzatishi bajarilgan).

### 3.2 Real-time holat

- **Heartbeat**: agent har ~25 soniyada `/api/agent/heartbeat/` chaqiradi →
  `User.last_agent_heartbeat`; dashboard `is_agent_online` (90s chegara)
  bo'yicha stansiyani onlayn/oflayn ko'rsatadi.
- **WebSocket**: `agent_socket_service.py` — server `ombor_changed` kabi
  hodisalarni yuboradi, agent jim resinxronlaydi; server tomonda
  `_send_ws_notification` bilan dashboard ham xabardor qilinadi.
- Middleware `api/agent/` yo'llarini subdomain/sessiya tekshiruvidan chetlab
  o'tkazadi (`middleware.py:21`) — agent istalgan hostdan ishlay oladi.

---

## 4. Hozirgacha qurilgan QR oqimlari (API bilan)

Barcha endpointlar: `crm/main/agent_api_views.py`.

### 4.1 Universal skanerlash — `GET /api/agent/scan/`
Skanerlangan kod turini server o'zi aniqlaydi:
- `XodimBadge.kod` → `type='badge'` (xodim ma'lumoti + `session_token`).
- `ProductionMaterialRequest.kod` → `type='material_request'` (o'qish uchun).
- Mos kelmasa — 404.

### 4.2 Davomat (Reception) — `POST /api/agent/attendance/`
Badge skanerlanganda avtomatik: oxirgi hodisaga qarab kirish/chiqish yoziladi
(`XodimDavomat`). Kun davomida bir necha marta kirish-chiqish tabiiy ishlaydi.

### 4.3 Xom ashyo (material) so'rovi oqimi — ishlab chiqaruvchi
1. Ishlab chiqaruvchi dashboardda so'rov yuboradi (`ProductionMaterialRequest`,
   status=`waiting`, har so'rovga unikal `kod` — QR chop etib paketga
   yopishtiriladi).
2. Agentda badge skanerlaydi → `GET /api/agent/material-requests/` FIFO navbat.
3. `POST .../acknowledge/` — "qabul qildim" (faqat `acknowledged_at`, status
   o'zgarmaydi).
4. `POST .../weigh/` — **tarozi tekshiruvi**: o'lchangan miqdor normadan ±2%
   (min 0.05) ichida bo'lsa so'rov **avtomatik tasdiqlanadi** — zaxira
   kamayadi, `StockHistory(RAW_APPROVED)` yoziladi, dashboardga WS xabar.
   **Bu qadam omborchining web'dagi qo'lda tasdiqlashini butunlay almashtiradi.**

### 4.4 Miqdor qo'shish (ishlab chiqarilgan mahsulot topshirish)
1. Ishlab chiqaruvchi dashboardda `MiqdorQoshish` yaratadi — agentli firmada
   `tasdiqlangan=False` bo'lib qoladi (agentsizda darhol tasdiqlanadi).
2. Agentda badge → `GET /api/agent/miqdor-requests/` → `POST .../approve/` —
   mavjud `approve_miqdor_qoshish_service()` chaqiriladi (zaxira oshirish,
   BOM/norma tekshiruvi, jarima/ish haqi hisobi, tannarx snapshot,
   `serial_granularity`ga qarab Serial/QR generatsiya).
3. Javobda `serials` ro'yxati — agent XPrinter'da har dona/partiya uchun QR
   yorliq chop etadi (yoki `print_url` orqali brauzerdan).

### 4.5 Yuklama (yetkazib beruvchi yuk olishi)
1. Yetkazib beruvchi badge skanerlab yuklama sessiyasini boshlaydi.
2. Har jismoniy donaning Serial QR'ini skanerlaydi —
   `POST /api/agent/scan-delivery-serial/` (faqat `serial_granularity='unit'`
   va `holati='omborda'` seriallar qabul qilinadi); savat agent tomonda.
3. `POST /api/agent/finalize-yuklama/` — savatdagi har mahsulot uchun
   `YuklamaSorov` yaratiladi va `approve_yuklama_sorov_service()` bilan darhol
   tasdiqlanadi. Savat elementida `serial_ids` ham yuboriladi — **aynan
   skanerlangan donalar** `chiqarilgan` deb belgilanadi (`yetkazib_beruvchi` va
   `chiqarilgan_at` bilan); `serial_ids` bo'lmasa (web oqimi) FIFO ishlaydi.

### 4.6 Video audit
Har omborga kamera biriktiriladi; hodisa atrofida (oldin/keyin) yozuv olinadi
(`camera_recorder_service.py`) — Smart Factory vision moduli.

---

## 5. Bog'liq modellar xaritasi (tez ma'lumot)

| Model | Vazifasi |
|---|---|
| `User.token`, `last_agent_heartbeat`, `type='desktop_agent'` | Stansiya hisobi va onlayn holati |
| `Company.custom_desktop_agent_stations` | Agentli/agentsiz rejim kaliti + billing |
| `XodimBadge` | Xodim shaxsiy QR (badge) — sessiya boshlash |
| `XodimDavomat` | Kirish/chiqish hodisalari (Reception) |
| `ProductionMaterialRequest.kod` | Xom ashyo so'rovi QR |
| `MiqdorQoshish` + `Serial` | Ishlab chiqarish partiyasi + dona/partiya QR |
| `Serial.holati` (omborda/chiqarilgan/sotilgan) | QR bo'yicha dona kuzatuvi |
| `Serial.yetkazib_beruvchi`, `chiqarilgan_at` | Donani omboradan kim/qachon olib chiqqani |
| `SerialHarakat` | Dona bo'yicha to'liq hayot tarixi (yaratildi → chiqarildi → sotildi → qaytarildi) |
| `StockHistory` | Barcha zaxira harakatlari auditi |
| `Mahsulot.mahsulot_turi` | distributor / ishlab_chiqariladigan bo'linishi |
| `Mahsulot.serial_granularity` | none / batch / unit QR siyosati |

---

## 6. Maqsadli holat (vision) va hali qilinmagan ishlar

Maqsad: **agentli firmada omborchi butunlay yo'q** — barcha so'rovlar
dashboardda yuboriladi, tasdiqlash esa faqat Desktop Agent'da QR ko'rsatish
orqali bo'ladi. Hozirgi holat bilan solishtirganda qolgan bo'shliqlar:

1. **Distributor kirim oqimi** — distributor mahsulot omborga qabul qilinishi
   (kirim narxi/tannarx bilan) hozircha faqat web'da; agent orqali "QR bilan
   qabul qilish" oqimi yo'q. Agent bergan QR (yoki mavjud QR ko'rsatish) orqali
   mahsulot qo'shish qurilishi kerak.
2. **Sotuvchi (savdogar) oqimi agentda yo'q** — vision bo'yicha sotuvchi ham
   yetkazib beruvchi kabi o'z QR'i + mahsulot QR'ini skanerlab yuk olishi
   kerak; hozir faqat `YetkazibBeruvchi` tekshiriladi
   (`agent_scan_delivery_serial` sotuvchini rad etadi).
3. **Yuklamada batch/serial'siz mahsulotlar** — dona QR (`unit`) bo'lmagan
   mahsulotlar uchun agentda yuklash yo'li hozircha yo'q (faqat web).
4. **Tarozi haqiqiy integratsiyasi** — hozir qiymat qo'lda kiritiladi;
   COM/USB tarozidan avtomatik o'qish rejalashtirilgan (tolerans shunga qarab
   qayta ko'rib chiqiladi).
5. **So'rov rad etish (rejected) agentda yo'q** — norma tashqarisida faqat
   "qayta o'lchang" qaytadi; rad etish/eskalatsiya oqimi web'da qolgan.
6. **Yuklama tasdig'i hozir "o'zi so'rab o'zi tasdiqlaydi"** — kelgusida
   agentli firmada yuklama ham fizik skanerlashsiz o'tmasligi ta'minlanishi
   kerak (web-formadan agentli firmada yuklamani cheklash masalasi ochiq).

---

## 7. AI-agent uchun ish qoidalari (shu modul ustida ishlaganda)

- Rejim tekshiruvi doim `company.custom_desktop_agent_stations > 0` orqali —
  yangi oqim qo'shganda agentsiz firmalarning eski xatti-harakati
  **o'zgarishsiz qolishi shart**.
- Amal-endpointlarda `user_id`ni hech qachon mijozdan olmaslik — faqat
  `_user_id_from_session_token()` (badge sessiyasi) orqali.
- Zaxira o'zgarishlari faqat mavjud servislar orqali
  (`approve_miqdor_qoshish_service`, `approve_yuklama_sorov_service`) —
  `select_for_update` + `StockHistory` yozuvi majburiy.
- Har muvaffaqiyatli amalda dashboardga `_send_ws_notification` yuborish
  (xato bo'lsa jim yutish — `try/except` mavjud namunaga qarang).
- Kod izohlari va xabarlar o'zbek tilida; qadamlar tarixi `steps.md`da
  yuritiladi.
