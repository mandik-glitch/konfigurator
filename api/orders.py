"""
Backend modul pro objednavky (e-shop checkout nad katalogem shop_products).

Autor: bot3 (Claude / Cowork), 2026-07-25.
Kontext a duvod existence tohoto souboru jako SAMOSTATNEHO modulu (misto
primeho zapsani do app.py): viz KOORDINACE_BOTU.md a zaznam v
AGENTS_LOG.md ze dne 2026-07-25 (bot3) - tahle session nema z bezpecnostnich
duvodu sandboxu pristup na server (SSH port 22 ani port 8090 aplikace jsou
z ni blokovane), takze kod byl navrzen a otestovan lokalne (syntax check +
mock DB harness), ale NEBYL primo nasazen. Nasazujici osoba/bot postupuje
podle DEPLOY.md v teto slozce.

Aktivace: modul se registruje primo na existujici Flask `app` instanci z
app.py (stejna konvence jako zbytek projektu - zadne Flask Blueprints).
Na konec app.py (uplne na konec souboru, AZ PO definici vsech ostatnich
route a AZ PO `app = Flask(__name__)` atd.) staci pridat:

    import orders  # noqa: F401 - registruje /api/orders + /api/admin/orders

Tabulky (DDL viz sql/2026-07-25_orders_schema.sql - je potreba spustit
migraci na DB PRED prvnim restartem se zapnutym timhle modulem):
  shop_orders               - hlavicka objednavky (1 radek = 1 objednavka)
  shop_order_items          - polozky objednavky (snapshot produktu+ceny
                               v okamziku objednani, aby se historie
                               objednavky nezmenila pri pozdejsi zmene ceny
                               nebo smazani produktu)
  shop_order_status_history - auditni historie zmen stavu (kdo/kdy/na co)

Datovy a stavovy model je zdokumentovany v README_OBJEDNAVKY.md v teto
slozce (API kontrakt, povolene prechody stavu, priklady requestu).

--- V3 (bot3, 2026-07-25, PRIPRAVENO, ZATIM NENASAZENO) ---
Robert: "skupiny zákazníků, potřebujeme jim přiřadit různou rámcovou
slevu." Pokud ma prihlaseny zakaznik profil (shop_customers) s
prirazenou skupinou (shop_customer_groups.discount_percent), sleva se
serverove aplikuje na cenu KAZDE polozky objednavky (zaokrouhleno na 2
des. mista) - klient zadnou slevu poslat/ovlivnit nemuze. Skupina/sleva
se zaroven ulozi jako snapshot na objednavku (customer_group_name,
customer_discount_percent), aby pozdejsi zmena slevy skupiny nezmenila
historickou objednavku. Vyzaduje migraci
sql/2026-07-25_customer_groups.sql (JESTE NEAPLIKOVANOU na produkci).

--- V4 (bot3, 2026-07-25, PRIPRAVENO, ZATIM NENASAZENO) ---
Robert: "připrav že objednávku lze zadat i ručně." Novy endpoint
POST /api/admin/orders - admin muze zadat objednavku za zakaznika (napr.
telefonicky). Sdili logiku se samoobsluznym POST /api/orders pres
_resolve_and_insert_order() (viz jeji docstring pro presny rozdil).
Vyzaduje uz nasazenou v3 migraci (kvuli slevovym skupinam - rucni
objednavka napojena na ucet se zakaznickym profilem slevu dostane stejne
jako samoobsluzna).

--- V2 (bot3, 2026-07-25, stejny den) ---
Robert rozhodl: "objednávka nelze zadat bez přihlášení" -> zrusen guest
checkout, POST /api/orders ted vyzaduje @login_required. Soucasne pribyly
navazujici moduly cart.py (kosik) a customers.py (fakturacni profil
zakaznika) - viz jejich vlastni docstringy. orders_create() ted umi:
  - vzit polozky primo z kosiku (`"use_cart": true` misto rucniho "items")
  - predvyplnit kontakt/fakturaci z ulozeneho profilu zakaznika (shop_customers),
    pokud v requestu nejsou explicitne poslane
  - zvolit dopravu/platbu (shipping_method_id/payment_method_id) - viz
    shop_shipping_methods/shop_payment_methods, zadna platebni brana
Vyzaduje migraci sql/2026-07-25_orders_v2_customers_cart_shipping.sql.
"""
import io
import json
import math
import re
import threading
from datetime import datetime

from flask import request, jsonify, Response

from app import (
    app, get_conn, login_required, require_permission, current_user,
    log_audit, parse_bulk_ids, bulk_update_fields, bulk_delete,
    get_pagination_args, paginated_query, get_setting, create_party,
)
from products import _cut_service_price_czk, _effective_unit_price, reverse_and_delete_stock_movements
from product_assemblies import _assembly_price_components, _montaz_mista_map

# V6 (bot3, 2026-07-25): top-level import (NE uvnitr funkce) - Flask
# zakazuje registrovat nove routy (@app.get/@app.post v documents.py) po
# obslouzeni prvniho requestu. Kdyby byl import az uvnitr
# _resolve_and_insert_order (lazy, spousteny az pri prvnim vytvoreni
# objednavky za behu), padalo by to prave na tenhle Flask limit (overeno
# testem - "The setup method 'get' can no longer be called..."). Tenhle
# top-level import je bezpecny, protoze `app` uz v app.py existuje v
# okamziku, kdy se orders.py vubec poprve importuje (viz konec app.py).
import documents  # noqa: E402
import customers  # noqa: E402 - V8: find_duplicate_customers() pro admin_orders_create() nize
# V9 (bot3, 2026-07-25): STEJNY duvod jako u `import documents` vyse - byl
# tu puvodne lazy `import emails` UVNITR _send_order_emails()/
# _send_status_change_email(), coz vypadalo bezpecne (emails.py uz je v
# realne appce davno nacteny pres retez v app.py), ALE test_harness/
# run_tests.py (nejstarsi test soubor) importuje jen `orders` - tim padem
# byl `emails` poprve importovan az UVNITR prvniho POST /api/orders
# requestu, tedy PO tom, co uz Flask test klient obslouzil prvni request -
# presne ten samy Flask limit jako u puvodniho bugu s `documents`. Reseni
# je stejne: top-level import (bezpecny, `emails.py` samo importuje zpet
# `documents` - viz jeho docstring, proc to NENI cyklicky problem, kdyz
# zadny z modulu nesahá na atributy toho druheho na urovni modulu, jen az
# uvnitr telech funkci).
import emails  # noqa: E402
# Stejny duvod/vzor jako import documents/customers/emails vyse - top-level,
# ne lazy uvnitr funkce. Potreba pro _delete_one_purchase_order() v
# _delete_orders_cascade nize (Robert 2026-08-06: smazani objednavky musi
# smazat i navazanou auto-zalozenou nakupni objednavku, viz tamni komentar) -
# znovupouziva uz overenou bezpecnou logiku (vraceni skladu, smazani emailu)
# misto duplikovani.
import purchase_orders  # noqa: E402

# ---------------------------------------------------------------------------
# Stavovy model
# ---------------------------------------------------------------------------

ORDER_STATUSES = ("nova", "potvrzena", "ceka_na_zbozi", "pripravit", "expedovana", "fakturovana", "zrusena")

STATUS_LABELS_CZ = {
    "nova": "Nová",
    "potvrzena": "Potvrzená",
    "ceka_na_zbozi": "Čeká na zboží",
    "pripravit": "Připravit",
    "expedovana": "Expedovaná",
    "fakturovana": "Fakturovaná",
    "zrusena": "Zrušená",
}

# Stavy, ve kterych je zbozi jiz odecteno ze skladu - pouziva se pro
# spravne doplneni/vraceni zasob pri KAZDE zmene stavu (viz
# admin_orders_update), ne jen pri prvnim potvrzeni. "fakturovana" je
# tu take (zbozi zustava vydane, jen se vystavila faktura - fakturace
# sama o sobe sklad nijak nemeni).
STOCK_DEDUCTED_STATUSES = {"potvrzena", "pripravit", "expedovana", "fakturovana"}

# Povolene prechody mezi stavy (jednosmerny produkcni tok + moznost
# zruseni z kterehokoli aktivniho stavu). "fakturovana" a "zrusena" jsou
# koncove stavy - z nich uz dal nejde prejit (pripadnou opravu chyby
# resi admin rucne v DB, ne pres API - je to zamerne konzervativni).
# Robert 2026-07-31: novy stav "ceka_na_zbozi" - objednavka, kterou nejde
# potvrdit, protoze na ni nestaci sklad ("se zbozi objednat takze bude ve
# stavu ceka na zbozi"). NENI mezi STOCK_DEDUCTED_STATUSES - dokud se ceka,
# nic se neodepisuje. Ven z nej vede automaticke preklopeni pri naskladneni
# (viz try_release_waiting_orders nize) nebo rucni zasah.
# Retez "pripravit"/"expedovana"/"fakturovana" je rucni (Robert: "stav
# expedovat dela skladnik rucne nasleduje stav fakturovana tento stav
# dela rucne ucetni") - system tu nic sam neprepina, jen hlida povoleny
# smer prechodu (permission sekce "objednavky" resi kdo smi menit stav
# vubec, ne konkretni roli na konkretnim prechodu - viz poznamka u
# admin_orders_update).
ALLOWED_TRANSITIONS = {
    "nova": {"potvrzena", "ceka_na_zbozi", "zrusena"},
    "ceka_na_zbozi": {"potvrzena", "zrusena"},
    "potvrzena": {"pripravit", "zrusena"},
    "pripravit": {"expedovana", "zrusena"},
    # Robert (pres bot3, revize kodu 2026-09-03): zruseni JIZ EXPEDOVANE
    # (fyzicky odeslane) objednavky uz neni povolene - drivejsi
    # {"fakturovana", "zrusena"} umoznovalo zrusit objednavku, ktera uz
    # fyzicky opustila sklad, a _apply_order_update by pritom rovnou tise
    # vratil zbozi na sklad (stock_qty+=qty), i kdyz fyzicky vraceno
    # nebylo. Samostatny tok "vraceni zbozi/reklamace" v projektu zatim
    # NEEXISTUJE (Robert bude pripadne resit jako novou funkci).
    "expedovana": {"fakturovana"},
    "fakturovana": set(),
    "zrusena": set(),
}

# bot18, 2026-09-04/05 (Robert pres bot3, krok 4/5 schvalenych doporuceni
# z Dolibarr/ERPNext rozboru - ADITIVNI dvouosy model delivery_state/
# billing_state vedle `status`, viz sql/2026-09-04_shop_orders_delivery_
# billing_state.sql). `status` zustava JEDINYM zdrojem pravdy pro
# ALLOWED_TRANSITIONS/STOCK_DEDUCTED_STATUSES/VDD gate/admin UI - tahle
# funkce jen udrzuje dve NOVE, zatim nikde nepouzivane sloupce
# konzistentni s kazdou budouci zmenou statusu, stejne mapovani jako
# jednorazovy backfill (scripts/2026-09-04_shop_orders_state_backfill.py
# MAPPING - "fakturovana" je dosazitelna jen z "expedovana", "zrusena"
# neni dosazitelna z "expedovana"/"fakturovana", viz ALLOWED_TRANSITIONS
# vyse). Volat pri KAZDEM zapisu shop_orders.status (INSERT i UPDATE),
# aby obe osy nikdy nezestaraly.
def _states_for_status(status):
    if status == "fakturovana":
        return "expedovana", "fakturovano"
    if status == "zrusena":
        return None, "nevyfakturovano"
    return status, "nevyfakturovano"


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Pomocne funkce
# ---------------------------------------------------------------------------

def _money(v):
    return float(v) if v is not None else None


def _dt(v):
    return v.isoformat() if v else None


def _serialize_order(row):
    return {
        "id": row["id"],
        "order_number": row["order_number"],
        "status": row["status"],
        "status_label": STATUS_LABELS_CZ.get(row["status"], row["status"]),
        "is_urgent": bool(row.get("is_urgent")),
        "user_id": row["user_id"],
        "customer_name": row["customer_name"],
        "customer_email": row["customer_email"],
        "customer_phone": row["customer_phone"],
        "delivery_address": row["delivery_address"],
        "delivery_zip": row["delivery_zip"],
        "note": row["note"],
        "admin_note": row["admin_note"],
        "customer_group_name": row["customer_group_name"],
        "customer_discount_percent": _money(row["customer_discount_percent"]),
        "billing_name": row["billing_name"],
        "billing_ico": row["billing_ico"],
        "billing_dic": row["billing_dic"],
        "billing_address": row["billing_address"],
        "shipping_method_name": row["shipping_method_name"],
        "shipping_price_czk": _money(row["shipping_price_czk"]),
        "payment_method_name": row["payment_method_name"],
        "payment_price_czk": _money(row["payment_price_czk"]),
        "total_czk": _money(row["total_czk"]),
        "bank_paid": bool(row.get("bank_paid")),
        "bank_paid_at": _dt(row.get("bank_paid_at")),
        # bot5, 2026-09-28 (Robert primo: "platbu jsem oznacil za
        # přijatou, vytvořil se doklad k platbě, ale v přehledu je
        # objednávka jako neuhrazená, oprav návaznosti") - "Uhrazeno"
        # sloupec v seznamu cetl JEN bank_paid (automaticke parovani
        # bankovnich vypisu podle VS), ne rucni potvrzeni platby (VDD
        # vystavene pres "Označit platbu jako přijatou" -
        # payment_received_at/payment_received_total_czk). Frontend teď
        # bere OBOJI.
        "payment_received_at": _dt(row.get("payment_received_at")),
        "payment_received_total_czk": _money(row.get("payment_received_total_czk")),
        # bot5, 2026-10-02 (dealersky program): puvod objednavky pro admina - dealer_id + cesta ('our' = zakaznik z odkazu dealera, provize; 'dealer' = objednavka
        # z webu dealera pres API za dealerskou cenu, zbozi jde koncovemu zakaznikovi) a external_ref dealera. Jen admin, zakaznicka serializace to nema.
        "dealer_id": row.get("dealer_id"),
        "order_path": row.get("order_path"),
        "dealer_external_ref": row.get("dealer_external_ref"),
        # bot5, 2026-10-03 (Robert pres bot3: "priznak, odkud prisla, ve viditelnem sloupci"): puvod objednavky = host a jazyk mini-shopu (order_host, order_lang), NULL = hlavni e-shop;
        # shipping_review = doprava ke schvaleni zamestnancem (mini-shop), vat_mode/vat_check = rezim DPH a vysledek overeni IC DPH (VIES). Jen admin serializace.
        "order_host": row.get("order_host"),
        "order_lang": row.get("order_lang"),
        "origin_label": _origin_label(row),
        "shipping_review": int(row.get("shipping_review") or 0),
        "vat_mode": row.get("vat_mode"),
        "vat_check": row.get("vat_check"),
        "created_at": _dt(row["created_at"]),
        "updated_at": _dt(row["updated_at"]),
    }


def _origin_label(row):
    """Puvod pro admin prehled: 'host - jazyk' mini-shopu, hlavni e-shop = 'e-shop'."""
    host = row.get("order_host")
    return f"{host} \u00b7 {row.get('order_lang')}" if host and row.get("order_lang") else (host or "e-shop")


def _serialize_order_for_customer(row):
    """Ozeznany podmnozina _serialize_order() pro zakaznickou self-service
    cestu (bot18, 2026-09-05, "moje objednavky") - VYNECHAVA admin_note
    (interni poznamky pro personal, muzou obsahovat neco jako "podezrela
    objednavka, overit" - zakaznik tohle videt nema) a customer_group_name/
    customer_discount_percent (interni cenotvorba)."""
    return {
        "id": row["id"], "order_number": row["order_number"],
        "status": row["status"], "status_label": STATUS_LABELS_CZ.get(row["status"], row["status"]),
        "delivery_address": row["delivery_address"], "delivery_zip": row["delivery_zip"],
        "note": row["note"],
        "shipping_method_name": row["shipping_method_name"],
        "shipping_price_czk": _money(row["shipping_price_czk"]),
        "payment_method_name": row["payment_method_name"],
        "payment_price_czk": _money(row["payment_price_czk"]),
        "total_czk": _money(row["total_czk"]),
        "created_at": _dt(row["created_at"]),
    }


def _serialize_konfigurace(raw, plna):
    # bot5, 2026-10-02: konfigurace sestavy: snimek konfigurace na radku objednavky. Zakaznik vidi jen kod a souhrn voleb, kusovnik a cenovy souhrn (nakladova struktura) jen zamestnanec.
    if not raw:
        return None
    import konfigurace_kosik
    return konfigurace_kosik.nacti_vyber_snimku(raw) if plna else konfigurace_kosik.zakaznicky_snimek(raw)


def _serialize_item(row, misto_labels=None, plna_konfigurace=False):
    cut_pieces = None
    raw_cut_pieces = row.get("cut_pieces_json")
    if raw_cut_pieces:
        try:
            cut_pieces = json.loads(raw_cut_pieces)
        except (TypeError, ValueError):
            cut_pieces = None
    return {
        "id": row["id"],
        "product_id": row["product_id"],
        "product_name": row["product_name_snapshot"],
        "unit_price_czk": _money(row["unit_price_czk"]),
        "qty": row["qty"],
        # Dodaci listy (Robert primo, 2026-09-16: "položky které se
        # vydali a které ještě ne") - cisty procesni pokrok, NEMENI
        # shop_products.stock_qty (ten uz resi STOCK_DEDUCTED_STATUSES
        # na urovni cele objednavky, viz komentar u sloupce v sql/
        # 2026-09-16_shop_order_items_qty_dispatched.sql).
        "qty_dispatched": row.get("qty_dispatched") or 0,
        "cut_pieces": cut_pieces,
        "line_total_czk": _money(row["line_total_czk"]),
        # Snapshot volby varianty/montaze/boxu v okamziku objednani
        # (Robert 2026-09-13: "přidá se informace do objednávky") - viz
        # komentar u INSERT INTO shop_order_items v _resolve_and_insert_order.
        "assembly_kod_snapshot": row.get("assembly_kod_snapshot"),
        "montaz_zvolena": bool(row.get("montaz_zvolena")),
        "montaz_czk_snapshot": _money(row.get("montaz_czk_snapshot")) if row.get("montaz_czk_snapshot") is not None else None,
        "montaz_misto_snapshot": row.get("montaz_misto_snapshot"),
        "montaz_misto_label": (misto_labels or {}).get(row.get("montaz_misto_snapshot")),
        "bez_boxu": bool(row.get("bez_boxu")),
        "boxy_czk_snapshot": _money(row.get("boxy_czk_snapshot")) if row.get("boxy_czk_snapshot") is not None else None,
        "configuration_code": row.get("configuration_code"),
        "configuration": _serialize_konfigurace(row.get("configuration_json"), plna_konfigurace),
    }


# bot5, 2026-09-26 (Robert: "nesmí vzniknout díra v číslování žádné
# číselné řady", incident objednávka 191): order_number uz NENI odvozene
# z shop_orders.id (smazani radku = navzdy ztracene cislo, presne to se
# stalo). Vlastni atomicka rada (shop_order_number_sequence, FOR UPDATE
# zamek, stejny vzor jako documents._next_document_number()/
# quotes._next_quote_number()), rocni reset (Robert 2026-09-26, stejna
# rodina jako novy format dokladu). Format displaye zustava beze zmeny
# (OBJ-{rok}-{poradi:05d}) - jen zdroj cisla se meni.
#
# Testovaci objednavky (Robert: "testovací je vždy s emailem
# robert.mandik@gmail.com") SMI byt tvrde smazany - jejich cislo se v tom
# pripade vrati do shop_order_number_released, aby se nabidlo znovu
# DRIVE nez prubezny citac postoupi dal (_next_order_number nize).
# Normalni objednavky se nemazou, jen stavem 'zrusena' (viz
# admin_orders_update) - jejich cislo tedy z teto rady NIKDY nezmizi.
TEST_ORDER_EMAIL = "robert.mandik@gmail.com"

_ORDER_NUMBER_RE = re.compile(r"^OBJ-(\d{4})-(\d{5})$")


def _next_order_number(cur, year):
    """Vrati dalsi volne poradove cislo pro danou rocni radu - nejdriv
    nejmensi uvolnene cislo (test. objednavka smazana driv), pak teprve
    prubezny citac. FOR UPDATE zamyka prislusny radek/podmnozinu -
    bezpecne pri soubehu (stejny vzor jako ostatni atomicke rady v
    projektu)."""
    cur.execute(
        "SELECT seq_number FROM shop_order_number_released WHERE seq_year=%s "
        "ORDER BY seq_number ASC LIMIT 1 FOR UPDATE",
        (year,),
    )
    released = cur.fetchone()
    if released:
        seq_number = released["seq_number"]
        cur.execute(
            "DELETE FROM shop_order_number_released WHERE seq_year=%s AND seq_number=%s",
            (year, seq_number),
        )
        return seq_number
    cur.execute("SELECT next_number FROM shop_order_number_sequence WHERE seq_year=%s FOR UPDATE", (year,))
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "INSERT INTO shop_order_number_sequence (seq_year, next_number) VALUES (%s,2)",
            (year,),
        )
        return 1
    cur.execute(
        "UPDATE shop_order_number_sequence SET next_number=next_number+1 WHERE seq_year=%s",
        (year,),
    )
    return row["next_number"]


def _release_order_number(cur, order_number):
    """Vrati cislo smazane TESTOVACI objednavky do fondu. Tiche no-op u
    stareho/importovaneho formatu (napr. '26080054...') - ten neni
    soucasti teto rady, neni co uvolnovat."""
    m = _ORDER_NUMBER_RE.match(order_number or "")
    if not m:
        return
    year, seq_number = int(m.group(1)), int(m.group(2))
    cur.execute(
        "INSERT INTO shop_order_number_released (seq_year, seq_number) VALUES (%s,%s) "
        "ON DUPLICATE KEY UPDATE released_at=released_at",
        (year, seq_number),
    )


def _generate_order_number(cur, created_at):
    year = created_at.year if created_at else datetime.utcnow().year
    seq_number = _next_order_number(cur, year)
    return f"OBJ-{year}-{seq_number:05d}"


def _is_test_order(row):
    """Testovaci = uz existujici prizna is_test=1 (stary import/backfill),
    NEBO Robertuv vlastni e-mail (2026-09-26: "testovací je vždy s
    emailem robert.mandik@gmail.com") - jedine dve objednavky, ktere je
    v adminu jeste dovoleno tvrde smazat."""
    return bool(row.get("is_test")) or (row.get("customer_email") or "").strip().lower() == TEST_ORDER_EMAIL


def create_bare_order_from_lead(cur, customer_name, customer_email, admin_note):
    """Vytvori MINIMALNI objednavku BEZ POLOZEK - volano z api/support.py
    trideni e-mailu (Robert 2026-08-22: "kdyz to navrhne jako objednavku
    tak to musi pri schvaleni skoncit v objednavkach!" - PREKONAVA
    drivejsi zamerne "nedela" v _link_conversation_to_order, kdyz cislo
    objednavky nenajde/neodpovida zadne existujici).

    Na rozdil od _resolve_and_insert_order (ktera VYZADUJE aspon 1
    polozku, viz jeji "items"-kontrola vyse) tahle zalozi jen holy
    zaznam se stavem 'nova', bez polozek/dopravy/platby/fakturacniho
    snapshotu - nespolehlivy parsing volneho textu e-mailu by vedl k
    nahodnym/spatnym polozkam a cenam, admin je doplni RUCNE (pridat
    polozku, upravit pocet ks - viz TASKS.md 2026-08-22 "Hotovo").
    admin_note = puvodni text e-mailu, at admin vidi z ceho objednavka
    vznikla. Zadny FK na uzivatelsky ucet (user_id NULL) - konverzace
    z e-mailu nemusi mit napojeny app_users ucet vubec.

    Vraci (order_id, order_number)."""
    if not customer_email:
        raise ValueError("customer_email je povinny.")
    cur.execute(
        "INSERT INTO shop_orders (order_number, status, delivery_state, billing_state, is_urgent, user_id, customer_name, customer_email, admin_note, total_czk) "
        "VALUES ('', 'nova', 'nova', 'nevyfakturovano', 0, NULL, %s, %s, %s, 0)",
        (customer_name or customer_email, customer_email, admin_note),
    )
    order_id = cur.lastrowid
    cur.execute("SELECT created_at FROM shop_orders WHERE id=%s", (order_id,))
    created_at = cur.fetchone()["created_at"]
    order_number = _generate_order_number(cur, created_at)
    cur.execute("UPDATE shop_orders SET order_number=%s WHERE id=%s", (order_number, order_id))
    cur.execute(
        "INSERT INTO shop_order_status_history (order_id, status, changed_by, note) "
        "VALUES (%s, 'nova', NULL, 'Objednávka založena automaticky z e-mailu (třídění) - bez položek, doplní admin ručně.')",
        (order_id,),
    )
    return order_id, order_number


