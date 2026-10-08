"""
Roztrideni fotogalerie realizaci do 2 kategorii (vestavby_dodavek /
realizace_stolu) - bot5, 2026-08-10.

Robert: "umis roztridit fotky galerie do tech 2 dlazdic?" - kontrola
DB odhalila, ze kategorie "realizace_stolu" obsahuje z velke casti
DOSLOVNE duplicitni kopie (stejny filename+title) polozek jiz
spravne zarazenych v "vestavby_dodavek" (pravdepodobne pozustatek
puvodniho hromadneho importu z logiman.cz, kde se stejne fotky
objevovaly na vice starych galeriich webu).

Postup (viz konverzace pro plne odduvodneni kazde kategorie, vizualne
overeno pres Read na nejasnych titulcich pred timto skriptem):

1. DUPLICATE_FILENAMES (58 polozek) - presne stejny filename existuje
   v OBOU kategoriich. Ponechame original ve vestavby_dodavek (spravne
   umisteni, overeno na vzorku), kopii v realizace_stolu jen
   DEAKTIVUJEME (active=0) - soubor na disku zustava beze zmeny,
   jen zmizi z /api/gallery (WHERE active=1).

2. MOVE_TO_VESTAVBY (14 polozek, aktualne v realizace_stolu) - vizualne
   overeno jako:
   - 4x skutecny interier dodavky (kufrik-43-1-vysuv(-b), dvojita-
     podlaha-v-aute, vestavba-filmoveho-stabu)
   - 10x privesne/rybarske voziky - nejsou to stoly ani interier
     dodavky, ale Robert vyslovne chtel "nechat v autech" (=kategorie
     vestavby_dodavek), ne skryvat ani vytvaret 3. kategorii.
   UPDATE category + FYZICKE presunuti souboru na disku (URL obrazku
   obsahuje kategorii jako slozku, viz gallery.py _category_dir), jinak
   by DB rikala "vestavby_dodavek" ale soubor zustal ve slozce
   realizace_stolu a URL by vratila 404.

Zbytek unikatnich polozek v realizace_stolu (balici/tridici/SSE stoly,
ergonomicka pracoviste, ramy stroju, kryt-priklad, rezacka-zakazka,
ponk-v-aute-boxy-jako-supliky) zustava beze zmeny - vizualne/textove
overeno jako spravne zarazene (tabulkove/pracovni vybaveni, zadny
interier vozidla).

Pouziti:
  cd /opt/konfigurator && api/venv/bin/python3 scripts/2026-08-10_gallery_sort_vestavby_stolu.py            # dry-run
  cd /opt/konfigurator && api/venv/bin/python3 scripts/2026-08-10_gallery_sort_vestavby_stolu.py --apply    # skutecny zapis
"""
import json
import os
import shutil
import sys

import pymysql

from _env import load_env as _load_env

_cfg = _load_env()
DB = dict(
    host=_cfg["DB_HOST"], port=int(_cfg.get("DB_PORT", 3306)), user=_cfg["DB_USER"],
    password=_cfg["DB_PASSWORD"], database=_cfg["DB_NAME"], charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)
GALLERY_DIR = "/opt/konfigurator/webapp/content-files/gallery"
BACKUP_PATH = "/opt/konfigurator/backups/gallery_sort_vestavby_stolu_backup_20260810.json"

