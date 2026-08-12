from django.shortcuts import render, get_list_or_404, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages 
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.shortcuts import redirect
from .models import BACKUP_CHOICES, BillingPaymentLink, Company, Plan, HaridorDukon, User, YetkazibBeruvchi, Pazanda, Mahsulot, MahsulotTuri, Savdo, YuklamaSorov, MiqdorQoshish, HaridorDukon, AmalLog, qaytarilgan_mahsulotlar, PlanRequest, NasiyaTolov, ProductionMaterialRequest, StockHistory, Serial, Ombor, MahsulotQoshimchaXarajat, PazandaMahsulot, MahsulotRetsept, DESKTOP_AGENT_UNIT_PRICE, XodimBadge, ProductionTask, XodimMaosh, XodimTolov, XodimOyYopish, QoshimchaChiqim, AgentRelease, TaskMaterialPickup
from .functions import mahsulotlar_miqdori, makenewform, yuklama_maker, accptyuk, sotishm, sotuv_new_form ,yetkazuvchi_mahsulot_filter, get_bugungi_savdo_summ, add_spctoint, format_compact_money
from .plan_utils import (
    company_has_access, get_feature_flags,
    is_tariff_change_locked, get_tariff_lock_reason,
    plan_is_visible_to_owner, plan_is_contact_only,
)
import datetime as dt
import json
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from collections import defaultdict
from decimal import Decimal, InvalidOperation

# Login brute-force himoyasi (UPDATENEWVERSION.md #8) — IP + username
# bo'yicha muvaffaqiyatsiz urinishlarni sanaydi, limitga yetganda vaqtincha
# bloklaydi. Yangi tashqi kutubxona (masalan django-axes) kerak emas —
# mavjud Django cache orqali yetarli.
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60


def _get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _login_throttle_key(request, username):
    return f'login_throttle:{_get_client_ip(request)}:{(username or "").lower()}'


def _is_login_locked_out(request, username):
    return cache.get(_login_throttle_key(request, username), 0) >= LOGIN_MAX_ATTEMPTS


def _register_failed_login(request, username):
    key = _login_throttle_key(request, username)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, LOGIN_LOCKOUT_SECONDS)


def _reset_login_throttle(request, username):
    cache.delete(_login_throttle_key(request, username))

def send_ws_notification(company_subdomain, title, message, type='info', refresh=False):
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"notifications_{company_subdomain}",
                {
                    "type": "send_notification",
                    "title": title,
                    "message": message,
                    "notification_type": type,
                    "refresh": refresh,
                }
            )
    except Exception as e:
        print(f"WS Notification Error: {e}")

@login_required(login_url='login')
def end_setup(request):
    if request.user.type != 'ega':
        messages.error(request, "Faqat korxona rahbari sozlash rejimini tugata oladi.")
        return redirect('main')
    
    company = request.company
    company.setup_mode = False
    company.setup_expires_at = None
    company.save()
    from .services.billing_service import invalidate_lifecycle_cache
    invalidate_lifecycle_cache(company)

    messages.success(request, "Tizim sozlash rejimi muvaffaqiyatli yakunlandi. Endi barcha xodimlar tizimdan foydalana oladi.")
    return redirect('main')



from .services.stock_service import (
    approve_miqdor_qoshish_service,
    approve_yuklama_sorov_service,
    get_pazanda_month_stats,
    get_mahsulot_statistika,
    recompute_tannarx,
    effective_ish_haqi_turi,
)
from .services.retsept_service import add_retsept_row, delete_retsept_row
from .services import qr_service, task_service, payroll_service, kpi_service
from .services.auth_service import create_user_service, update_user_service
from .services.billing_service import (
    consume_billing_payment_link,
    create_billing_payment_link,
    get_billing_dashboard_data,
    get_company_dashboard_url,
    get_company_login_url,
)
from landing.realtime import broadcast_superadmin_update
from .analytics.services import get_dashboard_stats
from .services.credit_service import (
    DEFAULT_SAVDOGAR_CONTRACT_TEMPLATE,
    SYSTEM_CREDIT_RULES,
    allowed_credit_terms,
    build_contract_draft,
    build_credit_contract,
    calculate_credit_total,
    credit_due_date,
)
from .credit_utils import add_months

User = get_user_model()
# Create your views here.
from .bot_logic import verify_tg_link_token

def _apply_session_expiry(request, user):
    """'ega' roli moliyaviy/billing amallarni boshqargani uchun sessiyasi
    qisqaroq bo'lishi kerak (UPDATENEWVERSION.md — sessiya muddati).

    Shuningdek, bitta faol veb-sessiya qoidasini ta'minlash uchun joriy
    sessiya kalitini `User.web_session_key`ga yozib qo'yadi — boshqa
    qurilmada/brauzerda avval kirilgan bo'lsa, o'sha eski sessiya
    `CompanyMiddleware` orqali keyingi so'rovda avtomatik yopiladi."""
    if getattr(user, 'type', None) == 'ega':
        request.session.set_expiry(60 * 60 * 24)  # 1 kun
    request.session.save()  # session_key generatsiya qilinishi uchun majburiy
    user.web_session_key = request.session.session_key
    user.save(update_fields=['web_session_key'])


def login(request):
    data={}
    if request.GET.get('session_kicked'):
        messages.info(request, "Boshqa qurilma yoki brauzerda tizimga kirilgani uchun bu sessiya yopildi.")
    is_tg_linking = bool(request.GET.get('tg_id') and request.GET.get('hash'))
    is_session_linking = bool(request.session.get('pending_tg_id'))
    
    if not getattr(request, 'company', None):
        # If no company (landing domain or admin panel)
        if getattr(request, 'is_admin_panel', False) or is_tg_linking or is_session_linking:
            # Let it proceed for superuser or telegram linking
            pass
        else:
            return redirect('landing_home')

    # Telegram Auto-Login and Linking Logic
    tg_id = request.GET.get('tg_id')
    tg_hash = request.GET.get('hash')

    if tg_id and tg_hash:
        if verify_tg_link_token(tg_id, tg_hash):
            # 1. Already Authenticated? Link it now.
            if request.user.is_authenticated:
                # Check tariff or if user is owner
                if getattr(request, 'has_telegram_bot', False) or request.user.type == 'ega':
                    if User.objects.filter(tg_id=tg_id).exclude(id=request.user.id).exists():
                        messages.error(request, "Ushbu Telegram hisobi boshqa foydalanuvchiga bog'langan!")
                    else:
                        request.user.tg_id = tg_id
                        request.user.save()
                        messages.success(request, "Telegram hisobingiz muvaffaqiyatli bog'landi.")
                else:
                    messages.warning(request, "Sizning tarifingizda Telegram bot xizmati mavjud emas.")
                
                from django.conf import settings
                return redirect(get_company_dashboard_url(request.user.company, getattr(settings, 'BASE_DOMAIN', 'stockfirm.uz')))
            
            # 2. Not authenticated? Check for existing link for auto-login
            # Auto-login should only work if tariff is ON or if user is owner
            query = User.objects.filter(tg_id=tg_id)
            if request.company:
                query = query.filter(company=request.company)
            linked_user = query.first()
            if linked_user:
                if getattr(request, 'has_telegram_bot', False) or linked_user.type == 'ega':
                    auth_login(request, linked_user)
                    _apply_session_expiry(request, linked_user)
                    messages.success(request, f"Xush kelibsiz, {linked_user.tuliq_ismi or linked_user.username}! (Telegram orqali kirildi)")
                    from django.conf import settings
                    return redirect(get_company_dashboard_url(linked_user.company, getattr(settings, 'BASE_DOMAIN', 'stockfirm.uz')))
                else:
                    messages.warning(request, "Sizning tarifingizda Telegram bot xizmati mavjud emas.")
            
            # 3. New link? Store in session for post-login linking
            request.session['pending_tg_id'] = tg_id
        else:
            messages.error(request, "Telegram havolasi noto'g'ri!")

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        data['username'] = username
        data['password'] = password

        if _is_login_locked_out(request, username):
            messages.error(
                request,
                "Juda ko'p muvaffaqiyatsiz urinish. Iltimos, 15 daqiqadan keyin qayta urinib ko'ring.",
            )
            return render(request, 'login.html', data)

        user = authenticate(request, username=username, password=password)

        if user is not None:
            _reset_login_throttle(request, username)
            # Successful authentication
            # Check for pending Telegram link
            pending_tg_id = request.session.get('pending_tg_id')
            if pending_tg_id:
                # Check tariff or if user is owner
                if getattr(request, 'has_telegram_bot', False) or user.type == 'ega':
                    if User.objects.filter(tg_id=pending_tg_id).exists():
                        messages.error(request, "Ushbu Telegram hisobi boshqa foydalanuvchiga bog'langan!")
                    else:
                        user.tg_id = pending_tg_id
                        user.save()
                        messages.success(request, "Telegram hisobingiz muvaffaqiyatli bog'landi.")
                else:
                    messages.warning(request, "Sizning tarifingizda Telegram bot xizmati mavjud emas.")
                del request.session['pending_tg_id']

            # Check if it's a superuser logging into the admin panel
            if user.is_superuser and getattr(request, 'is_admin_panel', False):
                auth_login(request, user)
                _apply_session_expiry(request, user)
                return redirect('super_dashboard')

            # Standard company user login
            user_company = getattr(user, 'company', None)
            if user_company and (user_company == request.company or is_tg_linking or is_session_linking):
                auth_login(request, user)
                _apply_session_expiry(request, user)
                if not request.company:
                    # Redirect to subdomain if logging in from landing
                    from django.conf import settings
                    return redirect(get_company_dashboard_url(user_company, getattr(settings, 'BASE_DOMAIN', 'stockfirm.uz')))
                return redirect('main')
            else:
                messages.error(request, "Siz ushbu firmaga tegishli emassiz!")
        else:
            _register_failed_login(request, username)
            messages.error(request, "Login yoki parol noto'g'ri!")

    return render(request, 'login.html',data)


@login_required(login_url='login')
def select_plan(request, plan_id):
    """Tarif tanlash uchun so'rov yuborish"""
    if request.user.type != 'ega':
        messages.error(request, "Faqat do'kon egasi tarifni o'zgartira oladi.")
        return redirect('main')
    lock_reason = get_tariff_lock_reason(request.company)
    if lock_reason == 'contact_only':
        messages.error(request, f"Siz tizim bilan aloqa orqali olingan maxsus tarifdasiz. Muddat ({request.company.next_payment_date.strftime('%d.%m.%Y')}) tugamaguncha tarifni o'zgartirib bo'lmaydi.")
        return redirect('main')
    if lock_reason == 'lock_changes':
        messages.error(request, f"Ushbu tarif muddati {request.company.next_payment_date.strftime('%d.%m.%Y')} gacha faol. Muddat tugamaguncha tarifni o'zgartirib bo'lmaydi.")
        return redirect('main')
    
    plan = get_object_or_404(Plan, id=plan_id, is_active=True)
    if not plan_is_visible_to_owner(plan):
        messages.error(request, "Bu tarif faqat superadmin tomonidan biriktiriladi.")
        return redirect('select_plan_page')
    company = request.company
    current_staff_count = User.objects.filter(company=company).exclude(type='ega').count()
    
    # Check for existing pending request
    if PlanRequest.objects.filter(company=company, status='pending').exists():
        messages.warning(request, "Sizda kutilayotgan tarif so'rovi mavjud. Iltimos, admin tasdiqlashini kuting.")
        return redirect('main')

    if plan.max_users != 0 and current_staff_count > plan.max_users:
        messages.error(
            request,
            f"Bu tarifni tanlab bo'lmaydi. Hozir {current_staff_count} ta hodimingiz bor, tarif esa {plan.max_users} tagacha ruxsat beradi."
        )
        return redirect('select_plan_page')

    # If they are just starting (no plan yet), we might still want approval or immediate? 
    # User said "tasdiqlasa keyin ozgarsin", so always approval.
    PlanRequest.objects.create(
        company=company,
        plan=plan,
        is_custom=False,
        status='pending'
    )
    broadcast_superadmin_update()
    
    messages.success(request, f"{plan.name} tarifi uchun so'rov yuborildi. Admin tasdiqlaganidan so'ng faollashadi.")
    return redirect('main')

@login_required(login_url='login')
@require_POST
def select_custom_plan(request):
    """Maxsus (Custom) tarif uchun so'rov yuborish"""
    if request.user.type != 'ega':
        messages.error(request, "Faqat do'kon egasi tarifni o'zgartira oladi.")
        return redirect('main')
    lock_reason = get_tariff_lock_reason(request.company)
    if lock_reason == 'contact_only':
        messages.error(request, f"Siz tizim bilan aloqa orqali olingan maxsus tarifdasiz. Muddat ({request.company.next_payment_date.strftime('%d.%m.%Y')}) tugamaguncha tarifni o'zgartirib bo'lmaydi.")
        return redirect('main')
    if lock_reason == 'lock_changes':
        messages.error(request, f"Ushbu tarif muddati {request.company.next_payment_date.strftime('%d.%m.%Y')} gacha faol. Muddat tugamaguncha tarifni o'zgartirib bo'lmaydi.")
        return redirect('main')

    company = request.company
    current_staff_count = User.objects.filter(company=company).exclude(type='ega').count()

    # Check for existing pending request
    if PlanRequest.objects.filter(company=company, status='pending').exists():
        messages.warning(request, "Sizda kutilayotgan tarif so'rovi mavjud. Iltimos, admin tasdiqlashini kuting.")
        return redirect('main')

    unlimited_staff = 'unlimited_staff' in request.POST
    if unlimited_staff:
        staff_count = 0
    else:
        staff_count = int(request.POST.get('staff_count', 5))
        if staff_count > 55:
            staff_count = 0  # 0 indicates unlimited
            unlimited_staff = True

    if staff_count != 0 and staff_count < current_staff_count:
        messages.error(
            request,
            f"Maxsus tarifdagi hodim limiti kamida {current_staff_count} bo'lishi kerak. Chunki hozir {current_staff_count} ta hodim mavjud."
        )
        return redirect('select_plan_page')
    has_bot = 'has_bot' in request.POST
    has_analytics = 'has_analytics' in request.POST
    has_map = 'has_map' in request.POST
    has_savdogar_sales = 'has_savdogar_sales' in request.POST
    backup_type = request.POST.get('backup_type', 'none')
    try:
        desktop_agent_stations = max(int(request.POST.get('desktop_agent_stations', 0) or 0), 0)
    except ValueError:
        desktop_agent_stations = 0

    price = Decimal("0.00")
    if staff_count == 0: price += Decimal("55.00")
    else: price += Decimal(staff_count)

    if has_map: price += Decimal("20.00")
    if has_bot: price += Decimal("5.00")
    if has_analytics: price += Decimal("15.00")
    if has_savdogar_sales: price += Decimal("10.00")
    price += desktop_agent_stations * DESKTOP_AGENT_UNIT_PRICE

    if backup_type == 'monthly': price += Decimal("5.00")
    elif backup_type == 'weekly': price += Decimal("15.00")
    elif backup_type == 'daily': price += Decimal("30.00")

    PlanRequest.objects.create(
        company=company,
        plan=company.plan if company.plan and not company.is_custom_plan else None,
        is_custom=True,
        custom_max_users=staff_count,
        custom_has_telegram_bot=has_bot,
        custom_has_analytics=has_analytics,
        custom_has_map=has_map,
        custom_has_savdogar_sales=has_savdogar_sales,
        custom_desktop_agent_stations=desktop_agent_stations,
        custom_backup_type=backup_type,
        custom_price=price,
        status='pending'
    )
    broadcast_superadmin_update()

    messages.success(request, "Maxsus tarif uchun so'rov yuborildi. Admin tasdiqlaganidan so'ng faollashadi.")
    return redirect('main')

@login_required(login_url='login')
def request_trial(request):
    company = request.company
    if request.user.type != 'ega':
        messages.error(request, "Faqat do'kon egasi sinov muddatini so'rashi mumkin.")
        return redirect('main')
    
    if company.has_used_trial:
        messages.error(request, "Siz allaqachon sinov muddatidan foydalanganiz.")
        return redirect('main')
    
    # Check if more than 10 days since creation
    from django.utils import timezone
    from datetime import timedelta
    if company.created_at + timedelta(days=10) < timezone.now():
        messages.error(request, "Sinov muddatini so'rash vaqti tugagan (ro'yxatdan o'tgandan keyin 10 kun ichida ruxsat beriladi).")
        return redirect('main')
    
    # Check if already has a pending trial request
    if PlanRequest.objects.filter(company=company, is_trial=True, status='pending').exists():
        messages.info(request, "Sizning sinov muddati uchun so'rovingiz ko'rib chiqilmoqda.")
        return redirect('main')
        
    PlanRequest.objects.create(
        company=company,
        is_trial=True,
        status='pending'
    )
    broadcast_superadmin_update()
    messages.success(request, "Sinov muddati uchun so'rov yuborildi. Tez orada tasdiqlanadi.")
    return redirect('main')


@login_required(login_url='login')
def billing_page(request):
    if request.user.type != 'ega':
        return redirect('main')

    billing_data = get_billing_dashboard_data(request.company)
    paginator = Paginator(billing_data['payment_links'], 8)
    billing_data['payment_links_page'] = paginator.get_page(request.GET.get('page'))
    billing_data['payment_links'] = billing_data['payment_links_page'].object_list
    return render(request, 'billing.html', billing_data)


@login_required(login_url='login')
@require_POST
def create_billing_link(request):
    if request.user.type != 'ega':
        return redirect('main')

    try:
        from .click_views import CLICK_MERCHANT_ID, CLICK_SERVICE_ID

        payment_link = create_billing_payment_link(
            request.company,
            service_id=CLICK_SERVICE_ID,
            merchant_id=CLICK_MERCHANT_ID,
        )
        if payment_link.status == 'created' and payment_link.opened_at is None:
            messages.success(request, "To'lov silkasini tayyorlab qo'ydik. U billing sahifasida saqlanadi.")
    except ValueError as exc:
        messages.warning(request, str(exc))

    return redirect('billing_page')


@login_required(login_url='login')
@require_POST
def save_savdogar_contract(request):
    if request.user.type != 'ega':
        return redirect('main')

    contract_text = (request.POST.get('savdogar_contract_text') or '').strip()
    if not contract_text:
        messages.error(request, "Savdogar shartnoma matni bo'sh bo'lishi mumkin emas.")
        return redirect('billing_page')

    request.company.savdogar_contract_text = contract_text
    request.company.save(update_fields=['savdogar_contract_text'])
    messages.success(request, "Savdogar shartnoma matni saqlandi. Tizim qoidalari shartnomaga avtomatik qo'shiladi.")
    return redirect(request.POST.get('next') or 'savdogar_contract')


def get_savdogar_sales_queryset(company):
    return Savdo.objects.filter(company=company).filter(
        Q(savdogar__isnull=False) | Q(yetkazib_beruvchi__user__type='savdogar')
    ).select_related('haridor_dukon', 'yetkazib_beruvchi', 'yetkazib_beruvchi__user', 'savdogar')


