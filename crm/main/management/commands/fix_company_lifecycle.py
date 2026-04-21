"""
Management command to fix company lifecycle issues:
1. Auto-expire setup_mode where deadline has passed
2. Reset incorrectly set next_payment_date for new unpaid companies (backfill bug)
3. Reset has_used_trial for companies that got it incorrectly (plan approved but trial never used)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = "Firma lifecycle muammolarini tuzatish (setup_mode, next_payment_date, has_used_trial)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Faqat ko'rish, hech narsa saqlama",
        )
        parser.add_argument(
            '--reset-trial-flag',
            action='store_true',
            help="has_used_trial=True bo'lgan lekin hech qachon trial ishlatmagan firmalarni reset qilish",
        )

    def handle(self, *args, **options):
        from main.models import Company, PlanRequest

        dry_run = options['dry_run']
        reset_trial = options['reset_trial_flag']
        now = timezone.now()
        fixed = 0

        self.stdout.write(self.style.WARNING("🔍 Firmalar tekshirilmoqda...\n"))

        for company in Company.objects.all():
            changes = []

            # 1. Setup mode auto-expire
            if company.setup_mode:
                deadline = company.setup_expires_at or (company.created_at + timedelta(days=7))
                if now > deadline:
                    changes.append(f"  ✅ setup_mode: True → False (muddati: {deadline.strftime('%d.%m.%Y %H:%M')})")
                    if not dry_run:
                        company.setup_mode = False
                        company.setup_expires_at = None

            # 2. next_payment_date — noto'g'ri backfill tizatish
            # Agar firma hech qachon to'lov qilmagan (payment_status=unpaid) va
            # next_payment_date created_at + 5 kun ga teng (backfill artefakt) bo'lsa reset
            if (
                company.next_payment_date is not None
                and company.payment_status == 'unpaid'
                and not company.is_on_trial
                and company.plan is None
                and not company.is_custom_plan
            ):
                expected_backfill = company.created_at + timedelta(days=5)
                diff = abs((company.next_payment_date - expected_backfill).total_seconds())
                if diff < 86400:  # 1 soat ichida (backfill artefakt)
                    changes.append(f"  🗑️  next_payment_date: {company.next_payment_date.strftime('%d.%m.%Y')} → NULL (backfill artefakt)")
                    if not dry_run:
                        company.next_payment_date = None

            # 3. has_used_trial reset (agar hech qachon trial ishlatilmagan bo'lsa)
            if reset_trial and company.has_used_trial:
                actually_used_trial = PlanRequest.objects.filter(
                    company=company, is_trial=True, status='approved'
                ).exists()
                if not actually_used_trial and not company.is_on_trial:
                    changes.append("  🔄 has_used_trial: True → False (trial hech qachon ishlatilmagan)")
                    if not dry_run:
                        company.has_used_trial = False

            if changes:
                self.stdout.write(f"\n🏢 {company.name} ({company.subdomain}):")
                for c in changes:
                    self.stdout.write(c)
                if not dry_run:
                    company.save()
                fixed += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  Dry-run: {fixed} ta firma o'zgartirilishi kerak. Saqlash uchun --dry-run ni olib tashlang."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ {fixed} ta firma muvaffaqiyatli tuzatildi."
            ))
