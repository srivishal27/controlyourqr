"""Route behaviour: every page renders, and the well-known endpoints work."""

import pytest


@pytest.mark.parametrize("path", ["/", "/privacy", "/security"])
def test_pages_render(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.mimetype == "text/html"


def test_generator_page_contains_the_tool(client):
    body = client.get("/").get_data(as_text=True)
    assert 'id="qr-canvas"' in body
    assert 'id="theme-toggle"' in body
    assert "js/vendor/qrcode.min.js" in body


def test_about_credits_the_author(client):
    body = client.get("/").get_data(as_text=True)
    assert "Vishal Srivastava" in body
    assert "IIT Kanpur" in body
    assert "security researcher" in body


def test_page_states_the_free_and_no_redirect_promise(client):
    body = client.get("/").get_data(as_text=True)
    assert "Free, forever" in body
    assert "Static codes, no redirects" in body


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_data(as_text=True).strip() == "ok"
    assert response.headers["Cache-Control"] == "no-store"


def test_robots_points_at_the_sitemap(client):
    body = client.get("/robots.txt").get_data(as_text=True)
    assert "User-agent: *" in body
    assert "/sitemap.xml" in body


def test_sitemap_is_wellformed_xml(client):
    from xml.etree import ElementTree

    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    root = ElementTree.fromstring(response.get_data())
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    locations = [node.text for node in root.iter(f"{namespace}loc")]
    assert any(url.endswith("/") for url in locations)


def test_security_txt_has_required_fields(client):
    body = client.get("/.well-known/security.txt").get_data(as_text=True)
    assert "Contact:" in body
    assert "Expires:" in body  # required by RFC 9116


def test_unknown_path_renders_the_404_page(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert "404" in response.get_data(as_text=True)


def test_static_assets_are_fingerprinted(client):
    body = client.get("/").get_data(as_text=True)
    assert "css/style.css?v=" in body
    assert "js/app.js?v=" in body
