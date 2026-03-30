"""
URL configuration for crm project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from landing import views as landing_views

def root_routing_view(request):
    if getattr(request, 'is_landing', False):
        return include('landing.urls') # Note: include doesn't work directly in views like this easily in standard Django
    return include('main.urls')

# Simplified logic: use URLconfs directly or a routing wrapper
urlpatterns = [
    path('admin/', admin.site.urls),
]

# dynamic inclusion based on middleware flags
def get_urls(request):
    if getattr(request, 'is_landing', False):
        return 'landing.urls'
    return 'main.urls'

# Actually, the best way in Django for this is to include both but let middleware/views handle the logic, 
# or use a custom URL dispatcher. But for a simple SaaS, we can just include them both 
# and let the views in each app check for request.is_landing.

urlpatterns = [
    path('admin_panel/', admin.site.urls), # Rename to avoid confusion with subdomain admin
    path('', include('landing.urls')),
    path('', include('main.urls')),
]

handler404 = 'landing.views.custom_404'
