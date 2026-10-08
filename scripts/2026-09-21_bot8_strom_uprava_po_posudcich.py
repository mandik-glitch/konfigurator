"""Uprava stromu podle dvou nezavislych posudku (workflow wf_71407825-eda).
Oba posudky vybraly stejneho viteze (deleni podle predmetu) a oba nezavisle
oznacily TUTEZ slabinu: strom podle dilu nema kam dat postup, ktery neni dil.
Dusledek byl, ze #11 (oprava uz postavenych sestav) skoncil zahrabany pod
euroboxovym regalem a kvuli #10 (razitkovani logem) vznikla pseudo-vetev
"Povrch a produktove rendery", ktera slibuje vic, nez obsahuje.
"""
import sys, pymysql
sys.path.insert(0, '/opt/konfigurator/scripts')
from _env import get_conn

ZMENY = [
    # 1) nova vetev pro to, co se deje s HOTOVOU sestavou (obe posudky)
    ("shape_geometry_methods", 11, "Hotová sestava – kontrola, oprava, render", 10),
    ("shape_geometry_methods", 10, "Hotová sestava – kontrola, oprava, render", 20),
    # 2) "Nohy" zplostit - deleni rozmer/tvar bylo u #1 a #6 hod minci a
    #    plodilo spor, kam #6 patri (obe posudky)
    ("shape_geometry_methods",  2, "Nohy", 10),
    ("shape_geometry_methods",  8, "Nohy", 20),
    ("shape_geometry_methods",  1, "Nohy", 30),
    ("shape_geometry_methods",  6, "Nohy", 40),
    # 3) findability: "uhelnik" je slovo, ktere majitel hleda (posudek 1)
    ("shape_geometry_methods",  7, "Spojky, úhelníky a záslepky", 10),
    ("shape_geometry_methods",  4, "Spojky, úhelníky a záslepky", 20),
]

c = get_conn(); cur = c.cursor(pymysql.cursors.DictCursor); w = c.cursor()
print("PRED:")
cur.execute("SELECT id,name,kategorie FROM shape_geometry_methods WHERE id IN (1,2,4,6,7,8,10,11) ORDER BY id")
for r in cur.fetchall():
    print(f"   #{r['id']:<3} {r['kategorie']}")
for t, i, k, p in ZMENY:
    w.execute(f"UPDATE {t} SET kategorie=%s, poradi=%s WHERE id=%s", (k, p, i))
    if w.rowcount != 1:
        raise SystemExit(f"CHYBA: {t}#{i} rowcount={w.rowcount}")
c.commit()

c2 = get_conn(); cur2 = c2.cursor(pymysql.cursors.DictCursor)
cur2.execute("SELECT COUNT(*) n FROM shape_geometry_methods WHERE kategorie IS NULL OR kategorie=''")
bez = cur2.fetchone()["n"]
cur2.execute("SELECT COUNT(*) n FROM shape_geometry_methods WHERE kategorie LIKE 'Povrch%'")
povrch = cur2.fetchone()["n"]
print(f"\noverena z noveho spojeni: bez zarazeni {bez}, zbytky vetve 'Povrch' {povrch}")
assert bez == 0 and povrch == 0
