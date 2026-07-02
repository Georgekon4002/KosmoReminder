"""
KosmoSMS — Database Access Layer

All SQL queries against the KosmoSMS database live here.
Uses pyodbc for MS SQL Server connectivity.
"""

import logging
from decimal import Decimal
from typing import Optional

import pyodbc

from config import cfg

logger = logging.getLogger(__name__)


def get_connection() -> pyodbc.Connection:
    """Open a new connection to the KosmoSMS database."""
    return pyodbc.connect(cfg.DB_CONNECTION_STRING)


# =============================================================================
# Queries used by reminder_service.py
# =============================================================================

_SQL_DUE_APPOINTMENTS = """\
SELECT
    a.AppointmentID,
    a.SlisAppointmentID,
    a.AppointmentDateTime,
    a.ExamType,
    a.Status,
    -- Patient
    p.PatientID,
    p.FirstName   AS PatientFirstName,
    p.LastName    AS PatientLastName,
    p.Phone,
    p.Email,
    p.PreferredChannel,
    -- Doctor
    d.DocID,
    d.FirstName   AS DoctorFirstName,
    d.LastName    AS DoctorLastName,
    d.Expertise,
    -- Lab
    l.LabID,
    l.LabName,
    l.LabGeoLocation
FROM dbo.Appointments a
INNER JOIN dbo.Patients p ON p.PatientID = a.PatientID
LEFT  JOIN dbo.Doctors  d ON d.DocID     = a.DocID
LEFT  JOIN dbo.Labs     l ON l.LabID     = a.LabID
WHERE
    -- Appointment is in the future
    a.AppointmentDateTime > SYSUTCDATETIME()
    -- Appointment is within the reminder window
    AND a.AppointmentDateTime <= DATEADD(HOUR, ?, SYSUTCDATETIME())
    -- Not cancelled or completed
    AND a.Status NOT IN ('Cancelled', 'Completed')
    -- Patient has a phone number
    AND p.Phone IS NOT NULL
    AND LEN(LTRIM(RTRIM(p.Phone))) > 0
    -- No existing successful notification for this appointment
    AND NOT EXISTS (
        SELECT 1
        FROM dbo.Notifications n
        WHERE n.AppointmentID = a.AppointmentID
          AND n.Status IN ('Sent', 'Delivered', 'Pending')
    )
ORDER BY a.AppointmentDateTime;
"""


def get_due_appointments(lead_time_hours: int) -> list[dict]:
    """
    Query appointments that are due for a reminder.

    Returns a list of dicts, each representing a flattened appointment
    with patient, doctor, and lab info.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(_SQL_DUE_APPOINTMENTS, (lead_time_hours,))

        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        cursor.close()
        conn.close()

        logger.info("Found %d appointments due for reminder", len(rows))
        return rows

    except Exception:
        logger.exception("Error querying due appointments")
        raise


_SQL_INSERT_NOTIFICATION = """\
INSERT INTO dbo.Notifications
    (AppointmentID, MessageID, ChannelUsed, SentAt, Status)
OUTPUT INSERTED.NotificationID
VALUES
    (?, ?, ?, SYSUTCDATETIME(), ?);
"""


def insert_notification(
    appointment_id: int,
    message_id: Optional[str],
    channel_used: str,
    status: str,
) -> int:
    """
    Insert a notification record and return its NotificationID.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            _SQL_INSERT_NOTIFICATION,
            (appointment_id, message_id, channel_used, status),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to insert notification, no ID returned")
        notification_id = row[0]
        conn.commit()
        cursor.close()
        conn.close()

        logger.info(
            "Notification %d created for appointment %d via %s — status: %s",
            notification_id, appointment_id, channel_used, status,
        )
        return notification_id

    except Exception:
        logger.exception(
            "Error inserting notification for appointment %d", appointment_id
        )
        raise


# =============================================================================
# Queries used by callback_receiver.py
# =============================================================================

_SQL_EXISTS_PENDING = """\
SELECT CASE WHEN EXISTS (
    SELECT 1 FROM dbo.Notifications
    WHERE MessageID = ?
      AND Status IN ('Pending', 'Sent')
) THEN 1 ELSE 0 END;
"""


def notification_exists_pending(message_id: str) -> bool:
    """Check if a pending/sent notification exists for the given message ID."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(_SQL_EXISTS_PENDING, (message_id,))
        row = cursor.fetchone()
        result = row[0] if row is not None else 0
        cursor.close()
        conn.close()
        return bool(result)

    except Exception:
        logger.exception(
            "Error checking pending notification for msgid=%s", message_id
        )
        raise


_SQL_UPDATE_STATUS = """\
UPDATE dbo.Notifications
SET Status      = ?,
    DeliveredAt = CASE WHEN ? = 'Delivered' THEN SYSUTCDATETIME() ELSE DeliveredAt END,
    Cost        = COALESCE(?, Cost),
    MCC         = COALESCE(?, MCC),
    MNC         = COALESCE(?, MNC)
WHERE MessageID = ?
  AND Status IN ('Pending', 'Sent');
"""

_STATUS_MAP = {
    "delivered": "Delivered",
    "failed": "Failed",
    "rejected": "Rejected",
    "expired": "Failed",
    "sent": "Sent",
}


def update_delivery_status(
    message_id: str,
    external_status: str,
    cost: Optional[Decimal],
    mcc: Optional[str],
    mnc: Optional[str],
) -> bool:
    """
    Update a notification's delivery status from an easysms.gr callback.

    Maps external status strings (delivered, failed, etc.) to internal values.
    Returns True if a row was updated, False if no pending row was found.
    """
    internal_status = _STATUS_MAP.get(external_status.lower(), external_status)

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            _SQL_UPDATE_STATUS,
            (internal_status, internal_status, cost, mcc, mnc, message_id),
        )
        rows_affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()

        if rows_affected > 0:
            logger.info(
                "Notification updated: msgid=%s, status=%s, cost=%s",
                message_id, internal_status, cost,
            )
            return True
        else:
            logger.warning(
                "No pending notification found for msgid=%s (may already be updated)",
                message_id,
            )
            return False

    except Exception:
        logger.exception(
            "Error updating notification status for msgid=%s", message_id
        )
        raise
