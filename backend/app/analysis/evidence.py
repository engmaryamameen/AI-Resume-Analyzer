"""Match requirements to source passages and reconcile evidence labels.

Degrees use level comparisons; experience uses dated-role arithmetic."""

import re
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.analysis.passages import build_passages
from app.analysis.schema import EvidenceRef, MatchResult, MatchStatus, RequirementDraft
from app.core.metrics import ML_STAGE_SECONDS
from app.documents.schema import Block, NormalizedDocument
from app.lang.taxonomy import Taxonomy, get_taxonomy
from app.ml.contracts import Mention, Passage, Query
from app.ml.decision import CandidateEvidence, Decision, decide
from app.ml.degree import LEVEL_RANK, degree_level
from app.ml.engine import Budget, Engine
from app.ml.hypotheses import (
    certification_hypothesis,
    experience_hypothesis,
    responsibility_hypothesis,
    skill_hypothesis,
    soft_skill_hypothesis,
)
from app.ml.linking import mention_matches_query

RETRIEVAL_K = 5
MAX_CANDIDATES = 8
MAX_EVIDENCE_SHOWN = 3
EXCERPT_CHARS = 400
_YEARS_PHRASE = re.compile(
    r"\b\d{1,2}\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years?|yrs?)\b(?:\s+of)?(?:\s+(?:professional|relevant|hands-on|industry|"
    r"commercial|work))*(?:\s+experience)?(?:\s+(?:in|with|of|using))?",
    re.IGNORECASE,
)


@dataclass
class _Candidate:
    passage_id: str
    score: float | None = None
    method: str | None = None
    linked: list[Mention] = field(default_factory=list)


def build_query(requirement: RequirementDraft, taxonomy: Taxonomy) -> Query | None:
    """The retrieval query and the hypothesis to verify. Education is decided without a model (see _education)."""
    category, text, qid = requirement.category, requirement.text, str(requirement.ordinal)
    if category in {"skill", "soft_skill"} and requirement.terms:
        term = taxonomy.get(requirement.terms[0])
        hypothesis = (
            soft_skill_hypothesis(term.name)
            if category == "soft_skill"
            else skill_hypothesis(term.name)
        )
        return Query(
            id=qid,
            retrieval_query=f"{term.name} {' '.join(term.aliases[:2])}".strip(),
            hypothesis=hypothesis,
            term_ids=[term.id],
            surface_forms=list(taxonomy.surface_forms(term.id)),
        )
    if category == "certification":
        return Query(
            id=qid,
            retrieval_query=text,
            hypothesis=certification_hypothesis(text),
            surface_forms=list(requirement.terms),
        )
    if category == "experience_years":
        if requirement.terms:
            term = taxonomy.get(requirement.terms[0])
            return Query(
                id=qid,
                retrieval_query=term.name,
                hypothesis=skill_hypothesis(term.name),
                term_ids=[term.id],
                surface_forms=list(taxonomy.surface_forms(term.id)),
            )
        phrase = _YEARS_PHRASE.sub("", text).strip(" ,.:;-")
        subject = phrase if len(phrase) >= 3 else "a relevant professional field"
        return Query(id=qid, retrieval_query=subject, hypothesis=experience_hypothesis(subject))
    if category == "responsibility":
        return Query(id=qid, retrieval_query=text, hypothesis=responsibility_hypothesis(text))
    return None


def _timed[T](stage: str, engine: Engine, call: Callable[[], T]) -> T:
    started = time.perf_counter()
    try:
        return call()
    finally:
        ML_STAGE_SECONDS.labels(stage=stage, mode=engine.info.mode).observe(
            time.perf_counter() - started
        )


