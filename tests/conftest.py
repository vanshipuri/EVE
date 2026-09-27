import os

# Must be set before app imports so test settings apply.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test_eve.db"
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.rate_limit import limiter
from app.db.session import Base, get_db

# Import models so metadata is complete
import app.models  # noqa: F401


@pytest.fixture(scope="session")
def test_engine():
    # Fresh file DB per test session (StaticPool keeps in-memory consistent if switched).
    if os.path.exists("./test_eve.db"):
        os.remove("./test_eve.db")
    engine = create_engine(
        "sqlite:///./test_eve.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()
    if os.path.exists("./test_eve.db"):
        os.remove("./test_eve.db")


@pytest.fixture()
def db(test_engine):
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = TestingSession()
    yield session
    session.rollback()
    session.close()
    # Wipe data between tests for isolation (keep schema).
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture()
def client(db):
    from app.main import create_app

    def override_get_db():
        try:
            yield db
        finally:
            pass

    test_app = create_app()
    # Disable rate limiting entirely in tests.
    limiter.enabled = False
    test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_app) as c:
        yield c
    test_app.dependency_overrides.clear()


@pytest.fixture()
def authed(client):
    """Create a user and return (headers, user_json)."""
    email = "neha@example.com"
    res = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "password123", "full_name": "Neha Sharma"},
    )
    assert res.status_code == 201, res.text
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, res.json()


@pytest.fixture()
def catalogue(client, authed):
    """Seed one centre + two tests + priced links. Returns ids."""
    headers, _ = authed
    c = client.post(
        "/api/v1/centres/",
        json={"name": "EVE - Test Centre", "location": "Bengaluru", "phone": "080-00000001"},
        headers=headers,
    ).json()
    t1 = client.post(
        "/api/v1/tests/",
        json={"name": "Complete Blood Count", "code": "CBC", "category": "Pathology"},
        headers=headers,
    ).json()
    t2 = client.post(
        "/api/v1/tests/",
        json={"name": "Lipid Profile", "code": "LIPID", "category": "Pathology"},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/centres/{c['id']}/tests",
        json={"test_id": t1["id"], "price": "299.00"},
        headers=headers,
    )
    client.post(
        f"/api/v1/centres/{c['id']}/tests",
        json={"test_id": t2["id"], "price": "799.00"},
        headers=headers,
    )
    return {"centre": c, "cbc": t1, "lipid": t2}
