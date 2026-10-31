"""Run extraction with process, resource, output and wall-clock limits.

Filesystem and network isolation require the worker container; see docs/deployment.md."""

import ctypes
import json
import os
import resource
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)
_WORKER = Path(__file__).with_name("_extract_worker.py")
_MAX_OUTPUT = 8 * 1024 * 1024
_PR_SET_NO_NEW_PRIVS = 38


class ExtractionFailed(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RawLine:
    text: str
    page: int | None
    bullet: bool


@dataclass(frozen=True)
class RawExtraction:
    page_count: int | None
    lines: list[RawLine]


def _limits(memory_mb: int, cpu_seconds: int) -> Callable[[], None]:
    def apply() -> None:
        memory = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        resource.setrlimit(resource.RLIMIT_FSIZE, (_MAX_OUTPUT, _MAX_OUTPUT))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        ctypes.CDLL(None).prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)

    return apply


def run_extraction(path: Path, kind: str) -> RawExtraction:
    settings = get_settings()
    cmd = [sys.executable, "-I", str(_WORKER), kind, str(path), str(settings.max_pdf_pages)]
    with tempfile.TemporaryFile() as out:
        try:
            proc = subprocess.Popen(  # noqa: S603 - fixed argv, no shell, no user-controlled argv parts
                cmd,
                stdout=out,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                env={},
                cwd="/",
                start_new_session=True,
                preexec_fn=_limits(settings.parser_memory_mb, settings.parser_timeout_seconds),  # noqa: PLW1509
            )
        except OSError as exc:
            log.error("extraction_spawn_failed", extra={"error_type": type(exc).__name__})
            raise ExtractionFailed("extraction_unavailable") from exc
        try:
            returncode = proc.wait(timeout=settings.parser_timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            raise ExtractionFailed("extraction_timeout") from exc
        if returncode != 0:
            log.warning("extraction_worker_exit", extra={"kind": kind, "returncode": returncode})
            raise ExtractionFailed("extraction_crashed")
        out.seek(0)
        payload = out.read(_MAX_OUTPUT + 1)

    if len(payload) > _MAX_OUTPUT:
        raise ExtractionFailed("extraction_crashed")
    try:
        data = json.loads(payload)
    except ValueError as exc:
        raise ExtractionFailed("extraction_bad_output") from exc
    if not data.get("ok"):
        raise ExtractionFailed(str(data.get("code", "extraction_failed"))[:64])
    lines = [
        RawLine(text=str(item["text"]), page=item.get("page"), bullet=bool(item.get("bullet")))
        for item in data.get("lines", [])
    ]
    return RawExtraction(page_count=data.get("page_count"), lines=lines)
