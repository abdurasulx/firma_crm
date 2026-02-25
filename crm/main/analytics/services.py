from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from ..models import Savdo, Mahsulot, User

def get_dashboard_stats():
    """Generates high-level stats for the dashboard using Savdo.summa."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Low stock: mahsulotlar that are below their individual min_miqdori threshold
    all_products = Mahsulot.objects.all()
    low_stock_list = [m for m in all_products if m.past_zaxira]

    stats = {
        'total_sales_today': Savdo.objects.filter(vaqt_sana__gte=today_start).aggregate(total=Sum('summa'))['total'] or 0,
        'total_sales_month': Savdo.objects.filter(vaqt_sana__gte=month_start).aggregate(total=Sum('summa'))['total'] or 0,
        'low_stock_products': len(low_stock_list),
        'low_stock_list': low_stock_list,
        'top_products_by_summa': [],
        'active_delivery_users': User.objects.filter(type='yetkazib_beruvchi', is_active=True).count()
    }
    return stats

def get_sales_timeseries(days=30):
    """Returns daily sales totals for the last N days."""
    now = timezone.now()
    data = []
    for i in range(days):
        date = (now - timedelta(days=i)).date()
        total = Savdo.objects.filter(
            vaqt_sana__year=date.year, 
            vaqt_sana__month=date.month, 
            vaqt_sana__day=date.day
        ).aggregate(total=Sum('summa'))['total'] or 0
        data.append({'date': date.isoformat(), 'total': total})
    return data[::-1]
