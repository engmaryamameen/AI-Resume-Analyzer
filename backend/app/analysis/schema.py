from typing import Any, Literal

from pydantic import BaseModel, Field

from app.ml.contracts import EngineInfo, Mention

RequirementKind = Literal["required", "preferred"]
RequirementCategory = Literal[
    "skill", "experience_years", "education", "certification", "responsibility", "soft_skill"
]
RequirementOrigin = Literal["extracted", "inferred", "user"]
MatchStatus = Literal["supported", "mentioned_only", "contradicted", "insufficient", "no_evidence"]
EvidenceLabel = Literal["supports", "mentions_only", "contradicts", "insufficient"]


class RequirementDraft(BaseModel):
    ordinal: int
    text: str = Field(max_length=500)
    kind: RequirementKind
    category: RequirementCategory
    origin: RequirementOrigin = "extracted"
    terms: list[str] = Field(default_factory=list)
    min_years: float | None = None
    # {"start": int, "end": int, "alt_group": int | None, "inferred_from": [term ids], "reason": str}
    source_span: dict[str, Any] | None = None


class EvidenceRef(BaseModel):
    """Exact résumé text that a conclusion rests on. The excerpt is always verbatim, never generated."""

    block_id: str | None
    section_kind: str | None
    page: int | None = None
    line: int | None = None
    excerpt: str = Field(max_length=400)
    highlights: list[tuple[int, int]] = Field(
        default_factory=list
    )  # character ranges inside the excerpt
    label: EvidenceLabel | None = None
    roles: list[str] = Field(default_factory=list)  # roles of the matching mentions in this passage
    retrieval_score: float | None = None  # raw similarity, ordering only; not a probability
    retrieval_method: str | None = None
    derived: bool = False  # computed from the document (e.g. total experience), not quoted from it


class MatchResult(BaseModel):
    ordinal: int
    status: MatchStatus
    conflict: bool = False
    probability: float | None = (
        None  # calibrated estimate for the strongest passage's label, or None
    )
    reasons: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    explanation: str | None = None


class Metric(BaseModel):
    name: str
    value: int | float | str
    unit: Literal["count", "percent", "months", "text"]
    definition: str


class Assessment(BaseModel):
    id: Literal[
        "requirement_evidence", "document_structure", "writing_style", "extraction_reliability"
    ]
    label: str
    summary: str
    metrics: list[Metric] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    """Advice anchored in the résumé's own text. `fill_in` is a blank for the user, not generated prose."""

    kind: Literal["add_evidence", "resolve_conflict", "clarify", "add_dates", "style_note"]
    requirement_ordinal: int | None = None
    title: str
    detail: str
    block_id: str | None = None
    excerpt: str | None = None
    fill_in: str | None = None


class AnalysisWarning(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warn", "error"] = "warn"


class AnalysisResult(BaseModel):
    pipeline_version: str
    engine: EngineInfo
    requirements: list[RequirementDraft]
    matches: list[MatchResult]
    mentions: list[Mention]
    assessments: list[Assessment]
    recommendations: list[Recommendation]
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
