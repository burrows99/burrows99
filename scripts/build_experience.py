#!/usr/bin/env python3
"""Rebuild tiles/exp-metro.svg (career as a metro line, oldest -> newest) from
scripts/experience.json and refresh the README between the experience markers
(the collapsed roles table is generated from the same file).

Usage: python3 scripts/build_experience.py
"""

import base64
import json
import pathlib
import re
import struct
import urllib.request
from html import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "scripts/experience.json").read_text())
SVG = ROOT / "tiles/exp-metro.svg"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
W, H = 820, 214
X0, STEP, LINE_Y, R = (
    72,
    128,
    84,
    33,
)  # first station x, spacing, line y, logo ring radius


def ink(hex_):
    r, g, b = (int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return "#1f2328" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.6 else "#fff"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.headers.get_content_type(), r.read()


def size(kind, data):
    if kind == "image/svg+xml":  # ponytail: viewBox only, every logo used here has one
        return tuple(map(float, re.search(rb'viewBox="([^"]+)"', data)[1].split()[2:]))
    return struct.unpack(">II", data[16:24])  # PNG IHDR


def logo(r, cx, cy, i):
    """Logo clipped to a circle; `crop` (x y w h in image units) picks the mark out of a wordmark."""
    kind, data = fetch(r["logo"])
    w, h = size(kind, data) if "crop" in r else (1, 1)
    vb = " ".join(map(str, r.get("crop", [0, 0, 1, 1])))
    s = 2 * (R - 3)
    return (
        f'<clipPath id="c{i}"><circle cx="{cx}" cy="{cy}" r="{R - 3}"/></clipPath>'
        f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="#fff" filter="url(#sh)"/>'
        f'<g clip-path="url(#c{i})"><svg x="{cx - s / 2}" y="{cy - s / 2}" width="{s}" height="{s}" viewBox="{vb}" preserveAspectRatio="xMidYMid slice">'
        f'<image width="{w}" height="{h}" preserveAspectRatio="none" href="data:{kind};base64,{base64.b64encode(data).decode()}"/></svg></g>'
    )


def role_lines(role, fit=15):
    if len(role) <= fit:
        return [role]
    cut = min(
        (i for i, c in enumerate(role) if c == " "),
        key=lambda i: abs(i - len(role) / 2),
    )
    return [role[:cut], role[cut + 1 :]]


def metro(roles):
    xs = [X0 + i * STEP for i in range(len(roles))]
    end = xs[-1] + 58
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
        "<title>" + escape(alt(roles)) + "</title>",
        '<defs><filter id="sh" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#000" flood-opacity="0.45"/></filter></defs>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="#161b22" stroke="#30363d"/>',
    ]
    # each company's segment runs from its station to the next one (its tenure)
    edges = [16] + xs[1:] + [end]
    for i, r in enumerate(roles):
        a = xs[i] if i else edges[0]
        out.append(
            f'<line x1="{a}" y1="{LINE_Y}" x2="{edges[i + 1]}" y2="{LINE_Y}" stroke="{r["color"]}" stroke-width="10" stroke-linecap="round"/>'
        )
    out.append(
        f'<path d="M{end + 2} {LINE_Y - 9} l12 9 l-12 9 z" fill="{roles[-1]["color"]}"/>'
    )
    out.append(
        f'<text x="{end + 8}" y="{LINE_Y + 30}" text-anchor="middle" font-size="11" font-weight="700" fill="#3fb950">now</text>'
    )
    for i, (r, x) in enumerate(zip(roles, xs)):
        out.append(
            f'<text x="{x}" y="{LINE_Y - R - 10}" text-anchor="middle" font-size="11" fill="#8b949e">{escape(r["years"])}</text>'
        )
        out.append(logo(r, x, LINE_Y, i))
        lines = role_lines(r["role"])
        y = LINE_Y + R + 20 if len(lines) == 1 else LINE_Y + R + 14
        spans = "".join(
            f'<tspan x="{x}" y="{y + j * 15}">{escape(s)}</tspan>'
            for j, s in enumerate(lines)
        )
        out.append(
            f'<text text-anchor="middle" font-size="13" font-weight="700" fill="#e6edf3">{spans}</text>'
        )
        out.append(
            f'<text x="{x}" y="{LINE_Y + R + 46}" text-anchor="middle" font-size="11.5" fill="#9da7b3">{escape(r["company"])}</text>'
        )
        pw = 14 + 6.4 * len(
            r["kpi"]
        )  # ponytail: ~6.4px per bold 10.5px glyph, fine for short pills
        py = LINE_Y + R + 55
        out.append(
            f'<rect x="{x - pw / 2:.1f}" y="{py}" width="{pw:.1f}" height="18" rx="4" fill="{r["color"]}" stroke="#fff" stroke-opacity="0.35"/>'
            f'<text x="{x}" y="{py + 12.8}" text-anchor="middle" font-size="10.5" font-weight="700" fill="{ink(r["color"])}">{escape(r["kpi"])}</text>'
        )
    return "\n".join(out + ["</svg>"]) + "\n"


def alt(roles):
    return "Career, oldest to newest: " + " → ".join(
        f"{r['role']}, {r['company']} ({r['years']}, {r['kpi']})" for r in roles
    )


def table(roles):
    nb = lambda s: s.replace(" ", "&nbsp;")
    rows = [
        f"| **{nb(r['role'])}**<br>[{nb(r['company'])}]({r['url']})&nbsp;·&nbsp;<sub>{r['years']}</sub> | {r['highlight']} |"
        for r in reversed(roles)  # table stays newest first
    ]
    return "\n".join(["| Role | Highlight |", "|---|---|"] + rows)


def main():
    roles = DATA["roles"]
    SVG.write_text(metro(roles))
    a = escape(alt(roles))
    snippet = "\n".join(
        [
            "<!-- experience:start (generated by scripts/build_experience.py) -->",
            f'<p align="center"><a href="{DATA["link"]}" title="{a}"><img src="./tiles/exp-metro.svg" width="{W}" alt="{a}" /></a></p>',
            "",
            "<details><summary>Roles and highlights</summary>",
            "",
            table(roles),
            "",
            "</details>",
            "<!-- experience:end -->",
        ]
    )
    readme = ROOT / "README.md"
    text = readme.read_text()
    new = re.sub(
        r"<!-- experience:start.*?<!-- experience:end -->",
        lambda _: snippet,
        text,
        flags=re.S,
    )
    if new != text:
        readme.write_text(new)
    print(snippet)


if __name__ == "__main__":
    main()
