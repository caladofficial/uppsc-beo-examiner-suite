# System Architecture & Deployment Runbook

## 1. Modular Monolith + Isolated Worker Topology

- **`apps/web` (Next.js 14 + TypeScript + Tailwind CSS):** Examiner-focused UI implementing the 6-stage workflow using the `@RIARYDESIGN` palette (`#484A47` Outer Space, `#5C6D70` Payne's Gray, `#A37774` Old Rose, `#E88873` Salmon, `#E0AC9D` Melon, `#FAF6F3` Warm Cream).
- **`apps/api` (FastAPI Modular Monolith):** Handles tenant-scoped authorization, import validation, quarantine uploads, transcript versioning, deterministic score validation, teacher overrides, and hash-chained audit logging.
- **`apps/worker` (Isolated Python Image & OCR/Grading Pipeline):** Performs PDF rendering, Hough deskewing, CIE-LAB CLAHE shadow removal, adaptive ink thresholding, multi-adapter OCR/HTR inference, and rubric-bounded grading.
- **`supabase/` (Migrations, RLS, Private Storage & `pgmq` Queues):** Full SQL schema (`20261012000001_initial_schema_and_rls.sql`), Edge Function job orchestrator (`supabase/functions/orchestrate-job/index.ts`), and RLS verification suite (`supabase/tests/rls_policy_verification.sql`).

## 2. Staging & Production Gate Policy

Per product instructions:
- **No unapproved remote mutations:** Migrations and Vercel configuration (`infra/deployment/vercel.json`) are prepared and verified locally. Do not push migrations to the remote Supabase project or trigger a production Vercel deployment until explicit owner sign-off.
