"""
Bankovni vypisy FIO - bot10, 2026-08-21.

Kontext (Robert pres bot3): "potrebujeme bankovni vypisy do leveho panelu
administrace, zobrazovat v obsahovem okne (novy tab-panel vedle Prijate
doklady apod.), zobrazovat POUZE prijate platby (kredit, ne debetni/
odchozi), moznost hledat podle castky, navazeme na FIO banku."

Architektura (vzor "append/cache lokalne", stejny jako
remeslo_material_price_history/incoming_documents - NE dotaz na FIO
pri kazdem loadu adminu): FIO REST API (verejne, tokenove) se
periodicky synchronizuje do `bank_transactions` (viz
sql/2026-08-21_bank_transactions.sql), admin panel cte JEN odsud.
Duvod navic k obecnemu vzoru: FIO API ma dokumentovany limit "doporuceny
nejmensi interval dotazu na stejny token je 30 sekund" (FIO API
Bankovnictvi, kap. 5.2) - primy dotaz z kazdeho nacteni stranky by ho
casto porusil.

FIO REST API (overeno primo proti oficialni dokumentaci
https://www.fio.cz/docs/cz/API_Bankovnictvi.pdf, verze 1.9/2025-10-16):
  Base URL: https://fioapi.fio.cz/v1/rest/
  - periods/{token}/{datumOd}/{datumDo}/transactions.{format} - pohyby
    za obdobi (POUZITO TADY - stateless, nezavisi na servery drzenem
    "last" ukazateli, ktery by mohl kolidovat s jinym pouzitim stejneho
    tokenu, napr. rucnim stazenim v internetovem bankovnictvi).
  - last/{token}/transactions.{format} - pohyby od posledniho stazeni
    (NEPOUZITO zamerne - viz vyse).
  Format pouzity: json.

Mapovani sloupcu JSON odpovedi (transactionList.transaction[].columnN.value,
viz dokumentace kap. 5.3.1.6 "JSON", tabulka "Struktura TransactionList"):
  column22 = ID pohybu (unikatni, PK synchronizace)
  column0  = Datum
  column1  = Objem (kladne = prijem/kredit, zaporne = odchozi/debet)
  column14 = Mena
  column2  = Protiucet (cislo uctu protistrany)
  column10 = Nazev protiuctu
  column3  = Kod banky protiuctu
  column12 = Nazev banky protiuctu
  column4  = KS, column5 = VS, column6 = SS
  column7  = Uzivatelska identifikace
  column16 = Zprava pro prijemce
  column8  = Typ pohybu
  column9  = Provedl
  column25 = Komentar
  column17 = ID pokynu

**Ukladaji se VSECHNY platby** - prijate (Objem > 0, puvodni chovani)
i odchozi (Objem < 0, bot10 2026-08-22, viz `direction` sloupec a
_upsert_transactions nize). `amount_czk` je VZDY kladne cislo
(absolutni hodnota), `direction` ('prijem'/'vydaj') rika smer.
Admin panel (`bank_transactions_list()`) VYCHOZI filtruje jen na
`direction='prijem'` (zachovava puvodni chovani beze zmeny), odchozi
jde zobrazit pres `?direction=vydaj` (nebo `?direction=all`).
Odchozi platby se navic paruji (jako NAVRH, ne automaticky) s
`incoming_documents` - viz find_incoming_document_payment_matches()
nize a api/incoming_documents.py.

**Token**: FIO_BANK_API_TOKEN v api/.env (stejny vzor jako
SMTP_PASSWORD/DOGUS_LOGIN_PASSWORD/RENDER_WORKER_TOKEN - viz WORKFLOW.md
bod 2, tajne udaje NIKDY do gitu). Dokud neni nastaven, sync vraci jasnou
chybu (ne tichy no-op) - viz sync_fio_transactions(). Ziskani tokenu
vyzaduje Robertovo primo jednani ve FIO internetovem bankovnictvi
(Nastaveni -> API -> Pridat novy token, typ "Sledovani uctu" staci -
jen cteni, zadne davani prikazu) - zapsano v TASKS.md, NEPTAT SE
Roberta primo (nekomunikuje s boty primo, viz WORKFLOW.md).

Endpointy (admin, @require_permission("bankovni_vypisy", ...)):
  GET  /api/admin/bank-transactions          - seznam + filtr (q, amount, amount_from/to, date_from/to) + strankovani
  POST /api/admin/bank-transactions/sync     - rucni synchronizace (admin tlacitko), vraci pocet novych zaznamu
  GET  /api/admin/bank-transactions/sync-status - info o posledni synchronizaci (pro UI hlasku)

CLI (pro periodicky timer, az bude token k dispozici - vzor
support-email-sync/offer-expiry-reminder v app.py __main__):
  api/venv/bin/python3 api/app.py bank-statements-sync
"""
import datetime
import re
import json
import os
import urllib.error
import urllib.request

import pymysql
import pymysql.cursors
from flask import request, jsonify

from app import (
    app, get_conn, require_permission, current_user, log_audit,
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME,
)

FIO_BASE_URL = "https://fioapi.fio.cz/v1/rest"
FIO_REQUEST_TIMEOUT = 20

# Sloupce FIO JSON odpovedi -> nase pole (viz mapovani v hlavicce souboru).
_COLUMN_MAP = {
    "date": "column0",
    "amount": "column1",
    "counter_account": "column2",
    "counter_bank_code": "column3",
    "constant_symbol": "column4",
    "variable_symbol": "column5",
    "specific_symbol": "column6",
    "user_identification": "column7",
    "transaction_type": "column8",
    "performed_by": "column9",
    "counter_account_name": "column10",
    "counter_bank_name": "column12",
    "currency": "column14",
    "message_for_recipient": "column16",
    "comment": "column25",
    "instruction_id": "column17",
    "transaction_id": "column22",
}


def _fio_token():
    return os.environ.get("FIO_BANK_API_TOKEN", "").strip()


def _column_value(tx, key):
    col = tx.get(_COLUMN_MAP[key])
    if not col:
        return None
    return col.get("value")


