import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from main.models import (
    Company, DeliveryStock, KpiQoida, Mahsulot, MahsulotRetsept, MahsulotTuri, MiqdorQoshish,
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
    oyda amalga oshirgan savdolaridagi `Savdo.ish_haqi_summasi`
    (mahsulotning `sotuv_ish_haqi_narxi`si asosida hisoblangan)
    yig'indisidan hisoblanadi."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testpersale", setup_mode=False)
        self.turi = MahsulotTuri.objects.create(nomi="dona")
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Non", narxi=5000, turi=self.turi, warehouse_type="finished",
            sotuv_ish_haqi_narxi=2000,
        )
        self.sd_user = User.objects.create_user(
            username="sd1", password="secret123", type="savdogar", company=self.company,
            ish_haqi_turi_override="per_sale",
        )
        self.yb_user = User.objects.create_user(
            username="yb1", password="secret123", type="yetkazib_beruvchi", company=self.company,
            ish_haqi_turi_override="per_sale",
        )
        self.yb = YetkazibBeruvchi.objects.create(user=self.yb_user, company=self.company, tuliq_ismi="YB Test")

    def test_savdogar_komissiya(self):
        for _ in range(3):
            Savdo.objects.create(
                company=self.company, savdogar=self.sd_user, oluvchining_ismi="X", st="naqd",
                summa=10000, ish_haqi_summasi=2000,
            )
        earned = payroll_service.compute_oylik_ish_haqi(self.sd_user, self.company)
        self.assertEqual(earned["manba"], "per_sale")
        self.assertEqual(earned["summa"], Decimal("6000"))  # 3 * 2000

    def test_yetkazib_beruvchi_komissiya(self):
        for _ in range(2):
            Savdo.objects.create(
                company=self.company, yetkazib_beruvchi=self.yb, oluvchining_ismi="X", st="naqd",
                summa=10000, ish_haqi_summasi=1500,
            )
        earned = payroll_service.compute_oylik_ish_haqi(self.yb_user, self.company)
        self.assertEqual(earned["manba"], "per_sale")
        self.assertEqual(earned["summa"], Decimal("3000"))  # 2 * 1500

    def test_no_sales_zero(self):
        earned = payroll_service.compute_oylik_ish_haqi(self.sd_user, self.company)
        self.assertEqual(earned["summa"], Decimal("0"))


class SotuvIshHaqiTannarxTests(TestCase):
    """Mahsulotning `sotuv_ish_haqi_narxi`si tannarxga qo'shilishi va
    savdo yaratilganda `Savdo.ish_haqi_summasi`ga to'g'ri yozilishi
    kerak (ega tanlagan "mahsulot narxiga qo'shiladi" yondashuvi)."""

    def test_sotuv_ish_haqi_narxi_added_to_tannarx(self):
        from main.services.stock_service import recompute_tannarx

        company = Company.objects.create(name="Test", subdomain="testsotuvth", setup_mode=False)
        turi = MahsulotTuri.objects.create(nomi="dona")
        mahsulot = Mahsulot.objects.create(
            company=company, nomi="Kola", narxi=10000, turi=turi, warehouse_type="finished",
            mahsulot_turi="distributor", baza_tannarx=5000, sotuv_ish_haqi_narxi=300,
        )
        unit_cost = recompute_tannarx(mahsulot)
        self.assertEqual(unit_cost, Decimal("5300"))  # 5000 (baza) + 300 (sotuv ish haqi)


