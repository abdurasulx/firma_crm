import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from main.models import Company, Mahsulot, MahsulotRetsept, MahsulotTuri

_MEDIA = tempfile.mkdtemp(prefix="sf_test_media_")


@override_settings(MEDIA_ROOT=_MEDIA)
class ResetOmborCommandTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        self.company = Company.objects.create(name="Makmecco", subdomain="makmecco", setup_mode=False)
        self.other = Company.objects.create(name="Boshqa", subdomain="boshqa", setup_mode=False)
        self.kg = MahsulotTuri.objects.create(nomi="Kg")
        self.dona = MahsulotTuri.objects.create(nomi="Dona")

        self.eski = Mahsulot.objects.create(
            company=self.company, nomi="go'sht", narxi=0, turi=self.kg,
            warehouse_type="semi_finished", ombor_turi="xom_ashyo",
        )
        self.lahim = Mahsulot.objects.create(
            company=self.company, nomi="Lahim", narxi=50000, turi=self.kg, warehouse_type="finished",
        )
        MahsulotRetsept.objects.create(company=self.company, mahsulot=self.lahim, komponent=self.eski, norma_miqdor=1)
        # Boshqa firmaning ombori — tegilmasligi kerak.
        self.boshqa_ombor = Mahsulot.objects.create(
            company=self.other, nomi="Un", narxi=0, turi=self.kg, warehouse_type="semi_finished",
        )

    def _run(self, *args):
        out = StringIO()
        call_command("reset_ombor", "--subdomain", "makmecco", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_hech_narsa_ozgartirmaydi(self):
        output = self._run("--dry-run")
        self.assertIn("go'sht", output)
        self.assertIn("main.MahsulotRetsept — 1 ta", output)   # kaskad ogohlantirishi
        self.assertIn("DRY-RUN", output)
        self.assertTrue(Mahsulot.objects.filter(id=self.eski.id).exists())
        self.assertEqual(MahsulotRetsept.objects.count(), 1)
        self.assertEqual(Mahsulot.objects.filter(company=self.company, warehouse_type="semi_finished").count(), 1)

    def test_eski_ombor_ochirilib_yangisi_qoshiladi(self):
        self._run()
        ombor = Mahsulot.objects.filter(company=self.company, warehouse_type="semi_finished")
        self.assertFalse(ombor.filter(id=self.eski.id).exists())
        self.assertEqual(ombor.count(), 10)
        self.assertEqual(ombor.get(nomi="Mol tanasi").turi_id, self.kg.id)
        self.assertEqual(ombor.get(nomi="Qadoq").turi_id, self.dona.id)
        for m in ombor:
            self.assertEqual(m.ombor_turi, "xom_ashyo")
            self.assertTrue(m.rasmi.name)

        # Tayyor mahsulot va boshqa firma ombori joyida.
        self.assertTrue(Mahsulot.objects.filter(id=self.lahim.id).exists())
        self.assertTrue(Mahsulot.objects.filter(id=self.boshqa_ombor.id).exists())
        self.assertEqual(MahsulotTuri.objects.count(), 2)   # yangi birlik yaratilmadi

    def test_tayyor_mahsulot_nomi_bilan_toqnashsa_toxtaydi(self):
        Mahsulot.objects.create(
            company=self.company, nomi="Mol tanasi", narxi=0, turi=self.kg, warehouse_type="finished",
        )
        with self.assertRaises(CommandError):
            self._run()
        self.assertTrue(Mahsulot.objects.filter(id=self.eski.id).exists())
