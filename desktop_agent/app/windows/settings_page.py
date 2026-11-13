import os
import tempfile

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox,
    QFrame, QScrollArea, QLayout,
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QPolygonF

from .. import db
from ..api_client import station_login, station_login_by_qr, parse_server_input, ApiError, send_logout
from ..label_printer_service import list_printers, LabelPrintWorker
from ..network_printer_service import (
    discover_lan_printers, make_reachable, make_tcp_name, parse_tcp_name, display_name,
)
from .camera_config_dialog import CameraConfigDialog


# Sozlamalar sahifasining ko'rinishi (ERP veb-interfeysi bilan bir xil
# ranglar: to'q ko'k matn, yashil asosiy tugma, oq kartochkalar). Faqat
# shu sahifaga (va undan ochiladigan dialoglarga) ta'sir qiladi.
SETTINGS_QSS = """
#settingsPage, #settingsContent { background:#f1f5f9; }
QScrollArea { background:#f1f5f9; border:none; }
QFrame#card { background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; }
QLabel { color:#0f172a; font-size:13px; background:transparent; }
QLabel#pageTitle { font-size:24px; font-weight:800; }
QLabel#pageSubtitle { color:#64748b; font-size:13px; }
QLabel#cardIcon { font-size:20px; }
QLabel#cardTitle { font-size:16px; font-weight:800; }
QLabel#cardDesc { color:#64748b; font-size:12px; }
QLabel#fieldLabel { color:#475569; font-size:12px; font-weight:700; }
QLabel#fieldHint { color:#94a3b8; font-size:11px; }
QLabel#accountStatus { font-size:14px; font-weight:700; }
QLabel#statusPill {
    background:#f1f5f9; border:1px solid #e2e8f0; border-radius:8px;
    padding:10px 12px; font-weight:700; color:#334155;
}
QLabel#infoBox {
    color:#1e3a8a; background:#eff6ff; border:1px solid #bfdbfe;
    border-radius:10px; padding:14px; font-weight:600;
}
QLabel#warnBox {
    color:#92400e; background:#fffbeb; border:1px solid #fde68a;
    border-radius:10px; padding:12px; font-weight:700;
}
QLineEdit, QComboBox {
    background:#ffffff; border:1px solid #cbd5e1; border-radius:8px;
    padding:8px 10px; font-size:14px; color:#0f172a; min-height:22px;
}
QLineEdit:focus, QComboBox:focus { border:1px solid #10b981; }
QComboBox::drop-down { subcontrol-origin:padding; subcontrol-position:center right; width:30px; border:none; }
QComboBox::down-arrow { image:url(__COMBO_ARROW__); width:12px; height:12px; margin-right:10px; }
QComboBox QAbstractItemView {
    background:#ffffff; border:1px solid #cbd5e1; color:#0f172a;
    selection-background-color:#d1fae5; selection-color:#065f46; outline:none;
}
QPushButton {
    background:#ffffff; border:1px solid #cbd5e1; border-radius:8px;
    padding:9px 16px; font-size:13px; font-weight:700; color:#0f172a; min-height:20px;
}
QPushButton:hover { background:#f8fafc; border-color:#94a3b8; }
QPushButton:pressed { background:#e2e8f0; }
QPushButton:disabled { color:#94a3b8; background:#f1f5f9; border-color:#e2e8f0; }
QPushButton[variant="primary"] { background:#10b981; border:1px solid #10b981; color:#ffffff; }
QPushButton[variant="primary"]:hover { background:#059669; border-color:#059669; }
QPushButton[variant="primary"]:pressed { background:#047857; }
QPushButton[variant="primary"]:disabled { background:#a7f3d0; border-color:#a7f3d0; color:#ffffff; }
QPushButton[variant="danger"] { background:#fff1f2; border:1px solid #fecaca; color:#b91c1c; }
QPushButton[variant="danger"]:hover { background:#ffe4e6; border-color:#fca5a5; }
QPushButton[variant="link"] {
    background:transparent; border:none; color:#2563eb; padding:2px 0; text-align:left;
}
QPushButton[variant="link"]:hover { color:#1d4ed8; background:transparent; }
"""


