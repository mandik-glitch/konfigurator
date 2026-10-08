#!/usr/bin/env python3
"""Robert pres bot3 2026-09-11: 4 ze vzorku 20 patri do vyrazenych rodin
(logiman-sse-vratkove-stoly, ford-transit-doublefloor-01,
vysuvy-z-podlahy-na-miru, balici-ergonomicke-stoly) - "Obnov je ze
zaloh do puvodniho stavu, at vzorek odpovida pravidlu, ktere plati."

Obnova + overeni SHA proti manifestu, stejny bezpecny vzor jako
2026-09-11_prerazitkuj_vzorek_20_hustota.py - NEMAZE radek z manifestu
(historie "bylo otisknuto, pak obnoveno" je uzitecna), jen fyzicky
vraci live soubor na original a oznaci radek pres `reverted_at`
(bot3 2026-09-11: bez tohohle radek dal lze, ze soubor je otisknuty).

Spoustet VYHRADNE jako www-data (systemd-run, viz
2026-09-11_razitkuj_vzorek_20.py pro presny prikaz).
"""
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402
os.environ.update(_env.load_env())

import app  # noqa: E402,F401
import obrazky_razitko as orz  # noqa: E402

REL_PATHS_K_OBNOVE = (
    "content-files/gallery/realizace_stolu/logiman-sse-vratkove-stoly.jpg",
    "content-files/gallery/vestavby_dodavek/ford-transit-doublefloor-01.jpg",
    "content-files/gallery/vestavby_dodavek/vysuvy-z-podlahy-na-miru.jpg",
    "content-files/gallery/realizace_stolu/balici-ergonomicke-stoly.jpg",
    # bot9 2026-09-11 dohledal dodatecne: v puvodnim vzorku 20 byl i tenhle
    # soubor (jmeno odpovida filtru "vandrawee", i kdyz nemel vizualne
    # potvrzenou zapecenou znacku) - Robertovo pravidlo "vyradit CELOU
    # rodinu" ho zahrnuje, i kdyz nebyl v puvodnim seznamu 4 od bot3.
    "content-files/gallery/vestavby_dodavek/stavebnice-do-aut-vandrawee-2020-foto-00.jpg",
)


def main():
    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rel_path, original_backup_path, original_sha256 "
                "FROM image_watermark_manifest WHERE rel_path IN (%s)" %
                ",".join(["%s"] * len(REL_PATHS_K_OBNOVE)), REL_PATHS_K_OBNOVE)
            radky = {r["rel_path"]: r for r in cur.fetchall()}
    finally:
        conn.close()

    for rel in REL_PATHS_K_OBNOVE:
        radek = radky.get(rel)
        if not radek:
            print(f"CHYBA {rel}: neni v manifestu")
            continue
        abs_path = os.path.join(orz.WEBAPP_ROOT, rel)
        with open(radek["original_backup_path"], "rb") as f:
            zaloha_bytes = f.read()
        if orz._sha256(zaloha_bytes) != radek["original_sha256"]:
            print(f"STOP {rel}: zaloha se neshoduje s manifestem, PRESKAKUJI")
            continue
        orz._atomicky_zapis(abs_path, zaloha_bytes)
        with open(abs_path, "rb") as f:
            po_obnove = f.read()
        if orz._sha256(po_obnove) != radek["original_sha256"]:
            print(f"CHYBA {rel}: po obnove neshoda!")
            continue

        conn2 = app.get_conn()
        try:
            with conn2.cursor() as cur:
                orz._zapis_obnoveni(cur, rel)
            conn2.commit()
        finally:
            conn2.close()
        print(f"OBNOVENO+OVERENO+OZNACENO(reverted_at) {rel}")


if __name__ == "__main__":
    main()
