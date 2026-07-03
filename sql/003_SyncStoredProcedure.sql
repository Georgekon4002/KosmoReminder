-- ============================================================================
-- KosmoSMS — Sync Stored Procedure (Local LISKOSMO)
-- ============================================================================
-- Syncs appointments from LISKOSMO into KosmoSMS.
-- Uses LabNameMap    → resolves Slis LABORATORYID to our pretty LabID.
-- Uses DepartmentMap → normalizes SCHEDULERRESOURCESGROUP to display name.
--
-- NOTE: ExamNameMap and the SCHEDULERDATAEXAM JOIN have been removed.
-- The message template uses {Department}, not {ExamType}.
-- ============================================================================

USE [KosmoSMS];
GO

-- ============================================================================
-- Helper Table: DepartmentMap
-- ============================================================================
-- Maps LISKOSMO.SCHEDULERRESOURCESGROUP.SCHEDULERRESOURCESGROUPID to a
-- patient-facing department name shown in the SMS body.
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[DepartmentMap]') AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[DepartmentMap] (
        [SlisGroupID]  INT            NOT NULL,
        [DisplayName]  NVARCHAR(200)  NOT NULL,

        CONSTRAINT [PK_DepartmentMap] PRIMARY KEY CLUSTERED ([SlisGroupID])
    );
    PRINT 'Table [DepartmentMap] created.';
END
GO

-- Seed / upsert all known department groups (safe to re-run)
MERGE [dbo].[DepartmentMap] AS target
USING (VALUES
    (1,  N'Τμήμα Μαστογραφίας'),
    (2,  N'Τμήμα Καρδιολογικού'),
    (3,  N'Τμήμα Υπερήχων'),
    (4,  N'Τμήμα Μαγνητικής Τομογραφίας'),
    (5,  N'Τμήμα Αξονικού'),
    (6,  N'Τμήμα Μικροβιολογικού'),
    (7,  N'Τμήμα Γαστρεντερολογικού'),
    (14, N'Τμήμα Ιατρών Ειδικοτήτων'),
    (15, N'Τμήμα Πυρηνικής')
) AS source ([SlisGroupID], [DisplayName])
ON target.[SlisGroupID] = source.[SlisGroupID]
WHEN MATCHED     THEN UPDATE SET target.[DisplayName] = source.[DisplayName]
WHEN NOT MATCHED THEN INSERT ([SlisGroupID], [DisplayName])
                      VALUES (source.[SlisGroupID], source.[DisplayName]);

PRINT 'DepartmentMap seeded/updated.';
GO

