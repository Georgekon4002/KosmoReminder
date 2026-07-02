-- ============================================================================
-- KosmoSMS — Database Schema Creation Script
-- ============================================================================
-- Run this script on your own MS SQL Server instance.
-- It creates the KosmoSMS database and all required tables.
-- Safe to re-run: uses IF NOT EXISTS checks throughout.
-- ============================================================================

-- 1. Create the database (if it doesn't exist)
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'KosmoSMS')
BEGIN
    CREATE DATABASE [KosmoSMS];

PRINT 'Database [KosmoSMS] created.';

END ELSE BEGIN PRINT 'Database [KosmoSMS] already exists — skipping creation.';

END

USE [KosmoSMS];
GO

-- ============================================================================
-- 2. Labs
-- ============================================================================


IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Labs]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[Labs] (
        [LabID]       INT            NOT NULL,
        [LabName]     NVARCHAR(200)  NOT NULL,
        [LabAddress]  NVARCHAR(500)  NULL,   -- Street address for Google Maps link

        CONSTRAINT [PK_Labs] PRIMARY KEY CLUSTERED ([LabID])
    );

PRINT 'Table [Labs] created.';

END
GO

-- Seed Labs data (safe to re-run — skips if rows already exist)
IF NOT EXISTS (SELECT 1 FROM [dbo].[Labs] WHERE [LabID] = 5552201)
BEGIN
    INSERT INTO [dbo].[Labs] ([LabID], [LabName], [LabAddress])
    VALUES
        (5552201, N'Κοσμοϊατρική Πατησίων', N'Πατησίων 237, Πλ. Κολιάτσου'),
        (5552202, N'Κοσμοϊατρική Σεπολίων', N'Αμφιαράου 165, Σεπόλια, 10443'),
        (5552203, N'Κοσμοϊατρική Άνω Πατησίων', N'Χαλκίδος 12, Άνω Πατήσια, 11143'),
        (5552204, N'Κοσμοϊατρική Ιλίου', N'Θηβών 439, Ίλιον, 12131');

    PRINT 'Seed data inserted into [Labs].';
END
GO

-- ============================================================================
-- 3. Patients
-- ============================================================================


IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Patients]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[Patients] (
        [PatientID]        INT            NOT NULL,  -- Insurance number or Slis patient ID
        [FirstName]        NVARCHAR(100)  NOT NULL,
        [LastName]         NVARCHAR(100)  NOT NULL,
        [Phone]            NVARCHAR(20)   NULL,
        [Email]            NVARCHAR(200)  NULL,
        [PreferredChannel] NVARCHAR(10)   NULL,      -- 'Viber', 'SMS', or NULL (try Viber first)

        CONSTRAINT [PK_Patients] PRIMARY KEY CLUSTERED ([PatientID])
    );

PRINT 'Table [Patients] created.';

END

-- ============================================================================
-- 4. Appointments
-- ============================================================================


IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Appointments]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[Appointments] (
        [AppointmentID]       INT            IDENTITY(1,1) NOT NULL,
        [SlisAppointmentID]   INT            NOT NULL,       -- ID from the Slis source system
        [PatientID]           INT            NOT NULL,
        [AppointmentDateTime] DATETIME2(0)   NOT NULL,
        [ExamType]            NVARCHAR(200)  NULL,
        [Status]              NVARCHAR(50)   NOT NULL DEFAULT 'Scheduled',  -- Scheduled, Confirmed, Cancelled, Completed
        [LastSyncedAt]        DATETIME2(0)   NOT NULL DEFAULT SYSUTCDATETIME(),
        [LabID]               INT            NULL,

        CONSTRAINT [PK_Appointments]           PRIMARY KEY CLUSTERED ([AppointmentID]),
        CONSTRAINT [UQ_Appointments_SlisID]    UNIQUE ([SlisAppointmentID]),
        CONSTRAINT [FK_Appointments_Patients]  FOREIGN KEY ([PatientID]) REFERENCES [dbo].[Patients]([PatientID]),
        CONSTRAINT [FK_Appointments_Labs]      FOREIGN KEY ([LabID])     REFERENCES [dbo].[Labs]([LabID])
    );

