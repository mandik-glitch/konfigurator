"""Jednorázové veřejné čtení fotografií výrobce; nejde o test."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from io import BytesIO
import hashlib
import json
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent

def download(record):
    photo=record['image'];path=ROOT/'nahled'/photo['file']
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        r=requests.get(photo['source_url'],timeout=35);r.raise_for_status()
        im=Image.open(BytesIO(r.content));im.verify()
        path.write_bytes(r.content)
    im=Image.open(path)
    return {'sku':record['sku'],'file':photo['file'],'url':photo['source_url'],
            'width':im.width,'height':im.height,'bytes':path.stat().st_size,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

if __name__=='__main__':
    catalogue=json.loads((ROOT/'kufriky.json').read_text())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(download,catalogue['records']))
    (ROOT/'zdroje'/'fotografie-doklady.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print('Staženo lokálních miniatur:',len(results),'celkem bajtů:',sum(r['bytes'] for r in results))
