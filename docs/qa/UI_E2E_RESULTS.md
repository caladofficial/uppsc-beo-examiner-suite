# UI End-to-End Test Results

Generated: 2026-10-12 (test driver: `tests/e2e/ui_e2e.py`, headless Chromium via Playwright)

| Target | Checks passed |
|---|---|
| Server build (Next.js on Vercel-style server, port 3000) | 66 / 66 |
| Static build (GitHub Pages base path, served locally) | 66 / 66 |

The suite walks all six workflow stages, clicks every filter, search box, page-view tab, reader choice,
transcript action, grading control, review form, export, and safety check, then scans the visible text
for AI-facing or internal terms and checks for uncaught errors and failed asset loads.

## Server build — checks

| | Check |
|---|---|
| ✅ | no AI/internal terms visible [header] |
| ✅ | sample-data notice shown |
| ✅ | nav button exists: Question Papers |
| ✅ | nav button exists: Upload Answer |
| ✅ | nav button exists: Read & Check |
| ✅ | nav button exists: Grade & Review |
| ✅ | nav button exists: Candidate Report |
| ✅ | nav button exists: Quality & Security |
| ✅ | GS paper: 40 question rows |
| ✅ | section filter Sec A lists rows |
| ✅ | section filter Sec B lists rows |
| ✅ | section filter Sec C lists rows |
| ✅ | All (40) restores 40 rows |
| ✅ | search 'Vedic' finds matches |
| ✅ | search with no match shows empty state |
| ✅ | question detail: marks breakdown heading |
| ✅ | question detail: answer outline heading |
| ✅ | question detail: reference sources heading |
| ✅ | GS Q11 detail shows outline points |
| ✅ | no AI/internal terms visible [stage1 GS detail] |
| ✅ | Hindi paper: 13 item rows |
| ✅ | Hindi item detail shows marks breakdown |
| ✅ | penalty toggle reveals deduction input |
| ✅ | publishing Hindi scheme shows Approved status |
| ✅ | no AI/internal terms visible [stage1 end] |
| ✅ | upload stage renders |
| ✅ | invalid file is rejected with a message |
| ✅ | valid PNG upload accepted |
| ✅ | file-check result shows MIME |
| ✅ | page view 'Straightened' renders an image |
| ✅ | page view 'Brightness balanced' renders an image |
| ✅ | page view 'High-contrast ink' renders an image |
| ✅ | page view 'Sharpened preview' renders an image |
| ✅ | page view 'Original scan' renders an image |
| ✅ | page views switch image source |
| ✅ | candidate pages listed (seeded + uploaded) |
| ✅ | no AI/internal terms visible [stage2] |
| ✅ | stage 3 renders transcript editor |
| ✅ | readings have 'Use this reading' buttons |
| ✅ | 'Use this reading' loads text into editor |
| ✅ | save draft adds a version to history |
| ✅ | confirm transcript adds a confirmed version |
| ✅ | 'Go to grading' navigates to grading stage |
| ✅ | no AI/internal terms visible [stage3] |
| ✅ | grading: criterion breakdown shown |
| ✅ | grading: question total shown |
| ✅ | grading: feedback sections shown |
| ✅ | recalculate marks completes |
| ✅ | review decision dropdown offers 3 choices |
| ✅ | saved review appears in review history |
| ✅ | no AI/internal terms visible [stage4] |
| ✅ | report shows candidate ID |
| ✅ | report shows human-readable paper status |
| ✅ | report has per-question rows |
| ✅ | export downloads JSON report |
| ✅ | no AI/internal terms visible [stage5] |
| ✅ | reader comparison table renders |
| ✅ | reader rows present |
| ✅ | planning-target disclaimer shown |
| ✅ | blocked metadata address is refused |
| ✅ | hidden instruction is flagged |
| ✅ | activity log lists events |
| ✅ | no AI/internal terms visible [stage6] |
| ✅ | no uncaught page errors |
| ✅ | no console errors |
| ✅ | every page asset / image loads (no non-API 4xx/5xx) |

## Static (GitHub Pages) build — checks

| | Check |
|---|---|
| ✅ | no AI/internal terms visible [header] |
| ✅ | sample-data notice shown |
| ✅ | nav button exists: Question Papers |
| ✅ | nav button exists: Upload Answer |
| ✅ | nav button exists: Read & Check |
| ✅ | nav button exists: Grade & Review |
| ✅ | nav button exists: Candidate Report |
| ✅ | nav button exists: Quality & Security |
| ✅ | GS paper: 40 question rows |
| ✅ | section filter Sec A lists rows |
| ✅ | section filter Sec B lists rows |
| ✅ | section filter Sec C lists rows |
| ✅ | All (40) restores 40 rows |
| ✅ | search 'Vedic' finds matches |
| ✅ | search with no match shows empty state |
| ✅ | question detail: marks breakdown heading |
| ✅ | question detail: answer outline heading |
| ✅ | question detail: reference sources heading |
| ✅ | GS Q11 detail shows outline points |
| ✅ | no AI/internal terms visible [stage1 GS detail] |
| ✅ | Hindi paper: 13 item rows |
| ✅ | Hindi item detail shows marks breakdown |
| ✅ | penalty toggle reveals deduction input |
| ✅ | publishing Hindi scheme shows Approved status |
| ✅ | no AI/internal terms visible [stage1 end] |
| ✅ | upload stage renders |
| ✅ | invalid file is rejected with a message |
| ✅ | valid PNG upload accepted |
| ✅ | file-check result shows MIME |
| ✅ | page view 'Straightened' renders an image |
| ✅ | page view 'Brightness balanced' renders an image |
| ✅ | page view 'High-contrast ink' renders an image |
| ✅ | page view 'Sharpened preview' renders an image |
| ✅ | page view 'Original scan' renders an image |
| ✅ | page views switch image source |
| ✅ | candidate pages listed (seeded + uploaded) |
| ✅ | no AI/internal terms visible [stage2] |
| ✅ | stage 3 renders transcript editor |
| ✅ | readings have 'Use this reading' buttons |
| ✅ | 'Use this reading' loads text into editor |
| ✅ | save draft adds a version to history |
| ✅ | confirm transcript adds a confirmed version |
| ✅ | 'Go to grading' navigates to grading stage |
| ✅ | no AI/internal terms visible [stage3] |
| ✅ | grading: criterion breakdown shown |
| ✅ | grading: question total shown |
| ✅ | grading: feedback sections shown |
| ✅ | recalculate marks completes |
| ✅ | review decision dropdown offers 3 choices |
| ✅ | saved review appears in review history |
| ✅ | no AI/internal terms visible [stage4] |
| ✅ | report shows candidate ID |
| ✅ | report shows human-readable paper status |
| ✅ | report has per-question rows |
| ✅ | export downloads JSON report |
| ✅ | no AI/internal terms visible [stage5] |
| ✅ | reader comparison table renders |
| ✅ | reader rows present |
| ✅ | planning-target disclaimer shown |
| ✅ | blocked metadata address is refused |
| ✅ | hidden instruction is flagged |
| ✅ | activity log lists events |
| ✅ | no AI/internal terms visible [stage6] |
| ✅ | no uncaught page errors |
| ✅ | no console errors |
| ✅ | every page asset / image loads (no non-API 4xx/5xx) |
