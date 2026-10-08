#!/usr/bin/env python3
"""Zdroj k prekladu ZAKAZNICKYCH SABLON (e-maily objednavek a dokladu, popisky PDF dokladu) do en / it: docs/web_jazyky/12_sablony.json (bot5, 2026-10-08; zadani bot7 + Robert: IT/EN web jen firmam).

Format polozky stejny jako ostatni sesity: {id "sablona:<soubor>:<klic>", typ "text", cs, en, it, h, [zmena]}; promenne zustavaji ve slozenych zavorkach ({order_number}), preklad je nesmi menit.
Texty sablon jsou v kodu (api/orders.py, api/emails.py, api/documents.py); tenhle skript drzi jejich PREHLED a kontroluje, ze kazdy staticky kus textu v kodu porad je doslova (zmena v kodu bez zmeny
tady = skript skonci chybou, ať se sesit neztrati ze zdroje). Opakovane spusteni je bezpecne: hotove preklady a rucni upravy zustanou, zmenena cestina dostane "zmena": true, zmizele polozky se vypisou.
VAT_ZERO_NOTE (dolozka DPH 0 %) tu NENI - jeji zneni potvrzuje ucetni. Radky e-mailu s odsazenim ("  - ...") maji v sesitu bez odsazeni, kod ho pridava.

Pouziti (z korene repa, DB neni potreba, nic nezapisuje mimo docs/web_jazyky/12_sablony.json):
  api/venv/bin/python3 scripts/web_jazyk_sablony.py [--jen-kontrola]
Pridani sablony: radek do SABLONY nize (id, cesta k souboru s textem, cs s {promennymi}); kontrola kodu probehne sama.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from web_jazyk_zdroj import hsh, nacti, JAZYKY  # noqa: E402  (stejny zpusob hashovani a slevani jako u ostatnich sesitu)

VYSTUP = os.path.join(ROOT, "docs", "web_jazyky", "12_sablony.json")
O, E, D = "api/orders.py", "api/emails.py", "api/documents.py"

# (id po "sablona:", soubor s textem, cs) - poradi = poradi v sesitu
SABLONY = [
    # ---- potvrzeni objednavky (orders.py::_order_confirmation_email_body, _send_order_emails) ----
    ("orders.py:potvrzeni_predmet", O, "Potvrzení přijetí objednávky {order_number}"),
    ("orders.py:pozdrav", O, "Dobrý den,"),
    ("orders.py:potvrzeni_uvod", O, "děkujeme za Vaši objednávku {order_number}. Aktuální stav: {status}."),
    ("orders.py:potvrzeni_polozky", O, "Položky objednávky:"),
    ("orders.py:potvrzeni_radek", O, "- {name} × {qty} {unit}{unit_note} = {line_total} Kč"),
    ("orders.py:jednotka_ks", O, "ks"),
    ("orders.py:potvrzeni_celkem", O, "Celkem: {total} Kč"),
    ("orders.py:potvrzeni_nedostatek", O, "Upozorňujeme, že u níže uvedených položek aktuálně nemáme dostatek skladu. Doobjednáváme je u dodavatele a přesný termín dodání Vám upřesníme v nejbližší době:"),
    ("orders.py:potvrzeni_dalsi_kroky", O, "Ozveme se Vám s dalšími kroky."),
    ("orders.py:podpis", O, "S pozdravem,"),
    # ---- zmena stavu objednavky (orders.py::_status_change_email_body, STATUS_LABELS_CZ) ----
    ("orders.py:stav_predmet", O, "Změna stavu objednávky {order_number}"),
    ("orders.py:stav_text", O, "stav Vaší objednávky {order_number} se změnil na: {status}."),
    ("orders.py:stav:nova", O, "Nová"),
    ("orders.py:stav:potvrzena", O, "Potvrzená"),
    ("orders.py:stav:ceka_na_zbozi", O, "Čeká na zboží"),
    ("orders.py:stav:pripravit", O, "Připravit"),
    ("orders.py:stav:expedovana", O, "Expedovaná"),
    ("orders.py:stav:fakturovana", O, "Fakturovaná"),
    ("orders.py:stav:zrusena", O, "Zrušená"),
    # ---- e-mail k dokladu (emails.py::default_subject_body_for_document) ----
    ("emails.py:doklad_predmet", E, "{label} č. {document_number} - objednávka {order_number}"),
    ("emails.py:pozdrav_jmeno", E, "Dobrý den, {first_name},"),
    ("emails.py:doklad_uvod", E, "v příloze Vám zasíláme {label_lower} č. {document_number} k objednávce č. {order_number}."),
    ("emails.py:doklad_k_uhrade", E, "K úhradě: {amount_due}"),
    ("emails.py:doklad_splatnost", E, ", splatnost do {due_date}."),
    ("emails.py:doklad_zaloha_neplatit", E, "Tento doklad slouží pouze jako potvrzení přijaté platby - prosím NEPLAŤTE jej."),
    ("emails.py:doklad_dodaci_list", E, "Zásilka byla předána k expedici - v příloze najdete dodací list s přehledem dodaných položek."),
    # ---- rucni potvrzeni objednavky z adminu (emails.py::_default_subject_body_order_confirmation) ----
    ("emails.py:potvrzeni_predmet", E, "Potvrzení objednávky č. {order_number} - LOGIMAN s.r.o."),
    ("emails.py:potvrzeni_uvod", E, "děkujeme za Vaši objednávku č. {order_number}."),
    ("emails.py:potvrzeni_radek", E, "- {name} × {qty} ks{unit_note} = {line_total}"),
    ("emails.py:potvrzeni_celkem", E, "Celkem: {total}"),
    # ---- nazvy dokladu (documents.py::DOCUMENT_TYPE_LABELS; v predmetu e-mailu, nadpisu PDF) ----
    ("documents.py:typ:proforma_invoice", D, "Zálohová faktura"),
    ("documents.py:typ:payment_tax_document", D, "Daňový doklad k přijaté platbě"),
    ("documents.py:typ:invoice", D, "Faktura - Daňový doklad"),
    ("documents.py:typ:delivery_note", D, "Dodací list"),
    ("documents.py:typ:credit_note", D, "Dobropis"),
    # ---- PDF dokladu (documents.py::render_document_pdf): bloky stran ----
    ("documents.py:pdf:dodavatel", D, "Dodavatel:"),
    ("documents.py:pdf:prijemce", D, "Příjemce:"),
    ("documents.py:pdf:odesilatel", D, "Odesílatel:"),
    ("documents.py:pdf:dorucovaci_adresa", D, "Doručovací adresa: {address}"),
    ("documents.py:pdf:ico", D, "IČ: {ico}"),
    ("documents.py:pdf:dic", D, "DIČ: {dic}"),
    ("documents.py:pdf:tel", D, "Tel: {phone}"),
    ("documents.py:pdf:email", D, "E-mail: {email}"),
    ("documents.py:pdf:cislo_uctu", D, "Číslo účtu: {bank_account}"),
    # ---- PDF: hlavicka dokladu ----
    ("documents.py:pdf:variabilni_symbol", D, "Variabilní symbol: {variable_symbol}"),
    ("documents.py:pdf:forma_uhrady", D, "Forma úhrady: {payment_method_label}"),
    ("documents.py:pdf:datum_vystaveni", D, "Datum vystavení: {issue_date}"),
    ("documents.py:pdf:datum_splatnosti", D, "Datum splatnosti: {due_date}"),
    ("documents.py:pdf:datum_zdanitelneho_plneni", D, "Datum zdanitelného plnění"),
    ("documents.py:pdf:datum_dodani", D, "Datum dodání"),
    ("documents.py:pdf:cislo_objednavky", D, "Číslo objednávky: {reference}"),
    # ---- PDF: tabulka polozek a soucty ----
    ("documents.py:pdf:polozka", D, "Položka"),
    ("documents.py:pdf:polozky_dodavky", D, "Položky dodávky"),
    ("documents.py:pdf:mnozstvi", D, "Množství"),
    ("documents.py:pdf:cena_za_mj", D, "Cena za m.j."),
    ("documents.py:pdf:cena", D, "Cena"),
    ("documents.py:pdf:cena_celkem", D, "Cena celkem"),
    ("documents.py:pdf:cena_bez_dph", D, "Cena bez DPH"),
    ("documents.py:pdf:celkova_cena_vc_dph", D, "Celková cena vč. DPH"),
    ("documents.py:pdf:celkem_vc_dph", D, "Celkem vč. DPH"),
    ("documents.py:pdf:celkem", D, "Celkem"),
    ("documents.py:pdf:dph_procenta", D, "DPH %"),
    ("documents.py:pdf:dph", D, "DPH"),
    ("documents.py:pdf:bez_dph", D, "bez DPH"),
    ("documents.py:pdf:sazba_dph", D, "Sazba DPH"),
    ("documents.py:pdf:soucet_dph", D, "Součet DPH:"),
    ("documents.py:pdf:shrnuti", D, "Shrnutí"),
    ("documents.py:pdf:zaokrouhleni", D, "Zaokrouhlení"),
    ("documents.py:pdf:vyse_zalohy", D, "Výše zálohy"),
    ("documents.py:pdf:uhrazena_zaloha", D, "Uhrazená záloha - Kód: {advance_document_number}"),
    ("documents.py:pdf:k_zaplaceni", D, "K ZAPLACENÍ"),
    ("documents.py:pdf:neplatte", D, "NEPLAŤTE!"),
    # ---- PDF: podpisy a pata ----
    ("documents.py:pdf:vydal", D, "Vydal:"),
    ("documents.py:pdf:vystavil", D, "Vystavil: {issued_by}"),
    ("documents.py:pdf:prevzal", D, "Převzal(a):"),
    ("documents.py:pdf:podpis_datum", D, "podpis, datum"),
    ("documents.py:pdf:paticka", D, "Vystaveno systémem konfigurátoru logiman.cz"),
]


def kontrola_kodu():
    """Kazdy staticky kus textu (mimo {promenne}) musi byt v kodu doslova. -> seznam (id, kus) ktere v kodu chybi."""
    zdroje, chyby = {}, []
    for ident, soubor, cs in SABLONY:
        if soubor not in zdroje:                         # sousedici retezce v kodu ("..." "...") se pro kontrolu spoji do jednoho
            zdroje[soubor] = re.sub(r'"\s*\n\s*(?:f)?"', "", open(os.path.join(ROOT, soubor), encoding="utf-8").read())
        for kus in re.split(r"\{[a-z_]+\}", cs):
            kus = kus.strip()
            if len(kus) >= 2 and kus not in zdroje[soubor]:
                chyby.append((ident, kus))
    return chyby


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--jen-kontrola", action="store_true", help="jen zkontroluje, ze texty jsou v kodu; sesit nepise")
    ap.add_argument("--vystup", default=VYSTUP)
    a = ap.parse_args(argv)
    ids = [i for i, _, _ in SABLONY]
    if len(ids) != len(set(ids)):
        print("CHYBA: duplicitni id v SABLONY:", sorted({i for i in ids if ids.count(i) > 1}))
        return 2
    chyby = kontrola_kodu()
    if chyby:
        print("CHYBA: text sablony uz v kodu neni doslova (zmenil se zdroj? uprav SABLONY):")
        for i, k in chyby:
            print("  sablona:%s: %r" % (i, k))
        return 1
    if a.jen_kontrola:
        print("OK: %d sablon, vsechny texty jsou v kodu" % len(SABLONY))
        return 0
    stare = nacti(a.vystup)
    ven, nove, zmeny = [], 0, 0
    for ident, _soubor, cs in SABLONY:
        pid = "sablona:" + ident
        s = stare.pop(pid, None)
        if s is None:
            ven.append({"id": pid, "typ": "text", "cs": cs, "en": "", "it": "", "h": ""})
            nove += 1
            continue
        o = {"id": pid, "typ": "text", "cs": cs}
        for j in JAZYKY:
            o[j] = s.get(j, "")
        prelozeno = any(o[j] for j in JAZYKY)
        o["h"] = s.get("h", "") if prelozeno else ""
        if prelozeno and o["h"] and o["h"] != hsh(cs):
            o["zmena"] = True
            zmeny += 1
        elif s.get("zmena") and o["h"] == hsh(cs):
            pass
        ven.append(o)
    if stare:
        print("ZASTARALE: " + ", ".join(list(stare)[:8]) + (" ..." if len(stare) > 8 else ""))
    with open(a.vystup, "w", encoding="utf-8") as f:
        json.dump(ven, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("12_sablony: %d polozek, %d znaku cs (nove %d, zmenene cs %d, zastarale %d)" % (len(ven), sum(len(p["cs"]) for p in ven), nove, zmeny, len(stare)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
