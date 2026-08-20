import datetime as dt
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import QoshimchaChiqim, Savdo, NasiyaTolov, XodimTolov, User
from .services import payroll_service
from .services.stock_service import effective_ish_haqi_turi


def _ega_guard(request):
    return request.user.type == 'ega'


@login_required(login_url='login')
def qoshimcha_chiqimlar_page(request):
    if not _ega_guard(request):
        return redirect('main')

    if request.method == 'POST':
        nomi = (request.POST.get('nomi') or '').strip()
        try:
            summa = float(request.POST.get('summa') or 0)
        except ValueError:
            summa = 0
        sana = request.POST.get('sana') or None
        izoh = (request.POST.get('izoh') or '').strip()

        if not nomi:
            messages.error(request, "Chiqim nomi kiritilishi shart.")
        elif summa <= 0:
            messages.error(request, "Summa 0 dan katta bo'lishi kerak.")
        else:
            chiqim = QoshimchaChiqim(
                company=request.company, nomi=nomi, summa=summa, izoh=izoh,
                created_by=request.user,
            )
            if sana:
                chiqim.sana = sana
            chiqim.save()
            messages.success(request, "Chiqim qo'shildi.")
        return redirect('qoshimcha_chiqimlar')

    chiqimlar = QoshimchaChiqim.objects.filter(company=request.company).select_related('created_by')
    jami = sum(float(c.summa) for c in chiqimlar)
    return render(request, 'qoshimcha_chiqimlar.html', {
        'chiqimlar': chiqimlar,
        'jami': jami,
    })


