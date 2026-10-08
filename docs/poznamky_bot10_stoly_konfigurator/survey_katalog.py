import sys, json, os, collections
sys.path.insert(0,'/tmp/claude-0/-opt-konfigurator/3a4f3da8-6534-422d-a853-fe8654c9f7d6/scratchpad/v3d/api')
import v3d_glb
KAT='/opt/konfigurator/webapp/katalog/'
st=collections.Counter(); bad=[]; rows=[]
for fn in sorted(os.listdir(KAT)):
    if not fn.endswith('.glb'): continue
    p=KAT+fn
    try:
        g,b=v3d_glb.read_glb(open(p,'rb').read())
    except Exception as e:
        bad.append((fn,str(e))); continue
    st['n']+=1
    nm=len(g.get('meshes',[])); st['meshes>1']+= nm>1
    npr=sum(len(m['primitives']) for m in g.get('meshes',[])); st['prims>1']+= npr>1
    st['has_mat']+= bool(g.get('materials')); st['has_img']+= bool(g.get('images')); st['has_tex']+=bool(g.get('textures'))
    xf=any(any(k in n for k in ('matrix','translation','rotation','scale')) for n in g.get('nodes',[]))
    st['node_xform']+=xf
    st['sparse/draco']+= bool(g.get('extensionsUsed'))
    st['no_normal']+= any('NORMAL' not in pr['attributes'] for m in g.get('meshes',[]) for pr in m['primitives'])
    st['has_color']+= any('COLOR_0' in pr['attributes'] for m in g.get('meshes',[]) for pr in m['primitives'])
    st['has_uv']+= any('TEXCOORD_0' in pr['attributes'] for m in g.get('meshes',[]) for pr in m['primitives'])
    st['no_indices']+= any('indices' not in pr for m in g.get('meshes',[]) for pr in m['primitives'])
    st['mode!=4']+= any(pr.get('mode',4)!=4 for m in g.get('meshes',[]) for pr in m['primitives'])
    st['skins']+= bool(g.get('skins')); st['anim']+=bool(g.get('animations'))
    nv=sum(g['accessors'][pr['attributes']['POSITION']]['count'] for m in g.get('meshes',[]) for pr in m['primitives'])
    rows.append((fn,os.path.getsize(p),nv,nm,npr,xf))
print(dict(st)); print('bad',bad[:5],len(bad))
rows.sort(key=lambda r:-r[2]); print('top verts',rows[:8])
import statistics
print('median verts',statistics.median(r[2] for r in rows),'median size',statistics.median(r[1] for r in rows))
json.dump(rows,open('survey_katalog.json','w'))
