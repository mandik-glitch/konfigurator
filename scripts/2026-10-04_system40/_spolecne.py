import json, struct, numpy as np
KAT='/opt/konfigurator/webapp/katalog/'
def load_glb(path):
    b=open(path,'rb').read(); n=struct.unpack('<I',b[12:16])[0]; j=json.loads(b[20:20+n]); off=20+n
    m2=struct.unpack('<I',b[off:off+4])[0]; BIN=b[off+8:off+8+m2]
    CT={5126:np.float32,5123:np.uint16,5125:np.uint32}; TN={'SCALAR':1,'VEC3':3}
    def acc(i):
        a=j['accessors'][i]; bv=j['bufferViews'][a['bufferView']]; k=TN[a['type']]
        return np.frombuffer(BIN,dtype=CT[a['componentType']],count=a['count']*k,offset=bv.get('byteOffset',0)+a.get('byteOffset',0)).reshape(a['count'],k).astype(float)
    V=[];F=[];o=0
    for m in j['meshes']:
        for p in m['primitives']:
            v=acc(p['attributes']['POSITION']); i=acc(p['indices']).astype(int)[:,0].reshape(-1,3); V.append(v); F.append(i+o); o+=len(v)
    return np.vstack(V),np.vstack(F)
def quat(q):
    x,y,z,w=q; return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def world(p,V):
    R=quat(p['quaternion']); s=np.array(p['scale'],float)
    return (V*s)@R.T+np.array(p['position'])
def tmpl(): return json.load(open('/opt/konfigurator/api/stul_sablona_577.json',encoding='utf-8'))
