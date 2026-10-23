# HTR pipeline: training, evaluation and fixes (synthetic data only)

Date: 2026-10-15. Hardware: CPU only (no GPU; Kaggle key not yet provided).

## 0. Latest: GPU model v3 is the final model

- **Kaggle GPU training** (private kernel `adityarai20033/uppsc-htr-gpu-train`, private dataset
  `uppsc-htr-training-src`; the dataset contains the exam-derived report JSON, as you approved). Wider CRNN
  (LSTM 256, 2.69M params), 40,000 synthetic lines, page-style augmentation, 11 epochs on a GPU (about 10 min
  of training). Best validation line CER 0.0204, against 0.0288 for the CPU v2 model on the same validation lines.
- **Page-level test (same 12 pages, same evaluation):**

| Metric | CPU v2 | GPU v3 (final) |
|---|---|---|
| Test CER | 0.0294 | **0.0208** |
| Test WER | 0.131 | **0.088** |
| Line recall | 0.996 | 0.996 |
| Review-flag F1 | 0.61 | 0.57 (precision 0.65 vs 0.75) |
| Size, fp32 / int8 | 3.5 / 1.3 MB | 10.8 / 3.1 MB |

  The review-flag result is worse. Validation chose τ = 0.95 and pad 14 for v3. The flag catches about half of
  wrong lines, so unflagged lines still need human checking.
- **Final files:** `ml/htr/results/` = v3. `ml/htr/results_cpu_v2/` = CPU v2. `ml/htr/results_v1/` = first model.
  The adapter uses `packages/model-adapters/models/htr_crnn_v3.pt` with pad 14 and τ 0.95. The upload route
  label is "Handwriting reader (local)".
- **Caveat:** the GPU run used the same synthetic generator. Its numbers say nothing about real handwriting.
- **Kaggle key:** used only through an environment variable. Nothing is saved to the workspace. Consider rotating
  it, since it was pasted in chat.

## 0a. Earlier status (CPU v2, original font history)

- **Environment reset.** The sandbox was re-provisioned between sessions. Installed Python packages
  (torch), `/tmp` (test pages), and the system Noto Devanagari font were removed.
  - torch reinstalled (CPU build 2.14.1). Dependencies restored for the API.
  - The Devanagari font is now bundled at `ml/htr/fonts/NotoSansDevanagari-VF.ttf`
    (Google Fonts build of Noto Sans Devanagari). `htr_data.py` uses it as fallback. Both
    Devanagari variants map to this one font, so the generator is slightly different from the original run.
  - Test and validation pages were regenerated. Evaluation was rerun on them.
- **Current numbers on the regenerated pages** (`results/eval_report.json`; the earlier numbers are kept in
  `results/eval_report_original_font.json`):
  - Test CER **0.0294** (fp32), **0.0296** (int8). WER 0.131 (fp32). Devanagari lines CER about 0.066, Latin about 0.018.
  - Review flag at τ = 0.94: F1 0.61, precision 0.75, recall 0.52.
  - The chosen configuration did not change on validation.
  - The earlier figures (CER 0.0351, Devanagari 0.090, F1 0.67) were on the original font. The benchmark shifted
    with the font, so compare only within the same page set.
- **Upload route now uses the local handwriting reader as the primary reader** (your choice). Details in section 5.
  The visual OCR reader is the fallback if the local reader fails or returns an empty transcript.
  The transcript stays provisional and needs human confirmation before grading.
  Tested with FastAPI TestClient: upload returns 200 with candidate "Handwriting reader (local)", 3 flagged lines
  on a test page. Forced failure falls back to the old reader with 200.
- **Real-handwriting data.** Downloading IIIT-HW-Dev (Devanagari word images, 1.7 GB) from the official CVIT page
  to `~/.cache/htr_raw/` (not in workspace snapshots). It was at about 74 MB when this was written, and
  will take roughly 70 more minutes at current speed. Fine-tuning and a real-handwriting word-level test
  come after extraction. The archive can be resumed with `curl -C -` if the transfer is interrupted.
- **Kaggle key:** not received yet. Please paste it in chat.

## 1. Important caveat

**No real handwritten data was used.** Every number here comes from synthetic pages:
printed-style Devanagari and English text rendered with fonts, then given handwriting-like
distortion (shear, elastic warp, stroke thickness, blur, noise), and page-level skew, lighting,
and JPEG compression. These results show that the pipeline works on this synthetic domain.
They are **not** field accuracy on real scanned handwritten answer sheets. Real accuracy is
unknown until real transcribed pages are available (see section 6).

Split discipline: the validation copies use validation questions and the test copies use
test questions, with no overlap. Model selection and the review threshold were chosen on
validation only. The test copies were scored once with the chosen configuration.

## 2. Final results (synthetic test copies, 12 pages, 264 GT lines, 4,961 GT characters)

| Metric | fp32 (chosen) | int8 dynamic quantised |
|---|---|---|
| Character error rate (CER) | **0.0351** | 0.0351 |
| Word error rate (WER) | 0.1524 | 0.1524 |
| Line recall (GT lines matched to a segment) | 0.996 | 0.996 |
| Spurious segments | 0 | 0 |
| Review-flag F1 (wrong lines vs flagged lines) | 0.671 | 0.657 |
| Review-flag precision / recall | 0.92 / 0.53 | 0.90 / 0.52 |
| Seconds per page (CPU, measured in eval) | 0.146 | 0.152 |
| Model size | 3.53 MB | 1.26 MB |

Per-copy CER ranges from 0.012 to 0.085 across the 12 test copies.

By script (test copies, from the packaged module, which reproduced the 0.0351 total):
- Latin lines: CER 0.018 (3,776 characters)
- Devanagari lines: CER 0.090 (1,185 characters)

