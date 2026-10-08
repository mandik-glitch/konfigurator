"""Novy standard varianty 04 horniho bloku (Robert 2026-09-15, po schvaleni
testovaci kopie #472): celo prvniho sloupce (vypln-celo-0-a/b) se zkrati na
1/3 puvodni delky a nahodne posune v ramci puvodniho okna (zbytek beze
zmeny) - "posuvne celo" pro pristup dovnitr/dlouhy material. Aplikuje se
JEN na 21 Jumpy sestav radku 04, ktere jsou dnes NEZARAZENE (category_id
IS NULL) - zpetne (uz zarazene/schvalene, napr. Doblo K-075) se nedela,
presne podle Robertova zadani "zpetne to delat nebudeme".
"""
import sys, json, random
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn

conn = get_conn()
with conn.cursor() as cur:
    cur.execute(
        "SELECT id FROM product_assemblies WHERE name REGEXP '[ABC]-04' "
        "AND category_id IS NULL AND id != 472 ORDER BY id"
    )
    ids = [r["id"] for r in cur.fetchall()]

print(f"cilovych sestav: {len(ids)}")
random.seed(2026091502)  # jeden reprodukovatelny beh pro celou davku

report = []
for aid in ids:
    with conn.cursor() as cur:
        cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (aid,))
        data = json.loads(cur.fetchone()["data"])

    a_part = next((p for p in data["parts"] if p.get("role") == "vypln-celo-0-a"), None)
    b_part = next((p for p in data["parts"] if p.get("role") == "vypln-celo-0-b"), None)
    if not a_part or not b_part:
        report.append((aid, "PRESKOCENO - chybi vypln-celo-0-a/b", None, None))
        continue

    orig_width = a_part["scale"][0] * 1000.0
    orig_center_z = a_part["position"][2]
    new_width = orig_width / 3.0
    half_win = orig_width / 2.0
    half_new = new_width / 2.0
    lo = orig_center_z - half_win + half_new
    hi = orig_center_z + half_win - half_new

    new_za = random.uniform(lo, hi)
    new_zb = random.uniform(lo, hi)
    a_part["scale"][0] = new_width / 1000.0
    a_part["position"][2] = new_za
    b_part["scale"][0] = new_width / 1000.0
    b_part["position"][2] = new_zb

    with conn.cursor() as cur:
        cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s", (json.dumps(data, ensure_ascii=False), aid))
    report.append((aid, "OK", round(new_za, 1), round(new_zb, 1)))

conn.commit()
conn.close()
for r in report:
    print(r)