def create_order_from_scene_offer(cur, offer, *, name, company_ico, company_name, company_dic,
                                   company_address, contact_email, contact_phone, total_czk,
                                   qty_multiplier=1, extra_note=None, extra_items=None):
    """Vytvori objednavku z prijate online nabidky (scene_offers) -
    Robert primo, 2026-09-14 (pres bot16): "v pripade objednani se
    zadane udaje propisuji do adresare zakazniku a do objednavek" +
    (primo): "je potreba u objednavky evidovat VS nabidky, resp VS
    platby, podle ktere se to pak sparuje". VS PLATBY je uz existujici
    mechanismus (shop_documents.variable_symbol, vznika az pri
    vystaveni zalohove faktury pro objednavku - viz documents.py,
    tenhle kod ho nijak nenahrazuje). VS NABIDKY nemela dosud zadny
    protejsek - `shop_orders.source_scene_offer_id` (sql/2026-09-14_
    shop_orders_source_scene_offer.sql) je ta trvala vazba zpet na
    puvodni nabidku, dostupna hned pri zalozeni objednavky, driv nez
    pripadne vznikne VS platby.

    Volano ZE STEJNE TRANZAKCE jako INSERT do scene_offer_acceptances
    (api/scene_offers.py::public_offer_accept), PRED commit - prijeti
    nabidky a vznik objednavky maji byt atomicke (bud obojí, nebo nic).

    Zakaznik: dedup podle ICO/e-mailu stejnym helperem jako
    crm.py::crm_admin_lead_convert (customers.find_duplicate_customers).
    Na rozdil od crm_admin_lead_convert (ktery jen NAVRHNE shodu a ceka
    na potvrzeny klik admina) tady zalozeni MUSI byt rovnou automaticke -
    zakaznik prave kliknul "Souhlasím/objednávám" na verejne strance,
    zadny admin u toho neni.

    Polozky: Robert primo, 2026-09-16 ("cena se doplnovala rucne, ale
    seznam dilu se musi automaticky propisovat") - `offer["items"]` SE
    ted rozepisuje do shop_order_items automaticky (drive se nekopirovalo
    vubec, admin musel dopisovat rucne podle prilozene nabidky - puvodni
    opatrnost z 2026-09-14, "bez ziveho otestovani"). Kazda polozka
    `offer["items"]` uz ma tvar velmi blizky shop_order_items (name/dim/
    qty/unit_price/total/product_id, viz nabidka-online.html cenova
    tabulka - `product_id` overeno, ze je to skutecne `shop_products.id`,
    ne jiny ciselnik) - mapuje se primo, bez cut_kind/material_key/
    assembly_id/montaz_*/bez_boxu (ty patri jen "rež si sam" e-shop
    kosiku, sestava ze sceny je uz hotova konfigurace, ne rozestavana
    zakaznikem). `qty_multiplier` (pocet objednanych KUSU CELE SESTAVY,
    Robert 2026-09-14 "moznost objednat vice ks vyrobku") nasobi qty i
    total KAZDE polozky - `offer["items"]` sam o sobe je vzdy za JEDEN
    kus sestavy, bez ohledu na to, kolik kusu zakaznik nakonec zvolil.
    `total_czk` (povinny parametr) zustava souhrnna castka pro hlavicku
    objednavky (uz vc. DPH/dopravy) - separatni od souctu polozek
    (ktery je bez DPH/dopravy), tahle funkce cenovou logiku hlavicky
    sama nezna, jen ji preberame hotovou od volajiciho.

    Trvala testovaci nabidka (TEST_OFFER_NUMBER) sem nemá vubec chodit -
    volajici (scene_offers.py) ji filtruje driv, at neplodi realne
    zakaznicke ucty/objednavky pri kazdem otestovani tlacitka.

    Vraci (order_id, order_number)."""
    customer_type = "firma" if company_name else "osoba"
    matches = customers.find_duplicate_customers(
        cur, email=contact_email, ico=company_ico, dic=company_dic,
        full_name=name, phone=contact_phone,
    )
    if matches:
        user_id = matches[0]["user_id"]
        cur.execute("SELECT party_id FROM app_users WHERE id=%s", (user_id,))
        row = cur.fetchone()
        party_id = row["party_id"] if row else None
    else:
        clean, err = customers._validate_and_clean({
            "customer_type": customer_type, "full_name": name, "company_name": company_name,
            "ico": company_ico, "dic": company_dic, "email": contact_email, "phone": contact_phone,
            "billing_address": company_address, "delivery_same_as_billing": True,
        }, existing_email_fallback=contact_email)
        if err:
            # Uz validovano driv na verejnem endpointu (IC0 8 cislic,
            # format e-mailu...) - sem by se melo dostat jen ve
            # vyjimecnych hranicnich pripadech.
            raise ValueError(f"Nepodařilo se založit zákazníka: {err}")
        cur.execute("SELECT id FROM app_users WHERE email=%s", (clean["email"],))
        existing_user = cur.fetchone()
        if existing_user:
            user_id = existing_user["id"]
            cur.execute("SELECT party_id FROM app_users WHERE id=%s", (user_id,))
            party_id = cur.fetchone()["party_id"]
        else:
            party_id = create_party(
                cur, party_type=clean["customer_type"], full_name=clean["full_name"],
                primary_email=clean["email"], primary_phone=clean["phone"],
                ico=clean["ico"], dic=clean["dic"],
            )
            random_password = customers.secrets.token_urlsafe(24)
            cur.execute(
                "INSERT INTO app_users (email, password_hash, name, role, active, party_id) "
                "VALUES (%s,%s,%s,'user',1,%s)",
                (clean["email"], customers.generate_password_hash(random_password), clean["full_name"], party_id),
            )
            user_id = cur.lastrowid
        cols_sql, placeholders, values = customers._customer_insert_clause(clean)
        cur.execute(
            f"INSERT INTO shop_customers (user_id, party_id, {cols_sql}, group_id, note) "
            f"VALUES (%s, %s, {placeholders}, %s, %s)",
            (user_id, party_id) + values
            + (None, f"Automaticky založeno přijetím online nabídky {offer['offer_number']}."),
        )

    # total_czk je POVINNY parametr od volajiciho, ne odvozeny tady z
    # offer['total_price'] (bot16, 2026-09-14: chysta se moznost
    # objednat vic ks - celkova castka = total_price * qty, tenhle
    # nasobek zna jen volajici, ktery uz stejne pocita QR platbu).
    total = float(total_czk or 0)
    admin_note = (
        f"Objednávka založena automaticky přijetím online nabídky {offer['offer_number']} "
        f"(#{offer['id']}). Souhrnná cena {total:.0f} Kč přebrána z nabídky, položky "
        f"převzaty automaticky - zkontrolujte prosím proti přiložené nabídce."
    )
    if extra_note:                      # bot8 2026-10-06: zvolena montaz (misto + cena) - v total_czk je, v polozkach ne, proto aspon poznamka
        admin_note += f"\n{extra_note}"
    cur.execute(
        "INSERT INTO shop_orders "
        "(order_number, status, delivery_state, billing_state, is_urgent, user_id, party_id, "
        " customer_name, customer_email, customer_phone, delivery_address, "
        " billing_name, billing_ico, billing_dic, billing_address, admin_note, total_czk, "
        " source_scene_offer_id) "
        "VALUES ('', 'nova', 'nova', 'nevyfakturovano', 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (user_id, party_id, name, contact_email, contact_phone, company_address,
         company_name, company_ico, company_dic, company_address, admin_note, total,
         offer["id"]),
    )
    order_id = cur.lastrowid
    cur.execute("SELECT created_at FROM shop_orders WHERE id=%s", (order_id,))
    created_at = cur.fetchone()["created_at"]
    order_number = _generate_order_number(cur, created_at)
    cur.execute("UPDATE shop_orders SET order_number=%s WHERE id=%s", (order_number, order_id))
    cur.execute(
        "INSERT INTO shop_order_status_history (order_id, status, changed_by, note) "
        "VALUES (%s, 'nova', NULL, %s)",
        (order_id, f"Objednávka založena automaticky přijetím online nabídky {offer['offer_number']}."),
    )

    # Polozky (Robert primo, 2026-09-16: "seznam dilu se musi automaticky
    # propisovat") - viz docstring vyse pro zduvodneni mapovani/qty_multiplier.
    try:
        items = json.loads(offer["items"] or "[]")
    except (TypeError, ValueError):
        items = []
    _DIM_MM_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*mm$")
    # bot5, 2026-10-06: nabidka z konfigurace stolu (offer_options.source = configurator) - snimek konfigurace (vyber, neutralni kusovnik, cenovy souhrn, kod) na radek objednavky,
    # jako u kosiku (vyroba na zakazku, product_id NULL); chyba snimku objednavku nikdy nezastavi (loguje se)
    cfg_snimek = None
    try:
        import nabidka_z_konfigurace
        cfg_snimek = nabidka_z_konfigurace.snapshot_pro_objednavku(json.loads(offer.get("offer_options") or "{}"))
    except Exception:
        app.logger.exception("objednavka z nabidky %s: snimek konfigurace se nepodarilo sestavit", offer.get("offer_number"))
    for it in items:
        if not isinstance(it, dict) or not it.get("name"):
            continue
        qty_raw = str(it.get("qty") or "1")
        m = re.match(r"\d+", qty_raw)
        qty = (int(m.group()) if m else 1) * max(1, int(qty_multiplier or 1))
        unit_price = float(it.get("unit_price") or 0)
        line_total = float(it.get("total") or 0) * max(1, int(qty_multiplier or 1))
        dim_match = _DIM_MM_RE.match(str(it.get("dim") or "").strip())
        length_mm = float(dim_match.group(1).replace(",", ".")) if dim_match else None
        # bot5, 2026-09-17 (Robert pres bot3: "rozmery profilu se z
        # nabidky nepropsaly do objednavky") - length_mm uz se ukladal
        # spravne, ale bez cut_kind/material_key api/cutting.py::
        # _classify_items() polozku vubec nezaradi mezi profily k
        # rezani ("if not cut_kind or not material_key: continue") -
        # navenek to vypadalo jako ztraceny rozmer. material_key
        # stejnou metodou jako _cross_key_for_profile() nize (cfg_dily
        # dva nejmensi rozmery, format "AxB") - jen kdyz je produkt
        # skutecne profil (is_profile_material=1) A ma cfg_dily_id A
        # ma znamou delku, jinak zustava NULL/NULL jako dosud (zadny
        # hadany material_key).
        cut_kind = None
        material_key = None
        if it.get("product_id") and length_mm:
            cur.execute(
                "SELECT is_profile_material, cfg_dily_id FROM shop_products WHERE id=%s",
                (it["product_id"],),
            )
            sp = cur.fetchone()
            if sp and sp["is_profile_material"] and sp["cfg_dily_id"]:
                mk = _cross_key_for_profile(cur, sp["cfg_dily_id"])
                if mk:
                    cut_kind = "profil"
                    material_key = mk
        # bot5, 2026-09-28 (Robert primo: "do objednávky se nedostaly do
        # textu délky profilů") - length_mm se sice spravne uklada do
        # vlastniho sloupce (viz vyse), ale product_name_snapshot (text,
        # ktery se skutecne zobrazuje v Dokladech/Dodacich listech/
        # e-mailech) ho nikdy neobsahoval - vic ruznych delek stejneho
        # profilu (napr. 4 radky "Profil 40x40mm (alu)") pak vypadaji k
        # nerozeznani. Pripojit puvodni "dim" text z nabidky (uz overeny
        # regexem vyse, format "1916 mm"/"590,5 mm") primo do nazvu.
        name_snapshot = str(it["name"])[:255]
        if dim_match:
            dim_text = str(it.get("dim") or "").strip()
            name_snapshot = f"{name_snapshot} - {dim_text}"[:255]
        cur.execute(
            "INSERT INTO shop_order_items "
            "(order_id, product_id, product_name_snapshot, unit_price_czk, qty, "
            " line_total_czk, length_mm, cut_kind, material_key) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (order_id, it.get("product_id"), name_snapshot, unit_price, qty,
             line_total, length_mm, cut_kind, material_key),
        )
        if cfg_snimek and it.get("configuration_code") == cfg_snimek.get("kod"):
            cur.execute("UPDATE shop_order_items SET configuration_json=%s, configuration_code=%s WHERE id=%s",
                        (json.dumps(cfg_snimek, ensure_ascii=False), cfg_snimek.get("kod"), cur.lastrowid))
    # Prislusenstvi zvolene zakaznikem v nabidce (bot8, 2026-10-07: pricky do multiboxu): `extra_items` = [{product_id, name, qty, unit_price}] za JEDEN kus sestavy (overuje a pocita volajici,
    # api/scene_offers.py::_pricky_vyber, ceny z karet) - qty i celkem se nasobi poctem kusu sestavy jako ostatni radky; cena je uz v total_czk hlavicky
    for it in extra_items or []:
        mult = max(1, int(qty_multiplier or 1))
        q = int(it["qty"]) * mult
        unit = round(float(it["unit_price"]), 2)
        cur.execute(
            "INSERT INTO shop_order_items (order_id, product_id, product_name_snapshot, unit_price_czk, qty, line_total_czk) VALUES (%s,%s,%s,%s,%s,%s)",
            (order_id, it.get("product_id"), str(it["name"])[:255], unit, q, round(unit * q, 2)),
        )
    return order_id, order_number


def _resolve_toptrans_price(cur, shipping_method_id, delivery_zip, weight_kg, volume_m3=0.0):
    """
    V9 (bot3, 2026-08-08 - pridan objem). Dopocita cenu dopravy pro metody
    s pricing_mode='zip_weight' (aktualne jen Toptrans) podle PSC dodaci
    adresy + celkove hmotnosti/objemu objednavky.

    Zdroj cen: shop_shipping_price_rules - REALNY oficialni cenik
    Toptrans (stazeny z toptrans.cz, viz sql/2026-07-25_toptrans_duplicates.sql),
    tarifikace hmotnostni/objemove pasmo x vzdalenostni pasmo (km_band).

    Robert 2026-08-08: "Toptrans vzdy fakturuje tu vyssi cenu" (z hmotnosti
    nebo z objemu). Skutecny Toptrans PDF cenik (viz
    sql/2026-08-08_toptrans_volume.sql) potvrdil, ze kazdy radek cenika je
    PAR "do X kg / do Y m3" se stejnou cenou - tedy STEJNY km_band, dve
    nezavisla hledani (podle weight_to_kg a podle volume_to_m3), vezme se
    vyssi z obou cen. volume_m3=0 (chybejici/nedopocitatelna data u casti
    polozek, "co neni doplnime pozdeji") znamena proste "objemova cena se
    nepocita", pouzije se jen hmotnostni - NIKDY netvrdime cenu z objemu
    0, to by bylo vzdy nejlevnejsi pasmo a systematicky by podcenovalo
    dopravu.

    PSC -> vzdalenostni pasmo: shop_zip_distance_bands - Robertuv pokyn
    "cenik si najdi na toptrans.cz" byl splnen pro CENY, ale presna
    vzdalenost KAZDEHO PSC od depa neni nikde verejne k dispozici (chtelo
    by to routovaci API) - tabulka je proto ODHAD podle kraje/regionu.
    Neznamy PSC prefix -> pouzije se nejvyssi/nejbezpecnejsi pasmo (700 km),
    aby se doprava spis PREPLATILA nez PODCENILA.

    Vraci (price_czk, km_band, basis), basis je "weight" nebo "volume"
    (podle ceho vysledna - vyssi - cena vysla; pro zobrazeni v kosiku/
    objednavce). Vyhodi _OrderCreateError, pokud PSC chybi/je neplatne,
    nebo HMOTNOST presahuje nejvyssi pasmo v ceniku (Toptrans by takovou
    zasilku stejne ocenoval individualne - "Individuální nacenění" v
    cenovem listu). Objemove presazeni pasma samo o sobe NEBLOKUJE -
    objemova data jsou u casti produktu jen odhad/chybi, takze se v tom
    pripade jen tise nezapocita do porovnani (viz vyse).
    """
    if not delivery_zip:
        raise _OrderCreateError("Pro dopravu Toptrans je nutné zadat PSČ dodací adresy.")
    zip_clean = re.sub(r"\D", "", delivery_zip)
    if len(zip_clean) != 5:
        raise _OrderCreateError("Neplatné PSČ dodací adresy (očekáváno 5 číslic).")
    # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): admin CRUD
    # (admin_shipping_zip_bands_create) zamerne povoluje 1-3 mistny
    # prefix, ale lookup zkousel VZDY jen presne 2 znaky - 1/3 mistna
    # pravidla tak nikdy nenasla shodu, tise spadla na vychozi pasmo
    # 700. CRUD se nemeni (zamer 1-3 znaku zustava), lookup zkousi
    # NEJDELSI prefix napřed (specifictejsi pravidlo ma prednost pred
    # obecnejsim - 3 znaky "100" pred 2 znaky "10").
    row = None
    for plen in (3, 2, 1):
        cur.execute(
            "SELECT km_band FROM shop_zip_distance_bands WHERE zip_prefix=%s",
            (zip_clean[:plen],),
        )
        row = cur.fetchone()
        if row:
            break
    km_band = row["km_band"] if row else 700

    cur.execute(
        "SELECT price_czk FROM shop_shipping_price_rules "
        "WHERE shipping_method_id=%s AND km_band=%s AND weight_to_kg>=%s "
        "ORDER BY weight_to_kg ASC LIMIT 1",
        (shipping_method_id, km_band, weight_kg),
    )
    rule = cur.fetchone()
    if not rule:
        raise _OrderCreateError(
            f"Zásilka o hmotnosti {weight_kg:.1f} kg přesahuje rozsah ceníku Toptrans "
            f"(nad 3000 kg je individuální nacenění) - kontaktujte prosím dopravce/administrátora přímo."
        )
    price_czk = float(rule["price_czk"])
    basis = "weight"

    if volume_m3:
        cur.execute(
            "SELECT price_czk FROM shop_shipping_price_rules "
            "WHERE shipping_method_id=%s AND km_band=%s AND volume_to_m3>=%s "
            "ORDER BY volume_to_m3 ASC LIMIT 1",
            (shipping_method_id, km_band, volume_m3),
        )
        vol_rule = cur.fetchone()
        if vol_rule and float(vol_rule["price_czk"]) > price_czk:
            price_czk = float(vol_rule["price_czk"])
            basis = "volume"

    return price_czk, km_band, basis


def _product_unit_volume_m3(cur, product):
    """
    Objem JEDNE prodejni jednotky produktu (bot3, 2026-08-08, Toptrans
    doprava podle objemu) - u profilu (cfg_dily_id) za 1 tyc/3000mm
    (stejna "1ks=3000mm" konvence jako u weight_g/price_czk_placeholder
    - prurez z cfg_dily.dim_x/dim_y_mm je delkove nezavisly, ale skutecna
    prodavana delka jednotky je vzdy 3000mm rod, ne modelovana delka v
    cfg_dily). U ostatnich produktu (bez cfg_dily_id) z rucne zadanych
    length_mm/width_mm/height_mm na skladove karte.

    Vraci None, pokud neni znamo (chybi cfg_dily prurez i rucne zadane
    rozmery) - "co neni doplnime pozdeji" (Robert), volajici pak tuhle
    polozku do celkoveho objemu proste nezapocita (misto chybneho 0).
    """
    cfg_dily_id = product.get("cfg_dily_id")
    if cfg_dily_id:
        cur.execute("SELECT dim_x_mm, dim_y_mm, dim_z_mm FROM cfg_dily WHERE id=%s", (cfg_dily_id,))
        d = cur.fetchone()
        if d and d["dim_x_mm"] is not None and d["dim_y_mm"] is not None and d["dim_z_mm"] is not None:
            dims_sorted = sorted([float(d["dim_x_mm"]), float(d["dim_y_mm"]), float(d["dim_z_mm"])])
            cross_a_mm, cross_b_mm = dims_sorted[0], dims_sorted[1]
            return (cross_a_mm / 1000.0) * (cross_b_mm / 1000.0) * 3.0
        return None
    length_mm, width_mm, height_mm = product.get("length_mm"), product.get("width_mm"), product.get("height_mm")
    if length_mm and width_mm and height_mm:
        return (length_mm / 1000.0) * (width_mm / 1000.0) * (height_mm / 1000.0)
    return None


def _cross_key_for_profile(cur, cfg_dily_id):
    """'AxB' material_key pro profil (dva nejmensi rozmery cfg_dily,
    stejna konvence jako cross_key()/fetch_katalog_parts() v api/app.py
    a jiz existujici _product_unit_volume_m3() vyse - jen tu vraci
    format retezce misto plochy). None, kdyz cfg_dily nema kompletni
    dimenze (stejny fallback jako _product_unit_volume_m3)."""
    cur.execute("SELECT dim_x_mm, dim_y_mm, dim_z_mm FROM cfg_dily WHERE id=%s", (cfg_dily_id,))
    d = cur.fetchone()
    if not d or d["dim_x_mm"] is None or d["dim_y_mm"] is None or d["dim_z_mm"] is None:
        return None
    a, b, _c = sorted([float(d["dim_x_mm"]), float(d["dim_y_mm"]), float(d["dim_z_mm"])])
    return f"{int(round(a))}x{int(round(b))}"


def _cutting_plan_shadow_items(cur, product, cut_pieces_json):
    """Robert 2026-08-08: "nahraju ti testovací objednávku profily s
    přířezy a desky, uchop to napoj reálně funkčně na řezné plány" -
    api/cutting.py (rezne plany) cte cut_kind/material_key/length_mm/
    width_mm/height_mm na shop_order_items, ale nikdo tyhle sloupce
    nikdy nezapisoval (zdokumentovana, 2x vedome odlozena mezera, viz
    NAVRH_REZNE_PLANY.md §5.3). Tahle funkce je most: z cut_pieces_json
    (uz ulozeneho na hlavnim radku objednavky, viz cut_pieces_json v
    order_items.append() vyse) vyrobi JEDEN STINOVY radek NA KAZDOU
    ODLISNOU velikost priřezu (cutting.py::_classify_items cte
    length_mm/width_mm+height_mm jako JEDNU PLOCHOU hodnotu na radek,
    cut_pieces_json samo vubec neparsuje - nejde tedy poslat jeden
    radek s celym seznamem). Stinove radky maji cenu 0 (cena uz je v
    hlavnim radku s poctem tyci/tabuli) - stejny idiom jako existujici
    "Řez profilu" service-fee radek o par radku vyse.

    Vraci [] kdyz cut_pieces_json chybi, produkt neni profil (cfg_dily_id)
    ani deska (is_board_material), nebo material_key nejde urcit
    (cfg_dily bez kompletnich dimenzi / deska bez nastaveneho
    cutting_material_key v adminu - v tom pripade radek proste zustane
    bez cut_kind, jako driv, a admin si toho vsimne v "Řezné plány" v
    sekci nedopocitatelnych polozek)."""
    if not cut_pieces_json:
        return []
    try:
        cuts = json.loads(cut_pieces_json)
    except (TypeError, ValueError):
        return []
    if not isinstance(cuts, list) or not cuts:
        return []

    # POZOR poradi: desky (napr. PR10) maji casto nastavene OBOJI
    # cfg_dily_id (kvuli 3D scene/hmotnosti) i is_board_material -
    # is_board_material se testuje PRVNI, jinak by se deska omylem
    # klasifikovala jako profil (cross_key_for_profile by navic vratil
    # None, protoze desky nemaji cfg_dily dimenze - viz test 2026-08-08).
    if product.get("is_board_material"):
        cut_kind = "deska"
        material_key = product.get("cutting_material_key")
    elif product.get("cfg_dily_id"):
        cut_kind = "profil"
        material_key = _cross_key_for_profile(cur, product["cfg_dily_id"])
    else:
        return []
    if not material_key:
        return []

    shadow_items = []
    for c in cuts:
        qty = c.get("qty")
        if not qty:
            continue
        if cut_kind == "profil":
            length_mm = c.get("length_mm")
            if not length_mm:
                continue
            label = f"Řezný plán – {length_mm:.0f} mm – {product['name']}"
            dims = {"length_mm": length_mm, "width_mm": None, "height_mm": None}
        else:
            width_mm, height_mm = c.get("width_mm"), c.get("height_mm")
            if not width_mm or not height_mm:
                continue
            label = f"Řezný plán – {width_mm:.0f}×{height_mm:.0f} mm – {product['name']}"
            dims = {"length_mm": None, "width_mm": width_mm, "height_mm": height_mm}
        shadow_items.append({
            "product_id": product["id"],
            "product_name_snapshot": label,
            "unit_price_czk": 0.0,
            "qty": qty,
            "cut_pieces_json": None,
            "line_total_czk": 0.0,
            "cut_kind": cut_kind,
            "material_key": material_key,
            **dims,
        })
    return shadow_items


