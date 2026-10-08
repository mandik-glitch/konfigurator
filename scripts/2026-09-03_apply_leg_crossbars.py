#!/opt/konfigurator/api/venv/bin/python
"""Zapise do DB chybejici vnitrni pricky vyrezovych noh (bot22, 2026-09-03).

Vstup: JSON navrh vyrobeny a OVERENY skriptem
       scripts/2026-09-03_fix_leg_missing_crossbars.js --out <soubor>
       (format: {"<assembly_id>": {"id":.., "name":.., "add":[ <dil>, ... ]}})

Kazdy dil uz PROSEL trojim overenim na realne GLB geometrii (spoje na vsech
3 osach, self-kolize, kolize s karoserii) - tenhle skript uz nic nepocita,
jen zapisuje.

IDEMPOTENTNI: dil se prida jen tehdy, kdyz v dane noze (shodne Z, tolerance
60mm) role jeste NEEXISTUJE - opakovany beh tedy neprida duplicity.

Bez --apply jen vypise plan (READ-ONLY). S --apply zapisuje, VZDY az po
ulozeni zalohy puvodnich hodnot do backups/.
"""
import argparse
import copy
import json
import os
import sys
from datetime import date

TOL_Z = 60


def load_env():
    with open("/opt/konfigurator/api/.env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("navrh", help="JSON navrh z 2026-09-03_fix_leg_missing_crossbars.js")
    ap.add_argument("--apply", action="store_true", help="skutecne zapsat do DB")
    ap.add_argument("--backup", default="/opt/konfigurator/backups/%s_leg_crossbars_backup.json" % date.today().isoformat())
    a = ap.parse_args()

    navrh = json.load(open(a.navrh))
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
    n_add = n_skip = 0
    for aid in ids:
        r = rows.get(aid)
        if not r:
            print("id=%s NENALEZENO v DB - preskakuji" % aid)
            continue
        data = json.loads(r["data"]) if isinstance(r["data"], (str, bytes)) else (r["data"] or {})
        parts = data.get("parts") or []
        backup[str(aid)] = copy.deepcopy(data)
        added_here = []
        for novy in navrh[str(aid)]["add"]:
            z = novy["position"][2]
            role = novy["role"]
            exists = any(
                (p.get("role") == role and p.get("position") and abs(p["position"][2] - z) <= TOL_Z)
                for p in parts
            )
            if exists:
                n_skip += 1
                continue
            parts.append(novy)
            added_here.append("%s@z=%.0f" % (role, z))
            n_add += 1
        if added_here:
            data["parts"] = parts
            updates.append((aid, json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
            print("id=%-4s %-46s +%d: %s" % (aid, str(r["name"])[:46], len(added_here), ", ".join(added_here)))

    print("\npridano dilu: %d, preskoceno (uz existuji): %d, dotcenych sestav: %d" % (n_add, n_skip, len(updates)))

    if not a.apply:
        print("\n(DRY-RUN - do DB se nezapsalo nic. Pro zapis pridej --apply)")
        conn.close()
        os.chdir(cwd)
        return

    if not updates:
        print("nic k zapsani")
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
