using KosmoSMS.ReminderService.Models;

namespace KosmoSMS.ReminderService.Services;

/// <summary>
/// Client for the easysms.gr REST API.
/// Handles number validation, Viber sending, and SMS sending.
/// </summary>
public interface IEasySmsClient
{
    /// <summary>
    /// Validates a phone number via api/mobile/check.
    /// This endpoint is free and does not require an API key.
    /// </summary>
    Task<MobileCheckResponse?> CheckMobileAsync(string phoneNumber);

    /// <summary>
    /// Sends a Viber message via api/viber/send.
    /// </summary>
    /// <param name="to">Recipient phone number (international format).</param>
    /// <param name="message">Message text (up to 1000 chars for Viber).</param>
    /// <param name="senderId">Viber Sender ID (must be pre-approved).</param>
    /// <returns>Send response with msgid on success.</returns>
    Task<SendMessageResponse?> SendViberAsync(string to, string message, string senderId);

    /// <summary>
    /// Sends an SMS via api/sms/send.
    /// </summary>
    /// <param name="to">Recipient phone number (international format).</param>
    /// <param name="message">Message text.</param>
    /// <param name="senderId">SMS originator / Sender ID.</param>
    /// <returns>Send response with msgid on success.</returns>
    Task<SendMessageResponse?> SendSmsAsync(string to, string message, string senderId);
}
