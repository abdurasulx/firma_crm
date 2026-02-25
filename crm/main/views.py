from django.shortcuts import render, get_list_or_404, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages 
from django.utils import timezone
from django.shortcuts import redirect
from .models import HaridorDukon, User, YetkazibBeruvchi, Pazanda, Mahsulot, MahsulotTuri, Savdo, YuklamaSorov, MiqdorQoshish, HaridorDukon, AmalLog
from .functions import mahsulotlar_miqdori, makenewform, yuklama_maker, accptyuk, sotishm, sotuv_new_form ,yetkazuvchi_mahsulot_filter, get_bugungi_savdo_summ, add_spctoint
import datetime as dt



from .services.stock_service import (
    approve_miqdor_qoshish_service, 
    approve_yuklama_sorov_service
)
from .services.auth_service import create_user_service, update_user_service
from .analytics.services import get_dashboard_stats

User = get_user_model()
# Create your views here.
def login(request):
    data={}
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        data['username'] = username
        data['password'] = password
        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            return redirect('main')  # 'main' - asosiy sahifa URL nomi
        else:
            messages.error(request, "Login yoki parol noto'g'ri!")

    return render(request, 'login.html',data)
@login_required(login_url='login')
def main(request):
    payload={}
    user=request.user
    
    if user.type == 'pazanda':
        now = timezone.localtime()
        today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
        today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))
        payload['sorovlar'] = YuklamaSorov.objects.filter(pazanda=Pazanda.objects.get(user=request.user),sana__range=(today_start, today_end)).all()
        payload['zaxira_mahsulotlar']=Mahsulot.objects.all()
        zapros=MiqdorQoshish.objects.filter(pazanda=Pazanda.objects.get(user=request.user),vaqt_sana__range=(today_start, today_end)).all()
        payload['qms']=len(zapros)
        payload['kunlik_miqdorlar'] = zapros
        return render(request, 'pazanda_dashboard.html',payload)
    elif user.type == 'yetkazib_beruvchi':
        if request.method == 'GET':
            yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=request.user).mahsulotlar) or []
            
            payload['yuklamalar'] = yuklamalar
            mahs=Mahsulot.objects.all()
            payload['zaxira_mahsulotlar'] = mahs
            payload['lnmahs']=len(mahs)

            now = timezone.localtime()
            today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
            today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))

            reqyuklama = YuklamaSorov.objects.filter(
                user=YetkazibBeruvchi.objects.get(user=request.user),
                tasdiq=False,
                mode='waiting',
                sana__range=(today_start, today_end)).all()
            # reqyuklama=YuklamaSorov.objects.filter(user=YetkazibBeruvchi.objects.get(user=request.user),tasdiq=False, mode='waiting',sana=dt.date.today() ).all()
            payload['reqyuklama'] = reqyuklama
            savdo=Savdo.objects.filter(yetkazib_beruvchi=YetkazibBeruvchi.objects.get(user=request.user),vaqt_sana__range=(today_start, today_end)).all()
            payload['savdo'] = savdo
            nfs=yetkazuvchi_mahsulot_filter(savdo)
            payload['nfs'] = nfs
            return render(request, 'yetkazuvchi_dashboard.html',payload)
        elif request.method == 'POST':
            if 'yk_id' in request.POST: 
                yk_id=request.POST.get('yk_id')
               
                if 'accept' in yk_id:
                    yk_id=yk_id.replace('accept','')
                    # Refactored to use Service
                    success, message = approve_yuklama_sorov_service(yk_id, request.user)
                    if success:
                        messages.success(request, message)
                    else:
                        messages.error(request, message)

                elif 'reject' in yk_id:
                    yk_id=yk_id.replace('reject','')
                    yk=YuklamaSorov.objects.get(id=yk_id)
                    yk.mode='rejected'
                    yk.tasdiq=True
                    yk.save()
                    # Activity log
                    AmalLog.objects.create(
                        user=request.user,
                        amal_shifri=f"yuklama_rad|{yk.mahsulot.nomi}|{yk.miqdor}"
                    )
                
                return redirect('main')
            yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=request.user).mahsulotlar) or []
            savdo=Savdo.objects.filter(yetkazib_beruvchi=YetkazibBeruvchi.objects.get(user=request.user))
            payload['savdo'] = savdo
            nfs=yetkazuvchi_mahsulot_filter(savdo)
            payload['nfs'] = nfs

            payload['yuklamalar'] = yuklamalar
            now = timezone.localtime()
            today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
            today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))

            reqyuklama = YuklamaSorov.objects.filter(
                user=YetkazibBeruvchi.objects.get(user=request.user),
                tasdiq=False,
                mode='waiting',
                sana__range=(today_start, today_end)).all()
            savdo=Savdo.objects.filter(yetkazib_beruvchi=YetkazibBeruvchi.objects.get(user=request.user),vaqt_sana__range=(today_start, today_end)).all()
            payload['savdo'] = savdo
            # reqyuklama=YuklamaSorov.objects.filter(user=YetkazibBeruvchi.objects.get(user=request.user),tasdiq=False, mode='waiting',sana=dt.date.today() ).all()
            payload['reqyuklama'] = reqyuklama
            mahs=Mahsulot.objects.all()
            payload['zaxira_mahsulotlar'] = mahs
            
            return render(request, 'yetkazuvchi_dashboard.html',payload)
            
    
    hodims = User.objects.exclude(type='ega').order_by('-date_joined')[:6]  # Faqat 6 ta
    mahs = Mahsulot.objects.all().order_by('nomi')[:6]  # Faqat 6 ta
    
    # Jami sonlar
    jami_hodimlar = User.objects.exclude(type='ega').count()
    jami_mahsulotlar = Mahsulot.objects.count()
    
    payload['mahsulotlar'] = mahs
    payload['hodims'] = hodims
    
    soni = jami_hodimlar
    msoni = jami_mahsulotlar

    now = timezone.localtime()

    today_start = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.min))
    today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))
    bsavdo=Savdo.objects.filter(vaqt_sana__range=(today_start, today_end)).all()
    

    # Oyning 1-kunining 00:00:00 va bugungi 23:59:59
    month_start = timezone.make_aware(dt.datetime.combine(now.replace(day=1).date(), dt.time.min))
    today_end = timezone.make_aware(dt.datetime.combine(now.date(), dt.time.max))

    savdo = Savdo.objects.filter(vaqt_sana__range=(month_start, today_end)).all()
    

    payload['bsavdo'] = bsavdo

    payload['savdo'] = savdo
    # Use Analytics Service
    stats = get_dashboard_stats()
    payload['usumma'] = add_spctoint(stats['total_sales_month'])
    payload['bsumma'] = add_spctoint(stats['total_sales_today'])
    payload['low_stock_list'] = stats['low_stock_list']
    payload['low_stock_count'] = stats['low_stock_products']
    
    payload['ishchilar_soni'] = soni
    payload['msoni'] = msoni
    
    return render(request, 'main.html', payload)

