"""Mock payment gateway + webhook processing with strict idempotency."""

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.webhook_event import WebhookEvent
from app.schemas.payment import PaymentCreate, WebhookPayload

log = get_logger("eve.payments")

TERMINAL_BOOKING_STATES = {BookingStatus.CONFIRMED.value, BookingStatus.CANCELLED.value}


def _mock_charge(*, amount, simulate_failure: bool) -> tuple[str, str | None]:
    """Simulates a provider call. Deterministic for tests; no network I/O."""
    provider_payment_id = f"pay_mock_{uuid.uuid4().hex[:12]}"
    if simulate_failure:
        return provider_payment_id, "Mock gateway declined the payment (simulate_failure=true)"
    return provider_payment_id, None


def create_payment(
    db: Session, *, user_id: int, payload: PaymentCreate, idempotency_key: str | None
) -> tuple[Payment, bool]:
    if idempotency_key:
        existing = (
            db.query(Payment)
            .join(Booking, Booking.id == Payment.booking_id)
            .filter(Booking.user_id == user_id, Payment.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing, False

    booking = db.get(Booking, payload.booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.status == BookingStatus.CANCELLED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot pay for a cancelled booking")
    if booking.status == BookingStatus.CONFIRMED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Booking is already paid/confirmed")

    provider_payment_id, failure_reason = _mock_charge(
        amount=booking.amount, simulate_failure=payload.simulate_failure
    )

    if failure_reason:
        payment_status = PaymentStatus.FAILED.value
        booking.status = BookingStatus.FAILED.value
    else:
        payment_status = PaymentStatus.SUCCESS.value
        booking.status = BookingStatus.CONFIRMED.value

    payment = Payment(
        booking_id=booking.id,
        amount=booking.amount,
        currency=booking.currency,
        status=payment_status,
        payment_method=payload.payment_method,
        provider_payment_id=provider_payment_id,
        idempotency_key=idempotency_key,
        failure_reason=failure_reason,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    log.info(
        "payment_created",
        payment_id=payment.id,
        booking_id=booking.id,
        status=payment_status,
    )
    return payment, True


def process_webhook(db: Session, *, payload: WebhookPayload) -> tuple[dict, bool]:
    """Process provider webhook exactly-once per event_id.

    Returns (result_dict, deduped).
    - Same event_id twice -> deduped=True, no state change.
    - Terminal bookings (CONFIRMED/CANCELLED) are never downgraded.
    """
    seen = db.get(WebhookEvent, payload.event_id)
    if seen:
        booking = db.get(Booking, payload.booking_id) if payload.booking_id else None
        log.info("webhook_duplicate_ignored", event_id=payload.event_id)
        return (
            {
                "booking_id": payload.booking_id,
                "booking_status": booking.status if booking else None,
                "payment_id": seen.payment_id,
                "message": "Duplicate event ignored (idempotent replay)",
            },
            True,
        )

    booking = db.get(Booking, payload.booking_id)
    if booking is None:
        # Do NOT record the event: caller should fix the booking_id and retry.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")

    # Terminal-state guard: never corrupt a finished booking via late/duplicate provider events.
    if booking.status in TERMINAL_BOOKING_STATES and payload.status == "FAILED":
        # Record the event so replays stay cheap, but keep booking untouched.
        event = WebhookEvent(
            event_id=payload.event_id,
            booking_id=booking.id,
            payment_id=None,
            event_type=f"payment.{payload.status.lower()}",
            payload=payload.model_dump(),
            result="ignored_terminal_state",
        )
        db.add(event)
        db.commit()
        return (
            {
                "booking_id": booking.id,
                "booking_status": booking.status,
                "payment_id": None,
                "message": f"Ignored {payload.status} for terminal booking {booking.status}",
            },
            False,
        )

    if booking.status == BookingStatus.CANCELLED.value:
        event = WebhookEvent(
            event_id=payload.event_id,
            booking_id=booking.id,
            payment_id=None,
            event_type=f"payment.{payload.status.lower()}",
            payload=payload.model_dump(),
            result="ignored_cancelled",
        )
        db.add(event)
        db.commit()
        return (
            {
                "booking_id": booking.id,
                "booking_status": booking.status,
                "payment_id": None,
                "message": "Booking already cancelled; payment event ignored",
            },
            False,
        )

    provider_payment_id = payload.provider_payment_id or f"pay_mock_wh_{uuid.uuid4().hex[:12]}"
    if payload.status == "SUCCESS":
        payment_status = PaymentStatus.SUCCESS.value
        new_booking_status = BookingStatus.CONFIRMED.value
        failure_reason = None
    else:
        payment_status = PaymentStatus.FAILED.value
        new_booking_status = BookingStatus.FAILED.value
        failure_reason = payload.failure_reason or "Provider reported payment failure"

    payment = Payment(
        booking_id=booking.id,
        amount=booking.amount,
        currency=booking.currency,
        status=payment_status,
        provider_payment_id=provider_payment_id,
        provider_event_id=payload.event_id,
        failure_reason=failure_reason,
    )
    booking.status = new_booking_status
    db.add(payment)
    db.flush()  # get payment.id before recording the event

    event = WebhookEvent(
        event_id=payload.event_id,
        booking_id=booking.id,
        payment_id=payment.id,
        event_type=f"payment.{payload.status.lower()}",
        payload=payload.model_dump(),
        result="processed",
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent delivery of the same event: treat as duplicate.
        db.rollback()
        seen = db.get(WebhookEvent, payload.event_id)
        refreshed = db.get(Booking, booking.id)
        log.info("webhook_race_deduped", event_id=payload.event_id)
        return (
            {
                "booking_id": booking.id,
                "booking_status": refreshed.status if refreshed else None,
                "payment_id": seen.payment_id if seen else None,
                "message": "Duplicate event ignored (concurrent delivery)",
            },
            True,
        )

    db.refresh(payment)
    log.info(
        "webhook_processed",
        event_id=payload.event_id,
        booking_id=booking.id,
        booking_status=new_booking_status,
    )
    return (
        {
            "booking_id": booking.id,
            "booking_status": new_booking_status,
            "payment_id": payment.id,
            "message": f"Booking {new_booking_status.lower()} via webhook",
        },
        False,
    )
