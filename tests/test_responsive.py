"""Guards for the mobile fixes that fail silently when they regress.

Neither of these shows up as an error anywhere: the page simply scrolls
sideways, or iOS quietly zooms on every tap. Both were shipped broken once.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "app" / "static" / "css" / "style.css").read_text(encoding="utf-8")
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")


def _block(selector: str, source: str) -> str:
    """Return the declaration block for the first rule matching ``selector``."""
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", source)
    assert match, f"rule not found: {selector}"
    return match.group(1)


def test_single_column_track_cannot_be_widened_by_its_content():
    """`1fr` is minmax(auto, 1fr); the auto minimum caused page-wide h-scroll.

    The tab strip is min-width:max-content inside a horizontal scroller. With
    an auto track minimum, that content width set the track width and the whole
    document became wider than the viewport on every phone.
    """
    mobile = CSS.split("@media (max-width: 900px)", 1)[1]
    track = _block(".tool", mobile)
    assert "minmax(0, 1fr)" in track, f"single-column track must pin its minimum: {track!r}"
    assert not re.search(r"grid-template-columns:\s*1fr\s*;", track)


def test_form_fields_are_16px_on_mobile():
    """Under 16px, iOS Safari zooms the viewport when a field takes focus."""
    assert "@media (max-width: 768px)" in CSS
    mobile = CSS.split("@media (max-width: 768px)", 1)[1]
    sizes = re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", mobile[:1200])
    assert sizes, "no font-size declarations found in the mobile block"
    assert min(float(s) for s in sizes) >= 16, f"a mobile field is under 16px: {sizes}"


def test_panels_are_siblings_in_reading_order():
    """Input, then the code it produces, then appearance controls.

    They must be siblings of .tool for the mobile `order` to apply at all; when
    the options accordion lived inside the input card the preview was pushed
    650px down the page and you could not see your QR code while typing.
    """
    order = re.findall(r'class="panel panel-(\w+)"', INDEX)
    assert order == ["input", "preview", "options"], order


def test_mobile_menu_links_exist_without_javascript():
    """nav.js only toggles state; the links must be in the served HTML."""
    assert 'id="site-nav"' in (ROOT / "app" / "templates" / "base.html").read_text()
    assert 'id="nav-toggle"' in (ROOT / "app" / "templates" / "base.html").read_text()
