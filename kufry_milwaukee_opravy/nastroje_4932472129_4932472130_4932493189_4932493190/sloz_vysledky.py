#!/usr/bin/env python3
"""Složí výsledky ověření do kufriky_cloud/srovnani_opravy/<SKU>/: iou.json (staré IoU z kontroly John v6, nové IoU z přepočtených kamer, nové IoU z kamer reportu,
IoU z dofitované kamery) a rendery modelu cNN_model.png (jen náš model, žádné fotografie). Použití: sloz_vysledky.py <scratch> <kolo_nova> <kolo_john> <SKU…>"""
import sys, os, json, shutil
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sc, kn, kj = sys.argv[1:4]; skus = sys.argv[4:]
for sku in skus:
    old = json.load(open(f'{REPO}/kufriky_cloud/kontrola_john_v6/{sku}/iou.json'))
    out = f'{REPO}/kufriky_cloud/srovnani_opravy/{sku}'; os.makedirs(out, exist_ok=True)
    dofit = {}
    pf = f'{sc}/mszas/{sku}_dofit.json'
    if os.path.exists(pf): dofit = json.load(open(pf))
    res = {}
    for p in sorted(old):
        n = json.load(open(f'{sc}/mszas/k{kn}/{sku}_{p}_iou.json')); j = json.load(open(f'{sc}/mszas/k{kj}_john/{sku}_{p}_iou.json'))
        r = {'iou_john_v6': old[p]['iou'], 'iou_nova_kamera_landmarky': n['iou'], 'iou_nova_kamera_reportu': j['iou'],
             'px_jen_foto': n['px_jen_foto'], 'px_jen_model': n['px_jen_model'], 'rms_landmarku_px_report': old[p]['rms_landmarku_px']}
        if p in dofit: r['iou_dofit_kamera_400px_NENI_DUKAZ'] = dofit[p]['iou400_dofit']; r['iou_start_400px'] = dofit[p]['iou400_start']
        cj = json.load(open(f'{out}/{p}.json')); r['rms_landmarku_px_nova'] = cj.get('rms_px')
        res[p] = r
        shutil.copy(f'{sc}/mszas/k{kn}/{sku}_{p}_model.png', f'{out}/{p}_model.png')
    json.dump({'sku': sku, 'poznamka': 'IoU = průnik/sjednocení obrysu fotografie (jas < 245, bez vyplňování děr) a obrysu modelu v 1200×1200 px; nová kamera = přepočet z ručních landmarků reportu s opravenými z-úrovněmi rohů (bez dofitování podle tvaru); iou_nova_kamera_reportu = kamery z reportu beze změny; dofit = kamera doladěná překryvem obrysu (400 px) a NENÍ důkaz.', 'pohledy': res}, open(f'{out}/iou.json', 'w'), indent=1, ensure_ascii=False)
    print(sku, {p: (r['iou_john_v6'], r['iou_nova_kamera_landmarky'], r['iou_nova_kamera_reportu']) for p, r in res.items()})
