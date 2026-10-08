"""
Nabidka ze sceny (Robert, 2026-08-04): "pridej do sceny na pravy panel
tlacitko Nabidka - system vygeneruje nabidku v PDF - hlavicka firmy,
kontakty, cislo nabidky (zaloz cislovani), nabidky se budou ukladat na
sdilenem disku do Nabidek - technicka cast: naryscasu/bokorys/pudorys
jako kotovane vykresy + 2x 3D pohled ze sceny, popis, cenova tabulka +
celkova cena. Styl: 'modernejsi jakoby stylu html5' / 'jako letak' /
'jako prezentace'".

Rozhodnuti Roberta (AskUserQuestion, 2026-08-04):
  - cislovani SDILENE s CRM Nabidkami (crm_quotes) - stejna rada
    quotes.py::_next_quote_number()/QUOTE_PREFIX ("RM####"), aby cisla
    nekolidovala a byl to poznatelne stejny koncept "Nabidka" v cele
    appce. TATO nabidka NEVYTVARI radek v crm_quotes (nepatri ke
    konkretnimu leadu/obchodu) - jen si pujcuje stejne pocitadlo.
  - ulozeni: existujici Sdileny disk (drive.py, shared_drive_folders/
    shared_drive_files), do slozky "Nabidky" (vytvorena uz drive
    vzorem vzor1 - viz AGENTS_LOG.md).

Render: WeasyPrint (HTML+CSS, nove pridano do api/venv +
requirements.txt) misto ReportLab tabulek pouzivanych v documents.py -
Robert vyslovne chtel modernejsi/letakovy/prezentacni vzhled, ktery se
v ReportLabovych primitivech delal spatne. Font Roboto (apt
fonts-roboto) - viz vzorova sablona "vzor1" v Nabidkach.

Technicke pohledy (narys/bokorys/pudorys + 2x 3D) generuje FRONTEND
(scene.html) - kazdy je canvas.toDataURL() snimek z three.js sceny
(preserveDrawingBuffer:true na rendereru), pro ortho pohledy s KOTAMI
DOKRESLENYMI primo do snimku (frontend prekresli renderer.domElement
do pomocneho 2D <canvas> a nad nej vykresli kotovaci cary+text ze
stejnych dat jako HTML overlay #dimLabels/updateDimLabelPositions() -
jinak by kotovaci popisky, ktere jsou samostatny HTML overlay MIMO
WebGL canvas, ve snimku vubec nebyly videt). Backend jen prijme
hotove PNG/JPEG data URI a vlozi je do PDF - zadna geometrie se tu
nepocita.

Editovatelny text (Robert: "editovatelne pro text"): _load_editable_text()
cte AKTUALNI obsah souboru "vzor1_sablona_textu.html" ulozeneho v
"Nabidky" slozce Sdileneho disku (viz app.py::drive.py) - pokud ho
Robert prepise (stahne, upravi, znovu nahraje pres UI Sdileneho disku
se stejnym nazvem souboru), dalsi generovane nabidky uz pouziji jeho
text. Zadna zavislost na konkretnim file_id - hleda se podle NAZVU
souboru uvnitr slozky "Nabidky", takze nahrazeni souboru funguje bez
nutnosti menit kod.
"""
import os
import re
import base64
import io
import json
import secrets
import hashlib
import uuid
import shutil
import datetime
import time
import urllib.request
import urllib.error

import pymysql

from flask import request, jsonify, Response, session

from app import app, get_conn, require_permission, current_user, log_audit, get_pagination_args, paginated_query, parse_bulk_ids, get_setting, APP_BASE_URL, _rate_limited, send_email, KATALOG_GLB_DIR
from documents import SUPPLIER, VAT_RATE, SPAYD_CURRENCY_CODE
from quotes import safe_stored_filename, _next_quote_number, QUOTE_PREFIX, PRIVATE_FILES_DIR
from drive import DRIVE_FILES_DIR
# Robert ("stisk toptransu... vypsat živou cenu") - stejny vypocet ceny
# Toptrans (PSC + hmotnost) jako v e-shop kosiku, viz
# public_offer_toptrans_price() nize.
from orders import _resolve_toptrans_price, _OrderCreateError, create_order_from_scene_offer
from product_assemblies import _montaz_mista_map
try:                                       # pricky do multiboxu (bot8, 2026-10-07): chybejici / vadny 3D modul nesmi shodit import nabidek (viz test_import v 3D testech)
    import v3d_glb
except Exception:                          # noqa: BLE001
    v3d_glb = None
try:
    import nabidka_pricky
except Exception:                          # noqa: BLE001
    nabidka_pricky = None

try:
    from weasyprint import HTML
except ImportError:
    HTML = None  # appka nesmi spadnout, pokud weasyprint chybi - endpoint jen vrati chybu

NABIDKY_FOLDER_NAME = "Nabídky"
EDITABLE_TEXT_FILENAME = "vzor1_sablona_textu.html"

# Interaktivni online nabidka (Robert 2026-08-04, viz AGENTS_LOG.md pro
# cely kontext planu) - DRUHA forma evidence vedle uz existujiciho
# statickeho PDF vyse. Obrazky snimku se ukladaji SAMOSTATNE (mimo
# nginx docroot, stejny princip jako DRIVE_FILES_DIR/QUOTE_FILES_DIR),
# aby je verejna stranka mohla nacist jednotlive (PDF vyse je porad
# jeden blob, nehodi se pro interaktivni prochazeni po strankach).
OFFER_IMAGES_DIR = os.path.join(PRIVATE_FILES_DIR, "scene-offer-images")
os.makedirs(OFFER_IMAGES_DIR, exist_ok=True)

# Zivy 3D model (Robert: "3D model ne jako nahledy ale rovnou jako zivy
# model") - NEPOSILA se v ramci hlavniho POSTu nize (nginx
# client_max_body_size je 10M/20M podle vhostu, uz ted tam jsou 4
# obrazky) - nahraje se SAMOSTATNYM pozadavkem az PO zalozeni nabidky
# (viz admin_scene_offer_upload_model nize). Selhani exportu/uploadu na
# frontendu nesmi ohrozit hlavni tok (PDF+obrazky vzniknou vzdy).
OFFER_MODELS_DIR = os.path.join(PRIVATE_FILES_DIR, "scene-offer-models")
os.makedirs(OFFER_MODELS_DIR, exist_ok=True)
MAX_MODEL_BYTES = 15 * 1024 * 1024  # bezpecna rezerva pod nginx limitem (10M/20M)

OFFER_LINK_VALIDITY_DAYS = 30  # stejna doba jako "Platnost nabidky do" v PDF vyse

# Poradi a klice "slidu" - MUSI odpovidat poradi <div class="slide"> v
# _render_offer_html nize (cover/intro/2x vykresy/3D/cenik/zaver).
# page_key (ne jen index) je citelny a stabilni i kdyby se poradi/pocet
# slidu v budoucnu zmenil - historicke udaje zustanou dohledatelne podle
# jmena, ne podle pozice.
# "renders" (Robert 2026-08-11: "kdyz se mi budou libit, chci nekde
# odkliknout ano maji byt soucasti nabidky a pripoji se tim do nabidky na
# novou stranku mezi 3D model a cenovou nabidku") - stranka existuje jen
# tehdy, kdyz ma nabidka aspon jeden schvaleny render; klic tu je vzdy,
# aby proslo overovani page_key u statistik prohlizeni.
# "drawings_vandr" (bot16, 2026-10-07, Robert: v nabidce z Vandr karty chybelo zakreslovani zmen): stranka "Technicke vykresy" u nabidek z Vandr karty
# (nabidka-online.html ji nahrazuje drawings_1+drawings_2). Frontend ji posila jako page_key u /event (statistiky), u "Dotazu" (note) i u znacek (markups);
# dokud tu nebyla, backend ji odmital 400 a v admin statistikach (by_page) chybela. Sloupce page_key v DB jsou varchar(30), zadny DDL.
OFFER_PAGE_KEYS = ("cover", "intro", "drawings_1", "drawings_2", "drawings_vandr", "view_3d",
                   "renders", "pricing", "closing")

# Mapovani JSON klice z payloadu (views_in) <-> DB sloupec scene_offers
# <-> pripona souboru na disku - jeden zdroj pravdy na vsech mistech.
# narys_ghost/bokorys_ghost/pudorys_ghost (Robert: "2D pohledy... drateny
# a ghosted") - druhy styl stejnych 3 pohledu, viz sql/2026-08-09_offer_
# ghost_views.sql. NEPOVINNE (na rozdil od zbytku) - stare nabidky je
# nemaji, viz _validate_data_uri volani nize (jen kdyz je hodnota poslana).
OFFER_VIEW_KEYS = {
    "narys": "view_narys", "bokorys": "view_bokorys", "pudorys": "view_pudorys",
    "narys_ghost": "view_narys_ghost", "bokorys_ghost": "view_bokorys_ghost", "pudorys_ghost": "view_pudorys_ghost",
    "view3d_a": "view_3d_a", "view3d_b": "view_3d_b",
}

# Fallback, pokud sablona textu na disku (zatim) neexistuje nebo se
# nepodarilo naparsovat - stejny text jako v puvodni vzorove sablone.
DEFAULT_EDITABLE_TEXT = {
    "popis": (
        "Na základě Vaší poptávky Vám předkládáme cenovou nabídku na konstrukci z "
        "hliníkových stavebnicových profilů dle přiloženého 3D návrhu. Veškeré "
        "rozměry odpovídají uvedeným kótám."
    ),
    "patka": (
        "Nabídka je platná 30 dní od data vystavení. Ceny jsou uvedeny bez DPH "
        "i včetně DPH 21 %. "
        "Platební podmínky a dodací lhůta budou upřesněny po odsouhlasení nabídky."
    ),
}

MAX_IMAGE_BYTES = 6 * 1024 * 1024  # 6 MB/obrazek - bezpecnostni strop proti zneuziti endpointu
DATA_URI_RE = re.compile(r"^data:image/(png|jpeg);base64,(?P<b64>[A-Za-z0-9+/=]+)$")