@login_required(login_url='login')
def logout_view(request):
    """Foydalanuvchini tizimdan chiqarish"""
    auth_logout(request)
    return redirect('login')
@login_required(login_url='login')
def add_haridor(request):
    if request.user.type == 'yetkazib_beruvchi':
        if request.method == 'POST':
            nomi = request.POST.get('nomi')
            egasi = request.POST.get('egasi')
            joylashuvi = request.POST.get('joylashuvi')
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            dukon_rasmi = request.FILES.get('dukon_rasmi')
            egasining_rasmi = request.FILES.get('egasining_rasmi')
            
            # Saqlash
            HaridorDukon.objects.create(
                nomi=nomi,
                egasi=egasi,
                joylashuvi=joylashuvi,
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None,
                dukon_rasmi=dukon_rasmi,
                egasining_rasmi=egasining_rasmi
            )
            
            messages.success(request, "Yangi haridor muvaffaqiyatli qo‘shildi!")
            return redirect('main')  # yoki kerakli sahifaga
    
        return render(request, 'add_haridor.html')
    return redirect('main')
@login_required(login_url='login')
def profile_view(request, username):
    user =  User.objects.get(username=username)
    if request.method == 'GET':
    
        if request.user.type ==  'yetkazib_beruvchi':
            return render(request, 'ytprofile.html', {'user': user})
        elif request.user.type == 'pazanda':
            return render(request, 'pzprofile.html', {'user': user})
        elif request.user.type=='ega':
            if user.type == 'yetkazib_beruvchi':
                yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=user).mahsulotlar) or []
                return render(request, 'egayt.html',{'user': user,'yuklamalar': yuklamalar})
            return render(request, 'egaprofile.html', {'user': user})
    elif request.method == 'POST':
        if request.user.type == 'ega':
            res=''
            if user.type == 'yetkazib_beruvchi':
                # Note: Keeping legacy stock adjustment for now as a fallback, 
                # but ideally this should also use a service.
                for i in request.POST:
                    
                    nomi=Mahsulot.objects.filter(nomi=i)
                    if nomi.exists():
                        
                        mq=request.POST[i]
                        if mq!="0":
                            res+=f"{i} {mq},"
                
                yt=YetkazibBeruvchi.objects.get(user=user)
                yt.mahsulotlar=res
                yt.save()
                yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=user).mahsulotlar) or []
                return render(request, 'egayt.html',{'user': user,'yuklamalar': yuklamalar})
