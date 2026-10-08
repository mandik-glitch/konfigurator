#!/opt/konfigurator/api/venv/bin/python
"""Dealersky program, cesta (b) (bot5, 2026-10-02): NEUTRALNI DODACI LIST u dealerskych objednavek - api/documents.py (create_delivery_note + render_document_pdf).

Robert: zbozi jde KONCOVEMU ZAKAZNIKOVI dealera, dodaci list v baliku proto nesmi mit ceny ani nasi znacku (Logiman) ani udaje dodavatele. Odesilatel je dealer (jeho udaje jsou uz
v recipient snapshotu, fakturace objednavky je na nej), prijemce je adresa doruceni, v meta je cislo objednavky dealera (external_ref). Bezny dodaci list (cesta 'our' / bez dealera)
se NESMI zmenit (otisk vykresleneho textu pred a po opravou je shodny).

Test pouziva jen DOCASNE tabulky (shop_documents, shop_document_sequences, shop_stock_movements); skutecna funkce create_delivery_note a render_document_pdf.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_dealeri_testy/test_dodaci_list_dealer.py       (kandidat: --setenv=DOCUMENTS_PY=/cesta/documents.py)
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
if os.environ.get("DOCUMENTS_PY"):
    tmp = tempfile.mkdtemp(prefix="kand_documents_")
    shutil.copy(os.environ["DOCUMENTS_PY"], os.path.join(tmp, "documents.py"))
    sys.path.insert(0, tmp)
sys.path.insert(1 if os.environ.get("DOCUMENTS_PY") else 0, os.path.join(REPO, "api"))

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import documents  # noqa: E402
from reportlab.platypus import Paragraph, Table  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))


def ostre_stav():
    c = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                        port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    try:
        with c.cursor() as cur:
            out = {}
            for t in ("shop_documents", "shop_stock_movements"):
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            cur.execute("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_document_sequences")
            out["seq_dok"] = int(cur.fetchone()["s"])
            return out
    finally:
        c.close()


PRED = ostre_stav()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
CAPTURED = []


def texty(flow):
    out = []
    for f in flow:
        if isinstance(f, Paragraph):
            out.append(f.getPlainText())
        elif isinstance(f, Table):
            for row in f._cellvalues:
                for cell in row:
                    out.append(cell.getPlainText() if isinstance(cell, Paragraph) else str(cell))
    return out


class Zaznam(documents.SimpleDocTemplate):
    def build(self, flowables, *a, **k):
        CAPTURED.append(texty(flowables))        # texty PRED stavbou (reportlab pri build() tabulky deli)
        return super().build(flowables, *a, **k)


documents.SimpleDocTemplate = Zaznam

try:
    with real.cursor() as cur:
        for t in ("shop_document_sequences",):
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"INSERT INTO `_tpl_{t}` SELECT * FROM `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"INSERT INTO `{t}` SELECT * FROM `_tpl_{t}`")
        for t in ("shop_documents", "shop_stock_movements"):
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
        for t in ("shop_document_sequences", "shop_documents", "shop_stock_movements"):
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
    real.commit()

    def objednavka(path, ref=None, cislo="OBJ-2026-90001"):
        return {"id": 90001 if path == "dealer" else 90002, "order_number": cislo, "order_path": path, "dealer_external_ref": ref,
                "billing_name": "Alfa s.r.o.", "billing_ico": "11111111", "billing_dic": "CZ11111111", "billing_address": "Dealerská 1, 602 00 Brno",
                "customer_name": "Alfa s.r.o.", "customer_email": "objednavky@alfa.example", "customer_phone": "+420 111 222 333",
                "delivery_address": "Jan Novák, Ulice 5, 110 00 Praha, tel. +420 777 123 456"}

    ITEMS = [{"product_id": 91001, "product_name_snapshot": "Spojka L 30", "product_unit": "ks", "product_is_profile_material": 0},
             {"product_id": 91002, "product_name_snapshot": "Profil 30x30 (3 m)", "product_unit": "ks", "product_is_profile_material": 1}]

    def vystav(o, items=ITEMS):
        with real.cursor() as cur:
            cur.execute("INSERT INTO shop_stock_movements (product_id, movement_type, qty, document_number) VALUES (%s,'issue',4,%s),(%s,'issue',2,%s)",
                        (items[0]["product_id"], o["order_number"], items[1]["product_id"], o["order_number"]))
            res = documents.create_delivery_note(cur, o, items, "Jana Skladová")
            cur.execute("SELECT * FROM shop_documents WHERE id=%s", (res["id"],))
            doc = cur.fetchone()
        real.commit()
        return res, doc

    def vykresli(doc):
        CAPTURED.clear()
        pdf = documents.render_document_pdf(doc)
        return pdf, "\n".join(CAPTURED[-1])

    print("== A dodaci list dealerske objednavky (cesta 'dealer')")
    o_d = objednavka("dealer", "ESHOP-10234")
    res_d, doc_d = vystav(o_d)
    rec = json.loads(doc_d["recipient_snapshot"])
    over("A1 doklad vznikne s cislem rady dodacich listu a snapshot nese priznak neutral_delivery, odesilatele (dealer: fakturace objednavky) a cislo objednavky dealera",
         res_d["document_number"].startswith("DL") and rec.get("neutral_delivery") is True and rec["name"] == "Alfa s.r.o." and rec["ico"] == "11111111" and rec.get("reference") == "ESHOP-10234" and doc_d["note"] == "Obsah zásilky:", (rec, doc_d["note"]))
    pdf_d, tx_d = vykresli(doc_d)
    over("A2 PDF se vygeneruje a neobsahuje obrazek", pdf_d[:4] == b"%PDF" and b"/Subtype /Image" not in pdf_d, None)
    sup = documents.SUPPLIER
    nase = [sup["name"], sup["street"], sup["city"], sup["ico"], sup["dic"], sup["phone"], sup["email"], sup["web"], sup["bank_account"]]
    nalez = [x for x in nase if x and x.lower() in tx_d.lower()]
    over("A3 ZADNY nas udaj ani znacka: ani nazev firmy, ulice, mesto, IC, DIC, telefon, e-mail, web, ucet dodavatele, ani 'logiman', 'konfigurator', 'Vystavil', 'Dodavatel'",
         not nalez and not re.search(r"logiman|konfigur|vystavil|dodavatel", tx_d, re.I), (nalez, tx_d[:300]))
    over("A4 zadne ceny, DPH ani platebni udaje: bez 'Kc', 'Cena', 'DPH', 'Variabilni symbol', 'Forma uhrady', 'K ZAPLACENI', 'Soucet'",
         not re.search(r"Kč|Cena|DPH|Variabilní symbol|Forma úhrady|ZAPLACEN|Součet|Shrnutí", tx_d), tx_d[:300])
    over("A5 odesilatel = dealer (nazev, adresa, IC, DIC, telefon, e-mail), prijemce = adresa doruceni koncoveho zakaznika (jmeno, ulice, PSC mesto, telefon), cislo objednavky dealera, data",
         all(x in tx_d for x in ("Odesílatel:", "Alfa s.r.o.", "Dealerská 1", "602 00 Brno", "IČ: 11111111", "DIČ: CZ11111111", "Tel: +420 111 222 333", "E-mail: objednavky@alfa.example",
                                 "Příjemce:", "Jan Novák", "Ulice 5", "110 00 Praha", "tel. +420 777 123 456", "Číslo objednávky: ESHOP-10234", "Datum vystavení:", "Datum dodání:")), tx_d[:600])
    over("A6 polozky a mnozstvi ze skladovych vydejek (Spojka 4 ks, Profil 2 ks (3 m)), nadpis 'Dodaci list c. DL...' bez nazvu firmy", "Spojka L 30" in tx_d and "Profil 30x30 (3 m)" in tx_d and re.search(r"Dodací list č\. DL\d+", tx_d) and "4" in tx_d and "Obsah zásilky:" in tx_d, tx_d[-400:])
    over("A7 podpisovy blok (Vydal / Prevzal(a)) zustava", "Vydal:" in tx_d and "Převzal(a):" in tx_d, tx_d[-300:])

    print("== B bezny dodaci list (cesta 'our' nebo bez dealera) se nezmenil")
    for path in ("our", None):
        o_n = objednavka(path, None, cislo=f"OBJ-2026-9100{'1' if path else '2'}")
        o_n["id"] = 90100 + (1 if path else 2)
        res_n, doc_n = vystav(o_n)
        rec_n = json.loads(doc_n["recipient_snapshot"])
        pdf_n, tx_n = vykresli(doc_n)
        over(f"B1 order_path={path!r}: snapshot BEZ neutral_delivery, poznamka puvodni, PDF ma dodavatele, znacku a 'Vystavil'", "neutral_delivery" not in rec_n and doc_n["note"] == "Vyskladněno dle výdejek k objednávce:"
             and sup["name"] in tx_n and "Dodavatel:" in tx_n and "Doručovací adresa:" in tx_n and "Vystavil: Jana Skladová" in tx_n and "logiman.cz" in tx_n and "Odesílatel:" not in tx_n, tx_n[:300])
    FIN = hashlib.sha256(tx_n.encode("utf-8")).hexdigest()[:16]
    print("OTISK_BEZNEHO_DODACIHO_LISTU", FIN)

    print("== C bezpecnost: hostilni text v neutralnim dodacim listu")
    o_h = objednavka("dealer", "REF-<x>", cislo="OBJ-2026-90003")
    o_h["id"] = 90003
    o_h["delivery_address"] = f"<img src='{os.path.join(REPO, 'webapp', 'capture-icon-192.png')}'/> Jan <Novák> & syn, Ulice 5, 110 00 Praha, tel. +420 777 123 456"
    o_h["billing_name"] = "R&D <font color='red'>Alfa</font>"
    res_h, doc_h = vystav(o_h)
    pdf_h, tx_h = vykresli(doc_h)
    over("C1 neutralni dodaci list s hostilnimi texty: PDF vznikne, zadny obrazek, texty doslova (<img>, <font>, R&D, Jan <Novák>)", pdf_h[:4] == b"%PDF" and b"/Subtype /Image" not in pdf_h and "<img src=" in tx_h and "Jan <Novák>" in tx_h and "R&D <font color='red'>Alfa</font>" in tx_h, tx_h[:300])

    print("== D mutace a staticke kontroly")
    zdroj = open(documents.__file__, encoding="utf-8").read()
    over("D1 priznak neutral_delivery se nastavuje jen pro order_path == 'dealer' a PDF se meni jen s priznakem (nic jineho nepouziva)",
         zdroj.count('order.get("order_path") == "dealer"') == 1 and zdroj.count("neutral_delivery") >= 2 and zdroj.count("neutral = doc_type") == 1, zdroj.count("neutral_delivery"))
    real_create = documents.create_delivery_note

    def bez_priznaku(cur, order, order_items, issued_by_label):
        return real_create(cur, {**order, "order_path": None}, order_items, issued_by_label)

    o_m = objednavka("dealer", "REF-M", cislo="OBJ-2026-90004")
    o_m["id"] = 90004
    with real.cursor() as cur:
        cur.execute("INSERT INTO shop_stock_movements (product_id, movement_type, qty, document_number) VALUES (%s,'issue',1,%s)", (ITEMS[0]["product_id"], o_m["order_number"]))
        res_m = bez_priznaku(cur, o_m, ITEMS, "x")
        cur.execute("SELECT * FROM shop_documents WHERE id=%s", (res_m["id"],))
        doc_m = cur.fetchone()
    real.commit()
    pdf_m, tx_m = vykresli(doc_m)
    over("M1 mutace: kdyby se priznak neutral_delivery nenastavil, dodaci list dealerske objednavky by nesl nasi znacku, dodavatele a 'Vystavil' (testy A3 a A5 ji zachytí)", sup["name"] in tx_m and "Vystavil" in tx_m and "Odesílatel:" not in tx_m, tx_m[:200])
finally:
    with real.cursor() as cur:
        for t in ("shop_document_sequences", "shop_documents", "shop_stock_movements", "_tpl_shop_document_sequences", "_tpl_shop_documents", "_tpl_shop_stock_movements"):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
    real.commit()

PO = ostre_stav()
over("ostre tabulky (doklady, skladove pohyby, citace dokladu) jsou po testu beze zmeny", PO == PRED, (PRED, PO))
ok = sum(vysl)
print(f"\nVYSLEDEK neutralni dodaci list dealera: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
