from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.booking import Booking
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingOut, Paginated
from app.services.booking_service import cancel_booking, create_booking, get_owned_booking

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _to_out(booking: Booking) -> dict:
    return {
        "id": booking.id,
        "user_id": booking.user_id,
        "centre_id": booking.centre_id,
        "test_id": booking.test_id,
        "centre_name": booking.centre.name if booking.centre else None,
        "test_name": booking.test.name if booking.test else None,
        "appointment_time": booking.appointment_time,
        "amount": booking.amount,
        "currency": booking.currency,
        "status": booking.status,
        "created_at": booking.created_at,
        "updated_at": booking.updated_at,
    }


@router.post("/", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    booking, _ = create_booking(db, user_id=current.id, payload=payload, idempotency_key=idempotency_key)
    booking = (
        db.query(Booking)
        .options(joinedload(Booking.centre), joinedload(Booking.test))
        .filter(Booking.id == booking.id)
        .first()
    )
    return _to_out(booking)


@router.get("/", response_model=Paginated[BookingOut])
def list_mine(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    query = (
        db.query(Booking)
        .options(joinedload(Booking.centre), joinedload(Booking.test))
        .filter(Booking.user_id == current.id)
    )
    if status_filter:
        query = query.filter(Booking.status == status_filter.upper())
    total = query.count()
    items = query.order_by(Booking.id.desc()).limit(limit).offset(offset).all()
    return {"items": [_to_out(b) for b in items], "total": total, "limit": limit, "offset": offset}


@router.get("/{booking_id}", response_model=BookingOut)
def get_one(
    booking_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    booking = get_owned_booking(db, user_id=current.id, booking_id=booking_id)
    # Ensure relationships loaded for names
    db.refresh(booking)
    _ = booking.centre, booking.test
    return _to_out(booking)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel(
    booking_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    booking = get_owned_booking(db, user_id=current.id, booking_id=booking_id)
    booking = cancel_booking(db, booking=booking)
    db.refresh(booking)
    _ = booking.centre, booking.test
    return _to_out(booking)
