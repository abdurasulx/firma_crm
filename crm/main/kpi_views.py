"""
KPI — Kunlik maqsad, trend grafigi va rag'batlantirish (bonus)
qoidalari uchun viewlar
"""
import datetime as dt
import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.db.models import Sum
from django.views.decorators.http import require_POST

from .models import DailyTarget, KpiQoida, Mahsulot, Savdo, User


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

    labels, summa_data, soni_data, foyda_data = [], [], [], []
    for i in range(days - 1, -1, -1):
        day   = now.date() - dt.timedelta(days=i)
        start = timezone.make_aware(dt.datetime.combine(day, dt.time.min))
        end   = timezone.make_aware(dt.datetime.combine(day, dt.time.max))
        qs    = Savdo.objects.filter(company=request.company, vaqt_sana__range=(start, end))
        labels.append(day.strftime('%d.%m'))
        summa_data.append(float(qs.aggregate(t=Sum('summa'))['t'] or 0))
        soni_data.append(qs.count())
        foyda_data.append(float(qs.aggregate(t=Sum('foyda'))['t'] or 0))

    return JsonResponse({
        'labels':     labels,
        'summa_data': summa_data,
        'soni_data':  soni_data,
        'foyda_data': foyda_data,
    })


@login_required(login_url='login')
def kpi_qoidalari_view(request):
    """Ega firma sozlamalarida KPI (rag'batlantirish/bonus) qoidalarini
    boshqaradi — xodim TURI bo'yicha (individual emas), bir turga
    bir nechta bosqich (qoida) qo'shish mumkin."""
    if request.user.type != 'ega':
        return redirect('main')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            try:
                xodim_turi = request.POST.get('xodim_turi')
                if xodim_turi not in dict(KpiQoida.XODIM_TURI_CHOICES):
                    raise ValueError("Noto'g'ri xodim turi")
                olchov_turi = request.POST.get('olchov_turi')
                bonus_turi = request.POST.get('bonus_turi')
                mahsulot_id = request.POST.get('mahsulot_id') or None
                mahsulot = None
                if mahsulot_id:
                    mahsulot = Mahsulot.objects.filter(id=mahsulot_id, company=request.company).first()
                chegara = Decimal(request.POST.get('chegara') or '0')
                bonus_qiymati = Decimal(request.POST.get('bonus_qiymati') or '0')
                if chegara <= 0 or bonus_qiymati <= 0:
                    raise ValueError("Chegara va bonus 0 dan katta bo'lishi kerak")
                KpiQoida.objects.create(
                    company=request.company, xodim_turi=xodim_turi, mahsulot=mahsulot,
                    olchov_turi=olchov_turi, chegara=chegara,
                    bonus_turi=bonus_turi, bonus_qiymati=bonus_qiymati,
                )
                messages.success(request, "KPI qoidasi qo'shildi.")
            except (InvalidOperation, ValueError):
                messages.error(request, "Ma'lumotlar noto'g'ri kiritildi.")
            return redirect('kpi_qoidalari')

        if action == 'delete':
            KpiQoida.objects.filter(id=request.POST.get('qoida_id'), company=request.company).delete()
            messages.success(request, "KPI qoidasi o'chirildi.")
            return redirect('kpi_qoidalari')

        if action == 'toggle':
            qoida = KpiQoida.objects.filter(id=request.POST.get('qoida_id'), company=request.company).first()
            if qoida:
                qoida.faol = not qoida.faol
                qoida.save(update_fields=['faol'])
            return redirect('kpi_qoidalari')

    qoidalar = KpiQoida.objects.filter(company=request.company).select_related('mahsulot')
    context = {
        'qoidalar': qoidalar,
        'xodim_turi_choices': KpiQoida.XODIM_TURI_CHOICES,
        'olchov_turi_choices': KpiQoida.OLCHOV_TURI_CHOICES,
        'bonus_turi_choices': KpiQoida.BONUS_TURI_CHOICES,
        'mahsulotlar': Mahsulot.objects.filter(company=request.company, warehouse_type='finished').order_by('nomi'),
    }
    return render(request, 'kpi_qoidalari.html', context)
