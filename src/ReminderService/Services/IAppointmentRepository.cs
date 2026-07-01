using KosmoSMS.ReminderService.Models;

namespace KosmoSMS.ReminderService.Services;

/// <summary>
/// Reads appointments that are due for reminder notifications.
/// </summary>
public interface IAppointmentRepository
{
    /// <summary>
    /// Returns appointments that:
    /// - Are within the reminder window (appointment time is leadTimeHours from now)
    /// - Have not already been successfully notified
    /// - Are not cancelled
    /// </summary>
    Task<IEnumerable<AppointmentReminder>> GetDueAppointmentsAsync(int leadTimeHours);
}
