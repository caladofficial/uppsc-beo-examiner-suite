"""Build synthetic handwritten answer sheets (PDF) from the paper's own expected points, with ground truth.

Each answer is written at one of three designed levels:
  strong : first 3 expected points          -> expected mark fraction >= 0.5
  weak   : first expected point only         -> expected mark fraction <= 0.35
  off    : an expected point from another question (wrong topic) -> expected 0
These are renderer handwriting images, not real student scripts.
"""
import json, sys
from pathlib import Path
import fitz  # pymupdf
import cv2, numpy as np

sys.path.insert(0, "/home/user/ml/htr")
import htr_data as H

ROOT = Path("/home/user/ml/answer_check_eval")
OUT = ROOT / "sheets"
PAPERS = json.load(open("/home/user/apps/web/src/data/import-preview-report.json"))["papers"]
CAP = 22  # lines per page (A4 at 150 dpi with our margins)


def pages_from_texts(texts, seed):
    """Split paragraphs into pages of at most CAP wrapped lines; never split a paragraph's header from its text."""
    pages, cur, n = [], [], 0
    for t in texts:
        k = len(H.wrap(t, H.PAGE_W - 2 * H.MARGIN_X - 60))
        if cur and n + k > CAP:
            pages.append(cur); cur, n = [], 0
        cur.append(t); n += k
    if cur:
        pages.append(cur)
    return pages


def build(paper, levels, name, header_fmt, seed0):
    qs = paper["questions"]
    paras, truth = [], []
    import re
    generic = re.compile(r"Key constitutional, historical, or policy significance|Concise illustration or example|within the 25-word", re.I)
    all_points = [p for q in qs for p in q["answer_outline"]["expected_points"] if not generic.search(p)]
    for i, q in enumerate(qs):
        pts = q["answer_outline"]["expected_points"]
        lvl = levels[i % len(levels)]
        if lvl == "strong":
            body = " ".join(pts[:3])
        elif lvl == "weak":
            body = pts[0]
        else:  # off-topic: a point from a different question
            other = all_points[(i * 7 + 13) % len(all_points)]
            body = other
        header = header_fmt(q)
        paras.append(f"{header} {body}")
        truth.append({"question_id": q["question_id"], "level": lvl, "max_marks": q["max_marks"]})
    pages = pages_from_texts(paras, seed0)
    doc = fitz.open()
    gt_all = []
    for pi, page_texts in enumerate(pages):
        img, gt, _ = H.make_copy(page_texts, seed=seed0 + pi, strength=[0.8, 1.0][pi % 2])
        gt_all.extend([g[0] for g in gt])
        ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        pix = fitz.Pixmap(enc.tobytes())
        pg = doc.new_page(width=pix.width * 0.5, height=pix.height * 0.5)
        pg.insert_image(pg.rect, stream=enc.tobytes())
    pdf = OUT / f"{name}.pdf"
    doc.save(pdf)
    json.dump({"paper_id": paper["paper_id"], "pdf": pdf.name, "truth": truth,
               "gt_lines": gt_all, "pages": len(pages)}, open(OUT / f"{name}.truth.json", "w"),
              ensure_ascii=False, indent=1)
    print(name, "pages", len(pages), "questions", len(truth), "gt lines", len(gt_all))


if __name__ == "__main__":
    gs = PAPERS[0]
    build(gs, ["strong", "weak", "off"], "gs17_sheet_a", lambda q: f"{q['question_number']}.", 4100)
