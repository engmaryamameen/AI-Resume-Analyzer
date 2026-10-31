"""Untrusted-document text extraction. Runs in a separate, resource-limited process.

Self-contained on purpose (standard library, pypdf and defusedxml only, no application imports) so it can
run under `python -I`. It prints exactly one JSON object to stdout. The parent (documents.isolated)
treats a non-zero exit, a timeout or malformed output as an extraction failure.
"""

import json
import re
import sys
import zipfile
from typing import Any

MAX_TOTAL_CHARS = 150_000
MAX_PAGE_CHARS = 25_000
MAX_DOCX_ENTRIES = 200
MAX_DOCX_UNCOMPRESSED = 50 * 1024 * 1024
MAX_XML_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = int(sys.argv[3]) if len(sys.argv) > 3 else 8

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_INVISIBLE = re.compile(
    "[" + "".join(chr(c) for c in (0x00, 0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF)) + "]"
)


def fail(code: str) -> None:
    print(json.dumps({"ok": False, "code": code}))
    sys.exit(0)


def _clean(text: str) -> str:
    return _INVISIBLE.sub("", text)


def extract_pdf(path: str) -> dict[str, Any]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted:
            fail("pdf_encrypted")
        pages = len(reader.pages)
        if pages == 0:
            fail("pdf_empty")
        if pages > MAX_PDF_PAGES:
            fail("too_many_pages")
        lines, total = [], 0
        for index, page in enumerate(reader.pages, start=1):
            text = _clean(page.extract_text() or "")[:MAX_PAGE_CHARS]
            total += len(text)
            if total > MAX_TOTAL_CHARS:
                fail("text_too_large")
            lines += [
                {"text": raw.strip(), "page": index, "bullet": False}
                for raw in text.splitlines()
                if raw.strip()
            ]
        return {"ok": True, "page_count": pages, "lines": lines}
    except SystemExit:
        raise
    except Exception:  # any parser failure on hostile input means "corrupt"
        fail("pdf_corrupt")
    return {}


def extract_docx(path: str) -> dict[str, Any]:
    from defusedxml import ElementTree as ET

    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_DOCX_ENTRIES:
                fail("docx_too_many_entries")
            if sum(i.file_size for i in infos) > MAX_DOCX_UNCOMPRESSED:
                fail("docx_too_large_uncompressed")
            for info in infos:
                if info.filename.startswith(("/", "\\")) or ".." in info.filename.split("/"):
                    fail("docx_unsafe_path")
                if info.file_size > 1_000_000 and info.file_size > 100 * max(info.compress_size, 1):
                    fail("docx_compression_ratio")
            names = {i.filename for i in infos}
            if any(n.lower().endswith("vbaproject.bin") for n in names):
                fail("docx_macro")
            if "word/document.xml" not in names:
                fail("docx_corrupt")
            document = archive.getinfo("word/document.xml")
            if document.file_size > MAX_XML_BYTES:
                fail("docx_too_large_uncompressed")
            with archive.open(document) as handle:
                root = ET.fromstring(handle.read(MAX_XML_BYTES + 1))
    except SystemExit:
        raise
    except Exception:  # corrupt zip, entity/DTD use refused by defusedxml, malformed XML
        fail("docx_corrupt")

    lines, total = [], 0
    for paragraph in root.iter(f"{W}p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == f"{W}t" and node.text:
                parts.append(node.text)
            elif node.tag in (f"{W}tab", f"{W}br"):
                parts.append(" ")
        text = _clean("".join(parts)).strip()
        if not text:
            continue
        total += len(text)
        if total > MAX_TOTAL_CHARS:
            fail("text_too_large")
        lines.append(
            {"text": text, "page": None, "bullet": paragraph.find(f"{W}pPr/{W}numPr") is not None}
        )
    return {"ok": True, "page_count": None, "lines": lines}


def main() -> None:
    if len(sys.argv) < 3:
        fail("bad_invocation")
    kind, path = sys.argv[1], sys.argv[2]
    if kind == "pdf":
        result = extract_pdf(path)
    elif kind == "docx":
        result = extract_docx(path)
    else:
        fail("unsupported_kind")
        return
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
