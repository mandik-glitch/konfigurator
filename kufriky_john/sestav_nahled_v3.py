"""Sestavení statického náhledu v3; bez DB a sítě, bez cizích fotografií."""
import base64
import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT/'nahled-modely-v3'
cat = json.loads((ROOT/'kufriky.json').read_text())
records = [next(r for r in cat['records'] if r['id']==i) for i in cat['model_order']]
for r in records:
    for v in r['model_variants']:
        binary = (ROOT/v['file']).read_bytes()
        (SITE/'modely'/(v['sku']+'.js')).write_text('window.KUFRIKY_MODEL_PAYLOADS['+json.dumps(v['sku'])+']='+json.dumps(base64.b64encode(binary).decode())+';\n')
cad = json.loads((ROOT/'zdroje/cad_tvar_v2.json').read_text())['candidates']
payload = {'summary':cat['model_summary'], 'records':records, 'cad_sources':cad, 'convention':cat['model_convention']}
(SITE/'data.js').write_text('window.KUFRIKY_MODEL_PAYLOADS={};\nwindow.KUFRIKY_MODELY='+json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';\n')
with (ROOT/'zdroje/etapa1-kufriky.csv').open(encoding='utf-8-sig',newline='') as f:
    reader = csv.DictReader(f,delimiter=';'); fields = reader.fieldnames+['uroven_detailu','shoda_fotografie','opravy_v3','neovereno','pocet_fotografii','fotografie_url','velikost_glb_B']; rows=list(reader)
by_id = {r['id']:r for r in cat['records']}
with (ROOT/'kufriky.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer = csv.DictWriter(f,fieldnames=fields,delimiter=';'); writer.writeheader()
    for row in rows:
        r = by_id[row['id']]; row['model_stav']=r['model_status'];row['model_soubor']=r['model_file'] or ''
        if 'review' in r:
            rv=r['review'];row.update(uroven_detailu=r['detail_label'],shoda_fotografie=rv['match'],opravy_v3=rv['changed'],neovereno=' | '.join(rv['unverified']),pocet_fotografii=rv['photo_count'],fotografie_url=' | '.join(p['url'] for p in r['photo_sources']),velikost_glb_B=r['model_variants'][0]['bytes'])
        writer.writerow(row)
shutil.copyfile(ROOT/'kufriky.csv',SITE/'kufriky.csv')
shutil.copyfile(ROOT/'mereni/prehled.csv',SITE/'mereni.csv')
(SITE/'kufriky.json').write_text(json.dumps(cat,ensure_ascii=False,indent=2)+'\n')
print('V3: 20 typů, odkazy na fotografie, vlastní porovnávací rendery.')
