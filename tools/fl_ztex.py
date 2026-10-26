#!/usr/bin/env python3
"""Fantasy Life ZTEX textures: decode to PNG, encode from PNG (3DS PICA200 formats).

Standard library only. Layout follows the Ohana3DS Rebirth ZTEX loader and Kuriimu2's
Ztex load/save (read as specifications; see docs/modding-guide.md):

    0x00 'ztex'  u16 image_count  u16 flags (bit0 extended entries, bit1 extra table)
    [flags&2]   u32 extra_count
    per image   [flags&1: u32 0] name[0x40] u32 crc32(name) u32 offset u32 0
                u32 data_size u16 width u16 height u8 mip_count u8 format u16 0x00ff
    [flags&2]   extra_count * 8 bytes (kept as-is)
    image data, each image (all mips) aligned to 0x80

Pixels are stored in 8x8 Morton-ordered tiles, tile rows in storage order. PNGs show the
image the way the game displays it (checked against in-game screenshots: the item icons'
handles are bottom-left): the first stored row is the TOP row of the PNG. In this
orientation model UVs follow the usual convention, v = 0 at the bottom row of the PNG.

    python3 -I tools/fl_ztex.py info  <file.ztex>
    python3 -I tools/fl_ztex.py decode <file.ztex> <out.png> [--image N] [--mip N]
    python3 -I tools/fl_ztex.py encode <in.png> <out.ztex> --name NAME [--format etc1a4] [--mips N]
    python3 -I tools/fl_ztex.py replace <file.ztex> <in.png> <out.ztex> [--image N]
"""
import argparse
import struct
import sys
import zlib
from pathlib import Path

FORMATS = {  # id: (name, bits per pixel)
    0x01: ('rgb565', 16), 0x03: ('rgb8', 24), 0x05: ('rgba4', 16), 0x07: ('rgba5551', 16),
    0x09: ('rgba8', 32), 0x0b: ('l4', 4), 0x0d: ('la4', 8), 0x11: ('a8', 8), 0x13: ('l8', 8),
    0x15: ('la8', 16), 0x18: ('etc1', 4), 0x19: ('etc1a4', 8)}
FORMAT_IDS = {name: id_ for id_, (name, _) in FORMATS.items()}


class ZtexError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ZtexError(message)


