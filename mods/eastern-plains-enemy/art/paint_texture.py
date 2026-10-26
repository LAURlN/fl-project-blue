#!/usr/bin/env python3
"""Paint the Thistle Wolf texture (128x128) for the Red Wolf model's UV layout.

The colours are our own art. The script only reads the Red Wolf *geometry* (model 46390,
unit/mon/mon004/0001) from your extraction to learn which body part every texel covers:
each texel of the UV layout is baked to its 3D surface position, normal and skin weights,
and the fur is painted as a function of that 3D position. Seams therefore match on both
sides, and the mirrored halves stay symmetric. Small decals (eye, nose, teeth, tongue,
mouth) are painted per UV island.

Design: a thistle in wolf form. The spiky mane is the flower head: a sage-green spiny
bract collar at the root, violet florets, magenta-pink tips. Dusty lavender fur with
three sage leaf markings along the back, cream muzzle/bib, sage "stem" socks, a floret
tuft on the tail, chartreuse-gold eyes. Soft painted bands and a few flowing strokes
like the game's own monster textures; the in-game cel lighting adds the form shading.

    python3 -I mods/eastern-plains-enemy/art/paint_texture.py extracted/fl_eu/archive \\
        mods/eastern-plains-enemy/art/thistle_wolf.png

Standard library only. Deterministic: the same extraction gives the same PNG.
"""
import json
import math
import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[3]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ztex, zmdl, archive = load('fl_ztex'), load('fl_zmdl'), load('fl_archive')

MODEL = 46390            # Red Wolf model, shared with the Thistle Wolf
SIZE = 128

# ---------------------------------------------------------------- palette (own)
LAV_LIGHT = (204, 182, 222)
LAV = (160, 130, 190)
LAV_MID = (132, 102, 166)
LAV_DARK = (100, 74, 136)
PLUM = (74, 46, 96)
PLUM_DEEP = (52, 30, 66)
VIOLET = (140, 74, 170)
MAGENTA = (204, 82, 170)
PINK_TIP = (246, 150, 206)
PINK_GLOW = (255, 196, 228)
SAGE_LIGHT = (184, 208, 132)
SAGE = (126, 164, 92)
SAGE_DARK = (78, 116, 70)
CREAM = (248, 236, 204)
CREAM_SHADE = (222, 202, 166)
NOSE = (70, 38, 72)
TONGUE = (232, 120, 150)
TONGUE_DARK = (176, 70, 106)
MOUTH = (92, 36, 64)
TOOTH = (252, 250, 238)
TOOTH_SHADE = (214, 210, 200)
EYE_IRIS = (222, 228, 96)
EYE_IRIS_DARK = (150, 176, 52)
CLAW = (240, 232, 214)

HEAD_CENTRE = (0.0, 11.5)   # mane radiates around this point in the x/y plane


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def shade(colour, k):
    return tuple(c * k for c in colour)


def hash3(i, j, k, seed):
    n = (i * 374761393 + j * 668265263 + k * 2147483647 + seed * 1442695041) & 0xffffffff
    n = (n ^ (n >> 13)) * 1274126177 & 0xffffffff
    return ((n ^ (n >> 16)) & 0xffff) / 65535.0


def noise3(x, y, z, seed=0):
    """Smooth value noise, used only for gentle low-frequency variation."""
    i, j, k = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - i, y - j, z - k
    fx, fy, fz = (f * f * (3 - 2 * f) for f in (fx, fy, fz))
    total = 0.0
    for di in (0, 1):
        for dj in (0, 1):
            for dk in (0, 1):
                w = (fx if di else 1 - fx) * (fy if dj else 1 - fy) * (fz if dk else 1 - fz)
                total += w * hash3(i + di, j + dj, k + dk, seed)
    return total


def tri_wave(x):
    """0..1..0 sawtooth used for spiky (zigzag) edges."""
    x = x - math.floor(x)
    return 1 - abs(2 * x - 1)


