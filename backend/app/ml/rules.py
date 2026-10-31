"""Deterministic baseline engine. Not machine learning.

Mentions come from the vocabulary and degree rules; roles from cue lists (negation, hedging, list
shape, a verb in the sentence); retrieval is BM25; verification maps the role of the linked mention
to a verdict. It is deliberately conservative: lexical overlap alone never yields "supports" for a
requirement that has no linked mention, and it reports no probabilities.
"""

import re
from collections.abc import Sequence

from app.lang.taxonomy import get_taxonomy
from app.lang.text import content_tokens, is_list_like, mentions_action_verb
from app.ml.bm25 import Bm25Index
from app.ml.contracts import (
    ROLE_TYPES,
    Candidate,
    EngineInfo,
    Mention,
    MentionRole,
    MentionType,
    Passage,
    Query,
    Verdict,
    VerdictLabel,
)
from app.ml.degree import find_degrees
from app.ml.engine import Budget
from app.ml.linking import mention_matches_query

EXPERIENCE_SECTIONS = {"experience", "projects", "volunteering", "other"}
_CLAUSE_BREAK = re.compile(r"[.;]|\bbut\b|\bhowever\b", re.IGNORECASE)
_NEGATION = re.compile(
    r"\b(?:no|not|never|without|lack(?:s|ing)?|none|zero|unfamiliar|nor|cannot)\b|n't\b",
    re.IGNORECASE,
)
_NEGATED_STATE = re.compile(
    r"\b(?:did not (?:complete|finish)|left before|left\b[^.;]{0,80}\bbefore finishing|dropped out|incomplete|unfinished)\b",
    re.IGNORECASE,
)
_HEDGE = re.compile(
    r"\b(?:learning|studying|exploring|familiar(?:ity)? with|exposure to|basic knowledge of|beginner|"
    r"interested in|aspir\w+|seeking|plan(?:ning)? to|want(?:ing)? to|in progress|pursuing|"
    r"working towards?|enrolled in|expected|candidate for)\b",
    re.IGNORECASE,
)
_HEDGE_AFTER = re.compile(r"^\s*(?:basics|fundamentals|\((?:basic|beginner)\))", re.IGNORECASE)
_CERTIFICATION = re.compile(
    r"\b(?:PMP|CISSP|CISM|CKA|CKAD|CKS|CCNA|CCNP|CPA|CFA|CompTIA [A-Z+0-9]+|AWS Certified [A-Za-z ]+?(?=[,.;(–—-]|$)|"
    r"Azure [A-Za-z ]*?(?:Associate|Fundamentals|Expert)|Google Cloud Certified[ -]*[A-Za-z ]+?(?=[,.;(–—-]|$)|"
    r"Certified [A-Z][A-Za-z ]+?(?=[,.;(–—-]|$)|Scrum Master)\b"
)
_WINDOW = 70
_NEGATION_WORDS = 4  # a negation only applies to a mention within a few words after it
_HEDGE_WORDS = 6
_SUPPORT_COVERAGE = 0.8
_RELATED_COVERAGE = 0.35


class RulesEngine:
    def __init__(self, notes: Sequence[str] = ()):
        self.info = EngineInfo(mode="rules", fingerprint="rules", notes=list(notes))
        self._taxonomy = get_taxonomy()

    # ----- extraction -----------------------------------------------------------------------------
    def extract(self, passages: Sequence[Passage], budget: Budget) -> list[Mention]:
        out: list[Mention] = []
        for passage in passages:
            budget.check()
            out.extend(self._mentions(passage))
        return out

    def _mentions(self, passage: Passage) -> list[Mention]:
        found: list[tuple[int, int, MentionType]] = []
        in_skills = passage.section_kind == "skills"
        for hit in self._taxonomy.find(passage.text, trusted_context=in_skills):
            found.append((hit.start, hit.end, "SKILL"))
        found += [
            (s.start, s.end, "DEGREE") for s in find_degrees(passage.text, passage.section_kind)
        ]
        found += self._certifications(passage)
        mentions = []
        for start, end, kind in sorted(found):
            role = self._role(passage, start, end, kind) if kind in ROLE_TYPES else None
            mentions.append(
                Mention(
                    passage_id=passage.id,
                    start=start,
                    end=end,
                    text=passage.text[start:end],
                    type=kind,
                    role=role,
                    source="rules",
                )
            )
        return mentions

    @staticmethod
    def _certifications(passage: Passage) -> list[tuple[int, int, MentionType]]:
        spans = [(m.start(), m.end(), "CERT") for m in _CERTIFICATION.finditer(passage.text)]
        if not spans and passage.section_kind == "certifications":
            head = re.split(r"[,–—(0-9]", passage.text, maxsplit=1)[0].strip()
            if head:
                start = passage.text.index(head)
                spans = [(start, start + len(head), "CERT")]
        return spans  # type: ignore[return-value]

    @staticmethod
    def _role(passage: Passage, start: int, end: int, kind: str) -> MentionRole:
        text = passage.text
        breaks = [m.end() for m in _CLAUSE_BREAK.finditer(text[:start])]
        words = text[(breaks[-1] if breaks else 0) : start].split()
        near_negation, near_hedge = (
            " ".join(words[-_NEGATION_WORDS:]),
            " ".join(words[-_HEDGE_WORDS:]),
        )
        after = text[end:]
        if _NEGATION.search(near_negation) or _NEGATED_STATE.search(
            near_negation + " " + after[:_WINDOW]
        ):
            return "negated"
        if _HEDGE.search(near_hedge) or _HEDGE_AFTER.match(after):
            return "hedged"
        if kind != "SKILL":
            return "affirmed"
        if passage.section_kind == "skills" or is_list_like(text):
            return "listed"
        if passage.section_kind in EXPERIENCE_SECTIONS and mentions_action_verb(text):
            return "affirmed"
        return "mentioned"

    # ----- retrieval ------------------------------------------------------------------------------
    def retrieve(
        self, queries: Sequence[Query], passages: Sequence[Passage], k: int, budget: Budget
    ) -> dict[str, list[Candidate]]:
        index = Bm25Index([p.text for p in passages])
        result: dict[str, list[Candidate]] = {}
        for query in queries:
            budget.check()
            result[query.id] = [
                Candidate(passage_id=passages[i].id, score=score, method="bm25")
                for i, score in index.top(query.retrieval_query, k)
            ]
        return result

    # ----- verification ---------------------------------------------------------------------------
    def verify(self, pairs: Sequence[tuple[Query, Passage]], budget: Budget) -> list[Verdict]:
        verdicts = []
        for query, passage in pairs:
            budget.check()
            verdicts.append(Verdict(label=self._label(query, passage), source="rules"))
        return verdicts

    def _label(self, query: Query, passage: Passage) -> VerdictLabel:
        linked = [
            m for m in self._mentions(passage) if mention_matches_query(self._taxonomy, query, m)
        ]
        if linked:
            roles = {m.role for m in linked}
            if "affirmed" in roles:
                return "supports"
            if "negated" in roles:
                return "contradicts"
            if "hedged" in roles:
                return "insufficient"
            return "mentions_only"
        wanted = content_tokens(query.retrieval_query)
        coverage = len(wanted & content_tokens(passage.text)) / len(wanted) if wanted else 0.0
        if (
            not query.term_ids
            and coverage >= _SUPPORT_COVERAGE
            and passage.section_kind in EXPERIENCE_SECTIONS
            and mentions_action_verb(passage.text)
        ):
            return "supports"
        return "insufficient" if coverage >= _RELATED_COVERAGE else "unrelated"
