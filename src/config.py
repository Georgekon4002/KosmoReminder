"""
KosmoSMS — Central Configuration

Loads all settings from a .env file (or environment variables).
Usage:
    from config import cfg
    print(cfg.EASYSMS_API_KEY)
"""

import os
from dotenv import load_dotenv

# Load .env from the src/ directory (or parent if running from project root)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_env_path)


class _Config:
    """Read-only configuration container. All values come from environment."""

    # --- Database ---
    @property
    def DB_CONNECTION_STRING(self) -> str:
        return os.environ.get(
            "DB_CONNECTION_STRING",
            "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=KosmoSMS;Trusted_Connection=yes;",
        )

    # --- easysms.gr API ---
    @property
    def EASYSMS_API_KEY(self) -> str:
        return os.environ.get("EASYSMS_API_KEY", "")

    @property
    def EASYSMS_BASE_URL(self) -> str:
        return os.environ.get("EASYSMS_BASE_URL", "https://easysms.gr/api").rstrip("/")

    @property
    def VIBER_SENDER_ID(self) -> str:
        return os.environ.get("VIBER_SENDER_ID", "Kosmoiatriki")

    @property
    def SMS_SENDER_ID(self) -> str:
        return os.environ.get("SMS_SENDER_ID", "Kosmoiatriki")

    @property
    def CALLBACK_URL(self) -> str:
        return os.environ.get("CALLBACK_URL", "")

    # --- Reminder settings ---
    @property
    def LEAD_TIME_HOURS(self) -> int:
        return int(os.environ.get("LEAD_TIME_HOURS", "24"))

    @property
    def INTERVAL_MINUTES(self) -> int:
        return int(os.environ.get("INTERVAL_MINUTES", "15"))

    @property
    def MESSAGE_TEMPLATE(self) -> str:
        return os.environ.get(
            "MESSAGE_TEMPLATE",
            "Αγαπητέ/ή {PatientName}, σας υπενθυμίζουμε το ραντεβού σας στις "
            "{DateTime} για {ExamType} στο {LabName}. "
            "Για αλλαγή ή ακύρωση, καλέστε μας. "
            "Τοποθεσία: {MapsLink}",
        )

    # --- Callback Receiver (Flask) ---
    @property
    def CALLBACK_HOST(self) -> str:
        return os.environ.get("CALLBACK_HOST", "0.0.0.0")

    @property
    def CALLBACK_PORT(self) -> int:
        return int(os.environ.get("CALLBACK_PORT", "5000"))


# Singleton — import this everywhere
cfg = _Config()
