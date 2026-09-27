from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.cache import cache_get, cache_invalidate_prefix, cache_set
from app.db.session import get_db
from app.models.centre import Centre
from app.models.centre_test import CentreTest
from app.models.diagnostic_test import DiagnosticTest
from app.models.user import User
from app.schemas.booking import Paginated
from app.schemas.centre import (
    CentreCreate,
    CentreDetailOut,
    CentreOut,
    CentreTestCreate,
    CentreTestOut,
    CentreTestUpdate,
    CentreUpdate,
)

router = APIRouter(prefix="/centres", tags=["centres"])
CACHE_PREFIX = "centres:list"


def _centre_detail(centre: Centre) -> dict:
    return {
        "id": centre.id,
        "name": centre.name,
        "location": centre.location,
        "phone": centre.phone,
        "is_active": centre.is_active,
        "created_at": centre.created_at.isoformat(),
        "tests": [
            {
                "id": link.id,
                "price": str(link.price),
                "currency": link.currency,
                "is_available": link.is_available,
                "test": {
                    "id": link.test.id,
                    "name": link.test.name,
                    "code": link.test.code,
                    "description": link.test.description,
                    "category": link.test.category,
                },
            }
            for link in centre.centre_tests
        ],
    }


@router.post("/", response_model=CentreOut, status_code=status.HTTP_201_CREATED)
def create_centre(
    payload: CentreCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    centre = Centre(
        name=payload.name.strip(), location=payload.location.strip(), phone=payload.phone
    )
    db.add(centre)
    db.commit()
    db.refresh(centre)
    cache_invalidate_prefix(CACHE_PREFIX)
    return centre


@router.get("/", response_model=Paginated[CentreOut])
def list_centres(
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, description="Search by name or location"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    cache_key = f"{CACHE_PREFIX}:{q}:{limit}:{offset}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    query = db.query(Centre).filter(Centre.is_active.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter((Centre.name.ilike(like)) | (Centre.location.ilike(like)))
    total = query.count()
    items = query.order_by(Centre.id).limit(limit).offset(offset).all()
    result = {
        "items": [
            {
                "id": c.id,
                "name": c.name,
                "location": c.location,
                "phone": c.phone,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat(),
            }
            for c in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
    cache_set(cache_key, result, ttl_seconds=60)
    return result


@router.get("/{centre_id}", response_model=CentreDetailOut)
def get_centre(centre_id: int, db: Session = Depends(get_db)):
    centre = (
        db.query(Centre)
        .options(joinedload(Centre.centre_tests).joinedload(CentreTest.test))
        .filter(Centre.id == centre_id, Centre.is_active.is_(True))
        .first()
    )
    if centre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Centre not found")
    return _centre_detail(centre)


@router.patch("/{centre_id}", response_model=CentreOut)
def update_centre(
    centre_id: int,
    payload: CentreUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    centre = db.get(Centre, centre_id)
    if centre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Centre not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(centre, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(centre)
    cache_invalidate_prefix(CACHE_PREFIX)
    return centre


@router.delete("/{centre_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_centre(
    centre_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Soft-delete so historical bookings stay intact."""
    centre = db.get(Centre, centre_id)
    if centre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Centre not found")
    centre.is_active = False
    db.commit()
    cache_invalidate_prefix(CACHE_PREFIX)
    return None


# ---- Tests offered by a centre (with price) ----


@router.post(
    "/{centre_id}/tests", response_model=CentreTestOut, status_code=status.HTTP_201_CREATED
)
def attach_test(
    centre_id: int,
    payload: CentreTestCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    centre = db.get(Centre, centre_id)
    if centre is None or not centre.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Centre not found")
    test = db.get(DiagnosticTest, payload.test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diagnostic test not found")
    existing = (
        db.query(CentreTest)
        .filter(CentreTest.centre_id == centre_id, CentreTest.test_id == payload.test_id)
        .first()
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Test already linked to this centre")
    link = CentreTest(
        centre_id=centre_id,
        test_id=payload.test_id,
        price=payload.price,
        currency=payload.currency,
        is_available=payload.is_available,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    cache_invalidate_prefix(CACHE_PREFIX)
    return link


@router.get("/{centre_id}/tests", response_model=list[CentreTestOut])
def list_centre_tests(centre_id: int, db: Session = Depends(get_db)):
    centre = db.get(Centre, centre_id)
    if centre is None or not centre.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Centre not found")
    return (
        db.query(CentreTest)
        .options(joinedload(CentreTest.test))
        .filter(CentreTest.centre_id == centre_id)
        .order_by(CentreTest.id)
        .all()
    )


@router.patch("/{centre_id}/tests/{link_id}", response_model=CentreTestOut)
def update_centre_test(
    centre_id: int,
    link_id: int,
    payload: CentreTestUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    link = (
        db.query(CentreTest)
        .filter(CentreTest.id == link_id, CentreTest.centre_id == centre_id)
        .first()
    )
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Centre-test link not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(link, field, value)
    db.commit()
    db.refresh(link)
    cache_invalidate_prefix(CACHE_PREFIX)
    return link


@router.delete("/{centre_id}/tests/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def detach_test(
    centre_id: int,
    link_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    link = (
        db.query(CentreTest)
        .filter(CentreTest.id == link_id, CentreTest.centre_id == centre_id)
        .first()
    )
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Centre-test link not found")
    db.delete(link)
    db.commit()
    cache_invalidate_prefix(CACHE_PREFIX)
    return None
