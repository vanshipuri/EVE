def test_signup_login_me(client):
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "a@x.com", "password": "password123", "full_name": "Asha Verma"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "a@x.com"

    login = client.post("/api/v1/auth/login", json={"email": "a@x.com", "password": "password123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@x.com"


def test_duplicate_signup_rejected(client):
    body = {"email": "dup@x.com", "password": "password123", "full_name": "Dup User"}
    assert client.post("/api/v1/auth/signup", json=body).status_code == 201
    assert client.post("/api/v1/auth/signup", json=body).status_code == 400


def test_login_wrong_password(client):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "w@x.com", "password": "password123", "full_name": "Wrong Pass"},
    )
    r = client.post("/api/v1/auth/login", json={"email": "w@x.com", "password": "nope-nope-no"})
    assert r.status_code == 401


def test_signup_validation(client):
    # Short password + bad email -> 422
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "not-an-email", "password": "short", "full_name": "X"},
    )
    assert r.status_code == 422


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    )
