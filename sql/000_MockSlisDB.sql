-- ============================================================================
-- KosmoSMS — Mock Slis Database (LISKOSMO) for Local Testing
-- ============================================================================
-- Creates a local mock of the Infomed Slis database so you can test the
-- entire sync and reminder pipeline without access to the real Slis server.
--
-- Run this script BEFORE 001_CreateDatabase.sql and 003_SyncStoredProcedure.sql.
-- Safe to re-run: uses IF NOT EXISTS / MERGE checks throughout.
-- ============================================================================

-- 1. Drop and recreate the database
IF EXISTS (SELECT name FROM sys.databases WHERE name = N'LISKOSMO')
BEGIN
    ALTER DATABASE [LISKOSMO] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE [LISKOSMO];
    PRINT 'Database [LISKOSMO] dropped.';
END
GO

CREATE DATABASE [LISKOSMO];
PRINT 'Database [LISKOSMO] created.';
GO

USE [LISKOSMO];
GO

-- ============================================================================
-- 2. SCHEDULERRESOURCESGROUP — Department / exam-type groups
--    Must be created BEFORE SCHEDULERRESOURCES (FK dependency).
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[SCHEDULERRESOURCESGROUP]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[SCHEDULERRESOURCESGROUP] (
        [SCHEDULERRESOURCESGROUPID]  INT            NOT NULL,
        [GROUPNAME]                  NVARCHAR(200)  NOT NULL,   -- e.g. 'ΑΞΟΝΙΚΟΥ', 'ΥΠΕΡΗΧΩΝ'

        CONSTRAINT [PK_SCHEDULERRESOURCESGROUP] PRIMARY KEY CLUSTERED ([SCHEDULERRESOURCESGROUPID])
    );
    PRINT 'Table [SCHEDULERRESOURCESGROUP] created.';
END
GO

-- ============================================================================
-- 3. LABORATORY — Lab/Branch locations (as they appear in Slis)
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[LABORATORY]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[LABORATORY] (
        [LABORATORYID]  INT            NOT NULL,
        [FNAME]         NVARCHAR(200)  NOT NULL,   -- Short branch name (all-caps)
        [ADDRESS]       NVARCHAR(500)  NULL,        -- Raw address from Slis
        [ISACTIVE]      INT            NOT NULL DEFAULT 1,

        CONSTRAINT [PK_LABORATORY] PRIMARY KEY CLUSTERED ([LABORATORYID])
    );
    PRINT 'Table [LABORATORY] created.';
END
GO

-- ============================================================================
-- 4. SCHEDULERRESOURCES — Exam rooms / devices, linked to a group and lab
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[SCHEDULERRESOURCES]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[SCHEDULERRESOURCES] (
        [SCHEDULERRESOURCESID]       INT            NOT NULL,
        [NAME]                       NVARCHAR(200)  NOT NULL,
        [LABORATORYID]               INT            NOT NULL,
        [SCHEDULERRESOURCESGROUPID]  INT            NULL,   -- Which department group this room belongs to
        [ISACTIVE]                   INT            NOT NULL DEFAULT 1,

        CONSTRAINT [PK_SCHEDULERRESOURCES] PRIMARY KEY CLUSTERED ([SCHEDULERRESOURCESID]),
        CONSTRAINT [FK_SR_LABORATORY]  FOREIGN KEY ([LABORATORYID])              REFERENCES [dbo].[LABORATORY]([LABORATORYID]),
        CONSTRAINT [FK_SR_GROUP]       FOREIGN KEY ([SCHEDULERRESOURCESGROUPID]) REFERENCES [dbo].[SCHEDULERRESOURCESGROUP]([SCHEDULERRESOURCESGROUPID])
    );
    PRINT 'Table [SCHEDULERRESOURCES] created.';
END
GO

