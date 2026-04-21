from django.shortcuts import render, get_list_or_404, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages 
from django.core.paginator import Paginator
from django.utils import timezone
from django.shortcuts import redirect
from .models import BACKUP_CHOICES, BillingPaymentLink, Plan, HaridorDukon, User, YetkazibBeruvchi, Pazanda, Mahsulot, MahsulotTuri, Savdo, YuklamaSorov, MiqdorQoshish, HaridorDukon, AmalLog, qaytarilgan_mahsulotlar, PlanRequest, ProductionMaterialRequest, StockHistory
from .functions import mahsulotlar_miqdori, makenewform, yuklama_maker, accptyuk, sotishm, sotuv_new_form ,yetkazuvchi_mahsulot_filter, get_bugungi_savdo_summ, add_spctoint
from .plan_utils import company_has_access
import datetime as dt
import json
from django.db.models import Count, Sum

def send_ws_notification(company_subdomain, title, message, type='info'):
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
                    "notification_type": type
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
    
    messages.success(request, "Tizim sozlash rejimi muvaffaqiyatli yakunlandi. Endi barcha xodimlar tizimdan foydalana oladi.")
    return redirect('main')



from .services.stock_service import (
    approve_miqdor_qoshish_service, 
    approve_yuklama_sorov_service,
    approve_material_request_service,
    reject_material_request_service,
)
from .services.auth_service import create_user_service, update_user_service
from .services.billing_service import (
    consume_billing_payment_link,
    create_billing_payment_link,
    get_billing_dashboard_data,
    get_company_dashboard_url,
    get_company_login_url,
)
from .analytics.services import get_dashboard_stats
from .credit_utils import CREDIT_TERM_MARKUPS, build_credit_terms

User = get_user_model()
# Create your views here.
from .bot_logic import verify_tg_link_token

def login(request):
    data={}
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
        user = authenticate(request, username=username, password=password)

        if user is not None:
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
                return redirect('super_dashboard')
            
            # Standard company user login
            user_company = getattr(user, 'company', None)
            if user_company and (user_company == request.company or is_tg_linking or is_session_linking):
                auth_login(request, user)
                if not request.company:
                    # Redirect to subdomain if logging in from landing
                    from django.conf import settings
                    return redirect(get_company_dashboard_url(user_company, getattr(settings, 'BASE_DOMAIN', 'stockfirm.uz')))
                return redirect('main')
            else:
                messages.error(request, "Siz ushbu firmaga tegishli emassiz!")
        else:
            messages.error(request, "Login yoki parol noto'g'ri!")

    return render(request, 'login.html',data)


@login_required(login_url='login')
def select_plan(request, plan_id):
    """Tarif tanlash uchun so'rov yuborish"""
    if request.user.type != 'ega':
        messages.error(request, "Faqat do'kon egasi tarifni o'zgartira oladi.")
        return redirect('main')
    
    plan = get_object_or_404(Plan, id=plan_id, is_active=True)
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
    
    messages.success(request, f"{plan.name} tarifi uchun so'rov yuborildi. Admin tasdiqlaganidan so'ng faollashadi.")
    return redirect('main')

@login_required(login_url='login')
@require_POST
def select_custom_plan(request):
    """Maxsus (Custom) tarif uchun so'rov yuborish"""
    if request.user.type != 'ega':
        messages.error(request, "Faqat do'kon egasi tarifni o'zgartira oladi.")
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
    backup_type = request.POST.get('backup_type', 'none')

    # Calculate Price
    price = 0
    if staff_count == 0: price += 55
    else: price += staff_count * 1

    if has_map: price += 20
    if has_bot: price += 5
    if has_analytics: price += 15

    if backup_type == 'monthly': price += 5
    elif backup_type == 'weekly': price += 15
    elif backup_type == 'daily': price += 30

    PlanRequest.objects.create(
        company=company,
        is_custom=True,
        custom_max_users=staff_count,
        custom_has_telegram_bot=has_bot,
        custom_has_analytics=has_analytics,
        custom_has_map=has_map,
        custom_backup_type=backup_type,
        custom_price=price,
        status='pending'
    )

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
    messages.success(request, "Sinov muddati uchun so'rov yuborildi. Tez orada tasdiqlanadi.")
    return redirect('main')


