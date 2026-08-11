import datetime as dt
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from ..models import (
    Mahsulot, YetkazibBeruvchi, YuklamaSorov,
    MiqdorQoshish, DeliveryStock, StockHistory,
    MahsulotRetsept, ProductionMaterialRequest, Savdo,
)
from . import qr_service


def effective_ish_haqi_turi(user, company):
    """Ish haqi turi endi individual (har bir xodim uchun alohida)
    sozlanishi mumkin — `User.ish_haqi_turi_override`. Bo'sh bo'lsa
    (standart) firma umumiy sozlamasi (`Company.ish_haqi_turi`) ishlatiladi
    — eski xatti-harakat o'zgarmaydi, faqat kerak bo'lganda bitta xodim
    uchun bekor qilish (override) imkoniyati qo'shildi."""
    override = getattr(user, 'ish_haqi_turi_override', '') or ''
    return override or company.ish_haqi_turi


def get_pazanda_month_stats(pazanda, company, yil=None, oy=None):
    """
    Ishlab chiqaruvchi (pazanda/ishlab_chiqaruvchi) uchun oy statistikasi
    (standart — joriy oy, `yil`/`oy` berilsa o'sha oy uchun): ishlab
    chiqargan mahsulotlari (nomi bo'yicha jamlangan miqdor) va shu oyda
    topgan puli. `ish_haqi_summasi` allaqachon jarima ayirilgan holda hisoblab
    qo'yilgan (_apply_retsept_hisobkitob), shuning uchun bu yerda sof qiymat.
    """
    now = timezone.localtime()
    if yil is None or oy is None:
        yil, oy = now.year, now.month
    month_start = timezone.make_aware(dt.datetime(yil, oy, 1))
    if oy == 12:
        month_end = timezone.make_aware(dt.datetime(yil + 1, 1, 1))
    else:
        month_end = timezone.make_aware(dt.datetime(yil, oy + 1, 1))
    qs = MiqdorQoshish.objects.filter(
        pazanda=pazanda, company=company, tasdiqlangan=True,
        vaqt_sana__gte=month_start, vaqt_sana__lt=month_end,
    )
    earnings = float(qs.aggregate(t=Sum('ish_haqi_summasi'))['t'] or 0)
    jarima = float(qs.aggregate(t=Sum('jarima_summasi'))['t'] or 0)
    # `earnings` (sof) = `gross` (ishlab chiqargani uchun to'plangan, jarimasiz) - `jarima`
    # — shuning uchun bu yerdan qayta hisoblanadi (Decimal'dan aggregatsiya
    # qilinmaydi, ikkalasi ham allaqachon bor).
    gross = earnings + jarima
    per_product = list(
        qs.values('mahsulot__nomi', 'mahsulot__turi__nomi')
        .annotate(jami_miqdor=Sum('miqdor'))
        .order_by('-jami_miqdor')
    )
    return {
        'earnings': earnings,
        'gross': gross,
        'jarima': jarima,
        'per_product': per_product,
    }

def _sotilgan_dona_soni(mahsulot, kun_soni):
    """`Savdo.smm` — bitta savdo tranzaksiyasidagi BARCHA mahsulotlarni
    "Nomi miqdor narx,Nomi2 miqdor2 narx2,..." shaklida saqlaydigan matn
    maydoni (alohida "sotuv qatori" jadvali yo'q). Shu matndan aynan shu
    mahsulotning nomi bo'yicha miqdorlarini ajratib, oxirgi `kun_soni`
    kunlik yig'indisini hisoblaydi — "sotuv tezligi" prognozi uchun."""
    cutoff = timezone.now() - dt.timedelta(days=kun_soni)
    jami = Decimal('0')
    qs = Savdo.objects.filter(
        company=mahsulot.company, vaqt_sana__gte=cutoff,
    ).values_list('smm', flat=True)
    for smm in qs:
        if not smm:
            continue
        for entry in smm.split(','):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.rsplit(' ', 2)
            if len(parts) != 3:
                continue
            nomi, miqdor_str, _narx = parts
            if nomi.strip() != mahsulot.nomi:
                continue
            try:
                jami += Decimal(str(float(miqdor_str)))
            except ValueError:
                continue
    return jami


