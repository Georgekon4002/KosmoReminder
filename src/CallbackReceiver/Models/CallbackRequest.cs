using Microsoft.AspNetCore.Mvc;

namespace KosmoSMS.CallbackReceiver.Models;

/// <summary>
/// Represents the delivery report callback parameters sent by easysms.gr.
/// easysms.gr sends these as query string parameters via GET or POST.
/// </summary>
public class CallbackRequest
{
    /// <summary>
    /// The unique message ID assigned when the message was sent.
    /// </summary>
    [FromQuery(Name = "msgid")]
    public string? MsgId { get; set; }

    /// <summary>
    /// Delivery status (e.g., "delivered", "failed", "rejected", "expired").
    /// </summary>
    [FromQuery(Name = "status")]
    public string? Status { get; set; }

    /// <summary>
    /// Cost of the message in EUR.
    /// </summary>
    [FromQuery(Name = "cost")]
    public string? Cost { get; set; }

    /// <summary>
    /// The recipient phone number.
    /// </summary>
    [FromQuery(Name = "to")]
    public string? To { get; set; }

    /// <summary>
    /// Mobile Country Code (e.g., "202" for Greece).
    /// </summary>
    [FromQuery(Name = "mcc")]
    public string? MCC { get; set; }

    /// <summary>
    /// Mobile Network Code (e.g., "01" for Cosmote, "10" for Wind, "05" for Vodafone).
    /// </summary>
    [FromQuery(Name = "mnc")]
    public string? MNC { get; set; }

    /// <summary>
    /// Validates that the minimum required fields are present.
    /// </summary>
    public bool IsValid => !string.IsNullOrWhiteSpace(MsgId) && !string.IsNullOrWhiteSpace(Status);
}
