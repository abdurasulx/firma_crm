# StockFirm ERP Vision

## Maqsad

StockFirm --- distributor va ishlab chiqaruvchilar uchun modulli ERP.

## Rollar

-   Admin
-   Omborchi
-   Ishlab chiqaruvchi
-   Yetkazib beruvchi (PWA)

## Modullar

### Core ERP

-   Mahsulot
-   Ombor
-   Kirim tannarxi (omborga kirayotgan mahsulot/xom ashyo tannarxi yozib olinadi)
-   Sotuv
-   Hisobot

### Manufacturing Pro

-   Xom ashyo
-   Yarim tayyor mahsulot
-   Multi-level BOM
-   Ishlab chiqarish daraxti
-   Batch tracking
-   Brak nazorati

### Smart Factory (Premium)

-   QR asosida tasdiqlash
-   Desktop Agent
-   Kamera (2 ta)
-   Tarozi integratsiyasi
-   XPrinter
-   Video audit (hodisadan oldin/keyin yozuv)
-   Avtomatik ombor harakati

### Sales

-   PWA
-   Offline ishlash
-   Internet qaytganda sinxronlash
-   GPS tekshiruvi
-   Magazin QR kodi
-   Vozvrat

### HR

-   KPI
-   Ish haqi
-   Bonus/Jarima

### Finance

-   Qo'shimcha xarajatlar
-   Amortizatsiya
-   Tannarx

## Ishlab chiqarish modeli

Item turlari: - RAW (Xom ashyo) - SEMI (Yarim tayyor) - FINISHED (Tayyor
mahsulot)

Qoidalar: - Yarim tayyor = Xom ashyo + Yarim tayyor - Tayyor mahsulot =
Yarim tayyor + Xom ashyo - Tayyor mahsulot -\> Tayyor mahsulot
bog'lanishi taqiqlanadi. - Retseptlar rekursiv hisoblanadi. - Aylanma
bog'lanish (cycle) taqiqlanadi.

## Smart Warehouse

1.  Ishlab chiqaruvchi so'rov yuboradi.
2.  Tizim BOM hisoblaydi.
3.  QR token yaratiladi.
4.  Ishchi QR bilan tasdiqlanadi.
5.  Tarozi norma bo'yicha yo'naltiradi.
6.  Ombordan avtomatik chiqim qilinadi.
7.  Ishlab chiqaruvchiga biriktiriladi.

## QR konsepsiyasi

Public: https://stockfirm.uz/p/`<serial>`{=html}

Ko'rsatiladi: - Mahsulot - Ishlab chiqarilgan sana - Yaroqlilik
muddati - Batch - Original mahsulot tasdig'i

Ichki ERP: - Serial - Batch - Holat - Egasi - Scan soni

## Tayyor mahsulot

Har bir qadoq noyob serialga ega. Distributor, ombor va vozvrat QR
orqali kuzatiladi.

## GPS

Agent sotuvni yakunlashdan oldin: - Magazin radiusida ekanligi
tekshiriladi. - Zarurat bo'lsa magazin QR kodi skaner qilinadi.

## Dashboard

Omborchi: - Kirim - Chiqim - Xom ashyo qoldig'i - Tayyor mahsulot -
Buyurtmalar

Ishlab chiqaruvchi: - Reja - Bajarildi - Limit - KPI - Ish haqi

Admin: - Sotuv - Ishlab chiqarish - Pul oqimi - Foyda - Ombor

## Kelajak

-   Workflow Designer
-   Universal modul arxitekturasi
-   Mebel, kosmetika va boshqa ishlab chiqarish sohalarini
    qo'llab-quvvatlash.
