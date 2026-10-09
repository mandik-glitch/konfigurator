"""Čistá, opakovatelná příprava etapy 2. Bez DB, sítě a domýšlených detailů.

GLB obsahuje pouze matematickou obálku publikovaných rozměrů, ne tělo
skutečného výrobku. model_file zůstává null; obálka má samostatné pole.
Katalogové osy podle změřených euroboxů: X=Š, Y=L, Z=V; čísla v mm.
"""
from pathlib import Path
import base64
import csv
import hashlib
import json
import shutil
import struct

ROOT = Path(__file__).resolve().parent
SITE = ROOT/'nahled-modely'
FIRST = ['4932471064', '4932464082']
PREVIEW = 'https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v1/'

def envelope_glb(sku, dims, source):
    x, y, z = dims['width']/2, dims['length']/2, dims['height']/2
    positions = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    indices = [0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5]
    binary = struct.pack('<24f',*(v for p in positions for v in p))+struct.pack('<36H',*indices)
    metadata = {
        'sku':sku, 'kind':'published_dimension_envelope', 'is_product_geometry':False,
        'units':'mm', 'catalog_axes':{'X':'width','Y':'length','Z':'height'},
        'pivot':'center_of_published_envelope', 'dimensions_mm':dims,
        'dimensions_source_url':source,
        'limitation':'Pouze rozměrová obálka. Tvar výrobku, držadla, zámky, kolečka a spoje nejsou ověřeny ani modelovány.'
    }
    doc = {
        'asset':{'version':'2.0','generator':'John – rozměrové obálky, mm','extras':metadata},
        'scene':0, 'scenes':[{'nodes':[0],'extras':metadata}],
        'nodes':[{'name':sku+'_ROZMEROVA_OBALKA','mesh':0,'extras':metadata}],
        'meshes':[{'name':sku+'_ROZMEROVA_OBALKA','primitives':[{'attributes':{'POSITION':0},'indices':1,'material':0}]}],
        'materials':[{'name':'Obálka rozměrů – není materiál výrobku','doubleSided':True,'alphaMode':'BLEND','pbrMetallicRoughness':{'baseColorFactor':[0.31,0.40,0.64,0.22],'metallicFactor':0,'roughnessFactor':1}}],
        'buffers':[{'byteLength':len(binary)}],
        'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':96,'target':34962},{'buffer':0,'byteOffset':96,'byteLength':72,'target':34963}],
        'accessors':[{'bufferView':0,'componentType':5126,'count':8,'type':'VEC3','min':[-x,-y,-z],'max':[x,y,z]},{'bufferView':1,'componentType':5123,'count':36,'type':'SCALAR','min':[0],'max':[7]}]
    }
    text = json.dumps(doc,ensure_ascii=False,separators=(',',':')).encode()
    text += b' '*((-len(text))%4)
    binary += b'\0'*((-len(binary))%4)
    return struct.pack('<III',0x46546c67,2,12+8+len(text)+8+len(binary))+struct.pack('<II',len(text),0x4e4f534a)+text+struct.pack('<II',len(binary),0x004e4942)+binary

def missing_details(record):
    items = [
        {'key':'body_surface','text':'Skutečný obrys těla, úkosy, zaoblení, výztuhy a jejich souřadnice.'},
        {'key':'packout_interface','text':'Profily, kóty a polohy spodních a horních spojů PACKOUT včetně funkčních vůlí.'},
        {'key':'handles','text':'Rozměry, polohy a obálka držadel v přepravní poloze.'},
        {'key':'support_surface','text':'Poloha a rozměry skutečných opěrných ploch a spodních výstupků.'}
    ]
    if record['category'] != 'Přepravka':
        items.append({'key':'closures','text':'Kóty a polohy uzávěrů, pantů, víka nebo čelních dvířek/zásuvek.'})
    if 'Pojízdn' in record['name']:
        items.append({'key':'wheels','text':'Průměr, šířka a polohy koleček/osy a obálka vysunutého a zasunutého držadla.'})
    if record['review_status']=='pozor':
        items.insert(0,{'key':'overall_conflict','text':'Potvrdit rozpory v celkových rozměrech, verzi SKU a co zahrnuje uváděná obálka.'})
    return items

