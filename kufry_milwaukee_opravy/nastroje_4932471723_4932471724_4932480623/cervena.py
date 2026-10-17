#!/usr/bin/env python3
"""Porovnání červených oblastí (logo, spona, jazýčky) fotografie a renderu v okně: cervena.py SKU cNN render.png x0 y0 x1 y1 → bbox červených pixelů v okně u obou."""
import sys
import numpy as np
from PIL import Image
S='/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad'
sku,c,rnd=sys.argv[1:4]; x0,y0,x1,y1=map(int,sys.argv[4:8])
f=np.asarray(Image.open(f'{S}/kufry3/{sku}/{c}.jpg').convert('RGB')).astype(int); r=np.asarray(Image.open(rnd).convert('RGB').resize((1200,1200))).astype(int)
for n,a in (('foto',f),('model',r)):
    m=(a[:,:,0]-np.maximum(a[:,:,1],a[:,:,2])>55); m[:y0]=0; m[y1:]=0; m[:,:x0]=0; m[:,x1:]=0
    ys,xs=np.nonzero(m)
    print(n, 'bbox x',xs.min(),xs.max(),'y',ys.min(),ys.max(),'n',len(xs)) if len(xs) else print(n,'nic')
