from django.conf import settings
from django.urls import path, include, re_path
from django.views.static import serve
from . import views
from .views import (
    landing_home,
    marketing_page,
    pricing_view,
    offer_view,
    register_company,
    custom_404,
    super_plan_delete,
    plan_requests_list,
    approve_plan_request,
    reject_plan_request,
    product_scan_view,
    product_scan_status_api,
    qr_image_view,
)
from main.views import login
from main.agent_api_views import (
    agent_station_login,
    agent_login_by_qr,
    agent_verify_kiosk_unlock,
    agent_omborlar,
    agent_badge_scan,
    agent_scan,
    agent_material_requests,
    agent_acknowledge_material_request,
    agent_weigh_material_request,
    agent_weigh_task_pickup,
    agent_pending_print_batch,
    agent_mark_batch_printed,
    agent_report_print_result,
    agent_miqdor_requests,
    agent_my_task_pickups,
    agent_approve_miqdor_qoshish,
    agent_miqdor_print_page,
    agent_delivery_requests,
    agent_scan_delivery_serial,
    agent_finalize_yuklama,
    agent_saler_lookup_mahsulot,
    agent_saler_finalize_sale,
    agent_toggle_attendance,
    agent_heartbeat,
    agent_logout,
)

urlpatterns = [
    path('', landing_home, name='landing_home'),
    path('platform/<slug:slug>/', marketing_page, name='marketing_page'),
    path('pricing/', pricing_view, name='pricing'),
    path('offer/', offer_view, name='offer'),
    path('register/', register_company, name='register_company'),
    path('login/', login, name='login'),
    
    # Super Admin Dashboard
    path('super/', views.super_dashboard, name='super_dashboard'),
    path('super/companies/', views.super_companies, name='super_companies'),
    path('super/companies/create/', views.super_company_create, name='super_company_create'),
    path('super/companies/edit/<int:pk>/', views.super_company_edit, name='super_company_edit'),
    path('super/companies/delete/<int:pk>/', views.super_company_delete, name='super_company_delete'),
    
    # Super Admin Plans
    path('super/plans/', views.super_plan_list, name='super_plan_list'),
    path('super/plans/create/', views.super_plan_create, name='super_plan_create'),
    path('super/plans/<int:pk>/edit/', views.super_plan_edit, name='super_plan_edit'),
    path('super/plans/<int:pk>/delete/', views.super_plan_delete, name='super_plan_delete'),
    
    # Plan Requests
    path('super/plan-requests/', views.plan_requests_list, name='plan_requests_list'),
    path('super/plan-requests/<int:request_id>/approve/', views.approve_plan_request, name='approve_plan_request'),
    path('super/plan-requests/<int:request_id>/reject/', views.reject_plan_request, name='reject_plan_request'),
    
    # Billing
    path('super/billing/', views.super_billing_report, name='super_billing_report'),
    path('super/billing/update/<int:company_id>/', views.update_billing_status, name='update_billing_status'),

    # Backup (superadmin — bitta firma yoki butun tizim, faqat yuklab olish)
    path('super/backup/', views.super_backup_page, name='super_backup_page'),
    path('super/backup/download/', views.super_backup_download, name='super_backup_download'),
    path('super/agent-releases/', views.super_agent_releases, name='super_agent_releases'),
    path('super/agent-releases/<int:release_id>/delete/', views.super_agent_release_delete, name='super_agent_release_delete'),
    
    path('404/', custom_404, name='custom_404_preview'),

    # QR/Serial — public
    path('p/<str:kod>/', product_scan_view, name='product_scan'),
    path('api/p/<str:kod>/status/', product_scan_status_api, name='product_scan_status_api'),
    path('api/qr/image/<str:kod>/', qr_image_view, name='qr_image'),

    # Desktop Agent REST API (token orqali autentifikatsiya, subdomain'ga bog'liq emas)
    path('api/agent/login/', agent_station_login, name='agent_station_login'),
    path('api/agent/login-by-qr/', agent_login_by_qr, name='agent_login_by_qr'),
    path('api/agent/verify-kiosk-unlock/', agent_verify_kiosk_unlock, name='agent_verify_kiosk_unlock'),
    path('api/agent/omborlar/', agent_omborlar, name='agent_omborlar'),
    path('api/agent/badge-scan/', agent_badge_scan, name='agent_badge_scan'),
    path('api/agent/scan/', agent_scan, name='agent_scan'),
    path('api/agent/material-requests/', agent_material_requests, name='agent_material_requests'),
    path('api/agent/material-requests/<int:request_id>/acknowledge/', agent_acknowledge_material_request, name='agent_acknowledge_material_request'),
    path('api/agent/material-requests/<int:request_id>/weigh/', agent_weigh_material_request, name='agent_weigh_material_request'),
    path('api/agent/task-pickup/<int:pickup_id>/weigh/', agent_weigh_task_pickup, name='agent_weigh_task_pickup'),
    path('api/agent/pending-print-batch/', agent_pending_print_batch, name='agent_pending_print_batch'),
    path('api/agent/mark-batch-printed/', agent_mark_batch_printed, name='agent_mark_batch_printed'),
    path('api/agent/report-print-result/', agent_report_print_result, name='agent_report_print_result'),
    path('api/agent/my-task-pickups/', agent_my_task_pickups, name='agent_my_task_pickups'),
    path('api/agent/miqdor-qoshish/', agent_miqdor_requests, name='agent_miqdor_requests'),
    path('api/agent/miqdor-qoshish/<int:request_id>/tasdiqlash/', agent_approve_miqdor_qoshish, name='agent_approve_miqdor_qoshish'),
    path('api/agent/miqdor-qoshish/<int:request_id>/chop-etish/', agent_miqdor_print_page, name='agent_miqdor_print_page'),
    path('api/agent/yuklama/sorovlar/', agent_delivery_requests, name='agent_delivery_requests'),
    path('api/agent/yuklama/skaner/', agent_scan_delivery_serial, name='agent_scan_delivery_serial'),
    path('api/agent/yuklama/yakunlash/', agent_finalize_yuklama, name='agent_finalize_yuklama'),
    path('api/agent/saler/mahsulot/', agent_saler_lookup_mahsulot, name='agent_saler_lookup_mahsulot'),
    path('api/agent/saler/sotuv/', agent_saler_finalize_sale, name='agent_saler_finalize_sale'),
    path('api/agent/davomat/', agent_toggle_attendance, name='agent_toggle_attendance'),
    path('api/agent/heartbeat/', agent_heartbeat, name='agent_heartbeat'),
    path('api/agent/logout/', agent_logout, name='agent_logout'),
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
