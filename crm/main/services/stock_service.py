from django.db import transaction
from django.utils import timezone
from ..models import (
    Mahsulot, YetkazibBeruvchi, YuklamaSorov, 
    MiqdorQoshish, DeliveryStock, StockHistory
)

def log_stock_change(actor, mahsulot, old_qty, new_qty, event_type, yetkazib_beruvchi=None):
    """Utility to log stock movement in StockHistory."""
    delta = new_qty - old_qty
    StockHistory.objects.create(
        actor_user=actor,
        yetkazib_beruvchi=yetkazib_beruvchi,
        mahsulot=mahsulot,
        event_type=event_type,
        old_qty=old_qty,
        new_qty=new_qty,
        delta=delta
    )

@transaction.atomic
def approve_miqdor_qoshish_service(request_id, actor):
    """Approves a production request (MiqdorQoshish) and updates product stock."""
    req = MiqdorQoshish.objects.select_for_update().get(id=request_id)
    if req.tasdiqlangan:
        return False, "Ushbu ariza allaqachon tasdiqlangan."

    mahsulot = req.mahsulot
    old_qty = mahsulot.miqdori
    new_qty = old_qty + req.miqdor

    # Update Product
    mahsulot.miqdori = new_qty
    mahsulot.save()

    # Update Request Status
    req.tasdiqlangan = True
    req.save()

    # Log History
    log_stock_change(actor, mahsulot, old_qty, new_qty, 'ADD')
    
    return True, "Zaxira muvaffaqiyatli oshirildi."

@transaction.atomic
def approve_yuklama_sorov_service(request_id, actor):
    """Approves a delivery stock request (YuklamaSorov) and transfers stock from warehouse to delivery person."""
    req = YuklamaSorov.objects.select_for_update().get(id=request_id)
    if req.tasdiq:
        return False, "Ushbu so'rov allaqachon bajarilgan."

    mahsulot = req.mahsulot
    if mahsulot.miqdori < req.miqdor:
        return False, "Omborda yetarli mahsulot mavjud emas."

    # 1. Update Warehouse Stock
    old_warehouse_qty = mahsulot.miqdori
    new_warehouse_qty = old_warehouse_qty - req.miqdor
    mahsulot.miqdori = new_warehouse_qty
    mahsulot.save()
    log_stock_change(actor, mahsulot, old_warehouse_qty, new_warehouse_qty, 'DEDUCT', yetkazib_beruvchi=req.user)

    # 2. Update Delivery Stock (Modern tracking)
    ds, created = DeliveryStock.objects.get_or_create(
        yetkazib_beruvchi=req.user,
        mahsulot=mahsulot
    )
    old_ds_qty = ds.qty
    ds.qty += req.miqdor
    ds.save()

    # 3. Legacy Mahsulotlar String (Backward compatibility)
    yb = req.user
    from ..functions import mahsulotlar_miqdori, yuklama_maker
    current_yuk = mahsulotlar_miqdori(yb.mahsulotlar)
    found = False
    for y in current_yuk:
        if y.nom == mahsulot.nomi:
            y.miqdor += int(req.miqdor)
            found = True
            break
    if not found:
        # If using new_yuklama class as defined in functions.py
        from ..functions import new_yuklama
        current_yuk.append(new_yuklama(mahsulot.nomi, int(req.miqdor), mahsulot.turi.nomi, mahsulot.narxi))
    
    yb.mahsulotlar = yuklama_maker(current_yuk)
    yb.save()

    # Update Request Status
    req.mode = 'done'
    req.tasdiq = True
    req.save()

    return True, "Yuklama muvaffaqiyatli topshirildi."

@transaction.atomic
def adjust_stock_service(mahsulot_id, new_qty, actor):
    """Admin utility to adjust warehouse stock manually."""
    mahsulot = Mahsulot.objects.select_for_update().get(id=mahsulot_id)
    old_qty = mahsulot.miqdori
    mahsulot.miqdori = new_qty
    mahsulot.save()

    log_stock_change(actor, mahsulot, old_qty, new_qty, 'ADJUST')
    return True
