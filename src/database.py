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

# Groups appointments by patient + lab + department + appointment day.
# A patient with same-day exams in DIFFERENT departments gets separate SMS.
# A patient with same-day exams in the SAME department gets one SMS
# with all exam types concatenated.
_SQL_DUE_APPOINTMENTS = """\
SELECT
    STRING_AGG(a.ExamType, ', ') WITHIN GROUP (ORDER BY a.AppointmentDateTime)
                                    AS ExamType,
    MIN(a.AppointmentDateTime)      AS AppointmentDateTime,
    STRING_AGG(CAST(a.AppointmentID AS NVARCHAR(20)), '|')
                                    AS AppointmentIDs,
    -- Department (normalized from SCHEDULERRESOURCESGROUP via DepartmentMap)
    a.Department,
    -- Patient
    p.PatientID,
    p.FirstName   AS PatientFirstName,
    p.LastName    AS PatientLastName,
    p.Phone,
    p.Email,
    p.Sex,
    p.PreferredChannel,
    -- Lab
    l.LabID,
    l.LabName,
    l.LabAddress
FROM dbo.Appointments a
INNER JOIN dbo.Patients p ON p.PatientID = a.PatientID
LEFT  JOIN dbo.Labs     l ON l.LabID     = a.LabID
WHERE
    a.AppointmentDateTime > SYSDATETIME()
    AND a.AppointmentDateTime <= DATEADD(HOUR, ?, SYSDATETIME())
    AND a.Status NOT IN ('Cancelled', 'Completed')
    AND p.Phone IS NOT NULL
    AND LEN(LTRIM(RTRIM(p.Phone))) > 0
    -- Exclude groups where ALL appointments already have a notification
    AND NOT EXISTS (
        SELECT 1
        FROM dbo.Notifications n
        WHERE n.AppointmentID = a.AppointmentID
          AND n.Status IN ('Sent', 'Delivered', 'Pending')
    )
GROUP BY
    p.PatientID,
    p.FirstName,
    p.LastName,
    p.Phone,
    p.Email,
    p.Sex,
    p.PreferredChannel,
    l.LabID,
    l.LabName,
    l.LabAddress,
    a.Department,
    CAST(a.AppointmentDateTime AS DATE)
ORDER BY AppointmentDateTime;
"""


def get_due_appointments(lead_time_hours: int) -> list[dict]:
    """
    Query appointments due for a reminder, grouped by patient + lab + day.

    Each dict represents one SMS to send. Key fields:
      - AppointmentIDs      : pipe-delimited string of grouped appointment IDs
      - ExamType            : comma-separated list of normalized exam names
      - Department          : patient-facing department name (e.g. 'Τμήμα Αξονικού')
      - AppointmentDateTime : earliest slot (used for Day/Date/Time in SMS)
      - Sex                 : 'M' | 'F' | None — for the gendered greeting helper
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(_SQL_DUE_APPOINTMENTS, (lead_time_hours,))

        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        cursor.close()
        conn.close()

        logger.info("Found %d appointment groups due for reminder", len(rows))
        return rows

    except Exception:
        logger.exception("Error querying due appointments")
        raise


_SQL_INSERT_NOTIFICATION = """\
INSERT INTO dbo.Notifications
    (AppointmentID, MessageID, ChannelUsed, SentAt, Status)
OUTPUT INSERTED.NotificationID
VALUES
    (?, ?, ?, SYSDATETIME(), ?);
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


_SQL_UPDATE_PREFERRED_CHANNEL = """\
UPDATE dbo.Patients
SET PreferredChannel = ?
WHERE PatientID = ?;
"""

def set_preferred_channel(patient_id: int, channel: str) -> None:
    """
    Update the preferred channel for a patient.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(_SQL_UPDATE_PREFERRED_CHANNEL, (channel, patient_id))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Updated preferred channel for patient %d to %s", patient_id, channel)
    except Exception:
        logger.exception("Error updating preferred channel for patient %d", patient_id)
        # We don't raise here, as this is a non-critical update

def insert_notifications_for_group(
    appointment_ids: list[int],
    message_id: Optional[str],
    channel_used: str,
    status: str,
) -> None:
    """
    Insert one Notification row per appointment in a grouped SMS send.

    All rows share the same message_id (the single SMS sent to the patient)
    so delivery callbacks update all of them at once.
    """
    for appt_id in appointment_ids:
        insert_notification(appt_id, message_id, channel_used, status)


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
    DeliveredAt = CASE WHEN ? = 'Delivered' THEN SYSDATETIME() ELSE DeliveredAt END,
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

# =============================================================================
# Email Queries
# =============================================================================

_SQL_UNSENT_EMAILS = """\
SELECT
    a.AppointmentID,
    a.AppointmentDateTime,
    a.Department,
    p.PatientID,
    p.FirstName AS PatientFirstName,
    p.LastName AS PatientLastName,
    p.Email,
    l.LabName,
    l.LabAddress
