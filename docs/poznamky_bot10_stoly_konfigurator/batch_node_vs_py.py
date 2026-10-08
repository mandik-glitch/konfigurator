import sys, json, subprocess, time
sys.dont_write_bytecode=True
sys.path.insert(0,'.')
import prototyp_compose_glb as P, db
c,cur=db.ro()
cur.execute("SELECT id,data FROM product_assemblies ORDER BY id"); rows=cur.fetchall()
allp=set(); batch=[]; py={}; stored={}
data={}
for r in rows:
    d=json.loads(r['data']); data[r['id']]=d
    for p in d['parts']: allp.add(p['part_id'])
cat=P.resolve_catalog(cur,allp)
for aid,d in data.items():
    ps=[p for p in d['parts'] if not p['part_id'].startswith('car_body_') and not (p.get('role') or '').startswith(('logo-ochrana','kontrolni-pomucka'))]
    batch.append({'id':aid,'parts':[{k:p[k] for k in ('part_id','position','quaternion','scale')} for p in ps]})
    py[aid]=P.count_joints(ps,cat,False)[0]; stored[aid]=d['price_summary']['joint_count']
inp={'batch':batch,'glb_map':{k:v['glb'] for k,v in cat.items()},'is_profile':{k:v['is_profile'] for k,v in cat.items()},'length_mm':{k:v['length_mm'] for k,v in cat.items()},'cross':{k:v['cross'] for k,v in cat.items()}}
json.dump(inp,open('out/batch_in.json','w'))
t0=time.time()
r=subprocess.run(['node','node_ref.js','out/batch_in.json','out/batch_out.json'],capture_output=True,text=True,cwd='/tmp/claude-0/-opt-konfigurator/3a4f3da8-6534-422d-a853-fe8654c9f7d6/scratchpad/konfigurator')
print(r.stdout.strip() or r.stderr[:800], 'node %.0fs'%(time.time()-t0))
nd=json.load(open('out/batch_out.json'))
eq=sum(1 for a in py if nd[str(a)]==py[a]); print('Python == Node(scene.html kód) jen geometrie:',eq,'/',len(py))
print('Python == uložený price_summary.joint_count:',sum(1 for a in py if py[a]==stored[a]),'/',len(py))
print('Node == uložený:',sum(1 for a in py if nd[str(a)]==stored[a]),'/',len(py))
print('rozdíly Python vs Node:',[(a,py[a],nd[str(a)]) for a in py if nd[str(a)]!=py[a]][:10])