def _validate_data_uri(value, field_name):
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: chybí obrázek.")
    m = DATA_URI_RE.match(value.strip())
    if not m:
        raise ValueError(f"{field_name}: neplatný formát obrázku (očekáván data:image/png|jpeg;base64,...).")
    # Rovnou i zvaliduje, ze je to skutecne dekodovatelny base64 (ne jen
    # spravny prefix) - garbage by jinak WeasyPrint tise vykreslil jako
    # prazdny obrazek misto chyby.
    try:
        raw = base64.b64decode(m.group("b64"), validate=True)
    except Exception:
        raise ValueError(f"{field_name}: obrázek se nepodařilo dekódovat.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(f"{field_name}: obrázek je příliš velký (max {MAX_IMAGE_BYTES // (1024*1024)} MB).")
    return value.strip()


def _ensure_nabidky_folder(cur):
    cur.execute(
        "SELECT id FROM shared_drive_folders WHERE parent_folder_id IS NULL AND name=%s",
        (NABIDKY_FOLDER_NAME,),
    )
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        "INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (NULL,%s,NULL)",
        (NABIDKY_FOLDER_NAME,),
    )
    return cur.lastrowid


def _load_editable_text(cur, folder_id):
    cur.execute(
        "SELECT stored_filename FROM shared_drive_files WHERE folder_id=%s AND filename=%s "
        "ORDER BY id DESC LIMIT 1",
        (folder_id, EDITABLE_TEXT_FILENAME),
    )
    row = cur.fetchone()
    if not row:
        return dict(DEFAULT_EDITABLE_TEXT)
    path = os.path.join(DRIVE_FILES_DIR, row["stored_filename"])
    try:
        with open(path, encoding="utf-8") as f:
            html = f.read()
    except OSError:
        return dict(DEFAULT_EDITABLE_TEXT)
    result = dict(DEFAULT_EDITABLE_TEXT)
    for key in ("popis", "patka"):
        m = re.search(rf'<div class="editable" id="{key}">(.*?)</div>', html, re.DOTALL)
        if m:
            result[key] = m.group(1).strip()
    return result


def _fmt_czk(v):
    try:
        return f"{float(v):,.0f} Kč".replace(",", " ")
    except (TypeError, ValueError):
        return "0 Kč"


def _sanitize_montaz_pct(raw):
    """Sazba montaze v % z ceny nabidky: cislo 0-100 (na 2 desetinna mista), jinak None (= bez vlastni volby, plati vychozi
    sazba z nastaveni). Retezec s carkou se bere (formular), bool ne (v Pythonu je to int)."""
    if raw is None or isinstance(raw, bool) or raw == "":
        return None
    try:
        val = float(raw.replace(",", ".")) if isinstance(raw, str) else float(raw)
    except (TypeError, ValueError):
        return None
    if val != val or val < 0 or val > 100:      # NaN, zaporne, nesmyslne
        return None
    return round(val, 2)


def _sanitize_discount_pct(raw):
    """Sleva v % z ceny zbozi nabidky (Robert 2026-10-07: "chci v cenovem souhrnu online nabidky nabidnout slevu, i v te 0133 zpetne"): cislo vetsi nez 0 a nejvyse 100
    (2 desetinna mista, carka se bere), jinak None = bez slevy (prazdne, 0, bool, NaN, zaporne, nesmysl). Stejna pravidla jako _sanitize_montaz_pct, jen 0 = bez slevy."""
    val = _sanitize_montaz_pct(raw)
    return val if val else None


# bot16, 2026-09-14 (Robert primo, doslova): "na startu pri zadavani
# terminu dodani pridat tyto moznosti: volba platby ktera se nenabidne /
# volba vyse zalohy fixne dana / volba QR platbou / volba nechci
# kusovnik s zadnymi cenami, vlozeni individualni ceny." Rozsireni
# stavajiciho offer_options JSON (show_qr/delivery_term, Robert
# 2026-08-09) - SDILENY whitelist/sanitizer, aby create i update
# endpoint (driv 2 nezavisle kopie stejne logiky) nemohly casem
# rozjet. "volba QR platbou" = uz existujici show_qr, zadne nove pole.
#
# hide_bom_prices: kusovnik na verejne strance ztrati sloupce Cena/ks a
# Celkem (viz nabidka-online.html), total_price (uz dnes plne
# samostatny, admin-zadatelny sloupec - NENI dopocitavany server-side,
# viz admin_scene_offer_update nize) se v adminu prepne z auto-souctu
# polozek na rucne zadavane cislo - "vlozeni individualni ceny" presne
# timhle uz existujicim polem, zadne nove misto pro cislo neni potreba.
def _sanitize_offer_options(options_in):
    if not isinstance(options_in, dict):
        options_in = {}
    offer_options = {
        "show_qr": bool(options_in.get("show_qr", True)),
        "delivery_term": None,
        "hidden_payment_method": None,
        "fixed_deposit_pct": None,
        "hide_bom_prices": bool(options_in.get("hide_bom_prices", False)),
        "hidden_delivery_state": None,
        # bot5, 2026-09-28 (Robert primo: "stejne jako je volba montaze
        # (Praha/Slavicin) na eshopu v detailu sestav, tataz volba
        # montaze nech je v online nabidce... pokud je v nabidce sestava
        # do auta") - RUCNI admin prepinac (zadny spolehlivy signal
        # "je to auto" v datech sceny/nabidky neexistuje - offer["items"]
        # jsou proste BOM radky, karoserie mezi nimi neni odlisena),
        # stejny vzor jako hide_bom_prices vyse. Kdyz true, nabidka-
        # online.html misto "Dodani ve stavu" nabidne Montaz (+cena,
        # montaz_pct z app_settings, viz public_offer_get) a Misto
        # montaze (/api/montaz-mista, stejny katalog jako product.html).
        "is_vehicle_assembly": bool(options_in.get("is_vehicle_assembly", False)),
        # Rucni prebiti automaticke Toptrans ceny KONKRETNE pro "Dodani
        # ve stavu: Smontovano" (Robert primo: "je potreba rucne zadat
        # castku za dopravu při smontovanem stavu, ktera přebije
        # automatickou cenu Toptransu") - jen kdyz NENI is_vehicle_
        # assembly (u sestavy do auta se "Dodani ve stavu" vubec
        # nenabizi, viz vyse). Kc BEZ DPH (stejna jednotka jako
        # toptrans_price_czk/offer["total_price"]), None = zadne
        # prebiti, pouzije se dal automaticky vypocet jako dosud.
        "manual_assembled_shipping_czk": None,
        # bot5, 2026-10-01 (Robert primo: "montaz v online nabidce chci pred
        # vytvorenim nabidky zvolit jako % castku") - sazba montaze PRO TUTO
        # nabidku (% z ceny nabidky bez DPH, 0 = montaz se v nabidce vubec
        # nenabizi). None = bez vlastni volby -> plati vychozi sazba z
        # app_settings ZIVE, jako dosud (tak se chovaji vsechny nabidky
        # vytvorene driv + Vandr). Rozhoduje o ni JEN _offer_montaz_pct
        # (verejny payload, QR platba i vznikla objednavka).
        "montaz_pct": _sanitize_montaz_pct(options_in.get("montaz_pct")),
        # bot16, 2026-10-07 (Robert: "nabidnout slevu v cenovem souhrnu online nabidky, i v te 0133 zpetne"): sleva v % z ceny ZBOZI (bez dopravy a montaze), None = bez
        # slevy. Rozhoduje o ni JEN _offer_discount_pct / _offer_discount_net (verejny payload, QR platba, objednavka a e-mail, montaz se pocita z ceny PO sleve).
        "discount_pct": _sanitize_discount_pct(options_in.get("discount_pct")),
    }
    term = options_in.get("delivery_term")
    if isinstance(term, str) and term.strip():
        offer_options["delivery_term"] = term.strip()[:255]
    # Ktera z voleb platby (viz PAYMENT_METHOD_CHOICES/scene_offer_order_
    # prefs.payment_method) se zakaznikovi NENABIDNE - napr. kdyz Logiman
    # u konkretni nabidky nechce dobirku. Whitelist na existujici hodnoty,
    # at se do DB nedostane libovolny retezec.
    hpm = options_in.get("hidden_payment_method")
    if hpm in ("dobirka", "zaloha"):
        offer_options["hidden_payment_method"] = hpm
    # Fixni % zalohy (misto posuvniku 50-100 % volitelneho zakaznikem) -
    # stejne meze jako u zakaznikem voleneho deposit_pct (viz
    # admin_scene_offer_update_order_prefs nize).
    fdp = options_in.get("fixed_deposit_pct")
    if fdp is not None:
        try:
            fdp = int(fdp)
        except (TypeError, ValueError):
            fdp = None
        if fdp is not None and 50 <= fdp <= 100:
            offer_options["fixed_deposit_pct"] = fdp
    # Stav dodani, ktery se zakaznikovi NENABIDNE (Robert primo,
    # 2026-09-14: "urcit nemoznost zvolit si smontovano/rozlozeno") -
    # stejny vzor jako hidden_payment_method vyse, whitelist na stejne
    # hodnoty jako delivery_state ma v _load_order_prefs (radek 1894).
    hds = options_in.get("hidden_delivery_state")
    if hds in ("smontovano", "demontovano"):
        offer_options["hidden_delivery_state"] = hds
    masc = options_in.get("manual_assembled_shipping_czk")
    if masc is not None and masc != "":
        try:
            masc = float(masc)
        except (TypeError, ValueError):
            masc = None
        if masc is not None and masc >= 0:
            offer_options["manual_assembled_shipping_czk"] = round(masc, 2)
    # bot10, 2026-10-01: systemovy priznak Vandr nabidky (1 kotovany vykres
    # misto narys/bokorys/pudorys, viz api/vandr_scene_offers.py a
    # buildDeck v nabidka-online.html). Nastavuje ho JEN zalozeni Vandr
    # nabidky - tady se jen propusti dal, jinak by ho kazde prociseni
    # (napr. ulozeni rucni ceny dopravy) potichu smazalo a Vandr nabidka by
    # se prepla na 3 vykresy, z nichz 2 jsou u Vandru prazdne (NULL).
    if options_in.get("vandr_single_drawing") is True:
        offer_options["vandr_single_drawing"] = True
    # bot10, 2026-10-06: SPOLECNA Vandr nabidka z vice karet (leva + prava + prepazka, api/vandr_scene_offers.py) - jeden kotovany vykres ke kazde strane (slide
    # drawings_vandr v nabidka-online.html). Jen u Vandr nabidky (vandr_single_drawing), 2-3 ruzne znamé sloty a kratke popisky; neplatne = klic se zahodi cely (stranka
    # ukaze dosavadni jeden vykres, ne neuplny seznam). Stejne jako vandr_single_drawing ho admin formular neposila - admin_scene_offer_update ho bere z ulozeneho radku
    # (z tela pozadavku se nastavit neda); tady se jen propusti dal, aby ho nesmazalo prociseni ulozenych voleb (napr. rucni cena dopravy).
    # bot5, 2026-10-06 (Robert: Vandr 2D se jen prejima, nikdy nevyrabi): strana bez Vandr vykresu se z vykresu vynechava, takze u spolecne nabidky muze zbyt i JEDEN vykres (1-3)
    # a Vandr nabidka z karty, kde Vandr zadny kotovany vykres nema, nese vandr_bez_vykresu (stranka Vykresy se nezobrazuje); stejna pravidla pruchodu jako vandr_single_drawing
    if offer_options.get("vandr_single_drawing") and options_in.get("vandr_bez_vykresu") is True:
        offer_options["vandr_bez_vykresu"] = True
    kresby = options_in.get("vandr_drawings")
    if offer_options.get("vandr_single_drawing") and not offer_options.get("vandr_bez_vykresu") and isinstance(kresby, list) and 1 <= len(kresby) <= 3:
        platne = [{"slot": d["slot"], "label": d["label"].strip()[:40]} for d in kresby
                  if isinstance(d, dict) and d.get("slot") in ("narys", "bokorys", "pudorys") and isinstance(d.get("label"), str) and d["label"].strip()]
        if len(platne) == len(kresby) and len({d["slot"] for d in platne}) == len(platne):
            offer_options["vandr_drawings"] = platne
    return offer_options


OFFER_OPTIONS_DEFAULT = _sanitize_offer_options({})

# Nabidka z konfigurace stolu (api/nabidka_z_konfigurace.py): `source` + verejna cast `config` + SOUKROMA cast `config_private` (vyber, cenovy souhrn, hmotnost) v offer_options.
# Sanitize tyhle klice zamerne NEPROPOUSTI (z tela admin pozadavku se nastavit nedaji); uprava nabidky je zachova z ulozeneho radku (admin_scene_offer_update), verejny JSON
# soukromou cast odstrani.


def _je_auto_sestava(offer_options):
    """Sestava do AUTA (Robert 2026-10-06, "opravte to"): montaz v Praze / Slavicine (zvolena zakaznikem, vylucuje volbu dopravy) je JEN u sestav do aut - rucni priznak
    is_vehicle_assembly (scena a dalsi auto-sestavy) NEBO nabidka z Vandr karty (vandr_single_drawing: Vandr sestavy jsou vzdy do auta). NE u stolu (nabidka z konfigurace) ani ostatnich."""
    return isinstance(offer_options, dict) and bool(offer_options.get("is_vehicle_assembly") or offer_options.get("vandr_single_drawing"))


def _verejne_offer_options(options):
    """Volby nabidky pro VEREJNY JSON: bez soukrome casti snimku konfigurace (cenovy souhrn, hmotnost, vyber) a z verejne casti jen to, co zakaznik vidi
    (kod, ks, zeme dodani, souhrn voleb, neutralni kusovnik; ne hash, pravidla ani id karty)."""
    if isinstance(options, dict) and _je_auto_sestava(options) and not options.get("is_vehicle_assembly"):
        options = dict(options, is_vehicle_assembly=True)            # Vandr nabidky (i starsi, vytvorene bez priznaku) stranka bere jako sestavu do auta
    if isinstance(options, dict) and ("config_private" in options or "config" in options):
        options = {k: v for k, v in options.items() if k != "config_private"}
        cfg = options.get("config")
        if isinstance(cfg, dict):
            options["config"] = {k: cfg.get(k) for k in ("kod", "qty", "delivery_country", "souhrn", "bom", "pocet_spoju", "vykresy") if k in cfg}
    return options


def _verejna_konfigurace(options):
    """Verejna cast konfigurace pro stranku nabidky (offer.source === "configurator"): kod, souhrn voleb a neutralni kusovnik BEZ cen dilu, vyberu, hashe a hmotnosti."""
    cfg = options.get("config") if isinstance(options, dict) and options.get("source") == "configurator" else None
    if not isinstance(cfg, dict):
        return None
    # vykresy = nabidka ma kotovane 2D vykresy ze sceny (nahrane po vytvoreni, api/nabidka_z_konfigurace.py::/vykresy); stranka podle toho ukaze stranky Vykresy
    return {"kod": cfg.get("kod"), "summary": cfg.get("souhrn") or [], "bom": cfg.get("bom") or [], "vykresy": cfg.get("vykresy") is True}


def _render_offer_html(offer_number, items, total_price, views, editable_text, customer):
    today = datetime.date.today().strftime("%d. %m. %Y")
    valid_until = (datetime.date.today() + datetime.timedelta(days=30)).strftime("%d. %m. %Y")

    items_rows = "".join(f"""
      <tr>
        <td class="it-name">{it['name']}</td>
        <td class="it-dim">{it.get('dim') or '–'}</td>
        <td class="it-qty">{it.get('qty') or ''}</td>
        <td class="it-price">{_fmt_czk(it.get('unit_price'))}</td>
        <td class="it-total">{_fmt_czk(it.get('total'))}</td>
      </tr>""" for it in items)

    customer_name = (customer or {}).get("name") or "—"
    customer_note = (customer or {}).get("note") or ""

    return f"""<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<style>
@page {{ size: A4; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Roboto', 'DejaVu Sans', sans-serif; color: #1b2430; }}

.slide {{ width: 210mm; height: 297mm; position: relative; overflow: hidden; break-after: page; }}
.slide:last-child {{ break-after: auto; }}

.cover {{
  background: linear-gradient(135deg, #0f2138 0%, #16324f 55%, #1c4a6b 100%);
  color: #fff; padding: 26mm 22mm;
}}
.cover .eyebrow {{ font-size: 12pt; letter-spacing: 4px; text-transform: uppercase; color: #ff9a66; font-weight: 700; margin-bottom: 8mm; }}
.cover h1 {{ font-size: 46pt; font-weight: 900; line-height: 1.05; margin-bottom: 10mm; }}
.cover .offer-meta {{ font-size: 12pt; color: #cfe0ee; line-height: 1.9; margin-top: 14mm; }}
.cover .offer-meta b {{ color: #fff; }}
.cover .accent-bar {{ position: absolute; left: 0; bottom: 0; width: 100%; height: 10mm; background: linear-gradient(90deg, #ff7a3d, #ffb35c); }}
.cover .shape {{ position: absolute; border-radius: 50%; opacity: 0.12; background: #ffffff; }}
.cover .shape.s1 {{ width: 260mm; height: 260mm; right: -110mm; top: -140mm; }}
.cover .shape.s2 {{ width: 120mm; height: 120mm; right: 10mm; bottom: 20mm; background: #ff7a3d; opacity: 0.18; }}
.cover .brand {{ position: absolute; left: 22mm; bottom: 18mm; font-size: 13pt; font-weight: 700; letter-spacing: 1px; }}
.cover .brand .brand-logo {{ font-size: 20pt; font-weight: 800; letter-spacing: .01em; white-space: nowrap; }}
.cover .brand .brand-logo-hl {{ color: #e05a1c; }}
.cover .brand .brand-logo-lt {{ color: #e8eaed; }}

.content {{ padding: 18mm 20mm; }}
.content-wide {{ padding: 10mm 8mm; height: 100%; display: flex; flex-direction: column; }}
.content-wide .slide-title {{ flex-shrink: 0; }}
.slide-title {{ display: flex; align-items: baseline; gap: 6mm; margin-bottom: 10mm; }}
.slide-title .num {{ font-size: 30pt; font-weight: 900; color: #ff7a3d; }}
.slide-title h2 {{ font-size: 20pt; font-weight: 700; color: #16324f; }}
.slide-title .rule {{ flex: 1; height: 2px; background: #e2e8ee; margin-left: 4mm; }}

.intro-card {{ background: #f4f8fb; border-left: 5px solid #ff7a3d; border-radius: 4px; padding: 10mm 12mm; font-size: 12.5pt; line-height: 1.75; color: #2a3646; }}
.recipient-grid {{ display: flex; gap: 8mm; margin-top: 12mm; }}
.recipient-card {{ flex: 1; background: #ffffff; border: 1px solid #e2e8ee; border-radius: 6px; padding: 8mm; }}
.recipient-card .label {{ font-size: 9pt; text-transform: uppercase; letter-spacing: 2px; color: #ff7a3d; font-weight: 700; margin-bottom: 3mm; }}
.recipient-card .line {{ font-size: 11pt; line-height: 1.7; color: #2a3646; }}

/* Robert: "technicke vykresy musi vyplnovat 80% okna a okna 80%
   stranky" - karta (.view-card) proto vyplnuje skoro celou vysku
   stranky (flex:1 v ramci .content-wide, ktera uz sama zabira temer
   celou vysku .slide), a uvnitr karty samotny obrazek roztahujeme
   object-fit:contain uvnitr .img-wrap, ktery je take flex:1 (zabira
   vsechnu vysku karty krome male patky s popiskem) - obrazek se tak
   zvetsi na maximum, co dovoli jeho pomer stran, misto puvodniho
   pevneho "width:100%" (kde vyslednou vysku diktoval jen pomer stran
   zdrojoveho PNG/JPEG, casto mnohem mensi nez cela karta). */
.views-grid {{ display: flex; gap: 6mm; flex: 1; min-height: 0; }}
.views-grid .view-card {{ flex: 1; min-height: 0; }}
.views-grid-single {{ justify-content: center; }}
.views-grid-single .view-card {{ flex: 0 1 auto; width: 90%; }}
.view-card {{ background: #fff; border-radius: 8px; overflow: hidden; border: 1px solid #e2e8ee; box-shadow: 0 2px 10px rgba(22,50,79,0.08); display: flex; flex-direction: column; }}
.view-card .img-wrap {{ flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; background: #fff; overflow: hidden; }}
.view-card .img-wrap img {{ max-width: 100%; max-height: 100%; object-fit: contain; display: block; }}
.view-card .caption {{ flex-shrink: 0; padding: 5mm 6mm; font-size: 10.5pt; font-weight: 700; color: #16324f; border-top: 3px solid #ff7a3d; background: #f8fafc; }}
.view-card .caption small {{ display: block; font-weight: 400; color: #7a8798; font-size: 8.5pt; margin-top: 1mm; }}

table.items {{ width: 100%; border-collapse: collapse; margin-top: 2mm; }}
table.items thead th {{ background: #16324f; color: #fff; font-size: 9.5pt; text-transform: uppercase; letter-spacing: 0.5px; padding: 4mm; text-align: left; }}
table.items thead th.num {{ text-align: right; }}
table.items tbody td {{ padding: 4mm; font-size: 10.5pt; border-bottom: 1px solid #eef1f5; color: #2a3646; }}
table.items tbody tr:nth-child(even) {{ background: #f7f9fb; }}
table.items td.it-dim, table.items td.it-qty, table.items td.it-price, table.items td.it-total {{ text-align: right; white-space: nowrap; }}
table.items td.it-total {{ font-weight: 700; color: #16324f; }}

.total-banner {{ margin-top: 10mm; display: flex; justify-content: space-between; align-items: center; background: linear-gradient(90deg, #16324f, #1c4a6b); color: #fff; border-radius: 8px; padding: 8mm 10mm; }}
.total-banner .label {{ font-size: 12pt; letter-spacing: 1px; text-transform: uppercase; color: #cfe0ee; }}
.total-banner .value {{ font-size: 24pt; font-weight: 900; color: #ffb35c; }}

.closing {{ background: linear-gradient(135deg, #0f2138 0%, #16324f 100%); color: #fff; padding: 26mm 22mm; height: 100%; position: relative; }}
.closing h2 {{ font-size: 30pt; font-weight: 900; margin-bottom: 8mm; }}
.closing p {{ font-size: 11.5pt; line-height: 1.8; color: #cfe0ee; max-width: 130mm; }}
.closing .contact-grid {{ margin-top: 16mm; display: flex; gap: 10mm; flex-wrap: wrap; }}
.closing .contact-item {{ font-size: 10.5pt; color: #fff; }}
.closing .contact-item .k {{ color: #ff9a66; font-weight: 700; display: block; font-size: 8.5pt; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 1mm; }}
.closing .accent-bar {{ position: absolute; left: 0; top: 0; width: 100%; height: 6mm; background: linear-gradient(90deg, #ff7a3d, #ffb35c); }}
</style>
</head>
<body>

<div class="slide cover">
  <div class="shape s1"></div>
  <div class="shape s2"></div>
  <div class="eyebrow">Cenová nabídka</div>
  <h1>Nabídka<br>č. {offer_number}</h1>
  <div class="offer-meta">
    Datum vystavení: <b>{today}</b><br>
    Platnost nabídky do: <b>{valid_until}</b><br>
    Vypracoval: <b>{SUPPLIER['name']}</b>
  </div>
  <div class="brand"><span class="brand-logo"><span class="brand-logo-hl">LOGi</span><span class="brand-logo-lt">MAN</span></span> · 3D konfigurátor hliníkových konstrukcí</div>
  <div class="accent-bar"></div>
</div>

<div class="slide">
  <div class="content">
    <div class="slide-title"><span class="num">01</span><h2>O nabízeném řešení</h2><div class="rule"></div></div>
    <div class="intro-card">{editable_text['popis']}{(' ' + customer_note) if customer_note else ''}</div>
    <div class="recipient-grid">
      <div class="recipient-card">
        <div class="label">Dodavatel</div>
        <div class="line">
          <b>{SUPPLIER['name']}</b><br>
          {SUPPLIER['street']}, {SUPPLIER['city']}<br>
          IČ: {SUPPLIER['ico']} · DIČ: {SUPPLIER['dic']}<br>
          {SUPPLIER['phone']} · {SUPPLIER['email']}
        </div>
      </div>
      <div class="recipient-card">
        <div class="label">Odběratel</div>
        <div class="line">{customer_name}</div>
      </div>
    </div>
  </div>
</div>

<div class="slide">
  <div class="content content-wide">
    <div class="slide-title"><span class="num">02</span><h2>Technické výkresy</h2><div class="rule"></div></div>
    <div class="views-grid">
      <div class="view-card"><div class="img-wrap"><img src="{views['narys']}"></div><div class="caption">Nárys<small>s kótami</small></div></div>
      <div class="view-card"><div class="img-wrap"><img src="{views['bokorys']}"></div><div class="caption">Bokorys<small>s kótami</small></div></div>
    </div>
  </div>
</div>

<div class="slide">
  <div class="content content-wide">
    <div class="slide-title"><span class="num">02</span><h2>Technické výkresy (pokračování)</h2><div class="rule"></div></div>
    <div class="views-grid views-grid-single">
      <div class="view-card"><div class="img-wrap"><img src="{views['pudorys']}"></div><div class="caption">Půdorys<small>s kótami</small></div></div>
    </div>
  </div>
</div>

<div class="slide">
  <div class="content content-wide">
    <div class="slide-title"><span class="num">03</span><h2>3D pohledy ze scény</h2><div class="rule"></div></div>
    <div class="views-grid">
      <div class="view-card"><div class="img-wrap"><img src="{views['view3d_a']}"></div><div class="caption">3D pohled – úhel 1</div></div>
      <div class="view-card"><div class="img-wrap"><img src="{views['view3d_b']}"></div><div class="caption">3D pohled – úhel 2</div></div>
    </div>
  </div>
</div>

<div class="slide">
  <div class="content">
    <div class="slide-title"><span class="num">04</span><h2>Cenová nabídka</h2><div class="rule"></div></div>
    <table class="items">
      <thead><tr><th>Položka</th><th class="num">Rozměr</th><th class="num">Množství</th><th class="num">Cena/ks</th><th class="num">Celkem</th></tr></thead>
      <tbody>{items_rows}
      </tbody>
    </table>
    <div class="total-banner">
      <div class="label">Celková cena bez DPH</div>
      <div class="value">{_fmt_czk(total_price)}</div>
    </div>
  </div>
</div>

<div class="slide closing">
  <div class="accent-bar"></div>
  <h2>Děkujeme za poptávku</h2>
  <p>{editable_text['patka']}</p>
  <div class="contact-grid">
    <div class="contact-item"><span class="k">Web</span>{SUPPLIER['web']}</div>
    <div class="contact-item"><span class="k">E-mail</span>{SUPPLIER['email']}</div>
    <div class="contact-item"><span class="k">Telefon</span>{SUPPLIER['phone']}</div>
    <div class="contact-item"><span class="k">Bankovní účet</span>{SUPPLIER['bank_account']}</div>
  </div>
</div>

</body>
</html>
"""


def _save_offer_image(data_uri):
    """Ulozi jeden validovany data:image/... snimek jako soubor v
    OFFER_IMAGES_DIR, vrati stored_filename (ne cestu - stejna konvence
    jako quotes.py/drive.py). Pripona podle skutecneho typu v data-URI
    (png/jpeg), pro spravny Content-Type pri pozdejsim servirovani."""
    m = DATA_URI_RE.match(data_uri.strip())
    ext = "jpg" if m.group(1) == "jpeg" else "png"
    raw = base64.b64decode(m.group("b64"), validate=True)
    stored_filename = safe_stored_filename(f"view.{ext}")
    with open(os.path.join(OFFER_IMAGES_DIR, stored_filename), "wb") as f:
        f.write(raw)
    return stored_filename


# Robert 2026-08-07 ("vlož odklikávání správnosti rovnou tam do sceny,
# ať není pochyb a komunikační šum"): styl kotovani technickeho vykresu
# (narys/bokorys/pudorys v generateSceneOffer()) byl donedavna natvrdo
# zadratovany DEFAULT_DIM_STYLE primo v scene.html (viz "Náhled
# kótování" modal, commit 40cb1be) - misto aby Robert musel popisovat
# vybranou kombinaci zpet v chatu, tlacitko "✓ Toto je správně" v tom
# modalu ted ulozi zvolenou kombinaci sem, a `generateSceneOffer()` si
# ji pri KAZDEM generovani skutecne nabidky nacte a pouzije - zadny
# prepis kodu/nasazeni potreba pro zmenu stylu.
DIMENSION_STYLE_SETTING_KEY = "scene_dimension_style"
DIMENSION_STYLE_OCCLUSION_VALUES = ("loose", "strict")
DIMENSION_STYLE_TOTALS_VALUES = ("both", "totalOnly", "segmentsOnly")
# Robert 2026-08-07 ("toto nastavení chceme dafaultní" - odklikano v
# Náhled kótování primo ve scene.html): jen jednotlive rozmery dilu,
# bez celkoveho rozmeru sestavy. Tenhle konstantni fallback se pouzije
# jen kdyz v app_settings jeste neni zadny ulozeny zaznam (viz
# admin_dimension_style_get nize) - jinak je zdrojem pravdy DB hodnota.
DIMENSION_STYLE_DEFAULT = {"chainMerge": True, "occlusion": "loose", "totals": "segmentsOnly"}


@app.get("/api/admin/dimension-style")
@require_permission("nabidky", "zobrazit")
def admin_dimension_style_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            raw = get_setting(cur, DIMENSION_STYLE_SETTING_KEY, None)
    finally:
        conn.close()
    if not raw:
        return jsonify(dict(DIMENSION_STYLE_DEFAULT))
    try:
        style = json.loads(raw)
    except (TypeError, ValueError):
        return jsonify(dict(DIMENSION_STYLE_DEFAULT))
    return jsonify({
        "chainMerge": bool(style.get("chainMerge", DIMENSION_STYLE_DEFAULT["chainMerge"])),
        "occlusion": style.get("occlusion", DIMENSION_STYLE_DEFAULT["occlusion"]),
        "totals": style.get("totals", DIMENSION_STYLE_DEFAULT["totals"]),
    })


@app.put("/api/admin/dimension-style")
@require_permission("nabidky", "upravit")
def admin_dimension_style_set():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    occlusion = body.get("occlusion", DIMENSION_STYLE_DEFAULT["occlusion"])
    totals = body.get("totals", DIMENSION_STYLE_DEFAULT["totals"])
    if occlusion not in DIMENSION_STYLE_OCCLUSION_VALUES:
        return jsonify({"error": "Neplatná hodnota occlusion."}), 400
    if totals not in DIMENSION_STYLE_TOTALS_VALUES:
        return jsonify({"error": "Neplatná hodnota totals."}), 400
    style = {"chainMerge": bool(body.get("chainMerge", True)), "occlusion": occlusion, "totals": totals}
    value = json.dumps(style)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                (DIMENSION_STYLE_SETTING_KEY, value, value),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "dimension_style", None, value)
    return jsonify({"status": "ok", **style})


# --- Prostředí scény: globální VÝCHOZÍ nastavení (Robert 2026-09-05:
# "tlačítko pro uložení aktuálního nastavení jako defaultní"). Admin uloží
# aktuální stav sliderů prostředí/materiálu ve scene.html; ostatní uživatelé
# scény (interní nástroj, ne veřejný e-shop) ho dostanou jako výchozí při
# načtení. Stejný vzor jako dimension-style výše (app_settings key-value JSON).
SCENE_ENV_DEFAULTS_KEY = "scene_env_defaults"
# Bílá listina klíčů - uloží se jen tyhle, žádný cizí balast z těla requestu.
SCENE_ENV_DEFAULTS_ALLOWED = (
    "envBrightness", "envSaturation", "lightIntensity", "sceneContrast", "envHue",
    "metalness", "roughness", "sparkle", "baseColor", "shadows", "lowRes", "hdriFile",
)


@app.get("/api/admin/scene-env-defaults")
@require_permission("nabidky", "zobrazit")
def scene_env_defaults_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            raw = get_setting(cur, SCENE_ENV_DEFAULTS_KEY, None)
    finally:
        conn.close()
    if not raw:
        return jsonify({})
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return jsonify({})
    return jsonify(data if isinstance(data, dict) else {})


@app.put("/api/admin/scene-env-defaults")
@require_permission("nabidky", "upravit")
def scene_env_defaults_set():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    clean = {k: body[k] for k in SCENE_ENV_DEFAULTS_ALLOWED if k in body}
    value = json.dumps(clean)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                (SCENE_ENV_DEFAULTS_KEY, value, value),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "scene_env_defaults", None, value)
    return jsonify({"status": "ok", "saved": clean})


def create_scene_offer_row(items, total_price, views, customer_name, customer_email,
                            hdri_json, offer_options, user_id):
    """Sdileny zapis noveho radku scene_offers - DB cast toho, co drive
    delal jen scene_offers_create() primo (bot10 2026-09-28, zadal Robert:
    "integrace Vandr do online nabidky"). `views` uz MUSI byt validovany
    dict data-URI (viz _validate_data_uri) - volajici (HTTP handler nize,
    nebo vandr_scene_offers.py) je zodpovedny za vstupni validaci/vyrobu
    obrazku, tahle funkce uz jen zapisuje. Vraci (offer_id, offer_number,
    view_token) - `online_url` si slozi volajici, at HTTP odpoved zustava
    presne stejna jako drive."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            folder_id = _ensure_nabidky_folder(cur)
            editable_text = _load_editable_text(cur, folder_id)
            seq = _next_quote_number(cur)
            offer_number = f"{QUOTE_PREFIX}{seq}"

            # Automaticke PDF ZRUSENO (Robert 2026-08-06: "zrus automaticke
            # generovani PDF nabidky to uz nepotrebujeme protoze online
            # nabidka se da stahnout v PDF") - drive se tu pres WeasyPrint
            # renderovalo PDF a ukladalo do slozky Nabidky na Sdilenem
            # disku (drive_file_id). Nove nabidky maji drive_file_id NULL
            # -> verejna stranka nenabizi tlacitko ⬇ PDF (pdf_url null),
            # klient si nabidku vytiskne/ulozi z prohlizece. Stare nabidky
            # sva PDF na disku maji dal. _render_offer_html/WeasyPrint
            # zustavaji v kodu (netknute) pro pripadny navrat.
            file_id = None

            # Interaktivni online nabidka - obrazky ulozit JEDNOTLIVE (na
            # rozdil od PDF vyse, ktere je uz hotovy jeden blob) a
            # zaznamenat obsah trvale (jinak by po tehle funkci zmizel -
            # html/pdf_bytes vyse jsou jen v pameti, nikam se neuklada
            # samotny kusovnik/cena/text).
            view_files = {col: (_save_offer_image(views[key]) if key in views else None)
                          for key, col in OFFER_VIEW_KEYS.items()}
            view_token = secrets.token_urlsafe(32)
            view_token_hash = hashlib.sha256(view_token.encode()).hexdigest()
            expires_at = datetime.datetime.now() + datetime.timedelta(days=OFFER_LINK_VALIDITY_DAYS)
            cur.execute(
                "INSERT INTO scene_offers (offer_number, drive_file_id, items, total_price, "
                "view_narys, view_bokorys, view_pudorys, "
                "view_narys_ghost, view_bokorys_ghost, view_pudorys_ghost, view_3d_a, view_3d_b, "
                "editable_text_popis, editable_text_patka, customer_name, customer_email, "
                "view_token_hash, expires_at, created_by, hdri_json, offer_options) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    offer_number, file_id, json.dumps(items, ensure_ascii=False), total_price,
                    view_files["view_narys"], view_files["view_bokorys"], view_files["view_pudorys"],
                    view_files["view_narys_ghost"], view_files["view_bokorys_ghost"], view_files["view_pudorys_ghost"],
                    view_files["view_3d_a"], view_files["view_3d_b"],
                    editable_text["popis"], editable_text["patka"], customer_name, customer_email,
                    view_token_hash, expires_at, user_id, hdri_json,
                    json.dumps(offer_options, ensure_ascii=False),
                ),
            )
            offer_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    log_audit(user_id, "create", "scene_offer", offer_id, offer_number)
    return offer_id, offer_number, view_token


@app.post("/api/admin/scene-offers")
@require_permission("sdileny_disk", "zobrazit")
def scene_offers_create():
    if request.content_length and request.content_length > 8 * MAX_IMAGE_BYTES:
        return jsonify({"error": "Požadavek je příliš velký."}), 413

    body = request.get_json(silent=True) or {}
    items = body.get("items")
    total_price = body.get("total_price")
    views_in = body.get("views") or {}
    customer = body.get("customer") or {}
    # HDRI odlesky (Robert 2026-08-06: "zapec") - snapshot aktualniho
    # nastaveni ze sceny v okamziku generovani. Volitelne; validace
    # minimalni (jen tvar/typy), soubor se overuje az pri cteni klientem
    # (kdyz mapa mezitim zmizi z /katalog/hdri/, viewer proste degraduje
    # bez odlesku).
    hdri_in = body.get("hdri")
    hdri_json = None
    if isinstance(hdri_in, dict) and isinstance(hdri_in.get("file"), str) and hdri_in["file"].strip():
        try:
            base_color = hdri_in.get("base_color")
            base_color = (base_color.strip()[:9] if isinstance(base_color, str) and
                          re.match(r"^#[0-9a-fA-F]{3,8}$", base_color.strip()) else None)
            hdri_json = json.dumps({
                "file": hdri_in["file"].strip()[:255],
                "rotation": float(hdri_in.get("rotation") or 0),
                "intensity": max(0.0, min(3.0, float(hdri_in.get("intensity") or 1))),
                "roughness": (max(0.0, min(1.0, float(hdri_in["roughness"])))
                              if hdri_in.get("roughness") is not None else None),
                "metalness": (max(0.0, min(1.0, float(hdri_in["metalness"])))
                              if hdri_in.get("metalness") is not None else None),
                "base_color": base_color,
            })
        except (TypeError, ValueError):
            hdri_json = None

    if not isinstance(items, list) or not items:
        return jsonify({"error": "Chybí kusovník (items)."}), 400
    if total_price is None:
        return jsonify({"error": "Chybí celková cena (total_price)."}), 400

    # E-mail zakaznika (Robert 2026-08-10: "pridat pole e-mail pri
    # vytvoreni nabidky") - VOLITELNY (na rozdil od jmena neni povinny,
    # obchodnik ho nemusi mit hned po ruce), ale kdyz je vyplneny, musi
    # byt platny - jinak by tise nefungovala upominka pred vyprsenim
    # (scripts/2026-08-10_offer_expiry_reminder.py), ktera na nej cili.
    customer_email = (customer.get("email") or "").strip()[:255] or None
    if customer_email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", customer_email):
        return jsonify({"error": "E-mail zákazníka není platný."}), 400

    # Robert 2026-08-09 ("při její tvorbě... chci mit moznost vzdy
    # nektere prvky odebrat, napr QR kod, nebo naopak doplnit: Termin
    # dodani") - volitelne prvky zvolene v okamziku vytvoreni nabidky.
    # JSON (ne samostatne sloupce), aby sla sada v budoucnu rozsirit o
    # dalsi prvky beze zmeny schematu. Whitelist klicu + typova/delkova
    # sanitizace, at si klient v POST body neposle libovolna data.
    offer_options = _sanitize_offer_options(body.get("offer_options"))

    try:
        views = {
            "narys": _validate_data_uri(views_in.get("narys"), "Nárys"),
            "bokorys": _validate_data_uri(views_in.get("bokorys"), "Bokorys"),
            "pudorys": _validate_data_uri(views_in.get("pudorys"), "Půdorys"),
            "view3d_a": _validate_data_uri(views_in.get("view3d_a"), "3D pohled 1"),
            "view3d_b": _validate_data_uri(views_in.get("view3d_b"), "3D pohled 2"),
        }
        # narys_ghost/bokorys_ghost/pudorys_ghost (Robert: "2D pohledy...
        # drateny a ghosted") - nepovinne, jen kdyz je klient posle (novy
        # scene.html je vzdy posila, ale nechceme tvrdou vazbu na presnou
        # verzi frontendu).
        for ghost_key, label in (("narys_ghost", "Nárys (ghost)"), ("bokorys_ghost", "Bokorys (ghost)"), ("pudorys_ghost", "Půdorys (ghost)")):
            if views_in.get(ghost_key):
                views[ghost_key] = _validate_data_uri(views_in.get(ghost_key), label)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    user = current_user()
    offer_id, offer_number, view_token = create_scene_offer_row(
        items, total_price, views, customer.get("name") or None, customer_email,
        hdri_json, offer_options, user["id"],
    )
    return jsonify({
        "status": "ok",
        "offer_id": offer_id,
        "offer_number": offer_number,
        "online_url": f"/nabidka-online.html?t={view_token}",
    }), 201


# Robert pres bot3, 2026-09-14: "geometrie sestav z online nabidek
# potrebuje jit na Sdileny disk s vazbou na nabidku, aby prezila i
# archivaci nabidky" - VLASTNI root (ne spolecny s rendery), at se
# binarni GLB nemicha s obrazky ve stejnem seznamu slozky. Narozdil od
# renderu/PDF (viz admin_scene_offers_bulk_delete nize) tenhle soubor
# pri smazani nabidky NEmizi - zivou scenu, ze ktere GLB vznikl, uz
# nejde zpetne obnovit, takze jednou ztraceny model je ztraceny navzdy.
OFFER_MODELS_DRIVE_ROOT = "Modely nabídek"


def _ensure_offer_models_folder(cur, offer_number):
    """Vrati id slozky 'Modely nabidek/<offer_number>' (vytvori chybejici)."""
    cur.execute("SELECT id FROM shared_drive_folders "
                "WHERE parent_folder_id IS NULL AND name=%s", (OFFER_MODELS_DRIVE_ROOT,))
    row = cur.fetchone()
    if row:
        root_id = row["id"]
    else:
        cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) "
                    "VALUES (NULL,%s,%s)", (OFFER_MODELS_DRIVE_ROOT, None))
        root_id = cur.lastrowid
    cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id=%s AND name=%s",
                (root_id, offer_number))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) "
                "VALUES (%s,%s,%s)", (root_id, offer_number, None))
    return cur.lastrowid


def _model_filename_slug(text):
    """ASCII/pomlckovy slug pro citelny nazev souboru na Sdilenem disku
    (Robert: "nese offer_number + jmeno zakaznika, ne jen interni ID") -
    lokalni jednoduchy variant, at se nemusi importovat app.py::_slugify
    (ten ma jiny fallback urceny pro kategorie, ne pro tenhle ucel)."""
    import unicodedata
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def save_offer_model_bytes(offer_id, raw, admin_id):
    """Sdilena cast admin_scene_offer_upload_model() nize (bot10
    2026-09-28, "integrace Vandr do online nabidky") - bere uz nacteny
    a velikostne overeny GLB obsah (magic hlavicka "glTF" kontroluje
    volajici, at tahle funkce zustane cistá zapisova cast, stejny vzor
    jako create_scene_offer_row vyse). Vraci None (uspech) nebo retezec
    s chybou pro pripad "nabidka neexistuje"."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, offer_number, customer_name FROM scene_offers WHERE id=%s", (offer_id,))
            offer = cur.fetchone()
            if not offer:
                return "Nabídka neexistuje."
            stored_filename = safe_stored_filename("model.glb")
            with open(os.path.join(OFFER_MODELS_DIR, stored_filename), "wb") as fh:
                fh.write(raw)
            drive_model_file_id = None
            try:
                folder_id = _ensure_offer_models_folder(cur, offer["offer_number"])
                slug_parts = [offer["offer_number"]]
                if offer["customer_name"]:
                    slug_parts.append(_model_filename_slug(offer["customer_name"]))
                nice_name = "model_" + "_".join(p for p in slug_parts if p) + ".glb"
                drive_stored = safe_stored_filename(nice_name)
                with open(os.path.join(DRIVE_FILES_DIR, drive_stored), "wb") as fh:
                    fh.write(raw)
                cur.execute(
                    "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, "
                    "content_type, size_bytes, uploaded_by) VALUES (%s,%s,%s,%s,%s,%s)",
                    (folder_id, nice_name, drive_stored, "model/gltf-binary", len(raw), admin_id),
                )
                drive_model_file_id = cur.lastrowid
            except Exception as e:
                app.logger.warning("Zrcadleni 3D modelu nabidky %s na Sdileny disk selhalo: %s",
                                    offer["offer_number"], e)
            cur.execute(
                "UPDATE scene_offers SET view_3d_model=%s, drive_model_file_id=%s WHERE id=%s",
                (stored_filename, drive_model_file_id, offer_id),
            )
        conn.commit()
    finally:
        conn.close()
    return None


