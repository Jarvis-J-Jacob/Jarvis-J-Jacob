#!/usr/bin/env python3
"""
isocal.py — draws an isometric contribution calendar as an SVG, straight from
GitHub's GraphQL contribution data. Same idea as the lowlighter/metrics
isocalendar plugin, but self-hosted so it can't 503 on us.

Usage:
    python scripts/isocal.py --user YOUR_USERNAME -o assets/isocal

Writes <out>-dark.svg and <out>-light.svg.

Needs a token in GITHUB_TOKEN or METRICS_TOKEN — the contribution calendar is
a GraphQL-only field, so unauthenticated calls can't reach it. The GitHub
Actions default GITHUB_TOKEN is enough; no personal token required.
"""

import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

ACCENT = "#a855f7"
ACCENT_LIGHT = "#7e22ce"

# five-step purple ramp, faint -> vivid, one pair per theme
RAMP_DARK = ["#241b33", "#452c6b", "#6d3fb0", "#9a63e8", "#c9a4ff"]
RAMP_LIGHT = ["#efeafb", "#cdb6ef", "#a67fe0", "#7f4bcf", "#5a2ca6"]

TILE = 12          # half-width of a tile diamond in the isometric projection
BASE_RISE = 3      # how tall a zero-contribution day stands
MAX_RISE = 34      # extra height at the busiest day

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_args():
    p = argparse.ArgumentParser(description="Isometric contribution calendar SVG.")
    p.add_argument("--user", required=True, help="GitHub username")
    p.add_argument("-o", "--out", required=True, help="Output path prefix, e.g. assets/isocal")
    return p.parse_args()


def get_token():
    return os.environ.get("METRICS_TOKEN") or os.environ.get("GITHUB_TOKEN")


def fetch_calendar(username, token):
    """Returns (total, weeks) where weeks is a list of lists of day dicts."""
    query = """
    { user(login: "%s") { contributionsCollection { contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
    } } } }
    """ % username
    body = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body, method="POST",
        headers={
            "User-Agent": "profile-readme-isocal",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read())
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return cal["totalContributions"], cal["weeks"]


def streaks(days):
    """current streak (counting back from today) and longest streak, in days."""
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    current = 0
    for i, c in enumerate(reversed(counts)):
        if c > 0:
            current += 1
        elif i == 0:
            continue  # today is allowed to be empty without breaking the streak
        else:
            break
    return current, longest


def level_for(count, ceiling):
    if count <= 0:
        return 0
    if ceiling <= 1:
        return 4
    frac = count / ceiling
    return max(1, min(4, 1 + int(frac * 3.999)))


