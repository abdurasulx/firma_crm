from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from .models import Mahsulot, MahsulotTuri, ProductionMaterialRequest, StockHistory, Ombor, MahsulotQoshimchaXarajat, MahsulotRetsept
from .services.ombor_service import deduct_ombor_stock, add_ombor_stock
from .services.stock_service import recompute_tannarx
from .services.retsept_service import add_retsept_row, delete_retsept_row
from .decorators import role_required


def _send_ws_notification(company_subdomain, title, message, type='info', refresh=False, event=None, extra=None):
    """`event` — ixtiyoriy, mashinaviy o'qish uchun semantik hodisa nomi
    (masalan 'ombor_changed') — brauzer buni e'tiborsiz qoldiradi
    (faqat `title`/`message`/`type`/`refresh` ko'rsatadi), lekin Desktop
    Agent (`/ws/notifications/`ga token orqali ulanadigan) shu maydonga
    qarab, faqat o'ziga tegishli hodisalarda (masalan omborlar
    ro'yxatini) qayta yuklaydi (90-qadamdan keyingi, real-vaqtli
    sinxronlash ishi).

    `extra` — ixtiyoriy qo'shimcha ma'lumot (dict), masalan stansiya
    onlayn holati (`agent_heartbeat` hodisasi uchun) — brauzer JS'i
    shu orqali sahifani qayta yuklashsiz darhol yangilaydi."""
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
                "event": event,
                "extra": extra or {},
            },
        )
    except Exception as exc:
        print(f"Warehouse notification error: {exc}")


def _warehouse_guard(request):
    return request.user.type in ['omborchi', 'ega']


def _is_warehouse_operator(request):
    return request.user.type == 'omborchi'


def _warehouse_product_queryset(request):
    return Mahsulot.objects.filter(company=request.company, warehouse_type='semi_finished').select_related('turi')