@app.post("/api/admin/scene-offers/<int:offer_id>/model")
@require_permission("sdileny_disk", "zobrazit")
def admin_scene_offer_upload_model(offer_id):
    """Zivy 3D model (Robert: "3D model ne jako nahledy ale rovnou jako
    zivy model") - nahrava se SAMOSTATNE, druhym pozadavkem z frontendu
    az PO uspesnem scene_offers_create() vyse (viz komentar u
    OFFER_MODELS_DIR - duvod je nginx client_max_body_size). Volitelne:
    kdyz frontend export/upload selze, nabidka proste zustane bez
    modelu (view_3d_model NULL) a verejna stranka spadne na ploche
    obrazky - nejde o kriticky krok.

    Robert pres bot3, 2026-09-14: model se navic ZRCADLI na Sdileny
    disk (Modely nabidek/<offer_number>) - viz OFFER_MODELS_DRIVE_ROOT
    komentar pro duvod (na rozdil od PDF/renderu se pri smazani nabidky
    NEmaze). Zrcadleni je best-effort - kdyby selhalo (napr. Sdileny
    disk docasne nedostupny), lokalni kopie (view_3d_model, servrovana
    verejne strance) uz je ulozena a funkcni, jen bez trvale Drive
    zalohy; nejde o kriticky krok stejne jako upload samotny."""
    # current_user() MUSI byt pred get_conn() - stejne pooled-spojeni
    # gotcha jako u admin_scene_offer_render_add (viz jeho komentar).
    admin = current_user()
    f = request.files.get("model")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor modelu."}), 400
    raw = f.read()
    if len(raw) > MAX_MODEL_BYTES:
        return jsonify({"error": f"Model je příliš velký (max {MAX_MODEL_BYTES // (1024*1024)} MB)."}), 400
    # Overit SKUTECNY obsah (GLB magic hlavicka "glTF"), ne jen priponu/
    # content-type z uploadu - stejny princip jako PDF magic bytes u
    # quotes.py preview endpointu.
    if len(raw) < 20 or raw[:4] != b"glTF":
        return jsonify({"error": "Neplatný GLB soubor."}), 400
    err = save_offer_model_bytes(offer_id, raw, admin["id"] if admin else None)
    if err:
        return jsonify({"error": err}), 404
    return jsonify({"status": "ok"}), 201


@app.post("/api/admin/scene-offers/<int:offer_id>/views-3d")
@require_permission("sdileny_disk", "zobrazit")
def admin_scene_offer_update_views_3d(offer_id):
    """Robert 2026-08-10 ("nejdriv vygenerovat nabidku s okny pro
    rendery... abych vedel kde to cekat kdyby to nevyslo, a teprve pote
    vytvorit rendery a ty tam vlozit"): fotorealisticky (ray-traced)
    render uz NEBLOKUJE samotne vytvoreni nabidky (viz scene_offers_create
    vyse) - nabidka se zalozi HNED s rychlymi rastrovanymi 3D nahledy a
    ray tracing bezi AZ POTOM na pozadi (viz runPathTraceUpgrade ve
    scene.html). Tenhle endpoint jen DODATECNE PREPISE uz ulozene
    view_3d_a/view_3d_b existujici nabidky, kdyz je fotorealisticky
    vysledek hotovy. Kazdy klic (view3d_a/view3d_b) volitelny zvlast -
    kdyz se povede jen 1 ze 2 pohledu, druhy zustane puvodni rastrovany
    beze zmeny. Stare soubory se smazou az PO commitu (stejny vzor jako
    admin_scene_offers_bulk_delete)."""
    body = request.get_json(silent=True) or {}
    try:
        new_data = {}
        for key, col in (("view3d_a", "view_3d_a"), ("view3d_b", "view_3d_b")):
            if body.get(key):
                new_data[col] = _validate_data_uri(body[key], "3D pohled")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not new_data:
        return jsonify({"error": "Nic k aktualizaci (chybí view3d_a/view3d_b)."}), 400

    conn = get_conn()
    old_files = {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT view_3d_a, view_3d_b FROM scene_offers WHERE id=%s", (offer_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Nabídka neexistuje."}), 404
            fields, params = [], []
            for col, data_uri in new_data.items():
                old_files[col] = row[col]
                fields.append(f"{col}=%s")
                params.append(_save_offer_image(data_uri))
            params.append(offer_id)
            cur.execute(f"UPDATE scene_offers SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()

    for old_filename in old_files.values():
        if old_filename:
            try:
                os.remove(os.path.join(OFFER_IMAGES_DIR, old_filename))
            except OSError:
                pass  # soubor uz chybi - DB je autoritativni, nevadi
    return jsonify({"status": "ok"})


# --------------------------------------------------------------------
# Rendery nabidky (Robert 2026-08-11: "ted potrebujeme nas Render cycle
# dostat do nabidky" -> "kdyz se mi budou libit chci nekde odkliknout ano
# maji byt soucasti nabidky" -> "pokud udelam renderu vic, kazdy projde
# timto koleckem, tudiz mezi 3D objekt a cenovou nabidku muze umistit
# libovolny pocet renderu").
#
# Zamerne ODDELENE od view_3d_a/view_3d_b vyse: ty dva jsou pevne
# "okenka" nabidky a prepisuji se. Tohle je otevrena galerie - render
# vznikne v panelu Render ve scene.html, admin si ho prohledne a teprve
# schvalenim ho sem posle. Nic se nedeje automaticky.
# --------------------------------------------------------------------

MAX_OFFER_RENDERS = 30  # rozumny strop, at jedna nabidka nezaplni disk

# Robert 2026-08-11: "nechci ukladat rendery kam nevidim, ale do
# sdileneho disku, kde je muzu kdykoli smazat." Obrazky renderu se
# proto ukladaji jako soubory Sdileneho disku (slozka "Rendery nabidek/
# <cislo nabidky>") - jsou videt v adminu, jdou stahnout i smazat jako
# kazdy jiny soubor. scene_offer_renders na ne odkazuje pres
# drive_file_id; kdyz soubor ze Sdileneho disku zmizi, render se v
# nabidce proste prestane ukazovat (zadna chyba).
OFFER_RENDERS_DRIVE_ROOT = "Rendery nabídek"


def _ensure_offer_renders_folder(cur, offer_number):
    """Vrati id slozky 'Rendery nabidek/<offer_number>' (vytvori chybejici)."""
    cur.execute("SELECT id FROM shared_drive_folders "
                "WHERE parent_folder_id IS NULL AND name=%s", (OFFER_RENDERS_DRIVE_ROOT,))
    row = cur.fetchone()
    if row:
        root_id = row["id"]
    else:
        cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) "
                    "VALUES (NULL,%s,%s)", (OFFER_RENDERS_DRIVE_ROOT, None))
        root_id = cur.lastrowid
    cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id=%s AND name=%s",
                (root_id, offer_number))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) "
                "VALUES (%s,%s,%s)", (root_id, offer_number, None))
    return cur.lastrowid


def _render_row_file_path(row):
    """Cesta k obrazku renderu: novy zpusob = soubor Sdileneho disku
    (drive_stored), stary = OFFER_IMAGES_DIR (stored_filename)."""
    if row.get("drive_stored"):
        return os.path.join(DRIVE_FILES_DIR, row["drive_stored"])
    if row.get("stored_filename"):
        return os.path.join(OFFER_IMAGES_DIR, row["stored_filename"])
    return None


@app.get("/api/admin/scene-offers/<int:offer_id>/renders")
@require_permission("sdileny_disk", "zobrazit")
def admin_scene_offer_renders_list(offer_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT r.id, r.caption, r.mesh_group, r.sort_order, r.created_at, "
                        "r.stored_filename, r.drive_file_id, f.stored_filename AS drive_stored, "
                        "f.filename AS drive_name "
                        "FROM scene_offer_renders r "
                        "LEFT JOIN shared_drive_files f ON f.id = r.drive_file_id "
                        "WHERE r.offer_id=%s ORDER BY r.sort_order, r.id", (offer_id,))
            rows = cur.fetchall()
    finally:
        conn.close()
    # Rendery, jejichz soubor byl mezitim smazan ze Sdileneho disku, se
    # tise vynechaji (Robert je maze primo tam - to je zadane chovani).
    rows = [r for r in rows if _render_row_file_path(r) and os.path.exists(_render_row_file_path(r))]
    return jsonify({"renders": [{
        "id": r["id"], "caption": r["caption"], "mesh_group": r["mesh_group"],
        "sort_order": r["sort_order"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "url": f"/api/admin/scene-offers/{offer_id}/renders/{r['id']}/image",
        "drive_name": r.get("drive_name"),
    } for r in rows]})


@app.post("/api/admin/scene-offers/<int:offer_id>/renders")
@require_permission("sdileny_disk", "zobrazit")
def admin_scene_offer_render_add(offer_id):
    body = request.get_json(silent=True) or {}
    try:
        data_uri = _validate_data_uri(body.get("image"), "Render")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    caption = (body.get("caption") or "").strip()[:200] or None
    mesh_group = body.get("mesh_group")
    mesh_group = int(mesh_group) if isinstance(mesh_group, int) else None
    # POZOR: current_user() MUSI byt pred get_conn()/zacatkem transakce.
    # Pouziva stejne per-thread spojeni a jeho conn.close() (= rollback,
    # viz _PooledConn) by ODROLOVAL nase necommitnute INSERTy - presne
    # tak spadly prvni pokusy o ulozeni renderu na Sdileny disk
    # (IntegrityError 1452: slozka vlozena v _ensure_offer_renders_folder
    # zmizela driv, nez se na ni stihl navazat soubor).
    admin = current_user()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, offer_number FROM scene_offers WHERE id=%s", (offer_id,))
            offer = cur.fetchone()
            if not offer:
                return jsonify({"error": "Nabídka neexistuje."}), 404
            cur.execute("SELECT COUNT(*) AS n, COALESCE(MAX(sort_order), -1) AS mx "
                        "FROM scene_offer_renders WHERE offer_id=%s", (offer_id,))
            agg = cur.fetchone()
            if agg["n"] >= MAX_OFFER_RENDERS:
                return jsonify({"error": f"Nabídka už má maximum renderů ({MAX_OFFER_RENDERS})."}), 400
            # Soubor jde na SDILENY DISK (Robert 2026-08-11: "nechci
            # ukladat rendery kam nevidim, ale do sdileneho disku, kde je
            # muzu kdykoli smazat") - slozka Rendery nabidek/<cislo>.
            folder_id = _ensure_offer_renders_folder(cur, offer["offer_number"])
            m = DATA_URI_RE.match(data_uri.strip())
            ext = "jpg" if m.group(1) == "jpeg" else "png"
            raw = base64.b64decode(m.group("b64"), validate=True)
            nice_name = f"render_{offer['offer_number']}_{agg['n'] + 1:02d}.{ext}"
            stored = safe_stored_filename(nice_name)
            with open(os.path.join(DRIVE_FILES_DIR, stored), "wb") as fh:
                fh.write(raw)
            cur.execute("INSERT INTO shared_drive_files (folder_id, filename, stored_filename, "
                        "content_type, size_bytes, uploaded_by) VALUES (%s,%s,%s,%s,%s,%s)",
                        (folder_id, nice_name, stored, f"image/{'jpeg' if ext == 'jpg' else 'png'}",
                         len(raw), admin["id"] if admin else None))
            drive_file_id = cur.lastrowid
            cur.execute("INSERT INTO scene_offer_renders "
                        "(offer_id, drive_file_id, caption, mesh_group, sort_order) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (offer_id, drive_file_id, caption, mesh_group, agg["mx"] + 1))
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": new_id,
                    "url": f"/api/admin/scene-offers/{offer_id}/renders/{new_id}/image"}), 201


@app.get("/api/admin/scene-offers/<int:offer_id>/renders/<int:render_id>/image")
@require_permission("sdileny_disk", "zobrazit")
def admin_scene_offer_render_image(offer_id, render_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT r.stored_filename, f.stored_filename AS drive_stored "
                        "FROM scene_offer_renders r "
                        "LEFT JOIN shared_drive_files f ON f.id = r.drive_file_id "
                        "WHERE r.id=%s AND r.offer_id=%s", (render_id, offer_id))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Render nenalezen."}), 404
    return _send_offer_image_path(_render_row_file_path(row))


@app.put("/api/admin/scene-offers/<int:offer_id>/renders/<int:render_id>")
@require_permission("sdileny_disk", "zobrazit")
def admin_scene_offer_render_update(offer_id, render_id):
    """Uprava popisku a poradi (Robert 2026-08-11: sprava renderu v
    adminu - "miniatury, smazat, zmenit popisek, poradi"). move=up/down
    prohodi sort_order se sousedem - klient nemusi znat cizi sort_order."""
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sort_order FROM scene_offer_renders "
                        "WHERE id=%s AND offer_id=%s", (render_id, offer_id))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Render nenalezen."}), 404
            if "caption" in body:
                caption = (str(body.get("caption") or "")).strip()[:200] or None
                cur.execute("UPDATE scene_offer_renders SET caption=%s WHERE id=%s",
                            (caption, render_id))
            move = body.get("move")
            if move in ("up", "down"):
                op, order = ("<", "DESC") if move == "up" else (">", "ASC")
                cur.execute(f"SELECT id, sort_order FROM scene_offer_renders "
                            f"WHERE offer_id=%s AND (sort_order {op} %s "
                            f"OR (sort_order = %s AND id {op} %s)) "
                            f"ORDER BY sort_order {order}, id {order} LIMIT 1",
                            (offer_id, row["sort_order"], row["sort_order"], render_id))
                other = cur.fetchone()
                if other:
                    # Prohodit; pri shodnem sort_order (stare radky) rozrazit o 1.
                    a, b = row["sort_order"], other["sort_order"]
                    if a == b:
                        b = a + (-1 if move == "up" else 1)
                    cur.execute("UPDATE scene_offer_renders SET sort_order=%s WHERE id=%s", (b, render_id))
                    cur.execute("UPDATE scene_offer_renders SET sort_order=%s WHERE id=%s", (a, other["id"]))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.delete("/api/admin/scene-offers/<int:offer_id>/renders/<int:render_id>")
@require_permission("sdileny_disk", "zobrazit")
def admin_scene_offer_render_delete(offer_id, render_id):
    conn = get_conn()
    path = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT r.stored_filename, r.drive_file_id, "
                        "f.stored_filename AS drive_stored "
                        "FROM scene_offer_renders r "
                        "LEFT JOIN shared_drive_files f ON f.id = r.drive_file_id "
                        "WHERE r.id=%s AND r.offer_id=%s", (render_id, offer_id))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Render nenalezen."}), 404
            path = _render_row_file_path(row)
            cur.execute("DELETE FROM scene_offer_renders WHERE id=%s", (render_id,))
            if row["drive_file_id"]:
                cur.execute("DELETE FROM shared_drive_files WHERE id=%s", (row["drive_file_id"],))
        conn.commit()
    finally:
        conn.close()
    if path:  # az po commitu - stejny vzor jako u /views-3d vyse
        try:
            os.remove(path)
        except OSError:
            pass
    return jsonify({"status": "ok"})


@app.get("/api/public/offers/<token>/render/<int:render_id>")
def public_offer_render(token, render_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
            if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
                return jsonify({"error": "Nabídka nebyla nalezena."}), 404
            cur.execute("SELECT r.stored_filename, f.stored_filename AS drive_stored "
                        "FROM scene_offer_renders r "
                        "LEFT JOIN shared_drive_files f ON f.id = r.drive_file_id "
                        "WHERE r.id=%s AND r.offer_id=%s", (render_id, offer["id"]))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Render nenalezen."}), 404
    return _send_offer_image_path(_render_row_file_path(row))


def _send_offer_image_path(path):
    """Spolecne cteni obrazku renderu z disku (Sdileny disk i legacy)."""
    if not path:
        return jsonify({"error": "Obrázek na disku chybí."}), 404
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return jsonify({"error": "Obrázek na disku chybí."}), 404
    mimetype = "image/jpeg" if path.lower().endswith(("jpg", "jpeg")) else "image/png"
    return Response(data, mimetype=mimetype, headers={"X-Content-Type-Options": "nosniff"})


@app.post("/api/admin/scene-offers/<int:offer_id>/path-trace-error")
@require_permission("sdileny_disk", "zobrazit")
def admin_scene_offer_path_trace_error(offer_id):
    """Robert 2026-08-10 ("podivej se na tu nabidku je ulozena" -> zjisteno
    v nginx logu, ze runPathTraceUpgrade() ve scene.html nikdy ani
    nezkusila zavolat /views-3d - capturePathTracedOfferViews tedy
    selhala UPLNE, driv nez cokoli poslala). Ray tracing bezi CELY v
    prohlizeci admina, takze jeho JS chyby server normalne vubec nevidi
    - kazda diagnoza dosud vyzadovala rucni otevreni konzole prohlizece.
    Tenhle endpoint jen zaloguje (app.logger.warning, ctitelne pres
    `journalctl -u konfigurator`) presny text chyby + faze, kde nastala,
    poslany klientem (viz _reportPathTraceError ve scene.html) - dalsi
    selhani uz nebude potreba dohledavat pres Roberta, staci log."""
    body = request.get_json(silent=True) or {}
    stage = str(body.get("stage") or "?")[:100]
    message = str(body.get("message") or "?")[:2000]
    app.logger.warning(
        "Path tracer selhal (nabídka #%s, fáze '%s'): %s | UA: %s",
        offer_id, stage, message, request.headers.get("User-Agent", "?")[:300],
    )
    return jsonify({"status": "ok"})


# ============================================================
# Verejne API (BEZ prihlaseni) - klient otevre odkaz z e-mailu/chatu,
# token v URL nahrazuje session. Token samotny se nikde neuklada, jen
# jeho SHA-256 hash (viz scene_offers_create vyse) - stejny princip
# jako app_users.magic_token_hash.
# ============================================================

def _resolve_offer_by_token(cur, token):
    # Pousti jak klientsky token, tak oddeleny admin "Zobrazit online"
    # token (viz admin_scene_offer_view_online nize) - oba se ukladaji
    # jen jako hash, admin token se prepisuje pri kazdem kliknuti.
    token_hash = hashlib.sha256((token or "").encode()).hexdigest()
    cur.execute(
        "SELECT * FROM scene_offers WHERE view_token_hash=%s OR admin_view_token_hash=%s",
        (token_hash, token_hash),
    )
    return cur.fetchone()


def _client_ip():
    # X-Real-IP, ne X-Forwarded-For (bezpecnostni nalez, bot3 2026-09-02,
    # stejna oprava jako app.py::_client_ip) - nginx do XFF hodnotu jen
    # PRIDAVA, klient si libovolnou hodnotu na zacatek podvrhne sam.
    # X-Real-IP nginx vzdy prepisuje na skutecnou IP spojeni.
    ip = request.headers.get("X-Real-IP") or request.remote_addr or ""
    return ip.strip()[:45]


def _public_offer_rate_limited(token, scope, per_token, per_ip):
    """Brzda verejnych zapisujicich endpointu nabidky (bot16, 2026-09-03,
    revize bot3 - W2/W3/W4): limit na hash tokenu (kdo ma odkaz) + na IP.
    _rate_limited je in-memory per gunicorn worker (--workers 2), takze
    realny strop je az 2x - staci proti spamu DB/fronty e-mailu. Vraci
    odpoved 429 nebo None; token=None = jen IP."""
    if token is not None:
        token_hash = hashlib.sha256((token or "").encode()).hexdigest()
        if _rate_limited(f"scene_offer_{scope}:tok:{token_hash}", max_requests=per_token, window_seconds=3600):
            return jsonify({"error": "Příliš mnoho pokusů. Zkuste to prosím později."}), 429
    if _rate_limited(f"scene_offer_{scope}:ip:{_client_ip()}", max_requests=per_ip, window_seconds=3600):
        return jsonify({"error": "Příliš mnoho pokusů. Zkuste to prosím později."}), 429
    return None


def _offer_reaction_conflict(cur, offer_id, for_decline):
    """409 pri opakovane reakci (bot16, 2026-09-03, revize bot3 - W2):
    drive append-only bez limitu = kazde volani novy radek + e-mail do
    fronty. Zamkne radek nabidky (FOR UPDATE) - kontrola i nasledny
    INSERT bezi pod stejnym spojenim/transakci, dva soubezne pozadavky
    se serializuji. Prijeti ma prednost: odmitnout uz prijatou nejde,
    prijmout drive odmitnutou ano (zakaznik si to rozmyslel)."""
    cur.execute("SELECT id FROM scene_offers WHERE id=%s FOR UPDATE", (offer_id,))
    cur.execute("SELECT 1 FROM scene_offer_acceptances WHERE offer_id=%s LIMIT 1", (offer_id,))
    if cur.fetchone():
        return jsonify({"error": "already_accepted"}), 409
    if for_decline:
        cur.execute("SELECT 1 FROM scene_offer_declines WHERE offer_id=%s LIMIT 1", (offer_id,))
        if cur.fetchone():
            return jsonify({"error": "already_declined"}), 409
    return None


def _quote_guest_id():
    """Trvala anonymni identita napric navstevami (mirror
    support.py::_support_identity) - NA ROZDIL od scene_offer_views.view_id,
    ktery vznika NOVY pri kazdem nacteni stranky, tady potrebujeme
    poznat STEJNOU osobu, kdyz se na uz jednou objednanou/otazkou
    opatrenou nabidku vrati (napr. aby druhe nacteni stranky spravne
    ukazalo 'uz objednano' bez nutnosti znovu odesilat)."""
    gid = session.get("quote_guest_id")
    if not gid:
        gid = uuid.uuid4().hex
        session["quote_guest_id"] = gid
        session.permanent = True
    return gid


@app.get("/api/public/offers/<token>")
def public_offer_get(token):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
    finally:
        conn.close()
    # 404 shodne pro "neexistuje" i "deaktivovano" - neprozrazovat cizim
    # pozorovatelum, ktery pripad nastal.
    if not offer or not offer["is_active"]:
        return jsonify({"error": "Nabídka nebyla nalezena."}), 404
    if offer["expires_at"] < datetime.datetime.now():
        return jsonify({"error": "Platnost nabídky vypršela.", "expired": True}), 410
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, accepted_at FROM scene_offer_acceptances WHERE offer_id=%s ORDER BY accepted_at ASC LIMIT 1",
                (offer["id"],),
            )
            acceptance = cur.fetchone()
            # Odmitnuti/pripominka (Robert 2026-08-10: "nemam zajem" jako
            # protejsek k accept vyse) - stejny vzor, jen posledni zaznam
            # (na rozdil od acceptance, kde je prvni, protoze acceptance
            # se casteji NEopakuje - "uz objednano" stav se ukazuje trvale;
            # decline chce zobrazit NEJNOVEJSI pripominku, kdyby jich
            # zakaznik napsal vic).
            cur.execute(
                "SELECT reason, declined_at FROM scene_offer_declines WHERE offer_id=%s ORDER BY declined_at DESC LIMIT 1",
                (offer["id"],),
            )
            decline = cur.fetchone()
            order_prefs = _load_order_prefs(cur, offer["id"], _quote_guest_id())
            montaz_pct = get_setting(cur, "montaz_pct", "0")
            cur.execute("SELECT data FROM scene_offer_markups WHERE offer_id=%s", (offer["id"],))
            markup_row = cur.fetchone()
            # Schvalene rendery (viz admin_scene_offer_render_add) - stranka
            # "renders" se v prohlizeci ukaze jen kdyz je tenhle seznam neprazdny.
            cur.execute("SELECT r.id, r.caption, r.stored_filename, "
                        "f.stored_filename AS drive_stored "
                        "FROM scene_offer_renders r "
                        "LEFT JOIN shared_drive_files f ON f.id = r.drive_file_id "
                        "WHERE r.offer_id=%s ORDER BY r.sort_order, r.id", (offer["id"],))
            render_rows = [r for r in cur.fetchall()
                           if _render_row_file_path(r) and os.path.exists(_render_row_file_path(r))]
            pricky_blok = None                                    # pricky do multiboxu (bot8, 2026-10-07): nikdy nesmi shodit verejnou nabidku
            try:
                _pk = _pricky_kontext(cur, offer, _pricky_je_admin(token, offer))
                if _pk is not None:
                    pricky_blok = nabidka_pricky.payload(_pk["spec"], _pk["ceny"], nahled_admin=_pricky_je_admin(token, offer))
            except Exception:                                     # noqa: BLE001
                app.logger.exception("nabidka %s: blok pricek se nepodarilo sestavit", offer.get("offer_number"))
                pricky_blok = None
    finally:
        conn.close()
    try:
        saved_markups = json.loads(markup_row["data"]) if markup_row else []
    except (TypeError, ValueError):
        saved_markups = []
    # Role divaka podle pouziteho tokenu (bot4, 2026-08-05): admin
    # "Zobrazit online" token vs klientsky odkaz - admin dela znacky
    # modrozelene, zakaznik cervene (viz markups nize).
    viewer_is_admin = hashlib.sha256(token.encode()).hexdigest() == offer["admin_view_token_hash"]
    try:    # lokalni import: offer_markup_requests se registruje AZ po scene_offers (app.py); verejna stranka nesmi kvuli priznaku nikdy spadnout
        from offer_markup_requests import markup_requests_enabled
        markup_requests = bool(markup_requests_enabled(offer))
    except Exception:
        markup_requests = False
    return jsonify({
        "offer_number": offer["offer_number"],
        "items": json.loads(offer["items"]),
        "total_price": offer["total_price"],
        "editable_text": {"popis": offer["editable_text_popis"], "patka": offer["editable_text_patka"]},
        "customer_name": offer["customer_name"],
        "created_at": offer["created_at"].isoformat(),
        "expires_at": offer["expires_at"].isoformat(),
        "pages": list(OFFER_PAGE_KEYS),
        "image_urls": {
            key: f"/api/public/offers/{token}/image/{key}"
            for key in ("narys", "bokorys", "pudorys", "view3d_a", "view3d_b")
        },
        # Zivy 3D model (Robert: "ne jako nahledy ale rovnou jako zivy
        # model") - frontend podle has_3d_model ROVNOU vi, jestli ma
        # zkouset interaktivni verzi, nemusi cekat na 404.
        "has_3d_model": bool(offer["view_3d_model"]),
        # Galerie schvalenych renderu - vlastni stranka mezi 3D modelem a
        # cenovou nabidkou (Robert 2026-08-11).
        "renders": [{"id": r["id"], "caption": r["caption"],
                     "url": f"/api/public/offers/{token}/render/{r['id']}"}
                    for r in render_rows],
        "model_url": f"/api/public/offers/{token}/model" if offer["view_3d_model"] else None,
        # Robert ("2D pohledy... drateny a ghosted") - stare nabidky
        # (pred 2026-08-09) nemaji ghost varianty ulozene, frontend podle
        # tehle znacky rovnou vi, jestli ma prepinac vubec ukazovat.
        "has_ghost_views": bool(offer["view_narys_ghost"]),
        # Souhlas/objednavka (Robert: "Souhlasim / objednavam") - kdyz uz
        # nekdo drive potvrdil, frontend hned pri nacteni ukaze "uz
        # objednano" misto formulare.
        "accepted": {"name": acceptance["name"], "accepted_at": acceptance["accepted_at"].isoformat()} if acceptance else None,
        # Odmitnuti/pripominka - viz komentar u dotazu vyse. NULL misto
        # "" u reason (zakaznik mohl poslat jen "nemam zajem" bez textu).
        "declined": {"reason": decline["reason"], "declined_at": decline["declined_at"].isoformat()} if decline else None,
        # Historie verzi (Robert 2026-08-10: "plne editovani nabidky v
        # adminu") - frontend ukaze badge "aktualizovano DD.MM.", jen
        # kdyz uz byla nabidka po vytvoreni upravena (revision_number>1).
        "revision_number": offer["revision_number"],
        "last_edited_at": offer["last_edited_at"].isoformat() if offer["last_edited_at"] else None,
        "supplier": SUPPLIER,
        # QR Platba + verejne PDF + drive ulozene volby objednavky
        # (Robert 2026-08-05, viz komentar u prislusnych endpointu).
        "pdf_url": f"/api/public/offers/{token}/pdf" if offer["drive_file_id"] else None,
        "payment_qr_url": f"/api/public/offers/{token}/payment-qr",
        "order_prefs": order_prefs,
        # Ulozene oznaceni/kresba (tlacitko "Ulozit oznaceni") -
        # vektorove znacky, vykresli se u kazdeho, kdo nabidku otevre
        # (klient i admin pres "Zobrazit online"). Kazda znacka nese
        # author: 'admin'|'client' (barevne odlisene).
        "markups": saved_markups,
        "viewer_role": "admin" if viewer_is_admin else "client",
        # HDRI odlesky zapecene pri generovani (null = bez HDRI) - viewer
        # nacte mapu primo z /katalog/hdri/<file> (verejne servirovano).
        "hdri": (json.loads(offer["hdri_json"]) if offer.get("hdri_json") else None),
        # Volitelne prvky zvolene pri vytvoreni (Robert 2026-08-09, viz
        # scene_offers_create) - stare nabidky pred timhle datem maji
        # NULL, vychozi hodnoty odpovidaji puvodnimu (jedinemu) chovani
        # (QR platba vzdy zobrazena, zadny termin dodani).
        "offer_options": _verejne_offer_options(json.loads(offer["offer_options"]) if offer.get("offer_options")
                                                 else OFFER_OPTIONS_DEFAULT),
        # Montaz jako nabizena sluzba (Robert primo, 2026-09-28, viz
        # _offer_gross_total) - % z ceny sestavy. Od 2026-10-01 ji muze
        # zvolit Robert pri vytvoreni nabidky (offer_options.montaz_pct, i 0 =
        # bez montaze); nabidky bez vlastni volby ctou ZIVOU vychozi sazbu z
        # app_settings (stejne jako scene.html PRICING_CONFIG.montaz_pct), aby
        # jeji zmena platila okamzite i pro uz rozeslane nabidky. Stranka cte
        # jen toto jedno cislo (offer.montaz_pct) - rozhodnuti dela
        # _offer_montaz_pct, stejne jako u QR platby a objednavky.
        "montaz_pct": _offer_montaz_pct(_offer_options_from_row(offer), montaz_pct),
        # Sleva nabidky v % z ceny zbozi (bot16, 2026-10-07; 0 = bez slevy) - stranka ji ukaze v cenovem souhrnu, QR a objednavka ji pocitaji pres _offer_gross_total
        "discount_pct": _offer_discount_pct(_offer_options_from_row(offer)),
        # Montaz jako zatrhavaci volba u KAZDE nabidky se sazbou > 0 (bot8, 2026-10-06, Robert: "zatrhavaci sluzbu montaz (a kde Praha / Slavicin)"). PRIZNAK kvuli poradi
        # nasazeni: stranka (statika, zive hned) nabidne volbu u nabidek, ktere nejsou sestava do auta, JEN kdyz ho backend posle - starsi backend ho nema a stranka nechava puvodni chovani
        # (jinak by QR / objednavka, ktere pocita starsi _offer_gross_total, nesedely s cenou na strance)
        "montaz_volba": _je_auto_sestava(_offer_options_from_row(offer)),
        # Nabidka z konfigurace stolu (api/nabidka_z_konfigurace.py, bot5 2026-10-06): zdroj a verejna cast konfigurace; stranka podle `source` pouzije 3D prohlizec V3D a souhrn voleb misto vykresu
        "source": _offer_options_from_row(offer).get("source"),
        "configuration": _verejna_konfigurace(_offer_options_from_row(offer)),
        # Zakreslene zmeny v nabidce (api/offer_markup_requests.py, bot16 2026-10-07): PRIZNAK kvuli poradi nasazeni (statika je zive hned, API az 0:00/12:30) - stranka nastroj
        # nabidne JEN kdyz ho backend umi. Vlastnost NABIDKY (z konfigurace stolu / z Vandr karty), bez ohledu na roli tokenu (role = viewer_role; admin token odmita az POST, 403).
        "markup_requests": markup_requests,
        # Pricky do multiboxu - sety pro celou polici / suplik (api/nabidka_pricky.py, bot8 2026-10-07): null = nabidka je nenabizi (bez multiboxu / karty neaktivni / modul chybi); stranka sekci ukaze JEN kdyz klic prijde
        "pricky": pricky_blok,
    })