@login_required(login_url='login')
def billing_page(request):
    if request.user.type != 'ega':
        return redirect('main')

    billing_data = get_billing_dashboard_data(request.company)
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
    
    # Faqat tarif so'rovi (trial emas) kutilayotgan bo'lsa blok qilamiz
    if PlanRequest.objects.filter(company=request.company, status='pending', is_trial=False).exists():
        messages.warning(request, "Sizda kutilayotgan tarif so'rovi mavjud.")
        return redirect('main')
    
    # Trial eligibility
    from datetime import timedelta
    can_request_trial = False
    trial_pending = PlanRequest.objects.filter(company=request.company, is_trial=True, status='pending').exists()
    days_since_creation = (timezone.now() - request.company.created_at).days
    if (
        not request.company.has_used_trial
        and days_since_creation <= 10
        and not trial_pending
        and not request.company.is_on_trial
    ):
        can_request_trial = True
    
    plans = Plan.objects.filter(is_active=True).order_by('price')
    current_staff_count = User.objects.filter(company=request.company).exclude(type='ega').count()
    return render(request, 'select_plan_page.html', {
        'plans': plans,
        'backup_choices': BACKUP_CHOICES,
        'can_request_trial': can_request_trial,
        'trial_pending': trial_pending,
        'days_since_creation': days_since_creation,
        'current_staff_count': current_staff_count,
    })

@login_required(login_url='login')
def main(request):
    payload={}
    user=request.user
    
    if user.type in ['pazanda', 'ishlab_chiqaruvchi']:
        now = timezone.localtime()
        today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
        today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))
        pz = Pazanda.objects.get(user=request.user)
        payload['sorovlar'] = YuklamaSorov.objects.filter(company=request.company, pazanda=pz, mode='waiting').all()
        payload['zaxira_mahsulotlar']=Mahsulot.objects.filter(company=request.company, warehouse_type='finished')
        payload['material_sorovlar']=ProductionMaterialRequest.objects.filter(company=request.company, producer=pz)[:8]
        zapros=MiqdorQoshish.objects.filter(company=request.company, pazanda=pz,vaqt_sana__range=(today_start, today_end)).all()
        payload['qms']=len(zapros)
        payload['kunlik_miqdorlar'] = zapros
        return render(request, 'pazanda_dashboard.html',payload)
    elif user.type == 'yetkazib_beruvchi':
        if request.method == 'GET':
            yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=request.user).mahsulotlar) or []
            
            payload['yuklamalar'] = yuklamalar
            mahs=Mahsulot.objects.filter(company=request.company, warehouse_type='finished')
            payload['zaxira_mahsulotlar'] = mahs
            payload['lnmahs']=len(mahs)

            now = timezone.localtime()
            today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
            today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))

            reqyuklama = YuklamaSorov.objects.filter(company=request.company, user=YetkazibBeruvchi.objects.get(user=request.user), mode="waiting").all()
            # reqyuklama=YuklamaSorov.objects.filter(user=YetkazibBeruvchi.objects.get(user=request.user),tasdiq=False, mode='waiting',sana=dt.date.today() ).all()
            payload['reqyuklama'] = reqyuklama
            savdo=Savdo.objects.filter(company=request.company, yetkazib_beruvchi=YetkazibBeruvchi.objects.get(user=request.user),vaqt_sana__range=(today_start, today_end)).all()
            payload['savdo'] = savdo
            nfs=yetkazuvchi_mahsulot_filter(savdo)
            payload['nfs'] = nfs
            return render(request, 'yetkazuvchi_dashboard.html',payload)
        elif request.method == 'POST':
            if 'yk_id' in request.POST: 
                yk_id=request.POST.get('yk_id')
               
                if 'accept' in yk_id:
                    yk_id=yk_id.replace('accept','')
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
            yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=request.user).mahsulotlar) or []
            savdo=Savdo.objects.filter(yetkazib_beruvchi=YetkazibBeruvchi.objects.get(user=request.user))
            payload['savdo'] = savdo
            nfs=yetkazuvchi_mahsulot_filter(savdo)
            payload['nfs'] = nfs

            payload['yuklamalar'] = yuklamalar
            now = timezone.localtime()
            today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
            today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))

            reqyuklama = YuklamaSorov.objects.filter(company=request.company, user=YetkazibBeruvchi.objects.get(user=request.user), mode="waiting").all()
            savdo=Savdo.objects.filter(company=request.company, yetkazib_beruvchi=YetkazibBeruvchi.objects.get(user=request.user),vaqt_sana__range=(today_start, today_end)).all()
            payload['savdo'] = savdo
            # reqyuklama=YuklamaSorov.objects.filter(user=YetkazibBeruvchi.objects.get(user=request.user),tasdiq=False, mode='waiting',sana=dt.date.today() ).all()
            payload['reqyuklama'] = reqyuklama
            mahs=Mahsulot.objects.filter(company=request.company, warehouse_type='finished')
            payload['zaxira_mahsulotlar'] = mahs
            
            return render(request, 'yetkazuvchi_dashboard.html',payload)
    elif user.type == 'omborchi':
        if request.method == 'POST':
            request_id = request.POST.get('material_request_id')
            if request_id:
                if 'approve' in request.POST:
                    success, message = approve_material_request_service(request_id, request.user)
                elif 'reject' in request.POST:
                    success, message = reject_material_request_service(request_id, request.user)
                else:
                    success, message = False, "Amal noto'g'ri tanlandi."

                if success:
                    messages.success(request, message)
                else:
                    messages.error(request, message)
                return redirect('main')

        payload['finished_products'] = Mahsulot.objects.filter(
            company=request.company,
            warehouse_type='finished'
        ).order_by('nomi')
        payload['materials'] = Mahsulot.objects.filter(
            company=request.company,
            warehouse_type='semi_finished'
        ).order_by('nomi')
        payload['pending_material_requests'] = ProductionMaterialRequest.objects.filter(
            company=request.company,
            status='waiting'
        ).select_related('producer__user', 'material')[:30]
        payload['recent_material_requests'] = ProductionMaterialRequest.objects.filter(
            company=request.company
        ).select_related('producer__user', 'material', 'reviewed_by')[:20]
        return render(request, 'warehouse_dashboard.html', payload)
    elif user.type == 'savdogar':
        now = timezone.localtime()
        today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
        month_start = timezone.make_aware(dt.datetime.combine(now.date().replace(day=1), dt.time.min))
        today_sales = Savdo.objects.filter(company=request.company, savdogar=request.user, vaqt_sana__gte=today_start)
        month_sales = Savdo.objects.filter(company=request.company, savdogar=request.user, vaqt_sana__gte=month_start)
        payload['today_sales_count'] = today_sales.count()
        payload['today_sales_amount'] = today_sales.aggregate(t=Sum('summa'))['t'] or 0
        payload['month_sales_amount'] = month_sales.aggregate(t=Sum('summa'))['t'] or 0
        payload['nasiya_count'] = Savdo.objects.filter(company=request.company, savdogar=request.user, st='nasiya', tulandi=False).count()
        payload['recent_sales'] = Savdo.objects.filter(company=request.company, savdogar=request.user).select_related('haridor_dukon').order_by('-vaqt_sana')[:8]
        payload['products'] = Mahsulot.objects.filter(company=request.company, warehouse_type='finished').order_by('nomi')[:10]
        return render(request, 'savdogar_dashboard.html', payload)
            
    
    hodims = User.objects.filter(company=request.company).exclude(type='ega').order_by('-date_joined')[:6]  # Faqat 6 ta
    mahs = Mahsulot.objects.filter(company=request.company).order_by('nomi')[:6]  # Faqat 6 ta
    
    # Jami sonlar
    jami_hodimlar = User.objects.filter(company=request.company).exclude(type='ega').count()
    jami_mahsulotlar = Mahsulot.objects.filter(company=request.company).count()
    
    payload['mahsulotlar'] = mahs
    payload['hodims'] = hodims
    
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
        payload['plans'] = Plan.objects.filter(is_active=True).order_by('price')
        payload['backup_choices'] = BACKUP_CHOICES
        payload['has_pending_request'] = PlanRequest.objects.filter(company=request.company, status='pending').exists()
    
    return render(request, 'main.html', payload)

