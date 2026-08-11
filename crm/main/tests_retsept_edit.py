from django.test import TestCase

from main.models import Company, Mahsulot, MahsulotRetsept, MahsulotTuri, User


class RetseptRowEditTests(TestCase):
    """Retsept qatorining norma_miqdorini TO'G'RIDAN-TO'G'RI tahrirlash
    (mavjud komponentni qayta tanlamasdan) — `seemahsulot` sahifasidagi
    yangi inline forma `add_retsept_row`ni mavjud komponent bilan qayta
    chaqiradi, bu `update_or_create` bo'lgani uchun yangilanishi kerak,
    ikkinchi qator YARATILMASLIGI kerak."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testretsept", setup_mode=False)
        self.ega = User.objects.create_user(username="ega1", password="secret123", type="ega", company=self.company)
        self.turi = MahsulotTuri.objects.create(nomi="kg")
        self.komponent = Mahsulot.objects.create(
            company=self.company, nomi="Un", narxi=0, turi=self.turi,
            warehouse_type="semi_finished", ombor_turi="xom_ashyo", miqdori=1000, tannarx=1000,
        )
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Somsa", narxi=5000, turi=self.turi,
            warehouse_type="finished", mahsulot_turi="ishlab_chiqariladigan",
        )
        MahsulotRetsept.objects.create(
            company=self.company, mahsulot=self.mahsulot, komponent=self.komponent, norma_miqdor=0.5,
        )
        self.client.force_login(self.ega)

    def test_edit_updates_existing_row_not_duplicate(self):
        response = self.client.post(
            f"/product/{self.mahsulot.id}/",
            {"action": "add_retsept_row", "komponent": self.komponent.id, "norma_miqdor": "0.8"},
            SERVER_NAME="testretsept.localhost",
        )
        self.assertEqual(response.status_code, 302)
        rows = MahsulotRetsept.objects.filter(company=self.company, mahsulot=self.mahsulot)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().norma_miqdor, 0.8)

    def test_edit_recomputes_tannarx(self):
        self.client.post(
            f"/product/{self.mahsulot.id}/",
            {"action": "add_retsept_row", "komponent": self.komponent.id, "norma_miqdor": "2"},
            SERVER_NAME="testretsept.localhost",
        )
        self.mahsulot.refresh_from_db()
        self.assertEqual(self.mahsulot.baza_tannarx, 2000)  # 2 * 1000
