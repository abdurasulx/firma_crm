"""
Desktop Agent uchun REST API — birinchi bosqich: faqat omborlar ro'yxatini
o'qish (read-only). Autentifikatsiya `Company.desktop_agent_token` orqali
(oddiy opaque token, `Authorization: Token <token>` header'ida yuboriladi)
— bu subdomain/sessiyaga bog'liq emas, shuning uchun bu endpoint istalgan
host (asosiy domen yoki `localhost`) orqali chaqirilishi mumkin.
"""
from urllib.parse import urlparse
from uuid import uuid4

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from django.http import Http404
from django.shortcuts import render

from .models import (
    Company, Ombor, XodimBadge, Pazanda, ProductionMaterialRequest, User, Mahsulot, StockHistory,
    MiqdorQoshish, Serial, YetkazibBeruvchi, YuklamaSorov, XodimDavomat, ProductionTask, TaskMaterialPickup,
)
from .warehouse_views import _send_ws_notification
from .services.stock_service import approve_miqdor_qoshish_service, approve_yuklama_sorov_service
from .services import qr_service, task_service

# Xom ashyo so'rovini Desktop Agent orqali (tarozi) tekshirishda ruxsat
# etiladigan chetlashish — tadbirkor bilan kelishilgan qat'iy qoida:
# ASIMMETRIK. KAM tortish deyarli umuman ruxsat etilmaydi (faqat tarozi/
# float noaniqligi uchun kichik zaxira), ORTIQCHA tortish esa 50g gacha
# normal hisoblanadi (`task_service.TASK_WEIGH_SHORTFALL_TOLERANCE`/
# `TASK_WEIGH_OVERAGE_TOLERANCE` bilan bir xil qiymatlar).
MATERIAL_WEIGH_SHORTFALL_TOLERANCE = 0.002
MATERIAL_WEIGH_OVERAGE_TOLERANCE = 0.05

# Badge skanerlangandan keyin beriladigan sessiya-tokeni uchun. Avval 90
# soniya edi (Desktop Agent'dagi 60 soniyalik UI-hisoblagichdan biroz
# uzunroq, faqat tarmoq kechikishi uchun zaxira sifatida mo'ljallangan)
# — lekin real ishlab chiqarish jarayoni (xom ashyo tortish, tayyorlash,
# 12+ ta QR-yorliqni chop etib yopishtirish, so'ng har birini birma-bir
# skanerlash) osongina bir necha daqiqa, hatto undan ko'proq davom etishi
# mumkin ekani real sinovda aniqlandi ("Sessiya-token yo'q yoki muddati
# tugagan" xatosi) — shuning uchun 1 soatgacha kengaytirildi. Desktop
# Agent'ning o'z 60/120 soniyalik faolsizlik-hisoblagichi (`SESSION_
# TIMEOUT_SECONDS`/`DELIVERY_SESSION_TIMEOUT_SECONDS`) UI darajasida hamon
# ishlaydi — bu faqat token imzosining eng uzoq umri, xavfsizlik nuqtai
# nazaridan past-xavfli ichki API uchun 1 soat yetarlicha qisqa.
BADGE_SESSION_SALT = 'desktop-agent-badge-session'
BADGE_SESSION_MAX_AGE = 3600


AGENT_ONLINE_THRESHOLD_SECONDS = User.AGENT_ONLINE_THRESHOLD_SECONDS


def _extract_token(request):
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Token '):
        return auth_header[len('Token '):].strip()
    return request.headers.get('X-Agent-Token', '').strip()


def _public_scan_url(company, kod):
    """QR-yorliqqa jismonan chop etiladigan (mahsulotga yopishtiriladigan)
    manzil — atayin `request.build_absolute_uri()` ISHLATILMAYDI, chunki
    Desktop Agent'ning so'rovi qaysi host orqali serverga yetib kelgani
    (test/lokal tunnel, IP va h.k.) tasodifiy bo'lishi mumkin. Mahsulotga
    bosib chiqariladigan QR har doim haqiqiy, xaridor telefonidan
    ochadigan PUBLIC domenga (`https://<firma>.stockfirm.uz/p/<kod>/`)
    ishora qilishi shart — aks holda chop etilgandan keyin QR ishlamay
    qoladi."""
    return f"https://{company.subdomain}.{settings.BASE_DOMAIN}/p/{kod}/"


def _company_from_token(request):
    """Firmani token orqali aniqlaydi. Ikki xil token qabul qilinadi:
    - `Company.desktop_agent_token` — eski, butun firma uchun umumiy token
      (orqaga moslik uchun saqlangan).
    - Istalgan foydalanuvchining shaxsiy tokeni (`/api/agent/login/` orqali
      login qilib olinadi — 72-qadamdan buyon `type='desktop_agent'` bilan
      cheklanmagan, firmaning istalgan faol hisobi kirishi mumkin)."""
    token = _extract_token(request)
    if not token:
        return None
    return _resolve_company_by_token(token)


def _resolve_company_by_token(token):
    """`_company_from_token`ning header'siz (masalan brauzer query-param
    orqali) chaqiriladigan varianti uchun umumiy mantiq."""
    if not token:
        return None

    company = Company.objects.filter(desktop_agent_token=token).first()
    if company:
        return company

    station = User.objects.filter(token=token, is_active=True).select_related('company').first()
    if station and station.company:
        return station.company

    return None


def _station_from_token(token):
    """`_resolve_company_by_token`dan farqli — aynan stansiya (`User`)
    obyektining o'zini qaytaradi (real-time online/oflayn holatini
    yozib borish uchun kerak). Eski `Company.desktop_agent_token`
    yo'li orqali kirilgan bo'lsa — bu yo'lda alohida stansiya
    (`User`) yozuvi yo'q, shuning uchun `None` qaytadi (heartbeat
    faqat shaxsiy token bilan kirgan stansiyalar uchun ma'noli)."""
    if not token:
        return None
    return User.objects.filter(token=token, is_active=True).select_related('company').first()


def _issue_badge_session_token(user, company):
    return signing.dumps({'user_id': user.id, 'company_id': company.id}, salt=BADGE_SESSION_SALT)


def _user_id_from_session_token(token, company):
    """Badge skanerlanganda berilgan sessiya-tokenini tekshiradi va undan
    `user_id`ni chiqarib oladi. Mijozdan to'g'ridan-to'g'ri `user_id`
    qabul qilish o'rniga shu ishlatiladi — aks holda kompaniya tokeniga
    ega har qanday stansiya istalgan xodim nomidan so'rov ko'rishi/
    tasdiqlashi mumkin bo'lardi (UPDATENEWVERSION.md #4)."""
    if not token:
        return None
    try:
        data = signing.loads(token, salt=BADGE_SESSION_SALT, max_age=BADGE_SESSION_MAX_AGE)
    except signing.BadSignature:
        return None
    if data.get('company_id') != company.id:
        return None
    return data.get('user_id')