def _fetch_fio_transactions(token, date_from, date_to):
    """Stahne pohyby za obdobi z FIO REST API (periods/.../transactions.json).
    Vraci syrovy seznam 'transaction' polozek z JSON odpovedi (i odchozi -
    filtrace na prijem probiha az v _upsert_transactions)."""
    url = f"{FIO_BASE_URL}/periods/{token}/{date_from}/{date_to}/transactions.json"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=FIO_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            raise RuntimeError(
                "FIO API: 409 Conflict - pravdepodobne dalsi dotaz na stejny "
                "token driv nez za 30s od predchoziho (dokumentovany limit)."
            ) from exc
        raise RuntimeError(f"FIO API HTTP chyba {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"FIO API sitova chyba: {exc.reason}") from exc
    tx_list = (
        data.get("accountStatement", {})
        .get("transactionList", {})
        .get("transaction")
        or []
    )
    return tx_list


def _upsert_transactions(cur, tx_list):
    """Zapise VSECHNY platby - prijate (Objem > 0, puvodni chovani) i
    odchozi (Objem < 0, bot10 2026-08-22, Robert pres bot3: "z
    bankovnich vypisu je videt i odchozi platby, sparujme je s
    evidovanymi prijatymi doklady, at admin vidi uhradu a nezaplati
    omylem duplicitne"). `amount_czk` VZDY kladne cislo (absolutni
    hodnota), smer rika `direction` ('prijem'/'vydaj') - jednodussi
    porovnani s incoming_documents.amount_czk (taky vzdy kladne) pri
    parovani, viz find_incoming_document_payment_matches() nize.
    INSERT IGNORE na fio_transaction_id (idempotentni pri
    prekryvajicich se obdobich). Vraci pocet skutecne vlozenych
    (novych) radku."""
    inserted = 0
    for tx in tx_list:
        amount = _column_value(tx, "amount")
        if amount is None or float(amount) == 0:
            continue
        direction = "prijem" if float(amount) > 0 else "vydaj"
        amount_abs = abs(float(amount))
        fio_id = _column_value(tx, "transaction_id")
        date_raw = _column_value(tx, "date")
        tx_date = (date_raw or "")[:10] or None
        cur.execute(
            "INSERT IGNORE INTO bank_transactions "
            "(fio_transaction_id, transaction_date, amount_czk, direction, currency, "
            "counter_account, counter_account_name, counter_bank_code, counter_bank_name, "
            "variable_symbol, constant_symbol, specific_symbol, user_identification, "
            "message_for_recipient, transaction_type, performed_by, comment, instruction_id, raw_json) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                fio_id, tx_date, amount_abs, direction, _column_value(tx, "currency") or "CZK",
                _column_value(tx, "counter_account"), _column_value(tx, "counter_account_name"),
                _column_value(tx, "counter_bank_code"), _column_value(tx, "counter_bank_name"),
                _column_value(tx, "variable_symbol"), _column_value(tx, "constant_symbol"),
                _column_value(tx, "specific_symbol"), _column_value(tx, "user_identification"),
                _column_value(tx, "message_for_recipient"), _column_value(tx, "transaction_type"),
                _column_value(tx, "performed_by"), _column_value(tx, "comment"),
                _column_value(tx, "instruction_id"), json.dumps(tx, ensure_ascii=False),
            ),
        )
        if cur.rowcount:
            inserted += 1
    return inserted


def sync_fio_transactions(date_from=None, date_to=None):
    """Hlavni synchronizacni funkce - pouziva se z admin tlacitka i CLI
    (budouci timer). date_from/date_to (YYYY-MM-DD) - default: od
    posledniho uspesneho sync data (bank_sync_state.last_synced_date,
    s 1denním prekryvem pro jistotu) do dneska, nebo poslednich 30 dni
    pri prvnim behu. Vraci dict se statusem, poctem novych zaznamu."""
    token = _fio_token()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not token:
                cur.execute(
                    "UPDATE bank_sync_state SET last_sync_at=NOW(), last_sync_status='chyba', "
                    "last_sync_error='FIO_BANK_API_TOKEN neni nastaven v api/.env' WHERE id=1"
                )
                conn.commit()
                return {"status": "chyba", "error": "FIO_BANK_API_TOKEN neni nastaven v api/.env."}

            today = datetime.date.today()
            if not date_to:
                date_to = today.isoformat()
            if not date_from:
                cur.execute("SELECT last_synced_date FROM bank_sync_state WHERE id=1")
                row = cur.fetchone()
                last = row["last_synced_date"] if row else None
                if last:
                    date_from = (last - datetime.timedelta(days=1)).isoformat()
                else:
                    date_from = (today - datetime.timedelta(days=30)).isoformat()

            try:
                tx_list = _fetch_fio_transactions(token, date_from, date_to)
            except RuntimeError as exc:
                cur.execute(
                    "UPDATE bank_sync_state SET last_sync_at=NOW(), last_sync_status='chyba', "
                    "last_sync_error=%s WHERE id=1",
                    (str(exc)[:500],),
                )
                conn.commit()
                return {"status": "chyba", "error": str(exc)}

            inserted = _upsert_transactions(cur, tx_list)
            cur.execute(
                "UPDATE bank_sync_state SET last_synced_date=%s, last_sync_at=NOW(), "
                "last_sync_status='ok', last_sync_error=NULL, last_sync_count=%s WHERE id=1",
                (date_to, inserted),
            )
            # bot10, 2026-08-22 (Robert pres bot3, TASKS.md "Objednavky:
            # parovani bankovnich plateb podle VS") - automaticky po
            # KAZDEM behu syncu, bezpecne (jen cteni/oznaceni stavu +
            # vystaveni VDD, nic neposila ven - e-mail jde pres
            # schvalovaci frontu, viz WORKFLOW.md bod 16).
            match_result = match_bank_payments_to_orders(cur)
            conn.commit()
            result = {
                "status": "ok", "inserted": inserted, "date_from": date_from, "date_to": date_to,
                "bank_paid_matched": match_result["matched"],
                "bank_paid_amount_warnings": match_result["amount_warnings"],
                "bank_paid_auto_issued": match_result["auto_issued"],
                "bank_paid_vs_conflicts": match_result["vs_conflicts"],
                "bank_paid_partial_payments": match_result["partial_payments"],
            }
    finally:
        conn.close()

    # bot10, 2026-08-22: side-effekty (log_audit + automaticky e-mail) AZ
    # PO commitu a conn.close() - log_audit()/documents._auto_email_after_
    # issue() si otviraji VLASTNI spojeni (get_conn()), ktere je na
    # stejnem threadu sdilene s timhle - volani driv (uvnitr jeste
    # otevrene transakce) by ji predcasne zacommitovalo/rozbilo (znama
    # past, viz AGENTS_LOG.md "pooled conn rollback trap"). Stejny vzor
    # jako VSECHNY existujici doklad-endpointy v api/documents.py.
    for doc in result["bank_paid_auto_issued"]:
        import documents
        log_audit(None, "create", "document_payment_tax", doc["document_id"], doc["document_number"])
        documents._auto_email_after_issue(doc["order_id"], doc["document_id"])
    return result


