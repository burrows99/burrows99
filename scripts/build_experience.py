#!/usr/bin/env python3
"""Rebuild tiles/exp-gantt.svg (career as a Gantt chart: one row per job, newest on top,
company logo in the gutter, bars on a real time axis) from scripts/experience.json and
refresh the README between the experience markers (the collapsed roles table is
generated from the same file).

Usage: python3 scripts/build_experience.py
"""

import base64
import datetime
import json
import pathlib
import re
import struct
import urllib.request
from html import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "scripts/experience.json").read_text())
SVG = ROOT / "tiles/exp-gantt.svg"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
TODAY = datetime.date.today()
W, PAD, GUTTER = 820, 18, 128  # panel width, side padding, logo + company column
TOP, ROW, BAR = 36, 38, 22  # first row y, row height, bar height
R = 15  # logo ring radius
MIN_BAR = 26  # a job that just started still gets a visible bar


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
    s = 2 * (R - 2)
    return (
        f'<clipPath id="c{i}"><circle cx="{cx}" cy="{cy}" r="{R - 2}"/></clipPath>'
        f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="#fff" filter="url(#sh)"/>'
        f'<g clip-path="url(#c{i})"><svg x="{cx - s / 2}" y="{cy - s / 2}" width="{s}" height="{s}" viewBox="{vb}" preserveAspectRatio="xMidYMid slice">'
        f'<image width="{w}" height="{h}" preserveAspectRatio="none" href="data:{kind};base64,{base64.b64encode(data).decode()}"/></svg></g>'
    )


def day(s):
    return TODAY if s == "present" else datetime.date.fromisoformat(s)


def text_w(s, fs):
    return 0.56 * fs * len(s)  # ponytail: ~0.56em per bold glyph (measured in Chrome), fine for these strings


