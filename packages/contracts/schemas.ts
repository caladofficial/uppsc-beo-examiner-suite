/**
 * Shared TypeScript & Zod-compatible interfaces for UPPSC BEO Answer-Sheet Scanner & Rubric Grader.
 */

export type WordLimitStatus = "within" | "exceeded" | "approximate" | "not_specified";
export type FactualErrorSeverity = "minor" | "material";
export type ConfidenceLevel = "high" | "medium" | "low";

export interface AnswerEvidence {
  page: number;
  bbox: [number, number, number, number];
  quote: string;
}

export interface KeyEvidence {
  source_id: string;
  claim: string;
}

export interface CriterionScore {
  criterion_id: string;
  score: number;
  max_score: number;
  reason: string;
  answer_evidence: AnswerEvidence[];
  key_evidence: KeyEvidence[];
}

export interface FactualErrorItem {
  claim: string;
  severity: FactualErrorSeverity;
  explanation: string;
}

export interface GradingContract {
  exam_version: string;
  rubric_version: string;
  question_id: string;
  transcript_version: string;
  word_count: number;
  word_limit_status: WordLimitStatus;
  criterion_scores: CriterionScore[];
  final_score: number;
  strengths: string[];
  missing_points: string[];
  factual_errors: FactualErrorItem[];
  language_or_format_issues: string[];
  improvements: string[];
  confidence: ConfidenceLevel;
  needs_human_review: boolean;
  review_reasons: string[];
}
