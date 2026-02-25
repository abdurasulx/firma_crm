from django.contrib.auth import authenticate, get_user_model
from ..models import YetkazibBeruvchi, Pazanda

User = get_user_model()

def create_user_service(username, password, fullname, user_type, phone=None, profile_photo=None, car_info=None, car_photo=None):
    """Securely creates a new user and its profile."""
    if User.objects.filter(username=username).exists():
        return None, "Ushbu login allaqachon mavjud!"

    user = User.objects.create_user(
        username=username, 
        password=password, 
        tuliq_ismi=fullname, 
        tel_raqami=phone
    )
    user.type = user_type
    user.save()

    if user_type == 'yetkazib_beruvchi':
        YetkazibBeruvchi.objects.create(
            user=user, 
            tuliq_ismi=fullname, 
            rasmi=profile_photo, 
            bmr=car_photo, 
            bmh=car_info
        )
    elif user_type == 'pazanda':
        Pazanda.objects.create(
            user=user, 
            tuliq_ismi=fullname, 
            rasmi=profile_photo
        )
    
    return user, "Foydalanuvchi muvaffaqiyatli yaratildi."

def update_user_service(user, username, fullname, phone, password=None, profile_photo=None, car_info=None, car_photo=None, is_active=None):
    """Securely updates user information and profile."""
    user.username = username
    user.tuliq_ismi = fullname
    user.tel_raqami = phone
    
    if is_active is not None:
        user.is_active = is_active
        
    if password:
        user.set_password(password)
    
    user.save()

    if user.type == 'yetkazib_beruvchi':
        yb = YetkazibBeruvchi.objects.get(user=user)
        yb.tuliq_ismi = fullname
        yb.bmh = car_info
        if car_photo:
            yb.bmr = car_photo
        if profile_photo:
            yb.rasmi = profile_photo
        yb.save()
    elif user.type == 'pazanda':
        pz = Pazanda.objects.get(user=user)
        pz.tuliq_ismi = fullname
        if profile_photo:
            pz.rasmi = profile_photo
        pz.save()

    return user, "Ma'lumotlar saqlandi."
