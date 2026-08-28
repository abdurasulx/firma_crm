# StockFirm Desktop Agent

Omborga o'rnatiladigan mahalliy PyQt6 **kiosk** dastur — xodim badge/QR
kartasini skanerlab o'zini tasdiqlaydi, shu sessiya davomida ishlab
chiqarish, yuklama olish, xom ashyo tortish/qabul qilish va QR yorliq
chop etish amallarini bajaradi. Ombor kameralarini (USB/RTSP) sozlash
ham shu yerda.

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

1. **Login** — stansiya CRM'da "Hodimlar → Yangi hodim → Desktop Agent"
   orqali yaratilgan o'z shaxsiy login/paroli bilan kiradi (bir firma
   bir nechta stansiyani alohida boshqarishi mumkin). Login qilingandan
   keyin **kiosk qulfi** yoqiladi (Qt darajasida — faqat shu oynaning
   ichida sichqoncha/klaviaturani bloklaydi, OS'ga yoki tashqi
   skaner-klaviatura ilgichiga tegmaydi).
2. **Badge/QR skanerlash** — xodim shaxsiy QR (badge) kartasini
   ko'rsatib o'zini tasdiqlaydi, avtomatik davomat (kirish/chiqish)
   belgilanadi, sessiya boshlanadi (~60–120 soniya, har harakatda
   uzayadi). Rolga qarab sessiya ichida:
   - **Ishlab chiqaruvchi** — xom ashyo so'rovlari ("Oldim ✓" bilan
     tasdiqlash), tarozida tortish, vazifa QR'ini skanerlab band
     qilish, "Ish bitdi" bosilgach QR/Serial yorliqlarni chop etish
     va har birini jismonan yopishtirib qayta skanerlash.
   - **Yetkazib beruvchi/savdogar** — "Yuklama" (yuk olish): dashboardda
     so'ralgan mahsulotlarning Serial QR kodlarini skanerlab savatga
     yig'adi, hammasi to'lganda avtomatik yakunlanadi.
3. **Omborlar** — CRM'dagi `Ombor` ro'yxati va har biriga biriktirilgan
   kamera (USB avtomatik aniqlanadi / RTSP manzil + login-parol) —
   voqea atrofida (skanerlash, tortish, miqdor qo'shish) video yozish
   uchun.
4. **QR yorliq chop etish** — TSPL termal printer orqali, tanlangan
   qog'oz o'lchamiga (kenglik/balandlik) mos hujayra o'lchami avtomatik
   hisoblanadi (kichik qog'ozda QR kesilib qolmasligi uchun).

Telefon orqali (Desktop Agentsiz) muqobil variant ham bor: yetkazib
beruvchi mobil brauzerda QR-kodli mahsulotni kamera bilan skanerlab
yuklama olishi mumkin — bunda fizik nazoratni stansiya o'rniga **GPS
100 metr radiusi** ta'minlaydi (`safiya.stockfirm.uz` dashboardida).

## Fayl tuzilishi

```
desktop_agent/
  main.py                            - kirish nuqtasi
  requirements.txt                   - runtime kutubxonalar
  requirements-build.txt             - faqat .exe yig'ish uchun (PyInstaller)
  StockFirmAgent.spec                - PyInstaller build konfiguratsiyasi
  app/
    db.py                            - mahalliy SQLite (sozlamalar, agent token)
    api_client.py                    - CRM REST API bilan aloqa (login, scan, yuklama, tortish)
    label_printer_service.py         - TSPL QR yorliq generatsiya va RAW chop etish
    camera_recorder_service.py       - ombor kamerasi orqali voqea-yozuv
    windows/
      main_window.py                 - asosiy oyna, kiosk qulfi, navigatsiya
      employee_scan_widget.py        - badge/QR skanerlash va BARCHA sessiya oqimlari
                                        (xom ashyo, tortish, vazifa, yuklama, chop etish)
      startup_check_page.py          - ishga tushishda kamera/printer/tarozi tekshiruvi
      warehouse_list_page.py         - omborlar ro'yxati
      warehouse_cameras_dialog.py    - kamera sozlash (USB/RTSP + preview)
      settings_page.py               - CRM bilan bog'lanish (login)
```
