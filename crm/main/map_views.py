from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from .models import YetkazibBeruvchi, LocationHistory, Savdo, HaridorDukon
from django.db.models import Sum
from .plan_utils import company_has_access

@login_required(login_url='login')
def map_dashboard(request):
    # Tarifda xarita bormi?
    if not request.has_map:
        return render(request, 'map_no_access.html')
    
    # To'lov qilinganmi? (yoki trial)
    if not company_has_access(request.company):
        messages.warning(request, "Xarita xizmatidan foydalanish uchun to'lov amalga oshirilgan bo'lishi kerak.")
        return render(request, 'map_no_access.html')
    
    return render(request, 'map_dashboard.html')

@login_required(login_url='login')
def api_map_data(request):
    if not company_has_access(request.company) or not request.has_map:
        return JsonResponse({'error': 'No access'}, status=403)
    
    # Real-time & Recent Deliverers (active in last 7 days)
    now = timezone.now()
    active_threshold = now - timedelta(days=7)
    online_threshold = now - timedelta(minutes=2) # 2 minute threshold for "Real-time"
    
    deliverers = YetkazibBeruvchi.objects.filter(
        company=request.company,
        last_lat__isnull=False,
        last_lng__isnull=False,
        last_active__gte=active_threshold
    ).order_by('-last_active')
    
    deliverers_data = []
    colors = ['#f43f5e', '#8b5cf6', '#0ea5e9', '#10b981', '#f59e0b', '#6366f1', '#ec4899', '#14b8a6']
    
    for d in deliverers:
        is_online = d.last_active >= online_threshold
        
        # Local timezone for display
        local_active = timezone.localtime(d.last_active)
        
        # Determine path "since" time
        if is_online:
            # For online: show today's path in local time
            local_now = timezone.localtime(now)
            today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
            since = min(today_start, now - timedelta(hours=8))
        else:
            # For offline: show path from their last active 12 hours
            since = d.last_active - timedelta(hours=12)
            
        history = LocationHistory.objects.filter(
            yetkazib_beruvchi=d,
            timestamp__gte=since,
            timestamp__lte=d.last_active
        ).order_by('timestamp')
        
        path = [[h.lat, h.lng] for h in history]
        
        # Minutes ago for friendly display
        diff = now - d.last_active
        minutes_ago = int(diff.total_seconds() / 60)
        if minutes_ago < 1:
            last_seen_text = "Hozirgina"
        elif minutes_ago < 60:
            last_seen_text = f"{minutes_ago} daqiqa oldin"
        else:
            last_seen_text = local_active.strftime('%d.%m %H:%M')
            
        deliverers_data.append({
            'id': d.id,
            'name': d.tuliq_ismi,
            'lat': d.last_lat,
            'lng': d.last_lng,
            'last_active': last_seen_text,
            'is_online': is_online,
            'image': d.rasmi.url if d.rasmi else None,
            'color': colors[d.id % len(colors)],
            'path': path
        })
    
    # Recent Sales with locations (TODAY ONLY)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    sales = Savdo.objects.filter(
        company=request.company,
        vaqt_sana__gte=today_start,
        latitude__isnull=False,
        longitude__isnull=False
    ).select_related('haridor_dukon', 'yetkazib_beruvchi')
    
    sales_data = []
    for s in sales:
        if not s.yetkazib_beruvchi:
            continue
        sales_data.append({
            'shop_name': s.haridor_dukon.nomi,
            'summa': float(s.summa),
            'lat': s.latitude,
            'lng': s.longitude,
            'deliverer_name': s.yetkazib_beruvchi.tuliq_ismi,
            'time': s.vaqt_sana.strftime('%H:%M')
        })
        
    # All Shops for static list
    shops = HaridorDukon.objects.filter(
        company=request.company,
        latitude__isnull=False,
        longitude__isnull=False
    )
    shops_data = []
    for s in shops:
        shops_data.append({
            'name': s.nomi,
            'lat': s.latitude,
            'lng': s.longitude,
            'pic': s.dukon_rasmi.url if s.dukon_rasmi else None
        })

    return JsonResponse({
        'deliverers': deliverers_data,
        'sales': sales_data,
        'shops': shops_data
    })

@login_required(login_url='login')
def api_route_history(request, deliverer_id):
    if not company_has_access(request.company) or not request.has_map:
        return JsonResponse({'error': 'No access'}, status=403)
    
    # Default: last 24 hours
    since = timezone.now() - timedelta(hours=24)
    
    history = LocationHistory.objects.filter(
        yetkazib_beruvchi_id=deliverer_id,
        company=request.company,
        timestamp__gte=since
    ).order_by('timestamp')
    
    path = [[h.lat, h.lng, h.timestamp.strftime('%H:%M')] for h in history]
    
    return JsonResponse({'path': path})
