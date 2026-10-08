#!/opt/konfigurator/api/venv/bin/python
"""Zapise do product_assemblies NAHRAZENE pole data.parts (bot22, 2026-09-03).

Vstup: JSON navrh {"<assembly_id>": {"id":.., "name":.., "parts":[ ... ]}}
vyrobeny a OVERENY nekterym z navrhovych skriptu (napr.
scripts/2026-09-03_fix_leg_height_vs_door.js --out <soubor>).

Tenhle skript uz NIC NEPOCITA a nic neoveruje - jen zapisuje hotovy,
predem overeny vysledek. Ostatni klice `data` (_note, bom, price_summary,
join_groups, frame_groups) zustavaji beze zmeny.

Bez --apply jen vypise plan (READ-ONLY). S --apply zapisuje, VZDY az po
ulozeni zalohy PUVODNIHO `data` do backups/.
"""
import argparse
import copy
import json
import os
import sys
from datetime import date


def load_env():
    with open("/opt/konfigurator/api/.env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("navrh")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup", required=True, help="cesta pro zalohu puvodniho stavu")
    a = ap.parse_args()

    navrh = json.load(open(a.navrh))
    if not navrh:
        print("navrh je prazdny - neni co zapisovat")
        return

    load_env()
    sys.path.insert(0, "/opt/konfigurator/api")
    cwd = os.getcwd()
    os.chdir("/opt/konfigurator/api")
    import app as A  # noqa: E402

    conn = A.get_conn()
    cur = conn.cursor()
    ids = sorted(int(k) for k in navrh)
    cur.execute("SELECT id, name, data FROM product_assemblies WHERE id IN (%s)" % ",".join(str(i) for i in ids))
    rows = {r["id"]: r for r in cur.fetchall()}

    backup, updates = {}, []
    for aid in ids:
        r = rows.get(aid)
        if not r:
            print("id=%s NENALEZENO v DB - preskakuji" % aid)
            continue
        data = json.loads(r["data"]) if isinstance(r["data"], (str, bytes)) else (r["data"] or {})
        backup[str(aid)] = copy.deepcopy(data)
        stare, nove = len(data.get("parts") or []), len(navrh[str(aid)]["parts"])
        data["parts"] = navrh[str(aid)]["parts"]
        updates.append((aid, json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
        print("id=%-4s %-46s dilu %d -> %d" % (aid, str(r["name"])[:46], stare, nove))

    print("\ndotcenych sestav: %d" % len(updates))
    if not a.apply:
        print("(DRY-RUN - do DB se nezapsalo nic. Pro zapis pridej --apply)")
        conn.close()
        os.chdir(cwd)
        return

    with open(a.backup, "w") as f:
        json.dump(backup, f, ensure_ascii=False)
    print("zaloha PRED zapisem -> %s" % a.backup)

    for aid, dj in updates:
        cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s", (dj, aid))
    conn.commit()
    conn.close()
    print("ZAPSANO do DB: %d sestav" % len(updates))
    os.chdir(cwd)


if __name__ == "__main__":
    main()
