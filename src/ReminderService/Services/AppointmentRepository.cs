using Dapper;
using KosmoSMS.ReminderService.Models;
using Microsoft.Data.SqlClient;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;

namespace KosmoSMS.ReminderService.Services;

/// <summary>
/// Dapper-based implementation that queries the KosmoSMS database
/// for appointments due for a reminder.
/// </summary>
public class AppointmentRepository : IAppointmentRepository
{
    private readonly string _connectionString;
    private readonly ILogger<AppointmentRepository> _logger;

    public AppointmentRepository(IConfiguration configuration, ILogger<AppointmentRepository> logger)
    {
        _connectionString = configuration.GetConnectionString("KosmoSMS")
            ?? throw new InvalidOperationException("Connection string 'KosmoSMS' is not configured.");
        _logger = logger;
    }

    /// <inheritdoc />
    public async Task<IEnumerable<AppointmentReminder>> GetDueAppointmentsAsync(int leadTimeHours)
    {
        const string sql = @"
            SELECT
                a.AppointmentID,
                a.SlisAppointmentID,
                a.AppointmentDateTime,
                a.ExamType,
                a.Status,
                -- Patient
                p.PatientID,
                p.FirstName   AS PatientFirstName,
                p.LastName    AS PatientLastName,
                p.Phone,
                p.Email,
                p.PreferredChannel,
                -- Doctor
                d.DocID,
                d.FirstName   AS DoctorFirstName,
                d.LastName    AS DoctorLastName,
                d.Expertise,
                -- Lab
                l.LabID,
                l.LabName,
                l.LabGeoLocation
            FROM dbo.Appointments a
            INNER JOIN dbo.Patients p ON p.PatientID = a.PatientID
            LEFT  JOIN dbo.Doctors  d ON d.DocID     = a.DocID
            LEFT  JOIN dbo.Labs     l ON l.LabID     = a.LabID
            WHERE
                -- Appointment is in the future
                a.AppointmentDateTime > SYSUTCDATETIME()
                -- Appointment is within the reminder window
                AND a.AppointmentDateTime <= DATEADD(HOUR, @LeadTimeHours, SYSUTCDATETIME())
                -- Not cancelled or completed
                AND a.Status NOT IN ('Cancelled', 'Completed')
                -- Patient has a phone number
                AND p.Phone IS NOT NULL
                AND LEN(LTRIM(RTRIM(p.Phone))) > 0
                -- No existing successful notification for this appointment
                AND NOT EXISTS (
                    SELECT 1
                    FROM dbo.Notifications n
                    WHERE n.AppointmentID = a.AppointmentID
                      AND n.Status IN ('Sent', 'Delivered', 'Pending')
                )
            ORDER BY a.AppointmentDateTime;";

        try
        {
            await using var connection = new SqlConnection(_connectionString);
            var results = await connection.QueryAsync<AppointmentReminder>(sql, new { LeadTimeHours = leadTimeHours });
            _logger.LogInformation("Found {Count} appointments due for reminder", results.AsList().Count);
            return results;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error querying due appointments");
            throw;
        }
    }
}
