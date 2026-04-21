import calendar
from decimal import Decimal

from django.utils import timezone

from .models import NasiyaTolov


CREDIT_TERM_MARKUPS = {
    3: Decimal('10'),
    6: Decimal('15'),
    9: Decimal('20'),
    12: Decimal('30'),
}


def add_months(date_value, months):
    month = date_value.month - 1 + months
    year = date_value.year + month // 12
    month = month % 12 + 1
    day = min(date_value.day, calendar.monthrange(year, month)[1])
    return date_value.replace(year=year, month=month, day=day)


def build_credit_terms(base_amount, months, company, customer=None):
    months = int(months or 3)
    if months not in CREDIT_TERM_MARKUPS:
        months = 3

    base = Decimal(str(base_amount or 0))
    markup_percent = CREDIT_TERM_MARKUPS[months]
    markup_amount = (base * markup_percent / Decimal('100')).quantize(Decimal('0.01'))
    total = base + markup_amount
    start_date = timezone.localdate()
    due_date = add_months(start_date, months)

    template = company.credit_contract_template or ''
    contract_text = (
        template
        .replace('{{ company }}', company.name or '')
        .replace('{{ customer }}', customer or '')
        .replace('{{ months }}', str(months))
        .replace('{{ base }}', f"{base:,.0f}")
        .replace('{{ markup_percent }}', f"{markup_percent:,.0f}")
        .replace('{{ markup }}', f"{markup_amount:,.0f}")
        .replace('{{ total }}', f"{total:,.0f}")
        .replace('{{ due_date }}', due_date.isoformat())
    )

    return {
        'months': months,
        'markup_percent': float(markup_percent),
        'markup_amount': float(markup_amount),
        'total': float(total),
        'due_date': due_date,
        'contract_text': contract_text,
    }


def credit_payment_summary(savdo):
    payments = NasiyaTolov.objects.filter(savdo=savdo).order_by('-tolov_sanasi')
    total_paid = sum(Decimal(str(p.tolov_summasi or 0)) for p in payments)
    total_due = Decimal(str(savdo.summa or 0))
    months = int(savdo.credit_term_months or 0)
    today = timezone.localdate()

    result = {
        'payments': payments,
        'total_payments': float(total_paid),
        'remaining': float(max(total_due - total_paid, Decimal('0'))),
        'is_fully_paid': total_paid >= total_due and total_due > 0,
        'status_label': "Oddiy nasiya",
        'status_type': "neutral",
        'expected_paid': 0,
        'overdue_amount': 0,
        'late_penalty': 0,
        'early_discount_hint': 0,
        'final_due_date': savdo.credit_due_date,
        'days_to_due': None,
    }

    if not months or not savdo.vaqt_sana:
        return result

    sale_date = timezone.localtime(savdo.vaqt_sana).date()
    monthly_due = total_due / Decimal(str(months))
    due_count = 0
    for index in range(1, months + 1):
        if add_months(sale_date, index) <= today:
            due_count += 1

    expected_paid = (monthly_due * Decimal(str(due_count))).quantize(Decimal('0.01'))
    overdue_amount = max(expected_paid - total_paid, Decimal('0'))
    final_due_date = savdo.credit_due_date or add_months(sale_date, months)
    days_to_due = (final_due_date - today).days

    late_penalty_percent = Decimal(str(getattr(savdo.company, 'credit_late_penalty_percent', 0) or 0))
    early_discount_percent = Decimal(str(getattr(savdo.company, 'credit_early_discount_percent', 0) or 0))
    late_penalty = (overdue_amount * late_penalty_percent / Decimal('100')).quantize(Decimal('0.01'))
    remaining = max(total_due + late_penalty - total_paid, Decimal('0'))
    early_discount_hint = (remaining * early_discount_percent / Decimal('100')).quantize(Decimal('0.01'))

    if total_paid >= total_due and days_to_due is not None and days_to_due > 0:
        status_label = "Oldindan yopildi"
        status_type = "early"
    elif total_paid >= total_due:
        status_label = "Yopilgan"
        status_type = "paid"
    elif overdue_amount > 0:
        status_label = "Kechikkan"
        status_type = "late"
    elif total_paid > expected_paid and days_to_due is not None and days_to_due > 0:
        status_label = "Oldindan to'lanmoqda"
        status_type = "early"
    else:
        status_label = "O'z vaqtida"
        status_type = "ontime"

    result.update({
        'total_payments': float(total_paid),
        'remaining': float(remaining),
        'is_fully_paid': remaining <= 0,
        'status_label': status_label,
        'status_type': status_type,
        'expected_paid': float(expected_paid),
        'overdue_amount': float(overdue_amount),
        'late_penalty': float(late_penalty),
        'early_discount_hint': float(early_discount_hint),
        'final_due_date': final_due_date,
        'days_to_due': days_to_due,
    })
    return result
