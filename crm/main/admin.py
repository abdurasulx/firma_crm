from django.contrib import admin
from .models import (
    Company, User, HaridorDukon, Pazanda, YetkazibBeruvchi,
    MahsulotTuri, Mahsulot, MiqdorQoshish, Savdo, YuklamaSorov, NasiyaTolov,
    ProductionMaterialRequest
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
    list_display = ('nomi', 'company', 'warehouse_type', 'is_savdogar_product', 'narxi', 'turi', 'miqdori')
    list_filter = ('company', 'warehouse_type', 'is_savdogar_product', 'turi')
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
    list_display = ('producer', 'material', 'target_product', 'qty', 'status', 'created_at', 'reviewed_by')
    list_filter = ('company', 'status', 'created_at')
    search_fields = ('producer__tuliq_ismi', 'material__nomi', 'target_product__nomi')
