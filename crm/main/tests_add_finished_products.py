import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from main.models import Company, Mahsulot, MahsulotTuri

_MEDIA = tempfile.mkdtemp(prefix="sf_test_media_")


@override_settings(MEDIA_ROOT=_MEDIA)
class AddFinishedProductsCommandTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        self.company = Company.objects.create(name="Makmecco", subdomain="makmecco", setup_mode=False)
        self.other = Company.objects.create(name="Boshqa", subdomain="boshqa", setup_mode=False)
        self.kg = MahsulotTuri.objects.create(nomi="Kg")

    def _run(self, *args):
        out = StringIO()
        call_command("add_finished_products", "--subdomain", "makmecco", *args, stdout=out)
        return out.getvalue()

    def test_yetti_mahsulot_kg_da_qoshiladi(self):
        self._run()
        products = Mahsulot.objects.filter(company=self.company)
        self.assertEqual(products.count(), 7)
        self.assertEqual(
            set(products.values_list("nomi", flat=True)),
            {"Mol yog'i (mayda)", "Mol yog'i (yirik)", "Shashlik marinatlari", "Quyon", "Kurka", "O'rdak", "Tovuq"},
        )
        for p in products:
            self.assertEqual(p.turi_id, self.kg.id)          # mavjud "Kg" qayta ishlatildi
            self.assertEqual(p.warehouse_type, "finished")
            self.assertTrue(p.is_kg)
            self.assertTrue(p.rasmi.name)
            self.assertGreater(p.rasmi.size, 0)
        self.assertEqual(MahsulotTuri.objects.filter(nomi__iexact="kg").count(), 1)
        self.assertEqual(Mahsulot.objects.filter(company=self.other).count(), 0)

    def test_qayta_ishga_tushirish_dublikat_yaratmaydi(self):
        self._run()
        output = self._run()
        self.assertEqual(Mahsulot.objects.filter(company=self.company).count(), 7)
        self.assertIn("7 ta o'tkazildi", output)

    def test_dry_run_hech_narsa_saqlamaydi(self):
        output = self._run("--dry-run")
        self.assertEqual(Mahsulot.objects.count(), 0)
        self.assertIn("DRY-RUN", output)

    def test_nomalum_firma_xato_beradi(self):
        with self.assertRaises(CommandError):
            call_command("add_finished_products", "--subdomain", "yoq-firma", stdout=StringIO())
