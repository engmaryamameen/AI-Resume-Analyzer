import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings
from app.core.logging import get_logger, request_id_var
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS

log = get_logger(__name__)
_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        {
            "error": {
                "code": code,
                "message": message,
                "details": {},
                "request_id": request_id_var.get(),
            }
        },
        status_code=status,
    )


class BodyLimitMiddleware:
    """Bounds the complete body before dispatch, including chunked and early-response requests."""

    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        # Buffer at most max_bytes before invoking the app. This also covers endpoints
        # that answer without reading their body: no response can start before the limit
        # is established. The ingress supplies slow-client timeouts and its own cap.
        lengths = Headers(scope=scope).getlist("content-length")
        if lengths and (len(lengths) != 1 or not re.fullmatch(r"[0-9]+", lengths[0])):
            return await _error("invalid_content_length", "Invalid Content-Length.", 400)(
                scope, receive, send
            )
        if lengths and (len(lengths[0]) > 20 or int(lengths[0]) > self.max_bytes):
            return await _error("payload_too_large", "The request body is too large.", 413)(
                scope, receive, send
            )
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.max_bytes:
                return await _error("payload_too_large", "The request body is too large.", 413)(
                    scope, receive, send
                )
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def buffered_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, buffered_receive, send)


class RequestContextMiddleware:
    """Request id, security headers, Origin check for state-changing requests, metrics."""

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.allowed_origins = set(settings.cors_origins)
        self.hsts = settings.is_production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        incoming = headers.get("x-request-id", "")
        rid = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status_holder = {"code": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
                h = MutableHeaders(scope=message)
                h["X-Request-ID"] = rid
                h["X-Content-Type-Options"] = "nosniff"
                h["Referrer-Policy"] = "no-referrer"
                h["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
                h["Cross-Origin-Resource-Policy"] = "same-site"
                if "cache-control" not in h:
                    h["Cache-Control"] = "no-store"
                if self.hsts:
                    h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        try:
            origin = headers.get("origin")
            if scope["method"] in _UNSAFE and origin and origin not in self.allowed_origins:
                response = _error("origin_not_allowed", "Cross-origin request rejected.", 403)
                await response(scope, receive, send_wrapper)
                return
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            label = getattr(route, "path", "unmatched")
            HTTP_REQUESTS.labels(
                method=scope["method"], route=label, status=str(status_holder["code"])
            ).inc()
            HTTP_LATENCY.labels(route=label).observe(time.perf_counter() - started)
            request_id_var.reset(token)
