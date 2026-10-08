"""Zapis opravy 30mm mezery (viz 2026-09-21_bot8_oprava_30mm_mezery.js).

UPDATE na STEJNE id (WORKFLOW.md pravidlo 45 - sestava si pri oprave ponechava
sve ID, nikdy delete+insert). Zaloha PRED zapisem, rowcount overen u kazdeho
radku, po zapisu kontrolni SELECT z NOVEHO spojeni.
"""
import sys, json, pymysql
sys.path.insert(0, '/opt/konfigurator/scripts')
from _env import get_conn

APPLY = "--apply" in sys.argv
SRC = sys.argv[1]
ZAL = "backups/2026-09-21_horni_blok_30mm_pred_opravou.json"

op = json.load(open(SRC))
print(f"k zapisu: {len(op)} sestav")

c = get_conn(); cur = c.cursor(pymysql.cursors.DictCursor)
ids = [r["id"] for r in op]
q = ",".join(["%s"] * len(ids))
cur.execute(f"SELECT id,name,data FROM product_assemblies WHERE id IN ({q})", ids)
pred = cur.fetchall()
if len(pred) != len(ids):
    raise SystemExit(f"CHYBA: v DB nalezeno {len(pred)} z {len(ids)} sestav - nic nezapsano")

if APPLY:
    json.dump(pred, open(ZAL, "w"), ensure_ascii=False)
    print(f"zaloha: {ZAL} ({len(pred)} sestav)")

w = c.cursor()
zapsano = 0
for r in op:
    cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (r["id"],))
    d = json.loads(cur.fetchone()["data"])
    puv = len(d["parts"])
    if puv != len(r["parts"]):
        raise SystemExit(f"CHYBA #{r['id']}: pocet dilu se lisi {puv} vs {len(r['parts'])} - nic dalsiho nezapsano")
    d["parts"] = r["parts"]
    # kusovnik/cena prestavaji platit az pri zmene POCTU dilu - ten se nemeni,
    # jde o ciste posunuti, takze price_summary/bom zustavaji platne.
    if not APPLY:
        continue
    w.execute("UPDATE product_assemblies SET data=%s WHERE id=%s", (json.dumps(d, ensure_ascii=False), r["id"]))
    if w.rowcount != 1:
        raise SystemExit(f"CHYBA #{r['id']}: rowcount={w.rowcount} - rollback")
    zapsano += 1

if not APPLY:
    print("(dry-run, nic nezapsano - spust s --apply)")
    sys.exit(0)

c.commit()
print(f"zapsano: {zapsano} sestav")

# kontrola z NOVEHO spojeni
c2 = get_conn(); cur2 = c2.cursor(pymysql.cursors.DictCursor)
cur2.execute(f"SELECT id,data FROM product_assemblies WHERE id IN ({q})", ids)
ok = 0
byId = {r["id"]: r for r in op}
for row in cur2.fetchall():
    d = json.loads(row["data"])
    want = byId[row["id"]]["parts"]
    if len(d["parts"]) == len(want) and json.dumps(d["parts"], sort_keys=True) == json.dumps(want, sort_keys=True):
        ok += 1
print(f"overeno z noveho spojeni: {ok}/{len(ids)} sestav ma presne zapsana data")
