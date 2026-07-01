namespace KosmoSMS.CallbackReceiver.Services;

/// <summary>
/// Repository for querying and updating notification delivery statuses.
/// </summary>
public interface INotificationRepository
{
    /// <summary>
    /// Checks if a notification with the given message ID exists
    /// and is in a pending/sent state (eligible for status update).
    /// </summary>
    /// <returns>True if the notification exists and can be updated.</returns>
    Task<bool> ExistsPendingAsync(string messageId);

    /// <summary>
    /// Updates the delivery status of a notification identified by its message ID.
    /// </summary>
    Task<bool> UpdateDeliveryStatusAsync(
        string messageId,
        string status,
        decimal? cost,
        string? mcc,
        string? mnc);
}
