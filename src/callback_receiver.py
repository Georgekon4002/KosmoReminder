"""
KosmoSMS — Callback Receiver (Flask)

Small web server that receives delivery status callbacks from easysms.gr.

easysms.gr calls this endpoint in real time when a message is delivered or
fails. It sends the following query string parameters:
  - msgid:  unique message identifier
  - status: delivery status (delivered, failed, rejected, expired)
  - cost:   message cost
  - to:     recipient number
  - mcc:    mobile country code
  - mnc:    mobile network code

Usage:
  python callback_receiver.py
  # or: flask --app callback_receiver run --host 0.0.0.0 --port 5000
"""

import logging
import os
import sys
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, request

import database
from config import cfg

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/callback-receiver.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("callback_receiver")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    """Simple health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route("/api/sms-callback", methods=["GET", "POST"])
def sms_callback():
    """
    Webhook endpoint for delivery status callbacks from easysms.gr.

    Accepts both GET and POST — easysms.gr may use either.
    Parameters come via query string.
    """
    # --- 1. Read parameters ---
    msgid = request.args.get("msgid")
    status = request.args.get("status")
    cost_str = request.args.get("cost")
    to = request.args.get("to")
    mcc = request.args.get("mcc")
    mnc = request.args.get("mnc")

    logger.info(
        "Callback received [%s]: msgid=%s, status=%s, cost=%s, to=%s, mcc=%s, mnc=%s",
        request.method, msgid, status, cost_str, to, mcc, mnc,
    )

    # --- 2. Validate required parameters ---
    if not msgid or not status:
        logger.warning("Invalid callback: missing required parameters (msgid or status)")
        return jsonify({"error": "Missing required parameters: msgid and status are required."}), 400

    # --- 3. Check if we have a pending notification ---
    try:
        exists = database.notification_exists_pending(msgid)

        if not exists:
            logger.warning(
                "No pending notification found for msgid=%s. Possibly already processed.",
                msgid,
            )
            # Return 200 anyway to prevent easysms.gr from retrying
            return jsonify({"status": "ignored", "reason": "No pending notification found for this msgid."}), 200

        # --- 4. Parse cost ---
        cost = None
        if cost_str:
            try:
                cost = Decimal(cost_str)
            except InvalidOperation:
                logger.warning("Could not parse cost value: %s", cost_str)

        # --- 5. Update the notification record ---
        updated = database.update_delivery_status(msgid, status, cost, mcc, mnc)

        if updated:
            logger.info("Successfully processed callback for msgid=%s", msgid)
            return jsonify({"status": "ok", "msgid": msgid}), 200
        else:
            logger.warning("Notification msgid=%s was already updated (race condition)", msgid)
            return jsonify({"status": "already_processed", "msgid": msgid}), 200

    except Exception:
        logger.exception("Error processing callback for msgid=%s", msgid)
        return jsonify({"error": "Internal server error processing callback."}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info(
        "CallbackReceiver starting on %s:%d", cfg.CALLBACK_HOST, cfg.CALLBACK_PORT,
    )
    app.run(host=cfg.CALLBACK_HOST, port=cfg.CALLBACK_PORT, debug=False)