@login_required(login_url='login')
def crtuser(request):
    if request.method == 'POST':
        user, message = create_user_service(
            username=request.POST.get('username'),
            password=request.POST.get('password'),
            fullname=request.POST.get('tuliq_ismi'),
            user_type=request.POST.get('turi'),
            phone=request.POST.get('telefon'),
            profile_photo=request.FILES.get('rasmi'),
            car_info=request.POST.get('mashina_nomi'),
            car_photo=request.FILES.get('mashina_rasmi')
        )
        if user:
            messages.success(request, message)
            return redirect('hodimlar_list')
        else:
            messages.error(request, message)
            return render(request, 'useryaratish.html', request.POST)

    return render(request, 'useryaratish.html')

@login_required(login_url='login')
def editusr(request, username):
    user_edit = get_object_or_404(User, username=username)
    mn = ''
    mr = ''
    all_mahsulotlar = []
    current_yuklamalar_dict = {}

    if user_edit.type == 'yetkazib_beruvchi':
        yb = YetkazibBeruvchi.objects.get(user=user_edit)
        mn = yb.bmh
        mr = yb.bmr.url if yb.bmr else ''
        all_mahsulotlar = Mahsulot.objects.all().order_by('nomi')
        
        # Parse current stock string into dict {nom: miqdor}
        from .functions import mahsulotlar_miqdori
        yuklamalar_list = mahsulotlar_miqdori(yb.mahsulotlar)
        for y in yuklamalar_list:
            current_yuklamalar_dict[y.nom] = y.miqdor

    if request.method == 'POST':
        action_type = request.POST.get('action_type')
        
        if action_type == 'delete_account':
            if request.POST.get('confirm_text') == 'OCHIR':
                user_edit.delete()
                messages.success(request, "Foydalanuvchi o'chirildi.")
                return redirect('hodimlar_list')
            else:
                messages.error(request, "Tasdiq matni noto'g'ri.")
                return redirect('edituser', username=username)

        # Refactored to Auth Service
        user, message = update_user_service(
            user=user_edit,
            username=request.POST.get('username'),
            fullname=request.POST.get('tuliq_ismi'),
            phone=request.POST.get('telefon'),
            password=request.POST.get('password'),
            profile_photo=request.FILES.get('rasmi'),
            car_info=request.POST.get('mashina_nomi'),
            car_photo=request.FILES.get('mashina_rasmi1'),
            is_active=(request.POST.get('is_active') == "1")
        )

        # Handle manual stock override for delivery users if they are not using sorov flow
        if user.type == 'yetkazib_beruvchi':
            yb = YetkazibBeruvchi.objects.get(user=user)
            new_yuklamalar_str = ""
            all_mahs = Mahsulot.objects.all()
            for m in all_mahs:
                miqdor = request.POST.get(f'qty_{m.id}') # Use ID as sent from updated template
                if miqdor and float(miqdor) > 0:
                    new_yuklamalar_str += f"{m.nomi} {int(float(miqdor))},"
            yb.mahsulotlar = new_yuklamalar_str
            yb.save()

        messages.success(request, message)
        return redirect('hodimlar_list')

    return render(request, 'editusr.html', {
        'user_edit': user_edit,
        'mn': mn,
        'mr': mr,
        'all_mahsulotlar': all_mahsulotlar,
        'current_yuklamalar': current_yuklamalar_dict
    })