def _combo_arrow_path() -> str:
    """Ro'yxat (combo) uchun pastga qaragan strelka rasmi. Qt uslublar
    jadvali strelkani faqat rasm fayli orqali qabul qiladi, exe ichiga esa
    alohida resurs fayllari qo'shilmagan — shuning uchun kichik PNG ish
    vaqtida vaqtinchalik papkaga chizib qo'yiladi."""
    path = os.path.join(tempfile.gettempdir(), "stockfirm_agent_combo_arrow.png")
    if not os.path.exists(path):
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#64748b"))
        pen.setWidthF(3.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(QPolygonF([QPointF(5, 9), QPointF(12, 16), QPointF(19, 9)]))
        painter.end()
        pixmap.save(path, "PNG")
    return path.replace("\\", "/")


class _ApiCallWorker(QThread):
    """Login/sinxronlash so'rovlarini fon oqimida bajaradi — to'g'ridan-
    to'g'ri asosiy oqimda chaqirilsa, server sekin javob bersa yoki
    umuman ulanmasa, butun ilova muzlab qolardi (68-qadamda tuzatilgan
    skanerlash muammosi bilan bir xil turkumdagi xavf)."""
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    # Token eskirgan/bekor qilingan (401) — faqat MAVJUD tokendan
    # foydalanadigan so'rovlar (masalan `fetch_omborlar` sinxronlash)
    # uchun ma'noli; login urinishidagi 401 ("parol xato") bilan
    # aralashtirilmasligi kerak — shu sabab chaqiruvchi tomon o'zi
    # tanlab ulaydi (barcha worker'larga avtomatik emas).
    token_invalid = pyqtSignal()

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        # Eski worker obyekti tezda yangisi bilan almashtirilganda GC uni
        # C++ oqimi hali to'liq join bo'lmasdan o'chirib yubormasligi uchun.
        self.finished.connect(self.wait)

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
        except ApiError as exc:
            if exc.status_code == 401:
                self.token_invalid.emit()
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 — kutilmagan xato butun ilovani yiqitmasin
            self.failed.emit(f"Kutilmagan xato: {exc}")
        else:
            self.succeeded.emit(result)


class SettingsPage(QWidget):
    """Har bir Desktop Agent o'rnatilishi (stansiya) o'zining shaxsiy
    login/paroli bilan ERP'ga kiradi — ERP'dagi "Hodimlar" bo'limida
    "Desktop Agent" turida yaratilgan hisob orqali. Bitta firma bir nechta
    stansiyani shu tarzda alohida-alohida boshqarishi mumkin."""

    # `_sync_worker` (mavjud tokendan foydalanadigan `fetch_omborlar`)
    # 401 qaytarsa — token boshqa joyda bekor qilingan, `MainWindow`
    # heartbeatdagi bilan bir xil avtomatik logout oqimini ishga tushiradi.
    session_expired = pyqtSignal()

    def __init__(self, on_synced=None, on_scanner_changed=None, on_login_succeeded=None, on_scale_changed=None,
                 on_recheck_devices=None, on_logout=None, parent=None):
        super().__init__(parent)
        self.on_synced = on_synced
        self.on_scanner_changed = on_scanner_changed
        self.on_scale_changed = on_scale_changed
        self.on_login_succeeded = on_login_succeeded
        self.on_recheck_devices = on_recheck_devices
        self.on_logout = on_logout
        self._login_worker: _ApiCallWorker | None = None
        self._logout_worker: _ApiCallWorker | None = None
        self._connecting_timer = QTimer(self)
        self._connecting_timer.setInterval(400)
        self._connecting_timer.timeout.connect(self._tick_connecting_animation)
        self._connecting_dots = 0
        self.setObjectName("settingsPage")
        self.setStyleSheet(SETTINGS_QSS.replace("__COMBO_ARROW__", _combo_arrow_path()))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Kichik ekranli stansiyalarda ham hamma narsa sig'ishi uchun —
        # sahifa aylantiriladigan (scroll) maydon ichida.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        content = QWidget()
        content.setObjectName("settingsContent")
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 26, 32, 26)
        layout.setSpacing(16)

        # ── Sarlavha ─────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Sozlamalar")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Stansiyani ERP'ga ulash va qurilmalarni (skaner, tarozi, printer) sozlash")
        subtitle.setObjectName("pageSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        title_row.addLayout(title_col)
        title_row.addStretch(1)
        # Qurilma-tekshiruv sahifasidan "Sozlamalarga o'tish" bosilgach
        # (176-qadam) — muammo tuzatilgach shu tugma orqali qayta
        # tekshirishga qaytiladi (`_on_startup_open_settings`ga qarang).
        recheck_btn = QPushButton("🔄  Qurilmalarni qayta tekshirish")
        recheck_btn.setProperty("variant", "primary")
        recheck_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        recheck_btn.clicked.connect(lambda: self.on_recheck_devices and self.on_recheck_devices())
        title_row.addWidget(recheck_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(title_row)

        # ── Hisob (ERP bilan bog'lanish) ─────────────────────────────────
        account_card, account_body = self._make_card("🔗", "ERP hisobi")

        account_row = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("accountStatus")
        account_row.addWidget(self.status_label, 1)
        # Real bug (foydalanuvchi topdi): omborlar allaqachon WebSocket
        # orqali real-vaqtda avtomatik sinxronlanadi (91-qadam) — qo'lda
        # "Sinxronlash" tugmasi endi ortiqcha, chalkashtiradi. Olib
        # tashlandi.
        # Faqat login qilingan holatda ko'rinadi (`_show_synced_view`/
        # `show_login_required` shu ko'rinishni boshqaradi) — stansiyani
        # boshqa xodim/firma uchun qayta ishlatish uchun.
        self.logout_btn = QPushButton("🚪  Chiqish")
        self.logout_btn.setProperty("variant", "danger")
        self.logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logout_btn.clicked.connect(self._logout)
        self.logout_btn.setVisible(False)
        account_row.addWidget(self.logout_btn, 0, Qt.AlignmentFlag.AlignTop)
        account_body.addLayout(account_row)

        # QR kod orqali login — endi standart usul (145-qadam). Qurilma
        # hali login qilinmagan bo'lsa, qo'lda login/parol maydonlari
        # o'rniga shu xabar ko'rsatiladi — stansiya kamerasi (yoki HID
        # skaner) allaqachon login holatidan mustaqil ishlab turibdi
        # (`ScannerService`), shuning uchun QR kod har qanday paytda
        # skanerlanishi mumkin.
        self.qr_prompt_label = QLabel(
            "📷 Qurilmani ro'yxatdan o'tkazish uchun administratordan "
            "so'rang: ERP'da Profil sahifasida \"Desktop Agent QR-login\" "
            "kartasidagi QR kodni shu stansiya kamerasiga (yoki HID "
            "skaneriga) ko'rsating — avtomatik tizimga kirasiz."
        )
        self.qr_prompt_label.setWordWrap(True)
        self.qr_prompt_label.setObjectName("infoBox")
        account_body.addWidget(self.qr_prompt_label)

        # Real muammo (foydalanuvchi xabar berdi): yangi stansiyada hali
        # hech qanday kamera "skaner" roliga ulanmagan bo'lsa,
        # `ScannerService` HECH QACHON kamerani ochmaydi — QR-login
        # skaneri "jim" qoladi, hech qanday oyna/xato ko'rinmaydi.
        # Foydalanuvchi buni tushunishi qiyin edi ("nega reaksiya yo'q").
        self.no_scanner_warning_label = QLabel(
            "⚠ Hali hech qanday kamera \"Skaner\" sifatida ulanmagan — QR-login "
            "ISHLAMAYDI. Pastdagi \"Skaner\" bo'limida kamerani tanlab saqlang."
        )
        self.no_scanner_warning_label.setWordWrap(True)
        self.no_scanner_warning_label.setObjectName("warnBox")
        self.no_scanner_warning_label.setVisible(False)
        account_body.addWidget(self.no_scanner_warning_label)

        self.manual_toggle_btn = QPushButton("Qo'lda login/parol bilan kirish")
        self.manual_toggle_btn.setProperty("variant", "link")
        self.manual_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manual_toggle_btn.clicked.connect(self._toggle_manual_login)
        account_body.addWidget(self.manual_toggle_btn, 0, Qt.AlignmentFlag.AlignLeft)

        self.manual_login_container = QWidget()
        manual_layout = QVBoxLayout(self.manual_login_container)
        manual_layout.setContentsMargins(0, 4, 0, 0)
        manual_layout.setSpacing(8)

        desc = QLabel(
            "Firmangiz nomini (do'kon yaratilganda tanlangan manzil qismi, "
            "masalan \"birzumda\") va ERP'da (Hodimlar > Yangi hodim "
            "qo'shish > \"Desktop Agent\") yaratilgan login/parolni "
            "kiriting. (Test/lokal server — IP yoki localhost — uchun "
            "\"<firma nomi>@<manzil>\" formatida kiriting, masalan "
            "birzumda@http://127.0.0.1:8000.)"
        )
        desc.setWordWrap(True)
        desc.setObjectName("cardDesc")
        manual_layout.addWidget(desc)

        manual_fields = QHBoxLayout()
        manual_fields.setSpacing(12)
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("masalan: birzumda")
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._login)
        for label_text, widget in (
            ("Firma nomi", self.server_input),
            ("Stansiya logini", self.username_input),
            ("Parol", self.password_input),
        ):
            manual_fields.addLayout(self._make_field(label_text, widget), 1)
        self.login_btn = QPushButton("Kirish")
        self.login_btn.setProperty("variant", "primary")
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.clicked.connect(self._login)
        manual_fields.addWidget(self.login_btn, 0, Qt.AlignmentFlag.AlignBottom)
        manual_layout.addLayout(manual_fields)

        self.manual_login_container.setVisible(False)
        account_body.addWidget(self.manual_login_container)
        layout.addWidget(account_card)

        # ── Qurilmalar: uchta kartochka yonma-yon ────────────────────────
        devices_row = QHBoxLayout()
        devices_row.setSpacing(16)

        # Skaner
        scanner_card, scanner_body = self._make_card(
            "📷", "Skaner",
            "Xodim badge'i va QR kodlar uchun kamera yoki qo'l (USB) skaneri. "
            "Sozlangach, dastur ochiq turganda istalgan payt skanerlash mumkin — "
            "boshqa oyna fokusda bo'lsa ham.",
        )
        self.scanner_status_label = QLabel("")
        self.scanner_status_label.setWordWrap(True)
        self.scanner_status_label.setObjectName("statusPill")
        scanner_body.addWidget(self.scanner_status_label)
        scanner_body.addStretch(1)
        scanner_configure_btn = QPushButton("Skanerni sozlash")
        scanner_configure_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        scanner_configure_btn.clicked.connect(self._configure_scanner)
        scanner_body.addWidget(scanner_configure_btn)
        devices_row.addWidget(scanner_card, 1)

        # Tarozi (CAS CI-200A va shu formatga mos boshqalar, RS232)
        scale_card, scale_body = self._make_card(
            "⚖️", "Tarozi",
            "Vazn tarozidan avtomatik olinadi. Tarozi ulangan COM portni tanlang; "
            "tanlanmasa, vazn qo'lda kiritiladi.",
        )
        self.scale_com_combo = QComboBox()
        self.scale_refresh_btn = QPushButton("↻")
        self.scale_refresh_btn.setToolTip("Portlar ro'yxatini yangilash")
        self.scale_refresh_btn.setFixedWidth(40)
        self.scale_refresh_btn.setStyleSheet("font-size:18px; padding:4px 0;")
        self.scale_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scale_refresh_btn.clicked.connect(self._refresh_scale_ports)
        port_row = QHBoxLayout()
        port_row.setSpacing(8)
        port_row.addWidget(self.scale_com_combo, 1)
        port_row.addWidget(self.scale_refresh_btn)
        scale_body.addLayout(self._make_field("COM port", port_row))

        self.scale_capacity_input = QLineEdit()
        self.scale_capacity_input.setPlaceholderText("Masalan: 30")
        scale_body.addLayout(self._make_field(
            "Maksimal sig'im (kg)", self.scale_capacity_input,
            hint="Kerakli miqdor sig'imdan oshsa, tortish porsiyalarga bo'linadi "
                 "(45 kg, 30 kg li tarozida: 30 + 15). Bo'sh qoldirilsa — cheklovsiz.",
        ))
        self.scale_status_label = QLabel("")
        self.scale_status_label.setWordWrap(True)
        scale_body.addWidget(self.scale_status_label)
        scale_body.addStretch(1)
        # Port va sig'im avval ikkita alohida "Saqlash" tugmasi bilan
        # saqlanardi — chalkashtirardi, endi bittasi ikkalasini saqlaydi.
        self.scale_save_btn = QPushButton("Saqlash")
        self.scale_save_btn.setProperty("variant", "primary")
        self.scale_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scale_save_btn.clicked.connect(self._save_scale_all)
        scale_body.addWidget(self.scale_save_btn)
        devices_row.addWidget(scale_card, 1)

        # Etiketka printeri (XPrinter XP-365B va h.k. — TSPL)
        printer_card, printer_body = self._make_card(
            "🖨️", "Etiketka printeri",
            "QR yorliqlar shu printerda chop etiladi. O'lchamlarni ishlatilayotgan "
            "etiketka (plyonka) o'lchamiga moslang.",
        )
        self.printer_combo = QComboBox()
        self.printer_refresh_btn = QPushButton("↻")
        self.printer_refresh_btn.setToolTip("Printerlar ro'yxatini yangilash")
        self.printer_refresh_btn.setFixedWidth(40)
        self.printer_refresh_btn.setStyleSheet("font-size:18px; padding:4px 0;")
        self.printer_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.printer_refresh_btn.clicked.connect(self._refresh_printers)
        printer_row = QHBoxLayout()
        printer_row.setSpacing(8)
        printer_row.addWidget(self.printer_combo, 1)
        printer_row.addWidget(self.printer_refresh_btn)
        printer_body.addLayout(self._make_field("Printer", printer_row))

        # LAN (tarmoq) printerini IP'sini bilmasdan topish — kabelda turgan
        # printer boshqa tarmoqda bo'lsa ham (zavod manzili) aniqlanadi.
        self.printer_lan_search_btn = QPushButton("🔍  LAN printerni avtomatik qidirish")
        self.printer_lan_search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.printer_lan_search_btn.clicked.connect(self._search_lan_printers)
        printer_body.addWidget(self.printer_lan_search_btn)

        size_row = QHBoxLayout()
        size_row.setSpacing(10)
        self.label_width_input = QLineEdit()
        self.label_width_input.setPlaceholderText("40")
        self.label_height_input = QLineEdit()
        self.label_height_input.setPlaceholderText("30")
        self.label_gap_input = QLineEdit()
        self.label_gap_input.setPlaceholderText("2")
        size_row.addLayout(self._make_field("Kenglik (mm)", self.label_width_input), 1)
        size_row.addLayout(self._make_field("Balandlik (mm)", self.label_height_input), 1)
        size_row.addLayout(self._make_field("Oraliq (mm)", self.label_gap_input), 1)
        printer_body.addLayout(size_row)

        self.printer_status_label = QLabel("")
        self.printer_status_label.setWordWrap(True)
        printer_body.addWidget(self.printer_status_label)
        printer_body.addStretch(1)

        printer_btn_row = QHBoxLayout()
        printer_btn_row.setSpacing(8)
        self.printer_test_btn = QPushButton("Sinov chop etish")
        self.printer_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.printer_test_btn.clicked.connect(self._test_print)
        self.printer_save_btn = QPushButton("Saqlash")
        self.printer_save_btn.setProperty("variant", "primary")
        self.printer_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.printer_save_btn.clicked.connect(self._save_printer_settings)
        printer_btn_row.addWidget(self.printer_test_btn, 1)
        printer_btn_row.addWidget(self.printer_save_btn, 1)
        printer_body.addLayout(printer_btn_row)
        devices_row.addWidget(printer_card, 1)

        layout.addLayout(devices_row)

        self._print_worker: LabelPrintWorker | None = None
        self._lan_search_worker: _ApiCallWorker | None = None
        self._lan_reach_worker: _ApiCallWorker | None = None

        layout.addStretch(1)
        self._load()
        self._refresh_scanner_status()
        self._refresh_printers()
        self._load_printer_settings()
        self._refresh_scale_ports()
        self._load_scale_capacity()

    def _make_card(self, icon: str, title: str, desc: str = ""):
        """Oq kartochka (sarlavha + ixtiyoriy izoh). (frame, ichki layout)
        qaytaradi — bo'lim maydonlari shu layoutga qo'shiladi."""
        card = QFrame()
        card.setObjectName("card")
        body = QVBoxLayout(card)
        body.setContentsMargins(20, 18, 20, 18)
        body.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(8)
        icon_label = QLabel(icon)
        icon_label.setObjectName("cardIcon")
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        head.addWidget(icon_label)
        head.addWidget(title_label)
        head.addStretch(1)
        body.addLayout(head)
        if desc:
            desc_label = QLabel(desc)
            desc_label.setWordWrap(True)
            desc_label.setObjectName("cardDesc")
            body.addWidget(desc_label)
        return card, body

    def _make_field(self, label_text: str, field, hint: str = ""):
        """Maydon ustida kichik sarlavha, ostida ixtiyoriy izoh. `field` —
        widget yoki tayyor layout (masalan combo + yangilash tugmasi)."""
        col = QVBoxLayout()
        col.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        col.addWidget(label)
        if isinstance(field, QLayout):
            col.addLayout(field)
        else:
            col.addWidget(field)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setWordWrap(True)
            hint_label.setObjectName("fieldHint")
            col.addWidget(hint_label)
        return col

    def _load(self):
        self.server_input.setText(db.get_setting("server_input_raw", "") or db.get_setting("server_url", ""))
        self.username_input.setText(db.get_setting("station_username", ""))
        station_name = db.get_setting("station_name", "")
        company_name = db.get_setting("company_name", "")
        if db.get_setting("agent_token", "") and station_name:
            self.status_label.setStyleSheet("color:#059669;")
            self.status_label.setText(f"Kirilgan: {station_name} ({company_name})")
        self._update_login_ui_state()

    def _toggle_manual_login(self):
        visible = not self.manual_login_container.isVisible()
        self.manual_login_container.setVisible(visible)
        self.manual_toggle_btn.setText(
            "Qo'lda kirishni yopish" if visible else "Qo'lda login/parol bilan kirish"
        )

    def _update_login_ui_state(self):
        """QR kod — standart usul. Stansiya login qilingan bo'lsa, QR
        taklifi va qo'lda kirish bo'limi butunlay yashiriladi (endi
        kerak emas); login qilinmagan bo'lsa — QR taklifi ko'rinadi,
        qo'lda kirish esa ixtiyoriy (yig'ilgan) holatda qoladi."""
        logged_in = bool(db.get_setting("agent_token", ""))
        self.qr_prompt_label.setVisible(not logged_in)
        self.manual_toggle_btn.setVisible(not logged_in)
        self.logout_btn.setVisible(logged_in)
        if logged_in:
            self.manual_login_container.setVisible(False)
            self.manual_toggle_btn.setText("Qo'lda login/parol bilan kirish")

    def _start_connecting_animation(self, base_text: str):
        """Server bilan aloqa boshlanganda (qo'lda yoki QR orqali login,
        sinxronlash) chaqiriladi — foydalanuvchi hech narsa osilib
        qolmaganini ko'rishi uchun "Ulanmoqda..." matni nuqtalar bilan
        animatsiya qilinadi, javob kelguncha (muvaffaqiyat/xato) davom
        etadi."""
        self._connecting_base_text = base_text
        self._connecting_dots = 0
        self.status_label.setStyleSheet("color:#64748b;")
        self.status_label.setText(base_text)
        self._connecting_timer.start()

    def _tick_connecting_animation(self):
        self._connecting_dots = (self._connecting_dots + 1) % 4
        self.status_label.setText(self._connecting_base_text + "." * self._connecting_dots)

    def _stop_connecting_animation(self):
        self._connecting_timer.stop()

    def start_qr_login(self, subdomain: str, qr_payload: str, server_url: str):
        """`MainWindow`dagi global skaner `AGENTQR|...` kodini aniqlaganda
        chaqiradi — natija xuddi qo'lda login (`_on_login_succeeded`/
        `_on_login_failed`) bilan bir xil ishlov beriladi, shuning uchun
        UI holati (status_label, keyingi qadamlar) farqsiz yangilanadi."""
        db.set_setting("server_url", server_url)
        self._start_connecting_animation("QR kod orqali kirilmoqda")
        self._login_worker = _ApiCallWorker(station_login_by_qr, server_url, subdomain, qr_payload)
        self._login_worker.succeeded.connect(self._on_login_succeeded)
        self._login_worker.failed.connect(self._on_login_failed)
        self._login_worker.start()

    def _login(self):
        raw_input = self.server_input.text().strip()
        server_url, subdomain = parse_server_input(raw_input)
        username = self.username_input.text().strip()
        password = self.password_input.text()

        db.set_setting("server_input_raw", raw_input)
        db.set_setting("server_url", server_url)
        db.set_setting("station_username", username)

        self.login_btn.setEnabled(False)
        self._start_connecting_animation("Kirilmoqda")

        self._login_worker = _ApiCallWorker(station_login, server_url, subdomain, username, password)
        self._login_worker.succeeded.connect(self._on_login_succeeded)
        self._login_worker.failed.connect(self._on_login_failed)
        self._login_worker.start()

    def _on_login_succeeded(self, result: dict):
        self._stop_connecting_animation()
        self.login_btn.setEnabled(True)
        db.set_setting("agent_token", result["token"])
        db.set_setting("station_name", result["station_name"])
        db.set_setting("company_name", result["company"])
        # Firma ERP sozlamasida tarozi "shart emas" deb belgilangan bo'lsa —
        # startup tekshiruvi tarozini talab qilmaydi, tortish ekranida esa
        # oddiy "Oldim" tugmasi chiqadi (`employee_scan_widget.py`).
        db.set_setting("tarozi_majburiy", "1" if result.get("tarozi_majburiy", True) else "")
        self.password_input.clear()

        self.status_label.setStyleSheet("color:#059669;")
        self.status_label.setText(f"Kirildi: {result['station_name']} ({result['company']})")
        self._update_login_ui_state()

        if self.on_login_succeeded:
            self.on_login_succeeded()

    def _on_login_failed(self, message: str):
        self._stop_connecting_animation()
        self.login_btn.setEnabled(True)
        self.status_label.setStyleSheet("color:#b91c1c;")
        self.status_label.setText(message)

    def show_login_required(self):
        """Boshqa kompyuterda qayta login qilingani uchun bu stansiya
        tokeni serverda bekor qilingach (`MainWindow._handle_token_invalid`)
        chaqiriladi — foydalanuvchiga qaytadan kirish kerakligini
        ko'rsatadi, parol maydonini tozalaydi."""
        self.password_input.clear()
        self.status_label.setStyleSheet("color:#b91c1c;")
        self.status_label.setText("Sessiya yopildi — qaytadan kiring.")
        self._update_login_ui_state()

    def _logout(self):
        """Foydalanuvchi o'zi "Chiqish"ni bosganda — stansiya boshqa
        xodim/firma uchun qayta ishlatilishi kerak bo'lganda (masalan
        smena almashinuvi). Serverga "oflayn" xabari best-effort
        yuboriladi (`send_logout`) — natijasidan qat'i nazar mahalliy
        token darhol tozalanadi, chunki xodim uchun asosiysi shu
        qurilmada endi hech kim uning nomidan ish qila olmasligi."""
        if not db.get_setting("agent_token", ""):
            return
        reply = QMessageBox.question(
            self, "Chiqish",
            "Rostdan ham tizimdan chiqmoqchimisiz? Keyingi ishlatishda "
            "qaytadan login qilish kerak bo'ladi.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        self.logout_btn.setEnabled(False)
        worker = _ApiCallWorker(send_logout, server_url, token)
        worker.succeeded.connect(self._on_logout_finished)
        worker.failed.connect(lambda _msg: self._on_logout_finished(None))
        self._logout_worker = worker
        worker.start()

    def _on_logout_finished(self, _result):
        self.logout_btn.setEnabled(True)
        db.set_setting("agent_token", "")
        db.set_setting("station_name", "")
        db.set_setting("company_name", "")
        if self.on_logout:
            self.on_logout()
        self.status_label.setStyleSheet("color:#64748b;")
        self.status_label.setText("Tizimdan chiqdingiz.")
        self._update_login_ui_state()

    def _refresh_scanner_status(self):
        cam = db.get_scanner_camera()
        self.no_scanner_warning_label.setVisible(cam is None)
        if cam is None:
            self.scanner_status_label.setText("Holat: skaner hali sozlanmagan")
        elif cam.connection_type == "usb":
            self.scanner_status_label.setText(f"Holat: USB Kamera #{cam.usb_index} biriktirilgan")
        elif cam.connection_type == "hid":
            self.scanner_status_label.setText("Holat: Qo'lda skaner (USB, klaviatura kabi) biriktirilgan")
        else:
            self.scanner_status_label.setText(f"Holat: RTSP ({cam.rtsp_url}) biriktirilgan")

    def _configure_scanner(self):
        dialog = CameraConfigDialog(role="skaner", warehouse_id=None,
                                     title="Skanerni sozlash", parent=self)
        if dialog.exec():
            self._refresh_scanner_status()
            if self.on_scanner_changed:
                self.on_scanner_changed()

    # ── Tarozi ────────────────────────────────────────────────────────

    def _refresh_scale_ports(self):
        import serial.tools.list_ports

        current = self.scale_com_combo.currentText()
        self.scale_com_combo.clear()
        self.scale_com_combo.addItem("(tanlanmagan)", "")
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for port in ports:
            self.scale_com_combo.addItem(port, port)

        saved = db.get_setting("scale_com_port", "")
        target = current if current and current != "(tanlanmagan)" else saved
        if target:
            idx = self.scale_com_combo.findData(target)
            if idx >= 0:
                self.scale_com_combo.setCurrentIndex(idx)

    def _save_scale_all(self):
        """Bitta "Saqlash" — port ham, sig'im ham. Sig'im noto'g'ri bo'lsa
        hech narsa saqlanmaydi (xabar chiqadi)."""
        if not self._save_scale_capacity():
            self.scale_status_label.setText("")
            return
        self._save_scale_settings()
        port = self.scale_com_combo.currentData() or ""
        capacity = db.get_setting("scale_max_capacity_kg", "")
        self.scale_status_label.setStyleSheet("color:#059669;")
        self.scale_status_label.setText(
            f"Saqlandi: {port or 'port tanlanmagan'}"
            + (f", sig'im {float(capacity):g} kg" if capacity else ", sig'im cheklovsiz")
        )

    def _save_scale_settings(self):
        db.set_setting("scale_com_port", self.scale_com_combo.currentData() or "")
        if self.on_scale_changed:
            self.on_scale_changed()

    def _load_scale_capacity(self):
        self.scale_capacity_input.setText(db.get_setting("scale_max_capacity_kg", ""))

    def _save_scale_capacity(self):
        raw = self.scale_capacity_input.text().strip().replace(",", ".")
        if raw:
            try:
                value = float(raw)
                if value <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "Xato", "Sig'im musbat son bo'lishi kerak (masalan 30).")
                return False
            db.set_setting("scale_max_capacity_kg", str(value))
        else:
            db.set_setting("scale_max_capacity_kg", "")
        return True

    # ── Etiketka printeri ─────────────────────────────────────────────

    def _refresh_printers(self):
        current = self._selected_printer()
        self.printer_combo.clear()
        try:
            names = list_printers()
        except Exception as exc:  # noqa: BLE001 — Windows printer subsystem xatosi bo'lsa ham sahifa ochilaveradi
            self.printer_status_label.setStyleSheet("color:#b91c1c;")
            self.printer_status_label.setText(f"Printerlar ro'yxatini olishda xato: {exc}")
            return
        # Har bir qatorning "data"si — saqlanadigan haqiqiy nom: Windows
        # printer nomi yoki LAN printer uchun `tcp://ip:port`.
        for name in names:
            self.printer_combo.addItem(name, name)
        saved = db.get_setting("label_printer_name", "")
        for lan_name in (saved, current):
            if parse_tcp_name(lan_name):
                self._add_lan_printer_item(lan_name)
        target = saved if self.printer_combo.findData(saved) >= 0 else current
        if target:
            index = self.printer_combo.findData(target)
            if index >= 0:
                self.printer_combo.setCurrentIndex(index)

    def _selected_printer(self) -> str:
        return (self.printer_combo.currentData() or "").strip()

    def _add_lan_printer_item(self, tcp_name: str) -> int:
        index = self.printer_combo.findData(tcp_name)
        if index < 0:
            self.printer_combo.addItem(display_name(tcp_name), tcp_name)
            index = self.printer_combo.count() - 1
        return index

    # ── LAN printerni avtomatik topish ────────────────────────────────

    def _set_printer_status(self, text: str, color: str):
        self.printer_status_label.setStyleSheet(f"color:{color};")
        self.printer_status_label.setText(text)

    def _search_lan_printers(self):
        self.printer_lan_search_btn.setEnabled(False)
        self._set_printer_status("Tarmoqda printer qidirilmoqda (10–20 soniya)...", "#64748b")
        worker = _ApiCallWorker(discover_lan_printers)
        worker.succeeded.connect(self._on_lan_search_done)
        worker.failed.connect(self._on_lan_search_failed)
        self._lan_search_worker = worker
        worker.start()

    def _on_lan_search_failed(self, message: str):
        self.printer_lan_search_btn.setEnabled(True)
        self._set_printer_status(f"Qidirishda xato: {message}", "#b91c1c")

    def _on_lan_search_done(self, devices: list):
        self.printer_lan_search_btn.setEnabled(True)
        if not devices:
            self._set_printer_status(
                "Tarmoqda printer topilmadi — printer yoqilganini va LAN kabeli ulanganini tekshiring.",
                "#b91c1c",
            )
            return

        ready = [d for d in devices if d["reachable"]]
        if ready:
            self._select_lan_printer(ready[0]["ip"])
            boshqalar = f" (yana {len(ready) - 1} ta topildi — ro'yxatdan tanlang)" if len(ready) > 1 else ""
            for d in ready[1:]:
                self._add_lan_printer_item(make_tcp_name(d["ip"]))
            self._set_printer_status(
                f"Topildi: {ready[0]['ip']}{boshqalar}. \"Sinov chop etish\" bilan tekshirib, \"Saqlash\"ni bosing.",
                "#059669",
            )
            return

        # Printer kabelda bor, lekin kompyuter boshqa tarmoqda — yo'l ochish
        # uchun tarmoq kartasiga manzil qo'shiladi (Windows ruxsat so'raydi).
        device = devices[0]
        reply = QMessageBox.question(
            self, "LAN printer topildi",
            f"Printer topildi: {device['ip']} (\"{device['alias']}\" kabelida).\n\n"
            f"U kompyuterdan boshqa tarmoqda turibdi (kompyuter: {device['src_ip']}). Ulanish uchun "
            "kompyuterning shu tarmoq kartasiga printer tarmog'idan qo'shimcha manzil qo'shiladi — "
            "mavjud manzil o'zgarmaydi.\n\nWindows administrator ruxsatini so'raydi. Davom etilsinmi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            self._set_printer_status(
                f"Printer topildi ({device['ip']}), lekin u boshqa tarmoqda — ulanish yoqilmadi.", "#b45309",
            )
            return
        self.printer_lan_search_btn.setEnabled(False)
        self._set_printer_status(f"{device['ip']} ga ulanilmoqda...", "#64748b")
        worker = _ApiCallWorker(make_reachable, device)
        worker.succeeded.connect(lambda result, d=device: self._on_lan_reach_done(d, result))
        worker.failed.connect(self._on_lan_search_failed)
        self._lan_reach_worker = worker
        worker.start()

    def _on_lan_reach_done(self, device: dict, result):
        self.printer_lan_search_btn.setEnabled(True)
        ok, message = result
        if not ok:
            self._set_printer_status(message, "#b91c1c")
            return
        self._select_lan_printer(device["ip"])
        self._set_printer_status(
            f"{message} \"Sinov chop etish\" bilan tekshirib, \"Saqlash\"ni bosing.", "#059669",
        )

    def _select_lan_printer(self, ip: str):
        self.printer_combo.setCurrentIndex(self._add_lan_printer_item(make_tcp_name(ip)))

    def _load_printer_settings(self):
        self.label_width_input.setText(db.get_setting("label_width_mm", "40"))
        self.label_height_input.setText(db.get_setting("label_height_mm", "30"))
        self.label_gap_input.setText(db.get_setting("label_gap_mm", "2"))

    def _read_label_size(self):
        try:
            width = float(self.label_width_input.text().strip().replace(",", "."))
            height = float(self.label_height_input.text().strip().replace(",", "."))
            gap = float(self.label_gap_input.text().strip().replace(",", "."))
        except ValueError:
            return None
        if width <= 0 or height <= 0 or gap < 0:
            return None
        return width, height, gap

    def _save_printer_settings(self):
        printer_name = self._selected_printer()
        if not printer_name:
            self.printer_status_label.setStyleSheet("color:#b91c1c;")
            self.printer_status_label.setText("Avval printer tanlang.")
            return
        size = self._read_label_size()
        if size is None:
            self.printer_status_label.setStyleSheet("color:#b91c1c;")
            self.printer_status_label.setText("Kenglik/balandlik/oraliq son bo'lishi kerak.")
            return
        width, height, gap = size

        db.set_setting("label_printer_name", printer_name)
        db.set_setting("label_width_mm", f"{width:g}")
        db.set_setting("label_height_mm", f"{height:g}")
        db.set_setting("label_gap_mm", f"{gap:g}")
        self.printer_status_label.setStyleSheet("color:#059669;")
        self.printer_status_label.setText(f"Saqlandi: {display_name(printer_name)} ({width:g}x{height:g} mm, oraliq {gap:g} mm)")

    def _test_print(self):
        printer_name = self._selected_printer()
        if not printer_name:
            self.printer_status_label.setStyleSheet("color:#b91c1c;")
            self.printer_status_label.setText("Avval printer tanlang.")
            return
        size = self._read_label_size()
        if size is None:
            self.printer_status_label.setStyleSheet("color:#b91c1c;")
            self.printer_status_label.setText("Kenglik/balandlik/oraliq son bo'lishi kerak.")
            return
        width, height, gap = size

        self.printer_test_btn.setEnabled(False)
        self.printer_status_label.setStyleSheet("color:#64748b;")
        self.printer_status_label.setText("Sinov etiketkasi chop etilmoqda...")

        label = {"qr_data": "https://stockfirm.uz/p/test/"}
        self._print_worker = LabelPrintWorker(printer_name, [label], width, height, gap)
        self._print_worker.succeeded.connect(self._on_test_print_succeeded)
        self._print_worker.failed.connect(self._on_test_print_failed)
        self._print_worker.start()

    def _on_test_print_succeeded(self, count: int):
        self.printer_test_btn.setEnabled(True)
        self.printer_status_label.setStyleSheet("color:#059669;")
        self.printer_status_label.setText("Sinov etiketkasi printerga yuborildi ✓")

    def _on_test_print_failed(self, message: str):
        self.printer_test_btn.setEnabled(True)
        self.printer_status_label.setStyleSheet("color:#b91c1c;")
        self.printer_status_label.setText(message)