FROM dbo.Appointments a
INNER JOIN dbo.Patients p ON p.PatientID = a.PatientID
LEFT JOIN dbo.Labs l ON l.LabID = a.LabID
WHERE
    a.EmailStatus IS NULL
    AND a.AppointmentDateTime > SYSDATETIME()
    AND a.Status NOT IN ('Cancelled', 'Completed');
"""

def get_unsent_emails() -> list[dict]:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(_SQL_UNSENT_EMAILS)
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return rows
    except Exception:
        logger.exception("Error querying unsent emails")
        raise

_SQL_UPDATE_EMAIL_STATUS = """\
UPDATE dbo.Appointments
SET EmailStatus = ?
WHERE AppointmentID = ?;
"""

def update_email_status(appointment_id: int, status: str) -> None:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(_SQL_UPDATE_EMAIL_STATUS, (status, appointment_id))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Updated EmailStatus for appointment %d to %s", appointment_id, status)
    except Exception:
        logger.exception("Error updating EmailStatus for appointment %d", appointment_id)


# =============================================================================
# Queries used by dashboard UI
# =============================================================================

_SQL_DASHBOARD_STATS = """\
SELECT 
    COUNT(*) AS Total,
    SUM(CASE WHEN Status = 'Sent' THEN 1 ELSE 0 END) AS Sent,
    SUM(CASE WHEN Status = 'Delivered' THEN 1 ELSE 0 END) AS Delivered,
    SUM(CASE WHEN Status IN ('Failed', 'Rejected') THEN 1 ELSE 0 END) AS Failed,
    SUM(CASE WHEN Status = 'Pending' THEN 1 ELSE 0 END) AS Pending
FROM dbo.Notifications;
"""

_SQL_DASHBOARD_STATS_TODAY = """\
SELECT 
    COUNT(*) AS Total,
    SUM(CASE WHEN Status = 'Sent' THEN 1 ELSE 0 END) AS Sent,
    SUM(CASE WHEN Status = 'Delivered' THEN 1 ELSE 0 END) AS Delivered,
    SUM(CASE WHEN Status IN ('Failed', 'Rejected') THEN 1 ELSE 0 END) AS Failed,
    SUM(CASE WHEN Status = 'Pending' THEN 1 ELSE 0 END) AS Pending
FROM dbo.Notifications
WHERE CAST(SentAt AS DATE) = CAST(SYSDATETIME() AS DATE);
"""

def get_dashboard_stats(mode: str = 'all-time') -> dict:
    """Get aggregate statistics for the dashboard."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if mode == 'today-sent':
            cursor.execute(_SQL_DASHBOARD_STATS_TODAY)
        else:
            cursor.execute(_SQL_DASHBOARD_STATS)
        
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if row:
            return dict(zip(columns, row))
        return {"Total": 0, "Sent": 0, "Delivered": 0, "Failed": 0, "Pending": 0}
        
    except Exception:
        logger.exception("Error fetching dashboard stats")
        return {"Total": 0, "Sent": 0, "Delivered": 0, "Failed": 0, "Pending": 0}

_SQL_ALL_NOTIFICATIONS = """\
SELECT
    n.NotificationID,
    n.MessageID,
    n.ChannelUsed,
    n.Status,
    n.SentAt,
    n.DeliveredAt,
    n.Cost,
    a.AppointmentID,
    a.AppointmentDateTime,
    a.ExamType,
    a.Department,
    a.EmailStatus,
    p.FirstName,
    p.LastName,
    p.Phone
FROM dbo.Notifications n
LEFT JOIN dbo.Appointments a ON n.AppointmentID = a.AppointmentID
LEFT JOIN dbo.Patients p ON a.PatientID = p.PatientID
WHERE CAST(a.AppointmentDateTime AS DATE) >= ? AND CAST(a.AppointmentDateTime AS DATE) <= ?
ORDER BY a.AppointmentDateTime ASC;
"""

