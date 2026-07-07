-- ============================================================================
-- KosmoSMS — Database Schema Creation Script
-- ============================================================================
-- Safe to re-run: all CREATE TABLE / INSERT blocks are guarded with
-- IF NOT EXISTS checks.
-- ============================================================================

-- 1. Drop and recreate the database
IF EXISTS (SELECT name FROM sys.databases WHERE name = N'KosmoSMS')
BEGIN
    ALTER DATABASE [KosmoSMS] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE [KosmoSMS];
    PRINT 'Database [KosmoSMS] dropped.';
END
GO

CREATE DATABASE [KosmoSMS];
PRINT 'Database [KosmoSMS] created.';
GO

USE [KosmoSMS];
GO

-- ============================================================================
-- 2. Labs — our own curated branch list
-- ============================================================================
-- LabName    : short name used in the SMS ("Μονάδας Πατησίων")
-- LabAddress : formatted address shown in the SMS ("Πατησίων 237, ΤΚ 11254")
-- IDs start at 5552201 and never collide with LISKOSMO LABORATORYID values.
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Labs]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[Labs] (
        [LabID]       INT            NOT NULL,
        [LabName]     NVARCHAR(200)  NOT NULL,
        [LabAddress]  NVARCHAR(500)  NULL,

        CONSTRAINT [PK_Labs] PRIMARY KEY CLUSTERED ([LabID])
    );
    PRINT 'Table [Labs] created.';
END
GO

IF NOT EXISTS (SELECT 1 FROM [dbo].[Labs] WHERE [LabID] = 5552201)
BEGIN
    INSERT INTO [dbo].[Labs] ([LabID], [LabName], [LabAddress])
    VALUES
        (5552201, N'Κολιάτσου',      N'Πατησίων 237, ΤΚ 11254'),
        (5552202, N'Σεπολίων',       N'Αμφιαράου 165, ΤΚ 10443'),
        (5552203, N'Άνω Πατησίων',   N'Χαλκίδος 12, ΤΚ 11143'),
        (5552204, N'Ιλίου',          N'Λ.Θηβών 439, ΤΚ 13121'),
        (5552205, N'Πολυιατρείου',   N'Πατησίων 237, ΤΚ 11254');
    PRINT 'Seed data inserted into [Labs].';
END
GO

-- ============================================================================
-- 3. LabNameMap — maps Slis LABORATORYID → our own LabID
-- ============================================================================
-- This is the single source of truth for lab name/address in SMS messages.
-- The sync SP looks up this table and stores KosmoLabID in Appointments.
-- Our Labs table is NEVER modified by the sync.
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[LabNameMap]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[LabNameMap] (
        [SlisLabID]   INT  NOT NULL,
        [KosmoLabID]  INT  NOT NULL,

        CONSTRAINT [PK_LabNameMap] PRIMARY KEY CLUSTERED ([SlisLabID]),
        CONSTRAINT [FK_LNM_Labs]   FOREIGN KEY ([KosmoLabID]) REFERENCES [dbo].[Labs]([LabID])
    );
    PRINT 'Table [LabNameMap] created.';
END
GO

IF NOT EXISTS (SELECT 1 FROM [dbo].[LabNameMap] WHERE [SlisLabID] = 1)
BEGIN
    INSERT INTO [dbo].[LabNameMap] ([SlisLabID], [KosmoLabID])
    VALUES
        (1, 5552201),   -- ΚΟΛΙΑΤΣΟΥ    → Μονάδα Πατησίων
        (2, 5552205),   -- ΠΟΛΥΙΑΤΡΕΙΟ  → Μονάδα Πολυιατρείου
        (5, 5552202),   -- ΣΕΠΟΛΙΩΝ     → Μονάδα Σεπολίων
        (6, 5552203),   -- ΑΝΩ ΠΑΤΗΣΙΩΝ → Μονάδα Άνω Πατησίων
        (7, 5552204);   -- ΙΛΙΟΥ        → Μονάδα Ιλίου
    PRINT 'Seed data inserted into [LabNameMap].';
END
GO

-- ============================================================================
-- 4. Patients
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Patients]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[Patients] (
        [PatientID]        INT            NOT NULL,
        [FirstName]        NVARCHAR(100)  NOT NULL,
        [LastName]         NVARCHAR(100)  NOT NULL,
        [Phone]            NVARCHAR(20)   NULL,
        [Email]            NVARCHAR(200)  NULL,
        [Sex]              CHAR(1)        NULL CHECK ([Sex] IN ('M', 'F')),
        [PreferredChannel] NVARCHAR(10)   NULL,   -- 'Viber' | 'SMS' | NULL (try Viber first)

        CONSTRAINT [PK_Patients] PRIMARY KEY CLUSTERED ([PatientID])
    );
    PRINT 'Table [Patients] created.';
END
GO