def main():
    original = json.loads((ROOT/'zdroje/etapa1-kufriky.json').read_text())
    catalog = json.loads(json.dumps(original))
    catalog.update(stage=2,schema_version='2.0',stage_status='nedokonceno_chybi_presna_geometrie',model_preview_url=PREVIEW,
        model_convention={'units':'mm','axes':{'X':'width','Y':'length','Z':'height'},'pivot':'center_of_published_envelope','reference_files':['Object_7.glb','product_3788.glb','product_3794.glb'],
        'evidence':'Skutečné katalogové GLB byly změřeny. Euroboxy mají kratší stranu na X, délku na Y a výšku na Z. Středový pivot nových obálek je výslovná volba Johna; původní euroboxy mají pivot posunutý.'})
    order = sorted((r for r in catalog['records'] if r['group']=='kufriky'),key=lambda r:(FIRST.index(r['sku'][0]) if r['sku'][0] in FIRST else len(FIRST),r['outer']['mm']['length'],r['sku'][0]))
    catalog['model_summary']={'types_in_scope':20,'sku_in_scope':sum(len(r['sku']) for r in order),'exact_models_ready':0,'envelopes_ready':20,
        'message':'Přesné modely výrobků nejsou hotové. Připravené jsou pouze obálky zveřejněných rozměrů; neprokazují tvar ani kompatibilitu spojů.'}
    model_dir=ROOT/'modely'; model_dir.mkdir(exist_ok=True)
    (SITE/'modely').mkdir(parents=True,exist_ok=True)
    (SITE/'obrazky').mkdir(exist_ok=True)
    (ROOT/'mereni').mkdir(exist_ok=True)
    payload={}
    sheets=[]
    for r in catalog['records']:
        if r['group']!='kufriky':
            r['model_status']='mimo_etapu_2'
            continue
        r['model_file']=None
        r['model_status']='chybi_presny_model'
        r['missing_geometry']=missing_details(r)
        r['envelope']={'kind':'published_dimension_envelope','is_product_geometry':False,'units':'mm','file':f"modely/{r['sku'][0]}.glb",'dimensions_mm':r['outer']['mm'],
            'source_url':r['outer']['source_url'],'comparison_tolerance_mm':0.01,'physical_tolerance_mm':None,
            'uncertainty':'Obálka publikovaných rozměrů; fyzický kus a detaily nejsou změřeny.','variants':[]}
        for sku in r['sku']:
            relative=f'modely/{sku}.glb'
            b=envelope_glb(sku,r['outer']['mm'],r['outer']['source_url'])
            (ROOT/relative).write_bytes(b)
            (SITE/relative).write_bytes(b)
            payload[relative]=base64.b64encode(b).decode()
            r['envelope']['variants'].append({'sku':sku,'file':relative,'sha256':hashlib.sha256(b).hexdigest(),
                'limitation':'Společný publikovaný rozměr není důkaz konstrukční shody verzí.' if len(r['sku'])>1 else None})
        shutil.copyfile(ROOT/'nahled'/r['image']['file'],SITE/r['image']['file'])
        sheet={'id':r['id'],'sku':r['sku'],'name':r['name'],'units':'mm','axes':catalog['model_convention']['axes'],
            'published_dimensions_mm':r['outer']['mm'],'source_url':r['outer']['source_url'],'physical_overall_mm':None,
            'physical_tolerance_mm':None,'physical_piece_revision':None,'dimension_includes_handles_and_latches':None,
            'scan_or_cad_file':None,'scan_or_cad_license':None,'geometry':{p['key']:None for p in r['missing_geometry']},
            'required_geometry':r['missing_geometry'],'instructions':'Vyplnit z měření kusu správného SKU nebo z kótovaného CAD. K údajům přidat zdroj, datum a nejistotu. Fotografie bez kót neurčuje prostorové souřadnice.'}
        (ROOT/'mereni'/f"{r['sku'][0]}.json").write_text(json.dumps(sheet,ensure_ascii=False,indent=2)+'\n')
        sheets.append(sheet)
    catalog['model_order']=[r['id'] for r in order]
    text=json.dumps(catalog,ensure_ascii=False,indent=2)+'\n'
    (ROOT/'kufriky.json').write_text(text)
    (SITE/'kufriky.json').write_text(text)
    # Dosavadní sloupce zachováváme; nové přidávají stav skutečného modelu a obálku.
    with (ROOT/'zdroje/etapa1-kufriky.csv').open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f,delimiter=';'); fields=reader.fieldnames+['obalka_soubor','obalka_druh','model_geometrie_chybi']; rows=list(reader)
    by_id={r['id']:r for r in catalog['records']}
    with (ROOT/'kufriky.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,delimiter=';'); writer.writeheader()
        for row in rows:
            r=by_id[row['id']]; row['model_stav']=r['model_status']; row['model_soubor']=r['model_file'] or ''
            row['obalka_soubor']=r.get('envelope',{}).get('file','')
            row['obalka_druh']='Pouze publikovaná rozměrová obálka; přesný tvar chybí' if 'envelope' in r else ''
            row['model_geometrie_chybi']=' | '.join(i['text'] for i in r.get('missing_geometry',[])); writer.writerow(row)
    shutil.copyfile(ROOT/'kufriky.csv',SITE/'kufriky.csv')
    public={'summary':catalog['model_summary'],'convention':catalog['model_convention'],'records':order,'models':payload,
        'cad_sources':json.loads((ROOT/'zdroje/cad_etapa2/pruzkum.json').read_text())['candidates']}
    (SITE/'data.js').write_text('window.KUFRIKY_MODELY = '+json.dumps(public,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+';\n')
    with (ROOT/'mereni/prehled.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f,delimiter=';'); writer.writerow(['SKU','název','L_mm','Š_mm','V_mm','zdroj','fyzické_měření','chybějící_geometrie'])
        for s in sheets:
            d=s['published_dimensions_mm'];writer.writerow([' / '.join(s['sku']),s['name'],d['length'],d['width'],d['height'],s['source_url'],'NE',' | '.join(p['text'] for p in s['required_geometry'])])
    shutil.copyfile(ROOT/'mereni/prehled.csv',SITE/'mereni.csv')
    print('20 typů / 21 SKU: publikované rozměrové obálky. Přesné modely hotové: 0. Žádný detail nebyl odhadnut.')

if __name__=='__main__':
    main()
