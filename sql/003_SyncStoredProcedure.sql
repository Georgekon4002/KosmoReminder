-- ============================================================================
-- KosmoSMS — Sync Stored Procedure (Local LISKOSMO)
-- ============================================================================
-- This procedure syncs appointments from the local LISKOSMO mock database
-- into the KosmoSMS database.
--
-- It queries LISKOSMO.DBO.* tables directly (no Linked Server needed).
-- It normalizes ugly EXAMSTRCODE values into professional Greek text.
--
-- Schedule via SQL Server Agent to run every 5-15 minutes, or run manually.
-- ============================================================================

USE [KosmoSMS];
GO

-- ============================================================================
-- Helper: Exam Name Mapping Table
-- ============================================================================
-- This table maps the raw EXAMSTRCODE values from Slis to clean,
-- professional Greek names for use in patient-facing SMS messages.
-- Add new mappings here as you encounter new exam types.
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[ExamNameMap]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[ExamNameMap] (
        [RawCode]        NVARCHAR(200)  NOT NULL,   -- Exact EXAMSTRCODE from Slis (uppercase)
        [DisplayName]    NVARCHAR(200)  NOT NULL,   -- Clean, professional Greek name

        CONSTRAINT [PK_ExamNameMap] PRIMARY KEY CLUSTERED ([RawCode])
    );
    PRINT 'Table [ExamNameMap] created.';
END
GO

-- Seed the mapping table with known exam types
-- (safe to re-run — uses MERGE to upsert)
MERGE [dbo].[ExamNameMap] AS target
USING (VALUES
    -- Ultrasound exams
    (N'ΥΠ ΑΝΩ ΚΟΙΛΙΑΣ',                     N'Υπέρηχος Άνω Κοιλίας'),
    (N'ΥΠ ΚΑΤΩ ΚΟΙΛ ΓΥ',                     N'Υπέρηχος Κάτω Κοιλίας Γυναικολογικός'),
    (N'ΥΠ ΚΑΤΩ ΚΟΙΛ ΑΝ',                     N'Υπέρηχος Κάτω Κοιλίας Ανδρολογικός'),
    (N'ΥΠ ΘΥΡΕΟΕΙΔΟΥΣ',                      N'Υπέρηχος Θυρεοειδούς'),
    (N'ΥΠ ΜΑΣΤΩΝ',                            N'Υπέρηχος Μαστών'),
    (N'US ΟΥΡ. ΚΥΣΤΗ-2',                      N'Υπέρηχος Ουροποιητικού'),
    (N'US ΤΡΑΧΗΛΟΥ',                           N'Υπέρηχος Τραχήλου'),

    -- MRI exams
    (N'MRI ΟΜΣΣ',                              N'Μαγνητική Τομογραφία ΟΜΣΣ'),
    (N'MRI ΩΜΟΥ ΔΕΞ',                         N'Μαγνητική Τομογραφία Ώμου Δεξιού'),
    (N'MRI ΩΜΟΥ ΑΡΙΣΤ',                       N'Μαγνητική Τομογραφία Ώμου Αριστερού'),
    (N'MRI ΓΟΝΑΤΟΣ ΔΕΞ',                      N'Μαγνητική Τομογραφία Γόνατος Δεξιού'),
    (N'MRI ΓΟΝΑΤΟΣ ΑΡΙ',                      N'Μαγνητική Τομογραφία Γόνατος Αριστερού'),

    -- Puncture / biopsy exams
    (N'ΠΑΡΑΚΕΝΤΗΣΕΙΣ ΠΑΡΑΚ ΘΥΡΕΟΕΙΔ',         N'Παρακέντηση Θυρεοειδούς'),
    (N'ΠΑΡΑΚ ΘΥΡΕΟΕΙΔ',                       N'Παρακέντηση Θυρεοειδούς'),

    -- CT exams
    (N'ΑΞ ΤΟΜΟ ΘΩΡΑΚΟΣ',                     N'Αξονική Τομογραφία Θώρακος'),
    (N'ΑΣΤ ΘΩΡΑΚΟΣ',                          N'Αξονική Τομογραφία Θώρακος'),

    -- Triplex / Doppler
    (N'TR ΛΑΓΟΝ ΑΡΤ',                         N'Triplex Λαγονίων Αρτηριών'),
    (N'TR ΑΡΤ ΚΑΤΩ ΑΚΡ',                      N'Triplex Αρτηριών Κάτω Άκρων'),

    -- Mammography
    (N'ΜΑΣΤΟΓΡΑΦΙΑ',                           N'Μαστογραφία'),

    -- Bone density
    (N'ΟΣΤΕΟΠΥΚΝΟΜΕΤΡΙΑ',                     N'Οστεοπυκνομετρία')
) AS source ([RawCode], [DisplayName])
ON target.[RawCode] = source.[RawCode]
WHEN NOT MATCHED THEN
    INSERT ([RawCode], [DisplayName])
    VALUES (source.[RawCode], source.[DisplayName]);

PRINT 'ExamNameMap seeded with known exam types.';
GO

-- ============================================================================
-- Main Sync Stored Procedure
-- ============================================================================

