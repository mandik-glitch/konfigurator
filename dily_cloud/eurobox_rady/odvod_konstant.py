"""Odvození konstant euroboxů 400x300 z GLB (webapp/katalog/product_<karta>.glb).
Spuštění: python3 -I odvod_konstant.py  -> vypíše JSON konstant (ty jsou pak zapsané v eurobox_rady.py).
Lokální osy GLB: X = kratší strana (299), Y = delší strana (399), Z = výška; nožka je u minimálního Z.
"""
import json, os, struct, sys
import numpy as np

KAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'webapp', 'katalog')
KARTY = {120: 3788, 170: 3793, 220: 3794, 270: 3795, 320: 3796}


def vrcholy(cesta):
    d = open(cesta, 'rb').read()
    l = struct.unpack('<I', d[12:16])[0]
    j = json.loads(d[20:20 + l])
    off = 20 + l
    bl = struct.unpack('<I', d[off:off + 4])[0]
    b = d[off + 8:off + 8 + bl]
    out = []
    for m in j['meshes']:
        for p in m['primitives']:
            a = j['accessors'][p['attributes']['POSITION']]
            bv = j['bufferViews'][a['bufferView']]
            o = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
            st = bv.get('byteStride') or 12
            out.append(np.ndarray((a['count'], 3), '<f4', b, o, (st, 4)).astype(float))
    # uzly: v těchto GLB jediný uzel bez transformace (ověřeno níže)
    for n in j['nodes']:
        assert not any(k in n for k in ('matrix', 'rotation', 'translation', 'scale')), n
    return np.concatenate(out)


def main():
    res = {}
    for vyska, karta in KARTY.items():
        v = vrcholy(os.path.join(KAT, 'product_%d.glb' % karta))
        mn, mx = v.min(0), v.max(0)
        rozm = mx - mn
        # nožka: vrstvy v Z, kde je rozměr XY menší než celek
        zs = np.unique(v[:, 2].round(2))
        nozka_z = None
        for z in zs:
            w = v[np.abs(v[:, 2] - z) < 0.01]
            ex = w[:, :2].max(0) - w[:, :2].min(0)
            if ex[0] > rozm[0] - 0.1 and ex[1] > rozm[1] - 0.1:
                nozka_z = z
                break
        spodek = v[np.abs(v[:, 2] - mn[2]) < 0.01]
        res[str(vyska)] = {
            'karta': karta,
            'stred_glb': [round(float(x), 4) for x in (mn + mx) / 2],
            'rozmer_glb': [round(float(x), 3) for x in rozm],
            'nozka_vyska': round(float(nozka_z - mn[2]), 3),
            'nozka_spodek_xy': [round(float(x), 3) for x in (spodek[:, :2].max(0) - spodek[:, :2].min(0))],
        }
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
