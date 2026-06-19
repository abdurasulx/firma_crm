"""
Qaytarilgan Mahsulotlar Moduli — Growth Feature #6

Yetkazuvchi mahsulot qaytaradi → admin tasdiqlaydi → DeliveryStock kamayadi, Mahsulot.miqdori ortadi
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from .models import (
    qaytarilgan_mahsulotlar, Mahsulot, YetkazibBeruvchi,
    AmalLog, DeliveryStock
)


# ─── Yetkazuvchi: Qaytarish So'rovi Yuborish ─────────────────────────────────
@login_required(login_url='login')
def qaytarish_view(request):
    """Yetkazuvchi o'zida qolgan mahsulotni qaytarish so'rovini yuboradi."""
    if request.user.type != 'yetkazib_beruvchi':
        return redirect('main')

    try:
        yb = YetkazibBeruvchi.objects.get(user=request.user, company=request.company)
    except YetkazibBeruvchi.DoesNotExist:
        return redirect('main')

    # Faqat yetkazuvchida mavjud mahsulotlar (DeliveryStock orqali)
    stocks = DeliveryStock.objects.filter(
        company=request.company,
        yetkazib_beruvchi=yb, 
        qty__gt=0
    ).select_related('mahsulot')

    if request.method == 'POST':
        mahsulot_id = request.POST.get('mahsulot')
        miqdor_str  = request.POST.get('miqdor', '').replace(',', '.')

        try:
            mahsulot = Mahsulot.objects.get(id=mahsulot_id, company=request.company)
            miqdor   = float(miqdor_str)
        except (Mahsulot.DoesNotExist, ValueError):
            messages.error(request, "Noto'g'ri mahsulot yoki miqdor.")
            return redirect('qaytarish')

        if miqdor <= 0:
            messages.error(request, "Miqdor 0 dan katta bo'lishi kerak.")
            return redirect('qaytarish')

        # Mavjuddagi stokni tekshirish
        try:
            ds = DeliveryStock.objects.get(yetkazib_beruvchi=yb, mahsulot=mahsulot, company=request.company)
            if miqdor > ds.qty:
                messages.error(request, f"Sizda faqat {ds.qty} ta {mahsulot.nomi} bor.")
                return redirect('qaytarish')
        except DeliveryStock.DoesNotExist:
            messages.error(request, "Bu mahsulot sizda mavjud emas.")
            return redirect('qaytarish')

        qaytarilgan_mahsulotlar.objects.create(
            company=request.company,
            mahsulot=mahsulot,
            miqdor=miqdor,
            status=qaytarilgan_mahsulotlar.STATUS_PENDING,
        )

        AmalLog.objects.create(
            user=request.user,
            company=request.company,
            amal_shifri=f"qaytarish_sorov|{mahsulot.nomi}|{miqdor}|{yb.tuliq_ismi}"
        )

        messages.success(request, f"{mahsulot.nomi} uchun qaytarish so'rovi yuborildi.")
        return redirect('qaytarish')

    context = {
        'stocks': stocks,
    }
    return render(request, 'qaytarish.html', context)


# ─── Admin: Barcha Qaytarish So'rovlari Ro'yxati ─────────────────────────────
@login_required(login_url='login')
def qaytarishlar_view(request):
    """Admin uchun barcha qaytarish so'rovlari ro'yxati."""
    if request.user.type != 'ega':
        return redirect('main')

    pending = qaytarilgan_mahsulotlar.objects.filter(
        company=request.company, status=qaytarilgan_mahsulotlar.STATUS_PENDING
    ).select_related('mahsulot').order_by('-sana')
    done = qaytarilgan_mahsulotlar.objects.filter(
        company=request.company, status__in=[qaytarilgan_mahsulotlar.STATUS_APPROVED, qaytarilgan_mahsulotlar.STATUS_REJECTED]
    ).select_related('mahsulot').order_by('-sana')[:50]

    context = {
        'pending': pending,
        'done': done,
        'pending_count': pending.count(),
    }
    return render(request, 'qaytarishlar.html', context)


# ─── Admin: Qaytarishni Tasdiqlash ───────────────────────────────────────────
@login_required(login_url='login')
def qaytarish_tasdiq(request, qaytarish_id):
    """Admin qaytarishni tasdiqlaydi: mahsulot omborga qaytadi, so'rov yopiladi."""
    if request.user.type != 'ega':
        return redirect('main')

    q = get_object_or_404(qaytarilgan_mahsulotlar, id=qaytarish_id,
                          status=qaytarilgan_mahsulotlar.STATUS_PENDING, company=request.company)

    if request.method == 'POST':
        with transaction.atomic():
            q_locked = qaytarilgan_mahsulotlar.objects.select_for_update().get(pk=q.pk)
            if q_locked.status != qaytarilgan_mahsulotlar.STATUS_PENDING:
                messages.warning(request, "Bu qaytarish allaqachon ko'rib chiqilgan.")
                return redirect('qaytarishlar')

            m = Mahsulot.objects.select_for_update().get(pk=q_locked.mahsulot.pk)
            m.miqdori = (m.miqdori or 0) + q_locked.miqdor
            m.save(update_fields=['miqdori'])

            q_locked.status = qaytarilgan_mahsulotlar.STATUS_APPROVED
            q_locked.yq = True  # backwards compat
            q_locked.save(update_fields=['status', 'yq'])

            AmalLog.objects.create(
                user=request.user,
                company=request.company,
                amal_shifri=f"qaytarish_tasdiq|{m.nomi}|{q_locked.miqdor}"
            )

        messages.success(request, f"{m.nomi} uchun {q_locked.miqdor} {m.turi} qaytarish tasdiqlandi.")

    return redirect('qaytarishlar')


# ─── Admin: Qaytarishni Rad Etish ────────────────────────────────────────────
@login_required(login_url='login')
def qaytarish_rad(request, qaytarish_id):
    """Admin qaytarishni rad etadi — hech narsa o'zgarmaydi, so'rov yopiladi."""
    if request.user.type != 'ega':
        return redirect('main')

    q = get_object_or_404(qaytarilgan_mahsulotlar, id=qaytarish_id,
                          status=qaytarilgan_mahsulotlar.STATUS_PENDING, company=request.company)

    if request.method == 'POST':
        AmalLog.objects.create(
            user=request.user,
            company=request.company,
            amal_shifri=f"qaytarish_rad|{q.mahsulot.nomi}|{q.miqdor}"
        )
        q.status = qaytarilgan_mahsulotlar.STATUS_REJECTED
        q.yq = True  # backwards compat
        q.save(update_fields=['status', 'yq'])
        messages.warning(request, f"{q.mahsulot.nomi} qaytarishi rad etildi.")

    return redirect('qaytarishlar')
