import hashlib
from datetime import datetime

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def _signature(params, action):
    parts = [
        str(params["click_trans_id"]),
        str(params["service_id"]),
        settings.CLICK_SECRET_KEY,
        str(params["merchant_trans_id"]),
    ]
    if str(action) == "1":
        parts.append(str(params["merchant_prepare_id"]))
    parts.extend([
        str(params["amount"]),
        str(params["action"]),
        str(params["sign_time"]),
    ])
    return hashlib.md5("".join(parts).encode("utf-8")).hexdigest()


class Command(BaseCommand):
    help = "Generate or send signed Click Prepare/Complete requests for local testing."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["prepare", "complete"])
        parser.add_argument("merchant_trans_id")
        parser.add_argument("amount")
        parser.add_argument("--base-url", default="https://starify.uz")
        parser.add_argument("--click-trans-id", default=None)
        parser.add_argument("--click-paydoc-id", default=None)
        parser.add_argument("--merchant-prepare-id", default=None)
        parser.add_argument("--send", action="store_true")

    def handle(self, *args, **options):
        click_trans_id = options["click_trans_id"] or datetime.now().strftime("%Y%m%d%H%M%S")
        click_paydoc_id = options["click_paydoc_id"] or click_trans_id
        action_number = "0" if options["action"] == "prepare" else "1"

        params = {
            "click_trans_id": click_trans_id,
            "service_id": settings.CLICK_SERVICE_ID,
            "click_paydoc_id": click_paydoc_id,
            "merchant_trans_id": options["merchant_trans_id"],
            "amount": options["amount"],
            "action": action_number,
            "error": "0",
            "error_note": "Success",
            "sign_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        if options["action"] == "complete":
            if not options["merchant_prepare_id"]:
                raise CommandError("--merchant-prepare-id is required for complete")
            params["merchant_prepare_id"] = options["merchant_prepare_id"]

        params["sign_string"] = _signature(params, action_number)

        endpoint = f'{options["base_url"].rstrip("/")}/api/click/{options["action"]}/'
        curl_parts = [
            "curl -X POST",
            f'"{endpoint}"',
            '-H "Content-Type: application/x-www-form-urlencoded"',
        ]
        for key, value in params.items():
            curl_parts.append(f'--data-urlencode "{key}={value}"')
        self.stdout.write(" \\\n  ".join(curl_parts))

        if options["send"]:
            response = requests.post(endpoint, data=params, timeout=3)
            self.stdout.write(response.text)
