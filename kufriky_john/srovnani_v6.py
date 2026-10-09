"""Build public source-link/model pairs and PRIVATE photo/model proof sheets."""
from pathlib import Path
import json,html
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
SITE=ROOT/'nahled-modely-v6'
PRIVATE=ROOT/'zdroje/doladeni-v6/porovnani-soukrome'
PRIVATE.mkdir(exist_ok=True)
cat=json.loads((ROOT/'kufriky.json').read_text())
pairs=json.loads((ROOT/'zdroje/doladeni-v6/srovnani.json').read_text())
try:font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
except OSError:font=ImageFont.load_default()
def normalize(im,limit):
 im=im.convert('RGB')
 # Crop white/background margins, independent scale per image. This is for
 # shape comparisons, NOT a claim of sub-2 mm metrology.
 import numpy as np
 a=np.asarray(im);mask=(a.max(2)-a.min(2)>15)|(a.mean(2)<195)
 yy,xx=np.where(mask)
 if len(xx):im=im.crop((max(0,xx.min()-12),max(0,yy.min()-12),min(im.width,xx.max()+13),min(im.height,yy.max()+13)))
 im.thumbnail(limit);return im
def pair_image(sku,pair,file):
 im=Image.new('RGB',(1400,650),'white');d=ImageDraw.Draw(im)
 for j,source in enumerate([ROOT/pair['source_file'] if pair['source_file'] else None,SITE/pair['render_file']]):
  if source:
   x=normalize(Image.open(source),(665,560));im.paste(x,(j*700+(700-x.width)//2,60+(560-x.height)//2))
  else:d.text((30,230),'Fotografie tohoto pohledu chybí',fill='#742b30',font=font)
 d.text((20,12),sku+' · '+pair['label']+' · fotografie',fill='black',font=font)
 d.text((725,12),'Model v6 · stejný směr pohledu',fill='black',font=font)
 d.text((20,625),'Soukromé studium; přesnost jednotlivých detailů do 2 mm neověřena.',fill='black',font=font)
 im.save(file)
for sku,rows in pairs.items():
 for pair in rows:pair_image(sku,pair,PRIVATE/(sku+'-'+pair['view']+'.jpg'))
 overview=Image.new('RGB',(1400,6*650),'white')
 for i,pair in enumerate(rows):overview.paste(Image.open(PRIVATE/(sku+'-'+pair['view']+'.jpg')),(0,i*650))
 overview.save(PRIVATE/(sku+'-prehled.jpg'))

# Public comparison page has only our rendered images and explicit hyperlinks
# to foreign originals; no remote image, embed, iframe or fetch.
e=html.escape
parts=['''<!doctype html><html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; object-src 'none'; form-action 'none'"><meta name="referrer" content="no-referrer"><title>Fotografie a modely organizérů · v6 · John</title><link rel="stylesheet" href="style.css"></head><body><main class="comparison-gallery"><p><a href="index.html">← 3D prohlížeč v6</a></p><h1>Fotografie ↔ model v6</h1><p>Pět organizérů, šest pohledů. Vlevo otevřete originální fotografii u jejího autora, vpravo je náš vlastní render. Originály se zde nestahují ani nevkládají. Chybějící pohled je označený. <strong>Shoda detailů do 2 mm není prokázaná.</strong></p><nav class="comparison-nav">''']
for sku in pairs:parts.append('<a href="#'+sku+'">'+sku+'</a>')
parts.append('</nav>')
for sku,rows in pairs.items():
 r=next(r for r in cat['records'] if sku in r.get('sku',[]))
 parts.append('<section id="'+sku+'"><h2>'+e(r['name'])+' · '+sku+'</h2><p><strong>Co v5 neodpovídalo:</strong> '+e(r['review']['seen'])+'</p><p><strong>Opraveno:</strong> '+e(r['review']['changed'])+'</p><p><a href="index.html#'+sku+'">Otáčet model ve 3D ↗</a> · <a href="srovnani/'+sku+'-prehled.png">Všech šest vlastních renderů na jednom obrázku ↗</a></p>')
 for pair in rows:
  parts.append('<div class="photo-model-pair"><figure><figcaption><strong>'+e(pair['label'])+' · fotografie</strong></figcaption>')
  if pair['photo_url']:parts.append('<a class="photo-external" target="_blank" rel="noopener noreferrer" href="'+e(pair['photo_url'],quote=True)+'">Otevřít původní fotografii ↗</a><p><a target="_blank" rel="noopener noreferrer" href="'+e(pair['photo_page_url'],quote=True)+'">Stránka výrobce / prodejce ↗</a></p>')
  else:parts.append('<p class="photo-external">Fotografie tohoto pohledu daného SKU chybí.<br>Neověřeno.</p>')
  parts.append('<p>'+e(pair['alignment'])+'</p></figure><figure><a href="'+pair['render_file']+'"><img loading="lazy" src="'+pair['render_file']+'" alt="'+e(sku+' model v6 '+pair['label'])+'"></a><figcaption>Náš model v6 · '+e(pair['label'])+'</figcaption></figure></div>')
 parts.append('<p><strong>Neověřeno:</strong> '+e(' '.join(r['review']['unverified']))+'</p></section>')
 # Public overview contains ONLY our renders.
 overview=Image.new('RGB',(1500,3*420),'white');d=ImageDraw.Draw(overview)
 for i,pair in enumerate(rows):
  x=normalize(Image.open(SITE/pair['render_file']),(735,370));col=i%2;row=i//2;overview.paste(x,(col*750+(750-x.width)//2,row*420+30));d.text((col*750+15,row*420+5),sku+' · '+pair['label'],fill='black',font=font)
 overview.save(SITE/'srovnani'/(sku+'-prehled.png'))
parts.append('<p>John · 8. 10. 2026 · v5 zachovaná. Modely čekají na Robertovo posouzení.</p></main></body></html>')
(SITE/'srovnani.html').write_text(''.join(parts))
print('Veřejná srovnávací stránka a pět přímých přehledových obrázků vytvořené; cizí fotografie zůstaly soukromé.')
