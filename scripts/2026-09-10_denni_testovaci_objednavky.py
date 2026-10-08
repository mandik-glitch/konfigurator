#!/usr/bin/env python3
"""Denni testovaci objednavky (2/den) - WORKFLOW.md bod 27.

Robert 2026-09-10: "nech delat test, kazdy den 2 objednavky pro testovani
stavu a pruchodnosti systemem" + "cely tok vcetne faktury a danoveho
dokladu".

REALNA CESTA KODEM, ne prime INSERTy: pouzivaji se TYTEZ funkce, ktere
vola admin z UI -
  orders._resolve_and_insert_order()   zalozeni objednavky
  orders._system_confirm_or_wait()     potvrzeni + odpis skladu
  documents.create_proforma_invoice()  zalohova faktura
  documents.create_payment_tax_document()  VDD (danovy doklad k platbe)
  documents.create_invoice()           faktura
Tim se opravdu overi pruchodnost, ne jen ze jde zapsat radek.

=== PROC SE NEPOSILA ZADNY E-MAIL (vedoma mezera, bot3 2026-09-10) ===
`_auto_email_after_issue()` je az v ENDPOINTECH documents.py, ne uvnitr
`create_*()`; a `_send_order_emails_bg()` je az v endpointu orders.py.
Tenhle skript vola jen ta jadra, takze nevznikne ani jeden `pending`
radek v `shop_emails` - schvalovaci fronta zustane cista.
DUSLEDEK, KTERY MUSI BYT VIDET: denni test tim padem NEOVERUJE cestu
e-mailu. Kdyby se rozbilo zarazovani do schvalovaci fronty, tenhle test
to NECHYTI. Je to vedoma cena za nezaplevelenou frontu (bod 16 zakazuje
automaticke odesilani, takze denne by se hromadily desitky cekajicich
e-mailu, ktere by stejne nikdo neschvaloval).

=== POJISTKY (WORKFLOW.md bod 28) ===
1. IDEMPOTENCE NA DEN - druhy beh teze dne nevyrobi dalsi davku.
2. STROP NA SKLAD - kdyz na testovacim produktu nedostava kusu, NIC se
   nezaklada a skript skonci chybou. Bez teto pojistky by objednavka
   spadla do `ceka_na_zbozi` a zacala by DENNE zakladat objednavky u
   dodavatele (_autocreate_supplier_orders) - presne ten sum, kteremu se
   vyhybame.
3. Kazdy beh (i "dnesni davka uz existuje") pise na stdout -> journald.
   Problem = nenulovy exit -> unit ve `systemctl --failed`.
4. Na konci kontrola CERSTVYM spojenim, co v DB opravdu vzniklo.

Pojistka proti SOUBEHU je na urovni systemd unitu, ne tady (bod 28: patri
na spousteci vrstvu) - viz deploy/konfigurator-test-orders.service.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402

os.environ.update(_env.load_env())

import app  # noqa: E402,F401 - MUSI byt drive nez orders/documents, jinak kruhovy import
import documents  # noqa: E402
import orders  # noqa: E402

# --- parametry testovaci objednavky ---------------------------------------
POCET_DENNE = 2
# Jediny produkt v katalogu, ktery ma zasobu (315 ks k 2026-09-10); vsechny
# ostatni maji stock_qty=0 a objednavka by spadla do `ceka_na_zbozi`.
PRODUKT_ID = 3045
QTY = 1
# Bod 19: danovy doklad k prijate platbe (VDD) smi vzniknout JEN u platby
# predem. Robert chce "vcetne danoveho dokladu", takze jina metoda nejde.
PAYMENT_METHOD_ID = 1      # Platba predem
SHIPPING_METHOD_ID = 1     # Osobni odber (nevyzaduje dopocet ceny Toptransu)
VYSTAVIL = "Automaticky denni test (WORKFLOW.md bod 27)"


def _telo_objednavky(poradi):
    return {
        "items": [{"product_id": PRODUKT_ID, "qty": QTY}],
        "customer_name": f"TEST pruchodnost systemu {poradi}/{POCET_DENNE}",
        # .local domena zamerne - neexistujici, needoruceni nehrozi ani omylem
        "customer_email": "test-pruchodnost@konfigurator.local",
        "billing_name": "TEST pruchodnost systemu",
        "billing_address": "Testovaci 1, Brno",
        "billing_zip": "60200",
        "delivery_address": "Testovaci 1, Brno",
        "delivery_zip": "60200",
        "payment_method_id": PAYMENT_METHOD_ID,
        "shipping_method_id": SHIPPING_METHOD_ID,
        "note": "Automaticka denni testovaci objednavka (WORKFLOW.md bod 27). "
                "Smaze se 14 dni po oznaceni.",
    }


def _conn():
    return app.get_conn()


def dnesni_davka_existuje():
    """POJISTKA 1 - idempotence na den. Historicky oznacenych 39 objednavek
    tady nevadi: maji `created_at` v minulosti, dnesni datum nesplnuji."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) n FROM shop_orders "
                "WHERE is_test=1 AND DATE(created_at)=CURDATE()"
            )
            return cur.fetchone()["n"]
    finally:
        conn.close()


