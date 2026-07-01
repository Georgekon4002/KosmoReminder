-- ============================================================================
-- KosmoSMS — Change Tracking Sync Stored Procedure
-- ============================================================================
-- This procedure syncs appointments from Infomed Slis (via Linked Server and
-- Change Tracking) into the local KosmoSMS database.
--
-- It should be scheduled via SQL Server Agent to run every 5-15 minutes.
--
-- !! Replace ALL <<...>> placeholders before deploying !!
-- ============================================================================

USE [KosmoSMS];
GO

CREATE OR ALTER PROCEDURE [dbo].[usp_SyncAppointmentsFromSlis]
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    -- -------------------------------------------------------
    -- Configuration: replace these placeholders
    -- -------------------------------------------------------
    DECLARE @LinkedServer   NVARCHAR(128) = N'<<SLIS_SERVER_NAME>>';
    DECLARE @SlisDatabase   NVARCHAR(128) = N'<<SLIS_DATABASE_NAME>>';
    DECLARE @SlisSchema     NVARCHAR(128) = N'dbo';
    DECLARE @SlisTable      NVARCHAR(128) = N'<<SLIS_APPOINTMENTS_TABLE>>';

    -- -------------------------------------------------------
    -- Variables
    -- -------------------------------------------------------
    DECLARE @LastChangeVersion   BIGINT;
    DECLARE @CurrentVersion      BIGINT;
    DECLARE @RowsAffected        INT = 0;
    DECLARE @RunAt               DATETIME2(0) = SYSUTCDATETIME();
    DECLARE @ErrorMessage        NVARCHAR(MAX);

    BEGIN TRY
        -- =======================================================
        -- Step 1: Get the last sync version from SyncState
        -- =======================================================
        SELECT @LastChangeVersion = [LastChangeVersion]
        FROM [dbo].[SyncState]
        WHERE [TableName] = N'Appointments';

        IF @LastChangeVersion IS NULL
        BEGIN
            RAISERROR('SyncState row for "Appointments" not found. Run 001_CreateDatabase.sql first.', 16, 1);
            RETURN;
        END

        -- =======================================================
        -- Step 2: Get the current change tracking version
        --         from the remote (Slis) database
        -- =======================================================
        -- NOTE: CHANGE_TRACKING_CURRENT_VERSION() must be called
        -- in the context of the remote database. We use OPENQUERY
        -- for this since it's a scalar function.
        -- =======================================================
        DECLARE @VersionSQL NVARCHAR(MAX) = N'
            SELECT CHANGE_TRACKING_CURRENT_VERSION()';

        DECLARE @VersionResult TABLE ([CurrentVersion] BIGINT);

        INSERT INTO @VersionResult
        EXEC (@VersionSQL) AT [<<SLIS_SERVER_NAME>>];
        -- NOTE: If the above fails, you may need to use OPENQUERY:
        -- INSERT INTO @VersionResult
        -- SELECT * FROM OPENQUERY([<<SLIS_SERVER_NAME>>],
        --     'SELECT CHANGE_TRACKING_CURRENT_VERSION()');

        SELECT @CurrentVersion = [CurrentVersion] FROM @VersionResult;

        IF @CurrentVersion IS NULL
        BEGIN
            RAISERROR('Could not retrieve CHANGE_TRACKING_CURRENT_VERSION from Slis. Check linked server and Change Tracking config.', 16, 1);
            RETURN;
        END

        -- If versions match, nothing has changed
        IF @CurrentVersion = @LastChangeVersion
        BEGIN
            INSERT INTO [dbo].[SyncLog] ([RunAt], [RowsProcessed], [Status], [ErrorMessage])
            VALUES (@RunAt, 0, N'Success', N'No changes detected (version unchanged).');
            RETURN;
        END

        -- =======================================================
        -- Step 3: Pull changed rows via CHANGETABLE(CHANGES ...)
        -- =======================================================
        -- We create a temp table to hold the changes pulled from
        -- the remote server, since cross-server MERGE with
        -- CHANGETABLE can be tricky.
        -- =======================================================
        IF OBJECT_ID('tempdb..#SlisChanges') IS NOT NULL
            DROP TABLE #SlisChanges;

        CREATE TABLE #SlisChanges (
            [SlisAppointmentID]   INT            NOT NULL,
            [PatientID]           INT            NULL,
            [AppointmentDateTime] DATETIME       NULL,
            [ExamType]            NVARCHAR(200)  NULL,
            [Status]              NVARCHAR(50)   NULL,
            [LabID]               INT            NULL,
            [DocID]               INT            NULL,
            [SYS_CHANGE_OPERATION] CHAR(1)       NOT NULL   -- 'I' = Insert, 'U' = Update, 'D' = Delete
        );

        -- -------------------------------------------------------
        -- IMPORTANT: Adjust the column names below to match the
        -- actual column names in the Slis Appointments table.
        -- The SELECT list maps Slis columns → our column names.
        -- -------------------------------------------------------
        DECLARE @ChangeSQL NVARCHAR(MAX) = N'
            SELECT
                ct.<<SLIS_APPOINTMENT_ID_COLUMN>>   AS SlisAppointmentID,
                a.<<SLIS_PATIENT_ID_COLUMN>>        AS PatientID,
                a.<<SLIS_DATETIME_COLUMN>>          AS AppointmentDateTime,
                a.<<SLIS_EXAM_TYPE_COLUMN>>         AS ExamType,
                a.<<SLIS_STATUS_COLUMN>>            AS [Status],
                a.<<SLIS_LAB_ID_COLUMN>>            AS LabID,
                a.<<SLIS_DOC_ID_COLUMN>>            AS DocID,
                ct.SYS_CHANGE_OPERATION
            FROM CHANGETABLE(CHANGES ' + QUOTENAME(@SlisDatabase) + N'.' + QUOTENAME(@SlisSchema) + N'.' + QUOTENAME(@SlisTable) + N', ' + CAST(@LastChangeVersion AS NVARCHAR(20)) + N') AS ct
            LEFT JOIN ' + QUOTENAME(@SlisDatabase) + N'.' + QUOTENAME(@SlisSchema) + N'.' + QUOTENAME(@SlisTable) + N' AS a
                ON a.<<SLIS_APPOINTMENT_ID_COLUMN>> = ct.<<SLIS_APPOINTMENT_ID_COLUMN>>';

        INSERT INTO #SlisChanges
        EXEC (@ChangeSQL) AT [<<SLIS_SERVER_NAME>>];

        -- =======================================================
        -- Step 4: MERGE into local Appointments table
        -- =======================================================
        BEGIN TRANSACTION;

            MERGE [dbo].[Appointments] AS target
            USING #SlisChanges AS source
                ON target.[SlisAppointmentID] = source.[SlisAppointmentID]

            -- UPDATE existing rows (change operation = 'U' or 'I' when row already exists)
            WHEN MATCHED AND source.[SYS_CHANGE_OPERATION] IN ('U', 'I') THEN
                UPDATE SET
                    target.[PatientID]           = source.[PatientID],
                    target.[AppointmentDateTime] = source.[AppointmentDateTime],
                    target.[ExamType]            = source.[ExamType],
                    target.[Status]              = source.[Status],
                    target.[LabID]               = source.[LabID],
                    target.[DocID]               = source.[DocID],
                    target.[LastSyncedAt]         = SYSUTCDATETIME()

            -- INSERT new rows
            WHEN NOT MATCHED BY TARGET AND source.[SYS_CHANGE_OPERATION] IN ('I', 'U') THEN
                INSERT ([SlisAppointmentID], [PatientID], [AppointmentDateTime], [ExamType], [Status], [LabID], [DocID], [LastSyncedAt])
                VALUES (source.[SlisAppointmentID], source.[PatientID], source.[AppointmentDateTime],
                        source.[ExamType], source.[Status], source.[LabID], source.[DocID], SYSUTCDATETIME())

            -- DELETE rows that were deleted in Slis
            WHEN MATCHED AND source.[SYS_CHANGE_OPERATION] = 'D' THEN
                DELETE;

            SET @RowsAffected = @@ROWCOUNT;

        -- =======================================================
        -- Step 5: Update SyncState with the new version
        -- =======================================================
            UPDATE [dbo].[SyncState]
            SET [LastChangeVersion] = @CurrentVersion,
                [LastRunAt]         = SYSUTCDATETIME()
            WHERE [TableName] = N'Appointments';

        COMMIT TRANSACTION;

        -- =======================================================
        -- Step 6: Log success
        -- =======================================================
        INSERT INTO [dbo].[SyncLog] ([RunAt], [RowsProcessed], [Status], [ErrorMessage])
        VALUES (@RunAt, @RowsAffected, N'Success', NULL);

        -- Clean up
        DROP TABLE IF EXISTS #SlisChanges;

        PRINT 'Sync completed successfully. Rows affected: ' + CAST(@RowsAffected AS NVARCHAR(10));

    END TRY
    BEGIN CATCH
        -- Rollback if transaction is still open
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        SET @ErrorMessage = ERROR_MESSAGE();

        -- Log the failure
        INSERT INTO [dbo].[SyncLog] ([RunAt], [RowsProcessed], [Status], [ErrorMessage])
        VALUES (@RunAt, 0, N'Failed', @ErrorMessage);

        -- Clean up
        DROP TABLE IF EXISTS #SlisChanges;

        -- Re-raise the error
        THROW;
    END CATCH
