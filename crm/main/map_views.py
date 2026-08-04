from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, time, timedelta
from math import asin, cos, radians, sin, sqrt
from .models import YetkazibBeruvchi, LocationHistory, Savdo, HaridorDukon, Ombor
from .plan_utils import company_has_access

ROUTE_GAP_LIMIT = timedelta(minutes=4)


def _local_day_bounds(day):
    current_tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), current_tz)
    end = timezone.make_aware(datetime.combine(day, time.max), current_tz)
    return start, end


def _distance_km(points):
    total = 0
    previous = None
    for point in points:
        if previous and point.timestamp - previous.timestamp <= ROUTE_GAP_LIMIT:
            lat1, lng1 = previous.lat, previous.lng
            lat2, lng2 = point.lat, point.lng
            dlat = radians(lat2 - lat1)
            dlng = radians(lng2 - lng1)
            a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
            total += 6371 * 2 * asin(sqrt(a))
        previous = point
    return round(total, 2)


def build_route_segments(history):
    segments = []
    current_segment = []
    previous_point = None

    for point in history:
        if previous_point and point.timestamp - previous_point.timestamp > ROUTE_GAP_LIMIT:
            if len(current_segment) > 1:
                segments.append(current_segment)
            current_segment = []

        current_segment.append([point.lat, point.lng])
        previous_point = point

    if len(current_segment) > 1:
        segments.append(current_segment)

    return segments

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
def route_history_page(request):
    if request.user.type != 'ega':
        return JsonResponse({'error': 'No access'}, status=403)

    if not request.has_map:
        return render(request, 'map_no_access.html')

    if not company_has_access(request.company):
        messages.warning(request, "Marshrut tarixidan foydalanish uchun xarita xizmati faol bo'lishi kerak.")
        return render(request, 'map_no_access.html')

    deliverers = YetkazibBeruvchi.objects.filter(
        company=request.company,
        user__type='yetkazib_beruvchi',
    ).select_related('user').order_by('tuliq_ismi')
    selected_date = request.GET.get('date') or timezone.localdate().isoformat()
    selected_deliverer = request.GET.get('deliverer') or (str(deliverers[0].id) if deliverers else '')

    return render(request, 'route_history.html', {
        'deliverers': deliverers,
        'selected_date': selected_date,
        'selected_deliverer': selected_deliverer,
    })


@login_required(login_url='login')
def api_route_active_days(request, deliverer_id):
    if request.user.type != 'ega' or not company_has_access(request.company) or not request.has_map:
        return JsonResponse({'error': 'No access'}, status=403)

    deliverer = get_object_or_404(
        YetkazibBeruvchi,
        id=deliverer_id,
        company=request.company,
        user__type='yetkazib_beruvchi',
    )
    local_dates = {}
    history = LocationHistory.objects.filter(
        yetkazib_beruvchi=deliverer,
        company=request.company,
    ).order_by('-timestamp')

    for point in history:
        day = timezone.localtime(point.timestamp).date().isoformat()
        local_dates[day] = day

    days = list(local_dates.values())
    return JsonResponse({
        'deliverer': {
            'id': deliverer.id,
            'name': deliverer.tuliq_ismi,
        },
        'days': days,
        'default_date': days[0] if days else None,
    })


