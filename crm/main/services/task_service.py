from decimal import Decimal

from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.utils import timezone

from ..models import (
    Mahsulot, MahsulotRetsept, MiqdorQoshish, ProductionTask, TaskMaterialPickup, StockHistory, Serial,
)
from . import qr_service
from .stock_service import recompute_tannarx, log_stock_change, effective_ish_haqi_turi

# `agent_api_views.MATERIAL_WEIGH_TOLERANCE_FIXED` bilan bir xil qiymat —
# eski xom ashyo so'rovi tarozi tekshiruvi bilan tajriba/UX izchil qolishi
# uchun ataylab takrorlangan (services qatlami agent_api_views'ga
# bog'lanmasligi kerak, aks holda aylanma import bo'ladi). Tadbirkor bilan
# kelishilgan qat'iy chegara — miqdordan qat'i nazar doim 50g (foizli
# masshtablash olib tashlandi, katta miqdorlarda ham 50gdan oshmaydi).
TASK_WEIGH_TOLERANCE_FIXED = 0.05

# Desktop Agent'dagi `WEIGHABLE_BIRLIKLAR` bilan bir xil ro'yxat — faqat
# massa birliklari tarozida o'lchanadi. "dona"/"litr" kabi sanoq/hajm
# komponentlar (masalan qadoq etiketkasi, moy) endi Desktop Agent'da EMAS,
# veb dashboardda ("Mening vazifalarim" — pazanda_dashboard.html) bitta
# "Oldim ✓" tugmasi bilan tasdiqlanadi — kioskda sichqoncha ishlatilmagani
# uchun, foydalanuvchi bilan kelishilgan qaror.
WEIGHABLE_BIRLIKLAR = {"kg", "g", "gr", "gramm", "kilogramm"}


def is_weighable_birlik(birlik):
    return (birlik or "").strip().lower() in WEIGHABLE_BIRLIKLAR


def create_production_task(
    company, mahsulot, rejalashtirilgan_miqdor, sana, created_by, pazanda=None,
    qadoq_hajmi=None, force_uneven_qadoq=False,
):
    """Ega tomonidan "Vazifalar" panelida (ochiq pul — `pazanda=None`) yoki
    ishlab chiqaruvchining o'zi tomonidan (`pazanda` berilsa — o'ziga,
    darhol band qilingan holda) chaqiriladi. Mahsulotda BOM
    (MahsulotRetsept) yo'q bo'lsa vazifa yaratilmaydi — foydalanuvchi bilan
    kelishilgan qat'iy qoida ("agar mahsulot retsepti kiritilmagan bo'lsa
    task yaratilmasin"), chunki xom ashyo ehtiyoji BOM asosida avtomatik
    hisoblanadi va bu talab qilinadi.

    `qadoq_hajmi` — mahsulot `serial_granularity='batch'` bo'lsa **majburiy**
    ("non" misolida so'ralgan, 110-qadamdan keyin): 1 QR nechta donadan
    iborat qadoqni ifodalashi. Reja miqdoriga aniq bo'linmasa (masalan 50
    ta, 3 talik qadoq — 16x3 qoldiq 2) — `force_uneven_qadoq=True`
    berilmaguncha rad etiladi (aks holda qoldiq alohida 1 donalik QR
    kodlar bilan chiqarilishi haqida ogohlantiriladi).

    Muvaffaqiyatli bo'lsa (task, None, False), aks holda (None, xato_xabari,
    needs_confirm) qaytaradi — `needs_confirm=True` bo'lsa, bu "qattiq" xato
    emas, balki reja qadoqqa bo'linmagani haqida ogohlantirish (chaqiruvchi
    "Baribir davom et" tugmasini ko'rsatishi mumkin, `force_uneven_qadoq=True`
    bilan qayta chaqirilsa o'tadi)."""
    bom_rows = list(MahsulotRetsept.objects.filter(company=company, mahsulot=mahsulot).select_related('komponent'))
    if not bom_rows:
        return None, "Bu mahsulot uchun retsept (BOM) kiritilmagan — avval mahsulot sozlamalaridan retsept kiriting.", False

    if rejalashtirilgan_miqdor <= 0:
        return None, "Rejalashtirilgan miqdor 0 dan katta bo'lishi kerak.", False

    if mahsulot.serial_granularity == 'batch':
        if not qadoq_hajmi or qadoq_hajmi <= 0:
            return None, "Bu mahsulot uchun \"necha donadan bitta qadoq\" kiritilishi shart (partiya turi tanlangan).", False
        full_packages, remainder = divmod(int(rejalashtirilgan_miqdor), int(qadoq_hajmi))
        if remainder and not force_uneven_qadoq:
            return None, (
                f"{int(rejalashtirilgan_miqdor)} ta {int(qadoq_hajmi)} tadan bo'linmaydi — "
                f"{full_packages}x{int(qadoq_hajmi)} + {remainder} dona qoladi (qoldiq alohida-alohida "
                f"1 donalik QR kodlar bilan chiqariladi). Baribir davom etish uchun tasdiqlang."
            ), True
    else:
        qadoq_hajmi = None

    with transaction.atomic():
        task = ProductionTask.objects.create(
            company=company, mahsulot=mahsulot, rejalashtirilgan_miqdor=rejalashtirilgan_miqdor,
            sana=sana, created_by=created_by, qadoq_hajmi=qadoq_hajmi,
            status='claimed' if pazanda else 'open',
            pazanda=pazanda, claimed_at=timezone.now() if pazanda else None,
        )
        for row in bom_rows:
            TaskMaterialPickup.objects.create(
                task=task, komponent=row.komponent,
                expected_qty=row.norma_miqdor * rejalashtirilgan_miqdor,
            )
    return task, None, False


