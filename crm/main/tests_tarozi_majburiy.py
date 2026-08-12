from django.test import TestCase

from main.models import Company, User


class TaroziMajburiyAgentApiTests(TestCase):
    """`Company.tarozi_majburiy` Desktop Agent API javoblarida
    ko'rsatilishi kerak — agent shu maydonga qarab ishga tushishda
    tarozini talab qilish-qilmaslikni hal qiladi."""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test", subdomain="testtarozi", setup_mode=False,
            desktop_agent_token="test-agent-token-123",
        )

    def _get(self, path):
        return self.client.get(path, HTTP_AUTHORIZATION="Token test-agent-token-123")

    def test_omborlar_endpoint_includes_tarozi_majburiy_default_true(self):
        response = self._get("/api/agent/omborlar/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["tarozi_majburiy"])

    def test_omborlar_endpoint_reflects_false(self):
        self.company.tarozi_majburiy = False
        self.company.save(update_fields=['tarozi_majburiy'])
        response = self._get("/api/agent/omborlar/")
        self.assertFalse(response.json()["tarozi_majburiy"])


class TaroziMajburiySettingsViewTests(TestCase):
    """Ega Desktop Agent stansiyasini (`type='desktop_agent'`) tahrirlash
    sahifasidan (`editusr.html`) `tarozi_majburiy`ni yoqib/o'chira olishi
    kerak — bu firma darajasidagi sozlama, lekin foydalanuvchi qulayligi
    uchun aynan agent stansiyasi sahifasidan boshqariladi."""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test", subdomain="testtaroziview", setup_mode=False,
            custom_desktop_agent_stations=2,
        )
        self.ega = User.objects.create_user(username="ega1", password="secret123", type="ega", company=self.company)
        self.agent_user = User.objects.create_user(
            username="agent001", password="secret123", type="desktop_agent", company=self.company,
        )
        self.client.force_login(self.ega)

    def test_disable_tarozi_majburiy(self):
        response = self.client.post(
            f"/edituser/{self.agent_user.username}",
            {"action": "set_tarozi_majburiy", "tarozi_majburiy": "0"},
            SERVER_NAME="testtaroziview.localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.company.refresh_from_db()
        self.assertFalse(self.company.tarozi_majburiy)

    def test_enable_tarozi_majburiy(self):
        self.company.tarozi_majburiy = False
        self.company.save(update_fields=['tarozi_majburiy'])
        response = self.client.post(
            f"/edituser/{self.agent_user.username}",
            {"action": "set_tarozi_majburiy", "tarozi_majburiy": "1"},
            SERVER_NAME="testtaroziview.localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.company.refresh_from_db()
        self.assertTrue(self.company.tarozi_majburiy)
