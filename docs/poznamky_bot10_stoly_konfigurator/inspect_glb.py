import sys, json
sys.path.insert(0,'/tmp/claude-0/-opt-konfigurator/3a4f3da8-6534-422d-a853-fe8654c9f7d6/scratchpad/v3d/api')
import v3d_glb, numpy as np
KAT='/opt/konfigurator/webapp/katalog/'
def info(fn):
    g,b=v3d_glb.read_glb(open(KAT+fn,'rb').read())
    print('==',fn, 'nodes',len(g.get('nodes',[])),'meshes',len(g.get('meshes',[])),'mats',len(g.get('materials',[])),'images',len(g.get('images',[])),'scenes',g.get('scenes'),'exts',g.get('extensionsUsed'))
    for i,n in enumerate(g.get('nodes',[])):
        print('  node',i,{k:v for k,v in n.items()})
    for i,m in enumerate(g.get('meshes',[])):
        for p in m['primitives']:
            a=g['accessors'][p['attributes']['POSITION']]
            print('  mesh',i,m.get('name'),'prims',len(m['primitives']),'attrs',list(p['attributes']),'mat',p.get('material'),'count',a['count'],'min',a.get('min'),'max',a.get('max'),'idx',p.get('indices'), 'mode',p.get('mode'))
    for i,m in enumerate(g.get('materials',[])): print('  material',i,m)
for fn in sys.argv[1:]: info(fn)