_SQL_TODAY_NOTIFICATIONS = """\
SELECT
    n.NotificationID,
    n.MessageID,
    n.ChannelUsed,
    n.Status,
    n.SentAt,
    n.DeliveredAt,
    n.Cost,
    a.AppointmentID,
    a.AppointmentDateTime,
    a.ExamType,
    a.Department,
    a.EmailStatus,
    p.FirstName,
    p.LastName,
    p.Phone
FROM dbo.Notifications n
LEFT JOIN dbo.Appointments a ON n.AppointmentID = a.AppointmentID
LEFT JOIN dbo.Patients p ON a.PatientID = p.PatientID
WHERE CAST(n.SentAt AS DATE) = CAST(SYSDATETIME() AS DATE)
ORDER BY n.SentAt DESC;
"""

def get_all_notifications(start_date: str = None, end_date: str = None, mode: str = 'all-time') -> list[dict]:
    """Get a list of notifications for the dashboard list bounded by dates."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if mode == 'today-sent':
            cursor.execute(_SQL_TODAY_NOTIFICATIONS)
        else:
            cursor.execute(_SQL_ALL_NOTIFICATIONS, (start_date, end_date))
        
        columns = [desc[0] for desc in cursor.description]
        rows = []
        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))
            # Format dates to string for JSON serialization
            if row_dict['SentAt']:
                row_dict['SentAt'] = row_dict['SentAt'].isoformat()
            if row_dict['DeliveredAt']:
                row_dict['DeliveredAt'] = row_dict['DeliveredAt'].isoformat()
            if row_dict['AppointmentDateTime']:
                row_dict['AppointmentDateTime'] = row_dict['AppointmentDateTime'].isoformat()
            if row_dict['Cost'] is not None:
                row_dict['Cost'] = float(row_dict['Cost'])
            rows.append(row_dict)
            
        cursor.close()
        conn.close()
        return rows
        
    except Exception:
        logger.exception("Error fetching all notifications")
        return []

_SQL_PENDING_APPOINTMENTS_TODAY = """\
SELECT
    STRING_AGG(a.ExamType, ', ') WITHIN GROUP (ORDER BY a.AppointmentDateTime)
                                    AS ExamType,
    MIN(a.AppointmentDateTime)      AS AppointmentDateTime,
    STRING_AGG(CAST(a.AppointmentID AS NVARCHAR(20)), '|')
                                    AS AppointmentIDs,
    a.Department,
    a.EmailStatus,
    p.PatientID,
    p.FirstName   AS PatientFirstName,
    p.LastName    AS PatientLastName,
    p.Phone,
    p.Email,
    p.Sex,
    p.PreferredChannel,
    l.LabID,
    l.LabName,
    l.LabAddress
FROM dbo.Appointments a
INNER JOIN dbo.Patients p ON p.PatientID = a.PatientID
LEFT  JOIN dbo.Labs     l ON l.LabID     = a.LabID
WHERE
    a.AppointmentDateTime > SYSDATETIME()
    AND CAST(a.AppointmentDateTime AS DATE) = CAST(DATEADD(DAY, 1, SYSDATETIME()) AS DATE)
    AND a.Status NOT IN ('Cancelled', 'Completed')
    AND p.Phone IS NOT NULL
    AND LEN(LTRIM(RTRIM(p.Phone))) > 0
    AND NOT EXISTS (
        SELECT 1
        FROM dbo.Notifications n
        WHERE n.AppointmentID = a.AppointmentID
          AND n.Status IN ('Sent', 'Delivered', 'Pending')
    )
GROUP BY
    p.PatientID, p.FirstName, p.LastName, p.Phone, p.Email, p.Sex, p.PreferredChannel,
    l.LabID, l.LabName, l.LabAddress, a.Department, a.EmailStatus, CAST(a.AppointmentDateTime AS DATE)
ORDER BY AppointmentDateTime;
"""

_SQL_PENDING_APPOINTMENTS_ALL = """\
SELECT
    STRING_AGG(a.ExamType, ', ') WITHIN GROUP (ORDER BY a.AppointmentDateTime)
                                    AS ExamType,
    MIN(a.AppointmentDateTime)      AS AppointmentDateTime,
    STRING_AGG(CAST(a.AppointmentID AS NVARCHAR(20)), '|')
                                    AS AppointmentIDs,
    a.Department,
    a.EmailStatus,
    p.PatientID,
    p.FirstName   AS PatientFirstName,
    p.LastName    AS PatientLastName,
    p.Phone,
    p.Email,
    p.Sex,
    p.PreferredChannel,
    l.LabID,
    l.LabName,
    l.LabAddress
