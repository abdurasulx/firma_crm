"""KPI (asosiy ko'rsatkichlar) tizimi — egadan boshqa BARCHA xodim
turlari uchun, joriy oy bo'yicha. Har bir rol o'ziga xos ko'rsatkichga
ega (masalan ishlab chiqaruvchida "muddatga rioya", omborchida "so'rovga
javob tezligi", savdogar/yetkazib beruvchida "qaytarish nisbati")."""
import datetime as dt
from decimal import Decimal

from django.db.models import Avg, Count, F, Sum
from django.utils import timezone

from ..models import (
    KpiQoida, Mahsulot, MiqdorQoshish, Pazanda, ProductionTask,
    ProductionMaterialRequest, Savdo, YetkazibBeruvchi,
    qaytarilgan_mahsulotlar,
)


def _month_bounds(yil=None, oy=None):
    now = timezone.localtime()
    if yil is None or oy is None:
        yil, oy = now.year, now.month
    start = timezone.make_aware(dt.datetime(yil, oy, 1))
    end = timezone.make_aware(dt.datetime(yil + 1, 1, 1)) if oy == 12 else timezone.make_aware(dt.datetime(yil, oy + 1, 1))
    return start, end


def _pazanda_kpi(user, company, start, end):
    pz = Pazanda.objects.filter(user=user, company=company).first()
    if not pz:
        return None
    tasks = ProductionTask.objects.filter(
        company=company, pazanda=pz, status='done', completed_at__gte=start, completed_at__lt=end,
    )
    jami = tasks.count()
    # `kechikdi` — Python property, DB darajasida filtrlab bo'lmaydi —
    # kichik oylik hajmda (odatda o'nlab vazifa) Python'da hisoblash
    # yetarli, qo'shimcha so'rov shart emas.
    kechikkan = sum(1 for t in tasks if t.muddat and t.kechikdi)
    muddatli_jami = sum(1 for t in tasks if t.muddat)
    ozvaqtida_foiz = round(100 * (muddatli_jami - kechikkan) / muddatli_jami, 1) if muddatli_jami else None
    return {
        'turi': 'ishlab_chiqaruvchi',
        'jami_vazifa': jami,
        'muddatli_vazifa': muddatli_jami,
        'kechikkan_vazifa': kechikkan,
        'ozvaqtida_foiz': ozvaqtida_foiz,
    }


def _omborchi_kpi(user, company, start, end):
    reqs = ProductionMaterialRequest.objects.filter(
        company=company, reviewed_by=user, reviewed_at__gte=start, reviewed_at__lt=end,
    ).exclude(status='waiting')
    jami = reqs.count()
    tasdiqlangan = reqs.filter(status='approved').count()
    avg_seconds = reqs.annotate(
        kutish=F('reviewed_at') - F('created_at'),
    ).aggregate(t=Avg('kutish'))['t']
    avg_daqiqa = round(avg_seconds.total_seconds() / 60, 1) if avg_seconds else None
    return {
        'turi': 'omborchi',
        'jami_korib_chiqilgan': jami,
        'tasdiqlangan': tasdiqlangan,
        'orta_javob_daqiqa': avg_daqiqa,
    }


def _savdo_qaytarish_kpi(user, company, start, end, filter_field):
    # `Savdo.savdogar` — `User`ga FK, lekin `Savdo.yetkazib_beruvchi` —
    # `YetkazibBeruvchi`ga FK (User emas) — shu farqni hisobga olish kerak.
    if filter_field == 'yetkazib_beruvchi':
        from ..models import YetkazibBeruvchi
        yb = YetkazibBeruvchi.objects.filter(user=user, company=company).first()
        savdo_filter = {'yetkazib_beruvchi': yb, 'company': company, 'vaqt_sana__gte': start, 'vaqt_sana__lt': end} if yb else None
    else:
        savdo_filter = {filter_field: user, 'company': company, 'vaqt_sana__gte': start, 'vaqt_sana__lt': end}

    if savdo_filter is None:
        savdolar = Savdo.objects.none()
    else:
        savdolar = Savdo.objects.filter(**savdo_filter)
    jami_savdo_soni = savdolar.count()
    jami_savdo_summa = savdolar.aggregate(t=Sum('summa'))['t'] or 0

    qaytarish_soni = 0
    if filter_field == 'yetkazib_beruvchi' and savdo_filter is not None:
        qaytarish_soni = qaytarilgan_mahsulotlar.objects.filter(
            yetkazib_beruvchi=savdo_filter['yetkazib_beruvchi'], company=company,
            sana__gte=start, sana__lt=end,
        ).exclude(status='rejected').count()

    qaytarish_nisbati = round(100 * qaytarish_soni / jami_savdo_soni, 1) if jami_savdo_soni else None
    return {
        'turi': 'savdogar' if filter_field == 'savdogar' else 'yetkazib_beruvchi',
        'jami_savdo_soni': jami_savdo_soni,
        'jami_savdo_summa': jami_savdo_summa,
        'qaytarish_soni': qaytarish_soni,
        'qaytarish_nisbati_foiz': qaytarish_nisbati,
    }