END
GO

-- ============================================================================
-- SQL Server Agent Job Template (reference — create via SSMS or T-SQL)
-- ============================================================================
-- To schedule this SP, create a SQL Server Agent Job:
--
-- 1. Open SSMS → SQL Server Agent → Jobs → New Job
-- 2. Name: "KosmoSMS - Sync Appointments from Slis"
-- 3. Steps:
--    - Step 1: Type = T-SQL, Database = KosmoSMS
--      Command: EXEC [dbo].[usp_SyncAppointmentsFromSlis];
-- 4. Schedule:
--    - Frequency: Recurring, every 5–15 minutes
--    - During: Operating hours (e.g., 06:00 to 22:00)
-- 5. Notifications:
--    - On failure: email/page operator
--
-- Alternatively, use the T-SQL below (uncomment and adjust):
--
-- EXEC msdb.dbo.sp_add_job
--     @job_name = N'KosmoSMS_SyncAppointments',
--     @enabled = 1;
--
-- EXEC msdb.dbo.sp_add_jobstep
--     @job_name = N'KosmoSMS_SyncAppointments',
--     @step_name = N'Run Sync SP',
--     @subsystem = N'TSQL',
--     @command = N'EXEC [dbo].[usp_SyncAppointmentsFromSlis];',
--     @database_name = N'KosmoSMS';
--
-- EXEC msdb.dbo.sp_add_schedule
--     @schedule_name = N'Every10Minutes',
--     @freq_type = 4,               -- Daily
--     @freq_interval = 1,
--     @freq_subday_type = 4,        -- Minutes
--     @freq_subday_interval = 10,
--     @active_start_time = 060000,  -- 06:00
--     @active_end_time = 220000;    -- 22:00
--
-- EXEC msdb.dbo.sp_attach_schedule
--     @job_name = N'KosmoSMS_SyncAppointments',
--     @schedule_name = N'Every10Minutes';
--
-- EXEC msdb.dbo.sp_add_jobserver
--     @job_name = N'KosmoSMS_SyncAppointments';
-- ============================================================================

PRINT '========================================';
PRINT 'Sync stored procedure created/updated.';
PRINT 'Replace <<...>> placeholders and schedule via SQL Agent.';
PRINT '========================================';
GO
