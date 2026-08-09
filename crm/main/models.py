from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from uuid import uuid4

SAVDOGAR_SALES_ADDON_PRICE = Decimal("10.00")
DESKTOP_AGENT_UNIT_PRICE = Decimal("60.00")

BACKUP_CHOICES = (
    ('none', 'Yo\'q ($0)'),
    ('monthly', 'Oylik ($5)'),
    ('weekly', 'Haftalik ($15)'),
    ('daily', 'Kunlik ($30)'),
)

# --- PLAN (TARIFF) MODEL ---
class Plan(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_users = models.IntegerField(default=5)
    has_telegram_bot = models.BooleanField(default=False)
    has_analytics = models.BooleanField(default=True)
    has_map = models.BooleanField(default=False)
    backup_type = models.CharField(max_length=20, choices=BACKUP_CHOICES, default='none')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# --- COMPANY MODEL ---
class Company(models.Model):
    name = models.CharField(max_length=255)
    subdomain = models.CharField(max_length=100, unique=True)
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    desktop_agent_token = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False,
        help_text="Desktop Agent dasturi shu firmaning ma'lumotlariga (omborlar ro'yxati) kirishi uchun token.",
    )

    # Custom Plan Fields
    is_custom_plan = models.BooleanField(default=False)
    custom_max_users = models.IntegerField(default=5) # 0 means unlimited
    custom_has_telegram_bot = models.BooleanField(default=False)
    custom_has_analytics = models.BooleanField(default=False)
    custom_has_map = models.BooleanField(default=False)
    custom_has_savdogar_sales = models.BooleanField(default=False)
    custom_desktop_agent_stations = models.PositiveIntegerField(
        default=0,
        help_text=(
            f"Sotib olingan Desktop Agent stansiyalari soni (donasiga oyiga "
            f"${DESKTOP_AGENT_UNIT_PRICE}). Faqat aloqa orqali (superadmin "
            f"tomonidan) belgilanadi — firma egasi o'zi so'ray olmaydi."
        ),
    )
    custom_backup_type = models.CharField(max_length=20, choices=BACKUP_CHOICES, default='none')
    custom_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Credit/savdogar contract settings
    credit_sales_enabled = models.BooleanField(default=True)
    credit_contract_template = models.TextField(
        blank=True,
        default=(
            "Nasiya shartnomasi: {{ company }} va {{ customer }} o'rtasida "
            "{{ months }} oy muddatga {{ total }} so'mlik savdo."
        ),
    )
    credit_early_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    credit_late_penalty_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    credit_rules_note = models.TextField(
        blank=True,
        default="3 oy - 10%, 6 oy - 15%, 9 oy - 20%, 12 oy - 30% ustama. To'lov grafigi oyma-oy nazorat qilinadi.",
    )
    savdogar_contract_text = models.TextField(blank=True, default="")
    savdogar_contract_next_number = models.PositiveIntegerField(default=1)

    # Ishlab chiqarish — ish haqi turi
    ISH_HAQI_TURI_CHOICES = (
        ('fixed', "Oylik (fiksval)"),
        ('per_unit', "Ishlab chiqarilgan mahsulotga qarab"),
    )
    ish_haqi_turi = models.CharField(max_length=20, choices=ISH_HAQI_TURI_CHOICES, default='fixed')

    last_backup_at = models.DateTimeField(null=True, blank=True)
    
    # Billing fields
    PAYMENT_CHOICES = (
        ('paid', "To'langan"),
        ('unpaid', "To'lanmagan")
    )
    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='unpaid')
    next_payment_date = models.DateTimeField(null=True, blank=True)
    
    
    # Lifecycle fields
    setup_mode = models.BooleanField(default=True)
    setup_expires_at = models.DateTimeField(null=True, blank=True)
    is_on_trial = models.BooleanField(default=False)
    trial_expires_at = models.DateTimeField(null=True, blank=True)
    has_used_trial = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def desktop_agent_addon_price(self):
        return self.custom_desktop_agent_stations * DESKTOP_AGENT_UNIT_PRICE

    @property
    def monthly_price(self):
        if self.plan:
            price = Decimal(self.plan.price or 0)
            if self.custom_has_savdogar_sales:
                price += SAVDOGAR_SALES_ADDON_PRICE
            price += self.desktop_agent_addon_price
            return price
        # Maxsus tarif: `custom_price` "Maxsus Tarif Quruvchi" orqali
        # tanlangan barcha modullar (Desktop Agent stansiyalari ham shu
        # jumladan) narxini o'z ichiga oladi — bu yerda qayta qo'shilmaydi
        # (aks holda ikki marta hisoblanib qolardi).
        return Decimal(self.custom_price or 0)

    def __str__(self):
        return self.name

class PlanRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Kutilmoqda'),
        ('approved', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='plan_requests')
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)
    is_custom = models.BooleanField(default=False)
    # Store custom plan details if is_custom is True
    custom_max_users = models.IntegerField(default=5)
    custom_has_telegram_bot = models.BooleanField(default=False)
    custom_has_analytics = models.BooleanField(default=False)
    custom_has_map = models.BooleanField(default=False)
    custom_has_savdogar_sales = models.BooleanField(default=False)
    custom_desktop_agent_stations = models.PositiveIntegerField(default=0)
    custom_backup_type = models.CharField(max_length=20, choices=BACKUP_CHOICES, default='none')
    custom_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    is_trial = models.BooleanField(default=False)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.company.name} - {self.status}"

