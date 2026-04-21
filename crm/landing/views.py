import json
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from main.models import Company, User, Plan, PlanRequest
from django.db import models, transaction
from django.db.models import Count, Q, Sum
from django.contrib.auth.decorators import user_passes_test
from django.utils import timezone
from datetime import timedelta
from main.services.auth_service import create_user_service
from main.services.billing_service import (
    apply_plan_request,
    get_company_login_url,
    mark_company_paid,
    mark_company_unpaid,
    reject_plan_request as reject_plan_request_service,
    sync_company_lifecycle,
)

def landing_home(request):
    if not getattr(request, "is_landing", False):
        return redirect('/') 
    return render(request, "landing/home_pro.html")


MARKETING_PAGES = {
    "features": {
        "eyebrow": "Platforma",
        "title": "StockFirm CRM nimalarni hal qiladi?",
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
            ("Rollar", "Ega, pazanda va yetkazuvchi huquqlari farqlanadi."),
            ("Audit", "Muhim harakatlar jurnalga yoziladi."),
            ("Backup", "Kerak bo'lsa ma'lumotlarni eksport va tiklash."),
        ],
    },
    "implementation": {
        "eyebrow": "Joriy qilish",
        "title": "StockFirm CRM'ni ishga tushirish murakkab emas.",
        "lead": "Firma ochiladi, subdomain tanlanadi, mahsulot va hodimlar kiritiladi, keyin jarayonlar tizimga o'tkaziladi.",
        "items": [
            ("1-qadam", "Firma va ega akkaunti yaratiladi."),
            ("2-qadam", "Mahsulot turlari, mahsulotlar va mijozlar kiritiladi."),
            ("3-qadam", "Pazanda va yetkazuvchilar qo'shiladi."),
            ("4-qadam", "Savdo, zaxira va hisobotlar real ishda sinovdan o'tadi."),
        ],
    },
    "contact": {
        "eyebrow": "Aloqa",
        "title": "Tizimni biznesingizga moslab ko'rishni xohlaysizmi?",
        "lead": "Demo, pilot firma yoki individual tarif bo'yicha bog'laning. Sizning jarayoningizni CRM oqimiga moslab beramiz.",
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

def register_company(request):
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        subdomain = (request.POST.get('subdomain') or '').lower()
        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        password = request.POST.get('password')
        phone = request.POST.get('phone')

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
    # Overall counts
    total_companies = Company.objects.count()
    active_companies = Company.objects.filter(is_active=True).count()
    trial_companies = Company.objects.filter(is_on_trial=True).count()
    setup_companies = Company.objects.filter(setup_mode=True).count()
    total_users = User.objects.count()
    
    # Registrations in the last 24 hours
    now = timezone.now()
    yesterday = now - timezone.timedelta(days=1)
    today_registrations = Company.objects.filter(created_at__gte=yesterday).count()
    
    # Stats for charts (last 7 days)
    chart_data = []
    labels = []
    for i in range(6, -1, -1):
        day = now.date() - timezone.timedelta(days=i)
        count = Company.objects.filter(created_at__date=day).count()
        labels.append(day.strftime('%d-%b'))
        chart_data.append(count)
    
    recent_companies = Company.objects.all().order_by('-created_at')[:5]
    
    context = {
        'total_companies': total_companies,
        'active_companies': active_companies,
        'trial_companies': trial_companies,
        'setup_companies': setup_companies,
        'total_users': total_users,
        'today_registrations': today_registrations,
        'recent_companies': recent_companies,
        'chart_labels': json.dumps(labels),
        'chart_data': json.dumps(chart_data),
    }
    return render(request, "landing/super_dashboard.html", context)

@user_passes_test(is_superuser)
def super_companies(request):
    companies = Company.objects.annotate(
        total_users=Count('user'),
        staff_count=Count('user', filter=~models.Q(user__type='ega'))
    ).order_by('-created_at')
    return render(request, "landing/super_companies.html", {'companies': companies})

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
                messages.success(request, f"{name} firmasi muvaffaqiyatli qo'shildi.")
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
            else:
                company.plan = None
            company.save()
            messages.success(request, "Firma ma'lumotlari yangilandi.")
            return redirect('super_companies')
            
    plans = Plan.objects.all()
    return render(request, "landing/super_company_form.html", {
        'company': company,
        'plans': plans,
        'action': 'Tahrirlash'
    })

@user_passes_test(is_superuser)
def super_company_delete(request, pk):
    company = get_object_or_404(Company, pk=pk)
    if request.method == 'POST':
        name = company.name
        company.delete()
        messages.success(request, f"{name} firmasi o'chirildi.")
    return redirect('super_companies')

@user_passes_test(is_superuser)
def super_plan_list(request):
    plans = Plan.objects.all().order_by('-created_at')
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
            
            Plan.objects.create(
                name=name,
                description=description,
                price=price,
                max_users=max_users,
                has_telegram_bot=has_telegram_bot,
                has_analytics=has_analytics,
                has_map=has_map,
                backup_type=backup_type
            )
            messages.success(request, "Tarif muvaffaqiyatli qo'shildi.")
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
            plan.description = request.POST.get('description')
            plan.price = request.POST.get('price')
            plan.max_users = request.POST.get('max_users')
            plan.has_telegram_bot = request.POST.get('has_telegram_bot') == 'on'
            plan.has_analytics = request.POST.get('has_analytics') == 'on'
            plan.has_map = request.POST.get('has_map') == 'on'
            plan.backup_type = request.POST.get('backup_type', 'none')
            plan.save()
            messages.success(request, "Tarif ma'lumotlari yangilandi.")
            return redirect('super_plan_list')
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")
            
    return render(request, "landing/super_plan_form.html", {
        'plan': plan,
        'action': 'Tahrirlash'
    })

@user_passes_test(is_superuser)
def super_plan_delete(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    if request.method == 'POST':
        name = plan.name
        plan.delete()
        messages.success(request, f"{name} tarifi o'chirildi.")
    return redirect('super_plan_list')

def custom_404(request, exception=None):
    return render(request, '404.html', status=404)

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
    messages.success(request, f"{company.name} uchun tarif muvaffaqiyatli o'zgartirildi.")
    return redirect('plan_requests_list')


@user_passes_test(lambda u: u.is_superuser)
def reject_plan_request(request, request_id):
    """Tarif so'rovini rad etish"""
    plan_request = get_object_or_404(PlanRequest, id=request_id)
    reject_plan_request_service(plan_request)
    
    messages.warning(request, f"{plan_request.company.name} so'rovi rad etildi.")
    return redirect('plan_requests_list')

@user_passes_test(lambda u: u.is_superuser)
def super_billing_report(request):
    """Barcha firmalar bo'yicha to'lovlar hisoboti"""
    companies = Company.objects.all().order_by('-created_at')
    
    # Calculate some summary stats for the dashboard header
    total_companies = companies.count()
    paid_companies = companies.filter(payment_status='paid').count()
    unpaid_companies = companies.filter(payment_status='unpaid').count()
    inactive_companies = companies.filter(is_active=False).count()
    
    context = {
        'companies': companies,
        'total_companies': total_companies,
        'paid_companies': paid_companies,
        'unpaid_companies': unpaid_companies,
        'inactive_companies': inactive_companies,
        'debug_mode': settings.DEBUG,
    }

    # Admin billing sahifasiga kirganida barcha firmalar lifecycle tekshiruvi
    for company in companies:
        sync_company_lifecycle(company)

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
            
        elif action == 'mark_paid':
            if not settings.DEBUG:
                return redirect('super_billing_report')
            company = mark_company_paid(company)
            messages.success(request, f"💵 {company.name} to'lovi qabul qilindi. Keyingi to'lov: {company.next_payment_date.strftime('%d.%m.%Y')}")
            
        elif action == 'mark_unpaid':
            mark_company_unpaid(company)
            messages.warning(request, f"⚠️ {company.name} to'lovi 'to'lanmagan' deb belgilandi.")
        
    return redirect('super_billing_report')

