"""Structured JSON logging with defensive redaction.

Policy: application code never passes résumé text, contact details, tokens or prompts to the
logger. The redacting filter is a second line of defence for accidental leaks.
"""

import json
import logging
import re
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\s().-]?){9,15}(?!\d)")
_BEARER = re.compile(r"(?i)(bearer\s+|token[=:]\s*|api[_-]?key[=:]\s*|password[=:]\s*)[^\s,;]+")
_SENSITIVE_KEYS = {
    "password",
    "token",
    "authorization",
    "cookie",
    "set-cookie",
    "api_key",
    "secret",
    "text",
    "content",
    "prompt",
    "body",
    "email",
    "phone",
    "excerpt",
}


def redact(value: str) -> str:
    value = _EMAIL.sub("[email]", value)
    value = _BEARER.sub(r"\1[redacted]", value)
    return _PHONE.sub("[phone]", value)


class _JsonFormatter(logging.Formatter):
    _RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "event": redact(record.getMessage()),
            "request_id": request_id_var.get(),
        }
        for key, val in record.__dict__.items():
            if key in self._RESERVED:
                continue
            if key.lower() in _SENSITIVE_KEYS:
                payload[key] = "[withheld]"
            elif isinstance(val, str):
                payload[key] = redact(val)
            elif isinstance(val, int | float | bool) or val is None:
                payload[key] = val
            else:
                payload[key] = "[omitted]"
        # Tracebacks may embed document fragments; keep only the exception type.
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc_type"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
