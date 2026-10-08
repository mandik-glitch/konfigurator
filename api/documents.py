"""
Doklady (zalohova faktura, danovy doklad k prijate platbe, faktura) -
bot3, 2026-07-25 (v6).

Kontext: Robert dodal 4 vzorove doklady puvodne ze Shoptet.cz (vzorova
objednavka.pdf, proformaInvoice_26080012.pdf, invoice_26010042.pdf,
proofPayment_vdd26080018-01.pdf) a chce mit v systemu zavedene vsechny
jejich pole/promenne, ve dvou workflow:

  WORKFLOW1 (platba prevodem predem): objednavka -> zalohova faktura ->
    danovy doklad k prijate platbe (VDD) -> konecna faktura (odecte zalohu)
  WORKFLOW2 (dobirka / karta): objednavka -> rovnou faktura

Rozhodnuti Roberta (AskUserQuestion, 2026-07-25):
  - rozsah: datovy model + PDF generovani (moje volba - "bez preference")
  - workflow se urcuje AUTOMATICKY podle zvolene platebni metody objednavky
    (shop_payment_methods.requires_advance_invoice)
  - cislovani novych dokladu stylem Shoptet RRMMxxxx (samostatna rada na
    kazdy typ dokladu, pocitadlo bezi cely rok, MM = mesic vystaveni)
  - ceny v e-shopu (shop_products, doprava, platba) jsou BEZ DPH -> na
    dokladech se pripocitava DPH navic (VAT_RATE = 21 %, jedina sazba ve
    vsech vzorech - system nema koncept snizene sazby)

Co je AUTOMATICKE a co vyzaduje klik admina (zamerne, aby se na produkci
nevystavovaly danove doklady se spatnym datem bez vedomi Roberta):
  - Zalohova faktura: vystavi se AUTOMATICKY hned pri vytvoreni objednavky,
    pokud zvolena platebni metoda ma requires_advance_invoice=1 (zakaznik
    ji potrebuje hned, aby mohl zaplatit - viz create_proforma_invoice_if_needed(),
    volano z orders.py::_resolve_and_insert_order).
  - Danovy doklad k prijate platbe (VDD): NIKDY automaticky - admin musi
    rucne potvrdit prijeti platby (POST .../documents/payment-received).
    Lze zavolat vicekrat (castecne platby) - kazde volani = 1 VDD s
    rostoucim part_number (-01, -02, ...).
  - Faktura: NIKDY automaticky - admin rucne vystavi (POST .../documents/invoice),
    typicky pri expedici/dokonceni objednavky. Pokud k objednavce existuje
    zalohova faktura, castka jiz uhrazene zalohy se odecte a K ZAPLACENI
    vyjde 0 Kc (nebo zbytek, pokud faktura vysla vyssi nez zaloha).

Objednavka sama (prvni krok obou workflow) NENI novy typ dokladu - jeji
udaje uz existuji v shop_orders/shop_order_items a jsou dostupne pres
GET /api/orders/<id> resp. /api/admin/orders/<id> (orders.py). Tisknuty
PDF export samotne objednavky ZDE NENI reseny (jen 3 nove typy: zalohova
faktura, VDD, faktura) - lze doplnit pozdeji, pokud bude potreba.

Znama omezeni v1 (vedome, kvuli rozsahu existujiciho datoveho modelu):
  - Kod polozky ("Kód: 2.1.012.08.01" ve vzorech) se netiskne - shop_order_items
    zatim neuklada kod produktu, jen nazev (product_name_snapshot).
  - Jedina sazba DPH (21 %) - system nema pole pro ruznou sazbu na produktu.
  - Udaje dodavatele (LOGIMAN s.r.o.) jsou HARDCODED nize (SUPPLIER) - zmena
    (napr. cislo uctu) vyzaduje upravu kodu + redeploy, ne DB/admin UI.
  - Variabilni symbol = primo shop_orders.id (order_number ve tvaru
    "OBJ-2026-00042" neni ciselny, nelze pouzit jako VS).

Aktivace: `import documents` na konec app.py (AZ PO `import orders`, viz
orders.py pro presny import poradek a duvod - stejna konvence jako
cart.py/customers.py). Vyzaduje migraci sql/2026-07-25_documents.sql
(nova tabulka shop_documents, shop_document_sequences, nove sloupce na
shop_orders a shop_payment_methods) - MUSI byt spustena PRED restartem se
zapnutym timhle modulem.
"""
import json
import os
import re
from datetime import datetime, timedelta

from flask import request, jsonify, Response

from app import (
    app, get_conn, login_required, require_permission, current_user, log_audit,
    get_pagination_args, paginated_query, parse_bulk_ids, bulk_delete,
)
from products import reverse_and_delete_stock_movements

# V9 (bot3, 2026-07-25): top-level import (NE lazy uvnitr funkce) - stejny
# duvod jako `import documents`/`import emails` v orders.py (viz jeho
# komentar): puvodne tu byl lazy `import emails` uvnitr
# _auto_email_after_issue(), coz selhavalo v testech, ktere neimportuji
# `orders` (pripadne importuji jen `documents`+`purchase_orders`) DRIV nez
# poprve vystavi doklad - `emails` se pak poprve importoval AZ za behu
# requestu, po tom, co uz Flask obslouzil prvni request (stejny limit jako
# u puvodniho bugu s `import documents`). NENI to cyklicky problem: emails.py
# sice take importuje `documents` zpet, ale ani jeden modul nesaha na
# atributy toho druheho na urovni modulu (jen uvnitr telech funkci, ktere
# se volaji az za behu, kdy uz jsou oba moduly plne nactene).
import emails  # noqa: E402

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape as _xml_escape


# bot5, 2026-10-02 (nalez pri dealerskych objednavkach, zadani bot3 "oprav, vysoka priorita"): reportlab Paragraph PARSUJE ZNACKY. Text z objednavky
# (jmeno, adresa, nazev polozky, poznamka - zadava je zakaznik/dealer) se do nej vkladal bez escapovani, takze `<img src='/cesta/k/souboru.png'/>`
# vlozilo do PDF libovolny cteny obrazek ze serveru (lokalni cesty reportlab NEOMEZUJE; http(s) se vychozim nastavenim nestahuje), neplatna znacka
# shodila generovani PDF (500) a `R&D` se tisklo jako `R&D;`. Oprava ve DVOU vrstvach:
#   1) _esc() - vsechen dynamicky text se escapuje PRED vlozenim do Paragraph (adresa: nejdriv escape, az pak <br/>),
#   2) _P() - pojistka: do Paragraph projdou jen znacky b/i/u/br, kazde jine `<` se zmeni na `&lt;` (kdyby nekdo pri budouci uprave zapomnel na _esc).
_ALLOWED_MARKUP_RE = re.compile(r"<(?!/?(?:b|i|u|br)\s*/?>)", re.I)


def _esc(value):
    """Text z dat -> bezpecny text pro Paragraph (&, <, > escapovane, None = prazdny retezec)."""
    return _xml_escape("" if value is None else str(value))


def _P(markup, style):
    """Paragraph, do ktereho projdou jen nase znacky <b>, <i>, <u>, <br/>; jakekoli jine `<` (img, font, a, link...) se zmeni na `&lt;`."""
    return Paragraph(_ALLOWED_MARKUP_RE.sub("&lt;", markup), style)


# Zakladni PDF fonty (Helvetica) v ReportLabu podporuji jen WinAnsi/Latin-1
# kodovani a NEUMI vsechny ceske znaky s diakritikou (napr. č/ř/š/ž/ď/ť se
# tisknou spatne). Pokud je na serveru dostupny DejaVu Sans (bezny balicek
# fonts-dejavu-core, overeno ze je na produkcnim serveru i v sandboxu),
# pouzijeme ho misto Helvetiky - jinak (fallback) zustane Helvetica a
# diakritika bude poskozena, ale PDF se aspon vygeneruje.
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
_DEJAVU_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if os.path.exists(_DEJAVU_REGULAR) and os.path.exists(_DEJAVU_BOLD):
    try:
        pdfmetrics.registerFont(TTFont("DejaVuSans", _DEJAVU_REGULAR))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", _DEJAVU_BOLD))
        FONT_REGULAR = "DejaVuSans"
        FONT_BOLD = "DejaVuSans-Bold"
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Staticka konfigurace
# ---------------------------------------------------------------------------

VAT_RATE = 21  # % - jedina sazba pouzita ve vsech vzorovych dokladech

# bot5, 2026-10-03 (Robert pres bot3: zakaznik z jineho clenskeho statu s PLATNYM IC DPH = DPH se neuctuje, na dokladu dolozka): objednavka z mini-shopu nese shop_orders.vat_mode
# ('reverse_charge' = 0 %, jinak/NULL = CZ sazba beze zmeny). Sazbu a doplnujici text dokladu urcuji jen tyhle dve funkce, zadne jine misto sazbu pro objednavku nerozhoduje.
# POZOR (otevreny bod pro ucetni): zneni dolozky VAT_ZERO_NOTE je navrh, ucetni ho potvrdi/upravi.
PODPORA_PRENESENE_DPH = True
VAT_ZERO_NOTE = "Osvobozené plnění – dodání zboží do jiného členského státu (§ 64 zákona č. 235/2004 Sb., o DPH). IČ DPH odběratele: {dic}."


def _order_vat_rate(order):
    return 0 if (order or {}).get("vat_mode") == "reverse_charge" else VAT_RATE


def _order_doc_note(order, base):
    """Poznamka dokladu = zakladni text + (u DPH 0 %) dolozka s IC DPH odberatele + (je-li) text k prepoctu meny z objednavky (order['document_note'], jen mini-shop). Jeden odstavec."""
    parts = [base]
    if (order or {}).get("vat_mode") == "reverse_charge":
        parts.append(VAT_ZERO_NOTE.format(dic=(order.get("billing_dic") or "").strip() or "-"))
    if (order or {}).get("document_note"):
        parts.append(str(order["document_note"]))
    return " ".join(p for p in parts if p)

# Menovy kod pro SPAYD/IBAN QR platbu (viz _build_spayd() nize) - bot16
# nalez 2026-09-17 (pres bot3): byl natvrdo "CC:CZK" nezavisle na 2
# mistech (tady + api/scene_offers.py::_build_spayd, ktera VLASTNI kopii
# funkce ma zamerne - viz komentar u _cz_account_to_iban nize - ale
# VAT_RATE/SUPPLIER uz odsud IMPORTUJE, takze jeden spolecny zdroj i pro
# tenhle konstantu nic nemeni na te zamerne nezavislosti funkci).
SPAYD_CURRENCY_CODE = "CZK"

SUPPLIER = {
    "name": "LOGIMAN s.r.o.",
    "street": "Husinecká 903/10",
    "city": "13000 Praha",
    "country": "Česká republika",
    "ico": "28337638",
    "dic": "CZ28337638",
    "phone": "+420 603 230 059",
    "email": "mandik@logiman.cz",
    "web": "https://www.logiman.cz",
    "bank_account": "2100198113/2010",
}


# QR Platba (Robert 2026-09-07, pres bot3: "QR platbu na misto platby
# kartou" - "Kartou online" byl nefunkcni popisek bez navaznosti na
# platebni branu, kterou projekt nema; cesky standard "QR Platba" funguje
# bez ni - jen bankovni prevod zakodovany do QR kodu). Stejny cisty
# vypocet (ISO 13616 mod-97-10, zadna sit) jako uz zavedeny vzor v
# api/scene_offers.py::_cz_account_to_iban/_build_spayd (verejne nabidky
# ze sceny) - zamerne DUPLIKOVANO sem, ne importovano odtud, aby
# orders.py/documents.py nemusely tahat zavislost na scene_offers.py
# (jina domenova oblast).
def _cz_account_to_iban(local_account):
    """'2100198113/2010' (pripadne s predcislim '19-2000145399/0800')
    -> 'CZ..' IBAN. Cisty vypocet, zadna sit."""
    acct_part, bank_code = local_account.split("/")
    prefix, _, number = acct_part.rpartition("-")
    bban = bank_code.zfill(4) + prefix.zfill(6) + number.zfill(10)
    numeric = "".join(str(int(c, 36)) if c.isalpha() else c for c in bban + "CZ00")
    return f"CZ{98 - int(numeric) % 97:02d}{bban}"


def _build_spayd(iban, amount, vs, message=""):
    parts = [f"ACC:{iban}", f"AM:{amount:.2f}", f"CC:{SPAYD_CURRENCY_CODE}"]
    if vs:
        parts.append(f"X-VS:{vs}")
    if message:
        parts.append("MSG:" + message.replace("*", " ")[:60])
    return "SPD*1.0*" + "*".join(parts)

DOCUMENT_TYPES = ("proforma_invoice", "payment_tax_document", "invoice", "delivery_note", "credit_note")

DOCUMENT_TYPE_LABELS = {
    "proforma_invoice": "Zálohová faktura",
    "payment_tax_document": "Daňový doklad k přijaté platbě",
    "invoice": "Faktura - Daňový doklad",
    "delivery_note": "Dodací list",
    "credit_note": "Dobropis",
}

AUTO_EMAIL_DOCUMENT_TYPES = ("proforma_invoice", "payment_tax_document", "invoice", "delivery_note")      # typy, ke kterym se zakaznikovi automaticky zarazuje e-mail s PDF (dobropis ne)

DUE_DAYS = 7  # splatnost - 7 dni od vystaveni, stejne jako oba vzory (proforma i faktura)



# ---------------------------------------------------------------------------
# Pomocne funkce - cisla, castky, snapshoty
# ---------------------------------------------------------------------------

def _round2(v):
    return round(float(v) + 1e-9, 2)


def _money(v):
    return float(v) if v is not None else None


