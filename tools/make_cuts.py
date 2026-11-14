"""Make one line drawing (SVG) per haircut in docs/cuts/.

Each drawing is a neutral face outline of that face shape with a hair shape
on it. It shows the cut, not a real person.

The cut names come from the live `haircuts` table, so the file names match
what the page looks up: <face shape>-<cut name in lower case with hyphens>.svg

Usage (needs SUPABASE_URL and SUPABASE_ANON_KEY in .env, no other packages):
    python tools/make_cuts.py

It also writes tools/cuts-review.html, one page with every drawing (git-ignored).
"""

import html
import json
import math
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "cuts"
REVIEW = ROOT / "tools" / "cuts-review.html"

W, H, CX = 200, 260, 100
INK = "#1c1c1e"
HAIR = "#c4c8cf"
SKIN = "#ffffff"
STROKE = 2.2

# Face outlines: top of head and chin (y), then half-widths at the forehead,
# cheekbones, jaw and chin.
FACES = {
    "oval":     dict(top=55, chin=205, fw=44, cw=48, jw=38, chw=16),
    "round":    dict(top=62, chin=196, fw=46, cw=54, jw=46, chw=22),
    "square":   dict(top=60, chin=198, fw=50, cw=52, jw=50, chw=28),
    "oblong":   dict(top=46, chin=212, fw=42, cw=44, jw=38, chw=18),
    "heart":    dict(top=55, chin=205, fw=52, cw=50, jw=34, chw=10),
    "diamond":  dict(top=55, chin=205, fw=36, cw=52, jw=34, chw=12),
    "triangle": dict(top=58, chin=202, fw=38, cw=46, jw=52, chw=26),
}

# Hair settings per cut name.
#   tv      height of the hair above the head
#   sv      width of the hair beyond the face at the sides
#   fringe  none | full | soft | side | curtain
#   drop    how far down the fringe comes (fraction of face length)
#   hl      hairline height for fringe "none"
#   end     where the hair ends: None = at the ear (short cut),
#           a number = pixels below the chin, "bottom" = past the shoulders
#   ends    blunt | layered
#   frame   how much the hair covers the edge of the face
#   flare   extra width (+) or taper (-) at the ends
SHORT = dict(tv=9, sv=1.5, fringe="none", drop=None, hl=0.15, end=None, ends="blunt", frame=4, flare=0)
HANG = dict(tv=8, sv=9, fringe="curtain", drop=0.30, hl=0.15, end=28, ends="layered", frame=7, flare=-4)

