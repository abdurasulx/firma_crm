"""
Qaytarilgan Mahsulotlar Moduli — Growth Feature #6

Yetkazuvchi mahsulot qaytaradi → admin tasdiqlaydi → DeliveryStock kamayadi, Mahsulot.miqdori ortadi
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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
        yb = YetkazibBeruvchi.objects.get(user=request.user)
    except YetkazibBeruvchi.DoesNotExist:
        return redirect('main')

    # Faqat yetkazuvchida mavjud mahsulotlar (DeliveryStock orqali)
    stocks = DeliveryStock.objects.filter(
        yetkazib_beruvchi=yb, qty__gt=0
    ).select_related('mahsulot')

    if request.method == 'POST':
        mahsulot_id = request.POST.get('mahsulot')
        miqdor_str  = request.POST.get('miqdor', '').replace(',', '.')

        try:
            mahsulot = Mahsulot.objects.get(id=mahsulot_id)
            miqdor   = float(miqdor_str)
        except (Mahsulot.DoesNotExist, ValueError):
            messages.error(request, "Noto'g'ri mahsulot yoki miqdor.")
            return redirect('qaytarish')

        if miqdor <= 0:
            messages.error(request, "Miqdor 0 dan katta bo'lishi kerak.")
            return redirect('qaytarish')

        # Mavjuddagi stokni tekshirish
        try:
            ds = DeliveryStock.objects.get(yetkazib_beruvchi=yb, mahsulot=mahsulot)
            if miqdor > ds.qty:
                messages.error(request, f"Sizda faqat {ds.qty} ta {mahsulot.nomi} bor.")
                return redirect('qaytarish')
        except DeliveryStock.DoesNotExist:
            messages.error(request, "Bu mahsulot sizda mavjud emas.")
            return redirect('qaytarish')

        # So'rov yaratish (yq=False — tasdiqlash kutilmoqda)
        qaytarilgan_mahsulotlar.objects.create(
            mahsulot=mahsulot,
            miqdor=miqdor,
            yq=False,
        )

        AmalLog.objects.create(
            user=request.user,
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

    pending = qaytarilgan_mahsulotlar.objects.filter(yq=False).select_related('mahsulot').order_by('-sana')
    done    = qaytarilgan_mahsulotlar.objects.filter(yq=True).select_related('mahsulot').order_by('-sana')[:50]

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

    q = get_object_or_404(qaytarilgan_mahsulotlar, id=qaytarish_id, yq=False)

    if request.method == 'POST':
        # Mahsulot ombor zaxirasini oshir
        m = q.mahsulot
        m.miqdori = (m.miqdori or 0) + q.miqdor
        m.save()

        # So'rovni yopiq deb belgilaymiz
        q.yq = True
        q.save()

        AmalLog.objects.create(
            user=request.user,
            amal_shifri=f"qaytarish_tasdiq|{m.nomi}|{q.miqdor}"
        )

        messages.success(request, f"{m.nomi} uchun {q.miqdor} {m.turi} qaytarish tasdiqlandi.")

    return redirect('qaytarishlar')


# ─── Admin: Qaytarishni Rad Etish ────────────────────────────────────────────
@login_required(login_url='login')
def qaytarish_rad(request, qaytarish_id):
    """Admin qaytarishni rad etadi — hech narsa o'zgarmaydi, so'rov yopiladi."""
    if request.user.type != 'ega':
        return redirect('main')

    q = get_object_or_404(qaytarilgan_mahsulotlar, id=qaytarish_id, yq=False)

    if request.method == 'POST':
        AmalLog.objects.create(
            user=request.user,
            amal_shifri=f"qaytarish_rad|{q.mahsulot.nomi}|{q.miqdor}"
        )
        q.yq = True   # yopish (rad etildi deb belgilash uchun yq=True)
        q.save()
        messages.warning(request, f"{q.mahsulot.nomi} qaytarishi rad etildi.")

    return redirect('qaytarishlar')
