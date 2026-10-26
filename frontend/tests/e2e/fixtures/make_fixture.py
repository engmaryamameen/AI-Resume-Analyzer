"""Generates the synthetic DOCX used by the E2E journeys. Run it ONCE in the verification environment:

    python frontend/tests/e2e/fixtures/make_fixture.py

It uses only the standard library and writes synthetic-resume.docx next to itself. The content is
entirely invented (example.com address, 555-01xx phone, fictional employers).
"""

import zipfile
from pathlib import Path

LINES = """Riley Fixture
riley.fixture@example.com | +1 555 010 0123
SUMMARY
Developer who builds web services for fictional retail companies.
EXPERIENCE
Software Engineer, Globex Retail (fictional)
Feb 2019 - Present
- Built a catalogue API in Python and Django used by 25 internal teams
- Responsible for maintaining the PostgreSQL schema
- Led the move of six services to Docker
EDUCATION
BSc Computer Science, Example University, 2018
SKILLS
Python, Django, PostgreSQL, Docker, Kubernetes""".splitlines()

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
body = "".join(
    "<w:p><w:r><w:t>{}</w:t></w:r></w:p>".format(t.replace("&", "&amp;").replace("<", "&lt;")) for t in LINES
)
doc = f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'
out = Path(__file__).with_name("synthetic-resume.docx")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
    z.writestr("word/document.xml", doc)
print("wrote", out)
