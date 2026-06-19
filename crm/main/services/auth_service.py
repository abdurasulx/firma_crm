from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from ..models import YetkazibBeruvchi, Pazanda

User = get_user_model()

@transaction.atomic
def create_user_service(username, password, fullname, user_type, phone=None, profile_photo=None, car_info=None, car_photo=None, company=None):
    """Securely creates a new user and its profile."""
    if User.objects.filter(username=username, company=company).exists():
        return None, "Ushbu login allaqachon mavjud!"

    user = User.objects.create_user(
        username=username, 
        password=password, 
        tuliq_ismi=fullname, 
        tel_raqami=phone,
        company=company,
        type=user_type,
    )

    if user_type in ['yetkazib_beruvchi', 'savdogar']:
        YetkazibBeruvchi.objects.create(
            user=user, 
            tuliq_ismi=fullname, 
            rasmi=profile_photo, 
            bmr=car_photo, 
            bmh=car_info or '',
            company=company
        )
    elif user_type in ['pazanda', 'ishlab_chiqaruvchi']:
        Pazanda.objects.create(
            user=user, 
            tuliq_ismi=fullname, 
            rasmi=profile_photo,
            company=company
        )
    
    return user, "Foydalanuvchi muvaffaqiyatli yaratildi."

def update_user_service(user, username, fullname, phone, password=None, profile_photo=None, car_info=None, car_photo=None, is_active=None):
    """Securely updates user information and profile."""
    if User.objects.filter(company=user.company, username=username).exclude(pk=user.pk).exists():
        return None, "Ushbu login allaqachon mavjud!"

    user.username = username
    user.tuliq_ismi = fullname
    user.tel_raqami = phone
    
    if is_active is not None:
        user.is_active = is_active

    if profile_photo and user.type not in ['yetkazib_beruvchi', 'savdogar', 'pazanda', 'ishlab_chiqaruvchi']:
        user.rasm = profile_photo
        
    if password:
        user.set_password(password)
    
    user.save()

    if user.type in ['yetkazib_beruvchi', 'savdogar']:
        yb = YetkazibBeruvchi.objects.get(user=user)
        yb.tuliq_ismi = fullname
        yb.bmh = car_info or ''
        if car_photo:
            yb.bmr = car_photo
        if profile_photo:
            yb.rasmi = profile_photo
        yb.save()
    elif user.type in ['pazanda', 'ishlab_chiqaruvchi']:
        pz = Pazanda.objects.get(user=user)
        pz.tuliq_ismi = fullname
        if profile_photo:
            pz.rasmi = profile_photo
        pz.save()

    return user, "Ma'lumotlar saqlandi."