-- ============================================================================
-- 5. DEMOG — Patient demographics
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[DEMOG]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[DEMOG] (
        [DEMOGID]  INT            NOT NULL,
        [LNAME]    NVARCHAR(100)  NOT NULL,   -- Last name (all-caps)
        [FNAME]    NVARCHAR(100)  NOT NULL,   -- First name (all-caps)
        [MOBILE]   NVARCHAR(20)   NULL,
        [EMAIL]    NVARCHAR(200)  NULL,
        [SEX]      CHAR(1)        NULL CHECK ([SEX] IN ('M', 'F')),

        CONSTRAINT [PK_DEMOG] PRIMARY KEY CLUSTERED ([DEMOGID])
    );
    PRINT 'Table [DEMOG] created.';
END
GO

-- ============================================================================
-- 6. SCHEDULERDATA — Appointment header
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

        CONSTRAINT [PK_SCHEDULERDATA]     PRIMARY KEY CLUSTERED ([SCHEDULERDATAID]),
        CONSTRAINT [FK_SD_DEMOG]          FOREIGN KEY ([DEMOGID])     REFERENCES [dbo].[DEMOG]([DEMOGID]),
        CONSTRAINT [FK_SD_RESOURCES]      FOREIGN KEY ([RESOURCEID])  REFERENCES [dbo].[SCHEDULERRESOURCES]([SCHEDULERRESOURCESID])
    );
    PRINT 'Table [SCHEDULERDATA] created.';
END
GO

-- ============================================================================
-- 7. SCHEDULERDATAEXAM — Exam codes per appointment
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[SCHEDULERDATAEXAM]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[SCHEDULERDATAEXAM] (
        [SCHEDULERDATAEXAMID]  INT            IDENTITY(1,1) NOT NULL,
        [SCHEDULERDATAID]      INT            NOT NULL,
        [EXAMSTRCODE]          NVARCHAR(200)  NOT NULL,

        CONSTRAINT [PK_SCHEDULERDATAEXAM]  PRIMARY KEY CLUSTERED ([SCHEDULERDATAEXAMID]),
        CONSTRAINT [FK_SDE_SCHEDULERDATA]  FOREIGN KEY ([SCHEDULERDATAID]) REFERENCES [dbo].[SCHEDULERDATA]([SCHEDULERDATAID])
    );
    PRINT 'Table [SCHEDULERDATAEXAM] created.';
END
GO

-- ============================================================================
-- 8. Seed: Department groups
-- ============================================================================
IF NOT EXISTS (SELECT 1 FROM [dbo].[SCHEDULERRESOURCESGROUP] WHERE [SCHEDULERRESOURCESGROUPID] = 1)
BEGIN
    INSERT INTO [dbo].[SCHEDULERRESOURCESGROUP] ([SCHEDULERRESOURCESGROUPID], [GROUPNAME])
    VALUES
        (1,  N'Α/Α-Μ.Ο.Π-ΜΑΣΤΟ'),
        (2,  N'ΚΑΡΔΙΟΛΟΓΙΚΟ'),
        (3,  N'ΥΠΕΡΗΧΩΝ'),
        (4,  N'ΜΑΓΝΗΤΗ'),
        (5,  N'ΑΞΟΝΙΚΟΥ'),
        (6,  N'ΜΙΚΡΟΒΙΟΛΟΓΙΚΟ'),
        (7,  N'ΓΑΣΤΡΕΝΤΕΡΟΛΟΓΙΚΟ'),
        (14, N'ΙΑΤΡΟΙ ΕΙΔΙΚΟΤΗΤΩΝ'),
        (15, N'ΠΥΡΗΝΙΚΗΣ');
    PRINT 'Seed data inserted into [SCHEDULERRESOURCESGROUP].';
END
GO

