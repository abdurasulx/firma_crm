import hashlib
import hmac
import logging
import time
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from main.models import BillingPaymentLink, ClickTransaction
from .services.billing_service import mark_company_paid


logger = logging.getLogger("click")

PREPARE_REQUIRED = (
    "click_trans_id",
    "service_id",
    "click_paydoc_id",
    "merchant_trans_id",
    "amount",
    "action",
    "error",
    "error_note",
    "sign_time",
    "sign_string",
)
COMPLETE_REQUIRED = PREPARE_REQUIRED + ("merchant_prepare_id",)

ERROR_INVALID_SIGNATURE = {"error": -1, "error_note": "Invalid signature"}
ERROR_AMOUNT = {"error": -2, "error_note": "Incorrect parameter amount"}
ERROR_ACTION = {"error": -3, "error_note": "Action not found"}
ERROR_ALREADY_PAID = {"error": -4, "error_note": "Already paid"}
ERROR_ORDER_NOT_FOUND = {"error": -5, "error_note": "User does not exist"}
ERROR_TRANSACTION_NOT_FOUND = {"error": -6, "error_note": "Transaction does not exist"}
ERROR_UPDATE = {"error": -7, "error_note": "Failed to update user"}
ERROR_REQUEST = {"error": -8, "error_note": "Error in request from click"}
ERROR_CANCELLED = {"error": -9, "error_note": "Transaction cancelled"}
SUCCESS_NOTE = "Success"


def _click_secret_key():
    return (
        getattr(settings, "CLICK_SECRET_KEY", "")
        or getattr(settings, "SECRET_KEY", "")
    )


def _click_service_id():
    return str(getattr(settings, "CLICK_SERVICE_ID", "") or "")


def _request_params(request):
    return {key: request.POST.get(key, "") for key in request.POST.keys()}


def _json_response(payload):
    return JsonResponse(payload, json_dumps_params={"ensure_ascii": False})


def _is_form_post(request):
    content_type = (request.META.get("CONTENT_TYPE") or "").split(";")[0].strip().lower()
    return request.method == "POST" and content_type == "application/x-www-form-urlencoded"


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _ip_allowed(request):
    allowed_ips = getattr(settings, "CLICK_ALLOWED_IPS", [])
    if not allowed_ips:
        return True
    return _client_ip(request) in allowed_ips


def _missing_params(params, required):
    return [name for name in required if params.get(name) in (None, "")]


def calculate_click_signature(params, action):
    action = str(action)
    parts = [
        params.get("click_trans_id", ""),
        params.get("service_id", ""),
        _click_secret_key(),
        params.get("merchant_trans_id", ""),
    ]
    if action == "1":
        parts.append(params.get("merchant_prepare_id", ""))
    parts.extend([
        params.get("amount", ""),
        params.get("action", ""),
        params.get("sign_time", ""),
    ])
    raw_signature = "".join(parts)
    return hashlib.md5(raw_signature.encode("utf-8")).hexdigest()


def _signature_valid(params, action):
    calculated = calculate_click_signature(params, action)
    received = params.get("sign_string", "")
    return hmac.compare_digest(calculated, received), calculated


