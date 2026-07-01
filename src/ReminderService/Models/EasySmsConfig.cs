namespace KosmoSMS.ReminderService.Models;

/// <summary>
/// Configuration POCO bound to the "EasySms" section of appsettings.json.
/// </summary>
public class EasySmsConfig
{
    public const string SectionName = "EasySms";

    /// <summary>
    /// Base URL for the easysms.gr API (e.g., "https://easysms.gr/api").
    /// </summary>
    public string BaseUrl { get; set; } = "https://easysms.gr/api";

    /// <summary>
    /// API key generated from the easysms.gr dashboard.
    /// </summary>
    public string ApiKey { get; set; } = string.Empty;

    /// <summary>
    /// Approved Viber Sender ID (e.g., "Kosmoiatriki").
    /// Must be registered with easysms.gr / Viber.
    /// </summary>
    public string ViberSenderId { get; set; } = string.Empty;

    /// <summary>
    /// SMS Sender ID / alphanumeric originator.
    /// </summary>
    public string SmsSenderId { get; set; } = string.Empty;

    /// <summary>
    /// The publicly-accessible URL that easysms.gr will call back for delivery reports.
    /// e.g., "https://your-domain.com/api/sms-callback"
    /// </summary>
    public string CallbackUrl { get; set; } = string.Empty;
}

/// <summary>
/// Configuration POCO bound to the "Reminder" section of appsettings.json.
/// </summary>
public class ReminderConfig
{
    public const string SectionName = "Reminder";

    /// <summary>
    /// How many hours before the appointment to send the reminder.
    /// Default: 24 hours.
    /// </summary>
    public int LeadTimeHours { get; set; } = 24;

    /// <summary>
    /// How often (in minutes) the reminder worker checks for due appointments.
    /// Default: 15 minutes.
    /// </summary>
    public int IntervalMinutes { get; set; } = 15;

    /// <summary>
    /// Message template with placeholders:
    /// {PatientName}, {ExamType}, {DateTime}, {LabName}, {DoctorName}
    /// </summary>
    public string MessageTemplate { get; set; } =
        "Αγαπητέ/ή {PatientName}, σας υπενθυμίζουμε το ραντεβού σας στις {DateTime} για {ExamType} στο {LabName}. Ιατρός: {DoctorName}.";
}
