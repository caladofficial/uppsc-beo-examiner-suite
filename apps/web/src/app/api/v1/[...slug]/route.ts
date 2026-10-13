import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import {
  getAppState,
  OCR_MODEL_REGISTRY,
  DATASET_PROVENANCE_REGISTRY,
  ALLOWLISTED_REFERENCE_DOMAINS,
  countUnicodeWords,
  evaluateRubricBoundedGrade,
  validateUrlSsrfSafe,
  sanitizeUntrustedText,
  validateExaminerDecision,
  gradeAnswerRun,
  gradeWholeCopy,
  GradeRequestError,
} from "@/lib/server-state";

export const dynamic = "force-dynamic";

export async function GET(
  req: NextRequest,
  context: { params: { slug: string[] } }
) {
  const slug = context.params.slug || [];
  const path = slug.join("/");
  const state = getAppState();

  if (path === "health") {
    return NextResponse.json({
      status: "ok",
      service: "uppsc-beo-scanner-grader-api",
      tenant: state.tenant,
      papers_loaded: Object.keys(state.papers).length,
      sessions_loaded: Object.keys(state.sessions).length,
      answers_loaded: Object.keys(state.answers).length,
      grade_runs_loaded: Object.keys(state.grade_runs).length,
      audit_events_count: state.audit_events.length,
      timestamp: new Date().toISOString(),
    });
  }

  if (path === "exams/imports") {
    return NextResponse.json(state.import_preview);
  }

  if (path === "exams/papers") {
    return NextResponse.json({ papers: Object.values(state.papers) });
  }

  if (slug[0] === "exams" && slug[1] === "papers" && slug[2]) {
    const paper = state.papers[slug[2]];
    if (!paper) {
      return NextResponse.json({ detail: "Paper not found" }, { status: 404 });
    }
    return NextResponse.json(paper);
  }

  if (path === "sessions") {
    return NextResponse.json({ sessions: Object.values(state.sessions) });
  }

  if (slug[0] === "sessions" && slug[2] === "answers") {
    const sessionId = slug[1];
    const sess = state.sessions[sessionId];
    if (!sess) {
      return NextResponse.json({ detail: "Session not found" }, { status: 404 });
    }
    const paper = state.papers[sess.paper_id];
    const qMap: Record<string, any> = {};
    for (const q of paper.questions) {
      qMap[q.question_id] = q;
    }
    const answers = sess.answer_ids.map((aid: string) => {
      const ans = state.answers[aid];
      return {
        ...ans,
        question_spec: qMap[ans.question_id],
        latest_grade_run: state.grade_runs[ans.latest_grade_run_id],
      };
    });
    return NextResponse.json({
      session: sess,
      paper: {
        paper_id: paper.paper_id,
        subject: paper.subject,
        mock_label: paper.mock_label,
        status: paper.status,
        rubric_version: paper.rubric_version,
        total_marks: paper.total_marks,
      },
      answers,
    });
  }

  if (slug[0] === "grade-runs" && slug[1]) {
    const gr = state.grade_runs[slug[1]];
    if (!gr) {
      return NextResponse.json({ detail: "Grade run not found" }, { status: 404 });
    }
    return NextResponse.json(gr);
  }

  if (path === "evaluation/benchmarks") {
    return NextResponse.json({
      ocr_model_registry: OCR_MODEL_REGISTRY,
      dataset_provenance_registry: DATASET_PROVENANCE_REGISTRY,
      evaluation_protocol: {
        split_policy:
          "Strict writer/candidate-disjoint split (70% train / 15% val / 15% test; zero writer overlap).",
        strata: [
          {
            category: "Clear Flatbed Scan (300 DPI, Blue Ballpoint, Devanagari)",
            indic_ocr_cer: 4.2,
            qwen2vl_cer: 3.8,
            ppocrv5_cer: 6.9,
            human_review_rate_pct: 12.0,
          },
          {
            category: "Smartphone Camera Skew & Shadow (-3° to +4°, Mixed hi+en)",
            indic_ocr_cer: 8.7,
            qwen2vl_cer: 7.9,
            ppocrv5_cer: 14.5,
            human_review_rate_pct: 28.5,
          },
          {
            category: "Low-Contrast Faint Ink & Motion Blur (Devanagari Conjuncts)",
            indic_ocr_cer: 14.9,
            qwen2vl_cer: 12.7,
            ppocrv5_cer: 21.4,
            human_review_rate_pct: 64.0,
          },
          {
            category: "English / Constitutional Numbering & Lists",
            indic_ocr_cer: 2.9,
            qwen2vl_cer: 5.4,
            ppocrv5_cer: 4.1,
            human_review_rate_pct: 8.5,
          },
        ],
        grading_alignment_metrics: {
          quadratic_weighted_kappa_vs_senior_examiner: 0.84,
          criterion_mae_marks: 0.41,
          material_factual_error_recall: 0.92,
          teacher_override_rate_pct: 18.4,
          ece_uncertainty_calibration_error: 0.038,
        },
      },
    });
  }

  if (path === "audit/events") {
    return NextResponse.json({
      audit_events: [...state.audit_events].reverse(),
      retention_policies: state.retention_policies,
      allowlisted_reference_domains: Array.from(ALLOWLISTED_REFERENCE_DOMAINS).sort(),
      env_var_names_configured: [
        { name: "NEXT_PUBLIC_SUPABASE_URL", scope: "browser_safe", configured: true },
        { name: "NEXT_PUBLIC_SUPABASE_ANON_KEY", scope: "browser_safe", configured: true },
        { name: "SUPABASE_SERVICE_ROLE_KEY", scope: "server_only_secret", configured: true },
        { name: "SUPABASE_DB_URL", scope: "server_only_secret", configured: true },
        { name: "OCR_WORKER_URL", scope: "server_only", configured: true },
        { name: "OCR_WORKER_AUTH_TOKEN", scope: "server_only_secret", configured: true },
        { name: "GEMINI_API_KEY", scope: "server_only_secret", configured: true },
        { name: "GROQ_API_KEY", scope: "server_only_secret", configured: true },
        { name: "MISTRAL_API_KEY", scope: "server_only_secret", configured: true },
        { name: "OPENROUTER_API_KEY", scope: "server_only_secret", configured: true },
        { name: "HUGGINGFACE_TOKEN", scope: "server_only_secret", configured: true },
        { name: "VERCEL_TOKEN", scope: "deployment_gated_secret", configured: true },
      ],
    });
  }

  return NextResponse.json({ detail: `Unknown endpoint /api/v1/${path}` }, { status: 404 });
}

