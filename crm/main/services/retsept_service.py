from decimal import Decimal

from django.db import transaction

from ..models import MahsulotRetsept
from .stock_service import recompute_tannarx, cascade_recompute_tannarx


def _creates_cycle(root_mahsulot, komponent):
    """komponent'ni root_mahsulot retseptiga qo'shish aylanma bog'lanish hosil qiladimi?"""
    if komponent.id == root_mahsulot.id:
        return True
    for row in MahsulotRetsept.objects.filter(mahsulot=komponent).select_related('komponent'):
        if _creates_cycle(root_mahsulot, row.komponent):
            return True
    return False


def recompute_baza_tannarx_from_bom(mahsulot):
    """
    Retsept (BOM) qatorlari yig'indisidan baza_tannarxni hisoblaydi va
    yakuniy tannarxni qayta hisoblaydi. Retsept tahrirlangan zahoti
    (production kutmasdan) chaqiriladi — foydalanuvchi jonli narx ko'rishi
    uchun. Xuddi shu formula `stock_service._apply_retsept_hisobkitob`da
    production tasdiqlanganda ham ishlatiladi — ziddiyat yo'q.
    """
    rows = MahsulotRetsept.objects.filter(mahsulot=mahsulot).select_related('komponent')
    total = sum(
        (Decimal(str(r.komponent.tannarx)) * Decimal(str(r.norma_miqdor)) for r in rows),
        Decimal('0'),
    )
    mahsulot.baza_tannarx = total
    mahsulot.save(update_fields=['baza_tannarx'])
    result = recompute_tannarx(mahsulot)
    cascade_recompute_tannarx(mahsulot)
    return result


@transaction.atomic
def add_retsept_row(company, mahsulot, komponent, norma_miqdor):
    """
    Retseptga komponent qo'shadi/yangilaydi. Narx maydoni yo'q — komponentning
    o'z tannarxi avtomatik ishlatiladi (`recompute_baza_tannarx_from_bom`
    orqali). Normadan chetlashish jarimasi alohida kiritilmaydi — mahsulotning
    o'z `ishlab_chiqarish_narxi`si bilan bir xil (`stock_service.
    _apply_retsept_hisobkitob`da ishlatiladi). Validatsiya muvaffaqiyatsiz
    bo'lsa (False, xabar) qaytaradi.
    """
    if komponent.id == mahsulot.id:
        return False, "Mahsulot o'zini komponent sifatida ishlata olmaydi."
    if komponent.warehouse_type != 'semi_finished':
        return False, "Komponent faqat 'ombor mahsulotlari' (xom ashyo/yarim tayyor) turidan bo'lishi kerak."
    if norma_miqdor <= 0:
        return False, "Norma miqdori 0 dan katta bo'lishi kerak."
    if _creates_cycle(mahsulot, komponent):
        return False, "Bu bog'lanish aylanma retsept (cycle) hosil qiladi — qo'shib bo'lmaydi."

    MahsulotRetsept.objects.update_or_create(
        company=company, mahsulot=mahsulot, komponent=komponent,
        defaults={'norma_miqdor': norma_miqdor},
    )
    recompute_baza_tannarx_from_bom(mahsulot)
    return True, None


@transaction.atomic
def delete_retsept_row(company, mahsulot, row_id):
    MahsulotRetsept.objects.filter(id=row_id, company=company, mahsulot=mahsulot).delete()
    recompute_baza_tannarx_from_bom(mahsulot)
