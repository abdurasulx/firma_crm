"""XPrinter XP-365B (va TSPL/TSPL2 tilini tushunadigan boshqa termal
etiketka printerlari) uchun to'g'ridan-to'g'ri, drayver orqali RAW chop
etish xizmati.

XP-365B rasmiy Python SDK'ga ega emas — lekin u standart Windows printer
drayveri (Seagull) orqali o'rnatiladi va TSPL/TSPL2 buyruqlarini RAW
(qayta ishlanmagan bayt) rejimida qabul qiladi. Shuning uchun bu yerda
alohida SDK shart emas: `pywin32` (`win32print`) orqali TSPL matn
buyruqlari to'g'ridan-to'g'ri printer navbatiga yuboriladi — bu XPrinter
o'zi tavsiya qiladigan, eng barqaror usul (drayver versiyasi/OS
yangilanishlariga bog'liq emas).

**Turli o'lchamdagi plyonka (etiketka) uchun optimal yechim**: o'lcham
(kenglik/balandlik/oralig'lar) TSPL buyruqlari ichida ("SIZE"/"GAP")
har bir chop etishda YUBORILADI — printer xotirasiga oldindan
"dasturlab" qo'yilmaydi. Demak yechim: o'lchamni **qattiq kodlamaslik**,
balki Sozlamalar sahifasida (mm birligida) saqlab, har bir chop etishda
o'sha qiymatlar bilan TSPL generatsiya qilish — plyonka boshqa
o'lchamga almashtirilsa, foydalanuvchi faqat Sozlamalarni yangilaydi,
kod o'zgarishi shart emas.
"""
import win32print
from PyQt6.QtCore import QThread, pyqtSignal

DEFAULT_DPI = 203  # XP-365B standart bosim zichligi (nuqta/dyuym) — aksariyat 3-dyuymli termal etiketka printerlarida shu


def list_printers() -> list[str]:
    """Windows'da o'rnatilgan barcha printerlar nomlari ro'yxati —
    Sozlamalar sahifasida tanlash uchun."""
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    return [p[2] for p in win32print.EnumPrinters(flags)]


def _mm_to_dots(mm: float, dpi: int = DEFAULT_DPI) -> int:
    return round(mm * dpi / 25.4)


# QR-kod "bayt rejimi" (byte mode), ECC daraja L (kod TSPL buyrug'ida
# ham "L" bilan chop etiladi) uchun har bir versiyaning maksimal
# sig'imi (bayt) — standart QR spetsifikatsiyasidan. Modul soni =
# 4*versiya + 17 (versiya 1 dan 20 gacha — bizning qisqa URL'larimiz
# uchun yetarli, undan uzunroq matn kamdan-kam uchraydi).
_QR_BYTE_CAPACITY_ECC_L = [
    17, 32, 53, 78, 106, 134, 154, 192, 230, 271,
    321, 367, 425, 458, 520, 586, 644, 718, 792, 858,
]


def _qr_module_count(data: str) -> int:
    """Berilgan matn uchun QR-kod nechta "modul"dan (katakcha) iborat
    bo'lishini taxmin qiladi — cell_size (dona nuqta/modul) ni qog'oz
    o'lchamiga moslab hisoblash uchun kerak."""
    data_len = len(data.encode('utf-8', errors='replace'))
    for i, cap in enumerate(_QR_BYTE_CAPACITY_ECC_L, start=1):
        if data_len <= cap:
            return 4 * i + 17
    # Juda uzun matn (kamdan-kam) — eng katta versiya bilan davom etiladi.
    return 4 * len(_QR_BYTE_CAPACITY_ECC_L) + 17


def _fit_qr_cell_size(qr_data: str, width_mm: float, height_mm: float, margin_mm: float, dpi: int) -> int:
    """QR-kod tanlangan qog'oz o'lchamiga (kenglik/balandlik) sig'adigan
    eng katta hujayra o'lchamini (1-10, TSPL QRCODE buyrug'ining o'zi
    qabul qiladigan diapazon) hisoblaydi — kichik qog'ozda QR chegaradan
    chiqib ketmasligi (kesilib qolmasligi), katta qog'ozda esa imkon
    qadar yaxshi o'qiladigan (yirik) bo'lishi uchun."""
    modules = _qr_module_count(qr_data)
    available_mm = min(width_mm, height_mm) - 2 * margin_mm
    available_dots = _mm_to_dots(max(available_mm, 0), dpi)
    cell_size = available_dots // modules
    return max(1, min(10, cell_size))


