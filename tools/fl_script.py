#!/usr/bin/env python3
"""Lossless Fantasy Life EU event/field disassembler and assembler (stdlib).

'disasm FILE [--archive DIR]' emits editable .fls text; 'asm TEXT OUT' rebuilds
it. All bytes are represented by directives/instructions, with no hidden binary
preservation image. Dialogue comments are read from SCR with --archive. Unknown
field payloads and message attributes remain explicit hex. See phase1c-scripts.md.
"""
import argparse
from collections import Counter
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

_spec = importlib.util.spec_from_file_location('fl_scr', Path(__file__).with_name('fl_scr.py'))
fl_scr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fl_scr)
_map_spec = importlib.util.spec_from_file_location('fl_map', Path(__file__).with_name('fl_map.py'))
fl_map = importlib.util.module_from_spec(_map_spec)
_map_spec.loader.exec_module(fl_map)

FIELD_MAGIC = bytes.fromhex('0ff14033')
WRAPPER = struct.pack('<II', 2, 16)
VM_NAMES = ('load', 'push', 'address', 'load_index', 'address_index', 'store',
            'store_index', 'native', 'call_global', 'return_global', 'call',
            'return', 'end', 'frame', 'alloc', 'jump', 'jump_zero', 'alu')
ALU_NAMES = ('neg', 'add', 'sub', 'mul', 'div', 'mod', 'shl', 'asr', 'inc', 'dec',
             'and', 'or', 'xor', 'not', 'bitnot', 'eq', 'ne', 'lt', 'gt', 'le',
             'ge', 'dup', 'drop')
BRANCHES = {10, 15, 16}


@lru_cache(maxsize=1)
def commands():
    path = Path(__file__).parent / 're' / 'script_commands.json'
    return json.loads(path.read_text())['commands']


def require(value, message):
    if not value:
        raise ValueError(message)


def number(value):
    return int(value, 0)


def sections(data):
    require(data[:8] == WRAPPER, 'Not a two-section wrapper')
    second, end = struct.unpack('<II', fl_scr.span(data, 8, 8))
    require(16 <= second <= end == len(data), 'Invalid wrapper boundaries')
    return data[16:second], data[second:]


