"""Čistá kontrola skutečných GLB vrcholů, zdrojů a hranice tvrzené přesnosti."""
from pathlib import Path
from urllib.parse import urlsplit
import csv
import hashlib
import html
import json
import math
import re
import struct
import unittest

ROOT=Path(__file__).resolve().parent
CAT=json.loads((ROOT/'kufriky.json').read_text())
ORIGINAL=json.loads((ROOT/'zdroje/etapa1-kufriky.json').read_text())
RECORDS=[r for r in CAT['records'] if r['group']=='kufriky']
SITE=ROOT/'nahled-modely'

def read_glb(data):
    if len(data)<20:raise ValueError('Neúplná hlavička')
    magic,version,total=struct.unpack_from('<III',data)
    if magic!=0x46546c67 or version!=2 or total!=len(data):raise ValueError('Vadná hlavička GLB')
    chunks={};offset=12
    while offset<len(data):
        n,kind=struct.unpack_from('<II',data,offset);offset+=8
        if offset+n>len(data) or n%4:raise ValueError('Neúplný nebo nezarovnaný chunk')
        if kind in chunks:raise ValueError('Duplicitní chunk')
        chunks[kind]=data[offset:offset+n];offset+=n
    return json.loads(chunks[0x4e4f534a]),chunks[0x004e4942]

