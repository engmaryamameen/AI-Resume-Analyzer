"""Turns dataset records into the objects the inference engines take. Shared by evaluation, training and
benchmarking, so a model is always trained and measured on exactly what the application will give it."""

from app.analysis.evidence import build_query
from app.analysis.schema import RequirementDraft
from app.lang.taxonomy import get_taxonomy
from app.ml.contracts import Passage, Query, format_context
from ml.schema import ExtractionRecord, Requirement, VerificationRecord

_CATEGORY = {
    "skill": "skill",
    "soft_skill": "soft_skill",
    "certification": "certification",
    "experience": "experience_years",
    "responsibility": "responsibility",
}


def passage_of(record: ExtractionRecord | VerificationRecord) -> Passage:
    return Passage(id=record.id, text=record.text, section_kind=record.section_kind,
                   context=format_context(record.section_kind, record.entry_header))


def query_of(requirement: Requirement, query_id: str) -> Query:
    """The query the analysis pipeline builds for a requirement of this type. The hypothesis always comes
    from the record's own requirement, the wording the verifier was trained on."""
    taxonomy = get_taxonomy()
    term_id = taxonomy.normalise_surface(requirement.value) if requirement.type in {"skill", "soft_skill"} else None
    category = _CATEGORY[requirement.type]
    if term_id is None and category in {"skill", "soft_skill"}:
        category = "responsibility"  # a skill outside the vocabulary is verified as free text
    draft = RequirementDraft(ordinal=0, text=requirement.value, kind="required", category=category,  # type: ignore[arg-type]
                             terms=[term_id] if term_id else [])
    query = build_query(draft, taxonomy)
    if query is None:
        raise ValueError(f"cannot build a query for {requirement!r}")
    return query.model_copy(update={"id": query_id, "hypothesis": requirement.hypothesis()})
