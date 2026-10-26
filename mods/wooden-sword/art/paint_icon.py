#!/usr/bin/env python3
"""Paint the Wooden Sword item icon (64x64 RGBA) procedurally, in the style of FL item icons.

Shapes are signed-distance fields in a sword-local frame (t along the blade from the pommel,
s across it), evaluated 4x supersampled and box-filtered. The frame below is laid out with the
pommel top-left; the image is mirrored vertically on output, so the PNG shows the icon as the
game displays it (pommel bottom-left, tip top-right, like every weapon icon in the menus).
Palette, outline colour/weight and the 45-degree layout follow the original sword/wood icons
(Squire's Sword, Oak Staff, Oak Beam). Standard library only.

    python3 -I mods/wooden-sword/art/paint_icon.py mods/wooden-sword/art/icon.png
"""
import math
import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('fl_ztex', ROOT / 'tools' / 'fl_ztex.py')
ztex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ztex)

SIZE, SS = 64, 4
OUTLINE = (84, 22, 24)          # sampled from the original icons' outline
OUTLINE_W = 2.1                 # icon pixels
INNER_W = 0.9                   # separating line between overlapping parts

# sword axis in icon pixels: pommel end -> tip
P0, P1 = (10.0, 9.8), (55.6, 55.2)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def sd_polygon(p, poly):
    """Signed distance to a convex/concave polygon (negative inside)."""
    d, sign = float('inf'), 1.0
    px, py = p
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        wx, wy = px - ax, py - ay
        h = max(0.0, min(1.0, (wx * ex + wy * ey) / (ex * ex + ey * ey)))
        dx, dy = wx - ex * h, wy - ey * h
        d = min(d, dx * dx + dy * dy)
        c1, c2, c3 = py >= ay, py < by, ex * wy > ey * wx
        if (c1 and c2 and c3) or (not c1 and not c2 and not c3):
            sign = -sign
    return sign * math.sqrt(d)


def sd_box(p, t0, t1, half, radius):
    t, s = p
    ct, hs = (t0 + t1) / 2, (t1 - t0) / 2
    qx, qy = abs(t - ct) - hs + radius, abs(s) - half + radius
    outside = math.hypot(max(qx, 0), max(qy, 0))
    return outside + min(max(qx, qy), 0) - radius


def sd_ellipse(p, ct, rt, rs):
    t, s = p
    k = math.hypot((t - ct) / rt, s / rs)
    return (k - 1) * min(rt, rs)


# ---------------------------------------------------------------- parts (t: 0..~67, s: +-)
BLADE = [(21.0, -4.3), (55.5, -4.3), (61.4, -2.0), (63.0, 0.0), (61.4, 2.0), (55.5, 4.3), (21.0, 4.3)]


def blade_sd(p):
    return sd_polygon(p, BLADE) - 0.6


def guard_sd(p):
    return sd_box(p, 17.4, 21.6, 7.6, 1.7)


def grip_sd(p):
    return sd_box(p, 6.4, 18.0, 2.5, 1.0)


def pommel_sd(p):
    return sd_ellipse(p, 4.3, 3.7, 3.9)


def noise(x, y, seed=0):
    """Smooth value noise for grain wobble."""
    def h(i, j):
        n = (i * 374761393 + j * 668265263 + seed * 1442695041) & 0xffffffff
        n = (n ^ (n >> 13)) * 1274126177 & 0xffffffff
        return ((n ^ (n >> 16)) & 0xffff) / 65535.0
    i, j = math.floor(x), math.floor(y)
    fx, fy = x - i, y - j
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = h(i, j), h(i + 1, j)
    c, d = h(i, j + 1), h(i + 1, j + 1)
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy


# ---------------------------------------------------------------- materials
OAK_HI = (250, 222, 166)
OAK_LIGHT = (240, 196, 132)
OAK = (224, 166, 98)
OAK_SHADE = (196, 128, 70)
OAK_DEEP = (166, 98, 52)
GRAIN = (164, 92, 46)


def blade_colour(p, sd):
    t, s = p
    across = s / 4.3                       # -1 lower-left edge .. +1 upper-right edge
    # broad soft gradient: lit upper-right half, shaded lower-left half
    c = mix(OAK_SHADE, OAK, smooth(-0.95, -0.15, across))
    c = mix(c, OAK_LIGHT, smooth(0.0, 0.55, across) * 0.85)
    # wood grain: long wavy streaks along the blade
    wob = 0.9 * math.sin(t * 0.21 + 1.3) + 1.4 * (noise(t * 0.08, 3.1) - 0.5)
    g = math.sin((s + wob) * 1.9 + 0.4)
    streak = smooth(0.80, 0.97, g) * (0.45 + 0.55 * noise(t * 0.16, s * 0.5, 2))
    streak *= smooth(21.5, 24.0, t)
    c = mix(c, GRAIN, streak * 0.95)
    # one small knot on the shaded half
    kd = math.hypot((t - 39.5) / 2.0, (s + 1.8) / 1.25)
    if kd < 1.6:
        ring = smooth(1.6, 1.1, kd) * (0.6 if kd > 0.55 else 1.0)
        c = mix(c, OAK_DEEP, ring * 0.75)
    # bevelled rim: bright highlight on the upper-right edge, darker rim on the lower-left edge
    rim = smooth(-1.45, -0.2, sd)          # 1 deep inside, 0 at the edge
    if s > 0:
        c = mix(OAK_HI, c, 0.25 + 0.75 * rim)
    else:
        c = mix(OAK_DEEP, c, 0.35 + 0.65 * rim)
    # gentle highlight streak just inside the lit edge (hand-painted gloss)
    hl = smooth(0.35, 0.62, across) * smooth(0.95, 0.7, across) * smooth(23, 30, t) * smooth(60, 50, t)
    c = mix(c, OAK_HI, hl * 0.55)
    return c


