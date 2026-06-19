from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation

from .models import Mahsulot, MahsulotTuri, ProductionMaterialRequest, StockHistory


def _send_ws_notification(company_subdomain, title, message, type='info', refresh=False):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"notifications_{company_subdomain}",
            {
                "type": "send_notification",
                "title": title,
                "message": message,
                "notification_type": type,
                "refresh": refresh,
            },
        )
    except Exception as exc:
        print(f"Warehouse notification error: {exc}")


def _warehouse_guard(request):
    return request.user.type in ['omborchi', 'ega']


def _is_warehouse_operator(request):
    return request.user.type == 'omborchi'


def _warehouse_product_queryset(request):
    products = Mahsulot.objects.filter(company=request.company).select_related('turi')
    if _is_warehouse_operator(request):
        products = products.filter(warehouse_type='semi_finished')
    return products


@login_required(login_url='login')
def warehouse_products(request):
    if not _warehouse_guard(request):
        return redirect('main')

    products = _warehouse_product_queryset(request)
    warehouse_type = request.GET.get('warehouse_type', 'semi_finished')
    query = request.GET.get('q', '').strip()

    if _is_warehouse_operator(request):
        warehouse_type = 'semi_finished'
    elif warehouse_type in ['finished', 'semi_finished']:
        products = products.filter(warehouse_type=warehouse_type)
    if query:
        products = products.filter(Q(nomi__icontains=query) | Q(turi__nomi__icontains=query))

    products = products.order_by('nomi')
    paginator = Paginator(products, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'warehouse_products.html', {
        'products': page_obj,
        'total': products.count(),
        'warehouse_type': warehouse_type,
        'query': query,
        'warehouse_only': _is_warehouse_operator(request),
    })


@login_required(login_url='login')
def warehouse_product_create(request):
    if not _warehouse_guard(request):
        return redirect('main')
    if _is_warehouse_operator(request):
        messages.error(request, "Omborchi mahsulot yaratmaydi. Mahsulotlarni ega boshqaradi.")
        return redirect('warehouse_products')

    if request.method == 'POST':
        product_data = {
            'company': request.company,
            'nomi': request.POST.get('nomi', '').strip(),
            'miqdori': float(request.POST.get('miqdori') or 0),
            'min_miqdori': float(request.POST.get('min_miqdori') or 10),
            'narxi': request.POST.get('narxi') or 0,
            'turi': get_object_or_404(MahsulotTuri, id=request.POST.get('turi')),
            'warehouse_type': 'semi_finished' if _is_warehouse_operator(request) else request.POST.get('warehouse_type', 'semi_finished'),
            'is_savdogar_product': False if _is_warehouse_operator(request) else 'is_savdogar_product' in request.POST,
        }
        if request.FILES.get('rasmi'):
            product_data['rasmi'] = request.FILES['rasmi']
        product = Mahsulot.objects.create(**product_data)
        StockHistory.objects.create(
            actor_user=request.user,
            company=request.company,
            mahsulot=product,
            event_type='ADD',
            old_qty=0,
            new_qty=product.miqdori,
            delta=product.miqdori,
        )
        messages.success(request, "Ombor mahsuloti yaratildi.")
        return redirect('warehouse_products')

    return render(request, 'warehouse_product_form.html', {
        'turs': MahsulotTuri.objects.all().order_by('nomi'),
        'product': None,
        'warehouse_only': _is_warehouse_operator(request),
    })


