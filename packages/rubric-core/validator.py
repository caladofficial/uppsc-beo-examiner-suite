"""
Deterministic Rubric & Score Validator (packages/rubric-core).
Calculates word counts with Unicode NFC Devanagari preservation, validates criterion IDs,
enforces mark caps and score increments, checks approved reference snapshots, and
computes final marks deterministically in application code (never trusting raw LLM arithmetic).
"""

import math
import re
import unicodedata
from typing import Dict, Any, List, Tuple


# Matches sequences of word characters including Devanagari combining marks (\u0900-\u097F)
WORD_TOKEN_RE = re.compile(r"[\w\u0900-\u097F]+(?:[-'’][\w\u0900-\u097F]+)*", re.UNICODE)


def count_unicode_words(text: str) -> Dict[str, Any]:
    """
    Normalizes text to Unicode NFC so Devanagari base consonants + matras/virama stay unified,
    strips standalone punctuation (danda '।', double danda '॥', bullets), and counts lexical words.
    Also reports script distribution (Devanagari vs Latin).
    """
    if not text:
        return {"word_count": 0, "devanagari_words": 0, "latin_words": 0, "tokens": []}

    normalized = unicodedata.normalize("NFC", text)
    # Remove standalone dandas and numbering prefixes like (क), (i), 1.
    cleaned = normalized.replace("।", " ").replace("॥", " ")
    tokens = WORD_TOKEN_RE.findall(cleaned)
    # Filter out pure-digit list markers if standalone (e.g., "1", "2") unless part of content
    lexical_tokens = [t for t in tokens if not (len(t) <= 2 and t.isdigit())]

    dev_count = 0
    lat_count = 0
    for tok in lexical_tokens:
        if any("\u0900" <= ch <= "\u097F" for ch in tok):
            dev_count += 1
        elif any("a" <= ch.lower() <= "z" for ch in tok):
            lat_count += 1

    return {
        "word_count": len(lexical_tokens),
        "devanagari_words": dev_count,
        "latin_words": lat_count,
        "tokens": lexical_tokens,
        "counting_convention": "NFC Unicode Word Tokenizer (Devanagari akshara clusters preserved; dandas & list numbers excluded)"
    }


def evaluate_word_limit(
    word_count: int,
    word_limit: int | None,
    word_limit_type: str
) -> Tuple[str, List[str]]:
    """
    Returns (word_limit_status, review_notes).
    Distinguishes 'maximum' (GS Mock 17: 125/50/25) from 'approximate' (Hindi Mock 16: ~700 / ~82)
    and 'not_specified'.
    """
    notes = []
    if not word_limit or word_limit_type == "not_specified":
        return "not_specified", notes

    if word_limit_type == "approximate":
        # Allow +/- 20% band around approximate target before flagging review note
        low_band = int(round(word_limit * 0.75))
        high_band = int(round(word_limit * 1.25))
        if word_count < low_band or word_count > high_band:
            notes.append(
                f"Word count ({word_count}) deviates noticeably from approximate target (~{word_limit} words; band {low_band}–{high_band}). No automatic cutoff applied per paper policy."
            )
        return "approximate", notes

    # Hard maximum (e.g., GS Mock 17)
    if word_count > word_limit:
        excess = word_count - word_limit
        pct = round((excess / word_limit) * 100, 1)
        notes.append(
            f"Word limit exceeded: {word_count}/{word_limit} words (+{excess} words, +{pct}%). Flagged per rubric guardrails."
        )
        return "exceeded", notes

    return "within", notes


def snap_to_increment(score: float, increment: float = 0.5) -> float:
    if increment <= 0:
        return round(score, 2)
    steps = round(score / increment)
    return round(steps * increment, 2)


