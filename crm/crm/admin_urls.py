from django.urls import path
from landing import views as landing_views
from django.contrib import admin

from main import views as main_views

urlpatterns = [
    path('login/', main_views.login, name='login'),
    # Alias for default Django redirection
    path('accounts/login/', main_views.login), 
    path('logout/', main_views.logout_view, name='logout'),
    path('', landing_views.super_dashboard, name='super_dashboard'),
    # Fallback for views that expect landing_home
    path('dashboard/', landing_views.super_dashboard, name='landing_home'), 
    path('companies/', landing_views.super_companies, name='super_companies'),
    path('companies/add/', landing_views.super_company_create, name='super_company_create'),
    path('companies/edit/<int:pk>/', landing_views.super_company_edit, name='super_company_edit'),
    path('companies/delete/<int:pk>/', landing_views.super_company_delete, name='super_company_delete'),
    
    path('plans/', landing_views.super_plan_list, name='super_plan_list'),
    path('plans/add/', landing_views.super_plan_create, name='super_plan_create'),
    path('plans/edit/<int:pk>/', landing_views.super_plan_edit, name='super_plan_edit'),
    path('plans/delete/<int:pk>/', landing_views.super_plan_delete, name='super_plan_delete'),
    
    # Plan Requests
    path('plan-requests/', landing_views.plan_requests_list, name='plan_requests_list'),
    path('plan-requests/<int:request_id>/approve/', landing_views.approve_plan_request, name='approve_plan_request'),
    path('plan-requests/<int:request_id>/reject/', landing_views.reject_plan_request, name='reject_plan_request'),
    
    # Billing
    path('billing/', landing_views.super_billing_report, name='super_billing_report'),
    path('billing/update/<int:company_id>/', landing_views.update_billing_status, name='update_billing_status'),
    
    path('admin_panel/', admin.site.urls),
]