def get_mahsulot_statistika(mahsulot, kunlar_oyiga=30):
    """Mahsulot sahifasida ko'rsatiladigan ishlab chiqarish/foyda
    statistikasi.

    Har bir tasdiqlangan `MiqdorQoshish` partiyasi o'zining ishlab
    chiqarilgan vaqtidagi tannarxini (`tannarx_snapshot`) saqlaydi —
    retsept keyinroq o'zgargan bo'lsa ham, ESKI partiyalarning haqiqiy
    xarajati o'zgarmaydi (shu snapshot orqali). Shu sababli "hozirgacha
    qancha foyda qoldi" — har bir partiyani O'ZINING tannarxi bilan
    hisoblab yig'indilanadi, hammasini bitta (joriy) tannarxga
    tenglashtirib emas. `tannarx_snapshot` bo'lmagan (eski, bu maydon
    qo'shilishidan oldingi) partiyalar uchun joriy tannarx bilan
    taxminiy hisoblanadi (aniq belgilanadi).

    Prognoz IKKI XIL tezlikka asosan alohida hisoblanadi (`_ic` — ishlab
    chiqarish, `_sotuv` — sotuv), chunki ular har doim bir xil emas: agar
    ishlab chiqarish sotuvdan tez bo'lsa, "ishlab chiqarish" prognozi
    haqiqiy foydani oshirib ko'rsatadi (sotilmagan mahsulot hali daromad
    keltirmagan) — shuning uchun ikkalasi ham ko'rsatiladi, foydalanuvchi
    o'zi solishtirsin.
    """
    partiyalar = MiqdorQoshish.objects.filter(mahsulot=mahsulot, tasdiqlangan=True)

    jami_dona = Decimal('0')
    jami_xarajat = Decimal('0')
    snapshot_yoq_soni = 0
    for p in partiyalar:
        miqdor = Decimal(str(p.miqdor))
        birlik_tannarx = p.tannarx_snapshot
        if birlik_tannarx is None:
            birlik_tannarx = mahsulot.tannarx
            snapshot_yoq_soni += 1
        jami_dona += miqdor
        jami_xarajat += Decimal(str(birlik_tannarx)) * miqdor

    narxi = Decimal(str(mahsulot.narxi or 0))
    joriy_tannarx = Decimal(str(mahsulot.tannarx or 0))

    jami_daromad = jami_dona * narxi
    jami_foyda = jami_daromad - jami_xarajat
    ortacha_tarixiy_birlik_tannarx = (jami_xarajat / jami_dona) if jami_dona > 0 else Decimal('0')

    # Oxirgi N kunlik ishlab chiqarish tezligi — bugungi/kelajakdagi
    # prognoz shu tezlik va JORIY narx/tannarx bilan hisoblanadi.
    now = timezone.now()
    davr_boshi = now - dt.timedelta(days=kunlar_oyiga)
    songi_davr_dona = MiqdorQoshish.objects.filter(
        mahsulot=mahsulot, tasdiqlangan=True, vaqt_sana__gte=davr_boshi,
    ).aggregate(t=Sum('miqdor'))['t'] or 0
    kunlik_ortacha_ic = Decimal(str(songi_davr_dona)) / Decimal(str(kunlar_oyiga))

    # Sotuv tezligi — `Savdo.smm` matnidan shu mahsulot nomi bo'yicha
    # oxirgi `kunlar_oyiga` kunda sotilgan miqdor.
    songi_davr_sotuv_dona = _sotilgan_dona_soni(mahsulot, kunlar_oyiga)
    kunlik_ortacha_sotuv = songi_davr_sotuv_dona / Decimal(str(kunlar_oyiga))

    joriy_birlik_foyda = narxi - joriy_tannarx

    def prognoz(kunlik_tezlik, kun_soni):
        return {
            'dona': (kunlik_tezlik * kun_soni).quantize(Decimal('1')),
            'foyda': kunlik_tezlik * kun_soni * joriy_birlik_foyda,
        }

    return {
        'jami_dona': jami_dona,
        'jami_xarajat': jami_xarajat,
        'jami_daromad': jami_daromad,
        'jami_foyda': jami_foyda,
        'ortacha_tarixiy_birlik_tannarx': ortacha_tarixiy_birlik_tannarx,
        'joriy_birlik_tannarx': joriy_tannarx,
        'joriy_birlik_foyda': joriy_birlik_foyda,
        'snapshot_yoq_soni': snapshot_yoq_soni,
        'kunlik_ortacha_ic': kunlik_ortacha_ic,
        'kunlik_ortacha_sotuv': kunlik_ortacha_sotuv,
        'prognoz_ic_oylik': prognoz(kunlik_ortacha_ic, 30),
        'prognoz_ic_olti_oylik': prognoz(kunlik_ortacha_ic, 180),
        'prognoz_ic_yillik': prognoz(kunlik_ortacha_ic, 365),
        'prognoz_sotuv_oylik': prognoz(kunlik_ortacha_sotuv, 30),
        'prognoz_sotuv_olti_oylik': prognoz(kunlik_ortacha_sotuv, 180),
        'prognoz_sotuv_yillik': prognoz(kunlik_ortacha_sotuv, 365),
    }


