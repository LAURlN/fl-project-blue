#!/usr/bin/env python3
"""Validate private decrypted EU dumps and extract their modding archive read-only."""
import argparse
import importlib.util
import mmap
from pathlib import Path
import struct
import tempfile

spec = importlib.util.spec_from_file_location('phase0_extract', Path(__file__).with_name('phase0_extract.py'))
phase0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phase0)


def main_partition(data):
    layout = phase0.parse_ncsd(data)
    part = next((p for p in layout['partitions'] if p['index'] == 0), None)
    phase0.require(part is not None and part['program_id'] == '0004000000113100', 'Expected Fantasy Life EU (0004000000113100)')
    phase0.require(part['no_crypto'], 'The ROM must be decrypted (NCCH NoCrypto)')
    phase0.require(part['sections']['romfs']['size'] > 0, 'ROM has no RomFS')
    return part


def validate_dlc(path):
    with path.open('rb') as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
        phase0.require(len(data) >= 0x2020, 'Truncated CIA')
        header, = struct.unpack_from('<I', data)
        cert, ticket, tmd, meta = struct.unpack_from('<4I', data, 8)
        content_size, = struct.unpack_from('<Q', data, 24)
        phase0.require(0x2020 <= header <= len(data), 'Invalid CIA header')
        align = lambda x: (x + 63) & ~63
        ticket_at = align(align(header) + cert)
        tmd_at = align(ticket_at + ticket)
        content_at = align(tmd_at + tmd)
        phase0.require(content_at + content_size <= len(data), 'CIA contents exceed file')
        phase0.require(content_size > 0 and tmd >= 0x100, 'CIA has no contents')
        sig, = struct.unpack_from('>I', data, tmd_at)
        signature_size = {0x10000: 0x240, 0x10001: 0x140, 0x10002: 0x80, 0x10003: 0x240, 0x10004: 0x140, 0x10005: 0x80}.get(sig)
        phase0.require(signature_size is not None and signature_size + 0xc4 <= tmd, 'Invalid TMD signature layout')
        title, = struct.unpack_from('>Q', data, tmd_at + signature_size + 0x4c)
        phase0.require(title == 0x0004008c00113100, 'Expected Origin Island EU DLC (0004008c00113100)')
        count, = struct.unpack_from('>H', data, tmd_at + signature_size + 0x9e)
        phase0.require(count > 0, 'DLC has no content records')
        installed = 0
        records = tmd_at + signature_size + 0x9c4
        phase0.require(records + count * 0x30 <= tmd_at + tmd, 'Truncated TMD content table')
        cursor = content_at
        for i in range(count):
            record = records + i * 0x30
            index, flags, size = struct.unpack_from('>HHQ', data, record + 4)
            if not data[0x20 + index // 8] & (0x80 >> (index % 8)):
                continue
            phase0.require(not flags & 1, 'DLC CIA contains encrypted content')
            phase0.require(size and cursor + size <= content_at + content_size, 'Invalid CIA content size')
            if data[cursor + 0x100:cursor + 0x104] == b'NCCH':
                phase0.require(data[cursor + 0x18f] & 4, 'DLC NCCH must be decrypted')
            cursor += size
            installed += 1

        phase0.require(installed > 0, 'DLC CIA contains no installed content')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check-rom', 'check-dlc', 'extract-archive'])
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path, nargs='?')
    args = parser.parse_args()
    if args.command == 'check-dlc':
        validate_dlc(args.source)
    else:
        with args.source.open('rb') as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
            part = main_partition(data)
            if args.command == 'extract-archive':
                phase0.require(args.output is not None and not args.output.exists(), 'Choose a new output archive path')
                phase0.require(args.output.resolve() != args.source.resolve(), 'Output must differ from the original ROM')
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix='fl-romfs-', dir=args.output.parent) as temp:
                    root = Path(temp)
                    phase0.extract_romfs(data, part, root)
                    archive = root / '_file_archive.bin'
                    phase0.require(archive.is_file(), 'ROM does not contain _file_archive.bin')
                    archive.replace(args.output)
    print('OK: ' + args.command)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, struct.error, IndexError) as error:
        raise SystemExit(str(error))
