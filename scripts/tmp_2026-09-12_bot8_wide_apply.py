"""Aplikace overenych transformu (shape_geometry_methods.id=11) na 37 nechranenych
sestav (11 modelu z 13 pridelenych - K-118 uz hotovo drivejsi soubeznou session,
K-282 preskoceno - viz report_K_282.json, vyrezova noha bez sloupku by se zvedla
nad podlahu). Kazde id ma svuj transformovany `parts` v newparts_<id>.json
(scratchpad), tenhle skript dopocita/zapise cely `data` (jen `parts` klic se meni,
zbytek data beze zmeny) primo UPDATEm na miste (zadne z 37 id neni na chranenem
seznamu - overeno explicitne nize) + zaloha puvodniho radku pred zapisem.
"""
import json
import sys
sys.path.insert(0, '/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad')
from dbenv import env
import pymysql

PROTECTED = {79,82,83,116,117,134,135,151,152,173,182,189,209,219,224,250,251,279,289,294,320,321,332,333,334,335,336,337}

IDS = [95,137,138,159,160, 111,153,154,175,176, 92,193,263, 124,196,266,
       69,233,303, 68,237,307, 183,221,291, 102,260,330, 133,258,328,
       115,212,282, 78,227,297]

SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad"
BACKUP_DIR = "/opt/konfigurator/backups/2026-09-12_kolizni_rezerva_wide_bot8"

assert not (set(IDS) & PROTECTED), f"KOLIZE s chranenym seznamem: {set(IDS) & PROTECTED}"

conn = pymysql.connect(host=env['DB_HOST'], port=int(env.get('DB_PORT', 3306)), user=env['DB_USER'],
                        password=env['DB_PASSWORD'], database=env['DB_NAME'], charset='utf8mb4')
cur = conn.cursor(pymysql.cursors.DictCursor)

results = []
for aid in IDS:
    npf = f"{SCRATCH}/newparts_{aid}.json"
    with open(npf) as f:
        new_parts = json.load(f)

    cur.execute("SELECT id, data, prepazka_rezerva_mm, podbeh_rezerva_mm FROM product_assemblies WHERE id=%s", (aid,))
    row = cur.fetchone()
    assert row, f"id={aid} nenalezeno v DB"
    data = json.loads(row['data'])
    old_nparts = len(data.get('parts', []))
    assert old_nparts == len(new_parts), f"id={aid}: pocet dilu nesedi ({old_nparts} vs {len(new_parts)})"

    # zaloha PRED zapisem
    with open(f"{BACKUP_DIR}/{aid}_before.json", "w") as f:
        f.write(row['data'])

    data['parts'] = new_parts
    new_data_json = json.dumps(data, ensure_ascii=False)

    cur.execute(
        "UPDATE product_assemblies SET data=%s, prepazka_rezerva_mm=10, podbeh_rezerva_mm=30 WHERE id=%s",
        (new_data_json, aid)
    )
    results.append((aid, old_nparts))
    print(f"id={aid}: UPDATE OK ({old_nparts} dilu, prepazka 2->10, podbeh 20->30)")

conn.commit()
print(f"\nCOMMIT hotovo, {len(results)} radku aktualizovano.")

# over po zapisu
cur.execute("SELECT id, prepazka_rezerva_mm, podbeh_rezerva_mm, JSON_LENGTH(data,'$.parts') as nparts FROM product_assemblies WHERE id IN (%s)" % ",".join(str(i) for i in IDS))
bad = 0
for r in cur.fetchall():
    if r['prepazka_rezerva_mm'] != 10 or r['podbeh_rezerva_mm'] != 30:
        bad += 1
        print("PROBLEM po zapisu:", r)
print(f"Overeni po zapisu: {'VSE OK' if not bad else f'{bad} PROBLEMU'}")
conn.close()