-- ============================================================================
-- 9. Seed: Labs (matching exact data from the live Slis system)
-- ============================================================================
IF NOT EXISTS (SELECT 1 FROM [dbo].[LABORATORY] WHERE [LABORATORYID] = 1)
BEGIN
    INSERT INTO [dbo].[LABORATORY] ([LABORATORYID], [FNAME], [ADDRESS], [ISACTIVE])
    VALUES
        (1, N'ΚΟΛΙΑΤΣΟΥ',    N'ΠΑΤΗΣΙΩΝ 237 – ΤΚ 11254',   1),
        (2, N'ΠΟΛΥΙΑΤΡΕΙΟ',  N'ΠΑΤΗΣΙΩΝ 237 – ΤΚ 11254',   1),
        (5, N'ΣΕΠΟΛΙΩΝ',     N'ΑΜΦΙΑΡΑΟΥ 165 – ΤΚ 10443',  1),
        (6, N'ΑΝΩ ΠΑΤΗΣΙΩΝ', N'ΧΑΛΚΙΔΟΣ 12 – ΤΚ 11143',   1),
        (7, N'ΙΛΙΟΥ',        N'Λ.ΘΗΒΩΝ 439 – ΤΚ 13121',    1);
    PRINT 'Seed data inserted into [LABORATORY].';
END
GO

-- ============================================================================
-- 10. Seed: Exam rooms / devices (SCHEDULERRESOURCES)
--     Each resource belongs to a lab and a department group.
-- ============================================================================
IF NOT EXISTS (SELECT 1 FROM [dbo].[SCHEDULERRESOURCES] WHERE [SCHEDULERRESOURCESID] = 12)
BEGIN
    INSERT INTO [dbo].[SCHEDULERRESOURCES] ([SCHEDULERRESOURCESID], [NAME], [LABORATORYID], [SCHEDULERRESOURCESGROUPID], [ISACTIVE])
    VALUES
        (12, N'ΠΑΡΑΚΕΝΤΗΣΕΙΣ',     1, 3, 1),   -- Lab 1 (ΚΟΛΙΑΤΣΟΥ)  | Group 3 (ΥΠΕΡΗΧΩΝ)
        (16, N'ΥΠΕΡΗΧΟΙ 2ου-B',    1, 3, 1),   -- Lab 1 (ΚΟΛΙΑΤΣΟΥ)  | Group 3 (ΥΠΕΡΗΧΩΝ)
        (19, N'ΑΞΟΝΙΚΟΣ (Σ)',       5, 5, 1),   -- Lab 5 (ΣΕΠΟΛΙΩΝ)   | Group 5 (ΑΞΟΝΙΚΟΥ)
        (22, N'ΜΑΓΝΗΤΗΣ (Σ)',       5, 4, 1),   -- Lab 5 (ΣΕΠΟΛΙΩΝ)   | Group 4 (ΜΑΓΝΗΤΗ)
        (24, N'ΥΠΕΡΗΧΟΙ Β (Σ)',     5, 3, 1),   -- Lab 5 (ΣΕΠΟΛΙΩΝ)   | Group 3 (ΥΠΕΡΗΧΩΝ)
        (32, N'ΥΠΕΡΗΧΟΙ Α (ΑΠ)',    6, 3, 1),   -- Lab 6 (ΑΝΩ ΠΑΤΗΣΙΩΝ) | Group 3 (ΥΠΕΡΗΧΩΝ)
        (77, N'ΜΑΓΝΗΤΗΣ (Ι)',       7, 4, 1);   -- Lab 7 (ΙΛΙΟΥ)      | Group 4 (ΜΑΓΝΗΤΗ)
    PRINT 'Seed data inserted into [SCHEDULERRESOURCES].';
END
GO

