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

from flask import Flask, jsonify, request, render_template

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
app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates"
)


@app.route("/health", methods=["GET"])
def health():
    """Simple health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def index():
    """Serve the dashboard UI."""
    return render_template("index.html")


@app.route("/api/dashboard/stats", methods=["GET"])
def dashboard_stats():
    """Return dashboard summary statistics."""
    try:
        mode = request.args.get("mode", "all-time")
        # In the db, 'today' gets today's sent logic in get_dashboard_stats
        db_mode = 'today-sent' if mode == 'today' else 'all-time'
        stats = database.get_dashboard_stats(db_mode)
        
        pending_groups = database.get_pending_appointments(mode)
        stats["Pending"] = len(pending_groups)
        
        return jsonify(stats), 200
    except Exception:
        logger.exception("Error getting dashboard stats")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/dashboard/messages", methods=["GET"])
def dashboard_messages():
    """Return recent notifications for the dashboard."""
    from datetime import date, timedelta, datetime
    try:
        mode = request.args.get("mode", "all-time")
        week_offset = int(request.args.get("weekOffset", 0))
        
        # Calculate Monday to Sunday boundaries for the given weekOffset
        today = date.today()
        start_of_current_week = today - timedelta(days=today.weekday()) # Monday
        start_date_obj = start_of_current_week + timedelta(weeks=week_offset)
        end_date_obj = start_date_obj + timedelta(days=6) # Sunday
        
        start_date_str = start_date_obj.strftime("%Y-%m-%d")
        end_date_str = end_date_obj.strftime("%Y-%m-%d")
        
        messages = []
        if mode == 'today':
            db_mode = 'today-sent'
            pending_groups = database.get_pending_appointments(mode='today')
            notifs = database.get_all_notifications(mode=db_mode)
        else:
            db_mode = 'all-time'
            pending_groups = database.get_pending_appointments(start_date=start_date_str, end_date=end_date_str, mode='all-time')
            notifs = database.get_all_notifications(start_date=start_date_str, end_date=end_date_str, mode='all-time')
            
        for d in pending_groups:
            messages.append({
                "FirstName": d.get("PatientFirstName", ""),
                "LastName": d.get("PatientLastName", ""),
                "Department": d.get("Department", ""),
                "Phone": d.get("Phone", ""),
                "ExamType": d.get("ExamType", ""),
                "ChannelUsed": d.get("PreferredChannel") or "SMS",
                "Status": "Pending",
                "SentAt": None,
                "AppointmentDateTime": d.get("AppointmentDateTime").isoformat() if d.get("AppointmentDateTime") else None,
                "Cost": None,
                "EmailStatus": d.get("EmailStatus"),
                "EmailAddress": d.get("Email", ""),
                "AppointmentIDs": d.get("AppointmentIDs")
            })
            
        for n in notifs:
            n["AppointmentIDs"] = str(n.get("AppointmentID", ""))
            n["EmailAddress"] = n.get("Email", "")
        messages.extend(notifs)
        
        # Sort combined results by AppointmentDateTime ascending
        def get_dt(msg):
            dt = msg.get("AppointmentDateTime")
            if dt:
                # Remove Z or handle fractional seconds if any, but isoformat should be standard
                return datetime.fromisoformat(dt.replace('Z', '+00:00'))
            return datetime.max
            
        messages.sort(key=get_dt)
        
        return jsonify({
            "messages": messages,
            "pagination": {
                "weekOffset": week_offset,
                "startDate": start_date_str,
                "endDate": end_date_str
            }
        }), 200
    except Exception:
        logger.exception("Error getting dashboard messages")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/send-sms", methods=["POST"])
def send_sms():
    try:
        data = request.get_json()
        raw_ids = data.get("appointment_ids")
        if not raw_ids:
            return jsonify({"error": "Missing appointment_ids"}), 400
            
        import reminder_service
        appt_ids = [int(x) for x in str(raw_ids).split("|") if x.strip().isdigit()]
        group = database.get_appointment_group_by_ids(appt_ids)
        if group:
            reminder_service.send_reminder_for_group(group)
            return jsonify({"status": "ok"}), 200
        return jsonify({"error": "Group not found"}), 404
    except Exception:
        logger.exception("Error in send-sms")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/send-email", methods=["POST"])
def send_email():
    try:
        data = request.get_json()
        raw_ids = data.get("appointment_ids")
        if not raw_ids:
            return jsonify({"error": "Missing appointment_ids"}), 400
            
        import email_reminder_service
        # Get first ID if it's a pipe-separated list
        appt_id = int(str(raw_ids).split("|")[0])
        appt = database.get_appointment_for_email(appt_id)
        if appt:
            success = email_reminder_service.send_email(appt)
            if success:
                database.update_email_status(appt_id, "sent")
                return jsonify({"status": "ok"}), 200
            else:
                database.update_email_status(appt_id, "failed")
                return jsonify({"error": "Failed to send email"}), 500
        return jsonify({"error": "Appointment not found"}), 404
    except Exception:
        logger.exception("Error in send-email")
        return jsonify({"error": "Internal server error"}), 500


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
