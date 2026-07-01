# KosmoSMS — Appointment Reminder System

SMS/Viber reminder system for **Kosmoiatriki** diagnostic center. Syncs appointments from **Infomed Slis** and sends automated reminders via the **easysms.gr** API.

---

## Architecture Overview

```
┌──────────────────────┐       ┌─────────────────────────────┐
│  Infomed Slis DB     │       │  KosmoSMS DB (own)          │
│  (MS SQL Server)     │       │  (MS SQL Server)            │
│                      │       │                             │
│  Appointments table  │──────▶│  Appointments, Patients,    │
│  (Change Tracking)   │ Sync  │  Doctors, Labs,             │
│                      │ (SP)  │  Notifications, SyncState   │
└──────────────────────┘       └─────────────┬───────────────┘
                                             │
                                ┌────────────┴────────────┐
                                │                         │
                        ┌───────▼───────┐         ┌───────▼───────┐
                        │ ReminderSvc   │         │ CallbackRcvr  │
                        │ (.NET Worker) │         │ (ASP.NET API) │
                        │               │         │               │
                        │ Checks due    │         │ GET/POST      │
                        │ appointments  │         │ /api/sms-     │
                        │ & sends msgs  │         │  callback     │
                        └───────┬───────┘         └───────▲───────┘
                                │                         │
                                ▼                         │
                        ┌───────────────┐                 │
                        │ easysms.gr    │─────────────────┘
                        │ API           │   delivery report
                        │ (Viber + SMS) │   callback
                        └───────────────┘
```

See the `puml/` folder for detailed PlantUML diagrams.

---

## Prerequisites