AUTO_ISSUE_PAYMENT_TAX_DOCUMENT = True  # bot10, 2026-08-22: docasne
# vypnuto, pak znovu povoleno stejny den - viz AGENTS_LOG.md "DULEZITY
# NALEZ" + nasledny zaznam "OMYL, revert". Prvni realny backfill
# ukazal, ze u vsech 25 sparovanych objednavek castka z banky odpovida
# shop_orders.total_czk (ne total_czk*1,21) - vypadalo to na mozny
# problem se zakaznickym podfakturovanim DPH, docasne vypnuto pro
# jistotu. Robert pak primym porovnanim se SKUTECNYM admin zaznamem na
# zivem logiman.cz potvrdil, ze shop_orders.total_czk/shipping_price_czk
# u techhle (importovanych historickych) objednavek JSOU spravne S DPH
# (gross) - zadny bug, zadne podfakturovani, jen mylna domnenka po
# cestě (viz AGENTS_LOG.md pro cely prubeh vc. omylem provedene a
# nasledne vracene "opravy"). Auto-VDD zustava zapnute, nic mu nebrani.


def _create_auto_payment_tax_document(cur, order, bank_amount_gross, payment_date):
    """Automaticky vystavi Danovy doklad k prijate platbe (VDD), volano
    z match_bank_payments_to_orders() pri KAZDE NOVE shode VS (bot10,
    2026-08-22, Robert pres bot3: "kdyz admin vystavi danovy doklad k
    prijate platbe uz nechceme > musi se vystavovat automaticky pri
    prijeti platby"). Zrcadli rucni endpoint
    admin_documents_mark_payment_received() (api/documents.py) - vola
    STEJNOU documents.create_payment_tax_document(), jen programove s
    castkou/datem z bank_transactions misto rucne vyplneneho formulare.
    Rucni endpoint NEODSTRANEN - objednavky placene jinak (hotovost,
    karta osobne) ho porad potrebuji, tohle je DRUHA, automaticka cesta
    vedle nej.

    `bank_amount_gross` je castka, co skutecne dorazila na ucet - VC.
    DPH (tak zakaznik plati "K ZAPLACENI" z proformy/webu). Naproti
    tomu `shop_orders.total_czk` je NAOPAK BEZ DPH (viz
    documents._build_items_with_vat - radky objednavky se berou primo
    jako unit_price_net), proto se nepouziva primo - amount_net se
    dopocita z bank_amount_gross vydelenim (1 + VAT_RATE/100).

    DULEZITE (pooled-connection past, viz AGENTS_LOG.md): tahle funkce
    NEVOLA log_audit()/documents._auto_email_after_issue() primo (ty si
    otevriraji VLASTNI spojeni get_conn(), ktere by na stejnem threadu
    uprostred JESTE NEZAKOMMITOVANE transakce predcasne zacommitovalo/
    rozbilo cely sync). Volajici (sync_fio_transactions) tyhle
    side-effekty provede AZ PO commitu + conn.close(), stejnym vzorem
    jako vsechny existujici doklad-endpointy.

    OPRAVA (bot10, 2026-08-26, "ghost VDD", schvaleno bot3): INSERT
    dokladu + UPDATE payment_received_* driv bezely na sdilenem `cur`
    cele davky (match_bank_payments_to_orders -> sync_fio_transactions,
    jeden nepodmineny conn.commit() na konci VSECH objednavek) - kdyz
    INSERT dokladu prosel, ale nasledny UPDATE selhal, except nize jen
    logoval a vratil None, ale JIZ PROVEDENY INSERT zustal v transakci a
    komitnul se spolu se zbytkem davky (zadny rollback pri navratu None).
    Vysledek: realny doklad v DB (spotrebuje cislo rady), ale mimo
    `auto_issued` list -> zadny log_audit, zadny e-mail do fronty, admin
    o nem nevi. Ted bezi na SKUTECNE nezavislem spojeni (`pymysql.
    connect()` PRIMO, NE get_conn() - ten je thread-local pooled/1
    spojeni na thread, druhe volani na stejnem threadu jako sdileny
    `cur` by vratilo TOTOZNE spojeni, takze rollback by stshl i uz
    zpracovane objednavky driv v tehle davce). Kdyz kterykoli z obou
    kroku selze, TOHLE spojeni se vrati zpet (rollback), aniz by se
    dotklo sdilene transakce davky - bank_paid=1 na sdilenem `cur`
    (nastaveno PRED timhle volanim) zustava nedotceno, presne jak ma.

    Vraci dict {"order_id","order_number","document_id","document_number"}
    pro pozdejsi log_audit/e-mail, nebo None pri jakekoli chybe (jen
    zalogovano printem, NIKDY nesmi shodit parovani/sync), NEBO kdyz
    zvolena platebni metoda objednavky nevyzaduje platbu predem (viz
    kontrola nize).

    BUG oprava (bot10, 2026-08-22, zjistil bot3/Robert: "VDD vzniká
    pouze při platbě předem"): puvodni verze tehle funkce volala
    create_payment_tax_document() pro KAZDOU shodu VS bez ohledu na
    zvolenou platebni metodu - vystavila VDD i pro 6 objednavek s
    "Dobírkou"/"Online platba kartou", kde VDD nepatri (jen bankovni
    prevod predem). Kontrola pouziva STEJNY strukturovany priznak, jaky
    uz pouziva documents.create_proforma_invoice_if_needed() a orders.py
    pro stejny ucel (WORKFLOW1 vs WORKFLOW2) -
    shop_payment_methods.requires_advance_invoice.

    DULEZITE zjisteni pri implementaci (bot10): presny name-match na
    zivy katalog SAM O SOBE nestaci - historicky CSV import (VSECH 39
    aktualnich objednavek) uklada payment_method_name jako volny text
    ("Dobírkou", "Převodem - zálohová faktura", ...), ktery se PRESNE
    neshoduje se zivymi radky v shop_payment_methods ("Dobírka",
    "Platba předem", ...) - presny match by tedy vratil "zadny radek"
    pro VŠECHNY historicke objednavky, vc. tech se skutecnou platbou
    predem (regrese - VDD by nikdy nevzniklo ani tam, kde ma). Overeno
    zivym dotazem (3 objednavky s bank_paid=0 a "Převodem - zálohová
    faktura" by tim byly postizeny). Pro "Dobírkou"/"Online platba
    kartou"/"Apple Pay"/"Google Pay"/"Převodem 14 dní po dodání" mismatch
    naopak NEVADI - spadnou do bezpecneho "zadna shoda -> nevystavit",
    coz uz je spravny vysledek.

    Reseni: primy match zustava PRIMARNI cestou (spolehlivy pro VSECHNY
    BUDOUCI objednavky z realneho e-shop checkoutu - tam payment_method_
    name vzdy vznika kopii ZE ZIVEHO katalogoveho radku, viz
    _resolve_and_insert_order). Kdyz presny radek nenajde, fallback na
    klicova slova v nazvu ("zálohov"/"předem") - presne navrh z
    TASKS.md pro pripad, ze strukturovany priznak na historicka data
    nesedi. Netyka se zadneho jineho konzumenta stejneho pole (napr.
    orders.py "nejde na Připravit bez platby" gate ma STEJNY problem u
    historickych dat - nahlaseno zvlast, mimo rozsah teto opravy).

    bank_paid/bank_paid_at (parovani VS samo o sobe) tímhle NENÍ
    dotčeno - nastavuje se v match_bank_payments_to_orders() PŘED
    volanim tehle funkce, pro VŠECHNY platebni metody stejne (Robert
    resil vyslovne jen VDD, ne samotne parovani platby - "VDD vzniká
    pouze při platbě předem" mluvi jen o dokladu, ne o priznaku
    uhrazeno)."""
    import documents
    if order.get("payment_method_name"):
        cur.execute(
            "SELECT requires_advance_invoice FROM shop_payment_methods WHERE name=%s",
            (order["payment_method_name"],),
        )
        pm_row = cur.fetchone()
        if pm_row:
            requires_advance = bool(pm_row["requires_advance_invoice"])
        else:
            name_lower = order["payment_method_name"].strip().lower()
            requires_advance = ("zálohov" in name_lower) or ("předem" in name_lower)
        if not requires_advance:
            return None
    else:
        # Bez zvolene platebni metody (napr. stary import) nevime jistě,
        # ze jde o platbu predem - bezpecny default je NEVYSTAVOVAT
        # (stejny princip jako create_proforma_invoice_if_needed vyse).
        return None
    amount_net = round(float(bank_amount_gross) / (1 + documents._order_vat_rate(order) / 100), 2)
    if amount_net <= 0:
        return None
    dedicated_conn = None
    try:
        dedicated_conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10, read_timeout=25, write_timeout=25,
        )
        with dedicated_conn.cursor() as dcur:
            dcur.execute(
                "SELECT * FROM shop_documents WHERE order_id=%s AND document_type='proforma_invoice'",
                (order["id"],),
            )
            proforma = dcur.fetchone()
            issued_by_label = documents._issued_by_label(None)
            result = documents.create_payment_tax_document(dcur, order, proforma, amount_net, payment_date, issued_by_label)
            # bot5, 2026-09-29 (Robert primo, objednavka OBJ-2026-00001:
            # "prijal jsem platbu celych 12tisic... dnes je napsano jen
            # castecna uhrada") - payment_received_total_czk se VSUDE
            # JINDE (admin_documents_list/admin_documents_mark_payment_
            # received guard, objednavky-doklady.js badge) porovnava
            # PRIMO proti total_czk (GROSS) bez prevodu - tenhle radek
            # ale pricital amount_net (BEZ DPH), takze soucet trvale
            # nedosahl total_czk o presne castku DPH. Opraveno na
            # result["total_with_vat_czk"] (skutecna GROSS castka VDD
            # prave vystaveneho o par radku vyse), stejna jednotka jako
            # total_czk vsude jinde.
            new_total_received = round((float(order["payment_received_total_czk"] or 0)) + result["total_with_vat_czk"], 2)
            dcur.execute(
                "UPDATE shop_orders SET payment_received_at=%s, payment_received_total_czk=%s WHERE id=%s",
                (payment_date, new_total_received, order["id"]),
            )
        dedicated_conn.commit()
        return {
            "order_id": order["id"], "order_number": order["order_number"],
            "document_id": result["id"], "document_number": result["document_number"],
        }
    except Exception as e:
        if dedicated_conn is not None:
            try:
                dedicated_conn.rollback()
            except Exception:
                pass
        print(f"[bank_statements] automaticke vystaveni VDD selhalo pro objednavku {order['order_number']}: {e}")
        return None
    finally:
        if dedicated_conn is not None:
            try:
                dedicated_conn.close()
            except Exception:
                pass


