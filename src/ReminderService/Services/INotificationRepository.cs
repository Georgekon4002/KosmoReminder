namespace KosmoSMS.ReminderService.Services;

/// <summary>
/// Writes notification records to the KosmoSMS database.
/// </summary>
public interface INotificationRepository
{
    /// <summary>
    /// Inserts a new notification record with status 'Pending' or 'Sent'.
    /// </summary>
    /// <param name="appointmentId">The appointment this notification is for.</param>
    /// <param name="messageId">The msgid returned by easysms.gr (may be null on failure).</param>
    /// <param name="channelUsed">"Viber" or "SMS".</param>
    /// <param name="status">Initial status: "Sent" if accepted, "Failed" if rejected.</param>
    /// <returns>The newly created NotificationID.</returns>
    Task<int> InsertNotificationAsync(int appointmentId, string? messageId, string channelUsed, string status);
}
