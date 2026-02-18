"""
Demand Analysis & Forecasting Engine

Analyzes sales trends and provides demand forecasts without external APIs.
Uses only pandas, numpy, and Django ORM.
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
from django.db.models import Q
from django.utils import timezone

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None
    np = None

from main.models import Savdo, HaridorDukon
from .parser import parse_smm


def build_product_timeseries() -> 'pd.DataFrame':
    """
    Build a timeseries DataFrame of all product sales.
    
    Returns:
        DataFrame with columns: [date, product, qty, shop, price]
        
    Raises:
        ImportError: If pandas is not installed
    """
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas is required for demand analysis. Install: pip install pandas numpy")
    
    # Query all sales with related shop data (avoid N+1)
    sales = Savdo.objects.select_related('haridor_dukon').values(
        'vaqt_sana', 'smm', 'haridor_dukon__nomi'
    ).order_by('vaqt_sana')
    
    # Parse all sales data
    rows = []
    for sale in sales:
        products = parse_smm(sale['smm'])
        
        for product in products:
            rows.append({
                'date': sale['vaqt_sana'].date() if hasattr(sale['vaqt_sana'], 'date') else sale['vaqt_sana'],
                'product': product['name'],
                'qty': product['qty'],
                'price': product['price'],
                'shop': sale['haridor_dukon__nomi']
            })
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
    
    return df


def analyze_product_demand(product_name: str) -> Dict:
    """
    Analyze demand for a specific product and generate forecast.
    
    Args:
        product_name: Name of the product to analyze
        
    Returns:
        Dict containing:
            - product: Product name
            - avg_last_7_days: Average daily quantity (last 7 days)
            - avg_last_30_days: Average daily quantity (last 30 days)
            - avg_last_90_days: Average daily quantity (last 90 days)
            - trend: "increasing", "decreasing", or "stable"
            - trend_ratio: Ratio of 7d avg to 30d avg
            - recommendation: Production recommendation text
            - forecast_next_7_days: Predicted total for next 7 days
            - forecast_next_30_days: Predicted total for next 30 days
            - total_sales_count: Total number of sales
            
    Raises:
        ImportError: If pandas is not installed
        ValueError: If product has no sales data
    """
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas is required. Install: pip install pandas numpy")
    
    # Build timeseries
    df = build_product_timeseries()
    
    if df.empty:
        raise ValueError("No sales data available")
    
    # Filter for this product
    product_df = df[df['product'] == product_name].copy()
    
    if product_df.empty:
        raise ValueError(f"No sales data found for product: {product_name}")
    
    # Group by date and sum quantities
    daily_sales = product_df.groupby('date')['qty'].sum().reset_index()
    daily_sales = daily_sales.sort_values('date')
    
    # Calculate date ranges
    today = timezone.now().date()
    date_7d = today - timedelta(days=7)
    date_30d = today - timedelta(days=30)
    date_90d = today - timedelta(days=90)
    
    # Filter by date ranges
    last_7d = daily_sales[daily_sales['date'] >= pd.Timestamp(date_7d)]
    last_30d = daily_sales[daily_sales['date'] >= pd.Timestamp(date_30d)]
    last_90d = daily_sales[daily_sales['date'] >= pd.Timestamp(date_90d)]
    
    # Calculate averages (per day)
    avg_7d = last_7d['qty'].mean() if not last_7d.empty else 0
    avg_30d = last_30d['qty'].mean() if not last_30d.empty else 0
    avg_90d = last_90d['qty'].mean() if not last_90d.empty else 0
    
    # Handle edge cases
    if avg_30d == 0:
        avg_30d = 0.01  # Prevent division by zero
    
    # Calculate trend ratio
    trend_ratio = avg_7d / avg_30d
    
    # Determine trend and recommendation
    if trend_ratio < 0.8:
        trend = "decreasing"
        recommendation = "Ishlab chiqarishni kamaytirish tavsiya etiladi"
    elif trend_ratio > 1.2:
        trend = "increasing"
        recommendation = "Ishlab chiqarishni oshirish tavsiya etiladi"
    else:
        trend = "stable"
        recommendation = "Joriy ishlab chiqarishni davom ettirish"
    
    # Forecast
    forecast_7d = avg_7d * 7
    forecast_30d = avg_30d * 30
    
    return {
        'product': product_name,
        'avg_last_7_days': round(avg_7d, 2),
        'avg_last_30_days': round(avg_30d, 2),
        'avg_last_90_days': round(avg_90d, 2),
        'trend': trend,
        'trend_ratio': round(trend_ratio, 2),
        'recommendation': recommendation,
        'forecast_next_7_days': round(forecast_7d, 2),
        'forecast_next_30_days': round(forecast_30d, 2),
        'total_sales_count': len(product_df)
    }


def get_all_products() -> List[str]:
    """
    Get list of all unique products from sales data.
    
    Returns:
        List of product names
    """
    if not PANDAS_AVAILABLE:
        return []
    
    df = build_product_timeseries()
    
    if df.empty:
        return []
    
    return sorted(df['product'].unique().tolist())