def _issue_station_token(station, company):
    """Ikkala login yo'li (parol va QR) uchun umumiy — token yangilanadi
    (eski token bekor bo'ladi, bitta faol Desktop Agent sessiyasi
    qoidasi), javob shakli ikkalasida ham bir xil bo'lishi uchun."""
    station.token = uuid4().hex
    station.save(update_fields=['token'])
    return {
        'token': station.token,
        'company': company.name,
        'station_name': station.tuliq_ismi or station.username,
    }


@api_view(['POST'])
def agent_station_login(request):
    """Desktop Agent stansiyasi birinchi marta ishga tushirilganda (yoki
    qayta ulanganda) chaqiriladi: firma subdomeni + login/parol orqali
    shaxsiy token oladi. Bu token keyingi barcha so'rovlarda
    `Authorization: Token <token>` sifatida ishlatiladi.

    Asosiy saytdagi login (`views.login`) bilan bir xil mantiq: alohida
    "Desktop Agent" turida hisob yaratish shart emas — firmaning istalgan
    faol foydalanuvchisi (`ega`, `omborchi`, maxsus yaratilgan
    `desktop_agent` stansiyasi va h.k.) o'z login/paroli bilan shu yerdan
    ham kira oladi. Bir nechta stansiya bir xil hisob bilan kirsa ham
    muammo emas — har biri kirishda o'zining alohida `token`ini oladi
    (avvalgi token bekor bo'ladi).

    145-qadamdan buyon bu — **fallback** yo'l; standart usul QR kod
    orqali (`agent_login_by_qr`, pastda) — qo'lda login/parol kiritish
    endi majburiy emas."""
    subdomain = (request.data.get('subdomain') or '').strip()
    username = (request.data.get('username') or '').strip()
    password = request.data.get('password') or ''

    if not subdomain or not username or not password:
        return Response(
            {'detail': "'subdomain', 'username' va 'password' kerak."}, status=status.HTTP_400_BAD_REQUEST,
        )

    company = Company.objects.filter(subdomain=subdomain).first()
    if not company:
        return Response({'detail': "Firma topilmadi."}, status=status.HTTP_404_NOT_FOUND)

    station = User.objects.filter(company=company, username=username).first()
    if not station or not station.check_password(password):
        return Response({'detail': "Login yoki parol noto'g'ri."}, status=status.HTTP_401_UNAUTHORIZED)

    if not station.is_active:
        return Response({'detail': "Bu hisob faol emas."}, status=status.HTTP_403_FORBIDDEN)

    return Response(_issue_station_token(station, company))


