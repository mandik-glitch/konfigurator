"""Regrese nad skutečným GLB, včetně záměrně posunuté patky."""
from pathlib import Path
import hashlib
import json
import struct
import tempfile
import unittest
import numpy as np
from over_realne_tvary import read_glb
from over_podstavy_v4 import audit

ROOT = Path(__file__).resolve().parent


def moved_mesh(source, target, name, shift):
    doc, _ = read_glb(source)
    node = next(n for n in doc['nodes'] if n['name'] == name)
    accessor = doc['accessors'][doc['meshes'][node['mesh']]['primitives'][0]['attributes']['POSITION']]
    view = doc['bufferViews'][accessor['bufferView']]
    data = bytearray(source.read_bytes())
    offset = 12
    while offset < len(data):
        length, kind = struct.unpack_from('<II', data, offset)
        offset += 8
        if kind == 0x004e4942:
            break
        offset += length
    vertices = np.frombuffer(data, dtype='<f4', count=accessor['count']*3,
                             offset=offset+view.get('byteOffset', 0)+accessor.get('byteOffset', 0)).reshape(-1, 3)
    vertices += np.array(shift, dtype=np.float32)
    target.write_bytes(data)


class Supports(unittest.TestCase):
    def test_first_three_organisers_are_the_requested_skus(self):
        catalog = json.loads((ROOT/'kufriky.json').read_text())
        ordered = [next(r for r in catalog['records'] if r['id'] == i) for i in catalog['model_order']]
        self.assertEqual([r['sku'][0] for r in ordered[:3]], ['4932471064', '4932464082', '4932471065'])
        self.assertEqual(ordered[1]['outer']['mm']['height'], 117)

    def test_original_defect_is_detected_in_all_three(self):
        for sku, expected in [('4932471064', 16), ('4932464082', 15.44), ('4932471065', 16)]:
            report = audit(ROOT/'modely-v3'/(sku+'.glb'), sku)
            self.assertTrue(report['failures'])
            pads = [r for r in report['rows'] if r['kind'] == 'ground_pad']
            self.assertAlmostEqual(max(r['bbox_overhang_mm'] for r in pads), expected, places=3)

    def test_every_current_support_is_inside_and_has_a_measured_contact(self):
        catalog = json.loads((ROOT/'kufriky.json').read_text())
        count = 0
        for record in catalog['records']:
            if record['group'] != 'kufriky':
                continue
            for sku in record['sku']:
                report = audit(ROOT/'modely'/(sku+'.glb'), sku)
                self.assertEqual(report['failures'], [], sku)
                self.assertGreaterEqual(report['supports_measured'], 12)
                count += 1
        self.assertEqual(count, 21)

    def test_shift_is_caught_even_when_foot_center_is_still_inside(self):
        sku = '4932464082'
        with tempfile.TemporaryDirectory(dir=ROOT/'overeni-tvar-v4') as folder:
            mutant = Path(folder)/'posunuta-patka.glb'
            moved_mesh(ROOT/'modely'/(sku+'.glb'), mutant, 'patka-1-1', [16, 0, 0])
            report = audit(mutant, sku)
            foot = next(r for r in report['rows'] if r['part'] == 'patka-1-1')
            self.assertGreater(foot['contour_overhang_mm'], 15)
            self.assertLess(foot['center_overhang_mm'], .01)
            self.assertTrue(report['failures'])

    def test_detached_foot_is_caught_even_with_valid_xy_footprint(self):
        sku = '4932471065'
        with tempfile.TemporaryDirectory(dir=ROOT/'overeni-tvar-v4') as folder:
            mutant = Path(folder)/'patka-bez-dosedu.glb'
            moved_mesh(ROOT/'modely'/(sku+'.glb'), mutant, 'patka-1-1', [0, 0, -2])
            report = audit(mutant, sku)
            foot = next(r for r in report['rows'] if r['part'] == 'patka-1-1')
            self.assertLess(foot['contour_overhang_mm'], .01)
            self.assertGreater(foot['vertical_gap_mm'], 1.99)
            self.assertTrue(report['failures'])

    def test_v3_local_and_public_history_is_preserved(self):
        manifest = json.loads((ROOT/'overeni-tvar-v4/historie-v3-sha256.json').read_text())
        self.assertEqual(len(manifest), 94)
        for relative, expected in manifest.items():
            for folder in [ROOT/'nahled-modely-v3', Path('/opt/konfigurator/webapp/nahled-john/kufriky-milwaukee-modely-v3')]:
                file = folder/relative
                self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), expected, str(file))


if __name__ == '__main__':
    unittest.main(verbosity=2)
