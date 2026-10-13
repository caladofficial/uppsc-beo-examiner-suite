# UI browser test results

Test: `/home/user/tests/e2e/ui_e2e.py <base_url> <screenshot_dir>`
Browser: Chromium via Playwright, 1440 px desktop viewport.

## Latest run (two grading modes, server and static builds)

| Build | Base URL | Result |
|---|---|---|
| Next.js server build (`next start`, fresh state) | `http://localhost:3000` | 86 / 86 |
| Static GitHub Pages build (`GITHUB_PAGES=true`) | `http://localhost:8001/uppsc-beo-examiner-suite` | 86 / 86 |

API tests: `python3 -m pytest tests/api -q` → 12 passed (single-question and whole-copy grading, confirmation gate, skip reasons, examiner decision rules).

### Grading modes (Marks tab)

- **One question:** confirm transcript → calculate marks → criterion adjustments → examiner decision. Calculation is blocked with a clear message until the transcript is confirmed; a stale-marks notice appears when the transcript has changed since marks were calculated.
- **Whole copy:** one table for every answer on the candidate's copy (transcript status, suggested marks, decision status, Open). "Calculate marks for whole copy" grades every answer with a confirmed transcript. Answers already decided by an examiner are skipped unless "Also recalculate answers that already have a decision" is ticked; the run summary lists skipped answers and the reason.
- **Decisions:** "Accept" keeps the suggested mark and needs no reason. "Change marks" needs a reason of at least 5 characters. "Return for transcript correction" needs no reason.

### Fixes found by this test pass

- Accepting a suggested mark without a reason failed with "could not be saved" in both backends. Accept now needs no reason and keeps the suggested mark.
- Saving a transcript in the static build re-graded in place and overwrote the grade record. The live API did not. Both now only add an immutable transcript revision; marks are recalculated explicitly.
- Decision rules now match in the Next route, the static client and FastAPI (`validateExaminerDecision` / `_run_grade`).
- Grading now requires a confirmed transcript (HTTP 409 for single, `transcript_not_confirmed` skip for whole copy).

## Earlier run (English / Hindi interface)

| Build | Base URL | Result |
|---|---|---|
| Next.js server build | `http://127.0.0.1:3000` | 71 / 71 |
| Static GitHub Pages build | `http://127.0.0.1:3100/uppsc-beo-examiner-suite` | 73 / 73 |

The counts differ because the server keeps the Hindi paper approval from earlier runs, so the static run performs the full approval step.

### Dual-language interface

- Language switch in the header: English | हिन्दी. The choice is saved in the browser and restored after reload; `<html lang>` follows it.
- Every interface label, button, status, message and activity-log label is translated. Exam content (question text, rubric criteria, reader transcripts, import notes) stays in its source language.
- The test switches to Hindi, checks the navigation, Papers, Handwriting, Marks and Report labels, reloads, and switches back.

## Previous run (five-section examiner workspace)

| Build | Base URL | Result |
|---|---|---|
| Next.js server build | `http://127.0.0.1:3000` | 63 / 63 |
| Static GitHub Pages build | `http://127.0.0.1:3100/uppsc-beo-examiner-suite` | 63 / 63 |

### What the 63 checks cover

- **Shell:** exactly five sections (Papers, Answer sheets, Handwriting, Marks, Report); the sample-data note is present.
- **Papers:** two paper cards with approval status; GS Mock 17 shows 40 rows; the Section A filter shows 10 rows; search, empty state, and question detail (criteria, expected points) work; the 14 import notes expand; Hindi Mock 16 shows 13 items; the approval box, deduction toggle, and publish action work.
- **Answer sheets:** an invalid file is refused with a plain message; a valid PNG is accepted and checked; page buttons and the five page views work; enhanced views show the caution note; the answers table lists each answer.
- **Handwriting:** "Open" moves to this section; readings can be used; a draft revision adds a history entry; a confirmed revision shows "Confirmed"; zoom and rotate work.
- **Marks:** marks can be calculated and recalculated; a criterion mark can be adjusted; an override is blocked without a reason and saved with one; the decision history updates.
- **Report:** per-question rows and totals; export is locked until the examiner authorises the report; the JSON export downloads; the activity log lists events.
- **Global:** no uncaught page errors; no console errors; no unexpected HTTP errors; no AI or internal terms on any section.

## Earlier run (six-section workspace, before the redesign)

Server build 66 / 66, static build 66 / 66. Superseded by the run above.

## Known limits

- Accuracy figures for the readers are planning targets, not measured results.
- Uploaded pages show only the original scan; enhanced views are not generated for uploads yet.
- The Hindi Mock 16 approval is held in server memory for the running demo, so it resets when the server restarts.