# --- USER MODELI ---
class User(AbstractUser):
    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        _("username"),
        max_length=150,
        validators=[username_validator],
        help_text=_("150 ta belgigacha. Harf, raqam va @/./+/-/_ belgilaridan foydalaning."),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    id = models.BigAutoField(primary_key=True)
    USER_TYPES = (
        ('pazanda', 'Ishlab chiqaruvchi'),
        ('ishlab_chiqaruvchi', 'Ishlab chiqaruvchi'),
        ('omborchi', 'Omborchi'),
        ('savdogar', 'Savdogar'),
        ('yetkazib_beruvchi', 'Yetkazib Beruvchi'),
        ('desktop_agent', 'Desktop Agent'),
        ('ega', 'Ega'),
    )
    login=models.CharField(max_length=255, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    tuliq_ismi = models.CharField(max_length=255, blank=True, null=True)
    type = models.CharField(max_length=20, choices=USER_TYPES)
    token = models.CharField(max_length=255, blank=True, null=True)
    tg_id = models.CharField(max_length=100, blank=True, null=True)
    tel_raqami = models.CharField(max_length=100, blank=True, null=True)
    rasm = models.ImageField(upload_to='users/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_agent_heartbeat = models.DateTimeField(
        null=True, blank=True,
        help_text="Desktop Agent stansiyasi (type='desktop_agent') fondan har ~25 soniyada yuboradigan "
                   "'tirik ekanligi' signalining oxirgi vaqti — online/oflayn holatini aniqlash uchun.",
    )
    web_session_key = models.CharField(
        max_length=40, null=True, blank=True,
        help_text="Joriy amaldagi veb-sessiya kaliti — yangi qurilmada login qilinganda "
                   "eskisi CompanyMiddleware orqali avtomatik yopiladi (bitta faol veb-sessiya qoidasi).",
    )
    agent_qr_nonce = models.CharField(
        max_length=64, default=uuid4, editable=False,
        help_text="Desktop Agent QR-login shifrlangan payload'ining bir qismi — "
                   "'Yangilash' bosilganda o'zgaradi, shu orqali eski ko'rsatilgan/chop "
                   "etilgan QR kod bekor bo'ladi.",
    )
    ISH_HAQI_TURI_OVERRIDE_CHOICES = (
        ('', "Firma standarti"),
        ('fixed', "Oylik (fiksval)"),
        ('per_unit', "Ishlab chiqarilgan mahsulotga qarab"),
    )
    ish_haqi_turi_override = models.CharField(
        max_length=20, choices=ISH_HAQI_TURI_OVERRIDE_CHOICES, blank=True, default='',
        help_text="Bo'sh bo'lsa Company.ish_haqi_turi (firma standarti) ishlatiladi — "
                   "faqat shu xodim uchun boshqacha to'lov turi kerak bo'lsa to'ldiriladi.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'username'], name='unique_username_per_company'),
        ]

    def __str__(self):
        return f"{self.username} ({self.type})"

    # Stansiya oxirgi shuncha soniya ichida heartbeat yubormasa — "oflayn"
    # hisoblanadi (heartbeat har ~25 soniyada yuboriladi, shuning uchun bu
    # 2-3 marta o'tkazib yuborilgan holatga ham bardosh beradi).
    AGENT_ONLINE_THRESHOLD_SECONDS = 90

    @property
    def is_agent_online(self):
        """Istalgan turdagi foydalanuvchi uchun ishlaydi — Desktop Agent
        stansiyasiga shaxsiy hisob bilan kirilganda ham heartbeat shu
        foydalanuvchiga yoziladi (72-qadam). Stansiya oxirgi
        `AGENT_ONLINE_THRESHOLD_SECONDS` ichida heartbeat yuborganmi."""
        if not self.last_agent_heartbeat:
            return False
        from django.utils import timezone
        return self.last_agent_heartbeat >= timezone.now() - timezone.timedelta(seconds=self.AGENT_ONLINE_THRESHOLD_SECONDS)

    @property
    def rasmi(self):
        if self.type in ['yetkazib_beruvchi', 'savdogar']:
            try:
                return YetkazibBeruvchi.objects.get(user=self).rasmi.url
            except YetkazibBeruvchi.DoesNotExist:
                pass
        elif self.type in ['pazanda', 'ishlab_chiqaruvchi']:
            try:
                return Pazanda.objects.get(user=self).rasmi.url
            except Pazanda.DoesNotExist:
                pass
        return self.rasm.url if self.rasm else None


# --- HARIDOR DUKON ---
class HaridorDukon(models.Model):
    MIJOZ_TURI_CHOICES = (
        ('oddiy', 'Oddiy'),
        ('doimiy', 'Doimiy'),
        ('vip', 'VIP'),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    nomi = models.CharField(max_length=255)
    egasi = models.CharField(max_length=255)
    joylashuvi = models.TextField()
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    dukon_rasmi = models.ImageField(upload_to='dukons/')
    egasining_rasmi = models.ImageField(upload_to='egalar/')
    telefon = models.CharField(max_length=20, null=True, blank=True)
    telegram_username = models.CharField(max_length=100, null=True, blank=True)
    mijoz_turi = models.CharField(max_length=10, choices=MIJOZ_TURI_CHOICES, default='oddiy')

    def __str__(self):
        return self.nomi


# --- MAHSULOT TURI ---
class MahsulotTuri(models.Model):
    nomi = models.CharField(max_length=100)  # kg, dona, l

    def __str__(self):
        return self.nomi


# --- MAHSULOT ---
class Mahsulot(models.Model):
    WAREHOUSE_TYPES = (
        ('finished', 'Tayyor mahsulotlar ombori'),
        ('semi_finished', 'Ombor mahsulotlari'),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    nomi = models.CharField(max_length=255)
    rasmi = models.ImageField(upload_to='mahsulotlar/')
    narxi = models.DecimalField(max_digits=10, decimal_places=2)
    tannarx = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Yakuniy tannarx — avtomatik hisoblanadi, qo'lda tahrirlanmaydi")
    baza_tannarx = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Amortizatsiya/qo'shimcha xarajatlarsiz asosiy tannarx — distributor uchun kirim narxi, ishlab chiqaruvchi uchun retsept bo'yicha hisoblangan qism",
    )
    MAHSULOT_TURI_CHOICES = (
        ('ishlab_chiqariladigan', "Ishlab chiqariladigan (retsept asosida)"),
        ('distributor', "Distributor (tayyor sotib olinadigan)"),
    )
    mahsulot_turi = models.CharField(
        max_length=25, choices=MAHSULOT_TURI_CHOICES, default='ishlab_chiqariladigan',
        help_text="Faqat 'finished' turdagi mahsulotlar uchun ma'noli",
    )
    ishlab_chiqarish_narxi = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="1 dona ishlab chiqargani uchun ishchiga to'lanadigan summa (ish_haqi_turi=per_unit bo'lsa ishlatiladi)",
    )
    amortizatsiya_foizi = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Foizda (masalan 10 = 10%) — baza tannarx + qo'shimcha xarajatlar yig'indisiga ustama sifatida qo'shiladi",
    )
    turi = models.ForeignKey(MahsulotTuri, on_delete=models.CASCADE)
    miqdori = models.FloatField(default=0)
    min_miqdori = models.FloatField(default=10, help_text="Bu miqdordan kam bo'lsa ogohlantirish chiqadi")
    warehouse_type = models.CharField(max_length=20, choices=WAREHOUSE_TYPES, default='finished')
    OMBOR_TURI_CHOICES = (
        ('xom_ashyo', "Xom ashyo"),
        ('yarim_tayyor', "Yarim tayyor mahsulot"),
    )
    ombor_turi = models.CharField(
        max_length=20, choices=OMBOR_TURI_CHOICES, default='xom_ashyo',
        help_text="Faqat 'semi_finished' mahsulotlar uchun ma'noli",
    )
    is_savdogar_product = models.BooleanField(default=False)

    SERIAL_GRANULARITY_CHOICES = (
        ('none', "Yo'q"),
        ('batch', "Partiya bo'yicha (1 QR = 1 ishlab chiqarish yozuvi)"),
        ('unit', "Har bir donaga alohida QR"),
    )
    serial_granularity = models.CharField(
        max_length=10, choices=SERIAL_GRANULARITY_CHOICES, default='none',
        help_text="Ishlab chiqarishda avtomatik QR/serial yaratilsinmi",
    )
    yaroqlilik_kun_soni = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Ishlab chiqarilgan sanadan necha kun yaroqli (bo'sh = muddat ko'rsatilmaydi)",
    )
    qr_tavsif = models.TextField(
        blank=True, default="",
        help_text="Public QR sahifasida ko'rsatiladigan matn (tarkib, foydalanish, ogohlantirish va h.k.)",
    )

    def __str__(self):
        return self.nomi

    @property
    def past_zaxira(self):
        """Zaxira minimal chegaradan past bo'lsa True qaytaradi"""
        return self.miqdori < self.min_miqdori