def shade(hex_color, factor):
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r, g, b = (max(0, min(255, int(v * factor))) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def draw(username, total, weeks, ramp, text_color, accent):
    days = [d for w in weeks for d in w["contributionDays"]]
    nonzero = sorted(d["contributionCount"] for d in days if d["contributionCount"] > 0)
    # 90th percentile as the ceiling so one monster day doesn't flatten the rest
    ceiling = nonzero[int(len(nonzero) * 0.9)] if nonzero else 1
    cur_streak, best_streak = streaks(days)
    busiest = max((d["contributionCount"] for d in days), default=0)

    n_weeks = len(weeks)
    ox = 40 + 6 * TILE          # shift right to make room for the r=6 overhang
    oy = 116

    cells = []  # (depth, svg)
    month_labels = []
    last_month = None

    for c, week in enumerate(weeks):
        for d in week["contributionDays"]:
            r = d["weekday"]
            count = d["contributionCount"]
            lvl = level_for(count, ceiling)
            h = BASE_RISE + (0 if not count else (min(count, ceiling) / ceiling) ** 0.6 * MAX_RISE)

            gx = ox + (c - r) * TILE
            gy = oy + (c + r) * TILE * 0.5

            top = ramp[lvl]
            left = shade(top, 0.62)
            right = shade(top, 0.82)

            # ground diamond points, then the same raised by h
            def dia(yoff):
                return (f"{gx:.1f},{gy - yoff:.1f} "
                        f"{gx + TILE:.1f},{gy + TILE * 0.5 - yoff:.1f} "
                        f"{gx:.1f},{gy + TILE - yoff:.1f} "
                        f"{gx - TILE:.1f},{gy + TILE * 0.5 - yoff:.1f}")

            svg = (
                f'<polygon points="{gx - TILE:.1f},{gy + TILE * 0.5 - h:.1f} '
                f'{gx:.1f},{gy + TILE - h:.1f} {gx:.1f},{gy + TILE:.1f} '
                f'{gx - TILE:.1f},{gy + TILE * 0.5:.1f}" fill="{left}"/>'
                f'<polygon points="{gx:.1f},{gy + TILE - h:.1f} '
                f'{gx + TILE:.1f},{gy + TILE * 0.5 - h:.1f} {gx + TILE:.1f},{gy + TILE * 0.5:.1f} '
                f'{gx:.1f},{gy + TILE:.1f}" fill="{right}"/>'
                f'<polygon points="{dia(h)}" fill="{top}"/>'
            )
            cells.append((c + r, gx, svg))

            # month label when a new month first appears (near the top row)
            iso_day = date.fromisoformat(d["date"])
            if r == 0:
                if last_month != iso_day.month and iso_day.day <= 7:
                    lx = ox + (c - 0) * TILE
                    ly = oy + c * TILE * 0.5 - 20
                    month_labels.append(
                        f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{text_color}" fill-opacity="0.65" '
                        f'font-size="10" text-anchor="middle">{MONTHS[iso_day.month - 1]}</text>')
                    last_month = iso_day.month

    cells.sort(key=lambda t: (t[0], t[1]))
    body = "\n".join(s for _, _, s in cells)

    width = ox + (n_weeks - 1) * TILE + TILE + 40
    height = oy + (n_weeks - 1 + 6) * TILE * 0.5 + TILE + 46

    # legend
    lg_x = width - 200
    lg_y = height - 26
    legend = [f'<text x="{lg_x - 8:.0f}" y="{lg_y + 4:.0f}" fill="{text_color}" fill-opacity="0.6" '
              f'font-size="10" text-anchor="end">less</text>']
    for i, col in enumerate(ramp):
        legend.append(f'<rect x="{lg_x + i * 20:.0f}" y="{lg_y - 6:.0f}" width="13" height="13" rx="2" '
                      f'fill="{col}"/>')
    legend.append(f'<text x="{lg_x + len(ramp) * 20 + 2:.0f}" y="{lg_y + 4:.0f}" fill="{text_color}" '
                  f'fill-opacity="0.6" font-size="10">more</text>')

    stat = (f'<text x="40" y="34" fill="{text_color}" font-size="15" font-weight="600">'
            f'{username} — contributions, last year</text>'
            f'<text x="40" y="62" fill="{accent}" font-size="24" font-weight="700">{total:,}</text>'
            f'<text x="40" y="80" fill="{text_color}" fill-opacity="0.65" font-size="10">'
            f'commits, PRs, issues &amp; reviews</text>'
            f'<text x="{width - 40:.0f}" y="34" fill="{text_color}" fill-opacity="0.75" font-size="11" '
            f'text-anchor="end">current streak {cur_streak}d · longest {best_streak}d · '
            f'busiest day {busiest}</text>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}" font-family="JetBrains Mono, monospace">\n'
        f'{stat}\n{body}\n{"".join(month_labels)}\n{"".join(legend)}\n</svg>'
    )


def placeholder(text_color, accent):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 240" width="760" height="240" '
            f'font-family="JetBrains Mono, monospace">'
            f'<rect x="1" y="1" width="758" height="238" rx="12" fill="none" stroke="{accent}" '
            f'stroke-opacity="0.35"/>'
            f'<text x="380" y="110" fill="{text_color}" font-size="14" font-weight="600" '
            f'text-anchor="middle">isometric contribution calendar</text>'
            f'<text x="380" y="138" fill="{text_color}" fill-opacity="0.7" font-size="12" '
            f'text-anchor="middle">fills in once the charts workflow runs with a token</text></svg>')


def main():
    args = parse_args()
    token = get_token()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    dark_path = Path(f"{out}-dark.svg")
    light_path = Path(f"{out}-light.svg")

    if not token:
        dark_path.write_text(placeholder("#e6edf3", ACCENT), encoding="utf-8")
        light_path.write_text(placeholder("#1f2328", ACCENT_LIGHT), encoding="utf-8")
        print("no token — wrote placeholder isocal SVGs")
        return

    try:
        total, weeks = fetch_calendar(args.user, token)
    except Exception as e:
        sys.exit(f"error fetching contribution calendar: {e}")

    dark_path.write_text(draw(args.user, total, weeks, RAMP_DARK, "#e6edf3", ACCENT), encoding="utf-8")
    light_path.write_text(draw(args.user, total, weeks, RAMP_LIGHT, "#1f2328", ACCENT_LIGHT), encoding="utf-8")
    print(f"wrote {dark_path} and {light_path}")


if __name__ == "__main__":
    main()
