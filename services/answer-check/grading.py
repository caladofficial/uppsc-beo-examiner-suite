"""Model answers and full grading for one question, using the Groq API.

- model_answer(paper, q): written once per question by the model from the question and the paper's
  expected points, then cached in data/model_answers.json so every student is marked against the same answer.
- grade(q, model_answer, student_text, keyword): one JSON call that returns marks, which expected points are
  covered, good points, missing points and short feedback in English and Hindi. The keyword check is used
  as a cross-check, with the same disagreement rule as the answer-check module.
No key is written to any file here: the key is read from the GROQ_API_KEY environment variable.
"""
import json
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

ADAPTERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "packages", "model-adapters")
sys.path.insert(0, os.path.abspath(ADAPTERS))
import answer_check as AC  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(HERE, "data", "model_answers.json")
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
_lock = threading.Lock()


def _chat_json(messages: List[Dict[str, str]], max_tokens: int) -> Optional[Dict[str, Any]]:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    body = {
        "model": MODEL, "temperature": 0.0, "reasoning_effort": "low",
        "max_completion_tokens": max_tokens, "response_format": {"type": "json_object"},
        "messages": messages,
    }
    for attempt in range(5):
        AC._pace()
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post("https://api.groq.com/openai/v1/chat/completions",
                                   headers={"Authorization": f"Bearer {key}"}, json=body)
        except Exception as exc:
            print(f"[grading] call failed: {type(exc).__name__}", file=sys.stderr)
            return None
        if resp.status_code == 429 and attempt < 4:
            wait = float(resp.headers.get("retry-after", "5") or 5)
            time.sleep(min(max(wait, 1.0), 60.0))
            continue
        if resp.status_code != 200:
            print(f"[grading] HTTP {resp.status_code}", file=sys.stderr)
            return None
        try:
            data = resp.json()
            AC._note_tokens(data)
            out = json.loads(data["choices"][0]["message"]["content"])
            return out if isinstance(out, dict) else None
        except Exception:
            print("[grading] reply unreadable", file=sys.stderr)
            return None
    return None


def _load_cache() -> Dict[str, Any]:
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CACHE_PATH)


def paper_language(paper_id: str) -> str:
    return "hi" if "hindi" in paper_id.lower() else "en"


def model_answer(paper_id: str, q: Dict[str, Any]) -> Optional[str]:
    """The model answer for a question, generated once and cached."""
    with _lock:
        cache = _load_cache()
        if q["question_id"] in cache:
            return cache[q["question_id"]]["text"]
    points = [p for p in q.get("expected_points", []) if isinstance(p, str)]
    lang = paper_language(paper_id)
    lang_name = "Hindi (Devanagari)" if lang == "hi" else "English"
    prompt = (
        "You write model answers for a UPPSC BEO Mains examination.\n"
        f"Question: {q.get('question_text', '')}\n"
        f"Marks: {q['max_marks']}. Word limit: {q.get('word_limit') or 'not stated'}.\n"
        "The model answer must cover every point below, in clear exam language, within the word limit. "
        "Do not add a heading. Do not number the points.\n"
        "Points to cover:\n" + "\n".join(f"- {p}" for p in points) + "\n"
        f"Write the answer in {lang_name}. Return JSON: {{\"model_answer\": \"...\"}}"
    )
    out = _chat_json([{"role": "system", "content": "Return valid JSON only."},
                      {"role": "user", "content": prompt}], max_tokens=1500)
    text = (out or {}).get("model_answer")
    if not isinstance(text, str) or not text.strip():
        return None
    with _lock:
        cache = _load_cache()
        cache[q["question_id"]] = {"text": text.strip(), "language": lang}
        _save_cache(cache)
    return text.strip()


