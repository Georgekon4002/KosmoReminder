"""
KosmoSMS — Reminder Service

Background script that periodically checks for appointments due for a
reminder and sends Viber/SMS notifications via easysms.gr.

Flow for each appointment:
  1. Validate phone number via api/mobile/check
  2. Send Viber message with sms_fallback=true (easysms.gr handles fallback)
  3. If Viber send fails at API level, fall back to direct SMS send
  4. Log the notification result to the database

Usage:
  python reminder_service.py
"""

import logging
import sys
import time
from urllib.parse import quote

import database
import easysms_client
from config import cfg

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/reminder-service.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("reminder_service")


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

def build_message(appointment: dict) -> str:
    """
    Build the reminder message by replacing placeholders in the template.

    Placeholders: {PatientName}, {ExamType}, {DateTime}, {LabName}, {MapsLink}
    """
    patient_name = f"{appointment.get('PatientFirstName', '')} {appointment.get('PatientLastName', '')}".strip()

    # Format the date/time in Greek-friendly format: dd/MM/yyyy HH:mm
    appt_dt = appointment.get("AppointmentDateTime")
    if appt_dt is not None:
        formatted_dt = appt_dt.strftime("%d/%m/%Y %H:%M")
    else:
        formatted_dt = ""

    # Build a universal Google Maps link from the lab address
    lab_address = (appointment.get("LabAddress") or "").strip()
    if lab_address:
        maps_link = f"https://maps.google.com/?q={quote(lab_address)}"
    else:
        maps_link = ""

    message = cfg.MESSAGE_TEMPLATE
    message = message.replace("{PatientName}", patient_name)
    message = message.replace("{ExamType}", appointment.get("ExamType") or "εξέταση")
    message = message.replace("{DateTime}", formatted_dt)
    message = message.replace("{LabName}", appointment.get("LabName") or "το εργαστήριο")
    message = message.replace("{MapsLink}", maps_link)

    return message


# ---------------------------------------------------------------------------
# Reminder processing
# ---------------------------------------------------------------------------

def send_reminder_for_appointment(appointment: dict) -> None:
    """Process a single appointment: validate phone, send message, log result."""
    appt_id = appointment["AppointmentID"]
    phone = (appointment.get("Phone") or "").strip()
    patient_name = f"{appointment.get('PatientFirstName', '')} {appointment.get('PatientLastName', '')}".strip()

    logger.info(
        "Processing reminder for appointment %d: %s, %s at %s",
        appt_id, patient_name,
        appointment.get("ExamType"), appointment.get("AppointmentDateTime"),
    )

    # ----- Step 1: Validate the phone number -----
    check_result = easysms_client.check_mobile(phone)

    if check_result is None:
        logger.warning(
            "Phone %s for patient %s is not valid. Skipping.", phone, patient_name,
        )
        database.insert_notification(appt_id, None, "None", "Failed")
        return

    # Use the normalized MSISDN number if available
    mobile_info = check_result.get("mobile", {})
    normalized_phone = mobile_info.get("msisdn") or phone

    # ----- Step 2: Build the message -----
    message = build_message(appointment)

    # ----- Step 3: Try Viber (with built-in SMS fallback) -----
    preferred = (appointment.get("PreferredChannel") or "").lower()
    prefer_sms_only = preferred == "sms"

    if not prefer_sms_only:
        viber_result = easysms_client.send_viber(
            to=normalized_phone,
            text=message,
            sms_fallback_text=message,
        )

        if viber_result is not None:
            # Viber API accepted the message. The message ID is in "id".
            msg_id = str(viber_result.get("id", ""))
            database.insert_notification(appt_id, msg_id, "Viber", "Sent")
            logger.info(
                "Viber reminder sent for appointment %d, id=%s", appt_id, msg_id,
            )
            return  # Done — easysms.gr will auto-fallback to SMS if Viber fails

        logger.warning(
            "Viber send failed at API level for appointment %d. Trying direct SMS.",
            appt_id,
        )

    # ----- Step 4: Direct SMS fallback -----
    sms_result = easysms_client.send_sms(
        to=normalized_phone,
        text=message,
    )

    if sms_result is not None:
        msg_id = str(sms_result.get("smsId", ""))
        database.insert_notification(appt_id, msg_id, "SMS", "Sent")
        logger.info("SMS reminder sent for appointment %d, smsId=%s", appt_id, msg_id)
    else:
        database.insert_notification(appt_id, None, "SMS", "Failed")
        logger.error(
            "All channels failed for appointment %d (patient: %s)",
            appt_id, patient_name,
        )


def process_reminders() -> None:
    """Query due appointments and send reminders for each."""
    try:
        appointments = database.get_due_appointments(cfg.LEAD_TIME_HOURS)
    except Exception:
        logger.exception("Failed to query due appointments")
        return

    if not appointments:
        logger.debug("No appointments due for reminder.")
        return

    logger.info("Processing %d appointments for reminders", len(appointments))

    for appointment in appointments:
        try:
            send_reminder_for_appointment(appointment)
        except Exception:
            logger.exception(
                "Failed to send reminder for appointment %d",
                appointment.get("AppointmentID"),
            )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point — run the reminder loop forever."""
    import os
    os.makedirs("logs", exist_ok=True)

    logger.info(
        "ReminderService started. Interval=%dmin, LeadTime=%dh",
        cfg.INTERVAL_MINUTES, cfg.LEAD_TIME_HOURS,
    )

    while True:
        try:
            process_reminders()
        except Exception:
            logger.exception("Unhandled error in reminder processing loop")

        logger.debug("Sleeping for %d minutes...", cfg.INTERVAL_MINUTES)
        time.sleep(cfg.INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