def claim_task(kod, pazanda, company):
    """Desktop Agent'da vazifa QR kodi (faol badge-sessiya ichida)
    skanerlanganda chaqiriladi. Faqat `status='open'` bo'lsa band qiladi.
    (task, xato_xabari) juftligini qaytaradi — muvaffaqiyat yoki band
    qilingan/topilmagan/allaqachon sizniki bo'lgan holatlar aniq
    ajratiladi."""
    with transaction.atomic():
        task = ProductionTask.objects.select_for_update().filter(kod=kod, company=company).first()
        if not task:
            return None, "Bu QR kod hech qanday vazifaga tegishli emas."
        if task.status == 'claimed' and task.pazanda_id == pazanda.id:
            return task, None
        if task.status != 'open':
            who = task.pazanda.tuliq_ismi if task.pazanda_id else "boshqa xodim"
            return None, f"Bu vazifa allaqachon band qilingan ({who})."
        task.status = 'claimed'
        task.pazanda = pazanda
        task.claimed_at = timezone.now()
        task.save(update_fields=['status', 'pazanda', 'claimed_at'])
    return task, None


def weigh_task_pickup(pickup_id, pazanda, measured_qty):
    """Vazifaning bitta BOM-komponentini (xom ashyo/yarim tayyor) tarozi
    orqali tekshiradi va tasdiqlaydi — `agent_weigh_material_request`dagi
    bilan bir xil tolerantlik formulasi. Muvaffaqiyatli bo'lsa zaxiradan
    shu zahoti ayiriladi. Agar bu vazifaning oxirgi tasdiqlanmagan
    komponenti bo'lsa — darhol `approve_production_task_service`ni
    chaqiradi, alohida "ishlab chiqarishni tasdiqlash" bosqichi kerak
    emas.

    Kerakli miqdor (`expected_qty`) bitta tarozida sig'maydigan darajada
    katta bo'lishi mumkin (tarozilar 20/30/60 kg kabi turlicha sig'imga
    ega) — shuning uchun bu funksiya BIR MARTALIK emas, KETMA-KET
    chaqiruvlarni qo'llab-quvvatlaydi: har chaqiruv `measured_qty`ni
    (bitta "tortish"/pour) `poured_qty`ga qo'shib boradi, faqat yig'indi
    `expected_qty`ga (tolerantlik ichida) yetganda pickup yakuniy
    tasdiqlanadi. Necha marta tortish kerakligini (tarozi sig'imidan kelib
    chiqib) Desktop Agent o'zi hisoblaydi — server faqat yig'indini
    kuzatadi, tarozi sig'imini bilishi shart emas.

    Natija dict qaytaradi: `{'approved': bool, 'pour_completed': bool,
    'materials_ready': bool, 'poured'/'remaining'/...}`."""
    with transaction.atomic():
        pickup = TaskMaterialPickup.objects.select_for_update().select_related(
            'task', 'komponent', 'komponent__turi',
        ).filter(id=pickup_id, task__pazanda=pazanda, tasdiqlangan=False).first()
        if not pickup:
            return {'approved': False, 'detail': "So'rov topilmadi yoki allaqachon ko'rib chiqilgan."}

        expected = pickup.expected_qty
        tolerance = TASK_WEIGH_TOLERANCE_FIXED
        new_poured = pickup.poured_qty + measured_qty
        remaining_after = expected - new_poured

        if remaining_after < -tolerance:
            # Bu tortish (avvalgi tortishlar bilan birga) kerakligidan
            # ko'p bo'lib ketdi — hali hech narsa saqlanmadi, pazanda
            # qayta tortishi kerak.
            return {
                'approved': False, 'expected': expected, 'measured': measured_qty,
                'poured': pickup.poured_qty, 'remaining': max(expected - pickup.poured_qty, 0),
                'detail': f"Miqdor normadan ko'p — qolgan kerakli: {expected - pickup.poured_qty:g}, o'lchangan: {measured_qty:g}. Qayta o'lchang.",
            }

        komponent = Mahsulot.objects.select_for_update().select_related('turi').get(id=pickup.komponent_id)
        # Zaxiradan HAQIQIY tortilgan miqdor ayiriladi (rejalashtirilgan
        # emas) — tadbirkor bilan kelishilgan qaror: 50g tolerantlik
        # ichida ozroq yoki ko'proq tortilgan bo'lsa ham, ombor qoldig'i
        # haqiqatda nima olinganini aniq aks ettirishi kerak. Har bir
        # tortish (pour) darhol ayiriladi, yakuniy tasdiqlanishni
        # kutmaydi.
        if komponent.miqdori < measured_qty:
            return {
                'approved': False, 'expected': expected, 'measured': measured_qty,
                'poured': pickup.poured_qty, 'remaining': max(expected - pickup.poured_qty, 0),
                'detail': f"{komponent.nomi} omborda yetarli emas. Qoldiq: {komponent.miqdori:g} {komponent.turi.nomi if komponent.turi else ''}.",
            }

        old_qty = komponent.miqdori
        komponent.miqdori = old_qty - measured_qty
        komponent.save(update_fields=['miqdori'])

        StockHistory.objects.create(
            actor_user=None, company=pickup.task.company, mahsulot=komponent, event_type='RAW_APPROVED',
            old_qty=old_qty, new_qty=komponent.miqdori, delta=-measured_qty,
        )

        pickup.poured_qty = new_poured

        if abs(remaining_after) > tolerance:
            # Hali navbatdagi tortish(lar) bor — pickup ochiq qoladi,
            # Desktop Agent keyingi porsiyani (qolgan miqdor va tarozi
            # sig'imidan kichigini) so'raydi.
            pickup.save(update_fields=['poured_qty'])
            return {
                'approved': True, 'pour_completed': True, 'pickup_completed': False, 'materials_ready': False,
                'expected': expected, 'measured': measured_qty,
                'poured': new_poured, 'remaining': max(remaining_after, 0),
            }

        pickup.measured_qty = new_poured
        pickup.tasdiqlangan = True
        pickup.tasdiqlangan_at = timezone.now()
        pickup.save(update_fields=['poured_qty', 'measured_qty', 'tasdiqlangan', 'tasdiqlangan_at'])

        materials_ready = False
        # `select_for_update()` shu yerda vazifaning o'zini qulflaydi —
        # aks holda ikkita xom ashyo qatori deyarli bir vaqtda tortilsa
        # (masalan ikkita komponent bo'lgan retsept), ikkalasi ham
        # "hali qolgani bor" deb noto'g'ri xulosa chiqarib, hech biri
        # holatni yangilamay, vazifa abadiy 'claimed' holatida qolib
        # ketishi mumkin edi (race condition).
        task = ProductionTask.objects.select_for_update().get(id=pickup.task_id)
        remaining = TaskMaterialPickup.objects.filter(task=task, tasdiqlangan=False).exists()
        if not remaining:
            # 159-qadamdan keyin: xom ashyo tortilgani bilan ishlab
            # chiqarish/QR chop etish DARHOL boshlanmaydi — pazanda
            # haqiqatda mahsulotni tayyorlab bo'lgach, veb dashboardda
            # "Ish bitdi" tugmasini bosishi kerak (`confirm_task_finished_materials`),
            # shundagina Serial/QR yaratiladi va Desktop Agent'ning
            # KEYINGI badge skanida chop etiladi.
            task.status = 'materials_ready'
            task.save(update_fields=['status'])
            materials_ready = True

    return {
        'approved': True, 'pour_completed': True, 'pickup_completed': True,
        'expected': expected, 'measured': measured_qty,
        'poured': new_poured, 'remaining': 0, 'materials_ready': materials_ready,
    }


