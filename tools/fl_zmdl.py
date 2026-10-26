#!/usr/bin/env python3
"""Fantasy Life ZMDL models: inspect, export OBJ/glTF, import glTF, replace geometry, render previews.

Standard library only. Layout (version 3) follows Ohana3DS Rebirth's ZMDL importer (read as
a specification) plus the observations in docs/modding-guide.md:

    0x00 'zmdl' u32 version(3) f32 bound[4]  ...
    0x20 u32 materials_offset u32 bones_offset u32 meshes_offset
         u16 material_count u16 bone_count u16 mesh_count u16 unknown
    material (0xb4): name[0x40] ... @0x94 u32 texture_ref_offset u32 mesh_index_offset
    bone (0xcc):     name[0x40] u32 crc32(name) f32 local[3][4] f32 inverse_bind[3][4]
                     @0xa4 f32 translation[3] rotation[3] scale[3] s16 parent s16 unknown
    mesh (0xc4):     9 attributes x (f32[4] scale/default, u8 offset/4, u8 components, u16 stride/4)
                     (position, normal, colour, uv0, uv1, uv2, bone index, bone weight, outline
                     normal), then u32 face_groups_offset u32 face_group_count
                     u32 vertex_buffer_offset u32 vertex_buffer_words
    face group (0x14): u32 nodes_offset u32 node_count u32 index_offset u32 index_count u32 mode
    vertex attributes are f32; indices u16 triangle lists. All vertex buffers follow the
    metadata, then all index buffers (each 4-byte aligned); nothing follows them.

Bones: `local` (row-major 3x4) = T * Rz * Ry * Rx * S of the euler fields; `inverse_bind` is
the inverse of the composed parent chain (checked on all 29,111 bones of the 4,442 v3 models).
An absent attribute (0 components) takes its descriptor's default value for every vertex.
Face group mode 0 is rigid: each vertex is in the local space of bone nodes[node[0]] (whole
mesh on nodes[0] without a bone-index attribute). Mode 1 is smooth skinning in model space
(4 palette indices, 4 weights summing to 1). Palettes hold at most 20 bones.
Attribute 8 is a smooth per-position normal used for the game's inverted-hull outline.

    python3 -I tools/fl_zmdl.py info   <model.zmdl>
    python3 -I tools/fl_zmdl.py obj    <model.zmdl> <out.obj>
    python3 -I tools/fl_zmdl.py gltf   <model.zmdl> <out.glb> [--ztex tex.ztex ...] [--up z]
    python3 -I tools/fl_zmdl.py import-glb <donor.zmdl> <in.glb> <out.zmdl> [--up z] [--bone R_tool]
    python3 -I tools/fl_zmdl.py render <model.zmdl> <texture.ztex> <out.png> [--yaw 35 --pitch 20 --size 512]
"""
import argparse
import base64
import json
import math
import re
import struct
import sys
import zlib
from pathlib import Path
import importlib.util

ATTRIBUTES = ('position', 'normal', 'colour', 'uv0', 'uv1', 'uv2', 'node', 'weight', 'outline_normal')
MATERIAL_SIZE, BONE_SIZE, MESH_SIZE, GROUP_SIZE = 0xb4, 0xcc, 0xc4, 0x14
MAX_PALETTE = 20       # largest bone palette in any shipped face group


class ZmdlError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ZmdlError(message)


def cstr(raw, offset, size=0x40):
    return raw[offset:offset + size].split(b'\0', 1)[0].decode('latin-1')


def _rows(values):
    """12 floats (3x4, row-major, translation in the 4th column) -> 4x4 row lists."""
    return [list(values[0:4]), list(values[4:8]), list(values[8:12]), [0.0, 0.0, 0.0, 1.0]]


