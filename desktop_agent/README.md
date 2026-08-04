# StockFirm Desktop Agent

Ombor(lar)ga ulangan kameralarni (USB yoki RTSP), skaner oldidagi
web-kamerani sozlash va CRM bilan bog'lanish uchun mahalliy PyQt6
desktop dastur.

## O'rnatish (ishga tushirish uchun)

```
cd desktop_agent
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Build (.exe yig'ish uchun)

Build faqat vaqti-vaqti bilan kerak bo'lgani uchun bu kutubxonalar
alohida faylda — kundalik ishga tushirish uchun ular shart emas:

```
pip install -r requirements.txt -r requirements-build.txt
pyinstaller --noconfirm --onefile --windowed --name StockFirmAgent main.py
```

Natija: `dist/StockFirmAgent.exe`.

## Funksiyalar

1. **Omborlar** — CRM'dagi haqiqiy `Ombor` ro'yxati bilan sinxronlanadi
   (Sozlamalar sahifasida "Sinxronlash"). Har bir omborga kamera
   biriktiriladi:
   - **USB** — kompyuterga ulangan kameralar avtomatik aniqlanadi va
     ro'yxatdan tanlanadi (jonli ko'rinish bilan tekshiriladi).
   - **RTSP** — IP-kamera manzili (URL) + login/parol kiritiladi,
     "Ulanishni tekshirish" tugmasi bilan jonli oqim tekshiriladi.
2. **Skaner** — QR/shtrix-kod skaneri oldidagi alohida web-kamera:
   xodim shaxsiy QR (badge) kartasini ko'rsatib o'zini tasdiqlaydi —
   "stansiya sessiyasi" boshlanadi (60 soniya), shu vaqt ichida uning
   kutilayotgan xom ashyo so'rovi ko'rsatiladi va "Qabul qildim" tugmasi
   bilan tasdiqlanadi.
3. **Sozlamalar** — CRM bilan bog'lanish: har bir stansiya CRM'da
   "Hodimlar > Yangi hodim qo'shish > Desktop Agent" orqali yaratilgan
   o'z shaxsiy login/paroli bilan kiradi (bitta firma bir nechta
   stansiyani alohida-alohida boshqarishi mumkin).

## Fayl tuzilishi

```
desktop_agent/
  main.py                          - kirish nuqtasi
  requirements.txt                 - runtime kutubxonalar
  requirements-build.txt           - faqat .exe yig'ish uchun (PyInstaller)
  app/
    db.py                          - mahalliy SQLite (omborlar, kameralar, sozlamalar)
    api_client.py                  - CRM REST API bilan aloqa (login, sinxronlash, badge-scan)
    camera_utils.py                - USB device aniqlash, RTSP ulanish, QR skanerlash, preview
    windows/
      main_window.py                - asosiy oyna (sidebar: Omborlar / Skaner / Sozlamalar)
      warehouse_list_page.py         - omborlar ro'yxati sahifasi
      warehouse_form_dialog.py       - ombor qo'shish/tahrirlash dialogi
      camera_config_dialog.py        - kamera sozlash dialogi (USB/RTSP + preview)
      scanner_page.py                - skaner ishga tushirish, stansiya sessiyasi, material so'rovlari
      settings_page.py               - CRM bilan bog'lanish (login/sinxronlash)
```
