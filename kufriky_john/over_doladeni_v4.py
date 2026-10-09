"""Nezávislé čisté kontroly GLB: skutečné vrcholy, dutiny a uchycení.

Kontakt dokládá bod na trojúhelníku nebo průsečík hrany s trojúhelníkem.
Obálky slouží pouze k výběru kandidátů. Vzorkování není úplným důkazem
absence všech kolizí; podrobnosti rozsahu jsou v uloženém výsledku.
"""
from pathlib import Path
import hashlib
import json
import re
import sys
import unittest
import numpy as np
from over_realne_tvary import inspect, ray_hits

ROOT=Path(__file__).resolve().parent
SITE=ROOT/'nahled-modely-v4'
OUT=ROOT/'overeni-tvar-v4'
CAT=json.loads((ROOT/'kufriky.json').read_text())
BEFORE=json.loads((ROOT/'zdroje/doladeni-v3/pred-kufriky.json').read_text())

def bounds(part):
    return part['vertices'].min(axis=0),part['vertices'].max(axis=0)

def samples(part,maximum=100):
    pts=np.unique(part['vertices'],axis=0)
    if len(pts)>maximum:pts=pts[np.linspace(0,len(pts)-1,maximum,dtype=int)]
    centroids=part['faces'].mean(axis=1)
    if len(centroids)>maximum:centroids=centroids[np.linspace(0,len(centroids)-1,maximum,dtype=int)]
    return np.vstack((pts,centroids))

def point_surface_distance(points,faces):
    """Exact contact distances; triangles too far for 0.08 mm are excluded."""
    best=float('inf'); lo=faces.min(axis=1)-.081;hi=faces.max(axis=1)+.081
    for p in points:
        mask=np.all((p>=lo)&(p<=hi),axis=1)
        if not mask.any():continue
        f=faces[mask];a,b,c=f[:,0],f[:,1],f[:,2];e1,e2=b-a,c-a
        normal=np.cross(e1,e2);nn=(normal*normal).sum(axis=1)
        pa=p-a;h=(pa*normal).sum(axis=1)/nn;projection=p-h[:,None]*normal;v=projection-a
        d00=(e1*e1).sum(1);d01=(e1*e2).sum(1);d11=(e2*e2).sum(1)
        d20=(v*e1).sum(1);d21=(v*e2).sum(1);den=d00*d11-d01*d01
        u=(d11*d20-d01*d21)/den;w=(d00*d21-d01*d20)/den
        inside=(u>=-1e-8)&(w>=-1e-8)&(u+w<=1+1e-8)
        if inside.any():best=min(best,float(np.min(h[inside]**2*nn[inside])))
        for v0,v1 in ((a,b),(b,c),(c,a)):
            edge=v1-v0;length2=(edge*edge).sum(1);valid=length2>1e-12
            edge=edge[valid];v0=v0[valid];length2=length2[valid]
            if not len(edge):continue
            t=np.clip(((p-v0)*edge).sum(1)/length2,0,1)
            best=min(best,float(((p-(v0+t[:,None]*edge))**2).sum(1).min()))
        if best<1e-10:return 0.0
    return best**.5

def segment_contact(part,other):
    # Sampling includes all edges of up to 80 triangles. Any reported contact
    # is an actual geometric witness. A missing witness remains unresolved.
    faces=part['faces']
    if len(faces)>80:faces=faces[np.linspace(0,len(faces)-1,80,dtype=int)]
    for tri in faces:
        for a,b in ((tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])):
            v=b-a;length=np.linalg.norm(v)
            if length<1e-8:continue
            hits=ray_hits(other['faces'],a,v/length)
            if len(hits) and hits[0]<=length+.001:return True
    return False

def contact(part,other):
    a,b=bounds(part);c,d=bounds(other)
    gap=np.maximum(np.maximum(c-b,a-d),0)
    if np.linalg.norm(gap)>.08:return None
    dist=point_surface_distance(samples(part,36),other['faces'])
    if dist<=.08:return {'method':'bod–trojúhelník','distance_mm':dist}
    if segment_contact(part,other):return {'method':'hrana–trojúhelník','distance_mm':0.0}
    return None

