"""Real PostgreSQL billing settlement; only Stripe's external network is replaced."""

import hashlib
import hmac
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select

from app.analysis import service as analysis
from app.billing import service
from app.core.config import get_settings
from app.core.errors import Forbidden
from app.db.locks import lock_user
from app.db.models import BillingOrder, CreditEntry
from app.db.session import session_scope
from tests.integration.test_workflows import analyse, make_job, ready_resume

pytestmark = pytest.mark.integration


def enable(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "billing_enabled", True)
    monkeypatch.setattr(settings, "billing_require_credits", True)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_synthetic_only")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_synthetic_only")
    return settings


def order_for(c):
    uid = uuid.UUID(c.get("/api/v1/auth/me").json()["id"])
    with session_scope() as db:
        order = BillingOrder(user_id=uid, request_key=str(uuid.uuid4()))
        db.add(order)
        db.flush()
        return uid, order.id


def event_for(oid):
    return {
        "id": "evt_synthetic",
        "object": "event",
        "livemode": False,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_synthetic",
                "object": "checkout.session",
                "livemode": False,
                "mode": "payment",
                "payment_status": "paid",
                "currency": "usd",
                "amount_total": 500,
                "client_reference_id": str(oid),
                "metadata": {"order_id": str(oid)},
            }
        },
    }


def send(c, event, *, timestamp=None, secret="whsec_synthetic_only"):
    body = json.dumps(event).encode()
    timestamp = timestamp or int(time.time())
    signature = hmac.new(
        secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return c.post(
        "/api/v1/billing/webhook",
        content=body,
        headers={
            "Stripe-Signature": f"t={timestamp},v1={signature}",
            "Content-Type": "application/json",
        },
    )


def test_checkout_disabled_and_csrf_required(make_user):
    _, c = make_user()
    assert c.get("/api/v1/billing").json()["enabled"] is False
    assert (
        c.post("/api/v1/billing/checkout", headers={"Idempotency-Key": "checkout-key"}).status_code
        == 503
    )
    c.headers.pop("X-CSRF-Token")
    assert (
        c.post("/api/v1/billing/checkout", headers={"Idempotency-Key": "checkout-key"}).status_code
        == 403
    )


def test_checkout_retries_same_server_order_and_cannot_accept_price(make_user, monkeypatch):
    _, c = make_user()
    enable(monkeypatch)
    create = Mock(
        return_value=SimpleNamespace(
            id="cs_test_synthetic", livemode=False, url="https://checkout.stripe.com/c/pay/test"
        )
    )
    monkeypatch.setattr(
        service.stripe,
        "StripeClient",
        Mock(
            return_value=SimpleNamespace(
                v1=SimpleNamespace(
                    checkout=SimpleNamespace(sessions=SimpleNamespace(create=create))
                )
            )
        ),
    )
    for _ in range(2):
        response = c.post(
            "/api/v1/billing/checkout",
            headers={"Idempotency-Key": "checkout-key"},
            json={"amount": 1},
        )
        assert response.status_code == 200, response.text
    a, b = create.call_args_list
    assert a.kwargs["options"] == b.kwargs["options"]
    assert a.args[0]["line_items"][0]["price_data"]["unit_amount"] == 500
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(BillingOrder)) == 1
        assert db.scalar(select(func.count()).select_from(CreditEntry)) == 0


def test_signed_payment_fulfills_once_across_duplicate_event_ids(make_user, monkeypatch):
    _, c = make_user()
    uid, oid = order_for(c)
    enable(monkeypatch)
    event = event_for(oid)
    assert send(c, event).status_code == 204
    event["id"] = "evt_different_duplicate"
    assert send(c, event).status_code == 204
    assert c.get("/api/v1/billing").json()["credits"] == 5
    with session_scope() as db:
        assert service.balance(db, uid) == 5
        assert db.scalar(select(func.count()).select_from(CreditEntry)) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount_total", 1),
        ("currency", "eur"),
        ("mode", "subscription"),
        ("livemode", True),
        ("client_reference_id", "other"),
    ],
)
def test_signed_but_mismatched_pack_never_grants_credits(make_user, monkeypatch, field, value):
    _, c = make_user()
    _, oid = order_for(c)
    enable(monkeypatch)
    event = event_for(oid)
    event["data"]["object"][field] = value
    assert send(c, event).status_code == 409
    assert c.get("/api/v1/billing").json()["credits"] == 0


def test_forged_stale_live_unpaid_and_deleted_account_events(make_user, monkeypatch):
    _, c = make_user()
    _, oid = order_for(c)
    enable(monkeypatch)
    event = event_for(oid)
    assert send(c, event, secret="wrong").status_code == 403
    assert send(c, event, timestamp=int(time.time()) - 600).status_code == 403
    event["livemode"] = True
    assert send(c, event).status_code == 403
    event["livemode"] = False
    event["data"]["object"]["payment_status"] = "unpaid"
    assert send(c, event).status_code == 204
    assert c.get("/api/v1/billing").json()["credits"] == 0
    event["data"]["object"]["payment_status"] = "paid"
    event["data"]["object"]["metadata"]["order_id"] = str(uuid.uuid4())
    assert send(c, event).status_code == 204


def test_paid_api_analysis_replay_and_cancel_refund_once(make_user, run_jobs, monkeypatch):
    _, c = make_user()
    _, rv = ready_resume(c, run_jobs)
    _, jv = make_job(c)
    uid, oid = order_for(c)
    enable(monkeypatch)
    assert analyse(c, rv, jv).status_code == 403
    assert send(c, event_for(oid)).status_code == 204
    run = analyse(c, rv, jv, key="paid-analysis-key")
    assert run.status_code == 202, run.text
    assert analyse(c, rv, jv, key="paid-analysis-key").json()["id"] == run.json()["id"]
    assert c.get("/api/v1/billing").json()["credits"] == 4
    rid = uuid.UUID(run.json()["id"])
    with session_scope() as db:
        analysis.cancel_analysis(db, uid, rid)
    with session_scope() as db:
        lock_user(db, uid)
        analysis.mark_analysis_failed(db, rid, "synthetic_failure")
        service.refund(db, uid, rid)
    assert c.get("/api/v1/billing").json()["credits"] == 5
    second = analyse(c, rv, jv, key="paid-analysis-second")
    with session_scope() as db:
        lock_user(db, uid)
        analysis.mark_analysis_failed(db, uuid.UUID(second.json()["id"]), "synthetic_failure")
    assert c.get("/api/v1/billing").json()["credits"] == 5


def test_concurrent_spend_cannot_overdraw(make_user, monkeypatch):
    _, c = make_user()
    uid, oid = order_for(c)
    enable(monkeypatch)
    assert send(c, event_for(oid)).status_code == 204

    def spend_one(_):
        try:
            with session_scope() as db:
                service.spend(db, uid, uuid.uuid4())
            return True
        except Forbidden:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(spend_one, range(8)))
    assert sum(outcomes) == 5
    assert c.get("/api/v1/billing").json()["credits"] == 0


def test_guest_review_stays_free_with_test_billing_enabled(
    client, db_engine, run_jobs, monkeypatch
):
    from tests.integration.test_guest import complete, submit

    enable(monkeypatch)
    assert submit(client).status_code == 202
    response = complete(client, run_jobs)
    assert response.json()["status"] == "succeeded", response.text
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(CreditEntry)) == 0
