"""Doplneni chybejicich GEOMETRICKYCH poli u 12 sestav (zadani bot5, pravidlo 52).

Bot5 dogeneroval kod_sestavy u 269 z 283 sestav; u 12 chybelo konkretni
geometricke pole, ktere je domena bota8. NIC SE NEHADA - kazda hodnota je
odvozena z dat:

  * `horni_blok_varianta_id` -> ZMERENO nad data.parts. Recept
    shape_geometry_methods #18 (klic kod_0_tvrda_podminka) definuje kod 00
    jako tvrdou podminku na OBSAH: sestava nesmi mit ANI JEDEN dil s roli
    zacinajici na 'podelnik', 'vypln-', 'pricka-horni', 'pricka-police'
    nebo 'pricka-spodni'. Tyhle sestavy zadny takovy dil nemaji -> kod 00.

  * `verze` a `typologie_varianta_id` -> z tabulky `karoserie_verze`, ktera
    je podle PLAN_TVORBY_SESTAV.md ZDROJ PRAVDY pro vazbu verze <-> rozpis
    boxu pro dane auto. Nikdy se neodvozuje regexem z nazvu sestavy.

POZOR na zamenu K-122 a K-123e - jsou to DVE RUZNA VOZIDLA (pripona 'e' =
elektricka verze), obe shodou okolnosti maji typologie_varianta_id=34 pro
verzi A. Skript proto kontroluje karoserii kazde sestavy zvlast.

Spusteni NA SERVERU, v /opt/konfigurator:
  api/venv/bin/python scripts/2026-09-24_bot8_doplnit_geometricka_pole_12.py --apply
Bez --apply jen ukaze, co by zapsal.
"""
import json
import re
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
import pymysql
from _env import get_conn

APPLY = "--apply" in sys.argv

# Role, ktere podle receptu #18 definuji "ma horni blok".
BLOK_RE = re.compile(r"^(podelnik|vypln-|pricka-horni|pricka-police|pricka-spodni)")

# id -> co se ma doplnit. Hodnoty se NEZAPISUJI naslepo: skript kazdou
# znovu overi proti datum a pri neshode nezapise NIC.
PLAN = {
    127: {"typologie_varianta_id": None},          # dopocita se z karoserie_verze
    363: {"horni_blok_varianta_id": None},         # dopocita se z mereni
    364: {"horni_blok_varianta_id": None},
    365: {"horni_blok_varianta_id": None},
    371: {"horni_blok_varianta_id": None},
    372: {"verze": None, "horni_blok_varianta_id": None},
    583: {"verze": None},
    585: {"verze": None},
    588: {"verze": None},
    595: {"verze": None},
    634: {"verze": None},
    670: {"verze": None},
}

conn = get_conn()
cur = conn.cursor(pymysql.cursors.DictCursor)

cur.execute("SELECT id, kod FROM horni_blok_varianty WHERE kod='00'")
row = cur.fetchone()
if not row:
    raise SystemExit("CHYBA: v ciselniku horni_blok_varianty neni kod '00' - nic nezapisuji")
HB_BEZ = row["id"]
print(f"kod 00 (bez horniho bloku) = horni_blok_varianty.id={HB_BEZ}")

ids = tuple(PLAN)
q = ",".join(["%s"] * len(ids))
cur.execute(
    f"SELECT pa.id, pa.name, pa.verze, pa.typologie_varianta_id, pa.horni_blok_varianta_id, "
    f"pa.technicky_ok, pa.data, cm.name AS model "
    f"FROM product_assemblies pa LEFT JOIN car_models cm ON cm.id=pa.car_model_id "
    f"WHERE pa.id IN ({q}) ORDER BY pa.id", ids)
rows = cur.fetchall()
if len(rows) != len(ids):
    raise SystemExit(f"CHYBA: nalezeno {len(rows)} z {len(ids)} sestav - nic nezapisuji")

cur.execute("SELECT karoserie_kod, verze, typologie_varianta_id FROM karoserie_verze")
kv = cur.fetchall()
# (karoserie, typvar) -> verze   a   (karoserie, verze) -> typvar
podle_typvar = {}
podle_verze = {}
for r in kv:
    podle_typvar.setdefault((r["karoserie_kod"], r["typologie_varianta_id"]), set()).add(r["verze"])
    podle_verze[(r["karoserie_kod"], r["verze"])] = r["typologie_varianta_id"]

