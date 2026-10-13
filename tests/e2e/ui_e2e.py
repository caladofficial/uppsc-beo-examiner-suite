"""Browser test for the UPPSC BEO examiner workspace (five-section layout).

Usage: python3 ui_e2e.py <base_url> <screenshot_dir> [scan_png]
Exercises every section and control in a real browser and checks that no
AI-facing or internal terms appear on the page.
"""
import os
import re
import sys
import pathlib
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = sys.argv[2] if len(sys.argv) > 2 else "/tmp/shots"
SCAN = sys.argv[3] if len(sys.argv) > 3 else "/home/user/apps/web/public/scans/gs17_cand01_p1_deskewed.png"
os.makedirs(SHOTS, exist_ok=True)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), str(detail)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not detail else f"  [{str(detail)[:160]}]"))


FORBIDDEN = re.compile(
    r"\b(AI|VLM|LLM|Gemini|Qwen\S*|Bodhan|IndicOCR|Surya|PaddleOCR|PP-OCR\S*|Tesseract|Restormer|"
    r"Real-ESRGAN|Deterministic|Pinned|Teacher|Pseudonym\S*|SSRF|Immutable|Sparkles|Zero-Context|NFC|"
    r"SHA-256|CMap|OCR/HTR|Magic-byte|Quarantine|quarantine|Validator|Rubric-bounded)\b",
    re.I,
)

