USE [LISKOSMO];
GO

-- ============================================================================
-- 8. Seed: Department groups
-- ============================================================================
MERGE [dbo].[SCHEDULERRESOURCESGROUP] AS target
USING (VALUES
    (1,  N'Α/Α-Μ.Ο.Π-ΜΑΣΤΟ'),
    (2,  N'ΚΑΡΔΙΟΛΟΓΙΚΟ'),
    (3,  N'ΥΠΕΡΗΧΩΝ'),
    (4,  N'ΜΑΓΝΗΤΗ'),
    (5,  N'ΑΞΟΝΙΚΟΥ'),
    (6,  N'ΜΙΚΡΟΒΙΟΛΟΓΙΚΟ'),
    (7,  N'ΓΑΣΤΡΕΝΤΕΡΟΛΟΓΙΚΟ'),
    (14, N'ΙΑΤΡΟΙ ΕΙΔΙΚΟΤΗΤΩΝ'),
    (15, N'ΠΥΡΗΝΙΚΗΣ')
) AS source ([SCHEDULERRESOURCESGROUPID], [GROUPNAME])
ON target.[SCHEDULERRESOURCESGROUPID] = source.[SCHEDULERRESOURCESGROUPID]
WHEN MATCHED THEN
    UPDATE SET target.[GROUPNAME] = source.[GROUPNAME]
WHEN NOT MATCHED THEN
    INSERT ([SCHEDULERRESOURCESGROUPID], [GROUPNAME])
    VALUES (source.[SCHEDULERRESOURCESGROUPID], source.[GROUPNAME]);

PRINT 'Seed data merged into [SCHEDULERRESOURCESGROUP].';
GO

-- ============================================================================
-- 9. Seed: Labs (matching exact data from the live Slis system)
-- ============================================================================
MERGE [dbo].[LABORATORY] AS target
USING (VALUES
    (1, N'ΚΟΛΙΑΤΣΟΥ',    N'ΠΑΤΗΣΙΩΝ 237 – ΤΚ 11254',   1),
    (2, N'ΠΟΛΥΙΑΤΡΕΙΟ',  N'ΠΑΤΗΣΙΩΝ 237 – ΤΚ 11254',   1),
    (5, N'ΣΕΠΟΛΙΩΝ',     N'ΑΜΦΙΑΡΑΟΥ 165 – ΤΚ 10443',  1),
    (6, N'ΑΝΩ ΠΑΤΗΣΙΩΝ', N'ΧΑΛΚΙΔΟΣ 12 – ΤΚ 11143',   1),
    (7, N'ΙΛΙΟΥ',        N'Λ.ΘΗΒΩΝ 439 – ΤΚ 13121',    1)
) AS source ([LABORATORYID], [FNAME], [ADDRESS], [ISACTIVE])
ON target.[LABORATORYID] = source.[LABORATORYID]
WHEN MATCHED THEN
    UPDATE SET target.[FNAME] = source.[FNAME], target.[ADDRESS] = source.[ADDRESS], target.[ISACTIVE] = source.[ISACTIVE]
WHEN NOT MATCHED THEN
    INSERT ([LABORATORYID], [FNAME], [ADDRESS], [ISACTIVE])
    VALUES (source.[LABORATORYID], source.[FNAME], source.[ADDRESS], source.[ISACTIVE]);

PRINT 'Seed data merged into [LABORATORY].';
GO

