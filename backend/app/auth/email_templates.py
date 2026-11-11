"""Transactional account messages with matching HTML and plain-text alternatives."""

from dataclasses import dataclass
from html import escape
from typing import Literal


@dataclass(frozen=True)
class AccountEmail:
    subject: str
    text: str
    html: str


def account_email(
    kind: Literal["verify_email", "reset_password", "password_changed"], url: str
) -> AccountEmail:
    if kind == "verify_email":
        subject = "Verify your email · Rolemaker"
        title = "Your workspace starts here."
        intro = "Confirm your email address to finish setting up your Rolemaker account."
        action = "Verify email address"
        note = "This link expires in 30 minutes and can only be used once."
        security = "If you did not create an account, you can safely ignore this email."
    elif kind == "reset_password":
        subject = "Reset your password · Rolemaker"
        title = "Let’s get you back in."
        intro = "We received a request to reset the password for your Rolemaker account."
        action = "Choose a new password"
        note = "This link expires in 30 minutes and can only be used once."
        security = "If you did not request this, ignore this email. Your password has not changed."
    else:
        subject = "Your password was changed · Rolemaker"
        title = "Your password has changed."
        intro = "Your Rolemaker password was updated. All existing sessions have been signed out."
        action = "Recover your account"
        note = "If you made this change, no further action is needed."
        security = (
            "If this was not you, recover your account immediately and secure your email account."
        )
    text = f"Rolemaker\n\n{title}\n\n{intro}\n\n{note}\n\n{action}:\n{url}\n\n{security}\n\nAccount security · Rolemaker"
    link = escape(url, quote=True)
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#f3f4f1;color:#20251f;font-family:Arial,Helvetica,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(intro)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f1;"><tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid #dde2d8;border-radius:12px;">
<tr><td style="padding:32px 32px 24px;border-bottom:1px solid #e7ebe3;"><span style="font-size:26px;font-weight:bold;letter-spacing:-1px;color:#20251f;">Rolemaker</span></td></tr>
<tr><td style="padding:32px;">
<p style="margin:0 0 16px;font-size:12px;letter-spacing:1.3px;color:#596651;">ACCOUNT SECURITY</p>
<h1 style="margin:0 0 20px;font-size:30px;line-height:1.2;font-weight:600;letter-spacing:-.7px;">{escape(title)}</h1>
<p style="margin:0 0 16px;font-size:16px;line-height:1.7;">{escape(intro)}</p>
<p style="margin:0 0 28px;font-size:14px;line-height:1.7;color:#596651;">{escape(note)}</p>
<table role="presentation" cellpadding="0" cellspacing="0"><tr><td bgcolor="#abf565" style="border-radius:6px;text-align:center;"><a href="{link}" style="display:inline-block;padding:15px 24px;font-size:16px;line-height:1.4;font-weight:bold;text-decoration:none;color:#10200a;">{escape(action)}</a></td></tr></table>
<p style="margin:28px 0 0;padding-top:24px;border-top:1px solid #e7ebe3;font-size:14px;line-height:1.7;color:#596651;">{escape(security)}</p>
<p style="margin:24px 0 8px;font-size:12px;line-height:1.7;color:#596651;">If the button does not work, copy this address into your browser:</p>
<p style="margin:0;font-size:12px;line-height:1.7;overflow-wrap:anywhere;word-break:break-all;"><a href="{link}" style="color:#285a20;text-decoration:underline;">{escape(url)}</a></p>
</td></tr></table>
<p style="margin:20px 0 0;font-size:12px;line-height:1.7;color:#596651;">Account security · Rolemaker</p>
</td></tr></table></body></html>'''
    return AccountEmail(subject, text, html)
