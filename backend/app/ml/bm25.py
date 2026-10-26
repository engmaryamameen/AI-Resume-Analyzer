"""BM25 lexical retrieval. The retrieval baseline: used by the rules engine and by model evaluation."""

import math
from collections import Counter
from collections.abc import Sequence

from app.lang.text import content_tokens_list


class Bm25Index:
    def __init__(self, documents: Sequence[str], k1: float = 1.5, b: float = 0.75):
        self._docs = [Counter(content_tokens_list(d)) for d in documents]
        self._lengths = [sum(c.values()) for c in self._docs]
        self._avg = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0
        self._k1, self._b = k1, b
        df: Counter[str] = Counter()
        for doc in self._docs:
            df.update(doc.keys())
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, query: str) -> list[float]:
        terms = set(content_tokens_list(query))
        out = []
        for doc, length in zip(self._docs, self._lengths, strict=True):
            score = 0.0
            for t in terms:
                tf = doc.get(t, 0)
                if tf:
                    norm = tf + self._k1 * (1 - self._b + self._b * length / (self._avg or 1.0))
                    score += self._idf[t] * tf * (self._k1 + 1) / norm
            out.append(score)
        return out

    def top(self, query: str, k: int) -> list[tuple[int, float]]:
        ranked = sorted(enumerate(self.scores(query)), key=lambda p: -p[1])
        return [(i, s) for i, s in ranked[:k] if s > 0]
