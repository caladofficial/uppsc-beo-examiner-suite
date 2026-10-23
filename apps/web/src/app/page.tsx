"use client";

import React, { useEffect, useState } from "react";
import { LANG_STORAGE_KEY, Lang, Key, translate } from "@/lib/i18n";

type Paper = {
  paper_id: string;
  title: string;
  subject: string | null;
  mock_label: string | null;
  question_count: number;
  total_marks: number;
};

type QuestionItem = {
  question_id: string;
  label: string;
  max_marks: number;
  word_limit: number | null;
  question_en: string;
  question_hi: string;
};

type Bilingual = { en: string[]; hi: string[] };

type GradeResult = {
  status: "good" | "partial" | "low" | "needs_review" | "not_answered" | "not_found";
  label: string;
  marks: number;
  max_marks: number;
  method: string | null;
  review_codes: string[];
  good_points: Bilingual;
  missing_points: Bilingual;
  feedback: { en: string; hi: string };
  model_answer: string | null;
  read_text: string;
  word_count?: number;
  word_limit?: number | null;
  reader: { pages: number; vision_pages: number; fallback_pages: number };
};

const MAX_BYTES = 25 * 1024 * 1024;
const ACCESS_STORAGE_KEY = "uppsc-access-code";
const ACCEPT = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";

const STATUS_STYLE: Record<GradeResult["status"], { key: Key; cls: string }> = {
  good: { key: "statusGood", cls: "bg-[#E4F0E8] text-[#23543A]" },
  partial: { key: "statusPartial", cls: "bg-[#FBF0D9] text-[#7A5410]" },
  low: { key: "statusLow", cls: "bg-[#F7E1DC] text-[#8A3B2A]" },
  needs_review: { key: "statusReview", cls: "bg-[#E6ECF7] text-[#2F4A7A]" },
  not_answered: { key: "statusNone", cls: "bg-[#ECEBE9] text-[#5C5E5B]" },
  not_found: { key: "statusNone", cls: "bg-[#ECEBE9] text-[#5C5E5B]" },
};