# --- PAZANDA (User vorisi) ---
class Pazanda(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    tuliq_ismi = models.CharField(max_length=255)
    turi = models.CharField(max_length=100, blank=True, null=True)
    rasmi = models.ImageField(upload_to='pazandalar/')

    def __str__(self):
        return self.tuliq_ismi


# --- ISHLAB CHIQARUVCHIGA BIRIKTIRILGAN MAHSULOT ---
class PazandaMahsulot(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    pazanda = models.ForeignKey(Pazanda, on_delete=models.CASCADE, related_name='biriktirilgan_mahsulotlar')
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE, related_name='masul_ishlab_chiqaruvchilar')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ishlab chiqaruvchiga biriktirilgan mahsulot"
        verbose_name_plural = "Ishlab chiqaruvchiga biriktirilgan mahsulotlar"
        unique_together = ('pazanda', 'mahsulot')

    def __str__(self):
        return f"{self.pazanda.tuliq_ismi} - {self.mahsulot.nomi}"


# --- YETKAZIB BERUVCHI ---
class YetkazibBeruvchi(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    tuliq_ismi = models.CharField(max_length=255)
    rasmi = models.ImageField(upload_to='yetkazib/')
    bmh = models.TextField(verbose_name="Biriktirilgan mashina haqida")
    bmr = models.ImageField(upload_to='mashina_rasmlar/')
    mahsulotlar = models.TextField(null=True, blank=True)
    
    # Location tracking
    last_lat = models.FloatField(null=True, blank=True)
    last_lng = models.FloatField(null=True, blank=True)
    last_active = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.tuliq_ismi

class LocationHistory(models.Model):
    yetkazib_beruvchi = models.ForeignKey(YetkazibBeruvchi, on_delete=models.CASCADE, related_name='location_history')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    lat = models.FloatField()
    lng = models.FloatField()
    timestamp = models.DateTimeField(default=timezone.now)
    client_timestamp = models.DateTimeField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=30, default='websocket')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Joylashuv tarixi"
        verbose_name_plural = "Joylashuv tarixlari"

    def __str__(self):
        return f"{self.yetkazib_beruvchi.tuliq_ismi} - {self.timestamp}"


# --- MIQDOR QO‘SHISH ---
class MiqdorQoshish(models.Model):
    pazanda = models.ForeignKey(Pazanda, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE)
    vaqt_sana = models.DateTimeField(auto_now_add=True)
    miqdor = models.FloatField()
    tasdiqlangan = models.BooleanField(default=False)
    ariza_text = models.TextField(blank=True, null=True)
    rasmi = models.ImageField(upload_to='miqdor_qoshish/', blank=True, null=True)

    # Retsept (BOM) asosida hisoblanadigan qiymatlar — tasdiqlash vaqtida "surat" sifatida saqlanadi
    tannarx_snapshot = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    jarima_summasi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ish_haqi_summasi = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # "✓ Bo'ldim" havolasi orqali (pazanda_dashboard.html) qaysi material
    # so'rovi asosida yaratilganini eslab qolish uchun. `consumed_in`
    # (ProductionMaterialRequest'da) faqat BOM/retsept mavjud bo'lganda,
    # tasdiqlash vaqtida yoziladi — retseptsiz mahsulotlarda (masalan BOM
    # kiritilmagan xom ashyo) hech qachon yozilmaydi, shuning uchun
    # "Bo'ldim" tugmasi qayta-qayta bosilib, bir xil so'rov uchun bir
    # nechta MiqdorQoshish (dublikat) yaratilishi mumkin edi. Bu maydon
    # BOM borligi/yo'qligidan qat'i nazar, "bu so'rov uchun allaqachon
    # miqdor yuborilgan" holatini aniq belgilaydi.
    source_material_request = models.ForeignKey(
        'ProductionMaterialRequest', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='miqdor_qoshishlar',
    )

    # Desktop Agent "Task Panel" orqali (103-qadam) yakunlangan bo'lsa —
    # qaysi ProductionTask'dan kelganini eslab qolish uchun. Eski (web
    # forma) yo'lda bo'sh qoladi.
    source_task = models.ForeignKey(
        'ProductionTask', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='miqdor_qoshishlar', unique=True,
        help_text="Har bir vazifada FAQAT bitta MiqdorQoshish/Serial partiyasi bo'lishi "
                  "mumkin — bu DB darajasidagi cheklov \"Ish bitdi\" ikki marta bosilib "
                  "(real sinovda kuzatilgan) dublikat QR-yorliq yaratilishining oldini oladi.",
    )

    # Vazifa (Task Panel) orqali "Ish bitdi" bosilgach Serial/QR kodlar
    # generatsiya qilinadi, lekin jismoniy chop etish Desktop Agent
    # stansiyasida, KEYINGI badge skanida sodir bo'ladi (158-qadamdan
    # keyin — pazanda tortish/o'ram ishlarini tugatgandan keyin alohida
    # "Ish bitdi" tugmasini bosishi kerak, printer darhol emas). Shu
    # bosqichgacha `False`, chop etilgach (yoki serial umuman yo'q bo'lsa
    # darhol) `True` bo'ladi — qayta-qayta chop etilib ketmasligi uchun.
    labels_printed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.pazanda} - {self.mahsulot}"