def recompute_tannarx(mahsulot):
    """
    Mahsulotning yakuniy tannarxini qayta hisoblaydi:
    (baza_tannarx (distributor uchun kirim narxi, ishlab chiqaruvchi uchun
    retsept bo'yicha hisoblangan qism) + 1 dona uchun ishchiga to'lanadigan
    ish haqi (`ishlab_chiqarish_narxi`) + mahsulotga bog'langan qo'shimcha
    xarajatlar yig'indisi) ustiga amortizatsiya foizi qo'shiladi (ustama
    sifatida ko'paytiriladi). Har doim shu funksiya orqali chaqiriladi —
    tannarx hech qayerda to'g'ridan-to'g'ri qo'lda o'rnatilmaydi.

    `ishlab_chiqariladigan` (retsept asosidagi) mahsulotlar uchun baza_tannarx
    HAR SAFAR joriy retsept (BOM) qatorlaridan JONLI hisoblanadi — alohida
    saqlanadigan "curzatma" sifatida emas. Sabab (real production bug):
    avval bu faqat retsept qatori qo'shilgan/o'chirilgan paytda yangilanardi;
    boshqa har qanday keyingi `recompute_tannarx` chaqiruvi (masalan
    qo'shimcha xarajat qo'shilganda) uni ESKI holicha qoldirar edi — agar
    o'sha snapshot biror sababdan 0 bo'lib qolgan bo'lsa (masalan mahsulot
    turi keyinroq o'zgartirilgan), xom ashyo narxi tannarxdan butunlay
    tushib qolardi, foyda haqiqatdan ancha katta ko'rsatilardi.
    Distributor mahsulotlarda baza_tannarx hamon alohida (kirim narxi)
    saqlanadi — bu yerda tegilmaydi.

    `ishlab_chiqarish_narxi` — real xarajat (ishchi haqiqatan shuncha pul
    oladi 1 dona uchun), shuning uchun tannarxga qo'shilmasa, tannarx
    haqiqiy xarajatdan kam ko'rsatilib, foyda noto'g'ri (shishirilgan)
    hisoblanardi (real bug: bu yerda unutilgan edi).

    Qo'shimcha xarajatlar ikki turda bo'lishi mumkin (har bir firma har xil
    ishlaydi): `turi='miqdor'` — aniq summa (to'g'ridan-to'g'ri qo'shiladi);
    `turi='foiz'` — baza tannarxga nisbatan foiz (baza_tannarx * foiz/100).

    Narxi (sotuv narxi) bunga tegilmaydi — ega tomonidan qo'lda kiritiladi
    (faqat tannarxdan yuqori bo'lishi talab qilinadi, tekshiruv view
    darajasida amalga oshiriladi).
    """
    update_fields = ['tannarx']
    # `mahsulot_turi` FAQAT `warehouse_type='finished'` (tayyor mahsulot)
    # uchun ma'noli (model help_text'ida ham aytilgan) — ombor xom ashyo/
    # yarim tayyor mahsulotlarida bu maydon ham default qiymat
    # ('ishlab_chiqariladigan') bilan qoladi, garchi ular hech qachon
    # retsept (BOM)ga ega bo'lmasa ham. Shu ikkinchi shartsiz tekshirilsa,
    # xom ashyolarning baza_tannarxi (bo'sh BOM=0 dan) noto'g'ri
    # nolga tushirib qo'yilardi (real bug — shu joyda topilgan).
    if mahsulot.warehouse_type == 'finished' and mahsulot.mahsulot_turi == 'ishlab_chiqariladigan':
        rows = MahsulotRetsept.objects.filter(mahsulot=mahsulot).select_related('komponent')
        baza = sum(
            (Decimal(str(r.komponent.tannarx)) * Decimal(str(r.norma_miqdor)) for r in rows),
            Decimal('0'),
        )
        if baza != Decimal(str(mahsulot.baza_tannarx or 0)):
            mahsulot.baza_tannarx = baza
            update_fields.append('baza_tannarx')
    else:
        baza = Decimal(str(mahsulot.baza_tannarx or 0))

    ish_haqi = Decimal(str(mahsulot.ishlab_chiqarish_narxi or 0))
    sotuv_ish_haqi = Decimal(str(mahsulot.sotuv_ish_haqi_narxi or 0))

    extra_miqdor = mahsulot.qoshimcha_xarajatlar.filter(turi='miqdor').aggregate(t=Sum('summa'))['t'] or 0
    extra_foiz_yigindisi = mahsulot.qoshimcha_xarajatlar.filter(turi='foiz').aggregate(t=Sum('summa'))['t'] or 0
    extra_foiz = baza * (Decimal(str(extra_foiz_yigindisi)) / Decimal('100'))

    subtotal = baza + ish_haqi + sotuv_ish_haqi + Decimal(str(extra_miqdor)) + extra_foiz
    foiz = Decimal(str(mahsulot.amortizatsiya_foizi or 0))
    mahsulot.tannarx = subtotal * (1 + foiz / Decimal('100'))
    mahsulot.save(update_fields=update_fields)
    return mahsulot.tannarx


