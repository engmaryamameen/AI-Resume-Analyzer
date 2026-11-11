import io
import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.analysis import reviewer
from app.core.config import Settings
from app.core.errors import ServiceUnavailable
from app.documents.schema import Block, NormalizedDocument, Section

TEXT = "Built billing APIs in Python with integration tests for payment and refund flows."


def document():
    return NormalizedDocument(
        sections=[Section(id="work", kind="experience"), Section(id="contact", kind="header")],
        blocks=[
            Block(id="b1", section_id="work", kind="bullet", text=TEXT, line=3),
            Block(
                id="b0",
                section_id="contact",
                kind="paragraph",
                text="Alex alex@example.test",
                line=1,
            ),
        ],
    )


def content():
    return {
        "summary": "The résumé describes concrete billing API work and test coverage. Its impact could be easier to assess with context about scope.",
        **{
            k: [
                {
                    "title": title,
                    "detail": detail,
                    "evidence": [{"block_id": "b1", "excerpt": TEXT}],
                }
            ]
            for k, title, detail in [
                (
                    "strengths",
                    "Concrete implementation evidence",
                    "The billing API and refund integration tests demonstrate a specific engineering contribution.",
                ),
                (
                    "concerns",
                    "Scope is not yet clear",
                    "This passage does not establish the scale or outcomes of the API work; that limits what a reviewer can assess.",
                ),
                (
                    "next_steps",
                    "Clarify the outcome",
                    "Explain the outcome of the billing work, using a verifiable result if available; do not invent a metric.",
                ),
            ]
        },
    }


def settings(**kwargs):
    return Settings(
        _env_file=None,
        app_env="test",
        reviewer_enabled=True,
        reviewer_url="http://localhost:11434",
        **kwargs,
    )


def transport(monkeypatch, reply=None, tags=None):
    calls = []

    def open_url(request, timeout):
        calls.append(request)
        if isinstance(request, str):
            data = (
                tags
                if tags is not None
                else {"models": [{"name": "qwen3:4b-instruct", "digest": "sha256:synthetic-model"}]}
            )
        else:
            data = (
                reply
                if reply is not None
                else {
                    "done": True,
                    "done_reason": "stop",
                    "message": {"content": json.dumps(content())},
                }
            )
        return io.BytesIO(json.dumps(data).encode())

    monkeypatch.setattr(reviewer, "urlopen", open_url)
    return calls


def test_source_grounding_contact_exclusion_and_model_provenance(monkeypatch):
    calls = transport(monkeypatch)
    beat = Mock()
    result = reviewer.review_document(document(), None, settings(), beat)
    assert result.model == "qwen3:4b-instruct" and result.prompt_version == reviewer.PROMPT_VERSION
    assert result.reviewed_blocks == 1 and result.total_blocks == 2
    payload = json.loads(calls[1].data)
    assert "alex@example.test" not in json.dumps(payload)
    assert json.loads(payload["messages"][1]["content"])["job_description"] is None
    assert payload["format"]["$defs"]["ReviewCitation"]["properties"]["block_id"]["enum"] == ["b1"]
    assert result.strengths[0].evidence[0].excerpt in document().blocks[0].text
    assert beat.call_count == 2


@pytest.mark.parametrize("change", ["block", "quote", "truncated", "schema", "model"])
def test_invalid_model_output_is_never_presented_as_an_ai_review(monkeypatch, change):
    c = content()
    if change == "block":
        c["concerns"][0]["evidence"][0]["block_id"] = "made-up"
    if change == "quote":
        c["concerns"][0]["evidence"][0]["excerpt"] = "Managed a team of fifty engineers."
    if change == "schema":
        del c["summary"]
    reply = {
        "done": True,
        "done_reason": "length" if change == "truncated" else "stop",
        "message": {"content": json.dumps(c)},
    }
    transport(monkeypatch, reply=reply, tags={"models": []} if change == "model" else None)
    with pytest.raises(ServiceUnavailable) as err:
        reviewer.review_document(document(), None, settings(), lambda: None)
    assert err.value.code == "ai_review_unavailable"


def test_model_digest_mismatch_refuses_inference(monkeypatch):
    calls = transport(monkeypatch)
    with pytest.raises(ServiceUnavailable):
        reviewer.review_document(
            document(), None, settings(reviewer_model_digest="different"), lambda: None
        )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com",
        "http://169.254.169.254",
        "file:///etc/passwd",
        "http://localhost:11434@outside.example",
    ],
)
def test_only_local_inference_endpoints_are_allowed(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="test", reviewer_url=url)
