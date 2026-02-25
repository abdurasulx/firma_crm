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
    
    # Qidiruv
    search_query = request.GET.get('q', '')
    if search_query:
        from django.db.models import Q
        hodimlar = hodimlar.filter(
            Q(tuliq_ismi__icontains=search_query) | 
            Q(username__icontains=search_query) |
            Q(tel_raqami__icontains=search_query)
        )

    # Role Filter
    role_filter = request.GET.get('role', '')
    if role_filter:
        hodimlar = hodimlar.filter(type=role_filter)

    # Filter
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        hodimlar = hodimlar.filter(is_active=True)
    elif status_filter == 'inactive':
        hodimlar = hodimlar.filter(is_active=False)
        
    # Sorting
    sort_order = request.GET.get('sort', 'newest')
    if sort_order == 'oldest':
        hodimlar = hodimlar.order_by('date_joined')
    else:
        hodimlar = hodimlar.order_by('-date_joined')
    
    # Check for AJAX/JSON request
    if request.GET.get('data_format') == 'json':
        from django.http import JsonResponse
        from django.utils.timesince import timesince
        data = []
        for h in hodimlar[:7]:  # Limit to 7 results for dropdown
            data.append({
                'username': h.username,
                'tuliq_ismi': h.tuliq_ismi or h.username,
                'rasmi_url': h.rasmi if h.rasmi else None,
                'tel_raqami': h.tel_raqami or '',
                'type': h.get_type_display(),
                'status': 'Active' if h.is_active else 'Inactive',
                'date_joined': h.date_joined.strftime('%d %b %Y, %H:%M') if h.date_joined else '',
                'last_activity': timesince(h.last_login) + ' oldin' if h.last_login else 'Noma\'lum',
            })
        return JsonResponse({'results': data})
    
    # Pagination - har sahifada 20 ta
    paginator = Paginator(hodimlar, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get elided page range (e.g. 1 ... 4 5 6 ... 35)
    elided_range = paginator.get_elided_page_range(page_number, on_each_side=2, on_ends=1)
    
    context = {
        'hodimlar': page_obj,
        'total': hodimlar.count(),
        'page_range': elided_range,
        'search_query': search_query,
        'status_filter': status_filter,
        'role_filter': role_filter,
        'sort_order': sort_order
    }
    
    return render(request, 'hodimlar_list.html', context)


@login_required(login_url='login')
def mahsulotlar_list(request):
    """Barcha mahsulotlar ro'yxati"""
    if request.user.type != 'ega':
        return redirect('main')
    
    mahsulotlar = Mahsulot.objects.all()
    
    # Qidiruv
    search_query = request.GET.get('q', '')
    if search_query:
        from django.db.models import Q
        mahsulotlar = mahsulotlar.filter(Q(nomi__icontains=search_query))
    
    # Tur filter
    tur_filter = request.GET.get('tur', '')
    if tur_filter:
        mahsulotlar = mahsulotlar.filter(turi__id=tur_filter)
    
    # Sorting
    sort_order = request.GET.get('sort', 'name')
    if sort_order == 'name':
        mahsulotlar = mahsulotlar.order_by('nomi')
    elif sort_order == 'price_high':
        mahsulotlar = mahsulotlar.order_by('-narxi')
    elif sort_order == 'price_low':
        mahsulotlar = mahsulotlar.order_by('narxi')
    elif sort_order == 'stock':
        mahsulotlar = mahsulotlar.order_by('-miqdori')
    else:
        mahsulotlar = mahsulotlar.order_by('nomi')
    
    # Check for AJAX/JSON request
    if request.GET.get('data_format') == 'json':
        from django.http import JsonResponse
        data = []
        # Limit to 7 results for the search dropdown
        for m in mahsulotlar[:7]:
            data.append({
                'id': m.id,
                'nomi': m.nomi,
                'turi': m.turi.nomi if m.turi else 'Kategoriya yo\'q',
                'narxi': f"{m.narxi:,.0f} so'm".replace(',', ' '),
                'rasmi_url': m.rasmi.url if m.rasmi else None,
            })
        return JsonResponse({'results': data})

    # Pagination - har sahifada 24 ta
    paginator = Paginator(mahsulotlar, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all product types for filter dropdown
    from .models import MahsulotTuri
    mahsulot_turlari = MahsulotTuri.objects.all()
    
    context = {
        'mahsulotlar': page_obj,
        'total': mahsulotlar.count(),
        'search_query': search_query,
        'tur_filter': tur_filter,
        'sort_order': sort_order,
        'mahsulot_turlari': mahsulot_turlari
    }
    
    return render(request, 'mahsulotlar_list.html', context)
