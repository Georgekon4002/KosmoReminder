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

PRINT 'Mock LISKOSMO schema setup complete.';
GO
