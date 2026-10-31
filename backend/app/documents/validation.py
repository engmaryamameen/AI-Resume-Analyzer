"""Upload validation. File type is decided by content, never by filename or declared MIME type."""

import unicodedata
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from app.core.errors import PayloadTooLarge, UnsupportedMedia, ValidationFailed
from app.core.textclean import strip_controls

FileKind = Literal["pdf", "docx"]
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


@dataclass(frozen=True)
class ValidatedUpload:
    kind: FileKind
    data: bytes
    display_title: str


def display_title(filename: str | None) -> str:
    """A label for the UI only. The filename is never used for storage or any filesystem path."""
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = unicodedata.normalize("NFC", strip_controls(name, keep_whitespace=False)).strip()
    stem = name.rsplit(".", 1)[0] if "." in name else name
    stem = stem.strip(" .")[:120]
    return stem or "Résumé"


def sniff_kind(data: bytes) -> FileKind:
    if data[:1024].lstrip(b"\x00\t\r\n ").startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(_OLE_MAGIC):
        raise UnsupportedMedia(
            "Legacy .doc files are not supported. Save the file as PDF or DOCX and upload again.",
            code="legacy_doc_unsupported",
        )
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(BytesIO(data)) as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile as exc:
            raise ValidationFailed(
                "The file is damaged or not a valid DOCX.", code="docx_corrupt"
            ) from exc
        if "[Content_Types].xml" in names and "word/document.xml" in names:
            return "docx"
    raise UnsupportedMedia("Only PDF and DOCX résumés are supported.", code="unsupported_file_type")


def validate_upload(filename: str | None, data: bytes, max_bytes: int) -> ValidatedUpload:
    if len(data) == 0:
        raise ValidationFailed("The uploaded file is empty.", code="empty_file")
    if len(data) > max_bytes:
        raise PayloadTooLarge(
            f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.",
            code="file_too_large",
        )
    kind = sniff_kind(data)
    ext = (filename or "").rsplit(".", 1)[-1].lower() if filename and "." in filename else ""
    if ext and ext not in {"pdf", "docx"}:
        raise UnsupportedMedia(
            "Only .pdf and .docx files are supported.", code="unsupported_file_type"
        )
    if ext and ext != kind:
        raise ValidationFailed(
            "The file extension does not match the file content.", code="file_type_mismatch"
        )
    return ValidatedUpload(kind=kind, data=data, display_title=display_title(filename))
