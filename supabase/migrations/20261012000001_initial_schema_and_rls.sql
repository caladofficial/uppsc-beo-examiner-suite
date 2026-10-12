-- =============================================================================
-- Migration: 20261012000001_initial_schema_and_rls.sql
-- Purpose: Tenant-scoped schema, immutable versioning, pgmq queues, private
--          Storage buckets, table privilege revocations, and Row-Level Security
--          for UPPSC BEO Mains Answer-Sheet Scanner & Rubric Grader.
-- NOTE: Do NOT apply to production without explicit owner sign-off.
-- =============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pgmq";

-- -----------------------------------------------------------------------------
-- 1. Core Tenant & Role Types
-- -----------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE public.app_role AS ENUM ('tenant_admin', 'senior_teacher', 'examiner', 'candidate', 'auditor');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE public.paper_status AS ENUM ('draft_import', 'draft_requires_teacher_approval', 'published_v1', 'archived');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE public.job_status AS ENUM ('queued', 'processing', 'review_needed', 'completed', 'failed', 'quarantined');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS public.tenant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    kms_key_arn TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.user_profile (
    id UUID PRIMARY KEY, -- matches auth.users.id
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    pseudonym_code TEXT NOT NULL,
    display_name TEXT NOT NULL,
    mfa_verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, pseudonym_code)
);

CREATE TABLE IF NOT EXISTS public.user_role_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE CASCADE,
    role public.app_role NOT NULL,
    granted_by UUID REFERENCES public.user_profile(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id, role)
);

-- -----------------------------------------------------------------------------
-- 2. Security Helper Functions (Tenant & Role Resolution)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.current_user_tenant_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT tenant_id FROM public.user_profile WHERE id = auth.uid() LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.current_user_has_role(allowed_roles public.app_role[])
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.user_role_assignment ura
        WHERE ura.user_id = auth.uid()
          AND ura.tenant_id = public.current_user_tenant_id()
          AND ura.role = ANY(allowed_roles)
    );
$$;

-- -----------------------------------------------------------------------------
-- 3. Exam, PaperVersion, Question, RubricVersion & ReferenceSnapshots
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.exam (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    exam_code TEXT NOT NULL,
    title TEXT NOT NULL,
    conducting_body TEXT NOT NULL DEFAULT 'UPPSC',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, exam_code)
);

CREATE TABLE IF NOT EXISTS public.paper_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    exam_id UUID NOT NULL REFERENCES public.exam(id) ON DELETE RESTRICT,
    paper_slug TEXT NOT NULL,
    subject TEXT NOT NULL,
    mock_label TEXT NOT NULL,
    language_code TEXT NOT NULL,
    duration_minutes INT NOT NULL DEFAULT 180,
    total_marks NUMERIC(6,2) NOT NULL DEFAULT 200.00,
    total_questions INT NOT NULL,
    status public.paper_status NOT NULL DEFAULT 'draft_requires_teacher_approval',
    source_pdf_name TEXT NOT NULL,
    source_pdf_sha256 TEXT NOT NULL,
    source_workbook_name TEXT,
    source_workbook_sha256 TEXT,
    word_count_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    import_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    published_by UUID REFERENCES public.user_profile(id),
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, paper_slug)
);

CREATE TABLE IF NOT EXISTS public.question (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    paper_version_id UUID NOT NULL REFERENCES public.paper_version(id) ON DELETE CASCADE,
    question_code TEXT NOT NULL,
    question_number INT NOT NULL,
    section_code TEXT NOT NULL,
    max_marks NUMERIC(5,2) NOT NULL,
    word_limit INT,
    word_limit_type TEXT NOT NULL DEFAULT 'maximum',
    directive TEXT,
    selection_rule TEXT NOT NULL DEFAULT 'compulsory',
    raw_imported_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    canonical_text_hi TEXT,
    canonical_text_en TEXT,
    passage_context TEXT,
    source_page INT,
    source_row INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (paper_version_id, question_code)
);

CREATE TABLE IF NOT EXISTS public.question_option (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    question_id UUID NOT NULL REFERENCES public.question(id) ON DELETE CASCADE,
    option_code TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    UNIQUE (question_id, option_code)
);

CREATE TABLE IF NOT EXISTS public.rubric_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    paper_version_id UUID NOT NULL REFERENCES public.paper_version(id) ON DELETE RESTRICT,
    version_tag TEXT NOT NULL,
    is_immutable BOOLEAN NOT NULL DEFAULT false,
    numeric_penalty_configured BOOLEAN NOT NULL DEFAULT false,
    approved_by UUID REFERENCES public.user_profile(id),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (paper_version_id, version_tag)
);