# ---------------------------------------------------------------- bake
def bake(raw):
    """Per texel: 3D position, normal, bone weights and UV island of the covering triangle."""
    model = zmdl.parse(raw)
    names = [b['name'] for b in model['bones']]
    mesh = model['meshes'][0]
    verts = zmdl.vertices(raw, mesh)
    tris = []
    for group in mesh['groups']:
        idx = zmdl.indices(raw, group)
        for k in range(0, len(idx), 3):
            tv = [verts[i] for i in idx[k:k + 3]]
            weights = []
            for v in tv:
                w = {}
                for node, weight in zip(v['node'], v['weight']):
                    if weight > 0:
                        bone = names[group['nodes'][int(node)]]
                        w[bone] = w.get(bone, 0) + weight
                weights.append(w)
            tris.append((tv, weights))
    # UV islands: triangles connected through shared UV coordinates
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def key(v):
        return round(v['uv0'][0], 4), round(v['uv0'][1], 4)
    for tv, _ in tris:
        for v in tv[1:]:
            parent[find(key(v))] = find(key(tv[0]))
    islands = {}
    for n, (tv, _) in enumerate(tris):
        islands.setdefault(find(key(tv[0])), []).append(n)
    island_of = {}
    island_info = []
    for members in islands.values():
        us = [v['uv0'][0] * SIZE for n in members for v in tris[n][0]]
        vs = [(1 - v['uv0'][1]) * SIZE for n in members for v in tris[n][0]]
        info = dict(bbox=(min(us), min(vs), max(us), max(vs)), id=len(island_info))
        island_info.append(info)
        for n in members:
            island_of[n] = info['id']
    cells = [None] * (SIZE * SIZE)
    for n, (tv, weights) in enumerate(tris):
        pts = [(v['uv0'][0] * SIZE, (1 - v['uv0'][1]) * SIZE) for v in tv]
        (ax, ay), (bx, by), (cx, cy) = pts
        area = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        if abs(area) < 1e-12:
            continue
        for py in range(max(0, int(min(ay, by, cy)) - 1), min(SIZE - 1, int(max(ay, by, cy)) + 1) + 1):
            for px in range(max(0, int(min(ax, bx, cx)) - 1), min(SIZE - 1, int(max(ax, bx, cx)) + 1) + 1):
                fx, fy = px + 0.5, py + 0.5
                w0 = ((bx - fx) * (cy - fy) - (cx - fx) * (by - fy)) / area
                w1 = ((cx - fx) * (ay - fy) - (ax - fx) * (cy - fy)) / area
                w2 = 1 - w0 - w1
                inside = min(w0, w1, w2) >= 0
                if min(w0, w1, w2) < -0.04:
                    continue
                old = cells[py * SIZE + px]
                if old is not None and (old['inside'] or not inside):
                    continue
                ws = (w0, w1, w2)
                bones = {}
                for w, b in zip(ws, weights):
                    for name, value in b.items():
                        bones[name] = bones.get(name, 0) + w * value
                cells[py * SIZE + px] = dict(
                    pos=tuple(sum(w * v['position'][c] for w, v in zip(ws, tv)) for c in range(3)),
                    nrm=tuple(sum(w * v['normal'][c] for w, v in zip(ws, tv)) for c in range(3)),
                    bone=max(bones, key=bones.get), bones=bones, island=island_of[n],
                    uv=(fx, fy), inside=inside)
    return cells, island_info


def island_kind(info):
    """Name the Red Wolf's UV islands by their UV box (stable for model 46390)."""
    x0, y0, x1, y1 = info['bbox']
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if x1 < 17:
        return 'palate'
    if x0 > 120 and 40 < cy < 65:
        return 'teeth'
    if 18 <= x0 < 20 and x1 < 32 and 45 < y0 < 50:
        return 'tongue'
    if 74 < x0 < 77 and y0 > 110 and x1 > 85:
        return 'eye'
    if 74 < x0 < 77 and y0 > 110:
        return 'eye_corner'
    if 84 < x0 < 86 and 32 < y0 < 34:
        return 'ear_back'
    if 96 < x0 < 98 and 32 < y0 < 34:
        return 'ear_front'
    if 34 < x0 < 36 and 55 < y0 < 57:
        return 'crest'
    if 28 < x0 < 29 and 44 < y0 < 46:
        return 'tail'
    if 18 <= x0 < 20 and y0 > 95:
        return 'paws'
    if 39 < x0 < 40 and y0 > 108:
        return 'soles'
    if 96 < x0 < 98 and 7 < y0 < 9:
        return 'mane_back'
    if 110 < x0 < 111 and y0 < 2:
        return 'mane_back'
    if 110 < x0 < 111 and 43 < y0 < 45:
        return 'belly'
    if 71 < x0 < 73 and 94 < y0 < 96:
        return 'belly'
    if 18 <= x0 < 19 and y0 < 2:
        return 'head'
    return 'body'