def _dt(v):
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _next_document_number(cur, document_type, issue_dt):
    """Samostatne pocitadlo pro kazdy typ dokladu, bezici cely rok
    (seq_year particionuje FOR UPDATE zamek pocitadla, stejna konvence
    jako sklad v orders.py).

    Prefix (bot10, 2026-08-22, admin-editovatelny sloupec
    `shop_document_sequences.prefix`, viz "Nastavení číselné řady
    dokladů" v adminu, PUT /api/admin/document-sequences/<document_
    type>) - Novy rok bez vlastniho radku zdedi prefix z nejnovejsiho
    existujiciho radku stejneho typu (prefix je vlastnost TYPU
    dokladu, ne konkretniho roku).

    Format `display_number` (bot5, 2026-09-28, Robert primo, TRETI a
    FINALNI verze zadani po dvou predchozich pokusech - nejdriv "rok se
    predsazuje automaticky + kod typu", pak "prefix doslovny jen u
    3 novych typu, dodaci list/dobropis stary format", nakonec "kde
    vidis v prefixu 2609????" u dodaciho listu, kdyz ocekaval, ze tam
    bude JEN to, co napsal): VSECHNY typy dokladu STEJNE, ZADNA
    vyjimka - `display_number = prefix (presne tak, jak ho admin zadal)
    + poradi na 5 cislic`. ZADNY rok, mesic ani jiny automaticky
    pridavany kus textu u zadneho typu. Rocni prechod (1.1.) si admin
    musi pohlidat rucnim prepsanim prefixu, system to sam nedela.

    Vraci (display_number, year, seq_number). `display_number` se pouziva
    i jako variable_symbol (bot5, 2026-09-28, Robert primo: "v textu
    dokladu k platbě se musí používat VS včetně prefixů, totéž platí
    pro faktury a ostatní doklady" - PREKONAVA drivejsi "VS musi byt
    ciste ciselny" pravidlo). POZOR: bankovni prevod (SPAYD QR kod u
    zalohove faktury/faktury) potrebuje VS SLOZENY JEN Z CISLIC - pokud
    admin nastavi prefix s pismeny (napr. "VDD") u typu, kde se
    skutecne generuje platebni QR kod (proforma_invoice/invoice), banka
    takovy VS odmitne. U payment_tax_document (VDD, "NEPLAŤTE!") tohle
    nevadi - k nemu se zadny platebni QR kod negeneruje, je to jen
    zpetne potvrzeni jiz prijate platby."""
    year = issue_dt.year
    cur.execute(
        "SELECT next_number, prefix FROM shop_document_sequences WHERE document_type=%s AND seq_year=%s FOR UPDATE",
        (document_type, year),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "SELECT prefix FROM shop_document_sequences WHERE document_type=%s ORDER BY seq_year DESC LIMIT 1",
            (document_type,),
        )
        prev = cur.fetchone()
        prefix = prev["prefix"] if prev else ""
        cur.execute(
            "INSERT INTO shop_document_sequences (document_type, seq_year, next_number, prefix) VALUES (%s,%s,2,%s)",
            (document_type, year, prefix),
        )
        seq_number = 1
    else:
        seq_number = row["next_number"]
        prefix = row["prefix"]
        cur.execute(
            "UPDATE shop_document_sequences SET next_number=next_number+1 WHERE document_type=%s AND seq_year=%s",
            (document_type, year),
        )
    display_number = f"{prefix}{seq_number:05d}"
    return display_number, year, seq_number


def _next_part_number(cur, order_id):
    """Poradove cislo VDD dokladu v ramci jedne objednavky (podpora
    castecnych plateb - kazde 'oznacit platbu jako prijatou' = novy VDD s
    rostoucim part_number, viz vzor 'VDD26080018-01')."""
    cur.execute(
        "SELECT COUNT(*) AS n FROM shop_documents WHERE order_id=%s AND document_type='payment_tax_document'",
        (order_id,),
    )
    return cur.fetchone()["n"] + 1


def _build_items_with_vat(order, order_items):
    """Polozky dokladu = polozky objednavky + doprava + platba (presne
    jako ve vzorech - 'Toptrans a balné' a 'Převodem - zálohová faktura'
    jsou tam taky uvedene jako radky). Vsechny ceny v DB jsou BEZ DPH."""
    rows = []
    for oi in order_items:
        rows.append({
            "name": oi["product_name_snapshot"],
            "qty": oi["qty"],
            "unit_price_net": _money(oi["unit_price_czk"]),
            "line_total_net": _money(oi["line_total_czk"]),
            # Robert 2026-08-08 ("uvadejme u ceny profilů, vedle ks také
            # 3m") - profil ("1 ks = 3000mm tyc") dostane v dokladu "(3 m)"
            # vedle "ks", stejne jako na webu - viz _is_profile_order_item.
            "is_profile_unit": _is_profile_order_item(oi),
            "unit": oi.get("product_unit") or "ks",
        })
    if order.get("shipping_method_name"):
        price = _money(order["shipping_price_czk"]) or 0.0
        rows.append({"name": order["shipping_method_name"], "qty": 1,
                      "unit_price_net": price, "line_total_net": price, "is_profile_unit": False, "unit": "ks"})
    if order.get("payment_method_name"):
        price = _money(order["payment_price_czk"]) or 0.0
        rows.append({"name": order["payment_method_name"], "qty": 1,
                      "unit_price_net": price, "line_total_net": price, "is_profile_unit": False, "unit": "ks"})
    rate = _order_vat_rate(order)
    for r in rows:
        r["vat_rate"] = rate
        r["vat_amount"] = _round2(r["line_total_net"] * rate / 100)
        r["line_total_gross"] = _round2(r["line_total_net"] + r["vat_amount"])
    return rows


def _build_items_from_stock_issues(cur, order, order_items):
    """Polozky dodaciho listu = SOUHRN SKUTECNYCH SKLADOVYCH VYDEJEK, ne
    prosta kopie objednanych mnozstvi (Robert, 2026-07-25: 'je to v
    podstatě souhrn výdejek'). Cerpa ze shop_stock_movements, kde
    document_number == order_number (stejny zpusob znaceni jako pouziva
    admin_orders_update_status() pri prechodu nova->potvrzena - viz
    orders.py, movement_type='issue' + pripadne 'receipt' pri naslednem
    zruseni/vraceni na sklad, ktere se tu NETUJI proti sobe, aby dodaci
    list odrazel skutecny aktualni stav vyskladneni). Vraci None, pokud k
    objednavce jeste ZADNA vydejka neexistuje (objednavka jeste nebyla ani
    jednou potvrzena/vyskladnena) - v tom pripade nema smysl dodaci list
    vystavovat (viz kontrola v admin_documents_create_delivery_note)."""
    cur.execute(
        "SELECT product_id, "
        "       SUM(CASE WHEN movement_type='issue' THEN qty "
        "                WHEN movement_type='receipt' THEN -qty ELSE 0 END) AS net_qty "
        "FROM shop_stock_movements WHERE document_number=%s GROUP BY product_id",
        (order["order_number"],),
    )
    # SUM(...) v MySQL/pymysql vraci Decimal (ne int/float) - bez prevodu
    # by pozdejsi json.dumps(items_snapshot) v _insert_document spadl na
    # "TypeError: Object of type Decimal is not JSON serializable" (overeno
    # na produkci - qty je INT sloupec, ale SUM agregace ho i tak vraci
    # jako Decimal). Vsechny mnozstvi jsou vzdy cela cisla (qty INT), proto
    # bezpecny prevod na int().
    net_by_product = {
        r["product_id"]: int(r["net_qty"]) for r in cur.fetchall() if r["net_qty"] and r["net_qty"] > 0
    }
    if not net_by_product:
        return None
    name_by_product = {oi["product_id"]: oi["product_name_snapshot"] for oi in order_items}
    # Robert 2026-08-08 ("uvadejme u ceny profilů, vedle ks také 3m") -
    # per-produkt (ne per-radek, proto bez cut_kind kontroly z
    # _is_profile_order_item - dodaci list uz je souhrn skutecne
    # vyskladnenych kusu, ne jednotlivé radky objednavky).
    profile_by_product = {
        oi["product_id"]: (bool(oi.get("product_is_profile_material")) and not oi.get("product_is_board_material"))
        for oi in order_items
    }
    unit_by_product = {oi["product_id"]: (oi.get("product_unit") or "ks") for oi in order_items}
    return [
        {"name": name_by_product.get(pid, f"Produkt #{pid}"), "qty": qty,
         "is_profile_unit": profile_by_product.get(pid, False),
         "unit": unit_by_product.get(pid, "ks")}
        for pid, qty in net_by_product.items()
    ]


def _totals(items):
    # total_vat = SOUCET jiz zaokrouhlenych radkovych vat_amount (ne
    # prepocet DPH ze souctu zakladu) - zivy nalez z revize kodu (bot3
    # 2026-09-02): kazda polozka na dokladu tiskne SVOJI vat_amount
    # (_build_items_with_vat), takze soucet zaokrouhleni po radcich se
    # muze o ±0,01 Kc lisit od DPH prepocitane az z jednou zaokrouhleneho
    # total_net - dva ruzna cisla DPH na stejnem PDF. Soucet radkovych
    # hodnot zaruci, ze se dokument shoduje sam se sebou.
    total_net = _round2(sum(i["line_total_net"] for i in items))
    total_vat = _round2(sum(i["vat_amount"] for i in items))
    total_gross_exact = _round2(total_net + total_vat)
    total_gross_rounded = round(total_gross_exact)
    rounding = _round2(total_gross_rounded - total_gross_exact)
    return total_net, total_vat, total_gross_exact, total_gross_rounded, rounding


def _recipient_snapshot(order):
    return {
        "name": order.get("billing_name") or order.get("customer_name"),
        "ico": order.get("billing_ico"),
        "dic": order.get("billing_dic"),
        "address": order.get("billing_address"),
        "email": order.get("customer_email"),
        "phone": order.get("customer_phone"),
    }


def _delivery_snapshot(order):
    if order.get("delivery_address"):
        return {"address": order["delivery_address"]}
    return None


def _issued_by_label(admin):
    if admin is None:
        return "Systém (automaticky)"
    return admin.get("name") or admin.get("email") or "Admin"


def _auto_email_after_issue(order_id, document_id):
    """Po uspesnem vystaveni dokladu (zalohova faktura/VDD/faktura/dodaci
    list) AUTOMATICKY posle e-mail s PDF prilohou zakaznikovi (Robert,
    AskUserQuestion 2026-07-25: 'Automaticky u klíčových událostí' - vedle
    rucniho odeslani z adminu, viz api/emails.py, top-level import vyse).
    NIKDY nesmi shodit hlavni response na vystaveni dokladu - pripadne
    selhani (SMTP vypadek apod.) se jen zaloguje v shop_emails jako
    'failed' (viz emails.send_document_email_auto).

    TESTOVACI OBJEDNAVKY (WORKFLOW.md bod 27) tudy neprojdou vubec. Denne
    by 2 objednavky x nekolik dokladu nasypaly nekolik `pending` radku do
    schvalovaci fronty (bod 16 zakazuje automaticke odeslani, takze by tam
    jen lezely a nikdo by je neschvaloval) - v `shop_emails` je dnes za
    celou historii jediny radek, takze by to frontu okamzite zaplevelilo.

    VEDOMA MEZERA, ktera z toho plyne (bot3, 2026-09-10 - at si za pul roku
    nekdo nemysli, ze denni test pokryva i tohle): denni test tim padem
    NEOVERUJE cestu e-mailu. Kdyby se rozbilo zarazovani do schvalovaci
    fronty, tenhle test to NECHYTI.

    Tahle podminka je pas i sle: generator
    (`scripts/2026-09-10_denni_testovaci_objednavky.py`) vola primo
    `create_*()` jadra, ktera `_auto_email_after_issue()` nevolaji, takze
    v dnesni podobe se sem vubec nedostane. Kdyby ale testovaci objednavka
    nekdy prosla ENDPOINTEM (rucne z adminu, budouci jina cesta), e-mail
    stejne nevznikne.

    NESCHVALENY DOKLAD (Robert 2026-10-08): e-mail se NEZARADI - emails.send_document_email_auto ho vrati jako "not_approved"; zaradi se az po schvaleni dokladu
    (approvals.approve_document znovu zavola tuhle funkci, zarazeni je idempotentni)."""
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT is_test FROM shop_orders WHERE id=%s", (order_id,))
                row = cur.fetchone()
        finally:
            conn.close()
        if row and row["is_test"]:
            return
        emails.send_document_email_auto(order_id, document_id)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Vytvoreni dokladu (sdileny insert)
# ---------------------------------------------------------------------------

def _insert_document(cur, *, order_id, document_type, items, vat_breakdown,
                      total_net, total_vat, total_gross, rounding,
                      advance_deduction, advance_document_number, amount_due,
                      variable_symbol, issue_dt, due_date, taxable_supply_date,
                      recipient_snapshot, delivery_snapshot, note,
                      payment_method_label, related_document_id, part_number,
                      issued_by_label, display_number, seq_year, seq_number):
    cur.execute(
        "INSERT INTO shop_documents "
        "(order_id, document_type, document_number, seq_year, seq_number, part_number, "
        " related_document_id, variable_symbol, constant_symbol, specific_symbol, "
        " payment_method_label, issue_date, due_date, taxable_supply_date, "
        " recipient_snapshot, delivery_snapshot, items_snapshot, vat_breakdown, note, "
        " total_without_vat_czk, total_vat_czk, total_with_vat_czk, rounding_czk, "
        " advance_deduction_czk, advance_document_number, amount_due_czk, issued_by) "
        "VALUES (%s,%s,%s,%s,%s,%s, %s,%s,NULL,NULL, %s,%s,%s,%s, %s,%s,%s,%s,%s, "
        "        %s,%s,%s,%s, %s,%s,%s,%s)",
        (order_id, document_type, display_number, seq_year, seq_number, part_number,
         related_document_id, variable_symbol,
         payment_method_label, issue_dt, due_date, taxable_supply_date,
         json.dumps(recipient_snapshot, ensure_ascii=False),
         json.dumps(delivery_snapshot, ensure_ascii=False) if delivery_snapshot else None,
         json.dumps(items, ensure_ascii=False),
         json.dumps(vat_breakdown, ensure_ascii=False),
         note,
         total_net, total_vat, total_gross, rounding,
         advance_deduction, advance_document_number, amount_due, issued_by_label),
    )
    return cur.lastrowid


