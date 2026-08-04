"""RLS1100B (Rongta) LAN tarozi uchun diagnostika skripti.

Rasmiy protokol hujjati hali topilmagan (RLS1100B_INTEGRATION_NOTES.md'ga
qarang). Bu skript ochiq portlarni topadi va umumiy (boshqa arzon xitoy
tarozi indikatorlarida uchraydigan) protokol namunalarini sinab ko'radi,
har bir javobni hex+matn ko'rinishida chiqaradi.

Ishlatish: `python rls1100b_probe.py` — kerak bo'lsa IP'ni pastda
o'zgartiring. Yangi taxminlarni sinash uchun `PROBES` lug'atiga qo'shing.
"""
import socket
import binascii

IP = "192.168.1.87"
PORTS = [5001, 5002, 5100]  # 1-10000 to'liq skanerlash orqali topilgan (2026-07-31)

# Boshqa arzon xitoy tarozi indikatorlarida ko'p uchraydigan naqshlar.
PROBES = {
    "ENQ": bytes([0x05]),
    "STX_ENQ_ETX": bytes([0x02, 0x05, 0x03]),
    "ascii_W_CRLF": b"W\r\n",
    "ascii_lowercase_w": b"w\r\n",
    "ascii_S_CRLF": b"S\r\n",
    "ascii_P_CRLF": b"P\r\n",
    "single_01": bytes([0x01]),
    "single_02": bytes([0x02]),
    "single_06_ACK": bytes([0x06]),
    "toledo_like": b"\x02W1\r\n\x03",
    "empty_then_wait": b"",
}


def hexdump(data: bytes) -> str:
    if not data:
        return "(empty)"
    return binascii.hexlify(data).decode() + "  |  " + repr(data)


def scan_ports(ip: str, port_range=range(1, 10001), timeout=0.3):
    """To'liq port skanerlash — yangi qurilma/IP uchun qayta ishlatish uchun."""
    import socket as _socket
    from concurrent.futures import ThreadPoolExecutor

    def check(port):
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((ip, port))
            s.close()
            return port
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=200) as ex:
        results = list(ex.map(check, port_range))
    return [p for p in results if p]


def probe_all(ip: str, ports: list):
    for port in ports:
        print(f"\n========== PORT {port} ==========")
        for name, probe in PROBES.items():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.5)
            try:
                s.connect((ip, port))
                if probe:
                    s.sendall(probe)
                try:
                    data = s.recv(4096)
                    print(f"[{name}] probe={probe!r}\n   -> RESPONSE: {hexdump(data)}")
                except socket.timeout:
                    pass  # ko'pchiligi kutilgandek timeout beradi -- faqat javob kelganda chop etiladi
            except Exception as e:
                print(f"[{name}] connect/send error: {e}")
            finally:
                s.close()
        print(f"--- port {port}: barcha probe yuborildi, faqat javoblar (bo'lsa) yuqorida ko'rsatilgan ---")


if __name__ == "__main__":
    probe_all(IP, PORTS)
