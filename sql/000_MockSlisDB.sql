-- ============================================================================
-- KosmoSMS — Mock Slis Database (LISKOSMO) for Local Testing
-- ============================================================================
-- Creates a local mock of the Infomed Slis database so you can test the
-- entire sync and reminder pipeline without access to the real Slis server.
--
-- Run this script BEFORE 001_CreateDatabase.sql and 003_SyncStoredProcedure.sql.
-- Safe to re-run: uses IF NOT EXISTS checks throughout.
-- ============================================================================

-- 1. Create the database
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'LISKOSMO')
BEGIN
    CREATE DATABASE [LISKOSMO];
    PRINT 'Database [LISKOSMO] created.';
END
ELSE
BEGIN
    PRINT 'Database [LISKOSMO] already exists — skipping creation.';
END
GO

USE [LISKOSMO];
GO

-- ============================================================================
-- 2. LABORATORY — Lab/Branch locations
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[LABORATORY]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[LABORATORY] (
        [LABORATORYID]  INT            NOT NULL,
        [FNAME]         NVARCHAR(200)  NOT NULL,   -- Lab display name (e.g. 'ΑΝΩ ΠΑΤΗΣΙΑ')
        [ADDRESS]       NVARCHAR(500)  NULL,        -- Lab address

        CONSTRAINT [PK_LABORATORY] PRIMARY KEY CLUSTERED ([LABORATORYID])
    );
    PRINT 'Table [LABORATORY] created.';
END
GO

-- ============================================================================
-- 3. SCHEDULERRESOURCES — Doctor/Resource slots
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[SCHEDULERRESOURCES]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[SCHEDULERRESOURCES] (
        [SCHEDULERRESOURCESID]  INT            NOT NULL,
        [NAME]                 NVARCHAR(200)  NOT NULL,   -- Resource name (e.g. 'ΥΠΕΡΗΧΟΙ (Α)')
        [LABORATORYID]         INT            NOT NULL,
        [ISACTIVE]             INT            NOT NULL DEFAULT 1,

        CONSTRAINT [PK_SCHEDULERRESOURCES] PRIMARY KEY CLUSTERED ([SCHEDULERRESOURCESID]),
        CONSTRAINT [FK_SR_LABORATORY] FOREIGN KEY ([LABORATORYID]) REFERENCES [dbo].[LABORATORY]([LABORATORYID])
    );
    PRINT 'Table [SCHEDULERRESOURCES] created.';
END
GO

-- ============================================================================
-- 4. DEMOG — Patient demographics
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[DEMOG]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[DEMOG] (
        [DEMOGID]  INT            NOT NULL,
        [LNAME]    NVARCHAR(100)  NOT NULL,   -- Last name
        [FNAME]    NVARCHAR(100)  NOT NULL,   -- First name
        [MOBILE]   NVARCHAR(20)   NULL,
        [EMAIL]    NVARCHAR(200)  NULL,

        CONSTRAINT [PK_DEMOG] PRIMARY KEY CLUSTERED ([DEMOGID])
    );
    PRINT 'Table [DEMOG] created.';
END
GO

-- ============================================================================
-- 5. SCHEDULERDATA — Appointment header
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[SCHEDULERDATA]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[SCHEDULERDATA] (
        [SCHEDULERDATAID]  INT            NOT NULL,
        [START]            DATETIME       NOT NULL,
        [FINISH]           DATETIME       NOT NULL,
        [RESOURCEID]       INT            NOT NULL,
        [MESSAGE]          NVARCHAR(MAX)  NULL,
        [DEMOGID]          INT            NULL,
        [DELETED]          INT            NOT NULL DEFAULT 0,
        [WARDID]           INT            NULL,

        CONSTRAINT [PK_SCHEDULERDATA] PRIMARY KEY CLUSTERED ([SCHEDULERDATAID]),
        CONSTRAINT [FK_SD_DEMOG] FOREIGN KEY ([DEMOGID]) REFERENCES [dbo].[DEMOG]([DEMOGID]),
        CONSTRAINT [FK_SD_RESOURCES] FOREIGN KEY ([RESOURCEID]) REFERENCES [dbo].[SCHEDULERRESOURCES]([SCHEDULERRESOURCESID])
    );
    PRINT 'Table [SCHEDULERDATA] created.';
