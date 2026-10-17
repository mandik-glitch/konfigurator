#!/usr/bin/env python3
"""Mřížka v rovině (mm) promítnutá kamerou z kamera_cNN.json přes fotografii (jen scratchpad) – pro odečítání rozměrů.
Použití: mriz.py SKU cNN rovina hodnota a0 a1 z0 z1 krok vystup.png [x0 y0 x1 y1 zoom] [--kam soubor.json]
 rovina: x (plocha X=hodnota; vodorovně Y), y (plocha Y=hodnota; vodorovně X), z (vodorovná rovina z'=hodnota; a = rozsah X, z0..z1 = rozsah Y); jinak z je výška od země z' (0..V).
 Příklad: mriz.py 4932471723 c01 y 205.5 -124.5 124.5 0 330 20 mriz.png"""
import sys, json, math
import numpy as np
from PIL import Image, ImageDraw
SCR='/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad'
KC='/home/user/konfigurator/kufriky_cloud/kontrola_john_v6'
V={'4932471723':330,'4932471724':251,'4932480623':381}
def proj(cam, X, W=1200, H=1200):
    a,e=math.radians(cam['azim']),math.radians(cam['elev'])
    d=cam['dist']; pos=d*np.array([math.cos(e)*math.cos(a),math.cos(e)*math.sin(a),math.sin(e)])
    f=-pos/np.linalg.norm(pos); up=np.array([0,0,1.0]); r=np.cross(f,up); r/=np.linalg.norm(r); u=np.cross(r,f)
    ro=math.radians(cam.get('roll',0)); r2=r*math.cos(ro)+u*math.sin(ro); u2=-r*math.sin(ro)+u*math.cos(ro)
    D=np.asarray(X,float)-pos; xc,yc,zc=D@r2,D@u2,D@f
    fp=(H/2)/math.tan(math.radians(cam['fov'])/2)
    return (W/2+cam.get('shiftX',0)*W+fp*xc/zc, H/2+cam.get('shiftY',0)*H-fp*yc/zc)
if __name__=='__main__':
    args=sys.argv[1:]; kam=None
    if '--kam' in args: i=args.index('--kam'); kam=args[i+1]; del args[i:i+2]
    sku,c,pl,val,a0,a1,z0,z1,step,out=args[:10]; crop=list(map(float,args[10:14])) if len(args)>14 else None; zoom=float(args[14]) if len(args)>14 else 1
    cam=json.load(open(kam or f'{KC}/{sku}/kamera_{c}.json'))['kamera']; val,a0,a1,z0,z1,step=map(float,(val,a0,a1,z0,z1,step))
    im=Image.open(f'{SCR}/kufry3/{sku}/{c}.jpg').convert('RGB'); dr=ImageDraw.Draw(im); h=V[sku]/2
    def P(a,z):
        if pl=='z': X=(a,z,val-h)          # vodorovná rovina z'=val: a = X, z = Y
        else: X=(val,a,z-h) if pl=='x' else (a,val,z-h)
        return proj(cam,X)
    aa=np.arange(a0,a1+1e-6,step); zz=np.arange(z0,z1+1e-6,step)
    for z in zz:
        col=(255,0,255) if int(round(z))%100==0 else (0,170,255)
        dr.line([P(a0,z),P(a1,z)],fill=col,width=1); dr.text(P(a0,z),str(int(z)),fill=(255,255,0))
    for a in aa:
        col=(255,0,255) if int(round(a))%100==0 else (0,255,120)
        dr.line([P(a,z0),P(a,z1)],fill=col,width=1); dr.text(P(a,z1),str(int(a)),fill=(255,255,0))
    if crop: im=im.crop(tuple(map(int,crop))); im=im.resize((int(im.width*zoom),int(im.height*zoom)),Image.LANCZOS)
    im.save(out); print(out,im.size)
