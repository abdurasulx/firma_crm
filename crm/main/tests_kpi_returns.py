import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from main.models import (
    Company, DeliveryStock, Mahsulot, MahsulotRetsept, MahsulotTuri,
    Pazanda, ProductionTask, Savdo, User, YetkazibBeruvchi, qaytarilgan_mahsulotlar,
)
from main.services import kpi_service, payroll_service, task_service


class ProductionMuddatTests(TestCase):
    """Mahsulotda kutilgan ishlab chiqarish vaqti belgilangan bo'lsa,
    vazifa OLINGANDA (claimed_at) shu asosda muddat avtomatik
    hisoblanishi kerak."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testmuddat", setup_mode=False)
        self.ega = User.objects.create_user(username="ega1", password="secret123", type="ega", company=self.company)
        self.pz_user = User.objects.create_user(
            username="pz1", password="secret123", type="ishlab_chiqaruvchi", company=self.company,
        )
        self.pazanda = Pazanda.objects.create(user=self.pz_user, company=self.company)
        self.turi = MahsulotTuri.objects.create(nomi="dona")
        self.komponent = Mahsulot.objects.create(
            company=self.company, nomi="Un", narxi=0, turi=self.turi,
            warehouse_type="semi_finished", ombor_turi="xom_ashyo", miqdori=1000,
        )

    def test_muddat_computed_when_kutilgan_soat_set(self):
        mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Somsa", narxi=5000, turi=self.turi,
            warehouse_type="finished", mahsulot_turi="ishlab_chiqariladigan",
            serial_granularity="none", kutilgan_ishlab_chiqarish_soat=2,
        )
        MahsulotRetsept.objects.create(company=self.company, mahsulot=mahsulot, komponent=self.komponent, norma_miqdor=1)

        before = timezone.now()
        task, err, _ = task_service.create_production_task(
            self.company, mahsulot, 5, timezone.localdate(), self.ega, pazanda=self.pazanda,
        )
        self.assertIsNone(err, err)
        self.assertIsNotNone(task.muddat)
        expected_min = before + dt.timedelta(hours=2)
        self.assertGreaterEqual(task.muddat, expected_min)
        self.assertFalse(task.kechikdi)  # hali muddat o'tmagan

    def test_no_muddat_when_kutilgan_soat_not_set(self):
        mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Lavash", narxi=5000, turi=self.turi,
            warehouse_type="finished", mahsulot_turi="ishlab_chiqariladigan",
            serial_granularity="none",
        )
        MahsulotRetsept.objects.create(company=self.company, mahsulot=mahsulot, komponent=self.komponent, norma_miqdor=1)

        task, err, _ = task_service.create_production_task(
            self.company, mahsulot, 5, timezone.localdate(), self.ega, pazanda=self.pazanda,
        )
        self.assertIsNone(err, err)
        self.assertIsNone(task.muddat)
        self.assertFalse(task.kechikdi)


class QaytarishHalQilishTests(TestCase):
    """Utilizatsiya — ombor qoldig'iga qo'shilmasligi, Qayta ishlash —
    tanlangan xom ashyoga qo'shilishi, javobgar tanlansa qarz
    yozilishi kerak."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testqayt", setup_mode=False)
        self.ega = User.objects.create_user(username="ega1", password="secret123", type="ega", company=self.company)
        self.yb_user = User.objects.create_user(
            username="yb1", password="secret123", type="yetkazib_beruvchi", company=self.company,
        )
        self.yb = YetkazibBeruvchi.objects.create(user=self.yb_user, company=self.company, tuliq_ismi="YB Test")
        self.turi = MahsulotTuri.objects.create(nomi="dona")
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Non", narxi=5000, turi=self.turi,
            warehouse_type="finished", tannarx=1000, miqdori=0,
        )
        self.komponent = Mahsulot.objects.create(
            company=self.company, nomi="Un", narxi=0, turi=self.turi,
            warehouse_type="semi_finished", ombor_turi="xom_ashyo", miqdori=10,
        )
        self.q = qaytarilgan_mahsulotlar.objects.create(
            company=self.company, mahsulot=self.mahsulot, miqdor=3,
            status=qaytarilgan_mahsulotlar.STATUS_PENDING, yetkazib_beruvchi=self.yb,
        )
        self.client.force_login(self.ega)

    def _post(self, **extra):
        data = {"harakat_turi": "utilizatsiya"}
        data.update(extra)
        return self.client.post(
            f"/qaytarish/tasdiq/{self.q.id}/", data, SERVER_NAME="testqayt.localhost",
        )

    def test_utilizatsiya_does_not_add_stock(self):
        self._post(harakat_turi="utilizatsiya")
        self.mahsulot.refresh_from_db()
        self.q.refresh_from_db()
        self.assertEqual(self.mahsulot.miqdori, 0)
        self.assertEqual(self.q.status, qaytarilgan_mahsulotlar.STATUS_APPROVED)
        self.assertEqual(self.q.harakat_turi, "utilizatsiya")

    def test_qayta_ishlash_adds_to_chosen_komponent(self):
        self._post(harakat_turi="qayta_ishlash", komponent_id=self.komponent.id, komponent_miqdor="1.5")
        self.komponent.refresh_from_db()
        self.mahsulot.refresh_from_db()
        self.q.refresh_from_db()
        self.assertEqual(self.komponent.miqdori, 11.5)
        self.assertEqual(self.mahsulot.miqdori, 0)  # tayyor mahsulot qoldig'iga qo'shilmagan
        self.assertEqual(self.q.harakat_turi, "qayta_ishlash")
        self.assertEqual(self.q.komponent_id, self.komponent.id)

    def test_javobgar_tanlansa_qarz_yoziladi(self):
        self._post(harakat_turi="utilizatsiya", javobgar_id=self.yb_user.id)
        self.q.refresh_from_db()
        self.assertEqual(self.q.javobgar_id, self.yb_user.id)
        self.assertEqual(self.q.qarz_summasi, Decimal("3000"))  # 1000 tannarx * 3 miqdor

    def test_javobgar_tanlanmasa_qarz_yozilmaydi(self):
        self._post(harakat_turi="utilizatsiya")
        self.q.refresh_from_db()
        self.assertIsNone(self.q.javobgar)
        self.assertEqual(self.q.qarz_summasi, Decimal("0"))


