"""
Plan & Billing Utilities

Yagona joy — firma hozirda xizmatlardan foydalana oladimi yoki yo'qligini tekshirish.
Bu funksiyalar barcha view-larda `payment_status != 'paid'` kabi to'g'ridan-to'g'ri
tekshiruvlar o'rniga ishlatiladi.
"""

import re

from django.utils import timezone


PLAN_META_RE = re.compile(r"\[\[stockfirm:([^\]]*)\]\]\s*", re.IGNORECASE)


def parse_plan_metadata(plan):
    raw = getattr(plan, 'description', '') or ''
    match = PLAN_META_RE.search(raw)
    meta = {
        'hidden': False,
        'savdogar': False,
        'lock_changes': False,
        'months': 1,
        'description': PLAN_META_RE.sub('', raw).strip(),
    }
    if not match:
        return meta

    for item in match.group(1).split(';'):
        if '=' not in item:
            continue
        key, value = [part.strip().lower() for part in item.split('=', 1)]
        if key == 'hidden':
            meta['hidden'] = value in ['1', 'true', 'yes', 'on']
        elif key == 'savdogar':
            meta['savdogar'] = value in ['1', 'true', 'yes', 'on']
        elif key in ['lock', 'lock_changes']:
            meta['lock_changes'] = value in ['1', 'true', 'yes', 'on']
        elif key == 'months':
            try:
                meta['months'] = max(1, int(value))
            except ValueError:
                meta['months'] = 1
    return meta


def build_plan_description(description, hidden=False, lock_changes=False, months=1, savdogar=False):
    months = max(1, int(months or 1))
    clean_description = PLAN_META_RE.sub('', description or '').strip()
    if not hidden and not lock_changes and months == 1 and not savdogar:
        return clean_description
    marker = f"[[stockfirm:hidden={int(bool(hidden))};lock={int(bool(lock_changes))};months={months};savdogar={int(bool(savdogar))}]]"
    return f"{marker}\n{clean_description}".strip()


def plan_is_visible_to_owner(plan):
    return not parse_plan_metadata(plan).get('hidden')


def plan_is_contact_only(plan):
    """Hidden plan = faqat tizim bilan aloqa orqali beriladigan tarif."""
    return parse_plan_metadata(plan).get('hidden', False)


def get_plan_duration_months(plan):
    return parse_plan_metadata(plan).get('months', 1)


def plan_locks_tariff_changes(plan):
    return bool(parse_plan_metadata(plan).get('lock_changes'))


def get_tariff_lock_reason(company, now=None):
    """
    Tarif o'zgartirish bloklangan bo'lsa sababini qaytaradi.
    Returns: None | 'contact_only' | 'lock_changes'
    """
    now = now or timezone.now()
    if not company or not company.plan:
        return None
    if not company.next_payment_date or company.next_payment_date <= now:
        return None
    if plan_is_contact_only(company.plan):
        return 'contact_only'
    if plan_locks_tariff_changes(company.plan):
        return 'lock_changes'
    return None


def is_tariff_change_locked(company, now=None):
    return get_tariff_lock_reason(company, now) is not None


def company_has_paid_access(company):
    """
    Firma to'lov qilganmi? (Qat'iy tekshiruv — grace period YO'Q)
    
    Ruxsat beriladi FAQAT:
    1. payment_status == 'paid' (to'lov qilingan)
    
    Trial uchun alohida funksiya ishlatiladi.
    
    Returns:
        bool: True — to'lov qilingan, False — to'lanmagan
    """
    if not company or not company.is_active:
        return False
    return company.payment_status == 'paid'


def company_has_access(company):
    """
    Firma hozirda tizim xizmatlaridan foydalana oladimi?
    
    Ruxsat beriladi agar:
    1. payment_status == 'paid' (to'lov qilingan)
    2. is_on_trial == True va trial muddati tugamagan
    
    To'lanmagan firma — feature-lardan foydalana OLMAYDI.
    
    Returns:
        bool: True — firma foydalana oladi, False — bloklanadi
    """
    if not company or not company.is_active:
        return False
    
    # 1. To'lov qilingan
    if company.payment_status == 'paid':
        return True
    
    # 2. Trial davri faol va muddati tugamagan
    if company.is_on_trial:
        if company.trial_expires_at and company.trial_expires_at > timezone.now():
            return True
    
    return False


def get_feature_flags(company):
    """
    Firma uchun tarif imkoniyatlarini qaytarish.
    
    Custom plan bo'lsa — custom fieldlardan oladi.
    Standart plan bo'lsa — plan fieldlaridan oladi.
    Trial davrda — barcha imkoniyatlar yoqiladi (backup BUNDAN MUSTASNO).
    
    Returns:
        dict: {has_analytics, has_telegram_bot, has_map, backup_type, max_users}
    """
    if not company:
        return {
            'has_analytics': False,
            'has_telegram_bot': False,
            'has_map': False,
            'has_savdogar_sales': False,
            'backup_type': 'none',
            'max_users': 5,
        }
    
    # Trial — hamma narsa yoqiladi, FAQAT backup yo'q
    if company.is_on_trial:
        return {
            'has_analytics': True,
            'has_telegram_bot': True,
            'has_map': True,
            'has_savdogar_sales': True,
            'backup_type': 'none',  # Trialda backup yo'q
            'max_users': 0,  # 0 = unlimited
        }
    
    if company.is_custom_plan:
        return {
            'has_analytics': company.custom_has_analytics,
            'has_telegram_bot': company.custom_has_telegram_bot,
            'has_map': company.custom_has_map,
            'has_savdogar_sales': company.custom_has_savdogar_sales,
            'backup_type': company.custom_backup_type,
            'max_users': company.custom_max_users,
        }
    
    plan = company.plan
    if plan:
        meta = parse_plan_metadata(plan)
        return {
            'has_analytics': plan.has_analytics,
            'has_telegram_bot': plan.has_telegram_bot,
            'has_map': plan.has_map,
            'has_savdogar_sales': company.custom_has_savdogar_sales or meta.get('savdogar'),
            'backup_type': plan.backup_type,
            'max_users': plan.max_users,
        }
    
    # No plan
    return {
        'has_analytics': False,
        'has_telegram_bot': False,
        'has_map': False,
        'has_savdogar_sales': False,
        'backup_type': 'none',
        'max_users': 5,
    }
