"""
Firma OMBORINI (xom ashyo — `warehouse_type='semi_finished'`) to'liq
yangilaydi: eski ombor mahsulotlari o'chiriladi, o'rniga yangi ro'yxat
qo'shiladi. Tayyor mahsulotlarga ("Mahsulotlar" bo'limi) TEGILMAYDI.

    python manage.py reset_ombor --subdomain makmecco --dry-run
    python manage.py reset_ombor --subdomain makmecco

Standart ro'yxat — go'sht firmasi (makmecco) uchun: omborga so'yilgan
hayvon tanasi kiradi, ishlab chiqaruvchilar uni bo'laklab (lahm, tuyoq,
suyak, qiyma...) tayyor mahsulot qilib chiqaradi.

DIQQAT — o'chirish qaytarilmaydi. Eski ombor mahsuloti bilan birga unga
bog'langan retsept qatorlari, ombor tarixi, material so'rovlari va
vazifa xom ashyo qatorlari ham o'chadi. Shuning uchun avval `--dry-run`
bilan nima o'chishini ko'ring (dry-run hech narsa saqlamaydi).

Yangi mahsulotlar: qoldiq 0, tannarx 0, rasm — vaqtinchalik placeholder.
Qoldiq va narx keyin "Ombor > Kirim-chiqim" orqali kiritiladi.
"""
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from main.management.commands.add_finished_products import _placeholder_image
from main.models import Company, Mahsulot, MahsulotTuri

# (nomi, birlik). Nomlar tayyor mahsulot nomlaridan ATAYLAB farq qiladi
# ("Tovuq" emas, "Tovuq (butun)") — sotuv/yuklama kodi mahsulotni nomi
# bo'yicha qidiradi, bir xil nom ombor va tayyor mahsulotni chalkashtirardi.
DEFAULT_ITEMS = [
    ("Mol tanasi", "kg"),
    ("Qo'y tanasi", "kg"),
    ("Ot tanasi", "kg"),
    ("Tuya tanasi", "kg"),
    ("Tovuq (butun)", "kg"),
    ("Kurka (butun)", "kg"),
    ("O'rdak (butun)", "kg"),
    ("Quyon (butun)", "kg"),
    ("Marinad ziravorlari", "kg"),
    ("Qadoq", "dona"),
]


class Command(BaseCommand):
    help = "Firma omborini to'liq yangilash: eski xom ashyolarni o'chirib, yangi ro'yxatni qo'shish"

    def add_arguments(self, parser):
        parser.add_argument('--subdomain', required=True, help="Firma subdomeni, masalan: makmecco")
        parser.add_argument('--dry-run', action='store_true', help="Faqat ko'rsatish, hech narsa saqlanmaydi")

    def _get_turi(self, birlik, dry_run):
        turi = MahsulotTuri.objects.filter(nomi__iexact=birlik).order_by('id').first()
        if not turi and not dry_run:
            turi = MahsulotTuri.objects.create(nomi=birlik)
        return turi

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        try:
            company = Company.objects.get(subdomain=options['subdomain'])
        except Company.DoesNotExist:
            raise CommandError(f"'{options['subdomain']}' subdomenli firma topilmadi.")

        self.stdout.write(f"Firma: {company.name} ({company.subdomain})")

        finished_names = {
            n.strip().lower()
            for n in Mahsulot.objects.filter(company=company, warehouse_type='finished').values_list('nomi', flat=True)
        }
        clash = [nomi for nomi, _ in DEFAULT_ITEMS if nomi.lower() in finished_names]
        if clash:
            raise CommandError(
                "Bu nomlar tayyor mahsulotlar orasida allaqachon bor, ombor mahsuloti sifatida "
                f"qo'shib bo'lmaydi: {', '.join(clash)}"
            )

        with transaction.atomic():
            old = Mahsulot.objects.filter(company=company, warehouse_type='semi_finished')
            self.stdout.write(self.style.WARNING(f"O'chiriladigan eski ombor mahsulotlari ({old.count()} ta):"))
            for m in old.order_by('nomi'):
                self.stdout.write(f"  - {m.nomi} (qoldiq: {m.miqdori:g} {m.turi.nomi})")

            # Haqiqiy o'chirish tranzaksiya ichida bajariladi — dry-run'da
            # ham, shunda bog'langan (kaskad) yozuvlar soni ANIQ ko'rinadi;
            # dry-run oxirida hammasi orqaga qaytariladi.
            _, per_model = old.delete()
            for label, count in sorted(per_model.items()):
                if count and label != 'main.Mahsulot':
                    self.stdout.write(self.style.WARNING(f"    bog'langan yozuvlar ham o'chadi: {label} — {count} ta"))

            self.stdout.write(f"Qo'shiladigan yangi ombor mahsulotlari ({len(DEFAULT_ITEMS)} ta):")
            for index, (nomi, birlik) in enumerate(DEFAULT_ITEMS):
                self.stdout.write(f"  + {nomi} ({birlik})")
                if dry_run:
                    continue
                mahsulot = Mahsulot(
                    company=company, nomi=nomi, turi=self._get_turi(birlik, dry_run), narxi=0, miqdori=0,
                    warehouse_type='semi_finished', ombor_turi='xom_ashyo',
                )
                mahsulot.rasmi.save(
                    f"ombor_placeholder_{index + 1}.png", ContentFile(_placeholder_image(nomi, index)), save=False,
                )
                mahsulot.save()

            if dry_run:
                transaction.set_rollback(True)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN: hech narsa saqlanmadi."))
        else:
            self.stdout.write(self.style.SUCCESS("Tayyor: ombor yangilandi."))
