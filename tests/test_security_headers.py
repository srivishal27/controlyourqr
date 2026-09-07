"""The headers are the product, so they get tested like one."""

import pytest

from app.security import CSP_DIRECTIVES


@pytest.mark.parametrize(
    "header",
    [
        "Content-Security-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cross-Origin-Opener-Policy",
        "Cross-Origin-Resource-Policy",
        "Cross-Origin-Embedder-Policy",
    ],
)
def test_header_is_present(client, header):
    assert header in client.get("/").headers


def test_csp_blocks_all_outbound_requests(client):
    """connect-src 'none' is the guarantee the whole site rests on."""
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "connect-src 'none'" in csp


def test_csp_has_no_unsafe_escape_hatches(client):
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp


def test_csp_confines_every_source_to_this_origin():
    for directive in ("default-src", "script-src", "style-src"):
        assert CSP_DIRECTIVES[directive] == "'self'"


def test_csp_denies_framing_and_form_posts():
    assert CSP_DIRECTIVES["frame-ancestors"] == "'none'"
    assert CSP_DIRECTIVES["form-action"] == "'none'"
    assert CSP_DIRECTIVES["base-uri"] == "'none'"


def test_hsts_follows_configuration(client, app):
    # The testing config leaves TLS off, so HSTS must not be advertised.
    assert app.config["ENABLE_HSTS"] is False
    assert "Strict-Transport-Security" not in client.get("/").headers


def test_hsts_is_emitted_in_production():
    from app import create_app

    production = create_app("production")
    production.config["TESTING"] = True
    with production.test_client() as production_client:
        header = production_client.get("/").headers["Strict-Transport-Security"]
    assert "max-age=63072000" in header
    assert "includeSubDomains" in header


def test_no_cookies_are_set(client):
    assert "Set-Cookie" not in client.get("/").headers
