"""Autorizované čtení veřejných stránek. Není test; pouze GET bez účtů.

Ukládá jen specifikace z Product JSON-LD a veřejné odkazy na soubory.
Neukládá HTML, skripty stránky, cookies ani hlavičky odpovědi.
"""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import json
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'zdroje' / 'cad_etapa2'
FORMATS = ('.step', '.stp', '.iges', '.igs', '.stl', '.obj', '.glb', '.gltf', '.fbx', '.3dm', '.sldprt', '.zip', '.pdf', '.dxf')

class PublicLinks(HTMLParser):
    def __init__(self, url):
        super().__init__()
        self.url, self.links, self.products = url, [], []
        self.in_product_json, self.parts = False, []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == 'script' and d.get('type') == 'application/ld+json':
            self.in_product_json, self.parts = True, []
        if tag == 'a':
            u = urljoin(self.url, d.get('href', ''))
            if urlsplit(u).path.lower().endswith(FORMATS):
                # Případné dočasné parametry odkazu se neukládají.
                s = urlsplit(u)
                self.links.append(s._replace(query='', fragment='').geturl())
    def handle_data(self, text):
        if self.in_product_json:
            self.parts.append(text)
    def handle_endtag(self, tag):
        if tag != 'script' or not self.in_product_json:
            return
        self.in_product_json = False
        d = json.loads(''.join(self.parts))
        if isinstance(d, dict) and d.get('@type') in ('Product', 'ProductGroup'):
            for p in d.get('hasVariant', [d]):
                self.products.append({k:p[k] for k in ('sku', 'name', 'additionalProperty') if k in p})

def read(url):
    r = requests.get(url, timeout=30)
    result = {'source_url':url, 'status':r.status_code, 'checked_on':'2026-10-05'}
    if r.status_code == 200:
        parser = PublicLinks(url)
        parser.feed(r.text)
        result.update(products=parser.products, file_links=sorted(set(parser.links)))
    else:
        result['note'] = 'Přístup odmítnut nebo chyba. Žádné obcházení ani přihlášení.'
    return result

def main():
    catalog = json.loads((ROOT/'kufriky.json').read_text())
    urls = sorted({r['outer']['source_url'] for r in catalog['records'] if r['group']=='kufriky' and r['outer']['basis']=='vyrobce'})
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(read, urls))
    (OUT/'vyrobce.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n')
    for result in results:
        print(result['status'], result['source_url'], 'varianty:',len(result.get('products',[])), 'CAD:',len([u for u in result.get('file_links',[]) if not u.endswith('.pdf')]))

if __name__ == '__main__':
    main()