CREATE TABLE IF NOT EXISTS public.rubric_criterion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    rubric_version_id UUID NOT NULL REFERENCES public.rubric_version(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES public.question(id) ON DELETE CASCADE,
    criterion_code TEXT NOT NULL,
    display_name TEXT NOT NULL,
    max_score NUMERIC(5,2) NOT NULL,
    score_increment NUMERIC(4,2) NOT NULL DEFAULT 0.50,
    scoring_anchor TEXT,
    UNIQUE (rubric_version_id, question_id, criterion_code)
);

CREATE TABLE IF NOT EXISTS public.accepted_answer_point (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    rubric_version_id UUID NOT NULL REFERENCES public.rubric_version(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES public.question(id) ON DELETE CASCADE,
    point_type TEXT NOT NULL DEFAULT 'expected', -- expected | optional | alternative | common_error
    point_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.penalty_rule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    rubric_version_id UUID NOT NULL REFERENCES public.rubric_version(id) ON DELETE CASCADE,
    rule_code TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    deduction_marks NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    is_enabled BOOLEAN NOT NULL DEFAULT false,
    configured_by UUID REFERENCES public.user_profile(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.reference_source (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    source_code TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    domain TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source_code)
);

CREATE TABLE IF NOT EXISTS public.reference_snapshot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    reference_source_id UUID NOT NULL REFERENCES public.reference_source(id) ON DELETE RESTRICT,
    question_id UUID NOT NULL REFERENCES public.question(id) ON DELETE CASCADE,
    snapshot_sha256 TEXT NOT NULL,
    claim_excerpt TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_by UUID REFERENCES public.user_profile(id)
);

-- -----------------------------------------------------------------------------
-- 4. Candidate Sessions, Uploads, Pages, Regions, OCR Runs & Immutable Transcripts
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.candidate_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    paper_version_id UUID NOT NULL REFERENCES public.paper_version(id) ON DELETE RESTRICT,
    candidate_user_id UUID REFERENCES public.user_profile(id),
    pseudonym_session_code TEXT NOT NULL,
    status public.job_status NOT NULL DEFAULT 'queued',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, pseudonym_session_code)
);

