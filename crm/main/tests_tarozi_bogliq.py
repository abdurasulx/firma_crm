from django.test import TestCase
from django.utils import timezone

from main.agent_api_views import _issue_badge_session_token
from main.models import (
    Company, Mahsulot, MahsulotRetsept, MahsulotTuri, MiqdorQoshish, Pazanda, ProductionTask, Serial, User,
)
from main.services import task_service
from main.services.retsept_service import add_retsept_row, set_tarozi_bogliq


class TaroziBogliqTests(TestCase):
    """Taroziga bog'liq (o'zgaruvchan) mahsulot — masalan go'sht: reja
    faqat taxminiy, haqiqiy miqdor Desktop Agent'da tarozidan olinadi
    (Enter = done). "O'zgarmas" komponent (qadoq) reja miqdoriga
    ko'paytirilmaydi."""

    def setUp(self):
        self.company = Company.objects.create(
            name="Go'sht Firma", subdomain="gosht", setup_mode=False,
            desktop_agent_token="agent-token-gosht", custom_desktop_agent_stations=1,
        )
        self.ega = User.objects.create_user(username="ega1", password="secret123", type="ega", company=self.company)
        self.pz_user = User.objects.create_user(
            username="pz1", password="secret123", type="ishlab_chiqaruvchi", company=self.company,
        )
        self.pazanda = Pazanda.objects.create(user=self.pz_user, company=self.company, tuliq_ismi="Pazanda Bir")
        self.kg = MahsulotTuri.objects.create(nomi="kg")
        self.dona = MahsulotTuri.objects.create(nomi="dona")

        self.gosht = Mahsulot.objects.create(
            company=self.company, nomi="Xom go'sht", narxi=0, turi=self.kg,
            warehouse_type="semi_finished", ombor_turi="xom_ashyo",
            miqdori=100, baza_tannarx=80000, tannarx=80000,
        )
        self.qadoq = Mahsulot.objects.create(
            company=self.company, nomi="Qadoq", narxi=0, turi=self.dona,
            warehouse_type="semi_finished", ombor_turi="xom_ashyo",
            miqdori=50, baza_tannarx=1000, tannarx=1000,
        )
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Qiyma", narxi=120000, turi=self.kg,
            warehouse_type="finished", mahsulot_turi="ishlab_chiqariladigan",
            serial_granularity="batch", ishlab_chiqarish_narxi=2000,
        )
        ok, err = add_retsept_row(self.company, self.mahsulot, self.gosht, 1.0, ozgarmas=False)
        self.assertTrue(ok, err)
        ok, err = add_retsept_row(self.company, self.mahsulot, self.qadoq, 1, ozgarmas=True)
        self.assertTrue(ok, err)
        ok, err = set_tarozi_bogliq(self.mahsulot, True)
        self.assertTrue(ok, err)

    def _task_with_materials_ready(self, miqdor=5):
        task, err, _ = task_service.create_production_task(
            self.company, self.mahsulot, miqdor, timezone.localdate(), self.ega, pazanda=self.pazanda,
        )
        self.assertIsNone(err, err)
        for pickup in task.material_pickups.all():
            result = task_service.weigh_task_pickup(pickup.id, self.pazanda, pickup.expected_qty)
            self.assertTrue(result["approved"], result)
        task.refresh_from_db()
        self.assertEqual(task.status, "materials_ready")
        return task

    def test_ozgarmas_komponent_reja_miqdoriga_kopaytirilmaydi(self):
        task, err, _ = task_service.create_production_task(
            self.company, self.mahsulot, 5, timezone.localdate(), self.ega, pazanda=self.pazanda,
        )
        self.assertIsNone(err, err)
        expected = {p.komponent_id: p.expected_qty for p in task.material_pickups.all()}
        self.assertEqual(expected[self.gosht.id], 5.0)   # o'zgaruvchan: 1.0 * 5
        self.assertEqual(expected[self.qadoq.id], 1)     # o'zgarmas: doim 1 ta qadoq

    def test_norma_tahrirlanganda_ozgarmas_belgisi_saqlanadi(self):
        ok, err = add_retsept_row(self.company, self.mahsulot, self.qadoq, 2)  # `ozgarmas` yuborilmadi
        self.assertTrue(ok, err)
        row = MahsulotRetsept.objects.get(mahsulot=self.mahsulot, komponent=self.qadoq)
        self.assertEqual(row.norma_miqdor, 2)
        self.assertTrue(row.ozgarmas)

    def test_veb_ish_bitdi_rad_etiladi(self):
        task = self._task_with_materials_ready()
        mq, err = task_service.confirm_task_finished_materials(task.id, self.pazanda, self.company)
        self.assertIsNone(mq)
        self.assertIn("taroziga bog'liq", err)
        task.refresh_from_db()
        self.assertEqual(task.status, "materials_ready")

    def test_tarozidagi_ogirlik_bilan_yakunlanadi_shtrafsiz(self):
        task = self._task_with_materials_ready(miqdor=5)
        mq, err = task_service.finish_weighed_task(task.id, self.pazanda, self.company, 4.35)
        self.assertIsNone(err, err)

        task.refresh_from_db()
        self.mahsulot.refresh_from_db()
        self.assertEqual(task.status, "done")
        self.assertEqual(mq.miqdor, 4.35)
        self.assertTrue(mq.tasdiqlangan)
        self.assertEqual(self.mahsulot.miqdori, 4.35)      # omborga HAQIQIY og'irlik qo'shildi
        self.assertEqual(mq.jarima_summasi, 0)             # 5 kg rejadan kam — shtraf yo'q
        # 1 vazifa = 1 partiya = 1 QR, QR haqiqiy og'irlikni ifodalaydi
        self.assertEqual([s.dona_soni for s in Serial.objects.filter(batch=mq)], [4.35])
        self.assertFalse(mq.labels_printed)                # agent keyingi qadamda chop etadi

    def test_ikki_marta_enter_bitta_partiya(self):
        task = self._task_with_materials_ready()
        mq, err = task_service.finish_weighed_task(task.id, self.pazanda, self.company, 4.9)
        self.assertIsNone(err, err)
        mq2, err2 = task_service.finish_weighed_task(task.id, self.pazanda, self.company, 4.9)
        self.assertIsNone(mq2)
        self.assertIsNotNone(err2)
        self.assertEqual(MiqdorQoshish.objects.filter(source_task=task).count(), 1)
        self.assertEqual(Serial.objects.filter(batch=mq).count(), 1)
        self.mahsulot.refresh_from_db()
        self.assertEqual(self.mahsulot.miqdori, 4.9)

    def test_bosh_tarozi_rad_etiladi(self):
        task = self._task_with_materials_ready()
        mq, err = task_service.finish_weighed_task(task.id, self.pazanda, self.company, 0)
        self.assertIsNone(mq)
        self.assertIsNotNone(err)
        task.refresh_from_db()
        self.assertEqual(task.status, "materials_ready")

    def test_oddiy_mahsulotni_tortib_yakunlab_bolmaydi(self):
        ok, err = set_tarozi_bogliq(self.mahsulot, False)
        self.assertTrue(ok, err)
        task = self._task_with_materials_ready()
        mq, err = task_service.finish_weighed_task(task.id, self.pazanda, self.company, 4.5)
        self.assertIsNone(mq)
        self.assertIsNotNone(err)
        # Eski oqim buzilmagan: veb "Ish bitdi" ishlaydi, vazifa QR skanerini kutadi.
        mq, err = task_service.confirm_task_finished_materials(task.id, self.pazanda, self.company)
        self.assertIsNone(err, err)
        task.refresh_from_db()
        self.assertEqual(task.status, "producing")

    def test_set_tarozi_bogliq_cheklovlari(self):
        dona_mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Non", narxi=5000, turi=self.dona,
            warehouse_type="finished", mahsulot_turi="ishlab_chiqariladigan",
        )
        ok, err = set_tarozi_bogliq(dona_mahsulot, True)
        self.assertFalse(ok)
        self.assertIn("kg", err)

        # Tugallanmagan vazifa bor paytda almashtirib bo'lmaydi.
        self._task_with_materials_ready()
        ok, err = set_tarozi_bogliq(self.mahsulot, False)
        self.assertFalse(ok)
        self.mahsulot.refresh_from_db()
        self.assertTrue(self.mahsulot.tarozi_bogliq)

    def test_agent_api_enter_oqimi(self):
        task = self._task_with_materials_ready(miqdor=5)
        session_token = _issue_badge_session_token(self.pz_user, self.company)
        auth = {"HTTP_AUTHORIZATION": "Token agent-token-gosht"}

        response = self.client.get("/api/agent/my-output-weighs/", {"session_token": session_token}, **auth)
        self.assertEqual(response.status_code, 200, response.content)
        vazifalar = response.json()["vazifalar"]
        self.assertEqual([v["id"] for v in vazifalar], [task.id])
        self.assertEqual(vazifalar[0]["mahsulot"], "Qiyma")

        response = self.client.post(
            f"/api/agent/task/{task.id}/output-weigh/",
            {"session_token": session_token, "measured_qty": "4.82"}, **auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data["approved"], data)
        self.assertEqual(data["miqdor"], 4.82)
        self.assertTrue(data["has_labels"])

        # Yorliq odatdagi "chop etilmagan partiya" navbatiga tushadi.
        response = self.client.get("/api/agent/pending-print-batch/", {"session_token": session_token}, **auth)
        batch = response.json()["batch"]
        self.assertEqual(batch["serial_soni"], 1)

        # Navbat bo'shadi; ikkinchi Enter hech narsa qilmaydi.
        response = self.client.get("/api/agent/my-output-weighs/", {"session_token": session_token}, **auth)
        self.assertEqual(response.json()["vazifalar"], [])
        response = self.client.post(
            f"/api/agent/task/{task.id}/output-weigh/",
            {"session_token": session_token, "measured_qty": "4.82"}, **auth,
        )
        self.assertFalse(response.json()["approved"])
        self.assertEqual(ProductionTask.objects.get(id=task.id).status, "done")
