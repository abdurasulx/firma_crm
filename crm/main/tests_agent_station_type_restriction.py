from django.test import TestCase

from main.models import Company, User
from main.services.agent_qr_crypto import encrypt_login_payload


class AgentStationLoginTypeRestrictionTests(TestCase):
    """Desktop Agent stansiyasi sifatida kirish (parol yoki QR orqali)
    endi FAQAT `type='desktop_agent'` hisoblar uchun ishlashi kerak —
    avval istalgan faol hisob (ega, omborchi va h.k.) stansiya sifatida
    kira olardi, bu real ishlab chiqarishda xavfsizlik muammosi sifatida
    aniqlandi (ega bilan kelishilgan holda yopildi)."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testagentrestrict", setup_mode=False)
        self.ega = User.objects.create_user(
            username="ega1", password="secret123", type="ega", company=self.company,
        )
        self.agent = User.objects.create_user(
            username="agent001", password="secret123", type="desktop_agent", company=self.company,
        )

    def test_password_login_rejects_ega(self):
        response = self.client.post(
            "/api/agent/login/",
            {"subdomain": "testagentrestrict", "username": "ega1", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 403)

    def test_password_login_accepts_desktop_agent(self):
        response = self.client.post(
            "/api/agent/login/",
            {"subdomain": "testagentrestrict", "username": "agent001", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())

    def test_qr_login_rejects_ega(self):
        payload = encrypt_login_payload(self.ega.id, self.ega.agent_qr_nonce)
        response = self.client.post(
            "/api/agent/login-by-qr/",
            {"subdomain": "testagentrestrict", "qr_payload": payload},
        )
        self.assertEqual(response.status_code, 403)

    def test_qr_login_accepts_desktop_agent(self):
        payload = encrypt_login_payload(self.agent.id, self.agent.agent_qr_nonce)
        response = self.client.post(
            "/api/agent/login-by-qr/",
            {"subdomain": "testagentrestrict", "qr_payload": payload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())
