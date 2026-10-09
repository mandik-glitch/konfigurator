"""Oddělené veřejné čtení GET, bez účtů a formulářů; nejde o čistý test."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'overeni-tvar-v4'
manifest = json.loads((OUT/'nahrani.json').read_text())
base = manifest['url']
snapshot = OUT/'verejne'
snapshot.mkdir(exist_ok=True)


def read(relative):
    response = requests.get(base+relative, timeout=30)
    response.raise_for_status()
    if response.status_code != 200 or not response.url.startswith(base):
        raise ValueError('Neočekávaná odpověď veřejného souboru '+relative)
    checksum = hashlib.sha256(response.content).hexdigest()
    if checksum != manifest['sha256'][relative]:
        raise ValueError('Neshodný veřejný soubor '+relative)
    file = snapshot/relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(response.content)
    return {'file': relative, 'status': response.status_code, 'bytes': len(response.content),
            'sha256': checksum, 'content_type': response.headers.get('Content-Type')}


with ThreadPoolExecutor(max_workers=6) as pool:
    rows = list(pool.map(read, manifest['sha256']))
result = {'status': 'PASS', 'checked_at': datetime.now(ZoneInfo('Europe/Berlin')).isoformat(timespec='seconds'),
          'url': base, 'files_read': len(rows), 'bytes_read': sum(r['bytes'] for r in rows),
          'method': 'Pouze veřejné GET statických souborů, bez účtů a odesílání dat.', 'rows': rows}
(OUT/'verejny-get.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(f"Veřejné čtení PASS: {len(rows)} souborů, všechny HTTP 200 a shodný SHA-256.")
