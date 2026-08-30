#!/usr/bin/env python3
"""
dotify.py — turn a photo into a dot-matrix SVG portrait.

Usage:
    python scripts/dotify.py me.png -o assets/portrait --cols 100 --equalize --detail 0.5 --color

Writes:
    <out>.svg              (if --color is used — one file, works on both GitHub themes)
    <out>-dark.svg / <out>-light.svg   (if --color is NOT used — green monochrome pair)
"""

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageOps, ImageFilter


def parse_args():
    p = argparse.ArgumentParser(description="Turn a photo into a dot-matrix SVG portrait.")
    p.add_argument("image", help="Path to the source photo")
    p.add_argument("-o", "--out", required=True, help="Output path prefix, e.g. assets/portrait")
    p.add_argument("--cols", type=int, default=88, help="Number of dot columns (default 88)")
    p.add_argument("--equalize", action="store_true", help="Stretch tones against the subject's own histogram")
    p.add_argument("--detail", type=float, default=0.0, help="Local-contrast boost, 0-1ish, sweet spot ~0.5")
    p.add_argument("--color", action="store_true", help="Keep original color instead of green monochrome")
    p.add_argument("--invert", action="store_true", help="Invert brightness (for dark-on-light subjects)")
    p.add_argument("--circle", action="store_true", help="Mask output to a feathered circle")
    p.add_argument("--square", action="store_true", help="Crop to 1:1 before sampling")
    p.add_argument("--focus", type=str, default="0.5,0.5", help="Crop focus point as x,y fractions, e.g. 0.55,0.45")
    p.add_argument("--animate", action="store_true", help="Add a CSS shimmer sweep across columns")
    p.add_argument("--reveal", action="store_true", help="Animate rows appearing on load")
    p.add_argument("--reveal-time", type=float, default=2.5, help="Total reveal sweep duration in seconds")
    p.add_argument("--reveal-fade", type=float, default=0.45, help="Per-row fade-in duration in seconds")
    p.add_argument("--reveal-dir", choices=["down", "up"], default="down", help="Reveal sweep direction")
    p.add_argument("--mode", choices=["dots", "binary", "ascii", "braille"], default="dots",
                    help="Rendering mode. ascii/braille write a .txt instead of an SVG.")
    return p.parse_args()


def load_and_prep(path, square, focus):
    img = Image.open(path)
    # Alpha channel becomes a subject mask, if present.
    mask = None
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        mask = img.split()[-1]
    rgb = img.convert("RGB")

    if square:
        w, h = rgb.size
        side = min(w, h)
        fx, fy = [float(v) for v in focus.split(",")]
        cx, cy = w * fx, h * fy
        left = min(max(cx - side / 2, 0), w - side)
        top = min(max(cy - side / 2, 0), h - side)
        box = (int(left), int(top), int(left) + side, int(top) + side)
        rgb = rgb.crop(box)
        if mask is not None:
            mask = mask.crop(box)

    return rgb, mask


