"""Kiosk qulflangan holatda Win tugmasi va Alt+Tab/Alt+Esc'ni
BLOKLAYDIGON past darajali klaviatura ilgichi (WH_KEYBOARD_LL,
faqat Windows'da ishlaydi).

**Muhim cheklov**: Ctrl+Alt+Delete BU ORQALI (yoki umuman HECH QANDAY
oddiy dastur orqali) bloklanmaydi — Windows uni "xavfsiz diqqat
ketma-ketligi" (Secure Attention Sequence) sifatida har doim
to'g'ridan-to'g'ri Winlogon'ga yuboradi, hech qanday user-mode ilova
(bu jumladan) uni ko'rmaydi ham, to'xtata ham olmaydi. Buni cheklash
UCHUN stansiya kompyuterida operatsion tizim darajasida (Windows Kiosk
rejimi / Assigned Access yoki domen Group Policy) sozlash kerak —
dasturiy kod bilan amalga oshirib bo'lmaydi."""
import ctypes
from ctypes import wintypes

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
LLKHF_ALTDOWN = 0x20

VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_TAB = 0x09
VK_ESCAPE = 0x1B

try:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
except (OSError, AttributeError):
    _user32 = None  # Windows emas (masalan dasturchi Linux/macOS'da sinab ko'rmoqchi)


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


if _user32 is not None:
    _HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
else:
    _HOOKPROC = None


class KioskKeyboardBlocker:
    """`enabled=True` bo'lganda Win (chap/o'ng) va Alt+Tab/Alt+Esc
    kombinatsiyalarini butunlay yutib yuboradi (ilova ularni ko'radi,
    lekin Windows'ga uzatmaydi — Boshlash menyusi ochilmaydi, oyna
    almashtirilmaydi). `install()` dastur ishga tushganda BIR MARTA
    chaqiriladi, `set_enabled()` esa kiosk qulfi holati o'zgarganda
    (`MainWindow._set_kiosk_locked`)."""

    def __init__(self):
        self.enabled = False
        self._hook_id = None
        self._proc_ref = _HOOKPROC(self._hook_proc) if _HOOKPROC else None

    def _hook_proc(self, n_code, w_param, l_param):
        if n_code == 0 and self.enabled and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
            info = ctypes.cast(l_param, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
            vk = info.vkCode
            alt_down = bool(info.flags & LLKHF_ALTDOWN)
            if vk in (VK_LWIN, VK_RWIN):
                return 1
            if alt_down and vk in (VK_TAB, VK_ESCAPE):
                return 1
        return _user32.CallNextHookEx(self._hook_id, n_code, w_param, l_param)

    def install(self):
        if _user32 is None or self._hook_id is not None:
            return
        self._hook_id = _user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc_ref, None, 0)

    def uninstall(self):
        if _user32 is None or self._hook_id is None:
            return
        _user32.UnhookWindowsHookEx(self._hook_id)
        self._hook_id = None

    def set_enabled(self, enabled: bool):
        self.enabled = enabled


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
