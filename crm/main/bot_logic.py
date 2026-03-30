import hashlib
import hmac
from django.conf import settings
import requests
import logging

logger = logging.getLogger(__name__)

def generate_tg_link_token(tg_id):
    """
    Generates a secure hash for a Telegram ID.
    Used to prevent spoofing of the tg_id parameter in URLs.
    """
    secret = settings.SECRET_KEY.encode()
    hash_obj = hmac.new(secret, str(tg_id).encode(), hashlib.sha256)
    return hash_obj.hexdigest()

def verify_tg_link_token(tg_id, token):
    """
    Verifies if the provided token matches the hash of the tg_id.
    """
    if not tg_id or not token:
        return False
    expected_token = generate_tg_link_token(tg_id)
    return hmac.compare_digest(expected_token, token)

def send_telegram_notification(chat_id, text):
    """
    Sends a message to a Telegram chat.
    Expects TELEGRAM_BOT_TOKEN in settings.
    """
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not found in settings.")
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False
