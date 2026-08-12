from django.test import TestCase

from main.models import Company, Mahsulot, MahsulotTuri, MiqdorQoshish, Pazanda, Serial, User
from main.services import task_service


class PrintFailureTrackingTests(TestCase):
    """Chop etish MUVAFFAQIYATSIZ bo'lgan (printer holati bo'yicha
    aniqlangan — qog'oz tugagan/oflayn/xato) QR kodlar keyingi badge
    skanida qayta chop etishga taklif qilinishi kerak."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testprintfail", setup_mode=False)
        self.pz_user = User.objects.create_user(
            username="pz1", password="secret123", type="ishlab_chiqaruvchi", company=self.company,
        )
        self.pazanda = Pazanda.objects.create(user=self.pz_user, company=self.company)
        self.turi = MahsulotTuri.objects.create(nomi="dona")
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Somsa", narxi=5000, turi=self.turi, warehouse_type="finished",
        )
        self.batch = MiqdorQoshish.objects.create(
            company=self.company, pazanda=self.pazanda, mahsulot=self.mahsulot, miqdor=5, labels_printed=True,
        )
        self.serial1 = Serial.objects.create(company=self.company, mahsulot=self.mahsulot, batch=self.batch, kod="QR-1")
        self.serial2 = Serial.objects.create(company=self.company, mahsulot=self.mahsulot, batch=self.batch, kod="QR-2")

    def test_report_failure_marks_serial(self):
        task_service.report_serial_print_result("QR-1", self.company, success=False, reason="Qog'oz tugagan")
        self.serial1.refresh_from_db()
        self.assertTrue(self.serial1.chop_etilmadi)
        self.assertEqual(self.serial1.chop_etish_sababi, "Qog'oz tugagan")

    def test_report_success_clears_failure(self):
        self.serial1.chop_etilmadi = True
        self.serial1.chop_etish_sababi = "Qog'oz tugagan"
        self.serial1.save()
        task_service.report_serial_print_result("QR-1", self.company, success=True)
        self.serial1.refresh_from_db()
        self.assertFalse(self.serial1.chop_etilmadi)
        self.assertEqual(self.serial1.chop_etish_sababi, "")

    def test_get_failed_print_serials_returns_only_failed(self):
        task_service.report_serial_print_result("QR-1", self.company, success=False, reason="Oflayn")
        failed = task_service.get_failed_print_serials(self.pazanda, self.company)
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].kod, "QR-1")

    def test_report_unknown_kod_returns_false(self):
        found = task_service.report_serial_print_result("QR-NOMAVJUD", self.company, success=False)
        self.assertFalse(found)

    def test_pending_batch_falls_back_to_failed_serials(self):
        # Batch allaqachon "chop etilgan" deb belgilangan (labels_printed=True),
        # lekin bitta seriali haqiqatda chop etilmagan bo'lsa —
        # get_pending_print_batch (yangi partiya) hech narsa topmaydi,
        # get_failed_print_serials esa aynan shu qatorni qaytarishi kerak.
        mq, serials = task_service.get_pending_print_batch(self.pazanda, self.company)
        self.assertIsNone(mq)
        task_service.report_serial_print_result("QR-2", self.company, success=False, reason="Qog'oz tugagan")
        failed = task_service.get_failed_print_serials(self.pazanda, self.company)
        self.assertEqual([s.kod for s in failed], ["QR-2"])


class AgentReportPrintResultApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Test", subdomain="testprintapi", setup_mode=False,
            desktop_agent_token="agent-token-abc",
        )
        self.pz_user = User.objects.create_user(
            username="pz1", password="secret123", type="ishlab_chiqaruvchi", company=self.company,
        )
        self.pazanda = Pazanda.objects.create(user=self.pz_user, company=self.company)
        self.turi = MahsulotTuri.objects.create(nomi="dona")
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Somsa", narxi=5000, turi=self.turi, warehouse_type="finished",
        )
        self.serial = Serial.objects.create(company=self.company, mahsulot=self.mahsulot, kod="QR-API-1")

    def test_report_print_failure_via_api(self):
        response = self.client.post(
            "/api/agent/report-print-result/",
            {"kod": "QR-API-1", "success": "0", "reason": "Qog'oz tugagan"},
            HTTP_AUTHORIZATION="Token agent-token-abc",
        )
        self.assertEqual(response.status_code, 200)
        self.serial.refresh_from_db()
        self.assertTrue(self.serial.chop_etilmadi)
        self.assertEqual(self.serial.chop_etish_sababi, "Qog'oz tugagan")

    def test_report_unknown_serial_404(self):
        response = self.client.post(
            "/api/agent/report-print-result/",
            {"kod": "YOQ", "success": "0"},
            HTTP_AUTHORIZATION="Token agent-token-abc",
        )
        self.assertEqual(response.status_code, 404)
