#!/usr/bin/env python3
"""Paint the Wooden Sword model texture (128x128 RGB), matching the UV layout of build_mesh.py.

Style reference: the game's own wooden weapons (Oak Staff 3662, Oak Bow 3674): warm orange-tan
oak, broad soft grain bands with a few flowing darker strokes, cream highlight strips, no fine
noise. The in-game toon lighting adds the form shading, so this is mostly painted albedo with
gentle baked gradients. Regions are painted over generous gutters so ETC1 blocks and texture
filtering never pick up a neighbouring region. The painters below measure y downwards from
v = 0 (the tip/guard end); the result is flipped on output because v = 0 is the bottom row
of the PNG. Standard library only.

    python3 -I mods/wooden-sword/art/paint_texture.py mods/wooden-sword/art/sword_texture.png
"""
import math
import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('fl_ztex', ROOT / 'tools' / 'fl_ztex.py')
ztex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ztex)

SIZE = 128


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def noise(x, y, seed=0):
    def h(i, j):
        n = (i * 374761393 + j * 668265263 + seed * 1442695041) & 0xffffffff
        n = (n ^ (n >> 13)) * 1274126177 & 0xffffffff
        return ((n ^ (n >> 16)) & 0xffff) / 65535.0
    i, j = math.floor(x), math.floor(y)
    fx, fy = x - i, y - j
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b, c, d = h(i, j), h(i + 1, j), h(i, j + 1), h(i + 1, j + 1)
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy


OAK_CREAM = (248, 222, 168)
OAK_LIGHT = (240, 188, 118)
OAK = (228, 158, 88)
OAK_SHADE = (204, 128, 66)
OAK_GRAIN = (178, 100, 48)
OAK_DEEP = (140, 72, 34)


def blade(x, y):
    """x: 0..64 across the blade strip (edge, centre at 32, edge); y: 0 tip .. 128 guard."""
    across = (x - 32) / 29.4             # -1..1 edge to edge (both faces share the strip)
    along = y / 128
    # broad soft bands that drift slowly along the length
    drift = 0.22 * math.sin(along * 5.1 + 0.6) + 0.12 * math.sin(along * 11.3 + 2.0)
    band = math.sin((across + drift) * 5.2)
    c = mix(OAK, OAK_LIGHT, smooth(-0.2, 0.9, band) * 0.75)
    c = mix(c, OAK_SHADE, smooth(0.15, -0.85, band) * 0.55)
    # a few flowing darker strokes (hand-painted grain lines)
    for k, (offset, freq, phase, strength) in enumerate(((-0.42, 6.0, 0.4, 0.75), (0.18, 4.4, 2.1, 0.6),
                                                          (0.55, 7.3, 4.0, 0.5))):
        centre = offset + 0.07 * math.sin(along * freq + phase) + 0.04 * math.sin(along * 17 + k)
        width = 0.035 + 0.02 * noise(along * 9, k, 3)
        d = abs(across - centre)
        fade = smooth(0.0, 0.08, along) * smooth(1.0, 0.86, along) * (0.6 + 0.4 * noise(along * 6, k, 5))
        c = mix(c, OAK_GRAIN, smooth(width, width * 0.35, d) * strength * fade)
    # knot with a swirl of grain around it (one face shows it on each side, mirrored)
    kx, ky = -0.30, 0.47
    dx, dy = (across - kx) / 0.13, (along - ky) / 0.045
    r = math.hypot(dx, dy)
    c = mix(c, OAK_DEEP, smooth(0.85, 0.5, r) * 0.8)
    c = mix(c, OAK_GRAIN, smooth(0.25, 0.0, abs(r - 1.45)) * smooth(2.4, 1.0, r) * 0.55)
    # cream highlight strip down the lit middle of the blade (painted gloss)
    hl = smooth(0.30, 0.0, abs(across + 0.08 - 0.05 * math.sin(along * 6))) * smooth(0.05, 0.2, along)
    c = mix(c, OAK_CREAM, hl * smooth(0.95, 0.7, along) * 0.55)
    # rounded edges a little darker and warmer, the tip lighter, darker near the guard (contact shadow)
    c = mix(c, OAK_SHADE, smooth(0.78, 1.0, abs(across)) * 0.45)
    c = mix(c, OAK_LIGHT, smooth(0.14, 0.0, along) * 0.35)
    c = mix(c, OAK_DEEP, smooth(0.90, 1.0, along) * 0.45)
    return c


