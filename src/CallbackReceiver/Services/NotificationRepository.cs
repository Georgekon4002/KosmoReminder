using Dapper;
using Microsoft.Data.SqlClient;

namespace KosmoSMS.CallbackReceiver.Services;

/// <summary>
/// Dapper-based implementation for updating notification delivery statuses
/// from easysms.gr webhook callbacks.
/// </summary>
public class NotificationRepository : INotificationRepository
{
    private readonly string _connectionString;
    private readonly ILogger<NotificationRepository> _logger;

    public NotificationRepository(IConfiguration configuration, ILogger<NotificationRepository> logger)
    {
        _connectionString = configuration.GetConnectionString("KosmoSMS")
            ?? throw new InvalidOperationException("Connection string 'KosmoSMS' is not configured.");
        _logger = logger;
    }

    /// <inheritdoc />
    public async Task<bool> ExistsPendingAsync(string messageId)
    {
        const string sql = @"
            SELECT CASE WHEN EXISTS (
                SELECT 1 FROM dbo.Notifications
                WHERE MessageID = @MessageID
                  AND Status IN ('Pending', 'Sent')
            ) THEN 1 ELSE 0 END;";

        try
        {
            await using var connection = new SqlConnection(_connectionString);
            return await connection.ExecuteScalarAsync<bool>(sql, new { MessageID = messageId });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error checking pending notification for msgid={MsgId}", messageId);
            throw;
        }
    }

    /// <inheritdoc />
    public async Task<bool> UpdateDeliveryStatusAsync(
        string messageId,
        string status,
        decimal? cost,
        string? mcc,
        string? mnc)
    {
        // Map easysms.gr status strings to our internal status values
        var internalStatus = MapStatus(status);

        const string sql = @"
            UPDATE dbo.Notifications
            SET Status      = @Status,
                DeliveredAt = CASE WHEN @Status = 'Delivered' THEN SYSUTCDATETIME() ELSE DeliveredAt END,
                Cost        = COALESCE(@Cost, Cost),
                MCC         = COALESCE(@MCC, MCC),
                MNC         = COALESCE(@MNC, MNC)
            WHERE MessageID = @MessageID
              AND Status IN ('Pending', 'Sent');";

        try
        {
            await using var connection = new SqlConnection(_connectionString);
            var rowsAffected = await connection.ExecuteAsync(sql, new
            {
                MessageID = messageId,
                Status = internalStatus,
                Cost = cost,
                MCC = mcc,
                MNC = mnc
            });

            if (rowsAffected > 0)
            {
                _logger.LogInformation(
                    "Notification updated: msgid={MsgId}, status={Status}, cost={Cost}",
                    messageId, internalStatus, cost);
                return true;
            }
            else
            {
                _logger.LogWarning(
                    "No pending notification found for msgid={MsgId} (may already be updated)",
                    messageId);
                return false;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error updating notification status for msgid={MsgId}", messageId);
            throw;
        }
    }

    /// <summary>
    /// Maps easysms.gr status strings to our internal notification statuses.
    /// </summary>
    private static string MapStatus(string externalStatus)
    {
        return externalStatus.ToLowerInvariant() switch
        {
            "delivered" => "Delivered",
            "failed"    => "Failed",
            "rejected"  => "Rejected",
            "expired"   => "Failed",
            "sent"      => "Sent",
            _           => externalStatus  // Pass through unknown statuses
        };
    }
}
