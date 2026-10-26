"""Regression tests for encryption preflight and malformed extraction inputs."""
import contextlib
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import phase0_extract as phase0


class ExtractionTests(unittest.TestCase):
    def test_blz_backreferences(self):
        # Independent tiny BLZ stream: three literal As, then 18+18+18+7 As.
        payload = struct.pack('<4H', 0x4000, 0xf000, 0xf000, 0xf000) + b'AAA\x1e'
        encoded = payload + struct.pack('<II', (8 << 24) | 20, 44)
        self.assertEqual(phase0.decompress_blz(encoded), b'A' * 64)

    def test_invalid_blz_footer(self):
        with self.assertRaisesRegex(ValueError, 'Invalid BLZ trailer'):
            phase0.decompress_blz(b'\0' * 8)

    def test_path_traversal(self):
        for name in (b'..', b'../code.bin', b'/etc/passwd', b'a\\b', b'x\0y'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                phase0.checked_name(name, 'ascii')

    def test_mixed_encryption_stops_before_writing(self):
        # Even a late encrypted partition must stop extraction of an earlier
        # decrypted one. No payload data or keys are involved in this fixture.
        image = bytearray(0x600)
        image[0x100:0x104] = b'NCSD'
        for i, base in [(0, 0x200), (7, 0x400)]:
            struct.pack_into('<II', image, 0x120 + 8 * i, base // 0x200, 1)
            image[base + 0x100:base + 0x104] = b'NCCH'
            struct.pack_into('<I', image, base + 0x104, 1)
            image[base + 0x18f] = 4 if i == 0 else 0
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'dumps' / 'fixture.3ds'
            source.parent.mkdir()
            source.write_bytes(image)
            output = root / 'extracted'
            argv = ['phase0_extract.py', str(source), '--output', str(output)]
            with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(phase0.main(), 2)
            self.assertIn('ENCRYPTED NCCH CONTENT', stdout.getvalue())
            self.assertFalse(output.exists())
            self.assertEqual(source.read_bytes(), image)

    def test_partition_outside_trimmed_file(self):
        image = bytearray(0x200)
        image[0x100:0x104] = b'NCSD'
        struct.pack_into('<II', image, 0x120, 1, 1)
        with self.assertRaisesRegex(ValueError, 'Partition outside dump'):
            phase0.parse_ncsd(image)


if __name__ == '__main__':
    unittest.main()
