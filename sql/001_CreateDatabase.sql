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
END
ELSE
BEGIN
    PRINT 'Database [KosmoSMS] already exists — skipping creation.';
END
GO

USE [KosmoSMS];
GO

-- ============================================================================
-- 2. Doctors
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Doctors]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[Doctors] (
        [DocID]      INT            NOT NULL,
        [FirstName]  NVARCHAR(100)  NOT NULL,
        [LastName]   NVARCHAR(100)  NOT NULL,
        [Expertise]  NVARCHAR(200)  NULL,

        CONSTRAINT [PK_Doctors] PRIMARY KEY CLUSTERED ([DocID])
    );
    PRINT 'Table [Doctors] created.';
END
GO

-- ============================================================================
-- 3. Labs
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Labs]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[Labs] (
        [LabID]           INT            NOT NULL,
        [LabName]         NVARCHAR(200)  NOT NULL,
        [LabGeoLocation]  NVARCHAR(500)  NULL,   -- e.g., address or lat/lng

        CONSTRAINT [PK_Labs] PRIMARY KEY CLUSTERED ([LabID])
    );
    PRINT 'Table [Labs] created.';
END
GO

-- ============================================================================
-- 4. Patients
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
GO

-- ============================================================================
-- 5. Appointments
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
        [DocID]               INT            NULL,

        CONSTRAINT [PK_Appointments]           PRIMARY KEY CLUSTERED ([AppointmentID]),
        CONSTRAINT [UQ_Appointments_SlisID]    UNIQUE ([SlisAppointmentID]),
        CONSTRAINT [FK_Appointments_Patients]  FOREIGN KEY ([PatientID]) REFERENCES [dbo].[Patients]([PatientID]),
        CONSTRAINT [FK_Appointments_Labs]      FOREIGN KEY ([LabID])     REFERENCES [dbo].[Labs]([LabID]),
        CONSTRAINT [FK_Appointments_Doctors]   FOREIGN KEY ([DocID])     REFERENCES [dbo].[Doctors]([DocID])
    );
    PRINT 'Table [Appointments] created.';
END
GO

-- Index for querying upcoming appointments by date
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
GO

-- Index for callback lookups by MessageID
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = N'IX_Notifications_MessageID' AND object_id = OBJECT_ID(N'[dbo].[Notifications]'))
BEGIN
    CREATE NONCLUSTERED INDEX [IX_Notifications_MessageID]
        ON [dbo].[Notifications] ([MessageID])
        INCLUDE ([Status]);
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

        CONSTRAINT [PK_SyncState] PRIMARY KEY CLUSTERED ([SyncID]),
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
        [Status]         NVARCHAR(30)   NOT NULL,    -- Success, Failed, PartialSuccess
        [ErrorMessage]   NVARCHAR(MAX)  NULL,

        CONSTRAINT [PK_SyncLog] PRIMARY KEY CLUSTERED ([LogID])
    );
    PRINT 'Table [SyncLog] created.';
END
GO

-- ============================================================================
-- 9. Seed data: initial SyncState row for Appointments table
-- ============================================================================
IF NOT EXISTS (SELECT 1 FROM [dbo].[SyncState] WHERE [TableName] = N'Appointments')
BEGIN
    INSERT INTO [dbo].[SyncState] ([TableName], [LastChangeVersion], [LastRunAt])
    VALUES (N'Appointments', 0, NULL);
    PRINT 'Seed row inserted into [SyncState] for Appointments.';
END
GO

PRINT '========================================';
PRINT 'KosmoSMS schema creation complete.';
PRINT '========================================';
GO
