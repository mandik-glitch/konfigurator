#!/opt/konfigurator/api/venv/bin/python
"""Slozi sablonu stolu (30 nebo 40) do jednoho GLB pro nahled (bot10, 2026-10-04): kazdy dil se svym modelem z katalogu v svete, barvy podle druhu dilu.
  api/venv/bin/python -B scripts/2026-10-04_system40/sestav_glb_sablony.py 30|40 vystup.glb"""
import json, os, sys
import numpy as np, trimesh
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from _spolecne import load_glb, world, tmpl, KAT
BARVY = {'Object_7': (200, 205, 210), 'Object_11': (200, 205, 210), 'product_3158': (70, 70, 74), 'product_3176': (70, 70, 74), 'product_4933': (190, 190, 186),
         'product_4931': (130, 134, 140), 'product_4930': (90, 98, 110), 'product_4929': (250, 240, 200), 'product_4932': (60, 60, 64), 'product_4928': (40, 120, 200), 'product_4916': (30, 30, 34)}
def main():
    sys_ = sys.argv[1]; out = sys.argv[2]
    parts = tmpl()['parts'] if sys_ == '30' else json.load(open(os.path.join(HERE, 'vystup', 'stul_sablona_system40.json'), encoding='utf-8'))['parts']
    sc = trimesh.Scene(); cache = {}
    for i, p in enumerate(parts):
        pid = p['part_id']
        if pid not in cache: cache[pid] = load_glb(KAT + pid + '.glb')
        V, F = cache[pid]; W = world(p, V)
        m = trimesh.Trimesh(W, F, process=False); m.visual.face_colors = list(BARVY.get(pid, (150, 150, 150))) + [255]
        sc.add_geometry(m, node_name='%s_%d' % (pid, i))
    sc.export(out)
    # popis v3d (pro nas prohlizec: souradnice v mm, osa Y nahoru, bez pohybu a kot), jinak ho nastroj na snimky odmitne jako legacy model
    import struct
    b = open(out, 'rb').read(); n = struct.unpack('<I', b[12:16])[0]; j = json.loads(b[20:20 + n]); rest = b[20 + n:]
    allv = np.vstack([world(p, cache[p['part_id']][0]) for p in parts])
    j['scenes'][0]['extras'] = {'v3d': {'v': 1, 'u': 'mm', 'up': [0, 1, 0], 'front': [0, 0, 1], 'box': {'min': [round(float(x), 1) for x in allv.min(0)], 'max': [round(float(x), 1) for x in allv.max(0)]}, 'look': 'nat', 'dims': [], 'motions': []}}
    js = json.dumps(j, separators=(',', ':')).encode(); js += b' ' * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + len(rest)
    open(out, 'wb').write(b[:8] + struct.pack('<I', total) + struct.pack('<I', len(js)) + b'JSON' + js + rest)
    print('zapsano', out, len(parts), 'dilu')
main()
