import math
import time
import webbrowser

import requests

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QLineEdit,
    QScrollArea, QGridLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap

from .. import db
from ..api_client import (
    fetch_material_requests, weigh_material_request, fetch_miqdor_requests,
    approve_miqdor_qoshish, scan_delivery_serial, finalize_yuklama, toggle_attendance, scan, ApiError,
    weigh_task_pickup, fetch_my_task_pickups, fetch_pending_print_batch, mark_batch_printed,
    fetch_delivery_requests, report_print_result,
)
from ..label_printer_service import LabelPrintWorker

SESSION_TIMEOUT_SECONDS = 60
# Yuklama (yetkazib beruvchi) rejimida mahsulotlar omborda bir-biridan
# uzoqroq joylashgan bo'lishi mumkin — har bir skanerlash orasida
# yurish vaqtiga yetadigan uzunroq muddat (oxirgi urinishdan 2 daqiqa).
DELIVERY_SESSION_TIMEOUT_SECONDS = 120

# QR-yorliq partiyasi ekranda hech qanday tugmasiz ko'rsatiladigan muddat
# (kiosk stansiyasida xodimning mishka/klaviaturasi bo'lmasligi mumkin —
# tasdiqlash tugmasi ishlatilmaydi). Shundan keyin navbat o'zi davom etadi.
PRINT_BATCH_DISPLAY_MS = 8000

# Bitta QR-yorliq partiyasi shu muddat ichida ALLAQACHON ko'rsatilgan/
# chop etilgan bo'lsa, qayta badge skanerlansa ham (server hali
# "chop etildi" deb ulgurmagan bo'lsa ham) qayta ko'rsatilmaydi —
# `_mark_batch_printed`ning asinxron javobi kelguncha bo'lgan poyga
# oynasini yopish uchun (server-side muddat, `BADGE_SESSION_MAX_AGE`
# kabi, bundan ancha uzunroq — bu faqat qisqa amaliy zaxira).
RECENTLY_SHOWN_BATCH_TTL_SECONDS = 60

# `_mark_batch_printed` muvaffaqiyatsiz bo'lsa (tarmoq uzilishi/vaqtinchalik
# server javobsizligi) necha marta va qancha oraliqda qayta uriniladi.
# Muhim: bu muvaffaqiyatsizlik jim yutilsa, server `labels_printed`ni
# HECH QACHON True qilmaydi va xodim 60s (RECENTLY_SHOWN_BATCH_TTL_SECONDS)
# dan keyin qayta badge skanerlaganda xuddi shu partiya YANA ko'rsatiladi
# — real sinovda "bitta QR ikki marta chiqmoqda" deb xabar qilingan holat
# aynan shu edi (DB'da haqiqiy dublikat yo'qligi alohida tekshirilgan).
MARK_PRINTED_MAX_ATTEMPTS = 5
MARK_PRINTED_RETRY_MS = 3000

# Tarozi jonli ulangan holatda tortishni to'liq avtomatlashtirish uchun
# (158-qadamdan keyin, foydalanuvchi so'rovi bo'yicha) — qiymat shu
# muddat davomida (soniyada) deyarli o'zgarmasa "barqaror" deb topiladi
# va avtomatik yuborilaadi (qo'lda "Tekshirish" bosish shart emas).
SCALE_STABLE_SECONDS = 0.8
SCALE_STABLE_THRESHOLD_KG = 0.01
# Shundan past qiymat — mahsulot hali tarozi ustiga qo'yilmagan yoki
# (tasdiqlangandan keyin) tarozidan olib tashlangan deb hisoblanadi.
# Real ishlab chiqarishda 20g juda "yumshoq" chiqdi — xodim materialni
# hali TO'LIQ olib ulgurmasdan (masalan idishda ozgina qolgan, yoki
# tarozi noldan sal chetga chiqib turgan holatda) allaqachon "bo'sh" deb
# hisoblanib, keyingi mahsulotni tortish so'ralib qolardi ("shoshib
# qolyapti" shikoyati). Chegara qattiqlashtirildi.
SCALE_EMPTY_THRESHOLD_KG = 0.005
# Bo'shashni tasdiqlashda oddiy tortish-barqarorligidan (0.8s) ko'ra
# UZOQROQ barqarorlik talab qilinadi — xodim materialni olib
# tashlayotganda tarozi bir necha soniya davomida turli oraliq
# qiymatlardan o'tadi, shulardan biri tasodifan bir lahzaga barqaror
# ko'rinib, chalg'itmasligi uchun.
SCALE_EMPTY_STABLE_SECONDS = 1.5

# Jonli tarozi o'qish maydoni (`weigh_input`) shu chegaradan kichik
# o'zgarishlarda YANGILANMAYDI — tarozi shovqini (masalan 4.781/4.783
# kabi milligrammlik tebranish) har safar matnni qayta yozib, ekranni
# tinimsiz "chayqalayotgandek" ko'rsatishining oldini oladi.
SCALE_DISPLAY_THRESHOLD_KG = 0.01

# Faqat shu birliklar tarozida (massa asosida) o'lchanadi. Boshqa hamma
# narsa (dona, litr, metr va h.k.) — sanoq/hajm, tarozida o'lchab
# bo'lmaydi (tarozi faqat kilogramm/gramm o'qiydi) — bunday so'rovlar
# uchun kartochka faqat ko'rsatish uchun, avtomatik tasdiqlanadi.
WEIGHABLE_BIRLIKLAR = {"kg", "g", "gr", "gramm", "kilogramm"}


def _is_weighable_birlik(birlik: str) -> bool:
    return (birlik or "").strip().lower() in WEIGHABLE_BIRLIKLAR


def _scale_required() -> bool:
    """Firma ERP sozlamasida (`Company.tarozi_majburiy`) tarozi shart
    emas deb belgilangan bo'lsa — kg/g birlikdagi komponentlar ham
    xuddi dona/litr kabi, oddiy "Oldim ✓" tugmasi bilan tasdiqlanadi
    (haqiqiy tortish talab qilinmaydi)."""
    return bool(db.get_setting("tarozi_majburiy", "1"))


_GRAM_BIRLIKLAR = {"g", "gr", "gramm"}


def _scale_capacity_for_birlik(birlik: str) -> float | None:
    """Settings sahifasida kiritilgan tarozi sig'imini (doim kg da
    saqlanadi) so'rov birligiga (kg yoki g) moslab qaytaradi. Sig'im
    kiritilmagan/0 bo'lsa `None` — bu holda tortish cheklovsiz, bitta
    porsiyada so'raladi (eski xatti-harakat)."""
    raw = db.get_setting("scale_max_capacity_kg", "").strip()
    if not raw:
        return None
    try:
        cap_kg = float(raw)
    except ValueError:
        return None
    if cap_kg <= 0:
        return None
    if (birlik or "").strip().lower() in _GRAM_BIRLIKLAR:
        return cap_kg * 1000
    return cap_kg


class _ApiCallWorker(QThread):
    """Har qanday tarmoq chaqiruvini (server sekin javob bersa yoki
    umuman ulanmasa ham) fon oqimida bajaradi.

    **Muhim**: `ScannerService` endi butun dastur bo'ylab fonda ishlaydi —
    xodim badge'ini istalgan payt skanerlashi mumkin, hech qanday tugma
    bosilishini kutmasdan. Agar tarmoq chaqiruvi (`resolve_badge` va
    h.k.) to'g'ridan-to'g'ri asosiy (GUI) oqimda bajarilsa, server sekin
    javob bersa yoki umuman ulanmasa — **butun ilova muzlab qoladi**
    (bir necha soniyaga, `api_client.TIMEOUT` davomida). Shu sababli
    barcha tarmoq chaqiruvlari shu worker orqali fon oqimida bajariladi.

    **Muhim (2)**: `run()` faqat `ApiError`ni emas, **har qanday**
    kutilmagan xatoni ham ushlaydi — sinab ko'rilganda aniqlandiki, agar
    biror kutilmagan Python xatosi (masalan `StopIteration` yoki boshqa)
    `QThread.run()`dan chiqib ketsa, PyQt6/sip buni to'g'ri
    boshqarolmaydi va **butun dastur darhol, hech qanday xabarsiz
    yiqiladi** (Windows darajasidagi jiddiy xato, oddiy Python
    exception emas). Shuning uchun bu yerda har qanday xato xavfsiz
    `failed` signaliga aylantiriladi — dastur hech qachon shu sababdan
    yiqilmasligi kerak.

    **Muhim (3)**: o'z `finished` signalini `self.wait()`ga ulaymiz. Buni
    sabab: agar shu worker obyektiga ishora qiluvchi oxirgi Python
    o'zgaruvchisi (masalan `self._resolve_worker`) tezda YANGI worker bilan
    almashtirilsa (masalan ketma-ket ikkinchi skaner), eski obyekt
    axlat yig'uvchi (GC) tomonidan o'chirilishi mumkin — agar shu payt
    C++ tomondagi oqim hali to'liq "join" bo'lmagan bo'lsa (`isRunning()`
    hali `True`), bu ham xuddi shu tarzda butun dasturni jimgina yiqitadi.
    `finished` signali oqim tugagach chaqiriladi, shu yerda `wait()`
    chaqirish oqim to'liq join bo'lishini kafolatlaydi va shu poyga
    holatini (race condition) yopadi."""
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    # Token eskirgan/bekor qilingan (401) — `heartbeat`dagi kabi, lekin
    # endi ISTALGAN so'rov (skanerlash, tortish, yetkazib berish va h.k.)
    # shu holatni sezishi mumkin, faqat heartbeatni kutib o'tirmasdan.
    # `failed` signali ham baribir yuboriladi (orqaga moslik — mavjud
    # xato ko'rsatish kodi o'zgarishsiz ishlayveradi), bu qo'shimcha.
    token_invalid = pyqtSignal()

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self.finished.connect(self.wait)

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
        except ApiError as exc:
            if exc.status_code == 401:
                self.token_invalid.emit()
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 — pastdagi izohga qarang
            self.failed.emit(f"Kutilmagan xato: {exc}")
        else:
            self.succeeded.emit(result)


class _ImageFetchWorker(QThread):
    """Rasmni fon oqimida yuklab oladi (asosiy oqimni bloklamasdan)."""
    ready = pyqtSignal(bytes)
    failed = pyqtSignal()

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self):
        try:
            resp = requests.get(self._url, timeout=5)
            if resp.status_code == 200:
                self.ready.emit(resp.content)
                return
        except requests.exceptions.RequestException:
            pass
        self.failed.emit()