END
GO

-- ============================================================================
-- 6. SCHEDULERDATAEXAM — Exam details linked to appointments
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[SCHEDULERDATAEXAM]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[SCHEDULERDATAEXAM] (
        [SCHEDULERDATAEXAMID]  INT            IDENTITY(1,1) NOT NULL,
        [SCHEDULERDATAID]      INT            NOT NULL,
        [EXAMSTRCODE]          NVARCHAR(200)  NOT NULL,   -- Raw exam code (e.g. 'ΠΑΡΑΚ ΘΥΡΕΟΕΙΔ')

        CONSTRAINT [PK_SCHEDULERDATAEXAM] PRIMARY KEY CLUSTERED ([SCHEDULERDATAEXAMID]),
        CONSTRAINT [FK_SDE_SCHEDULERDATA] FOREIGN KEY ([SCHEDULERDATAID]) REFERENCES [dbo].[SCHEDULERDATA]([SCHEDULERDATAID])
    );
    PRINT 'Table [SCHEDULERDATAEXAM] created.';
END
GO

-- ============================================================================
-- 7. Seed data — 3 realistic appointments
-- ============================================================================
-- The dummy data mirrors real Slis screenshots with Greek names, valid
-- phone numbers, and ugly EXAMSTRCODE values that the sync procedure
-- will normalize.
-- ============================================================================

-- -------------------------------------------------------
-- Labs (matching the 4 real Kosmoiatriki branches)
-- -------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM [dbo].[LABORATORY] WHERE [LABORATORYID] = 1)
BEGIN
    INSERT INTO [dbo].[LABORATORY] ([LABORATORYID], [FNAME], [ADDRESS])
    VALUES
        (1, N'ΚΕΝΤΡΙΚΟ',     N'ΠΑΤΗΣΙΩΝ 237'),
        (5, N'ΣΕΠΟΛΙΑ',      N'ΑΜΦΙΑΡΑΟΥ 165'),
        (6, N'ΑΝΩ ΠΑΤΗΣΙΑ',  N'ΥΠΟΚΑΤΑΣΤΗΜΑ:ΧΑΛΚΙΔΟΣ 12'),
        (7, N'ΙΛΙΟΝ',        N'ΥΠΟΚΑΤΑΣΤΗΜΑ:Λ.ΘΗΒΩΝ 439');
    PRINT 'Seed data inserted into [LABORATORY].';
END
GO

-- -------------------------------------------------------
-- Scheduler Resources (exam rooms / devices)
-- -------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM [dbo].[SCHEDULERRESOURCES] WHERE [SCHEDULERRESOURCESID] = 12)
BEGIN
    INSERT INTO [dbo].[SCHEDULERRESOURCES] ([SCHEDULERRESOURCESID], [NAME], [LABORATORYID], [ISACTIVE])
    VALUES
        (12, N'ΠΑΡΑΚΕΝΤΗΣΕΙΣ',    2, 1),   -- Puncture room (Lab 2 → will be mapped)
        (24, N'ΥΠΕΡΗΧΟΙ Β (Ζ)',   5, 1),   -- Ultrasound B at Sepolia
        (77, N'ΜΑΓΝΗΤΗΣ (Ι)',      7, 1);   -- MRI at Ilion
    PRINT 'Seed data inserted into [SCHEDULERRESOURCES].';

    -- Fix: ensure referenced labs exist for resources
    -- Lab 2 doesn't exist in our seed, so let's add it
    IF NOT EXISTS (SELECT 1 FROM [dbo].[LABORATORY] WHERE [LABORATORYID] = 2)
    BEGIN
        INSERT INTO [dbo].[LABORATORY] ([LABORATORYID], [FNAME], [ADDRESS])
        VALUES (2, N'ΙΚΕ', N'ΠΑΤΗΣΙΩΝ 237');
    END
END
GO

