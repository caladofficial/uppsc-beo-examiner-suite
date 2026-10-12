/**
 * Supabase Edge Function: orchestrate-job
 * Lightweight, authenticated job orchestrator that validates tenant ownership
 * and enqueues heavy OCR/HTR or Rubric Grading work onto pgmq / external Python worker.
 * Heavy PDF rendering, deblurring, and VLM inference NEVER run inside Edge Function limits.
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405 });
  }

  const authHeader = req.headers.get("Authorization");
  if (!authHeader) {
    return new Response(JSON.stringify({ error: "Missing Authorization header" }), { status: 401 });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const supabaseAnonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
  const workerUrl = Deno.env.get("OCR_WORKER_URL");
  const workerToken = Deno.env.get("OCR_WORKER_AUTH_TOKEN");

  // User-scoped client enforces Row-Level Security (never bypasses RLS for ownership verification)
  const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    global: { headers: { Authorization: authHeader } },
  });

  const { data: userData, error: userErr } = await supabase.auth.getUser();
  if (userErr || !userData?.user) {
    return new Response(JSON.stringify({ error: "Unauthorized session" }), { status: 401 });
  }

  const body = await req.json();
  const { session_id, job_type, idempotency_key } = body;

  if (!session_id || !job_type || !idempotency_key) {
    return new Response(JSON.stringify({ error: "Missing session_id, job_type, or idempotency_key" }), { status: 400 });
  }

  // Verify tenant-scoped ownership via RLS-protected query
  const { data: sessionRow, error: sessErr } = await supabase
    .from("candidate_session")
    .select("id, tenant_id, status")
    .eq("id", session_id)
    .single();

  if (sessErr || !sessionRow) {
    return new Response(JSON.stringify({ error: "Forbidden: session not found or cross-tenant access denied" }), {
      status: 403,
    });
  }

  // Create idempotent job record
  const { data: jobRow, error: jobErr } = await supabase
    .from("job")
    .upsert(
      {
        tenant_id: sessionRow.tenant_id,
        session_id: sessionRow.id,
        idempotency_key,
        job_type,
        status: "queued",
      },
      { onConflict: "idempotency_key" }
    )
    .select()
    .single();

  if (jobErr) {
    return new Response(JSON.stringify({ error: jobErr.message }), { status: 500 });
  }

  // Dispatch asynchronously to isolated non-root Python worker if configured
  if (workerUrl && workerToken) {
    fetch(`${workerUrl}/v1/internal/dispatch`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Worker-Auth": workerToken,
      },
      body: JSON.stringify({ job_id: jobRow.id, session_id, job_type }),
    }).catch(() => {});
  }

  return new Response(JSON.stringify({ job: jobRow }), {
    status: 202,
    headers: { "Content-Type": "application/json" },
  });
});