def parse(raw):
    require(raw[:4] == b'zmdl', 'not a zmdl file')
    version, = struct.unpack_from('<I', raw, 4)
    require(version == 3, f'unsupported zmdl version {version}')
    mat_off, bone_off, mesh_off, mat_count, bone_count, mesh_count, unknown = struct.unpack_from('<3I4H', raw, 0x20)
    model = dict(version=version, bound=struct.unpack_from('<4f', raw, 8), unknown=unknown,
                 materials=[], bones=[], meshes=[])
    for i in range(mat_count):
        base = mat_off + i * MATERIAL_SIZE
        tex_ref, mesh_ref = struct.unpack_from('<2I', raw, base + 0x94)
        model['materials'].append(dict(name=cstr(raw, base), texture=cstr(raw, tex_ref),
                                       texture_crc32=struct.unpack_from('<I', raw, tex_ref + 0x70)[0],
                                       mesh=raw[mesh_ref], offset=base))
    for i in range(bone_count):
        base = bone_off + i * BONE_SIZE
        values = struct.unpack_from('<9fh', raw, base + 0xa4)
        matrices = struct.unpack_from('<24f', raw, base + 0x44)
        model['bones'].append(dict(name=cstr(raw, base), translation=values[0:3], rotation=values[3:6],
                                   scale=values[6:9], parent=values[9],
                                   local=_rows(matrices[:12]), inverse_bind=_rows(matrices[12:])))
    for i in range(mesh_count):
        base = mesh_off + i * MESH_SIZE
        attributes = {}
        for k, name in enumerate(ATTRIBUTES):
            *default, offset, count, stride = struct.unpack_from('<4f2BH', raw, base + k * 20)
            attributes[name] = dict(default=tuple(default), offset=offset, count=count, stride=stride)
        groups_off, group_count, vb_off, vb_words = struct.unpack_from('<4I', raw, base + 0xb4)
        stride = attributes['outline_normal']['stride']
        require(stride and all(a['stride'] == stride for a in attributes.values()), 'inconsistent vertex stride')
        groups = []
        for g in range(group_count):
            gbase = groups_off + g * GROUP_SIZE
            nodes_off, node_count, ib_off, index_count, mode = struct.unpack_from('<5I', raw, gbase)
            groups.append(dict(nodes=list(raw[nodes_off:nodes_off + node_count]), index_offset=ib_off,
                               index_count=index_count, mode=mode, header=gbase))
        model['meshes'].append(dict(header=base, attributes=attributes, stride_words=stride,
                                    vertex_offset=vb_off, vertex_words=vb_words,
                                    vertex_count=vb_words // stride, groups=groups))
    return model


def vertices(raw, mesh):
    """List of vertices; each a dict attribute -> tuple of floats (present attributes only)."""
    stride = mesh['stride_words'] * 4
    out = []
    for i in range(mesh['vertex_count']):
        words = struct.unpack_from(f'<{mesh["stride_words"]}f', raw, mesh['vertex_offset'] + i * stride)
        out.append({name: tuple(words[a['offset']:a['offset'] + a['count']])
                    for name, a in mesh['attributes'].items() if a['count']})
    return out


def indices(raw, group):
    return list(struct.unpack_from(f'<{group["index_count"]}H', raw, group['index_offset']))


def _buffers(model):
    blobs = []
    for m, mesh in enumerate(model['meshes']):
        blobs.append((mesh['vertex_offset'], 'v', m, None))
        for g, group in enumerate(mesh['groups']):
            blobs.append((group['index_offset'], 'i', m, g))
    return sorted(blobs)


def rebuild(raw, replacements):
    """Return new zmdl bytes. replacements: {mesh_index: (vertex_bytes, [index_bytes per group])}.

    Metadata is kept byte for byte; vertex/index buffers are relocated in their original
    order (vertex buffers, then index buffers, 4-byte aligned) and the offsets/counts patched.
    """
    model = parse(raw)
    blobs = _buffers(model)
    require(blobs, 'model has no meshes')
    data = {}
    for _, kind, m, g in blobs:
        mesh = model['meshes'][m]
        if kind == 'v':
            original = raw[mesh['vertex_offset']:mesh['vertex_offset'] + mesh['vertex_words'] * 4]
            data[(kind, m, g)] = replacements[m][0] if m in replacements else original
        else:
            group = mesh['groups'][g]
            original = raw[group['index_offset']:group['index_offset'] + group['index_count'] * 2]
            data[(kind, m, g)] = replacements[m][1][g] if m in replacements else original
    for m, (vbytes, ibytes) in replacements.items():
        mesh = model['meshes'][m]
        require(len(vbytes) % (mesh['stride_words'] * 4) == 0, 'vertex data is not a whole number of vertices')
        require(len(ibytes) == len(mesh['groups']), 'one index buffer per face group required')
        count = len(vbytes) // (mesh['stride_words'] * 4)
        require(count <= 65536, 'too many vertices for u16 indices')
        for buf in ibytes:
            require(len(buf) % 6 == 0, 'index buffers are triangle lists')
            require(all(i < count for i in struct.unpack(f'<{len(buf) // 2}H', buf)), 'index out of range')
    out = bytearray(raw[:blobs[0][0]])
    for _, kind, m, g in blobs:
        out.extend(b'\0' * (-len(out) % 4))
        mesh = model['meshes'][m]
        blob = data[(kind, m, g)]
        if kind == 'v':
            struct.pack_into('<2I', out, mesh['header'] + 0xbc, len(out), len(blob) // 4)
        else:
            struct.pack_into('<I', out, mesh['groups'][g]['header'] + 8, len(out))
            struct.pack_into('<I', out, mesh['groups'][g]['header'] + 12, len(blob) // 2)
        out.extend(blob)
    out.extend(b'\0' * (-len(out) % 4))
    return bytes(out)


def pack_vertices(mesh, verts):
    """verts: list of dicts attribute -> floats. Unused words are zero."""
    stride = mesh['stride_words']
    out = bytearray()
    for v in verts:
        words = [0.0] * stride
        for name, a in mesh['attributes'].items():
            if a['count']:
                values = v[name]
                require(len(values) == a['count'], f'{name} needs {a["count"]} components')
                words[a['offset']:a['offset'] + a['count']] = values
        out.extend(struct.pack(f'<{stride}f', *words))
    return bytes(out)


def replace_mesh(raw, mesh_index, verts, tris):
    """Replace one single-group mesh with new vertices (dicts) and triangles (index triples)."""
    model = parse(raw)
    mesh = model['meshes'][mesh_index]
    require(len(mesh['groups']) == 1, 'replace_mesh supports single face-group meshes')
    flat = [i for tri in tris for i in tri]
    return rebuild(raw, {mesh_index: (pack_vertices(mesh, verts), [struct.pack(f'<{len(flat)}H', *flat)])})


def rename_textures(raw, names):
    """Point materials at other texture names: {old: new}, name field (0x40 bytes) and CRC32.

    E.g. a copy of a donor model for another unit that should reference that unit's own
    texture name. Only the texture reference changes; nothing moves.
    """
    out = bytearray(raw)
    used = set()
    for material in parse(raw)['materials']:
        new = names.get(material['texture'])
        if new is None:
            continue
        encoded = new.encode('ascii')
        require(0 < len(encoded) < 0x40 and b'\0' not in encoded, 'texture names are 1..63 ASCII bytes')
        tex_ref, = struct.unpack_from('<I', raw, material['offset'] + 0x94)
        out[tex_ref:tex_ref + 0x40] = encoded.ljust(0x40, b'\0')
        struct.pack_into('<I', out, tex_ref + 0x70, zlib.crc32(encoded))
        used.add(material['texture'])
    require(used == set(names), f'no material uses texture {sorted(set(names) - used)}')
    return bytes(out)


def set_bound(raw, bound):
    out = bytearray(raw)
    struct.pack_into('<4f', out, 8, *bound)
    return bytes(out)


def export_obj(raw):
    model = parse(raw)
    lines, base = ['# Fantasy Life ZMDL export (fl_zmdl.py)'], 1
    for m, mesh in enumerate(model['meshes']):
        verts = vertices(raw, mesh)
        lines.append(f'o mesh_{m}')
        for v in verts:
            lines.append('v %.6f %.6f %.6f' % v['position'])
        for v in verts:
            u, t = v.get('uv0', (0.0, 0.0))
            lines.append('vt %.6f %.6f' % (u, 1 - t))
        for v in verts:
            lines.append('vn %.6f %.6f %.6f' % v.get('normal', (0.0, 0.0, 1.0)))
        for group in mesh['groups']:
            idx = indices(raw, group)
            for i in range(0, len(idx), 3):
                a, b, c = (base + j for j in idx[i:i + 3])
                lines.append(f'f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}')
        base += len(verts)
    return '\n'.join(lines) + '\n'




# --------------------------------------------------------------------------- bind pose helpers
def _mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _mat_point(m, p):
    return tuple(m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3] for i in range(3))


def _mat_dir(m, d):
    return tuple(m[i][0] * d[0] + m[i][1] * d[1] + m[i][2] * d[2] for i in range(3))


def _identity():
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def _mat_inv(m):
    """General 4x4 inverse (Gauss-Jordan with partial pivoting)."""
    a = [list(map(float, row)) + [1.0 if i == j else 0.0 for j in range(4)] for i, row in enumerate(m)]
    for c in range(4):
        p = max(range(c, 4), key=lambda r: abs(a[r][c]))
        require(abs(a[p][c]) > 1e-12, 'singular transform')
        a[c], a[p] = a[p], a[c]
        pivot = a[c][c]
        a[c] = [x / pivot for x in a[c]]
        for r in range(4):
            if r != c and a[r][c]:
                f = a[r][c]
                a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    return [row[4:] for row in a]


def _normal_matrix(m):
    """Inverse transpose of the upper 3x3 (as a 4x4 without translation)."""
    inv = _mat_inv([m[0][:3] + [0.0], m[1][:3] + [0.0], m[2][:3] + [0.0], [0.0, 0.0, 0.0, 1.0]])
    return [[inv[j][i] for j in range(4)] for i in range(4)]


def _det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def _quat_from_matrix(r):
    """Unit quaternion (x, y, z, w) of a 3x3 rotation (rows)."""
    trace = r[0][0] + r[1][1] + r[2][2]
    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2
        q = ((r[2][1] - r[1][2]) / s, (r[0][2] - r[2][0]) / s, (r[1][0] - r[0][1]) / s, 0.25 * s)
    elif r[0][0] > r[1][1] and r[0][0] > r[2][2]:
        s = math.sqrt(1.0 + r[0][0] - r[1][1] - r[2][2]) * 2
        q = (0.25 * s, (r[0][1] + r[1][0]) / s, (r[0][2] + r[2][0]) / s, (r[2][1] - r[1][2]) / s)
    elif r[1][1] > r[2][2]:
        s = math.sqrt(1.0 + r[1][1] - r[0][0] - r[2][2]) * 2
        q = ((r[0][1] + r[1][0]) / s, 0.25 * s, (r[1][2] + r[2][1]) / s, (r[0][2] - r[2][0]) / s)
    else:
        s = math.sqrt(1.0 + r[2][2] - r[0][0] - r[1][1]) * 2
        q = ((r[0][2] + r[2][0]) / s, (r[1][2] + r[2][1]) / s, 0.25 * s, (r[1][0] - r[0][1]) / s)
    n = math.sqrt(sum(c * c for c in q)) or 1.0
    q = tuple(c / n for c in q)
    return q if q[3] >= 0 else tuple(-c for c in q)


def _decompose(m):
    """4x4 affine -> (translation, rotation quaternion xyzw, scale)."""
    scale = [math.sqrt(sum(m[i][j] ** 2 for i in range(3))) or 1.0 for j in range(3)]
    if _det3(m) < 0:
        scale[0] = -scale[0]
    rot = [[m[i][j] / scale[j] for j in range(3)] for i in range(3)]
    return (m[0][3], m[1][3], m[2][3]), _quat_from_matrix(rot), tuple(scale)


def _compose(t=(0, 0, 0), q=(0, 0, 0, 1), s=(1, 1, 1)):
    x, y, z, w = q
    r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[r[i][0] * s[0], r[i][1] * s[1], r[i][2] * s[2], t[i]] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]]


def _unit(v, fallback=(0.0, 1.0, 0.0)):
    length = math.sqrt(sum(c * c for c in v))
    return tuple(c / length for c in v) if length > 1e-12 else tuple(fallback)


def bind_matrices(model):
    """Per bone: the bind-pose (model-space) matrix, inverse of the stored inverse bind matrix."""
    out = []
    for b in model['bones']:
        try:
            m = _mat_inv(b['inverse_bind'])
        except ZmdlError:
            m = _identity()
        out.append(m)
    return out


def _value(vertex, mesh, name):
    a = mesh['attributes'][name]
    return vertex[name] if a['count'] else a['default'][:4]


def bind_pose(raw, model=None):
    """Per mesh: (vertices, groups) in model space, each vertex once per face group using it.

    Rigid (mode 0) vertices are moved out of their bone's local space; every vertex gets
    `influences` [(bone, weight)] (one bone for rigid, up to four for smooth skinning).
    Groups are (palette, mode, triangle index list into that mesh's vertex list)."""
    model = model or parse(raw)
    binds = bind_matrices(model)
    normal_mats = {}
    out = []
    for mesh in model['meshes']:
        verts = vertices(raw, mesh)
        result, groups, remap = [], [], {}
        for gi, group in enumerate(mesh['groups']):
            palette = group['nodes']
            local = []
            for i in indices(raw, group):
                key = (i, tuple(palette), group['mode'])
                if key not in remap:
                    v = dict(verts[i])
                    node = _value(v, mesh, 'node')
                    if group['mode'] == 0:
                        slot = int(node[0])
                        require(slot < len(palette) or not palette, f'bone slot {slot} outside palette {palette}')
                        if palette and binds:
                            bone = palette[slot]
                            m = binds[bone]
                            if bone not in normal_mats:
                                normal_mats[bone] = _normal_matrix(m)
                            v['position'] = _mat_point(m, v['position'])
                            for name in ('normal', 'outline_normal'):
                                if name in v:
                                    v[name] = _unit(_mat_dir(normal_mats[bone], v[name]))
                            v['influences'] = [(bone, 1.0)]
                        else:
                            v['influences'] = []
                    else:
                        weight = _value(v, mesh, 'weight')
                        acc = {}
                        for n, w in zip(node, weight):
                            if w > 0:
                                slot = int(round(n))
                                require(slot < len(palette), f'bone slot {slot} outside palette {palette}')
                                acc[palette[slot]] = acc.get(palette[slot], 0.0) + w
                        v['influences'] = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
                    remap[key] = len(result)
                    result.append(v)
                local.append(remap[key])
            groups.append((palette, group['mode'], local))
        out.append((result, groups))
    return out


# --------------------------------------------------------------------------- glTF 2.0 export
GLB_MAGIC, GLB_JSON, GLB_BIN = b'glTF', 0x4E4F534A, 0x004E4942
UP_Z_ROTATION = (-math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5))   # glTF root: model +z (weapon blade) -> glTF +y
COMPONENTS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
COMPONENT_FORMATS = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}
NORMALIZE = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}