def _order_vs_candidates(cur, order):
    """Vraci seznam kandidatu na VS pro parovani bankovni platby, v
    poradí priority (bot10, 2026-08-22, BUG oprava - Robert po serii
    zjisteni: "zálohové faktury mají také svoji řadu číselnou i
    prefix" + VS ma byt cislo dokladu, ne interni id ani order_number):

    1. VS zalohove faktury teto objednavky (shop_documents.variable_
       symbol WHERE document_type='proforma_invoice') - SPRAVNY
       mechanismus pro objednavky zalozene primo v konfiguratoru (tam
       zakaznik dostane zalohovku s timhle VS a podle nej i plati).
    2. VS PUVODNI ONLINE NABIDKY, ze ktere objednavka vznikla
       (bot5, 2026-09-17, Robert primo pres bot3/bot9: zakaznik muze
       zaplatit primo pres QR kod na strance nabidky JESTE PRED tim,
       nez vubec vznikne zalohova faktura objednavky - ten QR kod nese
       VLASTNI VS, viz api/scene_offers.py::public_offer_payment_qr
       "vs = re.sub(r'\\D', '', offer['offer_number']) or str(offer['id'])").
       Kandidat jen kdyz `shop_orders.source_scene_offer_id` je
       vyplnene - spocteno STEJNYM vzorcem, aby vysledek byl bajt-
       identicky s tim, co zakaznik skutecne videl/pouzil na QR kodu.
    3. shop_orders.order_number - FALLBACK pro historicke/importovane
       objednavky ze stareho e-shopu (Shoptet/Upgates), kde zadna
       zalohova faktura ani online nabidka v konfiguratoru nikdy
       nevznikla - zakaznik tehdy platil podle CISLA OBJEDNAVKY toho
       stareho systemu, coz uz je neměnny historicky fakt na
       bankovnim vypisu. Rozhodnuti Robert/bot3 (2026-08-22): dual-path,
       aby zadna z uz drive spravne sparovanych historickych objednavek
       neprestala fungovat jen proto, ze presny mechanismus VS se
       zmenil pro NOVE objednavky (viz TASKS.md/AGENTS_LOG.md pro cely
       kontext).

    bot16, 2026-09-02 (revize bot3, bod 9 - kolize VS): order_number je
    kandidat JEN KDYZ objednavka NEMA zadny presnejsi kandidat vyse
    (zalohovku ani online nabidku). Tvar VS zalohovky (26+MM+rocni
    poradi, documents.py) a Upgates order_number importu
    (26080054-26080092) se mohou potkat - zakaznik s presnejsim
    kandidatem plati vzdy podle nej, takze fallback na order_number u
    takove objednavky by jen umoznil prisvojit si cizi platbu. Kolize
    samotna se resi v _vs_conflicts() pred oznacenim bank_paid.

    Vraci jen existujici/neprazdne kandidaty, bez duplicit, v poradí
    priority - volajici zkousi kazdy postupne a bere PRVNI, ktery ma
    aspon jednu odpovidajici bankovni transakci."""
    candidates = []
    cur.execute(
        "SELECT variable_symbol FROM shop_documents WHERE order_id=%s AND document_type='proforma_invoice'",
        (order["id"],),
    )
    proforma = cur.fetchone()
    if proforma and proforma["variable_symbol"]:
        candidates.append(proforma["variable_symbol"])
    if order.get("source_scene_offer_id"):
        cur.execute("SELECT id, offer_number FROM scene_offers WHERE id=%s", (order["source_scene_offer_id"],))
        offer = cur.fetchone()
        if offer:
            offer_vs = re.sub(r"\D", "", offer["offer_number"] or "") or str(offer["id"])
            if offer_vs and offer_vs not in candidates:
                candidates.append(offer_vs)
    if not candidates and order.get("order_number"):
        candidates.append(order["order_number"])
    return candidates