-- ============================================================================
-- 11. Seed: Patients (DEMOG)
--     6 patients: mix of M/F, including patients with same-day multi-exams.
-- ============================================================================
IF NOT EXISTS (SELECT 1 FROM [dbo].[DEMOG] WHERE [DEMOGID] = 728314)
BEGIN
    INSERT INTO [dbo].[DEMOG] ([DEMOGID], [LNAME], [FNAME], [MOBILE], [EMAIL], [SEX])
    VALUES
        (728314, N'ΑΝΔΡΕΣΑΚΗ',    N'ΜΑΡΙΑ',      N'6970668784', N'mandressaki@hotmail.com', 'F'),
        (827598, N'ΓΕΩΡΓΙΟΥ',     N'ΑΣΗΜΕΝΙΑ',   N'6970668784', NULL,                       'F'),
        (576903, N'ΜΟΥΓΚΑΡΑΚΗΣ', N'ΠΑΝΑΓΙΩΤΗΣ', N'6970668784', NULL,                       'M'),
        (260603, N'ΚΑΒΑΛΗ',       N'ΙΩΑΝΝΑ',     N'6970668784', N'i.micha@progressinc.gr',  'F'),
        (344423, N'ΚΑΡΑΜΟΥΤΣΙΟΣ',N'ΔΗΜΗΤΡΙΟΣ',  N'6970668784', N'michalisp75@gmail.com',   'M'),
        (311678, N'ΚΑΤΣΟΥΛΑ',     N'ΠΑΡΑΣΚΕΥΗ',  N'6970668784', N'mary_hala@yahoo.com',     'F');
    PRINT 'Seed data inserted into [DEMOG].';
END
GO

