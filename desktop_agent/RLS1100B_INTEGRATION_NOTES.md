# RLS1100B — Integration Research Notes (LAN tarozi)

> Bu **rasmiy SDK/hujjat emas** — Rongta'dan aniq protokol hujjati hali
> topilmagan holda, real qurilmani tekshirib to'plangan xulosalar. Kelgusi
> ishni shu yerdan davom ettirish uchun yozilgan.

## 1. Qurilma

- Model: RLS1100B (Rongta Technology) — o'z ichiga label printer + tarozi
  birlashtirilgan.
- Aloqa: Ethernet (TCP/IP) va RS232 (ikkalasi ham qo'llab-quvvatlanadi,
  hozircha faqat Ethernet tekshirilgan).
- Sinovda ishlatilgan IP: `192.168.1.87` (statik, LAN ichida).

## 2. Aniqlangan (real tekshiruv orqali)

- Qurilma tarmoqda **jonli** (ping javob beradi, TTL=64 — embedded
  Linux'ga o'xshaydi).
- **Ochiq TCP portlar: 5001, 5002, 5100** (1-10000 oralig'ida to'liq
  skanerlash orqali topilgan — `rls1100b_probe.py`ga qarang).
- Bu portlar **doimiy oqim (continuous streaming) emas** — ulanib
  kutilganda hech narsa yubormaydi (6 soniyagacha sinalgan).
- Umumiy sinov so'rovlariga (ENQ 0x05, oddiy ASCII "W\r\n", STX/ETX
  ramka va h.k. — `rls1100b_probe.py`dagi `PROBES` ro'yxati) **hech
  qanday javob qaytmadi**. Demak protokol maxsus (proprietary) formatli
  paket talab qiladi — vendor hujjatisiz taxmin bilan ochib bo'lmadi.

## 3. Sinab ko'rilgan, natija bermagan yo'llar

- Rongta rasmiy sayti (`rongtatech.com`)dagi va manualslib/scribd kabi
  uchinchi tomon sahifalardagi "RLS1000 based on TCP/IP protocol
  interface specification" hujjatini avtomatik olishga urinildi — bu
  saytlarning barchasi avtomatik so'rovlarni bloklaydi (odam brauzerda
  ochsa ishlaydi).
- Foydalanuvchi saytdan yuklagan SDK (`thermal-printer-windows-sdk-1.zip`)
  tekshirildi — bu **faqat printer** (ESC/POS, `POSDLL.dll`) uchun,
  vazn o'qish bilan aloqasi yo'q (DLL eksport qilingan funksiyalar:
  `POS_PrintBitmap`, `POS_CutPaper`, `POS_SetBarcode` va h.k. — vaznga
  tegishli funksiya yo'q).
- Tarozi bilan birga keladigan PC dasturi (Wireshark bilan trafik
  yozib olish uchun) mavjud emas/topilmadi.

## 4. Integratsiya arxitekturasi (reja, hali qurilmagan)

```
RLS1100B tarozi
      │  TCP (port hali aniq emas — 5001/5002/5100dan biri)
      ▼
Desktop Agent (Python, PyQt6) — yangi scale_service.py
      │  mavjud _ApiCallWorker naqshi orqali fon oqimida
      ▼
CRM backend (agent_weigh_material_request / agent_weigh_task_pickup)
      │  allaqachon mavjud, real vaznni measured_qty sifatida qabul qiladi
      ▼
StockFirm Dashboard
```

**Muhim**: CRM tomoni (backend, `agent_weigh_material_request`,
`agent_weigh_task_pickup`) allaqachon "qo'lda kiritilgan `measured_qty`"
qabul qilishga tayyor — real tarozi ulanganda faqat Desktop Agent
tomonida `weigh_input.setText(...)`ni qo'lda emas, tarozidan kelgan
qiymat bilan avtomatik to'ldirish kifoya. Backend/protokol o'zgarishi
shart emas.

## 5. Keyingi qadamlar (protokol aniqlanguncha)

1. **Eng ishonchli**: Rongta qo'llab-quvvatlashiga (`service-07@rongtatech.com`)
   yozib, "RLS1100B TCP/IP vazn o'qish protokoli" hujjatini so'rash —
   ochiq portlarni (5001/5002/5100) ham aytish, ular tezroq javob
   topishga yordam beradi.
2. Agar Rongta javob bermasa — RS232 (serial) chiqishini sinab ko'rish:
   ko'p arzon xitoy tarozi indikatorlari serial orqali sodda,
   standart ("Toledo", "NCI" kabi) uzluksiz oqim beradi — buni
   USB-seriya adapter bilan o'qib, formatni ko'rish TCP'dan ancha oson.
3. Agar boshqa PC dasturi (hatto boshqa tarozi modelidan) topilsa —
   Wireshark bilan trafikni yozib, haqiqiy baytlarni ko'rish eng tez yo'l.

## 6. Diagnostika skripti

`rls1100b_probe.py` (shu papkada, `desktop_agent/rls1100b_probe.py`) —
portlarni skanerlaydi (`scan_ports()`) va umumiy protokol namunalarini
sinaydi (`probe_all()`), har bir javobni hex+matn ko'rinishida chiqaradi.
Yangi taxminlarni sinash uchun `PROBES` lug'atiga qo'shish kifoya.
Ishlatish: `python rls1100b_probe.py` (IP kerak bo'lsa fayl boshidan
o'zgartiring).