def _fetch_order_with_items(conn, order_id):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM shop_orders WHERE id=%s", (order_id,))
        order = cur.fetchone()
        if not order:
            return None, []
        cur.execute(
            "SELECT * FROM shop_order_items WHERE order_id=%s ORDER BY id",
            (order_id,),
        )
        items = cur.fetchall()
    return order, items


def _order_confirmation_email_body(order_number, items, total, missing_items=None):
    lines = [
        "Dobrý den,",
        "",
        f"děkujeme za Vaši objednávku {order_number}. Aktuální stav: {STATUS_LABELS_CZ['nova']}.",
        "",
        "Položky objednávky:",
    ]
    for it in items:
        # Robert 2026-08-08 ("uvadejme u ceny profilů, vedle ks také 3m") -
        # is_profile_material je uz soucasti order_items (viz _resolve_and_insert_order).
        unit_note = " (3 m)" if it.get("is_profile_material") else ""
        jednotka = {"m": "m", "m2": "m²"}.get(it.get("product_unit"), "ks")      # metraz (kat. Kryci listy, valeckova draha): mnozstvi je v metrech, ne v kusech
        lines.append(f"  - {it['product_name_snapshot']} × {it['qty']} {jednotka}{unit_note} = {it['line_total_czk']:.2f} Kč")
    lines += ["", f"Celkem: {total:.2f} Kč"]
    # Robert 2026-07-31: "pokud neni na sklade objednavka se e-mailem
    # presto potvrdi ale s informaci ze neni neco skladem a ze to
    # upresnime pozdeji" - stav objednavky (Potvrzena/Ceka na zbozi)
    # zustava rizeny jen skladem (viz auto_confirm_after_confirmation_email),
    # tady se meni JEN text e-mailu zakaznikovi.
    if missing_items:
        lines += [
            "",
            "Upozorňujeme, že u níže uvedených položek aktuálně nemáme dostatek "
            "skladu. Doobjednáváme je u dodavatele a přesný termín dodání Vám "
            "upřesníme v nejbližší době:",
        ]
        for name in missing_items:
            lines.append(f"  - {name}")
    lines += [
        "",
        "Ozveme se Vám s dalšími kroky.",
        "",
        "S pozdravem,",
        "logiman.cz",
    ]
    return "\n".join(lines)


def _find_missing_stock_items(order_id):
    """Cisty READ (bez FOR UPDATE) - kolik kusu chybi na sklade pro danou
    objednavku, jen pro TEXT potvrzovaciho e-mailu. Autoritativni
    rozhodnuti (a samotny odpis skladu) dela _system_confirm_or_wait() v
    transakci o par radku niz - tohle je jen informativni predbezny
    pohled, drobne race podmince (mezitim se sklad zmeni) nevadi, jde o
    formulaci e-mailu, ne o skutecny stav."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT oi.product_name_snapshot, oi.qty, p.stock_qty "
                "FROM shop_order_items oi LEFT JOIN shop_products p ON p.id = oi.product_id "
                "WHERE oi.order_id=%s AND oi.configuration_json IS NULL",
                (order_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [r["product_name_snapshot"] for r in rows if r["stock_qty"] is None or r["stock_qty"] < r["qty"]]


def _status_change_email_body(order_number, new_status, history_note):
    lines = [
        "Dobrý den,",
        "",
        f"stav Vaší objednávky {order_number} se změnil na: {STATUS_LABELS_CZ.get(new_status, new_status)}.",
    ]
    if history_note:
        lines += ["", history_note]
    lines += ["", "S pozdravem,", "logiman.cz"]
    return "\n".join(lines)


# --- V9 (bot3, 2026-07-25): e-mailovy klient + historie (viz emails.py) ---
# Puvodni primy `send_email(...)` na techto mistech NEBYL zalogovan nikam
# (zadna historie) a navic bezel MIMO try/finally bloky DB spojeni - kdyby
# SMTP vyhodilo vyjimku, cely request by spadl na 500 i kdyz uz byla
# objednavka davno commitnuta. Obe veci resi lazy import `emails` (viz
# dlouhy komentar v emails.py, proc je bezpecny) + obal try/except - stejny
# obsah e-mailu (funkce _order_confirmation_email_body/_status_change_email_body
# vyse zustavaji beze zmeny), jen ted navic zalogovano do shop_emails a
# nikdy nespadne request kvuli vypadku SMTP.
def _send_order_emails(result):
    """Po uspesnem vytvoreni objednavky posle potvrzeni objednavky, a
    pokud WORKFLOW1 rovnou vystavil i zalohovou fakturu
    (result['proforma_document']), posle i tu (s PDF prilohou) - obojí
    AUTOMATICKY (Robert, AskUserQuestion: 'automaticky u klíčových
    událostí')."""
    try:
        missing = _find_missing_stock_items(result["order_id"])
        _log_id, status, _err = emails.send_and_log(
            result["order_id"], template_key="order_confirmation", recipient=result["customer_email"],
            subject=f"Potvrzení přijetí objednávky {result['order_number']}",
            body=_order_confirmation_email_body(result["order_number"], result["order_items"], result["total"], missing),
            admin=None, auto=True,
        )
        # Robert 2026-07-31: "objednavka se potvrdi klientovi coz je stav
        # potvrzena tim ze se mu odesle potvrzovaci e-mail" + "muze se stat
        # ze nebude fungovat e-mailovy klient to znamena ze bude nova a bude
        # videt ze neni potvrzena" -> stav se preklopi VYHRADNE pri
        # skutecne uspesnem odeslani. Kdyz e-mail selze, objednavka zustane
        # "nova" a je na prvni pohled videt, ze zakaznik potvrzeni nedostal.
        if status == "sent":
            auto_confirm_after_confirmation_email(result["order_id"])
        proforma = result.get("proforma_document")
        if proforma:
            emails.send_document_email_auto(result["order_id"], proforma["id"])
    except Exception:
        pass


# Robert 2026-08-08 ("kosik nam na konci odeslani obj usnul") - _send_order_emails
# vola SMTP (az 15s timeout, viz send_email v app.py) + pripadne generovani
# PDF zalohove faktury, VSE PUVODNE synchronne UVNITR requestu na
# POST /api/orders - zakaznik tak cekal na odpoved klidne desitky sekund,
# coz vypadalo jako zamrznuti kosiku. Samotne vytvoreni objednavky (DB zapis)
# je rychle a nezavisi na e-mailu, takze se e-mailova cast presouva do
# samostatneho vlakna PO commitu - odpoved se zakaznikovi vrati hned. Bezpecne
# vuci sdilenemu DB spojeni (viz threading.local() v get_conn()/app.py -
# tenhle background thread dostane VLASTNI spojeni, ne to od hlavniho
# pozadavku).
def _send_order_emails_bg(result):
    threading.Thread(target=_send_order_emails, args=(result,), daemon=True).start()


def _send_status_change_email(order_id, order_number, customer_email, new_status, history_note):
    try:
        emails.send_and_log(
            order_id, template_key="status_change", recipient=customer_email,
            subject=f"Změna stavu objednávky {order_number}",
            body=_status_change_email_body(order_number, new_status, history_note),
            admin=None, auto=True,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Zakaznik: vytvoreni objednavky + nahled vlastnich objednavek
# ---------------------------------------------------------------------------

class _OrderCreateError(Exception):
    """Interni signal chyby ze sdileneho _resolve_and_insert_order() - viz
    pouziti v orders_create()/admin_orders_create() nize."""
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code


def _resolve_and_insert_order(cur, body, attribute_user_id, profile_user_id, require_active=True, dealer=None):
    """
    Sdilene jadro vytvoreni objednavky - pouziva ho jak samoobsluzny
    POST /api/orders (zakaznik objednava sam sobe), tak
    POST /api/admin/orders (bot3, 2026-07-25 v4: "objednávku lze zadat i
    ručně" - admin zadava objednavku za zakaznika, napr. telefonicky/
    osobne). Nedela commit/rollback/close - o transakci se stara volajici.

    require_active - True u samoobsluzneho letu (zakaznik nikdy nesmi
                      koupit neaktivni/nedostupny produkt). admin_orders_create()
                      posila False (bot5, 2026-09-23, Robert zasekly na
                      "Produkt neexistuje nebo neni dostupny" pri rucnim
                      zadani objednavky pro neaktivni produkt) - admin
                      vedome vybira konkretni produkt v pickeru (ten uz
                      dnes neaktivni produkty nabizi, viz stockMoveProductsCache
                      z /api/shop/products?all=1), typicky telefonicka/
                      osobni objednavka na polozku, ktera jeste/uz neni
                      verejne na webu. Produkt porad MUSI existovat a mit
                      cenu (nize) - jen `active` flag se u admina neresi.

    attribute_user_id - komu se objednavka PRIPOJI (shop_orders.user_id).
                         U samoobsluzneho letu = prihlaseny zakaznik. U
                         rucniho admin zadani muze byt None (zakaznik bez
                         uctu - stary "guest" zpusob, ted jen adminovi
                         pristupny) nebo id existujiciho uctu.
    profile_user_id   - cim uctem se ma predvyplnit kontakt/fakturace a
                         odkud se vezme slevova skupina. Normalne stejne
                         jako attribute_user_id, ale muze byt None (rucni
                         zadani bez napojeni na ucet - zadna sleva, zadne
                         predvyplneni, admin musi poslat kontakt rucne).

    dealer            - radek dealers (dict) jen u dealerske objednavky pres API (cesta (b),
                         api/dealer_orders.py, bot5 2026-10-02): cena KAZDE polozky je
                         dealerska cena (dealers.dealer_effective_price), ne skupinova
                         sleva/kupon, produkt musi projit branou dealer_product_view (stejne
                         jako feed a widget), zadny kosik, zadne sestavy/montaz/priřezy.
                         None (vsichni ostatni volajici) = chovani beze zmeny.

    Vraci dict: {order_id, order_number, total, order_items, customer_email}.
    Pri chybe vyhodi _OrderCreateError (message + status_code) - volajici
    ji odchyti a spravi rollback + JSON odpoved.
    """
    profile = None
    if profile_user_id is not None:
        # g.active=1 v ON (bezpecnostni nalez, bot3/revize kodu 2026-09-02) -
        # stejna oprava jako products.py::_effective_unit_price.
        cur.execute(
            "SELECT c.*, g.name AS group_name, g.discount_percent AS group_discount_percent "
            "FROM shop_customers c LEFT JOIN shop_customer_groups g ON g.id = c.group_id AND g.active=1 "
            "WHERE c.user_id=%s",
            (profile_user_id,),
        )
        profile = cur.fetchone()
    customer_group_name = profile["group_name"] if profile else None
    discount_percent = float(profile["group_discount_percent"]) if profile and profile.get("group_discount_percent") is not None else 0.0

    # --- polozky: z requestu, nebo z kosiku ---
    use_cart = bool(body.get("use_cart"))
    if dealer is not None and use_cart:
        raise _OrderCreateError("Dealerská objednávka nemůže použít košík.")
    if use_cart:
        if profile_user_id is None:
            raise _OrderCreateError("Košík lze použít jen u objednávky napojené na existující účet (user_id).")
        # FOR UPDATE (bot16, 2026-09-03, revize bot3 - W1): dva soubezne
        # POST /api/orders use_cart=1 drive vytvorily DVE objednavky ze
        # stejneho kosiku (kosik se cetl bez zamku, DELETE az na konci).
        # Ted druha transakce ceka na prvni a po jejim commitu (radky
        # smazane) dostane prazdny vysledek -> "Kosik je prazdny".
        cur.execute(
            "SELECT ci.product_id, ci.qty, ci.cut_pieces_json, ci.cut_service_qty, ci.coupon_code, "
            "       ci.assembly_id, ci.montaz_zvolena, ci.bez_boxu, ci.montaz_misto, ci.configuration_json, ci.config_hash "
            "FROM shop_cart_items ci WHERE ci.user_id=%s ORDER BY ci.added_at ASC FOR UPDATE",
            (profile_user_id,),
        )
        cart_rows = cur.fetchall()
        if not cart_rows:
            raise _OrderCreateError("Košík je prázdný.")
        # cut_pieces_json (prirezy profilu, Robert 2026-08-06) se z kosiku
        # do objednavky preklopi beze zmeny - viz api/cart.py, qty uz je
        # tam spravne dopoctene (pocet celych tyci). cut_service_qty
        # (pocet rezu) se pouziva nize pro samostatny radek "Rezy".
        # coupon_code (Robert 2026-08-08) se stejne tak preklopi, aby se
        # kupon uplatnil i pri skutecnem checkoutu, ne jen v nahledu kosiku.
        # assembly_id/montaz_zvolena/bez_boxu/montaz_misto (Robert
        # 2026-09-13) se preklopi stejne beze zmeny - 0 -> None, stejny
        # "jednoducha podminka" duvod jako _serialize_cart v cart.py.
        clean_items = [
            {"product_id": r["product_id"], "qty": r["qty"], "cut_pieces_json": r["cut_pieces_json"],
             "cut_service_qty": r["cut_service_qty"], "coupon_code": r["coupon_code"],
             "assembly_id": r["assembly_id"] or None, "montaz_zvolena": bool(r["montaz_zvolena"]),
             "bez_boxu": bool(r["bez_boxu"]), "montaz_misto": r["montaz_misto"],
             "configuration_json": r["configuration_json"], "config_hash": r["config_hash"]}
            for r in cart_rows
        ]
    else:
        items_in = body.get("items")
        if not isinstance(items_in, list) or not items_in:
            raise _OrderCreateError("Objednávka musí obsahovat alespoň jednu položku (nebo use_cart: true).")
        if len(items_in) > 200:
            raise _OrderCreateError("Příliš mnoho položek v jedné objednávce.")
        clean_items = []
        for raw in items_in:
            if not isinstance(raw, dict):
                raise _OrderCreateError("Neplatná položka objednávky.")
            if dealer is not None and set(raw) - {"product_id", "qty"}:
                raise _OrderCreateError("Dealerská objednávka přijímá u položky jen product_id a qty.")
            try:
                product_id = int(raw.get("product_id"))
                qty = int(raw.get("qty"))
            except (TypeError, ValueError):
                raise _OrderCreateError("Neplatné product_id nebo množství.")
            if qty <= 0:
                raise _OrderCreateError("Množství musí být kladné celé číslo.")
            # assembly_id nepovinne i pri rucnim zadani polozek (admin
            # vytvarejici objednavku primo, viz admin_orders_create nize,
            # ktera tuhle vetev take vola) - stejna volba jako z kosiku.
            assembly_id_raw = raw.get("assembly_id")
            try:
                assembly_id = int(assembly_id_raw) if assembly_id_raw else None
            except (TypeError, ValueError):
                raise _OrderCreateError("Neplatná varianta sestavy.")
            montaz_misto_raw = (raw.get("montaz_misto") or "").strip().lower() or None
            if montaz_misto_raw is not None and montaz_misto_raw not in _montaz_mista_map(cur):
                raise _OrderCreateError("Neplatné místo montáže.")
            clean_items.append({
                "product_id": product_id, "qty": qty, "assembly_id": assembly_id,
                "montaz_zvolena": bool(raw.get("montaz_zvolena")), "bez_boxu": bool(raw.get("bez_boxu")),
                "montaz_misto": montaz_misto_raw, "configuration": raw.get("configuration"),
            })

    # --- kontakt: request pole > profil zakaznika > chyba ---
    customer_name = (body.get("customer_name") or "").strip() or (profile["full_name"] if profile else "")
    customer_email = (body.get("customer_email") or "").strip().lower() or (profile["email"] if profile else "")
    customer_phone = (body.get("customer_phone") or "").strip() or (profile["phone"] if profile else None) or None
    delivery_address = (
        (body.get("delivery_address") or "").strip()
        or (profile["delivery_address"] if profile else None)
        or (profile["billing_address"] if profile else None)
        or None
    )
    note = (body.get("note") or "").strip() or None

    if not customer_name or not customer_email:
        raise _OrderCreateError(
            "Jméno a e-mail jsou povinné (vyplň v požadavku, nebo napoj objednávku na účet "
            "s uloženým fakturačním profilem)."
        )
    if not _EMAIL_RE.match(customer_email):
        raise _OrderCreateError("Neplatný e-mail.")

    # --- fakturacni snapshot ---
    billing_name = (body.get("billing_name") or "").strip() or (
        (profile["company_name"] or profile["full_name"]) if profile else None
    ) or customer_name
    billing_ico = (body.get("billing_ico") or "").strip() or (profile["ico"] if profile else None) or None
    billing_dic = (body.get("billing_dic") or "").strip() or (profile["dic"] if profile else None) or None
    billing_address = (
        (body.get("billing_address") or "").strip()
        or (profile["billing_address"] if profile else None)
        or delivery_address
    )

    # --- PSC dodaci adresy (V8, bot3 2026-07-25) - potreba STRUKTUROVANE,
    # aby se z nej dala dopocitat cena Toptrans (viz nize). Request > profil
    # > PSC fakturacni adresy (stejny fallback retezec jako delivery_address
    # o par radku vys - kdyz zakaznik nevyplni samostatnou dodaci adresu,
    # bere se fakturacni, PSC ted symetricky totez, oprava Robert 2026-08-06:
    # "Pro dopravu Toptrans je nutné zadat PSČ dodací adresy" hlaska, na
    # kterou se zakaznik v puvodnim checkoutu nemel jak dostat - zadne pole
    # PSC v nem vubec nebylo, viz webapp/index.html+category.html+product.html).
    # Normalizujeme na 5 cistych cislic (stejne jako customers.py::_validate_and_clean). ---
    raw_billing_zip = (
        (body.get("billing_zip") or "").strip()
        or (profile["billing_zip"] if profile else None)
        or None
    )
    billing_zip = re.sub(r"\D", "", raw_billing_zip) if raw_billing_zip else None
    if billing_zip and len(billing_zip) != 5:
        raise _OrderCreateError("Neplatné PSČ fakturační adresy (očekáváno 5 číslic).")
    raw_delivery_zip = (
        (body.get("delivery_zip") or "").strip()
        or (profile["delivery_zip"] if profile else None)
        or raw_billing_zip
        or None
    )
    delivery_zip = re.sub(r"\D", "", raw_delivery_zip) if raw_delivery_zip else None
    if delivery_zip and len(delivery_zip) != 5:
        raise _OrderCreateError("Neplatné PSČ dodací adresy (očekáváno 5 číslic).")

    # --- platba (volitelna) ---
    payment_method_name, payment_price = None, 0.0
    payment_method_id = body.get("payment_method_id")
    if payment_method_id is not None:
        cur.execute(
            "SELECT name, price_czk FROM shop_payment_methods WHERE id=%s AND active=1",
            (payment_method_id,),
        )
        pm = cur.fetchone()
        if not pm:
            raise _OrderCreateError("Zvolený způsob platby neexistuje nebo není aktivní.")
        payment_method_name, payment_price = pm["name"], float(pm["price_czk"])

    # --- polozky: nacteni aktualni ceny (FOR UPDATE) ---
    # Soucasne scitame celkovou hmotnost objednavky (weight_g) - potreba
    # pro dopocet ceny dopravy Toptrans NIZE (cena zavisi na PSC i
    # hmotnosti, viz Robert 2026-07-25).
    #
    # Robert 2026-07-25 (opakovane): "musi byt povoleno vytvorit objednavku
    # i kdyz neni dost na sklade" - VYTVORENI objednavky uz tedy NEKONTROLUJE
    # stock_qty vubec (zadny blokujici raise), objednavka muze vzniknout i
    # nad ramec aktualnich skladovych zasob. Zadna deduplikace skladu tady
    # ani neprobiha (stock_qty se odecita az pri POTVRZENI objednavky, viz
    # PUT /api/admin/orders/<id> nize) - tenhle SELECT ... FOR UPDATE jen
    # zamyka radek produktu kvuli konzistentnimu cteni ceny/hmotnosti pri
    # soubeznych objednavkach, ne kvuli kontrole skladu. Nedostatek skladu
    # se resi az pozdeji: bud v "Sestave k objednani" (auto-sync z
    # min_stock), nebo pri pokusu o potvrzeni teto objednavky (tam
    # blokujici kontrola ZUSTAVA - viz nize, protoze tam uz jde o skutecne
    # odecteni fyzickeho skladu).
    order_items = []
    total = 0.0
    total_weight_kg = 0.0
    total_volume_m3 = 0.0
    weight_incomplete_cfg = False                          # bot5, 2026-10-02: konfigurace sestavy: hmotnost konfigurace z katalogu je neuplna -> Toptrans se pro ni nepocita
    for it in clean_items:
        # bot5, 2026-10-02: konfigurace sestavy: konfigurace je vyroba na zakazku. Vyber se znovu overi a cena spocita na serveru (z kosiku ani z pozadavku se cena nebere), radek ma
        # product_id NULL (jako sluzba), takze se na nej nevztahuje zadna logika skladu; odkaz na kartu a hash jsou ve snimku. Viz api/konfigurace_kosik.py.
        try:
            import konfigurace_kosik
        except Exception:                                      # modul se nenacetl: bezne radky dal funguji, konfigurovatelny produkt skonci jako "cena na dotaz"
            konfigurace_kosik = None
            getattr(app, "logger", None) and app.logger.exception("orders: modul konfigurace se nenacetl")
        if konfigurace_kosik is not None and (it.get("config_hash") or it.get("configuration") is not None or konfigurace_kosik.je_konfigurovatelny(it["product_id"])):
            if dealer is not None:
                raise _OrderCreateError("Konfigurovatelný produkt nelze objednat dealerskou cestou.", status_code=422)
            cur.execute("SELECT id, name, active FROM shop_products WHERE id=%s", (it["product_id"],))
            product_cfg = cur.fetchone()
            if not product_cfg or (require_active and not product_cfg["active"]):
                raise _OrderCreateError(f"Produkt {it['product_id']} neexistuje nebo není dostupný.")
            order_item_cfg, kg_cfg, kg_cfg_ok = konfigurace_kosik.radek_objednavky(
                cur, product_cfg, it, attribute_user_id, lambda zprava, stav=400: _OrderCreateError(zprava, status_code=stav))
            total += order_item_cfg["line_total_czk"]
            total_weight_kg += kg_cfg
            weight_incomplete_cfg = weight_incomplete_cfg or not kg_cfg_ok
            montaz_radek = order_item_cfg.pop("_montaz_radek", None)           # bot5, 2026-10-04: montaz stolu = samostatny radek objednavky (Robert pres bot9)
            order_items.append(order_item_cfg)
            if montaz_radek:
                total += montaz_radek["line_total_czk"]
                order_items.append(montaz_radek)
            continue
        cur.execute(
            "SELECT id, name, price_czk_placeholder, stock_qty, active, weight_g, cfg_dily_id, "
            "       length_mm, width_mm, height_mm, is_board_material, is_profile_material, cutting_material_key, "
            "       dealer_discount_percent, sale_price_czk, sale_price_from, sale_price_until, category_id, unit "
            "FROM shop_products WHERE id=%s FOR UPDATE",
            (it["product_id"],),
        )
        product = cur.fetchone()
        if not product or (require_active and not product["active"]):
            raise _OrderCreateError(f"Produkt {it['product_id']} neexistuje nebo není dostupný.")
        # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): produkt bez
        # ceny (price_czk_placeholder NULL) prosel checkoutem za 0 Kc -
        # sdilene pro orders_create() i admin_orders_create() (obe volaji
        # tuhle funkci), stejny fix jako cart.py::cart_add_item.
        if product["price_czk_placeholder"] is None:
            raise _OrderCreateError("price_on_request", status_code=409)

        # Varianta sestavy (Robert 2026-09-13: "u sestav s euroboxy...
        # vedle výběru montáže, také volbu: bez boxů") - stejny princip
        # jako cart.py::_fetch_cart_rows: zaklad pro cenovou hierarchii
        # nize je cena VYBRANE VARIANTY (assembly_id), ne cena zastupce
        # karty. `_assembly_price_components` sama overi, ze assembly_id
        # patri tomuto product_id - jinak 400, NIKDY tise nepokracovat s
        # cizi/neplatnou variantou.
        assembly_montaz_czk, assembly_boxy_czk, assembly_kod = None, None, None
        base_price = float(product["price_czk_placeholder"])
        if it.get("assembly_id"):
            assembly_ceny = _assembly_price_components(cur, it["assembly_id"], product["id"], base_price)
            if assembly_ceny is None:
                raise _OrderCreateError(f"Neplatná varianta sestavy pro produkt {product['id']}.")
            if assembly_ceny["base_czk"] is None:
                raise _OrderCreateError("price_on_request", status_code=409)
            base_price = assembly_ceny["base_czk"]
            assembly_montaz_czk = assembly_ceny["montaz_czk"]
            assembly_boxy_czk = assembly_ceny["boxy_czk"]
            assembly_kod = assembly_ceny["kod_sestavy"]
        montaz_zvolena = bool(it.get("montaz_zvolena")) and assembly_montaz_czk is not None
        bez_boxu = bool(it.get("bez_boxu")) and assembly_boxy_czk is not None
        # Misto montaze POVINNE, kdyz je montaz skutecne zvolena (Robert
        # pres bot16, 2026-09-13: "výběr montáže klientem: v Praze nebo
        # ve Slavičíně, povinný výběr") - nevericky klientovi/kosiku,
        # kontrola znovu i tady (stejny princip jako cena, ktera se tu
        # take nebere z kosiku, ale dopocita znovu).
        montaz_misto = it.get("montaz_misto") if montaz_zvolena else None
        if montaz_zvolena and montaz_misto not in _montaz_mista_map(cur):
            raise _OrderCreateError("Vyberte místo montáže.")

        # Cenova hierarchie (Robert 2026-08-08, opraveno tentyz den: "ad 4 je
        # špatně, nesmí se slevy nikdy sčítat, platí jedna nebo druhá") -
        # skupinova sleva zakaznika (discount_percent nize) je ted PRIMO
        # SOUCASTI _effective_unit_price() jako 4. rovnocenny kandidat vedle
        # dealerske slevy/akcni ceny/kuponu (viz jeji komentar v
        # products.py) - VYHRAVA VZDY jen jedna nejnizsi cena, NIKDY se
        # nenasobi/nekombinuje. Puvodne se tu skupinova sleva chybne
        # nasobila JESTE NAVRCH vyherni ceny z ostatnich 3 mechanismu.
        product_for_pricing = dict(product)
        product_for_pricing["price_czk_placeholder"] = base_price
        if dealer is not None:
            # Dealerska objednavka (cesta (b), bot5 2026-10-02): cena = dealerska cena (cenik dealera x (1 - sleva), nikdy vic nez akcni cena),
            # zadna skupinova sleva ani kupon. Produkt musi projit stejnou branou jako feed a widget (dealer_product_view: zadne sestavy,
            # znacka, neviditelne kategorie, neaktivni) - fail closed. Selhani = _OrderCreateError, objednavka nevznikne.
            import dealers
            if dealers.dealer_product_view(cur, product["id"], mode="none") is None:
                raise _OrderCreateError(f"Produkt {product['id']} není pro dealery k dispozici.", status_code=422)
            unit_price, _price_basis = dealers.dealer_effective_price(cur, product_for_pricing, dealer)
            if unit_price is None:
                raise _OrderCreateError(f"Pro produkt {product['id']} nemáte nastavenou dealerskou cenu.", status_code=422)
        else:
            unit_price, _price_basis = _effective_unit_price(
                cur, product_for_pricing, user=attribute_user_id and {"id": attribute_user_id},
                coupon_code=it.get("coupon_code"),
            )
        # Montaz/odectena cena boxu AZ PO cenove hierarchii (nejsou to
        # slevy, jsou samostatne sluzby/slozky - TEXT_FILTR.md pravidlo 14a).
        if bez_boxu:
            unit_price = round(unit_price - assembly_boxy_czk, 2)
        if montaz_zvolena:
            unit_price = round(unit_price + assembly_montaz_czk, 2)
        line_total = round(unit_price * it["qty"], 2)
        total += line_total
        total_weight_kg += float(product["weight_g"] or 0) / 1000.0 * it["qty"]
        unit_volume_m3 = _product_unit_volume_m3(cur, product)
        if unit_volume_m3 is not None:
            total_volume_m3 += unit_volume_m3 * it["qty"]
        order_items.append({
            "product_id": product["id"],
            "product_name_snapshot": product["name"],
            "unit_price_czk": unit_price,
            "qty": it["qty"],
            "cut_pieces_json": it.get("cut_pieces_json"),
            "line_total_czk": line_total,
            # Vykonnostni audit bot5 2026-09-03: predano az sem, at se
            # nemusi znovu SELECTovat par radku nize pro kontrolu skladu
            # (bylo redundantni - stejny radek uz je zamceny FOR UPDATE
            # vyse, ~25ms sitoveho RTT navic na kazdou polozku checkoutu).
            "stock_qty": product["stock_qty"],
            # Robert 2026-08-08 ("uvadejme u ceny profilů, vedle ks také
            # 3m") - profil "1 ks = 3000mm tyc", potreba pro proformu
            # vystavenou rovnou pri vytvoreni objednavky (WORKFLOW1, viz
            # order_items_db nize) - documents._fetch_order_items() to
            # dodatecne dopoji JOINem, ale tady jeste zadne radky v DB
            # nejsou, takze se to musi predat rovnou. POZOR poradi: desky
            # (napr. PR10) maji casto nastavene OBOJI cfg_dily_id (kvuli 3D
            # scene) i is_board_material - stejna past jako v
            # _cutting_plan_shadow_items vyse, deska se NEPRODAVA po 3m
            # tycich, proto is_board_material testovat first.
            # Robert 2026-08-09 ("dokonci poctive moznost prirezu u vsech
            # profilu"): drivejsi cfg_dily_id znamenalo "ma 3D model", ne
            # "prodava se na delku" - is_profile_material je nezavisly
            # signal (nastaveny u vsech 101 profilu, ne jen 22 s modelem).
            "is_profile_material": bool(product.get("is_profile_material")) and not product.get("is_board_material"),
            # Snapshot volby varianty/montaze/boxu v OKAMZIKU OBJEDNANI
            # (Robert 2026-09-13: "přidá se informace do objednávky") -
            # nemenna historie, na rozdil od kosiku se NEDOPOCITAVA ziva
            # pri kazdem zobrazeni objednavky (cena montaze/boxu v CASE
            # objednani muze byt jina, nez co dnes rika scena).
            "product_unit": product.get("unit"),                 # jednotka karty (ks / m / m2) pro potvrzovaci e-mail: metraz = "x N m", ne "ks" (bot5 2026-10-07)
            "assembly_id": it.get("assembly_id"),
            "assembly_kod_snapshot": assembly_kod,
            "montaz_zvolena": montaz_zvolena,
            "montaz_czk_snapshot": assembly_montaz_czk if montaz_zvolena else None,
            "montaz_misto_snapshot": montaz_misto,
            "bez_boxu": bez_boxu,
            "boxy_czk_snapshot": assembly_boxy_czk if bez_boxu else None,
        })
        # Rezny plan (Robert 2026-08-08: "napoj reálně funkčně na řezné
        # plány") - viz docstring _cutting_plan_shadow_items vyse. Cena
        # techto stinovych radku je 0 (uz zapocitana v hlavnim radku
        # vyse), proto se NEPRICITA do `total`.
        order_items.extend(_cutting_plan_shadow_items(cur, product, it.get("cut_pieces_json")))

        # Rezy jako samostatna polozka objednavky (Robert 2026-08-06:
        # "vždy když klient zadá přířezy je nutné do objenávky přidat
        # automaticky řezy, musí figurovat v košíku") - VOLNA polozka
        # (product_id NULL, stejny vzor jako rucne pridana "sluzba" v
        # admin_orders_add_item), protoze cena za rez je specificka pro
        # KONKRETNI profil (cfg_dily.price_per_cut_czk), ne jeden spolecny
        # katalogovy produkt "Rezy" pro cely e-shop.
        cut_service_qty = it.get("cut_service_qty")
        if cut_service_qty:
            cut_price = _cut_service_price_czk(cur, product.get("cfg_dily_id"))
            if cut_price is not None:
                cut_unit_price = round(cut_price * (1 - discount_percent / 100), 2) if discount_percent else cut_price
                cut_line_total = round(cut_unit_price * cut_service_qty, 2)
                total += cut_line_total
                order_items.append({
                    "product_id": None,
                    "product_name_snapshot": f"Řez profilu – {product['name']}",
                    "unit_price_czk": cut_unit_price,
                    "qty": cut_service_qty,
                    "cut_pieces_json": None,
                    "line_total_czk": cut_line_total,
                })

    # --- doprava (volitelna) - AZ TEĎ, potrebuje uz spocitanou hmotnost ---
    shipping_method_name, shipping_price = None, 0.0
    shipping_review = False                                    # bot5, 2026-10-04: doprava ke schvaleni zamestnancem (viz nize, jen konfigurace s neuplnou hmotnosti)
    shipping_method_id = body.get("shipping_method_id")
    if shipping_method_id is not None:
        cur.execute(
            "SELECT id, name, price_czk, pricing_mode FROM shop_shipping_methods WHERE id=%s AND active=1",
            (shipping_method_id,),
        )
        sm = cur.fetchone()
        if not sm:
            raise _OrderCreateError("Zvolený způsob dopravy neexistuje nebo není aktivní.")
        shipping_method_name = sm["name"]
        if sm["pricing_mode"] == "zip_weight":
            if weight_incomplete_cfg:                          # bot5, 2026-10-02: konfigurace sestavy; od 2026-10-04 (Robert pres bot9: doprava u hlavniho e-shopu ke schvaleni zamestnancem) objednavka VZNIKNE
                # s cenou dopravy 0 a priznakem shipping_review, zalohova faktura az po schvaleni dopravy (POST /api/admin/orders/<id>/shipping)
                shipping_price = 0.0
                shipping_method_name = sm["name"] + " – cena ke schválení"
                shipping_review = True
            else:
                shipping_price, _km_band, _basis = _resolve_toptrans_price(
                    cur, sm["id"], delivery_zip, total_weight_kg, total_volume_m3
                )
        else:
            shipping_price = float(sm["price_czk"])

    total = round(total + shipping_price + payment_price, 2)

    # Robert (pres toscanaccio-0b, 2026-08-29): objednavky z modelovych
    # mini-eshopu (car_storefronts) maji sdileny kosik/checkout s hlavnim
    # e-shopem (Robertovo rozhodnuti - NE izolovany kosik per web), jen se
    # podle domeny, ze ktere prisel POST /api/orders, dopise storefront_id
    # pro reporting/filtr v adminu. NULL = objednavka z hlavniho
    # konfiguratoru/e-shopu, ne z mini-eshopu. Lokalni import ze stejneho
    # duvodu jako scene_offers/support v app.py (car_storefronts se
    # registruje az za orders v poradi importu na konci app.py).
    import car_storefronts
    storefront_id = car_storefronts.resolve_storefront_id(cur)

    # Party model (bot18, 2026-09-05) - party_id se prebira VYHRADNE po
    # tvrde FK (attribute_user_id -> app_users.party_id), zadne fuzzy
    # dohadovani. attribute_user_id=None (rucni zadani bez uctu) ->
    # party_id zustava NULL, presne jako user_id.
    order_party_id = None
    if attribute_user_id is not None:
        cur.execute("SELECT party_id FROM app_users WHERE id=%s", (attribute_user_id,))
        row = cur.fetchone()
        order_party_id = row["party_id"] if row else None

    cur.execute(
        "INSERT INTO shop_orders "
        "(order_number, status, delivery_state, billing_state, is_urgent, user_id, party_id, storefront_id, customer_name, customer_email, "
        " customer_phone, delivery_address, delivery_zip, note, admin_note, "
        " customer_group_name, customer_discount_percent, "
        " billing_name, billing_ico, billing_dic, billing_address, "
        " shipping_method_name, shipping_price_czk, payment_method_name, payment_price_czk, "
        " total_czk) "
        "VALUES ('', 'nova', 'nova', 'nevyfakturovano', 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (attribute_user_id, order_party_id, storefront_id, customer_name, customer_email, customer_phone,
         delivery_address, delivery_zip, note,
         customer_group_name, discount_percent,
         billing_name, billing_ico, billing_dic, billing_address,
         shipping_method_name, shipping_price, payment_method_name, payment_price,
         total),
    )
    order_id = cur.lastrowid

    cur.execute("SELECT created_at FROM shop_orders WHERE id=%s", (order_id,))
    created_at = cur.fetchone()["created_at"]
    order_number = _generate_order_number(cur, created_at)
    cur.execute("UPDATE shop_orders SET order_number=%s WHERE id=%s", (order_number, order_id))

    for oi in order_items:
        cur.execute(
            "INSERT INTO shop_order_items "
            "(order_id, product_id, product_name_snapshot, unit_price_czk, qty, cut_pieces_json, line_total_czk, "
            " cut_kind, material_key, length_mm, width_mm, height_mm, "
            " assembly_id, assembly_kod_snapshot, montaz_zvolena, montaz_czk_snapshot, montaz_misto_snapshot, "
            " bez_boxu, boxy_czk_snapshot, configuration_json, configuration_code) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (order_id, oi["product_id"], oi["product_name_snapshot"],
             oi["unit_price_czk"], oi["qty"], oi.get("cut_pieces_json"), oi["line_total_czk"],
             oi.get("cut_kind"), oi.get("material_key"), oi.get("length_mm"), oi.get("width_mm"), oi.get("height_mm"),
             oi.get("assembly_id"), oi.get("assembly_kod_snapshot"), oi.get("montaz_zvolena", False),
             oi.get("montaz_czk_snapshot"), oi.get("montaz_misto_snapshot"),
             oi.get("bez_boxu", False), oi.get("boxy_czk_snapshot"),
             oi.get("configuration_json"), oi.get("configuration_code")),
        )

    if use_cart:
        cur.execute("DELETE FROM shop_cart_items WHERE user_id=%s", (profile_user_id,))

    # --- V6 (bot3, 2026-07-25): automaticke vystaveni zalohove faktury ---
    # Pokud zvolena platebni metoda vyzaduje zalohu predem (WORKFLOW1 -
    # viz documents.py), vystavime zalohovou fakturu rovnou v ramci teto
    # transakce - zakaznik ji potrebuje hned, aby mohl zaplatit.
    #
    # Robert 2026-08-05: "pokud neco neni skladem, ta zalohova faktura
    # nemuze odejit automaticky, musi se to se zakaznikem konzultovat" -
    # kdyz nektera polozka nema dostatek skladu (stejna kontrola jako
    # pozdejsi _system_confirm_or_wait, jen o par radku driv, v JEDNE
    # transakci s vlozenim objednavky), zalohova faktura se VUBEC
    # nevystavi ani nezaklada - admin/asistent ji po konzultaci s
    # zakaznikem (dostupnost/termin) vystavi rucne v zalozce Doklady.
    has_missing_stock = False
    for oi in order_items:
        # oi.get("cut_kind") - stejna oprava jako u _system_confirm_or_wait()
        # nize (bot13, 2026-09-02), jen tady je order_items uz hotovy Python
        # seznam v pameti (sestaveny o par radku vyse), ne cerstvy SELECT -
        # zadne WHERE k opraveni, filtruje se primo v podmince.
        if oi["product_id"] is None or oi.get("cut_kind"):
            continue
        if oi["stock_qty"] < oi["qty"]:
            has_missing_stock = True
            break

    order_snapshot = {
        "id": order_id,
        "billing_name": billing_name, "billing_ico": billing_ico,
        "billing_dic": billing_dic, "billing_address": billing_address,
        "customer_name": customer_name, "customer_email": customer_email,
        "customer_phone": customer_phone, "delivery_address": delivery_address,
        "shipping_method_name": shipping_method_name, "shipping_price_czk": shipping_price,
        "payment_method_name": payment_method_name, "payment_price_czk": payment_price,
    }
    order_items_db = [
        {"product_name_snapshot": oi["product_name_snapshot"], "unit_price_czk": oi["unit_price_czk"],
         "qty": oi["qty"], "line_total_czk": oi["line_total_czk"],
         # Robert 2026-08-08 ("uvadejme u ceny profilů, vedle ks také 3m"),
         # 2026-08-09 prepnuto z cfg_dily_id na is_profile_material - stejny
         # klic jako documents._fetch_order_items() JOIN pouziva
         # (product_is_profile_material), aby _build_items_with_vat() poznala
         # profil i u proformy vystavene hned pri vytvoreni objednavky.
         "product_is_profile_material": oi.get("is_profile_material")}
        for oi in order_items
    ]
    if shipping_review:                                        # cena dopravy jeste neni: priznak ke schvaleni; zalohova faktura se nevystavuje (vystavi ji zamestnanec po schvaleni dopravy)
        cur.execute("UPDATE shop_orders SET shipping_review=1 WHERE id=%s", (order_id,))
    proforma = None if (has_missing_stock or shipping_review) else documents.create_proforma_invoice_if_needed(
        cur, order_snapshot, order_items_db
    )

    return {
        "order_id": order_id,
        "order_number": order_number,
        "total": total,
        "order_items": order_items,
        "customer_email": customer_email,
        "proforma_document": proforma,
    }


