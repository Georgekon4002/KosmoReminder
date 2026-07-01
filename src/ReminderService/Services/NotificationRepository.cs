using Dapper;
using Microsoft.Data.SqlClient;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;

namespace KosmoSMS.ReminderService.Services;

/// <summary>
/// Dapper-based implementation for writing notification records.
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
    public async Task<int> InsertNotificationAsync(int appointmentId, string? messageId, string channelUsed, string status)
    {
        const string sql = @"
            INSERT INTO dbo.Notifications
                (AppointmentID, MessageID, ChannelUsed, SentAt, Status)
            OUTPUT INSERTED.NotificationID
            VALUES
                (@AppointmentID, @MessageID, @ChannelUsed, SYSUTCDATETIME(), @Status);";

        try
        {
            await using var connection = new SqlConnection(_connectionString);
            var notificationId = await connection.ExecuteScalarAsync<int>(sql, new
            {
                AppointmentID = appointmentId,
                MessageID = messageId,
                ChannelUsed = channelUsed,
                Status = status
            });

            _logger.LogInformation(
                "Notification {NotificationID} created for appointment {AppointmentID} via {Channel} — status: {Status}",
                notificationId, appointmentId, channelUsed, status);

            return notificationId;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error inserting notification for appointment {AppointmentID}", appointmentId);
            throw;
        }
    }
}
