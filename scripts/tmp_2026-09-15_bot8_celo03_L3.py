"""Rozsireni "posuvne celo" (viz shape_geometry_methods id=9 v17) na
Jumpy L3 variantu 03 - Robert 2026-09-15: "zkusime upravit oranzove Jumpy
L3 var 03 zkracenim cel v 1. sloupci na 2/3 delky, podobne jako ve
variantach 04". Rozdil oproti 04: varianta 03 nema police, takze vypln-
celo-0 je JEDEN kus (ne "-a"/"-b" split), a frakce je 2/3 (ne 1/3).
"""
import sys, json, random
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn

IDS = [388, 440, 444, 448, 452, 456]
FRACTION = 2.0 / 3.0

conn = get_conn()
random.seed(2026091503)  # samostatny seed pro tuhle davku (jina nez 04)

report = []
for aid in IDS:
    with conn.cursor() as cur:
        cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (aid,))
        data = json.loads(cur.fetchone()["data"])

    p = next((x for x in data["parts"] if x.get("role") == "vypln-celo-0"), None)
    if not p:
        report.append((aid, "PRESKOCENO - chybi vypln-celo-0", None))
        continue

    orig_width = p["scale"][0] * 1000.0
    orig_center_z = p["position"][2]
    new_width = orig_width * FRACTION
    half_win = orig_width / 2.0
    half_new = new_width / 2.0
    lo = orig_center_z - half_win + half_new
    hi = orig_center_z + half_win - half_new

    new_z = random.uniform(lo, hi)
    p["scale"][0] = new_width / 1000.0
    p["position"][2] = new_z

    with conn.cursor() as cur:
        cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s", (json.dumps(data, ensure_ascii=False), aid))
    report.append((aid, "OK", round(new_z, 1)))

conn.commit()
conn.close()
for r in report:
    print(r)
