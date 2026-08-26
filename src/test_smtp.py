"""
KosmoReminder — SMTP Credentials Test Script

Usage:
    python src/test_smtp.py [recipient_email]

Example:
    python src/test_smtp.py myemail@example.com
"""

import sys
import os
from datetime import datetime

# Configure UTF-8 encoding for Windows console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure src/ is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import cfg
from email_reminder_service import send_email

def main():
    print(f"--- KosmoReminder SMTP Test ---")
    print(f"SMTP Host: {cfg.SMTP_HOST}:{cfg.SMTP_PORT}")
    print(f"SMTP User: {cfg.SMTP_USER}")
    print(f"From:      {cfg.EMAIL_FROM_NAME} <{cfg.EMAIL_FROM_ADDRESS}>")
    print("--------------------------------")

    if len(sys.argv) > 1:
        recipient = sys.argv[1].strip()
    else:
        recipient = input("Enter recipient email address to send test email to: ").strip()

    if not recipient:
        print("Error: No recipient email provided.")
        sys.exit(1)

    dummy_appointment = {
        "AppointmentID": 99999,
        "Email": recipient,
        "AppointmentDateTime": datetime.now(),
        "Department": "Τμήμα Αξονικού Τομογράφου",
        "LabName": "Μονάδα Πατησίων",
        "LabAddress": "Λεωφ. Γαλατσίου 13, Πατήσια 111 41",
        "PatientFirstName": "Δοκιμαστικός",
        "PatientLastName": "Ασθενής",
        "Sex": "M",
    }

    print(f"\nSending test reminder email to: {recipient} ...")
    success = send_email(dummy_appointment)

    if success:
        print("\nSuccess! Test email sent successfully.")
    else:
        print("\nFailed to send email. Check logs/email-reminder-service.log for full error details.")

if __name__ == "__main__":
    main()