# --- SERIAL (QR kuzatuv) ---
class Serial(models.Model):
    HOLAT_CHOICES = (
        ('omborda', "Omborda"),
        ('chiqarilgan', "Chiqarilgan"),
        ('sotilgan', "Sotilgan"),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='seriallar')
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE, related_name='seriallar')
    batch = models.ForeignKey(MiqdorQoshish, on_delete=models.CASCADE, related_name='seriallar', null=True, blank=True)
    savdo = models.ForeignKey('Savdo', on_delete=models.SET_NULL, related_name='serials', null=True, blank=True)
    kod = models.CharField(max_length=64, unique=True, default=uuid4, editable=False)
    unit_index = models.PositiveIntegerField(null=True, blank=True, help_text="Bo'sh bo'lsa — butun partiyani anglatadi")
    dona_soni = models.PositiveIntegerField(
        default=1,
        help_text="Bu QR kod nechta mahsulot donasini ifodalaydi — 'unit' granularityda har doim 1, "
                   "'batch'da qadoqlash hajmiga qarab (masalan 3talik qadoq bo'lsa 3, qoldiq bo'lsa 1)",
    )
    holati = models.CharField(max_length=20, choices=HOLAT_CHOICES, default='omborda')
    yetkazib_beruvchi = models.ForeignKey(
        YetkazibBeruvchi, on_delete=models.SET_NULL, related_name='olib_chiqilgan_seriallar',
        null=True, blank=True,
        help_text="Bu donani omboradan kim olib chiqqani (yuklama tasdiqlanganda yoziladi)",
    )
    chiqarilgan_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Omboradan chiqarilgan (yuklamaga olingan) vaqt",
    )
    scan_soni = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Serial"
        verbose_name_plural = "Seriallar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.mahsulot.nomi} - {self.kod}"


class SerialHarakat(models.Model):
    """Har bir dona (Serial) bo'yicha to'liq hayot tarixi — kim ishlab
    chiqargan, kim olib chiqqan, kim sotgan, kim qaytargan. Yo'qolgan/
    o'g'irlangan dona bo'yicha zanjirni uzilmasdan kuzatish uchun."""
    EVENT_CHOICES = (
        ('yaratildi', "Ishlab chiqarildi"),
        ('chiqarildi', "Omboradan chiqarildi (yuklama)"),
        ('sotildi', "Sotildi"),
        ('qaytarildi', "Qaytarildi"),
        ('shubhali', "Shubhali — sotilmagan holda ombordan tashqarida skanerlandi"),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='serial_harakatlari')
    serial = models.ForeignKey(Serial, on_delete=models.CASCADE, related_name='harakatlar')
    event = models.CharField(max_length=15, choices=EVENT_CHOICES)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Hodisani amalga oshirgan xodim (ishlab chiqaruvchi / yetkazib beruvchi / sotuvchi)",
    )
    izoh = models.CharField(max_length=255, blank=True, default="")
    vaqt = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Serial harakati"
        verbose_name_plural = "Serial harakatlari"
        ordering = ['-vaqt']

    def __str__(self):
        return f"{self.serial.kod} - {self.get_event_display()}"