@login_required(login_url='login')
def logout_view(request):
    """Foydalanuvchini tizimdan chiqarish"""
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
    
        return render(request, 'add_haridor.html')
    return redirect('main')
@login_required(login_url='login')
def profile_view(request, username):
    user = get_object_or_404(User, username=username, company=request.company)
    if request.method == 'GET':
    
        if request.user.type ==  'yetkazib_beruvchi':
            return render(request, 'ytprofile.html', {'user': user})
        elif request.user.type == 'savdogar':
            return render(request, 'egaprofile.html', {'user': user})
        elif request.user.type in ['pazanda', 'ishlab_chiqaruvchi']:
            return render(request, 'pzprofile.html', {'user': user})
        elif request.user.type=='ega':
            if user.type == 'yetkazib_beruvchi':
                yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=user).mahsulotlar) or []
                return render(request, 'egayt.html',{'user': user,'yuklamalar': yuklamalar})
            return render(request, 'egaprofile.html', {'user': user})
    elif request.method == 'POST':
        if request.user.type == 'ega':
            res=''
            if user.type == 'yetkazib_beruvchi':
                # Note: Keeping legacy stock adjustment for now as a fallback, 
                # but ideally this should also use a service.
                for i in request.POST:
                    
                    nomi=Mahsulot.objects.filter(nomi=i)
                    if nomi.exists():
                        
                        mq=request.POST[i]
                        if mq!="0":
                            res+=f"{i} {mq},"
                
                yt=YetkazibBeruvchi.objects.get(user=user)
                yt.mahsulotlar=res
                yt.save()
                yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=user).mahsulotlar) or []
                return render(request, 'egayt.html',{'user': user,'yuklamalar': yuklamalar})
