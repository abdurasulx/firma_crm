import json
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from main.models import BillingPaymentLink, Company, User, Plan, PlanRequest
from django.db import models, transaction
from django.db.models import Count, Q, Sum
from django.contrib.auth.decorators import user_passes_test
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from main.services.auth_service import create_user_service
from main.services.billing_service import (
    apply_plan_request,
    get_billing_period_start,
    get_prorated_billing,
    get_company_login_url,
    mark_company_paid,
    mark_company_unpaid,
    reject_plan_request as reject_plan_request_service,
    sync_company_lifecycle,
)
from main.plan_utils import (
    build_plan_description,
    get_plan_duration_months,
    is_tariff_change_locked,
    parse_plan_metadata,
)
from .realtime import broadcast_superadmin_update, get_superadmin_context

def send_company_notification(company, title, message, type='info', refresh=False):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer and company and company.subdomain:
            async_to_sync(channel_layer.group_send)(
                f"notifications_{company.subdomain}",
                {
                    "type": "send_notification",
                    "title": title,
                    "message": message,
                    "notification_type": type,
                    "refresh": refresh,
                },
            )
    except Exception as e:
        print(f"WS Notification Error: {e}")

def landing_home(request):
    if not getattr(request, "is_landing", False):
        return redirect('/') 
    return render(request, "landing/home_pro.html")