class _GlbBuilder:
    def __init__(self):
        self.data = bytearray()
        self.views, self.accessors = [], []

    def view(self, blob, target=None):
        self.data.extend(b'\0' * (-len(self.data) % 4))
        view = dict(buffer=0, byteOffset=len(self.data), byteLength=len(blob))
        if target:
            view['target'] = target
        self.data.extend(blob)
        self.views.append(view)
        return len(self.views) - 1

    def accessor(self, values, kind, ctype=5126, target=34962, bounds=False, normalized=False):
        n = COMPONENTS[kind]
        flat = [c for v in values for c in v] if n > 1 else list(values)
        fmt = COMPONENT_FORMATS[ctype]
        blob = struct.pack(f'<{len(flat)}{fmt}', *flat)
        acc = dict(bufferView=self.view(blob, target), componentType=ctype, count=len(values), type=kind)
        if normalized:
            acc['normalized'] = True
        if bounds:
            stored = struct.unpack(f'<{len(flat)}{fmt}', blob)        # bounds of the stored float32 values
            acc['min'] = [min(stored[k::n]) for k in range(n)]
            acc['max'] = [max(stored[k::n]) for k in range(n)]
        self.accessors.append(acc)
        return len(self.accessors) - 1


def _texture_images(textures):
    """{image name: (width, height, rgba)} decoder over ZTEX blobs, plus the total image count."""
    ztex = _ztex_module()
    index = {}
    for raw in textures:
        for i, image in enumerate(ztex.parse(raw)['images']):
            index.setdefault(image['name'], (raw, i))
    cache = {}

    def get(name):
        if name not in index:
            if len(index) != 1:
                return None
            name = next(iter(index))      # binding is by slot: a lone image belongs to the model
        if name not in cache:
            raw, i = index[name]
            cache[name] = (name,) + tuple(ztex.decode(raw, i))
        return cache[name]
    return get, ztex


def export_gltf(raw, textures=(), up='y'):
    """ZMDL (+ ZTEX blobs whose images the materials name) -> binary glTF 2.0 (.glb bytes).

    Bones become a node hierarchy and one skin (stored inverse bind matrices); every mesh is
    a skinned primitive in bind pose model space, rigid meshes included (weight 1 on their
    bone), so posing the armature moves everything as in game. up='z' adds a root rotation
    for weapons/tools (blade +z shown upright in Blender); import with the same `up`.
    Positions, triangles and winding are otherwise unchanged; UV v is flipped to glTF's
    top-left origin, colours are clamped to 0..1, textures are embedded as PNG."""
    require(up in ('y', 'z'), 'up must be y or z')
    model = parse(raw)
    bones = model['bones']
    out = _GlbBuilder()
    nodes, roots = [], []
    for bone in bones:
        t, q, s = _decompose(bone['local'])
        node = dict(name=bone['name'])
        if any(abs(c) > 1e-9 for c in t):
            node['translation'] = list(t)
        if abs(q[3] - 1) > 1e-9:
            node['rotation'] = list(q)
        if any(abs(c - 1) > 1e-9 for c in s):
            node['scale'] = list(s)
        nodes.append(node)
    for i, bone in enumerate(bones):
        if 0 <= bone['parent'] < len(bones) and bone['parent'] != i:
            nodes[bone['parent']].setdefault('children', []).append(i)
        else:
            roots.append(i)
    gltf = dict(asset=dict(version='2.0', generator='fl_zmdl.py (Fantasy Life ZMDL -> glTF)'),
                extras=dict(zmdl=dict(up=up, bound=list(model['bound']))),
                scene=0, scenes=[dict(name='zmdl', nodes=[])], nodes=nodes, meshes=[], materials=[])
    get_texture, ztex = _texture_images(textures)
    images, gl_textures, image_index = [], [], {}
    mesh_material = {}
    for mat in model['materials']:
        entry = dict(name=mat['name'], extras=dict(zmdl_texture=mat['texture']),
                     pbrMetallicRoughness=dict(metallicFactor=0.0, roughnessFactor=1.0))
        image = get_texture(mat['texture']) if textures else None
        if image:
            name, width, height, rgba = image
            if name not in image_index:
                view = out.view(ztex.png_encode(width, height, rgba))
                images.append(dict(name=name, mimeType='image/png', bufferView=view))
                gl_textures.append(dict(source=len(images) - 1, sampler=0))
                image_index[name] = (len(gl_textures) - 1, any(a < 255 for a in rgba[3::4]))
            tex, alpha = image_index[name]
            entry['pbrMetallicRoughness']['baseColorTexture'] = dict(index=tex)
            if alpha:
                entry.update(alphaMode='MASK', alphaCutoff=0.5)
        gltf['materials'].append(entry)
        mesh_material.setdefault(mat['mesh'], len(gltf['materials']) - 1)
    if images:
        gltf.update(images=images, textures=gl_textures,
                    samplers=[dict(magFilter=9729, minFilter=9729, wrapS=10497, wrapT=10497)])
    mesh_nodes = []
    joint_type = 5121 if len(bones) <= 256 else 5123
    for m, (verts, groups) in enumerate(bind_pose(raw, model)):
        if not verts:
            continue
        attrs = dict(POSITION=out.accessor([v['position'] for v in verts], 'VEC3', bounds=True))
        if 'normal' in verts[0]:
            attrs['NORMAL'] = out.accessor([_unit(v['normal']) for v in verts], 'VEC3')
        for k in range(3):
            if f'uv{k}' in verts[0]:
                attrs[f'TEXCOORD_{k}'] = out.accessor([(v[f'uv{k}'][0], 1.0 - v[f'uv{k}'][1]) for v in verts], 'VEC2')
        if 'colour' in verts[0]:
            attrs['COLOR_0'] = out.accessor([tuple(min(1.0, max(0.0, c)) for c in (tuple(v['colour']) + (1.0,))[:4])
                                             for v in verts], 'VEC4')
        if bones:
            joints, weights = [], []
            for v in verts:
                infl = v['influences'] or [(0, 1.0)]
                total = sum(w for _, w in infl) or 1.0
                pad = [(0, 0.0)] * (4 - len(infl))
                joints.append(tuple(b for b, _ in infl + pad))
                weights.append(tuple(w / total for _, w in infl + pad))
            attrs['JOINTS_0'] = out.accessor(joints, 'VEC4', joint_type)
            attrs['WEIGHTS_0'] = out.accessor(weights, 'VEC4')
        flat = [i for _, _, local in groups for i in local]
        index_type = 5123 if len(verts) < 65536 else 5125
        primitive = dict(attributes=attrs, indices=out.accessor(flat, 'SCALAR', index_type, 34963), mode=4)
        if m in mesh_material:
            primitive['material'] = mesh_material[m]
        gltf['meshes'].append(dict(name=f'mesh_{m}', primitives=[primitive],
                                   extras=dict(zmdl_mesh=m, palettes=[list(p) for p, _, _ in groups],
                                               modes=[mode for _, mode, _ in groups])))
        node = dict(name=f'mesh_{m}', mesh=len(gltf['meshes']) - 1)
        if bones:
            node['skin'] = 0
        nodes.append(node)
        mesh_nodes.append(len(nodes) - 1)
    if bones:
        ibm = [tuple(b['inverse_bind'][r][c] for c in range(4) for r in range(4)) for b in bones]  # column-major
        skin = dict(name='zmdl_skeleton', joints=list(range(len(bones))),
                    inverseBindMatrices=out.accessor(ibm, 'MAT4', target=None))
        if len(roots) == 1:
            skin['skeleton'] = roots[0]
        gltf['skins'] = [skin]
    scene = gltf['scenes'][0]['nodes']
    if up == 'z':
        # skinned meshes follow their joints, so they stay root nodes (glTF ignores their transform)
        nodes.append(dict(name='zmdl_up_z', rotation=list(UP_Z_ROTATION),
                          children=roots + ([] if bones else mesh_nodes)))
        scene.extend([len(nodes) - 1] + (mesh_nodes if bones else []))
    else:
        scene.extend(roots + mesh_nodes)
    if not gltf['meshes']:
        del gltf['meshes']
    gltf['accessors'], gltf['bufferViews'] = out.accessors, out.views
    gltf['buffers'] = [dict(byteLength=len(out.data))]
    return pack_glb(gltf, bytes(out.data))


