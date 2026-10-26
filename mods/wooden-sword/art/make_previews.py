#!/usr/bin/env python3
"""Render offline previews of the Wooden Sword from a BUILT overlay (what the game will load).

    python3 -I mods/wooden-sword/art/make_previews.py extracted/fl_eu/archive \\
        port/build/fl-data/yw2-recomp/mods/fantasylife/wooden-sword docs/assets/wooden-sword

Writes (own art only, safe to commit):
    icon-1x.png, icon-4x.png      item 77's icon resolved exactly like the game (item table ->
                                  icon table -> texture), decoded as displayed, on the menu colour
    model.png                     three views of the overlay model with its overlay texture
    texture-4x.png                the overlay model texture (ETC1), 4x
and, for local comparison only (contain original game art; git-ignored, never commit):
    compare-icons-1x.png, compare-icons-4x.png, compare-model.png
Standard library only.
"""
import json
import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[3]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ztex, zmdl, archive, scr = load('fl_ztex'), load('fl_zmdl'), load('fl_archive'), load('fl_scr')
MENU = (236, 226, 196, 255)      # parchment tone of the item menus
SLATE = (122, 138, 154, 255)

ITEM = 77
ITEM_NAMES_GB, ICONS_GB = 6800, 8694             # en-GB slots of the item and icon tables
MODEL, TEXTURE = 4122, 4123
REFERENCE_ITEMS = [0, 46, 35, 915]               # Squire's Sword, Oak Staff, Oak Bow, Oak Axe
REFERENCE_MODEL = (3804, 3805)                  # Squire's Sword


class Canvas:
    def __init__(self, width, height, colour):
        self.w, self.h = width, height
        self.px = bytearray(bytes(colour) * (width * height))

    def paste(self, x0, y0, w, h, rgba, scale=1):
        for y in range(h * scale):
            for x in range(w * scale):
                tx, ty = x0 + x, y0 + y
                if not (0 <= tx < self.w and 0 <= ty < self.h):
                    continue
                o = ((y // scale) * w + x // scale) * 4
                r, g, b, a = rgba[o:o + 4]
                d = (ty * self.w + tx) * 4
                for c, v in enumerate((r, g, b)):
                    self.px[d + c] = (v * a + self.px[d + c] * (255 - a)) // 255

    def save(self, path):
        ztex.png_write(path, self.w, self.h, bytes(self.px))


def overlay_resource(overlay, id_):
    manifest = json.loads((overlay / 'overlay.json').read_text())
    entry = next(r for r in manifest['resources'] if r['id'] == id_)
    return archive.decompress_nintendo((overlay / entry['file']).read_bytes())[0]


def game_resource(extraction, id_):
    return next((extraction / '_unnamed').glob(f'{id_:05d}_*')).read_bytes()


def resource(extraction, overlay, id_):
    """What the game loads: the overlay's copy if it replaces the resource, else the original."""
    try:
        return overlay_resource(overlay, id_)
    except StopIteration:
        return game_resource(extraction, id_)


def item_icon(extraction, overlay, item):
    """Follow the game's path: item row -> icon_index -> icon table -> icon_id -> ZTEX."""
    items = scr.dump(resource(extraction, overlay, ITEM_NAMES_GB), ITEM_NAMES_GB)['sections'][0]['rows']
    icons = scr.dump(resource(extraction, overlay, ICONS_GB), ICONS_GB)['sections'][0]['rows']
    row = items[item]['icon_index']
    icon_id = icons[row]['icon_id']
    raw = resource(extraction, overlay, icon_id)
    name = ztex.parse(raw)['images'][0]['name']
    w, h, rgba = ztex.decode(raw)
    # item icons are drawn in 64x64 cells; other families (cmd 128x32, ...) would distort
    assert name.startswith('icn_itm') and (w, h) == (64, 64), (row, icon_id, name, w, h)
    print(f'item {item}: icon row {row} -> texture {icon_id} {name} {w}x{h} (item-icon cell)')
    return w, h, rgba


def row(images, scale, colour, pad=8):
    size = 64 * scale
    canvas = Canvas(len(images) * (size + pad) + pad, size + 2 * pad, colour)
    for i, (w, h, rgba) in enumerate(images):
        canvas.paste(pad + i * (size + pad), pad, w, h, rgba, scale)
    return canvas


def renders(model, texture, size=300, views=((0, 0, 0), (35, 18, -25), (80, 8, 0))):
    out = []
    for yaw, pitch, roll in views:
        out.append((size, size, zmdl.render(model, texture, size, yaw, pitch, roll, outline=0.06)))
    return out


def main():
    extraction, overlay, target = (Path(p) for p in sys.argv[1:4])
    target.mkdir(parents=True, exist_ok=True)
    icon = item_icon(extraction, overlay, ITEM)
    for scale in (1, 4):
        row([icon], scale, MENU).save(target / f'icon-{scale}x.png')
    model = overlay_resource(overlay, MODEL)
    tex_raw = overlay_resource(overlay, TEXTURE)
    names = [i['name'] for i in ztex.parse(tex_raw)['images']]
    wanted = zmdl.parse(model)['materials'][0]['texture']
    texture = ztex.decode(tex_raw, names.index(wanted) if wanted in names else 0)
    views = renders(model, texture)
    canvas = Canvas(3 * 300 + 4 * 8, 300 + 16, SLATE)
    for i, (w, h, rgba) in enumerate(views):
        canvas.paste(8 + i * 308, 8, w, h, rgba)
    canvas.save(target / 'model.png')
    tw, th, trgba = texture
    canvas = Canvas(tw * 4, th * 4, SLATE)
    canvas.paste(0, 0, tw, th, trgba, 4)
    canvas.save(target / 'texture-4x.png')
    # local-only comparisons with original game art
    originals = [item_icon(extraction, overlay, i) for i in REFERENCE_ITEMS]
    for scale in (1, 4):
        row([originals[0], icon] + originals[1:], scale, MENU).save(target / f'compare-icons-{scale}x.png')
    ref_model = game_resource(extraction, REFERENCE_MODEL[0])
    ref_tex_raw = game_resource(extraction, REFERENCE_MODEL[1])
    ref_names = [i['name'] for i in ztex.parse(ref_tex_raw)['images']]
    ref_tex = ztex.decode(ref_tex_raw, ref_names.index(zmdl.parse(ref_model)['materials'][0]['texture']))
    pair = renders(ref_model, ref_tex, views=((35, 18, -25),)) + renders(model, texture, views=((35, 18, -25),))
    canvas = Canvas(2 * 300 + 3 * 8, 300 + 16, SLATE)
    for i, (w, h, rgba) in enumerate(pair):
        canvas.paste(8 + i * 308, 8, w, h, rgba)
    canvas.save(target / 'compare-model.png')
    (target / '.gitignore').write_text('# Contain original game art: local only, never commit.\ncompare-*.png\ningame-*.png\n')
    print(f'wrote previews to {target}')


if __name__ == '__main__':
    main()