MARKETING_PAGES = {
    "features": {
        "eyebrow": "Platforma",
        "title": "StockFirm ERP nimalarni hal qiladi?",
        "lead": "Firma ichidagi tarqoq Excel, Telegram xabarlar, qo'lda yozilgan daftar va og'zaki kelishuvlarni bitta tartibli tizimga almashtiring.",
        "items": [
            ("Ombor", "Mahsulot kirimi, chiqimi, minimal qoldiq va audit tarixi."),
            ("Savdo", "Naqd, karta va nasiya savdolarini hodimlar kesimida ko'rish."),
            ("Yetkazib berish", "Kuryer zaxirasi, yuklama so'rovlari va GPS monitoring."),
            ("Analitika", "Mahsulot talabi, top mijozlar va o'sish signallari."),
            ("Billing", "Tarif, trial, Click to'lov va feature gating."),
            ("Backup", "Ma'lumotlarni eksport qilish va tiklash imkoniyati."),
        ],
    },
    "inventory": {
        "eyebrow": "Ombor nazorati",
        "title": "Har bir mahsulot qayerdan keldi va qayerga ketdi?",
        "lead": "Ombor qoldig'i, ishlab chiqarishdan kirim, yetkazuvchiga yuklama va qaytarilgan mahsulotlar aniq hisobda yuradi.",
        "items": [
            ("Minimal zaxira", "Qoldiq belgilangan chegaradan pastlasa rahbar ko'radi."),
            ("Stock history", "Har bir o'zgarish kim tomonidan va qachon qilinganini saqlaydi."),
            ("Delivery stock", "Har bir yetkazuvchidagi mahsulot alohida hisoblanadi."),
            ("Qaytarish", "Qaytgan mahsulotlar umumiy ombor jarayonidan ajralmaydi."),
        ],
    },
    "sales": {
        "eyebrow": "Savdo boshqaruvi",
        "title": "Sotuvlar, mijozlar va cheklar bitta oqimda.",
        "lead": "Yetkazuvchi sotuv qilganda mahsulot avtomatik kamayadi, summa hisoblanadi va rahbar dashboardda ko'radi.",
        "items": [
            ("Mijoz tarixi", "Har bir do'kon bilan savdo tarixi saqlanadi."),
            ("To'lov turi", "Naqd, karta va nasiya alohida tahlil qilinadi."),
            ("Chek", "Savdo bo'yicha tezkor chek va hujjat ko'rinishi."),
            ("Hisobot", "Kunlik, haftalik, oylik va xodim kesimida hisobot."),
        ],
    },
    "nasiya": {
        "eyebrow": "Nasiya nazorati",
        "title": "Qarzlar yo'qolmaydi, nazoratdan chiqmaydi.",
        "lead": "Nasiya savdolar, qisman to'lovlar, qarzdor mijozlar va muddati o'tgan qarzlarni bitta joyda kuzating.",
        "items": [
            ("Qisman to'lov", "Mijoz to'lovni bo'lib-bo'lib qilsa ham tarix saqlanadi."),
            ("Qarzdorlar ro'yxati", "Kim qancha qarzdorligini tez ko'rasiz."),
            ("Mas'ul hodim", "Qarz qaysi yetkazuvchi savdosidan kelgani aniq."),
            ("Rahbar nazorati", "Nasiya biznes pul oqimiga qanday ta'sir qilayotganini ko'rsatadi."),
        ],
    },
    "delivery": {
        "eyebrow": "Yetkazib berish",
        "title": "Kuryer qayerda, yonida nima bor, qancha sotdi?",
        "lead": "Yetkazuvchilar zaxirasi, yuklama so'rovlari, real vaqt lokatsiyasi va savdo tarixi tizimda bog'lanadi.",
        "items": [
            ("Yuklama", "Ombordan kuryerga mahsulot berish tasdiq bilan yuradi."),
            ("GPS", "Xaritada faol yetkazuvchilarni kuzatish."),
            ("Zaxira", "Har bir kuryerning alohida mahsulot qoldig'i."),
            ("Marshrut", "Do'konlar va savdo nuqtalari bilan ishlash osonlashadi."),
        ],
    },
    "analytics": {
        "eyebrow": "Analitika",
        "title": "Qarorlar taxmin bilan emas, raqam bilan qabul qilinadi.",
        "lead": "Dashboard, grafiklar, mahsulot talabi va do'konlar bo'yicha tavsiyalar biznes egasiga tez qaror qilishga yordam beradi.",
        "items": [
            ("Talab prognozi", "Qaysi mahsulotni ko'proq ishlab chiqarish kerakligini ko'rsatadi."),
            ("Top mijozlar", "Eng faol do'konlarni ajratadi."),
            ("Past zaxira", "Tugab qolish xavfini oldindan bildiradi."),
            ("Excel export", "Hisobotlarni tashqi tahlil uchun yuklab olish."),
        ],
    },
    "maps": {
        "eyebrow": "Xarita",
        "title": "Real vaqt xarita bilan yetkazuvchilar nazoratda.",
        "lead": "GPS monitoring, do'kon koordinatalari va yetkazuvchi faolligi savdo geografiyasini tushunarli qiladi.",
        "items": [
            ("Online status", "Qaysi yetkazuvchi hozir faol ekanini ko'rsatadi."),
            ("Lokatsiya tarixi", "Harakatlar tarixi keyingi nazorat uchun saqlanadi."),
            ("Do'konlar xaritada", "Mijozlar joylashuvi aniq ko'rinadi."),
            ("Hudud nazorati", "Qaysi hudud ko'proq ishlayotganini ko'rish oson."),
        ],
    },
    "billing": {
        "eyebrow": "SaaS billing",
        "title": "Tarif, trial va to'lovlar tizimli boshqariladi.",
        "lead": "Firma to'lovi, keyingi to'lov sanasi, Click linklari va feature access bitta billing oqimida ishlaydi.",
        "items": [
            ("Trial", "Yangi firmaga sinov muddati berish mumkin."),
            ("Tariflar", "Standart yoki custom tarif tanlash."),
            ("Feature gating", "To'lanmagan firma premium funksiyalardan foydalana olmaydi."),
            ("Click", "Online to'lov linki va status tracking."),
        ],
    },
    "security": {
        "eyebrow": "Xavfsizlik",
        "title": "Har bir firma o'z ma'lumotini alohida ko'radi.",
        "lead": "Subdomain asosidagi tenant ajratish, rollar, super admin va firma ichidagi user limitlar ma'lumotlarni tartibli saqlaydi.",
        "items": [
            ("Tenant isolation", "Firma ma'lumotlari boshqa firmadan ajratiladi."),
            ("Rollar", "Ega, ishlab chiqaruvchi va yetkazuvchi huquqlari farqlanadi."),
            ("Audit", "Muhim harakatlar jurnalga yoziladi."),
            ("Backup", "Kerak bo'lsa ma'lumotlarni eksport va tiklash."),
        ],
    },
    "implementation": {
        "eyebrow": "Joriy qilish",
        "title": "StockFirm ERP'ni ishga tushirish murakkab emas.",
        "lead": "Firma ochiladi, subdomain tanlanadi, mahsulot va hodimlar kiritiladi, keyin jarayonlar tizimga o'tkaziladi.",
        "items": [
            ("1-qadam", "Firma va ega akkaunti yaratiladi."),
            ("2-qadam", "Mahsulot turlari, mahsulotlar va mijozlar kiritiladi."),
            ("3-qadam", "Ishlab chiqaruvchi va yetkazuvchilar qo'shiladi."),
            ("4-qadam", "Savdo, zaxira va hisobotlar real ishda sinovdan o'tadi."),
        ],
    },
    "contact": {
        "eyebrow": "Aloqa",
        "title": "Tizimni biznesingizga moslab ko'rishni xohlaysizmi?",
        "lead": "Demo, pilot firma yoki individual tarif bo'yicha bog'laning. Sizning jarayoningizni ERP oqimiga moslab beramiz.",
        "items": [
            ("Demo", "Tizim imkoniyatlarini jonli ko'rish."),
            ("Pilot", "Bitta firma bilan sinov ishga tushirish."),
            ("Custom tarif", "Kerakli modullarni tanlab narx shakllantirish."),
            ("Migratsiya", "Mavjud Excel yoki daftar jarayonini tizimga ko'chirish."),
        ],
    },
}


