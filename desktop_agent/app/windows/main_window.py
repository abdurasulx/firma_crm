from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QStackedWidget,
    QStackedLayout, QLabel, QMessageBox, QGraphicsOpacityEffect,
)
from PyQt6.QtCore import QThread, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve

from .. import db
from ..scanner_service import ScannerService
from ..camera_recorder_service import CameraRecorderService
from ..scale_service import ScaleService
from ..api_client import ApiError, send_heartbeat, send_logout, normalize_server_url, verify_kiosk_unlock
from ..agent_socket_service import AgentSocketWorker
from .warehouse_list_page import WarehouseListPage
from .employee_scan_widget import EmployeeScanWidget
from .settings_page import SettingsPage, _ApiCallWorker
from .startup_check_page import StartupCheckPage

SCAN_CARD_WIDTH = 460

HEARTBEAT_INTERVAL_MS = 25_000  # server tomonida AGENT_ONLINE_THRESHOLD_SECONDS=90ga mos, bir necha marta o'tkazib yuborilsa ham bardosh beradigan zaxira bilan


class _HeartbeatWorker(QThread):
    """Har chaqirilishda bitta heartbeat so'rovini fon oqimida yuboradi —
    server sekin javob bersa yoki umuman ulanmasa ham asosiy oyna
    muzlab qolmasligi uchun. Tarmoq xatolari (ulanmadi, timeout va h.k.)
    jimgina e'tiborsiz qoldiriladi — keyingisida qayta urinadi. Lekin
    401 (token yaroqsiz — masalan boshqa kompyuterda qayta login
    qilingani uchun bekor bo'lgan) alohida ushlanib, `token_invalid`
    signali orqali bildiriladi — shu orqali stansiya "kirib ketilgan"
    holatini darhol (indikatsiya kutilmasdan) sezadi."""
    token_invalid = pyqtSignal()

    def __init__(self, server_url: str, token: str):
        super().__init__()
        self._server_url = server_url
        self._token = token
        self.finished.connect(self.wait)

    def run(self):
        try:
            send_heartbeat(self._server_url, self._token)
        except ApiError as exc:
            if exc.status_code == 401:
                self.token_invalid.emit()
        except Exception:  # noqa: BLE001 — heartbeat muvaffaqiyatsiz bo'lishi jiddiy emas, keyingisida qayta urinadi
            pass


class _LogoutWorker(QThread):
    """Dastur yopilayotganda (`closeEvent`) bitta "men oflaynman" so'rovini
    yuboradi — natijasi kutilmaydi (`closeEvent` uni bir necha soniya
    kutadi, xolos), tarmoq sekin/o'chgan bo'lsa ham dastur yopilishini
    abadiy to'sib qo'ymasligi kerak."""
    def __init__(self, server_url: str, token: str):
        super().__init__()
        self._server_url = server_url
        self._token = token

    def run(self):
        try:
            send_logout(self._server_url, self._token)
        except Exception:  # noqa: BLE001 — yopilish har qanday holatda ham davom etishi kerak
            pass


