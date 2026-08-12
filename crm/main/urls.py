from django.conf import settings
from django.views.static import serve
from .views import (
    login, main, end_setup, add_haridor, profile_view, crtuser, editusr,
    sotish, seemahsulot, createmahsulot, deleteprdct, addmiqdor,
    add_yuklama, logout_view, check_new_deliveries, check_sale_serial, pz_sorov_tarixi,
    yetkazuvchi_hisobot, pazanda_hisobot,
    select_plan, select_custom_plan, select_plan_page, yt_navigation,
    billing_page, create_billing_link, open_billing_link,
    request_trial, save_savdogar_contract,
    savdogar_admin_dashboard, savdogar_contract_page, savdogar_contract_download, savdogar_sales_page,
    savdogar_admin_credit_page, savdogar_admin_products_page, savdogar_admin_analytics_page,
    savdogar_my_sales, savdogar_my_credit, savdogar_my_products, savdogar_analytics_page,
    offline_page, service_worker_js, download_desktop_agent, agent_stations_status_api,
)
from landing.views import product_scan_view, product_scan_status_api
from .hisobot_views import hisobotlar_view
from .list_views import hodimlar_list, mahsulotlar_list
from .nasiya_views import nasiya_savdolar_view, add_nasiya_payment
from .mijoz_views import mijozlar_list, mijoz_detail, set_mijoz_turi
from .log_views import amallog_view, savdo_chek
from .qaytarish_views import qaytarish_view, qaytarishlar_view, qaytarish_tasdiq, qaytarish_rad, qaytarish_sozlash
from . import analytics
from .analytics_views import analytics_dashboard
from .map_views import map_dashboard, route_history_page, api_map_data, api_route_history, api_route_active_days, api_location_batch
from .api import dashboard_stats_api
from .backup_views import download_backup, restore_view, prepare_backup_page
from .export_views import export_savdolar, export_nasiya, export_mahsulotlar, export_xodimlar
from .kpi_views import set_daily_target, kpi_today, trend_30, kpi_qoidalari_view
from .click_views import click_prepare, click_complete, click_pay_redirect
from .warehouse_views import (
    warehouse_history,
    warehouse_movements,
    warehouse_product_create,
    warehouse_product_edit,
    warehouse_products,
    warehouse_request_review,
    warehouse_requests,
    material_request_qr_image,
    ombor_list_page,
)
from .production_views import (
    serial_list_page, vazifalar_page, vazifa_qr_image, pz_create_task, pz_finish_task,
    pz_confirm_task_finished, pz_ack_task_pickup,
)
from .finance_views import qoshimcha_chiqimlar_page, moliya_dashboard
from .badge_views import xodim_badge_page, xodim_badge_image, agent_login_qr_image, regenerate_agent_qr
from django.urls import path, re_path

