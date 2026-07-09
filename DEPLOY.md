# Οδηγός Ανάπτυξης (Deployment Guide) — KosmoReminder

Αυτός ο οδηγός περιγράφει **όλα τα βήματα** για την τελική εγκατάσταση του συστήματος KosmoReminder στο διαγνωστικό κέντρο της Κοσμοϊατρικής. Απευθύνεται στους διαχειριστές του συστήματος και στο IT.

> **Σύνοψη:** Πρέπει να γίνουν τα εξής:
> 1. Δοκιμαστική εκτέλεση στον υπολογιστή σας (για να δείτε το Dashboard)
> 2. Ρύθμιση του easySMS API Key
> 3. Ρύθμιση του Callback URL (δημόσιο URL)
> 4. Ρύθμιση του Email Domain (Resend)
> 5. Εγκατάσταση της βάσης δεδομένων & δημιουργία του SQL Agent Job
> 6. Εγκατάσταση στον κεντρικό Server (services)
> 7. Deployment του .exe στους υπολογιστές των υπαλλήλων

---

## Εκκρεμότητες — GitHub Projects

Η πρόοδος του deployment παρακολουθείται μέσω **GitHub Projects**. Παρακάτω βρίσκονται τα ανοιχτά Issues που πρέπει να ολοκληρωθούν πριν το τελικό deployment:

| # | Issue | Αντιστοιχία σε αυτόν τον οδηγό |
|---|-------|-------------------------------|
| #25 | **Job to sync Slis with KosmoSMS DB** — Δημιουργία SQL Agent Job για αυτόματο συγχρονισμό | → Βήμα 5.3 (SQL Agent Job) |
| #18 | **Change to sms-marketing** — Αλλαγή Sender ID σε sms-marketing (αν απαιτηθεί από easysms.gr) | → Βήμα 2 (easySMS API Key & Sender IDs) |
| #24 | **Check if we need Resend -> SMTP authentication** — Διερεύνηση αν χρειαζόμαστε SMTP ή μόνο Resend API | → Βήμα 4 (Email Domain / Resend) |
| #13 | **Define Callback URL** — Ορισμός δημόσιου URL για delivery reports | → Βήμα 3 (Callback URL) |
| #14 | **Adapt to actual Slis DB** — Προσαρμογή του sync SP στα πραγματικά schemas/πίνακες του Slis | → Βήμα 5.1 & 5.2 (Linked Server & Sync) |
| #9  | **Test & Bug Fixes** — Δοκιμές end-to-end και διόρθωση σφαλμάτων | → Βήμα 1 (Δοκιμαστική Εκτέλεση) + Βήμα 7 (Troubleshooting) |
| #10 | **Deploy** — Τελική εγκατάσταση στον production server | → Βήμα 6 (Εγκατάσταση Server & Clients) |

> **Σημείωση:** Κάθε issue αντιστοιχεί σε μια ενότητα αυτού του οδηγού. Ολοκληρώστε τα βήματα στη σειρά που αναγράφονται παραπάνω, ξεκινώντας από τα #13, #14, #25 (υποδομή) και καταλήγοντας στα #9, #10 (τεστ & deploy).

---

## 0. Προαπαιτούμενα

