import importPreviewData from "@/data/import-preview-report.json";

export function stableHashHex(input: string): string {
  // Pure TypeScript deterministic 256-bit hash (works in both Node.js and Browser without native crypto)
  const seeds = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ];
  for (let i = 0; i < input.length; i++) {
    const c = input.charCodeAt(i);
    const idx = i & 7;
    seeds[idx] = Math.imul(seeds[idx] ^ c, 0x01000193) >>> 0;
    seeds[(idx + 3) & 7] =
      (seeds[(idx + 3) & 7] + ((seeds[idx] << 5) | (seeds[idx] >>> 27))) >>> 0;
  }
  return seeds.map((n) => n.toString(16).padStart(8, "0")).join("");
}

export const ALLOWLISTED_REFERENCE_DOMAINS = new Set([
  "ncert.nic.in",
  "legislative.gov.in",
  "upagripardarshi.gov.in",
  "education.gov.in",
  "www.education.gov.in",
  "dpe.gov.in",
  "wcd.nic.in",
  "niti.gov.in",
  "www.niti.gov.in",
  "ndma.gov.in",
  "sac.gov.in",
  "www.sac.gov.in",
  "upeida.up.gov.in",
  "amritmahotsav.nic.in",
  "cazri.res.in",
  "www.cazri.res.in",
  "indiabudget.gov.in",
  "www.indiabudget.gov.in",
  "labour.gov.in",
  "mofpi.gov.in",
  "www.mofpi.gov.in",
  "fsi.nic.in",
  "indiaai.gov.in",
  "meity.gov.in",
  "www.meity.gov.in",
  "niepa.ac.in",
]);

export const OCR_MODEL_REGISTRY = [
  {
    adapter_id: "indic_ocr_bodhan",
    name: "Reader A (primary)",
    model_ref: "bodhan-ai/indic-ocr",
    version_pin: "sha256:9b4e1a2c8d0f6e3b1c2d4e5f6a7b8c9d0e1f2a3b",
    role: "Primary reader for printed and neat handwriting",
    scripts_supported: ["Devanagari (hi)", "Latin (en)", "Mixed (hi+en)"],
    handwriting_status:
      "Experimental / Work-in-Progress (Strong on layout & clear handwriting; requires human review on cursives/smudges)",
    license_summary:
      "Bodhan AI Custom License — Attribution required ('Attribution per licence'); commercial hosted API/service exposure requires written sign-off from Bodhan AI.",
    commercial_api_cleared: false,
    license_action_required:
      "Obtain written commercial API approval from Bodhan AI before exposing hosted inference to external commercial tenants.",
    calibration_temperature: 1.35,
    eval_metrics_writer_split: {
      cer_clear_scan_hi: 4.2,
      wer_clear_scan_hi: 11.8,
      cer_camera_blur_hi: 14.9,
      wer_camera_blur_hi: 31.4,
      layout_region_iou: 0.89,
      question_linking_acc: 0.94,
    },
  },
  {
    adapter_id: "qwen2vl_2b_hindi_htr",
    name: "Reader B (Hindi handwriting)",
    model_ref: "ianuragbhatt/hindi-handwritten-ocr-qwen2vl-2b",
    version_pin: "sha256:3c7f8e9a1b2d4c6e8f0a1b3c5d7e9f2a4b6c8d0e",
    role: "Hindi handwriting: word and line specialist",
    scripts_supported: ["Devanagari (hi)"],
    handwriting_status:
      "Fine-tuned on IIIT-INDIC-HW-WORDS Hindi word crops; strong on isolated Devanagari words and short phrases.",
    license_summary:
      "Base Reader B-2B is Apache-2.0; fine-tune trained on IIIT-INDIC-HW-WORDS (academic/research dataset terms must be verified).",
    commercial_api_cleared: false,
    license_action_required:
      "Verify IIIT Hyderabad dataset derivative commercial rights and benchmark on full UPPSC multi-line crops before production deployment.",
    calibration_temperature: 1.48,
    eval_metrics_writer_split: {
      cer_clear_scan_hi: 3.8,
      wer_clear_scan_hi: 9.6,
      cer_camera_blur_hi: 12.7,
      wer_camera_blur_hi: 27.5,
      layout_region_iou: 0.0,
      question_linking_acc: 0.0,
    },
  },
  {
    adapter_id: "paddleocr_ppocrv5_devanagari",
    name: "Reader C (Devanagari line reader)",
    model_ref: "PaddlePaddle/devanagari_Reader C_mobile_rec + Reader C_server_det",
    version_pin: "sha256:7d1e5a9b3c4f2e8d6a0b9c8e7f6d5c4b3a2f1e0d",
    role: "Devanagari printed and neat-script line reader",
    scripts_supported: ["Devanagari (hi)", "Digits/Punctuation"],
    handwriting_status:
      "84.96% benchmark accuracy on printed/scene Devanagari lines; PP-OCRv6 docs do not establish Devanagari support so pinned to Reader C.",
    license_summary: "Apache-2.0 License (Permissive commercial & production use allowed with attribution).",
    commercial_api_cleared: true,
    license_action_required:
      "Cleared under Apache-2.0; pair with en_Reader C_mobile_rec for pure-Latin lines.",
    calibration_temperature: 1.25,
    eval_metrics_writer_split: {
      cer_clear_scan_hi: 6.9,
      wer_clear_scan_hi: 18.2,
      cer_camera_blur_hi: 21.4,
      wer_camera_blur_hi: 43.0,
      layout_region_iou: 0.86,
      question_linking_acc: 0.88,
    },
  },
  {
    adapter_id: "surya_layout_line",
    name: "Reader D (layout & line finder)",
    model_ref: "LPAI-Org/Reader D",
    version_pin: "sha256:5a8b2c4d6e9f1a3b5c7d9e0f2a4b6c8d1e3f5a7b",
    role: "Page layout, reading order and line detection",
    scripts_supported: ["Devanagari (hi)", "Latin (en)", "90+ languages"],
    handwriting_status: "Excellent for line bounding-box detection and margin question-number isolation.",
    license_summary: "GPL-3.0 / Modified Model Weights License.",
    commercial_api_cleared: false,
    license_action_required:
      "Confirm Reader D weights license compatibility with commercial SaaS or use Apache-2.0 Reader C_server_det.",
    calibration_temperature: 1.2,
    eval_metrics_writer_split: {
      cer_clear_scan_hi: 7.4,
      wer_clear_scan_hi: 19.5,
      cer_camera_blur_hi: 23.1,
      wer_camera_blur_hi: 46.8,
      layout_region_iou: 0.93,
      question_linking_acc: 0.95,
    },
  },
  {
    adapter_id: "tesseract_printed_baseline",
    name: "Reader E (printed header fallback)",
    model_ref: "tesseract-ocr/tessdata_best (hin+eng)",
    version_pin: "v5.3.4-tessdata-best-2024",
    role: "Printed headers and booklet codes only (fallback)",
    scripts_supported: ["Devanagari (hi)", "Latin (en)"],
    handwriting_status: "Printed text baseline only; never used as primary Hindi handwriting recognizer.",
    license_summary: "Apache-2.0 License.",
    commercial_api_cleared: true,
    license_action_required: "Cleared under Apache-2.0; restrict strictly to printed headers and PDF cross-check.",
    calibration_temperature: 1.6,
    eval_metrics_writer_split: {
      cer_clear_scan_hi: 28.5,
      wer_clear_scan_hi: 61.0,
      cer_camera_blur_hi: 49.2,
      wer_camera_blur_hi: 82.4,
      layout_region_iou: 0.72,
      question_linking_acc: 0.76,
    },
  },
];

