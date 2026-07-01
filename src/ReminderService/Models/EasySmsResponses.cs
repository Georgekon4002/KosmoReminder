using System.Text.Json.Serialization;

namespace KosmoSMS.ReminderService.Models;

/// <summary>
/// Response from api/mobile/check — validates a phone number.
/// </summary>
public class MobileCheckResponse
{
    /// <summary>
    /// The status of the check (e.g., "ok", "error").
    /// </summary>
    [JsonPropertyName("status")]
    public string? Status { get; set; }

    /// <summary>
    /// The formatted/normalized phone number.
    /// </summary>
    [JsonPropertyName("number")]
    public string? Number { get; set; }

    /// <summary>
    /// The type of number: "mobile", "landline", "unknown".
    /// </summary>
    [JsonPropertyName("type")]
    public string? Type { get; set; }

    /// <summary>
    /// Whether the number is valid for messaging.
    /// </summary>
    public bool IsMobile => string.Equals(Type, "mobile", StringComparison.OrdinalIgnoreCase);
}

/// <summary>
/// Response from api/viber/send or api/sms/send.
/// </summary>
public class SendMessageResponse
{
    /// <summary>
    /// Status of the send request (e.g., "ok", "error").
    /// </summary>
    [JsonPropertyName("status")]
    public string? Status { get; set; }

    /// <summary>
    /// The unique message ID assigned by easysms.gr.
    /// Used to correlate delivery callbacks.
    /// </summary>
    [JsonPropertyName("msgid")]
    public string? MessageId { get; set; }

    /// <summary>
    /// Error message if the send failed.
    /// </summary>
    [JsonPropertyName("error")]
    public string? Error { get; set; }

    /// <summary>
    /// Whether the send request was accepted.
    /// </summary>
    public bool IsSuccess => string.Equals(Status, "ok", StringComparison.OrdinalIgnoreCase);
}