-- -------------------------------------------------------
-- Patients (DEMOG)
-- -------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM [dbo].[DEMOG] WHERE [DEMOGID] = 728314)
BEGIN
    INSERT INTO [dbo].[DEMOG] ([DEMOGID], [LNAME], [FNAME], [MOBILE], [EMAIL])
    VALUES
        (728314, N'ΑΝΔΡΕΣΑΚΗ',   N'ΜΑΡΙΑ',      N'6972719730', N'mandressaki@hotmail.com'),
        (827598, N'ΓΕΩΡΓΙΟΥ',    N'ΑΣΗΜΕΝΙΑ',    N'6940581538', NULL),
        (576903, N'ΜΟΥΓΚΑΡΑΚΗΣ', N'ΠΑΝΑΓΙΩΤΗΣ',  N'6938924827', NULL);
    PRINT 'Seed data inserted into [DEMOG].';
END
GO

-- -------------------------------------------------------
-- Appointments (SCHEDULERDATA)
-- Use DATEADD to set appointments ~23 hours in the future
-- so the reminder service picks them up immediately.
-- -------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM [dbo].[SCHEDULERDATA] WHERE [SCHEDULERDATAID] = 2990743)
BEGIN
    INSERT INTO [dbo].[SCHEDULERDATA] ([SCHEDULERDATAID], [START], [FINISH], [RESOURCEID], [MESSAGE], [DEMOGID], [DELETED], [WARDID])
    VALUES
        -- Appointment 1: Maria Andresaki — Thyroid puncture at Patision (tomorrow morning)
        (2990743,
         DATEADD(HOUR, 23, CAST(CAST(GETDATE() AS DATE) AS DATETIME) + CAST('07:30:00' AS DATETIME)),
         DATEADD(HOUR, 23, CAST(CAST(GETDATE() AS DATE) AS DATETIME) + CAST('08:00:00' AS DATETIME)),
         12, N'ΦΝΑ ΘΥΡΕΟ  ΦΙΛΗ κ ΠΙΠΕΡΟΠΟΥΛΟΥ   ΔΩΡΕΑΝ!!!!', 728314, 0, NULL),

        -- Appointment 2: Asimenia Georgiou — MRI at Ilion (tomorrow morning)
        (2992733,
         DATEADD(HOUR, 23, CAST(CAST(GETDATE() AS DATE) AS DATETIME) + CAST('06:30:00' AS DATETIME)),
         DATEADD(HOUR, 23, CAST(CAST(GETDATE() AS DATE) AS DATETIME) + CAST('07:30:00' AS DATETIME)),
         77, NULL, 827598, 0, 33549),

        -- Appointment 3: Panagiotis Mougarakis — Ultrasound at Sepolia (tomorrow afternoon)
        (2943960,
         DATEADD(HOUR, 23, CAST(CAST(GETDATE() AS DATE) AS DATETIME) + CAST('15:00:00' AS DATETIME)),
         DATEADD(HOUR, 23, CAST(CAST(GETDATE() AS DATE) AS DATETIME) + CAST('15:30:00' AS DATETIME)),
         24, NULL, 576903, 0, 23257);
    PRINT 'Seed data inserted into [SCHEDULERDATA].';
END
GO

-- -------------------------------------------------------
-- Exam details (SCHEDULERDATAEXAM)
-- These are the ugly raw codes that the sync SP will normalize.
-- -------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM [dbo].[SCHEDULERDATAEXAM] WHERE [SCHEDULERDATAID] = 2990743)
BEGIN
    INSERT INTO [dbo].[SCHEDULERDATAEXAM] ([SCHEDULERDATAID], [EXAMSTRCODE])
    VALUES
        (2990743, N'ΠΑΡΑΚΕΝΤΗΣΕΙΣ ΠΑΡΑΚ ΘΥΡΕΟΕΙΔ'),
        (2992733, N'MRI ΟΜΣΣ'),
        (2943960, N'ΥΠ ΑΝΩ ΚΟΙΛΙΑΣ');
    PRINT 'Seed data inserted into [SCHEDULERDATAEXAM].';
END
GO

PRINT '========================================';
PRINT 'Mock LISKOSMO database setup complete.';
PRINT 'You can now run 001_CreateDatabase.sql and 003_SyncStoredProcedure.sql.';
PRINT '========================================';
GO
