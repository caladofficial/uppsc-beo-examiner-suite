import crypto from "crypto";
import { NextRequest, NextResponse } from "next/server";

// Gives the browser the address of the answer-check service and a short-lived token (10 minutes).
// Tokens are issued only to visitors who send the access code. The shared service key never leaves the
// server. Answer sheets are uploaded straight to the service because the hosting platform limits
// request bodies to a few megabytes.
export const dynamic = "force-dynamic";

function safeEqual(a: string, b: string): boolean {
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}

export async function GET(req: NextRequest) {
  const url = (process.env.CHECK_SERVICE_URL || "").replace(/\/$/, "");
  const key = process.env.CHECK_SERVICE_KEY || "";
  const code = process.env.ACCESS_CODE || "";
  if (!url || !key || !code) return NextResponse.json({ error: "unavailable" }, { status: 503 });

  const sent = req.headers.get("x-access-code") || "";
  if (!sent || !safeEqual(sent, code)) {
    return NextResponse.json({ error: "access" }, { status: 401, headers: { "cache-control": "no-store" } });
  }

  const ts = Math.floor(Date.now() / 1000).toString();
  const sig = crypto.createHmac("sha256", key).update(ts).digest("hex");
  return NextResponse.json({ url, token: `${ts}.${sig}` }, { headers: { "cache-control": "no-store" } });
}
