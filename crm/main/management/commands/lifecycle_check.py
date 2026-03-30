from django.core.management.base import BaseCommand
from django.utils import timezone
from main.models import Company, User
from main.bot_logic import send_telegram_notification
import datetime

class Command(BaseCommand):
    help = 'Checks company trial status and sends notifications'

    def handle(self, *args, **options):
        now = timezone.now()
        # Only check active companies on trial
        companies = Company.objects.filter(is_active=True, is_on_trial=True)
        
        self.stdout.write(f"Checking {companies.count()} companies on trial...")
        
        for company in companies:
            if not company.trial_expires_at:
                continue
                
            # Calculate remaining time
            delta = company.trial_expires_at - now
            # Total seconds to be precise, then convert to days
            # We want to notify exactly when it hits the "3 days left" mark roughly.
            # Using total_seconds / 86400 gives us a float of days.
            days_left_float = delta.total_seconds() / 86400
            
            owner = User.objects.filter(company=company, type='ega').first()
            if not owner or not owner.tg_id:
                # Can't notify via TG if no EGA or no TG_ID
                continue

            # Notification logic (integers for days)
            # Use rounding or simple integer conversion depending on when the command runs
            days_left = int(days_left_float)

            if 2.9 <= days_left_float <= 3.1: # 3 days left
                msg = (
                    f"⏳ <b>Sinov muddati eslatmasi!</b>\n\n"
                    f"Firma: {company.name}\n"
                    f"Sizning bepul sinov muddatingiz 3 kundan keyin tugaydi. "
                    f"Xizmatlardan uzilishlarsiz foydalanish uchun tarifni yangilashni tavsiya qilamiz."
                )
                send_telegram_notification(owner.tg_id, msg)
                self.stdout.write(f"Notified {company.name} (3 days left)")
                
            elif 0.9 <= days_left_float <= 1.1: # 1 day left
                msg = (
                    f"⚠️ <b>Muhim eslatma!</b>\n\n"
                    f"Firma: {company.name}\n"
                    f"Sizning bepul sinov muddatingiz ertaga tugaydi. "
                    f"To'lov amalga oshirilmasa, tizimga kirish vaqtincha cheklanishi mumkin."
                )
                send_telegram_notification(owner.tg_id, msg)
                self.stdout.write(f"Notified {company.name} (1 day left)")

            elif days_left_float <= 0:
                # Expired
                company.is_on_trial = False
                company.is_active = False # Suspend the company
                company.save()
                
                msg = (
                    f"❌ <b>Sinov muddati tugadi</b>\n\n"
                    f"Firma: {company.name}\n"
                    f"Sizning bepul sinov muddatingiz tugadi va tizim faoliyati to'xtatildi. "
                    f"Iltimos, xizmatni davom ettirish uchun tarifni sotib oling yoki admin bilan bog'laning."
                )
                send_telegram_notification(owner.tg_id, msg)
                self.stdout.write(self.style.SUCCESS(f"Company {company.name} suspended due to trial expiration."))

        self.stdout.write(self.style.SUCCESS("Lifecycle check completed."))