def match_requirements(
    doc: NormalizedDocument,
    requirements: Sequence[RequirementDraft],
    engine: Engine,
    budget: Budget,
) -> tuple[list[MatchResult], list[Mention]]:
    taxonomy = get_taxonomy()
    passages = build_passages(doc)
    by_id = {p.id: p for p in passages}
    blocks = doc.block_map()
    mentions = _timed("extract", engine, lambda: engine.extract(passages, budget))
    mentions_by_passage: dict[str, list[Mention]] = defaultdict(list)
    for mention in mentions:
        mentions_by_passage[mention.passage_id].append(mention)

    queries = {r.ordinal: q for r in requirements if (q := build_query(r, taxonomy)) is not None}
    retrieved = (
        _timed(
            "retrieve",
            engine,
            lambda: engine.retrieve(list(queries.values()), passages, RETRIEVAL_K, budget),
        )
        if queries and passages
        else {}
    )

    plans: dict[int, list[_Candidate]] = {}
    pairs: list[tuple[Query, Passage]] = []
    for ordinal, query in queries.items():
        chosen: dict[str, _Candidate] = {}
        for pid, found in mentions_by_passage.items():
            linked = [m for m in found if mention_matches_query(taxonomy, query, m)]
            if linked:
                chosen[pid] = _Candidate(pid, linked=linked)
        for hit in retrieved.get(query.id, []):
            candidate = chosen.setdefault(hit.passage_id, _Candidate(hit.passage_id))
            candidate.score, candidate.method = hit.score, hit.method
        plans[ordinal] = list(chosen.values())[:MAX_CANDIDATES]
        pairs += [(query, by_id[c.passage_id]) for c in plans[ordinal]]

    verdicts = iter(_timed("verify", engine, lambda: engine.verify(pairs, budget)) if pairs else [])
    decisions: dict[int, Decision] = {}
    for ordinal, candidates in plans.items():
        evidence = [
            CandidateEvidence(
                c.passage_id,
                next(verdicts),
                tuple(m.role for m in c.linked if m.role),
                c.score,
                c.method,
            )
            for c in candidates
        ]
        decisions[ordinal] = decide(evidence)
    linked_by_passage = {o: {c.passage_id: c.linked for c in cands} for o, cands in plans.items()}

    results = []
    for requirement in requirements:
        decision = decisions.get(requirement.ordinal)
        passage_links = linked_by_passage.get(requirement.ordinal, {})
        if requirement.category == "education":
            results.append(_education(requirement, mentions, blocks, by_id))
        elif requirement.category == "experience_years":
            results.append(_years(requirement, doc, decision, passage_links, blocks, by_id))
        elif decision is not None:
            results.append(_from_decision(requirement, decision, passage_links, blocks, by_id))
        else:
            results.append(
                MatchResult(
                    ordinal=requirement.ordinal,
                    status="no_evidence",
                    explanation=_explain("no_evidence", requirement.text, False),
                )
            )
    return results, mentions


def _evidence_refs(
    decision: Decision,
    linked: dict[str, list[Mention]],
    blocks: dict[str, Block],
    by_id: dict[str, Passage],
) -> list[EvidenceRef]:
    refs = []
    for judged in decision.evidence[:MAX_EVIDENCE_SHOWN]:
        c = judged.candidate
        block = blocks[c.passage_id]
        mentions = linked.get(c.passage_id, [])
        refs.append(
            EvidenceRef(
                block_id=block.id,
                section_kind=by_id[c.passage_id].section_kind,
                page=block.page,
                line=block.line,
                excerpt=block.text[:EXCERPT_CHARS],
                highlights=[(m.start, m.end) for m in mentions if m.end <= EXCERPT_CHARS],
                label=judged.label if judged.label != "unrelated" else None,
                roles=[m.role for m in mentions if m.role],
                retrieval_score=c.retrieval_score,
                retrieval_method=c.retrieval_method,
            )
        )
    return refs


def _explain(status: MatchStatus, name: str, conflict: bool) -> str | None:
    if status == "supported":
        return None
    if status == "mentioned_only":
        return f"“{name}” is named, but nothing in the résumé shows what you did with it."
    if status == "contradicted":
        return "Text in the résumé contradicts this requirement."
    if status == "insufficient":
        return (
            "There is related text, but it conflicts with other text and can't be relied on."
            if conflict
            else "There is related text, but it isn't specific enough to count as evidence."
        )
    return "Nothing in the résumé relates to this requirement."


def _from_decision(
    requirement: RequirementDraft,
    decision: Decision,
    linked: dict[str, list[Mention]],
    blocks: dict[str, Block],
    by_id: dict[str, Passage],
) -> MatchResult:
    return MatchResult(
        ordinal=requirement.ordinal,
        status=decision.status,
        conflict=decision.conflict,
        probability=decision.probability,
        reasons=decision.reasons,
        evidence=_evidence_refs(decision, linked, blocks, by_id),
        explanation=_explain(decision.status, requirement.text, decision.conflict),
    )