class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models={};cls.rows=[];cls.attachments=[]
        for r in CAT['records']:
            if r['group']!='kufriky':continue
            for variant in r['model_variants']:
                doc,parts,m=inspect(ROOT/variant['file']);sku=variant['sku']
                cls.models[sku]=(r,doc,parts,m)
                target=[r['outer']['mm'][k] for k in ('width','length','height')]
                cls.rows.append({'sku':sku,'source_url':r['outer']['source_url'],'target_xyz_mm':target,'actual':m,'deviation_xyz_mm':(np.array(m['size_xyz_mm'])-target).tolist(),'tolerance_mm':.01,'sha256':hashlib.sha256((ROOT/variant['file']).read_bytes()).hexdigest(),'bytes':(ROOT/variant['file']).stat().st_size})

    def test_01_sources_scope_and_v2_preserved(self):
        self.assertEqual(len(self.models),21)
        old={r['id']:r for r in BEFORE['records']}
        for r in CAT['records']:
            for field in ('sku','outer','inner','sales','observations','notes','image'):
                self.assertEqual(r[field],old[r['id']][field],r['id']+' '+field)
        self.assertEqual(sum(r['group']=='ostatni' and r['model_file'] is None for r in CAT['records']),14)
        for sku,(r,doc,parts,m) in self.models.items():
            self.assertEqual((ROOT/'modely-v2'/(sku+'.glb')).read_bytes(),(ROOT/'nahled-modely-v2/modely'/(sku+'.glb')).read_bytes())
            self.assertFalse(doc['asset']['extras']['physical_accuracy_verified'])
            self.assertEqual(doc['asset']['extras']['envelope_fit']['axis_scale'],[1,1,1])
            self.assertFalse(doc['asset']['extras']['envelope_fit']['applied'])

    def test_02_all_vertices_envelope_and_size(self):
        for row in self.rows:
            self.assertLess(max(abs(x) for x in row['deviation_xyz_mm']),.01,row['sku'])
            self.assertLess(row['bytes'],3_000_000)
            self.assertGreater(row['actual']['parts'],30)
            self.assertEqual((ROOT/'modely'/(row['sku']+'.glb')).read_bytes(),(SITE/'modely'/(row['sku']+'.glb')).read_bytes())

    def test_03_circular_wheels_and_correct_chest_axle(self):
        for sku,diam,axis in [('4932464078',228,1),('4932498651',228,1),('4932478161',230,0)]:
            parts=self.models[sku][2];wheels=[p for p in parts if p['name'].startswith('kolo-pneumatika')]
            self.assertEqual(len(wheels),2)
            for wheel in wheels:
                lo,hi=bounds(wheel);size=hi-lo
                for a in set(range(3))-{axis}:self.assertAlmostEqual(size[a],diam,places=3)
                center=(lo+hi)/2;radial=np.delete(wheel['vertices']-center,axis,axis=1)
                radial=np.linalg.norm(radial,axis=1);radial=radial[radial>diam*.1]
                self.assertLess(np.max(np.abs(radial-diam/2)),.002)
            if sku=='4932478161':
                centers=[sum(bounds(p))/2 for p in wheels]
                self.assertLess(abs(centers[0][1]-centers[1][1]),.001)
                self.assertGreater(abs(centers[0][0]-centers[1][0]),500)

    def test_04_known_cavities_measured_in_actual_mesh(self):
        type(self).cavity_rows=[]
        for sku,(r,doc,parts,m) in self.models.items():
            meta=doc['asset']['extras']
            for feature in meta['measured_features']:
                if feature['kind'] not in ('cavity','drawer_cavity') or not feature.get('component'):continue
                part=next(p for p in parts if p['name']==feature['component']);lo,hi=bounds(part)
                center=(lo+hi)/2;center[2]=lo[2]+(hi[2]-lo[2])*.5
                distances=[];ray_distances=[]
                for a in [0,1]:
                    hits=[]
                    for sign in [-1,1]:
                        direction=np.zeros(3);direction[a]=sign
                        values=ray_hits(part['faces'],center,direction)
                        self.assertGreater(len(values),0,sku+' cavity axis '+str(a));hits.append(float(values[0]))
                    distances.append(sum(hits));ray_distances.append(hits)
                q=feature['dimensions_mm'];expected=[q['width'],q['length']]
                if meta['front_axis']=='positive_y':expected.reverse()
                self.assertLess(max(abs(a-b) for a,b in zip(distances,expected)),.005,sku+' '+part['name'])
                self.assertAlmostEqual(hi[2]-lo[2],q['height'],places=3)
                self.cavity_rows.append({'sku':sku,'component':part['name'],'measured_opening_xy_mm':distances,'ray_distances_mm':ray_distances,'expected_opening_xy_mm':expected,'measured_height_mm':float(hi[2]-lo[2]),'source_url':feature['source_url']})
        self.assertGreater(len(self.cavity_rows),20)

    def test_05_documented_topology_corrections(self):
        parts=self.models['4932471065'][2]
        self.assertEqual(sum(p['name'].startswith('zapadka-cervena') for p in parts),2)
        parts=self.models['4932471723'][2]
        self.assertEqual(sum(p['name'].startswith('zapadka-cervena') for p in parts),1)
        self.assertTrue(any(p['name']=='kompakt-vnitrni-delic' for p in parts))
        parts=self.models['4932478625'][2]
        self.assertFalse(any(p['name'].startswith('prihradka-') for p in parts))
        self.assertEqual(sum(p['name'].startswith('hluboky-cerveny-delic') for p in parts),2)
        parts=self.models['4932480623'][2]
        self.assertEqual(sum(p['name'].startswith('dvere-horni-pant') for p in parts),2)
        parts=self.models['4932478161'][2]
        self.assertEqual(sum('PACKOUT-horni-drazka' in p['name'] for p in parts),12)
        parts=self.models['4932471724'][2]
        self.assertFalse(any('drzadlo-otevreny' in p['name'] for p in parts))

    def test_06_actual_contact_of_protruding_parts(self):
        failures=[]
        selected=re.compile(r'^(zamek-packout-cerveny|PACKOUT-celni-odjistovaci-tlacitko|zapadka-cervena|zapadka-kov|drzadlo-|bocni-drzadlo-|vyklopne-drzadlo-|roh-kov-|zajistovaci-lista|teleskopicke-madlo|teleskopicka-tyc|bedna-zasunute-bocni-madlo|PACKOUT-spodni-patka|.*-cerveny-uchop|dvere-cerveny-uzaver)')
        for sku,(r,doc,parts,m) in self.models.items():
            for part in parts:
                if not selected.search(part['name']):continue
                candidates=[];lo,hi=bounds(part)
                for other in parts:
                    if other is part or other['name'].startswith('oznaceni'):continue
                    a,b=bounds(other);gap=np.maximum(np.maximum(a-hi,lo-b),0)
                    if np.linalg.norm(gap)<=.08:candidates.append(other)
                witnesses=[]
                for other in candidates:
                    witness=contact(part,other)
                    if witness:witnesses.append({'parent':other['name'],**witness});break
                row={'sku':sku,'part':part['name'],'candidate_count':len(candidates),'contact_witnesses':witnesses}
                self.attachments.append(row)
                if not witnesses:failures.append(sku+' '+part['name'])
        (OUT/'uchyceni.json').write_text(json.dumps({'scope':'Skutečný kontakt vybraných vyčnívajících komponent. Neověřuje kompletní fyzické spoje ani absenci všech kolizí.','parts_measured':len(self.attachments),'candidate_pairs_measured':sum(r['candidate_count'] for r in self.attachments),'rows':self.attachments,'unresolved':failures},ensure_ascii=False,indent=2)+'\n')
        self.assertEqual(failures,[],json.dumps(failures,ensure_ascii=False))

    def test_06b_cups_and_trays_have_actual_support(self):
        measured=[]
        for sku,(r,doc,parts,m) in self.models.items():
            bases=[p for p in parts if (p['name'].startswith('prihradka-') and p['name'].endswith('-dno')) or p['name'] in ('profesni-panel-dno','vlozka-dno')]
            for part in bases:
                supports=[p for p in parts if p['name']=='telo-dno' or p['name'].startswith('vlozka-operna-lista-')]
                witnesses=[p['name'] for p in supports if contact(part,p)]
                self.assertTrue(witnesses,sku+' '+part['name'])
                measured.append({'sku':sku,'part':part['name'],'supports':witnesses})
        self.assertGreater(len(measured),30)
        (OUT/'opory-vlozek.json').write_text(json.dumps({'parts_measured':len(measured),'rows':measured},ensure_ascii=False,indent=2)+'\n')

    def test_07_public_source_links_and_no_copied_photos(self):
        html=(SITE/'index.html').read_text()
        self.assertIn('<meta name="robots" content="noindex, nofollow">',html)
        self.assertIn("connect-src 'none'",html)
        js=(SITE/'app.js').read_text();self.assertNotRegex(js,r'\b(fetch|XMLHttpRequest|WebSocket|EventSource)\b')
        self.assertFalse((SITE/'obrazky').exists())
        for r in CAT['records']:
            if r['group']!='kufriky':continue
            self.assertTrue(r['photo_sources']);self.assertTrue(r['review']['match']);self.assertTrue(r['review']['unverified'])
        for file in SITE.rglob('*'):
            if file.suffix in ('.html','.json','.csv') or file.name in ('app.js','data.js'):
                text=file.read_text(encoding='utf-8-sig')
                for forbidden in ('/home/openai1','/opt/','ukoly/'):self.assertNotIn(forbidden,text,str(file))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'status':'PASS' if result.wasSuccessful() else 'FAIL','models_measured':len(Checks.rows),'vertices_measured':sum(r['actual']['vertices_measured'] for r in Checks.rows),'triangles_measured':sum(r['actual']['triangles'] for r in Checks.rows),'rows':Checks.rows,'cavities':getattr(Checks,'cavity_rows',[]),'limits':'Digitální kontrola geometrií a vybraných uchycení; žádná fyzická tolerance ani úplná kolizní certifikace.'}
    (OUT/'rozmery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