def create_proforma_invoice(cur, order, order_items, issued_by_label):
    """Vytvori zalohovou fakturu pro objednavku. `order` je dict se sloupci
    shop_orders (staci id, billing_*, customer_*, delivery_address,
    shipping_/payment_method_name+price_czk)."""
    issue_dt = datetime.now()
    display_number, seq_year, seq_number = _next_document_number(cur, "proforma_invoice", issue_dt)
    items = _build_items_with_vat(order, order_items)
    total_net, total_vat, total_gross, total_gross_rounded, rounding = _totals(items)
    vat_breakdown = [{"rate": _order_vat_rate(order), "base_czk": total_net, "vat_czk": total_vat, "total_czk": total_gross}]
    doc_id = _insert_document(
        cur, order_id=order["id"], document_type="proforma_invoice",
        items=items, vat_breakdown=vat_breakdown,
        total_net=total_net, total_vat=total_vat, total_gross=total_gross, rounding=rounding,
        advance_deduction=0, advance_document_number=None, amount_due=total_gross_rounded,
        # bot10, 2026-08-22 (BUG - Robert: VS byl mylne interni DB id
        # objednavky, ne cislo zalohove faktury - viz TASKS.md/
        # AGENTS_LOG.md pro cely kontext): VS = VLASTNI cislo teto
        # zalohove faktury (bot5, 2026-09-28: Robert primo, VS "včetně
        # prefixů" - display_number, ne jen ciselna cast), presne co
        # bankovni parovani (match_bank_payments_to_orders) ocekava jako
        # parovaci znak.
        variable_symbol=display_number, issue_dt=issue_dt,
        due_date=(issue_dt.date() + timedelta(days=DUE_DAYS)), taxable_supply_date=None,
        recipient_snapshot=_recipient_snapshot(order), delivery_snapshot=_delivery_snapshot(order),
        note=_order_doc_note(order, "Zasíláme fakturu k uhrazení zálohy dle vaší objednávky:"),
        payment_method_label=order.get("payment_method_name"),
        related_document_id=None, part_number=None,
        issued_by_label=issued_by_label, display_number=display_number,
        seq_year=seq_year, seq_number=seq_number,
    )
    return {"id": doc_id, "document_number": display_number, "amount_due_czk": total_gross_rounded,
            "total_with_vat_czk": total_gross_rounded}


def create_proforma_invoice_if_needed(cur, order, order_items):
    """Volano z orders.py::_resolve_and_insert_order hned po vlozeni nove
    objednavky. Pokud zvolena platebni metoda vyzaduje zalohovou fakturu
    (shop_payment_methods.requires_advance_invoice), vystavi ji rovnou
    (WORKFLOW1) - zakaznik ji potrebuje hned, aby mohl zaplatit. Jinak nic
    nedela (WORKFLOW2 - faktura az na rucni pokyn admina pri expedici)."""
    requires = False
    # order dict nemusi obsahovat payment_method_id (jen name/price snapshot) -
    # znovu dotazeme podle nazvu, coz je bezpecne, protoze v ramci JEDNE
    # transakce vytvoreni objednavky se nazev metody nemuze zmenit.
    if order.get("payment_method_name"):
        cur.execute(
            "SELECT requires_advance_invoice FROM shop_payment_methods WHERE name=%s",
            (order["payment_method_name"],),
        )
        row = cur.fetchone()
        requires = bool(row and row["requires_advance_invoice"])
    if not requires:
        return None
    return create_proforma_invoice(cur, order, order_items, issued_by_label=_issued_by_label(None))


def create_payment_tax_document(cur, order, proforma_doc, amount_net, payment_date, issued_by_label):
    """Danovy doklad k prijate platbe (VDD). `amount_net` je castka BEZ
    DPH, ze ktere se dopocita DPH (stejne jako u ostatnich polozek).
    `proforma_doc` (dict s id/document_number) je volitelny - pokud
    existuje, VDD na nej odkazuje (related_document_id)."""
    issue_dt = datetime.now()
    # bot10, 2026-08-22: prefix "VDD" uz NENI hardcoded tady - ctě se ze
    # shop_document_sequences.prefix (seedovano na "VDD", aby uz vydane
    # doklady zustaly konzistentni), viz _next_document_number() a
    # "Nastavení číselné řady dokladů" v adminu.
    # bot5, 2026-09-28 (Robert primo, u skutecne vydaneho VDD "proc se
    # tam přidlo na konci čísla 01? to nechceme") - `-{part_number:02d}`
    # koncovka odstranena z ZOBRAZOVANEHO cisla. part_number sam se dal
    # POCITA a UKLADA (sloupec shop_documents.part_number, viz nize) -
    # jen uz neni soucasti display_number. Neni potreba pro unikatnost:
    # seq_number uz je z JEDNE sdilene atomicke rady napric VSEMI
    # objednavkami, takze display_number je unikatni sam o sobe i bez
    # part_number pripony (overeno - shop_documents.document_number ma
    # UNIQUE (document_type, document_number)).
    display_number, seq_year, seq_number = _next_document_number(cur, "payment_tax_document", issue_dt)
    part_number = _next_part_number(cur, order["id"])

    # bot10, 2026-08-22 (BUG): drive str(order["id"]) - viz TASKS.md/AGENTS_LOG.md
    # bot5, 2026-09-28 (Robert primo, "VS včetně prefixů" - pak "nepobrals
    # to... v tom řádku má být číslo zálohové faktury!!!!!!!!!!"): VS
    # uvadeny v textu VDD (a v samotnem poli variable_symbol) NENI vlastni
    # cislo VDD dokladu (to zustava v `display_number`/document_number,
    # viz nize) - je to cislo ZALOHOVE FAKTURY, ke ktere se platba vaze
    # (presne ten VS, ktery zakaznik skutecne pouzil na bankovni prevod).
    # Bez zalohove faktury (proforma_doc=None - rucni potvrzeni platby se
    # spatnym/chybejicim VS, viz can_mark_payment) neni co odkazovat,
    # padame zpet na vlastni cislo VDD.
    vs = proforma_doc["document_number"] if proforma_doc else display_number
    rate = _order_vat_rate(order)
    vat_amount = _round2(amount_net * rate / 100)
    gross = _round2(amount_net + vat_amount)
    # bot5, 2026-09-28 (Robert primo, vzor proofPayment_vdd26080021-01.pdf:
    # "Daňový doklad k přijaté platbě s VS 26080087 v sazbě DPH 21 %") -
    # DPH koncovka OBNOVENA, vzor ji ma. Vizualni prekryv se sloupcem
    # "DPH %", ktery se driv objevil, byl format textove bunky (plain
    # string, ne Paragraph) - opraveno v render_document_pdf (wrap do
    # Paragraph = spravne zalamovani v ramci sirky sloupce), ne odebranim
    # textu.
    item = {
        "name": f"Daňový doklad k přijaté platbě s VS {vs} v sazbě DPH {rate} %",
        "qty": 1, "unit_price_net": _round2(amount_net), "line_total_net": _round2(amount_net),
        "vat_rate": rate, "vat_amount": vat_amount, "line_total_gross": gross,
    }
    vat_breakdown = [{"rate": rate, "base_czk": _round2(amount_net), "vat_czk": vat_amount, "total_czk": gross}]

    doc_id = _insert_document(
        cur, order_id=order["id"], document_type="payment_tax_document",
        items=[item], vat_breakdown=vat_breakdown,
        total_net=_round2(amount_net), total_vat=vat_amount, total_gross=gross, rounding=0,
        advance_deduction=0, advance_document_number=None, amount_due=0,
        variable_symbol=vs, issue_dt=issue_dt,
        due_date=None, taxable_supply_date=(payment_date or issue_dt.date()),
        recipient_snapshot=_recipient_snapshot(order), delivery_snapshot=None,
        note="NEPLAŤTE!",
        payment_method_label=order.get("payment_method_name"),
        related_document_id=(proforma_doc["id"] if proforma_doc else None), part_number=part_number,
        issued_by_label=issued_by_label, display_number=display_number,
        seq_year=seq_year, seq_number=seq_number,
    )
    return {"id": doc_id, "document_number": display_number, "total_with_vat_czk": gross}


def create_invoice(cur, order, order_items, proforma_doc, issued_by_label):
    """Konecna faktura. Pokud `proforma_doc` (dict id/document_number/
    total_with_vat_czk) existuje, jeji jiz uhrazena castka se odecte od
    zaokrouhlene celkove ceny (presne jako ve vzoru invoice_26010042:
    Shrnutí -> Zaokrouhlení -> 'Zálohová faktura - Kód: ... -X Kč' ->
    K ZAPLACENÍ)."""
    issue_dt = datetime.now()
    display_number, seq_year, seq_number = _next_document_number(cur, "invoice", issue_dt)
    items = _build_items_with_vat(order, order_items)
    total_net, total_vat, total_gross, total_gross_rounded, rounding = _totals(items)
    vat_breakdown = [{"rate": _order_vat_rate(order), "base_czk": total_net, "vat_czk": total_vat, "total_czk": total_gross}]

    # bot5, 2026-09-28 (Robert primo: "u zálohy např 60% je doklad k
    # platbe jen na 60%... při dodání zboží se vystaví faktura kde se
    # od celkové ceny... odečte právě VDD (zaplacená suma) a faktura
    # zobrazí rozdíl tzn doplatek") - odecita se skutecne PRIJATA castka
    # (soucet vsech VDD teto objednavky - castecnych plateb muze byt
    # vic), ne jen POZADOVANA castka na zalohove fakture. Bez tohohle by
    # rucne potvrzena platba BEZ zalohove faktury (viz can_mark_payment,
    # 2026-09-27 - prave kvuli spatnemu VS) fakturou vubec neprosla -
    # zakaznik by dostal fakturu na CELOU castku znovu, ackoli uz
    # castecne/plne zaplatil.
    advance_deduction = 0
    advance_document_number = None
    cur.execute(
        "SELECT document_number, total_with_vat_czk FROM shop_documents "
        "WHERE order_id=%s AND document_type='payment_tax_document' ORDER BY id",
        (order["id"],),
    )
    vdd_rows = cur.fetchall()
    if vdd_rows:
        advance_deduction = _round2(sum(_money(r["total_with_vat_czk"]) or 0.0 for r in vdd_rows))
        advance_document_number = vdd_rows[-1]["document_number"]
    elif proforma_doc:
        # Fallback (zadny VDD jeste nevznikl - platba jeste nebyla
        # potvrzena, ale zalohova faktura uz existuje): odecist aspon
        # POZADOVANOU castku, puvodni chovani zachovano.
        advance_deduction = _money(proforma_doc["amount_due_czk"]) or 0.0
        advance_document_number = proforma_doc["document_number"]
    amount_due = _round2(total_gross_rounded - advance_deduction)

    # bot5, 2026-09-28 (Robert primo, vzor invoice_26010097.pdf) - "Součet
    # DPH" tabulka na PDF u FAKTURY SE ZALOHOU pocita z DOPLATKU
    # (amount_due, po odectení zálohy), ne z celkové ceny objednávky pred
    # odectenim - presne overeno na vzoru (256300/53823/310123 v radku
    # "Shrnutí", ale 80040,50/21%/16808,50/96849 v "Součet DPH" dole,
    # kde 96849 = K ZAPLACENÍ). "Shrnutí" radek (total_net/total_vat/
    # total_gross vyse) zustava CELKOVA cena objednavky beze zmeny.
    if advance_deduction:
        remaining_net = _round2(amount_due / (1 + _order_vat_rate(order) / 100))
        remaining_vat = _round2(amount_due - remaining_net)
        vat_breakdown = [{"rate": _order_vat_rate(order), "base_czk": remaining_net, "vat_czk": remaining_vat, "total_czk": amount_due}]

    doc_id = _insert_document(
        cur, order_id=order["id"], document_type="invoice",
        items=items, vat_breakdown=vat_breakdown,
        total_net=total_net, total_vat=total_vat, total_gross=total_gross, rounding=rounding,
        advance_deduction=advance_deduction, advance_document_number=advance_document_number,
        amount_due=amount_due,
        variable_symbol=display_number, issue_dt=issue_dt,  # bot10, 2026-08-22 (BUG): drive str(order["id"])
        due_date=(issue_dt.date() + timedelta(days=DUE_DAYS)), taxable_supply_date=issue_dt.date(),
        recipient_snapshot=_recipient_snapshot(order), delivery_snapshot=_delivery_snapshot(order),
        note=_order_doc_note(order, "Položky objednávky:"),
        payment_method_label=order.get("payment_method_name"),
        related_document_id=(proforma_doc["id"] if proforma_doc else None), part_number=None,
        issued_by_label=issued_by_label, display_number=display_number,
        seq_year=seq_year, seq_number=seq_number,
    )
    return {"id": doc_id, "document_number": display_number, "amount_due_czk": amount_due}


