"""
Serazeni fotogalerie realizaci podle tematicke podobnosti objektu na
fotce (v ramci kazde kategorie zvlast) - bot5, 2026-08-10.

Robert: "ješte ty fotky seradit podle podobných objektu na fotce" -
navazuje na predchozi roztrideni do 2 kategorii (2026-08-10_gallery_
sort_vestavby_stolu.py). Fotky v ramci kategorie byly dosud v puvodnim
poradi importu (nahodile prehazene tema od tematu) - tenhle skript
priradi novy sort_order tak, aby podobne objekty (vysuvne boxy,
regaly, suplíky, kufriky, stavebnice Vandrawee, sveraky, ...) byly
pohromade.

Klasifikace: sada (klicova slova v titulku, nazev shluku) kontrolovana
V PORADI (prvni shoda vyhrava) - poradi shluku = poradi zobrazeni.
V ramci shluku se zachovava puvodni relativni poradi (stabilni razeni
podle puvodniho sort_order/id).

Pouziti:
  cd /opt/konfigurator && api/venv/bin/python3 scripts/2026-08-10_gallery_sort_by_theme.py            # dry-run, vypise shluky
  cd /opt/konfigurator && api/venv/bin/python3 scripts/2026-08-10_gallery_sort_by_theme.py --apply    # skutecny zapis sort_order
"""
import json
import sys

import pymysql

from _env import load_env as _load_env

_cfg = _load_env()
DB = dict(
    host=_cfg["DB_HOST"], port=int(_cfg.get("DB_PORT", 3306)), user=_cfg["DB_USER"],
    password=_cfg["DB_PASSWORD"], database=_cfg["DB_NAME"], charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)
BACKUP_PATH = "/opt/konfigurator/backups/gallery_sort_by_theme_backup_20260810.json"

# (nazev shluku, [klicova slova/fragmenty v title.lower() nebo filename.lower()])
# Poradi = poradi zobrazeni. Prvni shoda vyhrava.
CLUSTERS_VESTAVBY = [
    ("Celkove/prehledove vestavby", [
        "vestavby do vw transportera", "vestavby do uzitkovych vozidel",
        "vestavba do dodavky supliky", "vestavba do dodavky", "vestavba pro dodavku",
        "vestavba v dodavce na zakazku", "individualni prestavba v dodavce",
        "vestavba do transportera", "individualni vestavba z profilu",
        "vestavba uzitkova atypicka", "092 vestavba v aute",
        "210 vestavba do auta system na hilty", "technicka vestavba v aute",
        "ulozna vestavba do auta", "3d model vestavby do auta",
        "vizualizace vestavby na klic dodavce", "dvojita podlaha v aute",
        "demo auto vandrawee", "8a57", "ford transit doublefloor",
        "pracovni vestavba na miru",
    ]),
    ("Stavebnice do aut Vandrawee (modularni rada)", [
        "stavebnice do aut vandrawee", "stavebnice ponk do auta vandrawee",
        "stavebnice do transportera", "individualni stavebnice modul v aute",
        "profi system do aut vandrawee", "mini flotila",
    ]),
    ("Regalove systemy", [
        "regalovy system", "regaly police supliky", "regal na kufry",
        "regal v aute na krabice", "regalova zastavba", "regaly do transportera",
        "regal na kanystry", "vysuvne regaly", "regal do fiat ducato",
        "regal v aute", "vysuvne vestavene regaly", "regaly do auta na miru",
        "regal na motokary", "vany s alu lamelovymi okraji",
    ]),
    ("Suplíky a zasuvky", [
        "vysuvy supliky do bocnich dveri", "suplikova vestavba",
        "zasuvky vestavba", "suplik maxi", "suplik 2080",
        "suplik organizer", "supliky vestavba do auta", "supliky organizery",
        "ocelove supliky", "suplik upraveny na miru", "zapadky pro zasuvky",
    ]),
    ("Kufriky a organizery", [
        "kufrik organizer", "system na kufry presne na miru", "kufrik 43",
        "vysuv kufriky", "vysuv kufr makita", "kufrikovy vyssuv",
        "organizery do auta", "organizery pro elektrikare", "drobny material",
    ]),
    ("Vysuvy a podlahove uloziste", [
        "vysuvne boxy do transportera", "vysuv klt", "vysuvy z podlahy",
        "ulozny prostor v podlaze", "prepravky bocni vysuv", "bocni vysuvy z dodavky",
        "vysuv auto vyndavaci prepravky", "podlahovy ulozny system euroboxu",
        "ukladani v podlaze auta", "ukladani do podlahy v aute",
        "dlouhy vysuv do auta", "vysouvaci plosina", "vysuvna police v aute",
        "vysuvne plato", "vysuvne ramy pro prepravky", "police se sklopnymi dvirka",
        "boxy se sklopnym vikem", "otevreny box podbeh", "bedna pres podbeh",
        "paleta v toyote",
    ]),
    ("Pracovni pult/ponk v aute", [
        "ponk v aute", "ponk do auta",
    ]),
    ("Sveraky", [
        "vysuvny sverak", "sverak vysuv", "vysuvneho sveraku", "vysuvny velky sverak",
    ]),
    ("Naradi a elektrocentrala", [
        "vercajk v podlaze", "vysuv pro elektrocentralu", "drzak na tyce a naradi",
        "drzak zebre", "drzak na zebre", "drzak lopat", "napojeni nohou na sebe",
    ]),
    ("Kanystry a lahve", [
        "kanystr", "kotveni mensich lahvi", "drzaky lahvi a zavitovych tyci",
    ]),
    ("Nastupni schudky", [
        "nastupni schudek", "nastupni schod",
    ]),
    ("Specializovane oborove vestavby", [
        "vestavba filmare", "vestavba kameramana", "vestavba filmoveho stabu",
        "expedicni vestavba", "hygienicky set", "mobilni kancelar",
        "spojovaci material v aute", "rychlopopruhy do drazek",
    ]),
    ("Skrine a specialni produkty", [
        "skrine do dodavky na miru", "koma modular",
    ]),
    ("Privesy - dilny a motokary", [
        "pojizdna dilna v privesu", "dilna s luzkem pro motokaru",
        "individualni vestavba do privesu",
    ]),
    ("Privesne/rybarske voziky", [
        "multifunkcni vozik", "privesne rybarske voziky", "privesne voziky",
        "privesny rybarsky vozik", "rybarske voziky", "rybarsky vozik",
        "vozik pro rybare", "vozik s uloznymi prostory", "vozik za auto pro rybare",
        "voziky na miru pro rybare", "voziky pro rybare na miru",
    ]),
]