def volny_sklad():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name, stock_qty FROM shop_products WHERE id=%s", (PRODUKT_ID,))
            return cur.fetchone()
    finally:
        conn.close()


def zaloz_objednavku(poradi):
    """Zalozi objednavku pres sdilene jadro + oznaci ji jako testovaci
    JESTE VE STEJNE TRANSAKCI (aby nikdy nevznikla neoznacena)."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            result = orders._resolve_and_insert_order(
                cur, _telo_objednavky(poradi), attribute_user_id=None, profile_user_id=None
            )
            cur.execute(
                "UPDATE shop_orders SET is_test=1, test_marked_at=NOW() WHERE id=%s",
                (result["order_id"],),
            )
            cur.execute(
                "INSERT INTO shop_order_status_history (order_id, status, changed_by, note) "
                "VALUES (%s, 'nova', NULL, %s)",
                (result["order_id"], "Automaticka denni testovaci objednavka (WORKFLOW.md bod 27)."),
            )
        conn.commit()
        return result
    finally:
        conn.close()


def potvrd(order_id):
    """Potvrzeni = odpis skladu. Stejna cesta jako auto-potvrzeni v appce."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_orders WHERE id=%s FOR UPDATE", (order_id,))
            order = cur.fetchone()
            stav = orders._system_confirm_or_wait(cur, order)
        conn.commit()
        return stav
    finally:
        conn.close()


def vystav_doklady(order_id):
    """Zalohova faktura -> VDD (danovy doklad k prijate platbe) -> faktura.
    ZADNY e-mail (viz hlavicka souboru)."""
    conn = _conn()
    vysledek = {}
    try:
        with conn.cursor() as cur:
            order = documents._fetch_order(cur, order_id)
            polozky = documents._fetch_order_items(cur, order_id)

            proforma = documents.create_proforma_invoice(cur, order, polozky, VYSTAVIL)
            vysledek["proforma"] = proforma["document_number"]

            cur.execute(
                "SELECT * FROM shop_documents WHERE id=%s", (proforma["id"],)
            )
            proforma_row = cur.fetchone()

            castka = documents._money(order["total_czk"]) or 0.0
            vdd = documents.create_payment_tax_document(
                cur, order, proforma_row, castka, datetime.now().date(), VYSTAVIL
            )
            vysledek["vdd"] = vdd["document_number"]
            # stejny dopocet jako admin_documents_mark_payment_received()
            prijato = documents._round2(
                (documents._money(order["payment_received_total_czk"]) or 0.0) + castka
            )
            cur.execute(
                "UPDATE shop_orders SET payment_received_at=%s, payment_received_total_czk=%s "
                "WHERE id=%s",
                (datetime.now(), prijato, order_id),
            )

            order = documents._fetch_order(cur, order_id)
            faktura = documents.create_invoice(cur, order, polozky, proforma_row, VYSTAVIL)
            vysledek["faktura"] = faktura["document_number"]
        conn.commit()
        return vysledek
    finally:
        conn.close()


