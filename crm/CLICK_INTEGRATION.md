# Click Integration

Production callback endpoints:

- `https://starify.uz/api/click/prepare/`
- `https://starify.uz/api/click/complete/`

Both endpoints accept only `POST` with `Content-Type: application/x-www-form-urlencoded` and return JSON.

## Environment

```env
SERVICE_ID=your-click-service-id
MERCHANT_ID=your-click-merchant-id
SECRET_KEY=your-click-secret-key
CLICK_ALLOWED_IPS=
```

`CLICK_ALLOWED_IPS` is optional. Keep it empty until Click gives the final callback IP list, then set a comma-separated allow-list.

## Internal Order

`merchant_trans_id` is the internal `BillingPaymentLink.id`. The callback validates that the payment link exists, is not already paid/canceled, and that `amount` exactly matches `BillingPaymentLink.amount_uzs`.

## Signatures

Prepare:

```text
md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id + amount + action + sign_time)
```

Complete:

```text
md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id + merchant_prepare_id + amount + action + sign_time)
```

## Test Helper

Generate a signed Prepare curl:

```powershell
D:\firma_crm\vwin\Scripts\python.exe manage.py simulate_click prepare 123 1000 --base-url https://starify.uz
```

Generate a signed Complete curl after Prepare returns `merchant_prepare_id`:

```powershell
D:\firma_crm\vwin\Scripts\python.exe manage.py simulate_click complete 123 1000 --merchant-prepare-id 456 --base-url https://starify.uz
```

Send the request instead of only printing curl:

```powershell
D:\firma_crm\vwin\Scripts\python.exe manage.py simulate_click prepare 123 1000 --base-url https://starify.uz --send
```

## Example Curl Shape

```bash
curl -X POST "https://starify.uz/api/click/prepare/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "click_trans_id=1000001" \
  --data-urlencode "service_id=$SERVICE_ID" \
  --data-urlencode "click_paydoc_id=9000001" \
  --data-urlencode "merchant_trans_id=123" \
  --data-urlencode "amount=1000.00" \
  --data-urlencode "action=0" \
  --data-urlencode "error=0" \
  --data-urlencode "error_note=Success" \
  --data-urlencode "sign_time=2026-04-21 12:00:00" \
  --data-urlencode "sign_string=<prepare-md5>"
```

```bash
curl -X POST "https://starify.uz/api/click/complete/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "click_trans_id=1000001" \
  --data-urlencode "service_id=$SERVICE_ID" \
  --data-urlencode "click_paydoc_id=9000001" \
  --data-urlencode "merchant_trans_id=123" \
  --data-urlencode "merchant_prepare_id=456" \
  --data-urlencode "amount=1000.00" \
  --data-urlencode "action=1" \
  --data-urlencode "error=0" \
  --data-urlencode "error_note=Success" \
  --data-urlencode "sign_time=2026-04-21 12:00:10" \
  --data-urlencode "sign_string=<complete-md5>"
```

## Logs

Callbacks are logged to:

```text
logs/click.log
```

Each line includes incoming params, calculated signature, JSON response, client IP, and execution time in milliseconds.

## Debugging -1905

Click-side `-1905` usually means Click could not complete the callback contract with your server: URL is not reachable from Click, HTTPS/certificate/proxy is wrong, your endpoint is too slow, the callback returns invalid JSON, the service URLs in merchant cabinet do not match production, or the signature/amount response makes Click reject the flow. Check `logs/click.log`, web server access logs, HTTPS certificate validity, callback URL paths, and compare Click's sent `sign_string` with the logged calculated signature.