def build_tspl_label(
    qr_data: str,
    width_mm: float = 40.0, height_mm: float = 30.0, gap_mm: float = 2.0,
    dpi: int = DEFAULT_DPI,
) -> bytes:
    """Bitta etiketka uchun TSPL buyruqlar ketma-ketligini quradi —
    faqat QR kod, hech qanday matn (avval mahsulot nomi TEXT sifatida
    QR ostiga chop etilardi, lekin katta QR kontentida u QR chegarasi
    bilan ustma-ust tushib, "QR ortida yozuv" ko'rinishini berardi —
    shuning uchun butunlay olib tashlandi).

    `SIZE`/`GAP` buyruqlari mm birligini to'g'ridan-to'g'ri qabul qiladi
    (masalan "SIZE 40 mm,30 mm") — lekin `QRCODE` kabi joylashuv
    buyruqlari har doim NUQTA (dot) birligida, shuning uchun ular DPI
    asosida mm'dan hisoblanadi.

    QR-kod hujayra o'lchami endi QATTIQ KODLANMAGAN — tanlangan qog'oz
    o'lchamiga (`width_mm`/`height_mm`) qarab avtomatik hisoblanadi
    (`_fit_qr_cell_size`), shunda kichik qog'ozda QR kesilib qolmaydi."""
    margin_mm = 2
    margin_dots = _mm_to_dots(margin_mm, dpi)
    qr_cell_size = _fit_qr_cell_size(qr_data, width_mm, height_mm, margin_mm, dpi)

    lines = [
        f"SIZE {width_mm:g} mm,{height_mm:g} mm",
        f"GAP {gap_mm:g} mm,0",
        "DIRECTION 0",
        # Ba'zi printerlarda drayver/firmware qayta o'rnatilgandan yoki
        # fabrika sozlamalariga qaytarilgandan keyin bosim zichligi
        # (DENSITY) 0'ga tushib qolishi mumkin — bu holda TSPL
        # buyruqlari to'g'ri qabul qilinsa ham, termal qog'oz
        # "isitilmaydi" va chin BO'SH yorliq chiqadi (real shikoyat:
        # "sinov chop etsam bo'm-bo'sh qog'oz chiqdi"). Shu sabab
        # zichlik/tezlik har safar aniq (0/kalibrlanmagan holatga
        # tayanmasdan) o'rnatiladi.
        "DENSITY 8",
        "SPEED 4",
        "CLS",
        f'QRCODE {margin_dots},{margin_dots},L,{qr_cell_size},A,0,"{_escape(qr_data)}"',
        "PRINT 1,1",
    ]

    body = "\r\n".join(lines) + "\r\n"
    return body.encode("gbk", errors="replace")  # TSPL firmware'lari odatda GBK/lotin kodlashni kutadi, UTF-8 emas


def _escape(text: str) -> str:
    return (text or "").replace('"', "'")


# Windows spooler PRINTER_STATUS_* bitmask qiymatlari (win32print
# konstantalari sifatida eksport qilinmagan, shuning uchun qo'lda
# yozilgan) — xuddi shu bitlar `startup_check_page._check_printer_live`da
# ham ishlatiladi.
_STATUS_PAPER_JAM = 0x8
_STATUS_PAPER_OUT = 0x10
_STATUS_OFFLINE = 0x80
_STATUS_ERROR = 0x2
_STATUS_USER_INTERVENTION = 0x100000
_STATUS_DOOR_OPEN = 0x400000
_STATUS_NOT_AVAILABLE = 0x1000

_STATUS_REASONS = (
    (_STATUS_PAPER_OUT, "Qog'oz tugagan"),
    (_STATUS_PAPER_JAM, "Qog'oz tiqilib qolgan"),
    (_STATUS_DOOR_OPEN, "Printer qopqog'i ochiq"),
    (_STATUS_OFFLINE, "Printer oflayn"),
    (_STATUS_NOT_AVAILABLE, "Printer mavjud emas"),
    (_STATUS_ERROR, "Printer xato holatida"),
    (_STATUS_USER_INTERVENTION, "Printerga e'tibor kerak"),
)


