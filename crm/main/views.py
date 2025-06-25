from django.shortcuts import render, get_list_or_404, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages 
from django.shortcuts import redirect
from .models import HaridorDukon, User, YetkazibBeruvchi
from .functions import mahsulotlar_miqdori



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
    user=request.user
    
    if user.type == 'pazanda':
        return render(request, 'pazanda_dashboard.html')
    elif user.type == 'yetkazib_beruvchi':
        yuklamalar = mahsulotlar_miqdori( YetkazibBeruvchi.objects.get(user=request.user).mahsulotlar) or []
        return render(request, 'yetkazuvchi_dashboard.html',{'yuklamalar': yuklamalar})
    
    return render(request, 'main.html')
def logout(request):
    logout(request)
    return redirect('login')
@login_required(login_url='login')
def add_haridor(request):
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
def profile_view(request, username):
    user = request.user if username == 'request.user.username' else User.objects.get(username=username)
    if user.type == 'yetkazib_beruvchi':
        return render(request, 'ytprofile.html', {'user': user})
    elif user.type == 'pazanda':
        return render(request, 'pzprofile.html', {'user': user})
    elif user.type=='ega':
        return render(request, 'egaprofile.html', {'user': user})
