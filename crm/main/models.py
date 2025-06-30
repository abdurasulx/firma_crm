from django.db import models
from django.contrib.auth.models import AbstractUser


# --- USER MODELI ---
class User(AbstractUser):
    id = models.BigAutoField(primary_key=True)
    USER_TYPES = (
        ('pazanda', 'Pazanda'),
        ('yetkazib_beruvchi', 'Yetkazib Beruvchi'),
        ('ega', 'Ega'),
    )
    login=models.CharField(max_length=255, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    tuliq_ismi = models.CharField(max_length=255, blank=True, null=True)
    type = models.CharField(max_length=20, choices=USER_TYPES)
    token = models.CharField(max_length=255, blank=True, null=True)
    tg_id = models.CharField(max_length=100, blank=True, null=True)
    tel_raqami = models.CharField(max_length=100, blank=True, null=True)
    

    def __str__(self):
        return f"{self.username} ({self.type})"
    @property
    def rasmi(self):
        if self.type == 'yetkazib_beruvchi':
            try:
                return YetkazibBeruvchi.objects.get(user=self).rasmi.url
            except YetkazibBeruvchi.DoesNotExist:
                return None
        elif self.type == 'pazanda':
            try:
                return Pazanda.objects.get(user=self).rasmi.url
            except Pazanda.DoesNotExist:
                return None
        return None


# --- HARIDOR DUKON ---
class HaridorDukon(models.Model):
    nomi = models.CharField(max_length=255)
    egasi = models.CharField(max_length=255)
    joylashuvi = models.TextField()
    dukon_rasmi = models.ImageField(upload_to='dukons/')
    egasining_rasmi = models.ImageField(upload_to='egalar/')

    def __str__(self):
        return self.nomi


# --- MAHSULOT TURI ---
class MahsulotTuri(models.Model):
    nomi = models.CharField(max_length=100)  # kg, dona, l

    def __str__(self):
        return self.nomi


# --- MAHSULOT ---
class Mahsulot(models.Model):
    nomi = models.CharField(max_length=255)
    rasmi = models.ImageField(upload_to='mahsulotlar/')
    narxi = models.DecimalField(max_digits=10, decimal_places=2)
    turi = models.ForeignKey(MahsulotTuri, on_delete=models.CASCADE)
    miqdori = models.FloatField(default=0)

    def __str__(self):
        return self.nomi


# --- PAZANDA (User vorisi) ---
class Pazanda(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tuliq_ismi = models.CharField(max_length=255)
    turi = models.CharField(max_length=100)
    rasmi = models.ImageField(upload_to='pazandalar/')

    def __str__(self):
        return self.tuliq_ismi


# --- YETKAZIB BERUVCHI ---
class YetkazibBeruvchi(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tuliq_ismi = models.CharField(max_length=255)
    rasmi = models.ImageField(upload_to='yetkazib/')
    bmh = models.TextField(verbose_name="Biriktirilgan mashina haqida")
    bmr = models.ImageField(upload_to='mashina_rasmlar/')
    mahsulotlar = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.tuliq_ismi


# --- MIQDOR QO‘SHISH ---
class MiqdorQoshish(models.Model):
    pazanda = models.ForeignKey(Pazanda, on_delete=models.CASCADE)
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE)
    vaqt_sana = models.DateTimeField(auto_now_add=True)
    miqdor = models.FloatField()
    tasdiqlangan = models.BooleanField(default=False)
    ariza_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.pazanda} - {self.mahsulot}"


# --- SAVDO ---
class Savdo(models.Model):
    ST_CHOICES = (
        ('naqd', 'Naqd'),
        ('karta', 'Karta'),
        ('nasiya', 'Nasiya'),
    )

    haridor_dukon = models.ForeignKey(HaridorDukon, on_delete=models.CASCADE)
    yetkazib_beruvchi = models.ForeignKey(YetkazibBeruvchi, on_delete=models.CASCADE)
    vaqt_sana = models.DateTimeField(auto_now_add=True)
    oluvchining_ismi = models.CharField(max_length=255)
    smm = models.FloatField(verbose_name="Sotilgan mahsulot miqdori")
    smr = models.ImageField(upload_to='savdo/')
    st = models.CharField(max_length=20, choices=ST_CHOICES)
    tulandi = models.BooleanField(default=False)
    tasdiq_kutilmoqda = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.haridor_dukon.nomi} - {self.oluvchining_ismi}"

class AmalLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amal_shifri = models.TextField()  # Masalan: 'chiqarish|un|10'
    sana_vaqti = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.amal_shifri}"
class qaytarilgan_mahsulotlar(models.Model):
   
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE)
    miqdor = models.FloatField()
    sana = models.DateTimeField(auto_now_add=True)
    yq=models.BooleanField(default=False)

    def __str__(self):
        return f"{self.mahsulot} - {self.miqdor}"