-- ============================================================================
-- 10. Seed: Exam rooms / devices (SCHEDULERRESOURCES)
--     Each resource belongs to a lab and a department group.
-- ============================================================================
MERGE [dbo].[SCHEDULERRESOURCES] AS target
USING (VALUES
    (12, N'ΠΑΡΑΚΕΝΤΗΣΕΙΣ',     1, 3, 1),   -- Lab 1 (ΚΟΛΙΑΤΣΟΥ)  | Group 3 (ΥΠΕΡΗΧΩΝ)
    (16, N'ΥΠΕΡΗΧΟΙ 2ου-B',    1, 3, 1),   -- Lab 1 (ΚΟΛΙΑΤΣΟΥ)  | Group 3 (ΥΠΕΡΗΧΩΝ)
    (19, N'ΑΞΟΝΙΚΟΣ (Σ)',       5, 5, 1),   -- Lab 5 (ΣΕΠΟΛΙΩΝ)   | Group 5 (ΑΞΟΝΙΚΟΥ)
    (22, N'ΜΑΓΝΗΤΗΣ (Σ)',       5, 4, 1),   -- Lab 5 (ΣΕΠΟΛΙΩΝ)   | Group 4 (ΜΑΓΝΗΤΗ)
    (24, N'ΥΠΕΡΗΧΟΙ Β (Σ)',     5, 3, 1),   -- Lab 5 (ΣΕΠΟΛΙΩΝ)   | Group 3 (ΥΠΕΡΗΧΩΝ)
    (32, N'ΥΠΕΡΗΧΟΙ Α (ΑΠ)',    6, 3, 1),   -- Lab 6 (ΑΝΩ ΠΑΤΗΣΙΩΝ) | Group 3 (ΥΠΕΡΗΧΩΝ)
    (77, N'ΜΑΓΝΗΤΗΣ (Ι)',       7, 4, 1)    -- Lab 7 (ΙΛΙΟΥ)      | Group 4 (ΜΑΓΝΗΤΗ)
) AS source ([SCHEDULERRESOURCESID], [NAME], [LABORATORYID], [SCHEDULERRESOURCESGROUPID], [ISACTIVE])
ON target.[SCHEDULERRESOURCESID] = source.[SCHEDULERRESOURCESID]
WHEN MATCHED THEN
    UPDATE SET target.[NAME] = source.[NAME], target.[LABORATORYID] = source.[LABORATORYID], target.[SCHEDULERRESOURCESGROUPID] = source.[SCHEDULERRESOURCESGROUPID], target.[ISACTIVE] = source.[ISACTIVE]
WHEN NOT MATCHED THEN
    INSERT ([SCHEDULERRESOURCESID], [NAME], [LABORATORYID], [SCHEDULERRESOURCESGROUPID], [ISACTIVE])
    VALUES (source.[SCHEDULERRESOURCESID], source.[NAME], source.[LABORATORYID], source.[SCHEDULERRESOURCESGROUPID], source.[ISACTIVE]);

PRINT 'Seed data merged into [SCHEDULERRESOURCES].';
GO

-- ============================================================================
-- 11. Seed: Patients (DEMOG)
--     6 patients: mix of M/F, including patients with same-day multi-exams.
-- ============================================================================
MERGE [dbo].[DEMOG] AS target
USING (VALUES
    (728314, N'ΑΝΔΡΕΣΑΚΗ',    N'ΜΑΡΙΑ',      N'6970668784', N'georgekon1@hotmail.gr', 'F'),
    (827598, N'ΓΕΩΡΓΙΟΥ',     N'ΑΣΗΜΕΝΙΑ',   N'6970668784', NULL,                       'F'),
    (576903, N'ΜΟΥΓΚΑΡΑΚΗΣ', N'ΠΑΝΑΓΙΩΤΗΣ', N'6970668784', NULL,                       'M'),
    (260603, N'ΚΑΒΑΛΗ',       N'ΙΩΑΝΝΑ',     N'6970668784', N'georgekon12@gmail.com',  'F'),
    (344423, N'ΚΑΡΑΜΟΥΤΣΙΟΣ',N'ΔΗΜΗΤΡΙΟΣ',  N'6970668784', N'georgios.konstantopoulos@best-eu.org',   'M'),
    (311678, N'ΚΑΤΣΟΥΛΑ',     N'ΠΑΡΑΣΚΕΥΗ',  N'6970668784', N'el22104@mail.ntua.gr',     'F')
) AS source ([DEMOGID], [LNAME], [FNAME], [MOBILE], [EMAIL], [SEX])
ON target.[DEMOGID] = source.[DEMOGID]
WHEN MATCHED THEN
    UPDATE SET target.[LNAME] = source.[LNAME], target.[FNAME] = source.[FNAME], target.[MOBILE] = source.[MOBILE], target.[EMAIL] = source.[EMAIL], target.[SEX] = source.[SEX]
WHEN NOT MATCHED THEN
    INSERT ([DEMOGID], [LNAME], [FNAME], [MOBILE], [EMAIL], [SEX])
    VALUES (source.[DEMOGID], source.[LNAME], source.[FNAME], source.[MOBILE], source.[EMAIL], source.[SEX]);