@api_view(['POST'])
def agent_login_by_qr(request):
    """Desktop Agent stansiyasini **shifrlangan QR kod** orqali kiritadi —
    qo'lda login/parol o'rniga standart usul (145-qadam). Veb ERP'da
    (`agent_login_qr_image`, faqat `ega` ko'radi) ko'rsatilgan QR
    kodning matni `AGENTQR|<subdomain>|<shifrlangan_qism>` shaklida —
    klient birinchi ikki qismdan qaysi serverga ulanishni biladi,
    uchinchi (shifrlangan) qismni esa o'zgartirmasdan shu yerga
    yuboradi — faqat server (`SECRET_KEY` bilan) uni ocha oladi."""
    subdomain = (request.data.get('subdomain') or '').strip()
    qr_payload = (request.data.get('qr_payload') or '').strip()

    if not subdomain or not qr_payload:
        return Response(
            {'detail': "'subdomain' va 'qr_payload' kerak."}, status=status.HTTP_400_BAD_REQUEST,
        )

    company = Company.objects.filter(subdomain=subdomain).first()
    if not company:
        return Response({'detail': "Firma topilmadi."}, status=status.HTTP_404_NOT_FOUND)

    from .services.agent_qr_crypto import decrypt_login_payload
    data = decrypt_login_payload(qr_payload)
    if not data:
        return Response({'detail': "QR kod yaroqsiz yoki buzilgan."}, status=status.HTTP_401_UNAUTHORIZED)

    station = User.objects.filter(id=data.get('user_id'), company=company).first()
    if not station or station.agent_qr_nonce != data.get('nonce'):
        return Response(
            {'detail': "QR kod eskirgan — administratordan yangisini so'rang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not station.is_active:
        return Response({'detail': "Bu hisob faol emas."}, status=status.HTTP_403_FORBIDDEN)

    return Response(_issue_station_token(station, company))


@api_view(['POST'])
def agent_verify_kiosk_unlock(request):
    """Desktop Agent kiosk-qulfini ochish uchun **faqat `ega`ning** QR
    kodini tekshiradi — `agent_login_by_qr` bilan bir xil shifrlangan
    payload (`AGENTQR|<subdomain>|<shifrlangan_qism>`) ishlatiladi, lekin
    stansiya tokeni umuman o'zgartirilmaydi (station login/identifikatsiyasi
    daxlsiz qoladi) — faqat "bu chindan ham ega'ning QR kodimi" deb
    tasdiqlaydi, shu orqali mishka/klaviatura kirish qulfi vaqtincha
    ochiladi (qulflash klient tomonda saqlanadi, bu yerda holat yo'q)."""
    subdomain = (request.data.get('subdomain') or '').strip()
    qr_payload = (request.data.get('qr_payload') or '').strip()

    if not subdomain or not qr_payload:
        return Response(
            {'detail': "'subdomain' va 'qr_payload' kerak."}, status=status.HTTP_400_BAD_REQUEST,
        )

    company = Company.objects.filter(subdomain=subdomain).first()
    if not company:
        return Response({'detail': "Firma topilmadi."}, status=status.HTTP_404_NOT_FOUND)

    from .services.agent_qr_crypto import decrypt_login_payload
    data = decrypt_login_payload(qr_payload)
    if not data:
        return Response({'detail': "QR kod yaroqsiz yoki buzilgan."}, status=status.HTTP_401_UNAUTHORIZED)

    ega_user = User.objects.filter(id=data.get('user_id'), company=company).first()
    if not ega_user or ega_user.agent_qr_nonce != data.get('nonce'):
        return Response(
            {'detail': "QR kod eskirgan — administratordan yangisini so'rang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if ega_user.type != 'ega':
        return Response(
            {'detail': "Faqat firma egasining QR kodi qulfni ocha oladi."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not ega_user.is_active:
        return Response({'detail': "Bu hisob faol emas."}, status=status.HTTP_403_FORBIDDEN)

    return Response({'ok': True, 'name': ega_user.tuliq_ismi or ega_user.username})


@api_view(['GET'])
def agent_omborlar(request):
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    omborlar = Ombor.objects.filter(company=company).order_by('nomi').values('id', 'nomi', 'manzil')
    return Response({
        'company': company.name,
        'omborlar': list(omborlar),
    })


def _badge_scan_response(request, company, badge):
    user = badge.user
    rasmi_url = user.rasmi
    if rasmi_url:
        rasmi_url = request.build_absolute_uri(rasmi_url)
    return Response({
        'type': 'badge',
        'user_id': user.id,
        'username': user.username,
        'tuliq_ismi': user.tuliq_ismi or user.username,
        'lavozim': user.get_type_display(),
        'user_type': user.type,
        'tel_raqami': user.tel_raqami or '',
        'rasmi': rasmi_url,
        'is_active': user.is_active,
        'session_token': _issue_badge_session_token(user, company),
    })


def _material_request_scan_response(material_request):
    r = material_request
    return Response({
        'type': 'material_request',
        'id': r.id,
        'material': r.material.nomi,
        'birlik': r.material.turi.nomi if r.material.turi else '',
        'qty': r.qty,
        'target_product': r.target_product.nomi if r.target_product else '',
        'producer': r.producer.tuliq_ismi or r.producer.user.username,
        'status': r.status,
        'status_display': r.get_status_display(),
        'acknowledged': r.acknowledged_at is not None,
    })


@api_view(['GET'])
def agent_badge_scan(request):
    """Skaner kamerasi o'qigan QR kodni (XodimBadge.kod) xodimga aylantiradi.

    Desktop Agent skaner oldida turgan xodimni aniqlashi uchun ishlatiladi
    (vision hujjatidagi "xodim shaxsiy QR orqali o'zini tasdiqlaydi" oqimi).

    Eslatma: yangi skanerlash uchun `agent_scan` (universal, badge VA
    material so'rovi kodlarini ham qabul qiladi) tavsiya etiladi — bu
    endpoint faqat orqaga moslik uchun saqlanmoqda.
    """
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    kod = (request.GET.get('kod') or '').strip()
    if not kod:
        return Response({'detail': "'kod' parametri kerak."}, status=status.HTTP_400_BAD_REQUEST)

    badge = XodimBadge.objects.filter(kod=kod, company=company).select_related('user').first()
    if not badge:
        return Response({'detail': "Bu QR kod hech qanday xodimga tegishli emas."}, status=status.HTTP_404_NOT_FOUND)

    return _badge_scan_response(request, company, badge)


def _kod_candidates(raw: str) -> list:
    """Skanerlangan matn ikki xil formatda bo'lishi mumkin: (1) yalang'och
    kod (masalan `XodimBadge`/`ProductionMaterialRequest` QR'lari — faqat
    ichki tizim ichida ishlatilgani uchun shunday qilingan), yoki (2)
    to'liq public URL (masalan `Serial` QR'lari — `https://.../p/<kod>/`,
    chunki mijozlar ularni oddiy telefon kamerasi bilan ham ochishi kerak).
    Ikkalasini ham qo'llab-quvvatlash uchun, agar matn URL'ga o'xshasa,
    undan oxirgi yo'l segmentini (haqiqiy kodni) ham ajratib, ikkala
    variantni ham "nomzod" sifatida qaytaramiz."""
    raw = raw.strip()
    candidates = [raw]
    if '://' in raw:
        path = urlparse(raw).path.strip('/')
        if path:
            extracted = path.split('/')[-1]
            if extracted and extracted not in candidates:
                candidates.append(extracted)
    return candidates


def _serial_scan_response(serial):
    data = {
        'type': 'serial',
        'kod': serial.kod,
        'mahsulot': serial.mahsulot.nomi,
        'holati': serial.holati,
        'holati_display': serial.get_holati_display(),
        'scan_soni': serial.scan_soni,
        'unit_index': serial.unit_index,
        'batch_miqdor': serial.batch.miqdor if serial.batch_id else None,
    }
    task = _maybe_finish_task_on_scan(serial)
    if task:
        data['task_progress'] = {
            'mahsulot': task.mahsulot.nomi,
            'count': task_service.task_progress(task),
            'max': task.rejalashtirilgan_miqdor,
            'task_done': task.status == 'done',
        }
    return Response(data)


def _maybe_finish_task_on_scan(serial):
    """Har bir dona QR'i skanerlanganda chaqiriladi ("dona-dona kuzatish",
    110-qadam) — agar bu serial `producing` holatidagi bir vazifaga
    tegishli bo'lsa va endi barcha rejalashtirilgan sonlar skanerlangan
    bo'lsa, vazifani avtomatik yakunlaydi (shtrafsiz — reja to'liq
    bajarilgan). Aks holda hech narsa qilmaydi, faqat progress
    ko'rsatish uchun `task`ni qaytaradi (agar mavjud bo'lsa)."""
    if not serial.batch_id:
        return None
    mq = serial.batch
    task = getattr(mq, 'source_task', None)
    if not task or task.status not in ('producing', 'done'):
        return None
    if task.status == 'producing':
        with transaction.atomic():
            task_locked = ProductionTask.objects.select_for_update().get(id=task.id)
            if task_locked.status == 'producing':
                # `dona_soni` yig'indisi — `batch` turida har bir skanerlangan
                # QR o'zining qadoq hajmicha (masalan 3) qo'shadi, shunchaki
                # QR soni emas (110/183-qadam: partiyalarda ham QR orqali
                # kuzatish ta'minlandi).
                count = Serial.objects.filter(batch=mq, scan_soni__gte=1).aggregate(
                    t=Sum('dona_soni'),
                )['t'] or 0
                if count >= task_locked.rejalashtirilgan_miqdor:
                    task_service.finish_production_task_service(task_locked)
                    try:
                        _send_ws_notification(
                            task_locked.company.subdomain, "Vazifa bajarildi",
                            f"{task_locked.pazanda.tuliq_ismi} {task_locked.mahsulot.nomi} vazifasini to'liq bajardi.",
                            'success', refresh=True,
                        )
                    except Exception:
                        pass
            task = task_locked
    return task


@api_view(['GET'])
def agent_scan(request):
    """Universal skanerlash endpointi — Desktop Agent skanerlagan har
    qanday QR kodni qabul qiladi va turini o'zi aniqlaydi:
      - `XodimBadge.kod` bo'lsa — `type='badge'` (xodim ma'lumoti, sessiya
        boshlash uchun `session_token` bilan birga, `agent_badge_scan`
        bilan bir xil).
      - `ProductionMaterialRequest.kod` bo'lsa — `type='material_request'`
        (77-qadamda chop etiladigan QR kodi — material, miqdor, maqsad,
        holat ma'lumoti bilan, faqat o'qish uchun; sessiya boshlamaydi).
      - `ProductionTask.kod` bo'lsa — `type='task'` (103-qadam, "Vazifalar
        paneli"da chop etilgan QR — taxtaga yopishtirilgan). Faqat faol
        badge-sessiya (`session_token` GET parametri) bilan ishlaydi —
        skanerlagan xodim shu vazifani o'ziga oladi (band qiladi), yoki
        agar allaqachon o'zi band qilgan bo'lsa — qolgan xom ashyo
        navbatini qaytaradi.
      - `Serial.kod` bo'lsa (yoki uning public URL shaklidagi to'liq QR
        matni) — `type='serial'` (masalan XPrinter orqali chop etilgan
        yorliqni sinov uchun skanerlaganda — mahsulot/holat ma'lumoti
        bilan, faqat o'qish uchun, hech narsa o'zgartirmaydi).
    Hech biriga mos kelmasa — 404.
    """
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    kod = (request.GET.get('kod') or '').strip()
    if not kod:
        return Response({'detail': "'kod' parametri kerak."}, status=status.HTTP_400_BAD_REQUEST)

    candidates = _kod_candidates(kod)

    badge = XodimBadge.objects.filter(kod__in=candidates, company=company).select_related('user').first()
    if badge:
        return _badge_scan_response(request, company, badge)

    material_request = ProductionMaterialRequest.objects.filter(kod__in=candidates, company=company).select_related(
        'material', 'material__turi', 'target_product', 'producer', 'producer__user',
    ).first()
    if material_request:
        return _material_request_scan_response(material_request)

    task = ProductionTask.objects.filter(kod__in=candidates, company=company).first()
    if task:
        return _task_scan_response(request, company, task)

    for candidate in candidates:
        if Serial.objects.filter(kod=candidate, company=company).exists():
            serial = qr_service.register_scan(candidate)  # scan_soni'ni ham oshiradi
            if serial:
                return _serial_scan_response(serial)

    return Response({'detail': "Bu QR kod hech qanday narsaga tegishli emas."}, status=status.HTTP_404_NOT_FOUND)


def _task_pickup_dict(pickup):
    """`ProductionMaterialRequest` navbati bilan bir xil shakl — Desktop
    Agent'dagi mavjud tortish (weigh) UI/navbat mashinasini qayta
    ishlatish uchun ataylab shunday qilingan."""
    return {
        'id': pickup.id,
        'material': pickup.komponent.nomi,
        'birlik': pickup.komponent.turi.nomi if pickup.komponent.turi else '',
        'qty': pickup.expected_qty,
        # Tarozi sig'imi cheklangan stansiyalarda bir necha tortishga
        # bo'linadi — agent qayta ulanganda ("badge sessiyasi qayta
        # boshlansa" kabi) qaysi porsiyada to'xtaganini shu ikkitasidan
        # biladi.
        'poured': pickup.poured_qty,
        'remaining': max(pickup.expected_qty - pickup.poured_qty, 0),
        'rasmi': None,
        'target_product': pickup.task.mahsulot.nomi,
    }


def _task_scan_response(request, company, task):
    session_token = request.GET.get('session_token', '')
    user_id = _user_id_from_session_token(session_token, company)
    if not user_id:
        return Response(
            {'detail': "Avval o'z badge'ingizni skanerlang, so'ng vazifa QR kodini skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    pazanda = Pazanda.objects.filter(user_id=user_id, company=company).first()
    if not pazanda:
        return Response({'detail': "Bu foydalanuvchi ishlab chiqaruvchi emas."}, status=status.HTTP_404_NOT_FOUND)

    claimed, err = task_service.claim_task(task.kod, pazanda, company)
    if err:
        return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)

    pickups = claimed.material_pickups.filter(tasdiqlangan=False).select_related('komponent', 'komponent__turi')
    return Response({
        'type': 'task',
        'id': claimed.id,
        'mahsulot': claimed.mahsulot.nomi,
        'rejalashtirilgan_miqdor': claimed.rejalashtirilgan_miqdor,
        'pickups': [_task_pickup_dict(p) for p in pickups],
    })


@api_view(['GET'])
def agent_my_task_pickups(request):
    """Badge sessiyasi boshlanganda avtomatik chaqiriladi — ishlab
    chiqaruvchining o'ziga tayinlangan ('claimed', o'zi yaratgan yoki ega
    tomonidan biriktirilgan) vazifalaridagi hali tortilmagan xom ashyo
    qatorlarini qaytaradi. Bu orqali o'ziga o'zi yaratgan vazifalar uchun
    alohida vazifa-QR skanerlash shart emas — u allaqachon o'ziniki."""
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.GET.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    pazanda = Pazanda.objects.filter(user_id=user_id, company=company).first()
    if not pazanda:
        return Response({'detail': "Bu foydalanuvchi ishlab chiqaruvchi emas."}, status=status.HTTP_404_NOT_FOUND)

    pickups = TaskMaterialPickup.objects.filter(
        task__company=company, task__pazanda=pazanda, task__status='claimed', tasdiqlangan=False,
    ).select_related('komponent', 'komponent__turi', 'task', 'task__mahsulot').order_by('task__created_at')

    return Response({'so_rovlar': [_task_pickup_dict(p) for p in pickups]})


@api_view(['GET'])
def agent_material_requests(request):
    """Xodim (ishlab chiqaruvchi) uchun kutilayotgan xom ashyo so'rovlari.

    Stansiya sessiyasi boshlanganda (badge tasdiqlangach) chaqiriladi —
    vision hujjatidagi "tasdiqlangach, uning navbatdagi so'rovi ishga
    tushadi" oqimi. Eng eski so'rov birinchi (FIFO navbat) qaytariladi.
    """
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.GET.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    pazanda = Pazanda.objects.filter(user_id=user_id, company=company).first()
    if not pazanda:
        return Response({'detail': "Bu foydalanuvchi ishlab chiqaruvchi emas."}, status=status.HTTP_404_NOT_FOUND)

    requests_qs = ProductionMaterialRequest.objects.filter(
        company=company, producer=pazanda, status='waiting',
    ).select_related('material', 'material__turi', 'target_product').order_by('created_at')

    data = [
        {
            'id': r.id,
            'material': r.material.nomi,
            'birlik': r.material.turi.nomi if r.material.turi else '',
            'qty': r.qty,
            'rasmi': request.build_absolute_uri(r.material.rasmi.url) if r.material.rasmi else None,
            'target_product': r.target_product.nomi if r.target_product else '',
            'note': r.note or '',
            'created_at': r.created_at.isoformat(),
            'acknowledged': r.acknowledged_at is not None,
        }
        for r in requests_qs
    ]
    return Response({'so_rovlar': data})


@api_view(['POST'])
def agent_acknowledge_material_request(request, request_id):
    """Ishlab chiqaruvchi Desktop Agent orqali "Qabul qildim" tugmasini
    bosganda chaqiriladi. Faqat `acknowledged_at`ni belgilaydi — so'rov
    `status`iga (hali ham 'waiting') tegmaydi, omborchi tasdiqlash oqimi
    o'zgarishsiz qoladi."""
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.data.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    req = ProductionMaterialRequest.objects.filter(
        id=request_id, company=company, producer__user_id=user_id,
    ).first()
    if not req:
        return Response({'detail': "So'rov topilmadi."}, status=status.HTTP_404_NOT_FOUND)

    if req.status != 'waiting':
        return Response(
            {'detail': "Bu so'rov endi 'kutilmoqda' holatida emas."}, status=status.HTTP_400_BAD_REQUEST,
        )

    if req.acknowledged_at is None:
        req.acknowledged_at = timezone.now()
        req.save(update_fields=['acknowledged_at'])

    return Response({'id': req.id, 'acknowledged_at': req.acknowledged_at.isoformat()})


@api_view(['POST'])
def agent_weigh_material_request(request, request_id):
    """Xom ashyo so'rovini Desktop Agent orqali tarozi bilan tekshiradi.
    Foydalanuvchi bilan kelishilgan qaror: Desktop Agent ishlatilayotgan
    firmalarda bu qadam omborchining web-sahifadagi qo'lda "Tasdiqlash"
    bosishini butunlay almashtiradi — norma (kam tortish deyarli ruxsat
    etilmaydi, 50g gacha ortiqcha normal) ichida bo'lsa so'rov shu yerning
    o'zida avtomatik tasdiqlanadi
    (zaxiradan HAQIQIY tortilgan miqdor ayiriladi, `RAW_APPROVED` yozuvi
    qo'shiladi)."""
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.data.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        measured_qty = float(request.data.get('measured_qty'))
    except (TypeError, ValueError):
        return Response({'detail': "'measured_qty' noto'g'ri."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        material_request = ProductionMaterialRequest.objects.select_for_update().select_related(
            'material', 'material__turi', 'target_product',
        ).filter(id=request_id, company=company, producer__user_id=user_id, status='waiting').first()
        if not material_request:
            return Response({'detail': "So'rov topilmadi yoki allaqachon ko'rib chiqilgan."}, status=status.HTTP_404_NOT_FOUND)

        expected = material_request.qty
        deviation = measured_qty - expected

        if deviation > MATERIAL_WEIGH_OVERAGE_TOLERANCE or deviation < -MATERIAL_WEIGH_SHORTFALL_TOLERANCE:
            direction = "ko'p" if deviation > 0 else "kam"
            return Response({
                'approved': False,
                'expected': expected,
                'measured': measured_qty,
                'detail': f"Miqdor normadan {direction} — kerakli: {expected:g}, o'lchangan: {measured_qty:g}. Qayta o'lchang.",
            })

        material = Mahsulot.objects.select_for_update().select_related('turi').get(id=material_request.material_id)
        # Zaxiradan HAQIQIY tortilgan miqdor ayiriladi (rejalashtirilgan
        # emas) — tadbirkor bilan kelishilgan qaror.
        if material.miqdori < measured_qty:
            return Response({
                'approved': False,
                'expected': expected,
                'measured': measured_qty,
                'detail': f"{material.nomi} omborda yetarli emas. Qoldiq: {material.miqdori:g} {material.turi.nomi}.",
            })

        old_qty = material.miqdori
        material.miqdori = old_qty - measured_qty
        material.save(update_fields=['miqdori'])

        material_request.status = 'approved'
        material_request.reviewed_at = timezone.now()
        material_request.acknowledged_at = material_request.acknowledged_at or timezone.now()
        material_request.save(update_fields=['status', 'reviewed_at', 'acknowledged_at'])

        StockHistory.objects.create(
            actor_user=None, company=company, mahsulot=material, event_type='RAW_APPROVED',
            old_qty=old_qty, new_qty=material.miqdori, delta=-measured_qty,
        )

    target_name = material_request.target_product.nomi if material_request.target_product else "mahsulot"
    try:
        _send_ws_notification(
            company.subdomain, "Material so'rovi tasdiqlandi",
            f"{target_name} uchun {expected:g} {material_request.material.turi.nomi} "
            f"{material_request.material.nomi} Desktop Agent (tarozi) orqali tasdiqlandi.",
            'success', refresh=True,
        )
    except Exception:
        pass

    return Response({'approved': True, 'id': material_request.id, 'expected': expected, 'measured': measured_qty})


@api_view(['POST'])
def agent_weigh_task_pickup(request, pickup_id):
    """`agent_weigh_material_request`ning "Vazifalar paneli" (103-qadam)
    varianti — vazifaning bitta BOM-komponentini tarozi orqali tekshiradi.
    Agar bu vazifaning oxirgi tasdiqlanmagan komponenti bo'lsa, vazifa
    `materials_ready` holatiga o'tadi (159-qadamdan keyin) — ishlab
    chiqarish/QR chop etish bu yerda DARHOL boshlanmaydi, pazanda
    haqiqatda tayyorlab bo'lgach veb dashboardda "Ish bitdi" tugmasini
    bosishi kerak (`pz_confirm_task_finished`)."""
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.data.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    pazanda = Pazanda.objects.filter(user_id=user_id, company=company).first()
    if not pazanda:
        return Response({'detail': "Bu foydalanuvchi ishlab chiqaruvchi emas."}, status=status.HTTP_404_NOT_FOUND)

    try:
        measured_qty = float(request.data.get('measured_qty'))
    except (TypeError, ValueError):
        return Response({'detail': "'measured_qty' noto'g'ri."}, status=status.HTTP_400_BAD_REQUEST)

    result = task_service.weigh_task_pickup(pickup_id, pazanda, measured_qty)
    if not result['approved']:
        return Response(result)

    response_data = {
        'approved': True, 'expected': result['expected'], 'measured': result['measured'],
        'poured': result.get('poured', result['expected']), 'remaining': result.get('remaining', 0),
        'pour_completed': result.get('pour_completed', True),
        'pickup_completed': result.get('pickup_completed', True),
        'materials_ready': result['materials_ready'],
    }
    if result['materials_ready']:
        try:
            _send_ws_notification(
                company.subdomain, "Xom ashyo tortildi",
                f"{pazanda.tuliq_ismi} vazifa uchun barcha xom ashyoni tortib bo'ldi — "
                "\"Ish bitdi\" bosilishi kutilmoqda.",
                'success', refresh=True,
            )
        except Exception:
            pass
    return Response(response_data)


@api_view(['GET'])
def agent_pending_print_batch(request):
    """Desktop Agent badge-sessiya boshida chaqiriladi (159-qadam) — veb
    dashboardda "Ish bitdi" bosilib, hali shu stansiyada chop etilmagan
    (`labels_printed=False`) yorliq partiyasi bo'lsa, shuni qaytaradi.
    Topilmasa `{'batch': None}`."""
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.GET.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    pazanda = Pazanda.objects.filter(user_id=user_id, company=company).first()
    if not pazanda:
        return Response({'detail': "Bu foydalanuvchi ishlab chiqaruvchi emas."}, status=status.HTTP_404_NOT_FOUND)

    mq, serials = task_service.get_pending_print_batch(pazanda, company)
    if not mq:
        return Response({'batch': None})

    serial_kodlar = [s.kod for s in serials]
    token = _extract_token(request)
    print_url = request.build_absolute_uri(
        f'/api/agent/miqdor-qoshish/{mq.id}/chop-etish/?token={token}',
    ) if serial_kodlar else None
    return Response({
        'batch': {
            'id': mq.id,
            'mahsulot': mq.mahsulot.nomi,
            'miqdor': mq.miqdor,
            'serial_soni': len(serial_kodlar),
            'print_url': print_url,
            'serials': [
                {'kod': kod, 'url': _public_scan_url(company, kod)}
                for kod in serial_kodlar
            ],
        },
    })


@api_view(['POST'])
def agent_mark_batch_printed(request):
    """Desktop Agent yorliqlarni chop etib bo'lgach (yoki chop etadigan
    hech narsa topilmagach) chaqiradi — shu partiya keyingi skanlarda
    qayta chop etishga taklif qilinmasligi uchun."""
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.data.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    pazanda = Pazanda.objects.filter(user_id=user_id, company=company).first()
    if not pazanda:
        return Response({'detail': "Bu foydalanuvchi ishlab chiqaruvchi emas."}, status=status.HTTP_404_NOT_FOUND)

    batch_id = request.data.get('batch_id')
    if not batch_id:
        return Response({'detail': "'batch_id' kerak."}, status=status.HTTP_400_BAD_REQUEST)

    task_service.mark_batch_printed(batch_id, pazanda, company)
    return Response({'ok': True})


@api_view(['GET'])
def agent_miqdor_requests(request):
    """Ishlab chiqaruvchi uchun kutilayotgan "miqdor qo'shish" so'rovlari
    (`MiqdorQoshish.tasdiqlangan=False`) — faqat Desktop Agent stansiyasi
    sotib olingan firmalarda hosil bo'ladi (`views.addmiqdor`, 82-qadam),
    boshqa firmalarda bu ro'yxat doim bo'sh (ular hamon web'da darhol
    tasdiqlanadi)."""
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.GET.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    pazanda = Pazanda.objects.filter(user_id=user_id, company=company).first()
    if not pazanda:
        return Response({'detail': "Bu foydalanuvchi ishlab chiqaruvchi emas."}, status=status.HTTP_404_NOT_FOUND)

    # Vazifadan ("Ish bitdi", 159-qadam) kelgan partiyalar bu navbatga
    # kirmasligi kerak — ular pending-print oqimida ko'rsatiladi va har bir
    # dona QR skanerlanishi orqali yakunlanadi; bu yerga tushsa avtotasdiqlash
    # ularni darhol yopib, QR yorliqlarni ikkinchi marta chop etib yuborardi.
    qs = MiqdorQoshish.objects.filter(
        company=company, pazanda=pazanda, tasdiqlangan=False, source_task__isnull=True,
    ).select_related('mahsulot').order_by('vaqt_sana')

    data = [
        {
            'id': r.id,
            'mahsulot': r.mahsulot.nomi,
            'miqdor': r.miqdor,
            'rasmi': request.build_absolute_uri(r.mahsulot.rasmi.url) if r.mahsulot.rasmi else None,
            'created_at': r.vaqt_sana.isoformat(),
        }
        for r in qs
    ]
    return Response({'so_rovlar': data})


@api_view(['POST'])
def agent_approve_miqdor_qoshish(request, request_id):
    """Ishlab chiqaruvchi Desktop Agent'da badge skanerlab, "miqdor
    qo'shish" so'rovini tasdiqlaganda chaqiriladi. Mavjud
    `approve_miqdor_qoshish_service()` (zaxira oshirish, BOM/jarima/ish
    haqi hisob-kitobi, Serial/QR generatsiya) o'zgarishsiz chaqiriladi —
    faqat omborchi/ega web-sahifasiga kirmasdan, agentning o'zidan turib.
    Yaratilgan Seriallar bo'lsa, ularni chop etish uchun sahifa manzili
    (`print_url`) qaytariladi."""
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.data.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    req = MiqdorQoshish.objects.filter(id=request_id, company=company, pazanda__user_id=user_id).first()
    if not req:
        return Response({'detail': "So'rov topilmadi."}, status=status.HTTP_404_NOT_FOUND)
    if req.tasdiqlangan:
        return Response({'detail': "Ushbu ariza allaqachon tasdiqlangan."}, status=status.HTTP_400_BAD_REQUEST)
    if req.source_task_id:
        return Response(
            {'detail': "Bu partiya vazifadan yaratilgan — har bir dona QR kodi skanerlanishi orqali yakunlanadi, bu yerda tasdiqlanmaydi."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        success, message = approve_miqdor_qoshish_service(req.id, actor=None)
    if not success:
        return Response({'detail': message}, status=status.HTTP_400_BAD_REQUEST)

    try:
        _send_ws_notification(
            company.subdomain, "Miqdor qo'shildi",
            f"{req.pazanda.tuliq_ismi} {req.miqdor:g} ta {req.mahsulot.nomi} Desktop Agent orqali tasdiqladi.",
            'success', refresh=True,
        )
    except Exception:
        pass

    serial_kodlar = list(Serial.objects.filter(batch=req).values_list('kod', flat=True))
    token = request.headers.get('Authorization', '')[len('Token '):].strip() if request.headers.get('Authorization', '').startswith('Token ') else request.headers.get('X-Agent-Token', '').strip()
    print_url = request.build_absolute_uri(f'/api/agent/miqdor-qoshish/{req.id}/chop-etish/?token={token}') if serial_kodlar else None

    # Desktop Agent'da XPrinter (TSPL) orqali to'g'ridan-to'g'ri chop etish
    # uchun — brauzer/PDF (`print_url`) o'rniga, sozlangan bo'lsa, agent
    # o'zi har bir serial uchun QR-yorliq chop etadi (`label_printer_service.py`).
    serials = [
        {'kod': kod, 'url': _public_scan_url(company, kod)}
        for kod in serial_kodlar
    ]

    return Response({
        'id': req.id,
        'mahsulot': req.mahsulot.nomi,
        'miqdor': req.miqdor,
        'serial_soni': len(serial_kodlar),
        'print_url': print_url,
        'serials': serials,
    })


def agent_miqdor_print_page(request, request_id):
    """Ishlab chiqarilgan partiyaning Serial QR kodlarini chop etish uchun
    sahifa — Desktop Agent brauzerda ochadi (`webbrowser.open`, hozircha
    XPrinter'ga xos SDK o'rniga oddiy tizim printeridan foydalaniladi).
    Login talab qilmaydi (Desktop Agent'ning o'z brauzer sessiyasi yo'q) —
    o'rniga token so'rov parametri sifatida tekshiriladi."""
    company = _resolve_company_by_token(request.GET.get('token', '').strip())
    if not company:
        raise Http404("Ruxsat yo'q")

    req = MiqdorQoshish.objects.filter(id=request_id, company=company).select_related('mahsulot').first()
    if not req:
        raise Http404("So'rov topilmadi")

    seriallar = Serial.objects.filter(batch=req).order_by('unit_index', 'id')
    return render(request, 'agent_miqdor_print.html', {
        'req': req,
        'seriallar': seriallar,
    })


@api_view(['GET'])
def agent_delivery_requests(request):
    """Yetkazib beruvchi/savdogar badge skanerlab "yuklama" sessiyasini
    boshlaganda chaqiriladi — dashboardda oldindan so'ragan (zayavka,
    mode='waiting') mahsulotlari ro'yxatini qaytaradi, agent ekranida
    "nima olishingiz kerak" sifatida ko'rsatiladi."""
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.GET.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    yb = YetkazibBeruvchi.objects.filter(user_id=user_id, company=company).first()
    if not yb:
        return Response({'detail': "Bu foydalanuvchi yetkazib beruvchi emas."}, status=status.HTTP_404_NOT_FOUND)

    so_rovlar = [
        {
            'mahsulot_id': r.mahsulot_id,
            'mahsulot': r.mahsulot.nomi if r.mahsulot else '',
            'miqdor': r.miqdor,
            'birlik': str(r.mahsulot.turi) if r.mahsulot else '',
        }
        for r in YuklamaSorov.objects.filter(
            company=company, user=yb, mode='waiting',
        ).select_related('mahsulot', 'mahsulot__turi').order_by('sana')
    ]
    return Response({'so_rovlar': so_rovlar})


@api_view(['POST'])
def agent_scan_delivery_serial(request):
    """Yetkazib beruvchi **yoki savdogar** (ikkalasi ham `YetkazibBeruvchi`
    profiliga ega — model umumiy) Desktop Agent'da badge skanerlab
    "yuklama" (yuk olish) sessiyasini boshlagach, har bir jismoniy donani
    olayotib uning Serial QR kodini skanerlaydi — bu shu donani "yuklama
    savati"ga qo'shadi (mijozning o'zi bilan kelishilgan qaror: faqat har
    bir donaga alohida QR — `serial_granularity='unit'` — yoqilgan
    mahsulotlar uchun ishlaydi). Bufer/hisob mijoz tomonda (Desktop Agent)
    saqlanadi — bu endpoint faqat bitta serialni tekshirib, mahsulot
    ma'lumotini qaytaradi."""
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.data.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    yb = YetkazibBeruvchi.objects.filter(user_id=user_id, company=company).first()
    if not yb:
        return Response({'detail': "Bu foydalanuvchi yetkazib beruvchi emas."}, status=status.HTTP_404_NOT_FOUND)

    kod = (request.data.get('kod') or '').strip()
    if not kod:
        return Response({'detail': "'kod' parametri kerak."}, status=status.HTTP_400_BAD_REQUEST)

    # QR ichida odatda serialning public URL'i (`/p/<kod>/`) bo'ladi —
    # universal skan (`agent_scan`) kabi URL'dan kod ajratib olinadi.
    candidates = _kod_candidates(kod)
    serial = Serial.objects.filter(kod__in=candidates, company=company, holati='omborda').select_related('mahsulot').first()
    if not serial:
        return Response(
            {'detail': "Bu QR kod topilmadi yoki mahsulot allaqachon omboradan chiqarilgan."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Yuklama faqat dashboardda oldindan so'ralgan (zayavka, mode='waiting')
    # mahsulotlardan olinadi — so'ralmagan mahsulot skanerlansa rad etiladi,
    # xodim uni joyiga qaytarib qo'yishi kerak.
    if not YuklamaSorov.objects.filter(
        company=company, user=yb, mahsulot=serial.mahsulot, mode='waiting',
    ).exists():
        return Response(
            {'detail': f"{serial.mahsulot.nomi} — buni so'ramagansiz. Joyiga qo'yib qo'ying."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({
        'serial_id': serial.id,
        'mahsulot_id': serial.mahsulot_id,
        'mahsulot': serial.mahsulot.nomi,
    })


@api_view(['POST'])
def agent_finalize_yuklama(request):
    """Yetkazib beruvchi yoki savdogar "Yuklamani yakunlash"ni bosganda
    chaqiriladi. Desktop Agent'da to'plangan savat
    (`items` — `[{mahsulot_id, miqdor}]`) bo'yicha har bir mahsulot uchun
    `YuklamaSorov` yaratiladi va **darhol o'zi tomonidan tasdiqlanadi** —
    lekin bu endi fizik skanerlash bilan tasdiqlangan (har bir dona Serial
    QR'i skanerlangan) — shuning uchun "o'zi so'rab-o'zi tasdiqlaydi"
    muammosi yo'q (web-formadagi xuddi shu muammoli yo'l ham agentli
    firmalar uchun alohida yopilgan, `views.py::main`ga qarang)."""
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.data.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    yb = YetkazibBeruvchi.objects.filter(user_id=user_id, company=company).first()
    if not yb:
        return Response({'detail': "Bu foydalanuvchi yetkazib beruvchi emas."}, status=status.HTTP_404_NOT_FOUND)

    items = request.data.get('items') or []
    if not isinstance(items, list) or not items:
        return Response({'detail': "Savat bo'sh."}, status=status.HTTP_400_BAD_REQUEST)

    results = []
    for item in items:
        try:
            mahsulot_id = int(item.get('mahsulot_id'))
            miqdor = float(item.get('miqdor'))
        except (TypeError, ValueError, AttributeError):
            continue
        if miqdor <= 0:
            continue

        mahsulot = Mahsulot.objects.filter(id=mahsulot_id, company=company).first()
        if not mahsulot:
            continue

        # Skanerlangan aniq donalar — 'chiqarilgan' deb FIFO bo'yicha emas,
        # aynan shu seriallar belgilanadi (kim olib chiqqani bilan birga).
        raw_serial_ids = item.get('serial_ids') or []
        serial_ids = [int(s) for s in raw_serial_ids if str(s).isdigit()]

        with transaction.atomic():
            # Dashboardda oldindan yaratilgan zayavka (mode='waiting') bo'lsa —
            # yangi so'rov ochilmaydi, aynan o'sha tasdiqlanadi (miqdor real
            # skanerlangan soniga moslanadi); bo'lmasa (eski oqim/zaxira yo'l)
            # avvalgidek yangi so'rov yaratiladi.
            req = YuklamaSorov.objects.select_for_update().filter(
                company=company, user=yb, mahsulot=mahsulot, mode='waiting',
            ).order_by('sana').first()
            if req:
                req.miqdor = miqdor
                req.save(update_fields=['miqdor'])
            else:
                req = YuklamaSorov.objects.create(
                    company=company, user=yb, mahsulot=mahsulot, miqdor=miqdor, mode='waiting',
                )
            success, message = approve_yuklama_sorov_service(req.id, actor=None, serial_ids=serial_ids)

        results.append({'mahsulot': mahsulot.nomi, 'miqdor': miqdor, 'success': success, 'detail': message})

    try:
        ok_count = sum(1 for r in results if r['success'])
        _send_ws_notification(
            company.subdomain, "Yuklama olindi",
            f"{yb.tuliq_ismi} Desktop Agent orqali {ok_count} turdagi mahsulot yukladi.",
            'success', refresh=True,
        )
    except Exception:
        pass

    return Response({'results': results})


@api_view(['POST'])
def agent_toggle_attendance(request):
    """Reception — badge skanerlanganda avtomatik chaqiriladi (istalgan
    xodim turi uchun, alohida "reception rejimi" tanlash shart emas).
    Shu xodimning bugungi eng so'nggi hodisasiga qarab avtomatik
    kirish/chiqishni belgilaydi — birinchi skan (yoki oxirgisi
    "chiqish" bo'lsa) "kirish", aks holda "chiqish" deb yoziladi. Shu
    tarzda kun davomida bir necha marta kirish/chiqish (masalan
    tushlikka chiqish) tabiiy qo'llab-quvvatlanadi."""
    company = _company_from_token(request)
    if not company:
        return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)

    user_id = _user_id_from_session_token(request.data.get('session_token'), company)
    if not user_id:
        return Response(
            {'detail': "Sessiya-token yo'q yoki muddati tugagan. Badge'ni qayta skanerlang."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    user = User.objects.filter(id=user_id, company=company).first()
    if not user:
        return Response({'detail': "Foydalanuvchi topilmadi."}, status=status.HTTP_404_NOT_FOUND)

    last_event = XodimDavomat.objects.filter(company=company, user=user).order_by('-vaqt').first()
    next_action = 'kirish' if (last_event is None or last_event.action == 'chiqish') else 'chiqish'

    event = XodimDavomat.objects.create(company=company, user=user, action=next_action)

    return Response({
        'action': event.action,
        'action_display': event.get_action_display(),
        'vaqt': event.vaqt.isoformat(),
    })


@api_view(['POST'])
def agent_heartbeat(request):
    """Desktop Agent stansiyasi fondan (`MainWindow`da QTimer orqali, ~25
    soniyada bir marta) chaqiradi — hech qanday skanerlash faoliyati
    bo'lmasa ham "men hali ishlab turibman" signalini beradi. Bu
    `User.last_agent_heartbeat`ni yangilaydi — web dashboard shu asosda
    stansiyani "onlayn"/"oflayn" deb ko'rsatadi (`User.is_agent_online`,
    `AGENT_ONLINE_THRESHOLD_SECONDS`). Faqat shaxsiy token bilan kirgan
    stansiyalar uchun ma'noli (eski umumiy `Company.desktop_agent_token`
    yo'lida alohida stansiya yozuvi yo'q — shu holatda jimgina hech narsa
    qilinmaydi, xato ham qaytarilmaydi, chunki bu holat allaqachon
    ma'lum va orqaga moslik uchun saqlanadi)."""
    token = _extract_token(request)
    station = _station_from_token(token)
    if station:
        station.last_agent_heartbeat = timezone.now()
        station.save(update_fields=['last_agent_heartbeat'])
        if station.company:
            # Dashboard darhol (sahifani qayta yuklashsiz) "onlayn" deb
            # ko'rsatishi uchun — foydalanuvchi bilan kelishilgan qaror:
            # oflayn->onlayn holat WebSocket orqali real-vaqtda push
            # qilinadi (oflaynga o'tish esa brauzer JS tomonda, heartbeat
            # kutilgan vaqtda kelmasa, mahalliy hisoblanadi).
            _send_ws_notification(
                station.company.subdomain, '', '', type='info', event='agent_heartbeat',
                extra={'station_id': station.id, 'is_online': True},
            )
        return Response({'status': 'ok', 'station': station.username})

    # Eski umumiy token yo'li — stansiya yozuvi yo'q, lekin token
    # o'zi to'g'ri bo'lsa ham xato qaytarmaymiz (orqaga moslik).
    if _resolve_company_by_token(token):
        return Response({'status': 'ok', 'station': None})

    return Response({'detail': "Token noto'g'ri yoki topilmadi."}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
def agent_logout(request):
    """Desktop Agent dasturi tozalik bilan (oyna yopilganda,
    `MainWindow.closeEvent`) yopilayotganda chaqiriladi — "oflayn"
    holatni endi 90 soniyalik heartbeat-kutish oynasini kutmasdan,
    **darhol** (WebSocket orqali) dashboardga bildiradi.

    Muhim: bu faqat "yaxshi xulq" signali — tarmoq uzilib qolsa yoki
    dastur kutilmagan tarzda yiqilib tushsa (crash), bu chaqirilmaydi,
    va stansiya baribir eski usul (heartbeat muddati o'tishi, JS
    tomonidan hisoblangan) orqali oflayn deb aniqlanadi. Shuning uchun
    `last_agent_heartbeat`ni o'chirib qo'yamiz (`None`) — endi
    `is_agent_online` darhol `False` qaytaradi, sahifa qayta
    yuklansa ham to'g'ri holat ko'rsatiladi."""
    token = _extract_token(request)
    station = _station_from_token(token)
    if station:
        station.last_agent_heartbeat = None
        station.save(update_fields=['last_agent_heartbeat'])
        if station.company:
            _send_ws_notification(
                station.company.subdomain, '', '', type='info', event='agent_heartbeat',
                extra={'station_id': station.id, 'is_online': False},
            )
    return Response({'status': 'ok'})