def marketing_page(request, slug):
    page = MARKETING_PAGES.get(slug)
    if not page:
        return render(request, '404.html', status=404)
    return render(request, "landing/marketing_page.html", {'page': page, 'slug': slug})

def pricing_view(request):
    return render(request, "landing/pricing.html")

def offer_view(request):
    return render(request, "landing/offer.html")

def register_company(request):
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        subdomain = (request.POST.get('subdomain') or '').lower()
        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        password = request.POST.get('password')
        phone = request.POST.get('phone')

        if request.POST.get('accept_offer') != 'on':
            messages.error(request, "Ro'yxatdan o'tish uchun ommaviy ofertani qabul qilish kerak.")
            return render(request, "landing/register.html", {'post_data': request.POST})

        if Company.objects.filter(subdomain=subdomain).exists():
            messages.error(request, "Bu subdomain allaqachon band!")
            return render(request, "landing/register.html", {'post_data': request.POST})

        try:
            with transaction.atomic():
                # Create Company
                now = timezone.now()
                setup_expires = now + timezone.timedelta(days=5)
                
                trial_expires = None
                is_on_trial = request.POST.get('free_trial') == 'on'
                if is_on_trial:
                    trial_expires = now + timezone.timedelta(days=30)

                company = Company.objects.create(
                    name=company_name, 
                    subdomain=subdomain,
                    setup_mode=True,
                    setup_expires_at=setup_expires,
                    is_on_trial=is_on_trial,
                    trial_expires_at=trial_expires
                )
                
                user, message = create_user_service(
                    username=username,
                    password=password,
                    fullname=full_name,
                    user_type='ega',
                    phone=phone,
                    company=company,
                )
                if not user:
                    raise ValueError(message)
                
                messages.success(request, f"Tabriklaymiz! {company_name} muvaffaqiyatli ro'yxatdan o'tdi. 5 kunlik sozlash rejimi yoqildi.")
                transaction.on_commit(broadcast_superadmin_update)
                return redirect(get_company_login_url(company, request.get_host()))
                
        except Exception as e:
            messages.error(request, f"Xatolik yuz berdi: {str(e)}")
            return render(request, "landing/register.html", {'post_data': request.POST})
    
    return render(request, "landing/register.html")

from django.contrib.auth.decorators import user_passes_test
from django.utils import timezone

def is_superuser(user):
    return user.is_authenticated and user.is_superuser

@user_passes_test(is_superuser)
def super_dashboard(request):
    return render(request, "landing/super_dashboard.html", get_superadmin_context())

@user_passes_test(is_superuser)
def super_companies(request):
    from django.core.paginator import Paginator

    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    companies_qs = Company.objects.annotate(
        total_users=Count('user'),
        staff_count=Count('user', filter=~models.Q(user__type='ega'))
    ).order_by('-created_at')

    if q:
        companies_qs = companies_qs.filter(
            Q(name__icontains=q) | Q(subdomain__icontains=q)
        )
    if status_filter == 'active':
        companies_qs = companies_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        companies_qs = companies_qs.filter(is_active=False)
    elif status_filter == 'trial':
        companies_qs = companies_qs.filter(is_on_trial=True)

    paginator = Paginator(companies_qs, 15)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, "landing/super_companies.html", {
        'companies': page_obj,
        'page_obj': page_obj,
        'q': q,
        'status_filter': status_filter,
    })

