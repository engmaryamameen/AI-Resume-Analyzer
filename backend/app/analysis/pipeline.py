"""The analysis pipeline: résumé + requirements + engine -> evidence, summaries and recommendations.

Pure with respect to the database. If the learned engine fails mid-run (time budget, out of memory) the
whole analysis is redone with the rules engine and says so, so results are never a silent mixture.
"""

from collections.abc import Callable, Sequence

from app.analysis import summary
from app.analysis.evidence import match_requirements
from app.analysis.recommendations import build_recommendations
from app.analysis.schema import AnalysisResult, AnalysisWarning, RequirementDraft
from app.core.config import PIPELINE_VERSION
from app.core.logging import get_logger
from app.core.metrics import ENGINE_FALLBACKS
from app.documents.schema import NormalizedDocument, Parseability
from app.ml.engine import Budget, BudgetExceeded, Engine, EngineUnavailable
from app.ml.rules import RulesEngine

log = get_logger(__name__)

LIMITATIONS = [
    *summary.GENERAL_LIMITS,
    "Evidence statuses describe what the résumé's text claims in context. They don't verify that a claim is true.",
    "Years of experience are computed from dated roles and can't be attributed to a single skill.",
    "Models can be wrong, especially on layouts, wording and domains unlike their training data (docs/AI_LIMITATIONS.md).",
]


def analyze(
    doc: NormalizedDocument, parse: Parseability, requirements: Sequence[RequirementDraft],
    engine: Engine, make_budget: Callable[[], Budget],
) -> AnalysisResult:
    try:
        return _run(doc, parse, requirements, engine, make_budget())
    except (BudgetExceeded, EngineUnavailable) as exc:
        reason = "ran out of its time budget" if isinstance(exc, BudgetExceeded) else f"could not run ({exc.reason})"
        log.warning("learned_engine_fell_back", extra={"reason": reason})
        ENGINE_FALLBACKS.labels(reason="budget" if isinstance(exc, BudgetExceeded) else exc.reason[:30]).inc()
        fallback = RulesEngine(notes=[f"The learned models {reason}; this analysis used the rule-based reading."])
        return _run(doc, parse, requirements, fallback, make_budget())


def _run(
    doc: NormalizedDocument, parse: Parseability, requirements: Sequence[RequirementDraft],
    engine: Engine, budget: Budget,
) -> AnalysisResult:
    matches, mentions = match_requirements(doc, requirements, engine, budget)
    warnings = [AnalysisWarning(code=s.code, message=s.message, severity=s.severity)
                for s in parse.signals if s.severity in {"warn", "error"}]
    if not parse.reliable_for_analysis:
        warnings.append(AnalysisWarning(
            code="low_extraction_reliability",
            message="The file was hard to read. Treat “no evidence” results with caution and review the extracted text."))
    if engine.info.mode == "rules":
        warnings.append(AnalysisWarning(
            code="rule_based_reading", severity="info",
            message="This analysis used the rule-based reading, not learned models. It is more literal and "
                    "misses paraphrases that the learned models are meant to catch."))
    return AnalysisResult(
        pipeline_version=PIPELINE_VERSION, engine=engine.info, requirements=list(requirements), matches=matches,
        mentions=mentions,
        assessments=[summary.requirement_evidence(requirements, matches), summary.document_structure(doc),
                     summary.writing_style(doc), summary.extraction_reliability(parse, engine.info)],
        recommendations=build_recommendations(doc, requirements, matches), warnings=warnings, limitations=LIMITATIONS)
