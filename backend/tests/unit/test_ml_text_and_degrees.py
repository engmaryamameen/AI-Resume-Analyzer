"""Chunking, BIO decoding, BM25 and degree recognition."""

import pytest

from app.ml.bm25 import Bm25Index
from app.ml.decoding import chunk_text, spans_from_labels, trim_span, truncate_context
from app.ml.degree import degree_level, find_degrees


class TestChunking:
    def test_short_text_is_one_chunk(self):
        assert chunk_text("One sentence.") == [(0, "One sentence.")]

    def test_long_text_splits_at_sentences_and_offsets_line_up(self):
        text = " ".join(f"Sentence number {i} says something useful." for i in range(60))
        chunks = chunk_text(text, max_chars=200)
        assert len(chunks) > 1
        assert all(len(c) <= 200 for _, c in chunks)
        assert all(text[offset: offset + len(chunk)] == chunk for offset, chunk in chunks)
        assert all(c.rstrip().endswith(".") for _, c in chunks[:-1])

    def test_text_without_boundaries_is_cut_at_the_limit(self):
        chunks = chunk_text("x" * 450, max_chars=200)
        assert [len(c) for _, c in chunks] == [200, 200, 50]

    def test_context_is_truncated_with_an_ellipsis(self):
        assert truncate_context("a" * 500).endswith("…") and len(truncate_context("a" * 500)) <= 160


class TestBioDecoding:
    OFFSETS = [(0, 5), (6, 11), (12, 18), (19, 22), (23, 30)]

    def test_adjacent_tokens_form_one_span(self):
        spans = spans_from_labels(["O", "B-SKILL", "I-SKILL", "O", "B-DEGREE"], self.OFFSETS)
        assert [(s.start, s.end, s.type, s.first_token) for s in spans] == [(6, 18, "SKILL", 1), (23, 30, "DEGREE", 4)]

    def test_inside_label_without_an_open_span_starts_one(self):
        assert [(s.start, s.type) for s in spans_from_labels(["I-ORG", "I-ORG", "O", "O", "O"], self.OFFSETS)] == [(0, "ORG")]

    def test_type_change_closes_the_span(self):
        spans = spans_from_labels(["B-SKILL", "I-FIELD", "O", "O", "O"], self.OFFSETS)
        assert [s.type for s in spans] == ["SKILL", "FIELD"]

    def test_trim_span_removes_surrounding_whitespace(self):
        assert trim_span("a  Python  b", 1, 10) == (3, 9)


class TestBm25:
    DOCS = ["Built services in Python and Django", "Managed the quarterly newsletter", "Deployed Python scripts nightly"]

    def test_documents_with_the_query_terms_rank_first(self):
        top = Bm25Index(self.DOCS).top("Python Django", 3)
        assert [i for i, _ in top] == [0, 2]

    def test_documents_without_overlap_are_not_returned(self):
        assert Bm25Index(self.DOCS).top("Kubernetes", 3) == []

    def test_empty_index_is_safe(self):
        assert Bm25Index([]).top("anything", 3) == []


class TestDegrees:
    def spans(self, text, section="experience"):
        return [text[s.start: s.end] for s in find_degrees(text, section)]

    @pytest.mark.parametrize("text,section", [
        ("Relocated to Boston, MA in 2019", "experience"),
        ("Member of the nurses' association in Worcester, MA", "experience"),
        ("Administered MS Office for 200 staff", "experience"),
        ("Rolled out MS Teams to three offices", "experience"),
        ("Drafted BS EN ISO 9001 checklists", "experience"),
    ])
    def test_ambiguous_abbreviations_are_not_degrees(self, text, section):
        assert self.spans(text, section) == []

    @pytest.mark.parametrize("text,section,expected", [
        ("MS in Statistics, Summit College", "education", ["MS"]),
        ("She earned an MA from Riverside", "experience", ["MA"]),
        ("B.S. in Biology", "education", ["B.S."]),
        ("MBA, Example Business School", "education", ["MBA"]),
        ("Master of Science in Data Science", "education", ["Master of"]),
    ])
    def test_genuine_degrees_are_found(self, text, section, expected):
        assert self.spans(text, section) == expected

    @pytest.mark.parametrize("text,level", [
        ("BSc Computer Science", "bachelor"), ("Bachelor of Arts, History", "bachelor"),
        ("M.Sc. Data Science", "master"), ("MBA", "master"), ("PhD in Physics", "doctorate"),
        ("Associate degree", "associate"), ("High school diploma", None),
    ])
    def test_levels(self, text, level):
        assert degree_level(text) == level