@user_passes_test(is_superuser)
def super_company_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        subdomain = (request.POST.get('subdomain') or '').lower()
        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        password = request.POST.get('password')
        phone = request.POST.get('phone')

        if Company.objects.filter(subdomain=subdomain).exists():
            messages.error(request, "Bu subdomain allaqachon band!")
            return render(request, "landing/super_company_form.html", {'plans': Plan.objects.all(), 'action': 'Qo\'shish'})

        try:
            with transaction.atomic():
                plan_id = request.POST.get('plan')
                is_active = 'is_active' in request.POST
                plan = Plan.objects.get(pk=plan_id) if plan_id else None
                plan_months = int(request.POST.get('plan_months') or (get_plan_duration_months(plan) if plan else 1))
                
                now = timezone.now()
                setup_mode = request.POST.get('setup_mode') == 'on'
                setup_expires = now + timezone.timedelta(days=5) if setup_mode else None
                
                is_on_trial = request.POST.get('is_on_trial') == 'on'
                trial_expires = now + timezone.timedelta(days=30) if is_on_trial else None

                company = Company.objects.create(
                    name=name, 
                    subdomain=subdomain, 
                    plan=plan, 
                    is_active=is_active,
                    setup_mode=setup_mode,
                    setup_expires_at=setup_expires,
                    is_on_trial=is_on_trial,
                    trial_expires_at=trial_expires,
                    payment_status='paid' if plan and plan_months > 0 else 'unpaid',
                    next_payment_date=now + relativedelta(months=plan_months) if plan and plan_months > 0 else None
                )
                user, message = create_user_service(
                    username=username,
                    password=password,
                    fullname=full_name,
                    user_type='ega',
                    phone=phone,
                    company=company,
                )
                if not user:
                    raise ValueError(message)
                messages.success(request, f"{name} firmasi muvaffaqiyatli qo'shildi.")
                transaction.on_commit(broadcast_superadmin_update)
                return redirect('super_companies')
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")
    
    plans = Plan.objects.all()
    return render(request, "landing/super_company_form.html", {'plans': plans, 'action': 'Qo\'shish'})

@user_passes_test(is_superuser)
def super_company_edit(request, pk):
    company = get_object_or_404(Company, pk=pk)
    if request.method == 'POST':
        company.name = request.POST.get('name')
        new_subdomain = request.POST.get('subdomain').lower()
        plan_id = request.POST.get('plan')
        plan_months = int(request.POST.get('plan_months') or 0)
        company.is_active = 'is_active' in request.POST
        
        prev_setup_mode = company.setup_mode
        company.setup_mode = 'setup_mode' in request.POST
        if company.setup_mode and not prev_setup_mode:
            company.setup_expires_at = timezone.now() + timezone.timedelta(days=5)
        elif not company.setup_mode:
            company.setup_expires_at = None
            
        prev_trial_mode = company.is_on_trial
        company.is_on_trial = 'is_on_trial' in request.POST
        if company.is_on_trial and not prev_trial_mode:
            company.trial_expires_at = timezone.now() + timezone.timedelta(days=30)
        elif not company.is_on_trial:
            company.trial_expires_at = None
        
        if Company.objects.filter(subdomain=new_subdomain).exclude(pk=pk).exists():
            messages.error(request, "Bu subdomain allaqachon band!")
        else:
            company.subdomain = new_subdomain
            if plan_id:
                company.plan = Plan.objects.get(pk=plan_id)
                if plan_months > 0:
                    company.payment_status = 'paid'
                    company.next_payment_date = timezone.now() + relativedelta(months=plan_months)
            else:
                company.plan = None
            company.save()
            messages.success(request, "Firma ma'lumotlari yangilandi.")
            broadcast_superadmin_update()
            return redirect('super_companies')
            
    plans = Plan.objects.all()
    return render(request, "landing/super_company_form.html", {
        'company': company,
        'plans': plans,
        'current_plan_months': get_plan_duration_months(company.plan) if company.plan else 1,
        'tariff_change_locked': is_tariff_change_locked(company),
        'action': 'Tahrirlash'
    })

@user_passes_test(is_superuser)
def super_company_delete(request, pk):
    company = get_object_or_404(Company, pk=pk)
    if request.method == 'POST':
        name = company.name
        company.delete()
        messages.success(request, f"{name} firmasi o'chirildi.")
        broadcast_superadmin_update()
    return redirect('super_companies')

@user_passes_test(is_superuser)
def super_plan_list(request):
    plans = Plan.objects.all().order_by('-created_at')
    for plan in plans:
        plan.meta = parse_plan_metadata(plan)
    return render(request, "landing/super_plan_list.html", {'plans': plans})