CREATE TABLE IF NOT EXISTS public.uploaded_file (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    session_id UUID NOT NULL REFERENCES public.candidate_session(id) ON DELETE CASCADE,
    storage_bucket TEXT NOT NULL DEFAULT 'answer-scans-raw',
    storage_object_path TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    detected_mime TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256_hash TEXT NOT NULL,
    page_count INT NOT NULL DEFAULT 1,
    quarantine_status TEXT NOT NULL DEFAULT 'verified_clean',
    envelope_key_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.page (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    session_id UUID NOT NULL REFERENCES public.candidate_session(id) ON DELETE CASCADE,
    uploaded_file_id UUID NOT NULL REFERENCES public.uploaded_file(id) ON DELETE CASCADE,
    page_number INT NOT NULL,
    rotation_deg NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    detected_skew_deg NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    width_px INT NOT NULL,
    height_px INT NOT NULL,
    derivatives JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    UNIQUE (session_id, page_number)
);

CREATE TABLE IF NOT EXISTS public.answer_region (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    session_id UUID NOT NULL REFERENCES public.candidate_session(id) ON DELETE CASCADE,
    page_id UUID NOT NULL REFERENCES public.page(id) ON DELETE CASCADE,
    linked_question_id UUID REFERENCES public.question(id),
    bbox_px JSONB NOT NULL,
    script_detected TEXT NOT NULL DEFAULT 'hi',
    assignment_confidence NUMERIC(4,3) NOT NULL DEFAULT 0.900,
    needs_region_review BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.ocr_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    answer_region_id UUID NOT NULL REFERENCES public.answer_region(id) ON DELETE CASCADE,
    adapter_id TEXT NOT NULL,
    model_version_pin TEXT NOT NULL,
    source_variant_id TEXT NOT NULL DEFAULT 'clahe_contrast',
    raw_text TEXT NOT NULL,
    calibrated_confidence NUMERIC(4,3) NOT NULL,
    used_rubric_context BOOLEAN NOT NULL DEFAULT false CHECK (used_rubric_context = false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.transcript_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    answer_region_id UUID NOT NULL REFERENCES public.answer_region(id) ON DELETE CASCADE,
    revision_number INT NOT NULL,
    source_type TEXT NOT NULL, -- 'ocr_ensemble' | 'user_correction' | 'teacher_verified'
    is_confirmed_for_grading BOOLEAN NOT NULL DEFAULT false,
    transcript_text TEXT NOT NULL,
    overall_confidence NUMERIC(4,3) NOT NULL,
    has_unresolved_disagreement BOOLEAN NOT NULL DEFAULT false,
    created_by UUID REFERENCES public.user_profile(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (answer_region_id, revision_number)
);

CREATE TABLE IF NOT EXISTS public.transcript_span (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    transcript_version_id UUID NOT NULL REFERENCES public.transcript_version(id) ON DELETE CASCADE,
    span_index INT NOT NULL,
    text_value TEXT NOT NULL,
    bbox_px JSONB NOT NULL,
    calibrated_confidence NUMERIC(4,3) NOT NULL,
    alternative_readings JSONB NOT NULL DEFAULT '[]'::jsonb,
    requires_human_decision BOOLEAN NOT NULL DEFAULT false
);

-- -----------------------------------------------------------------------------
-- 5. Jobs, Grade Runs, Criterion Marks, Feedback & Human Reviews
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.job (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    session_id UUID REFERENCES public.candidate_session(id) ON DELETE CASCADE,
    idempotency_key TEXT NOT NULL UNIQUE,
    job_type TEXT NOT NULL, -- 'import_parse' | 'scan_ocr' | 'rubric_grade'
    status public.job_status NOT NULL DEFAULT 'queued',
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    progress_pct INT NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.grade_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    session_id UUID NOT NULL REFERENCES public.candidate_session(id) ON DELETE CASCADE,
    answer_region_id UUID NOT NULL REFERENCES public.answer_region(id) ON DELETE RESTRICT,
    paper_version_id UUID NOT NULL REFERENCES public.paper_version(id) ON DELETE RESTRICT,
    rubric_version_id UUID NOT NULL REFERENCES public.rubric_version(id) ON DELETE RESTRICT,
    transcript_version_id UUID NOT NULL REFERENCES public.transcript_version(id) ON DELETE RESTRICT,
    question_id UUID NOT NULL REFERENCES public.question(id) ON DELETE RESTRICT,
    model_provider_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    reference_snapshot_ids UUID[] NOT NULL DEFAULT '{}',
    word_count INT NOT NULL,
    word_limit_status TEXT NOT NULL,
    ai_suggested_score NUMERIC(5,2) NOT NULL,
    max_marks NUMERIC(5,2) NOT NULL,
    confidence TEXT NOT NULL,
    needs_human_review BOOLEAN NOT NULL DEFAULT true,
    review_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    validator_passed BOOLEAN NOT NULL DEFAULT true,
    structured_contract_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.criterion_mark (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    grade_run_id UUID NOT NULL REFERENCES public.grade_run(id) ON DELETE CASCADE,
    criterion_code TEXT NOT NULL,
    score NUMERIC(5,2) NOT NULL,
    max_score NUMERIC(5,2) NOT NULL,
    reason TEXT NOT NULL,
    answer_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    key_evidence JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS public.feedback_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    grade_run_id UUID NOT NULL REFERENCES public.grade_run(id) ON DELETE CASCADE,
    feedback_category TEXT NOT NULL, -- 'strength' | 'missing_point' | 'factual_error' | 'language_issue' | 'improvement'
    severity TEXT,
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS public.human_review (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    grade_run_id UUID NOT NULL REFERENCES public.grade_run(id) ON DELETE RESTRICT,
    reviewer_id UUID NOT NULL REFERENCES public.user_profile(id) ON DELETE RESTRICT,
    action TEXT NOT NULL, -- 'approved' | 'overridden' | 'returned_for_transcript_correction'
    reviewed_final_score NUMERIC(5,2) NOT NULL,
    criterion_overrides JSONB NOT NULL DEFAULT '[]'::jsonb,
    override_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.audit_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE RESTRICT,
    actor_user_id UUID REFERENCES public.user_profile(id),
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    prev_event_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.retention_policy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenant(id) ON DELETE CASCADE,
    artifact_category TEXT NOT NULL,
    retention_days INT NOT NULL DEFAULT 180,
    auto_purge_enabled BOOLEAN NOT NULL DEFAULT true,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, artifact_category)
);

-- -----------------------------------------------------------------------------
-- 6. Immutability Triggers (Never overwrite transcript versions or AI grade runs)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.prevent_immutable_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Immutable record in table % cannot be updated or deleted; insert a new revision instead.', TG_TABLE_NAME;
END;
$$;

DROP TRIGGER IF EXISTS trg_immutable_transcript_version ON public.transcript_version;
CREATE TRIGGER trg_immutable_transcript_version
BEFORE UPDATE OR DELETE ON public.transcript_version
FOR EACH ROW EXECUTE FUNCTION public.prevent_immutable_mutation();

DROP TRIGGER IF EXISTS trg_immutable_grade_run ON public.grade_run;
CREATE TRIGGER trg_immutable_grade_run
BEFORE UPDATE OR DELETE ON public.grade_run
FOR EACH ROW EXECUTE FUNCTION public.prevent_immutable_mutation();

DROP TRIGGER IF EXISTS trg_immutable_human_review ON public.human_review;
CREATE TRIGGER trg_immutable_human_review
BEFORE UPDATE OR DELETE ON public.human_review
FOR EACH ROW EXECUTE FUNCTION public.prevent_immutable_mutation();

-- -----------------------------------------------------------------------------
-- 7. Durable Queues via pgmq (if extension active)
-- -----------------------------------------------------------------------------
DO $$ BEGIN
    PERFORM pgmq.create('ocr_jobs');
    PERFORM pgmq.create('grading_jobs');
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgmq queue creation skipped or handled by external worker queue.';
END $$;

-- -----------------------------------------------------------------------------
-- 8. Least-Privilege Grants & Row-Level Security (RLS) on Every Table
-- -----------------------------------------------------------------------------
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC, anon;
GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'tenant', 'user_profile', 'user_role_assignment',
        'exam', 'paper_version', 'question', 'question_option',
        'rubric_version', 'rubric_criterion', 'accepted_answer_point', 'penalty_rule',
        'reference_source', 'reference_snapshot',
        'candidate_session', 'uploaded_file', 'page', 'answer_region',
        'ocr_run', 'transcript_version', 'transcript_span',
        'job', 'grade_run', 'criterion_mark', 'feedback_item',
        'human_review', 'audit_event', 'retention_policy'
    ]
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', tbl);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY;', tbl);
    END LOOP;
END $$;

-- Tenant isolation policy template: authenticated users can only read rows in their tenant
CREATE POLICY tenant_isolation_select_exam ON public.exam
    FOR SELECT TO authenticated
    USING (tenant_id = public.current_user_tenant_id());

CREATE POLICY tenant_isolation_select_paper ON public.paper_version
    FOR SELECT TO authenticated
    USING (tenant_id = public.current_user_tenant_id());

CREATE POLICY teacher_publish_paper ON public.paper_version
    FOR UPDATE TO authenticated
    USING (
        tenant_id = public.current_user_tenant_id()
        AND public.current_user_has_role(ARRAY['tenant_admin'::public.app_role, 'senior_teacher'::public.app_role])
    )
    WITH CHECK (
        tenant_id = public.current_user_tenant_id()
        AND public.current_user_has_role(ARRAY['tenant_admin'::public.app_role, 'senior_teacher'::public.app_role])
    );

-- Candidate sessions: candidates see only their own session; examiners/teachers see tenant sessions
CREATE POLICY session_access_policy ON public.candidate_session
    FOR SELECT TO authenticated
    USING (
        tenant_id = public.current_user_tenant_id()
        AND (
            candidate_user_id = auth.uid()
            OR public.current_user_has_role(ARRAY['tenant_admin'::public.app_role, 'senior_teacher'::public.app_role, 'examiner'::public.app_role, 'auditor'::public.app_role])
        )
    );

-- Human review: only senior_teacher, examiner, or tenant_admin in same tenant may insert reviews
CREATE POLICY teacher_insert_human_review ON public.human_review
    FOR INSERT TO authenticated
    WITH CHECK (
        tenant_id = public.current_user_tenant_id()
        AND reviewer_id = auth.uid()
        AND public.current_user_has_role(ARRAY['tenant_admin'::public.app_role, 'senior_teacher'::public.app_role, 'examiner'::public.app_role])
    );

-- -----------------------------------------------------------------------------
-- 9. Private Supabase Storage Buckets & Storage RLS
-- -----------------------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES
    ('answer-scans-raw', 'answer-scans-raw', false, 26214400, ARRAY['application/pdf', 'image/png', 'image/jpeg']),
    ('answer-page-derivatives', 'answer-page-derivatives', false, 26214400, ARRAY['image/png', 'image/jpeg']),
    ('answer-region-crops', 'answer-region-crops', false, 10485760, ARRAY['image/png', 'image/jpeg']),
    ('exam-source-artifacts', 'exam-source-artifacts', false, 52428800, ARRAY['application/pdf', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'])
ON CONFLICT (id) DO UPDATE SET
    public = EXCLUDED.public,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Storage objects RLS: folder path must start with user's tenant_id UUID
CREATE POLICY storage_private_tenant_read ON storage.objects
    FOR SELECT TO authenticated
    USING (
        bucket_id IN ('answer-scans-raw', 'answer-page-derivatives', 'answer-region-crops', 'exam-source-artifacts')
        AND (storage.foldername(name))[1] = public.current_user_tenant_id()::text
    );

CREATE POLICY storage_private_tenant_insert ON storage.objects
    FOR INSERT TO authenticated
    WITH CHECK (
        bucket_id IN ('answer-scans-raw', 'exam-source-artifacts')
        AND (storage.foldername(name))[1] = public.current_user_tenant_id()::text
    );

COMMIT;
