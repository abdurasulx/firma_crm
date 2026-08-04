"""Desktop Agent stansiyasi uchun QR-login shifrlash yordamchisi.

QR kod matni ikki qismdan iborat: `AGENTQR|<subdomain>|<shifrlangan_qism>`
— birinchi ikki qism ochiq (klient qaysi serverga ulanishni bilishi
uchun kerak), uchinchi qism (`user_id`+`nonce`) `cryptography.fernet.Fernet`
bilan simmetrik shifrlangan — faqat server (shu `SECRET_KEY` bilan)
buni ocha oladi, boshqa hech kim (hatto QR rasmning o'zini ko'rgan
odam ham) uning ichidagi foydalanuvchi ma'lumotini o'qiy olmaydi.

Kalit `SECRET_KEY`dan hosil qilinadi (alohida .env o'zgaruvchisi
kerak emas) — `SECRET_KEY` rotatsiya qilinsa, barcha eski QR kodlar
ham avtomatik yaroqsiz bo'ladi (xavfsizlik nuqtai nazaridan to'g'ri
xatti-harakat)."""
import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    key_material = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


def encrypt_login_payload(user_id, nonce):
    data = json.dumps({'user_id': user_id, 'nonce': str(nonce)}).encode()
    return _fernet().encrypt(data).decode()


def decrypt_login_payload(token):
    """Muvaffaqiyatli bo'lsa `{'user_id':..., 'nonce':...}` qaytaradi,
    yaroqsiz/qalbaki bo'lsa `None`."""
    try:
        data = _fernet().decrypt(token.encode())
        return json.loads(data)
    except (InvalidToken, ValueError, UnicodeDecodeError):
        return None
