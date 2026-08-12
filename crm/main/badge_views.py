from io import BytesIO

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import User, XodimBadge, _gen_agent_qr_nonce
from .services.agent_qr_crypto import encrypt_login_payload


@login_required(login_url='login')
def xodim_badge_page(request, user_id=None):
    if user_id and user_id != request.user.id:
        if request.user.type != 'ega':
            return redirect('main')
        target_user = get_object_or_404(User, id=user_id, company=request.company)
    else:
        target_user = request.user

    badge, _ = XodimBadge.objects.get_or_create(
        user=target_user, defaults={'company': request.company},
    )

    xodimlar = None
    if request.user.type == 'ega':
        xodimlar = User.objects.filter(company=request.company).exclude(id=request.user.id).order_by('username')

    return render(request, 'xodim_badge.html', {
        'target_user': target_user,
        'badge': badge,
        'xodimlar': xodimlar,
    })


@login_required(login_url='login')
def xodim_badge_image(request, kod):
    """Xodim badge QR PNG — internal/authenticated, public emas (shaxsni aniqlaydi)."""
    badge = XodimBadge.objects.filter(kod=kod, company=request.company).first()
    if not badge:
        raise Http404("Badge topilmadi")
    if badge.user_id != request.user.id and request.user.type != 'ega':
        raise Http404("Ruxsat yo'q")

    img = qrcode.make(str(badge.kod))
    buf = BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')


@login_required(login_url='login')
def agent_login_qr_image(request, user_id):
    """Desktop Agent stansiyasini shifrlangan QR orqali kiritish uchun
    (145-qadam) — faqat `ega` ko'radi (bu qo'lda login/parolning
    o'rnini bosuvchi maxfiy hisob ma'lumoti, xodimning o'ziga ham
    ko'rsatilmaydi — parolni ko'rsatish bilan bir xil sezgirlik
    darajasida)."""
    if request.user.type != 'ega':
        raise Http404("Ruxsat yo'q")
    target_user = get_object_or_404(User, id=user_id, company=request.company)

    payload = encrypt_login_payload(target_user.id, target_user.agent_qr_nonce)
    qr_text = f"AGENTQR|{request.company.subdomain}|{payload}"

    # Shifrlangan payload (Fernet) ~200 belgigacha bo'lib, oddiy xodim
    # badge (36 belgili UUID)ga qaraganda ANCHA zichroq QR panjarasini
    # talab qiladi — kamera bilan (ayniqsa monitordan) o'qish real
    # sinovda ishonchsiz chiqdi. Yuqori xato-tuzatish darajasi
    # (`ERROR_CORRECT_H`, 30% zaxira) — xiralik/nur aksi/qisman
    # to'siqqa chidamliroq qiladi, kattaroq `box_size` esa har bir
    # katakchani kamera uchun yetarlicha yirik qilib chop etadi.
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=12, border=4)
    qr.add_data(qr_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')


@login_required(login_url='login')
def regenerate_agent_qr(request, user_id):
    """Eski ko'rsatilgan/chop etilgan Desktop Agent QR kodini bekor
    qiladi (nonce yangilanadi) — masalan QR kimgadir ko'rinib qolgan
    bo'lsa yoki xodim ishdan bo'shatilganda."""
    if request.user.type != 'ega' or request.method != 'POST':
        return redirect('main')
    target_user = get_object_or_404(User, id=user_id, company=request.company)
    target_user.agent_qr_nonce = _gen_agent_qr_nonce()
    target_user.save(update_fields=['agent_qr_nonce'])
    messages.success(request, "Eski QR kod bekor qilindi, yangisi generatsiya qilindi.")
    return redirect('profile', username=target_user.username)
