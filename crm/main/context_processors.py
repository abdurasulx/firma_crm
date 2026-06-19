from main.models import Company, PlanRequest
from main.services.billing_service import get_billing_dashboard_data
from django.db.utils import OperationalError, ProgrammingError

def plan_context(request):
    """
    Kompaniya tarifiga ko'ra funksiyalarni template-ga uzatish.
    """
    superadmin_context = _safe_superadmin_context(request)
    company = getattr(request, 'company', None)
    if company:
        is_trial = company.is_on_trial
        
        if is_trial:
            has_analytics = True
            has_telegram_bot = True
            has_map = True
            max_users = 0
            backup_type = 'none'
            current_plan_obj = None
            plan_name = "Sinov Muddati (30 kun)"
        elif company.is_custom_plan:
            has_analytics = company.custom_has_analytics
            has_telegram_bot = company.custom_has_telegram_bot
            has_map = company.custom_has_map
            max_users = company.custom_max_users
            backup_type = company.custom_backup_type
            current_plan_obj = None
            plan_name = "Maxsus"
        else:
            plan = company.plan
            has_analytics = plan.has_analytics if plan else False
            has_telegram_bot = plan.has_telegram_bot if plan else False
            has_map = plan.has_map if plan else False
            max_users = plan.max_users if plan else 5
            backup_type = plan.backup_type if plan else 'none'
            current_plan_obj = plan
            plan_name = plan.name if plan else "Noma'lum"
            
        # Backup availability logic
        is_backup_available = False
        if backup_type != 'none':
            if not company.last_backup_at:
                is_backup_available = True
            else:
                from django.utils import timezone
                delta = timezone.now() - company.last_backup_at
                if backup_type == 'daily' and delta.days >= 1:
                    is_backup_available = True
                elif backup_type == 'weekly' and delta.days >= 7:
                    is_backup_available = True
                elif backup_type == 'monthly' and delta.days >= 30:
                    is_backup_available = True
                    
        return {
            'current_plan': current_plan_obj,
            'current_plan_name': plan_name,
            'has_analytics': has_analytics,
            'has_telegram_bot': has_telegram_bot,
            'has_map': has_map,
            'max_users': max_users,
            'backup_type': backup_type,
            'is_backup_available': is_backup_available,
            'billing_data': _safe_billing_data(company),
            **superadmin_context,
        }
    
    # Default values if no company or plan
    return {
        'current_plan': None,
        'current_plan_name': "Noma'lum",
        'has_analytics': False,
        'has_telegram_bot': False,
        'has_map': False,
        'max_users': 5,
        'backup_type': 'none',
        'is_backup_available': False,
        'billing_data': {
            'is_current': False,
            'monthly_price_usd': 0,
            'payment_due_usd': 0,
            'pending_amount_usd': 0,
            'is_prorated_due': False,
            'latest_link': None,
            'payment_links': [],
            'next_payment_date': None,
            'billing_reason': '',
        },
        **superadmin_context,
    }


def _safe_billing_data(company):
    try:
        return get_billing_dashboard_data(company)
    except (OperationalError, ProgrammingError):
        return {
            'is_current': False,
            'monthly_price_usd': 0,
            'payment_due_usd': 0,
            'pending_amount_usd': 0,
            'is_prorated_due': False,
            'latest_link': None,
            'payment_links': [],
            'next_payment_date': None,
            'billing_reason': '',
        }


def _safe_superadmin_context(request):
    try:
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and user.is_superuser:
            return {
                'pending_plan_requests': PlanRequest.objects.filter(status='pending').count(),
            }
    except (OperationalError, ProgrammingError):
        pass
    return {}
