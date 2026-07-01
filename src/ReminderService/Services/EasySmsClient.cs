using System.Net.Http.Json;
using System.Web;
using KosmoSMS.ReminderService.Models;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace KosmoSMS.ReminderService.Services;

/// <summary>
/// HttpClient-based implementation of the easysms.gr API client.
/// Uses IHttpClientFactory for proper connection management.
/// </summary>
public class EasySmsClient : IEasySmsClient
{
    private readonly HttpClient _httpClient;
    private readonly EasySmsConfig _config;
    private readonly ILogger<EasySmsClient> _logger;

    public EasySmsClient(HttpClient httpClient, IOptions<EasySmsConfig> config, ILogger<EasySmsClient> logger)
    {
        _httpClient = httpClient;
        _config = config.Value;
        _logger = logger;

        // Set base address from config
        if (!string.IsNullOrWhiteSpace(_config.BaseUrl))
        {
            _httpClient.BaseAddress = new Uri(_config.BaseUrl.TrimEnd('/') + "/");
        }
    }

    /// <inheritdoc />
    public async Task<MobileCheckResponse?> CheckMobileAsync(string phoneNumber)
    {
        try
        {
            // api/mobile/check does NOT require an API key
            var encodedPhone = HttpUtility.UrlEncode(phoneNumber);
            var requestUri = $"mobile/check?number={encodedPhone}";

            _logger.LogDebug("Checking mobile number: {Phone}", phoneNumber);

            var response = await _httpClient.GetAsync(requestUri);
            response.EnsureSuccessStatusCode();

            var result = await response.Content.ReadFromJsonAsync<MobileCheckResponse>();
            _logger.LogDebug("Mobile check result for {Phone}: Type={Type}", phoneNumber, result?.Type);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error checking mobile number {Phone}", phoneNumber);
            return null;
        }
    }

    /// <inheritdoc />
    public async Task<SendMessageResponse?> SendViberAsync(string to, string message, string senderId)
    {
        try
        {
            _logger.LogInformation("Sending Viber message to {To} via sender {Sender}", to, senderId);

            var parameters = new Dictionary<string, string>
            {
                ["key"] = _config.ApiKey,
                ["to"] = to,
                ["text"] = message,
                ["from"] = senderId,
                ["callback_url"] = _config.CallbackUrl
            };

            var content = new FormUrlEncodedContent(parameters);
            var response = await _httpClient.PostAsync("viber/send", content);
            response.EnsureSuccessStatusCode();

            var result = await response.Content.ReadFromJsonAsync<SendMessageResponse>();

            if (result?.IsSuccess == true)
            {
                _logger.LogInformation("Viber message sent to {To}, msgid={MsgId}", to, result.MessageId);
            }
            else
            {
                _logger.LogWarning("Viber send failed for {To}: {Error}", to, result?.Error ?? "Unknown error");
            }

            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error sending Viber message to {To}", to);
            return null;
        }
    }

    /// <inheritdoc />
    public async Task<SendMessageResponse?> SendSmsAsync(string to, string message, string senderId)
    {
        try
        {
            _logger.LogInformation("Sending SMS to {To} via sender {Sender}", to, senderId);

            var parameters = new Dictionary<string, string>
            {
                ["key"] = _config.ApiKey,
                ["to"] = to,
                ["text"] = message,
                ["from"] = senderId,
                ["callback_url"] = _config.CallbackUrl
            };

            var content = new FormUrlEncodedContent(parameters);
            var response = await _httpClient.PostAsync("sms/send", content);
            response.EnsureSuccessStatusCode();

            var result = await response.Content.ReadFromJsonAsync<SendMessageResponse>();

            if (result?.IsSuccess == true)
            {
                _logger.LogInformation("SMS sent to {To}, msgid={MsgId}", to, result.MessageId);
            }
            else
            {
                _logger.LogWarning("SMS send failed for {To}: {Error}", to, result?.Error ?? "Unknown error");
            }

            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error sending SMS to {To}", to);
            return null;
        }
    }
}
