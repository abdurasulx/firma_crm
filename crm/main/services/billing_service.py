from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, time, timedelta
from uuid import uuid4

from dateutil.relativedelta import relativedelta

import requests
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from ..models import BillingPaymentLink, Company, PlanRequest
from ..plan_utils import get_plan_duration_months


def lifecycle_cache_key(company_id):
    return f'company_lifecycle:{company_id}'


def invalidate_lifecycle_cache(company):
    """Firmaning to'lov/holat maydonlari (`is_active`, `payment_status`,
    `next_payment_date`, `setup_mode`, `is_on_trial` va h.k.) qo'lda —
    admin panel orqali — o'zgartirilgan har bir joyda chaqirilishi kerak.

    Sabab (real production bug): `CompanyMiddleware` `sync_company_
    lifecycle()` natijasini 5 daqiqaga keshlaydi (`LIFECYCLE_SYNC_CACHE_
    SECONDS`). Admin firmani "to'landi" deb belgilasa-yu, shu keshni
    bekor qilmasa — tashrifchilar hali eski (masalan "to'xtatilgan")
    holatni ko'raveradi, DB'da allaqachon to'g'irlangan bo'lsa ham, toki
    5 daqiqa TTL o'z-o'zidan tugamaguncha."""
    cache.delete(lifecycle_cache_key(company.id))


def get_company_host(company, base_domain):
    base_domain = (base_domain or "localhost:8000").strip()
    return f"{company.subdomain}.{base_domain}"


def get_company_login_url(company, base_domain):
    host = get_company_host(company, base_domain)
    scheme = "http" if any(part in base_domain for part in ("localhost", "127.0.0.1", "lvh.me")) else "https"
    return f"{scheme}://{host}/login/"


def get_company_dashboard_url(company, base_domain):
    return get_company_login_url(company, base_domain).replace("/login/", "/")


