import sys, struct
sys.path.insert(0,'/tmp/claude-0/-opt-konfigurator/3a4f3da8-6534-422d-a853-fe8654c9f7d6/scratchpad/v3d/api')
import v3d_glb, numpy as np
CT={5120:np.int8,5121:np.uint8,5122:np.int16,5123:np.uint16,5125:np.uint32,5126:np.float32}
NC={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
def accessor(g,b,i):
    a=g['accessors'][i]; bv=g['bufferViews'][a['bufferView']]
    dt=np.dtype(CT[a['componentType']]); nc=NC[a['type']]
    off=bv.get('byteOffset',0)+a.get('byteOffset',0); stride=bv.get('byteStride') or dt.itemsize*nc
    if stride==dt.itemsize*nc:
        arr=np.frombuffer(b,dtype=dt,count=a['count']*nc,offset=off).reshape(a['count'],nc)
    else:
        arr=np.empty((a['count'],nc),dtype=dt)
        for k in range(a['count']):
            arr[k]=np.frombuffer(b,dtype=dt,count=nc,offset=off+k*stride)
    return arr
def mesh_prims(g,b):
    """vrati seznam (pos[N,3] f32, nrm|None, idx[M,3], material_index|None) pro vsechny mesh primitiva (uzly s identitou)"""
    out=[]
    for m in g.get('meshes',[]):
        for p in m['primitives']:
            pos=accessor(g,b,p['attributes']['POSITION']).astype(np.float64)
            nrm=accessor(g,b,p['attributes']['NORMAL']).astype(np.float64) if 'NORMAL' in p['attributes'] else None
            idx=accessor(g,b,p['indices']).astype(np.int64).reshape(-1,3) if 'indices' in p else np.arange(len(pos)).reshape(-1,3)
            out.append((pos,nrm,idx,p.get('material')))
    return out
if __name__=='__main__':
    KAT='/opt/konfigurator/webapp/katalog/'
    g,b=v3d_glb.read_glb(open(KAT+sys.argv[1],'rb').read())
    for pos,nrm,idx,mat in mesh_prims(g,b):
        ys=np.unique(np.round(pos[:,1],3)); print('unique y',ys[:20],len(ys))
        print('verts',len(pos),'faces',len(idx))
        print('xz unique at y=-500:',len(np.unique(np.round(pos[np.isclose(pos[:,1],-500,atol=0.01)][:,[0,2]],3),axis=0)))
        xz=np.unique(np.round(pos[:,[0,2]],2),axis=0); print('xz outline pts',len(xz)); print(xz[:60].tolist())
