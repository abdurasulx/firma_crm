from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from uuid import uuid4

SAVDOGAR_SALES_ADDON_PRICE = Decimal("10.00")

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

    # Custom Plan Fields
    is_custom_plan = models.BooleanField(default=False)
    custom_max_users = models.IntegerField(default=5) # 0 means unlimited
    custom_has_telegram_bot = models.BooleanField(default=False)
    custom_has_analytics = models.BooleanField(default=False)
    custom_has_map = models.BooleanField(default=False)
    custom_has_savdogar_sales = models.BooleanField(default=False)
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
    def monthly_price(self):
        if self.plan:
            price = Decimal(self.plan.price or 0)
            if self.custom_has_savdogar_sales:
                price += SAVDOGAR_SALES_ADDON_PRICE
            return price
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
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'username'], name='unique_username_per_company'),
        ]

    def __str__(self):
        return f"{self.username} ({self.type})"
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
    turi = models.ForeignKey(MahsulotTuri, on_delete=models.CASCADE)
    miqdori = models.FloatField(default=0)
    min_miqdori = models.FloatField(default=10, help_text="Bu miqdordan kam bo'lsa ogohlantirish chiqadi")
    warehouse_type = models.CharField(max_length=20, choices=WAREHOUSE_TYPES, default='finished')
    is_savdogar_product = models.BooleanField(default=False)

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

    def __str__(self):
        return f"{self.pazanda} - {self.mahsulot}"


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

    class Meta:
        verbose_name = "Ishlab chiqarish material so'rovi"
        verbose_name_plural = "Ishlab chiqarish material so'rovlari"
        ordering = ['-created_at']

    def __str__(self):
        target = f" -> {self.target_product.nomi}" if self.target_product else ""
        return f"{self.producer.tuliq_ismi}: {self.qty} {self.material.nomi}{target}"


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
