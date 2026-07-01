-- ============================================================================
-- KosmoSMS — Linked Server Setup Template
-- ============================================================================
-- This script creates a Linked Server pointing to the Infomed Slis SQL Server.
-- 
-- !! IMPORTANT !!
-- 1. Replace ALL placeholders marked with <<...>> before running.
-- 2. Run this on YOUR SQL Server instance (the one hosting KosmoSMS).
-- 3. The credentials used here should be READ-ONLY on the Slis database.
-- 4. Change Tracking must be enabled on the SLIS side — see notes at bottom.
-- ============================================================================

-- -------------------------------------------------------
-- Step 1: Create the Linked Server
-- -------------------------------------------------------
-- Replace <<SLIS_SERVER_NAME>> with the actual hostname or IP\instance
-- e.g., 'SLIS-SERVER\SQLEXPRESS' or '192.168.1.100'

IF NOT EXISTS (SELECT * FROM sys.servers WHERE name = N'<<SLIS_SERVER_NAME>>')
BEGIN
    EXEC sp_addlinkedserver
        @server     = N'<<SLIS_SERVER_NAME>>',
        @srvproduct = N'',
        @provider   = N'SQLNCLI11',            -- or 'MSOLEDBSQL' for newer drivers
        @datasrc    = N'<<SLIS_SERVER_NAME>>';  -- server hostname\instance

    PRINT 'Linked server [<<SLIS_SERVER_NAME>>] created.';
END
ELSE
BEGIN
    PRINT 'Linked server [<<SLIS_SERVER_NAME>>] already exists — skipping.';
END
GO

-- -------------------------------------------------------
-- Step 2: Configure login mapping (READ-ONLY credentials)
-- -------------------------------------------------------
-- Replace <<SLIS_READ_USER>> and <<SLIS_READ_PASSWORD>> with the
-- read-only SQL login credentials for the Slis database.

EXEC sp_addlinkedsrvlogin
    @rmtsrvname  = N'<<SLIS_SERVER_NAME>>',
    @useself     = N'FALSE',
    @locallogin  = NULL,                        -- applies to all local logins
    @rmtuser     = N'<<SLIS_READ_USER>>',
    @rmtpassword = N'<<SLIS_READ_PASSWORD>>';

PRINT 'Linked server login mapping configured.';
GO

-- -------------------------------------------------------
-- Step 3: Set linked server options (recommended)
-- -------------------------------------------------------
EXEC sp_serveroption
    @server  = N'<<SLIS_SERVER_NAME>>',
    @optname = N'rpc out',
    @optvalue = N'TRUE';

-- Allow distributed queries
EXEC sp_serveroption
    @server  = N'<<SLIS_SERVER_NAME>>',
    @optname = N'data access',
    @optvalue = N'TRUE';

PRINT 'Linked server options configured.';
GO

-- -------------------------------------------------------
-- Step 4: Verify connectivity
-- -------------------------------------------------------
-- Test the linked server connection (uncomment to run):
-- EXEC sp_testlinkedserver N'<<SLIS_SERVER_NAME>>';

-- Test a simple query (uncomment and adjust table/catalog names):
-- SELECT TOP 5 *
-- FROM [<<SLIS_SERVER_NAME>>].[<<SLIS_DATABASE_NAME>>].[dbo].[<<SLIS_APPOINTMENTS_TABLE>>];

GO

-- ============================================================================
-- IMPORTANT: Change Tracking must be enabled ON THE SLIS SERVER
-- ============================================================================
-- The following commands need to be executed by a DBA on the Slis SQL Server.
-- They CANNOT be run via a linked server. They are included here for reference.
--
-- Step A: Enable Change Tracking on the Slis database
-- (retention = how long change history is kept; adjust as needed)
--
--   ALTER DATABASE [<<SLIS_DATABASE_NAME>>]
--   SET CHANGE_TRACKING = ON
--   (CHANGE_RETENTION = 7 DAYS, AUTO_CLEANUP = ON);
--
-- Step B: Enable Change Tracking on the Appointments table
--
--   ALTER TABLE [<<SLIS_DATABASE_NAME>>].[dbo].[<<SLIS_APPOINTMENTS_TABLE>>]
--   ENABLE CHANGE_TRACKING
--   WITH (TRACK_COLUMNS_UPDATED = ON);
--
-- Step C: Verify Change Tracking is active
--
--   SELECT DB_NAME(database_id) AS DatabaseName, *
--   FROM sys.change_tracking_databases;
--
--   SELECT OBJECT_NAME(object_id) AS TableName, *
--   FROM sys.change_tracking_tables;
--
-- ============================================================================

PRINT '========================================';
PRINT 'Linked Server setup template complete.';
PRINT 'Remember to replace ALL <<...>> placeholders!';
PRINT '========================================';
GO
