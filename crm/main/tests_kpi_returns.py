import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from main.models import (
    Company, DeliveryStock, Mahsulot, MahsulotRetsept, MahsulotTuri, MiqdorQoshish,
    Pazanda, ProductionTask, Savdo, User, YetkazibBeruvchi, qaytarilgan_mahsulotlar,
)
from main.services import kpi_service, payroll_service, task_service


class MaterialDeviationJarimaTests(TestCase):
    """Xom ashyo tortish og'ishidan shtraf: (1) qabul qilingan tortish
    tolerantligi (2g kam / 50g ortiq) doirasidagi og'ish shtrafsiz
    bo'lishi, (2) shtraf tayyor mahsulotning ish haqi narxida emas,
    komponentning O'Z narxida hisoblanishi kerak — avvalgi xato: hatto
    rejani TO'LIQ topshirgan pazanda ham, tortishdagi arzimas og'ish
    tayyor mahsulotning (ancha qimmat) ish haqi narxiga ko'paytirilib,
    noo'rin katta shtrafga uchrardi."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testjarima", setup_mode=False)
        self.ega = User.objects.create_user(username="ega1", password="secret123", type="ega", company=self.company)
        self.pz_user = User.objects.create_user(
            username="pz1", password="secret123", type="ishlab_chiqaruvchi", company=self.company,
        )
        self.pazanda = Pazanda.objects.create(user=self.pz_user, company=self.company)
        self.turi = MahsulotTuri.objects.create(nomi="kg")
        # Arzon xom ashyo (narxi=50 so'm/kg) — tannarx qasddan 0, `narxi`ga
        # tushishini tekshirish uchun.
        self.komponent = Mahsulot.objects.create(
            company=self.company, nomi="Un", narxi=50, turi=self.turi,
            warehouse_type="semi_finished", ombor_turi="xom_ashyo", miqdori=1000,
        )
        # Qimmat ish haqi narxi (1500 so'm/dona) — bu shtrafga aralashmasligi kerak.
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Somsa", narxi=5000, turi=self.turi,
            warehouse_type="finished", mahsulot_turi="ishlab_chiqariladigan",
            serial_granularity="none", ishlab_chiqarish_narxi=1500,
        )
        MahsulotRetsept.objects.create(
            company=self.company, mahsulot=self.mahsulot, komponent=self.komponent, norma_miqdor=1,
        )

    def _create_task_and_weigh(self, measured_qty):
        task, err, _ = task_service.create_production_task(
            self.company, self.mahsulot, 1, timezone.localdate(), self.ega, pazanda=self.pazanda,
        )
        self.assertIsNone(err, err)
        pickup = task.material_pickups.get()
        result = task_service.weigh_task_pickup(pickup.id, self.pazanda, measured_qty)
        self.assertTrue(result["approved"], result)
        task_service.confirm_task_finished_materials(task.id, self.pazanda, self.company)
        return task.miqdor_qoshishlar.get()

    def test_deviation_within_tolerance_no_fine(self):
        # 40g ortiqcha — 50g tolerantlik ichida, shtraf 0 bo'lishi kerak.
        mq = self._create_task_and_weigh(1.04)
        self.assertEqual(mq.jarima_summasi, Decimal('0'))

    def test_exact_match_no_fine(self):
        mq = self._create_task_and_weigh(1.0)
        self.assertEqual(mq.jarima_summasi, Decimal('0'))


class LegacyMaterialRequestJarimaTests(TestCase):
    """Eski (Task Panel'gacha bo'lgan) `ProductionMaterialRequest`
    oqimida ham xuddi shu xato bor edi — shtraf komponentning o'z
    narxida emas, tayyor mahsulotning ish haqi narxida hisoblanardi."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testlegjar", setup_mode=False)
        self.pz_user = User.objects.create_user(
            username="pz1", password="secret123", type="ishlab_chiqaruvchi", company=self.company,
        )
        self.pazanda = Pazanda.objects.create(user=self.pz_user, company=self.company)
        self.turi = MahsulotTuri.objects.create(nomi="kg")
        self.komponent = Mahsulot.objects.create(
            company=self.company, nomi="Un", narxi=50, turi=self.turi,
            warehouse_type="semi_finished", ombor_turi="xom_ashyo", miqdori=1000,
        )
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Somsa", narxi=5000, turi=self.turi,
            warehouse_type="finished", mahsulot_turi="ishlab_chiqariladigan",
            serial_granularity="none", ishlab_chiqarish_narxi=1500,
        )
        MahsulotRetsept.objects.create(
            company=self.company, mahsulot=self.mahsulot, komponent=self.komponent, norma_miqdor=1,
        )

    def test_fine_uses_komponent_price_not_product_labor_rate(self):
        from main.models import ProductionMaterialRequest
        from main.services import stock_service

        mq = MiqdorQoshish.objects.create(
            company=self.company, pazanda=self.pazanda, mahsulot=self.mahsulot, miqdor=1,
        )
        # 1.5 kg olindi, norma 1 kg — 0.5 kg og'ish.
        req = ProductionMaterialRequest.objects.create(
            company=self.company, producer=self.pazanda, material=self.komponent,
            target_product=self.mahsulot, qty=1.5, status='approved', reviewed_at=timezone.now(),
        )
        stock_service._apply_retsept_hisobkitob(mq, self.mahsulot)
        # To'g'ri: 0.5 kg * 50 so'm (komponent narxi) = 25 so'm.
        # Eski (xato) hisob: 0.5 * 1500 (ishlab_chiqarish_narxi) = 750 so'm bo'lardi.
        self.assertEqual(mq.jarima_summasi, Decimal('25'))


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
