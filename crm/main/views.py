from django.shortcuts import render, get_list_or_404, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages 
from django.core.paginator import Paginator
from django.utils import timezone
from django.shortcuts import redirect
from .models import BACKUP_CHOICES, Plan, HaridorDukon, User, YetkazibBeruvchi, Pazanda, Mahsulot, MahsulotTuri, Savdo, YuklamaSorov, MiqdorQoshish, HaridorDukon, AmalLog, qaytarilgan_mahsulotlar, PlanRequest
from .functions import mahsulotlar_miqdori, makenewform, yuklama_maker, accptyuk, sotishm, sotuv_new_form ,yetkazuvchi_mahsulot_filter, get_bugungi_savdo_summ, add_spctoint
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
    approve_yuklama_sorov_service
)
from .services.auth_service import create_user_service, update_user_service
from .analytics.services import get_dashboard_stats

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
                base_domain = getattr(settings, 'BASE_DOMAIN', 'stockfirm.uz')
                scheme = "http" if any(x in base_domain for x in ["localhost", "lvh.me"]) else "https"
                return redirect(f"{scheme}://{request.user.company.subdomain}.{base_domain}/")
            
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
                    base_domain = getattr(settings, 'BASE_DOMAIN', 'stockfirm.uz')
                    scheme = "http" if any(x in base_domain for x in ["localhost", "lvh.me"]) else "https"
                    return redirect(f"{scheme}://{linked_user.company.subdomain}.{base_domain}/")
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
                    base_domain = getattr(settings, 'BASE_DOMAIN', 'stockfirm.uz')
                    scheme = "http" if any(x in base_domain for x in ["localhost", "lvh.me"]) else "https"
                    return redirect(f"{scheme}://{user_company.subdomain}.{base_domain}/")
                return redirect('main')
            else:
                messages.error(request, "Siz ushbu firmaga tegishli emassiz!")
        else:
            messages.error(request, "Login yoki parol noto'g'ri!")

    return render(request, 'login.html',data)

@login_required(login_url='login')
def activate_trial(request):
    if request.user.type != 'ega':
        messages.error(request, "Faqat firma egasi sinov muddatini yoqa oladi.")
        return redirect('main')
    
    company = request.company
    if company.is_on_trial:
        messages.info(request, "Sinov muddati allaqachon yoqilgan.")
        return redirect('main')
    
    if company.plan and company.plan.price > 0:
        messages.warning(request, "Sizda allaqachon pullik tarif faol.")
        return redirect('main')

    # 10-day limit check
    now = timezone.now()
    days_since_creation = (now - company.created_at).days
    
    if days_since_creation > 10:
        messages.error(request, "Sinov muddatini faqat ro'yxatdan o'tganingizdan so'ng 10 kun ichida yoqishingiz mumkin. Iltimos, admin bilan bog'laning.")
        return redirect('main')
    
    # Activate trial
    company.is_on_trial = True
    company.trial_expires_at = now + timezone.timedelta(days=30)
    company.save()
    
    messages.success(request, "Sinov muddati 30 kunga muvaffaqiyatli yoqildi!")
    return redirect('main')

@login_required(login_url='login')
def select_plan(request, plan_id):
    """Tarif tanlash uchun so'rov yuborish"""
    if request.user.type != 'ega':
        messages.error(request, "Faqat do'kon egasi tarifni o'zgartira oladi.")
        return redirect('main')
    
    plan = get_object_or_404(Plan, id=plan_id, is_active=True)
    company = request.company
    
    # Check for existing pending request
    if PlanRequest.objects.filter(company=company, status='pending').exists():
        messages.warning(request, "Sizda kutilayotgan tarif so'rovi mavjud. Iltimos, admin tasdiqlashini kuting.")
        return redirect('main')

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
def select_plan_page(request):
    """Tarif o'zgartirish sahifasi"""
    if request.user.type != 'ega':
        return redirect('main')
    
    if PlanRequest.objects.filter(company=request.company, status='pending').exists():
        messages.warning(request, "Sizda kutilayotgan tarif so'rovi mavjud.")
        return redirect('main')
    
    plans = Plan.objects.filter(is_active=True).order_by('price')
    return render(request, 'select_plan_page.html', {
        'plans': plans,
        'backup_choices': BACKUP_CHOICES
    })

@login_required(login_url='login')
def main(request):
    payload={}
    user=request.user
    
    if user.type == 'pazanda':
        now = timezone.localtime()
        today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
        today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))
        pz = Pazanda.objects.get(user=request.user)
        payload['sorovlar'] = YuklamaSorov.objects.filter(company=request.company, pazanda=pz, mode='waiting').all()
        payload['zaxira_mahsulotlar']=Mahsulot.objects.filter(company=request.company)
        zapros=MiqdorQoshish.objects.filter(company=request.company, pazanda=pz,vaqt_sana__range=(today_start, today_end)).all()
        payload['qms']=len(zapros)
        payload['kunlik_miqdorlar'] = zapros
        return render(request, 'pazanda_dashboard.html',payload)
    elif user.type == 'yetkazib_beruvchi':
        if request.method == 'GET':
            yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=request.user).mahsulotlar) or []
            
            payload['yuklamalar'] = yuklamalar
            mahs=Mahsulot.objects.filter(company=request.company)
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
            mahs=Mahsulot.objects.filter(company=request.company)
            payload['zaxira_mahsulotlar'] = mahs
            
            return render(request, 'yetkazuvchi_dashboard.html',payload)
            
    
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
    if request.user.type in ['yetkazib_beruvchi', 'ega']:
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
    user =  User.objects.get(username=username)
    if request.method == 'GET':
    
        if request.user.type ==  'yetkazib_beruvchi':
            return render(request, 'ytprofile.html', {'user': user})
        elif request.user.type == 'pazanda':
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
                    return render(request, 'useryaratish.html', request.POST)

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
            return render(request, 'useryaratish.html', request.POST)

    return render(request, 'useryaratish.html')

