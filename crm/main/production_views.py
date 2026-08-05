from io import BytesIO

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Mahsulot, Serial, ProductionTask, MahsulotRetsept, Pazanda
from .services import task_service


def _warehouse_guard(request):
    return request.user.type in ('ega', 'omborchi')


@login_required(login_url='login')
def serial_list_page(request, mahsulot_id):
    if not _warehouse_guard(request):
        return redirect('main')

    mahsulot = get_object_or_404(Mahsulot, id=mahsulot_id, company=request.company)
    seriallar = (
        Serial.objects.filter(company=request.company, mahsulot=mahsulot)
        .select_related('batch')
        .order_by('-created_at')[:300]
    )
    return render(request, 'serial_list.html', {
        'mahsulot': mahsulot,
        'seriallar': seriallar,
        'base_domain': settings.BASE_DOMAIN,
    })


@login_required(login_url='login')
def vazifalar_page(request):
    """"Vazifalar paneli" (103-qadam) — Desktop Agent ishlatuvchi
    firmalarda "Miqdor Qo'shish"/"Material So'rash" o'rnini bosadi: ega
    bu yerda "bugunga 100 dona Burger" kabi vazifa yaratadi (faqat
    retsepti/BOM'i bor mahsulotlar uchun — dropdown shu bilan
    cheklangan), istalgan ishlab chiqaruvchi uni agentda o'ziga oladi."""
    if request.user.type != 'ega':
        return redirect('main')
    if not request.company.custom_desktop_agent_stations:
        messages.error(request, "Bu funksiya Desktop Agent stansiyasi sotib olingan firmalar uchun mo'ljallangan.")
        return redirect('main')

    if request.method == 'POST':
        mahsulot = get_object_or_404(
            Mahsulot, id=request.POST.get('mahsulot'), company=request.company,
            warehouse_type='finished', mahsulot_turi='ishlab_chiqariladigan',
        )
        try:
            rejalashtirilgan_miqdor = float(request.POST.get('rejalashtirilgan_miqdor'))
        except (TypeError, ValueError):
            messages.error(request, "Miqdor noto'g'ri kiritildi.")
            return redirect('vazifalar')

        sana = request.POST.get('sana') or timezone.localdate()
        qadoq_hajmi = request.POST.get('qadoq_hajmi') or None
        try:
            qadoq_hajmi = int(qadoq_hajmi) if qadoq_hajmi else None
        except ValueError:
            qadoq_hajmi = None
        force_uneven_qadoq = request.POST.get('force_uneven_qadoq') == '1'
        task, err, needs_confirm = task_service.create_production_task(
            request.company, mahsulot, rejalashtirilgan_miqdor, sana, request.user,
            qadoq_hajmi=qadoq_hajmi, force_uneven_qadoq=force_uneven_qadoq,
        )
        if err:
            if needs_confirm:
                messages.warning(request, err + " (\"Bo'linmasa ham davom et\" belgisini yoqib qayta yuboring.)")
            else:
                messages.error(request, err)
        else:
            messages.success(request, f"Vazifa yaratildi: {mahsulot.nomi} — {rejalashtirilgan_miqdor:g} dona.")
        return redirect('vazifalar')

    # Faqat BOM (retsept) kiritilgan mahsulotlar tanlanishi mumkin —
    # foydalanuvchi bilan kelishilgan qat'iy qoida: retseptsiz vazifa
    # yaratilmasin.
    bom_mahsulot_ids = MahsulotRetsept.objects.filter(
        company=request.company,
    ).values_list('mahsulot_id', flat=True).distinct()
    mahsulotlar = Mahsulot.objects.filter(
        company=request.company, id__in=bom_mahsulot_ids,
        warehouse_type='finished', mahsulot_turi='ishlab_chiqariladigan',
    ).order_by('nomi')

    # Faqat vazifa BOR kunlar ("active days") — sana filtri shu ro'yxatdan
    # tanlanadi, xodim bo'sh kunni qidirib vaqt yo'qotmasin.
    active_days = list(
        ProductionTask.objects.filter(company=request.company)
        .order_by('-sana').values_list('sana', flat=True).distinct()
    )

    pazanda_list = Pazanda.objects.filter(
        company=request.company, olingan_vazifalar__isnull=False,
    ).select_related('user').distinct().order_by('user__tuliq_ismi')

    tasks = ProductionTask.objects.filter(
        company=request.company,
    ).select_related('mahsulot', 'pazanda__user').order_by('-sana', '-created_at')

    filter_mode = request.GET.get('mode', 'day')
    sana_str = request.GET.get('sana')
    from_str = request.GET.get('from')
    to_str = request.GET.get('to')
    pazanda_id = request.GET.get('pazanda')

    if filter_mode == 'range' and (from_str or to_str):
        if from_str:
            tasks = tasks.filter(sana__gte=from_str)
        if to_str:
            tasks = tasks.filter(sana__lte=to_str)
    elif sana_str:
        tasks = tasks.filter(sana=sana_str)

    if pazanda_id:
        tasks = tasks.filter(pazanda_id=pazanda_id)

    tasks = tasks[:200]

    return render(request, 'vazifalar.html', {
        'mahsulotlar': mahsulotlar,
        'tasks': tasks,
        'today': timezone.localdate(),
        'active_days': active_days,
        'pazanda_list': pazanda_list,
        'filter_mode': filter_mode,
        'sel_sana': sana_str,
        'sel_from': from_str,
        'sel_to': to_str,
        'sel_pazanda': pazanda_id,
    })