@login_required(login_url='login')
def savdogar_admin_dashboard(request):
    if request.user.type != 'ega':
        return redirect('main')

    flags = get_feature_flags(request.company)
    sales = get_savdogar_sales_queryset(request.company)
    nasiya_sales = sales.filter(st='nasiya')
    unpaid_nasiya = nasiya_sales.filter(tulandi=False)
    sellers = User.objects.filter(company=request.company, type='savdogar').order_by('tuliq_ismi', 'username')
    missing_docs = sales.filter(
        Q(contract_pdf='') | Q(contract_pdf__isnull=True) |
        Q(signed_contract_scan='') | Q(signed_contract_scan__isnull=True) |
        Q(customer_passport_image='') | Q(customer_passport_image__isnull=True)
    )

    context = {
        'has_savdogar_sales': flags.get('has_savdogar_sales'),
        'contract_ready': bool((request.company.savdogar_contract_text or '').strip()),
        'sellers': sellers,
        'sales_count': sales.count(),
        'sales_total': sales.aggregate(total=Sum('summa'))['total'] or 0,
        'nasiya_count': nasiya_sales.count(),
        'unpaid_nasiya_count': unpaid_nasiya.count(),
        'missing_docs_count': missing_docs.count(),
        'recent_sales': sales.order_by('-vaqt_sana')[:10],
    }
    return render(request, 'savdogar_admin_dashboard.html', context)


@login_required(login_url='login')
def savdogar_contract_page(request):
    if request.user.type != 'ega':
        return redirect('main')

    flags = get_feature_flags(request.company)
    return render(request, 'savdogar_contract.html', {
        'has_savdogar_sales': flags.get('has_savdogar_sales'),
        'savdogar_contract_text': request.company.savdogar_contract_text or DEFAULT_SAVDOGAR_CONTRACT_TEMPLATE,
        'credit_rules_note': request.company.credit_rules_note,
        'system_credit_rules': SYSTEM_CREDIT_RULES,
    })


def _pdf_escape(value):
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_text_width(value, size=12):
    return len(str(value)) * size * 0.48


def _wrap_pdf_text(value, max_width, size=12):
    words = str(value).split()
    lines = []
    current = ""
    for word in words:
        proposed = f"{current} {word}".strip()
        if current and _pdf_text_width(proposed, size) > max_width:
            lines.append(current)
            current = word
        else:
            current = proposed
    if current:
        lines.append(current)
    return lines or [""]


def _is_contract_heading(line):
    text = line.strip().lstrip("-").strip()
    if not text:
        return False
    if text.startswith(("Shartnoma N:", "Firma:", "Xaridor:", "Sana:", "3 oy", "6 oy", "9 oy", "12 oy", "Tizim qoidasi:")):
        return False
    if text.isupper() and "SHARTNOMASI" in text:
        return False
    if len(text) > 70 or text.endswith((".", ",", ";", ":")):
        return False
    return len(text.split()) <= 5


def _contract_pdf_rows(text):
    rows = []
    section_no = 0
    for raw_line in str(text).splitlines():
        line = raw_line.strip()
        if not line:
            rows.append({"kind": "space"})
            continue

        clean_line = line.lstrip("-").strip()
        if clean_line.isupper() and "SHARTNOMASI" in clean_line:
            rows.append({"kind": "title", "text": clean_line})
        elif line.startswith(("Shartnoma N:", "Firma:", "Xaridor:", "Sana:")):
            rows.append({"kind": "meta", "text": line})
        elif _is_contract_heading(line):
            section_no += 1
            rows.append({"kind": "heading", "text": f"{section_no}. {clean_line}"})
        elif line.startswith("Tizim qoidasi:"):
            rows.append({"kind": "heading", "text": "Tizim ishlash qoidasi"})
            rows.append({"kind": "paragraph", "text": line, "indent": True})
        else:
            rows.append({"kind": "paragraph", "text": clean_line, "indent": line.startswith("-")})

    rows.extend([
        {"kind": "space"},
        {"kind": "signature_title", "text": "Tomonlar tasdig'i"},
        {"kind": "signature"},
    ])
    return rows


