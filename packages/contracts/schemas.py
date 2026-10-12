"""
Strict Pydantic & JSON Schema Contracts for UPPSC BEO Answer-Sheet Scanner & Rubric Grader.
Enforces the exact Grading Output Contract and Transcript/OCR separation rules.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class WordLimitStatus(str, Enum):
    within = "within"
    exceeded = "exceeded"
    approximate = "approximate"
    not_specified = "not_specified"


class FactualErrorSeverity(str, Enum):
    minor = "minor"
    material = "material"


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class AnswerEvidence(BaseModel):
    page: int = Field(..., ge=1, description="1-indexed page number in candidate scan")
    bbox: List[float] = Field(..., min_length=4, max_length=4, description="[x1, y1, x2, y2] normalized or pixel coordinates")
    quote: str = Field(..., min_length=1, description="Exact quote from confirmed student transcript")


class KeyEvidence(BaseModel):
    source_id: str = Field(..., min_length=1, description="ID of approved ReferenceSnapshot in pinned rubric")
    claim: str = Field(..., min_length=1, description="Supporting claim from approved reference snapshot")


class CriterionScoreContract(BaseModel):
    criterion_id: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0)
    max_score: float = Field(..., gt=0.0)
    reason: str = Field(..., min_length=3)
    answer_evidence: List[AnswerEvidence] = Field(default_factory=list)
    key_evidence: List[KeyEvidence] = Field(default_factory=list)

    @field_validator("score")
    @classmethod
    def score_not_above_max(cls, v: float, info):
        max_s = info.data.get("max_score")
        if max_s is not None and v > max_s:
            raise ValueError(f"Criterion score {v} exceeds max_score {max_s}")
        return v


class FactualErrorItem(BaseModel):
    claim: str = Field(..., min_length=1)
    severity: FactualErrorSeverity
    explanation: str = Field(..., min_length=3)


class GradingOutputContract(BaseModel):
    """
    Canonical structured JSON grading output contract.
    Final score is deterministically calculated and capped by packages/rubric-core.
    """
    exam_version: str
    rubric_version: str
    question_id: str
    transcript_version: str
    word_count: int = Field(..., ge=0)
    word_limit_status: WordLimitStatus
    criterion_scores: List[CriterionScoreContract]
    final_score: float = Field(..., ge=0.0)
    strengths: List[str] = Field(default_factory=list)
    missing_points: List[str] = Field(default_factory=list)
    factual_errors: List[FactualErrorItem] = Field(default_factory=list)
    language_or_format_issues: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    confidence: ConfidenceLevel
    needs_human_review: bool
    review_reasons: List[str] = Field(default_factory=list)
