"""Generate placeholder .ico files for BudBridge using Pillow.

Run from the pc/ directory:
    python assets/generate_icons.py

Produces:
    assets/budbridge.ico           (disconnected — grey)
    assets/budbridge_connected.ico (connected — green)
    assets/budbridge_busy.ico      (busy — yellow)
    assets/budbridge_error.ico     (error — red)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("Pillow is required. Run: pip install Pillow")

# Output directory is the same directory as this script
ASSETS_DIR = Path(__file__).parent

ICONS = {
    "budbridge.ico": (156, 163, 175, 255),           # grey  — disconnected
    "budbridge_connected.ico": (34, 197, 94, 255),   # green — connected
    "budbridge_busy.ico": (234, 179, 8, 255),         # yellow — busy
    "budbridge_error.ico": (239, 68, 68, 255),        # red   — error
}

SIZES = [16, 32, 48, 64, 128, 256]


def draw_icon(colour: tuple, size: int = 256) -> Image.Image:
    """Draw a coloured circle with a white headphone silhouette."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    margin = max(1, size // 32)
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=colour,
    )

    # Headphone shape (white)
    c = size // 2
    r_outer = int(size * 0.28)
    lw = max(2, size // 20)
    white = (255, 255, 255, 220)

    # Headband arc (top)
    arc_x0 = c - r_outer
    arc_y0 = c - r_outer
    arc_x1 = c + r_outer
    arc_y1 = c + r_outer
    draw.arc(
        [arc_x0, arc_y0, arc_x1, arc_y1],
        start=210,
        end=330,
        fill=white,
        width=lw,
    )

    # Left ear cup
    ear_r = max(3, lw + 2)
    lx = c - r_outer
    ly = c + int(size * 0.05)
    draw.ellipse(
        [lx - ear_r, ly - ear_r, lx + ear_r, ly + ear_r],
        fill=white,
    )

    # Right ear cup
    rx = c + r_outer
    ry = ly
    draw.ellipse(
        [rx - ear_r, ry - ear_r, rx + ear_r, ry + ear_r],
        fill=white,
    )

    # Vertical stems from arc ends to ear cups
    # Left stem
    stem_top_lx = c - int(r_outer * 0.87)
    stem_top_ly = c - int(r_outer * 0.5)
    draw.line([(stem_top_lx, stem_top_ly), (lx, ly)], fill=white, width=lw)

    # Right stem
    stem_top_rx = c + int(r_outer * 0.87)
    stem_top_ry = stem_top_ly
    draw.line([(stem_top_rx, stem_top_ry), (rx, ry)], fill=white, width=lw)

    return img


def make_ico(filename: str, colour: tuple) -> None:
    """Build a multi-resolution .ico file."""
    frames = []
    for sz in SIZES:
        frame = draw_icon(colour, sz)
        frames.append(frame)

    out_path = ASSETS_DIR / filename
    # Save as ICO with all sizes embedded
    frames[0].save(
        out_path,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=frames[1:],
    )
    print(f"  Written: {out_path}")


def main() -> None:
    print(f"Generating icons in: {ASSETS_DIR.resolve()}")
    for filename, colour in ICONS.items():
        make_ico(filename, colour)
    print("Done.")


if __name__ == "__main__":
    main()
