#!/usr/bin/env python3
"""Generate the Wooden Sword mesh (our own geometry) as JSON for fl_mod.py.

Model space follows the Squire's Sword (resource 3804) it replaces at build time: rigid on bone
R_tool, z = blade axis (pommel ~-1.9, tip ~8.4), x = blade width, y = thickness, origin in the
hand. Shape: a chunky training sword: thick lens-shaped blade with soft edges and a rounded tip,
a bevelled wooden block guard, a cloth-wrapped round grip and a ball pommel.

UVs address the 128x128 texture painted by paint_texture.py (v = 0 is the bottom row of the PNG,
as fl_ztex decodes it; regions below are listed in v):
    blade  u 0.02-0.48, v 0.02-0.98 (front and back share the strip, mapped by x)
    guard  u 0.52-0.98, v 0.02-0.22
    grip   u 0.52-0.98, v 0.27-0.61 (wraps around)
    pommel u 0.52-0.98, v 0.66-0.98 (wraps around)

Vertex record: position, normal, uv, outline normal (smooth normal per position, used by the
game's inverted-hull outline). Triangles are counter-clockwise seen from outside.

    python3 -I mods/wooden-sword/art/build_mesh.py mods/wooden-sword/art/sword_mesh.json
"""
import json
import math
import sys
from pathlib import Path

verts, tris = [], []


def norm(v):
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / length for c in v)


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def add_vertex(position, normal, uv):
    verts.append(dict(position=position, normal=norm(normal), uv=uv))
    return len(verts) - 1


def add_tri(a, b, c):
    """Add a triangle, flipping it if needed so it is counter-clockwise around its normal."""
    pa, pb, pc = (verts[i]['position'] for i in (a, b, c))
    n = cross(sub(pb, pa), sub(pc, pa))
    avg = [sum(verts[i]['normal'][k] for i in (a, b, c)) for k in range(3)]
    if sum(x * y for x, y in zip(n, avg)) < 0:
        b, c = c, b
    tris.append((a, b, c))


def loft(rings, uv_of, closed_tip=None, wrap_seam=False):
    """rings: list of (z, [(x, y, nx, ny), ...]) with the same point count, CCW seen from +z.

    Smooth normals (profile normal + slope along z). With wrap_seam the first point is repeated
    at the end (u = 1) so the texture can wrap around; otherwise the ring is closed directly.
    """
    count = len(rings[0][1])
    ids = []
    for r, (z, points) in enumerate(rings):
        # slope: how much the profile shrinks along z here (for the normal's z component)
        prev_z, prev_pts = rings[max(0, r - 1)]
        next_z, next_pts = rings[min(len(rings) - 1, r + 1)]
        row = []
        span = list(range(count)) + ([0] if wrap_seam else [])
        for k, i in enumerate(span):
            x, y, nx, ny = points[i]
            dz = next_z - prev_z
            radial_change = 0.0
            if dz:
                r0 = math.hypot(prev_pts[i][0], prev_pts[i][1])
                r1 = math.hypot(next_pts[i][0], next_pts[i][1])
                radial_change = -(r1 - r0) / dz
            normal = (nx, ny, radial_change)
            row.append(add_vertex((x, y, z), normal, uv_of(x, y, z, k / count if wrap_seam else None, i)))
        ids.append(row)
    width = count + (1 if wrap_seam else 0)
    for r in range(len(rings) - 1):
        for i in range(count):
            j = (i + 1) if wrap_seam else (i + 1) % count
            a, b, c, d = ids[r][i], ids[r][j], ids[r + 1][j], ids[r + 1][i]
            add_tri(a, b, c)
            add_tri(a, c, d)
    if closed_tip is not None:
        z, normal, uv = closed_tip
        tip = add_vertex((0.0, 0.0, z), normal, uv)
        last = ids[-1]
        for i in range(count):
            j = (i + 1) if wrap_seam else (i + 1) % count
            add_tri(last[i], last[j], tip)
    return ids


