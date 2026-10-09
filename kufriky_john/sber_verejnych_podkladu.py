"""Čtení veřejných nabídek; žádné účty, cookies, objednávky ani soukromá API.
Nejde o test. Testy a generátor používají jen uložená data bez sítě.
"""
import concurrent.futures
import html
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
BASE = 'https://www.oknaradie.sk'
CATEGORIES = ['packout--pojazdne-boxy-a-voziky', 'packout--boxy-na-naradie',
              'packout--organizery', 'packout--tasky-na-naradie',
              'packout--chladiace-boxy-a-nadoby-na-napoje', 'packout--montazne-prvky',
              'packout--prilusenstvo']

def read(url):
    s = urllib.request.urlopen(url, timeout=25).read().decode('utf-8')
    return re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', s, flags=re.S)

def plain(s):
    return ' '.join(html.unescape(re.sub('<[^>]+>', ' ', s)).split())

def category(name):
    url = BASE + '/' + name + '/'
    s = read(url)
    links = re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*class="name"[^>]*>(.*?)</a>', s, re.S)
    return [{'url': BASE + link, 'name': plain(title), 'category_url': url} for link, title in links]

def product(record):
    s = read(record['url'])
    code = re.search(r'<span[^>]*class="p-code"[^>]*>', s, re.S)
    sku = re.search(r'\b493\d{7}\b', plain(s[code.end():code.end()+400])) if code else None
    if not sku:
        raise ValueError('Chybí SKU: ' + record['url'])
    record['sku'] = sku.group()
    record['table_rows'] = [plain(x) for x in re.findall(r'<tr\b.*?</tr>', s, re.S)]
    fact = re.findall(r'href="([^"]*fact-tag-generator[^"]+)"', s)
    record['official_datasheet_url'] = html.unescape(fact[0]) if fact else None
    price = re.search(r'<[^>]*class="price-additional"[^>]*>(.*?)</(?:div|span)>', s, re.S)
    record['price_net_text'] = plain(price.group(1)) if price else None
    # Record stock words only; no tracking identifiers, scripts or contact details.
    stock = re.search(r'<[^>]*class="availability-value"[^>]*>(.*?)</span>', s, re.S)
    record['availability_text'] = plain(stock.group(1)) if stock else None
    return record

if __name__ == '__main__':
    candidates = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for rows in pool.map(category, CATEGORIES):
            for row in rows:
                candidates.setdefault(row['url'], row)
    records, failures = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(product, row): row for row in candidates.values()}
        for future, row in futures.items():
            try:
                records.append(future.result())
            except Exception as error:
                failures.append({'url': row['url'], 'error': str(error)})
    records.sort(key=lambda x: x['sku'])
    (ROOT/'zdroje/nabidky_sk.json').write_text(json.dumps({'checked_on': '2026-10-05',
        'records': records, 'failures': failures}, ensure_ascii=False, indent=2) + '\n')
    print('Veřejné nabídky:', len(records), 'nepřečtené:', len(failures))
    for r in records:
        print(r['sku'], r['name'], r['price_net_text'], r['official_datasheet_url'])