# Presne stejny filename existuje v obou kategoriich - deaktivovat
# kopii v realizace_stolu (naplneno programove nize kontrolou proti DB,
# tady jen explicitni seznam pro auditovatelnost/reprodukovatelnost).
DUPLICATE_FILENAMES = [
    "vysuvne-boxy-do-transportera-do-aut-1.jpg", "regalovy-system-do-aut-1.jpg",
    "vestavby-do-vw-transportera.jpg", "regaly-police-supliky-do-aut.jpg",
    "regal-na-kufry-s-naradim.jpg", "vany-s-alu-lamelovymi-okraji.jpg",
    "individualni-prestavba-v-dodavce.jpg", "pracovni-vestavba-na-miru.png",
    "regalova-zastavba-v-auto-mrazak.jpg", "vestavby-do-uzitkovych-vozidel.jpg",
    "vysuv-klt-3.jpg", "ulozny-prostor-v-podlaze-auta.jpg",
    "individualni-stavebnice-modul-v-aute.jpg", "stavebnice-ponk-do-auta-vandrawee.jpg",
    "ponk-v-aute-s-boxem-na-rychly-uklid-pracovni-plochy.jpg",
    "stavebnice-do-aut-vandrawee-2020-foto-04.jpg", "organizery-pro-elektrikare.jpg",
    "drzak-na-tyce-a-naradi-do-auta.jpg", "dlouhy-vysuv-do-auta-1200mm.jpg",
    "regaly-do-transportera.jpg", "regal-na-kanystry-do-auta.jpg",
    "suplikova-vestavba-do-auta.jpg", "zasuvky-vestavba-do-auta.jpg",
    "vysuvne-regaly-do-aut.jpg", "030-stavebnice-do-aut-vandrawee-2020-foto-04.jpg",
    "040-stavebnice-do-aut-vandrawee-2020-foto-02.jpg",
    "050-stavebnice-do-aut-vandrawee-2020-foto-03.jpg", "092-vestavba-v-aute.jpg",
    "hygienicky-set-na-zadni-dvere-auta.jpg", "vw-t5-prava-strana-sverak-vysuv.jpg",
    "demo-auto-vandrawee.jpg", "expedicni-vestavba.jpg", "mobilni-kancelar.jpg",
    "regal-do-fiat-ducato-l2h1.jpg", "suplik-2080-927-a.jpg", "suplik-maxi-30-927.jpg",
    "vysuv-kufriky-43-1057.jpg", "vysuv-auto-vyndavaci-prepravky.jpg",
    "vysuvne-vestavene-regaly-do-aut.jpg", "stavebnice-do-aut-vandrawee.jpg",
    "supliky-organizery-do-auta.jpg", "stavebnice-do-aut-vandrawee-2.jpg",
    "stavebnice-do-aut-vandrawee-2020-foto-00.jpg", "012-stavebnice-do-aut-vandrawee.jpg",
    "023-stavebnice-do-aut-vandrawee-2020-foto-01.jpg",
    "033-mini-flotila-8ks-vozidel-vestavby-do-aut.jpg", "vestavba-do-transportera.jpg",
    "stavebnice-do-transportera.jpg", "ponk-do-auta.jpg", "profi-system-do-aut-vandrawee.jpg",
    "ford-transit-doublefloor-01.jpg",
    "otevreny-box-podbeh.png", "drzaky-lahvi-a-zavitovych-tyci.jpg",
    "organizery-do-auta.jpg", "spojovaci-material-v-aute.jpg",
    "system-na-kufry-presne-na-miru.png",
    # Doplneno po dry-run overeni proti DB (chybely v puvodnim rucne
    # prepsanem seznamu, viz konverzace - skript spravne odhalil
    # nesoulad pred zapisem):
    "210-vestavba-do-auta-system-na-hilty.png", "supliky-vestavba-do-auta.jpg",
]

# Vizualne overeno (Read na obrazku) jako skutecny interier vozidla /
# privesny vozik - presun z realizace_stolu do vestavby_dodavek.
MOVE_TO_VESTAVBY = [
    "kufrik-43-1-vysuv.jpg", "kufrik-43-1-vysuv-b.jpg",
    "dvojita-podlaha-v-aute.jpg", "vestavba-filmoveho-stabu.jpg",
    "multifunkcni-vozik-na-miru-za-auto.jpeg",
    "privesne-rybarske-voziky-na-miru.jpg", "privesne-voziky-na-miru.jpeg",
    "privesny-rybarsky-vozik.jpeg", "rybarske-voziky-na-miru.jpg",
    "rybarsky-vozik.jpeg", "vozik-pro-rybare.jpeg",
    "vozik-s-uloznymi-prostory-na-miru.jpg", "vozik-za-auto-pro-rybare.jpeg",
    "voziky-na-miru-pro-rybare.jpg", "voziky-pro-rybare-na-miru.jpg",
]


