#!/usr/bin/env python3
"""
radar.py — draws a radar/spider chart SVG, either from a JSON file of
hand-rated values, or live from a GitHub user's public repo language bytes.

Usage:
    python scripts/radar.py --data assets/skills.json -o assets/radar
    python scripts/radar.py --github YOUR_USERNAME -o assets/radar-langs \
        --limit 7 --values --curve 0.4 --exclude "shell,makefile,dockerfile"

Writes <out>-dark.svg and <out>-light.svg.
"""

import argparse
import json
import math
import os
import sys
import urllib.request
from pathlib import Path

ACCENT = "#a855f7"       # purple — change here to re-theme everything
ACCENT_LIGHT = "#7e22ce"


def parse_args():
    p = argparse.ArgumentParser(description="Draw a radar chart as SVG.")
    p.add_argument("--data", help="Path to a JSON file: {title, axes: [{label, value}]}")
    p.add_argument("--github", help="GitHub username to pull live language bytes for")
    p.add_argument("-o", "--out", required=True, help="Output path prefix")
    p.add_argument("--limit", type=int, default=7, help="Max axes for --github mode")
    p.add_argument("--curve", type=float, default=1.0,
                    help="Exponent applied to normalized values (1=linear, 0.4=compressed)")
    p.add_argument("--values", action="store_true", help="Print the numeric value next to each axis")
    p.add_argument("--exclude", default="", help="Comma-separated language names to drop (github mode)")
    p.add_argument("--title", default=None, help="Override chart title")
    return p.parse_args()


def fetch_language_bytes(username, exclude):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("METRICS_TOKEN")
    headers = {"User-Agent": "profile-readme-radar"}
    if token:
        headers["Authorization"] = f"token {token}"

    repos = []
    page = 1
    while True:
        req = urllib.request.Request(
            f"https://api.github.com/users/{username}/repos?per_page=100&page={page}&type=owner",
            headers=headers,
        )
        with urllib.request.urlopen(req) as resp:
            batch = json.loads(resp.read())
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    totals = {}
    excl = {e.strip().lower() for e in exclude.split(",") if e.strip()}
    for repo in repos:
        if repo.get("fork"):
            continue
        lang_url = repo["languages_url"]
        req = urllib.request.Request(lang_url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                langs = json.loads(resp.read())
        except Exception:
            continue
        for lang, count in langs.items():
            if lang.lower() in excl:
                continue
            totals[lang] = totals.get(lang, 0) + count

    return totals


def load_axes_from_json(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    title = data.get("title", "Skill Radar")
    axes = [(a["label"], float(a["value"])) for a in data["axes"]]
    return title, axes, 100.0  # self-rated is already 0-100


def load_axes_from_github(username, limit, exclude):
    totals = fetch_language_bytes(username, exclude)
    if not totals:
        sys.exit("no language data returned — check the username or your rate limit")
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    max_val = ranked[0][1]
    axes = [(name, count) for name, count in ranked]
    return "Language Radar", axes, max_val


def draw_radar(title, axes, max_val, curve, show_values, accent, size=420):
    n = len(axes)
    cx, cy = size / 2, size / 2 + 10
    r_max = size * 0.34
    angle_step = 2 * math.pi / n
    start_angle = -math.pi / 2

    def point_for(i, frac):
        ang = start_angle + i * angle_step
        return cx + r_max * frac * math.cos(ang), cy + r_max * frac * math.sin(ang)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size + 20}" '
             f'width="{size}" height="{size + 20}" font-family="JetBrains Mono, monospace">']

    # background rings
    for frac in (0.25, 0.5, 0.75, 1.0):
        ring_pts = [point_for(i, frac) for i in range(n)]
        path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(ring_pts))
        parts.append(f'<path d="{path} Z" fill="none" stroke="{accent}" stroke-opacity="0.15"/>')

    # spokes
    for i in range(n):
        x, y = point_for(i, 1.0)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" '
                      f'stroke="{accent}" stroke-opacity="0.15"/>')

    # data polygon
    data_pts = []
    for i, (label, value) in enumerate(axes):
        norm = max(0.0, min(1.0, value / max_val)) if max_val else 0
        norm = norm ** curve
        data_pts.append(point_for(i, norm))
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(data_pts))
    parts.append(f'<path d="{path} Z" fill="{accent}" fill-opacity="0.25" stroke="{accent}" stroke-width="2"/>')
    for x, y in data_pts:
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{accent}"/>')

    # labels
    for i, (label, value) in enumerate(axes):
        lx, ly = point_for(i, 1.22)
        anchor = "middle"
        ang_deg = math.degrees(start_angle + i * angle_step) % 360
        if 45 < ang_deg < 135:
            anchor = "middle"
        elif ang_deg <= 45 or ang_deg >= 315:
            anchor = "start"
        elif 135 <= ang_deg <= 225:
            anchor = "end"
        text = label
        if show_values:
            display_val = int(value) if value == int(value) else round(value, 1)
            text = f"{label} ({display_val})"
        parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="currentColor" font-size="12" '
                      f'text-anchor="{anchor}" dominant-baseline="middle">{text}</text>')

    parts.append(f'<text x="{cx}" y="16" fill="currentColor" font-size="14" font-weight="600" '
                 f'text-anchor="middle">{title}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    args = parse_args()

    if args.data:
        title, axes, max_val = load_axes_from_json(args.data)
    elif args.github:
        title, axes, max_val = load_axes_from_github(args.github, args.limit, args.exclude)
    else:
        sys.exit("provide either --data or --github")

    if args.title:
        title = args.title

    if not axes:
        sys.exit("no axes to draw")

    dark_svg = draw_radar(title, axes, max_val, args.curve, args.values, ACCENT)
    light_svg = draw_radar(title, axes, max_val, args.curve, args.values, ACCENT_LIGHT)

    out_prefix = Path(args.out)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    dark_path = Path(str(out_prefix) + "-dark.svg")
    light_path = Path(str(out_prefix) + "-light.svg")
    # currentColor needs a concrete color per theme since SVGs are standalone files
    dark_final = f'<g color="#e6edf3">{dark_svg}</g>' if False else dark_svg.replace(
        'fill="currentColor"', 'fill="#e6edf3"')
    light_final = light_svg.replace('fill="currentColor"', 'fill="#1f2328"')
    dark_path.write_text(dark_final, encoding="utf-8")
    light_path.write_text(light_final, encoding="utf-8")
    print(f"wrote {dark_path} and {light_path}")


if __name__ == "__main__":
    main()
