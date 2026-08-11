from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from main.models import (
    Company, HaridorDukon, Mahsulot, MahsulotTuri, Serial, User, YetkazibBeruvchi,
)


def _fake_image():
    # 1x1 shaffof PNG — rasm/skan maydonlarini to'ldirish uchun, mazmuni muhim emas.
    content = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
        b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    return SimpleUploadedFile('test.png', content, content_type='image/png')


class YetkazibBeruvchiUnregisteredQrSaleTests(TestCase):
    """Yetkazib beruvchi Desktop Agent orqali hali "yuklamaga olmagan"
    (holati hamon 'omborda') QR kodni to'g'ridan-to'g'ri sotuvga
    kiritmoqchi bo'lsa — aniq, tushunarli ogohlantirish chiqishi kerak
    (avval umumiy "yaroqsiz yoki ishlatilgan" xabari chiqar edi)."""

    def setUp(self):
        self.company = Company.objects.create(name="Test", subdomain="testqrsale", setup_mode=False)
        self.yb_user = User.objects.create_user(
            username="yb1", password="secret123", type="yetkazib_beruvchi", company=self.company,
        )
        self.yb = YetkazibBeruvchi.objects.create(
            user=self.yb_user, company=self.company, tuliq_ismi="YB Test",
            mahsulotlar="Kola 5,",
        )
        self.turi = MahsulotTuri.objects.create(nomi="dona")
        self.mahsulot = Mahsulot.objects.create(
            company=self.company, nomi="Kola", narxi=10000, turi=self.turi,
            warehouse_type="finished", serial_granularity="unit", miqdori=5,
        )
        self.serial = Serial.objects.create(
            company=self.company, mahsulot=self.mahsulot, kod="QR-NOT-REGISTERED", holati="omborda",
        )
        self.haridor = HaridorDukon.objects.create(company=self.company, nomi="Do'kon")
        self.client.force_login(self.yb_user)

    def _post(self):
        return self.client.post(
            "/sotish/",
            {
                "st": "naqd",
                "haridor": self.haridor.id,
                "miqdor_Kola": "1",
                "serial_kodlari_Kola": self.serial.kod,
                "rasm": _fake_image(),
            },
            SERVER_NAME="testqrsale.localhost",
        )

    def test_unregistered_qr_gives_specific_warning(self):
        response = self._post()
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("hali agentda ro'yxatdan o'tkazilmagan" in str(m) for m in messages), messages)

    def test_unregistered_qr_does_not_create_sale(self):
        from main.models import Savdo
        self._post()
        self.assertEqual(Savdo.objects.count(), 0)
        self.serial.refresh_from_db()
        self.assertEqual(self.serial.holati, "omborda")