def create_delivery_note(cur, order, order_items, issued_by_label):
    """Dodaci list (v9, Robert 2026-07-25: 'přidej dodací listy', upresneno
    'je to v podstatě souhrn výdejek' - polozky tedy NEJSOU proste opis
    objednanych mnozstvi, ale SOUHRN SKUTECNYCH SKLADOVYCH VYDEJEK teto
    objednavky, viz _build_items_from_stock_issues). Vraci None, pokud
    objednavka jeste nema zadnou vydejku (jeste nebyla potvrzena/
    vyskladnena) - volajici endpoint v tom pripade vrati 400, dodaci list
    nejde vystavit "naprazdno". Cislovan stejne jako ostatni typy dokladu
    (RRMMxxxx, vlastni rocni rada), ale BEZ cen/DPH - dorucovaci adresa je
    tu KLICOVA (na rozdil od VDD, kde se vubec netiskne)."""
    items = _build_items_from_stock_issues(cur, order, order_items)
    if items is None:
        return None
    issue_dt = datetime.now()
    display_number, seq_year, seq_number = _next_document_number(cur, "delivery_note", issue_dt)
    recipient_snapshot = _recipient_snapshot(order)
    note = "Vyskladněno dle výdejek k objednávce:"
    if order.get("order_path") == "dealer":
        # bot5, 2026-10-02 (dealersky program, cesta (b), Robert: dodaci list a balik BEZ cen a BEZ znacky): zbozi jde koncovemu zakaznikovi DEALERA, dodaci list je
        # proto NEUTRALNI - odesilatel je dealer (jeho udaje uz jsou v recipient snapshotu, protoze fakturace objednavky je na nej), prijemce je doruceni, bez nasi znacky
        # a udaju dodavatele (viz render_document_pdf). Priznak je ve snapshotu, takze se PDF vykresli stejne i po case.
        recipient_snapshot = {**recipient_snapshot, "neutral_delivery": True, "reference": order.get("dealer_external_ref")}
        note = "Obsah zásilky:"
    doc_id = _insert_document(
        cur, order_id=order["id"], document_type="delivery_note",
        items=items, vat_breakdown=[],
        total_net=0, total_vat=0, total_gross=0, rounding=0,
        advance_deduction=0, advance_document_number=None, amount_due=0,
        variable_symbol=display_number, issue_dt=issue_dt,  # bot10, 2026-08-22 (BUG): drive str(order["id"])
        due_date=None, taxable_supply_date=issue_dt.date(),
        recipient_snapshot=recipient_snapshot, delivery_snapshot=_delivery_snapshot(order),
        note=note,
        payment_method_label=None,
        related_document_id=None, part_number=None,
        issued_by_label=issued_by_label, display_number=display_number,
        seq_year=seq_year, seq_number=seq_number,
    )
    return {"id": doc_id, "document_number": display_number}


# ---------------------------------------------------------------------------
# Serializace + nacitani
# ---------------------------------------------------------------------------

def _serialize_document(row, full=False):
    out = {
        "id": row["id"],
        "order_id": row["order_id"],
        "document_type": row["document_type"],
        "document_type_label": DOCUMENT_TYPE_LABELS.get(row["document_type"], row["document_type"]),
        "document_number": row["document_number"],
        "part_number": row["part_number"],
        "related_document_id": row["related_document_id"],
        "variable_symbol": row["variable_symbol"],
        "issue_date": _dt(row["issue_date"]),
        "due_date": _dt(row["due_date"]),
        "taxable_supply_date": _dt(row["taxable_supply_date"]),
        "total_without_vat_czk": _money(row["total_without_vat_czk"]),
        "total_vat_czk": _money(row["total_vat_czk"]),
        "total_with_vat_czk": _money(row["total_with_vat_czk"]),
        "rounding_czk": _money(row["rounding_czk"]),
        "advance_deduction_czk": _money(row["advance_deduction_czk"]),
        "advance_document_number": row["advance_document_number"],
        "amount_due_czk": _money(row["amount_due_czk"]),
        "issued_by": row["issued_by"],
        "created_at": _dt(row["created_at"]),
        "approval_status": row.get("approval_status"),
        "approved_at": _dt(row.get("approved_at")),
    }
    if full:
        out["items"] = json.loads(row["items_snapshot"])
        out["vat_breakdown"] = json.loads(row["vat_breakdown"])
        out["recipient"] = json.loads(row["recipient_snapshot"])
        out["delivery"] = json.loads(row["delivery_snapshot"]) if row["delivery_snapshot"] else None
        out["note"] = row["note"]
        out["payment_method_label"] = row["payment_method_label"]
    return out


def _fetch_document(cur, doc_id):
    cur.execute("SELECT * FROM shop_documents WHERE id=%s", (doc_id,))
    return cur.fetchone()


def _fetch_order(cur, order_id, for_update=False):
    cur.execute("SELECT * FROM shop_orders WHERE id=%s" + (" FOR UPDATE" if for_update else ""), (order_id,))
    return cur.fetchone()


def _lock_order_for_document(cur, order_id, document_type, exists_error):
    """Uzamkne radek objednavky (FOR UPDATE) a overi, ze doklad daneho
    typu k ni jeste neexistuje - OBOJI v JEDNE transakci, aby dva
    soubezne pozadavky na stejnou objednavku (dvojklik, dve otevrena
    admin okna) nemohly vystavit 2 platne, ruzne cislovane doklady
    stejneho typu (zivy nalez z revize kodu, bot3 2026-09-02 - puvodne
    kazdy endpoint delal SELECT bez FOR UPDATE, coz je klasicky TOCTOU
    race). shop_documents zatim nema UNIQUE(order_id, document_type) -
    FOR UPDATE na shop_orders je zamerne nejmensi oprava bez migrace;
    pridani takoveho constraintu (az pri prilezitosti) by byl dalsi,
    jeste tvrdsi zamek proti stejne tride chyby. Sdileno proformou/
    fakturou/dodacim listem - VDD (payment_tax_document) tenhle helper
    NEPOUZIVA, protoze tam je opakovane vystaveni ZAMERNE (castecne
    platby, viz admin_documents_mark_payment_received docstring).
    Vraci (order, None) na uspech, nebo (None, (response, status)) k
    primemu vraceni z volajiciho endpointu."""
    cur.execute("SELECT * FROM shop_orders WHERE id=%s FOR UPDATE", (order_id,))
    order = cur.fetchone()
    if not order:
        return None, (jsonify({"error": "Objednávka neexistuje."}), 404)
    cur.execute(
        "SELECT id FROM shop_documents WHERE order_id=%s AND document_type=%s",
        (order_id, document_type),
    )
    if cur.fetchone():
        return None, (jsonify({"error": exists_error}), 400)
    return order, None


def _fetch_order_items(cur, order_id):
    # Robert 2026-08-08 ("uvadejme u ceny profilů, vedle ks také 3m") -
    # LEFT JOIN na shop_products jen kvuli cfg_dily_id (profil = "1 ks =
    # 3000mm tyc"), aby doklady (_build_items_with_vat nize) mohly u
    # profilovych polozek pripsat "(3 m)" vedle jednotky. oi.* first,
    # pripojene sloupce pod product_ prefixem, at nekolidujou se
    # stavajicimi sloupci shop_order_items (produkt uz smazany/archivovany
    # = p.cfg_dily_id proste NULL, polozka objednavky tim neprijde o nic).
    # is_board_material dotazeno TAKY - desky (napr. PR10) maji casto
    # nastavene OBOJI cfg_dily_id (kvuli 3D scene) i is_board_material,
    # ale neprodavaji se po 3m tycich (viz _is_profile_order_item nize).
    cur.execute(
        "SELECT oi.*, p.cfg_dily_id AS product_cfg_dily_id, "
        "p.is_board_material AS product_is_board_material, "
        "p.is_profile_material AS product_is_profile_material, "
        # Robert 2026-08-10 ("to se přenese až do dokladů, že mj je m
        # nikoli ks") - "prodava se na metry" produkty (unit='m' - viz
        # admin skladova karta) nesmi na dokladech skoncit natvrdo jako
        # "ks", stejne jako to uz resi is_profile_material vyse.
        "p.unit AS product_unit "
        "FROM shop_order_items oi LEFT JOIN shop_products p ON p.id = oi.product_id "
        "WHERE oi.order_id=%s ORDER BY oi.id",
        (order_id,),
    )
    return cur.fetchall()


def _is_profile_order_item(oi):
    # Robert 2026-08-08 ("uvadejme u ceny profilů, vedle ks také 3m"),
    # rozsireno 2026-08-09 (Robert: "dokonci poctive moznost prirezu u
    # vsech profilu" - drivejsi cfg_dily_id test znamenal "ma hotovy 3D
    # model", ne "prodava se na delku", 79/101 profilu bez modelu tak
    # nemelo "(3 m)" ani na dokladech) - sdilena podminka pro "tenhle
    # radek objednavky reprezentuje CELE 3000mm tyce": produkt musi mit
    # is_profile_material, NESMI byt deska (is_board_material - stejna
    # past jako _cutting_plan_shadow_items v orders.py) a radek NESMI byt
    # stinovy radek rezneho planu (cut_kind neni NULL - ten reprezentuje
    # konkretni NAREZANE kusy, ne cele tyce, viz orders.py::
    # _cutting_plan_shadow_items).
    return (
        bool(oi.get("product_is_profile_material"))
        and not oi.get("product_is_board_material")
        and oi.get("cut_kind") is None
    )


def _build_return_items_with_vat(return_items):
    """Polozky dobropisu = VRACENE polozky (mnozstvi muze byt mensi nez
    puvodni radek objednavky - castecna vratka), NE cela objednavka -
    na rozdil od _build_items_with_vat tu NEJSOU doprava/platba (ta se
    nevraci, jen samotne zbozi). Vraci castky KLADNE - zaporne se delaji
    az v create_credit_note (bot18, 2026-09-05, Robertovo rozhodnuti:
    zaporna hodnota, standardni ucetni vzor - mnozstvi zustava KLADNE,
    citelnejsi nez zaporne kusy)."""
    rows = []
    for ri in return_items:
        qty = ri["qty"]
        unit_price_net = _money(ri["unit_price_czk"])
        line_total_net = _round2(unit_price_net * qty)
        rows.append({
            "name": ri["product_name_snapshot"], "qty": qty,
            "unit_price_net": unit_price_net, "line_total_net": line_total_net,
            "is_profile_unit": False, "unit": "ks",
        })
    for r in rows:
        r["vat_rate"] = VAT_RATE
        r["vat_amount"] = _round2(r["line_total_net"] * VAT_RATE / 100)
        r["line_total_gross"] = _round2(r["line_total_net"] + r["vat_amount"])
    return rows


def create_credit_note(cur, order, return_row, return_items, original_invoice, issued_by_label):
    """Dobropis k reklamaci/vratce (bot18, 2026-09-05, Robert pres bot3).
    Castky VZDY zaporne (unit_price_net/line_total_net/vat_amount/
    line_total_gross i souhrnne total_*/amount_due) - standardni ucetni
    vzor. `related_document_id` ukazuje na PUVODNI fakturu, co dobropis
    opravuje - pole uz existuje (dosud pouzivane invoice->proforma),
    zadny novy sloupec potreba. Na rozdil od invoice/delivery_note/atd.
    NEKONTROLUJE "uz existuje doklad tohoto typu k objednavce" pres
    _lock_order_for_document - jedna objednavka muze mit VICE dobropisu
    (vic samostatnych reklamaci v case), unikatnost hlida volajici
    (shop_returns.credit_note_document_id jeden na return, ne na
    order)."""
    issue_dt = datetime.now()
    display_number, seq_year, seq_number = _next_document_number(cur, "credit_note", issue_dt)
    items = _build_return_items_with_vat(return_items)
    for it in items:
        it["unit_price_net"] = -it["unit_price_net"]
        it["line_total_net"] = -it["line_total_net"]
        it["vat_amount"] = -it["vat_amount"]
        it["line_total_gross"] = -it["line_total_gross"]
    total_net, total_vat, total_gross_exact, total_gross_rounded, rounding = _totals(items)
    note = f"Dobropis k reklamaci/vratce {return_row['return_number']}"
    if original_invoice:
        note += f" (opravuje fakturu {original_invoice['document_number']})."
    else:
        note += "."
    doc_id = _insert_document(
        cur, order_id=order["id"], document_type="credit_note",
        items=items, vat_breakdown=[{"rate": VAT_RATE, "base_czk": total_net, "vat_czk": total_vat,
                                      "total_czk": total_gross_rounded}],
        total_net=total_net, total_vat=total_vat, total_gross=total_gross_rounded, rounding=rounding,
        advance_deduction=0, advance_document_number=None, amount_due=total_gross_rounded,
        variable_symbol=display_number, issue_dt=issue_dt,
        due_date=None, taxable_supply_date=issue_dt.date(),
        recipient_snapshot=_recipient_snapshot(order), delivery_snapshot=_delivery_snapshot(order),
        note=note, payment_method_label=None,
        related_document_id=(original_invoice["id"] if original_invoice else None), part_number=None,
        issued_by_label=issued_by_label, display_number=display_number,
        seq_year=seq_year, seq_number=seq_number,
    )
    return {"id": doc_id, "document_number": display_number, "amount_due_czk": total_gross_rounded}


def _workflow_for_order(cur, order):
    """Vrati 1 nebo 2 podle toho, jestli zvolena platebni metoda vyzaduje
    zalohovou fakturu."""
    if not order.get("payment_method_name"):
        return 2
    cur.execute(
        "SELECT requires_advance_invoice FROM shop_payment_methods WHERE name=%s",
        (order["payment_method_name"],),
    )
    row = cur.fetchone()
    return 1 if (row and row["requires_advance_invoice"]) else 2


# ---------------------------------------------------------------------------
# Admin endpointy
# ---------------------------------------------------------------------------

