"""Read-only launcher validation of synthetic EU ROM and DLC containers."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('fl_3ds', Path(__file__).resolve().parents[1] / 'fl_3ds.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class GameFileValidation(unittest.TestCase):
    def test_rom_region_encryption_and_bounds(self):
        image = bytearray(0x600)
        image[0x100:0x104] = b'NCSD'
        struct.pack_into('<II', image, 0x120, 1, 2)
        image[0x300:0x304] = b'NCCH'
        struct.pack_into('<I', image, 0x304, 2)
        struct.pack_into('<Q', image, 0x318, 0x0004000000113100)
        struct.pack_into('<II', image, 0x3b0, 1, 1)
        image[0x38f] = 4
        before = bytes(image)
        self.assertEqual(tool.main_partition(image)['program_id'], '0004000000113100')
        self.assertEqual(bytes(image), before)
        image[0x38f] = 0
        with self.assertRaisesRegex(ValueError, 'decrypted'):
            tool.main_partition(image)
        image[0x38f] = 4
        struct.pack_into('<Q', image, 0x318, 1)
        with self.assertRaisesRegex(ValueError, 'Fantasy Life EU'):
            tool.main_partition(image)
        with self.assertRaisesRegex(ValueError, 'Partition outside'):
            tool.main_partition(image[:-1])

    def test_dlc_title_encryption_and_content_bounds(self):
        image = bytearray(0x3200)
        tmd_at, signature = 0x2040, 0x140
        tmd_size = signature + 0x9c4 + 0x30
        content_at = (tmd_at + tmd_size + 63) & ~63
        struct.pack_into('<I', image, 0, 0x2020)
        struct.pack_into('<4I', image, 8, 0, 0, tmd_size, 0)
        struct.pack_into('<Q', image, 24, 0x200)
        image[0x20] = 0x80
        struct.pack_into('>I', image, tmd_at, 0x10004)
        struct.pack_into('>Q', image, tmd_at + signature + 0x4c, 0x0004008c00113100)
        struct.pack_into('>H', image, tmd_at + signature + 0x9e, 1)
        record = tmd_at + signature + 0x9c4
        struct.pack_into('>HHQ', image, record + 4, 0, 0, 0x200)
        image[content_at + 0x100:content_at + 0x104] = b'NCCH'
        image[content_at + 0x18f] = 4
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.cia'
            path.write_bytes(image)
            tool.validate_dlc(path)
            self.assertEqual(path.read_bytes(), image)
            struct.pack_into('>H', image, record + 6, 1)
            path.write_bytes(image)
            with self.assertRaisesRegex(ValueError, 'encrypted'):
                tool.validate_dlc(path)
            struct.pack_into('>H', image, record + 6, 0)
            struct.pack_into('>Q', image, tmd_at + signature + 0x4c, 1)
            path.write_bytes(image)
            with self.assertRaisesRegex(ValueError, 'Origin Island EU'):
                tool.validate_dlc(path)
