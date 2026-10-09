"""Čistý audit všech skutečných meshů a spodních ploch, bez DB a sítě.

Zpráva obsahuje i očekávané přesahy víka/nožek na Z. Není to měření
nekótovaných součástí fyzického výrobku ani certifikace spojů PACKOUT.
"""
from pathlib import Path
import json, re, hashlib, csv, unittest
import numpy as np
from over_realne_tvary import inspect, ray_hits
from over_podstavy_v4 import audit as audit_supports, SUPPORT, FLOORS

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'overeni-tvar-v5'
ORGS=['4932471064','4932464082','4932471065','4932478625','4932498323']
TOL=.01

def xy_bounds(part):
    return part['vertices'].min(0),part['vertices'].max(0)

def part_failures(part,lo,hi,organizer):
    a,b=xy_bounds(part);errors=[]
    if organizer:
        # ALL nodes, no bypass by colour, name or material. The side photos
        # show latches and handle recessed behind the full moulded corners.
        if max(0,*(lo[:2]-a[:2]),*(b[:2]-hi[:2]))>TOL:
            errors.append('Součást přesahuje plný půdorysný obrys trupu')
        if 'celo-roh-ochrana-' in part['name']:
            errors.append('Původní samostatná čelní deska stále přítomná')
        if part['name']=='zamek-packout-cerveny':
            errors.append('Původní generická červená smyčka stále přítomná')
    return errors

def audit(file,record,organizer):
    doc,parts,m=inspect(file);floor=next(p for p in parts if p['name'] in FLOORS)
    lo,hi=xy_bounds(floor)
    body_parts=[p for p in parts if p['name'] in FLOORS or p['name'] in ['telo-duta-stena','pojezdove-telo-duta-stena','skrin-bocni-stena-1','skrin-bocni-stena--1','vyklopny-organizer-obvodovy-ram']]
    vertices=np.concatenate([p['vertices'] for p in body_parts]);blo,bhi=vertices.min(0),vertices.max(0)
    # Use the real floor for XY; this catches v4 boards even when they set
    # the model's source-sized outer envelope themselves.
    rows=[];fail=[]
    for p in parts:
        a,b=xy_bounds(p);over=np.maximum(0,np.maximum(lo-a,b-hi))
        errors=part_failures(p,lo,hi,organizer);fail.extend(p['name']+': '+x for x in errors)
        kind='spodní díl' if SUPPORT.match(p['name']) else 'víko / pant' if p['role']=='lid' or p['name'].startswith('pant-') else 'čelní díl' if re.match(r'^(zapadka|drzadlo|PACKOUT-(celni|spodni-odjist))',p['name']) else 'trup / vnitřní díl'
        rows.append({'part':p['name'],'role':p['role'],'material':doc['materials'][p['material']]['name'],
                     'min_mm':a.tolist(),'max_mm':b.tolist(),'center_mm':((a+b)/2).tolist(),
                     'vertices_measured':len(p['vertices']),'over_floor_xyz_mm':over.tolist(),
                     'over_body_xyz_mm':np.maximum(0,np.maximum(blo-a,b-bhi)).tolist(),
                     'classification':kind,'failures':errors})
    expected=[record['outer']['mm'][k] for k in ['width','length','height']]
    delta=np.array(m['size_xyz_mm'])-expected
    if np.abs(delta).max()>TOL:fail.append('Nesouhlasí zdrojová obálka')
    if file.stat().st_size>=3_000_000:fail.append('Soubor nad 3 MB')
    if doc['asset']['extras']['envelope_fit']['axis_scale']!=[1,1,1]:fail.append('Dodatečné natažení geometrie')
    supports=audit_supports(file,file.stem);fail.extend(supports['failures'])
    exact=[]
    # Test every foot vertex AND top-cap centroid against actual floor faces.
    # This supplements the old convex hull test: a notch or hole cannot pass
    # just because it lies inside the enclosing rectangle / convex hull.
    for p in parts:
        if not SUPPORT.match(p['name']) or p['name'].startswith('PACKOUT-spodni-zub-'):continue
        top=p['vertices'][:,2].max();v=p['vertices'];caps=p['faces'][np.all(abs(p['faces'][:,:,2]-top)<.001,axis=1)]
        points=np.concatenate([v[abs(v[:,2]-top)<.001],caps.mean(1)])
        bad=[]
        for point in points:
            start=point.copy();start[2]=lo[2]-.1
            hits=ray_hits(floor['faces'],start,[0,0,1])
            if not len(hits) or abs(start[2]+hits[0]-lo[2])>.011:bad.append(point.tolist())
        exact.append({'part':p['name'],'surface_points_measured':len(points),'unsupported_points':bad})
        if bad:fail.append(p['name']+': vrchol nebo plocha mimo skutečnou spodní plochu')
    if organizer and file.stem!='4932498323':
        release=next(p for p in parts if p['name']=='PACKOUT-spodni-odjistovaci-tlacitko');a,b=xy_bounds(release)
        if a[2]<lo[2]-TOL:fail.append('Spodní červené odjištění visí pod trupem')
    return {'sku':file.stem,'name':record['name'],'source_url':record['outer']['source_url'],
            'expected_xyz_mm':expected,'deviation_xyz_mm':delta.tolist(),'actual':m,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
            'bytes':file.stat().st_size,'body_min_mm':blo.tolist(),'body_max_mm':bhi.tolist(),'floor_min_mm':lo.tolist(),'floor_max_mm':hi.tolist(),
            'parts':rows,'supports':supports,'actual_floor_contact':exact,'failures':fail}

