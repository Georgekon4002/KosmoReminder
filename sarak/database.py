"""
MSSQL Database Manager.
Handles all read/write operations for the message queue table.
"""
import pyodbc
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .config import DatabaseConfig

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Status constants (Greek values as stored in DB)
# ──────────────────────────────────────────────
STATUS_PENDING   = "ΠΡΟΣ ΑΠΟΣΤΟΛΗ"
STATUS_SENDING   = "ΣΕ ΑΠΟΣΤΟΛΗ"
STATUS_SENT      = "ΑΠΕΣΤΑΛΛΕΙ"
STATUS_ERROR     = "ΣΦΑΛΜΑ"

ALL_STATUSES = [STATUS_PENDING, STATUS_SENDING, STATUS_SENT, STATUS_ERROR]


class DatabaseManager:
    """Thread-safe (via new connection per call) MSSQL manager."""

    def __init__(self, config: DatabaseConfig):
        self.config = config

    # ── Connection helpers ─────────────────────────────────────────────────

    def _connect(self) -> pyodbc.Connection:
        """Open and return a fresh connection (caller must close)."""
        conn_str = self.config.get_connection_string()
        conn = pyodbc.connect(conn_str, autocommit=False)
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
        conn.setencoding(encoding="utf-8")
        return conn

    def test_connection(self) -> Tuple[bool, str]:
        """Quick connectivity test – does not keep the connection open."""
        try:
            with self._connect() as conn:
                conn.cursor().execute("SELECT 1")
            return True, "Η σύνδεση με τη βάση δεδομένων ήταν επιτυχής ✓"
        except pyodbc.Error as exc:
            return False, f"Σφάλμα σύνδεσης: {exc}"
        except Exception as exc:
            return False, str(exc)

    # ── Table columns shortcut ─────────────────────────────────────────────

    @property
    def c(self):
        """Shortcut to column name config."""
        return self.config

    # ── Read operations ────────────────────────────────────────────────────

    def get_messages(
        self,
        status: Optional[str] = None,
        limit: int = 2000,
        filter_text: str = "",
    ) -> List[Dict[str, Any]]:
        """Fetch messages, optionally filtered by status and/or text."""
        table = self.config.table_name
        c = self.c
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                where_parts = []
                params: List[Any] = []

                if status:
                    where_parts.append(f"{c.col_status} = ?")
                    params.append(status)

                if filter_text:
                    search = f"%{filter_text}%"
                    where_parts.append(
                        f"({c.col_recipient} LIKE ? OR {c.col_phone} LIKE ? "
                        f"OR {c.col_message} LIKE ? OR {c.col_campaign} LIKE ?)"
                    )
                    params.extend([search, search, search, search])

                where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

                query = (
                    f"SELECT TOP {limit} "
                    f"{c.col_id}, {c.col_recipient}, {c.col_phone}, "
                    f"{c.col_message}, {c.col_type}, {c.col_status}, "
                    f"{c.col_campaign}, {c.col_scheduled}, {c.col_sent}, "
                    f"{c.col_platform_id}, {c.col_error}, {c.col_created}, {c.col_updated} "
                    f"FROM {table} {where_clause} "
                    f"ORDER BY {c.col_created} DESC"
                )
                cursor.execute(query, params)
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as exc:
            logger.error(f"get_messages error: {exc}")
            return []

    def get_pending_messages(self, limit: int = 2000) -> List[Dict[str, Any]]:
        return self.get_messages(status=STATUS_PENDING, limit=limit)

    def get_statistics(self) -> Dict[str, int]:
        """Return counts grouped by status."""
        table = self.config.table_name
        c = self.c
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT {c.col_status}, COUNT(*) FROM {table} GROUP BY {c.col_status}"
                )
                return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as exc:
            logger.error(f"get_statistics error: {exc}")
            return {}

    def get_total_count(self) -> int:
        table = self.config.table_name
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                return cursor.fetchone()[0]
        except Exception as exc:
            logger.error(f"get_total_count error: {exc}")
            return 0

    # ── Write operations ───────────────────────────────────────────────────

    def update_message_status(
        self,
        message_id: int,
        status: str,
        platform_id: Optional[str] = None,
        error_msg: Optional[str] = None,
    ) -> bool:
        table = self.config.table_name
        c = self.c
        sent_at = datetime.now() if status == STATUS_SENT else None
        try:
            with self._connect() as conn:
                conn.cursor().execute(
                    f"UPDATE {table} SET "
                    f"  {c.col_status}=?, {c.col_sent}=?, "
                    f"  {c.col_platform_id}=?, {c.col_error}=?, "
                    f"  {c.col_updated}=GETDATE() "
                    f"WHERE {c.col_id}=?",
                    status, sent_at, platform_id, error_msg, message_id,
                )
                conn.commit()
            return True
        except Exception as exc:
            logger.error(f"update_message_status({message_id}) error: {exc}")
            return False

    def bulk_update_status(
        self,
        message_ids: List[int],
        status: str,
        results: Optional[Dict[int, Dict]] = None,
    ) -> bool:
        """Update multiple messages in a single transaction."""
        if not message_ids:
            return True
        table = self.config.table_name
        c = self.c
        sent_at = datetime.now() if status == STATUS_SENT else None
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                for mid in message_ids:
                    res = (results or {}).get(mid, {})
                    cursor.execute(
                        f"UPDATE {table} SET "
                        f"  {c.col_status}=?, {c.col_sent}=?, "
                        f"  {c.col_platform_id}=?, {c.col_error}=?, "
                        f"  {c.col_updated}=GETDATE() "
                        f"WHERE {c.col_id}=?",
                        status, sent_at,
                        res.get("platform_id"),
                        res.get("error_msg"),
                        mid,
                    )
                conn.commit()
            return True
        except Exception as exc:
            logger.error(f"bulk_update_status error: {exc}")
            return False

    def reset_sending_to_pending(self) -> int:
        """On startup, reset any 'ΣΕ ΑΠΟΣΤΟΛΗ' stuck records back to pending."""
        table = self.config.table_name
        c = self.c
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"UPDATE {table} SET {c.col_status}=? "
                    f"WHERE {c.col_status}=?",
                    STATUS_PENDING, STATUS_SENDING,
                )
                count = cursor.rowcount
                conn.commit()
            if count:
                logger.warning(f"Reset {count} stuck SENDING records → PENDING")
            return count
        except Exception as exc:
            logger.error(f"reset_sending_to_pending error: {exc}")
            return 0
