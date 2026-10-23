import crypto from "crypto";
import { NextResponse } from "next/server";

// Gives the browser the public address of the answer-check service and a short-lived token (10 minutes).
// The shared key itself never leaves the server. Answer sheets are uploaded straight to the service,
// because the hosting platform limits request bodies to a few megabytes.
export const dynamic = "force-dynamic";

export async function GET() {
  const url = (process.env.CHECK_SERVICE_URL || "").replace(/\/$/, "");
  const key = process.env.CHECK_SERVICE_KEY || "";
  if (!url || !key) return NextResponse.json({ error: "unavailable" }, { status: 503 });
  const ts = Math.floor(Date.now() / 1000).toString();
  const sig = crypto.createHmac("sha256", key).update(ts).digest("hex");
  return NextResponse.json({ url, token: `${ts}.${sig}` }, { headers: { "cache-control": "no-store" } });
}