@login_required(login_url='login')
def seemahsulot(request, mahsulot_id):
    mahsulot = Mahsulot.objects.get(id=mahsulot_id)
    turs = MahsulotTuri.objects.all()
    if request.method == 'POST':
        if 'nomi' in request.POST:
            nnomi = request.POST.get('nomi')
            yts = YetkazibBeruvchi.objects.all()
            for yt in yts:
                mahs = mahsulotlar_miqdori(yt.mahsulotlar)
                for m in mahs:
                    if m.nom == mahsulot.nomi:
                        m.nom = nnomi
                yt.mahsulotlar = yuklama_maker(mahs)
                yt.save()
            mahsulot.nomi = nnomi

        mahsulot.miqdori = request.POST.get('miqdori')
        mahsulot.narxi = request.POST.get('narxi')
        
        # Look up by ID as sent from the template <option value="{{ tur.id }}">
        turi_id = request.POST.get('turi')
        if turi_id:
            mahsulot.turi = MahsulotTuri.objects.get(id=turi_id)
            
        if 'rasmi' in request.FILES:
            mahsulot.rasmi = request.FILES['rasmi']
        
        mahsulot.save()
        messages.success(request, "Mahsulot muvaffaqiyatli saqlandi.")
        return redirect('mahsulotlar_list')
    return render(request, 'seemahsulot.html', {'mahsulot': mahsulot, 'turs': turs})
@login_required(login_url='login')
def createmahsulot(request):
    tur=MahsulotTuri.objects.all()
    payload={}  
    payload['turs']=tur
    if request.method == 'POST':
        nomi = request.POST.get('nomi')
        miqdori = request.POST.get('miqdori')
        turi=MahsulotTuri.objects.get(nomi=request.POST.get('turi'))
        rasmi = request.FILES.get('rasmi')
        narxi=request.POST.get('narxi')
        mh=Mahsulot.objects.create(nomi=nomi, miqdori=miqdori, turi=turi,narxi=narxi, rasmi=rasmi)
        mh.save()
        # Activity log
        AmalLog.objects.create(
            user=request.user,
            amal_shifri=f"mahsulot_yaratish|{nomi}|{miqdori}|{narxi}"
        )
        return redirect('main')
    return render(request, 'crtmahsulot.html',payload)

@login_required(login_url='login')
def deleteprdct(request, product_id):
    mhs = get_object_or_404(Mahsulot, id=product_id)
    if request.method == 'POST':
        confirm_text = request.POST.get('confirm_text')
        if confirm_text == 'OCHIR':
            mhs.delete()
            messages.success(request, "Mahsulot o'chirildi.")
            return redirect('mahsulotlar_list')
        else:
            messages.error(request, "Tasdiqlash matni noto'g'ri.")
    return redirect('seeproduct', mahsulot_id=product_id)
@login_required(login_url='login')
def addmiqdor(request):
    if request.user.type=='pazanda':        
        
        payload={}
        payload['mahsulotlar']=Mahsulot.objects.all()
        
        if request.method == 'POST':
            ok=1
            mxs=Mahsulot.objects.get(nomi=request.POST.get('mahsulot'))
            mqdr=request.POST.get('miqdor')
            rasmi=request.FILES.get('rasm')
            pz=Pazanda.objects.get(user=request.user)
            nw=MiqdorQoshish.objects.create(mahsulot=mxs,miqdor=mqdr,rasmi=rasmi,tasdiqlangan=True, pazanda=pz)
            mxs.miqdori+=int(mqdr)
            mxs.save()
            nw.save()
            
            
            return redirect('main')
        return render(request, 'addmiqdor.html',payload)
    return redirect('main')
@login_required(login_url='login')
def add_yuklama(request):
    pazanda = Pazanda.objects.get(user=request.user)
    mahsulotlar = Mahsulot.objects.all()
    yetkazuvchilar = YetkazibBeruvchi.objects.all()

    if request.method == "POST":
        mahsulot = Mahsulot.objects.get(id=request.POST['mahsulot'])
        miqdor = float(request.POST['miqdor'])
        yetkazuvchi = YetkazibBeruvchi.objects.get(id=request.POST['yetkazuvchi'])
        

        YuklamaSorov.objects.create(
            pazanda=pazanda,
            mahsulot=mahsulot,
            user=yetkazuvchi,
            miqdor=miqdor,
            mode='waiting',
            
        )
        return redirect('main')

    return render(request, 'pzyuklama.html', {
        'mahsulotlar': mahsulotlar,
        'yetkazuvchilar': yetkazuvchilar,
    })
