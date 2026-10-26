"""Text windowing and BIO decoding for the extractor. Pure Python (no torch), shared by training and inference."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

MAX_CONTEXT_CHARS = 160
MAX_CHUNK_CHARS = 700
_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+")


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    type: str
    first_token: int  # index (in the sequence given to spans_from_labels) of the span's first token


def truncate_context(context: str) -> str:
    return context if len(context) <= MAX_CONTEXT_CHARS else context[: MAX_CONTEXT_CHARS - 1] + "…"


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[tuple[int, str]]:
    """Split long text at sentence boundaries into (offset, chunk) pieces no longer than max_chars."""
    if len(text) <= max_chars:
        return [(0, text)]
    boundaries = [m.end() for m in _SENTENCE_END.finditer(text)]
    chunks: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        limit = start + max_chars
        if limit >= len(text):
            cut = len(text)
        else:
            usable = [b for b in boundaries if start < b <= limit]
            cut = usable[-1] if usable else limit
        piece = text[start:cut]
        if piece.strip():
            chunks.append((start, piece))
        start = cut
    return chunks


def spans_from_labels(labels: Sequence[str], offsets: Sequence[tuple[int, int]]) -> list[Span]:
    """Turn per-token BIO labels into character spans. An I- label with no open span of its type starts one."""
    spans: list[Span] = []
    current: list | None = None  # [start, end, type, first_token]

    def close() -> None:
        nonlocal current
        if current is not None:
            spans.append(Span(current[0], current[1], current[2], current[3]))
            current = None

    for index, (label, (start, end)) in enumerate(zip(labels, offsets, strict=True)):
        if label == "O":
            close()
            continue
        prefix, _, kind = label.partition("-")
        if prefix == "I" and current is not None and current[2] == kind:
            current[1] = end
        else:
            close()
            current = [start, end, kind, index]
    close()
    return spans


def trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end
