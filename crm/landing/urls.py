from django.urls import path, include
from . import views
from .views import (
    landing_home,
    pricing_view,
    register_company,
    custom_404,
    super_plan_delete,
    plan_requests_list,
    approve_plan_request,
    reject_plan_request
)
from main.views import login

urlpatterns = [
    path('', landing_home, name='landing_home'),
    path('pricing/', pricing_view, name='pricing'),
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
    
    path('404/', custom_404, name='custom_404_preview'),
]