@login_required(login_url='login')
def crtuser(request):
    if request.method == 'POST':
        # Check plan limit
        company = request.user.company
        if company:

            # Get max_users from custom plan or standard plan
            if company.is_custom_plan:
                max_users = company.custom_max_users
            elif company.plan:
                max_users = company.plan.max_users
            else:
                max_users = 5 # Default for trial/no plan
            
            # 0 means Unlimited
            if max_users > 0:
                current_users_count = User.objects.filter(company=company).count()
                if current_users_count >= max_users:
                    messages.error(request, f"Siz tanlagan tarif bo'yicha maksimal foydalanuvchilar soni ({max_users}) ga yetgan. Qo'shish uchun tarifni yangilang.")
                    return render(request, 'useryaratish.html', request.POST.dict())

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
            return render(request, 'useryaratish.html', request.POST.dict())

    return render(request, 'useryaratish.html')

@login_required(login_url='login')
def editusr(request, username):
    user_edit = get_object_or_404(User, username=username, company=request.company)
    mn = ''
    mr = ''
    all_mahsulotlar = []
    current_yuklamalar_dict = {}

    if user_edit.type == 'yetkazib_beruvchi':
        yb = YetkazibBeruvchi.objects.get(user=user_edit)
        mn = yb.bmh
        mr = yb.bmr.url if yb.bmr else ''
        all_mahsulotlar = Mahsulot.objects.filter(company=request.company, warehouse_type='finished').order_by('nomi')
        
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

        # Handle manual stock override for delivery users if they are not using sorov flow
        if user.type == 'yetkazib_beruvchi':
            yb = YetkazibBeruvchi.objects.get(user=user)
            new_yuklamalar_str = ""
            all_mahs = Mahsulot.objects.filter(company=request.company, warehouse_type='finished')
            for m in all_mahs:
                miqdor = request.POST.get(f'qty_{m.id}') # Use ID as sent from updated template
                if miqdor and float(miqdor) > 0:
                    new_yuklamalar_str += f"{m.nomi} {int(float(miqdor))},"
            yb.mahsulotlar = new_yuklamalar_str
            yb.save()

        messages.success(request, message)
        return redirect('hodimlar_list')

    return render(request, 'editusr.html', {
        'user_edit': user_edit,
        'mn': mn,
        'mr': mr,
        'all_mahsulotlar': all_mahsulotlar,
        'current_yuklamalar': current_yuklamalar_dict
    })
@login_required(login_url='login')
def seemahsulot(request, mahsulot_id):
    mahsulot = get_object_or_404(Mahsulot, id=mahsulot_id, company=request.company)
    turs = MahsulotTuri.objects.all().order_by('nomi')
    if request.method == 'POST':
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

        mahsulot.miqdori = request.POST.get('miqdori')
        mahsulot.narxi = request.POST.get('narxi')
        if request.POST.get('warehouse_type'):
            mahsulot.warehouse_type = request.POST.get('warehouse_type')
        
        # Look up by ID as sent from the template <option value="{{ tur.id }}">
        turi_id = request.POST.get('turi')
        if turi_id:
            mahsulot.turi = get_object_or_404(MahsulotTuri, id=turi_id)
            
        if 'rasmi' in request.FILES:
            mahsulot.rasmi = request.FILES['rasmi']
        
        mahsulot.save()
        messages.success(request, "Mahsulot muvaffaqiyatli saqlandi.")
        return redirect('mahsulotlar_list')
    return render(request, 'seemahsulot.html', {'mahsulot': mahsulot, 'turs': turs, 'warehouse_types': Mahsulot.WAREHOUSE_TYPES})
@login_required(login_url='login')
def createmahsulot(request):
    tur=MahsulotTuri.objects.all().order_by('nomi')
    payload={}  
    payload['turs']=tur
    payload['warehouse_types']=Mahsulot.WAREHOUSE_TYPES
    if request.method == 'POST':
        nomi = request.POST.get('nomi')
        miqdori = request.POST.get('miqdori')
        turi=get_object_or_404(MahsulotTuri, id=request.POST.get('turi'))
        rasmi = request.FILES.get('rasmi')
        narxi=request.POST.get('narxi')
        warehouse_type = request.POST.get('warehouse_type') or 'finished'
        mh=Mahsulot.objects.create(nomi=nomi, miqdori=miqdori, turi=turi, narxi=narxi, rasmi=rasmi, company=request.company, warehouse_type=warehouse_type)
        mh.save()
        # Activity log
        AmalLog.objects.create(
            user=request.user,
            company=request.company,
            amal_shifri=f"mahsulot_yaratish|{nomi}|{miqdori}|{narxi}"
        )
        return redirect('main')
    return render(request, 'crtmahsulot.html',payload)