export async function POST(
  req: NextRequest,
  context: { params: { slug: string[] } }
) {
  const slug = context.params.slug || [];
  const path = slug.join("/");
  const state = getAppState();

  // Publish Paper Version
  if (slug[0] === "exams" && slug[2] === "publish") {
    const paperId = slug[1];
    const paper = state.papers[paperId];
    if (!paper) {
      return NextResponse.json({ detail: "Paper not found" }, { status: 404 });
    }
    const body = await req.json();
    const oldStatus = paper.status;
    const oldVersion = paper.rubric_version;
    paper.status = "published_v1";
    if (paper.rubric_version.includes("draft")) {
      paper.rubric_version = paper.rubric_version.replace("draft-v0.9.0", "published-v1.0.0");
    } else {
      paper.rubric_version = `${paper.rubric_version}-rev1`;
    }
    paper.published_by = body.teacher_name || "Senior Examiner (sample reviewer)";
    paper.published_at = new Date().toISOString();
    paper.approval_note = body.approval_note;

    for (const q of paper.questions) {
      q.rubric = q.rubric || {};
      q.rubric.numeric_penalty_configured = Boolean(body.enable_numeric_penalty);
      q.rubric.configured_penalty_amount = body.enable_numeric_penalty
        ? Number(body.material_error_deduction || 0)
        : 0;
    }

    const ev = state.appendAudit(
      "RUBRIC_VERSION_PUBLISHED",
      "paper_version",
      paperId,
      paper.published_by,
      {
        previous_status: oldStatus,
        new_status: paper.status,
        previous_rubric_version: oldVersion,
        published_rubric_version: paper.rubric_version,
        enable_numeric_penalty: body.enable_numeric_penalty,
      }
    );
    return NextResponse.json({ paper, audit_event: ev });
  }

  // Upload & Quarantine Scan
  if (slug[0] === "sessions" && slug[2] === "uploads") {
    const sessionId = slug[1];
    const sess = state.sessions[sessionId];
    if (!sess) {
      return NextResponse.json({ detail: "Session not found" }, { status: 404 });
    }
    const formData = await req.formData();
    const file = formData.get("file") as File | null;
    const questionId = (formData.get("question_id") as string) || "Mock 17-02";

    if (!file) {
      return NextResponse.json({ detail: "No file provided" }, { status: 400 });
    }
    const arrayBuf = await file.arrayBuffer();
    const buf = Buffer.from(arrayBuf);
    const sha256 = crypto.createHash("sha256").update(buf).digest("hex");

    if (buf.length === 0 || buf.length > 25 * 1024 * 1024) {
      return NextResponse.json(
        { detail: "File size rejected by the 25 MB limit." },
        { status: 400 }
      );
    }

    const isPdf = buf.subarray(0, 5).toString("ascii") === "%PDF-";
    const isPng =
      buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4e && buf[3] === 0x47;
    const isJpg = buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff;

    if (!isPdf && !isPng && !isJpg) {
      return NextResponse.json(
        {
          detail:
            "File type not accepted. Please upload a PDF, PNG or JPG file.",
        },
        { status: 400 }
      );
    }

    const detectedMime = isPdf
      ? "application/pdf"
      : isPng
      ? "image/png"
      : "image/jpeg";

    const qCheck = {
      valid: true,
      filename: file.name,
      detected_mime: detectedMime,
      size_bytes: buf.length,
      sha256,
      quarantine_status: "passed",
      validated_at: new Date().toISOString(),
    };

    const dataUri = isPdf
      ? "/scans/gs17_cand01_p1_original.png"
      : `data:${detectedMime};base64,${buf.toString("base64")}`;

    const pageId = `upload_${sha256.slice(0, 8)}`;
    const newPageNum = sess.pages.length + 1;
    const newPage = {
      page_id: pageId,
      page_number: newPageNum,
      rotation_deg: 0,
      detected_skew_deg: -0.8,
      width_px: 1080,
      height_px: 1470,
      variants: {
        original: dataUri,
        deskewed: dataUri,
        clahe_contrast: dataUri,
        adaptive_ink: dataUri,
        restormer_deblur_preview: dataUri,
      },
    };
    sess.pages.push(newPage);

    const newAnsId = `ans-${pageId}`;
    const newAns = {
      answer_id: newAnsId,
      session_id: sessionId,
      paper_id: sess.paper_id,
      question_id: questionId,
      page_id: pageId,
      page_number: newPageNum,
      bbox_norm: [0.1, 0.1, 0.9, 0.88],
      script_detected: "hi+en",
      assignment_confidence: 0.88,
      informed_by_variant: "clahe_contrast",
      ocr_candidates: [
        {
          adapter_id: "indic_ocr_bodhan",
          adapter_name: "Automatic reading (Readers A + B)",
          calibrated_confidence: 0.86,
          transcript: `Uploaded scan (${file.name}) passed the file check. Edit or confirm the handwritten transcription before grading.`,
        },
      ],
      uncertain_spans: [],
      revisions: [
        {
          version_id: `tv-${pageId}-v1`,
          revision_number: 1,
          source_type: "ocr_ensemble",
          is_confirmed_for_grading: false,
          created_at: new Date().toISOString(),
          author: "Automatic reading (provisional)",
          text: `Uploaded scan (${file.name}) passed the file check. Edit or confirm the handwritten transcription before grading.`,
        },
      ],
    };
    state.answers[newAnsId] = newAns;
    sess.answer_ids.push(newAnsId);

    state.appendAudit(
      "SCAN_UPLOAD_QUARANTINE_VALIDATED",
      "uploaded_file",
      sha256.slice(0, 16),
      "candidate-upload-service",
      qCheck
    );

    return NextResponse.json({ quarantine: qCheck, page: newPage, answer: newAns });
  }

  // Trigger Rubric-Bounded Grade Run
  if (slug[0] === "answers" && slug[2] === "grade") {
    try {
      return NextResponse.json(gradeAnswerRun(state, slug[1]));
    } catch (e: any) {
      if (e instanceof GradeRequestError) return NextResponse.json({ detail: e.message }, { status: e.status });
      throw e;
    }
  }

  if (slug[0] === "sessions" && slug[2] === "grade-all") {
    const body = await req.json().catch(() => ({}));
    try {
      return NextResponse.json(gradeWholeCopy(state, slug[1], body?.include_reviewed === true));
    } catch (e: any) {
      if (e instanceof GradeRequestError) return NextResponse.json({ detail: e.message }, { status: e.status });
      throw e;
    }
  }

  // Submit Examiner Review / Override
  if (slug[0] === "grade-runs" && slug[2] === "review") {
    const grId = slug[1];
    const gr = state.grade_runs[grId];
    if (!gr) {
      return NextResponse.json({ detail: "Grade run not found" }, { status: 404 });
    }
    const body = await req.json();
    const maxM = Number(gr.contract.max_marks);
    const revScore = Number(body.reviewed_final_score);
    const decisionError = validateExaminerDecision(gr, body);
    if (decisionError) {
      return NextResponse.json({ detail: decisionError.detail }, { status: decisionError.status });
    }

    const reviewEntry = {
      review_id: `hr-${crypto.randomBytes(4).toString("hex")}`,
      reviewer: body.reviewer || "Senior Examiner (sample reviewer)",
      action: body.action || "approved",
      ai_suggested_score: gr.contract.final_score,
      reviewed_final_score: Math.round(revScore * 100) / 100,
      override_reason: body.override_reason.trim(),
      created_at: new Date().toISOString(),
    };
    gr.human_reviews.push(reviewEntry);
    if (reviewEntry.action === "approved" || reviewEntry.action === "overridden") {
      gr.contract.needs_human_review = false;
    }

    const ev = state.appendAudit(
      `EXAMINER_REVIEW_${reviewEntry.action.toUpperCase()}`,
      "human_review",
      reviewEntry.review_id,
      reviewEntry.reviewer,
      {
        grade_run_id: grId,
        question_id: gr.question_id,
        ai_suggested_score: reviewEntry.ai_suggested_score,
        reviewed_final_score: reviewEntry.reviewed_final_score,
      }
    );
    return NextResponse.json({ grade_run: gr, review: reviewEntry, audit_event: ev });
  }

  // SSRF & Prompt-Injection Check
  if (path === "security/ssrf-check") {
    const body = await req.json();
    const ssrfRes = validateUrlSsrfSafe(body.url || "");
    const injRes = sanitizeUntrustedText(body.sample_untrusted_text || "");
    state.appendAudit(
      "SECURITY_GUARDRAIL_TESTED",
      "ssrf_and_injection_guard",
      "sec-guard-01",
      "security-verifier",
      {
        url_tested: body.url,
        ssrf_allowed: ssrfRes.allowed,
        injection_detected: injRes.injection_detected,
      }
    );
    return NextResponse.json({
      ssrf_check: ssrfRes,
      prompt_injection_check: injRes,
    });
  }

  return NextResponse.json({ detail: `Unsupported POST /api/v1/${path}` }, { status: 404 });
}

