#!/usr/bin/env python3
"""Srovna SKU karet sestav do dohodnute konvence.

Robert 2026-09-13: *"Bylo nastaveno určité kódování sku"*, *"mám dojem že
schválené sestavy na e-shopu pravidlo kódu SKU nesplňují"*. Ma pravdu.

KONVENCE
--------
Kod sestavy ma tvar (Robert 2026-09-11, presny tvar):

    K-075-EB-30-A-0001-2-0
    │     │  │  │ │    │ └─ dodatek
    │     │  │  │ │    └─── horni blok
    │     │  │  │ └──────── rozpis boxu (4 cislice)
    │     │  │  └────────── verze
    │     │  └───────────── profil
    │     └──────────────── typologie (2 znaky)
    └────────────────────── karoserie

SKU KARTY je ta cast, ktera je pro vsechna provedeni na karte SPOLECNA, tedy
**karoserie-typologie-profil**. Presne tak Robert 2026-09-11 opravil kartu
3942 na `K-075-EB-30` (z puvodniho `SEST-K-075-EB-30`, "v sku nebude slovo
SEST").

CO BYLO SPATNE (zavedl bot5 2026-09-12)
---------------------------------------
* `K-075-EB-30-1030` - spravny prefix, ale `-1030` je segment navic, ktery
  ve schematu neexistuje. Na te pozici ma stat VERZE, takze se `1030` cte
  jako oznaceni verze.
* `K-118-EB-1030`, `K-119-EB-1030` - HORSI: profil u techto sestav nebyl
  znamy, takze se vynechal a `1030` tim sklouzlo do pozice PROFILU. SKU se
  tedy cte jako "profil 1030 mm". Aktivne matouci udaj.

`-1030` melo odlisit generaci s koliznimi rezervami 10/30 mm od starsi
2/20 mm. Jenze starsi karta (3942) je archivovana, takze uz neni co
odlisovat - a rezerva neni soucast dohodnuteho schematu.

CO SKRIPT DELA
--------------
1. Archivovane 3942 uvolni `K-075-EB-30` (dostane archivni SKU se suffixem).
2. Nastupnicka 3943 dostane ciste `K-075-EB-30`.
3. Jumpy 3944/3945 zbavi matouciho `-1030` -> `K-118-EB` / `K-119-EB`.
   Profil se NEDOPLNUJE: `profil_mm` je u nich NULL a projekt ma vyslovne
   pravidlo, ze profil URCUJE ADMIN, nehada se z geometrie ("velikost
   profilu je jen pro orientaci, profil určuje admin"). SKU je tim pravdive
   neuplne misto nepravdive uplneho. Jakmile admin profil vyplni, dosypat
   posledni segment je jednoradkova zmena.

BEZPECNOST
----------
* Overeno pred zapisem: na zadne z karet nevisi ani jedna polozka
  objednavky (`shop_order_items`), takze zmena SKU nerozbije historii.
  Skript to kontroluje SAM a pri nalezu kartu PRESKOCI - SKU je
  identifikator, na ktery se vaze objednavka a sklad (WORKFLOW.md 26).
* `sku` je UNIQUE, proto se 3942 prejmenovava PRVNI (jinak by INSERT/UPDATE
  nastupkyne spadl na duplicitu). Cele v jedne transakci.
* Idempotentni, zaloha do `backups/`.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-13_bot5_sku_do_konvence.py
    api/venv/bin/python3 scripts/2026-09-13_bot5_sku_do_konvence.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-13_bot5_sku_do_konvence",
)

# (id, nove SKU, duvod) - poradi ZALEZI: 3942 uvolnuje SKU pro 3943.
ZMENY = [
    (3942, "K-075-EB-30-ARCHIV-2-20",
     "archivovana karta uvolnuje K-075-EB-30 nastupkyni; suffix rika, ze je to "
     "starsi generace s rezervami 2/20 mm"),
    (3943, "K-075-EB-30",
     "karoserie-typologie-profil podle konvence; -1030 byl segment navic na "
     "pozici verze"),
    (3944, "K-118-EB",
     "pryc matouci -1030, ktere sedelo v pozici PROFILU; profil doplni admin"),
    (3945, "K-119-EB",
     "pryc matouci -1030, ktere sedelo v pozici PROFILU; profil doplni admin"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== SKU do konvence — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha, provest = [], []
    # SKU, ktera uvolni DRIVE naplanovana zmena v teze davce. Bez tohohle by
    # kontrola kolize nize odmitla 3943 ("K-075-EB-30 uz ma karta 3942"),
    # prestoze 3942 to SKU o radek vys prave opousti. Poradi v ZMENY tedy
    # neni kosmeticke - uvolneni musi predchazet obsazeni.
    uvolnene = set()
    try:
        with conn.cursor() as cur:
            for pid, nove, duvod in ZMENY:
                cur.execute(
                    "SELECT id, sku, name, active, is_archived FROM shop_products WHERE id=%s",
                    (pid,),
                )
                r = cur.fetchone()
                if not r:
                    print(f"  {pid}: karta neexistuje, preskakuji")
                    continue
                if r["sku"] == nove:
                    print(f"  {pid}: uz ma {nove}, preskakuji")
                    continue
                cur.execute(
                    "SELECT COUNT(*) n FROM shop_order_items WHERE product_id=%s", (pid,)
                )
                pocet = cur.fetchone()["n"]
                if pocet:
                    # SKU je identifikator, na ktery se vaze objednavka a sklad.
                    print(f"  {pid}: ⛔ PRESKAKUJI — visi na nem {pocet} polozek objednavek")
                    continue
                cur.execute("SELECT id FROM shop_products WHERE sku=%s AND id<>%s", (nove, pid))
                kolize = cur.fetchone()
                if kolize and nove not in uvolnene:
                    print(f"  {pid}: ⛔ PRESKAKUJI — SKU {nove} uz ma karta {kolize['id']}")
                    continue
                uvolnene.add(r["sku"])
                print(f"  {pid}: {r['sku']} -> {nove}")
                print(f"        {duvod}")
                zaloha.append({"product_id": pid, "puvodni_sku": r["sku"], "nove_sku": nove,
                               "nazev": r["name"], "duvod": duvod})
                provest.append((nove, pid, r["sku"]))

            if args.apply and provest:
                os.makedirs(ZALOHA_DIR, exist_ok=True)
                with open(os.path.join(ZALOHA_DIR, "pred_zmenou.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(zaloha, f, ensure_ascii=False, indent=2)
                for nove, pid, stare in provest:
                    cur.execute("UPDATE shop_products SET sku=%s WHERE id=%s", (nove, pid))
                    cur.execute(
                        "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) "
                        "VALUES (NULL,'update','shop_product',%s,%s)",
                        (pid, f"bot5 skript 2026-09-13: SKU {stare} -> {nove} "
                              f"(srovnani do konvence karoserie-typologie-profil)"),
                    )
        if args.apply:
            conn.commit()
            print(f"\nCOMMIT hotovy, zmeneno SKU: {len(provest)}")
        else:
            print(f"\nDRY-RUN: nic nezapsano, ke zmene: {len(provest)}")
    finally:
        conn.close()

    if args.apply:
        print("\n=== OVERENI z noveho spojeni ===")
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute(
                    "SELECT id, sku, active, is_archived FROM shop_products "
                    "WHERE id IN (3942,3943,3944,3945) ORDER BY id"
                )
                for r in cur.fetchall():
                    stav = "archiv" if r["is_archived"] else ("aktivni" if r["active"] else "neaktivni")
                    print(f"  {r['id']}  {r['sku']:26} [{stav}]")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
