"""Answer checking against the model answer for UPPSC BEO Mains questions.

Pipeline per question:
1. Keyword check (always on): every expected point of the model answer is compared with the student
   text. Tokens are matched fuzzily so that small handwriting-reader errors do not count as misses.
2. LLM check (only when GROQ_API_KEY is set): the same points are judged by a language model that
   returns the evidence it used. A second, independent opinion.
3. Cross-check: if the two methods disagree on marks or on which points are covered, the answer is
   marked for human review instead of being silently trusted.

The checker never sees the expected answer in the reader stage, and never guesses text that was not read.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

STOPWORDS = {
    # English
    "the", "a", "an", "of", "and", "or", "in", "on", "to", "for", "is", "are", "was", "were", "by", "with",
    "as", "that", "this", "it", "be", "from", "at", "its", "their", "which", "such", "also", "like", "into",
    # Hindi (common function words)
    "और", "का", "की", "के", "में", "से", "को", "है", "हैं", "पर", "यह", "एक", "इस", "वह", "तथा", "एवं",
    "भी", "था", "थे", "ने", "कि", "जो", "हो", "गया", "रहा", "या", "हुए", "हुआ", "किया", "किए", "लिए",
}

LOW_CREDIT = 0.25   # coverage needed for half credit of a point
FULL_CREDIT = 0.5   # coverage needed for full credit of a point
FUZZY_LATIN = 0.80
FUZZY_DEVA = 0.72   # handwriting-reader errors on matras are common, so a looser match


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    # Devanagari digits -> ASCII digits
    text = text.translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    text = text.lower()
    text = re.sub(r"[\(\)\[\]\{\}\.,;:!?\"'“”‘’।॥\-–—/\\|]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def keywords(text: str) -> List[str]:
    out = []
    for tok in normalise(text).split(" "):
        if not tok or tok in STOPWORDS or tok.isdigit():
            continue
        is_deva = bool(re.search("[\u0900-\u097F]", tok))
        min_len = 2 if is_deva else 3
        if len(tok) >= min_len:
            out.append(tok)
    # keep order, drop duplicates
    seen, res = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            res.append(t)
    return res


def _token_matches(kw: str, answer_tokens: List[str], answer_norm: str) -> bool:
    if kw in answer_norm:
        return True
    threshold = FUZZY_DEVA if re.search("[\u0900-\u097F]", kw) else FUZZY_LATIN
    for at in answer_tokens:
        if abs(len(at) - len(kw)) > max(3, len(kw) // 2):
            continue
        if SequenceMatcher(None, kw, at).ratio() >= threshold:
            return True
    return False


def point_coverage(point: str, answer_text: str) -> Tuple[float, List[str], List[str]]:
    """Share of a model-answer point's keywords found in the student's answer."""
    kws = keywords(point)
    if not kws:
        return 0.0, [], []
    a_norm = normalise(answer_text)
    a_tokens = a_norm.split(" ")
    hit = [k for k in kws if _token_matches(k, a_tokens, a_norm)]
    miss = [k for k in kws if k not in hit]
    return len(hit) / len(kws), hit, miss


def point_credit(coverage: float) -> float:
    if coverage >= FULL_CREDIT:
        return 1.0
    if coverage >= LOW_CREDIT:
        return 0.5
    return 0.0


def round_half(x: float) -> float:
    return round(x * 2) / 2.0


def word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", normalise(text)) if w])


def keyword_check(question: Dict[str, Any], answer_text: str) -> Dict[str, Any]:
    points = [p for p in (question.get("expected_points") or []) if isinstance(p, str) and p.strip()]
    max_marks = float(question.get("max_marks") or 0)
    words = word_count(answer_text)
    if not answer_text.strip() or words == 0:
        return {
            "marks": 0.0, "max_marks": max_marks, "method": "keyword",
            "points": [{"point": p, "coverage": 0.0, "covered": False} for p in points],
            "word_count": 0, "notes": ["No readable answer found for this question."],
        }
    rows, credits = [], []
    for p in points:
        cov, hit, miss = point_coverage(p, answer_text)
        credits.append(point_credit(cov))
        rows.append({"point": p, "coverage": round(cov, 2), "covered": cov >= FULL_CREDIT,
                     "partial": LOW_CREDIT <= cov < FULL_CREDIT})
    share = sum(credits) / len(points) if points else 0.0
    marks = min(max_marks, round_half(share * max_marks))
    return {"marks": marks, "max_marks": max_marks, "method": "keyword", "points": rows,
            "word_count": words, "notes": []}


_TPM_BUDGET = int(os.environ.get("GROQ_TPM_BUDGET", "6500"))  # account limit is 8,000 tokens per minute
_EST_TOKENS = 2000                                               # rough size of one check
_recent_tokens: List[Tuple[float, int]] = []                     # (time, tokens) of recent calls


def _pace(need: int = _EST_TOKENS) -> None:
    """Wait until the last minute's token use leaves room for one more check (keeps us under the limit)."""
    while True:
        now = time.time()
        _recent_tokens[:] = [(t, n) for t, n in _recent_tokens if now - t < 60.0]
        used = sum(n for _, n in _recent_tokens)
        if used + need <= _TPM_BUDGET or not _recent_tokens:
            return
        oldest = min(t for t, _ in _recent_tokens)
        time.sleep(min(max(60.0 - (now - oldest), 0.5), 15.0))