# ---------------------------------------------------------------- painters
def mane(x, y, z, kind):
    """The thistle flower: bract root -> violet -> magenta -> pink tips, radial strokes."""
    dx, dy = x - HEAD_CENTRE[0], y - HEAD_CENTRE[1]
    r = math.hypot(dx, dy)
    theta = math.atan2(dy, abs(dx))
    m = smooth(3.15, 6.4, r + (0.5 if kind == 'mane_back' else 0.0))
    if kind == 'mane_back' and r < 3.0:
        return mix(LAV_MID, LAV_DARK, smooth(3.0, 1.0, r) * 0.5)      # nape fur behind the head
    # spiny bract collar at the root, with a zigzag edge
    edge = 0.15 + 0.07 * tri_wave(theta * 2.4 + 0.15)
    if m < edge:
        t = m / max(edge, 1e-6)
        col = mix(SAGE_DARK, SAGE, 0.35 + t)
        # overlapping spiny bract scales, like the cup of a thistle head
        scale = tri_wave(theta * 3.2 + (0.5 if (r * 1.3) % 2 < 1 else 0.0))
        col = mix(col, SAGE_LIGHT, smooth(0.45, 0.95, scale) * 0.45)
        if t > 0.86:
            col = mix(col, SAGE_DARK, 0.55)          # dark rim where florets begin
        return col
    t = (m - edge) / (1 - edge)
    col = mix(mix(PLUM, VIOLET, smooth(0.0, 0.2, t)), MAGENTA, smooth(0.2, 0.72, t))
    col = mix(col, PINK_TIP, smooth(0.62, 0.95, t))
    col = mix(col, PINK_GLOW, smooth(0.9, 1.0, t) * 0.6)
    # fibrous floret strokes along the spikes (a few broad bands, not noise)
    streak = 0.5 + 0.5 * math.sin(theta * 9.0 + 1.7 * noise3(x * 0.35, y * 0.35, z * 0.35, 7))
    col = shade(col, 0.9 + 0.13 * streak)
    if t < 0.12:
        col = mix(col, PLUM, 0.35 * (1 - t / 0.12))  # depth where florets sink into the bract
    return col


def fur(x, y, z, n, bone):
    """Lavender coat: light belly/chest, darker back, sage leaf markings on the back."""
    height = smooth(2.0, 7.5, y)
    col = mix(LAV_DARK, LAV, 0.35 + 0.65 * height)
    col = mix(col, LAV_LIGHT, smooth(0.55, 0.95, n[1]) * 0.35)    # painted top light
    col = mix(col, LAV_DARK, smooth(-0.2, -0.8, n[1]) * 0.45)     # belly in shadow
    # a few long flowing fur strokes along the body
    stroke = math.sin(y * 2.3 + 1.4 * noise3(x * 0.3, y * 0.3, z * 0.25, 5) * 3.0)
    col = shade(col, 0.97 + 0.05 * stroke)
    # chest bib: cream wedge under the chin
    if bone in ('shoulder', 'spine', 'neck') or z > 1.5:
        bib = smooth(1.9, 1.1, abs(x) + max(0.0, 6.6 - y) * 0.25) * smooth(1.6, 3.2, z) * smooth(9.0, 6.0, y)
        if bib > 0:
            col = mix(col, CREAM, smooth(0.25, 0.6, bib))
    # three leaf markings across the back (thistle leaves: pointed, with a light vein)
    if y > 6.0 and n[1] > 0.25:
        # a thistle stem along the spine from the mane to the tail, carrying the leaves
        if -5.2 < z < 2.6:
            stem = smooth(0.32, 0.18, x) * smooth(-5.2, -4.6, z) * smooth(2.6, 2.0, z)
            col = mix(col, mix(SAGE_DARK, SAGE, 0.4), stem)
        for zc in (1.5, -1.1, -3.7):
            along = (z - zc) - 0.6 * x                 # chevron pointing forward
            width = 0.8 - 0.3 * x
            if width > 0.1:
                leaf = smooth(width, width - 0.18, abs(along))
                if leaf > 0:
                    lc = SAGE if abs(along) > 0.2 or x > 1.1 else SAGE_LIGHT
                    col = mix(col, lc, leaf)
    return col


