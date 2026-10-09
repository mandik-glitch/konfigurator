"""Offline checks of actual GLB vertices, surfaces and data provenance."""
from pathlib import Path
import hashlib
import json
import re
import struct
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parent
SITE=ROOT/'nahled-modely-v2'
OUT=ROOT/'overeni-tvar-v2'
CAT=json.loads((ROOT/'kufriky.json').read_text())
FIRST=json.loads((ROOT/'zdroje/etapa1-kufriky.json').read_text())
RECORDS=[r for r in CAT['records'] if r['group']=='kufriky']

def read_glb(file):
    data=file.read_bytes()
    magic,version,total=struct.unpack_from('<III',data)
    if (magic,version,total)!=(0x46546c67,2,len(data)):raise ValueError('GLB header')
    offset=12;chunks={}
    while offset<len(data):
        n,kind=struct.unpack_from('<II',data,offset);offset+=8
        if n%4 or offset+n>len(data) or kind in chunks:raise ValueError('GLB chunk')
        chunks[kind]=data[offset:offset+n];offset+=n
    return json.loads(chunks[0x4e4f534a]),chunks[0x004e4942]

def array(doc,binary,index):
    a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
    if v['buffer']!=0 or a.get('sparse') or v.get('byteStride'):raise ValueError('Unsupported accessor')
    dtype={5126:'<f4',5123:'<u2',5125:'<u4'}[a['componentType']]
    count=a['count']*(3 if a['type']=='VEC3' else 1);start=v.get('byteOffset',0)+a.get('byteOffset',0)
    out=np.frombuffer(binary,dtype=dtype,count=count,offset=start)
    if a['type']=='VEC3':out=out.reshape(-1,3)
    return out

def inspect(file):
    doc,binary=read_glb(file);lo=np.full(3,np.inf);hi=-lo;parts=[];vertices=0;triangles=0
    for node_id in doc['scenes'][doc.get('scene',0)]['nodes']:
        node=doc['nodes'][node_id]
        if any(k in node for k in ('translation','rotation','scale','matrix','children')):raise ValueError('Unexpected transform')
        for prim in doc['meshes'][node['mesh']]['primitives']:
            p=array(doc,binary,prim['attributes']['POSITION']).astype(np.float64)
            normal=array(doc,binary,prim['attributes']['NORMAL']).astype(np.float64)
            indices=array(doc,binary,prim['indices'])
            if len(indices)%3 or indices.max()>=len(p):raise ValueError('Indices')
            if not np.isfinite(p).all() or not np.isfinite(normal).all():raise ValueError('Non-finite geometry')
            if np.max(np.abs(np.linalg.norm(normal,axis=1)-1))>.002:raise ValueError('Non-unit normal')
            faces=p[indices.reshape(-1,3)]
            area2=np.linalg.norm(np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0]),axis=1)
            if np.any(area2<1e-7):raise ValueError('Degenerate triangle '+node['name'])
            lo=np.minimum(lo,p.min(axis=0));hi=np.maximum(hi,p.max(axis=0));vertices+=len(p);triangles+=len(faces)
            parts.append({'name':node['name'],'role':node['extras']['component'],'vertices':p,'faces':faces,'material':prim['material']})
    if not parts:raise ValueError('No geometry')
    return doc,parts,{'min_mm':lo.tolist(),'max_mm':hi.tolist(),'size_xyz_mm':(hi-lo).tolist(),'vertices_measured':vertices,'triangles':triangles,'parts':len(parts)}

def ray_hits(faces,origin,direction):
    """Independent Möller–Trumbore intersections; both sides, distance in mm."""
    o=np.asarray(origin,dtype=float);d=np.asarray(direction,dtype=float)
    a=faces[:,0];e1=faces[:,1]-a;e2=faces[:,2]-a;h=np.cross(np.broadcast_to(d,e2.shape),e2);det=np.einsum('ij,ij->i',e1,h)
    valid=np.abs(det)>1e-8;inv=np.zeros_like(det);inv[valid]=1/det[valid];s=o-a;u=inv*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1);v=inv*(q@d);t=inv*np.einsum('ij,ij->i',e2,q)
    valid &= (u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)&(t>1e-6)
    return np.sort(t[valid])

class RealShapeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models={};cls.rows=[]
        for r in RECORDS:
            for v in r['model_variants']:
                doc,parts,m=inspect(ROOT/v['file']);cls.models[v['sku']]=(doc,parts,m)
                target=[r['outer']['mm'][k] for k in ('width','length','height')];delta=[x-y for x,y in zip(m['size_xyz_mm'],target)]
                cls.rows.append({'sku':v['sku'],'file':v['file'],'source_url':r['outer']['source_url'],'target_xyz_mm':target,'actual':m,'deviation_xyz_mm':delta,'comparison_tolerance_mm':.01,'physical_tolerance_mm':None,'physical_accuracy_verified':False,'sha256':hashlib.sha256((ROOT/v['file']).read_bytes()).hexdigest(),'bytes':v['bytes']})
        OUT.mkdir(exist_ok=True)
        (OUT/'rozmery.json').write_text(json.dumps({'status':'measured_tests_pending','types_measured':len(RECORDS),'sku_models_measured':len(cls.rows),'vertices_measured':sum(r['actual']['vertices_measured'] for r in cls.rows),'rows':cls.rows},ensure_ascii=False,indent=2)+'\n')

    def test_01_scope_and_original_sources_preserved(self):
        self.assertEqual(len(RECORDS),20);self.assertEqual(len(self.models),21)
        originals={r['id']:r for r in FIRST['records']}
        self.assertEqual({r['id'] for r in RECORDS},{r['id'] for r in FIRST['records'] if r['group']=='kufriky'})
        for r in CAT['records']:
            for field in ('sku','outer','inner','sales','observations','notes','image'):
                self.assertEqual(r[field],originals[r['id']][field],r['id']+' '+field)
        self.assertEqual(CAT['model_order'][:2],['milwaukee-packout-4932471064','milwaukee-packout-4932464082'])
        self.assertEqual(sum(r['group']=='ostatni' and r['model_file'] is None for r in CAT['records']),14)

    def test_02_every_vertex_matches_published_envelope(self):
        for row in self.rows:
            self.assertLess(max(abs(x) for x in row['deviation_xyz_mm']),.01,row['sku'])
            self.assertLess(row['bytes'],3_000_000)
            self.assertEqual((ROOT/row['file']).read_bytes(),(SITE/row['file']).read_bytes())
            self.assertGreater(row['actual']['triangles'],1000)
            self.assertGreater(row['actual']['parts'],25)

    def test_03_no_box_surrogate_or_false_precision(self):
        for r in RECORDS:
            self.assertEqual(r['detail_level'],'realny_tvar');self.assertFalse(r['physical_accuracy_verified']);self.assertTrue(r['model_file'])
            for v in r['model_variants']:
                doc,parts,m=self.models[v['sku']];meta=doc['asset']['extras']
                self.assertEqual(meta['units'],'mm');self.assertTrue(meta['is_product_geometry']);self.assertFalse(meta['physical_accuracy_verified']);self.assertIsNone(meta['physical_tolerance_mm'])
                self.assertEqual(meta['sku'],v['sku']);self.assertEqual(meta['catalog_axes'],{'X':'width','Y':'length','Z':'height'})
                self.assertFalse(any('OBALKA' in p['name'] for p in parts))
                self.assertTrue(any(p['name'].startswith('PACKOUT-spodni-') for p in parts))
        self.assertEqual(CAT['model_summary']['exact_models_ready'],0)

    def test_04_bin_topology_is_open_not_solid(self):
        for sku,count in [('4932471064',10),('4932464082',10),('4932471065',5),('4932478625',10),('4932498323',10)]:
            doc,parts,m=self.models[sku];self.assertEqual(doc['asset']['extras']['bin_count'],count)
            bins=[p for p in parts if '-duta-stena' in p['name'] and p['role']=='bins' or '-dute-cire-steny' in p['name']]
            self.assertEqual(len(bins),count)
            for p in bins:
                bmin=p['vertices'].min(axis=0);bmax=p['vertices'].max(axis=0);origin=(bmin+bmax)/2;origin[2]=bmax[2]+10
                self.assertEqual(len(ray_hits(p['faces'],origin,[0,0,-1])),0,'Open bin mouth '+p['name'])

    def test_05_drawer_counts_and_no_filled_interior(self):
        for sku,count in [('4932472129',2),('4932472130',3),('4932493189',4),('4932493190',3),('4932498651',1)]:
            doc,parts,m=self.models[sku];walls=[p for p in parts if '-dute-steny' in p['name']]
            self.assertEqual(len(walls),count)
            for p in walls:
                bmin=p['vertices'].min(axis=0);bmax=p['vertices'].max(axis=0);origin=(bmin+bmax)/2;origin[2]=bmax[2]+10
                self.assertEqual(len(ray_hits(p['faces'],origin,[0,0,-1])),0)

    def test_06_real_handholes_and_wheels_present(self):
        doc,parts,m=self.models['4932471724']
        walls=[p for p in parts if 's-otvorem' in p['name']];self.assertEqual(len(walls),4)
        for p in walls:
            xyz=p['vertices'];a=xyz.min(axis=0);b=xyz.max(axis=0);origin=(a+b)/2;origin[2]=a[2]+(b[2]-a[2])*.85
            axis=int(np.argmin(b-a));origin[axis]=b[axis]+10;direction=np.zeros(3);direction[axis]=-1
            self.assertEqual(len(ray_hits(p['faces'],origin,direction)),0,'Handle through hole '+p['name'])
        for sku in ('4932464078','4932478161','4932498651'):
            parts=self.models[sku][1];self.assertEqual(sum(p['name'].startswith('kolo-pneumatika-') for p in parts),2)
            self.assertGreater(sum(p['name'].startswith('kolo-paprsek-') for p in parts),20)

    def test_07_public_preview_has_no_internal_paths_or_external_runtime(self):
        html=(SITE/'index.html').read_text();self.assertIn('<meta name="robots" content="noindex, nofollow">',html);self.assertIn("connect-src 'none'",html)
        for f in SITE.rglob('*'):
            if f.suffix in ('.html','.json','.csv') or f.name in ('app.js','data.js'):
                txt=f.read_text(encoding='utf-8-sig')
                for forbidden in ('/home/openai1','/opt/','ukoly/'):
                    self.assertNotIn(forbidden,txt,str(f))
        js=(SITE/'app.js').read_text();self.assertNotRegex(js,r'\b(fetch|XMLHttpRequest|WebSocket|EventSource)\b')
        self.assertNotRegex(html,r'<script[^>]*src=["\']https?://')
        for r in RECORDS:self.assertTrue((SITE/r['image']['file']).exists())

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(RealShapeChecks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    file=OUT/'rozmery.json'
    if file.exists():
        report=json.loads(file.read_text());report['status']='PASS_shape_and_published_envelope' if result.wasSuccessful() else 'FAIL';file.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
