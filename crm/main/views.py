from django.shortcuts import render, get_list_or_404, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages 
from django.utils import timezone
from django.shortcuts import redirect
from .models import HaridorDukon, User, YetkazibBeruvchi, Pazanda, Mahsulot, MahsulotTuri, Savdo, YuklamaSorov, MiqdorQoshish, HaridorDukon, AmalLog
from .functions import mahsulotlar_miqdori, makenewform, yuklama_maker, accptyuk, sotishm, sotuv_new_form ,yetkazuvchi_mahsulot_filter, get_bugungi_savdo_summ
import datetime as dt



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
                    yk=YuklamaSorov.objects.get(id=yk_id)
                   
                    accptyuk(request.user,yk)
                    # Activity log
                    AmalLog.objects.create(
                        user=request.user,
                        amal_shifri=f"yuklama_qabul|{yk.mahsulot.nomi}|{yk.miqdor}"
                    )    


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
    payload['usumma']=get_bugungi_savdo_summ(savdo)
    payload['bsumma'] = get_bugungi_savdo_summ(bsavdo)
    
    payload['ishchilar_soni'] = soni
    payload['msoni'] = msoni
    
    return render(request, 'main.html',payload)

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
    payload = {}
   
    if request.method == 'POST':
       
        username = request.POST.get('username')
        password = request.POST.get('password')
        fullname = request.POST.get('tuliq_ismi')
        type = request.POST.get('turi')
        telefon = request.POST.get('telefon')
        rasmi = request.FILES.get('rasmi')
        payload['username'] = username
        payload['password'] = password
        payload['tuliq_ismi'] = fullname
        payload['turi'] = type
        payload['telefon'] = telefon

        if User.objects.filter(username=username).exists():
            messages.error(request, "Bu login allaqachon mavjud!")
            return render(request, 'useryaratish.html',payload)

        

        if type == 'yetkazib_beruvchi':
            mn=request.POST.get('mashina_nomi')
            payload['mashina_nomi'] = mn
            if 'mashina_rasmi' in request.FILES:
                mr=request.FILES.get('mashina_rasmi')
                user = User.objects.create_user(username=username, password=password,tel_raqami=telefon, tuliq_ismi=fullname)
                user.type = type  # Agar User modelida type bo'lsa
                user.save()
            else:
                messages.error(request, "Mashina rasmini tanlang!")
                return render(request, 'useryaratish.html',payload)
            
            
            YetkazibBeruvchi.objects.create(user=user, tuliq_ismi=fullname ,rasmi=rasmi,bmr=mr,bmh=mn)
        elif type == 'pazanda':
            
            Pazanda.objects.create(user=user, tuliq_ismi=fullname, rasmi=rasmi)

        
        return redirect('main')
    
    
    return render(request, 'useryaratish.html')
@login_required(login_url='login')
def editusr(request, username):

    user_edit = get_object_or_404(User, username=username)
    mn=''
    mr=''
    if user_edit.type == 'yetkazib_beruvchi':
        mn=YetkazibBeruvchi.objects.get(user=user_edit).bmh
        mr=YetkazibBeruvchi.objects.get(user=user_edit).bmr.url
    
    if request.method == 'POST':
        action_type = request.POST.get('action_type')
        if user_edit.type == 'yetkazib_beruvchi':
            su=YetkazibBeruvchi.objects.get(user=user_edit)
        elif user_edit.type == 'pazanda':
            su=Pazanda.objects.get(user=user_edit)

        if action_type == 'delete_account':
            confirm_text = request.POST.get('confirm_text')
            if confirm_text == 'OCHIR':
                user_edit.delete()
                su.delete()
             
                return redirect('main')  # O'chirilgandan keyin qaysi sahifaga yo'naltirilishini belgilang
            else:
                messages.error(request, "Tasdiq matni noto'g'ri.")


    if request.method == 'POST':
        
        user_edit.username = request.POST.get('username')
        user_edit.tuliq_ismi = request.POST.get('tuliq_ismi')
        user_edit.tel_raqami = request.POST.get('telefon')
        new_password = request.POST.get('password')
        is_active = request.POST.get('is_active')=="True"
        
        if is_active!=user_edit.is_active:
            user_edit.is_active=is_active

        if new_password:
            user_edit.set_password(new_password)

        user_edit.save()

        if user_edit.type == 'yetkazib_beruvchi':
            
            yb = YetkazibBeruvchi.objects.get(user=user_edit)
            yb.mashina_nomi = request.POST.get('mashina_nomi')
            yb.tuliq_ismi=request.POST.get('tuliq_ismi')
            yb.user.tuliq_ismi=request.POST.get('tuliq_ismi')
            if 'mashina_rasmi1' in request.FILES:
                
                yb.bmr = request.FILES['mashina_rasmi1']
               
            if 'rasmi' in request.FILES:
                yb.rasmi = request.FILES['rasmi']
            yb.save()

        if user_edit.type == 'pazanda':
            pz = Pazanda.objects.get(user=user_edit)
            if 'rasmi' in request.FILES:
                pz.rasmi = request.FILES['rasmi']
            pz.save()

        
        return redirect('main')

    return render(request, 'editusr.html', {'user_edit': user_edit,'mn':mn,'mr':mr})
@login_required(login_url='login')
def seemahsulot(request, mahsulot_id):
    mahsulot = Mahsulot.objects.get(id=mahsulot_id)
    turs=MahsulotTuri.objects.all()
    if request.method == 'POST':
        if 'nomi' in request.POST:
            nnomi=request.POST.get('nomi')
            yts=YetkazibBeruvchi.objects.all()
            for yt in yts:
                mahs= mahsulotlar_miqdori(yt.mahsulotlar)
                
                for m in mahs:

                    if m.nom==mahsulot.nomi:
                        

                        m.nom=nnomi
                    
                yt.mahsulotlar=yuklama_maker(mahs)
                yt.save()
            mahsulot.nomi = request.POST.get('nomi')

        mahsulot.miqdori = request.POST.get('miqdori')
        turi=MahsulotTuri.objects.get(nomi=request.POST.get('turi'))
        mahsulot.turi = turi
        mahsulot.save()
        if 'mahsulot_rasmi' in request.FILES:
            mahsulot.rasmi = request.FILES['mahsulot_rasmi']
            mahsulot.save()
        return redirect('main')
    return render(request, 'seemahsulot.html', {'mahsulot': mahsulot,'turs':turs})
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
def deleteprdct(request,product_id):
    mhs=get_object_or_404(Mahsulot,id=product_id)
    if mhs:
        mhs.delete()
        return redirect('main')
    return redirect('main')
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
