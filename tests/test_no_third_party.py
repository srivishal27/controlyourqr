"""Supply-chain and no-egress guarantees, enforced in CI.

These tests are the reason a visitor can believe the privacy claim. If someone
later pastes in a CDN link, a web font or an analytics snippet, the build
breaks here rather than quietly shipping.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
STATIC = ROOT / "app" / "static"

# Attributes that cause the browser to *load* something. Hyperlinks in prose
# are fine — pointing at GitHub is not the same as executing code from it.
RESOURCE_ATTR_RE = re.compile(
    r"""(?:src|srcset)\s*=\s*["']([^"']+)["']""", re.IGNORECASE
)
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)

CSS_URL_RE = re.compile(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", re.IGNORECASE)
CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\()?\s*[\"']([^\"']+)", re.IGNORECASE)

EXTERNAL_RE = re.compile(r"^(?:https?:)?//", re.IGNORECASE)

# Live network primitives. Comment lines are skipped, so the file may still
# *describe* them.
NETWORK_TOKENS = [
    "fetch(",
    "XMLHttpRequest",
    "sendBeacon",
    "WebSocket",
    "EventSource",
    "importScripts",
    "navigator.connection",
]
DYNAMIC_CODE_TOKENS = ["eval(", "new Function"]


def _templates():
    return sorted(TEMPLATES.rglob("*.html"))


def _scripts():
    return sorted(STATIC.rglob("*.js"))


def _is_comment(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(("//", "/*", "*"))


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("template", _templates(), ids=lambda p: p.name)
def test_templates_load_no_external_resources(template):
    html = template.read_text(encoding="utf-8")

    for url in RESOURCE_ATTR_RE.findall(html):
        assert not EXTERNAL_RE.match(url), f"{template.name} loads external resource {url}"

    for tag in LINK_TAG_RE.findall(html):
        for url in HREF_RE.findall(tag):
            assert not EXTERNAL_RE.match(url), f"{template.name} <link> to external {url}"


@pytest.mark.parametrize("template", _templates(), ids=lambda p: p.name)
def test_templates_have_no_inline_scripts_or_styles(template):
    """Our CSP has no unsafe-inline, so inline blocks would silently break."""
    html = template.read_text(encoding="utf-8")

    inline_scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html, re.IGNORECASE)
    assert not inline_scripts, f"{template.name} has an inline <script>"

    assert not re.search(r"<style\b", html, re.IGNORECASE), f"{template.name} has a <style> block"
    assert not re.search(r"""\sstyle\s*=\s*["']""", html), f"{template.name} has a style attribute"


@pytest.mark.parametrize("template", _templates(), ids=lambda p: p.name)
def test_templates_have_no_inline_event_handlers(template):
    html = template.read_text(encoding="utf-8")
    handlers = re.findall(r"""\son[a-z]+\s*=\s*["']""", html, re.IGNORECASE)
    assert not handlers, f"{template.name} has inline event handlers: {handlers}"


# --------------------------------------------------------------------------- #
# Stylesheet
# --------------------------------------------------------------------------- #

def test_stylesheet_fetches_nothing_external():
    css = (STATIC / "css" / "style.css").read_text(encoding="utf-8")

    for url in CSS_URL_RE.findall(css):
        assert not EXTERNAL_RE.match(url), f"stylesheet references external {url}"

    assert not CSS_IMPORT_RE.findall(css), "stylesheet uses @import"


def test_stylesheet_uses_only_locally_available_fonts():
    """No webfont downloads: the design runs on the system font stack."""
    css = (STATIC / "css" / "style.css").read_text(encoding="utf-8")
    assert "@font-face" not in css
    assert "fonts.googleapis.com" not in css


# --------------------------------------------------------------------------- #
# JavaScript
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("script", _scripts(), ids=lambda p: p.name)
def test_scripts_contain_no_network_calls(script):
    code = script.read_text(encoding="utf-8")
    offenders = [
        (number, token)
        for number, line in enumerate(code.splitlines(), start=1)
        if not _is_comment(line)
        for token in NETWORK_TOKENS
        if token in line
    ]
    assert not offenders, f"{script.name} contains network calls: {offenders}"


@pytest.mark.parametrize("script", _scripts(), ids=lambda p: p.name)
def test_scripts_contain_no_dynamic_code_execution(script):
    code = script.read_text(encoding="utf-8")
    offenders = [
        (number, token)
        for number, line in enumerate(code.splitlines(), start=1)
        if not _is_comment(line)
        for token in DYNAMIC_CODE_TOKENS
        if token in line
    ]
    assert not offenders, f"{script.name} executes dynamic code: {offenders}"


def test_vendor_bundle_is_present_and_pinned():
    bundle = STATIC / "js" / "vendor" / "qrcode.min.js"
    licence = STATIC / "js" / "vendor" / "qrcode.LICENSE.txt"

    assert bundle.is_file(), "vendored QR encoder is missing"
    assert bundle.stat().st_size > 10_000, "vendored bundle looks truncated"
    assert licence.is_file(), "upstream licence must ship with the bundle"

    build_script = (ROOT / "tools" / "build-vendor.sh").read_text(encoding="utf-8")
    assert "qrcode@" in build_script, "vendor build script must pin an exact version"


# --------------------------------------------------------------------------- #
# Server
# --------------------------------------------------------------------------- #

def test_server_exposes_no_endpoint_that_accepts_input(app):
    """Nothing can be POSTed to this application, by construction."""
    for rule in app.url_map.iter_rules():
        assert rule.methods <= {"GET", "HEAD", "OPTIONS"}, f"{rule} accepts {rule.methods}"
