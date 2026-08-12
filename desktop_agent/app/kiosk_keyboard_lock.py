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


# ── Xavfsiz kombinatsiya-bloklash (RegisterHotKey) ───────────────────────
#
# `WH_KEYBOARD_LL` (223-qadamda olib tashlangan) HAR BIR tugma bosilishini
# Python callback orqali o'tkazadi — shu sabab (callback sekinligi) butun
# tizimni "muzlatib" qo'yishi mumkin edi. `RegisterHotKey` esa BUTUNLAY
# BOSHQA mexanizm: Windows'ning o'zi (ichki, C darajasidagi) tugma
# jadvalida FAQAT ro'yxatdan o'tkazilgan aniq kombinatsiyani "band qilib"
# qo'yadi — bizning kodimiz har bir tugma bosilishida chaqirilmaydi,
# faqat ANIQ o'sha kombinatsiya bosilganda, bitta `WM_HOTKEY` xabari
# keladi. Shuning uchun tizim tezligiga UMUMAN ta'sir qilmaydi — bu
# Windows'da Alt+Tab/Alt+Esc/Alt+F4'ni xavfsiz bloklashning standart
# usuli (masalan ko'plab kiosk/o'yin dasturlarida ishlatiladi).
#
# **Cheklov**: bu usul bilan yolg'iz Win tugmasini (Boshlash menyusini
# ochadigan) bloklab bo'lmaydi — Windows uni oddiy "hotkey" sifatida
# ro'yxatdan o'tkazishga imkon bermaydi (alohida, ichki shell xatti-
# harakati). Win tugmasini ham cheklash UCHUN operatsion tizim darajasida
# (Windows Kiosk/Assigned Access yoki Group Policy) sozlash kerak.
MOD_ALT = 0x0001
MOD_NOREPEAT = 0x4000
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_F4 = 0x73

WM_HOTKEY = 0x0312

# Har bir hotkey uchun o'ziga xos ID (bitta oyna ichida noyob bo'lishi kifoya).
HOTKEY_ALT_TAB = 1
HOTKEY_ALT_ESCAPE = 2
HOTKEY_ALT_F4 = 3

_KIOSK_HOTKEYS = (
    (HOTKEY_ALT_TAB, MOD_ALT | MOD_NOREPEAT, VK_TAB),
    (HOTKEY_ALT_ESCAPE, MOD_ALT | MOD_NOREPEAT, VK_ESCAPE),
    (HOTKEY_ALT_F4, MOD_ALT | MOD_NOREPEAT, VK_F4),
)


def register_kiosk_hotkeys(hwnd: int) -> None:
    """Alt+Tab, Alt+Esc, Alt+F4'ni shu OYNA uchun "band qiladi" — Windows
    endi bu kombinatsiyalarni umuman odatdagidek ishlatmaydi (vazifa
    almashtirgich ochilmaydi, oyna yopilmaydi), chaqiruvchiga esa
    `WM_HOTKEY` xabari keladi (`nativeEvent`da e'tiborsiz qoldiriladi —
    yagona maqsad shu kombinatsiyani "yutib qo'yish"). Kiosk qulflanganda
    chaqiriladi."""
    if _user32 is None:
        return
    for hotkey_id, mods, vk in _KIOSK_HOTKEYS:
        _user32.RegisterHotKey(hwnd, hotkey_id, mods, vk)


def unregister_kiosk_hotkeys(hwnd: int) -> None:
    """`register_kiosk_hotkeys()`ni bekor qiladi — kiosk qulfi ochilganda
    yoki dastur haqiqatan yopilganda chaqiriladi, aks holda bu
    kombinatsiyalar Windows'da doimiy band bo'lib qolardi."""
    if _user32 is None:
        return
    for hotkey_id, _mods, _vk in _KIOSK_HOTKEYS:
        _user32.UnregisterHotKey(hwnd, hotkey_id)