def cascade_recompute_tannarx(komponent, _seen=None):
    """Bitta mahsulotning tannarxi o'zgarganda (masalan omborga kirim
    qilinganda o'rtacha narx o'zgarsa), shu mahsulot BOSHQA biror
    mahsulotning retseptida (`MahsulotRetsept.komponent`) ishlatilgan
    bo'lsa — o'sha "ota" mahsulot(lar)ning tannarxi ESKI holicha qolib
    ketardi, tadbirkor ularning tahrirlash sahifasini ochib "Saqlash"
    bosgunicha (bu sahifa ham `recompute_tannarx` chaqiradi) yangilanmasdi.
    Real ishlab chiqarishda aniqlangan xato — kutilgan xatti-harakat
    "jonli" (real-time) yangilanish edi.

    Bu funksiya `komponent`ni ishlatgan barcha "ota" mahsulotlarni qayta
    hisoblaydi va REKURSIV ravishda ular ham boshqa birovning retseptida
    komponent bo'lsa, yuqoriga qarab davom etadi (ko'p bosqichli BOM —
    masalan xom ashyo -> yarim tayyor -> tayyor mahsulot zanjiri).
    `_seen` — aylanma bog'lanish (bo'lmasligi kerak, lekin ehtiyot uchun)
    va bir xil mahsulotni bir necha marta qayta hisoblashning oldini
    oladi."""
    seen = _seen if _seen is not None else set()
    if komponent.id in seen:
        return
    seen.add(komponent.id)

    parent_ids = list(
        MahsulotRetsept.objects.filter(komponent=komponent)
        .exclude(mahsulot_id__in=seen)
        .values_list('mahsulot_id', flat=True).distinct()
    )
    for parent_id in parent_ids:
        parent = Mahsulot.objects.filter(id=parent_id).first()
        if not parent:
            continue
        recompute_tannarx(parent)
        cascade_recompute_tannarx(parent, seen)


