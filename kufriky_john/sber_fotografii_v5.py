"""Veřejné GET fotografií, bez účtů. Soukromé podklady, nikoli test."""
from pathlib import Path
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import requests, json, re, html, hashlib, io, csv
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'zdroje/doladeni-v5'

def collect():
    pages=json.loads((OUT/'stranky.json').read_text())
    tasks=[]
    for page in pages:
        for url in page.get('image_urls',[]):
            if '/thumbnail/' in url or '/28/' in url: continue
            tasks.append((page['sku'],page['page_url'],url.replace('http:','https:',1)))
    # This precise URL was returned by public image search, not guessed.
    tasks.append(('4932464082',pages[1]['page_url'],
                  'https://www.tim.pl/media/wysiwyg/w360/0001-00018-63769/images/Photo007.jpg'))
    # New dealer galleries of the correct European product variant.
    extra=[('4932471065','https://www.paulimot.de/en-gb/milwaukee-packout-organiser-slim-compact'),
           ('4932464082','https://www.paulimot.de/milwaukee-packout-organiser'),
           ('4932478625','https://www.paulimot.de/milwaukee-packout-organiser-tief'),
           ('4932498323','https://www.stavbaeu.sk/milwaukee-packout-organizer-s-vyklapacimi-boxmi-4932498323-359935')]
    for sku,url in extra:
        try:
            response=requests.get(url,timeout=25);response.raise_for_status()
            t=html.unescape(response.text).replace('\\/','/')
            urls=list(dict.fromkeys(re.findall(r'https?://[^\s\"<>]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"<>]*)?',t,re.I)))
            urls=[u for u in urls if sku in u and '/thumbnail/' not in u]
            tasks.extend((sku,url,u) for u in urls)
            pages.append({'sku':sku,'page_url':url,'status':response.status_code,'image_urls':urls})
        except Exception as e:pages.append({'sku':sku,'page_url':url,'error':str(e)})
    for sku,url in [('4932471065','https://www.stavbaeu.sk/milwaukee-packout-slim-kompaktny-organizer-4932471065-235267')]:
        response=requests.get(url,timeout=25);response.raise_for_status()
        urls=list(dict.fromkeys(re.findall(r'href="([^"]*productsdetail[^"]*-800x800.jpg)"',response.text)))
        tasks.extend((sku,url,urljoin(url,u)) for u in urls)
    # Manufacturer galleries already inspected in v3 are retained as evidence.
    old=json.loads((ROOT/'zdroje/doladeni-v3/fotografie.json').read_text())
    oldrows=[p for r in old['records'] if r['sku'][0] in ['4932471064','4932464082','4932471065','4932478625','4932498323'] for p in r['photos']]
    def download(task):
        sku,page,url=task
        try:
            folder=OUT/sku;folder.mkdir(exist_ok=True)
            name=hashlib.sha256(url.encode()).hexdigest()[:10]+'-'+Path(urlparse(url).path).name
            dest=folder/name
            if not dest.exists():
                r=requests.get(url,timeout=25);r.raise_for_status()
                Image.open(io.BytesIO(r.content)).verify();dest.write_bytes(r.content)
            return {'sku':sku,'url':url,'page_url':page,'file':str(dest.relative_to(ROOT)),
                    'kind':'nová fotografie prodejce','image_size_px':list(Image.open(dest).size),
                    'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'view_verified':False,
                    'license':'Fotografie prodejce; pouze soukromé studium, kopii nezveřejňovat.'}
        except Exception as e:return {'sku':sku,'url':url,'page_url':page,'error':str(e)}
    results=list(ThreadPoolExecutor(max_workers=4).map(download,tasks))
    rows=oldrows+[r for r in results if 'file' in r]
    records=[]
    for sku in ['4932471064','4932464082','4932471065','4932478625','4932498323']:
        (OUT/sku).mkdir(exist_ok=True)
        photos=[p for p in rows if p['sku']==sku]
        sheet=Image.new('RGB',(1200,((len(photos)+3)//4)*250),'white');draw=ImageDraw.Draw(sheet)
        for i,p in enumerate(photos):
            im=Image.open(ROOT/p['file']).convert('RGB');im.thumbnail((290,217))
            x=i%4*300;y=i//4*250;sheet.paste(im,(x+(300-im.width)//2,y+(217-im.height)//2))
            draw.text((x+5,y+220),str(i)+': '+Path(p['file']).name[:37],fill='black')
            p['sheet_index']=i
        sheet.save(OUT/sku/'prehled.jpg')
        records.append({'sku':sku,'photos':photos})
        print(sku,len(photos),'fotografií',flush=True)
    result={'checked_on':datetime.now().astimezone().isoformat(),'method':'Pouze veřejné GET stránek a obrázků, žádné účty a formuláře.',
            'public_photos_copied':False,'new_photos':len(rows)-len(oldrows),'records':records,'errors':[r for r in results if 'error' in r]}
    (OUT/'fotografie.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (OUT/'stranky.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':collect()
