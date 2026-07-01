using System.Globalization;
using KosmoSMS.CallbackReceiver.Models;
using KosmoSMS.CallbackReceiver.Services;
using Microsoft.AspNetCore.Mvc;

namespace KosmoSMS.CallbackReceiver.Controllers;

/// <summary>
/// Webhook endpoint for receiving delivery status callbacks from easysms.gr.
///
/// easysms.gr calls this endpoint in real time when a message is delivered or fails.
/// It sends the following query string parameters:
///   - msgid:  unique message identifier
///   - status: delivery status (delivered, failed, rejected, expired)
///   - cost:   message cost
///   - to:     recipient number
///   - mcc:    mobile country code
///   - mnc:    mobile network code
/// </summary>
[ApiController]
[Route("api/sms-callback")]
public class SmsCallbackController : ControllerBase
{
    private readonly INotificationRepository _notificationRepo;
    private readonly ILogger<SmsCallbackController> _logger;

    public SmsCallbackController(
        INotificationRepository notificationRepo,
        ILogger<SmsCallbackController> logger)
    {
        _notificationRepo = notificationRepo;
        _logger = logger;
    }

    /// <summary>
    /// Handles GET callbacks from easysms.gr.
    /// Parameters are passed via query string.
    /// </summary>
    [HttpGet]
    public async Task<IActionResult> HandleGetCallback([FromQuery] CallbackRequest request)
    {
        return await ProcessCallbackAsync(request, "GET");
    }

    /// <summary>
    /// Handles POST callbacks from easysms.gr.
    /// Parameters may come via query string or form body.
    /// </summary>
    [HttpPost]
    public async Task<IActionResult> HandlePostCallback([FromQuery] CallbackRequest request)
    {
        return await ProcessCallbackAsync(request, "POST");
    }

    /// <summary>
    /// Shared processing logic for both GET and POST callbacks.
    /// </summary>
    private async Task<IActionResult> ProcessCallbackAsync(CallbackRequest request, string httpMethod)
    {
        // -------------------------------------------------------
        // 1. Log the raw callback for debugging/audit
        // -------------------------------------------------------
        _logger.LogInformation(
            "Callback received [{Method}]: msgid={MsgId}, status={Status}, cost={Cost}, to={To}, mcc={MCC}, mnc={MNC}",
            httpMethod, request.MsgId, request.Status, request.Cost, request.To, request.MCC, request.MNC);

        // -------------------------------------------------------
        // 2. Validate required parameters
        // -------------------------------------------------------
        if (!request.IsValid)
        {
            _logger.LogWarning("Invalid callback: missing required parameters (msgid or status)");
            return BadRequest(new { error = "Missing required parameters: msgid and status are required." });
        }

        // -------------------------------------------------------
        // 3. Check if we have a pending notification with this msgid
        // -------------------------------------------------------
        try
        {
            var exists = await _notificationRepo.ExistsPendingAsync(request.MsgId!);

            if (!exists)
            {
                _logger.LogWarning(
                    "No pending notification found for msgid={MsgId}. Possibly already processed or unknown.",
                    request.MsgId);

                // Return 200 anyway to prevent easysms.gr from retrying
                // (we don't want to reject callbacks for already-processed messages)
                return Ok(new { status = "ignored", reason = "No pending notification found for this msgid." });
            }

            // -------------------------------------------------------
            // 4. Parse cost (may be null or a string like "0.0250")
            // -------------------------------------------------------
            decimal? cost = null;
            if (!string.IsNullOrWhiteSpace(request.Cost) &&
                decimal.TryParse(request.Cost, NumberStyles.Any, CultureInfo.InvariantCulture, out var parsedCost))
            {
                cost = parsedCost;
            }

            // -------------------------------------------------------
            // 5. Update the notification record
            // -------------------------------------------------------
            var updated = await _notificationRepo.UpdateDeliveryStatusAsync(
                request.MsgId!,
                request.Status!,
                cost,
                request.MCC,
                request.MNC);

            if (updated)
            {
                _logger.LogInformation("Successfully processed callback for msgid={MsgId}", request.MsgId);
                return Ok(new { status = "ok", msgid = request.MsgId });
            }
            else
            {
                // Race condition: another callback already updated it
                _logger.LogWarning("Notification msgid={MsgId} was already updated (race condition)", request.MsgId);
                return Ok(new { status = "already_processed", msgid = request.MsgId });
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing callback for msgid={MsgId}", request.MsgId);
            return StatusCode(500, new { error = "Internal server error processing callback." });
        }
    }
}