def kontrola_po_behu(ids):
    """POJISTKA 4 - cerstve spojeni, at se necteme z vlastni transakce."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(ids))
            cur.execute(
                f"SELECT id, order_number, status, is_test, total_czk FROM shop_orders "
                f"WHERE id IN ({fmt}) ORDER BY id", ids)
            for r in cur.fetchall():
                print(f"  objednavka #{r['id']} {r['order_number']} stav={r['status']} "
                      f"is_test={r['is_test']} celkem={r['total_czk']}")
            cur.execute(
                f"SELECT order_id, document_type, document_number FROM shop_documents "
                f"WHERE order_id IN ({fmt}) ORDER BY order_id, id", ids)
            for r in cur.fetchall():
                print(f"  doklad k #{r['order_id']}: {r['document_type']:<22} {r['document_number']}")
            cur.execute("SELECT stock_qty FROM shop_products WHERE id=%s", (PRODUKT_ID,))
            print(f"  sklad produktu {PRODUKT_ID} po behu: {cur.fetchone()['stock_qty']} ks")
            cur.execute(
                f"SELECT COUNT(*) n FROM shop_emails WHERE order_id IN ({fmt})", ids)
            n = cur.fetchone()["n"]
            print(f"  e-maily k temto objednavkam: {n} (musi byt 0 - viz hlavicka souboru)")
            return n
    finally:
        conn.close()


def main():
    ted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    uz = dnesni_davka_existuje()
    if uz:
        print(f"[{ted}] Dnesni davka uz existuje ({uz} testovacich objednavek s dnesnim datem) "
              f"- NEDELAM NIC (idempotence, WORKFLOW.md bod 28).")
        return 0

    produkt = volny_sklad()
    potreba = POCET_DENNE * QTY
    if not produkt:
        print(f"[{ted}] CHYBA: testovaci produkt id={PRODUKT_ID} neexistuje.", file=sys.stderr)
        return 1
    if (produkt["stock_qty"] or 0) < potreba:
        print(f"[{ted}] CHYBA: nedostatek skladu na testovacim produktu "
              f"{PRODUKT_ID} ({produkt['name']}): skladem {produkt['stock_qty']}, "
              f"potreba {potreba}. NEZAKLADAM NIC - objednavka by spadla do "
              f"'ceka_na_zbozi' a zacala denne zakladat objednavky u dodavatele.",
              file=sys.stderr)
        return 1

    print(f"[{ted}] Zakladam {POCET_DENNE} testovaci objednavky "
          f"(produkt {PRODUKT_ID} '{produkt['name']}', skladem {produkt['stock_qty']} ks).")

    ids = []
    for i in range(1, POCET_DENNE + 1):
        vysl = zaloz_objednavku(i)
        ids.append(vysl["order_id"])
        print(f"  [{i}/{POCET_DENNE}] zalozena #{vysl['order_id']} {vysl['order_number']} "
              f"celkem {vysl['total']} Kc")

        stav = potvrd(vysl["order_id"])
        print(f"      potvrzeni -> {stav}")
        if stav != "potvrzena":
            print(f"      CHYBA: ocekaval jsem 'potvrzena', doslo k '{stav}'. "
                  f"Doklady nevystavuji.", file=sys.stderr)
            continue

        doklady = vystav_doklady(vysl["order_id"])
        print(f"      doklady: zalohova {doklady['proforma']}, VDD {doklady['vdd']}, "
              f"faktura {doklady['faktura']}")

    print("\nKontrola cerstvym spojenim:")
    pocet_emailu = kontrola_po_behu(ids)
    if pocet_emailu:
        print("CHYBA: vznikly e-mailove zaznamy, ackoli nemely.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
