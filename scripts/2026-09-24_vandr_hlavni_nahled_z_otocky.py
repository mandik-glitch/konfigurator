#!/usr/bin/env python3
"""Hlavni nahledovy obrazek Vandr karet = snimek z jejich otocky
(azimut 240 deg, elevace 0 deg), ne kotovany 2D vykres s vodoznakem
vanDrawee (bot5, 2026-09-24, Robert pres bot3, URGENTNI).

Priciny: bot7 vycistil galerii Vandr karet (zustaly jen "s kotami"
obrazky), _category_products_with_images() v api/app.py bere jako
nahled PRVNI content_gallery_items radek (owner_type='product',
is_public=1, ORDER BY sort_order) - bez zasahu tak vyhral kotovany
vykres. Rendery z otocky se do galerie vubec nepropisuji automaticky.

Oprava: zkopiruje aktivni 2048px snimek a240/e00 z product_turntable_frames
do webapp/content-files/gallery-items/ a vlozi ho jako novy
content_gallery_items radek se sort_order NIZSIM nez vsechny stavajici
(vyhraje razeni, kotovane obrazky zustavaji v galerii dal - Robert je
tam chce, jen nemaji byt PRVNI). Idempotentni - pokud uz radek se
stejnym filename existuje, kartu preskoci.

`zajisti_hlavni_nahled_z_otocky(cur, product_id, apply=True)` je sdilena
i s scripts/2026-09-22_vandr_card_activate.py (zavola se hned po aktivaci
karty, aby kazda NOVE aktivovana Vandr karta dostala tenhle nahled sama,
bez cekani na dalsi rucni beh tohohle skriptu).

Spusteni NA SERVERU (/opt/konfigurator), MUSI byt jako www-data (pise do
webapp/content-files/gallery-items/):
    systemd-run --pipe --quiet --uid=www-data --gid=www-data \\
      -p EnvironmentFile=/opt/konfigurator/api/.env --wait \\
      api/venv/bin/python3 scripts/2026-09-24_vandr_hlavni_nahled_z_otocky.py
    (pridej --apply pro skutecny zapis, bez neho jen dry-run - zpetny
    beh pro VSECHNY jiz aktivni Vandr karty, ktere tenhle nahled jeste
    nemaji)
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402
import _nahled_dlazdice as nd  # noqa: E402 - jednotna dlazdice (bot4 2026-09-30), viz jeho hlavicka

CONTENT_FILES_ROOT = "/opt/konfigurator/webapp/content-files"
GALLERY_ITEMS_DIR = os.path.join(CONTENT_FILES_ROOT, "gallery-items")
ELEVATION_DEG = 0
VD_SKU_REGEXP = r"^VD-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


def _cilovy_azimut(cur, product_id):
    """OPRAVA 2026-09-25 (bot3/Robert, karty #4593/#4903): drive pevnych
    240 - to je "celo minus 30" jen u LEVYCH regalu (celo 270), u
    PRAVYCH (celo 90) padne presne do sektoru {240,270,300}, ktery se
    VUBEC nerenderuje (viz VANDR_RENDER_HOWTO.md "otočka podle strany").
    Pocita se relativne ke KARTINU vlastnimu celu (`vandr_predni_
    azimut_deg`, stejny sloupec jako pouziva render) - zadna druha
    konstanta. None = karta jeste nema spocitane celo (nemel by nastat
    u zadne karty s aktivnim renderem, ale radeji nehadat nez tvrdit
    nesmyslny azimut)."""
    cur.execute("SELECT vandr_predni_azimut_deg FROM shop_products WHERE id=%s", (product_id,))
    r = cur.fetchone()
    if not r or r["vandr_predni_azimut_deg"] is None:
        return None
    return (r["vandr_predni_azimut_deg"] - 30) % 360


# Soubor nahledu je od 2026-09-30 JEDNOTNA DLAZDICE (ctverec nd.CIL, delsi strana sestavy 85 %), ne surovy snimek
# otocky - viz scripts/_nahled_dlazdice.py (Robert 2026-09-25 "PODRUHE": nahledy musi byt vsechny stejne velke
# a ve stejnem formatu). Priponu (vc. VERZE algoritmu) pozna idempotence: nahled bez ni je surovy nebo ze starsi
# verze algoritmu a prepise se.
NORMALIZOVANY_SUFIX = "-t%dv%d.jpg" % (nd.CIL, nd.VERZE)   # zmena algoritmu (nd.VERZE) = prepocet vsech


def _hlavni_nahled_filename(product_id, azimuth_deg):
    return f"product-{product_id}_turntable-a{azimuth_deg}-e{ELEVATION_DEG:02d}{NORMALIZOVANY_SUFIX}"


def zajisti_hlavni_nahled_z_otocky(cur, product_id, sku=None, apply=True, smazat_stare=True):
    """Vraci (stav, detail): stav je 'vlozeno'/'aktualizovano'/'preskoceno'/'chyba'.

    Nedela commit - o transakci se stara volajici (stejny vzor jako
    _resolve_and_insert_order v api/orders.py).

    OPRAVA 2026-09-25 (Robert: "pravé sestavy se přerenderovaly, ale je
    potřeba aktualizovat náhledový obrázek") - puvodni idempotence
    ("existuje radek s timhle PRESNYM nazvem souboru?") znamenala, ze
    po JAKEMKOLI prerenderovani (i beze zmeny razitek - presne tenhle
    pripad, oprava azimutu v renderu samotnem) zustal viset stary
    obrazek navzdy. Otisk razitek (_vandr_render_otisk.py, sha256 vs
    vandr_render_razitka_otisk) by TENHLE konkretni pripad NEODHALIL -
    razitka se nezmenila, zmenila se jen davka snimku - proto se
    porovnava STARI aktivniho snimku vuci stari existujiciho nahledu,
    ne otisk razitek. Idempotentni presto zustava: kdyz je existujici
    nahled stejne stary nebo novejsi nez aktivni snimek, nic se
    nemeni.

    `smazat_stare=False` (jednorazove prepnuti surovych nahledu na jednotnou dlazdici, 2026-09-30): stary soubor
    zustane na disku (jen radek galerie se nahradi) - lze se vratit podle zalohy radku v backups/."""
    azimuth_deg = _cilovy_azimut(cur, product_id)
    if azimuth_deg is None:
        return "chyba", "karta jeste nema spocitane celo (vandr_predni_azimut_deg IS NULL)"

    cur.execute(
        "SELECT filename, created_at FROM product_turntable_frames "
        "WHERE shop_product_id=%s AND azimuth_deg=%s AND elevation_deg=%s AND is_active=1 "
        "ORDER BY tier_px DESC LIMIT 1",
        (product_id, azimuth_deg, ELEVATION_DEG),
    )
    frame = cur.fetchone()
    if not frame:
        return "chyba", f"zadny aktivni frame a{azimuth_deg}/e{ELEVATION_DEG:02d} (celo-30)"
    src = os.path.join(CONTENT_FILES_ROOT, frame["filename"])
    if not os.path.isfile(src):
        return "chyba", f"soubor chybi na disku: {src}"

    # Stavajici hlavni nahled TOHOTO produktu podle PREFIXU nazvu (ne
    # presneho nazvu) - presny azimut v nazvu se muze mezi kartami/
    # prepocty lisit, sledujeme "existuje uz nejaky otockovy hlavni
    # nahled", ne "existuje presne TENHLE soubor".
    cur.execute(
        "SELECT id, filename, created_at FROM content_gallery_items "
        "WHERE owner_type='product' AND owner_id=%s AND filename LIKE %s "
        "ORDER BY created_at DESC",
        (product_id, f"product-{product_id}_turntable-a%"),
    )
    stavajici = cur.fetchall()
    if (stavajici and stavajici[0]["created_at"] >= frame["created_at"]
            and stavajici[0]["filename"].endswith(NORMALIZOVANY_SUFIX)):
        return "preskoceno", None

    nazev_souboru = _hlavni_nahled_filename(product_id, azimuth_deg)
    if not apply:
        return ("aktualizovano" if stavajici else "vlozeno"), \
            f"{nazev_souboru} (azimut={azimuth_deg})" + (
                f", nahradilo by {stavajici[0]['filename']}" if stavajici else "")

    if stavajici:
        # Zachovat POZICI stavajiciho hlavniho nahledu (uz driv vyhral
        # razeni jako nejnizsi sort_order) - novy jen prevezme jeho
        # misto, nepocita se znovu.
        cur.execute("SELECT sort_order FROM content_gallery_items WHERE id=%s", (stavajici[0]["id"],))
        novy_sort = cur.fetchone()["sort_order"]
    else:
        cur.execute(
            "SELECT COALESCE(MIN(sort_order), 1) AS m FROM content_gallery_items "
            "WHERE owner_type='product' AND owner_id=%s",
            (product_id,),
        )
        novy_sort = cur.fetchone()["m"] - 1

    for stary in stavajici:
        cur.execute("DELETE FROM content_gallery_items WHERE id=%s", (stary["id"],))
        if smazat_stare and stary["filename"] != nazev_souboru:
            stara_cesta = os.path.join(GALLERY_ITEMS_DIR, stary["filename"])
            if os.path.isfile(stara_cesta):
                os.remove(stara_cesta)

    os.makedirs(GALLERY_ITEMS_DIR, exist_ok=True)
    dst = os.path.join(GALLERY_ITEMS_DIR, nazev_souboru)
    nd.uloz_dlazdici(src, dst)
    cur.execute(
        "INSERT INTO content_gallery_items "
        "(owner_type, owner_id, filename, media_type, caption, is_public, sort_order) "
        "VALUES ('product', %s, %s, 'image', %s, 1, %s)",
        (product_id, nazev_souboru, "Náhled sestavy", novy_sort),
    )
    akce = "aktualizovano" if stavajici else "vlozeno"
    detail = f"{nazev_souboru} (azimut={azimuth_deg}, sort_order={novy_sort})" + (
        f" - nahradilo {stavajici[0]['filename']}" if stavajici else "")
    return akce, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--ponechat-stare", action="store_true",
                    help="stare soubory nahledu nemazat (jednorazove prepnuti na jednotnou dlazdici)")
    args = ap.parse_args()
    print(f"=== Vandr hlavni nahled z otocky (azimut = celo-30 na kartu, e{ELEVATION_DEG}) — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zmeneno, preskoceno, chyba = 0, 0, []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, sku FROM shop_products WHERE sku REGEXP %s AND active=1 ORDER BY id",
                (VD_SKU_REGEXP,),
            )
            karty = cur.fetchall()
            for k in karty:
                stav, detail = zajisti_hlavni_nahled_z_otocky(cur, k["id"], sku=k["sku"], apply=args.apply,
                                                              smazat_stare=not args.ponechat_stare)
                if stav == "preskoceno":
                    preskoceno += 1
                elif stav == "chyba":
                    chyba.append((k["id"], k["sku"], detail))
                else:
                    zmeneno += 1
                    print(f"[{k['id']}] {k['sku']} -> {'' if args.apply else 'BYLO BY: '}{detail}")
        if args.apply:
            conn.commit()
    finally:
        conn.close()

    print(f"\n{'HOTOVO' if args.apply else 'DRY-RUN'}: {zmeneno} karet {'upraveno' if args.apply else 'by bylo upraveno'}, {preskoceno} uz melo (preskoceno).")
    if chyba:
        print(f"\nCHYBY ({len(chyba)}):")
        for pid, sku, msg in chyba:
            print(f"  [{pid}] {sku}: {msg}")
    return 1 if chyba else 0


if __name__ == "__main__":
    sys.exit(main())
