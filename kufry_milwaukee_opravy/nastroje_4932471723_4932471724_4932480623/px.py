#!/usr/bin/env python3
"""Výřez fotografie s pixelovou mřížkou v souřadnicích originálu: px.py SKU cNN x0 y0 x1 y1 zoom krok vystup.png"""
import sys
from PIL import Image, ImageDraw
SCR='/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad'
sku,c,x0,y0,x1,y1,z,st,out=sys.argv[1:10]; x0,y0,x1,y1=map(int,(x0,y0,x1,y1)); z=float(z); st=int(st)
im=Image.open(f'{SCR}/kufry3/{sku}/{c}.jpg').convert('RGB').crop((x0,y0,x1,y1)); im=im.resize((int(im.width*z),int(im.height*z)),Image.LANCZOS)
d=ImageDraw.Draw(im)
for x in range((x0//st+1)*st,x1,st):
    X=(x-x0)*z; d.line([(X,0),(X,im.height)],fill=(0,255,255),width=1); d.text((X+2,2),str(x),fill=(255,255,0))
for y in range((y0//st+1)*st,y1,st):
    Y=(y-y0)*z; d.line([(0,Y),(im.width,Y)],fill=(0,255,255),width=1); d.text((2,Y+2),str(y),fill=(255,255,0))
im.save(out); print(out,im.size)
