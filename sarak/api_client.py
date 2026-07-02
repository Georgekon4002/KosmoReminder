"""
SMS/Viber API Client.

Generic REST client configurable for any platform.
Includes ready-made adapters for:
  • Generic REST (default)
  • Apifon  (https://apifon.com)
  • Yuboto  (https://yuboto.com)

Set config.api.platform = "generic" | "apifon" | "yuboto"
"""
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import APIConfig

logger = logging.getLogger(__name__)


# ── Result dataclass ───────────────────────────────────────────────────────

@dataclass
class SendResult:
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None

    def __repr__(self):
        if self.success:
            return f"SendResult(ok, id={self.message_id})"
        return f"SendResult(FAIL, error={self.error})"


# ── Base client ────────────────────────────────────────────────────────────

class SMSViberClient:
    """Generic REST API client for SMS/Viber platforms."""

    def __init__(self, config: APIConfig):
        self.config = config
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        # Retry on connection errors and 5xx
        retry = Retry(
            total=self.config.retry_count,
            backoff_factor=self.config.retry_delay_seconds,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self._set_auth(session)
        return session

    def _set_auth(self, session: requests.Session):
        """Override this in platform subclasses if auth differs."""
        if self.config.api_key:
            session.headers["Authorization"] = f"Bearer {self.config.api_key}"

    # ── Single-message sends ───────────────────────────────────────────────

    def send_sms(self, phone: str, message: str) -> SendResult:
        payload = {
            "to": phone,
            "message": message,
            "from": self.config.sender_sms,
            "type": "sms",
        }
        return self._post_single(payload)

    def send_viber(self, phone: str, message: str) -> SendResult:
        payload = {
            "to": phone,
            "message": message,
            "from": self.config.sender_viber,
            "type": "viber",
        }
        return self._post_single(payload)

    def _post_single(self, payload: dict) -> SendResult:
        try:
            resp = self.session.post(
                f"{self.config.base_url}/send",
                json=payload,
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return SendResult(
                success=True,
                message_id=str(data.get("message_id") or data.get("id") or ""),
            )
        except requests.HTTPError as exc:
            return SendResult(success=False, error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            return SendResult(success=False, error=str(exc))

    # ── Batch send ─────────────────────────────────────────────────────────

    def send_batch(self, messages: List[Dict[str, Any]]) -> Dict[int, SendResult]:
        """
        Try batch endpoint first; fall back to per-message sends.
        messages: list of dicts with keys: ID, PHONE, MESSAGE, TYPE
        """
        results: Dict[int, SendResult] = {}

        # Build batch payload
        items = []
        for msg in messages:
            msg_type = (msg.get("TYPE") or "SMS").upper()
            items.append({
                "ref": str(msg["ID"]),
                "to": msg["PHONE"],
                "message": msg["MESSAGE"],
                "from": self.config.sender_viber if msg_type == "VIBER" else self.config.sender_sms,
                "type": msg_type.lower(),
            })

        try:
            resp = self.session.post(
                f"{self.config.base_url}/send/batch",
                json={"messages": items},
                timeout=self.config.timeout * 2,
            )
            if resp.status_code == 404:
                raise requests.HTTPError(response=resp)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", []):
                ref = int(item.get("ref", 0))
                if ref:
                    results[ref] = SendResult(
                        success=item.get("status", "").lower() in ("ok", "success", "sent"),
                        message_id=str(item.get("message_id") or item.get("id") or ""),
                        error=item.get("error"),
                    )
            # Fill missing with success (if platform doesn't return per-item)
            for msg in messages:
                if msg["ID"] not in results:
                    results[msg["ID"]] = SendResult(success=True)
            return results

        except (requests.HTTPError, requests.ConnectionError, ValueError):
            logger.info("Batch endpoint unavailable – falling back to individual sends")

        # Fallback: send one by one
        for msg in messages:
            msg_type = (msg.get("TYPE") or "SMS").upper()
            if msg_type == "VIBER":
                res = self.send_viber(msg["PHONE"], msg["MESSAGE"])
            else:
                res = self.send_sms(msg["PHONE"], msg["MESSAGE"])
            results[msg["ID"]] = res
            time.sleep(0.05)  # gentle rate limit

        return results

    # ── Delivery status check ──────────────────────────────────────────────

    def check_delivery_status(self, platform_id: str) -> Optional[str]:
        try:
            resp = self.session.get(
                f"{self.config.base_url}/status/{platform_id}",
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("status")
        except Exception as exc:
            logger.debug(f"check_delivery_status error: {exc}")
            return None

    # ── Connectivity test ──────────────────────────────────────────────────

    def test_connection(self) -> Tuple[bool, str]:
        for endpoint in ("/ping", "/health", "/balance"):
            try:
                resp = self.session.get(
                    f"{self.config.base_url}{endpoint}",
                    timeout=10,
                )
                if resp.status_code < 500:
                    return True, f"API προσβάσιμο ({resp.status_code}) ✓"
            except requests.ConnectionError:
                return False, f"Αδυναμία σύνδεσης στο {self.config.base_url}"
            except Exception:
                continue
        return False, "Δεν ανταποκρίθηκε κανένα endpoint"


# ── Platform adapters ──────────────────────────────────────────────────────

class ApifonClient(SMSViberClient):
    """Apifon platform adapter – https://apifon.com/developers"""

    def _set_auth(self, session: requests.Session):
        # Apifon uses Basic auth with token
        session.headers["Authorization"] = f"Token {self.config.api_key}"

    def send_sms(self, phone: str, message: str) -> SendResult:
        payload = {
            "to": [{"msisdn": phone}],
            "message": {"text": message, "from": self.config.sender_sms},
            "callback_url": self.config.webhook_url or None,
        }
        try:
            resp = self.session.post(
                f"{self.config.base_url}/messages",
                json=payload,
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return SendResult(success=True, message_id=str(data.get("id", "")))
        except Exception as exc:
            return SendResult(success=False, error=str(exc))


class YubotoClient(SMSViberClient):
    """Yuboto platform adapter – https://yuboto.com"""

    def _set_auth(self, session: requests.Session):
        session.headers["ApiKey"] = self.config.api_key

    def send_sms(self, phone: str, message: str) -> SendResult:
        payload = {
            "username": self.config.api_key,
            "password": self.config.api_secret,
            "from": self.config.sender_sms,
            "to": phone,
            "message": message,
        }
        try:
            resp = self.session.post(
                f"{self.config.base_url}/api/sms/send",
                json=payload,
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return SendResult(
                success=data.get("StatusCode") == 200,
                message_id=str(data.get("MessageId", "")),
                error=data.get("Description") if data.get("StatusCode") != 200 else None,
            )
        except Exception as exc:
            return SendResult(success=False, error=str(exc))


# ── Factory ────────────────────────────────────────────────────────────────

def create_client(config: APIConfig) -> SMSViberClient:
    """Return the correct client based on config.platform."""
    platform_map = {
        "apifon": ApifonClient,
        "yuboto": YubotoClient,
    }
    cls = platform_map.get(config.platform.lower(), SMSViberClient)
    logger.info(f"Using API client: {cls.__name__} → {config.base_url}")
    return cls(config)
