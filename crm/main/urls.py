from django.conf import settings
from django.conf.urls.static import static
from .views import login, main, add_haridor, profile_view, crtuser, editusr, seemahsulot, createmahsulot, deleteprdct
from django.urls import path

urlpatterns = [
    path('login/', login, name='login'),
    path('', main, name='main'),
    path('logout/', login, name='logout'),
    path('add/haridor/', add_haridor, name='add_haridor'),
    path('profile/<str:username>', profile_view, name='profile'),
    path('createuser/', crtuser , name='crtuser'),
    path('edituser/<str:username>', editusr , name='edituser'),
    path('product/<int:mahsulot_id>/', seemahsulot, name='seeproduct'),
    path('product/create/', createmahsulot, name='createproduct'),
    path('product/delete/<str:product_id>',deleteprdct,name='delprdct'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)