def validate_and_compute_grade(
    raw_grade_payload: Dict[str, Any],
    question_spec: Dict[str, Any],
    pinned_rubric_version: str,
    paper_status: str,
    transcript_confidence: float = 0.92,
    has_unresolved_ocr_disagreement: bool = False
) -> Dict[str, Any]:
    """
    Server-side deterministic validator for AI grading output:
    1. Verifies every criterion exists in the pinned rubric (rejects invented criteria).
    2. Enforces 0 <= score <= criterion.max_score and snaps to permitted score increments (0.5).
    3. Verifies key_evidence source_ids against approved ReferenceSnapshots for the question.
    4. Applies numeric penalties ONLY if configured and published by a teacher.
    5. Deterministically calculates final_score capped at [0, question.max_marks].
    6. Enforces human review flags when OCR uncertainty, draft rubric status, word-limit exceedance,
       or material factual errors occur.
    """
    validation_errors: List[str] = []
    review_reasons: List[str] = list(raw_grade_payload.get("review_reasons", []))

    rubric_block = question_spec.get("rubric") or {}
    expected_criteria = rubric_block.get("criteria") or question_spec.get("criteria") or []
    criterion_map = {c["criterion_id"]: c for c in expected_criteria}

    approved_sources = {
        s["source_id"]
        for s in (question_spec.get("answer_outline", {}).get("reference_sources") or [])
    }

    submitted_criteria = raw_grade_payload.get("criterion_scores") or []
    seen_ids = set()
    validated_criteria = []

    for item in submitted_criteria:
        cid = item.get("criterion_id")
        if cid not in criterion_map:
            validation_errors.append(f"Rejected invented criterion_id '{cid}' not in pinned rubric {pinned_rubric_version}.")
            continue
        if cid in seen_ids:
            validation_errors.append(f"Duplicate criterion_id '{cid}' in model output.")
            continue
        seen_ids.add(cid)

        spec_c = criterion_map[cid]
        max_s = float(spec_c["max_score"])
        inc = float(spec_c.get("increment", 0.5))
        raw_s = float(item.get("score", 0.0))

        if raw_s < 0:
            validation_errors.append(f"Criterion '{cid}' score {raw_s} below 0; clamped to 0.")
            raw_s = 0.0
        if raw_s > max_s:
            validation_errors.append(f"Criterion '{cid}' score {raw_s} exceeded max_score {max_s}; capped to {max_s}.")
            raw_s = max_s

        snapped_s = snap_to_increment(raw_s, inc)
        snapped_s = min(max_s, max(0.0, snapped_s))

        # Validate key_evidence against approved ReferenceSnapshot set
        valid_key_ev = []
        for kev in item.get("key_evidence", []):
            sid = kev.get("source_id", "")
            if approved_sources and sid not in approved_sources:
                validation_errors.append(f"Rejected unapproved reference source_id '{sid}' in criterion '{cid}'.")
            else:
                valid_key_ev.append(kev)

        validated_criteria.append({
            "criterion_id": cid,
            "name": spec_c.get("name", cid),
            "score": snapped_s,
            "max_score": max_s,
            "reason": item.get("reason", "Evaluated against rubric anchor."),
            "answer_evidence": item.get("answer_evidence", []),
            "key_evidence": valid_key_ev
        })

    # Ensure any missing rubric criteria are explicitly filled with 0.0 and flagged
    for cid, spec_c in criterion_map.items():
        if cid not in seen_ids:
            validation_errors.append(f"Model omitted required criterion '{cid}'; initialized to 0.0 and flagged for review.")
            validated_criteria.append({
                "criterion_id": cid,
                "name": spec_c.get("name", cid),
                "score": 0.0,
                "max_score": float(spec_c["max_score"]),
                "reason": "Criterion omitted by model; requires human examiner scoring.",
                "answer_evidence": [],
                "key_evidence": []
            })
            review_reasons.append(f"Missing criterion '{cid}' in model response")

    raw_sum = sum(c["score"] for c in validated_criteria)
    max_marks = float(question_spec.get("max_marks", 10.0))

    # Check teacher-configured numeric penalty rules
    penalty_applied = 0.0
    penalty_configured = bool(rubric_block.get("numeric_penalty_configured", False))
    configured_penalty_amount = float(rubric_block.get("configured_penalty_amount", 0.0))

    factual_errors = raw_grade_payload.get("factual_errors", [])
    has_material_error = any(fe.get("severity") == "material" for fe in factual_errors)

    if has_material_error:
        if penalty_configured and configured_penalty_amount > 0:
            penalty_applied = configured_penalty_amount
            review_reasons.append(
                f"Applied teacher-configured numeric deduction of -{penalty_applied} marks for material factual error."
            )
        else:
            review_reasons.append(
                "Material factual error detected; reflected within criterion scores (no flat numeric deduction applied as none is configured in published rubric)."
            )

    if paper_status != "published_v1":
        review_reasons.append(
            f"Paper rubric status is '{paper_status}' (Hindi Mock 16 draft). Teacher must publish an approved rubric version before marks can be finalized."
        )

    if transcript_confidence < 0.80 or has_unresolved_ocr_disagreement:
        review_reasons.append(
            f"OCR/HTR transcript has low-confidence spans ({round(transcript_confidence * 100)}%) or unresolved model disagreement on mark-sensitive tokens."
        )

    final_score = max(0.0, min(max_marks, round(raw_sum - penalty_applied, 2)))
    needs_human_review = bool(
        raw_grade_payload.get("needs_human_review", False)
        or len(review_reasons) > 0
        or len(validation_errors) > 0
        or paper_status != "published_v1"
    )

    # Deduplicate review reasons
    dedup_reasons = []
    for r in review_reasons:
        if r not in dedup_reasons:
            dedup_reasons.append(r)

    return {
        "criterion_scores": validated_criteria,
        "raw_criterion_sum": round(raw_sum, 2),
        "penalty_applied": penalty_applied,
        "final_score": final_score,
        "max_marks": max_marks,
        "needs_human_review": needs_human_review,
        "review_reasons": dedup_reasons,
        "validator_passed": len(validation_errors) == 0,
        "validator_warnings": validation_errors
    }
