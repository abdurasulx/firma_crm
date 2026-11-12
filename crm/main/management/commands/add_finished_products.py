"""
Firmaga bir nechta TAYYOR mahsulotni birdaniga qo'shadi ("Mahsulotlar"
bo'limi, `warehouse_type='finished'`).

    python manage.py add_finished_products --subdomain makmecco --dry-run
    python manage.py add_finished_products --subdomain makmecco

Standart ro'yxat — go'sht firmasi (makmecco) uchun so'ralgan mahsulotlar;
boshqa ro'yxat kerak bo'lsa `--names "A" "B"` bilan beriladi.

- Shu firmada xuddi shu nomli mahsulot allaqachon bo'lsa — o'tkazib
  yuboriladi (buyruqni qayta ishga tushirish xavfsiz, dublikat yaratmaydi).
- Rasm majburiy maydon bo'lgani uchun har biriga oddiy vaqtinchalik rasm
  (mahsulot nomining bosh harfi) generatsiya qilinadi — keyin mahsulot
  sahifasidan haqiqiysiga almashtiriladi.
- Narx 0, qoldiq 0, QR turi "Yo'q" — bularni ega keyin o'zi to'g'rilaydi.
"""
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, ImageDraw, ImageFont

from main.models import Company, Mahsulot, MahsulotTuri

DEFAULT_NAMES = [
    "Mol yog'i (mayda)",
    "Mol yog'i (yirik)",
    "Shashlik marinatlari",
    "Quyon",
    "Kurka",
    "O'rdak",
    "Tovuq",
]

PLACEHOLDER_COLORS = ["#b91c1c", "#c2410c", "#a16207", "#15803d", "#0e7490", "#1d4ed8", "#7e22ce"]


def _placeholder_image(nomi, index):
    """400x400 rangli kvadrat, o'rtasida mahsulot nomining bosh harfi."""
    img = Image.new("RGB", (400, 400), PLACEHOLDER_COLORS[index % len(PLACEHOLDER_COLORS)])
    draw = ImageDraw.Draw(img)
    harf = (nomi.strip()[:1] or "?").upper()
    try:
        font = ImageFont.load_default(size=220)
    except TypeError:  # eski Pillow — o'lchamsiz standart shrift
        font = ImageFont.load_default()
    left, top, right, bottom = draw.textbbox((0, 0), harf, font=font)
    draw.text(
        ((400 - (right - left)) / 2 - left, (400 - (bottom - top)) / 2 - top),
        harf, fill="white", font=font,
    )
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class Command(BaseCommand):
    help = "Firmaga tayyor mahsulotlarni birdaniga qo'shish (mavjudlari o'tkazib yuboriladi)"

    def add_arguments(self, parser):
        parser.add_argument('--subdomain', required=True, help="Firma subdomeni, masalan: makmecco")
        parser.add_argument('--names', nargs='+', default=DEFAULT_NAMES, help="Mahsulot nomlari")
        parser.add_argument('--unit', default='kg', help="O'lchov birligi (standart: kg)")
        parser.add_argument('--dry-run', action='store_true', help="Faqat ko'rsatish, hech narsa saqlanmaydi")

    def handle(self, *args, **options):
        try:
            company = Company.objects.get(subdomain=options['subdomain'])
        except Company.DoesNotExist:
            raise CommandError(f"'{options['subdomain']}' subdomenli firma topilmadi.")

        # Mavjud birlik ("Kg"/"kg") qayta ishlatiladi — dublikat tur yaratilmaydi.
        turi = MahsulotTuri.objects.filter(nomi__iexact=options['unit']).order_by('id').first()
        if not turi:
            if options['dry_run']:
                self.stdout.write(f"O'lchov birligi '{options['unit']}' yo'q — yaratiladi.")
            else:
                turi = MahsulotTuri.objects.create(nomi=options['unit'])

        self.stdout.write(f"Firma: {company.name} ({company.subdomain}), birlik: {options['unit']}")
        created = skipped = 0
        with transaction.atomic():
            for index, raw in enumerate(options['names']):
                nomi = raw.strip()
                if not nomi:
                    continue
                if Mahsulot.objects.filter(company=company, nomi__iexact=nomi).exists():
                    self.stdout.write(self.style.WARNING(f"  o'tkazildi (allaqachon bor): {nomi}"))
                    skipped += 1
                    continue
                if options['dry_run']:
                    self.stdout.write(f"  qo'shiladi: {nomi}")
                    created += 1
                    continue
                mahsulot = Mahsulot(
                    company=company, nomi=nomi, turi=turi, narxi=0, miqdori=0,
                    warehouse_type='finished', mahsulot_turi='ishlab_chiqariladigan',
                )
                mahsulot.rasmi.save(f"placeholder_{index + 1}.png", ContentFile(_placeholder_image(nomi, index)), save=False)
                mahsulot.save()
                self.stdout.write(self.style.SUCCESS(f"  qo'shildi: {nomi}"))
                created += 1

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f"DRY-RUN: {created} ta qo'shilardi, {skipped} ta o'tkazilardi. Hech narsa saqlanmadi."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Tayyor: {created} ta qo'shildi, {skipped} ta o'tkazildi."))
