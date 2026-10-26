"""ZMDL inspection/patching tests on a synthetic model; real-file identity checks if an extraction exists."""
import importlib.util
import os
from pathlib import Path
import struct
import unittest
import zlib

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location('fl_zmdl', ROOT / 'tools' / 'fl_zmdl.py')
zmdl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zmdl)

ARCHIVE = Path(os.environ.get('FL_EU_ARCHIVE', ROOT / 'extracted/fl_eu/archive'))
if not ARCHIVE.is_dir():
    ARCHIVE = ROOT.parents[1] / 'fl-project-blue/extracted/fl_eu/archive'
EXTRACTION = ARCHIVE / '_unnamed'
STRIDE = 11  # position 3, normal 3, uv 2, outline normal 3 (as the game's weapon models)

# a unit square (two triangles) facing +z
SQUARE = [((0, 0, 0), (0, 0, 1), (0, 1)), ((1, 0, 0), (0, 0, 1), (1, 1)),
          ((1, 1, 0), (0, 0, 1), (1, 0)), ((0, 1, 0), (0, 0, 1), (0, 0))]


def make_zmdl(vertices=SQUARE, triangles=((0, 1, 2), (0, 2, 3)), texture='tex_test'):
    """A minimal version-3 ZMDL: one material, one bone (R_tool), one mesh, one face group."""
    mat, bone, mesh = 0x34, 0x34 + 0xb4, 0x34 + 0xb4 + 0xcc
    group = mesh + 0xc4
    tex_ref = group + 0x14
    nodes = tex_ref + 0x78
    vb = nodes + 8
    vdata = b''.join(struct.pack('<11f', *p, *n, *uv, *n) for p, n, uv in vertices)
    flat = [i for t in triangles for i in t]
    ib = vb + len(vdata)
    out = bytearray(ib + len(flat) * 2)
    out[:8] = b'zmdl' + struct.pack('<I', 3)
    struct.pack_into('<4f', out, 8, 2.0, 0.5, 0.5, 0.0)
    struct.pack_into('<3I4H', out, 0x20, mat, bone, mesh, 1, 1, 1, 0x18)
    out[mat:mat + 8] = b'mat_test'
    struct.pack_into('<2I', out, mat + 0x94, tex_ref, nodes + 4)
    out[bone:bone + 6] = b'R_tool'
    ident = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    struct.pack_into('<24f', out, bone + 0x44, *(ident + ident))
    struct.pack_into('<9fh', out, bone + 0xa4, 0, 0, 0, 0, 0, 0, 1, 1, 1, -1)
    layout = [(0, 3), (3, 3), (6, 0), (6, 2), (8, 0), (8, 0), (8, 0), (8, 0), (8, 3)]
    for k, (offset, count) in enumerate(layout):
        struct.pack_into('<4f2BH', out, mesh + k * 20, 0, 0, 0, 0, offset, count, STRIDE)
    struct.pack_into('<4I', out, mesh + 0xb4, group, 1, vb, len(vdata) // 4)
    struct.pack_into('<5I', out, group, nodes, 1, ib, len(flat), 0)
    name = texture.encode()
    out[tex_ref:tex_ref + len(name)] = name
    struct.pack_into('<I', out, tex_ref + 0x70, zlib.crc32(name))
    out[nodes] = 0
    out[nodes + 4] = 0
    out[vb:ib] = vdata
    struct.pack_into(f'<{len(flat)}H', out, ib, *flat)
    out.extend(b'\0' * (-len(out) % 4))
    return bytes(out)


class Zmdl(unittest.TestCase):
    def test_parse_synthetic(self):
        raw = make_zmdl()
        model = zmdl.parse(raw)
        self.assertEqual(model['materials'][0]['texture'], 'tex_test')
        self.assertEqual(model['materials'][0]['texture_crc32'], zlib.crc32(b'tex_test'))
        self.assertEqual(model['bones'][0]['name'], 'R_tool')
        mesh = model['meshes'][0]
        self.assertEqual((mesh['vertex_count'], mesh['stride_words']), (4, 11))
        verts = zmdl.vertices(raw, mesh)
        self.assertEqual(verts[2]['position'], (1.0, 1.0, 0.0))
        self.assertEqual(verts[2]['uv0'], (1.0, 0.0))
        self.assertEqual(zmdl.indices(raw, mesh['groups'][0]), [0, 1, 2, 0, 2, 3])
        self.assertEqual(zmdl.rebuild(raw, {}), raw)

    def test_replace_mesh_relocates_buffers(self):
        raw = make_zmdl()
        verts = [dict(position=(x, y, z), normal=(0, 0, 1), uv0=(x, y), outline_normal=(0, 0, 1))
                 for x, y, z in [(0, 0, 0), (2, 0, 0), (0, 2, 0), (2, 2, 0), (1, 3, 0)]]
        tris = [(0, 1, 3), (0, 3, 2), (2, 3, 4)]
        new = zmdl.replace_mesh(raw, 0, verts, tris)
        mesh = zmdl.parse(new)['meshes'][0]
        self.assertEqual(mesh['vertex_count'], 5)
        self.assertEqual([v['position'] for v in zmdl.vertices(new, mesh)], [v['position'] for v in verts])
        self.assertEqual(zmdl.indices(new, mesh['groups'][0]), [i for t in tris for i in t])
        self.assertEqual(len(new) % 4, 0)
        self.assertEqual(new[:mesh['vertex_offset']][:0x20], raw[:0x20])  # header untouched
        self.assertEqual(zmdl.parse(new)['materials'], zmdl.parse(raw)['materials'])
        self.assertEqual(zmdl.rebuild(new, {}), new)
        with self.assertRaises(zmdl.ZmdlError):
            zmdl.replace_mesh(raw, 0, verts, [(0, 1, 9)])           # index out of range
        with self.assertRaises(zmdl.ZmdlError):
            zmdl.replace_mesh(raw, 0, [dict(verts[0], uv0=(0,))], [(0, 0, 0)])  # wrong component count

    def test_obj_and_render(self):
        raw = make_zmdl()
        obj = zmdl.export_obj(raw)
        self.assertEqual(obj.count('\nv '), 4)
        self.assertEqual(obj.count('\nf '), 2)
        texture = (2, 2, bytes([200, 100, 50, 255] * 4))
        rgba = zmdl.render(raw, texture, size=32, yaw=0, pitch=90, outline=0.05, supersample=1)
        self.assertEqual(len(rgba), 32 * 32 * 4)
        covered = [rgba[i:i + 4] for i in range(0, len(rgba), 4) if rgba[i + 3]]
        self.assertGreater(len(covered), 200)
        self.assertTrue(any(p[0] > p[2] + 60 for p in covered))  # textured, not just outline

    def test_render_unit_orientation(self):
        # units/monsters stand y-up facing +z: the +z-facing square is seen face-on with up='y'
        raw, texture = make_zmdl(), (2, 2, bytes([200, 100, 50, 255] * 4))

        def covered(**view):
            rgba = zmdl.render(raw, texture, size=32, yaw=0, pitch=0, outline=0, supersample=1, **view)
            return sum(1 for i in range(3, len(rgba), 4) if rgba[i])
        self.assertGreater(covered(up='y'), 600)
        self.assertLess(covered(up='z'), 100)       # weapon convention: the same square edge-on
        with self.assertRaises(zmdl.ZmdlError):
            covered(up='x')

    def test_rename_textures(self):
        raw = make_zmdl(texture='mon004_0001_001')
        renamed = zmdl.rename_textures(raw, {'mon004_0001_001': 'mon078_0003_001'})
        material = zmdl.parse(renamed)['materials'][0]
        self.assertEqual((material['texture'], material['texture_crc32']),
                         ('mon078_0003_001', zlib.crc32(b'mon078_0003_001')))
        self.assertEqual(len(renamed), len(raw))
        self.assertLessEqual(sum(a != b for a, b in zip(raw, renamed)), 3 + 4)   # 3 name bytes, CRC
        self.assertEqual(zmdl.parse(renamed)['meshes'], zmdl.parse(raw)['meshes'])
        for names in ({'other': 'x'}, {'mon004_0001_001': ''}, {'mon004_0001_001': 'x' * 64}):
            with self.subTest(names=names), self.assertRaises(zmdl.ZmdlError):
                zmdl.rename_textures(raw, names)

    def test_rejects_other_files(self):
        with self.assertRaises(zmdl.ZmdlError):
            zmdl.parse(b'ztex' + bytes(80))

    @unittest.skipUnless(EXTRACTION.is_dir(), 'game extraction not present')
    def test_real_models_rebuild_byte_identical(self):
        count = 0
        for path in sorted(EXTRACTION.glob('0[3-4]*.mdl'))[:300]:
            raw = path.read_bytes()
            try:
                model = zmdl.parse(raw)
            except zmdl.ZmdlError:
                continue
            if model['meshes']:
                self.assertEqual(zmdl.rebuild(raw, {}), raw, path.name)
                count += 1
        self.assertGreater(count, 100)


    def test_outline_normals(self):
        corners = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                   (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
        triangles = [
            (4, 5, 6), (4, 6, 7),  # front +Z
            (1, 0, 3), (1, 3, 2),  # back -Z
            (0, 4, 7), (0, 7, 3),  # left -X
            (5, 1, 2), (5, 2, 6),  # right +X
            (7, 6, 2), (7, 2, 3),  # top +Y
            (0, 1, 5), (0, 5, 4),  # bottom -Y
        ]
        smooth = zmdl.outline_normals(corners, triangles)
        self.assertEqual(len(smooth), len(corners))
        for n in smooth:
            self.assertAlmostEqual(sum(c * c for c in n), 1.0, places=4)
        self.assertGreater(smooth[6][0], 0.5)
        self.assertGreater(smooth[6][1], 0.5)
        self.assertGreater(smooth[6][2], 0.5)

    def test_palette_splitting_over_limit(self):
        verts = []
        for i in range(25):
            verts.append(dict(position=(i, 0, 0), influences=[(i, 1.0)]))
        triangles = [(i, i + 1, i + 2) for i in range(23)]
        groups = zmdl._split_groups(verts, triangles)
        self.assertGreater(len(groups), 1)
        for palette, tris in groups:
            self.assertLessEqual(len(palette), zmdl.MAX_PALETTE)
            pal_set = set(palette)
            for t in tris:
                for idx in t:
                    self.assertTrue(all(b in pal_set for b, _ in verts[idx]['influences']))

    def test_synthetic_gltf_roundtrip(self):
        raw = make_zmdl()
        glb = zmdl.export_gltf(raw, up='z')
        self.assertTrue(glb.startswith(b'glTF'))
        rebuilt, report = zmdl.import_gltf(raw, glb, up='z')
        self.assertEqual(len(rebuilt) % 4, 0)
        val = zmdl.validate(rebuilt)
        self.assertEqual(val['meshes'][0]['vertex_count'], 4)
        orig_v = zmdl.vertices(raw, zmdl.parse(raw)['meshes'][0])
        reb_v = zmdl.vertices(rebuilt, val['meshes'][0])
        for vo, vr in zip(orig_v, reb_v):
            for k in range(3):
                self.assertAlmostEqual(vo['position'][k], vr['position'][k], places=4)

    @unittest.skipUnless(ARCHIVE.is_dir(), 'game extraction not present')
    def test_shipped_rigid_model_glb_roundtrip(self):
        sword_path = EXTRACTION / '03804_7b0e0d07707e.mdl'
        tex_path = EXTRACTION / '03805_fcffa328b1a5.tex'
        raw = sword_path.read_bytes()
        tex_raw = tex_path.read_bytes()
        glb = zmdl.export_gltf(raw, [tex_raw], up='z')
        self.assertTrue(glb.startswith(b'glTF'))
        rebuilt, report = zmdl.import_gltf(raw, glb, up='z')
        val = zmdl.validate(rebuilt)
        self.assertEqual(len(val['meshes']), 1)
        self.assertEqual(val['meshes'][0]['vertex_count'], 66)
        self.assertEqual(val['meshes'][0]['groups'][0]['nodes'], [2])
        ztex = zmdl._ztex_module()
        tex = ztex.decode(tex_raw, 0)
        rgba = zmdl.render(rebuilt, tex, size=32, up='z')
        self.assertEqual(len(rgba), 32 * 32 * 4)
        self.assertTrue(any(a > 0 for a in rgba[3::4]))

    @unittest.skipUnless(ARCHIVE.is_dir(), 'game extraction not present')
    def test_shipped_skinned_model_glb_roundtrip(self):
        wolf_path = ARCHIVE / 'unit/mon/mon004/0001/model/mon004_0001.mdl'
        tex_path = ARCHIVE / 'unit/mon/mon004/0001/model/mon004_0001.texa'
        raw = wolf_path.read_bytes()
        tex_raw = tex_path.read_bytes()
        glb = zmdl.export_gltf(raw, [tex_raw], up='y')
        self.assertTrue(glb.startswith(b'glTF'))
        rebuilt, report = zmdl.import_gltf(raw, glb, up='y')
        val = zmdl.validate(rebuilt)
        self.assertEqual(len(val['meshes']), 1)
        self.assertEqual(val['meshes'][0]['vertex_count'], 440)
        self.assertEqual(val['meshes'][0]['groups'][0]['mode'], 1)
        bone_count = len(val['bones'])
        for node in val['meshes'][0]['groups'][0]['nodes']:
            self.assertTrue(0 <= node < bone_count)
        ztex = zmdl._ztex_module()
        tex = ztex.decode(tex_raw, 0)
        rgba = zmdl.render(rebuilt, tex, size=32, up='y')
        self.assertEqual(len(rgba), 32 * 32 * 4)
        self.assertTrue(any(a > 0 for a in rgba[3::4]))

    @unittest.skipUnless(ARCHIVE.is_dir(), 'game extraction not present')
    def test_shipped_multi_material_glb_roundtrip(self):
        attic_path = EXTRACTION / '09065_f23facdced77.mdl'
        tex_path = EXTRACTION / '09066_2ac747ebe231.tex'
        raw = attic_path.read_bytes()
        tex_raw = tex_path.read_bytes()
        glb = zmdl.export_gltf(raw, [tex_raw], up='y')
        rebuilt, report = zmdl.import_gltf(raw, glb, up='y')
        val = zmdl.validate(rebuilt)
        self.assertEqual(len(val['meshes']), 7)
        self.assertEqual(len(val['materials']), 7)
        for m in val['meshes']:
            self.assertGreater(m['vertex_count'], 0)


if __name__ == '__main__':
    unittest.main()
