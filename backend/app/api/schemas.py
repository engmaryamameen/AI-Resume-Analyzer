"""Request and response contracts. These drive the OpenAPI document."""

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.analysis.job_descriptions import RequirementInput
from app.analysis.schema import AnalysisWarning, Assessment, EvidenceRef, MatchStatus, Recommendation
from app.ml.contracts import EngineInfo, Mention, ModelRef

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Credentials(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=256)


class DeleteAccountIn(BaseModel):
    password: str = Field(max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    role: str


class ResumeVersionOut(BaseModel):
    id: uuid.UUID
    version_no: int
    source: str
    status: str
    error_code: str | None
    parseability: dict | None
    created_at: datetime


class ResumeOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    latest_version: ResumeVersionOut


class ResumeDetailOut(ResumeOut):
    normalized: dict | None
    versions: list[ResumeVersionOut]


class ContactCorrection(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None


class CorrectionIn(BaseModel):
    base_version_no: int = Field(ge=1)
    block_edits: dict[str, str] = Field(default_factory=dict, max_length=200)
    contact: ContactCorrection | None = None


class JobCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(max_length=100_000)


class RequirementOut(BaseModel):
    id: uuid.UUID
    ordinal: int
    text: str
    kind: str
    category: str
    origin: str
    terms: list
    min_years: float | None
    source_span: dict | None


class JobVersionOut(BaseModel):
    id: uuid.UUID
    version_no: int
    source: str
    created_at: datetime


class JobOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    latest_version: JobVersionOut


class JobDetailOut(JobOut):
    raw_text: str
    requirements: list[RequirementOut]
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    versions: list[JobVersionOut]


class RequirementsReplaceIn(BaseModel):
    base_version_no: int = Field(ge=1)
    requirements: list[RequirementInput] = Field(max_length=80)


class AnalysisCreateIn(BaseModel):
    resume_version_id: uuid.UUID
    jd_version_id: uuid.UUID


class Staleness(BaseModel):
    is_stale: bool
    reasons: list[str]


class MatchOut(BaseModel):
    requirement: RequirementOut
    status: MatchStatus
    conflict: bool
    probability: float | None
    reasons: list[str]
    evidence: list[EvidenceRef]
    explanation: str | None


class AnalysisOut(BaseModel):
    id: uuid.UUID
    status: str
    resume_version_id: uuid.UUID
    resume_document_id: uuid.UUID | None
    resume_version_no: int | None
    jd_version_id: uuid.UUID
    latest_resume_version_id: uuid.UUID | None  # what "run it again" should use
    latest_jd_version_id: uuid.UUID | None
    pipeline_version: str
    engine: EngineInfo | None
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None
    staleness: Staleness


class AnalysisDetailOut(AnalysisOut):
    assessments: list[Assessment] | None
    warnings: list[AnalysisWarning]
    recommendations: list[Recommendation]
    limitations: list[str]
    matches: list[MatchOut]
    mentions: list[Mention]


class ModelStatusOut(BaseModel):
    learned_models_approved: bool
    models: list[ModelRef]
    note: str


class DemoAnalyzeIn(BaseModel):
    resume_id: str = Field(max_length=40)
    job_id: str | None = Field(default=None, max_length=40)
    job_text: str | None = Field(default=None, max_length=20_000)
