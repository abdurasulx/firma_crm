import datetime as dt
from decimal import Decimal

OY_NOMLARI = [
    '', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
    'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr',
]

from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.utils import timezone

from ..models import User, Pazanda, Savdo, YetkazibBeruvchi, XodimMaosh, XodimTolov, XodimOyYopish
from .stock_service import get_pazanda_month_stats, effective_ish_haqi_turi


def get_month_bounds(yil, oy):
    month_start = timezone.make_aware(dt.datetime(yil, oy, 1))
    if oy == 12:
        month_end = timezone.make_aware(dt.datetime(yil + 1, 1, 1))
    else:
        month_end = timezone.make_aware(dt.datetime(yil, oy + 1, 1))
    return month_start, month_end


def _month_savdolar_for_user(user, company, yil, oy):
    """Savdogar/yetkazib beruvchi shu oyda amalga oshirgan (yaratgan)
    savdolari. `Savdo.savdogar` — `User`ga to'g'ridan-to'g'ri FK, lekin
    `Savdo.yetkazib_beruvchi` — `YetkazibBeruvchi`ga FK (`User`ga emas),
    shuning uchun avval shu profilni topish kerak."""
    month_start, month_end = get_month_bounds(yil, oy)
    if user.type == 'yetkazib_beruvchi':
        yb = YetkazibBeruvchi.objects.filter(user=user, company=company).first()
        if not yb:
            return Savdo.objects.none()
        return Savdo.objects.filter(
            yetkazib_beruvchi=yb, company=company, vaqt_sana__gte=month_start, vaqt_sana__lt=month_end,
        )
    return Savdo.objects.filter(
        savdogar=user, company=company, vaqt_sana__gte=month_start, vaqt_sana__lt=month_end,
    )


def compute_oylik_ish_haqi(user, company, yil=None, oy=None):
    """Xodimning shu oy uchun "ishlab topgan" summasini hisoblaydi.

    Firma `ish_haqi_turi == 'per_unit'` bo'lsa va xodimga bog'langan
    `Pazanda` profili mavjud bo'lsa — `MiqdorQoshish.ish_haqi_summasi`
    yig'indisidan (jarima allaqachon ichida ayirilgan) hisoblanadi.
    `per_sale` bo'lsa (faqat savdogar/yetkazib_beruvchi uchun ma'noli) —
    shu oydagi savdolaridagi `Savdo.ish_haqi_summasi` yig'indisidan
    (mahsulotning `sotuv_ish_haqi_narxi`si asosida hisoblangan).
    Aks holda — `XodimMaosh.oylik_maosh` (belgilanmagan bo'lsa 0).

    Bazaviy summaga qo'shimcha, ega firma sozlamalarida belgilagan `KpiQoida`
    bonuslari (chegaraga yetsa) HAR DOIM qo'shiladi — ish haqi turidan
    qat'i nazar (bu alohida rag'batlantirish, asosiy to'lov turini
    almashtirmaydi).
    """
    now = timezone.localtime()
    if yil is None or oy is None:
        yil, oy = now.year, now.month

    turi = effective_ish_haqi_turi(user, company)
    base = None

    if turi == 'per_unit':
        pazanda = Pazanda.objects.filter(user=user, company=company).first()
        if pazanda:
            stats = get_pazanda_month_stats(pazanda, company, yil=yil, oy=oy)
            base = {'summa': Decimal(str(stats['earnings'])), 'manba': 'per_unit'}

    if base is None and turi == 'per_sale' and user.type in ('savdogar', 'yetkazib_beruvchi'):
        # Mahsulotning o'z sahifasida belgilangan `sotuv_ish_haqi_narxi`
        # asosida — har bir savdoda hisoblanib `Savdo.ish_haqi_summasi`ga
        # yozib qo'yilgan yig'indi (production'dagi `per_unit`ga o'xshab).
        summa = _month_savdolar_for_user(user, company, yil, oy).aggregate(
            t=Sum('ish_haqi_summasi'),
        )['t'] or Decimal('0')
        base = {'summa': Decimal(str(summa)), 'manba': 'per_sale'}

    if base is None:
        maosh = XodimMaosh.objects.filter(user=user, company=company).first()
        base = {'summa': maosh.oylik_maosh if maosh else Decimal('0'), 'manba': 'fixed'}

    from .kpi_service import compute_kpi_bonus
    kpi_bonus = compute_kpi_bonus(user, company, yil=yil, oy=oy)['bonus_summasi']
    base['summa'] = base['summa'] + kpi_bonus
    base['kpi_bonus'] = kpi_bonus
    return base


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


def pay_outstanding_month(user, company, yil, oy, summa, rasm, paid_by, izoh=''):
    """O'tgan (qolib ketgan) oy uchun to'lov — **to'liq shart emas, qisman
    ham bo'lishi mumkin**. Chek/kvitansiya rasmi majburiy (bu funksiyaga
    kirguncha view'da tekshiriladi, lekin xavfsizlik uchun shu yerda ham
    qat'iy talab qilinadi).

    To'lov shu oyning ICHIDAGI sana bilan (oy oxiri) yoziladi — shunda
    keyingi hisob-kitoblarda (`get_month_summary`/`get_user_outstanding_months`)
    aynan shu oyning avansi sifatida hisobga olinadi, joriy oyga emas.

    Agar shu to'lovdan keyin qoldiq 0 yoki undan kam qolsa — oy avtomatik
    yopiladi (`close_month`), aks holda oy "ochiq" holida qoladi va
    keyinroq yana qisman to'lov qilish mumkin."""
    if not rasm:
        raise ValueError("To'lov cheki rasmi majburiy.")
    summa = Decimal(str(summa))
    if summa <= 0:
        raise ValueError("Summa 0 dan katta bo'lishi kerak.")

    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        if is_month_closed(user, yil, oy):
            raise ValueError("Bu oy allaqachon yopilgan.")

        earned = compute_oylik_ish_haqi(user, company, yil=yil, oy=oy)['summa']
        avans_sum = XodimTolov.objects.filter(
            user=user, company=company, turi='avans', sana__year=yil, sana__month=oy,
        ).aggregate(t=Sum('summa'))['t'] or Decimal('0')
        owed = earned - avans_sum
        if summa > owed:
            raise ValueError(
                f"To'lov summasi qolgan qarzdan ({owed:,.0f} so'm) katta bo'lishi mumkin emas.",
            )

        _, oy_end = get_month_bounds(yil, oy)
        tolov_sanasi = (oy_end - dt.timedelta(days=1)).date()

        tolov = XodimTolov.objects.create(
            user=user, company=company, turi='avans', summa=summa, sana=tolov_sanasi,
            rasm=rasm, berdi=paid_by, izoh=izoh,
        )

        yangi_qoldiq = owed - summa
        yopildi = False
        if yangi_qoldiq <= 0:
            close_month(user, company, paid_by, yil=yil, oy=oy)
            yopildi = True

        return {'tolov': tolov, 'yopildi': yopildi, 'qolgan_qarz': max(yangi_qoldiq, Decimal('0'))}


def get_user_outstanding_months(user, company, lookback_months=12):
    """`get_outstanding_previous_months`ning bitta xodim uchun tor varianti
    — xodim profilida ("qolib ketgan oylik") ko'rsatish uchun, butun
    firma bo'yicha aylanish shart emas."""
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
                'yil': m_yil, 'oy': m_oy, 'owed': owed,
                'label': f"{OY_NOMLARI[m_oy]} {m_yil}",
            })
    results.sort(key=lambda r: (r['yil'], r['oy']))
    return results


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
