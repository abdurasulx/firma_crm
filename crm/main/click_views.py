import hashlib
import requests
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta
from main.models import Company, ClickTransaction

CLICK_SECRET_KEY = 'HaLZ1bWlBHY'
CLICK_MERCHANT_ID = '40045'
CLICK_SERVICE_ID = '80588'

def check_sign(request_data):
    # sign_string = md5 ( click_trans_id + service_id + secret_key + merchant_trans_id + amount + action + sign_time )
    click_trans_id = request_data.get('click_trans_id', '')
    service_id = request_data.get('service_id', '')
    merchant_trans_id = request_data.get('merchant_trans_id', '')
    amount = request_data.get('amount', '')
    action = request_data.get('action', '')
    sign_time = request_data.get('sign_time', '')
    
    sign_string = f"{click_trans_id}{service_id}{CLICK_SECRET_KEY}{merchant_trans_id}{amount}{action}{sign_time}"
    sign_hash = hashlib.md5(sign_string.encode('utf-8')).hexdigest()
    
    return sign_hash == request_data.get('sign_string', '')

def get_usd_rate():
    rate = cache.get('usd_rate')
    if rate:
        return rate
    try:
        response = requests.get('https://cbu.uz/uz/arkhiv-kursov-valyut/json/', timeout=5)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                if item['Ccy'] == 'USD':
                    rate = float(item['Rate'])
                    cache.set('usd_rate', rate, 3600 * 12) # cache for 12 hours
                    return rate
    except Exception:
        pass
    return 12500.0 # fallback conservative rate

def click_pay_redirect(request):
    if not hasattr(request, 'company') or not request.company:
        return redirect('login')
        
    company = request.company
    if company.plan:
        price_usd = float(company.plan.price)
    else:
        price_usd = float(company.custom_price)
        
    if price_usd <= 0:
        return redirect('main') # Free or error
        
    usd_rate = get_usd_rate()
    price_uzs = int(price_usd * usd_rate)
    
    url = f"https://my.click.uz/services/pay?service_id={CLICK_SERVICE_ID}&merchant_id={CLICK_MERCHANT_ID}&amount={price_uzs}&transaction_param={company.id}"
    return redirect(url)

@csrf_exempt
def click_prepare(request):
    if request.method == 'POST':
        if not check_sign(request.POST):
            return JsonResponse({'error': -1, 'error_note': 'SIGN CHECK FAILED'})
        
        click_trans_id = request.POST.get('click_trans_id')
        merchant_trans_id = request.POST.get('merchant_trans_id') # company_id
        # amount might have decimal, Click sends it like 1000.00
        # float handles it
        try:
            amount = float(request.POST.get('amount', 0))
        except ValueError:
            return JsonResponse({'error': -2, 'error_note': 'Incorrect parameter amount'})
            
        try:
            company = Company.objects.get(id=int(merchant_trans_id))
        except (Company.DoesNotExist, ValueError):
            return JsonResponse({'error': -5, 'error_note': 'USER NOT FOUND'})
        
        
        # Check if transaction already exists
        if ClickTransaction.objects.filter(click_trans_id=click_trans_id).exists():
            return JsonResponse({'error': -6, 'error_note': 'TRANSACTION ALREADY EXISTS'})
            
        # Create transaction record
        tx = ClickTransaction.objects.create(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            company=company,
            amount=amount,
            action=request.POST.get('action', 0),
            sign_time=request.POST.get('sign_time', ''),
            sign_string=request.POST.get('sign_string', ''),
            status='processing'
        )
        
        return JsonResponse({
            'click_trans_id': click_trans_id,
            'merchant_trans_id': merchant_trans_id,
            'merchant_prepare_id': tx.id,
            'error': 0,
            'error_note': 'Success'
        })
    return JsonResponse({'error': -8, 'error_note': 'Error request'})

@csrf_exempt
def click_complete(request):
    if request.method == 'POST':
        if not check_sign(request.POST):
            return JsonResponse({'error': -1, 'error_note': 'SIGN CHECK FAILED'})
            
        click_trans_id = request.POST.get('click_trans_id')
        merchant_trans_id = request.POST.get('merchant_trans_id')
        merchant_prepare_id = request.POST.get('merchant_prepare_id')
        error = int(request.POST.get('error', 0))
        
        try:
            tx = ClickTransaction.objects.get(id=merchant_prepare_id, click_trans_id=click_trans_id)
        except ClickTransaction.DoesNotExist:
            return JsonResponse({'error': -6, 'error_note': 'TRANSACTION NOT FOUND'})
            
        if tx.status == 'paid':
            return JsonResponse({'error': -4, 'error_note': 'ALREADY PAID'})
        elif tx.status == 'canceled':
            return JsonResponse({'error': -9, 'error_note': 'TRANSACTION CANCELLED'})
            
        if error < 0:
            tx.status = 'error'
            tx.error_reason = str(error) # click error
            tx.cancel_time = timezone.now()
            tx.save()
            return JsonResponse({'error': -9, 'error_note': 'TRANSACTION CANCELLED'})
            
        # Success!
        tx.status = 'paid'
        tx.perform_time = timezone.now()
        tx.save()
        
        # Apply logic to the company
        company = tx.company
        company.payment_status = 'paid'
        
        # Add 30 days
        if company.next_payment_date and company.next_payment_date > timezone.now():
            company.next_payment_date = company.next_payment_date + timedelta(days=30)
        else:
            company.next_payment_date = timezone.now() + timedelta(days=30)
            
        # Standardize trial end
        company.is_on_trial = False
        company.trial_expires_at = None
        
        company.save()
        
        return JsonResponse({
            'click_trans_id': click_trans_id,
            'merchant_trans_id': merchant_trans_id,
            'merchant_confirm_id': tx.id,
            'error': 0,
            'error_note': 'Success'
        })
        
    return JsonResponse({'error': -8, 'error_note': 'Error request'})