def guard_colour(p, sd):
    t, s = p
    base = mix((150, 86, 46), (196, 124, 70), smooth(-6.5, 3.0, s))
    base = mix(base, (226, 160, 98), smooth(18.6, 17.6, t) * 0.7)          # lit pommel-facing face
    base = mix(base, (128, 70, 38), smooth(20.4, 21.4, t) * 0.6)           # shaded blade-facing face
    wob = 0.5 * math.sin(t * 1.3)
    base = mix(base, (130, 74, 40), smooth(0.8, 0.98, math.sin((s + wob) * 1.9)) * 0.35)
    rim = smooth(-1.0, -0.15, sd)
    return mix(base, (232, 170, 104) if s > 0 else (120, 64, 34), (1 - rim) * 0.55)


def grip_colour(p, sd):
    t, s = p
    # red cloth wrap: diagonal bands with a dark seam, cylinder shading across
    across = s / 2.5
    light = smooth(-1.0, 0.6, across)
    base = mix((150, 40, 40), (214, 74, 62), light)
    base = mix(base, (238, 120, 96), smooth(0.25, 0.75, across) * smooth(1.0, 0.75, across) * 0.7)
    band = ((t - s * 0.9) / 3.0) % 1.0
    seam = smooth(0.62, 0.80, band) * smooth(1.0, 0.86, band)
    base = mix(base, (104, 24, 28), seam * 0.95)
    base = mix(base, (240, 132, 104), smooth(0.0, 0.18, band) * smooth(0.36, 0.18, band) * 0.35 * light)
    return base


def pommel_colour(p, sd):
    t, s = p
    d = math.hypot((t - 3.2) / 2.0, (s - 1.3) / 2.0)
    base = mix((150, 86, 46), (200, 128, 72), smooth(-3.8, 2.0, s + (4.3 - t) * 0.6))
    base = mix(base, (238, 182, 118), smooth(1.0, 0.2, d) * 0.85)
    rim = smooth(-1.0, -0.15, sd)
    return mix(base, (120, 64, 34), (1 - rim) * 0.45 * (1 if s < 0 else 0.4))


# draw order: later parts sit on top of earlier ones
PARTS = [(blade_sd, blade_colour), (guard_sd, guard_colour), (grip_sd, grip_colour), (pommel_sd, pommel_colour)]


def to_local(x, y):
    ax, ay = P1[0] - P0[0], P1[1] - P0[1]
    length = math.hypot(ax, ay)
    ux, uy = ax / length, ay / length
    scale = length / 63.0                  # local t 0..63 spans P0..P1
    dx, dy = x - P0[0], y - P0[1]
    t = (dx * ux + dy * uy) / scale
    s = (dx * uy - dy * ux) / scale        # +s = upper-right side
    return (t, s), scale


def shade_pixel(x, y):
    p, scale = to_local(x, y)
    sds = [f(p) * scale for f, _ in PARTS]  # distances in icon pixels
    union = min(sds)
    top = None
    for i in range(len(PARTS) - 1, -1, -1):
        if sds[i] < 0:
            top = i
            break
    if top is None:
        return OUTLINE + (255,) if union < OUTLINE_W else None
    colour = PARTS[top][1](p, sds[top] / scale)
    # dark separating line where this part covers an earlier one
    for j in range(top):
        if sds[j] < 0 and sds[top] > -INNER_W:
            colour = OUTLINE
            break
    return tuple(int(round(c)) for c in colour) + (255,)


def paint():
    n = SIZE * SS
    out = bytearray(SIZE * SIZE * 4)
    for y in range(SIZE):
        for x in range(SIZE):
            acc, alpha = [0.0, 0.0, 0.0], 0
            for sy in range(SS):
                for sx in range(SS):
                    c = shade_pixel(x + (sx + 0.5) / SS, y + (sy + 0.5) / SS)
                    if c:
                        alpha += 1
                        for k in range(3):
                            acc[k] += c[k]
            if alpha:
                o = ((SIZE - 1 - y) * SIZE + x) * 4   # mirrored: displayed orientation
                out[o:o + 4] = bytes([round(acc[0] / alpha), round(acc[1] / alpha), round(acc[2] / alpha),
                                      round(255 * alpha / (SS * SS))])
    return bytes(out)


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('icon.png')
    ztex.png_write(target, SIZE, SIZE, paint())
    print(f'wrote {target}')