CREATE OR ALTER PROCEDURE [dbo].[usp_SyncAppointmentsFromSlis]
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    -- -------------------------------------------------------
    -- Variables
    -- -------------------------------------------------------
    DECLARE @RowsAffected   INT = 0;
    DECLARE @RunAt          DATETIME2(0) = SYSUTCDATETIME();
    DECLARE @ErrorMessage   NVARCHAR(MAX);

    BEGIN TRY
        -- =======================================================
        -- Step 1: Pull appointments from LISKOSMO into a temp table
        -- =======================================================
        -- This query mirrors the original Slis SELECT but reads
        -- directly from the local LISKOSMO database.
        -- =======================================================
        IF OBJECT_ID('tempdb..#SlisChanges') IS NOT NULL
            DROP TABLE #SlisChanges;

        SELECT
            SC.SCHEDULERDATAID                          AS SlisAppointmentID,
            SC.DEMOGID                                  AS PatientID,
            D.FNAME                                     AS PatientFirstName,
            D.LNAME                                     AS PatientLastName,
            D.MOBILE                                    AS PatientPhone,
            D.EMAIL                                     AS PatientEmail,
            SC.[START]                                  AS AppointmentDateTime,
            -- Normalize the exam name: use the mapping table if available,
            -- otherwise fall back to the raw EXAMSTRCODE as-is
            COALESCE(emap.DisplayName, SM.EXAMSTRCODE)  AS ExamType,
            CASE WHEN SC.DELETED = 1 THEN N'Cancelled' ELSE N'Scheduled' END AS [Status],
            L.LABORATORYID                              AS LabID,
            L.FNAME                                     AS LabName,
            L.[ADDRESS]                                 AS LabAddress
        INTO #SlisChanges
        FROM [LISKOSMO].[dbo].[SCHEDULERDATA] AS SC WITH (NOLOCK)
        INNER JOIN [LISKOSMO].[dbo].[SCHEDULERRESOURCES] AS SR WITH (NOLOCK)
            ON SR.SCHEDULERRESOURCESID = SC.RESOURCEID
        INNER JOIN [LISKOSMO].[dbo].[DEMOG] AS D WITH (NOLOCK)
            ON D.DEMOGID = SC.DEMOGID
        INNER JOIN [LISKOSMO].[dbo].[LABORATORY] AS L
            ON L.LABORATORYID = SR.LABORATORYID
        INNER JOIN [LISKOSMO].[dbo].[SCHEDULERDATAEXAM] AS SM WITH (NOLOCK)
            ON SM.SCHEDULERDATAID = SC.SCHEDULERDATAID
        LEFT JOIN [KosmoSMS].[dbo].[ExamNameMap] AS emap
            ON emap.RawCode = UPPER(LTRIM(RTRIM(SM.EXAMSTRCODE)))
        WHERE SC.DEMOGID IS NOT NULL
          AND SC.DELETED = 0;

        -- =======================================================
        -- Step 2: Upsert Patients from the pulled data
        -- =======================================================
        BEGIN TRANSACTION;

            MERGE [dbo].[Patients] AS target
            USING (
                SELECT DISTINCT
                    PatientID,
                    PatientFirstName,
                    PatientLastName,
                    PatientPhone,
                    PatientEmail
                FROM #SlisChanges
                WHERE PatientID IS NOT NULL
            ) AS source
            ON target.[PatientID] = source.[PatientID]
            WHEN MATCHED THEN
                UPDATE SET
                    target.[FirstName] = source.[PatientFirstName],
                    target.[LastName]  = source.[PatientLastName],
                    target.[Phone]     = source.[PatientPhone],
                    target.[Email]     = source.[PatientEmail]
            WHEN NOT MATCHED BY TARGET THEN
                INSERT ([PatientID], [FirstName], [LastName], [Phone], [Email])
                VALUES (source.[PatientID], source.[PatientFirstName],
                        source.[PatientLastName], source.[PatientPhone], source.[PatientEmail]);

        -- =======================================================
        -- Step 3: Upsert Labs from the pulled data
        -- =======================================================
            MERGE [dbo].[Labs] AS target
            USING (
                SELECT DISTINCT
                    LabID,
                    LabName,
                    LabAddress
                FROM #SlisChanges
                WHERE LabID IS NOT NULL
            ) AS source
            ON target.[LabID] = source.[LabID]
            WHEN MATCHED THEN
                UPDATE SET
                    target.[LabName]    = source.[LabName],
                    target.[LabAddress] = source.[LabAddress]
            WHEN NOT MATCHED BY TARGET THEN
                INSERT ([LabID], [LabName], [LabAddress])
                VALUES (source.[LabID], source.[LabName], source.[LabAddress]);

        -- =======================================================
        -- Step 4: MERGE into Appointments
        -- =======================================================
            MERGE [dbo].[Appointments] AS target
            USING #SlisChanges AS source
                ON target.[SlisAppointmentID] = source.[SlisAppointmentID]

            WHEN MATCHED THEN
                UPDATE SET
                    target.[PatientID]           = source.[PatientID],
                    target.[AppointmentDateTime] = source.[AppointmentDateTime],
                    target.[ExamType]            = source.[ExamType],
                    target.[Status]              = source.[Status],
                    target.[LabID]               = source.[LabID],
                    target.[LastSyncedAt]         = SYSUTCDATETIME()

            WHEN NOT MATCHED BY TARGET THEN
                INSERT ([SlisAppointmentID], [PatientID], [AppointmentDateTime],
                        [ExamType], [Status], [LabID], [LastSyncedAt])
                VALUES (source.[SlisAppointmentID], source.[PatientID],
                        source.[AppointmentDateTime], source.[ExamType],
                        source.[Status], source.[LabID], SYSUTCDATETIME());

            SET @RowsAffected = @@ROWCOUNT;

        -- =======================================================
        -- Step 5: Update SyncState
        -- =======================================================
            UPDATE [dbo].[SyncState]
            SET [LastRunAt] = SYSUTCDATETIME()
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
PRINT 'Schedule via SQL Agent or run manually:';
PRINT '  EXEC [dbo].[usp_SyncAppointmentsFromSlis];';
PRINT '========================================';
GO
