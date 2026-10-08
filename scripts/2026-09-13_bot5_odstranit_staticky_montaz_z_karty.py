#!/usr/bin/env python3
"""Odstrani staticky montazni odstavec z `shop_products.description` u karet,
kde uz montaz jede dynamicky pres `regal_umisteni.montaz_zakaznicky`.

Bez tohohle by se montazni veta zobrazovala DVAKRAT - jednou staticky
(soucast puvodniho odstavce popisu karty), jednou dynamicky (novy oddil
#pdMontazVarianta, viz api/product_assemblies.py + webapp/product.html,
2026-09-13).

Odstranuje jen PRESNY, znamy odstavec (beze zmeny zbytku popisu) - kdyz
nesedi presne, kartu PRESKOCI a nahlasi (nikdy needituje priblizne).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-13_bot5_odstranit_staticky_montaz_z_karty.py
    api/venv/bin/python3 scripts/2026-09-13_bot5_odstranit_staticky_montaz_z_karty.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-13_bot5_odstranit_staticky_montaz_z_karty",
)

ODSTAVEC = (
    "Konstrukce se kotví do zpevněných částí karoserie (bočnice a "
    "podlaha). Montáž zahrnuje vrtání do těchto částí, v souladu s "
    "požadavky na homologaci."
)
KARTY = (3943,)  # jedina karta dnes s timhle staticky vsazenym odstavcem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== odstraneni duplicitniho statickeho montaz odstavce — "
          f"{'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = []
    try:
        with conn.cursor() as cur:
            for pid in KARTY:
                cur.execute("SELECT id, sku, description FROM shop_products WHERE id=%s", (pid,))
                r = cur.fetchone()
                if not r:
                    print(f"  {pid}: karta neexistuje, preskakuji"); continue
                popis = r["description"] or ""
                if ODSTAVEC not in popis:
                    print(f"  {pid} [{r['sku']}]: presny odstavec nenalezen, PRESKAKUJI beze zmeny")
                    continue
                # Odstran odstavec i jeho okolni prazdne radky (dvojity
                # newline pred/za), at nezbyde osamela mezera v textu.
                novy = popis.replace("\n\n" + ODSTAVEC, "").replace(ODSTAVEC + "\n\n", "").replace(ODSTAVEC, "")
                novy = novy.strip()
                print(f"  {pid} [{r['sku']}]: odstavec nalezen, odstranuji "
                      f"({len(popis)} -> {len(novy)} znaku)")
                zaloha.append({"id": pid, "puvodni_description": popis})
                if args.apply:
                    cur.execute("UPDATE shop_products SET description=%s WHERE id=%s", (novy, pid))

        if args.apply and zaloha:
            os.makedirs(ZALOHA_DIR, exist_ok=True)
            with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                json.dump(zaloha, f, ensure_ascii=False, indent=2)
            conn.commit()
            print("\nCOMMIT hotovy.")
        else:
            print("\nDRY-RUN: nic nezapsano." if not args.apply else "\nNic k zapsani.")
    finally:
        conn.close()

    if args.apply and zaloha:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                print("\n=== OVERENI z noveho spojeni ===")
                for pid in KARTY:
                    cur.execute("SELECT description FROM shop_products WHERE id=%s", (pid,))
                    d = cur.fetchone()["description"]
                    print(f"  {pid}: odstavec porad pritomen? {'ANO - CHYBA' if ODSTAVEC in (d or '') else 'ne, OK'}")
                    print(f"       {d}")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