class KpiServiceSmokeTests(TestCase):
    """KPI faqat egadan boshqa xodimlar uchun ishlashi va rolga mos
    kalitlarni qaytarishi kerak."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testkpi", setup_mode=False)
        self.ega = User.objects.create_user(username="ega1", password="secret123", type="ega", company=self.company)
        self.omborchi = User.objects.create_user(
            username="omb1", password="secret123", type="omborchi", company=self.company,
        )

    def test_ega_has_no_kpi(self):
        self.assertIsNone(kpi_service.get_employee_kpi(self.ega, self.company))

    def test_omborchi_kpi_shape(self):
        kpi = kpi_service.get_employee_kpi(self.omborchi, self.company)
        self.assertIsNotNone(kpi)
        self.assertEqual(kpi["turi"], "omborchi")
        self.assertEqual(kpi["jami_korib_chiqilgan"], 0)


class PerSaleIshHaqiTests(TestCase):
    """Savdogar/yetkazib beruvchi uchun 'per_sale' ish haqi turi — shu
    oyda amalga oshirgan har bir savdo uchun belgilangan komissiya."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testpersale", setup_mode=False)
        self.turi = MahsulotTuri.objects.create(nomi="dona")
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Non", narxi=5000, turi=self.turi, warehouse_type="finished",
        )
        self.sd_user = User.objects.create_user(
            username="sd1", password="secret123", type="savdogar", company=self.company,
            ish_haqi_turi_override="per_sale", savdo_birlik_narxi=Decimal("2000"),
        )
        self.yb_user = User.objects.create_user(
            username="yb1", password="secret123", type="yetkazib_beruvchi", company=self.company,
            ish_haqi_turi_override="per_sale", savdo_birlik_narxi=Decimal("1500"),
        )
        self.yb = YetkazibBeruvchi.objects.create(user=self.yb_user, company=self.company, tuliq_ismi="YB Test")

    def test_savdogar_komissiya(self):
        for _ in range(3):
            Savdo.objects.create(company=self.company, savdogar=self.sd_user, oluvchining_ismi="X", st="naqd", summa=10000)
        earned = payroll_service.compute_oylik_ish_haqi(self.sd_user, self.company)
        self.assertEqual(earned["manba"], "per_sale")
        self.assertEqual(earned["summa"], Decimal("6000"))  # 3 * 2000

    def test_yetkazib_beruvchi_komissiya(self):
        for _ in range(2):
            Savdo.objects.create(company=self.company, yetkazib_beruvchi=self.yb, oluvchining_ismi="X", st="naqd", summa=10000)
        earned = payroll_service.compute_oylik_ish_haqi(self.yb_user, self.company)
        self.assertEqual(earned["manba"], "per_sale")
        self.assertEqual(earned["summa"], Decimal("3000"))  # 2 * 1500

    def test_no_sales_zero(self):
        earned = payroll_service.compute_oylik_ish_haqi(self.sd_user, self.company)
        self.assertEqual(earned["summa"], Decimal("0"))