def vm_layout(meta, code):
    """Recognize verified VM shapes, including independent old label/code widths."""
    require(len(meta) >= 4, 'Missing VM label table')
    label_width = 2 if meta[2:4] == b'\xff\xff' else 4
    count = int.from_bytes(meta[:label_width], 'little')
    require(count <= (len(meta)-label_width)//label_width, 'Invalid label count')
    labels = [int.from_bytes(meta[i:i+label_width], 'little')
              for i in range(label_width, (count+1)*label_width, label_width)]
    candidates = []
    for width in (5, 6):
        n = len(code)//width
        pad = code[n*width:]
        if len(pad) > 3 or any(pad):
            continue
        ops = [struct.unpack_from('<BI' if width == 5 else '<HI', code, i*width)
               for i in range(n)]
        if not ops or any(op >= 18 for op, val in ops):
            continue
        sentinel = (1 << (label_width*8))-1
        if any((v & 0xffffff if label_width == 4 else v) >= n
               for v in labels if v != sentinel):
            continue
        if any(v >> 8 >= n for op, v in ops if op in BRANCHES):
            continue
        candidates.append((width, ops, pad))
    require(candidates, 'Unrecognized VM encoding or invalid label/branch target')
    prefer = 6 if label_width == 2 else 5
    width, ops, pad = next((x for x in candidates if x[0] == prefer), candidates[0])
    pool = meta[(count+1)*label_width:]
    require(len(pool) >= 2, 'Missing global function table')
    n = int.from_bytes(pool[:2], 'little')
    require(2+2*n <= len(pool), 'Truncated global function table')
    globals_ = list(struct.unpack_from(f'<{n}H', pool, 2))
    require(all(x < len(ops) for x in globals_), 'Global function target outside code')
    return dict(label_width=label_width, labels=labels, width=width, ops=ops, padding=pad,
                globals=globals_, pool=pool[2+2*n:])


class Resolver:
    def __init__(self, root=None, language=8):
        self.root = Path(root) if root else None
        self.entries = {}
        self.cache = {}
        require(0 <= language <= 8, 'Language slot must be 0..8')
        self.language = language
        if self.root:
            manifest = json.loads((self.root / '.fl_archive' / 'manifest.json').read_text())
            self.entries = {e['id']: self.root/e['path'] for e in manifest['entries']}

    def rows(self, id_):
        if id_ not in self.cache:
            path = self.entries.get(id_)
            if not path:
                return []
            try:
                self.cache[id_] = fl_scr.dump(path.read_bytes(), id_)['sections'][0].get('rows', [])
            except ValueError:
                self.cache[id_] = []
        return self.cache[id_]

    def flag(self, id_):
        rows = self.rows(5417)
        return fl_scr.plain(rows[id_]['label']) if 0 <= id_ < len(rows) else ''

    def text(self, id_, row=0, column=0):
        rows = self.rows(id_)
        if not 0 <= row < len(rows):
            return ''
        vals = [v for k, v in rows[row].items() if k != '_raw']
        if not 0 <= column < len(vals):
            return ''
        val = vals[column]
        return fl_scr.plain(val) if isinstance(val, (str, list)) else ''

    def local_text(self, resource_id, row, global_=False):
        for assoc in self.rows(8697):
            ids = assoc['c00']
            if (global_ and assoc['c01'] == 0) or (not global_ and ids[0] == resource_id):
                if not global_ and assoc['c01'] == 0:
                    # Shared code keeps the calling thread's message object.
                    return ''
                base = ids[1]
                # Japanese text precedes code; eight Western text slots follow it.
                return self.text(base + (self.language+1 if self.language else 0), row)
        return ''


def comment(value):
    return json.dumps(value, ensure_ascii=False)


def hex_lines(data, out, directive='.hex'):
    for start in range(0, len(data), 32):
        out.append(f'{directive} {data[start:start+32].hex()}')


def annotate_table(data, out):
    if data[:4] != fl_scr.MAGIC:
        return
    section = fl_scr.decode_section(data)
    columns = [c['name'] for c in section['columns'] if c['type'] in ('utf16', 'ascii')]
    for i, row in enumerate(section['rows']):
        for col in columns:
            out.append(f'# text row={i} column={col}: {comment(fl_scr.plain(row[col]))}')


def call_comments(ops, command_table, resolver, resource_id=None):
    """Conservative annotations for contiguous literal arguments; never simulate branches."""
    result = {}
    for i, (op, val) in enumerate(ops):
        if op != 7 or val >> 8 >= len(command_table):
            continue
        cmd = command_table[val >> 8]
        argc = cmd['argc']
        args = ops[i-argc:i] if i >= argc and argc else []
        if len(args) != argc or any(o != 1 for o, v in args):
            continue
        values = [v if v < 0x80000000 else v-0x100000000 for o, v in args]
        notes = [f'{k}={v}' for k, v in zip(cmd['operands'], values)]
        if cmd['id'] in (65, 66) and values:
            label = resolver.flag(values[0])
            if label:
                notes.append('flag ' + comment(label))
        # 90 reads the calling thread's text; 91 explicitly uses the global text
        # object. 95 selects NPC/speaker/message within a thread, NOT a resource ID.
        text = ''
        if cmd['id'] in (90, 91) and values:
            text = resolver.local_text(resource_id, values[0], global_=cmd['id'] == 91)
        if text:
            notes.append('dialogue ' + comment(text))
        result[i] = '; '.join(notes)
    return result


def disassemble(data, resolver=None, resource_id=None):
    resolver = resolver or Resolver()
    table = commands()
    out = ['# Fantasy Life EU script assembly; comments are informational.', '.format fl-script-v1']
    if resource_id is not None:
        out.append(f'# archive resource {resource_id}')
    if data[:4] == FIELD_MAGIC:
        field = fl_map.dump(data)
        count = len(field['rows'])
        offset = fl_scr.u32(data, 16)
        fl_scr.span(data, offset, count*52)
        out.append('.container field')
        out.append(f'# {count} typed objects; object table at {offset:#x}; absolute field-relative pointers')
        hex_lines(data[:offset], out)
        for i in range(count):
            raw = data[offset+i*52:offset+(i+1)*52]
            row = field['rows'][i]
            out.append(f'# object {i}: map={row["map_id"]} type={row["type"]} '
                       f'flags={row["flags"]:#x} subtype={row["subtype"]} '
                       f'uid={row["uid"]:#x} reference={row["reference"]} xyz={row["position"]!r}')
            out.append('.object ' + raw.hex())
        hex_lines(data[offset+count*52:], out)
    elif data[:8] == WRAPPER:
        first, second = sections(data)
        out.append('.container wrapper')
        if first[:4] not in (fl_scr.MAGIC, b'MSG '):
            layout = vm_layout(first, second)
            out.append(f'.labels {layout["label_width"]}')
            sentinel = (1 << (layout['label_width']*8))-1
            for i, label in enumerate(layout['labels']):
                if label == sentinel:
                    out.append('.entry absent')
                else:
                    index = label & 0xffffff if layout['label_width'] == 4 else label
                    tag = label >> 24 if layout['label_width'] == 4 else 0
                    out.append(f'.entry L{index:05d} {tag:#x}')
            out.append('.globals')
            for target in layout['globals']:
                out.append(f'.global L{target:05d}')
            out.append('.pool')
            hex_lines(layout['pool'], out)
            out.append(f'.code {layout["width"]}')
            notes = call_comments(layout['ops'], table, resolver, resource_id)
            targets = {v >> 8 for op, v in layout['ops'] if op in BRANCHES}
            targets.update(x & 0xffffff for x in layout['labels'] if x != sentinel)
            targets.update(layout['globals'])
            for i, (op, val) in enumerate(layout['ops']):
                if i in targets:
                    out.append(f'L{i:05d}:')
                suffix = ''
                if op in BRANCHES:
                    operand = f'L{val >> 8:05d} {val & 255:#x}'
                elif op == 7:
                    operand = f'{table[val >> 8]["name"] if val >> 8 < 700 else str(val >> 8)} {val & 255:#x}'
                    if val >> 8 < 700:
                        cmd = table[val >> 8]
                        suffix = f'argc={cmd["argc"]} handler={cmd["handler"]} confidence={cmd["confidence"]}'
                elif op == 17 and val < len(ALU_NAMES):
                    operand = ALU_NAMES[val]
                else:
                    operand = f'{val:#010x}'
                if i in notes:
                    suffix += ('; ' if suffix else '') + notes[i]
                out.append(f'  {VM_NAMES[op]} {operand}' + (f' # {suffix}' if suffix else ''))
            out.append('.padding ' + (layout['padding'].hex() or '-'))
        else:
            out.append('.section 0')
            annotate_table(first, out)
            hex_lines(first, out)
            out.append('.section 1')
            if second:
                count = fl_scr.u32(second, 0)
                width = (len(second)-4)//count if count and (len(second)-4)%count == 0 else 0
                if width in (4, 60):
                    out.append(f'# {count} message attributes, {width} bytes per text row')
                    hex_lines(second[:4], out)
                    for i in range(count):
                        out.append(f'.attribute {second[4+i*width:4+(i+1)*width].hex()} # row {i}')
                else:
                    hex_lines(second, out)
    else:
        raise ValueError('Unsupported script resource magic')
    return '\n'.join(out)+'\n'


def assemble(text):
    table = commands()
    native = {c['name']: c['id'] for c in table}
    mode = None
    raw = bytearray()
    parts = [bytearray(), bytearray()]
    current = 0
    entries, globals_, pool, ops, labels = [], None, bytearray(), [], {}
    label_width = code_width = None
    padding = b''
    state = 'raw'
    seen_format = False
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        tokens = line.split()
        name, args = tokens[0], tokens[1:]
        try:
            if name == '.format':
                require(args == ['fl-script-v1'] and not seen_format, 'Unsupported/duplicate format')
                seen_format = True
            elif name == '.container':
                require(mode is None and args in (['wrapper'], ['field']), 'Invalid container')
                mode = args[0]
            elif name == '.section':
                require(mode == 'wrapper' and label_width is None and len(args) == 1, 'Invalid raw section')
                current = number(args[0])
                require(current in (0, 1), 'Invalid section number')
            elif name == '.labels':
                require(mode == 'wrapper' and label_width is None and len(args) == 1
                        and not any(parts), 'Invalid/duplicate label table')
                label_width = number(args[0])
                require(label_width in (2, 4), 'Invalid label width')
                state = 'labels'
            elif name == '.entry':
                require(state == 'labels' and 1 <= len(args) <= 2, 'Invalid entry')
                entries.append(args)
            elif name == '.pool':
                require(state in ('labels', 'globals') and not args, 'Pool must follow label/global table')
                state = 'pool'
            elif name == '.globals':
                require(state == 'labels' and not args, 'Globals must follow entries')
                globals_ = []
                state = 'globals'
            elif name == '.global':
                require(state == 'globals' and len(args) == 1, 'Invalid global entry')
                globals_.append(args[0])
            elif name == '.code':
                require(state == 'pool' and len(args) == 1, 'Code must follow pool')
                code_width = number(args[0])
                require(code_width in (5, 6), 'Invalid instruction width')
                state = 'code'
            elif name == '.padding':
                require(state == 'code', 'Padding must follow code')
                padding = b'' if args == ['-'] else bytes.fromhex(''.join(args))
                require(len(padding) <= 3 and not any(padding), 'Invalid VM alignment padding')
                state = 'done'
            elif name in ('.hex', '.object', '.attribute'):
                payload = bytes.fromhex(''.join(args))
                require(name != '.object' or len(payload) == 52, 'Object requires 52 bytes')
                if mode == 'field':
                    raw.extend(payload)
                elif state == 'pool':
                    pool.extend(payload)
                else:
                    require(mode == 'wrapper' and label_width is None, 'Hex outside raw section/pool')
                    parts[current].extend(payload)
            elif name.endswith(':'):
                require(state == 'code' and not args and name[:-1] not in labels, 'Invalid/duplicate label')
                labels[name[:-1]] = len(ops)
            else:
                require(state == 'code' and name in VM_NAMES, 'Unknown instruction/directive')
                ops.append((VM_NAMES.index(name), args, lineno))
        except (ValueError, IndexError) as error:
            raise ValueError(f'Line {lineno}: {error}') from error
    require(seen_format and mode, 'Missing format/container')
    if mode == 'field':
        # Validate fixed object table and preserve all unknown payload/pointer bytes.
        require(raw[:4] == FIELD_MAGIC and len(raw) >= 212, 'Invalid field container')
        struct.pack_into('<I', raw, 4, len(raw)-212)
        fl_map.dump(bytes(raw))
        return bytes(raw)
    if label_width:
        require(state == 'done' and code_width, 'Missing code/padding')
        sentinel = (1 << (label_width*8))-1
        first = bytearray(len(entries).to_bytes(label_width, 'little'))
        for args in entries:
            if args == ['absent']:
                val = sentinel
            else:
                require(args[0] in labels and len(args) == 2, 'Undefined entry label')
                tag = number(args[1])
                require(0 <= tag <= 255 and (label_width == 4 or tag == 0), 'Invalid entry tag')
                val = labels[args[0]] | tag << 24
                require(val < sentinel, 'Entry outside label integer range')
            first.extend(val.to_bytes(label_width, 'little'))
        if globals_ is not None:
            require(len(globals_) <= 65535, 'Too many global functions')
            global_bytes = bytearray(struct.pack('<H', len(globals_)))
            for target in globals_:
                require(target in labels and labels[target] <= 65535, 'Invalid global function label')
                global_bytes.extend(struct.pack('<H', labels[target]))
            first.extend(global_bytes)
        first.extend(pool)
        second = bytearray()
        for op, args, lineno in ops:
            try:
                if op in BRANCHES:
                    require(len(args) == 2 and args[0] in labels, 'Undefined branch label')
                    low = number(args[1]); require(0 <= low <= 255, 'Branch low byte outside range')
                    val = labels[args[0]] << 8 | low
                elif op == 7:
                    require(len(args) == 2, 'Native requires command and low byte')
                    id_ = native[args[0]] if args[0] in native else number(args[0])
                    low = number(args[1]); require(0 <= low <= 255 and 0 <= id_ < 1 << 24, 'Invalid native operand')
                    val = id_ << 8 | low
                elif op == 17 and len(args) == 1 and args[0] in ALU_NAMES:
                    val = ALU_NAMES.index(args[0])
                else:
                    require(len(args) == 1, 'Instruction requires one operand')
                    val = number(args[0])
                require(0 <= val <= 0xffffffff, 'Operand outside u32 range')
                second.extend(struct.pack('<BI' if code_width == 5 else '<HI', op, val))
            except (ValueError, IndexError) as error:
                raise ValueError(f'Line {lineno}: {error}') from error
        second.extend(padding)
        parts = [first, second]
        vm_layout(bytes(first), bytes(second))
    return WRAPPER + struct.pack('<II', 16+len(parts[0]), 16+sum(map(len, parts))) + b''.join(parts)


def corpus(root):
    root = Path(root)
    manifest = json.loads((root/'.fl_archive/manifest.json').read_text())
    for entry in manifest['entries']:
        path = root/entry['path']
        with path.open('rb') as f:
            magic = f.read(8)
        if magic[:4] == FIELD_MAGIC or magic == WRAPPER:
            yield entry['id'], path


def flag_references(root, flag_id):
    """Literal native flag tests/writes only; does not claim dynamic data-flow coverage."""
    for resource_id, path in corpus(root):
        data = path.read_bytes()
        if data[:8] != WRAPPER:
            continue
        first, second = sections(data)
        if first[:4] in (fl_scr.MAGIC, b'MSG '):
            continue
        layout = vm_layout(first, second)
        ops = layout['ops']
        for pc, (op, value) in enumerate(ops):
            command = value >> 8
            argc = 1 if command == 66 else 2 if command == 65 else 0
            if op == 7 and argc and pc >= argc and ops[pc-argc] == (1, flag_id):
                yield dict(resource_id=resource_id, instruction=pc, command=command,
                           file_offset=16+len(first)+pc*layout['width'], path=str(path))


def main():
    p = argparse.ArgumentParser(__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    d = sub.add_parser('disasm')
    d.add_argument('input', type=Path)
    d.add_argument('-o', '--output', type=Path)
    d.add_argument('--archive', type=Path)
    d.add_argument('--language', type=int, default=8, help='Text slot 0..8 (default UK English)')
    a = sub.add_parser('asm')
    a.add_argument('input', type=Path)
    a.add_argument('output', type=Path)
    c = sub.add_parser('check', help='Verify the entire extracted script corpus byte for byte')
    c.add_argument('archive', type=Path)
    f = sub.add_parser('find-flag', help='Find literal flag_set/flag_test references (not dynamic arguments)')
    f.add_argument('archive', type=Path)
    f.add_argument('flag_id', type=int)
    args = p.parse_args()
    try:
        if args.command == 'disasm':
            match = re.match(r'(\d+)_', args.input.name)
            text = disassemble(args.input.read_bytes(), Resolver(args.archive, args.language),
                               int(match[1]) if match else None)
            if args.output:
                args.output.write_text(text, encoding='utf-8')
            else:
                sys.stdout.write(text)
        elif args.command == 'asm':
            args.output.write_bytes(assemble(args.input.read_text(encoding='utf-8')))
        elif args.command == 'find-flag':
            print(json.dumps(list(flag_references(args.archive, args.flag_id)), indent=2))
        else:
            counts = Counter()
            for id_, path in corpus(args.archive):
                data = path.read_bytes()
                rebuilt = assemble(disassemble(data))
                require(rebuilt == data, f'Resource {id_}: byte mismatch')
                counts['field' if data[:4] == FIELD_MAGIC else 'wrapper'] += 1
            print(json.dumps(dict(counts), sort_keys=True))
    except (ValueError, OSError) as error:
        p.exit(1, f'fl_script: {error}\n')


if __name__ == '__main__':
    main()