@login_required(login_url='login')
def deleteprdct(request, product_id):
    mhs = get_object_or_404(Mahsulot, id=product_id)
    if request.method == 'POST':
        confirm_text = request.POST.get('confirm_text')
        if confirm_text == 'OCHIR':
            if mhs.stockhistory_set.exists() or mhs.yuklamasorov_set.exists() or mhs.deliverystock_set.exists() or mhs.miqdorqoshish_set.exists() or mhs.production_material_requests.exists():
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
@login_required(login_url='login')
def addmiqdor(request):
    if request.user.type in ['pazanda', 'ishlab_chiqaruvchi']:
        
        payload={}
        payload['mahsulotlar']=Mahsulot.objects.filter(company=request.company, warehouse_type='finished')
        payload['materials']=Mahsulot.objects.filter(company=request.company, warehouse_type='semi_finished')
        
        if request.method == 'POST':
            pz=Pazanda.objects.get(user=request.user)

            if 'request_material' in request.POST:
                material = get_object_or_404(
                    Mahsulot,
                    id=request.POST.get('material'),
                    company=request.company,
                    warehouse_type='semi_finished'
                )
                try:
                    qty = float(request.POST.get('material_qty') or 0)
                except (TypeError, ValueError):
                    qty = 0
                if qty <= 0:
                    messages.error(request, "So'raladigan material miqdori 0 dan katta bo'lishi kerak.")
                    return redirect('add_miqdor')

                material_request = ProductionMaterialRequest.objects.create(
                    company=request.company,
                    producer=pz,
                    material=material,
                    qty=qty,
                    note=request.POST.get('material_note') or None
                )
                StockHistory.objects.create(
                    company=request.company,
                    actor_user=request.user,
                    mahsulot=material,
                    event_type='RAW_REQUESTED',
                    old_qty=material.miqdori,
                    new_qty=material.miqdori,
                    delta=0
                )
                messages.success(request, f"{material.nomi} uchun {qty} {material.turi.nomi} material so'rovi yuborildi.")
                send_ws_notification(
                    request.company.subdomain,
                    "Yangi material so'rovi",
                    f"{pz.tuliq_ismi} {material.nomi}dan {qty} {material.turi.nomi} so'radi.",
                    'info'
                )
                return redirect('main')

            mxs=Mahsulot.objects.get(
                id=request.POST.get('mahsulot'),
                company=request.company,
                warehouse_type='finished'
            )
            mqdr=request.POST.get('miqdor')
            rasmi=request.FILES.get('rasm')
            # Create request for this company (Unapproved initially)
            nw=MiqdorQoshish.objects.create(
                company=request.company,
                mahsulot=mxs,
                miqdor=mqdr,
                rasmi=rasmi,
                tasdiqlangan=False, 
                pazanda=pz
            )
            
            # Delegate to atomic service to prevent race conditions and log history
            success, message = approve_miqdor_qoshish_service(nw.id, request.user)
            if not success:
                from django.contrib import messages
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

    pazanda = Pazanda.objects.get(user=request.user)
    mahsulotlar = Mahsulot.objects.filter(company=request.company, warehouse_type='finished')
    yetkazuvchilar = YetkazibBeruvchi.objects.filter(company=request.company)

    if request.method == "POST":
        mahsulot = Mahsulot.objects.get(id=request.POST['mahsulot'], company=request.company, warehouse_type='finished')
        miqdor = float(request.POST['miqdor'])
        yetkazuvchi = YetkazibBeruvchi.objects.get(id=request.POST['yetkazuvchi'], company=request.company)
        

        YuklamaSorov.objects.create(
            pazanda=pazanda,
            mahsulot=mahsulot,
            user=yetkazuvchi,
            miqdor=miqdor,
            mode='waiting',
            company=request.company
        )
        return redirect('main')

    return render(request, 'pzyuklama.html', {
        'mahsulotlar': mahsulotlar,
        'yetkazuvchilar': yetkazuvchilar,
    })
