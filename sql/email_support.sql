-- ============================================================================
-- KosmoSMS — Migration: Add Email Support
-- ============================================================================
-- Adds the EmailStatus column to the Appointments table to track one-time
-- email sending. Values: NULL (pending), 'sent', 'no_email', 'failed'
-- ============================================================================

USE [KosmoSMS];
GO

IF NOT EXISTS (
    SELECT * FROM sys.columns 
    WHERE object_id = OBJECT_ID(N'[dbo].[Appointments]') AND name = 'EmailStatus'
)
BEGIN
    ALTER TABLE [dbo].[Appointments] 
    ADD [EmailStatus] NVARCHAR(50) NULL;
    
    PRINT 'Column [EmailStatus] added to [Appointments] table.';
END
ELSE
BEGIN
    PRINT 'Column [EmailStatus] already exists in [Appointments] table.';
END
GO
