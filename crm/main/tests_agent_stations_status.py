from django.test import TestCase
from django.utils import timezone

from main.models import Company, User


class AgentStationsStatusApiTests(TestCase):
    """Desktop Agent "onlayn emas" bannerining zaxira (fallback)
    yangilanish endpointi — WebSocket orqali "onlayn" xabari yetib
    kelmasa ham, sahifa davriy so'rov orqali o'zini tuzata olishi
    uchun."""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test", subdomain="testagentstatus", setup_mode=False,
            custom_desktop_agent_stations=1,
        )
        self.ega = User.objects.create_user(username="ega1", password="secret123", type="ega", company=self.company)
        self.agent_user = User.objects.create_user(
            username="agent001", password="secret123", type="desktop_agent", company=self.company,
            tuliq_ismi="Stansiya 1",
        )
        self.client.force_login(self.ega)

    def test_offline_station_reported(self):
        response = self.client.get("/api/stansiyalar-holati/", SERVER_NAME="testagentstatus.localhost")
        self.assertEqual(response.status_code, 200)
        stations = response.json()["stations"]
        self.assertEqual(len(stations), 1)
        self.assertFalse(stations[0]["is_online"])

    def test_online_station_reported(self):
        self.agent_user.last_agent_heartbeat = timezone.now()
        self.agent_user.save(update_fields=["last_agent_heartbeat"])
        response = self.client.get("/api/stansiyalar-holati/", SERVER_NAME="testagentstatus.localhost")
        stations = response.json()["stations"]
        self.assertTrue(stations[0]["is_online"])

    def test_non_ega_gets_empty_list(self):
        pazanda = User.objects.create_user(
            username="pz1", password="secret123", type="ishlab_chiqaruvchi", company=self.company,
        )
        self.client.force_login(pazanda)
        response = self.client.get("/api/stansiyalar-holati/", SERVER_NAME="testagentstatus.localhost")
        self.assertEqual(response.json()["stations"], [])
