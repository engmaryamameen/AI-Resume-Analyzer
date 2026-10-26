"""Combining the outputs of verification and extraction into one requirement status.

Pure functions, no models: this is the documented decision table, unit-testable without any weights.

Two independent signals describe each candidate passage:
  * the verifier's label for (requirement, passage), and
  * the role the extractor gave to mentions of the requirement's term inside that passage.
When they agree the label stands. When they disagree the weaker claim wins (and the disagreement is
reported), except that an explicit negation outranks a mere mention. Across passages, supporting and
contradicting evidence together mean "conflicting", never "supported".
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from app.ml.contracts import MentionRole, Verdict, VerdictLabel

Status = Literal["supported", "mentioned_only", "contradicted", "insufficient", "no_evidence"]

_ROLE_TO_LABEL: dict[str, VerdictLabel] = {
    "affirmed": "supports", "listed": "mentions_only", "mentioned": "mentions_only",
    "negated": "contradicts", "hedged": "insufficient",
}
_COMBINED: dict[frozenset[str], VerdictLabel] = {
    frozenset({"supports", "mentions_only"}): "mentions_only",
    frozenset({"supports", "insufficient"}): "insufficient",
    frozenset({"supports", "contradicts"}): "insufficient",
    frozenset({"mentions_only", "insufficient"}): "insufficient",
    frozenset({"mentions_only", "contradicts"}): "contradicts",
    frozenset({"insufficient", "contradicts"}): "contradicts",
}
_STATUS: dict[str, Status] = {
    "supports": "supported", "mentions_only": "mentioned_only", "contradicts": "contradicted",
    "insufficient": "insufficient",
}
_PRIORITY = ("supports", "contradicts", "mentions_only", "insufficient")


@dataclass(frozen=True)
class CandidateEvidence:
    passage_id: str
    verdict: Verdict
    linked_roles: tuple[MentionRole, ...] = ()
    retrieval_score: float | None = None
    retrieval_method: str | None = None


@dataclass(frozen=True)
class JudgedEvidence:
    candidate: CandidateEvidence
    label: VerdictLabel
    agreed: bool  # verifier and extractor said the same thing (or only one of them spoke)


@dataclass(frozen=True)
class Decision:
    status: Status
    conflict: bool = False
    evidence: list[JudgedEvidence] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    probability: float | None = None  # calibrated; None whenever no calibrated estimate applies


def role_label(roles: Sequence[MentionRole]) -> VerdictLabel | None:
    """The single label implied by several mentions in one passage: affirmed beats negated beats the rest."""
    labels = {_ROLE_TO_LABEL[r] for r in roles}
    for label in ("supports", "contradicts", "insufficient", "mentions_only"):
        if label in labels:
            return label  # type: ignore[return-value]
    return None


def combine(verifier: VerdictLabel, from_roles: VerdictLabel | None) -> tuple[VerdictLabel, bool]:
    if from_roles is None or from_roles == verifier:
        return verifier, True
    if "unrelated" in (verifier, from_roles):
        # A linked mention exists, so the passage is related; trust the extractor's reading of it.
        return (from_roles, False) if verifier == "unrelated" else (verifier, False)
    return _COMBINED[frozenset({verifier, from_roles})], False


def decide(candidates: Sequence[CandidateEvidence]) -> Decision:
    judged = []
    for c in candidates:
        label, agreed = combine(c.verdict.label, role_label(c.linked_roles))
        judged.append(JudgedEvidence(c, label, agreed))
    related = [j for j in judged if j.label != "unrelated"]
    if not related:
        return Decision("no_evidence", reasons=["No passage in the résumé is related to this requirement."])

    labels = {j.label for j in related}
    conflict = {"supports", "contradicts"} <= labels
    chosen: VerdictLabel = "insufficient" if conflict else next(p for p in _PRIORITY if p in labels)  # type: ignore[assignment]
    ordered = sorted(related, key=lambda j: (j.label != chosen, _PRIORITY.index(j.label), -(j.candidate.retrieval_score or 0)))

    reasons = []
    if conflict:
        reasons.append("The résumé both supports and contradicts this requirement; review the passages.")
    if any(not j.agreed for j in ordered[:1]):
        reasons.append("The verifier and the extractor read the strongest passage differently; the more "
                       "cautious reading was used.")
    best = ordered[0]
    probability = None
    if not conflict and best.agreed and best.label == chosen and best.candidate.verdict.probs:
        probability = best.candidate.verdict.probs.get(chosen)
    return Decision(_STATUS[chosen], conflict, ordered, reasons, probability)
