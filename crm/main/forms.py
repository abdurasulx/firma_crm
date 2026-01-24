from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User, HaridorDukon

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'type', 'tg_id', 'token')

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('username', 'type', 'tg_id', 'token')
class HaridorForm(forms.ModelForm):
    class Meta:
        model = HaridorDukon
        fields = ['nomi', 'egasi', 'joylashuvi', 'dukon_rasmi', 'egasining_rasmi']