def pack_glb(gltf, binary):
    text = json.dumps(gltf, separators=(',', ':')).encode('utf-8')
    text += b' ' * (-len(text) % 4)
    binary = binary + b'\0' * (-len(binary) % 4)
    total = 12 + 8 + len(text) + (8 + len(binary) if binary else 0)
    out = bytearray(GLB_MAGIC + struct.pack('<2I', 2, total))
    out += struct.pack('<2I', len(text), GLB_JSON) + text
    if binary:
        out += struct.pack('<2I', len(binary), GLB_BIN) + binary
    return bytes(out)


# --------------------------------------------------------------------------- glTF 2.0 reading
SUPPORTED_EXTENSIONS = {'KHR_mesh_quantization', 'KHR_materials_unlit', 'KHR_texture_transform',
                        'KHR_materials_emissive_strength', 'KHR_materials_specular', 'KHR_materials_ior'}


class Gltf:
    """Minimal glTF 2.0 reader (.glb or .gltf with embedded/external buffers)."""

    def __init__(self, data, resolve=None):
        self.data = data
        binary = None
        if data[:4] == GLB_MAGIC:
            version, length = struct.unpack_from('<2I', data, 4)
            require(version == 2, f'unsupported glb version {version}')
            require(length <= len(data), 'truncated glb')
            pos, doc = 12, None
            while pos + 8 <= length:
                size, kind = struct.unpack_from('<2I', data, pos)
                chunk = data[pos + 8:pos + 8 + size]
                require(len(chunk) == size, 'truncated glb chunk')
                if kind == GLB_JSON:
                    doc = json.loads(chunk.decode('utf-8'))
                elif kind == GLB_BIN and binary is None:
                    binary = chunk
                pos += 8 + size + (-size % 4)
            require(doc is not None, 'glb without JSON chunk')
        else:
            try:
                doc = json.loads(data.decode('utf-8-sig'))
            except (UnicodeDecodeError, ValueError) as error:
                raise ZmdlError(f'not a glTF file ({error})') from None
        require(str(doc.get('asset', {}).get('version', '')).startswith('2'), 'only glTF 2.0 is supported')
        unsupported = set(doc.get('extensionsRequired', [])) - SUPPORTED_EXTENSIONS
        require(not unsupported, f'unsupported required glTF extensions {sorted(unsupported)} '
                '(export without Draco/meshopt compression)')
        self.doc = doc
        self.buffers = []
        for i, buffer in enumerate(doc.get('buffers', [])):
            uri = buffer.get('uri')
            if uri is None:
                require(i == 0 and binary is not None, 'buffer without data')
                blob = binary
            elif uri.startswith('data:'):
                blob = base64.b64decode(uri.split(',', 1)[1])
            else:
                require(resolve is not None, f'external buffer {uri!r} needs a base folder')
                from urllib.parse import unquote
                blob = resolve(unquote(uri))
            require(len(blob) >= buffer.get('byteLength', 0), f'buffer {i} is shorter than declared')
            self.buffers.append(blob)
        self.nodes = doc.get('nodes', [])
        self.parent = {}
        for i, node in enumerate(self.nodes):
            for child in node.get('children', []):
                self.parent[child] = i
        self._world = {}

    def accessor(self, index):
        acc = self.doc['accessors'][index]
        n, fmt = COMPONENTS[acc['type']], COMPONENT_FORMATS[acc['componentType']]
        count = acc['count']
        size = struct.calcsize('<' + fmt)
        if 'bufferView' in acc:
            view = self.doc['bufferViews'][acc['bufferView']]
            buf = self.buffers[view['buffer']]
            start = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
            stride = view.get('byteStride') or n * size
            if acc['type'] == 'MAT4' or n * size % 4 == 0 or 'byteStride' in view:
                pass
            require(count == 0 or start + (count - 1) * stride + n * size <= view.get('byteOffset', 0) + view['byteLength']
                    and view.get('byteOffset', 0) + view['byteLength'] <= len(buf), f'accessor {index} out of bounds')
            if stride == n * size:
                flat = struct.unpack_from(f'<{count * n}{fmt}', buf, start)
                values = [tuple(flat[k * n:(k + 1) * n]) for k in range(count)]
            else:
                values = [struct.unpack_from(f'<{n}{fmt}', buf, start + k * stride) for k in range(count)]
        else:
            values = [(0,) * n] * count
        sparse = acc.get('sparse')
        if sparse:
            idx = sparse['indices']
            iview = self.doc['bufferViews'][idx['bufferView']]
            ifmt = COMPONENT_FORMATS[idx['componentType']]
            ipos = iview.get('byteOffset', 0) + idx.get('byteOffset', 0)
            where = struct.unpack_from(f'<{sparse["count"]}{ifmt}', self.buffers[iview['buffer']], ipos)
            vals = sparse['values']
            vview = self.doc['bufferViews'][vals['bufferView']]
            vpos = vview.get('byteOffset', 0) + vals.get('byteOffset', 0)
            flat = struct.unpack_from(f'<{sparse["count"] * n}{fmt}', self.buffers[vview['buffer']], vpos)
            values = list(values)
            for k, at in enumerate(where):
                values[at] = tuple(flat[k * n:(k + 1) * n])
        if acc.get('normalized') and acc['componentType'] in NORMALIZE:
            d = NORMALIZE[acc['componentType']]
            values = [tuple(max(c / d, -1.0) for c in v) for v in values]
        return values

    def local(self, index):
        node = self.nodes[index]
        if 'matrix' in node:
            m = node['matrix']
            return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
        return _compose(node.get('translation', (0, 0, 0)), node.get('rotation', (0, 0, 0, 1)),
                        node.get('scale', (1, 1, 1)))

    def world(self, index):
        if index not in self._world:
            chain, i = [], index
            while i is not None:
                require(i not in chain, 'node hierarchy has a cycle')
                chain.append(i)
                i = self.parent.get(i)
            m = _identity()
            for i in reversed(chain):
                m = _mat_mul(m, self.local(i))
            self._world[index] = m
        return self._world[index]

    def ancestors(self, index):
        while index is not None:
            yield index
            index = self.parent.get(index)

    def scene_nodes(self):
        scenes = self.doc.get('scenes')
        if not scenes:
            return [i for i in range(len(self.nodes)) if i not in self.parent]
        roots = scenes[self.doc.get('scene', 0)].get('nodes', [])
        out, stack = [], list(roots)
        while stack:
            i = stack.pop()
            out.append(i)
            stack.extend(self.nodes[i].get('children', []))
        return sorted(set(out))