CUTS = {
    # oval
    "Textured crop": dict(SHORT, tv=10, fringe="soft"),
    "Pixie cut": dict(SHORT, sv=3, fringe="side", drop=0.36),
    "Short tapered curls": dict(SHORT, tv=16),
    "Blunt bob": dict(HANG, end=4, ends="blunt", flare=0),
    "Medium side part": dict(HANG, end=-28, sv=7, frame=3, fringe="side", drop=0.34),
    "Shoulder-length layers": dict(HANG, end=30, sv=10, frame=6),
    "Long layers": dict(HANG, end="bottom", sv=10, frame=6),
    # round
    "Quiff with short sides": dict(SHORT, tv=28, hl=0.14),
    "Pixie with volume on top": dict(SHORT, tv=20, sv=3, fringe="side", drop=0.34),
    "High-top curls with tapered sides": dict(SHORT, tv=34),
    "Long bob below the chin": dict(HANG, end=18, ends="blunt", sv=7, frame=8, flare=0),
    "Layered cut with a side part": dict(HANG, end=26, sv=10, fringe="side", drop=0.36),
    "Long face-framing layers": dict(HANG, end="bottom", sv=8, frame=12),
    # square
    "Crew cut": dict(SHORT, tv=5, sv=1, hl=0.13),
    "Textured crop with a soft fringe": dict(SHORT, tv=10, fringe="soft"),
    "Soft pixie with a side-swept fringe": dict(SHORT, tv=10, sv=3, fringe="side", drop=0.42),
    "Wavy long bob": dict(HANG, end=18, sv=11, frame=8, flare=0),
    "Long soft layers": dict(HANG, end="bottom", sv=9),
    "Long curls": dict(HANG, end=45, sv=16, frame=8, flare=4),
    # oblong
    "Side-parted crop with fuller sides": dict(SHORT, tv=6, sv=6, fringe="side", drop=0.34),
    "French crop": dict(SHORT, tv=7, fringe="full", drop=0.33),
    "Pixie with a long side fringe": dict(SHORT, tv=8, sv=4, fringe="side", drop=0.46),
    "Chin-length bob with a fringe": dict(HANG, end=2, ends="blunt", sv=12, fringe="full", drop=0.37, flare=0),
    "Curly bob": dict(HANG, end=4, sv=16, frame=8, drop=0.32, flare=2),
    "Shoulder-length waves with a curtain fringe": dict(HANG, end=28, sv=12, drop=0.42),
    "Long layers with a fringe": dict(HANG, end="bottom", sv=12, frame=6, fringe="full", drop=0.37),
    # heart
    "Crop with a side-swept fringe": dict(SHORT, fringe="side", drop=0.40),
    "Textured pixie with a side-swept fringe": dict(SHORT, tv=11, sv=4, fringe="side", drop=0.42),
    "Tapered curls with a fringe": dict(SHORT, tv=16, fringe="full", drop=0.33),
    "Chin-length bob": dict(HANG, end=2, ends="blunt", sv=12, flare=0),
    "Shoulder-length cut with layers from the chin down": dict(HANG, end=30, frame=6, flare=6),
    "Long layers with a curtain fringe": dict(HANG, end="bottom", drop=0.42),
    # diamond
    "Textured fringe crop": dict(SHORT, tv=10, fringe="soft", drop=0.34),
    "Side part with length on top": dict(SHORT, tv=14, fringe="side", drop=0.30),
    "Pixie with a full fringe": dict(SHORT, sv=3, fringe="full", drop=0.37),
    "Short curls with a curly fringe": dict(SHORT, tv=16, sv=5, fringe="full", drop=0.34),
    "Shoulder-length shag with a curtain fringe": dict(HANG, end=28, sv=12, frame=8, drop=0.42),
    "Long layers with a side-swept fringe": dict(HANG, end="bottom", frame=6, fringe="side", drop=0.42),
    # triangle
    "Quiff with tapered sides": dict(SHORT, tv=26, hl=0.14),
    "Textured crop with a fuller top": dict(SHORT, tv=16, fringe="soft"),
    "Pixie with volume at the crown": dict(SHORT, tv=18, sv=4, fringe="side", drop=0.36),
    "Layered cut with volume at the temples": dict(HANG, end=10, sv=16, frame=6, flare=-12, fringe="side", drop=0.36),
    "Shoulder-length cut with a side-swept fringe": dict(HANG, end=28, sv=8, frame=6, fringe="side", drop=0.42),
    "Long layers with crown volume": dict(HANG, end="bottom", tv=20, frame=6),
}

# Outline texture: wave height and wave length in pixels.
TEXTURE = {
    "straight": None,
    "wavy": dict(amp=2.6, lam=26, bumps=False),
    "curly": dict(amp=4.2, lam=11, bumps=True),
    "coily": dict(amp=3.0, lam=7, bumps=True),
}


