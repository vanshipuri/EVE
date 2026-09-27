from datetime import datetime, timedelta


def _future(days=2):
    return (datetime.utcnow() + timedelta(days=days)).isoformat()


def _book(client, headers, catalogue):
    c, t = catalogue["centre"], catalogue["cbc"]
    r = client.post(
        "/api/v1/bookings/",
        json={"centre_id": c["id"], "test_id": t["id"], "appointment_time": _future()},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_payment_success_confirms_booking(client, authed, catalogue):
    headers, _ = authed
    booking = _book(client, headers, catalogue)
    pay = client.post(
        "/api/v1/payments/", json={"booking_id": booking["id"]}, headers=headers
    )
    assert pay.status_code == 201, pay.text
    assert pay.json()["status"] == "SUCCESS"

    refreshed = client.get(f"/api/v1/bookings/{booking['id']}", headers=headers).json()
    assert refreshed["status"] == "CONFIRMED"


def test_payment_failure_marks_booking_failed_and_allows_retry(client, authed, catalogue):
    headers, _ = authed
    booking = _book(client, headers, catalogue)
    pay = client.post(
        "/api/v1/payments/",
        json={"booking_id": booking["id"], "simulate_failure": True},
        headers=headers,
    )
    assert pay.status_code == 201
    assert pay.json()["status"] == "FAILED"
    assert client.get(f"/api/v1/bookings/{booking['id']}", headers=headers).json()["status"] == "FAILED"

    # Retry without failure succeeds
    retry = client.post(
        "/api/v1/payments/", json={"booking_id": booking["id"]}, headers=headers
    )
    assert retry.status_code == 201
    assert retry.json()["status"] == "SUCCESS"


def test_payment_rejects_double_pay_on_confirmed(client, authed, catalogue):
    headers, _ = authed
    booking = _book(client, headers, catalogue)
    assert client.post("/api/v1/payments/", json={"booking_id": booking["id"]}, headers=headers).status_code == 201
    second = client.post("/api/v1/payments/", json={"booking_id": booking["id"]}, headers=headers)
    assert second.status_code == 409


def test_payment_rejects_cancelled_and_invalid_booking(client, authed, catalogue):
    headers, _ = authed
    booking = _book(client, headers, catalogue)
    client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=headers)
    assert client.post("/api/v1/payments/", json={"booking_id": booking["id"]}, headers=headers).status_code == 409
    assert client.post("/api/v1/payments/", json={"booking_id": 999999}, headers=headers).status_code == 404


def test_payment_idempotency_key(client, authed, catalogue):
    headers, _ = authed
    booking = _book(client, headers, catalogue)
    h = {**headers, "Idempotency-Key": "pay-key-xyz"}
    r1 = client.post("/api/v1/payments/", json={"booking_id": booking["id"]}, headers=h)
    r2 = client.post("/api/v1/payments/", json={"booking_id": booking["id"]}, headers=h)
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_webhook_idempotent_no_duplicates(client, authed, catalogue):
    headers, _ = authed
    booking = _book(client, headers, catalogue)
    payload = {"event_id": "evt_test_001", "booking_id": booking["id"], "status": "SUCCESS"}

    first = client.post("/api/v1/payments/webhook/", json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["deduped"] is False
    assert first.json()["booking_status"] == "CONFIRMED"
    payment_id = first.json()["payment_id"]

    before = client.get("/api/v1/payments/", headers=headers).json()["total"]

    # Replay same event 3 times
    for _ in range(3):
        replay = client.post("/api/v1/payments/webhook/", json=payload)
        assert replay.status_code == 200
        assert replay.json()["deduped"] is True
        assert replay.json()["payment_id"] == payment_id

    after = client.get("/api/v1/payments/", headers=headers).json()["total"]
    assert after == before  # no duplicate payments created

    # Booking still CONFIRMED (not corrupted)
    assert client.get(f"/api/v1/bookings/{booking['id']}", headers=headers).json()["status"] == "CONFIRMED"


def test_webhook_failed_event_and_invalid_booking(client, authed, catalogue):
    headers, _ = authed
    booking = _book(client, headers, catalogue)
    failed = client.post(
        "/api/v1/payments/webhook/",
        json={"event_id": "evt_fail_001", "booking_id": booking["id"], "status": "FAILED"},
    )
    assert failed.status_code == 200
    assert failed.json()["booking_status"] == "FAILED"

    invalid = client.post(
        "/api/v1/payments/webhook/",
        json={"event_id": "evt_bad_001", "booking_id": 999999, "status": "SUCCESS"},
    )
    assert invalid.status_code == 404


def test_webhook_ignores_terminal_states(client, authed, catalogue):
    headers, _ = authed
    booking = _book(client, headers, catalogue)
    # Confirm via direct payment
    assert client.post("/api/v1/payments/", json={"booking_id": booking["id"]}, headers=headers).status_code == 201
    # Late FAILED webhook must NOT downgrade CONFIRMED
    late = client.post(
        "/api/v1/payments/webhook/",
        json={"event_id": "evt_late_001", "booking_id": booking["id"], "status": "FAILED"},
    )
    assert late.status_code == 200
    assert client.get(f"/api/v1/bookings/{booking['id']}", headers=headers).json()["status"] == "CONFIRMED"
