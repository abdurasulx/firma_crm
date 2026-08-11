from django.test import TestCase

from main.models import Company, Mahsulot, MahsulotTuri, User, YetkazibBeruvchi, YuklamaSorov


class YuklamaSorovAjaxTests(TestCase):
    """Yetkazib beruvchi dashboardidagi "Yuklama olish" so'rovi endi
    AJAX (fetch) orqali ham ishlaydi — sahifa qayta yuklanmasdan JSON
    javob qaytishi kerak (X-Requested-With: XMLHttpRequest bilan)."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testsorov", setup_mode=False)
        self.yb_user = User.objects.create_user(
            username="yb1", password="secret123", type="yetkazib_beruvchi", company=self.company,
        )
        self.yb = YetkazibBeruvchi.objects.create(user=self.yb_user, company=self.company, tuliq_ismi="YB Test")
        self.turi = MahsulotTuri.objects.create(nomi="dona")
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Kola", narxi=10000, turi=self.turi,
            warehouse_type="finished", miqdori=50,
        )
        self.client.force_login(self.yb_user)

    def _post_ajax(self, miqdor):
        return self.client.post(
            "/",
            {"sorov_submit": "1", f"sorov_miqdor_{self.mahsulot.id}": str(miqdor)},
            SERVER_NAME="testsorov.localhost",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_ajax_success_returns_json_not_redirect(self):
        response = self._post_ajax(10)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["yaratilgan"]), 1)
        self.assertEqual(data["yaratilgan"][0]["mahsulot"], "Kola")
        self.assertTrue(YuklamaSorov.objects.filter(company=self.company, user=self.yb, mahsulot=self.mahsulot).exists())

    def test_ajax_over_stock_returns_warning_not_error_page(self):
        response = self._post_ajax(999)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertEqual(len(data["yaratilgan"]), 0)
        self.assertTrue(any("omborda faqat" in w for w in data["ogohlantirishlar"]))

    def test_non_ajax_still_redirects(self):
        response = self.client.post(
            "/",
            {"sorov_submit": "1", f"sorov_miqdor_{self.mahsulot.id}": "5"},
            SERVER_NAME="testsorov.localhost",
        )
        self.assertEqual(response.status_code, 302)
