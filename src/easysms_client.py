"""
KosmoSMS — easysms.gr API Client

Provides functions to interact with the easysms.gr REST API:
  - check_mobile()  — validate a phone number (free, no API key)
  - send_viber()    — send a Viber message with optional SMS fallback
  - send_sms()      — send an SMS message

API docs: https://easysms.gr/api/docs/en
"""

import logging
from typing import Optional

import requests

from config import cfg

logger = logging.getLogger(__name__)

# Timeout for all HTTP requests (seconds)
_TIMEOUT = 30


def check_mobile(phone: str) -> Optional[dict]:
    """
    Validate a phone number via api/mobile/check.

    This endpoint is FREE and does NOT require an API key.
    Returns a dict with keys: mobile{msisdn, national, country, countryCode,
    gsmCode, number, mcc, mnc, cost}, status, error, remarks.

    Returns None on error.
    """
    url = f"{cfg.EASYSMS_BASE_URL}/mobile/check"
    params = {
        "mobile": phone,
        "type": "json",
    }

    try:
        logger.debug("Checking mobile number: %s", phone)
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status")
        if str(status) == "1":
            mobile_info = data.get("mobile", {})
            logger.debug(
                "Mobile check OK for %s: msisdn=%s",
                phone, mobile_info.get("msisdn"),
            )
            return data
        else:
            logger.warning(
                "Mobile check failed for %s: error=%s, remarks=%s",
                phone, data.get("error"), data.get("remarks"),
            )
            return None

    except Exception:
        logger.exception("Error checking mobile number %s", phone)
        return None


def send_viber(
    to: str,
    text: str,
    from_id: Optional[str] = None,
    callback_url: Optional[str] = None,
    sms_fallback_text: Optional[str] = None,
    sms_from: Optional[str] = None,
) -> Optional[dict]:
    """
    Send a Viber message via api/viber/send.

    Uses the built-in sms_fallback=true parameter so that easysms.gr
    automatically falls back to SMS if Viber delivery fails.

    The Viber endpoint does NOT support a `callback` parameter for delivery
    reports. However, when sms_fallback is used and the fallback SMS is sent,
    the SMS callback mechanism applies to the fallback message.

    Returns the API response dict on success, None on error.
    Keys on success: id, cost, balance, status (1), error (0), remarks.
    """
    url = f"{cfg.EASYSMS_BASE_URL}/viber/send"
    payload = {
        "key": cfg.EASYSMS_API_KEY,
        "to": to,
        "text": text,
        "from": from_id or cfg.VIBER_SENDER_ID,
        "sms_fallback": "true",
        "sms_text": sms_fallback_text or text,
        "sms_from": sms_from or cfg.SMS_SENDER_ID,
        "ucs": "true",  # Greek characters in fallback SMS
        "type": "json",
    }

    try:
        logger.info("Sending Viber message to %s (from: %s)", to, payload["from"])
        resp = requests.post(url, data=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if str(data.get("status")) == "1":
            logger.info(
                "Viber message sent to %s, id=%s, cost=%s",
                to, data.get("id"), data.get("cost"),
            )
            return data
        else:
            logger.warning(
                "Viber send failed for %s: error=%s, remarks=%s",
                to, data.get("error"), data.get("remarks"),
            )
            return None

    except Exception:
        logger.exception("Error sending Viber message to %s", to)
        return None


def send_sms(
    to: str,
    text: str,
    from_id: Optional[str] = None,
    callback_url: Optional[str] = None,
) -> Optional[dict]:
    """
    Send an SMS via api/sms/send.

    Passes the `callback` parameter so easysms.gr calls our webhook
    with delivery status updates.

    Returns the API response dict on success, None on error.
    Keys on success: smsId, cost, balance, mcc, mnc, status (1), error (0), remarks.
    """
    url = f"{cfg.EASYSMS_BASE_URL}/sms/send"
    payload = {
        "key": cfg.EASYSMS_API_KEY,
        "to": to,
        "text": text,
        "from": from_id or cfg.SMS_SENDER_ID,
        "callback": callback_url or cfg.CALLBACK_URL,
        "ucs": "true",  # Required for Greek characters
        "type": "json",
    }

    try:
        logger.info("Sending SMS to %s (from: %s)", to, payload["from"])
        resp = requests.post(url, data=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if str(data.get("status")) == "1":
            logger.info(
                "SMS sent to %s, smsId=%s, cost=%s",
                to, data.get("smsId"), data.get("cost"),
            )
            return data
        else:
            logger.warning(
                "SMS send failed for %s: error=%s, remarks=%s",
                to, data.get("error"), data.get("remarks"),
            )
            return None

    except Exception:
        logger.exception("Error sending SMS to %s", to)
        return None
