#!/usr/bin/env python3
"""Uklid testovacich objednavek starsich 14 dnu - WORKFLOW.md bod 27.

LHUTA SE POCITA OD OZNACENI, NE OD VZNIKU. Robert 2026-09-10 na primy
dotaz, jestli se ma 39 historickych objednavek (vsechny starsi 14 dnu,
19 fakturovanych s danovymi doklady) smazat hned pri prvnim behu:
"pravidlo je po 14ti dnech, jako testovaci jsme je oznacili dnes".
Proto podminka `test_marked_at < NOW() - INTERVAL 14 DAY`, ne `created_at`.

=== CO SE MAZE ===
Objednavka a vsechno, co k ni tok vyrobil:
  shop_documents          doklady (zalohova/VDD/faktura/dodaci list)
  shop_stock_movements    skladove pohyby - VRACI SE UCINEK NA SKLAD
  shop_order_items        polozky
  shop_order_status_history  historie stavu
  shop_emails             pripadne e-mailove zaznamy
Samotne mazani NEPISE tenhle skript znovu - deleguje na
`orders._delete_orders_cascade()`, tedy TUTEZ funkci, kterou pouziva
mazani objednavky z adminu (vc. vraceni skladu pres
`products.reverse_and_delete_stock_movements()` a smazani navazanych
nakupnich objednavek). Detaily viz docstring u `smaz()` nize.

=== POJISTKY (WORKFLOW.md bod 28) ===
1. ZALOHA PRED SMAZANIM jako DOKONCENY KROK - kompletni JSON dump vsech
   dotcenych radku do backups/, fsync + kontrola velikosti. Kdyz zaloha
   z jakehokoli duvodu nevznikne, NEMAZE SE NIC.
2. Loguje se, CO se smazalo (seznam id + cisla objednavek a dokladu), ne
   jen pocet - `audit_log.detail` u bulk_delete dnes nese jen pocet, coz
   je znama mezera.
3. Kontrola cerstvym spojenim po commitu.
4. --dry-run pro nahled bez zapisu.
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402

os.environ.update(_env.load_env())

import app  # noqa: E402,F401 - MUSI byt drive nez orders (kruhovy import)
import orders  # noqa: E402

LHUTA_DNI = 14
BACKUP_DIR = "/opt/konfigurator/backups"

TABULKY_PODLE_ORDER_ID = [
    "shop_documents",
    "shop_order_items",
    "shop_order_status_history",
    "shop_emails",
]


def _conn():
    return app.get_conn()


def najdi_ke_smazani(cur):
    cur.execute(
        "SELECT id, order_number, status, created_at, test_marked_at, total_czk "
        "FROM shop_orders "
        "WHERE is_test=1 AND test_marked_at IS NOT NULL "
        "  AND test_marked_at < NOW() - INTERVAL %s DAY "
        "ORDER BY id",
        (LHUTA_DNI,),
    )
    return cur.fetchall()


def posbirej_zalohu(cur, ids):
    """Kompletni obsah vsech dotcenych radku - aby slo obnovit, ne jen zjistit,
    ze neco bylo."""
    fmt = ",".join(["%s"] * len(ids))
    data = {
        "vytvoreno": datetime.now().isoformat(),
        "duvod": f"uklid testovacich objednavek starsich {LHUTA_DNI} dnu (WORKFLOW.md bod 27)",
        "order_ids": list(ids),
        "tabulky": {},
    }
    cur.execute(f"SELECT * FROM shop_orders WHERE id IN ({fmt}) ORDER BY id", ids)
    data["tabulky"]["shop_orders"] = cur.fetchall()
    for tab in TABULKY_PODLE_ORDER_ID:
        cur.execute(f"SELECT * FROM {tab} WHERE order_id IN ({fmt}) ORDER BY id", ids)
        data["tabulky"][tab] = cur.fetchall()

    cisla = [r["order_number"] for r in data["tabulky"]["shop_orders"]]
    if cisla:
        fmt2 = ",".join(["%s"] * len(cisla))
        cur.execute(
            f"SELECT * FROM shop_stock_movements WHERE document_number IN ({fmt2}) ORDER BY id",
            cisla,
        )
        data["tabulky"]["shop_stock_movements"] = cur.fetchall()
    else:
        data["tabulky"]["shop_stock_movements"] = []
    return data


def zapis_zalohu(data):
    """POJISTKA 1 - zaloha musi byt na disku a kompletni DRIV, nez se maze."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    cesta = os.path.join(
        BACKUP_DIR, f"{datetime.now():%Y-%m-%d_%H%M%S}_test_orders_pred_smazanim.json"
    )
    with open(cesta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, default=str)
        f.flush()
        os.fsync(f.fileno())
    velikost = os.path.getsize(cesta)
    if velikost < 100:
        raise RuntimeError(f"Zaloha {cesta} je podezrele mala ({velikost} B) - NEMAZU nic.")
    return cesta, velikost


