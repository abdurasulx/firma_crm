from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import HaridorDukon, Savdo, NasiyaTolov
from django.db.models import Sum, Count, Q


@login_required(login_url='login')
def mijozlar_list(request):
    """Barcha mijozlar ro'yxati"""
    
    if request.user.type != 'ega':
        return redirect('main')
    
    mijozlar = HaridorDukon.objects.all().order_by('nomi')
    
    # Calculate statistics for each customer
    mijoz_stats = []
    
    for mijoz in mijozlar:
        # Get all sales for this customer
        savdolar = Savdo.objects.filter(haridor_dukon=mijoz)
        
        # Total sales
        total_sales = savdolar.count()
        total_amount = sum([s.summa or 0 for s in savdolar])
        
        # Credit sales
        nasiya_savdolar = savdolar.filter(st='nasiya')
        total_credit = sum([s.summa or 0 for s in nasiya_savdolar])
        
        # Calculate debt (unpaid credit)
        debt = 0
        for savdo in nasiya_savdolar:
            payments = NasiyaTolov.objects.filter(savdo=savdo)
            total_paid = sum([p.tolov_summasi for p in payments])
            remaining = (savdo.summa or 0) - total_paid
            if remaining > 0:
                debt += remaining
        
        mijoz_stats.append({
            'mijoz': mijoz,
            'total_sales': total_sales,
            'total_amount': total_amount,
            'total_credit': total_credit,
            'debt': debt,
            'has_debt': debt > 0
        })
    
    # Sort by debt (highest first)
    mijoz_stats = sorted(mijoz_stats, key=lambda x: x['debt'], reverse=True)
    
    # Overall statistics
    total_customers = mijozlar.count()
    total_debt_sum = sum([m['debt'] for m in mijoz_stats])
    customers_with_debt = len([m for m in mijoz_stats if m['has_debt']])
    
    context = {
        'mijoz_stats': mijoz_stats,
        'total_customers': total_customers,
        'total_debt_sum': total_debt_sum,
        'customers_with_debt': customers_with_debt,
    }
    
    return render(request, 'mijozlar_list.html', context)


@login_required(login_url='login')
def mijoz_detail(request, mijoz_id):
    """Mijoz batafsil sahifasi"""
    
    if request.user.type != 'ega':
        return redirect('main')
    
    mijoz = get_object_or_404(HaridorDukon, id=mijoz_id)
    
    # Get all sales
    savdolar = Savdo.objects.filter(haridor_dukon=mijoz).order_by('-vaqt_sana')
    
    # Statistics
    total_sales = savdolar.count()
    total_amount = sum([s.summa or 0 for s in savdolar])
    
    # Payment types
    naqd_amount = sum([s.summa or 0 for s in savdolar.filter(st='naqd')])
    karta_amount = sum([s.summa or 0 for s in savdolar.filter(st='karta')])
    nasiya_amount = sum([s.summa or 0 for s in savdolar.filter(st='nasiya')])
    
    # Credit details
    nasiya_savdolar = savdolar.filter(st='nasiya')
    credit_sales_list = []
    total_debt = 0
    total_paid_for_credits = 0
    
    for savdo in nasiya_savdolar:
        payments = NasiyaTolov.objects.filter(savdo=savdo).order_by('-tolov_sanasi')
        total_paid = sum([p.tolov_summasi for p in payments])
        remaining = (savdo.summa or 0) - total_paid
        
        credit_sales_list.append({
            'savdo': savdo,
            'payments': payments,
            'total_paid': total_paid,
            'remaining': remaining,
            'is_fully_paid': remaining <= 0
        })
        
        if remaining > 0:
            total_debt += remaining
        
        total_paid_for_credits += total_paid
    
    # Recent sales
    recent_sales = savdolar[:10]
    
    context = {
        'mijoz': mijoz,
        'total_sales': total_sales,
        'total_amount': total_amount,
        
        # Payment breakdown
        'naqd_amount': naqd_amount,
        'karta_amount': karta_amount,
        'nasiya_amount': nasiya_amount,
        
        # Credit info
        'credit_sales_list': credit_sales_list,
        'total_debt': total_debt,
        'total_paid_for_credits': total_paid_for_credits,
        
        # Recent sales
        'recent_sales': recent_sales,
    }
    
    return render(request, 'mijoz_detail.html', context)