@app.get("/api/public/offers/<token>/image/<key>")
def public_offer_image(token, key):
    if key not in OFFER_VIEW_KEYS:
        return jsonify({"error": "Neplatný obrázek."}), 404
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
    finally:
        conn.close()
    if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
        return jsonify({"error": "Nabídka nebyla nalezena."}), 404
    stored_filename = offer[OFFER_VIEW_KEYS[key]]
    if not stored_filename:
        # narys_ghost/bokorys_ghost/pudorys_ghost jsou nepovinne - stare
        # nabidky (pred 2026-08-09) je nemaji ulozene vubec.
        return jsonify({"error": "Obrázek není u této nabídky k dispozici."}), 404
    try:
        with open(os.path.join(OFFER_IMAGES_DIR, stored_filename), "rb") as fh:
            data = fh.read()
    except OSError:
        return jsonify({"error": "Obrázek na disku chybí."}), 404
    mimetype = "image/jpeg" if stored_filename.lower().endswith(("jpg", "jpeg")) else "image/png"
    return Response(data, mimetype=mimetype, headers={"X-Content-Type-Options": "nosniff"})


@app.get("/api/public/offers/<token>/model")
def public_offer_model(token):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
    finally:
        conn.close()
    if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
        return jsonify({"error": "Nabídka nebyla nalezena."}), 404
    stored_filename = offer["view_3d_model"]
    if not stored_filename:
        return jsonify({"error": "Model není k dispozici."}), 404
    try:
        with open(os.path.join(OFFER_MODELS_DIR, stored_filename), "rb") as fh:
            data = fh.read()
    except OSError:
        return jsonify({"error": "Model na disku chybí."}), 404
    # bot10 2026-10-02 (3D model nabidky, viewer3d.js): model je za tokenem (soukromy), nesmi do sdilenych
    # cache (private) a prohlizec ho pri kazdem otevreni jen revaliduje pres ETag (304 = zadny prenos
    # 1-2 MB; admin muze model nahradit, proto ne max-age). Obsah nemenime, jen hlavicky.
    resp = Response(data, mimetype="model/gltf-binary",
                    headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-cache"})
    resp.set_etag(hashlib.sha256(data).hexdigest()[:32])
    return resp.make_conditional(request)


def _je_zamestnanec():
    """Prihlaseny ZAMESTNANEC (role z PERMISSION_ROLES, aktivni) - jeho zobrazeni nabidky se do statistik nepocita (bot5, 2026-10-06). Nikdy nesmi shodit verejny pozadavek."""
    try:
        from app import PERMISSION_ROLES
        u = current_user()
        return bool(u and u.get("active") and u.get("role") in PERMISSION_ROLES)
    except Exception:                                         # noqa: BLE001
        return False


def _zobrazeni_zamestnance(token, offer):
    """True = zobrazeni udelal zamestnanec: bud pres admin odkaz "Zobrazit online" (admin_view_token_hash), nebo je prihlaseny v adminu (session cookie).
    Robert 2026-10-06 ("nemuze to pocitat moje pristupy, to se musi hlidat"): takove zobrazeni se do statistik (Shlednuti podle IP, Podle stranky nabidky) nezapisuje."""
    if hashlib.sha256((token or "").encode()).hexdigest() == offer["admin_view_token_hash"]:
        return True
    return _je_zamestnanec()


@app.post("/api/public/offers/<token>/view")
def public_offer_view_start(token):
    # W4 (bot16, 2026-09-03): 30/h na IP - kazde volani je INSERT (UA az 500 B)
    limited = _public_offer_rate_limited(None, "view", 0, 30)
    if limited:
        return limited
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
            if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
                return jsonify({"error": "Nabídka nebyla nalezena."}), 404
            if _zobrazeni_zamestnance(token, offer):
                # zamestnanec (admin odkaz nebo prihlaseny v adminu): nic se nezapisuje, view_id null -> stranka neposila ani udalosti (viz viewId v nabidka-online.html)
                return jsonify({"view_id": None, "pocitano": False}), 200
            ip = _client_ip()
            user_agent = (request.headers.get("User-Agent") or "")[:500]
            now = datetime.datetime.now()
            cur.execute(
                "INSERT INTO scene_offer_views (offer_id, ip_address, user_agent, started_at, last_seen_at) "
                "VALUES (%s,%s,%s,%s,%s)",
                (offer["id"], ip, user_agent, now, now),
            )
            view_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"view_id": view_id}), 201


MAX_DWELL_MS = 30 * 60 * 1000  # 30 minut - pojistka proti zjevne nesmyslnym hodnotam z klienta

# Robert: "Kliky (na co klikli...)" - pevny seznam sledovanych prvku (NE
# volny text z klienta) - obsahovy engagement (obrazky, cena, kontakty),
# navigace (sipky/tecky) zamerne VYNECHANA - ta uz je 1:1 dohledatelna z
# poradi page_view eventu, sledovat by ji znamenalo jen sum bez noveho
# poznatku.
CLICK_TARGETS = (
    "image_narys", "image_bokorys", "image_pudorys", "image_view3d_a", "image_view3d_b",
    "total_price", "contact_email", "contact_phone", "contact_web",
    "interact_3d_model",  # zivy 3D model - prvni interakce (rotace/zoom) behem 1 shlednuti
    "item_product_link",  # klik na polozku kusovniku s odkazem na e-shop
    "download_pdf",       # tlacitko "Stahnout PDF" (bot6, 2026-08-05)
    "bom_highlight",      # klik na radek kusovniku -> zvyrazneni v 3D modelu
    "payment_qr",         # klik/tap na QR platbu
    # 3D prohlizec nabidky (bot10 2026-10-02, webapp/js/v3d/viewer3d.js) - detail udalosti
    # (id pohybu/pohled/rezim) server neuklada, jen cil.
    "v3d_view",           # pohled (zepredu/shora/z boku/iso/reset/cela obrazovka)
    "v3d_dims",           # prepnuti urovne kot
    "v3d_mode",           # prepnuti vzhledu (drateny/skutecny)
    "v3d_anim",           # otevreni/zavreni pohybu (supliky, dvirka, boxy, "otevrit vse")
    # zakreslene zmeny v nabidce (bot16, 2026-10-07, api/offer_markup_requests.py, webapp/nabidka-online.html) - statistika pouziti nastroje
    "markup_request_draw",  # zakaznik otevrel kreslici nastroj (klik "Zakreslit zmenu")
    "markup_request_sent",  # zakaznik odeslal zakreslenou zmenu (uspesny POST .../markup-requests)
)


@app.post("/api/public/offers/<token>/event")
def public_offer_event(token):
    body = request.get_json(silent=True) or {}
    view_id = body.get("view_id")
    page_index = body.get("page_index")
    page_key = body.get("page_key")
    dwell_ms = body.get("dwell_ms")
    event_type = body.get("event_type") or "page_view"
    target = body.get("target")
    scroll_pct = body.get("scroll_pct")

    if not isinstance(view_id, int) or not isinstance(page_index, int) or page_key not in OFFER_PAGE_KEYS:
        return jsonify({"error": "Neplatná data události."}), 400
    if event_type not in ("page_view", "click"):
        return jsonify({"error": "Neplatný typ události."}), 400
    if event_type == "click" and target not in CLICK_TARGETS:
        return jsonify({"error": "Neplatný cíl kliknutí."}), 400
    if event_type == "page_view":
        target = None
    try:
        dwell_ms = max(0, min(int(dwell_ms or 0), MAX_DWELL_MS))
    except (TypeError, ValueError):
        dwell_ms = 0
    try:
        scroll_pct = max(0, min(int(scroll_pct), 100)) if scroll_pct is not None else None
    except (TypeError, ValueError):
        scroll_pct = None

    # Robert 2026-08-05: pri rychlych po sobe jdoucich udalostech ze stejneho
    # shlednuti (klik+scroll temer soucasne) obcas INSERT+UPDATE nad stejnym
    # view_id uvaznou v DB deadlocku (errno 1213) - jde jen o analytiku, ne o
    # kritickou cestu, takze se nesnazime vyhnout kontenci pretypovanim
    # dotazu, staci na deadlock/lock-wait-timeout par kratkych pokusu znovu.
    DEADLOCK_ERRNOS = (1213, 1205)
    attempts = 0
    while True:
        attempts += 1
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                offer = _resolve_offer_by_token(cur, token)
                # I5 (bot16, 2026-09-03, revize bot3): stejna podminka jako
                # detail - po deaktivaci/expiraci uz statistiky nesbirat.
                if not offer or not offer["is_active"]:
                    return jsonify({"error": "Nabídka nebyla nalezena."}), 404
                if offer["expires_at"] < datetime.datetime.now():
                    return jsonify({"error": "Platnost nabídky vypršela.", "expired": True}), 410
                # view_id MUSI patrit k timhle tokenem dohledanemu offeru -
                # jinak by kdokoli se znamym cizim view_id mohl zapisovat
                # udalosti do ciziho shlednuti.
                cur.execute("SELECT id FROM scene_offer_views WHERE id=%s AND offer_id=%s", (view_id, offer["id"]))
                if not cur.fetchone():
                    return jsonify({"error": "Neplatné view_id."}), 400
                now = datetime.datetime.now()
                cur.execute(
                    "INSERT INTO scene_offer_page_events "
                    "(view_id, page_index, page_key, event_type, target, entered_at, dwell_ms, scroll_pct) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (view_id, page_index, page_key, event_type, target, now, dwell_ms, scroll_pct),
                )
                cur.execute("UPDATE scene_offer_views SET last_seen_at=%s WHERE id=%s", (now, view_id))
            conn.commit()
            return jsonify({"status": "ok"}), 201
        except pymysql.err.OperationalError as e:
            if e.args and e.args[0] in DEADLOCK_ERRNOS and attempts < 3:
                time.sleep(0.05 * attempts)
                continue
            raise
        finally:
            conn.close()


MAX_NOTE_LEN = 2000  # jedina pojistka proti zneuziti - token samotny je hlavni ochrana (stejna uroven jako u /event)
MAX_NAME_LEN = 255


@app.get("/api/public/ares/<ico>")
def public_ares_lookup(ico):
    """Doplneni firemnich udaju podle ICO (bot4, Robert 2026-08-06:
    "za ico se doplni automaticky napriklad z justice.cz") - ARES REST
    API (ares.gov.cz, stejna zdrojova data jako justice.cz, verejne bez
    klice). Proxy pres backend kvuli CORS + at neprozrazujeme klientum
    strukturu externi sluzby. Jen normalizovany vytah: nazev, DIC,
    adresa."""
    # W1 (bot16, 2026-09-03, revize bot3): striktni ^\d{8}$ misto tiche
    # normalizace + limit 10/10 min na IP + timeout 4 s - endpoint je bez
    # tokenu a synchronni gunicorn (2 workery) by par soubeznych pomalych
    # dotazu na ARES zablokovalo pro celou appku.
    if not re.fullmatch(r"\d{8}", ico or ""):
        return jsonify({"error": "IČO musí mít 8 číslic."}), 400
    if _rate_limited(f"ares:{_client_ip()}", max_requests=10, window_seconds=600):
        return jsonify({"error": "Příliš mnoho dotazů na ARES. Zkuste to prosím později."}), 429
    try:
        req = urllib.request.Request(
            f"https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return jsonify({"error": "Subjekt s tímto IČO nebyl nalezen."}), 404
        return jsonify({"error": "Registr ARES je momentálně nedostupný."}), 502
    except Exception:
        return jsonify({"error": "Registr ARES je momentálně nedostupný."}), 502
    return jsonify({
        "ico": ico,
        "name": data.get("obchodniJmeno") or "",
        "dic": data.get("dic") or "",
        "address": (data.get("sidlo") or {}).get("textovaAdresa") or "",
    })


@app.post("/api/public/offers/<token>/accept")
def public_offer_accept(token):
    """Souhlas/objednavka (Robert: "Souhlasim / objednavam") - jednoduchy
    el. souhlas (jmeno + potvrzeni), NE plnohodnotny e-signing. Puvodne
    append-only; od 2026-09-03 (bot16, revize bot3 - W2) max jedno
    prijeti na nabidku (dalsi -> 409 already_accepted) + rate limit
    3/h na token a 10/h na IP - frontend po uspechu stejne ukazuje "uz
    objednano" (viz public_offer_get - "accepted")."""
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Vyplňte prosím jméno."}), 400
    if len(name) > MAX_NAME_LEN:
        return jsonify({"error": f"Jméno je příliš dlouhé (max {MAX_NAME_LEN} znaků)."}), 400
    # Firemni udaje (bot4, Robert 2026-08-06: tabulka inicialu u tlacitka
    # objednat, doplnovana z ARES podle ICO) - Robert primo, 2026-09-14
    # ("povinne vyplneni udajů od klienta"): VSECHNA pole ted povinna
    # (drive nepovinna), jen se orezou na delky sloupcu.
    def _req(field, maxlen):
        v = (body.get(field) or "").strip()
        return v[:maxlen]
    company_ico = _req("company_ico", 20)
    company_name = _req("company_name", 255)
    company_dic = _req("company_dic", 20)
    company_address = _req("company_address", 500)
    contact_email = _req("contact_email", 255)
    contact_phone = _req("contact_phone", 50)
    if not re.match(r"^\d{8}$", company_ico or ""):
        return jsonify({"error": "Vyplňte prosím IČO (8 číslic)."}), 400
    if not company_name:
        return jsonify({"error": "Vyplňte prosím název firmy."}), 400
    if not company_dic:
        return jsonify({"error": "Vyplňte prosím DIČ."}), 400
    if not company_address:
        return jsonify({"error": "Vyplňte prosím adresu."}), 400
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", contact_email or ""):
        return jsonify({"error": "Vyplňte prosím platný e-mail."}), 400
    if not contact_phone:
        return jsonify({"error": "Vyplňte prosím telefon."}), 400
    limited = _public_offer_rate_limited(token, "react", 3, 10)
    if limited:
        return limited

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
            if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
                return jsonify({"error": "Nabídka nebyla nalezena."}), 404
            conflict = _offer_reaction_conflict(cur, offer["id"], for_decline=False)
            if conflict:
                return conflict
            guest_id = _quote_guest_id()
            ip = _client_ip()
            now = datetime.datetime.now()
            # Robert primo, 2026-09-14 ("moznost objednat vice ks
            # vyrobku") - qty + doprava z ulozenych voleb objednavky
            # (stejny zdroj jako public_offer_payment_qr), aby vznikla
            # objednavka mela STEJNOU castku, jakou si zakaznik na
            # strance uz videl a odsouhlasil.
            order_prefs_for_total = _load_order_prefs(cur, offer["id"], guest_id)
            montaz_pct_for_total = get_setting(cur, "montaz_pct", "0")
            # pricky do multiboxu (bot8, 2026-10-07): vyber se overuje PRED zapisem prijeti; ceny z karet, cena za 1 kus sestavy se nasobi qty
            try:
                pricky_res = _pricky_vyber(cur, offer, token, body.get("pricky"))
            except ValueError:
                return jsonify({"error": "Výběr příček není platný, obnovte stránku."}), 400
            prefs_celkem = dict(order_prefs_for_total) if order_prefs_for_total else {}
            if pricky_res:
                prefs_celkem["pricky_net"] = pricky_res["net"]
            montaz_poznamka = _montaz_poznamka(cur, offer, prefs_celkem, montaz_pct_for_total)          # zvolena montaz (misto + cena) do poznamky objednavky a e-mailu
            pricky_poznamka = _pricky_poznamka(pricky_res, _clamp_qty(order_prefs_for_total["qty"] if order_prefs_for_total else None))
            poznamky_objednavky = "\n".join(x for x in (montaz_poznamka, pricky_poznamka) if x)
            cur.execute(
                "INSERT INTO scene_offer_acceptances (offer_id, guest_id, name, company_ico, company_name, "
                "company_dic, company_address, contact_email, contact_phone, ip_address, accepted_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (offer["id"], guest_id, name, company_ico, company_name, company_dic,
                 company_address, contact_email, contact_phone, ip, now),
            )
            # Robert primo, 2026-09-14 (pres bot16): "v pripade objednani
            # se zadane udaje propisuji do adresare zakazniku a do
            # objednavek" + (primo): "je potreba u objednavky evidovat VS
            # nabidky, resp VS platby, podle ktere se to pak sparuje" -
            # viz orders.py::create_order_from_scene_offer. STEJNA
            # TRANZAKCE jako prijeti vyse (bud obojí, nebo nic - selze-li
            # zalozeni objednavky, cele prijeti se vrati zpet a zakaznik
            # muze kliknout znovu, misto tiche napulcestne mezistavu).
            # Trvala testovaci nabidka (TEST_OFFER_NUMBER) vynechana
            # schvalne, at neplodi realne zakaznicke ucty/objednavky pri
            # kazdem otestovani tlacitka.
            order_number = None
            if offer["offer_number"] != TEST_OFFER_NUMBER:
                try:
                    _order_id, order_number = create_order_from_scene_offer(
                        cur, offer, name=name, company_ico=company_ico, company_name=company_name,
                        company_dic=company_dic, company_address=company_address,
                        contact_email=contact_email, contact_phone=contact_phone,
                        total_czk=_offer_gross_total(offer, prefs_celkem, montaz_pct_for_total),
                        # Robert primo, 2026-09-16: "seznam dilu se musi
                        # automaticky propisovat" - offer["items"] je vzdy
                        # za JEDEN kus sestavy, qty_multiplier (pocet
                        # objednanych kusu CELE sestavy) nasobi kazdou
                        # polozku, at odpovida i castce v total_czk.
                        qty_multiplier=_clamp_qty(order_prefs_for_total["qty"] if order_prefs_for_total else None),
                        extra_note=poznamky_objednavky or None,
                        extra_items=(pricky_res["radky"] if pricky_res else None),
                    )
                except Exception as e:
                    app.logger.error(
                        "Založení objednávky z nabídky %s selhalo: %s", offer["offer_number"], e
                    )
                    return jsonify({
                        "error": "Nepodařilo se zpracovat objednání, zkuste to prosím znovu "
                                 "nebo nás kontaktujte."
                    }), 500
        conn.commit()
    finally:
        conn.close()

    company_lines = ""
    if company_ico or company_name:
        company_lines = (
            f"Firma: {company_name or '-'}\n"
            f"IČO: {company_ico or '-'}\n"
            f"DIČ: {company_dic or '-'}\n"
            f"Adresa: {company_address or '-'}\n"
            f"E-mail: {contact_email or '-'}\n"
            f"Telefon: {contact_phone or '-'}\n\n"
        )
    # E-maily z trvale testovaci nabidky se oznacuji prefixem, at je na
    # prvni pohled poznat, ze nejde o realneho klienta (Robert 2026-08-06:
    # "do e-mailu mne prisla testovaci zprava").
    test_prefix = "[TESTOVACÍ NABÍDKA] " if offer["offer_number"] == TEST_OFFER_NUMBER else ""
    # bot7 2026-08-11 (incident: rucni curl test primo na 127.0.0.1:8090
    # poslal Robertovi realny e-mail s nefunkcnim odkazem na
    # "http://127.0.0.1:8090/...") - odkaz v e-mailu (tady i u decline/
    # note nize) STAVET Z APP_BASE_URL, NE z request.host_url. Ten druhy
    # odpovida tomu, KAM presne pozadavek dorazil (pri primem volani
    # backendu mimo nginx je to jen lokalni port), ne verejne adrese
    # webu - pro odkaz v e-mailu je potreba vzdy ta druha.
    # DALSI VYJIMKA z bodu 16 (Robert primo, 2026-09-15, po dotazu "proc
    # je to v odchozi poste a ne v prichozi"): jediny prijemce tady je
    # VZDY Robertova vlastni adresa (SUPPLIER["email"]) - interni
    # systemova notifikace, ne odchozi komunikace s tretí stranou, ktere
    # pravidlo 16 chrani. Posila se PRIMO, mimo pending-frontu (viz
    # WORKFLOW.md bod 16, stejny vzor jako auth_forgot_password/
    # auth_send_temp_password - zapsano i do
    # qa_checks._SEND_EMAIL_APPROVED_WRAPPERS). PUVODNI verze (bot10,
    # 2026-08-26) tohle schvalne posilala do fronty misto primo, protoze
    # tehdy jeste tahle vyjimka neexistovala.
    try:
        send_email(
            SUPPLIER["email"],
            # Robert primo, 2026-09-14: "potrebuji aby mě prisel
            # email s predmetem Objednavka dle cisla nabidky" -
            # drive "Nabídka X potvrzena - jmeno", jmeno klienta
            # zustava v tele e-mailu (prvni radek nize), jen uz
            # neni v predmetu.
            f"{test_prefix}Objednávka {offer['offer_number']}",
            f"Klient {name} potvrdil objednání nabídky {offer['offer_number']}.\n\n"
            + company_lines +
            f"Čas: {now.strftime('%d.%m.%Y %H:%M')}\n"
            f"IP adresa: {ip}\n"
            + (f"Založena objednávka: {order_number} (položky převzaty automaticky "
               f"z nabídky, zkontrolujte prosím)\n" if order_number else "")
            + (f"{poznamky_objednavky}\n" if poznamky_objednavky else "") +
            f"Odkaz na nabídku: {APP_BASE_URL}/nabidka-online.html?t={token}",
        )
    except Exception as e:
        # E-mail je informativni navazba, ne kriticka cast tranzakce -
        # objednani uz je v DB bezpecne ulozeno, selhani odeslani se jen
        # zaloguje (stejny princip jako auth_forgot_password).
        app.logger.warning("Nepodařilo se odeslat e-mail o objednání nabídky %s: %s", offer["offer_number"], e)

    return jsonify({"status": "ok", "accepted_at": now.isoformat(), "order_number": order_number}), 201


