import sys, json, time, collections
sys.dont_write_bytecode=True
sys.path.insert(0,'.')
import numpy as np, prototyp_compose_glb as P, db
c,cur=db.ro()
cur.execute("SELECT id,name,data FROM product_assemblies ORDER BY id")
rows=cur.fetchall()
res=[]; t0=time.time()
allpids=set()
data={}
for r in rows:
    d=json.loads(r['data']); data[r['id']]=(r['name'],d)
    for p in d.get('parts',[]): allpids.add(p['part_id'])
cat=P.resolve_catalog(cur,allpids)
print('sestav',len(rows),'různých part_id',len(allpids),'chybí v katalogu',[p for p in allpids if p not in cat and not p.startswith('car_body_')][:10])
st=collections.Counter(); diffs=[]
for aid,(name,d) in data.items():
    ps=d.get('parts',[])
    ps=[p for p in ps if not p['part_id'].startswith('car_body_') and not (p.get('role') or '').startswith(('logo-ochrana','kontrolni-pomucka'))]
    summ=d.get('price_summary') or {}
    stored=summ.get('joint_count'); ver=summ.get('joint_rule_version')
    try:
        ng,_=P.count_joints(ps,cat,False)
        nl,_=P.count_joints(ps,cat,True)
    except Exception as e:
        st['chyba']+=1; diffs.append((aid,'ERR',str(e)[:80])); continue
    st['celkem']+=1
    if ver==3 and stored is not None:
        st['v3']+=1
        st['geo==stored']+= (ng==stored); st['geo+lic==stored']+= (nl==stored); st['geo|geo+lic ==stored']+= (ng==stored or nl==stored)
        if ng!=stored: diffs.append((aid,name[:30],len(ps),'stored',stored,'geo',ng,'geo+lic',nl))
print(dict(st), 'čas %.1fs'%(time.time()-t0))
for x in diffs[:25]: print(x)
