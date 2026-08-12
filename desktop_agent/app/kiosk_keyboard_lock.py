"""Kiosk rejimi uchun Windows taskbar'ni yashirish/qaytarish.

**Tarix (223-qadam, real ishlab chiqarishda topilgan xato)**: bu faylda
avval Win tugmasi/Alt+Tab'ni bloklaydigan `WH_KEYBOARD_LL` past
darajali klaviatura ilgichi ham bor edi — lekin bunday GLOBAL ilgich
BUTUN TIZIM darajasida ishlaydi: agar Python callback (GIL/interpretator
tezligi tufayli) biroz sekinlik qilsa, Windows shu ilgichni kutib,
BOSHQA HAMMA dastur (jumladan HID skaner, klaviatura sifatida ishlaydi)
uchun ham kiritishni kechiktirib/bloklab qo'yishi mumkin — aynan shu
sabab butun kompyuterda yozish/skanerlash ishlamay qoldi. Shuning uchun
BUTUNLAY OLIB TASHLANDI. Win/Alt+Tab kabi tizim buyruqlarini ishonchli
va xavfsiz cheklash FAQAT operatsion tizim darajasida (Windows Kiosk/
Assigned Access yoki Group Policy) — xuddi Ctrl+Alt+Delete kabi —
amalga oshirilishi kerak, dasturiy global ilgich orqali emas.

Taskbar yashirish esa XAVFSIZ — u global INPUT pipeline'ga tegmaydi,
faqat bitta oynani (`Shell_TrayWnd`) ko'rsatish/yashirish, shuning
uchun saqlanib qolgan."""
import ctypes

try:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
except (OSError, AttributeError):
    _user32 = None  # Windows emas (masalan dasturchi Linux/macOS'da sinab ko'rmoqchi)

SW_HIDE = 0
SW_SHOW = 5


def hide_taskbar():
    """Windows Taskbar'ni yashiradi (`showFullScreen()` o'zi buni
    qilmaydi — oyna to'liq ekranga chiqadi, lekin taskbar hamon pastda
    ko'rinib turadi va bosilishi mumkin edi). `Shell_TrayWnd` — asosiy
    taskbar oynasi, `Button` klassidagi bolasi — "Boshlash" tugmasi."""
    if _user32 is None:
        return
    tray = _user32.FindWindowW("Shell_TrayWnd", None)
    if tray:
        _user32.ShowWindow(tray, SW_HIDE)
    start_btn = _user32.FindWindowW("Button", "Start")
    if start_btn:
        _user32.ShowWindow(start_btn, SW_HIDE)


def show_taskbar():
    """`hide_taskbar()`ni bekor qiladi — dastur haqiqatan yopilganda
    (kiosk qulfi ochiq holatda) chaqiriladi, aks holda foydalanuvchi
    Windows'ning o'zida taskbarsiz qolib ketardi."""
    if _user32 is None:
        return
    tray = _user32.FindWindowW("Shell_TrayWnd", None)
    if tray:
        _user32.ShowWindow(tray, SW_SHOW)
    start_btn = _user32.FindWindowW("Button", "Start")
    if start_btn:
        _user32.ShowWindow(start_btn, SW_SHOW)