def _build_text_pdf(title, text):
    page_commands = [[]]
    y = 805

    def ensure_space(height=22):
        nonlocal y
        if y < 70 + height:
            page_commands.append([])
            y = 805

    def draw_line(value, x=56, size=12, font="F1", align="left"):
        nonlocal y
        ensure_space(size + 10)
        text_value = _pdf_escape(value)
        draw_x = x
        if align == "center":
            draw_x = max(56, (595 - _pdf_text_width(value, size)) / 2)
        elif align == "right":
            draw_x = max(56, 535 - _pdf_text_width(value, size))
        page_commands[-1].append(f"BT /{font} {size} Tf 1 0 0 1 {draw_x:.2f} {y:.2f} Tm ({text_value}) Tj ET")
        y -= size + 7

    for row in _contract_pdf_rows(text):
        kind = row["kind"]
        if kind == "space":
            y -= 12
        elif kind == "meta":
            draw_line(row["text"], x=56, size=11, font="F1")
        elif kind == "title":
            y -= 10
            draw_line(row["text"], x=56, size=15, font="F2", align="center")
            y -= 8
        elif kind == "heading":
            y -= 8
            draw_line(row["text"], x=56, size=12, font="F2")
        elif kind == "signature_title":
            y -= 10
            draw_line(row["text"], x=56, size=12, font="F2")
            y -= 4
        elif kind == "signature":
            ensure_space(75)
            page_commands[-1].append(f"BT /F2 11 Tf 1 0 0 1 56 {y:.2f} Tm (Xaridor imzosi) Tj ET")
            page_commands[-1].append(f"BT /F2 11 Tf 1 0 0 1 330 {y:.2f} Tm (Firma muhri va imzosi) Tj ET")
            y -= 32
            page_commands[-1].append(f"BT /F1 12 Tf 1 0 0 1 56 {y:.2f} Tm (____________________________) Tj ET")
            page_commands[-1].append(f"BT /F1 12 Tf 1 0 0 1 330 {y:.2f} Tm (____________________________) Tj ET")
            y -= 22
            page_commands[-1].append(f"BT /F1 10 Tf 1 0 0 1 56 {y:.2f} Tm (F.I.Sh. va imzo) Tj ET")
            page_commands[-1].append(f"BT /F1 10 Tf 1 0 0 1 330 {y:.2f} Tm (Firma vakili, muhr) Tj ET")
            y -= 18
        else:
            x = 76 if row.get("indent") else 56
            max_width = 482 if row.get("indent") else 500
            for wrapped in _wrap_pdf_text(row["text"], max_width=max_width, size=11):
                draw_line(wrapped, x=x, size=11, font="F1")
            y -= 4

    objects = []
    page_ids = []

    def add_obj(body):
        objects.append(body)
        return len(objects)

    regular_font_id = add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    bold_font_id = add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    for commands in page_commands:
        stream = "\n".join(commands).encode("latin-1", "replace")
        content_id = add_obj(f"<< /Length {len(stream)} >>\nstream\n{stream.decode('latin-1')}\nendstream")
        page_id = add_obj(
            f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {regular_font_id} 0 R /F2 {bold_font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    pages_id = len(objects) + 1
    for page_id in page_ids:
        objects[page_id - 1] = objects[page_id - 1].replace("/Parent 0 0 R", f"/Parent {pages_id} 0 R")
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    add_obj(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>")
    catalog_id = add_obj(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n{body}\nendobj\n".encode("latin-1", "replace"))
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R /Title ({_pdf_escape(title)}) >>\n"
        f"startxref\n{xref}\n%%EOF".encode("latin-1", "replace")
    )
    return bytes(pdf)


@login_required(login_url='login')
def savdogar_contract_download(request):
    if request.user.type not in ['savdogar', 'ega']:
        return redirect('main')
    if request.user.type == 'savdogar' and not get_feature_flags(request.company).get('has_savdogar_sales'):
        messages.error(request, "Savdogar savdo moduli tarifda ochilmagan.")
        return redirect('main')

    customer = (request.GET.get('customer') or '').strip()
    if not customer:
        messages.error(request, "Shartnoma yuklash uchun mijoz ism-familyasini kiriting.")
        return redirect('sotish')

    payment_type = request.GET.get('payment_type')
    if payment_type not in ['naqd', 'karta', 'nasiya']:
        messages.error(request, "Shartnoma uchun to'lov turini tanlang.")
        return redirect('sotish')
    try:
        requested_contract_number = int(request.GET.get('contract_number') or 0)
    except ValueError:
        requested_contract_number = 0
    if requested_contract_number != request.company.savdogar_contract_next_number:
        messages.error(request, "Shartnoma raqami yangilangan. Sahifani qayta ochib, shartnomani qayta yuklab oling.")
        return redirect('sotish')

    try:
        items = json.loads(request.GET.get('items') or '[]')
    except json.JSONDecodeError:
        items = []
    if not items:
        messages.error(request, "Shartnoma uchun kamida bitta mahsulot tanlang.")
        return redirect('sotish')

    base_summa = sum(float(item.get('qty') or 0) * float(item.get('price') or 0) for item in items)
    months = None
    markup = 0
    total = base_summa
    down_payment = 0
    if payment_type == 'nasiya':
        try:
            months = int(request.GET.get('term') or 0)
            total, markup = calculate_credit_total(base_summa, months)
            down_payment = float(request.GET.get('down_payment') or 0)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect('sotish')
        if down_payment < 0 or down_payment > total:
            messages.error(request, "Boshlang'ich to'lov yakuniy summadan katta bo'lishi mumkin emas.")
            return redirect('sotish')

    text = build_contract_draft(
        request.company,
        customer,
        contract_number=requested_contract_number,
        payment_type=payment_type,
        items=items,
        base_summa=base_summa,
        total=total,
        months=months,
        markup=markup,
        down_payment=down_payment,
    )
    pdf_bytes = _build_text_pdf("Savdogar shartnomasi", text)
    filename = f"savdogar_shartnoma_{customer[:40].replace(' ', '_')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required(login_url='login')
def savdogar_sales_page(request):
    if request.user.type != 'ega':
        return redirect('main')

    sales = get_savdogar_sales_queryset(request.company).order_by('-vaqt_sana')
    seller_id = request.GET.get('seller')
    payment_type = request.GET.get('payment')

    if seller_id:
        sales = sales.filter(Q(savdogar_id=seller_id) | Q(yetkazib_beruvchi__user_id=seller_id))
    if payment_type in ['naqd', 'karta', 'nasiya']:
        sales = sales.filter(st=payment_type)

    paginator = Paginator(sales, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'savdogar_sales.html', {
        'page_obj': page_obj,
        'sellers': User.objects.filter(company=request.company, type='savdogar').order_by('tuliq_ismi', 'username'),
        'seller_id': seller_id or '',
        'payment_type': payment_type or '',
        'total_amount': sales.aggregate(total=Sum('summa'))['total'] or 0,
        'sales_count': sales.count(),
    })


@login_required(login_url='login')
def savdogar_admin_credit_page(request):
    if request.user.type != 'ega':
        return redirect('main')

    sales = get_savdogar_sales_queryset(request.company).filter(st='nasiya').order_by('-vaqt_sana')
    seller_id = request.GET.get('seller')
    if seller_id:
        sales = sales.filter(Q(savdogar_id=seller_id) | Q(yetkazib_beruvchi__user_id=seller_id))

    rows = []
    for sale in sales:
        paid = NasiyaTolov.objects.filter(savdo=sale).aggregate(total=Sum('tolov_summasi'))['total'] or 0
        remaining = max(float(sale.summa or 0) - float(paid), 0)
        rows.append({
            'sale': sale,
            'paid': paid,
            'remaining': remaining,
            'overdue': bool(sale.credit_due_date and sale.credit_due_date < timezone.localdate() and remaining > 0),
        })

    return render(request, 'savdogar_admin_credit.html', {
        'rows': rows,
        'sellers': User.objects.filter(company=request.company, type='savdogar').order_by('tuliq_ismi', 'username'),
        'seller_id': seller_id or '',
        'open_count': sum(1 for row in rows if row['remaining'] > 0),
        'debt_total': sum(row['remaining'] for row in rows),
    })


@login_required(login_url='login')
def savdogar_admin_products_page(request):
    if request.user.type != 'ega':
        return redirect('main')

    products = Mahsulot.objects.filter(company=request.company, is_savdogar_product=True).order_by('nomi')
    return render(request, 'savdogar_admin_products.html', {'products': products})


@login_required(login_url='login')
def savdogar_admin_analytics_page(request):
    if request.user.type != 'ega':
        return redirect('main')

    sales = list(get_savdogar_sales_queryset(request.company).order_by('-vaqt_sana')[:1000])
    analytics_payload = _savdogar_analytics_payload(sales)
    total_amount = sum(float(sale.summa or 0) for sale in sales)
    return render(request, 'savdogar_admin_analytics.html', {
        'analytics_json': json.dumps(analytics_payload),
        'sales_count': len(sales),
        'total_amount': total_amount,
        'avg_sale': total_amount / len(sales) if sales else 0,
        'nasiya_count': sum(1 for sale in sales if sale.st == 'nasiya'),
    })


def _get_savdogar_profile(request):
    return get_object_or_404(YetkazibBeruvchi, user=request.user, company=request.company)


def _parse_savdo_items(smm):
    items = []
    for raw_item in (smm or '').split(','):
        raw_item = raw_item.strip()
        if not raw_item:
            continue
        parts = raw_item.rsplit(' ', 2)
        if len(parts) != 3:
            continue
        name, qty, price = parts
        try:
            qty_value = float(qty)
            price_value = float(price)
        except ValueError:
            continue
        items.append({
            'name': name,
            'qty': qty_value,
            'price': price_value,
            'total': qty_value * price_value,
        })
    return items


def _savdogar_sales_for_user(request):
    seller = _get_savdogar_profile(request)
    return Savdo.objects.filter(
        company=request.company,
        yetkazib_beruvchi=seller,
    ).select_related('haridor_dukon', 'yetkazib_beruvchi', 'savdogar').order_by('-vaqt_sana')


def _credit_rows_for_sales(sales, today=None):
    today = today or timezone.localdate()
    sales = list(sales)
    paid_by_sale = {
        row['savdo_id']: row['total'] or 0
        for row in NasiyaTolov.objects.filter(savdo__in=sales)
        .values('savdo_id')
        .annotate(total=Sum('tolov_summasi'))
    }
    rows = []
    for sale in sales:
        paid = paid_by_sale.get(sale.id, 0)
        remaining = max(float(sale.summa or 0) - float(paid), 0)
        term_months = int(sale.credit_term_months or 0)
        sale_date = timezone.localtime(sale.vaqt_sana).date() if sale.vaqt_sana else today
        monthly_due = (float(sale.summa or 0) / term_months) if term_months else 0
        next_due_date = sale.credit_due_date
        overdue_amount = 0

        if term_months and monthly_due:
            for month_index in range(1, term_months + 1):
                due_date = add_months(sale_date, month_index)
                expected_paid = monthly_due * month_index
                if float(paid) + 0.01 < expected_paid:
                    next_due_date = due_date
                    overdue_amount = max(expected_paid - float(paid), 0) if due_date < today else 0
                    break

        days_to_due = (next_due_date - today).days if next_due_date else None
        rows.append({
            'sale': sale,
            'paid': paid,
            'remaining': remaining,
            'next_due_date': next_due_date,
            'overdue_amount': overdue_amount,
            'days_to_due': days_to_due,
            'overdue': bool(days_to_due is not None and days_to_due < 0 and remaining > 0),
            'due_soon': bool(days_to_due is not None and 0 <= days_to_due <= 7 and remaining > 0),
        })
    return rows


def _savdogar_analytics_payload(sales):
    today = timezone.localdate()
    day_labels = []
    daily_totals = []
    daily_counts = []
    for offset in range(6, -1, -1):
        day = today - dt.timedelta(days=offset)
        day_sales = [sale for sale in sales if timezone.localtime(sale.vaqt_sana).date() == day]
        day_labels.append(day.strftime('%d.%m'))
        daily_totals.append(round(sum(float(sale.summa or 0) for sale in day_sales), 2))
        daily_counts.append(len(day_sales))

    payment_totals = {'naqd': 0, 'karta': 0, 'nasiya': 0}
    payment_counts = {'naqd': 0, 'karta': 0, 'nasiya': 0}
    product_totals = defaultdict(float)
    product_qty = defaultdict(float)
    customer_totals = defaultdict(float)

    for sale in sales:
        payment_totals[sale.st] = payment_totals.get(sale.st, 0) + float(sale.summa or 0)
        payment_counts[sale.st] = payment_counts.get(sale.st, 0) + 1
        customer_name = sale.haridor_dukon.nomi if sale.haridor_dukon else sale.oluvchining_ismi
        customer_totals[customer_name or "Noma'lum"] += float(sale.summa or 0)
        for item in _parse_savdo_items(sale.smm):
            product_totals[item['name']] += item['total']
            product_qty[item['name']] += item['qty']

    top_products = sorted(product_totals.items(), key=lambda item: item[1], reverse=True)[:7]
    top_customers = sorted(customer_totals.items(), key=lambda item: item[1], reverse=True)[:7]

    return {
        'day_labels': day_labels,
        'daily_totals': daily_totals,
        'daily_counts': daily_counts,
        'payment_labels': ["Naqd", "Karta", "Nasiya"],
        'payment_totals': [round(payment_totals.get(key, 0), 2) for key in ['naqd', 'karta', 'nasiya']],
        'payment_counts': [payment_counts.get(key, 0) for key in ['naqd', 'karta', 'nasiya']],
        'product_labels': [item[0] for item in top_products],
        'product_totals': [round(item[1], 2) for item in top_products],
        'product_qty': [round(product_qty[item[0]], 2) for item in top_products],
        'customer_labels': [item[0] for item in top_customers],
        'customer_totals': [round(item[1], 2) for item in top_customers],
    }


@login_required(login_url='login')
def savdogar_my_sales(request):
    if request.user.type != 'savdogar':
        return redirect('main')

    sales = _savdogar_sales_for_user(request)
    payment_type = request.GET.get('payment', '')
    query = (request.GET.get('q') or '').strip()
    if payment_type in ['naqd', 'karta', 'nasiya']:
        sales = sales.filter(st=payment_type)
    if query:
        sales = sales.filter(Q(oluvchining_ismi__icontains=query) | Q(smm__icontains=query))

    paginator = Paginator(sales, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'savdogar_my_sales.html', {
        'page_obj': page_obj,
        'payment_type': payment_type,
        'query': query,
        'sales_count': sales.count(),
        'total_amount': sales.aggregate(total=Sum('summa'))['total'] or 0,
    })


@login_required(login_url='login')
def savdogar_my_credit(request):
    if request.user.type != 'savdogar':
        return redirect('main')

    sales = _savdogar_sales_for_user(request).filter(st='nasiya', tulandi=False)
    rows = _credit_rows_for_sales(sales)

    return render(request, 'savdogar_my_credit.html', {
        'rows': rows,
        'open_count': sum(1 for row in rows if row['remaining'] > 0),
        'debt_total': sum(row['remaining'] for row in rows),
        'due_soon_count': sum(1 for row in rows if row['due_soon']),
        'overdue_count': sum(1 for row in rows if row['overdue']),
    })


@login_required(login_url='login')
def savdogar_my_products(request):
    if request.user.type != 'savdogar':
        return redirect('main')

    products = Mahsulot.objects.filter(company=request.company, is_savdogar_product=True).order_by('nomi')
    return render(request, 'savdogar_my_products.html', {'products': products})


@login_required(login_url='login')
def savdogar_analytics_page(request):
    if request.user.type != 'savdogar':
        return redirect('main')

    sales = list(_savdogar_sales_for_user(request)[:500])
    analytics_payload = _savdogar_analytics_payload(sales)
    total_amount = sum(float(sale.summa or 0) for sale in sales)
    return render(request, 'savdogar_analytics.html', {
        'analytics_json': json.dumps(analytics_payload),
        'sales_count': len(sales),
        'total_amount': total_amount,
        'avg_sale': total_amount / len(sales) if sales else 0,
        'nasiya_count': sum(1 for sale in sales if sale.st == 'nasiya'),
    })


@login_required(login_url='login')
def open_billing_link(request, token):
    if request.user.type != 'ega':
        return redirect('main')

    payment_link = get_object_or_404(BillingPaymentLink, token=token, company=request.company)
    try:
        payment_link = consume_billing_payment_link(payment_link)
    except ValueError as exc:
        messages.warning(request, str(exc))
        return redirect('billing_page')

    return redirect(payment_link.click_url)

@login_required(login_url='login')
def select_plan_page(request):
    """Tarif o'zgartirish sahifasi"""
    if request.user.type != 'ega':
        return redirect('main')

    company = request.company
    lock_reason = get_tariff_lock_reason(company)

    # Faqat tarif so'rovi (trial emas) kutilayotgan bo'lsa blok qilamiz
    pending_request = PlanRequest.objects.filter(company=company, status='pending', is_trial=False).exists()

    # Trial eligibility
    can_request_trial = False
    trial_pending = PlanRequest.objects.filter(company=company, is_trial=True, status='pending').exists()
    days_since_creation = (timezone.now() - company.created_at).days
    if (
        not company.has_used_trial
        and days_since_creation <= 10
        and not trial_pending
        and not company.is_on_trial
        and not lock_reason
    ):
        can_request_trial = True

    plans = [plan for plan in Plan.objects.filter(is_active=True).order_by('price') if plan_is_visible_to_owner(plan)]
    current_staff_count = User.objects.filter(company=company).exclude(type='ega').count()
    return render(request, 'select_plan_page.html', {
        'plans': plans,
        'backup_choices': BACKUP_CHOICES,
        'can_request_trial': can_request_trial,
        'trial_pending': trial_pending,
        'days_since_creation': days_since_creation,
        'current_staff_count': current_staff_count,
        'lock_reason': lock_reason,
        'pending_request': pending_request,
    })

@login_required(login_url='login')
def main(request):
    payload={}
    user=request.user
    
    if user.type in ['pazanda', 'ishlab_chiqaruvchi']:
        now = timezone.localtime()
        today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
        today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))
        try:
            pz = Pazanda.objects.get(user=request.user, company=request.company)
        except Pazanda.DoesNotExist:
            messages.error(request, "Profil topilmadi. Administrator bilan bog'laning.")
            return redirect('login')
        payload['sorovlar'] = YuklamaSorov.objects.filter(company=request.company, pazanda=pz, mode='waiting').all()
        payload['zaxira_mahsulotlar'] = _pazanda_mahsulotlar_qs(request.company, pz)
        payload['is_agent_company'] = bool(request.company.custom_desktop_agent_stations)
        if payload['is_agent_company']:
            # Agent firmalarida "Material So'rash"/"Miqdor Qo'shish" o'rniga
            # "Vazifalar paneli" ishlatiladi (103-108 qadamlar) — bandlik/
            # bajarish har doim Desktop Agent orqali, veb sahifada faqat
            # ma'lumot uchun ko'rsatiladi.
            payload['open_tasks'] = ProductionTask.objects.filter(
                company=request.company, status='open',
            ).select_related('mahsulot').order_by('sana', '-created_at')[:20]
            my_tasks = list(ProductionTask.objects.filter(
                company=request.company, pazanda=pz,
            ).exclude(status='open').select_related('mahsulot').order_by('-created_at')[:20])
            for t in my_tasks:
                t.produced_count = task_service.task_progress(t)
                # "Tugatish" (erta yopish, shtraf bilan) tugmasi faqat
                # yorliqlar Desktop Agent'da haqiqatda chop etilgandan
                # keyin ko'rsatilishi kerak — aks holda pazanda "Ish
                # bitdi"ni bosgach, hali stansiyaga borib skanerlashdan
                # oldin bexosdan "Tugatish"ni bosib, 0 dona uchun shtraf
                # olishi mumkin (real holatda sodir bo'lgan bug).
                mq = t.miqdor_qoshishlar.first() if t.status == 'producing' else None
                t.labels_printed = bool(mq and mq.labels_printed)
            payload['my_tasks'] = my_tasks
            # Sanoq/hajm (dona/litr) komponentlar — Desktop Agent'da EMAS,
            # shu yerda bitta tugma bilan tasdiqlanadi (kioskda sichqoncha
            # yo'q, avtomatik 600ms tasdiq esa o'qishga ulgurmasdan
            # g'oyib bo'lardi — real ishlab chiqarishda aniqlangan xato).
            pending_pickups = list(
                TaskMaterialPickup.objects.filter(
                    task__company=request.company, task__pazanda=pz,
                    task__status='claimed', tasdiqlangan=False,
                ).select_related('komponent', 'komponent__turi', 'task', 'task__mahsulot')
            )
            payload['pending_pickups'] = [
                p for p in pending_pickups
                if not task_service.is_weighable_birlik(p.komponent.turi.nomi if p.komponent.turi else '')
            ]
            # Ishlab chiqaruvchi o'zi vazifa yaratishi uchun — faqat BOM
            # (retsept) kiritilgan mahsulotlar tanlanishi mumkin.
            bom_mahsulot_ids = MahsulotRetsept.objects.filter(
                company=request.company,
            ).values_list('mahsulot_id', flat=True).distinct()
            payload['task_mahsulotlar'] = Mahsulot.objects.filter(
                company=request.company, id__in=bom_mahsulot_ids,
                warehouse_type='finished', mahsulot_turi='ishlab_chiqariladigan',
            ).order_by('nomi')
            # Printer holati (qog'oz tugagan/oflayn/xato) tekshiruvi orqali
            # HAQIQATAN chop etilmagan deb aniqlangan QR-yorliqlar — Desktop
            # Agentda keyingi badge skanida qayta taklif qilinadi, bu yerda
            # esa ogohlantirish sifatida ko'rsatiladi.
            payload['failed_print_serials_count'] = Serial.objects.filter(
                company=request.company, batch__pazanda=pz, chop_etilmadi=True,
            ).count()
        else:
            payload['material_requests'] = ProductionMaterialRequest.objects.filter(
                company=request.company, producer=pz,
            ).prefetch_related('miqdor_qoshishlar')[:8]
        zapros=MiqdorQoshish.objects.filter(company=request.company, pazanda=pz,vaqt_sana__range=(today_start, today_end)).all()
        payload['qms']=len(zapros)
        payload['kunlik_miqdorlar'] = zapros
        return render(request, 'pazanda_dashboard.html',payload)
    elif user.type == 'omborchi':
        pending_material_requests = ProductionMaterialRequest.objects.filter(
            company=request.company,
            status='waiting',
            material__warehouse_type='semi_finished',
        ).select_related('producer', 'producer__user', 'material', 'material__turi', 'target_product')

        if request.method == 'POST':
            with transaction.atomic():
                req = ProductionMaterialRequest.objects.select_for_update().select_related('material').get(
                    id=request.POST.get('material_request_id'),
                    company=request.company,
                    status='waiting',
                    material__warehouse_type='semi_finished',
                )
                material = req.material
                old_qty = material.miqdori
                if 'approve' in request.POST:
                    if old_qty < req.qty:
                        messages.error(request, f"{material.nomi} omborda yetarli emas. Qoldiq: {old_qty:g} {material.turi.nomi}.")
                        return redirect('main')
                    material.miqdori = old_qty - req.qty
                    material.save(update_fields=['miqdori'])
                    req.status = 'approved'
                    event_type = 'RAW_APPROVED'
                    delta = -req.qty
                    messages.success(request, "Material so'rovi tasdiqlandi va ombor qoldig'i kamaytirildi.")
                else:
                    req.status = 'rejected'
                    event_type = 'RAW_REJECTED'
                    delta = 0
                    messages.success(request, "Material so'rovi rad etildi.")
                req.reviewed_by = request.user
                req.reviewed_at = timezone.now()
                req.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
                StockHistory.objects.create(
                    actor_user=request.user,
                    company=request.company,
                    mahsulot=material,
                    event_type=event_type,
                    old_qty=old_qty,
                    new_qty=material.miqdori,
                    delta=delta,
                )
            return redirect('main')

        payload.update({
            'materials': Mahsulot.objects.filter(company=request.company, warehouse_type='semi_finished').order_by('nomi'),
            'pending_material_requests': pending_material_requests,
            'omborlar': Ombor.objects.filter(company=request.company).order_by('nomi'),
        })
        return render(request, 'warehouse_dashboard.html', payload)
    elif user.type == 'savdogar':
        seller = get_object_or_404(YetkazibBeruvchi, user=request.user, company=request.company)
        now = timezone.localtime()
        today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
        today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))

        today_sales = Savdo.objects.filter(
            company=request.company,
            yetkazib_beruvchi=seller,
            vaqt_sana__range=(today_start, today_end)
        )
        nasiya_sales = Savdo.objects.filter(
            company=request.company,
            yetkazib_beruvchi=seller,
            st='nasiya',
            tulandi=False
        )
        credit_rows = _credit_rows_for_sales(nasiya_sales, today=now.date())
        open_credit_rows = [row for row in credit_rows if row['remaining'] > 0]
        due_soon_rows = [row for row in open_credit_rows if row['due_soon']]
        overdue_rows = [row for row in open_credit_rows if row['overdue']]
        analytics_sales = list(Savdo.objects.filter(
            company=request.company,
            yetkazib_beruvchi=seller,
            vaqt_sana__gte=timezone.now() - dt.timedelta(days=7),
        ).select_related('haridor_dukon', 'yetkazib_beruvchi', 'savdogar').order_by('-vaqt_sana'))

        payload.update({
            'seller': seller,
            'today_sales': today_sales.order_by('-vaqt_sana')[:8],
            'today_sales_count': today_sales.count(),
            'today_sales_sum': today_sales.aggregate(total=Sum('summa'))['total'] or 0,
            'nasiya_count': len(open_credit_rows),
            'nasiya_debt': sum(row['remaining'] for row in open_credit_rows),
            'credit_due_soon_count': len(due_soon_rows),
            'credit_overdue_count': len(overdue_rows),
            'credit_due_soon_rows': due_soon_rows[:5],
            'credit_overdue_rows': overdue_rows[:5],
            'savdogar_contract_ready': bool((request.company.savdogar_contract_text or '').strip()),
            'zaxira_mahsulotlar': Mahsulot.objects.filter(company=request.company, is_savdogar_product=True).order_by('nomi'),
            'lnmahs': Mahsulot.objects.filter(company=request.company, is_savdogar_product=True).count(),
            'analytics_json': json.dumps(_savdogar_analytics_payload(analytics_sales)),
        })
        return render(request, 'savdogar_dashboard.html', payload)
    elif user.type == 'yetkazib_beruvchi':
        try:
            yt_obj = YetkazibBeruvchi.objects.get(user=request.user, company=request.company)
        except YetkazibBeruvchi.DoesNotExist:
            messages.error(request, "Profil topilmadi. Administrator bilan bog'laning.")
            return redirect('login')
        if request.method == 'GET':
            yuklamalar = mahsulotlar_miqdori(yt_obj.mahsulotlar) or []

            payload['yuklamalar'] = yuklamalar
            # Yetkazib beruvchiga faqat sotuvga chiqadigan tayyor mahsulotlar
            # ko'rsatiladi — xom ashyo/yarim tayyor (semi_finished) uning
            # ishiga aloqasi yo'q va ro'yxatni chalg'itadi.
            mahs=Mahsulot.objects.filter(company=request.company, warehouse_type='finished')
            payload['zaxira_mahsulotlar'] = mahs
            payload['lnmahs']=len(mahs)
            payload['is_agent_company'] = bool(request.company.custom_desktop_agent_stations)

            now = timezone.localtime()
            today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
            today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))

            reqyuklama = YuklamaSorov.objects.filter(company=request.company, user=yt_obj, mode="waiting").all()
            payload['reqyuklama'] = reqyuklama
            savdo=Savdo.objects.filter(company=request.company, yetkazib_beruvchi=yt_obj, vaqt_sana__range=(today_start, today_end)).all()
            payload['savdo'] = savdo
            nfs=yetkazuvchi_mahsulot_filter(savdo)
            payload['nfs'] = nfs
            return render(request, 'yetkazuvchi_dashboard.html',payload)
        elif request.method == 'POST':
            if 'sorov_submit' in request.POST:
                # Agent firmalarda yetkazib beruvchi kerakli mahsulotlarni
                # dashboardda oldindan so'raydi (zayavka) — bir formada bir
                # nechta mahsulot birdan (har biriga alohida miqdor). Keyin
                # stansiyada aynan shu so'ralgan mahsulotlarning Serial QR
                # kodlarini skanerlab oladi; so'ralmagan mahsulot skani
                # agentda rad etiladi (`agent_scan_delivery_serial`).
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                yaratilgan_matn = []
                yaratilgan_json = []
                ogohlantirishlar = []
                for m in Mahsulot.objects.filter(company=request.company, warehouse_type='finished'):
                    try:
                        sorov_miqdor = float(request.POST.get(f'sorov_miqdor_{m.id}') or 0)
                    except ValueError:
                        continue
                    if sorov_miqdor <= 0:
                        continue
                    if sorov_miqdor > m.miqdori:
                        ogohlantirishlar.append(f"{m.nomi} uchun omborda faqat {m.miqdori:g} {m.turi} bor — so'rov o'tkazib yuborildi.")
                        continue
                    if YuklamaSorov.objects.filter(
                        company=request.company, user=yt_obj, mahsulot=m, mode='waiting',
                    ).exists():
                        ogohlantirishlar.append(f"{m.nomi} uchun kutilayotgan so'rovingiz allaqachon bor — o'tkazib yuborildi.")
                        continue
                    YuklamaSorov.objects.create(
                        company=request.company, user=yt_obj,
                        mahsulot=m, miqdor=sorov_miqdor, mode='waiting',
                    )
                    yaratilgan_matn.append(f"{sorov_miqdor:g} {m.turi} {m.nomi}")
                    yaratilgan_json.append({'mahsulot_id': m.id, 'mahsulot': m.nomi, 'miqdor': f"{sorov_miqdor:g}", 'birlik': m.turi.nomi})

                if yaratilgan_matn:
                    send_ws_notification(
                        request.company.subdomain, "Yuklama so'rovi",
                        f"{yt_obj.tuliq_ismi} so'radi: {', '.join(yaratilgan_matn)}.",
                        "info",
                    )
                    ok = True
                    msg = f"So'rov yuborildi ({len(yaratilgan_matn)} mahsulot) — endi stansiyada badge'ingizni skanerlab, QR kodlarni skanerlang."
                else:
                    ok = False
                    msg = ogohlantirishlar[0] if ogohlantirishlar else "Hech qanday miqdor kiritilmadi."

                # AJAX (fetch) orqali yuborilgan bo'lsa — sahifa umuman
                # qayta yuklanmasin, faqat JSON javob (frontend DOM'ni o'zi
                # yangilaydi). Oddiy forma-submit (JS o'chirilgan yoki eski
                # brauzer) hamon eski redirect+messages yo'lidan ishlaydi.
                if is_ajax:
                    return JsonResponse({
                        'ok': ok, 'message': msg,
                        'ogohlantirishlar': ogohlantirishlar,
                        'yaratilgan': yaratilgan_json,
                    })

                if ok:
                    messages.success(request, msg)
                for w in ogohlantirishlar:
                    messages.error(request, w)
                return redirect('main')
            if 'yk_id' in request.POST:
                yk_id=request.POST.get('yk_id')
               
                if 'accept' in yk_id:
                    yk_id=yk_id.replace('accept','')
                    # Desktop Agent ishlatuvchi firmalarda bu yerdan
                    # tasdiqlash butunlay yopiladi — aks holda yetkazib
                    # beruvchi/savdogar hech qanday fizik nazoratsiz
                    # ("o'zi so'rab-o'zi tasdiqlaydi") o'zining yuklamasini
                    # o'zi tasdiqlab yuborishi mumkin edi. Bunday firmalarda
                    # tasdiqlash faqat Desktop Agent'da Serial QR skanerlab
                    # amalga oshadi (`agent_finalize_yuklama`).
                    if request.company.custom_desktop_agent_stations > 0:
                        messages.error(
                            request,
                            "Bu firmada yuklama faqat Desktop Agent orqali (Serial QR skanerlab) tasdiqlanadi."
                        )
                        return redirect('main')
                    # Refactored to use Service
                    success, message = approve_yuklama_sorov_service(yk_id, request.user)
                    if success:
                        messages.success(request, message)
                    else:
                        messages.error(request, message)

                elif 'reject' in yk_id:
                    yk_id=yk_id.replace('reject','')
                    yk=YuklamaSorov.objects.get(id=yk_id)
                    yk.mode='rejected'
                    yk.tasdiq=True
                    yk.save()
                    # Activity log
                    AmalLog.objects.create(
                        user=request.user,
                        amal_shifri=f"yuklama_rad|{yk.mahsulot.nomi}|{yk.miqdor}"
                    )
                
                return redirect('main')
            yuklamalar = mahsulotlar_miqdori(yt_obj.mahsulotlar) or []
            savdo=Savdo.objects.filter(company=request.company, yetkazib_beruvchi=yt_obj)
            payload['savdo'] = savdo
            nfs=yetkazuvchi_mahsulot_filter(savdo)
            payload['nfs'] = nfs

            payload['yuklamalar'] = yuklamalar
            payload['is_agent_company'] = bool(request.company.custom_desktop_agent_stations)
            now = timezone.localtime()
            today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
            today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))

            reqyuklama = YuklamaSorov.objects.filter(company=request.company, user=yt_obj, mode="waiting").all()
            savdo=Savdo.objects.filter(company=request.company, yetkazib_beruvchi=yt_obj, vaqt_sana__range=(today_start, today_end)).all()
            payload['savdo'] = savdo
            # reqyuklama=YuklamaSorov.objects.filter(user=YetkazibBeruvchi.objects.get(user=request.user),tasdiq=False, mode='waiting',sana=dt.date.today() ).all()
            payload['reqyuklama'] = reqyuklama
            mahs=Mahsulot.objects.filter(company=request.company, warehouse_type='finished')
            payload['zaxira_mahsulotlar'] = mahs

            return render(request, 'yetkazuvchi_dashboard.html',payload)
            
    
    mahs = Mahsulot.objects.filter(company=request.company).order_by('nomi')[:6]  # Faqat 6 ta
    
    # Jami sonlar
    jami_hodimlar = User.objects.filter(company=request.company).exclude(type='ega').count()
    jami_mahsulotlar = Mahsulot.objects.filter(company=request.company).count()
    
    payload['mahsulotlar'] = mahs

    soni = jami_hodimlar
    msoni = jami_mahsulotlar

    now = timezone.localtime()

    today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
    today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))
    bsavdo = Savdo.objects.filter(company=request.company, vaqt_sana__range=(today_start, today_end)).all()
    bsoni = bsavdo.count()

    # Trial eligibility check
    from datetime import timedelta
    trial_pending = PlanRequest.objects.filter(company=request.company, is_trial=True, status='pending').exists()
    days_since_creation = (timezone.now() - request.company.created_at).days
    can_request_trial = (
        not request.company.has_used_trial
        and days_since_creation <= 10
        and not trial_pending
        and not request.company.is_on_trial
    )
    
    payload['can_request_trial'] = can_request_trial
    payload['trial_pending'] = trial_pending
    payload['days_since_creation'] = days_since_creation

    # Oyning 1-kunining 00:00:00 va bugungi 23:59:59
    month_start = timezone.make_aware(dt.datetime.combine(now.replace(day=1).date(), dt.time.min))
    today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))

    savdo = Savdo.objects.filter(company=request.company, vaqt_sana__range=(month_start, today_end)).all()

    payload['bsavdo'] = bsavdo
    payload['savdo'] = savdo
    payload['bsoni'] = bsoni

    # ── Oylik sof foyda (narx - tannarx, sotuv paytidagi snapshot) ───────────
    oylik_foyda = savdo.aggregate(t=Sum('foyda'))['t'] or 0
    payload['oylik_foyda'] = add_spctoint(round(oylik_foyda))

    # ── Moliya bo'limidagi qo'shimcha ko'rsatkichlar (shu oy uchun) ──────────
    savdo_totals = savdo.aggregate(revenue=Sum('summa'), base=Sum('base_summa'))
    oylik_tushum = savdo_totals['revenue'] or 0
    oylik_cogs = (savdo_totals['base'] or 0) - oylik_foyda
    oylik_naqd_savdo = savdo.filter(st__in=['naqd', 'karta']).aggregate(t=Sum('summa'))['t'] or 0
    oylik_nasiya_tolov = NasiyaTolov.objects.filter(
        company=request.company, tolov_sanasi__range=(month_start, today_end),
    ).aggregate(t=Sum('tolov_summasi'))['t'] or 0
    oylik_pul_aylanma = oylik_naqd_savdo + oylik_nasiya_tolov
    oylik_qoshimcha = QoshimchaChiqim.objects.filter(
        company=request.company, sana__range=(month_start.date(), today_end.date()),
    ).aggregate(t=Sum('summa'))['t'] or 0
    oylik_ish_haqi_tolov = XodimTolov.objects.filter(
        company=request.company, sana__range=(month_start.date(), today_end.date()),
    ).aggregate(t=Sum('summa'))['t'] or 0
    oylik_sof_foyda_toliq = oylik_foyda - float(oylik_qoshimcha) - float(oylik_ish_haqi_tolov)
    oylik_marja = (oylik_sof_foyda_toliq / oylik_tushum * 100) if oylik_tushum else 0

    payload['oylik_pul_aylanma'] = add_spctoint(round(oylik_pul_aylanma))
    payload['oylik_cogs'] = add_spctoint(round(oylik_cogs))
    payload['oylik_qoshimcha'] = add_spctoint(round(oylik_qoshimcha))
    payload['oylik_marja'] = round(oylik_marja, 1)

    # ── Ombordagi hozirgi mahsulotlar qiymati (miqdori x narxi) ──────────────
    from django.db.models import F, DecimalField, ExpressionWrapper
    ombor_qiymati = Mahsulot.objects.filter(company=request.company).aggregate(
        t=Sum(
            ExpressionWrapper(F('miqdori') * F('narxi'), output_field=DecimalField(max_digits=18, decimal_places=2)),
        )
    )['t'] or 0
    payload['ombor_qiymati'] = add_spctoint(round(ombor_qiymati))

    # ── Top 8 — bu oy eng ko'p pul ishlab topgan hodimlar ────────────────────
    all_staff = list(User.objects.filter(company=request.company).exclude(type='ega'))
    for staff in all_staff:
        earned = 0
        if staff.type in ('pazanda', 'ishlab_chiqaruvchi'):
            pz = Pazanda.objects.filter(user=staff, company=request.company).first()
            if pz:
                earned = MiqdorQoshish.objects.filter(
                    pazanda=pz, company=request.company, tasdiqlangan=True,
                    vaqt_sana__range=(month_start, today_end),
                ).aggregate(t=Sum('ish_haqi_summasi'))['t'] or 0
        elif staff.type == 'savdogar':
            earned = Savdo.objects.filter(
                company=request.company, savdogar=staff,
                vaqt_sana__range=(month_start, today_end),
            ).aggregate(t=Sum('summa'))['t'] or 0
        elif staff.type == 'yetkazib_beruvchi':
            yt_obj = YetkazibBeruvchi.objects.filter(user=staff, company=request.company).first()
            if yt_obj:
                earned = Savdo.objects.filter(
                    company=request.company, yetkazib_beruvchi=yt_obj,
                    vaqt_sana__range=(month_start, today_end),
                ).aggregate(t=Sum('summa'))['t'] or 0
        staff.earned = float(earned)
        staff.earned_display = format_compact_money(earned)

    hodims = sorted(all_staff, key=lambda u: u.earned, reverse=True)[:8]
    payload['hodims'] = hodims

    # ── Haftalik savdo (oxirgi 7 kun) ────────────────────────────────────────
    UZ_DAYS = ['Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan', 'Yak']
    weekly_labels = []
    weekly_soni = []    # savdolar soni
    weekly_summa = []   # savdolar summasi (so'm)
    for i in range(6, -1, -1):
        day = now.date() - dt.timedelta(days=i)
        day_start = timezone.make_aware(dt.datetime.combine(day, dt.time.min))
        day_end   = timezone.make_aware(dt.datetime.combine(day, dt.time.max))
        qs = Savdo.objects.filter(company=request.company, vaqt_sana__range=(day_start, day_end))
        weekly_labels.append(UZ_DAYS[day.weekday()])
        weekly_soni.append(qs.count())
        weekly_summa.append(float(qs.aggregate(t=Sum('summa'))['t'] or 0))

    payload['weekly_labels'] = json.dumps(weekly_labels, ensure_ascii=False)
    payload['weekly_soni']   = json.dumps(weekly_soni)
    payload['weekly_summa']  = json.dumps(weekly_summa)

    # ── Mahsulotlar statistikasi (doughnut) ──────────────────────────────────
    # Zaxirada: jami mahsulotlar soni (dona)
    zaxira_miqdori = Mahsulot.objects.filter(company=request.company).aggregate(t=Sum('miqdori'))['t'] or 0
    # Sotilgan: oy davomida sotilgan savdolar soni
    sotilgan_soni = Savdo.objects.filter(company=request.company, vaqt_sana__range=(month_start, today_end)).count()
    # Qaytarilgan
    qaytarilgan_soni = qaytarilgan_mahsulotlar.objects.filter(company=request.company).count()
   

    payload['donut_zaxira'] = float(zaxira_miqdori)
    payload['donut_sotilgan'] = float(sotilgan_soni)
    payload['donut_qaytarilgan'] = float(qaytarilgan_soni)

    # Use Analytics Service
    stats = get_dashboard_stats(request.company)
    payload['usumma'] = add_spctoint(stats['total_sales_month'])
    payload['bsumma'] = add_spctoint(stats['total_sales_today'])
    payload['low_stock_list'] = stats['low_stock_list']
    payload['low_stock_count'] = stats['low_stock_products']
    
    payload['ishchilar_soni'] = soni
    payload['msoni'] = msoni

    # Trial & Plan info for Owner
    if user.type == 'ega':
        days_since_creation = (timezone.now() - request.company.created_at).days
        payload['days_since_creation'] = days_since_creation
        payload['plans'] = [plan for plan in Plan.objects.filter(is_active=True).order_by('price') if plan_is_visible_to_owner(plan)]
        payload['backup_choices'] = BACKUP_CHOICES
        payload['has_pending_request'] = PlanRequest.objects.filter(company=request.company, status='pending').exists()
    
    return render(request, 'main.html', payload)

