import sys, numpy as np, db
sys.path.insert(0,'.')
import glbnp, v3d_glb
KAT='/opt/konfigurator/webapp/katalog/'
c,cur=db.ro()
rows=[]
cur.execute("SELECT id,name,layer,glb_file,dim_x_mm,dim_y_mm,dim_z_mm FROM cfg_dily WHERE glb_file IS NOT NULL")
for r in cur.fetchall(): rows.append(('cfg',r['id'],r['name'],r['layer'],r['glb_file']))
cur.execute("SELECT id,name,glb_file,is_profile_material,is_board_material FROM shop_products WHERE glb_file IS NOT NULL AND (is_profile_material=1 OR is_board_material=1)")
for r in cur.fetchall(): rows.append(('prod%s%s'%('P' if r['is_profile_material'] else '','B' if r['is_board_material'] else ''),'product_%d'%r['id'],r['name'],None,r['glb_file']))
print(len(rows))
for kind,i,name,layer,fn in rows:
    try:
        g,b=v3d_glb.read_glb(open(KAT+fn,'rb').read())
    except Exception as e:
        print(kind,i,fn,'ERR',e); continue
    P=np.concatenate([p[0] for p in glbnp.mesh_prims(g,b)])
    mn,mx=P.min(0),P.max(0); ext=mx-mn; ax=int(np.argmax(ext))
    u=len(np.unique(np.round(P[:,ax],2)))
    cs=sorted([ext[k] for k in range(3) if k!=ax])
    print(f"{kind:6} {i:22} {fn:28} ext={np.round(ext,1).tolist()} lenAxis={'xyz'[ax]} uniqLenVals={u} center={np.round((mn+mx)/2,1).tolist()} {name[:40]}")
