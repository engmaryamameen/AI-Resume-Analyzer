"""Data contracts shared by the inference engines, the analysis pipeline and the training code.

Nothing here imports torch. Label vocabularies are defined once and used by training, inference and
evaluation, so a model can never be loaded with a different label order than it was trained with.
"""

from typing import Literal

from pydantic import BaseModel, Field

ENTITY_TYPES = ("SKILL", "DEGREE", "FIELD", "ORG", "TITLE", "CERT")
MentionType = Literal["SKILL", "DEGREE", "FIELD", "ORG", "TITLE", "CERT"]
TOKEN_LABELS = ("O", *(f"{prefix}-{t}" for t in ENTITY_TYPES for prefix in ("B", "I")))

# What a mention is doing in its sentence. For degrees and certifications, "affirmed" means held or
# completed; "hedged" means in progress, aspirational or only loosely claimed.
ROLES = ("affirmed", "listed", "mentioned", "negated", "hedged")
MentionRole = Literal["affirmed", "listed", "mentioned", "negated", "hedged"]
ROLE_TYPES = frozenset({"SKILL", "DEGREE", "CERT"})

VERDICT_LABELS = ("supports", "mentions_only", "contradicts", "insufficient", "unrelated")
VerdictLabel = Literal["supports", "mentions_only", "contradicts", "insufficient", "unrelated"]


def format_context(section_kind: str, entry_header: str | None) -> str:
    """The context line given to the models with each passage. Training data uses this same function."""
    return f"{section_kind} | {entry_header[:100]}" if entry_header else section_kind


class Passage(BaseModel):
    """A piece of résumé text with where it sits, e.g. one bullet inside one role."""

    id: str  # the résumé block id
    text: str
    context: str  # "experience | Senior Engineer, Acme, 2019-2022"; model input and display
    section_kind: str


class Mention(BaseModel):
    passage_id: str
    start: int  # character offsets into Passage.text
    end: int
    text: str
    type: MentionType
    role: MentionRole | None = None  # only for SKILL, DEGREE, CERT
    role_probs: dict[str, float] | None = None  # calibrated, or None
    source: Literal["rules", "learned"]


class Query(BaseModel):
    """A requirement, expressed both as a retrieval query and as a hypothesis to verify."""

    id: str
    retrieval_query: str
    hypothesis: str
    term_ids: list[str] = Field(
        default_factory=list
    )  # canonical vocabulary ids, when the requirement has them
    surface_forms: list[str] = Field(
        default_factory=list
    )  # names and aliases used to link mentions


class Candidate(BaseModel):
    passage_id: str
    # Raw retrieval score (BM25 or cosine similarity). It orders candidates; it is NOT a probability.
    score: float
    method: Literal["bm25", "embedding"]


class Verdict(BaseModel):
    label: VerdictLabel
    probs: dict[str, float] | None = None  # present only when the verifier is calibrated
    source: Literal["rules", "learned"]


class ModelRef(BaseModel):
    id: str
    origin: Literal["pretrained", "fine_tuned"]
    base_model: str
    revision: str
    license: str


class EngineInfo(BaseModel):
    mode: Literal["learned", "semantic", "rules"]
    models: list[ModelRef] = Field(default_factory=list)
    calibrated: bool = False
    fingerprint: str  # "rules", or a hash of the approved model files
    notes: list[str] = Field(
        default_factory=list
    )  # why the learned engine is not in use, if it is not
