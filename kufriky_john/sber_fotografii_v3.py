"""Čtení veřejných galerií výrobce; bez účtů, formulářů a spouštění stránky.

Není test. Fotografie zůstávají výhradně mezi soukromými podklady.
Z veřejného HTML se ukládají pouze URL fotografií a seznam variant.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qs, urlencode
import hashlib
import io
import json
import re
import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'zdroje/doladeni-v3'
OUT.mkdir(exist_ok=True)
CAT = json.loads((OUT / 'pred-kufriky.json').read_text())
RECORDS = [next(r for r in CAT['records'] if r['id'] == i) for i in CAT['model_order']]

def page(url):
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    m = re.search(r'window\.__REDUX_STORE\s*=\s*', r.text)
    if not m:
        raise ValueError('Chybí veřejná galerie')
    d = json.JSONDecoder().raw_decode(r.text[m.end():])[0]['productDetail']
    return {k: d[k] for k in ('assets', 'variants')}

def process(record):
    sku = record['sku'][0]
    folder = OUT / sku
    folder.mkdir(exist_ok=True)
    cache = folder / 'galerie.json'
    if cache.exists():
        d = json.loads(cache.read_text())
    else:
        url = record['image']['page_url']
        initial = page(url)
        variant = next((v for v in initial['variants'] if v['articleNumber'] in record['sku']), None)
        if variant is None:
            raise ValueError('Chybí SKU v galerii ' + sku)
        url = urljoin(url, variant['url'])
        selected = page(url)
        d = {'page_url': url, 'variants': selected['variants'], 'assets': selected['assets']}
        cache.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    rows = []
    seen = set()
    for kind in ('hero', 'feature', 'app', 'appNoPadding'):
        for asset in d['assets'].get(kind, []):
            url = asset['imageUrl']
            split = urlsplit(url)
            key = split.path
            if key in seen or not any(x in key for x in record['sku']):
                continue
            seen.add(key)
            query = parse_qs(split.query)
            clean_query = {k: v[0] for k, v in query.items() if k == 'v'}
            clean_query['width'] = '1200'
            url = urlunsplit((split.scheme, split.netloc, split.path, urlencode(clean_query), ''))
            name = Path(split.path).name
            target = folder / name
            if not target.exists():
                response = requests.get(url, timeout=25)
                response.raise_for_status()
                Image.open(io.BytesIO(response.content)).verify()
                target.write_bytes(response.content)
            im = Image.open(target)
            rows.append({'sku': sku, 'url': url, 'page_url': d['page_url'],
                         'kind': kind, 'file': str(target.relative_to(ROOT)),
                         'image_size_px': list(im.size), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                         'license': 'Autorská fotografie výrobce; jen soukromé studium tvaru, nezveřejňovat kopii.',
                         'view_verified': False})
    if not rows:
        raise ValueError('Žádná fotografie konkrétního SKU ' + sku)
    sheet = Image.new('RGB', (1200, ((len(rows)+3)//4)*285), 'white')
    draw = ImageDraw.Draw(sheet)
    for i, row in enumerate(rows):
        im = Image.open(ROOT / row['file']).convert('RGB'); im.thumbnail((290, 255))
        x, y = i % 4 * 300, i // 4 * 285
        sheet.paste(im, (x+(300-im.width)//2, y))
        draw.text((x+6, y+259), Path(row['file']).name, fill='black')
    sheet.save(folder / 'prehled.jpg')
    print(sku + ': ' + str(len(rows)) + ' fotografií', flush=True)
    return {'id': record['id'], 'sku': record['sku'], 'name': record['name'], 'photos': rows}

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(process, RECORDS))
    manifest = {'checked_on': datetime.now().astimezone().isoformat(timespec='seconds'),
                'method': 'Veřejný GET produktových galerií správné varianty; žádné účty ani formuláře.',
                'public_photos_copied': False, 'records': rows}
    (OUT / 'fotografie.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print('Celkem', sum(len(r['photos']) for r in rows), 'fotografií pro', len(rows), 'typů.')
