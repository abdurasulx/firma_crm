"""
KPI — Kunlik maqsad va trend grafigi uchun viewlar
"""
import datetime as dt
import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.db.models import Sum
from django.views.decorators.http import require_POST

from .models import DailyTarget, Savdo, User


@login_required(login_url='login')
@require_POST
def set_daily_target(request):
    """Xodim uchun kunlik savdo maqsadini belgilash (faqat ega)"""
    if request.user.type != 'ega':
        return JsonResponse({'ok': False, 'error': 'Ruxsat yo\'q'}, status=403)

    user_id = request.POST.get('user_id')
    maqsad  = request.POST.get('maqsad')
    sana_str = request.POST.get('sana')

    try:
        user   = User.objects.get(id=user_id, company=request.company)
        maqsad = float(maqsad)
        sana   = dt.datetime.strptime(sana_str, '%Y-%m-%d').date() if sana_str else timezone.localtime().date()
    except (User.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Noto\'g\'ri ma\'lumot'}, status=400)

    obj, created = DailyTarget.objects.update_or_create(
        company=request.company,
        user=user,
        sana=sana,
        defaults={'maqsad': maqsad}
    )
    return JsonResponse({'ok': True, 'id': obj.pk, 'created': created})


@login_required(login_url='login')
def kpi_today(request):
    """Joriy foydalanuvchining bugungi KPI (JSON)"""
    today = timezone.localtime().date()
    today_start = timezone.make_aware(dt.datetime.combine(today, dt.time.min))
    today_end   = timezone.make_aware(dt.datetime.combine(today, dt.time.max))

    target_obj = DailyTarget.objects.filter(
        company=request.company, user=request.user, sana=today
    ).first()
    maqsad = float(target_obj.maqsad) if target_obj else 0

    savdo_qs = Savdo.objects.filter(
        company=request.company, vaqt_sana__range=(today_start, today_end)
    )
    if request.user.type in ('yetkazib_beruvchi', 'savdogar'):
        from .models import YetkazibBeruvchi
        try:
            agent = YetkazibBeruvchi.objects.get(user=request.user, company=request.company)
            savdo_qs = savdo_qs.filter(yetkazib_beruvchi=agent)
        except YetkazibBeruvchi.DoesNotExist:
            savdo_qs = savdo_qs.none()

    amalda = float(savdo_qs.aggregate(t=Sum('summa'))['t'] or 0)
    foiz   = round((amalda / maqsad * 100) if maqsad > 0 else 0, 1)

    return JsonResponse({
        'maqsad': maqsad,
        'amalda': amalda,
        'foiz':   foiz,
        'sana':   today.strftime('%d.%m.%Y'),
    })


@login_required(login_url='login')
def trend_30(request):
    """Oxirgi 30 kun savdo trendi (JSON) — dashboard uchun"""
    if request.user.type != 'ega':
        return JsonResponse({'error': 'ruxsat yo\'q'}, status=403)

    now   = timezone.localtime()
    days  = int(request.GET.get('days', 30))
    days  = min(max(days, 7), 90)

    labels, summa_data, soni_data = [], [], []
    for i in range(days - 1, -1, -1):
        day   = now.date() - dt.timedelta(days=i)
        start = timezone.make_aware(dt.datetime.combine(day, dt.time.min))
        end   = timezone.make_aware(dt.datetime.combine(day, dt.time.max))
        qs    = Savdo.objects.filter(company=request.company, vaqt_sana__range=(start, end))
        labels.append(day.strftime('%d.%m'))
        summa_data.append(float(qs.aggregate(t=Sum('summa'))['t'] or 0))
        soni_data.append(qs.count())

    return JsonResponse({
        'labels':     labels,
        'summa_data': summa_data,
        'soni_data':  soni_data,
    })
