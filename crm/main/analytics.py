"""
Analytics API Views

REST endpoints for demand forecasting and recommendations.
No external APIs - 100% local processing.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import datetime

from main.services import (
    analyze_product_demand,
    recommend_shops_for_product,
    get_all_products
)
from main.models import Savdo, Mahsulot


@require_http_methods(["GET"])
def product_demand_api(request):
    """
    Get demand analysis and forecast for a product.
    
    Query Parameters:
        product (required): Product name to analyze
        
    Returns:
        JSON with demand metrics, trend, forecast, and shop recommendations
        
    Example:
        GET /api/analytics/product-demand/?product=Un
        
    Response:
        {
            "product": "Un",
            "avg_last_7_days": 45.2,
            "avg_last_30_days": 72.8,
            "avg_last_90_days": 68.5,
            "trend": "decreasing",
            "trend_ratio": 0.62,
            "recommendation": "Ishlab chiqarishni kamaytirish tavsiya etiladi",
            "forecast_next_7_days": 316.4,
            "forecast_next_30_days": 2184.0,
            "total_sales_count": 145,
            "shop_recommendations": [
                {
                    "shop": "Magazin A",
                    "total_sales": 45,
                    "total_qty": 520.5,
                    "avg_qty_per_sale": 11.6,
                    "recommendation": "Ko'proq mahsulot yuborish tavsiya etiladi",
                    "priority": "high"
                }
            ]
        }
    """
    product_name = request.GET.get('product')
    
    if not product_name:
        return JsonResponse({
            'error': 'product parameter is required',
            'example': '/api/analytics/product-demand/?product=Un'
        }, status=400)
    
    try:
        # Get demand analysis
        demand_data = analyze_product_demand(product_name)
        
        # Get shop recommendations
        shop_recs = recommend_shops_for_product(product_name)
        
        # Combine results
        response_data = {
            **demand_data,
            'shop_recommendations': shop_recs
        }
        
        return JsonResponse(response_data)
        
    except ImportError as e:
        return JsonResponse({
            'error': 'pandas/numpy not installed',
            'message': str(e),
            'install_command': 'pip install pandas numpy'
        }, status=500)
        
    except ValueError as e:
        return JsonResponse({
            'error': 'no_data',
            'message': str(e)
        }, status=404)
        
    except Exception as e:
        return JsonResponse({
            'error': 'internal_error',
            'message': str(e)
        }, status=500)


@require_http_methods(["GET"])
def products_list_api(request):
    """
    Get list of all products with sales data.
    
    Returns:
        JSON array of product names
        
    Example:
        GET /api/analytics/products/
        
    Response:
        {
            "products": ["Un", "Non", "Shakar"],
            "count": 3
        }
    """
    try:
        products = get_all_products()
        
        return JsonResponse({
            'products': products,
            'count': len(products)
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def shop_recommendations_api(request):
    """
    Get shop recommendations for a specific product.
    
    Query Parameters:
        product (required): Product name
        limit (optional): Max number of shops to return (default: all)
        
    Example:
        GET /api/analytics/shop-recommendations/?product=Un&limit=5
        
    Response:
        {
            "product": "Un",
            "recommendations": [...]
        }
    """
    product_name = request.GET.get('product')
    limit = request.GET.get('limit')
    
    if not product_name:
        return JsonResponse({
            'error': 'product parameter is required'
        }, status=400)
    
    try:
        recommendations = recommend_shops_for_product(product_name)
        
        # Apply limit if specified
        if limit:
            try:
                limit = int(limit)
                recommendations = recommendations[:limit]
            except ValueError:
                pass
        
        return JsonResponse({
            'product': product_name,
            'recommendations': recommendations,
            'count': len(recommendations)
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def top_products_api(request):
    """
    Top mahsulotlar — Savdo.summa ga asoslangan reyting.
    Query params:
        days (optional): 7, 30, 90 (default: 30)
        limit (optional): nechtasini qaytarish (default: 8)
    """
    try:
        days  = int(request.GET.get('days',  30))
        limit = int(request.GET.get('limit', 8))

        from_dt = timezone.now() - datetime.timedelta(days=days)
        savdolar = Savdo.objects.filter(vaqt_sana__gte=from_dt).select_related('haridor_dukon')

        # Group by haridor_dukon (shop) by summa
        from collections import defaultdict
        shop_totals = defaultdict(float)
        shop_counts = defaultdict(int)

        for s in savdolar:
            nm = s.haridor_dukon.nomi if s.haridor_dukon else "Noma'lum"
            shop_totals[nm] += (s.summa or 0)
            shop_counts[nm] += 1

        # Sort descending
        sorted_shops = sorted(shop_totals.items(), key=lambda x: x[1], reverse=True)

        result = []
        for i, (nm, total) in enumerate(sorted_shops[:limit]):
            result.append({
                'name':   nm,
                'summa':  round(total, 0),
                'count':  shop_counts[nm],
                'rank':   i + 1,
            })

        return JsonResponse({
            'days':   days,
            'total':  len(sorted_shops),
            'items':  result,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
