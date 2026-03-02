"""
Management Command: nasiya_eslatma
Muddati o'tgan nasiyalarni topib AmalLog ga yozadi.
Ishlatish: python manage.py nasiya_eslatma
Cron: 0 9 * * * cd /path/to/crm && python manage.py nasiya_eslatma
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from main.models import Savdo, NasiyaTolov, AmalLog
import datetime


class Command(BaseCommand):
    help = "Muddati o'tgan nasiyalarni topib, AmalLog ga yozadi."

    def add_arguments(self, parser):
        parser.add_argument(
            '--kunlar',
            type=int,
            default=7,
            help="Necha kundan keyin muddati o'tgan hisoblash (default: 7)"
        )

    def handle(self, *args, **options):
        kunlar  = options['kunlar']
        chegara = timezone.now() - datetime.timedelta(days=kunlar)

        overdue = Savdo.objects.filter(
            st='nasiya',
            tulandi=False,
            vaqt_sana__lte=chegara
        ).select_related('haridor_dukon', 'yetkazib_beruvchi')

        count = 0
        for savdo in overdue:
            # Qolgan qarzni hisoblash
            payments      = NasiyaTolov.objects.filter(savdo=savdo)
            total_paid    = sum(p.tolov_summasi for p in payments)
            remaining     = (savdo.summa or 0) - total_paid

            if remaining <= 0:
                continue  # Aslida to'langan bo'lsa o'tkazib yubor

            haridor  = savdo.haridor_dukon.nomi if savdo.haridor_dukon else "Noma'lum"
            kun_otdi = (timezone.now() - savdo.vaqt_sana).days

            # AmalLog ga yozish — actor sifatida birinchi admin (ega) foydalaniladi
            if not hasattr(self, '_admin_user'):
                from main.models import User as CrmUser
                try:
                    self._admin_user = CrmUser.objects.filter(type='ega').first()
                except Exception:
                    self._admin_user = None

            if self._admin_user:
                AmalLog.objects.create(
                    user=self._admin_user,
                    amal_shifri=(
                        f"nasiya_eslatma|{haridor}|{remaining:.0f}|{kun_otdi}_kun"
                    )
                )

            self.stdout.write(
                self.style.WARNING(
                    f"  ⚠️  {haridor}: {remaining:,.0f} so'm qarz, {kun_otdi} kun o'tdi"
                )
            )
            count += 1

        self.stdout.write(
            self.style.SUCCESS(f"\n✅ Jami {count} ta muddati o'tgan nasiya aniqlandi.")
        )
