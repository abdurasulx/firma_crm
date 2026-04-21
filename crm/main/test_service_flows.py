from datetime import timedelta

from django.test import RequestFactory, TestCase
from django.utils import timezone

from main.auth_backends import CompanyAwareModelBackend
from main.models import BillingPaymentLink, Company, Plan, PlanRequest, User
from main.services.auth_service import create_user_service
from main.services.billing_service import (
    apply_plan_request,
    consume_billing_payment_link,
    create_billing_payment_link,
    mark_company_paid,
    reject_plan_request,
    sync_company_lifecycle,
)


class AuthServiceTests(TestCase):
    def test_create_user_service_persists_required_type(self):
        company = Company.objects.create(name="Test Co", subdomain="test-co")

        user, message = create_user_service(
            username="owner",
            password="secret123",
            fullname="Owner User",
            user_type="ega",
            phone="+998900000000",
            company=company,
        )

        self.assertIsNotNone(user, message)
        user.refresh_from_db()
        self.assertEqual(user.type, "ega")
        self.assertTrue(user.check_password("secret123"))

    def test_same_username_can_exist_in_different_companies(self):
        company_one = Company.objects.create(name="One", subdomain="one")
        company_two = Company.objects.create(name="Two", subdomain="two")

        first_user, _ = create_user_service("ninetydev", "secret123", "First", "ega", company=company_one)
        second_user, _ = create_user_service("ninetydev", "secret456", "Second", "ega", company=company_two)

        self.assertIsNotNone(first_user)
        self.assertIsNotNone(second_user)
        self.assertNotEqual(first_user.company_id, second_user.company_id)

    def test_auth_backend_authenticates_within_current_company_only(self):
        company_one = Company.objects.create(name="One", subdomain="one")
        company_two = Company.objects.create(name="Two", subdomain="two")
        create_user_service("ninetydev", "secret123", "First", "ega", company=company_one)
        company_two_user, _ = create_user_service("ninetydev", "secret456", "Second", "ega", company=company_two)

        request = RequestFactory().post("/login/")
        request.company = company_two
        request.is_admin_panel = False

        user = CompanyAwareModelBackend().authenticate(request, username="ninetydev", password="secret456")
        self.assertEqual(user.pk, company_two_user.pk)


class BillingServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Alpha", subdomain="alpha")
        self.plan = Plan.objects.create(name="Pro", price=10, max_users=7, has_analytics=True)

    def test_apply_standard_plan_request_sets_grace_period_and_clears_trial(self):
        self.company.is_on_trial = True
        self.company.trial_expires_at = timezone.now() + timedelta(days=10)
        self.company.save()
        request = PlanRequest.objects.create(company=self.company, plan=self.plan)

        before = timezone.now()
        apply_plan_request(request)

        self.company.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual(request.status, "approved")
        self.assertEqual(self.company.plan, self.plan)
        self.assertEqual(self.company.payment_status, "unpaid")
        self.assertFalse(self.company.is_on_trial)
        self.assertIsNotNone(self.company.next_payment_date)
        self.assertGreaterEqual(self.company.next_payment_date, before + timedelta(days=5))

    def test_reject_plan_request_uses_reviewed_at(self):
        request = PlanRequest.objects.create(company=self.company, plan=self.plan)

        reject_plan_request(request)

        request.refresh_from_db()
        self.assertEqual(request.status, "rejected")
        self.assertIsNotNone(request.reviewed_at)

    def test_sync_company_lifecycle_expires_trial_without_plan(self):
        expired_company = Company.objects.create(
            name="Trial Co",
            subdomain="trial-co",
            is_on_trial=True,
            trial_expires_at=timezone.now() - timedelta(days=1),
            is_active=True,
        )

        result = sync_company_lifecycle(expired_company)

        expired_company.refresh_from_db()
        self.assertTrue(result["changed"])
        self.assertFalse(expired_company.is_on_trial)
        self.assertFalse(expired_company.is_active)

    def test_mark_company_paid_extends_from_existing_future_due_date(self):
        future_due = timezone.now() + timedelta(days=12)
        self.company.next_payment_date = future_due
        self.company.payment_status = "unpaid"
        self.company.save()

        mark_company_paid(self.company)

        self.company.refresh_from_db()
        self.assertEqual(self.company.payment_status, "paid")
        self.assertGreaterEqual(self.company.next_payment_date, future_due + timedelta(days=30))

    def test_create_and_consume_payment_link(self):
        payment_link = create_billing_payment_link(self.company, service_id="80588", merchant_id="40045")

        self.assertEqual(payment_link.status, "created")
        self.assertIn(f"transaction_param={payment_link.id}", payment_link.click_url)

        payment_link = consume_billing_payment_link(payment_link)
        payment_link.refresh_from_db()
        self.assertEqual(payment_link.status, "opened")
        self.assertIsNotNone(payment_link.opened_at)


class RegistrationUrlTests(TestCase):
    def test_register_redirects_to_current_host_base_domain(self):
        response = self.client.post(
            "/register/",
            {
                "company_name": "Beta",
                "subdomain": "beta",
                "full_name": "Beta Owner",
                "username": "beta-owner",
                "password": "secret123",
                "phone": "+998901234567",
            },
            HTTP_HOST="crm.stockfirm.uz",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://beta.crm.stockfirm.uz/login/")
        self.assertTrue(User.objects.filter(username="beta-owner", type="ega").exists())
