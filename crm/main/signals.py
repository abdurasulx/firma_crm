from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='main.Savdo')
def savdo_telegram_notification(sender, instance, created, **kwargs):
    """Send Telegram notification when a sale is marked as paid."""
    savdo = instance
    if not savdo.tulandi:
        return

    # Only fire on newly paid sales (created and paid, or just became paid)
    # We use a flag set before save to detect status change
    just_paid = getattr(savdo, '_just_became_paid', False)
    if not (created or just_paid):
        return

    try:
        from .plan_utils import company_has_access, get_feature_flags
        if not company_has_access(savdo.company):
            return
        flags = get_feature_flags(savdo.company)
        if not flags.get('has_telegram_bot'):
            return

        from .bot_logic import send_telegram_notification
        from .models import User
        owner = User.objects.filter(company=savdo.company, type='ega').first()
        if not owner or not owner.tg_id:
            return

        customer_name = savdo.haridor_dukon.nomi if savdo.haridor_dukon else savdo.oluvchining_ismi
        seller_name = (
            savdo.yetkazib_beruvchi.tuliq_ismi if savdo.yetkazib_beruvchi
            else (savdo.savdogar.tuliq_ismi if savdo.savdogar else "-")
        )
        msg = (
            f"\U0001f4b0 <b>Yangi to'lov tasdiqlandi!</b>\n\n"
            f"\U0001f3e2 Mijoz: {customer_name}\n"
            f"\U0001f464 Sotuvchi: {seller_name}\n"
            f"\U0001f4b5 Summa: {savdo.summa:,.0f} so'm\n"
            f"\U0001f4c5 Vaqt: {savdo.vaqt_sana.strftime('%d.%m.%Y %H:%M') if savdo.vaqt_sana else 'Hozir'}"
        )
        send_telegram_notification(owner.tg_id, msg)
    except Exception as e:
        print(f"Telegram Notification Error: {e}")