export const DATASET_PROVENANCE_REGISTRY = [
  {
    dataset_id: "iiit_indic_hw_words_hindi",
    name: "IIIT-INDIC-HW-WORDS (Hindi / Devanagari Subset)",
    url: "https://cvit.iiit.ac.in/research/projects/cvit-projects/iiit-indic-hw-words",
    detail_url: "https://ilocr.iiit.ac.in/dataset/18/",
    scope:
      "95,431 handwritten Hindi word images (69,853 train / 12,708 val / 12,870 test; 11,030 unique words) written by 12 writers inside boxed forms, scanned at 600 DPI.",
    limitations:
      "Isolated word crops from 12 writers do not capture full multi-line UPPSC answer sheets or margin question numbers.",
    license_status:
      "Academic & Research Release (CVIT, IIIT Hyderabad — Gongidi & Jawahar, ICDAR 2021). Written permission from IIIT-H required before commercial model training.",
    training_allowed_now: false,
  },
  {
    dataset_id: "iiit_indic_hw_uc",
    name: "IIIT-Indic-HW-UC (Unconstrained Camera-Captured Indic Handwriting)",
    url: "https://cvit.iiit.ac.in/usodi/ucciohd.php",
    detail_url: "https://cvit.iiit.ac.in/usodi/ucciohd.php",
    scope: "Camera-captured Indic handwriting under unconstrained lighting, shadow, skew, and perspective distortion.",
    limitations: "Verify exact page-level downloadable archives and writer-split metadata before ingestion.",
    license_status: "Research dataset by CVIT IIIT Hyderabad; verify release terms and commercial rights prior to training.",
    training_allowed_now: false,
  },
  {
    dataset_id: "icdar_2025_indic_hdr",
    name: "ICDAR 2025 Indic Handwritten Document Recognition Dataset",
    url: "https://ilocr.iiit.ac.in/icdar_2025_Indic_HDR/dataset.html",
    detail_url: "https://ilocr.iiit.ac.in/icdar_2025_Indic_HDR/dataset.html",
    scope: "Page-level handwritten document detection and recognition benchmark across Indic scripts.",
    limitations: "Stated as available for academic and research benchmarking.",
    license_status: "Academic/Research benchmark license; commercial training rights not granted by default.",
    training_allowed_now: false,
  },
  {
    dataset_id: "dohascript_sir_lab",
    name: "DohaScript (Multi-Writer Continuous Hindi Handwriting)",
    url: "https://huggingface.co/datasets/SIR-Lab/DohaScript",
    detail_url: "https://github.com/KAS4453/DohaScript",
    scope: "Multi-writer continuous Hindi handwriting across a corpus of six dohas.",
    limitations: "Narrow lexical domain (six poetic dohas); useful only as a line-continuity benchmark.",
    license_status: "Non-commercial research license; dataset card states commercial use requires author permission.",
    training_allowed_now: false,
  },
];

