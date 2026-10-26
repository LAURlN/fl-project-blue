import base64
import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import os
import unittest

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = Path(os.environ.get('FL_EU_ARCHIVE', ROOT / 'extracted/fl_eu/archive'))
if not ARCHIVE.is_dir():
    ARCHIVE = ROOT.parents[1] / 'fl-project-blue/extracted/fl_eu/archive'

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fl_map as fm


def fixture():
    """Invented two-map placements, one warp and one two-point spawn."""
    b = bytearray(fm.HEADER + 2*fm.ROW_SIZE)
    b[:4] = fm.MAGIC
    struct.pack_into('<hhHII', b, 10, 2, 2, 0, fm.HEADER, 0)
    for t in range(fm.TYPE_COUNT):
        struct.pack_into('<H', b, 30+8*t, 0xffff)
    def append(raw):
        p = len(b)
        b.extend(raw)
        return p
    warp = append(struct.pack('<11fI', 1,2,3,0,4,5,6,1,1,1,0,0))
    spawn = append(struct.pack('<5hbbBbHII', -1,2,1,2,2,0,1,0,4,0,0,0))
    conditions = append(bytes.fromhex('0600000002000000'))
    points = append(struct.pack('<4fbBBB', 1,0,1,0,-1,0,0,0) +
                    struct.pack('<4fbBBB', 2,0,2,1,0,0,4,0))
    struct.pack_into('<II', b, spawn+16, conditions, points)
    for i,(map_id,t,ref,p) in enumerate([(7,3,5,warp),(8,12,0,spawn)]):
        off = fm.HEADER+fm.ROW_SIZE*i
        struct.pack_into('<hhBbHhHII7fI', b, off, i,map_id,t,-1,0,ref,0,
                         0x04000000+i,0xffffffff,1,2,3,1,1,1,0,p)
        index = append(struct.pack('<I', off))
        struct.pack_into('<h',b,28+8*t,1)
        struct.pack_into('<I',b,32+8*t,index)
    group = append(struct.pack('<hhI',1,-1,append(struct.pack('<I',fm.HEADER+fm.ROW_SIZE))))
    maps = append(struct.pack('<hhI',7,0,0)+struct.pack('<hhI',8,1,group))
    struct.pack_into('<I',b,20,maps)
    struct.pack_into('<I',b,4,len(b)-fm.HEADER)
    return bytes(b)


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        self.doc = fm.dump(self.data)

    def test_round_trip(self):
        self.assertEqual(fm.build(self.doc), self.data)
        self.assertEqual(self.doc['map_groups'][1]['groups'][0]['rows'], [1])

    def test_coordinate_warp_and_spawn_edit(self):
        self.doc['rows'][0]['position'] = [8.5,0,-2]
        self.doc['rows'][0]['warp']['arrival_position'] = [4,0,5]
        self.doc['rows'][1]['spawn']['level'] = 6
        self.doc['rows'][1]['spawn']['points'][1]['position'] = [-1,0,2]
        out = fm.build(self.doc)
        result = fm.dump(out)
        self.assertEqual(len(out),len(self.data))
        self.assertEqual(result['rows'],self.doc['rows'])
        self.assertEqual(out[:fm.HEADER],self.data[:fm.HEADER])

    def test_clone_growth_indexes_and_groups(self):
        clone = copy.deepcopy(self.doc['rows'][1])
        clone.update(index=2,uid=0x04000002,position=[20,0,20])
        self.doc['rows'].append(clone)
        self.doc['map_groups'][1]['groups'][0]['rows'].append(2)
        with self.assertRaisesRegex(ValueError,'experimental-growth'):
            fm.build(self.doc)
        out = fm.build(self.doc,experimental_growth=True)
        result = fm.dump(out)
        self.assertEqual(result['rows'][:2],self.doc['rows'][:2])
        self.assertEqual(result['rows'][2]['position'],clone['position'])
        self.assertNotEqual(result['rows'][2]['payload_offset'],clone['payload_offset'])
        self.assertNotEqual(result['rows'][2]['spawn']['points_offset'],clone['spawn']['points_offset'])
        self.assertEqual(result['map_groups'],self.doc['map_groups'])
        self.assertEqual(fm.build(result),out)
        # The re-dumped clone owns its payload and both nested arrays.
        result['rows'][2]['spawn']['points'][0]['position'] = [9,0,9]
        result['rows'][2]['spawn']['conditions'][0] = '0600000003000000'
        edited = fm.dump(fm.build(result))
        self.assertEqual(edited['rows'][1], self.doc['rows'][1])
        self.assertEqual(edited['rows'][2]['spawn']['points'][0]['position'], [9,0,9])
        self.assertEqual(edited['rows'][2]['spawn']['conditions'][0], '0600000003000000')

    def test_warp_clone_has_independent_payload(self):
        clone = copy.deepcopy(self.doc['rows'][0])
        clone.update(index=2, uid=0x04000002)
        self.doc['rows'].append(clone)
        doc = fm.dump(fm.build(self.doc, True))
        doc['rows'][2]['warp']['arrival_position'] = [9,0,8]
        result = fm.dump(fm.build(doc))
        self.assertEqual(result['rows'][0], self.doc['rows'][0])
        self.assertEqual(result['rows'][2]['warp']['arrival_position'], [9,0,8])

    def test_opaque_bytes_and_float_bits_survive_json(self):
        data = bytearray(self.data)
        # Noncanonical NaN bits, negative zero, and unused header bytes.
        struct.pack_into('<II', data, fm.HEADER+20, 0x7fc12345, 0x80000000)
        struct.pack_into('<H', data, 8, 0xbeef)
        doc = json.loads(json.dumps(fm.dump(bytes(data))))
        self.assertEqual(fm.build(doc), bytes(data))
        doc['rows'][0]['position'][2] = 8
        out = fm.build(doc)
        self.assertEqual(out[fm.HEADER+20:fm.HEADER+28], data[fm.HEADER+20:fm.HEADER+28])
        self.assertEqual(out[8:10], data[8:10])
        doc['rows'][0]['position'][1] = 0.0
        self.assertEqual(fm.build(doc)[fm.HEADER+24:fm.HEADER+28], bytes(4))

    def test_no_growth_for_fixed_fields(self):
        self.doc['rows'][0]['reference'] = 12
        self.assertEqual(fm.dump(fm.build(self.doc))['rows'][0]['reference'],12)

    def test_bad_input(self):
        for offset,value in [(4,0),(16,1),(20,0),(32+3*8,0xffffffff)]:
            b=bytearray(self.data)
            struct.pack_into('<I',b,offset,value)
            with self.assertRaises(ValueError):fm.dump(bytes(b))
        with self.assertRaises(ValueError):fm.dump(b'garbage')

    def test_reject_unsafe_edits(self):
        for key,value in [('type',4),('payload_offset',0),('index',9),('flags',65536),
                          ('yaw',float('inf')),('reference',1.5)]:
            doc=copy.deepcopy(self.doc)
            doc['rows'][0][key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):fm.build(doc)
        self.doc['rows'][1]['spawn']['point_count']=3
        with self.assertRaises(ValueError):fm.build(self.doc)

    def test_reject_lossy_or_invalid_documents(self):
        for key,value in [('flags',0.0),('subtype',True),('position',[1,2]),
                          ('position',[1,2,'3'])]:
            doc=copy.deepcopy(self.doc)
            doc['rows'][0][key]=value
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):fm.build(doc)
        doc=copy.deepcopy(self.doc)
        doc['extra']='not represented'
        with self.assertRaises(ValueError):fm.build(doc)
        for key,value in [('choice',-2),('rows',[0]),('rows',[True])]:
            doc=copy.deepcopy(self.doc)
            doc['map_groups'][1]['groups'][0][key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):fm.build(doc,True)

    def test_remap_room_identity_and_empty_group(self):
        # A donor room's header group must follow its edited map ID.
        doc=copy.deepcopy(self.doc)
        doc['rows'][1]['map_id']=154
        with self.assertRaises(ValueError):fm.build(doc)
        doc['map_groups'][1]['map_id']=154
        result=fm.dump(fm.build(doc,True))
        self.assertEqual(result['rows'][1]['map_id'],154)
        self.assertEqual(result['map_groups'][1]['map_id'],154)

    def test_shared_payload_conflict(self):
        clone=copy.deepcopy(self.doc['rows'][0])
        clone.update(index=2,uid=0x04000002)
        self.doc['rows'].append(clone)
        data=bytearray(fm.build(self.doc,True))
        start=struct.unpack_from('<I',data,16)[0]
        struct.pack_into('<I',data,start+2*fm.ROW_SIZE+48,self.doc['rows'][0]['payload_offset'])
        shared=fm.dump(bytes(data))
        shared['rows'][0]['warp']['arrival_yaw']=1
        with self.assertRaisesRegex(ValueError,'Conflicting shared'):
            fm.build(shared)

    def test_model_inspection(self):
        b=bytearray(52+180+204)
        b[:4]=b'zmdl'
        struct.pack_into('<IIIHHHH',b,32,52,232,436,1,1,0,0)
        b[52:56]=b'mat\0'
        b[232:237]=b'root\0'
        struct.pack_into('<9fhH',b,232+164,1,2,3,0,0,0,1,1,1,-1,0)
        m=fm.inspect_model(bytes(b))
        self.assertEqual(m['materials'],['mat'])
        self.assertEqual(m['bones'][0]['translation'],[1,2,3])
        self.assertEqual(m['bones'][0]['parent'],-1)
        with self.assertRaises(ValueError):fm.inspect_model(bytes(b[:100]))

    @unittest.skipUnless(ARCHIVE.is_dir(), 'game extraction not present')
    def test_archive_map_gltf_export(self):
        archive = fm.Archive(ARCHIVE)
        glb_data = archive.gltf(150)
        self.assertTrue(glb_data.startswith(b'glTF'))
        self.assertGreater(len(glb_data), 100000)


class RttiTests(unittest.TestCase):
    def test_substring_and_bounded_vtable_preview(self):
        spec=importlib.util.spec_from_file_location('rtti',Path(fm.__file__).parent/'re/rtti.py')
        rtti=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rtti)
        data=bytearray(64)
        data[:10]=b'7cAppMap\x00\x00'
        struct.pack_into('<II',data,32,0,rtti.BASE)
        struct.pack_into('<III',data,52,0,rtti.BASE+32,0x123456)
        found=list(rtti.find_vtables(bytes(data),'App',12))
        self.assertEqual(found[0]['name'],'7cAppMap')
        self.assertEqual(found[0]['types'][0]['vtables'][0],
                         {'address':rtti.BASE+60,'entries':[0x123456]})
        self.assertEqual(list(rtti.find_vtables(bytes(data),'Other')),[])
        with self.assertRaises(ValueError):list(rtti.find_vtables(bytes(data),'App',-1))


if __name__=='__main__':unittest.main()
