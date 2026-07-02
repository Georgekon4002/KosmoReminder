"""
MessageProcessor – orchestrates:
  1. Read pending messages from DB
  2. Send via API (in batches)
  3. Update DB status (ΑΠΕΣΤΑΛΛΕΙ / ΣΦΑΛΜΑ)

Designed to be used both from GUI (via QThread) and from service mode.
"""
import logging
import time
from typing import Callable, Dict, List, Optional, Tuple

from .api_client import create_client
from .config import AppConfig
from .database import (
    DatabaseManager,
    STATUS_ERROR,
    STATUS_PENDING,
    STATUS_SENDING,
    STATUS_SENT,
)

logger = logging.getLogger(__name__)

ProgressCB = Optional[Callable[[int, int, str], None]]
LogCB = Optional[Callable[[str, str], None]]


class MessageProcessor:
    """
    Core processing engine. Stateless between runs.

    Usage (GUI thread):
        proc = MessageProcessor(config, progress_cb, log_cb)
        sent, errors = proc.process_pending()

    Usage (service):
        proc = MessageProcessor(config)
        proc.process_pending()
    """

    def __init__(
        self,
        config: AppConfig,
        progress_callback: ProgressCB = None,
        log_callback: LogCB = None,
    ):
        self.config = config
        self.db = DatabaseManager(config.database)
        self.api = create_client(config.api)
        self._progress_cb = progress_callback
        self._log_cb = log_callback
        self._stop = False

    # ── Callbacks ──────────────────────────────────────────────────────────

    def _log(self, msg: str, level: str = "INFO"):
        log_fn = getattr(logger, level.lower(), logger.info)
        log_fn(msg)
        if self._log_cb:
            try:
                self._log_cb(msg, level)
            except Exception:
                pass

    def _progress(self, current: int, total: int, note: str = ""):
        if self._progress_cb:
            try:
                self._progress_cb(current, total, note)
            except Exception:
                pass

    # ── Main entry point ───────────────────────────────────────────────────

    def process_pending(
        self, selected_ids: Optional[List[int]] = None
    ) -> Tuple[int, int]:
        """
        Process pending messages.

        Args:
            selected_ids: If given, only process those IDs.

        Returns:
            (sent_count, error_count)
        """
        self._stop = False

        # Fetch messages
        if selected_ids:
            all_msgs = self.db.get_messages(status=STATUS_PENDING, limit=5000)
            messages = [m for m in all_msgs if m[self.config.database.col_id] in selected_ids]
        else:
            messages = self.db.get_pending_messages(
                limit=self.config.service.max_messages_per_run
            )

        if not messages:
            self._log("Δεν βρέθηκαν μηνύματα προς αποστολή.", "INFO")
            return 0, 0

        total = len(messages)
        self._log(f"▶ Βρέθηκαν {total} μηνύματα προς αποστολή", "INFO")

        sent_count = 0
        error_count = 0
        batch_size = max(1, self.config.api.batch_size)

        for batch_start in range(0, total, batch_size):
            if self._stop:
                self._log("⏹ Η αποστολή διακόπηκε από τον χρήστη.", "WARNING")
                break

            batch = messages[batch_start: batch_start + batch_size]
            batch_ids = [m[self.config.database.col_id] for m in batch]
            batch_num = batch_start // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            self._log(
                f"📤 Batch {batch_num}/{total_batches} – {len(batch)} μηνύματα",
                "INFO",
            )
            self._progress(
                batch_start,
                total,
                f"Batch {batch_num}/{total_batches}",
            )

            # Mark as "sending" so a crash/restart doesn't double-send
            self.db.bulk_update_status(batch_ids, STATUS_SENDING)

            try:
                # Normalize keys for API client (use DB column names → standard keys)
                c = self.config.database
                api_messages = []
                for msg in batch:
                    api_messages.append({
                        "ID":      msg[c.col_id],
                        "PHONE":   msg[c.col_phone],
                        "MESSAGE": msg[c.col_message],
                        "TYPE":    msg.get(c.col_type) or "SMS",
                    })

                results = self.api.send_batch(api_messages)

                sent_ids: List[int] = []
                error_ids: List[int] = []
                result_meta: Dict[int, dict] = {}

                for msg in batch:
                    mid = msg[c.col_id]
                    res = results.get(mid)
                    if res and res.success:
                        sent_ids.append(mid)
                        result_meta[mid] = {"platform_id": res.message_id}
                        sent_count += 1
                    else:
                        error_ids.append(mid)
                        err = res.error if res else "Άγνωστο σφάλμα"
                        result_meta[mid] = {"error_msg": err}
                        error_count += 1
                        self._log(f"  ✗ ID={mid}: {err}", "WARNING")

                if sent_ids:
                    self.db.bulk_update_status(
                        sent_ids,
                        STATUS_SENT,
                        {k: v for k, v in result_meta.items() if k in sent_ids},
                    )
                if error_ids:
                    self.db.bulk_update_status(
                        error_ids,
                        STATUS_ERROR,
                        {k: v for k, v in result_meta.items() if k in error_ids},
                    )

                self._log(
                    f"  ✓ {len(sent_ids)} εστάλησαν  ✗ {len(error_ids)} σφάλματα",
                    "INFO" if not error_ids else "WARNING",
                )

            except Exception as exc:
                logger.exception(f"Batch {batch_num} failed: {exc}")
                self._log(f"  ✗ Batch {batch_num} απέτυχε: {exc}", "ERROR")
                self.db.bulk_update_status(
                    batch_ids,
                    STATUS_ERROR,
                    {bid: {"error_msg": str(exc)} for bid in batch_ids},
                )
                error_count += len(batch)

            time.sleep(0.3)  # brief pause between batches

        self._progress(total, total, "Ολοκλήρωση")
        self._log(
            f"✅ Αποστολή ολοκληρώθηκε: {sent_count} επιτυχή | {error_count} σφάλματα",
            "INFO",
        )
        return sent_count, error_count

    def stop(self):
        """Request graceful stop after current batch."""
        self._stop = True