@login_required(login_url='login')
def warehouse_products(request):
    if not _warehouse_guard(request):
        return redirect('main')

    products = _warehouse_product_queryset(request)
    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(Q(nomi__icontains=query) | Q(turi__nomi__icontains=query))

    products = products.order_by('nomi')
    paginator = Paginator(products, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'warehouse_products.html', {
        'products': page_obj,
        'total': products.count(),
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
        if not request.FILES.get('rasmi'):
            messages.error(request, "Rasm biriktirish majburiy.")
            return redirect('warehouse_product_create')

        product_data = {
            'company': request.company,
            'nomi': request.POST.get('nomi', '').strip(),
            'miqdori': float(request.POST.get('miqdori') or 0),
            'min_miqdori': float(request.POST.get('min_miqdori') or 10),
            'narxi': 0,
            'turi': get_object_or_404(MahsulotTuri, id=request.POST.get('turi')),
            'warehouse_type': 'semi_finished',
            'ombor_turi': request.POST.get('ombor_turi', 'xom_ashyo'),
            'rasmi': request.FILES['rasmi'],
        }
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
        'ombor_turi_choices': Mahsulot.OMBOR_TURI_CHOICES,
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
        action = request.POST.get('action')

        if action == 'add_xarajat':
            nomi_x = (request.POST.get('xarajat_nomi') or '').strip()
            turi_x = request.POST.get('xarajat_turi') or 'miqdor'
            if turi_x not in dict(MahsulotQoshimchaXarajat.XARAJAT_TURI_CHOICES):
                turi_x = 'miqdor'
            try:
                summa_x = float(request.POST.get('xarajat_summa') or 0)
            except ValueError:
                summa_x = 0
            if nomi_x and summa_x > 0:
                MahsulotQoshimchaXarajat.objects.create(
                    company=request.company, mahsulot=product, nomi=nomi_x, turi=turi_x, summa=summa_x,
                )
                recompute_tannarx(product)
                messages.success(request, "Qo'shimcha xarajat qo'shildi.")
            else:
                messages.error(request, "Xarajat nomi va summasi to'g'ri kiritilishi kerak.")
            return redirect('warehouse_product_edit', product_id=product.id)

        if action == 'delete_xarajat':
            MahsulotQoshimchaXarajat.objects.filter(
                id=request.POST.get('xarajat_id'), company=request.company, mahsulot=product,
            ).delete()
            recompute_tannarx(product)
            messages.success(request, "Qo'shimcha xarajat o'chirildi.")
            return redirect('warehouse_product_edit', product_id=product.id)

        if action == 'add_retsept_row':
            komponent = get_object_or_404(Mahsulot, id=request.POST.get('komponent'), company=request.company)
            try:
                norma_miqdor = float(request.POST.get('norma_miqdor') or 0)
            except ValueError:
                norma_miqdor = 0
            ok, err = add_retsept_row(request.company, product, komponent, norma_miqdor)
            if ok:
                messages.success(request, "Retsept qatori saqlandi.")
            else:
                messages.error(request, err)
            return redirect('warehouse_product_edit', product_id=product.id)

        if action == 'delete_retsept_row':
            delete_retsept_row(request.company, product, request.POST.get('row_id'))
            messages.success(request, "Retsept qatori o'chirildi.")
            return redirect('warehouse_product_edit', product_id=product.id)

        if not product.rasmi and not request.FILES.get('rasmi'):
            messages.error(request, "Rasm biriktirish majburiy.")
            return redirect('warehouse_product_edit', product_id=product.id)

        # Miqdor — faqat mahsulot birinchi marta yaratilganda kiritiladi.
        # Undan keyin faqat "Kirim-chiqim" sahifasi orqali (tizim, StockHistory
        # bilan) o'zgaradi — bu yerdan qo'lda tahrirlash imkoni yo'q.
        product.nomi = request.POST.get('nomi', '').strip()
        product.min_miqdori = float(request.POST.get('min_miqdori') or 10)
        product.turi = get_object_or_404(MahsulotTuri, id=request.POST.get('turi'))
        product.ombor_turi = request.POST.get('ombor_turi', product.ombor_turi)
        if request.FILES.get('rasmi'):
            product.rasmi = request.FILES['rasmi']
        recompute_needed = product.ombor_turi == 'yarim_tayyor'
        if recompute_needed:
            product.ishlab_chiqarish_narxi = request.POST.get('ishlab_chiqarish_narxi') or 0
            product.amortizatsiya_foizi = request.POST.get('amortizatsiya_foizi') or 0
        product.save()
        if recompute_needed:
            recompute_tannarx(product)

        messages.success(request, "Ombor mahsuloti saqlandi.")
        return redirect('warehouse_products')

    context = {
        'turs': MahsulotTuri.objects.all().order_by('nomi'),
        'product': product,
        'warehouse_only': _is_warehouse_operator(request),
        'ombor_turi_choices': Mahsulot.OMBOR_TURI_CHOICES,
        'xarajatlar': product.qoshimcha_xarajatlar.all(),
    }
    if product.ombor_turi == 'yarim_tayyor':
        context['retsept_rows'] = MahsulotRetsept.objects.filter(
            company=request.company, mahsulot=product
        ).select_related('komponent')
        context['retsept_komponentlar'] = Mahsulot.objects.filter(
            company=request.company, warehouse_type='semi_finished'
        ).exclude(id=product.id).order_by('nomi')
    return render(request, 'warehouse_product_form.html', context)


@login_required(login_url='login')
def warehouse_movements(request):
    if not _warehouse_guard(request):
        return redirect('main')

    products = _warehouse_product_queryset(request).order_by('nomi')

    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        def _fail(error_text):
            if is_ajax:
                return JsonResponse({'ok': False, 'error': error_text}, status=400)
            messages.error(request, error_text)
            return redirect('warehouse_movements')

        movement_type = request.POST.get('movement_type')
        qty = float(request.POST.get('qty') or 0)
        incoming_price = None

        if qty <= 0:
            return _fail("Miqdor 0 dan katta bo'lishi kerak.")
        if movement_type != 'in':
            return _fail("Omborda faqat kirim kiritiladi. Kamaytirish ishlab chiqaruvchi so'rovlari orqali yuritiladi.")
        if movement_type == 'in':
            try:
                incoming_price = Decimal((request.POST.get('price') or '0').replace(',', '.'))
            except (InvalidOperation, AttributeError):
                incoming_price = Decimal('0')
            if incoming_price < 0:
                return _fail("Kirim narxi manfiy bo'lishi mumkin emas.")

        with transaction.atomic():
            product_qs = Mahsulot.objects.select_for_update().select_related('turi').filter(company=request.company)
            if _is_warehouse_operator(request):
                product_qs = product_qs.filter(warehouse_type='semi_finished')
            product = get_object_or_404(product_qs, id=request.POST.get('mahsulot'))
            old_qty = product.miqdori
            new_qty = old_qty + qty
            # O'rtacha og'irlikdagi tannarx (weighted average cost) — kirim
            # narxi eskisi ustidan yozilmaydi, mavjud qoldiq bilan birga
            # o'rtacha hisoblanadi. Shu bilan ishlab chiqarish/BOM hisob-kitobi
            # har doim o'sha paytdagi haqiqiy o'rtacha tannarxdan foydalanadi.
            old_baza = Decimal(str(product.baza_tannarx or 0))
            if new_qty > 0:
                weighted_baza = (Decimal(str(old_qty)) * old_baza + Decimal(str(qty)) * incoming_price) / Decimal(str(new_qty))
            else:
                weighted_baza = incoming_price
            product.miqdori = new_qty
            product.baza_tannarx = weighted_baza
            event_type = 'ADD'
            delta = qty
            action_text = "Kirim"
            update_fields = ['miqdori', 'baza_tannarx']
            product.save(update_fields=update_fields)
            recompute_tannarx(product)

            ombor_id = request.POST.get('ombor_id')
            if ombor_id and product.warehouse_type == 'semi_finished':
                ombor = Ombor.objects.filter(id=ombor_id, company=request.company).first()
                if ombor:
                    add_ombor_stock(ombor, product, qty)
            StockHistory.objects.create(
                actor_user=request.user,
                company=request.company,
                mahsulot=product,
                event_type=event_type,
                old_qty=old_qty,
                new_qty=product.miqdori,
                delta=delta,
            )
        success_text = f"{action_text} yozildi: {product.nomi} {qty:g} {product.turi.nomi}."
        if is_ajax:
            return JsonResponse({
                'ok': True, 'message': success_text,
                'product': {
                    'id': product.id, 'tannarx': float(product.tannarx), 'miqdori': float(product.miqdori),
                },
                'history': {
                    'sana': timezone.localtime(timezone.now()).strftime('%d.%m.%Y %H:%M'),
                    'mahsulot': product.nomi, 'tur': 'Kirim',
                    'delta': float(delta), 'yangi_qoldiq': float(product.miqdori),
                },
            })
        messages.success(request, success_text)
        return redirect('warehouse_movements')

    recent_history = StockHistory.objects.filter(company=request.company).select_related('mahsulot', 'actor_user')
    if _is_warehouse_operator(request):
        recent_history = recent_history.filter(mahsulot__warehouse_type='semi_finished')
    recent_history = recent_history[:15]
    return render(request, 'warehouse_movements.html', {
        'products': products,
        'recent_history': recent_history,
        'omborlar': Ombor.objects.filter(company=request.company).order_by('nomi'),
    })


@login_required(login_url='login')
def material_request_qr_image(request, kod):
    """Material so'rovi uchun QR PNG rasm — chop etib jismoniy paketga
    yopishtirish uchun (masalan omborchi xom ashyoni berayotganda). Ichki/
    autentifikatsiyalangan endpoint, public emas — xuddi `xodim_badge_image`
    kabi, faqat shu firma xodimlariga ochiq."""
    import qrcode
    from io import BytesIO
    from django.http import HttpResponse, Http404

    material_request = ProductionMaterialRequest.objects.filter(kod=kod, company=request.company).first()
    if not material_request:
        raise Http404("So'rov topilmadi")

    img = qrcode.make(str(material_request.kod))
    buf = BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')


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
        'omborlar': Ombor.objects.filter(company=request.company).order_by('nomi'),
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

            ombor_id = request.POST.get('ombor_id')
            if ombor_id:
                ombor = Ombor.objects.filter(id=ombor_id, company=request.company).first()
                if ombor:
                    ok, result = deduct_ombor_stock(ombor, material, material_request.qty)
                    if not ok:
                        messages.error(request, result)
                        return redirect('warehouse_requests')
                    material_request.ombor = ombor

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
        material_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'ombor'])
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


