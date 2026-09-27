def test_demo_page_served(client):
    r = client.get("/demo")
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
