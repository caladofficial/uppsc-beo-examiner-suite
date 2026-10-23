import { NextRequest, NextResponse } from "next/server";

// Answer-check service (Python). Only the server calls it; the browser uses this route.
const SERVICE_URL = (process.env.CHECK_SERVICE_URL || "http://127.0.0.1:8001").replace(/\/$/, "");
const MAX_BYTES = 25 * 1024 * 1024;

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const res = await fetch(`${SERVICE_URL}/papers`, { cache: "no-store" });
    const body = await res.json();
    return NextResponse.json(body, { status: res.status });
  } catch {
    return NextResponse.json({ error: "unavailable" }, { status: 503 });
  }
}

export async function POST(req: NextRequest) {
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }
  const paperId = String(form.get("paper_id") ?? "");
  const file = form.get("file");
  if (!paperId || !(file instanceof File)) {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }
  if (file.size === 0 || file.size > MAX_BYTES) {
    return NextResponse.json({ error: "file_size" }, { status: 400 });
  }

  const out = new FormData();
  out.set("paper_id", paperId);
  out.set("file", file, file.name || "answer-sheet");
  try {
    const res = await fetch(`${SERVICE_URL}/check`, { method: "POST", body: out, cache: "no-store" });
    const body = await res.json().catch(() => ({ error: "bad_response" }));
    return NextResponse.json(body, { status: res.status });
  } catch {
    return NextResponse.json({ error: "unavailable" }, { status: 503 });
  }
}