def slug(text):
    """Same rule as slug() in docs/app.js."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def spline(points, closed=False, steps=12):
    """Catmull-Rom spline through the points, as a dense list of points."""
    n = len(points)
    out = []
    last = n if closed else n - 1
    for i in range(last):
        if closed:
            p0, p1, p2, p3 = (points[(i + k - 1) % n] for k in range(4))
        else:
            p0 = points[max(i - 1, 0)]
            p1, p2 = points[i], points[i + 1]
            p3 = points[min(i + 2, n - 1)]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(
                0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t
                       + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                       + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3)
                for k in (0, 1)
            ))
    if not closed:
        out.append(points[-1])
    return out


def resample(points, weights, step=1.5):
    """Points at even spacing along the line, with weights carried along."""
    out_p, out_w = [points[0]], [weights[0]]
    carry = 0.0
    for (a, b, wa, wb) in zip(points, points[1:], weights, weights[1:]):
        seg = math.dist(a, b)
        if seg == 0:
            continue
        d = step - carry
        while d <= seg:
            t = d / seg
            out_p.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            out_w.append(wa + (wb - wa) * t)
            d += step
        carry = seg - (d - step)
    out_p.append(points[-1])
    out_w.append(weights[-1])
    return out_p, out_w


def displace(points, weights, tex):
    """Push the line sideways in a wave (wavy) or in bumps (curly, coily)."""
    if not tex:
        return points
    pts, ws = resample(points, weights)
    out = []
    dist_along = 0.0
    for i, p in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        norm = math.hypot(tx, ty) or 1.0
        nx, ny = ty / norm, -tx / norm  # points away from the head
        if i:
            dist_along += math.dist(pts[i - 1], p)
        wave = math.sin(2 * math.pi * dist_along / tex["lam"])
        if tex["bumps"]:
            wave = abs(math.sin(math.pi * dist_along / tex["lam"]))
        off = tex["amp"] * wave * ws[i]
        out.append((p[0] + nx * off, p[1] + ny * off))
    return out


def path(points, close=True):
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return d + (" Z" if close else "")


def mirror(points):
    return [(2 * CX - x, y) for x, y in points]


class Face:
    def __init__(self, shape):
        f = FACES[shape]
        self.top, self.chin = f["top"], f["chin"]
        self.len = self.chin - self.top
        fw, cw, jw, chw = f["fw"], f["cw"], f["jw"], f["chw"]
        y = self.y
        right = [
            (CX, self.top),
            (CX + 0.62 * fw, y(0.045)),
            (CX + 0.93 * fw, y(0.14)),
            (CX + fw, y(0.27)),
            (CX + cw, y(0.50)),
            (CX + jw, y(0.78)),
            (CX + chw, y(0.965)),
            (CX, self.chin),
        ]
        left = mirror(right[1:-1])[::-1]
        self.outline = spline(right + left, closed=True)
        chin_i = max(range(len(self.outline)), key=lambda i: self.outline[i][1])
        self.right = self.outline[: chin_i + 1]

    def y(self, fraction):
        return self.top + fraction * self.len

    def hw(self, y):
        """Half-width of the face at height y."""
        for (x0, y0), (x1, y1) in zip(self.right, self.right[1:]):
            if y0 <= y <= y1 and y1 > y0:
                return x0 + (x1 - x0) * (y - y0) / (y1 - y0) - CX
        return 0.0


def hairline(face, spec, xt_at):
    """Lower edge of the hair on the forehead, from the right temple to the
    left temple. Returns (points, right temple y, left temple y)."""
    kind = spec["fringe"]
    y = face.y

    if kind == "none":
        hl = spec["hl"]
        yt = y(hl + 0.15)
        xt = xt_at(yt)
        pts = spline([(xt, yt), (0.6 * xt, y(hl + 0.035)), (0, y(hl)), (-0.6 * xt, y(hl + 0.035)), (-xt, yt)])
        return pts, yt, yt

    if kind in ("full", "soft"):
        drop = spec["drop"] or (0.37 if kind == "full" else 0.29)
        yt = y(drop + 0.03)
        xt = xt_at(yt)
        pts = spline([(xt, yt), (0.82 * xt, y(drop)), (0, y(drop) + 1.5), (-0.82 * xt, y(drop)), (-xt, yt)])
        if kind == "soft":  # broken, choppy edge
            pts, _ = resample(pts, [1] * len(pts), step=4.5)
            pts = [(px, py + (2.6 if i % 2 else -2.6) * (0 < i < len(pts) - 1)) for i, (px, py) in enumerate(pts)]
        return pts, yt, yt

    if kind == "side":
        drop = spec["drop"] or 0.42
        part_y = 0.14
        yt_r, yt_l = y(drop), y(0.30)
        xr, xl = xt_at(yt_r), xt_at(yt_l)
        part = (-0.45 * xl, y(part_y))
        at = lambda k: y(part_y + (drop - part_y) * k)
        seg1 = spline([(xr, yt_r), (0.55 * xr, at(0.74)), (0.05 * xr, at(0.40)), part])
        seg2 = spline([part, (-0.78 * xl, y(0.20)), (-xl, yt_l)])
        return seg1 + seg2[1:], yt_r, yt_l

    # curtain: centre part, hair falls to both temples
    drop = spec["drop"] or 0.42
    yt = y(drop)
    xt = xt_at(yt)
    centre = (0, y(0.13))
    at = lambda k: y(0.13 + (drop - 0.13) * k)
    seg = spline([(xt, yt), (0.6 * xt, at(0.62)), (0.22 * xt, at(0.25)), centre])
    return seg + [(-px, py) for px, py in seg[::-1]][1:], yt, yt


def draw(shape, name, texture):
    face = Face(shape)
    spec = CUTS.get(name)
    if spec is None:
        raise KeyError(name)
    y, hw = face.y, face.hw
    tex = TEXTURE[texture]
    short = spec["end"] is None
    y_t, y_c = y(0.27), y(0.50)
    tv, sv, frame = spec["tv"], spec["sv"], spec["frame"]

    if short:
        side_end = y(0.47) if sv < 5 else y(0.56)
    elif spec["end"] == "bottom":
        side_end = H - 8
    else:
        side_end = face.chin + spec["end"]

    # Where the outline texture applies: curls on a short cut sit on top,
    # waves show in the hanging part, curls on longer hair are everywhere.
    def tex_weight(py):
        if not tex:
            return 0.0
        if short:
            return 1 - smoothstep((py - y_t) / (0.10 * face.len)) if tex["bumps"] else 0.0
        if tex["bumps"]:
            return 1.0
        return smoothstep((py - y_t) / (y_c - y_t))

    # ---- outer edge of the hair, right side, from the top centre down ----
    wc = hw(y_c) + sv
    lower_max = max(hw(yy) for yy in range(int(y_c), int(face.chin)))
    w_end = max(wc, lower_max + sv) + spec["flare"]

    def outer_below(py):
        u = (py - y_c) / max(side_end - y_c, 1)
        return max(hw(py) + sv, wc + (w_end - wc) * u)

    outer, weights = [], []
    for (px, py) in face.right:
        if py > min(side_end, y_c):
            break
        s = smoothstep((py - face.top) / (y_t - face.top))
        outer.append((px + sv * s, py - tv * (1 - s)))
        weights.append(tex_weight(py))
    if side_end > y_c:
        py = y_c + 2
        while py < side_end:
            outer.append((CX + outer_below(py), py))
            weights.append(tex_weight(py))
            py += 2
        outer.append((CX + outer_below(side_end), side_end))
    else:
        outer.append((CX + hw(side_end) + sv, side_end))
    weights.append(tex_weight(side_end))
    outer = displace(outer, weights, tex)
    outer_x_end = outer[-1][0] - CX

    # ---- inner edge of the hair next to the face ----
    def inner(py):
        if py <= y_c:
            x = hw(py) - frame
        else:
            x = max(hw(py) - frame, hw(y_c) - frame - 0.12 * (py - y_c))
        return x

    line, yt_r, yt_l = hairline(face, spec, inner)
    line = [(CX + px, py) for px, py in line]
    if tex and tex["bumps"] and spec["fringe"] in ("full", "none"):
        line = displace(line, [0.6] * len(line), dict(tex, amp=tex["amp"] * 0.8))

    inner_end = side_end - (10 if (spec["ends"] == "layered" and not short) else 0)

    def inner_edge(y_from):
        pts, py = [], inner_end
        while py > y_from:
            pts.append((CX + min(inner(py), outer_x_end - 3 if py > y_c else 1e9), py))
            py -= 2
        return pts

    right_inner = inner_edge(yt_r)             # bottom -> temple
    left_inner = mirror(inner_edge(yt_l))[::-1]  # temple -> bottom
    left_outer = mirror(outer)[::-1]           # bottom -> top centre

    hair = left_outer + outer[1:] + right_inner + line + left_inner

    parts = [f'<rect width="{W}" height="{H}" rx="12" fill="#ffffff"/>']
    style = f'stroke="{INK}" stroke-width="{STROKE}" stroke-linejoin="round" stroke-linecap="round"'

    # 1. hair behind the head (only for hair that hangs)
    if not short:
        back = [p for p in outer if p[1] >= y_t]
        back = back + mirror(back)[::-1]
        parts.append(f'<path d="{path(back)}" fill="{HAIR}" {style}/>')

    # 2. neck and shoulders
    nb = face.chin + 14
    neck = [(CX - 17, face.chin - 0.1 * face.len), (CX - 19, nb), (CX - 50, nb + 12), (CX - 84, nb + 24), (CX - 92, H + 4)]
    neck = neck + mirror(neck)[::-1]
    parts.append(f'<path d="{path(neck)}" fill="{SKIN}" {style}/>')

    # 3. ears, then the face
    y_ear = y(0.52)
    for sign in (-1, 1):
        parts.append(f'<ellipse cx="{CX + sign * (hw(y_ear) + 2):.1f}" cy="{y_ear:.1f}" rx="5" ry="10" fill="{SKIN}" {style}/>')
    parts.append(f'<path d="{path(face.outline)}" fill="{SKIN}" {style}/>')

    # 4. simple features
    ey, ex = y(0.47), 0.45 * hw(y(0.47))
    for sign in (-1, 1):
        parts.append(f'<path d="M{CX + sign * ex - 6:.1f},{ey:.1f} q6,-4 12,0" fill="none" {style}/>')
    parts.append(f'<path d="M{CX},{y(0.55):.1f} q-5,{0.10 * face.len:.1f} 1,{0.11 * face.len:.1f}" fill="none" {style}/>')
    parts.append(f'<path d="M{CX - 10},{y(0.80):.1f} q10,5 20,0" fill="none" {style}/>')

    # 5. hair in front
    parts.append(f'<path d="{path(hair)}" fill="{HAIR}" {style}/>')

    # 6. parting line
    def top_of_hair(xrel):
        side = outer if xrel >= 0 else mirror(outer)
        return min(side, key=lambda p: abs(p[0] - CX - xrel))[1]

    if spec["fringe"] == "side":
        px, py = -0.45 * inner(yt_l), y(0.14)
        tx = px * 0.8
        parts.append(f'<path d="M{CX + px:.1f},{py:.1f} L{CX + tx:.1f},{top_of_hair(tx) + 4:.1f}" fill="none" {style}/>')
    elif spec["fringe"] == "curtain":
        parts.append(f'<path d="M{CX},{y(0.13):.1f} L{CX},{face.top - tv + 4:.1f}" fill="none" {style}/>')

    # 7. one inner line per side to hint at layers
    if not short and spec["ends"] == "layered" and side_end - y_c > 40:
        for sign in (-1, 1):
            pts, py = [], y_c + 8
            while py < inner_end - 6:
                pts.append((CX + sign * (0.5 * (outer_below(py) + inner(py))), py))
                py += 2
            pts = displace(pts, [1] * len(pts), tex if tex and not tex["bumps"] else None)
            parts.append(f'<path d="{path(pts, close=False)}" fill="none" stroke="{INK}" stroke-width="1.2" stroke-linecap="round"/>')

    label = html.escape(f"{name}, on a neutral {shape} face outline")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">\n'
        + "\n".join(parts)
        + "\n</svg>\n"
    )


def read_env():
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"')
    return env


def fetch_haircuts():
    env = read_env()
    url = env["SUPABASE_URL"].rstrip("/") + "/rest/v1/haircuts?select=id,face_shape,name,textures&order=id"
    request = urllib.request.Request(url, headers={"apikey": env["SUPABASE_ANON_KEY"]})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main():
    rows = fetch_haircuts()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.svg"):
        old.unlink()

    cards, missing = [], []
    for row in rows:
        shape, name = row["face_shape"], row["name"]
        if name not in CUTS:
            missing.append(f"{shape}: {name}")
            continue
        file_name = f"{slug(shape)}-{slug(name)}.svg"
        (OUT_DIR / file_name).write_text(draw(shape, name, row["textures"][0]), encoding="utf-8", newline="\n")
        cards.append(
            f'<figure><img src="../docs/cuts/{file_name}" alt=""><figcaption><b>{row["id"]}. {html.escape(name)}</b>'
            f'<br>{shape} · drawn {row["textures"][0]}</figcaption></figure>'
        )

    REVIEW.write_text(
        "<!doctype html><meta charset='utf-8'><title>Haircut drawings review</title>"
        "<style>body{font:14px system-ui;margin:16px;background:#eef0f3;color:#1c1c1e}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}"
        "figure{margin:0}img{width:100%;display:block;border-radius:10px}figcaption{padding:4px 2px}</style>"
        f"<h1>Haircut drawings ({len(cards)})</h1><div class='grid'>{''.join(cards)}</div>",
        encoding="utf-8",
        newline="\n",
    )

    print(f"Wrote {len(cards)} drawings to {OUT_DIR}", file=sys.stderr)
    for item in missing:
        print(f"No drawing settings for: {item}", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