@app.post("/api/public/offers/<token>/decline")
def public_offer_decline(token):
    """Protejsek k public_offer_accept vyse (Robert 2026-08-10: "nemam
    zajem" jako druha moznost vedle "Souhlasim / objednavam") - dava
    adminovi signal, ze zakaznik nabidku videl a NEreaguje kladne,
    misto aby nabidka jen tise leznla bez zpetne vazby. Duvod je
    NEPOVINNY (zakaznik nemusi vysvetlovat, staci kliknuti). Od
    2026-09-03 (bot16, revize bot3 - W2) uz NE append-only: opakovane
    odmitnuti -> 409 already_declined, odmitnuti prijate -> 409
    already_accepted, + rate limit jako u accept. Dalsi pripominky
    posila zakaznik pres /note."""
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip() or None
    if reason and len(reason) > MAX_NOTE_LEN:
        return jsonify({"error": f"Text je příliš dlouhý (max {MAX_NOTE_LEN} znaků)."}), 400
    limited = _public_offer_rate_limited(token, "react", 3, 10)
    if limited:
        return limited

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
            if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
                return jsonify({"error": "Nabídka nebyla nalezena."}), 404
            conflict = _offer_reaction_conflict(cur, offer["id"], for_decline=True)
            if conflict:
                return conflict
            guest_id = _quote_guest_id()
            ip = _client_ip()
            now = datetime.datetime.now()
            cur.execute(
                "INSERT INTO scene_offer_declines (offer_id, guest_id, reason, ip_address, declined_at) "
                "VALUES (%s,%s,%s,%s,%s)",
                (offer["id"], guest_id, reason, ip, now),
            )
        conn.commit()
    finally:
        conn.close()

    test_prefix = "[TESTOVACÍ NABÍDKA] " if offer["offer_number"] == TEST_OFFER_NUMBER else ""
    # OPRAVA (bot10, 2026-08-26, schvaleno bot3) - viz stejna oprava u
    # public_offer_accept vys.
    try:
        main_conn = get_conn()
        try:
            with main_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO system_emails (user_id, kind, recipient_email, subject, body_text, status, trigger_type) "
                    "VALUES (NULL,'scene_offer_declined',%s,%s,%s,'pending','auto')",
                    (
                        SUPPLIER["email"],
                        f"{test_prefix}Nabídka {offer['offer_number']} - klient nemá zájem / má připomínku",
                        f"Klient u nabídky {offer['offer_number']} kliknul na 'Nemám zájem / mám připomínku'.\n\n"
                        + (f"Důvod:\n{reason}\n\n" if reason else "Důvod nebyl vyplněn.\n\n")
                        + f"Čas: {now.strftime('%d.%m.%Y %H:%M')}\n"
                        f"IP adresa: {ip}\n"
                        f"Odkaz na nabídku: {APP_BASE_URL}/nabidka-online.html?t={token}",
                    ),
                )
            main_conn.commit()
        finally:
            main_conn.close()
    except Exception as e:
        app.logger.warning("Nepodařilo se zařadit e-mail o odmítnutí nabídky %s do fronty: %s", offer["offer_number"], e)

    return jsonify({"status": "ok", "declined_at": now.isoformat()}), 201


MAX_MARKUPS = 300
MAX_MARKUP_POINTS = 500


@app.put("/api/public/offers/<token>/markups")
def public_offer_markups_save(token):
    """Ulozeni oznaceni/kresby (bot4, 2026-08-05, Robert: "na konci dej
    nejak tlacitko ulozit at vidis co jsem kreslil" + "zeleno modrou
    barvou dela poznamky admin a cervene dela zakaznik"). Kazda znacka
    nese author ('admin'|'client') urceny VYHRADNE podle pouziteho
    tokenu (admin "Zobrazit online" vs klientsky odkaz) - klient tedy
    nemuze prepsat/smazat adminovy znacky ani naopak: ulozeni nahradi
    jen znacky VLASTNI role, ciziho autora se nedotkne. Vektorova data
    (zlomky 0..1) - viz sql/2026-08-05_scene_offer_markups.sql."""
    # QA bezpecnostni nalez (2026-09-05): chybel rate-limit (na rozdil od
    # sourozeneckych "react"/"note" verejnych endpointu v tomtez souboru) -
    # volnejsi strop nez u nich, znacky se behem kresleni ukladaji casteji.
    limited = _public_offer_rate_limited(token, "markups", 20, 60)
    if limited:
        return limited
    body = request.get_json(silent=True) or {}
    marks = body.get("marks")
    if not isinstance(marks, list):
        return jsonify({"error": "marks musí být pole."}), 400
    if len(marks) > MAX_MARKUPS:
        return jsonify({"error": f"Příliš mnoho značek (max {MAX_MARKUPS})."}), 400

    cleaned = []
    for m in marks:
        if not isinstance(m, dict):
            return jsonify({"error": "Neplatná značka."}), 400
        kind = m.get("kind")
        page = m.get("page")
        view = m.get("view") or None
        number = m.get("number")
        label = m.get("label")
        points = m.get("points")
        if kind not in ("pen", "number"):
            return jsonify({"error": "Neplatný typ značky."}), 400
        if page not in OFFER_PAGE_KEYS:
            return jsonify({"error": "Neplatná stránka značky."}), 400
        if view is not None and view not in OFFER_VIEW_KEYS:
            return jsonify({"error": "Neplatný výkres značky."}), 400
        if kind == "pen" and view is None:
            return jsonify({"error": "Kreslení je možné jen na výkresech."}), 400
        if kind == "number":
            if not isinstance(number, int) or not (1 <= number <= 999):
                return jsonify({"error": "Neplatné číslo značky."}), 400
            if label is not None:
                if not isinstance(label, str):
                    return jsonify({"error": "Neplatný popisek značky."}), 400
                # viceradkovy popisek (Robert 2026-08-05: "1 radek je
                # malo") - \n se zachovava, ostatni ridici znaky pryc
                label = "".join(ch for ch in label if ch == "\n" or ord(ch) >= 32)
                label = label.strip()[:500] or None
        else:
            number = None
            label = None
        if not isinstance(points, list) or not points or len(points) > MAX_MARKUP_POINTS:
            return jsonify({"error": "Neplatné body značky."}), 400
        clean_points = []
        for p in points:
            if not isinstance(p, dict):
                return jsonify({"error": "Neplatný bod značky."}), 400
            try:
                x, y = float(p.get("x")), float(p.get("y"))
            except (TypeError, ValueError):
                return jsonify({"error": "Neplatné souřadnice značky."}), 400
            # znacka muze mirne pretekat okraj obrazku (kruzek na hrane) -
            # tolerance, ale zadne divoke hodnoty
            if not (-0.5 <= x <= 1.5 and -0.5 <= y <= 1.5):
                return jsonify({"error": "Souřadnice značky mimo rozsah."}), 400
            clean_points.append({"x": round(x, 4), "y": round(y, 4)})
        cleaned.append({"kind": kind, "page": page, "view": view, "number": number,
                        "label": label, "points": clean_points})

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
            if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
                return jsonify({"error": "Nabídka nebyla nalezena."}), 404
            role = "admin" if hashlib.sha256(token.encode()).hexdigest() == offer["admin_view_token_hash"] else "client"
            for m in cleaned:
                m["author"] = role
            cur.execute("SELECT data FROM scene_offer_markups WHERE offer_id=%s", (offer["id"],))
            row = cur.fetchone()
            try:
                existing = json.loads(row["data"]) if row else []
            except (TypeError, ValueError):
                existing = []
            # znacky bez author (ulozene pred timhle rozsirenim) = client
            kept = [m for m in existing if m.get("author", "client") != role]
            merged = kept + cleaned
            if len(merged) > MAX_MARKUPS * 2:
                return jsonify({"error": "Příliš mnoho značek celkem."}), 400
            cur.execute(
                "INSERT INTO scene_offer_markups (offer_id, guest_id, data) VALUES (%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE guest_id=VALUES(guest_id), data=VALUES(data)",
                (offer["id"], _quote_guest_id(), json.dumps(merged, ensure_ascii=False)),
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "count": len(cleaned)})


@app.post("/api/public/offers/<token>/note")
def public_offer_note(token):
    """Dotaz/poznamka ke strance nebo konkretni polozce (Robert: "ke
    konkretni polozce nebo strance... automaticky i v emailu admina")."""
    body = request.get_json(silent=True) or {}
    note_body = (body.get("body") or "").strip()
    page_key = body.get("page_key")
    item_name = (body.get("item_name") or "").strip() or None

    if not note_body:
        return jsonify({"error": "Vyplňte prosím text dotazu."}), 400
    if len(note_body) > MAX_NOTE_LEN:
        return jsonify({"error": f"Text je příliš dlouhý (max {MAX_NOTE_LEN} znaků)."}), 400
    if page_key is not None and page_key not in OFFER_PAGE_KEYS:
        return jsonify({"error": "Neplatná stránka."}), 400
    if item_name and len(item_name) > 500:
        item_name = item_name[:500]
    # W3 (bot16, 2026-09-03): 5/h na token + 20/h na IP - kazdy dotaz =
    # radek + e-mail do fronty dodavateli.
    limited = _public_offer_rate_limited(token, "note", 5, 20)
    if limited:
        return limited

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
            if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
                return jsonify({"error": "Nabídka nebyla nalezena."}), 404
            guest_id = _quote_guest_id()
            ip = _client_ip()
            now = datetime.datetime.now()
            cur.execute(
                "INSERT INTO scene_offer_notes (offer_id, guest_id, page_key, item_name, body, ip_address, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (offer["id"], guest_id, page_key, item_name, note_body, ip, now),
            )
        conn.commit()
    finally:
        conn.close()

    context = item_name or (page_key or "obecný dotaz")
    test_prefix = "[TESTOVACÍ NABÍDKA] " if offer["offer_number"] == TEST_OFFER_NUMBER else ""
    # OPRAVA (bot10, 2026-08-26, schvaleno bot3) - viz stejna oprava u
    # public_offer_accept vys.
    try:
        main_conn = get_conn()
        try:
            with main_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO system_emails (user_id, kind, recipient_email, subject, body_text, status, trigger_type) "
                    "VALUES (NULL,'scene_offer_note',%s,%s,%s,'pending','auto')",
                    (
                        SUPPLIER["email"],
                        f"{test_prefix}Dotaz k nabídce {offer['offer_number']} - {context}",
                        f"K nabídce {offer['offer_number']} přišel dotaz/poznámka:\n\n"
                        f"{'Položka: ' + item_name if item_name else 'Stránka: ' + (page_key or '-')}\n\n"
                        f"{note_body}\n\n"
                        f"Čas: {now.strftime('%d.%m.%Y %H:%M')}\n"
                        f"IP adresa: {ip}\n"
                        f"Odkaz na nabídku: {APP_BASE_URL}/nabidka-online.html?t={token}",
                    ),
                )
            main_conn.commit()
        finally:
            main_conn.close()
    except Exception as e:
        app.logger.warning("Nepodařilo se zařadit e-mail o dotazu k nabídce %s do fronty: %s", offer["offer_number"], e)

    return jsonify({"status": "ok"}), 201


# ============================================================
# QR Platba (Robert 2026-08-05: "QR kod primo pro zaplaceni... bankovnim
# prevodem v mobilu klienta" - platba kartou vyzaduje platebni branu,
# ktera v projektu neexistuje; potvrzeno pres AskUserQuestion: "jen QR
# na bankovni prevod"). Cesky standard "QR Platba" = SPAYD retezec
# (SPD*1.0*ACC:...*AM:...) vyzadujici IBAN - SUPPLIER['bank_account']
# je v lokalnim formatu cislo/kod_banky, prevadime za behu (ISO 13616
# mod-97-10, obecny algoritmus, zadna banka-specificka logika).
# ============================================================

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


ORDER_PREF_CHOICES = {
    "shipping_method": ("vlastni", "toptrans"),
    "payment_method": ("dobirka", "zaloha"),
    "delivery_state": ("smontovano", "demontovano"),
}


def _load_order_prefs(cur, offer_id, guest_id):
    cur.execute(
        "SELECT shipping_method, payment_method, deposit_pct, delivery_state, qty, "
        "delivery_zip, toptrans_price_czk, montaz_zvolena, montaz_misto "
        "FROM scene_offer_order_prefs WHERE offer_id=%s AND guest_id=%s",
        (offer_id, guest_id),
    )
    return cur.fetchone()


# Robert primo, 2026-09-14: "moznost objednat vice ks vyrobku" - JEDNO
# misto pravdy pro castku, kterou zakaznik skutecne plati (QR platba i
# vznikla objednavka v create_order_from_scene_offer) - musi vracet
# STEJNE cislo jako JS effectiveNetTotal/withVat v nabidka-online.html.
def _clamp_qty(raw, default=1):
    """Bezpecne mnozstvi (1-99) - sdileny helper pro qty napric online
    nabidkami (order-prefs, toptrans-price), at se validace nerozjede
    na 2 mistech. Robert primo (pres bot3, 2026-09-14): "navysil pocet
    kusu (qty), ale cena Toptransu se vubec nezvedla" - jeden z
    korenovych bugu byl presne tenhle druh rozjezdu, viz
    public_offer_toptrans_price nize."""
    if raw is None:
        return default
    try:
        return max(1, min(99, int(raw)))
    except (TypeError, ValueError):
        return default


def _offer_options_from_row(offer):
    try:
        return json.loads(offer["offer_options"]) if offer.get("offer_options") else {}
    except (TypeError, ValueError):
        return {}


def _offer_montaz_pct(offer_options, global_pct=0):
    """Sazba montaze (% z ceny) platna pro KONKRETNI nabidku - JEDINE misto rozhodnuti pro verejny payload (public_offer_get),
    QR platbu i vznikajici objednavku (_offer_gross_total). Volba zvolena pri vytvoreni nabidky (offer_options.montaz_pct,
    0 = bez montaze) ma prednost; nabidky bez ni (starsi, Vandr) pouzivaji ZIVOU vychozi sazbu z app_settings."""
    own = _sanitize_montaz_pct(offer_options.get("montaz_pct")) if isinstance(offer_options, dict) else None
    if own is not None:
        return own
    try:
        return max(0.0, float(global_pct or 0))
    except (TypeError, ValueError):
        return 0.0


def _offer_discount_pct(offer_options):
    """Sleva nabidky v % (0.0 = bez slevy) - JEDINE misto rozhodnuti pro verejny payload i vypocet castky k uhrade (_offer_gross_total, _montaz_poznamka)."""
    own = _sanitize_discount_pct(offer_options.get("discount_pct")) if isinstance(offer_options, dict) else None
    return own or 0.0


def _offer_discount_net(offer_options, items_net):
    """Castka slevy (Kc bez DPH, zaokrouhleno na haliře - pul halire nahoru, STEJNE jako JS Math.round(cena * pct) / 100 na strance) z ceny zbozi VCETNE poctu kusu, BEZ dopravy a montaze; 0.0 bez slevy."""
    pct = _offer_discount_pct(offer_options)
    return int(float(items_net) * pct + 0.5) / 100 if pct else 0.0


def _offer_montaz_net(offer_options, items_net, prefs, global_pct=0):
    """JEDINE misto, kde se montaz nasobi procentem: cena montaze (bez DPH) zvolene zakaznikem v online nabidce - 0, kdyz ji nezvolil
    (prefs.montaz_zvolena) nebo je sazba nabidky 0 (= montaz se v nabidce nenabizi, napr. nabidky z konfigurace mimo CR). `items_net` = cisty soucet
    polozek VCETNE poctu kusu, BEZ dopravy; sazba z _offer_montaz_pct (vlastni volba nabidky, jinak zivá vychozi z app_settings)."""
    if not _je_auto_sestava(offer_options):
        return 0.0                                                    # stoly a ostatni nabidky: montaz je jen informace pod tabulkou (Robert 2026-10-06), ne volba k platbe
    montaz_pct = _offer_montaz_pct(offer_options, global_pct)
    if prefs and prefs.get("montaz_zvolena") and montaz_pct:
        return round(items_net * montaz_pct / 100, 2)
    return 0.0


def _montaz_poznamka(cur, offer, prefs, global_pct=0):
    """Text o montazi, kterou zakaznik zvolil v online nabidce (poznamka objednavky a e-mail o prijeti): "Montáž: ano, místo Praha, +11 500 Kč bez DPH
    (15 % z ceny zboží)"; prazdny retezec, kdyz ji nezvolil nebo je sazba nabidky 0. Cena z _offer_montaz_net = STEJNE cislo jako v QR / objednavce."""
    offer_options = _offer_options_from_row(offer)
    qty = max(1, int(prefs["qty"])) if (prefs and prefs.get("qty")) else 1
    zbozi = float(offer["total_price"]) * qty
    sleva = _offer_discount_net(offer_options, zbozi)
    pricky = float((prefs or {}).get("pricky_net") or 0.0) * qty                       # pricky do multiboxu (bot8) jsou soucasti zakladu (bez slevy - cena z karet)
    cena = _offer_montaz_net(offer_options, (round(zbozi - sleva, 2) if sleva else zbozi) + pricky, prefs, global_pct)           # montaz z ceny zbozi PO sleve + pricky (stejne jako _offer_gross_total a stranka)
    if not cena:
        return ""
    pct = _offer_montaz_pct(offer_options, global_pct)
    klic = prefs.get("montaz_misto")
    misto = _montaz_mista_map(cur, jen_aktivni=False).get(klic) if klic else None
    pct_txt = str(int(pct)) if float(pct).is_integer() else str(pct).replace(".", ",")
    cena_txt = f"{cena:,.2f}".replace(",", " ").replace(".", ",")
    cena_txt = cena_txt[:-3] if cena_txt.endswith(",00") else cena_txt
    return f"Montáž: ano, místo {misto or 'neurčeno'}, +{cena_txt} Kč bez DPH ({pct_txt} % z ceny zboží{' po slevě' if sleva else ''})"


# ---------------------------------------------------------------------------------------------------------------------
# PRICKY DO MULTIBOXU (bot8, 2026-10-07; Robert: "nabidnout vzdy nejake varianty setu, vzdy pro celou polici/suplik s multiboxy", docs/KONTRAKT_NABIDKA_PRICKY.md)
# Sety (bez / zakladni / stredni / plny) pro kazdou polici / suplik s multiboxy ve Vandr modelu nabidky; zakaznik je vybira na strance (vizualne ve 3D), vyber jde na server jen v QR (?pr=) a pri prijeti
# (pole `pricky`, "s1:pln,s2:zak") - do scene_offer_order_prefs se NEUKLADA (bez DDL). Boxy a skupiny se berou ze spec ulozeneho GLB, ceny z karet (SKU MBX-PRICKA-*); verejnosti se sekce nabizi jen kdyz jsou
# obe karty aktivni (pravidlo 54), admin (odkaz "Zobrazit online") ji vidi i driv. Cena pricek za 1 kus sestavy bez DPH (prefs["pricky_net"]) se nasobi poctem kusu a je soucasti zakladu pro montaz.
_PRICKY_SPEC_CACHE = {}


def _pricky_spec(offer):
    """Spec v3d zakaznickeho GLB nabidky (jen cteni, cache podle id nabidky a jmena souboru modelu) nebo None."""
    fn = offer.get("view_3d_model")
    if not fn or v3d_glb is None:
        return None
    cesta = os.path.join(OFFER_MODELS_DIR, fn)
    try:
        key = (offer["id"], fn, os.stat(cesta).st_mtime_ns)             # nahrazeny soubor modelu (jiny cas) = nova polozka cache
    except OSError:
        return None
    if key in _PRICKY_SPEC_CACHE:
        return _PRICKY_SPEC_CACHE[key]
    spec = None
    try:
        with open(cesta, "rb") as fh:
            spec = v3d_glb.embedded_spec(fh.read())
    except Exception:                                       # noqa: BLE001 - chybejici / rozbity model = prislusenstvi se nenabizi, nabidka funguje dal
        spec = None
    if len(_PRICKY_SPEC_CACHE) > 64:
        _PRICKY_SPEC_CACHE.clear()
    _PRICKY_SPEC_CACHE[key] = spec if isinstance(spec, dict) else None
    return _PRICKY_SPEC_CACHE[key]


def _pricky_kontext(cur, offer, viewer_is_admin):
    """{"spec", "boxy", "skupiny", "ceny", "zapnuto", "povoleno"} nebo None (modul chybi / model nema boxy znameho typu).
    boxy = boxy skupin, ktere se divakovi smi nabidnout (nabidka_pricky.dostupne_boxy: vsechny dily skupiny maji kartu s cenou a verejnosti i aktivni; admin vidi i neaktivni = nahled pred aktivaci);
    zapnuto = verejnosti se nabizi aspon jedna skupina; povoleno = divak ma co vybirat (zapnuto, nebo je admin a nejaka skupina ma karty s cenou)."""
    if nabidka_pricky is None:
        return None
    spec = _pricky_spec(offer)
    if not spec or not spec.get("mbx"):
        return None
    ceny = nabidka_pricky.nacti_ceny(cur)
    vse = nabidka_pricky.boxy_ze_spec(spec)
    if not vse:
        return None
    verejne = nabidka_pricky.dostupne_boxy(vse, ceny, False)
    boxy = nabidka_pricky.dostupne_boxy(vse, ceny, True) if viewer_is_admin else verejne
    if not boxy:
        return None
    return {"spec": spec, "boxy": boxy, "skupiny": nabidka_pricky.skupiny_z_boxu(boxy, ceny), "ceny": ceny, "zapnuto": bool(verejne), "povoleno": True}


def _pricky_je_admin(token, offer):
    return hashlib.sha256((token or "").encode()).hexdigest() == offer["admin_view_token_hash"]


def _pricky_vyber(cur, offer, token, raw):
    """Overeny vyber pricek PO BOXECH ze zapisu "b01:6,b02:2" (QR, prijeti): vraci nabidka_pricky.spocti(...) + "vyber" (cisty), nebo None pro prazdny vyber (nebo same nuly).
    Neplatny zapis, neznamy box, pocet nad pocet slotu, nabidka bez pricek nebo funkce verejnosti zatim nezapnuta = ValueError."""
    if raw is None or raw == "":
        return None
    if nabidka_pricky is None:
        raise ValueError("pricky nejsou k dispozici")
    vyber = nabidka_pricky.parse_vyber(raw)
    if not vyber:
        return None
    ctx = _pricky_kontext(cur, offer, _pricky_je_admin(token, offer))
    if ctx is None or not ctx["povoleno"]:
        raise ValueError("pricky se u teto nabidky nenabizeji")
    clean = nabidka_pricky.over_vyber(vyber, ctx["boxy"])
    if not clean:
        return None
    res = nabidka_pricky.spocti(ctx["boxy"], ctx["skupiny"], clean, ctx["ceny"])
    res["vyber"] = clean
    return res