# bot10, 2026-08-22 - "Nastavení číselné řady dokladů" (Robert: "obj mají
# svoji řadu i prefix, zálohovky mají také svoji řadu číselnou i prefix" -
# admin editovatelny prefix per typ dokladu, viz shop_document_sequences.
# prefix + _next_document_number() docstring nahoře). DOCUMENT_TYPES
# (radek 133) je uzavreny seznam vsech typu - objednavky (shop_orders.
# order_number) SEM ZAMERNE NEPATRI: maji vlastni, jednodussi mechanismus
# (orders.py::_generate_order_number(), odvozeny primo z auto-increment
# id objednavky, zadne samostatne pocitadlo/FOR UPDATE zamek jako tady) a
# konceptualne nejde o "vystaveny ucetni doklad" se zakonnou navazností
# cislovani - rozhodnuti bot10, nahlaseno k potvrzeni, viz TASKS.md.
@app.get("/api/admin/document-sequences")
@require_permission("doklady", "zobrazit")
def admin_document_sequences_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT document_type, seq_year, next_number, prefix FROM shop_document_sequences "
                "ORDER BY document_type, seq_year DESC"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    # Kazdy typ v DOCUMENT_TYPES se ukaze VZDY, i kdyz jeste nikdy nebyl
    # vydan (zadny radek v DB) - admin musi mit moznost nastavit prefix
    # PREDEM, driv nez vubec vznikne prvni doklad tohohle typu.
    by_type = {}
    for r in rows:
        by_type.setdefault(r["document_type"], []).append(
            {"seq_year": r["seq_year"], "next_number": r["next_number"], "prefix": r["prefix"]}
        )
    return jsonify({
        "sequences": [
            {
                "document_type": dt,
                "label": DOCUMENT_TYPE_LABELS.get(dt, dt),
                "prefix": (by_type[dt][0]["prefix"] if dt in by_type else ""),
                "years": by_type.get(dt, []),
            }
            for dt in DOCUMENT_TYPES
        ],
    })


@app.put("/api/admin/document-sequences/<document_type>")
@require_permission("doklady", "upravit")
def admin_document_sequences_update(document_type):
    """Zmeni prefix VSECH existujicich rocnich radku daneho typu najednou
    (prefix je vlastnost TYPU, ne konkretniho roku - viz _next_document_
    number docstring). NETYKA se uz vydanych dokladu (jejich document_
    number je nemenny snapshot, viz shop_documents docstring) - projevi
    se az u PRISTIHO vydaneho dokladu tohodle typu.

    Volitelne "current_number" (bot5, 2026-09-27, Robert primo ze
    screenshotu "Nastavení číselné řady dokladů" - "editovatelné
    startovní číslo nastavím") - poslednji VYDANE cislo pro AKTUALNI rok
    (stejne jako se zobrazuje ve sloupci "Aktuální číslo (letos)"), admin
    ho preepise a dalsi vydany doklad tohodle typu dostane current_
    number+1. NEMENI uz vydana cisla, jen kam ukazuje pocitadlo."""
    if document_type not in DOCUMENT_TYPES:
        return jsonify({"error": "Neznámý typ dokladu."}), 400
    admin = current_user()
    body = request.get_json(silent=True) or {}
    prefix = (body.get("prefix") or "").strip().upper()
    if len(prefix) > 10:
        return jsonify({"error": "Prefix může mít nejvýš 10 znaků."}), 400
    if prefix and not re.match(r"^[A-Z0-9]+$", prefix):
        return jsonify({"error": "Prefix smí obsahovat jen velká písmena a číslice."}), 400

    current_number = None
    raw_current = body.get("current_number")
    if raw_current not in (None, ""):
        try:
            current_number = int(raw_current)
        except (TypeError, ValueError):
            return jsonify({"error": "Aktuální číslo musí být celé číslo."}), 400
        if current_number < 0:
            return jsonify({"error": "Aktuální číslo nesmí být záporné."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # BUG opraveno (bot10, 2026-08-22, zivy test): cur.rowcount po
            # UPDATE je pocet SKUTECNE ZMENENYCH radku (MySQL/pymysql
            # vychozi chovani), ne pocet NALEZENYCH radku - kdyz admin
            # ulozi STEJNY prefix, jaky uz mel (napr. vraceni zpet po
            # omylu), rowcount je 0 i kdyz radek existuje, a nasledny
            # INSERT nize by spadl na duplicate-key (overeno zivym testem,
            # puvodni verze takhle padala). Existenci proto overujeme
            # samostatnym SELECT, ne rowcount z UPDATE.
            cur.execute(
                "SELECT 1 FROM shop_document_sequences WHERE document_type=%s LIMIT 1",
                (document_type,),
            )
            exists = cur.fetchone() is not None
            if exists:
                cur.execute(
                    "UPDATE shop_document_sequences SET prefix=%s WHERE document_type=%s",
                    (prefix, document_type),
                )
            else:
                # Typ jeste nikdy nemel vydany doklad (zadny radek pro
                # zadny rok) - zalozime "placeholder" radek pro aktualni
                # rok, aby prefix nebyl ztracen, az prvni doklad vznikne
                # (_next_document_number pak uz jen najde existujici
                # radek misto lazy-insertu s prazdnym prefixem).
                cur.execute(
                    "INSERT INTO shop_document_sequences (document_type, seq_year, next_number, prefix) "
                    "VALUES (%s,%s,1,%s)",
                    (document_type, datetime.now().year, prefix),
                )

            if current_number is not None:
                # Vlastnost KONKRETNIHO ROKU (na rozdil od prefixu vyse) -
                # jen aktualni rok, at admin nepretaci pocitadlo minulych
                # let omylem. Radek pro aktualni rok uz muze existovat
                # (bud z vetve vyse, nebo uz driv vydanym dokladem).
                year = datetime.now().year
                cur.execute(
                    "SELECT 1 FROM shop_document_sequences WHERE document_type=%s AND seq_year=%s",
                    (document_type, year),
                )
                if cur.fetchone():
                    cur.execute(
                        "UPDATE shop_document_sequences SET next_number=%s WHERE document_type=%s AND seq_year=%s",
                        (current_number + 1, document_type, year),
                    )
                else:
                    cur.execute(
                        "INSERT INTO shop_document_sequences (document_type, seq_year, next_number, prefix) "
                        "VALUES (%s,%s,%s,%s)",
                        (document_type, year, current_number + 1, prefix),
                    )
        conn.commit()
    finally:
        conn.close()
    note = f"{document_type} -> prefix={prefix or '(prázdný)'}"
    if current_number is not None:
        note += f", aktuální číslo={current_number}"
    log_audit(admin["id"], "update", "document_sequence_prefix", None, note)
    return jsonify({"status": "ok", "document_type": document_type, "prefix": prefix})


def _serialize_document_row_with_order(row):
    """Jako _serialize_document(), ale doplnuje order_number/customer_name
    (z JOIN na shop_orders) - urceno pro celkovy prehled admin_documents_overview()
    NIZE, kde je potreba vedet KTERA objednavka/zakaznik ke kazdemu
    dokladu patri (na rozdil od per-objednavka seznamu admin_documents_list(),
    kde uz je to jasne z kontextu)."""
    out = _serialize_document(row)
    out["order_number"] = row["order_number"]
    out["customer_name"] = row["customer_name"]
    out["customer_email"] = row["customer_email"]
    return out


@app.get("/api/admin/documents")
@require_permission("doklady", "zobrazit")
def admin_documents_overview():
    """
    Celkovy prehled VSECH dokladu napric objednavkami (Robert, 2026-07-25:
    "delal jsi tabulku přehled faktur?" - nedelal, admin_documents_list()
    nize je jen PO JEDNE objednavce - tenhle endpoint je noveji doplnena
    tabulka pro cely seznam, stejny vzor jako GET /api/admin/orders).

    ?document_type=proforma_invoice|payment_tax_document|invoice  - filtr na typ
    ?q=...      - hledani v cisle dokladu / cisle objednavky / jmene zakaznika / e-mailu
    ?date_from=YYYY-MM-DD, ?date_to=YYYY-MM-DD  - filtr na datum vystaveni (issue_date)

    Odpoved obsahuje "counts" (pocet pro kazdy typ + "all"), stejny vzor
    jako u GET /api/admin/orders - pro vykresleni tabu bez nutnosti volat
    endpoint vicekrat.
    """
    document_type = request.args.get("document_type")
    q = (request.args.get("q") or "").strip()
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    if document_type and document_type not in DOCUMENT_TYPES:
        return jsonify({"error": "Neplatný document_type."}), 400

    where, params = [], []
    if document_type:
        where.append("d.document_type=%s")
        params.append(document_type)
    if q:
        where.append(
            "(d.document_number LIKE %s OR o.order_number LIKE %s "
            "OR o.customer_name LIKE %s OR o.customer_email LIKE %s)"
        )
        like = f"%{q}%"
        params += [like, like, like, like]
    if date_from:
        where.append("DATE(d.issue_date) >= %s")
        params.append(date_from)
    if date_to:
        where.append("DATE(d.issue_date) <= %s")
        params.append(date_to)

    # Stránkování (task #78/83)
    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            base_sql = (
                "SELECT d.*, o.order_number, o.customer_name, o.customer_email "
                "FROM shop_documents d JOIN shop_orders o ON o.id = d.order_id"
            )
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            rows, total = paginated_query(cur, base_sql, where_sql, params,
                                           " ORDER BY d.issue_date DESC, d.id DESC", page, page_size)

            cur.execute("SELECT document_type, COUNT(*) AS n FROM shop_documents GROUP BY document_type")
            type_counts = {r["document_type"]: r["n"] for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) AS n FROM shop_documents")
            all_count = cur.fetchone()["n"]
            cur.execute(
                "SELECT COALESCE(SUM(amount_due_czk),0) AS n FROM shop_documents "
                "WHERE document_type IN ('proforma_invoice','invoice') AND amount_due_czk > 0"
            )
            total_outstanding = _money(cur.fetchone()["n"])
    finally:
        conn.close()

    counts = {"all": all_count}
    for t in DOCUMENT_TYPES:
        counts[t] = type_counts.get(t, 0)

    resp = {
        "documents": [_serialize_document_row_with_order(r) for r in rows],
        "counts": counts,
        "total_outstanding_czk": total_outstanding,
    }
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.get("/api/admin/orders/<int:order_id>/documents")
@require_permission("doklady", "zobrazit")
def admin_documents_list(order_id):
    """Prehled dokladu k objednavce + info o workflow (1/2) a jake dalsi
    doklady lze jeste vystavit (pro vykresleni tlacitek v adminu)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            order = _fetch_order(cur, order_id)
            if not order:
                return jsonify({"error": "Objednávka neexistuje."}), 404
            workflow = _workflow_for_order(cur, order)
            cur.execute(
                "SELECT * FROM shop_documents WHERE order_id=%s ORDER BY issue_date ASC, id ASC",
                (order_id,),
            )
            docs = cur.fetchall()
            # Dodaci list = souhrn skutecnych skladovych vydejek (viz
            # create_delivery_note) - tlacitko dava smysl zobrazit jen kdyz
            # uz nejaka vydejka k teto objednavce existuje (vznika pri
            # prechodu nova->potvrzena, orders.py).
            cur.execute(
                "SELECT 1 FROM shop_stock_movements WHERE document_number=%s AND movement_type='issue' LIMIT 1",
                (order["order_number"],),
            )
            has_stock_issued = cur.fetchone() is not None
    finally:
        conn.close()

    has_proforma = any(d["document_type"] == "proforma_invoice" for d in docs)
    has_invoice = any(d["document_type"] == "invoice" for d in docs)
    has_delivery_note = any(d["document_type"] == "delivery_note" for d in docs)
    can_issue_proforma = workflow == 1 and not has_proforma
    # bot5, 2026-09-27 (Robert primo: "nejde vytvořit ze zálohové faktury
    # doklad k přijaté platbě... kdyz klient splete variabilní symbol...
    # vytvořím VDD ručně") - drive vyzadovalo existujici zalohovou fakturu
    # (has_proforma), coz blokovalo prave tenhle pripad: platba prijde se
    # SPATNYM/nesedicim VS (automaticke parovani v bank_statements.py ji
    # nenajde), objednavka pritom jeste zadnou zalohovku mit nemusi. Sam
    # create_payment_tax_document() uz proforma_doc=None podporuje (viz
    # jeho docstring - "volitelny"), gating tady byl zbytecne prisnejsi
    # nez samotna funkce - ted staci, ze objednavka existuje.
    #
    # bot5, 2026-09-28 (Robert primo, po nahodnem 2. potvrzeni uz plne
    # uhrazene objednavky - "proboha nemuze se uhradit 2x uz uhrazená!!!"):
    # jakmile castka jiz prijata (bank_paid NEBO rucne potvrzeno) pokryva
    # CELY total_czk, dalsi potvrzeni uz nedava smysl - tlacitko zmizi
    # (endpoint nize navic razi tvrdy server-side guard, at nejde obejit
    # primym volanim API).
    already_fully_paid = bool(order.get("bank_paid")) or (
        _money(order.get("payment_received_total_czk")) is not None
        and _money(order["payment_received_total_czk"]) >= _money(order["total_czk"]) - 0.01
    )
    can_mark_payment = not already_fully_paid
    can_issue_invoice = not has_invoice
    can_issue_delivery_note = not has_delivery_note and has_stock_issued

    # bot5, 2026-09-28 (Robert primo: "ale pozor je potreba rozlišovat
    # částečné uhrady") - "uhrazeno/neuhrazeno" v seznamu objednavek uz
    # castecnou platbu rozlisuje (viz objednavky-doklady.js
    # renderOrdersTable), ale TADY - primo v zalozce Doklady dane
    # objednavky, kde admin platby rucne potvrzuje - zadny souhrn nebyl,
    # jen jednotlive VDD radky bez kontextu "kolik uz/kolik zbyva".
    already_received = _money(order.get("payment_received_total_czk")) or 0.0
    order_total = _money(order["total_czk"]) or 0.0
    if order.get("bank_paid") or already_received >= order_total - 0.01:
        payment_status = "paid"
    elif already_received > 0:
        payment_status = "partial"
    else:
        payment_status = "unpaid"

    return jsonify({
        "workflow": workflow,
        "documents": [_serialize_document(d) for d in docs],
        "payment_summary": {
            "status": payment_status,
            "total_czk": order_total,
            "received_czk": already_received,
            "remaining_czk": round(max(0.0, order_total - already_received), 2),
            "bank_paid": bool(order.get("bank_paid")),
        },
        "actions": {
            "can_issue_proforma": can_issue_proforma,
            "can_mark_payment_received": can_mark_payment,
            "can_issue_invoice": can_issue_invoice,
            "can_issue_delivery_note": can_issue_delivery_note,
        },
    })


@app.post("/api/admin/orders/<int:order_id>/documents/proforma")
@require_permission("doklady", "vytvorit")
def admin_documents_create_proforma(order_id):
    """Rucni vystaveni zalohove faktury (obvykle neni treba - vystavi se
    automaticky pri vytvoreni objednavky s platbou 'requires_advance_invoice',
    viz create_proforma_invoice_if_needed - tenhle endpoint je pro dohnani
    starsi objednavky nebo dodatecnou zmenu platebni metody)."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            order, err = _lock_order_for_document(
                cur, order_id, "proforma_invoice", "Zálohová faktura k této objednávce už existuje.",
            )
            if err:
                conn.rollback()
                return err
            items = _fetch_order_items(cur, order_id)
            result = create_proforma_invoice(cur, order, items, _issued_by_label(admin))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "document_proforma", result["id"], result["document_number"])
    _auto_email_after_issue(order_id, result["id"])
    return jsonify({"status": "ok", **result})