def _years(
    requirement: RequirementDraft,
    doc: NormalizedDocument,
    decision: Decision | None,
    linked: dict[str, list[Mention]],
    blocks: dict[str, Block],
    by_id: dict[str, Passage],
) -> MatchResult:
    needed = requirement.min_years or 0
    ordinal = requirement.ordinal
    if doc.total_experience_months is None:
        return MatchResult(
            ordinal=ordinal,
            status="insufficient",
            reasons=["No parseable date ranges were found, so total experience can't be computed."],
            explanation="Give each role a date range such as “Jan 2021 – Present”.",
        )
    years = doc.total_experience_months / 12
    derived = EvidenceRef(
        block_id=None,
        section_kind="experience",
        derived=True,
        excerpt=f"Dated roles span about {years:.1f} years (computed from the date ranges).",
    )
    if years < needed:
        return MatchResult(
            ordinal=ordinal,
            status="insufficient",
            evidence=[derived],
            reasons=[f"Dated roles total about {years:.1f} years; {needed:g} requested."],
            explanation=f"The posting asks for {needed:g}+ years; your dated roles total about {years:.1f}.",
        )
    base = _from_decision(requirement, decision, linked, blocks, by_id) if decision else None
    if base is None or base.status in {"no_evidence", "mentioned_only", "insufficient"}:
        return MatchResult(
            ordinal=ordinal,
            status="no_evidence"
            if base is None or base.status == "no_evidence"
            else "insufficient",
            evidence=[derived, *(base.evidence if base else [])],
            reasons=[
                "Total experience is long enough, but the résumé doesn't show experience in the area asked for."
            ],
            explanation="Your dated roles are long enough, but nothing shows experience in the area the posting names.",
        )
    return MatchResult(
        ordinal=ordinal,
        status=base.status,
        conflict=base.conflict,
        probability=base.probability,
        reasons=[*base.reasons, f"Dated roles total about {years:.1f} years, meeting {needed:g}+."],
        evidence=[derived, *base.evidence],
        explanation=base.explanation,
    )


def _education(
    requirement: RequirementDraft,
    mentions: Sequence[Mention],
    blocks: dict[str, Block],
    by_id: dict[str, Passage],
) -> MatchResult:
    required = next(
        (t.split(":", 1)[1] for t in requirement.terms if t.startswith("degree:")), "bachelor"
    )
    need = LEVEL_RANK[required]
    degrees = [
        (m, level) for m in mentions if m.type == "DEGREE" and (level := degree_level(m.text))
    ]

    def refs(selected: list[tuple[Mention, str]]) -> list[EvidenceRef]:
        out = []
        for m, _ in selected[:MAX_EVIDENCE_SHOWN]:
            block = blocks[m.passage_id]
            out.append(
                EvidenceRef(
                    block_id=block.id,
                    section_kind=by_id[m.passage_id].section_kind,
                    page=block.page,
                    line=block.line,
                    excerpt=block.text[:EXCERPT_CHARS],
                    highlights=[(m.start, m.end)] if m.end <= EXCERPT_CHARS else [],
                    roles=[m.role] if m.role else [],
                )
            )
        return out

    def result(
        status: MatchStatus, selected: list[tuple[Mention, str]], explanation: str | None
    ) -> MatchResult:
        return MatchResult(
            ordinal=requirement.ordinal,
            status=status,
            evidence=refs(selected),
            explanation=explanation,
        )

    held = [(m, lv) for m, lv in degrees if m.role == "affirmed" and LEVEL_RANK[lv] >= need]
    if held:
        return result("supported", held, None)
    negated = [(m, lv) for m, lv in degrees if m.role == "negated" and LEVEL_RANK[lv] >= need]
    if negated:
        return result("contradicted", negated, "The résumé says this degree was not completed.")
    hedged = [(m, lv) for m, lv in degrees if m.role == "hedged" and LEVEL_RANK[lv] >= need]
    if hedged:
        return result(
            "insufficient", hedged, "The degree is described as in progress or only tentatively."
        )
    lower = [(m, lv) for m, lv in degrees if m.role == "affirmed"]
    if lower:
        highest = max(lower, key=lambda p: LEVEL_RANK[p[1]])
        return result(
            "insufficient",
            [highest],
            f"The highest degree found is at {highest[1]} level; {required} level was requested.",
        )
    if "equivalent_ok" in requirement.terms:
        return result(
            "insufficient",
            [],
            "No degree was found. The posting accepts equivalent experience, which can't be verified.",
        )
    return result("no_evidence", [], "No degree was found in the résumé.")