def gantt(roles):
    rows = sorted(roles, key=lambda r: day(r["start"]), reverse=True)  # newest on top
    H = TOP + len(rows) * ROW + 26
    t0 = min(day(r["start"]) for r in roles).replace(day=1) - datetime.timedelta(
        days=45
    )
    t1 = TODAY + datetime.timedelta(days=290)  # headroom right of "now" for the "→ now" tag
    x0, x1 = PAD + GUTTER, W - PAD
    x = lambda d: x0 + (d - t0).days / (t1 - t0).days * (x1 - x0)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
        "<title>" + escape(alt(roles)) + "</title>",
        '<defs><filter id="sh" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="#000" flood-opacity="0.45"/></filter></defs>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="#161b22" stroke="#30363d"/>',
    ]
    for i in range(1, len(rows), 2):  # faint zebra rows
        out.append(
            f'<rect x="{PAD - 6}" y="{TOP + i * ROW}" width="{W - 2 * PAD + 12}" height="{ROW}" rx="6" fill="#1c2128"/>'
        )
    for yr in range(
        t0.year, t1.year + 1
    ):  # year gridlines on 1 January, label centred in its year
        a, b = max(t0, datetime.date(yr, 1, 1)), min(t1, datetime.date(yr + 1, 1, 1))
        if a.year == yr and a.month == 1 and a.day == 1:
            out.append(
                f'<line x1="{x(a):.1f}" y1="{TOP - 6}" x2="{x(a):.1f}" y2="{H - 14}" stroke="#30363d" stroke-dasharray="2 4"/>'
            )
        mid = a + (b - a) / 2
        out.append(
            f'<text x="{x(mid):.1f}" y="{TOP - 14}" text-anchor="middle" font-size="11" fill="#6e7681">{yr}</text>'
        )
    xn = x(TODAY)
    for i, r in enumerate(rows):
        cy = TOP + i * ROW + ROW / 2
        out.append(logo(r, PAD + R + 2, cy, i))
        out.append(
            f'<text x="{PAD + 2 * R + 10}" y="{cy + 4.5}" font-size="12.5" font-weight="600" fill="#e6edf3">{escape(r["company"])}</text>'
        )
        a, b = x(day(r["start"])), x(day(r["end"]))
        ongoing = r["end"] == "present"
        if ongoing:  # solid up to today, then a fade so a brand-new job doesn't look broken
            solid = max(b - a, 8)
            b = a + max(solid + 18, MIN_BAR)
            fade = f"g{i}"
            out.append(
                f'<linearGradient id="{fade}" x1="0" x2="1"><stop offset="0" stop-color="{r["color"]}"/>'
                f'<stop offset="{solid / (b - a):.2f}" stop-color="{r["color"]}"/><stop offset="1" stop-color="{r["color"]}" stop-opacity="0.15"/></linearGradient>'
            )
            fill = f"url(#{fade})"
        else:
            fill = r["color"]
        out.append(
            f'<rect x="{a:.1f}" y="{cy - BAR / 2}" width="{b - a:.1f}" height="{BAR}" rx="6" fill="{fill}"/>'
        )
        role, kpi = r.get("label", r["role"]), r["kpi"]
        fs, ps = 11.5, 10.5
        inside = not ongoing and text_w(role, fs) + 14 <= b - a
        if inside:
            out.append(
                f'<text x="{(a + b) / 2:.1f}" y="{cy + 4}" text-anchor="middle" font-size="{fs}" font-weight="700" fill="{ink(r["color"])}">{escape(role)}</text>'
            )
        # outside content, in reading order: [role] [pill]; right of the bar if it fits, else left of it
        items = ([] if inside else [("role", role, text_w(role, fs))]) + [("pill", kpi, 16 + text_w(kpi, ps))]
        need = sum(w for _, _, w in items) + 8 * (len(items) - 1)
        if ongoing:  # an open-ended bar always gets "→ now" right after it
            out.append(f'<text x="{b + 6:.1f}" y="{cy + 4}" font-size="{fs}" font-weight="700" fill="#3fb950">→ now</text>')
            assert b + 6 + text_w("→ now", fs) <= x1, "no room for → now; raise the headroom"
        right = not ongoing and b + 8 + need <= xn - 6  # labels never cross the "now" line
        cur = b + 8 if right else a - 8 - need
        assert cur >= x0 - 2, f"{r['company']} label runs into the gutter"
        for kind, s_, w in items:
            if kind == "pill":
                out.append(
                    f'<rect x="{cur:.1f}" y="{cy - 8.5}" width="{w:.1f}" height="17" rx="4" fill="{r["color"]}" stroke="#fff" stroke-opacity="0.35"/>'
                    f'<text x="{cur + w / 2:.1f}" y="{cy + 3.8}" text-anchor="middle" font-size="{ps}" font-weight="700" fill="{ink(r["color"])}">{escape(s_)}</text>'
                )
            else:
                out.append(f'<text x="{cur:.1f}" y="{cy + 4}" font-size="{fs}" font-weight="700" fill="#e6edf3">{escape(s_)}</text>')
            cur += w + 8
    out.append(
        f'<line x1="{xn:.1f}" y1="{TOP - 4}" x2="{xn:.1f}" y2="{H - 14}" stroke="#3fb950" stroke-width="1.5"/>'
    )
    out.append(
        f'<text x="{xn:.1f}" y="{H - 3}" text-anchor="middle" font-size="11" font-weight="700" fill="#3fb950">now</text>'
    )
    return "\n".join(out + ["</svg>"]) + "\n", H


def alt(roles):
    fmt = lambda s: (
        "now" if s == "present" else datetime.date.fromisoformat(s).strftime("%b %Y")
    )
    return "Career Gantt chart, newest first: " + "; ".join(
        f"{r['role']}, {r['company']} ({fmt(r['start'])}–{fmt(r['end'])}, {r['kpi']})"
        for r in sorted(roles, key=lambda r: r["start"], reverse=True)
    )


def table(roles):
    nb = lambda s: (
        s.replace(" ", "&nbsp;") if len(s) <= 21 else s
    )  # a long title may wrap
    rows = [
        f"| **{nb(r['role'])}**<br>[{nb(r['company'])}]({r['url']})&nbsp;·&nbsp;<sub>{r['years']}</sub> | {r['highlight']} |"
        for r in reversed(roles)  # table stays newest first
    ]
    return "\n".join(["| Role | Highlight |", "|---|---|"] + rows)


def main():
    roles = DATA["roles"]
    svg, _ = gantt(roles)
    SVG.write_text(svg)
    a = escape(alt(roles))
    snippet = "\n".join(
        [
            "<!-- experience:start (generated by scripts/build_experience.py) -->",
            f'<p align="center"><a href="{DATA["link"]}" title="{a}"><img src="./tiles/exp-gantt.svg" width="{W}" alt="{a}" /></a></p>',
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