@login_required(login_url='login')
def pz_create_task(request):
    """Ishlab chiqaruvchi o'zi uchun vazifa yaratadi (110-qadam) — mahsulot
    tanlab, sonini kiritib, "Vazifa yaratish"ni bosadi. `ega`ning
    "Vazifalar" panelidan farqli — bu yerda vazifa darhol o'ziga
    (yaratuvchiga) band qilingan holda tug'iladi, alohida "band qilish"
    bosqichi kerak emas."""
    if request.user.type not in ('pazanda', 'ishlab_chiqaruvchi'):
        return redirect('main')
    if not request.company.custom_desktop_agent_stations:
        return redirect('main')
    if request.method != 'POST':
        return redirect('main')

    try:
        pazanda = Pazanda.objects.get(user=request.user, company=request.company)
    except Pazanda.DoesNotExist:
        messages.error(request, "Profil topilmadi. Administrator bilan bog'laning.")
        return redirect('main')

    mahsulot = get_object_or_404(
        Mahsulot, id=request.POST.get('mahsulot'), company=request.company,
        warehouse_type='finished', mahsulot_turi='ishlab_chiqariladigan',
    )
    try:
        rejalashtirilgan_miqdor = float(request.POST.get('rejalashtirilgan_miqdor'))
    except (TypeError, ValueError):
        messages.error(request, "Miqdor noto'g'ri kiritildi.")
        return redirect('main')

    qadoq_hajmi = request.POST.get('qadoq_hajmi') or None
    try:
        qadoq_hajmi = int(qadoq_hajmi) if qadoq_hajmi else None
    except ValueError:
        qadoq_hajmi = None
    force_uneven_qadoq = request.POST.get('force_uneven_qadoq') == '1'

    task, err, needs_confirm = task_service.create_production_task(
        request.company, mahsulot, rejalashtirilgan_miqdor, timezone.localdate(),
        request.user, pazanda=pazanda, qadoq_hajmi=qadoq_hajmi, force_uneven_qadoq=force_uneven_qadoq,
    )
    if err:
        if needs_confirm:
            messages.warning(request, err + " (\"Bo'linmasa ham davom et\" belgisini yoqib qayta yuboring.)")
        else:
            messages.error(request, err)
    else:
        messages.success(
            request,
            f"Vazifa yaratildi: {mahsulot.nomi} — {rejalashtirilgan_miqdor:g} dona. "
            "Endi Desktop Agent'da badge'ingizni skanerlab xom ashyoni tortib oling.",
        )
    return redirect('main')