@app.post("/api/admin/orders/<int:order_id>/documents/payment-received")
@require_permission("doklady", "vytvorit")
def admin_documents_mark_payment_received(order_id):
    """
    Rucni potvrzeni prijate platby - vystavi Danovy doklad k prijate
    platbe (VDD). Lze volat opakovane (castecne platby), kazde volani = 1
    novy VDD doklad.

    Body (vse volitelne):
    {
      "amount_czk": 2088.00,     BEZ DPH - jinak se pouzije zbyvajici
                                  neuhrazena castka objednavky (bez DPH)
      "payment_date": "2026-07-22"   jinak dnesni datum
    }
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # FOR UPDATE (bot3, revize kodu 2026-09-03): tenhle endpoint dela
            # read-modify-write na payment_received_total_czk nize - bez
            # zamku by dve soubezna "oznacit platbu jako prijatou" na
            # stejnou objednavku vytvorila oba VDD doklady spravne
            # (cislovani ma svuj vlastni zamek), ale soucet by ztratil jednu
            # z plateb (lost update). NEpouziva se _lock_order_for_document,
            # ten navic kontroluje duplicitu dokladu daneho typu - tady je
            # opakovane vystaveni VDD ZAMERNE povolene (castecne platby).
            order = _fetch_order(cur, order_id, for_update=True)
            if not order:
                conn.rollback()
                return jsonify({"error": "Objednávka neexistuje."}), 404

            cur.execute(
                "SELECT * FROM shop_documents WHERE order_id=%s AND document_type='proforma_invoice'",
                (order_id,),
            )
            proforma = cur.fetchone()

            # bot5, 2026-09-28 (Robert primo, po nahodnem 2. potvrzeni uz
            # plne uhrazene objednavky - "proboha nemuze se uhradit 2x uz
            # uhrazená!!!"): tvrdy guard - kdyz uz prijata castka (bank_paid
            # NEBO drivejsi rucni potvrzeni) pokryva CELY total_czk, dalsi
            # potvrzeni se ODMITA. Nejde jen o UI (can_mark_payment vyse) -
            # tohle je server-side, nejde obejit primym volanim API.
            already_received = _money(order.get("payment_received_total_czk")) or 0.0
            order_total = _money(order["total_czk"]) or 0.0
            if order.get("bank_paid") or already_received >= order_total - 0.01:
                conn.rollback()
                return jsonify({
                    "error": f"Objednávka je už plně uhrazena ({already_received:.2f} Kč "
                             f"z {order_total:.2f} Kč) - nelze potvrdit platbu znovu."
                }), 400

            raw_amount = body.get("amount_czk")
            if raw_amount is not None:
                try:
                    amount_net = float(raw_amount)
                except (TypeError, ValueError):
                    conn.rollback()
                    return jsonify({"error": "Neplatná částka."}), 400
            else:
                # bot5, 2026-09-28: docstring vyse slibuje "zbývající
                # neuhrazená částka", kod ale vzdy pouzival CELY total_czk
                # znovu (presne tenhle nesoulad umoznil dvojite potvrzeni
                # plne castky pri 2. kliknuti bez zadane castky) - opraveno
                # na skutecny zbytek.
                # bot5, 2026-09-29 (Robert primo, OBJ-2026-00001: "prijal
                # jsem platbu celych 12tisic... dnes je napsano jen
                # castecna uhrada") - already_received/order_total jsou OBA
                # GROSS (vc. DPH), ale create_payment_tax_document nize
                # ocekava amount_net BEZ DPH - chybel prevod, VDD tak
                # trvale vychazelo o castku DPH nizsi, nez skutecne zbyvalo.
                remaining_gross = round(order_total - already_received, 2)
                amount_net = round(remaining_gross / (1 + _order_vat_rate(order) / 100), 2)
            if amount_net <= 0:
                conn.rollback()
                return jsonify({"error": "Částka musí být kladná."}), 400

            payment_date = None
            if body.get("payment_date"):
                try:
                    payment_date = datetime.strptime(body["payment_date"], "%Y-%m-%d").date()
                except ValueError:
                    conn.rollback()
                    return jsonify({"error": "Neplatné datum platby (očekáván formát YYYY-MM-DD)."}), 400

            result = create_payment_tax_document(
                cur, order, proforma, amount_net, payment_date, _issued_by_label(admin)
            )

            # GROSS (result["total_with_vat_czk"]), NE amount_net - viz
            # komentar u remaining_gross vyse, stejna jednotka jako
            # total_czk vsude, kde se payment_received_total_czk porovnava.
            new_total_received = _round2((_money(order["payment_received_total_czk"]) or 0.0) + result["total_with_vat_czk"])
            cur.execute(
                "UPDATE shop_orders SET payment_received_at=%s, payment_received_total_czk=%s WHERE id=%s",
                (payment_date or datetime.now(), new_total_received, order_id),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "document_payment_tax", result["id"], result["document_number"])
    _auto_email_after_issue(order_id, result["id"])
    return jsonify({"status": "ok", **result})


@app.put("/api/admin/documents/<int:doc_id>/payment-date")
@require_permission("doklady", "upravit")
def admin_documents_update_payment_date(doc_id):
    """Zpetna oprava data prijeti platby u jiz vydaneho VDD (bot5,
    2026-09-28, Robert primo: "pokud se nepriradi platba automaticky k
    zálohove fakture musí být volba rucní uhrady s volitelným datumem
    uhrady... admin si to musi najít ručně tu platbu a zadat ručně to
    datum... takže potrebuji zpetne upravit tu platbu").

    Na rozdil od ostatnich dokladu (nemenny snapshot) tady VYSLOVNE
    dovolujeme upravu PO vydani - datum prijeti platby se casto zjisti
    az zpetne (rucni parovani spatneho/chybejiciho VS), VDD sam o sobe
    zadnou castku/polozky nemeni, jen KDY se platba stala.

    Meni issue_date + taxable_supply_date na danem dokladu, a pokud jde
    o (chronologicky) POSLEDNI VDD teto objednavky, i shop_orders.
    payment_received_at (to je pole, ktere admin/prehled skutecne
    zobrazuje jako "kdy uhrazeno")."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    raw_date = (body.get("payment_date") or "").strip()
    if not raw_date:
        return jsonify({"error": "Chybí payment_date (formát YYYY-MM-DD)."}), 400
    try:
        new_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Neplatné datum (očekáván formát YYYY-MM-DD)."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            doc = _fetch_document(cur, doc_id)
            if not doc:
                conn.rollback()
                return jsonify({"error": "Doklad neexistuje."}), 404
            if doc["document_type"] != "payment_tax_document":
                conn.rollback()
                return jsonify({"error": "Datum jde takhle opravit jen u dokladu k přijaté platbě (VDD)."}), 400
            new_issue_dt = datetime.combine(new_date, doc["issue_date"].time())
            cur.execute(
                "UPDATE shop_documents SET issue_date=%s, taxable_supply_date=%s WHERE id=%s",
                (new_issue_dt, new_date, doc_id),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return jsonify({"error": f"UPDATE zasáhl {cur.rowcount} řádků místo 1."}), 500
            # Nejnovejsi VDD teto objednavky urcuje, co se zobrazuje jako
            # "kdy uhrazeno" v prehledu - jen kdyz tenhle doklad je (po
            # opravě) skutecne ten posledni, at drivejsi castecna platba
            # neprepise pozdejsi.
            cur.execute(
                "SELECT id FROM shop_documents WHERE order_id=%s AND document_type='payment_tax_document' "
                "ORDER BY issue_date DESC, id DESC LIMIT 1",
                (doc["order_id"],),
            )
            latest = cur.fetchone()
            if latest and latest["id"] == doc_id:
                cur.execute(
                    "UPDATE shop_orders SET payment_received_at=%s WHERE id=%s",
                    (new_issue_dt, doc["order_id"]),
                )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "document_payment_date", doc_id, f"-> {new_date.isoformat()}")
    return jsonify({"status": "ok", "document_number": doc["document_number"], "payment_date": new_date.isoformat()})


@app.post("/api/admin/orders/<int:order_id>/documents/invoice")
@require_permission("doklady", "vytvorit")
def admin_documents_create_invoice(order_id):
    """Vystaveni konecne faktury. Pokud k objednavce existuje zalohova
    faktura, jeji castka se automaticky odecte (viz create_invoice)."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            order, err = _lock_order_for_document(
                cur, order_id, "invoice", "Faktura k této objednávce už existuje.",
            )
            if err:
                conn.rollback()
                return err

            cur.execute(
                "SELECT * FROM shop_documents WHERE order_id=%s AND document_type='proforma_invoice'",
                (order_id,),
            )
            proforma = cur.fetchone()
            items = _fetch_order_items(cur, order_id)
            result = create_invoice(cur, order, items, proforma, _issued_by_label(admin))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "document_invoice", result["id"], result["document_number"])
    _auto_email_after_issue(order_id, result["id"])
    return jsonify({"status": "ok", **result})


@app.post("/api/admin/orders/<int:order_id>/documents/delivery-note")
@require_permission("doklady", "vytvorit")
def admin_documents_create_delivery_note(order_id):
    """Rucni vystaveni dodaciho listu (v9, Robert 2026-07-25: 'přidej
    dodací listy', upresneno 'je to v podstatě souhrn výdejek') - typicky
    pri expedici zbozi. Na rozdil od proformy/VDD/faktury NENI vazany na
    workflow ani na platbu, ALE VYZADUJE, aby objednavka uz mela alespon
    jednu skladovou vydejku (viz create_delivery_note/
    _build_items_from_stock_issues - vydejka vznika automaticky pri
    prechodu objednavky nova->potvrzena, orders.py::admin_orders_update_status).
    Bez vydejky (objednavka jeste nebyla potvrzena) nejde dodaci list
    vystavit "naprazdno" - a tez nejde vystavit podruhe."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            order, err = _lock_order_for_document(
                cur, order_id, "delivery_note", "Dodací list k této objednávce už existuje.",
            )
            if err:
                conn.rollback()
                return err
            items = _fetch_order_items(cur, order_id)
            result = create_delivery_note(cur, order, items, _issued_by_label(admin))
            if result is None:
                conn.rollback()
                return jsonify({
                    "error": "Objednávka ještě nemá žádné vyskladněné položky (musí být alespoň jednou "
                             "potvrzena, aby vznikly skladové výdejky) - dodací list nelze vystavit."
                }), 400
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "document_delivery_note", result["id"], result["document_number"])
    _auto_email_after_issue(order_id, result["id"])
    return jsonify({"status": "ok", **result})


