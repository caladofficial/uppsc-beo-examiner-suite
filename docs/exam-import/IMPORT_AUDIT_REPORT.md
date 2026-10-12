# UPPSC BEO Mains — Exam & Rubric Import Audit Report

## 1. Source Artifacts Inspected

| File Name | Artifact Kind | Size | Rows / Pages | Mocks Covered |
|---|---|---:|---:|---|
| `ToppersCode_Merged_AI_Mains_Rubrics_All_Mocks.xlsx` | GS Master Rubric Workbook | 46,881 B | 200 rows (5 sheets) | Mock 01, Mock 02, Mock 03, Mock 10, Mock 17 (40 Qs each = 200 Marks) |
| `ToppersCode_UPPSC_BEO_Hindi_Mocks_04_05_06_07_13_15_17_AI_Rubrics.xlsx` | Hindi & Essay Master Workbook | 28,753 B | 91 rows (5 sheets) | Mocks 04, 05, 06, 07, 13, 15, 17 (13 Items each = 200 Marks) |
| `UPPSC BEO MAINS Mock 17.pdf` | GS Mock 17 Canonical Paper | 135,848 B | 4 pages | General Studies Mock 17 (40 compulsory bilingual questions, 200 Marks) |
| `UPPSC BEO MAINS हिंदी मॉक 16.pdf` | Hindi Mock 16 Canonical Paper | 146,273 B | 4 pages | General Hindi & Essay Mock 16 (7 main questions / 13 evaluation items, 200 Marks) |

Machine-readable full output: `docs/exam-import/import-preview-report.json`.

---

## 2. Exact Question Counts, Section Totals & Rubric Mappings

### 2.1 General Studies Mock 17 (`uppsc-beo-mains-gs-mock-17-v1`)
- **Duration & Total Marks:** 3 Hours (180 mins), 200 Marks, 40 Compulsory Questions.
- **Section Breakdown & Rubric Dimensions:**
  - **Section A (Q1–Q10):** 10 questions × 10 marks = **100 marks** | Word limit: **Maximum 125 words** (`Content: 4`, `Analysis: 2`, `Relevance: 2`, `Structure: 1`, `Language/Accuracy: 1`).
  - **Section B (Q11–Q20):** 10 questions × 6 marks = **60 marks** | Word limit: **Maximum 50 words** (`Content: 3`, `Analysis: 1`, `Relevance: 1`, `Structure: 1`, `Language/Accuracy: 0`).
  - **Section C (Q21–Q40):** 20 questions × 2 marks = **40 marks** | Word limit: **Maximum 25 words** (`Content: 1.5`, `Relevance: 0.5`; `Analysis`, `Structure`, and `Language/Accuracy` carry `0` marks).

### 2.2 General Hindi & Essay Mock 16 (`uppsc-beo-mains-hindi-mock-16-draft`)
- **Duration & Total Marks:** 3 Hours (180 mins), 200 Marks, 7 Compulsory Main Questions mapped to **13 Scored Evaluation Items**:
  - **Q1(a) Vocabulary (`1(a)`):** 6 marks (3 words × 2 marks: `आधारशिला`, `स्थायित्व`, `असावधानी`).
  - **Q1(b) Comprehension (`1(b)`):** 5 marks (`संबंधों में विश्वास और संवाद का क्या महत्व है?`).
  - **Q1(c) Title (`1(c)`):** 4 marks (`गद्यांश के लिए एक उपयुक्त शीर्षक दीजिए`).
  - **Q1(d) Summary (`1(d)`):** 10 marks (`गद्यांश का सारांश लगभग एक-तिहाई शब्दों में लिखिए` — ~82 words).
  - **Q2 Official Memo (`2`):** 20 marks (`कार्यालय ज्ञापन` regarding protection of public property and school discipline).
  - **Q3 Grammar (`3` — Any One):** 10 marks (`3(क)` 8 sentence types by meaning with examples **OR** `3(ख)` separate suffix and root word for `मानवता, सामाजिक, लिखावट, मिठास, बचपन`). Score only the attempted option.
  - **Q4(a) Translation Hindi → English (`4(a)`):** 10 marks (5 sentences × 2 marks).
  - **Q4(b) Translation English → Hindi (`4(b)`):** 10 marks (5 sentences × 2 marks).
  - **Q5 Idioms/Proverbs (`5`):** 15 marks (5 items × 3 marks; draft template split: `1.5` meaning + `1.5` sentence usage).
  - **Q6(a) Spelling Correction (`6(a)`):** 5 marks (5 words × 1 mark: `कृतग्य → कृतज्ञ`, `स्वाधिन → स्वाधीन`, `उत्तरदाई → उत्तरदायी`, `सौन्दर्य → सौंदर्य`, `उज्जवल → उज्ज्वल`).
  - **Q6(b) Sentence Correction (`6(b)`):** 5 marks (5 sentences × 1 mark).
  - **Q7(a) Essay Subsection A (`7(a)` — Any One of 3):** 50 marks, ~700 words (`1. सामाजिक जीवन में संवाद और सहिष्णुता`, `2. भारतीय संस्कृति में पारस्परिक सहयोग की परंपरा`, `3. मानवीय मूल्यों के संरक्षण में साहित्य की भूमिका`).
  - **Q7(b) Essay Subsection B (`7(b)` — Any One of 3):** 50 marks, ~700 words (`1. बाढ़ : कारण, प्रभाव और प्रभावी प्रबंधन`, `2. कृषि में जैविक पद्धतियाँ : संभावनाएँ और सीमाएँ`, `3. ग्रामीण क्षेत्रों में स्वरोजगार की संभावनाएँ`).

