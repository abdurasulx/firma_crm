from decimal import Decimal
from datetime import date, timedelta
from uuid import uuid4

import requests
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from ..models import BillingPaymentLink, Company, PlanRequest


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
    if company.plan:
        return Decimal(company.plan.price)
    return Decimal(company.custom_price or 0)


def get_billing_period_start(now=None):
    now = now or timezone.localtime()
    return date(now.year, now.month, 1)


def get_billing_reason(company, now=None):
    now = now or timezone.localtime()
    return f"{now.strftime('%B %Y')} uchun oylik abonent to'lovi"


def is_company_billing_current(company, now=None):
    now = now or timezone.now()
    return bool(company.payment_status == "paid" and company.next_payment_date and company.next_payment_date > now)


def get_latest_payment_link(company):
    return company.billing_payment_links.order_by("-created_at").first()


def get_latest_unopened_payment_link(company):
    return company.billing_payment_links.filter(status="created").order_by("-created_at").first()


def build_click_payment_url(service_id, merchant_id, amount_uzs, payment_link_id):
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

    existing_link = get_latest_unopened_payment_link(company)
    if existing_link:
        return existing_link

    amount_usd = get_company_monthly_price(company)
    if amount_usd <= 0:
        raise ValueError("Ushbu tarif uchun to'lov summasi aniqlanmadi.")

    amount_uzs = (amount_usd * get_usd_rate()).quantize(Decimal("0.01"))
    payment_link = BillingPaymentLink.objects.create(
        company=company,
        token=uuid4().hex,
        reason=get_billing_reason(company, now=timezone.localtime(now)),
        billing_period_start=get_billing_period_start(timezone.localtime(now)),
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
    return {
        "is_current": is_company_billing_current(company, now=now),
        "monthly_price_usd": get_company_monthly_price(company),
        "latest_link": latest_link,
        "payment_links": company.billing_payment_links.order_by("-created_at")[:10],
        "next_payment_date": company.next_payment_date,
        "billing_reason": get_billing_reason(company, now=timezone.localtime(now)),
    }


@transaction.atomic
def apply_plan_request(plan_request, now=None):
    now = now or timezone.now()
    company = Company.objects.select_for_update().get(pk=plan_request.company_id)
    plan_request = PlanRequest.objects.select_for_update().get(pk=plan_request.pk)

    if plan_request.status != "pending":
        raise ValueError("Faqat kutilayotgan so'rovni tasdiqlash mumkin.")

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
        company.custom_backup_type = plan_request.custom_backup_type
        company.custom_price = plan_request.custom_price
    else:
        company.plan = plan_request.plan
        company.is_custom_plan = False
        company.custom_max_users = 0
        company.custom_has_telegram_bot = False
        company.custom_has_analytics = False
        company.custom_has_map = False
        company.custom_backup_type = "none"
        company.custom_price = 0

    if not plan_request.is_trial:
        company.payment_status = "unpaid"
        company.next_payment_date = now + timedelta(days=5)
        company.is_on_trial = False
        company.trial_expires_at = None

    company.save()

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


def mark_company_paid(company, now=None, days=30):
    now = now or timezone.now()
    company.payment_status = "paid"
    if company.next_payment_date and company.next_payment_date > now:
        company.next_payment_date = company.next_payment_date + timedelta(days=days)
    else:
        company.next_payment_date = now + timedelta(days=days)
    company.is_on_trial = False
    company.trial_expires_at = None
    company.save()
    return company


def mark_company_unpaid(company):
    company.payment_status = "unpaid"
    company.save(update_fields=["payment_status"])
    return company