def _month_ishlab_chiqarish_stats(user, company, start, end, mahsulot=None):
    """Ishlab chiqaruvchi shu oyda tasdiqlangan (ombor qoldig'iga
    qo'shilgan) ishlab chiqarish miqdori — dona (soni) va summa
    (mahsulot sotuv narxi asosidagi qiymat)."""
    pazanda = Pazanda.objects.filter(user=user, company=company).first()
    if not pazanda:
        return {'dona': 0.0, 'summa': 0.0}
    qs = MiqdorQoshish.objects.filter(
        company=company, pazanda=pazanda, tasdiqlangan=True, vaqt_sana__gte=start, vaqt_sana__lt=end,
    )
    if mahsulot:
        qs = qs.filter(mahsulot=mahsulot)
    dona = qs.aggregate(t=Sum('miqdor'))['t'] or 0.0
    summa = 0.0
    for row in qs.values('mahsulot').annotate(q=Sum('miqdor')):
        m = Mahsulot.objects.filter(id=row['mahsulot']).first()
        if m:
            summa += float(row['q']) * float(m.narxi)
    return {'dona': float(dona), 'summa': summa}


def _month_savdo_stats(user, company, start, end, mahsulot=None):
    """Savdogar/yetkazib beruvchi shu oyda amalga oshirgan savdolari —
    dona (sotilgan mahsulot soni) va summa (savdo qiymati). `Savdo.smm`
    erkin matn ("nomi soni, nomi soni") sifatida saqlanadi, shuning
    uchun mahsulot-bo'yicha filtrlash uchun parse qilish kerak."""
    from ..functions import mahsulotlar_miqdori

    if user.type == 'yetkazib_beruvchi':
        yb = YetkazibBeruvchi.objects.filter(user=user, company=company).first()
        if not yb:
            return {'dona': 0.0, 'summa': 0.0}
        savdolar = Savdo.objects.filter(
            yetkazib_beruvchi=yb, company=company, vaqt_sana__gte=start, vaqt_sana__lt=end,
        )
    else:
        savdolar = Savdo.objects.filter(
            savdogar=user, company=company, vaqt_sana__gte=start, vaqt_sana__lt=end,
        )

    if mahsulot is None:
        summa = float(savdolar.aggregate(t=Sum('summa'))['t'] or 0)
        dona = 0.0
        for s in savdolar:
            for item in mahsulotlar_miqdori(s.smm, company):
                dona += float(item.miqdor)
        return {'dona': dona, 'summa': summa}

    dona = 0.0
    summa = 0.0
    for s in savdolar:
        for item in mahsulotlar_miqdori(s.smm, company):
            if item.nom == mahsulot.nomi:
                dona += float(item.miqdor)
                summa += float(item.miqdor) * float(mahsulot.narxi)
    return {'dona': dona, 'summa': summa}


