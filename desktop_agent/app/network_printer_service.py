"""Tarmoq (LAN) orqali ulangan etiketka/chek printerini AVTOMATIK topish va
unga to'g'ridan-to'g'ri (Windows printer drayverisiz) ulanish.

Nega kerak (real holat, XP-80C): printer LAN kabel bilan ulanganda u
o'zining zavod manzilida (`192.168.123.100`) turadi, kompyuterning
tarmoq kartasi esa odatda boshqa tarmoqda (masalan `192.168.1.50`).
Windows'dagi printer hamon eski USB portga bog'langan bo'ladi va
"Offline" ko'rinadi — foydalanuvchi IP topishi, tarmoq kartasiga manzil
qo'shishi va TCP/IP port yaratishi kerak edi. Bu modul shularni o'zi
bajaradi:

1. `discover_lan_printers()` — simli tarmoq kartalaridan ARP so'rovi
   yuborib qurilmalarni topadi. ARP kabel darajasida ishlaydi, shuning
   uchun printer BOSHQA tarmoqda (subnet) bo'lsa ham javob beradi.
2. `make_reachable()` — printer boshqa tarmoqda bo'lsa, kompyuter
   kartasiga o'sha tarmoqdan ikkinchi manzil qo'shadi (Windows
   administrator ruxsatini — UAC — so'raydi; eski manzil joyida qoladi).
3. Chop etish `tcp://<ip>:9100` ko'rinishidagi "printer nomi" orqali
   to'g'ridan-to'g'ri TCP (RAW/JetDirect, 9100-port) bilan bajariladi —
   `label_printer_service.print_raw` shu prefiksni taniydi.
"""
import ctypes
import ctypes.wintypes
import ipaddress
import json
import socket
import struct
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

RAW_PRINT_PORT = 9100
TCP_PREFIX = "tcp://"

# Printerlarning keng tarqalgan zavod tarmoqlari — kompyuter boshqa
# tarmoqda bo'lsa ham shu yerlar tekshiriladi (Xprinter: 192.168.123.100).
DEFAULT_PRINTER_NETWORKS = ("192.168.123", "192.168.1", "192.168.0", "192.168.2", "192.168.100", "10.0.0")

_CREATE_NO_WINDOW = 0x08000000


# ── tcp:// "printer nomi" ────────────────────────────────────────────────

def make_tcp_name(ip: str, port: int = RAW_PRINT_PORT) -> str:
    return f"{TCP_PREFIX}{ip}:{port}"


def parse_tcp_name(name: str):
    """`tcp://192.168.123.100:9100` -> ("192.168.123.100", 9100); oddiy
    Windows printer nomi bo'lsa `None`."""
    if not name or not name.startswith(TCP_PREFIX):
        return None
    rest = name[len(TCP_PREFIX):]
    host, _, port = rest.partition(":")
    try:
        return host, int(port) if port else RAW_PRINT_PORT
    except ValueError:
        return None


def display_name(name: str) -> str:
    parsed = parse_tcp_name(name)
    return f"LAN printer — {parsed[0]}" if parsed else name


