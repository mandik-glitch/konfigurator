#!/usr/bin/env python3
"""Po srovnej_vse_tstak.sh: doplní do srovnani/<kód>/<pohled>.json odkaz na fotografii (URL z fotky_url.tsv, bez cesty do scratchpadu) a popis metody."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
urls = {}
for l in open(os.path.join(HERE, '..', 'fotky_url.tsv'), encoding='utf-8'):
    p = l.rstrip('\n').split('\t')
    if len(p) >= 3: urls[(p[0], p[1])] = p[2]
for k, num in (('DWST83346', 'DWST83346-1'), ('DWST83345', 'DWST83345-1')):
    for pv, c in (('celo-c02', 'c02'), ('sikmo-c01', 'c01'), ('celo-c03', 'c03')):
        f = os.path.join(ROOT, 'kufriky_cloud/srovnani', k, pv + '.json')
        if not os.path.exists(f): continue
        j = json.load(open(f))
        j['foto_repo_cesta'] = f'scratchpad session: kufry2/{num}/{c}.jpg (mimo repo, jen ke čtení)'
        j['foto_url'] = urls.get((num, c + '.jpg'))
        if pv == 'celo-c03': j['foto_poznamka'] = 'c03 = kufr + vyjmutá vložka; pro srovnání oříznuto na řádky 0–1735 (vložka pod kufrem odstraněna z masky)'
        j['poznamka'] = 'Kamera (azim, elev, roll, dist, fov, posun hlavního bodu) odhadnuta z ručních landmarků (kufry_dewalt/zdroje/landmarky/) a překryvu obrysu v rámu fotografie (kufry_dewalt/nastroje/fit_lm.mjs, Nelder–Mead); ohnisko není změřené. U fotografií se zvednutým držadlem je fitován i úhel skupiny drzadlo (pose). IoU = obrys modelu vs. maska fotografie (díry vyplněny) v rozlišení 480 px.'
        json.dump(j, open(f, 'w'), ensure_ascii=False, indent=1)
