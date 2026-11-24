#!/usr/bin/env python3
"""Rebuild tiles/*.svg from scripts/oss_wall.json and
refresh the README between the oss-wall markers (also printed to stdout).

Usage: python3 scripts/build_oss_wall.py   # edit counts in oss_wall.json first
"""

import base64
import http.client
import json
import pathlib
import re
import urllib.request
from html import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
TILES = ROOT / "tiles"
DATA = json.loads((ROOT / "scripts/oss_wall.json").read_text())
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
BADGE = {"merged": "#1F883D", "open": "#BF8700", "earlier": "#6E7781"}
PRS = "https://github.com/{}/pulls?q=is%3Apr+author%3Aburrows99+is%3A{}"


def avatar(owner_id, cache={}):
    if owner_id not in cache:
        url = f"https://avatars.githubusercontent.com/u/{owner_id}?s=128"
        for attempt in range(3):  # avatars CDN occasionally truncates a read
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    cache[owner_id] = (
                        f"data:{r.headers.get_content_type()};base64,{base64.b64encode(r.read()).decode()}"
                    )
                break
            except (OSError, http.client.HTTPException):
                if attempt == 2:
                    raise
    return cache[owner_id]


def badge(p):
    if "badge" in p:
        return p["badge"]
    if p["status"] == "open":
        return "PR" if p["count"] == 1 else f"{p['count']} PR"
    return str(p["count"])


def link(p):
    # a card always opens that repo's list of my PRs (or issues), never a single PR
    if p.get("badge") == "issue":
        return f"https://github.com/{p['repo']}/issues?q=is%3Aissue+author%3Aburrows99"
    if p["status"] == "earlier":
        return f"https://github.com/{p['repo']}/pulls?q=is%3Apr+author%3Aburrows99"
    return PRS.format(p["repo"], "open" if p["status"] == "open" else "merged")


def title(p):
    what = (
        f"{p['count']} merged"
        if p["status"] == "merged"
        else {"open": "in review", "earlier": "earlier"}[p["status"]]
    )
    return f"{p['name']} — {what}: {p['highlight']}"


TILE_W, TILE_H = 104, 96  # brand-coloured block, one per project


def tile(p):
    b = badge(p)
    if p["status"] in ("earlier", "merged") and b.isdigit():
        b = f"{b} merged"
    c = ink(p["color"])
    fs = min(14, (TILE_W - 10) / (0.6 * len(p["name"])))  # ponytail: ~0.6em per glyph
    pw = 10 + 6.5 * len(b)  # ~6.5px per bold 10px glyph, fine for short pills
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{TILE_W}" height="{TILE_H}" viewBox="0 0 {TILE_W} {TILE_H}">
<title>{escape(title(p))}</title>
<rect x="1" y="1" width="{TILE_W - 2}" height="{TILE_H - 2}" rx="10" fill="{p["color"]}"/>
<clipPath id="c"><rect x="32" y="10" width="40" height="40" rx="8"/></clipPath>
<rect x="30" y="8" width="44" height="44" rx="10" fill="#fff"/>
<image x="32" y="10" width="40" height="40" clip-path="url(#c)" href="{avatar(p["id"])}"/>
<text x="{TILE_W / 2}" y="69" text-anchor="middle" font-family="{FONT}" font-size="{fs:.1f}" font-weight="600" fill="{c}">{escape(p["name"])}</text>
<rect x="{(TILE_W - pw) / 2:.1f}" y="76" width="{pw:.1f}" height="14" rx="7" fill="{BADGE[p["status"]]}" stroke="#fff" stroke-width="1"/>
<text x="{TILE_W / 2}" y="86.5" text-anchor="middle" font-family="{FONT}" font-size="10" font-weight="700" fill="#fff">{escape(b)}</text>
</svg>"""


def more_tile(m):
    # one more tile in the grid, same size and layout as the project blocks
    b = f"{m['open']} PR"
    pw = 10 + 6.5 * len(b)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{TILE_W}" height="{TILE_H}" viewBox="0 0 {TILE_W} {TILE_H}">
<title>{m["projects"]} more projects, {m["open"]} open PRs</title>
<rect x="1.5" y="1.5" width="{TILE_W - 3}" height="{TILE_H - 3}" rx="10" fill="#30363d" stroke="#8b949e" stroke-width="1.5" stroke-dasharray="5 4"/>
<text x="{TILE_W / 2}" y="44" text-anchor="middle" font-family="{FONT}" font-size="26" font-weight="700" fill="#fff">+{m["projects"]}</text>
<text x="{TILE_W / 2}" y="66" text-anchor="middle" font-family="{FONT}" font-size="12" font-weight="600" fill="#fff">more projects</text>
<rect x="{(TILE_W - pw) / 2:.1f}" y="76" width="{pw:.1f}" height="14" rx="7" fill="{BADGE["open"]}" stroke="#fff" stroke-width="1"/>
<text x="{TILE_W / 2}" y="86.5" text-anchor="middle" font-family="{FONT}" font-size="10" font-weight="700" fill="#fff">{escape(b)}</text>
</svg>"""