- **SQL Server** 2016+ (or SQL Server Express) — for the KosmoSMS database
- **.NET 8 SDK** (or later) — [download](https://dotnet.microsoft.com/download)
- **ngrok** — for local webhook testing — [download](https://ngrok.com/download)
- **easysms.gr account** — [register](https://easysms.gr)

---

## Quick Start

### 1. Create the Database

Run the SQL scripts in order on your SQL Server instance:

```bash
# Connect to your SQL Server (e.g., via sqlcmd or SSMS) and run:
sql/001_CreateDatabase.sql    # Creates DB + tables + indexes + seed data
sql/002_LinkedServerSetup.sql # Template for Slis linked server (edit placeholders!)
sql/003_SyncStoredProcedure.sql # Change Tracking sync stored procedure
```

> **Important:** Before running `002_LinkedServerSetup.sql`, replace ALL `<<...>>` placeholders with your actual Slis server name, credentials, and table names.

### 2. Configure the Reminder Service

Edit `src/ReminderService/appsettings.json` (or create `appsettings.Development.json` for local dev):

```json
{
  "ConnectionStrings": {
    "KosmoSMS": "Server=YOUR_SERVER;Database=KosmoSMS;User Id=YOUR_USER;Password=YOUR_PASSWORD;TrustServerCertificate=True;"
  },
  "EasySms": {
    "BaseUrl": "https://easysms.gr/api",
    "ApiKey": "YOUR_API_KEY_HERE",
    "ViberSenderId": "Kosmoiatriki",
    "SmsSenderId": "Kosmoiatriki",
    "CallbackUrl": "https://YOUR_NGROK_URL/api/sms-callback"
  },
  "Reminder": {
    "LeadTimeHours": 24,
    "IntervalMinutes": 15,
    "MessageTemplate": "Αγαπητέ/ή {PatientName}, σας υπενθυμίζουμε..."
  }
}
```

### 3. Configure the Callback Receiver

Edit `src/CallbackReceiver/appsettings.json`:

```json
{
  "ConnectionStrings": {
    "KosmoSMS": "Server=YOUR_SERVER;Database=KosmoSMS;User Id=YOUR_USER;Password=YOUR_PASSWORD;TrustServerCertificate=True;"
  }
}
```

### 4. Run Locally

```bash
# Terminal 1: Start the Callback Receiver
cd src/CallbackReceiver
dotnet run

# Terminal 2: Expose it via ngrok (so easysms.gr can reach your callback)
ngrok http 5000

# Terminal 3: Start the Reminder Service
cd src/ReminderService
dotnet run
```

Copy the ngrok URL (e.g., `https://abc123.ngrok-free.app`) and set it as the `CallbackUrl` in the ReminderService config:
```
"CallbackUrl": "https://abc123.ngrok-free.app/api/sms-callback"
```

### 5. Test the Webhook

You can simulate an easysms.gr callback using curl:

```bash
curl "http://localhost:5000/api/sms-callback?msgid=TEST123&status=delivered&cost=0.025&to=306912345678&mcc=202&mnc=01"
```

Expected response:
```json
{ "status": "ignored", "reason": "No pending notification found for this msgid." }
```

---

## Project Structure

```
kosmosms/
├── sql/
│   ├── 001_CreateDatabase.sql          # DB schema (6 tables)
│   ├── 002_LinkedServerSetup.sql       # Linked server template
│   └── 003_SyncStoredProcedure.sql     # Sync SP + Agent job template
├── src/
│   ├── KosmoSMS.slnx                   # Solution file
│   ├── ReminderService/                # .NET Worker Service
│   │   ├── Models/
│   │   ├── Services/
│   │   ├── Workers/
│   │   ├── Program.cs
│   │   └── appsettings.json
│   └── CallbackReceiver/              # ASP.NET Core Web API
│       ├── Controllers/
│       ├── Models/
│       ├── Services/
│       ├── Program.cs
│       └── appsettings.json
├── puml/                              # Architecture diagrams
├── README.md
└── .gitignore
```

---

## Database Schema

| Table          | Purpose                                              |
|----------------|------------------------------------------------------|
| `Patients`     | Patient contact information (phone, email, channel preference) |
| `Doctors`      | Doctor details (name, expertise)                     |
| `Labs`         | Lab/location information                             |
| `Appointments` | Synced from Slis; links to Patient, Doctor, Lab      |
| `Notifications`| Message send/delivery tracking (msgid, status, cost) |
| `SyncState`    | Tracks last Change Tracking version per table        |
| `SyncLog`      | Audit log of every sync run                          |

---

## Configuration Reference

### Connection Strings

Both projects need a `KosmoSMS` connection string pointing to your database.

For **Windows Authentication** (local dev):
```
Server=localhost;Database=KosmoSMS;Integrated Security=True;TrustServerCertificate=True;
```

For **SQL Authentication** (production):
```
Server=YOUR_SERVER;Database=KosmoSMS;User Id=YOUR_USER;Password=YOUR_PASSWORD;TrustServerCertificate=True;Encrypt=True;
```

### EasySms Settings

| Setting          | Description                                              |
|------------------|----------------------------------------------------------|
| `BaseUrl`        | API base URL (default: `https://easysms.gr/api`)         |
| `ApiKey`         | Your easysms.gr API key (from dashboard)                 |
| `ViberSenderId`  | Approved Viber sender name (register with easysms.gr)    |
| `SmsSenderId`    | SMS alphanumeric originator                              |
| `CallbackUrl`    | Public URL where easysms.gr sends delivery reports       |

### Reminder Settings

| Setting           | Description                              | Default |
|-------------------|------------------------------------------|---------|
| `LeadTimeHours`   | Hours before appointment to send reminder| 24      |
| `IntervalMinutes` | How often to check for due reminders     | 15      |
| `MessageTemplate` | Message with `{PatientName}`, `{ExamType}`, `{DateTime}`, `{LabName}`, `{DoctorName}` placeholders | Greek template |

---

## Secrets Management

> **Never commit secrets to git!** The `.gitignore` file excludes `appsettings.Development.json`.

For production, consider:
- **Environment variables**: `ConnectionStrings__KosmoSMS=...`
- **Azure Key Vault** or **Windows DPAPI**
- **User Secrets** for development: `dotnet user-secrets set "EasySms:ApiKey" "your-key"`

---

## Deployment

### ReminderService as a Windows Service

```bash
dotnet publish src/ReminderService -c Release -o C:\Services\KosmoSMS-ReminderService

sc create "KosmoSMS-ReminderService" binPath="C:\Services\KosmoSMS-ReminderService\KosmoSMS.ReminderService.exe"
sc start "KosmoSMS-ReminderService"
```

### CallbackReceiver on IIS or as a Service

For IIS: publish and configure as a standard ASP.NET Core site.

For a Windows Service:
```bash
dotnet publish src/CallbackReceiver -c Release -o C:\Services\KosmoSMS-CallbackReceiver

sc create "KosmoSMS-CallbackReceiver" binPath="C:\Services\KosmoSMS-CallbackReceiver\KosmoSMS.CallbackReceiver.exe"
sc start "KosmoSMS-CallbackReceiver"
```

### SQL Server Agent Job

Schedule the sync stored procedure via SQL Server Agent (see the template at the bottom of `sql/003_SyncStoredProcedure.sql`).

---

## Sync Flow

1. **SQL Server Agent** triggers `usp_SyncAppointmentsFromSlis` every 5–15 minutes
2. The SP reads `LastChangeVersion` from `SyncState`
3. Queries `CHANGETABLE(CHANGES ...)` via the Linked Server
4. `MERGE`s changed rows into `Appointments`
5. Updates `SyncState` and logs to `SyncLog`

## Reminder Flow

1. **ReminderWorker** runs every 15 minutes (configurable)
2. Queries for appointments within the reminder window (24h default)
3. For each appointment:
   - Validates phone via `api/mobile/check`
   - Attempts **Viber** send (unless patient prefers SMS)
   - Falls back to **SMS** if Viber fails
   - Logs result to `Notifications` table
4. **easysms.gr** sends a delivery callback to the **CallbackReceiver**
5. The callback updates the `Notifications` table with final status, cost, and carrier info

---

## License

Private — Kosmoiatriki internal use.
