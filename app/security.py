"""Response hardening.

The single most important header here is the Content-Security-Policy, and the
single most important directive in it is ``connect-src 'none'``.

That directive makes the browser itself refuse every fetch(), XMLHttpRequest,
WebSocket, EventSource and sendBeacon originating from our pages.  It is the
mechanism that turns "we do not upload your data" from a promise into something
the user's browser enforces and any visitor can verify in DevTools.
"""

from __future__ import annotations

from flask import Flask, Response, request

# Rendered once at import time; the policy is static by design (no nonces, no
# per-request values) so that it can be audited by reading this file.
CSP_DIRECTIVES: dict[str, str] = {
    # Nothing loads from anywhere but our own origin.
    "default-src": "'self'",
    "script-src": "'self'",
    "style-src": "'self'",
    "font-src": "'self'",
    # data:/blob: are needed to paint the generated QR code and to hand the
    # user a downloadable file. Neither can reach the network.
    "img-src": "'self' data: blob:",
    # The whole point: the page cannot talk to any server, including ours.
    "connect-src": "'none'",
    "form-action": "'none'",
    "frame-ancestors": "'none'",
    "frame-src": "'none'",
    "object-src": "'none'",
    "media-src": "'none'",
    "worker-src": "'none'",
    "manifest-src": "'self'",
    "base-uri": "'none'",
}

CSP_HEADER = "; ".join(f"{key} {value}" for key, value in CSP_DIRECTIVES.items())

# Explicitly switch off browser features this site has no business using.
PERMISSIONS_POLICY = ", ".join(
    f"{feature}=()"
    for feature in (
        "accelerometer",
        "ambient-light-sensor",
        "autoplay",
        "battery",
        "camera",
        "display-capture",
        "document-domain",
        "encrypted-media",
        "geolocation",
        "gyroscope",
        "hid",
        "idle-detection",
        "local-fonts",
        "magnetometer",
        "microphone",
        "midi",
        "payment",
        "publickey-credentials-get",
        "screen-wake-lock",
        "serial",
        "usb",
        "xr-spatial-tracking",
    )
)

SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": CSP_HEADER,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": PERMISSIONS_POLICY,
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Embedder-Policy": "require-corp",
    # Nothing on this site is personalised, but make the intent explicit.
    "X-Robots-Tag": "index, follow",
}

HSTS_VALUE = "max-age=63072000; includeSubDomains; preload"


def _is_https(req) -> bool:
    """True when the client's connection to nginx used TLS.

    HSTS is meaningless — and per RFC 6797 ignored — on a plaintext response,
    so we emit it only once TLS is genuinely in front. This makes the header
    appear by itself the moment certbot lands, with nothing to remember to
    switch on afterwards.
    """
    forwarded = req.headers.get("X-Forwarded-Proto", "")
    return req.is_secure or forwarded.split(",")[0].strip().lower() == "https"


def init_security(app: Flask) -> None:
    """Attach the response hardening hook to ``app``."""

    @app.after_request
    def _apply_security_headers(response: Response) -> Response:
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)

        if app.config.get("ENABLE_HSTS") and _is_https(request):
            response.headers.setdefault("Strict-Transport-Security", HSTS_VALUE)

        # Advertise nothing about the stack.
        response.headers.pop("Server", None)
        return response