export default function AnswerCheckPage() {
  const [lang, setLang] = useState<Lang>("en");
  const [step, setStep] = useState<1 | 2 | 3>(1);

  const [papers, setPapers] = useState<Paper[] | null>(null);
  const [papersError, setPapersError] = useState(false);
  const [paperId, setPaperId] = useState<string | null>(null);

  const [questions, setQuestions] = useState<QuestionItem[] | null>(null);
  const [questionsError, setQuestionsError] = useState(false);
  const [questionId, setQuestionId] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<Key | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState(false);
  const [result, setResult] = useState<GradeResult | null>(null);
  const [accessCode, setAccessCode] = useState("");
  const [accessWrong, setAccessWrong] = useState(false);

  const t = (key: Key, vars?: Record<string, string | number>) => translate(lang, key, vars);

  // Read the saved language once on load. It is only written when the user picks a language.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(LANG_STORAGE_KEY);
      if (saved === "en" || saved === "hi") setLang(saved);
      const code = window.sessionStorage.getItem(ACCESS_STORAGE_KEY);
      if (code) setAccessCode(code);
    } catch {
      /* storage unavailable: keep English */
    }
  }, []);

  function changeAccessCode(value: string) {
    setAccessCode(value);
    setAccessWrong(false);
    try {
      window.sessionStorage.setItem(ACCESS_STORAGE_KEY, value);
    } catch {
      /* storage unavailable: the code must be entered again on reload */
    }
  }

  useEffect(() => {
    document.documentElement.lang = lang === "hi" ? "hi" : "en";
  }, [lang]);

  useEffect(() => {
    fetch("/api/check", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((body: { papers: Paper[] }) => setPapers(body.papers))
      .catch(() => setPapersError(true));
  }, []);

  function chooseLang(next: Lang) {
    setLang(next);
    try {
      window.localStorage.setItem(LANG_STORAGE_KEY, next);
    } catch {
      /* storage unavailable: the choice applies for this visit only */
    }
  }

  function pickPaper(id: string) {
    setPaperId(id);
    setQuestionId(null);
    setQuestions(null);
    setQuestionsError(false);
    fetch(`/api/grade?paper_id=${encodeURIComponent(id)}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((body: { questions: QuestionItem[] }) => setQuestions(body.questions))
      .catch(() => setQuestionsError(true));
  }

  function pickFile(f: File | null) {
    setFileError(null);
    if (!f) {
      setFile(null);
      return;
    }
    if (f.size > MAX_BYTES) {
      setFile(null);
      setFileError("fileTooLarge");
      return;
    }
    const name = f.name.toLowerCase();
    const okType = /\.(pdf|png|jpe?g)$/.test(name) && (f.type === "" || /pdf|png|jpeg/.test(f.type));
    if (!okType) {
      setFile(null);
      setFileError("fileType");
      return;
    }
    setFile(f);
  }

  async function start() {
    if (!file || !paperId || !questionId) return;
    setChecking(true);
    setCheckError(false);
    setResult(null);
    setStep(3);
    try {
      const form = new FormData();
      form.set("paper_id", paperId);
      form.set("question_id", questionId);
      form.set("file", file);
      // The sheet goes straight to the answer-check service (the hosting platform limits request
      // bodies to a few megabytes). The service grades in the background; we poll for the result.
      // Each request uses a fresh short-lived token from this site's server.
      async function auth(): Promise<{ url: string; token: string }> {
        const r = await fetch("/api/token", { cache: "no-store", headers: { "x-access-code": accessCode.trim() } });
        if (r.status === 401) throw new Error("access");
        if (!r.ok) throw new Error("token");
        return (await r.json()) as { url: string; token: string };
      }
      const first = await auth();
      const started = await fetch(`${first.url}/grade-jobs`, {
        method: "POST",
        body: form,
        headers: { "x-service-token": first.token },
      });
      if (!started.ok) throw new Error("start failed");
      const { job_id } = (await started.json()) as { job_id: string };

      const deadline = Date.now() + 15 * 60 * 1000;
      let finished = false;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const { url, token } = await auth();
        const r = await fetch(`${url}/grade-jobs/${job_id}`, { cache: "no-store", headers: { "x-service-token": token } });
        if (!r.ok) throw new Error("poll failed");
        const body = (await r.json()) as { status: string; result?: GradeResult; detail?: string };
        if (body.status === "done" && body.result) {
          setResult(body.result);
          finished = true;
          break;
        }
        if (body.status === "error") throw new Error(body.detail || "check failed");
      }
      if (!finished) throw new Error("timeout");
    } catch (err) {
      if (err instanceof Error && err.message === "access") {
        // Wrong or missing access code: send the visitor back to the upload step with a message.
        setAccessWrong(true);
        setStep(2);
      } else {
        setCheckError(true);
      }
    } finally {
      setChecking(false);
    }
  }

  function startOver() {
    setFile(null);
    setFileError(null);
    setResult(null);
    setCheckError(false);
    setQuestionId(null);
    setPaperId(null);
    setQuestions(null);
    setStep(1);
  }

  function checkAnother() {
    setFile(null);
    setFileError(null);
    setResult(null);
    setCheckError(false);
    setStep(2);
  }

  const selectedQuestion = questions?.find((q) => q.question_id === questionId) ?? null;
  const selectedPaper = papers?.find((p) => p.paper_id === paperId) ?? null;

  function questionText(q: QuestionItem): string {
    const text = lang === "hi" ? q.question_hi || q.question_en : q.question_en || q.question_hi;
    return text.length > 170 ? text.slice(0, 170).trimEnd() + "…" : text;
  }

  // Points in the chosen language; if that language has none, show the other one rather than "none found".
  function pointsFor(list: Bilingual): string[] {
    const chosen = lang === "hi" ? list.hi : list.en;
    return chosen.length > 0 ? chosen : lang === "hi" ? list.en : list.hi;
  }

  function noteTexts(r: GradeResult): string[] {
    const notes: string[] = [];
    if (r.review_codes.includes("disagree")) notes.push(t("noteDisagree"));
    if (r.review_codes.includes("header_unclear")) notes.push(t("noteHeader"));
    if (r.review_codes.includes("single_check")) notes.push(t("noteSingle"));
    if (r.review_codes.includes("word_limit")) notes.push(t("noteWordLimit"));
    if (r.reader && r.reader.fallback_pages > 0) notes.push(t("noteFallbackReader"));
    return notes;
  }

  const steps: { n: 1 | 2 | 3; key: Key }[] = [
    { n: 1, key: "stepQuestion" },
    { n: 2, key: "stepUpload" },
    { n: 3, key: "stepResult" },
  ];

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-5 py-8 sm:py-12">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium tracking-wide text-[#9A6A5C]">{t("appName")}</p>
          <h1 className="mt-1 text-2xl font-semibold text-[#3A3C39] sm:text-3xl">{t("pageTitle")}</h1>
          <p className="mt-2 max-w-xl text-sm text-[#6B6D6A]">{t("pageLead")}</p>
        </div>
        <div role="group" aria-label={t("languageLabel")} className="flex shrink-0 rounded-full border border-[#E3D5CE] bg-white p-1 text-sm">
          {(["en", "hi"] as Lang[]).map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => chooseLang(l)}
              aria-pressed={lang === l}
              className={`rounded-full px-3 py-1 transition ${lang === l ? "bg-[#484A47] text-white" : "text-[#484A47] hover:bg-[#F3EAE6]"}`}
            >
              {l === "en" ? "English" : "हिन्दी"}
            </button>
          ))}
        </div>
      </header>

      <ol className="mt-8 grid grid-cols-3 gap-2 text-sm">
        {steps.map((s) => {
          const active = step === s.n;
          const done = step > s.n;
          return (
            <li
              key={s.n}
              aria-current={active ? "step" : undefined}
              className={`flex items-center gap-2 rounded-xl border px-3 py-2 ${active ? "border-[#C98B79] bg-white" : "border-[#EADFD9] bg-[#FDF9F7]"}`}
            >
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  active || done ? "bg-[#C98B79] text-white" : "bg-[#EADFD9] text-[#6B6D6A]"
                }`}
              >
                {s.n}
              </span>
              <span className={`${active ? "font-semibold text-[#3A3C39]" : "text-[#6B6D6A]"}`}>{t(s.key)}</span>
            </li>
          );
        })}
      </ol>

      {step === 1 && (
        <section className="mt-6 space-y-6">
          <div className="rounded-2xl border border-[#EADFD9] bg-white p-5 sm:p-7">
            <h2 className="text-lg font-semibold text-[#3A3C39]">{t("paperHeading")}</h2>
            <p className="mt-1 text-sm text-[#6B6D6A]">{t("paperHelp")}</p>
            {papersError && <p className="mt-5 text-sm text-[#8A3B2A]">{t("papersError")}</p>}
            {!papers && !papersError && <p className="mt-5 text-sm text-[#6B6D6A]">{t("loadingPapers")}</p>}
            {papers && (
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {papers.map((p) => {
                  const active = p.paper_id === paperId;
                  return (
                    <button
                      key={p.paper_id}
                      type="button"
                      onClick={() => pickPaper(p.paper_id)}
                      aria-pressed={active}
                      className={`rounded-xl border p-4 text-left transition ${active ? "border-[#C98B79] bg-[#FDF3EF]" : "border-[#E3D5CE] bg-white hover:border-[#C98B79]"}`}
                    >
                      <span className="block text-base font-semibold text-[#3A3C39]">{p.mock_label ?? p.title}</span>
                      <span className="mt-1 block text-sm text-[#6B6D6A]">{p.subject ?? p.title}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {paperId && (
            <div className="rounded-2xl border border-[#EADFD9] bg-white p-5 sm:p-7">
              <h2 className="text-lg font-semibold text-[#3A3C39]">{t("questionHeading")}</h2>
              <p className="mt-1 text-sm text-[#6B6D6A]">{t("questionHelp")}</p>
              {questionsError && <p className="mt-5 text-sm text-[#8A3B2A]">{t("questionsError")}</p>}
              {!questions && !questionsError && <p className="mt-5 text-sm text-[#6B6D6A]">{t("loadingQuestions")}</p>}
              {questions && (
                <ul className="mt-5 grid max-h-[460px] gap-2 overflow-y-auto pr-1">
                  {questions.map((q) => {
                    const active = q.question_id === questionId;
                    return (
                      <li key={q.question_id}>
                        <button
                          type="button"
                          onClick={() => setQuestionId(q.question_id)}
                          aria-pressed={active}
                          className={`w-full rounded-xl border px-4 py-3 text-left transition ${active ? "border-[#C98B79] bg-[#FDF3EF]" : "border-[#E3D5CE] bg-white hover:border-[#C98B79]"}`}
                        >
                          <span className="flex flex-wrap items-center gap-2 text-sm font-semibold text-[#3A3C39]">
                            <span>{q.label}</span>
                            <span className="rounded-full bg-[#F3EAE6] px-2 py-0.5 text-xs font-medium text-[#7A4A3A]">{t("marks", { n: q.max_marks })}</span>
                            {q.word_limit ? <span className="text-xs font-normal text-[#6B6D6A]">{t("wordLimit", { n: q.word_limit })}</span> : null}
                          </span>
                          <span className="mt-1 block text-sm leading-relaxed text-[#4B4D4A]">{questionText(q)}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}

          <div className="flex justify-end">
            <button
              type="button"
              disabled={!questionId}
              onClick={() => setStep(2)}
              className="rounded-full bg-[#484A47] px-6 py-2.5 text-sm font-medium text-white transition hover:bg-[#3A3C39] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {t("next")}
            </button>
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="mt-6 rounded-2xl border border-[#EADFD9] bg-white p-5 sm:p-7">
          {selectedQuestion && (
            <div className="rounded-xl bg-[#FDF9F7] px-4 py-3 text-sm text-[#4B4D4A]">
              <span className="font-semibold text-[#3A3C39]">{selectedQuestion.label}</span>
              <span className="ml-2 text-[#7A4A3A]">{t("marks", { n: selectedQuestion.max_marks })}</span>
              <p className="mt-1 leading-relaxed">{questionText(selectedQuestion)}</p>
            </div>
          )}
          <h2 className="mt-6 text-lg font-semibold text-[#3A3C39]">{t("uploadHeading")}</h2>
          <p className="mt-1 text-sm text-[#6B6D6A]">{t("uploadHelp")}</p>

          <label className="mt-5 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-[#D8C5BD] bg-[#FDF9F7] px-6 py-8 text-center transition hover:border-[#C98B79]">
            <span className="rounded-full bg-[#484A47] px-4 py-2 text-sm font-medium text-white">{t("chooseFile")}</span>
            <span className="text-sm text-[#6B6D6A]">{t("dropHint")}</span>
            <input
              type="file"
              accept={ACCEPT}
              className="sr-only"
              onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
            />
          </label>

          <div className="mt-6">
            <label htmlFor="access-code" className="block text-sm font-semibold text-[#3A3C39]">
              {t("accessLabel")}
            </label>
            <p className="mt-1 text-xs text-[#6B6D6A]">{t("accessHelp")}</p>
            <input
              id="access-code"
              type="password"
              autoComplete="off"
              value={accessCode}
              onChange={(e) => changeAccessCode(e.target.value)}
              className="mt-2 w-full max-w-xs rounded-lg border border-[#D8C5BD] bg-white px-3 py-2 text-sm text-[#3A3C39] focus:border-[#C98B79] focus:outline-none"
            />
            {accessWrong && <p className="mt-2 text-sm text-[#8A3B2A]">{t("accessWrong")}</p>}
          </div>

          {file && (
            <p className="mt-4 text-sm text-[#3A3C39]">
              {t("selectedFile")}: <span className="font-medium">{file.name}</span>
            </p>
          )}
          {fileError && <p className="mt-3 text-sm text-[#8A3B2A]">{t(fileError)}</p>}

          <div className="mt-6 flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="rounded-full border border-[#E3D5CE] px-5 py-2.5 text-sm font-medium text-[#484A47] hover:bg-[#F3EAE6]"
            >
              {t("back")}
            </button>
            <button
              type="button"
              disabled={!file || !accessCode.trim()}
              onClick={start}
              className="rounded-full bg-[#484A47] px-6 py-2.5 text-sm font-medium text-white transition hover:bg-[#3A3C39] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {t("start")}
            </button>
          </div>
        </section>
      )}

      {step === 3 && (
        <section className="mt-6 space-y-5">
          {checking && (
            <div className="rounded-2xl border border-[#EADFD9] bg-white p-6 text-sm text-[#4B4D4A]" role="status">
              {t("checking")}
            </div>
          )}

          {checkError && !checking && (
            <div className="rounded-2xl border border-[#EADFD9] bg-white p-6">
              <p className="text-sm text-[#8A3B2A]">{t("checkFailed")}</p>
              <button type="button" onClick={() => setStep(2)} className="mt-4 rounded-full border border-[#E3D5CE] px-5 py-2 text-sm text-[#484A47] hover:bg-[#F3EAE6]">
                {t("back")}
              </button>
            </div>
          )}

          {result && !checking && result.status === "not_found" && (
            <div className="rounded-2xl border border-[#EADFD9] bg-white p-6">
              <p className="text-sm text-[#8A3B2A]">{t("noAnswer")}</p>
              <button type="button" onClick={() => setStep(2)} className="mt-4 rounded-full border border-[#E3D5CE] px-5 py-2 text-sm text-[#484A47] hover:bg-[#F3EAE6]">
                {t("back")}
              </button>
            </div>
          )}

          {result && !checking && result.status !== "not_found" && (
            <>
              <div className="rounded-2xl border border-[#EADFD9] bg-white p-5 sm:p-7">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm text-[#6B6D6A]">{result.label}</p>
                    <p className="mt-1 text-sm font-medium text-[#6B6D6A]">{t("scoreLabel")}</p>
                    <p className="text-4xl font-semibold text-[#3A3C39]">
                      {result.marks}
                      <span className="ml-2 text-lg font-normal text-[#6B6D6A]">{t("outOf", { n: result.max_marks })}</span>
                    </p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-sm font-medium ${STATUS_STYLE[result.status].cls}`}>
                    {t(STATUS_STYLE[result.status].key)}
                  </span>
                </div>
                {result.feedback && (lang === "hi" ? result.feedback.hi : result.feedback.en) && (
                  <div className="mt-5">
                    <h3 className="text-sm font-semibold text-[#3A3C39]">{t("feedbackHeading")}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-[#4B4D4A]">{lang === "hi" ? result.feedback.hi : result.feedback.en}</p>
                  </div>
                )}
                {noteTexts(result).length > 0 && (
                  <ul className="mt-5 space-y-2">
                    {noteTexts(result).map((n) => (
                      <li key={n} className="rounded-lg bg-[#EEF2F9] px-3 py-2 text-sm text-[#2F4A7A]">
                        {n}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="grid gap-5 sm:grid-cols-2">
                <div className="rounded-2xl border border-[#EADFD9] bg-white p-5">
                  <h3 className="text-base font-semibold text-[#23543A]">{t("goodHeading")}</h3>
                  {pointsFor(result.good_points).length === 0 ? (
                    <p className="mt-3 text-sm text-[#6B6D6A]">{t("goodEmpty")}</p>
                  ) : (
                    <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-[#3A3C39]">
                      {pointsFor(result.good_points).map((g, i) => (
                        <li key={i}>{g}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="rounded-2xl border border-[#EADFD9] bg-white p-5">
                  <h3 className="text-base font-semibold text-[#8A3B2A]">{t("missingHeading")}</h3>
                  {pointsFor(result.missing_points).length === 0 ? (
                    <p className="mt-3 text-sm text-[#6B6D6A]">{t("missingEmpty")}</p>
                  ) : (
                    <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-[#3A3C39]">
                      {pointsFor(result.missing_points).map((m, i) => (
                        <li key={i}>{m}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              {result.model_answer && (
                <details className="rounded-2xl border border-[#EADFD9] bg-white p-5">
                  <summary className="cursor-pointer text-base font-semibold text-[#3A3C39]">{t("modelHeading")}</summary>
                  <p className="mt-2 text-xs text-[#6B6D6A]">{t("modelHelp")}</p>
                  <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-[#3A3C39]">{result.model_answer}</p>
                </details>
              )}

              <details className="rounded-2xl border border-[#EADFD9] bg-white p-5">
                <summary className="cursor-pointer text-base font-semibold text-[#3A3C39]">{t("readHeading")}</summary>
                <p className="mt-2 text-xs text-[#6B6D6A]">{t("readHelp")}</p>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-[#3A3C39]">{result.read_text}</p>
              </details>

              <p className="text-xs text-[#6B6D6A]">{t("guide")}</p>

              <div className="flex flex-wrap justify-end gap-3">
                <button type="button" onClick={checkAnother} className="rounded-full border border-[#E3D5CE] px-5 py-2.5 text-sm font-medium text-[#484A47] hover:bg-[#F3EAE6]">
                  {t("checkAnother")}
                </button>
                <button type="button" onClick={startOver} className="rounded-full bg-[#484A47] px-6 py-2.5 text-sm font-medium text-white hover:bg-[#3A3C39]">
                  {t("startOver")}
                </button>
              </div>
            </>
          )}
        </section>
      )}
      {selectedPaper && step === 1 && <span className="sr-only">{selectedPaper.title}</span>}
    </main>
  );
}
