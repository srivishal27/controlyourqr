"""WSGI entry point.

Used by gunicorn in production:

    gunicorn --config gunicorn.conf.py wsgi:application
"""

from app import create_app

application = create_app()

# Convenience alias for tools that look for `app`.
app = application

if __name__ == "__main__":  # pragma: no cover - local development only
    application.run(host="127.0.0.1", port=5000, debug=True)