class MainWindow(QMainWindow):
    """Skaner — hech qanday menyu/sahifa emas. `ScannerService` dastur
    ishga tushgan zahotidan boshlab fonda doimiy ishlaydi (sozlangan
    kamera yoki qo'lda HID skaner orqali) — foydalanuvchi istalgan payt
    (dastur qaysi sahifada bo'lishidan qat'iy nazar) badge'ini ko'rsatsa,
    kod shu firmaga tegishli bo'lib chiqsa, ma'lumoti oyna markazida
    xira fon ustida suzuvchi kartada darhol chiqadi (138-143-qadamlar —
    avval alohida popup oyna, so'ng o'ng tomondagi tor panel edi —
    matn kesilib qolgani uchun markazlashtirilgan kengroq kartaga
    o'zgartirildi).

    Dastur har ishga tushganda avval qurilma-tekshiruv sahifasi
    (`StartupCheckPage`) ko'rsatiladi, "Davom etish" bosilgach asosiy
    qobiqqa o'tiladi."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("StockFirm Desktop Agent")
        self.resize(1000, 640)

        self.root_stack = QStackedWidget()
        self.setCentralWidget(self.root_stack)

        # `scale_service` bu yerda hali yaratilmagan (pastda, `_scan_widget`
        # tayyor bo'lgandan keyin) — lambda uni FAQAT chaqirilganda (keyinroq,
        # `.show()`dan keyin) izlaydi, shuning uchun xavfsiz. Alohida COM-port
        # ulanishi ochish o'rniga, allaqachon fonda ishlayotgan xizmatning
        # o'zidan so'raladi (176-177-qadamlarga qarang).
        self.startup_check_page = StartupCheckPage(
            scale_checker=lambda: self.scale_service.is_connected(),
            scanner_checker=lambda: self.scanner_service.is_camera_connected(),
            ombor_checker=lambda: self.camera_recorder_service.connected_camera_count(),
        )
        self.startup_check_page.continue_requested.connect(self._on_startup_check_continue)
        self.startup_check_page.open_settings_requested.connect(self._on_startup_open_settings)
        self.root_stack.addWidget(self.startup_check_page)  # index 0

        shell = QWidget()
        self._shell_layers = QStackedLayout(shell)
        self._shell_layers.setStackingMode(QStackedLayout.StackingMode.StackAll)
        shell_layers = self._shell_layers

        normal_content = QWidget()
        root_layout = QHBoxLayout(normal_content)

        # Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("background:#0f172a;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)

        brand = QLabel("StockFirm\nAgent")
        brand.setStyleSheet("color:white; font-size:16px; font-weight:800; padding:0 16px 20px 16px;")
        sidebar_layout.addWidget(brand)

        self.nav_buttons = []
        self.warehouse_btn = self._make_nav_button("📦  Omborlar")
        self.settings_btn = self._make_nav_button("⚙️  Sozlamalar")
        sidebar_layout.addWidget(self.warehouse_btn)
        sidebar_layout.addWidget(self.settings_btn)
        sidebar_layout.addStretch(1)

        # Kiosk qulfi — dastur ochilganda standart holat "qulflangan":
        # sidebar navigatsiyasi (Omborlar/Sozlamalar) va oynani yopish
        # bloklanadi, faqat xodim-skan paneli (kameradan, mishka/klaviatura
        # emas) ishlab turadi. Faqat firma egasining shaxsiy QR kodini
        # (profildagi "Desktop Agent QR-login" kartasi) skanerlash orqali
        # vaqtincha ochiladi — "Qulflash" tugmasi bosilguncha ochiq qoladi.
        self.kiosk_status_label = QLabel()
        self.kiosk_status_label.setWordWrap(True)
        self.kiosk_status_label.setStyleSheet("color:#94a3b8; font-size:11px; padding:0 16px;")
        sidebar_layout.addWidget(self.kiosk_status_label)

        self.kiosk_lock_btn = QPushButton("🔒  Qulflash")
        self.kiosk_lock_btn.setStyleSheet(
            "QPushButton { margin:8px 16px 0 16px; padding:8px; color:white; "
            "background:#334155; border:none; border-radius:8px; }"
            "QPushButton:hover { background:#475569; }"
        )
        self.kiosk_lock_btn.clicked.connect(self._on_kiosk_lock_btn_clicked)
        sidebar_layout.addWidget(self.kiosk_lock_btn)

        root_layout.addWidget(sidebar)

        # Ombor kamerasi — voqea (QR skaner/tasdiqlash) atrofida video
        # yozish xizmati. Dastur ochiq turgan davomida fonda ishlaydi
        # (`ScannerService` kabi); sozlangan ombor kamerasi bo'lmasa,
        # hech narsa qilmaydi.
        self.camera_recorder_service = CameraRecorderService(self)

        # Pages
        self.stack = QStackedWidget()
        self.warehouse_page = WarehouseListPage(on_cameras_changed=self.camera_recorder_service.reload)
        self.settings_page = SettingsPage(
            on_synced=self.warehouse_page.refresh,
            on_scanner_changed=self._reload_scanner,
            on_login_succeeded=self._on_login_succeeded,
            on_scale_changed=self._reload_scale,
            on_recheck_devices=self._on_recheck_devices_requested,
            on_logout=self._on_logout,
        )
        self.settings_page.session_expired.connect(self._handle_token_invalid)
        self.stack.addWidget(self.warehouse_page)
        self.stack.addWidget(self.settings_page)
        root_layout.addWidget(self.stack, 1)

        self.warehouse_btn.clicked.connect(lambda: self._select_page(0))
        self.settings_btn.clicked.connect(lambda: self._select_page(1))
        self._select_page(0)

        shell_layers.addWidget(normal_content)

        # Skan-overlay — oyna markazida, xira fon ustida suzuvchi karta
        # (avvalgi popup, so'ng o'ng tor panel o'rniga — matn kesilib
        # qolgani uchun kengroq va markazlashtirilgan qilindi).
        # `QStackedLayout(StackAll)` orqali `normal_content` bilan bir
        # xil hajmda qoplab turadi, faqat `setVisible()` bilan
        # ko'rinish/yashirish boshqariladi.
        self._scan_overlay = QWidget()
        self._scan_overlay.setStyleSheet("background: rgba(15, 23, 42, 0.55);")
        self._scan_overlay.setVisible(False)
        overlay_layout = QVBoxLayout(self._scan_overlay)
        overlay_layout.addStretch(1)
        center_row = QHBoxLayout()
        center_row.addStretch(1)

        card = QWidget()
        card.setFixedWidth(SCAN_CARD_WIDTH)
        card.setStyleSheet("background:white; border-radius:16px;")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)

        self._scan_widget = EmployeeScanWidget(camera_recorder=self.camera_recorder_service, parent=card)
        self._scan_widget.close_requested.connect(self._hide_scan_overlay)
        # Skanerlash/tortish/yetkazib berish kabi ISTALGAN so'rov token
        # eskirganini (401) sezishi mumkin, faqat heartbeatni kutmasdan —
        # heartbeatdagi bilan bir xil avtomatik logout oqimi ishlatiladi.
        self._scan_widget.session_expired.connect(self._handle_token_invalid)
        self._scan_widget.ega_badge_scanned.connect(self._on_ega_badge_scanned)
        card_layout.addWidget(self._scan_widget)

        center_row.addWidget(card)
        center_row.addStretch(1)
        overlay_layout.addLayout(center_row)
        overlay_layout.addStretch(1)

        self._scan_opacity_effect = QGraphicsOpacityEffect(card)
        card.setGraphicsEffect(self._scan_opacity_effect)
        self._scan_fade_anim = QPropertyAnimation(self._scan_opacity_effect, b"opacity", self)
        self._scan_fade_anim.setDuration(280)
        self._scan_fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        shell_layers.addWidget(self._scan_overlay)
        shell_layers.setCurrentIndex(0)  # normal_content tepada, overlay boshida yashirin

        self.root_stack.addWidget(shell)  # index 1

        # Real bug (foydalanuvchi topdi): qurilma-tekshiruv sahifasi
        # (printer/tarozi/kamera) HAR DOIM birinchi ko'rsatilardi — hali
        # login qilinmagan stansiyada ham. Bu ma'nosiz: login yo'q bo'lsa
        # qurilmalarni ishlatishning o'zi mumkin emas (xodim skanerlash,
        # etiketka chop etish va h.k. barchasi login qilingan stansiyaga
        # bog'liq). Endi: token yo'q bo'lsa — tekshiruvni butunlay
        # o'tkazib yuborib, to'g'ridan-to'g'ri Sozlamalar (login) sahifasi
        # ko'rsatiladi; login qilingandan keyin esa tekshiruv haqiqiy
        # ma'noga ega bo'lganda (`_on_login_succeeded`) ishga tushadi.
        if db.get_setting("agent_token", ""):
            self.root_stack.setCurrentIndex(0)
        else:
            self.root_stack.setCurrentIndex(1)
            self._select_page(1)

        # Fon skaner xizmati — hech qanday sahifaga bog'liq emas, dastur
        # ochiq turgan davomida doimiy ishlaydi.
        self.scanner_service = ScannerService(self)
        self.scanner_service.code_scanned.connect(self._on_code_scanned)

        # Tarozi xizmati — sozlanmagan bo'lsa hech narsa qilmaydi
        # (qo'lda kiritish avvalgidek ishlayveradi). Jonli vazn faqat
        # tortish kartochkasi ochiq turganda ishlatiladi.
        self.scale_service = ScaleService(on_weight_changed=self._scan_widget.update_live_weight)

        # Real-vaqtli onlayn/oflayn holat — hech qanday skanerlash
        # faoliyati bo'lmasa ham, stansiya "tirikligini" muntazam
        # bildirib turadi (web dashboardda qizil ogohlantirish
        # ko'rsatilmasligi uchun).
        self._heartbeat_worker: _HeartbeatWorker | None = None
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(HEARTBEAT_INTERVAL_MS)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._heartbeat_timer.start()
        self._send_heartbeat()

        # Real-vaqtli sinxronlash — qo'lda "Sinxronlash" tugmasi endi yo'q
        # (91-qadam). Server tomonida biror narsa o'zgarsa (masalan ombor
        # qo'shilsa), shu WebSocket ulanishi orqali darhol xabar keladi va
        # `warehouse_page` o'zi (jimgina, faqat haqiqiy o'zgarish bo'lsa)
        # yangilanadi.
        self._socket_worker: AgentSocketWorker | None = None
        self._restart_socket_worker()

        # 219-qadamda qo'shilgan past darajali klaviatura ilgichi
        # (WH_KEYBOARD_LL, Win/Alt+Tab bloklash uchun) BUTUNLAY OLIB
        # TASHLANDI (223-qadam, real ishlab chiqarishda topilgan xato):
        # bunday global ilgich BUTUN TIZIM darajasida ishlaydi — agar
        # Python callback'imiz biroz sekinlik qilsa (GIL/interpretator
        # tezligi tufayli haqiqiy xavf), Windows shu ilgichni kutib,
        # BOSHQA HAMMA dastur uchun ham klaviatura kiritishni kechiktirib/
        # bloklab qo'yadi — aynan shu sabab HID skaner (klaviatura sifatida
        # ishlaydi) va boshqa dasturlarda yozish ishlamay qoldi. Win/Alt+Tab
        # kabi tizim buyruqlarini haqiqatan ishonchli va xavfsiz cheklash
        # FAQAT operatsion tizim darajasida (Windows Kiosk/Assigned Access
        # yoki Group Policy) — xuddi Ctrl+Alt+Delete kabi — amalga
        # oshirilishi kerak, dasturiy global ilgich orqali emas.
        self._kiosk_unlock_worker: _ApiCallWorker | None = None
        # Real bug (foydalanuvchi topdi): bu yerda har doim `True`
        # bilan qulflanardi — HALI LOGIN QILINMAGAN holatda ham.
        # Natijada: stansiya hech qachon login qilmagan (yoki token
        # tozalangan) bo'lsa ham, dastur "qulflangan" holatda ochilib,
        # Sozlamalar/Omborlar tugmalari o'chirilgan, oyna yopilmaydi —
        # lekin qulfni ochish uchun kerak bo'lgan `agent_verify_kiosk_unlock`
        # so'rovi ALLAQACHON login qilingan stansiyani talab qiladi
        # (saqlangan `server_url`ga tayanadi). Hali login qilinmagan
        # stansiyada bu — chiqib ketib bo'lmaydigan tuzoq. Qulf faqat
        # ALLAQACHON login qilingan stansiyada (kiosk rejimiga
        # kirilgandan keyin) ma'noga ega — shuning uchun endi haqiqiy
        # login holatiga qarab qaror qilinadi. Bu yerda hali umuman
        # QULFLANMAYDI — qulf faqat qurilma-tekshiruv MUVAFFAQIYATLI
        # o'tib, asosiy qobiqqa kirilganda yoqiladi
        # (`_on_startup_check_continue`), aks holda (masalan qurilma
        # nosoz chiqib Sozlamalarga o'tilganda) Omborlar/Sozlamalar
        # bloklanib, kameralarni/printerni sozlab bo'lmay qolardi.
        self._set_kiosk_locked(False)

    def _on_startup_check_continue(self):
        self.root_stack.setCurrentIndex(1)
        self._set_kiosk_locked(True)
        # Kiosk rejimi — dastur ishga tushganda avtomatik to'liq ekranga
        # o'tadi (foydalanuvchi so'rovi: "dasturga kirishi bilan full
        # screen bo'lib qolishi kerak").
        #
        # **Muhim (real ishlab chiqarish xatosi, 232-qadam)**: avval
        # bu yerda `hide_taskbar()` ham chaqirilardi (`ShowWindow`
        # orqali `Shell_TrayWnd`ni yashirish) — lekin bu Windows
        # DARAJASIDAGI GLOBAL holat, dastur jarayoniga BOG'LIQ EMAS.
        # Agar dastur "Vazifalar menejeri"/`taskkill` orqali majburan
        # o'chirilsa, yiqilib tushsa (crash) yoki boshqa har qanday
        # NOTO'G'RI (closeEvent'dan tashqari) usulda tugasa —
        # `show_taskbar()` HECH QACHON chaqirilmaydi va foydalanuvchi
        # butun kompyuterda taskbarsiz qolib ketadi (aynan shu holat
        # real sinovda yuz berdi). Xavf foyda-zarar nisbatiga
        # nomutanosib bo'lgani uchun BUTUNLAY OLIB TASHLANDI.
        self.showFullScreen()

    def _on_startup_open_settings(self):
        """Qurilma-tekshiruv sahifasida birror qurilma nosoz chiqsa
        (176-qadam) — to'g'ridan-to'g'ri Sozlamalar sahifasiga o'tiladi
        (kiosk hali ham qulflangan holatda qoladi, faqat shu bir martalik
        dastlabki navigatsiya dasturiy ravishda amalga oshadi)."""
        self.root_stack.setCurrentIndex(1)
        self._select_page(1)

    def _on_recheck_devices_requested(self):
        """Sozlamalar sahifasidagi "Qurilmalarni qayta tekshirish"
        tugmasi — qurilma-tekshiruv sahifasiga qaytib, jonli tekshiruvni
        qaytadan boshlaydi."""
        self.root_stack.setCurrentIndex(0)
        self.startup_check_page.refresh()

    def _on_login_succeeded(self):
        """Sozlamalar sahifasida login muvaffaqiyatli bo'lgach chaqiriladi
        (yangi login yoki `_handle_token_invalid`dan keyingi qayta-login) —
        WebSocket va heartbeat'ni (agar `_handle_token_invalid` to'xtatgan
        bo'lsa) qayta ishga tushiradi."""
        self._restart_socket_worker()
        if not self._heartbeat_timer.isActive():
            self._heartbeat_timer.start()
        self._send_heartbeat()
        self.warehouse_page.refresh()
        # Qurilma-tekshiruv sahifasi bu paytgacha o'tkazib yuborilgan
        # edi (login yo'q holatda ma'nosiz edi) — endi, aynan login
        # qilingandan KEYIN, birinchi marta ishga tushiriladi.
        #
        # **Muhim (real bug, foydalanuvchi topdi)**: bu yerda avval
        # `_set_kiosk_locked(True)` DARHOL chaqirilardi — birinchi
        # marta login qilingan (dastlabki sozlash) stansiyada bu
        # Omborlar bo'limini bloklab qo'yardi, holbuki ega hali
        # kameralarni (Omborlar → Kameralar) va printer/tarozi
        # (Sozlamalar)ni SOZLASHI kerak. Kiosk qulfi endi FAQAT
        # qurilma-tekshiruv MUVAFFAQIYATLI o'tib, "Davom etish"
        # bosilib, asosiy qobiqqa kirilganda yoqiladi
        # (`_on_startup_check_continue`) — shu paytgacha erkin
        # navigatsiya (Omborlar/Sozlamalar) ochiq qoladi.
        self.root_stack.setCurrentIndex(0)
        self.startup_check_page.refresh()

    def _restart_socket_worker(self):
        """Stansiya login qilingach (yoki dastur ochilganda, agar
        avvalroq login qilingan bo'lsa) chaqiriladi — WebSocket
        ulanishini (qayta) boshlaydi."""
        token = db.get_setting("agent_token", "")
        if not token:
            return
        server_url = db.get_setting("server_url", "")
        if self._socket_worker is not None:
            self._socket_worker.stop()
        self._socket_worker = AgentSocketWorker(server_url, token)
        self._socket_worker.notification_received.connect(self._on_ws_notification)
        self._socket_worker.start()

    def _on_ws_notification(self, data: dict):
        if data.get("event") == "ombor_changed":
            self.warehouse_page.sync_from_server(silent=True)

    def _make_nav_button(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setStyleSheet(
            """
            QPushButton { text-align:left; padding:12px 16px; color:#cbd5e1; background:transparent; border:none; font-size:14px; }
            QPushButton:checked { background:#1e293b; color:white; font-weight:700; }
            QPushButton:hover { background:#1e293b; }
            """
        )
        self.nav_buttons.append(btn)
        return btn

    def _select_page(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        if index == 0:
            self.warehouse_page.refresh()

    def _reload_scanner(self):
        """Sozlamalar sahifasida skaner kamerasi qayta sozlangach chaqiriladi."""
        self.scanner_service.reload()

    def _reload_scale(self):
        """Sozlamalar sahifasida tarozi COM porti qayta saqlangach chaqiriladi."""
        self.scale_service.reload()

    def _send_heartbeat(self):
        token = db.get_setting("agent_token", "")
        if not token:
            return  # hali login qilinmagan — heartbeat yuborishning ma'nosi yo'q
        server_url = db.get_setting("server_url", "")
        old = self._heartbeat_worker
        if old is not None and old.isRunning():
            old.wait()
        self._heartbeat_worker = _HeartbeatWorker(server_url, token)
        self._heartbeat_worker.token_invalid.connect(self._handle_token_invalid)
        self._heartbeat_worker.start()

    def _on_logout(self):
        """Sozlamalar sahifasida "Chiqish" bosilib, token tozalanganda —
        login yo'q endi, shuning uchun kiosk qulfi ham bo'shatiladi
        (aks holda login yo'q/qulflangan tuzog'i qayta yuzaga keladi)."""
        self._stop_session_workers()
        self._set_kiosk_locked(False)
        self.warehouse_page.refresh()

    def _stop_session_workers(self):
        """Faol sessiyaga bog'liq fon jarayonlarini (heartbeat, WS ulanish)
        to'xtatadi — token bekor qilinganda (`_handle_token_invalid`) ham,
        foydalanuvchi qo'lda "Chiqish"ni bosganda (`SettingsPage`) ham
        chaqiriladi."""
        self._heartbeat_timer.stop()
        if self._socket_worker is not None:
            self._socket_worker.stop()
            self._socket_worker = None

    def _handle_token_invalid(self):
        """Boshqa kompyuterda/qurilmada shu hisob bilan qayta login
        qilingani uchun bu stansiyaning tokeni server tomonda bekor
        qilingan (bitta hisob — faqat bitta faol Desktop Agent
        sessiyasi qoidasi). Mahalliy keshni tozalab, sozlamalar
        (login) sahifasiga qaytaramiz."""
        if not db.get_setting("agent_token", ""):
            return  # allaqachon logout qilingan (masalan foydalanuvchi o'zi chiqqan)
        self._stop_session_workers()
        db.set_setting("agent_token", "")
        # Token bekor qilindi — endi login qilinmagan, shuning uchun
        # kiosk qulfi ham ma'nosiz (aks holda yuqoridagi tuzoq qayta
        # takrorlanadi: login yo'q, lekin qulflangan).
        self._set_kiosk_locked(False)
        self.warehouse_page.refresh()
        QMessageBox.warning(
            self, "Sessiya yopildi",
            "Boshqa kompyuter yoki qurilmada shu hisob bilan tizimga kirilgani uchun "
            "bu stansiya tizimdan chiqarildi. Davom etish uchun qaytadan kiring.",
        )
        self.settings_page.show_login_required()
        self._select_page(1)

    def _on_code_scanned(self, kod: str):
        if kod.startswith("AGENTQR|"):
            # Real bug (foydalanuvchi topdi): `_kiosk_locked` dastur
            # ishga tushganda har doim `True` bilan boshlanadi — HALI
            # LOGIN QILINMAGAN bo'lsa ham. Shuning uchun avval bu yer
            # faqat `_kiosk_locked`ga qarab qaror qilardi: birinchi
            # (hali login qilinmagan) skanerlash NOTO'G'RI "kiosk
            # qulfini ochish" so'rovi deb talqin qilinardi (server buni
            # ham qabul qilib "Qulf ochildi" derdi), faqat IKKINCHI
            # skanerlashda haqiqiy login sodir bo'lardi. Endi avval
            # HAQIQIY login holati (`agent_token` bor-yo'qligi)
            # tekshiriladi — hali login qilinmagan bo'lsa, DOIM login
            # oqimiga yo'naltiriladi, `_kiosk_locked`dan qat'i nazar.
            is_logged_in = bool(db.get_setting("agent_token", ""))
            if is_logged_in and self._kiosk_locked:
                # Allaqachon login qilingan, faqat kiosk ekrani
                # qulflangan — bu QR kiosk qulfini ochish so'rovi
                # (faqat ega'ning QR kodi qabul qilinadi, server
                # tomonda tekshiriladi).
                self._handle_kiosk_unlock_qr(kod)
            else:
                self._handle_agent_login_qr(kod)
            return

        self._scan_overlay.setVisible(True)
        # `QStackedLayout(StackAll)`da ham faqat "joriy" widget tepada
        # chiqadi — shuning uchun overlayni ko'rsatishda uni aniq
        # `setCurrentWidget` qilish shart (oddiy `raise_()` yetarli emas).
        self._shell_layers.setCurrentWidget(self._scan_overlay)
        self._scan_widget.handle_scanned_code(kod)
        self._play_scan_fade_in()

    def _handle_agent_login_qr(self, kod: str):
        """ERP profilida ko'rsatilgan shifrlangan "Desktop Agent QR-login"
        kodi skanerlandi (145-qadam) — `AGENTQR|<subdomain>|<shifrlangan_qism>`
        formatida. Login holatidan qat'i nazar qayta skanerlash orqali
        boshqa hisobga o'tish ham mumkin (masalan stansiyani boshqa
        xodimga qayta belgilash uchun)."""
        parts = kod.split("|", 2)
        if len(parts) != 3:
            # Kamera zich QR'ni TO'LIQ/TO'G'RI o'qiy olmagan bo'lishi
            # mumkin (real muammo — payload ~200 belgi, oddiy xodim
            # badge'idan ancha zichroq panjara talab qiladi). Avval bu
            # yerda JIMGINA qaytilar edi — foydalanuvchi hech qanday
            # feedback olmasdan "hech narsa bo'lmadi" deb qolardi.
            self._select_page(1)
            self.settings_page.status_label.setStyleSheet("color:#b91c1c;")
            self.settings_page.status_label.setText(
                "QR kod to'liq o'qilmadi — kamerani QR'ga yaqinroq/tekisroq tuting va qayta "
                "skanerlang, yoki login/parol bilan kiring.",
            )
            return
        _, subdomain, qr_payload = parts
        server_url = normalize_server_url(subdomain)
        self._select_page(1)
        self.settings_page.start_qr_login(subdomain, qr_payload, server_url)

    def _handle_kiosk_unlock_qr(self, kod: str):
        """Kiosk qulflangan holatda `AGENTQR|...` skanerlanganda chaqiriladi
        — stansiyaning o'z login holatiga tegilmaydi, faqat serverga
        so'rov yuborib QR kod chindan ham firma egasiga tegishli ekanini
        tekshiradi (`agent_verify_kiosk_unlock`, token yaratilmaydi).

        **Muhim (topilgan real bug)**: `_handle_agent_login_qr`dan farqli
        (u LOGIN uchun ishlatiladi — stansiya hali hech qanday serverga
        ulanmagan bo'lishi mumkin, shuning uchun manzil skanerlangan
        subdomendan `normalize_server_url()` orqali QURILADI), bu yerda
        stansiya ALLAQACHON muayyan serverga ulangan/login qilingan —
        shuning uchun o'sha MAVJUD (`db`da saqlangan) `server_url`
        ishlatilishi kerak, subdomendan qayta qurilmasligi kerak. Aks
        holda (masalan mahalliy/test server bilan ishlaganda)
        `normalize_server_url()` har doim `https://<subdomen>.stockfirm.uz`
        (production manzili) deb hisoblab, butunlay boshqa (yoki
        mavjud bo'lmagan) serverga so'rov yuborardi — natijada
        tushunarsiz "QR kod tasdiqlanmadi" xatosi chiqardi, garchi QR
        kodning o'zi to'g'ri va server ishlab tursa ham."""
        parts = kod.split("|", 2)
        if len(parts) != 3:
            # Kamera zich QR'ni TO'LIQ/TO'G'RI o'qiy olmagan bo'lishi
            # mumkin — avval jimgina qaytilar edi, foydalanuvchi hech
            # qanday feedback olmasdi.
            self.kiosk_status_label.setText(
                "⚠ QR kod to'liq o'qilmadi — kamerani QR'ga yaqinroq/tekisroq tutib qayta skanerlang.",
            )
            return
        _, subdomain, qr_payload = parts
        server_url = db.get_setting("server_url", "") or normalize_server_url(subdomain)

        self.kiosk_status_label.setText("🔒 QR kod tekshirilmoqda...")

        old = self._kiosk_unlock_worker
        if old is not None and old.isRunning():
            old.wait()
        self._kiosk_unlock_worker = _ApiCallWorker(verify_kiosk_unlock, server_url, subdomain, qr_payload)
        self._kiosk_unlock_worker.succeeded.connect(self._on_kiosk_unlock_succeeded)
        self._kiosk_unlock_worker.failed.connect(self._on_kiosk_unlock_failed)
        self._kiosk_unlock_worker.start()

    def _on_ega_badge_scanned(self, name: str):
        """Ega o'zining ODDIY shaxsiy QR badge'ini (maxsus "Desktop Agent
        QR-login" emas) ko'rsatganda — agar kiosk hozir qulflangan bo'lsa,
        shu orqali ham ochiladi (foydalanuvchi talabi: alohida-alohida QR
        qidirishning hojati yo'q). Server allaqachon `scan()` orqali bu
        badge shu firmaning `ega`siga tegishli ekanini tasdiqlagan —
        qo'shimcha so'rov shart emas."""
        if not self._kiosk_locked:
            return  # allaqachon ochiq — oddiy skan, hech narsa qilinmaydi
        self._set_kiosk_locked(False)
        QMessageBox.information(
            self, "Qulf ochildi",
            f"{name} tomonidan qulf ochildi — endi mishka/klaviatura orqali "
            "boshqarish mumkin. Ishni tugatgach \"Qulflash\" tugmasini bosing.",
        )

    def _on_kiosk_unlock_succeeded(self, result: dict):
        self._set_kiosk_locked(False)
        QMessageBox.information(
            self, "Qulf ochildi",
            f"{result.get('name', 'Ega')} tomonidan qulf ochildi — endi mishka/klaviatura orqali "
            "boshqarish mumkin. Ishni tugatgach \"Qulflash\" tugmasini bosing.",
        )

    def _on_kiosk_unlock_failed(self, message: str):
        self.kiosk_status_label.setText(
            "🔒 Qulflangan — ega profilidagi \"Desktop Agent QR-login\" kodini skanerlang "
            "(shaxsiy badge emas)."
        )
        QMessageBox.warning(self, "Qulf ochilmadi", message)

    def _on_kiosk_lock_btn_clicked(self):
        """"Qulflash" tugmasi — real bug (foydalanuvchi topdi): bu
        avval login holatidan qat'i nazar ishlar edi, ya'ni hali login
        qilinmagan stansiyada ham bosilsa, xuddi 236-qadamdagi tuzoqni
        FOYDALANUVCHI O'ZI qo'lda qayta yaratardi (qulf ochish esa
        ALLAQACHON login qilingan stansiyani talab qiladi). Qulflash
        faqat ALLAQACHON login qilingan stansiyada ma'noga ega."""
        if not db.get_setting("agent_token", ""):
            QMessageBox.warning(
                self, "Login qilinmagan",
                "Hali stansiya login qilinmagan — avval Sozlamalarda login qiling, "
                "keyingina kiosk qulflash mumkin bo'ladi.",
            )
            return
        self._set_kiosk_locked(True)

    def _set_kiosk_locked(self, locked: bool):
        """Kiosk qulfi holatini o'rnatadi. Qulflanganda: sidebar
        navigatsiyasi (Omborlar/Sozlamalar) va oynani yopish bloklanadi —
        faqat kamera orqali xodim-skan/badge oqimi (mishka/klaviatura emas)
        ishlab turadi. Ochilganda: hammasi avvalgidek erkin."""
        self._kiosk_locked = locked
        self.warehouse_btn.setEnabled(not locked)
        self.settings_btn.setEnabled(not locked)
        self.kiosk_lock_btn.setVisible(not locked)
        if locked:
            self.kiosk_status_label.setText(
            "🔒 Qulflangan — ega profilidagi \"Desktop Agent QR-login\" kodini skanerlang "
            "(shaxsiy badge emas)."
        )
        else:
            self.kiosk_status_label.setText("🔓 Qulf ochiq.")

    def _hide_scan_overlay(self):
        """`EmployeeScanWidget.close_requested` kelganda (sessiya
        tugagach yoki "Yopish" bosilgach) — markaziy karta yashiriladi,
        asosiy sahifa (Omborlar/Sozlamalar) yana to'liq ko'rinadi."""
        self._scan_overlay.setVisible(False)
        self._shell_layers.setCurrentIndex(0)

    def _play_scan_fade_in(self):
        self._scan_fade_anim.stop()
        self._scan_opacity_effect.setOpacity(0.0)
        self._scan_fade_anim.setStartValue(0.0)
        self._scan_fade_anim.setEndValue(1.0)
        self._scan_fade_anim.start()

    def closeEvent(self, event):
        if self._kiosk_locked:
            # Kiosk qulflangan holatda dasturni yopish bloklanadi (oyna
            # sarlavhasidagi X tugmasi ham shu orqali to'xtaydi) — faqat
            # ega QR kodini skanerlab qulfni ochgach yopish mumkin.
            event.ignore()
            QMessageBox.warning(
                self, "Qulflangan",
                "Dastur kiosk rejimida qulflangan. Yopish uchun avval ega profilidagi "
                "\"Desktop Agent QR-login\" kodini skanerlang (shaxsiy badge emas).",
            )
            return

        self._heartbeat_timer.stop()
        # Dashboardga "oflayn"ligimizni 90 soniyalik heartbeat-kutish
        # oynasini kutmasdan darhol bildiramiz — foydalanuvchi
        # tomonidan aynan shu narsa so'ralgan ("agentdan chiqishim
        # bilanoq oflaynligi haqida ma'lumot yo'q"). Best-effort: 2
        # soniyadan ortiq kutmaymiz, tarmoq sekin/o'chgan bo'lsa ham
        # dastur yopilishi to'xtab qolmasligi kerak.
        token = db.get_setting("agent_token", "")
        if token:
            server_url = db.get_setting("server_url", "")
            logout_worker = _LogoutWorker(server_url, token)
            logout_worker.start()
            logout_worker.wait(2000)
        if self._socket_worker is not None:
            self._socket_worker.stop()
        self.scanner_service.stop()
        self.camera_recorder_service.stop()
        self.scale_service.stop()
        super().closeEvent(event)
