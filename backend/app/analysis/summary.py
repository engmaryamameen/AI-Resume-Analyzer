"""Descriptive summaries of an analysis.

Deliberately not scores. Each metric is a count, a share of a stated population or a duration, and
carries its own definition. There is no overall rating: a single number would hide the evidence and
would need a calibration this system does not have.
"""

from collections import Counter
from collections.abc import Callable, Sequence
from statistics import median

from app.analysis.schema import Assessment, MatchResult, MatchStatus, Metric, RequirementDraft
from app.documents.schema import NormalizedDocument, Parseability
from app.lang.text import has_action_verb, has_metric, weak_opener, word_count
from app.ml.contracts import EngineInfo

STATUSES: tuple[MatchStatus, ...] = (
    "supported",
    "mentioned_only",
    "contradicted",
    "insufficient",
    "no_evidence",
)
_PRIORITY = {status: rank for rank, status in enumerate(STATUSES)}
GENERAL_LIMITS = [
    "These figures describe how the wording of this résumé relates to the wording of this posting. They do "
    "not predict interview or hiring outcomes and are not an applicant-tracking-system rating."
]


def _collapse_alternatives(
    requirements: Sequence[RequirementDraft], matches: Sequence[MatchResult]
) -> list[tuple[RequirementDraft, MatchResult]]:
    """Requirements joined by "or" count once, using the best-supported alternative."""
    best: dict[int, tuple[RequirementDraft, MatchResult]] = {}
    out: list[tuple[RequirementDraft, MatchResult]] = []
    for requirement, match in zip(requirements, matches, strict=True):
        group = (requirement.source_span or {}).get("alt_group")
        if group is None:
            out.append((requirement, match))
        elif group not in best or _PRIORITY[match.status] < _PRIORITY[best[group][1].status]:
            best[group] = (requirement, match)
    return out + list(best.values())


def requirement_evidence(
    requirements: Sequence[RequirementDraft], matches: Sequence[MatchResult]
) -> Assessment:
    explicit = [
        (r, m) for r, m in _collapse_alternatives(requirements, matches) if r.origin != "inferred"
    ]
    metrics: list[Metric] = []
    for kind, label in (("required", "must-have"), ("preferred", "nice-to-have")):
        counts = Counter(m.status for r, m in explicit if r.kind == kind)
        metrics.append(
            Metric(
                name=f"{kind}_total",
                value=sum(counts.values()),
                unit="count",
                definition=f"Number of {label} requirements found in the posting (alternatives count once).",
            )
        )
        metrics += [
            Metric(
                name=f"{kind}_{status}",
                value=counts[status],
                unit="count",
                definition=f"{label.capitalize()} requirements whose evidence status is “{status}”.",
            )
            for status in STATUSES
        ]
    conflicts = sum(1 for _, m in explicit if m.conflict)
    metrics.append(
        Metric(
            name="conflicting_evidence",
            value=conflicts,
            unit="count",
            definition="Requirements where the résumé both supports and contradicts the requirement.",
        )
    )
    return Assessment(
        id="requirement_evidence",
        label="Requirements and evidence",
        summary="How many requirements the résumé supports, only mentions, contradicts, leaves unclear or never touches.",
        metrics=metrics,
        limitations=[
            *GENERAL_LIMITS,
            "Only requirements recognised in the posting are counted; check the extracted list for omissions.",
            "“Supported” means the résumé's text claims it in context. It does not verify that the claim is true.",
        ],
    )


