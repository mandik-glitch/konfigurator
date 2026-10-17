#!/usr/bin/env python3
"""Překryv: obrys modelu (cyan) + hrany vnitřních dílů (žlutě) přes fotografii, volitelný výřez a zvětšení; vedle sebe foto | model.
Použití: prekryv.py SKU cNN render.png vystup.png [x0 y0 x1 y1 zoom]"""
import sys
import numpy as np
from PIL import Image, ImageFilter, ImageChops
SCR='/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad'
sku,c,rnd,out=sys.argv[1:5]; crop=list(map(int,sys.argv[5:9])) if len(sys.argv)>8 else None; zoom=float(sys.argv[9]) if len(sys.argv)>9 else 1
f=Image.open(f'{SCR}/kufry3/{sku}/{c}.jpg').convert('RGB'); r=Image.open(rnd).convert('RGB').resize(f.size,Image.LANCZOS)
rm=Image.fromarray(((np.asarray(r).astype(int).min(axis=2)<246)*255).astype('uint8'))
edge=ImageChops.subtract(rm.filter(ImageFilter.MaxFilter(3)),rm.filter(ImageFilter.MinFilter(3)))
ov=f.copy(); ov.paste((0,220,255),mask=edge)
# hrany shadingu modelu (vnitřní detaily): gradient jasu
g=np.asarray(r.convert('L')).astype(float); gx=np.abs(np.diff(g,axis=1,prepend=g[:,:1])); gy=np.abs(np.diff(g,axis=0,prepend=g[:1,:])); e2=((gx+gy)>14)&(np.asarray(rm)>0)
ov2=np.asarray(f).copy(); ov2[e2]=(255,230,0); ov2=Image.fromarray(ov2); ov2.paste((0,220,255),mask=edge)
ims=[f,r,ov2]
if crop: ims=[im.crop(tuple(crop)) for im in ims]
if zoom!=1: ims=[im.resize((int(im.width*zoom),int(im.height*zoom)),Image.LANCZOS) for im in ims]
W=sum(i.width for i in ims); H=ims[0].height; cv=Image.new('RGB',(W,H),'white'); x=0
for im in ims: cv.paste(im,(x,0)); x+=im.width
cv.save(out); print(out,cv.size)