def get_printer_status_issue(printer_name: str) -> str | None:
    """Chop etishdan KEYIN chaqiriladi — printer HAQIQIY holatini
    (Windows spooler `GetPrinter` status bitmask) tekshiradi. `print_raw`
    (RAW yozish API'si) printer oflayn/qog'ozsiz bo'lsa ham odatda
    xatosiz qaytadi — shuning uchun haqiqiy natija faqat shu status
    tekshiruvi orqali aniqlanadi. Muammo topilmasa `None`."""
    try:
        handle = win32print.OpenPrinter(printer_name)
    except Exception:  # noqa: BLE001
        return "Printer bilan bog'lanib bo'lmadi"
    try:
        info = win32print.GetPrinter(handle, 2)
        status_bits = info.get("Status", 0)
    except Exception:  # noqa: BLE001
        return None  # holatni bilib bo'lmadi — ijobiy taxmin qilamiz (spooler qabul qilgan)
    finally:
        win32print.ClosePrinter(handle)

    for bit, reason in _STATUS_REASONS:
        if status_bits & bit:
            return reason
    return None


def print_raw(printer_name: str, data: bytes, doc_name: str = "StockFirm Label"):
    """Tayyor TSPL bayt ketma-ketligini printer navbatiga RAW rejimida
    yuboradi — hech qanday Windows sahifa-tarjimasi/GDI ishlatilmaydi,
    printer buyruqlarni bevosita, o'zgarishsiz oladi."""
    handle = win32print.OpenPrinter(printer_name)
    try:
        job_info = (doc_name, None, "RAW")
        win32print.StartDocPrinter(handle, 1, job_info)
        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)


class LabelPrintWorker(QThread):
    """Bir nechta etiketkani (masalan bitta partiyaning barcha Serial
    QR kodlarini) fon oqimida, ketma-ket chop etadi — printer sekin
    javob bersa ham GUI muzlab qolmasligi uchun. Har bir kutilmagan
    xato (printer o'chiq, drayver xatosi va h.k.) xavfsiz `failed`
    signaliga aylantiriladi — QThread ichida ushlanmagan xato butun
    dasturni yiqitib qo'yishi mumkinligi allaqachon tasdiqlangan
    (86-qadam)."""
    progress = pyqtSignal(int, int)  # (chop etilgan soni, jami)
    succeeded = pyqtSignal(int)  # jami chop etilgan soni
    failed = pyqtSignal(str)
    # Har bir alohida yorliq chop etilgandan KEYIN, printer HOLATI
    # tekshirilib chiqadi — (kod, muvaffaqiyatmi, sabab-agar-yo'q-bo'lsa).
    # `kod` bo'sh bo'lishi mumkin (`label["kod"]` berilmagan chaqiruvlar
    # uchun, masalan eski/boshqa joylardan) — bunda serverga xabar
    # qilinmaydi, faqat UI feedback uchun ishlatiladi.
    label_result = pyqtSignal(str, bool, str)

    def __init__(self, printer_name: str, labels: list[dict], width_mm: float, height_mm: float, gap_mm: float):
        """`labels` — [{"qr_data": str, "kod": str (ixtiyoriy)}, ...]"""
        super().__init__()
        self._printer_name = printer_name
        self._labels = labels
        self._width_mm = width_mm
        self._height_mm = height_mm
        self._gap_mm = gap_mm
        self.finished.connect(self.wait)

    def run(self):
        try:
            for i, label in enumerate(self._labels):
                data = build_tspl_label(
                    label["qr_data"], self._width_mm, self._height_mm, self._gap_mm,
                )
                print_raw(self._printer_name, data)
                issue = get_printer_status_issue(self._printer_name)
                self.label_result.emit(label.get("kod", ""), issue is None, issue or "")
                self.progress.emit(i + 1, len(self._labels))
        except Exception as exc:  # noqa: BLE001 — QThread ichida ushlanmagan xato butun dasturni yiqitadi
            self.failed.emit(f"Chop etishda xato: {exc}")
        else:
            self.succeeded.emit(len(self._labels))