def _decimal_amount(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _amount_matches(click_amount, order_amount):
    parsed = _decimal_amount(click_amount)
    if parsed is None:
        return False
    return parsed == Decimal(order_amount).quantize(Decimal("0.01"))


def _log_callback(endpoint, params, response, started_at, calculated_signature="", level=logging.INFO):
    duration_ms = round((time.monotonic() - started_at) * 1000, 2)
    logger.log(
        level,
        "endpoint=%s client_ip=%s params=%s calculated_signature=%s response=%s execution_time_ms=%s",
        endpoint,
        params.pop("_client_ip", ""),
        params,
        calculated_signature,
        response,
        duration_ms,
    )


def _validate_common_request(request, params, required, expected_action):
    if not _is_form_post(request):
        return ERROR_REQUEST, ""
    if not _ip_allowed(request):
        return ERROR_REQUEST, ""

    missing = _missing_params(params, required)
    if missing:
        return ERROR_REQUEST, ""

    if params.get("service_id") != _click_service_id():
        return ERROR_REQUEST, ""

    if str(params.get("action")) != str(expected_action):
        return ERROR_ACTION, ""

    if _decimal_amount(params.get("amount")) is None:
        return ERROR_AMOUNT, ""

    is_valid, calculated_signature = _signature_valid(params, expected_action)
    if not is_valid:
        return ERROR_INVALID_SIGNATURE, calculated_signature

    return None, calculated_signature


def _get_payment_link_for_update(merchant_trans_id):
    try:
        return BillingPaymentLink.objects.select_for_update().select_related("company").get(pk=merchant_trans_id)
    except (BillingPaymentLink.DoesNotExist, ValueError, TypeError):
        return None


def _response_for_existing_prepare(tx, params):
    if tx.status == "paid":
        return ERROR_ALREADY_PAID
    if tx.status in ("canceled", "error"):
        return ERROR_CANCELLED
    if str(tx.merchant_trans_id) != str(params.get("merchant_trans_id")):
        return ERROR_TRANSACTION_NOT_FOUND
    if _decimal_amount(params.get("amount")) != Decimal(tx.amount).quantize(Decimal("0.01")):
        return ERROR_AMOUNT
    return {
        "click_trans_id": params.get("click_trans_id"),
        "merchant_trans_id": params.get("merchant_trans_id"),
        "merchant_prepare_id": tx.id,
        "error": 0,
        "error_note": SUCCESS_NOTE,
    }


def click_pay_redirect(request):
    return redirect("billing_page")


@csrf_exempt
def click_prepare(request):
    started_at = time.monotonic()
    params = _request_params(request)
    params["_client_ip"] = _client_ip(request)
    response = ERROR_REQUEST
    calculated_signature = ""

    try:
        validation_error, calculated_signature = _validate_common_request(request, params, PREPARE_REQUIRED, 0)
        if validation_error:
            response = validation_error
            return _json_response(response)

        with transaction.atomic():
            existing_tx = (
                ClickTransaction.objects.select_for_update()
                .filter(click_trans_id=params["click_trans_id"])
                .order_by("id")
                .first()
            )
            if existing_tx:
                response = _response_for_existing_prepare(existing_tx, params)
                return _json_response(response)

            payment_link = _get_payment_link_for_update(params["merchant_trans_id"])
            if not payment_link:
                response = ERROR_ORDER_NOT_FOUND
                return _json_response(response)

            if payment_link.status == "paid":
                response = ERROR_ALREADY_PAID
                return _json_response(response)
            if payment_link.status in ("failed", "canceled"):
                response = ERROR_CANCELLED
                return _json_response(response)
            if not _amount_matches(params["amount"], payment_link.amount_uzs):
                response = ERROR_AMOUNT
                return _json_response(response)

            try:
                tx = ClickTransaction.objects.create(
                    click_trans_id=params["click_trans_id"],
                    click_paydoc_id=params["click_paydoc_id"],
                    service_id=params["service_id"],
                    merchant_trans_id=params["merchant_trans_id"],
                    company=payment_link.company,
                    amount=_decimal_amount(params["amount"]),
                    action=0,
                    sign_time=params["sign_time"],
                    sign_string=params["sign_string"],
                    status="processing",
                    payment_reason=payment_link.reason,
                )
            except IntegrityError:
                tx = ClickTransaction.objects.select_for_update().get(click_trans_id=params["click_trans_id"])
                response = _response_for_existing_prepare(tx, params)
                return _json_response(response)

            if payment_link.status == "created":
                payment_link.status = "opened"
                payment_link.opened_at = timezone.now()
                payment_link.save(update_fields=["status", "opened_at"])

            response = {
                "click_trans_id": params["click_trans_id"],
                "merchant_trans_id": params["merchant_trans_id"],
                "merchant_prepare_id": tx.id,
                "error": 0,
                "error_note": SUCCESS_NOTE,
            }
            return _json_response(response)
    except Exception:
        logger.exception("Unhandled Click prepare error params=%s", params)
        response = ERROR_REQUEST
        return _json_response(response)
    finally:
        _log_callback("prepare", params.copy(), response, started_at, calculated_signature)


@csrf_exempt
def click_complete(request):
    started_at = time.monotonic()
    params = _request_params(request)
    params["_client_ip"] = _client_ip(request)
    response = ERROR_REQUEST
    calculated_signature = ""

    try:
        validation_error, calculated_signature = _validate_common_request(request, params, COMPLETE_REQUIRED, 1)
        if validation_error:
            response = validation_error
            return _json_response(response)

        click_error = int(params.get("error", "0"))

        with transaction.atomic():
            tx = (
                ClickTransaction.objects.select_for_update().select_related("company")
                .filter(
                    id=params["merchant_prepare_id"],
                    click_trans_id=params["click_trans_id"],
                    merchant_trans_id=params["merchant_trans_id"],
                )
                .first()
            )
            if not tx:
                response = ERROR_TRANSACTION_NOT_FOUND
                return _json_response(response)

            payment_link = _get_payment_link_for_update(params["merchant_trans_id"])
            if not payment_link:
                response = ERROR_ORDER_NOT_FOUND
                return _json_response(response)

            if tx.status == "paid" or payment_link.status == "paid":
                response = ERROR_ALREADY_PAID
                return _json_response(response)
            if tx.status in ("canceled", "error") or payment_link.status in ("failed", "canceled"):
                response = ERROR_CANCELLED
                return _json_response(response)
            if not _amount_matches(params["amount"], payment_link.amount_uzs):
                response = ERROR_AMOUNT
                return _json_response(response)

            if click_error < 0:
                tx.status = "canceled"
                tx.error_reason = f"{params.get('error')}: {params.get('error_note', '')}"
                tx.cancel_time = timezone.now()
                tx.save(update_fields=["status", "error_reason", "cancel_time"])

                payment_link.status = "failed"
                payment_link.save(update_fields=["status"])
                response = ERROR_CANCELLED
                return _json_response(response)

            tx.status = "paid"
            tx.action = 1
            tx.perform_time = timezone.now()
            tx.save(update_fields=["status", "action", "perform_time"])

            mark_company_paid(tx.company, now=timezone.now())

            payment_link.status = "paid"
            payment_link.paid_at = timezone.now()
            payment_link.save(update_fields=["status", "paid_at"])

            response = {
                "click_trans_id": params["click_trans_id"],
                "merchant_trans_id": params["merchant_trans_id"],
                "merchant_confirm_id": tx.id,
                "error": 0,
                "error_note": SUCCESS_NOTE,
            }
            return _json_response(response)
    except (TypeError, ValueError):
        response = ERROR_REQUEST
        return _json_response(response)
    except Exception:
        logger.exception("Unhandled Click complete error params=%s", params)
        response = ERROR_UPDATE
        return _json_response(response)
    finally:
        _log_callback("complete", params.copy(), response, started_at, calculated_signature)
