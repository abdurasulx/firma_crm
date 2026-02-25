import csv
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from .models import AmalLog, Savdo, YetkazibBeruvchi, HaridorDukon
from django.utils import timezone
import datetime as dt

User = get_user_model()


# ─── AmalLog Ko'rinishi ────────────────────────────────────────────────────────
@login_required(login_url='login')
def amallog_view(request):
    """Admin uchun barcha amallar jurnali."""
    if request.user.type != 'ega':
        return redirect('main')

    # Filters
    user_filter = request.GET.get('user', '')
    from_str = request.GET.get('from', '')
    to_str = request.GET.get('to', '')

    logs = AmalLog.objects.select_related('user').order_by('-sana_vaqti')

    if user_filter:
        logs = logs.filter(user__username=user_filter)

    try:
        if from_str:
            from_dt = timezone.make_aware(dt.datetime.combine(dt.date.fromisoformat(from_str), dt.time.min))
            logs = logs.filter(sana_vaqti__gte=from_dt)
        if to_str:
            to_dt = timezone.make_aware(dt.datetime.combine(dt.date.fromisoformat(to_str), dt.time.max))
            logs = logs.filter(sana_vaqti__lte=to_dt)
    except ValueError:
        pass

    # CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="amallog.csv"'
        response.write('\ufeff')  # BOM for Excel
        writer = csv.writer(response)
        writer.writerow(['Sana', 'Foydalanuvchi', 'Amal'])
        for log in logs:
            writer.writerow([
                log.sana_vaqti.strftime('%d.%m.%Y %H:%M'),
                log.user.tuliq_ismi or log.user.username,
                log.amal_shifri,
            ])
        return response

    # Users list for filter dropdown
    all_users = User.objects.filter(is_active=True).order_by('username')

    context = {
        'logs': logs[:500],           # cap at 500 to avoid slow page
        'jami': logs.count(),
        'all_users': all_users,
        'user_filter': user_filter,
        'from_date': from_str,
        'to_date': to_str,
    }
    return render(request, 'amallog.html', context)


# ─── Savdo Cheki ──────────────────────────────────────────────────────────────
@login_required(login_url='login')
def savdo_chek(request, savdo_id):
    """Savdo uchun chop etiladigan chek sahifasi."""
    savdo = get_object_or_404(Savdo, id=savdo_id)

    # Only ega and the delivery person who made the sale can view
    if request.user.type not in ('ega',):
        try:
            yb = YetkazibBeruvchi.objects.get(user=request.user)
            if savdo.yetkazib_beruvchi != yb:
                return redirect('main')
        except YetkazibBeruvchi.DoesNotExist:
            return redirect('main')

    context = {'savdo': savdo}
    return render(request, 'savdo_chek.html', context)