def main():
    apply = "--apply" in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    cur.execute(
        "SELECT id, category, filename, title, active FROM shop_gallery_images "
        "WHERE category='realizace_stolu' AND filename IN %s",
        (tuple(DUPLICATE_FILENAMES),),
    )
    dup_rows = cur.fetchall()
    cur.execute(
        "SELECT id, category, filename, title, active FROM shop_gallery_images "
        "WHERE category='realizace_stolu' AND filename IN %s",
        (tuple(MOVE_TO_VESTAVBY),),
    )
    move_rows = cur.fetchall()

    found_dup = {r["filename"] for r in dup_rows}
    missing_dup = set(DUPLICATE_FILENAMES) - found_dup
    found_move = {r["filename"] for r in move_rows}
    missing_move = set(MOVE_TO_VESTAVBY) - found_move

    print(f"Duplicitni k deaktivaci: {len(dup_rows)} nalezeno (ocekavano {len(DUPLICATE_FILENAMES)})")
    if missing_dup:
        print("  CHYBI v DB (jiz asi nedeaktivni/smazano?):", missing_dup)
    already_inactive = [r for r in dup_rows if not r["active"]]
    if already_inactive:
        print(f"  Jiz neaktivni ({len(already_inactive)}): {[r['filename'] for r in already_inactive]}")

    print(f"\nK presunu do vestavby_dodavek: {len(move_rows)} nalezeno (ocekavano {len(MOVE_TO_VESTAVBY)})")
    if missing_move:
        print("  CHYBI v DB:", missing_move)

    if not apply:
        print("\nDRY RUN - nic nezapsano ani nepresunuto. Spust s --apply pro skutecne provedeni.")
        cur.close()
        conn.close()
        return

    backup = {
        "duplicate_deactivated": [dict(r, active=bool(r["active"])) for r in dup_rows],
        "moved_to_vestavby": [dict(r, active=bool(r["active"])) for r in move_rows],
    }
    with open(BACKUP_PATH, "w") as f:
        json.dump(backup, f, default=str, ensure_ascii=False, indent=2)
    print(f"\nZaloha zapsana: {BACKUP_PATH}")

    # 1) Deaktivace duplicit (jen DB, soubor na disku netknuty).
    to_deactivate = [r["id"] for r in dup_rows if r["active"]]
    if to_deactivate:
        cur.execute(
            f"UPDATE shop_gallery_images SET active=0 WHERE id IN ({','.join(['%s'] * len(to_deactivate))})",
            to_deactivate,
        )
    print(f"Deaktivovano {len(to_deactivate)} duplicitnich radku.")

    # 2) Presun kategorie + fyzicky presun souboru.
    moved = 0
    for r in move_rows:
        src = os.path.join(GALLERY_DIR, "realizace_stolu", r["filename"])
        dst_dir = os.path.join(GALLERY_DIR, "vestavby_dodavek")
        dst = os.path.join(dst_dir, r["filename"])
        if not os.path.exists(src):
            print(f"  PRESKOCENO (soubor chybi na disku): {src}")
            continue
        os.makedirs(dst_dir, exist_ok=True)
        shutil.move(src, dst)
        os.chown(dst, 33, 33)  # www-data
        cur.execute("UPDATE shop_gallery_images SET category='vestavby_dodavek' WHERE id=%s", (r["id"],))
        moved += 1
    print(f"Presunuto {moved} polozek do vestavby_dodavek (DB + soubor).")

    conn.commit()
    cur.close()
    conn.close()
    print("\nHOTOVO.")


if __name__ == "__main__":
    main()