def get_usd_rate():
    rate = cache.get("usd_rate")
    if rate:
        return rate

    try:
        response = requests.get("https://cbu.uz/uz/arkhiv-kursov-valyut/json/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                if item["Ccy"] == "USD":
                    rate = Decimal(str(item["Rate"]))
                    cache.set("usd_rate", rate, 3600 * 12)
                    return rate
    except Exception:
        pass

    return Decimal("12500.0")


def get_company_monthly_price(company):
    return Decimal(company.monthly_price or 0)


def get_plan_request_monthly_price(plan_request):
    if not plan_request or plan_request.is_trial:
        return Decimal("0.00")
    if plan_request.is_custom:
        return Decimal(plan_request.custom_price or 0)
    if plan_request.plan:
        return Decimal(plan_request.plan.price or 0)
    return Decimal("0.00")


def get_current_period_start(company, paid_until=None, now=None):
    now = now or timezone.now()
    base_links = company.billing_payment_links.exclude(reason__startswith="Tarif farqi:")
    latest_paid_link = base_links.filter(status="paid").order_by("-paid_at", "-created_at").first()
    if latest_paid_link:
        return latest_paid_link.paid_at or latest_paid_link.opened_at or latest_paid_link.created_at

    latest_link = base_links.order_by("-created_at").first()
    if latest_link and company.payment_status == "paid":
        return latest_link.opened_at or latest_link.created_at or timezone.make_aware(
            datetime.combine(latest_link.billing_period_start, time.min)
        )
    if paid_until and paid_until > now:
        return paid_until - timedelta(days=30)
    return now


def calculate_prorated_amount(monthly_difference, period_start, period_stop, now=None):
    now = now or timezone.now()
    monthly_difference = Decimal(monthly_difference or 0)
    if monthly_difference <= 0 or not period_start or not period_stop or period_stop <= now:
        return Decimal("0.00")

    total_seconds = Decimal(str(max((period_stop - period_start).total_seconds(), 1)))
    remaining_seconds = Decimal(str(max((period_stop - now).total_seconds(), 0)))
    return (monthly_difference * remaining_seconds / total_seconds).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_prorated_billing(company, now=None):
    now = now or timezone.now()
    paid_until = company.next_payment_date
    if company.payment_status != "paid" or not paid_until or paid_until <= now:
        return {"amount": Decimal("0.00"), "reason": ""}

    latest_request = (
        PlanRequest.objects.filter(company=company, status="approved", reviewed_at__isnull=False, is_trial=False)
        .order_by("-reviewed_at")
        .first()
    )
    if not latest_request:
        return {"amount": Decimal("0.00"), "reason": ""}

    period_start = get_current_period_start(company, paid_until=paid_until, now=now)
    if latest_request.reviewed_at <= period_start:
        return {"amount": Decimal("0.00"), "reason": ""}

    already_paid = company.billing_payment_links.filter(
        status="paid",
        created_at__gte=latest_request.reviewed_at,
        reason__startswith="Tarif farqi:",
    ).exists()
    if already_paid:
        return {"amount": Decimal("0.00"), "reason": ""}

    previous_request = (
        PlanRequest.objects.filter(
            company=company,
            status="approved",
            reviewed_at__isnull=False,
            reviewed_at__lt=latest_request.reviewed_at,
            is_trial=False,
        )
        .order_by("-reviewed_at")
        .first()
    )
    if previous_request:
        old_monthly_price = get_plan_request_monthly_price(previous_request)
    elif latest_request.is_custom and latest_request.plan:
        old_monthly_price = Decimal(latest_request.plan.price or 0)
    else:
        old_monthly_price = Decimal("0.00")
    new_monthly_price = get_company_monthly_price(company)
    prorated_amount = calculate_prorated_amount(
        new_monthly_price - old_monthly_price,
        period_start,
        paid_until,
        now=now,
    )
    if prorated_amount <= 0:
        return {"amount": Decimal("0.00"), "reason": ""}

    return {
        "amount": prorated_amount,
        "reason": (
            f"Tarif farqi: ${old_monthly_price:.2f} dan ${new_monthly_price:.2f} gacha, "
            f"{timezone.localtime(now).strftime('%d.%m.%Y')} - "
            f"{timezone.localtime(paid_until).strftime('%d.%m.%Y')} uchun"
        ),
    }


def get_company_pending_billing_amount(company):
    return get_prorated_billing(company)["amount"]


def get_company_payment_due_amount(company):
    pending_amount = get_company_pending_billing_amount(company)
    if pending_amount > 0:
        return pending_amount
    return get_company_monthly_price(company)


def is_company_on_free_plan(company):
    return get_company_monthly_price(company) <= 0


def get_tariff_started_at(company):
    if not company:
        return None
    latest_request = (
        PlanRequest.objects.filter(company=company, status="approved", reviewed_at__isnull=False)
        .order_by("-reviewed_at")
        .first()
    )
    if latest_request:
        return latest_request.reviewed_at
    return company.created_at


def get_billing_period_start(company=None, now=None):
    now = now or timezone.localtime()
    tariff_started_at = get_tariff_started_at(company)
    if tariff_started_at:
        return timezone.localtime(tariff_started_at).date()
    return date(now.year, now.month, 1)


def get_billing_reason(company, now=None):
    now = now or timezone.localtime()
    prorated_billing = get_prorated_billing(company, now=now)
    if prorated_billing["amount"] > 0:
        return prorated_billing["reason"]
    tariff_started_at = get_tariff_started_at(company)
    if tariff_started_at:
        return f"{timezone.localtime(tariff_started_at).strftime('%d.%m.%Y')} dan boshlangan tarif uchun oylik abonent to'lovi"
    return f"{now.strftime('%B %Y')} uchun oylik abonent to'lovi"


def is_company_billing_current(company, now=None):
    if is_company_on_free_plan(company):
        return True
    if get_company_pending_billing_amount(company) > 0:
        return False
    now = now or timezone.now()
    return bool(company.payment_status == "paid" and company.next_payment_date and company.next_payment_date > now)


def get_latest_payment_link(company):
    return company.billing_payment_links.order_by("-created_at").first()


def get_latest_unopened_payment_link(company):
    return company.billing_payment_links.filter(status="created").order_by("-created_at").first()


def build_click_payment_url(service_id, merchant_id, amount_uzs, payment_link_id):
    amount_uzs = Decimal(amount_uzs).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return (
        "https://my.click.uz/services/pay"
        f"?service_id={service_id}&merchant_id={merchant_id}&amount={int(amount_uzs)}"
        f"&transaction_param={payment_link_id}"
    )


def sync_company_lifecycle(company, now=None, save=True):
    now = now or timezone.now()
    changed = False
    payment_reason = None

    if company.setup_mode:
        setup_deadline = company.setup_expires_at or (company.created_at + timedelta(days=7))
        if now > setup_deadline:
            company.setup_mode = False
            company.setup_expires_at = None
            changed = True

    if company.is_on_trial and company.trial_expires_at and now > company.trial_expires_at:
        company.is_on_trial = False
        company.trial_expires_at = None
        if not company.plan and not company.is_custom_plan:
            company.is_active = False
        changed = True

    if is_company_on_free_plan(company):
        if company.payment_status != "paid" or company.next_payment_date is not None:
            company.payment_status = "paid"
            company.next_payment_date = None
            changed = True
    else:
        # To'lov muddati (`next_payment_date`) o'tib ketgan bo'lsa, firma
        # "to'lanmagan" holatga o'tkaziladi — bu holat pastdagi 3 kunlik
        # muhlat tekshiruvi uchun zarur. Bu qadamsiz `payment_status`
        # "paid" bo'lib qolaverardi va tizim hech qachon qulflanmasdi
        # (real bug — 2026-07-21 kuni aniqlandi).
        if company.payment_status == "paid" and company.next_payment_date and now > company.next_payment_date:
            company.payment_status = "unpaid"
            changed = True

        if company.payment_status == "unpaid" and company.next_payment_date:
            if now > company.next_payment_date + timedelta(days=3):
                payment_reason = "payment_overdue"

    if save and changed:
        company.save(
            update_fields=[
                "setup_mode",
                "setup_expires_at",
                "is_on_trial",
                "trial_expires_at",
                "is_active",
                "payment_status",
                "next_payment_date",
            ]
        )

    return {
        "changed": changed,
        "payment_reason": payment_reason,
        "is_active": company.is_active,
    }


@transaction.atomic
def create_billing_payment_link(company, service_id, merchant_id, now=None):
    now = now or timezone.now()
    if is_company_billing_current(company, now=now):
        raise ValueError("Joriy oylik to'lov allaqachon faol.")

    amount_usd = get_company_payment_due_amount(company)
    if amount_usd <= 0:
        raise ValueError("Siz bepul tarifdasiz. Bu tarif uchun to'lov silkasini yaratish shart emas.")

    existing_link = get_latest_unopened_payment_link(company)
    if existing_link:
        if Decimal(existing_link.amount_usd or 0) == amount_usd:
            return existing_link
        existing_link.status = "canceled"
        existing_link.save(update_fields=["status"])

    amount_uzs = (amount_usd * get_usd_rate()).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    payment_link = BillingPaymentLink.objects.create(
        company=company,
        token=uuid4().hex,
        reason=get_billing_reason(company, now=timezone.localtime(now)),
        billing_period_start=get_billing_period_start(company, timezone.localtime(now)),
        amount_usd=amount_usd,
        amount_uzs=amount_uzs,
        click_url="pending",
    )
    payment_link.click_url = build_click_payment_url(service_id, merchant_id, amount_uzs, payment_link.id)
    payment_link.save(update_fields=["click_url"])
    return payment_link


@transaction.atomic
def consume_billing_payment_link(payment_link, now=None):
    now = now or timezone.now()
    payment_link = BillingPaymentLink.objects.select_for_update().get(pk=payment_link.pk)

    if payment_link.status == "paid":
        raise ValueError("Bu to'lov silkasidan allaqachon foydalanilgan va to'lov tasdiqlangan.")
    if payment_link.status != "created":
        raise ValueError("Bu to'lov silkasiga qayta kirish mumkin emas. Yangi silka yarating.")

    payment_link.status = "opened"
    payment_link.opened_at = now
    payment_link.save(update_fields=["status", "opened_at"])
    return payment_link


def get_billing_dashboard_data(company, now=None):
    now = now or timezone.now()
    latest_link = get_latest_payment_link(company)
    monthly_price_usd = get_company_monthly_price(company)
    prorated_billing = get_prorated_billing(company, now=now)
    pending_amount_usd = prorated_billing["amount"]
    payment_due_usd = pending_amount_usd if pending_amount_usd > 0 else monthly_price_usd
    is_free_plan = monthly_price_usd <= 0
    current_plan_name = company.plan.name if company.plan else ("Maxsus tarif" if company.is_custom_plan else "Tarif tanlanmagan")
    return {
        "is_current": is_free_plan or is_company_billing_current(company, now=now),
        "is_free_plan": is_free_plan,
        "current_plan_name": current_plan_name,
        "has_savdogar_sales": bool(company.is_on_trial or company.custom_has_savdogar_sales),
        "savdogar_contract_text": company.savdogar_contract_text,
        "desktop_agent_stations": company.custom_desktop_agent_stations,
        "desktop_agent_addon_price": company.desktop_agent_addon_price,
        "monthly_price_usd": monthly_price_usd,
        "payment_due_usd": payment_due_usd,
        "pending_amount_usd": pending_amount_usd,
        "is_prorated_due": pending_amount_usd > 0,
        "latest_link": latest_link,
        "payment_links": company.billing_payment_links.order_by("-created_at"),
        "next_payment_date": company.next_payment_date,
        "billing_reason": prorated_billing["reason"] if pending_amount_usd > 0 else get_billing_reason(company, now=timezone.localtime(now)),
    }


@transaction.atomic
def apply_plan_request(plan_request, now=None):
    now = now or timezone.now()
    company = Company.objects.select_for_update().get(pk=plan_request.company_id)
    plan_request = PlanRequest.objects.select_for_update().get(pk=plan_request.pk)

    if plan_request.status != "pending":
        raise ValueError("Faqat kutilayotgan so'rovni tasdiqlash mumkin.")

    was_billing_current = is_company_billing_current(company, now=now)
    paid_until = company.next_payment_date

    if plan_request.is_trial:
        company.is_on_trial = True
        company.trial_expires_at = now + timedelta(days=30)
        company.next_payment_date = company.trial_expires_at
        company.has_used_trial = True
        company.payment_status = "paid"
    elif plan_request.is_custom:
        company.is_custom_plan = True
        company.plan = None
        company.custom_max_users = plan_request.custom_max_users
        company.custom_has_telegram_bot = plan_request.custom_has_telegram_bot
        company.custom_has_analytics = plan_request.custom_has_analytics
        company.custom_has_map = plan_request.custom_has_map
        company.custom_has_savdogar_sales = plan_request.custom_has_savdogar_sales
        company.custom_desktop_agent_stations = plan_request.custom_desktop_agent_stations
        company.custom_backup_type = plan_request.custom_backup_type
        company.custom_price = plan_request.custom_price
    else:
        company.plan = plan_request.plan
        company.is_custom_plan = False
        company.custom_max_users = 0
        company.custom_has_telegram_bot = False
        company.custom_has_analytics = False
        company.custom_has_map = False
        company.custom_has_savdogar_sales = False
        company.custom_desktop_agent_stations = 0
        company.custom_backup_type = "none"
        company.custom_price = 0

    if not plan_request.is_trial:
        if is_company_on_free_plan(company):
            company.payment_status = "paid"
            company.next_payment_date = None
        elif was_billing_current and paid_until and paid_until > now:
            company.payment_status = "paid"
            company.next_payment_date = paid_until
        else:
            company.payment_status = "unpaid"
            company.next_payment_date = now + timedelta(days=5)
        company.is_on_trial = False
        company.trial_expires_at = None

    company.save()
    invalidate_lifecycle_cache(company)

    plan_request.status = "approved"
    plan_request.reviewed_at = now
    plan_request.save(update_fields=["status", "reviewed_at"])
    return company


@transaction.atomic
def reject_plan_request(plan_request, now=None):
    now = now or timezone.now()
    plan_request = PlanRequest.objects.select_for_update().get(pk=plan_request.pk)

    if plan_request.status != "pending":
        raise ValueError("Faqat kutilayotgan so'rovni rad etish mumkin.")

    plan_request.status = "rejected"
    plan_request.reviewed_at = now
    plan_request.save(update_fields=["status", "reviewed_at"])
    return plan_request


def mark_company_paid(company, now=None, days=None, payment_link=None):
    now = now or timezone.now()
    months = get_plan_duration_months(company.plan) if company.plan else 1
    delta = relativedelta(months=months) if not days else timedelta(days=days)
    company.payment_status = "paid"
    is_prorated_payment = bool(payment_link and payment_link.reason.startswith("Tarif farqi:"))
    if not is_prorated_payment:
        if company.next_payment_date and company.next_payment_date > now:
            company.next_payment_date = company.next_payment_date + delta
        else:
            company.next_payment_date = now + delta
    company.is_on_trial = False
    company.trial_expires_at = None
    company.save()
    invalidate_lifecycle_cache(company)
    return company


def mark_company_unpaid(company):
    company.payment_status = "unpaid"
    company.save(update_fields=["payment_status"])
    invalidate_lifecycle_cache(company)
    return company