@login_required(login_url='login')
def logout_view(request):
    """Foydalanuvchini tizimdan chiqarish"""
    if request.user.is_authenticated:
        User.objects.filter(pk=request.user.pk).update(web_session_key=None)
    auth_logout(request)
    return redirect('login')
@login_required(login_url='login')
@login_required(login_url='login')
def add_haridor(request):
    if request.user.type in ['yetkazib_beruvchi', 'savdogar', 'ega']:
        if request.method == 'POST':
            nomi = request.POST.get('nomi')
            egasi = request.POST.get('egasi')
            joylashuvi = request.POST.get('joylashuvi')
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            dukon_rasmi = request.FILES.get('dukon_rasmi')
            egasining_rasmi = request.FILES.get('egasining_rasmi')
            telefon = request.POST.get('telefon')
            telegram_username = request.POST.get('telegram_username')
            
            # Saqlash
            HaridorDukon.objects.create(
                nomi=nomi,
                egasi=egasi,
                joylashuvi=joylashuvi,
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None,
                dukon_rasmi=dukon_rasmi,
                egasining_rasmi=egasining_rasmi,
                telefon=telefon,
                telegram_username=telegram_username,
                company=request.company
            )
            
            messages.success(request, "Yangi haridor muvaffaqiyatli qo‘shildi!")
            return redirect('main')  # yoki kerakli sahifaga
    
        base_template = 'sgbase.html' if request.user.type == 'savdogar' else 'ytbase.html'
        return render(request, 'add_haridor.html', {'base_template': base_template})
    return redirect('main')
def _payroll_context(user, company, can_edit):
    """Xodim (istalgan turdagi) uchun ish haqi/avans kontekstini quradi —
    `ega` boshqa xodim profilini ko'rganda ham (tahrirlash huquqi bilan),
    xodimning o'zi o'z profilini ko'rganda ham (faqat o'qish uchun)."""
    return {
        'payroll_maosh_obj': XodimMaosh.objects.filter(user=user, company=company).first(),
        'payroll_summary': payroll_service.get_month_summary(user, company),
        'payroll_history': payroll_service.get_payment_history(user, company),
        # O'tgan oylardan yopilmagan va musbat qoldig'i bor oylar — "qolib
        # ketgan oylik" (masalan ega "Oyni yopish"ni bosishni unutgan
        # oylar). Har biriga alohida "Shu oyni yopish" tugmasi chiqadi.
        'payroll_outstanding_months': payroll_service.get_user_outstanding_months(user, company),
        'payroll_is_per_unit_pazanda': (
            effective_ish_haqi_turi(user, company) == 'per_unit'
            and Pazanda.objects.filter(user=user, company=company).exists()
        ),
        'can_edit_payroll': can_edit,
    }


def _pazanda_assignment_context(pz, company):
    """Pazanda uchun biriktirilgan/biriktirilishi mumkin bo'lgan mahsulotlar + oylik statistika."""
    assignable_products = Mahsulot.objects.filter(
        Q(warehouse_type='finished', mahsulot_turi='ishlab_chiqariladigan')
        | Q(warehouse_type='semi_finished', ombor_turi='yarim_tayyor'),
        company=company,
    ).exclude(
        id__in=PazandaMahsulot.objects.filter(pazanda=pz).values_list('mahsulot_id', flat=True)
    ).order_by('nomi')
    assigned_products = PazandaMahsulot.objects.filter(
        pazanda=pz
    ).select_related('mahsulot').order_by('mahsulot__nomi')
    return {
        'pazanda_obj': pz,
        'assignable_products': assignable_products,
        'assigned_products': assigned_products,
        'pazanda_month_stats': get_pazanda_month_stats(pz, company),
    }


@login_required(login_url='login')
def profile_view(request, username):
    user = get_object_or_404(User, username=username, company=request.company)
    if request.method == 'GET':

        if request.user.type in ['yetkazib_beruvchi', 'savdogar']:
            base_template = 'sgbase.html' if request.user.type == 'savdogar' else 'ytbase.html'
            context = {'user': user, 'base_template': base_template}
            context['kpi'] = kpi_service.get_employee_kpi(user, request.company)
            context.update(_payroll_context(user, request.company, can_edit=False))
            if request.user.pk == user.pk:
                context['own_badge'], _ = XodimBadge.objects.get_or_create(
                    user=user, defaults={'company': request.company},
                )
            return render(request, 'ytprofile.html', context)
        elif request.user.type in ['pazanda', 'ishlab_chiqaruvchi']:
            context = {'user': user}
            context['kpi'] = kpi_service.get_employee_kpi(user, request.company)
            pz = Pazanda.objects.filter(user=user, company=request.company).first()
            if pz:
                context['pazanda_month_stats'] = get_pazanda_month_stats(pz, request.company)
                context['assigned_products'] = PazandaMahsulot.objects.filter(
                    pazanda=pz
                ).select_related('mahsulot').order_by('mahsulot__nomi')
            context.update(_payroll_context(user, request.company, can_edit=False))
            if request.user.pk == user.pk:
                context['own_badge'], _ = XodimBadge.objects.get_or_create(
                    user=user, defaults={'company': request.company},
                )
            return render(request, 'pzprofile.html', context)
        elif request.user.type == 'omborchi':
            context = {'user': user, 'profile_stats': None}
            context['kpi'] = kpi_service.get_employee_kpi(user, request.company)
            context.update(_payroll_context(user, request.company, can_edit=False))
            if request.user.pk == user.pk:
                context['own_badge'], _ = XodimBadge.objects.get_or_create(
                    user=user, defaults={'company': request.company},
                )
            return render(request, 'egaprofile.html', context)
        elif request.user.type=='ega':
            if user.type in ['yetkazib_beruvchi', 'savdogar']:
                yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=user).mahsulotlar) or []
                context = {'user': user, 'yuklamalar': yuklamalar}
                context['kpi'] = kpi_service.get_employee_kpi(user, request.company)
                context.update(_payroll_context(user, request.company, can_edit=True))
                return render(request, 'egayt.html', context)
            company = request.company
            flags = get_feature_flags(company)
            profile_stats = {
                'staff_count': User.objects.filter(company=company).exclude(type='ega').count(),
                'active_staff_count': User.objects.filter(company=company, is_active=True).exclude(type='ega').count(),
                'product_count': Mahsulot.objects.filter(company=company).count(),
                'customer_count': HaridorDukon.objects.filter(company=company).count(),
                'month_sales_total': Savdo.objects.filter(
                    company=company,
                    vaqt_sana__gte=timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                ).aggregate(total=Sum('summa'))['total'] or 0,
                'open_nasiya_count': Savdo.objects.filter(company=company, st='nasiya', tulandi=False).count(),
                'has_savdogar_sales': flags.get('has_savdogar_sales'),
                'savdogar_contract_ready': bool((company.savdogar_contract_text or '').strip()),
            }
            context = {'user': user, 'profile_stats': profile_stats}
            context['kpi'] = kpi_service.get_employee_kpi(user, company)
            if user.username == request.user.username and company.custom_desktop_agent_stations:
                context['agent_release'] = AgentRelease.objects.order_by('-created_at').first()
            if user.type in ['pazanda', 'ishlab_chiqaruvchi']:
                pz = Pazanda.objects.filter(user=user, company=company).first()
                if pz:
                    context.update(_pazanda_assignment_context(pz, company))
            if user.type != 'ega':
                context.update(_payroll_context(user, company, can_edit=True))
            if request.user.pk == user.pk:
                context['own_badge'], _ = XodimBadge.objects.get_or_create(
                    user=user, defaults={'company': request.company},
                )
            return render(request, 'egaprofile.html', context)
    elif request.method == 'POST':
        if request.user.type == 'ega':
            if request.POST.get('action') == 'set_oylik_maosh' and user.type != 'ega':
                try:
                    oylik_maosh = Decimal(request.POST.get('oylik_maosh') or '0')
                except InvalidOperation:
                    messages.error(request, "Maosh summasi noto'g'ri kiritildi.")
                    return redirect('profile', username=user.username)
                try:
                    payroll_service.set_fixed_salary(user, request.company, oylik_maosh, request.user)
                    messages.success(request, "Oylik maosh saqlandi.")
                except ValueError as e:
                    messages.error(request, str(e))
                return redirect('profile', username=user.username)

            if request.POST.get('action') == 'give_avans' and user.type != 'ega':
                try:
                    summa = Decimal(request.POST.get('summa') or '0')
                except InvalidOperation:
                    messages.error(request, "Summa noto'g'ri kiritildi.")
                    return redirect('profile', username=user.username)
                sana_str = (request.POST.get('sana') or '').strip()
                try:
                    sana = dt.date.fromisoformat(sana_str) if sana_str else timezone.localdate()
                except ValueError:
                    sana = timezone.localdate()
                izoh = (request.POST.get('izoh') or '').strip()
                try:
                    payroll_service.give_avans(user, request.company, summa, sana, request.user, izoh=izoh)
                    messages.success(request, "Avans berildi.")
                except ValueError as e:
                    messages.error(request, str(e))
                return redirect('profile', username=user.username)

            if request.POST.get('action') == 'close_oy' and user.type != 'ega':
                try:
                    snapshot = payroll_service.close_month(user, request.company, request.user)
                    messages.success(
                        request,
                        f"Oy yopildi. Yakuniy to'lov: {snapshot.tolangan_yakuniy_summa:,.0f} so'm",
                    )
                except ValueError as e:
                    messages.error(request, str(e))
                return redirect('profile', username=user.username)

            if request.POST.get('action') == 'pay_outstanding_oy' and user.type != 'ega':
                # Qolib ketgan (o'tgan) oy uchun to'lov — to'liq shart
                # emas, qisman ham bo'lishi mumkin; chek rasmi majburiy.
                try:
                    pay_yil = int(request.POST.get('oy_yil'))
                    pay_oy = int(request.POST.get('oy_oy'))
                    summa = Decimal(request.POST.get('summa') or '0')
                except (TypeError, ValueError, InvalidOperation):
                    messages.error(request, "Oy yoki summa noto'g'ri kiritildi.")
                    return redirect('profile', username=user.username)
                rasm = request.FILES.get('rasm')
                if not rasm:
                    messages.error(request, "To'lov cheki rasmini biriktirish majburiy.")
                    return redirect('profile', username=user.username)
                izoh = (request.POST.get('izoh') or '').strip()
                try:
                    result = payroll_service.pay_outstanding_month(
                        user, request.company, pay_yil, pay_oy, summa, rasm, request.user, izoh=izoh,
                    )
                    oy_label = f"{pay_yil}-{pay_oy:02d}"
                    if result['yopildi']:
                        messages.success(request, f"{oy_label} oyi to'liq to'landi va yopildi.")
                    else:
                        messages.success(
                            request,
                            f"{oy_label} oyiga {summa:,.0f} so'm to'landi. Qolgan qarz: {result['qolgan_qarz']:,.0f} so'm.",
                        )
                except ValueError as e:
                    messages.error(request, str(e))
                return redirect('profile', username=user.username)

            if request.POST.get('action') in ('assign_mahsulot', 'unassign_mahsulot') and user.type in ['pazanda', 'ishlab_chiqaruvchi']:
                pz = get_object_or_404(Pazanda, user=user, company=request.company)
                if request.POST.get('action') == 'assign_mahsulot':
                    mahsulot = get_object_or_404(Mahsulot, id=request.POST.get('mahsulot_id'), company=request.company)
                    PazandaMahsulot.objects.get_or_create(company=request.company, pazanda=pz, mahsulot=mahsulot)
                    messages.success(request, "Mahsulot biriktirildi.")
                else:
                    PazandaMahsulot.objects.filter(
                        pazanda=pz, mahsulot_id=request.POST.get('mahsulot_id'), company=request.company,
                    ).delete()
                    messages.success(request, "Mahsulot biriktirilishi bekor qilindi.")
                return redirect('profile', username=user.username)

            if user.type == 'ega':
                new_username = (request.POST.get('username') or '').strip()
                fullname = (request.POST.get('tuliq_ismi') or '').strip()
                phone = (request.POST.get('telefon') or '').strip()
                email = (request.POST.get('email') or '').strip()
                password = request.POST.get('password')

                if not new_username or not fullname:
                    messages.error(request, "Login va to'liq ism majburiy.")
                    return redirect('profile', username=user.username)

                if User.objects.filter(company=request.company, username=new_username).exclude(pk=user.pk).exists():
                    messages.error(request, "Ushbu login boshqa foydalanuvchida mavjud.")
                    return redirect('profile', username=user.username)

                user.username = new_username
                user.tuliq_ismi = fullname
                user.tel_raqami = phone
                user.email = email
                if password:
                    user.set_password(password)
                user.save()

                messages.success(request, "Profil ma'lumotlari saqlandi.")
                return redirect('profile', username=user.username)

            if request.user.pk == user.pk and user.type != 'ega':
                phone = (request.POST.get('telefon') or '').strip()
                email = (request.POST.get('email') or '').strip()
                password = request.POST.get('password')
                user.tel_raqami = phone
                user.email = email
                if password:
                    user.set_password(password)
                user.save()
                messages.success(request, "Profil ma'lumotlari saqlandi.")
                return redirect('profile', username=user.username)

            res=''
            if user.type in ['yetkazib_beruvchi', 'savdogar']:
                # Note: Keeping legacy stock adjustment for now as a fallback, 
                # but ideally this should also use a service.
                for i in request.POST:
                    nomi = Mahsulot.objects.filter(nomi=i)
                    if nomi.exists():
                        mq = request.POST.get(i, '0')
                        try:
                            mq_float = float(mq)
                        except (ValueError, TypeError):
                            continue
                        if mq_float != 0:
                            res += f"{i} {mq},"
                
                yt=YetkazibBeruvchi.objects.get(user=user)
                yt.mahsulotlar=res
                yt.save()
                yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=user).mahsulotlar) or []
                return render(request, 'egayt.html',{'user': user,'yuklamalar': yuklamalar})