def leg(x, y, z, n, bone):
    """Lavender legs fading into sage 'stem' socks above the paws."""
    col = mix(LAV_MID, LAV, smooth(1.0, 4.0, y))
    sock = smooth(2.6, 1.9, y + 0.15 * math.sin(math.atan2(x, z) * 6))
    col = mix(col, SAGE, sock)
    if sock > 0 and y > 1.8:
        col = mix(col, SAGE_DARK, smooth(2.35, 2.55, y) * smooth(2.75, 2.55, y) * 0.8)  # rim line
    return col


def paws(x, y, z, n):
    col = mix(SAGE, SAGE_LIGHT, smooth(0.0, 1.2, y) * 0.6)
    toes = abs(math.sin(x * 4.2)) if z > 0 else abs(math.sin(x * 4.2 + 1))
    if y < 0.55 and toes < 0.18:
        col = mix(col, SAGE_DARK, 0.7)
    if y < 0.35 and n[1] > -0.5 and (z > 2.6 or -4.4 > z):
        col = CLAW
    return col


def tail(x, y, z):
    """Lavender tail ending in a little thistle floret."""
    t = smooth(-6.0, -12.8, z)
    col = mix(LAV, LAV_MID, smooth(4.5, 3.6, y) * 0.5)
    if t > 0.55:
        u = (t - 0.55) / 0.45
        col = mix(SAGE, SAGE_DARK, 0.3) if u < 0.25 else mix(MAGENTA, PINK_TIP, smooth(0.45, 1.0, u))
        if u >= 0.25:
            col = shade(col, 0.92 + 0.12 * (0.5 + 0.5 * math.sin(y * 6 + x * 5)))
    return col


def head(x, y, z, n, bone):
    """Face: lavender skull, cream muzzle/cheeks/chin, plum nose and lip line, mane around it."""
    r = math.hypot(x - HEAD_CENTRE[0], y - HEAD_CENTRE[1])
    if r > 3.3 + 0.3 * smooth(5.0, 7.0, z) and z < 7.0:
        return mane(x, y, z, 'head')
    col = mix(LAV, LAV_LIGHT, smooth(11.0, 14.5, y) * 0.45)
    # dark brow marks above the eyes (a little stern, like the Red Wolf)
    brow = smooth(0.9, 0.3, math.hypot(abs(x) - 1.9, (y - 14.35) * 1.6)) * smooth(3.3, 4.3, z)
    col = mix(col, LAV_DARK, brow * 0.85)
    muzzle = smooth(6.4, 7.6, z)
    cheek = smooth(1.3, 0.6, math.hypot(abs(x) - 2.9, (y - 10.4) * 0.8)) if z < 8 else 0
    col = mix(col, CREAM, max(muzzle, cheek))
    # a soft lavender blaze runs from the forehead down the bridge of the nose
    blaze = smooth(0.9, 0.3, x) * smooth(11.6, 12.4, y) * smooth(10.5, 8.0, z) * (n[1] > 0.2)
    col = mix(col, LAV, blaze * 0.8)
    if bone == 'mouth' or (z > 7 and y < 10.0):
        col = mix(CREAM_SHADE, CREAM, 0.5 + 0.5 * smooth(0, 1, -n[1]))     # chin
    if n[1] < -0.55 and z > 6.5 and 9.6 < y < 11.2 and bone != 'mouth':
        col = mix(col, MOUTH, 0.8)                                       # upper lip / gum
    nose = smooth(1.12, 0.92, math.hypot(x / 1.7, (y - 12.95) / 0.95, (z - 11.75) / 1.25))
    if nose > 0:
        col = mix(col, NOSE, nose)
        if n[1] > 0.5 and z < 12.3:
            col = mix(col, (136, 100, 138), 0.4 * nose)                  # nose highlight
    return col


def eye(u, v, bbox):
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2 + 0.3, (y0 + y1) / 2 + 0.6
    rx, ry = (x1 - x0) / 2 - 1.0, (y1 - y0) / 2 - 1.6
    d = math.hypot((u - cx) / rx, (v - cy) / ry)
    if d > 1.0:
        return PLUM_DEEP
    col = mix(EYE_IRIS, EYE_IRIS_DARK, smooth(0.2, 1.0, (cy - v) / ry * 0.6 + d * 0.5))
    pupil = math.hypot((u - cx) / (rx * 0.22), (v - cy) / (ry * 0.62))
    if pupil < 1.0:
        col = PLUM_DEEP
    if math.hypot(u - cx + rx * 0.35, v - cy + ry * 0.38) < 1.4:
        col = (255, 255, 240)                                             # highlight
    if v < cy - ry * 0.55:
        col = mix(col, PLUM_DEEP, smooth(cy - ry * 0.55, cy - ry * 0.85, v))   # heavy upper lid
    return col


