"""Optional test-mode Checkout and a transactionally serialized review-credit ledger."""

import uuid
from typing import Any

import stripe
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import Conflict, Forbidden, NotFound, ServiceUnavailable
from app.db import idempotency
from app.db.locks import lock_user
from app.db.models import BillingOrder, CreditEntry

PACK_CREDITS = 5
PACK_CENTS = 500


def balance(db: Session, user_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(CreditEntry.amount), 0)).where(
                CreditEntry.user_id == user_id
            )
        )
        or 0
    )


def checkout(db: Session, settings: Settings, user_id: uuid.UUID, key: str) -> str:
    if not settings.billing_enabled:
        raise ServiceUnavailable(
            "Stripe test checkout is not configured.", code="billing_unavailable"
        )
    key = idempotency.validate_key(key) or ""
    if not key:
        raise Conflict("A checkout request key is required.")
    lock_user(db, user_id)
    order = db.scalar(
        select(BillingOrder).where(BillingOrder.user_id == user_id, BillingOrder.request_key == key)
    )
    if order is None:
        order = BillingOrder(user_id=user_id, request_key=key)
        db.add(order)
        db.flush()
    order_id = order.id
    db.commit()  # Persist the intent before a network call; retries use the same Stripe key.
    try:
        client = stripe.StripeClient(
            settings.stripe_secret_key,
            max_network_retries=1,
            http_client=stripe.RequestsClient(timeout=10),
        )
        session = client.v1.checkout.sessions.create(
            {
                "mode": "payment",
                "payment_method_types": ["card"],
                "client_reference_id": str(order_id),
                "metadata": {"order_id": str(order_id)},
                "line_items": [
                    {
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": PACK_CENTS,
                            "product_data": {"name": "Rolemaker — 5 review credits (test mode)"},
                        },
                        "quantity": 1,
                    }
                ],
                "success_url": settings.public_app_url.rstrip("/")
                + "/app/billing?checkout=returned",
                "cancel_url": settings.public_app_url.rstrip("/")
                + "/app/billing?checkout=cancelled",
            },
            options={"idempotency_key": f"rolemaker-order-{order_id}"},
        )
    except stripe.StripeError as exc:
        raise ServiceUnavailable(
            "Checkout could not be opened. Retry this request.", code="checkout_unavailable"
        ) from exc
    if (
        session.livemode
        or not session.url
        or not session.url.startswith("https://checkout.stripe.com/")
    ):
        raise ServiceUnavailable("A valid test checkout could not be opened.")
    lock_user(db, user_id)
    order = db.get(BillingOrder, order_id, populate_existing=True)
    if order is None:
        raise NotFound("Checkout account is no longer available.")
    if order.stripe_session_id and order.stripe_session_id != session.id:
        raise Conflict("The checkout session does not match this order.")
    order.stripe_session_id = session.id
    db.commit()
    return session.url


def fulfill(db: Session, event: dict[str, Any]) -> None:
    # Only signed Checkout events can reach this function. Redirect parameters never grant credits.
    if event.get("livemode") is not False:
        raise Forbidden("Only Stripe test events are accepted.", code="test_mode_required")
    if event.get("type") not in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }:
        return
    session = event.get("data", {}).get("object", {})
    if session.get("payment_status") != "paid":
        return
    try:
        order_id = uuid.UUID(session.get("metadata", {}).get("order_id", ""))
    except (ValueError, TypeError, AttributeError):
        return  # Another integration's event on the same Stripe test account.
    order = db.get(BillingOrder, order_id)
    if order is None:
        return  # Deleted account/order: do not recreate it or retain its data.
    lock_user(db, order.user_id)
    order = db.scalar(
        select(BillingOrder)
        .where(BillingOrder.id == order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if order is None:
        return
    if (
        session.get("livemode") is not False
        or session.get("mode") != "payment"
        or session.get("currency") != "usd"
        or session.get("amount_total") != PACK_CENTS
        or session.get("client_reference_id") != str(order.id)
        or not str(session.get("id", "")).startswith("cs_test_")
        or (order.stripe_session_id and order.stripe_session_id != session["id"])
    ):
        raise Conflict(
            "Checkout does not match the expected credit pack.", code="checkout_mismatch"
        )
    if not order.paid:
        order.stripe_session_id = session["id"]
        order.paid = True
        db.add(
            CreditEntry(
                user_id=order.user_id, kind="purchase", reference_id=order.id, amount=PACK_CREDITS
            )
        )
    db.commit()


def spend(db: Session, user_id: uuid.UUID, run_id: uuid.UUID) -> None:
    lock_user(db, user_id)
    if balance(db, user_id) < 1:
        raise Forbidden(
            "You need a review credit. Open Credits to add a test pack.", code="credits_required"
        )
    db.add(CreditEntry(user_id=user_id, kind="review", reference_id=run_id, amount=-1))
    db.flush()


def refund(db: Session, user_id: uuid.UUID, run_id: uuid.UUID) -> None:
    # Worker settlement already holds the owner advisory lock. Safe for local/free and guest runs.
    spent = db.scalar(
        select(CreditEntry.id).where(
            CreditEntry.user_id == user_id,
            CreditEntry.kind == "review",
            CreditEntry.reference_id == run_id,
        )
    )
    if spent:
        db.execute(
            insert(CreditEntry)
            .values(id=uuid.uuid4(), user_id=user_id, kind="refund", reference_id=run_id, amount=1)
            .on_conflict_do_nothing(constraint="uq_credit_reference")
        )