class EmployeeScanWidget(QWidget):
    """Skanerlangan xodim ma'lumotini (rasm, ism, lavozim, telefon),
    stansiya sessiyasini va — ishlab chiqaruvchi bo'lsa — uning kutilayotgan
    xom ashyo so'rovlarini tarozi orqali tekshirib, bir-bir tasdiqlash
    oqimini ko'rsatadi.

    Bu — alohida "Skaner" sahifa/menyu emas: `ScannerService` fon rejimida
    (kamera yoki qo'lda HID skaner orqali) kodni aniqlaganda,
    `handle_scanned_code()` chaqiriladi va shu vidjet o'z oynasida
    ko'rsatiladi — foydalanuvchi hech qanday menyuga kirmaydi.

    **Xom ashyo so'rovi — tarozi orqali tasdiqlash**: foydalanuvchi bilan
    kelishilgan qaror bo'yicha, Desktop Agent ishlatilayotgan firmalarda bu
    oqim omborchining web-sahifadagi qo'lda "Tasdiqlash" bosishini butunlay
    almashtiradi — ishlab chiqaruvchi materialni tarozida o'lchab, qiymatni
    kiritadi (hozircha qo'lda; haqiqiy tarozi ulangach — readonly, avtomatik
    o'qiladi), server normani tekshirib, mos kelsa avtomatik tasdiqlaydi.
    """

    close_requested = pyqtSignal()
    # `_ApiCallWorker.token_invalid` (401) — istalgan so'rovdan kelishi
    # mumkin, `MainWindow._handle_token_invalid`ga (avtomatik logout)
    # ulanadi (heartbeatdagi bilan bir xil oqim).
    session_expired = pyqtSignal()
    # Real bug (foydalanuvchi topdi): kiosk qulfini ochish avval FAQAT
    # maxsus shifrlangan "Desktop Agent QR-login" kodi orqali mumkin edi
    # — ega o'zining oddiy shaxsiy QR badge'ini (bu yerdagi umumiy skan
    # oqimi orqali, `scan()` API — allaqachon shu firma ekanini server
    # tasdiqlagan) ko'rsatganda esa faqat "Xush kelibsiz" karta ko'rinib,
    # qulf ochilmasdi. Endi bu yerda `user_type == 'ega'` aniqlansa, shu
    # signal orqali `MainWindow`ga bildiriladi — agar kiosk qulflangan
    # bo'lsa, xuddi maxsus QR bilan ochilganidek ochiladi.
    ega_badge_scanned = pyqtSignal(str)

    def __init__(self, camera_recorder=None, parent=None):
        super().__init__(parent)
        # Ombor kamerasi — voqea (tasdiqlash/QR skaner) atrofida video
        # yozish xizmati. `None` bo'lsa (masalan testlarda) — barcha
        # chaqiruvlar xavfsiz no-op.
        self._camera_recorder = camera_recorder
        self._active_rec_ids: set[str] = set()
        self._session: dict | None = None
        self._session_seconds_left = 0
        self._pending_requests: list = []
        self._current_weigh_request: dict | None = None
        self._pending_miqdor_requests: list = []
        self._current_miqdor_request: dict | None = None
        self._miqdor_fetched = False
        self._task_pickups_fetched = False
        self._pending_print_fetched = False
        self._had_any_request = False
        self._delivery_mode_active = False

        # Tarozi avtomatlashtirish holati (158-qadam) — jonli o'qish
        # barqarorlashganda avtomatik yuborish, so'ng mahsulot tarozidan
        # olib tashlanishi (0.0ga qaytishi) bilan keyingi so'rovga o'tish.
        self._scale_last_value: float | None = None
        self._scale_stable_since = 0.0
        self._auto_submit_pending = False
        self._awaiting_scale_clear = False
        # Ekranga chiqarilgan oxirgi qiymat — jonli o'qish HAR safar
        # (millisekundlarda, tarozi shovqini bilan) kelaveradi, lekin
        # matnni har safar yangilash ekranni tinimsiz "chayqalgan" holda
        # ko'rsatardi. Endi faqat sezilarli o'zgarishda (`SCALE_DISPLAY_
        # THRESHOLD_KG`dan katta) matn qayta yoziladi.
        self._scale_last_displayed: float | None = None
        self._delivery_cart: dict = {}
        # Dashboardda so'ralgan (zayavka) mahsulotlar: {mahsulot_id: {'mahsulot', 'miqdor'}}
        # — skanerlashda limit shu yerdan tekshiriladi (so'ralganidan ortiq
        # dona savatga qo'shilmaydi).
        self._delivery_requested: dict = {}
        self._delivery_finalizing = False
        self._resolve_worker: _ApiCallWorker | None = None
        self._requests_worker: _ApiCallWorker | None = None
        self._weigh_worker: _ApiCallWorker | None = None
        self._miqdor_worker: _ApiCallWorker | None = None
        self._miqdor_approve_worker: _ApiCallWorker | None = None
        self._delivery_scan_worker: _ApiCallWorker | None = None
        self._delivery_finalize_worker: _ApiCallWorker | None = None
        self._attendance_worker: _ApiCallWorker | None = None
        self._label_print_worker: LabelPrintWorker | None = None
        # Bir nechta yorliq ketma-ket chop etilganda, har biri uchun
        # natija-xabar so'rovi bir vaqtda "havoda" bo'lishi mumkin —
        # shuning uchun bittalik `_replace_worker` o'rniga ro'yxat orqali
        # barchasiga ishora saqlanadi (aks holda C++ oqim hali join
        # bo'lmasdan GC'ga uchrashi mumkin, `_replace_worker`dagi izohga
        # qarang).
        self._print_result_workers: list = []
        self._image_worker: _ImageFetchWorker | None = None
        self._weigh_image_worker: _ImageFetchWorker | None = None
        self._miqdor_image_worker: _ImageFetchWorker | None = None

        self._session_timer = QTimer(self)
        self._session_timer.setInterval(1000)
        self._session_timer.timeout.connect(self._tick_session)

        layout = QVBoxLayout(self)

        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Bu label butun modul bo'ylab (badge, serial-skan, xato xabarlari
        # va h.k.) o'nlab turli xabarlar uchun qayta ishlatiladi —
        # `setWordWrap` yo'qligi tufayli uzun matn kartochka chegarasidan
        # chiqib, o'rtasida kesilib qolardi (masalan "...allaqachon
        # skanerlangan (2-marta) — Ho[...]"). Endi hammasi avtomatik
        # ko'p qatorga o'tadi.
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet(
            "font-size:16px; font-weight:800; padding:16px; border-radius:10px; "
            "background:#f1f5f9; color:#475569;"
        )
        layout.addWidget(self.result_label)

        self.employee_card = QFrame()
        self.employee_card.setStyleSheet(
            "background:white; border:1px solid #e2e8f0; border-radius:10px;"
        )
        card_layout = QHBoxLayout(self.employee_card)
        self.employee_photo_label = QLabel()
        self.employee_photo_label.setFixedSize(96, 96)
        self.employee_photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.employee_photo_label.setStyleSheet(
            "background:#f1f5f9; border-radius:8px; color:#94a3b8;"
        )
        self.employee_photo_label.setText("Rasm yo'q")
        card_layout.addWidget(self.employee_photo_label)

        info_layout = QVBoxLayout()
        self.employee_name_label = QLabel("")
        self.employee_name_label.setStyleSheet("font-size:18px; font-weight:800; color:#1e293b;")
        self.employee_lavozim_label = QLabel("")
        self.employee_lavozim_label.setStyleSheet("font-size:14px; font-weight:600; color:#6366f1;")
        self.employee_phone_label = QLabel("")
        self.employee_phone_label.setStyleSheet("font-size:13px; color:#64748b;")
        self.employee_username_label = QLabel("")
        self.employee_username_label.setStyleSheet("font-size:13px; color:#94a3b8;")
        info_layout.addWidget(self.employee_name_label)
        info_layout.addWidget(self.employee_lavozim_label)
        info_layout.addWidget(self.employee_phone_label)
        info_layout.addWidget(self.employee_username_label)
        info_layout.addStretch(1)
        card_layout.addLayout(info_layout, 1)

        self.employee_card.setVisible(False)
        layout.addWidget(self.employee_card)

        # Reception — badge skanerlangan har safar avtomatik kelish/ketish
        # belgilanadi, natija shu yerda ko'rsatiladi (alohida rejim/menyu
        # tanlash shart emas — istalgan xodim uchun avtomatik ishlaydi).
        self.attendance_label = QLabel("")
        self.attendance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.attendance_label.setWordWrap(True)
        self.attendance_label.setStyleSheet(
            "font-size:13px; font-weight:700; padding:8px; border-radius:8px; "
            "background:#f1f5f9; color:#475569;"
        )
        self.attendance_label.setVisible(False)
        layout.addWidget(self.attendance_label)

        # Material so'rovi QR kodi skanerlanganda ko'rsatiladigan kartochka
        # (77-qadam) — faqat ma'lumot, sessiya boshlamaydi.
        self.material_request_card = QFrame()
        self.material_request_card.setStyleSheet(
            "background:#fff7ed; border:1px solid #fed7aa; border-radius:10px;"
        )
        mr_layout = QVBoxLayout(self.material_request_card)
        self.mr_title_label = QLabel("")
        self.mr_title_label.setStyleSheet("font-size:16px; font-weight:800; color:#1e293b;")
        self.mr_detail_label = QLabel("")
        self.mr_detail_label.setWordWrap(True)
        self.mr_detail_label.setStyleSheet("font-size:13px; color:#64748b;")
        self.mr_status_label = QLabel("")
        self.mr_status_label.setWordWrap(True)
        self.mr_status_label.setStyleSheet("font-size:13px; font-weight:700;")
        mr_layout.addWidget(self.mr_title_label)
        mr_layout.addWidget(self.mr_detail_label)
        mr_layout.addWidget(self.mr_status_label)
        self.material_request_card.setVisible(False)
        layout.addWidget(self.material_request_card)

        self.session_banner = QFrame()
        self.session_banner.setStyleSheet("background:#0f172a; border-radius:10px; padding:8px;")
        session_layout = QHBoxLayout(self.session_banner)
        self.session_label = QLabel("")
        self.session_label.setStyleSheet("color:white; font-weight:700; font-size:14px;")
        # Uzun ism/lavozim + hisoblagich matni tor kartochkada "Chiqish"
        # tugmasi ustiga chiqib, bir-biriga ustma-ust tushib qolardi
        # (real skrinshotda kuzatilgan) — endi matn ikkinchi qatorga
        # o'tadi, tugma esa doim o'zining minimal (siqilmaydigan)
        # o'lchamida, matn bilan bosilib qolmasdan turadi.
        self.session_label.setWordWrap(True)
        session_layout.addWidget(self.session_label, 1)
        logout_btn = QPushButton("Chiqish")
        logout_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        logout_btn.clicked.connect(self._end_session)
        session_layout.addWidget(logout_btn, 0, Qt.AlignmentFlag.AlignTop)
        self.session_banner.setVisible(False)
        layout.addWidget(self.session_banner)

        # So'rov yo'q / hammasi bajarildi xabari — 3 soniyadan keyin
        # avtomatik yopiladi (popup ham shu bilan yopiladi).
        self.no_requests_label = QLabel("")
        self.no_requests_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_requests_label.setWordWrap(True)
        self.no_requests_label.setStyleSheet(
            "font-size:14px; font-weight:700; padding:14px; border-radius:10px; "
            "background:#f1f5f9; color:#64748b;"
        )
        self.no_requests_label.setVisible(False)
        layout.addWidget(self.no_requests_label)

        # "Ish bitdi"dan keyingi kutilayotgan QR-yorliq partiyasi (159-qadam)
        # uchun — printer sozlanmagan bo'lsa, brauzerda ochilgan sahifaga
        # tayanish o'rniga (fullscreen kiosk rejimida ko'rinmay qolishi
        # mumkin edi — real sinovda topilgan bug), QR kodlar to'g'ridan-
        # to'g'ri shu oynaning o'zida ko'rsatiladi — har doim ko'rinadi,
        # tashqi brauzer/printerga bog'liq emas. "Davom etish" bosilgandan
        # keyingina "chop etilgan" deb belgilanadi (avtomatik emas).
        self.print_batch_card = QFrame()
        self.print_batch_card.setStyleSheet(
            "background:#f0fdf4; border:1px solid #86efac; border-radius:10px;"
        )
        print_batch_outer = QVBoxLayout(self.print_batch_card)
        self.print_batch_title = QLabel("")
        self.print_batch_title.setWordWrap(True)
        self.print_batch_title.setStyleSheet("font-size:14px; font-weight:800; color:#166534;")
        print_batch_outer.addWidget(self.print_batch_title)

        self.print_batch_scroll = QScrollArea()
        self.print_batch_scroll.setWidgetResizable(True)
        self.print_batch_scroll.setFixedHeight(220)
        self.print_batch_scroll.setStyleSheet("background:transparent; border:none;")
        self._print_batch_grid_widget = QWidget()
        self.print_batch_grid = QGridLayout(self._print_batch_grid_widget)
        self.print_batch_scroll.setWidget(self._print_batch_grid_widget)
        print_batch_outer.addWidget(self.print_batch_scroll)

        self.print_batch_card.setVisible(False)
        layout.addWidget(self.print_batch_card)
        self._pending_print_batch = None
        # Chop etilgan/ekranda ko'rsatilgan yorliqlarning `kod`lari — shu
        # yerda turadigan davrda kamera/skaner ULARNING O'ZINI (yangi
        # yopishtirilgan yorliq printerdan chiqib kameraning ko'rish
        # maydoniga tushib qolishi yoki ekrandagi QR-panjara aks etib
        # qolishi orqali) qayta o'qib yuborishi — bu haqiqatda foydalanuvchi
        # skanerlamagan holda ham skanerlash hodisasini ishga tushiradi,
        # va `_maybe_finish_task_on_scan` (server) shu orqali vazifani
        # "o'z-o'zidan" bajarilgan deb belgilashi mumkin, foydalanuvchiga
        # xuddi "vazifa/QR yana chiqmoqda" bo'lib ko'rinadi (real sinovda
        # DB orqali tasdiqlangan: yangi partiyaning `scan_soni`lari
        # yaratilgan zahoti, hech kim qo'lda skanerlamasdan, 1-2ga
        # ko'tarilgan edi). Shuning uchun shu ro'yxatdagi kodlar kelsa —
        # haqiqiy skan sifatida serverga yuborilmaydi, jim e'tiborsiz
        # qoldiriladi.
        self._own_batch_kods: set = set()
        self._batch_qr_workers: list = []
        # Server'ga "chop etildi" xabari (`_mark_batch_printed`) fon
        # oqimida, asinxron yuboriladi — agar shu payt (bir necha soniya
        # ichida) badge qayta skanerlansa, server hali "chop etilmagan"
        # deb bilishi mumkin va AYNAN O'SHA partiyani yana ko'rsatib/
        # chop etib yuboradi (real sinovda aniqlangan bug — DB'da
        # dublikat yo'q, lekin ekranga/printerga ikki marta chiqadi).
        # Shu race'ni yopish uchun — mahalliy (client) xotirada, so'nggi
        # ko'rsatilgan partiya ID'lari va vaqti saqlanadi.
        self._recently_shown_batch_ids: dict = {}

        # Xom ashyo so'rovini tarozi orqali tekshirib tasdiqlash kartochkasi.
        self.weigh_card = QFrame()
        self.weigh_card.setStyleSheet(
            "background:#fff7ed; border:1px solid #fed7aa; border-radius:10px;"
        )
        weigh_outer = QVBoxLayout(self.weigh_card)
        weigh_top_row = QHBoxLayout()
        self.weigh_photo_label = QLabel()
        self.weigh_photo_label.setFixedSize(80, 80)
        self.weigh_photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.weigh_photo_label.setStyleSheet("background:#f1f5f9; border-radius:8px; color:#94a3b8;")
        self.weigh_photo_label.setText("Rasm yo'q")
        weigh_top_row.addWidget(self.weigh_photo_label)

        weigh_text_col = QVBoxLayout()
        self.weigh_material_label = QLabel("")
        self.weigh_material_label.setWordWrap(True)
        self.weigh_material_label.setStyleSheet("font-size:15px; font-weight:800; color:#1e293b;")
        self.weigh_expected_label = QLabel("")
        self.weigh_expected_label.setStyleSheet("font-size:13px; color:#9a3412; font-weight:700;")
        weigh_text_col.addWidget(self.weigh_material_label)
        weigh_text_col.addWidget(self.weigh_expected_label)
        weigh_top_row.addLayout(weigh_text_col, 1)
        weigh_outer.addLayout(weigh_top_row)

        # Faqat OG'IRLIK birligida (kg/g) so'ralgan komponentlar uchun
        # ko'rinadi — tarozi haqiqatan mos keladi. "dona"/"litr" kabi
        # sanoq/hajm birliklarini tarozida o'lchab bo'lmaydi (tarozi
        # faqat massa o'qiydi), shuning uchun ular uchun bu qator
        # butunlay yashirin qoladi — `_show_next_weigh_request` shu
        # holatda kartani ko'rsatgan zahoti avtomatik tasdiqlaydi
        # (`_is_weighable_birlik`ga qarang).
        self.weigh_input_container = QWidget()
        weigh_input_row = QHBoxLayout(self.weigh_input_container)
        weigh_input_row.setContentsMargins(0, 0, 0, 0)
        weigh_input_row.addWidget(QLabel("Tarozi qiymati:"))
        self.weigh_input = QLineEdit()
        self.weigh_input.setPlaceholderText("hozircha qo'lda kiriting")
        self.weigh_input.returnPressed.connect(self._submit_weigh)
        weigh_input_row.addWidget(self.weigh_input, 1)
        self.weigh_submit_btn = QPushButton("Tekshirish")
        self.weigh_submit_btn.clicked.connect(self._submit_weigh)
        weigh_input_row.addWidget(self.weigh_submit_btn)
        weigh_outer.addWidget(self.weigh_input_container)

        # "dona"/"litr" kabi sanoq/hajm birligidagi (tarozida o'lchab
        # bo'lmaydigan) so'rovlar uchun — oldin bu holatda karta 600ms'da
        # OVOZSIZ o'zi tasdiqlanib ketardi, pazanda "necha dona qadoq/
        # necha litr yog' oling" degan matnni o'qishga ulgurmasdi (real
        # ishlab chiqarishda aniqlangan xato). Endi alohida, aniq ko'rinadigan
        # tugma orqali — xodim o'zi o'qib, o'zi bosib tasdiqlaydi.
        self.weigh_ack_btn = QPushButton("Oldim ✓")
        self.weigh_ack_btn.setStyleSheet(
            "font-size:15px; font-weight:800; padding:12px; border-radius:10px; "
            "background:#16a34a; color:#fff; border:none;"
        )
        self.weigh_ack_btn.clicked.connect(self._submit_weigh)
        weigh_outer.addWidget(self.weigh_ack_btn)

        self.weigh_feedback_label = QLabel("")
        self.weigh_feedback_label.setWordWrap(True)
        self.weigh_feedback_label.setStyleSheet("font-size:13px; font-weight:700; color:#9a3412;")
        weigh_outer.addWidget(self.weigh_feedback_label)

        self.weigh_card.setVisible(False)
        layout.addWidget(self.weigh_card)

        # Miqdor qo'shish (ishlab chiqarish natijasi) so'rovini tasdiqlash
        # kartochkasi (82-qadam) — tarozi tekshiruvi kerak emas, faqat
        # Bu stansiyada klaviatura/sichqoncha yo'q (faqat skaner) — shuning
        # uchun bu yerda hech qanday tugma yo'q: navbatdagi so'rov
        # ko'rsatilgan zahoti avtomatik tasdiqlanadi va Serial QR kodlar
        # (bo'lsa) darhol chop etiladi, xodim faqat kutib turadi.
        self.miqdor_card = QFrame()
        self.miqdor_card.setStyleSheet(
            "background:#eff6ff; border:1px solid #bfdbfe; border-radius:10px;"
        )
        miqdor_outer = QVBoxLayout(self.miqdor_card)
        miqdor_top_row = QHBoxLayout()
        self.miqdor_photo_label = QLabel()
        self.miqdor_photo_label.setFixedSize(80, 80)
        self.miqdor_photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.miqdor_photo_label.setStyleSheet("background:#f1f5f9; border-radius:8px; color:#94a3b8;")
        self.miqdor_photo_label.setText("Rasm yo'q")
        miqdor_top_row.addWidget(self.miqdor_photo_label)

        miqdor_text_col = QVBoxLayout()
        self.miqdor_title_label = QLabel("")
        self.miqdor_title_label.setWordWrap(True)
        self.miqdor_title_label.setStyleSheet("font-size:15px; font-weight:800; color:#1e293b;")
        miqdor_text_col.addWidget(self.miqdor_title_label)
        miqdor_top_row.addLayout(miqdor_text_col, 1)
        miqdor_outer.addLayout(miqdor_top_row)

        self.miqdor_feedback_label = QLabel("")
        self.miqdor_feedback_label.setWordWrap(True)
        self.miqdor_feedback_label.setStyleSheet("font-size:13px; font-weight:700; color:#1e40af;")
        miqdor_outer.addWidget(self.miqdor_feedback_label)

        self.miqdor_card.setVisible(False)
        layout.addWidget(self.miqdor_card)

        # Yetkazib beruvchi uchun "yuklama" (yuk olish) savati — har bir
        # mahsulot donasining Serial QR kodini skanerlab to'ldiriladi
        # (foydalanuvchi bilan kelishilgan qaror: sotuv jarayonining o'zi
        # hamon veb-saytda, faqat omborddan yuk olish agentda).
        self.delivery_card = QFrame()
        self.delivery_card.setStyleSheet(
            "background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px;"
        )
        delivery_outer = QVBoxLayout(self.delivery_card)
        delivery_title = QLabel("Yuklama — mahsulot QR kodlarini skanerlang")
        delivery_title.setStyleSheet("font-size:14px; font-weight:800; color:#166534;")
        delivery_outer.addWidget(delivery_title)

        # Dashboardda oldindan so'ralgan (zayavka) mahsulotlar — xodim
        # aynan nimalarni (va qanchadan) olishi kerakligi shu yerda
        # ko'rsatiladi; so'ralmagan mahsulot skanini server baribir rad
        # etadi, bu ro'yxat xodimga yo'l-yo'riq uchun.
        self.delivery_requests_label = QLabel("So'rovlaringiz yuklanmoqda...")
        self.delivery_requests_label.setWordWrap(True)
        self.delivery_requests_label.setStyleSheet(
            "font-size:13px; font-weight:700; color:#0f172a; background:#dcfce7; "
            "border-radius:8px; padding:8px;"
        )
        delivery_outer.addWidget(self.delivery_requests_label)

        self.delivery_cart_label = QLabel("Hali hech narsa skanerlanmadi.")
        self.delivery_cart_label.setWordWrap(True)
        self.delivery_cart_label.setStyleSheet("font-size:13px; color:#1e293b;")
        delivery_outer.addWidget(self.delivery_cart_label)

        self.delivery_feedback_label = QLabel("")
        self.delivery_feedback_label.setWordWrap(True)
        self.delivery_feedback_label.setStyleSheet("font-size:13px; font-weight:700; color:#166534;")
        delivery_outer.addWidget(self.delivery_feedback_label)

        self.delivery_finish_btn = QPushButton("Yuklamani yakunlash")
        self.delivery_finish_btn.clicked.connect(self._submit_finalize_delivery)
        delivery_outer.addWidget(self.delivery_finish_btn)

        self.delivery_card.setVisible(False)
        layout.addWidget(self.delivery_card)

        layout.addStretch(1)

    # ── Skanerlangan kodni qayta ishlash (hammasi fon oqimida) ───────────

    def _replace_worker(self, attr_name: str, worker):
        """`attr_name`dagi eski worker obyektini yangisi bilan
        almashtirishdan oldin chaqiriladi. Agar eski oqim negadir hali
        tugamagan bo'lsa (`isRunning()`), to'liq tugashini kutib turadi —
        aks holda Python GC eski obyektni C++ tomondagi oqim hali join
        bo'lmasdan o'chirib yuborishi mumkin, bu esa butun dasturni jimgina
        (hech qanday xabarsiz) yiqitadi (sinab ko'rilganda aniqlangan real
        poyga holati — `finished` signaliga ulanish yetarli emas edi,
        chunki ketma-ket ikkinchi harakat navbatdagi hodisa tsiklidan oldin
        sodir bo'lishi mumkin). Amalda bu deyarli hamisha darhol qaytadi,
        chunki yangi worker odatda eski oqim muvaffaqiyat/xato signalini
        yuborib bo'lgandan keyingina yaratiladi."""
        old = getattr(self, attr_name, None)
        if old is not None and old.isRunning():
            old.wait()
        if hasattr(worker, 'token_invalid'):
            worker.token_invalid.connect(self.session_expired.emit)
        setattr(self, attr_name, worker)

    # ── Ombor kamerasi — voqea atrofida video yozish ─────────────────────
    # Xom ashyo tarozida tekshirilishi, miqdor qo'shish tasdiqlanishi va
    # yuklama (yuk olish) — bularning har biri "voqea": kamera(lar)
    # tasdiqlashdan 5 soniya oldindan boshlab, voqea yopilgandan 5 soniya
    # keyingacha yozadi (`CameraRecorderService`, `camera_recorder_service.py`).
    # Hozircha aniq qaysi ombordan ekanligi kuzatilmagani uchun
    # (`warehouse_id=None`) barcha sozlangan ombor kameralarida yoziladi.

    def _rec_start(self, event_id: str, reason: str):
        self._active_rec_ids.add(event_id)
        if self._camera_recorder is not None:
            self._camera_recorder.start_event(event_id, None, reason)

    def _rec_stop(self, event_id: str):
        self._active_rec_ids.discard(event_id)
        if self._camera_recorder is not None:
            self._camera_recorder.stop_event(event_id)

    def _rec_stop_all(self):
        """Sessiya kutilmaganda tugasa (masalan vaqt tugashi) ham, hali
        yopilmagan barcha voqea-yozuvlari to'xtatiladi — aks holda
        `_ClipWriterWorker` faqat 300 soniyalik xavfsizlik chegarasida
        to'xtardi."""
        for event_id in list(self._active_rec_ids):
            self._rec_stop(event_id)

    def handle_scanned_code(self, kod: str):
        # HAQIQIY TOPILGAN ILDIZ SABAB (real DB tekshiruvi orqali
        # tasdiqlangan): shu sessiyada YANGI chop etilgan/ekranda
        # ko'rsatilgan yorliqning o'zi kamera/skaner tomonidan QAYTA
        # o'qilib qolishi mumkin (yangi yopishtirilgan yorliq printerdan
        # chiqib kameraning ko'rish maydoniga tushishi yoki ekrandagi
        # QR-panjara aks etib qolishi orqali) — bu esa `scan_soni`ni
        # oshirib, "vazifa avtomatik yakunlandi" (`_maybe_finish_task_
        # on_scan`, server) hodisasini xodim hech narsa qilmasdan ishga
        # tushiradi, foydalanuvchiga xuddi "vazifa/QR yana chiqmoqda"
        # bo'lib ko'rinadi. Shuning uchun shu sessiyada BIZNING O'ZIMIZ
        # ko'rsatgan/chop etgan yorliqlar kodlari kelsa — haqiqiy skan
        # sifatida serverga umuman yuborilmaydi.
        if self._own_batch_kods and any(k in kod for k in self._own_batch_kods):
            return

        # Yetkazib beruvchi "yuklama" sessiyasi faol bo'lsa, keyingi barcha
        # skanerlar YANGI badge/so'rov qidiruvi emas, balki mahsulot Serial
        # QR kodlari sifatida talqin qilinadi (savatga qo'shish uchun).
        if self._delivery_mode_active and self._session is not None:
            self._handle_delivery_scan(kod)
            return

        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        if not token:
            # Stansiya hali login qilinmagan (yoki "Chiqish" bosilgan) —
            # avval "Token kiritilmagan" degan tushunarsiz xato chiqardi
            # (real ishlab chiqarishda topilgan: foydalanuvchi shaxsiy
            # badge/boshqa QR'ni chiqib ketgan holatda skanerlasa).
            self._set_result("Avval stansiya login qilinishi kerak — Sozlamalarda kiring.", "error")
            return

        self._set_result("Tekshirilmoqda...", "idle")
        # Faol sessiya bo'lsa, uning tokeni ham yuboriladi — bu vazifa
        # (`ProductionTask`) QR kodini kim skanerlaganini serverga
        # bildiradi, shu orqali vazifa o'sha xodimga band qilinadi
        # (103-qadam). Badge/Serial/MaterialRequest skanerlariga ta'sir
        # qilmaydi — ular session_token'ga bog'liq emas.
        session_token = self._session["session_token"] if self._session else None

        worker = _ApiCallWorker(scan, server_url, token, kod, session_token)
        worker.succeeded.connect(self._on_scan_resolved)
        worker.failed.connect(self._on_scan_resolve_failed)
        self._replace_worker("_resolve_worker", worker)
        worker.start()

    def _on_scan_resolve_failed(self, message: str):
        self._set_result(message, "error")
        self.employee_card.setVisible(False)
        self.material_request_card.setVisible(False)
        self.attendance_label.setVisible(False)
        if not self._session:
            # Hali hech qanday faol sessiya yo'q (masalan birinchi skan
            # noto'g'ri chiqdi) — "Chiqish" tugmasi ham yo'q, shuning
            # uchun panel abadiy ochiq qolib ketmasligi uchun bir necha
            # soniyadan keyin o'zi yopiladi. Sessiya faol bo'lsa (xodim
            # allaqachon kirgan, shunchaki bitta skan mos kelmadi) —
            # panel ochiq qoladi, "Chiqish" tugmasi orqali yopiladi.
            QTimer.singleShot(3000, self._auto_close)

    def _on_scan_resolved(self, info: dict):
        if info.get("type") == "material_request":
            self.employee_card.setVisible(False)
            self._show_material_request_card(info)
            return
        if info.get("type") == "serial":
            self._show_serial_scan_result(info)
            return
        if info.get("type") == "task":
            self._on_task_resolved(info)
            return
        self._on_badge_resolved(info)

    def _on_task_resolved(self, info: dict):
        """"Vazifalar paneli" (103-qadam) — vazifa QR kodi (badge-sessiya
        ichida) skanerlanganda chaqiriladi. Server allaqachon vazifani
        skanerlagan xodimga band qilib bo'lgan (yoki u allaqachon o'ziniki
        bo'lsa, holatni qaytargan) — bu yerda faqat qolgan xom ashyo
        qatorlarini (`pickups`) mavjud tortish (weigh) navbatiga qo'shamiz,
        chunki interfeys bir xil (kutilgan miqdorni ko'rsatish, tarozi
        qiymatini kiritish)."""
        self.employee_card.setVisible(False)
        self.material_request_card.setVisible(False)
        pickups = info.get("pickups") or []
        for p in pickups:
            p["_kind"] = "task_pickup"
        if not pickups:
            self._set_result(
                f"✓ {info.get('mahsulot', '')} vazifasi olindi — barcha xom ashyo allaqachon tayyor.",
                "success",
            )
            return
        self._had_any_request = True
        self.no_requests_label.setVisible(False)
        self._pending_requests.extend(pickups)
        if self._current_weigh_request is None:
            self._show_next_weigh_request()

    def _show_serial_scan_result(self, info: dict):
        """Bitta mahsulot donasining Serial QR kodi (masalan sinov uchun,
        yorliq to'g'ri chop etilganini tekshirish maqsadida) skanerlanganda
        ko'rsatiladi — faqat ma'lumot, hech narsa o'zgarmaydi/sessiya
        boshlanmaydi. `holati` (masalan "Omborda") skanerlash sonidan
        qat'i nazar hech qachon o'zgarmaydi (bu faqat chiqarilgan/sotilgan
        payti o'zgaradi) — shuning uchun N-marta skanerlansa ham xabar
        tashqi ko'rinishda bir xil bo'lib qolar edi, xuddi "yana qo'shilgandek"
        taassurot qoldirib. `scan_soni` (server har safar oshiradi) orqali
        bu allaqachon oldin skanerlanganini ajratib ko'rsatamiz."""
        self.employee_card.setVisible(False)
        self.material_request_card.setVisible(False)
        kod_qisqa = (info.get("kod") or "")[:8]
        scan_soni = info.get("scan_soni") or 0
        progress = info.get("task_progress")
        progress_text = ""
        if progress:
            if progress.get("task_done"):
                progress_text = f" — Vazifa bajarildi ✓ ({progress['count']:g}/{progress['max']:g})"
            else:
                progress_text = f" — Ishlab chiqarilmoqda: {progress['count']:g}/{progress['max']:g}"
        if scan_soni > 1:
            self._set_result(
                f"⚠ {info['mahsulot']} — Serial: {kod_qisqa}... — Bu QR kod allaqachon skanerlangan "
                f"({scan_soni}-marta) — Holati: {info['holati_display']}{progress_text}",
                "error",
            )
        else:
            self._set_result(
                f"✓ {info['mahsulot']} — Serial: {kod_qisqa}... — Holati: {info['holati_display']}{progress_text}",
                "success",
            )

    def _on_badge_resolved(self, info: dict):
        self.material_request_card.setVisible(False)
        if not info.get("is_active", True):
            self._set_result(f"{info['tuliq_ismi']} — hisob faol emas.", "error")
            self.employee_card.setVisible(False)
            return

        self._set_result(f"Xush kelibsiz, {info['tuliq_ismi']}! ({info['lavozim']})", "success")
        self._show_employee_card(info)
        self._start_session(info)
        self._toggle_attendance(info["session_token"])
        if info.get("user_type") == "ega":
            self.ega_badge_scanned.emit(info.get("tuliq_ismi") or info.get("username", "Ega"))

    def _toggle_attendance(self, session_token: str):
        """Reception — har bir muvaffaqiyatli badge skaneridan keyin
        avtomatik chaqiriladi (rolidan qat'iy nazar). Xato bo'lsa jim
        e'tiborsiz qoldiriladi — bu asosiy oqim (xodim/so'rov ko'rsatish)
        uchun hal qiluvchi emas."""
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        worker = _ApiCallWorker(toggle_attendance, server_url, token, session_token)
        worker.succeeded.connect(self._on_attendance_toggled)
        worker.failed.connect(lambda _msg: self.attendance_label.setVisible(False))
        self._replace_worker("_attendance_worker", worker)
        worker.start()

    def _on_attendance_toggled(self, result: dict):
        vaqt = result["vaqt"][11:16]  # ISO datetime -> "HH:MM"
        if result["action"] == "kirish":
            text, bg, fg = f"✓ Ish boshlandi: {vaqt}", "#dcfce7", "#166534"
        else:
            text, bg, fg = f"✓ Ish tugadi: {vaqt}", "#e0e7ff", "#3730a3"
        self.attendance_label.setStyleSheet(
            f"font-size:13px; font-weight:700; padding:8px; border-radius:8px; background:{bg}; color:{fg};"
        )
        self.attendance_label.setText(text)
        self.attendance_label.setVisible(True)

    def _show_material_request_card(self, info: dict):
        """Material so'rovi QR kodi (77-qadam) skanerlanganda ko'rsatiladi —
        faqat ma'lumot, xodim sessiyasi boshlanmaydi (bu shaxsni emas,
        muayyan so'rovni aniqlaydi)."""
        self._set_result(f"So'rov: {info['producer']}", "success")
        target_text = f" ({info['target_product']} uchun)" if info.get("target_product") else ""
        self.mr_title_label.setText(f"{info['material']} — {info['qty']:g} {info['birlik']}{target_text}")
        self.mr_detail_label.setText(f"So'ragan: {info['producer']}")
        status_colors = {"waiting": "#b45309", "approved": "#166534", "rejected": "#b91c1c"}
        ack_text = " · Qabul qilingan ✓" if info.get("acknowledged") else ""
        self.mr_status_label.setText(f"Holat: {info['status_display']}{ack_text}")
        self.mr_status_label.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{status_colors.get(info['status'], '#475569')};"
        )
        self.material_request_card.setVisible(True)

    def _show_employee_card(self, info: dict):
        self.employee_name_label.setText(info.get("tuliq_ismi") or info.get("username", ""))
        self.employee_lavozim_label.setText(info.get("lavozim", ""))
        tel = info.get("tel_raqami") or ""
        self.employee_phone_label.setText(f"Tel: {tel}" if tel else "")
        self.employee_username_label.setText(f"Login: {info.get('username', '')}")

        self.employee_photo_label.setPixmap(QPixmap())
        self.employee_photo_label.setText("Rasm yo'q")
        rasmi_url = info.get("rasmi")
        if rasmi_url:
            worker = _ImageFetchWorker(rasmi_url)
            worker.ready.connect(self._on_photo_ready)
            self._replace_worker("_image_worker", worker)
            worker.start()

        self.employee_card.setVisible(True)

    def _on_photo_ready(self, content: bytes):
        pixmap = QPixmap()
        if pixmap.loadFromData(content):
            pixmap = pixmap.scaled(
                96, 96, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.employee_photo_label.setPixmap(pixmap)
            self.employee_photo_label.setText("")

    def _set_result(self, text: str, state: str):
        self.result_label.setText(text)
        colors = {
            "idle": ("#f1f5f9", "#475569"),
            "success": ("#dcfce7", "#166534"),
            "error": ("#fee2e2", "#b91c1c"),
        }
        bg, fg = colors.get(state, colors["idle"])
        self.result_label.setStyleSheet(
            f"font-size:16px; font-weight:800; padding:16px; border-radius:10px; background:{bg}; color:{fg};"
        )

    # ── Stansiya sessiyasi ──────────────────────────────────────────────

    def _start_session(self, info: dict):
        self._session = info
        self._session_seconds_left = SESSION_TIMEOUT_SECONDS
        self.session_banner.setVisible(True)
        self._update_session_label()
        self._session_timer.start()

        # Har bir badge skani (hatto sessiya hali faol bo'lsa ham, qayta
        # skanerlanganda) "vazifa"/"miqdor qo'shish" turdagi so'rovlarni
        # QAYTA tekshirishi kerak — aks holda foydalanuvchi shu sessiya
        # davomida yangi so'rov yaratsa, uni faqat sessiya to'liq tugab
        # (~60-120s) yangisi boshlangandan keyin ko'rar edi (`_advance_queue`
        # bu ikkalasini "bir marta tekshirilgan" deb faqat sessiya
        # boshida emas, hech qachon qayta tekshirmasdi).
        self._miqdor_fetched = False
        self._task_pickups_fetched = False
        self._pending_print_fetched = False

        if info.get("user_type") in ("yetkazib_beruvchi", "savdogar"):
            # Yetkazib beruvchi VA savdogar uchun ham material-so'rov/
            # miqdor-qo'shish navbati emas — "yuklama" (yuk olish) savati
            # boshlanadi (`YetkazibBeruvchi` profili ikkalasi uchun ham
            # umumiy — backend allaqachon ikkalasini ham qo'llab-quvvatlaydi,
            # bu yerda faqat mijoz tomonidagi cheklov olib tashlandi).
            self._delivery_mode_active = True
            self._delivery_cart = {}
            self.delivery_cart_label.setText("Hali hech narsa skanerlanmadi.")
            self.delivery_feedback_label.setText("")
            self.delivery_requests_label.setText("So'rovlaringiz yuklanmoqda...")
            self.delivery_card.setVisible(True)
            self._load_delivery_requests(info["session_token"])
            self._rec_start(f"delivery-{info['session_token']}", "yuklama")
            self._extend_session()  # birinchi mahsulotgacha ham uzunroq muddat berilsin
            return

        self._load_material_requests(info["session_token"])

    # ── Yetkazib beruvchi — "yuklama" (yuk olish) savati ─────────────────

    def _load_delivery_requests(self, session_token: str):
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        worker = _ApiCallWorker(fetch_delivery_requests, server_url, token, session_token)
        worker.succeeded.connect(self._on_delivery_requests_loaded)
        worker.failed.connect(
            lambda _msg: self.delivery_requests_label.setText(
                "So'rovlar ro'yxatini olib bo'lmadi — baribir skanerlashingiz mumkin."
            )
        )
        self._replace_worker("_delivery_requests_worker", worker)
        worker.start()

    def _on_delivery_requests_loaded(self, so_rovlar: list):
        if not so_rovlar:
            self._delivery_requested = {}
            self.delivery_requests_label.setStyleSheet(
                "font-size:13px; font-weight:700; color:#b45309; background:#fef3c7; "
                "border-radius:8px; padding:8px;"
            )
            self.delivery_requests_label.setText(
                "Sizda kutilayotgan yuklama so'rovi yo'q — avval dashboardda "
                "kerakli mahsulotlarni so'rang."
            )
            return
        self._delivery_requested = {
            r["mahsulot_id"]: r for r in so_rovlar if r.get("mahsulot_id") is not None
        }
        self.delivery_requests_label.setStyleSheet(
            "font-size:13px; font-weight:700; color:#0f172a; background:#dcfce7; "
            "border-radius:8px; padding:8px;"
        )
        self._refresh_delivery_requests_label()

    def _refresh_delivery_requests_label(self):
        """"Olishingiz kerak" ro'yxatini savatdagi hozirgi son bilan jonli
        yangilaydi (masalan `• Burger — 1/2`), to'lgan qator ✓ bilan
        belgilanadi."""
        if not self._delivery_requested:
            return
        lines = []
        for mid, r in self._delivery_requested.items():
            scanned = (self._delivery_cart.get(mid) or {}).get("count", 0)
            target = r["miqdor"]
            mark = " ✓" if scanned >= target else ""
            birlik = r.get("birlik") or ""
            lines.append(f"• {r['mahsulot']} — {scanned:g}/{target:g} {birlik}".rstrip() + mark)
        self.delivery_requests_label.setText("Olishingiz kerak:\n" + "\n".join(lines))

    def _all_delivery_requests_fulfilled(self) -> bool:
        """Dashboardda so'ralgan har bir mahsulot to'liq skanerlanganmi —
        shunda "Yuklamani yakunlash" tugmasi kutilmasdan avtomatik
        yakunlanadi (xodim mishka/klaviaturasiz kiosk stansiyada)."""
        if not self._delivery_requested:
            return False
        for mid, r in self._delivery_requested.items():
            scanned = (self._delivery_cart.get(mid) or {}).get("count", 0)
            if scanned < r["miqdor"]:
                return False
        return True

    def _handle_delivery_scan(self, kod: str):
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        self.delivery_feedback_label.setStyleSheet("font-size:13px; font-weight:700; color:#166534;")
        self.delivery_feedback_label.setText("Tekshirilmoqda...")

        worker = _ApiCallWorker(
            scan_delivery_serial, server_url, token, self._session["session_token"], kod,
        )
        worker.succeeded.connect(self._on_delivery_serial_scanned)
        worker.failed.connect(self._on_delivery_scan_failed)
        self._replace_worker("_delivery_scan_worker", worker)
        worker.start()

    def _on_delivery_serial_scanned(self, info: dict):
        self._extend_session()
        mahsulot_id = info["mahsulot_id"]
        entry = self._delivery_cart.setdefault(
            mahsulot_id, {"mahsulot": info["mahsulot"], "count": 0, "serial_ids": []},
        )
        # Bir xil dona ikki marta skanerlansa — qayta qo'shilmaydi
        serial_id = info.get("serial_id")
        if serial_id is not None and serial_id in entry["serial_ids"]:
            self.delivery_feedback_label.setStyleSheet("font-size:13px; font-weight:700; color:#b45309;")
            self.delivery_feedback_label.setText(f"Bu dona allaqachon savatda ({info['mahsulot']}).")
            return
        # So'ralgan miqdor limiti — zayavkada belgilangan sondan ortiq dona
        # savatga qo'shilmaydi: xodim ortiqcha skanerlagan donani joyiga
        # qaytarib, keyingi mahsulotga o'tishi kerak.
        requested = self._delivery_requested.get(mahsulot_id)
        if requested and entry["count"] >= requested["miqdor"]:
            self.delivery_feedback_label.setStyleSheet("font-size:13px; font-weight:700; color:#b45309;")
            self.delivery_feedback_label.setText(
                f"{info['mahsulot']} — so'ralgan miqdor to'ldi ({entry['count']:g}/{requested['miqdor']:g}). "
                "Bu donani joyiga qo'yib, keyingi mahsulotga o'ting."
            )
            return
        if serial_id is not None:
            entry["serial_ids"].append(serial_id)
        entry["count"] += 1
        self._refresh_delivery_cart_display()
        self._refresh_delivery_requests_label()
        self.delivery_feedback_label.setStyleSheet("font-size:13px; font-weight:700; color:#166534;")
        self.delivery_feedback_label.setText(f"✓ {info['mahsulot']} qo'shildi ({entry['count']})")

        if self._all_delivery_requests_fulfilled():
            # Barcha so'ralgan mahsulotlar to'liq skanerlandi — tugma
            # bosilishini kutmasdan darhol yakunlanadi va yetkazib
            # beruvchining o'z zaxirasiga (`DeliveryStock`) o'tadi, u
            # yerdan endi telefonida (QR skanerlab) sotadi.
            self.delivery_feedback_label.setText(
                f"✓ {info['mahsulot']} qo'shildi ({entry['count']}) — barcha mahsulotlar yig'ildi, yakunlanmoqda..."
            )
            QTimer.singleShot(600, self._submit_finalize_delivery)

    def _on_delivery_scan_failed(self, message: str):
        self._extend_session()
        self.delivery_feedback_label.setStyleSheet("font-size:13px; font-weight:700; color:#b91c1c;")
        self.delivery_feedback_label.setText(message)

    def _refresh_delivery_cart_display(self):
        if not self._delivery_cart:
            self.delivery_cart_label.setText("Hali hech narsa skanerlanmadi.")
            return
        lines = [f"{item['mahsulot']} — {item['count']} dona" for item in self._delivery_cart.values()]
        self.delivery_cart_label.setText("\n".join(lines))

    def _submit_finalize_delivery(self):
        if self._session is None or not self._delivery_cart or self._delivery_finalizing:
            # Avtomatik yakunlash allaqachon boshlangan (yoki sessiya
            # tugagan) bo'lsa — qayta yuborilmaydi.
            return
        self._delivery_finalizing = True
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        items = [
            {
                "mahsulot_id": mahsulot_id,
                "miqdor": entry["count"],
                "serial_ids": entry.get("serial_ids", []),
            }
            for mahsulot_id, entry in self._delivery_cart.items()
        ]
        self.delivery_finish_btn.setEnabled(False)
        self.delivery_feedback_label.setStyleSheet("font-size:13px; font-weight:700; color:#166534;")
        self.delivery_feedback_label.setText("Yakunlanmoqda...")

        worker = _ApiCallWorker(
            finalize_yuklama, server_url, token, self._session["session_token"], items,
        )
        worker.succeeded.connect(self._on_delivery_finalized)
        worker.failed.connect(self._on_delivery_finalize_failed)
        self._replace_worker("_delivery_finalize_worker", worker)
        worker.start()

    def _on_delivery_finalized(self, result: dict):
        self.delivery_finish_btn.setEnabled(True)
        self._delivery_cart = {}
        self._delivery_requested = {}
        self._delivery_mode_active = False
        if self._session:
            self._rec_stop(f"delivery-{self._session['session_token']}")
        results = result.get("results", [])
        ok_count = sum(1 for r in results if r.get("success"))
        self._show_transient_message(f"Yuklama yakunlandi ✓ ({ok_count} turdagi mahsulot)", success=True)

    def _on_delivery_finalize_failed(self, message: str):
        self._extend_session()
        self._delivery_finalizing = False
        self.delivery_finish_btn.setEnabled(True)
        self.delivery_feedback_label.setStyleSheet("font-size:13px; font-weight:700; color:#b91c1c;")
        self.delivery_feedback_label.setText(message)

    def _load_material_requests(self, session_token: str):
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        worker = _ApiCallWorker(fetch_material_requests, server_url, token, session_token)
        worker.succeeded.connect(self._on_material_requests_loaded)
        # Xatolik (masalan bu xodim ishlab chiqaruvchi emas — `ega`,
        # `omborchi` va h.k. o'z badge'ini skanerlasa server 404 qaytaradi)
        # — bo'sh ro'yxat sifatida davom etiladi, aks holda navbat hech
        # qachon ilgarilamay, panel abadiy "Ish boshlandi" holatida
        # qotib qolar edi (real sinovda ega o'z badge'ini skanerlaganda
        # aynan shu holat kuzatilgan).
        worker.failed.connect(lambda _msg: self._on_material_requests_loaded([]))
        self._replace_worker("_requests_worker", worker)
        worker.start()

    def _on_material_requests_loaded(self, so_rovlar: list):
        for r in so_rovlar:
            r["_kind"] = "material"
        self._pending_requests = list(so_rovlar)
        self._advance_queue()

    def _load_my_task_pickups(self, session_token: str):
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        worker = _ApiCallWorker(fetch_my_task_pickups, server_url, token, session_token)
        worker.succeeded.connect(self._on_my_task_pickups_loaded)
        worker.failed.connect(lambda _msg: self._on_my_task_pickups_loaded([]))
        self._replace_worker("_task_pickups_worker", worker)
        worker.start()

    def _on_my_task_pickups_loaded(self, pickups: list):
        # Sanoq/hajm (dona/litr) komponentlar — kioskda sichqoncha
        # ishlatilmagani va avtomatik 600ms tasdiq o'qishga ulgurmasdan
        # g'oyib bo'lgani uchun (real ishlab chiqarishda aniqlangan xato) —
        # endi bunday komponentlar Desktop Agent'da UMUMAN ko'rsatilmaydi,
        # pazanda ularni veb dashboardda ("Mening vazifalarim" > "Olib
        # qo'yish kerak") bitta "Oldim ✓" tugmasi bilan tasdiqlaydi.
        # Agent faqat HAQIQATAN tarozida o'lchanadigan (kg/g) komponentlarni
        # ko'rsatadi.
        weighable_pickups = [p for p in pickups if _is_weighable_birlik(p.get("birlik"))]
        for p in weighable_pickups:
            p["_kind"] = "task_pickup"
        self._pending_requests.extend(weighable_pickups)
        self._advance_queue()

    # ── Kutilayotgan QR-yorliq chop etish (159-qadam) ────────────────────

    def _load_pending_print_batch(self, session_token: str):
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        worker = _ApiCallWorker(fetch_pending_print_batch, server_url, token, session_token)
        worker.succeeded.connect(self._on_pending_print_batch_loaded)
        worker.failed.connect(lambda _msg: self._advance_queue())
        self._replace_worker("_pending_print_worker", worker)
        worker.start()

    def _on_pending_print_batch_loaded(self, batch):
        if not batch or not batch.get("serials"):
            self._advance_queue()
            return

        # Poyga holati himoyasi: agar shu partiya yaqinda (server hali
        # "chop etildi" deb ulgurmagan bo'lishi mumkin bo'lgan muddat
        # ichida) allaqachon ko'rsatilgan/chop etilgan bo'lsa — qayta
        # ko'rsatilmaydi/chop etilmaydi, faqat navbat davom etadi.
        now = time.monotonic()
        self._recently_shown_batch_ids = {
            bid: ts for bid, ts in self._recently_shown_batch_ids.items()
            if now - ts < RECENTLY_SHOWN_BATCH_TTL_SECONDS
        }
        if batch["id"] in self._recently_shown_batch_ids:
            self._advance_queue()
            return
        self._recently_shown_batch_ids[batch["id"]] = now

        self._had_any_request = True
        printer_name = db.get_setting("label_printer_name", "")
        if printer_name:
            # Fizik printerga ham (fon oqimida, "best-effort") yuboriladi
            # — lekin natijasi endi `labels_printed`ni ANIQLAMAYDI.
            # Sabab (real sinovda topilgan): Windows `win32print` RAW
            # yozish API'si printer o'chiq/uzilgan bo'lsa ham odatda
            # xatosiz "muvaffaqiyat" qaytaradi — bu faqat "ish Windows
            # navbatiga qabul qilindi" degani, HAQIQATDA qog'ozga
            # chiqqanini kafolatlamaydi. Shuning uchun operator baribir
            # pastdagi ekrandagi QR kodlarni ko'zi bilan tekshirib,
            # qo'lda "Davom etish"ni bosishi kerak — yagona haqiqiy
            # tasdiq shu.
            self._print_pending_batch_via_printer(batch, printer_name)

        # QR kodlar `print_url`/tashqi brauzer orqali EMAS (fullscreen
        # kiosk rejimida brauzer oyna ortida yashirin qolib, foydalanuvchi
        # hech narsa ko'rmasdan qolgan real bug), balki to'g'ridan-to'g'ri
        # shu oynaning o'zida, har doim ko'rinadigan holda ko'rsatiladi.
        # "Davom etish" bosilmaguncha `labels_printed` belgilanmaydi va
        # navbat davom etmaydi.
        self._show_print_batch_card(batch)

    def _print_pending_batch_via_printer(self, batch, printer_name):
        serials = batch["serials"]
        labels = [{"qr_data": s["url"], "kod": s["kod"]} for s in serials]
        width = float(db.get_setting("label_width_mm", "40") or "40")
        height = float(db.get_setting("label_height_mm", "30") or "30")
        gap = float(db.get_setting("label_gap_mm", "2") or "2")
        worker = LabelPrintWorker(printer_name, labels, width, height, gap)
        # Bu — faqat qo'shimcha (best-effort) fizik chop etish urinishi;
        # natijasi (muvaffaqiyat ham, xato ham) `print_batch_card`dagi
        # sarlavha matnida ko'rsatiladi, lekin `labels_printed`ni
        # ANIQLAMAYDI — yagona haqiqiy tasdiq operatorning "Davom etish"
        # tugmasini bosishi (`_on_print_batch_continue_clicked`).
        # Shu bilan birga, har bir yorliq uchun printer HOLATI (qog'oz
        # tugagan/oflayn/xato) alohida tekshirilib serverga xabar
        # qilinadi — muvaffaqiyatsiz kodlar keyingi badge skanida
        # qayta chop etishga taklif qilinadi.
        worker.progress.connect(lambda done, total: self._extend_session())
        worker.failed.connect(lambda msg: self._on_pending_batch_print_failed(msg))
        worker.succeeded.connect(lambda count: self._on_pending_batch_print_succeeded(count))
        worker.label_result.connect(self._report_print_result_async)
        self._replace_worker("_pending_print_label_worker", worker)
        worker.start()

    def _report_print_result_async(self, kod: str, success: bool, reason: str):
        """`LabelPrintWorker.label_result`ga ulanadi — har bir yorliqning
        HAQIQIY chop etish natijasini (printer holati tekshiruvi
        orqali) serverga xabar qiladi. Best-effort: tarmoq xatosi
        bo'lsa ham jimgina e'tiborsiz qoldiriladi (`_ApiCallWorker`
        allaqachon har qanday xatoni xavfsiz ushlaydi) — bu faqat
        qo'shimcha kuzatuv, asosiy oqimni to'xtatmasligi kerak."""
        if not kod:
            return
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        worker = _ApiCallWorker(report_print_result, server_url, token, kod, success, reason)

        def _cleanup():
            if worker in self._print_result_workers:
                self._print_result_workers.remove(worker)

        worker.finished.connect(_cleanup)
        self._print_result_workers.append(worker)
        worker.start()

    def _on_pending_batch_print_succeeded(self, count: int):
        self._extend_session()
        self.print_batch_title.setText(
            f"{count} ta yorliq printerga yuborildi ✓ — lekin bu faqat Windows navbatiga "
            "qabul qilingani, real chiqqanini ekrandagi QR kodlar bilan solishtirib tekshiring."
        )

    def _on_pending_batch_print_failed(self, message: str):
        self._extend_session()
        self.print_batch_title.setText(f"⚠ Printerga chop etishda xato: {message} — QR kodlarni ekrandan foydalaning.")

    def _show_print_batch_card(self, batch):
        # Hech qanday tugma/tasdiqlash yo'q — kiosk stansiyasida xodimning
        # mishka/klaviaturasi (hatto sensorli ekrani ham) bo'lmasligi
        # mumkin, faqat kamera/badge orqali ishlaydi. Shuning uchun bu
        # partiya ko'rsatilgan zahoti "chop etilgan" deb belgilanadi
        # (grid endi har doim shu oynaning o'zida ko'rinadi — avvalgi
        # "yashirin brauzer" bugi bu yerda mavjud emas) va bir necha
        # soniyadan keyin o'zi navbatga qaytadi.
        self._pending_print_batch = batch
        for s in batch["serials"]:
            self._own_batch_kods.add(s["kod"])
        if batch.get("is_reprint"):
            # Oldingi urinishda printer holati (qog'oz tugagan/oflayn/xato)
            # tekshiruvi orqali HAQIQATAN chop etilmagan deb aniqlangan
            # QR kodlar — endi qayta taklif qilinmoqda.
            self.print_batch_title.setText(
                f"⚠ Qayta chop etish: {batch['mahsulot']} — {len(batch['serials'])} ta yorliq oldin "
                "chop etilmagan edi. Har birini yopishtiring (yoki ekrandan chop eting)."
            )
        else:
            self.print_batch_title.setText(
                f"{batch['mahsulot']} — {len(batch['serials'])} ta QR-yorliq. Har birini yopishtiring "
                "(yoki ekrandan chop eting)."
            )

        while self.print_batch_grid.count():
            item = self.print_batch_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._batch_qr_workers = []

        server_url = db.get_setting("server_url", "")
        cols = 3
        for i, s in enumerate(batch["serials"]):
            thumb = QLabel("...")
            thumb.setFixedSize(120, 140)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setStyleSheet(
                "background:white; border:1px solid #d1fae5; border-radius:8px; font-size:10px; color:#94a3b8;"
            )
            self.print_batch_grid.addWidget(thumb, i // cols, i % cols)

            qr_image_url = server_url.rstrip("/") + f"/api/qr/image/{s['kod']}/"
            worker = _ImageFetchWorker(qr_image_url)
            worker.ready.connect(lambda content, lbl=thumb: self._on_batch_qr_image_ready(lbl, content))
            self._batch_qr_workers.append(worker)
            worker.start()

        self.print_batch_card.setVisible(True)
        if batch.get("id") is not None:
            self._mark_batch_printed(batch["id"])
        # Qayta chop etish (`is_reprint`) holatida bitta umumiy partiya
        # (`MiqdorQoshish`) yo'q — har bir Serial o'z chop etish natijasini
        # ALOHIDA xabar qiladi (`_report_print_result_async`, printer
        # holati asosida), shu orqali muvaffaqiyatli bo'lganlari
        # `chop_etilmadi=False`ga qaytadi va endi qayta taklif qilinmaydi.
        QTimer.singleShot(PRINT_BATCH_DISPLAY_MS, self._on_print_batch_display_timeout)

    def _on_batch_qr_image_ready(self, label, content: bytes):
        pixmap = QPixmap()
        if pixmap.loadFromData(content):
            pixmap = pixmap.scaled(
                100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(pixmap)
            label.setText("")

    def _on_print_batch_display_timeout(self):
        if self._pending_print_batch is None:
            return  # sessiya allaqachon tugagan/almashtirilgan
        self.print_batch_card.setVisible(False)
        self._pending_print_batch = None
        self._advance_queue()

    def _mark_batch_printed(self, batch_id: int, attempt: int = 1):
        # ANIQLANGAN TUB SABAB (real sinovda): bu chaqiruv avval "fire-and-
        # forget" edi (xato — jim yutilardi). Agar shu so'rov tarmoq
        # uzilishi/vaqtinchalik server javobsizligi sababli muvaffaqiyatsiz
        # bo'lsa, serverda `labels_printed` HECH QACHON True bo'lmaydi —
        # mijoz tomonidagi 60s "yaqinda ko'rsatilgan" keshi faqat qisqa
        # muddatli poyga holatidan himoya qiladi, lekin xodim 60 soniyadan
        # KEYIN (masalan chop etib bo'lib, keyingi vazifasi uchun) yana
        # badge'ini skanerlasa — xuddi shu partiya YANA ko'rsatiladi ("bir
        # xil QR ikki marta chiqmoqda" shikoyati aynan shu edi, DB'da
        # dublikat YO'Q ekani alohida tekshirilib tasdiqlangan). Shuning
        # uchun endi muvaffaqiyatsiz bo'lsa bir necha marta qayta uriniladi.
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        worker = _ApiCallWorker(mark_batch_printed, server_url, token, self._session["session_token"], batch_id)
        worker.failed.connect(lambda _msg, a=attempt: self._on_mark_batch_printed_failed(batch_id, a))
        self._replace_worker("_mark_printed_worker", worker)
        worker.start()

    def _on_mark_batch_printed_failed(self, batch_id: int, attempt: int):
        if attempt >= MARK_PRINTED_MAX_ATTEMPTS:
            return
        if self._session is None:
            return
        QTimer.singleShot(
            MARK_PRINTED_RETRY_MS, lambda: self._mark_batch_printed(batch_id, attempt + 1),
        )

    def _advance_queue(self):
        """Navbatdagi ish: avval xom ashyo so'rovlari (tarozi), keyin
        veb dashboardda "Ish bitdi" bosilgan (159-qadam) — hali shu
        stansiyada chop etilmagan QR-yorliq partiyasi, keyin o'ziga
        tayinlangan vazifalarning xom ashyo qatorlari (110-qadam, alohida
        vazifa-QR skanerlashsiz), keyin miqdor qo'shish so'rovlari
        (82-qadam), hech narsa qolmasa — yakunlovchi xabar va avtomatik
        yopilish."""
        if self._pending_requests:
            self._show_next_weigh_request()
            return
        self.weigh_card.setVisible(False)

        if not self._pending_print_fetched:
            self._pending_print_fetched = True
            self._load_pending_print_batch(self._session["session_token"])
            return

        if not self._task_pickups_fetched:
            self._task_pickups_fetched = True
            self._load_my_task_pickups(self._session["session_token"])
            return

        if not self._miqdor_fetched:
            self._miqdor_fetched = True
            self._load_miqdor_requests(self._session["session_token"])
            return

        if self._pending_miqdor_requests:
            self._show_next_miqdor_request()
            return

        self.miqdor_card.setVisible(False)
        if self._had_any_request:
            self._show_transient_message("Barcha so'rovlar bajarildi ✓", success=True)
        else:
            self._show_transient_message("Sizning so'rovlaringiz yo'q", success=False)

    def _show_transient_message(self, text: str, success: bool):
        """So'rov yo'q yoki hammasi bajarilgan holatda ko'rsatiladi — 3
        soniyadan so'ng avtomatik yopiladi (popup ham shu bilan yopiladi)."""
        self.weigh_card.setVisible(False)
        self.miqdor_card.setVisible(False)
        self.no_requests_label.setText(text)
        bg, fg = ("#dcfce7", "#166534") if success else ("#f1f5f9", "#64748b")
        self.no_requests_label.setStyleSheet(
            f"font-size:14px; font-weight:700; padding:14px; border-radius:10px; background:{bg}; color:{fg};"
        )
        self.no_requests_label.setVisible(True)
        QTimer.singleShot(3000, self._auto_close)

    def _auto_close(self):
        self.no_requests_label.setVisible(False)
        self.close_requested.emit()

    def _show_next_weigh_request(self):
        # Yangi so'rov uchun tarozi barqarorlik holati boshidan boshlanadi
        # — avvalgi so'rovdan qolgan "barqaror" holat yangisiga
        # tarqalib, xato vaqtda avtomatik yubormasligi uchun.
        self._scale_last_value = None
        self._scale_stable_since = 0.0
        self._auto_submit_pending = False
        self._awaiting_scale_clear = False
        self._scale_last_displayed = None

        if not self._pending_requests:
            self._current_weigh_request = None
            self._advance_queue()
            return

        self._extend_session()
        self._had_any_request = True
        self.no_requests_label.setVisible(False)
        req = self._pending_requests[0]
        self._current_weigh_request = req
        self._rec_start(f"weigh-{req['id']}", "xomashyo_tekshiruvi")

        target_text = f" ({req['target_product']} uchun)" if req.get("target_product") else ""
        self.weigh_material_label.setText(f"{req['material']}{target_text}")
        weighable = _is_weighable_birlik(req.get("birlik")) and _scale_required()

        # Tarozi sig'imi cheklangan bo'lsa (Sozlamalar > Tarozi) va bu
        # xom ashyoning qolgan (hali tortilmagan) miqdori sig'imdan katta
        # bo'lsa — kartochka bir martalik "to'liq miqdor" o'rniga NAVBATDAGI
        # porsiyani ko'rsatadi ("1/3-qism" kabi), pazanda shuni tarozida
        # tortadi, tasdiqlagach navbatdagi porsiya avtomatik chiqadi —
        # `_on_weigh_resolved`dagi `pickup_completed=False` shoxobchasi.
        if req.get("_kind") == "task_pickup" and weighable:
            remaining = req.get("remaining", req["qty"])
            capacity = _scale_capacity_for_birlik(req.get("birlik"))
            if capacity and remaining > capacity:
                total_pours = math.ceil(req["qty"] / capacity)
                pour_index = req.get("_pour_index", 1)
                pour_target = min(remaining, capacity)
                req["_pour_target"] = pour_target
                self.weigh_expected_label.setText(
                    f"{pour_index}/{total_pours}-qism: {pour_target:g} {req['birlik']}ni o'lchang "
                    f"(tarozi sig'imi {capacity:g} {req['birlik']}) — jami kerak: {req['qty']:g} {req['birlik']}"
                )
            else:
                req["_pour_target"] = remaining
                self.weigh_expected_label.setText(f"Kerakli miqdor: {remaining:g} {req['birlik']}ni o'lchang")
        elif weighable:
            req["_pour_target"] = req["qty"]
            self.weigh_expected_label.setText(f"Kerakli miqdor: {req['qty']:g} {req['birlik']}ni o'lchang")
        else:
            self.weigh_expected_label.setText(f"Kerakli miqdor: {req['qty']:g} {req['birlik']} — tasdiqlanmoqda...")
        self.weigh_input_container.setVisible(weighable)
        self.weigh_ack_btn.setVisible(not weighable)
        self.weigh_input.clear()
        # Yangi so'rov — standart holatda qo'lda kiritish mumkin (tarozi
        # sozlanmagan bo'lsa fallback); jonli tarozi qiymati kelishi bilan
        # `update_live_weight` bu maydonni faqat-o'qish holatiga o'tkazadi.
        self.weigh_input.setReadOnly(False)
        self.weigh_feedback_label.setText("")
        self.weigh_submit_btn.setEnabled(True)
        self.weigh_ack_btn.setEnabled(True)

        self.weigh_photo_label.setPixmap(QPixmap())
        self.weigh_photo_label.setText("Rasm yo'q")
        rasmi_url = req.get("rasmi")
        if rasmi_url:
            worker = _ImageFetchWorker(rasmi_url)
            worker.ready.connect(self._on_weigh_photo_ready)
            self._replace_worker("_weigh_image_worker", worker)
            worker.start()

        self.weigh_card.setVisible(True)

        if not weighable:
            # "dona"/"litr" kabi tarozida o'lchab bo'lmaydigan birlik —
            # avval kartochka o'zi 600ms'da OVOZSIZ tasdiqlanib, pazanda
            # "necha dona qadoq/litr yog' oling" matnini o'qishga
            # ulgurmasdi. Endi kartochka XODIM "Oldim ✓" tugmasini
            # bosmaguncha ochiq turadi — avtomatik yo'q.
            self.weigh_input.setText(f"{req['qty']:g}")
            return

        self.weigh_input.setFocus()

    def _on_weigh_photo_ready(self, content: bytes):
        pixmap = QPixmap()
        if pixmap.loadFromData(content):
            pixmap = pixmap.scaled(
                80, 80, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.weigh_photo_label.setPixmap(pixmap)
            self.weigh_photo_label.setText("")

    def update_live_weight(self, value: float):
        """Tarozi xizmati (`scale_service.py`) yangi o'qish jo'natganda
        chaqiriladi — faqat tortish kartochkasi ochiq turgan paytda
        maydonni jonli qiymat bilan yangilaydi (qo'lda kiritish o'rniga).
        Karta yopiq bo'lsa (masalan boshqa oyna ochiq) e'tiborsiz
        qoldiriladi. Tarozi jonli ulangani aniqlangach (birinchi haqiqiy
        o'qish kelgach), maydon FAQAT-O'QISH holatiga o'tkaziladi — soxta
        qiymat qo'lda kiritilmasligi uchun.

        158-qadamdan buyon to'liq avtomatik: qiymat `SCALE_STABLE_SECONDS`
        davomida deyarli o'zgarmasa (mahsulot tarozida barqaror turibdi
        deb topiladi) — qo'lda "Tekshirish" bosilmasdan avtomatik
        yuboriladi. Tasdiqlangandan keyin esa mahsulot tarozidan olib
        tashlanib (qiymat ~0ga qaytgach) — keyingi so'rov avtomatik
        ko'rsatiladi (`_awaiting_scale_clear`).

        **Muhim**: joriy so'rov "dona"/"litr" kabi o'lchab bo'lmaydigan
        (sanoq) birlikda bo'lsa, bu funksiya HECH NARSA QILMAYDI — aks
        holda jismonan ulangan tarozining tasodifiy shovqin qiymati
        (masalan bo'sh platforma ~0.26 kg) `_show_next_weigh_request`
        avtomatik to'ldirgan to'g'ri sonni (masalan "10 dona") bosib,
        keyin avtomatik yuborilganda serverga noto'g'ri qiymat
        (o'lchangan vazn, kerakli dona o'rniga) jo'natilib, "Miqdor
        normadan kam" xatosiga olib kelardi (real ishlab chiqarishda
        kuzatilgan xato)."""
        if not self.weigh_card.isVisible():
            return
        if self._current_weigh_request is not None and not (
            _is_weighable_birlik(self._current_weigh_request.get("birlik")) and _scale_required()
        ):
            return
        self.weigh_input.setReadOnly(True)
        if self._scale_last_displayed is None or abs(value - self._scale_last_displayed) >= SCALE_DISPLAY_THRESHOLD_KG:
            self.weigh_input.setText(f"{value:.2f}")
            self._scale_last_displayed = value

        now = time.monotonic()
        if self._scale_last_value is None or abs(value - self._scale_last_value) > SCALE_STABLE_THRESHOLD_KG:
            self._scale_last_value = value
            self._scale_stable_since = now
            return
        self._scale_last_value = value
        stable_for = now - self._scale_stable_since

        if self._awaiting_scale_clear:
            # Materialni OLIB TASHLASH jarayonida tarozi bir necha
            # soniya davomida turli oraliq qiymatlardan (masalan idishda
            # ozgina qolgan) o'tadi — oddiy tortish-barqarorligi (0.8s)
            # bunday oraliq holatni ham "bo'sh" deb noto'g'ri qabul qilib,
            # keyingi mahsulotni SHOSHILIB so'rab qolardi. Shu sabab bu
            # yerda ANCHA UZOQROQ (`SCALE_EMPTY_STABLE_SECONDS`)
            # barqarorlik talab qilinadi.
            if value <= SCALE_EMPTY_THRESHOLD_KG and stable_for >= SCALE_EMPTY_STABLE_SECONDS:
                self._awaiting_scale_clear = False
                self._show_next_weigh_request()
            return

        if stable_for < SCALE_STABLE_SECONDS:
            return  # hali barqaror deb hisoblanmaydi

        if value <= SCALE_EMPTY_THRESHOLD_KG:
            return  # tarozida hali hech narsa yo'q

        if (
            not self._auto_submit_pending
            and self._current_weigh_request is not None
            and self.weigh_submit_btn.isEnabled()
        ):
            self._auto_submit_pending = True
            self._submit_weigh()

    def _submit_weigh(self):
        if self._current_weigh_request is None or self._session is None:
            self._auto_submit_pending = False
            return
        raw = self.weigh_input.text().strip().replace(",", ".")
        try:
            measured_qty = float(raw)
        except ValueError:
            self._set_weigh_feedback("To'g'ri son kiriting.", error=True)
            self._auto_submit_pending = False
            return

        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        self.weigh_submit_btn.setEnabled(False)
        self.weigh_ack_btn.setEnabled(False)
        self._set_weigh_feedback("Tekshirilmoqda...", error=False)

        kind = self._current_weigh_request.get("_kind", "material")
        if kind == "task_pickup":
            worker = _ApiCallWorker(
                weigh_task_pickup, server_url, token, self._current_weigh_request["id"],
                self._session["session_token"], measured_qty,
            )
        else:
            worker = _ApiCallWorker(
                weigh_material_request, server_url, token, self._current_weigh_request["id"],
                self._session["session_token"], measured_qty,
            )
        worker.succeeded.connect(self._on_weigh_resolved)
        worker.failed.connect(self._on_weigh_failed)
        self._replace_worker("_weigh_worker", worker)
        worker.start()

    def _on_weigh_failed(self, message: str):
        self._auto_submit_pending = False
        self.weigh_ack_btn.setEnabled(True)
        self._set_weigh_feedback(message, error=True)

    def _on_weigh_resolved(self, result: dict):
        self._extend_session()
        self.weigh_submit_btn.setEnabled(True)
        self.weigh_ack_btn.setEnabled(True)
        self._auto_submit_pending = False
        if result.get("approved"):
            if not result.get("pickup_completed", True):
                # Faqat bitta porsiya tortildi — tarozi sig'imi tufayli
                # yana kamida bitta tortish kerak. So'rov navbatdan
                # OLIB TASHLANMAYDI, faqat "qolgan miqdor" yangilanadi va
                # kartochka navbatdagi porsiya bilan qayta ko'rsatiladi.
                req = self._pending_requests[0] if self._pending_requests else self._current_weigh_request
                remaining = result.get("remaining", 0)
                # Bu bosqich IKKI xil sababdan kelib chiqishi mumkin —
                # ular jismonan BUTUNLAY BOSHQACHA harakatni talab qiladi:
                #   (1) Tarozi SIG'IMIGA yetib to'xtatilgan (`_pour_target`
                #       haqiqatda `remaining`dan kichik edi) — tarozi
                #       to'lgan, xodim JISMONAN OLIB TASHLASHI shart, yangi
                #       porsiya uchun joy yo'q.
                #   (2) Server "asimmetrik tolerantlik" qoidasi bo'yicha
                #       ozroq tortilgan deb hisobladi (kam tortish
                #       tasdiqlanmaydi, lekin xato ham emas — "hali N kg
                #       kerak" deb ochiq qoladi), LEKIN tarozi sig'imiga
                #       yetmagan (masalan 4.78 kg so'ralib, 3.5 kg
                #       tortilgan) — bu holda tarozida hali JOY BOR,
                #       xodim shunchaki USTIGA QO'SHISHI kerak, OLIB
                #       TASHLASH SHART EMAS. Buni "tarozini bo'shating"
                #       deb talab qilish — real ishlab chiqarishda
                #       "tarozi real-time ishlamayapti, tarozi bo'shashini
                #       kutib qotib qolyapti" shikoyatiga sabab bo'lgan
                #       (chunki xodim hech qachon tarozini bo'shatmaydi,
                #       shunchaki ustiga solaveradi).
                pre_remaining = req.get("remaining", remaining) if req is not None else remaining
                pour_target = req.get("_pour_target", pre_remaining) if req is not None else pre_remaining
                capacity_hit = pour_target < pre_remaining - 0.001
                if req is not None:
                    req["remaining"] = remaining
                    req["poured"] = result.get("poured", 0)
                    req["_pour_index"] = req.get("_pour_index", 1) + 1
                    req["_pour_target"] = remaining
                if capacity_hit:
                    self.weigh_expected_label.setText(
                        f"✓ Bu porsiya qabul qilindi — TAROZINI BO'SHATING, "
                        f"keyin yana {remaining:g} kg qo'shib o'lchang."
                    )
                    self._set_weigh_feedback(
                        f"Porsiya qabul qilindi ✓ — yana {remaining:g} qoldi, tarozini bo'shating.",
                        error=False,
                    )
                    if db.get_setting("scale_com_port", "").strip():
                        self._awaiting_scale_clear = True
                    else:
                        QTimer.singleShot(1200, self._show_next_weigh_request)
                else:
                    # Tarozi hali to'lmagan — xodim OLIB TASHLAMASDAN,
                    # to'g'ridan-to'g'ri USTIGA qo'shishi kerak. Shu
                    # sabab `_awaiting_scale_clear`ga o'TILMAYDI — tarozi
                    # jonli o'qishni davom ettiradi, xodim yetarli
                    # miqdorga yetkazgach avtomatik qayta yuboriladi.
                    self.weigh_expected_label.setText(
                        f"Hali kam — yana {remaining:g} kg qo'shing (olib tashlash shart emas)."
                    )
                    self._set_weigh_feedback(
                        f"Qabul qilindi, lekin yetarli emas — yana {remaining:g} kg qo'shing.",
                        error=True,
                    )
                return

            self._set_weigh_feedback("Norma bo'yicha to'g'ri — oling! ✓", error=False)
            if self._pending_requests:
                req = self._pending_requests.pop(0)
                self._rec_stop(f"weigh-{req['id']}")
            if result.get("materials_ready"):
                # Vazifaning oxirgi xom ashyo qatori edi — endi pazanda
                # veb dashboardda "Ish bitdi" tugmasini bosishi kerak
                # (159-qadam); QR-yorliqlar shu yerda EMAS, "Ish bitdi"dan
                # keyingi KEYINGI badge skanida chop etiladi
                # (`_load_pending_print_batch`).
                self._set_weigh_feedback(
                    "Xom ashyo tortildi ✓ — mahsulotni tayyorlab bo'lgach, "
                    "dashboard'da \"Ish bitdi\"ni bosing.", error=False,
                )

            if db.get_setting("scale_com_port", "").strip():
                # Tarozi jonli ulangan — keyingi so'rov darhol/vaqt bo'yicha
                # emas, mahsulot tarozidan olib tashlanib (qiymat ~0ga
                # qaytgach, `update_live_weight`) ko'rsatiladi.
                self._awaiting_scale_clear = True
            else:
                QTimer.singleShot(1200, self._show_next_weigh_request)
        else:
            self._set_weigh_feedback(result.get("detail", "Noma'lum xato."), error=True)

    def _set_weigh_feedback(self, text: str, error: bool):
        color = "#b91c1c" if error else "#166534"
        self.weigh_feedback_label.setStyleSheet(f"font-size:13px; font-weight:700; color:{color};")
        self.weigh_feedback_label.setText(text)

    # ── Miqdor qo'shish (ishlab chiqarish natijasi) so'rovlari (82-qadam) ─

    def _load_miqdor_requests(self, session_token: str):
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")
        worker = _ApiCallWorker(fetch_miqdor_requests, server_url, token, session_token)
        worker.succeeded.connect(self._on_miqdor_requests_loaded)
        worker.failed.connect(lambda _msg: self._on_miqdor_requests_loaded([]))
        self._replace_worker("_miqdor_worker", worker)
        worker.start()

    def _on_miqdor_requests_loaded(self, so_rovlar: list):
        self._pending_miqdor_requests = list(so_rovlar)
        self._advance_queue()

    def _show_next_miqdor_request(self):
        if not self._pending_miqdor_requests:
            self._current_miqdor_request = None
            self._advance_queue()
            return

        self._extend_session()
        self._had_any_request = True
        self.no_requests_label.setVisible(False)
        req = self._pending_miqdor_requests[0]
        self._current_miqdor_request = req
        self._rec_start(f"miqdor-{req['id']}", "miqdor_qoshish")

        self.miqdor_title_label.setText(f"{req['mahsulot']} — {req['miqdor']:g} dona tayyorlandi")
        self.miqdor_feedback_label.setStyleSheet("font-size:13px; font-weight:700; color:#1e40af;")
        self.miqdor_feedback_label.setText("Tasdiqlanmoqda...")

        self.miqdor_photo_label.setPixmap(QPixmap())
        self.miqdor_photo_label.setText("Rasm yo'q")
        rasmi_url = req.get("rasmi")
        if rasmi_url:
            worker = _ImageFetchWorker(rasmi_url)
            worker.ready.connect(self._on_miqdor_photo_ready)
            self._replace_worker("_miqdor_image_worker", worker)
            worker.start()

        self.miqdor_card.setVisible(True)
        # Bu stansiyada tugma yo'q (klaviatura/sichqonchasiz kiosk) —
        # so'rov ko'rsatilgan zahoti avtomatik tasdiqlanadi.
        self._submit_miqdor_approve()

    def _on_miqdor_photo_ready(self, content: bytes):
        pixmap = QPixmap()
        if pixmap.loadFromData(content):
            pixmap = pixmap.scaled(
                80, 80, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.miqdor_photo_label.setPixmap(pixmap)
            self.miqdor_photo_label.setText("")

    def _submit_miqdor_approve(self):
        if self._current_miqdor_request is None or self._session is None:
            return
        server_url = db.get_setting("server_url", "")
        token = db.get_setting("agent_token", "")

        worker = _ApiCallWorker(
            approve_miqdor_qoshish, server_url, token, self._current_miqdor_request["id"],
            self._session["session_token"],
        )
        worker.succeeded.connect(self._on_miqdor_approve_resolved)
        worker.failed.connect(self._on_miqdor_approve_failed)
        self._replace_worker("_miqdor_approve_worker", worker)
        worker.start()

    def _on_miqdor_approve_resolved(self, result: dict):
        self._extend_session()
        serials = result.get("serials") or []
        printer_name = db.get_setting("label_printer_name", "")
        if serials and printer_name:
            # XPrinter (yoki boshqa TSPL printer) sozlangan bo'lsa — agentning
            # o'zi to'g'ridan-to'g'ri, brauzer/PDF oralig'isiz chop etadi.
            self.miqdor_feedback_label.setText(f"Tasdiqlandi ✓ — {len(serials)} ta QR chop etilmoqda...")
            self._print_serial_labels(serials, printer_name)
        elif result.get("print_url"):
            # Printer hali sozlanmagan bo'lsa — eski (brauzer/PDF) yo'l saqlanadi.
            self.miqdor_feedback_label.setText(f"Tasdiqlandi ✓ — {result.get('serial_soni', 0)} ta QR chop etilmoqda...")
            webbrowser.open(result["print_url"])
        else:
            self.miqdor_feedback_label.setText("Tasdiqlandi ✓")
        if self._pending_miqdor_requests:
            req = self._pending_miqdor_requests.pop(0)
            self._rec_stop(f"miqdor-{req['id']}")
        QTimer.singleShot(1500, self._show_next_miqdor_request)

    def _print_serial_labels(self, serials: list, printer_name: str, feedback_label=None):
        """`feedback_label` — natija qaysi label'da ko'rsatilishi kerak
        (miqdor-tasdiqlash yoki vazifa-tortish kartochkasi) — ikkalasi
        ham xuddi shu chop etish yo'lini ishlatadi (106-qadam, "Vazifalar
        paneli" ham shu funksiyani qayta ishlatadi)."""
        label = feedback_label or self.miqdor_feedback_label
        width = float(db.get_setting("label_width_mm", "40") or "40")
        height = float(db.get_setting("label_height_mm", "30") or "30")
        gap = float(db.get_setting("label_gap_mm", "2") or "2")
        labels = [{"qr_data": s["url"], "kod": s["kod"]} for s in serials]
        worker = LabelPrintWorker(printer_name, labels, width, height, gap)
        # Ko'p dona (masalan 23 ta) yorliqni ketma-ket chop etish bir necha
        # o'nlab soniya olishi mumkin — har bir bosqichda sessiyani
        # uzaytirmasak, 60 soniyalik kiosk hisoblagichi chop etish
        # tugamasdan turib sessiyani (va qolgan navbatni) jimgina o'chirib
        # yuboradi.
        worker.progress.connect(lambda done, total: self._extend_session())
        worker.failed.connect(lambda msg: self._on_label_print_failed(label, msg))
        worker.succeeded.connect(lambda count: self._on_label_print_succeeded(label, count))
        worker.label_result.connect(self._report_print_result_async)
        self._replace_worker("_label_print_worker", worker)
        worker.start()

    def _on_label_print_failed(self, label, msg: str):
        self._extend_session()
        self._set_miqdor_print_feedback(label, msg, error=True)

    def _on_label_print_succeeded(self, label, count: int):
        self._extend_session()
        self._set_miqdor_print_feedback(label, f"{count} ta yorliq chop etildi ✓", error=False)

    def _set_miqdor_print_feedback(self, label, text: str, error: bool):
        color = "#b91c1c" if error else "#166534"
        label.setStyleSheet(f"font-size:13px; font-weight:700; color:{color};")
        label.setText(text)

    def _on_miqdor_approve_failed(self, message: str):
        self._extend_session()
        # Bu stansiyada qayta urinish tugmasi yo'q — xatoni ko'rsatib,
        # keyin navbatdagi so'rovga o'tiladi (kiosk hech qachon abadiy
        # to'xtab qolmasligi kerak).
        self.miqdor_feedback_label.setStyleSheet("font-size:13px; font-weight:700; color:#b91c1c;")
        self.miqdor_feedback_label.setText(message)
        if self._pending_miqdor_requests:
            req = self._pending_miqdor_requests.pop(0)
            self._rec_stop(f"miqdor-{req['id']}")
        QTimer.singleShot(2500, self._show_next_miqdor_request)

    def _extend_session(self):
        """Faol ish (so'rov ko'rsatilmoqda, tasdiqlanmoqda, chop
        etilmoqda) davom etayotganda sessiya vaqtini to'liq qayta
        tiklaydi. Aks holda 60 soniyalik hisoblagich ishlanayotgan ishdan
        qat'i nazar tugab, navbatdagi (hali ko'rib chiqilmagan) so'rovlarni
        va hatto ekranda ochiq turgan kartani jimgina o'chirib yuborardi —
        masalan 23 ta QR yorliqni ketma-ket chop etish 60 soniyadan
        oshishi hech gap emas. Yuklama rejimida (mahsulotlar omborda
        uzoqroq joylashgan bo'lishi mumkin) — oxirgi urinishdan
        boshlab uzunroq (`DELIVERY_SESSION_TIMEOUT_SECONDS`) muddat
        beriladi."""
        if self._session:
            self._session_seconds_left = (
                DELIVERY_SESSION_TIMEOUT_SECONDS if self._delivery_mode_active
                else SESSION_TIMEOUT_SECONDS
            )
            self._update_session_label()

    def _tick_session(self):
        self._session_seconds_left -= 1
        if self._session_seconds_left <= 0:
            self._end_session()
            return
        self._update_session_label()

    def _update_session_label(self):
        if not self._session:
            return
        self.session_label.setText(
            f"Kirgan: {self._session['tuliq_ismi']} ({self._session['lavozim']}) — "
            f"avtomatik chiqish: {self._session_seconds_left}s"
        )

    def _end_session(self):
        self._rec_stop_all()
        self._session_timer.stop()
        self._session = None
        self._session_seconds_left = 0
        self._pending_requests = []
        self._current_weigh_request = None
        self._pending_miqdor_requests = []
        self._current_miqdor_request = None
        self._miqdor_fetched = False
        self._task_pickups_fetched = False
        self._pending_print_fetched = False
        self._had_any_request = False
        self._delivery_mode_active = False
        self._delivery_cart = {}
        self._delivery_requested = {}
        self._delivery_finalizing = False
        self._scale_last_value = None
        self._scale_stable_since = 0.0
        self._auto_submit_pending = False
        self._awaiting_scale_clear = False
        self._scale_last_displayed = None
        self._pending_print_batch = None
        self._own_batch_kods = set()
        self.session_banner.setVisible(False)
        self.weigh_card.setVisible(False)
        self.miqdor_card.setVisible(False)
        self.delivery_card.setVisible(False)
        self.no_requests_label.setVisible(False)
        self.print_batch_card.setVisible(False)
        self.employee_card.setVisible(False)
        self.attendance_label.setVisible(False)
        self.material_request_card.setVisible(False)
        self.result_label.setText("")
        self.close_requested.emit()