# --- SAVDO ---
class Savdo(models.Model):
    ST_CHOICES = (
        ('naqd', 'Naqd'),
        ('karta', 'Karta'),
        ('nasiya', 'Nasiya'),
    )

    haridor_dukon = models.ForeignKey(HaridorDukon, on_delete=models.CASCADE, null=True, blank=True)
    yetkazib_beruvchi = models.ForeignKey(YetkazibBeruvchi, on_delete=models.CASCADE, null=True, blank=True)
    savdogar = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='savdolar', null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    vaqt_sana = models.DateTimeField(auto_now_add=True)
    oluvchining_ismi = models.CharField(max_length=255)
    smm = models.TextField(verbose_name="Sotilgan mahsulot miqdori", blank=True, null=True)
    smr = models.ImageField(upload_to='savdo/')
    st = models.CharField(max_length=20, choices=ST_CHOICES)
    contract_number = models.PositiveIntegerField(null=True, blank=True)
    base_summa = models.FloatField(null=True, blank=True)
    summa=models.FloatField(null=True, blank=True)
    foyda = models.FloatField(
        default=0,
        help_text="Sof foyda snapshoti: sotuv paytidagi (narx - tannarx) * miqdor yig'indisi. "
                   "Kredit ustamasini o'z ichiga olmaydi — faqat mahsulot sotuvidan kelgan foyda.",
    )
    credit_down_payment = models.FloatField(default=0)
    credit_term_months = models.PositiveSmallIntegerField(null=True, blank=True)
    credit_markup_percent = models.FloatField(default=0)
    credit_due_date = models.DateField(null=True, blank=True)
    credit_contract_text = models.TextField(blank=True, null=True)
    contract_pdf = models.FileField(upload_to='savdo_contracts/pdf/', blank=True, null=True)
    signed_contract_scan = models.FileField(upload_to='savdo_contracts/signed/', blank=True, null=True)
    customer_passport_image = models.ImageField(upload_to='savdo_contracts/passports/', blank=True, null=True)
    tulandi = models.BooleanField(default=False)
    tasdiq_kutilmoqda = models.BooleanField(default=False)
    # Sotuvchining lokatsiyasi
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        customer = self.haridor_dukon.nomi if self.haridor_dukon else self.oluvchining_ismi
        return f"{customer} - {self.oluvchining_ismi}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_tulandi = None
        if not is_new:
            try:
                old_tulandi = Savdo.objects.values_list('tulandi', flat=True).get(pk=self.pk)
            except Savdo.DoesNotExist:
                pass

        # Mark for signal: True if this save transitions to paid
        self._just_became_paid = self.tulandi and (is_new or old_tulandi is False)

        super().save(*args, **kwargs)

class AmalLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    amal_shifri = models.TextField()  # Masalan: 'chiqarish|un|10'
    sana_vaqti = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.amal_shifri}"
class qaytarilgan_mahsulotlar(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Kutilmoqda'),
        (STATUS_APPROVED, 'Tasdiqlandi'),
        (STATUS_REJECTED, 'Rad etildi'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE)
    miqdor = models.FloatField()
    sana = models.DateTimeField(auto_now_add=True)
    yq = models.BooleanField(default=False)  # kept for backwards compat, use status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    def __str__(self):
        return f"{self.mahsulot} - {self.miqdor}"
class YuklamaSorov(models.Model):
    ST_CHOICES = (
        ('done', 'Done'),
        ('waiting', 'kutilmoqda'),
        ('rejected', 'Rad etildi'),
    )
    id=models.AutoField(primary_key=True)
    mode=models.CharField(max_length=20, choices=ST_CHOICES)
    pazanda=models.ForeignKey(Pazanda, on_delete=models.CASCADE, null=True, blank=True)
    user=models.ForeignKey(YetkazibBeruvchi, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    mahsulot=models.ForeignKey(Mahsulot, on_delete=models.CASCADE, null=True, blank=True)
    miqdor = models.FloatField()
    sana = models.DateTimeField(auto_now_add=True)
    tasdiq=models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.user.login} - {self.miqdor}"

# --- NASIYA TO'LOV ---
class NasiyaTolov(models.Model):
    savdo = models.ForeignKey(Savdo, on_delete=models.CASCADE, related_name='tolovlar')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    tolov_summasi = models.FloatField()
    tolov_sanasi = models.DateTimeField(auto_now_add=True)
    izoh = models.TextField(blank=True, null=True)
    qabul_qilgan_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        customer = self.savdo.haridor_dukon.nomi if self.savdo.haridor_dukon else self.savdo.oluvchining_ismi
        return f"{customer} - {self.tolov_summasi}"

    class Meta:
        verbose_name = "Nasiya To'lov"
        verbose_name_plural = "Nasiya To'lovlar"
        ordering = ['-tolov_sanasi']


# --- DELIVERY STOCK (Yangi qatlam) ---
class DeliveryStock(models.Model):
    yetkazib_beruvchi = models.ForeignKey(YetkazibBeruvchi, on_delete=models.CASCADE, related_name='stocks')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE)
    qty = models.FloatField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('yetkazib_beruvchi', 'mahsulot')
        verbose_name = "Yetkazib beruvchi zaxirasi"
        verbose_name_plural = "Yetkazib beruvchilar zaxiralari"

    def __str__(self):
        return f"{self.yetkazib_beruvchi.tuliq_ismi} - {self.mahsulot.nomi}: {self.qty}"


# --- OMBOR (ko'p-ombor poydevori — Desktop Agent uchun) ---
class Ombor(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='omborlar')
    nomi = models.CharField(max_length=255)
    manzil = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ombor"
        verbose_name_plural = "Omborlar"

    def __str__(self):
        return self.nomi


class OmborZaxira(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    ombor = models.ForeignKey(Ombor, on_delete=models.CASCADE, related_name='zaxiralar')
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE, related_name='ombor_zaxiralari')
    miqdor = models.FloatField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('ombor', 'mahsulot')
        verbose_name = "Ombor zaxirasi"
        verbose_name_plural = "Ombor zaxiralari"

    def __str__(self):
        return f"{self.ombor.nomi} - {self.mahsulot.nomi}: {self.miqdor}"