def _desktop_agent_slots_left(company):
    if not company:
        return 0
    used = User.objects.filter(company=company, type='desktop_agent').count()
    return max(company.custom_desktop_agent_stations - used, 0)


@login_required(login_url='login')
def crtuser(request):
    if request.method == 'POST':
        # Check plan limit
        company = request.user.company
        if company:
            requested_type = request.POST.get('turi')
            flags = get_feature_flags(company)
            if requested_type == 'savdogar' and not flags.get('has_savdogar_sales'):
                messages.error(request, "Savdogar rolini ochish uchun maxsus tarifda $10 lik Savdogar savdo modulini yoqing.")
                ctx = request.POST.dict()
                ctx['desktop_agent_slots_left'] = _desktop_agent_slots_left(company)
                return render(request, 'useryaratish.html', ctx)

            if requested_type == 'desktop_agent':
                current_stations = User.objects.filter(company=company, type='desktop_agent').count()
                if current_stations >= company.custom_desktop_agent_stations:
                    messages.error(
                        request,
                        f"Siz sotib olgan Desktop Agent stansiyalari soni ({company.custom_desktop_agent_stations}) "
                        f"ga yetgan. Ko'proq stansiya kerak bo'lsa, biz bilan bog'laning."
                    )
                    ctx = request.POST.dict()
                    ctx['desktop_agent_slots_left'] = _desktop_agent_slots_left(company)
                    return render(request, 'useryaratish.html', ctx)

            # Get max_users from custom plan or standard plan
            if company.is_custom_plan:
                max_users = company.custom_max_users
            elif company.plan:
                max_users = company.plan.max_users
            else:
                max_users = 5 # Default for trial/no plan

            # 0 means Unlimited. Desktop Agent stansiyalari alohida (billing addon)
            # kvota bilan cheklangani uchun umumiy xodim limitiga hisoblanmaydi.
            if max_users > 0 and requested_type != 'desktop_agent':
                current_users_count = User.objects.filter(company=company).exclude(type='desktop_agent').count()
                if current_users_count >= max_users:
                    messages.error(request, f"Siz tanlagan tarif bo'yicha maksimal foydalanuvchilar soni ({max_users}) ga yetgan. Qo'shish uchun tarifni yangilang.")
                    ctx = request.POST.dict()
                    ctx['desktop_agent_slots_left'] = _desktop_agent_slots_left(company)
                    return render(request, 'useryaratish.html', ctx)

        user, message = create_user_service(
            username=request.POST.get('username'),
            password=request.POST.get('password'),
            fullname=request.POST.get('tuliq_ismi'),
            user_type=request.POST.get('turi'),
            phone=request.POST.get('telefon'),
            profile_photo=request.FILES.get('rasmi'),
            car_info=request.POST.get('mashina_nomi'),
            car_photo=request.FILES.get('mashina_rasmi'),
            company=request.company
        )
        if user:
            messages.success(request, message)
            return redirect('hodimlar_list')
        else:
            messages.error(request, message)
            ctx = request.POST.dict()
            ctx['desktop_agent_slots_left'] = _desktop_agent_slots_left(company)
            return render(request, 'useryaratish.html', ctx)

    return render(request, 'useryaratish.html', {
        'desktop_agent_slots_left': _desktop_agent_slots_left(request.company),
    })

@login_required(login_url='login')
def editusr(request, username):
    user_edit = get_object_or_404(User, username=username, company=request.company)
    mn = ''
    mr = ''
    all_mahsulotlar = []
    current_yuklamalar_dict = {}

    if user_edit.type == 'yetkazib_beruvchi':
        yb = YetkazibBeruvchi.objects.filter(user=user_edit).first()
        if yb:
            mn = yb.bmh
            mr = yb.bmr.url if yb.bmr else ''
        all_mahsulotlar = Mahsulot.objects.filter(company=request.company).order_by('nomi')
        
        # Parse current stock string into dict {nom: miqdor}
        from .functions import mahsulotlar_miqdori
        yuklamalar_list = mahsulotlar_miqdori(yb.mahsulotlar)
        for y in yuklamalar_list:
            current_yuklamalar_dict[y.nom] = y.miqdor

    if request.method == 'POST':
        action_type = request.POST.get('action_type')

        if action_type == 'delete_account':
            if request.POST.get('confirm_text') == 'OCHIR':
                user_edit.delete()
                messages.success(request, "Foydalanuvchi o'chirildi.")
                return redirect('hodimlar_list')
            else:
                messages.error(request, "Tasdiq matni noto'g'ri.")
                return redirect('edituser', username=username)

        if request.POST.get('action') == 'set_tarozi_majburiy' and user_edit.type == 'desktop_agent':
            # Firma darajasidagi sozlama (`Company.tarozi_majburiy`) —
            # bu yerdan (aynan shu agent stansiyasini tahrirlash
            # sahifasidan) o'zgartiriladi, chunki ega ko'proq shu yerda
            # qidiradi (218-qadamda hodimlar ro'yxatida edi, foydalanuvchi
            # so'rovi bilan shu sahifaga ko'chirildi).
            request.company.tarozi_majburiy = request.POST.get('tarozi_majburiy') == '1'
            request.company.save(update_fields=['tarozi_majburiy'])
            messages.success(request, "Tarozi sozlamasi saqlandi.")
            return redirect('edituser', username=username)

        if request.POST.get('action') in ('assign_mahsulot', 'unassign_mahsulot') and user_edit.type in ['pazanda', 'ishlab_chiqaruvchi']:
            pz = get_object_or_404(Pazanda, user=user_edit, company=request.company)
            if request.POST.get('action') == 'assign_mahsulot':
                mahsulot = get_object_or_404(Mahsulot, id=request.POST.get('mahsulot_id'), company=request.company)
                PazandaMahsulot.objects.get_or_create(company=request.company, pazanda=pz, mahsulot=mahsulot)
                messages.success(request, "Mahsulot biriktirildi.")
            else:
                PazandaMahsulot.objects.filter(
                    pazanda=pz, mahsulot_id=request.POST.get('mahsulot_id'), company=request.company,
                ).delete()
                messages.success(request, "Mahsulot biriktirilishi bekor qilindi.")
            return redirect('edituser', username=username)

        if request.POST.get('action') == 'set_ish_haqi_turi_override' and user_edit.type in ['pazanda', 'ishlab_chiqaruvchi', 'savdogar', 'yetkazib_beruvchi']:
            override = request.POST.get('ish_haqi_turi_override', '')
            if override not in dict(User.ISH_HAQI_TURI_OVERRIDE_CHOICES):
                override = ''
            # 'per_unit' faqat ishlab chiqaruvchi uchun, 'per_sale' faqat savdogar/yetkazib beruvchi uchun ma'noli
            if override == 'per_unit' and user_edit.type not in ['pazanda', 'ishlab_chiqaruvchi']:
                override = ''
            if override == 'per_sale' and user_edit.type not in ['savdogar', 'yetkazib_beruvchi']:
                override = ''
            user_edit.ish_haqi_turi_override = override
            user_edit.save(update_fields=['ish_haqi_turi_override'])

            # "Oylik (fiksval)" tanlanganda summani ham SHU YERDA kiritish
            # imkoni — avval alohida profil sahifasiga o'tish kerak edi,
            # bu chalkashtirar edi ("fiksval belgilasa nega kiritadigan
            # maydon yo'q" — ega bilan kelishilgan tuzatish).
            oylik_maosh_raw = (request.POST.get('oylik_maosh') or '').strip()
            if oylik_maosh_raw:
                try:
                    oylik_maosh = Decimal(oylik_maosh_raw)
                    if oylik_maosh < 0:
                        raise InvalidOperation
                    payroll_service.set_fixed_salary(user_edit, request.company, oylik_maosh, request.user)
                except (InvalidOperation, ValueError):
                    messages.error(request, "Oylik maosh summasi noto'g'ri kiritildi.")
                    return redirect('edituser', username=username)

            messages.success(request, "Ish haqi turi saqlandi.")
            return redirect('edituser', username=username)

        # Refactored to Auth Service
        user, message = update_user_service(
            user=user_edit,
            username=request.POST.get('username'),
            fullname=request.POST.get('tuliq_ismi'),
            phone=request.POST.get('telefon'),
            password=request.POST.get('password'),
            profile_photo=request.FILES.get('rasmi'),
            car_info=request.POST.get('mashina_nomi'),
            car_photo=request.FILES.get('mashina_rasmi1'),
            is_active=(request.POST.get('is_active') == "1")
        )

        # Yetkazib beruvchining zaxirasi endi bu yerdan qo'lda tahrirlanmaydi —
        # faqat "yuklama" so'rovi (web'da tasdiqlash yoki Desktop Agent orqali
        # Serial QR skanerlash) orqali, tizim tomonidan o'zgaradi.

        messages.success(request, message)
        return redirect('hodimlar_list')

    company_ish_haqi_turi_display = dict(request.company.ISH_HAQI_TURI_CHOICES).get(request.company.ish_haqi_turi)
    effective_turi = effective_ish_haqi_turi(user_edit, request.company)
    effective_turi_display = dict(User.ISH_HAQI_TURI_OVERRIDE_CHOICES).get(effective_turi) or company_ish_haqi_turi_display
    maosh_obj = XodimMaosh.objects.filter(user=user_edit, company=request.company).first()

    context = {
        'user_edit': user_edit,
        'mn': mn,
        'mr': mr,
        'all_mahsulotlar': all_mahsulotlar,
        'current_yuklamalar': current_yuklamalar_dict,
        'ish_haqi_turi_override_choices': [
            (v, l) for v, l in User.ISH_HAQI_TURI_OVERRIDE_CHOICES if v != 'per_sale'
        ],
        'company_ish_haqi_turi_display': company_ish_haqi_turi_display,
        'effective_ish_haqi_turi_display': effective_turi_display,
        'oylik_maosh': maosh_obj.oylik_maosh if maosh_obj else None,
    }
    if user_edit.type in ['pazanda', 'ishlab_chiqaruvchi']:
        pz = Pazanda.objects.filter(user=user_edit, company=request.company).first()
        if pz:
            context.update(_pazanda_assignment_context(pz, request.company))

    if user_edit.type in ['savdogar', 'yetkazib_beruvchi']:
        context['savdo_ish_haqi_choices'] = [
            (v, l) for v, l in User.ISH_HAQI_TURI_OVERRIDE_CHOICES if v in ('', 'fixed', 'per_sale')
        ]

    if user_edit.type == 'desktop_agent':
        context['tarozi_majburiy'] = request.company.tarozi_majburiy

    return render(request, 'editusr.html', context)
@login_required(login_url='login')
def seemahsulot(request, mahsulot_id):
    mahsulot = get_object_or_404(Mahsulot, id=mahsulot_id, company=request.company, warehouse_type='finished')
    turs = MahsulotTuri.objects.all().order_by('nomi')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_xarajat':
            nomi_x = (request.POST.get('xarajat_nomi') or '').strip()
            turi_x = request.POST.get('xarajat_turi') or 'miqdor'
            if turi_x not in dict(MahsulotQoshimchaXarajat.XARAJAT_TURI_CHOICES):
                turi_x = 'miqdor'
            try:
                summa_x = float(request.POST.get('xarajat_summa') or 0)
            except ValueError:
                summa_x = 0
            if nomi_x and summa_x > 0:
                MahsulotQoshimchaXarajat.objects.create(
                    company=request.company, mahsulot=mahsulot, nomi=nomi_x, turi=turi_x, summa=summa_x,
                )
                recompute_tannarx(mahsulot)
                messages.success(request, "Qo'shimcha xarajat qo'shildi.")
            else:
                messages.error(request, "Xarajat nomi va summasi to'g'ri kiritilishi kerak.")
            return redirect('seeproduct', mahsulot_id=mahsulot.id)

        if action == 'delete_xarajat':
            MahsulotQoshimchaXarajat.objects.filter(
                id=request.POST.get('xarajat_id'), company=request.company, mahsulot=mahsulot,
            ).delete()
            recompute_tannarx(mahsulot)
            messages.success(request, "Qo'shimcha xarajat o'chirildi.")
            return redirect('seeproduct', mahsulot_id=mahsulot.id)

        if action == 'add_retsept_row':
            komponent = get_object_or_404(Mahsulot, id=request.POST.get('komponent'), company=request.company)
            try:
                norma_miqdor = float(request.POST.get('norma_miqdor') or 0)
            except ValueError:
                norma_miqdor = 0
            ok, err = add_retsept_row(request.company, mahsulot, komponent, norma_miqdor)
            if ok:
                messages.success(request, "Retsept qatori saqlandi.")
            else:
                messages.error(request, err)
            return redirect('seeproduct', mahsulot_id=mahsulot.id)

        if action == 'delete_retsept_row':
            delete_retsept_row(request.company, mahsulot, request.POST.get('row_id'))
            messages.success(request, "Retsept qatori o'chirildi.")
            return redirect('seeproduct', mahsulot_id=mahsulot.id)

        if 'nomi' in request.POST:
            nnomi = request.POST.get('nomi')
            yts = YetkazibBeruvchi.objects.all()
            for yt in yts:
                mahs = mahsulotlar_miqdori(yt.mahsulotlar)
                for m in mahs:
                    if m.nom == mahsulot.nomi:
                        m.nom = nnomi
                yt.mahsulotlar = yuklama_maker(mahs)
                yt.save()
            mahsulot.nomi = nnomi

        # Miqdor — faqat mahsulot birinchi marta yaratilganda (createmahsulot)
        # kiritiladi. Undan keyin faqat tizim orqali (ishlab chiqarish
        # tasdiqlanishi, sotish, qaytarish) o'zgaradi — bu yerdan qo'lda
        # tahrirlash imkoni yo'q (distributor turi bundan mustasno — ularga
        # hali alohida "kirim" oqimi qurilmagan, shuning uchun vaqtincha
        # eski xatti-harakat saqlanadi).
        if mahsulot.mahsulot_turi == 'distributor':
            mahsulot.miqdori = request.POST.get('miqdori')
        mahsulot.ishlab_chiqarish_narxi = request.POST.get('ishlab_chiqarish_narxi') or 0
        mahsulot.sotuv_ish_haqi_narxi = request.POST.get('sotuv_ish_haqi_narxi') or 0
        mahsulot.amortizatsiya_foizi = request.POST.get('amortizatsiya_foizi') or 0
        mahsulot.mahsulot_turi = request.POST.get('mahsulot_turi', mahsulot.mahsulot_turi)
        kutilgan_soat = (request.POST.get('kutilgan_ishlab_chiqarish_soat') or '').strip()
        try:
            mahsulot.kutilgan_ishlab_chiqarish_soat = float(kutilgan_soat) if kutilgan_soat else None
        except ValueError:
            mahsulot.kutilgan_ishlab_chiqarish_soat = None

        serial_granularity = request.POST.get('serial_granularity')
        if serial_granularity in dict(Mahsulot.SERIAL_GRANULARITY_CHOICES):
            mahsulot.serial_granularity = serial_granularity

        # Look up by ID as sent from the template <option value="{{ tur.id }}">
        turi_id = request.POST.get('turi')
        if turi_id:
            mahsulot.turi = get_object_or_404(MahsulotTuri, id=turi_id)
        mahsulot.is_savdogar_product = 'is_savdogar_product' in request.POST

        if 'rasmi' in request.FILES:
            mahsulot.rasmi = request.FILES['rasmi']

        mahsulot.save()
        recompute_tannarx(mahsulot)

        try:
            yangi_narxi = Decimal(str(request.POST.get('narxi') or 0))
        except Exception:
            yangi_narxi = Decimal('0')

        if yangi_narxi <= mahsulot.tannarx:
            messages.error(
                request,
                f"Narxi tannarxdan ({mahsulot.tannarx:.0f} so'm) yuqori bo'lishi kerak. "
                f"Narxi saqlanmadi, boshqa o'zgarishlar saqlandi."
            )
            return redirect('seeproduct', mahsulot_id=mahsulot.id)

        mahsulot.narxi = yangi_narxi
        mahsulot.save(update_fields=['narxi'])
        messages.success(request, "Mahsulot muvaffaqiyatli saqlandi.")
        return redirect('mahsulotlar_list')
    context = {
        'mahsulot': mahsulot, 'turs': turs,
        'mahsulot_turi_choices': Mahsulot.MAHSULOT_TURI_CHOICES,
        'serial_granularity_choices': Mahsulot.SERIAL_GRANULARITY_CHOICES,
        'xarajatlar': mahsulot.qoshimcha_xarajatlar.all(),
    }
    if mahsulot.mahsulot_turi == 'ishlab_chiqariladigan':
        context['retsept_rows'] = MahsulotRetsept.objects.filter(
            company=request.company, mahsulot=mahsulot
        ).select_related('komponent')
        context['retsept_komponentlar'] = Mahsulot.objects.filter(
            company=request.company, warehouse_type='semi_finished'
        ).order_by('nomi')
        context['statistika'] = get_mahsulot_statistika(mahsulot)
    return render(request, 'seemahsulot.html', context)
