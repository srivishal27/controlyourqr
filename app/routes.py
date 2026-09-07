"""HTTP routes.

Every route here is a GET that returns a static document. There is no endpoint
that accepts user content, because no user content is ever sent to the server.
"""

from __future__ import annotations

import datetime as dt

from flask import Blueprint, Flask, Response, current_app, render_template, url_for

bp = Blueprint("site", __name__)


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #

@bp.get("/")
def index() -> str:
    return render_template("index.html", page="generator")


@bp.get("/privacy")
def privacy() -> str:
    return render_template("privacy.html", page="privacy")


@bp.get("/security")
def security() -> str:
    return render_template("security.html", page="security")


# --------------------------------------------------------------------------- #
# Operational + well-known endpoints
# --------------------------------------------------------------------------- #

@bp.get("/healthz")
def healthz() -> Response:
    """Liveness probe for systemd, nginx and uptime monitoring."""
    return Response("ok\n", mimetype="text/plain", headers={"Cache-Control": "no-store"})


@bp.get("/robots.txt")
def robots() -> Response:
    sitemap = f"{current_app.config['CANONICAL_ORIGIN']}/sitemap.xml"
    body = f"User-agent: *\nAllow: /\n\nSitemap: {sitemap}\n"
    return Response(body, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap() -> Response:
    origin = current_app.config["CANONICAL_ORIGIN"].rstrip("/")
    today = dt.date.today().isoformat()
    paths = [("/", "1.0"), ("/security", "0.6"), ("/privacy", "0.5")]

    entries = "\n".join(
        "  <url>"
        f"<loc>{origin}{path}</loc>"
        f"<lastmod>{today}</lastmod>"
        f"<priority>{priority}</priority>"
        "</url>"
        for path, priority in paths
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )
    return Response(body, mimetype="application/xml")


@bp.get("/.well-known/security.txt")
def security_txt() -> Response:
    """RFC 9116 contact information for vulnerability reports."""
    origin = current_app.config["CANONICAL_ORIGIN"].rstrip("/")
    expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=365)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    body = (
        f"Contact: mailto:{current_app.config['CONTACT_EMAIL']}\n"
        f"Expires: {expires}\n"
        "Preferred-Languages: en\n"
        f"Canonical: {origin}/.well-known/security.txt\n"
        f"Policy: {origin}/security\n"
    )
    return Response(body, mimetype="text/plain")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

@bp.app_errorhandler(404)
def not_found(_error) -> tuple[str, int]:
    return render_template("error.html", code=404, message="Page not found"), 404


@bp.app_errorhandler(500)
def server_error(_error) -> tuple[str, int]:
    return render_template("error.html", code=500, message="Something went wrong"), 500


# --------------------------------------------------------------------------- #
# Template helpers
# --------------------------------------------------------------------------- #

def register_template_helpers(
    app: Flask, fingerprints: dict[str, str], version: str
) -> None:
    """Expose asset fingerprinting and site metadata to Jinja templates."""

    @app.template_global()
    def asset_url(filename: str) -> str:
        """URL for a static file, suffixed with its content hash."""
        digest = fingerprints.get(filename)
        if digest is None:
            return url_for("static", filename=filename)
        return url_for("static", filename=filename, v=digest)

    @app.context_processor
    def inject_globals() -> dict[str, object]:
        return {
            "site_name": app.config["SITE_NAME"],
            "site_tagline": app.config["SITE_TAGLINE"],
            "canonical_origin": app.config["CANONICAL_ORIGIN"].rstrip("/"),
            "contact_email": app.config["CONTACT_EMAIL"],
            "app_version": version,
            "current_year": dt.date.today().year,
        }