# --- XODIM SHAXSIY QR BADGE ---
class XodimBadge(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='badge')
    kod = models.CharField(max_length=64, unique=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Xodim badge"
        verbose_name_plural = "Xodim badgelari"

    def __str__(self):
        return f"{self.user.username} - {self.kod}"


class XodimDavomat(models.Model):
    """Xodim kelish-ketish hodisasi (Reception) — Desktop Agent'da badge
    skanerlanganda avtomatik yoziladi. Har bir yozuv bitta hodisa
    (kirish yoki chiqish); kunlik holat shu hodisalarning eng
    so'nggisidan aniqlanadi — shuning uchun kun davomida bir necha marta
    kirish/chiqish (masalan tushlik uchun) tabiiy qo'llab-quvvatlanadi."""
    ACTION_CHOICES = (
        ('kirish', "Keldi"),
        ('chiqish', "Ketdi"),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='davomatlar')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='davomat_hodisalari')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    vaqt = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Xodim davomati"
        verbose_name_plural = "Xodim davomatlari"
        ordering = ['-vaqt']

    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} ({self.vaqt})"


# --- STOCK HISTORY (Loglar) ---
class StockHistory(models.Model):
    EVENT_TYPES = (
        ('ADD', 'Qo\'shildi (Ishlab chiqaruvchi tomonidan)'),
        ('DEDUCT', 'Kamaytirildi (Savdo/Yuklash)'),
        ('RETURN', 'Qaytarildi'),
        ('REQUEST_APPROVED', 'Sorov tasdiqlandi'),
        ('RAW_REQUESTED', "Ishlab chiqarish uchun so'rov yuborildi"),
        ('RAW_APPROVED', 'Ombor mahsuloti berildi'),
        ('RAW_REJECTED', "Ombor mahsuloti so'rovi rad etildi"),
        ('ADJUST', 'Admin tomonidan tuzatildi'),
    )

    actor_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    yetkazib_beruvchi = models.ForeignKey(YetkazibBeruvchi, on_delete=models.CASCADE, null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    old_qty = models.FloatField()
    new_qty = models.FloatField()
    delta = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Zaxira tarixi"
        verbose_name_plural = "Zaxira tarixlari"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event_type} - {self.mahsulot.nomi} ({self.delta})"


# --- MAHSULOT RETSEPTI (BOM) ---
class MahsulotRetsept(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='retseptlar')
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE, related_name='retsept_qatorlari')
    komponent = models.ForeignKey(Mahsulot, on_delete=models.CASCADE, related_name='komponent_qatorlari')
    norma_miqdor = models.FloatField(help_text="1 dona 'mahsulot' uchun kerak bo'ladigan 'komponent' miqdori")

    class Meta:
        verbose_name = "Mahsulot retsepti"
        verbose_name_plural = "Mahsulot retseptlari"
        unique_together = ('mahsulot', 'komponent')

    def __str__(self):
        return f"{self.mahsulot.nomi} <- {self.norma_miqdor} x {self.komponent.nomi}"


# --- MAHSULOTGA BOG'LANGAN QO'SHIMCHA XARAJAT (tannarxga qo'shiladi) ---
class MahsulotQoshimchaXarajat(models.Model):
    XARAJAT_TURI_CHOICES = (
        ('miqdor', "Aniq miqdor (summa)"),
        ('foiz', "Foiz (baza tannarxga nisbatan)"),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE, related_name='qoshimcha_xarajatlar')
    nomi = models.CharField(max_length=255, help_text="Masalan: Tashish, Bojxona")
    turi = models.CharField(
        max_length=10, choices=XARAJAT_TURI_CHOICES, default='miqdor',
        help_text="Har bir firma har xil ishlaydi — ba'zilari aniq summa, ba'zilari baza tannarxdan foiz sifatida hisoblaydi",
    )
    summa = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="turi='miqdor' bo'lsa — 1 donaga to'g'ri keladigan qo'shimcha xarajat (so'm); "
                   "turi='foiz' bo'lsa — baza tannarxga nisbatan foiz (masalan 5 = 5%)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mahsulot qo'shimcha xarajati"
        verbose_name_plural = "Mahsulot qo'shimcha xarajatlari"

    def __str__(self):
        return f"{self.mahsulot.nomi} - {self.nomi}: {self.summa}"


# --- QO'SHIMCHA CHIQIM (Finance — nomli xarajatlar) ---
class QoshimchaChiqim(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='qoshimcha_chiqimlar')
    nomi = models.CharField(max_length=255, help_text="Masalan: Ijara, Svet, Transport")
    summa = models.DecimalField(max_digits=12, decimal_places=2)
    sana = models.DateField(default=timezone.now)
    izoh = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Qo'shimcha chiqim"
        verbose_name_plural = "Qo'shimcha chiqimlar"
        ordering = ['-sana']

    def __str__(self):
        return f"{self.nomi} - {self.summa}"


