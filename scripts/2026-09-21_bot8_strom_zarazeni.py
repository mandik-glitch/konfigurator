"""Prvni zarazeni geometrickych receptu do stromu (Robert 2026-09-21:
"udelej to jako strom, podle vyznamu ty pravidla" + "at se stejne shlukuji
do jedne vetve").

Deleni podle PREDMETU (ceho se pravidlo tyka), ne podle faze prace - prave
proto, ze Robert chce stejnorode veci pohromade. Deleni podle "otazky, kterou
bot resi" bylo take navrzeno, ale rozsypalo by horni blok do tri ruznych
vetvi, coz je presne to, cemu se ma predejit.

Zarazeni je DATA (sloupec `kategorie`) - tenhle skript je jen PRVNI naplneni,
dal se meni tlacitkem "Preradit" v adminu, ne editaci tohohle souboru.
"""
import sys, pymysql
sys.path.insert(0, '/opt/konfigurator/scripts')
from _env import get_conn

APPLY = "--apply" in sys.argv
Z = [
    ("car_body_placement_methods", 2,  "Vozidlo a usazení do něj", 10),
    ("car_body_placement_methods", 1,  "Vozidlo a usazení do něj", 20),

    ("shape_geometry_methods",  2, "Nohy/Rozměry nohy (hloubka a výška)", 10),
    ("shape_geometry_methods",  8, "Nohy/Rozměry nohy (hloubka a výška)", 20),
    ("shape_geometry_methods",  1, "Nohy/Tvar nohy (profil a výřez pro podběh)", 10),
    ("shape_geometry_methods",  6, "Nohy/Tvar nohy (profil a výřez pro podběh)", 20),

    ("shape_geometry_methods",  5, "Regál a euroboxy/Rozvržení noh a sloupců", 10),
    ("shape_geometry_methods",  3, "Regál a euroboxy/Postup stavby na euroboxy", 10),
    ("shape_geometry_methods", 11, "Regál a euroboxy/Přestavba už postavené sestavy", 10),

    ("shape_geometry_methods",  9, "Horní blok/Co se staví – rozcestník a volba", 10),
    ("shape_geometry_methods", 18, "Horní blok/Co se staví – rozcestník a volba", 20),
    ("shape_geometry_methods", 14, "Horní blok/Kde začíná a jak je hluboký", 10),
    ("shape_geometry_methods", 17, "Horní blok/Kde začíná a jak je hluboký", 20),
    ("shape_geometry_methods", 15, "Horní blok/Nosný rám", 10),
    ("shape_geometry_methods", 19, "Horní blok/Nosný rám", 20),
    ("shape_geometry_methods", 16, "Horní blok/Výplně a dvířka", 10),
    ("shape_geometry_methods", 12, "Horní blok/Výplně a dvířka", 20),
    ("shape_geometry_methods", 13, "Horní blok/Ověřené vzory a kontrola", 10),
    ("shape_geometry_methods", 20, "Horní blok/Ověřené vzory a kontrola", 20),

    ("shape_geometry_methods",  7, "Spojovací materiál a záslepky", 10),
    ("shape_geometry_methods",  4, "Spojovací materiál a záslepky", 20),

    ("shape_geometry_methods", 10, "Povrch a produktové rendery", 10),
]

c = get_conn(); cur = c.cursor(pymysql.cursors.DictCursor); w = c.cursor()
# pojistka: zadny recept nesmi zustat nezarazeny omylem
celkem = {}
for t in ("shape_geometry_methods", "car_body_placement_methods"):
    cur.execute(f"SELECT id FROM {t}")
    celkem[t] = {r["id"] for r in cur.fetchall()}
zarazene = {}
for t, i, _, _ in Z:
    zarazene.setdefault(t, set()).add(i)
for t in celkem:
    chybi = celkem[t] - zarazene.get(t, set())
    if chybi:
        raise SystemExit(f"CHYBA: {t} - nezarazene recepty {sorted(chybi)}, nic nezapsano")
    navic = zarazene.get(t, set()) - celkem[t]
    if navic:
        raise SystemExit(f"CHYBA: {t} - zarazuji neexistujici {sorted(navic)}, nic nezapsano")
print(f"kontrola: vsech {sum(len(v) for v in celkem.values())} receptu ma zarazeni")

if not APPLY:
    for t, i, k, p in Z:
        print(f"  {t}#{i:<3} -> {k}")
    print("\n(dry-run, nic nezapsano - spust s --apply)")
    sys.exit(0)

n = 0
for t, i, k, p in Z:
    w.execute(f"UPDATE {t} SET kategorie=%s, poradi=%s WHERE id=%s", (k, p, i))
    if w.rowcount != 1:
        raise SystemExit(f"CHYBA: {t}#{i} rowcount={w.rowcount}")
    n += 1
c.commit()
print(f"zapsano: {n} zarazeni")

c2 = get_conn(); cur2 = c2.cursor(pymysql.cursors.DictCursor)
bez = 0
for t in celkem:
    cur2.execute(f"SELECT COUNT(*) n FROM {t} WHERE kategorie IS NULL OR kategorie=''")
    bez += cur2.fetchone()["n"]
print(f"overeno z noveho spojeni: bez zarazeni zustava {bez} receptu")
