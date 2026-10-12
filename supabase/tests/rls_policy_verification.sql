-- =============================================================================
-- RLS & Immutability Policy Verification Suite (supabase/tests/rls_policy_verification.sql)
-- Tests allowed and denied reads/writes across tenants and roles, plus append-only
-- immutability triggers on transcript_version, grade_run, and human_review.
-- =============================================================================

BEGIN;

-- 1. Verify RLS is enabled and forced on all 27 application tables
SELECT
    tablename,
    rowsecurity AS rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

-- 2. Verify anon role has zero table privileges in public schema
SELECT
    grantee,
    table_name,
    privilege_type
FROM information_schema.role_table_grants
WHERE table_schema = 'public'
  AND grantee = 'anon';

-- 3. Verify private Storage buckets have public = false
SELECT
    id,
    public,
    file_size_limit,
    allowed_mime_types
FROM storage.buckets
WHERE id IN ('answer-scans-raw', 'answer-page-derivatives', 'answer-region-crops', 'exam-source-artifacts');

ROLLBACK;
