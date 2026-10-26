"""Builders for test documents. Pure functions; no file or network access."""

import io
import zipfile
from datetime import date

from app.analysis.schema import RequirementDraft
from app.documents.isolated import RawLine
from app.documents.normalize import normalize
from app.documents.parseability import assess
from app.documents.schema import NormalizedDocument, Parseability

TODAY = date(2026, 1, 1)


def make_pdf(pages: list[list[str]]) -> bytes:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    n = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, lines in enumerate(pages):
        content_no = 5 + 2 * i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_no} 0 R >>".encode()
        )
        ops = ["BT", "/F1 11 Tf", "14 TL", "50 750 Td"] + [f"({esc(l)}) Tj T*" for l in lines] + ["ET"]
        stream = "\n".join(ops).encode("latin-1", "replace")
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_docx(paragraphs: list[str], bullets: set[int] | None = None, extra: dict[str, bytes] | None = None) -> bytes:
    bullets = bullets or set()
    body = []
    for i, text in enumerate(paragraphs):
        ppr = '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>' if i in bullets else ""
        safe = text.replace("&", "&amp;").replace("<", "&lt;")
        body.append(f"<w:p>{ppr}<w:r><w:t>{safe}</w:t></w:r></w:p>")
    document = f'<?xml version="1.0"?><w:document xmlns:w="{_W}"><w:body>{"".join(body)}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        zf.writestr("word/document.xml", document)
        for name, data in (extra or {}).items():
            zf.writestr(name, data)
    return buf.getvalue()


def lines_of(text: str) -> list[RawLine]:
    return [RawLine(text=t, page=1, bullet=False) for t in text.splitlines() if t.strip()]


def build_doc(text: str, page_count: int = 1) -> tuple[NormalizedDocument, Parseability]:
    lines = lines_of(text)
    doc = normalize(lines, page_count, today=TODAY)
    return doc, assess([line.text for line in lines], doc)


def skill_req(ordinal: int, term: str, kind: str = "required", name: str | None = None, **kw) -> RequirementDraft:  # noqa: ANN003
    return RequirementDraft(ordinal=ordinal, text=name or term, kind=kind, category="skill", terms=[term], **kw)  # type: ignore[arg-type]


SAMPLE_RESUME = """Alex Tester
alex.tester@example.com | +1 555 010 0100
SUMMARY
Engineer who builds backend services.
EXPERIENCE
Backend Engineer, Example Corp
Jan 2020 - Present
- Built a billing API in Python and Django used by 30 internal teams
- Responsible for maintaining the PostgreSQL schema
- Led migration of services to Docker
EDUCATION
BSc Computer Science, Example University, 2019
SKILLS
Python, Django, PostgreSQL, Docker, Kubernetes, Terraform
"""
