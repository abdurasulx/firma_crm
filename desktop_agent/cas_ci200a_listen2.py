"""CAS CI-200A — 2-bosqich: DTR/RTS yoqilgan holda so'rov baytlari +
foydalanuvchi tugma bosgan real vaqtli tinglash.
"""
import serial
import time
import binascii

COM_PORT = "COM4"

CONFIGS = [
    (9600, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE),
    (9600, serial.SEVENBITS, serial.PARITY_EVEN, serial.STOPBITS_ONE),
    (4800, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE),
    (2400, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE),
]

PROBES = {
    "ENQ": bytes([0x05]),
    "W_CRLF": b"W\r\n",
    "P_CRLF": b"P\r\n",
    "SI_CRLF": b"SI\r\n",  # CAS "send immediate" komandasi (ba'zi modellarda)
    "R_CRLF": b"R\r\n",
}


def hexdump(data: bytes) -> str:
    if not data:
        return "(empty)"
    return binascii.hexlify(data).decode() + "  |  " + repr(data)


def main():
    for baud, bits, parity, stop in CONFIGS:
        label = f"{baud},{bits},{parity},{stop}"
        try:
            ser = serial.Serial(
                COM_PORT, baudrate=baud, bytesize=bits, parity=parity,
                stopbits=stop, timeout=0.7,
            )
            ser.dtr = True
            ser.rts = True
        except Exception as e:
            print(f"[{label}] portni ochib bo'lmadi: {e}")
            continue
        print(f"--- [{label}] DTR/RTS yoqildi, so'rovlar yuborilmoqda ---")
        for name, probe in PROBES.items():
            ser.reset_input_buffer()
            ser.write(probe)
            time.sleep(0.3)
            data = ser.read(256)
            if data:
                print(f">>> [{label}][{name}] JAVOB: {hexdump(data)}")
        ser.close()
    print("\n=== So'rov bosqichi tugadi. ===")


if __name__ == "__main__":
    main()