PRINT 'Seed data merged into [DEMOG].';
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
MERGE [dbo].[SCHEDULERDATA] AS target
USING (VALUES
    -- ΑΝΔΡΕΣΑΚΗ ΜΑΡΙΑ (F) — Puncture at ΚΟΛΙΑΤΣΟΥ (Lab 1, Group 3)
    (2990743, CAST('2026-07-07 12:40:00' AS DATETIME), CAST('2026-07-07 12:50:00' AS DATETIME), 12, N'ΦΝΑ ΘΥΡΕΟ ΦΙΛΗ κ ΠΙΠΕΡΟΠΟΥΛΟΥ ΔΩΡΕΑΝ!!!!', 728314, 0, NULL),

    -- ΓΕΩΡΓΙΟΥ ΑΣΗΜΕΝΙΑ (F) — MRI at ΙΛΙΟΥ (Lab 7, Group 4)
    (2992733, CAST('2026-07-07 18:00:00' AS DATETIME), CAST('2026-07-07 18:30:00' AS DATETIME), 77, NULL, 827598, 0, 33549),

    -- ΜΟΥΓΚΑΡΑΚΗΣ ΠΑΝΑΓΙΩΤΗΣ (M) — Ultrasound at ΣΕΠΟΛΙΩΝ (Lab 5, Group 3)
    (2943960, CAST('2026-07-07 11:00:00' AS DATETIME), CAST('2026-07-07 11:30:00' AS DATETIME), 24, NULL, 576903, 0, 23257),

    -- ΜΟΥΓΚΑΡΑΚΗΣ ΠΑΝΑΓΙΩΤΗΣ (M) — CT at ΣΕΠΟΛΙΩΝ same day (Lab 5, Group 5)
    (2943961, CAST('2026-07-08 12:00:00' AS DATETIME), CAST('2026-07-08 12:30:00' AS DATETIME), 19, NULL, 576903, 0, 23257),

    -- ΚΑΒΑΛΗ ΙΩΑΝΝΑ (F) — MRI at ΣΕΠΟΛΙΩΝ (Lab 5, Group 4)
    (2941823, CAST('2026-07-09 13:00:00' AS DATETIME), CAST('2026-07-09 13:30:00' AS DATETIME), 22, NULL, 260603, 0, 20145),

    -- ΚΑΒΑΛΗ ΙΩΑΝΝΑ (F) — Ultrasound at ΣΕΠΟΛΙΩΝ same day (Lab 5, Group 3)
    (2941824, CAST('2026-07-10 14:00:00' AS DATETIME), CAST('2026-07-10 14:30:00' AS DATETIME), 24, NULL, 260603, 0, 20145),

    -- ΚΑΡΑΜΟΥΤΣΙΟΣ ΔΗΜΗΤΡΙΟΣ (M) — Ultrasound at ΚΟΛΙΑΤΣΟΥ (Lab 1, Group 3)
    (2956163, CAST('2026-07-11 09:30:00' AS DATETIME), CAST('2026-07-11 10:00:00' AS DATETIME), 16, N'2606036558079', 344423, 0, 25241),

    -- ΚΑΤΣΟΥΛΑ ΠΑΡΑΣΚΕΥΗ (F) — Ultrasound at ΑΝΩ ΠΑΤΗΣΙΩΝ (Lab 6, Group 3)
    (2945443, CAST('2026-07-12 10:30:00' AS DATETIME), CAST('2026-07-12 11:00:00' AS DATETIME), 32, N'ΘΥΡ - ΤΡΑΧΗΛΟΥ ΜΑΖΙ 50Ε ΕΝΗΜΕΡΗ ΧΑΛΚΙΔΟΣ', 311678, 0, 9362),

    -- MORE DUMMY APPOINTMENTS FOR TESTING --
    (3000001, CAST('2026-07-07 14:30:00' AS DATETIME), CAST('2026-07-07 15:00:00' AS DATETIME), 12, NULL, 344423, 0, NULL),
    (3000002, CAST('2026-07-07 09:00:00' AS DATETIME), CAST('2026-07-07 09:30:00' AS DATETIME), 77, NULL, 311678, 0, NULL),
    (3000003, CAST('2026-07-08 10:00:00' AS DATETIME), CAST('2026-07-08 10:30:00' AS DATETIME), 19, NULL, 728314, 0, NULL),
    (3000004, CAST('2026-07-09 11:15:00' AS DATETIME), CAST('2026-07-09 11:45:00' AS DATETIME), 24, NULL, 827598, 0, NULL),
    (3000005, CAST('2026-07-07 15:00:00' AS DATETIME), CAST('2026-07-07 15:30:00' AS DATETIME), 32, NULL, 576903, 0, NULL),
    (3000006, CAST('2026-07-08 09:00:00' AS DATETIME), CAST('2026-07-08 09:30:00' AS DATETIME), 16, NULL, 260603, 0, NULL),
    (3000010, CAST('2026-07-02 10:00:00' AS DATETIME), CAST('2026-07-02 10:30:00' AS DATETIME), 19, NULL, 576903, 0, NULL),
    (3000011, CAST('2026-07-03 11:00:00' AS DATETIME), CAST('2026-07-03 11:30:00' AS DATETIME), 24, NULL, 311678, 0, NULL),
    (3000012, CAST('2026-07-15 09:00:00' AS DATETIME), CAST('2026-07-15 09:30:00' AS DATETIME), 77, NULL, 827598, 0, NULL),
    (3000013, CAST('2026-07-16 12:00:00' AS DATETIME), CAST('2026-07-16 12:30:00' AS DATETIME), 32, NULL, 728314, 0, NULL)
) AS source ([SCHEDULERDATAID], [START], [FINISH], [RESOURCEID], [MESSAGE], [DEMOGID], [DELETED], [WARDID])
ON target.[SCHEDULERDATAID] = source.[SCHEDULERDATAID]
WHEN MATCHED THEN
    UPDATE SET target.[START] = source.[START], target.[FINISH] = source.[FINISH], target.[RESOURCEID] = source.[RESOURCEID], target.[MESSAGE] = source.[MESSAGE], target.[DEMOGID] = source.[DEMOGID], target.[DELETED] = source.[DELETED], target.[WARDID] = source.[WARDID]
