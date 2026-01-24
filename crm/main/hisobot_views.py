from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Savdo, User, YetkazibBeruvchi, Pazanda, Mahsulot
from django.db.models import Sum, Count, Q
import datetime as dt
from .functions import add_spctoint
import calendar


@login_required(login_url='login')
def hisobotlar_view(request):
    """Professional hisobotlar sahifasi with hierarchical filtering"""
    
    if request.user.type != 'ega':
        return redirect('main')
    
    now = timezone.localtime()
    
    # System start date (first sale ever)
    first_sale = Savdo.objects.order_by('vaqt_sana').first()
    system_start_date = first_sale.vaqt_sana if first_sale else now
    
    # Get filter parameters (default: daily with current day)
    filter_type = request.GET.get('type', 'daily')  # Default to daily
    selected_year = int(request.GET.get('year', now.year))
    selected_month = int(request.GET.get('month', now.month))
    selected_week = request.GET.get('week', None)
    selected_day = request.GET.get('day', str(now.day))  # Default to current day
    employee_id = request.GET.get('employee', None)
    
    # Generate available years (from system start to current)
    available_years = list(range(system_start_date.year, now.year + 1))
    
    # Generate available months for selected year
    available_months = []
    for month in range(1, 13):
        # Get last day of month to check if month contains or is after system start
        _, last_day_of_month = calendar.monthrange(selected_year, month)
        month_start = dt.date(selected_year, month, 1)
        month_end = dt.date(selected_year, month, last_day_of_month)
        
        # Month is available if:
        # 1. Month end is >= system start (month contains or is after start)
        # 2. Year < current OR (year == current AND month <= current)
        is_in_range = month_end >= system_start_date.date()
        is_not_future = (selected_year < now.year) or (selected_year == now.year and month <= now.month)
        
        if is_in_range:
            available_months.append({
                'number': month,
                'name': calendar.month_name[month],
                'is_available': is_not_future
            })
    
    # Generate available weeks for selected month
    available_weeks = []
    if selected_year and selected_month:
        # Get first and last day of month
        _, last_day = calendar.monthrange(selected_year, selected_month)
        month_start = dt.date(selected_year, selected_month, 1)
        month_end = dt.date(selected_year, selected_month, last_day)
        
        # Generate weeks
        current_date = month_start
        week_num = 1
        while current_date <= month_end:
            # Get week start (Monday)
            week_start = current_date - dt.timedelta(days=current_date.weekday())
            if week_start < month_start:
                week_start = month_start
            
            # Get week end (Sunday or month end)
            week_end = week_start + dt.timedelta(days=6)
            if week_end > month_end:
                week_end = month_end
            
            # Check if week is available (not in future)
            is_available = week_end <= now.date()
            
            available_weeks.append({
                'number': week_num,
                'start': week_start,
                'end': week_end,
                'label': f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}",
                'is_available': is_available
            })
            
            current_date = week_end + dt.timedelta(days=1)
            week_num += 1
    
    # Generate available days for selected month
    available_days = []
    if selected_year and selected_month:
        _, last_day = calendar.monthrange(selected_year, selected_month)
        for day in range(1, last_day + 1):
            day_date = dt.date(selected_year, selected_month, day)
            is_available = day_date <= now.date() and day_date >= system_start_date.date()
            available_days.append({
                'number': day,
                'date': day_date,
                'is_available': is_available
            })
    
    # Calculate date range based on filter type
    if filter_type == 'yearly':
        start_date = timezone.make_aware(dt.datetime(selected_year, 1, 1, 0, 0, 0))
        end_date = timezone.make_aware(dt.datetime(selected_year, 12, 31, 23, 59, 59))
        period_label = f"{selected_year} yil"
        
    elif filter_type == 'monthly':
        _, last_day = calendar.monthrange(selected_year, selected_month)
        start_date = timezone.make_aware(dt.datetime(selected_year, selected_month, 1, 0, 0, 0))
        end_date = timezone.make_aware(dt.datetime(selected_year, selected_month, last_day, 23, 59, 59))
        period_label = f"{calendar.month_name[selected_month]} {selected_year}"
        
    elif filter_type == 'weekly' and selected_week:
        # Parse week number and get dates
        week_idx = int(selected_week) - 1
        if week_idx < len(available_weeks):
            week_info = available_weeks[week_idx]
            start_date = timezone.make_aware(dt.datetime.combine(week_info['start'], dt.time.min))
            end_date = timezone.make_aware(dt.datetime.combine(week_info['end'], dt.time.max))
            period_label = f"Hafta {selected_week} ({week_info['label']})"
        else:
            # Default to first week
            start_date = timezone.make_aware(dt.datetime.combine(available_weeks[0]['start'], dt.time.min))
            end_date = timezone.make_aware(dt.datetime.combine(available_weeks[0]['end'], dt.time.max))
            period_label = f"Hafta 1"
            
    elif filter_type == 'daily' and selected_day:
        day_num = int(selected_day)
        start_date = timezone.make_aware(dt.datetime(selected_year, selected_month, day_num, 0, 0, 0))
        end_date = timezone.make_aware(dt.datetime(selected_year, selected_month, day_num, 23, 59, 59))
        period_label = f"{day_num} {calendar.month_name[selected_month]} {selected_year}"
        
    else:
        # Default to current month
        _, last_day = calendar.monthrange(now.year, now.month)
        start_date = timezone.make_aware(dt.datetime(now.year, now.month, 1, 0, 0, 0))
        end_date = timezone.make_aware(dt.datetime(now.year, now.month, last_day, 23, 59, 59))
        period_label = f"{calendar.month_name[now.month]} {now.year}"
    
    # Base queryset
    savdolar = Savdo.objects.filter(vaqt_sana__range=(start_date, end_date))
    
    # Employee filter
    employee_name = None
    if employee_id:
        try:
            employee = User.objects.get(id=employee_id)
            if employee.type == 'yetkazib_beruvchi':
                yetkazuvchi = YetkazibBeruvchi.objects.get(user=employee)
                savdolar = savdolar.filter(yetkazib_beruvchi=yetkazuvchi)
            employee_name = employee.tuliq_ismi
        except:
            pass
    
    # Statistics
    total_sales = savdolar.count()
    total_amount = sum([s.summa or 0 for s in savdolar])
    
    # Payment types
    naqd_sales = savdolar.filter(st='naqd').count()
    karta_sales = savdolar.filter(st='karta').count()
    nasiya_sales = savdolar.filter(st='nasiya').count()
    
    naqd_amount = sum([s.summa or 0 for s in savdolar.filter(st='naqd')])
    karta_amount = sum([s.summa or 0 for s in savdolar.filter(st='karta')])
    nasiya_amount = sum([s.summa or 0 for s in savdolar.filter(st='nasiya')])
    
    # Paid/Unpaid
    paid_count = savdolar.filter(tulandi=True).count()
    unpaid_count = savdolar.filter(tulandi=False).count()
    
    # Delivery stats
    yetkazuvchilar_stats = []
    for yetkazuvchi in YetkazibBeruvchi.objects.all():
        y_sales = savdolar.filter(yetkazib_beruvchi=yetkazuvchi)
        if y_sales.exists():
            yetkazuvchilar_stats.append({
                'user': yetkazuvchi.user,
                'sales_count': y_sales.count(),
                'total_amount': sum([s.summa or 0 for s in y_sales]),
            })
    
    yetkazuvchilar_stats = sorted(yetkazuvchilar_stats, key=lambda x: x['total_amount'], reverse=True)
    
    # Recent sales
    recent_sales = savdolar.order_by('-vaqt_sana')[:10]
    
    # Get all employees for dropdown
    employees = User.objects.filter(Q(type='yetkazib_beruvchi') | Q(type='pazanda')).order_by('tuliq_ismi')
    
    context = {
        'filter_type': filter_type,
        'period_label': period_label,
        'employee_id': employee_id,
        'employee_name': employee_name,
        'employees': employees,
        'start_date': start_date,
        'end_date': end_date,
        
        # Filter options
        'available_years': available_years,
        'available_months': available_months,
        'available_weeks': available_weeks,
        'available_days': available_days,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'selected_week': selected_week,
        'selected_day': selected_day,
        
        # Main stats
        'total_sales': total_sales,
        'total_amount': add_spctoint(int(total_amount)),
        'total_amount_raw': total_amount,
        
        # Payment types
        'naqd_sales': naqd_sales,
        'karta_sales': karta_sales,
        'nasiya_sales': nasiya_sales,
        'naqd_amount': add_spctoint(int(naqd_amount)),
        'karta_amount': add_spctoint(int(karta_amount)),
        'nasiya_amount': add_spctoint(int(nasiya_amount)),
        
        # Paid status
        'paid_count': paid_count,
        'unpaid_count': unpaid_count,
        
        # Stats
        'yetkazuvchilar_stats': yetkazuvchilar_stats,
        'recent_sales': recent_sales,
    }
    
    return render(request, 'hisobotlar.html', context)
