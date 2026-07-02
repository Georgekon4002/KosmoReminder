# KosmoSMS — Appointment Reminder System

SMS/Viber reminder system for **Kosmoiatriki** diagnostic center. Syncs appointments from **Infomed Slis** and sends automated reminders via the **easysms.gr** API.

---

## Architecture Overview

```
              ┌─────────────┐
              │  Slis DB    │
              │ (Read-Only) │
              └──────┬──────┘
                     │ SQL Agent job
                     │ (every 5-15 min)
                     ▼
              ┌─────────────┐
              │ KosmoSMS DB │  ◄── Your own MS SQL Server
              │ (6 tables)  │
              └──┬───────┬──┘
                 │       │
     ┌───────────┘       └───────────┐
     │                               │
     ▼                               ▼
┌────────────────┐          ┌────────────────────┐
│reminder_service│          │ callback_receiver   │
│    .py         │          │    .py (Flask)      │
│                │          │                     │
│ Reads due      │          │ GET/POST            │
│ appointments   │          │ /api/sms-callback   │
│ every 15 min   │          │                     │
└───────┬────────┘          └─────────▲───────────┘
        │                             │
        │  HTTP calls                 │ delivery report
        ▼                             │ callback
┌───────────────┐                     │
│ easysms.gr    │─────────────────────┘
│ API           │
│ (Viber + SMS) │
└───────────────┘
```

### Components

| Component | Technology | Description |
|-----------|-----------|-------------|
| **Data Sync** | T-SQL Stored Procedure + SQL Agent | Pulls changed appointments from Slis via Linked Server every 5-15 min |
| **Reminder Service** | `reminder_service.py` (Python) | Checks for due appointments, validates phones, sends Viber/SMS |
| **Callback Receiver** | `callback_receiver.py` (Flask) | Receives delivery reports from easysms.gr, updates Notifications table |

---

## Prerequisites

