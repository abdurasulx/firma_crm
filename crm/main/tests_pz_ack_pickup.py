from django.test import TestCase
from django.utils import timezone

from main.models import Company, Mahsulot, MahsulotRetsept, MahsulotTuri, Pazanda, User
from main.services import task_service


class PzAckTaskPickupAjaxTests(TestCase):
    """Pazanda dashboardidagi "Oldim ✓" tugmasi (sanoq/hajm komponent
    uchun) endi AJAX orqali ham ishlaydi — sahifa qayta yuklanmasdan
    JSON javob qaytishi kerak."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testackpickup", setup_mode=False)
        self.ega = User.objects.create_user(username="ega1", password="secret123", type="ega", company=self.company)
        self.pz_user = User.objects.create_user(
            username="pz1", password="secret123", type="ishlab_chiqaruvchi", company=self.company,
        )
        self.pazanda = Pazanda.objects.create(user=self.pz_user, company=self.company)
        self.turi = MahsulotTuri.objects.create(nomi="dona")
        self.komponent = Mahsulot.objects.create(
            company=self.company, nomi="Qadoq", narxi=0, turi=self.turi,
            warehouse_type="semi_finished", ombor_turi="xom_ashyo", miqdori=1000,
        )
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Somsa", narxi=5000, turi=self.turi,
            warehouse_type="finished", mahsulot_turi="ishlab_chiqariladigan",
            serial_granularity="none",
        )
        MahsulotRetsept.objects.create(
            company=self.company, mahsulot=self.mahsulot, komponent=self.komponent, norma_miqdor=1,
        )
        task, err, _ = task_service.create_production_task(
            self.company, self.mahsulot, 1, timezone.localdate(), self.ega, pazanda=self.pazanda,
        )
        self.assertIsNone(err, err)
        self.pickup = task.material_pickups.get()
        self.client.force_login(self.pz_user)

    def _post(self, ajax=True):
        kwargs = {"SERVER_NAME": "testackpickup.localhost"}
        if ajax:
            kwargs["HTTP_X_REQUESTED_WITH"] = "XMLHttpRequest"
        return self.client.post(f"/vazifa/pickup/{self.pickup.id}/oldim/", {}, **kwargs)

    def test_ajax_ack_returns_json(self):
        response = self._post(ajax=True)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.pickup.refresh_from_db()
        self.assertTrue(self.pickup.tasdiqlangan)

    def test_non_ajax_ack_redirects(self):
        response = self._post(ajax=False)
        self.assertEqual(response.status_code, 302)
