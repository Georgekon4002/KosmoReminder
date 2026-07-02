"""
ServiceRunner – background daemon for automatic message processing.

Works in three deployment modes:
  1. Direct: python main.py --mode service
  2. Windows Service: via windows_service.py
  3. Linux systemd: via sms_sender.service unit file

Optionally exposes a Flask webhook endpoint for platform delivery callbacks.
"""
import logging
import signal
import threading
import time
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import AppConfig
from .database import DatabaseManager
from .processor import MessageProcessor

logger = logging.getLogger(__name__)


class ServiceRunner:
    """
    Wraps MessageProcessor with a scheduler and optional webhook server.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.db = DatabaseManager(config.database)
        self.scheduler = BackgroundScheduler(
            job_defaults={"coalesce": True, "max_instances": 1}
        )
        self._running = False
        self._lock = threading.Lock()
        self._webhook_thread: threading.Thread | None = None

    # ── Service lifecycle ──────────────────────────────────────────────────

    def start(self):
        logger.info("=== SMS/Viber Sender Service STARTING ===")

        # Reset any stuck "ΣΕ ΑΠΟΣΤΟΛΗ" records from previous crash
        self.db.reset_sending_to_pending()

        if self.config.service.auto_process:
            interval = self.config.service.check_interval_seconds
            self.scheduler.add_job(
                self._run_cycle,
                trigger=IntervalTrigger(seconds=interval),
                id="send_job",
                next_run_time=datetime.now(),
            )
            logger.info(f"Scheduler active – checking every {interval}s")
        else:
            logger.info("Auto-process disabled – waiting for manual trigger via webhook")

        # Optional webhook server
        if self.config.api.webhook_url:
            self._start_webhook_server()

        self.scheduler.start()
        self._running = True

        # Graceful shutdown on SIGTERM/SIGINT
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        logger.info("Service ready.")

        # Keep main thread alive
        try:
            while self._running:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self.stop()

    def stop(self):
        logger.info("Service STOPPING…")
        self._running = False
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("Service stopped.")

    def _handle_signal(self, signum, frame):
        logger.info(f"Received signal {signum} – shutting down")
        self._running = False

    # ── Processing cycle ───────────────────────────────────────────────────

    def _run_cycle(self):
        """Called by scheduler on each tick."""
        with self._lock:
            logger.info(f"⏰ Processing cycle @ {datetime.now():%Y-%m-%d %H:%M:%S}")
            try:
                proc = MessageProcessor(self.config)
                sent, errors = proc.process_pending()
                logger.info(f"Cycle done – sent={sent} errors={errors}")
            except Exception as exc:
                logger.exception(f"Processing cycle error: {exc}")

    def trigger_now(self):
        """Manually trigger a processing cycle (e.g., from webhook)."""
        threading.Thread(target=self._run_cycle, daemon=True).start()

    # ── Webhook server (optional) ──────────────────────────────────────────

    def _start_webhook_server(self):
        """
        Start a lightweight Flask server to:
          - Receive delivery callbacks from the SMS/Viber platform
          - Manually trigger a send cycle via HTTP
        """
        try:
            from flask import Flask, request, jsonify
            app = Flask("SMSWebhook")

            @app.route("/health", methods=["GET"])
            def health():
                stats = self.db.get_statistics()
                return jsonify({"status": "ok", "stats": stats})

            @app.route("/trigger", methods=["POST"])
            def trigger():
                """Manually trigger processing – useful for IIS / cron."""
                self.trigger_now()
                return jsonify({"queued": True})

            @app.route("/callback", methods=["POST"])
            def callback():
                """
                Receive delivery status callbacks from the SMS platform.
                Expected JSON: {"message_id": "xxx", "status": "delivered"}
                """
                data = request.get_json(silent=True) or {}
                platform_id = data.get("message_id") or data.get("id")
                status_raw = (data.get("status") or "").lower()

                if platform_id and status_raw in ("delivered", "sent", "success"):
                    logger.info(f"Callback: {platform_id} → {status_raw}")
                    # Additional status reconciliation can be done here
                return jsonify({"ack": True})

            def _run():
                try:
                    from waitress import serve
                    host, port = "0.0.0.0", 5050
                    logger.info(f"Webhook server listening on {host}:{port}")
                    serve(app, host=host, port=port)
                except ImportError:
                    logger.warning(
                        "waitress not installed – using Flask dev server (not for production)"
                    )
                    app.run(host="0.0.0.0", port=5050)

            self._webhook_thread = threading.Thread(
                target=_run, daemon=True, name="WebhookServer"
            )
            self._webhook_thread.start()

        except ImportError:
            logger.warning("Flask not installed – webhook server disabled")
        except Exception as exc:
            logger.error(f"Failed to start webhook server: {exc}")
