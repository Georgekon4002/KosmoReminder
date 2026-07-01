using KosmoSMS.CallbackReceiver.Services;
using Serilog;

// ============================================================================
// KosmoSMS Callback Receiver — Program Entry Point
// ============================================================================
// This ASP.NET Core Web API receives delivery status callbacks from easysms.gr.
//
// Endpoint: GET/POST /api/sms-callback
// Parameters: msgid, status, cost, to, mcc, mnc (query string)
//
// For local testing with ngrok:
//   1. dotnet run
//   2. ngrok http 5000
//   3. Set the ngrok URL as callback_url in ReminderService config
// ============================================================================

var builder = WebApplication.CreateBuilder(args);

// -------------------------------------------------------
// Serilog configuration
// -------------------------------------------------------
builder.Host.UseSerilog((context, config) =>
    config.ReadFrom.Configuration(context.Configuration));

// -------------------------------------------------------
// Services
// -------------------------------------------------------
builder.Services.AddControllers();

// Register the notification repository
builder.Services.AddScoped<INotificationRepository, NotificationRepository>();

// Add basic health check endpoint
builder.Services.AddHealthChecks();

var app = builder.Build();

// -------------------------------------------------------
// Middleware pipeline
// -------------------------------------------------------

// Request logging via Serilog
app.UseSerilogRequestLogging();

// Map controller routes
app.MapControllers();

// Health check endpoint for monitoring
app.MapHealthChecks("/health");

// Startup info
app.Logger.LogInformation("KosmoSMS Callback Receiver starting on {Urls}", string.Join(", ", app.Urls));

app.Run();
