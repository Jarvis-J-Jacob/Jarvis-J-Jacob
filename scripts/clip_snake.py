#!/usr/bin/env python3
"""
clip_snake.py - keep the snake inside the contribution grid.

Platane/snk lets the snake leave the grid while it plans its route (three times
per loop for a sparse year), so blocks float outside the grid lines. This clips
the four snake blocks to the grid area, so the snake slides out of view at the
edge instead of wandering outside it.

Usage:
    python scripts/clip_snake.py dist/snake-dark.svg dist/snake-light.svg
"""

import re
import sys
import xml.etree.ElementTree as ET

CELL = 16  # grid pitch in the snk output: a 12px cell plus a 4px gap
CLIP_ID = "grid-clip"


def clip(svg: str) -> str:
    if CLIP_ID in svg:
        return svg  # already clipped, so the script is safe to re-run

    # grid size from the number of distinct cell columns and rows
    xs = {m for m in re.findall(r'<rect class="c[^"]*" x="(-?[\d.]+)"', svg)}
    ys = {m for m in re.findall(r'<rect class="c[^"]*" x="-?[\d.]+" y="(-?[\d.]+)"', svg)}
    if not xs or not ys:
        raise ValueError("no grid cells found - is this a snk svg?")
    width, height = len(xs) * CELL, len(ys) * CELL

    snake = re.findall(r'<rect class="s s\d+"[^>]*/>', svg)
    if not snake:
        raise ValueError("no snake blocks found - is this a snk svg?")

    clip_def = (f'<clipPath id="{CLIP_ID}"><rect x="0" y="0" '
                f'width="{width}" height="{height}"/></clipPath>')
    group = f'<g clip-path="url(#{CLIP_ID})">' + "".join(snake) + "</g>"

    out = svg.replace("</style>", "</style>" + clip_def, 1)
    for block in snake:
        out = out.replace(block, "", 1)
    out = out.replace("</svg>", group + "</svg>")
    ET.fromstring(out)  # fail loudly if the result is not valid XML
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            original = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(clip(original))
        print(f"clipped {path}")


if __name__ == "__main__":
    main()
