import sys, json
sys.dont_write_bytecode=True
sys.path.insert(0,'.')
import numpy as np, prototyp_compose_glb as P, db
c,cur=db.ro()
cur.execute("SELECT data FROM custom_shapes WHERE id=577"); d=json.loads(cur.fetchone()['data']); parts=d['parts']
cat=P.resolve_catalog(cur,{p['part_id'] for p in parts})
ng,pg=P.count_joints(parts,cat,False); nl,pl=P.count_joints(parts,cat,True)
extra=sorted(set(pl)-set(pg)); print('geo',ng,'lic',nl,'jen v lic_peers:',extra)
ents={}
for i,p in enumerate(parts):
    cc=cat[p['part_id']]
    if cc['is_profile']: ents[i]=P.ProfEntry(i,p,P.catglb(cc['glb']))
for (i,j) in extra:
    a,b=ents[i],ents[j]
    print((i,j),'A',np.round(a.bmin,1),np.round(a.bmax,1),'B',np.round(b.bmin,1),np.round(b.bmax,1))
    for ax in 'xyz'.replace('x','x'):
        pass
    gap=[max(a.bmin[k]-b.bmax[k], b.bmin[k]-a.bmax[k]) for k in range(3)]
    ov=[min(a.bmax[k],b.bmax[k])-max(a.bmin[k],b.bmin[k]) for k in range(3)]
    print('   gap',np.round(gap,2),'overlap',np.round(ov,2),'axisdot',round(float(abs(a.axis_w@b.axis_w)),3),'joint?',P.is_real_joint(a,b))
# stored joint_count sum per part and lic_peers listing counts
print(sum(p.get('joint_count',0) for p in parts), sum(len(p.get('lic_peers',[])) for p in parts))