def _pricky_poznamka(res, qty=1):
    """Text o prislusenstvi (pricky) pro poznamku objednavky a e-mail o prijeti; prazdny retezec bez vyberu. Rozpis po policich / sufliccich (vyroba vi, kam co patri) a cena bez DPH."""
    if not res or not res.get("popis"):
        return ""
    def kc(x):
        t = f"{x:,.2f}".replace(",", " ").replace(".", ",")
        return (t[:-3] if t.endswith(",00") else t) + " Kč"
    def cast(p):                                                    # vyroba potrebuje pocty po boxech / suplicich v poradi jako v nabidce (Multibox 1..N / Suplik 1..N skupiny) u KAZDEHO setu (mixy maji ruzne pocty)
        return (f"{p['popis']} - {p['set_popis']} ({p['boxu_s_pricky']} z {p['boxu']} {p.get('jednotka') or 'boxů'}, {p['priccek']} příček, {kc(p['cena'])}; "
                f"příček po {p.get('jednotkaL') or 'boxech'} v pořadí {p.get('oznaceni') or 'Multibox'} 1…{p['boxu']}: {', '.join(str(n) for n in p['po_boxech'])})")
    druhy = {p.get("oznaceni") or "Multibox" for p in res["popis"]}
    nadpis = "Příčky do multiboxů a šuplíků" if len(druhy) > 1 else ("Příčky do šuplíků" if druhy == {"Šuplík"} else "Příčky do multiboxů")
    txt = nadpis + " (cena za 1 ks sestavy bez DPH): " + "; ".join(cast(p) for p in res["popis"]) + f"; celkem {kc(res['net'])}"
    return txt + (f"; počet kusů sestavy {qty}" if qty and int(qty) > 1 else "") + "."


def _offer_gross_total(offer, prefs, montaz_pct=0):
    # .get() vsude (bot5, 2026-09-15) - `prefs` uz neni jen VZDY-kompletni
    # radek z _load_order_prefs, ale muze byt i castecny dict slozeny jen
    # z live query parametru (viz public_offer_payment_qr, oprava "QR kod
    # se pri navysovani ks nemenil") - primy `prefs["klic"]` by na
    # chybejicim klici spadl na KeyError.
    qty = 1
    if prefs and prefs.get("qty"):
        qty = max(1, int(prefs["qty"]))
    items_net = float(offer["total_price"]) * qty
    offer_options = _offer_options_from_row(offer)
    # Sleva nabidky (bot16, 2026-10-07, offer_options.discount_pct): z ceny zbozi (BEZ pricek - ty zakaznik vybira na strance za pevne ceny z karet); po sleve se pocita i montaz
    # (% z ceny nabidky). Bez slevy beze zmeny.
    sleva_net = _offer_discount_net(offer_options, items_net)
    if sleva_net:                                                                           # bez slevy zadne zaokrouhlovani = vypocet presne jako dosud
        items_net = round(items_net - sleva_net, 2)
    # prislusenstvi: pricky do multiboxu (bot8, 2026-10-07) - cena za 1 kus sestavy bez DPH z _pricky_vyber, nasobi se poctem kusu a je soucasti zakladu pro montaz (jako rucni polozky)
    items_net += float((prefs or {}).get("pricky_net") or 0.0) * qty
    base_net = items_net
    is_vehicle = _je_auto_sestava(offer_options)
    manual_assembled_shipping = offer_options.get("manual_assembled_shipping_czk")
    montaz_net = _offer_montaz_net(offer_options, items_net, prefs, montaz_pct)
    # Robert 2026-10-06: zvolena montaz v Praze / Slavicine (sestava do auta) VYLUCUJE volbu dopravy - doprava se v tom pripade nepricita (UI ji skryje, server ji ignoruje)
    if prefs and prefs.get("shipping_method") == "toptrans" and not montaz_net:
        # bot5, 2026-09-28 (Robert primo): u sestav BEZ montaze (viz
        # is_vehicle_assembly nize) prebiji rucne zadana cena tu
        # automaticky dopocitanou KONKRETNE pro "Smontovano" - viz
        # _sanitize_offer_options.manual_assembled_shipping_czk.
        if not is_vehicle and prefs.get("delivery_state") == "smontovano" and manual_assembled_shipping is not None:
            base_net += float(manual_assembled_shipping)
        elif prefs.get("toptrans_price_czk"):
            base_net += float(prefs["toptrans_price_czk"])
    # Montaz jako nabizena sluzba (Robert primo, 2026-09-28: sestavy do auta; 2026-10-06: "zatrhavaci sluzba montaz (a kde Praha /
    # Slavicin)" u KAZDE nabidky, ne jen u is_vehicle_assembly) - jen kdyz ji zakaznik skutecne zvolil a sazba nabidky neni 0 (0 = montaz se
    # v nabidce nenabizi, napr. nabidky z konfigurace mimo CR). % z cisteho souctu polozek (items_net, BEZ dopravy) - stejny zaklad jako
    # scene.html::refreshSummary (grandTotal * montaz_pct/100), viz PRICING_CONFIG.montaz_pct tam.
    # `montaz_pct` z parametru je VYCHOZI sazba z app_settings (volajici ji cte jednou) - vlastni volba nabidky ji prebiji (viz _offer_montaz_net)
    base_net += montaz_net
    return round(base_net * (1 + VAT_RATE / 100), 2)


@app.get("/api/public/offers/<token>/payment-qr")
def public_offer_payment_qr(token):
    """PNG QR kod "QR Platba" - castka podle ?deposit_pct= (50-100,
    zalohova platba; Robert 2026-08-06: minimum 50 %) nebo plna cena
    nabidky, a ?qty= (mnozstvi kusu). VS = ciselna cast cisla nabidky
    (RM0026 -> 26).

    Robert primo (pres bot3, 2026-09-15): "nefunguje nam QR kod v
    online nabidce pri navysovani ks" - qty se driv cetlo VZDY z
    ulozenych order_prefs (DB), nikdy z live requestu. Stejny zavod
    jako uz drive vyresen u public_offer_toptrans_price (viz komentar
    tam, "qty posilame primo v requestu, NE ze ulozenych order_prefs -
    customer muze zmenit qty driv, nez se stihne ulozit") - QR endpoint
    ho bohuzel nedodrzoval. `?qty=` je ted primy query parametr
    (fallback na order_prefs, kdyz chybi - stara volani/zpetna
    kompatibilita); jako vedlejsi efekt to zaroven mění URL retezec
    kdykoli se qty zmeni, takze prohlizec obrazek fakt znovu nacte
    (viz refreshPayQr() v nabidka-online.html - drive pri stejnem qty
    slo o bajt-identicky <img src>, ktery se nekdy vubec znovu
    nenacetl)."""
    try:
        import qrcode
    except ImportError:
        return jsonify({"error": "QR generátor není nainstalovaný."}), 500
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
            prefs = _load_order_prefs(cur, offer["id"], _quote_guest_id()) if offer else None
            montaz_pct = get_setting(cur, "montaz_pct", "0") if offer else "0"
    finally:
        conn.close()
    if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
        return jsonify({"error": "Nabídka nebyla nalezena."}), 404

    deposit_pct = request.args.get("deposit_pct", type=int)
    qty_param = request.args.get("qty", type=int)
    prefs_for_total = dict(prefs) if prefs else {}
    if qty_param is not None:
        prefs_for_total["qty"] = _clamp_qty(qty_param)
    pr_raw = request.args.get("pr")                       # pricky do multiboxu (bot8, 2026-10-07): vyber "s1:pln,s2:zak" - castka musi sedet s objednavkou
    if pr_raw:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                try:
                    pr_res = _pricky_vyber(cur, offer, token, pr_raw)
                except ValueError:
                    return jsonify({"error": "Výběr příček není platný."}), 400
        finally:
            conn.close()
        if pr_res:
            prefs_for_total["pricky_net"] = pr_res["net"]
    # DPH + Toptrans doprava (viz _offer_gross_total docstring) + od
    # 2026-09-14 taky mnozstvi (qty) + od 2026-09-28 taky Montaz (u
    # sestav do auta) - vsechno v JEDNOM helperu, at nedojde k rozjezdu
    # mezi QR platbou a objednavkou.
    amount = _offer_gross_total(offer, prefs_for_total, montaz_pct)
    if deposit_pct is not None:
        deposit_pct = max(50, min(100, deposit_pct))
        amount = round(amount * deposit_pct / 100, 2)

    vs = re.sub(r"\D", "", offer["offer_number"]) or str(offer["id"])
    iban = _cz_account_to_iban(SUPPLIER["bank_account"])
    label = f"Nabidka {offer['offer_number']}" + (f" zaloha {deposit_pct}%" if deposit_pct is not None else "")
    spayd = _build_spayd(iban, amount, vs, label)

    img = qrcode.make(spayd)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), mimetype="image/png", headers={
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",  # castka se meni podle zvolene zalohy
    })


@app.get("/api/public/offers/<token>/pdf")
def public_offer_pdf(token):
    """Verejne stazeni PDF nabidky (Robert: "tlacitko stahnout jako
    PDF") - stejny soubor, ktery uz lezi na Sdilenem disku
    (drive_file_id), jen pristupny pres token nabidky misto admin
    loginu. Zadne pregenerovavani."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
            if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
                return jsonify({"error": "Nabídka nebyla nalezena."}), 404
            if not offer["drive_file_id"]:
                return jsonify({"error": "PDF není k dispozici."}), 404
            cur.execute("SELECT filename, stored_filename FROM shared_drive_files WHERE id=%s", (offer["drive_file_id"],))
            file_row = cur.fetchone()
    finally:
        conn.close()
    if not file_row:
        return jsonify({"error": "PDF není k dispozici."}), 404
    try:
        with open(os.path.join(DRIVE_FILES_DIR, file_row["stored_filename"]), "rb") as fh:
            data = fh.read()
    except OSError:
        return jsonify({"error": "PDF na disku chybí."}), 404
    safe_ascii = "".join(c if 32 <= ord(c) < 127 and c != '"' else "_" for c in file_row["filename"]) or "nabidka.pdf"
    return Response(data, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{safe_ascii}"',
        "X-Content-Type-Options": "nosniff",
    })


@app.post("/api/public/offers/<token>/order-prefs")
def public_offer_order_prefs(token):
    """Ulozeni voleb objednavky (doprava/platba/zaloha/stav dodani) -
    Robert pres AskUserQuestion: "Ano, ulozit a zobrazit v adminu".
    UPSERT pres UNIQUE (offer_id, guest_id) - posledni volba vyhrava."""
    # QA bezpecnostni nalez (2026-09-05): chybel rate-limit, stejny vzor
    # jako u markups vyse.
    limited = _public_offer_rate_limited(token, "order_prefs", 10, 30)
    if limited:
        return limited
    body = request.get_json(silent=True) or {}

    values = {}
    for field, allowed in ORDER_PREF_CHOICES.items():
        val = body.get(field)
        if val is not None and val not in allowed:
            return jsonify({"error": f"Neplatná hodnota pro {field}."}), 400
        values[field] = val
    deposit_pct = body.get("deposit_pct")
    if deposit_pct is not None:
        try:
            # 50-100 % (Robert 2026-08-06: "minimum 50% maximum 100% po 10Ti")
            deposit_pct = max(50, min(100, int(deposit_pct)))
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatná výše zálohy."}), 400
    if values["payment_method"] != "zaloha":
        deposit_pct = None
    # Robert primo, 2026-09-14: "moznost objednat vice ks vyrobku" -
    # mnozstvi celych sestav, vynasobi celkovou cenu/platbu (viz
    # _offer_gross_total). 1-99 (99 jako rozumny strop proti omylu/
    # zneuziti - vetsi davky se resi individualni poptavkou, ne timhle
    # widgetem).
    qty = _clamp_qty(body.get("qty"))

    # Robert ("stisk toptransu... vypsat živou cenu") - PSC a naposledy
    # dopocitana cena Toptrans se uklada spolu se zbytkem voleb, aby
    # prezily reload stranky a byly videt v adminu. Necha se prazdne
    # (None) pro shipping_method != "toptrans".
    delivery_zip = None
    toptrans_price_czk = None
    if values["shipping_method"] == "toptrans":
        raw_zip = (body.get("delivery_zip") or "").strip()
        if raw_zip:
            delivery_zip = re.sub(r"\D", "", raw_zip)[:6]
        toptrans_price = body.get("toptrans_price_czk")
        if toptrans_price is not None:
            try:
                toptrans_price_czk = int(toptrans_price)
            except (TypeError, ValueError):
                toptrans_price_czk = None
    # Montaz (Robert primo, 2026-09-28) - jen u sestav do auta, viz
    # _sanitize_offer_options.is_vehicle_assembly. montaz_zvolena bez
    # ohledu na offer_options tady (kontrola az v renderu/vypoctu, stejny
    # princip jako hidden_delivery_state - ulozit se smi cokoli platne,
    # co se s tim udela je vec vykresleni/souctu).
    montaz_zvolena = bool(body.get("montaz_zvolena"))
    montaz_misto = (body.get("montaz_misto") or "").strip().lower() or None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
            if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
                return jsonify({"error": "Nabídka nebyla nalezena."}), 404
            if montaz_misto is not None and montaz_misto not in _montaz_mista_map(cur):
                return jsonify({"error": "Neplatné místo montáže."}), 400
            if not montaz_zvolena:
                montaz_misto = None
            oo_prefs = _offer_options_from_row(offer)
            if not _je_auto_sestava(oo_prefs):
                montaz_zvolena, montaz_misto = False, None                  # montaz k platbe jen u sestav do aut (stoly a ostatni: jen informace)
            elif montaz_zvolena and _offer_montaz_pct(oo_prefs, get_setting(cur, "montaz_pct", "0")):
                # sestava do auta se zvolenou montazi (Praha / Slavicin): doprava se nevybira (vylucuje se) - explicitni Toptrans = chyba, ostatni se vynuluje
                if values["shipping_method"] == "toptrans":
                    return jsonify({"error": "Montáž a dopravu nelze zvolit současně – u montáže se doprava nevybírá.", "code": "montaz_doprava_vylouceno"}), 400
                values["shipping_method"], delivery_zip, toptrans_price_czk = None, None, None
            guest_id = _quote_guest_id()
            cur.execute(
                "INSERT INTO scene_offer_order_prefs "
                "(offer_id, guest_id, shipping_method, payment_method, deposit_pct, delivery_state, qty, "
                "delivery_zip, toptrans_price_czk, montaz_zvolena, montaz_misto, ip_address) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE shipping_method=VALUES(shipping_method), "
                "payment_method=VALUES(payment_method), deposit_pct=VALUES(deposit_pct), "
                "delivery_state=VALUES(delivery_state), qty=VALUES(qty), delivery_zip=VALUES(delivery_zip), "
                "toptrans_price_czk=VALUES(toptrans_price_czk), montaz_zvolena=VALUES(montaz_zvolena), "
                "montaz_misto=VALUES(montaz_misto), ip_address=VALUES(ip_address)",
                (offer["id"], guest_id, values["shipping_method"], values["payment_method"],
                 deposit_pct, values["delivery_state"], qty, delivery_zip, toptrans_price_czk,
                 montaz_zvolena, montaz_misto, _client_ip()),
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.put("/api/public/offers/<token>/manual-shipping")
def public_offer_set_manual_shipping(token):
    """Admin (podle admin_view_token_hash - viz "Zobrazit online" v
    adminu) muze primo na ZIVE strance nastavit rucni cenu dopravy pro
    Smontovano, bez zajizdky do "Upravit nabidku" (Robert primo, po
    zivem testu: "zadal jsem Smontovano, ale nenabidnul se zadne okno
    pro zadani ceny" - puvodni verze cekala jen v admin editacnim
    panelu, coz nebylo videt primo na strance, kterou uz ma otevrenou).
    Zapisuje do STEJNEHO pole jako "Upravit nabidku"
    (offer_options.manual_assembled_shipping_czk,
    _sanitize_offer_options) - oba vstupy jsou jen 2 cesty ke stejne
    hodnote, ne 2 nezavisla mista pravdy. Token musi patrit KONKRETNE
    admin_view_token_hash teto nabidky - klientsky (view_token_hash) i
    jakykoli cizi token dostane 403, i kdyby byl jinak platny."""
    limited = _public_offer_rate_limited(token, "manual_shipping", 20, 60)
    if limited:
        return limited
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
            if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
                conn.rollback()
                return jsonify({"error": "Nabídka nebyla nalezena."}), 404
            viewer_is_admin = hashlib.sha256(token.encode()).hexdigest() == offer["admin_view_token_hash"]
            if not viewer_is_admin:
                conn.rollback()
                return jsonify({"error": "Nemáte oprávnění tuto nabídku upravovat."}), 403
            raw = body.get("manual_assembled_shipping_czk")
            offer_options = _offer_options_from_row(offer)
            if raw in (None, ""):
                offer_options["manual_assembled_shipping_czk"] = None
            else:
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    conn.rollback()
                    return jsonify({"error": "Neplatná částka."}), 400
                if val < 0:
                    conn.rollback()
                    return jsonify({"error": "Částka nemůže být záporná."}), 400
                offer_options["manual_assembled_shipping_czk"] = round(val, 2)
            offer_options = _sanitize_offer_options(offer_options)
            cur.execute(
                "UPDATE scene_offers SET offer_options=%s WHERE id=%s",
                (json.dumps(offer_options), offer["id"]),
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "manual_assembled_shipping_czk": offer_options.get("manual_assembled_shipping_czk")})


# Robert primo, 2026-09-14: "pro volbu Toptransem je potreba
# zapocitavat pausalni priplatek 100,-" - zamerne JEN tady (online
# nabidky), NE v _resolve_toptrans_price() samotne, protoze tu sdili
# e-shop kosik (orders.py, bot5-ova domena) - tam se bez koordinace
# nesaha.
OFFER_TOPTRANS_SURCHARGE_CZK = 100


@app.post("/api/public/offers/<token>/toptrans-price")
def public_offer_toptrans_price(token):
    """Ziva cena dopravy Toptrans pro online nabidku - Robert: "stisk
    toptransu nic neudelal, musi vyvolat dotaz na PSC a vypsat živou
    cenu". Stejny vypocet (PSC + hmotnost -> cena) jako v e-shop kosiku
    (_resolve_toptrans_price, orders.py), jen hmotnost se nebere z
    kosiku, ale ze souctu weight_kg_total pres vsechny radky kusovniku
    ulozene nabidky (viz scene.html::generateSceneOffer - weight_kg
    pridano k radkum kusovniku 2026-08-09). Stare nabidky (pred timhle
    datem) nemaji weight_kg_total ulozene -> pocita se jako 0 (cenik
    pak vrati nejlevnejsi pasmo - znama neresena mez pro stary obsah,
    ne bug)."""
    body = request.get_json(silent=True) or {}
    delivery_zip = (body.get("delivery_zip") or "").strip()
    # Robert primo (pres bot3, 2026-09-14): "Toptrans je cenove podle
    # PSC A VAHY, takze s vic kusy = vic vahy logicky stoupa i cena" -
    # qty posilame primo v requestu (orderPrefsState.qty na frontendu),
    # NE ze ulozenych order_prefs - customer muze zmenit qty a hned
    # nato PSC (nebo obracene) driv, nez se qty stihne ulozit, takze
    # spoleh na DB radek by mohl pocitat se starou hodnotou.
    qty = _clamp_qty(body.get("qty"))
    # Stejny duvod jako u qty vyse - "Dodani ve stavu" muze byt zmeneno
    # driv, nez se stihne ulozit (bot5, 2026-09-28, rucni prebiti ceny
    # pro Smontovano, viz nize).
    delivery_state = body.get("delivery_state") if body.get("delivery_state") in ("smontovano", "demontovano") else None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
            if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
                return jsonify({"error": "Nabídka nebyla nalezena."}), 404

            # Robert primo, 2026-09-28: "je potreba rucne zadat castku za
            # dopravu při smontovanem stavu, ktera přebije automatickou
            # cenu Toptransu" - jen u sestav BEZ montaze (viz
            # is_vehicle_assembly, _offer_gross_total ma STEJNOU
            # podminku, at si obe cesty nikdy neodporuji) a jen pro
            # "Smontovano". Zadny dotaz na _resolve_toptrans_price/vahu -
            # rucne zadane cislo je uz hotova odpoved.
            offer_options = _offer_options_from_row(offer)
            manual_assembled_shipping = offer_options.get("manual_assembled_shipping_czk")
            if (not _je_auto_sestava(offer_options)) and delivery_state == "smontovano" \
                    and manual_assembled_shipping is not None:
                return jsonify({
                    "price_czk": round(float(manual_assembled_shipping)),
                    "km_band": None, "basis": "manual", "weight_kg": None,
                })

            # Nabidka z konfigurace stolu: hmotnost z katalogu je dnes neuplna (chybi laminodeska, supliky, panely...), Toptrans by byl vyrazne poddimenzovany - NEpocita se (409),
            # zamestnanec muze zadat rucni cenu dopravy ("Smontovano", viz vyse). Poskozeny/chybejici snimek = neuplna (fail closed). Hmotnost se nikdy neodhaduje.
            konfigurace_snimek = None
            if offer_options.get("source") == "configurator":
                konfigurace_snimek = offer_options.get("config_private") if isinstance(offer_options.get("config_private"), dict) else {}
                if konfigurace_snimek.get("weight_complete") is not True:
                    return jsonify({"error": "Dopravu Toptrans u této nabídky vám spočítáme individuálně. Zvolte prosím vlastní dopravu (osobní odběr), nebo nás kontaktujte.",
                                    "code": "weight_incomplete"}), 409
            cur.execute(
                "SELECT id FROM shop_shipping_methods WHERE pricing_mode='zip_weight' AND active=1 LIMIT 1"
            )
            method = cur.fetchone()
            if not method:
                return jsonify({"error": "Doprava Toptrans není momentálně dostupná."}), 400

            try:
                items = json.loads(offer["items"] or "[]")
            except (ValueError, TypeError):
                items = []
            if konfigurace_snimek is not None:
                weight_kg = float(konfigurace_snimek.get("weight_kg") or 0) * qty
            else:
                weight_kg = sum(float(it.get("weight_kg_total") or 0) for it in items if isinstance(it, dict)) * qty

            try:
                price_czk, km_band, basis = _resolve_toptrans_price(cur, method["id"], delivery_zip, weight_kg)
            except _OrderCreateError as e:
                return jsonify({"error": str(e)}), 400
            price_czk += OFFER_TOPTRANS_SURCHARGE_CZK
    finally:
        conn.close()
    return jsonify({"price_czk": round(price_czk), "km_band": km_band, "basis": basis, "weight_kg": round(weight_kg, 1)})


# ============================================================
# Admin API - seznam vygenerovanych online nabidek + statistiky.
# Reuse existujici sekce opravneni "nabidky" (stejny koncepcni celek
# "Nabidka" v cele appce, zadna nova sekce v PERMISSION_SECTIONS).
# ============================================================

@app.get("/api/admin/scene-offers")
@require_permission("nabidky", "zobrazit")
def admin_scene_offers_list():
    """
    ?archived=1 - jen nabídky s vypršenou platností (expires_at < NOW()),
    jinak (výchozí) jen platné. "Archiv" je čistě ODVOZENÝ od expires_at
    (žádný samostatný sloupec/cron úloha) - Robert 2026-08-06: "nabídky
    budou mít platnost 30 dní, poté vždy končí v archivu, z archivu je
    vyvolá pouze admin ručně". "Vyvolání" = POST .../regenerate-link (uz
    existovalo driv jako "poslat novy odkaz") - posune expires_at o
    dalsich 30 dni dopredu, cimz nabidka OKAMZITE zmizi z archivu a
    objevi se zpet v aktivnich (zadna extra logika navic potreba).
    """
    q = (request.args.get("q") or "").strip()
    archived = request.args.get("archived") == "1"
    where, params = [], []
    # Stala testovaci nabidka se v prehledu neukazuje (Robert 2026-08-06:
    # "staci kdyz bude tlacitko: radek v prehledu netreba") - zije dal,
    # tlacitko 🧪 ji pouziva, jen v seznamu neprekazi.
    where.append("o.offer_number != %s")
    params.append(TEST_OFFER_NUMBER)
    where.append("o.expires_at < NOW()" if archived else "o.expires_at >= NOW()")
    if q:
        where.append("(o.offer_number LIKE %s OR o.customer_name LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])
    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            base_sql = """
                SELECT o.id, o.offer_number, o.customer_name, o.total_price, o.is_active,
                       o.expires_at, o.created_at,
                       (SELECT COUNT(DISTINCT v.ip_address) FROM scene_offer_views v WHERE v.offer_id=o.id) AS view_count,
                       (SELECT COALESCE(SUM(e.dwell_ms),0) FROM scene_offer_page_events e
                          JOIN scene_offer_views v2 ON v2.id=e.view_id WHERE v2.offer_id=o.id) AS total_dwell_ms,
                       (SELECT a.name FROM scene_offer_acceptances a WHERE a.offer_id=o.id ORDER BY a.accepted_at ASC LIMIT 1) AS accepted_name
                FROM scene_offers o
            """
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            rows, total = paginated_query(cur, base_sql, where_sql, params, " ORDER BY o.created_at DESC", page, page_size)

            count_where = "WHERE o.offer_number != %s"
            cur.execute(f"SELECT COUNT(*) AS n FROM scene_offers o {count_where} AND o.expires_at >= NOW()", [TEST_OFFER_NUMBER])
            active_count = cur.fetchone()["n"]
            cur.execute(f"SELECT COUNT(*) AS n FROM scene_offers o {count_where} AND o.expires_at < NOW()", [TEST_OFFER_NUMBER])
            archived_count = cur.fetchone()["n"]
    finally:
        conn.close()
    resp = {"offers": [
        {
            "id": r["id"], "offer_number": r["offer_number"], "customer_name": r["customer_name"],
            "total_price": r["total_price"], "is_active": bool(r["is_active"]),
            "expires_at": r["expires_at"].isoformat(), "created_at": r["created_at"].isoformat(),
            "view_count": r["view_count"], "total_dwell_ms": r["total_dwell_ms"],
            "accepted_name": r["accepted_name"], "is_archived": archived,
        } for r in rows
    ], "counts": {"active": active_count, "archived": archived_count}}
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.get("/api/admin/scene-offers/<int:offer_id>/stats")
@require_permission("nabidky", "zobrazit")
def admin_scene_offer_stats(offer_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, offer_number FROM scene_offers WHERE id=%s", (offer_id,))
            offer = cur.fetchone()
            if not offer:
                return jsonify({"error": "Nabídka neexistuje."}), 404
            cur.execute("""
                SELECT v.ip_address, COUNT(*) AS visits, MIN(v.started_at) AS first_seen, MAX(v.last_seen_at) AS last_seen
                FROM scene_offer_views v WHERE v.offer_id=%s
                GROUP BY v.ip_address ORDER BY last_seen DESC
            """, (offer_id,))
            by_ip = cur.fetchall()
            # event_type='page_view' filtr je NUTNY - od pridani kliku
            # (viz nize) tahle tabulka obsahuje i 'click' radky, ktere by
            # jinak falesne navysovaly pocty shlednuti/cas.
            cur.execute("""
                SELECT e.page_key, COUNT(*) AS views, COUNT(DISTINCT e.view_id) AS unique_views,
                       COALESCE(SUM(e.dwell_ms),0) AS total_dwell_ms, COALESCE(AVG(e.dwell_ms),0) AS avg_dwell_ms,
                       COALESCE(AVG(e.scroll_pct),0) AS avg_scroll_pct, COALESCE(MAX(e.scroll_pct),0) AS max_scroll_pct
                FROM scene_offer_page_events e
                JOIN scene_offer_views v ON v.id=e.view_id
                WHERE v.offer_id=%s AND e.event_type='page_view' GROUP BY e.page_key
            """, (offer_id,))
            by_page_raw = {r["page_key"]: r for r in cur.fetchall()}
            cur.execute("""
                SELECT e.target, COUNT(*) AS clicks, COUNT(DISTINCT e.view_id) AS unique_clicks
                FROM scene_offer_page_events e
                JOIN scene_offer_views v ON v.id=e.view_id
                WHERE v.offer_id=%s AND e.event_type='click' GROUP BY e.target ORDER BY clicks DESC
            """, (offer_id,))
            by_click = cur.fetchall()
            cur.execute(
                "SELECT name, accepted_at FROM scene_offer_acceptances WHERE offer_id=%s ORDER BY accepted_at ASC LIMIT 1",
                (offer_id,),
            )
            acceptance = cur.fetchone()
            cur.execute(
                "SELECT reason, declined_at FROM scene_offer_declines WHERE offer_id=%s ORDER BY declined_at DESC",
                (offer_id,),
            )
            declines = cur.fetchall()
            cur.execute(
                "SELECT page_key, item_name, body, created_at FROM scene_offer_notes WHERE offer_id=%s ORDER BY created_at DESC",
                (offer_id,),
            )
            notes = cur.fetchall()
            # Volby objednavky (doprava/platba/zaloha/stav dodani) -
            # Robert: "ulozit a zobrazit v adminu". Muze jich byt vic
            # (ruzni guest_id, napr. nabidka preposlana kolegovi) -
            # ukazujeme vsechny, nejnovejsi napred.
            # Robert 2026-10-07 ("zase tam chybi montaz KDE Praha/Slavicin"): admin v detailu nabidky musi videt i pocet kusu, zvolenou montaz a MISTO montaze (Praha / Slavicin) -
            # dosud se z voleb klienta vracela jen doprava, platba a stav dodani
            cur.execute(
                "SELECT shipping_method, payment_method, deposit_pct, delivery_state, "
                "delivery_zip, toptrans_price_czk, qty, montaz_zvolena, montaz_misto, updated_at "
                "FROM scene_offer_order_prefs WHERE offer_id=%s ORDER BY updated_at DESC",
                (offer_id,),
            )
            order_prefs = cur.fetchall()
            mista_nazvy = _montaz_mista_map(cur, jen_aktivni=False)                      # klic -> nazev (i neaktivni misto zustane u uz zvolene montaze citelne)
    finally:
        conn.close()
    # Vraci VZDY vsechny page_key (i s nulami), v definovanem poradi -
    # admin UI pak nemusi resit chybejici radky pro stranky, ktere jeste
    # nikdo nenavstivil.
    by_page = [
        {
            "page_key": key,
            "views": (by_page_raw.get(key) or {}).get("views", 0),
            "unique_views": (by_page_raw.get(key) or {}).get("unique_views", 0),
            "total_dwell_ms": (by_page_raw.get(key) or {}).get("total_dwell_ms", 0),
            "avg_dwell_ms": round(float((by_page_raw.get(key) or {}).get("avg_dwell_ms", 0))),
            "avg_scroll_pct": round(float((by_page_raw.get(key) or {}).get("avg_scroll_pct", 0))),
            "max_scroll_pct": (by_page_raw.get(key) or {}).get("max_scroll_pct", 0),
        }
        for key in OFFER_PAGE_KEYS
    ]
    return jsonify({
        "offer_number": offer["offer_number"],
        "by_ip": [
            {"ip_address": r["ip_address"], "visits": r["visits"],
             "first_seen": r["first_seen"].isoformat(), "last_seen": r["last_seen"].isoformat()}
            for r in by_ip
        ],
        "by_page": by_page,
        "by_click": [{"target": r["target"], "clicks": r["clicks"], "unique_clicks": r["unique_clicks"]} for r in by_click],
        "acceptance": {"name": acceptance["name"], "accepted_at": acceptance["accepted_at"].isoformat()} if acceptance else None,
        "declines": [
            {"reason": d["reason"], "declined_at": d["declined_at"].isoformat()} for d in declines
        ],
        "notes": [
            {"page_key": n["page_key"], "item_name": n["item_name"], "body": n["body"], "created_at": n["created_at"].isoformat()}
            for n in notes
        ],
        "order_prefs": [
            {"shipping_method": p["shipping_method"], "payment_method": p["payment_method"],
             "deposit_pct": p["deposit_pct"], "delivery_state": p["delivery_state"],
             "delivery_zip": p["delivery_zip"], "toptrans_price_czk": p["toptrans_price_czk"],
             "qty": p["qty"], "montaz_zvolena": bool(p["montaz_zvolena"]), "montaz_misto": p["montaz_misto"],
             "montaz_misto_label": (mista_nazvy.get(p["montaz_misto"]) or p["montaz_misto"]) if p["montaz_misto"] else None,
             "updated_at": p["updated_at"].isoformat()}
            for p in order_prefs
        ],
    })


@app.post("/api/admin/scene-offers/<int:offer_id>/toggle-active")
@require_permission("nabidky", "upravit")
def admin_scene_offer_toggle_active(offer_id):
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT is_active FROM scene_offers WHERE id=%s", (offer_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Nabídka neexistuje."}), 404
            new_active = 0 if row["is_active"] else 1
            cur.execute("UPDATE scene_offers SET is_active=%s WHERE id=%s", (new_active, offer_id))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "scene_offer", offer_id, f"is_active={new_active}")
    return jsonify({"status": "ok", "is_active": bool(new_active)})


@app.post("/api/admin/scene-offers/<int:offer_id>/regenerate-link")
@require_permission("nabidky", "upravit")
def admin_scene_offer_regenerate_link(offer_id):
    """Token se uklada jen jako SHA-256 hash (viz modulovy komentar u
    scene_offers vyse) - puvodni odkaz proto NEJDE zpetne dohledat, pokud
    ho admin nezkopiroval hned pri generovani. Tohle vygeneruje NOVY
    token (stary prestane platit) a prodlouzi platnost o dalsich 30 dni -
    stejny princip jako "poslat novy odkaz" u password_reset_tokens.

    Zaroven JEDINA cesta, jak "vyvolat nabidku z archivu" (Robert
    2026-08-06) - jakmile expires_at posunuty spat do budoucnosti,
    nabidka uz v GET /api/admin/scene-offers?archived=1 neni (viz tam)."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM scene_offers WHERE id=%s", (offer_id,))
            if not cur.fetchone():
                return jsonify({"error": "Nabídka neexistuje."}), 404
            view_token = secrets.token_urlsafe(32)
            view_token_hash = hashlib.sha256(view_token.encode()).hexdigest()
            expires_at = datetime.datetime.now() + datetime.timedelta(days=OFFER_LINK_VALIDITY_DAYS)
            cur.execute(
                "UPDATE scene_offers SET view_token_hash=%s, expires_at=%s, is_active=1 WHERE id=%s",
                (view_token_hash, expires_at, offer_id),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "scene_offer", offer_id, "regenerate_link")
    return jsonify({"status": "ok", "online_url": f"/nabidka-online.html?t={view_token}"})