def equalize_against_mask(gray, mask):
    """Stretch the histogram using only the masked (subject) pixels."""
    if mask is not None:
        # Build a histogram limited to masked pixels by zeroing out background
        # contribution — approximate but avoids external deps.
        px = gray.load()
        mpx = mask.load()
        vals = []
        w, h = gray.size
        step = max(1, (w * h) // 20000)  # sample for speed on huge images
        idx = 0
        for y in range(h):
            for x in range(w):
                idx += 1
                if idx % step:
                    continue
                if mpx[x, y] > 10:
                    vals.append(px[x, y])
        if vals:
            lo, hi = min(vals), max(vals)
            if hi > lo:
                lut = [max(0, min(255, int((v - lo) * 255 / (hi - lo)))) for v in range(256)]
                return gray.point(lut)
    return ImageOps.equalize(gray)


def sample_grid(rgb, mask, cols, equalize, detail, invert):
    w, h = rgb.size
    aspect = h / w
    # Terminal/dot cells aren't square in most renderings; keep it simple, square dots.
    rows = max(1, round(cols * aspect))

    gray = rgb.convert("L")
    if equalize:
        gray = equalize_against_mask(gray, mask)
    if detail > 0:
        blurred = gray.filter(ImageFilter.GaussianBlur(radius=max(1, gray.size[0] // 60)))
        g_px, b_px = gray.load(), blurred.load()
        out = Image.new("L", gray.size)
        o_px = out.load()
        gw, gh = gray.size
        for y in range(gh):
            for x in range(gw):
                hi = g_px[x, y] + int((g_px[x, y] - b_px[x, y]) * detail * 2)
                o_px[x, y] = max(0, min(255, hi))
        gray = out
    if invert:
        gray = ImageOps.invert(gray)

    small_gray = gray.resize((cols, rows), Image.LANCZOS)
    small_rgb = rgb.resize((cols, rows), Image.LANCZOS)
    small_mask = mask.resize((cols, rows), Image.LANCZOS) if mask is not None else None

    cells = []
    gpx = small_gray.load()
    rpx = small_rgb.load()
    mpx = small_mask.load() if small_mask is not None else None
    for y in range(rows):
        row = []
        for x in range(cols):
            brightness = gpx[x, y] / 255.0
            visible = True
            if mpx is not None and mpx[x, y] < 10:
                visible = False
            r, g, b = rpx[x, y]
            row.append((brightness, (r, g, b), visible))
        cells.append(row)
    return cells, cols, rows


def render_svg(cells, cols, rows, color, monochrome_hex, cell_size=8, max_radius_frac=0.46, animate=False):
    width = cols * cell_size
    height = rows * cell_size
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
    ]
    if animate:
        parts.append(f"""
<defs>
  <linearGradient id="shimmer" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="{monochrome_hex}" stop-opacity="0.35"/>
    <stop offset="50%" stop-color="{monochrome_hex}" stop-opacity="1"/>
    <stop offset="100%" stop-color="{monochrome_hex}" stop-opacity="0.35"/>
  </linearGradient>
  <mask id="shimmerMask">
    <rect x="-{width}" y="0" width="{width*3}" height="{height}" fill="url(#shimmer)">
      <animate attributeName="x" values="-{width};{width}" dur="3.5s" repeatCount="indefinite"/>
    </rect>
  </mask>
</defs>
""")
    dot_group_open = '<g mask="url(#shimmerMask)">' if animate else "<g>"
    parts.append(dot_group_open)

    for y, row in enumerate(cells):
        for x, (brightness, rgb, visible) in enumerate(row):
            if not visible:
                continue
            radius = brightness * cell_size * max_radius_frac
            if radius < 0.35:
                continue
            cx = x * cell_size + cell_size / 2
            cy = y * cell_size + cell_size / 2
            fill = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})" if color else monochrome_hex
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.2f}" fill="{fill}"/>')
    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def render_reveal_svg(cells, cols, rows, color, monochrome_hex, cell_size, max_radius_frac,
                       reveal_time, reveal_fade, reveal_dir):
    width = cols * cell_size
    height = rows * cell_size
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
    ]
    row_order = range(rows) if reveal_dir == "down" else range(rows - 1, -1, -1)
    delay_step = reveal_time / max(1, rows)

    for i, y in enumerate(row_order):
        row = cells[y]
        delay = i * delay_step
        parts.append(f'<g opacity="0">'
                     f'<animate attributeName="opacity" from="0" to="1" '
                     f'begin="{delay:.3f}s" dur="{reveal_fade}s" fill="freeze"/>')
        for x, (brightness, rgb, visible) in enumerate(row):
            if not visible:
                continue
            radius = brightness * cell_size * max_radius_frac
            if radius < 0.35:
                continue
            cx = x * cell_size + cell_size / 2
            cy = y * cell_size + cell_size / 2
            fill = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})" if color else monochrome_hex
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.2f}" fill="{fill}"/>')
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def render_text_mode(cells, cols, rows, mode):
    if mode == "binary":
        chars = "01"
    elif mode == "ascii":
        chars = " .:-=+*#%@"
    else:  # braille — coarse 1-dot-per-cell approximation
        chars = " ⠂⠆⠇⠋⠛⠟⠿⡿⣿"
    lines = []
    n = len(chars) - 1
    for row in cells:
        line = []
        for brightness, _, visible in row:
            if not visible:
                line.append(" ")
                continue
            idx = min(n, int(brightness * n))
            line.append(chars[idx])
        lines.append("".join(line))
    return "\n".join(lines)


def apply_circle_mask(svg_text, width, height):
    r = min(width, height) * 0.5
    cx, cy = width / 2, height / 2
    clip = (f'<defs><clipPath id="circleClip"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>'
            f'<radialGradient id="feather" cx="50%" cy="50%" r="50%">'
            f'<stop offset="85%" stop-opacity="1"/><stop offset="100%" stop-opacity="0"/>'
            f'</radialGradient></defs>')
    svg_text = svg_text.replace("<defs>", clip + "<defs>", 1) if "<defs>" in svg_text else svg_text.replace(
        "<svg", "PLACEHOLDER", 1)
    if "PLACEHOLDER" in svg_text:
        svg_text = svg_text.replace("PLACEHOLDER", clip + "<svg", 1)
    svg_text = svg_text.replace("<g>", '<g clip-path="url(#circleClip)">', 1)
    return svg_text


def main():
    args = parse_args()
    src = Path(args.image)
    if not src.exists():
        sys.exit(f"error: {src} not found")

    rgb, mask = load_and_prep(src, args.square, args.focus)
    cells, cols, rows = sample_grid(rgb, mask, args.cols, args.equalize, args.detail, args.invert)

    out_prefix = Path(args.out)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    if args.mode in ("ascii", "braille"):
        text = render_text_mode(cells, cols, rows, args.mode)
        out_path = out_prefix.with_suffix(".txt")
        out_path.write_text(text, encoding="utf-8")
        print(f"wrote {out_path}")
        return

    green = "#a855f7" if False else "#a855f7"  # placeholder, overwritten by CLI accent below
    monochrome_hex = "#a855f7"

    if args.mode == "binary":
        # Render literal glyph-like large dots using two sizes only (handled visually as dots mode variant)
        pass

    if args.reveal:
        cell_size = 8
        svg = render_reveal_svg(cells, cols, rows, args.color, monochrome_hex, cell_size, 0.46,
                                 args.reveal_time, args.reveal_fade, args.reveal_dir)
    else:
        svg = render_svg(cells, cols, rows, args.color, monochrome_hex, animate=args.animate)

    width, height = cols * 8, rows * 8

    if args.circle:
        svg = apply_circle_mask(svg, width, height)

    if args.color:
        out_path = out_prefix.with_suffix(".svg")
        out_path.write_text(svg, encoding="utf-8")
        print(f"wrote {out_path}")
    else:
        dark_path = Path(str(out_prefix) + "-dark.svg")
        light_path = Path(str(out_prefix) + "-light.svg")
        dark_path.write_text(svg, encoding="utf-8")
        # Light variant: same dots, darker fill so they read on a white card.
        light_svg = svg.replace(monochrome_hex, "#6b21a8")
        light_path.write_text(light_svg, encoding="utf-8")
        print(f"wrote {dark_path} and {light_path}")


if __name__ == "__main__":
    main()