def _triangles(indices, mode):
    if mode == 4:
        require(len(indices) % 3 == 0, 'triangle list length is not a multiple of 3')
        return [tuple(indices[k:k + 3]) for k in range(0, len(indices), 3)]
    if mode == 5:
        return [(indices[k], indices[k + 1], indices[k + 2]) if k % 2 == 0 else
                (indices[k + 1], indices[k], indices[k + 2]) for k in range(len(indices) - 2)]
    if mode == 6:
        return [(indices[0], indices[k], indices[k + 1]) for k in range(1, len(indices) - 1)]
    raise ZmdlError(f'primitive mode {mode} is not triangles (points/lines cannot become a ZMDL mesh)')


def read_gltf_primitives(data, up='y', resolve=None):
    """Every triangle primitive of the default scene, baked to model space.

    Skinned primitives are evaluated in their rest pose (joint world * inverse bind); others
    use their node's world matrix. up='z' undoes export_gltf's weapon root rotation (and
    Blender's z-up -> y-up conversion). Returns (Gltf, [primitive dicts])."""
    require(up in ('y', 'z'), 'up must be y or z')
    g = Gltf(data, resolve)
    to_model = _identity() if up == 'y' else _compose(q=(-UP_Z_ROTATION[0], 0.0, 0.0, UP_Z_ROTATION[3]))
    materials = g.doc.get('materials', [])
    prims = []
    for n in g.scene_nodes():
        node = g.nodes[n]
        if 'mesh' not in node:
            continue
        mesh = g.doc['meshes'][node['mesh']]
        skin = g.doc['skins'][node['skin']] if 'skin' in node else None
        joint_mats = []
        if skin:
            ibms = (g.accessor(skin['inverseBindMatrices']) if 'inverseBindMatrices' in skin
                    else [tuple(_identity()[r][c] for c in range(4) for r in range(4))] * len(skin['joints']))
            for joint, ibm in zip(skin['joints'], ibms):
                ibm = [[ibm[c * 4 + r] for c in range(4)] for r in range(4)]
                joint_mats.append(_mat_mul(to_model, _mat_mul(g.world(joint), ibm)))
        node_mat = _mat_mul(to_model, g.world(n))
        for p, primitive in enumerate(mesh.get('primitives', [])):
            attrs = primitive['attributes']
            require('POSITION' in attrs, f'mesh {mesh.get("name", node["mesh"])} has a primitive without positions')
            positions = g.accessor(attrs['POSITION'])
            normals = g.accessor(attrs['NORMAL']) if 'NORMAL' in attrs else None
            uvs = [[(u, 1.0 - v) for u, v in g.accessor(attrs[f'TEXCOORD_{k}'])] if f'TEXCOORD_{k}' in attrs else None
                   for k in range(3)]
            colours = None
            if 'COLOR_0' in attrs:
                colours = [tuple(c) + (1.0,) * (4 - len(c)) for c in g.accessor(attrs['COLOR_0'])]
            influences = [[] for _ in positions]
            k = 0
            while skin and f'JOINTS_{k}' in attrs and f'WEIGHTS_{k}' in attrs:
                for v, (js, ws) in enumerate(zip(g.accessor(attrs[f'JOINTS_{k}']), g.accessor(attrs[f'WEIGHTS_{k}']))):
                    influences[v].extend((int(j), w) for j, w in zip(js, ws) if w > 0)
                k += 1
            idx = g.accessor(primitive['indices']) if 'indices' in primitive else None
            idx = [i[0] for i in idx] if idx is not None else list(range(len(positions)))
            require(all(i < len(positions) for i in idx), 'index out of range in glTF primitive')
            tris = _triangles(idx, primitive.get('mode', 4))
            out_p, out_n = [], []
            flips = 0
            for v, pos in enumerate(positions):
                infl = influences[v]
                total = sum(w for _, w in infl)
                if skin and total > 0:
                    m = [[sum(w * joint_mats[j][r][c] for j, w in infl) / total for c in range(4)] for r in range(4)]
                else:
                    m = node_mat
                out_p.append(_mat_point(m, pos))
                if normals:
                    out_n.append(_unit(_mat_dir(_normal_matrix(m) if m is not node_mat else node_normal(node_mat),
                                                normals[v])))
                flips += _det3(m) < 0
            if flips * 2 > len(positions):           # mirrored transform: keep counter-clockwise front faces
                tris = [(a, c, b) for a, b, c in tris]
            material = materials[primitive['material']] if 'material' in primitive else {}
            joint_nodes = skin['joints'] if skin else []
            prims.append(dict(
                node=n, node_name=node.get('name'), mesh_name=mesh.get('name'), primitive=p,
                material=material.get('name'), positions=out_p, normals=out_n or None, uvs=uvs, colours=colours,
                influences=[[(joint_nodes[j], w / (sum(x for _, x in infl) or 1)) for j, w in infl
                             if j < len(joint_nodes)] for infl in influences],
                triangles=[t for t in tris if len(set(t)) == 3]))
    require(prims, 'the glTF scene has no mesh')
    return g, prims


_NODE_NORMALS = {}


def node_normal(m):
    key = id(m)
    if key not in _NODE_NORMALS or _NODE_NORMALS[key][0] is not m:
        _NODE_NORMALS[key] = (m, _normal_matrix(m))
    return _NODE_NORMALS[key][1]


# --------------------------------------------------------------------------- glTF 2.0 -> ZMDL
def outline_normals(positions, triangles, normals=None, precision=4):
    """Smooth per-position normals (angle-weighted face normals over welded positions), as the
    game's inverted-hull outline expects in attribute 8; also a smooth-shading fallback."""
    keys = [tuple(round(c, precision) for c in p) for p in positions]
    acc = {}
    for a, b, c in triangles:
        pa, pb, pc = positions[a], positions[b], positions[c]
        e1 = tuple(pb[k] - pa[k] for k in range(3))
        e2 = tuple(pc[k] - pa[k] for k in range(3))
        face = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
        if not any(face):
            continue
        face = _unit(face)
        for i, j, k in ((a, b, c), (b, c, a), (c, a, b)):
            u = _unit(tuple(positions[j][t] - positions[i][t] for t in range(3)), (0, 0, 0))
            w = _unit(tuple(positions[k][t] - positions[i][t] for t in range(3)), (0, 0, 0))
            angle = math.acos(max(-1.0, min(1.0, sum(u[t] * w[t] for t in range(3)))))
            total = acc.setdefault(keys[i], [0.0, 0.0, 0.0])
            for t in range(3):
                total[t] += face[t] * angle
    out = []
    for v, key in enumerate(keys):
        fallback = normals[v] if normals else (0.0, 1.0, 0.0)
        out.append(_unit(acc[key], fallback) if key in acc else _unit(fallback))
    return out


def _assign_meshes(model, prims, mesh_map):
    by_material = {}
    for mat in model['materials']:
        by_material.setdefault(mat['name'], mat['mesh'])
    count = len(model['meshes'])

    def resolve(value):
        if isinstance(value, int):
            return value
        require(value in by_material, f'mesh_map value {value!r} is no donor material')
        return by_material[value]

    targets = []
    for p in prims:
        names = [n for n in (p['material'], p['mesh_name'], p['node_name']) if n]
        names += [re.sub(r'\.\d{3}$', '', n) for n in names]           # Blender duplicates: name.001
        target = None
        if mesh_map:
            target = next((resolve(mesh_map[n]) for n in names if n in mesh_map), None)
        if target is None:
            target = next((by_material[n] for n in names[:1] + names[3:4] if n in by_material), None)
        if target is None:
            target = next((int(m.group(1)) for n in names if (m := re.match(r'mesh_(\d+)', n))), None)
        if target is None and count == 1:
            target = 0
        require(target is not None, f'cannot tell which donor mesh glTF primitive {names[:3]} replaces: name its '
                f'material after a donor material ({sorted(by_material)}) or add a mesh_map entry')
        require(0 <= target < count, f'donor has no mesh {target}')
        targets.append(target)
    return targets


def _bone_lookup(model, g):
    names = {b['name']: i for i, b in enumerate(model['bones'])}

    def bone_of(node):
        """Donor bone for a glTF node: same name, else its nearest named ancestor."""
        for i in g.ancestors(node):
            name = g.nodes[i].get('name')
            if name in names:
                return names[name]
            if name and re.sub(r'\.\d{3}$', '', name) in names:
                return names[re.sub(r'\.\d{3}$', '', name)]
        return None
    return names, bone_of