class ProductionMaterialRequest(models.Model):
    STATUS_CHOICES = (
        ('waiting', 'Kutilmoqda'),
        ('approved', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='material_requests')
    producer = models.ForeignKey(Pazanda, on_delete=models.CASCADE, related_name='material_requests')
    material = models.ForeignKey(Mahsulot, on_delete=models.CASCADE, related_name='production_material_requests')
    target_product = models.ForeignKey(
        Mahsulot,
        on_delete=models.SET_NULL,
        related_name='production_target_requests',
        null=True,
        blank=True,
    )
    qty = models.FloatField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='reviewed_material_requests',
        null=True,
        blank=True,
    )
    consumed_in = models.ForeignKey(
        'MiqdorQoshish',
        on_delete=models.SET_NULL,
        related_name='consumed_material_requests',
        null=True,
        blank=True,
        help_text="Norma tekshiruvi vaqtida qaysi ishlab chiqarish yozuviga hisoblab chiqilgani",
    )
    ombor = models.ForeignKey(
        'Ombor',
        on_delete=models.SET_NULL,
        related_name='material_requests',
        null=True,
        blank=True,
        help_text="Tasdiqlash vaqtida omborchi tanlaydi — qaysi ombordan berilgani",
    )
    acknowledged_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Ishlab chiqaruvchi Desktop Agent orqali \"Qabul qildim\" deb belgilagan vaqt (status'ga ta'sir qilmaydi, faqat ma'lumot uchun)",
    )
    kod = models.CharField(
        max_length=64, unique=True, default=uuid4, editable=False,
        help_text="So'rov QR kodi — chop etib jismoniy paketga yopishtirish uchun",
    )

    class Meta:
        verbose_name = "Ishlab chiqarish material so'rovi"
        verbose_name_plural = "Ishlab chiqarish material so'rovlari"
        ordering = ['-created_at']

    def __str__(self):
        target = f" -> {self.target_product.nomi}" if self.target_product else ""
        return f"{self.producer.tuliq_ismi}: {self.qty} {self.material.nomi}{target}"


# --- ISHLAB CHIQARISH VAZIFASI (Desktop Agent "Task Panel", 103-qadam) ---
class ProductionTask(models.Model):
    """Desktop Agent ishlatuvchi firmalarda "Miqdor Qo'shish"/"Material
    So'rash" o'rniga ishlatiladi: ega "bugunga 100 dona Burger" kabi
    vazifa yaratadi (faqat retsepti/BOM'i bor mahsulotlar uchun — bu
    servis darajasida tekshiriladi), istalgan ishlab chiqaruvchi uni
    agentda o'z badge'ini va shu vazifaning QR kodini skanerlab o'ziga
    oladi ("ochiq pul" — oldindan biriktirilmagan)."""
    STATUS_CHOICES = (
        ('open', "Ochiq"),
        ('claimed', "Band qilingan"),
        ('materials_ready', "Xom ashyo tortildi — \"Ish bitdi\" kutilmoqda"),
        ('producing', "Ishlab chiqarilmoqda"),
        ('done', "Bajarildi"),
        ('cancelled', "Bekor qilindi"),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='production_tasks')
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE, related_name='production_tasks')
    rejalashtirilgan_miqdor = models.FloatField(help_text="Maqsad miqdor, masalan 100 dona")
    qadoq_hajmi = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Faqat mahsulot serial_granularity='batch' bo'lganda majburiy — 1 QR kod "
                   "nechta donadan iborat qadoqni ifodalashi (masalan 3) — reja miqdoriga "
                   "bo'linmasa, qoldiq alohida-alohida (1 donalik) QR kodlar bilan chiqariladi",
    )
    sana = models.DateField(default=timezone.now, help_text="Qaysi kun uchun vazifa")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    kod = models.CharField(
        max_length=64, unique=True, default=uuid4, editable=False,
        help_text="Vazifa QR kodi — chop etib taxtaga yopishtirish uchun",
    )
    pazanda = models.ForeignKey(
        Pazanda, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='olingan_vazifalar', help_text="Kim oldi (band qilingach to'ldiriladi)",
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='yaratgan_vazifalar')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Ishlab chiqarish vazifasi"
        verbose_name_plural = "Ishlab chiqarish vazifalari"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.mahsulot.nomi} — {self.rejalashtirilgan_miqdor:g} ({self.get_status_display()})"


class TaskMaterialPickup(models.Model):
    """Vazifa yaratilganda mahsulotning BOM (MahsulotRetsept) qatorlaridan
    avtomatik hosil qilinadi — har bir xom ashyo/yarim-tayyor komponent
    uchun bittadan. `expected_qty` = `norma_miqdor * rejalashtirilgan_miqdor`,
    vazifa yaratilganda hisoblab qo'yiladi (keyin o'zgarmaydi). Desktop
    Agent'da tarozi orqali (`weigh_task_pickup`) tekshiriladi va
    tasdiqlanadi — xuddi eski `ProductionMaterialRequest` tarozi oqimidagi
    kabi tolerantlik bilan."""
    task = models.ForeignKey(ProductionTask, on_delete=models.CASCADE, related_name='material_pickups')
    komponent = models.ForeignKey(Mahsulot, on_delete=models.CASCADE, related_name='task_pickuplari')
    expected_qty = models.FloatField(help_text="BOM.norma_miqdor * task.rejalashtirilgan_miqdor")
    measured_qty = models.FloatField(null=True, blank=True)
    # Tarozi sig'imi cheklangan stansiyalarda `expected_qty` bir necha
    # ketma-ket tortishga (pour) bo'lib tortiladi — har bir tortish
    # `weigh_task_pickup`da shu maydonga qo'shib boriladi, `expected_qty`ga
    # yetganda (tolerantlik ichida) pickup yakuniy tasdiqlanadi.
    poured_qty = models.FloatField(default=0)
    tasdiqlangan = models.BooleanField(default=False)
    tasdiqlangan_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Vazifa xom ashyo olib chiqishi"
        verbose_name_plural = "Vazifa xom ashyo olib chiqishlari"
        unique_together = ('task', 'komponent')

    def __str__(self):
        return f"{self.task} <- {self.komponent.nomi} ({self.expected_qty:g})"


