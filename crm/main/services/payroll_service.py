import datetime as dt
from decimal import Decimal

from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.utils import timezone

from ..models import User, Pazanda, XodimMaosh, XodimTolov, XodimOyYopish
from .stock_service import get_pazanda_month_stats


def get_month_bounds(yil, oy):
    month_start = timezone.make_aware(dt.datetime(yil, oy, 1))
    if oy == 12:
        month_end = timezone.make_aware(dt.datetime(yil + 1, 1, 1))
    else:
        month_end = timezone.make_aware(dt.datetime(yil, oy + 1, 1))
    return month_start, month_end


def compute_oylik_ish_haqi(user, company, yil=None, oy=None):
    """Xodimning shu oy uchun "ishlab topgan" summasini hisoblaydi.

    Firma `ish_haqi_turi == 'per_unit'` bo'lsa va xodimga bog'langan
    `Pazanda` profili mavjud bo'lsa — `MiqdorQoshish.ish_haqi_summasi`
    yig'indisidan (jarima allaqachon ichida ayirilgan) hisoblanadi.
    Aks holda — `XodimMaosh.oylik_maosh` (belgilanmagan bo'lsa 0).
    """
    now = timezone.localtime()
    if yil is None or oy is None:
        yil, oy = now.year, now.month

    if company.ish_haqi_turi == 'per_unit':
        pazanda = Pazanda.objects.filter(user=user, company=company).first()
        if pazanda:
            stats = get_pazanda_month_stats(pazanda, company, yil=yil, oy=oy)
            return {'summa': Decimal(str(stats['earnings'])), 'manba': 'per_unit'}

    maosh = XodimMaosh.objects.filter(user=user, company=company).first()
    summa = maosh.oylik_maosh if maosh else Decimal('0')
    return {'summa': summa, 'manba': 'fixed'}


def set_fixed_salary(user, company, oylik_maosh, updated_by):
    oylik_maosh = Decimal(str(oylik_maosh))
    if oylik_maosh < 0:
        raise ValueError("Oylik maosh manfiy bo'lishi mumkin emas.")
    maosh, _ = XodimMaosh.objects.get_or_create(user=user, company=company)
    maosh.oylik_maosh = oylik_maosh
    maosh.updated_by = updated_by
    maosh.save(update_fields=['oylik_maosh', 'updated_by', 'updated_at'])
    return maosh


def is_month_closed(user, yil, oy):
    return XodimOyYopish.objects.filter(user=user, yil=yil, oy=oy).exists()


def give_avans(user, company, summa, sana, berdi, izoh=''):
    summa = Decimal(str(summa))
    if summa <= 0:
        raise ValueError("Summa 0 dan katta bo'lishi kerak.")
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        if is_month_closed(user, sana.year, sana.month):
            raise ValueError("Bu oy allaqachon yopilgan, avans bera olmaysiz.")
        return XodimTolov.objects.create(
            user=user, company=company, turi='avans', summa=summa, sana=sana,
            berdi=berdi, izoh=izoh,
        )


def close_month(user, company, closed_by, yil=None, oy=None, izoh=''):
    now = timezone.localtime()
    if yil is None or oy is None:
        yil, oy = now.year, now.month

    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        if is_month_closed(user, yil, oy):
            raise ValueError("Bu oy uchun hisob-kitob allaqachon yopilgan.")

        earned = compute_oylik_ish_haqi(user, company, yil=yil, oy=oy)
        avans_sum = XodimTolov.objects.filter(
            user=user, company=company, turi='avans', sana__year=yil, sana__month=oy,
        ).aggregate(t=Sum('summa'))['t'] or Decimal('0')

        qoldiq = earned['summa'] - avans_sum
        yakuniy = max(qoldiq, Decimal('0'))

        try:
            snapshot = XodimOyYopish.objects.create(
                user=user, company=company, yil=yil, oy=oy,
                ishlab_topgan=earned['summa'], avanslar_jami=avans_sum,
                hisoblangan_qoldiq=qoldiq, tolangan_yakuniy_summa=yakuniy,
                manba=earned['manba'], yopgan_user=closed_by, izoh=izoh,
            )
        except IntegrityError:
            raise ValueError("Bu oy uchun hisob-kitob allaqachon yopilgan.")

        if yakuniy > 0:
            XodimTolov.objects.create(
                user=user, company=company, turi='yakuniy', summa=yakuniy,
                sana=timezone.localdate(), berdi=closed_by, oy_yopish=snapshot,
            )
        return snapshot


def get_month_summary(user, company, yil=None, oy=None):
    now = timezone.localtime()
    if yil is None or oy is None:
        yil, oy = now.year, now.month

    earned = compute_oylik_ish_haqi(user, company, yil=yil, oy=oy)
    avans_sum = XodimTolov.objects.filter(
        user=user, company=company, turi='avans', sana__year=yil, sana__month=oy,
    ).aggregate(t=Sum('summa'))['t'] or Decimal('0')
    snapshot = XodimOyYopish.objects.filter(user=user, company=company, yil=yil, oy=oy).first()

    return {
        'earned': earned['summa'],
        'manba': earned['manba'],
        'avans_sum': avans_sum,
        'qoldiq': earned['summa'] - avans_sum,
        'is_closed': snapshot is not None,
        'snapshot': snapshot,
        'yil': yil,
        'oy': oy,
    }


def get_payment_history(user, company, limit=50):
    return XodimTolov.objects.filter(user=user, company=company).order_by('-sana', '-created_at')[:limit]


def get_outstanding_previous_months(company, lookback_months=12):
    """O'tgan oylardan qaysilari hali **yopilmagan** (`XodimOyYopish`
    yo'q) va shu oy uchun (ishlab topgan − avans) musbat qoldiq
    borligini topadi — "yopishni unutib qo'ygan" oylar, ega e'tibor
    berishi kerak bo'lgan qarzdorlik ro'yxati. Joriy oy tekshirilmaydi
    (u hali tugamagan, "kechikkan" hisoblanmaydi)."""
    now = timezone.localtime()
    months = []
    yil, oy = now.year, now.month
    for _ in range(lookback_months):
        oy -= 1
        if oy == 0:
            oy = 12
            yil -= 1
        months.append((yil, oy))

    results = []
    users = User.objects.filter(company=company).exclude(type__in=['ega', 'desktop_agent'])
    for user in users:
        for (m_yil, m_oy) in months:
            if is_month_closed(user, m_yil, m_oy):
                continue
            earned = compute_oylik_ish_haqi(user, company, yil=m_yil, oy=m_oy)['summa']
            avans_sum = XodimTolov.objects.filter(
                user=user, company=company, turi='avans', sana__year=m_yil, sana__month=m_oy,
            ).aggregate(t=Sum('summa'))['t'] or Decimal('0')
            owed = earned - avans_sum
            if owed > 0:
                results.append({
                    'user': user, 'yil': m_yil, 'oy': m_oy, 'owed': owed,
                })
    results.sort(key=lambda r: (r['yil'], r['oy']))
    return results
