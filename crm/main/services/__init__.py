"""
Analytics Services Module
Demand forecasting and recommendation engine
"""

from .parser import parse_smm
from .demand import build_product_timeseries, analyze_product_demand, get_all_products
from .recommendations import recommend_shops_for_product

__all__ = [
    'parse_smm',
    'build_product_timeseries',
    'analyze_product_demand',
    'get_all_products',
    'recommend_shops_for_product',
]