| Λογισμικό | Λήψη |
|-----------|------|
| **Python 3.10+** | [python.org/downloads](https://www.python.org/downloads/) |
| **Microsoft ODBC Driver 17 for SQL Server** | [Microsoft Downloads](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) |
| **MS SQL Server** (τοπικός ή δικτυακός) | Ήδη εγκατεστημένο στον Server |
| **SQL Server Management Studio (SSMS)** | [Microsoft Downloads](https://learn.microsoft.com/en-us/sql/ssms/download-sql-server-management-studio-ssms) |

---

## 1. Δοκιμαστική Εκτέλεση (Δείτε το σύστημα να δουλεύει τοπικά)

Μπορείτε να τρέξετε ολόκληρο το σύστημα στον υπολογιστή σας **χωρίς να χρειάζεστε πρόσβαση στο Slis**, χρησιμοποιώντας τα mock (δοκιμαστικά) δεδομένα.

### Βήμα 1.1: Δημιουργία Mock Βάσης Δεδομένων

Ανοίξτε το **SSMS**, συνδεθείτε στον τοπικό SQL Server, και εκτελέστε τα παρακάτω SQL αρχεία **με αυτή τη σειρά**:

```
1. sql/mock_init.sql        ← Δημιουργεί μια τοπική βάση LISKOSMO (μίμηση του Slis)
2. sql/mock_insert.sql      ← Γεμίζει τη LISKOSMO με δοκιμαστικά ραντεβού
3. sql/init.sql             ← Δημιουργεί τη βάση KosmoSMS (πίνακες, Labs, κτλ.)
4. sql/sync.sql             ← Δημιουργεί το DepartmentMap και το Stored Procedure
5. sql/email_support.sql    ← Προσθέτει τη στήλη EmailStatus
```

Μετά, εκτελέστε χειροκίνητα τον συγχρονισμό στο SSMS:
```sql
USE [KosmoSMS];
EXEC [dbo].[usp_SyncAppointmentsFromSlis];
```

> **Σημείωση:** Αφού τρέξει ο sync, τα δοκιμαστικά ραντεβού θα μεταφερθούν στη βάση KosmoSMS. Μπορείτε να το επαληθεύσετε:
> ```sql
> SELECT TOP 10 p.FirstName, p.LastName, a.Department, a.AppointmentDateTime, l.LabName
> FROM KosmoSMS.dbo.Appointments a
> JOIN KosmoSMS.dbo.Patients p ON p.PatientID = a.PatientID
> LEFT JOIN KosmoSMS.dbo.Labs l ON l.LabID = a.LabID
> ORDER BY a.AppointmentDateTime;
> ```

### Βήμα 1.2: Ρύθμιση Python & Εκκίνηση

Ανοίξτε ένα **Command Prompt** ή **PowerShell** στον φάκελο του project:

```bash
# Δημιουργία εικονικού περιβάλλοντος
python -m venv venv
venv\Scripts\activate

# Εγκατάσταση βιβλιοθηκών
pip install -r src\requirements.txt
```

### Βήμα 1.3: Ρύθμιση .env (Ελάχιστη, για τοπική δοκιμή)

Αντιγράψτε το αρχείο template σε `.env`:
```bash
copy src\.env.example src\.env
```

Ανοίξτε το `src\.env` και βεβαιωθείτε ότι η γραμμή `DB_CONNECTION_STRING` δείχνει στον τοπικό σας SQL Server:
```ini
DB_CONNECTION_STRING=DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=KosmoSMS;Trusted_Connection=yes;
```

> Τα υπόλοιπα πεδία (API keys, Callback URL, κτλ.) μπορούν να μείνουν κενά — δεν χρειάζονται για τοπική προβολή.

### Βήμα 1.4: Εκκίνηση του Dashboard

```bash
# Εκκίνηση του Flask server (Dashboard + API)
python src\callback_receiver.py
```

Ανοίξτε τον browser σας στη διεύθυνση:
```
http://localhost:5000/
```

Θα δείτε το Dashboard με τα δοκιμαστικά ραντεβού σε κατάσταση **Pending** (αναμονή αποστολής). Αυτά είναι τα ραντεβού που θα περίμεναν αποστολή SMS/Viber αν τα services τρέχαν κανονικά.

> **Tip:** Μπορείτε να τρέξετε σε ξεχωριστό terminal και τον reminder service για πλήρη δοκιμή (αλλά θα αποτύχει η αποστολή SMS χωρίς πραγματικό API key — τα ραντεβού θα εμφανιστούν ως "Failed", πράγμα φυσιολογικό):
> ```bash
> python src\reminder_service.py
> ```

---

## 2. Ρύθμιση easySMS API Key

### Τι πρέπει να γίνει

1. Συνδεθείτε στο [easysms.gr](https://easysms.gr/) με τον λογαριασμό της Κοσμοϊατρικής.
2. Μεταβείτε στο **Dashboard → API Settings** (ή Settings → API Keys).
3. Αντιγράψτε το **API Key**.
4. Βεβαιωθείτε ότι τα **Sender IDs** (`Kosmoiatriki`) είναι εγκεκριμένα τόσο για Viber όσο και για SMS.

### Ρύθμιση στο `.env`

Στο αρχείο `src/.env`, συμπληρώστε:
```ini
EASYSMS_API_KEY=ΤΟ_API_KEY_ΣΑΣ_ΕΔΩ
VIBER_SENDER_ID=Kosmoiatriki
SMS_SENDER_ID=Kosmoiatriki
```

---

## 3. Ρύθμιση Callback URL (Delivery Reports)

### Τι είναι

Το Callback URL είναι ένα **δημόσια προσβάσιμο URL** που καλεί το easysms.gr αυτόματα κάθε φορά που ένα μήνυμα παραδίδεται (ή αποτυγχάνει). Μέσω αυτού, το Dashboard ενημερώνεται σε πραγματικό χρόνο.


### Τι πρέπει να γίνει

1. **Ορίστε ένα public domain ή IP** για τον κεντρικό server, π.χ.:
   - `sms.kosmoiatriki.gr` (αν έχετε domain) ή
   - Η δημόσια IP του server (αν δεν έχετε domain)

2. **Ρυθμίστε Port Forwarding / NAT** στο router/firewall ώστε οι εξωτερικές αιτήσεις στο port 443 (HTTPS) ή 80 (HTTP) να κατευθύνονται στον εσωτερικό server στο port 5000.

3. **(Προτεινόμενο) Ρυθμίστε ένα Reverse Proxy** με IIS ή Nginx ώστε:
   - Να τερματίζει TLS/HTTPS (με Let's Encrypt ή εσωτερικό πιστοποιητικό)
   - Να κάνει proxy τα requests στο `http://localhost:5000`

   **Παράδειγμα IIS URL Rewrite (web.config):**
   ```xml
   <rule name="KosmoReminder" stopProcessing="true">
       <match url="api/sms-callback(.*)" />
       <action type="Rewrite" url="http://localhost:5000/api/sms-callback{R:1}" />
   </rule>
   ```

4. **Ρυθμίστε στο `.env`:**
   ```ini
   CALLBACK_URL=https://sms.kosmoiatriki.gr/api/sms-callback
   ```

5. **Ρυθμίστε στο easysms.gr:** Μεταβείτε στο panel → Settings → Callback URL και βάλτε το ίδιο URL.

> ⚠️ **Χωρίς Callback URL** το σύστημα δουλεύει κανονικά — απλώς το Dashboard δεν θα εμφανίζει κατάσταση "Delivered" ή "Failed", αλλά μόνο "Sent".

---

## 4. Ρύθμιση Email Domain (Resend.com)

### Τι πρέπει να γίνει

Το σύστημα στέλνει emails επιβεβαίωσης ραντεβού (με ημερολογιακή πρόσκληση .ics) μέσω [Resend.com](https://resend.com). Για να φτάνουν τα emails στα inbox (και όχι στα spam), πρέπει να γίνει **domain verification**.

### Βήματα

1. **Δημιουργήστε λογαριασμό** στο [resend.com](https://resend.com) (ή συνδεθείτε αν υπάρχει).

2. **Προσθέστε Domain:** Μεταβείτε στο **Domains → Add Domain** και εισάγετε `kosmoiatriki.gr` (ή το domain που θέλετε να χρησιμοποιήσετε).

3. **Προσθέστε DNS Records:** Το Resend θα σας δώσει DNS εγγραφές (MX, TXT, CNAME) που πρέπει να προστεθούν στον DNS provider του domain σας. Συνήθως:
   - **SPF (TXT record):** Επιτρέπει στο Resend να στέλνει email εκ μέρους σας
   - **DKIM (CNAME records):** Ψηφιακή υπογραφή email
   - **DMARC (TXT record):** Πολιτική authentication

4. **Περιμένετε Verification** — συνήθως 5-10 λεπτά αφού προστεθούν τα DNS records.

5. **Αντιγράψτε το API Key:** Μεταβείτε στο **API Keys → Create API Key** στο Resend panel.

### Ρύθμιση στο `.env`
```ini
RESEND_API_KEY=re_xxxxxxxxxxxxxxxx
EMAIL_FROM_ADDRESS=noreply@kosmoiatriki.gr
EMAIL_FROM_NAME=ΚΟΣΜΟΪΑΤΡΙΚΗ
ORGANIZER_EMAIL=info@kosmoiatriki.gr
```

> **Εναλλακτικό Σενάριο (Χωρίς Resend):** Ενδέχεται να μη χρειαστείτε καθόλου το Resend αν επιλυθούν τα θέματα authentication με τον υπάρχοντα SMTP server της κλινικής. Η διεύθυνση `no-reply@kosmoiatriki.gr` που είχε οριστεί παλαιότερα μπορεί να λειτουργήσει κανονικά. Σε αυτή την περίπτωση, θα χρειαστεί απλώς να προσαρμοστεί ο κώδικας στο `email_reminder_service.py` ώστε να στέλνει μέσω απλού SMTP (αντί για το Resend API) και μπορείτε να παραλείψετε τα παρακάτω βήματα.

> ⚠️ **Χωρίς verified domain**, τα emails είτε δεν θα φεύγουν καθόλου, είτε θα πηγαίνουν στα Spam.

---

## 5. Βάση Δεδομένων & Δημιουργία SQL Agent Job

### Βήμα 5.1: Εγκατάσταση Σχήματος (Production)

Στο SSMS, εκτελέστε τα SQL αρχεία **με αυτή τη σειρά**:

```
1. sql/init.sql             ← Δημιουργεί τη βάση KosmoSMS και τους πίνακες
2. sql/link.sql             ← Ρυθμίζει τον Linked Server προς τη βάση Slis
                              ⚠️ Αντικαταστήστε τα <<SLIS_SERVER_NAME>>, 
                              <<SLIS_READ_USER>>, <<SLIS_READ_PASSWORD>>
3. sql/sync.sql             ← Δημιουργεί το DepartmentMap και το Stored Procedure
4. sql/email_support.sql    ← Προσθέτει τη στήλη EmailStatus
```

### Βήμα 5.2: Δοκιμή Συγχρονισμού (χειροκίνητα)

Αφού ρυθμιστεί ο Linked Server, δοκιμάστε τον sync χειροκίνητα:
```sql
USE [KosmoSMS];
EXEC [dbo].[usp_SyncAppointmentsFromSlis];

-- Δείτε αν μεταφέρθηκαν ραντεβού:
SELECT TOP 10 * FROM dbo.Appointments ORDER BY AppointmentDateTime DESC;

-- Δείτε το log:
SELECT TOP 5 * FROM dbo.SyncLog ORDER BY RunAt DESC;
```

### Βήμα 5.3: Δημιουργία SQL Agent Job (Αυτόματος Συγχρονισμός)

Ο παρακάτω κώδικας δημιουργεί ένα **SQL Server Agent Job** που θα εκτελεί αυτόματα τον συγχρονισμό **κάθε 10 λεπτά**.

> ⚠️ **Ο SQL Server Agent πρέπει να τρέχει** (services.msc → SQL Server Agent → Start / Automatic).

Εκτελέστε τον παρακάτω κώδικα στο SSMS:

```sql
-- ============================================================================
-- KosmoReminder — SQL Agent Job: Αυτόματος Συγχρονισμός Ραντεβού
-- ============================================================================
-- Δημιουργεί ένα Job που τρέχει κάθε 10 λεπτά το Stored Procedure
-- [dbo].[usp_SyncAppointmentsFromSlis] στη βάση KosmoSMS.
-- ============================================================================

USE [msdb];
GO

-- Αν υπάρχει ήδη, διαγραφή
IF EXISTS (SELECT * FROM msdb.dbo.sysjobs WHERE name = N'KosmoReminder_SyncAppointments')
BEGIN
    EXEC msdb.dbo.sp_delete_job @job_name = N'KosmoReminder_SyncAppointments', @delete_unused_schedule = 1;
    PRINT 'Existing job deleted.';
END
GO

-- 1. Δημιουργία Job
EXEC msdb.dbo.sp_add_job
    @job_name           = N'KosmoReminder_SyncAppointments',
    @enabled            = 1,
    @description        = N'Εκτελεί τον συγχρονισμό ραντεβού (Slis → KosmoSMS) κάθε 10 λεπτά.',
    @category_name      = N'[Uncategorized (Local)]',
    @owner_login_name   = N'sa';
GO

-- 2. Προσθήκη Βήματος (Step)
EXEC msdb.dbo.sp_add_jobstep
    @job_name           = N'KosmoReminder_SyncAppointments',
    @step_name          = N'Run usp_SyncAppointmentsFromSlis',
    @step_id            = 1,
    @subsystem          = N'TSQL',
    @command            = N'EXEC [dbo].[usp_SyncAppointmentsFromSlis];',
    @database_name      = N'KosmoSMS',
    @retry_attempts     = 2,
    @retry_interval     = 1,     -- λεπτά μεταξύ retries
    @on_success_action  = 1,     -- Quit with success
    @on_fail_action     = 2;     -- Quit with failure
GO

-- 3. Δημιουργία Χρονοδιαγράμματος (κάθε 10 λεπτά)
EXEC msdb.dbo.sp_add_jobschedule
    @job_name           = N'KosmoReminder_SyncAppointments',
    @name               = N'Every10Minutes',
    @enabled            = 1,
    @freq_type          = 4,     -- Daily
    @freq_interval      = 1,     -- κάθε 1 ημέρα
    @freq_subday_type   = 4,     -- Minutes
    @freq_subday_interval = 10,  -- κάθε 10 λεπτά
    @active_start_time  = 060000,  -- Ξεκινάει στις 06:00
    @active_end_time    = 230000;  -- Σταματάει στις 23:00
GO

-- 4. Αντιστοίχιση στον τοπικό server
EXEC msdb.dbo.sp_add_jobserver
    @job_name           = N'KosmoReminder_SyncAppointments',
    @server_name        = N'(LOCAL)';
GO

PRINT '================================================================';
PRINT 'SQL Agent Job [KosmoReminder_SyncAppointments] δημιουργήθηκε.';
PRINT 'Θα τρέχει κάθε 10 λεπτά (06:00 - 23:00).';
PRINT '================================================================';
GO
```

Μετά την εκτέλεση, μπορείτε να το επαληθεύσετε:
- **SSMS → SQL Server Agent → Jobs** → θα δείτε το `KosmoReminder_SyncAppointments`
- Δεξί κλικ → **Start Job at Step...** για χειροκίνητη δοκιμή
- Δείτε τα αποτελέσματα: `SELECT TOP 10 * FROM KosmoSMS.dbo.SyncLog ORDER BY RunAt DESC;`

---

## 6. Στρατηγική Εγκατάστασης (Deployment Strategy)

Το σύστημα είναι σχεδιασμένο με αρχιτεκτονική **Κεντρικού Server (Client-Server)**. Αυτό σημαίνει ότι τα background services ΔΕΝ χρειάζεται (και δεν πρέπει) να τρέχουν σε κάθε υπολογιστή του διαγνωστικού κέντρου.

### Βήμα 6.1: Εγκατάσταση στον Κεντρικό Server

Στον κεντρικό υπολογιστή/διακομιστή (εκεί όπου ιδανικά τρέχει και ο SQL Server ή σε κάποιον application server στο ίδιο δίκτυο):

1. **Εγκαταστήστε Python 3.10+** και τις βιβλιοθήκες:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r src\requirements.txt
   ```

2. **Δημιουργήστε το αρχείο `src/.env`** και συμπληρώστε τα κλειδιά (Βήματα 2, 3, 4):
   ```bash
   copy src\.env.example src\.env
   ```

3. **Τρέξτε το PowerShell script** `install_services.ps1`:
   - Κάντε Δεξί Κλικ → **Run with PowerShell** ως **Διαχειριστής (Administrator)**

   Αυτό θα εγκαταστήσει τα 3 βασικά προγράμματα ως **Windows Services** (μέσω NSSM):

   | Service | Περιγραφή |
   |---------|-----------|
   | `KosmoSMS_ReminderService` | Αποστολή SMS/Viber υπενθυμίσεων (κάθε 15 λεπτά) |
   | `KosmoSMS_CallbackReceiver` | Web Dashboard + Webhook για Delivery Reports |
   | `KosmoSMS_EmailReminderService` | Αποστολή email υπενθυμίσεων (κάθε 5 λεπτά) |

4. **Επαλήθευση:** Ανοίξτε `services.msc` και ελέγξτε ότι τα 3 services είναι **Running**. Ανοίξτε browser → `http://localhost:5000/` → πρέπει να δείτε το Dashboard.

### Βήμα 6.2: Εγκατάσταση στους Υπολογιστές των Υπαλλήλων (Clients)

Για τους υπολογιστές των υπαλλήλων (reception, κτλ.) **δεν απαιτείται καμία εγκατάσταση της Python ή των Services**.

**Επιλογή Α — Μέσω Web Browser (Προτεινόμενη):**

Οι χρήστες ανοίγουν τον Chrome/Edge και πληκτρολογούν:
```
http://<IP_ΚΕΝΤΡΙΚΟΥ_SERVER>:5000/
```
Π.χ. `http://192.168.1.100:5000/`

Αυτό είναι το πιο απλό — δεν χρειάζεται εγκατάσταση ή updates στους clients.

**Επιλογή Β — Μέσω Desktop Client (.exe):**

Αν θέλετε η εφαρμογή να εμφανίζεται σαν ξεχωριστό desktop πρόγραμμα (χωρίς tabs/browser):

1. **Build:** Στον server ή σε development PC, τρέξτε:
   ```bash
   # Χρειάζεται μία φορά (ή όταν αλλάξει ο κώδικας)
   pip install pyinstaller
   build.bat
   ```
   Αυτό θα δημιουργήσει το `dist\KosmoReminder.exe`.

2. **Αντιγραφή:** Αντιγράψτε **μόνο** το αρχείο `KosmoReminder.exe` στους υπολογιστές (π.χ. `C:\KosmoReminder\KosmoReminder.exe`).

3. **Shortcut (Συντόμευση):** Επειδή το `.exe` εξ ορισμού δείχνει στο `localhost`, φτιάξτε μια **Συντόμευση** στην επιφάνεια εργασίας κάθε υπαλλήλου:
   - Δεξί κλικ στο Desktop → Νέα Συντόμευση
   - **Target (Προορισμός):** `"C:\KosmoReminder\KosmoReminder.exe" http://192.168.1.100:5000/`
   - **Name:** `KosmoReminder`

   Αντικαταστήστε `192.168.1.100` με την πραγματική IP του κεντρικού server.

---

## 7. Logs & Troubleshooting

Τα logs βρίσκονται στον φάκελο `logs/` (στο root του project, στον Server):

| Log αρχείο | Τι καταγράφει |
|-------------|---------------|
| `reminder-service.log` | Αποστολή SMS/Viber (ποια ραντεβού, ποιος ασθενής, αποτυχίες) |
| `callback-receiver.log` | Webhook callbacks, Dashboard API requests |
| `email-reminder-service.log` | Αποστολή emails (Resend API responses) |
| `*-nssm.log` | stdout/stderr από τα Windows Services (για crashes/startup errors) |

**Συνήθη προβλήματα:**

| Πρόβλημα | Λύση |
|----------|------|
| Ο sync δεν τρέχει | Ελέγξτε ότι ο SQL Server Agent είναι **Started** (`services.msc`) |
| Τα SMS δεν στέλνονται | Ελέγξτε `reminder-service.log` — πιθανώς λάθος API key ή μη εγκεκριμένο Sender ID |
| Τα emails πάνε στα spam | Ελέγξτε ότι το domain είναι **Verified** στο Resend (SPF, DKIM, DMARC) |
| Το Dashboard δεν ανοίγει | Ελέγξτε ότι το service `KosmoSMS_CallbackReceiver` τρέχει (`services.msc`) ή κάντε σε Administrator PowerShell `Restart-Service KosmoSMS_*` |
| Ο .exe δεν βρίσκει τον server | Ελέγξτε ότι η IP στο Shortcut Target είναι σωστή και το port 5000 δεν μπλοκάρεται |