@app.post("/api/orders")
@login_required
def orders_create():
    """
    Vytvoreni nove objednavky z katalogu shop_products - samoobsluzne,
    zakaznik objednava sam sobe.

    Prihlaseni JE povinne (Robert, 2026-07-25: "objednávka nelze zadat
    bez přihlášení" - zrusen puvodni guest checkout). Cena se VZDY
    dopocitava serverove z aktualni ceny v shop_products - jakakoli cena
    poslana klientem v requestu se ignoruje. Pro RUCNI zadani objednavky
    adminem (napr. telefonicky) viz POST /api/admin/orders nize.

    Polozky: bud primo v requestu ("items"), nebo "use_cart": true - pak
    se vezmou VSECHNY polozky z aktualniho kosiku prihlaseneho uzivatele
    (shop_cart_items) a po uspesnem vytvoreni objednavky se kosik vyprazdni.

    Kontakt/fakturace: pokud nejsou v requestu explicitne poslane, doplni
    se z ulozeneho profilu zakaznika (shop_customers, viz customers.py) -
    pokud profil taky neexistuje, je potreba je poslat rucne (jinak 400).
    Fakturacni udaje (billing_*) se vzdy ULOZI JAKO SNAPSHOT na objednavku,
    aby pozdejsi zmena profilu nezmenila historickou objednavku. Pokud ma
    profil prirazenou slevovou skupinu (shop_customer_groups), jeji sleva
    se automaticky promitne do ceny kazde polozky.

    Doprava/platba: volitelne shipping_method_id/payment_method_id -
    musi odkazovat na aktivni radek v shop_shipping_methods/
    shop_payment_methods, jinak 400. Cena dopravy/platby se pricte k
    total_czk a ulozi jako snapshot (shipping_method_name/shipping_price_czk,
    payment_method_name/payment_price_czk).

    Ocekavany JSON payload:
    {
      "items": [{"product_id": 12, "qty": 3}, ...],   NEBO "use_cart": true
      "customer_name": "Jan Novak",                    (volitelne, jinak z profilu)
      "customer_email": "jan@example.cz",               (volitelne, jinak z profilu)
      "customer_phone": "+420...",                       (volitelne)
      "delivery_address": "...",                          (volitelne, jinak z profilu)
      "delivery_zip": "12345",              (volitelne, jinak billing_zip/profil - povinne pro dopravu Toptrans)
      "billing_zip": "12345",                             (volitelne, jinak z profilu)
      "note": "...",                                        (volitelne, poznamka zakaznika)
      "shipping_method_id": 2,                               (volitelne)
      "payment_method_id": 1                                  (volitelne)
    }
    """
    # Robert 2026-08-18: docasna deaktivace kosiku - viz stejny priznak a
    # zduvodneni v api/cart.py cart_add_item(). Dokonceni objednavky je
    # posledni krok kosikoveho wizardu (cart.html step "Dokonceni
    # objednavky"), takze patri ke stejnemu vypinaci jako pridavani
    # polozek. Rucni zadani adminem (POST /api/admin/orders) timhle
    # priznakem NENI ovlivneno - jina cesta, jiny endpoint.
    conn_flag = get_conn()
    try:
        with conn_flag.cursor() as cur_flag:
            cart_enabled = get_setting(cur_flag, "cart_enabled", "1") != "0"
    finally:
        conn_flag.close()
    if not cart_enabled:
        return jsonify({"error": "Košík je dočasně nedostupný."}), 403

    body = request.get_json(silent=True) or {}
    user = current_user()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            try:
                result = _resolve_and_insert_order(cur, body, attribute_user_id=user["id"], profile_user_id=user["id"])
            except _OrderCreateError as e:
                conn.rollback()
                return jsonify({"error": e.message}), e.status_code

            cur.execute(
                "INSERT INTO shop_order_status_history (order_id, status, changed_by, note) "
                "VALUES (%s, 'nova', %s, 'Objednávka vytvořena.')",
                (result["order_id"], user["id"]),
            )
            # bot5, 2026-10-02 (dealersky program etapa 1): objednavka zakaznika, ktery prisel z odkazu dealera (cookie dlr, 30 dni od
            # prokliku, last-click), se pripise dealerovi (shop_orders.dealer_id/dealer_click_id/order_path) - provize se pocita z techto
            # dat. attach_attribution NIKDY nevyhodi vyjimku (objednavka se kvuli dealerovi nesmi rozbit), selhani jen zaloguje.
            try:
                import dealers
                dealers.attach_attribution(cur, result["order_id"], user)
            except Exception:
                app.logger.exception("orders_create: atribuce dealera selhala (objednavka zalozena bez ni)")
        conn.commit()
    finally:
        conn.close()

    _send_order_emails_bg(result)

    return jsonify({
        "status": "ok", "id": result["order_id"],
        "order_number": result["order_number"], "total_czk": result["total"],
    }), 201


