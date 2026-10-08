#!/usr/bin/env python3
"""Smazani duplicitnich radku v shop_product_images (bot5, 2026-09-17,
Robert pres bot3: "proc se fotky duplikuji v galerii").

Bot3 dohledal pricinu (scripts/2026-08-11_dogus_dynamic_shelving_import.py,
opraveno samostatne) - kdyz dodavatel uvedl pro dogus_image_schema_url i
dogus_image_render_url STEJNOU URL, skript ji stahl a vlozil 2x.

Bot3 hlasil "36 zivych + 27 archivovanych" (63 celkem) - NEZAVISLE overeno
primo (MD5 na diskovych souborech, ne jen shoda source_url - 482 skupin
melo stejnou source_url, ale RUZNY soubor, tedy NEJSOU duplicitni):
skutecny pocet je 36 CELKEM, z toho jen 9 opravdu zivych/verejnych
(active=1 AND is_archived=0), zbylych 27 je archivovanych
(is_archived=1, i kdyz active=1) - bot3 pravdepodobne pocital jen
active=1 bez is_archived filtru, coz 9 zivych + 27 archivovanych sectlo
dohromady na "36 zivych". Opraveno zjisteni predano zpet bot3.

Postup: v kazde skupine (product_id, source_url s MD5 shodou) ponechat
radek s NEJNIZSIM sort_order (typicky 0, "prvni/hlavni" fotka), smazat
zbyvajici. Soubor na disku NEMAZAT (jina fotka muze mit vlastni odkaz
jinde, mazani DB radku staci - osirely soubor na disku je neskodny).

Zaloha do backups/ pred smazanim.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-17_bot5_fix_duplicitni_fotky.py
    api/venv/bin/python3 scripts/2026-09-17_bot5_fix_duplicitni_fotky.py --apply
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-17_bot5_fix_duplicitni_fotky",
)
GALLERY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "webapp", "content-files", "gallery",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== fix duplicitnich fotek v shop_product_images — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = []
    ke_smazani = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT product_id, source_url, GROUP_CONCAT(id ORDER BY sort_order) AS ids, "
                "       GROUP_CONCAT(filename ORDER BY sort_order) AS filenames "
                "FROM shop_product_images GROUP BY product_id, source_url HAVING COUNT(*) > 1"
            )
            skupiny = cur.fetchall()
            zivych = 0
            archivovanych = 0
            for r in skupiny:
                ids = [int(x) for x in r["ids"].split(",")]
                filenames = r["filenames"].split(",")
                hashes = []
                for fn in filenames:
                    path = os.path.join(GALLERY_DIR, fn)
                    with open(path, "rb") as f:
                        hashes.append(hashlib.md5(f.read()).hexdigest())
                if len(set(hashes)) != 1:
                    continue  # ruzny obsah navzdory stejne source_url - NENI duplicita
                cur.execute("SELECT active, is_archived, name FROM shop_products WHERE id=%s", (r["product_id"],))
                p = cur.fetchone()
                zivy = bool(p and p["active"] and not p["is_archived"])
                if zivy:
                    zivych += 1
                else:
                    archivovanych += 1
                # ponechat PRVNI (nejnizsi id/sort_order), smazat zbytek
                keep_id, drop_ids = ids[0], ids[1:]
                zaloha.append({
                    "product_id": r["product_id"], "product_name": p["name"] if p else None,
                    "zivy": zivy, "keep_id": keep_id, "drop_ids": drop_ids,
                    "filenames": filenames, "md5": hashes[0],
                })
                ke_smazani.extend(drop_ids)
            print(f"Skutecnych duplicitnich skupin (MD5 overeno): {len(zaloha)}")
            print(f"  z toho zive/verejne produkty: {zivych}")
            print(f"  z toho archivovane/neaktivni: {archivovanych}")
            print(f"Radku ke smazani celkem: {len(ke_smazani)}")

            os.makedirs(ZALOHA_DIR, exist_ok=True)
            with open(os.path.join(ZALOHA_DIR, "pred_smazanim.json"), "w", encoding="utf-8") as f:
                json.dump(zaloha, f, ensure_ascii=False, indent=2, default=str)

            if args.apply and ke_smazani:
                placeholders = ",".join(["%s"] * len(ke_smazani))
                cur.execute(f"DELETE FROM shop_product_images WHERE id IN ({placeholders})", ke_smazani)
                print(f"Smazano radku: {cur.rowcount}")
        if args.apply:
            conn.commit()
            print("COMMIT hotovy.")
        else:
            print("DRY-RUN: nic nesmazano.")
    finally:
        conn.close()

    if args.apply:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute(
                    "SELECT product_id, source_url, COUNT(*) c FROM shop_product_images "
                    "GROUP BY product_id, source_url HAVING c > 1"
                )
                zbyva = cur.fetchall()
                print(f"\nOVERENI: skupin se stale >1 radkem stejneho source_url: {len(zbyva)} "
                      f"(ocekavano >0 - to jsou ty s RUZNYM obsahem, ne skutecne duplicity)")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