def grade(paper_id: str, q: Dict[str, Any], model_text: str, student_text: str) -> Optional[Dict[str, Any]]:
    """One JSON call that marks the answer against the model answer and the expected points."""
    points = [p for p in q.get("expected_points", []) if isinstance(p, str)]
    max_marks = float(q["max_marks"])
    numbered = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(points))
    prompt = (
        "You are an experienced UPPSC BEO Mains examiner. Mark the student's answer fairly.\n"
        f"Question: {q.get('question_text', '')}\n"
        f"Maximum marks: {max_marks}. Word limit: {q.get('word_limit') or 'not stated'} "
        "(exceeding it is noted but does not reduce marks).\n"
        f"Model answer:\n{model_text}\n\n"
        f"Expected points:\n{numbered}\n\n"
        "Student's answer (read from the sheet; it may contain small reading errors. Do not penalise "
        "obvious misreadings of single letters, but do penalise missing content):\n"
        f"<<<{student_text}>>>\n\n"
        "Rules:\n"
        "- Reward correct content, including correct paraphrase in English or Hindi.\n"
        "- Give partial marks for partly correct points. Give 0 for empty or unrelated answers.\n"
        "- Marks are between 0 and the maximum, in steps of 0.5.\n"
        "- For each expected point give status: covered, partial or missing.\n"
        "- good_points: 2 to 4 specific things the student did well. Refer to the actual content.\n"
        "- missing_points: the important points that are absent, written as what the student should have "
        "added. Give 0 items if nothing important is missing.\n"
        "- Give both English and Hindi versions of good_points, missing_points and feedback.\n"
        "- feedback: one or two sentences for the student.\n"
        "Return JSON with exactly these keys: marks (number), points (list of {index, status}), "
        "good_points_en, good_points_hi, missing_points_en, missing_points_hi, feedback_en, feedback_hi."
    )
    return _chat_json([{"role": "system", "content": "Return valid JSON only."},
                       {"role": "user", "content": prompt}], max_tokens=2000)


def _strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if isinstance(v, (str, int, float)) and str(v).strip()][:6]


def combine(q: Dict[str, Any], student_text: str, kw: Dict[str, Any], llm: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge keyword and LLM results into one per-question result, using the same review rules as answer_check."""
    review: List[str] = []
    notes: List[str] = []
    max_marks = float(q["max_marks"])
    word_limit = q.get("word_limit")
    if word_limit and kw["word_count"] > int(word_limit) * 1.1:
        review.append("word_limit")
    result: Dict[str, Any] = {
        "marks": kw["marks"], "method": "keyword", "review_codes": review, "needs_review": bool(review),
        "good_points": {"en": [], "hi": []}, "missing_points": {"en": [], "hi": []},
        "feedback": {"en": "", "hi": ""}, "llm_marks": None,
    }
    if llm is None:
        if student_text.strip():
            review.append("single_check")
        result["missing_points"]["en"] = [r["point"] for r in kw["points"] if not r["covered"] and not r.get("partial")]
        result["good_points"]["en"] = [r["point"] for r in kw["points"] if r["covered"]]
        return result

    try:
        llm_marks = max(0.0, min(max_marks, AC.round_half(float(llm.get("marks", 0)))))
    except (TypeError, ValueError):
        llm_marks = None
    if llm_marks is None:
        review.append("single_check")
        return result

    llm_cov = {}
    pts = llm.get("points") if isinstance(llm.get("points"), list) else []
    for item in pts:
        if isinstance(item, dict):
            try:
                llm_cov[int(item.get("index")) - 1] = str(item.get("status", "missing")).lower()
            except (TypeError, ValueError):
                continue
    disagree_marks = abs(llm_marks - kw["marks"]) > 0.25 * max_marks if max_marks else False
    disagree_points = 0
    for i, row in enumerate(kw["points"]):
        says = llm_cov.get(i)
        if says is None:
            continue
        kw_says = "covered" if row["covered"] else ("partial" if row.get("partial") else "missing")
        if says != kw_says and {says, kw_says} != {"covered", "partial"}:
            disagree_points += 1
    if disagree_marks or disagree_points > max(1, len(kw["points"]) // 4):
        review.append("disagree")
        result["needs_review"] = True
    result["marks"] = llm_marks if not disagree_marks else min(llm_marks, kw["marks"])
    result["method"] = "keyword+llm"
    result["llm_marks"] = llm_marks
    result["good_points"] = {"en": _strings(llm.get("good_points_en")), "hi": _strings(llm.get("good_points_hi"))}
    result["missing_points"] = {"en": _strings(llm.get("missing_points_en")), "hi": _strings(llm.get("missing_points_hi"))}
    result["feedback"] = {"en": str(llm.get("feedback_en") or "")[:400], "hi": str(llm.get("feedback_hi") or "")[:400]}
    return result
