"""Booking business rules kept out of the route layer (testable, reusable)."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus
from app.models.centre import Centre
from app.models.centre_test import CentreTest
from app.models.diagnostic_test import DiagnosticTest
from app.schemas.booking import BookingCreate


def create_booking(
    db: Session, *, user_id: int, payload: BookingCreate, idempotency_key: str | None
) -> tuple[Booking, bool]:
    """Returns (booking, created). Honors Idempotency-Key per user when supplied."""
    if idempotency_key:
        existing = (
            db.query(Booking)
            .filter(Booking.user_id == user_id, Booking.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing, False

    centre = db.get(Centre, payload.centre_id)
    if centre is None or not centre.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diagnostic centre not found")

    test = db.get(DiagnosticTest, payload.test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diagnostic test not found")

    link = (
        db.query(CentreTest)
        .filter(CentreTest.centre_id == centre.id, CentreTest.test_id == test.id)
        .first()
    )
    if link is None or not link.is_available:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Test '{test.code}' is not offered at centre '{centre.name}'",
        )

    booking = Booking(
        user_id=user_id,
        centre_id=centre.id,
        test_id=test.id,
        appointment_time=payload.appointment_time.replace(tzinfo=None),
        amount=link.price,
        currency=link.currency,
        status=BookingStatus.PENDING.value,
        idempotency_key=idempotency_key,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking, True


def get_owned_booking(db: Session, *, user_id: int, booking_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.user_id != user_id:
        # 404 (not 403) avoids leaking existence of other users' bookings.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    return booking


def cancel_booking(db: Session, *, booking: Booking) -> Booking:
    if booking.status == BookingStatus.CANCELLED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Booking is already cancelled")
    if booking.status not in (BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot cancel a booking with status {booking.status}",
        )
    booking.status = BookingStatus.CANCELLED.value
    db.commit()
    db.refresh(booking)
    return booking
