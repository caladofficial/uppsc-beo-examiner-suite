"""Answer-check service: upload a scanned answer sheet, get marks and missing points per question.

Endpoints
- GET  /health
- GET  /papers                 papers and questions the sheet can be checked against
- POST /check                  multipart: paper_id (form), file (PDF / PNG / JPG)

Flow: page image -> handwriting reader (CRNN-CTC, line level) -> split into answers by question
number -> answer_check.check_answer per question -> report.
"""
import importlib.util
import threading
import time
import uuid
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ADAPTERS = os.path.join(ROOT, "packages", "model-adapters")
PAPERS_JSON = os.path.join(ROOT, "apps", "web", "src", "data", "import-preview-report.json")
MAX_PAGES = 20
MAX_BYTES = 25 * 1024 * 1024

sys.path.insert(0, ADAPTERS)
import answer_check as AC  # noqa: E402
import vision_reader  # noqa: E402
import grading  # noqa: E402


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HTR = _load("htr_pipeline", os.path.join(ADAPTERS, "htr_pipeline.py"))

app = FastAPI(title="Answer check service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Shared secret: when SERVICE_KEY is set, every route except /health needs the matching X-Service-Key header.
_SERVICE_KEY = os.environ.get("SERVICE_KEY", "").strip()


def _token_ok(token: str) -> bool:
    """Short-lived token from the website server: "<unix time>.<HMAC of the time with the shared key>"."""
    import hashlib
    import hmac
    import time
    try:
        ts, sig = token.split(".", 1)
        stamp = int(ts)
    except ValueError:
        return False
    if abs(time.time() - stamp) > 600:
        return False
    expected = hmac.new(_SERVICE_KEY.encode(), ts.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


@app.middleware("http")
async def _require_key(request, call_next):
    from fastapi.responses import JSONResponse
    if _SERVICE_KEY and request.url.path != "/health" and request.method != "OPTIONS":
        key_ok = request.headers.get("x-service-key", "") == _SERVICE_KEY
        token_ok = _token_ok(request.headers.get("x-service-token", ""))
        if not (key_ok or token_ok):
            return JSONResponse({"detail": "Not authorised."}, status_code=401)
    return await call_next(request)

# A line starts a new answer only if it begins with a question number, followed by a separator.
HEADER = re.compile(
    r"^\s*(?:प्रश्न|प्र\.?|q\.?|question)?\s*(\d{1,2})\s*"
    r"(?:\(\s*([a-dA-D])\s*\)|([a-dA-D])(?=[\.\)]))?"
    r"(?=\s*[\.\):\-\(]|\s+)\s*[\.\):\-]?\s*"
    r"(?:\(\s*([a-dA-D])\s*\))?\s*(.*)$",
    re.IGNORECASE,
)


SUBPART = re.compile(r"^\s*\(?\s*([a-dA-D])\s*\)\s*(.*)$")


def _load_papers() -> Dict[str, Any]:
    with open(PAPERS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    papers = {}
    for p in data.get("papers", []):
        questions = []
        for q in p.get("questions", []):
            qid = q.get("question_id", "")
            # The printed number and sub-part come from the id: the Hindi paper's question_number is a
            # running index (1(a)=1, 1(b)=2, ...), not the number printed on the paper.
            m = re.search(r"-(\d+)\s*(?:\(?([a-dA-D])\)?)?\s*$", qid)
            number = int(m.group(1)) if m else int(q.get("question_number") or 0)
            letter = m.group(2).lower() if (m and m.group(2)) else None
            cq = q.get("canonical_question") or {}
            text = cq.get("en") or cq.get("hi") or ""
            questions.append({
                "question_id": qid,
                "number": number,
                "letter": letter,
                "max_marks": float(q.get("max_marks") or 0),
                "word_limit": q.get("word_limit"),
                "question_text": text[:400],
                "question_en": (cq.get("en") or "")[:600],
                "question_hi": (cq.get("hi") or "")[:600],
                "expected_points": (q.get("answer_outline") or {}).get("expected_points") or [],
                "section": q.get("section"),
            })
        papers[p["paper_id"]] = {
            "paper_id": p["paper_id"],
            "title": p.get("exam_name") or p["paper_id"],
            "subject": p.get("subject"),
            "mock_label": p.get("mock_label"),
            "questions": questions,
        }
    return papers


PAPERS = _load_papers()


def _label(q: Dict[str, Any]) -> str:
    return f"Q{q['number']}" + (f"({q['letter']})" if q["letter"] else "")


def _public_paper(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "paper_id": p["paper_id"],
        "title": p["title"],
        "subject": p["subject"],
        "mock_label": p["mock_label"],
        "question_count": len(p["questions"]),
        "total_marks": sum(q["max_marks"] for q in p["questions"]),
    }


def _read_pages(raw: bytes, filename: str) -> List[Tuple[np.ndarray, str]]:
    """Return grey page images. PDFs are rendered page by page."""
    if raw[:5] == b"%PDF-":
        import pymupdf
        doc = pymupdf.open(stream=raw, filetype="pdf")
        pages = []
        for i in range(min(len(doc), MAX_PAGES)):
            pix = doc[i].get_pixmap(dpi=150, colorspace=pymupdf.csGRAY)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
            pages.append((img, f"page {i + 1}"))
        return pages
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(status_code=400, detail="The file could not be read as an image.")
    return [(img, "page 1")]


def _read_lines(raw: bytes, filename: str) -> Tuple[List[str], Dict[str, Any]]:
    """Read every page: the vision model first, the line reader only when the model cannot be used."""
    pages = _read_pages(raw, filename)
    lines: List[str] = []
    info = {"pages": len(pages), "vision_pages": 0, "fallback_pages": 0}
    for img, _name in pages:
        text = vision_reader.transcribe_image(img)
        if text:
            info["vision_pages"] += 1
            lines.extend(ln.strip() for ln in text.splitlines() if ln.strip())
            continue
        info["fallback_pages"] += 1
        res = HTR.recognise(img, HTR.Config(), *HTR.load_default_model())
        lines.extend(seg.text.strip() for seg in res.segments if seg.text.strip())
    return lines, info


def _edit1(a: str, b: str) -> bool:
    """True when two strings differ by at most one character (substitution, insertion or deletion)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def _lev(a: str, b: str) -> int:
    """Edit distance between two short strings."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _fuzzy_item(line: str, order: List[Tuple[int, Optional[str]]], last_idx: int) -> Optional[int]:
    """Match a misread sub-part header such as '((b)', 'N(c)', '4ia)' or 'dla)' to one of the next few items.
    Only lines whose first token has a bracket and ends in a sub-part letter qualify, and the letter must agree."""
    parts = line.split()
    if not parts:
        return None
    head = parts[0]
    if not re.search(r"[()\[\]]", head):
        return None
    h = re.sub(r"[^0-9a-z]", "", head.lower())
    if h and h[-1] in "0o":  # common misread of the letter d
        h = h[:-1] + "d"
    if not h or len(h) > 5 or not h[-1].isalpha():
        return None
    for idx in range(last_idx + 1, min(last_idx + 7, len(order))):
        num, letter = order[idx]
        if letter is None or letter != h[-1]:
            continue
        if _lev(h, f"{num}{letter}") <= 2:
            return idx
    return None


def _split_answers(lines: List[str], questions: List[Dict[str, Any]]):
    """Group reader lines into answers, following the paper's question order.

    - A header starts an answer only if it names a question that comes AFTER the last accepted one.
      A number that points backwards (e.g. "11." after "16.") is a misread, not a new answer, so it
      stays in the current answer and is noted.
    - A two-digit header misread by one character (e.g. "11." for "17.") is corrected to the next
      expected question, only when that question is the next one in order.
    - A short unreadable token followed by a dot (e.g. "t.") at a point where the next question is
      due is taken as that question's header, and the answer is flagged for a person to confirm.
    Returns (blocks, unmatched, guessed_headers).
    """
    order = [(q["number"], q["letter"]) for q in questions]
    index = {k: i for i, k in enumerate(order)}
    blocks: Dict[Tuple[int, Optional[str]], List[str]] = {}
    unmatched: List[str] = []
    guessed: set = set()
    current: Optional[Tuple[int, Optional[str]]] = None
    last_idx = -1  # index in `order` of the last accepted header

    def accept(key, rest, guess=False):
        nonlocal current, last_idx
        current = key
        last_idx = index[key]
        blocks.setdefault(key, [])
        if guess:
            guessed.add(key)
        if rest:
            blocks[key].append(rest)

    for line in lines:
        m = HEADER.match(line)
        if m:
            num = int(m.group(1))
            letter = (m.group(2) or m.group(3) or m.group(4) or "").lower() or None
            key = (num, letter)
            # A bare digit inside a sub-part block, when the sibling sub-part is due next, is almost always a
            # misread roman numeral such as "(ii)" -> "2": keep it as text rather than starting a new question.
            sibling_due = (current is not None and current[1] is not None and last_idx + 1 < len(order)
                           and order[last_idx + 1][0] == current[0] and key[0] != current[0])
            bare = letter is None and not re.match(r"^\s*\d{1,2}\s*[.)]", line)
            if sibling_due and bare:
                blocks[current].append(line)
                guessed.add(current)  # could be a misread "(ii)" or a real question: a person confirms
                continue
            if key in index and index[key] > last_idx:
                accept(key, (m.group(5) or "").strip())
                continue
            nxt = last_idx + 1
            if len(m.group(1)) == 2 and nxt < len(order) and _edit1(m.group(1), str(order[nxt][0])):
                # two-digit misread of the next expected question
                accept(order[nxt], (m.group(5) or "").strip())
                continue
            if key in index and current is not None:
                unmatched.append(f"{num}{'(' + letter + ')' if letter else ''}")  # backwards: keep as text
            if current is not None:
                # a numbered line we could not place: the answer it lands in may be mixed, so flag it
                guessed.add(current)
        fz = _fuzzy_item(line, order, last_idx)
        if fz is not None:
            accept(order[fz], "", guess=True)
            tail = line.split(None, 1)
            if len(tail) > 1:
                blocks[order[fz]].append(tail[1])
            continue
        # sub-part marker alone, e.g. "(b)" or "b)", directly after its question number
        sm = SUBPART.match(line)
        if sm and current is not None and (current[0], sm.group(1).lower()) in index and index[(current[0], sm.group(1).lower())] > last_idx:
            accept((current[0], sm.group(1).lower()), (sm.group(2) or "").strip())
            continue
        # unreadable header: a short token and a dot where the next question is due
        if not m and last_idx + 1 < len(order):
            gm = re.match(r"^\s*([^\s\w]?\w{1,2})[\.\)]\s+(\S.*)$", line)
            nxt_key = order[last_idx + 1]
            tok = gm.group(1) if gm else ""
            if gm and tok.isalpha() and not re.search(r"[aeiouAEIOU]", tok) and nxt_key[1] is None:
                accept(nxt_key, gm.group(2).strip(), guess=True)
                continue
        if current is not None:
            blocks[current].append(line)
    return blocks, unmatched, guessed


def _status(marks: float, max_marks: float, needs_review: bool, read: bool) -> str:
    if not read:
        return "not_answered"
    if needs_review:
        return "needs_review"
    if max_marks and marks >= 0.7 * max_marks:
        return "good"
    if max_marks and marks >= 0.3 * max_marks:
        return "partial"
    return "low"


@app.get("/health")
def health():
    return {"status": "ok", "papers": len(PAPERS)}


@app.get("/papers")
def papers():
    return {"papers": [_public_paper(p) for p in PAPERS.values()]}


@app.post("/check")
async def check(paper_id: str = Form(...), file: UploadFile = File(...), use_llm: bool = Form(True)):
    paper = PAPERS.get(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found.")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The file is empty.")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="The file is larger than 25 MB.")
    if raw[:5] != b"%PDF-" and raw[:3] != b"\xff\xd8\xff" and raw[:4] != b"\x89PNG":
        raise HTTPException(status_code=400, detail="Upload a PDF, PNG or JPG file.")

    lines, reader_info = _read_lines(raw, file.filename or "")
    line_total = len(lines)
    flagged_total = 0

    blocks, unmatched, guessed = _split_answers(lines, paper["questions"])
    page_notes: List[Dict[str, Any]] = []  # codes are translated by the page; no engineering text
    if line_total == 0:
        page_notes.append({"code": "no_text"})
    if reader_info["fallback_pages"] and not reader_info["vision_pages"]:
        page_notes.append({"code": "hard_to_read"})
    if unmatched:
        page_notes.append({"code": "unmatched_numbers", "detail": ", ".join(sorted(set(unmatched))[:10])})
    if line_total and not blocks:
        page_notes.append({"code": "no_numbers"})

    results = []
    total = 0.0
    max_total = 0.0
    for q in paper["questions"]:
        key = (q["number"], q["letter"])
        if key not in blocks:
            continue
        text = " ".join(blocks[key]).strip()
        chk = AC.check_answer(q, text, use_llm=use_llm)
        if key in guessed:  # header was unreadable: the answer is assigned by order, so a person confirms it
            chk["review_codes"] = list(chk.get("review_codes", [])) + ["header_unclear"]
            chk["needs_review"] = True
        total += chk["marks"]
        max_total += q["max_marks"]
        read = bool(text)
        results.append({
            "question_id": q["question_id"],
            "label": _label(q),
            "question_text": q["question_text"],
            "max_marks": q["max_marks"],
            "marks": chk["marks"],
            "status": _status(chk["marks"], q["max_marks"], chk["needs_review"], read),
            "word_limit": q.get("word_limit"),
            "review_codes": chk.get("review_codes", []),
            "method": chk["method"],
            "missing_points": [p["point"] for p in chk["points"] if not p["covered"] and not p.get("partial")],
            "partial_points": [p["point"] for p in chk["points"] if p.get("partial")],
            "covered_points": [p["point"] for p in chk["points"] if p["covered"]],
            "points_total": len(chk["points"]),
            "notes": chk["notes"],
            "word_count": chk["word_count"],
            "read_text": text,
        })

    answered = {r["question_id"] for r in results}
    not_found = [_label(q) for q in paper["questions"] if q["question_id"] not in answered]
    return {
        "paper": _public_paper(paper),
        "total_marks": round(total, 1),
        "max_total": round(max_total, 1),
        "questions": results,
        "not_found": not_found[:60],
        "page_notes": page_notes,
        "reader": {"lines": line_total, "flagged_lines": flagged_total},
        "checked_by": "keyword+llm" if any(r["method"] == "keyword+llm" for r in results) else "keyword",  # API only
    }


# ---------------------------------------------------------------------------
# Single-question grading: the student picks a question, uploads the sheet, and gets marks,
# good points, missing points and the model answer for that question.

@app.get("/questions")
def questions(paper_id: str):
    paper = PAPERS.get(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found.")
    return {
        "paper_id": paper_id,
        "title": paper["title"],
        "subject": paper["subject"],
        "language": grading.paper_language(paper_id),
        "questions": [
            {
                "question_id": q["question_id"],
                "label": _label(q),
                "max_marks": q["max_marks"],
                "word_limit": q.get("word_limit"),
                "question_en": q.get("question_en", ""),
                "question_hi": q.get("question_hi", ""),
            }
            for q in paper["questions"]
        ],
    }



def _grade_bytes(paper_id: str, question_id: str, raw: bytes, filename: str, use_llm: bool) -> Dict[str, Any]:
    """Grade one question from the uploaded bytes. Runs in a worker thread, never on the event loop."""
    paper = PAPERS.get(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found.")
    q = next((x for x in paper["questions"] if x["question_id"] == question_id), None)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    if not raw:
        raise HTTPException(status_code=400, detail="The file is empty.")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="The file is larger than 25 MB.")
    if raw[:5] != b"%PDF-" and raw[:3] != b"\xff\xd8\xff" and raw[:4] != b"\x89PNG":
        raise HTTPException(status_code=400, detail="Upload a PDF, PNG or JPG file.")

    lines, reader_info = _read_lines(raw, filename)
    blocks, _unmatched, guessed = _split_answers(lines, paper["questions"])
    key = (q["number"], q["letter"])
    text = " ".join(blocks.get(key, [])).strip()
    base = {
        "question_id": q["question_id"], "label": _label(q), "max_marks": q["max_marks"],
        "word_limit": q.get("word_limit"), "reader": reader_info,
    }
    if not text:
        return {**base, "status": "not_found", "marks": 0.0, "review_codes": [], "good_points": {"en": [], "hi": []},
                "missing_points": {"en": [], "hi": []}, "feedback": {"en": "", "hi": ""}, "model_answer": None,
                "read_text": "", "method": None}

    kw = AC.keyword_check(q, text)
    model_text = grading.model_answer(paper_id, q) if use_llm else None
    llm = grading.grade(paper_id, q, model_text, text) if (use_llm and model_text) else None
    res = grading.combine(q, text, kw, llm)
    if key in guessed:  # the header was hard to read: a person confirms that the answer belongs here
        res["review_codes"] = list(res["review_codes"]) + ["header_unclear"]
        res["needs_review"] = True
    status = _status(res["marks"], q["max_marks"], res["needs_review"], True)
    return {
        **base, "status": status, "marks": res["marks"], "method": res["method"],
        "review_codes": res["review_codes"], "good_points": res["good_points"],
        "missing_points": res["missing_points"], "feedback": res["feedback"],
        "llm_marks": res["llm_marks"], "model_answer": model_text, "read_text": text,
        "word_count": kw["word_count"], "points_total": len(kw["points"]),
    }

@app.post("/grade")
async def grade_one(paper_id: str = Form(...), question_id: str = Form(...),
                    file: UploadFile = File(...), use_llm: bool = Form(True)):
    raw = await file.read()
    return await run_in_threadpool(_grade_bytes, paper_id, question_id, raw, file.filename or "", use_llm)


# Background grading jobs: the browser starts a job, then polls. Long runs never hold one HTTP request open.
_JOBS: Dict[str, Dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


def _prune_jobs() -> None:
    cutoff = time.time() - 3600
    with _JOBS_LOCK:
        for jid in [k for k, v in _JOBS.items() if v.get("created", 0) < cutoff]:
            _JOBS.pop(jid, None)


@app.post("/grade-jobs")
async def start_grade_job(paper_id: str = Form(...), question_id: str = Form(...),
                          file: UploadFile = File(...), use_llm: bool = Form(True)):
    paper = PAPERS.get(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found.")
    if not any(x["question_id"] == question_id for x in paper["questions"]):
        raise HTTPException(status_code=404, detail="Question not found.")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The file is empty.")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="The file is larger than 25 MB.")
    if raw[:5] != b"%PDF-" and raw[:3] != b"\xff\xd8\xff" and raw[:4] != b"\x89PNG":
        raise HTTPException(status_code=400, detail="Upload a PDF, PNG or JPG file.")
    filename = file.filename or ""
    job_id = uuid.uuid4().hex
    _prune_jobs()
    with _JOBS_LOCK:
        _JOBS[job_id] = {"status": "running", "created": time.time()}

    def run() -> None:
        try:
            state: Dict[str, Any] = {"status": "done", "result": _grade_bytes(paper_id, question_id, raw, filename, use_llm)}
        except HTTPException as exc:
            state = {"status": "error", "detail": str(exc.detail)}
        except Exception as exc:  # the job must not hang; the cause goes to the service log
            print(f"[grade-jobs] {type(exc).__name__}: {exc}", file=sys.stderr)
            state = {"status": "error", "detail": "The answer could not be checked."}
        with _JOBS_LOCK:
            _JOBS[job_id].update(state)

    threading.Thread(target=run, daemon=True).start()
    return {"job_id": job_id}


@app.get("/grade-jobs/{job_id}")
def grade_job_status(job_id: str):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        snapshot = dict(job) if job else None
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    out: Dict[str, Any] = {"status": snapshot["status"]}
    if snapshot["status"] == "done":
        out["result"] = snapshot["result"]
    if snapshot["status"] == "error":
        out["detail"] = snapshot["detail"]
    return out