@app.get("/api/admin/documents/<int:doc_id>")
@require_permission("doklady", "zobrazit")
def admin_documents_get(doc_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            doc = _fetch_document(cur, doc_id)
    finally:
        conn.close()
    if not doc:
        return jsonify({"error": "Doklad neexistuje."}), 404
    return jsonify({"document": _serialize_document(doc, full=True)})


@app.get("/api/admin/documents/<int:doc_id>/pdf")
@require_permission("doklady", "zobrazit")
def admin_documents_pdf(doc_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            doc = _fetch_document(cur, doc_id)
    finally:
        conn.close()
    if not doc:
        return jsonify({"error": "Doklad neexistuje."}), 404
    pdf_bytes = render_document_pdf(doc)
    return Response(pdf_bytes, mimetype="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{doc["document_type"]}_{doc["document_number"]}.pdf"'
    })


# ---------------------------------------------------------------------------
# Mazani dokladu (Robert 2026-07-26: "mazat musí být všude !!!")
# ---------------------------------------------------------------------------

def _unlink_and_delete_documents(cur, docs):
    """Spolecna logika mazani 1..N dokladu (pouziva admin_documents_delete_one
    i admin_documents_bulk_delete). `docs` musi byt UZ NACTENE radky (SELECT *
    FROM shop_documents) - volajici je potrebuje znat PRED smazanim, aby se
    dalo rozhodnout o vedlejsich ucincich podle document_type/order_id.

    Doklad je jinak nemenny snapshot, ale ani jedna z FK vazeb SMEREM DO
    shop_documents nema v DB ON DELETE CASCADE/SET NULL - bez rucniho
    osetreni by samotny DELETE spadl na FK constraint:
      - shop_documents.related_document_id (faktura/VDD -> zalohova
        faktura, kterou odectena/dokladuje) - ODPOJUJEME, NEMAZEME.
        Navazujici doklad (napr. faktura) je porad platny sam o sobe,
        jen ztrati odkaz na uz neexistujici zalohu - smazat i jeho by
        byla neprimerena kaskada (jiny doklad, ne "log" tohoto).
      - shop_emails.document_id (PDF priloha) - Robert 2026-08-02
        (AskUserQuestion): "smaže-li se jakýkolikoli doklad... musí se
        smazat i každý návazný doklad pohyb cokoli co navazuje v DB" ->
        potvrzeno explicitne, ze e-maily se MAJI SMAZAT (puvodne se jen
        odpojovaly, historie odeslani se schvalne drzela jako audit
        stopa - tohle rozhodnuti Robert timhle prevazil).

    U VDD ("danovy doklad k prijate platbe") navic vratime castku ze
    shop_orders.payment_received_total_czk, kterou navysil
    admin_documents_mark_payment_received() pri vystaveni - jinak by
    "přijato" na objednavce zustalo falesne vysoke i po smazani dokladu o
    prijeti platby. Scitame podle objednavky (bulk mazani muze smazat vic
    VDD ze stejne objednavky najednou), vysledek nikdy do zaporu.

    Robert 2026-08-01 (AskUserQuestion): "smazat doklad = vrátit sklad +
    smazat pohyby objednávky" - smazani KTEREHOKOLI dokladu k objednavce
    navic vrati stav skladu a smaze VSECHNY skladove pohyby vazane na
    cislo dane objednavky (shop_stock_movements.document_number ==
    order_number, viz _build_items_from_stock_issues vyse). Zamerne NE
    jen pohyby "patrici" tomuto konkretnimu dokladu - takova 1:1 vazba v
    datech neexistuje, vic dokladu stejne objednavky (proforma/faktura/
    dodaci list) sdili tytez pohyby.

    Vraci dict {"deleted": pocet smazanych dokladu,
    "stock_movement_ids": [id smazanych pohybu, pro gallery cleanup u
    volajiciho], "stock_failed": [pohyby, ktere sly by do zaporu skladu,
    proto NEsmazane]}.
    """
    ids = [d["id"] for d in docs]
    if not ids:
        return {"deleted": 0, "stock_movement_ids": [], "stock_failed": []}
    placeholders = ",".join(["%s"] * len(ids))

    cur.execute(
        f"UPDATE shop_documents SET related_document_id=NULL WHERE related_document_id IN ({placeholders})",
        ids,
    )
    cur.execute(
        f"DELETE FROM shop_emails WHERE document_id IN ({placeholders})",
        ids,
    )

    stock_movement_ids = []
    stock_failed = []
    order_ids = {d["order_id"] for d in docs if d.get("order_id")}
    if order_ids:
        op = ",".join(["%s"] * len(order_ids))
        cur.execute(f"SELECT order_number FROM shop_orders WHERE id IN ({op})", list(order_ids))
        order_numbers = [r["order_number"] for r in cur.fetchall()]
        if order_numbers:
            np = ",".join(["%s"] * len(order_numbers))
            cur.execute(
                f"SELECT id FROM shop_stock_movements WHERE document_number IN ({np})",
                order_numbers,
            )
            movement_ids = [r["id"] for r in cur.fetchall()]
            if movement_ids:
                stock_movement_ids, stock_failed = reverse_and_delete_stock_movements(cur, movement_ids)

    per_order_refund = {}
    for d in docs:
        if d["document_type"] == "payment_tax_document":
            per_order_refund[d["order_id"]] = (
                per_order_refund.get(d["order_id"], 0.0) + float(d["total_without_vat_czk"] or 0)
            )
    for order_id, refund in per_order_refund.items():
        cur.execute("SELECT payment_received_total_czk FROM shop_orders WHERE id=%s", (order_id,))
        row = cur.fetchone()
        if not row:
            continue
        new_total = _round2(max(0.0, float(row["payment_received_total_czk"] or 0) - refund))
        if new_total <= 0:
            cur.execute(
                "UPDATE shop_orders SET payment_received_total_czk=0, payment_received_at=NULL WHERE id=%s",
                (order_id,),
            )
        else:
            cur.execute(
                "UPDATE shop_orders SET payment_received_total_czk=%s WHERE id=%s",
                (new_total, order_id),
            )

    deleted = bulk_delete(cur, "shop_documents", ids)
    return {"deleted": deleted, "stock_movement_ids": stock_movement_ids, "stock_failed": stock_failed}


@app.delete("/api/admin/documents/<int:doc_id>")
@require_permission("doklady", "smazat")
def admin_documents_delete_one(doc_id):
    """Smazani JEDNOHO dokladu - typicky omylem vystaveny/duplicitni
    doklad. Viz _unlink_and_delete_documents pro odpojeni FK vazeb a
    vraceni castky u VDD."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            doc = _fetch_document(cur, doc_id)
            if not doc:
                conn.rollback()
                return jsonify({"error": "Doklad neexistuje."}), 404
            result = _unlink_and_delete_documents(cur, [doc])
        conn.commit()
    finally:
        conn.close()
    import gallery_items
    gallery_items.delete_items_for_owner("document", doc_id)
    for mv_id in result["stock_movement_ids"]:
        gallery_items.delete_items_for_owner("stock_movement", mv_id)
    label = DOCUMENT_TYPE_LABELS.get(doc["document_type"], doc["document_type"])
    stock_note = f" Vráceno {len(result['stock_movement_ids'])} skladových pohybů objednávky." \
        if result["stock_movement_ids"] else ""
    log_audit(admin["id"], "delete", "document", doc_id, f"{label} {doc['document_number']} smazán.{stock_note}")
    return jsonify({
        "status": "ok",
        "stock_reversed": len(result["stock_movement_ids"]),
        "stock_failed": result["stock_failed"],
    })


@app.post("/api/admin/documents/bulk-delete")
@require_permission("doklady", "smazat")
def admin_documents_bulk_delete():
    """Hromadne smazani dokladu - stejne odpojeni FK vazeb + vraceni
    prijate castky u VDD jako admin_documents_delete_one."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT * FROM shop_documents WHERE id IN ({placeholders})", ids)
            docs = cur.fetchall()
            result = _unlink_and_delete_documents(cur, docs)
        conn.commit()
    finally:
        conn.close()
    import gallery_items
    for d in docs:
        gallery_items.delete_items_for_owner("document", d["id"])
    for mv_id in result["stock_movement_ids"]:
        gallery_items.delete_items_for_owner("stock_movement", mv_id)
    found_ids = {d["id"] for d in docs}
    missing = [i for i in ids if i not in found_ids]
    stock_note = f", {len(result['stock_movement_ids'])} skladových pohybů vráceno" \
        if result["stock_movement_ids"] else ""
    log_audit(admin["id"], "bulk_delete", "document", None,
              f"{result['deleted']} dokladů smazáno" + (f", {len(missing)} nenalezeno" if missing else "")
              + stock_note)
    return jsonify({
        "status": "ok", "deleted": result["deleted"],
        "failed": [{"id": i, "error": "Doklad neexistuje."} for i in missing],
        "stock_reversed": len(result["stock_movement_ids"]),
        "stock_failed": result["stock_failed"],
    })


# ---------------------------------------------------------------------------
# Zakaznik: vlastni doklady
# ---------------------------------------------------------------------------

@app.get("/api/customer/orders/<int:order_id>/documents")
@login_required
def customer_documents_list(order_id):
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            order = _fetch_order(cur, order_id)
            if not order:
                return jsonify({"error": "Objednávka neexistuje."}), 404
            if order["user_id"] != user["id"] and user["role"] != "admin":
                return jsonify({"error": "Nemáte oprávnění k této objednávce.", "code": "forbidden"}), 403
            cur.execute(
                "SELECT * FROM shop_documents WHERE order_id=%s ORDER BY issue_date ASC, id ASC",
                (order_id,),
            )
            docs = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"documents": [_serialize_document(d) for d in docs]})


@app.get("/api/customer/documents/<int:doc_id>/pdf")
@login_required
def customer_documents_pdf(doc_id):
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            doc = _fetch_document(cur, doc_id)
            if not doc:
                return jsonify({"error": "Doklad neexistuje."}), 404
            order = _fetch_order(cur, doc["order_id"])
    finally:
        conn.close()
    if not order or (order["user_id"] != user["id"] and user["role"] != "admin"):
        return jsonify({"error": "Nemáte oprávnění k tomuto dokladu.", "code": "forbidden"}), 403
    pdf_bytes = render_document_pdf(doc)
    return Response(pdf_bytes, mimetype="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{doc["document_type"]}_{doc["document_number"]}.pdf"'
    })


# ---------------------------------------------------------------------------
# PDF generovani (ReportLab - cisty Python, zadne systemove zavislosti)
# ---------------------------------------------------------------------------

def _fmt_czk(v):
    if v is None:
        return ""
    return f"{v:,.2f} Kč".replace(",", " ").replace(".", ",")


def _fmt_qty_unit(it):
    # Robert 2026-08-08 ("uvadejme u ceny profilů, vedle ks také 3m") -
    # stejne pripomenuti "ks" = "3 m" jako na webu, viz is_profile_unit
    # z _build_items_with_vat / _build_items_from_stock_issues.
    # Robert 2026-08-10 ("to se přenese až do dokladů, že mj je m nikoli
    # ks") - drive natvrdo "ks" pro VSECHNY radky; ted skutecna jednotka
    # produktu (shop_products.unit - "m" u polozek prodavanych na bezne
    # metry, viz admin skladova karta "Prodává se na metry").
    return f"{it['qty']} {it.get('unit') or 'ks'}" + (" (3 m)" if it.get("is_profile_unit") else "")


def _fmt_date(v):
    if not v:
        return ""
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v)
        except ValueError:
            return v
    return v.strftime("%-d.%-m.%Y") if hasattr(v, "strftime") else str(v)


# Robert 2026-07-31: "PDF doklady potrebujeme aby vypadaly seriozne
# ramecky tak jak byva zvykem" - puvodni vzhled mel ohraniceni jen u
# tabulky polozek (GRID), hlavicka (dodavatel/prijemce) a souhrn/K
# ZAPLACENI byly bez jakehokoli ramecku - pusobilo to "rozsypane", ne
# jako bezna ceska faktura. DOC_BORDER_COLOR sjednocuje ramecky se
# stavajici akcentovou barvou zahlavi tabulky polozek (#2f3e4d).
DOC_BORDER_COLOR = colors.HexColor("#2f3e4d")


