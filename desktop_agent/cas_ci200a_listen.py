"""CAS CI-200A tarozi indikatorini RS232 (COM4) orqali tinglash.

CAS seriyasidagi ko'p indikatorlar (shu jumladan CI-200A) standart
bo'lib, ulanganda **so'rovsiz o'zi uzluksiz oqim** yuboradi (odatda
9600,7,E,1 yoki 9600,8,N,1 — ikkalasini ham sinaymiz), format taxminan:
"ST,GS,+000.00kg\r\n" kabi vergul bilan ajratilgan matn.

Har bir (baud, bits, parity, stop) kombinatsiyasini navbat bilan bir
necha soniya tinglaydi va kelgan har qanday baytni hex+matn holida
chiqaradi.
"""
import serial
import time
import binascii

COM_PORT = "COM4"
SECONDS_PER_CONFIG = 5

CONFIGS = [
    (9600, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE),
    (9600, serial.SEVENBITS, serial.PARITY_EVEN, serial.STOPBITS_ONE),
    (9600, serial.SEVENBITS, serial.PARITY_ODD, serial.STOPBITS_ONE),
    (4800, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE),
    (4800, serial.SEVENBITS, serial.PARITY_EVEN, serial.STOPBITS_ONE),
    (2400, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE),
    (19200, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE),
    (1200, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE),
]


def hexdump(data: bytes) -> str:
    if not data:
        return "(empty)"
    return binascii.hexlify(data).decode() + "  |  " + repr(data)


def main():
    print("Tarozi yoqilgan va ekranda vazn ko'rsatilayotganiga ishonch hosil qiling.\n")
    for baud, bits, parity, stop in CONFIGS:
        label = f"{baud},{bits},{parity},{stop}"
        try:
            ser = serial.Serial(
                COM_PORT, baudrate=baud, bytesize=bits, parity=parity,
                stopbits=stop, timeout=0.5,
            )
        except Exception as e:
            print(f"[{label}] portni ochib bo'lmadi: {e}")
            continue
        print(f"--- [{label}] tinglanmoqda ({SECONDS_PER_CONFIG}s) ---")
        end = time.time() + SECONDS_PER_CONFIG
        got_data = False
        while time.time() < end:
            data = ser.read(256)
            if data:
                got_data = True
                print(f">>> [{label}] MA'LUMOT: {hexdump(data)}")
        ser.close()
        if not got_data:
            print(f"[{label}] hech narsa kelmadi.")
    print("\n=== Barcha konfiguratsiyalar sinaldi. ===")


if __name__ == "__main__":
    main()
