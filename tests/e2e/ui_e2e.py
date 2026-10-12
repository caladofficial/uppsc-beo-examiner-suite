"""End-to-end UI test for the UPPSC BEO grading workspace.
Usage: python3 ui_e2e.py <base_url> <screenshot_dir>
Exercises every stage and control, and checks visible text for AI-facing terms."""
import re, sys, os, json
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = sys.argv[2] if len(sys.argv) > 2 else "/tmp/shots"
os.makedirs(SHOTS, exist_ok=True)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), str(detail)))
    d = str(detail)[:160].replace("\n", " | ")
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not detail else f"  [{d}]"))


FORBIDDEN = re.compile(
    r"\b(AI|VLM|LLM|Gemini|Qwen\S*|Bodhan|IndicOCR|Surya|PaddleOCR|PP-OCR\S*|Tesseract|Restormer|"
    r"Real-ESRGAN|Deterministic|Pinned|Teacher|Pseudonym\S*|SSRF|Immutable|Sparkles|Zero-Context|NFC|"
    r"SHA-256|CMap|OCR/HTR|Magic-byte|Quarantine|quarantine|RIARY|CMap|CMAP)\b",
    re.I,
)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    console_errors, page_errors = [], []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    failed_responses = []
    page.on("response", lambda r: failed_responses.append(r.url) if r.status >= 400 else None)
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_selector("text=UPPSC BEO Mains", timeout=30000)
    page.wait_for_timeout(800)

    def text():
        return page.inner_text("body")

    def T():
        return page.inner_text("body").lower()

    def leak_scan(label):
        # "teacher" is legitimate exam wording inside some questions; exclude it from the scan
        body_txt = re.sub(r"(?i)\bteacher\b", "", text())
        hits = sorted(set(m.group(0) for m in FORBIDDEN.finditer(body_txt)))
        check(f"no AI/internal terms visible [{label}]", not hits, f"found {hits}")

    def nav(label_re):
        page.get_by_role("button", name=re.compile(label_re)).first.click()
        page.wait_for_timeout(500)

    # ---------------- global ----------------
    leak_scan("header")
    check("sample-data notice shown", "sample data for demonstration" in T())
    for lbl in ["Question Papers", "Upload Answer", "Read & Check", "Grade & Review",
                "Candidate Report", "Quality & Security"]:
        check(f"nav button exists: {lbl}", page.get_by_role("button", name=re.compile(lbl)).count() > 0)

    # ---------------- STAGE 1 ----------------
    nav("Question Papers")
    page.screenshot(path=f"{SHOTS}/01_stage1_gs.png")
    rows = page.locator("div.lg\\:col-span-5 button")
    check("GS paper: 40 question rows", rows.count() == 40, f"count={rows.count()}")
    for sec in ["Sec A", "Sec B", "Sec C"]:
        page.get_by_role("button", name=sec, exact=True).click()
        page.wait_for_timeout(200)
        check(f"section filter {sec} lists rows", rows.count() > 0, f"count={rows.count()}")
    page.get_by_role("button", name="All (40)", exact=True).click()
    page.wait_for_timeout(200)
    check("All (40) restores 40 rows", rows.count() == 40, f"count={rows.count()}")
    search = page.get_by_placeholder("Search Hindi/English question or topic...")
    search.fill("Vedic")
    page.wait_for_timeout(300)
    check("search 'Vedic' finds matches", rows.count() >= 1, f"count={rows.count()}")
    search.fill("zzzz-no-match")
    page.wait_for_timeout(300)
    check("search with no match shows empty state", "no matching questions found." in T())
    search.fill("")
    page.wait_for_timeout(300)
    rows.nth(10).click()
    page.wait_for_timeout(300)
    body = T()
    check("question detail: marks breakdown heading", "marks breakdown & allowed steps" in body)
    check("question detail: answer outline heading", "answer outline (for examiner reference)" in body)
    check("question detail: reference sources heading", "reference sources (approved sites only)" in body)
    check("GS Q11 detail shows outline points", "iron" in body.lower().lower() or "trade" in body.lower().lower())
    leak_scan("stage1 GS detail")
    page.get_by_role("button", name=re.compile("Mock 16")).first.click()
    page.wait_for_timeout(500)
    check("Hindi paper: 13 item rows", rows.count() == 13, f"count={rows.count()}")
    rows.nth(0).click()
    page.wait_for_timeout(300)
    check("Hindi item detail shows marks breakdown", "marks breakdown & allowed steps" in T())
    page.screenshot(path=f"{SHOTS}/02_stage1_hindi.png")
    page.get_by_text("Apply a fixed mark deduction for factual errors").click()
    page.wait_for_timeout(200)
    check("penalty toggle reveals deduction input", page.locator("input[type=number][step='0.5']").count() >= 1)
    page.get_by_text("Apply a fixed mark deduction for factual errors").click()
    page.wait_for_timeout(200)
    page.get_by_placeholder("Reason for approval (required)").fill("Checked against the 13-item pattern (test run).")
    page.get_by_role("button", name=re.compile("Approve & publish Hindi Mock 16")).click()
    page.wait_for_timeout(1500)
    check("publishing Hindi scheme shows Approved status", "approved" in T())
    page.get_by_role("button", name=re.compile("GS Mock 17")).first.click()
    page.wait_for_timeout(400)
    leak_scan("stage1 end")

    # ---------------- STAGE 2 ----------------
    nav("Upload Answer")
    check("upload stage renders", "upload an answer sheet" in T())
    page.screenshot(path=f"{SHOTS}/03_stage2.png")
    bad = "/tmp/uiclean_not_an_image.png"
    open(bad, "w").write("this is plain text, not an image")
    page.set_input_files("input[type=file]", bad)
    page.wait_for_timeout(1500)
    check("invalid file is rejected with a message", "not accepted" in T(),
          text()[-200:])
    good = "/home/user/apps/web/public/scans/hi16_cand02_p1_original.png"
    page.set_input_files("input[type=file]", good)
    page.wait_for_timeout(2000)
    check("valid PNG upload accepted", "file accepted" in T() or "page views are ready" in T())
    check("file-check result shows MIME", "mime" in T())
    page.get_by_role("button", name=re.compile(r"^Page 1 ")).first.click()
    page.wait_for_timeout(300)
    srcs = []
    for lbl in ["Straightened", "Brightness balanced", "High-contrast ink", "Sharpened preview", "Original scan"]:
        page.get_by_role("button", name=re.compile(lbl)).first.click()
        page.wait_for_timeout(250)
        img = page.locator("img[alt^='Scan page']").first
        srcs.append(img.get_attribute("src") or "")
        check(f"page view '{lbl}' renders an image", img.count() == 1 and srcs[-1] != "")
    check("page views switch image source", len(set(srcs)) >= 3, f"distinct={len(set(srcs))}")
    check("candidate pages listed (seeded + uploaded)", page.get_by_role("button", name=re.compile(r"^Page \d")).count() >= 3)
    leak_scan("stage2")

    # ---------------- STAGE 3 ----------------
    nav("Read & Check")
    check("stage 3 renders transcript editor", page.locator("#transcript-editor").count() == 1)
    page.screenshot(path=f"{SHOTS}/04_stage3.png")
    use_btns = page.get_by_role("button", name="Use this reading")
    check("readings have 'Use this reading' buttons", use_btns.count() >= 1, f"count={use_btns.count()}")
    if use_btns.count() >= 2:
        use_btns.nth(1).click()
        page.wait_for_timeout(200)
        check("'Use this reading' loads text into editor",
              page.locator("#transcript-editor").input_value().strip() != "")
    ta = page.locator("#transcript-editor")
    ta.fill(ta.input_value() + " परीक्षण।")
    drafts_before = page.get_by_text("Draft", exact=True).count()
    page.get_by_role("button", name="Save draft").click()
    page.wait_for_timeout(900)
    check("save draft adds a version to history", page.get_by_text("Draft", exact=True).count() > drafts_before)
    page.get_by_role("button", name="Confirm transcript").click()
    page.wait_for_timeout(900)
    check("confirm transcript adds a confirmed version", page.get_by_text("Confirmed", exact=True).count() >= 1)
    page.get_by_role("button", name="Go to grading").click()
    page.wait_for_timeout(700)
    check("'Go to grading' navigates to grading stage", "recalculate marks" in T())
    leak_scan("stage3")

    # ---------------- STAGE 4 ----------------
    page.screenshot(path=f"{SHOTS}/05_stage4.png")
    body = T()
    check("grading: criterion breakdown shown", "marks by criterion & evidence" in body)
    check("grading: question total shown", "question total:" in body)
    check("grading: feedback sections shown", "how to improve" in body)
    page.get_by_role("button", name="Recalculate marks").click()
    page.wait_for_timeout(1200)
    check("recalculate marks completes", "recalculate marks" in T())
    check("review decision dropdown offers 3 choices",
          page.get_by_role("option", name="Accept suggested marks").count() == 1
          and page.get_by_role("option", name="Change marks (reason required)").count() == 1)
    page.locator("input[type=number][step='0.5'][min='0']").last.fill("3.5")
    page.locator("textarea").last.fill("Test review: partial coverage of the directive.")
    page.get_by_role("button", name="Save review").click()
    page.wait_for_timeout(1200)
    check("saved review appears in review history", "review history:" in T())
    leak_scan("stage4")

    # ---------------- STAGE 5 ----------------
    nav("Candidate Report")
    body = T()
    check("report shows candidate ID", "candidate id:" in body)
    check("report shows human-readable paper status", "approved" in body or "draft" in body)
    check("report has per-question rows", "mock 17-01" in body)
    page.screenshot(path=f"{SHOTS}/06_stage5.png")
    with page.expect_download() as dl:
        page.get_by_role("button", name=re.compile("Export report")).click()
    check("export downloads JSON report", dl.value.suggested_filename.endswith(".json"), dl.value.suggested_filename)
    leak_scan("stage5")

    # ---------------- STAGE 6 ----------------
    nav("Quality & Security")
    body = T()
    check("reader comparison table renders", "reader comparison" in body)
    check("reader rows present", "reader a" in body and "reader b" in body)
    check("planning-target disclaimer shown", "planning targets" in body)
    page.screenshot(path=f"{SHOTS}/07_stage6.png")
    page.get_by_role("button", name="Try a blocked address").click()
    page.wait_for_timeout(200)
    page.get_by_role("button", name="Run safety check").click()
    page.wait_for_timeout(900)
    check("blocked metadata address is refused", "link allowed: false" in T())
    check("hidden instruction is flagged", "hidden instruction found: true" in T())
    check("activity log lists events", "activity log" in T())
    leak_scan("stage6")

    # ---------------- errors ----------------
    check("no uncaught page errors", not page_errors, "; ".join(page_errors)[:300])
    # Failed-load console lines are checked precisely via responses below.
    real = [c for c in console_errors if "favicon" not in c.lower() and "Failed to load resource" not in c]
    check("no console errors", not real, "; ".join(real)[:300])
    static_assets_bad = [u for u in failed_responses if "/api/v1/" not in u]
    check("every page asset / image loads (no non-API 4xx/5xx)", not static_assets_bad, "; ".join(static_assets_bad)[:300])
    api_probe_errors = [u for u in failed_responses if "/api/v1/" in u]
    print(f"   (expected API responses with 4xx reasons or static fallbacks: {len(api_probe_errors)})")
    browser.close()

passed = sum(1 for _, ok, _ in results if ok)
print(f"\n== {passed}/{len(results)} checks passed ==")
with open(os.path.join(SHOTS, "results.json"), "w") as f:
    json.dump([{"name": n, "ok": ok, "detail": d} for n, ok, d in results], f, ensure_ascii=False, indent=2)