@login_required(login_url='login')
def warehouse_product_edit(request, product_id):
    if not _warehouse_guard(request):
        return redirect('main')
    if _is_warehouse_operator(request):
        messages.error(request, "Omborchi mahsulot ma'lumotlarini tahrirlamaydi.")
        return redirect('warehouse_products')

    product = get_object_or_404(_warehouse_product_queryset(request), id=product_id)
    if request.method == 'POST':
        old_qty = product.miqdori
        product.nomi = request.POST.get('nomi', '').strip()
        product.narxi = request.POST.get('narxi') or 0
        product.miqdori = float(request.POST.get('miqdori') or 0)
        product.min_miqdori = float(request.POST.get('min_miqdori') or 10)
        product.turi = get_object_or_404(MahsulotTuri, id=request.POST.get('turi'))
        product.warehouse_type = 'semi_finished' if _is_warehouse_operator(request) else request.POST.get('warehouse_type', product.warehouse_type)
        product.is_savdogar_product = False if _is_warehouse_operator(request) else 'is_savdogar_product' in request.POST
        if request.FILES.get('rasmi'):
            product.rasmi = request.FILES['rasmi']
        product.save()

        if old_qty != product.miqdori:
            StockHistory.objects.create(
                actor_user=request.user,
                company=request.company,
                mahsulot=product,
                event_type='ADJUST',
                old_qty=old_qty,
                new_qty=product.miqdori,
                delta=product.miqdori - old_qty,
            )
        messages.success(request, "Ombor mahsuloti saqlandi.")
        return redirect('warehouse_products')

    return render(request, 'warehouse_product_form.html', {
        'turs': MahsulotTuri.objects.all().order_by('nomi'),
        'product': product,
        'warehouse_only': _is_warehouse_operator(request),
    })


@login_required(login_url='login')
def warehouse_movements(request):
    if not _warehouse_guard(request):
        return redirect('main')

    products = _warehouse_product_queryset(request).order_by('nomi')

    if request.method == 'POST':
        movement_type = request.POST.get('movement_type')
        qty = float(request.POST.get('qty') or 0)
        incoming_price = None

        if qty <= 0:
            messages.error(request, "Miqdor 0 dan katta bo'lishi kerak.")
            return redirect('warehouse_movements')
        if movement_type != 'in':
            messages.error(request, "Omborda faqat kirim kiritiladi. Kamaytirish ishlab chiqaruvchi so'rovlari orqali yuritiladi.")
            return redirect('warehouse_movements')
        if movement_type == 'in':
            try:
                incoming_price = Decimal((request.POST.get('price') or '0').replace(',', '.'))
            except (InvalidOperation, AttributeError):
                incoming_price = Decimal('0')
            if incoming_price < 0:
                messages.error(request, "Kirim narxi manfiy bo'lishi mumkin emas.")
                return redirect('warehouse_movements')

        with transaction.atomic():
            product_qs = Mahsulot.objects.select_for_update().select_related('turi').filter(company=request.company)
            if _is_warehouse_operator(request):
                product_qs = product_qs.filter(warehouse_type='semi_finished')
            product = get_object_or_404(product_qs, id=request.POST.get('mahsulot'))
            old_qty = product.miqdori
            product.miqdori = old_qty + qty
            product.narxi = incoming_price
            event_type = 'ADD'
            delta = qty
            action_text = "Kirim"
            update_fields = ['miqdori', 'narxi']
            product.save(update_fields=update_fields)
            StockHistory.objects.create(
                actor_user=request.user,
                company=request.company,
                mahsulot=product,
                event_type=event_type,
                old_qty=old_qty,
                new_qty=product.miqdori,
                delta=delta,
            )
        messages.success(request, f"{action_text} yozildi: {product.nomi} {qty:g} {product.turi.nomi}.")
        return redirect('warehouse_movements')

    recent_history = StockHistory.objects.filter(company=request.company).select_related('mahsulot', 'actor_user')
    if _is_warehouse_operator(request):
        recent_history = recent_history.filter(mahsulot__warehouse_type='semi_finished')
    recent_history = recent_history[:15]
    return render(request, 'warehouse_movements.html', {
        'products': products,
        'recent_history': recent_history,
    })


