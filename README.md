# UPPSC BEO Mains Handwritten Answer-Sheet Scanner, OCR/HTR & Rubric Grader

Production-minded MVP for **UPPSC Block Education Officer (BEO) Mains** handwritten answer-sheet scanning, zero-context multi-model OCR/HTR transcription, and deterministic rubric-bounded grading.

## Key Capabilities (5-Stage Separation of Concerns)

1. **Stage 1 — Exam & Rubric Import Workspace**:
   - Canonical reconciliation of **UPPSC BEO Mains GS Mock 17** (`uppsc-beo-mains-gs-mock-17-v1`, 40 compulsory bilingual questions, 200 marks) and **General Hindi & Essay Mock 16** (`uppsc-beo-mains-hindi-mock-16-v1`, 13 evaluation items, 200 marks).
   - Flags section-heading contamination in GS Mock 17 `Q10` & `Q20`, resolves the `Mock 17` identity collision between GS and Hindi workbooks via composite keys, generates a draft rubric template for Hindi Mock 16 requiring teacher sign-off, and flags legacy Devanagari PDF font-cmap garbling.
2. **Stage 2 — Candidate Upload, Quarantine & Reversible Page Derivatives**:
   - Magic-byte signature verification (`PDF`, `PNG`, `JPEG`), 25 MB quota enforcement, SHA-256 content hashing, and 5 reversible image derivatives (`original`, `deskewed`, `clahe_contrast`, `adaptive_ink`, `restormer_deblur_preview`).
3. **Stage 3 — Synchronized Scan Review & Zero-Context Multi-Model OCR/HTR**:
   - Side-by-side original scan viewer with bounding-box overlays, candidate readings from **IndicOCR (`bodhan-ai/indic-ocr`)**, **Qwen2-VL Hindi HTR**, and **PaddleOCR (`devanagari_PP-OCRv5_mobile_rec`)**, model disagreement badges, explicit `cannot_confidently_read` state, and immutable transcript revisions.
   - **Strict Context Isolation**: OCR/HTR adapters never receive expected answers or rubric points.
4. **Stage 4 — Rubric-Bounded Grader & Deterministic Validator**:
   - Strict JSON grading contract validated by deterministic Python (`packages/rubric-core/validator.py`) and TypeScript (`apps/web/src/lib/server-state.ts`) engines.
   - Enforces criterion caps, score increments (`0.5`), NFC Unicode bilingual word counting (`HARD_MAX` vs `APPROXIMATE`), and zero invented numeric deductions unless explicitly teacher-configured.
5. **Stage 5 — Teacher Override, Immutable Hash-Chained Audit Trail & Security Guardrails**:
   - Mandatory substantive reason for teacher score overrides, preserving AI-suggested marks alongside reviewed marks.
   - SSRF domain allowlist + private/link-local/metadata IP blocking and prompt-injection sanitization.

## Repository Structure

- `apps/web/` — Standalone Next.js 14 + TypeScript + Tailwind CSS application with built-in `/api/v1/[...slug]` App Router serverless endpoints and static GitHub Pages fallback.
- `apps/api/` — FastAPI modular monolith (`apps.api.main:app`).
- `apps/worker/` — Canonical exam importer (`importer.py`) and quarantine/image-derivative pipeline (`image_pipeline.py`).
- `packages/contracts/` — Pydantic (`schemas.py`) and TypeScript (`schemas.ts`) grading output contracts.
- `packages/rubric-core/` — Deterministic Unicode word-count and rubric score validator (`validator.py`).
- `packages/model-adapters/` — Zero-context OCR/HTR adapter registry, SSRF-safe retriever, and rubric-bounded VLM/LLM grader.
- `supabase/` — PostgreSQL schema & RLS migration (`20261012000001_initial_schema_and_rls.sql`), Edge Function orchestrator, and 7-assertion RLS test suite (`rls_policy_verification.sql`).
- `docs/` — Import audit report, OCR/HTR benchmark & license matrix, OWASP/NIST security controls, and system architecture.
- `scripts/git-sync.sh` — Pre-commit secret scanner + automated GitHub push & CI/CD trigger.
