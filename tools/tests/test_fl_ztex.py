"""ZTEX / PICA200 texture codec tests. Synthetic data; real-file checks only if an extraction exists."""
import importlib.util
import math
import os
from pathlib import Path
import random
import struct
import tempfile
import unittest
import zlib

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location('fl_ztex', ROOT / 'tools' / 'fl_ztex.py')
ztex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ztex)

EXTRACTION = Path(os.environ.get('FL_EU_ARCHIVE', ROOT / 'extracted/fl_eu/archive')) / '_unnamed'


def image(width, height, fn):
    out = bytearray()
    for y in range(height):
        for x in range(width):
            out.extend(fn(x, y))
    return bytes(out)


def psnr(a, b, opaque_only=True):
    se = n = 0
    for i in range(0, len(a), 4):
        if opaque_only and a[i + 3] < 128:
            continue
        se += sum((a[i + c] - b[i + c]) ** 2 for c in range(3))
        n += 3
    return 99.0 if se == 0 else 10 * math.log10(255 ** 2 / (se / n))


class Pixels(unittest.TestCase):
    def test_png_round_trip(self):
        rgba = image(13, 7, lambda x, y: (x * 19 % 256, y * 37 % 256, (x * y) % 256, (x + y) * 11 % 256))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'a.png'
            ztex.png_write(path, 13, 7, rgba)
            self.assertEqual(ztex.png_read(path), (13, 7, rgba))

    def test_exact_formats_round_trip(self):
        rng = random.Random(4)
        quant = {  # values each format stores exactly
            'rgba8': lambda: (rng.randrange(256), rng.randrange(256), rng.randrange(256), rng.randrange(256)),
            'rgb8': lambda: (rng.randrange(256), rng.randrange(256), rng.randrange(256), 255),
            'rgba4': lambda: tuple(rng.randrange(16) * 17 for _ in range(4)),
            'rgb565': lambda: ((lambda r, g, b: (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2, 255))(
                rng.randrange(32), rng.randrange(64), rng.randrange(32))),
            'rgba5551': lambda: ((lambda r, g, b, a: (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, a * 255))(
                rng.randrange(32), rng.randrange(32), rng.randrange(32), rng.randrange(2))),
            'a8': lambda: (255, 255, 255, rng.randrange(256)),
        }
        for fmt, value in quant.items():
            with self.subTest(fmt=fmt):
                rgba = image(16, 8, lambda x, y: value())
                data = ztex.encode_pixels(rgba, fmt, 16, 8)
                self.assertEqual(len(data), 16 * 8 * ztex.FORMATS[ztex.FORMAT_IDS[fmt]][1] // 8)
                self.assertEqual(ztex.decode_pixels(data, fmt, 16, 8), rgba)

    def test_tiles_are_morton_ordered_in_display_orientation(self):
        rgba = image(16, 8, lambda x, y: (x, y, 0, 255))
        data = ztex.encode_pixels(rgba, 'rgba8', 16, 8)
        pixel = lambda i: struct.unpack_from('4B', data, 4 * i)[:0:-1][:2]  # stored A, B, G, R -> (R, G)
        self.assertEqual(pixel(0), (0, 0))      # top-left pixel of the displayed image first
        self.assertEqual(pixel(1), (1, 0))      # then x+1
        self.assertEqual(pixel(2), (0, 1))      # then the next row (Z order)
        self.assertEqual(pixel(63), (7, 7))
        self.assertEqual(pixel(64), (8, 0))     # second 8x8 tile, left to right

    def test_etc1_known_block(self):
        # individual mode, both sub-blocks base 0x8 (136), table 0, all modifiers index 0 (+2)
        word = (0x88 << 56 | 0x88 << 48 | 0x88 << 40) | 0
        self.assertEqual(set(ztex._etc1_decode_block(word)), {(138, 138, 138)})
        # differential mode with a negative delta in the second sub-block
        word = (16 << 59 | 7 << 56 | 16 << 51 | 16 << 43 | 0b10 << 32)
        colours = ztex._etc1_decode_block(word)
        self.assertEqual(colours[0], (_clamp5(16) + 2,) * 1 + (_clamp5(16) + 2, _clamp5(16) + 2))
        self.assertEqual(colours[15], (_clamp5(15) + 2, _clamp5(16) + 2, _clamp5(16) + 2))

    def test_etc1_encoder_quality_and_alpha(self):
        rgba = image(32, 32, lambda x, y: (40 + x * 6, 200 - y * 5, 90 + (x ^ y) % 7 * 3, (x * 8) % 256))
        for fmt in ('etc1', 'etc1a4'):
            with self.subTest(fmt=fmt):
                data = ztex.encode_pixels(rgba, fmt, 32, 32)
                self.assertEqual(len(data), 32 * 32 // (2 if fmt == 'etc1' else 1))
                back = ztex.decode_pixels(data, fmt, 32, 32)
                self.assertGreater(psnr(rgba, back, opaque_only=False), 33)
                if fmt == 'etc1a4':
                    self.assertTrue(all(back[i + 3] == (rgba[i + 3] + 8) // 17 * 17 for i in range(0, len(rgba), 4)))
                # re-encoding decoded ETC1 data is (nearly) lossless
                again = ztex.decode_pixels(ztex.encode_pixels(back, fmt, 32, 32), fmt, 32, 32)
                self.assertGreater(psnr(back, again, opaque_only=False), 45)

    def test_flat_colours_are_exact(self):
        for colour in ((0, 0, 0, 255), (255, 255, 255, 255), (136, 68, 34, 255)):
            rgba = image(8, 8, lambda x, y: colour)
            back = ztex.decode_pixels(ztex.encode_pixels(rgba, 'etc1', 8, 8), 'etc1', 8, 8)
            self.assertLess(max(abs(a - b) for a, b in zip(rgba, back)), 3)


def _clamp5(v):
    return v << 3 | v >> 2


class Container(unittest.TestCase):
    def test_build_parse_decode_with_extra_records_and_mips(self):
        rgba = image(16, 16, lambda x, y: (x * 16, y * 16, 128, 255))
        extra = bytes.fromhex('ffffffff03000000000000ff03000000')
        raw = ztex.build([dict(name='tex_a', width=16, height=16, format='rgba8', mips=2,
                               data=ztex.image_data(rgba, 16, 16, 'rgba8', 2)),
                          dict(name='tex_b', width=8, height=8, format='rgb565', mips=1,
                               data=ztex.image_data(rgba[:8 * 8 * 4], 8, 8, 'rgb565', 1))], flags=2, extra=extra)
        info = ztex.parse(raw)
        self.assertEqual([i['name'] for i in info['images']], ['tex_a', 'tex_b'])
        self.assertEqual(info['extra'], extra)
        self.assertEqual(info['images'][0]['crc32'], zlib.crc32(b'tex_a'))
        self.assertTrue(all(i['offset'] % 0x80 == 0 for i in info['images']))
        self.assertEqual(ztex.decode(raw, 0), (16, 16, rgba))
        w, h, mip = ztex.decode(raw, 0, mip=1)
        self.assertEqual((w, h, len(mip)), (8, 8, 8 * 8 * 4))
        # replace keeps names/format/extras; a size change is rejected
        other = image(16, 16, lambda x, y: (255 - x * 16, 0, y * 16, 255))
        replaced = ztex.replace_image(raw, 0, other, 16, 16)
        self.assertEqual(ztex.decode(replaced, 0), (16, 16, other))
        self.assertEqual(ztex.parse(replaced)['extra'], extra)
        self.assertEqual(ztex.decode(replaced, 1), ztex.decode(raw, 1))
        with self.assertRaises(ztex.ZtexError):
            ztex.replace_image(raw, 0, other, 8, 8)

    def test_rejects_bad_input(self):
        with self.assertRaises(ztex.ZtexError):
            ztex.parse(b'zmdl' + bytes(60))
        with self.assertRaises(ztex.ZtexError):
            ztex.encode_pixels(bytes(12 * 12 * 4), 'rgba8', 12, 12)

    @unittest.skipUnless(EXTRACTION.is_dir(), 'game extraction not present')
    def test_real_icon_decodes_as_displayed_in_game(self):
        # In the game's menus the Squire's Sword handle is bottom-left and the tip top-right.
        w, h, rgba = ztex.decode(next(EXTRACTION.glob('16418_*')).read_bytes())
        alpha = lambda x, y: rgba[(y * w + x) * 4 + 3]
        self.assertGreater(alpha(12, 52), 200)   # pommel
        self.assertGreater(alpha(54, 14), 200)   # blade tip
        self.assertEqual(alpha(12, 12), 0)
        self.assertEqual(alpha(54, 54), 0)

    @unittest.skipUnless(EXTRACTION.is_dir(), 'game extraction not present')
    def test_real_files_rebuild_byte_identical(self):
        for id_ in (16418, 3805, 4113):  # icon (etc1a4), 3-image weapon texture with dye records, 2 mips
            with self.subTest(id=id_):
                raw = next(EXTRACTION.glob(f'{id_:05d}_*')).read_bytes()
                info = ztex.parse(raw)
                images = [dict(name=i['name'], width=i['width'], height=i['height'], format=i['format'],
                               mips=i['mips'], data=raw[i['offset']:i['offset'] + i['size']]) for i in info['images']]
                self.assertEqual(ztex.build(images, info['flags'], info['extra']), raw)


if __name__ == '__main__':
    unittest.main()