def _vs_conflicts(cur, vs, order):
    """Cizi objednavky, na ktere sedi TENTYZ VS (bot16, 2026-09-02, revize
    bot3 bod 9): zalohovka jine objednavky se stejnym VS, jina
    objednavka s order_number == VS, nebo jina objednavka, jejiz
    zdrojova online nabidka ma stejny VS (bot5, 2026-09-17, doplneno
    soucasne s tretim kandidatem v _order_vs_candidates() vyse -
    stejna trida kolize, jen pro novy typ VS). Neprazdny vysledek =
    platbu nelze automaticky prisoudit (jedna platba by oznacila dve
    objednavky a vystavila dva VDD) - volajici objednavku preskoci a
    vrati konflikt v `vs_conflicts` k rucnimu rozhodnuti. Vraci seznam
    {"order_id", "order_number", "via": "proforma"|"order_number"|"scene_offer"}."""
    conflicts = []
    cur.execute(
        "SELECT d.order_id, o.order_number FROM shop_documents d "
        "JOIN shop_orders o ON o.id=d.order_id "
        "WHERE d.document_type='proforma_invoice' AND d.variable_symbol=%s AND d.order_id<>%s",
        (vs, order["id"]),
    )
    for r in cur.fetchall():
        conflicts.append({"order_id": r["order_id"], "order_number": r["order_number"], "via": "proforma"})
    cur.execute(
        "SELECT id, order_number FROM shop_orders WHERE order_number=%s AND id<>%s",
        (vs, order["id"]),
    )
    for r in cur.fetchall():
        conflicts.append({"order_id": r["id"], "order_number": r["order_number"], "via": "order_number"})
    cur.execute(
        "SELECT so.id, so.order_number, sof.id AS offer_id, sof.offer_number "
        "FROM shop_orders so JOIN scene_offers sof ON sof.id = so.source_scene_offer_id "
        "WHERE so.id<>%s",
        (order["id"],),
    )
    for r in cur.fetchall():
        offer_vs = re.sub(r"\D", "", r["offer_number"] or "") or str(r["offer_id"])
        if offer_vs == vs:
            conflicts.append({"order_id": r["id"], "order_number": r["order_number"], "via": "scene_offer"})
    return conflicts


def _order_expected_amount(cur, order):
    """Castka, proti ktere se ma bankovni platba porovnavat - PRIMARNE
    amount_due_czk ze zalohove faktury objednavky (bot5, 2026-09-28,
    Robert primo: "nesedi presne castka na zalohove fakture se
    skutecnou platbou -> k doreseni rucne", ne uz order['total_czk']
    jako driv). Kdyz zalohova faktura neexistuje (WORKFLOW2/historicka
    data), padne zpatky na order['total_czk'] - stejne jako puvodne."""
    cur.execute(
        "SELECT amount_due_czk FROM shop_documents WHERE order_id=%s AND document_type='proforma_invoice'",
        (order["id"],),
    )
    proforma = cur.fetchone()
    if proforma and proforma["amount_due_czk"] is not None:
        return float(proforma["amount_due_czk"])
    return float(order["total_czk"])


def _iter_order_payment_matches(cur, order_numbers=None):
    """READ ONLY: pro kazdou objednavku s bank_paid=0, ktera ma alespon
    jednu prijatou CZK platbu pod nekterym ze svych VS kandidatu (viz
    _order_vs_candidates), vrati (order, matched_vs, row, conflicts,
    expected_amount) - "row" ma "first_date"/"total_paid" ze SUM pres
    ten VS, "expected_amount" viz _order_expected_amount() vyse. Sdilena
    logika mezi match_bank_payments_to_orders (zapisuje bank_paid) a
    find_partial_payments (jen cte, bod 10 varianta b - castecne
    uhrady, bot3/Robert 2026-09-03) - obe potrebuji STEJNE parovani,
    lisi se jen v tom, co s vysledkem udelaji."""
    if order_numbers:
        cur.execute(
            "SELECT * FROM shop_orders WHERE bank_paid=0 AND order_number IN %s",
            (tuple(order_numbers),),
        )
    else:
        cur.execute("SELECT * FROM shop_orders WHERE bank_paid=0")
    unpaid = cur.fetchall()
    for order in unpaid:
        row = None
        matched_vs = None
        for vs in _order_vs_candidates(cur, order):
            # currency='CZK' (bot16, 2026-09-02, revize bot3): platba v cizi
            # mene se nesmi secist s CZK a oznacit objednavku za uhrazenou.
            cur.execute(
                "SELECT MIN(transaction_date) AS first_date, SUM(amount_czk) AS total_paid "
                "FROM bank_transactions WHERE variable_symbol=%s AND direction='prijem' AND currency='CZK'",
                (vs,),
            )
            candidate_row = cur.fetchone()
            if candidate_row and candidate_row["first_date"]:
                row = candidate_row
                matched_vs = vs
                break
        if not row:
            continue
        conflicts = _vs_conflicts(cur, matched_vs, order)
        yield order, matched_vs, row, conflicts, _order_expected_amount(cur, order)