@app.get("/api/admin/scene-offers/<int:offer_id>/edit-data")
@require_permission("nabidky", "upravit")
def admin_scene_offer_edit_data(offer_id):
    """Plna data pro editacni formular v adminu (Robert 2026-08-10:
    "plne editovani nabidky v adminu") - oddeleno od admin_scene_offer_stats
    vyse, protoze ten se nacita pri KAZDEM otevreni detailu nabidky a
    items JSON muze byt velky (desitky radku kusovniku); tenhle endpoint
    se vola az kdyz admin skutecne klikne "Upravit"."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT offer_number, customer_name, items, total_price, editable_text_popis, editable_text_patka, "
                "offer_options, revision_number, last_edited_at FROM scene_offers WHERE id=%s",
                (offer_id,),
            )
            offer = cur.fetchone()
    finally:
        conn.close()
    if not offer:
        return jsonify({"error": "Nabídka neexistuje."}), 404
    return jsonify({
        "offer_number": offer["offer_number"],
        "items": json.loads(offer["items"]),
        "total_price": offer["total_price"],
        "customer_name": offer["customer_name"],              # jmeno klienta se da doplnit dodatecne (Robert 2026-10-06)
        "editable_text": {"popis": offer["editable_text_popis"], "patka": offer["editable_text_patka"]},
        "offer_options": (json.loads(offer["offer_options"]) if offer["offer_options"]
                           else OFFER_OPTIONS_DEFAULT),
        "revision_number": offer["revision_number"],
        "last_edited_at": offer["last_edited_at"].isoformat() if offer["last_edited_at"] else None,
        # Rucni polozky (bot8, 2026-10-06): priznak pro admin formular (staticky, zive driv nez API) - tlacitka "+ Z katalogu" / "+ Volny text" se ukazou jen s nim
        "rucni_polozky": {"max": MANUAL_ITEMS_MAX, "obrazky_max": MANUAL_IMAGES_MAX},
        # Sleva (bot16, 2026-10-07): priznak pro admin formular - pole "Sleva (% z ceny zbozi)" se ukaze jen s nim (starsi API by offer_options.discount_pct potichu zahodilo)
        "sleva": {"max_pct": 100},
    })


@app.get("/api/admin/scene-offers/<int:offer_id>/revisions")
@require_permission("nabidky", "zobrazit")
def admin_scene_offer_revisions(offer_id):
    """Historie verzi (viz scene_offer_revisions - kazdy radek je stav
    TESNE PRED nejakou editaci). Vraci jen souhrn (ne cely items JSON u
    kazde revize - admin si detail rozklikne zvlast, viz nize), at je
    seznam rychly i u nabidek editovanych vickrat."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM scene_offers WHERE id=%s", (offer_id,))
            if not cur.fetchone():
                return jsonify({"error": "Nabídka neexistuje."}), 404
            cur.execute(
                "SELECT r.id, r.revision_number, r.total_price, r.edited_at, r.change_note, "
                "u.name AS edited_by_name "
                "FROM scene_offer_revisions r LEFT JOIN app_users u ON u.id=r.edited_by "
                "WHERE r.offer_id=%s ORDER BY r.revision_number DESC",
                (offer_id,),
            )
            revisions = cur.fetchall()
    finally:
        conn.close()
    return jsonify({
        "revisions": [
            {"id": r["id"], "revision_number": r["revision_number"], "total_price": r["total_price"],
             "edited_at": r["edited_at"].isoformat(), "change_note": r["change_note"],
             "edited_by_name": r["edited_by_name"]}
            for r in revisions
        ],
    })


@app.get("/api/admin/scene-offers/revisions/<int:revision_id>")
@require_permission("nabidky", "zobrazit")
def admin_scene_offer_revision_detail(revision_id):
    """Plny snapshot jedne konkretni minule revize (items vcetne) -
    samostatny endpoint od seznamu vyse ze stejneho duvodu jako
    edit-data (items JSON muze byt velky, nechceme ho tahat pro
    kazdy radek historie najednou)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT offer_id, revision_number, items, total_price, editable_text_popis, "
                "editable_text_patka, offer_options FROM scene_offer_revisions WHERE id=%s",
                (revision_id,),
            )
            rev = cur.fetchone()
    finally:
        conn.close()
    if not rev:
        return jsonify({"error": "Revize neexistuje."}), 404
    return jsonify({
        "offer_id": rev["offer_id"],
        "revision_number": rev["revision_number"],
        "items": json.loads(rev["items"]),
        "total_price": rev["total_price"],
        "editable_text": {"popis": rev["editable_text_popis"], "patka": rev["editable_text_patka"]},
        "offer_options": json.loads(rev["offer_options"]) if rev["offer_options"] else None,
    })


# ---------------------------------------------------------------------------------------------------------------------
# RUCNI POLOZKY V ONLINE NABIDCE (bot8, 2026-10-06; Robert: "admin pripise do online nabidky dalsi polozky rucne z katalogu vcetne vlozeni 3D modelu, parametru a ceny" a
# "... jen jako volny text s nactenim obrazku (1-2 ks) a ceny"). Polozka je radek v `items` s klicem `manual` ({typ: "katalog" | "text", popis, model, obrazky}); pridava se VZDY
# NA KONEC kusovniku a nema mesh_group (zadne propojeni s vykresy / 3D), takze puvodni radky (vc. radku konfigurace u nabidky z konfigurace - ten zustava prvni) se nemeni.
# Server vsechno znovu overuje (admin formular se necha obejit): pocet a poradi obycejnych radku musi zustat, polozka z katalogu musi existovat, 3D model jen kdyz ho produkt ma,
# obrazky jen vlastni (klic z nahravani teto nabidky). Verejne se obrazek a model servíruji za tokenem a JEN kdyz je nabidka (items) odkazuje.
# ---------------------------------------------------------------------------------------------------------------------
MANUAL_ITEMS_MAX = 20
MANUAL_IMAGES_MAX = 2                  # obrazku u jedne polozky (volny text)
MANUAL_IMAGES_PER_OFFER_MAX = 60       # nahrane soubory pro jednu nabidku (strop proti zaplneni disku; nepouzite se neuklizeji, revize je mohou odkazovat)
MANUAL_NAME_MAX, MANUAL_DIM_MAX, MANUAL_POPIS_MAX = 200, 120, 2000
MANUAL_QTY_MAX = 999
MANUAL_PRICE_MAX = 10_000_000
MANUAL_IMAGE_KEY_RE = re.compile(r"^polozka_(\d{1,9})_([0-9a-f]{16})\.(jpg|png)$")


def _je_rucni(it):
    return isinstance(it, dict) and isinstance(it.get("manual"), dict)


def _rucni_cislo(v, nazev, lo, hi, cele=False):
    """Cislo z formulare (cislo nebo text s carkou) v rozsahu <lo, hi>; ValueError s ceskou hlaskou."""
    if isinstance(v, bool):
        raise ValueError(f"{nazev}: zadejte číslo.")
    try:
        x = float(v) if isinstance(v, (int, float)) else float(re.sub(r"[\s\u00a0\u202f]+", "", str(v)).replace(",", "."))          # "1 234,5" (mezera jako oddelovac tisicu, carka)
    except (TypeError, ValueError):
        raise ValueError(f"{nazev}: zadejte číslo.")
    if x != x or x in (float("inf"), float("-inf")):
        raise ValueError(f"{nazev}: zadejte číslo.")
    if cele and x != int(x):
        raise ValueError(f"{nazev}: zadejte celé číslo.")
    if not (lo <= x <= hi):
        raise ValueError(f"{nazev}: mimo rozsah {lo:g} až {hi:g}.")
    return x


def _rucni_mnozstvi(v, pre):
    """Mnozstvi rucni polozky: cele cislo 1 az MANUAL_QTY_MAX; bere cislo i text "N" / "N ks" (tak ho vraci edit-data po ulozeni - stejny tvar jako u radku ze sceny)."""
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(\d{1,6})\s*(?:ks)?\s*", v, re.IGNORECASE)
        if not m:
            raise ValueError(f"{pre}: množství zadejte jako celé číslo.")
        v = int(m.group(1))
    return int(_rucni_cislo(v, f"{pre}: množství", 1, MANUAL_QTY_MAX, cele=True))


def _vycisti_rucni_polozku(cur, offer_id, it, poradi):
    """Jedna rucni polozka -> cista (whitelist klicu, text oriznuty, cena a mnozstvi overene, produkt / model / obrazky existuji). ValueError s ceskou hlaskou."""
    pre = f"Ruční položka {poradi}"
    m = it.get("manual") or {}
    typ = m.get("typ")
    if typ not in ("katalog", "text"):
        raise ValueError(f"{pre}: neznámý typ položky.")
    name = str(it.get("name") or "").strip()
    if not name:
        raise ValueError(f"{pre}: chybí název.")
    if len(name) > MANUAL_NAME_MAX:
        raise ValueError(f"{pre}: název je delší než {MANUAL_NAME_MAX} znaků.")
    dim = str(it.get("dim") or "").strip()
    if len(dim) > MANUAL_DIM_MAX:
        raise ValueError(f"{pre}: rozměr / parametr je delší než {MANUAL_DIM_MAX} znaků.")
    popis = str(m.get("popis") or "").strip()
    if len(popis) > MANUAL_POPIS_MAX:
        raise ValueError(f"{pre}: popis je delší než {MANUAL_POPIS_MAX} znaků.")
    qty = _rucni_mnozstvi(it.get("qty"), pre)
    unit = _rucni_cislo(it.get("unit_price"), f"{pre}: cena za kus", 0, MANUAL_PRICE_MAX)
    unit = int(unit) if unit == int(unit) else round(unit, 2)
    out = {"name": name, "dim": dim, "qty": f"{qty} ks", "unit_price": unit, "total": int(qty * unit + 0.5), "manual": {"typ": typ, "popis": popis}}   # qty "N ks" jako u radku ze sceny (PDF, stranka, objednavka)
    if typ == "katalog":
        try:
            pid = int(it.get("product_id"))
        except (TypeError, ValueError):
            raise ValueError(f"{pre}: chybí produkt z katalogu.")
        cur.execute("SELECT id, glb_file FROM shop_products WHERE id=%s", (pid,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"{pre}: produkt #{pid} v katalogu neexistuje.")
        out["product_id"] = pid
        out["layer"] = "produkt"                       # kusovnikove radky vrstvy "produkt" se v tabulce nikdy nesluci jako profily (pricingRowsOf)
        if m.get("model") is True:
            glb = os.path.basename(str(row.get("glb_file") or ""))
            if not glb or not os.path.isfile(os.path.join(KATALOG_GLB_DIR, glb)):
                raise ValueError(f"{pre}: produkt #{pid} nemá 3D model.")
            out["manual"]["model"] = True
    else:
        obr = m.get("obrazky") or []
        if not isinstance(obr, list) or len(obr) > MANUAL_IMAGES_MAX:
            raise ValueError(f"{pre}: nejvýše {MANUAL_IMAGES_MAX} obrázky.")
        cisty = []
        for k in obr:
            km = MANUAL_IMAGE_KEY_RE.match(str(k))
            if not km or int(km.group(1)) != offer_id or not os.path.isfile(os.path.join(OFFER_IMAGES_DIR, str(k))):
                raise ValueError(f"{pre}: neplatný obrázek (nahrajte ho znovu).")
            if str(k) not in cisty:
                cisty.append(str(k))
        if cisty:
            out["manual"]["obrazky"] = cisty
    return out


def _over_rucni_polozky(cur, offer_id, items_in, items_current):
    """Kusovnik z formulare -> (items, None) nebo (None, hlaska). Obycejne radky (z 3D sceny / konfigurace / Vandr) se nesmi pridat, smazat ani prejmenovat (jsou provazane s vykresy a 3D
    pres mesh_group; radek konfigurace musi zustat prvni) - meni se jen mnozstvi a ceny; rucni polozky se pridavaji / meni / mazou volne a jdou VZDY NA KONEC."""
    obycejne_in = [it for it in items_in if not _je_rucni(it)]
    rucni_in = [it for it in items_in if _je_rucni(it)]
    obycejne_cur = [it for it in (items_current or []) if not _je_rucni(it)]
    jmena = lambda seznam: [str(i.get("name")) if isinstance(i, dict) else None for i in seznam]
    if len(obycejne_in) != len(obycejne_cur) or jmena(obycejne_in) != jmena(obycejne_cur):
        return None, "Řádky kusovníku nejde přidávat, mazat ani přejmenovat – jen ruční položky (tlačítka pod tabulkou)."
    if len(rucni_in) > MANUAL_ITEMS_MAX:
        return None, f"Nejvýše {MANUAL_ITEMS_MAX} ručních položek."
    hotove = []
    for i, it in enumerate(rucni_in, 1):
        try:
            hotove.append(_vycisti_rucni_polozku(cur, offer_id, it, i))
        except ValueError as e:
            return None, str(e)
    return obycejne_in + hotove, None


def _obrazek_polozky_cesta(offer_id, key):
    """Cesta k nahranemu obrazku rucni polozky nabidky `offer_id` (klic z nahravani), nebo None (neplatny klic / cizi nabidka)."""
    m = MANUAL_IMAGE_KEY_RE.match(str(key or ""))
    if not m or int(m.group(1)) != offer_id:
        return None
    return os.path.join(OFFER_IMAGES_DIR, str(key))


@app.post("/api/admin/scene-offers/<int:offer_id>/item-images")
@require_permission("nabidky", "upravit")
def admin_scene_offer_item_image_add(offer_id):
    """Nahraje obrazek rucni polozky nabidky ({image: data URI png / jpeg}); vrati {key, url} - klic se pak da do polozky (manual.obrazky) pri ulozeni nabidky (PUT)."""
    if request.content_length and request.content_length > 2 * MAX_IMAGE_BYTES:
        return jsonify({"error": "Obrázek je příliš velký."}), 413
    body = request.get_json(silent=True) or {}
    try:
        data_uri = _validate_data_uri(body.get("image"), "Obrázek")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    m = DATA_URI_RE.match(data_uri)
    raw = base64.b64decode(m.group("b64"), validate=True)
    jpeg = m.group(1) == "jpeg"
    if (jpeg and raw[:3] != b"\xff\xd8\xff") or (not jpeg and raw[:8] != b"\x89PNG\r\n\x1a\n"):
        return jsonify({"error": "Obsah souboru neodpovídá obrázku."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM scene_offers WHERE id=%s", (offer_id,))
            if not cur.fetchone():
                return jsonify({"error": "Nabídka neexistuje."}), 404
    finally:
        conn.close()
    predpona = f"polozka_{offer_id}_"
    if sum(1 for n in os.listdir(OFFER_IMAGES_DIR) if n.startswith(predpona)) >= MANUAL_IMAGES_PER_OFFER_MAX:
        return jsonify({"error": f"K nabídce je nahráno maximum obrázků ({MANUAL_IMAGES_PER_OFFER_MAX})."}), 400
    key = f"{predpona}{secrets.token_hex(8)}.{'jpg' if jpeg else 'png'}"
    with open(os.path.join(OFFER_IMAGES_DIR, key), "wb") as fh:
        fh.write(raw)
    return jsonify({"key": key, "url": f"/api/admin/scene-offers/{offer_id}/item-images/{key}"}), 201


@app.get("/api/admin/scene-offers/<int:offer_id>/item-images/<key>")
@require_permission("nabidky", "zobrazit")
def admin_scene_offer_item_image(offer_id, key):
    path = _obrazek_polozky_cesta(offer_id, key)
    if not path or not os.path.isfile(path):
        return jsonify({"error": "Obrázek nenalezen."}), 404
    return _send_offer_image_path(path)


@app.get("/api/public/offers/<token>/item-image/<key>")
def public_offer_item_image(token, key):
    """Obrazek rucni polozky pro zakaznika - jen kdyz ho nabidka (items) odkazuje."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
    finally:
        conn.close()
    if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
        return jsonify({"error": "Nabídka nebyla nalezena."}), 404
    path = _obrazek_polozky_cesta(offer["id"], key)
    try:
        items = json.loads(offer["items"] or "[]")
    except (TypeError, ValueError):
        items = []
    if not path or not any(_je_rucni(it) and key in (it["manual"].get("obrazky") or []) for it in items):
        return jsonify({"error": "Obrázek nenalezen."}), 404
    return _send_offer_image_path(path)


