"""Small dependency-free text utilities shared by the rules engine, retrieval baseline and summaries."""

import re

ACTION_VERBS = frozenset(
    """
accelerated achieved administered analysed analyzed architected assembled audited authored automated
built championed coached collaborated configured consolidated constructed contributed converted
coordinated created debugged decreased delivered deployed designed developed diagnosed directed
drove eliminated enabled engineered enhanced established evaluated executed expanded facilitated
founded generated guided identified implemented improved increased initiated integrated introduced
investigated launched led maintained managed mentored migrated modelled modeled monitored negotiated
operated optimised optimized orchestrated organised organized overhauled owned partnered piloted
planned presented prioritised prioritized produced programmed published rebuilt redesigned reduced
refactored released remediated replaced researched resolved restructured reviewed revised scaled
secured selected shipped simplified solved spearheaded standardised standardized streamlined
supervised supported tested trained transformed troubleshot upgraded used validated wrote
""".split()
)

WEAK_OPENERS = (
    "responsible for",
    "worked on",
    "helped with",
    "helped to",
    "assisted with",
    "assisted in",
    "duties included",
    "involved in",
    "tasked with",
    "in charge of",
)

_STOPWORDS = frozenset(
    """
a an and are as at be been by for from has have in into is it its of on or our that the their this
to was were will with you your we they them who which what when where how all any can may must
should would such than then also more most other some etc including include within across using
use used able ability strong good great plus well work working experience years year
""".split()
)

_TOKEN = re.compile(r"[a-z][a-z0-9+#]*")
_METRIC = re.compile(
    r"(\b\d[\d,.]*\s?(?:%|percent|x\b|k\b|m\b|million|billion|ms\b|seconds?|minutes?|hours?|days?|"
    r"users?|customers?|requests?|rps|qps|tps|engineers?|people|members|services?|teams?|"
    r"repos?|endpoints?|tickets?|clients?)|[$€£]\s?\d)",
    re.I,
)
_LIST_SEPARATORS = re.compile(r"[,;|/•·]")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def stem(word: str) -> str:
    for suffix in ("ingly", "edly", "ing", "ed", "ly", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def content_tokens_list(text: str) -> list[str]:
    return [stem(t) for t in tokens(text) if t not in _STOPWORDS and len(t) > 2]


def content_tokens(text: str) -> set[str]:
    return set(content_tokens_list(text))


def has_action_verb(text: str, window: int = 3) -> bool:
    """True if one of the first `window` words is an action verb."""
    return any(w.strip(".,:;").lower() in ACTION_VERBS for w in text.split()[:window])


def mentions_action_verb(text: str) -> bool:
    """True if any word in the text is an action verb."""
    return any(w in ACTION_VERBS for w in tokens(text))


def weak_opener(text: str) -> str | None:
    lowered = text.lower().lstrip()
    return next((w for w in WEAK_OPENERS if lowered.startswith(w)), None)


def has_metric(text: str) -> bool:
    return bool(_METRIC.search(text))


def word_count(text: str) -> int:
    return len(text.split())


def is_list_like(text: str) -> bool:
    """A line that enumerates items (a skills list, "Tech stack: A, B, C") rather than describing work."""
    if len(_LIST_SEPARATORS.findall(text)) < 2:
        return False
    chunks = [c for c in _LIST_SEPARATORS.split(text) if c.strip()]
    return sum(len(c.split()) for c in chunks) / max(len(chunks), 1) <= 3.5