WHEN NOT MATCHED THEN
    INSERT ([SCHEDULERDATAID], [START], [FINISH], [RESOURCEID], [MESSAGE], [DEMOGID], [DELETED], [WARDID])
    VALUES (source.[SCHEDULERDATAID], source.[START], source.[FINISH], source.[RESOURCEID], source.[MESSAGE], source.[DEMOGID], source.[DELETED], source.[WARDID]);

PRINT 'Seed data merged into [SCHEDULERDATA].';
GO

-- ============================================================================
-- 13. Seed: Exam codes (SCHEDULERDATAEXAM)
--     Raw Slis codes — normalized by ExamNameMap in the sync SP.
-- ============================================================================
MERGE [dbo].[SCHEDULERDATAEXAM] AS target
USING (VALUES
    (2990743, N'ΠΑΡΑΚΕΝΤΗΣΕΙΣ ΠΑΡΑΚ ΘΥΡΕΟΕΙΔ'),
    (2992733, N'MRI ΟΜΣΣ'),
    (2943960, N'ΥΠ ΑΝΩ ΚΟΙΛΙΑΣ'),
    (2943961, N'ΑΞ ΤΟΜΟ ΘΩΡΑΚΟΣ'),
    (2941823, N'MRI ΓΟΝΑΤΟΣ ΔΕΞ'),
    (2941824, N'ΥΠ ΚΑΤΩ ΚΟΙΛ ΓΥ'),
    (2956163, N'ΥΠ ΘΥΡΕΟΕΙΔΟΥΣ'),
    (2945443, N'ΥΠ ΜΑΣΤΩΝ'),
    (3000001, N'ΠΑΡΑΚΕΝΤΗΣΕΙΣ ΠΑΡΑΚ ΘΥΡΕΟΕΙΔ'),
    (3000002, N'MRI ΟΜΣΣ'),
    (3000003, N'ΑΞ ΤΟΜΟ ΘΩΡΑΚΟΣ'),
    (3000004, N'ΥΠ ΑΝΩ ΚΟΙΛΙΑΣ'),
    (3000005, N'ΥΠ ΘΥΡΕΟΕΙΔΟΥΣ'),
    (3000006, N'ΥΠ ΜΑΣΤΩΝ'),
    (3000010, N'ΑΞ ΤΟΜΟ ΘΩΡΑΚΟΣ'),
    (3000011, N'ΥΠ ΑΝΩ ΚΟΙΛΙΑΣ'),
    (3000012, N'MRI ΟΜΣΣ'),
    (3000013, N'ΥΠ ΜΑΣΤΩΝ')
) AS source ([SCHEDULERDATAID], [EXAMSTRCODE])
ON target.[SCHEDULERDATAID] = source.[SCHEDULERDATAID] AND target.[EXAMSTRCODE] = source.[EXAMSTRCODE]
WHEN NOT MATCHED THEN
    INSERT ([SCHEDULERDATAID], [EXAMSTRCODE])
    VALUES (source.[SCHEDULERDATAID], source.[EXAMSTRCODE]);

PRINT 'Seed data merged into [SCHEDULERDATAEXAM].';
GO

PRINT '========================================';
PRINT 'Mock LISKOSMO setup complete.';
PRINT '';
GO