def compute_kpi_bonus(user, company, yil=None, oy=None):
    """Ega firma sozlamalarida belgilagan `KpiQoida`larni (xodim TURI
    bo'yicha, individual emas) tekshiradi. Bir turga bir nechta qoida
    (bosqich) bo'lishi mumkin — barchasi mustaqil tekshiriladi, chegaraga
    yetganlari qo'shiladi (progressiv — bir vaqtda bir nechtasi faol
    bo'lishi mumkin). `bonus_turi='foiz'` faqat `olchov_turi='summa'`da
    ma'noli — 'dona'da har doim 'fiks' kabi ishlaydi (foiz % qiymatga
    emas, songa nisbatan ma'nosiz bo'lardi)."""
    xodim_turi = None
    if user.type in ('pazanda', 'ishlab_chiqaruvchi'):
        xodim_turi = 'ishlab_chiqaruvchi'
    elif user.type in ('savdogar', 'yetkazib_beruvchi'):
        xodim_turi = user.type

    if not xodim_turi:
        return {'bonus_summasi': Decimal('0'), 'qoidalar': []}

    start, end = _month_bounds(yil, oy)
    qoidalar = KpiQoida.objects.filter(company=company, xodim_turi=xodim_turi, faol=True).select_related('mahsulot')

    bonus_summasi = Decimal('0')
    natijalar = []
    cache = {}
    for q in qoidalar:
        key = q.mahsulot_id
        if key not in cache:
            if xodim_turi == 'ishlab_chiqaruvchi':
                cache[key] = _month_ishlab_chiqarish_stats(user, company, start, end, mahsulot=q.mahsulot)
            else:
                cache[key] = _month_savdo_stats(user, company, start, end, mahsulot=q.mahsulot)
        stats = cache[key]
        amalda = stats['dona'] if q.olchov_turi == 'dona' else stats['summa']
        chegara = float(q.chegara)
        yetdi = amalda >= chegara and chegara > 0

        if yetdi:
            if q.bonus_turi == 'foiz' and q.olchov_turi == 'summa':
                bonus_summasi += Decimal(str(amalda)) * q.bonus_qiymati / Decimal('100')
            else:
                bonus_summasi += q.bonus_qiymati

        natijalar.append({
            'qoida': q,
            'amalda': amalda,
            'yetdi': yetdi,
            'progress_foiz': min(round(amalda / chegara * 100, 1), 100) if chegara > 0 else 0,
        })

    return {'bonus_summasi': bonus_summasi, 'qoidalar': natijalar, 'bosqichlar': _group_into_bosqichlar(natijalar)}


def _group_into_bosqichlar(natijalar):
    """Bir xil o'lchov (mahsulot + dona/summa) bo'yicha bosqichma-bosqich
    qoidalarni BITTA umumiy progress-bar uchun guruhlaydi — har bir
    bosqich chiziqning bir SEGMENTI bo'ladi (masalan 300 va 500 dona
    qoidalari bir xil chiziqda ketma-ket to'ladi, ikkita alohida chiziq
    emas). Segmentlar chegara oralig'iga PROPORSIONAL kenglikda
    chiziladi (0-300 segmenti, 300-500 segmenti kabi)."""
    groups = {}
    order = []
    for n in natijalar:
        q = n['qoida']
        key = (q.mahsulot_id, q.olchov_turi)
        if key not in groups:
            groups[key] = {
                'label': q.mahsulot.nomi if q.mahsulot else "Jami",
                'olchov_turi_display': q.get_olchov_turi_display(),
                'amalda': n['amalda'],
                'tiers': [],
            }
            order.append(key)
        groups[key]['tiers'].append(n)

    bosqichlar = []
    for key in order:
        g = groups[key]
        tiers = sorted(g['tiers'], key=lambda n: float(n['qoida'].chegara))
        prev_chegara = 0.0
        amalda = g['amalda']
        segments = []
        for n in tiers:
            chegara = float(n['qoida'].chegara)
            span = chegara - prev_chegara
            segment_percent = min(max((amalda - prev_chegara) / span * 100, 0), 100) if span > 0 else 100
            segments.append({
                'qoida': n['qoida'],
                'yetdi': n['yetdi'],
                'segment_percent': round(segment_percent, 1),
                'width_percent': round(100 / len(tiers), 2),
            })
            prev_chegara = chegara
        bosqichlar.append({
            'label': g['label'],
            'olchov_turi_display': g['olchov_turi_display'],
            'amalda': amalda,
            'segments': segments,
        })
    return bosqichlar


def get_employee_kpi(user, company, yil=None, oy=None):
    """Xodim turiga qarab mos KPI to'plamini qaytaradi — `ega` uchun
    `None` (KPI faqat egadan boshqa xodimlar uchun mo'ljallangan)."""
    if user.type == 'ega':
        return None
    start, end = _month_bounds(yil, oy)

    result = None
    if user.type in ('pazanda', 'ishlab_chiqaruvchi'):
        result = _pazanda_kpi(user, company, start, end)
    elif user.type == 'omborchi':
        result = _omborchi_kpi(user, company, start, end)
    elif user.type == 'savdogar':
        result = _savdo_qaytarish_kpi(user, company, start, end, 'savdogar')
    elif user.type == 'yetkazib_beruvchi':
        result = _savdo_qaytarish_kpi(user, company, start, end, 'yetkazib_beruvchi')

    if result and user.type in ('pazanda', 'ishlab_chiqaruvchi', 'savdogar', 'yetkazib_beruvchi'):
        result['bonus'] = compute_kpi_bonus(user, company, yil=yil, oy=oy)

    return result
