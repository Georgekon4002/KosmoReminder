"""
Configuration management for SMS/Viber Sender.
Supports JSON config file with dataclass-based settings.
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_FILE = Path("config.json")


@dataclass
class DatabaseConfig:
    server: str = "localhost\\SQLEXPRESS"
    port: int = 1433
    database: str = "MyDatabase"
    username: str = "sa"
    password: str = ""
    driver: str = "ODBC Driver 17 for SQL Server"
    table_name: str = "MESSAGE_QUEUE"
    trusted_connection: bool = False
    connection_timeout: int = 30
    # Column name mapping (adapt to existing tables)
    col_id: str = "ID"
    col_recipient: str = "RECIPIENT_NAME"
    col_phone: str = "PHONE"
    col_message: str = "MESSAGE"
    col_type: str = "TYPE"
    col_status: str = "STATUS"
    col_campaign: str = "CAMPAIGN"
    col_scheduled: str = "SCHEDULED_AT"
    col_sent: str = "SENT_AT"
    col_platform_id: str = "PLATFORM_ID"
    col_error: str = "ERROR_MSG"
    col_created: str = "CREATED_AT"
    col_updated: str = "UPDATED_AT"

    def get_connection_string(self) -> str:
        server_str = f"{self.server},{self.port}" if self.port != 1433 else self.server
        if self.trusted_connection:
            return (
                f"DRIVER={{{self.driver}}};"
                f"SERVER={server_str};"
                f"DATABASE={self.database};"
                "Trusted_Connection=yes;"
                f"Connection Timeout={self.connection_timeout};"
            )
        return (
            f"DRIVER={{{self.driver}}};"
            f"SERVER={server_str};"
            f"DATABASE={self.database};"
            f"UID={self.username};"
            f"PWD={self.password};"
            f"Connection Timeout={self.connection_timeout};"
        )


@dataclass
class APIConfig:
    # Platform: "generic", "apifon", "yuboto"
    platform: str = "generic"
    base_url: str = "https://api.example.com/v1"
    api_key: str = ""
    api_secret: str = ""

    # Sender IDs
    sender_sms: str = "SENDER"
    sender_viber: str = "SENDER"

    # Request settings
    timeout: int = 30
    retry_count: int = 3
    retry_delay_seconds: int = 5
    batch_size: int = 50

    # Webhook / callback URL (optional)
    webhook_url: str = ""


@dataclass
class ServiceConfig:
    auto_process: bool = False
    check_interval_seconds: int = 60
    max_messages_per_run: int = 1000
    service_name: str = "SMSViberSender"
    service_display_name: str = "SMS/Viber Sender Service"
    service_description: str = "Αυτόματη αποστολή SMS και Viber μηνυμάτων"
    log_level: str = "INFO"
    log_file: str = "logs/app.log"
    max_log_size_mb: int = 10
    log_backup_count: int = 5


@dataclass
class AppConfig:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: APIConfig = field(default_factory=APIConfig)
    service: ServiceConfig = field(default_factory=ServiceConfig)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        config = cls()
        if "database" in data:
            db_data = {
                k: v for k, v in data["database"].items()
                if k in DatabaseConfig.__dataclass_fields__
            }
            config.database = DatabaseConfig(**db_data)
        if "api" in data:
            api_data = {
                k: v for k, v in data["api"].items()
                if k in APIConfig.__dataclass_fields__
            }
            config.api = APIConfig(**api_data)
        if "service" in data:
            svc_data = {
                k: v for k, v in data["service"].items()
                if k in ServiceConfig.__dataclass_fields__
            }
            config.service = ServiceConfig(**svc_data)
        return config

    def save(self, path: Path = CONFIG_FILE) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Configuration saved → {path}")
            return True
        except Exception as exc:
            logger.error(f"Failed to save config: {exc}")
            return False

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "AppConfig":
        if not path.exists():
            logger.info("Config file not found – using defaults")
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = cls.from_dict(data)
            logger.info(f"Configuration loaded ← {path}")
            return cfg
        except Exception as exc:
            logger.error(f"Failed to load config ({exc}) – using defaults")
            return cls()