@login_required(login_url='login')
def sotish(request):
    if request.user.type == 'savdogar':
        return redirect('savdogar_sotish')
    
    if request.user.type == 'yetkazib_beruvchi':
        yt = YetkazibBeruvchi.objects.get(user=request.user)
        usr=request.user
        mahsulotlar = mahsulotlar_miqdori(yt.mahsulotlar, company=request.company)
        xaridorlar=HaridorDukon.objects.filter(company=request.company)
        
        if request.method == "POST":
            from django.db import transaction
            
            with transaction.atomic():
                yt = YetkazibBeruvchi.objects.select_for_update().get(user=request.user)
                # Re-parse mahsulotlar inside the locked transaction to get latest string
                mahsulotlar = mahsulotlar_miqdori(yt.mahsulotlar, company=request.company)
                
                rasm=request.FILES.get('rasm')
                turi =request.POST.get('st')
                haridor= HaridorDukon.objects.get(id=request.POST.get('haridor'), company=request.company)
                oluvchi=request.POST.get('oluvchi')
                sotilganlar = []
                for m in mahsulotlar:
                    miqdor = request.POST.get(f'miqdor_{m.nom}')
                    if miqdor and miqdor != '0':
                        m.miqdor -= float(miqdor)
                        sotilganlar.append((m.nom, miqdor))  # Logging uchun
                    
                if len(sotilganlar) > 0:
                    txt=''
                    summa=0
                    for s in sotilganlar:
                        mxs = Mahsulot.objects.filter(nomi=s[0], company=request.company).first()
                        if not mxs:
                            # Skip if product was deleted
                            continue
                        txt+=f'{s[0]} {s[1]} {mxs.narxi},'
                        summa+=float(s[1])*float(mxs.narxi)
                    # Get seller's current location
                    seller_lat = yt.last_lat
                    seller_lng = yt.last_lng
                    
                    if turi=='nasiya':
                        svd=Savdo.objects.create(yetkazib_beruvchi=yt,haridor_dukon=haridor,smm=txt,smr=rasm,oluvchining_ismi=oluvchi,tulandi=False,tasdiq_kutilmoqda=False,st=turi,summa=summa, company=request.company, latitude=seller_lat, longitude=seller_lng)
                    else:
                        svd=Savdo.objects.create(yetkazib_beruvchi=yt,haridor_dukon=haridor,smm=txt,smr=rasm,oluvchining_ismi=oluvchi,tulandi=True,tasdiq_kutilmoqda=True,st=turi,summa=summa, company=request.company, latitude=seller_lat, longitude=seller_lng)
        
                    sotishm(txt,yt)
                    # Activity log
                    AmalLog.objects.create(
                        user=request.user,
                        company=request.company,
                        amal_shifri=f"savdo_yaratish|{haridor.nomi}|{summa}"
                    )
                    
                    # WebSocket Notification
                    send_ws_notification(
                        request.company.subdomain,
                        "Yangi Savdo",
                        f"{yt.tuliq_ismi} {haridor.nomi}ga {summa} so'mlik savdo qildi.",
                        'info'
                    )

                    # Update deliverer location if provided
                    lat = request.POST.get('latitude')
                    lng = request.POST.get('longitude')
                    if lat and lng:
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
                
                return redirect('main')
            # Istasa: Savdo modelga yozish
            return redirect('main')
    else:
        return redirect('main')

    return render(request, 'ytsot.html', {'mahsulotlar': mahsulotlar,'haridorlar':xaridorlar})


@login_required(login_url='login')
def savdogar_sotish(request):
    if request.user.type != 'savdogar':
        return redirect('main')

    from .functions import new_yuklama
    mahsulotlar_qs = Mahsulot.objects.filter(company=request.company, warehouse_type='finished').order_by('nomi')
    mahsulotlar = [
        new_yuklama(m.nomi, m.miqdori, m.turi.nomi if m.turi else '', m.narxi)
        for m in mahsulotlar_qs
        if m.miqdori > 0
    ]
    xaridorlar = HaridorDukon.objects.filter(company=request.company)

    if request.method == "POST":
        from django.db import transaction

        with transaction.atomic():
            rasm = request.FILES.get('rasm')
            turi = request.POST.get('st')
            haridor = HaridorDukon.objects.get(id=request.POST.get('haridor'), company=request.company)
            oluvchi = request.POST.get('oluvchi')
            sotilganlar = []
            summa = 0

            for mahsulot in Mahsulot.objects.select_for_update().filter(company=request.company, warehouse_type='finished'):
                miqdor = request.POST.get(f'miqdor_{mahsulot.nomi}')
                if not miqdor or miqdor == '0':
                    continue

                qty = float(miqdor)
                if qty <= 0:
                    continue
                if mahsulot.miqdori < qty:
                    messages.error(request, f"{mahsulot.nomi} omborda yetarli emas.")
                    return redirect('savdogar_sotish')

                old_qty = mahsulot.miqdori
                mahsulot.miqdori -= qty
                mahsulot.save(update_fields=['miqdori'])
                StockHistory.objects.create(
                    company=request.company,
                    actor_user=request.user,
                    mahsulot=mahsulot,
                    event_type='DEDUCT',
                    old_qty=old_qty,
                    new_qty=mahsulot.miqdori,
                    delta=-qty,
                )
                sotilganlar.append((mahsulot.nomi, qty, mahsulot.narxi))
                summa += qty * float(mahsulot.narxi)

            if not sotilganlar:
                messages.error(request, "Kamida bitta mahsulot tanlang.")
                return redirect('savdogar_sotish')

            txt = ''.join([f'{nom} {qty} {narx},' for nom, qty, narx in sotilganlar])
            credit_terms = None
            final_summa = summa
            if turi == 'nasiya':
                if not request.company.credit_sales_enabled:
                    messages.error(request, "Bu firmada nasiya savdo o'chirilgan.")
                    return redirect('savdogar_sotish')
                credit_terms = build_credit_terms(summa, request.POST.get('credit_term_months'), request.company, haridor.nomi)
                final_summa = credit_terms['total']

            savdo = Savdo.objects.create(
                savdogar=request.user,
                haridor_dukon=haridor,
                smm=txt,
                smr=rasm,
                oluvchining_ismi=oluvchi,
                tulandi=(turi != 'nasiya'),
                tasdiq_kutilmoqda=(turi != 'nasiya'),
                st=turi,
                base_summa=summa,
                summa=final_summa,
                credit_term_months=credit_terms['months'] if credit_terms else None,
                credit_markup_percent=credit_terms['markup_percent'] if credit_terms else 0,
                credit_due_date=credit_terms['due_date'] if credit_terms else None,
                credit_contract_text=credit_terms['contract_text'] if credit_terms else None,
                company=request.company,
            )
            if turi == 'nasiya':
                send_ws_notification(
                    request.company.subdomain,
                    "Yangi muddatli nasiya savdo",
                    f"{request.user.tuliq_ismi or request.user.username} {haridor.nomi}ga {credit_terms['months']} oyga {final_summa:,.0f} so'mlik nasiya savdo qildi.",
                    'warning'
                )
            AmalLog.objects.create(
                user=request.user,
                company=request.company,
                amal_shifri=f"savdogar_savdo|{haridor.nomi}|{summa}"
            )
            messages.success(request, "Savdo muvaffaqiyatli saqlandi.")
            return redirect('savdogar_savdolar')

    return render(request, 'ytsot.html', {
        'mahsulotlar': mahsulotlar,
        'haridorlar': xaridorlar,
        'base_template': 'ytbase.html',
        'sales_title': 'Savdogar savdosi',
        'sales_subtitle': "Tayyor mahsulot omboridan sotuv qiling",
        'credit_terms': CREDIT_TERM_MARKUPS,
        'credit_sales_enabled': request.company.credit_sales_enabled,
    })