def ellipse_ring(rx, ry, count, start=0.0):
    pts = []
    for i in range(count):
        a = start + 2 * math.pi * i / count
        x, y = rx * math.cos(a), ry * math.sin(a)
        n = norm((math.cos(a) / rx, math.sin(a) / ry, 0))
        pts.append((x, y, n[0], n[1]))
    return pts


# ---------------------------------------------------------------- blade
# Lens profile (one quadrant, x >= 0, y >= 0), mirrored into a 16-point CCW ring.
BLADE_Q = [(0.66, 0.0), (0.625, 0.115), (0.50, 0.215), (0.28, 0.268), (0.0, 0.282)]


def blade_profile(sx, sy):
    quad = BLADE_Q
    ring = quad[:-1] + [(-x, y) for x, y in reversed(quad[1:])] + \
        [(-x, -y) for x, y in quad[:-1]] + [(x, -y) for x, y in reversed(quad[1:])]
    pts = []
    n = len(ring)
    for i, (x, y) in enumerate(ring):
        px, py = ring[i - 1]
        qx, qy = ring[(i + 1) % n]
        tx, ty = qx - px, qy - py                   # tangent (CCW) -> outward normal (ty, -tx)
        nx, ny = ty / max(sx, 1e-6), -tx / max(sy, 1e-6)
        nn = norm((nx, ny, 0))
        pts.append((x * sx, y * sy, nn[0], nn[1]))
    return pts


Z_BLADE0, Z_TIP = 1.50, 8.38


def blade_uv(x, y, z, _wrap, _i):
    u = 0.02 + 0.46 * (x / 0.66 + 1) / 2
    v = 0.98 - (z - Z_BLADE0) / (Z_TIP - Z_BLADE0) * 0.96
    return (u, v)


TIP_START = 6.80
rings = [(z, blade_profile(1.0, 1.0)) for z in (Z_BLADE0, 3.3, 5.1, TIP_START)]
for f in (0.3, 0.55, 0.75, 0.9):           # ogive tip: a rounded point like the icon's
    width = math.cos(f * math.pi / 2) ** 0.7
    rings.append((TIP_START + (Z_TIP - TIP_START) * f, blade_profile(width, 0.5 + 0.5 * width)))
loft(rings, blade_uv, closed_tip=(Z_TIP, (0, 0, 1), blade_uv(0, 0, Z_TIP, None, 0)))

# ---------------------------------------------------------------- guard (flat-shaded bevelled block)
GX, GY, GZ0, GZ1, BEV = 1.20, 0.40, 1.14, 1.66, 0.11


def octagon(hx, hy, c):
    return [(hx, -hy + c), (hx, hy - c), (hx - c, hy), (-hx + c, hy), (-hx, hy - c), (-hx, -hy + c),
            (-hx + c, -hy), (hx - c, -hy)]


def guard_uv(x, y, z, cap=False):
    u = 0.52 + 0.46 * (x / GX + 1) / 2
    if cap:
        v = 0.02 + 0.20 * (y / GY + 1) / 2
    else:
        v = 0.02 + 0.20 * (GZ1 - z) / (GZ1 - GZ0)
    return (u, min(0.22, max(0.02, v)))


g_rings = [(GZ0, octagon(GX - BEV, GY - BEV, 0.06)), (GZ0 + BEV, octagon(GX, GY, 0.12)),
           (GZ1 - BEV, octagon(GX, GY, 0.12)), (GZ1, octagon(GX - BEV, GY - BEV, 0.06))]
for r in range(len(g_rings) - 1):
    (z0, p0), (z1, p1) = g_rings[r], g_rings[r + 1]
    for i in range(8):
        j = (i + 1) % 8
        quad = [(p0[i][0], p0[i][1], z0), (p0[j][0], p0[j][1], z0), (p1[j][0], p1[j][1], z1), (p1[i][0], p1[i][1], z1)]
        n = norm(cross(sub(quad[1], quad[0]), sub(quad[3], quad[0])))
        mid = [sum(q[k] for q in quad) / 4 for k in range(3)]
        if n[0] * mid[0] + n[1] * mid[1] + n[2] * (mid[2] - (GZ0 + GZ1) / 2) < 0:
            n = tuple(-c for c in n)
        ids = [add_vertex(q, n, guard_uv(*q)) for q in quad]
        add_tri(ids[0], ids[1], ids[2])
        add_tri(ids[0], ids[2], ids[3])
