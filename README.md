# KosmoSMS — Appointment Reminder System & Dashboard

SMS/Viber reminder system and Dashboard for **Kosmoiatriki** diagnostic center. Syncs appointments from **Infomed Slis**, sends automated reminders via the **easysms.gr** API, and provides a desktop dashboard to monitor the status.

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
│ Reads due      │          │ Provides Dashboard  │
│ appointments   │          │ API & UI, plus      │
│ every 15 min   │          │ /api/sms-callback   │
└───────┬────────┘          └─────────▲───┬──────┘
        │                             │   │
        │  HTTP calls                 │   │ serves UI
        ▼                             │   ▼
┌───────────────┐                     │ ┌──────────────────┐
│ easysms.gr    │─────────────────────┘ │ KosmoSMS         │
│ API           │     delivery report   │ Dashboard (exe)  │
│ (Viber + SMS) │     callback          │                  │
└───────────────┘                       └──────────────────┘
```

### Components

| Component | Technology | Description |
|-----------|-----------|-------------|
| **Data Sync** | T-SQL Stored Procedure + SQL Agent | Pulls changed appointments from Slis via Linked Server every 5-15 min |
| **Reminder Service** | `reminder_service.py` (Python) | Checks for due appointments, validates phones, sends Viber/SMS |
| **Dashboard & Webhook** | `callback_receiver.py` (Flask) | Serves the web dashboard UI/API, receives delivery reports from easysms.gr |
| **Desktop Client** | `desktop_client.py` (pywebview) | A thin desktop application wrapper that connects to the Dashboard UI |
| **Launcher** | `start_app.py` / `run.bat` | Starts all backend services and opens the Desktop UI simultaneously |

---

## Prerequisites

- **Python 3.10+** — [Download](https://www.python.org/downloads/)
- **Microsoft ODBC Driver for SQL Server** — [Download](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- **MS SQL Server** — Your own instance for the KosmoSMS database
- **easysms.gr account** — [Sign up](https://easysms.gr/app/sign-up)

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
# Create a virtual environment at the root folder
python -m venv venv
venv\Scripts\activate       # Windows

# Install dependencies (from src)
pip install -r src/requirements.txt

# Install pyinstaller for building the exe
pip install pyinstaller
```

### 3. Configure

```bash
cd src
# Copy the template and fill in your values
copy .env.example .env      # Windows
cd ..
```

Edit `src/.env` with your actual values:

```ini
DB_CONNECTION_STRING=DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=KosmoSMS;Trusted_Connection=yes;
EASYSMS_API_KEY=your_api_key_here
CALLBACK_URL=https://your-public-domain.com/api/sms-callback
```

### 4. Build and Run

1. Build the Desktop Client (only needed once or when `desktop_client.py` changes):
```bash
build.bat
```

2. Run the full application (services + UI):
```bash
run.bat
```
*(This starts `callback_receiver.py`, `reminder_service.py`, and launches the generated `KosmoSMS_Dashboard.exe`. Closing the UI will gracefully stop the backend services).*

---

## Configuration Reference

All settings are in `src/.env` (loaded by `config.py`):

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

### Callback Receiver / Dashboard

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

### 3. Dashboard and Webhook (`callback_receiver.py` — continuous)

This Flask application serves two main purposes:

**a. Webhook for Delivery Reports**
When easysms.gr delivers (or fails to deliver) a message, it calls back the webhook endpoint:
```
GET /api/sms-callback?msgid=ABC123&status=delivered&cost=0.025&mcc=202&mnc=01
```
The callback receiver looks up the pending notification by `msgid` and updates its status.

**b. Dashboard UI and API**
Serves the HTML dashboard on `http://localhost:5000/` and provides API endpoints (`/api/dashboard/stats`, `/api/dashboard/messages`) to poll for real-time status and message logs.

### 4. Desktop Client (`desktop_client.py` / `start_app.py`)

Provides a unified interface to the user. `start_app.py` runs the background scripts, while `KosmoSMS_Dashboard.exe` (built from `desktop_client.py`) opens a pywebview window pointing directly to the locally hosted dashboard, offering a native app feel.

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