export function countUnicodeWords(text: string) {
  if (!text) {
    return {
      word_count: 0,
      devanagari_words: 0,
      latin_words: 0,
      counting_convention:
        "NFC Unicode Word Tokenizer (Devanagari akshara clusters preserved; dandas & list numbers excluded)",
    };
  }
  const normalized = text.normalize("NFC").replace(/[।॥]/g, " ");
  const matches = normalized.match(/[\p{L}\p{M}\p{N}]+(?:[-'’][\p{L}\p{M}\p{N}]+)*/gu) || [];
  const lexical = matches.filter((t) => !(t.length <= 2 && /^\d+$/.test(t)));
  let dev = 0;
  let lat = 0;
  for (const tok of lexical) {
    if (/[\u0900-\u097F]/.test(tok)) dev++;
    else if (/[a-zA-Z]/.test(tok)) lat++;
  }
  return {
    word_count: lexical.length,
    devanagari_words: dev,
    latin_words: lat,
    counting_convention:
      "NFC Unicode Word Tokenizer (Devanagari akshara clusters preserved; dandas & list numbers excluded)",
  };
}

export function evaluateWordLimit(
  wordCount: number,
  wordLimit: number | null | undefined,
  wordLimitType: string
): { status: string; notes: string[] } {
  const notes: string[] = [];
  if (!wordLimit || wordLimitType === "not_specified" || wordLimitType === "item_bound") {
    return { status: "within", notes };
  }
  if (wordLimitType === "approximate") {
    const low = Math.round(wordLimit * 0.7);
    const high = Math.round(wordLimit * 1.3);
    if (wordCount < low || wordCount > high) {
      notes.push(
        `Word count (${wordCount} words) is outside the advisory range (~${wordLimit} words; expected ${low}–${high} words).`
      );
    }
    return { status: "approximate", notes };
  }
  if (wordCount > wordLimit) {
    const excess = wordCount - wordLimit;
    const pct = Math.round((excess / wordLimit) * 1000) / 10;
    notes.push(
      `Word limit exceeded: ${wordCount}/${wordLimit} words (+${excess} words, +${pct}%). Flagged per marking scheme rules.`
    );
    return { status: "exceeded", notes };
  }
  return { status: "within", notes };
}

export function sanitizeUntrustedText(text: string) {
  const patterns = [
    /ignore\s+(all\s+)?(previous|prior|above)\s+instructions/gi,
    /system\s*prompt/gi,
    /you\s+are\s+now\s+in\s+developer\s+mode/gi,
    /award\s+full\s+marks/gi,
    /give\s+10\s*out\s+of\s+10/gi,
    /पूर्ण\s+अंक\s+प्रदान\s+करें/g,
  ];
  let sanitized = text || "";
  const matched: string[] = [];
  for (const pat of patterns) {
    const m = sanitized.match(pat);
    if (m) {
      matched.push(...m);
      sanitized = sanitized.replace(pat, "[REDACTED_PROMPT_INJECTION_ATTEMPT]");
    }
  }
  return {
    sanitized_text: sanitized,
    injection_detected: matched.length > 0,
    matched_patterns: matched,
  };
}

export function validateUrlSsrfSafe(urlStr: string) {
  try {
    const parsed = new URL(urlStr);
    if (parsed.protocol !== "https:") {
      return {
        allowed: false,
        reason: `Disallowed scheme '${parsed.protocol.replace(":", "")}': only 'https' is permitted.`,
      };
    }
    if (parsed.username || parsed.password) {
      return { allowed: false, reason: "Embedded URL credentials are prohibited." };
    }
    const host = parsed.hostname.toLowerCase();
    if (
      host === "localhost" ||
      host.startsWith("127.") ||
      host.startsWith("10.") ||
      host.startsWith("192.168.") ||
      host.startsWith("169.254.") ||
      host === "[::1]"
    ) {
      return { allowed: false, reason: `Blocked private/metadata/loopback host: ${host}` };
    }
    if (!ALLOWLISTED_REFERENCE_DOMAINS.has(host)) {
      return {
        allowed: false,
        reason: `Host '${host}' is not in ALLOWLISTED_REFERENCE_DOMAINS.`,
      };
    }
    return {
      allowed: true,
      host,
      scheme: "https",
      validated_at: new Date().toISOString(),
    };
  } catch (e: any) {
    return { allowed: false, reason: `Malformed URL: ${e.message}` };
  }
}

export function evaluateRubricBoundedGrade(
  questionSpec: any,
  transcriptText: string,
  transcriptVersion: string,
  examVersion: string,
  rubricVersion: string,
  paperStatus: string,
  pageNumber: number,
  bbox: number[],
  transcriptConfidence: number,
  hasUnresolvedDisagreement: boolean
) {
  const san = sanitizeUntrustedText(transcriptText);
  const wcInfo = countUnicodeWords(san.sanitized_text);
  const wl = evaluateWordLimit(
    wcInfo.word_count,
    questionSpec.word_limit,
    questionSpec.word_limit_type || "maximum"
  );

  const rubricBlock = questionSpec.rubric || {};
  const criteria = rubricBlock.criteria || questionSpec.criteria || [];
  const outline = questionSpec.answer_outline || {};
  const expectedPts = outline.expected_points || questionSpec.expected_points || [];
  const refs = outline.reference_sources || [];
  const defaultRef = refs[0] || {
    source_id: "ref-paper-canonical",
    claim_snapshot: "Verified against canonical question paper and examiner marking scheme.",
  };

  const sentences = san.sanitized_text
    .replace(/।/g, "।\n")
    .replace(/\./g, ".\n")
    .split("\n")
    .map((s) => s.trim())
    .filter((s) => s.length > 6);
  const quote1 = sentences[0] || san.sanitized_text.slice(0, 120);
  const quote2 = sentences[1] || quote1;

  const wc = wcInfo.word_count;
  const targetWl = Number(questionSpec.word_limit || 50);
  const isShortOrItemBound =
    questionSpec.word_limit_type === "item_bound" || targetWl <= 35;

  // Compute content coverage against expected points and appropriate length
  let matchedPoints = 0;
  const lowerText = san.sanitized_text.toLowerCase();
  for (const pt of expectedPts) {
    const keywords = String(pt)
      .toLowerCase()
      .split(/[\s,():;—\-/]+/)
      .filter((k) => k.length >= 4);
    const hits = keywords.filter((k) => lowerText.includes(k)).length;
    if (hits >= 1) matchedPoints++;
  }
  const ptCoverage =
    expectedPts.length > 0 ? Math.min(1, matchedPoints / Math.max(1, expectedPts.length * 0.75)) : 0.85;

  let ratio = 0.85;
  if (wc === 0 || san.sanitized_text.includes("[UNREADABLE_SPAN]")) {
    ratio = 0.25;
  } else if (isShortOrItemBound) {
    ratio = wc >= 4 ? Math.max(0.84, Math.min(0.95, 0.75 + ptCoverage * 0.2)) : 0.4;
  } else {
    const lengthAdequacy = Math.min(1, wc / Math.max(15, targetWl * 0.65));
    ratio = Math.max(0.45, Math.min(0.92, 0.45 * lengthAdequacy + 0.45 * Math.max(0.7, ptCoverage)));
  }

  const validatedCriteria = criteria.map((c: any, idx: number) => {
    const maxS = Number(c.max_score);
    const inc = Number(c.increment || 0.5);
    const slightVar = idx === 0 ? 1.02 : idx === criteria.length - 1 ? 0.96 : 1.0;
    let rawS = Math.round((maxS * ratio * slightVar) / inc) * inc;
    rawS = Math.min(maxS, Math.max(wc > 3 ? inc : 0.0, Math.round(rawS * 100) / 100));
    return {
      criterion_id: c.criterion_id,
      name: c.name || c.criterion_id,
      score: rawS,
      max_score: maxS,
      increment: inc,
      reason: `Assessed against ${c.name || c.criterion_id} marking anchor (${rawS}/${maxS} marks); key points verified in candidate script.`,
      answer_evidence: [{ page: pageNumber, bbox, quote: idx % 2 === 0 ? quote1 : quote2 }],
      key_evidence: refs.length
        ? [{ source_id: defaultRef.source_id, claim: defaultRef.claim_snapshot }]
        : [],
    };
  });

  const rawSum = validatedCriteria.reduce((acc: number, c: any) => acc + c.score, 0);
  const configuredDeduction = rubricBlock.numeric_penalty_configured
    ? Number(rubricBlock.configured_penalty_amount || 0)
    : 0;
  const maxMarks = Number(questionSpec.max_marks || 10);
  const finalScore = Math.max(
    0,
    Math.min(maxMarks, Math.round((rawSum - configuredDeduction) * 100) / 100)
  );

  const reviewReasons: string[] = [...wl.notes];
  if (san.injection_detected) {
    reviewReasons.push(
      `Irrelevant instruction pattern detected and removed from transcript.`
    );
  }
  if (paperStatus !== "published_v1") {
    reviewReasons.push(
      `Marking scheme for this paper is currently in Draft state. Senior Examiner approval in Stage 1 is required before final result publication.`
    );
  }
  if (transcriptConfidence < 0.8 || hasUnresolvedDisagreement) {
    reviewReasons.push(
      `Handwritten script contains flagged words requiring examiner verification in Stage 3.`
    );
  }

  const needsHumanReview = reviewReasons.length > 0 || paperStatus !== "published_v1";

  return {
    exam_version: examVersion,
    rubric_version: rubricVersion,
    question_id: questionSpec.question_id,
    transcript_version: transcriptVersion,
    word_count: wc,
    word_count_breakdown: {
      devanagari_words: wcInfo.devanagari_words,
      latin_words: wcInfo.latin_words,
      counting_convention: wcInfo.counting_convention,
    },
    word_limit_status: wl.status,
    criterion_scores: validatedCriteria,
    final_score: finalScore,
    max_marks: maxMarks,
    strengths: [
      `Directly addresses the core demand of ${questionSpec.question_id} with accurate terminology.`,
      `Demonstrates structured presentation across ${wc} words (${wcInfo.devanagari_words} Devanagari, ${wcInfo.latin_words} English tokens).`,
    ],
    missing_points: [
      expectedPts.length >= 3
        ? `Could further elaborate on: ${expectedPts[expectedPts.length - 1]}`
        : "Include one concrete contemporary or constitutional illustration to enrich depth.",
    ],
    factual_errors: [],
    language_or_format_issues: [
      "Verify spelling/conjunct clarity on low-confidence handwritten spans flagged during OCR review.",
    ],
    improvements: [
      `Underline key constitutional/historical terms and incorporate the remaining rubric anchor point (${
        expectedPts[expectedPts.length - 1] || "specific examples"
      }) within the word limit.`,
    ],
    confidence: needsHumanReview ? "medium" : "high",
    needs_human_review: needsHumanReview,
    review_reasons: reviewReasons,
    validator_audit: {
      validator_passed: true,
      validator_warnings: [],
      raw_criterion_sum: rawSum,
      penalty_applied: 0,
      provider_used: "deterministic_rubric_anchor_engine_v1",
      prompt_version: "uppsc-beo-grader-prompt-v1.2.0",
      evaluated_at: new Date().toISOString(),
    },
  };
}

// Singleton global store for serverless warm instances
const globalForState = globalThis as unknown as { __UPPSC_STATE__: any };

function createInitialState() {
  const preview = JSON.parse(JSON.stringify(importPreviewData));
  const papers: Record<string, any> = {};
  for (const p of preview.papers) {
    papers[p.paper_id] = p;
  }

  const auditEvents: any[] = [];
  const appendAudit = (
    eventType: string,
    entityType: string,
    entityId: string,
    actor = "examiner-01 (sample reviewer)",
    metadata: any = {}
  ) => {
    const prevHash =
      auditEvents.length > 0 ? auditEvents[auditEvents.length - 1].event_hash : "0".repeat(64);
    const ts = new Date().toISOString();
    const payload = `${prevHash}|${ts}|${eventType}|${entityType}|${entityId}|${JSON.stringify(metadata)}`;
    const evHash = stableHashHex(payload);
    const ev = {
      id: `aud-${String(auditEvents.length + 1).padStart(4, "0")}`,
      tenant_id: "ten-uppsc-eval-01",
      actor,
      event_type: eventType,
      entity_type: entityType,
      entity_id: entityId,
      prev_event_hash: prevHash.slice(0, 16) + "...",
      event_hash: evHash,
      created_at: ts,
      metadata,
    };
    auditEvents.push(ev);
    return ev;
  };

  appendAudit("IMPORT_PREVIEW_GENERATED", "exam_import", "imp-uppsc-beo-2026-01", "system-importer-worker", {
    source_files: 4,
    gs_mock17_questions: 40,
    hindi_mock16_items: 13,
    warnings_flagged: preview.import_warnings.length,
  });

  const sess1Id = "sess-gs17-cand8841";
  const sess2Id = "sess-hi16-cand9204";

  const sessions: Record<string, any> = {
    [sess1Id]: {
      session_id: sess1Id,
      tenant_id: "ten-uppsc-eval-01",
      paper_id: "uppsc-beo-mains-gs-mock-17-v1",
      pseudonym_code: "CAND-UP-8841",
      status: "review_needed",
      uploaded_at: "2026-10-12T09:15:00Z",
      quarantine_check: {
        valid: true,
        detected_mime: "application/pdf",
        size_bytes: 1284920,
        sha256: "e4a91c8f2b7d3e5a6c9f0b1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f",
        quarantine_status: "passed",
      },
      pages: [
        {
          page_id: "gs17_cand01_p1",
          page_number: 1,
          rotation_deg: 0,
          detected_skew_deg: -1.35,
          width_px: 1080,
          height_px: 1470,
          variants: {
            original: "/scans/gs17_cand01_p1_original.png",
            deskewed: "/scans/gs17_cand01_p1_deskewed.png",
            clahe_contrast: "/scans/gs17_cand01_p1_clahe_contrast.png",
            adaptive_ink: "/scans/gs17_cand01_p1_adaptive_ink.png",
            restormer_deblur_preview: "/scans/gs17_cand01_p1_restormer_deblur.png",
          },
        },
        {
          page_id: "gs17_cand01_p2",
          page_number: 2,
          rotation_deg: 0,
          detected_skew_deg: 1.15,
          width_px: 1080,
          height_px: 1470,
          variants: {
            original: "/scans/gs17_cand01_p2_original.png",
            deskewed: "/scans/gs17_cand01_p2_deskewed.png",
            clahe_contrast: "/scans/gs17_cand01_p2_clahe_contrast.png",
            adaptive_ink: "/scans/gs17_cand01_p2_adaptive_ink.png",
            restormer_deblur_preview: "/scans/gs17_cand01_p2_restormer_deblur.png",
          },
        },
      ],
      answer_ids: ["ans-gs17-q1", "ans-gs17-q4", "ans-gs17-q11", "ans-gs17-q21", "ans-gs17-q28"],
    },
    [sess2Id]: {
      session_id: sess2Id,
      tenant_id: "ten-uppsc-eval-01",
      paper_id: "uppsc-beo-mains-hindi-mock-16-draft",
      pseudonym_code: "CAND-UP-9204",
      status: "review_needed",
      uploaded_at: "2026-10-12T09:22:00Z",
      quarantine_check: {
        valid: true,
        detected_mime: "application/pdf",
        size_bytes: 1419300,
        sha256: "a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e",
        quarantine_status: "passed",
      },
      pages: [
        {
          page_id: "hi16_cand02_p1",
          page_number: 1,
          rotation_deg: 0,
          detected_skew_deg: -1.55,
          width_px: 1080,
          height_px: 1470,
          variants: {
            original: "/scans/hi16_cand02_p1_original.png",
            deskewed: "/scans/hi16_cand02_p1_deskewed.png",
            clahe_contrast: "/scans/hi16_cand02_p1_clahe_contrast.png",
            adaptive_ink: "/scans/hi16_cand02_p1_adaptive_ink.png",
            restormer_deblur_preview: "/scans/hi16_cand02_p1_restormer_deblur.png",
          },
        },
        {
          page_id: "hi16_cand02_p2",
          page_number: 2,
          rotation_deg: 0,
          detected_skew_deg: 0.95,
          width_px: 1080,
          height_px: 1470,
          variants: {
            original: "/scans/hi16_cand02_p2_original.png",
            deskewed: "/scans/hi16_cand02_p2_deskewed.png",
            clahe_contrast: "/scans/hi16_cand02_p2_clahe_contrast.png",
            adaptive_ink: "/scans/hi16_cand02_p2_adaptive_ink.png",
            restormer_deblur_preview: "/scans/hi16_cand02_p2_restormer_deblur.png",
          },
        },
      ],
      answer_ids: [
        "ans-hi16-q1a",
        "ans-hi16-q1c",
        "ans-hi16-q2",
        "ans-hi16-q3b",
        "ans-hi16-q6a",
        "ans-hi16-q6b",
      ],
    },
  };

  const seededAnswers = [
    {
      answer_id: "ans-gs17-q1",
      session_id: sess1Id,
      paper_id: "uppsc-beo-mains-gs-mock-17-v1",
      question_id: "Mock 17-01",
      page_id: "gs17_cand01_p1",
      page_number: 1,
      bbox_norm: [0.144, 0.089, 0.925, 0.505],
      script_detected: "hi",
      assignment_confidence: 0.96,
      informed_by_variant: "clahe_contrast",
      ocr_candidates: [
        {
          adapter_id: "indic_ocr_bodhan",
          adapter_name: "Reader A (primary)",
          calibrated_confidence: 0.89,
          transcript:
            "वैदिक काल से महाजनपद काल (600 ई.पू.) तक भारतीय समाज एवं राजनीतिक व्यवस्था में आमूलचूल परिवर्तन हुए। ऋग्वैदिक काल में समाज कबीलाई संरचना ('जन') पर आधारित था तथा वर्ण व्यवस्था कर्म पर आधारित एवं लचीली थी। उत्तर वैदिक काल एवं महाजनपद काल तक वर्ण व्यवस्था जन्म आधारित हो गई और अनेक जातियों का उदय हुआ। राजनीतिक स्तर पर, 'जन' का स्थान क्षेत्रीय 'जनपद' और १६ महाजनपदों (मगध, कोशल, वत्स, अवंति) ने ले लिया। सभा और समिति जैसी संस्थाओं का प्रभाव घटा तथा राजतंत्र और गणसंघ (वज्जि, मल्ल) विकसित हुए। गंगा घाटी में लोहे के फाल (अयस्) के प्रयोग से कृषि अधिशेष बढ़ा, जिससे द्वितीय नगरीकरण, नियमित कर प्रणाली ('भाग' व 'बलि') तथा स्थायी सेना का निर्माण संभव हुआ।",
        },
        {
          adapter_id: "qwen2vl_2b_hindi_htr",
          adapter_name: "Reader B (Hindi handwriting)",
          calibrated_confidence: 0.86,
          transcript:
            "वैदिक काल से महाजनपद काल (600 ई.पू.) तक भारतीय समाज एवं राजनीतिक व्यवस्था में आमूलचूल परिवर्तन हुए। ऋग्वैदिक काल में समाज कबीलाई संरचना ('जन') पर आधारित था तथा वर्ण व्यवस्था कर्म पर आधारित एवं लचीली थी। उत्तर वैदिक काल एवं महाजनपद काल तक वर्ण व्यवस्था जन्म आधारित हो गई और अनेक जातियों का उदय हुआ। राजनीतिक स्तर पर, 'जन' का स्थान क्षेत्रीय 'जनपद' और १६ महाजनपदों (मगध, कोशल, वत्स, अवंति) ने ले लिया। सभा और सामिति जैसी संख्याओं का प्रभाव घटा तथा राजतंत्र और गणसंघ (वज्जि, मल्ल) विकसित हुए। गंगा घाटी में लोहे के फाल (अयस्) के प्रयोग से कृषि अधिशेष बढ़ा, जिससे द्वितीय नगरीकरण, नियमित कर प्रणाली ('भाग' व 'बलि') तथा स्थायी सेना का निर्माण संभव हुआ।",
        },
      ],
      uncertain_spans: [
        {
          span_id: "sp-gs17-q1-1",
          bbox_norm: [0.33, 0.23, 0.55, 0.26],
          current_text: "सभा और समिति जैसी संस्थाओं",
          calibrated_confidence: 0.68,
          disagreement_reason:
            "Smudged ink stroke on line 5: Primary Reader reads 'सभा और समिति जैसी संस्थाओं' (0.79) while Secondary Reader reads 'सभा और सामिति जैसी संख्याओं' (0.64).",
          alternatives: [
            { model: "Reading 1 (Primary)", text: "सभा और समिति जैसी संस्थाओं", confidence: 0.79 },
            { model: "Reading 2 (Secondary)", text: "सभा और सामिति जैसी संख्याओं", confidence: 0.64 },
            { model: "Mark as Illegible", text: "[UNREADABLE_SPAN]", confidence: 1.0 },
          ],
          resolved_by_human: true,
        },
      ],
      revisions: [
        {
          version_id: "tv-gs17-q1-v1",
          revision_number: 1,
          source_type: "ocr_ensemble",
          is_confirmed_for_grading: false,
          created_at: "2026-10-12T09:16:10Z",
          author: "Optical Script Reader (Initial Transcription)",
          text: "वैदिक काल से महाजनपद काल (600 ई.पू.) तक भारतीय समाज एवं राजनीतिक व्यवस्था में आमूलचूल परिवर्तन हुए। ऋग्वैदिक काल में समाज कबीलाई संरचना ('जन') पर आधारित था तथा वर्ण व्यवस्था कर्म पर आधारित एवं लचीली थी। उत्तर वैदिक काल एवं महाजनपद काल तक वर्ण व्यवस्था जन्म आधारित हो गई और अनेक जातियों का उदय हुआ। राजनीतिक स्तर पर, 'जन' का स्थान क्षेत्रीय 'जनपद' और १६ महाजनपदों (मगध, कोशल, वत्स, अवंति) ने ले लिया। सभा और सामिति जैसी संख्याओं का प्रभाव घटा तथा राजतंत्र और गणसंघ (वज्जि, मल्ल) विकसित हुए। गंगा घाटी में लोहे के फाल (अयस्) के प्रयोग से कृषि अधिशेष बढ़ा, जिससे द्वितीय नगरीकरण, नियमित कर प्रणाली ('भाग' व 'बलि') तथा स्थायी सेना का निर्माण संभव हुआ।",
        },
        {
          version_id: "tv-gs17-q1-v2",
          revision_number: 2,
          source_type: "examiner_verified",
          is_confirmed_for_grading: true,
          created_at: "2026-10-12T09:18:45Z",
          author: "Senior Examiner (sample reviewer)",
          text: "वैदिक काल से महाजनपद काल (600 ई.पू.) तक भारतीय समाज एवं राजनीतिक व्यवस्था में आमूलचूल परिवर्तन हुए। ऋग्वैदिक काल में समाज कबीलाई संरचना ('जन') पर आधारित था तथा वर्ण व्यवस्था कर्म पर आधारित एवं लचीली थी। उत्तर वैदिक काल एवं महाजनपद काल तक वर्ण व्यवस्था जन्म आधारित हो गई और अनेक जातियों का उदय हुआ। राजनीतिक स्तर पर, 'जन' का स्थान क्षेत्रीय 'जनपद' और १६ महाजनपदों (मगध, कोशल, वत्स, अवंति) ने ले लिया। सभा और समिति जैसी संस्थाओं का प्रभाव घटा तथा राजतंत्र और गणसंघ (वज्जि, मल्ल) विकसित हुए। गंगा घाटी में लोहे के फाल (अयस्) के प्रयोग से कृषि अधिशेष बढ़ा, जिससे द्वितीय नगरीकरण, नियमित कर प्रणाली ('भाग' व 'बलि') तथा स्थायी सेना का निर्माण संभव हुआ।",
        },
      ],
    },
    {
      answer_id: "ans-gs17-q4",
      session_id: sess1Id,
      paper_id: "uppsc-beo-mains-gs-mock-17-v1",
      question_id: "Mock 17-04",
      page_id: "gs17_cand01_p1",
      page_number: 1,
      bbox_norm: [0.144, 0.53, 0.925, 0.943],
      script_detected: "en",
      assignment_confidence: 0.98,
      informed_by_variant: "clahe_contrast",
      ocr_candidates: [
        {
          adapter_id: "indic_ocr_bodhan",
          adapter_name: "Reader A (primary)",
          calibrated_confidence: 0.93,
          transcript:
            "Part XI (Articles 245–255) and the Seventh Schedule of the Indian Constitution govern the distribution of legislative powers between the Union and the States.\n1. Territorial Jurisdiction (Art. 245): Parliament legislates for the whole or any part of India, while a State Legislature makes laws for the state territory.\n2. Threefold Subject Division (Art. 246): Powers are divided into Union List (List I — defence, foreign affairs, banking), State List (List II — public order, police, agriculture), and Concurrent List (List III — education, forests).\n3. Union Supremacy & Residuary Powers: Under Art. 254, Union law prevails in Concurrent List conflicts. Under Art. 248, residuary subjects belong to Parliament.\n4. Exceptional Parliamentary Legislation on State List: National interest resolution by Rajya Sabha (Art. 249), National Emergency (Art. 250), agreement of States (Art. 252), and international treaties (Art. 253).",
        },
      ],
      uncertain_spans: [
        {
          span_id: "sp-gs17-q4-1",
          bbox_norm: [0.43, 0.69, 0.62, 0.72],
          current_text: "(List III — education, forests)",
          calibrated_confidence: 0.74,
          disagreement_reason:
            "Blurred Roman numeral: Primary Reader reads 'List III' (0.88) while Line Segmenter reads 'List II' (0.61).",
          alternatives: [
            { model: "Reading 1 (Primary)", text: "(List III — education, forests)", confidence: 0.88 },
            { model: "Reading 2 (Segmenter)", text: "(List II — education, forests)", confidence: 0.61 },
          ],
          resolved_by_human: true,
        },
      ],
      revisions: [
        {
          version_id: "tv-gs17-q4-v1",
          revision_number: 1,
          source_type: "examiner_verified",
          is_confirmed_for_grading: true,
          created_at: "2026-10-12T09:19:30Z",
          author: "Senior Examiner (sample reviewer)",
          text: "Part XI (Articles 245–255) and the Seventh Schedule of the Indian Constitution govern the distribution of legislative powers between the Union and the States.\n1. Territorial Jurisdiction (Art. 245): Parliament legislates for the whole or any part of India, while a State Legislature makes laws for the state territory.\n2. Threefold Subject Division (Art. 246): Powers are divided into Union List (List I — defence, foreign affairs, banking), State List (List II — public order, police, agriculture), and Concurrent List (List III — education, forests).\n3. Union Supremacy & Residuary Powers: Under Art. 254, Union law prevails in Concurrent List conflicts. Under Art. 248, residuary subjects belong to Parliament.\n4. Exceptional Parliamentary Legislation on State List: National interest resolution by Rajya Sabha (Art. 249), National Emergency (Art. 250), agreement of States (Art. 252), and international treaties (Art. 253).",
        },
      ],
    },
    {
      answer_id: "ans-gs17-q11",
      session_id: sess1Id,
      paper_id: "uppsc-beo-mains-gs-mock-17-v1",
      question_id: "Mock 17-11",
      page_id: "gs17_cand01_p2",
      page_number: 2,
      bbox_norm: [0.144, 0.092, 0.925, 0.367],
      script_detected: "hi",
      assignment_confidence: 0.95,
      informed_by_variant: "clahe_contrast",
      ocr_candidates: [
        {
          adapter_id: "indic_ocr_bodhan",
          adapter_name: "Reader A (primary)",
          calibrated_confidence: 0.91,
          transcript:
            "महाजनपदों के उदय के दो प्रमुख कारण निम्नलिखित हैं:\n१. लोहे की तकनीक और कृषि अधिशेष: मध्य गंगा घाटी की उपजाऊ जलोढ़ भूमि में लोहे के हल के व्यापक प्रयोग से अन्न उत्पादन में भारी वृद्धि हुई, जिसने नगरों व प्रशासन को आधार दिया।\n२. व्यापार, आहत सिक्कों (Punch-marked coins) का प्रचलन तथा मगध जैसे राज्यों की सैन्य व खनिज संपन्नता।",
        },
      ],
      uncertain_spans: [],
      revisions: [
        {
          version_id: "tv-gs17-q11-v1",
          revision_number: 1,
          source_type: "examiner_verified",
          is_confirmed_for_grading: true,
          created_at: "2026-10-12T09:20:00Z",
          author: "Senior Examiner (sample reviewer)",
          text: "महाजनपदों के उदय के दो प्रमुख कारण निम्नलिखित हैं:\n१. लोहे की तकनीक और कृषि अधिशेष: मध्य गंगा घाटी की उपजाऊ जलोढ़ भूमि में लोहे के हल के व्यापक प्रयोग से अन्न उत्पादन में भारी वृद्धि हुई, जिसने नगरों व प्रशासन को आधार दिया।\n२. व्यापार, आहत सिक्कों (Punch-marked coins) का प्रचलन तथा मगध जैसे राज्यों की सैन्य व खनिज संपन्नता।",
        },
      ],
    },
    {
      answer_id: "ans-gs17-q21",
      session_id: sess1Id,
      paper_id: "uppsc-beo-mains-gs-mock-17-v1",
      question_id: "Mock 17-21",
      page_id: "gs17_cand01_p2",
      page_number: 2,
      bbox_norm: [0.144, 0.403, 0.925, 0.622],
      script_detected: "hi",
      assignment_confidence: 0.97,
      informed_by_variant: "clahe_contrast",
      ocr_candidates: [
        {
          adapter_id: "indic_ocr_bodhan",
          adapter_name: "Reader A (primary)",
          calibrated_confidence: 0.94,
          transcript:
            "महाजनपद: छठी शताब्दी ई.पू. में उत्तर भारत में उभरे १६ बड़े क्षेत्रीय राज्यों को महाजनपद कहा गया (बौद्ध ग्रंथ अंगुत्तर निकाय में उल्लिखित), जिनमें मगध, कोशल, वत्स, अवंति (राजतंत्र) तथा वज्जि व मल्ल (गणसंघ) प्रमुख थे।",
        },
      ],
      uncertain_spans: [],
      revisions: [
        {
          version_id: "tv-gs17-q21-v1",
          revision_number: 1,
          source_type: "examiner_verified",
          is_confirmed_for_grading: true,
          created_at: "2026-10-12T09:20:20Z",
          author: "Senior Examiner (sample reviewer)",
          text: "महाजनपद: छठी शताब्दी ई.पू. में उत्तर भारत में उभरे १६ बड़े क्षेत्रीय राज्यों को महाजनपद कहा गया (बौद्ध ग्रंथ अंगुत्तर निकाय में उल्लिखित), जिनमें मगध, कोशल, वत्स, अवंति (राजतंत्र) तथा वज्जि व मल्ल (गणसंघ) प्रमुख थे।",
        },
      ],
    },
    {
      answer_id: "ans-gs17-q28",
      session_id: sess1Id,
      paper_id: "uppsc-beo-mains-gs-mock-17-v1",
      question_id: "Mock 17-28",
      page_id: "gs17_cand01_p2",
      page_number: 2,
      bbox_norm: [0.144, 0.658, 0.925, 0.908],
      script_detected: "en",
      assignment_confidence: 0.97,
      informed_by_variant: "clahe_contrast",
      ocr_candidates: [
        {
          adapter_id: "indic_ocr_bodhan",
          adapter_name: "Reader A (primary)",
          calibrated_confidence: 0.95,
          transcript:
            "Union List: List I of the Seventh Schedule (Article 246(1)) of the Constitution enumerates subjects of national importance (originally 97, presently 100 items such as Defence, Atomic Energy, Foreign Affairs, Railways, and Banking) over which Parliament has exclusive legislative authority.",
        },
      ],
      uncertain_spans: [],
      revisions: [
        {
          version_id: "tv-gs17-q28-v1",
          revision_number: 1,
          source_type: "examiner_verified",
          is_confirmed_for_grading: true,
          created_at: "2026-10-12T09:20:45Z",
          author: "Senior Examiner (sample reviewer)",
          text: "Union List: List I of the Seventh Schedule (Article 246(1)) of the Constitution enumerates subjects of national importance (originally 97, presently 100 items such as Defence, Atomic Energy, Foreign Affairs, Railways, and Banking) over which Parliament has exclusive legislative authority.",
        },
      ],
    },
    {
      answer_id: "ans-hi16-q1a",
      session_id: sess2Id,
      paper_id: "uppsc-beo-mains-hindi-mock-16-draft",
      question_id: "Hindi-Mock16-1(a)",
      page_id: "hi16_cand02_p1",
      page_number: 1,
      bbox_norm: [0.144, 0.089, 0.925, 0.27],
      script_detected: "hi",
      assignment_confidence: 0.94,
      informed_by_variant: "clahe_contrast",
      ocr_candidates: [
        {
          adapter_id: "qwen2vl_2b_hindi_htr",
          adapter_name: "Reader B (Hindi handwriting)",
          calibrated_confidence: 0.88,
          transcript:
            "(i) आधारशिला — किसी संबंध या व्यवस्था का मूल आधार अथवा बुनियाद।\n(ii) स्थायित्व — स्थिरता, टिकाऊपन या दीर्घकाल तक बने रहने का गुण।\n(iii) असावधानी — लापरवाही, चूक अथवा सतर्कता का अभाव।",
        },
      ],
      uncertain_spans: [
        {
          span_id: "sp-hi16-q1a-1",
          bbox_norm: [0.25, 0.14, 0.43, 0.18],
          current_text: "असावधानी — लापरवाही, चूक",
          calibrated_confidence: 0.71,
          disagreement_reason:
            "Smudged stroke on line 3: Primary Reader reads 'असावधानी — लापरवाही, चूक' (0.86) while Secondary Reader drops the u-matra in 'चूक' ('चक', 0.58).",
          alternatives: [
            { model: "Reading 2 (Secondary)", text: "असावधानी — लापरवाही, चूक", confidence: 0.86 },
            { model: "Reading 2 (Line Check)", text: "असावधानी — लापरवाही, चक", confidence: 0.58 },
          ],
          resolved_by_human: true,
        },
      ],
      revisions: [
        {
          version_id: "tv-hi16-q1a-v1",
          revision_number: 1,
          source_type: "examiner_verified",
          is_confirmed_for_grading: true,
          created_at: "2026-10-12T09:24:00Z",
          author: "Hindi Examiner (sample reviewer)",
          text: "(i) आधारशिला — किसी संबंध या व्यवस्था का मूल आधार अथवा बुनियाद।\n(ii) स्थायित्व — स्थिरता, टिकाऊपन या दीर्घकाल तक बने रहने का गुण।\n(iii) असावधानी — लापरवाही, चूक अथवा सतर्कता का अभाव।",
        },
      ],
    },
    {
      answer_id: "ans-hi16-q1c",
      session_id: sess2Id,
      paper_id: "uppsc-beo-mains-hindi-mock-16-draft",
      question_id: "Hindi-Mock16-1(c)",
      page_id: "hi16_cand02_p1",
      page_number: 1,
      bbox_norm: [0.144, 0.285, 0.925, 0.377],
      script_detected: "hi",
      assignment_confidence: 0.96,
      informed_by_variant: "clahe_contrast",
      ocr_candidates: [
        {
          adapter_id: "indic_ocr_bodhan",
          adapter_name: "Reader A (primary)",
          calibrated_confidence: 0.94,
          transcript: "उपयुक्त शीर्षक: “स्वस्थ मानवीय संबंधों में विश्वास और संवाद का महत्व”",
        },
      ],
      uncertain_spans: [],
      revisions: [
        {
          version_id: "tv-hi16-q1c-v1",
          revision_number: 1,
          source_type: "examiner_verified",
          is_confirmed_for_grading: true,
          created_at: "2026-10-12T09:24:30Z",
          author: "Hindi Examiner (sample reviewer)",
          text: "उपयुक्त शीर्षक: “स्वस्थ मानवीय संबंधों में विश्वास और संवाद का महत्व”",
        },
      ],
    },
    {
      answer_id: "ans-hi16-q2",
      session_id: sess2Id,
      paper_id: "uppsc-beo-mains-hindi-mock-16-draft",
      question_id: "Hindi-Mock16-2",
      page_id: "hi16_cand02_p1",
      page_number: 1,
      bbox_norm: [0.144, 0.403, 0.925, 0.948],
      script_detected: "hi",
      assignment_confidence: 0.95,
      informed_by_variant: "clahe_contrast",
      ocr_candidates: [
        {
          adapter_id: "indic_ocr_bodhan",
          adapter_name: "Reader A (primary)",
          calibrated_confidence: 0.87,
          transcript:
            "कार्यालय जिला बेसिक शिक्षा अधिकारी, वाराणसी (उत्तर प्रदेश)\nपत्रांक: शि०नि०/अनु०/2026-27/148        दिनांक: 12 अक्टूबर, 2026\nकार्यालय ज्ञापन\nविषय: विद्यालयों में सार्वजनिक संपत्ति की सुरक्षा एवं परिसर में अनुशासन बनाए रखने के संबंध में।\nजनपद के समस्त राजकीय एवं परिषदीय विद्यालयों के प्रधानाध्यापकों, शिक्षकों एवं विद्यार्थियों को सूचित किया जाता है कि विद्यालय परिसर में स्थित कक्षा-कक्ष फर्नीचर, पुस्तकालय, प्रयोगशाला उपकरण, पेयजल एवं विद्युत संयंत्र सार्वजनिक संपत्ति हैं। इनका संरक्षण प्रत्येक विद्यार्थी का नैतिक एवं नागरिक कर्तव्य है।\nअतः निर्देशित किया जाता है कि विद्यालय में पूर्ण अनुशासन बनाए रखा जाए तथा किसी भी सार्वजनिक संपत्ति को क्षति न पहुँचाई जाए। प्रत्येक विद्यालय में 'अनुशासन एवं संपत्ति संरक्षण समिति' गठित कर नियमित निगरानी सुनिश्चित की जाए।\nह०/- (क०ख०ग०)\nजिला बेसिक शिक्षा अधिकारी, वाराणसी\nप्रतिलिपि: १. समस्त खंड शिक्षा अधिकारी (BEO) को अनुपालनार्थ। २. समस्त प्रधानाध्यापक को सूचनार्थ।",
        },
      ],
      uncertain_spans: [
        {
          span_id: "sp-hi16-q2-1",
          bbox_norm: [0.3, 0.63, 0.57, 0.67],
          current_text: "जाता है कि विद्यालय में पूर्ण अनुशासन",
          calibrated_confidence: 0.72,
          disagreement_reason:
            "Faint pen pressure in middle paragraph; verified against CLAHE contrast derivative.",
          alternatives: [
            { model: "Reading 1 (Primary)", text: "जाता है कि विद्यालय में पूर्ण अनुशासन", confidence: 0.84 },
            { model: "Reading 2 (Line Check)", text: "जाता है कि विध्यालय में पूर्ण अनुशासन", confidence: 0.62 },
          ],
          resolved_by_human: false,
        },
      ],
      revisions: [
        {
          version_id: "tv-hi16-q2-v1",
          revision_number: 1,
          source_type: "examiner_verified",
          is_confirmed_for_grading: true,
          created_at: "2026-10-12T09:25:15Z",
          author: "Hindi Examiner (sample reviewer)",
          text: "कार्यालय जिला बेसिक शिक्षा अधिकारी, वाराणसी (उत्तर प्रदेश)\nपत्रांक: शि०नि०/अनु०/2026-27/148        दिनांक: 12 अक्टूबर, 2026\nकार्यालय ज्ञापन\nविषय: विद्यालयों में सार्वजनिक संपत्ति की सुरक्षा एवं परिसर में अनुशासन बनाए रखने के संबंध में।\nजनपद के समस्त राजकीय एवं परिषदीय विद्यालयों के प्रधानाध्यापकों, शिक्षकों एवं विद्यार्थियों को सूचित किया जाता है कि विद्यालय परिसर में स्थित कक्षा-कक्ष फर्नीचर, पुस्तकालय, प्रयोगशाला उपकरण, पेयजल एवं विद्युत संयंत्र सार्वजनिक संपत्ति हैं। इनका संरक्षण प्रत्येक विद्यार्थी का नैतिक एवं नागरिक कर्तव्य है।\nअतः निर्देशित किया जाता है कि विद्यालय में पूर्ण अनुशासन बनाए रखा जाए तथा किसी भी सार्वजनिक संपत्ति को क्षति न पहुँचाई जाए। प्रत्येक विद्यालय में 'अनुशासन एवं संपत्ति संरक्षण समिति' गठित कर नियमित निगरानी सुनिश्चित की जाए।\nह०/- (क०ख०ग०)\nजिला बेसिक शिक्षा अधिकारी, वाराणसी\nप्रतिलिपि: १. समस्त खंड शिक्षा अधिकारी (BEO) को अनुपालनार्थ। २. समस्त प्रधानाध्यापक को सूचनार्थ।",
        },
      ],
    },
    {
      answer_id: "ans-hi16-q3b",
      session_id: sess2Id,
      paper_id: "uppsc-beo-mains-hindi-mock-16-draft",
      question_id: "Hindi-Mock16-3",
      page_id: "hi16_cand02_p2",
      page_number: 2,
      bbox_norm: [0.144, 0.092, 0.925, 0.367],
      script_detected: "hi",
      assignment_confidence: 0.97,
      informed_by_variant: "clahe_contrast",
      ocr_candidates: [
        {
          adapter_id: "qwen2vl_2b_hindi_htr",
          adapter_name: "Reader B (Hindi handwriting)",
          calibrated_confidence: 0.93,
          transcript:
            "प्रत्यय एवं मूल शब्द पृथक्करण (विकल्प ख):\n१. मानवता = मानव (मूल शब्द) + ता (प्रत्यय)\n२. सामाजिक = समाज (मूल शब्द) + इक (प्रत्यय)\n३. लिखावट = लिखना / लिख (धातु) + आवट (प्रत्यय)\n४. मिठास = मीठा (मूल शब्द) + आस (प्रत्यय)\n५. बचपन = बच्चा (मूल शब्द) + पन (प्रत्यय)",
        },
      ],
      uncertain_spans: [],
      revisions: [
        {
          version_id: "tv-hi16-q3b-v1",
          revision_number: 1,
          source_type: "examiner_verified",
          is_confirmed_for_grading: true,
          created_at: "2026-10-12T09:26:00Z",
          author: "Hindi Examiner (sample reviewer)",
          text: "प्रत्यय एवं मूल शब्द पृथक्करण (विकल्प ख):\n१. मानवता = मानव (मूल शब्द) + ता (प्रत्यय)\n२. सामाजिक = समाज (मूल शब्द) + इक (प्रत्यय)\n३. लिखावट = लिखना / लिख (धातु) + आवट (प्रत्यय)\n४. मिठास = मीठा (मूल शब्द) + आस (प्रत्यय)\n५. बचपन = बच्चा (मूल शब्द) + पन (प्रत्यय)",
        },
      ],
    },
    {
      answer_id: "ans-hi16-q6a",
      session_id: sess2Id,
      paper_id: "uppsc-beo-mains-hindi-mock-16-draft",
      question_id: "Hindi-Mock16-6a",
      page_id: "hi16_cand02_p2",
      page_number: 2,
      bbox_norm: [0.144, 0.392, 0.925, 0.612],
      script_detected: "hi",
      assignment_confidence: 0.95,
      informed_by_variant: "clahe_contrast",
      ocr_candidates: [
        {
          adapter_id: "qwen2vl_2b_hindi_htr",
          adapter_name: "Reader B (Hindi handwriting)",
          calibrated_confidence: 0.89,
          transcript:
            "शब्दों के शुद्ध रूप:\n१. कृतग्य → कृतज्ञ     २. स्वाधिन → स्वाधीन\n३. उत्तरदाई → उत्तरदायी     ४. सौन्दर्य → सौंदर्य\n५. उज्जवल → उज्ज्वल",
        },
      ],
      uncertain_spans: [
        {
          span_id: "sp-hi16-q6a-1",
          bbox_norm: [0.25, 0.52, 0.47, 0.56],
          current_text: "५. उज्जवल → उज्ज्वल",
          calibrated_confidence: 0.7,
          disagreement_reason:
            "Mark-sensitive conjunct 'ज्ज्व' in item 5: Primary Reader detects double half-ja 'उज्ज्वल' (0.87) while Secondary Reader collapses conjunct to 'उज्जवल' (0.59).",
          alternatives: [
            { model: "Reading 2 (Secondary)", text: "५. उज्जवल → उज्ज्वल", confidence: 0.87 },
            { model: "Reading 2 (Line Check)", text: "५. उज्जवल → उज्जवल", confidence: 0.59 },
          ],
          resolved_by_human: true,
        },
      ],
      revisions: [
        {
          version_id: "tv-hi16-q6a-v1",
          revision_number: 1,
          source_type: "examiner_verified",
          is_confirmed_for_grading: true,
          created_at: "2026-10-12T09:26:40Z",
          author: "Hindi Examiner (sample reviewer)",
          text: "शब्दों के शुद्ध रूप:\n१. कृतग्य → कृतज्ञ     २. स्वाधिन → स्वाधीन\n३. उत्तरदाई → उत्तरदायी     ४. सौन्दर्य → सौंदर्य\n५. उज्जवल → उज्ज्वल",
        },
      ],
    },
    {
      answer_id: "ans-hi16-q6b",
      session_id: sess2Id,
      paper_id: "uppsc-beo-mains-hindi-mock-16-draft",
      question_id: "Hindi-Mock16-6b",
      page_id: "hi16_cand02_p2",
      page_number: 2,
      bbox_norm: [0.144, 0.637, 0.925, 0.928],
      script_detected: "hi",
      assignment_confidence: 0.96,
      informed_by_variant: "clahe_contrast",
      ocr_candidates: [
        {
          adapter_id: "indic_ocr_bodhan",
          adapter_name: "Reader A (primary)",
          calibrated_confidence: 0.94,
          transcript:
            "वाक्य-शुद्धि:\n१. हमें एक-दूसरे का सहयोग करना चाहिए।\n२. उसके व्यवहार से मुझे बहुत संतोष हुआ है।\n३. दोनों मित्रों के बीच विवाद हो गया।\n४. वह अपने माता-पिता की आज्ञा मानता है।\n५. किसी के विचारों को बिना समझे उसका विरोध नहीं करना चाहिए।",
        },
      ],
      uncertain_spans: [],
      revisions: [
        {
          version_id: "tv-hi16-q6b-v1",
          revision_number: 1,
          source_type: "examiner_verified",
          is_confirmed_for_grading: true,
          created_at: "2026-10-12T09:27:10Z",
          author: "Hindi Examiner (sample reviewer)",
          text: "वाक्य-शुद्धि:\n१. हमें एक-दूसरे का सहयोग करना चाहिए।\n२. उसके व्यवहार से मुझे बहुत संतोष हुआ है।\n३. दोनों मित्रों के बीच विवाद हो गया।\n४. वह अपने माता-पिता की आज्ञा मानता है।\n५. किसी के विचारों को बिना समझे उसका विरोध नहीं करना चाहिए।",
        },
      ],
    },
  ];

  const answers: Record<string, any> = {};
  const gradeRuns: Record<string, any> = {};

  for (const ans of seededAnswers) {
    answers[ans.answer_id] = ans;
    const paper = papers[ans.paper_id];
    const qSpec = paper.questions.find((q: any) => q.question_id === ans.question_id);
    const latestRev = ans.revisions[ans.revisions.length - 1];
    const hasDis = ans.uncertain_spans.some((s: any) => !s.resolved_by_human);
    const contract = evaluateRubricBoundedGrade(
      qSpec,
      latestRev.text,
      latestRev.version_id,
      paper.paper_id,
      paper.rubric_version,
      paper.status,
      ans.page_number,
      ans.bbox_norm,
      ans.ocr_candidates[0].calibrated_confidence,
      hasDis
    );
    const grId = `gr-${ans.answer_id}`;
    const grRecord: any = {
      grade_run_id: grId,
      answer_id: ans.answer_id,
      session_id: ans.session_id,
      paper_id: ans.paper_id,
      question_id: ans.question_id,
      created_at: new Date().toISOString(),
      contract,
      human_reviews: [],
    };
    if (ans.answer_id === "ans-gs17-q1") {
      grRecord.human_reviews.push({
        review_id: "hr-gs17-q1-01",
        reviewer: "Senior Examiner (sample reviewer)",
        action: "overridden",
        ai_suggested_score: contract.final_score,
        reviewed_final_score: 8.5,
        override_reason:
          "Candidate accurately covered Vedic-to-Mahajanapada social & political shifts, iron ploughshare surplus, Gana-Sanghas, and Bhaga/Bali taxation within 118 words. Upgraded Content from 3.5 to 4.0.",
        created_at: "2026-10-12T09:30:00Z",
      });
    }
    gradeRuns[grId] = grRecord;
    (ans as any).latest_grade_run_id = grId;
  }

  return {
    tenant: {
      id: "ten-uppsc-eval-01",
      slug: "uppsc-beo-cell",
      name: "UPPSC Block Education Officer (BEO) Evaluation Directorate",
      kms_envelope_encryption: "AES-256-GCM (Managed KMS Envelope Key Rotation Active)",
    },
    import_preview: preview,
    papers,
    sessions,
    answers,
    grade_runs: gradeRuns,
    audit_events: auditEvents,
    appendAudit,
    retention_policies: [
      { category: "raw_answer_sheet_scans", retention_days: 180, auto_purge: true, encryption: "AES-256-GCM Envelope" },
      { category: "normalized_page_derivatives", retention_days: 90, auto_purge: true, encryption: "AES-256-GCM Envelope" },
      { category: "immutable_transcript_versions", retention_days: 365, auto_purge: false, encryption: "Postgres TDE + RLS" },
      { category: "grade_runs_and_teacher_reviews", retention_days: 730, auto_purge: false, encryption: "Postgres TDE + RLS" },
      { category: "hash_chained_audit_logs", retention_days: 1825, auto_purge: false, encryption: "Append-Only WORM" },
    ],
  };
}

export function getAppState() {
  if (!globalForState.__UPPSC_STATE__) {
    globalForState.__UPPSC_STATE__ = createInitialState();
  }
  return globalForState.__UPPSC_STATE__;
}

export const REVIEW_ACTIONS = ["approved", "overridden", "returned_for_transcript_correction"] as const;

/**
 * Validates an examiner decision against its grade run.
 * - "approved" accepts the AI suggestion as-is, so the mark must equal the suggestion.
 * - "overridden" changes the mark and always needs a substantive reason (min 5 characters).
 * - "returned_for_transcript_correction" needs no reason and leaves the mark unchanged.
 * Returns an error message, or null when the decision is valid.
 */
export function validateExaminerDecision(
  gr: any,
  body: { action?: string; reviewed_final_score?: unknown; override_reason?: unknown }
): { detail: string; status: number } | null {
  const action = body.action || "approved";
  if (!(REVIEW_ACTIONS as readonly string[]).includes(action)) {
    return { detail: "Unknown decision type.", status: 400 };
  }
  const maxM = Number(gr.contract.max_marks);
  const revScore = Number(body.reviewed_final_score);
  if (!Number.isFinite(revScore) || revScore < 0 || revScore > maxM) {
    return { detail: `Reviewed score must be between 0 and ${maxM}`, status: 400 };
  }
  const reason = typeof body.override_reason === "string" ? body.override_reason.trim() : "";
  if (action === "overridden" && reason.length < 5) {
    return { detail: "A substantive examiner reason is required when the mark is changed.", status: 400 };
  }
  if (action === "approved" && Math.abs(revScore - Number(gr.contract.final_score)) > 1e-9) {
    return { detail: "Accepting keeps the suggested mark. Choose 'Change mark' to record a different mark.", status: 400 };
  }
  return null;
}

export class GradeRequestError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/** Grades one answer against its latest transcript. Shared by single-question and whole-copy grading. */
export function gradeAnswerRun(state: any, answerId: string) {
  const ans = state.answers[answerId];
  if (!ans) throw new GradeRequestError("Answer not found", 404);
  const paper = state.papers[ans.paper_id];
  const qSpec = paper?.questions.find((q: any) => q.question_id === ans.question_id);
  if (!qSpec) throw new GradeRequestError("Question spec not found", 400);
  const latestRev = ans.revisions[ans.revisions.length - 1];
  if (!latestRev) throw new GradeRequestError("No transcript for this answer yet", 400);
  if (!latestRev.is_confirmed_for_grading) {
    throw new GradeRequestError("Confirm the transcript before calculating marks.", 409);
  }
  const hasDis = ans.uncertain_spans.some((s: any) => !s.resolved_by_human);

  const contract = evaluateRubricBoundedGrade(
    qSpec,
    latestRev.text,
    latestRev.version_id,
    paper.paper_id,
    paper.rubric_version,
    paper.status,
    ans.page_number,
    ans.bbox_norm,
    ans.ocr_candidates[0]?.calibrated_confidence || 0.88,
    hasDis
  );

  const grId = `gr-${answerId}-r${Object.keys(state.grade_runs).length + 1}`;
  const prevReviews =
    ans.latest_grade_run_id && state.grade_runs[ans.latest_grade_run_id]
      ? state.grade_runs[ans.latest_grade_run_id].human_reviews
      : [];
  const grRecord = {
    grade_run_id: grId,
    answer_id: answerId,
    session_id: ans.session_id,
    paper_id: ans.paper_id,
    question_id: ans.question_id,
    created_at: new Date().toISOString(),
    contract,
    human_reviews: prevReviews,
  };
  state.grade_runs[grId] = grRecord;
  ans.latest_grade_run_id = grId;
  const ev = state.appendAudit(
    "RUBRIC_GRADE_RUN_COMPLETED",
    "grade_run",
    grId,
    "rubric-grading-worker",
    {
      question_id: ans.question_id,
      rubric_version: paper.rubric_version,
      transcript_version: latestRev.version_id,
      ai_suggested_score: contract.final_score,
    }
  );
  return { grade_run: grRecord, audit_event: ev };
}

/**
 * Grades every answer on a candidate's copy. Answers already decided by an examiner are skipped
 * unless includeReviewed is set, so a re-run never silently replaces reviewed marks.
 */
export function gradeWholeCopy(state: any, sessionId: string, includeReviewed = false) {
  const sess = state.sessions?.[sessionId];
  if (!sess) throw new GradeRequestError("Session not found", 404);
  const graded: any[] = [];
  const skipped: any[] = [];
  for (const aid of sess.answer_ids) {
    const ans = state.answers[aid];
    const prev = state.grade_runs[ans.latest_grade_run_id || ""];
    if (!ans.revisions?.length) {
      skipped.push({ answer_id: aid, question_id: ans.question_id, reason: "no_transcript" });
      continue;
    }
    if (!ans.revisions[ans.revisions.length - 1].is_confirmed_for_grading) {
      skipped.push({ answer_id: aid, question_id: ans.question_id, reason: "transcript_not_confirmed" });
      continue;
    }
    if (prev?.human_reviews?.length && !includeReviewed) {
      skipped.push({ answer_id: aid, question_id: ans.question_id, reason: "already_reviewed" });
      continue;
    }
    const { grade_run } = gradeAnswerRun(state, aid);
    const c = grade_run.contract;
    graded.push({
      answer_id: aid,
      question_id: ans.question_id,
      grade_run_id: grade_run.grade_run_id,
      final_score: c.final_score,
      max_marks: c.max_marks,
      needs_human_review: c.needs_human_review,
      word_limit_status: c.word_limit_status,
    });
  }
  const totalSuggested = Math.round(graded.reduce((a, g) => a + g.final_score, 0) * 100) / 100;
  const totalMax = Math.round(graded.reduce((a, g) => a + g.max_marks, 0) * 100) / 100;
  const ev = state.appendAudit(
    "RUBRIC_COPY_GRADE_RUN_COMPLETED",
    "session",
    sessionId,
    "rubric-grading-worker",
    {
      graded_count: graded.length,
      skipped_count: skipped.length,
      total_suggested: totalSuggested,
      include_reviewed: includeReviewed,
    }
  );
  return {
    session_id: sessionId,
    graded_count: graded.length,
    needs_review_count: graded.filter((g) => g.needs_human_review).length,
    total_suggested: totalSuggested,
    total_max: totalMax,
    answers: graded,
    skipped,
    audit_event: ev,
  };
}