@transaction.atomic
def confirm_task_finished_materials(task_id, pazanda, company):
    """Pazanda veb dashboardda "Ish bitdi" tugmasini bosganda chaqiriladi —
    xom ashyo allaqachon to'liq tortib bo'lingan ('materials_ready')
    vazifani endi haqiqatda ishlab chiqarishga o'tkazadi: `MiqdorQoshish`
    yaratiladi, Serial/QR kodlar generatsiya qilinadi. Jismoniy chop etish
    bu yerda SODIR BO'LMAYDI — printer Desktop Agent stansiyasida, shu
    xodimning KEYINGI badge skanida ishga tushadi (`get_pending_print_batch`).

    (miqdor_qoshish, xato_xabari) juftligini qaytaradi.

    **Muhim**: `select_for_update()` SQLite'da haqiqiy qator-qulfini
    bermaydi (Django uni jimgina e'tiborsiz qoldiradi) — kiosk/sensorli
    ekranda tugma ikki marta tez ketma-ket bosilsa (real sinovda aynan
    shu holat kuzatilgan — bitta vazifa uchun ikki baravar Serial/QR
    yaratilib qolgan), ikkala so'rov ham "materials_ready" holatini
    ko'rib, ikkalasi ham o'tib ketishi mumkin edi. Shuning uchun bu yerda
    himoya select emas, **bitta atomik `UPDATE ... WHERE status=...`**
    orqali ta'minlanadi — bunday UPDATE har doim (SQLite'da ham) faqat
    bitta chaqiruvchi uchun muvaffaqiyatli bo'ladi, chunki DB darajasidagi
    yagona yozish amali sifatida bajariladi."""
    updated = ProductionTask.objects.filter(
        id=task_id, company=company, pazanda=pazanda, status='materials_ready',
    ).update(status='producing')
    if not updated:
        return None, "Bu vazifa hozir \"Ish bitdi\" bosish uchun mos holatda emas."
    task = ProductionTask.objects.select_related('mahsulot').get(id=task_id)
    return _start_producing(task), None


