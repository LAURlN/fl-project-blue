#!/usr/bin/env python3
"""Recover FL EU command metadata by emulating ONLY its table initializer.

Research dependency: unicorn 2.x (not needed by fl_script.py). No game boot, I/O,
services, or command handler is executed. The 700 argument counts are read from
rodata; the initializer copies ARM C++ member-function pointers into an object.
Usage: PYTHONPATH=tools/build/re-python python3 tools/re/script_commands.py CODE OUT
"""
import argparse
import json
from pathlib import Path
import struct


def extract(binary):
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
    from unicorn.arm_const import (UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_R0,
                                   UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC, UC_ARM_REG_PC)
    if binary[0x2a0fa8:0x2a0fac] != bytes.fromhex('e01f9fe5'):
        raise ValueError('Not the supported EU command initializer at VA 0x3a0fa8')
    vm = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    vm.mem_map(0x100000, 0x700000)
    vm.mem_write(0x100000, binary)
    vm.mem_map(0x1000000, 0x100000)
    vm.mem_map(0x2000000, 0x10000)
    vm.reg_write(UC_ARM_REG_SP, 0x200f000)
    vm.reg_write(UC_ARM_REG_LR, 0x2000000)
    vm.reg_write(UC_ARM_REG_R0, 0x1000000)
    vm.reg_write(UC_ARM_REG_C1_C0_2, 0xf << 20)
    vm.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
    vm.emu_start(0x3a0fa8, 0x2000000, count=20000)
    if vm.reg_read(UC_ARM_REG_PC) != 0x2000000:
        raise ValueError('Initializer did not return within the instruction bound')
    result = []
    for i in range(700):
        handler, adjustment = struct.unpack('<II', vm.mem_read(0x1000004 + 8*i, 8))
        if not 0x399000 <= handler < 0x3b2000 or adjustment:
            raise ValueError(f'Unexpected member-function pointer in slot {i}')
        result.append(dict(id=i, handler=f'0x{handler:08x}',
                           argc=binary[0x527f78+i]))
    return result


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('binary', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--check', action='store_true', help='Verify handler/argc against an annotated catalog without modifying it')
    args = p.parse_args()
    rows = extract(args.binary.read_bytes())
    if args.check:
        catalog = json.loads(args.output.read_text())['commands']
        if [{k: c[k] for k in ('id', 'handler', 'argc')} for c in catalog] != rows:
            raise ValueError('Command metadata differs from the annotated catalog')
        print('700 command handler/argc pairs match the executable')
    else:
        args.output.write_text(json.dumps(rows, indent=2)+'\n')


if __name__ == '__main__':
    main()
