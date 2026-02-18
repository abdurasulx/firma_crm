from django.conf import settings
from django.conf.urls.static import static
from .views import login, main, add_haridor, profile_view, crtuser, editusr, sotish, seemahsulot, createmahsulot, deleteprdct, addmiqdor, add_yuklama, logout_view, check_new_deliveries
from .hisobot_views import hisobotlar_view
from .list_views import hodimlar_list, mahsulotlar_list
from .nasiya_views import nasiya_savdolar_view, add_nasiya_payment
from .mijoz_views import mijozlar_list, mijoz_detail
from . import analytics
from .analytics_views import analytics_dashboard
from django.urls import path

urlpatterns = [
    path('login/', login, name='login'),
    path('', main, name='main'),
    path('logout/', logout_view, name='logout'),
    path('hisobotlar/', hisobotlar_view, name='hisobotlar'),
    path('nasiya-savdolar/', nasiya_savdolar_view, name='nasiya_savdolar'),
    path('nasiya-payment/<int:savdo_id>/', add_nasiya_payment, name='add_nasiya_payment'),
    path('mijozlar/', mijozlar_list, name='mijozlar_list'),
    path('mijoz/<int:mijoz_id>/', mijoz_detail, name='mijoz_detail'),
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
    
    # Analytics Dashboard
    path('analytics/', analytics_dashboard, name='analytics_dashboard'),
    
    # Analytics API endpoints
    path('api/analytics/product-demand/', analytics.product_demand_api, name='api_product_demand'),
    path('api/analytics/products/', analytics.products_list_api, name='api_products_list'),
    path('api/analytics/shop-recommendations/', analytics.shop_recommendations_api, name='api_shop_recommendations'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)