@login_required(login_url='login')
def createmahsulot(request):
    tur=MahsulotTuri.objects.all().order_by('nomi')
    payload={}
    payload['turs']=tur
    payload['mahsulot_turi_choices'] = Mahsulot.MAHSULOT_TURI_CHOICES
    if request.method == 'POST':
        nomi = request.POST.get('nomi')
        miqdori = request.POST.get('miqdori')
        turi=get_object_or_404(MahsulotTuri, id=request.POST.get('turi'))
        rasmi = request.FILES.get('rasmi')
        mahsulot_turi = request.POST.get('mahsulot_turi', 'ishlab_chiqariladigan')
        is_savdogar_product = 'is_savdogar_product' in request.POST
        mh=Mahsulot.objects.create(
            nomi=nomi, miqdori=miqdori, turi=turi, narxi=0, rasmi=rasmi, company=request.company,
            warehouse_type='finished', mahsulot_turi=mahsulot_turi, is_savdogar_product=is_savdogar_product,
        )
        # Activity log
        AmalLog.objects.create(
            user=request.user,
            company=request.company,
            amal_shifri=f"mahsulot_yaratish|{nomi}|{miqdori}"
        )
        return redirect('main')
    return render(request, 'crtmahsulot.html',payload)

@login_required(login_url='login')
def deleteprdct(request, product_id):
    mhs = get_object_or_404(Mahsulot, id=product_id)
    if request.method == 'POST':
        confirm_text = request.POST.get('confirm_text')
        if confirm_text == 'OCHIR':
            if mhs.stockhistory_set.exists() or mhs.yuklamasorov_set.exists() or mhs.deliverystock_set.exists() or mhs.miqdorqoshish_set.exists():
                from django.contrib import messages
                messages.error(request, "Ushbu mahsulot bo'yicha tarixiy yozuvlar mavjud! Uni o'chirish audit xatoliklariga olib keladi. Iltimos, o'rniga nomini 'Eskirgan' deb o'zgartiring.")
                return redirect('seeproduct', mahsulot_id=product_id)
            
            mhs.delete()
            from django.contrib import messages
            messages.success(request, "Mahsulot o'chirildi.")
            return redirect('mahsulotlar_list')
        else:
            from django.contrib import messages
            messages.error(request, "Tasdiqlash matni noto'g'ri.")
    return redirect('seeproduct', mahsulot_id=product_id)


def _pazanda_mahsulotlar_qs(company, pazanda):
    """
    Ishlab chiqaruvchi hisobot bera oladigan mahsulotlar (tayyor + yarim tayyor).
    Agar unga aniq mahsulot biriktirilgan bo'lsa — faqat o'shalar; hech narsa
    biriktirilmagan bo'lsa — eski xulq-atvor (faqat tayyor mahsulotlar).
    """
    assigned_ids = list(
        PazandaMahsulot.objects.filter(pazanda=pazanda).values_list('mahsulot_id', flat=True)
    )
    if assigned_ids:
        return Mahsulot.objects.filter(company=company, id__in=assigned_ids).order_by('nomi')
    return Mahsulot.objects.filter(company=company, warehouse_type='finished').order_by('nomi')


@login_required(login_url='login')
def addmiqdor(request):
    if request.user.type in ['pazanda', 'ishlab_chiqaruvchi']:
        # 108-qadam: agent-yoqilgan firmalarda "Miqdor Qo'shish"/"Material
        # So'rash" endi ishlatilmaydi — o'rniga "Vazifalar paneli" (103-107
        # qadamlar), bandlik/bajarish faqat Desktop Agent orqali. Agentsiz
        # firmalarda bu sahifa o'zgarishsiz ishlayveradi.
        if request.company.custom_desktop_agent_stations > 0:
            messages.info(
                request,
                "Bu funksiya endi Desktop Agent orqali ishlaydi. Yangi vazifalarni "
                "va yuklama topshirishni stansiyada badge'ingizni skanerlab bajaring.",
            )
            return redirect('main')

        payload={}
        try:
            pz_for_list = Pazanda.objects.get(user=request.user, company=request.company)
            payload['mahsulotlar'] = _pazanda_mahsulotlar_qs(request.company, pz_for_list)
        except Pazanda.DoesNotExist:
            payload['mahsulotlar'] = Mahsulot.objects.filter(company=request.company, warehouse_type='finished').order_by('nomi')
        payload['materials']=Mahsulot.objects.filter(company=request.company, warehouse_type='semi_finished').order_by('nomi')

        # Agent-yoqilgan firmalarda hali tasdiqlanmagan (Desktop Agent'da
        # kutilayotgan) so'rovlarni shu sahifaning o'zida ko'rsatamiz —
        # aks holda foydalanuvchi buni bilmasdan, bir xil mahsulot uchun
        # yana bir marta yuborishi (dublikat) mumkin edi (bugungi haqiqiy
        # holatda aynan shu tarzda bir necha marta takrorlangan edi).
        if request.company.custom_desktop_agent_stations > 0:
            try:
                pz_for_pending = Pazanda.objects.get(user=request.user, company=request.company)
                payload['pending_own_miqdor'] = MiqdorQoshish.objects.filter(
                    company=request.company, pazanda=pz_for_pending, tasdiqlangan=False,
                ).select_related('mahsulot').order_by('-vaqt_sana')
            except Pazanda.DoesNotExist:
                pass

        # "✓ Bo'ldim" havolasi orqali kelgan bo'lsa (pazanda_dashboard.html'dagi
        # tasdiqlangan, hali "tugallanmagan" material so'rovi) — mahsulot va
        # miqdorni oldindan to'ldiramiz (retsept/BOM orqali hisoblab: so'ralgan
        # xom ashyo miqdori / norma_miqdor = taxminiy tayyor mahsulot soni).
        # Foydalanuvchi baribir bu qiymatni kamaytirishi/ko'paytirishi mumkin —
        # bu shunchaki oldindan to'ldirish, majburiy qiymat emas.
        complete_request_id = request.GET.get('complete_request')
        if complete_request_id:
            try:
                pz_prefill = Pazanda.objects.get(user=request.user, company=request.company)
                creq = ProductionMaterialRequest.objects.select_related('material', 'target_product').get(
                    id=complete_request_id, company=request.company, producer=pz_prefill,
                    status='approved', consumed_in__isnull=True,
                )
                payload['prefill_mahsulot_id'] = creq.target_product_id
                payload['complete_request_id'] = creq.id
                bom_row = MahsulotRetsept.objects.filter(
                    company=request.company, mahsulot=creq.target_product, komponent=creq.material,
                ).first()
                if bom_row and bom_row.norma_miqdor:
                    payload['prefill_miqdor'] = round(creq.qty / bom_row.norma_miqdor, 2)
                else:
                    payload['prefill_miqdor'] = creq.qty
            except (Pazanda.DoesNotExist, ProductionMaterialRequest.DoesNotExist):
                pass

        if request.method == 'POST':
            try:
                pz = Pazanda.objects.get(user=request.user, company=request.company)
            except Pazanda.DoesNotExist:
                messages.error(request, "Profil topilmadi. Administrator bilan bog'laning.")
                return redirect('login')
            if request.POST.get('action') == 'request_material':
                material = get_object_or_404(
                    Mahsulot,
                    id=request.POST.get('material'),
                    company=request.company,
                    warehouse_type='semi_finished'
                )
                target_product = get_object_or_404(
                    _pazanda_mahsulotlar_qs(request.company, pz),
                    id=request.POST.get('target_product'),
                )
                try:
                    qty = float((request.POST.get('material_qty') or '0').replace(',', '.'))
                except ValueError:
                    qty = 0
                if qty <= 0:
                    messages.error(request, "So'raladigan material miqdori 0 dan katta bo'lishi kerak.")
                    return redirect('add_miqdor')
                if qty > material.miqdori:
                    unit_name = material.turi.nomi if material.turi else ''
                    messages.error(
                        request,
                        f"{material.nomi} omborda yetarli emas. Qoldiq: {material.miqdori:g} {unit_name}."
                    )
                    return redirect('add_miqdor')
                ProductionMaterialRequest.objects.create(
                    company=request.company,
                    producer=pz,
                    material=material,
                    target_product=target_product,
                    qty=qty,
                    note=request.POST.get('material_note') or ''
                )
                StockHistory.objects.create(
                    actor_user=request.user,
                    company=request.company,
                    mahsulot=material,
                    event_type='RAW_REQUESTED',
                    old_qty=material.miqdori,
                    new_qty=material.miqdori,
                    delta=0,
                )
                send_ws_notification(
                    request.company.subdomain,
                    "Yangi material so'rovi",
                    f"{pz.tuliq_ismi} {target_product.nomi} uchun {qty:g} {material.turi.nomi} {material.nomi} so'radi.",
                    'warning',
                    refresh=True
                )
                messages.success(request, "Material so'rovi omborchiga yuborildi.")
                return redirect('main')

            if request.POST.get('action') == 'cancel_material_request':
                # Ishlab chiqaruvchi o'zi yuborgan, hali "kutilmoqda" holatidagi
                # so'rovni bekor qiladi. Desktop Agent'da bekor qilish imkoni
                # yo'q (klaviatura/sichqonchasiz stansiya) — shuning uchun
                # foydalanuvchi bilan kelishilgan qaror: bekor qilish faqat
                # shu yerdan, o'z so'rovlari ro'yxatidan amalga oshiriladi.
                req = ProductionMaterialRequest.objects.filter(
                    id=request.POST.get('request_id'), company=request.company,
                    producer=pz, status='waiting',
                ).first()
                if req:
                    req.status = 'rejected'
                    req.reviewed_by = request.user
                    req.reviewed_at = timezone.now()
                    req.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
                    messages.success(request, "So'rov bekor qilindi.")
                else:
                    messages.error(request, "So'rov topilmadi yoki allaqachon ko'rib chiqilgan.")
                return redirect('main')

            mxs = get_object_or_404(_pazanda_mahsulotlar_qs(request.company, pz), id=request.POST.get('mahsulot'))
            mqdr=request.POST.get('miqdor')
            rasmi=request.FILES.get('rasm')

            # "✓ Bo'ldim" havolasi orqali kelgan bo'lsa — shu material
            # so'rovi uchun avvalroq allaqachon miqdor yuborilmaganini
            # tekshiramiz (BOM/retsept bo'lmagan mahsulotlarda `consumed_in`
            # hech qachon yozilmagani uchun, tugma qayta-qayta bosilib
            # dublikat yozuv yaratilishining oldini shu tekshiruv oladi).
            source_material_request = None
            complete_request_id = request.POST.get('complete_request_id')
            if complete_request_id:
                source_material_request = ProductionMaterialRequest.objects.filter(
                    id=complete_request_id, company=request.company, producer=pz,
                    status='approved', consumed_in__isnull=True, miqdor_qoshishlar__isnull=True,
                ).first()
                if not source_material_request:
                    messages.error(request, "Bu so'rov uchun miqdor allaqachon yuborilgan yoki topilmadi.")
                    return redirect('main')

            # Yuqoridagi tekshiruv faqat "✓ Bo'ldim" havolasi orqali kelgan
            # (complete_request_id bilan) submitlarni himoya qiladi. Lekin
            # aynan shu sahifadan to'g'ridan-to'g'ri (havolasiz) yuborilgan
            # so'rovlar ham xuddi shunday dublikat bo'lishi mumkin — masalan
            # foydalanuvchi "hech narsa bo'lmadi" deb o'ylab, bir xil
            # mahsulot/miqdorni bir necha marta (soatlar oralig'ida ham)
            # qayta yuboradi, chunki hozircha tasdiqlanmagan so'rovi
            # borligini ko'rmaydi. Shuning uchun bu yerda — agent-yoqilgan
            # firmalarda — umumiy tekshiruv: shu mahsulot uchun hali
            # tasdiqlanmagan so'rov mavjud bo'lsa va foydalanuvchi ataylab
            # tasdiqlamagan bo'lsa (confirm_duplicate), bloklanadi.
            if request.company.custom_desktop_agent_stations > 0 and request.POST.get('confirm_duplicate') != '1':
                pending_duplicate = MiqdorQoshish.objects.filter(
                    company=request.company, pazanda=pz, mahsulot=mxs, tasdiqlangan=False,
                ).order_by('-vaqt_sana').first()
                if pending_duplicate:
                    payload['duplicate_warning'] = pending_duplicate
                    payload['duplicate_mahsulot_id'] = mxs.id
                    payload['duplicate_miqdor'] = mqdr
                    payload['duplicate_complete_request_id'] = complete_request_id
                    return render(request, 'addmiqdor.html', payload)

            # Create request for this company (Unapproved initially)
            nw=MiqdorQoshish.objects.create(
                company=request.company,
                mahsulot=mxs,
                miqdor=mqdr,
                rasmi=rasmi,
                tasdiqlangan=False,
                pazanda=pz,
                source_material_request=source_material_request,
            )

            # Desktop Agent ishlatadigan firmalarda (stansiya sotib olingan)
            # bu yerda DARHOL tasdiqlanmaydi — ishlab chiqaruvchi Desktop
            # Agent'ga borib, badge skanerlab, o'sha yerda tasdiqlashi kerak
            # (81-qadamdagi xom ashyo so'rovi bilan bir xil qaror: agent
            # ishlatilganda, bu bosqich fizik hozirlikni tasdiqlaydi va
            # Serial QR chop etish imkonini beradi). Desktop Agent'i yo'q
            # firmalar uchun eski xatti-harakat (darhol tasdiqlash)
            # o'zgarishsiz qoladi.
            if request.company.custom_desktop_agent_stations > 0:
                send_ws_notification(
                    request.company.subdomain,
                    "Yangi miqdor qo'shish so'rovi",
                    f"{pz.tuliq_ismi} {mqdr} ta {mxs.nomi} uchun so'rov yubordi — Desktop Agent'da tasdiqlanishi kerak.",
                    'warning',
                )
                messages.success(request, "So'rovingiz yuborildi. Desktop Agent'ga borib badge'ingizni skanerlab tasdiqlang.")
                # Desktop Agent stansiyasi hozir oflayn bo'lsa — foydalanuvchi
                # buni darhol bilishi kerak, aks holda so'rov "havoga" ketgandek
                # tuyulishi mumkin (agent yoqilmaguncha hech kim tasdiqlamaydi).
                # `is_agent_online` heartbeat orqali (~25 soniyada bir marta)
                # doim yangilanib turadi — shuning uchun bu yerda alohida
                # so'rov/kutish shart emas, joriy holat allaqachon amalda
                # real-vaqtga yaqin (90 soniyagacha aniq).
                stations = User.objects.filter(
                    company=request.company, type='desktop_agent', is_active=True,
                )
                if stations.exists() and not any(s.is_agent_online for s in stations):
                    messages.warning(
                        request,
                        "Diqqat: Desktop Agent stansiyasi hozir oflayn ko'rinmoqda! "
                        "So'rovingiz saqlandi, lekin stansiya yoqilib, badge skanerlanmaguncha tasdiqlanmaydi.",
                    )
                return redirect('main')

            # Delegate to atomic service to prevent race conditions and log history
            success, message = approve_miqdor_qoshish_service(nw.id, request.user)
            if not success:
                messages.error(request, message)
                return redirect('main')

            # WebSocket Notification
            send_ws_notification(
                request.company.subdomain,
                "Yangi Miqdor Qo'shildi",
                f"{pz.tuliq_ismi} {mqdr} ta {mxs.nomi} qo'shdi.",
                'success'
            )

            return redirect('main')
        return render(request, 'addmiqdor.html',payload)
    return redirect('main')
@login_required(login_url='login')
def add_yuklama(request):
    if request.user.type not in ['pazanda', 'ishlab_chiqaruvchi']:
        return redirect('main')
    # 108-qadam: agent-yoqilgan firmalarda yetkazib beruvchi/savdogar
    # to'g'ridan-to'g'ri Serial-QR skanerlab yuklama oladi (Desktop Agent,
    # `agent_scan_delivery_serial`/`agent_finalize_yuklama`) — alohida
    # "so'rov yaratish" kerak emas.
    if request.company.custom_desktop_agent_stations > 0:
        messages.info(
            request,
            "Bu funksiya endi Desktop Agent orqali ishlaydi. Yetkazib beruvchi/savdogar "
            "stansiyada badge'ini va mahsulot QR kodlarini skanerlab yuklama oladi.",
        )
        return redirect('main')
    try:
        pazanda = Pazanda.objects.get(user=request.user, company=request.company)
    except Pazanda.DoesNotExist:
        messages.error(request, "Profil topilmadi. Administrator bilan bog'laning.")
        return redirect('main')
    mahsulotlar = Mahsulot.objects.filter(company=request.company)
    yetkazuvchilar = YetkazibBeruvchi.objects.filter(company=request.company, user__type='yetkazib_beruvchi')

    if request.method == "POST":
        mahsulot_id = request.POST.get('mahsulot')
        miqdor_str = request.POST.get('miqdor')
        yetkazuvchi_id = request.POST.get('yetkazuvchi')

        if not mahsulot_id or not miqdor_str or not yetkazuvchi_id:
            messages.error(request, "Barcha maydonlarni to'ldiring.")
            return render(request, 'add_yuklama.html', {'mahsulotlar': mahsulotlar, 'yetkazuvchilar': yetkazuvchilar})

        try:
            miqdor = float(miqdor_str)
        except ValueError:
            messages.error(request, "Miqdor raqam bo'lishi kerak.")
            return render(request, 'add_yuklama.html', {'mahsulotlar': mahsulotlar, 'yetkazuvchilar': yetkazuvchilar})

        if miqdor <= 0:
            messages.error(request, "Miqdor musbat bo'lishi kerak.")
            return render(request, 'add_yuklama.html', {'mahsulotlar': mahsulotlar, 'yetkazuvchilar': yetkazuvchilar})

        try:
            mahsulot = Mahsulot.objects.get(id=mahsulot_id, company=request.company)
        except Mahsulot.DoesNotExist:
            messages.error(request, "Mahsulot topilmadi.")
            return render(request, 'add_yuklama.html', {'mahsulotlar': mahsulotlar, 'yetkazuvchilar': yetkazuvchilar})

        try:
            yetkazuvchi = YetkazibBeruvchi.objects.get(id=yetkazuvchi_id, company=request.company)
        except YetkazibBeruvchi.DoesNotExist:
            messages.error(request, "Yetkazuvchi topilmadi.")
            return render(request, 'add_yuklama.html', {'mahsulotlar': mahsulotlar, 'yetkazuvchilar': yetkazuvchilar})
        

        yuklama = YuklamaSorov.objects.create(
            pazanda=pazanda,
            mahsulot=mahsulot,
            user=yetkazuvchi,
            miqdor=miqdor,
            mode='waiting',
            company=request.company
        )
        send_ws_notification(
            request.company.subdomain,
            "Yangi yuklama",
            f"{pazanda.tuliq_ismi} {yetkazuvchi.tuliq_ismi} uchun {miqdor:g} ta {mahsulot.nomi} so'radi.",
            "success",
            refresh=True
        )
        return redirect('main')

    return render(request, 'pzyuklama.html', {
        'mahsulotlar': mahsulotlar,
        'yetkazuvchilar': yetkazuvchilar,
    })
