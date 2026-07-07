"""
KosmoSMS — Email Reminder Service

Background script that periodically checks for newly synced appointments
and sends a one-time email with a calendar invite (.ics).
"""

import logging
import sys
import time
import smtplib
from email.message import EmailMessage
from email.utils import formatdate
import uuid

import database
import calendar_invite
from config import cfg

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
import os
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

def send_email(appointment: dict) -> bool:
    """Send calendar invite email. Returns True on success, False on failure."""
    patient_email = appointment.get("Email")
    if not patient_email:
        return False
        
    try:
        # Build message
        msg = EmailMessage()
        
        # Format Subject
        appt_dt = appointment.get("AppointmentDateTime")
        dt_str = appt_dt.strftime("%d/%m/%Y %H:%M") if appt_dt else ""
        subject = cfg.EMAIL_CONFIRMATION_SUBJECT_TEMPLATE.replace("{DateTime}", dt_str)
        
        msg['Subject'] = subject
        msg['From'] = f"{cfg.EMAIL_FROM_NAME} <{cfg.EMAIL_FROM_ADDRESS}>"
        msg['To'] = patient_email
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = f"<{uuid.uuid4()}@{cfg.EMAIL_FROM_ADDRESS.split('@')[-1] if '@' in cfg.EMAIL_FROM_ADDRESS else 'kosmoiatriki.gr'}>"

        department = appointment.get("Department") or "Τμήμα"
        lab_name = appointment.get("LabName") or "το εργαστήριο μας"
        
        body_text = f"Γεια σας,\n\nΣας επιβεβαιώνουμε το ραντεβού σας στο {department} της Μονάδας {lab_name} για τις {dt_str}.\n\nΜπορείτε να προσθέσετε το ραντεβού στο ημερολόγιό σας ανοίγοντας το συνημμένο αρχείο."
        msg.set_content(body_text)

        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 40px 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); overflow: hidden; }}
                .header {{ background-color: #ffffff; padding: 30px; text-align: center; border-bottom: 1px solid #eaeaea; }}
                .content {{ padding: 40px 30px; text-align: center; }}
                .title {{ color: #1a1a1a; font-size: 24px; font-weight: 600; margin: 0 0 10px 0; }}
                .subtitle {{ color: #666666; font-size: 16px; margin: 0 0 30px 0; }}
                .card {{ background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 25px; margin-bottom: 30px; text-align: left; }}
                .footer {{ background-color: #f8fafc; padding: 20px; text-align: center; color: #94a3b8; font-size: 13px; border-top: 1px solid #eaeaea; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 style="color: #2563eb; margin: 0; font-size: 28px; letter-spacing: -0.5px;">Kosmoiatriki</h2>
                </div>
                <div class="content">
                    <h1 class="title">Επιβεβαίωση Ραντεβού</h1>
                    <p class="subtitle">Το ραντεβού σας καταχωρήθηκε με επιτυχία.</p>
                    
                    <div class="card">
                        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse;">
                            <tr>
                                <td style="padding-bottom: 15px; color: #64748b; font-size: 14px; width: 40%; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">Ημερομηνία & Ωρα</td>
                                <td style="padding-bottom: 15px; color: #0f172a; font-size: 15px; font-weight: 600;">{dt_str}</td>
                            </tr>
                            <tr>
                                <td style="padding-bottom: 15px; color: #64748b; font-size: 14px; width: 40%; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">Τμήμα</td>
                                <td style="padding-bottom: 15px; color: #0f172a; font-size: 15px; font-weight: 600;">{department}</td>
                            </tr>
                            <tr>
                                <td style="color: #64748b; font-size: 14px; width: 40%; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">Μονάδα</td>
                                <td style="color: #0f172a; font-size: 15px; font-weight: 600;">{lab_name}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <p style="color: #475569; font-size: 15px; margin-bottom: 25px; line-height: 1.5;">
                        Βρείτε επισυναπτόμενο το αρχείο <strong>invite.ics</strong> για να προσθέσετε το ραντεβού στο προσωπικό σας ημερολόγιο (Google Calendar, Outlook, Apple Calendar).
                    </p>
                </div>
                <div class="footer">
                    &copy; {appt_dt.year if appt_dt else '2026'} Kosmoiatriki. Όλα τα δικαιώματα διατηρούνται.
                </div>
            </div>
        </body>
        </html>
        """
        msg.add_alternative(body_html, subtype='html')
        
        # Attach .ics
        ics_data = calendar_invite.build_ics(appointment)
        
        # Add as alternative for email clients that render requests
        msg.add_alternative(ics_data.decode('utf-8'), subtype='calendar', params={'method': 'REQUEST'})
        
        # Also add as an attachment for older clients
        msg.add_attachment(ics_data, maintype='text', subtype='calendar', filename='invite.ics')
        
        # Send
        if cfg.SMTP_USE_TLS:
            with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as server:
                server.starttls()
                server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as server:
                server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
                server.send_message(msg)
                
        return True
    except Exception:
        logger.exception("Failed to send email to %s for appointment %s", patient_email, appointment.get("AppointmentID"))
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
    logger.info("EmailReminderService started. Interval=5min")
    
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