-- ============================================================================
-- 5. Appointments
-- ============================================================================
-- Department: normalized name from DepartmentMap (set during sync).
-- Grouping key for SMS: PatientID + LabID + Department + AppointmentDate.
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Appointments]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[Appointments] (
        [AppointmentID]       INT            IDENTITY(1,1) NOT NULL,
        [SlisAppointmentID]   INT            NOT NULL,
        [PatientID]           INT            NOT NULL,
        [AppointmentDateTime] DATETIME2(0)   NOT NULL,
        [ExamType]            NVARCHAR(200)  NULL,
        [Department]          NVARCHAR(200)  NULL,   -- e.g. 'Τμήμα Αξονικού'
        [Status]              NVARCHAR(50)   NOT NULL DEFAULT 'Scheduled',
        [LastSyncedAt]        DATETIME2(0)   NOT NULL DEFAULT SYSUTCDATETIME(),
        [LabID]               INT            NULL,

        CONSTRAINT [PK_Appointments]           PRIMARY KEY CLUSTERED ([AppointmentID]),
        CONSTRAINT [UQ_Appointments_SlisID]    UNIQUE ([SlisAppointmentID]),
        CONSTRAINT [FK_Appointments_Patients]  FOREIGN KEY ([PatientID]) REFERENCES [dbo].[Patients]([PatientID]),
        CONSTRAINT [FK_Appointments_Labs]      FOREIGN KEY ([LabID])     REFERENCES [dbo].[Labs]([LabID])
    );
    PRINT 'Table [Appointments] created.';
END
GO

-- Upgrade path: add Department column if the table already exists without it
IF NOT EXISTS (SELECT * FROM sys.columns
               WHERE object_id = OBJECT_ID(N'[dbo].[Appointments]') AND name = 'Department')
BEGIN
    ALTER TABLE [dbo].[Appointments] ADD [Department] NVARCHAR(200) NULL;
    PRINT 'Column [Department] added to existing [Appointments] table.';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = N'IX_Appointments_DateTime' AND object_id = OBJECT_ID(N'[dbo].[Appointments]'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_Appointments_DateTime]
        ON [dbo].[Appointments] ([AppointmentDateTime])
        INCLUDE ([PatientID], [Status]);
    PRINT 'Index [IX_Appointments_DateTime] created.';
END
GO

-- ============================================================================
-- 6. Notifications
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Notifications]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[Notifications] (
        [NotificationID]  INT            IDENTITY(1,1) NOT NULL,
        [AppointmentID]   INT            NOT NULL,
        [MessageID]       NVARCHAR(100)  NULL,
        [ChannelUsed]     NVARCHAR(10)   NOT NULL,
        [SentAt]          DATETIME2(0)   NULL,
        [DeliveredAt]     DATETIME2(0)   NULL,
        [Status]          NVARCHAR(30)   NOT NULL DEFAULT 'Pending',
        [Cost]            DECIMAL(10,4)  NULL,
        [MCC]             NVARCHAR(10)   NULL,
        [MNC]             NVARCHAR(10)   NULL,

        CONSTRAINT [PK_Notifications]              PRIMARY KEY CLUSTERED ([NotificationID]),
        CONSTRAINT [FK_Notifications_Appointments] FOREIGN KEY ([AppointmentID]) REFERENCES [dbo].[Appointments]([AppointmentID])
    );
    PRINT 'Table [Notifications] created.';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = N'IX_Notifications_MessageID' AND object_id = OBJECT_ID(N'[dbo].[Notifications]'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_Notifications_MessageID]
        ON [dbo].[Notifications] ([MessageID]) INCLUDE ([Status]);
    PRINT 'Index [IX_Notifications_MessageID] created.';
END
GO

-- ============================================================================
-- 7. SyncState
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[SyncState]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[SyncState] (
        [SyncID]             INT            IDENTITY(1,1) NOT NULL,
        [TableName]          NVARCHAR(128)  NOT NULL,
        [LastChangeVersion]  BIGINT         NOT NULL DEFAULT 0,
        [LastRunAt]          DATETIME2(0)   NULL,

        CONSTRAINT [PK_SyncState]           PRIMARY KEY CLUSTERED ([SyncID]),
        CONSTRAINT [UQ_SyncState_TableName] UNIQUE ([TableName])
    );
    PRINT 'Table [SyncState] created.';
END
GO

-- ============================================================================
-- 8. SyncLog
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[SyncLog]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[SyncLog] (
        [LogID]          INT            IDENTITY(1,1) NOT NULL,
        [RunAt]          DATETIME2(0)   NOT NULL DEFAULT SYSUTCDATETIME(),
        [RowsProcessed]  INT            NOT NULL DEFAULT 0,
        [Status]         NVARCHAR(30)   NOT NULL,
        [ErrorMessage]   NVARCHAR(MAX)  NULL,

        CONSTRAINT [PK_SyncLog] PRIMARY KEY CLUSTERED ([LogID])
    );
    PRINT 'Table [SyncLog] created.';
END
GO

-- ============================================================================
-- 9. SyncState seed row
-- ============================================================================
IF NOT EXISTS (SELECT 1 FROM [dbo].[SyncState] WHERE [TableName] = N'Appointments')
BEGIN
    INSERT INTO [dbo].[SyncState] ([TableName], [LastChangeVersion], [LastRunAt])
    VALUES (N'Appointments', 0, NULL);
    PRINT 'Seed row inserted into [SyncState].';
END
GO

PRINT '========================================';
PRINT 'KosmoSMS schema creation complete.';
PRINT '========================================';
GO