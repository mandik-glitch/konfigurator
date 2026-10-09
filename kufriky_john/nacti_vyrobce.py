"""Jednorázové čtení veřejných produktových stránek; nejde o test."""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import requests
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent
SLUGS = [
    'packout-rolling-tool-chest', 'packout-trolley-box', 'packout-flat-trolley',
    'packout-2-wheeled-cart', 'packout-rolling-drawer', 'packout-boxes',
    'packout-drawer-tool-boxes', 'packout-cabinet', 'packout-crate',
    'packout-tool-tray', 'packout-electrician-box', 'packout-plumbing-box',
    'packout-organisers', 'packout-tip-bin-organiser',
    'packout-tote-toolbag', 'packout-backpack', 'packout-duffel-bag',
    'packout-tech-bag', 'packout-pro-tote-toolbag', 'packout-closed-tote-tool-bag',
    'packout-structured-backpack', 'packout-xl-cooler', 'packout-hard-cooler',
    'packout-jobsite-cooler', 'packout-first-aid-kit', 'packout-first-aid-kit-xl',
    'packout-mounting-plates', 'packout-customisable-work-surface',
]

class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.locales = []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == 'img' and d.get('alt', '').lower().startswith('packout'):
            self.images.append({k: d[k] for k in ('alt','src','data-src') if k in d})
        if tag in ('a', 'link'):
            href = d.get('href', '')
            if href.startswith(('https://cz.milwaukeetool.eu/', 'https://sk.milwaukeetool.eu/')):
                self.locales.append(href)

def read(url, slug):
    r = requests.get(url, timeout=35)
    r.raise_for_status()
    groups = []
    for raw in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', r.text, re.S):
        d = json.loads(raw)
        if d.get('@type') in ('ProductGroup', 'Product'):
            groups.append({k:d[k] for k in ('@type','name','url','image','model','sku','hasVariant','additionalProperty') if k in d})
    tags = Tags(); tags.feed(r.text)
    result = {'source_url':r.url,'groups':groups,'images':tags.images,'locales':sorted(set(tags.locales))}
    if groups:
        (ROOT/'zdroje'/f'{slug}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result

def fetch(slug):
    url = f'https://www.milwaukeetool.eu/en-eu/{slug}/{slug}/'
    try:
        result = read(url, slug)
        compact = []
        for g in result['groups']:
            for v in g.get('hasVariant', [g]):
                compact.append({'name':v.get('name'),'sku':v.get('sku'),'properties':v.get('additionalProperty',[])})
        return {'slug':slug,'data':compact,'locales':result['locales']}
    except Exception as e:
        return {'slug':slug,'error':type(e).__name__}

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(fetch, SLUGS))
    (ROOT/'zdroje'/'prehled-vyrobce.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    for row in rows:
        print(row['slug'], row.get('error',''))
        for v in row.get('data',[]):
            props = '; '.join(f"{x['name']}: {x['value']} [{x.get('unitCode','')}]" for x in v['properties'])
            print(' ',v['sku'],v['name'],props)