Devanagari is the weak spot. It has more conjunct and matra variation, and more visually
similar characters.

**Review flag:** the flag catches about half of the wrong lines (recall 0.53) at 92% precision.
That is not a complete safety net. Wrong lines often get confidence in the 0.8–0.97 range, so
a confidence threshold alone cannot separate them cleanly. Treat unflagged lines as unverified.

**Quantisation:** int8 gives the same CER and about 2.8x smaller size. It is not faster on this
CPU for a model this small (0.152 vs 0.146 s/page), so there is no speed benefit here.

## 3. What changed (in order of effect)

Validation page CER (6 copies) moved through these steps:

1. **Initial pipeline, default settings: CER 0.448, WER 1.07.** The line recogniser alone was
   at 0.026 on clean lines, so the drop came from the pipeline, not the model.
2. **Vertical margin rule removed (rule removal was horizontal-only before):** with pad 4 the
   CER was 0.41 with horizontal-only rule removal. Removing the vertical margin rule as well
   and using pad 8 gave CER 0.126 without deskew and 0.099 with deskew. The 170-grey margin
   rule was included in every line crop, which made each crop about 1,100 px wide and squeezed
   the text horizontally.
3. **Padding around each detected band raised from 4 px to 12–16 px:** CER 0.10 → 0.034.
   Hindi matras and descenders were being clipped. Padding above about 16 px pulled in
   neighbouring lines and made results worse again.
4. **Model v2 trained with page-style augmentation** (small rotation, lighting gradient,
   noise, JPEG at quality 50–90, random white margins, applied at native resolution). Page CER
   at the chosen padding: v1 0.0359 → v2 0.0343. This is a small gain, within noise on 132
   lines, but v2 is the better match to the page domain, so it was kept.

Bugs fixed along the way:
- **Ground-truth boxes ignored the page rotation** in `htr_data.make_copy`. Boxes are now
  transformed with the same rotation (bounding box of the four corners). This affected oracle
  checks; it did not change matched-line metrics, since IoU matching is tolerant.
- **Skew estimator** searched only in 0.25° steps. It now adds a 0.05° fine pass. Mean absolute
  error on the 12 test and 6 validation pages is 0.05° (max 0.19°), against the recorded
  ground truth.
- **Threshold sweep was capped at 0.90**, but the best threshold was above that. The sweep now
  runs 0.30–0.995 in 0.005 steps. It recognises each page once and scores every threshold from
  cached results, so it runs in about 3 seconds instead of minutes.
- **Default `Config` values did not match the validation-chosen config.** They now match.

## 4. Chosen configuration (selected on validation)

- Deskew: on (projection-profile, with fine pass)
- Binarisation: none (Otsu and CLAHE did not help)
- Rule removal: on, both horizontal and vertical (strokes darker than 150 are kept)
- Ink threshold: Otsu
- Band padding: 16 px
- Row-profile threshold: 0.02
- Review threshold τ: 0.94 (validation F1 peak is flat between about 0.94 and 0.97)

## 5. Files

- `ml/htr/results/` (final): `crnn_best.pt` (v2 checkpoint), `crnn_int8_state.pt`,
  `eval_report.json`, `train_log.json` (v2, reconstructed from the run output after an
  accidental overwrite; values are identical to the run), `copies_meta.json`.
- `ml/htr/results_v1/`: first model (clean-line training). Its `eval_report.json` was produced
  by the older pipeline and is superseded. Kept for comparison only.
- `ml/htr/pipeline.py`, `crnn.py`, `htr_data.py`, `train_crnn.py`, `gen_copies.py`,
  `evaluate.py`: development sources.
- `packages/model-adapters/htr_pipeline.py` and `htr_crnn.py`: packaged inference copy. Its
  defaults equal the validation-chosen configuration. Before the reset it reproduced the original test
  CER (0.0351) exactly. `transcribe_page()` is the entry point. Checkpoint: `models/htr_crnn_v2.pt`.
- `apps/api/main.py` upload route: calls `htr_pipeline.transcribe_page` first (primary), with fallback
  to the visual OCR reader. Startup does not fail if the reader cannot load.

Training data: 14,000 train-split lines (re-chunked, strength 0.6–1.4). Validation: 311 lines.
Model: CRNN-CTC, 876,860 parameters, 139-character set, 10 epochs, about 23 minutes on CPU.

Validation line-level CER for the final model is 0.0288 on the page-style validation lines.
v1 reached 0.0256 on clean validation lines. These two figures use different validation sets
and are not directly comparable. The page-level comparison above is the fair one.

## 6. What is needed for real accuracy

1. **Real scanned handwritten pages with transcriptions**, ideally from the UPPSC answer-script
   domain. This is the only way to measure real field accuracy and to fine-tune on real strokes.
2. **Permission to download IIIT-INDIC-HW-WORDS-Hindi** (Gongidi & Jawahar, ICDAR 2021;
   95,431 handwritten Devanagari word images). It is word-level, not line-level, so it would
   need a word-to-line adaptation step. Its license and terms need checking before use.
3. **A Kaggle key** (the current `/home/user/uploads/kaggle.json` has only a username). It
   would allow GPU training with larger capacity and more epochs. Expected benefit is unknown
   until tested.

## 7. Open items not covered by this work

- The web UI and port 3000 are not running, so the 86-check UI e2e cannot be rerun now.
- Port 8001 (`static-preview-54f01022`) is not running.
- Not done: rubric-core CI verify, `npm audit`, Next 16 decision, GitHub push decision,
  `copyRun` reset check in `switchSession()`.
- `scripts/git-sync.sh` shows as modified in the repo. It was not changed by this work.
  Nothing has been pushed or deployed.