@app.get("/api/public/offers/<token>/item-model/<int:product_id>")
def public_offer_item_model(token, product_id):
    """3D model (GLB z katalogu) rucni polozky z katalogu - jen kdyz nabidka obsahuje polozku s timto produktem a `manual.model`."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = _resolve_offer_by_token(cur, token)
            if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
                return jsonify({"error": "Nabídka nebyla nalezena."}), 404
            try:
                items = json.loads(offer["items"] or "[]")
            except (TypeError, ValueError):
                items = []
            if not any(_je_rucni(it) and it["manual"].get("model") is True and it.get("product_id") == product_id for it in items):
                return jsonify({"error": "Model není k dispozici."}), 404
            cur.execute("SELECT glb_file FROM shop_products WHERE id=%s", (product_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    glb = os.path.basename(str((row or {}).get("glb_file") or ""))
    if not glb:
        return jsonify({"error": "Model není k dispozici."}), 404
    try:
        with open(os.path.join(KATALOG_GLB_DIR, glb), "rb") as fh:
            data = fh.read()
    except OSError:
        return jsonify({"error": "Model na disku chybí."}), 404
    resp = Response(data, mimetype="model/gltf-binary", headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-cache"})
    resp.set_etag(hashlib.sha256(data).hexdigest()[:32])
    return resp.make_conditional(request)


@app.put("/api/admin/scene-offers/<int:offer_id>")
@require_permission("nabidky", "upravit")
def admin_scene_offer_update(offer_id):
    """Uprava existujici nabidky (Robert 2026-08-10: "plne editovani
    nabidky v adminu"). ZAMERNE OMEZENO na to, co dava smysl menit BEZ
    znovu-otevreni 3D sceny - mnozstvi/cena jednotlivych radku kusovniku,
    celkova cena, popis/patka, volitelne prvky (QR/termin dodani).
    NEJDE pridavat/mazat/prejmenovat OBYCEJNE radky kusovniku ani menit geometrii - ty jsou
    provazane s 3D modelem/vykresy pres groupIdx (viz generateSceneOffer
    ve scene.html), zmena poctu radku by rozbila prolinkovani vykres<->
    kusovnik. Pro skutecne novou sestavu dilu se pouzije normalni cesta
    (znovu vygenerovat nabidku ze sceny). VYJIMKA (bot8, 2026-10-06): RUCNI polozky
    (items[].manual, z katalogu nebo volny text, viz _over_rucni_polozky) se pridavaji /
    meni / mazou volne - jdou na konec kusovniku a nejsou s nicim provazane.

    Pred zapisem se AKTUALNI stav ulozi do scene_offer_revisions jako
    dalsi archivni revize (viz komentar u tabulky v SQL migraci) -
    zadna zmena tak neni nikdy nenavratne ztracena."""
    body = request.get_json(silent=True) or {}
    items = body.get("items")
    total_price = body.get("total_price")
    editable_text = body.get("editable_text") or {}
    change_note = (body.get("change_note") or "").strip()[:500] or None

    if not isinstance(items, list) or not items:
        return jsonify({"error": "Chybí kusovník (items)."}), 400
    if not isinstance(total_price, (int, float)) or total_price < 0:
        return jsonify({"error": "Neplatná celková cena."}), 400
    popis = (editable_text.get("popis") or "").strip()
    patka = (editable_text.get("patka") or "").strip()
    offer_options = _sanitize_offer_options(body.get("offer_options"))
    # Jmeno klienta (bot5, 2026-10-06, Robert: "chci mit moznost doplnit nazev klienta dodatecne v online nabidce"): klic customer_name v tele = nastavit (prazdne = smazat);
    # klic CHYBI (starsi admin.html v cache prohlizece) = zachovat ulozene jmeno, uprava nabidky ho nesmi potichu smazat.
    nastavit_klienta, nove_jmeno = "customer_name" in body, None
    if nastavit_klienta:
        hodnota = body.get("customer_name")
        if hodnota is not None and not isinstance(hodnota, str):
            return jsonify({"error": "Jméno klienta musí být text."}), 400
        nove_jmeno = (hodnota or "").strip() or None
        if nove_jmeno is not None and len(nove_jmeno) > 255:
            return jsonify({"error": "Jméno klienta může mít nejvýše 255 znaků."}), 400

    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT items, total_price, editable_text_popis, editable_text_patka, offer_options, "
                "revision_number, customer_name FROM scene_offers WHERE id=%s FOR UPDATE",
                (offer_id,),
            )
            current = cur.fetchone()
            if not current:
                conn.rollback()
                return jsonify({"error": "Nabídka neexistuje."}), 404
            # Rucni polozky (bot8, 2026-10-06): obycejne radky se nesmi pridat / smazat / prejmenovat, rucni se overi a jdou na konec
            try:
                items_cur = json.loads(current["items"]) if current["items"] else []
            except (TypeError, ValueError):
                items_cur = []
            items, chyba_polozek = _over_rucni_polozky(cur, offer_id, items, items_cur)
            if chyba_polozek:
                conn.rollback()
                return jsonify({"error": chyba_polozek}), 400
            # Systemovy priznak Vandr nabidky (viz _sanitize_offer_options)
            # admin formular neposila - prevzit ho z aktualniho radku, z tela
            # pozadavku se zapnout neda.
            try:
                current_options = json.loads(current["offer_options"]) if current["offer_options"] else {}
            except (TypeError, ValueError):
                current_options = {}
            if isinstance(current_options, dict) and current_options.get("vandr_single_drawing") is True:
                offer_options["vandr_single_drawing"] = True
            else:
                offer_options.pop("vandr_single_drawing", None)
            # Vykresy stran SPOLECNE Vandr nabidky (bot10, 2026-10-06): taky jen z ulozeneho radku (znovu overene) - admin formular je neposila, z tela pozadavku se nastavit nedaji,
            # jinak by je kazda uprava nabidky smazala a stranka by ukazala jediny vykres.
            _kresby = (_sanitize_offer_options({"vandr_single_drawing": True, "vandr_drawings": current_options.get("vandr_drawings")}).get("vandr_drawings")
                       if isinstance(current_options, dict) and offer_options.get("vandr_single_drawing") else None)
            if _kresby:
                offer_options["vandr_drawings"] = _kresby
            else:
                offer_options.pop("vandr_drawings", None)
            # Vandr nabidka bez 2D vykresu (bot5, 2026-10-06): taky jen z ulozeneho radku
            if offer_options.get("vandr_single_drawing") and isinstance(current_options, dict) and current_options.get("vandr_bez_vykresu") is True:
                offer_options["vandr_bez_vykresu"] = True
            else:
                offer_options.pop("vandr_bez_vykresu", None)
            # Snimek konfigurace u nabidky z konfigurace stolu (bot5, 2026-10-06, api/nabidka_z_konfigurace.py): admin formular ho neposila, z tela
            # pozadavku se nastavit neda (sanitize ho nepropousti) - vzdy se bere z aktualniho radku, jinak by ho kazda uprava nabidky smazala.
            for _k in ("source", "config", "config_private"):
                if isinstance(current_options, dict) and _k in current_options:
                    offer_options[_k] = current_options[_k]
                else:
                    offer_options.pop(_k, None)
            # Sazba montaze (bot5, 2026-10-01): admin formular ji posila (prazdne = vychozi sazba -> None). Kdyz klic v pozadavku
            # vubec NENI (starsi admin.html v cache prohlizece), zachova se ulozena volba - editace ji nesmi potichu smazat.
            raw_options = body.get("offer_options")
            if not (isinstance(raw_options, dict) and "montaz_pct" in raw_options):
                offer_options["montaz_pct"] = _sanitize_montaz_pct(
                    current_options.get("montaz_pct") if isinstance(current_options, dict) else None)
            # Sleva (bot16, 2026-10-07): stejny vzor - formular ji posila (prazdne = bez slevy -> None), chybi-li klic (starsi admin.html v cache), ulozena sleva se zachova.
            if not (isinstance(raw_options, dict) and "discount_pct" in raw_options):
                offer_options["discount_pct"] = _sanitize_discount_pct(
                    current_options.get("discount_pct") if isinstance(current_options, dict) else None)
            now = datetime.datetime.now()
            # Archivace AKTUALNIHO (pred-editacniho) stavu - viz komentar
            # v docstringu vyse. Pouziva se puvodni revision_number, novy
            # zaznam v scene_offers dostane +1 (viz UPDATE nize).
            cur.execute(
                "INSERT INTO scene_offer_revisions (offer_id, revision_number, items, total_price, "
                "editable_text_popis, editable_text_patka, offer_options, edited_by, edited_at, change_note) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (offer_id, current["revision_number"], current["items"], current["total_price"],
                 current["editable_text_popis"], current["editable_text_patka"], current["offer_options"],
                 admin["id"], now, change_note),
            )
            cur.execute(
                "UPDATE scene_offers SET items=%s, total_price=%s, editable_text_popis=%s, "
                "editable_text_patka=%s, offer_options=%s, revision_number=revision_number+1, "
                "last_edited_at=%s, last_edited_by=%s" + (", customer_name=%s" if nastavit_klienta else "") + " WHERE id=%s",
                (json.dumps(items, ensure_ascii=False), total_price, popis, patka,
                 json.dumps(offer_options, ensure_ascii=False), now, admin["id"])
                + ((nove_jmeno,) if nastavit_klienta else ()) + (offer_id,),
            )
        conn.commit()
    finally:
        conn.close()
    zmena_klienta = nastavit_klienta and (current["customer_name"] or None) != nove_jmeno
    log_audit(admin["id"], "update", "scene_offer", offer_id, f"editace nabídky (revize {current['revision_number']})"
              + (f"; klient: {(current['customer_name'] or '—')} -> {(nove_jmeno or '—')}" if zmena_klienta else ""))
    return jsonify({"status": "ok", "revision_number": current["revision_number"] + 1})


TEST_OFFER_NUMBER = "TEST"


@app.post("/api/admin/scene-offers/test-offer")
@require_permission("nabidky", "vytvorit")
def admin_scene_offer_test():
    """Stala testovaci nabidka (bot4, Robert 2026-08-05: "dej mi do
    adminu testovaci nabidku stalou tlacitko"). Jedna trvala nabidka s
    cislem 'TEST' (nespotrebovava RM radu, plati 10 let) - prvni klik
    ji zalozi (placeholder vykresy pres PIL + GLB model zkopirovany z
    katalogu), kazdy dalsi klik jen vygeneruje NOVY klientsky odkaz
    (token je v DB jen jako hash, zpetne dohledat nejde) a vrati ho.
    V admin seznamu je videt normalne - admin pohled pres existujici
    "Zobrazit online"."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM scene_offers WHERE offer_number=%s", (TEST_OFFER_NUMBER,))
            row = cur.fetchone()
            view_token = secrets.token_urlsafe(32)
            view_token_hash = hashlib.sha256(view_token.encode()).hexdigest()
            expires_at = datetime.datetime.now() + datetime.timedelta(days=3650)
            if row:
                cur.execute(
                    "UPDATE scene_offers SET view_token_hash=%s, expires_at=%s, is_active=1 WHERE id=%s",
                    (view_token_hash, expires_at, row["id"]),
                )
                offer_id = row["id"]
            else:
                try:
                    from PIL import Image, ImageDraw
                except ImportError:
                    return jsonify({"error": "PIL (pillow) není na serveru k dispozici."}), 500
                view_files = {}
                for key, col in OFFER_VIEW_KEYS.items():
                    img = Image.new("RGB", (900, 640), "#eef1f5")
                    d = ImageDraw.Draw(img)
                    d.rectangle([70, 70, 830, 570], outline="#16324f", width=5)
                    d.rectangle([200, 180, 700, 460], outline="#16324f", width=3)
                    d.line([70, 320, 830, 320], fill="#9199a3", width=2)
                    d.text((90, 90), f"TESTOVACI VYKRES - {key}", fill="#16324f")
                    stored = uuid.uuid4().hex + ".png"
                    img.save(os.path.join(OFFER_IMAGES_DIR, stored))
                    view_files[col] = stored
                # 3D model - prvni dostupny katalogovy GLB (pro test rezimu
                # zobrazeni/prostredi ve vieweru)
                model_stored = None
                katalog_dir = "/opt/konfigurator/webapp/katalog"
                try:
                    glbs = sorted(f for f in os.listdir(katalog_dir) if f.endswith(".glb"))
                    if glbs:
                        model_stored = uuid.uuid4().hex + ".glb"
                        shutil.copy(os.path.join(katalog_dir, glbs[0]), os.path.join(OFFER_MODELS_DIR, model_stored))
                except OSError:
                    model_stored = None
                items = [
                    {"name": "Testovací profil 40x40", "dim": "1000 mm", "qty": "4 ks", "unit_price": 350, "total": 1400},
                    {"name": "Testovací spojka", "dim": "-", "qty": "8 ks", "unit_price": 45, "total": 360},
                ]
                cur.execute(
                    "INSERT INTO scene_offers (offer_number, drive_file_id, items, total_price, "
                    "view_narys, view_bokorys, view_pudorys, view_3d_a, view_3d_b, view_3d_model, "
                    "editable_text_popis, editable_text_patka, customer_name, "
                    "view_token_hash, expires_at, created_by) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        TEST_OFFER_NUMBER, None, json.dumps(items, ensure_ascii=False), 1760,
                        view_files["view_narys"], view_files["view_bokorys"], view_files["view_pudorys"],
                        view_files["view_3d_a"], view_files["view_3d_b"], model_stored,
                        DEFAULT_EDITABLE_TEXT["popis"], DEFAULT_EDITABLE_TEXT["patka"],
                        "Testovací zákazník (stálá testovací nabídka)",
                        view_token_hash, expires_at, admin["id"],
                    ),
                )
                offer_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "read", "scene_offer", offer_id, "test_offer")
    return jsonify({"status": "ok", "offer_id": offer_id, "online_url": f"/nabidka-online.html?t={view_token}"})


@app.post("/api/admin/scene-offers/bulk-delete")
@require_permission("nabidky", "smazat")
def admin_scene_offers_bulk_delete():
    """Hromadne smazani online nabidek (Robert 2026-08-05: "udelej
    bulk mazani v online nabidkach"). DB potomci (views/page_events/
    acceptances/notes/order_prefs) odchazi pres ON DELETE CASCADE,
    fyzicke soubory (5 obrazku pohledu + lokalni kopie GLB modelu) se
    mazou az PO commitu (mirror quotes.py::remove_lead_attachment_files -
    kdyby smazani DB selhalo, soubory zustanou konzistentne na miste).
    Maze se i PDF ze Sdileneho disku (shared_drive_files radek +
    soubor) - mazane nabidky jsou typicky testovaci a jejich PDF by
    jinak zustavalo ve slozce Nabidky jako sirotek; FK drive_file_id
    je ON DELETE SET NULL, poradi mazani je proto jedno.

    Robert pres bot3, 2026-09-14: NA ROZDIL od PDF vyse se Sdileny disk
    zaznam GLB modelu (drive_model_file_id, "Modely nabidek/<cislo>")
    PRI SMAZANI NABIDKY NEMAZE - fyzicka geometrie sceny, ze ktere GLB
    vznikl, uz po smazani nabidky nikde nezustava, takze na rozdil od
    PDF/renderu (ktere lze v principu znovu vygenerovat z dat, co v DB
    porad jsou, dokud se nabidka nesmaze) je model NEOBNOVITELNY -
    zustava trvale dohledatelny na Disku podle offer_number ve nazvu
    slozky/souboru, i kdyz uz samotna nabidka v DB neexistuje."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err

    files_to_remove = []  # (adresar, nazev_souboru)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(
                f"SELECT id, offer_number, drive_file_id, drive_model_file_id, view_narys, view_bokorys, "
                f"view_pudorys, view_3d_a, view_3d_b, view_3d_model "
                f"FROM scene_offers WHERE id IN ({placeholders})",
                ids,
            )
            offers = cur.fetchall()
            if not offers:
                return jsonify({"error": "Žádná z vybraných nabídek neexistuje."}), 404
            drive_file_ids = [o["drive_file_id"] for o in offers if o["drive_file_id"]]
            for o in offers:
                for key in ("view_narys", "view_bokorys", "view_pudorys", "view_3d_a", "view_3d_b"):
                    if o[key]:
                        files_to_remove.append((OFFER_IMAGES_DIR, o[key]))
                if o["view_3d_model"]:
                    files_to_remove.append((OFFER_MODELS_DIR, o["view_3d_model"]))
            if drive_file_ids:
                dph = ",".join(["%s"] * len(drive_file_ids))
                cur.execute(f"SELECT stored_filename FROM shared_drive_files WHERE id IN ({dph})", drive_file_ids)
                for r in cur.fetchall():
                    files_to_remove.append((DRIVE_FILES_DIR, r["stored_filename"]))
                cur.execute(f"DELETE FROM shared_drive_files WHERE id IN ({dph})", drive_file_ids)
            found_ids = [o["id"] for o in offers]
            fph = ",".join(["%s"] * len(found_ids))
            cur.execute(f"DELETE FROM scene_offers WHERE id IN ({fph})", found_ids)
            deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()

    for directory, filename in files_to_remove:
        try:
            os.remove(os.path.join(directory, filename))
        except OSError:
            pass  # soubor uz chybi - DB je autoritativni, nevadi

    numbers = ", ".join(o["offer_number"] for o in offers)
    log_audit(admin["id"], "delete", "scene_offer", None, f"bulk: {numbers}")
    return jsonify({"status": "ok", "deleted": deleted})


@app.post("/api/admin/scene-offers/<int:offer_id>/view-online")
@require_permission("nabidky", "zobrazit")
def admin_scene_offer_view_online(offer_id):
    """Tlacitko "Zobrazit online" v admin seznamu (Robert 2026-08-05).
    Klientsky token je v DB jen jako hash (nejde zpetne dohledat) -
    admin dostava VLASTNI oddeleny token (admin_view_token_hash),
    prepsany pri kazdem kliknuti. Klientsky odkaz, platnost ani
    is_active se NEMENI - na rozdil od regenerate-link vyse je tohle
    ciste "podivat se", ne "vystavit novy odkaz". Neprodluzuje ani
    expires_at - po vyprseni admin uvidi stejnou "vyprselo" stranku
    jako klient (konzistentni pohled; prodlouzeni = Novy odkaz)."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM scene_offers WHERE id=%s", (offer_id,))
            if not cur.fetchone():
                return jsonify({"error": "Nabídka neexistuje."}), 404
            admin_token = secrets.token_urlsafe(32)
            cur.execute(
                "UPDATE scene_offers SET admin_view_token_hash=%s WHERE id=%s",
                (hashlib.sha256(admin_token.encode()).hexdigest(), offer_id),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "read", "scene_offer", offer_id, "view_online")
    return jsonify({"status": "ok", "online_url": f"/nabidka-online.html?t={admin_token}"})


# Robert 2026-08-10 ("upominka pred vyprsenim") - kolik dni pred
# expires_at se ma upominka poslat. Jeden beh (denni timer, viz
# konfigurator-offer-expiry-reminder.timer) pokryje kazdou nabidku
# PRAVE JEDNOU diky reminder_sent_at (nastavi se hned po prvnim uspesnem
# odeslani), takze zvyseni/snizeni tohohle cisla nezpusobi duplicity.
OFFER_REMINDER_DAYS_BEFORE = 3


def run_offer_expiry_reminder_cli():
    """Denni davkova upominka na brzy vyprsejici nabidky - spousti
    systemd timer konfigurator-offer-expiry-reminder.timer. NE pres
    HTTP/Flask, stejny princip jako run_price_refresh_cli v app.py.
    Pouziti: python3 app.py offer-expiry-reminder

    Ktere nabidky se upominaji: is_active=1, jeste NEvyprsely, vyprsi do
    OFFER_REMINDER_DAYS_BEFORE dni, nikdo ji jeste nepotvrdil ani
    neodmitl (viz scene_offer_acceptances/scene_offer_declines - u obou
    uz je zpetna vazba jasna, upominka by byla zbytecna) a upominka
    jeste nebyla poslana (reminder_sent_at IS NULL).

    Komu se posila (Robert 2026-08-10, po AskUserQuestion): kdyz
    scene_offers.customer_email zname (volitelne pole pri vytvoreni
    nabidky ve scene.html), posle se PRIMO zakaznikovi. Kdyz e-mail
    zname NENI, posle se aspon info adminovi/obchodu (SUPPLIER["email"]),
    at se ozve zakaznikovi jinou cestou sam - bez tohohle fallbacku by
    stare/bez e-mailu vytvorene nabidky nedostaly upominku VUBEC.

    reminder_sent_at se nastavi AZ PO uspesnem odeslani e-mailu (per
    nabidka) - pri selhani SMTP zustava NULL, takze se pokus zopakuje
    dalsi den (na rozdil od accept/decline e-mailu vyse, kde je e-mail
    jen informativni navazba k uz ulozene akci - tady je odeslani
    e-mailu SAMOTNA akce, takze ma smysl ji zopakovat)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            now = datetime.datetime.now()
            deadline = now + datetime.timedelta(days=OFFER_REMINDER_DAYS_BEFORE)
            cur.execute(
                "SELECT id, offer_number, customer_name, customer_email, view_token_hash, expires_at "
                "FROM scene_offers "
                "WHERE is_active=1 AND expires_at BETWEEN %s AND %s AND reminder_sent_at IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM scene_offer_acceptances a WHERE a.offer_id=scene_offers.id) "
                "AND NOT EXISTS (SELECT 1 FROM scene_offer_declines d WHERE d.offer_id=scene_offers.id)",
                (now, deadline),
            )
            offers = cur.fetchall()
            print(f"[offer-expiry-reminder] {len(offers)} nabídek k upomenutí")
            for offer in offers:
                days_left = (offer["expires_at"] - now).days
                # Klientsky token se uklada jen jako hash (viz modulovy
                # komentar u scene_offers) - PUVODNI token uz nejde
                # zpetne dohledat. Misto nej se pro upominku pouzije
                # admin "Zobrazit online" cesta (regenerovat by zrusila
                # stary odkaz, coz by u aktivni nabidky bylo nezadouci
                # prekvapeni pro zakaznika, kteremu uz byl puvodni odkaz
                # poslany drive).
                admin_token = secrets.token_urlsafe(32)
                # bot23 2026-08-18: token se MUSI commitnout PRED odeslanim
                # e-mailu, ne az spolecne s reminder_sent_at po uspesnem
                # send_email. Puvodne: kdyz send_email uspel, ale nasledny
                # UPDATE reminder_sent_at / conn.commit() pak selhal (DB
                # vypadek - u tohodle projektu zdokumentovany opakovany
                # problem), except nize zavolal rollback() a zahodil i
                # TENHLE jiz odeslany token - zakaznik dostal e-mail s
                # odkazem, ktery v DB nikdy nezustal ulozeny (404 navzdy),
                # a nabidka se priste znovu vyhodnotila jako needing
                # reminder (reminder_sent_at zustalo NULL) -> dalsi (opet
                # rozbity) e-mail donekonecna.
                cur.execute(
                    "UPDATE scene_offers SET admin_view_token_hash=%s WHERE id=%s",
                    (hashlib.sha256(admin_token.encode()).hexdigest(), offer["id"]),
                )
                conn.commit()
                offer_url = f"{APP_BASE_URL}/nabidka-online.html?t={admin_token}"
                # OPRAVA (bot10, 2026-08-26, schvaleno bot3) - primy
                # send_email() z cron-spousteneho behu obchazel
                # pending-frontu (WORKFLOW.md bod 16) - zakaznikovi tak
                # chodil e-mail bez schvaleni admina, KAZDY DEN. Kdyz je
                # prijemcem REALNY ZAKAZNIK (customer_email znamy nize),
                # jde pořád do fronty beze zmeny. Kdyz prijemcem NENI
                # zakaznik, ale Robertova vlastni adresa (e-mail klienta
                # neznamy, vetev nize) - DALSI VYJIMKA z bodu 16 (Robert
                # primo, 2026-09-15) posila PRIMO. "Uspech" pak znamena
                # bud "radek se ulozi jako pending" (zakaznik), nebo
                # "e-mail se skutecne odeslal" (admin fallback) - v obou
                # pripadech az POTE se nastavi reminder_sent_at; retry
                # logika (rollback pri selhani) zustava beze zmeny.
                try:
                    if offer["customer_email"]:
                        cur.execute(
                            "INSERT INTO system_emails (user_id, kind, recipient_email, subject, body_text, status, trigger_type) "
                            "VALUES (NULL,'scene_offer_expiry_reminder',%s,%s,%s,'pending','auto')",
                            (
                                offer["customer_email"],
                                f"Nabídka {offer['offer_number']} brzy vyprší",
                                f"Dobrý den{', ' + offer['customer_name'] if offer['customer_name'] else ''},\n\n"
                                f"platnost nabídky {offer['offer_number']} vyprší za {days_left} "
                                f"{'den' if days_left == 1 else ('dny' if 1 < days_left < 5 else 'dní')} "
                                f"({offer['expires_at'].strftime('%d.%m.%Y')}).\n\n"
                                f"Pokud budete potřebovat více času nebo máte k nabídce dotaz, "
                                f"ozvěte se nám prosím - rádi platnost prodloužíme.\n\n"
                                f"Odkaz na nabídku: {offer_url}\n\n"
                                f"{SUPPLIER['name']}\n{SUPPLIER['email']}\n{SUPPLIER.get('phone', '')}",
                            ),
                        )
                    else:
                        # DALSI VYJIMKA z bodu 16 (Robert primo, 2026-09-15,
                        # "proc je to v odchozi poste a ne v prichozi") -
                        # jediny prijemce tady je Robertova vlastni adresa
                        # (SUPPLIER["email"]), ne treti strana - posila se
                        # PRIMO, mimo pending-frontu (viz WORKFLOW.md bod 16,
                        # qa_checks._SEND_EMAIL_APPROVED_WRAPPERS). NA ROZDIL
                        # od vetve vyse (customer_email znamy) - ta zustava
                        # frontou beze zmeny, ma REALNEHO zakaznika jako
                        # prijemce.
                        send_email(
                            SUPPLIER["email"],
                            f"Nabídka {offer['offer_number']} brzy vyprší - e-mail klienta neznámý",
                            f"Nabídka {offer['offer_number']}"
                            f"{' (' + offer['customer_name'] + ')' if offer['customer_name'] else ''} "
                            f"vyprší za {days_left} dní ({offer['expires_at'].strftime('%d.%m.%Y')}) "
                            f"a zákazník na ni zatím nereagoval. E-mail zákazníka není u nabídky vyplněný - "
                            f"kontaktujte ho prosím jinou cestou.\n\n"
                            f"Odkaz na nabídku: {offer_url}",
                        )
                    cur.execute(
                        "UPDATE scene_offers SET reminder_sent_at=%s WHERE id=%s",
                        (now, offer["id"]),
                    )
                    conn.commit()
                    print(f"[offer-expiry-reminder] {offer['offer_number']}: OK "
                          + (f"(zarazeno do fronty, klient {offer['customer_email']})"
                             if offer["customer_email"] else "(odesláno přímo adminovi, e-mail klienta neznámý)"))
                except Exception as e:
                    conn.rollback()
                    print(f"[offer-expiry-reminder] {offer['offer_number']}: CHYBA {e}")
    finally:
        conn.close()
