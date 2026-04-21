"""
Kunlik Cron Task — StockFirm CRM

Quyidagi vazifalarni bajaradi:
  1. setup_mode avtomatik o'chirish (muddati o'tgan firmalar)
  2. Trial muddati tugashi tekshiruvi
  3. To'lov kechikishi tekshiruvi (payment_overdue)
  4. Nasiya eslatma — muddati yaqin/o'tgan savdolar uchun Telegram xabar

Ishlatish:
  python manage.py cron_tasks
  python manage.py cron_tasks --dry-run
  python manage.py cron_tasks --skip-nasiya
  python manage.py cron_tasks --skip-lifecycle
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = "Kunlik cron: setup_mode, trial, to'lov, nasiya eslatmalari"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help="Hech narsa saqlama, faqat natijani ko'rsat")
        parser.add_argument('--skip-lifecycle', action='store_true',
                            help="Firma lifecycle tekshiruvini o'tkazib yubor")
        parser.add_argument('--skip-nasiya', action='store_true',
                            help="Nasiya eslatmalarini o'tkazib yubor")

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()

        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*50}\n"
            f"🕐 StockFirm CRM Cron Task — {now.strftime('%d.%m.%Y %H:%M')}\n"
            f"{'='*50}"
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  DRY-RUN rejimi — hech narsa saqlanmaydi\n"))

        if not options['skip_lifecycle']:
            self._run_lifecycle(now, dry_run)

        if not options['skip_nasiya']:
            self._run_nasiya_reminders(now, dry_run)

        self.stdout.write(self.style.SUCCESS("\n✅ Cron task yakunlandi.\n"))

    # ──────────────────────────────────────────────────────────────────────────
    # 1. LIFECYCLE TEKSHIRUVI
    # ──────────────────────────────────────────────────────────────────────────
    def _run_lifecycle(self, now, dry_run):
        from main.models import Company
        self.stdout.write(self.style.HTTP_INFO("\n📋 Firma lifecycle tekshiruvi...\n"))

        companies = Company.objects.all()
        setup_expired = 0
        trial_expired = 0
        payment_overdue = 0

        for company in companies:
            changed = False

            # 1a. Setup mode muddati o'tgani
            if company.setup_mode:
                deadline = company.setup_expires_at or (company.created_at + timedelta(days=7))
                if now > deadline:
                    self.stdout.write(
                        f"  🔧 [{company.name}] setup_mode → OFF "
                        f"(muddat: {deadline.strftime('%d.%m.%Y')})"
                    )
                    if not dry_run:
                        company.setup_mode = False
                        company.setup_expires_at = None
                    setup_expired += 1
                    changed = True

            # 1b. Trial muddati tugashi
            if company.is_on_trial and company.trial_expires_at and now > company.trial_expires_at:
                self.stdout.write(
                    f"  ⏰ [{company.name}] Trial tugadi "
                    f"({company.trial_expires_at.strftime('%d.%m.%Y')})"
                )
                if not dry_run:
                    company.is_on_trial = False
                    company.trial_expires_at = None
                    if not company.plan and not company.is_custom_plan:
                        company.is_active = False
                        self.stdout.write(f"     ❌ [{company.name}] — tarif yo'q, deaktivlashtirildi")
                trial_expired += 1
                changed = True

            # 1c. To'lov 3+ kun kechikkan firmalar
            if (
                company.payment_status == 'unpaid'
                and company.next_payment_date
                and now > company.next_payment_date + timedelta(days=3)
            ):
                self.stdout.write(
                    f"  💸 [{company.name}] To'lov {(now - company.next_payment_date).days} kun kechikdi "
                    f"(muddati: {company.next_payment_date.strftime('%d.%m.%Y')})"
                )
                # Eslatma yubor (Telegram)
                self._notify_payment_overdue(company, dry_run)
                payment_overdue += 1
                # is_active ni o'CHIRMAYMIZ — admin o'zi hal qiladi

            if changed and not dry_run:
                company.save()

        self.stdout.write(
            f"\n  Natija: setup_mode={setup_expired} ta, "
            f"trial={trial_expired} ta, "
            f"to'lov kechikkan={payment_overdue} ta"
        )

    def _notify_payment_overdue(self, company, dry_run):
        """Egaga Telegram orqali to'lov kechikishi haqida xabar"""
        try:
            from main.models import User
            owner = User.objects.filter(company=company, type='ega').first()
            if not owner or not owner.tg_id:
                return
            days_late = (timezone.now() - company.next_payment_date).days
            msg = (
                f"⚠️ <b>To'lov eslatmasi!</b>\n\n"
                f"🏢 Firma: {company.name}\n"
                f"📅 To'lov muddati: {company.next_payment_date.strftime('%d.%m.%Y')}\n"
                f"⏳ Kechikish: <b>{days_late} kun</b>\n\n"
                f"💡 Iltimos, tizimga kiring va to'lovni amalga oshiring."
            )
            if not dry_run:
                from main.bot_logic import send_telegram_notification
                send_telegram_notification(owner.tg_id, msg)
                self.stdout.write(f"     📨 Telegram xabar yuborildi: {owner.tg_id}")
            else:
                self.stdout.write(f"     [DRY-RUN] Telegram xabar: {owner.tg_id} → '{msg[:60]}...'")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"     ❌ Telegram xato: {e}"))

    # ──────────────────────────────────────────────────────────────────────────
    # 2. NASIYA ESLATMALARI
    # ──────────────────────────────────────────────────────────────────────────
    def _run_nasiya_reminders(self, now, dry_run):
        from main.models import Savdo, NasiyaTolov
        from django.db.models import Sum

        self.stdout.write(self.style.HTTP_INFO("\n🧾 Nasiya eslatmalari tekshiruvi...\n"))

        # Nasiya savdolar: to'lanmagan (tulandi=False), yoki qisman to'langan
        nasiya_savdolar = Savdo.objects.filter(
            st='nasiya',
            tulandi=False,
        ).select_related('haridor_dukon', 'yetkazib_beruvchi', 'company')

        total_nasiya = nasiya_savdolar.count()
        reminded = 0
        overdue_count = 0

        # Firmalar bo'yicha guruhlash — ega'ga yig'ib bitta xabar
        from collections import defaultdict
        by_company = defaultdict(list)
        for savdo in nasiya_savdolar:
            if savdo.company:
                by_company[savdo.company].append(savdo)

        for company, savdolar in by_company.items():
            # To'langan miqdorni hisobla
            nasiya_items = []
            total_qarzdorlik = 0.0

            for s in savdolar:
                tolangan = NasiyaTolov.objects.filter(savdo=s).aggregate(
                    t=Sum('tolov_summasi')
                )['t'] or 0
                qoldiq = (s.summa or 0) - tolangan

                if qoldiq <= 0:
                    continue  # Aslida to'langan, flag yangilanmagan

                # Necha kun o'tdi
                days_ago = (now - s.vaqt_sana).days

                nasiya_items.append({
                    'savdo': s,
                    'qoldiq': qoldiq,
                    'days_ago': days_ago,
                    'is_overdue': days_ago >= 7,  # 7+ kun = muddati o'tgan
                })
                total_qarzdorlik += qoldiq
                if days_ago >= 7:
                    overdue_count += 1

            if not nasiya_items:
                continue

            # Ega ga Telegram xabar
            overdue_items = [i for i in nasiya_items if i['is_overdue']]

            if overdue_items:
                self.stdout.write(
                    f"  💰 [{company.name}] {len(overdue_items)} ta muddati o'tgan nasiya "
                    f"(jami qoldiq: {total_qarzdorlik:,.0f} so'm)"
                )
                self._send_nasiya_reminder(company, overdue_items, total_qarzdorlik, dry_run)
                reminded += 1

        self.stdout.write(
            f"\n  Natija: {total_nasiya} ta nasiya, "
            f"{overdue_count} ta muddati o'tgan, "
            f"{reminded} ta firma egasiga xabar yuborildi"
        )

    def _send_nasiya_reminder(self, company, overdue_items, total_qarzdorlik, dry_run):
        """Nasiya eslatmasini ega'ga Telegram orqali yuborish"""
        try:
            from main.models import User
            owner = User.objects.filter(company=company, type='ega').first()
            if not owner or not owner.tg_id:
                return

            # Xabar matni
            lines = [
                f"📊 <b>Nasiya Eslatmasi — {company.name}</b>\n",
                f"⏰ <b>{len(overdue_items)} ta</b> nasiya 7+ kundan beri to'lanmagan:\n",
            ]
            for i, item in enumerate(overdue_items[:10], 1):
                s = item['savdo']
                lines.append(
                    f"  {i}. 🏪 {s.haridor_dukon.nomi} — "
                    f"<b>{item['qoldiq']:,.0f} so'm</b> "
                    f"({item['days_ago']} kun oldin)"
                )

            if len(overdue_items) > 10:
                lines.append(f"  ... va yana {len(overdue_items) - 10} ta")

            lines.append(f"\n💸 Jami qarzdorlik: <b>{total_qarzdorlik:,.0f} so'm</b>")
            lines.append("💡 Tafsilotlar uchun nasiyalar sahifasiga kiring.")

            msg = "\n".join(lines)

            if not dry_run:
                from main.bot_logic import send_telegram_notification
                send_telegram_notification(owner.tg_id, msg)
                self.stdout.write(f"     📨 Nasiya eslatmasi yuborildi → {owner.tg_id}")
            else:
                self.stdout.write(f"     [DRY-RUN] Nasiya xabari → {owner.tg_id}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"     ❌ Nasiya Telegram xato: {e}"))
