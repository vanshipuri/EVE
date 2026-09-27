from datetime import datetime, timedelta


def _future(days=2):
    return (datetime.utcnow() + timedelta(days=days)).isoformat()


def test_booking_happy_path_and_amount_snapshot(client, authed, catalogue):
    headers, _ = authed
    c, t = catalogue["centre"], catalogue["cbc"]
    r = client.post(
        "/api/v1/bookings/",
        json={"centre_id": c["id"], "test_id": t["id"], "appointment_time": _future()},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "PENDING"
    assert body["amount"] == "299.00"  # snapshot from centre_tests.price
    assert body["centre_name"] == c["name"]


def test_booking_rejects_past_time(client, authed, catalogue):
    headers, _ = authed
    c, t = catalogue["centre"], catalogue["cbc"]
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    r = client.post(
        "/api/v1/bookings/",
        json={"centre_id": c["id"], "test_id": t["id"], "appointment_time": past},
        headers=headers,
    )
    assert r.status_code == 422


def test_booking_rejects_unoffered_test(client, authed, catalogue):
    headers, _ = authed
    c = catalogue["centre"]
    other = client.post(
        "/api/v1/tests/", json={"name": "MRI Brain", "code": "MRI_BRAIN"}, headers=headers
    ).json()
    r = client.post(
        "/api/v1/bookings/",
        json={"centre_id": c["id"], "test_id": other["id"], "appointment_time": _future()},
        headers=headers,
    )
    assert r.status_code == 400


def test_booking_requires_auth_and_ownership(client, authed, catalogue):
    headers, _ = authed
    c, t = catalogue["centre"], catalogue["cbc"]
    # No token
    assert (
        client.post(
            "/api/v1/bookings/",
            json={"centre_id": c["id"], "test_id": t["id"], "appointment_time": _future()},
        ).status_code
        == 401
    )
    # Owner creates
    created = client.post(
        "/api/v1/bookings/",
        json={"centre_id": c["id"], "test_id": t["id"], "appointment_time": _future()},
        headers=headers,
    ).json()
    # Other user cannot see it (404, not leak)
    client.post(
        "/api/v1/auth/signup",
        json={"email": "other@x.com", "password": "password123", "full_name": "Other User"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": "other@x.com", "password": "password123"}
    ).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/v1/bookings/{created['id']}", headers=other_headers).status_code == 404
    assert client.post(f"/api/v1/bookings/{created['id']}/cancel", headers=other_headers).status_code == 404


def test_booking_idempotency_key(client, authed, catalogue):
    headers, _ = authed
    c, t = catalogue["centre"], catalogue["cbc"]
    h = {**headers, "Idempotency-Key": "book-key-123"}
    body = {"centre_id": c["id"], "test_id": t["id"], "appointment_time": _future()}
    r1 = client.post("/api/v1/bookings/", json=body, headers=h)
    r2 = client.post("/api/v1/bookings/", json=body, headers=h)
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_cancel_flow_and_double_cancel(client, authed, catalogue):
    headers, _ = authed
    c, t = catalogue["centre"], catalogue["cbc"]
    created = client.post(
        "/api/v1/bookings/",
        json={"centre_id": c["id"], "test_id": t["id"], "appointment_time": _future()},
        headers=headers,
    ).json()
    cancelled = client.post(f"/api/v1/bookings/{created['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    # Second cancel -> 409
    assert client.post(f"/api/v1/bookings/{created['id']}/cancel", headers=headers).status_code == 409