class KpiQoidaBonusTests(TestCase):
    """Ega firma sozlamalarida belgilagan KPI qoidalari (xodim TURI
    bo'yicha, individual emas) — chegaraga yetganda bonus qo'shilishi,
    bir nechta bosqich (progressiv) bir vaqtda faol bo'lishi, faqat
    'summa'da 'foiz' ishlashi kerak."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testkpiqoida", setup_mode=False)
        self.turi = MahsulotTuri.objects.create(nomi="dona")
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Kola", narxi=10000, turi=self.turi, warehouse_type="finished",
        )
        self.sd_user = User.objects.create_user(
            username="sd1", password="secret123", type="savdogar", company=self.company,
        )

    def test_no_rules_zero_bonus(self):
        result = kpi_service.compute_kpi_bonus(self.sd_user, self.company)
        self.assertEqual(result["bonus_summasi"], Decimal("0"))
        self.assertEqual(result["qoidalar"], [])

    def test_fiks_bonus_when_threshold_reached(self):
        KpiQoida.objects.create(
            company=self.company, xodim_turi="savdogar", olchov_turi="summa",
            chegara=Decimal("10000"), bonus_turi="fiks", bonus_qiymati=Decimal("50000"),
        )
        Savdo.objects.create(company=self.company, savdogar=self.sd_user, oluvchining_ismi="X", st="naqd", summa=15000)
        result = kpi_service.compute_kpi_bonus(self.sd_user, self.company)
        self.assertEqual(result["bonus_summasi"], Decimal("50000"))
        self.assertTrue(result["qoidalar"][0]["yetdi"])

    def test_foiz_bonus_scales_with_value(self):
        KpiQoida.objects.create(
            company=self.company, xodim_turi="savdogar", olchov_turi="summa",
            chegara=Decimal("10000"), bonus_turi="foiz", bonus_qiymati=Decimal("5"),
        )
        Savdo.objects.create(company=self.company, savdogar=self.sd_user, oluvchining_ismi="X", st="naqd", summa=20000)
        result = kpi_service.compute_kpi_bonus(self.sd_user, self.company)
        self.assertEqual(result["bonus_summasi"], Decimal("1000"))  # 20000 * 5%

    def test_below_threshold_no_bonus(self):
        KpiQoida.objects.create(
            company=self.company, xodim_turi="savdogar", olchov_turi="summa",
            chegara=Decimal("100000"), bonus_turi="fiks", bonus_qiymati=Decimal("50000"),
        )
        Savdo.objects.create(company=self.company, savdogar=self.sd_user, oluvchining_ismi="X", st="naqd", summa=15000)
        result = kpi_service.compute_kpi_bonus(self.sd_user, self.company)
        self.assertEqual(result["bonus_summasi"], Decimal("0"))
        self.assertFalse(result["qoidalar"][0]["yetdi"])

    def test_progressive_tiers_both_apply(self):
        KpiQoida.objects.create(
            company=self.company, xodim_turi="savdogar", olchov_turi="summa",
            chegara=Decimal("5000"), bonus_turi="fiks", bonus_qiymati=Decimal("10000"),
        )
        KpiQoida.objects.create(
            company=self.company, xodim_turi="savdogar", olchov_turi="summa",
            chegara=Decimal("10000"), bonus_turi="fiks", bonus_qiymati=Decimal("20000"),
        )
        Savdo.objects.create(company=self.company, savdogar=self.sd_user, oluvchining_ismi="X", st="naqd", summa=15000)
        result = kpi_service.compute_kpi_bonus(self.sd_user, self.company)
        self.assertEqual(result["bonus_summasi"], Decimal("30000"))  # ikkalasi ham yetgan

        # Ikkala bosqich (5000 va 10000) BITTA guruhda (bir xil "Jami"/summa
        # o'lchovi), navbat-navbat segment sifatida — ikkalasi ham to'liq
        # yetgan (amalda=15000, ikkala chegaradan ham katta).
        self.assertEqual(len(result["bosqichlar"]), 1)
        segments = result["bosqichlar"][0]["segments"]
        self.assertEqual(len(segments), 2)
        self.assertTrue(segments[0]["yetdi"])
        self.assertEqual(segments[0]["segment_percent"], 100)
        self.assertTrue(segments[1]["yetdi"])
        self.assertEqual(segments[1]["segment_percent"], 100)

    def test_progressive_tiers_partial_segment(self):
        # 300 va 500 dona qoidalari, hozircha 350 dona — birinchi segment
        # TO'LIQ (300ga yetgan), ikkinchi segment esa 300-500 oralig'ida
        # (350-300)/(500-300) = 25% to'lgan bo'lishi kerak.
        KpiQoida.objects.create(
            company=self.company, xodim_turi="savdogar", mahsulot=self.mahsulot, olchov_turi="dona",
            chegara=Decimal("300"), bonus_turi="fiks", bonus_qiymati=Decimal("10000"),
        )
        KpiQoida.objects.create(
            company=self.company, xodim_turi="savdogar", mahsulot=self.mahsulot, olchov_turi="dona",
            chegara=Decimal("500"), bonus_turi="fiks", bonus_qiymati=Decimal("20000"),
        )
        Savdo.objects.create(
            company=self.company, savdogar=self.sd_user, oluvchining_ismi="X", st="naqd",
            summa=1, smm="Kola 350,",
        )
        result = kpi_service.compute_kpi_bonus(self.sd_user, self.company)
        self.assertEqual(result["bonus_summasi"], Decimal("10000"))  # faqat 300 yetgan
        segments = result["bosqichlar"][0]["segments"]
        self.assertTrue(segments[0]["yetdi"])
        self.assertEqual(segments[0]["segment_percent"], 100)
        self.assertFalse(segments[1]["yetdi"])
        self.assertEqual(segments[1]["segment_percent"], 25)  # (350-300)/(500-300)*100

    def test_inactive_rule_ignored(self):
        KpiQoida.objects.create(
            company=self.company, xodim_turi="savdogar", olchov_turi="summa",
            chegara=Decimal("1000"), bonus_turi="fiks", bonus_qiymati=Decimal("50000"), faol=False,
        )
        Savdo.objects.create(company=self.company, savdogar=self.sd_user, oluvchining_ismi="X", st="naqd", summa=15000)
        result = kpi_service.compute_kpi_bonus(self.sd_user, self.company)
        self.assertEqual(result["bonus_summasi"], Decimal("0"))

    def test_bonus_added_to_payroll(self):
        KpiQoida.objects.create(
            company=self.company, xodim_turi="savdogar", olchov_turi="summa",
            chegara=Decimal("10000"), bonus_turi="fiks", bonus_qiymati=Decimal("50000"),
        )
        Savdo.objects.create(company=self.company, savdogar=self.sd_user, oluvchining_ismi="X", st="naqd", summa=15000)
        earned = payroll_service.compute_oylik_ish_haqi(self.sd_user, self.company)
        self.assertEqual(earned["kpi_bonus"], Decimal("50000"))
        self.assertEqual(earned["summa"], Decimal("50000"))  # fixed maosh 0 + bonus

    def test_product_specific_rule(self):
        KpiQoida.objects.create(
            company=self.company, xodim_turi="savdogar", mahsulot=self.mahsulot, olchov_turi="dona",
            chegara=Decimal("2"), bonus_turi="fiks", bonus_qiymati=Decimal("30000"),
        )
        Savdo.objects.create(
            company=self.company, savdogar=self.sd_user, oluvchining_ismi="X", st="naqd",
            summa=20000, smm="Kola 2,",
        )
        result = kpi_service.compute_kpi_bonus(self.sd_user, self.company)
        self.assertEqual(result["bonus_summasi"], Decimal("30000"))


class KpiQoidalariViewTests(TestCase):
    """Ega KPI qoidalari sahifasidan qoida qo'sha olishi kerak."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testkpiview", setup_mode=False)
        self.ega = User.objects.create_user(username="ega1", password="secret123", type="ega", company=self.company)
        self.client.force_login(self.ega)

    def test_ega_can_add_rule(self):
        response = self.client.post(
            "/kpi/qoidalar/",
            {
                "action": "add", "xodim_turi": "savdogar", "olchov_turi": "summa",
                "chegara": "10000000", "bonus_turi": "foiz", "bonus_qiymati": "3",
            },
            SERVER_NAME="testkpiview.localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(KpiQoida.objects.filter(company=self.company).count(), 1)