def import_gltf(raw, data, mesh_map=None, bone=None, unmapped='hide', up=None, resolve=None):
    """Replace a donor ZMDL's geometry with a glTF scene; returns (zmdl bytes, report).

    The donor keeps skeleton, materials, attribute layouts and everything else. Each glTF
    primitive goes to a donor mesh: by `mesh_map` ({glTF material/mesh/node name: donor mesh
    index or material name}), by material name, by a `mesh_N` name, or to the only mesh.
    Rigid donor meshes (mode 0) store vertices in bone space (one bone per vertex, `bone`
    overrides it for meshes without a bone-index attribute); smooth meshes (mode 1) get the
    four strongest joint weights, glTF joints mapped onto donor bones by name (else the
    nearest named ancestor), split into face groups of at most 20 bones. Outline normals are
    recomputed. unmapped='hide' collapses donor meshes the glTF does not replace to one
    degenerate triangle; 'keep' leaves them unchanged."""
    require(unmapped in ('hide', 'keep'), "unmapped must be 'hide' or 'keep'")
    model = parse(raw)
    if up is None:
        up = 'y'
        if data[:4] == GLB_MAGIC or data.lstrip()[:1] == b'{':
            try:
                up = Gltf(data, resolve).doc.get('extras', {}).get('zmdl', {}).get('up', 'y')
            except ZmdlError:
                pass
    g, prims = read_gltf_primitives(data, up, resolve)
    targets = _assign_meshes(model, prims, mesh_map)
    names, bone_of = _bone_lookup(model, g)
    forced = None
    if bone is not None:
        require(bone in names, f'donor has no bone {bone!r} ({sorted(names)})')
        forced = names[bone]
    binds = bind_matrices(model)
    inverse, inverse_normals = [], []
    for b in model['bones']:
        m = b['inverse_bind']
        if abs(_det3(m)) < 1e-12:
            m = _identity()
        inverse.append(m)
        inverse_normals.append(_normal_matrix(m))
    # outline normals over the whole model in model space (continuous across material seams)
    all_pos, all_tris, offsets, base = [], [], [], 0
    for p in prims:
        offsets.append(base)
        all_pos.extend(p['positions'])
        all_tris.extend((a + base, b + base, c + base) for a, b, c in p['triangles'])
        base += len(p['positions'])
    all_normals = [n for p in prims for n in (p['normals'] or [None] * len(p['positions']))]
    smooth = outline_normals(all_pos, all_tris)
    report = dict(meshes={}, warnings=[], up=up)
    replacements = {}
    for m, mesh in enumerate(model['meshes']):
        chosen = [k for k, t in enumerate(targets) if t == m]
        if not chosen:
            if unmapped == 'hide' and mesh['vertex_count'] and mesh['groups']:
                first = raw[mesh['vertex_offset']:mesh['vertex_offset'] + mesh['stride_words'] * 4]
                group = mesh['groups'][0]
                replacements[m] = dict(vertices=first, groups=[dict(nodes=group['nodes'], mode=group['mode'],
                                                                    indices=struct.pack('<3H', 0, 0, 0))])
                report['meshes'][m] = dict(hidden=True)
            continue
        require(mesh['groups'], f'donor mesh {m} has no face group to copy')
        a = mesh['attributes']
        mode = mesh['groups'][0]['mode']
        donor_palette = mesh['groups'][0]['nodes']
        # merged vertex list (model space) with per-vertex donor bone influences
        verts, tris = [], []
        for k in chosen:
            p, off = prims[k], offsets[k]
            fallback = forced if forced is not None else bone_of(p['node'])
            start = len(verts)
            for v in range(len(p['positions'])):
                infl = {}
                for joint, w in p['influences'][v]:
                    b = bone_of(joint)
                    require(b is not None or not model['bones'],
                            f'glTF joint {g.nodes[joint].get("name")!r} matches no donor bone (or ancestor)')
                    infl[b] = infl.get(b, 0.0) + w
                if not infl:
                    b = fallback if fallback is not None else (donor_palette[0] if donor_palette else 0)
                    infl = {b: 1.0}
                vert = dict(position=p['positions'][v],
                            normal=p['normals'][v] if p['normals'] else smooth[off + v],
                            outline_normal=smooth[off + v],
                            colour=p['colours'][v] if p['colours'] else (1.0, 1.0, 1.0, 1.0),
                            influences=sorted(infl.items(), key=lambda kv: -kv[1]))
                for t in range(3):
                    vert[f'uv{t}'] = p['uvs'][t][v] if p['uvs'][t] else (0.0, 0.0)
                verts.append(vert)
            tris.extend((x + start, y + start, z + start) for x, y, z in p['triangles'])
        if not tris:
            report['warnings'].append(f'mesh {m}: no triangles in the glTF primitives')
        for name in ('uv0', 'uv1', 'colour'):
            have = any((prims[k]['uvs'][int(name[2])] if name.startswith('uv') else prims[k]['colours'])
                       for k in chosen)
            if have and not a[name]['count']:
                report['warnings'].append(f'mesh {m}: donor layout has no {name}; dropped')
        if mode == 0 and not a['node']['count']:
            slot = int(a['node']['default'][0])
            require(slot < len(donor_palette), f'donor mesh {m}: default bone slot outside its palette')
            single = forced if forced is not None else donor_palette[slot]
            for v in verts:
                if any(b != single for b, _ in v['influences']):
                    report['warnings'].append(f'mesh {m}: rigid on bone {model["bones"][single]["name"]}; '
                                              'other joint weights ignored')
                    break
                v['influences'] = [(single, 1.0)]
        elif mode == 0:
            for v in verts:
                v['influences'] = v['influences'][:1]
        else:
            require(a['node']['count'] and a['weight']['count'],
                    f'donor mesh {m} is skinned without per-vertex bone indices/weights; pick a donor mesh '
                    'with both (e.g. the body mesh of a unit)')
            limit = min(a['node']['count'], a['weight']['count'], 4)
            for v in verts:
                top = v['influences'][:limit]
                total = sum(w for _, w in top) or 1.0
                v['influences'] = [(b, w / total) for b, w in top]
        groups = _split_groups(verts, tris)
        vbytes, group_out = bytearray(), []
        count = 0
        for palette, group_tris in groups:
            slot = {b: s for s, b in enumerate(palette)}
            local, remap = [], {}
            records = []
            for tri in group_tris:
                for i in tri:
                    if i not in remap:
                        remap[i] = count + len(records)
                        records.append(_zmdl_vertex(verts[i], mesh, mode, slot, binds, inverse, inverse_normals,
                                                    model['bones']))
                    local.append(remap[i])
            vbytes += pack_vertices(mesh, records)
            count += len(records)
            group_out.append(dict(nodes=palette, mode=mode, indices=struct.pack(f'<{len(local)}H', *local)))
        require(count <= 65535, f'mesh {m}: {count} vertices after splitting exceed the u16 index range; '
                'split it into more materials/meshes')
        replacements[m] = dict(vertices=bytes(vbytes), groups=group_out)
        report['meshes'][m] = dict(vertices=count, triangles=len(tris), groups=[list(p) for p, _ in groups],
                                   mode=mode, sources=[prims[k]['material'] or prims[k]['mesh_name'] for k in chosen])
    report['warnings'] = list(dict.fromkeys(report['warnings']))
    built = write_meshes(raw, replacements)
    validate(built)
    return built, report


def _split_groups(verts, tris):
    """Greedy face groups whose bone palettes stay within MAX_PALETTE."""
    if not tris:
        bones = sorted({b for v in verts for b, _ in v['influences']}) or [0]
        return [(bones[:1], [])]
    def bones_of(tri):
        return frozenset(b for i in tri for b, _ in verts[i]['influences'])
    order = sorted(range(len(tris)), key=lambda t: sorted(bones_of(tris[t])))
    groups, palette, current = [], [], []
    for t in order:
        need = bones_of(tris[t])
        require(len(need) <= MAX_PALETTE, 'one triangle uses more than 20 bones')
        if len(set(palette) | need) > MAX_PALETTE:
            groups.append((palette, current))
            palette, current = [], []
        palette.extend(sorted(need - set(palette)))
        current.append(tris[t])
    groups.append((palette, current))
    return groups


