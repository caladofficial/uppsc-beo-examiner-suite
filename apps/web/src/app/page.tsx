"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { apiFetch, resolveAssetUrl } from "@/lib/client-api";
import { LANG_STORAGE_KEY, Lang, Key, makeT } from "@/lib/i18n";

type Tab = "papers" | "sheets" | "handwriting" | "marks" | "report";

const TAB_IDS: Tab[] = ["papers", "sheets", "handwriting", "marks", "report"];

const SESSIONS = [
  { id: "sess-gs17-cand8841", label: "CAND-UP-8841 · GS Mock 17", paper: "uppsc-beo-mains-gs-mock-17-v1" },
  { id: "sess-hi16-cand9204", label: "CAND-UP-9204 · Hindi Mock 16", paper: "uppsc-beo-mains-hindi-mock-16-draft" },
];

const VARIANT_IDS = ["original", "deskewed", "clahe_contrast", "adaptive_ink", "restormer_deblur_preview"];
const VARIANT_KEYS: Record<string, Key> = {
  original: "variant.original" as Key,
  deskewed: "variant.deskewed" as Key,
  clahe_contrast: "variant.clahe" as Key,
  adaptive_ink: "variant.ink" as Key,
  restormer_deblur_preview: "variant.sharp" as Key,
};
const ENHANCED = new Set(["adaptive_ink", "restormer_deblur_preview"]);

const EXAMINER = "Senior Examiner (sample reviewer)";
const AUTHOR = "Examiner (sample reviewer)";
const UNREADABLE = "[UNREADABLE_SPAN]";
const CANNOT_READ = "[cannot read]";
const CONFIDENCE_FLAG = 0.7;
const SEVERITY_KEYS: Record<string, { key: Key; tone: "alert" | "warn" | "neutral" }> = {
  critical: { key: "sev.critical" as Key, tone: "alert" },
  high: { key: "sev.high" as Key, tone: "alert" },
  medium: { key: "sev.medium" as Key, tone: "warn" },
  low: { key: "sev.low" as Key, tone: "neutral" },
};

// ---------- presentational helpers (module level) ----------

function Badge({ tone = "neutral", children }: { tone?: "ok" | "warn" | "alert" | "neutral"; children: React.ReactNode }) {
  const cls = {
    ok: "bg-[#484A47] text-[#FAF6F3]",
    warn: "bg-[#E88873] text-[#484A47]",
    alert: "bg-[#A37774] text-[#FAF6F3]",
    neutral: "bg-[#E0AC9D]/40 text-[#484A47]",
  }[tone];
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>{children}</span>;
}

function LangSwitch({ lang, onChange, label }: { lang: Lang; onChange: (l: Lang) => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-md border border-[#E0AC9D]/50 p-0.5">
      {(["en", "hi"] as Lang[]).map((l) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-pressed={lang === l}
          onClick={() => onChange(l)}
          className={`rounded px-2.5 py-1 text-xs font-semibold transition ${
            lang === l ? "bg-[#E88873] text-[#484A47]" : "text-[#E0AC9D] hover:text-white"
          }`}
        >
          {l === "en" ? "English" : "हिन्दी"}
        </button>
      ))}
    </div>
  );
}

const CARD = "rounded-xl border border-[#E0AC9D]/60 bg-white p-5 shadow-sm";
const INPUT =
  "w-full rounded-lg border border-[#A37774]/60 bg-white px-3 py-2 text-sm text-[#484A47] focus:outline-none focus:ring-2 focus:ring-[#E88873]/50";
const BTN =
  "inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50";
const BTN_PRIMARY = `${BTN} bg-[#E88873] text-[#484A47] hover:bg-[#E0AC9D]`;
const BTN_DARK = `${BTN} bg-[#484A47] text-[#FAF6F3] hover:bg-[#5C6D70]`;
const BTN_GHOST = `${BTN} border border-[#A37774] bg-white text-[#484A47] hover:bg-[#E0AC9D]/30`;
const CHIP = "rounded-full px-3 py-1 text-xs font-semibold transition";
const CHIP_ON = `${CHIP} bg-[#484A47] text-[#FAF6F3]`;
const CHIP_OFF = `${CHIP} border border-[#A37774]/50 bg-white text-[#484A47] hover:bg-[#E0AC9D]/30`;

// ---------- data helpers ----------

function qText(q: any) {
  return {
    hi: q?.canonical_question?.hi || q?.prompt_hi || "",
    en: q?.canonical_question?.en || q?.prompt_en || "",
  };
}
function txt(x: any): string {
  if (x == null) return "";
  if (typeof x === "string") return x;
  return x.text ?? x.point ?? x.title ?? x.label ?? x.claim ?? x.en ?? x.hi ?? x.source_id ?? "";
}
function latestText(ans: any): string {
  const revs = ans?.revisions || [];
  return revs.length ? revs[revs.length - 1].text : "";
}
function pct(x: any) {
  return `${Math.round(Number(x || 0) * 100)}%`;
}
function criteriaOf(q: any): any[] {
  return q?.rubric?.criteria || q?.criteria || [];
}
function openItems(a: any) {
  return (a?.uncertain_spans || []).filter((s: any) => !s.resolved_by_human).length;
}

