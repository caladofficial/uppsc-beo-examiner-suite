import { NextRequest, NextResponse } from "next/server";

// Answer-check service (Python). Only the server calls it; the browser uses this route.
const SERVICE_URL = (process.env.CHECK_SERVICE_URL || "http://127.0.0.1:8001").replace(/\/$/, "");
// Shared secret for the answer-check service (set CHECK_SERVICE_KEY on the host).
const SERVICE_HEADERS: Record<string, string> = process.env.CHECK_SERVICE_KEY
  ? { "x-service-key": process.env.CHECK_SERVICE_KEY }
  : {};
const MAX_BYTES = 25 * 1024 * 1024;

export const dynamic = "force-dynamic";
// A fresh answer sheet can take several minutes to read; allow the longest run the plan permits.
export const maxDuration = 300;

// GET ?paper_id=...  -> the questions of one paper
export async function GET(req: NextRequest) {
  const paperId = req.nextUrl.searchParams.get("paper_id") ?? "";
  if (!paperId) return NextResponse.json({ error: "bad_request" }, { status: 400 });
  try {
    const res = await fetch(`${SERVICE_URL}/questions?paper_id=${encodeURIComponent(paperId)}`, { cache: "no-store", headers: SERVICE_HEADERS });
    const body = await res.json().catch(() => ({ error: "bad_response" }));
    return NextResponse.json(body, { status: res.status });
  } catch {
    return NextResponse.json({ error: "unavailable" }, { status: 503 });
  }
}

// POST multipart: paper_id, question_id, file -> marks, good points, missing points, model answer
export async function POST(req: NextRequest) {
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }
  const paperId = String(form.get("paper_id") ?? "");
  const questionId = String(form.get("question_id") ?? "");
  const file = form.get("file");
  if (!paperId || !questionId || !(file instanceof File)) {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }
  if (file.size === 0 || file.size > MAX_BYTES) {
    return NextResponse.json({ error: "file_size" }, { status: 400 });
  }

  const out = new FormData();
  out.set("paper_id", paperId);
  out.set("question_id", questionId);
  out.set("file", file, file.name || "answer-sheet");
  out.set("use_llm", "true"); // always cross-check with the language model
  try {
    // A long sheet can take several minutes (the reader goes page by page), so allow a long wait.
    const res = await fetch(`${SERVICE_URL}/grade`, {
      method: "POST",
      body: out,
      cache: "no-store",
      headers: SERVICE_HEADERS,
      signal: AbortSignal.timeout(20 * 60 * 1000),
    });
    const body = await res.json().catch(() => ({ error: "bad_response" }));
    return NextResponse.json(body, { status: res.status });
  } catch {
    return NextResponse.json({ error: "unavailable" }, { status: 503 });
  }
}
