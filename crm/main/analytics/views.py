"""
Analytics API Views

REST endpoints for demand forecasting and recommendations.
No external APIs - 100% local processing.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from ..services import (
    analyze_product_demand,
    recommend_shops_for_product,
    get_all_products
)


@require_http_methods(["GET"])
def product_demand_api(request):
    """
    Get demand analysis and forecast for a product.
    
    Query Parameters:
        product (required): Product name to analyze
        
    Returns:
        JSON with demand metrics, trend, forecast, and shop recommendations
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