@login_required(login_url='login')
def editusr(request, username):
    user_edit = get_object_or_404(User, username=username)
    mn = ''
    mr = ''
    all_mahsulotlar = []
    current_yuklamalar_dict = {}

    if user_edit.type == 'yetkazib_beruvchi':
        yb = YetkazibBeruvchi.objects.get(user=user_edit)
        mn = yb.bmh
        mr = yb.bmr.url if yb.bmr else ''
        all_mahsulotlar = Mahsulot.objects.all().order_by('nomi')
        
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
            all_mahs = Mahsulot.objects.all()
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
    mahsulot = Mahsulot.objects.get(id=mahsulot_id)
    turs = MahsulotTuri.objects.filter(company=request.company)
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
        
        # Look up by ID as sent from the template <option value="{{ tur.id }}">
        turi_id = request.POST.get('turi')
        if turi_id:
            mahsulot.turi = MahsulotTuri.objects.get(id=turi_id, company=request.company)
            
        if 'rasmi' in request.FILES:
            mahsulot.rasmi = request.FILES['rasmi']
        
        mahsulot.save()
        messages.success(request, "Mahsulot muvaffaqiyatli saqlandi.")
        return redirect('mahsulotlar_list')
    return render(request, 'seemahsulot.html', {'mahsulot': mahsulot, 'turs': turs})
@login_required(login_url='login')
def createmahsulot(request):
    tur=MahsulotTuri.objects.filter(company=request.company)
    payload={}  
    payload['turs']=tur
    if request.method == 'POST':
        nomi = request.POST.get('nomi')
        miqdori = request.POST.get('miqdori')
        turi=MahsulotTuri.objects.get(nomi=request.POST.get('turi'), company=request.company)
        rasmi = request.FILES.get('rasmi')
        narxi=request.POST.get('narxi')
        mh=Mahsulot.objects.create(nomi=nomi, miqdori=miqdori, turi=turi, narxi=narxi, rasmi=rasmi, company=request.company)
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
            mhs.delete()
            messages.success(request, "Mahsulot o'chirildi.")
            return redirect('mahsulotlar_list')
        else:
            messages.error(request, "Tasdiqlash matni noto'g'ri.")
    return redirect('seeproduct', mahsulot_id=product_id)
@login_required(login_url='login')
def addmiqdor(request):
    if request.user.type=='pazanda':        
        
        payload={}
        payload['mahsulotlar']=Mahsulot.objects.filter(company=request.company)
        
        if request.method == 'POST':
            ok=1
            mxs=Mahsulot.objects.get(nomi=request.POST.get('mahsulot'), company=request.company)
            mqdr=request.POST.get('miqdor')
            rasmi=request.FILES.get('rasm')
            pz=Pazanda.objects.get(user=request.user)
            # Create request for this company
            nw=MiqdorQoshish.objects.create(
                company=request.company,
                mahsulot=mxs,
                miqdor=mqdr,
                rasmi=rasmi,
                tasdiqlangan=True, 
                pazanda=pz
            )
            mxs.miqdori+=int(mqdr)
            mxs.save()
            nw.save()
            
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
    pazanda = Pazanda.objects.get(user=request.user)
    mahsulotlar = Mahsulot.objects.filter(company=request.company)
    yetkazuvchilar = YetkazibBeruvchi.objects.filter(company=request.company)

    if request.method == "POST":
        mahsulot = Mahsulot.objects.get(id=request.POST['mahsulot'], company=request.company)
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
    
    if request.user.type == 'yetkazib_beruvchi':
        yt = YetkazibBeruvchi.objects.get(user=request.user)
        usr=request.user
        mahsulotlar = mahsulotlar_miqdori(yt.mahsulotlar, company=request.company)
        xaridorlar=HaridorDukon.objects.filter(company=request.company)
        
        if request.method == "POST":
            rasm=request.FILES.get('rasm')
            turi =request.POST.get('st')
            haridor= HaridorDukon.objects.get(id=request.POST.get('haridor'), company=request.company)
            oluvchi=request.POST.get('oluvchi')
            sotilganlar = []
            for m in mahsulotlar:
                miqdor = request.POST.get(f'miqdor_{m.nom}')
                if miqdor!='0':
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
                if turi=='nasiya':
                    svd=Savdo.objects.create(yetkazib_beruvchi=yt,haridor_dukon=haridor,smm=txt,smr=rasm,oluvchining_ismi=oluvchi,tulandi=False,tasdiq_kutilmoqda=False,st=turi,summa=summa, company=request.company)
                    svd.save()

                else:
                    svd=Savdo.objects.create(yetkazib_beruvchi=yt,haridor_dukon=haridor,smm=txt,smr=rasm,oluvchining_ismi=oluvchi,tulandi=True,tasdiq_kutilmoqda=True,st=turi,summa=summa, company=request.company)
                    svd.save()
    
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
                # svd=Savdo.objects.create(yetkazuvchi=yt,haridor=request.POST.get('haridor'),mahsulotlar=txt)
                # Istasa: Savdo modelga yozish

            

            # yt.mahsulotlar = yuklama_maker(mahsulotlar)
            # yt.save()
            # Istasa: Savdo modelga yozish
            return redirect('main')
    else:
        return redirect('main')

    return render(request, 'ytsot.html', {'mahsulotlar': mahsulotlar,'haridorlar':xaridorlar})


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
    if request.user.type != 'pazanda':
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

    target_user = get_object_or_404(User, username=username, type='yetkazib_beruvchi')
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

    target_user = get_object_or_404(User, username=username, type='pazanda')
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
