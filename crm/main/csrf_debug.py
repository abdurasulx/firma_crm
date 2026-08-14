"""Vaqtincha diagnostika: real ishlab chiqarishda takrorlanuvchi
"CSRF token missing" xatosining haqiqiy sababini topish uchun — har bir
CSRF muvaffaqiyatsizligida serverga QANDAY ma'lumot yetib kelganini
(content-length, POST/FILES kalitlari, cookie holati) jurnalga yozadi,
so'ng odatdagi Django CSRF xato sahifasini ko'rsatadi.

Sabab aniqlangandan keyin BU FAYL VA `CSRF_FAILURE_VIEW` SOZLAMASI
OLIB TASHLANISHI KERAK — doimiy production kodida bo'lmasligi lozim."""
import sys

from django.views.csrf import csrf_failure as _default_csrf_failure


def csrf_failure(request, reason=""):
    try:
        post_keys = list(request.POST.keys())
    except Exception as exc:  # noqa: BLE001
        post_keys = f"<o'qib bo'lmadi: {exc}>"
    try:
        files_keys = list(request.FILES.keys())
    except Exception as exc:  # noqa: BLE001
        files_keys = f"<o'qib bo'lmadi: {exc}>"

    print(
        "=== CSRF FAILURE DEBUG ===\n"
        f"reason={reason!r}\n"
        f"path={request.path} method={request.method}\n"
        f"CONTENT_LENGTH={request.META.get('CONTENT_LENGTH')}\n"
        f"CONTENT_TYPE={request.META.get('CONTENT_TYPE')}\n"
        f"post_keys={post_keys}\n"
        f"files_keys={files_keys}\n"
        f"cookie_csrftoken_present={'csrftoken' in request.COOKIES}\n"
        f"cookie_csrftoken_value_len={len(request.COOKIES.get('csrftoken', ''))}\n"
        f"sessionid_present={'sessionid' in request.COOKIES}\n"
        f"user_agent={request.META.get('HTTP_USER_AGENT', '')[:250]}\n"
        f"x_forwarded_for={request.META.get('HTTP_X_FORWARDED_FOR')}\n"
        f"remote_addr={request.META.get('REMOTE_ADDR')}\n"
        "=== END CSRF FAILURE DEBUG ===",
        file=sys.stderr, flush=True,
    )
    return _default_csrf_failure(request, reason=reason)