def log_stock_change(actor, mahsulot, old_qty, new_qty, event_type, yetkazib_beruvchi=None, company=None):
    """Utility to log stock movement in StockHistory."""
    delta = new_qty - old_qty
    StockHistory.objects.create(
        company=company or mahsulot.company,
        actor_user=actor,
        yetkazib_beruvchi=yetkazib_beruvchi,
        mahsulot=mahsulot,
        event_type=event_type,
        old_qty=old_qty,
        new_qty=new_qty,
        delta=delta
    )

def _apply_retsept_hisobkitob(req, mahsulot):
    """
    Retsept (BOM) mavjud bo'lsa: normadan chetlashish jarimasi, tannarx va
    (agar company.ish_haqi_turi == 'per_unit' bo'lsa) ish haqini hisoblaydi.
    Retsept yo'q bo'lsa hech narsa qilmaydi (eski xulq-atvor saqlanadi).
    """
    bom_rows = list(
        MahsulotRetsept.objects.filter(company=req.company, mahsulot=mahsulot).select_related('komponent')
    )
    if not bom_rows:
        return

    prev = (
        MiqdorQoshish.objects.filter(pazanda=req.pazanda, mahsulot=mahsulot, tasdiqlangan=True)
        .exclude(id=req.id)
        .order_by('-vaqt_sana')
        .first()
    )
    window_start = prev.vaqt_sana if prev else None

    jarima_summasi = Decimal('0')
    tannarx_ulushi = Decimal('0')

    for row in bom_rows:
        expected_qty = row.norma_miqdor * req.miqdor

        matched_qs = ProductionMaterialRequest.objects.select_for_update().filter(
            company=req.company,
            producer=req.pazanda,
            target_product=mahsulot,
            material=row.komponent,
            status='approved',
            consumed_in__isnull=True,
        )
        if window_start:
            matched_qs = matched_qs.filter(reviewed_at__gte=window_start)

        actual_qty = matched_qs.aggregate(t=Sum('qty'))['t'] or 0
        matched_qs.update(consumed_in=req)

        deviation = actual_qty - expected_qty
        # Shtraf KOMPONENTNING o'z narxida hisoblanadi (tannarx yoki
        # narxi) — avval xato bilan tayyor mahsulotning ish haqi narxiga
        # (`ishlab_chiqarish_narxi`, butunlay boshqa birlik/summa)
        # ko'paytirilardi, bu arzimas og'ishlarni ham noo'rin katta
        # shtrafga aylantirardi (bu 201-qadamda `task_service._start_producing`da
        # ham xuddi shu xato topilib tuzatilgan).
        komponent_narxi = row.komponent.tannarx or row.komponent.narxi or 0
        jarima_summasi += abs(Decimal(str(deviation))) * Decimal(str(komponent_narxi))
        tannarx_ulushi += Decimal(str(row.komponent.tannarx)) * Decimal(str(row.norma_miqdor))

    req.jarima_summasi = jarima_summasi
    if req.company and req.pazanda and effective_ish_haqi_turi(req.pazanda.user, req.company) == 'per_unit':
        req.ish_haqi_summasi = Decimal(str(req.miqdor)) * mahsulot.ishlab_chiqarish_narxi - jarima_summasi

    mahsulot.baza_tannarx = tannarx_ulushi
    mahsulot.save(update_fields=['baza_tannarx'])
    unit_cost = recompute_tannarx(mahsulot)
    req.tannarx_snapshot = unit_cost