def find_partial_payments(cur, order_numbers=None):
    """READ ONLY varianta pro GET /api/admin/bank-transactions/partial-payments
    (bot3/Robert 2026-09-03, bod 10 varianta b) - zadne zapisy, jen
    seznam objednavek, kde soucet napojenych CZK plateb NESEDI PRESNE
    (tolerance 1 Kc) na expected_amount (viz _order_expected_amount -
    castka na zalohove fakture, ne uz vzdy order['total_czk']).
    Rozsireno bot5, 2026-09-28 (Robert primo: "nesedi presne castka na
    zalohove fakture se skutecnou platbou -> k doreseni rucne") i o
    PREPLATEK, ne jen podplatek jako driv - missing_czk pak vyjde
    zaporne (= castka navic). VS kolize (_vs_conflicts) se sem
    NEPOCITAJI - ty maji vlastni "vs_conflicts" hlaseni a nejde
    jednoznacne rict, kolik z castky patri ktere objednavce."""
    out = []
    for order, _matched_vs, row, conflicts, expected_amount in _iter_order_payment_matches(cur, order_numbers):
        if conflicts:
            continue
        total_paid_gross = float(row["total_paid"] or 0)
        if abs(total_paid_gross - expected_amount) > 1:
            out.append({
                "order_number": order["order_number"],
                "total_czk": expected_amount,
                "bank_total_czk": total_paid_gross,
                "missing_czk": round(expected_amount - total_paid_gross, 2),
                "first_payment_date": row["first_date"].isoformat() if row["first_date"] else None,
            })
    return out


def match_bank_payments_to_orders(cur, order_numbers=None):
    """Sparuje bankovni platby s objednavkami podle variabilniho symbolu
    (VS) - viz _order_vs_candidates() pro presny popis dual-path
    priority (zalohova faktura primarne, order_number jako fallback pro
    historicka data). PUVODNE (bot10, 2026-08-22, Robert pres bot3:
    "u objednavek potrebujeme nove 2 sloupce, uhrazena/neuhrazena a
    uhrazena kdy. parovaci znak je VS") matchovalo VYHRADNE proti
    order_number - BUG, VS na zalohove fakture byl v te dobe jeste
    mylne interni DB id objednavky (viz TASKS.md/AGENTS_LOG.md).

    Zapisuje do NOVYCH sloupcu bank_paid/bank_paid_at
    (sql/2026-08-22_shop_orders_bank_paid.sql) - NEDOTYKA SE
    payment_received_at/payment_received_total_czk (ty aktualizuje az
    _create_auto_payment_tax_document() vyse, stejnym zpusobem jako
    rucni endpoint - jiny ucel/tok od bank_paid, Robert vyslovne
    potvrdil pres AskUserQuestion, ze chce oddelene sloupce).

    Parovani JEN podle shody VS (zakladni pravidlo, Robert to explicitne
    takhle nezadal jinak) - soucet napojenych plateb (SUM(amount_czk))
    se porovna PRIMO s expected_amount (viz _order_expected_amount -
    castka na zalohove fakture objednavky, obojí S DPH). PUVODNE
    (bot10, 2026-08-22) byla neshoda jen "bezpecnostni kontrola/
    varovani" - u podstrelu se VDD nevystavilo (partial_payments), ale
    u preplatku/jine neshody se VDD ZAROVEN vystavilo (na castku, co
    skutecne dosla) a jen se zapsalo do "amount_warnings". ZMENENO
    (bot5, 2026-09-28, Robert primo: "je potreba ale neupravovat
    automaticky rozdil kdyz nesedi presne castka na zalohove fakture se
    skutecnou platbou... k doreseni rucne") - ZADNA neshoda (nad 1 Kc
    tolerance, oba smery) uz VDD automaticky nevystavi ani neoznaci
    bank_paid=1, vzdy skonci v "partial_payments" k rucnimu rozhodnuti
    (stejny bucket pro podstrel i preplatek - "missing_czk" zaporne =
    castka navic). "amount_warnings" tim padem uz zachyti jen drobne
    rozdily v ramci 0.5-1 Kc (bankovni zaokrouhleni), na ty se VDD
    porad vystavi normalne.

    Idempotentni a lehke volat opakovane (napr. po kazdem behu
    sync_fio_transactions) - bere jen objednavky s bank_paid=0, jednou
    nastavene datum uz nemeni ani kdyz pribude dalsi platba se stejnym
    VS - VDD se tedy taky vystavi jen JEDNOU, pri prvni shode. Vraci
    dict {"matched", "amount_warnings", "auto_issued", "vs_conflicts"} - "auto_issued"
    je seznam nove vystavenych VDD dokladu, volajici z nej AZ PO
    commitu/close spojeni udela log_audit + automaticky e-mail.

    `order_numbers` (volitelne) omezi parovani jen na tenhle seznam VS -
    pouzito pro izolovane zive overeni na testovacich objednavkach pred
    pustenim na celou historii (bot10, 2026-08-22)."""
    matched = 0
    amount_warnings = []
    auto_issued = []
    vs_conflicts = []   # bot16, 2026-09-02: VS sedici na vic objednavek -> neparovat, k rucnimu rozhodnuti
    # partial_payments (bot3/Robert 2026-09-03, bod 10 varianta b;
    # rozsireno o preplatek bot5 2026-09-28 - viz docstring vyse):
    # soucet napojenych plateb NESEDI PRESNE na expected_amount (tolerance
    # 1 Kc, oba smery) - objednavka se NEoznaci bank_paid=1 a VDD se
    # NEvystavi, jen se zaznamena sem k rucnimu doreseni. Priste (dalsi
    # sync) uz muze mit vic plateb pod stejnym VS a SUM to sam dozene -
    # zadny dalsi kod netreba (u preplatku samo nezmizi, tam ceka na
    # rucni rozhodnuti admina).
    partial_payments = []
    for order, matched_vs, row, conflicts, expected_amount in _iter_order_payment_matches(cur, order_numbers):
        if conflicts:
            info = {
                "variable_symbol": matched_vs,
                "order_number": order["order_number"],
                "conflicting_orders": conflicts,
                "bank_total_czk": float(row["total_paid"] or 0),
            }
            vs_conflicts.append(info)
            print(f"[bank_statements] KOLIZE VS {matched_vs}: objednavka {order['order_number']} vs "
                  f"{[c['order_number'] for c in conflicts]} - neparovano, nutne rucni rozhodnuti")
            continue
        total_paid_gross = float(row["total_paid"] or 0)
        if abs(total_paid_gross - expected_amount) > 1:
            partial_payments.append({
                "order_number": order["order_number"],
                "total_czk": expected_amount,
                "bank_total_czk": total_paid_gross,
                "missing_czk": round(expected_amount - total_paid_gross, 2),
                "first_payment_date": row["first_date"].isoformat() if row["first_date"] else None,
            })
            continue
        try:
            cur.execute(
                "UPDATE shop_orders SET bank_paid=1, bank_paid_at=%s WHERE order_number=%s AND bank_paid=0",
                (row["first_date"], order["order_number"]),
            )
            # Commit HNED po nastaveni bank_paid=1, PRED volanim VDD funkce
            # nize (bot13, 2026-09-02, oprava nalezu z revize kodu - self-
            # lock). _create_auto_payment_tax_document() otevira VLASTNI
            # (dedicated_conn) spojeni a zapisuje do STEJNEHO radku
            # shop_orders (jen jiny sloupec, payment_received_*). Kdyz by
            # tenhle UPDATE zustal nekomitnuty (puvodne se commitovalo az
            # na uplnem konci cele davky v sync_fio_transactions), druhe
            # spojeni by na jeho zamek cekalo az do innodb_lock_wait_timeout
            # (50s, SHOW VARIABLES LIKE 'innodb_lock_wait_timeout') a pak
            # tise selhalo - VDD by se nikdy nevystavil. Vznik zamku od
            # opravy "ghost VDD" (396cf5b, 2026-08-26), ktera presunula VDD
            # zapis na dedicated_conn, ale commit puvodniho UPDATE zustal
            # az na konci cele davky - nikdy spolu naostro neotestovano
            # (viz "pozitivni cesta neni testovana live" v tom commitu).
            cur.connection.commit()
        except Exception as e:
            cur.connection.rollback()
            print(f"[bank_statements] parovani platby k objednavce {order['order_number']} selhalo, pokracuji dalsi: {e}")
            continue
        matched += 1
        # bot10, 2026-08-22 (po omylu a revertu, viz AGENTS_LOG.md): PRIME
        # porovnani s expected_amount, BEZ prepoctu na DPH - obojí je
        # castka s DPH (gross), stejna jako castka na bankovnim vypisu.
        # Rozdil nad 1 Kc (oba smery) uz je VYSE zachycen jako
        # partial_payments (continue, bot5 2026-09-28) - sem se dostane
        # jen presna shoda nebo drobny rozdil v ramci 1 Kc tolerance
        # (bankovni zaokrouhleni), ktery se jen POZNAMENA sem pro
        # prubezne sledovani, jestli se neopakuje stejny vzorec u vic
        # objednavek (Robert pres bot3, 2026-08-22) - nezamita match.
        if abs(total_paid_gross - expected_amount) > 0.5:
            amount_warnings.append({
                "order_number": order["order_number"],
                "total_czk": expected_amount,
                "bank_total_czk": total_paid_gross,
            })
        doc_info = _create_auto_payment_tax_document(cur, order, total_paid_gross, row["first_date"]) if AUTO_ISSUE_PAYMENT_TAX_DOCUMENT else None
        if doc_info:
            auto_issued.append(doc_info)
    return {"matched": matched, "amount_warnings": amount_warnings, "auto_issued": auto_issued,
            "vs_conflicts": vs_conflicts, "partial_payments": partial_payments}


