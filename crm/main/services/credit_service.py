import math
from datetime import timedelta

from django.utils import timezone


CREDIT_MARKUP_BY_MONTHS = {
    3: 10,
    6: 15,
    9: 20,
    12: 30,
}

SYSTEM_CREDIT_RULES = (
    "Tizim qoidasi: nasiya yopilish muddati bo'yicha qayta hisoblanadi. "
    "3 oy uchun 10%, 6 oy uchun 15%, 9 oy uchun 20%, 12 oy uchun 30% ustama qo'llanadi. "
    "Muddatidan oldin yopilsa yakuniy summa kamayadi, kech yopilsa keyingi muddat ustamasi bo'yicha oshadi. "
    "Ushbu tizim qoidasi shartnomadan olib tashlanmaydi."
)

DEFAULT_SAVDOGAR_CONTRACT_TEMPLATE = """SAVDOGAR NASIYA SAVDO SHARTNOMASI

Tomonlar va rozilik
Firma nomidan vakolatli savdogar xaridorga mahsulotlarni nasiya savdo tartibida topshiradi. Xaridor mahsulotlarni qabul qilganini, shartnoma shartlari bilan tanishganini va to'lov majburiyatini olganini tasdiqlaydi.

Savdo predmeti
Shartnoma doirasida xaridorga topshirilgan mahsulotlar, ularning soni, narxi va yakuniy qiymati elektron shartnoma ilovasida hamda savdo hujjatlarida ko'rsatiladi.

To'lov majburiyati
Xaridor nasiya savdo bo'yicha belgilangan to'lovlarni kelishilgan muddatlarda amalga oshiradi. To'lovlar kechiktirilganda yoki muddatidan oldin yopilganda yakuniy hisob-kitob tizim qoidalari asosida qayta ko'rib chiqiladi.

Hujjatlar va tasdiqlash
Savdo rasmiylashtirilganda elektron PDF shartnoma saqlanadi. Xaridor shartnomani imzolaganidan so'ng imzolangan nusxa skanerlanib tizimga biriktiriladi. Xaridorning ID karta yoki pasport nusxasi ham shartnoma hujjatlariga qo'shiladi.

Firma qo'shimcha shartlari
Firma ushbu bo'limda kafolat, qaytarish, aloqa, jarima, yetkazish, xizmat ko'rsatish yoki ichki tartib bo'yicha qo'shimcha shartlarni belgilashi mumkin."""


def allowed_credit_terms():
    return CREDIT_MARKUP_BY_MONTHS.items()


def get_markup_for_months(months):
    months = int(months or 0)
    if months not in CREDIT_MARKUP_BY_MONTHS:
        raise ValueError("Nasiya muddati faqat 3, 6, 9 yoki 12 oy bo'lishi mumkin.")
    return CREDIT_MARKUP_BY_MONTHS[months]


def get_effective_credit_months(sale, now=None):
    now = now or timezone.now()
    elapsed_days = max((now.date() - sale.vaqt_sana.date()).days, 0)
    elapsed_months = max(1, math.ceil(elapsed_days / 30))

    for months in sorted(CREDIT_MARKUP_BY_MONTHS):
        if elapsed_months <= months:
            return months
    return 12


def calculate_credit_total(base_summa, months):
    markup = get_markup_for_months(months)
    base = float(base_summa or 0)
    return round(base * (1 + markup / 100), 2), markup


def calculate_current_payoff_total(sale, now=None):
    """
    Returns (total, markup_percent, effective_months).
    Between bracket boundaries, markup is interpolated linearly so there is no
    cliff — e.g. paying 1 day past the 3-month mark adds only ~0.06% instead
    of jumping straight to 15%.
    """
    if not sale.base_summa:
        return float(sale.summa or 0), float(sale.credit_markup_percent or 0), sale.credit_term_months

    now = now or timezone.now()
    elapsed_days = max((now.date() - sale.vaqt_sana.date()).days, 0)

    brackets = sorted(CREDIT_MARKUP_BY_MONTHS.items())  # [(3,10),(6,15),(9,20),(12,30)]
    first_months, first_markup = brackets[0]

    if elapsed_days <= first_months * 30:
        markup = float(first_markup)
        effective_months = first_months
    else:
        # Default: past all brackets
        markup = float(brackets[-1][1])
        effective_months = brackets[-1][0]
        for i in range(1, len(brackets)):
            prev_months, prev_markup = brackets[i - 1]
            curr_months, curr_markup = brackets[i]
            prev_days = prev_months * 30
            curr_days = curr_months * 30
            if elapsed_days <= curr_days:
                progress = (elapsed_days - prev_days) / (curr_days - prev_days)
                markup = float(prev_markup) + (float(curr_markup) - float(prev_markup)) * progress
                effective_months = curr_months
                break

    base = float(sale.base_summa or 0)
    markup = round(markup, 2)
    total = round(base * (1 + markup / 100), 2)
    return total, markup, effective_months


