"""Score one /check response against the designed answer levels in a sheet's truth file."""
import json, sys
from collections import Counter

run_path, truth_path = sys.argv[1], sys.argv[2]
r = json.load(open(run_path))
truth = json.load(open(truth_path))
rows = r.get("questions") or r.get("results") or []
if not rows:
    print("no rows; keys:", list(r.keys())); sys.exit(1)
by_id = {x.get("question_id"): x for x in rows}
PAPERS = json.load(open("/home/user/apps/web/src/data/import-preview-report.json"))["papers"]
paper_pts = {q["question_id"]: q["answer_outline"]["expected_points"] for p in PAPERS for q in p["questions"]}
print("keys:", list(rows[0].keys()))
print("methods:", dict(Counter(x.get("method") for x in rows)))
print("review codes:", dict(Counter(c for x in rows for c in (x.get("review_codes") or []))))
print("single_check fallbacks:", sum(1 for x in rows if "single_check" in (x.get("review_codes") or [])))
band_ok = Counter(); band_n = Counter(); miss = []
for t in truth["truth"]:
    x = by_id.get(t["question_id"])
    if x is None:
        miss.append(t["question_id"]); continue
    pct = (x.get("marks") or 0) / (t["max_marks"] or 1)
    lvl = t["level"]
    band_n[lvl] += 1
    n_pts = len(paper_pts.get(t["question_id"], [])) or 1
    if lvl == "strong":   # first 3 expected points written
        ok = pct >= 0.5  # at least half the marks for three written points
    elif lvl == "weak":   # first expected point only
        ok = abs(pct - 1 / n_pts) <= 0.2
    else:                 # off-topic: nothing expected
        ok = pct <= 0.1
    band_ok[lvl] += int(ok)
    if not ok:
        print(f"  MISMATCH {t['question_id']} level={lvl} marks={x.get('marks')}/{t['max_marks']} method={x.get('method')} codes={x.get('review_codes')}")
print("missing questions:", miss)
print("not_found (service):", r.get("not_found"))
print("page notes:", r.get("page_notes"))
print("checked_by:", r.get("checked_by"))
print("band accuracy:", {k: f"{band_ok[k]}/{band_n[k]}" for k in band_n}, "overall", f"{sum(band_ok.values())}/{sum(band_n.values())}")
print("total marks:", r.get("total_marks"), "of", r.get("max_total") or r.get("total_max") or r.get("max_marks_total"))
