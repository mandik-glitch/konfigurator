#!/usr/bin/env python3
"""Rozsiri horni_blok_varianty.kod na dvojcislo + prepocita kod_sestavy.

Robert 2026-09-13 v chatu, segment 7: "dej mu dvojcifernost, varianty
pribudou" - 0-6 se zleva doplni na 00-06, aby bylo od zacatku misto na
dalsi provedeni bez dalsi zmeny sirky sloupce.

Kod_sestavy u sedmi sestav (341-347, jedine s vyplnenym kod_sestavy) se
prepocita ze zdrojovych sloupcu (karoserie_kod, typologie, profil_mm,
verze, typologie_varianta_id, horni_blok_varianty.kod, dodatek) - ne
retezcovym nahrazenim v existujicim textu, aby se predeslo chybe pri
pripadne kolizi vzoru.

Pouziti:
    python3 scripts/2026-09-13_horni_blok_dvojcisl_zapsat.py            # dry-run
    python3 scripts/2026-09-13_horni_blok_dvojcisl_zapsat.py --apply    # zapis
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_PATH = os.path.join(REPO_ROOT, "backups", "2026-09-13_horni_blok_dvojcisl_pred_zmenou.json")

APPLY = "--apply" in sys.argv


def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SHOW COLUMNS FROM horni_blok_varianty LIKE 'kod'")
    sloupec = cur.fetchone()
    print(f"[horni_blok_varianty.kod typ] {sloupec['Type']}")
    uz_hotovo = sloupec["Type"].lower().startswith("char(2)")

    if not uz_hotovo:
        cur.execute("SHOW INDEX FROM horni_blok_varianty WHERE Column_name='kod'")
        indexy_pred = cur.fetchall()
        print(f"[UNIQUE indexy na kod před změnou] {[i['Key_name'] for i in indexy_pred]}")

        if APPLY:
            cur.execute("ALTER TABLE horni_blok_varianty MODIFY kod CHAR(2) NOT NULL")
            cur.execute("UPDATE horni_blok_varianty SET kod = LPAD(kod, 2, '0')")
            cur.execute("SHOW INDEX FROM horni_blok_varianty WHERE Column_name='kod'")
            indexy_po = cur.fetchall()
            print(f"[UNIQUE indexy na kod po změně] {[i['Key_name'] for i in indexy_po]}")
            if not indexy_po:
                raise SystemExit("⛔ UNIQUE index na kod se ztratil, přerušuji před commitem!")
        else:
            print("  -> (dry-run) rozšířilo by se na CHAR(2) a doplnily nuly")
    else:
        print("  -> už CHAR(2), přeskočeno")

    cur.execute("""
        SELECT pa.id, pa.karoserie_kod, rt.kod AS typologie_kod, pa.profil_mm, pa.verze,
               tv.kod AS varianta_kod, hb.kod AS horni_blok_kod, pa.dodatek, pa.kod_sestavy
        FROM product_assemblies pa
        JOIN regal_typologie rt ON rt.id = pa.typologie_id
        JOIN typologie_varianty tv ON tv.id = pa.typologie_varianta_id
        JOIN horni_blok_varianty hb ON hb.id = pa.horni_blok_varianta_id
        WHERE pa.kod_sestavy IS NOT NULL
        ORDER BY pa.id
    """)
    radky = cur.fetchall()
    print(f"\n[sestav k přepočtu kod_sestavy] {len(radky)}")

    zaloha, zmeny = [], []
    for r in radky:
        novy = (f"{r['karoserie_kod']}-{r['typologie_kod']}-{r['profil_mm']}-{r['verze']}-"
                f"{r['varianta_kod']}-{r['horni_blok_kod']}-{r['dodatek']}")
        if novy == r["kod_sestavy"]:
            print(f"  [{r['id']}] beze změny ({novy})")
            continue
        print(f"  [{r['id']}] {r['kod_sestavy']} -> {novy}")
        zaloha.append({"id": r["id"], "puvodni_kod_sestavy": r["kod_sestavy"], "novy_kod_sestavy": novy})
        zmeny.append((novy, r["id"]))

    if APPLY and zmeny:
        os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
        with open(BACKUP_PATH, "w", encoding="utf-8") as f:
            json.dump(zaloha, f, ensure_ascii=False, indent=2)
        for novy, pid in zmeny:
            cur.execute("UPDATE product_assemblies SET kod_sestavy=%s WHERE id=%s", (novy, pid))

    if APPLY:
        conn.commit()
        print(f"\nAPLIKOVÁNO. kod_sestavy změněno u {len(zmeny)} sestav.")
    else:
        conn.rollback()
        print(f"\nDRY-RUN, nic nezapsáno. kod_sestavy ke změně: {len(zmeny)}. Spusť s --apply pro zápis.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
