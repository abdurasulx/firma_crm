from django.db import transaction

from ..models import OmborZaxira


def add_ombor_stock(ombor, mahsulot, qty):
    """
    Omborga kirim — OmborZaxira'ni oshiradi. request/actor'ga bog'lanmagan —
    Desktop Agent kelganda xuddi shu funksiyani chaqiradi.
    """
    zaxira, _ = OmborZaxira.objects.get_or_create(
        ombor=ombor, mahsulot=mahsulot, defaults={'company': ombor.company},
    )
    zaxira.miqdor += qty
    zaxira.save(update_fields=['miqdor', 'updated_at'])
    return zaxira


@transaction.atomic
def deduct_ombor_stock(ombor, mahsulot, qty):
    """
    Ombordan chiqim (material so'rovi tasdiqlanganda). Yetarli miqdor bo'lmasa
    (False, xabar) qaytaradi, hech narsa o'zgartirmaydi.
    """
    zaxira = OmborZaxira.objects.select_for_update().filter(ombor=ombor, mahsulot=mahsulot).first()
    if not zaxira or zaxira.miqdor < qty:
        mavjud = zaxira.miqdor if zaxira else 0
        return False, f"{ombor.nomi} omborida yetarli {mahsulot.nomi} yo'q (mavjud: {mavjud:g})."

    zaxira.miqdor -= qty
    zaxira.save(update_fields=['miqdor', 'updated_at'])
    return True, zaxira
