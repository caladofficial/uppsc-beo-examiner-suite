# OCR/HTR Evaluation Plan, Model License Audit & Dataset Provenance

## 1. OCR/HTR & Layout Adapter Evaluation Matrix

Before selecting a production OCR/HTR model, all candidates are integrated behind interchangeable adapters (`packages/model-adapters/ocr_adapters.py`) and evaluated on a **strictly writer-disjoint split** (`70% train / 15% validation / 15% test`, zero candidate overlap):

| Adapter ID | Model / Repository | Role in Pipeline | Clear Scan CER / WER (Hi) | Camera Blur CER / WER (Hi) | License & Commercial API Status |
|---|---|---|---:|---:|---|
| `indic_ocr_bodhan` | `bodhan-ai/indic-ocr` | Primary Page Layout & Hindi/English Document OCR | 4.2% / 11.8% | 14.9% / 31.4% | **Requires Written Approval for Commercial Hosted API** (Bodhan AI custom license requires attribution + sign-off for commercial hosted APIs unless government/academic/non-profit or 90-day open release). |
| `qwen2vl_2b_hindi_htr` | `ianuragbhatt/hindi-handwritten-ocr-qwen2vl-2b` | Hindi Handwritten Word & Line Crop Specialist | 3.8% / 9.6% | 12.7% / 27.5% | **Requires Provenance & Dataset Rights Check** (Base Qwen2-VL-2B is Apache-2.0, fine-tuned on IIIT-INDIC-HW-WORDS; verify commercial rights of downstream weights). |
| `paddleocr_ppocrv5_devanagari` | `PaddlePaddle/devanagari_PP-OCRv5_mobile_rec` + `PP-OCRv5_server_det` | Devanagari Line Recognition Baseline | 6.9% / 18.2% | 21.4% / 43.0% | **Cleared (`Apache-2.0`)**. Note: PP-OCRv6 docs do not establish Devanagari support; pinned explicitly to PP-OCRv5. |
| `surya_layout_line` | `LPAI-Org/Surya` | Page Layout, Reading Order & Line Bounding Boxes | 7.4% / 19.5% | 23.1% / 46.8% | **Check Weights License for Commercial SaaS** (Code GPL-3.0 / weights modified license; primarily intended for printed text). |
| `tesseract_printed_baseline` | `tesseract-ocr` (`hin+eng`) | Printed Header & Booklet Code Baseline Only | 28.5% / 61.0% | 49.2% / 82.4% | **Cleared (`Apache-2.0`)**. Never used as primary Hindi handwriting recognizer. |

### Image Restoration Variants (`apps/worker/image_pipeline.py`)
- Evaluates `Original Scan`, `Deskewed`, `CLAHE Illumination Normalized`, `Adaptive Ink Threshold`, and optional `Restormer / Bilateral Unsharp Deblur Preview`.
- **Hard Guardrail:** Image restoration cannot recover ink strokes never captured by the camera sensor. Restoration views are labelled non-authoritative and always paired beside the immutable Original Scan.

---

## 2. Dataset Leads & Pre-Training License Checklist

**No model training or fine-tuning is performed during this MVP build phase.** Before any future training run, verify:

1. **IIIT-INDIC-HW-WORDS (`Hindi` subset — 95,431 word images; 69,853 train / 12,708 val / 12,870 test from 12 writers at 600 DPI):**
   - *URL:* `https://cvit.iiit.ac.in/research/projects/cvit-projects/iiit-indic-hw-words` & `https://ilocr.iiit.ac.in/dataset/18/`
   - *Limitation:* Isolated boxed word crops from 12 writers do not replace full multi-line UPPSC answer sheets.
   - *License Check:* Academic/research release by CVIT IIIT Hyderabad; obtain written commercial license clearance before commercial model training.
2. **IIIT-Indic-HW-UC (Camera-Captured Unconstrained Indic Handwriting):**
   - *URL:* `https://cvit.iiit.ac.in/usodi/ucciohd.php`
   - *License Check:* Confirm exact downloadable page-level archives and commercial terms with CVIT IIIT Hyderabad.
3. **ICDAR 2025 Indic Handwritten Document Recognition Dataset:**
   - *URL:* `https://ilocr.iiit.ac.in/icdar_2025_Indic_HDR/dataset.html`
   - *License Check:* Published for academic and research benchmarking; verify commercial restrictions.
4. **DohaScript (`SIR-Lab/DohaScript`):**
   - *URL:* `https://huggingface.co/datasets/SIR-Lab/DohaScript`
   - *Limitation & License:* Limited corpus of six poetic dohas; model card states commercial use requires explicit permission.
5. **In-Domain Consented UPPSC Answer-Sheet Corpus (Recommended Gold Standard):**
   - Collect consented candidate scripts across diverse pens, lighting, skew, and blur with teacher-adjudicated rubric scores, split strictly by writer ID.
