#!/usr/bin/env python3
"""Offline previews of the Thistle Wolf from a BUILT overlay (what the game will load).

    python3 -I mods/eastern-plains-enemy/art/make_previews.py extracted/fl_eu/archive \\
        <built overlay folder> docs/assets/eastern-plains-enemy

The monster is resolved like the game does: spawn group 20 of the East plains table ->
monster 274 -> its unit row -> model / texture / battle-parameter resource IDs, reading
each resource from the overlay when it replaces it (named-pack members are taken from
their rebuilt pack) and from the extraction otherwise. Prints a summary (names, stats,
drops, spawn regions) and writes:

    texture-4x.png       the overlay's monster texture, 4x (own art, safe to commit)
and, for local viewing only (they contain the game's wolf model or map; git-ignored):
    model.png            four views of the Thistle Wolf, toon preview (not the game renderer)
    model-large.png      one large three-quarter view
    compare-model.png    Red Wolf (original) next to the Thistle Wolf, same views
    location.png         top-down East Grassy Plains with the new spawn region (magenta)
                         and the Red Wolf regions (red); north is up
Standard library only.
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


ztex, zmdl, archive, scr, fl_map = (load(n) for n in ('fl_ztex', 'fl_zmdl', 'fl_archive', 'fl_scr', 'fl_map'))

SPAWN_TABLE, GROUP, MONSTER = 7291, 20, 274          # 7291: English slot of the East plains groups
MONSTER_NAMES, UNIT_NAMES = 6947, 8713                 # English monster / en-GB unit tables
NAME_SLOTS = list(range(8706, 8714)) + [8719]
LOOT, ITEM_NAMES = 6930, 6800
RED_WOLF_UNIT = 12
MAP_MODEL, MAP_TEXTURES, LAYERS = 10332, 10333, (23053, 23055)
BACKGROUND = (186, 196, 178, 255)
VIEWS = ((0, 10), (-90, 5), (-35, 25), (160, 20))


class Resources:
    def __init__(self, extraction, overlay):
        self.root = Path(extraction)
        manifest = json.loads((self.root / '.fl_archive/manifest.json').read_text())
        self.entries = {e['id']: e for e in manifest['entries']}
        self.overlay = Path(overlay)
        self.manifest = json.loads((self.overlay / 'overlay.json').read_text())
        self.replaced = {r['id']: r for r in self.manifest['resources']}

    def __call__(self, id_):
        """Bytes of a resource as the game loads it with this overlay active."""
        if id_ in self.replaced:
            return archive.decompress_nintendo((self.overlay / self.replaced[id_]['file']).read_bytes())[0]
        entry = self.entries[id_]
        parent = entry.get('parent')
        if parent in self.replaced:
            pack = self(parent)
            member = next(m for m in archive.parse_pack(pack) if m['name'] == entry['path'])
            return archive.span(pack, member['offset'], member['size'])
        return archive.safe_path(self.root, entry['path']).read_bytes()

    def rows(self, id_):
        return scr.dump(self(id_), id_)['sections'][0]['rows']


class Canvas:
    def __init__(self, width, height, colour=BACKGROUND):
        self.w, self.h = width, height
        self.px = bytearray(bytes(colour) * (width * height))

    def paste(self, x0, y0, w, h, rgba, scale=1):
        for y in range(h * scale):
            for x in range(w * scale):
                tx, ty = x0 + x, y0 + y
                if 0 <= tx < self.w and 0 <= ty < self.h:
                    o = ((y // scale) * w + x // scale) * 4
                    a = rgba[o + 3]
                    d = (ty * self.w + tx) * 4
                    for c in range(3):
                        self.px[d + c] = (rgba[o + c] * a + self.px[d + c] * (255 - a)) // 255

    def dot(self, x, y, colour, radius=1):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if 0 <= x + dx < self.w and 0 <= y + dy < self.h:
                    self.px[((y + dy) * self.w + x + dx) * 4:((y + dy) * self.w + x + dx) * 4 + 3] = bytes(colour)

    def ring(self, x, y, r, colour):
        steps = max(16, int(r * 8))
        for k in range(steps):
            a = 2 * math.pi * k / steps
            self.dot(int(x + r * math.cos(a)), int(y + r * math.sin(a)), colour, 0)

    def save(self, path):
        ztex.png_write(path, self.w, self.h, bytes(self.px))


def views(model, texture, size):
    return [zmdl.render(model, texture, size=size, yaw=yaw, pitch=pitch, up='y') for yaw, pitch in VIEWS]


def strip(images, size):
    canvas = Canvas(size * len(images), size)
    for n, rgba in enumerate(images):
        canvas.paste(n * size, 0, size, size, rgba)
    return canvas


def location(res, out):
    """Top-down terrain colours of map 25 with the spawn regions of both normal layers."""
    raw, traw = res(MAP_MODEL), res(MAP_TEXTURES)
    model, names = zmdl.parse(raw), [i['name'] for i in ztex.parse(traw)['images']]
    cache, tris = {}, []
    for mat in model['materials']:
        if any(s in mat['name'] for s in ('cloud', 'light', 'shade', 'shadow')):
            continue
        if mat['texture'] not in cache:
            cache[mat['texture']] = ztex.decode(traw, names.index(mat['texture'])) if mat['texture'] in names else None
        mesh = model['meshes'][mat['mesh']]
        verts = zmdl.vertices(raw, mesh)
        for group in mesh['groups']:
            idx = zmdl.indices(raw, group)
            tris += [(cache[mat['texture']], [verts[i] for i in idx[k:k + 3]]) for k in range(0, len(idx), 3)]
    xs = [v['position'][0] for _, t in tris for v in t]
    zs = [v['position'][2] for _, t in tris for v in t]
    x0, z0 = min(xs), min(zs)
    size = 720
    scale = size / max(max(xs) - x0, max(zs) - z0)
    canvas, height = Canvas(size, size, (30, 30, 40, 255)), [-1e9] * (size * size)
    for tex, t in tris:
        p = [((v['position'][0] - x0) * scale, (v['position'][2] - z0) * scale, v['position'][1], v.get('uv0', (0, 0)))
             for v in t]
        (ax, ay, ah, _), (bx, by, bh, _), (cx, cy, ch, _) = p
        area = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        if abs(area) < 1e-9:
            continue
        for py in range(max(0, int(min(ay, by, cy))), min(size - 1, int(max(ay, by, cy)) + 1) + 1):
            for px in range(max(0, int(min(ax, bx, cx))), min(size - 1, int(max(ax, bx, cx)) + 1) + 1):
                fx, fy = px + 0.5, py + 0.5
                w0 = ((bx - fx) * (cy - fy) - (cx - fx) * (by - fy)) / area
                w1 = ((cx - fx) * (ay - fy) - (ax - fx) * (cy - fy)) / area
                w2 = 1 - w0 - w1
                if min(w0, w1, w2) < 0:
                    continue
                h = w0 * ah + w1 * bh + w2 * ch
                i = py * size + px
                if h > height[i]:
                    height[i] = h
                    colour = (200, 0, 200)
                    if tex:
                        tw, th, texels = tex[:3]
                        u = w0 * p[0][3][0] + w1 * p[1][3][0] + w2 * p[2][3][0]
                        v = w0 * p[0][3][1] + w1 * p[1][3][1] + w2 * p[2][3][1]
                        o = ((int((1 - v % 1) * th) % th) * tw + int((u % 1) * tw) % tw) * 4
                        colour = tuple(texels[o:o + 3])
                    canvas.px[i * 4:i * 4 + 3] = bytes(colour)
    groups = res.rows(SPAWN_TABLE)
    for layer in LAYERS:
        for row in fl_map.dump(res(layer))['rows']:
            if row['type'] != 12:
                continue
            members = groups[row['reference']]['monsters']
            colour = (255, 0, 200) if MONSTER in members else (230, 40, 40) if 11 in members else None
            if colour:
                cx, cy = (row['position'][0] - x0) * scale, (row['position'][2] - z0) * scale
                canvas.ring(cx, cy, row['extent'][0] / 2 * scale, colour)
                for point in row['spawn']['points']:
                    canvas.dot(int((point['position'][0] - x0) * scale), int((point['position'][2] - z0) * scale),
                               colour, 2)
    canvas.save(out)


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    res = Resources(sys.argv[1], sys.argv[2])
    out = Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    group = res.rows(SPAWN_TABLE)[GROUP]
    assert group['monsters'][0] == MONSTER, group
    monster = res.rows(MONSTER_NAMES)[MONSTER]
    unit = monster['unit_index']
    unit_row = res.rows(UNIT_NAMES)[unit]
    model_id, texture_id, battle_id = (unit_row['resources'][k] for k in (0, 2, 8))
    names = [scr.plain(res.rows(id_)[unit]['name']) for id_ in NAME_SLOTS]
    stats = [{k: r[k] for k in ('level_key', 'hp', 'physical_attack', 'physical_defence', 'magic_attack',
                                'magic_defence', 'u_40', 'u_68')} for r in res.rows(battle_id)]
    items = res.rows(ITEM_NAMES)
    loot = [(r['level_key'], [(scr.plain(items[r[f'drop_item_{i}']]['name']), round(r[f'drop_threshold_{i}'] / 2.55))
                              for i in range(5) if r[f'drop_item_{i}'] != 0xffffffff])
            for r in res.rows(LOOT) if r['monster_id'] == MONSTER]
    print(f'group {GROUP}: {group["label"]} monsters {group["monsters"][:2]} weights {group["weights"][:2]}')
    print(f'monster {MONSTER} -> unit {unit}; names (es-419 fr-CA de en es fr it en-GB ja): {names}')
    print(f'model {model_id}, texture {texture_id}, battle parameters {battle_id}: {stats}')
    print(f'drops (level key, [(item, ~percent)]): {loot}')
    model = res(model_id)
    texture = ztex.decode(res(texture_id))
    width, height, rgba = texture[:3]
    canvas = Canvas(width * 4, height * 4)
    canvas.paste(0, 0, width, height, rgba, 4)
    canvas.save(out / 'texture-4x.png')
    strip(views(model, texture, 300), 300).save(out / 'model.png')
    large = Canvas(560, 560)
    large.paste(0, 0, 560, 560, zmdl.render(model, texture, size=560, yaw=-40, pitch=22, up='y'))
    large.save(out / 'model-large.png')
    wolf = res.rows(UNIT_NAMES)[RED_WOLF_UNIT]['resources']
    original = views(res(wolf[0]), ztex.decode(res(wolf[2])), 240)
    custom = views(model, texture, 240)
    compare = Canvas(240 * 4, 480)
    for n, (a, b) in enumerate(zip(original, custom)):
        compare.paste(n * 240, 0, 240, 240, a)
        compare.paste(n * 240, 240, 240, 240, b)
    compare.save(out / 'compare-model.png')
    location(res, out / 'location.png')
    for layer in LAYERS:
        for row in fl_map.dump(res(layer))['rows']:
            if row['type'] == 12 and row['reference'] == GROUP:
                print(f'layer {layer}: region uid {row["uid"]:#010x} at {[round(c, 2) for c in row["position"]]}, '
                      f'{row["spawn"]["count_min"]}-{row["spawn"]["count_max"]} monsters, '
                      f'points {[(p["variant"], p["flags"]) for p in row["spawn"]["points"]]}')


if __name__ == '__main__':
    main()
