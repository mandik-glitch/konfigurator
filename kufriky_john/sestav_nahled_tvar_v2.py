"""Příprava místních statických souborů náhledu. Bez DB a sítě."""
from pathlib import Path
import base64
import csv
import json
import shutil
from PIL import Image

ROOT = Path(__file__).resolve().parent
SITE = ROOT / 'nahled-modely-v2'

def main():
    cat=json.loads((ROOT/'kufriky.json').read_text())
    records=[next(r for r in cat['records'] if r['id']==i) for i in cat['model_order']]
    for folder in ('vendor','obrazky','modely'):(SITE/folder).mkdir(exist_ok=True)
    for name in ('three.min.js','GLTFLoader.js','OrbitControls.js','LICENCE-three.json'):
        shutil.copyfile(ROOT/'nahled-modely/vendor'/name,SITE/'vendor'/name)
    font=json.loads((ROOT/'zdroje/pismo-v2/helvetiker_regular.typeface.json').read_text())
    (SITE/'vendor/LICENCE-pismo.json').write_text(json.dumps(font['original_font_information'],ensure_ascii=False,indent=2)+'\n')
    shutil.copyfile(ROOT/'nahled-modely/style.css',SITE/'style.css')
    with (SITE/'style.css').open('a') as f:
        f.write('\n.detail-state{display:block;color:#437354;font-size:10px;margin-top:4px}.badge{white-space:normal}.controls-detail{display:flex;flex-wrap:wrap;gap:14px;margin:10px 0 15px;font-size:12px}.controls-detail label{display:flex;gap:5px;align-items:center}.shape-features{padding:15px 18px;background:#eef5ef;border-radius:7px;margin:15px 0;font-size:13px}.shape-features p{margin:0}.status-table{overflow-x:auto;margin-top:25px}.status-table table{width:100%;border-collapse:collapse;font-size:12px}.status-table th,.status-table td{padding:8px;text-align:left;border-bottom:1px solid #e5e8eb}.watermark{color:#42564a}.type.active{background:#edf5ef;box-shadow:inset 4px 0 #52775b}.notice{background:#f0f6ef;border-color:#bad0bb}.notice strong{color:#355a3b}#photo{cursor:zoom-in}dialog{width:min(90vw,950px);border:1px solid #ddd;border-radius:10px;padding:18px}dialog::backdrop{background:#0009}dialog img{width:100%;height:75vh;object-fit:contain}dialog button{float:right;border:0;background:#eee;border-radius:5px;padding:7px 14px;cursor:pointer}.missing strong{color:#805d23}\n')
    for r in records:
        source=ROOT/'zdroje/fotografie-tvar-v2'/(r['sku'][0]+'.jpg')
        im=Image.open(source);im.thumbnail((700,700));im.save(SITE/r['image']['file'],quality=88)
        for v in r['model_variants']:
            binary=(ROOT/v['file']).read_bytes()
            js='window.KUFRIKY_MODEL_PAYLOADS['+json.dumps(v['sku'])+']='+json.dumps(base64.b64encode(binary).decode())+';\n'
            (SITE/'modely'/(v['sku']+'.js')).write_text(js)
    cad=json.loads((ROOT/'zdroje/cad_etapa2/pruzkum.json').read_text())['candidates']
    cad.append({'name':'Milwaukee Toolbox – 3D CAD Browser','url':'https://www.3dcadbrowser.com/3d-model/milwaukee-toolbox','license':'Royalty-Free; další šíření zdrojových modelů zakázáno.','access':'Stránka výslovně vyžaduje účet Free with uploads nebo placený účet.','decision':'Není staženo; účet nebyl založen. Shoda s evropským SKU není doložená.'})
    payload={'summary':cat['model_summary'],'records':records,'cad_sources':cad,'convention':cat['model_convention']}
    (SITE/'data.js').write_text('window.KUFRIKY_MODEL_PAYLOADS={};\nwindow.KUFRIKY_MODELY='+json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';\n')
    fields=None
    with (ROOT/'zdroje/etapa1-kufriky.csv').open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f,delimiter=';');fields=reader.fieldnames+['uroven_detailu','presnost_detailu_overena','pocet_casti','velikost_glb_B'];rows=list(reader)
    by_id={r['id']:r for r in cat['records']}
    with (ROOT/'kufriky.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter=';');w.writeheader()
        for row in rows:
            r=by_id[row['id']];row['model_stav']=r['model_status'];row['model_soubor']=r['model_file'] or ''
            v=r.get('model_variants',[{}])[0]
            row.update(uroven_detailu=r.get('detail_label','Mimo etapu 2'),presnost_detailu_overena='NE',pocet_casti=v.get('part_count',''),velikost_glb_B=v.get('bytes',''));w.writerow(row)
    shutil.copyfile(ROOT/'kufriky.csv',SITE/'kufriky.csv')
    shutil.copyfile(ROOT/'mereni/prehled.csv',SITE/'mereni.csv')
    (ROOT/'zdroje/cad_tvar_v2.json').write_text(json.dumps({'checked_on':'2026-10-05','downloaded_models':0,'candidates':cad,'conclusion':'Doplněn průzkum celých modelů; žádný úplný CAD správného SKU s ověřenou licencí a bez účtu nebyl získán.'},ensure_ascii=False,indent=2)+'\n')
    print('Statický náhled v2 připraven; 20 typů a 21 samostatných místních modelových souborů.')

if __name__=='__main__':main()