def ink(hex_):
    r, g, b = (int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return "#1f2328" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.6 else "#fff"


def main():
    TILES.mkdir(exist_ok=True)
    rows = {"merged": [], "open": [], "earlier": []}
    for p in DATA["projects"]:
        name = f"{p['repo'].replace('/', '-')}-{p['status']}.svg"
        (TILES / name).write_text(tile(p))
        t = escape(title(p))
        rows[p["status"]].append(
            f'<a href="{link(p)}" title="{t}"><img src="./tiles/{name}" width="{TILE_W}" alt="{t}" /></a>'
        )
    (TILES / "more.svg").write_text(more_tile(DATA["more"]))
    merged = [p for p in DATA["projects"] if p["status"] == "merged"]
    # one tile per merged project (biggest first) so each opens only that repo's merged PRs;
    # ponytail: the old one-image treemap could only link to a single combined search
    (TILES / "oss-treemap.svg").unlink(missing_ok=True)
    order = sorted(range(len(merged)), key=lambda i: -merged[i]["count"])
    rows["merged"] = [rows["merged"][i] for i in order]
    m, n_open = (
        DATA["more"],
        sum(p["count"] for p in DATA["projects"] if p["status"] == "open"),
    )
    label = lambda s: f"<sub><b>{s}</b></sub><br>"
    snippet = "\n".join(
        [
            "<!-- oss-wall:start (generated by scripts/build_oss_wall.py) -->",
            f'<p align="center">{label(f"✅ {sum(p["count"] for p in merged)} merged · {len(merged)} projects")}'
            f'<a href="{DATA["merged_search"]}">all merged PRs</a></p>\n<p align="center">\n' + "\n".join(rows["merged"]) + "</p>",
            # one grid: in-review blocks, then earlier ones (their pill tells them apart), then +more
            f'<p align="center">{label(f"🟡 {n_open} in review · 🕰️ {len(rows["earlier"])} earlier")}\n'
            + "\n".join(rows["open"] + rows["earlier"])
            + f'\n<a href="{m["link"]}" title="{m["projects"]} more projects, {m["open"]} open PRs"><img src="./tiles/more.svg" width="{TILE_W}" alt="+{m["projects"]} more projects, {m["open"]} open PRs" /></a></p>',
            "<!-- oss-wall:end -->",
        ]
    )
    readme = ROOT / "README.md"
    text = readme.read_text()
    new = re.sub(
        r"<!-- oss-wall:start.*?<!-- oss-wall:end -->",
        lambda _: snippet,
        text,
        flags=re.S,
    )
    if new != text:
        readme.write_text(new)
    print(snippet)


if __name__ == "__main__":
    main()
