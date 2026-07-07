"""
KosmoSMS — Calendar Invite Builder

Generates an .ics calendar payload for an appointment.
"""

from datetime import timedelta
from icalendar import Calendar, Event, vCalAddress, vText

from config import cfg

def build_ics(appointment: dict) -> bytes:
    """
    Build a valid .ics payload for a given appointment.
    """
    cal = Calendar()
    cal.add('prodid', '-//KosmoSMS Calendar Invite//kosmoiatriki.com//')
    cal.add('version', '2.0')
    cal.add('method', 'REQUEST')

    event = Event()
    
    # Stable UID
    appt_id = appointment.get("AppointmentID", 0)
    event.add('uid', f'appt-{appt_id}@kosmoiatriki')
    event.add('sequence', 0)
    
    dt = appointment.get("AppointmentDateTime")
    if dt:
        event.add('dtstart', dt)
        event.add('dtend', dt + timedelta(minutes=30))
        event.add('dtstamp', dt)
        
    organizer_email = cfg.ORGANIZER_EMAIL or "noreply@kosmoiatriki.com"
    organizer = vCalAddress(f'MAILTO:{organizer_email}')
    organizer.params['cn'] = vText(cfg.EMAIL_FROM_NAME or "Kosmoiatriki")
    event.add('organizer', organizer)
    
    patient_email = appointment.get("Email")
    if patient_email:
        attendee = vCalAddress(f'MAILTO:{patient_email}')
        attendee.params['cn'] = vText(f"{appointment.get('PatientFirstName', '')} {appointment.get('PatientLastName', '')}".strip())
        attendee.params['rsvp'] = vText('TRUE')
        event.add('attendee', attendee, encode=0)
        
    # Summary and Description using existing placeholders approach
    department = appointment.get("Department") or "Τμήμα"
    lab_name = appointment.get("LabName") or "το εργαστήριο μας"
    lab_address = appointment.get("LabAddress") or ""
    
    event.add('summary', f"Ραντεβού: {department} - {lab_name}")
    event.add('location', lab_address)
    
    description = f"Έχετε προγραμματισμένο ραντεβού στο {department} της Μονάδας {lab_name}."
    event.add('description', description)
    
    cal.add_component(event)
    return cal.to_ical()
