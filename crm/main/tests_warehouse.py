from django.test import TestCase

from main.models import Company, Mahsulot, MahsulotTuri, Ombor, User


class WarehouseKirimTests(TestCase):
    """Ombor "kirim" (stock-in) oqimining asosiy stsenariylari —
    o'rtacha og'irlikdagi tannarx (weighted average) hisob-kitobi va
    tannarxning darhol (Saqlash tugmasisiz) qayta hisoblanishi."""

    def setUp(self):
        self.company = Company.objects.create(name="Test Firma", subdomain="testfirma", setup_mode=False)
        self.ega = User.objects.create_user(
            username="ega1", password="secret123", type="ega", company=self.company,
        )
        self.turi = MahsulotTuri.objects.create(nomi="kg")
        self.product = Mahsulot.objects.create(
            company=self.company, nomi="Un", narxi=0, turi=self.turi,
            warehouse_type="semi_finished", ombor_turi="xom_ashyo",
            miqdori=100, baza_tannarx=1000, tannarx=1000,
        )
        self.client.force_login(self.ega)

    def _post_kirim(self, qty, price):
        return self.client.post(
            "/ombor/kirim-chiqim/",
            {"movement_type": "in", "mahsulot": self.product.id, "qty": qty, "price": price},
            SERVER_NAME="testfirma.localhost",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_kirim_computes_weighted_average_and_updates_tannarx_immediately(self):
        # 100 kg @ 1000 so'm bor edi. Yana 100 kg @ 2000 so'm kirim qilinadi.
        # Kutilgan o'rtacha: (100*1000 + 100*2000) / 200 = 1500.
        response = self._post_kirim(100, 2000)
        self.assertEqual(response.status_code, 200)

        self.product.refresh_from_db()
        self.assertEqual(self.product.miqdori, 200)
        self.assertEqual(float(self.product.baza_tannarx), 1500)
        # `recompute_tannarx` "Saqlash" tugmasisiz, shu so'rovning o'zida
        # darhol qo'llanadi (Saqlash bosilguncha eskirib qolish bugi
        # shu sinov bilan ushlanadi).
        self.assertEqual(float(self.product.tannarx), 1500)

    def test_kirim_requires_warehouse_when_omborlar_exist(self):
        Ombor.objects.create(company=self.company, nomi="Asosiy ombor")
        response = self._post_kirim(50, 1000)
        self.assertEqual(response.status_code, 400)

        self.product.refresh_from_db()
        # Ombor tanlanmagani uchun kirim rad etilishi kerak — miqdor
        # o'zgarmagan bo'lishi shart.
        self.assertEqual(self.product.miqdori, 100)