@login_required(login_url='login')
def sotish(request):
    
    if request.user.type in ['yetkazib_beruvchi', 'savdogar']:
        try:
            yt = YetkazibBeruvchi.objects.get(user=request.user, company=request.company)
        except YetkazibBeruvchi.DoesNotExist:
            messages.error(request, "Profil topilmadi. Administrator bilan bog'laning.")
            return redirect('main')
        usr=request.user
        credit_terms = list(allowed_credit_terms())
        if request.user.type == 'savdogar':
            flags = get_feature_flags(request.company)
            if not flags.get('has_savdogar_sales'):
                messages.error(request, "Savdogar savdo moduli tarifda ochilmagan. Ega billing/tarif sahifasidan $10 modulni yoqishi kerak.")
                return redirect('main')
            if not (request.company.savdogar_contract_text or '').strip():
                messages.error(request, "Ega avval savdogar shartnoma matnini shakllantirishi kerak. Shundan keyin savdogar savdo qila oladi.")
                return redirect('main')
        if request.user.type == 'savdogar':
            mahsulotlar = [
                {
                    'nom': m.nomi,
                    'miqdor': m.miqdori,
                    'turi': m.turi,
                    'narx': m.narxi,
                }
                for m in Mahsulot.objects.filter(company=request.company, is_savdogar_product=True).order_by('nomi')
            ]
        else:
            mahsulotlar = mahsulotlar_miqdori(yt.mahsulotlar, company=request.company)
        xaridorlar=HaridorDukon.objects.filter(company=request.company)
        
        if request.method == "POST":
            from django.db import transaction
            try:
              with transaction.atomic():
                yt = YetkazibBeruvchi.objects.select_for_update().get(user=request.user)
                company = request.company
                if request.user.type == 'savdogar':
                    company = Company.objects.select_for_update().get(pk=request.company.pk)
                    try:
                        requested_contract_number = int(request.POST.get('contract_number_preview') or 0)
                    except ValueError:
                        requested_contract_number = 0
                    if requested_contract_number != company.savdogar_contract_next_number:
                        messages.error(request, "Shartnoma raqami yangilangan. Shartnomani qayta yuklab olib, savdoni qayta saqlang.")
                        return redirect('sotish')
                if request.user.type == 'savdogar':
                    mahsulotlar = [
                        {
                            'nom': m.nomi,
                            'miqdor': m.miqdori,
                            'turi': m.turi,
                            'narx': m.narxi,
                            'object': m,
                        }
                        for m in Mahsulot.objects.select_for_update().filter(company=request.company, is_savdogar_product=True).order_by('nomi')
                    ]
                else:
                    # Re-parse mahsulotlar inside the locked transaction to get latest string
                    mahsulotlar = mahsulotlar_miqdori(yt.mahsulotlar, company=request.company)
                
                rasm=request.FILES.get('rasm')
                turi =request.POST.get('st')
                contract_pdf = request.FILES.get('contract_pdf')
                signed_contract_scan = request.FILES.get('signed_contract_scan')
                customer_passport_image = request.FILES.get('customer_passport_image')
                haridor = None
                if request.user.type != 'savdogar':
                    haridor = HaridorDukon.objects.get(id=request.POST.get('haridor'), company=request.company)
                oluvchi=(request.POST.get('oluvchi') or '').strip()
                if request.user.type == 'savdogar' and not oluvchi:
                    messages.error(request, "Savdogar savdosi uchun mijoz ism-familyasini kiriting.")
                    return redirect('sotish')

                if request.user.type == 'savdogar' and (not contract_pdf or not signed_contract_scan or not customer_passport_image):
                    messages.error(request, "Savdogar har bir savdoda PDF shartnoma, imzolangan skan va ID karta/pasport rasmini biriktirishi shart.")
                    return redirect('sotish')

                if request.user.type == 'savdogar':
                    from django.core.exceptions import ValidationError
                    from .utils import validate_uploaded_file
                    try:
                        validate_uploaded_file(contract_pdf, allowed_ext=('.pdf',))
                        validate_uploaded_file(signed_contract_scan, allowed_ext=('.pdf', '.jpg', '.jpeg', '.png'))
                    except ValidationError as e:
                        messages.error(request, str(e.message) if hasattr(e, 'message') else str(e))
                        return redirect('sotish')

                credit_months = None
                credit_markup = 0
                credit_total = None
                credit_contract_text = ""
                down_payment = 0
                if turi == 'nasiya':
                    if not company.credit_sales_enabled:
                        messages.error(request, "Bu firmada nasiya savdo o'chirilgan.")
                        return redirect('sotish')
                    try:
                        credit_months = int(request.POST.get('credit_term_months') or 0)
                        credit_total, credit_markup = calculate_credit_total(0, credit_months)
                        down_payment = float(request.POST.get('credit_down_payment') or 0)
                    except ValueError as exc:
                        messages.error(request, str(exc))
                        return redirect('sotish')

                # QR/Serial — "unit" granularity mahsulotlar uchun savdo yopishda
                # skanerlangan/kiritilgan serial kodlari majburiy va oldindan
                # tekshiriladi (hech qanday zaxira o'zgarishidan oldin).
                expected_serial_holati = 'chiqarilgan' if request.user.type == 'yetkazib_beruvchi' else 'omborda'
                serial_ids_by_nom = {}
                for m in mahsulotlar:
                    nom = m['nom'] if isinstance(m, dict) else m.nom
                    miqdor = request.POST.get(f'miqdor_{nom}')
                    if not miqdor or miqdor == '0':
                        continue
                    mahsulot_for_check = Mahsulot.objects.filter(nomi=nom, company=request.company).first()
                    if not mahsulot_for_check or mahsulot_for_check.serial_granularity != 'unit':
                        continue
                    miqdor_float = float(miqdor)
                    kodlar_raw = request.POST.get(f'serial_kodlari_{nom}', '')
                    kodlar = [k.strip() for k in kodlar_raw.replace(',', '\n').splitlines() if k.strip()]
                    if len(kodlar) != int(miqdor_float):
                        messages.error(
                            request,
                            f"{nom} uchun {int(miqdor_float)} ta serial (QR) kodi kiritilishi/skanerlanishi shart, {len(kodlar)} ta kiritildi.",
                        )
                        return redirect('sotish')
                    serials_qs = Serial.objects.select_for_update().filter(
                        company=request.company, mahsulot=mahsulot_for_check,
                        kod__in=kodlar, holati=expected_serial_holati, savdo__isnull=True,
                    )
                    if request.user.type == 'yetkazib_beruvchi':
                        # Faqat shu yetkazib beruvchi o'zi yuklamada olib
                        # chiqqan donalarni sotishi mumkin — boshqa
                        # yetkazuvchiga tegishli (yoki hali umuman
                        # chiqarilmagan) QR kod kiritilsa qabul qilinmaydi.
                        serials_qs = serials_qs.filter(yetkazib_beruvchi=yt)
                    found_kodlar = set(serials_qs.values_list('kod', flat=True))
                    missing = [k for k in kodlar if k not in found_kodlar]
                    if missing:
                        # Har bir "yaroqsiz" kod uchun ANIQ sababini topib
                        # ko'rsatamiz — ayniqsa yetkazib beruvchi hali
                        # Desktop Agent orqali yuklamaga olmagan (holati
                        # hamon "omborda") mahsulotni to'g'ridan-to'g'ri
                        # sotishga urinsa, oldingi umumiy "yaroqsiz yoki
                        # ishlatilgan" xabari chalkashtirar edi — ega bilan
                        # kelishilgan aniqlashtirish.
                        real_serials = {
                            s.kod: s for s in Serial.objects.filter(
                                company=request.company, mahsulot=mahsulot_for_check, kod__in=missing,
                            ).select_related('yetkazib_beruvchi')
                        }
                        sabablar = []
                        for kod in missing[:5]:
                            s = real_serials.get(kod)
                            if not s:
                                sabablar.append(f"{kod} — topilmadi")
                            elif s.savdo_id:
                                sabablar.append(f"{kod} — allaqachon sotilgan")
                            elif s.holati == 'omborda' and request.user.type == 'yetkazib_beruvchi':
                                sabablar.append(f"{kod} — hali agentda ro'yxatdan o'tkazilmagan (yuklamaga olinmagan, omborda turibdi)")
                            elif s.holati == 'chiqarilgan' and request.user.type == 'yetkazib_beruvchi':
                                sabablar.append(f"{kod} — boshqa yetkazib beruvchiga tegishli")
                            else:
                                sabablar.append(f"{kod} — noto'g'ri holatda ({s.get_holati_display()})")
                        messages.error(
                            request,
                            f"{nom} uchun quyidagi serial kodlari qabul qilinmadi: {'; '.join(sabablar)}.",
                        )
                        return redirect('sotish')
                    if len(found_kodlar) != len(set(kodlar)):
                        messages.error(request, f"{nom} uchun takrorlangan serial kodlari topildi.")
                        return redirect('sotish')
                    serial_ids_by_nom[nom] = list(serials_qs.values_list('id', flat=True))

                sotilganlar = []
                for m in mahsulotlar:
                    nom = m['nom'] if isinstance(m, dict) else m.nom
                    mavjud = float(m['miqdor'] if isinstance(m, dict) else m.miqdor)
                    miqdor = request.POST.get(f'miqdor_{nom}')
                    if miqdor and miqdor != '0':
                        miqdor_float = float(miqdor)
                        if miqdor_float > mavjud:
                            messages.error(request, f"{nom} uchun zaxirada yetarli miqdor yo'q.")
                            return redirect('sotish')
                        if request.user.type == 'savdogar':
                            mahsulot_obj = m['object']
                            mahsulot_obj.miqdori = mavjud - miqdor_float
                            mahsulot_obj.save(update_fields=['miqdori'])
                        else:
                            m.miqdor -= miqdor_float
                        sotilganlar.append((nom, miqdor))  # Logging uchun

                svd = None
                if len(sotilganlar) > 0:
                    txt=''
                    summa=0
                    foyda=0
                    ish_haqi_summasi=0
                    sale_items = []
                    for s in sotilganlar:
                        mxs = Mahsulot.objects.filter(nomi=s[0], company=request.company).first()
                        if not mxs:
                            # Skip if product was deleted
                            continue
                        txt+=f'{s[0]} {s[1]} {mxs.narxi},'
                        qty = float(s[1])
                        price = float(mxs.narxi)
                        cost = float(mxs.tannarx or 0)
                        summa+=qty*price
                        foyda+=qty*(price-cost)
                        # Savdogar/yetkazib beruvchiga tegishli ish haqi — mahsulotning
                        # sotuv_ish_haqi_narxi'siga qarab (allaqachon tannarx orqali
                        # foydadan ayirilgan, bu shunchaki KIMGA qancha tegishli
                        # ekanini ko'rsatuvchi alohida yig'indi).
                        ish_haqi_summasi += qty * float(mxs.sotuv_ish_haqi_narxi or 0)
                        sale_items.append({
                            'name': mxs.nomi,
                            'qty': qty,
                            'unit': mxs.turi.nomi if mxs.turi else '',
                            'price': price,
                        })
                    seller_lat = yt.last_lat if request.user.type == 'yetkazib_beruvchi' else None
                    seller_lng = yt.last_lng if request.user.type == 'yetkazib_beruvchi' else None

                    sale_summa = summa
                    if turi == 'nasiya':
                        sale_summa, credit_markup = calculate_credit_total(summa, credit_months)
                        if down_payment < 0 or down_payment > sale_summa:
                            messages.error(request, "Boshlang'ich to'lov yakuniy nasiya summadan katta bo'lishi mumkin emas.")
                            raise ValueError("invalid_down_payment")
                        credit_contract_text = build_credit_contract(
                            company,
                            oluvchi,
                            summa,
                            sale_summa,
                            credit_months,
                            credit_markup,
                            contract_number=requested_contract_number if request.user.type == 'savdogar' else None,
                            items=sale_items,
                            payment_type=turi,
                            down_payment=down_payment,
                        )
                    contract_number = requested_contract_number if request.user.type == 'savdogar' else None
                    
                    if turi=='nasiya':
                        svd=Savdo.objects.create(
                            yetkazib_beruvchi=yt,
                            savdogar=request.user if request.user.type == 'savdogar' else None,
                            haridor_dukon=haridor,
                            smm=txt,
                            smr=rasm,
                            oluvchining_ismi=oluvchi,
                            tulandi=down_payment >= sale_summa,
                            tasdiq_kutilmoqda=False,
                            st=turi,
                            contract_number=contract_number,
                            base_summa=summa,
                            summa=sale_summa,
                            foyda=foyda,
                            ish_haqi_summasi=ish_haqi_summasi,
                            credit_down_payment=down_payment,
                            credit_term_months=credit_months,
                            credit_markup_percent=credit_markup,
                            credit_due_date=credit_due_date(credit_months),
                            credit_contract_text=credit_contract_text,
                            contract_pdf=contract_pdf,
                            signed_contract_scan=signed_contract_scan,
                            customer_passport_image=customer_passport_image,
                            company=request.company,
                            latitude=seller_lat,
                            longitude=seller_lng
                        )
                        if down_payment > 0:
                            NasiyaTolov.objects.create(
                                savdo=svd,
                                company=request.company,
                                tolov_summasi=down_payment,
                                izoh="Boshlang'ich to'lov",
                                qabul_qilgan_user=request.user,
                            )
                    else:
                        svd=Savdo.objects.create(
                            yetkazib_beruvchi=yt,
                            savdogar=request.user if request.user.type == 'savdogar' else None,
                            haridor_dukon=haridor,
                            smm=txt,
                            smr=rasm,
                            oluvchining_ismi=oluvchi,
                            tulandi=True,
                            tasdiq_kutilmoqda=True,
                            st=turi,
                            contract_number=contract_number,
                            base_summa=summa,
                            summa=summa,
                            foyda=foyda,
                            ish_haqi_summasi=ish_haqi_summasi,
                            contract_pdf=contract_pdf,
                            signed_contract_scan=signed_contract_scan,
                            customer_passport_image=customer_passport_image,
                            company=request.company,
                            latitude=seller_lat,
                            longitude=seller_lng
                        )

                    # QR/Serial — validatsiyadan o'tgan seriallar shu savdoga bog'lanadi
                    # (SerialHarakat'ga "kim sotgan" logi bilan birga)
                    for serial_ids in serial_ids_by_nom.values():
                        qr_service.mark_serials_sotilgan(serial_ids, svd, actor=request.user)

                    if request.user.type == 'savdogar':
                        Company.objects.filter(pk=company.pk).update(
                            savdogar_contract_next_number=F('savdogar_contract_next_number') + 1
                        )
        
                    if request.user.type == 'yetkazib_beruvchi':
                        sotishm(txt,yt)
                    # Activity log
                    customer_label = haridor.nomi if haridor else oluvchi
                    AmalLog.objects.create(
                        user=request.user,
                        company=request.company,
                        amal_shifri=f"savdo_yaratish|{customer_label}|{sale_summa}"
                    )
                    
                    # WebSocket Notification
                    send_ws_notification(
                        request.company.subdomain,
                        "Yangi Savdo",
                        f"{yt.tuliq_ismi} {customer_label}ga {sale_summa} so'mlik savdo qildi.",
                        'info'
                    )

                    # Update deliverer location if provided
                    lat = request.POST.get('latitude')
                    lng = request.POST.get('longitude')
                    if request.user.type == 'yetkazib_beruvchi' and lat and lng:
                        yt.last_lat = float(lat)
                        yt.last_lng = float(lng)
                        yt.last_active = timezone.now()
                        yt.save()
                        from .models import LocationHistory
                        LocationHistory.objects.create(
                            yetkazib_beruvchi=yt,
                            company=request.company,
                            lat=float(lat),
                            lng=float(lng)
                        )

                # Landing sahifada va'da qilingan "har bir sotuvdan QR kodli
                # chek" haqiqatan ko'rinadigan bo'lishi uchun — savdo
                # muvaffaqiyatli yaratilgan bo'lsa, darhol shu savdoning QR
                # chekiga yo'naltiriladi (avval buni hech kim ko'rmasdi,
                # to'g'ridan-to'g'ri dashboardga qaytarilardi).
                if svd is not None:
                    messages.success(request, "Savdo saqlandi — QR kodli chek tayyor.")
                    return redirect('savdo_chek', savdo_id=svd.id)
                return redirect('main')
            except ValueError as e:
                if str(e) != 'invalid_down_payment':
                    messages.error(request, "Noto'g'ri qiymat kiritildi.")
                return redirect('sotish')
            # Istasa: Savdo modelga yozish
            return redirect('main')
    else:
        return redirect('main')

    template_name = 'sgsot.html' if request.user.type == 'savdogar' else 'ytsot.html'
    unit_serial_products = list(
        Mahsulot.objects.filter(company=request.company, serial_granularity='unit').values_list('nomi', flat=True)
    )
    # QR-skanerda serverga qaysi mahsulotga tekshirilayotgani ma'lum
    # bo'lishi uchun har bir qatorga mahsulot id'si biriktiriladi
    # (`check_sale_serial`, sahifada JS shu id bilan chaqiradi).
    id_by_nom = dict(
        Mahsulot.objects.filter(company=request.company).values_list('nomi', 'id')
    )
    for m in mahsulotlar:
        nom = m['nom'] if isinstance(m, dict) else m.nom
        if isinstance(m, dict):
            m['id'] = id_by_nom.get(nom)
        else:
            m.id = id_by_nom.get(nom)
    return render(request, template_name, {
        'mahsulotlar': mahsulotlar,
        'haridorlar': xaridorlar,
        'credit_terms': credit_terms,
        'next_contract_number': request.company.savdogar_contract_next_number,
        'unit_serial_products': unit_serial_products,
    })


