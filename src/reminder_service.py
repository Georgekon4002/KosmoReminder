"""
KosmoSMS — Reminder Service

Background script that periodically checks for appointments due for a
reminder and sends Viber/SMS notifications via easysms.gr.

Flow for each appointment group (patient + lab + department + day):
  1. Validate phone number via api/mobile/check
  2. Build message using the official Kosmoiatriki template
  3. Try Viber (with built-in SMS fallback from easysms.gr)
  4. If Viber API call fails entirely, fall back to direct SMS send
  5. Log one Notification row per underlying AppointmentID

Usage:
  python reminder_service.py
"""

import logging
import sys
import time

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
# Greek vocative conversion  (reserved for future personalised messages)
# ---------------------------------------------------------------------------
# Converts an all-caps Greek name stored in Slis to its proper vocative form.
#
# Strategy (covers ~95% of modern Greek names):
#   1. Title-case the raw string (ΜΟΥΓΚΑΡΑΚΗΣ → Μουγκαρακης).
#   2. Apply suffix replacement rules to produce the vocative case.
#
# Limitations: polytonic / irregular forms (e.g. Ζευς → Ζευ) are not
# handled — these are exceedingly rare in a medical context.
# ---------------------------------------------------------------------------

# Rules ordered most-specific (longest suffix) → least-specific.
_VOCATIVE_RULES_MASC = [
    ("ιος", "ιε"),   # Δημήτριος → Δημήτριε
    ("ης",  "η"),    # Παναγιώτης → Παναγιώτη  /  Μουγκαράκης → Μουγκαράκη
    ("ος",  "ε"),    # Νίκος → Νίκε
    ("ας",  "α"),    # Ηλίας → Ηλία
]

# Female names: nominative == vocative in Modern Greek for -α / -η endings.
# No rules needed — title-casing is sufficient.
_VOCATIVE_RULES_FEM: list[tuple[str, str]] = []


def _title_case_greek(name: str) -> str:
    """Title-case a single all-caps Greek word, preserving accents correctly."""
    if not name:
        return name
    return name.capitalize()


def to_vocative(raw_name: str, sex: str | None) -> str:
    """
    Convert an all-caps Greek name to its vocative case.

    Args:
        raw_name: all-caps string, e.g. 'ΜΟΥΓΚΑΡΑΚΗΣ'
        sex:      'M', 'F', or None

    Returns:
        Vocative form, e.g. 'Μουγκαράκη' / 'Παναγιώτη' / 'Μαρία'

    Note: currently unused in the standard template but kept for future use
    in personalised message variants.
    """
    if not raw_name:
        return raw_name

    word = _title_case_greek(raw_name.strip())

    if sex == "M":
        for suffix, replacement in _VOCATIVE_RULES_MASC:
            if word.endswith(suffix.capitalize()) or word.endswith(suffix):
                base = word[: len(word) - len(suffix)]
                return base + replacement
        return word  # fallback: return title-cased nominative

    # Female / unknown: nominative == vocative
    return word


def build_greeting(first_name: str, last_name: str, sex: str | None) -> str:
    """
    Build a gender-appropriate vocative greeting.

    Examples:
      M, ΠΑΝΑΓΙΩΤΗΣ ΜΟΥΓΚΑΡΑΚΗΣ  → 'Αγαπητέ κύριε Μουγκαράκη Παναγιώτη'
      F, ΙΩΑΝΝΑ ΚΑΒΑΛΗ            → 'Αγαπητή κυρία Καβάλη Ιωάννα'
      None, …                      → 'Αγαπητέ/ή [LastName]'

    Note: currently unused in the standard template but kept for future use.
    """
    voc_last  = to_vocative(last_name,  sex)
    voc_first = to_vocative(first_name, sex)

    if sex == "M":
        return f"Αγαπητέ κύριε {voc_last} {voc_first}"
    elif sex == "F":
        return f"Αγαπητή κυρία {voc_last} {voc_first}"
    else:
        title = _title_case_greek(last_name) if last_name else ""
        return f"Αγαπητέ/ή {title}"


# ---------------------------------------------------------------------------
# Date / time helpers
# ---------------------------------------------------------------------------

_GREEK_DAYS = {
    0: "Δευτέρα",
    1: "Τρίτη",
    2: "Τετάρτη",
    3: "Πέμπτη",
    4: "Παρασκευή",
    5: "Σάββατο",
    6: "Κυριακή",
}


def _format_appointment_dt(dt) -> tuple[str, str, str]:
    """
    Split an appointment datetime into three template components.

    Returns:
        (day_name, date_str, time_str)
        e.g. ('Παρασκευή', '04/07/2026', '09:00')
    """
    if dt is None:
        return ("", "", "")
    day_name = _GREEK_DAYS.get(dt.weekday(), "")
    date_str = dt.strftime("%d/%m/%Y")
    time_str = dt.strftime("%H:%M")
    return day_name, date_str, time_str


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

