"""
KosmoSMS — Email Reminder Service

Background script that periodically checks for newly synced appointments
and sends a one-time email with a calendar invite (.ics).

Sends via SMTP (standard library smtplib) — no third-party email SDK required.
"""

import logging
import os
import smtplib
import sys
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import database
import calendar_invite
from config import cfg
from reminder_service import build_greeting

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/email-reminder-service.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("email_reminder_service")

months_gr = ["", "Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου", "Ιουλίου", "Αυγούστου", "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου"]
days_gr = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]


def _build_smtp_message(appointment: dict) -> tuple[MIMEMultipart, str] | tuple[None, None]:
    """
    Build a MIMEMultipart email message for the given appointment.

    Returns (msg, recipient_address) or (None, None) if no email on file.
    """
    patient_email = appointment.get("Email")
    if not patient_email:
        return None, None

    try:
        appt_dt = appointment.get("AppointmentDateTime")
        if appt_dt:
            day_name = days_gr[appt_dt.weekday()]
            month_name = months_gr[appt_dt.month]
            dt_str = f"{day_name}, {appt_dt.day} {month_name} {appt_dt.year}, {appt_dt.strftime('%H:%M')}"
            subject_dt_str = appt_dt.strftime("%d/%m/%Y %H:%M")
        else:
            dt_str = ""
            subject_dt_str = ""

        department = appointment.get("Department") or "Τμήμα"
        subject = (
            cfg.EMAIL_CONFIRMATION_SUBJECT_TEMPLATE
            .replace("{DateTime}", subject_dt_str)
            .replace("{Department}", department)
        )

        lab_name = appointment.get("LabName") or "το εργαστήριο μας"

        first_name = appointment.get("PatientFirstName", "")
        last_name  = appointment.get("PatientLastName", "")
        sex        = appointment.get("Sex")
        greeting   = build_greeting(first_name, last_name, sex)

        lab_address_db = appointment.get("LabAddress") or "Αθήνα"

        # Build map link and address
        if "Κυψέλη" in lab_name:
            directions_url = "https://maps.app.goo.gl/9QZJ2qH9n9w3XQ9E8"
            lab_address = lab_address_db if lab_address_db != "Αθήνα" else "Πατησίων 237, Κυψέλη 112 54"
        elif "Πατήσια" in lab_name:
            directions_url = "https://maps.app.goo.gl/3XQ9E89QZJ2qH9n9w"
            lab_address = lab_address_db if lab_address_db != "Αθήνα" else "Λεωφ. Γαλατσίου 13, Πατήσια 111 41"
        elif "Περιστέρι" in lab_name:
            directions_url = "https://maps.app.goo.gl/9w3XQ9E89QZJ2qH9n"
            lab_address = lab_address_db if lab_address_db != "Αθήνα" else "Θηβών 153, Περιστέρι 121 34"
        else:
            import urllib.parse
            directions_url = f"https://maps.google.com/?q={urllib.parse.quote(lab_address_db)}"
            lab_address = lab_address_db

        # Build calendar link
        import urllib.parse
        gcal_title = urllib.parse.quote(f"Ραντεβού στην Κοσμοϊατρική ({department})")
        if appt_dt:
            from datetime import timedelta
            gcal_start = appt_dt.strftime("%Y%m%dT%H%M%S")
            gcal_end = (appt_dt + timedelta(minutes=30)).strftime("%Y%m%dT%H%M%S")
            calendar_url = (
                f"https://calendar.google.com/calendar/render?action=TEMPLATE"
                f"&text={gcal_title}&dates={gcal_start}/{gcal_end}"
                f"&details=&location={urllib.parse.quote(lab_name)}"
            )
        else:
            calendar_url = "#"

        # Load and fill HTML template
        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "templates", "mail.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            body_html = f.read()

        body_html = body_html.replace("{{{greeting}}}", greeting)
        body_html = body_html.replace("{{{exam_type}}}", department)
        body_html = body_html.replace("{{{datetime}}}", dt_str)
        body_html = body_html.replace("{{{lab_name}}}", lab_name)
        body_html = body_html.replace("{{{lab_address}}}", lab_address)
        body_html = body_html.replace("{{{directions_url}}}", directions_url)
        body_html = body_html.replace("{{{calendar_url}}}", calendar_url)

        # Build .ics attachment
        ics_data: bytes = calendar_invite.build_ics(appointment)

        # Assemble MIME message
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"{cfg.EMAIL_FROM_NAME} <{cfg.EMAIL_FROM_ADDRESS}>"
        msg["To"] = patient_email

        # HTML body
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        # .ics attachment
        ics_part = MIMEBase("text", "calendar", method="REQUEST", name="invite.ics")
        ics_part.set_payload(ics_data)
        encoders.encode_base64(ics_part)
        ics_part.add_header("Content-Disposition", "attachment", filename="invite.ics")
        msg.attach(ics_part)

        return msg, patient_email

    except Exception:
        logger.exception(
            "Failed to build email message for appointment %s",
            appointment.get("AppointmentID"),
        )
        return None, None


def send_email(appointment: dict) -> bool:
    """Send calendar invite email via SMTP. Returns True on success, False on failure."""
    msg, recipient = _build_smtp_message(appointment)
    if msg is None:
        return False

    try:
        if cfg.SMTP_USE_TLS:
            smtp = smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=30)
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
        else:
            smtp = smtplib.SMTP_SSL(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=30)

        if cfg.SMTP_USER and cfg.SMTP_PASSWORD:
            smtp.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)

        smtp.sendmail(cfg.EMAIL_FROM_ADDRESS, recipient, msg.as_string())
        smtp.quit()

        logger.info(
            "Email sent via SMTP to %s for appointment %s",
            recipient,
            appointment.get("AppointmentID"),
        )
        return True

    except Exception:
        logger.exception(
            "Failed to send email to %s for appointment %s",
            recipient,
            appointment.get("AppointmentID"),
        )
        return False


def process_emails() -> None:
    """Find newly synced appointments without email sent, and send them."""
    try:
        appointments = database.get_unsent_emails()
    except Exception:
        logger.exception("Failed to query unsent emails")
        return

    if not appointments:
        logger.debug("No unsent emails.")
        return

    logger.info("Processing %d email reminders", len(appointments))

    for appt in appointments:
        appt_id = appt.get("AppointmentID")
        email = appt.get("Email")

        if not email or not str(email).strip():
            logger.info("Appointment %d: no email on file", appt_id)
            database.update_email_status(appt_id, "no_email")
            continue

        logger.info("Sending email for appointment %d to %s", appt_id, email)
        success = send_email(appt)

        if success:
            logger.info("Email sent successfully for appointment %d", appt_id)
            database.update_email_status(appt_id, "sent")
        else:
            logger.error("Email failed for appointment %d", appt_id)
            database.update_email_status(appt_id, "failed")


def main() -> None:
    logger.info("EmailReminderService started (SMTP). Interval=5min")

    interval_minutes = 5

    while True:
        try:
            process_emails()
        except Exception:
            logger.exception("Unhandled error in email processing loop")

        logger.debug("Sleeping for %d minutes...", interval_minutes)
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    main()
