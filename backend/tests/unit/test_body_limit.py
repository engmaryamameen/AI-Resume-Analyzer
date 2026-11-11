"""Exercise ASGI events directly, including apps that never consume a request body."""

import asyncio

import pytest

from app.core.middleware import BodyLimitMiddleware


def exercise(chunks, limit=4, headers=(), read=True):
    sent, calls = [], []
    messages = iter(chunks)

    async def receive():
        calls.append(True)
        return next(messages)

    async def send(message):
        sent.append(message)

    async def app(scope, receive, send):
        if read:
            message = await receive()
            assert len(message["body"]) <= limit
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    asyncio.run(
        BodyLimitMiddleware(app, limit)({"type": "http", "headers": list(headers)}, receive, send)
    )
    return sent, len(calls)


@pytest.mark.parametrize("read", [True, False])
def test_chunked_excess_is_rejected_even_before_early_response(read):
    sent, calls = exercise(
        [
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"5", "more_body": True},
            {"type": "http.request", "body": b"unread", "more_body": False},
        ],
        read=read,
    )
    assert [m["status"] for m in sent if m["type"] == "http.response.start"] == [413]
    assert calls == 2


def test_exact_boundary_is_accepted():
    sent, _ = exercise([{"type": "http.request", "body": b"1234"}])
    assert sent[0]["status"] == 200


@pytest.mark.parametrize("value", [b"-1", b"abc", b"4,4", b" 4"])
def test_malformed_length_is_rejected_without_consuming(value):
    sent, calls = exercise([], headers=[(b"content-length", value)])
    assert sent[0]["status"] == 400 and calls == 0


def test_disconnect_during_upload_does_not_dispatch():
    assert exercise([{"type": "http.disconnect"}])[0] == []
