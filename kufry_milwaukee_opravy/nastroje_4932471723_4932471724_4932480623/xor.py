#!/usr/bin/env python3
"""Rozdíl obrysů: červeně = jen na fotografii, modře = jen v modelu; bíle shoda. xor.py SKU cNN render.png vystup.png [x0 y0 x1 y1 zoom]"""
import sys
import numpy as np
from PIL import Image
S='/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad'
sku,c,rnd,out=sys.argv[1:5]
f=np.asarray(Image.open(f'{S}/kufry3/{sku}/{c}.jpg').convert('L')).astype(int)<236
r=np.asarray(Image.open(rnd).convert('L').resize((1200,1200))).astype(int)<246
img=np.full((1200,1200,3),255,np.uint8); img[f&r]=(200,200,200); img[f&~r]=(230,40,40); img[~f&r]=(40,80,230)
im=Image.fromarray(img)
if len(sys.argv)>9:
    x0,y0,x1,y1=map(int,sys.argv[5:9]); z=float(sys.argv[9]); im=im.crop((x0,y0,x1,y1)); im=im.resize((int(im.width*z),int(im.height*z)),Image.NEAREST)
im.save(out); print(out, 'IoU', (f&r).sum()/(f|r).sum())