@login_required(login_url='login')
def pz_finish_task(request, task_id):
    """"Tugatish" tugmasi (110-qadam) — hali reja to'liq bajarilmagan
    ('producing') vazifani erta yopadi. Ishlab chiqarilmagan dona uchun
    shtraf `task_service.finish_production_task_service` ichida
    hisoblanadi."""
    if request.user.type not in ('pazanda', 'ishlab_chiqaruvchi'):
        return redirect('main')
    if request.method != 'POST':
        return redirect('main')

    try:
        pazanda = Pazanda.objects.get(user=request.user, company=request.company)
    except Pazanda.DoesNotExist:
        return redirect('main')

    task = get_object_or_404(
        ProductionTask, id=task_id, company=request.company, pazanda=pazanda, status='producing',
    )
    mq = task.miqdor_qoshishlar.first()
    if not mq or not mq.labels_printed:
        # Yorliqlar hali Desktop Agent'da chop etilmagan — bu bosqichda
        # "Tugatish" bosish real hech qanday foyda bermaydi (fizik
        # jarayon hali boshlanmagan ham), faqat bexosdan 0 dona uchun
        # shtraf yozib qo'yish xavfi bor (real holatda sodir bo'lgan).
        messages.error(
            request,
            "Yorliqlar hali chop etilmagan — avval Desktop Agent'da badge'ingizni skanerlang.",
        )
        return redirect('main')
    mq = task_service.finish_production_task_service(task, actor=request.user)
    if mq.miqdor < task.rejalashtirilgan_miqdor:
        messages.warning(
            request,
            f"Vazifa erta yopildi — {mq.miqdor:g}/{task.rejalashtirilgan_miqdor:g} dona tayyor bo'ldi, "
            f"qolgani uchun shtraf qo'llanildi.",
        )
    else:
        messages.success(request, f"Vazifa yopildi — {mq.miqdor:g} dona tasdiqlandi.")
    return redirect('main')


@login_required(login_url='login')
def pz_confirm_task_finished(request, task_id):
    """"Ish bitdi" tugmasi (159-qadam) — xom ashyo Desktop Agent'da
    tarozida allaqachon to'liq tortib bo'lingan ('materials_ready')
    vazifani ishlab chiqarishga o'tkazadi: Serial/QR kodlar shu yerda
    generatsiya qilinadi, lekin jismoniy chop etish veb sahifada
    SODIR BO'LMAYDI — pazanda Desktop Agent'da badge'ini keyingi safar
    skanerlaganda, stansiya printeri orqali avtomatik chop etiladi."""
    if request.user.type not in ('pazanda', 'ishlab_chiqaruvchi'):
        return redirect('main')
    if request.method != 'POST':
        return redirect('main')

    try:
        pazanda = Pazanda.objects.get(user=request.user, company=request.company)
    except Pazanda.DoesNotExist:
        return redirect('main')

    mq, err = task_service.confirm_task_finished_materials(task_id, pazanda, request.company)
    if err:
        messages.error(request, err)
    else:
        messages.success(
            request,
            "Ish bitdi qayd etildi — endi Desktop Agent'da badge'ingizni skanerlang, "
            "QR-yorliqlar avtomatik chop etiladi.",
        )
    return redirect('main')


@login_required(login_url='login')
def vazifa_qr_image(request, kod):
    """Vazifa QR PNG rasm — chop etib jismoniy taxtaga yopishtirish uchun.
    `xodim_badge_image`/`material_request_qr_image` bilan bir xil uslub:
    ichki/autentifikatsiyalangan endpoint, public emas."""
    task = ProductionTask.objects.filter(kod=kod, company=request.company).first()
    if not task:
        raise Http404("Vazifa topilmadi")

    img = qrcode.make(str(task.kod))
    buf = BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')
