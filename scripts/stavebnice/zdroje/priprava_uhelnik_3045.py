#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Priprava zdroje UHELNIKU (produkt 3045 pouziva model 2895): novy prevod STEP -> GLB ve vysoke kvalite.

Katalogovy webapp/katalog/product_2895.glb je silne zjednoduseny prevod (188 trojuhelniku, otvory ~6uhelniky). Zdrojovy STEP
(webapp/content-files/product_fbx/2895.step) se proto prevadi znovu pres api/step_convert.convert_single_step(quality='high')
(OpenCascade v izolovanem api/step_venv, linearni odchylka ~0,012 mm, bez decimace): kruhove otvory maji ~108 segmentu, zaobleni jsou hladka.
'high' ponechava i vyrobni rytinu (logo vyrobce, ~2000 trojuhelniku, zahloubeni 0,1 a 0,5 mm v boku x = 0), ktera se ve scene NESMI ukazat.
Plochy loga se nezahazuji (sit by nebyla uzavrena): vrcholy zahloubeni (0 < x < 0,6) se srovnaji do roviny boku x = 0, steny rytiny se tim
zdegeneruji a odpadnou, dno rytiny vyplni "okna" v boku. Vysledek je uzavreny mesh (watertight), objem = presny objem dilu bez rytiny.

Pouziti (nic se nezapisuje do repozitare krome --out; STEP se jen cte, prevod bezi v api/step_venv pod stejnym zamkem jako admin):
  python priprava_uhelnik_3045.py --step /opt/konfigurator/webapp/content-files/product_fbx/2895.step \
      --api /opt/konfigurator/api --out uhelnik_3045_vysoka_kvalita.glb
"""
import argparse, os, sys, time, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.dont_write_bytecode = True
import build_demo_glb as B


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--step', default='/opt/konfigurator/webapp/content-files/product_fbx/2895.step')
    ap.add_argument('--api', default='/opt/konfigurator/api', help='adresar s step_convert.py (a step_venv)')
    ap.add_argument('--out', default=os.path.join(HERE, 'uhelnik_3045_vysoka_kvalita.glb'))
    ap.add_argument('--raw', default=None, help='volitelne: kam ulozit surovy prevod (s rytinou)')
    ap.add_argument('--recess-max-x', type=float, default=0.6, help='zahloubeni rytiny: vrcholy 0 < x < tato hodnota se srovnaji na x = 0')
    a = ap.parse_args()
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.path.insert(0, a.api)
    import step_convert as SC
    raw = a.raw or os.path.join(tempfile.mkdtemp(prefix='uhelnik_'), 'raw.glb')
    for _ in range(120):
        try:
            with SC.step_convert_slot():
                ok, info = SC.convert_single_step(a.step, raw, quality='high')
            break
        except SC.StepConvertBusy:
            time.sleep(5)             # jiny prevod bezi (zamek povoli jen jeden), pockat
    else:
        raise SystemExit('zamek STEP prevodu stale obsazen')
    if not ok: raise SystemExit('prevod selhal: %r' % (info,))
    V, F = B.load_glb_geometry(raw); V, F = B.weld(V, F, 1e-5)
    sel = (V[:, 0] > 1e-4) & (V[:, 0] < a.recess_max_x)
    V2 = V.copy(); V2[sel, 0] = 0.0
    V3, F3 = B.weld(V2, F, 1e-5)
    V4, N4, F4 = B.crease_normals(V3, F3, 35.0)
    W = B.GLBWriter()
    pa = W.accessor(V4.astype(np.float32), 5126, 'VEC3', 34962, minmax=True)
    na = W.accessor(N4.astype(np.float32), 5126, 'VEC3', 34962)
    ia = W.accessor(F4.astype(np.uint32).reshape(-1), 5125, 'SCALAR', 34963)
    g = {'asset': {'version': '2.0', 'generator': 'priprava_uhelnik_3045.py'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
         'nodes': [{'name': 'uhelnik'}], 'meshes': [{'primitives': [{'attributes': {'POSITION': pa, 'NORMAL': na}, 'indices': ia, 'material': 0}]}],
         'materials': [{'name': 'ocel', 'pbrMetallicRoughness': {'baseColorFactor': [0.6, 0.62, 0.66, 1], 'metallicFactor': 0.6, 'roughnessFactor': 0.45}}]}
    g['nodes'][0]['mesh'] = 0
    data = W.finish(g)
    tmp = a.out + '.tmp'
    open(tmp, 'wb').write(data); os.replace(tmp, a.out)
    print('hotovo: %s, %d B, vrcholu %d, trojuhelniku %d (surovy prevod %s tr., srovnanych vrcholu rytiny %d); prevod: %s' %
          (a.out, len(data), len(V4), len(F4), info.get('triangles_after_simplify'), int(sel.sum()),
           {k: info.get(k) for k in ('quality', 'linear_deflection_used_mm', 'faces_step', 'watertight')}))


if __name__ == '__main__':
    main()