@login_required(login_url='login')
def warehouse_requests(request):
    if not _warehouse_guard(request):
        return redirect('main')

    requests_qs = ProductionMaterialRequest.objects.filter(company=request.company).select_related(
        'producer', 'producer__user', 'material', 'material__turi', 'target_product', 'reviewed_by'
    )
    if _is_warehouse_operator(request):
        requests_qs = requests_qs.filter(material__warehouse_type='semi_finished')
    status_filter = request.GET.get('status', 'waiting')
    if status_filter in ['waiting', 'approved', 'rejected']:
        requests_qs = requests_qs.filter(status=status_filter)

    paginator = Paginator(requests_qs, 20)
    return render(request, 'warehouse_requests.html', {
        'requests_page': paginator.get_page(request.GET.get('page')),
        'status_filter': status_filter,
    })


@login_required(login_url='login')
@require_POST
def warehouse_request_review(request, request_id):
    if not _warehouse_guard(request):
        return redirect('main')

    with transaction.atomic():
        request_qs = ProductionMaterialRequest.objects.select_for_update().select_related('material').filter(
            company=request.company,
            status='waiting',
        )
        if _is_warehouse_operator(request):
            request_qs = request_qs.filter(material__warehouse_type='semi_finished')
        material_request = get_object_or_404(request_qs, id=request_id)
        material_qs = Mahsulot.objects.select_for_update().select_related('turi').filter(company=request.company)
        if _is_warehouse_operator(request):
            material_qs = material_qs.filter(warehouse_type='semi_finished')
        material = get_object_or_404(material_qs, id=material_request.material_id)
        old_qty = material.miqdori
        if request.POST.get('action') == 'approve':
            if old_qty < material_request.qty:
                messages.error(request, f"{material.nomi} omborda yetarli emas. Qoldiq: {old_qty:g} {material.turi.nomi}.")
                return redirect('warehouse_requests')
            material.miqdori = old_qty - material_request.qty
            material.save(update_fields=['miqdori'])
            material_request.status = 'approved'
            event_type = 'RAW_APPROVED'
            delta = -material_request.qty
            notification_title = "Material so'rovi tasdiqlandi"
            notification_type = 'success'
            messages.success(request, "Material so'rovi tasdiqlandi.")
        else:
            material_request.status = 'rejected'
            event_type = 'RAW_REJECTED'
            delta = 0
            notification_title = "Material so'rovi rad etildi"
            notification_type = 'warning'
            messages.success(request, "Material so'rovi rad etildi.")

        material_request.reviewed_by = request.user
        material_request.reviewed_at = timezone.now()
        material_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
        StockHistory.objects.create(
            actor_user=request.user,
            company=request.company,
            mahsulot=material,
            event_type=event_type,
            old_qty=old_qty,
            new_qty=material.miqdori,
            delta=delta,
        )
        target_name = material_request.target_product.nomi if material_request.target_product else "mahsulot"
        notification_message = (
            f"{target_name} uchun {material_request.qty:g} {material.turi.nomi} "
            f"{material.nomi} so'rovi ko'rib chiqildi."
        )
    _send_ws_notification(
        request.company.subdomain,
        notification_title,
        notification_message,
        notification_type,
        refresh=True,
    )
    return redirect('warehouse_requests')


@login_required(login_url='login')
def warehouse_history(request):
    if not _warehouse_guard(request):
        return redirect('main')

    history = StockHistory.objects.filter(company=request.company).select_related('mahsulot', 'actor_user')
    event_choices = StockHistory.EVENT_TYPES
    if _is_warehouse_operator(request):
        history = history.filter(mahsulot__warehouse_type='semi_finished')
        allowed_events = {'ADD', 'ADJUST', 'RAW_APPROVED', 'RAW_REJECTED'}
        history = history.filter(event_type__in=allowed_events)
        event_choices = tuple(choice for choice in StockHistory.EVENT_TYPES if choice[0] in allowed_events)
    event_type = request.GET.get('event_type', '')
    query = request.GET.get('q', '').strip()

    if event_type:
        history = history.filter(event_type=event_type)
    if query:
        history = history.filter(mahsulot__nomi__icontains=query)

    paginator = Paginator(history, 30)
    return render(request, 'warehouse_history.html', {
        'history_page': paginator.get_page(request.GET.get('page')),
        'event_type': event_type,
        'query': query,
        'event_choices': event_choices,
    })