@login_required(login_url='login')
def moliya_dashboard(request):
    """Moliya dashboardi — tushum, xomashyo xarajati (COGS), naqd pul
    aylanma, ish haqi, qo'shimcha xarajatlar, sof foyda va marja %.

    "Ish haqi" bu yerda KASSA asosida hisoblanadi — `XodimTolov` orqali
    HAQIQATDA berilgan summalar yig'indisi, hisoblangan-lekin-berilmagan
    (accrual) emas — chunki oy yopish cronsiz, faqat qo'lda ishlaydi.
    """
    if not _ega_guard(request):
        return redirect('main')

    company = request.company
    now = timezone.localtime()

    from_date_str = request.GET.get('from')
    to_date_str = request.GET.get('to')
    try:
        from_date = dt.date.fromisoformat(from_date_str) if from_date_str else now.date().replace(day=1)
        to_date = dt.date.fromisoformat(to_date_str) if to_date_str else now.date()
    except ValueError:
        from_date = now.date().replace(day=1)
        to_date = now.date()

    from_dt = timezone.make_aware(dt.datetime.combine(from_date, dt.time.min))
    to_dt = timezone.make_aware(dt.datetime.combine(to_date, dt.time.max))

    savdolar = Savdo.objects.filter(company=company, vaqt_sana__range=(from_dt, to_dt))
    savdo_totals = savdolar.aggregate(revenue=Sum('summa'), base=Sum('base_summa'), foyda=Sum('foyda'))
    revenue = savdo_totals['revenue'] or 0
    cogs = (savdo_totals['base'] or 0) - (savdo_totals['foyda'] or 0)

    cash_from_sales = savdolar.filter(st__in=['naqd', 'karta']).aggregate(t=Sum('summa'))['t'] or 0
    nasiya_tolovlar = NasiyaTolov.objects.filter(
        company=company, tolov_sanasi__range=(from_dt, to_dt),
    ).aggregate(t=Sum('tolov_summasi'))['t'] or 0
    cash_turnover = cash_from_sales + nasiya_tolovlar

    # Fiks maoshli xodimlarga to'langan summalar bu yerdan chiqarib
    # tashlanadi — ularning foydaga ta'siri pastdagi `fixed_variance_total`
    # orqali (rejalashtirilgan-haqiqiy farq sifatida) hisobga olinadi,
    # aks holda oyligi HAM shu yerda, HAM tannarx ichida (ishlab_chiqarish_narxi/
    # sotuv_ish_haqi_narxi orqali) ikki marta ayirilib, foyda noto'g'ri
    # kamayib ko'rsatilardi.
    company_users = list(User.objects.filter(company=company).exclude(type__in=['ega', 'desktop_agent']))
    fixed_user_ids = {u.id for u in company_users if effective_ish_haqi_turi(u, company) == 'fixed'}
    wages_paid = XodimTolov.objects.filter(
        company=company, sana__range=(from_date, to_date),
    ).exclude(user_id__in=fixed_user_ids).aggregate(t=Sum('summa'))['t'] or 0
    qoshimcha_summa = QoshimchaChiqim.objects.filter(
        company=company, sana__range=(from_date, to_date),
    ).aggregate(t=Sum('summa'))['t'] or 0

    # Fiks xodimlar bo'yicha rejalashtirilgan-haqiqiy farq — joriy oy
    # uchun (sana oralig'idan mustaqil, xuddi `umumiy_ish_haqi` kabi).
    fixed_variance_total = sum(
        (payroll_service.compute_fixed_worker_variance(u, company)['farq']
         for u in company_users if effective_ish_haqi_turi(u, company) == 'fixed'),
        Decimal('0'),
    )

    net_profit = revenue - cogs - float(wages_paid) - float(qoshimcha_summa) + float(fixed_variance_total)
    margin_percent = (net_profit / revenue * 100) if revenue else 0

    # Joriy oy ish haqi — sana filtridan MUSTAQIL, doim joriy oy uchun
    # (asosiy sana-oralig'i KPI panjarasidan chetlashtirilgan, alohida
    # o'zgarmas blok sifatida ko'rsatiladi).
    umumiy_ish_haqi = sum(
        (payroll_service.compute_oylik_ish_haqi(u, company)['summa']
         for u in User.objects.filter(company=company).exclude(type__in=['ega', 'desktop_agent'])),
        Decimal('0'),
    )
    tolangan_ish_haqi_joriy_oy = XodimTolov.objects.filter(
        company=company, sana__year=now.year, sana__month=now.month,
    ).aggregate(t=Sum('summa'))['t'] or Decimal('0')

    # O'tgan oylardan yopilmagan (unutilgan) qoldiq to'lovlar — xodim
    # profiliga havola bilan, ega diqqatini tortish uchun.
    outstanding_months = payroll_service.get_outstanding_previous_months(company)
    outstanding_total = sum((row['owed'] for row in outstanding_months), Decimal('0'))

    if request.GET.get('export') == 'xlsx':
        import pandas as pd
        from .utils import export_to_excel

        df = pd.DataFrame([
            {"Ko'rsatkich": 'Umumiy tushum', 'Summa': float(revenue)},
            {"Ko'rsatkich": 'Xomashyo xarajati (COGS)', 'Summa': float(cogs)},
            {"Ko'rsatkich": 'Naqd pul aylanma', 'Summa': float(cash_turnover)},
            {"Ko'rsatkich": "Ish haqi (to'langan, tanlangan davr)", 'Summa': float(wages_paid)},
            {"Ko'rsatkich": "Qo'shimcha xarajatlar", 'Summa': float(qoshimcha_summa)},
            {"Ko'rsatkich": 'Sof foyda', 'Summa': float(net_profit)},
            {"Ko'rsatkich": 'Marja (%)', 'Summa': round(float(margin_percent), 2)},
            {"Ko'rsatkich": "Joriy oy — umumiy ish haqqi (hisoblangan)", 'Summa': float(umumiy_ish_haqi)},
            {"Ko'rsatkich": "Joriy oy — to'langan ish haqqi", 'Summa': float(tolangan_ish_haqi_joriy_oy)},
            {"Ko'rsatkich": "Joriy oy — fiks xodimlar rejalashtirilgan-haqiqiy farqi", 'Summa': float(fixed_variance_total)},
        ])
        header_info = {
            'title': f"Moliya hisoboti - {company.name}",
            'date_range': f"{from_date} dan {to_date} gacha",
        }
        filename = f"moliya_{from_date}_{to_date}.xlsx"
        return export_to_excel(df, filename, header_info)

    context = {
        'from_date': from_date.isoformat(),
        'to_date': to_date.isoformat(),
        'revenue': revenue,
        'cogs': cogs,
        'cash_turnover': cash_turnover,
        'qoshimcha': qoshimcha_summa,
        'net_profit': net_profit,
        'margin_percent': margin_percent,
        'umumiy_ish_haqi': umumiy_ish_haqi,
        'tolangan_ish_haqi_joriy_oy': tolangan_ish_haqi_joriy_oy,
        'fixed_variance_total': fixed_variance_total,
        'joriy_oy_nomi': now.strftime('%Y-%m'),
        'outstanding_months': outstanding_months,
        'outstanding_total': outstanding_total,
    }
    return render(request, 'moliya_dashboard.html', context)