def run_bank_sync_cli():
    result = sync_fio_transactions()
    print(result)


def _serialize(row):
    return {
        "id": row["id"],
        "fio_transaction_id": row["fio_transaction_id"],
        "transaction_date": row["transaction_date"].isoformat() if row["transaction_date"] else None,
        "amount_czk": float(row["amount_czk"]) if row["amount_czk"] is not None else None,
        "direction": row["direction"],
        "currency": row["currency"],
        "counter_account": row["counter_account"],
        "counter_account_name": row["counter_account_name"],
        "counter_bank_code": row["counter_bank_code"],
        "counter_bank_name": row["counter_bank_name"],
        "variable_symbol": row["variable_symbol"],
        "constant_symbol": row["constant_symbol"],
        "specific_symbol": row["specific_symbol"],
        "user_identification": row["user_identification"],
        "message_for_recipient": row["message_for_recipient"],
        "transaction_type": row["transaction_type"],
        "performed_by": row["performed_by"],
        "comment": row["comment"],
        "instruction_id": row["instruction_id"],
        "is_test_data": bool(row["is_test_data"]),
        "synced_at": row["synced_at"].isoformat() if row["synced_at"] else None,
        "linked_incoming_document_id": row.get("linked_incoming_document_id"),
        "linked_incoming_document_supplier": row.get("linked_incoming_document_supplier"),
    }


@app.get("/api/admin/bank-transactions")
@require_permission("bankovni_vypisy", "zobrazit")
def bank_transactions_list():
    """?q=... hleda ve VS/protiuctu/nazvu protiuctu/zprave pro prijemce.
    ?amount=... presna castka. ?amount_from=/?amount_to=... rozsah castky
    (Robertovo zadani "moznost hledat podle castky" - podporovano obojim,
    presna shoda i rozsah, at jde najit platbu i kdyz si clovek nepamatuje
    haleru presne). ?date_from=/?date_to=... filtr na datum.

    ?direction=prijem|vydaj|all (bot10, 2026-08-22) - VYCHOZI 'prijem'
    (zachovava puvodni chovani beze zmeny, kdyz parametr chybi), 'vydaj'
    zobrazi odchozi platby, 'all' obojí."""
    q = (request.args.get("q") or "").strip()
    amount = request.args.get("amount")
    amount_from = request.args.get("amount_from")
    amount_to = request.args.get("amount_to")
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    direction = (request.args.get("direction") or "prijem").strip()

    # bot10, 2026-08-22: vsechny WHERE sloupce KVALIFIKOVANE "bt." od
    # zacatku (ne dodatecnym string-replace) - incoming_documents (viz
    # LEFT JOIN nize) ma taky sloupec "amount_czk", bez prefixu by MySQL
    # dotaz odmitl jako nejednoznacny.
    where, params = [], []
    if direction in ("prijem", "vydaj"):
        where.append("bt.direction=%s")
        params.append(direction)
    if q:
        like = f"%{q}%"
        where.append(
            "(bt.variable_symbol LIKE %s OR bt.counter_account LIKE %s OR "
            "bt.counter_account_name LIKE %s OR bt.message_for_recipient LIKE %s OR bt.comment LIKE %s)"
        )
        params += [like, like, like, like, like]
    if amount:
        try:
            where.append("bt.amount_czk = %s")
            params.append(float(amount))
        except ValueError:
            return jsonify({"error": "Neplatná částka."}), 400
    if amount_from:
        try:
            where.append("bt.amount_czk >= %s")
            params.append(float(amount_from))
        except ValueError:
            return jsonify({"error": "Neplatná částka (od)."}), 400
    if amount_to:
        try:
            where.append("bt.amount_czk <= %s")
            params.append(float(amount_to))
        except ValueError:
            return jsonify({"error": "Neplatná částka (do)."}), 400
    if date_from:
        where.append("bt.transaction_date >= %s")
        params.append(date_from)
    if date_to:
        where.append("bt.transaction_date <= %s")
        params.append(date_to)

    # LEFT JOIN na incoming_documents - u odchozich plateb spojenych s
    # prijatym dokladem (potvrzeno adminem, viz api/incoming_documents.py)
    # ukaze proklik na dany doklad (Robert pres bot3: "v Bankovnich
    # vypisech videt propojeni oboma smery").
    sql = ("SELECT bt.*, doc.id AS linked_incoming_document_id, doc.supplier_name AS linked_incoming_document_supplier "
           "FROM bank_transactions bt "
           "LEFT JOIN incoming_documents doc ON doc.paid_bank_transaction_id = bt.id")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY bt.transaction_date DESC, bt.id DESC LIMIT 300"

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            # bot10, 2026-08-22: soucet respektuje aspon "direction" (jinak
            # by se prijate a odchozi castky scitaly dohromady jako by byly
            # stejneho smeru - amount_czk je vzdy kladne, viz _upsert_transactions)
            if direction in ("prijem", "vydaj"):
                cur.execute(
                    "SELECT COUNT(*) AS n, COALESCE(SUM(amount_czk),0) AS total FROM bank_transactions WHERE direction=%s",
                    (direction,),
                )
            else:
                cur.execute("SELECT COUNT(*) AS n, COALESCE(SUM(amount_czk),0) AS total FROM bank_transactions")
            summary = cur.fetchone()
    finally:
        conn.close()
    return jsonify({
        "transactions": [_serialize(r) for r in rows],
        "total_count": summary["n"],
        "total_amount_czk": float(summary["total"]),
    })


