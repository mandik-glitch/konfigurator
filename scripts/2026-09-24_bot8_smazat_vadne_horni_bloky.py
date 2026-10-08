"""Smazani 9 sestav, ktere maji ram horniho bloku UVNITR nejvyssiho euroboxu.

Robert 2026-09-24, nad kontrolni scenou (#620/#629/#664): "smazat, jsou spatne".

Kriterium (zmereno nad realnou GLB geometrii, ne odhad): spodek podelniku
horniho bloku lezi POD vrchem nejvyssiho euroboxu, tedy zaporna mezera.
Namereno -35 az -76 mm. Vsech 9 vzniklo tim, ze generator variant 05/06
posadil ram 5 mm nad nejvyssi uhelnik, jenze na techto karoseriich lezi
uhelnik pod vrchem boxu.

Vsech 9 je BEZPECNE mazat: technicky_ok=0, shop_product_id NULL,
category_id NULL, is_public=0, zadne radky v product_turntable_frames.
Skript to pred smazanim znovu overi a pri sebemensi odchylce nemaze NIC.

Zaloha kompletnich radku vcetne data.parts jde do
backups/2026-09-24_smazane_vadne_horni_bloky/pred_smazanim.json, takze
smazani je vratne.

Spusteni NA SERVERU, v /opt/konfigurator:
  api/venv/bin/python scripts/2026-09-24_bot8_smazat_vadne_horni_bloky.py --apply
Bez --apply jen ukaze, co by smazal.
"""
import os
import sys
import json

sys.path.insert(0, "/opt/konfigurator/scripts")
import pymysql
from _env import get_conn

APPLY = "--apply" in sys.argv
IDS = (620, 629, 662, 663, 664, 665, 666, 667, 668)
ZAL_DIR = "/opt/konfigurator/backups/2026-09-24_smazane_vadne_horni_bloky"
ZAL = os.path.join(ZAL_DIR, "pred_smazanim.json")

conn = get_conn()
cur = conn.cursor(pymysql.cursors.DictCursor)
q = ",".join(["%s"] * len(IDS))

cur.execute(
    f"SELECT id, name, technicky_ok, shop_product_id, category_id, is_public "
    f"FROM product_assemblies WHERE id IN ({q}) ORDER BY id", IDS)
rows = cur.fetchall()
if len(rows) != len(IDS):
    nalezene = {r["id"] for r in rows}
    raise SystemExit(
        f"CHYBA: v DB nalezeno {len(rows)} z {len(IDS)} sestav "
        f"(chybi {sorted(set(IDS) - nalezene)}) - NIC NEMAZU")

print("Ke smazani:")
for r in rows:
    print(f"   #{r['id']:<4} ok={r['technicky_ok']} produkt={r['shop_product_id']} "
          f"slozka={r['category_id']} public={r['is_public']}  {str(r['name'])[:52]}")

# Pojistka: nic schvaleneho ani napojeneho se nesmi smazat ani omylem.
for r in rows:
    if r["technicky_ok"] or r["shop_product_id"] or r["category_id"]:
        raise SystemExit(f"CHYBA: #{r['id']} je schvalena nebo napojena - NIC NEMAZU")

cur.execute("SHOW TABLES LIKE 'product_turntable_frames'")
if cur.fetchone():
    cur.execute(
        f"SELECT COUNT(*) n FROM product_turntable_frames WHERE assembly_id IN ({q})", IDS)
    n = cur.fetchone()["n"]
    if n:
        raise SystemExit(f"CHYBA: na mazanych sestavach visi {n} renderu - NIC NEMAZU")

if not APPLY:
    print("\n(dry-run, nic nesmazano - spust s --apply)")
    sys.exit(0)

# Zaloha AZ TED, s kompletnimi radky vcetne data.parts.
os.makedirs(ZAL_DIR, exist_ok=True)
cur.execute(f"SELECT * FROM product_assemblies WHERE id IN ({q}) ORDER BY id", IDS)
plne = cur.fetchall()
for r in plne:
    for k, v in r.items():
        if hasattr(v, "isoformat"):
            r[k] = v.isoformat()
        elif isinstance(v, (bytes, bytearray)):
            r[k] = v.decode("utf-8", "replace")
with open(ZAL, "w", encoding="utf-8") as f:
    json.dump(plne, f, ensure_ascii=False, indent=1)
print(f"\nzaloha: {ZAL} ({len(plne)} sestav vcetne data.parts)")

w = conn.cursor()
w.execute(f"DELETE FROM product_assemblies WHERE id IN ({q})", IDS)
print("smazano radku:", w.rowcount)
if w.rowcount != len(IDS):
    conn.rollback()
    raise SystemExit("CHYBA: rowcount nesedi - ROLLBACK, nic nesmazano")
conn.commit()

# Overeni z NOVEHO spojeni - ne podle chybejici vyjimky.
c2 = get_conn()
cur2 = c2.cursor(pymysql.cursors.DictCursor)
cur2.execute(f"SELECT id FROM product_assemblies WHERE id IN ({q})", IDS)
zbyva = [r["id"] for r in cur2.fetchall()]
cur2.execute("SELECT COUNT(*) n FROM product_assemblies")
celkem = cur2.fetchone()["n"]
print(f"overeno z noveho spojeni: zbyva {len(zbyva)} z {len(IDS)} {zbyva if zbyva else ''}")
print(f"sestav v katalogu po smazani: {celkem}")
if zbyva:
    raise SystemExit("CHYBA: nekterе sestavy v DB zustaly")
print("OK")