CLUSTERS_STOLU = [
    ("Balici stoly", [
        "baleni pack stations", "balici stoly ulozny prostor", "balici ergonomicke stoly",
        "balici stoly jirny", "balici nastavitelne stoly", "bublinkova role mezi stoly",
    ]),
    ("SSE stolove systemy", [
        "logiman sse",
    ]),
    ("Elektricke polohovaci stoly", [
        "elektricky nastavitelny stul", "elektricky polohovaci",
    ]),
    ("Ergonomicka pracoviste", [
        "ergonomicke police ke stolum", "esse 2000", "expedicni pracoviste",
        "logiman alu45 balici pracoviste",
    ]),
    ("Tridici stoly", [
        "tridici stoly",
    ]),
    ("Ramy stroju a kryty", [
        "ram stroje", "ramy stroju", "kryt priklad", "rezacka zakazka",
    ]),
]

# "8a57-4d5d..." (generic hash nazev), "img-0893", "pracuju-v-terenu" - bez
# jasneho tematu, zaradi se na konec kategorie (fallback shluk).
FALLBACK_CLUSTER = "Ostatni/nezarazene"


def classify(title, filename, clusters):
    t = (title or "").lower()
    fn = (filename or "").lower().replace("-", " ").replace(".jpg", "").replace(".png", "").replace(".jpeg", "")
    for idx, (name, keywords) in enumerate(clusters):
        for kw in keywords:
            if kw in t or kw in fn:
                return idx, name
    return len(clusters), FALLBACK_CLUSTER


def main():
    apply = "--apply" in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    backup = {}
    all_updates = []

    for category, clusters in (("vestavby_dodavek", CLUSTERS_VESTAVBY), ("realizace_stolu", CLUSTERS_STOLU)):
        cur.execute(
            "SELECT id, filename, title, sort_order FROM shop_gallery_images "
            "WHERE active=1 AND category=%s ORDER BY sort_order, id",
            (category,),
        )
        rows = cur.fetchall()
        backup[category] = [dict(r) for r in rows]

        classified = [(classify(r["title"], r["filename"], clusters), r) for r in rows]
        classified.sort(key=lambda x: (x[0][0], x[1]["sort_order"], x[1]["id"]))

        print(f"\n=== {category} ({len(rows)} polozek) ===")
        current_cluster = None
        new_sort = 1
        for (cluster_idx, cluster_name), r in classified:
            if cluster_name != current_cluster:
                print(f"\n-- {cluster_name} --")
                current_cluster = cluster_name
            print(f"  {new_sort:3d}  {r['filename']:55s} | {r['title']}")
            all_updates.append((r["id"], new_sort))
            new_sort += 1

    if not apply:
        print("\n\nDRY RUN - nic nezapsano. Zkontroluj razeni vyse, pak spust s --apply.")
        cur.close()
        conn.close()
        return

    with open(BACKUP_PATH, "w") as f:
        json.dump(backup, f, default=str, ensure_ascii=False, indent=2)
    print(f"\nZaloha zapsana: {BACKUP_PATH}")

    for img_id, sort_order in all_updates:
        cur.execute("UPDATE shop_gallery_images SET sort_order=%s WHERE id=%s", (sort_order, img_id))
    conn.commit()
    print(f"Aktualizovano poradi u {len(all_updates)} fotek.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