-- ============================================================================
-- Main Sync Stored Procedure
-- ============================================================================
CREATE OR ALTER PROCEDURE [dbo].[usp_SyncAppointmentsFromSlis]
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @RowsAffected  INT = 0;
    DECLARE @RunAt         DATETIME2(0) = SYSUTCDATETIME();
    DECLARE @ErrorMessage  NVARCHAR(MAX);

    BEGIN TRY
        -- =======================================================
        -- Step 1: Pull appointments from LISKOSMO
        -- =======================================================
        IF OBJECT_ID('tempdb..#SlisChanges') IS NOT NULL
            DROP TABLE #SlisChanges;

        SELECT
            SC.SCHEDULERDATAID                              AS SlisAppointmentID,
            SC.DEMOGID                                      AS PatientID,
            D.FNAME                                         AS PatientFirstName,
            D.LNAME                                         AS PatientLastName,
            D.MOBILE                                        AS PatientPhone,
            D.EMAIL                                         AS PatientEmail,
            D.SEX                                           AS PatientSex,
            SC.[START]                                      AS AppointmentDateTime,
            -- Normalize department name via mapping table;
            -- fall back to 'Τμήμα ' + raw GROUPNAME if not mapped
            COALESCE(
                dmap.DisplayName,
                CASE WHEN SRG.GROUPNAME IS NOT NULL
                     THEN N'Τμήμα ' + SRG.GROUPNAME
                     ELSE NULL END
            )                                               AS Department,
            CASE WHEN SC.DELETED = 1 THEN N'Cancelled' ELSE N'Scheduled' END AS [Status],
            -- Map Slis lab → our own LabID via LabNameMap
            lnm.KosmoLabID                                  AS LabID
        INTO #SlisChanges
        FROM [LISKOSMO].[dbo].[SCHEDULERDATA] AS SC WITH (NOLOCK)
        INNER JOIN [LISKOSMO].[dbo].[SCHEDULERRESOURCES] AS SR WITH (NOLOCK)
            ON SR.SCHEDULERRESOURCESID = SC.RESOURCEID
        INNER JOIN [LISKOSMO].[dbo].[DEMOG] AS D WITH (NOLOCK)
            ON D.DEMOGID = SC.DEMOGID
        LEFT JOIN [LISKOSMO].[dbo].[SCHEDULERRESOURCESGROUP] AS SRG WITH (NOLOCK)
            ON SRG.SCHEDULERRESOURCESGROUPID = SR.SCHEDULERRESOURCESGROUPID
        LEFT JOIN [KosmoSMS].[dbo].[LabNameMap] AS lnm
            ON lnm.SlisLabID = SR.LABORATORYID
        LEFT JOIN [KosmoSMS].[dbo].[DepartmentMap] AS dmap
            ON dmap.SlisGroupID = SR.SCHEDULERRESOURCESGROUPID
        WHERE SC.DEMOGID IS NOT NULL
          AND SC.DELETED = 0;

        -- =======================================================
        -- Step 2: Upsert Patients (including Sex)
        -- =======================================================
        BEGIN TRANSACTION;

            MERGE [dbo].[Patients] AS target
            USING (
                SELECT DISTINCT PatientID, PatientFirstName, PatientLastName,
                                PatientPhone, PatientEmail, PatientSex
                FROM #SlisChanges
                WHERE PatientID IS NOT NULL
            ) AS source
            ON target.[PatientID] = source.[PatientID]
            WHEN MATCHED THEN
                UPDATE SET
                    target.[FirstName] = source.[PatientFirstName],
                    target.[LastName]  = source.[PatientLastName],
                    target.[Phone]     = source.[PatientPhone],
                    target.[Email]     = source.[PatientEmail],
                    target.[Sex]       = source.[PatientSex]
            WHEN NOT MATCHED BY TARGET THEN
                INSERT ([PatientID], [FirstName], [LastName], [Phone], [Email], [Sex])
                VALUES (source.[PatientID], source.[PatientFirstName],
                        source.[PatientLastName], source.[PatientPhone],
                        source.[PatientEmail], source.[PatientSex]);

        -- =======================================================
        -- Step 3: MERGE Appointments
        -- Labs are NOT synced from Slis — managed via LabNameMap.
        -- ExamType is not populated (no longer used in the SMS).
        -- =======================================================
            MERGE [dbo].[Appointments] AS target
            USING #SlisChanges AS source
                ON target.[SlisAppointmentID] = source.[SlisAppointmentID]
            WHEN MATCHED THEN
                UPDATE SET
                    target.[PatientID]           = source.[PatientID],
                    target.[AppointmentDateTime] = source.[AppointmentDateTime],
                    target.[Department]          = source.[Department],
                    target.[Status]              = source.[Status],
                    target.[LabID]               = source.[LabID],
                    target.[LastSyncedAt]        = SYSUTCDATETIME()
            WHEN NOT MATCHED BY TARGET THEN
                INSERT ([SlisAppointmentID], [PatientID], [AppointmentDateTime],
                        [Department], [Status], [LabID], [LastSyncedAt])
                VALUES (source.[SlisAppointmentID], source.[PatientID],
                        source.[AppointmentDateTime], source.[Department],
                        source.[Status], source.[LabID], SYSUTCDATETIME());

            SET @RowsAffected = @@ROWCOUNT;

        -- =======================================================
        -- Step 4: Update SyncState
        -- =======================================================
            UPDATE [dbo].[SyncState]
            SET [LastRunAt] = SYSUTCDATETIME()
            WHERE [TableName] = N'Appointments';

        COMMIT TRANSACTION;

        INSERT INTO [dbo].[SyncLog] ([RunAt], [RowsProcessed], [Status], [ErrorMessage])
        VALUES (@RunAt, @RowsAffected, N'Success', NULL);

        DROP TABLE IF EXISTS #SlisChanges;
        PRINT 'Sync completed. Rows affected: ' + CAST(@RowsAffected AS NVARCHAR(10));

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        SET @ErrorMessage = ERROR_MESSAGE();

        INSERT INTO [dbo].[SyncLog] ([RunAt], [RowsProcessed], [Status], [ErrorMessage])
        VALUES (@RunAt, 0, N'Failed', @ErrorMessage);

        DROP TABLE IF EXISTS #SlisChanges;
        THROW;
    END CATCH
END
GO

-- ============================================================================
-- Verification query
-- ============================================================================
-- SELECT p.FirstName + ' ' + p.LastName AS Patient,
--        p.Sex, a.Department, a.AppointmentDateTime, l.LabName, l.LabAddress
-- FROM dbo.Appointments a
-- JOIN dbo.Patients p ON p.PatientID = a.PatientID
-- LEFT JOIN dbo.Labs l ON l.LabID = a.LabID
-- ORDER BY a.AppointmentDateTime;
-- ============================================================================

PRINT '========================================';
PRINT 'Sync SP created/updated.';
PRINT 'Run: EXEC [dbo].[usp_SyncAppointmentsFromSlis];';
PRINT '========================================';
GO
