#!/usr/bin/env python3
"""Zpětná projekce pixelu fotografie na rovinu (mm): odpichni.py SKU cNN osa hodnota px py [px py ...] [--kam soubor.json]
 osa: x|y|z (rovina X=hodnota | Y=hodnota | z'=hodnota); vrací zbývající dvě souřadnice. Souřadnice z' = Z_modelu + V/2."""
import sys, json, math
import numpy as np
sys.path.insert(0, __file__.rsplit('/',1)[0])
from mriz import V, KC
def ray(cam, px, py, W=1200, H=1200):
    a,e=math.radians(cam['azim']),math.radians(cam['elev']); d=cam['dist']
    pos=d*np.array([math.cos(e)*math.cos(a),math.cos(e)*math.sin(a),math.sin(e)])
    f=-pos/np.linalg.norm(pos); up=np.array([0,0,1.0]); r=np.cross(f,up); r/=np.linalg.norm(r); u=np.cross(r,f)
    ro=math.radians(cam.get('roll',0)); r2=r*math.cos(ro)+u*math.sin(ro); u2=-r*math.sin(ro)+u*math.cos(ro)
    fp=(H/2)/math.tan(math.radians(cam['fov'])/2)
    xc=(px-W/2-cam.get('shiftX',0)*W)/fp; yc=-(py-H/2-cam.get('shiftY',0)*H)/fp
    dirv=f+xc*r2+yc*u2; return pos, dirv/np.linalg.norm(dirv)
if __name__=='__main__':
    args=sys.argv[1:]; kam=None
    if '--kam' in args: i=args.index('--kam'); kam=args[i+1]; del args[i:i+2]
    sku,c,ax,val=args[:4]; val=float(val); pts=list(map(float,args[4:])); cam=json.load(open(kam or f'{KC}/{sku}/kamera_{c}.json'))['kamera']; h=V[sku]/2
    for i in range(0,len(pts),2):
        pos,dv=ray(cam,pts[i],pts[i+1]); k={'x':0,'y':1,'z':2}[ax]; target=val if ax!='z' else val-h
        t=(target-pos[k])/dv[k]; P=pos+t*dv; print(f'px({pts[i]:.0f},{pts[i+1]:.0f}) -> X={P[0]:.1f} Y={P[1]:.1f} z\'={P[2]+h:.1f}')