@login_required(login_url='login')
def savdogar_savdolar(request):
    if request.user.type != 'savdogar':
        return redirect('main')

    sales = Savdo.objects.filter(
        company=request.company,
        savdogar=request.user,
    ).select_related('haridor_dukon').order_by('-vaqt_sana')

    payment_filter = request.GET.get('payment', '')
    if payment_filter:
        sales = sales.filter(st=payment_filter)

    paginator = Paginator(sales, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'savdogar_savdolar.html', {
        'page_obj': page_obj,
        'payment_filter': payment_filter,
        'total_amount': sales.aggregate(t=Sum('summa'))['t'] or 0,
        'sales_count': sales.count(),
    })


@login_required(login_url='login')
def savdogar_hisobot(request):
    if request.user.type != 'savdogar':
        return redirect('main')

    now = timezone.localtime()
    from_date_str = request.GET.get('from')
    to_date_str = request.GET.get('to')

    try:
        from_date = dt.date.fromisoformat(from_date_str) if from_date_str else now.date().replace(day=1)
        to_date = dt.date.fromisoformat(to_date_str) if to_date_str else now.date()
    except ValueError:
        from_date = now.date().replace(day=1)
        to_date = now.date()

    from_dt = timezone.make_aware(dt.datetime.combine(from_date, dt.time.min))
    to_dt = timezone.make_aware(dt.datetime.combine(to_date, dt.time.max))

    sales = Savdo.objects.filter(
        company=request.company,
        savdogar=request.user,
        vaqt_sana__range=(from_dt, to_dt)
    ).select_related('haridor_dukon').order_by('-vaqt_sana')

    context = {
        'sales': sales,
        'from_date': from_date.isoformat(),
        'to_date': to_date.isoformat(),
        'total_sales': sales.count(),
        'total_amount': sales.aggregate(t=Sum('summa'))['t'] or 0,
        'naqd_amount': sales.filter(st='naqd').aggregate(t=Sum('summa'))['t'] or 0,
        'karta_amount': sales.filter(st='karta').aggregate(t=Sum('summa'))['t'] or 0,
        'nasiya_amount': sales.filter(st='nasiya').aggregate(t=Sum('summa'))['t'] or 0,
        'nasiya_unpaid': sales.filter(st='nasiya', tulandi=False).aggregate(t=Sum('summa'))['t'] or 0,
    }
    return render(request, 'savdogar_hisobot.html', context)