urlpatterns = [
    path('end-setup/', end_setup, name='end_setup'),
    path('login/', login, name='login'),
    path('', main, name='main'),
    path('logout/', logout_view, name='logout'),
    path('hisobotlar/', hisobotlar_view, name='hisobotlar'),
    path('nasiya-savdolar/', nasiya_savdolar_view, name='nasiya_savdolar'),
    path('nasiya-payment/<int:savdo_id>/', add_nasiya_payment, name='add_nasiya_payment'),
    path('mijozlar/', mijozlar_list, name='mijozlar_list'),
    path('mijoz/<int:mijoz_id>/', mijoz_detail, name='mijoz_detail'),
    path('mijoz/<int:mijoz_id>/set-turi/', set_mijoz_turi, name='set_mijoz_turi'),
    path('hodimlar/', hodimlar_list, name='hodimlar_list'),
    path('mahsulotlar/', mahsulotlar_list, name='mahsulotlar_list'),
    path('add/haridor/', add_haridor, name='add_haridor'),
    path('profile/<str:username>', profile_view, name='profile'),
    path('createuser/', crtuser , name='crtuser'),
    path('edituser/<str:username>', editusr , name='edituser'),
    path('product/<int:mahsulot_id>/', seemahsulot, name='seeproduct'),
    path('product/create/', createmahsulot, name='createproduct'),
    path('product/delete/<str:product_id>',deleteprdct,name='delprdct'),
    path('add/miqdor/', addmiqdor, name='add_miqdor'),
    path('add/yuklama', add_yuklama, name='add_yuklama'),
    path('sotish/' , sotish, name='sotish'),
    path('api/check-new-deliveries/', check_new_deliveries, name='api_check_deliveries'),
    path('api/check-sale-serial/', check_sale_serial, name='check_sale_serial'),
    path('pazanda/sorovlar/', pz_sorov_tarixi, name='pz_sorov_tarixi'),
    path('hisobot/yetkazuvchi/<str:username>/', yetkazuvchi_hisobot, name='yetkazuvchi_hisobot'),
    path('hisobot/pazanda/<str:username>/', pazanda_hisobot, name='pazanda_hisobot'),
    path('navigation/', yt_navigation, name='yt_navigation'),
    path('billing/', billing_page, name='billing_page'),
    path('billing/create-link/', create_billing_link, name='create_billing_link'),
    path('billing/open/<str:token>/', open_billing_link, name='open_billing_link'),
    path('billing/savdogar-contract/', save_savdogar_contract, name='save_savdogar_contract'),
    path('savdogar/', savdogar_admin_dashboard, name='savdogar_admin_dashboard'),
    path('savdogar/shartnoma/', savdogar_contract_page, name='savdogar_contract'),
    path('savdogar/shartnoma/yuklab-olish/', savdogar_contract_download, name='savdogar_contract_download'),
    path('savdogar/savdolar/', savdogar_sales_page, name='savdogar_sales'),
    path('savdogar/nasiya/', savdogar_admin_credit_page, name='savdogar_admin_credit'),
    path('savdogar/mahsulotlar-admin/', savdogar_admin_products_page, name='savdogar_admin_products'),
    path('savdogar/analitika-admin/', savdogar_admin_analytics_page, name='savdogar_admin_analytics'),
    path('savdogar/mening-savdolarim/', savdogar_my_sales, name='savdogar_my_sales'),
    path('savdogar/mening-nasiya/', savdogar_my_credit, name='savdogar_my_credit'),
    path('savdogar/mahsulotlar/', savdogar_my_products, name='savdogar_my_products'),
    path('savdogar/analitika/', savdogar_analytics_page, name='savdogar_analytics'),
    path('amallar/', amallog_view, name='amallog'),
    path('savdo/<int:savdo_id>/chek/', savdo_chek, name='savdo_chek'),
    path('qaytarish/', qaytarish_view, name='qaytarish'),
    path('qaytarishlar/', qaytarishlar_view, name='qaytarishlar'),
    path('qaytarish/tasdiq/<int:qaytarish_id>/', qaytarish_tasdiq, name='qaytarish_tasdiq'),
    path('qaytarish/rad/<int:qaytarish_id>/', qaytarish_rad, name='qaytarish_rad'),
    path('qaytarish/sozlash/', qaytarish_sozlash, name='qaytarish_sozlash'),
    path('kpi/qoidalar/', kpi_qoidalari_view, name='kpi_qoidalari'),
    path('ombor/mahsulotlar/', warehouse_products, name='warehouse_products'),
    path('ombor/mahsulotlar/create/', warehouse_product_create, name='warehouse_product_create'),
    path('ombor/mahsulotlar/<int:product_id>/edit/', warehouse_product_edit, name='warehouse_product_edit'),
    path('ombor/kirim-chiqim/', warehouse_movements, name='warehouse_movements'),
    path('ombor/sorovlar/', warehouse_requests, name='warehouse_requests'),
    path('ombor/sorovlar/<int:request_id>/review/', warehouse_request_review, name='warehouse_request_review'),
    path('ombor/sorovlar/qr/<str:kod>/', material_request_qr_image, name='material_request_qr_image'),
    path('ombor/tarix/', warehouse_history, name='warehouse_history'),
    path('omborlar/', ombor_list_page, name='ombor_list'),

    # Public mahsulot skan sahifasi — QR yorliqda ATAYLAB firma
    # subdomeniga (`https://<firma>.stockfirm.uz/p/<kod>/`) ishora
    # qiladi (`agent_api_views._public_scan_url`), lekin bu route avval
    # faqat `landing/urls.py`da bor edi — subdomen so'rovlari esa shu
    # (`main.urls`) urlconf orqali ishlaydi (`CompanyMiddleware`), shu
    # sabab har bir mijoz QR skanerlaganda 404 chiqargan (real bug,
    # xaridor tomonidan aniqlangan).
    path('p/<str:kod>/', product_scan_view, name='product_scan'),
    path('api/p/<str:kod>/status/', product_scan_status_api, name='product_scan_status_api'),

    # Xodim shaxsiy QR badge
    path('xodim/badge/', xodim_badge_page, name='xodim_badge'),
    path('xodim/badge/<int:user_id>/', xodim_badge_page, name='xodim_badge_for'),
    path('xodim/badge/rasm/<str:kod>/', xodim_badge_image, name='xodim_badge_image'),
    path('xodim/agent-qr/<int:user_id>/', agent_login_qr_image, name='agent_login_qr_image'),
    path('xodim/agent-qr/<int:user_id>/yangilash/', regenerate_agent_qr, name='regenerate_agent_qr'),

    # Ishlab chiqarish (serial/QR ro'yxati — "ish haqi turi" endi Hodimlar sahifasida)
    path('ishlab-chiqarish/seriallar/<int:mahsulot_id>/', serial_list_page, name='serial_list'),
    path('ishlab-chiqarish/vazifalar/', vazifalar_page, name='vazifalar'),
    path('ishlab-chiqarish/vazifalar/<str:kod>/qr/', vazifa_qr_image, name='vazifa_qr_image'),
    path('vazifa/yaratish/', pz_create_task, name='pz_create_task'),
    path('vazifa/<int:task_id>/tugatish/', pz_finish_task, name='pz_finish_task'),
    path('vazifa/<int:task_id>/ish-bitdi/', pz_confirm_task_finished, name='pz_confirm_task_finished'),
    path('vazifa/pickup/<int:pickup_id>/oldim/', pz_ack_task_pickup, name='pz_ack_task_pickup'),

    # Moliya
    path('moliya/chiqimlar/', qoshimcha_chiqimlar_page, name='qoshimcha_chiqimlar'),
    path('moliya/', moliya_dashboard, name='moliya_dashboard'),

    # KPI
    path('api/kpi/today/', kpi_today, name='kpi_today'),
    path('api/kpi/trend/', trend_30, name='trend_30'),
    path('api/kpi/set-target/', set_daily_target, name='set_daily_target'),

    # Excel Export
    path('export/savdolar/', export_savdolar, name='export_savdolar'),
    path('export/nasiya/', export_nasiya, name='export_nasiya'),
    path('export/mahsulotlar/', export_mahsulotlar, name='export_mahsulotlar'),
    path('export/xodimlar/', export_xodimlar, name='export_xodimlar'),

    # Backup System
    path('backup/prepare/', prepare_backup_page, name='prepare_backup_page'),
    path('backup/download/', download_backup, name='download_backup'),
    path('backup/restore/', restore_view, name='restore_view'),
    
    # Analytics Dashboard
    path('analytics/', analytics_dashboard, name='analytics_dashboard'),
    
    # Analytics API endpoints
    path('api/analytics/product-demand/', analytics.product_demand_api, name='api_product_demand'),
    path('api/analytics/products/', analytics.products_list_api, name='api_products_list'),
    path('api/analytics/shop-recommendations/', analytics.shop_recommendations_api, name='api_shop_recommendations'),
    path('api/analytics/top-shops/', analytics.top_products_api, name='api_top_shops'),
    path('map/', map_dashboard, name='map_dashboard'),
    path('map/routes/', route_history_page, name='route_history'),
    path('api/map/data/', api_map_data, name='api_map_data'),
    path('api/map/active-days/<int:deliverer_id>/', api_route_active_days, name='api_route_active_days'),
    path('api/map/route/<int:deliverer_id>/', api_route_history, name='api_route_history'),
    path('api/location/batch/', api_location_batch, name='api_location_batch'),
    path('agent/yuklab-olish/', download_desktop_agent, name='download_desktop_agent'),
    path('api/stansiyalar-holati/', agent_stations_status_api, name='agent_stations_status_api'),
    path('offline/', offline_page, name='offline_page'),
    path('sw.js', service_worker_js, name='service_worker_js'),
    path('select-plan-page/', select_plan_page, name='select_plan_page'),
    path('request-trial/', request_trial, name='request_trial'),
    path('select-plan/<int:plan_id>/', select_plan, name='select_plan'),
    path('select-custom-plan/', select_custom_plan, name='select_custom_plan'),
    
    # Click API integration
    path('api/click/prepare/', click_prepare, name='click_prepare'),
    path('api/click/complete/', click_complete, name='click_complete'),
    path('payment/click/redirect/', click_pay_redirect, name='click_pay_redirect'),
]

if settings.SERVE_MEDIA_FILES:
    urlpatterns += [
        re_path(
            r'^media/(?P<path>.*)$',
            serve,
            {'document_root': settings.MEDIA_ROOT},
        ),
    ]

if settings.SERVE_STATIC_FILES:
    urlpatterns += [
        re_path(
            r'^static/(?P<path>.*)$',
            serve,
            {'document_root': settings.STATIC_ROOT},
        ),
    ]
