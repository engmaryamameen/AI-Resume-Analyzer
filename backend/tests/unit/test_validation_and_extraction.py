"""Upload validation and sandboxed extraction.

Invariants: file type is decided by content; filenames never reach the filesystem; hostile or
corrupt documents fail closed with a stable error code and never produce invented text.
"""

import io
import os
import signal
import subprocess
import zipfile

import pytest

from app.core.config import get_settings
from app.core.errors import PayloadTooLarge, UnsupportedMedia, ValidationFailed
from app.documents.isolated import ExtractionFailed, run_extraction
from app.documents.validation import display_title, validate_upload
from tests.helpers import make_docx, make_pdf

MAX = 5 * 1024 * 1024


class TestValidation:
    def test_empty_file_rejected(self):
        with pytest.raises(ValidationFailed) as e:
            validate_upload("cv.pdf", b"", MAX)
        assert e.value.code == "empty_file"

    def test_oversized_upload_rejected(self):
        with pytest.raises(PayloadTooLarge) as e:
            validate_upload("cv.pdf", b"%PDF-" + b"0" * MAX, MAX)
        assert e.value.code == "file_too_large"

    def test_pdf_accepted_by_content(self):
        assert validate_upload("cv.pdf", make_pdf([["hi"]]), MAX).kind == "pdf"

    def test_docx_accepted_by_content(self):
        assert validate_upload("cv.docx", make_docx(["hi"]), MAX).kind == "docx"

    def test_extension_must_match_content(self):
        with pytest.raises(ValidationFailed) as e:
            validate_upload("cv.pdf", make_docx(["hi"]), MAX)
        assert e.value.code == "file_type_mismatch"

    def test_executable_extension_rejected_even_with_pdf_bytes(self):
        with pytest.raises(UnsupportedMedia):
            validate_upload("cv.exe", make_pdf([["hi"]]), MAX)

    def test_legacy_doc_gets_actionable_error(self):
        with pytest.raises(UnsupportedMedia) as e:
            validate_upload("cv.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 100, MAX)
        assert e.value.code == "legacy_doc_unsupported"

    def test_unknown_bytes_rejected(self):
        with pytest.raises(UnsupportedMedia) as e:
            validate_upload("cv.pdf", b"just some text", MAX)
        assert e.value.code == "unsupported_file_type"

    def test_truncated_zip_is_reported_as_corrupt(self):
        with pytest.raises(ValidationFailed) as e:
            validate_upload("cv.docx", b"PK\x03\x04 not really a zip", MAX)
        assert e.value.code == "docx_corrupt"

    @pytest.mark.security
    @pytest.mark.parametrize("name,expected", [
        ("../../etc/passwd.pdf", "passwd"),
        ("C:\\Users\\victim\\cv.pdf", "cv"),
        ("name\x00with\u202ebidi.pdf", "namewithbidi"),
        ("", "Résumé"),
        ("...pdf", "Résumé"),
    ])
    def test_dangerous_filenames_become_safe_labels(self, name, expected):
        assert display_title(name) == expected

    def test_long_filename_is_truncated(self):
        assert len(display_title("a" * 500 + ".pdf")) <= 120


class TestExtractionSandbox:
    def test_text_pdf_extracts_lines_and_pages(self, tmp_path):
        p = tmp_path / "a"
        p.write_bytes(make_pdf([["Jane Doe", "Python developer"], ["Second page"]]))
        raw = run_extraction(p, "pdf")
        assert raw.page_count == 2
        assert [l.text for l in raw.lines][:2] == ["Jane Doe", "Python developer"]
        assert raw.lines[-1].page == 2

    def test_corrupt_pdf_fails_closed(self, tmp_path):
        p = tmp_path / "a"
        p.write_bytes(b"%PDF-1.4\nthis is not a pdf body\n%%EOF")
        with pytest.raises(ExtractionFailed) as e:
            run_extraction(p, "pdf")
        assert e.value.code == "pdf_corrupt"

    def test_page_limit_enforced(self, tmp_path, monkeypatch):
        monkeypatch.setattr(get_settings(), "max_pdf_pages", 2)
        p = tmp_path / "a"
        p.write_bytes(make_pdf([["one"], ["two"], ["three"]]))
        with pytest.raises(ExtractionFailed) as e:
            run_extraction(p, "pdf")
        assert e.value.code == "too_many_pages"

    def test_docx_paragraphs_and_bullets(self, tmp_path):
        p = tmp_path / "a"
        p.write_bytes(make_docx(["Heading", "did a thing"], bullets={1}))
        raw = run_extraction(p, "docx")
        assert [(l.text, l.bullet) for l in raw.lines] == [("Heading", False), ("did a thing", True)]

    @pytest.mark.security
    def test_docx_compression_bomb_rejected(self, tmp_path):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("word/document.xml", "<w:document>" + " " * 3_000_000 + "</w:document>")
        p = tmp_path / "a"
        p.write_bytes(buf.getvalue())
        with pytest.raises(ExtractionFailed) as e:
            run_extraction(p, "docx")
        assert e.value.code == "docx_compression_ratio"

    @pytest.mark.security
    def test_docx_with_macro_part_rejected(self, tmp_path):
        p = tmp_path / "a"
        p.write_bytes(make_docx(["x"], extra={"word/vbaProject.bin": b"\x00"}))
        with pytest.raises(ExtractionFailed) as e:
            run_extraction(p, "docx")
        assert e.value.code == "docx_macro"

    @pytest.mark.security
    def test_docx_xml_entity_expansion_rejected(self, tmp_path):
        evil = (
            b'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "AAAA"><!ENTITY b "&a;&a;&a;&a;">]>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b"<w:body><w:p><w:r><w:t>&b;</w:t></w:r></w:p></w:body></w:document>"
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("word/document.xml", evil)
        p = tmp_path / "a"
        p.write_bytes(buf.getvalue())
        with pytest.raises(ExtractionFailed) as e:
            run_extraction(p, "docx")
        assert e.value.code == "docx_corrupt"

    def test_timeout_kills_the_whole_process_group_and_reports_a_stable_code(self, tmp_path, monkeypatch):
        killed = []

        class Hung:
            pid = 4242

            def __init__(self, *args, **kwargs):
                pass

            def wait(self, timeout=None):
                if timeout is not None:
                    raise subprocess.TimeoutExpired(cmd="x", timeout=timeout)
                return -9

        monkeypatch.setattr(subprocess, "Popen", Hung)
        monkeypatch.setattr(os, "killpg", lambda pid, sig: killed.append((pid, sig)))
        p = tmp_path / "a"
        p.write_bytes(make_pdf([["hi"]]))
        with pytest.raises(ExtractionFailed) as e:
            run_extraction(p, "pdf")
        assert e.value.code == "extraction_timeout" and killed == [(4242, signal.SIGKILL)]

    def test_failure_to_start_is_reported_as_unavailable(self, tmp_path, monkeypatch):
        def refuse(*args, **kwargs):
            raise OSError("no processes")

        monkeypatch.setattr(subprocess, "Popen", refuse)
        p = tmp_path / "a"
        p.write_bytes(make_pdf([["hi"]]))
        with pytest.raises(ExtractionFailed) as e:
            run_extraction(p, "pdf")
        assert e.value.code == "extraction_unavailable"
