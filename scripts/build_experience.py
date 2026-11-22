#!/usr/bin/env python3
"""Rebuild tiles/exp-metro.svg (career as a metro line on a real time axis, overlapping
jobs on a branch track) from scripts/experience.json and refresh the README between the experience markers
(the collapsed roles table is generated from the same file).

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
SVG = ROOT / "tiles/exp-metro.svg"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
W, H = 820, 292
PAD, R = 22, 24  # side padding, logo ring radius
MAIN_Y, BRANCH_Y = 156, 100  # overlapping jobs run on a branch track above the main line
TODAY = datetime.date.today()


def month(s):
    """'2024-06' -> months since year 0 (start of that month); 'present' -> today."""
    if s == "present":
        return TODAY.year * 12 + TODAY.month - 1 + TODAY.day / 31
    y, m = map(int, s.split("-"))
    return y * 12 + m - 1


def span(r):
    end = month(r["end"]) + (r["end"] != "present")  # an end month counts in full
    return month(r["start"]), end


def tracks(roles):
    """Greedy interval colouring: 0 = main line, 1 = branch. A one-month handover is not an overlap."""
    last, out = [], []
    for r in sorted(roles, key=lambda r: span(r)[0]):
        s, e = span(r)
        t = next((i for i, end in enumerate(last) if end <= s + 1), len(last))
        last[t:t + 1] = [e]
        out.append((r, t))
    assert max(t for _, t in out) <= 1, "ponytail: one branch level; add BRANCH_Y per level if three jobs ever overlap"
    return out


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
    s = 2 * (R - 2.5)
    return (
        f'<clipPath id="c{i}"><circle cx="{cx:.1f}" cy="{cy}" r="{R - 2.5}"/></clipPath>'
        f'<circle cx="{cx:.1f}" cy="{cy}" r="{R}" fill="#fff" filter="url(#sh)"/>'
        f'<g clip-path="url(#c{i})"><svg x="{cx - s / 2:.1f}" y="{cy - s / 2}" width="{s}" height="{s}" viewBox="{vb}" preserveAspectRatio="xMidYMid slice">'
        f'<image width="{w}" height="{h}" preserveAspectRatio="none" href="data:{kind};base64,{base64.b64encode(data).decode()}"/></svg></g>'
    )


def role_lines(role, fit=15):
    if len(role) <= fit:
        return [role]
    cut = min((i for i, c in enumerate(role) if c == " "), key=lambda i: abs(i - len(role) / 2))
    return [role[:cut], role[cut + 1 :]]


def label(r, cx, top, scale, single):
    """Role (bold), company, KPI pill, stacked from `top`; returns (svg, width). Widths are
    estimates (ponytail: ~0.6em per bold glyph), fine for these short strings."""
    lines = role_lines(r.get("label", r["role"]))
    fs, cs, ps = 12.5 * scale, 11.5 * scale, 10.5 * scale
    pw = 12 + 0.6 * ps * len(r["kpi"])
    w = max([0.6 * fs * len(l) for l in lines] + [0.55 * cs * len(r["company"]), pw])
    cx = min(max(cx, PAD + w / 2), W - PAD - w / 2)  # keep edge labels inside the panel
    y = top + fs + (0 if len(lines) == 2 else single)  # where a one-line role sits in the two-line slot
    spans = "".join(f'<tspan x="{cx:.1f}" y="{y + j * 15:.1f}">{escape(s)}</tspan>' for j, s in enumerate(lines))
    yc, yp = top + 2 * 15 + 12, top + 2 * 15 + 18
    return (
        f'<text text-anchor="middle" font-size="{fs:.1f}" font-weight="700" fill="#e6edf3">{spans}</text>'
        f'<text x="{cx:.1f}" y="{yc}" text-anchor="middle" font-size="{cs:.1f}" fill="#9da7b3">{escape(r["company"])}</text>'
        f'<rect x="{cx - pw / 2:.1f}" y="{yp}" width="{pw:.1f}" height="17" rx="4" fill="{r["color"]}" stroke="#fff" stroke-opacity="0.35"/>'
        f'<text x="{cx:.1f}" y="{yp + 12.3}" text-anchor="middle" font-size="{ps:.1f}" font-weight="700" fill="{ink(r["color"])}">{escape(r["kpi"])}</text>'
    ), cx, w


LABEL_H = 2 * 15 + 18 + 17  # two role lines, company, pill


def metro(roles):
    placed = tracks(roles)
    t0 = min(span(r)[0] for r in roles) - 3
    t1 = max(span(r)[1] for r in roles) + 4
    x = lambda m: PAD + (m - t0) / (t1 - t0) * (W - 2 * PAD)  # a real time axis: length ∝ duration
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
        "<title>" + escape(alt(roles)) + "</title>",
        '<defs><filter id="sh" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#000" flood-opacity="0.45"/></filter></defs>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="#161b22" stroke="#30363d"/>',
    ]
    for yr in range(int(t0 // 12), int(t1 // 12) + 1):  # year bands, ticks on each January
        a, b = x(max(t0, yr * 12)), x(min(t1, yr * 12 + 12))
        if yr * 12 > t0:
            out.append(f'<line x1="{a:.1f}" y1="12" x2="{a:.1f}" y2="{H - 24}" stroke="#30363d" stroke-dasharray="2 4"/>')
        out.append(f'<text x="{(a + b) / 2:.1f}" y="{H - 9}" text-anchor="middle" font-size="11" fill="#6e7681">{yr}</text>')
    main = [r for r, t in placed if t == 0]
    for p, n in zip(main, main[1:]):  # time between jobs on the main line stays visible
        if span(n)[0] > span(p)[1]:
            out.append(f'<line x1="{x(span(p)[1]):.1f}" y1="{MAIN_Y}" x2="{x(span(n)[0]):.1f}" y2="{MAIN_Y}" stroke="#6e7681" stroke-width="2.5" stroke-dasharray="4 4"/>')
    stations, labels = [], {0: [], 1: []}
    for i, (r, t) in enumerate(placed):
        a, b = x(span(r)[0]), x(span(r)[1])
        if t == 0:
            if r["end"] == "present":  # open segment runs past its station into the "now" arrow
                b = max(b, a + R + 8)
                out.append(f'<path d="M{b:.1f} {MAIN_Y - 9} l12 9 l-12 9 z" fill="{r["color"]}"/>')
                out.append(f'<text x="{b + 6:.1f}" y="{MAIN_Y - 16}" text-anchor="middle" font-size="11" font-weight="700" fill="#3fb950">now</text>')
            out.append(f'<line x1="{a:.1f}" y1="{MAIN_Y}" x2="{b:.1f}" y2="{MAIN_Y}" stroke="{r["color"]}" stroke-width="9" stroke-linecap="round"/>')
            cx, cy = a, MAIN_Y  # station at the start of the job
        else:
            # branch splits off the main line at the start, rejoins at the end; its x-extent is the job
            d = min(30, (b - a) / 2)
            out.append(
                f'<path d="M{a:.1f} {MAIN_Y} C{a + d / 2:.1f} {MAIN_Y} {a + d / 2:.1f} {BRANCH_Y} {a + d:.1f} {BRANCH_Y} '
                f'L{b - d:.1f} {BRANCH_Y} C{b - d / 2:.1f} {BRANCH_Y} {b - d / 2:.1f} {MAIN_Y} {b:.1f} {MAIN_Y}" '
                f'fill="none" stroke="{r["color"]}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>'
            )
            cx, cy = (a + b) / 2, BRANCH_Y
        stations.append(logo(r, cx, cy, i))
        labels[t].append((r, cx))
    out += stations
    # main: one-line roles centred in their slot; branch: one-line roles hug the company line
    for t, top, single in ((0, MAIN_Y + R + 8, 7), (1, BRANCH_Y - R - 8 - LABEL_H, 15)):
        row = sorted(labels[t], key=lambda l: l[1])
        for scale in (1, 0.92, 0.85, 0.78):  # shrink a crowded row until neighbours clear by 8px
            done = [label(r, cx, top, scale, single) for r, cx in row]
            if all(b[1] - b[2] / 2 - (a[1] + a[2] / 2) >= 8 for a, b in zip(done, done[1:])):
                break
        else:
            raise SystemExit(f"labels still collide on track {t}")
        out += [svg for svg, _, _ in done]
    return "\n".join(out + ["</svg>"]) + "\n"


def alt(roles):
    fmt = lambda s: "now" if s == "present" else datetime.date.fromisoformat(s + "-01").strftime("%b %Y")
    when = lambda r: f"{fmt(r['start'])}–{fmt(r['end'])}"
    return "Career timeline, oldest to newest (overlapping jobs on a branch line): " + " → ".join(
        f"{r['role']}, {r['company']} ({when(r)}, {r['kpi']})" for r in roles
    )


def table(roles):
    nb = lambda s: s.replace(" ", "&nbsp;") if len(s) <= 21 else s  # a long title may wrap
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