def build_message(group: dict) -> str:
    """
    Build the SMS reminder message for one appointment group.

    Template placeholders (defined in config.MESSAGE_TEMPLATE or .env):
      {Department}  — patient-facing department  (e.g. 'Τμήμα Αξονικού')
      {LabName}     — branch short name          (e.g. 'Πατησίων')
      {LabAddress}  — branch address             (e.g. 'Πατησίων 237, ΤΚ 11254')
      {Day}         — Greek day name             (e.g. 'Παρασκευή')
      {Date}        — appointment date           (e.g. '04/07/2026')
      {Time}        — appointment time           (e.g. '09:00')

    Unused but available for custom templates:
      {Greeting}    — gendered vocative greeting  (via build_greeting())
      {ExamType}    — comma-separated exam names
    """
    appt_dt = group.get("AppointmentDateTime")
    day_name, date_str, time_str = _format_appointment_dt(appt_dt)

    # Greeting available for custom template variants
    first_name = (group.get("PatientFirstName") or "").strip()
    last_name  = (group.get("PatientLastName")  or "").strip()
    sex        = group.get("Sex")
    greeting   = build_greeting(first_name, last_name, sex)

    message = cfg.MESSAGE_TEMPLATE
    message = message.replace("{Department}",  group.get("Department")  or "Τμήμα")
    message = message.replace("{LabName}",     group.get("LabName")     or "το εργαστήριο μας")
    message = message.replace("{LabAddress}",  group.get("LabAddress")  or "")
    message = message.replace("{Day}",         day_name)
    message = message.replace("{Date}",        date_str)
    message = message.replace("{Time}",        time_str)
    # Extra placeholders available for custom templates
    message = message.replace("{Greeting}",    greeting)
    message = message.replace("{ExamType}",    group.get("ExamType")    or "εξέταση")

    # Fix grammatical article for Saturday
    message = message.replace("για την Σάββατο", "για το Σάββατο")

    return message


# ---------------------------------------------------------------------------
# Reminder processing
# ---------------------------------------------------------------------------

def send_reminder_for_group(group: dict) -> None:
    """
    Process one appointment group: validate phone, send message, log results.

    A 'group' is one dict from database.get_due_appointments() — it covers
    all appointments for the same patient at the same lab+department on the
    same day.
    """
    raw_ids = group.get("AppointmentIDs") or ""
    appt_ids: list[int] = [int(x) for x in raw_ids.split("|") if x.strip().isdigit()]

    phone = (group.get("Phone") or "").strip()
    first_name = (group.get("PatientFirstName") or "").strip()
    last_name  = (group.get("PatientLastName")  or "").strip()
    patient_label = f"{last_name} {first_name}".strip()

    logger.info(
        "Processing group: patient=%s IDs=%s department=%s dt=%s",
        patient_label,
        raw_ids,
        group.get("Department"),
        group.get("AppointmentDateTime"),
    )

    if not appt_ids:
        logger.error("Group has no valid AppointmentIDs, skipping: %s", raw_ids)
        return

    # ----- Step 1: Validate the phone number -----
    check_result = easysms_client.check_mobile(phone)

    if check_result is None:
        logger.warning("Phone %s for patient %s is not valid. Skipping.", phone, patient_label)
        database.insert_notifications_for_group(appt_ids, None, "None", "Failed")
        return

    mobile_info = check_result.get("mobile", {})
    normalized_phone = mobile_info.get("msisdn") or phone

    # ----- Step 2: Build the message -----
    message = build_message(group)
    logger.info("Generated message for %s:\n%s", patient_label, message)

    # ----- Step 3: Try Viber (with built-in SMS fallback) -----
    preferred = (group.get("PreferredChannel") or "").lower()
    prefer_sms_only = preferred == "sms"

    if not prefer_sms_only:
        viber_result = easysms_client.send_viber(
            to=normalized_phone,
            text=message,
            sms_fallback_text=message,
        )

        if viber_result is not None:
            msg_id = str(viber_result.get("id", ""))
            database.insert_notifications_for_group(appt_ids, msg_id, "Viber", "Sent")
            database.set_preferred_channel(group.get("PatientID"), "Viber")
            logger.info(
                "Viber reminder sent: patient=%s IDs=%s id=%s",
                patient_label, raw_ids, msg_id,
            )
            return  # easysms.gr will auto-fallback to SMS if Viber is undeliverable

        logger.warning(
            "Viber send failed at API level for patient %s. Trying direct SMS.", patient_label,
        )

    # ----- Step 4: Direct SMS fallback -----
    sms_result = easysms_client.send_sms(to=normalized_phone, text=message)

    if sms_result is not None:
        msg_id = str(sms_result.get("smsId", ""))
        database.insert_notifications_for_group(appt_ids, msg_id, "SMS", "Sent")
        database.set_preferred_channel(group.get("PatientID"), "SMS")
        logger.info(
            "SMS reminder sent: patient=%s IDs=%s smsId=%s", patient_label, raw_ids, msg_id,
        )
    else:
        database.insert_notifications_for_group(appt_ids, None, "SMS", "Failed")
        logger.error("All channels failed: patient=%s IDs=%s", patient_label, raw_ids)


def process_reminders() -> None:
    """Query due appointment groups and send a reminder for each."""
    try:
        groups = database.get_due_appointments(cfg.LEAD_TIME_HOURS)
    except Exception:
        logger.exception("Failed to query due appointments")
        return

    if not groups:
        logger.debug("No appointments due for reminder.")
        return

    logger.info("Processing %d appointment groups", len(groups))

    for group in groups:
        try:
            send_reminder_for_group(group)
        except Exception:
            logger.exception(
                "Failed to send reminder for group: patient=%s IDs=%s",
                group.get("PatientID"),
                group.get("AppointmentIDs"),
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