for z, pts, nz in ((GZ0, g_rings[0][1], -1), (GZ1, g_rings[-1][1], 1)):
    centre = add_vertex((0.0, 0.0, z), (0, 0, nz), guard_uv(0, 0, z, cap=True))
    ids = [add_vertex((x, y, z), (0, 0, nz), guard_uv(x, y, z, cap=True)) for x, y in pts]
    for i in range(8):
        add_tri(centre, ids[i], ids[(i + 1) % 8])

# ---------------------------------------------------------------- grip (wrapped, round)
GRIP_Z0, GRIP_Z1, GRIP_SEG = -1.16, 1.24, 10


def grip_uv(x, y, z, wrap, _i):
    return (0.52 + 0.46 * wrap, 0.27 + 0.34 * (GRIP_Z1 - z) / (GRIP_Z1 - GRIP_Z0))


grip_rings = [(GRIP_Z0, ellipse_ring(0.285, 0.265, GRIP_SEG, math.pi / 2)),
              (0.04, ellipse_ring(0.300, 0.280, GRIP_SEG, math.pi / 2)),
              (GRIP_Z1, ellipse_ring(0.285, 0.265, GRIP_SEG, math.pi / 2))]
loft(grip_rings, grip_uv, wrap_seam=True)

# ---------------------------------------------------------------- pommel (ball)
PZ, PR, PRZ, P_SEG = -1.52, 0.43, 0.40, 10


def pommel_uv(x, y, z, wrap, _i):
    return (0.52 + 0.46 * wrap, 0.66 + 0.32 * (PZ + PRZ - z) / (2 * PRZ))


p_rings = []
for deg in (-72, -45, -15, 15, 45, 72):
    a = math.radians(deg)
    p_rings.append((PZ + PRZ * math.sin(a), ellipse_ring(PR * math.cos(a), PR * math.cos(a), P_SEG, math.pi / 2)))
# normals of a sphere: overwrite after lofting
first = len(verts)
loft(p_rings, pommel_uv, closed_tip=(PZ + PRZ, (0, 0, 1), pommel_uv(0, 0, PZ + PRZ, 0.5, 0)), wrap_seam=True)
bottom = add_vertex((0.0, 0.0, PZ - PRZ), (0, 0, -1), pommel_uv(0, 0, PZ - PRZ, 0.5, 0))
for i in range(P_SEG):
    add_tri(first + i + 1, first + i, bottom)
for v in verts[first:]:
    x, y, z = v['position']
    v['normal'] = norm((x / PR, y / PR, (z - PZ) / PRZ))

# ---------------------------------------------------------------- outline normals
groups = {}
for v in verts:
    key = tuple(round(c, 4) for c in v['position'])
    groups.setdefault(key, []).append(v)
for members in groups.values():
    n = norm([sum(m['normal'][k] for m in members) for k in range(3)])
    for m in members:
        m['outline_normal'] = n


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('sword_mesh.json')
    r6 = lambda vals: [round(c, 6) for c in vals]
    doc = dict(format='fl-mesh-v1', notes='Wooden Sword mesh; generated by build_mesh.py. Attributes per vertex: '
               'position, normal, uv0, outline_normal. Triangles CCW.',
               vertices=[dict(position=r6(v['position']), normal=r6(v['normal']), uv0=r6(v['uv']),
                              outline_normal=r6(v['outline_normal'])) for v in verts],
               triangles=[list(t) for t in tris])
    target.write_text(json.dumps(doc, separators=(',', ':')) + '\n')
    print(f'wrote {target}: {len(verts)} vertices, {len(tris)} triangles')


if __name__ == '__main__':
    main()