@app.post("/api/admin/orders")
@require_permission("objednavky", "vytvorit")
def admin_orders_create():
    """
    Rucni zadani objednavky adminem - bot3, 2026-07-25 (v4). Robert:
    "objednávku lze zadat i ručně" (napr. telefonicky/osobne prijata
    objednavka, kterou zakaznik sam pres web nezadal).

    Rozdil oproti samoobsluznemu POST /api/orders:
      - volajici je admin (@admin_required), ne zakaznik - proto zadny
        login_required na strane "zakaznika".
      - volitelne "user_id": pokud je zadane, objednavka se napoji na
        existujici ucet (shop_orders.user_id) a POUZIJE SE JEHO PROFIL
        (predvyplneni kontaktu/fakturace + slevova skupina), presne jako
        u samoobsluzneho letu. Bez "user_id" jde o objednavku BEZ vazby
        na ucet (stary "guest" zpusob - kontaktni udaje MUSI prijit v
        requestu, zadna sleva se neaplikuje).
      - "use_cart": true je povolene jen spolu s "user_id" (kosik je
        vazany na ucet).
      - do historie stavu se jako "changed_by" zapise ADMIN (ne zakaznik),
        s poznamkou, ze objednavka byla zadana rucne.

    Ocekavany JSON payload - stejny jako POST /api/orders, navic:
    {
      "user_id": 5,             (volitelne - napojeni na existujici ucet)
      "history_note": "..."     (volitelne, jinak default "Objednávka zadána ručně...")
      ...ostatni pole stejna jako u POST /api/orders...
    }
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}

    raw_user_id = body.get("user_id")
    target_user_id = None
    if raw_user_id is not None:
        try:
            target_user_id = int(raw_user_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatné user_id."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if target_user_id is not None:
                cur.execute("SELECT id FROM app_users WHERE id=%s", (target_user_id,))
                if not cur.fetchone():
                    conn.rollback()
                    return jsonify({"error": "Zvolený zákazník (user_id) neexistuje."}), 400

            try:
                result = _resolve_and_insert_order(
                    cur, body, attribute_user_id=target_user_id, profile_user_id=target_user_id,
                    require_active=False,
                )
            except _OrderCreateError as e:
                conn.rollback()
                return jsonify({"error": e.message}), e.status_code

            history_note = (body.get("history_note") or "").strip() or (
                f"Objednávka zadána ručně administrátorem ({admin['name'] or admin['email']})."
            )
            cur.execute(
                "INSERT INTO shop_order_status_history (order_id, status, changed_by, note) "
                "VALUES (%s, 'nova', %s, %s)",
                (result["order_id"], admin["id"], history_note),
            )

            # --- V8 (bot3, 2026-07-25): hlidani duplicit ---
            # Objednavka BEZ napojeni na ucet (target_user_id is None), ale
            # s e-mailem/ICO, ktere uz mame u jineho zakaznika -> upozornit
            # admina v odpovedi (viz customers.py::find_duplicate_customers).
            # NEBLOKUJE vytvoreni objednavky - jen "nabidne propojeni" pro
            # priste, presne jak Robert rozhodl (ne tiche auto-propojeni,
            # ktere by mohlo zmenit uz vytvorenou objednavku).
            duplicate_suggestions = []
            if target_user_id is None:
                duplicate_suggestions = customers.find_duplicate_customers(
                    cur, email=body.get("customer_email"), ico=body.get("billing_ico")
                )
        conn.commit()
    finally:
        conn.close()

    _send_order_emails_bg(result)

    response = {
        "status": "ok", "id": result["order_id"],
        "order_number": result["order_number"], "total_czk": result["total"],
    }
    if duplicate_suggestions:
        response["duplicate_suggestions"] = duplicate_suggestions
        response["duplicate_warning"] = (
            "Nalezen(i) existující zákazník(ci) se stejným e-mailem nebo IČO - "
            "zvažte propojení této objednávky na jejich účet (viz duplicate_suggestions)."
        )
    return jsonify(response), 201


@app.get("/api/orders")
@login_required
def orders_list_mine():
    """Vlastni objednavky prihlaseneho uzivatele (nejnovejsi prvni)."""
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM shop_orders WHERE user_id=%s ORDER BY created_at DESC",
                (user["id"],),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    # bot18, 2026-09-05: _serialize_order_for_customer(), NE _serialize_order -
    # ta druha obsahuje admin_note (interni poznamky pro personal, napr.
    # "podezrela objednavka, overit"), nalezeno pri stavbe "moje objednavky"
    # jako uz existujici mezera (endpoint byl zivy driv, nikdo si nevsiml).
    return jsonify({"orders": [_serialize_order_for_customer(r) for r in rows]})


@app.get("/api/orders/<int:order_id>")
@login_required
def orders_get(order_id):
    """Detail jedne objednavky vcetne polozek - jen vlastnik nebo admin."""
    user = current_user()
    conn = get_conn()
    try:
        order, items = _fetch_order_with_items(conn, order_id)
        # Popisky mist montaze - dokud je spojeni jeste otevrene (viz
        # komentar u _serialize_item, "misto_labels" nema vlastni cur).
        with conn.cursor() as cur:
            misto_labels = _montaz_mista_map(cur, jen_aktivni=False)
    finally:
        conn.close()
    if not order:
        return jsonify({"error": "Objednávka neexistuje."}), 404
    if order["user_id"] != user["id"] and user["role"] != "admin":
        return jsonify({"error": "Nemáte oprávnění k této objednávce.", "code": "forbidden"}), 403
    # admin vidi plny detail (vc. admin_note), zakaznik jen ozeznanou verzi -
    # stejny duvod jako u orders_list_mine() vyse.
    result = _serialize_order(order) if user["role"] == "admin" else _serialize_order_for_customer(order)
    result["items"] = [_serialize_item(i, misto_labels, user["role"] == "admin") for i in items]
    return jsonify({"order": result})


@app.get("/api/orders/<int:order_id>/payment-qr")
@login_required
def orders_payment_qr(order_id):
    """PNG QR kod "QR Platba" (bankovni prevod, cesky SPAYD standard) pro
    zalohovou fakturu teto objednavky - jen vlastnik nebo admin (stejne
    opravneni jako GET /api/orders/<id>). Existuje jen kdyz objednavka
    ma zalohovou fakturu (platebni metoda s requires_advance_invoice=1,
    napr. "QR platba"/"Platba předem" - viz documents.py::
    create_proforma_invoice_if_needed, vola se hned pri vytvoreni
    objednavky) - VS = variable_symbol te faktury, presne to, co
    bank_statements.py::match_bank_payments_to_orders pouziva k
    automatickemu parovani prijatych plateb (bank_paid=1). Zadna nova
    platebni logika - jen QR reprezentace uz existujiciho mechanismu."""
    try:
        import qrcode
    except ImportError:
        return jsonify({"error": "QR generátor není nainstalovaný."}), 500
    user = current_user()
    conn = get_conn()
    try:
        order, _items = _fetch_order_with_items(conn, order_id)
        if not order:
            return jsonify({"error": "Objednávka neexistuje."}), 404
        if order["user_id"] != user["id"] and user["role"] != "admin":
            return jsonify({"error": "Nemáte oprávnění k této objednávce.", "code": "forbidden"}), 403
        with conn.cursor() as cur:
            cur.execute(
                "SELECT variable_symbol, amount_due_czk FROM shop_documents "
                "WHERE order_id=%s AND document_type='proforma_invoice' AND variable_symbol IS NOT NULL "
                "ORDER BY id DESC LIMIT 1",
                (order_id,),
            )
            proforma = cur.fetchone()
    finally:
        conn.close()
    if not proforma:
        return jsonify({"error": "K této objednávce zatím není vystavená zálohová faktura."}), 404

    iban = documents._cz_account_to_iban(documents.SUPPLIER["bank_account"])
    label = f"Objednavka {order['order_number']}"
    spayd = documents._build_spayd(iban, float(proforma["amount_due_czk"]), proforma["variable_symbol"], label)

    img = qrcode.make(spayd)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), mimetype="image/png", headers={
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",  # castka/VS se vazou na fakturu, neni duvod cachovat napric requesty
    })


# ---------------------------------------------------------------------------
# Admin: prehled objednavek s filtrovanim podle stavu + pocty pro taby
# ---------------------------------------------------------------------------

@app.get("/api/admin/orders")
@require_permission("objednavky", "zobrazit")
def admin_orders_list():
    """
    Seznam objednavek pro admin prehled.

    ?status=nova           - filtr na jeden konkretni stav (viz ORDER_STATUSES)
    ?urgent=1               - jen urgentni objednavky
    ?q=...                  - hledani v cisle objednavky / jmenu / e-mailu
    ?date_from=YYYY-MM-DD   - objednano od (vcetne, cely den)
    ?date_to=YYYY-MM-DD     - objednano do (vcetne, cely den)
    ?shipping_method=...    - presny nazev zpusobu dopravy (shipping_method_name snapshot)
    ?payment_method=...     - presny nazev zpusobu platby (payment_method_name snapshot)
    ?price_min=...          - total_czk >= (Robert 2026-07-25: "dodělej plné
    ?price_max=...          -   filtrování v objednávkách")
    ?has_account=1|0        - 1 = jen objednavky napojene na existujici ucet
                               (user_id NENI NULL), 0 = jen bez uctu (guest,
                               ucet mezitim smazan apod.)

    Odpoved obsahuje "counts" (pocet objednavek pro KAZDY stav + "all" a
    "urgent") - urceno primo pro vykresleni tabu s cisly, jak je zvykem v
    beznych e-shop administracich (Vsechny / Nova (n) / Potvrzena (n) /
    ... / Urgent (n)), bez nutnosti volat endpoint vicekrat. Pocty vzdy
    odpovidaji CELE tabulce (bez ostatnich filtru), aby taby zustaly
    stabilni pri kombinaci s pokrocilymi filtry - jen samotny seznam
    "orders" respektuje vsechny aktivni filtry najednou (AND).
    """
    status = request.args.get("status")
    urgent_only = request.args.get("urgent") == "1"
    q = (request.args.get("q") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    shipping_method = (request.args.get("shipping_method") or "").strip()
    payment_method = (request.args.get("payment_method") or "").strip()
    price_min = request.args.get("price_min", type=float)
    price_max = request.args.get("price_max", type=float)
    has_account = request.args.get("has_account")
    origin = (request.args.get("origin") or "").strip()                 # bot5, 2026-10-03: eshop = hlavni e-shop (order_host NULL), jinak host mini-shopu
    shipping_review = request.args.get("shipping_review") == "1"
    # Testovaci objednavky (WORKFLOW.md bod 27) se do prehledu ani do poctu
    # NEPOCITAJI - Robert 2026-09-10: "testovaci objednavky se nesmi pocitat
    # do statistik a prehledu jako skutecne". Filtr je VIDITELNY a
    # prepinatelny (`?include_test=1`), ne natvrdo skryty - jinak by nesla
    # zkontrolovat davka po generatoru.
    # OCEKAVANY VEDLEJSI EFEKT: k 2026-09-10 je vsech 39 existujicich
    # objednavek oznacenych jako testovaci, takze vychozi prehled je
    # PRAZDNY. Je to spravne, projekt je pre-launch a zadna skutecna
    # objednavka zatim neexistuje.
    include_test = request.args.get("include_test") == "1"
    test_where_sql = "" if include_test else " WHERE is_test=0"

    if status and status not in ORDER_STATUSES:
        return jsonify({"error": "Neplatný status."}), 400

    where, params = [], []
    if not include_test:
        where.append("is_test=0")
    if status:
        where.append("status=%s")
        params.append(status)
    if urgent_only:
        where.append("is_urgent=1")
    if q:
        where.append("(order_number LIKE %s OR customer_name LIKE %s OR customer_email LIKE %s)")
        like = f"%{q}%"
        params += [like, like, like]
    if date_from:
        where.append("created_at >= %s")
        params.append(date_from + " 00:00:00")
    if date_to:
        where.append("created_at <= %s")
        params.append(date_to + " 23:59:59")
    if shipping_method:
        where.append("shipping_method_name=%s")
        params.append(shipping_method)
    if payment_method:
        where.append("payment_method_name=%s")
        params.append(payment_method)
    if price_min is not None:
        where.append("total_czk >= %s")
        params.append(price_min)
    if price_max is not None:
        where.append("total_czk <= %s")
        params.append(price_max)
    if has_account == "1":
        where.append("user_id IS NOT NULL")
    elif has_account == "0":
        where.append("user_id IS NULL")
    if origin == "eshop":
        where.append("order_host IS NULL")
    elif origin:
        where.append("order_host=%s")
        params.append(origin[:255])
    if shipping_review:
        where.append("shipping_review=1")

    # Stránkování (task #78/81) - admin-only, defaultně stránkuj.
    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            base_sql = "SELECT * FROM shop_orders"
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            rows, total = paginated_query(cur, base_sql, where_sql, params, " ORDER BY created_at DESC", page, page_size)

            # Napárované faktury (Robert 2026-08-22: "v přehledu
            # objednávek je potřeba sloupec s číslem napárované
            # faktury") - jen skutecne faktury (document_type='invoice'),
            # NE proforma/VDD/dodaci list. Jedna davkova SELECT pro
            # celou stranku (ne N+1 dotaz na kazdou objednavku), radi
            # se podle issue_date - u vetsiny objednavek 0-1 faktura,
            # vicero jen pri opravnem/castecnem doklade.
            invoices_by_order = {}
            order_ids = [r["id"] for r in rows]
            if order_ids:
                cur.execute(
                    "SELECT id, order_id, document_number FROM shop_documents "
                    "WHERE document_type='invoice' AND order_id IN %s "
                    "ORDER BY order_id, issue_date, id",
                    (tuple(order_ids),),
                )
                for d in cur.fetchall():
                    invoices_by_order.setdefault(d["order_id"], []).append(
                        {"id": d["id"], "document_number": d["document_number"]}
                    )

            # Pocty do tabu MUSI respektovat tentyz filtr jako seznam -
            # jinak by tab hlasil cislo, ktere se po rozkliknuti neobjevi.
            cur.execute(
                f"SELECT status, COUNT(*) AS n FROM shop_orders{test_where_sql} GROUP BY status")
            status_counts = {r["status"]: r["n"] for r in cur.fetchall()}
            cur.execute(
                "SELECT COUNT(*) AS n FROM shop_orders WHERE is_urgent=1"
                + ("" if include_test else " AND is_test=0"))
            urgent_count = cur.fetchone()["n"]
            cur.execute(f"SELECT COUNT(*) AS n FROM shop_orders{test_where_sql}")
            all_count = cur.fetchone()["n"]
            # bot5, 2026-10-03: seznam puvodu pro filtr (hlavni e-shop + kazdy mini-shop, ze ktereho prisla aspon jedna objednavka)
            cur.execute("SELECT order_host, order_lang, COUNT(*) AS n FROM shop_orders WHERE order_host IS NOT NULL" + ("" if include_test else " AND is_test=0") + " GROUP BY order_host, order_lang ORDER BY order_host, order_lang")
            origins = [{"key": "eshop", "label": "e-shop"}] + [{"key": r["order_host"], "label": _origin_label(r), "count": r["n"]} for r in cur.fetchall()]
    finally:
        conn.close()

    counts = {"all": all_count, "urgent": urgent_count}
    for s in ORDER_STATUSES:
        counts[s] = status_counts.get(s, 0)

    serialized_orders = []
    for r in rows:
        o = _serialize_order(r)
        o["invoices"] = invoices_by_order.get(r["id"], [])
        serialized_orders.append(o)

    resp = {"orders": serialized_orders, "counts": counts, "origins": origins}
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.get("/api/admin/orders/<int:order_id>")
@require_permission("objednavky", "zobrazit")
def admin_orders_get(order_id):
    """Detail objednavky pro admina - vcetne polozek a historie zmen stavu."""
    conn = get_conn()
    try:
        order, items = _fetch_order_with_items(conn, order_id)
        history = []
        with conn.cursor() as cur:
            misto_labels = _montaz_mista_map(cur, jen_aktivni=False)
            if order:
                cur.execute(
                    "SELECT h.*, u.name AS changed_by_name FROM shop_order_status_history h "
                    "LEFT JOIN app_users u ON u.id = h.changed_by "
                    "WHERE h.order_id=%s ORDER BY h.changed_at ASC, h.id ASC",
                    (order_id,),
                )
                history = cur.fetchall()
    finally:
        conn.close()
    if not order:
        return jsonify({"error": "Objednávka neexistuje."}), 404

    result = _serialize_order(order)
    result["items"] = [_serialize_item(i, misto_labels, True) for i in items]
    result["history"] = [
        {
            "status": h["status"],
            "status_label": STATUS_LABELS_CZ.get(h["status"], h["status"]),
            "changed_by": h["changed_by"],
            "changed_by_name": h["changed_by_name"],
            "changed_at": _dt(h["changed_at"]),
            "note": h["note"],
        }
        for h in history
    ]
    return jsonify({"order": result})


# Stavy, ve kterych uz nema smysl polozky pridavat/mazat/menit mnozstvi -
# "zrusena" je zrusena objednavka, "fakturovana" uz ma vystavenou fakturu
# se snapshotem puvodnich polozek (zmena polozek POTOM by fakturu rozjela
# s objednavkou do nesouladu), "expedovana" uz je fyzicky odeslana
# zakaznikovi (Robert pres bot3, 2026-08-22: "vyřízená objednávka nelze
# upravovat" - puvodne tu chybela, coz by dovolilo menit polozky u uz
# odeslaneho zbozi; doplneno DODATECNE k puvodnimu zadani na PUT qty
# endpoint, ale tyka se VSECH TRI endpointu add/delete/update-qty
# stejne, protoze sdileji tuhle jednu konstantu). Ve vsech ostatnich
# stavech (vc. tech se sklad-jiz-odectenym, viz STOCK_DEDUCTED_STATUSES)
# editace polozek povolena je - jen se pri ni sklad odpovidajicim
# zpusobem doodecte/vrati (viz nize).
NON_EDITABLE_ITEM_STATUSES = {"zrusena", "fakturovana", "expedovana"}


def _recalc_order_total(cur, order_id):
    cur.execute("SELECT COALESCE(SUM(line_total_czk), 0) AS s FROM shop_order_items WHERE order_id=%s", (order_id,))
    items_total = float(cur.fetchone()["s"])
    cur.execute("SELECT shipping_price_czk, payment_price_czk FROM shop_orders WHERE id=%s", (order_id,))
    o = cur.fetchone()
    total = round(items_total + float(o["shipping_price_czk"]) + float(o["payment_price_czk"]), 2)
    cur.execute("UPDATE shop_orders SET total_czk=%s WHERE id=%s", (total, order_id))
    return total


@app.post("/api/admin/orders/<int:order_id>/items")
@require_permission("objednavky", "upravit")
def admin_orders_add_item(order_id):
    """
    Rucni pridani polozky do JIZ EXISTUJICI objednavky (Robert 2026-08-06:
    "v objednávce je potřeba přidat možnost přidat zboží, produkt službu") -
    admin pri telefonicke/osobni komunikaci se zakaznikem dodatecne doplni
    zapomenutou polozku, nebo pripise sluzbu (montaz, doprava navic...),
    ktera v katalogu vubec neni.

    Dve varianty body:
      {"product_id": 12, "qty": 2}                     - z katalogu (cena
        se dopocita z aktualni ceny produktu a slevy zakaznika ulozene na
        objednavce, pokud "unit_price_czk" neni zadana rucne)
      {"name": "Montáž", "qty": 1, "unit_price_czk": 500} - volna polozka
        bez vazby na katalog (sluzba apod.) - "unit_price_czk" povinna,
        "product_id" zustava NULL (shop_order_items.product_id je NULLable
        presne pro tenhle pripad).

    Pokud uz ma objednavka odecteny sklad (STOCK_DEDUCTED_STATUSES) a jde
    o katalogovy produkt, sklad se odecte HNED (stejna logika/kontrola
    jako pri prechodu do potvrzena v _apply_order_update) - jinak by
    dodatecne pridana polozka zustala ze skladu neodectena.
    """
    body = request.get_json(silent=True) or {}
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_orders WHERE id=%s FOR UPDATE", (order_id,))
            order = cur.fetchone()
            if not order:
                conn.rollback()
                return jsonify({"error": "Objednávka neexistuje."}), 404
            if order["status"] in NON_EDITABLE_ITEM_STATUSES:
                conn.rollback()
                return jsonify({"error": (
                    f"Položky nelze upravovat u objednávky ve stavu „{STATUS_LABELS_CZ.get(order['status'], order['status'])}“."
                )}), 400

            try:
                qty = int(body.get("qty"))
            except (TypeError, ValueError):
                return jsonify({"error": "Neplatné množství."}), 400
            if qty <= 0:
                conn.rollback()
                return jsonify({"error": "Množství musí být kladné celé číslo."}), 400

            raw_product_id = body.get("product_id")
            product_id = None
            if raw_product_id is not None:
                try:
                    product_id = int(raw_product_id)
                except (TypeError, ValueError):
                    conn.rollback()
                    return jsonify({"error": "Neplatné product_id."}), 400

            if product_id is not None:
                cur.execute(
                    "SELECT id, name, price_czk_placeholder, stock_qty, active FROM shop_products "
                    "WHERE id=%s FOR UPDATE",
                    (product_id,),
                )
                product = cur.fetchone()
                if not product:
                    conn.rollback()
                    return jsonify({"error": "Produkt neexistuje nebo není dostupný."}), 400
                # bot5, 2026-09-23: admin_orders_add_item je uz staff-only
                # (@require_permission), zadny active=1 filtr tu tedy neni
                # potreba - stejna zmena a stejny duvod jako v
                # _resolve_and_insert_order() (require_active=False pro
                # admin_orders_create) vyse.
                name = product["name"]
                if body.get("unit_price_czk") is not None:
                    try:
                        unit_price = round(float(body["unit_price_czk"]), 2)
                    except (TypeError, ValueError):
                        conn.rollback()
                        return jsonify({"error": "Neplatná cena za kus."}), 400
                else:
                    discount = float(order["customer_discount_percent"] or 0)
                    base_price = float(product["price_czk_placeholder"] or 0)
                    unit_price = round(base_price * (1 - discount / 100), 2) if discount else base_price
                # math.isfinite (bezpecnostni nalez, bot3/revize kodu
                # 2026-09-02): float() prijme "nan"/"inf" bez vyjimky a
                # obe porovnani "< 0" jsou u nich VZDY False (NaN nikdy
                # nesplni zadne porovnani, +inf neni < 0) - bez tehle
                # kontroly by prošly az do DB.
                if not math.isfinite(unit_price) or unit_price < 0:
                    conn.rollback()
                    return jsonify({"error": "Cena za kus nesmí být záporná."}), 400
            else:
                name = (body.get("name") or "").strip()
                if not name:
                    conn.rollback()
                    return jsonify({"error": "Bez product_id je nutné zadat název položky (name)."}), 400
                try:
                    unit_price = round(float(body.get("unit_price_czk")), 2)
                except (TypeError, ValueError):
                    conn.rollback()
                    return jsonify({"error": "U volné položky (bez product_id) je nutné zadat unit_price_czk."}), 400
                if not math.isfinite(unit_price) or unit_price < 0:
                    conn.rollback()
                    return jsonify({"error": "Cena za kus nesmí být záporná."}), 400

            line_total = round(unit_price * qty, 2)

            if product_id is not None and order["status"] in STOCK_DEDUCTED_STATUSES:
                if product["stock_qty"] < qty:
                    conn.rollback()
                    return jsonify({"error": (
                        f"Nedostatek skladu pro „{name}“ (skladem {product['stock_qty']} ks, "
                        f"objednávka už má sklad odečtený, takže nová položka musí být hned k dispozici)."
                    )}), 400
                cur.execute("UPDATE shop_products SET stock_qty = stock_qty - %s WHERE id=%s", (qty, product_id))
                cur.execute(
                    "INSERT INTO shop_stock_movements "
                    "(product_id, movement_type, qty, unit_price_czk, note, document_number, user_id) "
                    "VALUES (%s, 'issue', %s, %s, %s, %s, %s)",
                    (product_id, qty, unit_price, f"Objednávka {order['order_number']} - dodatečně přidaná položka",
                     order["order_number"], admin["id"]),
                )

            cur.execute(
                "INSERT INTO shop_order_items "
                "(order_id, product_id, product_name_snapshot, unit_price_czk, qty, line_total_czk) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (order_id, product_id, name, unit_price, qty, line_total),
            )
            item_id = cur.lastrowid
            new_total = _recalc_order_total(cur, order_id)
        conn.commit()
    finally:
        conn.close()

    return jsonify({
        "status": "ok",
        "item": {
            "id": item_id, "product_id": product_id, "product_name": name,
            "unit_price_czk": unit_price, "qty": qty, "line_total_czk": line_total,
        },
        "total_czk": new_total,
    }), 201


@app.delete("/api/admin/orders/<int:order_id>/items/<int:item_id>")
@require_permission("objednavky", "upravit")
def admin_orders_delete_item(order_id, item_id):
    """
    Odebrani (omylem pridane/spatne) polozky z objednavky - protejsek k
    POST .../items vyse. Pokud uz ma objednavka odecteny sklad a jde o
    katalogovy produkt, sklad se vrati (stejnym zpusobem jako pri zruseni
    cele objednavky v _apply_order_update).
    """
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_orders WHERE id=%s FOR UPDATE", (order_id,))
            order = cur.fetchone()
            if not order:
                conn.rollback()
                return jsonify({"error": "Objednávka neexistuje."}), 404
            if order["status"] in NON_EDITABLE_ITEM_STATUSES:
                conn.rollback()
                return jsonify({"error": (
                    f"Položky nelze upravovat u objednávky ve stavu „{STATUS_LABELS_CZ.get(order['status'], order['status'])}“."
                )}), 400

            cur.execute("SELECT * FROM shop_order_items WHERE id=%s AND order_id=%s", (item_id, order_id))
            item = cur.fetchone()
            if not item:
                conn.rollback()
                return jsonify({"error": "Položka neexistuje."}), 404

            if item["product_id"] is not None and order["status"] in STOCK_DEDUCTED_STATUSES:
                cur.execute("UPDATE shop_products SET stock_qty = stock_qty + %s WHERE id=%s",
                            (item["qty"], item["product_id"]))
                cur.execute(
                    "INSERT INTO shop_stock_movements "
                    "(product_id, movement_type, qty, unit_price_czk, note, document_number, user_id) "
                    "VALUES (%s, 'receipt', %s, %s, %s, %s, %s)",
                    (item["product_id"], item["qty"], item["unit_price_czk"],
                     f"Objednávka {order['order_number']} - odebrání položky, vrácení skladu",
                     order["order_number"], admin["id"]),
                )

            cur.execute("DELETE FROM shop_order_items WHERE id=%s", (item_id,))
            new_total = _recalc_order_total(cur, order_id)
        conn.commit()
    finally:
        conn.close()

    return jsonify({"status": "ok", "total_czk": new_total})


@app.put("/api/admin/orders/<int:order_id>/items/<int:item_id>")
@require_permission("objednavky", "upravit")
def admin_orders_update_item_qty(order_id, item_id):
    """
    Uprava mnozstvi JIZ EXISTUJICI polozky (Robert 2026-08-22: "chceme v
    objednávkách mít možnost upravovat počet ks u položek" - dnes se
    misto toho musela polozka smazat a znovu pridat, coz zbytecne
    zahazovalo puvodni radek a prepocitavalo cenu od znova).

    Body: {"qty": N} - nove CELKOVE mnozstvi (ne delta).

    Pokud ma polozka product_id a objednavka je ve stavu jiz odectenem
    ze skladu (STOCK_DEDUCTED_STATUSES), sklad se upravuje o DELTU
    (rozdil stare/nove qty), stejny vzor jako v _apply_order_update pri
    prechodu objednavky do/ze stavu s odectenym skladem - NE o cele
    nove mnozstvi (to by sklad zdvojnasobilo/vynulovalo spatne). Mimo
    tyhle stavy se sklad vubec nedotyka - odecte se az pri pozdejsim
    prechodu do STOCK_DEDUCTED_STATUSES, uz s aktualni (upravenou) qty.
    """
    body = request.get_json(silent=True) or {}
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_orders WHERE id=%s FOR UPDATE", (order_id,))
            order = cur.fetchone()
            if not order:
                conn.rollback()
                return jsonify({"error": "Objednávka neexistuje."}), 404
            if order["status"] in NON_EDITABLE_ITEM_STATUSES:
                conn.rollback()
                return jsonify({"error": (
                    f"Položky nelze upravovat u objednávky ve stavu „{STATUS_LABELS_CZ.get(order['status'], order['status'])}“."
                )}), 400

            cur.execute("SELECT * FROM shop_order_items WHERE id=%s AND order_id=%s", (item_id, order_id))
            item = cur.fetchone()
            if not item:
                conn.rollback()
                return jsonify({"error": "Položka neexistuje."}), 404

            try:
                new_qty = int(body.get("qty"))
            except (TypeError, ValueError):
                conn.rollback()
                return jsonify({"error": "Neplatné množství."}), 400
            if new_qty <= 0:
                conn.rollback()
                return jsonify({"error": "Množství musí být kladné celé číslo (pro smazání položky použij DELETE)."}), 400

            old_qty = item["qty"]
            delta = new_qty - old_qty
            if delta != 0 and item["product_id"] is not None and order["status"] in STOCK_DEDUCTED_STATUSES:
                cur.execute("SELECT stock_qty FROM shop_products WHERE id=%s FOR UPDATE", (item["product_id"],))
                product = cur.fetchone()
                if delta > 0:
                    if not product or product["stock_qty"] < delta:
                        conn.rollback()
                        avail = product["stock_qty"] if product else 0
                        return jsonify({"error": (
                            f"Nedostatek skladu pro navýšení „{item['product_name_snapshot']}“ o {delta} ks "
                            f"(skladem jen {avail} ks, objednávka už má sklad odečtený)."
                        )}), 400
                    cur.execute("UPDATE shop_products SET stock_qty = stock_qty - %s WHERE id=%s",
                                (delta, item["product_id"]))
                    cur.execute(
                        "INSERT INTO shop_stock_movements "
                        "(product_id, movement_type, qty, unit_price_czk, note, document_number, user_id) "
                        "VALUES (%s, 'issue', %s, %s, %s, %s, %s)",
                        (item["product_id"], delta, item["unit_price_czk"],
                         f"Objednávka {order['order_number']} - navýšení množství položky ({old_qty}→{new_qty} ks)",
                         order["order_number"], admin["id"]),
                    )
                else:
                    cur.execute("UPDATE shop_products SET stock_qty = stock_qty + %s WHERE id=%s",
                                (-delta, item["product_id"]))
                    cur.execute(
                        "INSERT INTO shop_stock_movements "
                        "(product_id, movement_type, qty, unit_price_czk, note, document_number, user_id) "
                        "VALUES (%s, 'receipt', %s, %s, %s, %s, %s)",
                        (item["product_id"], -delta, item["unit_price_czk"],
                         f"Objednávka {order['order_number']} - snížení množství položky ({old_qty}→{new_qty} ks)",
                         order["order_number"], admin["id"]),
                    )

            new_line_total = round(float(item["unit_price_czk"]) * new_qty, 2)
            cur.execute(
                # qty_dispatched nesmi prevysit nove (snizene) mnozstvi -
                # LEAST() ho v tom pripade srazi dolu, at "Zbyva" nikdy
                # nevyjde zaporne (viz dodaci listy, Robert 2026-09-16).
                "UPDATE shop_order_items SET qty=%s, line_total_czk=%s, "
                "qty_dispatched=LEAST(qty_dispatched, %s) WHERE id=%s",
                (new_qty, new_line_total, new_qty, item_id),
            )
            new_total = _recalc_order_total(cur, order_id)
        conn.commit()
    finally:
        conn.close()

    return jsonify({
        "status": "ok",
        "item": {"id": item_id, "qty": new_qty, "line_total_czk": new_line_total},
        "total_czk": new_total,
    })


@app.put("/api/admin/orders/<int:order_id>/items/<int:item_id>/dispatch")
@require_permission("objednavky", "upravit")
def admin_orders_update_item_dispatch(order_id, item_id):
    """Dodaci listy (Robert primo, 2026-09-16: "potrebujeme resit dodaci
    listy... polozky ktere se vydali a ktere jeste ne, navazano na
    vydejky ze skladu") - nastavi qty_dispatched (kolik z teto polozky
    uz FYZICKY odeslo, na rozdil od uctetniho odectu skladu, ktery resi
    STOCK_DEDUCTED_STATUSES pro CELOU objednavku najednou pri zmene
    stavu). Zamerne NEMENI shop_products.stock_qty ani nezapisuje do
    shop_stock_movements - je to cisty procesni pokrok/checklist, ne
    dalsi ucetnictvi zasoby (to uz existuje a tenhle sloupec ho
    nezdvojuje).

    Body: {"qty_dispatched": N} - nove CELKOVE (ne delta) mnozstvi
    vydane z teto polozky, 0..qty."""
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_orders WHERE id=%s", (order_id,))
            if not cur.fetchone():
                return jsonify({"error": "Objednávka neexistuje."}), 404
            cur.execute("SELECT id, qty FROM shop_order_items WHERE id=%s AND order_id=%s", (item_id, order_id))
            item = cur.fetchone()
            if not item:
                return jsonify({"error": "Položka neexistuje."}), 404
            try:
                qty_dispatched = int(body.get("qty_dispatched"))
            except (TypeError, ValueError):
                return jsonify({"error": "Neplatné množství."}), 400
            if not (0 <= qty_dispatched <= item["qty"]):
                return jsonify({"error": f"Množství musí být 0 až {item['qty']} (objednané množství)."}), 400
            cur.execute("UPDATE shop_order_items SET qty_dispatched=%s WHERE id=%s", (qty_dispatched, item_id))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "item": {"id": item_id, "qty_dispatched": qty_dispatched}})


def _apply_order_update(order_id, admin, new_status=None, is_urgent=None, admin_note=None, history_note=None):
    """
    Jadro zmeny JEDNE objednavky - status prechod (dle ALLOWED_TRANSITIONS),
    is_urgent priznak a/nebo admin_note, vcetne odectu/vraceni skladu a
    e-mailu zakaznikovi pri zmene stavu. Sdilene mezi PUT /api/admin/orders/<id>
    (jednotliva zmena) a POST /api/admin/orders/bulk-status / bulk-urgent
    (hromadna zmena, viz NAVRH_HROMADNE_AKCE.md) - V11 (bot3, 2026-07-26),
    obe cesty musi projit STEJNOU validaci prechodu stavu a stejne
    odecitat/vracet sklad, proto se hromadna akce NEDELA jako holy UPDATE.

    Vraci (ok: bool, error: str|None).
    """
    if new_status is not None and new_status not in ORDER_STATUSES:
        return False, "Neplatný status."

    conn = get_conn()
    order_number = None
    customer_email = None
    status_changed = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_orders WHERE id=%s FOR UPDATE", (order_id,))
            order = cur.fetchone()
            if not order:
                conn.rollback()
                return False, "Objednávka neexistuje."

            old_status = order["status"]
            order_number = order["order_number"]
            customer_email = order["customer_email"]

            fields, params = [], []

            if new_status is not None and new_status != old_status:
                allowed = ALLOWED_TRANSITIONS.get(old_status, set())
                if new_status not in allowed:
                    conn.rollback()
                    return False, (
                        f"Přechod ze stavu „{STATUS_LABELS_CZ.get(old_status, old_status)}“ "
                        f"do „{STATUS_LABELS_CZ.get(new_status, new_status)}“ není povolen."
                    )

                # Robert 2026-07-31: "pri platbe predem se muze zbozi
                # pripravit az je zaplaceno" - u platebnich metod
                # oznacenych jako "platba predem" (shop_payment_methods.
                # requires_advance_invoice) nejde na Pripravit, dokud
                # neni evidovana prijata platba (payment_received_at,
                # nastavuje POST .../documents/payment-received - VDD).
                # Dobirka/platba pri prevzeti tenhle priznak nemaji,
                # tam se expeduje bez cekani na platbu (Robert:
                # "pri platbe prevodem/dobirku se expeduje, na platbu
                # se neceka" - vyjimka je prave jen "platba predem").
                if new_status == "pripravit" and old_status == "potvrzena":
                    # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02, zive
                    # overeno): payment_method_name je SNAPSHOT ulozeny na
                    # objednavce (napr. z CSV importu - "Převodem - zálohová
                    # faktura") - presny match proti ZIVEMU nazvu v
                    # shop_payment_methods ("Platba předem") nikdy nesedi pro
                    # historicka data (nulovy prekryv, overeno pro VSECH 39
                    # objednavek), gate tak mlcky NEPLATIL pro zadnou z nich.
                    # Fallback na klicova slova "zálohov"/"předem" - STEJNY
                    # vzor a STEJNE klice jako bank_statements.py
                    # (create_proforma_invoice_if_needed) - vedome NE
                    # "převodem" (napr. "Převodem 14 dní po dodání" neni
                    # platba predem). payment_method_id jako FK misto
                    # name-snapshotu by byl spolehlivejsi dlouhodobe reseni,
                    # ale to uz vyzaduje migraci (Robert ma 2 cekajici).
                    cur.execute(
                        "SELECT requires_advance_invoice FROM shop_payment_methods WHERE name=%s",
                        (order["payment_method_name"],),
                    )
                    pm = cur.fetchone()
                    if pm:
                        requires_advance = bool(pm["requires_advance_invoice"])
                    else:
                        name_lower = (order["payment_method_name"] or "").strip().lower()
                        requires_advance = ("zálohov" in name_lower) or ("předem" in name_lower)
                    if requires_advance and not order["payment_received_at"]:
                        conn.rollback()
                        return False, (
                            "Tato objednávka má platbu předem a ještě není evidovaná přijatá "
                            "platba - nejdřív označ platbu jako přijatou (doklad VDD)."
                        )

                # AND cut_kind IS NULL - viz stejna oprava a duvod u
                # _system_confirm_or_wait() nize (bot13, 2026-09-02).
                cur.execute(
                    "SELECT product_id, product_name_snapshot, unit_price_czk, qty "
                    "FROM shop_order_items WHERE order_id=%s AND cut_kind IS NULL",
                    (order_id,),
                )
                order_items = cur.fetchall()

                was_deducted = old_status in STOCK_DEDUCTED_STATUSES
                will_be_deducted = new_status in STOCK_DEDUCTED_STATUSES

                if not was_deducted and will_be_deducted:
                    for oi in order_items:
                        if oi["product_id"] is None:
                            continue
                        cur.execute(
                            "SELECT stock_qty FROM shop_products WHERE id=%s FOR UPDATE",
                            (oi["product_id"],),
                        )
                        prod = cur.fetchone()
                        if not prod:
                            continue
                        if prod["stock_qty"] < oi["qty"]:
                            conn.rollback()
                            return False, (
                                f"Nedostatek skladu pro „{oi['product_name_snapshot']}“ "
                                f"při potvrzení objednávky (skladem {prod['stock_qty']} ks)."
                            )
                        cur.execute(
                            "UPDATE shop_products SET stock_qty = stock_qty - %s WHERE id=%s",
                            (oi["qty"], oi["product_id"]),
                        )
                        cur.execute(
                            "INSERT INTO shop_stock_movements "
                            "(product_id, movement_type, qty, unit_price_czk, note, document_number, user_id) "
                            "VALUES (%s, 'issue', %s, %s, %s, %s, %s)",
                            (oi["product_id"], oi["qty"], oi["unit_price_czk"],
                             f"Objednávka {order_number}", order_number, admin["id"]),
                        )
                elif was_deducted and not will_be_deducted:
                    # zruseni jiz potvrzene/rozpracovane objednavky -> vratit zbozi na sklad
                    for oi in order_items:
                        if oi["product_id"] is None:
                            continue
                        cur.execute(
                            "UPDATE shop_products SET stock_qty = stock_qty + %s WHERE id=%s",
                            (oi["qty"], oi["product_id"]),
                        )
                        cur.execute(
                            "INSERT INTO shop_stock_movements "
                            "(product_id, movement_type, qty, unit_price_czk, note, document_number, user_id) "
                            "VALUES (%s, 'receipt', %s, %s, %s, %s, %s)",
                            (oi["product_id"], oi["qty"], oi["unit_price_czk"],
                             f"Zrušení objednávky {order_number} - vrácení skladu", order_number, admin["id"]),
                        )

                fields.append("status=%s")
                params.append(new_status)
                new_delivery, new_billing = _states_for_status(new_status)
                fields.append("delivery_state=%s")
                params.append(new_delivery)
                fields.append("billing_state=%s")
                params.append(new_billing)
                status_changed = True

                cur.execute(
                    "INSERT INTO shop_order_status_history (order_id, status, changed_by, note) "
                    "VALUES (%s, %s, %s, %s)",
                    (order_id, new_status, admin["id"], history_note),
                )

            if is_urgent is not None:
                fields.append("is_urgent=%s")
                params.append(1 if is_urgent else 0)

            if admin_note is not None:
                fields.append("admin_note=%s")
                params.append(admin_note)

            if not fields:
                conn.rollback()
                return False, "Nebyla zadána žádná změna."

            params.append(order_id)
            cur.execute(f"UPDATE shop_orders SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()

    if status_changed and customer_email:
        _send_status_change_email(order_id, order_number, customer_email, new_status, history_note)

    return True, None


# ---------------------------------------------------------------------------
# Automaticke preklapeni stavu (Robert 2026-07-31)
# ---------------------------------------------------------------------------
# Dohodnuta pravidla (postupne upresnovana v konverzaci):
#   1. "objednavka se potvrdi klientovi coz je stav potvrzena tim ze se mu
#      odesle potvrzovaci e-mail" -> nova -> potvrzena AZ pri skutecne
#      uspesnem odeslani potvrzovaciho e-mailu. Kdyz e-mail selze,
#      objednavka zustane "nova": "bude videt ze neni potvrzena".
#   2. "se zbozi objednat takze bude ve stavu ceka na zbozi" -> kdyz na
#      potvrzeni nestaci sklad, jde objednavka do "ceka_na_zbozi" (sklad se
#      NEodepisuje) misto aby prechod tvrde selhal.
#   3. "automaticky pri naskladneni" -> jakmile prijde zbozi na sklad,
#      cekajici objednavky, na ktere uz sklad staci, se samy potvrdi.
# Tyhle funkce zamerne NEPOUZIVAJI _apply_order_update() - ta je vazana na
# konkretniho admina (admin["id"]) a posila e-mail o zmene stavu. Systemova
# zmena zapisuje changed_by=NULL a stav "potvrzena" uz zakaznikovi ohlasil
# samotny potvrzovaci e-mail, takze se neposila druhy.

def _autocreate_supplier_orders(cur, order, missing_items):
    """Robert 2026-07-31: "muze se zalozit objednavka ale bude ve stavu
    nepotvrzena a bude cekat na admina k potvrzeni cimz se automaticky
    odesle dodavateli ktery se nastavi pro danou polozku produktu".

    Zaklada nakupni objednavky na CHYBEJICI mnozstvi, ve stavu 'navrh'
    (= nepotvrzena) - odeslani dodavateli se deje az rucnim potvrzenim
    adminem (viz purchase_orders.py, prechod navrh -> odeslano).

    Polozky se seskupuji podle dodavatele z produktu
    (shop_products.supplier_name - textove pole, parujeme podle jmena na
    kartu dodavatele kvuli e-mailu). Produkty bez dodavatele skonci v
    objednavce "Neznamy dodavatel" - Robert: "zalozit i tak, dodavatele
    doplni admin" (bez e-mailu ji stejne nejde odeslat).

    Bezi ve SDILENE transakci volajiciho - zadny vlastni commit.
    """
    if not missing_items:
        return []

    # 1) rozdelit chybejici kusy podle dodavatele produktu
    by_supplier = {}
    for mi in missing_items:
        cur.execute("SELECT supplier_name FROM shop_products WHERE id=%s", (mi["product_id"],))
        row = cur.fetchone()
        supplier_name = ((row or {}).get("supplier_name") or "").strip() or "Neznámý dodavatel"
        by_supplier.setdefault(supplier_name, []).append(mi)

    created = []
    for supplier_name, items in by_supplier.items():
        # 2) Robert 2026-08-06 ("porad vznikaji objednavky nakupni, psal
        # jsem že se to má opravit"): pred zalozenim NOVE NO nejdriv
        # zkusit dohledat uz existujici OTEVRENOU (status='navrh', tedy
        # jeste neodeslanou dodavateli) NO pro stejneho dodavatele -
        # chybejici polozky se do ni SLOUCI (existujici radek produktu se
        # navysi o qty_needed, jinak se prida novy radek), misto aby kazdy
        # dalsi checkout se stejnym nedostatkem zakladal dalsi a dalsi
        # samostatnou NO (presne to zpusobovalo hromadeni "Neznámý
        # dodavatel" NO v adminu pri opakovanem testovani).
        cur.execute(
            "SELECT id, po_number FROM shop_purchase_orders "
            "WHERE supplier_name=%s AND status='navrh' ORDER BY id DESC LIMIT 1",
            (supplier_name,),
        )
        existing_po = cur.fetchone()

        if existing_po:
            po_id = existing_po["id"]
            added_total = 0.0
            for mi in items:
                line_total = float(mi["unit_price_czk"] or 0) * mi["qty_needed"]
                added_total += line_total
                cur.execute(
                    "SELECT id FROM shop_purchase_order_items WHERE purchase_order_id=%s AND product_id=%s",
                    (po_id, mi["product_id"]),
                )
                existing_item = cur.fetchone()
                if existing_item:
                    cur.execute(
                        "UPDATE shop_purchase_order_items SET qty_ordered=qty_ordered+%s, "
                        "line_total_czk=line_total_czk+%s WHERE id=%s",
                        (mi["qty_needed"], line_total, existing_item["id"]),
                    )
                else:
                    cur.execute(
                        "INSERT INTO shop_purchase_order_items "
                        "(purchase_order_id, product_id, product_name_snapshot, unit_price_czk, qty_ordered, line_total_czk) "
                        "VALUES (%s,%s,%s,%s,%s,%s)",
                        (po_id, mi["product_id"], mi["product_name"], mi["unit_price_czk"] or 0,
                         mi["qty_needed"], line_total),
                    )
            cur.execute(
                # source_order_id se prepisuje na NEJNOVEJSI objednavku,
                # ktera do teto NO neco pridala - viz _delete_orders_cascade
                # (smazani NEJNOVEJSI navazane objednavky smaze i tuhle
                # jeste neodeslanou NO, starsi objednavky uz svuj kus
                # potreby "vyresily" tim, ze skoncil v teto NO).
                "UPDATE shop_purchase_orders SET total_czk=total_czk+%s, source_order_id=%s, "
                "note=CONCAT(COALESCE(note,''), %s) WHERE id=%s",
                (added_total, order["id"],
                 f" + chybějící zboží pro objednávku {order['order_number']}.", po_id),
            )
            cur.execute(
                "INSERT INTO shop_purchase_order_status_history (purchase_order_id, status, changed_by, note) "
                "VALUES (%s, 'navrh', NULL, %s)",
                (po_id, f"Doplněno o chybějící zboží pro objednávku {order['order_number']}."),
            )
            created.append(existing_po["po_number"])
            continue

        # 3) jinak (zadna otevrena NO pro tohohle dodavatele) zalozit
        # novou - puvodni chovani.
        cur.execute(
            "SELECT id, name, ico, dic, address, contact_name, email, phone "
            "FROM shop_suppliers WHERE name=%s AND active=1 LIMIT 1",
            (supplier_name,),
        )
        sup = cur.fetchone()

        total = sum(float(i["unit_price_czk"] or 0) * i["qty_needed"] for i in items)
        cur.execute(
            "INSERT INTO shop_purchase_orders "
            "(po_number, status, supplier_id, supplier_name, supplier_ico, supplier_dic, supplier_address, "
            " supplier_contact_name, supplier_email, supplier_phone, note, total_czk, created_by, source_order_id) "
            "VALUES ('', 'navrh', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s)",
            (sup["id"] if sup else None, supplier_name,
             sup["ico"] if sup else None, sup["dic"] if sup else None, sup["address"] if sup else None,
             sup["contact_name"] if sup else None, sup["email"] if sup else None, sup["phone"] if sup else None,
             f"Automaticky založeno – chybějící zboží pro objednávku {order['order_number']}.",
             total, order["id"]),
        )
        po_id = cur.lastrowid
        cur.execute("SELECT created_at FROM shop_purchase_orders WHERE id=%s", (po_id,))
        po_created_at = cur.fetchone()["created_at"]
        po_number = _generate_po_number(po_id, po_created_at)
        cur.execute("UPDATE shop_purchase_orders SET po_number=%s WHERE id=%s", (po_number, po_id))

        for mi in items:
            line_total = float(mi["unit_price_czk"] or 0) * mi["qty_needed"]
            cur.execute(
                "INSERT INTO shop_purchase_order_items "
                "(purchase_order_id, product_id, product_name_snapshot, unit_price_czk, qty_ordered, line_total_czk) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (po_id, mi["product_id"], mi["product_name"], mi["unit_price_czk"] or 0,
                 mi["qty_needed"], line_total),
            )

        cur.execute(
            "INSERT INTO shop_purchase_order_status_history (purchase_order_id, status, changed_by, note) "
            "VALUES (%s, 'navrh', NULL, %s)",
            (po_id, f"Automaticky založeno pro objednávku {order['order_number']} – čeká na potvrzení adminem."),
        )
        created.append(po_number)
    return created


def _generate_po_number(po_id, created_at):
    """Cislo nakupni objednavky - STEJNY tvar i zpusob jako
    purchase_orders._generate_po_number() (NO-RRRR-<id>), aby cisla z
    automatickeho i rucniho zakladani nesla dvema ruznymi radami.

    Oprava (bot3, revize kodu 2026-09-03): puvodne VZDY `datetime.utcnow().
    year` bez ohledu na skutecny `created_at` noveho radku - na rozdil od
    dvojcete v purchase_orders.py, ktere prednostne bere realny
    `created_at.year` z DB a na utcnow() sahne jen jako fallback (created_at
    None). Sjednoceno na stejny zpusob - `created_at` se ted cte cerstvym
    SELECTem hned po INSERTu (stejny vzor jako volajici u rucniho zalozeni
    v purchase_orders.py), utcnow() zustava jen jako fallback."""
    import datetime as _dt
    year = created_at.year if created_at else _dt.datetime.utcnow().year
    return f"NO-{year}-{po_id:05d}"


def _system_confirm_or_wait(cur, order):
    """V OTEVRENE transakci: zkusi objednavku potvrdit (odecist sklad).
    Kdyz sklad nestaci, prepne ji do "ceka_na_zbozi" a sklad nechá být.
    Vraci vysledny stav ("potvrzena" | "ceka_na_zbozi") nebo None, kdyz
    se nemenilo nic, nebo "unlinked_items", kdyz objednavka nema JEDINOU
    polozku s product_id (nelze overit sklad vubec, viz nize). Volajici
    zajistuje commit.

    POZOR na poradi (bezpecnostni nalez, bot3/revize kodu 2026-09-02):
    _autocreate_supplier_orders()/odecet skladu SMI bezet AZ PO overeni
    ALLOWED_TRANSITIONS, ne pred nim. Puvodne se vedlejsi ucinek spoustel
    VZDY - i pri self-transition ceka_na_zbozi->ceka_na_zbozi (neni
    povoleny prechod, viz ALLOWED_TRANSITIONS nahore v souboru), takze
    kazda DALSI prijemka cehokoli (viz try_release_waiting_orders, bezi
    pres VSECHNY cekajici objednavky) znovu a znovu navysovala
    qty_ordered/total_czk uz zalozene navazane NO pro objednavku, ktera
    porad ceka na totez zbozi. Ted se nejdriv spocita VYSLEDEK (cisty
    READ pres FOR UPDATE zamky, zadny zapis) a teprve kdyz jde o
    SKUTECNY POVOLENY prechod (prvni prijezd do ceka_na_zbozi/potvrzena,
    ne opakovani stejneho stavu), az POTOM se provede auto-NO/odecet
    skladu."""
    order_id = order["id"]
    order_number = order["order_number"]

    # AND cut_kind IS NULL (bot13, 2026-09-02, oprava nalezu z revize kodu) -
    # stinove radky "Rezneho planu" (cut_kind='profil'/'deska', viz
    # _cutting_plan_shadow_items vyse) sdili product_id se svym rodicovskym
    # radkem, ale maji VLASTNI qty (pocet rezanych kusu, jine cislo nez
    # pocet nakoupenych tyci/desek) - bez tohohle filtru by se sklad
    # odectl dvakrat (rodicovsky radek + kazdy stinovy radek zvlast).
    cur.execute(
        "SELECT product_id, product_name_snapshot, unit_price_czk, qty "
        "FROM shop_order_items WHERE order_id=%s AND cut_kind IS NULL",
        (order_id,),
    )
    items = cur.fetchall()

    # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02, zive overeno - 7 z
    # 8 objednavek ceka_na_zbozi): objednavka bez JEDINE polozky s
    # product_id (typicky stary CSV import, nikdy neparovany na katalog)
    # projde smyckou nize bez jedineho radku k overeni - "missing"
    # zustane prazdne, tise auto-potvrzena, i kdyz sklad realne NEBYL
    # overen vubec. Bez moznosti overit sklad se radsi neautomatizuje -
    # zustava ve stavu, admin rozhodne rucne (viz volajici, kteri tenhle
    # navrat zaznamenavaji zvlast pro viditelnost v adminu).
    if not any(oi["product_id"] is not None for oi in items):
        return "unlinked_items"

    missing = []
    missing_items = []
    for oi in items:
        if oi["product_id"] is None:
            continue
        cur.execute("SELECT stock_qty FROM shop_products WHERE id=%s FOR UPDATE", (oi["product_id"],))
        prod = cur.fetchone()
        if not prod:
            continue
        if prod["stock_qty"] < oi["qty"]:
            missing.append(f"{oi['product_name_snapshot']} (skladem {prod['stock_qty']}, potřeba {oi['qty']})")
            missing_items.append({
                "product_id": oi["product_id"],
                "product_name": oi["product_name_snapshot"],
                "unit_price_czk": oi["unit_price_czk"],
                "qty_needed": oi["qty"] - prod["stock_qty"],
            })

    new_status = "ceka_na_zbozi" if missing else "potvrzena"
    if new_status not in ALLOWED_TRANSITIONS.get(order["status"], set()):
        return None

    if missing:
        note = "Automaticky: nedostatek skladu – " + "; ".join(missing[:5])
        _autocreate_supplier_orders(cur, order, missing_items)
    else:
        note = "Automaticky potvrzeno (potvrzovací e-mail odeslán zákazníkovi)."
        for oi in items:
            if oi["product_id"] is None:
                continue
            cur.execute("UPDATE shop_products SET stock_qty = stock_qty - %s WHERE id=%s",
                        (oi["qty"], oi["product_id"]))
            cur.execute(
                "INSERT INTO shop_stock_movements "
                "(product_id, movement_type, qty, unit_price_czk, note, document_number, user_id) "
                "VALUES (%s, 'issue', %s, %s, %s, %s, NULL)",
                (oi["product_id"], oi["qty"], oi["unit_price_czk"],
                 f"Objednávka {order_number}", order_number),
            )

    new_delivery, new_billing = _states_for_status(new_status)
    cur.execute(
        "UPDATE shop_orders SET status=%s, delivery_state=%s, billing_state=%s WHERE id=%s",
        (new_status, new_delivery, new_billing, order_id),
    )
    cur.execute(
        "INSERT INTO shop_order_status_history (order_id, status, changed_by, note) VALUES (%s,%s,NULL,%s)",
        (order_id, new_status, note),
    )
    return new_status


def auto_confirm_after_confirmation_email(order_id):
    """Pravidlo 1+2: volano z _send_order_emails() POUZE kdyz potvrzovaci
    e-mail skutecne odesel. Nikdy nesmi shodit request, ktery objednavku
    zakladal - proto cely obal try/except."""
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM shop_orders WHERE id=%s FOR UPDATE", (order_id,))
                order = cur.fetchone()
                if not order or order["status"] != "nova":
                    conn.rollback()
                    return None
                new_status = _system_confirm_or_wait(cur, order)
            conn.commit()
            return new_status
        finally:
            conn.close()
    except Exception:
        return None


def try_release_waiting_orders():
    """Pravidlo 3: po naskladneni projde objednavky ve stavu
    "ceka_na_zbozi" (nejstarsi prvni - kdo cekal dele, dostane zbozi
    driv) a ty, na ktere uz sklad staci, potvrdi. Volano z mist, kde
    zbozi prichazi na sklad (rucni prijemka i prijem nakupni objednavky).
    Vraci (seznam cisel potvrzenych objednavek, seznam cisel objednavek
    bez napojenych polozek - ty NEJDOU auto-uvolnit vubec, viz
    _system_confirm_or_wait "unlinked_items", zustavaji ceka_na_zbozi a
    ceka se na rucni rozhodnuti admina)."""
    released = []
    needs_review = []
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM shop_orders WHERE status='ceka_na_zbozi' ORDER BY created_at, id"
                )
                waiting_ids = [r["id"] for r in cur.fetchall()]
                for oid in waiting_ids:
                    cur.execute("SELECT * FROM shop_orders WHERE id=%s FOR UPDATE", (oid,))
                    order = cur.fetchone()
                    if not order or order["status"] != "ceka_na_zbozi":
                        continue
                    result = _system_confirm_or_wait(cur, order)
                    if result == "potvrzena":
                        released.append(order["order_number"])
                    elif result == "unlinked_items":
                        needs_review.append(order["order_number"])
                        app.logger.info(
                            "try_release_waiting_orders: objednávka %s bez napojených položek, "
                            "přeskočeno (nejde ověřit sklad, čeká na ruční rozhodnutí)",
                            order["order_number"],
                        )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        return released, needs_review
    return released, needs_review


@app.put("/api/admin/orders/<int:order_id>")
@require_permission("objednavky", "upravit")
def admin_orders_update(order_id):
    """
    Zmena objednavky - status prechod (podle ALLOWED_TRANSITIONS),
    is_urgent priznak a/nebo admin_note. Kazde pole je volitelne (posila
    se jen to, co se ma zmenit).

    Zmena stavu do/ze "STOCK_DEDUCTED_STATUSES" automaticky odecte, resp.
    vrati sklad (shop_products.stock_qty) a zapise auditni radek do
    shop_stock_movements - stejnym zpusobem jako rucni prijem/vydej v
    /api/shop/stock/movements, jen s document_number = cislo objednavky.
    Zakaznikovi se pri zmene stavu posle e-mail (pokud je SMTP nastaveno).

    Body: {"status": "potvrzena", "is_urgent": true, "admin_note": "...",
           "history_note": "..." (volitelny text ulozeny k zaznamu v historii)}

    V11 (bot3, 2026-07-26) - tenky wrapper nad _apply_order_update(), sdilene
    jadro s POST .../bulk-status a .../bulk-urgent (viz NAVRH_HROMADNE_AKCE.md).
    """
    body = request.get_json(silent=True) or {}
    new_status = body.get("status")
    # bool() prevod (bezpecnostni nalez, bot3/revize kodu 2026-09-02,
    # stejny vzor jako admin_orders_bulk_urgent nize) - "is_urgent" not
    # in body / None znamena "nemenit" (viz _apply_order_update "is not
    # None" kontrola), takze None se NEPREVADI, jen skutecna hodnota.
    is_urgent = body.get("is_urgent")
    if is_urgent is not None:
        is_urgent = bool(is_urgent)
    admin_note = body.get("admin_note")
    history_note = (body.get("history_note") or "").strip() or None
    admin = current_user()

    ok, err = _apply_order_update(
        order_id, admin, new_status=new_status, is_urgent=is_urgent,
        admin_note=admin_note, history_note=history_note,
    )
    if not ok:
        code = 404 if err == "Objednávka neexistuje." else 400
        return jsonify({"error": err}), code
    return jsonify({"status": "ok"})


@app.post("/api/admin/orders/bulk-status")
@require_permission("objednavky", "upravit")
def admin_orders_bulk_status():
    """
    Hromadna zmena stavu vybranych objednavek (V11, bot3, 2026-07-26, viz
    NAVRH_HROMADNE_AKCE.md). Vola _apply_order_update() v cyklu pro kazde
    id - NE holy UPDATE - kvuli skladovym vedlejsim ucinkum a e-mailum.
    Selhani jedne objednavky (napr. nepovoleny prechod) se zaznamena do
    "failed" a nezastavi zbytek davky.

    Body: {"ids": [1,2,3], "status": "potvrzena", "history_note": "..."}
    Odpoved: {"status": "ok", "updated": N, "failed": [{"id": X, "error": "..."}]}
    """
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    new_status = body.get("status")
    if not new_status or new_status not in ORDER_STATUSES:
        return jsonify({"error": "Neplatný status."}), 400
    history_note = (body.get("history_note") or "").strip() or None
    admin = current_user()

    updated, failed = 0, []
    for order_id in ids:
        try:
            ok, error = _apply_order_update(order_id, admin, new_status=new_status, history_note=history_note)
        except Exception as e:
            failed.append({"id": order_id, "error": str(e)})
            continue
        if ok:
            updated += 1
        else:
            failed.append({"id": order_id, "error": error})

    log_audit(
        admin["id"], "bulk_status", "order", None,
        f"{updated} objednávek → {STATUS_LABELS_CZ.get(new_status, new_status)}"
        + (f" ({len(failed)} selhalo)" if failed else ""),
    )
    return jsonify({"status": "ok", "updated": updated, "failed": failed})


@app.post("/api/admin/orders/bulk-urgent")
@require_permission("objednavky", "upravit")
def admin_orders_bulk_urgent():
    """
    Hromadne nastaveni/zruseni priznaku "urgentni" u vybranych objednavek
    (V11, bot3, 2026-07-26, viz NAVRH_HROMADNE_AKCE.md).

    Body: {"ids": [1,2,3], "is_urgent": true}
    Odpoved: {"status": "ok", "updated": N, "failed": [{"id": X, "error": "..."}]}
    """
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    if "is_urgent" not in body:
        return jsonify({"error": "Chybí pole is_urgent."}), 400
    is_urgent = bool(body.get("is_urgent"))
    admin = current_user()

    updated, failed = 0, []
    for order_id in ids:
        try:
            ok, error = _apply_order_update(order_id, admin, is_urgent=is_urgent)
        except Exception as e:
            failed.append({"id": order_id, "error": str(e)})
            continue
        if ok:
            updated += 1
        else:
            failed.append({"id": order_id, "error": error})

    log_audit(
        admin["id"], "bulk_urgent", "order", None,
        f"{updated} objednávek → urgentní={'ano' if is_urgent else 'ne'}"
        + (f" ({len(failed)} selhalo)" if failed else ""),
    )
    return jsonify({"status": "ok", "updated": updated, "failed": failed})


# ---------------------------------------------------------------------------
# Mazani objednavek (Robert 2026-07-27: "proc nemaji objednavky bulk
# smazat?" - u zakazniku uz existuje "Smazat vse" + hromadny vyber +
# jednotlive mazani (viz customers.py), u objednavek tahle funkce
# chybela). Stejny vzor jako u zakazniku: delete_one (bez confirm_count,
# potvrzeni resi frontend confirm() dialogem), bulk (vybrana podmnozina
# pres {"ids":[...]}) a delete_all (confirm_count pojistka proti
# nechtenemu/naskriptovanemu smazani VSECH objednavek najednou).
#
# Na rozdil od zakazniku (kde DELETE z app_users kaskadove smaze
# shop_customers/shop_cart_items a objednavky si jen ztrati vazbu na
# ucet - ON DELETE SET NULL) tady mazeme PRIMO shop_orders. FK kontrola
# (viz information_schema.REFERENTIAL_CONSTRAINTS na live DB, 2026-07-27):
#   shop_order_items.order_id          -> ON DELETE CASCADE (smaze se samo)
#   shop_order_status_history.order_id -> ON DELETE CASCADE (smaze se samo)
#   shop_documents.order_id            -> NO ACTION, NOT NULL (musime smazat rucne)
#   shop_emails.order_id               -> NO ACTION, NOT NULL (musime smazat rucne)
# Proto se pred DELETE FROM shop_orders vzdy nejdriv smazou navazane
# shop_documents a shop_emails radky pro dane order_id - jinak by DELETE
# spadl na FK constraint chybu (1451).
# ---------------------------------------------------------------------------

def _delete_orders_cascade(cur, order_ids):
    """Smaze shop_documents + shop_emails navazane na dane objednavky (NO
    ACTION FK, jinak by DELETE FROM shop_orders selhal), pak samotne
    objednavky (shop_order_items/shop_order_status_history si smaze DB
    sama pres ON DELETE CASCADE).

    Robert 2026-08-06 ("porad vznikaji objednavky nakupni, psal jsem že
    se to má opravit" + obecny princip z 2026-08-02 pri mazani dodavatele:
    "smaže-li se jakýkolikoli doklad, prvek, tzn i nák.obj, musí se smazat
    i každý návazný doklad pohyb cokoli co navazuje v DB") - PRED smazanim
    samotnych objednavek se nejdriv smazou nakupni objednavky, ktere na ne
    navazuji (shop_purchase_orders.source_order_id, viz
    _autocreate_supplier_orders vyse) - jinak zustavaly osirele s
    poznamkou odkazujici na uz neexistujici cislo objednavky. Pouziva se
    stejna bezpecna _delete_one_purchase_order() jako pri rucnim mazani NO
    v adminu (vraceni skladu u uz prijatych NO, smazani navazanych emailu).

    Vraci (pocet smazanych objednavek, seznam smazanych
    shop_purchase_order_items.id pro nasledny uklid galerie u volajiciho,
    seznam ID PRESKOCENYCH objednavek - nejsou testovaci, viz nize).

    bot5, 2026-09-26 (Robert: "nesmí vzniknout díra v číslování žádné
    číselné řady" + "jen testovací objednávky budeme mazat... normální
    objednávky se mazat nebudou"): tvrde smazani je ted dovoleno JEN u
    testovacich objednavek (_is_test_order - is_test=1 NEBO Robertuv
    e-mail), zbytek se PRESKOCI (volajici endpoint at admina posle na
    zruseni stavem). U skutecne smazanych testovacich objednavek se
    JEJICH order_number vrati do fondu (_release_order_number) - jinak
    by test objednavky vytvarely stejne diry jako incident #191."""
    if not order_ids:
        return 0, [], []
    placeholders = ",".join(["%s"] * len(order_ids))

    cur.execute(
        f"SELECT id, order_number, customer_email, is_test FROM shop_orders WHERE id IN ({placeholders})",
        order_ids,
    )
    rows_by_id = {r["id"]: r for r in cur.fetchall()}
    order_ids = [i for i in order_ids if i in rows_by_id and _is_test_order(rows_by_id[i])]
    blocked_ids = [i for i in rows_by_id if i not in set(order_ids)]
    if not order_ids:
        return 0, [], blocked_ids
    placeholders = ",".join(["%s"] * len(order_ids))
    for i in order_ids:
        _release_order_number(cur, rows_by_id[i]["order_number"])

    cur.execute(f"SELECT id FROM shop_purchase_orders WHERE source_order_id IN ({placeholders})", order_ids)
    po_item_ids = []
    for row in cur.fetchall():
        result = purchase_orders._delete_one_purchase_order(cur, row["id"])
        if result:
            po_item_ids.extend(result["item_ids"])

    # Robert 2026-08-07 ("už jsme mazali staré kostlivce několikrát a
    # pořád lezou ven"): skladove pohyby (vydej pri potvrzeni objednavky,
    # viz _system_confirm_or_wait) nemaji FK na objednavku - jen volny
    # text document_number = order_number - takze DELETE FROM shop_orders
    # je bez tohohle kroku nikdy nesmaze, zustavaly navzdy jako osirely
    # radek se jmenem uz neexistujici objednavky. Cislo objednavky je
    # potreba precist PRED smazanim shop_orders nize.
    #
    # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): puvodne primy
    # DELETE FROM shop_stock_movements - smazal RADEK pohybu, ale
    # NEVRATIL jeho ucinek na shop_products.stock_qty (na rozdil od
    # NO cesty, ktera uz spravne pouziva reverse_and_delete_stock_movements
    # - viz _delete_one_purchase_order vyse). Smazani potvrzene/pripravovane
    # objednavky tak ticha snizovalo sklad natrvalo bez stopy. Sjednoceno
    # na stejny sdileny helper - reversal, co by poslal stock_qty do
    # zaporu, se NEPROVEDE (movement zustane v DB nesmazany), zbytek
    # objednavky se smaze normalne.
    cur.execute(f"SELECT order_number FROM shop_orders WHERE id IN ({placeholders})", order_ids)
    order_numbers = [row["order_number"] for row in cur.fetchall() if row["order_number"]]
    if order_numbers:
        onum_placeholders = ",".join(["%s"] * len(order_numbers))
        cur.execute(
            f"SELECT id FROM shop_stock_movements WHERE document_number IN ({onum_placeholders})",
            order_numbers,
        )
        movement_ids = [row["id"] for row in cur.fetchall()]
        if movement_ids:
            _deleted_mv_ids, failed_mv = reverse_and_delete_stock_movements(cur, movement_ids)
            if failed_mv:
                app.logger.warning(
                    "_delete_orders_cascade: %d skladových pohybů nešlo vrátit (šlo by do záporu), "
                    "ponechány v DB: %s", len(failed_mv), failed_mv,
                )

    cur.execute(f"DELETE FROM shop_documents WHERE order_id IN ({placeholders})", order_ids)
    cur.execute(f"DELETE FROM shop_emails WHERE order_id IN ({placeholders})", order_ids)
    cur.execute(f"DELETE FROM shop_orders WHERE id IN ({placeholders})", order_ids)
    return cur.rowcount, po_item_ids, blocked_ids


@app.delete("/api/admin/orders/<int:order_id>")
@require_permission("objednavky", "smazat")
def admin_orders_delete_one(order_id):
    """Smazani JEDNE objednavky. Potvrzeni resi frontend pres confirm()
    dialog (stejne jako admin_customers_delete_one) - jednotlivy zaznam
    neni tak rizikovy jako hromadne smazani vseho."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT order_number, customer_email, is_test FROM shop_orders WHERE id=%s", (order_id,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return jsonify({"error": "Objednávka neexistuje."}), 404
            if not _is_test_order(row):
                conn.rollback()
                return jsonify({
                    "error": "Tuto objednávku nelze smazat (má vydané číslo) - zrušte ji stavem "
                             "\"Zrušená\" (viz Upravit stav)."
                }), 400
            _, po_item_ids, _blocked = _delete_orders_cascade(cur, [order_id])
        conn.commit()
    finally:
        conn.close()
    if po_item_ids:
        import gallery_items
        for iid in po_item_ids:
            gallery_items.delete_items_for_owner("po_item", iid)
    log_audit(admin["id"], "delete", "order", order_id,
              f"Smazána objednávka {row['order_number']}.")
    return jsonify({"status": "ok"})


@app.delete("/api/admin/orders")
@require_permission("objednavky", "smazat")
def admin_orders_delete_all():
    """Hromadne smazani VSECH objednavek najednou (Robert 2026-07-27,
    stejny vzor jako admin_customers_delete_all). NEVRATNA akce - proto
    vyzaduje "confirm_count" presne odpovidajici AKTUALNIMU poctu
    objednavek (ochrana proti nechtenemu/naskriptovanemu volani a proti
    race podmince).

    Ocekavany JSON payload: {"confirm_count": <aktualni pocet objednavek>}
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_orders")
            order_ids = [r["id"] for r in cur.fetchall()]
            actual_count = len(order_ids)

            try:
                confirm_count = int(body.get("confirm_count"))
            except (TypeError, ValueError):
                conn.rollback()
                return jsonify({"error": "Chybí potvrzení počtu.", "current_count": actual_count}), 400

            if confirm_count != actual_count:
                conn.rollback()
                return jsonify({
                    "error": f"Potvrzený počet ({confirm_count}) neodpovídá aktuálnímu počtu "
                             f"objednávek ({actual_count}). Zkuste to prosím znovu.",
                    "current_count": actual_count,
                }), 409

            if actual_count == 0:
                conn.rollback()
                return jsonify({"status": "ok", "deleted": 0})

            deleted, po_item_ids, blocked_ids = _delete_orders_cascade(cur, order_ids)
        conn.commit()
    finally:
        conn.close()
    if po_item_ids:
        import gallery_items
        for iid in po_item_ids:
            gallery_items.delete_items_for_owner("po_item", iid)

    # bot5, 2026-09-26: "Smazat vsechny" uz nesmi tvrde smazat normalni
    # objednavky (viz _is_test_order/_delete_orders_cascade) - preskocene
    # se hlasi zvlast, at admin vi, ze zbytek musi zrusit stavem, ne ze se
    # "nestalo nic".
    note = f"Hromadně smazáno {deleted} testovacích objednávek."
    if blocked_ids:
        note += f" {len(blocked_ids)} přeskočeno (nejsou testovací, zrušte stavem)."
    log_audit(admin["id"], "delete_all", "order", None, note)
    return jsonify({"status": "ok", "deleted": deleted, "blocked": len(blocked_ids)})


@app.delete("/api/admin/orders/bulk")
@require_permission("objednavky", "smazat")
def admin_orders_bulk_delete():
    """Smazani VYBRANE podmnoziny objednavek (stejny vzor jako
    admin_customers_bulk_delete). Body: {"ids": [1,2,3]}."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id FROM shop_orders WHERE id IN ({placeholders})", ids)
            found_ids = [r["id"] for r in cur.fetchall()]
            deleted, po_item_ids, blocked_ids = _delete_orders_cascade(cur, found_ids)
        conn.commit()
    finally:
        conn.close()
    if po_item_ids:
        import gallery_items
        for iid in po_item_ids:
            gallery_items.delete_items_for_owner("po_item", iid)
    found_set = set(found_ids)
    missing = [i for i in ids if i not in found_set]
    log_audit(admin["id"], "bulk_delete", "order", None,
              f"{deleted} objednávek smazáno" + (f", {len(missing)} nenalezeno" if missing else "")
              + (f", {len(blocked_ids)} přeskočeno (nejsou testovací)" if blocked_ids else ""))
    # bot5, 2026-09-26: blocked_ids (normalni objednavky, ne test) se
    # hlasi ve "failed" jako ostatni neuspechy - frontend uz umi partial-
    # failure report zobrazit (viz driveBulkDeleteWithReport vzor).
    failed = [{"id": i, "error": "Objednávka neexistuje."} for i in missing]
    failed += [{"id": i, "error": "Nejde smazat (má vydané číslo) - zrušte stavem \"Zrušená\"."} for i in blocked_ids]
    return jsonify({"status": "ok", "deleted": deleted, "failed": failed})



# ---------------------------------------------------------------------------
# Doprava a platba - verejne (jen aktivni, pro checkout formular) + admin CRUD
# (bot3, 2026-07-25 v2). Zadna platebni brana - jen vyber + cena/poplatek.
# ---------------------------------------------------------------------------

def _serialize_method(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "price_czk": _money(row["price_czk"]),
        "active": bool(row["active"]),
        "sort_order": row["sort_order"],
        # V8 (bot3, 2026-07-25) - jen shop_shipping_methods ma tyhle sloupce
        # (shop_payment_methods ne) - .get() aby serializer fungoval pro obe.
        "pricing_mode": row.get("pricing_mode", "fixed"),
        "is_default": bool(row.get("is_default", 0)),
    }


@app.get("/api/shipping-methods")
def shipping_methods_public():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM shop_shipping_methods WHERE active=1 ORDER BY sort_order, name"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"methods": [_serialize_method(r) for r in rows]})


@app.get("/api/payment-methods")
def payment_methods_public():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM shop_payment_methods WHERE active=1 ORDER BY sort_order, name"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"methods": [_serialize_method(r) for r in rows]})


def _method_admin_crud(table, entity_type):
    """Tovarna na 4 admin CRUD endpointy - shipping i payment metody maji
    naprosto stejny tvar (id, name, price_czk, active, sort_order), stejny
    vzor jako /api/admin/accessories v app.py."""

    def list_all():
        # Robert 2026-08-01: "chceme ukazovat veškeré možné archivní věci
        # položky" - stejny vzor jako shop_suppliers (purchase_orders.py).
        show_archived = request.args.get("archived") == "1"
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM {table} WHERE active=%s ORDER BY sort_order, name",
                    (0 if show_archived else 1,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        return jsonify({"methods": [_serialize_method(r) for r in rows]})

    def create():
        admin = current_user()
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Chybí název."}), 400
        price = float(body.get("price_czk") or 0)
        sort_order = int(body.get("sort_order") or 0)
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {table} (name, price_czk, active, sort_order) VALUES (%s,%s,1,%s)",
                    (name, price, sort_order),
                )
                new_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        log_audit(admin["id"], "create", entity_type, new_id, name)
        return jsonify({"status": "ok", "id": new_id})

    def update(item_id):
        admin = current_user()
        body = request.get_json(silent=True) or {}
        fields, params = [], []
        if "name" in body:
            fields.append("name=%s"); params.append((body.get("name") or "").strip())
        if "price_czk" in body:
            fields.append("price_czk=%s"); params.append(float(body.get("price_czk") or 0))
        if "active" in body:
            fields.append("active=%s"); params.append(1 if body.get("active") else 0)
        if "sort_order" in body:
            fields.append("sort_order=%s"); params.append(int(body.get("sort_order") or 0))
        if not fields:
            return jsonify({"error": "Nic ke změně."}), 400
        params.append(item_id)
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE {table} SET {', '.join(fields)} WHERE id=%s", params)
            conn.commit()
        finally:
            conn.close()
        log_audit(admin["id"], "update", entity_type, item_id, None)
        return jsonify({"status": "ok"})

    def delete(item_id):
        admin = current_user()
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {table} WHERE id=%s", (item_id,))
            conn.commit()
        finally:
            conn.close()
        log_audit(admin["id"], "delete", entity_type, item_id, None)
        return jsonify({"status": "ok"})

    return list_all, create, update, delete


_shipping_list, _shipping_create, _shipping_update, _shipping_delete = _method_admin_crud(
    "shop_shipping_methods", "shipping_method"
)
_payment_list, _payment_create, _payment_update, _payment_delete = _method_admin_crud(
    "shop_payment_methods", "payment_method"
)

# Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): sdileny _shipping_delete
# (z _method_admin_crud tovarny, generovan spolecne pro shipping i payment
# metody) nemel VUBEC zadnou kontrolu, na rozdil od admin_shipping_methods_
# bulk_delete nize (is_default + navazany cenik). shop_shipping_price_rules.
# shipping_method_id je ON DELETE CASCADE - jedno kliknuti na jednotlive
# smazani tak umelo smazat cely cenik Toptrans bez varovani. Dedikovana
# funkce jen pro shipping (payment metody zadny "cenik" koncept nemaji,
# _payment_delete zustava beze zmeny - stejne jako jejich bulk-delete).
def admin_shipping_methods_delete_one(item_id):
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT is_default FROM shop_shipping_methods WHERE id=%s", (item_id,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return jsonify({"error": "Způsob dopravy neexistuje."}), 404
            if row["is_default"]:
                conn.rollback()
                return jsonify({"error": "Nelze smazat výchozí způsob dopravy - nejprve nastav jiný jako výchozí."}), 409
            cur.execute("SELECT COUNT(*) AS c FROM shop_shipping_price_rules WHERE shipping_method_id=%s", (item_id,))
            if cur.fetchone()["c"] > 0:
                conn.rollback()
                return jsonify({"error": "Má nastavený ceník (PSČ/hmotnost) - smaž nejprve ceník, pak metodu."}), 409
            cur.execute("DELETE FROM shop_shipping_methods WHERE id=%s", (item_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "delete", "shipping_method", item_id, None)
    return jsonify({"status": "ok"})


app.get("/api/admin/shipping-methods", endpoint="admin_shipping_methods_list")(require_permission("doprava_platba", "zobrazit")(_shipping_list))
app.post("/api/admin/shipping-methods", endpoint="admin_shipping_methods_create")(require_permission("doprava_platba", "vytvorit")(_shipping_create))
app.put("/api/admin/shipping-methods/<int:item_id>", endpoint="admin_shipping_methods_update")(require_permission("doprava_platba", "upravit")(_shipping_update))
app.delete("/api/admin/shipping-methods/<int:item_id>", endpoint="admin_shipping_methods_delete")(require_permission("doprava_platba", "smazat")(admin_shipping_methods_delete_one))

app.get("/api/admin/payment-methods", endpoint="admin_payment_methods_list")(require_permission("doprava_platba", "zobrazit")(_payment_list))
app.post("/api/admin/payment-methods", endpoint="admin_payment_methods_create")(require_permission("doprava_platba", "vytvorit")(_payment_create))
app.put("/api/admin/payment-methods/<int:item_id>", endpoint="admin_payment_methods_update")(require_permission("doprava_platba", "upravit")(_payment_update))
app.delete("/api/admin/payment-methods/<int:item_id>", endpoint="admin_payment_methods_delete")(require_permission("doprava_platba", "smazat")(_payment_delete))


# ---------------------------------------------------------------------------
# Hromadne akce nad zpusoby dopravy/platby (Robert: "mazat musí být
# všude !!!").
#
# FK bezpecnost (overeno v sql/2026-07-25_orders_v2_customers_cart_shipping.sql):
# shop_orders NEMA sloupec shipping_method_id/payment_method_id - ulozena
# objednavka drzi jen SNAPSHOT (shipping_method_name/price_czk,
# payment_method_name/price_czk), takze smazani metody NIKDY nerozbije
# existujici objednavky. Jedina realna FK je
# shop_shipping_price_rules.shipping_method_id -> shop_shipping_methods(id)
# ON DELETE CASCADE (sql/2026-07-25_toptrans_duplicates.sql) - smazani
# metody s napojenym cenikem by ho potichu smazalo taky, proto se to niz
# explicitne kontroluje a odmita. Vychozi (is_default=1) zpusob dopravy
# je take chranen pred bulk-delete/deaktivaci - shop_payment_methods
# zadny "is_default" sloupec nema, takze tam zadna analogicka pojistka
# neni potreba.
# ---------------------------------------------------------------------------

@app.post("/api/admin/shipping-methods/bulk-delete")
@require_permission("doprava_platba", "smazat")
def admin_shipping_methods_bulk_delete():
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    deleted = 0
    failed = []
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(
                f"SELECT id, is_default FROM shop_shipping_methods WHERE id IN ({placeholders})", ids,
            )
            found = {r["id"]: r for r in cur.fetchall()}
            for mid in ids:
                if mid not in found:
                    failed.append({"id": mid, "error": "Způsob dopravy neexistuje."})
                    continue
                if found[mid]["is_default"]:
                    failed.append({"id": mid, "error": "Nelze smazat výchozí způsob dopravy - nejprve nastav jiný jako výchozí."})
                    continue
                cur.execute(
                    "SELECT COUNT(*) AS c FROM shop_shipping_price_rules WHERE shipping_method_id=%s", (mid,),
                )
                if cur.fetchone()["c"] > 0:
                    failed.append({"id": mid, "error": "Má nastavený ceník (PSČ/hmotnost) - smaž nejprve ceník, pak metodu."})
                    continue
                cur.execute("DELETE FROM shop_shipping_methods WHERE id=%s", (mid,))
                deleted += 1
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "bulk_delete", "shipping_method", None,
              f"{deleted} způsobů dopravy smazáno" + (f", {len(failed)} přeskočeno" if failed else ""))
    return jsonify({"status": "ok", "deleted": deleted, "failed": failed})


@app.post("/api/admin/shipping-methods/bulk-active")
@require_permission("doprava_platba", "upravit")
def admin_shipping_methods_bulk_active():
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    if "active" not in body:
        return jsonify({"error": "Chybí pole active."}), 400
    active = 1 if body.get("active") else 0
    conn = get_conn()
    failed = []
    updated = 0
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(
                f"SELECT id, is_default FROM shop_shipping_methods WHERE id IN ({placeholders})", ids,
            )
            found = {r["id"]: r for r in cur.fetchall()}
            failed = [{"id": i, "error": "Způsob dopravy neexistuje."} for i in ids if i not in found]
            protected_ids = set()
            if not active:
                protected_ids = {i for i in ids if i in found and found[i]["is_default"]}
                for pid in protected_ids:
                    failed.append({"id": pid, "error": "Nelze deaktivovat výchozí způsob dopravy - nejprve nastav jiný jako výchozí."})
            update_ids = [i for i in ids if i in found and i not in protected_ids]
            if update_ids:
                updated = bulk_update_fields(cur, "shop_shipping_methods", update_ids, {"active": active})
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "bulk_active", "shipping_method", None,
              f"{updated} způsobů dopravy -> active={active}" + (f", {len(failed)} přeskočeno" if failed else ""))
    return jsonify({"status": "ok", "updated": updated, "failed": failed})


@app.post("/api/admin/payment-methods/bulk-delete")
@require_permission("doprava_platba", "smazat")
def admin_payment_methods_bulk_delete():
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            deleted = bulk_delete(cur, "shop_payment_methods", ids)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "bulk_delete", "payment_method", None, f"{deleted} způsobů platby smazáno")
    return jsonify({"status": "ok", "deleted": deleted})


@app.post("/api/admin/payment-methods/bulk-active")
@require_permission("doprava_platba", "upravit")
def admin_payment_methods_bulk_active():
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    if "active" not in body:
        return jsonify({"error": "Chybí pole active."}), 400
    active = 1 if body.get("active") else 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            updated = bulk_update_fields(cur, "shop_payment_methods", ids, {"active": active})
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "bulk_active", "payment_method", None, f"{updated} způsobů platby -> active={active}")
    return jsonify({"status": "ok", "updated": updated})


# ---------------------------------------------------------------------------
# V8 (bot3, 2026-07-25): admin CRUD nad cenikem Toptrans (PSC + hmotnost).
# Robert dodal pokyn "cenik si najdi na toptrans.cz" - realny cenik je uz
# nasazen migraci, ale PSC->vzdalenost je jen ODHAD (viz orders.py::_resolve_toptrans_price
# a komentar v sql/2026-07-25_toptrans_duplicates.sql) - tyhle 2 endpointy
# umoznuji Robertovi/adminovi cisla kdykoli opravit BEZ REDEPLOY.
# ---------------------------------------------------------------------------

def _serialize_price_rule(row):
    return {
        "id": row["id"], "shipping_method_id": row["shipping_method_id"],
        "weight_to_kg": _money(row["weight_to_kg"]),
        "volume_to_m3": float(row["volume_to_m3"]) if row.get("volume_to_m3") is not None else None,
        "km_band": row["km_band"],
        "price_czk": _money(row["price_czk"]), "sort_order": row["sort_order"],
    }


@app.get("/api/admin/shipping-price-rules")
@require_permission("doprava_platba", "zobrazit")
def admin_shipping_price_rules_list():
    shipping_method_id = request.args.get("shipping_method_id")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if shipping_method_id:
                cur.execute(
                    "SELECT * FROM shop_shipping_price_rules WHERE shipping_method_id=%s "
                    "ORDER BY km_band, weight_to_kg", (shipping_method_id,),
                )
            else:
                cur.execute("SELECT * FROM shop_shipping_price_rules ORDER BY shipping_method_id, km_band, weight_to_kg")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"rules": [_serialize_price_rule(r) for r in rows]})


@app.post("/api/admin/shipping-price-rules")
@require_permission("doprava_platba", "vytvorit")
def admin_shipping_price_rules_create():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    try:
        shipping_method_id = int(body.get("shipping_method_id"))
        weight_to_kg = float(body.get("weight_to_kg"))
        km_band = int(body.get("km_band"))
        price_czk = float(body.get("price_czk"))
    except (TypeError, ValueError):
        return jsonify({"error": "Chybí nebo je neplatné shipping_method_id, weight_to_kg, km_band nebo price_czk."}), 400
    volume_to_m3 = body.get("volume_to_m3")
    try:
        volume_to_m3 = float(volume_to_m3) if volume_to_m3 not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatné volume_to_m3."}), 400
    sort_order = int(body.get("sort_order") or 0)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO shop_shipping_price_rules "
                "(shipping_method_id, weight_to_kg, volume_to_m3, km_band, price_czk, sort_order) VALUES (%s,%s,%s,%s,%s,%s)",
                (shipping_method_id, weight_to_kg, volume_to_m3, km_band, price_czk, sort_order),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "shipping_price_rule", new_id, None)
    return jsonify({"status": "ok", "id": new_id}), 201


@app.put("/api/admin/shipping-price-rules/<int:rule_id>")
@require_permission("doprava_platba", "upravit")
def admin_shipping_price_rules_update(rule_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "weight_to_kg" in body:
        fields.append("weight_to_kg=%s"); params.append(float(body.get("weight_to_kg")))
    if "volume_to_m3" in body:
        v = body.get("volume_to_m3")
        fields.append("volume_to_m3=%s"); params.append(float(v) if v not in (None, "") else None)
    if "km_band" in body:
        fields.append("km_band=%s"); params.append(int(body.get("km_band")))
    if "price_czk" in body:
        fields.append("price_czk=%s"); params.append(float(body.get("price_czk")))
    if "sort_order" in body:
        fields.append("sort_order=%s"); params.append(int(body.get("sort_order") or 0))
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    params.append(rule_id)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE shop_shipping_price_rules SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "shipping_price_rule", rule_id, None)
    return jsonify({"status": "ok"})


@app.delete("/api/admin/shipping-price-rules/<int:rule_id>")
@require_permission("doprava_platba", "smazat")
def admin_shipping_price_rules_delete(rule_id):
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shop_shipping_price_rules WHERE id=%s", (rule_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "delete", "shipping_price_rule", rule_id, None)
    return jsonify({"status": "ok"})


@app.post("/api/admin/shipping-price-rules/bulk-delete")
@require_permission("doprava_platba", "smazat")
def admin_shipping_price_rules_bulk_delete():
    """Hromadne smazani vybranych radku ciselniku Toptrans (Robert:
    "mazat musí být všude !!!"). Samostatna ciselnikova tabulka bez FK
    zavislosti jinam - zadne vedlejsi ucinky, staci sdileny bulk_delete()."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id FROM shop_shipping_price_rules WHERE id IN ({placeholders})", ids)
            found_ids = {r["id"] for r in cur.fetchall()}
            deleted = bulk_delete(cur, "shop_shipping_price_rules", ids)
        conn.commit()
    finally:
        conn.close()
    missing = [i for i in ids if i not in found_ids]
    log_audit(admin["id"], "bulk_delete", "shipping_price_rule", None,
              f"{deleted} pravidel ceníku smazáno" + (f", {len(missing)} nenalezeno" if missing else ""))
    return jsonify({"status": "ok", "deleted": deleted,
                     "failed": [{"id": i, "error": "Pravidlo neexistuje."} for i in missing]})


def _serialize_zip_band(row):
    return {
        "id": row["id"], "zip_prefix": row["zip_prefix"], "km_band": row["km_band"],
        "note": row["note"], "sort_order": row["sort_order"],
    }


@app.get("/api/admin/shipping-zip-bands")
@require_permission("doprava_platba", "zobrazit")
def admin_shipping_zip_bands_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_zip_distance_bands ORDER BY zip_prefix")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"zip_bands": [_serialize_zip_band(r) for r in rows]})


@app.post("/api/admin/shipping-zip-bands")
@require_permission("doprava_platba", "vytvorit")
def admin_shipping_zip_bands_create():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    zip_prefix = (body.get("zip_prefix") or "").strip()
    if not zip_prefix or not zip_prefix.isdigit() or len(zip_prefix) > 3:
        return jsonify({"error": "Neplatný PSČ prefix (1-3 číslice)."}), 400
    try:
        km_band = int(body.get("km_band"))
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatné km_band."}), 400
    note = (body.get("note") or "").strip() or None
    sort_order = int(body.get("sort_order") or 0)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_zip_distance_bands WHERE zip_prefix=%s", (zip_prefix,))
            if cur.fetchone():
                conn.rollback()
                return jsonify({"error": f"Pravidlo pro PSČ prefix „{zip_prefix}“ už existuje - použijte PUT."}), 400
            cur.execute(
                "INSERT INTO shop_zip_distance_bands (zip_prefix, km_band, note, sort_order) VALUES (%s,%s,%s,%s)",
                (zip_prefix, km_band, note, sort_order),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "shipping_zip_band", new_id, zip_prefix)
    return jsonify({"status": "ok", "id": new_id}), 201


@app.put("/api/admin/shipping-zip-bands/<int:band_id>")
@require_permission("doprava_platba", "upravit")
def admin_shipping_zip_bands_update(band_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "km_band" in body:
        fields.append("km_band=%s"); params.append(int(body.get("km_band")))
    if "note" in body:
        fields.append("note=%s"); params.append((body.get("note") or "").strip() or None)
    if "sort_order" in body:
        fields.append("sort_order=%s"); params.append(int(body.get("sort_order") or 0))
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    params.append(band_id)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE shop_zip_distance_bands SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "shipping_zip_band", band_id, None)
    return jsonify({"status": "ok"})


@app.delete("/api/admin/shipping-zip-bands/<int:band_id>")
@require_permission("doprava_platba", "smazat")
def admin_shipping_zip_bands_delete(band_id):
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shop_zip_distance_bands WHERE id=%s", (band_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "delete", "shipping_zip_band", band_id, None)
    return jsonify({"status": "ok"})


@app.post("/api/admin/shipping-zip-bands/bulk-delete")
@require_permission("doprava_platba", "smazat")
def admin_shipping_zip_bands_bulk_delete():
    """Hromadne smazani vybranych PSC pravidel (Robert: "mazat musí být
    všude !!!"). Samostatna ciselnikova tabulka, zadne FK zavislosti
    jinam - staci sdileny bulk_delete()."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id FROM shop_zip_distance_bands WHERE id IN ({placeholders})", ids)
            found_ids = {r["id"] for r in cur.fetchall()}
            deleted = bulk_delete(cur, "shop_zip_distance_bands", ids)
        conn.commit()
    finally:
        conn.close()
    missing = [i for i in ids if i not in found_ids]
    log_audit(admin["id"], "bulk_delete", "shipping_zip_band", None,
              f"{deleted} PSČ pravidel smazáno" + (f", {len(missing)} nenalezeno" if missing else ""))
    return jsonify({"status": "ok", "deleted": deleted,
                     "failed": [{"id": i, "error": "Pravidlo neexistuje."} for i in missing]})


@app.post("/api/admin/shipping-zip-bands/bulk-set-km")
@require_permission("doprava_platba", "upravit")
def admin_shipping_zip_bands_bulk_set_km():
    """Hromadne prerazeni vybranych PSC prefixu do jineho vzdalenostniho
    pasma. Realny use-case: Toptrans dodal aktualizovana data ukazujici,
    ze nekolik prefixu je ve skutecnosti v jinem pasmu - misto rucni
    editace radek po radku jedno hromadne prirazeni km_band. Prosty
    sloupec bez vedlejsich ucinku, staci bulk_update_fields()."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    try:
        km_band = int(body.get("km_band"))
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatné km_band."}), 400
    if km_band <= 0:
        return jsonify({"error": "km_band musí být kladné číslo."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id FROM shop_zip_distance_bands WHERE id IN ({placeholders})", ids)
            found_ids = {r["id"] for r in cur.fetchall()}
            updated = bulk_update_fields(cur, "shop_zip_distance_bands", ids, {"km_band": km_band})
        conn.commit()
    finally:
        conn.close()
    missing = [i for i in ids if i not in found_ids]
    log_audit(admin["id"], "bulk_update", "shipping_zip_band", None,
              f"{updated} PSČ prefixů → pásmo {km_band} km" + (f", {len(missing)} nenalezeno" if missing else ""))
    return jsonify({"status": "ok", "updated": updated,
                     "failed": [{"id": i, "error": "Pravidlo neexistuje."} for i in missing]})


@app.post("/api/shipping-price-preview")
@login_required
def shipping_price_preview():
    """
    Nahled ceny dopravy PRED dokoncenim objednavky - Robert: "dodací
    adresu zadává dřív, než je výběr dopravy" - frontend (bot2) muze
    zavolat tenhle endpoint hned po zadani PSC (se znamymi polozkami
    kosiku/objednavky), aby zakaznikovi ukazal spravnou cenu dopravy JESTE
    PRED odeslanim cele objednavky. Pouziva stejnou logiku jako skutecne
    vytvoreni objednavky (_resolve_toptrans_price), takze cena se pak při
    samotnem POST /api/orders nezmeni (pokud se mezitim nezmeni cenik).

    Body: {"shipping_method_id": 4, "delivery_zip": "69601",
           "items": [{"product_id": 12, "qty": 2}, ...]}   NEBO "use_cart": true
    """
    user = current_user()
    body = request.get_json(silent=True) or {}

    try:
        shipping_method_id = int(body.get("shipping_method_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Chybí nebo je neplatné shipping_method_id."}), 400
    delivery_zip = (body.get("delivery_zip") or "").strip()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, price_czk, pricing_mode FROM shop_shipping_methods WHERE id=%s AND active=1",
                (shipping_method_id,),
            )
            sm = cur.fetchone()
            if not sm:
                return jsonify({"error": "Zvolený způsob dopravy neexistuje nebo není aktivní."}), 400

            if sm["pricing_mode"] != "zip_weight":
                return jsonify({"shipping_price_czk": _money(sm["price_czk"]), "km_band": None})

            if body.get("use_cart"):
                cur.execute(
                    "SELECT ci.product_id, ci.qty, ci.configuration_json, ci.config_hash FROM shop_cart_items ci WHERE ci.user_id=%s",
                    (user["id"],),
                )
                items = cur.fetchall()
            else:
                items_in = body.get("items") or []
                items = []
                for raw in items_in:
                    try:
                        items.append({"product_id": int(raw.get("product_id")), "qty": int(raw.get("qty")), "configuration": raw.get("configuration")})
                    except (TypeError, ValueError):
                        return jsonify({"error": "Neplatná položka."}), 400

            total_weight_kg = 0.0
            total_volume_m3 = 0.0
            for it in items:
                # bot5, 2026-10-02: konfigurace sestavy: konfigurace ma hmotnost z konfiguratoru; neuplna hmotnost (chybi hmotnosti dilu v katalogu) = cena dopravy se nepocita
                try:
                    import konfigurace_kosik
                except Exception:
                    konfigurace_kosik = None
                if konfigurace_kosik is not None and (it.get("config_hash") or it.get("configuration") is not None or konfigurace_kosik.je_konfigurovatelny(it["product_id"])):
                    try:
                        kg_cfg, kg_cfg_ok = konfigurace_kosik.hmotnost_pro_nahled(cur, it)
                    except konfigurace_kosik.KonfiguraceChyba as e:
                        return jsonify({"error": e.message, "code": e.code}), e.status
                    if not kg_cfg_ok:
                        return jsonify({"error": konfigurace_kosik.ZPRAVA_HMOTNOST, "code": "weight_incomplete"}), 409
                    total_weight_kg += kg_cfg
                    continue
                cur.execute(
                    "SELECT weight_g, cfg_dily_id, length_mm, width_mm, height_mm "
                    "FROM shop_products WHERE id=%s",
                    (it["product_id"],),
                )
                p = cur.fetchone()
                if p:
                    total_weight_kg += float(p["weight_g"] or 0) / 1000.0 * it["qty"]
                    unit_volume_m3 = _product_unit_volume_m3(cur, p)
                    if unit_volume_m3 is not None:
                        total_volume_m3 += unit_volume_m3 * it["qty"]

            try:
                price, km_band, basis = _resolve_toptrans_price(
                    cur, sm["id"], delivery_zip, total_weight_kg, total_volume_m3
                )
            except _OrderCreateError as e:
                return jsonify({"error": e.message}), e.status_code
    finally:
        conn.close()

    return jsonify({
        "shipping_price_czk": price, "km_band": km_band, "basis": basis,
        "weight_kg": round(total_weight_kg, 2), "volume_m3": round(total_volume_m3, 3),
    })

