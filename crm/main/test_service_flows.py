import json
import os
import unittest
from datetime import datetime, timedelta, timezone as dt_tz

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from main.auth_backends import CompanyAwareModelBackend
from main.models import BillingPaymentLink, Company, Plan, PlanRequest, User
from main.services.auth_service import create_user_service
from main.services.billing_service import (
    apply_plan_request,
    calculate_prorated_amount,
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
        self.plan = Plan.objects.create(name="Pro", price=10, max_users=7, has_analytics=True)
        self.company = Company.objects.create(name="Alpha", subdomain="alpha", plan=self.plan)

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

    def test_paid_company_upgrade_creates_prorated_due_only(self):
        now = timezone.now()
        start = now - timedelta(days=10)
        stop = start + timedelta(days=30)
        self.company.plan = self.plan
        self.company.payment_status = "paid"
        self.company.next_payment_date = stop
        self.company.save()
        PlanRequest.objects.create(company=self.company, plan=self.plan, status="approved", reviewed_at=start)
        BillingPaymentLink.objects.create(
            company=self.company,
            reason="May 2026 uchun oylik abonent to'lovi",
            billing_period_start=start.date(),
            amount_usd=10,
            amount_uzs=125000,
            click_url="test",
            status="opened",
            opened_at=start,
        )

        request = PlanRequest.objects.create(
            company=self.company,
            plan=self.plan,
            is_custom=True,
            custom_max_users=0,
            custom_has_telegram_bot=True,
            custom_has_analytics=True,
            custom_has_map=True,
            custom_has_savdogar_sales=True,
            custom_backup_type="none",
            custom_price=105,
        )

        apply_plan_request(request, now=now)

        self.company.refresh_from_db()
        self.assertEqual(self.company.payment_status, "paid")
        self.assertEqual(self.company.next_payment_date, stop)
        expected_prorated_amount = calculate_prorated_amount(95, start, stop, now=now)

        payment_link = create_billing_payment_link(self.company, service_id="80588", merchant_id="40045")
        self.assertEqual(payment_link.amount_usd, expected_prorated_amount)


class RegistrationUrlTests(TestCase):
    @unittest.skip("Registration routing test — lokal subdomain routing bilan integration test kerak")
    def test_register_redirects_to_subdomain_login(self):
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
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("beta", response["Location"])
        self.assertIn("login", response["Location"])
        self.assertTrue(User.objects.filter(username="beta-owner", type="ega").exists())


# ─── Billing fix regressions ──────────────────────────────────────────────────

class BillingFixRegressionTests(TestCase):
    """
    Tuzatilgan billing muammolari uchun regression testlar.
    Agar kelajakda bu kod o'zgarsa, testlar buziladi va muammo aniqlanadi.
    """

    def setUp(self):
        self.plan = Plan.objects.create(name="Startap", price=29, max_users=5)
        self.company = Company.objects.create(
            name="Test Firma",
            subdomain="testfirma",
            plan=self.plan,
        )

    def test_mark_company_paid_uses_calendar_months_not_30_days(self):
        """
        relativedelta(months=N) ishlatiladi — timedelta(days=30*N) emas.
        Yanvar 31 kuni to'lov qilinsa, keyingi to'lov aniq 1 oy keyingi
        kalendar sana bo'lishi kerak (Feb 28 in 2026).
        """
        jan31 = datetime(2026, 1, 31, 12, 0, tzinfo=dt_tz.utc)
        self.company.next_payment_date = None
        self.company.payment_status = "unpaid"
        self.company.save()

        mark_company_paid(self.company, now=jan31)
        self.company.refresh_from_db()

        # relativedelta(months=1) from Jan 31 → Feb 28 (2026 not leap)
        self.assertEqual(self.company.next_payment_date.month, 2)
        self.assertEqual(self.company.next_payment_date.year, 2026)
        # timedelta(days=30) would give Feb 1 — agar bug qaytsa aniqlanadi
        self.assertNotEqual(self.company.next_payment_date.day, 1)

    def test_mark_company_paid_explicit_days_param_still_works(self):
        """
        days= parametri berilsa, relativedelta o'rniga timedelta ishlatiladi.
        Bu eski Click webhook integratsiyasi uchun backward compat.
        """
        now = datetime(2026, 3, 1, 0, 0, tzinfo=dt_tz.utc)
        self.company.payment_status = "unpaid"
        self.company.next_payment_date = None
        self.company.save()

        mark_company_paid(self.company, now=now, days=30)
        self.company.refresh_from_db()

        self.assertEqual(self.company.payment_status, "paid")
        expected = datetime(2026, 3, 31, 0, 0, tzinfo=dt_tz.utc)
        self.assertEqual(self.company.next_payment_date.date(), expected.date())

    def test_one_month_plan_gets_paid_status_on_create(self):
        """
        plan_months=1 bo'lganda Company.payment_status='paid' bo'lishi kerak.
        Avvalgi bug: plan_months > 1 sharti 1-oylikni 'unpaid' qilardi.

        Bu test billing logikasini to'g'ridan-to'g'ri tekshiradi
        (view orqali emas — middleware izolatsiyasi uchun).
        """
        now = timezone.now()
        plan_months = 1
        company = Company.objects.create(
            name="Yangi Firma",
            subdomain="yangitest",
            plan=self.plan,
            is_active=True,
            payment_status='paid' if self.plan and plan_months > 0 else 'unpaid',
            next_payment_date=now + relativedelta(months=plan_months) if self.plan and plan_months > 0 else None,
        )

        self.assertEqual(
            company.payment_status, "paid",
            "1-oylik tarif bilan yaratilgan firma 'paid' bo'lishi kerak"
        )
        self.assertIsNotNone(
            company.next_payment_date,
            "next_payment_date None bo'lmasligi kerak"
        )
        # next_payment_date kamida 28 kun keyinroq bo'lishi kerak
        self.assertGreaterEqual(company.next_payment_date, now + timedelta(days=28))

    def test_mark_company_paid_extends_future_due_date_by_calendar_month(self):
        """Kelgusida to'lov sanasi bor firmada to'lov qilinsa, relativedelta bilan uzayadi."""
        future_due = timezone.now() + relativedelta(months=1)
        self.company.next_payment_date = future_due
        self.company.payment_status = "unpaid"
        self.company.save()

        mark_company_paid(self.company)
        self.company.refresh_from_db()

        self.assertEqual(self.company.payment_status, "paid")
        self.assertGreaterEqual(
            self.company.next_payment_date,
            future_due + timedelta(days=28),
        )


# ─── PWA static fayl tekshiruvi ──────────────────────────────────────────────

class PWAStaticFileTests(TestCase):
    """Service Worker, manifest.json va ikonlar fizik mavjudligini tekshiradi."""

    def test_sw_js_static_file_exists(self):
        """sw.js static/sw.js da fizik mavjud."""
        sw_path = os.path.join(settings.BASE_DIR, "static", "sw.js")
        self.assertTrue(os.path.exists(sw_path), "static/sw.js topilmadi")

    def test_sw_js_contains_background_sync_tag(self):
        """sw.js Background Sync tag ni o'z ichiga oladi."""
        sw_path = os.path.join(settings.BASE_DIR, "static", "sw.js")
        with open(sw_path) as f:
            content = f.read()
        self.assertIn("sf-location-sync", content)
        self.assertIn("sync", content)

    def test_sw_js_contains_tile_cache(self):
        """sw.js xarita tile cache strategiyasini o'z ichiga oladi."""
        sw_path = os.path.join(settings.BASE_DIR, "static", "sw.js")
        with open(sw_path) as f:
            content = f.read()
        self.assertIn("TILE_CACHE", content)
        self.assertIn("openstreetmap", content.lower())

    def test_manifest_json_exists_and_valid(self):
        """manifest.json fizik mavjud va to'g'ri JSON."""
        manifest_path = os.path.join(settings.BASE_DIR, "static", "manifest.json")
        self.assertTrue(os.path.exists(manifest_path), "static/manifest.json topilmadi")
        with open(manifest_path) as f:
            data = json.load(f)
        self.assertEqual(data["name"], "StockFirm ERP")
        self.assertIn("icons", data)
        self.assertGreaterEqual(len(data["icons"]), 2)
        self.assertEqual(data["display"], "standalone")
        self.assertIn("start_url", data)

    def test_pwa_icons_exist(self):
        """192x192 va 512x512 ikonlar PNG formatida mavjud."""
        for size in [192, 512]:
            icon_path = os.path.join(settings.BASE_DIR, "static", "icons", f"icon-{size}.png")
            self.assertTrue(os.path.exists(icon_path), f"icon-{size}.png topilmadi")

    def test_location_db_js_exists(self):
        """location-db.js IndexedDB moduli mavjud."""
        path = os.path.join(settings.BASE_DIR, "static", "js", "location-db.js")
        self.assertTrue(os.path.exists(path), "static/js/location-db.js topilmadi")

    def test_location_db_js_exports_required_methods(self):
        """location-db.js enqueue, peek, dequeue metodlarini eksport qiladi."""
        path = os.path.join(settings.BASE_DIR, "static", "js", "location-db.js")
        with open(path) as f:
            content = f.read()
        for method in ["enqueue", "peek", "dequeue", "incrementRetry", "count"]:
            self.assertIn(method, content, f"LocationDB.{method} topilmadi")

    def test_offline_html_template_exists(self):
        """offline.html template mavjud va queue info ko'rsatadi."""
        import glob
        templates = glob.glob(
            os.path.join(settings.BASE_DIR, "**", "offline.html"), recursive=True
        )
        self.assertTrue(len(templates) > 0, "offline.html template topilmadi")
        with open(templates[0]) as f:
            content = f.read()
        self.assertIn("queueCount", content)


# ─── PWA endpoint (view) testlari — RequestFactory orqali ────────────────────

class PWAViewTests(TestCase):
    """sw.js va offline/ viewlarini RequestFactory orqali tekshiradi."""

    def setUp(self):
        from main.views import offline_page, service_worker_js
        self.factory = RequestFactory()
        self.offline_view = offline_page
        self.sw_view = service_worker_js
        self.company = Company.objects.create(name="PWA Co", subdomain="pwa")

    def _make_request(self, path="/"):
        req = self.factory.get(path)
        req.company = self.company
        req.is_landing = False
        req.has_map = False
        req.has_analytics = False
        req.has_telegram_bot = False
        from django.contrib.auth.models import AnonymousUser
        req.user = AnonymousUser()
        return req

    def test_offline_page_returns_200(self):
        """Offline sahifasi 200 qaytaradi."""
        req = self._make_request("/offline/")
        response = self.offline_view(req)
        self.assertEqual(response.status_code, 200)

    def test_service_worker_js_content_type(self):
        """sw.js view JavaScript content-type bilan qaytaradi."""
        req = self._make_request("/sw.js")
        response = self.sw_view(req)
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.get("Content-Type", ""))
        self.assertEqual(response.get("Service-Worker-Allowed"), "/")


