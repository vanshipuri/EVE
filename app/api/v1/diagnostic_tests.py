from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.diagnostic_test import DiagnosticTest
from app.models.user import User
from app.schemas.booking import Paginated
from app.schemas.test import DiagnosticTestCreate, DiagnosticTestOut, DiagnosticTestUpdate

router = APIRouter(prefix="/tests", tags=["diagnostic-tests"])


@router.post("/", response_model=DiagnosticTestOut, status_code=status.HTTP_201_CREATED)
def create_test(
    payload: DiagnosticTestCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    existing = db.query(DiagnosticTest).filter(DiagnosticTest.code == payload.code).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Test code already exists")
    test = DiagnosticTest(
        name=payload.name.strip(),
        code=payload.code.strip(),
        description=payload.description,
        category=payload.category,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


@router.get("/", response_model=Paginated[DiagnosticTestOut])
def list_tests(
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, description="Search by name or code"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    query = db.query(DiagnosticTest)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (DiagnosticTest.name.ilike(like)) | (DiagnosticTest.code.ilike(like))
        )
    total = query.count()
    items = query.order_by(DiagnosticTest.id).limit(limit).offset(offset).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{test_id}", response_model=DiagnosticTestOut)
def get_test(test_id: int, db: Session = Depends(get_db)):
    test = db.get(DiagnosticTest, test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test not found")
    return test


@router.patch("/{test_id}", response_model=DiagnosticTestOut)
def update_test(
    test_id: int,
    payload: DiagnosticTestUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    test = db.get(DiagnosticTest, test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(test, field, value)
    db.commit()
    db.refresh(test)
    return test
