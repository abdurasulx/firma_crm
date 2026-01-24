from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count
from .models import Savdo, User, Mahsulot, YetkazibBeruvchi, Pazanda
import datetime as dt


@login_required(login_url='login')
def hisobotlar_view(request):
    """Asosiy hisobot sahifasi - faqat Ega ko'rishi mumkin"""
    if request.user.type != 'ega':
        return redirect('main')
    
    payload = {}
    now = timezone.localtime()
    
    # Bugungi savdolar
    today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
    today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))
    bugungi_savdolar = Savdo.objects.filter(vaqt_sana__range=(today_start, today_end))
    
    # Haftalik savdolar (oxirgi 7 kun)
    week_start = now - dt.timedelta(days=7)
    haftalik_savdolar = Savdo.objects.filter(vaqt_sana__gte=week_start)
    
    # Oylik savdolar
    month_start = timezone.make_aware(dt.datetime.combine(now.replace(day=1).date(), dt.time.min))
    oylik_savdolar = Savdo.objects.filter(vaqt_sana__range=(month_start, today_end))
    
    # Statistika
    payload['bugungi_summa'] = bugungi_savdolar.aggregate(Sum('summa'))['summa__sum'] or 0
    payload['bugungi_soni'] = bugungi_savdolar.count()
    
    payload['haftalik_summa'] = haftalik_savdolar.aggregate(Sum('summa'))['summa__sum'] or 0
    payload['haftalik_soni'] = haftalik_savdolar.count()
    
    payload['oylik_summa'] = oylik_savdolar.aggregate(Sum('summa'))['summa__sum'] or 0
    payload['oylik_soni'] = oylik_savdolar.count()
    
    # Nasiya savdolar
    nasiya_savdolar = oylik_savdolar.filter(st='nasiya', tulandi=False)
    payload['nasiya_soni'] = nasiya_savdolar.count()
    payload['nasiya_summa'] = nasiya_savdolar.aggregate(Sum('summa'))['summa__sum'] or 0
    
    # Yetkazib beruvchilar bo'yicha
    yetkazuvchilar = YetkazibBeruvchi.objects.all()
    yt_hisobot = []
    for yt in yetkazuvchilar:
        yt_savdo = oylik_savdolar.filter(yetkazib_beruvchi=yt)
        yt_hisobot.append({
            'ism': yt.tuliq_ismi,
            'savdo_soni': yt_savdo.count(),
            'jami_summa': yt_savdo.aggregate(Sum('summa'))['summa__sum'] or 0
        })
    payload['yt_hisobot'] = yt_hisobot
    
    # Oxirgi savdolar
    payload['oxirgi_savdolar'] = oylik_savdolar.order_by('-vaqt_sana')[:10]
    
    return render(request, 'hisobotlar.html', payload)
