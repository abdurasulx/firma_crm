from django.test import TestCase

from main.models import Company, User


class ProfileViewTests(TestCase):
    def test_self_profile_page_renders_for_yetkazib_beruvchi(self):
        company = Company.objects.create(name="Test Co", subdomain="testco", setup_mode=False)
        user = User.objects.create_user(
            username="yb1",
            password="secret123",
            type="yetkazib_beruvchi",
            company=company,
        )
        self.client.force_login(user)

        response = self.client.get(
            f"/profile/{user.username}", SERVER_NAME="testco.localhost"
        )

        self.assertEqual(response.status_code, 200)
