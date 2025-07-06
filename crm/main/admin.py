from django.contrib import admin
from .models import (
    User, HaridorDukon, Pazanda, YetkazibBeruvchi,
    MahsulotTuri, Mahsulot, MiqdorQoshish, Savdo, YuklamaSorov
)

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .forms import CustomUserCreationForm, CustomUserChangeForm

# --- User modelini admin panelga qo‘shish ---
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    list_display = ['username', 'type', 'is_staff', 'is_active']
    list_filter = ['type', 'is_staff', 'is_active']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Shaxsiy maʼlumotlar', {'fields': ('type', 'tg_id', 'token', 'tuliq_ismi', 'tel_raqami')}),
        ('Ruxsatlar', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'type', 'tg_id', 'token', 'password1', 'password2', 'is_staff', 'is_active')}
        ),
    )
    search_fields = ('username',)
    ordering = ('username',)


# --- Haridor Dukon ---
@admin.register(HaridorDukon)
class HaridorDukonAdmin(admin.ModelAdmin):
    list_display = ('nomi', 'egasi', 'joylashuvi')
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
    list_display = ('nomi', 'narxi', 'turi', 'miqdori')
    list_filter = ('turi',)
    search_fields = ('nomi',)


# --- Miqdor Qo‘shish ---
@admin.register(MiqdorQoshish)
class MiqdorQoshishAdmin(admin.ModelAdmin):
    list_display = ('pazanda', 'mahsulot', 'vaqt_sana', 'miqdor', 'tasdiqlangan')
    list_filter = ('tasdiqlangan', 'vaqt_sana')
    search_fields = ('pazanda__tuliq_ismi', 'mahsulot__nomi')


# --- Savdo ---
@admin.register(Savdo)
class SavdoAdmin(admin.ModelAdmin):
    list_display = ('haridor_dukon', 'yetkazib_beruvchi', 'vaqt_sana', 'oluvchining_ismi', 'smm', 'st', 'tulandi', 'tasdiq_kutilmoqda')

@admin.register(YuklamaSorov)
class yuklama(admin.ModelAdmin):
    list_display = ( 'id','mahsulot','miqdor','pazanda', 'mode', 'user', 'sana', 'tasdiq')