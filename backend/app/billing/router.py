import stripe
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.billing import service
from app.core.config import Settings, get_settings
from app.core.errors import Forbidden, ServiceUnavailable
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/billing", tags=["billing"])


class BillingStatus(BaseModel):
    enabled: bool
    require_credits: bool = False
    test_mode: bool = True
    credits: int
    pack_credits: int = service.PACK_CREDITS
    pack_cents: int = service.PACK_CENTS
    currency: str = "usd"


class CheckoutOut(BaseModel):
    url: str


@router.get("", response_model=BillingStatus)
def status(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> BillingStatus:
    return BillingStatus(
        enabled=settings.billing_enabled,
        require_credits=settings.billing_require_credits,
        credits=service.balance(db, user.id),
    )


@router.post("/checkout", response_model=CheckoutOut)
def checkout(
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CheckoutOut:
    return CheckoutOut(url=service.checkout(db, settings, user.id, idempotency_key))


@router.post("/webhook", status_code=204)
async def webhook(
    request: Request,
    stripe_signature: str = Header(default=""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.billing_enabled:
        raise ServiceUnavailable("Stripe test checkout is not configured.")
    try:
        event = stripe.Webhook.construct_event(
            await request.body(), stripe_signature, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise Forbidden("Invalid Stripe signature.", code="invalid_webhook_signature") from exc
    service.fulfill(db, event.to_dict())