@login_required(login_url='login')
def sotish(request):
    
    if request.user.type == 'yetkazib_beruvchi':
        yt = YetkazibBeruvchi.objects.get(user=request.user)
        usr=request.user
        mahsulotlar = mahsulotlar_miqdori(yt.mahsulotlar)
        xaridorlar=HaridorDukon.objects.all()
        
        if request.method == "POST":
            rasm=request.FILES.get('rasm')
            turi =request.POST.get('st')
            haridor= HaridorDukon.objects.get(id=  request.POST.get('haridor'))
            oluvchi=request.POST.get('oluvchi')
            sotilganlar = []
            for m in mahsulotlar:
                miqdor = request.POST.get(f'miqdor_{m.nom}')
                if miqdor!='0':
                    m.miqdor -= float(miqdor)
                    sotilganlar.append((m.nom, miqdor))  # Logging uchun
                
            if len(sotilganlar) > 0:
                txt=''
                summa=0
                for s in sotilganlar:
                    mxs=Mahsulot.objects.get(nomi=s[0])
                    txt+=f'{s[0]} {s[1]} {mxs.narxi},'
                    summa+=float(s[1])*float(mxs.narxi)
                if turi=='nasiya':
                    svd=Savdo.objects.create(yetkazib_beruvchi=yt,haridor_dukon=haridor,smm=txt,smr=rasm,oluvchining_ismi=oluvchi,tulandi=False,tasdiq_kutilmoqda=False,st=turi,summa=summa)
                    svd.save()

                else:
                    svd=Savdo.objects.create(yetkazib_beruvchi=yt,haridor_dukon=haridor,smm=txt,smr=rasm,oluvchining_ismi=oluvchi,tulandi=True,tasdiq_kutilmoqda=True,st=turi,summa=summa)
                    svd.save()
    
                sotishm(txt,yt)
                # Activity log
                AmalLog.objects.create(
                    user=request.user,
                    amal_shifri=f"savdo_yaratish|{haridor.nomi}|{summa}"
                )
                # svd=Savdo.objects.create(yetkazuvchi=yt,haridor=request.POST.get('haridor'),mahsulotlar=txt)
                # Istasa: Savdo modelga yozish

            

            # yt.mahsulotlar = yuklama_maker(mahsulotlar)
            # yt.save()
            # Istasa: Savdo modelga yozish
            return redirect('main')
    else:
        return redirect('main')

    return render(request, 'ytsot.html', {'mahsulotlar': mahsulotlar,'haridorlar':xaridorlar})


# ============================================
# API Endpoint for Browser Notifications
# ============================================
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

