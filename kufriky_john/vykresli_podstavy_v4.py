"""Půdorysy ze skutečných styčných ploch GLB v mm; standardní SVG, bez sítě."""
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET
import numpy as np
from over_realne_tvary import inspect
from over_podstavy_v4 import hull

ROOT=Path(__file__).resolve().parent
NS='http://www.w3.org/2000/svg'
ET.register_namespace('',NS)
report=json.loads((ROOT/'overeni-tvar-v4/podstavy.json').read_text())
for row in report['rows'][:3]:
    sku=row['sku'];_,parts,_=inspect(ROOT/'modely'/(sku+'.glb'))
    outline=np.array(row['floor']['contact_contour_xy_mm']);lo=outline.min(0);hi=outline.max(0)
    center=(lo+hi)/2;scale=min(630/(hi[0]-lo[0]+50),670/(hi[1]-lo[1]+50))
    svg=ET.Element('{'+NS+'}svg',{'width':'750','height':'900','viewBox':'0 0 750 900','role':'img'})
    ET.SubElement(svg,'{'+NS+'}title').text=sku+' – kontrola podstav v mm'
    def elem(tag,**attrs):return ET.SubElement(svg,'{'+NS+'}'+tag,{k.replace('_','-'):str(v) for k,v in attrs.items()})
    def point(x,y):return 375+(x-center[0])*scale,440-(y-center[1])*scale
    def text(x,y,value,size=14,color='#243746'):
        elem('text',x=x,y=y,font_family='sans-serif',font_size=size,text_anchor='middle',fill=color).text=value
    def polygon(points,color,opacity):
        elem('polygon',points=' '.join(f'{point(x,y)[0]:.3f},{point(x,y)[1]:.3f}' for x,y in points),fill=color,fill_opacity=opacity,stroke=color,stroke_width=1.1)
    elem('rect',x=0,y=0,width=750,height=900,fill='white')
    text(375,32,sku+' · podstavné plošky',23)
    text(375,58,'Skutečné styčné plochy GLB · přesah 0 mm',15)
    for axis in [0,1]:
        for value in range(math.ceil(lo[axis]/50)*50,math.floor(hi[axis]/50)*50+1,50):
            a=point(value,lo[1]) if axis==0 else point(lo[0],value)
            b=point(value,hi[1]) if axis==0 else point(hi[0],value)
            elem('line',x1=a[0],y1=a[1],x2=b[0],y2=b[1],stroke='#dae2e6',stroke_width=.6)
            if axis==0:text(a[0],a[1]+24,str(value),12)
            else:text(a[0]-25,a[1]+4,str(value),12)
    polygon(outline,'#465d70',.08)
    for support in row['rows']:
        part=next(p for p in parts if p['name']==support['part']);z=part['vertices'][:,2].max()
        contour=hull(part['vertices'][np.abs(part['vertices'][:,2]-z)<.001,:2])
        color='#ac243b' if support['kind']=='ground_pad' else '#357c69'
        polygon(contour,color,.15)
        if support['kind']=='ground_pad':
            x,y=point(*support['center_mm'][:2]);elem('path',d=f'M{x-4},{y}h8 M{x},{y-4}v8',stroke=color,stroke_width=1.2)
    text(375,815,'X [mm] · Y [mm]',15)
    text(375,840,'Červeně rohové patky; zeleně spodní spojovací prvky.',13)
    text(375,863,'Přesnost nekótovaných detailů fyzického výrobku není ověřená.',12)
    text(375,883,'Číselná tolerance 0,01 mm · John',12)
    ET.ElementTree(svg).write(ROOT/'nahled-modely-v4/kontrola'/(sku+'-podstava-mm.svg'),encoding='utf-8',xml_declaration=True)
print('Tři půdorysy skutečných styčných ploch v mm vytvořené.')
