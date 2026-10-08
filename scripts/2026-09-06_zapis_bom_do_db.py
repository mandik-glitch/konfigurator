#!/usr/bin/env python3
"""Zapise vypocitany bom/price_summary (scripts/2026-09-06_backfill_bom_price.js)
zpet do product_assemblies.data - MERGE, ne prepis. `parts`/`join_groups`/
`frame_groups` zustavaji presne beze zmeny, meni se jen `bom` a `price_summary`.

Zaloha CELEHO stavu pred zapisem: backups/2026-09-06_bom_backfill/pred_zapisem.json

bot8 2026-09-06.  Rezim: --dry-run | (bez argu = zapise)
"""
import copy
import json
import os
import sys

DRY = "--dry-run" in sys.argv
VYSLEDKY_DIR = "/tmp/backfill_bom_vysledky"
BACKUP = "/opt/konfigurator/backups/2026-09-06_bom_backfill"

sys.path.insert(0, "/opt/konfigurator/api")
os.chdir("/opt/konfigurator/api")
for _l in open(".env"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
import app as A  # noqa: E402

soubory = sorted(f for f in os.listdir(VYSLEDKY_DIR) if f.startswith("assembly_") and f.endswith(".json"))
print(f"Vysledku k zapisu: {len(soubory)}")

conn = A.get_conn()
cur = conn.cursor()

os.makedirs(BACKUP, exist_ok=True)
zaloha = {}
zapsano = 0
chyby = []

for fname in soubory:
    v = json.load(open(os.path.join(VYSLEDKY_DIR, fname), encoding="utf-8"))
    aid = v["id"]
    cur.execute("SELECT name, data FROM product_assemblies WHERE id=%s", (aid,))
    row = cur.fetchone()
    if not row:
        chyby.append(f"id={aid}: sestava uz v DB neexistuje (smazana mezitim?)")
        continue
    try:
        d = json.loads(row["data"])
    except Exception as e:
        chyby.append(f"id={aid}: nelze parsovat existujici data: {e}")
        continue
    # bot9 2026-09-11: PUVODNE `{"name": row["name"], "data": d}` - `d` je
    # python dict, tohle je prirazeni REFERENCE, ne kopie. Nasledujici zapis
    # `d["bom"] = ...` pak mutoval i to, co bylo (zdanlive) v zaloze, takze
    # soubor zapsany AZ PO teto mutaci obsahoval stav PO zapisu, ne pred nim -
    # "zaloha pred zapisem" byla k nerozeznani od zivych dat. Zachyceno pri
    # davce 21 sestav 2026-09-11 diky nezavislemu kontrolnimu dumpu, ne diky
    # tomuto souboru. deepcopy zajisti, ze zaloha je nezavisla na naslednych
    # zmenach `d`.
    zaloha[str(aid)] = {"name": row["name"], "data": copy.deepcopy(d)}
    d["bom"] = v["bom"]
    d["price_summary"] = v["price_summary"]
    if not DRY:
        cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",
                     (json.dumps(d, ensure_ascii=False), aid))
    zapsano += 1

if not DRY:
    conn.commit()
    with open(os.path.join(BACKUP, "pred_zapisem.json"), "w", encoding="utf-8") as f:
        json.dump(zaloha, f, ensure_ascii=False, indent=1)
    print(f"Zaloha (stav PRED zapisem, {len(zaloha)} sestav): {BACKUP}/pred_zapisem.json")

print(f"{'BY SE ZAPSALO' if DRY else 'ZAPSANO'}: {zapsano} sestav")
if chyby:
    print(f"CHYBY ({len(chyby)}):")
    for c in chyby:
        print("  " + c)

if not DRY:
    # over ctenim z NOVEHO spojeni (WORKFLOW.md tokenova disciplina bod 8 -
    # zadna vyjimka pri commit()/execute() neznamena, ze zapis skutecne
    # dopadl - vzdy overit ceerstvym SELECT)
    conn2 = A.get_conn()
    cur2 = conn2.cursor()
    cur2.execute("SELECT COUNT(*) n FROM product_assemblies WHERE data LIKE '%\"total_czk\"%'")
    n = cur2.fetchone()["n"]
    print(f"\nOVERENO ctenim z noveho spojeni: {n}/123 sestav ma vyplnene price_summary.total_czk")
