namespace KosmoSMS.ReminderService.Models;

/// <summary>
/// Represents an appointment that is due for a reminder notification.
/// This is a flattened view joining Appointments, Patients, Doctors, and Labs.
/// </summary>
public class AppointmentReminder
{
    // Appointment
    public int AppointmentID { get; set; }
    public int SlisAppointmentID { get; set; }
    public DateTime AppointmentDateTime { get; set; }
    public string? ExamType { get; set; }
    public string Status { get; set; } = string.Empty;

    // Patient
    public int PatientID { get; set; }
    public string PatientFirstName { get; set; } = string.Empty;
    public string PatientLastName { get; set; } = string.Empty;
    public string? Phone { get; set; }
    public string? Email { get; set; }
    public string? PreferredChannel { get; set; }

    // Doctor
    public int? DocID { get; set; }
    public string? DoctorFirstName { get; set; }
    public string? DoctorLastName { get; set; }
    public string? Expertise { get; set; }

    // Lab
    public int? LabID { get; set; }
    public string? LabName { get; set; }
    public string? LabGeoLocation { get; set; }

    /// <summary>
    /// Convenience property: "FirstName LastName"
    /// </summary>
    public string PatientFullName => $"{PatientFirstName} {PatientLastName}".Trim();

    /// <summary>
    /// Convenience property: "FirstName LastName"
    /// </summary>
    public string DoctorFullName =>
        string.IsNullOrWhiteSpace(DoctorFirstName) && string.IsNullOrWhiteSpace(DoctorLastName)
            ? string.Empty
            : $"{DoctorFirstName} {DoctorLastName}".Trim();
}
