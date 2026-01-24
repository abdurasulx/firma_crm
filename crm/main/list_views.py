from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import User, Mahsulot
from django.core.paginator import Paginator


@login_required(login_url='login')
def hodimlar_list(request):
    """Barcha xodimlar ro'yxati"""
    if request.user.type != 'ega':
        return redirect('main')
    
    hodimlar = User.objects.exclude(type='ega').order_by('-date_joined')
    
    # Pagination - har sahifada 20 ta
    paginator = Paginator(hodimlar, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'hodimlar': page_obj,
        'total': hodimlar.count()
    }
    
    return render(request, 'hodimlar_list.html', context)


@login_required(login_url='login')
def mahsulotlar_list(request):
    """Barcha mahsulotlar ro'yxati"""
    if request.user.type != 'ega':
        return redirect('main')
    
    mahsulotlar = Mahsulot.objects.all().order_by('nomi')
    
    # Pagination - har sahifada 24 ta
    paginator = Paginator(mahsulotlar, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'mahsulotlar': page_obj,
        'total': mahsulotlar.count()
    }
    
    return render(request, 'mahsulotlar_list.html', context)