def _zmdl_vertex(v, mesh, mode, slot, binds, inverse, inverse_normals, bones):
    record = {}
    a = mesh['attributes']
    position, normal, outline = v['position'], v['normal'], v['outline_normal']
    if mode == 0 and bones:
        b = v['influences'][0][0]
        position = _mat_point(inverse[b], position)
        normal = _unit(_mat_dir(inverse_normals[b], normal))
        outline = _unit(_mat_dir(inverse_normals[b], outline))
    values = dict(position=position, normal=normal, outline_normal=outline, colour=v['colour'],
                  uv0=v['uv0'], uv1=v['uv1'], uv2=v['uv2'])
    infl = v['influences'] + [(None, 0.0)] * 4
    values['node'] = [float(slot[b]) if b is not None else 0.0 for b, _ in infl[:4]]
    values['weight'] = [w for _, w in infl[:4]]
    for name, attr in a.items():
        if attr['count']:
            data = list(values[name]) + [0.0] * 4
            record[name] = tuple(data[:attr['count']])
    return record


def write_meshes(raw, replacements):
    """Return new zmdl bytes with replaced vertex buffers and face groups.

    replacements: {mesh_index: dict(vertices=bytes, groups=[dict(nodes, mode, indices=bytes)])}.
    Group records and palettes are rewritten in place when they fit (same group count, no
    palette longer than before); otherwise a new group table and palettes are appended to the
    metadata, before the buffers. Buffers keep rebuild()'s order and alignment."""
    model = parse(raw)
    blobs = _buffers(model)
    require(blobs, 'model has no meshes')
    bone_count = len(model['bones'])
    out = bytearray(raw[:blobs[0][0]])
    plan = []
    group_headers = {}
    for m, mesh in enumerate(model['meshes']):
        rep = replacements.get(m)
        if rep is None:
            plan.append(((mesh['vertex_offset'], 0), 'v', m, None,
                         raw[mesh['vertex_offset']:mesh['vertex_offset'] + mesh['vertex_words'] * 4]))
            for g, group in enumerate(mesh['groups']):
                plan.append(((group['index_offset'], 0), 'i', m, g,
                             raw[group['index_offset']:group['index_offset'] + group['index_count'] * 2]))
                group_headers[(m, g)] = group['header']
            continue
        stride = mesh['stride_words'] * 4
        vbytes, groups = rep['vertices'], rep['groups']
        require(len(vbytes) % stride == 0 and vbytes, f'mesh {m}: vertex data is not a whole number of vertices')
        count = len(vbytes) // stride
        require(count <= 65536, f'mesh {m}: too many vertices for u16 indices')
        require(groups, f'mesh {m}: at least one face group required')
        for group in groups:
            require(len(group['indices']) % 6 == 0, 'index buffers are triangle lists')
            require(all(i < count for i in struct.unpack(f'<{len(group["indices"]) // 2}H', group['indices'])),
                    'index out of range')
            require(0 < len(group['nodes']) <= MAX_PALETTE, f'palettes hold 1..{MAX_PALETTE} bones')
            require(all(0 <= b < max(bone_count, 1) and b < 256 for b in group['nodes']), 'palette bone out of range')
        original = mesh['groups']
        in_place = len(groups) == len(original) and all(
            len(new['nodes']) <= len(old['nodes']) for new, old in zip(groups, original))
        if in_place:
            for g, (new, old) in enumerate(zip(groups, original)):
                nodes_off = struct.unpack_from('<I', out, old['header'])[0]
                out[nodes_off:nodes_off + len(new['nodes'])] = bytes(new['nodes'])
                struct.pack_into('<I', out, old['header'] + 4, len(new['nodes']))
                struct.pack_into('<I', out, old['header'] + 16, new['mode'])
                group_headers[(m, g)] = old['header']
        else:
            out.extend(b'\0' * (-len(out) % 4))
            table = len(out)
            out.extend(bytes(GROUP_SIZE * len(groups)))
            for g, new in enumerate(groups):
                out.extend(b'\0' * (-len(out) % 4))
                nodes_off = len(out)
                out.extend(bytes(new['nodes']))
                struct.pack_into('<5I', out, table + g * GROUP_SIZE, nodes_off, len(new['nodes']), 0, 0, new['mode'])
                group_headers[(m, g)] = table + g * GROUP_SIZE
            out.extend(b'\0' * (-len(out) % 4))
            struct.pack_into('<2I', out, mesh['header'] + 0xb4, table, len(groups))
        plan.append(((mesh['vertex_offset'], 0), 'v', m, None, vbytes))
        last = original[-1]['index_offset'] if original else mesh['vertex_offset']
        for g, group in enumerate(groups):
            key = (original[g]['index_offset'], 0) if g < len(original) else (last, g)
            plan.append((key, 'i', m, g, group['indices']))
    plan.sort(key=lambda item: (item[0], item[1] != 'v'))
    for _, kind, m, g, blob in plan:
        out.extend(b'\0' * (-len(out) % 4))
        if kind == 'v':
            struct.pack_into('<2I', out, model['meshes'][m]['header'] + 0xbc, len(out), len(blob) // 4)
        else:
            struct.pack_into('<2I', out, group_headers[(m, g)] + 8, len(out), len(blob) // 2)
        out.extend(blob)
    out.extend(b'\0' * (-len(out) % 4))
    return bytes(out)


def validate(raw):
    """Structural checks of a ZMDL: buffers in range, indices, palette slots and bones."""
    model = parse(raw)
    bones = len(model['bones'])
    for m, mesh in enumerate(model['meshes']):
        require(mesh['vertex_offset'] + mesh['vertex_words'] * 4 <= len(raw), f'mesh {m}: vertex buffer out of range')
        a = mesh['attributes']
        verts = vertices(raw, mesh)
        for g, group in enumerate(mesh['groups']):
            require(group['index_offset'] + group['index_count'] * 2 <= len(raw), f'mesh {m} group {g}: indices out of range')
            require(group['index_count'] % 3 == 0, f'mesh {m} group {g}: not a triangle list')
            require(len(group['nodes']) <= MAX_PALETTE, f'mesh {m} group {g}: palette over {MAX_PALETTE} bones')
            require(all(b < max(bones, 1) for b in group['nodes']), f'mesh {m} group {g}: palette bone out of range')
            for i in indices(raw, group):
                require(i < len(verts), f'mesh {m} group {g}: index {i} out of range')
                node = _value(verts[i], mesh, 'node')
                used = node[:1] if group['mode'] == 0 else [n for n, w in zip(node, _value(verts[i], mesh, 'weight')) if w > 0]
                require(all(0 <= int(round(n)) < max(len(group['nodes']), 1) for n in used),
                        f'mesh {m} group {g}: vertex {i} uses a slot outside the palette')
    return model


# --------------------------------------------------------------------------- preview renderer
def _ztex_module():
    spec = importlib.util.spec_from_file_location('fl_ztex', Path(__file__).with_name('fl_ztex.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _norm(v):
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / length for c in v)


def render(raw, texture, size=512, yaw=35.0, pitch=20.0, roll=0.0, outline=0.05, background=(0, 0, 0, 0),
           light=(-0.4, 0.6, 0.7), edge_colour=(70, 32, 26), supersample=2, up='z'):
    """Toon-style orthographic preview: texture x two-band light ramp, inverted-hull outline.

    texture: (width, height, rgba) as fl_ztex decodes it; UV v = 0 is the bottom row.
    up: 'z' for weapons (blade along +z), 'y' for units/monsters (bind pose, y up, facing +z).
    Returns top-down RGBA bytes of size x size.
    """
    model = parse(raw)
    tw, th, tex = texture
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    cr, sr = math.cos(math.radians(roll)), math.sin(math.radians(roll))

    require(up in ('y', 'z'), 'up must be y or z')

    def view(p):
        if up == 'z':
            x, z, y = p[0], -p[1], p[2]                   # model z (blade axis) up, -y towards viewer
        else:
            x, y, z = p                                   # model y up, +z towards viewer
        x, z = x * cy + z * sy, -x * sy + z * cy          # yaw about y
        y, z = y * cp - z * sp, y * sp + z * cp           # pitch about x
        x, y = x * cr - y * sr, x * sr + y * cr           # roll about view axis
        return x, y, z

    tris = []
    for mesh in model['meshes']:
        verts = vertices(raw, mesh)
        for group in mesh['groups']:
            idx = indices(raw, group)
            tris.extend(tuple(verts[i] for i in idx[k:k + 3]) for k in range(0, len(idx), 3))
    points = [view(v['position']) for tri in tris for v in tri]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.15 + 2 * outline
    cx, cyy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    n = size * supersample
    scale = n / span

    def screen(p):
        return ((p[0] - cx) * scale + n / 2, n / 2 - (p[1] - cyy) * scale, p[2])

    depth = [float('-inf')] * (n * n)
    colour = [background] * (n * n)
    lx = _norm(light)

    def raster(sv, shade):
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = sv
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-9:
            return
        minx, maxx = max(0, int(min(x0, x1, x2))), min(n - 1, int(max(x0, x1, x2)) + 1)
        miny, maxy = max(0, int(min(y0, y1, y2))), min(n - 1, int(max(y0, y1, y2)) + 1)
        for py in range(miny, maxy + 1):
            fy = py + 0.5
            for px in range(minx, maxx + 1):
                fx = px + 0.5
                w0 = ((x1 - fx) * (y2 - fy) - (x2 - fx) * (y1 - fy)) / area
                w1 = ((x2 - fx) * (y0 - fy) - (x0 - fx) * (y2 - fy)) / area
                w2 = 1 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0:
                    continue
                z = w0 * z0 + w1 * z1 + w2 * z2
                i = py * n + px
                if z > depth[i]:
                    depth[i] = z
                    colour[i] = shade(w0, w1, w2)

    # 1. inverted hull outline: back faces pushed out along the outline normal, flat edge colour
    if outline:
        for tri in tris:
            pushed = []
            for v in tri:
                o = v.get('outline_normal', v.get('normal'))
                pushed.append(screen(view(tuple(p + outline * c for p, c in zip(v['position'], o)))))
            (x0, y0, _), (x1, y1, _), (x2, y2, _) = pushed
            if (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0) > 0:  # back face (screen y points down)
                shifted = [(x, y, z - 1e-3) for x, y, z in pushed]
                raster(shifted, lambda *_: edge_colour + (255,))
    # 2. surfaces
    for tri in tris:
        sv = [screen(view(v['position'])) for v in tri]
        (x0, y0, _), (x1, y1, _), (x2, y2, _) = sv
        if (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0) >= 0:
            continue  # cull back faces (models use counter-clockwise front faces)
        normals = [_norm(view(v.get('normal', (0, 0, 1)))) for v in tri]
        uvs = [v.get('uv0', (0.0, 0.0)) for v in tri]

        def shade(w0, w1, w2, normals=normals, uvs=uvs):
            nx = w0 * normals[0][0] + w1 * normals[1][0] + w2 * normals[2][0]
            ny = w0 * normals[0][1] + w1 * normals[1][1] + w2 * normals[2][1]
            nz = w0 * normals[0][2] + w1 * normals[1][2] + w2 * normals[2][2]
            d = (nx * lx[0] + ny * lx[1] + nz * lx[2]) / (math.sqrt(nx * nx + ny * ny + nz * nz) or 1)
            # soft two-band toon ramp, like the game's cel shading
            t = max(0.0, min(1.0, (d + 0.15) * 4))
            k = 0.78 + 0.27 * t
            u = w0 * uvs[0][0] + w1 * uvs[1][0] + w2 * uvs[2][0]
            v = w0 * uvs[0][1] + w1 * uvs[1][1] + w2 * uvs[2][1]
            tx = min(tw - 1, max(0, int((u % 1.0) * tw)))
            ty = min(th - 1, max(0, int((1.0 - v % 1.0) * th)))
            o = (ty * tw + tx) * 4
            return (min(255, int(tex[o] * k)), min(255, int(tex[o + 1] * k)), min(255, int(tex[o + 2] * k)), 255)
        raster(sv, shade)
    # downsample
    out = bytearray(size * size * 4)
    ss = supersample
    for y in range(size):
        for x in range(size):
            acc = [0, 0, 0, 0]
            for dy in range(ss):
                row = (y * ss + dy) * n + x * ss
                for dx in range(ss):
                    r, g, b, a = colour[row + dx]
                    acc[0] += r * a
                    acc[1] += g * a
                    acc[2] += b * a
                    acc[3] += a
            o = (y * size + x) * 4
            if acc[3]:
                out[o:o + 4] = bytes((acc[0] // acc[3], acc[1] // acc[3], acc[2] // acc[3], acc[3] // (ss * ss)))
    return bytes(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    c = commands.add_parser('info')
    c.add_argument('zmdl', type=Path)
    c = commands.add_parser('obj')
    c.add_argument('zmdl', type=Path)
    c.add_argument('out', type=Path)
    c = commands.add_parser('gltf')
    c.add_argument('zmdl', type=Path)
    c.add_argument('out', type=Path)
    c.add_argument('--ztex', type=Path, action='append', default=[], help='ztex texture files to decode and embed')
    c.add_argument('--up', choices=('y', 'z'), default='y', help="model upright axis ('z' for weapons, 'y' for units/monsters/maps)")
    c = commands.add_parser('import-glb')
    c.add_argument('donor', type=Path, help='base ZMDL providing skeleton, materials, and layout')
    c.add_argument('glb', type=Path, help='input glTF 2.0 (.glb or .gltf) file')
    c.add_argument('out', type=Path, help='output patched ZMDL file')
    c.add_argument('--bone', default=None, help='target bone name for unskinned/rigid geometry (e.g. R_tool)')
    c.add_argument('--up', choices=('y', 'z'), default=None, help="override glb upright axis ('z' for weapons, 'y' for units)")
    c.add_argument('--unmapped', choices=('hide', 'keep'), default='hide', help='action for donor meshes not present in glb')
    c = commands.add_parser('render')
    c.add_argument('zmdl', type=Path)
    c.add_argument('ztex', type=Path)
    c.add_argument('out', type=Path)
    c.add_argument('--image', type=int, default=None, help='ztex image (default: the material texture name)')
    c.add_argument('--yaw', type=float, default=35.0)
    c.add_argument('--pitch', type=float, default=20.0)
    c.add_argument('--roll', type=float, default=0.0)
    c.add_argument('--size', type=int, default=512)
    c.add_argument('--up', choices=('y', 'z'), default='z', help='z: weapons; y: units/monsters')
    args = parser.parse_args()
    raw = args.zmdl.read_bytes()
    if args.command == 'info':
        model = parse(raw)
        print(f"zmdl v{model['version']}, bound {['%.3f' % b for b in model['bound']]}, {len(raw)} bytes")
        for m in model['materials']:
            print(f"  material {m['name']}: texture {m['texture']} (crc {m['texture_crc32']:08x}), mesh {m['mesh']}")
        for i, b in enumerate(model['bones']):
            print(f"  bone {i} {b['name']} parent {b['parent']} t={['%.3f' % v for v in b['translation']]}")
        for i, mesh in enumerate(model['meshes']):
            present = ', '.join(f"{k}x{a['count']}@{a['offset']}" for k, a in mesh['attributes'].items() if a['count'])
            print(f"  mesh {i}: {mesh['vertex_count']} vertices ({mesh['stride_words'] * 4} bytes: {present})")
            for g in mesh['groups']:
                print(f"    group: {g['index_count'] // 3} triangles, mode {g['mode']}, bones {g['nodes']}")
    elif args.command == 'obj':
        args.out.write_text(export_obj(raw))
    elif args.command == 'gltf':
        textures = [p.read_bytes() for p in args.ztex]
        glb_bytes = export_gltf(raw, textures, up=args.up)
        args.out.write_bytes(glb_bytes)
    elif args.command == 'import-glb':
        glb_data = args.glb.read_bytes()
        built, report = import_gltf(raw, glb_data, bone=args.bone, unmapped=args.unmapped, up=args.up)
        args.out.write_bytes(built)
    else:
        ztex = _ztex_module()
        traw = args.ztex.read_bytes()
        index = args.image
        if index is None:
            names = [i['name'] for i in ztex.parse(traw)['images']]
            wanted = parse(raw)['materials'][0]['texture']
            index = names.index(wanted) if wanted in names else 0
        texture = ztex.decode(traw, index)
        rgba = render(raw, texture, args.size, args.yaw, args.pitch, args.roll, up=args.up)
        ztex.png_write(args.out, args.size, args.size, rgba)


if __name__ == '__main__':
    try:
        main()
    except ZmdlError as error:
        sys.exit(f'error: {error}')
