# UPPSC BEO answer-check: change log and model record

Date of this record: 2026-10-23. Working tree only. Nothing has been committed, pushed, or deployed.

## 1. Requests and status

| Request | Status |
|---|---|
| Question-first website: choose paper, choose question, upload sheet, Start, see marks, what is missing, what is good | Done, tested in a browser (local preview) |
| English / हिन्दी switch, saved under `localStorage` key `uppsc-ui-language`, `<html lang>` follows it | Done, tested after reload |
| Public pages show no AI or internal wording | Done |
| Model answer generated through an API and cached | Done (`services/answer-check/data/model_answers.json`) |
| Read text from every page, including Hindi and maths | Partly done. Vision reader (Qwen) is primary and CRNN is fallback. Graphs, figures and handwritten maths are described in text only, not tested |
| Single-question and whole-copy grading modes | Done earlier; `/check` (whole copy) and `/grade` (one question) |
| Own rate-limit bucket for vision | Done: `VISION_TPM_BUDGET` (default 7000), separate from the text model |
| Page transcript cache | Done: in-memory, up to 300 pages keyed by image hash |
| Smaller, consistent page images | Done: 900 px wide, JPEG quality 80 (Hindi legible; token cost does not change) |
| Web proxy always requests the LLM cross-check | Done (`apps/web/src/app/api/grade/route.ts`) |
| Empty Hindi/English point list falls back to the other language | Done |
| Review notes (disagree, header unclear, single check, word limit, fallback reader) shown in both languages | Done |
| Use the Kaggle token and private dataset for GPU training | Done earlier (v3), key not written to any file |
| Keep the trained model (v3) active; do not promote v4 or v4b | Done, per your decision |
| Hosted (public) link and live deploy | **Not done.** Deploys are yours to approve. Vercel token is gated |
| Recreate local commit `bcb189a` | **Not done.** Waiting for your approval |
| Generic rubric points: exclude, show separately, or keep | **Open.** Currently kept (they count toward marks) |
| Rotate the Groq and Kaggle keys pasted in chat | **Your action** |

## 2. Trained model

### Handwriting reader (HTR), CRNN v3, the active model
- Files: `packages/model-adapters/models/htr_crnn_v3.pt` (10,763,519 bytes; same size as `ml/htr/results/crnn_best.pt`), sha256 prefix `84124923ca224ac8`.
- Also in `ml/htr/results/`: `crnn_int8_state.pt` (int8 copy, 3.1 MB), `eval_report.json`, `copies_meta.json`.
- Architecture: CRNN with LSTM 256 hidden units, 2.69M parameters. Trained on Kaggle GPU (private dataset `adityarai20033/uppsc-htr-training-src`, kernel `uppsc-htr-gpu-train` v3).
- Results on synthetic test copies (12 pages, 264 lines, 4,961 characters):
  - Test CER 0.0208, WER 0.088, line recall 0.996 (v2 CPU: CER 0.0294).
  - Validation CER 0.0204.
  - Review F1 0.571 (precision 0.652, recall 0.509). Int8 CER 0.0208, F1 0.583.
- Important: these are synthetic results. They are not field accuracy on real scanned answer sheets, which has not been measured.

### Rejected experiments (not promoted)
- Word-only fine-tune on IIIT-HW-Hindi (`results_word_only_v4/`): line CER collapsed to 0.856. Do not retry without line-level data.
- Mixed round 1 (`results_mixed_v4/`): synthetic-page CER doubled to 0.042.
- Mixed round 2 with `page_like` (`results_mixed_v4b/`): synthetic CER 0.033; the guard never passed.
- Your decision: keep v3 and stop fine-tuning.

### Vision reader (answer-check)
- Model: `qwen/qwen3.8-27b` via Groq. No training was done. The model is used as is.
- Measured: about 2,400 tokens per page against an 8,000 tokens-per-minute limit, so about 3 pages a minute. A fresh 13-page sheet takes about 5 minutes.
- Measured on one GS17 question: 310 s; 13 pages read by vision; no fallback. The same sheet's second question took 3 s from cache.
- Not measured: transcription accuracy against ground truth across both sample sheets.

### Answer-check grading
- Text model: `openai/gpt-oss-120b` via Groq. Model answers are generated and cached.
- Mark combination: keyword coverage plus LLM cross-check. On disagreement, flag for review and cap at the lower mark.
- Results are single runs. LLM marks can vary between runs.

## 3. Files changed in this session
- `apps/web/src/app/page.tsx`: three-step question-first flow, language switch, result view.
- `apps/web/src/lib/i18n.ts`: English and Hindi strings for the new flow.
- `apps/web/src/app/api/grade/route.ts`: proxy for `/questions` and `/grade`.
- `services/answer-check/vision_reader.py`: own pacer, page cache, 900 px images.
- `services/answer-check/app.py`, `services/answer-check/grading.py`: earlier changes (`/grade`, `/questions`, vision-first reader).
- `ml/answer_check_eval/ui/`: browser test script and screenshots.

## 4. Not included / warnings
- The working tree shows `scripts/git-sync.sh` as modified. It was not part of this session's changes. Review it before any push.
- Keys: the Groq key was passed in service start commands during this session. Rotate it, along with the Kaggle key.
- Services and the preview are running only while the sandbox is up. A reset stops them, and `node_modules`, `.next` and Python packages must be reinstalled.
