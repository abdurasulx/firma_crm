"""
Analytics Services Module
Demand forecasting and recommendation engine
"""

from .auth_service import create_user_service, update_user_service
from .billing_service import (
    apply_plan_request,
    consume_billing_payment_link,
    create_billing_payment_link,
    get_billing_dashboard_data,
    get_billing_reason,
    get_company_dashboard_url,
    get_company_login_url,
    get_company_monthly_price,
    get_latest_payment_link,
    mark_company_paid,
    mark_company_unpaid,
    reject_plan_request,
    sync_company_lifecycle,
)
from .parser import parse_smm
from .demand import build_product_timeseries, analyze_product_demand, get_all_products
from .recommendations import recommend_shops_for_product

__all__ = [
    'create_user_service',
    'update_user_service',
    'apply_plan_request',
    'consume_billing_payment_link',
    'create_billing_payment_link',
    'get_billing_dashboard_data',
    'get_billing_reason',
    'get_company_dashboard_url',
    'get_company_login_url',
    'get_company_monthly_price',
    'get_latest_payment_link',
    'mark_company_paid',
    'mark_company_unpaid',
    'reject_plan_request',
    'sync_company_lifecycle',
    'parse_smm',
    'build_product_timeseries',
    'analyze_product_demand',
    'get_all_products',
    'recommend_shops_for_product',
]