# a deliberately invalid upload: text bytes named as a PNG
pathlib.Path("/tmp/fake_upload.png").write_text("this is not an image")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    page_errors, console_errors, bad_responses = [], [], []
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("response", lambda r: bad_responses.append(f"{r.status} {r.url}") if r.status >= 400 else None)

    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_selector("text=UPPSC BEO Mains", timeout=30000)
    page.wait_for_timeout(600)

    def body():
        return page.inner_text("body")

    def tab(name):
        page.get_by_role("button", name=name, exact=True).first.click()
        page.wait_for_timeout(500)

    def leak_scan(label):
        # "teacher" can appear in imported exam wording (e.g. Mock 17-08); exclude it from the scan
        body_txt = re.sub(r"(?i)\bteacher\b", "", body())
        hits = sorted(set(m.group(0) for m in FORBIDDEN.finditer(body_txt)))
        check(f"no AI/internal terms [{label}]", not hits, f"found {hits}")

    # ---------- shell ----------
    for name in ["Papers", "Answer sheets", "Handwriting", "Marks", "Report"]:
        check(f"nav has '{name}'", page.get_by_role("button", name=name, exact=True).count() == 1)
    check("exactly five sections in the navigation", page.get_by_role("navigation", name="Sections").get_by_role("button").count() == 5)
    check("sample-data note shown", "demonstration data" in body().lower())
    check("language switch offered", page.get_by_role("button", name="हिन्दी", exact=True).count() == 1)
    leak_scan("shell")

    # ---------- 1. Papers ----------
    check("two paper cards", page.locator("button[aria-pressed]", has_text=re.compile("marks$")).count() == 2)
    check("GS paper shows Approved", "Approved" in body())
    rows = page.locator("li > button")
    check("GS: 40 question rows", rows.count() == 40, f"count={rows.count()}")
    page.get_by_role("button", name=re.compile(r"Section A")).click()
    page.wait_for_timeout(300)
    check("Section A filter: 10 rows", rows.count() == 10, f"count={rows.count()}")
    page.get_by_role("button", name=re.compile(r"^All")).click()
    page.get_by_role("searchbox", name="Search questions").fill("Vedic")
    page.wait_for_timeout(300)
    check("search 'Vedic' finds rows", 1 <= rows.count() <= 40, f"count={rows.count()}")
    page.get_by_role("searchbox", name="Search questions").fill("zzzz-no-match")
    page.wait_for_timeout(300)
    check("search with no match shows empty state", "No matching questions." in body())
    page.get_by_role("searchbox", name="Search questions").fill("")
    page.wait_for_timeout(300)
    rows.nth(4).click()
    page.wait_for_timeout(300)
    check("question detail shows criteria table", "Marking criteria" in body())
    check("question detail shows expected points", page.get_by_text(re.compile(r"Expected points")).count() == 1)
    page.screenshot(path=f"{SHOTS}/01_papers_gs.png", full_page=True)
    leak_scan("papers GS")

    page.locator("details summary", has_text="Import notes").click()
    page.wait_for_timeout(200)
    notes = page.locator("details", has_text="Import notes").locator("li")
    check("import notes list 14 issues", notes.count() == 14, f"count={notes.count()}")

    page.get_by_role("button", name=re.compile("Hindi Mock 16")).click()
    page.wait_for_timeout(800)
    check("Hindi: 13 item rows", rows.count() == 13, f"count={rows.count()}")
    if page.get_by_role("button", name="Approve and publish").count() == 1:
        check("Hindi draft shows approval box", "Approve the marking scheme" in body())
        page.get_by_role("checkbox", name=re.compile("fixed deduction")).check()
        check("deduction checkbox reveals amount input",
              page.get_by_label("Deduction per factual error").count() == 1)
        page.get_by_role("checkbox", name=re.compile("fixed deduction")).uncheck()
        page.get_by_role("button", name="Approve and publish").click()
        page.wait_for_timeout(1200)
        check("publishing approves the Hindi scheme", "Approved" in body() and page.get_by_role("button", name="Approve and publish").count() == 0)
    else:
        check("Hindi scheme already approved (state persists)", "Approved" in body())
    page.screenshot(path=f"{SHOTS}/02_papers_hindi.png", full_page=True)
    leak_scan("papers Hindi")

    # ---------- 2. Answer sheets ----------
    page.get_by_role("button", name=re.compile("Mock 17|General Studies|GS")).first.click()
    page.wait_for_timeout(800)
    tab("Answer sheets")
    check("upload target select present", page.get_by_label("This sheet answers").count() == 1)
    page.locator("input[type=file]").set_input_files("/tmp/fake_upload.png")
    page.wait_for_timeout(1200)
    check("invalid file is refused with a message", "not accepted" in body().lower())
    page.locator("input[type=file]").set_input_files(SCAN)
    page.wait_for_timeout(1500)
    check("valid PNG accepted", "Passed" in body() and "PNG" in body())
    check("file fingerprint shown", "Fingerprint" in body() or "Size" in body())
    page_buttons = page.get_by_role("button", name=re.compile(r"^Page \d+$"))
    check("page buttons listed", page_buttons.count() >= 2, f"count={page_buttons.count()}")
    variant_btns = ["Original scan", "Straightened", "Brightness balanced", "High-contrast ink", "Sharpened preview"]
    for v in variant_btns:
        check(f"variant button '{v}'", page.get_by_role("button", name=v, exact=True).count() == 1)
    page.get_by_role("button", name=re.compile(r"^Page 1$")).click()
    page.wait_for_timeout(300)
    img = page.locator("img[alt^='Page']").first
    src_a = img.get_attribute("src")
    page.get_by_role("button", name="Brightness balanced", exact=True).click()
    page.wait_for_timeout(300)
    src_b = page.locator("img[alt^='Page']").first.get_attribute("src")
    check("page view switches image source", src_a != src_b)
    page.get_by_role("button", name="High-contrast ink", exact=True).click()
    page.wait_for_timeout(200)
    check("enhanced views carry a caution note", "cannot add strokes" in body())
    page.get_by_role("button", name="Original scan", exact=True).click()
    answer_rows = page.locator("tbody tr")
    check("answers table lists sheet answers", answer_rows.count() >= 1, f"count={answer_rows.count()}")
    page.screenshot(path=f"{SHOTS}/03_sheets.png", full_page=True)
    leak_scan("sheets")

    # ---------- 3. Handwriting ----------
    page.get_by_role("button", name="Open").first.click()
    page.wait_for_timeout(600)
    check("Open lands on Handwriting", page.get_by_role("button", name="Handwriting", exact=True).get_attribute("aria-current") == "page")
    editor = page.locator("#transcript-editor")
    check("transcript editor present", editor.count() == 1)
    use_btns = page.get_by_role("button", name="Use this reading")
    check("readings listed with 'Use this reading'", use_btns.count() >= 1, f"count={use_btns.count()}")
    use_btns.first.click()
    check("'Use this reading' fills the transcript", len(editor.input_value()) > 20)
    rev_before = re.search(r"Revision history \((\d+)\)", body())
    rev_before = int(rev_before.group(1)) if rev_before else 0
    editor.fill(editor.input_value() + " ।")
    page.get_by_role("button", name="Save draft revision").click()
    page.wait_for_timeout(1000)
    rev_after = re.search(r"Revision history \((\d+)\)", body())
    rev_after = int(rev_after.group(1)) if rev_after else 0
    check("saving a draft adds a revision", rev_after == rev_before + 1, f"{rev_before}->{rev_after}")
    page.get_by_role("button", name="Confirm for grading").click()
    page.wait_for_timeout(1000)
    page.locator("summary", has_text="Revision history").click()
    page.wait_for_timeout(200)
    check("confirming adds a confirmed revision", "Confirmed" in body())
    zoom_txt = page.get_by_role("button", name="Zoom in").click()
    page.wait_for_timeout(200)
    check("zoom in changes zoom level", "125%" in body())
    page.get_by_role("button", name="Zoom out").click()
    page.get_by_role("button", name="Rotate").click()
    page.wait_for_timeout(200)
    check("rotate applies a transform", page.locator("div[style*='rotate(90deg)']").count() == 1)
    page.screenshot(path=f"{SHOTS}/04_handwriting.png", full_page=True)
    leak_scan("handwriting")

    # ---------- 4. Marks ----------
    tab("Marks")
    if page.get_by_role("button", name="Calculate marks").count() == 1:
        page.get_by_role("button", name="Calculate marks").click()
    else:
        page.get_by_role("button", name="Recalculate marks").click()
    page.wait_for_timeout(1200)
    check("marks calculated", "Suggested marks" in body())
    check("criteria table lists marks", page.get_by_role("cell", name=re.compile("Content|Relevance|Analysis|Language|Structure")).count() >= 1)
    crit_input = page.get_by_label(re.compile("New marks for")).first
    crit_input.fill("1")
    page.get_by_role("button", name="Set").first.click()
    page.wait_for_timeout(900)
    check("criterion mark can be adjusted", "Criterion mark updated" in body())
    decision = page.get_by_label("Decision")
    decision.select_option("overridden")
    save_btn = page.get_by_role("button", name="Save decision")
    check("override is blocked without a reason", save_btn.is_disabled())
    page.locator("#reason").fill("Checked against the scan; content mark corrected.")
    check("override enabled once reason is given", save_btn.is_enabled())
    save_btn.click()
    page.wait_for_timeout(1000)
    check("decision saved to history", "Changed" in body())
    decision.select_option("approved")
    page.screenshot(path=f"{SHOTS}/05_marks.png", full_page=True)
    leak_scan("marks")

    # Accepting the suggested mark needs no reason (regression: accept used to fail with an empty reason)
    decision.select_option("approved")
    check("accept enables save without a reason", save_btn.is_enabled())
    check("accept locks the mark to the suggestion", page.locator("#final-marks").is_disabled())
    save_btn.click()
    page.wait_for_timeout(900)
    check("accept saved without error", "could not be saved" not in body())

    # ---------- 4b. Marks: whole-copy mode ----------
    page.get_by_role("button", name="Whole copy", exact=True).click()
    page.wait_for_timeout(500)
    check("whole-copy mode selected", page.get_by_role("button", name="Whole copy", exact=True).get_attribute("aria-pressed") == "true")
    m = re.search(r"(\d+) of (\d+) answers have a decision", body())
    check("whole-copy progress shown", m is not None)
    rows_copy = page.locator("table tbody tr")
    # Uploads can add answer regions to a sheet, so the total comes from the progress line, not a constant.
    check("whole-copy lists every answer", m is not None and rows_copy.count() == int(m.group(2)), f"rows={rows_copy.count()} progress={m.group(0) if m else None}")
    page.get_by_role("button", name="Calculate marks for whole copy").click()
    page.wait_for_timeout(1500)
    check("whole-copy run reports a result", "Marks calculated for" in body())
    check("skipped answers are explained", "Answers skipped in the last run" in body() and "Already decided" in body())
    page.get_by_role("checkbox", name=re.compile("recalculate")).check()
    page.get_by_role("button", name="Calculate marks for whole copy").click()
    page.wait_for_timeout(1500)
    check("recalculating decided answers no longer skips them", "Already decided" not in body())
    page.get_by_role("checkbox", name=re.compile("recalculate")).uncheck()
    page.screenshot(path=f"{SHOTS}/05b_marks_copy.png", full_page=True)
    leak_scan("marks copy")

    # Open one row in one-question mode
    rows_copy.nth(1).get_by_role("button", name="Open", exact=True).click()
    page.wait_for_timeout(500)
    check("Open switches to one-question mode", page.get_by_role("button", name="One question", exact=True).get_attribute("aria-pressed") == "true")
    check("Open shows the chosen answer", page.locator("h2", has_text="Mock 17-04").count() >= 1)
    page.get_by_role("button", name="Whole copy", exact=True).click()
    page.wait_for_timeout(300)

    # ---------- 5. Report ----------
    tab("Report")
    check("report lists per-question rows", page.locator("tbody tr").count() >= 1)
    check("report total row shown", "Total (" in body())
    export_btn = page.get_by_role("button", name="Export report (JSON)")
    check("export locked until authorised", export_btn.is_disabled())
    page.get_by_role("checkbox", name=re.compile("authorise")).check()
    check("export unlocked after authorisation", export_btn.is_enabled())
    with page.expect_download() as dl:
        export_btn.click()
    check("export downloads JSON report", dl.value.suggested_filename.endswith("-report.json"), dl.value.suggested_filename)
    page.locator("details summary", has_text="Activity log").click()
    page.wait_for_timeout(200)
    check("activity log lists events", page.locator("details li").count() >= 1)
    page.screenshot(path=f"{SHOTS}/06_report.png", full_page=True)
    leak_scan("report")

    # ---------- 6. Language (English / Hindi) ----------
    page.get_by_role("button", name="हिन्दी", exact=True).click()
    page.wait_for_timeout(500)
    page.get_by_role("button", name="प्रश्नपत्र", exact=True).click()
    page.wait_for_timeout(300)
    check("language switch to Hindi sets document lang", page.evaluate("document.documentElement.lang") == "hi")
    check("Hindi nav labels shown", page.get_by_role("button", name="प्रश्नपत्र", exact=True).count() == 1
          and page.get_by_role("button", name="Papers", exact=True).count() == 0)
    check("Hindi papers heading shown", "प्रश्नपत्र और अंकन योजनाएँ" in body())
    page.get_by_role("button", name="हस्तलेख", exact=True).click()
    page.wait_for_timeout(400)
    check("Hindi handwriting labels shown", "प्रतिलेख" in body() and "पठन" in body())
    page.get_by_role("button", name="अंक", exact=True).click()
    page.wait_for_timeout(400)
    check("Hindi grading modes shown", "एक प्रश्न" in body() and "पूरी कॉपी" in body())
    check("Hindi marks button shown", page.get_by_role("button", name=re.compile("अंक (गणना|पुनः|निकालें)")).count() >= 1)
    page.get_by_role("button", name="रिपोर्ट", exact=True).click()
    page.wait_for_timeout(400)
    check("Hindi report export label shown", "रिपोर्ट निर्यात करें (JSON)" in body())
    page.screenshot(path=f"{SHOTS}/07_hindi_report.png", full_page=True)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(800)
    check("language choice survives reload", page.evaluate("document.documentElement.lang") == "hi")
    page.get_by_role("button", name="English", exact=True).click()
    page.wait_for_timeout(400)
    check("switch back to English", page.evaluate("document.documentElement.lang") == "en"
          and page.get_by_role("button", name="Papers", exact=True).count() == 1)
    leak_scan("language switch")

    # ---------- global ----------
    check("no uncaught page errors", not page_errors, "; ".join(page_errors)[:300])
    real_console = [c for c in console_errors if "Failed to load resource" not in c]
    check("no console errors", not real_console, "; ".join(real_console)[:300])
    unexpected = [r for r in bad_responses if "/uploads" not in r]
    check("no unexpected HTTP errors", not unexpected, "; ".join(unexpected)[:300])

    browser.close()

passed = sum(1 for _, ok, _ in results if ok)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
