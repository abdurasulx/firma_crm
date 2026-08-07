from django.test import TestCase
from django.utils import timezone

from main.agent_api_views import _maybe_finish_task_on_scan
from main.models import Company, Mahsulot, MahsulotRetsept, MahsulotTuri, Pazanda, ProductionTask, User
from main.services import qr_service, task_service


class BatchQrTrackingTests(TestCase):
    """`batch` granularityda ham vazifa faqat QR skanerlangach yakunlanishi
    kerak — avval "Ish bitdi" bosilgan zahoti (skanerlashsiz) darhol
    to'liq reja bilan yopilardi, foydalanuvchi buni xato deb topdi."""

    def setUp(self):
        self.company = Company.objects.create(name="Test Firma", subdomain="testprod", setup_mode=False)
        self.ega = User.objects.create_user(username="ega1", password="secret123", type="ega", company=self.company)
        self.pz_user = User.objects.create_user(
            username="pz1", password="secret123", type="ishlab_chiqaruvchi", company=self.company,
        )
        self.pazanda = Pazanda.objects.create(user=self.pz_user, company=self.company)
        self.turi = MahsulotTuri.objects.create(nomi="kg")

        self.komponent = Mahsulot.objects.create(
            company=self.company, nomi="Un", narxi=0, turi=self.turi,
            warehouse_type="semi_finished", ombor_turi="xom_ashyo",
            miqdori=1000, baza_tannarx=1000, tannarx=1000,
        )
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Somsa hamir 24", narxi=12000, turi=self.turi,
            warehouse_type="finished", mahsulot_turi="ishlab_chiqariladigan",
            serial_granularity="batch",
        )
        MahsulotRetsept.objects.create(
            company=self.company, mahsulot=self.mahsulot, komponent=self.komponent, norma_miqdor=0.1,
        )

    def _create_and_start_task(self, miqdor=10, qadoq_hajmi=3):
        task, err, needs_confirm = task_service.create_production_task(
            self.company, self.mahsulot, miqdor, timezone.localdate(), self.ega,
            pazanda=self.pazanda, qadoq_hajmi=qadoq_hajmi, force_uneven_qadoq=True,
        )
        self.assertIsNone(err, err)

        for pickup in task.material_pickups.all():
            result = task_service.weigh_task_pickup(pickup.id, self.pazanda, pickup.expected_qty)
            self.assertTrue(result["approved"], result)

        task_service.confirm_task_finished_materials(task.id, self.pazanda, self.company)
        task.refresh_from_db()
        return task

    def test_batch_task_stays_producing_until_all_qr_scanned(self):
        task = self._create_and_start_task(miqdor=10, qadoq_hajmi=3)

        # Avvalgi xato: shu yerda task allaqachon 'done' bo'lib qolardi,
        # hech qanday QR skanerlanmasdan.
        self.assertEqual(task.status, "producing")

        mq = task.miqdor_qoshishlar.get()
        serials = list(mq.seriallar.all())
        # 10 ta, 3 talik qadoq -> 3+3+3+1 (qoldiq alohida 1 donalik QR)
        self.assertEqual(sum(s.dona_soni for s in serials), 10)
        self.assertEqual(len(serials), 4)

        # Hammasi emas — bitta QR qoldirib qolganlarini skanerlaymiz.
        for serial in serials[:-1]:
            scanned = qr_service.register_scan(serial.kod)
            _maybe_finish_task_on_scan(scanned)

        task.refresh_from_db()
        self.assertEqual(task.status, "producing")
        self.assertLess(task_service.task_progress(task), 10)

        # Oxirgi QR skanerlanganda vazifa avtomatik yakunlanishi kerak.
        last_scanned = qr_service.register_scan(serials[-1].kod)
        _maybe_finish_task_on_scan(last_scanned)

        task.refresh_from_db()
        self.assertEqual(task.status, "done")
        self.assertEqual(task_service.task_progress(task), 10)

    def test_none_granularity_still_finishes_instantly(self):
        self.mahsulot.serial_granularity = "none"
        self.mahsulot.save(update_fields=["serial_granularity"])

        task = self._create_and_start_task(miqdor=5, qadoq_hajmi=None)

        # QR umuman yo'q — eski xatti-harakat (darhol yakunlanish) saqlanishi kerak.
        self.assertEqual(task.status, "done")
        self.assertEqual(task_service.task_progress(task), 5)