def get_pending_print_batch(pazanda, company):
    """Desktop Agent badge-sessiya boshida chaqiriladi — veb dashboardda
    "Ish bitdi" bosilib, hali shu stansiyada chop etilmagan (`labels_printed
    =False`) yorliq partiyasi bo'lsa, shuni (`MiqdorQoshish`, `Serial` ro'yxati
    bilan) qaytaradi. Topilmasa `(None, [])`."""
    mq = MiqdorQoshish.objects.filter(
        company=company, pazanda=pazanda, source_task__isnull=False, labels_printed=False,
    ).select_related('mahsulot').order_by('vaqt_sana').first()
    if not mq:
        return None, []
    return mq, list(Serial.objects.filter(batch=mq))


def mark_batch_printed(mq_id, pazanda, company):
    """Desktop Agent chop etib bo'lgach (yoki chop etadigan hech narsa
    topilmagach) chaqiradi — shu partiya keyingi skanlarda qayta chop
    etishga taklif qilinmasligi uchun."""
    MiqdorQoshish.objects.filter(id=mq_id, company=company, pazanda=pazanda).update(labels_printed=True)


def _start_producing(task):
    """`confirm_task_finished_materials` ichidan chaqiriladi (xom ashyo
    tortilib, pazanda "Ish bitdi" bosgach). Eski `_apply_retsept_hisobkitob`dan
    farqli — vaqt-oynasi evristikasi kerak emas, chunki har bir
    `TaskMaterialPickup` allaqachon aynan shu vazifaga bog'langan.

    Bu bosqichda hali zaxira qo'shilmaydi/vazifa yakunlanmaydi — faqat
    (tasdiqlanmagan) `MiqdorQoshish` konteyner yaratiladi va Serial/QR
    kodlar generatsiya qilinadi (chop etish — Desktop Agent'ning keyingi
    badge skanida, `get_pending_print_batch` orqali). Har bir dona tayyor
    bo'lgach, uning QR kodi jismonan yopishtiriladi va keyin skanerlanadi —
    necha dona haqiqatda tayyor bo'lgani shu skanerlar orqali kuzatiladi
    (`finish_production_task_service`).

    `serial_granularity == 'unit'` (har biriga alohida QR) VA `'batch'`
    (partiya/qadoq QR, `Serial.dona_soni` orqali necha donani
    ifodalashi belgilanadi) — ikkalasida ham shu "skanerlash orqali
    kuzatish" ishlaydi, faqat progress `Serial.dona_soni` yig'indisi
    bilan hisoblanadi (`unit`da har doim 1, `batch`da qadoq hajmiga
    teng). Faqat `serial_granularity == 'none'` (chop etiladigan QR
    umuman yo'q) holatida eski xatti-harakat saqlanadi: darhol, to'liq
    reja miqdori bilan yakunlanadi (shtrafsiz) — chunki kutish uchun
    hech qanday QR mavjud emas."""
    mahsulot = Mahsulot.objects.select_for_update().get(id=task.mahsulot_id)
    pickups = list(task.material_pickups.select_related('komponent').all())

    jarima_summasi = Decimal('0')
    tannarx_ulushi = Decimal('0')
    for pickup in pickups:
        deviation = pickup.measured_qty - pickup.expected_qty
        jarima_summasi += abs(Decimal(str(deviation))) * mahsulot.ishlab_chiqarish_narxi
        bom_row = MahsulotRetsept.objects.filter(
            company=task.company, mahsulot=mahsulot, komponent=pickup.komponent,
        ).first()
        if bom_row:
            tannarx_ulushi += Decimal(str(pickup.komponent.tannarx)) * Decimal(str(bom_row.norma_miqdor))

    mahsulot.baza_tannarx = tannarx_ulushi
    mahsulot.save(update_fields=['baza_tannarx'])
    recompute_tannarx(mahsulot)

    # `MiqdorQoshish.source_task` DB darajasida UNIQUE (migratsiya) —
    # bu shu funksiya qandaydir sabab bilan (masalan "Ish bitdi" tugmasi
    # ketma-ket ikki marta bosilib, real sinovda kuzatilganidek) bir
    # necha marta chaqirilsa ham, Serial/QR ikki marta GENERATSIYA
    # QILINMASLIGINI kafolatlaydi — ikkinchi urinish shu yerda xavfsiz
    # to'xtaydi, mavjud partiya qaytariladi.
    try:
        with transaction.atomic():
            miqdor_qoshish = MiqdorQoshish.objects.create(
                company=task.company, pazanda=task.pazanda, mahsulot=mahsulot,
                miqdor=task.rejalashtirilgan_miqdor, tasdiqlangan=False,
                jarima_summasi=jarima_summasi, source_task=task,
            )
    except IntegrityError:
        return MiqdorQoshish.objects.get(source_task=task)

    serials = qr_service.generate_serials_for_batch(miqdor_qoshish, qadoq_hajmi=task.qadoq_hajmi)
    if not serials:
        # `serial_granularity == 'none'` — chop etiladigan yorliq yo'q,
        # Desktop Agent'ning "chop etilmagan partiya" navbatida abadiy
        # osilib qolmasligi uchun darhol "chop etilgan" deb belgilanadi.
        miqdor_qoshish.labels_printed = True
        miqdor_qoshish.save(update_fields=['labels_printed'])

    if mahsulot.serial_granularity != 'none':
        task.status = 'producing'
        task.save(update_fields=['status'])
    else:
        # `finish_production_task_service` DB'da yangi qatorni mutatsiya
        # qiladi — chaqiruvchiga eskirgan (tasdiqlanmagan) obyekt emas,
        # yangilangan holatni qaytarish uchun natijasini ishlatamiz.
        miqdor_qoshish = finish_production_task_service(task, actual_count=task.rejalashtirilgan_miqdor)

    return miqdor_qoshish


