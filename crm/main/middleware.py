from django.shortcuts import render
from django.conf import settings
from .models import Company

class CompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Admin panel, Super Admin, and API webhooks should always be accessible via project ROOT_URLCONF
        path = request.path.strip('/')
        if path.startswith('admin_panel') or path.startswith('super-admin') or path.startswith('api/click'):
            return self.get_response(request)
        
        host = request.get_host().split(':')[0]
        base_domain = getattr(settings, 'BASE_DOMAIN', 'stockfirm.uz').split(':')[0]
        parts = host.split('.')

        # Default values
        request.company = None
        request.is_landing = False
        request.is_admin_panel = False
        request.urlconf = None
        request.has_analytics = False
        request.has_telegram_bot = False
        request.has_map = False

        # Check if it's the landing page or local dev
        is_base = host == base_domain or host == f"www.{base_domain}"
        is_local = host in ["127.0.0.1", "localhost", "lvh.me"]
        
        if is_base or is_local:
            request.is_landing = True
            request.urlconf = 'landing.urls'
        
        # admin.stockfirm.uz -> super admin
        elif parts[0] == "admin":
            request.is_admin_panel = True
            request.urlconf = 'crm.admin_urls'
        
        # firma subdomain: firma.stockfirm.uz
        else:
            subdomain = parts[0]
            try:
                company = Company.objects.get(subdomain=subdomain)
                
                # Check lifecycle status
                from django.utils import timezone
                now = timezone.now()
                
                # 1. Automatic Setup Expiration
                if company.setup_mode and company.setup_expires_at and now > company.setup_expires_at:
                    company.setup_mode = False
                    company.setup_expires_at = None
                    company.save()
                
                # 2. Trial Expiration Check
                if company.is_on_trial and company.trial_expires_at and now > company.trial_expires_at:
                    # Trial tugadi — doimo is_on_trial ni False qilish
                    company.is_on_trial = False
                    company.trial_expires_at = None
                    if not company.plan and not company.is_custom_plan:
                        # Agar hech qanday tarif yo'q bo'lsa — firmani deaktiv qilish
                        company.is_active = False
                    company.save()
                        
                # 3. Grace Period Expiration Check (Unpaid past 3 days)
                from datetime import timedelta
                payment_reason = None
                if company.payment_status == 'unpaid' and company.next_payment_date:
                    if now > company.next_payment_date + timedelta(days=3):
                        payment_reason = 'payment_overdue'

                if not company.is_active:
                    return render(request, 'suspended.html', {'company': company, 'reason': 'stopped'}, status=403)
                if payment_reason:
                    return render(request, 'suspended.html', {'company': company, 'reason': payment_reason}, status=403)
                
                # 4. Setup Mode Access Restriction
                if company.setup_mode:
                    # Only allow 'ega' (admin) to access
                    # Note: request.user is available because we are after AuthenticationMiddleware
                    is_admin_access = request.user.is_authenticated and request.user.type == 'ega'
                    is_public_path = any(request.path.startswith(p) for p in ['/login/', '/logout/', '/static/', '/media/'])
                    
                    if not (is_admin_access or is_public_path):
                        return render(request, 'setup_in_progress.html', {'company': company})

                request.company = company
                request.is_landing = False
                request.urlconf = 'main.urls'
                
                # Attach plan features
                if company.is_custom_plan:
                    request.has_analytics = company.custom_has_analytics
                    request.has_telegram_bot = company.custom_has_telegram_bot
                    request.has_map = company.custom_has_map
                elif company.plan:
                    request.has_analytics = company.plan.has_analytics
                    request.has_telegram_bot = company.plan.has_telegram_bot
                    request.has_map = company.plan.has_map
                
                # Free trials usually include everything
                if company.is_on_trial:
                    request.has_analytics = True
                    request.has_telegram_bot = True
                    request.has_map = True
            except Company.DoesNotExist:
                # If subdomain doesn't exist, show custom 404 page even in debug mode
                return render(request, '404.html', status=404)

        response = self.get_response(request)
        return response