FROM dbo.Appointments a
INNER JOIN dbo.Patients p ON p.PatientID = a.PatientID
LEFT  JOIN dbo.Labs     l ON l.LabID     = a.LabID
WHERE
    CAST(a.AppointmentDateTime AS DATE) >= ? AND CAST(a.AppointmentDateTime AS DATE) <= ?
    AND a.Status NOT IN ('Cancelled', 'Completed')
    AND p.Phone IS NOT NULL
    AND LEN(LTRIM(RTRIM(p.Phone))) > 0
    AND NOT EXISTS (
        SELECT 1
        FROM dbo.Notifications n
        WHERE n.AppointmentID = a.AppointmentID
          AND n.Status IN ('Sent', 'Delivered', 'Pending')
    )
GROUP BY
    p.PatientID, p.FirstName, p.LastName, p.Phone, p.Email, p.Sex, p.PreferredChannel,
    l.LabID, l.LabName, l.LabAddress, a.Department, a.EmailStatus, CAST(a.AppointmentDateTime AS DATE)
ORDER BY AppointmentDateTime;
"""

def get_pending_appointments(start_date: str = None, end_date: str = None, mode: str = 'all-time') -> list[dict]:
    """Get pending appointments that have not received a notification yet."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if mode == 'today':
            cursor.execute(_SQL_PENDING_APPOINTMENTS_TODAY)
        else:
            cursor.execute(_SQL_PENDING_APPOINTMENTS_ALL, (start_date, end_date))
            
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        return rows
        
    except Exception:
        logger.exception("Error fetching pending appointments")
        return []

_SQL_APPOINTMENT_FOR_EMAIL = """\
SELECT
    a.AppointmentID,
    a.AppointmentDateTime,
    a.Department,
    p.PatientID,
    p.FirstName AS PatientFirstName,
    p.LastName AS PatientLastName,
    p.Email,
    l.LabName,
    l.LabAddress
FROM dbo.Appointments a
INNER JOIN dbo.Patients p ON p.PatientID = a.PatientID
LEFT JOIN dbo.Labs l ON l.LabID = a.LabID
WHERE a.AppointmentID = ?;
"""

def get_appointment_for_email(appointment_id: int) -> Optional[dict]:
    """Fetch appointment details needed to send an email."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(_SQL_APPOINTMENT_FOR_EMAIL, (appointment_id,))
        row = cursor.fetchone()
        
        if not row:
            cursor.close()
            conn.close()
            return None
            
        columns = [desc[0] for desc in cursor.description]
        result = dict(zip(columns, row))
        
        cursor.close()
        conn.close()
        return result
    except Exception:
        logger.exception("Error fetching appointment for email (ID: %s)", appointment_id)
        return None

_SQL_APPOINTMENT_GROUP_BY_IDS = """\
SELECT
    STRING_AGG(a.ExamType, ', ') WITHIN GROUP (ORDER BY a.AppointmentDateTime)
                                    AS ExamType,
    MIN(a.AppointmentDateTime)      AS AppointmentDateTime,
    STRING_AGG(CAST(a.AppointmentID AS NVARCHAR(20)), '|')
                                    AS AppointmentIDs,
    a.Department,
    p.PatientID,
    p.FirstName   AS PatientFirstName,
    p.LastName    AS PatientLastName,
    p.Phone,
    p.Email,
    p.Sex,
    p.PreferredChannel,
    l.LabID,
    l.LabName,
    l.LabAddress
FROM dbo.Appointments a
INNER JOIN dbo.Patients p ON p.PatientID = a.PatientID
LEFT  JOIN dbo.Labs     l ON l.LabID     = a.LabID
WHERE a.AppointmentID IN ({})
GROUP BY
    p.PatientID, p.FirstName, p.LastName, p.Phone, p.Email, p.Sex, p.PreferredChannel,
    l.LabID, l.LabName, l.LabAddress, a.Department, CAST(a.AppointmentDateTime AS DATE)
ORDER BY AppointmentDateTime;
"""

def get_appointment_group_by_ids(appointment_ids: list[int]) -> Optional[dict]:
    """Fetch appointment group details needed to send an SMS."""
    if not appointment_ids:
        return None
        
    try:
        placeholders = ','.join('?' * len(appointment_ids))
        query = _SQL_APPOINTMENT_GROUP_BY_IDS.format(placeholders)
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, appointment_ids)
        row = cursor.fetchone()
        
        if not row:
            cursor.close()
            conn.close()
            return None
            
        columns = [desc[0] for desc in cursor.description]
        result = dict(zip(columns, row))
        
        cursor.close()
        conn.close()
        return result
    except Exception:
        logger.exception("Error fetching appointment group by IDs: %s", appointment_ids)
        return None

