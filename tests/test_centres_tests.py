def test_centre_crud_and_search(client, authed):
    headers, _ = authed
    c1 = client.post(
        "/api/v1/centres/", json={"name": "EVE - Kochi", "location": "Kochi, Kerala"}, headers=headers
    )
    assert c1.status_code == 201
    c2 = client.post(
        "/api/v1/centres/", json={"name": "EVE - Jaipur", "location": "Jaipur, Rajasthan"}, headers=headers
    )
    assert c2.status_code == 201

    # Public listing works without auth + pagination envelope
    listed = client.get("/api/v1/centres/?limit=10&offset=0")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 2
    assert body["limit"] == 10

    # Search
    found = client.get("/api/v1/centres/?q=Jaipur")
    assert found.status_code == 200
    assert any("Jaipur" in item["name"] for item in found.json()["items"])

    # Detail + update + soft delete
    detail = client.get(f"/api/v1/centres/{c1.json()['id']}")
    assert detail.status_code == 200

    upd = client.patch(
        f"/api/v1/centres/{c1.json()['id']}", json={"phone": "0484-0000000"}, headers=headers
    )
    assert upd.status_code == 200
    assert upd.json()["phone"] == "0484-0000000"

    assert client.delete(f"/api/v1/centres/{c1.json()['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/centres/{c1.json()['id']}").status_code == 404


def test_create_centre_requires_auth(client):
    r = client.post("/api/v1/centres/", json={"name": "Nope", "location": "Nowhere"})
    assert r.status_code == 401


def test_test_crud_and_duplicate_code(client, authed):
    headers, _ = authed
    t = client.post(
        "/api/v1/tests/",
        json={"name": "HbA1c", "code": "HBA1C", "category": "Pathology"},
        headers=headers,
    )
    assert t.status_code == 201

    dup = client.post(
        "/api/v1/tests/", json={"name": "HbA1c dup", "code": "HBA1C"}, headers=headers
    )
    assert dup.status_code == 409

    listed = client.get("/api/v1/tests/")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1


def test_centre_test_link_price_flow(client, authed):
    headers, _ = authed
    c = client.post(
        "/api/v1/centres/", json={"name": "EVE - Link", "location": "Pune"}, headers=headers
    ).json()
    t = client.post(
        "/api/v1/tests/", json={"name": "X-Ray", "code": "XRAY_CHEST"}, headers=headers
    ).json()

    link = client.post(
        f"/api/v1/centres/{c['id']}/tests",
        json={"test_id": t["id"], "price": "450.00"},
        headers=headers,
    )
    assert link.status_code == 201
    assert link.json()["price"] == "450.00"

    # Duplicate link -> 409
    dup = client.post(
        f"/api/v1/centres/{c['id']}/tests",
        json={"test_id": t["id"], "price": "500.00"},
        headers=headers,
    )
    assert dup.status_code == 409

    # Invalid price -> 422
    bad = client.post(
        f"/api/v1/centres/{c['id']}/tests",
        json={"test_id": t["id"], "price": "-10"},
        headers=headers,
    )
    assert bad.status_code == 422
