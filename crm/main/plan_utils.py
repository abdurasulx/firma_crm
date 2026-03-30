"""
Plan & Billing Utilities

Yagona joy — firma hozirda xizmatlardan foydalana oladimi yoki yo'qligini tekshirish.
Bu funksiyalar barcha view-larda `payment_status != 'paid'` kabi to'g'ridan-to'g'ri
tekshiruvlar o'rniga ishlatiladi.
"""

from django.utils import timezone


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
            'backup_type': 'none',
            'max_users': 5,
        }
    
    # Trial — hamma narsa yoqiladi, FAQAT backup yo'q
    if company.is_on_trial:
        return {
            'has_analytics': True,
            'has_telegram_bot': True,
            'has_map': True,
            'backup_type': 'none',  # Trialda backup yo'q
            'max_users': 0,  # 0 = unlimited
        }
    
    if company.is_custom_plan:
        return {
            'has_analytics': company.custom_has_analytics,
            'has_telegram_bot': company.custom_has_telegram_bot,
            'has_map': company.custom_has_map,
            'backup_type': company.custom_backup_type,
            'max_users': company.custom_max_users,
        }
    
    plan = company.plan
    if plan:
        return {
            'has_analytics': plan.has_analytics,
            'has_telegram_bot': plan.has_telegram_bot,
            'has_map': plan.has_map,
            'backup_type': plan.backup_type,
            'max_users': plan.max_users,
        }
    
    # No plan
    return {
        'has_analytics': False,
        'has_telegram_bot': False,
        'has_map': False,
        'backup_type': 'none',
        'max_users': 5,
    }