def is_port_open(ip: str, port: int = RAW_PRINT_PORT, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def send_raw_tcp(ip: str, port: int, data: bytes, timeout: float = 5.0):
    with socket.create_connection((ip, port), timeout=timeout) as sock:
        sock.sendall(data)


# ── Tarmoq kartalari ─────────────────────────────────────────────────────

def list_physical_interfaces() -> list[dict]:
    """Yoqilgan JISMONIY tarmoq kartalari (VPN/virtual kartalarsiz) va
    ularning IPv4 manzillari: [{'alias', 'ip', 'prefix', 'wired'}]."""
    script = (
        "$a = Get-NetAdapter -Physical | Where-Object Status -eq 'Up'; "
        "$r = foreach ($n in $a) { Get-NetIPAddress -InterfaceIndex $n.ifIndex -AddressFamily IPv4 "
        "-ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ alias=$n.Name; ip=$_.IPAddress; "
        "prefix=$_.PrefixLength; media=[string]$n.PhysicalMediaType } } }; "
        "ConvertTo-Json -Compress @($r)"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20, creationflags=_CREATE_NO_WINDOW,
        ).stdout.strip()
        rows = json.loads(out) if out else []
    except Exception:  # noqa: BLE001 — PowerShell yo'q/sekin bo'lsa qidiruv shunchaki bo'sh qaytadi
        return []
    if isinstance(rows, dict):
        rows = [rows]
    result = []
    for row in rows:
        ip = row.get("ip") or ""
        if not ip or ip.startswith("169.254."):
            continue
        result.append({
            "alias": row.get("alias") or "",
            "ip": ip,
            "prefix": int(row.get("prefix") or 24),
            "wired": "802.3" in (row.get("media") or ""),
        })
    return result


# ── ARP orqali qidirish ──────────────────────────────────────────────────

def _send_arp(dest_ip: str, src_ip: str):
    """`dest_ip` uchun `src_ip` kartasidan ARP so'rovi. MAC (str) yoki `None`."""
    buf = (ctypes.c_ubyte * 6)()
    size = ctypes.c_ulong(6)
    dest = struct.unpack("<I", socket.inet_aton(dest_ip))[0]
    src = struct.unpack("<I", socket.inet_aton(src_ip))[0]
    rc = ctypes.windll.iphlpapi.SendARP(dest, src, ctypes.byref(buf), ctypes.byref(size))
    if rc == 0 and any(buf):
        return ":".join(f"{b:02x}" for b in buf)
    return None


def _same_network(ip: str, iface: dict) -> bool:
    network = ipaddress.ip_network(f"{iface['ip']}/{iface['prefix']}", strict=False)
    return ipaddress.ip_address(ip) in network


def discover_lan_printers() -> list[dict]:
    """Tarmoqdagi printerlarni qidiradi. Har biri:
    `{'ip', 'mac', 'alias', 'src_ip', 'reachable'}` — `reachable=False`
    bo'lsa printer kabelda bor, lekin kompyuter boshqa tarmoqda
    (`make_reachable` kerak). Avval darhol ishlaydiganlari qaytadi."""
    found: dict[str, dict] = {}
    for iface in list_physical_interfaces():
        own_net = ".".join(iface["ip"].split(".")[:3])
        networks = [own_net]
        if iface["wired"]:
            # Zavod manzillari faqat simli kartada tekshiriladi — printer
            # kabel bilan ulanadi; Wi-Fi orqali begona tarmoqqa ARP befoyda.
            networks += [n for n in DEFAULT_PRINTER_NETWORKS if n != own_net]
        candidates = [f"{net}.{i}" for net in networks for i in range(1, 255)]
        candidates = [c for c in candidates if c != iface["ip"]]
        with ThreadPoolExecutor(max_workers=400) as pool:
            macs = list(pool.map(lambda ip: _send_arp(ip, iface["ip"]), candidates))
        for ip, mac in zip(candidates, macs):
            if not mac or ip in found:
                continue
            same = _same_network(ip, iface)
            if same and not is_port_open(ip, timeout=0.7):
                continue  # shu tarmoqdagi boshqa qurilma (router, telefon...) — printer emas
            found[ip] = {"ip": ip, "mac": mac, "alias": iface["alias"], "src_ip": iface["ip"], "reachable": same}
    return sorted(found.values(), key=lambda d: (not d["reachable"], d["ip"]))


# ── Boshqa tarmoqdagi printerga yo'l ochish ──────────────────────────────

def _run_elevated(executable: str, parameters: str) -> bool:
    """Buyruqni administrator sifatida (UAC oynasi bilan) ishga tushirib,
    tugashini kutadi. Foydalanuvchi rad etsa yoki xato bo'lsa `False`."""

    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", ctypes.wintypes.HWND),
            ("lpVerb", ctypes.c_wchar_p), ("lpFile", ctypes.c_wchar_p), ("lpParameters", ctypes.c_wchar_p),
            ("lpDirectory", ctypes.c_wchar_p), ("nShow", ctypes.c_int), ("hInstApp", ctypes.wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p), ("lpClass", ctypes.c_wchar_p), ("hkeyClass", ctypes.wintypes.HKEY),
            ("dwHotKey", ctypes.wintypes.DWORD), ("hIcon", ctypes.wintypes.HANDLE),
            ("hProcess", ctypes.wintypes.HANDLE),
        ]

    info = SHELLEXECUTEINFO()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040  # SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = executable
    info.lpParameters = parameters
    info.nShow = 0  # SW_HIDE
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        return False
    if not info.hProcess:
        return False
    ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, 30000)
    exit_code = ctypes.wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code))
    ctypes.windll.kernel32.CloseHandle(info.hProcess)
    return exit_code.value == 0


def pick_free_address(printer_ip: str, src_ip: str) -> str | None:
    """Printer tarmog'idan kompyuter uchun bo'sh manzil (…50 dan boshlab)
    — band emasligi ARP bilan tekshiriladi."""
    net = ".".join(printer_ip.split(".")[:3])
    for host in (50, 51, 52, 60, 70, 200, 201, 202):
        candidate = f"{net}.{host}"
        if candidate != printer_ip and _send_arp(candidate, src_ip) is None:
            return candidate
    return None


def make_reachable(device: dict) -> tuple[bool, str]:
    """`discover_lan_printers` topgan, lekin boshqa tarmoqda turgan
    printerga yo'l ochadi: kompyuter kartasiga printer tarmog'idan
    IKKINCHI manzil qo'shadi (eski manzil o'zgarmaydi). (ok, xabar)."""
    ip = device["ip"]
    if is_port_open(ip, timeout=1.0):
        return True, f"{ip} bilan aloqa bor."
    new_address = pick_free_address(ip, device["src_ip"])
    if not new_address:
        return False, "Printer tarmog'ida kompyuter uchun bo'sh manzil topilmadi."
    ok = _run_elevated(
        "netsh", f'interface ipv4 add address "{device["alias"]}" {new_address} 255.255.255.0',
    )
    if not ok:
        return False, (
            "Tarmoq manzilini qo'shib bo'lmadi — administrator ruxsati berilmadi yoki tarmoq kartasi "
            "avtomatik (DHCP) rejimda. Qo'lda: administrator terminalida "
            f'netsh interface ipv4 add address "{device["alias"]}" {new_address} 255.255.255.0'
        )
    # Windows yangi manzilni bir necha soniyada ishga tushiradi.
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if is_port_open(ip, timeout=1.0):
            return True, f"Kompyuterga {new_address} manzili qo'shildi — {ip} bilan aloqa o'rnatildi."
        time.sleep(0.5)
    return False, (
        f"Kompyuterga {new_address} manzili qo'shildi, lekin {ip} ning chop etish porti "
        f"({RAW_PRINT_PORT}) javob bermadi — printer yoqilganini tekshiring."
    )
