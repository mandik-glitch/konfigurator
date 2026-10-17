#!/usr/bin/env python3
"""Vytvoří cfg_<SKU>.json z kontrola.json (kamera z kontroly = start, landmarky se známou výškou) + vyloučené oblasti masky."""
import json
SC = '/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad'
VYL = {
 '4932464079': {'c01': [[[150,40],[1160,40],[1160,432],[150,432]],[[180,430],[258,430],[258,462],[180,462]],[[985,430],[1085,430],[1085,565],[985,565]]],
                'c03': [[[735,735],[1100,735],[1100,1090],[735,1090]]]},
 '4932464080': {'c02': [[[10,520],[345,520],[345,890],[10,890]],[[905,755],[1140,755],[1140,1040],[905,1040]]]},
}
LMSKIP = {'4932464080': {'c01': [2]}}
for s in ['4932464079','4932464080','4932499703','4932499704']:
    d = json.load(open(f'../../kufriky_cloud/kontrola_john_v6/{s}/kontrola.json')); c = {}
    for f in d['fotky']:
        cam = dict(f['kamera']); cam.pop('rms_px', None); cam.pop('zt', None); cam['w'] = 1200; cam['h'] = 1200
        lm = [[l['model_xyz'][0], l['model_xyz'][1], l['model_xyz'][2], l['foto_px'][0], l['foto_px'][1], 1] for l in f['landmarky_xyz_px'] if not l['jen_svisle'] and not isinstance(l['model_xyz'][2], str)]
        for i in sorted(LMSKIP.get(s, {}).get(f['id'], []), reverse=True): lm.pop(i)
        e = {'foto': f"{SC}/kufry3/{s}/{f['id']}.jpg", 'start': cam, 'lm': lm, 'pose': {}, 'vyloucit': VYL.get(s, {}).get(f['id'], []), 'john_iou': f['iou_siluety'], 'john_iou_poznamka': f['iou_poznamka']}
        if f.get('uhel_viko_deg') is not None: e['pose'] = {'vicko': -f['uhel_viko_deg']}      # v našem modelu otevření = kladný úhel (osa -Y)
        if s in ('4932464079','4932464080') and f['id'] != 'c01':
            e['pose'].update({'trmen_L': 105 if s == '4932464079' else 135, 'trmen_P': 105 if s == '4932464079' else 135})   # drátěné třmeny na fotografiích visí dolů (otevřené západky)
        c[f['id']] = e
    if s == '4932464079':
        c['c01_nahore'] = json.loads(json.dumps(c['c01'])); c['c01_nahore']['vyloucit'] = []; c['c01_nahore']['glb'] = '../modely/4932464079_drzadlo_nahore.glb'
    if s in ('4932499703','4932499704'):
        c['c01']['pose'] = {'vicko': 118, 'trmen_L': 115, 'trmen_P': 115}
    if s in ('4932499703','4932499704'):
        base = {"azim": 30, "elev": 33, "dist": 2100, "fov": 22, "cx": 600, "cy": 600, "roll": 0, "w": 1200, "h": 1200}
        c['c02'] = {'foto': f"{SC}/kufry3/{s}/c02.jpg", 'start': base, 'lm': [], 'pose': {'vicko': 100, 'trmen_L': 140, 'trmen_P': 140}, 'vyloucit': [], 'nazev': 'sada 4932499466 Hero_3 (nepřímý důkaz, jiná fotografie než SKU)'}
        c['c03'] = {'foto': f"{SC}/kufry3/{s}/c03.jpg", 'start': dict(base, azim=0, elev=65, dist=2600, fov=18), 'lm': [], 'pose': {'vicko': 100, 'trmen_L': 120, 'trmen_P': 120}, 'vyloucit': [], 'nazev': 'sada 4932499466 Hero_2 (nepřímý důkaz, jiná fotografie než SKU)'}
    json.dump(c, open(f'cfg_{s}.json', 'w'), indent=1, ensure_ascii=False); print(s, {k: v['pose'] for k, v in c.items()})
