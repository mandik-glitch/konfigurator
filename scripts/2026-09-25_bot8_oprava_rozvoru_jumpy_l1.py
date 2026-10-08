"""Oprava rozvoru u L1/Compact variant platformy Jumpy/Expert/Proace/Scudo/Vivaro.

Nalez (bot8, 2026-09-25, pri overovani cifer v nazvech Vandr karet): nase
`karoserie_model_reference` si u TEHOZ vozu protireci. Kratka varianta
(L1/Compact, lozna delka 2160-2162 mm) ma u ctyr radku rozvor 2925 mm a u
sesti radku 3275 mm. 3275 je pritom rozvor DELSI varianty (L2/L3).

DUKAZY, ze spravne je 2925 (vsechny tri nezavisle na sobe):
  1. Nase vlastni tabulka: "Expert Compact (L1) 16-", "Proace Compact 16-",
     "Scudo L1 22-" a "Vivaro L1H1 19-" maji 2925 pri TEZE lozne delce
     (2160-2162). Je to badge-engineering teze karoserie, rozvor se lisit
     nemuze.
  2. vanDrawee katalog (vandrawee.car_models): Jumpy L1 2925, L2 3275,
     L3 3275 - nezavisly zdroj, ktery s nami nesdili data.
  3. Verejna specifikace vozu: Jumpy/Dispatch 2016- ma rozvory
     2925 (XS/SWB), 3275 (M/MWB), 3275 (XL/LWB) - viz
     https://vandimensions.com/database/citroen/jumpy-dispatch-2016
     To zaroven vysvetluje, proc L2 a L3 sdili 3275 (L3 ma delsi previs,
     ne delsi rozvor).

PUVOD CHYBY: hodnoty plnil crawl ciziho webu
(scripts/2026-08-22_crawl_karoserie_dnd.py -> _rebuild_karoserie_reference.py),
ne vyrobce. U sesti radku se zjevne prevzal rozvor delsi varianty.

DOPAD: `wheelbase_mm` se nikde NEPOCITA - cte ho jen api/cars.py (spec do
odpovedi) a webapp/scene.html (radek "Rozvor: N mm" v panelu karoserie).
Zadna geometrie sestav na nem nestoji. Na techto modelech ovsem stoji 48
sestav (14 schvalenych), takze spatne cislo se zakaznikovi i botovi
zobrazovalo jako fakt o voze.

Spusteni NA SERVERU, v /opt/konfigurator:
  api/venv/bin/python scripts/2026-09-25_bot8_oprava_rozvoru_jumpy_l1.py --apply
Bez --apply jen ukaze, co by zmenil.
"""
import json
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
import pymysql
from _env import get_conn

APPLY = "--apply" in sys.argv
SPRAVNY = 2925
CHYBNY = 3275
ZAL_DIR = "/opt/konfigurator/backups/2026-09-25_rozvor_jumpy_l1"
ZAL = os.path.join(ZAL_DIR, "pred_opravou.json")

conn = get_conn()
cur = conn.cursor(pymysql.cursors.DictCursor)

# Cilem jsou VYHRADNE radky kratke varianty (lozna delka 2160-2162), ktere
# nesou rozvor delsi varianty. Lozna delka je ten rozlisovac, ktery se
# NEMUZE zamenit - proto se filtruje podle ni, ne podle nazvu.
cur.execute(
    "SELECT real_name, wheelbase_mm, cargo_length_mm, car_models_id "
    "FROM karoserie_model_reference "
    "WHERE cargo_length_mm BETWEEN 2150 AND 2175 AND wheelbase_mm=%s "
    "ORDER BY real_name", (CHYBNY,))
cile = cur.fetchall()

cur.execute(
    "SELECT real_name, wheelbase_mm, cargo_length_mm FROM karoserie_model_reference "
    "WHERE cargo_length_mm BETWEEN 2150 AND 2175 AND wheelbase_mm=%s "
    "ORDER BY real_name", (SPRAVNY,))
vzory = cur.fetchall()

print(f"Referencni radky TEHOZ vozu, ktere uz maji spravny rozvor {SPRAVNY}: {len(vzory)}")
for v in vzory:
    print(f"   {v['wheelbase_mm']}  cargo={v['cargo_length_mm']}  {v['real_name']}")

print(f"\nK OPRAVE ({CHYBNY} -> {SPRAVNY}): {len(cile)} radku")
for r in cile:
    print(f"   cargo={r['cargo_length_mm']}  {r['real_name']}")

if not cile:
    print("\nNic k oprave - uz je opraveno.")
    sys.exit(0)
if not vzory:
    raise SystemExit("CHYBA: neexistuje ani jeden referencni radek s 2925 - "
                     "predpoklad neplati, NIC NEMENIM")

# Dopad, at je videt v logu behu
ids = [r["car_models_id"] for r in cile if r["car_models_id"]]
if ids:
    q = ",".join(["%s"] * len(ids))
    cur.execute(f"SELECT COUNT(*) n, SUM(technicky_ok=1) ok "
                f"FROM product_assemblies WHERE car_model_id IN ({q})", ids)
    d = cur.fetchone()
    print(f"\nNa techto modelech stoji {d['n']} sestav, z toho {d['ok']} schvalenych "
          f"(wheelbase_mm se ale nikde nepocita, jen zobrazuje).")

if not APPLY:
    print("\n(dry-run, nic nezmeneno - spust s --apply)")
    sys.exit(0)

os.makedirs(ZAL_DIR, exist_ok=True)
with open(ZAL, "w", encoding="utf-8") as f:
    json.dump(cile, f, ensure_ascii=False, indent=1, default=str)
print(f"\nzaloha: {ZAL} ({len(cile)} radku)")

w = conn.cursor()
w.execute(
    "UPDATE karoserie_model_reference SET wheelbase_mm=%s "
    "WHERE cargo_length_mm BETWEEN 2150 AND 2175 AND wheelbase_mm=%s",
    (SPRAVNY, CHYBNY))
print("zmeneno radku:", w.rowcount)
if w.rowcount != len(cile):
    conn.rollback()
    raise SystemExit(f"CHYBA: rowcount {w.rowcount} != ocekavanych {len(cile)} - ROLLBACK")
conn.commit()

# Overeni z NOVEHO spojeni, ne podle chybejici vyjimky.
c2 = get_conn()
cur2 = c2.cursor(pymysql.cursors.DictCursor)
cur2.execute(
    "SELECT real_name, wheelbase_mm FROM karoserie_model_reference "
    "WHERE cargo_length_mm BETWEEN 2150 AND 2175 ORDER BY wheelbase_mm, real_name")
print("\novereno z noveho spojeni - vsechny radky teto lozne delky:")
zbyva = 0
for r in cur2.fetchall():
    if r["wheelbase_mm"] == CHYBNY:
        zbyva += 1
    print(f"   {r['wheelbase_mm']}  {r['real_name']}")
if zbyva:
    raise SystemExit(f"CHYBA: {zbyva} radku stale ma {CHYBNY}")
print("\nOK")
