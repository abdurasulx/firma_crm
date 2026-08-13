from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from ..models import Company


def _resolve_company(company_or_subdomain):
    if isinstance(company_or_subdomain, Company):
        return company_or_subdomain
    if not company_or_subdomain:
        return None
    return Company.objects.filter(subdomain=str(company_or_subdomain)).first()


def create_company_notification(company_or_subdomain, title, message, notification_type='info'):
    """Real bug (bu funksiya avval hech qayerda import qilinmagan, shu
    sabab sezilmay qolgan): `AppNotification` modeli 0055-migratsiyada
    ATAYLAB o'chirilgan (endi hech qanday saqlanadigan bildirishnoma
    jadvali yo'q) — faqat jonli WebSocket "toast" xabari qoladi
    (`_notif_partial.html`dagi `showNotification`). Shu sabab bu yerda
    endi DB'ga yozish yo'q, faqat WS orqali darhol yuboriladi."""
    company = _resolve_company(company_or_subdomain)
    if not company:
        return None

    send_ws_notification(company.subdomain, title, message, notification_type)
    return True


def send_ws_notification(company_subdomain, title, message, notification_type='info', notification_id=None):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        f"notifications_{company_subdomain}",
        {
            "type": "send_notification",
            "id": notification_id,
            "title": title,
            "message": message,
            "notification_type": notification_type,
        },
    )


def notify_low_stock_if_needed(mahsulot, old_qty, new_qty):
    if not mahsulot or mahsulot.min_miqdori is None:
        return None
    if old_qty >= mahsulot.min_miqdori and new_qty < mahsulot.min_miqdori:
        return create_company_notification(
            mahsulot.company,
            "Tovar oz qoldi",
            f"{mahsulot.nomi} zaxirasi {new_qty:g} {mahsulot.turi.nomi if mahsulot.turi else ''} qoldi. Minimal chegara: {mahsulot.min_miqdori:g}.",
            "warning",
        )
    return None