@login_required(login_url='login')
@role_required('ega')
def ombor_list_page(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'generate_agent_token':
            request.company.desktop_agent_token = uuid4().hex
            request.company.save(update_fields=['desktop_agent_token'])
            messages.success(request, "Desktop Agent token yaratildi.")
            return redirect('ombor_list')

        nomi = (request.POST.get('nomi') or '').strip()
        manzil = (request.POST.get('manzil') or '').strip()
        latitude = (request.POST.get('latitude') or '').strip()
        longitude = (request.POST.get('longitude') or '').strip()
        if not nomi:
            messages.error(request, "Ombor nomi kiritilishi shart.")
        else:
            try:
                lat_val = float(latitude) if latitude else None
                lng_val = float(longitude) if longitude else None
            except ValueError:
                lat_val = lng_val = None
            Ombor.objects.create(
                company=request.company, nomi=nomi, manzil=manzil,
                latitude=lat_val, longitude=lng_val,
            )
            messages.success(request, "Ombor qo'shildi.")
            _send_ws_notification(
                request.company.subdomain, "Ombor qo'shildi", f"'{nomi}' ombori qo'shildi.",
                type='info', event='ombor_changed',
            )
        return redirect('ombor_list')

    omborlar = Ombor.objects.filter(company=request.company).prefetch_related('zaxiralar__mahsulot').order_by('nomi')
    return render(request, 'ombor_list.html', {
        'omborlar': omborlar,
        'agent_token': request.company.desktop_agent_token,
    })
