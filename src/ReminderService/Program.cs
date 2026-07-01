using KosmoSMS.ReminderService.Models;
using KosmoSMS.ReminderService.Services;
using KosmoSMS.ReminderService.Workers;
using Serilog;

// ============================================================================
// KosmoSMS Reminder Service — Program Entry Point
// ============================================================================
// This is a .NET 8 Worker Service that:
// 1. Periodically queries the KosmoSMS database for due appointments
// 2. Sends Viber/SMS reminders via the easysms.gr API
// 3. Logs notification results back to the database
//
// To run as a Windows Service, use:
//   dotnet publish -c Release
//   sc create KosmoSMS-ReminderService binPath="path\to\KosmoSMS.ReminderService.exe"
// ============================================================================

var builder = Host.CreateApplicationBuilder(args);

// -------------------------------------------------------
// Serilog configuration
// -------------------------------------------------------
builder.Services.AddSerilog(config =>
    config.ReadFrom.Configuration(builder.Configuration));

// -------------------------------------------------------
// Options binding
// -------------------------------------------------------
builder.Services.Configure<EasySmsConfig>(
    builder.Configuration.GetSection(EasySmsConfig.SectionName));

builder.Services.Configure<ReminderConfig>(
    builder.Configuration.GetSection(ReminderConfig.SectionName));

// -------------------------------------------------------
// HttpClient for easysms.gr API
// -------------------------------------------------------
builder.Services.AddHttpClient<IEasySmsClient, EasySmsClient>(client =>
{
    client.Timeout = TimeSpan.FromSeconds(30);
    client.DefaultRequestHeaders.Add("Accept", "application/json");
});

// -------------------------------------------------------
// Repositories (scoped — new instance per reminder cycle)
// -------------------------------------------------------
builder.Services.AddScoped<IAppointmentRepository, AppointmentRepository>();
builder.Services.AddScoped<INotificationRepository, NotificationRepository>();

// -------------------------------------------------------
// The background worker
// -------------------------------------------------------
builder.Services.AddHostedService<ReminderWorker>();

// -------------------------------------------------------
// Windows Service support (optional, for deployment as a service)
// -------------------------------------------------------
builder.Services.AddWindowsService(options =>
{
    options.ServiceName = "KosmoSMS Reminder Service";
});

var host = builder.Build();

Log.Information("KosmoSMS Reminder Service starting...");

try
{
    host.Run();
}
catch (Exception ex)
{
    Log.Fatal(ex, "KosmoSMS Reminder Service terminated unexpectedly");
}
finally
{
    Log.CloseAndFlush();
}
