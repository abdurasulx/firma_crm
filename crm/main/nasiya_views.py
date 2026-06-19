from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from .models import Savdo, NasiyaTolov, User, AmalLog, YetkazibBeruvchi
from .services.credit_service import calculate_current_payoff_total
from django.db import models
from django.db.models import Sum
import datetime as dt


@login_required(login_url='login')
def nasiya_savdolar_view(request):
    """Nasiya savdolar sahifasi"""

    if request.user.type != 'ega':
        return redirect('main')

    # Get all credit sales for this company
    nasiya_savdolar = Savdo.objects.filter(company=request.company, st='nasiya').order_by('-vaqt_sana')

    # Filter options
    status_filter = request.GET.get('status', 'all')  # all, paid, unpaid, overdue
    seller_id = request.GET.get('seller')
    sale_role = request.GET.get('role', 'all')
    selected_seller = None

    if sale_role in ['savdogar', 'yetkazib_beruvchi']:
        nasiya_savdolar = nasiya_savdolar.filter(yetkazib_beruvchi__user__type=sale_role)

    if seller_id:
        selected_seller = get_object_or_404(YetkazibBeruvchi, id=seller_id, company=request.company)
        nasiya_savdolar = nasiya_savdolar.filter(yetkazib_beruvchi=selected_seller)

    if status_filter == 'paid':
        nasiya_savdolar = nasiya_savdolar.filter(tulandi=True)
    elif status_filter == 'unpaid':
        nasiya_savdolar = nasiya_savdolar.filter(tulandi=False)
    elif status_filter == 'overdue':
        today = timezone.localdate()
        chegara = timezone.now() - dt.timedelta(days=7)
        nasiya_savdolar = nasiya_savdolar.filter(tulandi=False).filter(
            models.Q(credit_due_date__lt=today) | models.Q(credit_due_date__isnull=True, vaqt_sana__lte=chegara)
        )

    # Calculate statistics for each sale
    nasiya_list = []
    total_debt = 0
    total_paid_amount = 0
    overdue_count = 0
    overdue_total_debt = 0

    chegara = timezone.now() - dt.timedelta(days=7)

    for savdo in nasiya_savdolar:
        payments = NasiyaTolov.objects.filter(savdo=savdo).order_by('-tolov_sanasi')
        total_payments = sum([p.tolov_summasi for p in payments])

        if savdo.tulandi:
            # Order already closed — use stored summa so the display doesn't drift as time passes
            payoff_total = float(savdo.summa or 0)
            payoff_markup = float(savdo.credit_markup_percent or 0)
            payoff_months = savdo.credit_term_months
            remaining = 0
            is_fully_paid = True
        else:
            # Open order — calculate dynamically so "pay today" shows the correct bracket
            payoff_total, payoff_markup, payoff_months = calculate_current_payoff_total(savdo)
            remaining = max(payoff_total - total_payments, 0)
            is_fully_paid = remaining <= 0

        # Overdue check
        days_ago = (timezone.now() - savdo.vaqt_sana).days
        is_overdue = (not is_fully_paid) and (
            (savdo.credit_due_date and savdo.credit_due_date < timezone.localdate())
            or (not savdo.credit_due_date and savdo.vaqt_sana <= chegara)
        )
        due_soon = (not is_fully_paid) and savdo.credit_due_date and savdo.credit_due_date <= timezone.localdate() + dt.timedelta(days=7)

        nasiya_list.append({
            'savdo': savdo,
            'customer_name': savdo.haridor_dukon.nomi if savdo.haridor_dukon else savdo.oluvchining_ismi,
            'payments': payments,
            'total_payments': total_payments,
            'payoff_total': payoff_total,
            'payoff_markup': payoff_markup,
            'payoff_months': payoff_months,
            'remaining': remaining,
            'is_fully_paid': is_fully_paid,
            'is_overdue': is_overdue,
            'due_soon': due_soon,
            'days_ago': days_ago,
        })

        if remaining > 0:
            total_debt += remaining
            if is_overdue:
                overdue_count += 1
                overdue_total_debt += remaining

        total_paid_amount += total_payments

    # Overall statistics
    total_nasiya_count = nasiya_savdolar.count()
    total_nasiya_amount = sum([s.summa or 0 for s in nasiya_savdolar])
    paid_count = nasiya_savdolar.filter(tulandi=True).count()
    unpaid_count = nasiya_savdolar.filter(tulandi=False).count()
    due_soon_count = sum(1 for item in nasiya_list if item['due_soon'])

    sellers_qs = YetkazibBeruvchi.objects.filter(user__company=request.company).select_related('user').order_by('user__tuliq_ismi')
    if sale_role in ['savdogar', 'yetkazib_beruvchi']:
        sellers_qs = sellers_qs.filter(user__type=sale_role)

    context = {
        'nasiya_list': nasiya_list,
        'status_filter': status_filter,
        'seller_id': seller_id,
        'sale_role': sale_role,
        'selected_seller': selected_seller,
        'sellers': sellers_qs,

        # Statistics
        'total_nasiya_count': total_nasiya_count,
        'total_nasiya_amount': total_nasiya_amount,
        'total_debt': total_debt,
        'total_paid_amount': total_paid_amount,
        'paid_count': paid_count,
        'unpaid_count': unpaid_count,

        # Overdue
        'overdue_count': overdue_count,
        'overdue_total_debt': overdue_total_debt,
        'due_soon_count': due_soon_count,
    }

    return render(request, 'nasiya_savdolar.html', context)


@login_required(login_url='login')
def add_nasiya_payment(request, savdo_id):
    """Add payment for credit sale"""
    
    if request.user.type != 'ega':
        return redirect('main')
    
    if request.method == 'POST':
        try:
            from django.db import transaction
            with transaction.atomic():
                savdo = Savdo.objects.select_for_update().get(id=savdo_id, company=request.company)
                payment_amount = float(request.POST.get('payment_amount', 0))
                note = request.POST.get('note', '')
                
                if payment_amount <= 0:
                    messages.error(request, "To'lov summasi 0 dan katta bo'lishi kerak!")
                    return redirect('nasiya_savdolar')
                
                # Get current payments
                payments = NasiyaTolov.objects.filter(savdo=savdo)
                total_payments = sum([p.tolov_summasi for p in payments])
                payoff_total, payoff_markup, payoff_months = calculate_current_payoff_total(savdo)
                remaining = max(payoff_total - total_payments, 0)

                if payment_amount > remaining + 0.01:
                    messages.error(request, f"To'lov summasi qoldiqdan ({remaining:,.0f}) katta bo'lishi mumkin emas!")
                    return redirect('nasiya_savdolar')
                
                # Create payment
                NasiyaTolov.objects.create(
                    savdo=savdo,
                    tolov_summasi=payment_amount,
                    izoh=note,
                    qabul_qilgan_user=request.user,
                    company=request.company
                )

                # Recalculate after saving to get accurate total
                new_total = NasiyaTolov.objects.filter(savdo=savdo).aggregate(
                    total=Sum('tolov_summasi')
                )['total'] or 0
                if new_total >= payoff_total:
                    savdo.summa = payoff_total
                    savdo.credit_markup_percent = payoff_markup
                    savdo.credit_term_months = payoff_months
                    savdo.tulandi = True
                    savdo.save()
                
                messages.success(request, f"{payment_amount} so'm to'lov qabul qilindi!")
            
        except Exception as e:
            messages.error(request, f"Xato: {str(e)}")
    
    return redirect('nasiya_savdolar')