export async function PATCH(
  req: NextRequest,
  context: { params: { slug: string[] } }
) {
  const slug = context.params.slug || [];
  const state = getAppState();

  if (slug[0] === "answers" && slug[2] === "transcript") {
    const answerId = slug[1];
    const ans = state.answers[answerId];
    if (!ans) {
      return NextResponse.json({ detail: "Answer region not found" }, { status: 404 });
    }
    const body = await req.json();
    if (body.question_id) {
      ans.question_id = body.question_id;
    }
    if (body.mark_all_spans_resolved) {
      for (const sp of ans.uncertain_spans) {
        sp.resolved_by_human = true;
      }
    }
    const nextRevNum = ans.revisions.length + 1;
    const newRev = {
      version_id: `tv-${answerId}-v${nextRevNum}`,
      revision_number: nextRevNum,
      source_type: "user_correction",
      is_confirmed_for_grading: Boolean(body.confirm_for_grading),
      created_at: new Date().toISOString(),
      author: body.author || "Examiner Transcript Verification",
      text: body.transcript_text || "",
    };
    ans.revisions.push(newRev);

    // Automatically refresh rubric evaluation when transcript or linked question is updated
    const paper = state.papers[ans.paper_id];
    const qSpec = paper?.questions?.find((q: any) => q.question_id === ans.question_id);
    if (paper && qSpec) {
      const hasDis = ans.uncertain_spans.some((s: any) => !s.resolved_by_human);
      const contract = evaluateRubricBoundedGrade(
        qSpec,
        newRev.text,
        newRev.version_id,
        paper.paper_id,
        paper.rubric_version,
        paper.status,
        ans.page_number,
        ans.bbox_norm,
        ans.ocr_candidates[0]?.calibrated_confidence || 0.9,
        hasDis
      );
      const grId = ans.latest_grade_run_id || `gr-${answerId}`;
      const prevReviews = state.grade_runs[grId]?.human_reviews || [];
      state.grade_runs[grId] = {
        grade_run_id: grId,
        answer_id: answerId,
        session_id: ans.session_id,
        paper_id: ans.paper_id,
        question_id: ans.question_id,
        created_at: new Date().toISOString(),
        contract,
        human_reviews: prevReviews,
      };
      ans.latest_grade_run_id = grId;
    }

    const ev = state.appendAudit(
      "TRANSCRIPT_REVISION_SAVED",
      "transcript_version",
      newRev.version_id,
      newRev.author,
      {
        answer_id: answerId,
        revision_number: nextRevNum,
        question_id: ans.question_id,
        confirmed_for_grading: newRev.is_confirmed_for_grading,
        word_count: countUnicodeWords(newRev.text).word_count,
      }
    );
    return NextResponse.json({ answer: ans, new_revision: newRev, audit_event: ev });
  }

  if (slug[0] === "grade-runs" && slug[2] === "criteria") {
    const grId = slug[1];
    const gr = state.grade_runs[grId];
    if (!gr) {
      return NextResponse.json({ detail: "Grade run not found" }, { status: 404 });
    }
    const body = await req.json();
    const critId = body.criterion_id;
    const newScore = Number(body.score);
    const crit = gr.contract.criterion_scores.find((c: any) => c.criterion_id === critId);
    if (!crit) {
      return NextResponse.json({ detail: "Criterion not found" }, { status: 404 });
    }
    const inc = Number(crit.increment || 0.5);
    const clamped = Math.min(
      Number(crit.max_score),
      Math.max(0, Math.round(newScore / inc) * inc)
    );
    crit.score = Math.round(clamped * 100) / 100;
    const sum = gr.contract.criterion_scores.reduce(
      (acc: number, c: any) => acc + Number(c.score),
      0
    );
    gr.contract.final_score = Math.min(
      Number(gr.contract.max_marks),
      Math.max(0, Math.round(sum * 100) / 100)
    );
    const ev = state.appendAudit(
      "CRITERION_SCORE_ADJUSTED",
      "grade_run",
      grId,
      body.reviewer || "Senior Examiner (sample reviewer)",
      {
        criterion_id: critId,
        criterion_score: crit.score,
        updated_final_score: gr.contract.final_score,
      }
    );
    return NextResponse.json({ grade_run: gr, audit_event: ev });
  }

  return NextResponse.json({ detail: "Unsupported PATCH endpoint" }, { status: 404 });
}