def document_structure(doc: NormalizedDocument) -> Assessment:
    kinds = [s.kind for s in doc.sections if s.block_ids and s.kind != "header"]
    kind_of = doc.section_kind_by_id()
    experience = [e for e in doc.entries if kind_of.get(e.section_id) == "experience"]
    metrics = [
        Metric(
            name="sections_found",
            value=", ".join(kinds) or "none",
            unit="text",
            definition="Section headings the reader recognised.",
        ),
        Metric(
            name="roles_with_dates",
            value=len([e for e in experience if e.date_range]),
            unit="count",
            definition="Experience entries that have a parseable date range.",
        ),
        Metric(
            name="roles_total",
            value=len(experience),
            unit="count",
            definition="Experience entries found.",
        ),
        Metric(
            name="contact_details_found",
            value="yes" if doc.contact.email.value or doc.contact.phone.value else "no",
            unit="text",
            definition="Whether an email address or phone number was detected.",
        ),
    ]
    if doc.total_experience_months is not None:
        metrics.append(
            Metric(
                name="dated_experience",
                value=doc.total_experience_months,
                unit="months",
                definition="Months covered by dated roles, counting overlapping periods once.",
            )
        )
    return Assessment(
        id="document_structure",
        label="Structure",
        summary="What the reader found in the file's structure.",
        metrics=metrics,
        limitations=[
            *GENERAL_LIMITS,
            "A missing element may be a reading miss rather than a real omission; check the "
            "extraction review. Many roles don't need every section.",
        ],
    )


def writing_style(doc: NormalizedDocument) -> Assessment:
    kinds = doc.section_kind_by_id()
    bullets = [
        b
        for b in doc.blocks
        if b.kind == "bullet"
        and kinds.get(b.section_id) in {"experience", "projects", "volunteering", "other"}
    ]
    limits = [
        *GENERAL_LIMITS,
        "Describes surface style only. It can't judge accuracy or relevance, and style norms differ between fields.",
    ]
    if len(bullets) < 3:
        return Assessment(
            id="writing_style",
            label="Writing style",
            summary="Fewer than three experience or project bullets were found, too few to describe.",
            limitations=limits,
        )

    def share(predicate: Callable[[str], bool]) -> int:
        return round(100 * sum(1 for b in bullets if predicate(b.text)) / len(bullets))

    return Assessment(
        id="writing_style",
        label="Writing style",
        summary=f"Surface features of {len(bullets)} experience and project bullets.",
        metrics=[
            Metric(
                name="bullets_analysed",
                value=len(bullets),
                unit="count",
                definition="Bullets in experience, projects or volunteering.",
            ),
            Metric(
                name="start_with_action_verb",
                value=share(lambda t: has_action_verb(t) and not weak_opener(t)),
                unit="percent",
                definition="Share of bullets whose first words are an action verb and not a weak opener.",
            ),
            Metric(
                name="weak_openers",
                value=share(lambda t: bool(weak_opener(t))),
                unit="percent",
                definition="Share of bullets starting with phrases like “Responsible for” or “Worked on”.",
            ),
            Metric(
                name="contain_a_quantity",
                value=share(has_metric),
                unit="percent",
                definition="Share of bullets containing a number with a unit. Only add figures you can verify.",
            ),
            Metric(
                name="median_words_per_bullet",
                value=int(median(word_count(b.text) for b in bullets)),
                unit="count",
                definition="Median bullet length in words.",
            ),
        ],
        limitations=limits,
    )


def extraction_reliability(parse: Parseability, engine: EngineInfo) -> Assessment:
    mode = (
        "Local semantic models with deterministic entity/date checks"
        if engine.mode == "semantic"
        else "Learned models (locally executed)"
        if engine.mode == "learned"
        else "Rule-based reading (no learned models were used)"
    )
    metrics = [
        Metric(
            name="file_readability",
            value=parse.level,
            unit="text",
            definition="How reliably text and structure were read from the file: good, fair or poor.",
        ),
        Metric(
            name="analysis_engine",
            value=mode,
            unit="text",
            definition="Which engine produced the evidence statuses for this analysis.",
        ),
        Metric(
            name="probabilities_calibrated",
            value="yes" if engine.calibrated else "no",
            unit="text",
            definition="Whether model probabilities were calibrated and met the display policy.",
        ),
    ]
    return Assessment(
        id="extraction_reliability",
        label="How this was read",
        summary="How far to trust the reading of the file and which engine produced the results.",
        metrics=metrics,
        limitations=[
            "Low readability makes every other result less certain.",
            *(
                [f"Learned models were not used: {note}" for note in engine.notes]
                if engine.mode == "rules"
                else []
            ),
        ],
    )
