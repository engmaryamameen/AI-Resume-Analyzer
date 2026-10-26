"""Deciding whether a mention in a résumé passage refers to the thing a requirement asks for."""

from app.lang.taxonomy import Taxonomy
from app.ml.contracts import Mention, Query


def mention_matches_query(taxonomy: Taxonomy, query: Query, mention: Mention) -> bool:
    if mention.type not in {"SKILL", "CERT"}:
        return False
    text = mention.text.strip().lower()
    forms = [f.lower() for f in query.surface_forms if f]
    if mention.type == "CERT":
        return any(f in text or text in f for f in forms)
    term = taxonomy.normalise_surface(mention.text)
    return (term is not None and term in query.term_ids) or text in forms
