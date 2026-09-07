"""ControlYourQR - application factory.

The server's only job is to hand the browser a set of static files. It never
receives, processes, logs or stores the content a user encodes into a QR code:
that work happens entirely in the visitor's browser (see app/static/js/app.js).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from flask import Flask

from .config import BaseConfig, get_config
from .security import init_security

__version__ = "1.0.0"


def _asset_fingerprints(static_folder: Path) -> dict[str, str]:
    """Map each static file to a short content hash, for cache-busting URLs.

    Computed once at start-up. Content-addressed URLs let us cache assets for a
    year while still shipping updates the instant they are deployed.
    """
    fingerprints: dict[str, str] = {}
    if not static_folder.is_dir():
        return fingerprints

    for path in static_folder.rglob("*"):
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:10]
        fingerprints[path.relative_to(static_folder).as_posix()] = digest
    return fingerprints


def create_app(config_name: str | None = None) -> Flask:
    """Build and return the configured Flask application."""
    app = Flask(__name__, static_folder="static", template_folder="templates")

    config_class: type[BaseConfig] = get_config(config_name)
    app.config.from_object(config_class)

    _configure_logging(app)
    init_security(app)

    from .routes import bp as site_bp

    app.register_blueprint(site_bp)

    fingerprints = _asset_fingerprints(Path(app.static_folder))
    app.logger.info("Fingerprinted %d static assets", len(fingerprints))

    from .routes import register_template_helpers

    register_template_helpers(app, fingerprints, version=__version__)

    return app


def _configure_logging(app: Flask) -> None:
    """Log to stderr so systemd/journald owns retention and rotation.

    Access logs are gunicorn's job; here we only want application-level events.
    """
    if app.config.get("TESTING"):
        app.logger.setLevel(logging.CRITICAL)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
    )
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.DEBUG if app.config.get("DEBUG") else logging.INFO)
