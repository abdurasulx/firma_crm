"""
Qaytarilgan Mahsulotlar Moduli — Growth Feature #6

Yetkazuvchi mahsulot qaytaradi → admin tasdiqlaydi → DeliveryStock kamayadi, Mahsulot.miqdori ortadi
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from .models import (
    qaytarilgan_mahsulotlar, Mahsulot, YetkazibBeruvchi,
    AmalLog, DeliveryStock, User, Company,
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
            yetkazib_beruvchi=yb,
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

    # Javobgar (qarz yoziladigan) sifatida tanlash mumkin bo'lgan xodimlar —
    # savdogar va yetkazib beruvchi turlari.
    javobgar_nomzodlar = User.objects.filter(
        company=request.company, type__in=['savdogar', 'yetkazib_beruvchi'],
    ).order_by('tuliq_ismi')
    # "Qayta ishlash" uchun — qaysi xom ashyoga aylantirish mumkin.
    komponent_nomzodlar = Mahsulot.objects.filter(
        company=request.company, warehouse_type='semi_finished',
    ).order_by('nomi')

    context = {
        'pending': pending,
        'done': done,
        'pending_count': pending.count(),
        'javobgar_nomzodlar': javobgar_nomzodlar,
        'komponent_nomzodlar': komponent_nomzodlar,
        'qaytarish_javobgarligi_choices': Company.QAYTARISH_JAVOBGARLIGI_CHOICES,
        'company_qaytarish_javobgarligi': request.company.qaytarish_javobgarligi,
    }
    return render(request, 'qaytarishlar.html', context)


# ─── Admin: Qaytarish standart javobgarlik sozlamasi ─────────────────────────
@login_required(login_url='login')
def qaytarish_sozlash(request):
    """Firma bo'yicha standart javobgar rolni belgilaydi — tasdiqlash
    paytida shu tur oldindan tanlab qo'yiladi (majburiy emas, ega har
    safar o'zgartirishi mumkin)."""
    if request.user.type != 'ega' or request.method != 'POST':
        return redirect('qaytarishlar')

    value = request.POST.get('qaytarish_javobgarligi')
    if value in dict(Company.QAYTARISH_JAVOBGARLIGI_CHOICES):
        request.company.qaytarish_javobgarligi = value
        request.company.save(update_fields=['qaytarish_javobgarligi'])
        messages.success(request, "Qaytarish sozlamasi saqlandi.")
    return redirect('qaytarishlar')


# ─── Admin: Qaytarishni Hal Qilish (Utilizatsiya / Qayta ishlash) ────────────
@login_required(login_url='login')
def qaytarish_tasdiq(request, qaytarish_id):
    """Admin qaytarishni ikki xil yo'l bilan hal qiladi:
    - **Utilizatsiya**: mahsulot ombor qoldig'iga QO'SHILMAYDI (chiqim,
      zarar sifatida qayd etiladi).
    - **Qayta ishlash**: mahsulot ombordagi TAYYOR qoldiqqa emas, ega
      tanlagan XOM ASHYOga (masalan "non" -> "un") belgilangan miqdorda
      qo'shiladi.
    Ikkalasida ham, agar javobgar (savdogar/yetkazib beruvchi) tanlansa,
    mahsulot tannarxi asosida unga qarz yoziladi (`qarz_summasi`) —
    hisob-kitob/to'lov oqimi hozircha yo'q, faqat ko'rsatish uchun."""
    if request.user.type != 'ega':
        return redirect('main')

    q = get_object_or_404(qaytarilgan_mahsulotlar, id=qaytarish_id,
                          status=qaytarilgan_mahsulotlar.STATUS_PENDING, company=request.company)

    if request.method == 'POST':
        harakat_turi = request.POST.get('harakat_turi')
        if harakat_turi not in dict(qaytarilgan_mahsulotlar.HARAKAT_TURI_CHOICES):
            messages.error(request, "Harakat turini (Utilizatsiya yoki Qayta ishlash) tanlang.")
            return redirect('qaytarishlar')

        javobgar = None
        javobgar_id = request.POST.get('javobgar_id')
        if javobgar_id:
            javobgar = User.objects.filter(id=javobgar_id, company=request.company).first()

        komponent = None
        komponent_miqdor = None
        if harakat_turi == 'qayta_ishlash':
            komponent_id = request.POST.get('komponent_id')
            komponent = Mahsulot.objects.filter(
                id=komponent_id, company=request.company, warehouse_type='semi_finished',
            ).first()
            if not komponent:
                messages.error(request, "Qayta ishlash uchun xom ashyoni tanlang.")
                return redirect('qaytarishlar')
            try:
                komponent_miqdor = float(request.POST.get('komponent_miqdor') or 0)
            except ValueError:
                komponent_miqdor = 0
            if komponent_miqdor <= 0:
                messages.error(request, "Qayta ishlangan xom ashyo miqdori 0 dan katta bo'lishi kerak.")
                return redirect('qaytarishlar')

        with transaction.atomic():
            q_locked = qaytarilgan_mahsulotlar.objects.select_for_update().get(pk=q.pk)
            if q_locked.status != qaytarilgan_mahsulotlar.STATUS_PENDING:
                messages.warning(request, "Bu qaytarish allaqachon ko'rib chiqilgan.")
                return redirect('qaytarishlar')

            m = Mahsulot.objects.select_for_update().get(pk=q_locked.mahsulot.pk)

            if harakat_turi == 'utilizatsiya':
                # Ombor qoldig'iga HECH NARSA qo'shilmaydi — mahsulot
                # butunlay chiqim (zarar) hisoblanadi.
                pass
            else:
                komponent = Mahsulot.objects.select_for_update().get(pk=komponent.pk)
                komponent.miqdori = (komponent.miqdori or 0) + komponent_miqdor
                komponent.save(update_fields=['miqdori'])

            qarz_summasi = Decimal('0')
            if javobgar:
                qarz_summasi = Decimal(str(m.tannarx or 0)) * Decimal(str(q_locked.miqdor))

            q_locked.status = qaytarilgan_mahsulotlar.STATUS_APPROVED
            q_locked.harakat_turi = harakat_turi
            q_locked.javobgar = javobgar
            q_locked.qarz_summasi = qarz_summasi
            q_locked.komponent = komponent if harakat_turi == 'qayta_ishlash' else None
            q_locked.komponent_miqdor = komponent_miqdor if harakat_turi == 'qayta_ishlash' else None
            q_locked.yq = True  # backwards compat
            q_locked.save(update_fields=[
                'status', 'harakat_turi', 'javobgar', 'qarz_summasi',
                'komponent', 'komponent_miqdor', 'yq',
            ])

            AmalLog.objects.create(
                user=request.user,
                company=request.company,
                amal_shifri=f"qaytarish_{harakat_turi}|{m.nomi}|{q_locked.miqdor}|javobgar={javobgar.username if javobgar else '-'}|qarz={qarz_summasi:g}"
            )

        if harakat_turi == 'utilizatsiya':
            messages.success(request, f"{m.nomi} ({q_locked.miqdor:g} {m.turi}) utilizatsiya qilindi.")
        else:
            messages.success(
                request,
                f"{m.nomi} ({q_locked.miqdor:g} {m.turi}) qayta ishlandi — "
                f"{komponent.nomi}ga {komponent_miqdor:g} {komponent.turi} qo'shildi.",
            )
        if javobgar and qarz_summasi:
            messages.info(request, f"{javobgar.tuliq_ismi or javobgar.username}ga {qarz_summasi:g} so'm qarz yozildi.")

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