def mul(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

def identity():return [[float(i==j) for j in range(4)] for i in range(4)]

def node_matrix(node):
    if 'matrix' in node:return [[node['matrix'][4*j+i] for j in range(4)] for i in range(4)]
    x,y,z,w=node.get('rotation',[0,0,0,1]);sx,sy,sz=node.get('scale',[1,1,1]);tx,ty,tz=node.get('translation',[0,0,0])
    return [[(1-2*(y*y+z*z))*sx,2*(x*y-z*w)*sy,2*(x*z+y*w)*sz,tx],
            [2*(x*y+z*w)*sx,(1-2*(x*x+z*z))*sy,2*(y*z-x*w)*sz,ty],
            [2*(x*z-y*w)*sx,2*(y*z+x*w)*sy,(1-2*(x*x+y*y))*sz,tz],[0,0,0,1]]

def geometry_bounds(doc,binary):
    """Všechny aktivní uzly, všechny meshe a primitiva; aplikuje matrix i TRS."""
    vertices=[];triangles=0;primitives=0;mesh_instances=0;active=set()
    def visit(index,parent):
        nonlocal triangles,primitives,mesh_instances
        if index in active:raise ValueError('Cyklus uzlů')
        active.add(index);node=doc['nodes'][index];matrix=mul(parent,node_matrix(node))
        if 'mesh' in node:
            mesh_instances+=1
            for prim in doc['meshes'][node['mesh']]['primitives']:
                if prim.get('mode',4)!=4:raise ValueError('Nepodporovaný mód primitiva')
                if prim.get('extensions'):raise ValueError('Nepodporované rozšíření primitiva')
                primitives+=1;acc=doc['accessors'][prim['attributes']['POSITION']]
                if acc.get('sparse') or acc['componentType']!=5126 or acc['type']!='VEC3':raise ValueError('Nepodporovaný POSITION accessor')
                view=doc['bufferViews'][acc['bufferView']]
                if view['buffer']!=0:raise ValueError('Externí buffer')
                start=view.get('byteOffset',0)+acc.get('byteOffset',0);stride=view.get('byteStride',12)
                end=start+(acc['count']-1)*stride+12
                if stride<12 or end>len(binary) or end>view.get('byteOffset',0)+view['byteLength']:raise ValueError('Accessor mimo buffer')
                for i in range(acc['count']):
                    p=list(struct.unpack_from('<3f',binary,start+i*stride))+[1]
                    q=[sum(matrix[j][k]*p[k] for k in range(4)) for j in range(3)]
                    if not all(math.isfinite(v) for v in q):raise ValueError('Neplatná souřadnice')
                    vertices.append(q)
                count=doc['accessors'][prim['indices']]['count'] if 'indices' in prim else acc['count']
                if count%3:raise ValueError('Neúplný trojúhelník')
                triangles+=count//3
        for child in node.get('children',[]):visit(child,matrix)
        active.remove(index)
    for root in doc['scenes'][doc.get('scene',0)]['nodes']:visit(root,identity())
    if not vertices:raise ValueError('Nebyl změřen žádný vrchol')
    low=[min(p[k] for p in vertices) for k in range(3)];high=[max(p[k] for p in vertices) for k in range(3)]
    return {'min_mm':low,'max_mm':high,'size_xyz_mm':[b-a for a,b in zip(low,high)],'vertices_measured':len(vertices),'triangles':triangles,'primitives':primitives,'mesh_instances':mesh_instances}

def measure(path):return geometry_bounds(*read_glb(path.read_bytes()))

def write_report():
    rows=[]
    for r in RECORDS:
        d=r['outer']['mm'];target=[d['width'],d['length'],d['height']]
        for v in r['envelope']['variants']:
            m=measure(ROOT/v['file']);delta=[a-b for a,b in zip(m['size_xyz_mm'],target)]
            if max(abs(x) for x in delta)>.01:raise ValueError('Rozměrová odchylka '+v['sku'])
            rows.append({'sku':v['sku'],'type_id':r['id'],'file':v['file'],'target_xyz_mm':target,'actual':m,'deviation_xyz_mm':delta,'comparison_tolerance_mm':.01,
                'physical_tolerance_mm':None,'is_product_geometry':False,'source_url':r['outer']['source_url'],'source_basis':r['outer']['basis'],'status':'PASS_envelope_only'})
    result={'status':'PASS_envelope_only','types_measured':len(RECORDS),'sku_models_measured':len(rows),'product_geometries_verified':0,'vertices_measured':sum(x['actual']['vertices_measured'] for x in rows),'rows':rows}
    (ROOT/'overeni-modely').mkdir(exist_ok=True)
    (ROOT/'overeni-modely/obalky.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

class ModelChecks(unittest.TestCase):
    def test_01_all_approved_types_and_skus_present(self):
        self.assertEqual(len(RECORDS),20)
        self.assertEqual({r['id'] for r in RECORDS},{r['id'] for r in ORIGINAL['records'] if r['group']=='kufriky'})
        self.assertEqual(sum(len(r['sku']) for r in RECORDS),21)
        self.assertEqual(CAT['model_order'][:2],['milwaukee-packout-4932471064','milwaukee-packout-4932464082'])
        self.assertTrue(all('envelope' not in r for r in CAT['records'] if r['group']=='ostatni'))

    def test_02_actual_vertices_match_all_three_source_axes(self):
        originals={r['id']:r for r in ORIGINAL['records']}
        for r in RECORDS:
            self.assertEqual(r['outer'],originals[r['id']]['outer'])
            self.assertEqual(r['observations'],originals[r['id']]['observations'])
            d=r['outer']['mm'];expected=[d['width'],d['length'],d['height']]
            for v in r['envelope']['variants']:
                b=(ROOT/v['file']).read_bytes();doc,binary=read_glb(b);m=geometry_bounds(doc,binary)
                self.assertEqual(m['size_xyz_mm'],expected,v['sku'])
                self.assertEqual(m['vertices_measured'],8);self.assertEqual(m['triangles'],12)
                self.assertEqual(m['primitives'],1);self.assertEqual(m['mesh_instances'],1)
                self.assertEqual(doc['asset']['extras']['sku'],v['sku'])
                self.assertEqual(doc['asset']['extras']['units'],'mm')
                self.assertEqual(hashlib.sha256(b).hexdigest(),v['sha256'])
                self.assertEqual(b,(SITE/v['file']).read_bytes())

    def test_03_source_variants_rechecked_on_manufacturer_pages(self):
        pages=json.loads((ROOT/'zdroje/cad_etapa2/vyrobce.json').read_text())
        self.assertEqual(len(pages),9)
        variants={v['sku']:v for p in pages for v in p.get('products',[])}
        for r in RECORDS:
            if r['outer']['basis']!='vyrobce':continue
            sku='4932478162' if '4932478162' in r['sku'] else r['sku'][0]
            props={p['name']:p['value'] for p in variants[sku]['additionalProperty']}
            raw=props.get('Dimensions (Outer)') or props.get('Size')
            self.assertEqual(re.findall(r'\d+(?:\.\d+)?',html.unescape(raw)),re.findall(r'\d+(?:\.\d+)?',r['outer']['raw']),sku)

    def test_04_envelope_is_never_claimed_as_complete_product(self):
        self.assertEqual(CAT['model_summary']['exact_models_ready'],0)
        for r in RECORDS:
            self.assertIsNone(r['model_file']);self.assertEqual(r['model_status'],'chybi_presny_model')
            self.assertFalse(r['envelope']['is_product_geometry']);self.assertIsNone(r['envelope']['physical_tolerance_mm'])
            self.assertGreaterEqual(len(r['missing_geometry']),4)
            sheet=json.loads((ROOT/'mereni'/f"{r['sku'][0]}.json").read_text())
            self.assertIsNone(sheet['physical_overall_mm']);self.assertTrue(all(v is None for v in sheet['geometry'].values()))
        self.assertEqual(json.loads((ROOT/'zdroje/cad_etapa2/pruzkum.json').read_text())['downloaded_models'],0)

    def test_05_parser_applies_all_node_transforms_and_primitives(self):
        doc,binary=read_glb((ROOT/RECORDS[0]['envelope']['file']).read_bytes());base=geometry_bounds(doc,binary)
        # Druhý mesh a druhé primitivum nesmějí vypadnout. Nedůvěřujeme accessor.min/max.
        doc['meshes'].append(json.loads(json.dumps(doc['meshes'][0])))
        doc['meshes'][1]['primitives'].append(dict(doc['meshes'][1]['primitives'][0]))
        doc['nodes'].append({'mesh':1,'translation':[1000,0,0]});doc['scenes'][0]['nodes'].append(1)
        doc['accessors'][0]['min']=[0,0,0];doc['accessors'][0]['max']=[1,1,1]
        result=geometry_bounds(doc,binary)
        self.assertEqual(result['mesh_instances'],2);self.assertEqual(result['primitives'],3)
        self.assertEqual(result['vertices_measured'],24)
        self.assertEqual(result['size_xyz_mm'][0],base['size_xyz_mm'][0]+1000)
        # Stejná transformace v rodiči, scale se opravdu promítne do obálky.
        doc['nodes'].append({'children':[0,1],'scale':[2,1,1]});doc['scenes'][0]['nodes']=[2]
        self.assertEqual(geometry_bounds(doc,binary)['size_xyz_mm'][0],2*result['size_xyz_mm'][0])

    def test_06_bad_or_empty_geometry_fails_loudly(self):
        doc,binary=read_glb((ROOT/RECORDS[0]['envelope']['file']).read_bytes())
        with self.assertRaises(ValueError):read_glb(b'bad')
        doc['scenes'][0]['nodes']=[]
        with self.assertRaises(ValueError):geometry_bounds(doc,binary)
        doc['scenes'][0]['nodes']=[0];doc['accessors'][0]['count']=999
        with self.assertRaises(ValueError):geometry_bounds(doc,binary)

    def test_07_static_files_are_local_and_no_accounts(self):
        allowed={'.html','.js','.css','.json','.csv','.glb','.jpg'}
        for p in SITE.rglob('*'):
            if not p.is_file():continue
            self.assertIn(p.suffix,allowed,p)
            if p.suffix in {'.glb','.jpg'}:continue
            text=p.read_text(encoding='utf-8-sig')
            for s in ['/home/openai1','/opt/','ukoly/']:self.assertNotIn(s,text,p)
        index=(SITE/'index.html').read_text()
        self.assertIn('<meta name="robots" content="noindex, nofollow">',index)
        self.assertIn("connect-src 'none'",index)
        self.assertNotRegex(index,r'(?:src|href)="https?://')
        self.assertNotRegex((SITE/'app.js').read_text(),r'\b(?:fetch|XMLHttpRequest|WebSocket|sendBeacon)\s*\(')

    def test_08_csv_json_and_images_complete(self):
        self.assertEqual((ROOT/'kufriky.json').read_bytes(),(SITE/'kufriky.json').read_bytes())
        self.assertEqual((ROOT/'kufriky.csv').read_bytes(),(SITE/'kufriky.csv').read_bytes())
        with (ROOT/'kufriky.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f,delimiter=';'))
        selected=[r for r in rows if r['skupina']=='kufriky'];self.assertEqual(len(selected),20)
        self.assertTrue(all(r['model_soubor']=='' and r['obalka_soubor'] for r in selected))
        for r in RECORDS:self.assertEqual((SITE/r['image']['file']).read_bytes(),(ROOT/'nahled'/r['image']['file']).read_bytes())

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ModelChecks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    report=write_report();print('Změřeno:',report['types_measured'],'typů,',report['sku_models_measured'],'GLB,',report['vertices_measured'],'vrcholů. Přesné modely výrobků:',report['product_geometries_verified'])
