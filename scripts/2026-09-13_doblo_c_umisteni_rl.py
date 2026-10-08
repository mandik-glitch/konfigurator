#!/usr/bin/env python3
"""Priradi umisteni RL (regal levy) sestavam 341-347 a preflipne kod_sestavy.

Robert 2026-09-13 v chatu: "doposud delame zatim jen RL" - vsech sedm
sestav Doblo C vzoru je regal LEVY, prava strana se zatim nestavi.

Pozice segmentu umisteni v kod_sestavy potvrdil Robert primo:
"K-075-RL-EB-30..." - hned za karoserii, pred typologii.

Pouziti:
    python3 scripts/2026-09-13_doblo_c_umisteni_rl.py            # dry-run
    python3 scripts/2026-09-13_doblo_c_umisteni_rl.py --apply    # zapis
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_PATH = os.path.join(REPO_ROOT, "backups", "2026-09-13_doblo_c_umisteni_rl_pred_zmenou.json")

APPLY = "--apply" in sys.argv
SESTAVY = (341, 342, 343, 344, 345, 346, 347)


def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM regal_umisteni WHERE klic='regal_levy'")
    rl = cur.fetchone()
    if not rl:
        raise SystemExit("⛔ regal_umisteni.regal_levy nenalezeno")
    rl_id = rl["id"]

    cur.execute(f"""
        SELECT pa.id, pa.umisteni_id, pa.karoserie_kod, rt.kod AS typologie_kod, pa.profil_mm,
               pa.verze, tv.kod AS varianta_kod, hb.kod AS horni_blok_kod, pa.dodatek, pa.kod_sestavy
        FROM product_assemblies pa
        JOIN regal_typologie rt ON rt.id = pa.typologie_id
        JOIN typologie_varianty tv ON tv.id = pa.typologie_varianta_id
        JOIN horni_blok_varianty hb ON hb.id = pa.horni_blok_varianta_id
        WHERE pa.id IN ({','.join(str(i) for i in SESTAVY)})
        ORDER BY pa.id
    """)
    radky = cur.fetchall()
    print(f"[sestav nalezeno] {len(radky)} (očekáváno {len(SESTAVY)})")

    zaloha, zmeny_umisteni, zmeny_kod = [], [], []
    for r in radky:
        novy_kod = (f"{r['karoserie_kod']}-RL-{r['typologie_kod']}-{r['profil_mm']}-{r['verze']}-"
                    f"{r['varianta_kod']}-{r['horni_blok_kod']}-{r['dodatek']}")
        print(f"  [{r['id']}] umisteni_id {r['umisteni_id']} -> {rl_id}   "
              f"kod_sestavy {r['kod_sestavy']} -> {novy_kod}")
        zaloha.append({"id": r["id"], "puvodni_umisteni_id": r["umisteni_id"],
                        "puvodni_kod_sestavy": r["kod_sestavy"], "novy_kod_sestavy": novy_kod})
        zmeny_umisteni.append(r["id"])
        zmeny_kod.append((novy_kod, r["id"]))

    if APPLY and zmeny_kod:
        os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
        with open(BACKUP_PATH, "w", encoding="utf-8") as f:
            json.dump(zaloha, f, ensure_ascii=False, indent=2)
        cur.execute(
            f"UPDATE product_assemblies SET umisteni_id=%s WHERE id IN ({','.join(str(i) for i in SESTAVY)})",
            (rl_id,),
        )
        for novy, pid in zmeny_kod:
            cur.execute("UPDATE product_assemblies SET kod_sestavy=%s WHERE id=%s", (novy, pid))
        conn.commit()
        print(f"\nAPLIKOVÁNO, {len(zmeny_kod)} sestav.")
    else:
        conn.rollback()
        print(f"\nDRY-RUN, nic nezapsáno. Spusť s --apply pro zápis.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
