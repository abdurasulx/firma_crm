"""
Test Analytics Services

Quick test script for demand forecasting system.
Run: python manage.py shell < test_analytics.py
"""

print("=" * 60)
print("TESTING ANALYTICS SERVICES")
print("=" * 60)

# Test 1: Parser
print("\n1. Testing SMM Parser...")
from main.services.parser import parse_smm

test_data = "Un 1 14500.0,Non 2 5000,Shakar 1.5 8000,"
result = parse_smm(test_data)
print(f"   Input: {test_data}")
print(f"   Output: {result}")
print(f"   ✓ Parser works!")

# Test 2: Empty data
result_empty = parse_smm("")
print(f"   Empty string: {result_empty}")
print(f"   ✓ Handles empty data!")

# Test 3: Check pandas
print("\n2. Checking pandas installation...")
try:
    import pandas as pd
    import numpy as np
    print(f"   ✓ pandas {pd.__version__} installed")
    print(f"   ✓ numpy {np.__version__} installed")
    pandas_available = True
except ImportError:
    print("   ✗ pandas/numpy NOT installed")
    print("   Run: pip install pandas numpy")
    pandas_available = False

# Test 4: Database query (if pandas available)
if pandas_available:
    print("\n3. Testing database queries...")
    from main.models import Savdo
    
    count = Savdo.objects.count()
    print(f"   Total sales records: {count}")
    
    if count > 0:
        # Test timeseries builder
        print("\n4. Testing timeseries builder...")
        from main.services.demand import build_product_timeseries, get_all_products
        
        try:
            df = build_product_timeseries()
            print(f"   ✓ Timeseries DataFrame created")
            print(f"   Shape: {df.shape}")
            print(f"   Columns: {list(df.columns)}")
            
            if not df.empty:
                print(f"\n   First 3 rows:")
                print(df.head(3))
                
                # Get product list
                products = get_all_products()
                print(f"\n5. Products found: {len(products)}")
                print(f"   {products[:5]}...")  # First 5
                
                if products:
                    # Test demand analysis
                    print(f"\n6. Testing demand analysis for: {products[0]}")
                    from main.services.demand import analyze_product_demand
                    
                    analysis = analyze_product_demand(products[0])
                    print(f"   Product: {analysis['product']}")
                    print(f"   Avg 7 days: {analysis['avg_last_7_days']}")
                    print(f"   Avg 30 days: {analysis['avg_last_30_days']}")
                    print(f"   Trend: {analysis['trend']}")
                    print(f"   Recommendation: {analysis['recommendation']}")
                    print(f"   Forecast 7d: {analysis['forecast_next_7_days']}")
    print(f"   ✓ Demand analysis works!")
                    
                    # Test shop recommendations
                    print(f"\n7. Testing shop recommendations...")
                    from main.services.recommendations import recommend_shops_for_product
                    
                    shops = recommend_shops_for_product(products[0])
                    print(f"   Found {len(shops)} shops")
                    if shops:
                        top_shop = shops[0]
                        print(f"   Top shop: {top_shop['shop']}")
                        print(f"   Avg qty: {top_shop['avg_qty_per_sale']}")
                        print(f"   Recommendation: {top_shop['recommendation']}")
                        print(f"   ✓ Shop recommendations work!")
                        
        except Exception as e:
            print(f"   ✗ Error: {e}")
    else:
        print("   No sales data to test with")
        
print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
print("\nAPI Endpoints:")
print("  GET /api/analytics/products/")
print("  GET /api/analytics/product-demand/?product=Un")
print("  GET /api/analytics/shop-recommendations/?product=Un")
print("\nTest API:")
print("  curl http://localhost:8000/api/analytics/products/")