-- ============================================================================
-- 12. Seed: Appointments (SCHEDULERDATA)
--
-- Appointments are set ~23–26 hours in the future so the reminder service
-- picks them up immediately on first run.
--
-- Test cases for multi-exam grouping:
--   ΜΟΥΓΚΑΡΑΚΗΣ: 2 appts at Lab 5 — different departments (3 + 5) → 2 SMS
--   ΚΑΒΑΛΗ:      2 appts at Lab 5 — different departments (4 + 3) → 2 SMS
-- ============================================================================
IF NOT EXISTS (SELECT 1 FROM [dbo].[SCHEDULERDATA] WHERE [SCHEDULERDATAID] = 2990743)
BEGIN
    INSERT INTO [dbo].[SCHEDULERDATA]
        ([SCHEDULERDATAID], [START], [FINISH], [RESOURCEID], [MESSAGE], [DEMOGID], [DELETED], [WARDID])
    VALUES
        -- ΑΝΔΡΕΣΑΚΗ ΜΑΡΙΑ (F) — Puncture at ΚΟΛΙΑΤΣΟΥ (Lab 1, Group 3)
        (2990743,
         CAST('2026-07-07 12:40:00' AS DATETIME),
         CAST('2026-07-07 12:50:00' AS DATETIME),
         12, N'ΦΝΑ ΘΥΡΕΟ ΦΙΛΗ κ ΠΙΠΕΡΟΠΟΥΛΟΥ ΔΩΡΕΑΝ!!!!', 728314, 0, NULL),

        -- ΓΕΩΡΓΙΟΥ ΑΣΗΜΕΝΙΑ (F) — MRI at ΙΛΙΟΥ (Lab 7, Group 4)
        (2992733,
         CAST('2026-07-07 18:00:00' AS DATETIME),
         CAST('2026-07-07 18:30:00' AS DATETIME),
         77, NULL, 827598, 0, 33549),

        -- ΜΟΥΓΚΑΡΑΚΗΣ ΠΑΝΑΓΙΩΤΗΣ (M) — Ultrasound at ΣΕΠΟΛΙΩΝ (Lab 5, Group 3)
        (2943960,
         CAST('2026-07-07 11:00:00' AS DATETIME),
         CAST('2026-07-07 11:30:00' AS DATETIME),
         24, NULL, 576903, 0, 23257),

        -- ΜΟΥΓΚΑΡΑΚΗΣ ΠΑΝΑΓΙΩΤΗΣ (M) — CT at ΣΕΠΟΛΙΩΝ same day (Lab 5, Group 5)
        -- DIFFERENT department → separate SMS
        (2943961,
         CAST('2026-07-08 12:00:00' AS DATETIME),
         CAST('2026-07-08 12:30:00' AS DATETIME),
         19, NULL, 576903, 0, 23257),

        -- ΚΑΒΑΛΗ ΙΩΑΝΝΑ (F) — MRI at ΣΕΠΟΛΙΩΝ (Lab 5, Group 4)
        (2941823,
         CAST('2026-07-09 13:00:00' AS DATETIME),
         CAST('2026-07-09 13:30:00' AS DATETIME),
         22, NULL, 260603, 0, 20145),

        -- ΚΑΒΑΛΗ ΙΩΑΝΝΑ (F) — Ultrasound at ΣΕΠΟΛΙΩΝ same day (Lab 5, Group 3)
        -- DIFFERENT department → separate SMS
        (2941824,
         CAST('2026-07-10 14:00:00' AS DATETIME),
         CAST('2026-07-10 14:30:00' AS DATETIME),
         24, NULL, 260603, 0, 20145),

        -- ΚΑΡΑΜΟΥΤΣΙΟΣ ΔΗΜΗΤΡΙΟΣ (M) — Ultrasound at ΚΟΛΙΑΤΣΟΥ (Lab 1, Group 3)
        (2956163,
         CAST('2026-07-11 09:30:00' AS DATETIME),
         CAST('2026-07-11 10:00:00' AS DATETIME),
         16, N'2606036558079', 344423, 0, 25241),

        -- ΚΑΤΣΟΥΛΑ ΠΑΡΑΣΚΕΥΗ (F) — Ultrasound at ΑΝΩ ΠΑΤΗΣΙΩΝ (Lab 6, Group 3)
        (2945443,
         CAST('2026-07-12 10:30:00' AS DATETIME),
         CAST('2026-07-12 11:00:00' AS DATETIME),
         32, N'ΘΥΡ - ΤΡΑΧΗΛΟΥ ΜΑΖΙ 50Ε ΕΝΗΜΕΡΗ ΧΑΛΚΙΔΟΣ', 311678, 0, 9362),

        -- MORE DUMMY APPOINTMENTS FOR TESTING --
        -- ΚΑΡΑΜΟΥΤΣΙΟΣ ΔΗΜΗΤΡΙΟΣ (M) — Puncture at ΚΟΛΙΑΤΣΟΥ (Lab 1, Group 3)
        (3000001,
         CAST('2026-07-07 14:30:00' AS DATETIME),
         CAST('2026-07-07 15:00:00' AS DATETIME),
         12, NULL, 344423, 0, NULL),

        -- ΚΑΤΣΟΥΛΑ ΠΑΡΑΣΚΕΥΗ (F) — MRI at ΙΛΙΟΥ (Lab 7, Group 4)
        (3000002,
         CAST('2026-07-07 09:00:00' AS DATETIME),
         CAST('2026-07-07 09:30:00' AS DATETIME),
         77, NULL, 311678, 0, NULL),

        -- ΑΝΔΡΕΣΑΚΗ ΜΑΡΙΑ (F) — CT at ΣΕΠΟΛΙΩΝ (Lab 5, Group 5)
        (3000003,
         CAST('2026-07-08 10:00:00' AS DATETIME),
         CAST('2026-07-08 10:30:00' AS DATETIME),
         19, NULL, 728314, 0, NULL),

        -- ΓΕΩΡΓΙΟΥ ΑΣΗΜΕΝΙΑ (F) — Ultrasound at ΣΕΠΟΛΙΩΝ (Lab 5, Group 3)
        (3000004,
         CAST('2026-07-09 11:15:00' AS DATETIME),
         CAST('2026-07-09 11:45:00' AS DATETIME),
         24, NULL, 827598, 0, NULL),

        -- ΜΟΥΓΚΑΡΑΚΗΣ ΠΑΝΑΓΙΩΤΗΣ (M) — Ultrasound at ΑΝΩ ΠΑΤΗΣΙΩΝ (Lab 6, Group 3)
        (3000005,
         CAST('2026-07-07 15:00:00' AS DATETIME),
         CAST('2026-07-07 15:30:00' AS DATETIME),
         32, NULL, 576903, 0, NULL),

        -- ΚΑΒΑΛΗ ΙΩΑΝΝΑ (F) — Ultrasound at ΚΟΛΙΑΤΣΟΥ (Lab 1, Group 3)
        (3000006,
         CAST('2026-07-08 09:00:00' AS DATETIME),
         CAST('2026-07-08 09:30:00' AS DATETIME),
         16, NULL, 260603, 0, NULL);

    PRINT 'Seed data inserted into [SCHEDULERDATA].';
