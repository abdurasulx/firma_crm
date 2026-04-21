from django.contrib import admin
from .models import (
    Company, User, HaridorDukon, Pazanda, YetkazibBeruvchi,
    MahsulotTuri, Mahsulot, MiqdorQoshish, Savdo, YuklamaSorov, NasiyaTolov,
    ProductionMaterialRequest, BillingPaymentLink, ClickTransaction
)

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .forms import CustomUserCreationForm, CustomUserChangeForm

# --- User modelini admin panelga qo'shish ---
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    list_display = ['username', 'company', 'type', 'is_staff', 'is_active']
    list_filter = ['company', 'type', 'is_staff', 'is_active']
    fieldsets = (
        (None, {'fields': ('username', 'password', 'company')}),
        ('Shaxsiy maʼlumotlar', {'fields': ('type', 'tg_id', 'token', 'tuliq_ismi', 'tel_raqami')}),
        ('Ruxsatlar', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'company', 'type', 'tg_id', 'token', 'password1', 'password2', 'is_staff', 'is_active')}
        ),
    )
    search_fields = ('username',)
    ordering = ('username',)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'subdomain', 'created_at')
    search_fields = ('name', 'subdomain')
    fieldsets = (
        (None, {'fields': ('name', 'subdomain', 'plan', 'is_active', 'created_at')}),
        ('Custom tarif', {
            'fields': (
                'is_custom_plan',
                'custom_max_users',
                'custom_has_telegram_bot',
                'custom_has_analytics',
                'custom_has_map',
                'custom_backup_type',
                'custom_price',
                'last_backup_at',
            )
        }),
        ('Billing va lifecycle', {
            'fields': (
                'payment_status',
                'next_payment_date',
                'setup_mode',
                'setup_expires_at',
                'is_on_trial',
                'trial_expires_at',
                'has_used_trial',
            )
        }),
        ('Nasiya savdo sozlamalari', {
            'fields': (
                'credit_sales_enabled',
                'credit_contract_template',
                'credit_early_discount_percent',
                'credit_late_penalty_percent',
                'credit_rules_note',
            )
        }),
    )
    readonly_fields = ('created_at',)

# --- Haridor Dukon ---
@admin.register(HaridorDukon)
class HaridorDukonAdmin(admin.ModelAdmin):
    list_display = ('nomi', 'company', 'egasi', 'joylashuvi')
    list_filter = ('company',)
    search_fields = ('nomi', 'egasi')


# --- Pazanda ---
@admin.register(Pazanda)
class PazandaAdmin(admin.ModelAdmin):
    list_display = ('tuliq_ismi', 'turi')
    search_fields = ('tuliq_ismi',)


# --- Yetkazib Beruvchi ---
@admin.register(YetkazibBeruvchi)
class YetkazibBeruvchiAdmin(admin.ModelAdmin):
    list_display = ('tuliq_ismi', 'bmh')
    search_fields = ('tuliq_ismi', 'bmh')
    


# --- Mahsulot Turi ---
@admin.register(MahsulotTuri)
class MahsulotTuriAdmin(admin.ModelAdmin):
    list_display = ('nomi',)
    search_fields = ('nomi',)


# --- Mahsulot ---
@admin.register(Mahsulot)
class MahsulotAdmin(admin.ModelAdmin):
    list_display = ('nomi', 'company', 'warehouse_type', 'narxi', 'turi', 'miqdori')
    list_filter = ('company', 'warehouse_type', 'turi')
    search_fields = ('nomi',)


# --- Miqdor Qo'shish ---
@admin.register(MiqdorQoshish)
class MiqdorQoshishAdmin(admin.ModelAdmin):
    list_display = ('pazanda', 'company', 'mahsulot', 'vaqt_sana', 'miqdor', 'tasdiqlangan')
    list_filter = ('company', 'tasdiqlangan', 'vaqt_sana')
    search_fields = ('pazanda__tuliq_ismi', 'mahsulot__nomi')


# --- Savdo ---
@admin.register(Savdo)
class SavdoAdmin(admin.ModelAdmin):
    list_display = ('haridor_dukon', 'company', 'yetkazib_beruvchi', 'savdogar', 'vaqt_sana', 'oluvchining_ismi', 'st', 'tulandi')
    list_filter = ('company', 'st', 'tulandi')

@admin.register(YuklamaSorov)
class yuklama(admin.ModelAdmin):
    list_display = ( 'id','company', 'mahsulot','miqdor','pazanda', 'mode', 'user', 'sana', 'tasdiq')
    list_filter = ('company', 'mode', 'tasdiq')

# --- Nasiya To'lov ---
@admin.register(NasiyaTolov)
class NasiyaTolovAdmin(admin.ModelAdmin):
    list_display = ('savdo', 'company', 'tolov_summasi', 'tolov_sanasi', 'qabul_qilgan_user')
    list_filter = ('company', 'tolov_sanasi',)
    search_fields = ('savdo__haridor_dukon__nomi', 'izoh')


@admin.register(ProductionMaterialRequest)
class ProductionMaterialRequestAdmin(admin.ModelAdmin):
    list_display = ('company', 'producer', 'material', 'qty', 'status', 'created_at', 'reviewed_by')
    list_filter = ('company', 'status', 'created_at')
    search_fields = ('producer__tuliq_ismi', 'material__nomi')


@admin.register(BillingPaymentLink)
class BillingPaymentLinkAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'reason', 'amount_uzs', 'status', 'opened_at', 'paid_at', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('company__name', 'reason', 'token')
    readonly_fields = ('token', 'click_url', 'opened_at', 'paid_at', 'created_at')


@admin.register(ClickTransaction)
class ClickTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'click_trans_id', 'click_paydoc_id', 'merchant_trans_id', 'company', 'amount', 'status', 'create_time', 'perform_time')
    list_filter = ('status', 'create_time', 'perform_time')
    search_fields = ('click_trans_id', 'click_paydoc_id', 'merchant_trans_id', 'company__name')
    readonly_fields = ('create_time', 'perform_time', 'cancel_time')
