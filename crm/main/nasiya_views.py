from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from .models import Savdo, NasiyaTolov, User
from django.db.models import Sum
import datetime as dt


@login_required(login_url='login')
def nasiya_savdolar_view(request):
    """Nasiya savdolar sahifasi"""
    
    if request.user.type != 'ega':
        return redirect('main')
    
    # Get all credit sales
    nasiya_savdolar = Savdo.objects.filter(st='nasiya').order_by('-vaqt_sana')
    
    # Filter options
    status_filter = request.GET.get('status', 'all')  # all, paid, unpaid
    
    if status_filter == 'paid':
        nasiya_savdolar = nasiya_savdolar.filter(tulandi=True)
    elif status_filter == 'unpaid':
        nasiya_savdolar = nasiya_savdolar.filter(tulandi=False)
    
    # Calculate statistics for each sale
    nasiya_list = []
    total_debt = 0
    total_paid_amount = 0
    
    for savdo in nasiya_savdolar:
        # Get all payments for this sale
        payments = NasiyaTolov.objects.filter(savdo=savdo).order_by('-tolov_sanasi')
        total_payments = sum([p.tolov_summasi for p in payments])
        
        remaining = (savdo.summa or 0) - total_payments
        
        nasiya_list.append({
            'savdo': savdo,
            'payments': payments,
            'total_payments': total_payments,
            'remaining': remaining,
            'is_fully_paid': remaining <= 0
        })
        
        if remaining > 0:
            total_debt += remaining
        
        total_paid_amount += total_payments
    
    # Overall statistics
    total_nasiya_count = nasiya_savdolar.count()
    total_nasiya_amount = sum([s.summa or 0 for s in nasiya_savdolar])
    paid_count = nasiya_savdolar.filter(tulandi=True).count()
    unpaid_count = nasiya_savdolar.filter(tulandi=False).count()
    
    context = {
        'nasiya_list': nasiya_list,
        'status_filter': status_filter,
        
        # Statistics
        'total_nasiya_count': total_nasiya_count,
        'total_nasiya_amount': total_nasiya_amount,
        'total_debt': total_debt,
        'total_paid_amount': total_paid_amount,
        'paid_count': paid_count,
        'unpaid_count': unpaid_count,
    }
    
    return render(request, 'nasiya_savdolar.html', context)


@login_required(login_url='login')
def add_nasiya_payment(request, savdo_id):
    """Add payment for credit sale"""
    
    if request.user.type != 'ega':
        return redirect('main')
    
    if request.method == 'POST':
        try:
            savdo = Savdo.objects.get(id=savdo_id)
            payment_amount = float(request.POST.get('payment_amount', 0))
            note = request.POST.get('note', '')
            
            if payment_amount <= 0:
                messages.error(request, "To'lov summasi 0 dan katta bo'lishi kerak!")
                return redirect('nasiya_savdolar')
            
            # Get current payments
            payments = NasiyaTolov.objects.filter(savdo=savdo)
            total_payments = sum([p.tolov_summasi for p in payments])
            remaining = (savdo.summa or 0) - total_payments
            
            if payment_amount > remaining:
                messages.error(request, f"To'lov summasi qoldiqdan ({remaining}) katta bo'lishi mumkin emas!")
                return redirect('nasiya_savdolar')
            
            # Create payment
            NasiyaTolov.objects.create(
                savdo=savdo,
                tolov_summasi=payment_amount,
                izoh=note,
                qabul_qilgan_user=request.user
            )
            
            # Update sale status if fully paid
            new_total = total_payments + payment_amount
            if new_total >= savdo.summa:
                savdo.tulandi = True
                savdo.save()
            
            messages.success(request, f"{payment_amount} so'm to'lov qabul qilindi!")
            
        except Exception as e:
            messages.error(request, f"Xato: {str(e)}")
    
    return redirect('nasiya_savdolar')