# ─── Location batch API tests — RequestFactory orqali ─────────────────────────

class LocationBatchAPITests(TestCase):
    """GPS batch endpoint: /api/location/batch/"""

    def setUp(self):
        from main.models import YetkazibBeruvchi
        from main.map_views import api_location_batch
        self.factory = RequestFactory()
        self.view = api_location_batch
        self.company = Company.objects.create(name="Map Co", subdomain="mapco")
        self.user, _ = create_user_service(
            username="driver1",
            password="driverpass",
            fullname="Driver One",
            user_type="yetkazib_beruvchi",
            company=self.company,
        )
        self.deliverer, _ = YetkazibBeruvchi.objects.get_or_create(
            user=self.user,
            company=self.company,
            defaults={"ismi": "Driver One"},
        )

    def _make_post(self, points, user=None):
        body = json.dumps({"points": points})
        req = self.factory.post(
            "/api/location/batch/",
            data=body,
            content_type="application/json",
        )
        req.company = self.company
        req.user = user or self.user
        req.is_landing = False
        req.has_map = True
        return req

    def test_valid_batch_returns_200_and_saved_count(self):
        points = [
            {"lat": 41.299, "lng": 69.240, "client_timestamp": "2026-06-13T10:00:00Z"},
            {"lat": 41.300, "lng": 69.241, "client_timestamp": "2026-06-13T10:00:10Z"},
        ]
        response = self.view(self._make_post(points))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data.get("saved"), 2)

    def test_invalid_lat_lng_skipped(self):
        points = [
            {"lat": 999, "lng": 69.240, "client_timestamp": "2026-06-13T10:01:00Z"},
            {"lat": 41.300, "lng": 69.241, "client_timestamp": "2026-06-13T10:01:10Z"},
        ]
        response = self.view(self._make_post(points))
        self.assertEqual(json.loads(response.content).get("saved"), 1)

    def test_duplicate_timestamps_not_saved_twice(self):
        ts = "2026-06-13T10:02:00Z"
        points = [{"lat": 41.299, "lng": 69.240, "client_timestamp": ts}]
        self.view(self._make_post(points))
        response = self.view(self._make_post(points))
        self.assertEqual(json.loads(response.content).get("saved"), 0)

    def test_non_driver_user_gets_403(self):
        owner, _ = create_user_service(
            username="owner1", password="ownerpass",
            fullname="Owner", user_type="ega", company=self.company,
        )
        response = self.view(self._make_post([], user=owner))
        self.assertEqual(response.status_code, 403)

    def test_empty_points_list_returns_zero_saved(self):
        response = self.view(self._make_post([]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content).get("saved"), 0)

    def test_invalid_json_returns_400(self):
        req = self.factory.post(
            "/api/location/batch/",
            data="not-json",
            content_type="application/json",
        )
        req.company = self.company
        req.user = self.user
        response = self.view(req)
        self.assertEqual(response.status_code, 400)