def paint_cell(cell, kind, info):
    x, y, z = cell['pos']
    x = abs(x)
    n = cell['nrm']
    bone = cell['bone']
    if kind == 'palate':
        ridge = 0.5 + 0.5 * math.cos(z * 4.2)
        return mix(MOUTH, PLUM_DEEP, 0.35 + 0.35 * ridge)
    if kind == 'tongue':
        return mix(TONGUE, TONGUE_DARK, smooth(8.6, 6.0, z) * 0.7 + 0.2 * (0.5 + 0.5 * math.sin(y * 5)))
    if kind == 'teeth':
        return mix(TOOTH, TOOTH_SHADE, smooth(9.6, 8.4, y) * 0.6)
    if kind == 'eye':
        return eye(cell['uv'][0], cell['uv'][1], info['bbox'])
    if kind == 'eye_corner':
        return PLUM_DEEP
    if kind == 'ear_back':
        return mix(LAV_MID, VIOLET, smooth(14.5, 16.4, y))
    if kind == 'ear_front':
        inner = smooth(0.9, 0.4, abs(x - 2.0) + max(0.0, 14.2 - y) * 0.4)
        return mix(mix(LAV, VIOLET, smooth(14.8, 16.4, y)), (238, 170, 200), inner)
    if kind in ('crest', 'mane_back'):
        return mane(x, y, z, kind)
    if kind == 'tail':
        return tail(x, y, z)
    if kind == 'paws':
        return paws(x, y, z, n)
    if kind == 'soles':
        return mix(PLUM, LAV_DARK, 0.4)
    if kind == 'belly':
        return mix(LAV_LIGHT, CREAM, 0.25)
    if kind == 'head':
        return head(x, y, z, n, bone)
    if bone in ('L_arm', 'L_hand', 'L_shin', 'L_thigh', 'L_ankle', 'R_arm', 'R_hand', 'R_shin',
                'R_thigh', 'R_ankle', 'L_shoulder', 'R_shoulder') and y < 4.2:
        return leg(x, y, z, n, bone)
    if bone == 'tail':
        return tail(x, y, z)
    if bone in ('head', 'mouth'):
        return head(x, y, z, n, bone)
    return fur(x, y, z, n, bone)


def paint(raw):
    cells, islands = bake(raw)
    kinds = [island_kind(info) for info in islands]
    px = [None] * (SIZE * SIZE)
    for i, cell in enumerate(cells):
        if cell is not None:
            info = islands[cell['island']]
            px[i] = tuple(max(0, min(255, round(c))) for c in paint_cell(cell, kinds[info['id']], info))
    # pad every island by repeated dilation so ETC1 blocks and mipmaps never mix regions
    for _ in range(SIZE):
        empty = [i for i, p in enumerate(px) if p is None]
        if not empty:
            break
        new = {}
        for i in empty:
            x, y = i % SIZE, i // SIZE
            near = [px[j] for j in (i - 1 if x else -1, i + 1 if x < SIZE - 1 else -1,
                                    i - SIZE if y else -1, i + SIZE if y < SIZE - 1 else -1)
                    if j >= 0 and px[j] is not None]
            if near:
                new[i] = tuple(sum(c[k] for c in near) // len(near) for k in range(3))
        for i, c in new.items():
            px[i] = c
    return bytes(b for p in px for b in (*p, 255)), kinds


def model_bytes(extraction):
    manifest = json.loads((extraction / '.fl_archive/manifest.json').read_text())
    entry = next(e for e in manifest['entries'] if e['id'] == MODEL)
    raw = archive.safe_path(extraction, entry['path']).read_bytes()
    if archive.sha(raw) != entry['sha256']:
        raise SystemExit(f'model {MODEL} differs from the extraction manifest')
    return raw


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    rgba, _ = paint(model_bytes(Path(sys.argv[1])))
    ztex.png_write(Path(sys.argv[2]), SIZE, SIZE, rgba)


if __name__ == '__main__':
    main()
