"""API tests for the two grading modes (single question, whole copy) and examiner decision rules.

Run: cd /home/user && python3 -m pytest tests/api -q
"""
import sys
import warnings

import pytest

ROOT = "/home/user"
sys.path.insert(0, ROOT)
sys.path.insert(0, f"{ROOT}/apps/api")
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402

SESSION = "sess-gs17-cand8841"


@pytest.fixture()
def client():
    return TestClient(main.app)


def answers_of(client, session=SESSION):
    return client.get(f"/v1/sessions/{session}/answers").json()["answers"]


def fresh_answer(client, session=SESSION, skip_graded=False):
    """Return an answer id with a confirmed transcript; tests mutate state so they pick one fresh."""
    for a in answers_of(client, session):
        if a["revisions"] and a["revisions"][-1]["is_confirmed_for_grading"]:
            return a["answer_id"]
    raise AssertionError("no confirmed answer in seed data")


# ---------- single-question mode ----------

def test_single_grade_returns_contract_and_audit(client):
    aid = fresh_answer(client)
    r = client.post(f"/v1/answers/{aid}/grade")
    assert r.status_code == 200, r.text
    body = r.json()
    c = body["grade_run"]["contract"]
    for key in ("final_score", "max_marks", "needs_human_review", "word_limit_status", "criterion_scores"):
        assert key in c
    assert 0 <= c["final_score"] <= c["max_marks"]
    assert body["audit_event"]["event_type"] == "RUBRIC_GRADE_RUN_COMPLETED"


def test_single_grade_unknown_answer_404(client):
    assert client.post("/v1/answers/does-not-exist/grade").status_code == 404


def test_single_grade_blocks_unconfirmed_transcript(client):
    aid = fresh_answer(client)
    # Save an unconfirmed draft revision: marks must not be calculated from it.
    r = client.patch(f"/v1/answers/{aid}/transcript", json={
        "transcript_text": "draft text for the answer", "confirm_for_grading": False, "mark_all_spans_resolved": False,
    })
    assert r.status_code == 200
    r = client.post(f"/v1/answers/{aid}/grade")
    assert r.status_code == 409
    assert "Confirm the transcript" in r.json()["detail"]


# ---------- whole-copy mode ----------

def test_whole_copy_grades_every_confirmed_answer(client):
    res = client.post(f"/v1/sessions/{'sess-hi16-cand9204'}/grade-all")
    assert res.status_code == 200, res.text
    body = res.json()
    session_answers = answers_of(client, "sess-hi16-cand9204")
    assert body["graded_count"] + len(body["skipped"]) == len(session_answers)
    assert body["graded_count"] == len(body["answers"])
    assert body["total_suggested"] <= body["total_max"] + 1e-9
    assert round(sum(a["final_score"] for a in body["answers"]), 2) == body["total_suggested"]
    assert body["audit_event"]["event_type"] == "RUBRIC_COPY_GRADE_RUN_COMPLETED"


def test_whole_copy_skips_reviewed_unless_requested(client):
    session = "sess-gs17-cand8841"
    aid = fresh_answer(client, session)
    gr = client.post(f"/v1/answers/{aid}/grade").json()["grade_run"]
    score = gr["contract"]["final_score"]
    rv = client.post(f"/v1/grade-runs/{gr['grade_run_id']}/review", json={
        "action": "approved", "reviewed_final_score": score, "override_reason": "",
    })
    assert rv.status_code == 200, rv.text

    body = client.post(f"/v1/sessions/{session}/grade-all", json={}).json()
    skipped_ids = {s["answer_id"]: s["reason"] for s in body["skipped"]}
    assert skipped_ids.get(aid) == "already_reviewed"
    assert aid not in {a["answer_id"] for a in body["answers"]}

    body2 = client.post(f"/v1/sessions/{session}/grade-all", json={"include_reviewed": True}).json()
    assert aid in {a["answer_id"] for a in body2["answers"]}


def test_whole_copy_skips_unconfirmed_transcripts(client):
    session = "sess-hi16-cand9204"
    aid = fresh_answer(client, session)
    client.patch(f"/v1/answers/{aid}/transcript", json={
        "transcript_text": "unconfirmed text", "confirm_for_grading": False, "mark_all_spans_resolved": False,
    })
    body = client.post(f"/v1/sessions/{session}/grade-all", json={}).json()
    reasons = {s["answer_id"]: s["reason"] for s in body["skipped"]}
    assert reasons.get(aid) == "transcript_not_confirmed"


def test_whole_copy_unknown_session_404(client):
    assert client.post("/v1/sessions/nope/grade-all").status_code == 404


# ---------- examiner decision rules ----------

def _graded(client):
    aid = fresh_answer(client)
    gr = client.post(f"/v1/answers/{aid}/grade").json()["grade_run"]
    return gr


def test_accept_without_reason_is_allowed(client):
    gr = _graded(client)
    r = client.post(f"/v1/grade-runs/{gr['grade_run_id']}/review", json={
        "action": "approved", "reviewed_final_score": gr["contract"]["final_score"], "override_reason": "",
    })
    assert r.status_code == 200, r.text


def test_accept_with_different_mark_is_rejected(client):
    gr = _graded(client)
    other = gr["contract"]["final_score"] + 0.5 if gr["contract"]["final_score"] < gr["contract"]["max_marks"] else 0
    r = client.post(f"/v1/grade-runs/{gr['grade_run_id']}/review", json={
        "action": "approved", "reviewed_final_score": other, "override_reason": "",
    })
    assert r.status_code == 400


def test_change_mark_requires_reason(client):
    gr = _graded(client)
    r = client.post(f"/v1/grade-runs/{gr['grade_run_id']}/review", json={
        "action": "overridden", "reviewed_final_score": 1.0, "override_reason": "  ",
    })
    assert r.status_code == 400
    r = client.post(f"/v1/grade-runs/{gr['grade_run_id']}/review", json={
        "action": "overridden", "reviewed_final_score": 1.0, "override_reason": "Point on Article 21A is correct",
    })
    assert r.status_code == 200, r.text
    last = r.json()["grade_run"]["human_reviews"][-1]
    assert last["ai_suggested_score"] == gr["contract"]["final_score"]  # AI suggestion preserved
    assert last["reviewed_final_score"] == 1.0


def test_unknown_decision_type_rejected(client):
    gr = _graded(client)
    r = client.post(f"/v1/grade-runs/{gr['grade_run_id']}/review", json={
        "action": "auto_approve", "reviewed_final_score": 0, "override_reason": "",
    })
    assert r.status_code == 400


def test_return_for_correction_needs_no_reason(client):
    gr = _graded(client)
    r = client.post(f"/v1/grade-runs/{gr['grade_run_id']}/review", json={
        "action": "returned_for_transcript_correction", "reviewed_final_score": gr["contract"]["final_score"],
        "override_reason": "",
    })
    assert r.status_code == 200, r.text
