"""RLS1100Bda "Print" tugmasi bosilganda RS232 (COM4) yoki TCP
(192.168.1.87:5001/5002/5100) orqali biror narsa yuboriladimi — shuni
bir vaqtning o'zida tinglab tekshiruvchi skript.

Ishlatish: shu skriptni ishga tushiring, u har bir kanalni fon oqimida
tinglay boshlaydi, so'ng SIZ tarozida "Print" tugmasini bosing. Har
qanday kelgan bayt hex+matn ko'rinishida, qaysi kanaldan kelgani bilan
chiqariladi.
"""
import socket
import threading
import time
import binascii

IP = "192.168.1.87"
TCP_PORTS = [5001, 5002, 5100]
COM_PORT = "COM4"
BAUD_RATES = [9600, 19200, 4800, 2400, 1200]
LISTEN_SECONDS = 55

stop_flag = threading.Event()


def hexdump(data: bytes) -> str:
    if not data:
        return "(empty)"
    return binascii.hexlify(data).decode() + "  |  " + repr(data)


def listen_tcp(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((IP, port))
        s.settimeout(0.5)
        print(f"[TCP:{port}] ulandi, tinglanmoqda...")
        while not stop_flag.is_set():
            try:
                data = s.recv(4096)
                if data:
                    print(f"\n>>> [TCP:{port}] MA'LUMOT KELDI: {hexdump(data)}\n")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[TCP:{port}] xato: {e}")
                break
        s.close()
    except Exception as e:
        print(f"[TCP:{port}] ulanib bo'lmadi: {e}")


def listen_serial():
    try:
        import serial
    except ImportError:
        print("[SERIAL] pyserial o'rnatilmagan, RS232 o'tkazib yuborildi.")
        return
    # Bir nechta baud tezlikni ketma-ket sinaymiz, har birida qisqa kutish.
    per_baud = max(3, LISTEN_SECONDS // len(BAUD_RATES))
    for baud in BAUD_RATES:
        if stop_flag.is_set():
            return
        try:
            ser = serial.Serial(COM_PORT, baudrate=baud, timeout=0.5)
        except Exception as e:
            print(f"[SERIAL:{baud}] portni ochib bo'lmadi: {e}")
            continue
        print(f"[SERIAL:{COM_PORT}@{baud}] tinglanmoqda ({per_baud}s)...")
        end = time.time() + per_baud
        while time.time() < end and not stop_flag.is_set():
            data = ser.read(256)
            if data:
                print(f"\n>>> [SERIAL:{COM_PORT}@{baud}] MA'LUMOT KELDI: {hexdump(data)}\n")
        ser.close()


def main():
    threads = [threading.Thread(target=listen_tcp, args=(p,), daemon=True) for p in TCP_PORTS]
    threads.append(threading.Thread(target=listen_serial, daemon=True))
    for t in threads:
        t.start()
    time.sleep(1.5)  # TCP ulanishlar tayyor bo'lishi uchun kichik kutish
    print(">>> TINGLANMOQDA — Print tugmasini istalgan vaqtda bosavering <<<\n")
    time.sleep(LISTEN_SECONDS)
    stop_flag.set()
    time.sleep(1)
    print("\n=== Tinglash tugadi. ===")


if __name__ == "__main__":
    main()