@login_required(login_url='login')
def admin_savdogar_hisobot(request):
    if request.user.type != 'ega':
        return redirect('main')

    now = timezone.localtime()
    from_date_str = request.GET.get('from')
    to_date_str = request.GET.get('to')
    savdogar_id = request.GET.get('savdogar')

    try:
        from_date = dt.date.fromisoformat(from_date_str) if from_date_str else now.date().replace(day=1)
        to_date = dt.date.fromisoformat(to_date_str) if to_date_str else now.date()
    except ValueError:
        from_date = now.date().replace(day=1)
        to_date = now.date()

    from_dt = timezone.make_aware(dt.datetime.combine(from_date, dt.time.min))
    to_dt = timezone.make_aware(dt.datetime.combine(to_date, dt.time.max))

    sales = Savdo.objects.filter(
        company=request.company,
        savdogar__isnull=False,
        vaqt_sana__range=(from_dt, to_dt)
    ).select_related('savdogar', 'haridor_dukon').order_by('-vaqt_sana')

    if savdogar_id:
        sales = sales.filter(savdogar_id=savdogar_id)

    savdogarlar = User.objects.filter(company=request.company, type='savdogar').order_by('tuliq_ismi')
    seller_stats = []
    for seller in savdogarlar:
        seller_sales = sales.filter(savdogar=seller)
        if seller_sales.exists():
            seller_stats.append({
                'seller': seller,
                'sales_count': seller_sales.count(),
                'total_amount': seller_sales.aggregate(t=Sum('summa'))['t'] or 0,
                'nasiya_amount': seller_sales.filter(st='nasiya').aggregate(t=Sum('summa'))['t'] or 0,
            })

    return render(request, 'admin_savdogar_hisobot.html', {
        'sales': sales[:100],
        'seller_stats': seller_stats,
        'savdogarlar': savdogarlar,
        'savdogar_filter': savdogar_id or '',
        'from_date': from_date.isoformat(),
        'to_date': to_date.isoformat(),
        'total_sales': sales.count(),
        'total_amount': sales.aggregate(t=Sum('summa'))['t'] or 0,
        'naqd_amount': sales.filter(st='naqd').aggregate(t=Sum('summa'))['t'] or 0,
        'karta_amount': sales.filter(st='karta').aggregate(t=Sum('summa'))['t'] or 0,
        'nasiya_amount': sales.filter(st='nasiya').aggregate(t=Sum('summa'))['t'] or 0,
    })


@login_required(login_url='login')
def credit_settings_view(request):
    if request.user.type != 'ega':
        return redirect('main')

    company = request.company
    if request.method == 'POST':
        company.credit_sales_enabled = request.POST.get('credit_sales_enabled') == 'on'
        company.credit_contract_template = request.POST.get('credit_contract_template') or ''
        company.credit_rules_note = request.POST.get('credit_rules_note') or ''
        company.credit_early_discount_percent = request.POST.get('credit_early_discount_percent') or 0
        company.credit_late_penalty_percent = request.POST.get('credit_late_penalty_percent') or 0
        company.save(update_fields=[
            'credit_sales_enabled',
            'credit_contract_template',
            'credit_rules_note',
            'credit_early_discount_percent',
            'credit_late_penalty_percent',
        ])
        messages.success(request, "Nasiya savdo sozlamalari saqlandi.")
        return redirect('credit_settings')

    return render(request, 'credit_settings.html', {
        'company': company,
        'credit_terms': CREDIT_TERM_MARKUPS,
    })


# ============================================
# API Endpoint for Browser Notifications
# ============================================
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

@login_required(login_url='login')
@require_http_methods(["GET"])
def check_new_deliveries(request):
    """
    API endpoint to check for new delivery requests for delivery personnel.
    Returns JSON with count and details of new deliveries since last check.
    """
    if request.user.type != 'yetkazib_beruvchi':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        yetkazuvchi = YetkazibBeruvchi.objects.get(user=request.user)
        
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
            tasdiq=False
        ).select_related('pazanda__user').order_by('-sana')
        
        deliveries_data = []
        for delivery in new_deliveries:
            pazanda_name = delivery.pazanda.user.tuliq_ismi if delivery.pazanda else "Noma'lum"
            deliveries_data.append({
                'id': delivery.id,
                'pazanda': pazanda_name,
                'sana': delivery.sana.strftime('%H:%M'),
                'mahsulot': delivery.mahsulot.nom if delivery.mahsulot else "Mahsulot",
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
        return JsonResponse({'error': 'Delivery user not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─── MVP: Pazanda — So'rovlar tarixi ─────────────────────────────────────────
@login_required(login_url='login')
def pz_sorov_tarixi(request):
    """Pazanda uchun: o'zi yuborgan barcha YuklamaSorov larni ko'rish."""
    if request.user.type not in ['pazanda', 'ishlab_chiqaruvchi']:
        return redirect('main')

    pazanda = Pazanda.objects.get(user=request.user)
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
    """Admin yoki pazandaning o'zi uchun: to'liq hisobot."""
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
