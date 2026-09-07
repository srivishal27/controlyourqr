#!/usr/bin/env python3
"""Generate the site icons from one source pattern.

Emits:
  app/static/img/favicon.svg   — themed favicon (indigo tile, white glyph)
  app/static/img/icon-180.png  — apple-touch-icon
  app/static/img/brand-mark.svg — the header lockup mark (currentColor)

Pure standard library: PNG is written with zlib, no image dependencies.
Run from the repository root:  python3 tools/make_icons.py
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

# A stylised QR glyph: three finder rings plus a scatter of data modules.
PATTERN = [
    "XXX..X..XXX",
    "X.X.X...X.X",
    "XXX..X..XXX",
    "...........",
    "X.X.XX.X.X.",
    "..XX..XX...",
    "X.X.XX...X.",
    "...........",
    "XXX..X.XX.X",
    "X.X.XX.X.XX",
    "XXX....XX.X",
]

ACCENT = (79, 70, 229)   # #4f46e5
WHITE = (255, 255, 255)

GRID = len(PATTERN)
ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "app" / "static" / "img"


def validate() -> None:
    for index, row in enumerate(PATTERN):
        if len(row) != GRID:
            raise SystemExit(f"row {index} is {len(row)} cells, expected {GRID}")


def modules() -> list[tuple[int, int]]:
    return [
        (x, y)
        for y, row in enumerate(PATTERN)
        for x, cell in enumerate(row)
        if cell == "X"
    ]


# --------------------------------------------------------------------------- #
# SVG
# --------------------------------------------------------------------------- #

def write_favicon_svg() -> None:
    """Indigo rounded tile with a white glyph — legible on any browser chrome."""
    pad, unit = 6, 4  # 6 + 11*4 + 6 = 56 viewBox units
    box = pad * 2 + GRID * unit

    rects = "\n".join(
        f'    <rect x="{pad + x * unit}" y="{pad + y * unit}" '
        f'width="{unit}" height="{unit}" rx=".6"/>'
        for x, y in modules()
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {box} {box}" \
width="{box}" height="{box}" role="img" aria-label="ControlYourQR">
  <rect width="{box}" height="{box}" rx="12" fill="#4f46e5"/>
  <g fill="#ffffff">
{rects}
  </g>
</svg>
"""
    (IMG_DIR / "favicon.svg").write_text(svg, encoding="utf-8")


def write_brand_mark_svg() -> None:
    """Transparent glyph in currentColor, for inline use in the header."""
    unit = 3
    box = GRID * unit

    rects = "\n".join(
        f'  <rect x="{x * unit}" y="{y * unit}" width="{unit}" height="{unit}" rx=".5"/>'
        for x, y in modules()
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {box} {box}" \
fill="currentColor" aria-hidden="true" focusable="false">
{rects}
</svg>
"""
    (IMG_DIR / "brand-mark.svg").write_text(svg, encoding="utf-8")


# --------------------------------------------------------------------------- #
# PNG
# --------------------------------------------------------------------------- #

def _chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def write_png(path: Path, size: int) -> None:
    """Render the glyph as an opaque RGB PNG of ``size``x``size`` pixels."""
    pad_ratio = 0.14
    pad = int(size * pad_ratio)
    unit = (size - pad * 2) // GRID
    # Re-centre after integer rounding of the module size.
    offset = (size - unit * GRID) // 2

    cells = set(modules())
    rows = bytearray()

    for py in range(size):
        rows.append(0)  # PNG filter type 0 (None)
        gy = (py - offset) // unit if unit else -1
        in_y = 0 <= (py - offset) < unit * GRID
        for px in range(size):
            gx = (px - offset) // unit if unit else -1
            in_x = 0 <= (px - offset) < unit * GRID
            colour = WHITE if (in_x and in_y and (gx, gy) in cells) else ACCENT
            rows.extend(colour)

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit truecolour
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def main() -> None:
    validate()
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    write_favicon_svg()
    write_brand_mark_svg()
    write_png(IMG_DIR / "icon-180.png", 180)
    print(f"wrote icons to {IMG_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