def render_document_pdf(doc):
    """Vygeneruje PDF pro 1 doklad (shop_documents radek) - vraci bytes."""
    import io
    items = json.loads(doc["items_snapshot"])
    vat_breakdown = json.loads(doc["vat_breakdown"])
    recipient = json.loads(doc["recipient_snapshot"])
    delivery = json.loads(doc["delivery_snapshot"]) if doc["delivery_snapshot"] else None
    doc_type = doc["document_type"]
    label = DOCUMENT_TYPE_LABELS.get(doc_type, doc_type)

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName=FONT_BOLD, fontSize=15, spaceAfter=2)
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontName=FONT_REGULAR)
    small = ParagraphStyle("small", parent=styles["Normal"], fontName=FONT_REGULAR, fontSize=8, textColor=colors.grey)
    # bot5, 2026-09-28 (Robert nahlasil vizualni prekryv dlouheho nazvu
    # polozky se sloupcem "DPH %" na PDF VDD) - nazev polozky jako plain
    # string se v Table bunce nezalamoval spolehlive v ramci sirky
    # sloupce, Paragraph to resi standardne (stejny mechanismus, jaky uz
    # pouziva dodavatel/prijemce blok vyse).
    item_name_style = ParagraphStyle("item_name", parent=styles["Normal"], fontName=FONT_REGULAR, fontSize=8, leading=10)

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm,
                             leftMargin=15 * mm, rightMargin=15 * mm)
    flow = []

    # Neutralni dodaci list dealerske objednavky (cesta (b)): bez znacky, dodavatele a cen - viz create_delivery_note.
    neutral = doc_type == "delivery_note" and bool(recipient.get("neutral_delivery"))
    flow.append(_P(
        f"{_esc(label)} č. {_esc(doc['document_number'])}" if neutral
        else f"{_esc(SUPPLIER['name'])} &ndash; {_esc(label)} č. {_esc(doc['document_number'])}", h1))
    flow.append(HRFlowable(width="100%", thickness=1.2, color=DOC_BORDER_COLOR, spaceBefore=1, spaceAfter=0))
    flow.append(Spacer(1, 4 * mm))

    supplier_block = (
        f"<b>Dodavatel:</b><br/>{_esc(SUPPLIER['name'])}<br/>{_esc(SUPPLIER['street'])}<br/>"
        f"{_esc(SUPPLIER['city'])}<br/>{_esc(SUPPLIER['country'])}<br/>"
        f"IČ: {_esc(SUPPLIER['ico'])}<br/>DIČ: {_esc(SUPPLIER['dic'])}<br/>"
        f"Tel: {_esc(SUPPLIER['phone'])}<br/>E-mail: {_esc(SUPPLIER['email'])}<br/>{_esc(SUPPLIER['web'])}<br/>"
        f"Číslo účtu: {_esc(SUPPLIER['bank_account'])}"
    )
    recipient_block = (
        f"<b>Příjemce:</b><br/>{_esc(recipient.get('name'))}<br/>"
        f"{_esc(recipient.get('address')).replace(', ', '<br/>')}<br/>"
        f"IČ: {_esc(recipient.get('ico') or '-')}<br/>DIČ: {_esc(recipient.get('dic') or '-')}<br/>"
        f"Tel: {_esc(recipient.get('phone') or '-')}<br/>E-mail: {_esc(recipient.get('email') or '-')}"
    )
    meta_lines = [f"Variabilní symbol: {_esc(doc['variable_symbol'])}"]
    if doc["payment_method_label"]:
        meta_lines.append(f"Forma úhrady: {_esc(doc['payment_method_label'])}")
    meta_lines.append(f"Datum vystavení: {_esc(_fmt_date(doc['issue_date']))}")
    if doc["due_date"]:
        meta_lines.append(f"Datum splatnosti: {_esc(_fmt_date(doc['due_date']))}")
    if doc["taxable_supply_date"]:
        supply_label = "Datum dodání" if doc_type == "delivery_note" else "Datum zdanitelného plnění"
        meta_lines.append(f"{supply_label}: {_esc(_fmt_date(doc['taxable_supply_date']))}")
    meta_block = "<br/>".join(meta_lines)
    if neutral:
        # odesilatel = dealer (snapshot), prijemce = koncovy zakaznik (adresa doruceni), v meta jen data a cislo objednavky dealera; ZADNY nas udaj, cena ani variabilni symbol
        sender_lines = [recipient.get("name")] + (recipient.get("address") or "").split(", ")
        sender_lines += [f"IČ: {recipient['ico']}" if recipient.get("ico") else None, f"DIČ: {recipient['dic']}" if recipient.get("dic") else None,
                         f"Tel: {recipient['phone']}" if recipient.get("phone") else None, f"E-mail: {recipient['email']}" if recipient.get("email") else None]
        supplier_block = "<b>Odesílatel:</b><br/>" + "<br/>".join(_esc(x) for x in sender_lines if x)
        recipient_block = "<b>Příjemce:</b><br/>" + _esc((delivery or {}).get("address")).replace(", ", "<br/>")
        meta_lines = [f"Datum vystavení: {_esc(_fmt_date(doc['issue_date']))}"]
        if doc["taxable_supply_date"]:
            meta_lines.append(f"Datum dodání: {_esc(_fmt_date(doc['taxable_supply_date']))}")
        if recipient.get("reference"):
            meta_lines.append(f"Číslo objednávky: {_esc(recipient['reference'])}")
        meta_block = "<br/>".join(meta_lines)

    header_table = Table(
        [[_P(supplier_block, normal), _P(recipient_block, normal)],
         [_P(meta_block, normal), ""]],
        colWidths=[85 * mm, 85 * mm],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.75, DOC_BORDER_COLOR),
        ("LINEAFTER", (0, 0), (0, -1), 0.5, DOC_BORDER_COLOR),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, DOC_BORDER_COLOR),
    ]))
    flow.append(header_table)
    flow.append(Spacer(1, 4 * mm))

    if delivery and delivery.get("address") and not neutral:
        flow.append(_P(f"<b>Doručovací adresa:</b> {_esc(delivery['address'])}", normal))
        flow.append(Spacer(1, 3 * mm))

    # "NEPLAŤTE!" u VDD se vykresluje jako velky napis POD tabulkou (viz
    # nize), ne jako obycejna poznamka tady nahore - jinak by se
    # zobrazilo 2x.
    if doc["note"] and doc_type != "payment_tax_document":
        flow.append(_P(_esc(doc["note"]), normal))
        flow.append(Spacer(1, 2 * mm))

    # bot5, 2026-09-28 (Robert primo, vzory Shoptet: "důležitá je ta
    # část... zachovávat strukturu") - Shrnutí/Zaokrouhlení/odpocet
    # zalohy/K ZAPLACENI uz NEJSOU samostatna tabulka s vlastnimi sirkami
    # sloupcu (drive se vizualne netrefovala pod sloupce polozek nahore)
    # - jsou to DALSI RADKY TEHOZ stolu, s hodnotami ve STEJNYCH sloupcich
    # jako radky polozek (presne jak to dela vzor - "Shrnutí" ma svoje
    # cisla pod "Cena"/"DPH"/"Celkem vč. DPH", ne v samostatnem bloku).
    n_summary_rows = 0
    first_summary_row_idx = None
    if doc_type == "delivery_note":
        head = ["Položka", "Množství"]
        table_rows = [head]
        for it in items:
            table_rows.append([_P(_esc(it["name"]), item_name_style), _fmt_qty_unit(it)])
        col_widths = [140 * mm, 35 * mm]
    elif doc_type == "payment_tax_document":
        head = ["Položky dodávky", "DPH %", "bez DPH", "DPH", "Celkem"]
        table_rows = [head]
        for it in items:
            table_rows.append([
                _P(_esc(it["name"]), item_name_style), f"{it['vat_rate']} %", _fmt_czk(it["unit_price_net"]),
                _fmt_czk(it["vat_amount"]), _fmt_czk(it["line_total_gross"]),
            ])
        # bot5, 2026-09-28: posledni sloupec rozsiren (20->30mm) - tucne
        # 9pt "Celkem" na jedinem radku VDD se do puvodnich 25mm nevesla
        # a prekryvala se se sousednim sloupcem "DPH" (zivy nalez z
        # vygenerovaneho PDF, ne jen dohad).
        col_widths = [83 * mm, 14 * mm, 23 * mm, 20 * mm, 30 * mm]
        # Zadna samostatna Shrnuti radka (VDD ma vzdy jen 1 polozku, viz
        # create_payment_tax_document) - posledni sloupec POSLEDNIHO
        # (jedineho) radku polozky se jen zvyrazni tucne, presne jako vzor.
    elif doc_type == "proforma_invoice":
        head = ["Položky dodávky", "Množství", "Cena za m.j.", "Cena", "Cena celkem"]
        table_rows = [head]
        for it in items:
            table_rows.append([
                _P(_esc(it["name"]), item_name_style), _fmt_qty_unit(it), _fmt_czk(it["unit_price_net"]),
                _fmt_czk(it["line_total_net"]), _fmt_czk(it["line_total_gross"]),
            ])
        col_widths = [75 * mm, 18 * mm, 24 * mm, 24 * mm, 30 * mm]
        first_summary_row_idx = len(table_rows)
        table_rows.append(["Shrnutí", "", "", "", _fmt_czk(doc["total_with_vat_czk"])])
        # Vyse zalohy (bot5, 2026-09-28: dnes vzdy 100 % - system jeste
        # nema konfigurovatelnou castecnou zalohu, viz Robertuv vzor
        # "u zálohy např 60%" jako PRINCIP, ne jako uz hotova funkce).
        table_rows.append(["Výše zálohy", "", "", "", "100 %"])
        table_rows.append(["K ZAPLACENÍ", "", "", "", _fmt_czk(doc["amount_due_czk"])])
        n_summary_rows = len(table_rows) - first_summary_row_idx
    else:  # invoice
        head = ["Položky dodávky", "Množství", "Cena za m.j.", "Cena", "DPH %", "DPH", "Celkem vč. DPH"]
        table_rows = [head]
        for it in items:
            table_rows.append([
                _P(_esc(it["name"]), item_name_style), _fmt_qty_unit(it), _fmt_czk(it["unit_price_net"]),
                _fmt_czk(it["line_total_net"]), f"{it['vat_rate']} %",
                _fmt_czk(it["vat_amount"]), _fmt_czk(it["line_total_gross"]),
            ])
        # Robert 2026-07-31 ("seriozne vypadat") - puvodni sirky (15/18mm)
        # nechavaly zahlavi "Mnozstvi"/"DPH" tak natesno, ze se tucny text
        # vizualne dotykal sousedniho sloupce - rozsireno na ukor prvniho
        # (nejsirsiho) sloupce, ktery ma stale dost mista na nazvy polozek.
        # bot5, 2026-09-28: posledni sloupec dal rozsiren (25->30mm), stejny
        # duvod jako u VDD - tucny K ZAPLACENI radek potreboval vic mista.
        col_widths = [50 * mm, 18 * mm, 19 * mm, 19 * mm, 12 * mm, 19 * mm, 30 * mm]
        first_summary_row_idx = len(table_rows)
        table_rows.append([
            "Shrnutí", "", "", _fmt_czk(doc["total_without_vat_czk"]), "",
            _fmt_czk(doc["total_vat_czk"]), _fmt_czk(doc["total_with_vat_czk"]),
        ])
        if doc["rounding_czk"]:
            table_rows.append(["Zaokrouhlení", "", "", "", "", "", _fmt_czk(doc["rounding_czk"])])
        if doc["advance_deduction_czk"]:
            # bot5, 2026-09-28: "Uhrazená záloha" misto drivejsiho natvrdo
            # "Zálohová faktura" - odkazovane cislo uz nemusi byt vzdy
            # zalohova faktura, muze to byt i VDD (viz create_invoice,
            # castka se ted odecita z REALNE prijate platby, ne jen z
            # pozadovane castky na zalohovce).
            table_rows.append([
                f"Uhrazená záloha - Kód: {doc['advance_document_number']}", "", "", "", "", "",
                "-" + _fmt_czk(doc["advance_deduction_czk"]),
            ])
        table_rows.append(["K ZAPLACENÍ", "", "", "", "", "", _fmt_czk(doc["amount_due_czk"])])
        n_summary_rows = len(table_rows) - first_summary_row_idx

    items_table_style = [
        ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f3e4d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        # Robert 2026-07-31 ("seriozne vypadat") - hlavicky sloupcu jako
        # "Cena za m.j."/"Celkem vc. DPH" jsou v 8pt tucnem pismu SIRSI
        # nez sloupce u faktury (7 uzkych sloupcu) - zmereno primo
        # stringWidth() - orezany/dotykajici se text pusobil neseriozne.
        # Mensi font+odsazeni JEN pro zahlavi (0. radek) to spolehlive
        # vejde (overeno vizualne renderem), datove radky zustavaji 8pt.
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("LEFTPADDING", (0, 0), (-1, 0), 3),
        ("RIGHTPADDING", (0, 0), (-1, 0), 3),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    # bot5, 2026-09-28: 9pt (ne 11pt) - zivy render ukazal, ze 11pt tucne
    # "213 274,00 Kč" i v rozsirenem sloupci prekypovalo do sousedniho
    # sloupce. Tucne pismo samo o sobe staci na vizualni zvyrazneni.
    if doc_type == "payment_tax_document":
        # Jediny radek polozky = i souhrn (viz vyse) - posledni bunka
        # (Celkem) tucne, presne jako vzor.
        last_row = len(table_rows) - 1
        items_table_style += [
            ("FONTNAME", (-1, last_row), (-1, last_row), FONT_BOLD),
            ("FONTSIZE", (-1, last_row), (-1, last_row), 9),
        ]
    if n_summary_rows:
        # Cudlik nad souhrnnymi radky (oddeluje je od polozek) + posledni
        # radek (K ZAPLACENI) tucne - stejny vzor jako drivejsi samostatna
        # summary_table, ted uz jen jako radky stejneho stolu.
        last_row = len(table_rows) - 1
        items_table_style += [
            ("LINEABOVE", (0, first_summary_row_idx), (-1, first_summary_row_idx), 0.6, colors.black),
            ("FONTNAME", (0, last_row), (-1, last_row), FONT_BOLD),
            ("FONTSIZE", (0, last_row), (-1, last_row), 9),
            ("GRID", (0, first_summary_row_idx), (-1, -1), 0, colors.white),
            ("LINEBELOW", (0, first_summary_row_idx), (-1, -1), 0, colors.white),
        ]

    items_table = Table(table_rows, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle(items_table_style))
    flow.append(items_table)
    flow.append(Spacer(1, 4 * mm))

    if doc_type == "delivery_note":
        # Dodaci list nema ceny/DPH (viz create_delivery_note) - misto
        # Shrnuti/K ZAPLACENI je tu prostor pro podpis prevzeti.
        flow.append(Spacer(1, 10 * mm))
        sign_table = Table(
            [["Vydal:", "Převzal(a):"], ["", ""], ["podpis, datum", "podpis, datum"]],
            colWidths=[85 * mm, 85 * mm],
        )
        sign_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 2), (-1, 2), 7),
            ("TEXTCOLOR", (0, 2), (-1, 2), colors.grey),
            ("LINEABOVE", (0, 2), (-1, 2), 0.4, colors.black),
            ("TOPPADDING", (0, 1), (-1, 1), 14 * mm),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 2), (-1, 2), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("BOX", (0, 0), (-1, -1), 0.75, DOC_BORDER_COLOR),
            ("LINEAFTER", (0, 0), (0, -1), 0.5, DOC_BORDER_COLOR),
        ]))
        flow.append(sign_table)
        flow.append(Spacer(1, 4 * mm))
    elif doc_type == "payment_tax_document":
        # Robert primo, vzor proofPayment_vdd...: velky "NEPLAŤTE!" napis
        # pod tabulkou (vzor ma diagonalni vodoznak pres cely dokument -
        # zjednoduseno na velky vystredeny text, stejne sdeleni).
        neplatte_style = ParagraphStyle(
            "neplatte", parent=styles["Normal"], fontName=FONT_BOLD, fontSize=28,
            textColor=colors.HexColor("#bbbbbb"), alignment=1,
        )
        flow.append(Spacer(1, 8 * mm))
        flow.append(_P("NEPLAŤTE!", neplatte_style))
        flow.append(Spacer(1, 8 * mm))

        # bot5, 2026-09-28 (Robert primo: "v samotné zálohové faktuře se
        # DPH neukazuje") - zalohova faktura nema NIKDE zadnou zminku DPH
        # (DPH je zahrnute v cenach, jen se nerozepisuje - pravidlo 1),
        # vc. tohohle souhrnneho bloku, i kdyz stary Shoptet vzor ho mel.
        vb = vat_breakdown[0] if (vat_breakdown and doc_type != "proforma_invoice") else None
        if vb:
            # bot5, 2026-09-28 (Robert primo, vzory) - chybel sloupec "DPH"
            # (samotna castka dane) - vzory maji vzdy 4 sloupce (bez DPH /
            # sazba / DPH / celkem), ne 3.
            flow.append(_P("<b>Součet DPH:</b>", normal))
            vat_table = Table(
                [["Cena bez DPH", "Sazba DPH", "DPH", "Celková cena vč. DPH"],
                 [_fmt_czk(vb["base_czk"]), f"{vb['rate']} %", _fmt_czk(vb["vat_czk"]), _fmt_czk(vb["total_czk"])]],
                colWidths=[45 * mm, 25 * mm, 30 * mm, 40 * mm],
            )
            vat_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("BOX", (0, 0), (-1, -1), 0.75, DOC_BORDER_COLOR),
            ]))
            flow.append(vat_table)
            flow.append(Spacer(1, 6 * mm))

    if not neutral:
        flow.append(_P(f"Vystavil: {_esc(doc['issued_by'])}", small))
        flow.append(_P("Vystaveno systémem konfigurátoru logiman.cz", small))

    pdf.build(flow)
    return buf.getvalue()
