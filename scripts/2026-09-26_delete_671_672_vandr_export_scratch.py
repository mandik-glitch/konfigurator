#!/usr/bin/env python3
"""Smaze product_assemblies id 671 a 672 - testovaci/scratch export
radky z vyvoje Vandr FBX->karta pipeline (VD-EXPORT-trafic-2f89b425
a VD-2b6d4dd7-7a9d-400f-bfa6-a2d8e3aa743e), NE skutecne sestavy.

Kontext (bot16, 2026-09-26, v ramci ukolu "typ sestavy" - bot8 je
puvodne oznacil za scratch pri navrhu migrace vsech 530 zbylych
product_assemblies radku na sestava_typ=AUTO, bot3 rozhodnuti overil
a schvalil smazani):

  - Oba maji vyplnene shop_product_id (671->4902, 672->4903), na prvni
    pohled vypadaji jako zive, ALE:
  - OBA maji SKU s prefixem "VD-" (4902: VD-EXPORT-trafic-2f89b425,
    4903: VD-2b6d4dd7-7a9d-400f-bfa6-a2d8e3aa743e) - to jsou VANDR
    karty. Cenu/obsah berou ze synchronizace s vandrawee_work (viz
    api/vandr_price_webhook.py), NE z product_assemblies - smazani
    tady na ne nema zadny vliv.
  - Nazvy radku jsou doslovne "EXPORT (realny FBX z appky): Renault
    Trafic L2H1 - leva police" a "Fiat Ducato L1H1 (rozvor 3000 mm)"
    - `data` sloupec obou ma "role": "vandrawee-export" - jde o
    testovaci export z vyvoje pipeline, ne o schvalenou sestavu.
  - shop_product 4903 (active=1, category_id=269) je ta karta, na
    ktere dnes rano bot5 zivě testoval price-webhook (rozbil na 99999,
    webhook vratil na 28333 - presne cislo, ktere na ni dnes je).
    Zustava NEDOTCENA - VD-% karty nezavisi na product_assemblies.
  - Zadna reference v shop_cart_items/shop_order_items/
    production_comments/production_step_checks (0 radku, overeno).
  - FK product_turntable_frames.assembly_id -> product_assemblies.id
    ma ON DELETE SET NULL (ne RESTRICT/CASCADE) - existuje 204 radku
    pro 671 (54 z nich is_active=1) a 54 pro 672 (0 aktivnich).
    Smazanim se NESMAZOU, jen ztrati assembly_id (NULL) - shop_product
    4902 (671) je uz dnes active=0, takze zadny zivy nahled na ne
    nezavisi.

Zaloha (cely obsah vc. `data` sloupce) pred smazanim:
  backups/2026-09-26_product_assemblies_671_672_pred_smazanim.json

Pouziti:
    python3 scripts/2026-09-26_delete_671_672_vandr_export_scratch.py            # dry-run
    python3 scripts/2026-09-26_delete_671_672_vandr_export_scratch.py --apply    # smazani
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

APPLY = "--apply" in sys.argv
IDS = (671, 672)


def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, shop_product_id FROM product_assemblies WHERE id IN (%s,%s)", IDS)
    rows = cur.fetchall()
    print(f"[nalezeno v product_assemblies] {[r['id'] for r in rows]}")
    if not rows:
        print("Nic k smazani, radky uz neexistuji.")
        cur.close()
        conn.close()
        return

    if APPLY:
        cur.execute("DELETE FROM product_assemblies WHERE id IN (%s,%s)", IDS)
        print(f"[smazano radku] {cur.rowcount}")
    else:
        print("[dry-run] smazalo by se 2 radky (671, 672)")

    if APPLY:
        conn.commit()
        print("\nAPLIKOVÁNO.")
    else:
        conn.rollback()
        print("\nDRY-RUN, nic nezapsáno. Spusť s --apply pro smazání.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