---

## 3. Unresolved Import Warnings & Anomaly Resolutions (14 Total)

1. **`WARN-IDENTITY-COLLISION-MOCK17` (High):** Both workbooks contain a paper named `Mock 17`. WB1's `Mock 17` is General Studies (40 questions, matching `UPPSC BEO MAINS Mock 17.pdf`), while WB2's `Mock 17` is General Hindi & Essay (13 items). Papers are keyed by `(exam, subject, language, paper_version, sha256)` — never by mock number alone.
2. **`WARN-HINDI-MOCK16-MISSING-RUBRIC` (Critical):** The Hindi workbook covers Mocks `04, 05, 06, 07, 13, 15, 17` and omits `Mock 16`. A 13-item draft rubric has been synthesized from the workbook's `Rubric Framework` and VLM-verified questions from `UPPSC BEO MAINS हिंदी मॉक 16.pdf`, gated with `status = "draft_requires_teacher_approval"`.
3. **`WARN-GS-CONTAMINATED-HEADING-ROW-171` (High):** In WB1 Row 171 (`Mock 17-10`), `Question (English)` is contaminated with `SECTION B — 10 × 6 = 60 अं क लगभग 50 शब् / About 50 words`. Stripped and replaced with canonical PDF Q10 wording.
4. **`WARN-GS-CONTAMINATED-HEADING-ROW-181` (High):** In WB1 Row 181 (`Mock 17-20`), `Question (English)` is contaminated with `SECTION C — 20 × 2 = 40 अंक`. Stripped and replaced with canonical PDF Q20 wording.
5. **`WARN-GS-EMPTY-EN-ROW-81` (Medium):** In WB1 Row 81 (`Mock 02-40`), `Question (English)` is `None` while `Raw Extract` contains `नवद्यािर् प्रबंधि सनमनत School Management Committee www.topperscode.com`.
6. **`WARN-HINDI-WB-PROMPT-MISALIGNMENT` (High):** Across all 7 mocks in WB2 (`Merged Hindi Rubrics`), `Passage Context (Q1 only)` contains Instruction 1 (`सभी प्रश्न अनिवार्य हैं।`) and `Prompt / Task` for Items `2, 3, 4a, 4b, 6b, 7a, 7b` contains misaligned paper instructions or concatenated questions.
7. **`WARN-HINDI16-PDF-DEVANAGARI-CMAP` & `WARN-GS17-PDF-DEVANAGARI-CMAP` (High):** Direct PDF font-layer extraction corrupts Devanagari characters (e.g., `मिुष्य का जीवि अिेक सोंबोंर्नों से निनमयत हनता है` instead of `मनुष्य का जीवन अनेक संबंधों से निर्मित होता है`). All 8 pages across both PDFs were rendered at 200 DPI and verified via VLM visual inspection.
8. **`WARN-GS17-UNSPECIFIED-PENALTY-AMOUNT` (Medium):** The GS workbook says to deduct for material factual errors and flag word-limit exceedance, but defines no numeric deduction amount. Our deterministic score validator blocks flat numeric deductions unless explicitly configured by a teacher.
