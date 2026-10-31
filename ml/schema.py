"""Validated JSONL records and span markup.

Records sharing a document or template-family group must stay in the same split."""

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

from app.ml.contracts import ENTITY_TYPES, ROLE_TYPES, ROLES
from app.ml.hypotheses import (
    certification_hypothesis,
    experience_hypothesis,
    responsibility_hypothesis,
    skill_hypothesis,
    soft_skill_hypothesis,
)
from pydantic import BaseModel, Field, model_validator

SOURCES = ("synthetic", "hand_written", "licensed")
SPLITS = ("train", "validation", "calibration", "test")

_MARKUP = re.compile(
    r"\[\[(?P<text>[^\[\]|]+)\|(?P<type>[A-Z]+)(?:\|(?P<role>[a-z]+))?\]\]"
)


class Span(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    type: Literal["SKILL", "DEGREE", "FIELD", "ORG", "TITLE", "CERT"]
    role: Literal["affirmed", "listed", "mentioned", "negated", "hedged"] | None = None

    @model_validator(mode="after")
    def _check(self) -> "Span":
        if self.end <= self.start:
            raise ValueError("a span must end after it starts")
        if self.type in ROLE_TYPES and self.role is None:
            raise ValueError(f"{self.type} spans need a role")
        if self.type not in ROLE_TYPES and self.role is not None:
            raise ValueError(f"{self.type} spans take no role")
        return self


class Meta(BaseModel):
    id: str
    group: str
    source: Literal["synthetic", "hand_written", "licensed"]
    # Free-form tags used to slice the evaluation, e.g. "negation", "degree_ambiguity", "paraphrase".
    tags: list[str] = Field(default_factory=list)


class ExtractionRecord(Meta):
    kind: Literal["extraction"] = "extraction"
    section_kind: str
    entry_header: str | None = None
    text: str
    spans: list[Span]


class Requirement(BaseModel):
    type: Literal[
        "skill", "soft_skill", "certification", "experience", "responsibility"
    ]
    value: str

    def hypothesis(self) -> str:
        return _BUILDERS[self.type](self.value)


_BUILDERS = {
    "skill": skill_hypothesis,
    "soft_skill": soft_skill_hypothesis,
    "certification": certification_hypothesis,
    "experience": experience_hypothesis,
    "responsibility": responsibility_hypothesis,
}


class VerificationRecord(Meta):
    kind: Literal["verification"] = "verification"
    section_kind: str
    entry_header: str | None = None
    text: str
    requirement: Requirement
    label: Literal[
        "supports", "mentions_only", "contradicts", "insufficient", "unrelated"
    ]


class RetrievalPassage(BaseModel):
    id: str
    text: str
    relevant: bool


class RetrievalRecord(Meta):
    kind: Literal["retrieval"] = "retrieval"
    query: str
    passages: list[RetrievalPassage]


Record = ExtractionRecord | VerificationRecord | RetrievalRecord
_KINDS = {
    "extraction": ExtractionRecord,
    "verification": VerificationRecord,
    "retrieval": RetrievalRecord,
}


def parse_markup(marked: str) -> tuple[str, list[Span]]:
    """`"Built [[Kafka|SKILL|affirmed]] pipelines"` -> (`"Built Kafka pipelines"`, [Span(6, 11, SKILL, affirmed)])."""
    text_parts: list[str] = []
    spans: list[Span] = []
    cursor = 0
    length = 0
    for match in _MARKUP.finditer(marked):
        plain = marked[cursor : match.start()]
        text_parts.append(plain)
        length += len(plain)
        surface = match.group("text")
        kind, role = match.group("type"), match.group("role")
        if kind not in ENTITY_TYPES:
            raise ValueError(f"unknown entity type {kind!r}")
        if role is not None and role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
        spans.append(
            Span(start=length, end=length + len(surface), type=kind, role=role)
        )  # type: ignore[arg-type]
        text_parts.append(surface)
        length += len(surface)
        cursor = match.end()
    text_parts.append(marked[cursor:])
    return "".join(text_parts), spans


def parse_record(raw: dict) -> Record:
    """Build a record from one JSON object. Extraction records may give `marked` text instead of
    `text` and `spans`; see parse_markup."""
    if "marked" in raw:
        text, spans = parse_markup(raw["marked"])
        raw = {
            **{k: v for k, v in raw.items() if k != "marked"},
            "text": text,
            "spans": [s.model_dump() for s in spans],
        }
    kind = raw.get("kind")
    if kind not in _KINDS:
        raise ValueError(f"unknown record kind {kind!r}")
    return _KINDS[kind].model_validate(raw)


def read_jsonl(path: Path) -> list[Record]:
    records: list[Record] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(parse_record(json.loads(line)))
            except ValueError as exc:
                raise ValueError(f"{path}:{number}: {exc}") from exc
    return records


def write_jsonl(path: Path, records: Iterable[Record]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(
                    record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
                )
                + "\n"
            )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dataset_digest(paths: Sequence[Path]) -> str:
    """One hash over a set of dataset files; recorded with every trained model."""
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode())
        digest.update(file_sha256(path).encode())
    return digest.hexdigest()