# ============================================
# API Endpoint for Browser Notifications
# ============================================
from django.views.decorators.http import require_http_methods


def _extract_serial_kod(raw: str) -> str:
    """QR ichidagi matn to'liq public URL (`/p/<kod>/`) yoki xom kod
    bo'lishi mumkin — ikkalasini ham bir xilda qabul qilish uchun."""
    raw = (raw or '').strip()
    if '/' in raw:
        parts = [p for p in raw.split('/') if p]
        if parts:
            return parts[-1]
    return raw


@login_required(login_url='login')
@require_http_methods(["GET"])
def check_sale_serial(request):
    """Sotuv sahifasida (`ytsot.html`/`sgsot.html`) telefon kamerasi bilan
    QR skanerlanganda, kod ro'yxatga (yashirin maydonga) qo'shilishidan
    OLDIN chaqiriladi — begona/mos kelmaydigan QR kodlar sukut bo'yicha
    qabul qilinib, faqat "Tasdiqlash"da rad etilishi (yomon UX — foydalanuvchi
    nima xato ekanini darhol bilmaydi) o'rniga, shu yerda darhol tekshiriladi:
    kod mavjudmi, aynan shu mahsulotga tegishlimi va — yetkazib beruvchi
    bo'lsa — aynan shu xodim o'z yuklamasida olib chiqqan donami."""
    kod = _extract_serial_kod(request.GET.get('kod', ''))
    mahsulot_id = request.GET.get('mahsulot_id')
    if not kod or not mahsulot_id:
        return JsonResponse({'valid': False, 'detail': "Parametrlar yetishmayapti."}, status=400)

    try:
        mahsulot = Mahsulot.objects.get(id=mahsulot_id, company=request.company)
    except (Mahsulot.DoesNotExist, ValueError):
        return JsonResponse({'valid': False, 'detail': "Mahsulot topilmadi."}, status=404)

    expected_holati = 'chiqarilgan' if request.user.type == 'yetkazib_beruvchi' else 'omborda'
    serial = Serial.objects.filter(
        company=request.company, kod=kod, holati=expected_holati, savdo__isnull=True,
    ).select_related('mahsulot').first()
    if not serial:
        return JsonResponse({'valid': False, 'detail': "Bu QR kod topilmadi yoki allaqachon ishlatilgan."})

    if serial.mahsulot_id != mahsulot.id:
        return JsonResponse({
            'valid': False,
            'detail': f"Bu QR kod \"{serial.mahsulot.nomi}\"ga tegishli, \"{mahsulot.nomi}\"ga emas.",
        })

    if request.user.type == 'yetkazib_beruvchi':
        yt = YetkazibBeruvchi.objects.filter(user=request.user, company=request.company).first()
        if not yt or serial.yetkazib_beruvchi_id != yt.id:
            return JsonResponse({
                'valid': False,
                'detail': "Bu dona sizning yuklamangizda emas — boshqa yetkazuvchiga tegishli.",
            })

    return JsonResponse({'valid': True, 'kod': kod, 'mahsulot': serial.mahsulot.nomi})


@login_required(login_url='login')
@require_http_methods(["GET"])
def check_new_deliveries(request):
    """
    API endpoint to check for new delivery requests for delivery personnel.
    Returns JSON with count and details of new deliveries since last check.
    """
    if request.user.type != 'yetkazib_beruvchi':
        return JsonResponse({'success': False, 'count': 0, 'deliveries': []}, status=200)
    
    try:
        yetkazuvchi = YetkazibBeruvchi.objects.get(user=request.user, company=request.company)

        # Get last check time from session or default to 1 minute ago
        last_check_str = request.session.get('last_delivery_check')
        if last_check_str:
            from datetime import datetime
            last_check = timezone.make_aware(datetime.fromisoformat(last_check_str))
        else:
            # Default: check last 1 minute
            last_check = timezone.now() - timezone.timedelta(minutes=1)
        
        # Get new delivery requests since last check
        new_deliveries = YuklamaSorov.objects.filter(
            user=yetkazuvchi,
            sana__gt=last_check,
            mode='waiting',
            tasdiq=False
        ).select_related('pazanda__user').order_by('-sana')
        
        deliveries_data = []
        for delivery in new_deliveries:
            pazanda_name = delivery.pazanda.user.tuliq_ismi if delivery.pazanda and delivery.pazanda.user else "Noma'lum"
            deliveries_data.append({
                'id': delivery.id,
                'pazanda': pazanda_name,
                'sana': delivery.sana.strftime('%H:%M'),
                'mahsulot': delivery.mahsulot.nomi if delivery.mahsulot else "Mahsulot",
                'miqdor': delivery.miqdor
            })
        
        # Update last check time
        request.session['last_delivery_check'] = timezone.now().isoformat()
        
        return JsonResponse({
            'success': True,
            'count': len(deliveries_data),
            'deliveries': deliveries_data
        })
        
    except YetkazibBeruvchi.DoesNotExist:
        return JsonResponse({'success': False, 'count': 0, 'deliveries': []}, status=200)
    except Exception as e:
        return JsonResponse({'success': False, 'count': 0, 'deliveries': [], 'error': str(e)}, status=200)


# ─── MVP: Ishlab chiqaruvchi — So'rovlar tarixi ──────────────────────────────
@login_required(login_url='login')
def pz_sorov_tarixi(request):
    """Ishlab chiqaruvchi uchun: o'zi yuborgan barcha YuklamaSorov larni ko'rish."""
    if request.user.type not in ['pazanda', 'ishlab_chiqaruvchi']:
        return redirect('main')

    try:
        pazanda = Pazanda.objects.get(user=request.user, company=request.company)
    except Pazanda.DoesNotExist:
        messages.error(request, "Profil topilmadi. Administrator bilan bog'laning.")
        return redirect('main')
    filter_val = request.GET.get('filter', 'all')

    qs = YuklamaSorov.objects.filter(pazanda=pazanda).order_by('-sana')

    if filter_val == 'waiting':
        qs = qs.filter(tasdiq=False, mode='waiting')
    elif filter_val == 'approved':
        qs = qs.filter(tasdiq=True)
    elif filter_val == 'rejected':
        qs = qs.filter(mode='rejected')

    # Summary counts
    all_qs = YuklamaSorov.objects.filter(pazanda=pazanda)
    context = {
        'sorovlar': qs,
        'jami': all_qs.count(),
        'tasdiqlangan': all_qs.filter(tasdiq=True).count(),
        'kutilmoqda': all_qs.filter(tasdiq=False, mode='waiting').count(),
        'rad_etilgan': all_qs.filter(mode='rejected').count(),
    }
    return render(request, 'pzsorovlar.html', context)


# ─── MVP: Yetkazuvchi Hisobot ─────────────────────────────────────────────────
@login_required(login_url='login')
def yetkazuvchi_hisobot(request, username):
    """Admin yoki yetkazib beruvchining o'zi uchun: to'liq hisobot."""
    # Permission check: Only 'ega' or the user themselves
    if request.user.type != 'ega' and request.user.username != username:
        return redirect('main')

    target_user = get_object_or_404(User, username=username, type='yetkazib_beruvchi', company=request.company)
    yb = get_object_or_404(YetkazibBeruvchi, user=target_user)

    # Determine base template
    base_template = 'egabase.html' if request.user.type == 'ega' else 'ytbase.html'

    from django.db.models import Sum as DSum
    import datetime as _dt

    now = timezone.localtime()

    # Date filtering
    from_date_str = request.GET.get('from')
    to_date_str   = request.GET.get('to')

    try:
        from_date = _dt.date.fromisoformat(from_date_str) if from_date_str else now.date().replace(day=1)
        to_date   = _dt.date.fromisoformat(to_date_str)   if to_date_str   else now.date()
    except ValueError:
        from_date = now.date().replace(day=1)
        to_date   = now.date()

    from_dt = timezone.make_aware(_dt.datetime.combine(from_date, _dt.time.min))
    to_dt   = timezone.make_aware(_dt.datetime.combine(to_date,   _dt.time.max))

    # Base queryset for current filters
    savdolar_qs = Savdo.objects.filter(
        yetkazib_beruvchi=yb,
        vaqt_sana__range=(from_dt, to_dt)
    )

    # Filter by customer if provided
    current_customer_id = request.GET.get('customer')
    if current_customer_id:
        savdolar_qs = savdolar_qs.filter(haridor_dukon_id=current_customer_id)

    savdolar_qs = savdolar_qs.order_by('-vaqt_sana')

    # Total sum for filtered period and customer (before pagination)
    savdolar_jami = savdolar_qs.aggregate(t=DSum('summa'))['t'] or 0

    # Pagination
    paginator = Paginator(savdolar_qs, 20)  # 20 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Customers who have sales with this delivery person (for filter dropdown)
    active_customers = HaridorDukon.objects.filter(savdo__yetkazib_beruvchi=yb).distinct()

    # Stats
    today_start = timezone.make_aware(_dt.datetime.combine(now.date(), _dt.time.min))
    month_start = timezone.make_aware(_dt.datetime.combine(now.date().replace(day=1), _dt.time.min))

    bugun_savdo = Savdo.objects.filter(yetkazib_beruvchi=yb, vaqt_sana__gte=today_start).aggregate(t=DSum('summa'))['t'] or 0
    oy_savdo    = Savdo.objects.filter(yetkazib_beruvchi=yb, vaqt_sana__gte=month_start).aggregate(t=DSum('summa'))['t'] or 0

    # Nasiya qarz
    nasiya_qarz = Savdo.objects.filter(yetkazib_beruvchi=yb, st='nasiya', tulandi=False).aggregate(t=DSum('summa'))['t'] or 0

    # Zaxira (legacy)
    from .functions import mahsulotlar_miqdori
    zaxira = mahsulotlar_miqdori(yb.mahsulotlar) or []

    # Excel Export Logic
    if request.GET.get('export') == 'xlsx':
        import pandas as pd
        from .utils import export_to_excel, format_product_string
        rows = []
        for s in savdolar_qs:
            lt = timezone.localtime(s.vaqt_sana)
            rows.append({
                'Sana': lt.strftime('%Y-%m-%d'),
                'Vaqt': lt.strftime('%H:%M'),
                'Haridor': s.haridor_dukon.nomi if s.haridor_dukon else "-",
                'Mahsulotlar': format_product_string(s.smm, request.company),
                'Summa': float(s.summa),
                'To\'lov turi': s.get_st_display(),
                'To\'langan': "Ha" if s.tulandi else "Yo'q"
            })
        
        df = pd.DataFrame(rows)
        header_info = {
            'title': f"Hisobot - {yb.user.tuliq_ismi}",
            'date_range': f"{from_date} dan {to_date} gacha"
        }
        filename = f"hisobot_{yb.user.username}_{from_date}_{to_date}_{timezone.now().strftime('%H%M%S')}.xlsx"
        return export_to_excel(df, filename, header_info)

    context = {
        'yb': yb,
        'page_obj': page_obj,
        'savdolar_jami': savdolar_jami,
        'jami_savdo_soni': Savdo.objects.filter(yetkazib_beruvchi=yb).count(),
        'bugun_savdo': bugun_savdo,
        'oy_savdo': oy_savdo,
        'nasiya_qarz': nasiya_qarz,
        'zaxira': zaxira,
        'from_date': from_date.isoformat(),
        'to_date': to_date.isoformat(),
        'active_customers': active_customers,
        'current_customer_id': current_customer_id,
        'base_template': base_template,
    }
    return render(request, 'yt_hisobot.html', context)


@login_required(login_url='login')
def pazanda_hisobot(request, username):
    """Admin yoki ishlab chiqaruvchining o'zi uchun: to'liq hisobot."""
    # Permission check: Only 'ega' or the user themselves
    if request.user.type != 'ega' and request.user.username != username:
        return redirect('main')

    target_user = get_object_or_404(User, username=username, type__in=['pazanda', 'ishlab_chiqaruvchi'], company=request.company)
    pz = get_object_or_404(Pazanda, user=target_user)

    # Determine base template
    base_template = 'egabase.html' if request.user.type == 'ega' else 'pzbase.html'

    from django.db.models import Sum as DSum
    import datetime as _dt

    now = timezone.localtime()

    # Date filtering
    from_date_str = request.GET.get('from')
    to_date_str   = request.GET.get('to')

    try:
        from_date = _dt.date.fromisoformat(from_date_str) if from_date_str else now.date().replace(day=1)
        to_date   = _dt.date.fromisoformat(to_date_str)   if to_date_str   else now.date()
    except ValueError:
        from_date = now.date().replace(day=1)
        to_date   = now.date()

    from_dt = timezone.make_aware(_dt.datetime.combine(from_date, _dt.time.min))
    to_dt   = timezone.make_aware(_dt.datetime.combine(to_date,   _dt.time.max))

    # Production (Miqdor Qoshish)
    miqdorlar_qs = MiqdorQoshish.objects.filter(
        company=request.company,
        pazanda=pz,
        vaqt_sana__range=(from_dt, to_dt)
    ).order_by('-vaqt_sana')

    # Shipments (Yuklama Sorovlari)
    yuklamalar_qs = YuklamaSorov.objects.filter(
        pazanda=pz,
        sana__range=(from_dt, to_dt)
    ).order_by('-sana')

    # Pagination for production (main table)
    paginator = Paginator(miqdorlar_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Stats
    today_start = timezone.make_aware(_dt.datetime.combine(now.date(), _dt.time.min))
    bugun_miqdor = MiqdorQoshish.objects.filter(company=request.company, pazanda=pz, vaqt_sana__gte=today_start).aggregate(t=DSum('miqdor'))['t'] or 0
    bugun_yuklama = YuklamaSorov.objects.filter(pazanda=pz, sana__gte=today_start).aggregate(t=DSum('miqdor'))['t'] or 0

    # Ish haqi (mahsulot soniga qarab) — shu xodim uchun individual sozlangan
    # bo'lsa o'shani, aks holda firma standartini hisobga oladi.
    ish_haqi_turi_per_unit = effective_ish_haqi_turi(target_user, request.company) == 'per_unit'
    davr_ish_haqi = 0
    davr_jarima = 0
    if ish_haqi_turi_per_unit:
        davr_summalar = miqdorlar_qs.filter(tasdiqlangan=True).aggregate(
            ish_haqi=DSum('ish_haqi_summasi'), jarima=DSum('jarima_summasi'),
        )
        davr_ish_haqi = davr_summalar['ish_haqi'] or 0
        davr_jarima = davr_summalar['jarima'] or 0

    # Excel Export Logic
    if request.GET.get('export') == 'xlsx':
        import pandas as pd
        from .utils import export_to_excel
        rows = []
        for m in miqdorlar_qs:
            lt = timezone.localtime(m.vaqt_sana)
            rows.append({
                'Sana': lt.strftime('%Y-%m-%d'),
                'Vaqt': lt.strftime('%H:%M'),
                'Mahsulot': m.mahsulot.nomi if m.mahsulot else "-",
                'Miqdor': m.miqdor,
                'Izoh': m.ariza_text or ""
            })
        
        df = pd.DataFrame(rows)
        header_info = {
            'title': f"Hisobot - {pz.user.tuliq_ismi}",
            'date_range': f"{from_date} dan {to_date} gacha"
        }
        filename = f"pazanda_hisobot_{pz.user.username}_{from_date}_{to_date}_{timezone.now().strftime('%H%M%S')}.xlsx"
        return export_to_excel(df, filename, header_info)

    context = {
        'pz': pz,
        'page_obj': page_obj,
        'yuklamalar': yuklamalar_qs,
        'bugun_miqdor': bugun_miqdor,
        'bugun_yuklama': bugun_yuklama,
        'from_date': from_date.isoformat(),
        'to_date': to_date.isoformat(),
        'base_template': base_template,
        'ish_haqi_turi_per_unit': ish_haqi_turi_per_unit,
        'davr_ish_haqi': davr_ish_haqi,
        'davr_jarima': davr_jarima,
    }

    return render(request, 'pz_hisobot.html', context)


@login_required(login_url='login')
def yt_navigation(request):
    """
    Deliverer's dedicated navigation page.
    Shows all shops with Google/Yandex Maps links.
    """
    if request.user.type != 'yetkazib_beruvchi':
        return redirect('main')

    haridorlar = HaridorDukon.objects.filter(company=request.company).order_by('nomi')

    return render(request, 'ytnav.html', {
        'haridorlar': haridorlar
    })


def offline_page(request):
    """Service Worker offline fallback sahifasi."""
    return render(request, 'offline.html', status=200)


def service_worker_js(request):
    """sw.js ni root path dan serve qilish (SW scope uchun zarur)."""
    import os
    from django.conf import settings
    from django.http import FileResponse, Http404
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    if not os.path.exists(sw_path):
        raise Http404
    response = FileResponse(open(sw_path, 'rb'), content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


@login_required(login_url='login')
def download_desktop_agent(request):
    """Faqat Desktop Agent stansiyasi sotib olingan firma egasi uchun —
    superadmin yuklagan eng oxirgi StockFirmAgent.exe versiyasini
    yuklab beradi (`AgentRelease`, superadmin panelidan boshqariladi)."""
    if request.user.type != 'ega':
        messages.error(request, "Faqat firma egasi Desktop Agent dasturini yuklab olishi mumkin.")
        return redirect('main')
    if not request.company.custom_desktop_agent_stations:
        messages.error(request, "Sizning firmangizda Desktop Agent stansiyasi sotib olinmagan. Administrator bilan bog'laning.")
        return redirect('main')
    release = AgentRelease.objects.order_by('-created_at').first()
    if not release or not release.file:
        messages.error(request, "Hozircha Desktop Agent versiyasi yuklanmagan. Administrator bilan bog'laning.")
        return redirect('main')
    return redirect(release.file.url)


@login_required(login_url='login')
def agent_stations_status_api(request):
    """`egabase.html`dagi "Desktop Agent onlayn emas" banneri uchun
    ZAXIRA (fallback) yangilanish manbai — asosiy yo'l WebSocket orqali
    (`agent_heartbeat` hodisasi) DARHOL keladi, lekin kanal qatlami/
    tarmoq uzilishi sabab xabar yetib kelmasligi mumkin (real holatda
    ega tomonidan aniqlangan: sahifani qo'lda yangilamaguncha banner
    "onlayn emas" holida qolib ketardi). Shu sabab veb JS bu endpoint'ni
    davriy (~30s) so'raydi — `context_processors._safe_agent_stations_
    status` bilan bir xil hisob-kitob, faqat AJAX orqali."""
    if request.user.type != 'ega':
        return JsonResponse({'stations': []})
    from .context_processors import _safe_agent_stations_status
    return JsonResponse({'stations': _safe_agent_stations_status(request.company)})
