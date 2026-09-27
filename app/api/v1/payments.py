from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.user import User
from app.schemas.booking import Paginated
from app.schemas.payment import PaymentCreate, PaymentOut, WebhookPayload, WebhookResponse
from app.services.payment_service import create_payment, process_webhook
from fastapi import HTTPException

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def pay(
    request: Request,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    payment, _ = create_payment(db, user_id=current.id, payload=payload, idempotency_key=idempotency_key)
    return payment


@router.get("/", response_model=Paginated[PaymentOut])
def list_mine(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    booking_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    query = (
        db.query(Payment)
        .join(Booking, Booking.id == Payment.booking_id)
        .filter(Booking.user_id == current.id)
    )
    if booking_id:
        query = query.filter(Payment.booking_id == booking_id)
    total = query.count()
    items = query.order_by(Payment.id.desc()).limit(limit).offset(offset).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{payment_id}", response_model=PaymentOut)
def get_one(
    payment_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    payment = (
        db.query(Payment)
        .join(Booking, Booking.id == Payment.booking_id)
        .filter(Payment.id == payment_id, Booking.user_id == current.id)
        .first()
    )
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    return payment


@router.post("/webhook/", response_model=WebhookResponse)
@limiter.limit("100/minute")
def webhook(
    request: Request,
    payload: WebhookPayload,
    db: Session = Depends(get_db),
    webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    """Simulated provider callback. Idempotent on event_id. No user auth by design."""
    if settings.WEBHOOK_SECRET and webhook_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook secret")
    result, deduped = process_webhook(db, payload=payload)
    return WebhookResponse(received=True, deduped=deduped, **result)
