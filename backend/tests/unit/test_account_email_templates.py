from email.message import EmailMessage
from html import escape

import pytest

from app.auth import lifecycle
from app.auth.email_templates import account_email
from app.core.config import Settings


@pytest.mark.parametrize("kind", ["verify_email", "reset_password", "password_changed"])
def test_account_email_has_matching_accessible_alternatives(kind):
    url = "https://example.test/reset-password?source=email&next=workspace#token=synthetic"
    content = account_email(kind, url)
    assert url in content.text
    assert f'href="{escape(url, quote=True)}"' in content.html
    assert '<html lang="en">' in content.html
    assert '<h1 ' in content.html
    assert '<img' not in content.html  # no external assets or tracking pixels
    assert '<script' not in content.html
    if kind != "password_changed":
        assert "30 minutes" in content.text and "30 minutes" in content.html
        assert "only be used once" in content.text
    else:
        assert "All existing sessions" in content.text
        assert "If this was not you" in content.html
        assert "expires" not in content.text


def test_email_escapes_urls_in_html():
    url = 'https://example.test/?value="<unsafe>&other=1'
    content = account_email("reset_password", url)
    assert url in content.text
    assert 'value="<unsafe>' not in content.html
    assert '&quot;&lt;unsafe&gt;' in content.html


def test_smtp_sends_a_multipart_message_without_replacing_plain_text(monkeypatch):
    messages: list[EmailMessage] = []

    class SMTP:
        def __init__(self, host, port, **kwargs):
            assert host == "smtp.example.test"
            assert port == 465
            assert kwargs["timeout"] == 10
            assert kwargs["context"].check_hostname

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def send_message(self, message):
            messages.append(message)

    monkeypatch.setattr(lifecycle.smtplib, "SMTP_SSL", SMTP)
    settings = Settings(
        smtp_host="smtp.example.test", smtp_port=465,
        smtp_from="accounts@example.test", smtp_username="",
    )
    content = account_email("reset_password", "https://example.test/reset-password#token=synthetic")
    lifecycle.deliver(settings, "reader@example.test", content.subject, content.text, content.html)
    message = messages[0]
    assert message.get_content_type() == "multipart/alternative"
    assert message["From"] == "Rolemaker <accounts@example.test>"
    assert message["To"] == "reader@example.test"
    assert message["Subject"] == content.subject
    assert message.get_body(preferencelist=("plain",)).get_content().strip() == content.text
    assert message.get_body(preferencelist=("html",)).get_content().strip() == content.html
