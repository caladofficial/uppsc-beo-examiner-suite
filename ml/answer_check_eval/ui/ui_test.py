import re
from playwright.sync_api import sync_playwright

OUT = "/home/user/ml/answer_check_eval/ui"
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1100, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:3000", wait_until="networkidle")
    page.screenshot(path=f"{OUT}/1_start.png", full_page=True)
    cards = page.get_by_role("button").filter(has_text=re.compile("17|16"))
    print("paper cards:", [c.inner_text().replace("\n", " | ") for c in cards.all()])
    cards.first.click()
    q2 = page.get_by_role("button", name=re.compile(r"Q2\b|Mock 17-02")).first
    q2.wait_for(timeout=20000)
    page.screenshot(path=f"{OUT}/2_questions.png", full_page=True)
    q2.click()
    page.get_by_role("button", name="Next").click()
    page.locator("input[type=file]").set_input_files("/home/user/ml/answer_check_eval/sheets/gs17_sheet_a.pdf")
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Start").click()
    page.get_by_role("button", name="Check another question").wait_for(timeout=240000)
    page.wait_for_timeout(800)
    page.screenshot(path=f"{OUT}/3_result_en.png", full_page=True)
    print("EN result text:\n", page.locator("main").inner_text()[:1500])
    page.get_by_role("button", name="हिन्दी").click()
    page.wait_for_timeout(300)
    print("html lang:", page.evaluate("document.documentElement.lang"), "| saved:", page.evaluate("localStorage.getItem('uppsc-ui-language')"))
    page.screenshot(path=f"{OUT}/4_result_hi.png", full_page=True)
    print("HI result text:\n", page.locator("main").inner_text()[:800])
    page.reload(wait_until="networkidle")
    print("after reload html lang:", page.evaluate("document.documentElement.lang"))
    print("page errors:", errors)
    b.close()