# --- CLICK TRANSACTION MODEL ---
class ClickTransaction(models.Model):
    STATUS_CHOICES = (
        ('processing', 'Jarayonda'),
        ('paid', 'To\'langan'),
        ('canceled', 'Bekor qilingan'),
        ('error', 'Xatolik'),
    )
    click_trans_id = models.CharField(max_length=255)
    merchant_trans_id = models.CharField(max_length=255)
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='click_transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    action = models.IntegerField(default=0)
    sign_time = models.CharField(max_length=255)
    sign_string = models.CharField(max_length=255, blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    
    create_time = models.DateTimeField(auto_now_add=True)
    perform_time = models.DateTimeField(null=True, blank=True)
    cancel_time = models.DateTimeField(null=True, blank=True)
    error_reason = models.TextField(blank=True, null=True)
    payment_reason = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"ClickTrans {self.click_trans_id} - {self.company.name} - {self.amount}"


class BillingPaymentLink(models.Model):
    STATUS_CHOICES = (
        ('created', 'Yaratilgan'),
        ('opened', 'Ochildi'),
        ('paid', 'To\'langan'),
        ('failed', 'Xatolik'),
        ('canceled', 'Bekor qilingan'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='billing_payment_links')
    token = models.CharField(max_length=64, unique=True, default=uuid4, editable=False)
    reason = models.CharField(max_length=255)
    billing_period_start = models.DateField()
    amount_usd = models.DecimalField(max_digits=12, decimal_places=2)
    amount_uzs = models.DecimalField(max_digits=14, decimal_places=2)
    click_url = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    opened_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company.name} - {self.reason} - {self.status}"


# --- KUNLIK MAQSAD (KPI) ---
class DailyTarget(models.Model):
    company  = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='daily_targets')
    user     = models.ForeignKey('User', on_delete=models.CASCADE, related_name='daily_targets')
    sana     = models.DateField()
    maqsad   = models.DecimalField(max_digits=14, decimal_places=2, help_text="Kunlik savdo maqsadi (so'm)")

    class Meta:
        unique_together = ('company', 'user', 'sana')
        verbose_name = "Kunlik maqsad"
        verbose_name_plural = "Kunlik maqsadlar"

    def __str__(self):
        return f"{self.user} — {self.sana}: {self.maqsad:,.0f} so'm"


# --- XODIM ISH HAQI (avans + oyni yopish) ---
class XodimMaosh(models.Model):
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='maosh_sozlamasi')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    oylik_maosh = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Oylik belgilangan maosh — firma 'Oylik (fiksval)' rejimida yoki "
                   "xodim ishlab chiqaruvchi bo'lmaganda ishlatiladi.",
    )
    updated_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Xodim oylik maoshi"
        verbose_name_plural = "Xodim oylik maoshlari"

    def __str__(self):
        return f"{self.user} — {self.oylik_maosh:,.0f} so'm/oy"


class XodimTolov(models.Model):
    TURI_CHOICES = (
        ('avans', "Avans"),
        ('yakuniy', "Oy yakuniy hisob-kitobi"),
    )
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='xodim_tolovlari')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    turi = models.CharField(max_length=10, choices=TURI_CHOICES)
    summa = models.DecimalField(max_digits=12, decimal_places=2)
    sana = models.DateField(default=timezone.now)
    izoh = models.TextField(blank=True, null=True)
    rasm = models.ImageField(
        upload_to='xodim_tolovlar/', blank=True, null=True,
        help_text="To'lov cheki/kvitansiyasi rasmi — qolib ketgan oylikni to'lashda majburiy.",
    )
    berdi = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='berilgan_tolovlar')
    oy_yopish = models.ForeignKey(
        'XodimOyYopish', on_delete=models.SET_NULL, null=True, blank=True, related_name='tolovlar',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sana', '-created_at']
        verbose_name = "Xodim to'lovi"
        verbose_name_plural = "Xodim to'lovlari"

    def __str__(self):
        return f"{self.user} — {self.get_turi_display()}: {self.summa:,.0f} so'm ({self.sana})"


class XodimOyYopish(models.Model):
    MANBA_CHOICES = (
        ('per_unit', "Ishlab chiqarilganga qarab"),
        ('fixed', "Belgilangan oylik"),
    )
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='oy_yopishlar')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    yil = models.PositiveSmallIntegerField()
    oy = models.PositiveSmallIntegerField()
    ishlab_topgan = models.DecimalField(max_digits=12, decimal_places=2)
    avanslar_jami = models.DecimalField(max_digits=12, decimal_places=2)
    hisoblangan_qoldiq = models.DecimalField(max_digits=12, decimal_places=2)
    tolangan_yakuniy_summa = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    manba = models.CharField(max_length=20, choices=MANBA_CHOICES)
    yopgan_user = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    izoh = models.TextField(blank=True, null=True)
    yopilgan_vaqt = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'yil', 'oy'], name='unique_oy_yopish_per_user'),
        ]
        ordering = ['-yil', '-oy']
        verbose_name = "Oylik yopish"
        verbose_name_plural = "Oylik yopishlar"

    def __str__(self):
        return f"{self.user} — {self.yil}-{self.oy:02d}"


class AgentRelease(models.Model):
    """StockFirm Desktop Agent (StockFirmAgent.exe) ning platforma
    bo'ylab bitta joriy versiyasi — superadmin yangi build yuklaganda
    yaratiladi. Firma-maxsus emas: Desktop Agent stansiyasi sotib
    olingan (`custom_desktop_agent_stations > 0`) har qanday firma egasi
    eng oxirgi (`created_at` bo'yicha eng yangi) yozuvni yuklab oladi."""
    version = models.CharField(max_length=30, help_text="Masalan: 1.4.0")
    file = models.FileField(upload_to='agent_releases/')
    izoh = models.TextField(blank=True, default="", help_text="Bu versiyada nima o'zgargani (changelog)")
    uploaded_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Agent versiyasi"
        verbose_name_plural = "Agent versiyalari"

    def __str__(self):
        return f"StockFirm Agent v{self.version}"
