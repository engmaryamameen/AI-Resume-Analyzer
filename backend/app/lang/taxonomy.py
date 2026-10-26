import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Term:
    id: str
    name: str
    category: str
    aliases: tuple[str, ...]
    implies: tuple[str, ...] = ()
    case_sensitive: bool = False
    ambiguous: bool = False
    pattern: re.Pattern[str] = field(default=None, compare=False, repr=False)  # type: ignore[assignment]


@dataclass(frozen=True)
class TermHit:
    term_id: str
    start: int
    end: int


class Taxonomy:
    def __init__(self, terms: list[Term]):
        self.terms = {t.id: t for t in terms}

    def get(self, term_id: str) -> Term:
        return self.terms[term_id]

    def find(self, text: str, *, trusted_context: bool = False) -> list[TermHit]:
        """Find taxonomy terms in text.

        Ambiguous short terms ("C", "R", "Go") only count in a trusted skills context, inside a
        delimited list, or right after a word like "with"/"in"/"using", which avoids matching "Plan R",
        "R&D" or "Go to market".
        """
        hits = [TermHit(term.id, m.start(), m.end()) for term in self.terms.values() for m in term.pattern.finditer(text)]
        if not (trusted_context or _looks_like_list(text)):
            hits = [h for h in hits if not self.terms[h.term_id].ambiguous or _after_skill_preposition(text, h.start)]
        return _drop_overlaps(hits)

    def normalise_surface(self, surface: str) -> str | None:
        """Canonical term id when the whole surface form is a known term or alias, else None."""
        cleaned = surface.strip()
        hits = self.find(cleaned, trusted_context=True)
        if len(hits) == 1 and hits[0].start == 0 and hits[0].end == len(cleaned):
            return hits[0].term_id
        return None

    def surface_forms(self, term_id: str) -> tuple[str, ...]:
        term = self.terms[term_id]
        return (term.name, *term.aliases)

    def ids_in(self, text: str, *, trusted_context: bool = False) -> list[str]:
        seen: list[str] = []
        for h in self.find(text, trusted_context=trusted_context):
            if h.term_id not in seen:
                seen.append(h.term_id)
        return seen

    def implied_by(self, term_id: str) -> set[str]:
        """Transitive closure of implication edges, excluding the term itself."""
        out: set[str] = set()
        stack = list(self.terms[term_id].implies)
        while stack:
            t = stack.pop()
            if t not in out and t in self.terms:
                out.add(t)
                stack.extend(self.terms[t].implies)
        return out


_SKILL_PREPOSITIONS = ("with ", "in ", "using ", "of ", "and ", "or ", ", ", "/")


def _after_skill_preposition(text: str, start: int) -> bool:
    return text[:start].lower().endswith(_SKILL_PREPOSITIONS)


def _looks_like_list(text: str) -> bool:
    return len(re.findall(r"[,;/|•·]", text)) >= 2


def _drop_overlaps(hits: list[TermHit]) -> list[TermHit]:
    """Prefer the longest match when two aliases overlap (e.g. 'Spring Boot' over 'Spring')."""
    ordered = sorted(hits, key=lambda h: (h.start, -(h.end - h.start)))
    kept: list[TermHit] = []
    for h in ordered:
        if kept and h.start < kept[-1].end:
            continue
        kept.append(h)
    return kept


def _compile(forms: list[str], case_sensitive: bool) -> re.Pattern[str]:
    alts = "|".join(re.escape(f) for f in sorted(set(forms), key=len, reverse=True))
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(rf"(?<![\w+#.])(?:{alts})(?![\w+#]|\.\w)", flags)


@lru_cache
def get_taxonomy() -> Taxonomy:
    raw = json.loads(Path(__file__).with_name("taxonomy.json").read_text(encoding="utf-8"))
    terms = []
    for t in raw["terms"]:
        cs = bool(t.get("case_sensitive"))
        forms = [t["name"], *t.get("aliases", [])]
        terms.append(Term(
            id=t["id"], name=t["name"], category=t["category"], aliases=tuple(t.get("aliases", [])),
            implies=tuple(t.get("implies", [])), case_sensitive=cs,
            ambiguous=bool(t.get("ambiguous")), pattern=_compile(forms, cs),
        ))
    ids = {t.id for t in terms}
    for t in terms:
        missing = set(t.implies) - ids
        if missing:
            raise ValueError(f"taxonomy term {t.id} implies unknown {sorted(missing)}")
    return Taxonomy(terms)
