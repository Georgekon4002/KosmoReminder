using KosmoSMS.ReminderService.Models;
using KosmoSMS.ReminderService.Services;
using Microsoft.Extensions.Options;

namespace KosmoSMS.ReminderService.Workers;

/// <summary>
/// Background worker that periodically checks for appointments due for
/// reminder and sends Viber/SMS notifications via easysms.gr.
///
/// Flow for each appointment:
/// 1. Validate phone number via api/mobile/check
/// 2. Attempt Viber send (if patient prefers it or no preference set)
/// 3. Fall back to SMS if Viber fails or patient prefers SMS
/// 4. Log the notification result to the database
/// </summary>
public class ReminderWorker : BackgroundService
{
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly ILogger<ReminderWorker> _logger;
    private readonly ReminderConfig _reminderConfig;
    private readonly EasySmsConfig _easySmsConfig;

    public ReminderWorker(
        IServiceScopeFactory scopeFactory,
        ILogger<ReminderWorker> logger,
        IOptions<ReminderConfig> reminderConfig,
        IOptions<EasySmsConfig> easySmsConfig)
    {
        _scopeFactory = scopeFactory;
        _logger = logger;
        _reminderConfig = reminderConfig.Value;
        _easySmsConfig = easySmsConfig.Value;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation(
            "ReminderWorker started. Interval={IntervalMin}min, LeadTime={LeadHours}h",
            _reminderConfig.IntervalMinutes,
            _reminderConfig.LeadTimeHours);

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await ProcessRemindersAsync(stoppingToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unhandled error in reminder processing loop");
            }

            await Task.Delay(TimeSpan.FromMinutes(_reminderConfig.IntervalMinutes), stoppingToken);
        }

        _logger.LogInformation("ReminderWorker is stopping.");
    }

    private async Task ProcessRemindersAsync(CancellationToken ct)
    {
        // Create a new scope for each cycle (Dapper connections are short-lived)
        using var scope = _scopeFactory.CreateScope();
        var appointmentRepo = scope.ServiceProvider.GetRequiredService<IAppointmentRepository>();
        var notificationRepo = scope.ServiceProvider.GetRequiredService<INotificationRepository>();
        var smsClient = scope.ServiceProvider.GetRequiredService<IEasySmsClient>();

        var dueAppointments = await appointmentRepo.GetDueAppointmentsAsync(_reminderConfig.LeadTimeHours);
        var appointments = dueAppointments.ToList();

        if (appointments.Count == 0)
        {
            _logger.LogDebug("No appointments due for reminder.");
            return;
        }

        _logger.LogInformation("Processing {Count} appointments for reminders", appointments.Count);

        foreach (var appointment in appointments)
        {
            if (ct.IsCancellationRequested) break;

            try
            {
                await SendReminderForAppointmentAsync(appointment, smsClient, notificationRepo);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex,
                    "Failed to send reminder for appointment {AppointmentID} (patient: {PatientName})",
                    appointment.AppointmentID, appointment.PatientFullName);
            }
        }
    }

    private async Task SendReminderForAppointmentAsync(
        AppointmentReminder appointment,
        IEasySmsClient smsClient,
        INotificationRepository notificationRepo)
    {
        var phone = appointment.Phone!.Trim();

        _logger.LogInformation(
            "Processing reminder for appointment {AppointmentID}: {PatientName}, {ExamType} at {DateTime}",
            appointment.AppointmentID, appointment.PatientFullName,
            appointment.ExamType, appointment.AppointmentDateTime);

        // -------------------------------------------------------
        // Step 1: Validate the phone number
        // -------------------------------------------------------
        var checkResult = await smsClient.CheckMobileAsync(phone);

        if (checkResult == null || !checkResult.IsMobile)
        {
            _logger.LogWarning(
                "Phone number {Phone} for patient {PatientName} is not a valid mobile number (type={Type}). Skipping.",
                phone, appointment.PatientFullName, checkResult?.Type ?? "unknown");

            // Log a failed notification so we don't retry immediately
            await notificationRepo.InsertNotificationAsync(
                appointment.AppointmentID,
                messageId: null,
                channelUsed: "None",
                status: "Failed");
            return;
        }

        // Use normalized number if available
        var normalizedPhone = checkResult.Number ?? phone;

        // -------------------------------------------------------
        // Step 2: Build the message from template
        // -------------------------------------------------------
        var message = BuildMessage(appointment);

        // -------------------------------------------------------
        // Step 3: Try Viber first (unless patient prefers SMS)
        // -------------------------------------------------------
        var preferSmsOnly = string.Equals(appointment.PreferredChannel, "SMS", StringComparison.OrdinalIgnoreCase);

        if (!preferSmsOnly)
        {
            var viberResult = await smsClient.SendViberAsync(
                normalizedPhone, message, _easySmsConfig.ViberSenderId);

            if (viberResult?.IsSuccess == true)
            {
                await notificationRepo.InsertNotificationAsync(
                    appointment.AppointmentID,
                    viberResult.MessageId,
                    channelUsed: "Viber",
                    status: "Sent");

                _logger.LogInformation(
                    "Viber reminder sent for appointment {AppointmentID}, msgid={MsgId}",
                    appointment.AppointmentID, viberResult.MessageId);
                return; // Success — no need to fall back
            }

            _logger.LogWarning(
                "Viber send failed for appointment {AppointmentID}. Falling back to SMS.",
                appointment.AppointmentID);
        }

        // -------------------------------------------------------
        // Step 4: Fallback to SMS
        // -------------------------------------------------------
        var smsResult = await smsClient.SendSmsAsync(
            normalizedPhone, message, _easySmsConfig.SmsSenderId);

        if (smsResult?.IsSuccess == true)
        {
            await notificationRepo.InsertNotificationAsync(
                appointment.AppointmentID,
                smsResult.MessageId,
                channelUsed: "SMS",
                status: "Sent");

            _logger.LogInformation(
                "SMS reminder sent for appointment {AppointmentID}, msgid={MsgId}",
                appointment.AppointmentID, smsResult.MessageId);
        }
        else
        {
            // Both channels failed
            await notificationRepo.InsertNotificationAsync(
                appointment.AppointmentID,
                messageId: null,
                channelUsed: "SMS",
                status: "Failed");

            _logger.LogError(
                "All channels failed for appointment {AppointmentID} (patient: {PatientName})",
                appointment.AppointmentID, appointment.PatientFullName);
        }
    }

    /// <summary>
    /// Builds the reminder message by replacing placeholders in the template.
    /// </summary>
    private string BuildMessage(AppointmentReminder appointment)
    {
        var message = _reminderConfig.MessageTemplate;

        // Format the date/time in Greek-friendly format
        var formattedDateTime = appointment.AppointmentDateTime.ToString("dd/MM/yyyy HH:mm");

        message = message
            .Replace("{PatientName}", appointment.PatientFullName)
            .Replace("{ExamType}", appointment.ExamType ?? "εξέταση")
            .Replace("{DateTime}", formattedDateTime)
            .Replace("{LabName}", appointment.LabName ?? "το εργαστήριο")
            .Replace("{DoctorName}", !string.IsNullOrWhiteSpace(appointment.DoctorFullName)
                ? appointment.DoctorFullName
                : "τον ιατρό σας");

        return message;
    }
}
