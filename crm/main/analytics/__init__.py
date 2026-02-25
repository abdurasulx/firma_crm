from .services import get_dashboard_stats, get_sales_timeseries
from .views import product_demand_api, products_list_api, shop_recommendations_api
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import datetime


@require_http_methods(["GET"])
def top_products_api(request):
    """Top do'konlar — Savdo.summa bo'yicha reyting. Params: days, limit."""
    try:
        from main.models import Savdo
        from collections import defaultdict

        days  = int(request.GET.get('days',  30))
        limit = int(request.GET.get('limit', 8))

        from_dt  = timezone.now() - datetime.timedelta(days=days)
        savdolar = Savdo.objects.filter(vaqt_sana__gte=from_dt).select_related('haridor_dukon')

        shop_totals = defaultdict(float)
        shop_counts = defaultdict(int)
        for s in savdolar:
            nm = s.haridor_dukon.nomi if s.haridor_dukon else "Noma'lum"
            shop_totals[nm] += (s.summa or 0)
            shop_counts[nm] += 1

        sorted_shops = sorted(shop_totals.items(), key=lambda x: x[1], reverse=True)
        result = [
            {'name': nm, 'summa': round(total, 0), 'count': shop_counts[nm], 'rank': i + 1}
            for i, (nm, total) in enumerate(sorted_shops[:limit])
        ]
        return JsonResponse({'days': days, 'total': len(sorted_shops), 'items': result})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
