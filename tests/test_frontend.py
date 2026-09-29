import pytest


@pytest.mark.parametrize("path", ["/", "/demo"])
def test_demo_pages_served(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "EVE Healthcare" in r.text
    assert "/static/app.js" in r.text


def test_static_assets_served(client):
    js = client.get("/static/app.js")
    assert js.status_code == 200
    assert "Demo Console" in js.text

    css = client.get("/static/styles.css")
    assert css.status_code == 200
    assert "--accent" in css.text