@transaction.atomic
def approve_miqdor_qoshish_service(request_id, actor):
    """Approves a production request (MiqdorQoshish) and updates product stock."""
    req = MiqdorQoshish.objects.select_for_update().get(id=request_id)
    if req.tasdiqlangan:
        return False, "Ushbu ariza allaqachon tasdiqlangan."

    mahsulot = Mahsulot.objects.select_for_update().get(id=req.mahsulot_id)
    old_qty = mahsulot.miqdori
    new_qty = old_qty + req.miqdor

    # Update Product
    mahsulot.miqdori = new_qty
    mahsulot.save()

    # Retsept (BOM) asosida jarima/tannarx/ish haqi hisob-kitobi
    _apply_retsept_hisobkitob(req, mahsulot)

    # Update Request Status
    req.tasdiqlangan = True
    req.save()

    # Log History
    log_stock_change(actor, mahsulot, old_qty, new_qty, 'ADD', company=req.company)

    # QR/Serial — mahsulot serial_granularity yoqilgan bo'lsa avtomatik yaratiladi
    qr_service.generate_serials_for_batch(req)

    return True, "Zaxira muvaffaqiyatli oshirildi."

@transaction.atomic
def approve_yuklama_sorov_service(request_id, actor, serial_ids=None):
    """Approves a delivery stock request (YuklamaSorov) and transfers stock from warehouse to delivery person."""
    req = YuklamaSorov.objects.select_for_update().get(id=request_id)
    if req.tasdiq:
        return False, "Ushbu so'rov allaqachon bajarilgan."

    # Lock the product to prevent race conditions
    mahsulot = Mahsulot.objects.select_for_update().get(id=req.mahsulot_id)
    if mahsulot.miqdori < req.miqdor:
        return False, "Omborda yetarli mahsulot mavjud emas."

    # 1. Update Warehouse Stock
    old_warehouse_qty = mahsulot.miqdori
    new_warehouse_qty = old_warehouse_qty - req.miqdor
    mahsulot.miqdori = new_warehouse_qty
    mahsulot.save()
    log_stock_change(actor, mahsulot, old_warehouse_qty, new_warehouse_qty, 'DEDUCT', yetkazib_beruvchi=req.user, company=req.company)

    # 2. Update Delivery Stock (Modern tracking)
    ds, created = DeliveryStock.objects.get_or_create(
        company=req.company,
        yetkazib_beruvchi=req.user,
        mahsulot=mahsulot
    )
    old_ds_qty = ds.qty
    ds.qty += req.miqdor
    ds.save()

    # 3. Legacy Mahsulotlar String (Backward compatibility)
    yb = req.user
    from ..functions import mahsulotlar_miqdori, yuklama_maker
    current_yuk = mahsulotlar_miqdori(yb.mahsulotlar)
    found = False
    for y in current_yuk:
        if y.nom == mahsulot.nomi:
            y.miqdor += int(req.miqdor)
            found = True
            break
    if not found:
        # If using new_yuklama class as defined in functions.py
        from ..functions import new_yuklama
        current_yuk.append(new_yuklama(mahsulot.nomi, int(req.miqdor), mahsulot.turi.nomi, mahsulot.narxi))
    
    yb.mahsulotlar = yuklama_maker(current_yuk)
    yb.save()

    # Update Request Status
    req.mode = 'done'
    req.tasdiq = True
    req.save()

    # QR/Serial — kim olib chiqqani (req.user) bilan birga yoziladi; Desktop
    # Agent aynan skanerlangan donalarni serial_ids orqali beradi, web oqimida
    # esa avvalgidek FIFO ishlaydi.
    qr_service.mark_serials_chiqarilgan(
        mahsulot, req.company, req.miqdor,
        yetkazib_beruvchi=req.user, serial_ids=serial_ids,
    )

    return True, "Yuklama muvaffaqiyatli topshirildi."

@transaction.atomic
def adjust_stock_service(mahsulot_id, new_qty, actor):
    """Admin utility to adjust warehouse stock manually."""
    mahsulot = Mahsulot.objects.select_for_update().get(id=mahsulot_id)
    old_qty = mahsulot.miqdori
    mahsulot.miqdori = new_qty
    mahsulot.save()

    log_stock_change(actor, mahsulot, old_qty, new_qty, 'ADJUST', company=mahsulot.company)
    return True
