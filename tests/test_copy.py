"""House style for user-facing copy.

Em and en dashes are banned from anything a visitor reads. They are a tell that
makes prose read as machine-written, which is the last impression a site whose
whole pitch is trustworthiness can afford.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
STATIC = ROOT / "app" / "static"

DASHES = "—–"  # em dash, en dash
DASH_RE = re.compile(f"[{DASHES}]")


def _offending_lines(text: str, skip_comments: bool = False):
    found = []
    for number, line in enumerate(text.splitlines(), start=1):
        if skip_comments and line.lstrip().startswith(("//", "/*", "*")):
            continue
        if DASH_RE.search(line):
            found.append((number, line.strip()[:90]))
    return found


@pytest.mark.parametrize(
    "template", sorted(TEMPLATES.rglob("*.html")), ids=lambda p: p.name
)
def test_templates_use_no_em_dashes(template):
    offenders = _offending_lines(template.read_text(encoding="utf-8"))
    assert not offenders, f"{template.name} contains em/en dashes: {offenders}"


@pytest.mark.parametrize(
    "script",
    sorted(p for p in (STATIC / "js").glob("*.js")),
    ids=lambda p: p.name,
)
def test_script_strings_use_no_em_dashes(script):
    """Only user-visible strings matter, so comments are exempt."""
    offenders = _offending_lines(script.read_text(encoding="utf-8"), skip_comments=True)
    assert not offenders, f"{script.name} has em/en dashes in live code: {offenders}"


def test_rendered_pages_are_clean(client):
    """Belt and braces: check the actual bytes sent to a browser."""
    for path in ("/", "/privacy", "/security"):
        body = client.get(path).get_data(as_text=True)
        assert not DASH_RE.search(body), f"{path} renders an em/en dash"
