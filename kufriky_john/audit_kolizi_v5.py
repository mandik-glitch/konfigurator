"""Čistý objemový audit vybraných součástí proti nosnému tělu.

Vzorkuje skutečný materiál pomocí průsečíků paprsku s trojúhelníky.
Žádný pozitivní nález není odvozen jen z průniku obálek. Nula vzorků
uvnitř obou dílů není certifikací úplné absence všech kolizí.
"""
import json
from pathlib import Path
import numpy as np
from over_realne_tvary import inspect,ray_hits

ROOT=Path(__file__).resolve().parent
CAT=json.loads((ROOT/'kufriky.json').read_text())

def inside(part,point):
    hits=ray_hits(part['faces'],point,[.8013,.3927,.4519])
    if not len(hits):return False
    unique=hits[np.r_[True,np.diff(hits)>.0001]]
    return len(unique)%2==1

def material_points(part):
    faces=part['faces'];norm=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0]);norm/=np.linalg.norm(norm,axis=1)[:,None]
    chosen=np.linspace(0,len(faces)-1,min(36,len(faces)),dtype=int)
    centers=faces[chosen].mean(axis=1);normal=norm[chosen]
    points=np.vstack((centers-.25*normal,centers+.25*normal))
    return [p for p in points if inside(part,p)]

if __name__=='__main__':
    rows=[];overlaps=[];samples=0
    for record in CAT['records']:
        if record['group']!='kufriky':continue
        for variant in record['model_variants']:
            sku=variant['sku'];doc,parts,m=inspect(ROOT/variant['file'])
            body=[p for p in parts if p['name'] in ('telo-dno','telo-duta-stena','pojezdove-telo-dno','pojezdove-telo-duta-stena','skrin-zadni-stena','skrin-bocnice--1','skrin-bocnice-1','skrin-zada','skrin-bok--1','skrin-bok-1','skrin-dno','skrin-strop')]
            moving=[p for p in parts if (p['role']=='bins' and p['name'].startswith('prihradka-')) or p['name'].startswith('profesni-panel-') or p['name']=='dvere-panel' or (p['role'].startswith('drawer-') and ('dno' in p['name'] or 'dute-steny' in p['name']))]
            for part in moving:
                points=material_points(part);samples+=len(points)
                if not points:raise ValueError('Nevzorkovatelná součást '+sku+' '+part['name'])
                lo=part['vertices'].min(0);hi=part['vertices'].max(0)
                for other in body:
                    a=other['vertices'].min(0);b=other['vertices'].max(0)
                    if np.any(np.minimum(hi,b)-np.maximum(lo,a)<-.001):continue
                    common=[p.tolist() for p in points if np.all(p>a+.001) and np.all(p<b-.001) and inside(other,p)]
                    row={'sku':sku,'moving_part':part['name'],'body_part':other['name'],'material_samples':len(points),'shared_material_samples':len(common)}
                    rows.append(row)
                    if common:overlaps.append({**row,'witnesses_mm':common[:6]})
    result={'status':'PASS_sampled_material_clearance' if not overlaps else 'UNRESOLVED_material_overlap','sku_measured':21,'candidate_pairs_measured':len(rows),'material_samples_measured':samples,'rows':rows,'overlaps':overlaps,
            'exclusions':['Vlastní části jednoho výlisku, spony, osy kol a upevňovací prvky: styky a montážní uložení mají jiná kritéria.','Zjednodušené paprsky v nábojích a vizuální nápisy; nejde o výrobní rozklad.'],
            'limits':'Vzorkované průniky vybraných vnitřních nádob, zásuvek a dvířek s nosným tělem; nezaručuje kompletní bezkoliznost všech povrchů ani kinematiku.'}
    (ROOT/'overeni-tvar-v5/kolize.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(result['status'],len(rows),'párů,',samples,'materiálových vzorků,',len(overlaps),'nálezů.')
    for row in overlaps:print(row['sku'],row['moving_part'],row['body_part'],row['shared_material_samples'])
    raise SystemExit(1 if overlaps else 0)