def _parse_client_timestamp(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _optional_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


@csrf_exempt
@login_required(login_url='login')
@require_POST
def api_location_batch(request):
    # CSRF'dan ozod: PWA'da sahifa service worker keshidan ochilganda undagi
    # CSRF token eskirgan bo'ladi (login'da token aylanadi) va offline'da
    # yig'ilgan GPS nuqtalar sinxronlanmay 403 olardi. Endpoint sessiya bilan
    # himoyalangan, faqat o'z GPS tarixiga yozadi va dublikatlarni filtrlaydi.
    if request.user.type != 'yetkazib_beruvchi':
        return JsonResponse({'error': 'No access'}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    points = payload.get('points') or []
    if not isinstance(points, list):
        return JsonResponse({'error': 'points must be a list'}, status=400)

    deliverer = get_object_or_404(YetkazibBeruvchi, user=request.user, company=request.company)
    saved = 0
    last_point = None
    incoming_timestamps = [
        _parse_client_timestamp(point.get('client_timestamp'))
        for point in points[:500]
        if isinstance(point, dict) and point.get('client_timestamp')
    ]
    existing_timestamps = set(LocationHistory.objects.filter(
        yetkazib_beruvchi=deliverer,
        client_timestamp__in=[ts for ts in incoming_timestamps if ts],
    ).values_list('client_timestamp', flat=True))
    rows = []

    for point in points[:500]:
        if not isinstance(point, dict):
            continue
        try:
            lat = float(point.get('lat'))
            lng = float(point.get('lng'))
        except (TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue

        client_timestamp = _parse_client_timestamp(point.get('client_timestamp'))
        if client_timestamp and client_timestamp in existing_timestamps:
            continue
        rows.append(LocationHistory(
            yetkazib_beruvchi=deliverer,
            company=request.company,
            lat=lat,
            lng=lng,
            timestamp=client_timestamp or timezone.now(),
            client_timestamp=client_timestamp,
            accuracy=_optional_float(point.get('accuracy')),
            speed=_optional_float(point.get('speed')),
            source=point.get('source') or 'batch',
        ))
        saved += 1
        last_point = (lat, lng)

    if rows:
        LocationHistory.objects.bulk_create(rows)
        deliverer.last_lat = last_point[0]
        deliverer.last_lng = last_point[1]
        deliverer.last_active = timezone.now()
        deliverer.save(update_fields=['last_lat', 'last_lng', 'last_active'])

    return JsonResponse({'saved': saved})

@login_required(login_url='login')
def api_map_data(request):
    if not company_has_access(request.company) or not request.has_map:
        return JsonResponse({'error': 'No access'}, status=403)
    
    # Real-time & Recent Deliverers.
    # Keep old known positions visible as offline markers so the map does not look empty
    # when a courier has not sent a fresh browser GPS heartbeat yet.
    now = timezone.now()
    online_threshold = now - timedelta(minutes=2) # 2 minute threshold for "Real-time"
    
    deliverers = YetkazibBeruvchi.objects.filter(
        company=request.company,
        last_lat__isnull=False,
        last_lng__isnull=False,
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
        
        path_segments = build_route_segments(history)
        
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
            'path': [point for segment in path_segments for point in segment],
            'path_segments': path_segments,
        })
    
    # Recent Sales with locations (TODAY ONLY)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    sales = Savdo.objects.filter(
        company=request.company,
        vaqt_sana__gte=today_start,
        latitude__isnull=False,
        longitude__isnull=False
    ).select_related('haridor_dukon', 'yetkazib_beruvchi', 'savdogar')
    
    sales_data = []
    for s in sales:
        sales_data.append({
            'shop_name': s.haridor_dukon.nomi if s.haridor_dukon else s.oluvchining_ismi,
            'summa': float(s.summa),
            'lat': s.latitude,
            'lng': s.longitude,
            'deliverer_name': s.yetkazib_beruvchi.tuliq_ismi if s.yetkazib_beruvchi else (s.savdogar.tuliq_ismi if s.savdogar else "-"),
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

    # Omborlar (lokatsiyasi kiritilganlar) — statik belgilar sifatida
    omborlar = Ombor.objects.filter(
        company=request.company,
        latitude__isnull=False,
        longitude__isnull=False,
    )
    omborlar_data = [
        {
            'id': o.id,
            'name': o.nomi,
            'manzil': o.manzil,
            'lat': o.latitude,
            'lng': o.longitude,
        }
        for o in omborlar
    ]

    return JsonResponse({
        'deliverers': deliverers_data,
        'sales': sales_data,
        'shops': shops_data,
        'omborlar': omborlar_data,
    })

@login_required(login_url='login')
def api_route_history(request, deliverer_id):
    if not company_has_access(request.company) or not request.has_map:
        return JsonResponse({'error': 'No access'}, status=403)

    deliverer = get_object_or_404(
        YetkazibBeruvchi,
        id=deliverer_id,
        company=request.company,
        user__type='yetkazib_beruvchi',
    )
    if request.user.type != 'ega' and deliverer.user_id != request.user.id:
        return JsonResponse({'error': 'No access'}, status=403)

    selected_day = parse_date(request.GET.get('date') or '')
    if selected_day:
        since, until = _local_day_bounds(selected_day)
    else:
        since = timezone.now() - timedelta(hours=24)
        until = timezone.now()

    history = LocationHistory.objects.filter(
        yetkazib_beruvchi=deliverer,
        company=request.company,
        timestamp__gte=since,
        timestamp__lte=until,
    ).order_by('timestamp')

    path_segments = []
    current_segment = []
    previous_point = None
    points = list(history)
    for point in points:
        if previous_point and point.timestamp - previous_point.timestamp > ROUTE_GAP_LIMIT:
            if len(current_segment) > 1:
                path_segments.append(current_segment)
            current_segment = []
        local_time = timezone.localtime(point.timestamp)
        current_segment.append([point.lat, point.lng, local_time.strftime('%H:%M')])
        previous_point = point

    if len(current_segment) > 1:
        path_segments.append(current_segment)

    return JsonResponse({
        'deliverer': {
            'id': deliverer.id,
            'name': deliverer.tuliq_ismi,
        },
        'date': selected_day.isoformat() if selected_day else None,
        'path': [point for segment in path_segments for point in segment],
        'path_segments': path_segments,
        'gap_limit_minutes': 4,
        'point_count': len(points),
        'distance_km': _distance_km(points),
        'start_time': timezone.localtime(points[0].timestamp).strftime('%H:%M') if points else None,
        'end_time': timezone.localtime(points[-1].timestamp).strftime('%H:%M') if points else None,
    })