END
GO

-- ============================================================================
-- 13. Seed: Exam codes (SCHEDULERDATAEXAM)
--     Raw Slis codes — normalized by ExamNameMap in the sync SP.
-- ============================================================================
IF NOT EXISTS (SELECT 1 FROM [dbo].[SCHEDULERDATAEXAM] WHERE [SCHEDULERDATAID] = 2990743)
BEGIN
    INSERT INTO [dbo].[SCHEDULERDATAEXAM] ([SCHEDULERDATAID], [EXAMSTRCODE])
    VALUES
        (2990743, N'ΠΑΡΑΚΕΝΤΗΣΕΙΣ ΠΑΡΑΚ ΘΥΡΕΟΕΙΔ'),   -- ΑΝΔΡΕΣΑΚΗ
        (2992733, N'MRI ΟΜΣΣ'),                         -- ΓΕΩΡΓΙΟΥ
        (2943960, N'ΥΠ ΑΝΩ ΚΟΙΛΙΑΣ'),                  -- ΜΟΥΓΚΑΡΑΚΗΣ #1
        (2943961, N'ΑΞ ΤΟΜΟ ΘΩΡΑΚΟΣ'),                 -- ΜΟΥΓΚΑΡΑΚΗΣ #2 (same day, diff dept)
        (2941823, N'MRI ΓΟΝΑΤΟΣ ΔΕΞ'),                 -- ΚΑΒΑΛΗ #1
        (2941824, N'ΥΠ ΚΑΤΩ ΚΟΙΛ ΓΥ'),                -- ΚΑΒΑΛΗ #2 (same day, diff dept)
        (2956163, N'ΥΠ ΘΥΡΕΟΕΙΔΟΥΣ'),                  -- ΚΑΡΑΜΟΥΤΣΙΟΣ
        (2945443, N'ΥΠ ΜΑΣΤΩΝ'),                       -- ΚΑΤΣΟΥΛΑ
        (3000001, N'ΠΑΡΑΚΕΝΤΗΣΕΙΣ ΠΑΡΑΚ ΘΥΡΕΟΕΙΔ'),    -- ΚΑΡΑΜΟΥΤΣΙΟΣ (new)
        (3000002, N'MRI ΟΜΣΣ'),                        -- ΚΑΤΣΟΥΛΑ (new)
        (3000003, N'ΑΞ ΤΟΜΟ ΘΩΡΑΚΟΣ'),                 -- ΑΝΔΡΕΣΑΚΗ (new)
        (3000004, N'ΥΠ ΑΝΩ ΚΟΙΛΙΑΣ'),                  -- ΓΕΩΡΓΙΟΥ (new)
        (3000005, N'ΥΠ ΘΥΡΕΟΕΙΔΟΥΣ'),                  -- ΜΟΥΓΚΑΡΑΚΗΣ (new)
        (3000006, N'ΥΠ ΜΑΣΤΩΝ');                       -- ΚΑΒΑΛΗ (new)
    PRINT 'Seed data inserted into [SCHEDULERDATAEXAM].';
END
GO

PRINT '========================================';
PRINT 'Mock LISKOSMO setup complete.';
PRINT '';
PRINT 'Multi-exam / multi-department test cases:';
PRINT '  ΜΟΥΓΚΑΡΑΚΗΣ: ΥΠ ΑΝΩ ΚΟΙΛΙΑΣ (Υπερήχων) + ΑΞ ΤΟΜΟ (Αξονικού) at Σεπολίων → 2 SMS';
PRINT '  ΚΑΒΑΛΗ:      MRI ΓΟΝΑΤΟΣ (Μαγνητή)    + ΥΠ ΚΑΤΩ ΚΟΙΛ (Υπερήχων) at Σεπολίων → 2 SMS';
PRINT '========================================';
GO
