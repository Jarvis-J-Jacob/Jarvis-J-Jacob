#!/usr/bin/env python3
"""
cards.py — writes the stat card and project cards as real SVG files into your
own repo, so nothing depends on a third-party server being up.

Usage:
    python scripts/cards.py --user YOUR_USERNAME --out assets

Reads assets/projects.json for which repos get a project card.
Uses GITHUB_TOKEN / METRICS_TOKEN env var if present (set automatically by
the GitHub Actions workflow). Falls back to unauthenticated calls locally,
which is fine but rate-limited and gives 3 tiles instead of 6.
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ACCENT = "#a855f7"
ACCENT_LIGHT = "#7e22ce"

GRAPHQL_URL = "https://api.github.com/graphql"
REST_BASE = "https://api.github.com"


def parse_args():
    p = argparse.ArgumentParser(description="Generate stat card + project cards as SVG.")
    p.add_argument("--user", required=True, help="GitHub username")
    p.add_argument("--out", required=True, help="Output directory, e.g. assets")
    p.add_argument("--projects", default=None, help="Path to projects.json (default: <out>/projects.json)")
    return p.parse_args()


def get_token():
    return os.environ.get("METRICS_TOKEN") or os.environ.get("GITHUB_TOKEN")


def rest_get(path, token):
    req = urllib.request.Request(f"{REST_BASE}{path}", headers=_headers(token))
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _headers(token):
    h = {"User-Agent": "profile-readme-cards", "Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def graphql(query, token):
    if not token:
        return None
    body = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(GRAPHQL_URL, data=body, headers=_headers(token), method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def fetch_stats(username, token):
    """Returns dict with stars, repos, followers, and (if token) contributions/streak."""
    user = rest_get(f"/users/{username}", token)
    repos = []
    page = 1
    while True:
        batch = rest_get(f"/users/{username}/repos?per_page=100&page={page}&type=owner", token)
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)

    stats = {
        "repos": user.get("public_repos", len(repos)),
        "followers": user.get("followers", 0),
        "stars": total_stars,
        "forks": total_forks,
        "contributions": None,
        "streak": None,
    }

    gql = graphql(f"""
    {{
      user(login: "{username}") {{
        contributionsCollection {{
          contributionCalendar {{
            totalContributions
            weeks {{
              contributionDays {{ date contributionCount }}
            }}
          }}
        }}
      }}
    }}
    """, token)

    if gql and gql.get("data", {}).get("user"):
        cal = gql["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        stats["contributions"] = cal["totalContributions"]
        # current streak: count backward from most recent day with contributions
        days = [d for week in cal["weeks"] for d in week["contributionDays"]]
        streak = 0
        for d in reversed(days):
            if d["contributionCount"] > 0:
                streak += 1
            else:
                if streak > 0:
                    break
        stats["streak"] = streak

    return stats, {r["name"]: r for r in repos}


def stat_card_svg(username, stats, accent, text_color, six_tiles):
    tiles = [
        ("Public repos", stats["repos"]),
        ("Followers", stats["followers"]),
        ("Total stars", stats["stars"]),
        ("Total forks", stats["forks"]),
    ]
    if six_tiles and stats["contributions"] is not None:
        tiles.append(("Contributions", stats["contributions"]))
        tiles.append(("Current streak", f'{stats["streak"]}d'))

    cols = 3
    rows = -(-len(tiles) // cols)
    width = 640
    tile_w = width / cols
    tile_h = 80
    height = rows * tile_h + 50

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
             f'width="{width}" height="{height}" font-family="JetBrains Mono, monospace">']
    parts.append(f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="12" '
                 f'fill="none" stroke="{accent}" stroke-opacity="0.35"/>')
    parts.append(f'<text x="20" y="30" font-size="16" font-weight="600" fill="{text_color}">'
                 f'{username} — stats</text>')

    for i, (label, value) in enumerate(tiles):
        col, row = i % cols, i // cols
        x = col * tile_w
        y = 45 + row * tile_h
        parts.append(f'<text x="{x + tile_w/2:.1f}" y="{y + 32:.1f}" font-size="22" font-weight="700" '
                     f'fill="{accent}" text-anchor="middle">{value}</text>')
        parts.append(f'<text x="{x + tile_w/2:.1f}" y="{y + 52:.1f}" font-size="11" '
                     f'fill="{text_color}" fill-opacity="0.75" text-anchor="middle">{label}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def project_card_svg(name, description, language, stars, forks, accent, text_color):
    width, height = 420, 150
    desc = description or "No description set yet — add one on GitHub."
    # naive word wrap
    words = desc.split()
    lines, current = [], ""
    for w in words:
        trial = f"{current} {w}".strip()
        if len(trial) > 52:
            lines.append(current)
            current = w
        else:
            current = trial
    if current:
        lines.append(current)
    lines = lines[:3]

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
             f'width="{width}" height="{height}" font-family="JetBrains Mono, monospace">']
    parts.append(f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="12" '
                 f'fill="none" stroke="{accent}" stroke-opacity="0.35"/>')
    parts.append(f'<text x="20" y="32" font-size="16" font-weight="700" fill="{accent}">{name}</text>')
    for i, line in enumerate(lines):
        parts.append(f'<text x="20" y="{58 + i*18}" font-size="12" fill="{text_color}" '
                     f'fill-opacity="0.85">{line}</text>')
    footer_y = height - 20
    parts.append(f'<circle cx="24" cy="{footer_y-4}" r="5" fill="{accent}"/>')
    parts.append(f'<text x="36" y="{footer_y}" font-size="11" fill="{text_color}">{language or "—"}</text>')
    parts.append(f'<text x="160" y="{footer_y}" font-size="11" fill="{text_color}">★ {stars}</text>')
    parts.append(f'<text x="220" y="{footer_y}" font-size="11" fill="{text_color}">⑂ {forks}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    args = parse_args()
    token = get_token()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        stats, repo_index = fetch_stats(args.user, token)
    except Exception as e:
        sys.exit(f"error fetching GitHub data: {e}")

    six_tiles = token is not None and stats["contributions"] is not None

    dark = stat_card_svg(args.user, stats, ACCENT, "#e6edf3", six_tiles)
    light = stat_card_svg(args.user, stats, ACCENT_LIGHT, "#1f2328", six_tiles)
    (out_dir / "card-stats-dark.svg").write_text(dark, encoding="utf-8")
    (out_dir / "card-stats-light.svg").write_text(light, encoding="utf-8")
    print(f"wrote {out_dir}/card-stats-dark.svg and card-stats-light.svg "
          f"({'6' if six_tiles else '3'} tiles)")

    projects_path = Path(args.projects) if args.projects else out_dir / "projects.json"
    if not projects_path.exists():
        print(f"note: {projects_path} not found — skipping project cards")
        return

    projects = json.loads(projects_path.read_text(encoding="utf-8")).get("projects", [])
    for proj in projects:
        repo_name = proj["repo"]
        repo = repo_index.get(repo_name)
        if repo is None:
            try:
                repo = rest_get(f"/repos/{args.user}/{repo_name}", token)
            except Exception:
                print(f"warning: couldn't fetch {repo_name}, skipping")
                continue
        description = proj.get("description") or repo.get("description")
        language = repo.get("language")
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)

        dark_card = project_card_svg(repo_name, description, language, stars, forks, ACCENT, "#e6edf3")
        light_card = project_card_svg(repo_name, description, language, stars, forks, ACCENT_LIGHT, "#1f2328")
        (out_dir / f"card-{repo_name.lower()}-dark.svg").write_text(dark_card, encoding="utf-8")
        (out_dir / f"card-{repo_name.lower()}-light.svg").write_text(light_card, encoding="utf-8")
        print(f"wrote card-{repo_name.lower()}-{{dark,light}}.svg")


if __name__ == "__main__":
    main()
