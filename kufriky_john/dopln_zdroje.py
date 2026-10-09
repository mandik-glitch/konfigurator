"""Průzkum veřejných stránek GET; žádné účty, formuláře ani testy sítě."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
from cti_verejne import get

ROOT = Path(__file__).resolve().parent

def features(path):
    d = json.loads(path.read_text())
    _, tree = get(d['source_url'])
    texts = [' '.join(n.text().split()) for n in tree.walk()
             if n.tag == 'li' and 'ProductFeaturesTextstyles__Feature-' in n.attrs.get('class', '')]
    d['feature_texts'] = texts
    path.write_text(json.dumps(d, ensure_ascii=False, indent=2))
    return path.name, len(texts)

def supplemental(sku, url):
    r, tree = get(url)
    snippets = []
    for n in tree.walk():
        t = ' '.join(n.text().split())
        if n.tag in ('tr', 'li', 'h1') and len(t) < 300 and re.search(
                r'Länge|Breite|Höhe|Length|Width|Height|493249', t):
            snippets.append(t)
    d = {'sku': sku, 'url': r.url, 'excerpts': snippets}
    (ROOT/'zdroje'/f'rozmery-doplnkove-{sku}.json').write_text(json.dumps(d, ensure_ascii=False, indent=2))
    return sku, snippets

if __name__ == '__main__':
    paths = sorted((ROOT/'zdroje').glob('packout-*-cz.json'))
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(features, paths): print(result)
    print(supplemental('4932499704', 'https://www.muellershop.ch/?artId=101138385&groupId=100040772&markid=MI4932499704&pg=det&srv=marken'))
    print(supplemental('4932492962', 'https://www.klium.be/en/milwaukee-4932492962-packout-first-aid-first-aid-kit-xl-104213'))