# --------------------------------------------------------------------------- PNG I/O
def png_encode(width, height, rgba):
    """8-bit RGBA rows (bytes, top-down) as PNG file bytes."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    stride = width * 4
    raw = b''.join(b'\0' + bytes(rgba[y * stride:(y + 1) * stride]) for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def png_write(path, width, height, rgba):
    """Write 8-bit RGBA rows (bytes, top-down) as PNG."""
    Path(path).write_bytes(png_encode(width, height, rgba))


def png_read(path):
    """Read an 8-bit non-interlaced PNG (grey, grey+alpha, RGB, RGBA or palette) as RGBA."""
    return png_decode(Path(path).read_bytes(), path)


def png_decode(data, path='PNG data'):
    """PNG file bytes -> (width, height, rgba); see png_read."""
    require(data[:8] == b'\x89PNG\r\n\x1a\n', f'{path}: not a PNG')
    pos, idat, palette, trns = 8, bytearray(), None, None
    while pos < len(data):
        size, kind = struct.unpack_from('>I4s', data, pos)
        body = data[pos + 8:pos + 8 + size]
        pos += 12 + size
        if kind == b'IHDR':
            width, height, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', body)
            require(depth == 8 and interlace == 0, f'{path}: only 8-bit non-interlaced PNG is supported')
        elif kind == b'PLTE':
            palette = body
        elif kind == b'tRNS':
            trns = body
        elif kind == b'IDAT':
            idat.extend(body)
        elif kind == b'IEND':
            break
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    rows, prev, pos = [], bytearray(stride), 0
    for _ in range(height):
        kind, line = raw[pos], bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    out = bytearray()
    for line in rows:
        for x in range(width):
            px = line[x * channels:(x + 1) * channels]
            if ctype == 6:
                out.extend(px)
            elif ctype == 2:
                out.extend(px + b'\xff')
            elif ctype == 0:
                out.extend((px[0], px[0], px[0], 255))
            elif ctype == 4:
                out.extend((px[0], px[0], px[0], px[1]))
            else:
                i = px[0]
                out.extend(palette[i * 3:i * 3 + 3] + bytes([trns[i] if trns and i < len(trns) else 255]))
    return width, height, bytes(out)


# --------------------------------------------------------------------------- tiling
def _morton8():
    order = []
    for i in range(64):
        x = (i & 1) | ((i >> 1) & 2) | ((i >> 2) & 4)
        y = ((i >> 1) & 1) | ((i >> 2) & 2) | ((i >> 3) & 4)
        order.append((x, y))
    return order


MORTON = _morton8()


def _tiled_positions(width, height):
    """Yield (x, y) in storage order; y counted from the TOP of the returned image."""
    for ty in range(0, height, 8):
        for tx in range(0, width, 8):
            for x, y in MORTON:
                yield tx + x, ty + y


def _decode_pixel(fmt, data, i):
    """Return (r, g, b, a) of pixel i (in storage order) for non-ETC formats."""
    if fmt == 'rgba8':
        a, b, g, r = data[i * 4:i * 4 + 4]
        return r, g, b, a
    if fmt == 'rgb8':
        b, g, r = data[i * 3:i * 3 + 3]
        return r, g, b, 255
    if fmt in ('rgb565', 'rgba4', 'rgba5551', 'la8'):
        v = data[i * 2] | data[i * 2 + 1] << 8
        if fmt == 'rgb565':
            r, g, b = v >> 11, (v >> 5) & 63, v & 31
            return r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2, 255
        if fmt == 'rgba4':
            return (v >> 12) * 17, ((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17
        if fmt == 'rgba5551':
            r, g, b = v >> 11, (v >> 6) & 31, (v >> 1) & 31
            return r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, 255 if v & 1 else 0
        a, l = data[i * 2], data[i * 2 + 1]
        return l, l, l, a
    if fmt in ('l8', 'a8', 'la4'):
        v = data[i]
        if fmt == 'l8':
            return v, v, v, 255
        if fmt == 'a8':
            return 255, 255, 255, v
        return (v >> 4) * 17, (v >> 4) * 17, (v >> 4) * 17, (v & 15) * 17
    if fmt == 'l4':
        v = (data[i >> 1] >> (4 * (i & 1))) & 15
        return v * 17, v * 17, v * 17, 255
    raise ZtexError(f'unsupported format {fmt}')


def _encode_pixel(fmt, out, r, g, b, a):
    if fmt == 'rgba8':
        out.extend((a, b, g, r))
    elif fmt == 'rgb8':
        out.extend((b, g, r))
    elif fmt == 'rgb565':
        v = ((r * 31 + 127) // 255) << 11 | ((g * 63 + 127) // 255) << 5 | (b * 31 + 127) // 255
        out.extend((v & 255, v >> 8))
    elif fmt == 'rgba4':
        v = ((r + 8) // 17) << 12 | ((g + 8) // 17) << 8 | ((b + 8) // 17) << 4 | (a + 8) // 17
        out.extend((v & 255, v >> 8))
    elif fmt == 'rgba5551':
        v = ((r * 31 + 127) // 255) << 11 | ((g * 31 + 127) // 255) << 6 | ((b * 31 + 127) // 255) << 1 | (a >= 128)
        out.extend((v & 255, v >> 8))
    elif fmt == 'la8':
        out.extend((a, (r * 77 + g * 150 + b * 29) >> 8))
    elif fmt == 'l8':
        out.append((r * 77 + g * 150 + b * 29) >> 8)
    elif fmt == 'a8':
        out.append(a)
    elif fmt == 'la4':
        out.append(((r * 77 + g * 150 + b * 29) >> 8) // 17 << 4 | (a + 8) // 17)
    else:
        raise ZtexError(f'cannot encode format {fmt}')


# --------------------------------------------------------------------------- ETC1
ETC1_TABLES = ((2, 8), (5, 17), (9, 29), (13, 42), (18, 60), (24, 80), (33, 106), (47, 183))


def _clamp(v):
    return 0 if v < 0 else 255 if v > 255 else v


def _etc1_decode_block(word):
    """word: the 64-bit ETC1 block as a big-endian integer. Returns 16 (r,g,b) in [x][y] order (x*4+y)."""
    hi, lo = word >> 32, word & 0xffffffff
    flip, diff = (hi >> 0) & 1, (hi >> 1) & 1
    if diff:
        r1, g1, b1 = hi >> 27 & 31, hi >> 19 & 31, hi >> 11 & 31
        dr, dg, db = hi >> 24 & 7, hi >> 16 & 7, hi >> 8 & 7
        dr, dg, db = (d - 8 if d > 3 else d for d in (dr, dg, db))
        r2, g2, b2 = r1 + dr, g1 + dg, b1 + db
        c1 = tuple(v << 3 | v >> 2 for v in (r1, g1, b1))
        c2 = tuple((v & 31) << 3 | (v & 31) >> 2 for v in (r2, g2, b2))
    else:
        c1 = tuple((hi >> s & 15) * 17 for s in (28, 20, 12))
        c2 = tuple((hi >> s & 15) * 17 for s in (24, 16, 8))
    t1, t2 = hi >> 5 & 7, hi >> 2 & 7
    out = []
    for x in range(4):
        for y in range(4):
            i = x * 4 + y
            second = (y >= 2) if flip else (x >= 2)
            base, table = (c2, t2) if second else (c1, t1)
            msb, lsb = lo >> (16 + i) & 1, lo >> i & 1
            small, large = ETC1_TABLES[table]
            mod = (small, large, -small, -large)[msb << 1 | lsb]
            out.append(tuple(_clamp(c + mod) for c in base))
    return out


def _sub_error(pixels, weights, base, table):
    """Best modifier per pixel for a sub-block; returns (weighted error, [index])."""
    small, large = ETC1_TABLES[table]
    br, bg, bb = base
    cands = [(_clamp(br + m), _clamp(bg + m), _clamp(bb + m)) for m in (small, large, -small, -large)]
    total, picks = 0.0, []
    for (r, g, b), w in zip(pixels, weights):
        errors = [(r - cr) * (r - cr) * 3 + (g - cg) * (g - cg) * 6 + (b - cb) * (b - cb) for cr, cg, cb in cands]
        e = min(errors)
        total += e * w
        picks.append(errors.index(e))
    return total, picks


def _quantise(colour, bits):
    levels = (1 << bits) - 1
    return tuple(min(levels, max(0, round(c * levels / 255))) for c in colour)


def _expand(q, bits):
    return tuple(v * 17 for v in q) if bits == 4 else tuple(v << 3 | v >> 2 for v in q)


def _best_sub(pixels, weights, bits, allowed=None):
    """Best (error, quantised base, table, picks) for one 2x4 sub-block.

    Per table: start from the weighted mean, refine the base by least squares on the chosen
    modifiers, then search the +-1 neighbourhood of the two best candidates. `allowed`
    optionally restricts the base (per channel min/max) for the differential partner.
    """
    def ok(q):
        return allowed is None or all(lo <= v <= hi for v, (lo, hi) in zip(q, allowed))

    def clamp_q(q):
        if allowed is None:
            return q
        return tuple(min(hi, max(lo, v)) for v, (lo, hi) in zip(q, allowed))

    wsum = sum(weights) or 1e-9
    mean = [sum(p[c] * w for p, w in zip(pixels, weights)) / wsum for c in range(3)]
    levels = (1 << bits) - 1
    results = {}
    for table in range(8):
        small, large = ETC1_TABLES[table]
        mods = (small, large, -small, -large)
        q = clamp_q(_quantise(mean, bits))
        for _ in range(3):
            err, picks = _sub_error(pixels, weights, _expand(q, bits), table)
            results[(q, table)] = (err, q, table, picks)
            target = [sum((p[c] - mods[k]) * w for p, w, k in zip(pixels, weights, picks)) / wsum for c in range(3)]
            nq = clamp_q(_quantise(target, bits))
            if nq == q:
                break
            q = nq
        err, picks = _sub_error(pixels, weights, _expand(q, bits), table)
        results[(q, table)] = (err, q, table, picks)
    ranked = sorted(results.values(), key=lambda r: r[0])
    for err, q, table, _ in ranked[:2]:
        for dr in (-1, 0, 1):
            for dg in (-1, 0, 1):
                for db in (-1, 0, 1):
                    n = (q[0] + dr, q[1] + dg, q[2] + db)
                    if (n, table) in results or not all(0 <= v <= levels for v in n) or not ok(n):
                        continue
                    e, picks = _sub_error(pixels, weights, _expand(n, bits), table)
                    results[(n, table)] = (e, n, table, picks)
    return min(results.values(), key=lambda r: r[0])


def _etc1_encode_block(block, weights):
    """block: 16 (r,g,b) in [x*4+y] order. Returns the 64-bit block as an integer."""
    best = None
    for flip in (0, 1):
        idx1 = [x * 4 + y for x in range(4) for y in range(4) if ((y < 2) if flip else (x < 2))]
        idx2 = [x * 4 + y for x in range(4) for y in range(4) if not ((y < 2) if flip else (x < 2))]
        p1, w1 = [block[i] for i in idx1], [weights[i] for i in idx1]
        p2, w2 = [block[i] for i in idx2], [weights[i] for i in idx2]
        # individual mode, 4-bit bases
        s1, s2 = _best_sub(p1, w1, 4), _best_sub(p2, w2, 4)
        options = [(s1[0] + s2[0], 0, s1, s2)]
        # differential mode: 5-bit bases, second = first + delta, delta in [-4, 3]
        d1, d2 = _best_sub(p1, w1, 5), _best_sub(p2, w2, 5)
        if all(-4 <= y - x <= 3 for x, y in zip(d1[1], d2[1])):
            options.append((d1[0] + d2[0], 1, d1, d2))
        else:
            near2 = _best_sub(p2, w2, 5, [(max(0, v - 4), min(31, v + 3)) for v in d1[1]])
            near1 = _best_sub(p1, w1, 5, [(max(0, v - 3), min(31, v + 4)) for v in d2[1]])
            options.append((d1[0] + near2[0], 1, d1, near2))
            options.append((near1[0] + d2[0], 1, near1, d2))
        for err, diff, a, b in options:
            if best is None or err < best[0]:
                best = (err, flip, diff, a, b, idx1, idx2)
    _, flip, diff, a, b, idx1, idx2 = best
    if diff:
        require(all(-4 <= y - x <= 3 for x, y in zip(a[1], b[1])), 'internal ETC1 delta error')
        hi = a[1][0] << 27 | a[1][1] << 19 | a[1][2] << 11
        hi |= ((b[1][0] - a[1][0]) & 7) << 24 | ((b[1][1] - a[1][1]) & 7) << 16 | ((b[1][2] - a[1][2]) & 7) << 8
    else:
        hi = a[1][0] << 28 | b[1][0] << 24 | a[1][1] << 20 | b[1][1] << 16 | a[1][2] << 12 | b[1][2] << 8
    hi |= a[2] << 5 | b[2] << 2 | diff << 1 | flip
    lo = 0
    for idx, sub in ((idx1, a), (idx2, b)):
        for i, pick in zip(idx, sub[3]):
            lo |= (pick >> 1) << (16 + i) | (pick & 1) << i
    return hi << 32 | lo


def _etc_blocks(width, height):
    """(block_x, block_y) in storage order: 8x8 tiles, each with 2x2 blocks in Z order."""
    for ty in range(0, height // 4, 2):
        for tx in range(0, width // 4, 2):
            for dy, dx in ((0, 0), (0, 1), (1, 0), (1, 1)):
                yield tx + dx, ty + dy


def _decode_etc(data, width, height, alpha):
    out = bytearray(width * height * 4)
    pos = 0
    for bx, by in _etc_blocks(width, height):
        if alpha:
            amask = int.from_bytes(data[pos:pos + 8], 'little')
            pos += 8
        word = int.from_bytes(data[pos:pos + 8], 'little')
        pos += 8
        colours = _etc1_decode_block(word)
        for x in range(4):
            for y in range(4):
                i = x * 4 + y
                px, py = bx * 4 + x, by * 4 + y
                a = (amask >> (4 * i) & 15) * 17 if alpha else 255
                o = (py * width + px) * 4
                out[o:o + 4] = bytes(colours[i] + (a,))
    return bytes(out)


def _encode_etc(rgba, width, height, alpha):
    out = bytearray()
    for bx, by in _etc_blocks(width, height):
        block, weights, amask = [], [], 0
        for x in range(4):
            for y in range(4):
                px, py = bx * 4 + x, by * 4 + y
                o = (py * width + px) * 4
                r, g, b, a = rgba[o:o + 4]
                block.append((r, g, b))
                # Colour under (nearly) transparent texels does not matter: weight by alpha.
                weights.append((a + 8) / 263 if alpha else 1)
                amask |= ((a + 8) // 17) << (4 * (x * 4 + y))
        if alpha:
            out.extend(amask.to_bytes(8, 'little'))
        out.extend(_etc1_encode_block(block, weights).to_bytes(8, 'little'))
    return bytes(out)


def decode_pixels(data, fmt, width, height):
    """Raw PICA200 texture data -> top-down RGBA bytes."""
    if fmt in ('etc1', 'etc1a4'):
        return _decode_etc(data, width, height, fmt == 'etc1a4')
    out = bytearray(width * height * 4)
    for i, (x, y) in enumerate(_tiled_positions(width, height)):
        o = (y * width + x) * 4
        out[o:o + 4] = bytes(_decode_pixel(fmt, data, i))
    return bytes(out)


def encode_pixels(rgba, fmt, width, height):
    """Top-down RGBA bytes -> raw PICA200 texture data."""
    require(width % 8 == 0 and height % 8 == 0, 'texture size must be a multiple of 8')
    if fmt in ('etc1', 'etc1a4'):
        return _encode_etc(rgba, width, height, fmt == 'etc1a4')
    out = bytearray()
    if fmt == 'l4':
        values = [rgba[(y * width + x) * 4:(y * width + x) * 4 + 3] for x, y in _tiled_positions(width, height)]
        lum = [((r * 77 + g * 150 + b * 29) >> 8) // 17 for r, g, b in values]
        return bytes(lum[i] | lum[i + 1] << 4 for i in range(0, len(lum), 2))
    for x, y in _tiled_positions(width, height):
        o = (y * width + x) * 4
        _encode_pixel(fmt, out, *rgba[o:o + 4])
    return bytes(out)


def downsample(rgba, width, height):
    """2x2 box filter (alpha-weighted colour) for the next mip level."""
    w, h = width // 2, height // 2
    out = bytearray(w * h * 4)
    for y in range(h):
        for x in range(w):
            acc, asum = [0, 0, 0], 0
            for dy in (0, 1):
                for dx in (0, 1):
                    o = ((2 * y + dy) * width + 2 * x + dx) * 4
                    a = rgba[o + 3]
                    asum += a
                    for c in range(3):
                        acc[c] += rgba[o + c] * (a + 1)
            wsum = asum + 4
            o = (y * w + x) * 4
            out[o:o + 4] = bytes([round(acc[0] / wsum), round(acc[1] / wsum), round(acc[2] / wsum), round(asum / 4)])
    return bytes(out)


# --------------------------------------------------------------------------- container
def parse(raw):
    require(raw[:4] == b'ztex', 'not a ztex file')
    count, flags = struct.unpack_from('<HH', raw, 4)
    pos = 8
    extra_count = 0
    if flags & 2:
        extra_count, = struct.unpack_from('<I', raw, pos)
        pos += 4
    images = []
    for _ in range(count):
        if flags & 1:
            pos += 4
        name = raw[pos:pos + 0x40].split(b'\0', 1)[0].decode('ascii')
        crc, offset, zero, size, width, height, mips, fmt, tail = struct.unpack_from('<4I2H2BH', raw, pos + 0x40)
        require(fmt in FORMATS, f'unknown ztex format {fmt:#x}')
        require(offset + size <= len(raw), 'image data out of bounds')
        images.append(dict(name=name, crc32=crc, offset=offset, zero=zero, size=size, width=width,
                           height=height, mips=mips, format=FORMATS[fmt][0], tail=tail, entry=pos))
        pos += 0x58
    extra = raw[pos:pos + 8 * extra_count]
    return dict(flags=flags, images=images, extra=extra)


def mip_sizes(image):
    bpp = FORMATS[FORMAT_IDS[image['format']]][1]
    w, h, out = image['width'], image['height'], []
    for _ in range(image['mips']):
        out.append((w, h, w * h * bpp // 8))
        w, h = max(8, w // 2), max(8, h // 2)
    return out


def decode(raw, index=0, mip=0):
    """Return (width, height, rgba) of one image/mip level."""
    image = parse(raw)['images'][index]
    pos = image['offset']
    for level, (w, h, size) in enumerate(mip_sizes(image)):
        if level == mip:
            return w, h, decode_pixels(raw[pos:pos + size], image['format'], w, h)
        pos += size
    raise ZtexError(f'mip {mip} not present')


def image_data(rgba, width, height, fmt, mips):
    data = bytearray()
    for level in range(mips):
        data.extend(encode_pixels(rgba, fmt, width, height))
        if level + 1 < mips:
            rgba, width, height = downsample(rgba, width, height), width // 2, height // 2
    return bytes(data)


def build(images, flags=2, extra=b''):
    """images: list of dict(name, width, height, format, mips, data). Returns ztex bytes."""
    head = 8 + (4 if flags & 2 else 0)
    table = head + len(images) * (0x58 + (4 if flags & 1 else 0))
    pos = (table + len(extra) + 0x7f) & ~0x7f
    out = bytearray(pos)
    out[:8] = b'ztex' + struct.pack('<HH', len(images), flags)
    if flags & 2:
        struct.pack_into('<I', out, 8, len(extra) // 8)
    entry = head
    for image in images:
        name = image['name'].encode('ascii')
        require(len(name) < 0x40, 'texture name too long')
        out.extend(b'\0' * (pos - len(out)))
        if flags & 1:
            entry += 4
        out[entry:entry + 0x40] = name.ljust(0x40, b'\0')
        struct.pack_into('<4I2H2BH', out, entry + 0x40, zlib.crc32(name), pos, 0, len(image['data']),
                         image['width'], image['height'], image['mips'], FORMAT_IDS[image['format']], 0xff)
        out.extend(image['data'])
        entry += 0x58
        pos = (len(out) + 0x7f) & ~0x7f
    out[table:table + len(extra)] = extra
    return bytes(out)


def replace_image(raw, index, rgba, width, height):
    """Re-encode one image of an existing ztex (same name, format, mip count)."""
    info = parse(raw)
    images = []
    for i, image in enumerate(info['images']):
        start, size = image['offset'], sum(s for _, _, s in mip_sizes(image))
        data = raw[start:start + size]
        w, h = image['width'], image['height']
        if i == index:
            require((width, height) == (w, h), f'image must be {w}x{h}')
            data = image_data(rgba, w, h, image['format'], image['mips'])
        images.append(dict(name=image['name'], width=w, height=h, format=image['format'],
                           mips=image['mips'], data=data))
    return build(images, info['flags'], info['extra'])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    c = commands.add_parser('info')
    c.add_argument('ztex', type=Path)
    c = commands.add_parser('decode')
    c.add_argument('ztex', type=Path)
    c.add_argument('png', type=Path)
    c.add_argument('--image', type=int, default=0)
    c.add_argument('--mip', type=int, default=0)
    c = commands.add_parser('encode')
    c.add_argument('png', type=Path)
    c.add_argument('ztex', type=Path)
    c.add_argument('--name', required=True)
    c.add_argument('--format', default='etc1a4', choices=sorted(FORMAT_IDS))
    c.add_argument('--mips', type=int, default=1)
    c = commands.add_parser('replace')
    c.add_argument('ztex', type=Path)
    c.add_argument('png', type=Path)
    c.add_argument('out', type=Path)
    c.add_argument('--image', type=int, default=0)
    args = parser.parse_args()
    if args.command == 'info':
        info = parse(args.ztex.read_bytes())
        print(f"flags {info['flags']:#x}, {len(info['images'])} image(s), {len(info['extra']) // 8} extra record(s)")
        for image in info['images']:
            print(f"  {image['name']}: {image['width']}x{image['height']} {image['format']}, "
                  f"{image['mips']} mip(s), {image['size']} bytes at {image['offset']:#x}")
    elif args.command == 'decode':
        w, h, rgba = decode(args.ztex.read_bytes(), args.image, args.mip)
        png_write(args.png, w, h, rgba)
    elif args.command == 'encode':
        w, h, rgba = png_read(args.png)
        args.ztex.write_bytes(build([dict(name=args.name, width=w, height=h, format=args.format, mips=args.mips,
                                          data=image_data(rgba, w, h, args.format, args.mips))]))
    else:
        w, h, rgba = png_read(args.png)
        args.out.write_bytes(replace_image(args.ztex.read_bytes(), args.image, rgba, w, h))


if __name__ == '__main__':
    try:
        main()
    except ZtexError as error:
        sys.exit(f'error: {error}')
