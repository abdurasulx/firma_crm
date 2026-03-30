import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from main.models import Company, User, Plan, PlanRequest
from django.db import models, transaction
from django.db.models import Count, Q, Sum
from django.contrib.auth.decorators import user_passes_test
from django.utils import timezone
from datetime import timedelta

def landing_home(request):
    if not getattr(request, "is_landing", False):
        return redirect('/') 
    return render(request, "landing/index.html")

def pricing_view(request):
    return render(request, "landing/pricing.html")

def register_company(request):
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        subdomain = request.POST.get('subdomain').lower()
        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        password = request.POST.get('password')
        phone = request.POST.get('phone')

        if Company.objects.filter(subdomain=subdomain).exists():
            messages.error(request, "Bu subdomain allaqachon band!")
            return render(request, "landing/register.html", {'post_data': request.POST})

        if User.objects.filter(username=username).exists():
            messages.error(request, "Bu login allaqachon band!")
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
                
                # Create Admin User for this company
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    tuliq_ismi=full_name,
                    tel_raqami=phone,
                    type='ega',
                    company=company
                )
                
                messages.success(request, f"Tabriklaymiz! {company_name} muvaffaqiyatli ro'yxatdan o'tdi. 5 kunlik sozlash rejimi yoqildi.")
                # Redirect to the new subdomain's login page
                protocol = "http" # Simplified for local dev
                return redirect(f"{protocol}://{subdomain}.localhost:8000/login/")
                
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
        subdomain = request.POST.get('subdomain').lower()
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
                User.objects.create_user(
                    username=username,
                    password=password,
                    tuliq_ismi=full_name,
                    tel_raqami=phone,
                    type='ega',
                    company=company
                )
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
    company = plan_request.company
    
    if plan_request.is_trial:
        company.is_on_trial = True
        company.trial_expires_at = timezone.now() + timedelta(days=30)
        company.next_payment_date = company.trial_expires_at
        company.has_used_trial = True
        company.payment_status = 'paid' # Grant access during trial
    elif plan_request.is_custom:
        company.is_custom_plan = True
        company.plan = None
        company.custom_max_users = plan_request.custom_max_users
        company.custom_has_telegram_bot = plan_request.custom_has_telegram_bot
        company.custom_has_analytics = plan_request.custom_has_analytics
        company.custom_has_map = plan_request.custom_has_map
        company.custom_backup_type = plan_request.custom_backup_type
        company.custom_price = plan_request.custom_price
    else:
        company.plan = plan_request.plan
        company.is_custom_plan = False
        # Reset ALL custom fields to prevent stale data
        company.custom_max_users = 0
        company.custom_has_telegram_bot = False
        company.custom_has_analytics = False
        company.custom_has_map = False
        company.custom_backup_type = 'none'
        company.custom_price = 0
    
    if not plan_request.is_trial:
        # Set initial payment status to unpaid
        company.payment_status = 'unpaid'
        # Start the 5-day grace period
        company.next_payment_date = timezone.now() + timedelta(days=5)
        
        # Trial feature is disabled for normal plan upgrades
        company.is_on_trial = False
        company.has_used_trial = True # Mark as used so it never appears
        company.trial_expires_at = None
    
    company.save()
    
    plan_request.status = 'approved'
    plan_request.resolved_at = timezone.now()
    plan_request.save()
    
    messages.success(request, f"{company.name} uchun tarif muvaffaqiyatli o'zgartirildi.")
    return redirect('plan_requests_list')

@user_passes_test(lambda u: u.is_superuser)
def reject_plan_request(request, request_id):
    """Tarif so'rovini rad etish"""
    plan_request = get_object_or_404(PlanRequest, id=request_id)
    plan_request.status = 'rejected'
    plan_request.resolved_at = timezone.now()
    plan_request.save()
    
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
    }
    
    # Backfill logic for empty next_payment_date when visiting the dashboard
    for c in companies:
        if c.next_payment_date is None:
            c.next_payment_date = c.created_at + timedelta(days=5)
            c.save()
            
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
            
        elif action == 'mark_paid':
            company.payment_status = 'paid'
            # Add 30 days to their next payment date
            if company.next_payment_date and company.next_payment_date > timezone.now():
                company.next_payment_date = company.next_payment_date + timedelta(days=30)
            else:
                company.next_payment_date = timezone.now() + timedelta(days=30)
            
            # If they were inactive due to non-payment, we could auto activate them
            # company.is_active = True 
            
            messages.success(request, f"💵 {company.name} to'lovi qabul qilindi. Keyingi to'lov: {company.next_payment_date.strftime('%d.%m.%Y')}")
            
        elif action == 'mark_unpaid':
            company.payment_status = 'unpaid'
            messages.warning(request, f"⚠️ {company.name} to'lovi 'to'lanmagan' deb belgilandi.")
            
        company.save()
        
    return redirect('super_billing_report')
