"""
Shop Recommendation Engine

Analyzes shop-level sales patterns and provides recommendations
for product distribution optimization.
"""

from typing import List, Dict

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None
    np = None

from .demand import build_product_timeseries


def recommend_shops_for_product(product_name: str) -> List[Dict]:
    """
    Analyze shop-level demand and provide distribution recommendations.
    
    Args:
        product_name: Product to analyze
        
    Returns:
        List of dicts sorted by avg_qty (descending):
            - shop: Shop name
            - total_sales: Number of sales
            - total_qty: Total quantity sold
            - avg_qty_per_sale: Average quantity per transaction
            - recommendation: Distribution recommendation text
            
    Raises:
        ImportError: If pandas is not installed
        ValueError: If no data available for product
    """
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas is required. Install: pip install pandas numpy")
    
    # Get timeseries data
    df = build_product_timeseries()
    
    if df.empty:
        raise ValueError("No sales data available")
    
    # Filter for this product
    product_df = df[df['product'] == product_name].copy()
    
    if product_df.empty:
        raise ValueError(f"No sales data for product: {product_name}")
    
    # Group by shop and calculate metrics
    shop_stats = product_df.groupby('shop').agg({
        'qty': ['sum', 'count', 'mean']
    }).reset_index()
    
    # Flatten column names
    shop_stats.columns = ['shop', 'total_qty', 'total_sales', 'avg_qty_per_sale']
    
    # Sort by average quantity (descending)
    shop_stats = shop_stats.sort_values('avg_qty_per_sale', ascending=False)
    
    # Calculate percentiles for recommendations
    if len(shop_stats) > 1:
        percentile_75 = shop_stats['avg_qty_per_sale'].quantile(0.75)
        percentile_25 = shop_stats['avg_qty_per_sale'].quantile(0.25)
    else:
        percentile_75 = shop_stats['avg_qty_per_sale'].iloc[0]
        percentile_25 = shop_stats['avg_qty_per_sale'].iloc[0]
    
    # Generate recommendations
    results = []
    for _, row in shop_stats.iterrows():
        avg_qty = row['avg_qty_per_sale']
        
        if avg_qty >= percentile_75 and len(shop_stats) > 1:
            recommendation = "Ko'proq mahsulot yuborish tavsiya etiladi"
            priority = "high"
        elif avg_qty <= percentile_25 and len(shop_stats) > 1:
            recommendation = "Kamroq mahsulot yuborish tavsiya etiladi"
            priority = "low"
        else:
            recommendation = "Joriy miqdorni davom ettirish"
            priority = "normal"
        
        results.append({
            'shop': row['shop'],
            'total_sales': int(row['total_sales']),
            'total_qty': round(row['total_qty'], 2),
            'avg_qty_per_sale': round(avg_qty, 2),
            'recommendation': recommendation,
            'priority': priority
        })
    
    return results


def get_top_shops(product_name: str, limit: int = 10) -> List[Dict]:
    """
    Get top shops by sales volume for a product.
    
    Args:
        product_name: Product to analyze
        limit: Maximum number of shops to return
        
    Returns:
        List of top shops sorted by total quantity
    """
    recommendations = recommend_shops_for_product(product_name)
    
    # Sort by total quantity
    sorted_shops = sorted(recommendations, key=lambda x: x['total_qty'], reverse=True)
    
    return sorted_shops[:limit]
