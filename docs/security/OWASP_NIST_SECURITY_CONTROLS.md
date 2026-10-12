# Security, Privacy & Governance Controls (OWASP & NIST AI RMF)

## 1. Threat Model & Implemented Controls

Aligned with **OWASP API Security Top 10**, **OWASP File Upload Cheat Sheet**, **OWASP Top 10 for LLM Applications**, **OWASP Prompt Injection Prevention Cheat Sheet**, and **NIST AI RMF**:

1. **Tenant & Object-Level Authorization (BOLA / BOPLA Prevention):**
   - Every table in `supabase/migrations/20261012000001_initial_schema_and_rls.sql` has `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.
   - `REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC, anon;` removes excessive default grants.
   - Policies verify `tenant_id = public.current_user_tenant_id()` and role membership (`tenant_admin`, `senior_teacher`, `examiner`, `candidate`, `auditor`).
2. **Quarantine File Upload Validation (`apps/worker/image_pipeline.py`):**
   - Validates magic-byte signatures (`%PDF-`, `\x89PNG\r\n\x1a\n`, `\xff\xd8\xff`) rather than trusting HTTP `Content-Type` or file extensions.
   - Enforces a 25 MB size quota, 32-page PDF cap, and 24-megapixel decompression-bomb limit before rendering pages in an isolated non-root worker (`USER 10001:10001`).
   - Computes cryptographic SHA-256 hashes of all original uploads and stores objects in private Supabase Storage buckets (`public = false`) with short-lived signed URLs.
3. **SSRF Protection on Reference Retrieval (`packages/model-adapters/ssrf_retriever.py`):**
   - Disallows non-HTTPS schemes (`file://`, `http://`, `gopher://`, `ftp://`).
   - Blocks loopback (`127.0.0.0/8`, `::1`), RFC1918 private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local, and cloud metadata endpoints (`169.254.169.254`).
   - Enforces an explicit domain allowlist (`ncert.nic.in`, `legislative.gov.in`, `upagripardarshi.gov.in`, `education.gov.in`, `dpe.gov.in`, `wcd.nic.in`, `niti.gov.in`, `ndma.gov.in`, `sac.gov.in`, `upeida.up.gov.in`).
   - Never transmits student names, candidate IDs, answer-sheet images, or full student transcripts to search providers.
4. **Prompt-Injection Isolation & Deterministic Score Validation (`packages/rubric-core/validator.py`):**
   - Untrusted student transcripts are sanitized for override patterns and isolated inside `<untrusted_student_transcript>` XML delimiters.
   - Grading models have zero database or tool-execution privileges.
   - Application code—never the LLM—calculates `final_score`, enforces per-criterion maximums, snaps scores to permitted `0.5` increments, rejects invented criterion IDs, validates `ReferenceSnapshot` IDs, and blocks unconfigured numeric deductions.
5. **Secrets Hygiene:**
   - Zero secret values are committed to source control, printed in logs, or exposed in `NEXT_PUBLIC_` browser variables.
   - `.env.example` lists only variable names and safe placeholders; `.gitignore` excludes `.env*` and `uploads/`.
