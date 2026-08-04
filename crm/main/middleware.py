from django.contrib.auth import logout as auth_logout
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.conf import settings
from .models import Company
from .services.billing_service import sync_company_lifecycle

SESSION_CHECK_EXEMPT_PATHS = ('/login/', '/logout/', '/static/', '/media/')

# sync_company_lifecycle vaqt-asoslangan holat o'tishlarini (sinov muddati
# tugashi, to'lov muddati o'tishi va h.k.) tekshiradi — bular soniyama-soniya
# aniq bo'lishi shart emas, shuning uchun har so'rovda emas, bir necha
# daqiqada bir marta qayta hisoblanadi (UPDATENEWVERSION.md #6).
LIFECYCLE_SYNC_CACHE_SECONDS = 300


class CompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Admin panel, Super Admin, and API webhooks should always be accessible via project ROOT_URLCONF
        path = request.path.strip('/')
        if path.startswith('admin_panel') or path.startswith('super-admin') or path.startswith('api/click') or path.startswith('api/agent'):
            return self.get_response(request)
        
        host = request.get_host().split(':')[0]
        base_domain = getattr(settings, 'BASE_DOMAIN', 'stockfirm.uz').split(':')[0]
        landing_domains = set(getattr(settings, 'LANDING_DOMAINS', []))
        landing_domains.update({base_domain, f"www.{base_domain}"})
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
        is_base = host in landing_domains
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
                lifecycle_cache_key = f'company_lifecycle:{company.id}'
                lifecycle_state = cache.get(lifecycle_cache_key)
                if lifecycle_state is None:
                    lifecycle_state = sync_company_lifecycle(company)
                    cache.set(lifecycle_cache_key, lifecycle_state, LIFECYCLE_SYNC_CACHE_SECONDS)
                payment_reason = lifecycle_state['payment_reason']

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

                # Bitta faol veb-sessiya qoidasi: boshqa qurilma/brauzerda
                # keyinroq login qilingan bo'lsa (`web_session_key` yangilangan),
                # bu eski sessiya shu yerda avtomatik yopiladi.
                is_session_check_exempt = any(request.path.startswith(p) for p in SESSION_CHECK_EXEMPT_PATHS)
                if not is_session_check_exempt and request.user.is_authenticated and request.user.web_session_key:
                    if request.user.web_session_key != request.session.session_key:
                        auth_logout(request)
                        return redirect('/login/?session_kicked=1')
            except Company.DoesNotExist:
                # If subdomain doesn't exist, show custom 404 page even in debug mode
                return render(request, '404.html', status=404)

        response = self.get_response(request)
        return response
