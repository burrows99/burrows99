#!/usr/bin/env python3
"""Rebuild tiles/*.svg + tiles/oss-treemap.svg from scripts/oss_wall.json and
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
    if "link" in p:
        return p["link"]
    return PRS.format(p["repo"], "open" if p["status"] == "open" else "merged")


def title(p):
    what = f"{p['count']} merged" if p["status"] == "merged" else {"open": "in review", "earlier": "earlier"}[p["status"]]
    return f"{p['name']} — {what}: {p['highlight']}"


def tile(p):
    b = badge(p)
    bw = 8 + 7 * len(
        b
    )  # ponytail: ~7px per bold 11px glyph, good enough for short badges
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="64" height="80" viewBox="0 0 64 80">
<title>{escape(title(p))}</title>
<clipPath id="c"><rect x="6" y="6" width="52" height="52" rx="10"/></clipPath>
<rect x="1" y="1" width="62" height="62" rx="14" fill="#fff" stroke="#d0d7de"/>
<image x="6" y="6" width="52" height="52" clip-path="url(#c)" href="{avatar(p["id"])}"/>
<rect x="{63 - bw}" y="45" width="{bw}" height="18" rx="9" fill="{BADGE[p["status"]]}" stroke="#fff" stroke-width="1.5"/>
<text x="{63 - bw / 2}" y="58" text-anchor="middle" font-family="{FONT}" font-size="11" font-weight="700" fill="#fff">{escape(b)}</text>
<text x="32" y="76" text-anchor="middle" font-family="{FONT}" font-size="10" fill="#8b949e">{escape(p["name"])}</text>
</svg>"""


def more_tile(m):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="208" height="64" viewBox="0 0 208 64">
<title>{m["projects"]} more projects, {m["open"]} open PRs</title>
<rect x="1" y="1" width="206" height="62" rx="14" fill="#9A6700"/>
<text x="104" y="28" text-anchor="middle" font-family="{FONT}" font-size="16" font-weight="700" fill="#fff">+{m["projects"]} more projects</text>
<text x="104" y="48" text-anchor="middle" font-family="{FONT}" font-size="12" fill="#fff">{m["open"]} PRs in review · browse all →</text>
</svg>"""


def squarify(items, x, y, w, h):
    """Bruls et al. squarified treemap; items = [(area, payload)] sorted desc."""
    out, items = [], list(items)
    while items:
        side, row = min(w, h), []
        worst = lambda r: max(
            max(
                side**2 * a / sum(b for b, _ in r) ** 2,
                sum(b for b, _ in r) ** 2 / (side**2 * a),
            )
            for a, _ in r
        )
        while items and (not row or worst(row + [items[0]]) <= worst(row)):
            row.append(items.pop(0))
        s = sum(a for a, _ in row)
        if w >= h:
            rw, yy = s / h, y
            for a, p in row:
                out.append((x, yy, rw, a / rw, p))
                yy += a / rw
            x, w = x + rw, w - rw
        else:
            rh, xx = s / w, x
            for a, p in row:
                out.append((xx, y, a / rh, rh, p))
                xx += a / rh
            y, h = y + rh, h - rh
    return out


def ink(hex_):
    r, g, b = (int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return "#1f2328" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.6 else "#fff"


def treemap(merged, W=800, H=170):
    total = sum(p["count"] for p in merged)
    rects = squarify(
        [
            (p["count"] * W * H / total, p)
            for p in sorted(merged, key=lambda p: -p["count"])
        ],
        0,
        0,
        W,
        H,
    )
    body = []
    for x, y, w, h, p in rects:
        fs = max(8, min(26, (w - 10) / (0.58 * len(p["name"])), h / 3.2))
        cx, cy, c = x + w / 2, y + h / 2, ink(p["color"])
        body.append(
            f'<rect x="{x + 1.5:.1f}" y="{y + 1.5:.1f}" width="{w - 3:.1f}" height="{h - 3:.1f}" rx="8" fill="{p["color"]}"/>'
            f'<text x="{cx:.1f}" y="{cy - fs * 0.15:.1f}" text-anchor="middle" font-size="{fs:.1f}" font-weight="600" fill="{c}">{escape(p["name"])}</text>'
            f'<text x="{cx:.1f}" y="{cy + fs * 1.05:.1f}" text-anchor="middle" font-size="{fs * 0.95:.1f}" fill="{c}" opacity="0.85">{p["count"]}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">'
        f"<title>{total} merged pull requests across {len(merged)} projects, sized by count</title>"
        + "".join(body)
        + "</svg>"
    )


def main():
    TILES.mkdir(exist_ok=True)
    rows = {"merged": [], "open": [], "earlier": []}
    for p in DATA["projects"]:
        name = f"{p['repo'].replace('/', '-')}-{p['status']}.svg"
        (TILES / name).write_text(tile(p))
        t = escape(title(p))
        rows[p["status"]].append(
            f'<a href="{link(p)}" title="{t}"><img src="./tiles/{name}" width="56" alt="{t}" /></a>'
        )
    (TILES / "more.svg").write_text(more_tile(DATA["more"]))
    merged = [p for p in DATA["projects"] if p["status"] == "merged"]
    (TILES / "oss-treemap.svg").write_text(treemap(merged))
    m, n_open = (
        DATA["more"],
        sum(p["count"] for p in DATA["projects"] if p["status"] == "open"),
    )
    label = lambda s: f"<sub><b>{s}</b></sub><br>"
    snippet = "\n".join(
        [
            "<!-- oss-wall:start (generated by scripts/build_oss_wall.py) -->",
            f'<p align="center"><a href="{DATA["merged_search"]}"><img src="./tiles/oss-treemap.svg" width="800" alt="Merged PRs by project: {", ".join(f"{p["name"]} {p["count"]}" for p in merged)}" /></a></p>',
            f'<p align="center">{label(f"✅ {sum(p["count"] for p in merged)} merged · {len(merged)} projects")}\n'
            + "\n".join(rows["merged"])
            + "</p>",
            f'<p align="center">{label(f"🟡 {n_open} in review · {len(rows["open"])} projects")}\n'
            + "\n".join(rows["open"])
            + f'<br>\n<a href="{m["link"]}" title="{m["projects"]} more projects, {m["open"]} open PRs"><img src="./tiles/more.svg" width="208" alt="+{m["projects"]} more projects, {m["open"]} open PRs" /></a></p>',
            f'<p align="center">{label("🕰️ earlier")}\n'
            + "\n".join(rows["earlier"])
            + "</p>",
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