PRINT 'Table [Appointments] created.';

END

-- Index for querying upcoming appointments by date
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = N'IX_Appointments_DateTime' AND object_id = OBJECT_ID(N'[dbo].[Appointments]'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_Appointments_DateTime]
        ON [dbo].[Appointments] ([AppointmentDateTime])
        INCLUDE ([PatientID], [Status]);

PRINT 'Index [IX_Appointments_DateTime] created.';

END

-- ============================================================================
-- 5. Notifications
-- ============================================================================


IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Notifications]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[Notifications] (
        [NotificationID]  INT            IDENTITY(1,1) NOT NULL,
        [AppointmentID]   INT            NOT NULL,
        [MessageID]       NVARCHAR(100)  NULL,          -- msgid returned by easysms.gr
        [ChannelUsed]     NVARCHAR(10)   NOT NULL,      -- 'Viber' or 'SMS'
        [SentAt]          DATETIME2(0)   NULL,
        [DeliveredAt]     DATETIME2(0)   NULL,
        [Status]          NVARCHAR(30)   NOT NULL DEFAULT 'Pending',  -- Pending, Sent, Delivered, Failed, Rejected
        [Cost]            DECIMAL(10,4)  NULL,
        [MCC]             NVARCHAR(10)   NULL,           -- Mobile Country Code
        [MNC]             NVARCHAR(10)   NULL,           -- Mobile Network Code

        CONSTRAINT [PK_Notifications]              PRIMARY KEY CLUSTERED ([NotificationID]),
        CONSTRAINT [FK_Notifications_Appointments] FOREIGN KEY ([AppointmentID]) REFERENCES [dbo].[Appointments]([AppointmentID])
    );

PRINT 'Table [Notifications] created.';

END

-- Index for callback lookups by MessageID
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = N'IX_Notifications_MessageID' AND object_id = OBJECT_ID(N'[dbo].[Notifications]'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_Notifications_MessageID]
        ON [dbo].[Notifications] ([MessageID])
        INCLUDE ([Status]);

PRINT 'Index [IX_Notifications_MessageID] created.';

END

-- ============================================================================
-- 6. SyncState
-- ============================================================================


IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[SyncState]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[SyncState] (
        [SyncID]             INT            IDENTITY(1,1) NOT NULL,
        [TableName]          NVARCHAR(128)  NOT NULL,
        [LastChangeVersion]  BIGINT         NOT NULL DEFAULT 0,
        [LastRunAt]          DATETIME2(0)   NULL,

        CONSTRAINT [PK_SyncState] PRIMARY KEY CLUSTERED ([SyncID]),
        CONSTRAINT [UQ_SyncState_TableName] UNIQUE ([TableName])
    );

PRINT 'Table [SyncState] created.';

END

-- ============================================================================
-- 7. SyncLog
-- ============================================================================


IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[SyncLog]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[SyncLog] (
        [LogID]          INT            IDENTITY(1,1) NOT NULL,
        [RunAt]          DATETIME2(0)   NOT NULL DEFAULT SYSUTCDATETIME(),
        [RowsProcessed]  INT            NOT NULL DEFAULT 0,
        [Status]         NVARCHAR(30)   NOT NULL,    -- Success, Failed, PartialSuccess
        [ErrorMessage]   NVARCHAR(MAX)  NULL,

        CONSTRAINT [PK_SyncLog] PRIMARY KEY CLUSTERED ([LogID])
    );

PRINT 'Table [SyncLog] created.';

END

-- ============================================================================
-- 8. Seed data: initial SyncState row for Appointments table
-- ============================================================================
IF NOT EXISTS (SELECT 1 FROM [dbo].[SyncState] WHERE [TableName] = N'Appointments')
BEGIN
    INSERT INTO [dbo].[SyncState] ([TableName], [LastChangeVersion], [LastRunAt])
    VALUES (N'Appointments', 0, NULL);

PRINT 'Seed row inserted into [SyncState] for Appointments.';

END

PRINT '========================================';

PRINT 'KosmoSMS schema creation complete.';

PRINT '========================================';
GO