@transaction.atomic
def finish_production_task_service(task, actor=None, actual_count=None):
    """Vazifani yakunlaydi — ikki holatda chaqiriladi:
    (1) avtomatik, oxirgi dona QR skanerlanib, kuzatilgan son rejaga
    yetganda (`actual_count=None` — shu yerda serverning o'zi
    `Serial.scan_soni` orqali hisoblaydi); (2) qo'lda, "Tugatish"
    tugmasi orqali, hali reja to'liq bajarilmagan holda erta yopilganda.

    Ikkinchi holatda: ishlab chiqarilmagan dona uchun shtraf qo'llaniladi
    — `(reja - haqiqiy) * mahsulot.baza_tannarx` ("retsept narxi" — BOM
    asosida hisoblangan 1 donaning xom ashyo tannarxi), ish haqidan
    ayiriladi. Zaxiraga esa har doim faqat HAQIQIY (skanerlangan) son
    qo'shiladi — reja emas."""
    mq = task.miqdor_qoshishlar.get()
    mahsulot = Mahsulot.objects.select_for_update().get(id=mq.mahsulot_id)

    if actual_count is None:
        # `dona_soni` yig'indisi ishlatiladi (shunchaki qator soni emas) —
        # `unit` granularityda har bir Serial 1 donani anglatadi, `batch`da
        # esa har bir skanerlangan QR o'zining qadoq hajmicha (masalan 3
        # yoki qoldiq uchun 1) qo'shadi.
        actual_count = Serial.objects.filter(batch=mq, scan_soni__gte=1).aggregate(
            t=Sum('dona_soni'),
        )['t'] or 0

    shortfall = max(task.rejalashtirilgan_miqdor - actual_count, 0)
    penalty = Decimal(str(shortfall)) * Decimal(str(mahsulot.baza_tannarx))

    old_qty = mahsulot.miqdori
    new_qty = old_qty + actual_count
    mahsulot.miqdori = new_qty
    mahsulot.save(update_fields=['miqdori'])
    unit_cost = recompute_tannarx(mahsulot)

    # Erta yopishdagi shtraf (`penalty`) `jarima_summasi`ga QO'SHILADI —
    # avval faqat `ish_haqi_summasi` hisobida "yashirin" edi (maydonning
    # o'zi yangilanmasdi), shuning uchun hisobotlarda ("Bu oy topgan
    # puli") jami shtraf hech qachon ko'rinmas, foydalanuvchiga faqat
    # tushunarsiz manfiy yakuniy summa chiqardi. Endi `jarima_summasi`
    # HAR DOIM haqiqiy jami shtrafni aks ettiradi (tortishdagi og'ish +
    # bajarilmagan dona uchun shtraf).
    mq.jarima_summasi = mq.jarima_summasi + penalty

    ish_haqi_summasi = Decimal('0')
    if task.company and task.pazanda and effective_ish_haqi_turi(task.pazanda.user, task.company) == 'per_unit':
        ish_haqi_summasi = Decimal(str(actual_count)) * mahsulot.ishlab_chiqarish_narxi - mq.jarima_summasi

    mq.miqdor = actual_count
    mq.tasdiqlangan = True
    mq.ish_haqi_summasi = ish_haqi_summasi
    mq.tannarx_snapshot = unit_cost
    mq.save(update_fields=['miqdor', 'tasdiqlangan', 'ish_haqi_summasi', 'tannarx_snapshot', 'jarima_summasi'])

    log_stock_change(actor, mahsulot, old_qty, new_qty, 'ADD', company=task.company)

    task.status = 'done'
    task.completed_at = timezone.now()
    task.save(update_fields=['status', 'completed_at'])

    return mq


def task_progress(task):
    """Vazifaning jonli holati — dashboardda "ishlab chiqildi: count/max"
    ko'rsatish uchun. `producing` bo'lmagan holatlarda ham xavfsiz
    ishlaydi (0 qaytaradi)."""
    if task.status not in ('producing', 'done'):
        return 0
    mq = task.miqdor_qoshishlar.first()
    if not mq:
        return 0
    if task.status == 'done':
        return int(mq.miqdor)
    return Serial.objects.filter(batch=mq, scan_soni__gte=1).aggregate(t=Sum('dona_soni'))['t'] or 0
