"""Independent offline checks of actual v6 GLB meshes and v5 preservation."""
from pathlib import Path
import json,hashlib,numpy as np
from over_realne_tvary import inspect,ray_hits
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'overeni-tvar-v6'
CAT=json.loads((ROOT/'kufriky.json').read_text())
ORGS=['4932471064','4932464082','4932471065','4932478625','4932498323']
rows=[];errors=[];checks=0
def check(ok,why):
 global checks
 checks+=1
 if not ok:errors.append(why)

for ident in CAT['model_order']:
 rec=next(r for r in CAT['records'] if r['id']==ident)
 for sku in rec['sku']:
  file=ROOT/'nahled-modely-v6/modely'/(sku+'.glb')
  doc,parts,m=inspect(file);meta=doc['asset']['extras']
  expected=np.array([rec['outer']['mm'][k] for k in ['width','length','height']])
  delta=np.array(m['size_xyz_mm'])-expected
  check(np.abs(delta).max()<.01,sku+': source bounds')
  check(file.stat().st_size<3_000_000,sku+': file over 3 MB')
  check(meta['units']=='mm' and meta['catalog_axes']==dict(X='width',Y='length',Z='height'),sku+': unit convention')
  check(meta['envelope_fit']['axis_scale']==[1,1,1],sku+': shape scaled after generation')
  check(not meta['physical_accuracy_verified'] and meta['physical_tolerance_mm'] is None,sku+': unsupported physical precision')
  check(meta['sku']==sku,sku+': wrong SKU')
  if sku not in ORGS:
   check(file.read_bytes()==(ROOT/'nahled-modely-v5/modely'/(sku+'.glb')).read_bytes(),sku+': changed non-organizer')
  else:
   check(meta['revision']=='v6',sku+': missing v6 metadata')
   check((ROOT/'modely'/(sku+'.glb')).read_bytes()==file.read_bytes(),sku+': main model differs')
   names=[p['name'] for p in parts]
   check('celo-roh-ochrana--1' not in names and 'celo-roh-ochrana-1' not in names,sku+': detached front plates')
   check(len(parts)>100,sku+': implausibly empty model')
   # Actual body/floor and every ground support are checked, not just centers.
   floor=next(p for p in parts if p['name'] in ['telo-dno','vyklopny-organizer-zadni-panel'])
   fmin,fmax=floor['vertices'].min(0),floor['vertices'].max(0)
   for p in parts:
    v=p['vertices'];lo,hi=v.min(0),v.max(0)
    over=np.maximum(fmin[:2]-lo[:2],hi[:2]-fmax[:2]);allowed=np.zeros(2)
    if sku=='4932471065' and p['name'].startswith(('drzadlo-','zapadka-','PACKOUT-celni-')):allowed[1]=36 # photo of this SKU shows the handle outside the body, catalog front=+Y
    check((over-allowed).max()<.01,sku+': undocumented overhang outside floor XY '+p['name'])
    if p['name'].startswith(('patka-','PACKOUT-spodni-patka-')):
     cap=hi[2];points=v[abs(v[:,2]-cap)<.001]
     for q in points:
      start=q.copy();start[2]=fmin[2]-.01;hit=ray_hits(floor['faces'],start,[0,0,1])
      check(len(hit)>0 and abs(start[2]+hit[0]-fmin[2])<.01,sku+': foot unsupported '+p['name'])
   expected_bins=dict(zip(ORGS,[10,10,5,8,10]))[sku]
   check(meta['bin_count']==expected_bins,sku+': wrong bin/compartment count')
   if sku=='4932478625':
    check(sum(n.startswith('hluboky-cerveny-') for n in names)==6,sku+': not six red dividers')
    check('hluboky-pevny-stredni-delic' in names,sku+': missing fixed center')
   elif sku=='4932498323':
    check('vyklopny-organizer-obvodovy-ram' not in names,sku+': v5 tall wall remains')
    check(sum('kovova-tyc' in n for n in names)==3,sku+': not three retaining bars')
    check(sum('-vnitrni-delic' in n for n in names)==2,sku+': not two large-bin dividers')
    check('vyklopny-organizer-zapadka-T' in names,sku+': missing T latch')
    check(sum(n.endswith('-dute-cire-steny') for n in names)==10,sku+': not ten separate tip bins')
   else:
    check(sum(n.endswith('-duta-stena') and n.startswith('prihradka-') for n in names)==expected_bins,sku+': missing bins')
    for p in parts:
     if p['name'].startswith('prihradka-') and p['name'].endswith('-duta-stena'):
      lo,hi=p['vertices'].min(0),p['vertices'].max(0);start=(lo+hi)/2;start[2]=hi[2]+.1
      hits=ray_hits(p['faces'],start,[0,0,-1]);check(len(hits)==0,sku+': bin is solid '+p['name'])
    check(sum(n.startswith('viko-prolis-') for n in names)==expected_bins,sku+': wrong sealing windows')
   if sku in ['4932471064','4932478625','4932498323']:
    check(not any(n.startswith('PACKOUT-spodni-patka-') for n in names),sku+': unverified family bottom positions imported')
   else:
    check(sum(n.startswith('PACKOUT-spodni-patka-') for n in names)==(6 if sku=='4932471065' else 12),sku+': wrong own-SKU bottom stations')
   if sku!='4932498323':
    lh=rec['outer']['mm']['height']-max(p['vertices'][:,2].max() for p in parts if p['name']=='telo-duta-stena')-rec['outer']['mm']['height']/2
    check(lh>9,sku+': lid still collapsed')
    roof=next(p for p in parts if p['name']=='viko-panel')
    cavity_height=roof['vertices'][:,2].min()-floor['vertices'][:,2].max()
    check(abs(cavity_height-rec['inner'][0]['mm']['height'])<.01,sku+': closed internal height differs from source')
  rows.append(dict(sku=sku,size_xyz_mm=m['size_xyz_mm'],expected_xyz_mm=expected.tolist(),deviation_xyz_mm=delta.tolist(),bytes=file.stat().st_size,parts=m['parts'],vertices=m['vertices_measured'],sha256=hashlib.sha256(file.read_bytes()).hexdigest(),physical_accuracy_verified=False))

history=json.loads((ROOT/'zdroje/doladeni-v6/historie-v5-hashe.json').read_text())
for row in history:
 p=Path(row['base'])/row['file'];check(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],'v5 history changed: '+str(p))
check(len(rows)==21 and len(history)==930,'Missing model or historical files')
report=dict(status='FAIL' if errors else 'PASS',checks=checks,models=len(rows),organizers=5,history_files=len(history),digital_tolerance_mm=.01,physical_accuracy_verified=False,rows=rows,errors=errors)
OUT.mkdir(exist_ok=True);(OUT/'geometrie.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(report['status'],checks,'kontrol;',len(rows),'modelů;',len(history),'souborů v5 zachováno')
for e in errors[:30]:print(e)
assert not errors