def guard(x, y):
    """x: 64..128 along the guard (end, centre, end); y: 0..32 (pommel side face .. blade side)."""
    along = (x - 96) / 29.4
    across = y / 32
    base = mix((196, 118, 58), (172, 98, 48), smooth(0.2, 0.9, across))
    wave = math.sin(across * 9.0 + 1.8 * math.sin(along * 3.0)) * 0.5 + 0.5
    base = mix(base, (214, 140, 74), smooth(0.55, 0.95, wave) * 0.5)
    base = mix(base, (140, 74, 34), smooth(0.86, 1.0, 1 - wave) * 0.35)
    # bevel edges catch light at the ends, darker in the middle of the long faces
    base = mix(base, (226, 158, 92), smooth(0.80, 1.0, abs(along)) * 0.45)
    base = mix(base, (128, 66, 30), smooth(0.12, 0.0, across) * 0.35 + smooth(0.88, 1.0, across) * 0.35)
    return base


def grip(x, y):
    """Red cloth wrap. x: 64..128 wraps once around the grip; y: 32..80 along it (guard .. pommel)."""
    around = (x - 66.6) / 58.9           # 0..1 around the circumference (seamless)
    along = (y - 34.6) / 43.5
    phase = (along * 5.0 + around) % 1.0  # helix: one band step per full turn
    light = math.sin(phase * math.pi)    # each band is a rounded strip of cloth
    c = mix((126, 30, 32), (206, 66, 56), smooth(0.0, 0.75, light))
    c = mix(c, (236, 112, 90), smooth(0.80, 1.0, light) * 0.6)
    c = mix(c, (96, 20, 26), smooth(0.12, 0.0, phase) * 0.7)
    weave = noise(x * 0.9, y * 0.9, 7) - 0.5
    c = mix(c, (150, 40, 40), max(0.0, -weave) * 0.25)
    # a darker turn where the wrap starts at the guard and ends at the pommel
    c = mix(c, (110, 26, 28), smooth(0.06, 0.0, along) * 0.6 + smooth(0.94, 1.0, along) * 0.6)
    return c


def pommel(x, y):
    """Ball pommel: x wraps around, y: 84..126 top (grip) .. bottom."""
    around = (x - 66.6) / 58.9
    along = (y - 84.5) / 41
    rings = math.sin(along * 9.0 + 0.8 * math.sin(around * 2 * math.pi)) * 0.5 + 0.5
    c = mix((198, 122, 60), (220, 150, 82), smooth(0.4, 1.0, rings) * 0.7)
    c = mix(c, (150, 82, 38), smooth(0.15, 0.0, rings) * 0.5)
    c = mix(c, (128, 66, 30), smooth(0.15, 0.0, along) * 0.5)      # contact with the grip
    return c


REGIONS = [  # (x0, y0, x1, y1, painter): painted in order with gutters into neighbours
    (0, 0, 64, 128, lambda x, y: blade(x, y)),
    (64, 0, 128, 32, guard),
    (64, 31, 128, 82, grip),
    (64, 81, 128, 128, pommel),
]


def paint():
    out = bytearray(SIZE * SIZE * 4)
    for x0, y0, x1, y1, painter in REGIONS:
        for y in range(y0, y1):
            for x in range(x0, x1):
                c = painter(x + 0.5, y + 0.5)
                o = ((SIZE - 1 - y) * SIZE + x) * 4   # painter y runs up from v = 0
                out[o:o + 4] = bytes(int(round(v)) for v in c) + b'\xff'
    return bytes(out)


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('sword_texture.png')
    ztex.png_write(target, SIZE, SIZE, paint())
    print(f'wrote {target}')