def _note_tokens(resp_json: Any) -> None:
    try:
        n = int((resp_json.get("usage") or {}).get("total_tokens") or _EST_TOKENS)
    except (AttributeError, TypeError, ValueError):
        n = _EST_TOKENS
    _recent_tokens.append((time.time(), n))


def _groq_check(question: Dict[str, Any], answer_text: str, timeout: float = 20.0) -> Optional[Dict[str, Any]]:
    """Second opinion from an LLM. Returns None when no key is configured or the call fails."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key or not answer_text.strip():
        return None
    try:
        import httpx
    except ImportError:
        return None
    points = [p for p in (question.get("expected_points") or []) if isinstance(p, str)]
    max_marks = float(question.get("max_marks") or 0)
    numbered = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(points))
    prompt = (
        "You are checking a UPPSC BEO Mains answer. Judge only what the student wrote. "
        "Do not reward keyword lists. Accept correct paraphrase in English or Hindi.\n"
        f"Question: {question.get('question_text', '')}\n"
        f"Maximum marks: {max_marks}\n"
        f"Model answer points:\n{numbered}\n\n"
        f"Student answer (text read from the sheet, may contain reading errors):\n<<<{answer_text}>>>\n\n"
        "Return JSON only: {\"points\": [{\"index\": int, \"covered\": \"yes\"|\"partial\"|\"no\", "
        "\"evidence\": string}], \"marks\": number between 0 and maximum, \"errors\": [string]}"
    )
    body = {
        "model": os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
        "temperature": 0.0,
        "reasoning_effort": "low",          # keeps tokens per minute within the account limit
        "max_completion_tokens": 1500,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": "Return valid JSON only."},
                     {"role": "user", "content": prompt}],
    }
    data = None
    for attempt in range(5):
        _pace()
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json=body,
                )
        except Exception as exc:  # the key is never included in the message
            print(f"[answer_check] LLM check skipped: {type(exc).__name__}", file=sys.stderr)
            return None
        if resp.status_code == 429 and attempt < 4:
            # rate limit: wait as the service asks (header, or "try again in Ns" in the message), then retry
            try:
                wait = float(resp.headers.get("retry-after", "5"))
            except ValueError:
                wait = 5.0
            m = re.search(r"try again in ([0-9.]+)\s*s", resp.text or "")
            if m:
                wait = max(wait, float(m.group(1)))
            time.sleep(min(max(wait, 1.0), 60.0))
            continue
        if resp.status_code != 200:
            detail = (resp.text or "")[:200].replace(key, "[key]")
            print(f"[answer_check] LLM check skipped: HTTP {resp.status_code} {detail}", file=sys.stderr)
            return None
        try:
            body = resp.json()
            _note_tokens(body)
            data = json.loads(body["choices"][0]["message"]["content"])
            break
        except Exception as exc:
            print(f"[answer_check] LLM reply unreadable: {type(exc).__name__}", file=sys.stderr)
            if attempt == 2:
                return None
    if not isinstance(data, dict):
        print("[answer_check] LLM reply has the wrong shape", file=sys.stderr)
        return None
    marks = data.get("marks")
    try:
        marks = max(0.0, min(max_marks, round_half(float(marks))))
    except (TypeError, ValueError):
        return None
    covered = {}
    points = data.get("points", []) or []
    for item in points if isinstance(points, list) else []:
        if not isinstance(item, dict):
            continue  # the model sometimes returns a bare string; ignore it rather than fail
        try:
            covered[int(item.get("index")) - 1] = str(item.get("covered", "no")).lower()
        except (TypeError, ValueError):
            continue
    errs = data.get("errors", []) or []
    if not isinstance(errs, list):
        errs = [errs]
    return {"marks": marks, "covered": covered, "errors": [str(e) for e in errs][:5]}


def check_answer(question: Dict[str, Any], answer_text: str, use_llm: bool = True) -> Dict[str, Any]:
    """Full check for one answer. Returns marks, missing points and review reasons."""
    kw = keyword_check(question, answer_text)
    result = {
        "marks": kw["marks"], "max_marks": kw["max_marks"], "method": "keyword",
        "points": kw["points"], "word_count": kw["word_count"], "notes": list(kw["notes"]),
        "needs_review": False, "llm_marks": None, "llm_errors": [], "review_codes": [],
    }
    word_limit = question.get("word_limit")
    if word_limit and kw["word_count"] > int(word_limit) * 1.1:
        result["notes"].append(
            f"Answer has {kw['word_count']} words; the limit is {word_limit}. Marks are not reduced automatically."
        )
        result["review_codes"].append("word_limit")
        result["needs_review"] = True

    try:
        llm = _groq_check(question, answer_text) if use_llm and answer_text.strip() else None
    except Exception as exc:  # any unexpected reply shape must not fail the whole sheet
        print(f"[answer_check] LLM check failed: {type(exc).__name__}", file=sys.stderr)
        llm = None
    if llm is not None:
        result["method"] = "keyword+llm"
        result["llm_marks"] = llm["marks"]
        result["llm_errors"] = llm["errors"]
        disagree_marks = abs(llm["marks"] - kw["marks"]) > 0.25 * kw["max_marks"] if kw["max_marks"] else False
        llm_cov = llm["covered"]
        disagree_points = 0
        for i, row in enumerate(result["points"]):
            llm_says = llm_cov.get(i)
            if llm_says is None:
                continue
            kw_says = "yes" if row["covered"] else ("partial" if row.get("partial") else "no")
            if llm_says != kw_says and {llm_says, kw_says} != {"yes", "partial"}:
                disagree_points += 1
        if disagree_marks or disagree_points > max(1, len(result["points"]) // 4):
            result["needs_review"] = True
            result["review_codes"].append("disagree")
            result["notes"].append("The two checks disagree. A person should confirm this answer.")
        # The LLM marks are used when they agree with the keyword check; otherwise the lower value is kept,
        # so an unverified high score is never published.
        result["marks"] = llm["marks"] if not disagree_marks else min(llm["marks"], kw["marks"])
    elif use_llm and os.environ.get("GROQ_API_KEY", "").strip() and answer_text.strip():
        # a key is configured but the second check did not complete: say so, do not present it as verified
        result["review_codes"].append("single_check")
        result["notes"].append("Second check did not complete; result is from one method only.")
    elif use_llm:
        result["notes"].append("Checked by keyword matching only.")  # API note; not shown in the UI

    if not answer_text.strip():
        result["needs_review"] = False
    return result