def _format_money(value):
    return f"{float(value or 0):,.0f}".replace(",", " ")


def _contract_sale_details(payment_type=None, items=None, base_summa=0, total=0, months=None, markup=0, down_payment=0):
    labels = {
        "naqd": "Naqd",
        "karta": "Karta",
        "nasiya": "Nasiya",
    }
    lines = ["Savdo ma'lumotlari"]
    if payment_type:
        lines.append(f"To'lov turi: {labels.get(payment_type, payment_type)}")
    if items:
        lines.append("Olingan mahsulotlar:")
        for item in items:
            name = item.get("name") or item.get("nom") or "Mahsulot"
            qty = float(item.get("qty") or item.get("miqdor") or 0)
            unit = item.get("unit") or ""
            price = float(item.get("price") or item.get("narx") or 0)
            line_total = qty * price
            lines.append(f"- {name}: {qty:g} {unit} x {_format_money(price)} so'm = {_format_money(line_total)} so'm")
    lines.append(f"Asosiy summa: {_format_money(base_summa)} so'm")
    if payment_type == "nasiya":
        lines.append(f"Nasiya muddati: {months} oy")
        lines.append(f"Ustama: {markup:g}%")
        lines.append(f"Yakuniy nasiya summa: {_format_money(total)} so'm")
        lines.append(f"Boshlang'ich to'lov: {_format_money(down_payment)} so'm")
        lines.append(f"Qoldiq: {_format_money(max(float(total or 0) - float(down_payment or 0), 0))} so'm")
    else:
        lines.append(f"Yakuniy summa: {_format_money(total or base_summa)} so'm")
    return "\n".join(lines)


def build_credit_contract(company, customer, base_summa, total, months, markup, contract_number=None, items=None, payment_type="nasiya", down_payment=0):
    template = (company.credit_contract_template or "").strip()
    custom = (company.savdogar_contract_text or DEFAULT_SAVDOGAR_CONTRACT_TEMPLATE).strip()
    rules = (company.credit_rules_note or "").strip()
    replacements = {
        "{{ company }}": company.name,
        "{{ customer }}": customer,
        "{{ months }}": str(months),
        "{{ total }}": _format_money(total),
        "{{ base_total }}": _format_money(base_summa),
        "{{ markup }}": str(markup),
    }

    text = template
    for key, value in replacements.items():
        text = text.replace(key, value)
        custom = custom.replace(key, value)

    intro = (
        f"Shartnoma N: {contract_number or company.savdogar_contract_next_number}\n"
        f"Firma: {company.name}\n"
        f"Xaridor: {customer}\n"
        f"Sana: {timezone.localdate().strftime('%d.%m.%Y')}"
    )
    sale_details = _contract_sale_details(payment_type, items, base_summa, total, months, markup, down_payment)
    parts = [part for part in [intro, custom, sale_details, text, rules, SYSTEM_CREDIT_RULES] if part]
    return "\n\n".join(parts)


def build_contract_draft(company, customer, contract_number=None, payment_type=None, items=None, base_summa=0, total=0, months=None, markup=0, down_payment=0):
    custom = (company.savdogar_contract_text or DEFAULT_SAVDOGAR_CONTRACT_TEMPLATE).strip()
    rules = (company.credit_rules_note or "").strip()
    replacements = {
        "{{ company }}": company.name,
        "{{ customer }}": customer,
    }

    text = custom
    for key, value in replacements.items():
        text = text.replace(key, value)
    if payment_type and payment_type != "nasiya":
        text = text.replace("SAVDOGAR NASIYA SAVDO SHARTNOMASI", "SAVDOGAR SAVDO SHARTNOMASI")
        text = text.replace("nasiya savdo tartibida", "savdo tartibida")

    intro = (
        f"Shartnoma N: {contract_number or company.savdogar_contract_next_number}\n"
        f"Firma: {company.name}\n"
        f"Xaridor: {customer}\n"
        f"Sana: {timezone.localdate().strftime('%d.%m.%Y')}"
    )
    sale_details = _contract_sale_details(payment_type, items, base_summa, total, months, markup, down_payment)
    parts = [part for part in [intro, text, sale_details, rules, SYSTEM_CREDIT_RULES] if part]
    return "\n\n".join(parts)


def credit_due_date(months, start=None):
    start = start or timezone.localdate()
    return start + timedelta(days=int(months) * 30)
