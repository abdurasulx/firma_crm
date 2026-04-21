from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from .models import Savdo, NasiyaTolov, User, AmalLog
from django.db.models import Sum
import datetime as dt
from .credit_utils import credit_payment_summary


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
                    "notification_type": type,
                }
            )
    except Exception as exc:
        print(f"WS Notification Error: {exc}")


def build_nasiya_context(request, nasiya_savdolar, base_template, page_title):
    # Filter options
    status_filter = request.GET.get('status', 'all')  # all, paid, unpaid, overdue

    if status_filter == 'paid':
        nasiya_savdolar = nasiya_savdolar.filter(tulandi=True)
    elif status_filter == 'unpaid':
        nasiya_savdolar = nasiya_savdolar.filter(tulandi=False)
    elif status_filter == 'overdue':
        chegara = timezone.now() - dt.timedelta(days=7)
        nasiya_savdolar = nasiya_savdolar.filter(tulandi=False, vaqt_sana__lte=chegara)

    # Calculate statistics for each sale
    nasiya_list = []
    total_debt = 0
    total_paid_amount = 0
    overdue_count = 0
    overdue_total_debt = 0

    chegara = timezone.now() - dt.timedelta(days=7)

    for savdo in nasiya_savdolar:
        summary = credit_payment_summary(savdo)
        payments = summary['payments']
        total_payments = summary['total_payments']
        remaining = summary['remaining']
        is_fully_paid = summary['is_fully_paid']

        # Overdue check
        days_ago = (timezone.now() - savdo.vaqt_sana).days
        is_overdue = (summary['status_type'] == 'late') or ((not is_fully_paid) and (savdo.vaqt_sana <= chegara))

        nasiya_list.append({
            'savdo': savdo,
            'payments': payments,
            'total_payments': total_payments,
            'remaining': remaining,
            'is_fully_paid': is_fully_paid,
            'is_overdue': is_overdue,
            'days_ago': days_ago,
            'credit_summary': summary,
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

        # Overdue
        'overdue_count': overdue_count,
        'overdue_total_debt': overdue_total_debt,
        'base_template': base_template,
        'page_title': page_title,
    }


@login_required(login_url='login')
def nasiya_savdolar_view(request):
    """Nasiya savdolar sahifasi"""

    if request.user.type not in ['ega', 'savdogar']:
        return redirect('main')

    nasiya_savdolar = Savdo.objects.filter(company=request.company, st='nasiya').order_by('-vaqt_sana')
    if request.user.type == 'savdogar':
        nasiya_savdolar = nasiya_savdolar.filter(savdogar=request.user)

    context = build_nasiya_context(
        request,
        nasiya_savdolar,
        'ytbase.html' if request.user.type == 'savdogar' else 'egabase.html',
        "Nasiya Savdolar" if request.user.type == 'ega' else "Mening nasiya savdolarim",
    )
    return render(request, 'nasiya_savdolar.html', context)


@login_required(login_url='login')
def savdogar_nasiya_admin_view(request):
    """Admin uchun faqat savdogarlar qilgan nasiya savdolar."""
    if request.user.type != 'ega':
        return redirect('main')

    nasiya_savdolar = Savdo.objects.filter(
        company=request.company,
        st='nasiya',
        savdogar__isnull=False,
    ).select_related('savdogar', 'haridor_dukon').order_by('-vaqt_sana')

    savdogar_id = request.GET.get('savdogar')
    if savdogar_id:
        nasiya_savdolar = nasiya_savdolar.filter(savdogar_id=savdogar_id)

    context = build_nasiya_context(request, nasiya_savdolar, 'egabase.html', "Savdogar nasiya savdolari")
    context['savdogarlar'] = User.objects.filter(company=request.company, type='savdogar').order_by('tuliq_ismi')
    context['savdogar_filter'] = savdogar_id or ''
    return render(request, 'nasiya_savdolar.html', context)


@login_required(login_url='login')
def add_nasiya_payment(request, savdo_id):
    """Add payment for credit sale"""
    
    if request.user.type not in ['ega', 'savdogar']:
        return redirect('main')
    
    if request.method == 'POST':
        try:
            from django.db import transaction
            with transaction.atomic():
                savdo = Savdo.objects.select_for_update().get(id=savdo_id, company=request.company)
                if request.user.type == 'savdogar' and savdo.savdogar_id != request.user.id:
                    messages.error(request, "Ushbu nasiya savdosi sizga tegishli emas.")
                    return redirect('nasiya_savdolar')
                payment_amount = float(request.POST.get('payment_amount', 0))
                note = request.POST.get('note', '')
                
                if payment_amount <= 0:
                    messages.error(request, "To'lov summasi 0 dan katta bo'lishi kerak!")
                    return redirect('nasiya_savdolar')
                
                # Get current payments
                summary = credit_payment_summary(savdo)
                remaining = summary['remaining']
                
                if payment_amount > remaining:
                    messages.error(request, f"To'lov summasi qoldiqdan ({remaining}) katta bo'lishi mumkin emas!")
                    return redirect('nasiya_savdolar')
                
                # Create payment
                NasiyaTolov.objects.create(
                    savdo=savdo,
                    tolov_summasi=payment_amount,
                    izoh=note,
                    qabul_qilgan_user=request.user,
                    company=request.company
                )
                
                # Update sale status if fully paid
                new_total = summary['total_payments'] + payment_amount
                if new_total >= (savdo.summa or 0) + summary['late_penalty']:
                    savdo.tulandi = True
                    savdo.save()
                
                messages.success(request, f"{payment_amount} so'm to'lov qabul qilindi!")
                send_ws_notification(
                    request.company.subdomain,
                    "Nasiya to'lovi qabul qilindi",
                    f"{savdo.haridor_dukon.nomi} bo'yicha {payment_amount:,.0f} so'm to'lov qabul qilindi.",
                    'success'
                )
            
        except Exception as e:
            messages.error(request, f"Xato: {str(e)}")
    
    return redirect('nasiya_savdolar')