- **Python 3.10+** — [Download](https://www.python.org/downloads/)
- **Microsoft ODBC Driver for SQL Server** — [Download](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- **MS SQL Server** — Your own instance for the KosmoSMS database
- **easysms.gr account** — [Sign up](https://easysms.gr/app/sign-up)

---

## Project Structure

```
kosmosms/
├── README.md
├── .gitignore
├── sql/
│   ├── 001_CreateDatabase.sql      # Database schema (6 tables)
│   ├── 002_LinkedServerSetup.sql   # Linked Server to Slis
│   └── 003_SyncStoredProcedure.sql # Change Tracking sync SP
├── puml/
│   ├── architecture.puml           # High-level architecture diagram
│   ├── erd.puml                    # Entity-relationship diagram
│   ├── reminder_sequence.puml      # Reminder send flow
│   └── sync_sequence.puml          # Slis sync flow
└── src/
    ├── requirements.txt            # Python dependencies
    ├── .env.example                # Configuration template
    ├── config.py                   # Central config loader
    ├── database.py                 # SQL queries (pyodbc)
    ├── easysms_client.py           # easysms.gr API client
    ├── reminder_service.py         # Background reminder sender
    └── callback_receiver.py        # Flask webhook receiver
```

---

## Quick Start

### 1. Set up the database

Run the SQL scripts on your MS SQL Server in order:

```sql
-- Run in SQL Server Management Studio (SSMS)
-- 1. Create database and tables
sql/001_CreateDatabase.sql

-- 2. Configure Linked Server to Slis (fill in your Slis server details)
sql/002_LinkedServerSetup.sql

-- 3. Create the sync stored procedure and Agent job
sql/003_SyncStoredProcedure.sql
```

### 2. Set up Python

```bash
cd src

# Create a virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure

```bash
# Copy the template and fill in your values
copy .env.example .env      # Windows
# cp .env.example .env      # Linux/macOS
```

Edit `.env` with your actual values:

```ini
DB_CONNECTION_STRING=DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=KosmoSMS;Trusted_Connection=yes;
EASYSMS_API_KEY=your_api_key_here
CALLBACK_URL=https://your-public-domain.com/api/sms-callback
```

### 4. Run

Open **two terminals** (both from the `src/` directory with the venv activated):

**Terminal 1 — Reminder Service:**
```bash
python reminder_service.py
```

**Terminal 2 — Callback Receiver:**
```bash
python callback_receiver.py
```

The callback receiver listens on `http://0.0.0.0:5000` by default.

---

## Configuration Reference

All settings are in `.env` (loaded by `config.py`):

### Database

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_CONNECTION_STRING` | ODBC connection string to KosmoSMS database | `DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=KosmoSMS;Trusted_Connection=yes;` |

### easysms.gr API

| Variable | Description | Default |
|----------|-------------|---------|
| `EASYSMS_API_KEY` | API key from easysms.gr dashboard | *(empty)* |
| `EASYSMS_BASE_URL` | Base URL for the API | `https://easysms.gr/api` |
| `VIBER_SENDER_ID` | Approved Viber sender ID | `Kosmoiatriki` |
| `SMS_SENDER_ID` | SMS alphanumeric originator | `Kosmoiatriki` |
| `CALLBACK_URL` | Public URL for delivery reports | *(empty)* |

### Reminder Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `LEAD_TIME_HOURS` | Hours before appointment to send reminder | `24` |
| `INTERVAL_MINUTES` | How often to check for due appointments | `15` |
| `MESSAGE_TEMPLATE` | Greek message with `{PatientName}`, `{ExamType}`, `{DateTime}`, `{LabName}`, `{DoctorName}` placeholders | Greek template |

### Callback Receiver

| Variable | Description | Default |
|----------|-------------|---------|
| `CALLBACK_HOST` | Flask listen host | `0.0.0.0` |
| `CALLBACK_PORT` | Flask listen port | `5000` |

---

## Secrets Management

> **Never commit secrets to git!** The `.gitignore` file excludes `.env`.

For production, consider:
- **Environment variables** on the server
- **Windows DPAPI** or a secrets manager
- For development: keep secrets in `.env` (gitignored)

---

## Deployment

### Reminder Service as a Windows Service

Use [NSSM (Non-Sucking Service Manager)](https://nssm.cc/) to run the Python script as a Windows service:

```bash
nssm install KosmoSMS-ReminderService "C:\path\to\venv\Scripts\python.exe" "C:\path\to\src\reminder_service.py"
nssm set KosmoSMS-ReminderService AppDirectory "C:\path\to\src"
nssm start KosmoSMS-ReminderService
```

### Callback Receiver

For production, run Flask behind a proper WSGI server:

```bash
pip install waitress
waitress-serve --host=0.0.0.0 --port=5000 callback_receiver:app
```

Or use NSSM to run it as a Windows service:

```bash
nssm install KosmoSMS-CallbackReceiver "C:\path\to\venv\Scripts\python.exe" "-m" "waitress" "--host=0.0.0.0" "--port=5000" "callback_receiver:app"
nssm set KosmoSMS-CallbackReceiver AppDirectory "C:\path\to\src"
nssm start KosmoSMS-CallbackReceiver
```

### Testing Callbacks Locally (ngrok)

During development, use [ngrok](https://ngrok.com/) to expose your local callback receiver:

```bash
ngrok http 5000
```

Then set `CALLBACK_URL=https://abc123.ngrok.io/api/sms-callback` in your `.env`.

---

## How It Works

### 1. Sync (SQL Server Agent — every 5–15 minutes)

The sync stored procedure runs automatically as a SQL Agent job. It:
- Reads the last processed Change Tracking version from `SyncState`
- Queries Slis via the Linked Server for rows changed since that version
- `MERGE`s changed rows into the `Appointments` table (upsert)
- Updates `SyncState` with the new version
- Logs the result to `SyncLog`

### 2. Send Reminders (`reminder_service.py` — every 15 minutes)

The reminder service wakes up, queries for appointments due within the next 24 hours that don't already have a notification, then for each:
1. **Validates the phone** via `api/mobile/check` (free, no API key needed)
2. **Sends a Viber message** via `api/viber/send` with `sms_fallback=true` — easysms.gr will automatically fall back to SMS if the Viber message can't be delivered
3. **Falls back to direct SMS** via `api/sms/send` only if the Viber API call itself fails (network error, invalid sender, etc.)
4. **Logs the result** in the `Notifications` table with the message ID

### 3. Receive Delivery Reports (`callback_receiver.py` — real-time)

When easysms.gr delivers (or fails to deliver) a message, it calls back the webhook:
```
GET /api/sms-callback?msgid=ABC123&status=delivered&cost=0.025&mcc=202&mnc=01
```

The callback receiver:
1. Validates the parameters
2. Looks up the pending notification by `msgid`
3. Updates the status to `Delivered`, `Failed`, or `Rejected`
4. Returns `200 OK` (always, to prevent retries)

---

## Diagrams

PlantUML diagrams are in the `puml/` directory:

| Diagram | Description |
|---------|-------------|
| `architecture.puml` | High-level system architecture |
| `erd.puml` | Database entity-relationship diagram |
| `reminder_sequence.puml` | Reminder send and delivery confirmation flow |
| `sync_sequence.puml` | Slis-to-KosmoSMS sync flow |

Render them with any PlantUML viewer, IDE plugin, or [plantuml.com](https://www.plantuml.com/).
