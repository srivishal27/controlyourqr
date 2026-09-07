"""Application configuration.

Values are read from the environment so that the same code runs unchanged in
development and production.  Nothing here is secret: the application stores no
user data and has no database, sessions or authentication.
"""

from __future__ import annotations

import os


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class BaseConfig:
    """Settings shared by every environment."""

    SITE_NAME = "ControlYourQR"
    SITE_TAGLINE = "QR codes that never leave your browser."
    CANONICAL_ORIGIN = os.environ.get("CANONICAL_ORIGIN", "https://controlyourqr.com")
    CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "hello@controlyourqr.com")

    # No cookies or sessions are issued, but Flask still wants a key present.
    SECRET_KEY = os.environ.get("SECRET_KEY", "not-used-no-sessions-are-issued")

    JSON_SORT_KEYS = False
    TRAP_BAD_REQUEST_ERRORS = True

    # Static assets are fingerprinted with ?v=<hash>, so they can be cached hard.
    SEND_FILE_MAX_AGE_DEFAULT = 60 * 60 * 24 * 365

    # Emit Strict-Transport-Security. Enabled in production, where TLS is
    # terminated by nginx; disabled locally so http://127.0.0.1 keeps working.
    ENABLE_HSTS = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    SEND_FILE_MAX_AGE_DEFAULT = 0


class ProductionConfig(BaseConfig):
    DEBUG = False
    ENABLE_HSTS = _env_bool("ENABLE_HSTS", True)


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = False


_CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    """Return the config class for ``name`` (defaults to $FLASK_ENV)."""
    key = (name or os.environ.get("FLASK_ENV") or "production").strip().lower()
    return _CONFIGS.get(key, ProductionConfig)