@login_required(login_url='login')
@require_http_methods(["GET"])
def check_new_deliveries(request):
    """
    API endpoint to check for new delivery requests for delivery personnel.
    Returns JSON with count and details of new deliveries since last check.
    """
    if request.user.type != 'yetkazib_beruvchi':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        yetkazuvchi = YetkazibBeruvchi.objects.get(user=request.user)
        
        # Get last check time from session or default to 1 minute ago
        last_check_str = request.session.get('last_delivery_check')
        if last_check_str:
            from datetime import datetime
            last_check = timezone.make_aware(datetime.fromisoformat(last_check_str))
        else:
            # Default: check last 1 minute
            last_check = timezone.now() - timezone.timedelta(minutes=1)
        
        # Get new delivery requests since last check
        new_deliveries = YuklamaSorov.objects.filter(
            user=yetkazuvchi,
            sana__gt=last_check,
            tasdiq=False
        ).select_related('pazanda__user').order_by('-sana')
        
        deliveries_data = []
        for delivery in new_deliveries:
            pazanda_name = delivery.pazanda.user.tuliq_ismi if delivery.pazanda else "Noma'lum"
            deliveries_data.append({
                'id': delivery.id,
                'pazanda': pazanda_name,
                'sana': delivery.sana.strftime('%H:%M'),
                'mahsulot': delivery.mahsulot.nom if delivery.mahsulot else "Mahsulot",
                'miqdor': delivery.miqdor
            })
        
        # Update last check time
        request.session['last_delivery_check'] = timezone.now().isoformat()
        
        return JsonResponse({
            'success': True,
            'count': len(deliveries_data),
            'deliveries': deliveries_data
        })
        
    except YetkazibBeruvchi.DoesNotExist:
        return JsonResponse({'error': 'Delivery user not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─── MVP: Pazanda — So'rovlar tarixi ─────────────────────────────────────────
@login_required(login_url='login')
def pz_sorov_tarixi(request):
    """Pazanda uchun: o'zi yuborgan barcha YuklamaSorov larni ko'rish."""
    if request.user.type != 'pazanda':
        return redirect('main')

    pazanda = Pazanda.objects.get(user=request.user)
    filter_val = request.GET.get('filter', 'all')

    qs = YuklamaSorov.objects.filter(pazanda=pazanda).order_by('-sana')

    if filter_val == 'waiting':
        qs = qs.filter(tasdiq=False, mode='waiting')
    elif filter_val == 'approved':
        qs = qs.filter(tasdiq=True)
    elif filter_val == 'rejected':
        qs = qs.filter(mode='rejected')

    # Summary counts
    all_qs = YuklamaSorov.objects.filter(pazanda=pazanda)
    context = {
        'sorovlar': qs,
        'jami': all_qs.count(),
        'tasdiqlangan': all_qs.filter(tasdiq=True).count(),
        'kutilmoqda': all_qs.filter(tasdiq=False, mode='waiting').count(),
        'rad_etilgan': all_qs.filter(mode='rejected').count(),
    }
    return render(request, 'pzsorovlar.html', context)


# ─── MVP: Yetkazuvchi Hisobot ─────────────────────────────────────────────────
@login_required(login_url='login')
def yetkazuvchi_hisobot(request, username):
    """Admin uchun: berilgan yetkazuvchining to'liq hisoboti."""
    if request.user.type not in ('ega',):
        return redirect('main')

    target_user = get_object_or_404(User, username=username, type='yetkazib_beruvchi')
    yb = get_object_or_404(YetkazibBeruvchi, user=target_user)

    from django.db.models import Sum as DSum
    import datetime as _dt

    now = timezone.localtime()

    # Date filtering
    from_date_str = request.GET.get('from')
    to_date_str   = request.GET.get('to')

    try:
        from_date = _dt.date.fromisoformat(from_date_str) if from_date_str else now.date().replace(day=1)
        to_date   = _dt.date.fromisoformat(to_date_str)   if to_date_str   else now.date()
    except ValueError:
        from_date = now.date().replace(day=1)
        to_date   = now.date()

    from_dt = timezone.make_aware(_dt.datetime.combine(from_date, _dt.time.min))
    to_dt   = timezone.make_aware(_dt.datetime.combine(to_date,   _dt.time.max))

    savdolar = Savdo.objects.filter(
        yetkazib_beruvchi=yb,
        vaqt_sana__range=(from_dt, to_dt)
    ).order_by('-vaqt_sana')

    # Today stats
    today_start = timezone.make_aware(_dt.datetime.combine(now.date(), _dt.time.min))
    today_end   = timezone.make_aware(_dt.datetime.combine(now.date(), _dt.time.max))
    month_start = timezone.make_aware(_dt.datetime.combine(now.date().replace(day=1), _dt.time.min))

    bugun_savdo = Savdo.objects.filter(yetkazib_beruvchi=yb, vaqt_sana__range=(today_start, today_end)).aggregate(t=DSum('summa'))['t'] or 0
    oy_savdo    = Savdo.objects.filter(yetkazib_beruvchi=yb, vaqt_sana__gte=month_start).aggregate(t=DSum('summa'))['t'] or 0

    # Nasiya qarz
    nasiya_savdolar = Savdo.objects.filter(yetkazib_beruvchi=yb, st='nasiya', tulandi=False)
    nasiya_qarz = nasiya_savdolar.aggregate(t=DSum('summa'))['t'] or 0

    # Savdolar jami for filter period
    savdolar_jami = savdolar.aggregate(t=DSum('summa'))['t'] or 0

    # Zaxira (legacy string parsed)
    from .functions import mahsulotlar_miqdori
    zaxira = mahsulotlar_miqdori(yb.mahsulotlar) or []

    context = {
        'yb': yb,
        'savdolar': savdolar,
        'savdolar_jami': savdolar_jami,
        'jami_savdo_soni': savdolar.count(),
        'bugun_savdo': bugun_savdo,
        'oy_savdo': oy_savdo,
        'nasiya_qarz': nasiya_qarz,
        'zaxira': zaxira,
        'from_date': from_date.isoformat(),
        'to_date': to_date.isoformat(),
    }
    return render(request, 'yt_hisobot.html', context)
