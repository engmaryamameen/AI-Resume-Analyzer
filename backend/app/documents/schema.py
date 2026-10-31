"""Normalised document model produced by ingestion and consumed by analysis."""

from typing import Literal

from pydantic import BaseModel, Field

SectionKind = Literal[
    "header",
    "summary",
    "experience",
    "education",
    "projects",
    "skills",
    "certifications",
    "awards",
    "publications",
    "volunteering",
    "languages",
    "interests",
    "other",
]
BlockKind = Literal["bullet", "paragraph", "entry_header"]
Confidence = Literal["high", "medium", "low"]


class Block(BaseModel):
    id: str
    section_id: str
    kind: BlockKind
    text: str = Field(max_length=4000)
    page: int | None = None
    line: int  # 1-based position in the extracted line stream


class Section(BaseModel):
    id: str
    kind: SectionKind
    heading: str | None = None
    block_ids: list[str] = Field(default_factory=list)


class DateRange(BaseModel):
    start: str  # YYYY-MM
    end: str  # YYYY-MM or "present"
    months: int | None = None
    approximate: bool = False


class Entry(BaseModel):
    """A role, degree or project: a header block followed by its detail blocks."""

    id: str
    section_id: str
    header_block_id: str
    date_range: DateRange | None = None
    block_ids: list[str] = Field(default_factory=list)


class ContactField(BaseModel):
    value: str | None = None
    confidence: Confidence = "low"
    block_id: str | None = None


class Contact(BaseModel):
    name: ContactField = Field(default_factory=ContactField)
    email: ContactField = Field(default_factory=ContactField)
    phone: ContactField = Field(default_factory=ContactField)
    links: list[str] = Field(default_factory=list)


class Uncertainty(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warn", "error"] = "warn"
    block_id: str | None = None


class NormalizedDocument(BaseModel):
    page_count: int | None = None
    blocks: list[Block] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    entries: list[Entry] = Field(default_factory=list)
    contact: Contact = Field(default_factory=Contact)
    total_experience_months: int | None = None
    uncertainties: list[Uncertainty] = Field(default_factory=list)

    def block_map(self) -> dict[str, Block]:
        return {b.id: b for b in self.blocks}

    def section_kind_by_id(self) -> dict[str, str]:
        return {s.id: s.kind for s in self.sections}


class Parseability(BaseModel):
    """How far the extraction can be trusted. Descriptive, not a quality score."""

    level: Literal["good", "fair", "poor"]
    reliable_for_analysis: bool
    signals: list[Uncertainty] = Field(default_factory=list)