def main():
    cat=json.loads((ROOT/'kufriky.json').read_text());rows=[];before=[]
    for ident in cat['model_order']:
        rec=next(r for r in cat['records'] if r['id']==ident)
        for sku in rec['sku']:
            org=sku in ORGS
            rows.append(audit(ROOT/'modely'/(sku+'.glb'),rec,org))
            if org:
                d,p,m=inspect(ROOT/'modely-v4'/(sku+'.glb'));floor=next(t for t in p if t['name'] in FLOORS);lo,hi=xy_bounds(floor)
                before.append({'sku':sku,'body_xy_min_mm':lo[:2].tolist(),'body_xy_max_mm':hi[:2].tolist(),
                               'parts':[{'part':t['name'],'min_mm':xy_bounds(t)[0].tolist(),'max_mm':xy_bounds(t)[1].tolist(),
                                         'over_body_xy_mm':np.maximum(0,np.maximum(lo[:2]-xy_bounds(t)[0][:2],xy_bounds(t)[1][:2]-hi[:2])).tolist(),
                                         'findings':part_failures(t,lo,hi,True)} for t in p]})
    assert len(rows)==21 and len(before)==5,'Neúplný rozsah měření'
    failures=[r for r in rows if r['failures']]
    result={'status':'FAIL' if failures else 'PASS','models_measured':len(rows),'organizers_measured':len(before),
            'parts_measured':sum(len(r['parts']) for r in rows),'vertices_measured':sum(r['actual']['vertices_measured'] for r in rows),
            'supports_measured':sum(r['supports']['supports_measured'] for r in rows),'contact_points_measured':sum(x['surface_points_measured'] for r in rows for x in r['actual_floor_contact']),
            'digital_tolerance_mm':TOL,'physical_accuracy_verified':False,'rows':rows}
    (OUT/'soucasti-pred-v4.json').write_text(json.dumps(before,ensure_ascii=False,indent=2)+'\n')
    (OUT/'soucasti.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'soucasti.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter=';');w.writerow(['SKU','součást','min X','min Y','min Z','max X','max Y','max Z','přesah X vůči dnu','přesah Y vůči dnu','přesah Z vůči dnu','druh','nález'])
        for r in rows:
            for p in r['parts']:w.writerow([r['sku'],p['part'],*p['min_mm'],*p['max_mm'],*p['over_floor_xyz_mm'],p['classification'],' | '.join(p['failures'])])
    print(result['status'],{k:v for k,v in result.items() if k not in ['rows']})
    for r in failures:print(r['sku'],r['failures'])
    return int(bool(failures))

class Regression(unittest.TestCase):
    def setUp(self):
        _,self.parts,_=inspect(ROOT/'modely/4932464082.glb');floor=next(p for p in self.parts if p['name']=='telo-dno');self.lo,self.hi=xy_bounds(floor)
    def test_v4_boards_fail(self):
        _,p,_=inspect(ROOT/'modely-v4/4932464082.glb');f=next(t for t in p if t['name']=='telo-dno');a,b=xy_bounds(f)
        self.assertEqual(sum(bool(part_failures(t,a,b,True)) for t in p if t['name'].startswith('celo-roh-ochrana-')),2)
    def test_random_mesh_outside_fails_without_name_dependency(self):
        t=next(p for p in self.parts if p['name'].startswith('prihradka-')).copy();t['name']='libovolna-soucast';t['vertices']=t['vertices']+[500,0,0]
        self.assertTrue(part_failures(t,self.lo,self.hi,True))
    def test_center_inside_but_corner_outside_fails(self):
        t=next(p for p in self.parts if p['name'].startswith('patka-')).copy();t['vertices']=t['vertices'].copy();t['vertices'][0,0]=self.hi[0]+2
        self.assertTrue(part_failures(t,self.lo,self.hi,True))
    def test_red_mesh_not_exempted(self):
        t=next(p for p in self.parts if p['name']=='PACKOUT-spodni-odjistovaci-tlacitko').copy();t['vertices']=t['vertices']+[0,500,0]
        self.assertTrue(part_failures(t,self.lo,self.hi,True))
    def test_missing_geometry_is_error(self):
        with self.assertRaises(FileNotFoundError):inspect(ROOT/'modely/neexistuje.glb')
    def test_real_floor_notch_is_not_support_despite_bbox(self):
        floor=next(p for p in self.parts if p['name']=='telo-dno')
        origin=np.array([self.hi[0]-2,0,self.lo[2]-.1])
        self.assertTrue(np.all(origin[:2]>=self.lo[:2]) and np.all(origin[:2]<=self.hi[:2]))
        self.assertEqual(len(ray_hits(floor['faces'],origin,[0,0,1])),0)
    def test_red_release_does_not_hang_below_floor(self):
        release=next(p for p in self.parts if p['name']=='PACKOUT-spodni-odjistovaci-tlacitko')
        self.assertGreaterEqual(release['vertices'][:,2].min(),self.lo[2]-.01)

if __name__=='__main__':
    import sys
    if '--test' in sys.argv:unittest.main(argv=[sys.argv[0]])
    else:sys.exit(main())
