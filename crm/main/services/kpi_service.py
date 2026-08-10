"""KPI (asosiy ko'rsatkichlar) tizimi — egadan boshqa BARCHA xodim
turlari uchun, joriy oy bo'yicha. Har bir rol o'ziga xos ko'rsatkichga
ega (masalan ishlab chiqaruvchida "muddatga rioya", omborchida "so'rovga
javob tezligi", savdogar/yetkazib beruvchida "qaytarish nisbati")."""
import datetime as dt

from django.db.models import Avg, Count, F, Sum
from django.utils import timezone

from ..models import (
    Pazanda, ProductionTask, ProductionMaterialRequest, Savdo,
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


def get_employee_kpi(user, company, yil=None, oy=None):
    """Xodim turiga qarab mos KPI to'plamini qaytaradi — `ega` uchun
    `None` (KPI faqat egadan boshqa xodimlar uchun mo'ljallangan)."""
    if user.type == 'ega':
        return None
    start, end = _month_bounds(yil, oy)

    if user.type in ('pazanda', 'ishlab_chiqaruvchi'):
        return _pazanda_kpi(user, company, start, end)
    if user.type == 'omborchi':
        return _omborchi_kpi(user, company, start, end)
    if user.type == 'savdogar':
        return _savdo_qaytarish_kpi(user, company, start, end, 'savdogar')
    if user.type == 'yetkazib_beruvchi':
        return _savdo_qaytarish_kpi(user, company, start, end, 'yetkazib_beruvchi')
    return None