zapisy = []
for r in rows:
    kod_m = re.search(r"\[(K-\d+e?)\]", str(r["model"] or "")) or re.search(r"(K-\d+e?)", str(r["name"] or ""))
    if not kod_m:
        raise SystemExit(f"CHYBA #{r['id']}: nelze urcit kod karoserie - nic nezapisuji")
    karoserie = kod_m.group(1)

    try:
        parts = (json.loads(r["data"]) or {}).get("parts") or []
    except (TypeError, ValueError):
        raise SystemExit(f"CHYBA #{r['id']}: data nejsou platny JSON - nic nezapisuji")

    zmeny = {}
    for pole in PLAN[r["id"]]:
        if r[pole] is not None:
            print(f"   #{r['id']} {pole} uz je vyplnene ({r[pole]}) - preskakuji")
            continue

        if pole == "horni_blok_varianta_id":
            blokove = [p.get("role") for p in parts if BLOK_RE.match(str(p.get("role") or ""))]
            if blokove:
                raise SystemExit(
                    f"CHYBA #{r['id']}: MA dily horniho bloku ({len(blokove)}x, napr. "
                    f"{blokove[0]}) - kod 00 by byl NEPRAVDA, nic nezapisuji")
            zmeny[pole] = HB_BEZ

        elif pole == "verze":
            verze = podle_typvar.get((karoserie, r["typologie_varianta_id"]))
            if not verze or len(verze) != 1:
                raise SystemExit(
                    f"CHYBA #{r['id']}: karoserie_verze nedava JEDNOZNACNOU verzi pro "
                    f"{karoserie} + typvar {r['typologie_varianta_id']} (nalezeno {verze}) - nic nezapisuji")
            zmeny[pole] = next(iter(verze))

        elif pole == "typologie_varianta_id":
            tv = podle_verze.get((karoserie, r["verze"]))
            if tv is None:
                raise SystemExit(
                    f"CHYBA #{r['id']}: karoserie_verze nezna {karoserie} + verze {r['verze']} "
                    f"- nic nezapisuji")
            zmeny[pole] = tv

    if zmeny:
        zapisy.append((r["id"], karoserie, zmeny, str(r["name"])[:46]))

print(f"\nK zapisu: {len(zapisy)} sestav")
for i, kar, z, nm in zapisy:
    print(f"   #{i:<4} {kar:<7} {z}   {nm}")

if not APPLY:
    print("\n(dry-run, nic nezapsano - spust s --apply)")
    sys.exit(0)

w = conn.cursor()
for i, kar, z, nm in zapisy:
    sety = ", ".join(f"{k}=%s" for k in z)
    w.execute(f"UPDATE product_assemblies SET {sety} WHERE id=%s", (*z.values(), i))
    if w.rowcount != 1:
        conn.rollback()
        raise SystemExit(f"CHYBA #{i}: rowcount={w.rowcount} - ROLLBACK, nic nezapsano")
conn.commit()
print(f"\nzapsano: {len(zapisy)} sestav")

# Overeni z NOVEHO spojeni, ne podle chybejici vyjimky.
c2 = get_conn()
cur2 = c2.cursor(pymysql.cursors.DictCursor)
cur2.execute(
    f"SELECT id, verze, typologie_varianta_id, horni_blok_varianta_id "
    f"FROM product_assemblies WHERE id IN ({q}) ORDER BY id", ids)
print("overeno z noveho spojeni:")
chybi = 0
for r in cur2.fetchall():
    stale_prazdne = [k for k in PLAN[r["id"]] if r[k] is None]
    if stale_prazdne:
        chybi += 1
    print(f"   #{r['id']:<4} verze={r['verze']} typvar={r['typologie_varianta_id']} "
          f"hb={r['horni_blok_varianta_id']}" + (f"   STALE CHYBI: {stale_prazdne}" if stale_prazdne else ""))
if chybi:
    raise SystemExit(f"CHYBA: u {chybi} sestav pole stale chybi")
print("OK - vsech 12 ma doplneno")
