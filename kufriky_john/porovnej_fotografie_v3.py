"""Soukromá porovnání fotografií a modelů; cizí fotografie nezveřejňuje."""
import json
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent
reviews=json.loads((ROOT/'zdroje/doladeni-v3/review.json').read_text())['records']
OUT=ROOT/'zdroje/doladeni-v3/porovnani-soukrome'
OUT.mkdir(exist_ok=True)
sheet=Image.new('RGB',(1600,5*270),'white');draw=ImageDraw.Draw(sheet)
for i,review in enumerate(reviews):
    sku=review['sku'][0]
    source=Image.open(ROOT/review['private_reference_file']).convert('RGB')
    model=Image.open(ROOT/'nahled-modely-v3/porovnani'/(sku+'.png')).convert('RGB')
    pair=Image.new('RGB',(1200,600),'white');label=ImageDraw.Draw(pair)
    for j,im in enumerate((source,model)):
        im.thumbnail((595,550));pair.paste(im,(j*600+(600-im.width)//2,(550-im.height)//2))
        label.text((j*600+20,562),'Fotografie vyrobce' if j==0 else 'Vlastni model v3',fill='black')
    label.text((20,584),sku+' - perspektiva priblizena, nejde o rozmerovy vykres',fill='black')
    pair.save(OUT/(sku+'.jpg'))
    im=Image.open(ROOT/'nahled-modely-v3/porovnani'/(sku+'.png'));im.thumbnail((396,225))
    x,y=i%4*400,i//4*270;sheet.paste(im,(x+(400-im.width)//2,y));draw.text((x+8,y+235),sku,fill='black')
sheet.save(ROOT/'overeni-tvar-v3/v3-prehled.jpg')
print('20 soukromých porovnání fotografie–model; veřejná stránka má pouze vlastní rendery.')
