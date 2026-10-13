# Devanagari handwritten character model (Kaggle)

Purpose: a trained and measured building block for handwritten Devanagari reading (HTR).
It classifies one isolated handwritten character image. It is **not** a full-line or
full-page HTR system and is not wired into the grading path.

- Data: `ashokpant/devanagari-character-dataset` (NHCD handwritten vowels, consonants, numerals),
  read from `/kaggle/input`. Label = category/class folder (58 classes, 12,912 images).
- Split: stratified 80 / 10 / 10 (seeded). Model selection uses validation only; the test split is scored once.
- Model: 3-block CNN (1.45 M parameters), 32×32 grayscale input, AdamW + OneCycle, 12 epochs.
- Kaggle kernel: `jirandom/uppsc-devanagari-char-cnn` (private, internet off).

## Result (Kaggle version 3, CPU, 12 epochs, 1,002 s)

| Metric | Value |
|---|---|
| Test accuracy | **98.27%** |
| Test macro-F1 | 98.16% |
| Test weighted-F1 | 98.28% |
| Validation accuracy (best epoch) | 98.19% |
| Majority-class baseline | 2.28% |
| Test accuracy: consonants / vowels / numerals | 97.64% / 98.86% / 99.31% |

Files: `results/kaggle_v3/metrics.json`, `training_log.json`, `labels.json`, `devanagari_char_cnn.pt`, `kernel.log`.

## Kaggle run history

- Versions 1 and 2 (GPU enabled, 25 and then 12 epochs) stayed in `RUNNING` for more than an hour with no output, so they were abandoned.
- Version 3 (CPU, time-budgeted at 30 min) completed; its metrics above are the reported result.
- A local two-epoch smoke run (92.3% test accuracy) confirmed the script before the Kaggle run.

## Limits

- Isolated characters only. Full handwritten lines still need a line segmenter and a sequence model (CTC or VLM), which this does not provide.
- The NHCD dataset is clean, centred character scans. Real answer-sheet crops will be noisier, so accuracy on UPPSC scans must be measured separately before any use.

Re-run: `kaggle kernels push -p /home/user/ml/kaggle_devanagari` with `KAGGLE_API_TOKEN` set in the environment. The token is never written to the repository.
