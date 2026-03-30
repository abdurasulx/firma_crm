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
        from main.models import Company, User as CrmUser
        
        kunlar  = options['kunlar']
        chegara = timezone.now() - datetime.timedelta(days=kunlar)
        
        companies = Company.objects.all()
        total_count = 0
        
        for company in companies:
            self.stdout.write(f"Processing company: {company.name}")
            
            overdue = Savdo.objects.filter(
                company=company,
                st='nasiya',
                tulandi=False,
                vaqt_sana__lte=chegara
            ).select_related('haridor_dukon', 'yetkazib_beruvchi')

            company_admin = CrmUser.objects.filter(company=company, type='ega').first()
            if not company_admin:
                self.stdout.write(self.style.ERROR(f"  No admin found for {company.name}. Skipping log creation."))

            count = 0
            for savdo in overdue:
                # Qolgan qarzni hisoblash
                payments      = NasiyaTolov.objects.filter(company=company, savdo=savdo)
                total_paid    = sum(p.tolov_summasi for p in payments)
                remaining     = (savdo.summa or 0) - total_paid

                if remaining <= 0:
                    continue

                haridor  = savdo.haridor_dukon.nomi if savdo.haridor_dukon else "Noma'lum"
                kun_otdi = (timezone.now() - savdo.vaqt_sana).days

                if company_admin:
                    AmalLog.objects.create(
                        company=company,
                        user=company_admin,
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
            
            total_count += count
            self.stdout.write(self.style.SUCCESS(f"  Finished {company.name}: {count} overdue found."))

        self.stdout.write(
            self.style.SUCCESS(f"\n✅ Jami {total_count} ta muddati o'tgan nasiya aniqlandi barcha kompaniyalar bo'yicha.")
        )
