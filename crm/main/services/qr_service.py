from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ..models import Serial, SerialHarakat


def _log_harakat(serial, event, user=None, izoh=""):
    SerialHarakat.objects.create(
        company=serial.company, serial=serial, event=event, user=user, izoh=izoh,
    )


def generate_serials_for_batch(miqdor_qoshish, qadoq_hajmi=None):
    """
    MiqdorQoshish tasdiqlanganda chaqiriladi. mahsulot.serial_granularity'ga qarab
    0, N ta (batch, qadoqlash bilan) yoki N ta (unit) Serial yaratadi. Bu funksiya
    request/actor kabi web-specific narsalarga bog'lanmagan — bugun Django view,
    Desktop Agent (Task Panel) xuddi shu funksiyani chaqiradi.

    `qadoq_hajmi` — faqat `granularity == 'batch'` uchun ma'noli (110-qadamdan
    keyingi qo'shimcha, "non" misolida so'ralgan): berilsa, 1 QR = butun partiya
    o'rniga, har biri `qadoq_hajmi` donadan iborat QR kodlar generatsiya qilinadi
    (masalan 50 dona, qadoq_hajmi=3 -> 16 ta "3 donalik" + 2 ta "1 donalik" QR —
    qoldiq HAR DOIM alohida-alohida 1 donalik kodlar bilan chiqariladi, "2talik"
    kabi noaniq guruh sifatida emas). Berilmasa — eski xatti-harakat (1 QR = butun
    partiya, `dona_soni` = reja miqdori) saqlanadi, orqaga moslik uchun.
    """
    mahsulot = miqdor_qoshish.mahsulot
    granularity = mahsulot.serial_granularity

    if granularity == 'none':
        return []

    # YAKUNIY, ENG PASTKI DARAJADAGI himoya — real sinovda `MiqdorQoshish.
    # source_task` UNIQUE cheklovi (yuqori darajada) borligiga qaramasdan,
    # bitta partiya uchun Serial'lar baribir ikki marta yaratilib qolgan
    # holat kuzatildi (aniq sababi topilmadi — ehtimol boshqa jarayon/
    # so'rov qayta chaqirgan). Shu sababli bu yerda — Serial YARATISHNING
    # o'zida — qaysi yo'ldan, necha marta chaqirilishidan qat'i nazar,
    # bir marta yaratilgan partiya uchun ikkinchi marta hech qachon Serial
    # yaratilmaydigan qilib qo'yildi: agar bu partiya uchun Serial'lar
    # ALLAQACHON mavjud bo'lsa, ular qaytariladi, yangisi yaratilmaydi.
    existing = list(Serial.objects.filter(batch=miqdor_qoshish))
    if existing:
        return existing

    company = miqdor_qoshish.company
    producer_user = miqdor_qoshish.pazanda.user if miqdor_qoshish.pazanda_id else None
    total = int(miqdor_qoshish.miqdor)

    if granularity == 'batch':
        if qadoq_hajmi:
            full_packages, remainder = divmod(total, int(qadoq_hajmi))
            serials = [
                Serial.objects.create(
                    company=company, mahsulot=mahsulot, batch=miqdor_qoshish,
                    unit_index=i, dona_soni=qadoq_hajmi,
                )
                for i in range(1, full_packages + 1)
            ]
            serials += [
                Serial.objects.create(
                    company=company, mahsulot=mahsulot, batch=miqdor_qoshish,
                    unit_index=full_packages + i, dona_soni=1,
                )
                for i in range(1, remainder + 1)
            ]
        else:
            serials = [Serial.objects.create(
                company=company, mahsulot=mahsulot, batch=miqdor_qoshish, unit_index=None,
                dona_soni=total,
            )]
    elif granularity == 'unit':
        serials = [
            Serial.objects.create(
                company=company, mahsulot=mahsulot, batch=miqdor_qoshish, unit_index=i, dona_soni=1,
            )
            for i in range(1, total + 1)
        ]
    else:
        return []

    for serial in serials:
        _log_harakat(serial, 'yaratildi', user=producer_user)
    return serials


def register_scan(kod):
    """Public sahifa ochilganda chaqiriladi. Serial topilmasa None qaytaradi."""
    updated = Serial.objects.filter(kod=kod).update(scan_soni=F('scan_soni') + 1)
    if not updated:
        return None
    return Serial.objects.select_related('mahsulot', 'batch').get(kod=kod)


@transaction.atomic
def mark_serials_chiqarilgan(mahsulot, company, qty, yetkazib_beruvchi=None, serial_ids=None):
    """
    Yuklama (YuklamaSorov) tasdiqlanganda chaqiriladi.

    - `serial_ids` berilsa (Desktop Agent'da aynan skanerlangan donalar) —
      faqat o'sha seriallar chiqariladi; yetmasa qolgani FIFO bilan to'ldiriladi.
    - Berilmasa — eski xatti-harakat: FIFO, eng eski 'omborda' seriallar.

    Har bir chiqarilgan serialga `yetkazib_beruvchi` va `chiqarilgan_at`
    yoziladi hamda SerialHarakat('chiqarildi') log qo'shiladi — "bu donani
    kim olib chiqqan" savoliga keyinchalik aniq javob bo'lishi uchun.
    """
    unit_count = int(qty)
    if unit_count <= 0:
        return 0

    picked_ids = []
    if serial_ids:
        picked_ids = list(
            Serial.objects.select_for_update()
            .filter(id__in=serial_ids, company=company, mahsulot=mahsulot, holati='omborda')
            .values_list('id', flat=True)[:unit_count]
        )

    remaining = unit_count - len(picked_ids)
    if remaining > 0:
        picked_ids += list(
            Serial.objects.select_for_update()
            .filter(company=company, mahsulot=mahsulot, holati='omborda')
            .exclude(id__in=picked_ids)
            .order_by('created_at')
            .values_list('id', flat=True)[:remaining]
        )

    if not picked_ids:
        return 0

    updated = Serial.objects.filter(id__in=picked_ids).update(
        holati='chiqarilgan',
        yetkazib_beruvchi=yetkazib_beruvchi,
        chiqarilgan_at=timezone.now(),
    )

    yb_user = yetkazib_beruvchi.user if yetkazib_beruvchi else None
    for serial in Serial.objects.filter(id__in=picked_ids):
        _log_harakat(serial, 'chiqarildi', user=yb_user)

    return updated


@transaction.atomic
def mark_serials_sotilgan(serial_ids, savdo, actor=None, izoh=""):
    """Savdo yopilganda validatsiyadan o'tgan seriallarni savdoga bog'laydi,
    'sotilgan'ga o'tkazadi va har biriga SerialHarakat('sotildi') yozadi."""
    if not serial_ids:
        return 0

    updated = Serial.objects.filter(id__in=serial_ids).update(savdo=savdo, holati='sotilgan')
    for serial in Serial.objects.filter(id__in=serial_ids):
        _log_harakat(serial, 'sotildi', user=actor, izoh=izoh)
    return updated