def smaz(cur, ids):
    """Mazani deleguje na `orders._delete_orders_cascade()` - TUTEZ funkci,
    kterou pouziva mazani objednavky z adminu. Zamerne se to tu nepise
    znovu: ta funkce uz resi tri veci, na ktere je snadne zapomenout
    (a rucni verze tohohle skriptu na jednu z nich skutecne zapomnela):
      1. navazane NAKUPNI objednavky (shop_purchase_orders.source_order_id)
         se smazou bezpecnou cestou, jinak zustanou osirele,
      2. skladove pohyby nemaji FK na objednavku (vaze je jen textovy
         document_number), takze by je DELETE nikdy nesmazal - a hlavne
         se jejich ucinek VRACI na sklad pres
         reverse_and_delete_stock_movements() (pohyb, ktery by poslal
         stock_qty do zaporu, zustane radsi nesmazany),
      3. shop_documents/shop_emails maji NO ACTION FK a musi se smazat
         rucne pred objednavkou; polozky a historie stavu odejdou samy
         pres ON DELETE CASCADE.
    Vraci (prehled_pro_log, po_item_ids) - po_item_ids se po commitu
    douklidi v galerii, stejne jako to dela admin endpoint."""
    fmt = ",".join(["%s"] * len(ids))
    prehled = {"dokumenty": [], "objednavky": [], "smazano_objednavek": 0}

    # Precist PRED smazanim - kvuli vypisu do logu (bod 28: logovat CO, ne jen kolik)
    cur.execute(
        f"SELECT id, order_id, document_type, document_number FROM shop_documents "
        f"WHERE order_id IN ({fmt}) ORDER BY id", ids)
    prehled["dokumenty"] = [
        f"{r['document_type']}:{r['document_number']} (objednavka {r['order_id']})"
        for r in cur.fetchall()
    ]
    cur.execute(f"SELECT id, order_number FROM shop_orders WHERE id IN ({fmt}) ORDER BY id", ids)
    prehled["objednavky"] = [f"#{r['id']} {r['order_number']}" for r in cur.fetchall()]

    smazano, po_item_ids = orders._delete_orders_cascade(cur, ids)
    prehled["smazano_objednavek"] = smazano
    return prehled, po_item_ids


def main():
    dry = "--dry-run" in sys.argv
    ted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = _conn()
    try:
        with conn.cursor() as cur:
            radky = najdi_ke_smazani(cur)
    finally:
        conn.close()

    if not radky:
        print(f"[{ted}] Nic ke smazani (zadna testovaci objednavka starsi "
              f"{LHUTA_DNI} dnu od oznaceni).")
        return 0

    ids = [r["id"] for r in radky]
    print(f"[{ted}] Ke smazani {len(ids)} testovacich objednavek "
          f"(oznacenych pred vic nez {LHUTA_DNI} dny):")
    for r in radky:
        print(f"  #{r['id']:>4} {r['order_number']:<20} {r['status']:<14} "
              f"vznik {r['created_at']} oznaceno {r['test_marked_at']}")

    if dry:
        print("\n--dry-run: nic se nemaze, konec.")
        return 0

    # --- ZALOHA JAKO DOKONCENY KROK, mimo mazaci transakci ---
    conn = _conn()
    try:
        with conn.cursor() as cur:
            data = posbirej_zalohu(cur, ids)
    finally:
        conn.close()
    cesta, velikost = zapis_zalohu(data)
    print(f"\nZaloha hotova PRED mazanim: {cesta} ({velikost} B, "
          f"{sum(len(v) for v in data['tabulky'].values())} radku)")

    conn = _conn()
    try:
        with conn.cursor() as cur:
            prehled, po_item_ids = smaz(cur, ids)
        conn.commit()
    finally:
        conn.close()

    # Stejny douklid galerie po commitu, jaky dela admin endpoint
    if po_item_ids:
        import gallery_items
        for iid in po_item_ids:
            gallery_items.delete_items_for_owner("po_item", iid)

    print("\nSmazano (bod 28 - logujeme CO, ne jen kolik):")
    for o in prehled["objednavky"]:
        print(f"  objednavka: {o}")
    for d in prehled["dokumenty"]:
        print(f"  doklad: {d}")
    if po_item_ids:
        print(f"  polozky navazanych nakupnich objednavek: {po_item_ids}")
    print(f"  celkem smazanych objednavek: {prehled['smazano_objednavek']}")

    # --- kontrola cerstvym spojenim ---
    conn = _conn()
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT COUNT(*) n FROM shop_orders WHERE id IN ({fmt})", ids)
            zbylo = cur.fetchone()["n"]
            cur.execute(f"SELECT COUNT(*) n FROM shop_documents WHERE order_id IN ({fmt})", ids)
            zbylo_dokladu = cur.fetchone()["n"]
    finally:
        conn.close()
    print(f"\nKontrola cerstvym spojenim: zbylo objednavek {zbylo}, dokladu {zbylo_dokladu} "
          f"(oboji musi byt 0)")
    return 0 if (zbylo == 0 and zbylo_dokladu == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
