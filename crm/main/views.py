from django.shortcuts import render, get_list_or_404, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages 
from django.shortcuts import redirect
from .models import HaridorDukon, User, YetkazibBeruvchi, Pazanda, Mahsulot, MahsulotTuri
from .functions import mahsulotlar_miqdori, makenewform, yuklama_maker



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
            messages.error(request, "Login yoki parol noto‘g‘ri!")

    return render(request, 'login.html',data)
@login_required(login_url='login')
def main(request):
    payload={}
    user=request.user
    
    if user.type == 'pazanda':
        return render(request, 'pazanda_dashboard.html')
    elif user.type == 'yetkazib_beruvchi':
        yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=request.user).mahsulotlar) or []
        return render(request, 'yetkazuvchi_dashboard.html',{'yuklamalar': yuklamalar})
    hodims=  User.objects.exclude(type='ega')
    mahs=Mahsulot.objects.all()
    
    payload['hodims'] = hodims
    payload['mahsulotlar'] = mahs
    soni=len(hodims)
    
    payload['ishchilar_soni'] = soni
    
    return render(request, 'main.html',payload)
def logout(request):
    logout(request)
    return redirect('login')
@login_required(login_url='login')
def add_haridor(request):
    if request.user.type == 'yetkazib_beruvchi':
        if request.method == 'POST':
            nomi = request.POST.get('nomi')
            egasi = request.POST.get('egasi')
            joylashuvi = request.POST.get('joylashuvi')
            dukon_rasmi = request.FILES.get('dukon_rasmi')
            egasining_rasmi = request.FILES.get('egasining_rasmi')
            
            # Saqlash
            HaridorDukon.objects.create(
                nomi=nomi,
                egasi=egasi,
                joylashuvi=joylashuvi,
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
        print('post')
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
            if 'mashina_rasmi1' in request.FILES:
                print('mashina rasmi')
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

def seemahsulot(request, mahsulot_id):
    mahsulot = Mahsulot.objects.get(id=mahsulot_id)
    turs=MahsulotTuri.objects.all()
    return render(request, 'seemahsulot.html', {'mahsulot': mahsulot,'turs':turs})