export default function ExaminerWorkspace() {
  const [lang, setLang] = useState<Lang>("en");
  const t = useMemo(() => makeT(lang), [lang]);

  const [tab, setTab] = useState<Tab>("papers");
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: "ok" | "error" } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const notify = (message: string, type: "ok" | "error" = "ok") => {
    setToast({ message, type });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4500);
  };

  // language: read the saved choice after mount, keep <html lang> in step
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(LANG_STORAGE_KEY);
      if (saved === "hi" || saved === "en") setLang(saved);
    } catch {
      /* storage unavailable: keep English */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      window.localStorage.setItem(LANG_STORAGE_KEY, lang);
    } catch {
      /* ignore */
    }
  }, [lang]);

  // server data
  const [importData, setImportData] = useState<any>(null);
  const [sessionData, setSessionData] = useState<any>(null);
  const [auditData, setAuditData] = useState<any>(null);

  // selection
  const [sessionId, setSessionId] = useState(SESSIONS[0].id);
  const [paperId, setPaperId] = useState(SESSIONS[0].paper);
  const [answerId, setAnswerId] = useState("");
  const [viewPageId, setViewPageId] = useState("");
  const [variant, setVariant] = useState("original");

  // papers
  const [query, setQuery] = useState("");
  const [sectionChip, setSectionChip] = useState("ALL");
  const [qid, setQid] = useState("");
  const [approvalNote, setApprovalNote] = useState("Question wording checked against the PDF; marks capped per criterion.");
  const [penaltyOn, setPenaltyOn] = useState(false);
  const [penaltyAmount, setPenaltyAmount] = useState(0.5);
  const [publishing, setPublishing] = useState(false);

  // answer sheets
  const [uploadQid, setUploadQid] = useState("");
  const [uploading, setUploading] = useState(false);
  const [lastCheck, setLastCheck] = useState<any>(null);

  // handwriting
  const [zoom, setZoom] = useState(100);
  const [rotation, setRotation] = useState(0);
  const [draft, setDraft] = useState("");
  const [linkedQid, setLinkedQid] = useState("");
  const [saving, setSaving] = useState(false);

  // marks
  const [grading, setGrading] = useState(false);
  const [criterionInputs, setCriterionInputs] = useState<Record<string, string>>({});
  const [reviewAction, setReviewAction] = useState("approved");
  const [reviewScore, setReviewScore] = useState("");
  const [reviewReason, setReviewReason] = useState("");
  const [submittingReview, setSubmittingReview] = useState(false);

  // report
  const [authorised, setAuthorised] = useState(false);

  // ---------- loading ----------

  const applyAnswer = (ans: any) => {
    setAnswerId(ans.answer_id);
    setViewPageId(ans.page_id);
    setDraft(latestText(ans));
    setLinkedQid(ans.question_id);
    setCriterionInputs({});
    setReviewReason("");
    setReviewAction("approved");
    setReviewScore(String(ans.latest_grade_run?.contract?.final_score ?? ""));
  };

  const loadAll = async (sid: string, opts: { answerId?: string; resetDraft?: boolean } = {}) => {
    try {
      const [impRes, sessRes, audRes] = await Promise.all([
        apiFetch("/api/v1/exams/imports"),
        apiFetch(`/api/v1/sessions/${sid}/answers`),
        apiFetch("/api/v1/audit/events"),
      ]);
      const imp = await impRes.json();
      const sess = await sessRes.json();
      const aud = await audRes.json();
      setImportData(imp);
      setSessionData(sess);
      setAuditData(aud);
      const list: any[] = sess.answers || [];
      const ans = list.find((a) => a.answer_id === opts.answerId) || list[0];
      if (ans) {
        if (opts.resetDraft || !opts.answerId) applyAnswer(ans);
        else setAnswerId(ans.answer_id);
      }
    } catch (err) {
      console.error(err);
      notify(makeT(lang)("app.loadError"), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll(sessionId, { resetDraft: true });
    // initial load only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------- derived data ----------

  const papers: any[] = importData?.papers || [];
  const paper = papers.find((p) => p.paper_id === paperId) || papers[0];
  const warnings: any[] = importData?.import_warnings || [];
  const answers: any[] = sessionData?.answers || [];
  const answer = answers.find((a) => a.answer_id === answerId) || answers[0];
  const sessionPages: any[] = sessionData?.session?.pages || [];
  const viewPage = sessionPages.find((p) => p.page_id === viewPageId) || sessionPages[0];
  const scanPage = sessionPages.find((p) => p.page_id === answer?.page_id) || sessionPages[0];
  const paperQuestions: any[] = paper?.questions || [];

  useEffect(() => {
    setQid(paperQuestions[0]?.question_id || "");
    setUploadQid(paperQuestions[0]?.question_id || "");
    setSectionChip("ALL");
    setQuery("");
    // reset only when the paper changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paper?.paper_id]);

  const sectionKeys = useMemo(
    () => Array.from(new Set(paperQuestions.map((q) => q.section || q.section_code).filter(Boolean))) as string[],
    [paper?.paper_id, importData] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const questions = useMemo(() => {
    const term = query.trim().toLowerCase();
    return paperQuestions.filter((q) => {
      const sec = q.section || q.section_code;
      if (sectionChip !== "ALL" && sec !== sectionChip) return false;
      if (!term) return true;
      const tx = qText(q);
      return [q.question_id, tx.hi, tx.en, q.topic].some((v) => String(v || "").toLowerCase().includes(term));
    });
  }, [paper?.paper_id, query, sectionChip, importData]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectedQ = paperQuestions.find((q) => q.question_id === qid) || questions[0] || null;

  const detail = useMemo(() => {
    if (!selectedQ) return null;
    const outline = selectedQ.answer_outline || {};
    return {
      text: qText(selectedQ),
      criteria: criteriaOf(selectedQ),
      anchor: selectedQ.rubric?.scoring_anchor || "",
      points: Array.isArray(outline.expected_points) ? outline.expected_points : Array.isArray(outline) ? outline : [],
      refs: Array.isArray(outline.reference_sources) ? outline.reference_sources : [],
      source: selectedQ.source_reference || {},
    };
  }, [selectedQ]);

  // ---------- actions ----------

  const switchSession = (sid: string) => {
    const s = SESSIONS.find((x) => x.id === sid);
    if (!s) return;
    setSessionId(sid);
    setPaperId(s.paper);
    setLastCheck(null);
    loadAll(sid, { resetDraft: true });
  };

  const openAnswer = (a: any, goTo?: Tab) => {
    applyAnswer(a);
    if (goTo) setTab(goTo);
  };

  const publish = async () => {
    if (!paper) return;
    setPublishing(true);
    try {
      const res = await apiFetch(`/api/v1/exams/${paper.paper_id}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          teacher_name: EXAMINER,
          enable_numeric_penalty: penaltyOn,
          material_error_deduction: penaltyOn ? penaltyAmount : 0,
          word_limit_deduction: 0,
          approval_note: approvalNote,
        }),
      });
      if (!res.ok) throw new Error(t("publish.failed"));
      await loadAll(sessionId, { answerId: answer?.answer_id });
      notify(t("publish.done", { m: paper.mock_label }));
    } catch (e: any) {
      notify(e.message, "error");
    } finally {
      setPublishing(false);
    }
  };

  const saveTranscript = async (confirm: boolean) => {
    if (!answer) return;
    if (!draft.trim()) {
      notify(t("hw.emptyTranscript"), "error");
      return;
    }
    setSaving(true);
    try {
      const res = await apiFetch(`/api/v1/answers/${answer.answer_id}/transcript`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript_text: draft,
          question_id: linkedQid,
          confirm_for_grading: confirm,
          mark_all_spans_resolved: confirm,
          author: AUTHOR,
        }),
      });
      if (!res.ok) throw new Error(t("hw.revisionFailed"));
      await loadAll(sessionId, { answerId: answer.answer_id, resetDraft: true });
      notify(confirm ? t("hw.confirmedSaved") : t("hw.draftSaved"));
    } catch (e: any) {
      notify(e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const applyAlternative = (span: any, text: string) => {
    const replacement = text === UNREADABLE ? CANNOT_READ : text;
    if (!draft.includes(span.current_text)) {
      notify(t("hw.phraseMissing"), "error");
      return;
    }
    setDraft(draft.replace(span.current_text, replacement));
  };

  const runGrade = async () => {
    if (!answer) return;
    setGrading(true);
    try {
      const res = await apiFetch(`/api/v1/answers/${answer.answer_id}/grade`, { method: "POST" });
      if (!res.ok) throw new Error(t("marks.calcFailed"));
      const data = await res.json();
      await loadAll(sessionId, { answerId: answer.answer_id });
      setReviewScore(String(data.grade_run.contract.final_score));
      notify(t("marks.calcDone", { s: data.grade_run.contract.final_score, m: data.grade_run.contract.max_marks }));
    } catch (e: any) {
      notify(e.message, "error");
    } finally {
      setGrading(false);
    }
  };

  const setCriterion = async (criterionId: string, scoreText: string) => {
    const gr = answer?.latest_grade_run;
    if (!gr) return;
    try {
      const res = await apiFetch(`/api/v1/grade-runs/${gr.grade_run_id}/criteria`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ criterion_id: criterionId, score: Number(scoreText), reviewer: EXAMINER }),
      });
      if (!res.ok) throw new Error(t("marks.outOfRange"));
      await loadAll(sessionId, { answerId: answer.answer_id });
      setCriterionInputs((prev) => {
        const next = { ...prev };
        delete next[criterionId];
        return next;
      });
      notify(t("marks.updated"));
    } catch (e: any) {
      notify(e.message, "error");
    }
  };

  const submitDecision = async () => {
    const gr = answer?.latest_grade_run;
    if (!gr) return;
    if (reviewAction === "overridden" && !reviewReason.trim()) {
      notify(t("marks.enterReason"), "error");
      return;
    }
    setSubmittingReview(true);
    try {
      const res = await apiFetch(`/api/v1/grade-runs/${gr.grade_run_id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reviewer: EXAMINER,
          action: reviewAction,
          reviewed_final_score: Number(reviewScore),
          override_reason: reviewReason,
        }),
      });
      if (!res.ok) throw new Error(t("marks.decisionFailed"));
      await loadAll(sessionId, { answerId: answer.answer_id });
      setReviewReason("");
      notify(t("marks.decisionSaved"));
    } catch (e: any) {
      notify(e.message, "error");
    } finally {
      setSubmittingReview(false);
    }
  };

  const uploadSheet = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 25 * 1024 * 1024) {
      notify(t("sheets.tooLarge"), "error");
      return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("question_id", uploadQid);
      const res = await apiFetch(`/api/v1/sessions/${sessionId}/uploads`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(t("sheets.rejected"));
      setLastCheck(data.quarantine);
      await loadAll(sessionId, { answerId: data.answer.answer_id, resetDraft: true });
      notify(t("sheets.accepted", { type: mimeLabel(data.quarantine.detected_mime) }));
    } catch (err: any) {
      notify(err.message || t("sheets.uploadFailed"), "error");
    } finally {
      setUploading(false);
    }
  };

  function reportRow(a: any) {
    const gr = a.latest_grade_run;
    const c = gr?.contract;
    const reviews: any[] = gr?.human_reviews || [];
    const last = reviews[reviews.length - 1];
    const suggested = c ? Number(c.final_score) : null;
    const final = last ? Number(last.reviewed_final_score) : suggested;
    const status = !c
      ? t("report.st.notGraded")
      : !last
      ? t("report.st.suggestedOnly")
      : last.action === "overridden"
      ? t("report.st.changed")
      : last.action === "approved"
      ? t("report.st.accepted")
      : t("report.st.returned");
    return {
      question_id: a.question_id,
      max: a.question_spec?.max_marks ?? c?.max_marks ?? null,
      suggested,
      final,
      status,
      words: c?.word_count ?? null,
      wordStatus: c?.word_limit_status ?? null,
      criteria: (c?.criterion_scores || []).map((cs: any) => ({
        criterion: cs.name || cs.criterion_id,
        score: cs.score,
        max: cs.max_score,
      })),
      decisions: reviews.map((r) => ({
        action: r.action,
        reviewer: r.reviewer,
        suggested: r.ai_suggested_score,
        final: r.reviewed_final_score,
        reason: r.override_reason,
        at: r.created_at,
      })),
    };
  }

  const exportReport = () => {
    const rows = answers.map((a) => reportRow(a));
    const payload = {
      candidate_id: sessionData?.session?.pseudonym_code,
      subject: paper?.subject,
      mock: paper?.mock_label,
      marking_scheme_version: paper?.rubric_version,
      marking_scheme_status: paper?.status,
      exported_at: new Date().toISOString(),
      authorised_by_examiner: true,
      questions: rows.map((r) => ({
        question_id: r.question_id,
        max_marks: r.max,
        suggested_marks: r.suggested,
        final_marks: r.final,
        status: r.status,
        word_count: r.words,
        word_limit_status: r.wordStatus,
        criteria: r.criteria,
        decisions: r.decisions,
      })),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${sessionData?.session?.pseudonym_code || "candidate"}-report.json`;
    a.click();
    URL.revokeObjectURL(url);
    notify(t("report.exported"));
  };

  // ---------- label helpers that depend on the language ----------

  function mimeLabel(m: string) {
    if (m === "application/pdf") return "PDF";
    if (m === "image/png") return "PNG";
    if (m === "image/jpeg") return "JPG";
    return m || "—";
  }
  function eventLabel(ev: string) {
    const translated = t(`ev.${ev}` as Key);
    if (translated !== `ev.${ev}`) return translated;
    const s = ev.toLowerCase().replace(/_/g, " ");
    return (s.charAt(0).toUpperCase() + s.slice(1)).replace(/quarantine/gi, "file check");
  }
  function wordStatusLabel(s: string) {
    if (s === "within") return t("marks.withinLimit");
    if (s === "exceeded") return t("marks.overLimit");
    return s || "—";
  }
  const qPrimary = (q: any) => {
    const tx = qText(q);
    return lang === "hi" ? tx.hi || tx.en : tx.en || tx.hi;
  };
  const dateLabel = (iso: string) => new Date(iso).toLocaleString(lang === "hi" ? "hi-IN" : "en-IN");

  // ---------- render helpers ----------

  const renderAnswerPicker = () => (
    <div className="flex flex-wrap gap-2" role="group" aria-label={t("sheets.answersOnSheet")}>
      {answers.map((a) => {
        const active = a.answer_id === answer?.answer_id;
        const open = openItems(a);
        return (
          <button
            key={a.answer_id}
            type="button"
            aria-pressed={active}
            onClick={() => openAnswer(a)}
            className={active ? CHIP_ON : CHIP_OFF}
          >
            {a.question_id}
            {open > 0 && <span className="ml-1.5 inline-block h-2 w-2 rounded-full bg-[#E88873]" title={t("sheets.toCheck", { n: open })} />}
          </button>
        );
      })}
    </div>
  );

  const renderPapers = () => (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        {papers.map((p) => {
          const approved = p.status === "published_v1";
          const active = p.paper_id === paper?.paper_id;
          return (
            <button
              key={p.paper_id}
              type="button"
              aria-pressed={active}
              onClick={() => {
                const s = SESSIONS.find((x) => x.paper === p.paper_id);
                if (s) switchSession(s.id);
              }}
              className={`rounded-xl border-2 bg-white p-5 text-left transition ${
                active ? "border-[#E88873] shadow-md" : "border-transparent shadow-sm hover:border-[#E0AC9D]"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-[#5C6D70]">{p.mock_label}</p>
                  <h2 className="mt-1 text-lg font-semibold">{p.subject}</h2>
                </div>
                <Badge tone={approved ? "ok" : "warn"}>{approved ? t("papers.approved") : t("papers.needsApproval")}</Badge>
              </div>
              <p className="mt-3 text-sm text-[#5C6D70]">{t("papers.questionsCount", { n: p.total_questions, m: p.total_marks })}</p>
            </button>
          );
        })}
      </div>

      {paper && paper.status !== "published_v1" && (
        <section className={`${CARD} border-2 border-[#E88873]`}>
          <h2 className="text-base font-semibold">{t("papers.approveTitle")}</h2>
          <p className="mt-1 text-sm text-[#5C6D70]">{t("papers.approveText")}</p>
          <label htmlFor="approval-note" className="mt-4 block text-sm font-medium">
            {t("papers.approvalNote")}
          </label>
          <textarea id="approval-note" value={approvalNote} onChange={(e) => setApprovalNote(e.target.value)} rows={2} className={`${INPUT} mt-1`} />
          <label className="mt-4 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={penaltyOn} onChange={(e) => setPenaltyOn(e.target.checked)} />
            {t("papers.penaltyLabel")}
          </label>
          {penaltyOn && (
            <input
              type="number"
              step="0.5"
              min="0"
              aria-label={t("papers.penaltyAmount")}
              value={penaltyAmount}
              onChange={(e) => setPenaltyAmount(Number(e.target.value))}
              className={`${INPUT} mt-2 max-w-[160px]`}
            />
          )}
          <div className="mt-4">
            <button type="button" onClick={publish} disabled={publishing} className={BTN_PRIMARY}>
              {publishing ? t("papers.approving") : t("papers.approveAndPublish")}
            </button>
          </div>
        </section>
      )}

      <details className={CARD}>
        <summary className="cursor-pointer select-none text-sm font-semibold">
          {t("papers.importNotes")} ({warnings.length})
          <span className="ml-2 text-xs font-normal text-[#5C6D70]">{t("papers.importNotesHint")}</span>
        </summary>
        <ul className="mt-4 divide-y divide-[#E0AC9D]/50">
          {warnings.map((w) => {
            const sev = SEVERITY_KEYS[w.severity] || SEVERITY_KEYS.low;
            return (
              <li key={w.warning_id} className="py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={sev.tone}>{t(sev.key)}</Badge>
                  <span className="text-sm font-medium">{w.affected_scope}</span>
                </div>
                <p className="mt-1 text-sm">{w.description}</p>
                <p className="mt-1 text-xs text-[#5C6D70]">
                  {t("papers.handling")}: {w.resolution}
                </p>
              </li>
            );
          })}
        </ul>
      </details>

      <div className="grid gap-6 lg:grid-cols-5">
        <section className={`${CARD} lg:col-span-2`}>
          <div className="flex flex-col gap-3">
            <input
              type="search"
              aria-label={t("papers.searchLabel")}
              placeholder={t("papers.searchPlaceholder")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className={INPUT}
            />
            <div className="flex flex-wrap gap-2">
              {["ALL", ...sectionKeys].map((s) => (
                <button key={s} type="button" aria-pressed={sectionChip === s} onClick={() => setSectionChip(s)} className={sectionChip === s ? CHIP_ON : CHIP_OFF}>
                  {s === "ALL" ? `${t("papers.all")} (${paperQuestions.length})` : t("papers.section", { s })}
                </button>
              ))}
            </div>
          </div>
          <ul className="mt-4 max-h-[560px] divide-y divide-[#E0AC9D]/40 overflow-y-auto">
            {questions.map((q) => {
              const active = selectedQ?.question_id === q.question_id;
              return (
                <li key={q.question_id}>
                  <button
                    type="button"
                    aria-pressed={active}
                    onClick={() => setQid(q.question_id)}
                    className={`w-full px-3 py-3 text-left transition ${active ? "bg-[#E0AC9D]/30" : "hover:bg-[#FAF6F3]"}`}
                  >
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <span className="font-semibold">{q.question_id}</span>
                      <span className="text-[#5C6D70]">{t("papers.marks", { n: q.max_marks })}</span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm" lang={lang === "hi" ? "hi" : "en"}>
                      {qPrimary(q)}
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>
          {questions.length === 0 && <p className="py-6 text-center text-sm text-[#5C6D70]">{t("papers.noMatch")}</p>}
        </section>

        <section className={`${CARD} lg:col-span-3`}>
          {selectedQ && detail ? (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="ok">{selectedQ.question_id}</Badge>
                <Badge>{t("papers.marks", { n: selectedQ.max_marks })}</Badge>
                {selectedQ.word_limit_label && <Badge>{selectedQ.word_limit_label}</Badge>}
              </div>
              {selectedQ.topic && <p className="text-sm text-[#5C6D70]">{selectedQ.topic}</p>}
              <div className="rounded-lg bg-[#FAF6F3] p-4">
                <p className="text-base leading-relaxed" lang="hi">{detail.text.hi}</p>
                {detail.text.en && detail.text.en !== detail.text.hi && (
                  <p className="mt-2 text-sm text-[#5C6D70]" lang="en">{detail.text.en}</p>
                )}
              </div>
              {selectedQ.pdf_page_image && (
                <a href={resolveAssetUrl(selectedQ.pdf_page_image)} target="_blank" rel="noreferrer" className="text-sm font-medium underline underline-offset-4">
                  {t("papers.viewPage")}
                </a>
              )}

              {detail.criteria.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold">{t("papers.criteria")}</h3>
                  <table className="mt-2 w-full text-sm">
                    <thead>
                      <tr className="border-b border-[#E0AC9D] text-left text-xs text-[#5C6D70]">
                        <th className="py-2 font-medium">{t("papers.colCriterion")}</th>
                        <th className="py-2 text-right font-medium">{t("papers.colMax")}</th>
                        <th className="py-2 text-right font-medium">{t("papers.colStep")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.criteria.map((c: any) => (
                        <tr key={c.criterion_id} className="border-b border-[#E0AC9D]/40">
                          <td className="py-2 pr-3">{c.name}</td>
                          <td className="py-2 text-right font-mono">{c.max_score ?? c.max_marks ?? "—"}</td>
                          <td className="py-2 text-right font-mono">{c.increment ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {detail.anchor && <p className="text-sm text-[#5C6D70]">{detail.anchor}</p>}

              {detail.points.length > 0 && (
                <details>
                  <summary className="cursor-pointer text-sm font-semibold">
                    {t("papers.expectedPoints")} ({detail.points.length})
                  </summary>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                    {detail.points.map((p: any, i: number) => (
                      <li key={i} lang="hi">{txt(p)}</li>
                    ))}
                  </ul>
                </details>
              )}

              {detail.refs.length > 0 && (
                <details>
                  <summary className="cursor-pointer text-sm font-semibold">
                    {t("papers.references")} ({detail.refs.length})
                  </summary>
                  <ul className="mt-2 space-y-2 text-sm">
                    {detail.refs.map((r: any) => (
                      <li key={r.source_id}>
                        <span className="font-medium">{r.title || r.source_id}</span>
                        {r.url && (
                          <a href={r.url} target="_blank" rel="noreferrer" className="ml-2 break-all text-xs underline">
                            {r.url}
                          </a>
                        )}
                      </li>
                    ))}
                  </ul>
                </details>
              )}

              {detail.source?.workbook_row && (
                <p className="text-xs text-[#5C6D70]">
                  {t("papers.sourceRow", { row: detail.source.workbook_row })}
                  {detail.source.pdf_page ? ` · ${t("papers.sourcePage", { page: detail.source.pdf_page })}` : ""}
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-[#5C6D70]">{t("papers.selectQuestion")}</p>
          )}
        </section>
      </div>
    </div>
  );

  const renderSheets = () => (
    <div className="grid gap-6 lg:grid-cols-5">
      <section className={`${CARD} lg:col-span-2 space-y-4`}>
        <div>
          <h2 className="text-base font-semibold">{t("sheets.uploadTitle")}</h2>
          <p className="mt-1 text-sm text-[#5C6D70]">{t("sheets.uploadHint")}</p>
        </div>
        <div>
          <label htmlFor="upload-target" className="block text-sm font-medium">{t("sheets.answersQuestion")}</label>
          <select id="upload-target" value={uploadQid} onChange={(e) => setUploadQid(e.target.value)} className={`${INPUT} mt-1`}>
            {paperQuestions.map((q) => (
              <option key={q.question_id} value={q.question_id}>{q.question_id}</option>
            ))}
          </select>
        </div>
        <label className="flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed border-[#A37774] bg-[#FAF6F3] p-8 text-center hover:border-[#E88873]">
          <span className="text-sm font-semibold">{uploading ? t("sheets.checking") : t("sheets.chooseFile")}</span>
          <span className="mt-1 text-xs text-[#5C6D70]">{t("sheets.fileTypes")}</span>
          <input type="file" accept=".pdf,.png,.jpg,.jpeg" className="sr-only" disabled={uploading} onChange={uploadSheet} />
        </label>
        {lastCheck && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg bg-[#FAF6F3] p-4 text-sm">
            <dt className="text-[#5C6D70]">{t("sheets.check")}</dt>
            <dd className="font-medium">{lastCheck.quarantine_status === "passed" ? t("sheets.passed") : t("sheets.needsReview")}</dd>
            <dt className="text-[#5C6D70]">{t("sheets.fileType")}</dt>
            <dd className="font-medium">{mimeLabel(lastCheck.detected_mime)}</dd>
            <dt className="text-[#5C6D70]">{t("sheets.size")}</dt>
            <dd className="font-medium">{t("sheets.kb", { n: Math.round((lastCheck.size_bytes || 0) / 1024) })}</dd>
            <dt className="text-[#5C6D70]">{t("sheets.fingerprint")}</dt>
            <dd className="break-all font-mono text-xs">{String(lastCheck.sha256 || "").slice(0, 24)}…</dd>
          </dl>
        )}
      </section>

      <section className={`${CARD} lg:col-span-3`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold">{t("sheets.pages")}</h2>
          <div className="flex flex-wrap gap-2">
            {sessionPages.map((p) => (
              <button key={p.page_id} type="button" aria-pressed={viewPage?.page_id === p.page_id} onClick={() => setViewPageId(p.page_id)} className={viewPage?.page_id === p.page_id ? CHIP_ON : CHIP_OFF}>
                {t("sheets.page", { n: p.page_number })}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {VARIANT_IDS.map((v) => (
            <button key={v} type="button" aria-pressed={variant === v} onClick={() => setVariant(v)} className={variant === v ? CHIP_ON : CHIP_OFF}>
              {t(VARIANT_KEYS[v])}
            </button>
          ))}
        </div>
        {ENHANCED.has(variant) && <p className="mt-3 rounded-lg bg-[#E0AC9D]/30 p-3 text-xs">{t("sheets.enhancedNote")}</p>}
        {viewPage && (
          <div className="mt-4 max-h-[520px] overflow-auto rounded-lg bg-[#484A47]/5 p-2">
            {variant !== "original" && viewPage.variants[variant] === viewPage.variants.original && (
              <p className="mb-2 rounded bg-[#E0AC9D]/30 px-3 py-1.5 text-xs">{t("sheets.noEnhanced")}</p>
            )}
            <img
              src={resolveAssetUrl(viewPage.variants[variant] || viewPage.variants.original)}
              alt={t("sheets.page", { n: viewPage.page_number })}
              className="mx-auto h-auto max-w-full rounded shadow"
            />
          </div>
        )}
      </section>

      <section className={`${CARD} lg:col-span-5`}>
        <h2 className="text-base font-semibold">{t("sheets.answersOnSheet")}</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E0AC9D] text-left text-xs text-[#5C6D70]">
                <th className="py-2 font-medium">{t("sheets.colQuestion")}</th>
                <th className="py-2 font-medium">{t("sheets.colPage")}</th>
                <th className="py-2 font-medium">{t("sheets.colReadings")}</th>
                <th className="py-2 font-medium">{t("sheets.colMarks")}</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {answers.map((a) => {
                const open = openItems(a);
                return (
                  <tr key={a.answer_id} className="border-b border-[#E0AC9D]/40">
                    <td className="py-2 font-medium">{a.question_id}</td>
                    <td className="py-2">{a.page_number}</td>
                    <td className="py-2">
                      {open > 0 ? <Badge tone="warn">{t("sheets.toCheck", { n: open })}</Badge> : <Badge tone="ok">{t("sheets.ready")}</Badge>}
                    </td>
                    <td className="py-2">
                      {a.latest_grade_run ? <Badge tone="ok">{t("sheets.graded")}</Badge> : <Badge>{t("sheets.notGraded")}</Badge>}
                    </td>
                    <td className="py-2 text-right">
                      <button type="button" onClick={() => openAnswer(a, "handwriting")} className="text-xs font-semibold underline underline-offset-4">
                        {t("sheets.open")}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );

  const renderHandwriting = () => {
    if (!answer) return <p className="text-sm text-[#5C6D70]">{t("hw.none")}</p>;
    const spans: any[] = answer.uncertain_spans || [];
    const revs: any[] = answer.revisions || [];
    const scanUrl = scanPage ? scanPage.variants[variant] || scanPage.variants.original : "";
    const openCount = spans.filter((s) => !s.resolved_by_human).length;
    return (
      <div className="space-y-5">
        {renderAnswerPicker()}
        <div className="grid gap-6 lg:grid-cols-2">
          <section className={CARD}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">{t("hw.scanTitle", { q: answer.question_id })}</h2>
                <p className="text-xs text-[#5C6D70]">{t("hw.scanHint", { p: answer.page_number })}</p>
              </div>
              <div className="flex items-center gap-1.5">
                <select aria-label={t("hw.scanView")} value={variant} onChange={(e) => setVariant(e.target.value)} className="rounded-lg border border-[#A37774]/60 bg-white px-2 py-1.5 text-xs">
                  {VARIANT_IDS.map((v) => (
                    <option key={v} value={v}>{t(VARIANT_KEYS[v])}</option>
                  ))}
                </select>
                <button type="button" aria-label={t("hw.zoomOut")} onClick={() => setZoom((z) => Math.max(75, z - 25))} className={BTN_GHOST + " px-2.5 py-1.5"}>−</button>
                <span className="w-12 text-center text-xs font-mono">{zoom}%</span>
                <button type="button" aria-label={t("hw.zoomIn")} onClick={() => setZoom((z) => Math.min(250, z + 25))} className={BTN_GHOST + " px-2.5 py-1.5"}>+</button>
                <button type="button" onClick={() => setRotation((r) => (r + 90) % 360)} className={BTN_GHOST + " px-2.5 py-1.5"}>{t("hw.rotate")}</button>
              </div>
            </div>
            {ENHANCED.has(variant) && <p className="mt-3 rounded-lg bg-[#E0AC9D]/30 p-2.5 text-xs">{t("hw.enhancedCaution")}</p>}
            <div className="mt-4 max-h-[620px] overflow-auto rounded-lg bg-[#484A47]/5 p-3">
              <div className="relative mx-auto transition-all" style={{ width: `${zoom}%`, transform: `rotate(${rotation}deg)` }}>
                {scanUrl && <img src={resolveAssetUrl(scanUrl)} alt={t("hw.scanTitle", { q: answer.question_id })} className="block h-auto w-full rounded shadow" />}
                {answer.bbox_norm && (
                  <div
                    className="pointer-events-none absolute border-2 border-dashed border-[#5C6D70]"
                    style={{
                      left: `${answer.bbox_norm[0] * 100}%`,
                      top: `${answer.bbox_norm[1] * 100}%`,
                      width: `${(answer.bbox_norm[2] - answer.bbox_norm[0]) * 100}%`,
                      height: `${(answer.bbox_norm[3] - answer.bbox_norm[1]) * 100}%`,
                    }}
                  />
                )}
                {spans.map((sp) => (
                  <div
                    key={sp.span_id}
                    title={sp.current_text}
                    className={`absolute border-2 ${sp.resolved_by_human ? "border-[#5C6D70] bg-[#5C6D70]/10" : "border-[#E88873] bg-[#E88873]/20"}`}
                    style={{
                      left: `${sp.bbox_norm[0] * 100}%`,
                      top: `${sp.bbox_norm[1] * 100}%`,
                      width: `${(sp.bbox_norm[2] - sp.bbox_norm[0]) * 100}%`,
                      height: `${(sp.bbox_norm[3] - sp.bbox_norm[1]) * 100}%`,
                    }}
                  />
                ))}
              </div>
            </div>
          </section>

          <section className={`${CARD} space-y-5`}>
            <div>
              <h3 className="text-sm font-semibold">{t("hw.readings")}</h3>
              <p className="text-xs text-[#5C6D70]">{t("hw.readersNote")}</p>
              <ul className="mt-3 space-y-2">
                {(answer.ocr_candidates || []).map((c: any, i: number) => (
                  <li key={i} className="rounded-lg border border-[#E0AC9D]/60 p-3">
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <span className="font-semibold">{c.adapter_name}</span>
                      <span className="text-[#5C6D70]">{t("hw.confidence", { n: pct(c.calibrated_confidence) })}</span>
                    </div>
                    <p className="mt-1 line-clamp-3 text-sm" lang="hi">{c.transcript}</p>
                    <button type="button" onClick={() => setDraft(c.transcript)} className="mt-1.5 text-xs font-semibold underline underline-offset-4">
                      {t("hw.useReading")}
                    </button>
                  </li>
                ))}
              </ul>
            </div>

            {spans.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold">{t("hw.placesToCheck", { n: openCount })}</h3>
                <ul className="mt-3 space-y-2">
                  {spans.map((sp) => {
                    const low = Number(sp.calibrated_confidence) < CONFIDENCE_FLAG;
                    return (
                      <li key={sp.span_id} className="rounded-lg border border-[#E0AC9D]/60 p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium" lang="hi">“{sp.current_text}”</span>
                          <Badge tone={low ? "alert" : "neutral"}>{low ? t("hw.cannotReadConfidently") : t("hw.confidence", { n: pct(sp.calibrated_confidence) })}</Badge>
                          {sp.resolved_by_human && <Badge tone="ok">{t("hw.resolved")}</Badge>}
                        </div>
                        {sp.disagreement_reason && <p className="mt-1 text-xs text-[#5C6D70]">{sp.disagreement_reason}</p>}
                        <div className="mt-2 flex flex-wrap gap-2">
                          {(sp.alternatives || []).map((alt: any, i: number) => (
                            <button key={i} type="button" onClick={() => applyAlternative(sp, alt.text)} className={BTN_GHOST + " px-3 py-1 text-xs"}>
                              {alt.text === UNREADABLE ? t("hw.markCannotRead") : t("hw.useAlternative", { text: alt.text })}
                            </button>
                          ))}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            <div className="space-y-3">
              <h3 className="text-sm font-semibold">{t("hw.transcript")}</h3>
              <textarea id="transcript-editor" lang="hi" rows={8} value={draft} onChange={(e) => setDraft(e.target.value)} className={INPUT} />
              <div>
                <label htmlFor="linked-question" className="block text-sm font-medium">{t("hw.linkedQuestion")}</label>
                <select id="linked-question" value={linkedQid} onChange={(e) => setLinkedQid(e.target.value)} className={`${INPUT} mt-1`}>
                  {paperQuestions.map((q) => (
                    <option key={q.question_id} value={q.question_id}>{q.question_id}</option>
                  ))}
                </select>
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => saveTranscript(false)} disabled={saving} className={BTN_GHOST}>{t("hw.saveDraft")}</button>
                <button type="button" onClick={() => saveTranscript(true)} disabled={saving} className={BTN_PRIMARY}>{t("hw.confirm")}</button>
                <button type="button" onClick={() => setTab("marks")} className={BTN_DARK}>{t("hw.goToMarks")}</button>
              </div>
            </div>

            <details>
              <summary className="cursor-pointer text-sm font-semibold">{t("hw.revisionHistory", { n: revs.length })}</summary>
              <ol className="mt-3 space-y-2">
                {[...revs].reverse().map((rev: any) => (
                  <li key={rev.version_id} className="rounded-lg bg-[#FAF6F3] p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="font-semibold">{t("hw.revision", { n: rev.revision_number })}</span>
                      <Badge tone={rev.is_confirmed_for_grading ? "ok" : "neutral"}>{rev.is_confirmed_for_grading ? t("hw.confirmed") : t("hw.draft")}</Badge>
                      <span className="text-[#5C6D70]">{rev.author} · {dateLabel(rev.created_at)}</span>
                    </div>
                    <p className="mt-1 line-clamp-2" lang="hi">{rev.text}</p>
                  </li>
                ))}
              </ol>
              <p className="mt-2 text-xs text-[#5C6D70]">{t("hw.revisionsNote")}</p>
            </details>
          </section>
        </div>
      </div>
    );
  };

  const renderMarks = () => {
    if (!answer) return <p className="text-sm text-[#5C6D70]">{t("hw.none")}</p>;
    const gr = answer.latest_grade_run;
    const c = gr?.contract;
    const reviews: any[] = gr?.human_reviews || [];
    const max = c?.max_marks ?? answer.question_spec?.max_marks;
    return (
      <div className="space-y-5">
        {renderAnswerPicker()}
        <section className={CARD}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">{answer.question_id}</h2>
              <p className="text-sm text-[#5C6D70]">{answer.question_spec?.topic}</p>
              <p className="mt-1 text-xs text-[#5C6D70]">{answer.question_spec?.word_limit_label}</p>
            </div>
            <button type="button" onClick={runGrade} disabled={grading} className={BTN_PRIMARY}>
              {grading ? t("marks.calculating") : gr ? t("marks.recalculate") : t("marks.calculate")}
            </button>
          </div>

          {!c ? (
            <p className="mt-6 text-sm text-[#5C6D70]">{t("marks.notYet")}</p>
          ) : (
            <div className="mt-6 space-y-6">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-lg bg-[#FAF6F3] p-4">
                  <p className="text-xs text-[#5C6D70]">{t("marks.suggested")}</p>
                  <p className="mt-1 text-2xl font-semibold">{c.final_score} <span className="text-base font-normal text-[#5C6D70]">/ {max}</span></p>
                </div>
                <div className="rounded-lg bg-[#FAF6F3] p-4">
                  <p className="text-xs text-[#5C6D70]">{t("marks.wordCount")}</p>
                  <p className="mt-1 text-2xl font-semibold">{c.word_count}</p>
                  <p className="mt-1 text-xs text-[#5C6D70]">{wordStatusLabel(c.word_limit_status)}</p>
                </div>
                <div className="rounded-lg bg-[#FAF6F3] p-4">
                  <p className="text-xs text-[#5C6D70]">{t("marks.status")}</p>
                  <p className="mt-2">{c.needs_human_review ? <Badge tone="warn">{t("marks.needsReview")}</Badge> : <Badge tone="ok">{t("marks.noIssues")}</Badge>}</p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#E0AC9D] text-left text-xs text-[#5C6D70]">
                      <th className="py-2 font-medium">{t("marks.colCriterion")}</th>
                      <th className="py-2 pl-4 text-right font-medium">{t("marks.colMarks")}</th>
                      <th className="py-2 pl-6 font-medium">{t("marks.colChange")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(c.criterion_scores || []).map((cs: any) => (
                      <tr key={cs.criterion_id} className="border-b border-[#E0AC9D]/40 align-top">
                        <td className="py-3 pr-4">
                          <p className="font-medium">{cs.name}</p>
                          <p className="mt-1 text-xs text-[#5C6D70]">{cs.reason}</p>
                          {cs.answer_evidence?.[0]?.quote && (
                            <p className="mt-1 text-xs italic text-[#5C6D70]" lang="hi">“{cs.answer_evidence[0].quote}”</p>
                          )}
                        </td>
                        <td className="py-3 pl-4 text-right font-mono">{cs.score} / {cs.max_score}</td>
                        <td className="py-3 pl-6">
                          <div className="flex items-center gap-2">
                            <input
                              type="number"
                              aria-label={t("marks.newMarksFor", { name: cs.name })}
                              min={0}
                              max={cs.max_score}
                              step={cs.increment || 0.5}
                              value={criterionInputs[cs.criterion_id] ?? cs.score}
                              onChange={(e) => setCriterionInputs((prev) => ({ ...prev, [cs.criterion_id]: e.target.value }))}
                              className={`${INPUT} w-24`}
                            />
                            <button
                              type="button"
                              onClick={() => setCriterion(cs.criterion_id, criterionInputs[cs.criterion_id] ?? String(cs.score))}
                              className={BTN_GHOST + " px-3 py-2 text-xs"}
                            >
                              {t("marks.set")}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {[
                [t("marks.strengths"), c.strengths],
                [t("marks.missing"), c.missing_points],
                [t("marks.factual"), c.factual_errors],
                [t("marks.improve"), c.improvements],
              ].map(([label, items]: any) =>
                Array.isArray(items) && items.length > 0 ? (
                  <div key={label}>
                    <h3 className="text-sm font-semibold">{label}</h3>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                      {items.map((it: any, i: number) => (
                        <li key={i}>{txt(it)}</li>
                      ))}
                    </ul>
                  </div>
                ) : null
              )}
            </div>
          )}
        </section>

        {c && (
          <div className="grid gap-6 lg:grid-cols-2">
            <section className={CARD}>
              <h2 className="text-base font-semibold">{t("marks.decisionTitle")}</h2>
              <p className="mt-1 text-sm text-[#5C6D70]">{t("marks.decisionNote")}</p>
              <div className="mt-4 space-y-4">
                <div>
                  <label htmlFor="decision" className="block text-sm font-medium">{t("marks.decision")}</label>
                  <select id="decision" value={reviewAction} onChange={(e) => setReviewAction(e.target.value)} className={`${INPUT} mt-1`}>
                    <option value="approved">{t("marks.optAccept")}</option>
                    <option value="overridden">{t("marks.optChange")}</option>
                    <option value="returned_for_transcript_correction">{t("marks.optReturn")}</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="final-marks" className="block text-sm font-medium">{t("marks.finalMarks")}</label>
                  <input id="final-marks" type="number" step="0.5" min={0} max={max} value={reviewScore} onChange={(e) => setReviewScore(e.target.value)} className={`${INPUT} mt-1 max-w-[160px]`} />
                </div>
                <div>
                  <label htmlFor="reason" className="block text-sm font-medium">
                    {t("marks.reason")} {reviewAction === "overridden" && <span className="text-[#A37774]">{t("marks.required")}</span>}
                  </label>
                  <textarea id="reason" rows={3} value={reviewReason} onChange={(e) => setReviewReason(e.target.value)} className={`${INPUT} mt-1`} />
                </div>
                <button
                  type="button"
                  onClick={submitDecision}
                  disabled={submittingReview || (reviewAction === "overridden" && !reviewReason.trim())}
                  className={BTN_PRIMARY}
                >
                  {submittingReview ? t("marks.saving") : t("marks.saveDecision")}
                </button>
              </div>
            </section>

            <section className={CARD}>
              <h2 className="text-base font-semibold">{t("marks.historyTitle")}</h2>
              {reviews.length === 0 ? (
                <p className="mt-3 text-sm text-[#5C6D70]">{t("marks.noDecisions")}</p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {[...reviews].reverse().map((r: any) => (
                    <li key={r.review_id} className="rounded-lg bg-[#FAF6F3] p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <Badge tone={r.action === "overridden" ? "warn" : "ok"}>
                          {r.action === "overridden" ? t("marks.changed") : r.action === "approved" ? t("marks.accepted") : t("marks.returned")}
                        </Badge>
                        <span className="text-[#5C6D70]">{r.reviewer}</span>
                      </div>
                      <p className="mt-2">{t("marks.suggestedArrow", { s: r.ai_suggested_score, f: r.reviewed_final_score })}</p>
                      {r.override_reason && <p className="mt-1 text-xs text-[#5C6D70]">{r.override_reason}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </div>
    );
  };

  const renderReport = () => {
    const rows = answers.map((a) => reportRow(a));
    const graded = rows.filter((r) => r.suggested !== null);
    const totalFinal = rows.reduce((s, r) => s + (r.final ?? 0), 0);
    const totalSuggested = rows.reduce((s, r) => s + (r.suggested ?? 0), 0);
    const totalMax = rows.reduce((s, r) => s + (Number(r.max) || 0), 0);
    const events: any[] = (auditData?.audit_events || []).filter((e: any) => !String(e.event_type).startsWith("SECURITY_")).slice(-12).reverse();
    const isDraft = paper && paper.status !== "published_v1";
    return (
      <div className="space-y-6">
        <section className={CARD}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-[#5C6D70]">{t("report.candidateId")} {sessionData?.session?.pseudonym_code}</p>
              <h2 className="mt-1 text-xl font-semibold">{paper?.subject} · {paper?.mock_label}</h2>
              <p className="mt-1 text-sm text-[#5C6D70]">
                {t("report.scheme")} {paper?.rubric_version} ·{" "}
                {isDraft ? <Badge tone="warn">{t("report.draft")}</Badge> : <Badge tone="ok">{t("report.approved")}</Badge>}
              </p>
            </div>
          </div>

          {isDraft && (
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#E88873] bg-[#E88873]/15 p-4 text-sm">
              <span>{t("report.provisional")}</span>
              <button type="button" onClick={() => setTab("papers")} className={BTN_DARK}>{t("report.reviewApprove")}</button>
            </div>
          )}

          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E0AC9D] text-left text-xs text-[#5C6D70]">
                  <th className="py-2 font-medium">{t("report.colQuestion")}</th>
                  <th className="py-2 text-right font-medium">{t("report.colSuggested")}</th>
                  <th className="py-2 text-right font-medium">{t("report.colFinal")}</th>
                  <th className="py-2 pl-6 text-right font-medium">{t("report.colMax")}</th>
                  <th className="py-2 pl-6 font-medium">{t("report.colStatus")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.question_id} className="border-b border-[#E0AC9D]/40">
                    <td className="py-2 font-medium">{r.question_id}</td>
                    <td className="py-2 text-right font-mono">{r.suggested ?? "—"}</td>
                    <td className="py-2 text-right font-mono">{r.final ?? "—"}</td>
                    <td className="py-2 pl-6 text-right font-mono">{r.max ?? "—"}</td>
                    <td className="py-2 pl-6">{r.status}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="font-semibold">
                  <td className="py-3">{t("report.total", { n: rows.length, g: graded.length })}</td>
                  <td className="py-3 text-right font-mono">{totalSuggested}</td>
                  <td className="py-3 text-right font-mono">{totalFinal}</td>
                  <td className="py-3 pl-6 text-right font-mono">{totalMax}</td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </section>

        <section className={`${CARD} flex flex-col gap-4`}>
          <h2 className="text-base font-semibold">{t("report.export")}</h2>
          <label className="flex items-start gap-3 text-sm">
            <input type="checkbox" checked={authorised} onChange={(e) => setAuthorised(e.target.checked)} className="mt-1" />
            <span>{t("report.authorise")}</span>
          </label>
          <div>
            <button type="button" onClick={exportReport} disabled={!authorised} className={BTN_DARK}>
              {t("report.exportButton")}
            </button>
          </div>
        </section>

        <details className={CARD}>
          <summary className="cursor-pointer text-sm font-semibold">{t("report.activity")}</summary>
          {events.length === 0 ? (
            <p className="mt-3 text-sm text-[#5C6D70]">{t("report.noActivity")}</p>
          ) : (
            <ul className="mt-3 divide-y divide-[#E0AC9D]/40 text-sm">
              {events.map((e: any) => (
                <li key={e.id} className="flex flex-wrap justify-between gap-2 py-2">
                  <span>{eventLabel(e.event_type)}</span>
                  <span className="text-xs text-[#5C6D70]">{e.actor} · {dateLabel(e.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </details>
      </div>
    );
  };

  // ---------- layout ----------

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#FAF6F3] text-[#484A47]">
        <p className="text-sm">{t("app.loading")}</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-[#FAF6F3] text-[#484A47]">
      <header className="bg-[#484A47] text-[#FAF6F3]">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-[#E88873] text-sm font-bold text-[#484A47]">UP</div>
            <div>
              <h1 className="text-base font-semibold">{t("app.title")}</h1>
              <p className="text-xs text-[#E0AC9D]">{t("app.subtitle")}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <LangSwitch lang={lang} onChange={setLang} label={t("app.language")} />
            <label className="flex items-center gap-2 text-xs text-[#E0AC9D]">
              {t("app.candidate")}
              <select
                aria-label={t("app.selectCandidate")}
                value={sessionId}
                onChange={(e) => switchSession(e.target.value)}
                className="rounded-md border border-[#E0AC9D]/50 bg-[#5C6D70] px-2.5 py-1.5 text-sm text-[#FAF6F3] focus:outline-none focus:ring-2 focus:ring-[#E88873]"
              >
                {SESSIONS.map((s) => (
                  <option key={s.id} value={s.id}>{s.label}</option>
                ))}
              </select>
            </label>
          </div>
        </div>
        <nav aria-label={t("app.sections")} className="border-t border-[#5C6D70]">
          <div className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-3">
            {TAB_IDS.map((id) => {
              const active = tab === id;
              return (
                <button
                  key={id}
                  type="button"
                  aria-current={active ? "page" : undefined}
                  onClick={() => setTab(id)}
                  className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm transition ${
                    active ? "border-[#E88873] font-semibold text-white" : "border-transparent text-[#E0AC9D] hover:text-white"
                  }`}
                >
                  {t(`nav.${id === "sheets" ? "sheets" : id}` as Key)}
                </button>
              );
            })}
          </div>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-5 py-8">
        <div className="mb-6">
          <h2 className="text-xl font-semibold">{t(`title.${tab}` as Key)}</h2>
          <p className="mt-1 text-xs text-[#5C6D70]">{t("app.demoNote")}</p>
        </div>
        {tab === "papers" && renderPapers()}
        {tab === "sheets" && renderSheets()}
        {tab === "handwriting" && renderHandwriting()}
        {tab === "marks" && renderMarks()}
        {tab === "report" && renderReport()}
      </main>

      {toast && (
        <div
          role="status"
          aria-live="polite"
          className={`fixed bottom-5 right-5 z-50 max-w-sm rounded-lg px-4 py-3 text-sm shadow-xl ${
            toast.type === "error" ? "bg-[#A37774] text-[#FAF6F3]" : "bg-[#484A47] text-[#FAF6F3]"
          }`}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}
