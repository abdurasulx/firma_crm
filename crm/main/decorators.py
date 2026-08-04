"""
Rol-asoslangan ruxsat decoratori.

`views.py` ichida bir xil qo'lda yozilgan tekshiruv 74 marta takrorlangan
(`if request.user.type != 'ega': return redirect('main')` va shunga
o'xshashlar) — bitta joyda unutilgan tekshiruv ruxsatsiz kirishga olib
kelishi mumkin (UPDATENEWVERSION.md #7). Bu fayl shu naqshni bitta joyga
markazlashtiradi.

Diqqat: bu — 74 ta mavjud tekshiruvni bir yo'la almashtiradigan katta
refaktor emas (bu juda katta portlash radiusiga ega bo'lardi, har birini
alohida tekshirmasdan xavfli). Hozircha decorator yangi va yuqori xavfli
viewlarga qo'llanadi, qolganlari keyingi, alohida bosqichda ko'chiriladi.
"""
from functools import wraps

from django.shortcuts import redirect


def role_required(*allowed_types):
    """View faqat ko'rsatilgan `User.type` qiymatlaridan biriga ega,
    autentifikatsiyadan o'tgan foydalanuvchilar uchun ochiq bo'lishini
    ta'minlaydi. Boshqacha holatda `main`ga yo'naltiradi (mavjud
    viewlardagi xulq-atvor bilan bir xil)."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated or request.user.type not in allowed_types:
                return redirect('main')
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
