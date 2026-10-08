"""Syntheticky animovany GLB pro test pluginu demo-stavebnice.js: kostka 20 mm, klip 'demo' 6 s (posun po X, zacykleny), kotva a_box,
scenes[0].extras.v3d (minimalni platna spec) + extras.demo (cues, camera)."""
import json, struct, sys
import numpy as np
out = sys.argv[1]
# kostka 20 mm
p = np.array([[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1],[1,-1,-1],[-1,-1,-1],[-1,1,-1],[1,1,-1],[-1,1,1],[1,1,1],[1,1,-1],[-1,1,-1],[-1,-1,-1],[1,-1,-1],[1,-1,1],[-1,-1,1],[1,-1,1],[1,-1,-1],[1,1,-1],[1,1,1],[-1,-1,-1],[-1,-1,1],[-1,1,1],[-1,1,-1]], dtype=np.float32) * 10.0
n = np.array([[0,0,1]]*4+[[0,0,-1]]*4+[[0,1,0]]*4+[[0,-1,0]]*4+[[1,0,0]]*4+[[-1,0,0]]*4, dtype=np.float32)
idx = []
for f in range(6): b = f*4; idx += [b, b+1, b+2, b, b+2, b+3]
idx = np.array(idx, dtype=np.uint16)
times = np.array([0, 1.5, 3.0, 4.5, 6.0], dtype=np.float32)
trans = np.array([[-60,10,0],[0,10,0],[60,10,0],[0,10,0],[-60,10,0]], dtype=np.float32)
blob = bytearray(); views = []; acc = []
def add(arr, target=None, cmin=None, cmax=None, ctype=None, ncomp='VEC3'):
    off = len(blob); blob.extend(arr.tobytes()); 
    while len(blob) % 4: blob.append(0)
    views.append({"buffer": 0, "byteOffset": off, "byteLength": arr.nbytes, **({"target": target} if target else {})})
    a = {"bufferView": len(views)-1, "componentType": ctype, "count": int(arr.shape[0]), "type": ncomp}
    if cmin is not None: a["min"] = cmin; a["max"] = cmax
    acc.append(a); return len(acc)-1
ap = add(p, 34962, p.min(0).tolist(), p.max(0).tolist(), 5126)
an = add(n, 34962, ctype=5126)
ai = add(idx, 34963, ctype=5123, ncomp='SCALAR')
at = add(times, None, [0.0], [6.0], 5126, 'SCALAR')
av = add(trans, None, ctype=5126)
gltf = {
  "asset": {"version": "2.0"},
  "scene": 0,
  "scenes": [{"nodes": [0], "extras": {
     "v3d": {"v": 1, "u": "mm", "up": [0,1,0], "front": [0,0,1], "box": {"min": [-80,0,-20], "max": [80,40,20]}, "look": "vd", "dims": [], "motions": []},
     "demo": {"v": 1, "duration": 6.0, "loop": True, "poster": 3.0,
        "cues": [{"id": "intro", "t0": 0.0, "t1": 2.0, "anchor": None, "side": "top"}, {"id": "kamen", "t0": 2.0, "t1": 4.5, "anchor": "a_box", "side": "right"}],
        "steps": [{"id": "profil", "t0": 0.0, "t1": 2.0, "g": [0]}, {"id": "kamen", "t0": 2.0, "t1": 4.5, "g": [1]}, {"id": "hotovo", "t0": 4.5, "t1": 6.0, "g": []}],
        "camera": [{"t": 0, "pos": [150, 120, 220], "target": [0, 10, 0], "ease": "inout", "fit": 90}, {"t": 3, "pos": [-100, 60, 160], "target": [0, 10, 0], "ease": "inout"}, {"t": 6, "pos": [150, 120, 220], "target": [0, 10, 0], "ease": "inout", "fit": 90}],
        "fade": {"t0": 5.6, "t1": 6.0}}}}],
  "nodes": [{"name": "box", "mesh": 0, "translation": [-60, 10, 0], "children": [1], "extras": {"g": 1}}, {"name": "a_box"}],
  "meshes": [{"primitives": [{"attributes": {"POSITION": ap, "NORMAL": an}, "indices": ai, "material": 0}]}],
  "materials": [{"name": "kostka", "pbrMetallicRoughness": {"baseColorFactor": [0.8, 0.2, 0.1, 1], "metallicFactor": 0.1, "roughnessFactor": 0.5}}],
  "animations": [{"name": "demo", "samplers": [{"input": at, "output": av, "interpolation": "LINEAR"}], "channels": [{"sampler": 0, "target": {"node": 0, "path": "translation"}}]}],
  "buffers": [{"byteLength": len(blob)}], "bufferViews": views, "accessors": acc
}
j = json.dumps(gltf, separators=(',', ':')).encode()
while len(j) % 4: j += b' '
glb = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(j) + 8 + len(blob)) + struct.pack('<I', len(j)) + b'JSON' + j + struct.pack('<I', len(blob)) + b'BIN\x00' + bytes(blob)
open(out, 'wb').write(glb); print('ok', len(glb), 'B')