@app.get("/api/admin/bank-transactions/sync-status")
@require_permission("bankovni_vypisy", "zobrazit")
def bank_transactions_sync_status():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT last_synced_date, last_sync_at, last_sync_status, last_sync_error, last_sync_count "
                "FROM bank_sync_state WHERE id=1"
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"configured": bool(_fio_token())})
    return jsonify({
        "configured": bool(_fio_token()),
        "last_synced_date": row["last_synced_date"].isoformat() if row["last_synced_date"] else None,
        "last_sync_at": row["last_sync_at"].isoformat() if row["last_sync_at"] else None,
        "last_sync_status": row["last_sync_status"],
        "last_sync_error": row["last_sync_error"],
        "last_sync_count": row["last_sync_count"],
    })


@app.get("/api/admin/bank-transactions/partial-payments")
@require_permission("bankovni_vypisy", "zobrazit")
def bank_transactions_partial_payments():
    """Bod 10 varianta b (bot3/Robert, 2026-09-03) - trvala viditelnost
    objednavek, kde soucet napojenych CZK plateb NEDOSAHUJE total_czk
    (tolerance 1 Kc), misto jen jednorazoveho alertu po syncu. Cisty GET
    bez vedlejsich ucinku - find_partial_payments() nic nezapisuje."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            partial = find_partial_payments(cur)
    finally:
        conn.close()
    return jsonify({"partial_payments": partial})


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_iso_date(value):
    """Prisna kontrola vstupniho data z JSON (bot16, 2026-09-02, revize bot3):
    None/"" -> None (= vychozi obdobi), jinak musi byt string YYYY-MM-DD
    a realne datum. Vraci (date|None, error|None). Neoverena hodnota
    driv sla primo do FIO URL (periods/<token>/<from>/<to>) a do
    bank_sync_state.last_synced_date."""
    if value is None or value == "":
        return None, None
    if not isinstance(value, str) or not _ISO_DATE_RE.match(value):
        return None, "Neplatné datum, očekávám formát YYYY-MM-DD."
    try:
        return datetime.date.fromisoformat(value), None
    except ValueError:
        return None, "Neplatné datum, očekávám formát YYYY-MM-DD."


@app.post("/api/admin/bank-transactions/sync")
@require_permission("bankovni_vypisy", "upravit")
def bank_transactions_sync():
    body = request.get_json(silent=True) or {}
    date_from, err = _parse_iso_date(body.get("date_from"))
    if err:
        return jsonify({"status": "chyba", "error": f"date_from: {err}"}), 400
    date_to, err = _parse_iso_date(body.get("date_to"))
    if err:
        return jsonify({"status": "chyba", "error": f"date_to: {err}"}), 400
    if date_from and date_to and date_from > date_to:
        return jsonify({"status": "chyba", "error": "date_from nesmí být později než date_to."}), 400
    result = sync_fio_transactions(
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
    )
    admin = current_user()
    log_audit(admin["id"], "sync", "bank_transactions", None, result.get("status"))
    if result.get("status") != "ok":
        return jsonify(result), 400
    return jsonify(result)


@app.post("/api/admin/bank-transactions/rematch")
@require_permission("objednavky", "zobrazit")
def bank_transactions_rematch():
    """Robert primo (pres bot3, 2026-09-17): "pri kazdem otevreni sekce
    Objednavky se ma spustit kontrola uhrad proti vypisum." ZAMERNE
    NEVOLA FIO API vubec (na rozdil od /sync vyse) - jen spusti
    match_bank_payments_to_orders() nad UZ STAZENYMI daty v
    bank_transactions, cisty lokalni DB dotaz/parovani. Modulova
    hlavicka: FIO doporucuje min. 30s mezi dotazy na stejny token,
    volani pri KAZDEM otevreni Objednavek by ho casto porusilo -
    tenhle endpoint se toho netyka, protoze na FIO vubec nesahne.

    Opravneni zamerne "objednavky/zobrazit", ne "bankovni_vypisy/*" -
    spoustecem je prohlizeni Objednavek, ne akce nad bankovnimi vypisy
    samotnymi; kdokoli smi videt Objednavky, smi vyvolat i tenhle
    pasivni prepocet.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            match_result = match_bank_payments_to_orders(cur)
        conn.commit()
    finally:
        conn.close()
    # Stejny vzor jako sync_fio_transactions() - side-effekty (log_audit +
    # automaticky e-mail) az PO commitu/close, viz komentar tamtez.
    for doc in match_result["auto_issued"]:
        import documents
        log_audit(None, "create", "document_payment_tax", doc["document_id"], doc["document_number"])
        documents._auto_email_after_issue(doc["order_id"], doc["document_id"])
    return jsonify({
        "status": "ok",
        "matched": match_result["matched"],
        "amount_warnings": match_result["amount_warnings"],
        "auto_issued": match_result["auto_issued"],
        "vs_conflicts": match_result["vs_conflicts"],
        "partial_payments": match_result["partial_payments"],
    })
