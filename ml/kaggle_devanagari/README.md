# Devanagari handwritten character model (Kaggle)

Purpose: a trained, measured building block for handwritten Devanagari reading (HTR).
It classifies one isolated handwritten character image. It is **not** a full-line or
full-page HTR system and is not wired into the grading path.

- Data: `ashokpant/devanagari-character-dataset` (NHCD handwritten vowels, consonants, numerals),
  read from `/kaggle/input`. Label = category/class folder.
- Split: stratified 80 / 10 / 10 (seeded). Model selection uses validation only; the test split is scored once.
- Model: 3-block CNN (about 1.6 M parameters), 32×32 grayscale input, AdamW + OneCycle, 25 epochs.
- Run: pushed as a private Kaggle kernel `jirandom/uppsc-devanagari-char-cnn` with GPU enabled and internet off.
- Outputs (`/kaggle/working`): `devanagari_char_cnn.pt`, `metrics.json`, `training_log.json`, `labels.json`.

Re-run: `kaggle kernels push -p /home/user/ml/kaggle_devanagari` (requires `KAGGLE_API_TOKEN`, never committed).