@user_passes_test(is_superuser)
def super_plan_create(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description')
            price = request.POST.get('price')
            max_users = request.POST.get('max_users')
            has_telegram_bot = request.POST.get('has_telegram_bot') == 'on'
            has_analytics = request.POST.get('has_analytics') == 'on'
            has_map = request.POST.get('has_map') == 'on'
            backup_type = request.POST.get('backup_type', 'none')
            is_hidden = request.POST.get('is_hidden') == 'on'
            lock_changes = request.POST.get('lock_changes') == 'on'
            has_savdogar_sales = request.POST.get('has_savdogar_sales') == 'on'
            duration_months = request.POST.get('duration_months') or 1
            
            Plan.objects.create(
                name=name,
                description=build_plan_description(description, is_hidden, lock_changes, duration_months, has_savdogar_sales),
                price=price,
                max_users=max_users,
                has_telegram_bot=has_telegram_bot,
                has_analytics=has_analytics,
                has_map=has_map,
                backup_type=backup_type
            )
            messages.success(request, "Tarif muvaffaqiyatli qo'shildi.")
            broadcast_superadmin_update()
            return redirect('super_plan_list')
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")
            
    return render(request, "landing/super_plan_form.html", {'action': "Qo'shish"})

@user_passes_test(is_superuser)
def super_plan_edit(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    if request.method == 'POST':
        try:
            plan.name = request.POST.get('name')
            is_hidden = request.POST.get('is_hidden') == 'on'
            lock_changes = request.POST.get('lock_changes') == 'on'
            has_savdogar_sales = request.POST.get('has_savdogar_sales') == 'on'
            duration_months = request.POST.get('duration_months') or 1
            plan.description = build_plan_description(request.POST.get('description'), is_hidden, lock_changes, duration_months, has_savdogar_sales)
            plan.price = request.POST.get('price')
            plan.max_users = request.POST.get('max_users')
            plan.has_telegram_bot = request.POST.get('has_telegram_bot') == 'on'
            plan.has_analytics = request.POST.get('has_analytics') == 'on'
            plan.has_map = request.POST.get('has_map') == 'on'
            plan.backup_type = request.POST.get('backup_type', 'none')
            plan.save()
            messages.success(request, "Tarif ma'lumotlari yangilandi.")
            broadcast_superadmin_update()
            return redirect('super_plan_list')
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")
            
    return render(request, "landing/super_plan_form.html", {
        'plan': plan,
        'plan_meta': parse_plan_metadata(plan),
        'action': 'Tahrirlash'
    })

@user_passes_test(is_superuser)
def super_plan_delete(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    if request.method == 'POST':
        name = plan.name
        plan.delete()
        messages.success(request, f"{name} tarifi o'chirildi.")
        broadcast_superadmin_update()
    return redirect('super_plan_list')

def custom_404(request, exception=None):
    return render(request, '404.html', status=404)


def product_scan_view(request, kod):
    """Public QR-skan sahifasi: stockfirm.uz/p/<kod>/

    Mahsulot ma'lumoti server tomonida DARHOL berilmaydi — sahifa faqat
    "qobiq" (kod bilan), ma'lumotning o'zi mijoz brauzerida joylashuvga
    ruxsat berilgandan keyin `product_scan_status_api`dan JS orqali
    olinadi (pastga qarang: o'g'irlik nazorati shu joylashuv asosida).
    Bu yerda faqat kod haqiqatan mavjudligi tekshiriladi (topilmasa 404),
    scan_soni oshirilmaydi — buni endi status API o'zi qiladi (joylashuv
    bilan birga, bir marta)."""
    from main.models import Serial

    if not Serial.objects.filter(kod=kod).exists():
        return render(request, '404.html', status=404)

    return render(request, 'landing/product_scan.html', {'kod': kod})


# Ombordan necha metr uzoqlashguncha "hali ombor hududida" deb hisoblanadi —
# shundan uzoqda, hali SOTILMAGAN (holati != 'sotilgan') mahsulot
# skanerlansa, tizim tekshiruvidan o'tmasdan chiqarilgan (o'g'irlangan
# bo'lishi mumkin) deb belgilanadi.
THEFT_CHECK_RADIUS_METERS = 50


def _haversine_meters(lat1, lng1, lat2, lng2):
    from math import asin, cos, radians, sin, sqrt
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 6371000 * 2 * asin(sqrt(a))


def product_scan_status_api(request, kod):
    """`product_scan_view` sahifasi joylashuvga ruxsat berilgandan keyin
    shu API'ni chaqiradi. **Hech qachon tannarx yoki boshqa moliyaviy
    maydon qaytarilmaydi** — faqat mahsulot nomi, ishlab chiqarilgan sana,
    yaroqlilik va holat.

    O'g'irlik tekshiruvi: agar seriya hali 'omborda' holatida bo'lsa
    (ya'ni tizim orqali hech qanday tasdiqlangan yo'l bilan — yuklama,
    sotuv — chiqarilmagan), lekin firmaning barcha omborlaridan
    `THEFT_CHECK_RADIUS_METERS`dan uzoqda skanerlansa — bu mahsulot
    tizim tekshiruvidan o'tmasdan ombordan chiqarilgan (o'g'irlangan
    bo'lishi mumkin) deb belgilanadi: skanerlovchiga ogohlantirish matni
    ko'rsatiladi va firma egasiga (WS + doimiy `SerialHarakat` yozuvi
    orqali) darhol xabar boradi. 'chiqarilgan' holat TEKSHIRILMAYDI —
    u allaqachon Desktop Agent orqali tasdiqlangan legal yetkazib
    berish jarayoni (yetkazib beruvchi mijozga olib ketmoqda bo'lishi
    tabiiy) — buni ham tekshirish har bir oddiy yetkazib berishda soxta
    ogohlantirish yuborardi."""
    from main.models import Serial, SerialHarakat

    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return JsonResponse({'detail': "Joylashuv (lat/lng) kerak."}, status=400)

    serial = Serial.objects.select_related('mahsulot', 'batch', 'batch__pazanda__user', 'company').filter(kod=kod).first()
    if not serial:
        return JsonResponse({'detail': "Mahsulot topilmadi."}, status=404)

    Serial.objects.filter(pk=serial.pk).update(scan_soni=models.F('scan_soni') + 1)

    mahsulot = serial.mahsulot
    yaroqlilik_sanasi = None
    if serial.batch and mahsulot.yaroqlilik_kun_soni:
        yaroqlilik_sanasi = serial.batch.vaqt_sana + timedelta(days=mahsulot.yaroqlilik_kun_soni)

    data = {
        'mahsulot': mahsulot.nomi,
        'rasmi': request.build_absolute_uri(mahsulot.rasmi.url) if mahsulot.rasmi else None,
        'tavsif': mahsulot.qr_tavsif or '',
        'partiya_id': serial.batch_id,
        'ishlab_chiqarilgan_sana': serial.batch.vaqt_sana.strftime('%d.%m.%Y') if serial.batch else None,
        'yaroqlilik_sanasi': yaroqlilik_sanasi.strftime('%d.%m.%Y') if yaroqlilik_sanasi else None,
        'unit_index': serial.unit_index,
        'holati': serial.holati,
        # Ichki admin ko'rinishida "Sotilgan" — lekin public sahifada bu
        # noaniq (xaridorga "sizga tegishli emas" degandek tuyulishi mumkin);
        # shuning uchun bu yerda alohida, mijozga tushunarli matn bilan.
        'holati_display': "Sotuvga chiqarilgan" if serial.holati == 'sotilgan' else serial.get_holati_display(),
        'ogohlantirish': None,
    }

    # DIQQAT: faqat 'omborda' holati tekshiriladi, 'chiqarilgan' EMAS —
    # 'chiqarilgan' allaqachon tizim orqali (Desktop Agent'da xodim badge/
    # Serial-QR skanerlab, `YuklamaSorov` tasdiqlanib) LEGAL ravishda
    # ombordan chiqarilgan holat (yetkazib beruvchi mijozga olib
    # ketayotgan bo'lishi mumkin — bu me'yor). Agar bu ham tekshirilsa,
    # HAR BIR oddiy yetkazib berishda ombordan uzoqlashgani uchun egaga
    # soxta "o'g'irlangan bo'lishi mumkin" ogohlantirishi ketardi — vaqt
    # o'tib bunday soxta signal haqiqiy o'g'irlikni ham e'tiborsiz
    # qoldirishga olib kelishi mumkin. Faqat 'omborda' (hech qanday
    # tizim tasdig'isiz) holat chinakam shubhali.
    if serial.holati == 'omborda':
        omborlar = list(
            serial.company.omborlar.filter(latitude__isnull=False, longitude__isnull=False)
            .values_list('latitude', 'longitude')
        ) if serial.company else []
        if omborlar:
            min_dist = min(_haversine_meters(lat, lng, olat, olng) for olat, olng in omborlar)
            if min_dist > THEFT_CHECK_RADIUS_METERS:
                data['ogohlantirish'] = (
                    "Bu mahsulot o'g'irlangan bo'lishi mumkin — tizim tekshiruvidan o'tmasdan "
                    "ombordan tashqarida qayd etildi. Ehtiyot bo'ling yoki bu haqda xabar bering."
                )
                already_alerted = SerialHarakat.objects.filter(
                    serial=serial, event='shubhali', vaqt__gte=timezone.now() - timedelta(hours=24),
                ).exists()
                izoh = f"lat={lat:.5f},lng={lng:.5f},masofa={min_dist:.0f}m"
                SerialHarakat.objects.create(
                    company=serial.company, serial=serial, event='shubhali', izoh=izoh,
                )
                if not already_alerted:
                    producer = serial.batch.pazanda.user.tuliq_ismi if serial.batch and serial.batch.pazanda and serial.batch.pazanda.user else "Noma'lum"
                    send_company_notification(
                        serial.company,
                        "⚠ Shubhali holat — mahsulot ombordan tashqarida",
                        f"{producer} ishlab chiqargan \"{mahsulot.nomi}\" mahsuloti tizim tekshiruvidan "
                        f"o'tmasdan ombordan tashqarida (https://maps.google.com/?q={lat},{lng}) topildi. "
                        "O'g'irlangan bo'lishi mumkin.",
                        'error',
                        refresh=False,
                    )

    return JsonResponse(data)


def qr_image_view(request, kod):
    """Serial uchun QR PNG rasm qaytaradi — bugun 'yuklab olish' tugmasi, ertaga
    Desktop Agent ham shu endpointdan foydalanadi."""
    import qrcode
    from io import BytesIO
    from django.http import HttpResponse, Http404
    from main.models import Serial

    if not Serial.objects.filter(kod=kod).exists():
        raise Http404("Serial topilmadi")

    scan_url = f"https://{settings.BASE_DOMAIN}/p/{kod}/"
    img = qrcode.make(scan_url)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')

@user_passes_test(lambda u: u.is_superuser)
def plan_requests_list(request):
    """Barcha tarif so'rovlari ro'yxati"""
    requests = PlanRequest.objects.filter(status='pending').order_by('-created_at')
    return render(request, 'landing/plan_requests.html', {'requests': requests})

@user_passes_test(lambda u: u.is_superuser)
def approve_plan_request(request, request_id):
    """Tarif so'rovini tasdiqlash"""
    plan_request = get_object_or_404(PlanRequest, id=request_id)
    company = apply_plan_request(plan_request)
    send_company_notification(
        company,
        "Tarif tasdiqlandi",
        "Tarif so'rovingiz admin tomonidan tasdiqlandi.",
        "success",
        refresh=True,
    )
    messages.success(request, f"{company.name} uchun tarif muvaffaqiyatli o'zgartirildi.")
    broadcast_superadmin_update()
    return redirect('plan_requests_list')


@user_passes_test(lambda u: u.is_superuser)
def reject_plan_request(request, request_id):
    """Tarif so'rovini rad etish"""
    plan_request = get_object_or_404(PlanRequest, id=request_id)
    reject_plan_request_service(plan_request)
    send_company_notification(
        plan_request.company,
        "Tarif rad etildi",
        "Tarif so'rovingiz admin tomonidan rad etildi.",
        "warning",
        refresh=True,
    )
    
    messages.warning(request, f"{plan_request.company.name} so'rovi rad etildi.")
    broadcast_superadmin_update()
    return redirect('plan_requests_list')

@user_passes_test(lambda u: u.is_superuser)
def super_billing_report(request):
    """Barcha firmalar bo'yicha to'lovlar hisoboti"""
    from django.core.paginator import Paginator

    companies_qs = Company.objects.all().order_by('-created_at')

    # Search
    q = request.GET.get('q', '').strip()
    if q:
        companies_qs = companies_qs.filter(
            Q(name__icontains=q) | Q(subdomain__icontains=q)
        )

    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter == 'paid':
        companies_qs = companies_qs.filter(payment_status='paid')
    elif status_filter == 'unpaid':
        companies_qs = companies_qs.filter(payment_status='unpaid')
    elif status_filter == 'inactive':
        companies_qs = companies_qs.filter(is_active=False)

    total_companies = Company.objects.count()
    paid_companies = Company.objects.filter(payment_status='paid').count()
    unpaid_companies = Company.objects.filter(payment_status='unpaid').count()
    inactive_companies = Company.objects.filter(is_active=False).count()

    # Pagination
    paginator = Paginator(companies_qs, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    companies = list(page_obj)

    partial_payment_count = 0
    for company in companies:
        sync_company_lifecycle(company)
        prorated_billing = get_prorated_billing(company)
        company.prorated_amount_usd = prorated_billing['amount']
        company.prorated_reason = prorated_billing['reason']
        company.has_prorated_due = prorated_billing['amount'] > 0
        company.latest_prorated_link = company.billing_payment_links.filter(
            reason__startswith='Tarif farqi:',
            status__in=['created', 'opened'],
        ).order_by('-created_at').first()
        if company.has_prorated_due:
            partial_payment_count += 1

    context = {
        'companies': companies,
        'page_obj': page_obj,
        'total_companies': total_companies,
        'paid_companies': paid_companies,
        'unpaid_companies': unpaid_companies,
        'inactive_companies': inactive_companies,
        'partial_payment_count': partial_payment_count,
        'debug_mode': settings.DEBUG,
        'q': q,
        'status_filter': status_filter,
    }

    return render(request, 'landing/super_billing.html', context)

@user_passes_test(lambda u: u.is_superuser)
def update_billing_status(request, company_id):
    """Firma to'lov holatini va start/stop tugmasini ishlatish"""
    if request.method == 'POST':
        company = get_object_or_404(Company, id=company_id)
        action = request.POST.get('action')
        
        if action == 'toggle_active':
            company.is_active = not company.is_active
            status_text = "faollashtirildi" if company.is_active else "to'xtatildi"
            messages.success(request, f"🏢 {company.name} tizimi {status_text}.")
            company.save(update_fields=['is_active'])
            broadcast_superadmin_update()
            
        elif action == 'mark_paid':
            company = mark_company_paid(company)
            messages.success(request, f"💵 {company.name} to'lovi qabul qilindi. Keyingi to'lov: {company.next_payment_date.strftime('%d.%m.%Y')}")
            broadcast_superadmin_update()

        elif action == 'mark_prorated_paid':
            prorated_billing = get_prorated_billing(company)
            if prorated_billing['amount'] <= 0:
                messages.info(request, f"{company.name} uchun chala to'lov topilmadi.")
                return redirect('super_billing_report')

            payment_link = company.billing_payment_links.filter(
                reason__startswith='Tarif farqi:',
                status__in=['created', 'opened'],
            ).order_by('-created_at').first()
            if not payment_link:
                payment_link = BillingPaymentLink.objects.create(
                    company=company,
                    reason=prorated_billing['reason'],
                    billing_period_start=get_billing_period_start(company),
                    amount_usd=prorated_billing['amount'],
                    amount_uzs=0,
                    click_url='admin-marked',
                    status='created',
                )

            payment_link.status = 'paid'
            payment_link.paid_at = timezone.now()
            payment_link.save(update_fields=['status', 'paid_at'])
            mark_company_paid(company, payment_link=payment_link)
            messages.success(request, f"{company.name} tarif farqi (${prorated_billing['amount']}) to'landi deb belgilandi.")
            broadcast_superadmin_update()

        elif action == 'mark_unpaid':
            mark_company_unpaid(company)
            messages.warning(request, f"⚠️ {company.name} to'lovi 'to'lanmagan' deb belgilandi.")
            broadcast_superadmin_update()

    return redirect('super_billing_report')


@user_passes_test(is_superuser)
def super_backup_page(request):
    """
    Superadmin uchun zaxira (backup) sahifasi — yoki bitta firma, yoki
    butun tizim (barcha firmalar + media) zaxirasini yuklab olish mumkin.
    Faqat yuklab olish (export) uchun — qayta tiklash (restore) admin
    panel orqali amalga oshirilmaydi (server ko'chirilganda qo'lda,
    `loaddata` orqali qilinadi).
    """
    companies = Company.objects.all().order_by('name')
    return render(request, "landing/super_backup.html", {'companies': companies})


@user_passes_test(is_superuser)
def super_backup_download(request):
    """Superadmin uchun ZIP zaxirani yuklab olish (bitta firma yoki butun tizim)."""
    from django.http import HttpResponse
    from main.backup_utils import generate_backup, generate_full_system_backup

    scope = request.GET.get('scope')
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')

    if scope == 'full':
        try:
            memory_zip = generate_full_system_backup()
        except Exception as e:
            messages.error(request, f"Butun tizim zaxirasini yaratishda xato: {str(e)}")
            return redirect('super_backup_page')
        filename = f"stockfirm_full_system_backup_{timestamp}.zip"
    elif scope == 'company':
        company_id = request.GET.get('company_id')
        company = get_object_or_404(Company, id=company_id)
        try:
            memory_zip = generate_backup(company)
        except Exception as e:
            messages.error(request, f"{company.name} uchun zaxira yaratishda xato: {str(e)}")
            return redirect('super_backup_page')
        company.last_backup_at = timezone.now()
        company.save(update_fields=['last_backup_at'])
        filename = f"backup_{company.subdomain}_{timestamp}.zip"
    else:
        messages.error(request, "Zaxira turi ko'rsatilmagan.")
        return redirect('super_backup_page')

    response = HttpResponse(memory_zip.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

