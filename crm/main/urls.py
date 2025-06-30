from django.conf import settings
from django.conf.urls.static import static
from .views import login, main, add_haridor, profile_view, crtuser
from django.urls import path

urlpatterns = [
    path('login/', login, name='login'),
    path('', main, name='main'),
    path('logout/', login, name='logout'),
    path('register/', add_haridor, name='add_haridor'),
    path('profile/<str:username>', profile_view, name='profile'),
    path('createuser/', crtuser , name='crtuser'),
    path('edituser/<str:username>', profile_view , name='edituser'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)