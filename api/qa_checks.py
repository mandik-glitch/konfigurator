"""
QA kontroly konzistence dat i UI napric administraci - bot4, 2026-08-09,
rozsireno bot3 2026-08-10.

Sdileny modul mezi scripts/qa_product_audit.py (CLI, opakovatelny beh
mimo Flask) a qa_audit.py (admin panel /api/admin/qa-audit, zalozka
Dashboard) - jedna sada kontrol, dva zpusoby jak si je precist, zadna
duplicita logiky.

Kazda kontrola: fn(cur) -> list[(id, name, detail_string)]. Zadna
kontrola nic sama neopravuje, jen hlasi - oprava se dela zvlast a
rucne (viz backups/profile_description_length_fix_20260809.json pro
prvni takovou opravu, ktera k tomuhle modulu vedla).

Robert 2026-08-10 ("napříč naším celým kódem s nedokonalosti chybějící
prvky... vymyslí nějaký chytrý skript který by nám toto na pozadí
neustále kontroloval") - puvodne jen produktova data, ted rozsireno o
kontroly NAPRIC domenami (admin UI, kategorie, homepage mozaika,
fotobanka). "Na pozadí neustále" = tenhle modul uz beze zmeny bezi zive
pri kazdem otevreni Dashboardu (loadQaAudit() v admin.html) - zadny
novy cron/systemd timer nebyl potreba, jen vic kontrol ve stejnem
existujicim mechanismu. Explicitne zvazeno a NEudelano: automaticka
oprava nalezu (Robert zvolil "jen hledat a hlasit" v AskUserQuestion) -
kazda kontrola tu jen REPORTUJE, oprava zustava na botovi/Robertovi.
"""
import ast
import glob
import itertools
import html.parser
import json
import math
import os
import re
import struct

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KATALOG_GLB_DIR = os.path.join(REPO_ROOT, "webapp", "katalog")
WEBAPP_DIR = os.path.join(REPO_ROOT, "webapp")
API_DIR = os.path.join(REPO_ROOT, "api")
# Robert 2026-08-10 (upresneni): "já nemluvím o kontrolách dat... já
# chci aby se hledali chyby v kódu který vytváří prostředí" +
# "kontrolovalo to co se předpokládá že je precizně nasazené v celém
# systému ale nemusí to být pravda" - nasledujici kontroly (
# check_duplicate_html_id/check_dangling_get_element_by_id/
# check_broken_fetch_endpoint) skenuji VSECHNY stranky webapp/*.html,
# ne data v DB - hledaji konkretni tridu bugu, kdy kod na jednom miste
# PREDPOKLADA neco (existenci id, existenci backend route), co uz
# jinde v kodu neplati (prejmenovano/smazano/preklep). Overeno na
# realnem kodu 2026-08-10: nalezeny 2 skutecne bugy (viz AGENTS_LOG).
HTML_FILES = tuple(sorted(glob.glob(os.path.join(WEBAPP_DIR, "*.html"))))
API_FILES = tuple(sorted(glob.glob(os.path.join(API_DIR, "*.py"))))

# bot3 2026-08-11 (Robert: "v administraci konfiguratoru přijde vsechno
# zpomalene") - 21 z 38 kontrol nezavisle prochazi HTML_FILES/API_FILES a
# KAZDA z nich sama znovu cte stejne soubory z disku (admin.html 908KB,
# scene.html 1.1MB) - namereno 5.75s na jedno kompletni run_checks()
# (viz AGENTS_LOG). Admin dashboard navic voli /api/admin/qa-audit 2x
# najednou (kategorie "opravit"+"doplnit"), takze kazde otevreni
# zalozky Dashboard = ~5.75s blokovani gunicorn workeru.
# Reseni: cache podle (cesta, mtime) - NE prosty cas/TTL cache, protoze
# tenhle modul bezi ZIVE nad AKTUALNIM stavem souboru (dokumentovano
# vyse - "jakmile se podkladovy problem oprav, dalsi refresh uz ho
# proste nenajde") a vic botu dnes soubory prubezne edituje. Klic
# obsahuje mtime, takze zmena souboru automaticky zneplatni cache -
# zadne riziko zastaraleho vysledku, jen se nezmenene soubory nectou
# z disku znovu pri kazde ze zbylych ~20 kontrol ve stejnem behu (a i
# napric ruznymi HTTP pozadavky v ramci stejneho gunicorn workeru,
# pokud se soubory mezitim nezmenily).
_file_content_cache = {}


def _read_cached(path):
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        # soubor mezitim zmizel - necachovat, at chybu vidi volajici kod
        with open(path, encoding="utf-8") as f:
            return f.read()
    cached = _file_content_cache.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    with open(path, encoding="utf-8") as f:
        content = f.read()
    _file_content_cache[path] = (mtime, content)
    return content
# Sdileno vice kontrolami (check_dead_button, check_dangling_get_element_
# by_id) - kazdy quotovany retezec, ktery vypada jako identifikator.
_ALL_QUOTED_IDENT_RE = re.compile(r'''["']([A-Za-z][\w-]*)["']''')

# ---- Balicky stranek: HTML + JS, ktery nacita -------------------------
# Do 2026-09-03 zil vsechen JS primo v <script> blocich uvnitr
# webapp/*.html, takze krizovym kontrolam stacil JEDEN soubor -
# getElementById("x") i id="x" lezely vedle sebe. Split frontendu
# (webapp/admin/js/*.js 18 souboru, webapp/js/*.js 5 souboru) ten
# predpoklad zrusil a 5 kontrol tim ROZBIL. Nehlasily min, ale VIC:
# 298 falesnych "nezapojene tlacitko" v admin.html/scene.html, protoze
# zapojeni se odstehovalo do modulu (napr. #qaBugRefreshBtn ma
# .onclick v admin/js/dashboard.js:444). Zaroven glob("webapp/*.html")
# ty moduly nevidi vubec, takze ~1,7 MB ziveho JS nekontroloval nikdo.
# Nalezeno a opraveno bot18, 2026-09-03.
#
# Reseni: kontrola, ktera krizove porovnava JS proti HTML, se pta na
# CELY BALICEK stranky (HTML + vsechny lokalni <script src>), ne na
# jeden soubor. Sdileny modul (client-errors.js nacita 29 stranek) je
# validni, pokud obstoji u ASPON JEDNE stranky, ktera ho nacita - jinak
# by kazda dalsi stranka vyrobila falesny nalez.
_SCRIPT_SRC_RE = re.compile(r'<script[^>]*\bsrc="([^"]+)"', re.I)
# Extrahujici protejsek _FN_EXISTS_RE_TMPL (viz nize) - stejne tvary
# definice, ale vytahuje JMENA, aby se dala udelat mnozina a nemusel se
# pro kazde jmeno znovu prohledavat 1,2 MB textu balicku.
_FN_DEF_NAME_RE = re.compile(
    r'\bfunction\s+(\w+)\s*\(|\b(\w+)\s*=\s*function\s*\(|\b(?:const|let|var)\s+(\w+)\s*=')

_bundle_cache = {}


# Vsechny frontend zdroje VCETNE podadresaru - pro kontroly, ktere
# NEPOTREBUJI parovat JS s HTML, protoze protejsek hledaji mimo
# skenovany soubor (fetch -> Flask route v api/*.py, audio klic ->
# soubor na disku) nebo cistě uvnitř jednoho souboru (duplicitni
# deklarace funkce). Vynechava node_modules/, katalog/ (GLB assety) a
# content-files/ (nahrany obsah, ne nas kod).
def _all_frontend_files():
    # PROC os.walk s orezem, ne glob("**"): tahle funkce bezi PRI IMPORTU (ALL_FRONTEND_FILES nize), tedy v KAZDEM gunicorn workeru pri kazdem startu a HUP.
    # Puvodni glob("**", recursive=True) prochazel i vynechane adresare (vyfiltrovaly se az po nalezeni) a sledoval symbolicke odkazy: zbloudily odkaz
    # webapp/webapp -> /opt/konfigurator/webapp (vznikl 2026-10-03 21:47) z toho udelal smycku, kazdy import trval 45-85 s a po kazdem nasazeni (HUP)
    # obsluha stala 44-57 s (nalez bot9, 2026-10-04, cestou pres scripts/restart_konfigurator.sh --stav; pravidlo 57 pocita ~4 s).
    # Ted: vynechane adresare (node_modules, katalog, content-files - jen na nejvyssi urovni, jako dosud) se ani neotevrou, odkazy na adresare se nesleduji
    # (zadna smycka), skryte soubory a adresare se preskoci (stejne jako glob). Vysledek je stejny (overeno srovnanim s puvodnim globem).
    skip_top = ("node_modules", "katalog", "content-files")
    found = []
    for root, dirs, files in os.walk(WEBAPP_DIR, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith(".") and not (root == WEBAPP_DIR and d in skip_top)]
        for name in files:
            if not name.startswith(".") and (name.endswith(".html") or name.endswith(".js")):
                found.append(os.path.join(root, name))
    return tuple(sorted(set(found)))


ALL_FRONTEND_FILES = _all_frontend_files()


def _disp(path):
    """Jmeno souboru do hlaseni. Soubory primo ve webapp/ zustavaji na
    holem basename (ID uz existujicich nalezu se tim nemeni), vnorene
    dostanou cestu vuci webapp/ - samotny basename by dva stejne
    pojmenovane moduly v ruznych adresarich tise slil do jednoho ID."""
    rel = os.path.relpath(path, WEBAPP_DIR)
    return os.path.basename(path) if os.sep not in rel else rel


def _page_scripts(html_path):
    """Lokalni .js soubory, ktere stranka nacita pres <script src>."""
    try:
        content = _read_cached(html_path)
    except Exception:
        return ()
    found = []
    for src in _SCRIPT_SRC_RE.findall(content):
        if src.startswith(("http://", "https://", "//")):
            continue
        p = os.path.normpath(os.path.join(WEBAPP_DIR, src.split("?")[0].lstrip("/")))
        if p.startswith(WEBAPP_DIR + os.sep) and p.endswith(".js") and os.path.isfile(p):
            found.append(p)
    return tuple(dict.fromkeys(found))


def _bundle_sources(html_path):
    """(html, js1, js2, ...) - vsechny zdroje jedne stranky."""
    return (html_path,) + _page_scripts(html_path)


def _bundle_data(html_path):
    """Odvozena data balicku, cachovana podle mtime VSECH jeho souboru.
    run_checks() bezi zive z admin Dashboardu (~8,6 s na beh) - kdyby si
    kazda z 5 krizovych kontrol znovu spojovala a regexovala 1,2 MB
    (admin.html + 19 modulu), byl by to nekolikanasobek."""
    srcs = _bundle_sources(html_path)
    try:
        key = tuple(os.path.getmtime(p) for p in srcs)
    except OSError:
        key = None
    cached = _bundle_cache.get(html_path)
    if key is not None and cached is not None and cached[0] == key:
        return cached[1]
    text = "\n".join(_read_cached(p) for p in srcs)
    quoted_counts = {}
    for m in _ALL_QUOTED_IDENT_RE.finditer(text):
        quoted_counts[m.group(1)] = quoted_counts.get(m.group(1), 0) + 1
    queried_classes = set()
    for m in _QUERY_SELECTOR_ALL_RE.finditer(text):
        for tok in m.group(1).replace(",", " ").split():
            queried_classes.add(tok.lstrip("."))
    defined_fns = set()
    for m in _FN_DEF_NAME_RE.finditer(text):
        defined_fns.add(next(g for g in m.groups() if g))
    data = {
        "sources": srcs,
        "text": text,
        "quoted_counts": quoted_counts,
        "queried_classes": queried_classes,
        "defined_fns": defined_fns,
        "declared_ids": set(re.findall(r'''\bid\s*=\s*["']([\w-]+)["']''', text)),
    }
    if key is not None:
        _bundle_cache[html_path] = (key, data)
    return data


def _merge_bundle_findings(per_file_ok):
    """Sdileny modul obstoji, staci-li u JEDNE stranky, ktera ho nacita.
    per_file_ok: {(disp, klic): bool} slucovane pres OR volajicim."""
    return sorted(k for k, ok in per_file_ok.items() if not ok)


# Duplikat OWNER_TABLE z gallery_items.py (NE import - ten by pres
# `from app import app, ...` natahl cely Flask app modul i do
# scripts/qa_product_audit.py, ktery je schvalne "cisty CLI skript" bez
# zavislosti na Flasku, viz komentar u load_db_config() tam). Mapovani
# se meni zridka; pri pridani noveho owner_type do gallery_items.py
# aktualizovat i tady.
GALLERY_OWNER_TABLE = {
    "category": "content_categories", "product": "shop_products",
    "document": "shop_documents", "stock_movement": "shop_stock_movements",
    "po_item": "shop_purchase_order_items", "order": "shop_orders",
    "inbox": "app_users", "lead": "crm_leads", "homepage_block": "homepage_blocks",
}

# Soubory admin nastroju, kde se hlida "kazde modalove okno ma zavirak"
# (Robert: "chybějící zavírací křížky oken") - jen tyhle dva, product.html/
# category.html/index.html jsou zakaznicke stranky bez modalu tohohle typu.
ADMIN_UI_FILES = ("admin.html", "scene.html")


class _ModalCloseScanner(html.parser.HTMLParser):
    """Heuristicky scanner: najde korenove modalove <div id="...Modal(Box|
    Overlay)?">, ne vnitrni prvky se stejnym prefixem (napr. "hpbModalErr"
    neni samostatny dialog, jen pole uvnitr nej - proto presna koncovka
    Modal/ModalBox/ModalOverlay, ne jen substring "modal"). Vnorene
    korenove divy (ModalOverlay obaluje ModalBox) se hlasi jen jednou (ten
    vnejsi), aby stejny dialog nevygeneroval dva nalezy. "Zaviraci signal"
    = ✕/✖/× znak v textu, title="Zavřít", nebo trida obsahujici "close"
    (cem-close, fw-shapes-close-btn, ...) kdekoli v podstromu.

    extra_root_ids: dalsi id, ktera se maji povazovat za "korenovy prvek
    vyzadujici zavirak", i kdyz nejde o <div> a jmeno nekonci na Modal/
    ModalBox/ModalOverlay (viz check_public_page_missing_close_link -
    zakaznicka "detail" stranka otevrena z dlazdice/karty ma stejnou
    UX potrebu jasne cesty zpet, i kdyz strukturalne neni modal)."""

    def __init__(self, extra_root_ids=None):
        super().__init__()
        self.stack = []
        self.results = []
        self.extra_root_ids = extra_root_ids or set()

    def _mark_close_on_modal_ancestors(self):
        for frame in self.stack:
            if frame["is_modal_root"]:
                frame["has_close"] = True

    def handle_starttag(self, tag, attrs):
        self._handle_open(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._handle_open(tag, attrs, self_closing=True)

    def _handle_open(self, tag, attrs, self_closing):
        attrs_d = dict(attrs)
        elem_id = attrs_d.get("id", "") or ""
        cls = attrs_d.get("class", "") or ""
        title = attrs_d.get("title", "") or ""
        if "close" in cls.lower() or title.strip() == "Zavřít":
            self._mark_close_on_modal_ancestors()
        is_modal_root = (
            (tag == "div" and bool(re.search(r"Modal(Box|Overlay)?$", elem_id)))
            or elem_id in self.extra_root_ids
        )
        already_nested = any(f["is_modal_root"] for f in self.stack)
        if not self_closing:
            self.stack.append({
                "tag": tag, "is_modal_root": is_modal_root, "id": elem_id,
                "has_close": False, "report": is_modal_root and not already_nested,
            })

    def handle_data(self, data):
        if "✕" in data or "✖" in data or "×" in data:
            self._mark_close_on_modal_ancestors()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                popped = self.stack.pop()
                while len(self.stack) > i:
                    extra = self.stack.pop()
                    if extra["report"]:
                        self.results.append((extra["id"], extra["has_close"]))
                if popped["report"]:
                    self.results.append((popped["id"], popped["has_close"]))
                break


def check_admin_modal_missing_close(cur):
    out = []
    for fname in ADMIN_UI_FILES:
        path = os.path.join(REPO_ROOT, "webapp", fname)
        try:
            content = _read_cached(path)
            p = _ModalCloseScanner()
            p.feed(content)
        except Exception as e:
            # Parsovani nesmi shodit cely audit - jen se tenhle soubor
            # tise vynecha (stejny princip jako try/except v loadQaAudit()).
            out.append((f"{fname}:parse-error", fname, f"sken selhal ({e}) - zkontroluj ručně"))
            continue
        for elem_id, has_close in p.results:
            if not has_close:
                out.append((f"{fname}:{elem_id}", elem_id, f"modální okno v {fname} nemá zjevné zavírací tlačítko"))
    return out


# Robert 2026-08-10 ("otevřená dlaždice nema zaviraci krizek, jakto ze
# to nenasel hledac chyb?", navazuje na pravidlo #9 vyse u ADMIN_UI_FILES) -
# check_admin_modal_missing_close byl zamerne scoped jen na admin.html/
# scene.html, protoze "product.html/category.html/index.html jsou
# zakaznicke stranky bez modalu tohoto typu" (viz komentar u
# ADMIN_UI_FILES). Predpoklad byl mylny: /blok/<slug> (webapp/blok.html,
# #blockArticle) je zakaznicka stranka otevrena kliknutim na dlazdici
# homepage mozaiky a potrebuje stejnou jasnou cestu zpet, i kdyz
# strukturalne nejde o <div id=...Modal> (je to <article>). Samostatna
# kontrola s EXPLICITNIM seznamem znamych "detail stranek otevrenych z
# karty/dlazdice" (ne broad heuristika napric vsemi zakaznickymi
# strankami - bezny clanek/stranka nepotrebuje "zavirak", vysoke riziko
# falesnych nalezu). Pri pridani dalsi podobne stranky (dalsi "otevri z
# karty" detail) sem pridat radek.
PUBLIC_DETAIL_PAGE_ROOTS = {
    "blok.html": ("blockArticle",),
}


def check_public_page_missing_close_link(cur):
    out = []
    for fname, root_ids in PUBLIC_DETAIL_PAGE_ROOTS.items():
        path = os.path.join(WEBAPP_DIR, fname)
        try:
            content = _read_cached(path)
            p = _ModalCloseScanner(extra_root_ids=set(root_ids))
            p.feed(content)
        except Exception as e:
            out.append((f"{fname}:parse-error", fname, f"sken selhal ({e}) - zkontroluj ručně"))
            continue
        for elem_id, has_close in p.results:
            if not has_close:
                out.append((f"{fname}:{elem_id}", elem_id, f"stránka {fname} otevřená z dlaždice/karty nemá viditelnou cestu zpět (#{elem_id})"))
    return out


class _ButtonCollector(html.parser.HTMLParser):
    """Sbira <button id="X"> / <input type="button" id="X">, ktere
    SKUTECNE potrebuji vlastni JS zapojeni - vynechava implicitni
    submit tlacitka (<button> bez type="..." UVNITR <form> je dle
    specifikace type="submit", zpracovava ho formularuv submit handler,
    zadne primo tlacitko-specificke zapojeni netreba)."""

    def __init__(self):
        super().__init__()
        self.buttons = []
        self.form_depth = 0

    def handle_starttag(self, tag, attrs):
        self._handle(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._handle(tag, attrs, self_closing=True)

    def _handle(self, tag, attrs, self_closing):
        d = dict(attrs)
        if tag == "form" and not self_closing:
            self.form_depth += 1
            return
        explicit_type = d.get("type")
        if tag == "button":
            resolved_type = explicit_type or ("submit" if self.form_depth > 0 else "button")
        elif tag == "input":
            resolved_type = explicit_type
        else:
            resolved_type = None
        is_button = (tag == "button" and resolved_type != "submit") or (tag == "input" and resolved_type == "button")
        if is_button and d.get("id"):
            self.buttons.append((d["id"], "onclick" in d, (d.get("class") or "").split()))

    def handle_endtag(self, tag):
        if tag == "form" and self.form_depth > 0:
            self.form_depth -= 1


_QUERY_SELECTOR_ALL_RE = re.compile(r'(?:querySelectorAll|getElementsByClassName)\(\s*["\']([^"\']+)["\']')


def check_dead_button(cur):
    # Robert 2026-08-10 ("musí jít především systémem křížem krážem, tak
    # aby se procházela opravdu každá tabulka, každé okno, každé
    # tlačítko") - komplement k dangling_get_element_by_id (ten hleda JS
    # odkazy BEZ HTML id, tenhle hleda HTML tlacitka BEZ JAKEHOKOLI JS
    # zapojeni - ani onclick atribut, ani getElementById/jina quotovana
    # zminka kdekoli v souboru). Overeno synteticky (skutecne nezapojene
    # tlacitko chyti, implicitni submit/onclick/getElementById-jinde
    # spravne vynecha) - aktualne 0 nalezu na realnem kodu.
    #
    # OPRAVA (bot8, 2026-08-18, Robertovo "nekolik bodu se tyka sceny" -
    # 7 falesnych nalezu attachTeachModeCorner/CornerSide/.../None):
    # tyhle tlacitka NEMAJI vlastni getElementById zapojeni, jsou
    # zapojena HROMADNE pres sdilenou tridu (viz scene.html
    # `document.querySelectorAll(".attach-teach-mode-btn").forEach(b =>
    # b.addEventListener(...))` + `b.dataset.mode`) - legitimni,
    # bezny vzor delegovaneho zapojeni v tomhle projektu, ne bug. Puvodni
    # kontrola hledala jen VLASTNI id retezec jinde v souboru, takze
    # tenhle vzor vzdy falesne nahlasila. Ted se tlacitko NEnahlasi i
    # kdyz ma id pouzite jen jednou, pokud nektera z jeho CSS trid je
    # pouzita v querySelectorAll/getElementsByClassName kdekoli v souboru
    # (skutecny dukaz hromadneho zapojeni, ne jen shoda nahodou).
    out = []
    for path in HTML_FILES:
        fname = os.path.basename(path)
        try:
            content = _read_cached(path)
            p = _ButtonCollector()
            p.feed(content)
        except Exception as e:
            out.append((f"{fname}:parse-error", fname, f"sken selhal ({e}) - zkontroluj ručně"))
            continue
        # Zapojeni se hleda v CELEM balicku stranky, ne jen v HTML -
        # po splitu frontendu zije .onclick/querySelectorAll v modulech
        # (viz komentar u _bundle_data).
        bundle = _bundle_data(path)
        counts = bundle["quoted_counts"]
        queried_classes = bundle["queried_classes"]
        for btn_id, has_onclick, classes in p.buttons:
            if has_onclick:
                continue
            if counts.get(btn_id, 0) > 1:
                continue
            if any(c in queried_classes for c in classes):
                continue
            out.append((f"{fname}:{btn_id}", btn_id, f"<button id=\"{btn_id}\"> v {fname} - id se nikde v JS nepoužívá (možná nezapojené tlačítko)"))
    return out


class _IdCollector(html.parser.HTMLParser):
    """Sbira id="X" na SKUTECNYCH DOM prvcich (html.parser automaticky
    preskakuje obsah <script>/<style> jako raw text, takze nechyta
    "id" retezce uvnitr JS retezcu/sablon - jen realne HTML atributy)."""

    def __init__(self):
        super().__init__()
        self.counts = {}

    def handle_starttag(self, tag, attrs):
        self._handle(attrs)

    def handle_startendtag(self, tag, attrs):
        self._handle(attrs)

    def _handle(self, attrs):
        elem_id = dict(attrs).get("id")
        if elem_id:
            self.counts[elem_id] = self.counts.get(elem_id, 0) + 1


def check_duplicate_html_id(cur):
    # Dva prvky se stejnym id na jedne strance - getElementById() vrati
    # jen ten prvni, druhy je pro JS nedosazitelny (typicky copy-paste
    # bug, viz #jointPositionReviewButtons ve scene.html - dva ruzne
    # panely omylem sdileji stejne id tlacitkoveho kontejneru).
    out = []
    for path in HTML_FILES:
        fname = os.path.basename(path)
        try:
            content = _read_cached(path)
            p = _IdCollector()
            p.feed(content)
        except Exception as e:
            out.append((f"{fname}:parse-error", fname, f"sken selhal ({e}) - zkontroluj ručně"))
            continue
        for elem_id, count in p.counts.items():
            if count > 1:
                out.append((f"{fname}:{elem_id}", elem_id, f"id=\"{elem_id}\" v {fname} použito {count}×"))
    return out


# bot16, 2026-10-01: HTML komentar, ktery ve svem TELE obsahuje zaviraci sekvenci (typicky citovanou v uvozovkach pri
# vysvetlovani drivejsi chyby), se uzavre uz u jejiho PRVNIHO vyskytu a zbytek textu se zobrazi na strance jako
# VIDITELNY text. Presne to se 5 dni delo v admin.html (zalozka Koeficienty cen: surovy text komentare mezi popisem
# a varovanim) - objeveno az screenshotem, grep ani curl to nepoznaji (v souboru je vsechno "na spravnem miste").
# Detekce: zaviraci sekvence MIMO otevreny komentar, nebo komentar, ktery se neuzavre vubec. <script>/<style> se
# preskakuji (komentare v nich nejsou HTML komentare).
_HTML_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b", re.I)


def _najdi_zbloudile_zavirace_komentaru(text):
    """[(cislo_radku, uryvek)] pro kazdy zaviraci '-->' mimo HTML komentar a kazdy neuzavreny komentar."""
    nalez = []
    i, n = 0, len(text)
    while i < n:
        m = _HTML_SCRIPT_STYLE_RE.search(text, i)
        otevirac = text.find("<!--", i)
        zavirac = text.find("-->", i)
        kandidati = [x for x in (m.start() if m else None, otevirac if otevirac >= 0 else None,
                                 zavirac if zavirac >= 0 else None) if x is not None]
        if not kandidati:
            break
        p = min(kandidati)
        if m and p == m.start():
            konec = re.compile(r"</%s\s*>" % m.group(1), re.I).search(text, m.end())
            i = konec.end() if konec else n
        elif otevirac >= 0 and p == otevirac:
            e = text.find("-->", otevirac + 4)
            if e < 0:
                nalez.append((text.count("\n", 0, otevirac) + 1, "komentář se vůbec neuzavírá"))
                break
            i = e + 3
        else:
            nalez.append((text.count("\n", 0, zavirac) + 1,
                          "zaviraci sekvence mimo komentar: ..." + text[max(0, zavirac - 30):zavirac + 20].replace("\n", " ") + "..."))
            i = zavirac + 3
    return nalez


def check_html_comment_stray_close(cur):
    out = []
    for path in HTML_FILES:
        fname = os.path.basename(path)
        try:
            content = _read_cached(path)
        except Exception as e:
            out.append((f"{fname}:read-error", fname, f"sken selhal ({e}) - zkontroluj ručně"))
            continue
        for radek, uryvek in _najdi_zbloudile_zavirace_komentaru(content):
            out.append((f"{fname}:{radek}", fname,
                        f"{fname}, řádek {radek}: {uryvek} - zbytek komentáře je na stránce vidět jako text"))
    return out


# Kazdy quotovany retezec, ktery vypada jako identifikator - ne jen ty
# po "id=". Duvod: nekolik mist v kodu nestavi id primo (id="X"), ale
# pres pomocnou funkci/objekt (napr. scFieldInput(key, id, val) vraci
# `<input id="${id}">`, nebo initFloatingShapesWindow({winId: "X", ...})
# az uvnitr dela `win.id = opts.winId`) - trasovat kazdou takovou
# indirekci by bylo krehke. Misto toho: pokud se retezec "X" v souboru
# vyskytuje jako quotovany literal VICEKRAT nez jen v
# getElementById('X') samotnem, predpoklada se, ze nekde jinde je to
# skutecne deklarace/predani id (i kdyz neprimo) - a nehlasi se.
# Skutecne mrtve reference (viz btnAxisMoveMode) se v souboru jako
# quotovany retezec NEVYSKYTUJI vubec jinde (jen jako CSS
# selektor/JS identifikator - to same "slovo", ale ne string literal).
_GET_ELEM_RE = re.compile(r'''getElementById\(\s*["']([\w-]+)["']\s*\)''')


def check_dangling_get_element_by_id(cur):
    # Sken bezi pres VSECHNY zdroje balicku (HTML + jeho .js moduly) a
    # id se overuje proti celemu balicku - po splitu je volani v .js,
    # ale id="..." zustalo v .html.
    out = []
    ok_by_file = {}
    for html_path in HTML_FILES:
        try:
            bundle = _bundle_data(html_path)
        except Exception as e:
            fname = os.path.basename(html_path)
            out.append((f"{fname}:parse-error", fname, f"čtení selhalo ({e})"))
            continue
        counts = bundle["quoted_counts"]
        for src in bundle["sources"]:
            try:
                content = _read_cached(src)
            except Exception:
                continue
            disp = _disp(src)
            for elem_id in set(_GET_ELEM_RE.findall(content)):
                key = (disp, elem_id)
                ok_by_file[key] = ok_by_file.get(key, False) or counts.get(elem_id, 0) > 1
    for disp, elem_id in _merge_bundle_findings(ok_by_file):
        out.append((f"{disp}:{elem_id}", elem_id,
                    f"getElementById('{elem_id}') v {disp} - id se nevyskytuje nikde na stránce, "
                    "která tenhle soubor načítá (ani v jejích dalších skriptech)"))
    return out



# Klice zalozek adminu: admin.html ma tlacitka <button class="tab-btn"
# data-tab="orders">, backend i JS na ne odkazuji RETEZCEM. Kdyz se
# retezec rozejde se skutecnym atributem, querySelector vrati null a
# odkaz TISE nedela nic - zadna chyba v konzoli, zadny vizualni signal.
# Presne tohle mel panel "Ke schvaleni" u sekce Prijate doklady:
# api/approvals.py posilalo "incoming-documents", skutecny atribut je
# "incomingdocuments" (nalezeno a opraveno bot18, 2026-09-03).
# Stejna trida jako check_dangling_get_element_by_id - kod na jednom
# miste PREDPOKLADA existenci identifikatoru, ktery jinde neplati.
_ADMIN_TAB_ATTR_RE = re.compile(r'data-tab="([a-z0-9_-]+)"')
_ADMIN_TAB_PY_RE = re.compile(r'"tab"\s*:\s*"([a-z0-9_-]+)"')
_ADMIN_TAB_SELECTOR_RE = re.compile(r'tab-btn\[data-tab="([a-z0-9_-]+)"\]')


def check_dangling_admin_tab_key(cur):
    admin_html = os.path.join(WEBAPP_DIR, "admin.html")
    try:
        admin_src = _read_cached(admin_html)
    except Exception as e:
        return [("admin_tab_key:parse-error", "admin.html", f"čtení admin.html selhalo ({e})")]
    # Mnozina SKUTECNE existujicich zalozek. Dynamicky sestavene
    # selektory (CSS.escape(key) apod.) sem zamerne nespadnou - regex
    # bere jen doslovne male alfanumericke klice.
    valid = set(_ADMIN_TAB_ATTR_RE.findall(admin_src))
    if not valid:
        return [("admin_tab_key:no-tabs", "admin.html", "v admin.html nenalezen zadny data-tab - kontrola by hlasila vse, preskoceno")]
    out = []
    # 1) backendem posilane klice (napr. api/approvals.py "tab": "...")
    for path in API_FILES:
        fname = os.path.basename(path)
        try:
            content = _read_cached(path)
        except Exception:
            continue
        for key in sorted(set(_ADMIN_TAB_PY_RE.findall(content))):
            if key not in valid:
                out.append((f"{fname}:tab:{key}", fname,
                            f'{fname} posílá klíč záložky "{key}", ale admin.html žádné '
                            f'data-tab="{key}" nemá - odkaz v UI tiše nic neudělá'))
    # 2) staticke selektory v adminovem JS. POZOR: webapp/admin/js/*.js
    # se globuje zvlast - HTML_FILES je jen glob("webapp/*.html") a
    # moduly vyclenene ze split iniciativy 2026-09-03 do nej nespadaji.
    js_sources = sorted(glob.glob(os.path.join(WEBAPP_DIR, "admin", "js", "*.js"))) + [admin_html]
    for path in js_sources:
        fname = os.path.basename(path)
        try:
            content = _read_cached(path)
        except Exception:
            continue
        for key in sorted(set(_ADMIN_TAB_SELECTOR_RE.findall(content))):
            if key not in valid:
                out.append((f"{fname}:selector:{key}", fname,
                            f'{fname} hledá .tab-btn[data-tab="{key}"], ale taková záložka '
                            f'v admin.html neexistuje - querySelector vrátí null'))
    return out


# Route registrovane bud dekoratorem (@app.get("/path")) NEBO primym
# volanim (app.get("/path", endpoint="...")(require_permission(...)
# (fn)) - viz api/orders.py shipping/payment-methods CRUD. Regex bez
# vyzadovaneho "@" chyti obe formy stejne.
_ROUTE_RE = re.compile(r'''\bapp\.(get|post|put|delete|patch)\(\s*["']([^"']+)["']''')
_FETCH_STATIC_RE = re.compile(r'''fetch\(\s*["'](/api/[^"']*)["'](?!\s*\+)''')
_FETCH_TEMPLATE_RE = re.compile(r'''fetch\(\s*`(/api/[^`]*)`''')
_TEMPLATE_EXPR_RE = re.compile(r"\$\{[^}]*\}")
_SENTINEL = "\x00"


def _path_segments(path, is_js=False):
    if is_js:
        # ${...} bloky (vc. obsahu, treba i literalniho "?" uvnitr
        # podminenych retezcu jako "accShowArchived ? '?archived=1' :
        # ''") se NEJDRIV nahradi sentinelem - jinak by naivni split na
        # "?" usekl cestu uprostred template vyrazu.
        path = _TEMPLATE_EXPR_RE.sub(_SENTINEL, path)
    path = path.split("?")[0]
    return [s for s in path.split("/") if s != ""]


def _normalize_flask_segment(seg):
    return None if (seg.startswith("<") and seg.endswith(">")) else seg  # None = wildcard


def _normalize_js_segment(seg):
    if _SENTINEL not in seg:
        return seg
    stripped = seg.replace(_SENTINEL, "")
    return stripped if stripped else None  # cely segment byl jen ${...} -> wildcard


def _route_matches(js_segments, flask_segments):
    if len(js_segments) != len(flask_segments):
        return False
    for js_seg, fl_seg in zip(js_segments, flask_segments):
        fl_norm = _normalize_flask_segment(fl_seg)
        if fl_norm is None:
            continue
        js_norm = _normalize_js_segment(js_seg)
        if js_norm is None:
            continue
        if js_norm != fl_norm:
            return False
    return True


def check_broken_fetch_endpoint(cur):
    routes = []
    for path in glob.glob(os.path.join(API_DIR, "*.py")):
        content = _read_cached(path)
        for method, route in _ROUTE_RE.findall(content):
            routes.append(_path_segments(route))
    out = []
    # Route se hledaji mimo skenovany soubor (v api/*.py), takze .js
    # moduly staci pridat do seznamu zdroju - zadna krizova logika.
    for path in ALL_FRONTEND_FILES:
        fname = _disp(path)
        try:
            content = _read_cached(path)
        except Exception as e:
            out.append((f"{fname}:parse-error", fname, f"čtení selhalo ({e})"))
            continue
        calls = set(_FETCH_STATIC_RE.findall(content)) | set(_FETCH_TEMPLATE_RE.findall(content))
        for call_path in sorted(calls):
            js_segs = _path_segments(call_path, is_js=True)
            if not js_segs or js_segs[0] != "api":
                continue
            if not any(_route_matches(js_segs, fs) for fs in routes):
                out.append((f"{fname}:{call_path}", call_path, f"fetch('{call_path}') v {fname} - žádná odpovídající backend route"))
    return out


# bot5 2026-09-12 (pravidlo #8, nalezeno pri archivaci karty 3942):
# VEREJNA SSR stranka hledala slug BEZ filtru viditelnosti, zatimco
# funkce, ktera ji vykresluje, filtr `active=1 AND is_archived=0` ma.
# Vysledek: skryty produkt routu prosel, data se nenasla a odesla se
# PRAZDNA SKORAPKA se stavem **200** misto 404 - ucebnicovy soft-404.
# Neexistujici slug pritom vracel 404 spravne, takze si toho nikdo
# nevsiml; rozdil je videt az pri primem srovnani obou pripadu.
#
# Proc je to TRIDA chyby, ne jednorazovost: `/produkt/<slug>` a
# `/kategorie/<slug>` maji tentyz tvar a obe tabulky maji sloupec
# viditelnosti. V dobe nalezu byl projev jen u produktu (111 ze 718
# melo active=0/is_archived=1), u kategorii byl LATENTNI - skrytych
# kategorii bylo zrovna nula, takze by se to ozvalo az u prvni skryte.
# Presne na tohle je automaticka kontrola, ne rucni revize.
#
# Druhy dusledek, mene zjevny: vetev s presmerovanim
# (`shop_product_redirects`) se spousti jen kdyz slug NESEDI na zadny
# radek. Dokud skryty produkt slug "zabiral", nemohl na nej zadny
# 301 redirect vystrelit, i kdyby v tabulce byl.
#
# Co se ZAMERNE NEHLASI: dotaz bez filtru, kdyz je v teze funkci
# ZAROVEN dotaz s filtrem - to je legitimni vzor "staff vidi i skryte,
# anonym ne" (nahled pred aktivaci, viz products.py u
# /api/shop/products/<id>). Hlida se chybejici filtr, ne jeho pritomnost.
_SSR_SLUG_ROUTE_RE = re.compile(
    r'@app\.get\(\s*["\'](/(?!api/)[^"\']*<slug>[^"\']*)["\']\s*\)\s*\ndef\s+(\w+)',
)
_SLUG_SELECT_RE = re.compile(r"FROM\s+(\w+)\s+WHERE\s+slug\s*=\s*%s", re.IGNORECASE)
_VIDITELNOST_SLOUPCE = ("active", "is_visible", "is_archived", "is_public")
# Dlouhy SQL dotaz byva v Pythonu slozeny z nekolika retezcovych literalu
# pod sebou, takze filtr casto lezi AZ ZA uzaviraci uvozovkou toho
# literalu, kde konci `slug=%s`. Okno se proto bere ze zdrojaku za
# nalezem (ne do konce literalu) - jinak kontrola hlasi jako chybu i
# spravne odfiltrovany dotaz. Presne na tohle prvni verze tehle kontroly
# najela: opravenou routu oznacila za rozbitou.
_OKNO_ZA_NALEZEM = 220


def _telo_funkce(content, start):
    """Telo handleru od jeho `def` po dalsi dekorator/definici na sloupci 0."""
    konec = len(content)
    for m in re.finditer(r"^(?:@app\.|def )", content[start:], re.MULTILINE):
        if m.start() > 0:
            konec = start + m.start()
            break
    return content[start:konec]


def check_ssr_slug_route_without_visibility_filter(cur):
    # Ktere tabulky vubec maji sloupec viditelnosti - bez toho nema smysl
    # filtr vyzadovat (napr. homepage_blocks uz `AND is_visible=1` maji).
    sloupce_tabulky = {}

    def ma_viditelnost(tabulka):
        if tabulka not in sloupce_tabulky:
            try:
                cur.execute(f"SHOW COLUMNS FROM `{tabulka}`")
                sloupce_tabulky[tabulka] = {r["Field"] for r in cur.fetchall()}
            except Exception:  # noqa: BLE001 - tabulka neexistuje = nic nehlidame
                sloupce_tabulky[tabulka] = set()
        return sorted(sloupce_tabulky[tabulka] & set(_VIDITELNOST_SLOUPCE))

    out = []
    for path in glob.glob(os.path.join(API_DIR, "*.py")):
        content = _read_cached(path)
        fname = _disp(path)
        for m in _SSR_SLUG_ROUTE_RE.finditer(content):
            route, funkce = m.group(1), m.group(2)
            telo = _telo_funkce(content, m.end())
            nalezy = list(_SLUG_SELECT_RE.finditer(telo))
            if not nalezy:
                continue
            # Staci JEDEN dotaz s filtrem - druhy bez filtru je pak
            # legitimni staff vetev (viz komentar vyse). Okno se rezne i
            # o dalsi `execute`, at filtr z NASLEDUJICIHO dotazu nepropusti
            # ten soucasny.
            s_filtrem = False
            for nalez in nalezy:
                okno = telo[nalez.end():nalez.end() + _OKNO_ZA_NALEZEM]
                dalsi = okno.find("execute")
                if dalsi != -1:
                    okno = okno[:dalsi]
                if any(sl in okno.lower() for sl in _VIDITELNOST_SLOUPCE):
                    s_filtrem = True
                    break
            if s_filtrem:
                continue
            tabulka = nalezy[0].group(1)
            viditelnost = ma_viditelnost(tabulka)
            if not viditelnost:
                continue
            out.append((
                f"{fname}:{funkce}",
                route,
                f"{fname}: veřejná SSR routa {route} ({funkce}) hledá slug v `{tabulka}` "
                f"bez filtru viditelnosti ({'/'.join(viditelnost)}). Skrytý záznam routou "
                f"projde a stránka odejde jako prázdná skořápka se stavem 200 místo 404 "
                f"(soft-404); navíc kvůli tomu nemůže vystřelit 301 z tabulky přesměrování.",
            ))
    return out


# bot9 2026-08-19 (pravidlo #9 WORKFLOW.md, nalezeno pri stavbe
# mobilniho hlasoveho faceliftu Remesla): hlasovy Moderator prehrava
# predpripravene .wav vyzvy podle KLICE v kodu (`audio: "customer"` ->
# content-files/remeslo-voice-prompts/customer.wav). Kdyz nekdo prida
# novy zamer/krok a zapomene vyzvu vygenerovat (soubory jsou mimo git,
# generuji se Piperem), selhani je TICHE: audio.play() spadne do
# catch/onerror, appka jen preskoci hlas a rovnou posloucha - na
# desktopu si toho nikdo nevsimne, ale hands-free na mobilu prijde
# remeslnik o celou otazku. Tahle kontrola to hlasi driv, nez na to
# nekdo narazi v terenu.
VOICE_PROMPT_DIR = os.path.join(WEBAPP_DIR, "content-files", "remeslo-voice-prompts")
_VOICE_PROMPT_KEY_RE = re.compile(
    r'(?:audio|navigateAudio)\s*:\s*"([a-z0-9_]+)"'
    r'|playPrompt\(\s*"([a-z0-9_]+)"'
)


# bot9 2026-08-20 (pravidlo #9, nalez bot11 z auditu Remesla kolo 2):
# Remeslo ma vlastni domenu (remeslnik.pro), ale zdedilo APP_BASE_URL z
# hlavniho Konfiguratoru (od 2026-09-06 autovestavby.logiman.cz, drive
# vandrawee.cz - ta DNS je zrusena, viz AGENTS_LOG.md). Verejny odkaz na
# nabidku se z ni stavel dal i pote, co Remeslo vlastni domenu dostalo -
# zakaznik remeslnika tak dostal do e-mailu odkaz na uplne cizi znacku.
# Selhani je TICHE: odkaz funguje (oba vhosty sdili docroot), jen miri
# jinam, nez ma - proto to nasel az rucni audit.
#
# Kontrola hlida OBE podoby te chyby:
#   1. api/remeslo.py stavi URL z APP_BASE_URL (ma pouzivat
#      PUBLIC_PROFILE_DOMAIN),
#   2. stranky Remesla (webapp/remeslo*.html) maji natvrdo napsanou
#      e-shopovou domenu z APP_BASE_URL.
# ZAMERNE NEHLASI PUBLIC_PROFILE_BACKLINK_DOMAIN - SEO backlink v
# paticce vizitek na e-shopovou domenu mirit MA (viz check
# remeslo_backlink_domain_self_reference, ktery hlida opak).
_REMESLO_APP_BASE_URL_RE = re.compile(r"APP_BASE_URL")


def _blank_comments(content):
    """Nahradi obsah HTML (<!-- -->) i radkovych JS (//) komentaru
    mezerami - zachova delku i pocet radku, takze cisla radku dal sedi."""
    def blank(m):
        return "".join(ch if ch == "\n" else " " for ch in m.group(0))
    content = re.sub(r"<!--.*?-->", blank, content, flags=re.S)
    content = re.sub(r"^\s*//.*$", blank, content, flags=re.M)
    return content


def check_remeslo_link_uses_eshop_domain(cur):
    out = []
    remeslo_py = os.path.join(API_DIR, "remeslo.py")
    if os.path.exists(remeslo_py):
        try:
            content = _read_cached(remeslo_py)
        except Exception:
            content = ""
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or not _REMESLO_APP_BASE_URL_RE.search(line):
                continue
            # import samotne konstanty ani komentar/docstring o ni nevadi -
            # hlasi se az POUZITI ve skladani URL
            if "http" in line or "/remeslo" in line or "f\"" in line:
                out.append((f"remeslo.py:{i}", "APP_BASE_URL",
                            f"api/remeslo.py:{i} staví URL z APP_BASE_URL (e-shopová doména) - "
                            f"veřejné odkazy Řemesla patří na PUBLIC_PROFILE_DOMAIN"))
    eshop_host = ""
    base = os.environ.get("APP_BASE_URL", "")
    if "//" in base:
        eshop_host = base.split("//", 1)[1].split("/")[0].strip()
    if eshop_host:
        for path in sorted(glob.glob(os.path.join(WEBAPP_DIR, "remeslo*.html"))):
            fname = os.path.basename(path)
            try:
                content = _read_cached(path)
            except Exception:
                continue
            # Komentare (HTML i JS) se VYMASKUJI, ne filtruji radek po
            # radku - vysvetlujici komentar bezne pretece pres vic radku a
            # heuristika "obsahuje slovo backlink" by chytla jen ten prvni
            # (presne tak tahle kontrola pri prvnim behu falesne nahlasila
            # muj vlastni komentar o SEO backlinku). Delka se zachovava,
            # aby sedela cisla radku.
            content = _blank_comments(content)
            for i, line in enumerate(content.splitlines(), 1):
                if eshop_host not in line:
                    continue
                out.append((f"{fname}:{i}", eshop_host,
                            f"{fname}:{i} má natvrdo e-shopovou doménu {eshop_host} - "
                            f"stránka Řemesla má ukazovat vlastní doménu"))
    return out


def check_missing_voice_prompt_file(cur):
    if not os.path.isdir(VOICE_PROMPT_DIR):
        return []  # slozka je mimo git - na cistem checkoutu nehlasit nic
    out = []
    sources = ALL_FRONTEND_FILES
    for path in sources:
        fname = os.path.basename(path)
        try:
            content = _read_cached(path)
        except Exception:
            continue
        # jen soubory, ktere s hlasovymi vyzvami skutecne pracuji
        if "remeslo-voice-prompts" not in content:
            continue
        keys = set()
        for m in _VOICE_PROMPT_KEY_RE.finditer(content):
            keys.add(m.group(1) or m.group(2))
        for key in sorted(keys):
            if not os.path.exists(os.path.join(VOICE_PROMPT_DIR, key + ".wav")):
                out.append((
                    f"{fname}:{key}", key,
                    f"hlasová výzva '{key}' v {fname} nemá vygenerovaný {key}.wav "
                    f"(Piper, length_scale=0.72) - krok by proběhl bez hlasu",
                ))
    return out


def check_category_missing_meta_description(cur):
    cur.execute(
        "SELECT id, name FROM content_categories "
        "WHERE is_visible=1 AND (meta_description IS NULL OR TRIM(meta_description)='')"
    )
    return [(r["id"], r["name"], "viditelná kategorie bez meta popisu (SEO)") for r in cur.fetchall()]


def check_homepage_block_missing_image(cur):
    # bot5 2026-08-11: galerijni dlazdice (gallery_category IS NOT NULL,
    # viz sloupec z 2026-08-10 "rozdel dlazdici Realizace na vestavby a
    # stoly") vlastni obrazek zamerne NEMAJI - toci fotky primo z
    # fotogalerie dane kategorie. Kontrola je drive falesne hlasila
    # (nalezeno pri auditu "mame produkty plne vyladene vsechny?").
    cur.execute(
        "SELECT id, title FROM homepage_blocks "
        "WHERE is_visible=1 AND (image_filename IS NULL OR image_filename='') "
        "AND (gallery_category IS NULL OR gallery_category='')"
    )
    return [(r["id"], r["title"], "viditelná dlaždice homepage mozaiky bez obrázku") for r in cur.fetchall()]


def check_orphaned_gallery_items(cur):
    out = []
    for owner_type, table in GALLERY_OWNER_TABLE.items():
        cur.execute(
            "SELECT g.id, g.owner_id FROM content_gallery_items g "
            f"WHERE g.owner_type=%s AND NOT EXISTS (SELECT 1 FROM {table} t WHERE t.id=g.owner_id)",
            (owner_type,),
        )
        for r in cur.fetchall():
            out.append((r["id"], f"gallery item #{r['id']}", f"owner_type='{owner_type}' owner_id={r['owner_id']} v {table} neexistuje"))
    return out


# Robert 2026-08-10 ("musí hledat nové typy chyb") - dalsi tri kontroly,
# kazda jina TRIDA bugu nez dosavadnich 10 (ne dalsi "id/odkaz
# neexistuje" varianta):
#
# - duplicate_js_function / duplicate_py_function: stejne pojmenovana
#   funkce deklarovana 2x na NEJVYSSI urovni souboru - druha definice
#   tise PREPISE prvni (JS i Python), takze prvni verze je nedosazitelna
#   mrtvy kod, ktery navic muze matit pri cteni/upravach. JS varianta je
#   ZAMERNE jen regexem na sloupec 0 (^function jmeno() bez odsazeni) -
#   prvni pokus (bez ukotveni na sloupec 0) mel 6 "nálezů", vsechny
#   false positive (lokalni funkce se stejnym jmenem uvnitr RUZNYCH
#   uzavreni, napr. 10x "function onMove()" v ruznych obsluhach tazeni
#   mysi - naprosto v poradku, ruzny scope). Python varianta pouziva
#   ast.parse (spolehlivejsi nez regex, Python ma vestaveny parser).
# - dead_css_selector: CSS #id selektor v <style> bloku, pro ktery
#   neexistuje odpovidajici id="..." (staticke ani nepřímo postavene -
#   stejna heuristika jako dangling_get_element_by_id). Extrakce PRES
#   html.parser (ne regex) - prvni pokus regexem <style>(.*?)</style>
#   omylem chytal i text "<style>" uvnitr HTML komentaru/JS template
#   literalu (napr. document.write(`...<style>...`) v admin.html),
#   coz zpusobilo, ze regex "polykal" tisice radku mezi nahodnym
#   textovym vyskytem a vzdalenym skutecnym </style>.
def check_duplicate_js_function(cur):
    fn_re = re.compile(r'^(?:async )?function (\w+)\(', re.MULTILINE)
    out = []
    for path in ALL_FRONTEND_FILES:
        fname = _disp(path)
        content = _read_cached(path)
        # .js soubor nema <script> tag - cely soubor JE jeden blok
        scripts = ([content] if path.endswith(".js")
                   else re.findall(r'<script(?![^>]*src=)[^>]*>(.*?)</script>', content, re.DOTALL))
        counts = {}
        for s in scripts:
            for m in fn_re.finditer(s):
                counts[m.group(1)] = counts.get(m.group(1), 0) + 1
        for name, c in counts.items():
            if c > 1:
                out.append((f"{fname}:{name}", name, f"function {name}() v {fname} deklarována {c}× na nejvyšší úrovni (druhá tiše přepíše první)"))
    return out


def check_duplicate_py_function(cur):
    out = []
    for path in API_FILES:
        fname = os.path.basename(path)
        try:
            tree = ast.parse(_read_cached(path), filename=path)
        except SyntaxError as e:
            out.append((f"{fname}:syntax-error", fname, f"sken selhal ({e})"))
            continue
        counts = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                counts.setdefault(node.name, []).append(node.lineno)
        for name, lines in counts.items():
            if len(lines) > 1:
                out.append((f"{fname}:{name}", name, f"def {name}() v {fname} deklarována {len(lines)}× na řádcích {lines} (druhá tiše přepíše první)"))
    return out


_CSS_ID_SEL_RE = re.compile(r'#([A-Za-z][\w-]*)')


class _StyleTextCollector(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_style = False
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self.in_style = True

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            self.chunks.append(data)


def check_dead_css_selector(cur):
    out = []
    for path in HTML_FILES:
        fname = os.path.basename(path)
        try:
            content = _read_cached(path)
            p = _StyleTextCollector()
            p.feed(content)
        except Exception as e:
            out.append((f"{fname}:parse-error", fname, f"sken selhal ({e})"))
            continue
        style_content = "\n".join(p.chunks)
        if not style_content.strip():
            continue
        style_content = re.sub(r"/\*.*?\*/", "", style_content, flags=re.DOTALL)
        css_ids = set(_CSS_ID_SEL_RE.findall(style_content))
        # Hex barvy (#fff, #e07070, #ffffffee...) vypadaji syntakticky
        # identicky jako #id selektor.
        css_ids = {i for i in css_ids if not (len(i) in (3, 4, 6, 8) and re.fullmatch(r"[0-9a-fA-F]+", i))}
        # id muze byt deklarovane v HTML i vyrabene v JS modulu stranky
        bundle = _bundle_data(path)
        declared_ids = bundle["declared_ids"]
        all_quoted = set(bundle["quoted_counts"])
        for css_id in sorted(css_ids):
            if css_id in declared_ids or css_id in all_quoted:
                continue
            out.append((f"{fname}:{css_id}", css_id, f"CSS #{css_id} v {fname} - takové id nikde v HTML/JS neexistuje"))
    return out


# Robert 2026-08-10 ("Potřebujeme mít dokonalý že potřebujeme hledat
# desítky jiných typů chyb") - dalsi 3 kontroly, tridy bugu z Python
# backendu (ast.parse, ne regex - spolehlivejsi):
#
# - bare_except: "except:" bez typu chyti i KeyboardInterrupt/
#   SystemExit/GeneratorExit (ne jen ocekavane vyjimky) - typicky
#   nechtene, umi schovat skutecnou chybu a znemoznit ukoncit proces.
# - mutable_default_arg: "def f(x=[])"/"def f(x={})" - vychozi hodnota
#   se v Pythonu vytvori JEDNOU pri definici funkce a SDILI mezi vsemi
#   volanimi bez explicitniho argumentu, coz je klasicky zdroj bugu
#   (nezamerne sdileny stav mezi ruznymi requesty/volanimi).
# - admin_route_missing_permission: "/api/admin/..." route bez
#   @require_permission/@admin_required/@login_required dekoratoru A
#   bez rucniho current_user() gatingu v tele. Overeno na realnem kodu:
#   prvni verze (jen dekoratory) mela 1 "nalez" - approvals_overview()
#   v api/approvals.py - ktery ale dela gating RUCNE (current_user() +
#   explicitni if not user/not active -> 401), jen ne dekoratorem
#   (zamerne, viz komentar tam: "ZADNY permission filtr, vidi to kazdy
#   prihlaseny uzivatel"). Pridano rozpoznani inline current_user()
#   volani kdekoli v tele funkce jako platny gating -> 0 nalezu (zadny
#   admin endpoint dnes neni bez jakehokoli gatingu).
#
# Ctvrta ctverice tehoz kola - opet ruzne tridy bugu:
# - broken_static_image_src: <img src="..."> na staticky (ne JS-sablonou
#   stavěny) soubor, ktery na disku neexistuje. Extrakce PRES html.parser
#   (ne regex pres cely soubor) - regex by chytil i "<img src=...>"
#   zmineny jako TEXT uvnitr JS komentare (dokumentacni priklad syntaxe),
#   html.parser takovy text spravne ignoruje (neni to skutecny tag).
# - dangling_onclick_function: onclick="fn()" na atributu, kde fn neni
#   nikde v souboru definovana (function fn(){}/fn=function(){}/const fn=).
# - duplicate_api_route: dve ruzne registrace stejne (metoda, cesta) v
#   ruznych api/*.py souborech - druha muze tise zastinit prvni ve
#   Flask/Werkzeug routovani. qa_checks.py sam je z hledani VYNECHAN -
#   jeho vlastni komentare obsahuji priklady zapisu routy jako text.
# - requests_no_timeout: requests.get/post/... bez timeout= - bez limitu
#   muze cely request handler viset navzdy, pokud vzdaleny server
#   neodpovida (zadny takovy volani dnes v kodu neni, kontrola slouzi
#   jako regrese do budoucna).
#
# Zvazeno a VYNECHANO v tomhle kole (prilis sumu na realnem kodu):
# - dead_css_class_selector (komplement dead_css_selector pro .trida) -
#   68 "nalezu" na realnem kodu, drtiva vetsina false positive (tridy
#   pridavane/odebirane dynamicky pres classList.toggle/add s promennou
#   nebo template literalem, ktere se v souboru neobjevi jako presny
#   quotovany retezec, + externi knihovna Quill si sama injektuje vlastni
#   tridy ql-editor/ql-toolbar/ql-container, ktere v nasem kodu vubec
#   nejsou deklarovane). Vyzaduje hlubsi analyzu nez tohle kolo dovoluje.
# - print_statement_leftover (print() v backendu misto logovani) - vetsina
#   z 51 nalezu byla v CLI/migracnich/import skriptech (db_setup.py,
#   import_*.py, obj_to_fbx_blender.py...), kde je print() zcela bezny a
#   spravny zpusob vystupu, ne zapomenuty debug kod - kontrola by casteji
#   hlasila spravny kod jako bug nez skutecny problem.
def check_bare_except(cur):
    out = []
    for path in API_FILES:
        fname = os.path.basename(path)
        try:
            tree = ast.parse(_read_cached(path), filename=path)
        except SyntaxError as e:
            out.append((f"{fname}:syntax-error", fname, f"sken selhal ({e})"))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                out.append((f"{fname}:{node.lineno}", fname, f"holé except: na řádku {node.lineno} v {fname} - chytá i KeyboardInterrupt/SystemExit"))
    return out


def check_mutable_default_arg(cur):
    out = []
    for path in API_FILES:
        fname = os.path.basename(path)
        try:
            tree = ast.parse(_read_cached(path), filename=path)
        except SyntaxError as e:
            out.append((f"{fname}:syntax-error", fname, f"sken selhal ({e})"))
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in list(node.args.defaults) + list(node.args.kw_defaults):
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        out.append((f"{fname}:{node.lineno}", fname, f"def {node.name}() na řádku {node.lineno} v {fname} má měnitelnou výchozí hodnotu (list/dict/set) - sdílí se mezi voláními"))
    return out


_PERMISSION_GATE_NAMES = ("require_permission", "admin_required", "login_required", "staff_required")


def check_admin_route_missing_permission(cur):
    out = []
    for path in API_FILES:
        fname = os.path.basename(path)
        try:
            tree = ast.parse(_read_cached(path), filename=path)
        except SyntaxError as e:
            out.append((f"{fname}:syntax-error", fname, f"sken selhal ({e})"))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            route_paths = []
            has_permission_check = False
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    if dec.func.attr in ("get", "post", "put", "delete", "patch") and dec.args:
                        arg0 = dec.args[0]
                        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                            route_paths.append(arg0.value)
                    if dec.func.attr in _PERMISSION_GATE_NAMES:
                        has_permission_check = True
                elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id in _PERMISSION_GATE_NAMES:
                    has_permission_check = True
                elif isinstance(dec, ast.Name) and dec.id in _PERMISSION_GATE_NAMES:
                    has_permission_check = True
            if not has_permission_check:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "current_user":
                        has_permission_check = True
                        break
            admin_paths = [p for p in route_paths if p.startswith("/api/admin/")]
            if admin_paths and not has_permission_check:
                out.append((f"{fname}:{node.name}", node.name, f"{node.name}() ({', '.join(admin_paths)}) v {fname} nemá žádné ověření oprávnění"))
    return out


class _ImgSrcCollector(html.parser.HTMLParser):
    """html.parser preskakuje obsah <script> (raw CDATA) i HTML komentare
    <!-- ... --> automaticky - na rozdil od naiveho regexu pres cely
    soubor to nechyti priklad "<img src=...>" zminovany jako TEXT uvnitr
    JS radkoveho komentare (dokumentacni priklad syntaxe, ne skutecny
    DOM prvek)."""

    def __init__(self):
        super().__init__()
        self.srcs = []

    def handle_starttag(self, tag, attrs):
        self._handle(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._handle(tag, attrs)

    def _handle(self, tag, attrs):
        if tag == "img":
            src = dict(attrs).get("src")
            if src:
                self.srcs.append(src)


class _AuthInputCollector(html.parser.HTMLParser):
    """Sbira <input autocomplete="username"/"current-password"/"new-password">
    - pole, ktera prohlizec/spravce hesel ma nabidnout ulozit/vyplnit.
    Autocomplete hodnota sama casto NESTACI (viz check_auth_input_missing_name) -
    nektere mobilni spravce hesel (potvrzeno Robertem na realnem
    zarizeni) k rozpoznani vyzaduji i atribut name=, ne jen id=."""

    AUTH_VALUES = {"username", "current-password", "new-password"}

    def __init__(self):
        super().__init__()
        self.fields = []

    def handle_starttag(self, tag, attrs):
        self._handle(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._handle(tag, attrs)

    def _handle(self, tag, attrs):
        if tag != "input":
            return
        d = dict(attrs)
        ac = (d.get("autocomplete") or "").strip().lower()
        if ac in self.AUTH_VALUES:
            self.fields.append((ac, d.get("name"), d.get("id")))


def check_auth_input_missing_name(cur):
    # Robert 2026-08-11 ("Na mobilu se mi nenabízí heslo uložené pro
    # přihlášení") - login.html/capture.html/register.html mely
    # autocomplete="username"/"current-password"/"new-password", ale
    # zadne name= (jen id=) - staci to pro desktop Chrome, ale ne pro
    # vsechny mobilni spravce hesel. Tahle kontrola hlida, aby se stejna
    # trida chyby neopakovala v budoucich formularich/strankach.
    out = []
    for path in HTML_FILES:
        fname = os.path.basename(path)
        try:
            content = _read_cached(path)
            p = _AuthInputCollector()
            p.feed(content)
        except Exception as e:
            out.append((f"{fname}:parse-error", fname, f"sken selhal ({e})"))
            continue
        for ac, name, elem_id in p.fields:
            if not name:
                label = elem_id or ac
                out.append((f"{fname}:{label}", label,
                            f"<input autocomplete=\"{ac}\"> v {fname} nemá name= - mobilní správci hesel ho pak nemusí nabídnout k uložení/vyplnění"))
    return out


class _AssetRefCollector(html.parser.HTMLParser):
    """Sbira <script src=...> a <link href=...> (jen rel, ktere skutecne
    ukazuji na staticky soubor - manifest/ikony/stylesheet, ne
    "preconnect"/"dns-prefetch" apod.) - check_broken_static_image_src
    resi jen <img src>, tohle je stejna trida chyby na jinych znackach."""

    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        self._handle(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._handle(tag, attrs)

    _LINK_RELS = {"manifest", "icon", "shortcut icon", "apple-touch-icon", "mask-icon", "stylesheet"}

    def _handle(self, tag, attrs):
        d = dict(attrs)
        if tag == "script":
            src = d.get("src")
            if src:
                self.refs.append(("script", src))
        elif tag == "link":
            rel = (d.get("rel") or "").lower()
            href = d.get("href")
            if href and rel in self._LINK_RELS:
                self.refs.append(("link", href))


_CSS_URL_REF_RE = re.compile(r'url\(\s*[\'"]?([^\'")]+)[\'"]?\s*\)')


def check_broken_static_asset_ref(cur):
    """Rozsireni check_broken_static_image_src (jen <img src>) na dalsi
    staticke assety: <script src>, <link href> (manifest/ikony/
    stylesheet) a url(...) uvnitr <style> bloku (fonty/pozadi CSS) -
    stejna trida chyby (kod odkazuje na soubor, ktery byl mezitim
    prejmenovan/smazan), jina mnozina znacek. GLB soubory se resi uz
    v check_missing_glb_file (jsou dynamicke, {id}.glb z DB, ne staticky
    retezec v HTML). bot5 2026-09-02 (QA kontrolni mechanismy, ukol C)."""
    out = []
    for path in HTML_FILES:
        fname = os.path.basename(path)
        try:
            content = _read_cached(path)
        except Exception as e:
            out.append((f"{fname}:parse-error", fname, f"čtení selhalo ({e})"))
            continue

        def _is_skippable(ref):
            return ref.startswith(("http://", "https://", "//", "data:")) or "{" in ref or "$" in ref

        try:
            p = _AssetRefCollector()
            p.feed(content)
            for kind, ref in sorted(set(p.refs)):
                if _is_skippable(ref):
                    continue
                clean = ref.split("?", 1)[0].split("#", 1)[0]
                full = os.path.join(WEBAPP_DIR, clean.lstrip("/"))
                if not os.path.isfile(full):
                    tag_desc = "script src" if kind == "script" else "link href"
                    out.append((f"{fname}:{kind}:{ref}", ref,
                                f"<{tag_desc}=\"{ref}\"> v {fname} - soubor na disku neexistuje"))
        except Exception as e:
            out.append((f"{fname}:parse-error", fname, f"sken <script>/<link> selhal ({e})"))

        try:
            sp = _StyleTextCollector()
            sp.feed(content)
            style_content = "\n".join(sp.chunks)
            for url_ref in sorted(set(_CSS_URL_REF_RE.findall(style_content))):
                clean = url_ref.split("?", 1)[0].split("#", 1)[0]
                if not clean or _is_skippable(clean) or clean.startswith("#"):
                    continue
                full = os.path.join(WEBAPP_DIR, clean.lstrip("/"))
                if not os.path.isfile(full):
                    out.append((f"{fname}:css-url:{url_ref}", url_ref,
                                f"CSS url({url_ref}) v <style> {fname} - soubor na disku neexistuje"))
        except Exception:
            pass
    return out


def check_broken_static_image_src(cur):
    out = []
    for path in HTML_FILES:
        fname = os.path.basename(path)
        try:
            content = _read_cached(path)
            p = _ImgSrcCollector()
            p.feed(content)
        except Exception as e:
            out.append((f"{fname}:parse-error", fname, f"sken selhal ({e})"))
            continue
        for src in sorted(set(p.srcs)):
            if src.startswith(("http://", "https://", "//", "data:")) or "{" in src or "$" in src:
                continue
            full = os.path.join(WEBAPP_DIR, src.lstrip("/"))
            if not os.path.isfile(full):
                out.append((f"{fname}:{src}", src, f"<img src=\"{src}\"> v {fname} - soubor na disku neexistuje"))
    return out


_ONCLICK_RE = re.compile(r'''\bonclick\s*=\s*["']\s*(?:return\s+)?([A-Za-z_]\w*)\s*\(''')
_FN_EXISTS_RE_TMPL = r'\bfunction\s+{name}\s*\(|\b{name}\s*=\s*function\s*\(|\b(?:const|let|var)\s+{name}\s*='


def check_dangling_onclick_function(cur):
    # onclick= se po splitu vyskytuje i v HTML sablonach generovanych
    # UVNITR .js modulu, a cilova funkce casto zije v JINEM modulu teze
    # stranky - proto se sbira i cili napric celym balickem.
    out = []
    ok_by_file = {}
    for html_path in HTML_FILES:
        try:
            bundle = _bundle_data(html_path)
        except Exception as e:
            fname = os.path.basename(html_path)
            out.append((f"{fname}:parse-error", fname, f"čtení selhalo ({e})"))
            continue
        defined = bundle["defined_fns"]
        for src in bundle["sources"]:
            try:
                content = _read_cached(src)
            except Exception:
                continue
            disp = _disp(src)
            for name in set(_ONCLICK_RE.findall(content)):
                key = (disp, name)
                ok_by_file[key] = ok_by_file.get(key, False) or name in defined
    for disp, name in _merge_bundle_findings(ok_by_file):
        out.append((f"{disp}:{name}", name,
                    f"onclick=\"{name}(...)\" v {disp} - funkce {name} není definovaná nikde "
                    "na stránce, která tenhle soubor načítá"))
    return out


# qa_checks.py neni Flask blueprint - je to tento samotny audit nastroj a
# jeho komentare OBSAHUJI priklady route-zapisu jako TEXT (napr. u
# _ROUTE_RE vyse) - naivni regex by je bez rozliseni chytil jako kdyby
# slo o skutecnou route, proto se pri hledani DUPLICIT vynechava.
_ROUTE_SCAN_EXCLUDE_FILES = {"qa_checks.py"}


def check_duplicate_api_route(cur):
    seen = {}
    for path in API_FILES:
        fname = os.path.basename(path)
        if fname in _ROUTE_SCAN_EXCLUDE_FILES:
            continue
        content = _read_cached(path)
        for method, route in _ROUTE_RE.findall(content):
            seen.setdefault((method, route), []).append(fname)
    out = []
    for (method, route), files in seen.items():
        if len(files) > 1:
            out.append((f"{method}:{route}", route, f"{method.upper()} {route} registrováno {len(files)}× ({', '.join(files)}) - druhá definice může tiše zastínit první"))
    return out


def check_requests_no_timeout(cur):
    out = []
    for path in API_FILES:
        fname = os.path.basename(path)
        try:
            tree = ast.parse(_read_cached(path), filename=path)
        except SyntaxError as e:
            out.append((f"{fname}:syntax-error", fname, f"sken selhal ({e})"))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if (node.func.attr in ("get", "post", "put", "delete", "patch", "request")
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == "requests"):
                    if not any(kw.arg == "timeout" for kw in node.keywords):
                        out.append((f"{fname}:{node.lineno}", fname, f"requests.{node.func.attr}() na řádku {node.lineno} v {fname} bez timeout= - může viset navždy"))
    return out


def check_email_link_from_request_host(cur):
    # bot7 2026-08-11 (incident: rucni curl test primo na 127.0.0.1:8090
    # poslal Robertovi realny e-mail s nefunkcnim odkazem
    # "http://127.0.0.1:8090/..." misto verejne domeny, viz oprava v
    # scene_offers.py) - request.host_url odpovida tomu, KAM presne
    # HTTP pozadavek dorazil (pri primem volani backendu mimo nginx,
    # napr. testovaci curl na localhost, je to jen lokalni port), NE
    # verejne adrese webu. Pro odkaz v e-mailu (na rozdil od OG tagu/
    # canonical URL/sitemap, kde je request.host_url spravne - tam
    # odpovida realne prohlizecove navsteve) je potreba pevna
    # APP_BASE_URL. Kontrola hlasi kazdou funkci, ktera vola send_email
    # a soucasne pouziva request.host_url. Skutecne AST uzly (Call na
    # jmeno send_email / Attribute .host_url na jmenu request), NE
    # naivni podretezec ve zdrojovem textu funkce - ten by (overeno
    # v praxi pri prvni verzi teto kontroly) chybne matchoval i
    # KOMENTARE zminujici oboji, treba presne tenhle docstring.
    out = []
    for path in API_FILES:
        fname = os.path.basename(path)
        try:
            tree = ast.parse(_read_cached(path), filename=path)
        except SyntaxError as e:
            out.append((f"{fname}:syntax-error", fname, f"sken selhal ({e})"))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            has_send_email = False
            has_host_url = False
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "send_email":
                    has_send_email = True
                elif (isinstance(sub, ast.Attribute) and sub.attr == "host_url"
                        and isinstance(sub.value, ast.Name) and sub.value.id == "request"):
                    has_host_url = True
            if has_send_email and has_host_url:
                out.append((f"{fname}:{node.name}", fname,
                             f"{fname}::{node.name}() - odkaz/text v e-mailu postaven z request.host_url "
                             "(závisí na tom, odkud požadavek dorazil) místo pevné APP_BASE_URL"))
    return out


# bot10 2026-08-26 (audit AUDIT_OPTIMALIZACE_2026-08-26.md, schvaleno
# bot3) - primy send_email() (app.py) mimo schvaleny "pending frontu"
# vzor (WORKFLOW.md bod 16, Robert 2026-08-22: "vsechny odchozi emaily
# musi schvalit admin") obchazi admin schvaleni docela KAZDY den, i kdyz
# je to jen jedna nova funkce, co na to zapomene. Presne tahle trida
# chyby se v jednom auditu nasla NEZAVISLE 3x (remeslo.py::public_
# remeslo_offer_accept/decline, scene_offers.py 5x vc. denniho cron
# behu, fleet.py+support.py 4x) - vsechny opraveny stejny den, tahle
# kontrola ma zabranit, aby se stejny vzor priste zase priplizil zpatky
# nepovsimnute. Schvalene wrappery (SKUTECNE odesilaji, az PO schvaleni/
# rucnim kliknuti admina) jsou bilelistovane jmenne - kdyz pribude
# dalsi schvaleny wrapper, pridej ho sem.
#
# Krome skutecnych "wrapperu" (fronta/schvaleni) sem patri i uzce
# vymezene VYJIMKY z bodu 16 samotneho - funkce, ktere Robert VYSLOVNE
# schvalil jako primy send_email() BEZ fronty (viz WORKFLOW.md bod 16,
# "VYJIMKA" pod-odstavec, 2026-08-27): auth_forgot_password/
# auth_send_temp_password (reset hesla, casove/bezpecnostne kriticke -
# cekani na schvaleni admina by skodilo vic nez pomahalo). Pridavat sem
# dalsi vyjimku jen na vyslovne Robertovo schvaleni, ne podle vlastniho
# uvazeni.
_SEND_EMAIL_APPROVED_WRAPPERS = {
    ("emails.py", "send_and_log"),           # rucni odeslani (auto=False) NEBO fronta pri auto=True
    ("emails.py", "approve_pending_email"),  # admin aktivne schvaluje cekajici shop_emails radek
    ("system_emails.py", "admin_system_email_review"),  # admin aktivne schvaluje cekajici system_emails radek
    ("app.py", "auth_forgot_password"),      # VYJIMKA (Robert, 2026-08-27) - reset hesla, casove kriticke
    ("app.py", "auth_send_temp_password"),   # VYJIMKA (Robert, 2026-08-27) - docasne heslo, casove kriticke
    # DALSI VYJIMKA (Robert, 2026-09-15, "proc je to v odchozi poste a ne
    # v prichozi") - jediny prijemce je Robertova vlastni adresa
    # (SUPPLIER["email"]), interni systemova notifikace, ne odchozi
    # komunikace s tretí stranou. scene_offers.py::run_offer_expiry_
    # reminder_cli ma DVE vetve - jen ta bez customer_email (admin
    # fallback) posila primo, zakaznicka vetev zustava frontou, proto je
    # cela funkce ve whitelistu (per-radek rozliseni AST kontrola neumi).
    ("scene_offers.py", "public_offer_accept"),
    ("scene_offers.py", "run_offer_expiry_reminder_cli"),
}


def check_direct_send_email_bypass(cur):
    out = []
    for path in API_FILES:
        fname = os.path.basename(path)
        try:
            tree = ast.parse(_read_cached(path), filename=path)
        except SyntaxError as e:
            out.append((f"{fname}:syntax-error", fname, f"sken selhal ({e})"))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name == "send_email" or (fname, node.name) in _SEND_EMAIL_APPROVED_WRAPPERS:
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "send_email":
                    out.append((f"{fname}:{node.name}:{sub.lineno}", fname,
                                 f"{fname}::{node.name}() na řádku {sub.lineno} - přímé send_email() mimo "
                                 "schválenou pending-frontu (emails.send_and_log / system_emails), viz "
                                 "WORKFLOW.md bod 16"))
    return out


def check_qa_registration_incomplete(cur):
    # bot7 2026-08-11 - kontrola SEBE SAMA (kontrol v tomto souboru):
    # missing_dogus_price_coefficient byla pridana do CHECKS, ale
    # zapomenuta v CHECK_CATEGORY (commit 3d28f94), takze se v adminu
    # nikdy nezobrazila v zadne ze 2 zalozek (Doplnit/Opravit) - dohledano
    # a opraveno az o den pozdeji (commit cba4a0d). Aby se tenhle
    # konkretni bug uz neopakoval s CHECK_ADDED (pridano stejny den,
    # 2026-08-11, viz Robert: "chci aby se logovalo datum pridani
    # kazdeho noveho typu kontroly"), kontroluje se PRUNIK vsech tri
    # registru (CHECKS/CHECK_CATEGORY/CHECK_ADDED) - kazdy klic musi
    # byt ve VSECH TREM, jinak je registrace kontroly nekompletni.
    out = []
    all_keys = set(CHECKS.keys()) | set(CHECK_CATEGORY.keys()) | set(CHECK_ADDED.keys())
    for key in sorted(all_keys):
        missing_from = [
            reg_name for reg_name, reg in (
                ("CHECKS", CHECKS), ("CHECK_CATEGORY", CHECK_CATEGORY), ("CHECK_ADDED", CHECK_ADDED),
            ) if key not in reg
        ]
        if missing_from:
            out.append((f"qa_checks.py:{key}", "qa_checks.py",
                         f"kontrola '{key}' chybí v: {', '.join(missing_from)} - "
                         "v adminu se pravděpodobně vůbec nezobrazí nebo nemá datum přidání"))
    return out


def check_product_slug_not_from_name(cur):
    # bot5 2026-10-01 (Robert: "aby se prostě strojově vytvářely pěkné URL adresy pro SEO, ale ne ručně botem"):
    # adresu (slug) produktu tvori a meni JEN api/product_slug.py a ma SLEDOVAT aktualni nazev. Verejny produkt, jehoz
    # adresa neodpovida nazvu (po prejmenovani, z puvodniho importu), obsahuje interni nazev dodavatele nebo chybi, je
    # stopa po adrese psane rucne/skriptem. Oprava: tlacitko "Sjednotit adresy (SEO)" v Produktech (stara adresa se
    # sama presmeruje 301), jednotlive v karte "Prepsat adresu z nazvu".
    import product_slug  # lazy: nedostupnost modulu shodi jen tuhle kontrolu (run_checks ji odchyti)
    texty = {
        "interni": "adresa '{old}' obsahuje interní název dodavatele, který se zákazníkům ukazovat nemá",
        "nesedi": "adresa '{old}' neodpovídá aktuálnímu názvu (stará nebo psaná ručně)",
        "chybi": "veřejný produkt nemá žádnou adresu (zobrazuje se jako product.html?id=...)",
    }
    return [(p["id"], p["name"], texty[p["reason"]].format(old=p["old"]) + " - tlačítko „Sjednotit adresy (SEO)“ v Produktech")
            for p in product_slug.proposals(cur)]


def check_board_price_not_per_m2(cur):
    # bot5 2026-10-01 (Robert 2026-08-07: "u deskovych materialu se cena zadava za 1m2", znovu 2026-10-01: "musi se
    # sjednotit pouzivani za 1m2"): cena desky se uklada ZA 1 m² (unit='m2') a cena celé tabule se dopočítá z formátu
    # tabule (cena_desky() v products.py). Deska s jinou jednotkou (starší stav: 'ks' = cena za celou tabuli) nebo bez
    # formátu tabule je tichá past - cena se musí přepočítávat na několika místech (cena_desky, katalog scény) a při
    # záměně jednotek vyjde cena o násobky jinak (laminodeska 3671, 2026-09-30: 5 000 Kč za tabuli se četlo jako
    # 5 000 Kč/m² = 28 980 Kč za tabuli).
    cur.execute(
        "SELECT id, name, unit, board_sheet_width_mm AS w, board_sheet_height_mm AS h FROM shop_products "
        "WHERE is_board_material=1 AND is_archived=0 ORDER BY id"
    )
    out = []
    for r in cur.fetchall():
        problemy = []
        if (r["unit"] or "").strip().lower() != "m2":
            problemy.append(f"cena je uložená pro jednotku '{r['unit']}' (starší stav: za celou tabuli), ne za 1 m² - "
                            "převést v kartě tlačítkem „Převést na cenu za 1 m²“")
        if not r["w"] or not r["h"]:
            problemy.append("chybí formát tabule - cena celé tabule se nedá spočítat")
        if problemy:
            out.append((r["id"], r["name"], "; ".join(problemy)))
    return out


def check_product_duplicate_unclassified_table(cur):
    # bot5 2026-09-30 - duplikace produktu (api/product_duplicate.py) drzi registr tabulek, ktere odkazuji na
    # shop_products: COPIED_TABLES (kopiruji se) a SKIPPED_TABLES (nekopiruji se, s duvodem). Nova tabulka
    # s product_id / shop_product_id, kterou tam nikdo nezaradil, by v kopii tise chybela - nebo by se naopak
    # kopirovala data, ktera se kopirovat nemaji (osobni udaje zakazniku jako u product_markups). Tohle
    # je presne ten pripad "kod na jednom miste predpoklada neco, co jinde uz neplati".
    import product_duplicate  # lazy: nedostupnost modulu shodi jen tuhle kontrolu (run_checks ji odchyti)
    return [(f"tabulka:{t}", t,
             "tabulka odkazuje na shop_products, ale duplikace produktu o ní neví - zařadit do COPIED_TABLES "
             "(kopírovat) nebo SKIPPED_TABLES (nekopírovat, s důvodem) v api/product_duplicate.py")
            for t in product_duplicate.unclassified_reference_tables(cur)]


def check_missing_price(cur):
    cur.execute(
        "SELECT id, name FROM shop_products "
        "WHERE active=1 AND is_archived=0 AND (price_czk_placeholder IS NULL OR price_czk_placeholder<=0)"
    )
    return [(r["id"], r["name"], "cena chybí nebo je 0") for r in cur.fetchall()]


def check_missing_image(cur):
    # bot3, 2026-08-20 (nalezeno pri "Vyres co muzes" na #3539 PR10):
    # puvodni dotaz kontroloval JEN legacy shop_product_images (ta je
    # dle api/gallery_items.py hlavickoveho komentare "jen Shoptet-
    # importovane fotky, zadne admin UI pro spravu") - produkt s
    # obrazkem pridanym NEKTERYM z novejsich mechanismu (thumbnail_file
    # sloupec primo na produktu, nebo obecna content_gallery_items
    # galerie) tak vysel jako "bez obrazku", i kdyz realny obrazek ma.
    # Rozsireno o oba dalsi zdroje - false positive u PR10 (#3539) tim
    # zmizel, aniz by se cokoli falesne zapisovalo do Shoptet-only
    # tabulky jen kvuli umlceni kontroly.
    cur.execute(
        "SELECT p.id, p.name FROM shop_products p "
        "WHERE p.active=1 AND p.is_archived=0 "
        "AND NOT EXISTS (SELECT 1 FROM shop_product_images i WHERE i.product_id=p.id) "
        "AND (p.thumbnail_file IS NULL OR TRIM(p.thumbnail_file)='') "
        "AND NOT EXISTS (SELECT 1 FROM content_gallery_items g WHERE g.owner_type='product' AND g.owner_id=p.id)"
    )
    return [(r["id"], r["name"], "žádný obrázek (shop_product_images/thumbnail_file/content_gallery_items)") for r in cur.fetchall()]


def check_missing_description(cur):
    cur.execute(
        "SELECT id, name FROM shop_products WHERE active=1 AND is_archived=0 "
        "AND (description IS NULL OR TRIM(description)='') "
        "AND (short_description IS NULL OR TRIM(short_description)='')"
    )
    return [(r["id"], r["name"], "chybí description i short_description") for r in cur.fetchall()]


def check_board_missing_material_key(cur):
    cur.execute(
        "SELECT id, name FROM shop_products "
        "WHERE active=1 AND is_archived=0 AND is_board_material=1 "
        "AND (cutting_material_key IS NULL OR cutting_material_key='')"
    )
    return [(r["id"], r["name"], "deska bez cutting_material_key - nejde přidat do košíku s přířezem") for r in cur.fetchall()]


def check_profile_wrong_length_claim(cur):
    # Zobecneni bugu z 2026-08-09: popis tvrdi jinou "standardni delku
    # tyce", nez je skutecna prodejni konvence webu (3000 mm / 1 ks).
    # Regex zachyti "délka tyče <cislo> mm" nezavisle na presnem zneni
    # (kdyby se sablona popisu casem zmenila).
    cur.execute(
        "SELECT id, name, description FROM shop_products "
        "WHERE active=1 AND is_archived=0 AND is_profile_material=1 AND description IS NOT NULL"
    )
    out = []
    for r in cur.fetchall():
        m = re.search(r'délka tyče\s*(\d+)\s*mm', r["description"], re.IGNORECASE)
        if m and m.group(1) != "3000":
            out.append((r["id"], r["name"], f"popis tvrdí délku {m.group(1)} mm, web prodává po 3000 mm"))
    return out


def check_orphaned_cfg_dily_ref(cur):
    cur.execute(
        "SELECT p.id, p.name, p.cfg_dily_id FROM shop_products p "
        "WHERE p.active=1 AND p.is_archived=0 AND p.cfg_dily_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM cfg_dily d WHERE d.id=p.cfg_dily_id)"
    )
    return [(r["id"], r["name"], f"cfg_dily_id='{r['cfg_dily_id']}' neexistuje v cfg_dily") for r in cur.fetchall()]


def check_missing_glb_file(cur):
    cur.execute("SELECT id, name, glb_file FROM cfg_dily WHERE visible_in_scene=1 AND glb_file IS NOT NULL")
    out = []
    for r in cur.fetchall():
        path = os.path.join(KATALOG_GLB_DIR, r["glb_file"])
        if not os.path.isfile(path):
            out.append((r["id"], r["name"], f"glb_file '{r['glb_file']}' chybí na disku ({path})"))
    return out


def check_duplicate_sku(cur):
    cur.execute(
        "SELECT sku, GROUP_CONCAT(id) ids, GROUP_CONCAT(name SEPARATOR ' | ') names, COUNT(*) c "
        "FROM shop_products WHERE active=1 AND is_archived=0 AND sku IS NOT NULL AND sku<>'' "
        "GROUP BY sku HAVING c>1"
    )
    return [(r["ids"], r["names"], f"SKU '{r['sku']}' sdílí {r['c']} aktivních produktů") for r in cur.fetchall()]


def check_order_payment_received_mismatch(cur):
    """bot5, 2026-09-29 (Robert primo, OBJ-2026-00001: "vcera jsem prijal
    platbu celych 12tisic... dnes je napsáno jen částečná uharada" ->
    "rucni opravy nas ale nezachrani, potrebujeme mit plne autonomni
    system bez zasahu botu") - stejna trida bugu jako skutecny nalez:
    shop_orders.payment_received_total_czk se VSUDE, kde se pouziva
    (admin_documents_list payment_summary, already_fully_paid guard,
    objednavky-doklady.js badge), porovnava PRIMO proti total_czk
    (GROSS, vc. DPH) - musi tedy byt taky GROSS. Kontrola porovnava
    ulozenou hodnotu se souctem SKUTECNE vystavenych VDD (shop_documents
    total_with_vat_czk, autoritativni GROSS zdroj) - rozdil nad 0.5 Kc
    znamena bud NET misto GROSS (presne puvodni bug, viz api/bank_
    statements.py::_create_auto_payment_tax_document a api/documents.py::
    admin_documents_mark_payment_received), chybejici/duplicitni VDD,
    nebo rucni zasah primo v DB."""
    cur.execute(
        "SELECT o.id, o.order_number, o.payment_received_total_czk, "
        "       COALESCE(SUM(d.total_with_vat_czk), 0) AS vdd_sum "
        "FROM shop_orders o "
        "LEFT JOIN shop_documents d ON d.order_id = o.id AND d.document_type='payment_tax_document' "
        "WHERE o.payment_received_total_czk IS NOT NULL AND o.payment_received_total_czk > 0 "
        "GROUP BY o.id, o.order_number, o.payment_received_total_czk "
        "HAVING ABS(o.payment_received_total_czk - vdd_sum) > 0.5"
    )
    return [
        (r["id"], r["order_number"],
         f"payment_received_total_czk ({r['payment_received_total_czk']} Kč) neodpovídá součtu "
         f"vystavených VDD ({r['vdd_sum']} Kč) - měly by se rovnat (obojí GROSS, vč. DPH).")
        for r in cur.fetchall()
    ]


def check_zero_weight_profile(cur):
    # Vaha je vstup do kalkulace hmotnosti sestavy ve scene.html
    # (weight_kg_total, viz scene.html) - chybejici/nulova vaha u
    # profilu s hotovym 3D modelem by tise pocitala 0 kg.
    cur.execute(
        "SELECT p.id, p.name FROM shop_products p JOIN cfg_dily d ON d.id=p.cfg_dily_id "
        "WHERE p.active=1 AND p.is_archived=0 AND p.is_profile_material=1 "
        "AND d.visible_in_scene=1 AND (d.weight_kg_approx IS NULL OR d.weight_kg_approx<=0)"
    )
    return [(r["id"], r["name"], "profil v 3D scéně s nulovou/chybějící hmotností (cfg_dily.weight_kg_approx)") for r in cur.fetchall()]


def check_corner_side_missing_geo_faces(cur):
    # bot8, 2026-08-17 (WORKFLOW.md bod 11 "SKU, ne nazvy" + rozek/product_3158
    # T-spoj mezera): u prislusenstvi s attach_mode "corner_side"/"parallel_side"
    # (uhelniky/rozky/spojovaci desky napojovane bokem na 2 profily) bez
    # ulozenych geo_faces_json muze automaticke napojeni (uhelnikAutPlaceOne,
    # Place All) vybrat mene presny kandidatni bod na dilu misto spravneho -
    # projevi se jako viditelna mezera jen na JEDNE strane T-spoje (potvrzeno
    # naziva na product_3158). Stejne podbarveni ve webapp/scene.html
    # (partNeedsGeoFacesReview, zluty highlight v Katalogu (obrazky)) - tahle
    # kontrola je jen druhy (admin Dashboard) pohled na tutéž frontu.
    #
    # OPRAVA (bot8, 2026-08-18, Robert "nic co se naucis se neuklada
    # spravnym zpusobem na spravnem miste"): attach_pose (🎯 Ulozit pozici /
    # Auto-nauč, MA PREDNOST pred geo_faces v runCornerSideAut) je STEJNE
    # platne "hotovo" jako geo_faces - puvodni SQL kontrolovalo jen
    # geo_faces_json, takze vsech 43 dilu, u kterych se 2026-08-18 hromadne
    # dopocitalo+ulozilo attach_pose (viz AGENTS_LOG), by se dal hlasilo
    # jako "chybi", presne ten dojem "proste to zapomenes".
    cur.execute(
        "SELECT id, name, sku FROM shop_products WHERE active=1 AND is_archived=0 "
        "AND attach_mode IN ('corner_side','parallel_side') "
        "AND (geo_faces_json IS NULL OR geo_faces_json='' OR geo_faces_json='[]') "
        "AND (attach_pose IS NULL OR attach_pose='')"
    )
    return [(r["id"], r["name"], f"SKU {r['sku']} - chybí geo_faces_json i attach_pose (✨ Rozpoznat plochy podle geometrie NEBO 🎯 Uložit pozici v panelu 🎓 Naučit napojení)") for r in cur.fetchall()]


def check_missing_dogus_price_coefficient(cur):
    # Robert 2026-08-10 ("pokud nekde zmizi koeficient, musi se udelat
    # zapis, ale hlavne odstranit pricina" + "profily koeficient 1,
    # ostatni Dogus polozky koeficient 1,2") - kategorie s aspon jednim
    # aktivnim produktem sparovanym s Dogus (dogus_url vyplnene), ktera
    # nema dogus_price_coefficient nastaveny, znamena, ze tydenni
    # prepocet cen (scripts/2026-08-09_dogus_price_recompute.py) tuhle
    # kategorii tise preskoci (jen chybova hlaska v logu skriptu, ne
    # nikde v adminu) - admin by si toho jinak nemusel vsimnout tydny.
    # Doporucena vychozi hodnota podle typu polozek v kategorii (profil
    # = 1, ostatni Dogus polozky = 1.2) - konkretni PRICINA, proc
    # koeficient chybi/zmizel, se resi zvlast, tahle kontrola jen hlasi.
    cur.execute(
        "SELECT c.id, c.name, SUM(p.is_profile_material) AS profily, COUNT(*) AS pocet "
        "FROM content_categories c JOIN shop_products p ON p.category_id=c.id "
        "WHERE p.active=1 AND p.is_archived=0 AND p.dogus_url IS NOT NULL "
        "AND c.dogus_price_coefficient IS NULL "
        "GROUP BY c.id, c.name"
    )
    out = []
    for r in cur.fetchall():
        if r["profily"] == r["pocet"]:
            navrh = "doporučeno 1 (všechny položky jsou profily)"
        elif r["profily"] == 0:
            navrh = "doporučeno 1,2 (všechny položky jsou ostatní Dogus zboží)"
        else:
            navrh = "SMÍŠENÁ kategorie (profily i ostatní zboží) - rozhodnout ručně"
        out.append((r["id"], r["name"],
                     f"{r['pocet']} produktů spárovaných s Dogus bez koeficientu kategorie - {navrh}"))
    return out


def _brace_matched_block(text, start_open_brace_idx):
    # Vrati text od start_open_brace_idx (index znaku "{") po jeho
    # PAROVOU uzavirajici "}", pocitanim hloubky - pouzito pro vytazeni
    # cele funkce/bloku beze zavislosti na odsazeni.
    depth = 0
    for i in range(start_open_brace_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start_open_brace_idx:i + 1]
    return None


_CLASS_ATTR_RE = re.compile(r'''class=(["'])((?:(?!\1).)*)\1''')
_TEMPLATE_INTERP_RE = re.compile(r"\$\{[^}]*\}|(?<!\\)\{[^{}]*\}")
# class="${grooveBadgeClass(p.groove_family)}" (JS) / class="{groove_class}"
# kde groove_class == vysledek volani/vyrazu (Python) - jednoduchy JEDEN
# identifikator za class=, pripadne s volanim (...). Pouzito k dohledani
# "nepřímých" trid, ktere nejsou napsane primo v bloku, ale pochazi z
# pomocne funkce/promenne definovane jinde v tomtez souboru.
_INDIRECT_CLASS_REF_RE = re.compile(r'''class=["']\$?\{(\w+)''')
_QUOTED_STRING_RE = re.compile(r'''(["'`])((?:(?!\1).)*)\1''')


def _literal_class_tokens_from_string_literals(body):
    # Pouzito na TELO pomocne funkce/vyraz, ktery sklada nazev tridy
    # (napr. `return groove-badge... ? "groove-badge groove-badge-"+groove
    # : "groove-badge"`) - vytahne tokeny ze VSECH quotovanych/backtick
    # retezcu uvnitr, po odstraneni pripadnych DALSICH interpolaci.
    # Retezce, ktere nevypadaji jako CSS trida/tridy (jen pismena/cislice/
    # pomlcky/mezery), se ignoruji (napr. "⬡ Slot " nebo "mm").
    body = _TEMPLATE_INTERP_RE.sub(" ", body or "")
    tokens = set()
    for _, val in _QUOTED_STRING_RE.findall(body):
        val = val.strip()
        if val and re.fullmatch(r"[a-zA-Z][a-zA-Z0-9\- ]*", val):
            tokens.update(val.split())
    return tokens


def _resolve_indirect_class_fn(full_src, name, is_python):
    # Najde definici `name` (funkce, JS i Python, nebo prosta promenna
    # v Pythonu - viz `groove_class = f"..." if ... else "..."` v SSR
    # sablone) KDEKOLI v danem zdrojovem souboru a vrati CSS tridy, ktere
    # by mohla vratit/obsahovat - jedna uroven neprimeho odkazu (dost
    # pro znamy vzor "class=${pomocnaFunkce(...)}"/"class={promenna}",
    # nejde o obecny JS/Python interpreter).
    if is_python:
        m = re.search(r"^([ \t]*)" + re.escape(name) + r"\s*=", full_src, re.MULTILINE)
        if m:
            indent = len(m.group(1))
            rest = full_src[m.end():]
            rest_lines = rest.split("\n")
            # Prvni radek je POKRACOVANI prirazeni na stejnem radku (za
            # "=") - ma tedy vzdy prakticky nulove "odsazeni" (jen
            # mezera po "="), NE odsazeni statementu. Bez zvlastniho
            # osetreni by se hned na nem loop nize spatne zastavil a
            # vratil prazdny vysledek (nalezeno testem: `groove_class =
            # f"..." if ... else "..."` na jednom radku vracelo set()).
            body_lines = rest_lines[:1]
            for line in rest_lines[1:]:
                if line.strip() == "":
                    body_lines.append(line)
                    continue
                cur_indent = len(line) - len(line.lstrip())
                if cur_indent <= indent and line.strip():
                    break
                body_lines.append(line)
            return _literal_class_tokens_from_string_literals("\n".join(body_lines))
        m = re.search(r"def\s+" + re.escape(name) + r"\s*\([^)]*\)\s*:", full_src)
        if not m:
            return set()
        indent = len(re.match(r"[ \t]*", full_src[:m.start()].rsplit("\n", 1)[-1]).group())
        rest = full_src[m.end():]
        body_lines = []
        for line in rest.split("\n"):
            if line.strip() == "":
                body_lines.append(line)
                continue
            cur_indent = len(line) - len(line.lstrip())
            if cur_indent <= indent and line.strip():
                break
            body_lines.append(line)
        return _literal_class_tokens_from_string_literals("\n".join(body_lines))
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", full_src)
    if not m:
        return set()
    fn_body = _brace_matched_block(full_src, m.end() - 1) or ""
    return _literal_class_tokens_from_string_literals(fn_body)


def _class_tokens_in_block(block, full_src=None, is_python=False):
    # Vytahne VSECHNY literalni CSS tridy z class="..."/class='...'
    # atributu v danem bloku textu (JS template literal i Python
    # f-string pouzivaji stejnou class="..." syntaxi), VCETNE trid
    # dosazitelnych pres jednu uroven neprimeho odkazu (pomocna
    # funkce/promenna - viz _resolve_indirect_class_fn). DULEZITE
    # poradi: nejdriv se z RAW bloku vytahnou nazvy neprimych odkazu
    # (${fnName(...)}/{fnName(...)}), AZ POTOM se cely blok interpolacne
    # vycisti pro hledani primych literalnich class="..." - jinak by
    # cisteni znicilo informaci o tom, co bylo uvnitr `${...}` (napr.
    # `${hoverMode ? " cp-hover-mode" : ""}` obsahuje uvozovky UVNITR
    # interpolace, ktere by naivni "class="..."" regex spatne vzal za
    # konec atributu - nalezeno pri prvnim testu teto kontroly).
    indirect_names = set(_INDIRECT_CLASS_REF_RE.findall(block or ""))
    cleaned_block = _TEMPLATE_INTERP_RE.sub(" ", block or "")
    tokens = set()
    for _, raw in _CLASS_ATTR_RE.findall(cleaned_block):
        tokens.update(t for t in raw.split() if t)
    if full_src:
        for name in indirect_names:
            tokens.update(_resolve_indirect_class_fn(full_src, name, is_python))
    return tokens


def check_ssr_client_render_drift(cur):
    # Robert 2026-08-10 ("ty ikony Slotu se nacitaji opozdene jakoby
    # dodatecne po nacteni stranky") - skutecna prescina: SSR sablona
    # karty produktu (api/app.py::_category_page_response) MA byt 1:1
    # se strukturou webapp/category.html::renderProducts() (viz komentar
    # tam z 2026-08-09, "škaredý rozhoz na pul sekundy" - uz jednou
    # opraveny presne tenhle bug u ceny/obrazku), jinak SSR HTML chybi
    # prvek, ktery se objevi az po async fetchi klientskeho JS - presne
    # "opozdene nacitani odznaku" pri zavadeni Slot odznaku, kdy trida
    # groove-badge pribyla jen do JS, ne do SSR. Tahle kontrola srovna
    # mnozinu literalnich CSS trid pouzitych v obou blocich a nahlasi
    # asymetrii (trida jen na jedne strane) jako signal moznaho drift.
    #
    # Zamerne UZKY scope (jen tenhle jeden znamy par funkci s vyslovne
    # dokumentovanym pravidlem "musi zustat synchronni"), ne obecna
    # kontrola pres cely web - jine stranky/sekce takove pravidlo nemaji
    # (a spousta z nich je cistě klientska bez SSR ekvivalentu vubec).
    out = []
    cat_path = os.path.join(WEBAPP_DIR, "category.html")
    app_path = os.path.join(API_DIR, "storefront_pages.py")
    if not (os.path.exists(cat_path) and os.path.exists(app_path)):
        return out
    try:
        with open(cat_path, encoding="utf-8") as f:
            cat_src = f.read()
        with open(app_path, encoding="utf-8") as f:
            app_src = f.read()
    except Exception as e:
        return [("ssr_drift:read-error", "category.html/app.py", f"sken selhal ({e})")]

    m = re.search(r"function\s+renderProducts\s*\([^)]*\)\s*\{", cat_src)
    js_block = _brace_matched_block(cat_src, m.end() - 1) if m else None

    py_start = app_src.find('cards_html = ""')
    py_end = app_src.find("body_replacements['<div class=\"cat-products\"", py_start) if py_start != -1 else -1
    py_block = app_src[py_start:py_end] if py_start != -1 and py_end != -1 else None

    if not js_block or not py_block:
        out.append(("ssr_drift:anchor-missing", "category.html/app.py",
                     "renderProducts()/SSR karta - jeden z ukotvovacich textu (function renderProducts / "
                     "cards_html = \"\") nebyl nalezen, kontrola nemohla porovnat obsah - prekontroluj rucne, "
                     "jestli se nezmenilo jmeno funkce/promenne"))
        return out

    js_tokens = _class_tokens_in_block(js_block, full_src=cat_src, is_python=False)
    py_tokens = _class_tokens_in_block(py_block, full_src=app_src, is_python=True)
    only_js = sorted(js_tokens - py_tokens)
    only_py = sorted(py_tokens - js_tokens)
    for cls in only_js:
        out.append((f"ssr_drift:js-only:{cls}", cls,
                     f"třída '{cls}' se používá v category.html::renderProducts(), ale chybí v SSR šabloně "
                     "(api/app.py::_category_page_response) - prvek se zákazníkovi/robotovi objeví až po "
                     "async JS re-renderu, ne hned při načtení stránky"))
    for cls in only_py:
        out.append((f"ssr_drift:py-only:{cls}", cls,
                     f"třída '{cls}' se používá v SSR šabloně (api/app.py::_category_page_response), ale "
                     "chybí v category.html::renderProducts() - po JS re-renderu prvek zmizí/se přepíše bez něj"))
    return out


# Robert 2026-08-10 ("proc si tam neposlal vsechny kdyz je to pravidlo") -
# druha kontrola ze stejneho kola nalezenych chyb (viz zaznam "toast
# notifikace misto alert()"). Blokujici nativni alert() na zakaznickych
# strankach e-shopu byl nahrazen neblokujicim #toastStack/showToast() v
# product.html + nabidka-online.html - tahle kontrola hlida, aby se
# vzor nevratil (novy kod/jiny bot omylem znovu pouzije alert()).
#
# ZAMERNE UZKY rozsah - jen zakaznicke e-shop stranky, kde byl vzor
# VYSLOVNE opraven a nahrazen (viz SHOP_CUSTOMER_FILES nize), NE cely
# webapp/*.html:
#   - admin.html MA 78 vlastnich alert() volani, scene.html 48 - obe
#     mimo dnesni zadani (Robert resil konkretne kosik/nabidky, ne
#     cely web) a scene.html navic spada pod bot6 (role "Scena"), ne
#     bot5 ("Frontend e-shop") - hromadne prohlaseni 126 novych
#     "opravit" nalezu v cizi oblasti bez Robertova rozhodnuti by bylo
#     scope-creep, ne "poslani stejne chyby do kontrol".
#   - capture.html (1 vyskyt) je interni nastroj pro montery/ridice
#     (fotoaparat/kniha jizd), ne zakaznicka cast e-shopu - jiny UX
#     kontext, taky vynechano.
# Pokud Robert casem rozhodne rozsirit i na admin.html/scene.html,
# staci pridat jejich jmena do SHOP_CUSTOMER_FILES.
SHOP_CUSTOMER_FILES = (
    "index.html", "category.html", "product.html", "nabidka-online.html",
    "realizace.html", "login.html", "register.html", "forgot-password.html",
    "reset-password.html", "poptavka-stul.html", "blok.html",
)
_SCRIPT_BLOCK_RE = re.compile(r"<script(?:\s[^>]*)?>(.*?)</script>", re.DOTALL | re.IGNORECASE)
_JS_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_JS_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_ALERT_CALL_RE = re.compile(r"\balert\s*\(")


def check_blocking_alert_call(cur):
    out = []
    for fname in SHOP_CUSTOMER_FILES:
        path = os.path.join(WEBAPP_DIR, fname)
        if not os.path.exists(path):
            continue
        try:
            content = _read_cached(path)
        except Exception as e:
            out.append((f"{fname}:read-error", fname, f"sken selhal ({e})"))
            continue
        for script in _SCRIPT_BLOCK_RE.findall(content):
            # Komentare (// i /* */) musi zmizet PRED hledanim alert( -
            # jinak by kontrola hlasila i dokumentacni zminky typu
            # "// Toast notifikace - nahrazuje alert()" jako falesny
            # nalez (presne takove komentare dnes v product.html/
            # nabidka-online.html jsou, viz predchozi zaznam v logu).
            cleaned = _JS_BLOCK_COMMENT_RE.sub(" ", script)
            cleaned = _JS_LINE_COMMENT_RE.sub(" ", cleaned)
            for m in _ALERT_CALL_RE.finditer(cleaned):
                line_no = cleaned.count("\n", 0, m.start()) + 1
                out.append((f"{fname}:alert:{line_no}", fname,
                             f"{fname} řádek ~{line_no}: blokující alert() na zákaznické stránce e-shopu - "
                             "nahraď neblokující showToast() (#toastStack, viz product.html/nabidka-online.html)"))
    return out


# Robert 2026-08-11 - skutecny bug: pri prejmenovani "Novinky" ->
# "Hlášky" v adminu (webapp/admin.html) byl prepsan HTML atribut
# data-tab="newsitems" -> data-tab="announcementitems", ale JS
# dispatcher v initTabs() ("if (btn.dataset.tab === 'newsitems')
# loadX()") si porovnaval se STAROU hodnotou - podminka tak uz nikdy
# nebyla pravdiva a data se pri kliknuti na zalozku nikdy nenatahla
# (admin videl "Počet hlášek: 0", i kdyz polozky v DB existovaly).
# Stejny princip jako check_dangling_get_element_by_id (JS predpoklada
# neco, co uz v HTML neplati), jen pro data-tab misto id.
_DATA_TAB_ATTR_RE = re.compile(r'''data-tab=["\']([\w-]+)["\']''')
_DATASET_TAB_CMP_RE = re.compile(r'''dataset\.tab\s*===\s*["\']([\w-]+)["\']''')


def check_stale_admin_tab_reference(cur):
    out = []
    for path in HTML_FILES:
        fname = os.path.basename(path)
        try:
            _read_cached(path)
        except Exception as e:
            out.append((f"{fname}:parse-error", fname, f"čtení selhalo ({e})"))
            continue
        # data-tab= je v HTML, dataset.tab === "..." po splitu v modulu
        text = _bundle_data(path)["text"]
        tab_values = set(_DATA_TAB_ATTR_RE.findall(text))
        cmp_values = set(_DATASET_TAB_CMP_RE.findall(text))
        if not tab_values and not cmp_values:
            continue
        for stale in sorted(cmp_values - tab_values):
            out.append((f"{fname}:{stale}", stale,
                        f"{fname}: dataset.tab === '{stale}' v JS, ale žádné tlačítko nemá "
                        f"data-tab=\"{stale}\" - po přejmenování záložky zůstala tahle podmínka "
                        "nikdy pravdivá (data se při kliknutí na záložku nenačtou)"))
    return out


# Robert 2026-08-11 ("mam problem, chci smerovat na jiné weby linkem,
# v hlášce, ale před adresu se mi vkládá automaticky vandrawee.cz
# nechci") - kdyz admin v Quillu napise odkaz bez schematu (napr.
# "www.example.cz" misto "https://www.example.cz"), prohlizec ho bere
# jako RELATIVNI vuci aktualni strance ("vandrawee.cz/www.example.cz").
# Kontrola dat (ne kodu) - skenuje href="..." ve vsech rich-text
# body_html/intro_html/... sloupcich, kde admin muze pres Quill odkaz
# vlozit. Schema (http/https/mailto/tel/...) I interni/relativni
# odkazy (zacinaji "/" nebo "#") jsou v poradku, jen "bez schematu a
# bez / na zacatku" je podezrele.
_HREF_RE = re.compile(r'''href=["\']([^"']+)["\']''')
_URI_SCHEME_RE = re.compile(r'''^[a-zA-Z][a-zA-Z0-9+.\-]*:''')
RICH_TEXT_LINK_SOURCES = (
    ("homepage_blocks", "id", "title", ("body_html",)),
    ("sidebar_blocks", "id", "title", ("body_html",)),
    ("announcement_items", "id", "title", ("body_html",)),
    ("content_pages", "category_id", "title", ("intro_html", "body_html", "bottom_body_html")),
)


def check_missing_link_protocol(cur):
    out = []
    for table, id_col, name_col, html_cols in RICH_TEXT_LINK_SOURCES:
        cols = ", ".join([id_col, name_col] + list(html_cols))
        try:
            cur.execute(f"SELECT {cols} FROM {table}")
        except Exception:
            continue  # tabulka/sloupec v teto instanci (jeste) neexistuje
        for row in cur.fetchall():
            for col in html_cols:
                html_val = row.get(col) or ""
                for href in set(_HREF_RE.findall(html_val)):
                    if _URI_SCHEME_RE.match(href) or href.startswith(("/", "#")):
                        continue
                    out.append((
                        f"{table}:{row[id_col]}:{col}:{href}",
                        row.get(name_col) or f"{table}#{row[id_col]}",
                        f"{table}.{col} (id={row[id_col]}) - href=\"{href}\" nemá schéma (http/https/…) "
                        f"ani nezačíná / - prohlížeč to vezme jako relativní odkaz vůči aktuální stránce",
                    ))
    return out


# Robert 2026-08-11 ("kdyz kliknu na dlazdici jakoukoli, než se otevre
# detail, problikne levé menu jakoze zmizi, nebo se zabali a zase
# roztáhne") - stranky se sidebarem MAJI v surovem HTML prazdny
# placeholder `<div class="cat-tree" id="catTree"></div>` (viz
# webapp/*.html), ktery ocekava SSR vyplneni (viz
# api/app.py::_add_category_tree_ssr) - jinak sidebar pri kazdem
# nacteni stranky nejdriv problikne prazdny/nizky, nez ho JS
# fetch("/api/categories") dorenderuje na plnou vysku. Tenhle presny
# bug byl 2x nezavisle znovuobjeven (blok.html/panel a pak i
# product.html), pokazde protoze nova route mela vlastni kopii teto
# logiky (nebo zadnou). Kontrola: pro kazdou HTML sablonu s tímto
# prazdnym placeholderem najdi VSECHNY Flask route funkce, ktere ji
# renderuji pres _render_og_page(...), a over, ze kazda z nich volá
# _add_category_tree_ssr(...).
_RENDER_OG_PAGE_CALL_RE = re.compile(r'''_render_og_page\(\s*["'](\w[\w.\-]*\.html)["']''')
_EMPTY_CAT_TREE_PLACEHOLDER = '<div class="cat-tree" id="catTree"></div>'


def check_ssr_sidebar_tree_missing(cur):
    templates_with_empty_tree = set()
    for path in HTML_FILES:
        fname = os.path.basename(path)
        try:
            content = _read_cached(path)
        except Exception:
            continue
        if _EMPTY_CAT_TREE_PLACEHOLDER in content:
            templates_with_empty_tree.add(fname)
    if not templates_with_empty_tree:
        return []

    out = []
    for path in API_FILES:
        fname = os.path.basename(path)
        try:
            source = _read_cached(path)
            tree = ast.parse(source, filename=path)
        except (SyntaxError, OSError):
            continue
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            end_line = getattr(node, "end_lineno", node.lineno)
            body_src = "\n".join(lines[node.lineno - 1:end_line])
            rendered = set(_RENDER_OG_PAGE_CALL_RE.findall(body_src)) & templates_with_empty_tree
            if not rendered:
                continue
            has_ssr_fill = "_add_category_tree_ssr(" in body_src or 'id="catTree" data-ssr="1"' in body_src
            if not has_ssr_fill:
                for tmpl in sorted(rendered):
                    out.append((
                        f"{fname}:{node.name}:{tmpl}",
                        node.name,
                        f"{node.name}() v {fname} renderuje {tmpl} (má prázdný #catTree v HTML), ale nevolá "
                        "_add_category_tree_ssr() - levé menu se při navigaci nejdřív vykreslí prázdné "
                        "a pak 'problikne'/vyskočí na plnou výšku",
                    ))
    return out


# Robert 2026-08-11 ("na mobilu se prakticky nic nezobrazuje" - stranka
# byla na iPhonu uplne prazdna) - kontrola vznikla z realneho bugu, ktery
# se NEDAL odhalit staticky ani curl-em: SSR HTML bylo cele v poradku,
# jen bylo vizualne stlacene mimo obrazovku. Zmereno primo na Robertove
# telefonu (viewport 390px): .left-column w=390 h=0, .main-content w=0
# h=2146 x=390.
#
# Vzorec bugu: .layout je flex RADEK, .left-column v mobilnim
# breakpointu dostane width:100% a .main-content ma flex:1 (tj.
# flex-basis:0%). Prvek s nulovym flex-basis se do radku vzdy "vejde",
# takze se NIKDY nezalomi na dalsi radek - jen dostane 0px sirky, kdyz
# si sourozenec narokuje celych 100%. Pridani flex-wrap:wrap proto
# nepomuze (prvni pokus o opravu, commit 26a938f, presne na tohle
# naletel) - zalamovani se ridi flex-basis, ne obsahem. Jedina spolehliva
# oprava je v mobilnim breakpointu z .layout flex uplne zrusit
# (display:block), pripadne dat .main-content nenulovy flex-basis.
_MOBILE_MEDIA_RE = re.compile(r"@media\s*\(max-width:\s*(\d+)px\s*\)\s*\{", re.I)
_LEFT_COL_FULL_WIDTH_RE = re.compile(r"\.left-column\s*\{[^}]*\bwidth\s*:\s*100%", re.I)
_LAYOUT_RULE_RE = re.compile(r"\.layout\s*\{([^}]*)\}", re.I)
_MAIN_CONTENT_FLEX1_RE = re.compile(r"\.main-content\s*\{[^}]*\bflex\s*:\s*1\b", re.I)


def _css_block_at(content, open_brace_idx):
    """Vrati telo { ... } bloku zacinajiciho na dane '{' (hlida vnorene bloky)."""
    depth = 0
    for i in range(open_brace_idx, len(content)):
        ch = content[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return content[open_brace_idx + 1:i]
    return ""


def check_mobile_layout_zero_width(cur):
    out = []
    for path in HTML_FILES:
        fname = os.path.basename(path)
        try:
            content = _read_cached(path)
        except Exception:
            continue
        # Bug se tyka jen stranek se sidebarem vedle obsahu (.layout flex radek).
        if not _MAIN_CONTENT_FLEX1_RE.search(content):
            continue
        for m in _MOBILE_MEDIA_RE.finditer(content):
            block = _css_block_at(content, m.end() - 1)
            if not _LEFT_COL_FULL_WIDTH_RE.search(block):
                continue
            layout = _LAYOUT_RULE_RE.search(block)
            layout_decls = layout.group(1) if layout else ""
            # Bezpecne je jen uplne zruseni flexu na .layout v tomto breakpointu.
            if re.search(r"\bdisplay\s*:\s*(block|grid)\b", layout_decls, re.I):
                continue
            line_no = content[:m.start()].count("\n") + 1
            out.append((
                f"{fname}:{m.start()}",
                fname,
                f"{fname}:{line_no} - v @media (max-width:{m.group(1)}px) má .left-column width:100%, "
                "ale .layout tam zůstává flex řádek a .main-content má flex:1 (flex-basis:0%) - "
                "obsah stránky se na mobilu stlačí na 0px šířky a zmizí za pravý okraj "
                "(vypadá to jako úplně prázdná stránka). flex-wrap:wrap NEPOMŮŽE - "
                "je potřeba .layout { display:block; } v tomto breakpointu.",
            ))
    return out


def check_remeslo_backlink_domain_self_reference(cur):
    """Vizitky remeslniku (/r/<slug>) a SEO backlink v jejich paticce
    nesmi sdilet stejnou domenu.

    Zdroj chyby (bot15, 2026-08-19): v api/remeslo.py puvodne JEDNA
    konstanta (PUBLIC_PROFILE_DOMAIN) slouzila obojimu - kde vizitka
    bydli I kam miri sponzorska paticka. Odkaz tak ukazoval sam na sebe
    (vandrawee.cz -> vandrawee.cz) = interni odkaz BEZ SEO hodnoty,
    presne to, kvuli cemu paticka existuje. Opraveno rozdelenim na dve
    konstanty (PUBLIC_PROFILE_DOMAIN=remeslnik.pro vs.
    PUBLIC_PROFILE_BACKLINK_DOMAIN=vandrawee.cz) - tahle kontrola hlida,
    aby je nikdo znovu nesjednotil ("uklidem" kodu, env promennymi
    REMESLO_PUBLIC_DOMAIN/REMESLO_BACKLINK_DOMAIN nastavenymi na stejnou
    hodnotu, nebo smazanim jedne z konstant)."""
    out = []
    path = os.path.join(os.path.dirname(__file__), "remeslo.py")
    try:
        src = open(path, encoding="utf-8").read()
    except OSError:
        return out

    def _effective(const_name, env_name):
        m = re.search(
            const_name + r'\s*=\s*os\.environ\.get\(\s*"' + env_name
            + r'"\s*,\s*"([^"]+)"', src, re.S,
        )
        default = m.group(1) if m else None
        return os.environ.get(env_name, default)

    host = _effective("PUBLIC_PROFILE_DOMAIN", "REMESLO_PUBLIC_DOMAIN")
    back = _effective(
        "PUBLIC_PROFILE_BACKLINK_DOMAIN", "REMESLO_BACKLINK_DOMAIN"
    )
    if not host or not back:
        out.append((
            "remeslo_backlink_constants",
            "api/remeslo.py",
            "Nenalezena definice PUBLIC_PROFILE_DOMAIN nebo "
            "PUBLIC_PROFILE_BACKLINK_DOMAIN (os.environ.get vzor) - obe "
            "konstanty MUSI existovat oddelene (host vizitek vs. cil "
            "SEO backlinku v paticce), viz komentar u definice.",
        ))
    elif host == back:
        out.append((
            "remeslo_backlink_self_reference",
            "api/remeslo.py",
            f"Host vizitek a cil paticky jsou stejna domena ('{host}') - "
            "backlink ukazuje sam na sebe a nema SEO hodnotu. Rozdel "
            "PUBLIC_PROFILE_DOMAIN a PUBLIC_PROFILE_BACKLINK_DOMAIN "
            "(vc. pripadnych env REMESLO_PUBLIC_DOMAIN/"
            "REMESLO_BACKLINK_DOMAIN).",
        ))
    return out


_FLUNG_TOUCH_MM = 50.0     # dily blize nez tohle se "dotykaji" (jedna souvisla skupina)
_FLUNG_AWAY_MM = 300.0     # skupina dal nez tohle od hlavni skupiny = odletla
_FLUNG_SMALL_SHARE = 0.2   # ... a zaroven mala (nejvys 20 % hlavni skupiny)


def _glb_local_bbox(fname, cache):
    """(min, max) lokalni obalky GLB z accessoru POSITION vsech primitiv,
    nebo None (chybi / nejde cist / ma transformace uzlu - tam by obalka
    nesedela na to, co kresli scena)."""
    if fname in cache:
        return cache[fname]
    res = None
    path = os.path.join(KATALOG_GLB_DIR, fname.split("?")[0].replace("katalog/", "", 1))
    try:
        with open(path, "rb") as f:
            head = f.read(20)
            if head[:4] == b"glTF":
                g = json.loads(f.read(struct.unpack("<I", head[12:16])[0]))
                if not any(n.get(k) is not None for n in g.get("nodes") or []
                           for k in ("translation", "rotation", "scale", "matrix")):
                    lo, hi = [math.inf] * 3, [-math.inf] * 3
                    for m in g.get("meshes") or []:
                        for p in m.get("primitives") or []:
                            a = g["accessors"][p["attributes"]["POSITION"]]
                            lo = [min(lo[k], a["min"][k]) for k in range(3)]
                            hi = [max(hi[k], a["max"][k]) for k in range(3)]
                    if lo[0] != math.inf:
                        res = (lo, hi)
    except (OSError, ValueError, KeyError, IndexError, TypeError, struct.error):
        res = None
    cache[fname] = res
    return res


def _quat_to_matrix(q):
    x, y, z, w = (float(v) for v in q)
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def _flung_parts(parts, glb_files, cache):
    """[(index dilu, part_id, vzdalenost_mm)] dilu, ktere lezi v male
    souvisle skupine daleko od hlavni skupiny dilu (svetove obalky jako
    scena: svet = position + R*(scale*v_glb))."""
    boxes = []
    for k, p in enumerate(parts):
        fname = glb_files.get(p.get("part_id"))
        bb = _glb_local_bbox(fname, cache) if fname else None
        if not bb:
            continue
        try:
            m = _quat_to_matrix(p.get("quaternion") or [0, 0, 0, 1])
            s = [float(v) for v in (p.get("scale") or [1, 1, 1])]
            t = [float(v) for v in (p.get("position") or [0, 0, 0])]
        except (TypeError, ValueError):
            continue
        lo, hi = [math.inf] * 3, [-math.inf] * 3
        for cx in (bb[0][0], bb[1][0]):
            for cy in (bb[0][1], bb[1][1]):
                for cz in (bb[0][2], bb[1][2]):
                    v = (cx * s[0], cy * s[1], cz * s[2])
                    for r in range(3):
                        w = t[r] + m[r][0] * v[0] + m[r][1] * v[1] + m[r][2] * v[2]
                        lo[r], hi[r] = min(lo[r], w), max(hi[r], w)
        boxes.append((k, lo, hi))
    n = len(boxes)
    if n < 3:
        return []

    def gap(a, b):
        return math.sqrt(sum(max(0.0, a[1][r] - b[2][r], b[1][r] - a[2][r]) ** 2 for r in range(3)))
    parent = list(range(n))

    def root(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a in range(n):
        for b in range(a + 1, n):
            if root(a) != root(b) and gap(boxes[a], boxes[b]) <= _FLUNG_TOUCH_MM:
                parent[root(a)] = root(b)
    groups = {}
    for a in range(n):
        groups.setdefault(root(a), []).append(a)
    main = max(groups.values(), key=len)
    out = []
    for members in groups.values():
        if members is main or len(members) > _FLUNG_SMALL_SHARE * len(main):
            continue
        dist = min(gap(boxes[a], boxes[b]) for a in members for b in main)
        if dist > _FLUNG_AWAY_MM:
            out.extend((boxes[a][0], parts[boxes[a][0]].get("part_id"), round(dist)) for a in members)
    return out


def check_flung_shape_part(cur):
    """Dil vlastniho tvaru / sestavy "odletel" od zbytku - lezi v male
    skupine (nejvys 20 % hlavni skupiny) dal nez 300 mm od hlavni souvisle
    skupiny dilu.

    Zdroj chyby (bot8, 2026-10-01): univerzalni import FBX (build_shape)
    predpokladal u existujicich karet GLB vycentrovane a v osach sceny;
    karty nahrane pres admin FBX lezi na souradnicich z Rhina, takze po
    "Sestavit tvar" dily odletely o 1-3 m (Robertuv stul, tvary #573/#574).
    Opraveno v importu (commit 9ee23b1c), tahle kontrola hlida tridu chyby
    obecne: jakykoli generator/import, ktery spatne umisti dil, vyrobi
    osamely dil daleko od zbytku. Skupiny srovnatelne velikosti (napr.
    vzorkovnice 4 dvirek vedle sebe, #560) se nehlasi - to je zamer."""
    glb_files = {}
    cur.execute("SELECT id, glb_file FROM cfg_dily WHERE glb_file IS NOT NULL")
    glb_files.update({r["id"]: r["glb_file"] for r in cur.fetchall()})
    cur.execute("SELECT id, glb_file FROM shop_products WHERE glb_file IS NOT NULL")
    glb_files.update({f"product_{r['id']}": r["glb_file"] for r in cur.fetchall()})
    cache = {}
    out = []
    for table, name_col in (("custom_shapes", "name"), ("product_assemblies", "NULL")):
        cur.execute(f"SELECT id, {name_col} AS name, data FROM {table}")
        for r in cur.fetchall():
            try:
                data = json.loads(r["data"]) if isinstance(r["data"], str) else (r["data"] or {})
            except ValueError:
                continue
            flung = _flung_parts(data.get("parts") or [], glb_files, cache)
            if not flung:
                continue
            ukazka = ", ".join(f"#{i} {pid} ({d} mm)" for i, pid, d in flung[:6])
            out.append((r["id"], f"{table} #{r['id']}" + (f" {r['name']}" if r.get("name") else ""),
                        f"{len(flung)} dílů leží daleko od zbytku tvaru: {ukazka}"
                        + (" …" if len(flung) > 6 else "")
                        + " - nejspíš špatně umístěné (import/generátor), zkontroluj ve scéně."))
    return out


_JOINT_EPS_FACE_MM = 1.5     # stejne jako dimension_match_fbx.EPS_FACE_MM (cista CAD data)
_JOINT_EPS_OVERLAP_MM = 0.5  # prekryv na zbylych osach >= mensi rozmer - 0,5 mm (scene.html autoRegisterTouchedProfileJoints)


def _joint_definition_touch(a, b):
    """Definice spoje (Robert 2026-08-31, PRAVIDLA_SPOJU.md): na JEDNE ose se
    plochy dotykaji a na zbylych dvou prekryv pokryva CELOU mensi plochu - dotyk
    hranou/rohem ani castecne kryte celo spoj NENI. a, b = (lo[3], hi[3])."""
    for ax in range(3):
        if not (abs(a[1][ax] - b[0][ax]) < _JOINT_EPS_FACE_MM or abs(a[0][ax] - b[1][ax]) < _JOINT_EPS_FACE_MM):
            continue
        ok = True
        for o in range(3):
            if o == ax:
                continue
            lo, hi = max(a[0][o], b[0][o]), min(a[1][o], b[1][o])
            min_size = min(a[1][o] - a[0][o], b[1][o] - b[0][o])
            if hi - lo < min_size - _JOINT_EPS_OVERLAP_MM:
                ok = False
                break
        if ok:
            return True
    return False


def _lic_peers_profile_glb(cur):
    """{cfg_dily id: glb_file} jen hlinikovych profilu z katalogu (nazev "Profil...",
    delka >= 900 mm) - jen ty se u lic_peers kontroluji."""
    cur.execute("SELECT id, name, dim_x_mm, dim_y_mm, dim_z_mm, glb_file FROM cfg_dily WHERE glb_file IS NOT NULL")
    out = {}
    for r in cur.fetchall():
        dims = [r["dim_x_mm"], r["dim_y_mm"], r["dim_z_mm"]]
        if any(d is None for d in dims) or max(float(d) for d in dims) < 900:
            continue
        if str(r["name"] or "").lower().startswith("profil"):
            out[r["id"]] = r["glb_file"]
    return out


def lic_peers_bad_pairs(parts, profil_glb, cache):
    """(vsechny pary lic_peers mezi profily, pary NESPLNUJICI definici spoje) -
    obe jako serazene seznamy (i, j), i < j. Razitka/kontrolni pomucky se neberou.
    Sdileno kontrolou nize a opravnym skriptem scripts/2026-10-02_bot8_lic_peers_
    definice_spoje.py (jedna logika)."""
    boxes = {}
    for k, p in enumerate(parts):
        fname = profil_glb.get(p.get("part_id"))
        if not fname or str(p.get("role") or "").startswith(("logo-ochrana", "kontrolni-pomucka")):
            continue
        bb = _glb_local_bbox(fname, cache)
        if not bb:
            continue
        try:
            m = _quat_to_matrix(p.get("quaternion") or [0, 0, 0, 1])
            sc = [float(v) for v in (p.get("scale") or [1, 1, 1])]
            t = [float(v) for v in (p.get("position") or [0, 0, 0])]
        except (TypeError, ValueError):
            continue
        lo, hi = [math.inf] * 3, [-math.inf] * 3
        for cx in (bb[0][0], bb[1][0]):
            for cy in (bb[0][1], bb[1][1]):
                for cz in (bb[0][2], bb[1][2]):
                    v = (cx * sc[0], cy * sc[1], cz * sc[2])
                    for q in range(3):
                        w = t[q] + m[q][0] * v[0] + m[q][1] * v[1] + m[q][2] * v[2]
                        lo[q], hi[q] = min(lo[q], w), max(hi[q], w)
        boxes[k] = (lo, hi)
    pairs = set()
    for i in boxes:
        for j in parts[i].get("lic_peers") or []:
            if j in boxes and j != i:
                pairs.add((min(i, j), max(i, j)))
    bad = sorted(pr for pr in pairs if not _joint_definition_touch(boxes[pr[0]], boxes[pr[1]]))
    return sorted(pairs), bad


def check_lic_peers_not_a_joint(cur):
    """Dvojice profilu ulozena v lic_peers (spoj), ktera NESPLNUJE definici
    spoje - dotyk jen hranou/rohem, castecne kryte celo nebo se profily vubec
    nedotykaji.

    Zdroj chyby (bot8, 2026-10-02, nalez bot10): stul #577 hlasil po nacteni
    32 spoju, geometrie 26 (+660 Kc v cene), stejne #572, "Regal 40A01 Doblo"
    #524 (53 vs 35). scene.html insertCustomShape zapocita KAZDY par z
    lic_peers po nacteni do spoju bez kontroly geometrie; dimension_match_fbx.
    _profiles_touch() pritom bral dotyk hranou (prekryv >= -0,5 mm) - opraveno
    tamtez, tahle kontrola hlida STARA data a jine zdroje (ruzne zastarale
    indexy po uprave sestavy). Jen hlinikove profily z katalogu (cfg_dily,
    nazev "Profil...", delka >= 900 mm); razitka/kontrolni pomucky se neberou."""
    profil_glb = _lic_peers_profile_glb(cur)
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='joint_price_czk'")
    row = cur.fetchone()
    try:
        joint_price = float(row["setting_value"]) if row else 0.0
    except (TypeError, ValueError):
        joint_price = 0.0
    cache = {}
    out = []
    for table, name_col in (("custom_shapes", "name"), ("product_assemblies", "NULL")):
        cur.execute(f"SELECT id, {name_col} AS name, data FROM {table}")
        for r in cur.fetchall():
            try:
                data = json.loads(r["data"]) if isinstance(r["data"], str) else (r["data"] or {})
            except ValueError:
                continue
            parts = data.get("parts") or []
            if not any(p.get("lic_peers") for p in parts):
                continue
            pairs, bad = lic_peers_bad_pairs(parts, profil_glb, cache)
            if not bad:
                continue
            ukazka = ", ".join(f"#{i}↔#{j}" for i, j in bad[:6])
            cena = f" (+{round(len(bad) * joint_price)} Kč v ceně)" if joint_price else ""
            out.append((r["id"], f"{table} #{r['id']}" + (f" {r['name']}" if r.get("name") else ""),
                        f"{len(bad)} z {len(pairs)} párů v lic_peers nesplňuje definici spoje (celá plocha čela "
                        f"na čelo/stěnu): {ukazka}{' …' if len(bad) > 6 else ''} - scéna je po načtení započítá "
                        f"do spojů{cena}. Opravit data (odebrat páry), ne ceny."))
    return out


def check_absurd_attach_pose(cur):
    """Naucena poza napojeni (shop_products.attach_pose) s posunem vetsim
    nez 500 mm od rohu/svu = evidentne vadna hodnota.

    Zdroj chyby (bot8, 2026-08-19): hromadny precompute 2026-08-18 zapsal
    nekolika dilum pozy s posunem az 74 METRU (Place All je pak umistil
    uplne mimo scenu - Robertovo "rozky na kvadru nedolehaji"). Zadna
    kontrola tehdy absurdni hodnotu nezachytila - poza se tvari validne
    (spravny JSON tvar), jen cisla jsou nesmyslna. Realne pozy jsou v
    radu jednotek az desitek mm (odsazeni vuci rohu profilu); 500 mm je
    bezpecny strop i pro nejvetsi spojovaci desky (220 mm)."""
    out = []
    cur.execute(
        "SELECT id, name, sku, attach_pose FROM shop_products "
        "WHERE attach_pose IS NOT NULL AND attach_pose <> ''"
    )
    for row in cur.fetchall():
        pid, name, sku, raw = row["id"], row["name"], row["sku"], row["attach_pose"]
        try:
            pose = raw if isinstance(raw, dict) else json.loads(raw)
            pos = pose.get("pos") or []
            mag = math.sqrt(sum(float(x) * float(x) for x in pos))
        except (ValueError, TypeError, AttributeError):
            out.append((pid, name, f"SKU {sku}: attach_pose neni platny JSON s poli pos/q"))
            continue
        if mag > 500:
            out.append((
                pid, name,
                f"SKU {sku}: attach_pose pos={pos} je {mag:.0f} mm od rohu "
                "- evidentne vadna hodnota (realne pozy = jednotky az "
                "desitky mm). Dil se pri Place All umisti mimo sestavu. "
                "Znovu naucit (🎯 Ulozit pozici) nebo obnovit ze zalohy.",
            ))
    return out


# --- Mini-eshopy (car_storefronts) - popisne texty, viz WORKFLOW.md
# "Pravidla pro popisne texty storefrontu" (bot14, 2026-08-30, Robert:
# "musime udelat seznam limitu pro tvorbu popisu stranek a produktu...
# zadny popisny text pro autovestavby nesmi minout tento filtr"). Ctyri
# rucne psane bugy z noci 2026-08-29/30 zobecnene do trvalych kontrol -
# zbyla pravidla (fabrikace certifikaci, fingovane fotky) nejdou
# spolehlive overit regexem/SQL, zustavaji jen v dokumentu jako rucni
# kontrolni body.
_STOREFRONT_BRAND_RE = re.compile(r'logiman|konfigur[áa]tor|vandrawee', re.IGNORECASE)
# 2+ velka pismena + pomlcka/mezera + 3-5 cislic - tvar identifikatoru
# jako "HP-0579" (viz WORKFLOW.md pravidlo 4). Zamerne SIROKY vzorec
# (informativni upozorneni, ne tvrde selhani) - realne rozmery/vykony
# vozu ("88 kW", "L2H2") tenhle tvar nesplnuji (chybi pomlcka/mezera
# pred cislicemi ve spravnem poradi), ale false positive je porad
# mozny u budoucich textu - rucne posoudit kazdy nalez.
_STOREFRONT_CODE_RE = re.compile(r'\b[A-Z]{2,4}[- ]\d{3,5}\b')


def _storefront_text_fields(cur):
    """Sdileny generator (nameplate radek/pole, varianta radek/pole,
    text) pres oba zdroje textu storefrontu - pouziva vsechny 4 nasledujici
    kontroly, aby nove pridane pole stacilo zapsat na jednom miste."""
    cur.execute("SELECT id, slug, hero_title, hero_text, meta_title, meta_description FROM car_storefronts")
    for r in cur.fetchall():
        for field in ("hero_title", "hero_text", "meta_title", "meta_description"):
            val = r.get(field)
            if val:
                yield r["id"], f"car_storefronts:{r['slug']}", field, val
    cur.execute(
        "SELECT storefront_id, variant_slug, variant_description, meta_title, meta_description "
        "FROM car_storefront_models"
    )
    for r in cur.fetchall():
        for field in ("variant_description", "meta_title", "meta_description"):
            val = r.get(field)
            if val:
                yield r["storefront_id"], f"car_storefront_models:{r['variant_slug']}", field, val


def _category_text_fields(cur):
    """content_categories - hlavni kategorie konfiguratoru (TEXT_FILTR.md
    rozsah rozsireny 2026-09-05, bot20, Robert pres bot3). Napojeno na
    STEJNE 2 kontroly jako _storefront_text_fields nize
    (full_height_claim/nonsense_door_phrasing) - obe jsou univerzalni
    tvrzeni o fyzicke instalacni praxi, nezavisla na tom, jestli text
    zije na Fiat storefrontu nebo v hlavnim katalogu (overeno v datech -
    kategorie jako "Vestavby do dodávek, aut"/"Regály do auta"/
    "Kotvení vestaveb do auta" popisuji STEJNE vestavby do STEJNYCH aut).

    ZAMERNE NEnapojeno na storefront_brand_mention/storefront_
    identifier_leak/storefront_rack_height_exceeds_door:
    - brand_mention/identifier_leak reesi skryti materske firmy PRED
      oddelene brandovanym storefrontem (jina domena, Fiat mini-eshop).
      content_categories ale JE hlavni web Logiman/autovestavby.logiman.cz, kde
      vlastni jmeno v meta_title je SPRAVNE a OCEKAVANE - overeno primo
      v datech (napr. "Katalog hliníkových profilů Logiman ke stažení",
      "Konektory pro patky hliníkových profilů Logiman"). Napojit by
      znamenalo desitky falesnych "nalezu" na spravnem textu - presny
      opak ucelu kontroly.
    - rack_height_exceeds_door pocita konkretni cislo VYSKY DVERI JEDNE
      VARIANTY KONKRETNIHO AUTA (JOIN car_storefront_models -> car_models
      -> karoserie_model_reference). Kategorie neni vazana na jeden
      konkretni model/karoserii (jedna kategorie pokryva vic znacek/
      modelu najednou) - nema tedy jedno cislo, proti kteremu by se dalo
      porovnat. Strukturalni duvod (chybi 1:1 vazba), ne jen rozsah."""
    cur.execute("SELECT id, slug, meta_title, meta_description, nav_label FROM content_categories")
    for r in cur.fetchall():
        for field in ("meta_title", "meta_description", "nav_label"):
            val = r.get(field)
            if val:
                yield r["id"], f"content_categories:{r['slug'] or r['id']}", field, val


def check_storefront_brand_mention(cur):
    # WORKFLOW.md pravidlo 5 ("zadna zminka materske firmy/brandu") -
    # Robert: "Logiman nemuze byt uveden ani v paticce" - zjisteno
    # 2026-08-30 v paticce sablony I v DB meta_title (viz AGENTS_LOG.md).
    out = []
    for row_id, label, field, val in _storefront_text_fields(cur):
        if _STOREFRONT_BRAND_RE.search(val):
            out.append((row_id, label, f"pole '{field}' zmiňuje mateřskou firmu/projekt (pravidlo 5)"))
    return out


def check_miniweb_text_brand_leak(cur):
    # bot5 2026-10-02 (TEXT_FILTR pravidlo 5, bot3: mini-shop Packstations je BEZ znacky): texty mini-shopu - nazvy kategorii, texty produktu v kazdem jazyce (i koncepty), parametry, verejny kod,
    # adresy, kontakt shopu a adresa jeho domeny - nesmi nest znacku ani dodavatele. Zdroj pravdy o tom, co je znacka, je dealers._BRAND_RE (stejny regex pouziva verejne API /api/miniweb/*
    # a dealersky program). API takovou polozku verejne SKRYJE (fail closed: produkt se znackou se nevyda, kategorie se znackou i s podkategoriemi), zakaznik by proto videl jen tise chybejici
    # produkt. Tahle kontrola ukaze, KTERY text to je, aby se opravil u zdroje (anglicke texty dodava bot7, schvaluje Robert). Jedina vyjimka je legal.seller (zakonny udaj), ten v DB neni.
    import app  # noqa: F401 - NEJDRIV cely app (poradi importu), az pak dealers: import dealers jako prvni konci kruhovym importem dealers <-> app (v serveru je app uz nacteny)
    import dealers  # lazy: nedostupnost modulu shodi jen tuhle kontrolu (run_checks ji odchyti)
    hit = dealers._brand_hit
    out = []
    cur.execute(
        "SELECT t.miniweb_category_id AS id, t.lang, t.name, c.slug FROM miniweb_category_texts t "
        "JOIN miniweb_categories c ON c.id = t.miniweb_category_id ORDER BY t.miniweb_category_id, t.lang"
    )
    for r in cur.fetchall():
        for field in ("name", "slug"):
            if hit(r[field]):
                out.append((f"kategorie:{r['id']}:{r['lang']}:{field}", f"miniweb_category_texts:{r['slug']}",
                            f"pole '{field}' (jazyk {r['lang']}) zmiňuje značku/dodavatele (pravidlo 5) - API kategorii i s podkategoriemi veřejně skrývá"))
    cur.execute(
        "SELECT t.miniweb_product_id AS id, t.lang, t.name, t.summary, t.description, t.delivery, t.specs_json, p.slug, p.public_sku "
        "FROM miniweb_product_texts t JOIN miniweb_products p ON p.id = t.miniweb_product_id ORDER BY t.miniweb_product_id, t.lang"
    )
    for r in cur.fetchall():
        for field in ("name", "summary", "description", "delivery", "specs_json", "slug", "public_sku"):
            if hit(r[field]):
                out.append((f"produkt:{r['id']}:{r['lang']}:{field}", f"miniweb_product_texts:{r['slug']}",
                            f"pole '{field}' (jazyk {r['lang']}) zmiňuje značku/dodavatele (pravidlo 5) - API produkt veřejně skrývá"))
    cur.execute("SELECT m.storefront_id AS id, m.contact_json, s.slug, s.primary_domain FROM miniweb_shops m JOIN car_storefronts s ON s.id = m.storefront_id ORDER BY m.storefront_id")
    for r in cur.fetchall():
        for field in ("contact_json", "slug", "primary_domain"):
            if hit(r[field]):
                out.append((f"shop:{r['id']}:{field}", f"miniweb_shops:{r['slug']}",
                            f"pole '{field}' zmiňuje značku/dodavatele (pravidlo 5) - API ho veřejně neuvádí (kontakt prázdný, odkaz na jazykovou verzi a slug neutrální)"))
    return out


# --- Staticke stranky sdilene s anonymnimi domenami (bot16, 2026-10-01, Robert pres bot3: "at ma Logiman jednotny
# vzhled jako na homepage" - logo na prihlasovacich strankach). nginx servi na vhostech mini-eshopu cely webapp/
# (`location /` root webapp/ + try_files), takze login/register/forgot/reset/verify-email i sablony storefront-*.html
# vidi i zakaznik na domene BEZ znacky (TEXT_FILTR.md pravidlo 5, Robert 2026-08-30: "Logiman nemuze byt uveden ani v
# paticce"). `storefront_brand_mention` vyse ale cte jen TEXTY V DB, ne tyhle SOUBORY (viz "Nedoreseno (bot16)" v
# TEXT_FILTR.md u pravidla 5) - kdyby nekdo logo/jmeno firmy vlozil rovnou do login.html, nic by to nechytilo.
# Spravne reseni je logo ze serveru podle Hosta: api/site_brand.py + prazdny <div id="siteLogoSlot"> ve strankach.
# miniweb/*.html = anglicky mini-shop sestav stolu (bot16, 2026-10-02): bezi na samostatnych domenach BEZ znacky, texty jsou v i18n/*.json.
_ANONYMNI_STRANKY = ("login.html", "register.html", "forgot-password.html", "reset-password.html",
                     "verify-email.html", "storefront-*.html", "miniweb/*.html")
# Soubory, ktere se na anonymnich domenach servi, i kdyz je stranka nenacita staticky (logo ho nacita az dynamicky).
# Vzory (glob): mini-shop nacita config/preklady az za behu, modul konfiguratoru s 3D prohlizecem dynamicky z product.html i mini-shopu.
_ANONYMNI_DALSI_SOUBORY = ("css/brand-logo.css", "miniweb/*.json", "miniweb/i18n/*.json", "miniweb/*.js", "miniweb/*.css",
                           "js/product-configurator.js", "css/product-configurator.css", "js/v3d/viewer3d.js", "css/v3d.css")
_ANONYMNI_LOKALNI_ZDROJ_RE = re.compile(r'''(?:src|href)\s*=\s*["'](/[^"'#?]+\.(?:js|css))''', re.IGNORECASE)
# Logo je dvoubarevne ("LOGi" + "MAN" ve dvou <span>) - samotny regex na slovo by ho nechytil, kdyby chybel aria-label.
_ANONYMNI_ROZDELENE_LOGO_RE = re.compile(r"logi\s*(?:<[^>]*>\s*)*man\b", re.IGNORECASE)
# Uzce vymezena vyjimka (TEXT_FILTR.md pravidlo 5, Robert 2026-09-17): hub fiat-autovestavby.top smi mit 2 prolinky na
# hlavni web. Povolen je JEN tenhle host, nejvyse 2x, a jen v sablone hubu - zadny jiny text znacky.
_ANONYMNI_HUB_SABLONA = "storefront-hub.html"
_ANONYMNI_HUB_HOST = "autovestavby.logiman.cz"
_ANONYMNI_HUB_MAX = 2


def _anonymni_soubory():
    """(stranky, vsechny_skenovane_soubory) - stranky sdilene s anonymnimi domenami + lokalni .js/.css, ktere nacitaji."""
    stranky = []
    for vzor in _ANONYMNI_STRANKY:
        stranky.extend(sorted(glob.glob(os.path.join(WEBAPP_DIR, vzor))))
    soubory = list(stranky)
    for p in stranky:
        try:
            text = _read_cached(p)
        except Exception:
            continue  # nahlasi se nize pri ctenicim skenu stranky
        for m in _ANONYMNI_LOKALNI_ZDROJ_RE.finditer(text):
            cesta = os.path.normpath(os.path.join(WEBAPP_DIR, m.group(1).lstrip("/")))
            if cesta.startswith(WEBAPP_DIR + os.sep) and cesta not in soubory and os.path.isfile(cesta):
                soubory.append(cesta)
    for rel in _ANONYMNI_DALSI_SOUBORY:
        for cesta in sorted(glob.glob(os.path.join(WEBAPP_DIR, rel))):
            cesta = os.path.normpath(cesta)
            if cesta not in soubory and os.path.isfile(cesta):
                soubory.append(cesta)
    return stranky, soubory


def check_static_page_brand_leak(cur):
    stranky, soubory = _anonymni_soubory()
    if not stranky:
        # prazdny vstup nesmi vypadat jako "vse v poradku"
        return [("static_page_brand_leak:no-input", "webapp",
                 "kontrola nenašla žádnou hlídanou stránku (login.html, storefront-*.html...) - přejmenované/přesunuté? "
                 "Uprav _ANONYMNI_STRANKY v qa_checks.py")]
    out = []
    for path in soubory:
        rel = os.path.relpath(path, WEBAPP_DIR)
        try:
            content = _read_cached(path)
        except Exception as e:
            out.append((f"{rel}:read-error", rel, f"sken selhal ({e}) - zkontroluj ručně"))
            continue
        if os.path.basename(path) == _ANONYMNI_HUB_SABLONA and content.count(_ANONYMNI_HUB_HOST) <= _ANONYMNI_HUB_MAX:
            content = content.replace(_ANONYMNI_HUB_HOST, "")
        # cely obsah naraz (ne po radcich) - rozdelene logo se muze zalomit mezi dva radky
        nalezy = {}
        for rx in (_STOREFRONT_BRAND_RE, _ANONYMNI_ROZDELENE_LOGO_RE):
            for m in rx.finditer(content):
                nalezy.setdefault(content.count("\n", 0, m.start()) + 1, " ".join(m.group(0).split()))
        for radek in sorted(nalezy):
            out.append((f"{rel}:{radek}", rel,
                        f"{rel}, řádek {radek}: zmínka mateřské firmy/projektu ('{nalezy[radek]}') ve statické stránce sdílené "
                        "s anonymními doménami (pravidlo 5). Logo/značku sem nevkládat - ukazuje se jen ze serveru podle "
                        "Hosta (api/site_brand.py, prázdné místo #siteLogoSlot)"))
    return out


# --- Staticke stranky s PEVNE vlozenym pismem webu (bot16, 2026-10-01). Stranky bez SSR (kontakt, realizace, poptavka-stul, 404,
# moje-objednavky) nedostavaji --font-main z volby admina (site_font.py), takze logo i text v nich by byly v systemovem pismu a
# vypadaly jinak nez homepage ("Logo ztucnelo", Robert 2026-09-27). Maji proto Manrope vlozeny natvrdo (<link> na Google Fonts +
# --font-main). Kdyz admin zmeni volbu pisma, tyhle stranky o tom nevi - tahle kontrola to ohlasi misto tichych rozdilu.
_STATIC_FONT_PAGES = ("kontakt.html", "realizace.html", "poptavka-stul.html", "404.html", "moje-objednavky.html")
_GOOGLE_FONT_LINK_RE = re.compile(r'''fonts\.googleapis\.com/css2\?family=([^"&'\s]+)''')


def _site_font_options():
    """FONT_OPTIONS z api/site_font.py bez importu modulu (ten tahne celou aplikaci) - je to cisty literal dict, cte se z AST."""
    src = _read_cached(os.path.join(API_DIR, "site_font.py"))
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "FONT_OPTIONS" for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def check_static_page_font_stale(cur):
    try:
        opts = _site_font_options()
    except Exception:
        opts = None
    if not opts:
        return [("static_page_font_stale:no-options", "site_font.py",
                 "FONT_OPTIONS se nepodařilo načíst z api/site_font.py - kontrola písma statických stránek nemá s čím porovnat")]
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", ("site_font_key",))
    row = cur.fetchone()
    key = row["setting_value"] if row and row["setting_value"] in opts else "system"  # jako _resolve_key v site_font.py
    ocekavane = opts[key]["google"]  # None = systemove pismo (zadny Google Fonts odkaz)
    out = []
    for fname in _STATIC_FONT_PAGES:
        try:
            content = _read_cached(os.path.join(WEBAPP_DIR, fname))
        except Exception as e:
            out.append((f"{fname}:read-error", fname, f"sken selhal ({e}) - zkontroluj ručně"))
            continue
        m = _GOOGLE_FONT_LINK_RE.search(content)
        pouzite = m.group(1) if m else None
        if pouzite != ocekavane:
            out.append((fname, fname,
                        f"{fname}: pevně vložené písmo ({pouzite or 'žádné'}) neodpovídá volbě písma webu v adminu "
                        f"({key}: {ocekavane or 'systémové'}) - logo vypadá jinak než na homepage. Uprav <link> na fonts.googleapis.com "
                        "a --font-main v téhle stránce (nebo ji převeď na SSR přes site_font_ssr_head)"))
    return out


def check_storefront_identifier_leak(cur):
    # WORKFLOW.md pravidlo 4 - konkretni kod/identifikator sdileny s
    # hlavnim webem je fingerprint riziko stejne jako jmeno firmy (viz
    # HP-0579 pripad, AGENTS_LOG.md 2026-08-30). SIROKY/informativni
    # vzorec - kazdy nalez posoudit rucne, neni to tvrde pravidlo proti
    # kazdemu retezci ve tvaru pismena+cislice.
    out = []
    for row_id, label, field, val in _storefront_text_fields(cur):
        m = _STOREFRONT_CODE_RE.search(val)
        if m:
            out.append((row_id, label, f"pole '{field}' obsahuje možný identifikátor '{m.group(0)}' - ověřit, jestli není sdílený s hlavním webem (pravidlo 4)"))
    return out


def check_storefront_nonsense_door_phrasing(cur):
    # TEXT_FILTR.md pravidlo 2 (drive WORKFLOW.md bod 21) - "dvere se
    # oteviraji do X mm" popisuje vysku NAKLADACIHO OTVORU, ne pohyb
    # dveri (Robert, 2026-08-30, AGENTS_LOG.md - 3 z 22 variant mely
    # tenhle bug pri prvnim psani). Rozsireno 2026-09-05 (bot20) i na
    # content_categories - duvod/vyjimky viz _category_text_fields().
    out = []
    pattern = re.compile(r'dveř[^.]{0,20}otevír[^.]{0,10}do\s+(?:výšky\s+)?\d', re.IGNORECASE)
    for row_id, label, field, val in itertools.chain(_storefront_text_fields(cur), _category_text_fields(cur)):
        if pattern.search(val):
            out.append((row_id, label, f"pole '{field}' tvrdí, že dveře 'se otevírají do X mm' - popsat výšku NAKLÁDACÍHO OTVORU, ne pohyb dveří (pravidlo 2)"))
    return out


def check_storefront_full_height_claim(cur):
    # TEXT_FILTR.md pravidlo 1 (drive WORKFLOW.md bod 21) - tvrzeni
    # "regal do plne/celou vysky prostoru" je tvrzeni o SKUTECNE
    # INSTALACNI PRAXI, ne odvozeny fakt z rozmeru (Robert, 2026-08-30:
    # "nikdy nestavime regal do plne vysky", AGENTS_LOG.md). Vyjimka:
    # veta popisujici OPAK (ze prostor NA plnou vysku NESTACI, typicky
    # spojkou "spis X NEZ plnou vysku Y") je v poradku - overeno na
    # skutecnem pripadu (Scudo l1h1-16, "spis nizky regal po strane NEZ
    # plnou vysku police"), proto se matchi s "než"/"ne " tesne pred
    # frazi VYRAZENE, ne jen kazda zminka fraze. Rozsireno 2026-09-05
    # (bot20) i na content_categories - duvod/vyjimky viz
    # _category_text_fields().
    out = []
    pattern = re.compile(r'(?:plnou|plné|celou)\s+výšk\w*[^.]{0,40}(?:regál|polic|vestavb)', re.IGNORECASE)
    negation = re.compile(r'\b(než|ne)\s*$', re.IGNORECASE)
    for row_id, label, field, val in itertools.chain(_storefront_text_fields(cur), _category_text_fields(cur)):
        m = pattern.search(val)
        if m and not negation.search(val[max(0, m.start() - 20):m.start()]):
            out.append((row_id, label, f"pole '{field}' tvrdí, že regál/vestavba jde postavit do plné výšky prostoru - bez ověřené instalační praxe neuvádět (pravidlo 1)"))
    return out


def check_storefront_rack_height_exceeds_door(cur):
    """WORKFLOW.md pravidlo 1a - Robert pres toscanaccio-0b, 2026-08-30:
    "regál má vždy maximální výšku takovou, aby se dal vložit do auta
    zadními dveřmi" - realny strop vysky regalu je vyska ZADNICH DVERI
    (karoserie_model_reference.official_door_opening_height_mm), NE
    strop nakladoveho prostoru (cargo_height_mm) - u vyssich karoserii
    (H2 apod.) byva otvor nizsi nez strop. Presne tenhle vzorec unikl
    kontrole storefront_full_height_claim (ta hlida jen frazi "plnou/
    celou vysku", ne CISLO) - Ducato L2H2 puvodne psalo "Vyska 1932 mm
    dovoluje postavit vysoky regal", 1932 je ale strop, ne dvere (1790).

    Heuristika (informativni, kazdy nalez posoudit rucne): najde cisla
    3-4 cifer v okoli slova "regál" v textu, porovna proti znamemu
    door_h teto konkretni varianty (JOIN pres karoserie_model_reference.
    car_models_id - bot8 2026-09-06, drive fragilni parsovani vendor
    kodu v zavorce car_models.name, FUNGOVALO JEN PRO ZNACKY S KODEM VE
    TVARU [XXnn], napr. Fiat - stabilni FK funguje pro vsechny znacky).
    Cislo rovne door_h (spravna formulace, viz oprava vyse) se NEHLASI,
    jen cislo VETSI nez door_h.
    Varianty bez zname door_h (NULL v DB) kontrola presuti - nejde
    overit, proto se nehlasi (informace chybi, ne nutne chyba textu)."""
    out = []
    cur.execute(
        """
        SELECT csm.storefront_id, csm.variant_slug, csm.variant_description,
               kmr.official_door_opening_height_mm AS door_h
        FROM car_storefront_models csm
        JOIN car_models cm ON cm.id = csm.car_model_id
        LEFT JOIN karoserie_model_reference kmr ON kmr.car_models_id = cm.id
        WHERE csm.variant_description IS NOT NULL AND kmr.official_door_opening_height_mm IS NOT NULL
        """
    )
    number_near_rack = re.compile(r'(?:regál\w*[^.]{0,40}?(\d{3,4})|(\d{3,4})[^.]{0,40}?regál\w*)', re.IGNORECASE)
    # "A × B × C mm" rozmerova trojice (delka×sirka×vyska nakladoveho
    # prostoru/dveri) skoro vzdy jen popisuje KAROSERII, ne tvrzeni o
    # vysce regalu - i kdyz "regál" padne do 40znakoveho okna (napr.
    # "1817 × 1230 × 1270 mm... typicky nizsi regál po strane"). Cislo
    # tesne za "×" proto vyrazujeme (overeno na skutecnem false
    # positive, Doblò L1 2026-08-30).
    dimension_triple = re.compile(r'×\s*$')
    # OPRAVA (bot20, 2026-09-05, hloubkova kontrola pri rozsirovani
    # TEXT_FILTR.md na kategorie) - skutecny false positive na Scudo
    # l1h1-16: "Nižší strop (1449 mm) znamená spíš širší nízký regál po
    # straně NEŽ PLNOU VÝŠKU police" - presne tahle veta je v komentari
    # u check_storefront_full_height_claim vys citovana jako HISTORICKY
    # DUVOD, proc tam vznikl negacni "než/ne" guard - ten guard se ale
    # nikdy nepřenesl sem. Overeno primo v datech: 1449 mm je cargo_
    # height_mm (nakladovy prostor, ne regál) a sedi presne na
    # karoserie_model_reference; 1272 mm door_h je vyska ZADNICH dveri,
    # veta ale mluvi o BOCNICH dverich (1293 mm, taky presne sedici) -
    # ani text, ani DB nejsou spatne, jen kontrola srovnavala 2 nesouvisejici
    # cisla. Detekce: pokud je ve OKOLI cisla stejny vzorec "než/ne plnou/
    # plné/celou výšku", jde o VEDOME NEGOVANÉ tvrzeni (jako u sesterske
    # kontroly), ne o tvrzeni o presazeni - takove cislo se nehlasi.
    full_height_negated = re.compile(r'(?:než|ne)\s*(?:plnou|plné|celou)\s+výšk\w*', re.IGNORECASE)
    for r in cur.fetchall():
        door_h = r["door_h"]
        text = r["variant_description"]
        for m in number_near_rack.finditer(text):
            num_start = m.start(1 if m.group(1) else 2)
            num = int(m.group(1) or m.group(2))
            if dimension_triple.search(text[max(0, num_start - 4):num_start]):
                continue
            if full_height_negated.search(text[max(0, num_start - 80):num_start + 120]):
                continue
            if num > door_h:
                out.append((
                    r["storefront_id"], f"car_storefront_models:{r['variant_slug']}",
                    f"variant_description zmiňuje {num} mm u regálu, ale výška zadního nakládacího "
                    f"otvoru téhle varianty je jen {door_h} mm - regál nemůže být vyšší (pravidlo 1a)",
                ))
    return out


def check_assembly_rail_above_leg_top(cur):
    """Lůžko (nosník patra) nad horním okrajem profilu nohy = porušení
    pravidla limit_maximalni_vysky_patra (KOMPONENTY_EUROBOXY.md
    shape_geometry_methods.id=3): railYCenter musí být <= TOP_Y - T/2, kde
    TOP_Y = horní okraj profilu nohy. BOX v nejvyšším patře přesahovat SMÍ
    (podepřen jen zdola), LŮŽKO ne.

    Zdroj chyby (bot22, 2026-09-05, Robert "kde se zkrátily nohy, musí se
    znovu aplikovat pravidla"): po zkrácení noh (id=8 výška dveří / id=6
    podběh) zůstala u 5 sestav (Caddy VW31) lůžka nad novým, nižším TOP_Y -
    pravidlo se po zkrácení znovu neaplikovalo. Tahle kontrola tu třídu hlídá
    napříč VŠEMI sestavami, aby se stejný vzor po jakémkoli budoucím zkrácení
    noh chytil sám. TOP_Y i railYCenter se počítají z position/scale dílů
    Object_7 (symetrický pivot 30x1000x30 - ověřeno)."""
    T = 30.0
    BASE = 1000.0  # délka Object_7 při scale.y=1
    out = []
    cur.execute("SELECT id, name, data FROM product_assemblies")
    for pid, name, raw in cur.fetchall():
        try:
            data = raw if isinstance(raw, dict) else json.loads(raw)
        except (ValueError, TypeError):
            continue
        parts = data.get("parts") or []
        top_y = None
        for p in parts:
            if p.get("part_id") == "Object_7" and re.search(r"svislice|cap", p.get("role") or ""):
                pos, sc = p.get("position"), p.get("scale")
                if not pos or not sc:
                    continue
                t = pos[1] + sc[1] * BASE / 2.0  # vrchol svislého profilu
                if top_y is None or t > top_y:
                    top_y = t
        if top_y is None:
            continue
        limit = top_y - T / 2.0
        for p in parts:
            if re.match(r"^nosnik", p.get("role") or ""):
                pos = p.get("position")
                if pos and pos[1] > limit + 1:
                    out.append((
                        pid, name,
                        f"lůžko (nosník {p.get('role')}) railYCenter={pos[1]:.0f} mm > "
                        f"TOP_Y-T/2={limit:.0f} mm - po zkrácení noh se lůžko musí odstranit/"
                        "snížit (limit_maximalni_vysky_patra; box smí přesahovat, lůžko ne).",
                    ))
                    break
    return out


def check_assembly_part_missing_transform(cur):
    """Díl v product_assemblies.data.parts bez position/quaternion/scale.

    Zdroj chyby (bot22, 2026-09-05, Robert "nereaguje vložení do scény"):
    10 sestav (5x Transit Custom FO31, 5x T7 VW25 - přestavba 2026-09-01)
    mělo díly car_body BEZ position. insertCustomShape ve scene.html volá
    loadCustomShapePartEntry na každý díl; ten bez position hodí TypeError
    UVNITŘ async loader.load callbacku - mimo try/catch - takže unikne jako
    "Uncaught (in promise)" a celé vložení sestavy TIŠE zamrzne (žádný alert).
    Data se tváří validně (správný JSON), jen dílu chybí transformace.
    Každý díl MUSÍ mít position/quaternion/scale (pole 3, resp. 4 čísel)."""
    out = []
    cur.execute("SELECT id, name, data FROM product_assemblies")
    for pid, name, raw in cur.fetchall():
        try:
            data = raw if isinstance(raw, dict) else json.loads(raw)
        except (ValueError, TypeError):
            continue
        for i, part in enumerate(data.get("parts") or []):
            if not isinstance(part, dict):
                continue
            miss = [k for k in ("position", "quaternion", "scale") if not part.get(k)]
            if miss:
                out.append((
                    pid, name,
                    f"díl #{i} ({part.get('part_id')}) nemá {'/'.join(miss)} "
                    "- insertCustomShape ve scéně na tom tiše spadne (Uncaught, "
                    "vložení zamrzne). Doplnit transformaci do data.parts.",
                ))
                break
    return out


# Kod karoserie: K-075, K-123e. Pripona "e" je JINE vozidlo, ne varianta
# (WORKFLOW.md pravidlo 25).
#
# HRANICE SLOVA na obou stranach jsou nutne - bez nich chyta kontrola
# falesne nalezy uvnitr beznych nazvu (overeno na zivych datech 2026-09-11):
#   "delici-stena-k-4530-4531-4536"      -> k-453 + ctvrta cislice
#   "podlahova-brzda-zvedak-134x116-mm"  -> zvedaK-134
#   "valeckovy-posuvnik-150-mm"          -> posuvniK-150
# U vsech trech `\b` spravne zabrani nalezu (pred K je pismeno, resp. za
# treti cislici pokracuje dalsi).
#
# CASE-INSENSITIVE zamerne: kod se stejne tak dostane do SLUGU, kde je
# zapsany malymi pismeny ("doblo-k-075-c-...") a slug je v URL, tedy taky
# zakaznicky viditelny. Bez `re.I` by slug propadl.
_K_KOD_RE = re.compile(r"\bK-\d{3}e?\b", re.IGNORECASE)
# Rozpis boxu v nazvu, napr. "boxy43-220x3-170x3-120x2".
_ROZPIS_BOXU_RE = re.compile(r"boxy\d+-", re.IGNORECASE)


def _zakaznicky_viditelne_texty(cur):
    """Generator (id, popis_radku, pole, text) pres texty, ktere CTE ZAKAZNIK.

    Zamerne NEobsahuje `car_models.name` ani jina interni/katalogova pole -
    tam kod karoserie NALEZI (WORKFLOW.md pravidlo 25: "kod patri do DB").
    Kontroluje se jen to, co se dostane na produktovou kartu nebo do
    verejneho textu webu.

    `shop_products.sku` tu ZAMERNE NENI, i kdyz kod karoserie obsahuje
    (dnes napr. SEST-K-075-EB-30). SKU je technicky identifikator pro
    sklad a objednavky, kde je stabilni kod naopak zadouci - kdyby se
    odvozovalo od marketingoveho nazvu, rozpadne se pri kazde uprave
    textu. Rozhodnuto 2026-09-11 (Robert pres bot8) pri prejmenovani
    karty 3942. Nepridavat sem `sku` "pro uplnost" - byl by to falesny
    nalez na spravne hodnote."""
    cur.execute(
        "SELECT id, sku, name, slug, short_description, meta_title, meta_description "
        "FROM shop_products WHERE is_archived=0"
    )
    for r in cur.fetchall():
        # `slug` je soucasti verejne URL (/produkt/<slug>), tedy taky
        # zakaznicky viditelny - proto se kontroluje s ostatnimi texty.
        for field in ("name", "slug", "short_description", "meta_title", "meta_description"):
            val = r.get(field)
            if val:
                yield r["id"], f"shop_products:{r['sku'] or r['id']}", field, val

    # `product_assemblies.name` JE zakaznicky viditelny (bot5, 2026-09-12).
    # Od commitu `aa050117` (2026-09-10) ho posila ven VEREJNY endpoint
    # `GET /api/shop/products/<id>/assemblies` a `webapp/product.html` ho
    # vykresluje jako popisek provedeni na posuvniku. Tahle kontrola
    # vznikla 2026-09-11, tedy DEN POTE - nesla o zastaraly predpoklad,
    # ale o prehlednuti: docstring vyse spravne rika "interni/katalogova
    # pole sem nepatri", jenze tohle pole prestalo byt interni.
    #
    # Nalezeno na realnych datech: vsech 13 sestav navazanych na karty
    # 3943/3944/3945 by zakaznikovi ukazalo "[10/30mm od kolize]" a sestavy
    # Jumpy k tomu jeste "K-118"/"K-119". Neuniklo to jen proto, ze ty
    # karty jeste nejsou aktivni - tedy presne ten okamzik, kdy to ma
    # kontrola zachytit: PRED publikaci.
    #
    # Omezeno na sestavy NAVAZANE NA KARTU (`shop_product_id IS NOT NULL`):
    # jen ty muze verejny endpoint vratit. Nenavazana sestava je porad
    # cistě interni a jeji pracovni nazev je v poradku.
    #
    # ID nalezu je ZAMERNE retezec "sestava:<id>", ne cislo - v adminu
    # rozhoduje `String(parseInt(id)) === String(id)` o tom, jestli ma
    # nalez tlacitko "otevrit" (viz QA_AUDIT_ACTIONS v dashboard.js).
    # Cislo by se tvarilo jako id PRODUKTU a otevrelo cizi skladovou kartu.
    cur.execute(
        "SELECT pa.id, pa.name, sp.sku, sp.id AS product_id "
        "FROM product_assemblies pa "
        "JOIN shop_products sp ON sp.id = pa.shop_product_id "
        "WHERE sp.is_archived=0"
    )
    for r in cur.fetchall():
        if r["name"]:
            yield (
                f"sestava:{r['id']}",
                f"product_assemblies:{r['id']} (karta {r['sku'] or r['product_id']})",
                "name",
                r["name"],
            )
    for row in _storefront_text_fields(cur):
        yield row
    for row in _category_text_fields(cur):
        yield row


def check_k_kod_v_zakaznickem_textu(cur):
    """Kod karoserie K-XXX v textu, ktery cte zakaznik.

    WORKFLOW.md pravidlo 25 (Robert, 2026-09-09): "karoserie se cisluji
    K-XXX ... kod patri do DB, NE do produktovych karet sestav regalu."
    Zakaznikovi ten kod nic nerika - je to nas interni identifikator
    karoserie.

    Trida chyby, ne jednorazovy preklep (bot9, 2026-09-11): pri
    prejmenovavani karty 3942 se navrhoval nazev "Regal Doblo K-075",
    ktery by pravidlo porusil, a nikdo si toho nevsiml az do rucni
    kontroly - protoze tohle dosud nehlidalo nic. Stejne snadno to muze
    prosakovat pri kazdem dalsim zakladani karty ze sestavy, jejiz
    INTERNI nazev kod obsahuje (dnes 237 z 269 sestav)."""
    out = []
    for row_id, label, field, val in _zakaznicky_viditelne_texty(cur):
        nalez = _K_KOD_RE.search(str(val))
        if nalez:
            out.append((
                row_id, label,
                f"{field} obsahuje kód karoserie „{nalez.group(0)}\" - ten patří "
                f"do DB, ne do zákaznického textu (WORKFLOW.md pravidlo 25). "
                f"Text: {str(val)[:80]}",
            ))
    return out


_HRANATA_POZNAMKA_RE = re.compile(r"\[[^\]]{1,60}\]")


def check_interni_poznamka_v_zakaznickem_textu(cur):
    """Interni poznamka v [hranatych zavorkach] v zakaznicky viditelnem textu.

    Sesterska kontrola ke `k_kod_v_zakaznickem_textu` (bot5, 2026-09-12) -
    tentyz kanal uniku, jiny obsah. Zatimco K-kod hlida identifikator
    karoserie, tahle hlida PRACOVNI POZNAMKY, ktere si boti a scena
    pripisuji do nazvu v hranatych zavorkach.

    Trida chyby, ne preklep: hranata zavorka je v tomhle projektu
    zavedeny zpusob, jak k nazvu pripsat neco pro nas - nalezeno
    "[10/30mm od kolize]" (kolizni rezerva, ciste interni parametr) a
    "[ZÁKLAD]" (oznaceni zastupce). Obojí davalo smysl ve scene, obojí
    je pro zakaznika smeti. Pribyva to samo od sebe pri kazde davce, co
    sestavy prejmenovava.

    Nalezeno na realnych datech: 13 sestav navazanych na karty
    3943/3944/3945, tedy VSECHNY. V `shop_products` bylo naopak 0
    vyskytu - hranata zavorka tam zadnou legitimni funkci nema, takze
    kontrola nehlasi falesne spravny text.

    Pojistka na frontendu existuje taky (`pdAssemblyLabel` v
    `webapp/product.html` zavorky orezava), ale ta jen MASKUJE - v DB
    text zustava a jinou cestou ven muze uniknout. Proto obojí."""
    out = []
    for row_id, label, field, val in _zakaznicky_viditelne_texty(cur):
        nalez = _HRANATA_POZNAMKA_RE.search(str(val))
        if nalez:
            out.append((
                row_id, label,
                f"{field} obsahuje interní poznámku „{nalez.group(0)}\" - hranaté "
                f"závorky v názvu jsou pracovní poznámka pro nás, zákazníkovi nic "
                f"neříkají. Text: {str(val)[:80]}",
            ))
    return out


def check_karta_nazvana_jako_jedna_sestava(cur):
    """Produktova karta nese VIC sestav, ale jmenuje se jako jedna z nich.

    WORKFLOW.md pravidlo 26 (preformulovano Robertem 2026-09-11): jedna
    karta nese vic sestav a prepinaji se dvema posuvniky (verze boxu x
    horni blok) - u produktu 3942 dnes sedm, vyhledove 3 x 6 = 18. Karta
    se proto jmenuje PO VOZIDLE; nazev jedne konkretni sestavy (rozpis
    boxu nebo kod karoserie) na ni znamena, ze karta pojmenovava jednu
    polohu obou posuvniku misto celeho vyrobku.

    Hlasi se jen karty s VIC nez jednou navazanou sestavou - u karty
    s jedinou sestavou zatim neni co splest a hlasit by to znamenalo
    falesne nalezy na starsich produktech."""
    out = []
    cur.execute(
        "SELECT p.id, p.sku, p.name, COUNT(a.id) AS sestav "
        "FROM shop_products p JOIN product_assemblies a ON a.shop_product_id = p.id "
        "WHERE p.is_archived=0 GROUP BY p.id, p.sku, p.name HAVING COUNT(a.id) > 1"
    )
    for r in cur.fetchall():
        duvody = []
        if _ROZPIS_BOXU_RE.search(r["name"] or ""):
            duvody.append("rozpis boxů")
        nalez_k = _K_KOD_RE.search(r["name"] or "")
        if nalez_k:
            duvody.append(f"kód karoserie „{nalez_k.group(0)}\"")
        if duvody:
            out.append((
                r["id"], r["sku"] or str(r["id"]),
                f"karta nese {r['sestav']} sestav, ale její název obsahuje "
                f"{' a '.join(duvody)} - to je název jedné konkrétní sestavy, "
                f"ne výrobku. Karta se jmenuje po vozidle (pravidlo 26). "
                f"Název: {r['name']}",
            ))
    return out


CHECKS = {
    "ssr_slug_route_without_visibility_filter": ("Veřejná SSR routa hledá slug bez filtru viditelnosti (soft-404 u skrytého záznamu)", check_ssr_slug_route_without_visibility_filter),
    "assembly_rail_above_leg_top": ("Lůžko (nosník) nad horním okrajem nohy - porušení limit_maximalni_vysky_patra po zkrácení noh", check_assembly_rail_above_leg_top),
    "assembly_part_missing_transform": ("Díl produktové sestavy bez position/quaternion/scale (shodí vložení do scény)", check_assembly_part_missing_transform),
    "k_kod_v_zakaznickem_textu": ("Kód karoserie K-XXX v zákaznicky viditelném textu (patří do DB, ne na kartu)", check_k_kod_v_zakaznickem_textu),
    "interni_poznamka_v_zakaznickem_textu": ("Interní poznámka v [hranatých závorkách] v zákaznicky viditelném textu", check_interni_poznamka_v_zakaznickem_textu),
    "karta_nazvana_jako_jedna_sestava": ("Produktová karta nese víc sestav, ale jmenuje se jako jedna z nich", check_karta_nazvana_jako_jedna_sestava),
    "missing_price": ("Aktivní produkty bez ceny", check_missing_price),
    "missing_image": ("Aktivní produkty bez obrázku", check_missing_image),
    "missing_description": ("Aktivní produkty bez popisu", check_missing_description),
    "board_missing_material_key": ("Desky bez materiálu pro řezný plán", check_board_missing_material_key),
    "profile_wrong_length_claim": ("Popis profilu tvrdí špatnou délku tyče", check_profile_wrong_length_claim),
    "orphaned_cfg_dily_ref": ("Produkt odkazuje na neexistující cfg_dily", check_orphaned_cfg_dily_ref),
    "missing_glb_file": ("cfg_dily odkazuje na chybějící .glb soubor", check_missing_glb_file),
    "duplicate_sku": ("Duplicitní SKU mezi aktivními produkty", check_duplicate_sku),
    "zero_weight_profile": ("Profil ve 3D scéně s nulovou hmotností", check_zero_weight_profile),
    "missing_dogus_price_coefficient": ("Kategorie s Dogus produkty bez cenového koeficientu", check_missing_dogus_price_coefficient),
    "admin_modal_missing_close": ("Modální okno v administraci bez zavíracího tlačítka", check_admin_modal_missing_close),
    "public_page_missing_close_link": ("Zákaznická detail stránka otevřená z dlaždice bez cesty zpět", check_public_page_missing_close_link),
    "dead_button": ("Tlačítko bez zapojení v JS", check_dead_button),
    "duplicate_html_id": ("Duplicitní HTML id na stránce", check_duplicate_html_id),
    "dangling_get_element_by_id": ("JS odkazuje na neexistující HTML id", check_dangling_get_element_by_id),
    "html_comment_stray_close": ("HTML komentář se předčasně uzavřel (zbytek je vidět na stránce)", check_html_comment_stray_close),
    "dangling_admin_tab_key": ("Kód odkazuje na neexistující záložku adminu (data-tab)", check_dangling_admin_tab_key),
    "broken_fetch_endpoint": ("JS volá API endpoint bez odpovídající backend route", check_broken_fetch_endpoint),
    "category_missing_meta_description": ("Viditelná kategorie bez meta popisu", check_category_missing_meta_description),
    "homepage_block_missing_image": ("Dlaždice homepage mozaiky bez obrázku", check_homepage_block_missing_image),
    "orphaned_gallery_items": ("Fotka/video ve fotobance bez existujícího vlastníka", check_orphaned_gallery_items),
    "duplicate_js_function": ("Duplicitně deklarovaná JS funkce", check_duplicate_js_function),
    "duplicate_py_function": ("Duplicitně deklarovaná Python funkce", check_duplicate_py_function),
    "dead_css_selector": ("CSS pravidlo pro neexistující id", check_dead_css_selector),
    "bare_except": ("Holé except: v kódu backendu", check_bare_except),
    "mutable_default_arg": ("Měnitelná výchozí hodnota argumentu funkce", check_mutable_default_arg),
    "admin_route_missing_permission": ("Admin route bez ověření oprávnění", check_admin_route_missing_permission),
    "auth_input_missing_name": ("Přihlašovací pole s autocomplete bez name=", check_auth_input_missing_name),
    "broken_static_image_src": ("Obrázek odkazuje na neexistující soubor", check_broken_static_image_src),
    "broken_static_asset_ref": ("Script/link/CSS url() odkazuje na neexistující soubor", check_broken_static_asset_ref),
    "dangling_onclick_function": ("onclick volá nikde nedefinovanou funkci", check_dangling_onclick_function),
    "duplicate_api_route": ("Duplicitně registrovaná backend route", check_duplicate_api_route),
    "requests_no_timeout": ("HTTP volání bez timeoutu", check_requests_no_timeout),
    "ssr_client_render_drift": ("SSR karta kategorie neodpovídá klientskému renderProducts()", check_ssr_client_render_drift),
    "blocking_alert_call": ("Blokující alert() na zákaznické stránce e-shopu", check_blocking_alert_call),
    "stale_admin_tab_reference": ("JS porovnává data-tab se záložkou, která po přejmenování už neexistuje", check_stale_admin_tab_reference),
    "missing_link_protocol": ("Odkaz v textu bez http(s):// - hrozí relativní URL", check_missing_link_protocol),
    "ssr_sidebar_tree_missing": ("Stránka se sidebarem bez SSR vyplnění stromu kategorií (bliká/skládá se menu)", check_ssr_sidebar_tree_missing),
    "mobile_layout_zero_width": ("Obsah stránky se na mobilu stlačí na nulovou šířku (prázdná stránka)", check_mobile_layout_zero_width),
    "email_link_from_request_host": ("E-mail obsahuje odkaz postavený z request.host_url místo APP_BASE_URL", check_email_link_from_request_host),
    "qa_registration_incomplete": ("Kontrola chybí v CHECKS/CHECK_CATEGORY/CHECK_ADDED", check_qa_registration_incomplete),
    "corner_side_missing_geo_faces": ("Rohová/boční spojka (corner_side) bez rozpoznaných montážních ploch (geo_faces)", check_corner_side_missing_geo_faces),
    "remeslo_backlink_domain_self_reference": ("Vizitky řemeslníků a jejich SEO backlink sdílí stejnou doménu", check_remeslo_backlink_domain_self_reference),
    "missing_voice_prompt_file": ("Hlasová výzva Moderátora bez vygenerovaného .wav souboru", check_missing_voice_prompt_file),
    "absurd_attach_pose": ("Naučená póza napojení posunutá o víc než 500 mm (vadné učení)", check_absurd_attach_pose),
    "direct_send_email_bypass": ("Přímé send_email() mimo schválenou pending-frontu e-mailů", check_direct_send_email_bypass),
    "storefront_brand_mention": ("Storefront text zmiňuje mateřskou firmu/projekt", check_storefront_brand_mention),
    "static_page_brand_leak": ("Statická stránka sdílená s anonymními doménami zmiňuje mateřskou firmu", check_static_page_brand_leak),
    "miniweb_text_brand_leak": ("Text mini-shopu zmiňuje značku/dodavatele (API ho veřejně skrývá)", check_miniweb_text_brand_leak),
    "static_page_font_stale": ("Statická stránka má pevně vložené jiné písmo, než je volba písma webu v adminu", check_static_page_font_stale),
    "storefront_identifier_leak": ("Storefront text obsahuje možný identifikátor sdílený s hlavním webem", check_storefront_identifier_leak),
    "storefront_nonsense_door_phrasing": ("Storefront/kategorie text: dveře 'se otevírají do X mm' místo výšky otvoru", check_storefront_nonsense_door_phrasing),
    "storefront_full_height_claim": ("Storefront/kategorie text tvrdí regál/vestavbu do plné výšky prostoru", check_storefront_full_height_claim),
    "storefront_rack_height_exceeds_door": ("Storefront text zmiňuje výšku regálu vyšší než skutečný zadní nakládací otvor", check_storefront_rack_height_exceeds_door),
    "order_payment_received_mismatch": ("Přijatá platba objednávky neodpovídá součtu vystavených VDD (NET místo GROSS?)", check_order_payment_received_mismatch),
    "product_duplicate_unclassified_table": ("Tabulka odkazující na produkt není zařazená v duplikaci produktu (kopie by ji tiše vynechala)", check_product_duplicate_unclassified_table),
    "board_price_not_per_m2": ("Deska nemá cenu za 1 m² (starší stav: za celou tabuli) nebo jí chybí formát tabule", check_board_price_not_per_m2),
    "product_slug_not_from_name": ("Veřejný produkt má adresu (URL), která neodpovídá názvu, obsahuje interní název nebo chybí", check_product_slug_not_from_name),
    "flung_shape_part": ("Díl vlastního tvaru/sestavy leží daleko od zbytku (špatně umístěný importem/generátorem)", check_flung_shape_part),
    "lic_peers_neni_spoj": ("Dvojice profilů uložená jako spoj (lic_peers) nesplňuje definici spoje (dotyk hranou, nedotýkají se)", check_lic_peers_not_a_joint),
}

# Robert 2026-08-10 ("navrhy na doplneni oddelme od navrhu na opravy" +
# "budou 2 scripty ktere bude admin spoustet a zastavovat nezavisle" +
# "script na hledani chyb ma prednost") - dve nezavisle spustitelne
# skupiny v adminu (viz api/qa_audit.py ?category=, webapp/admin.html
# dva samostatne panely): "doplnit" = chybi hodnota (ma vzdy primy
# "otevrit editor" akci), "opravit" = spatna/rozbita hodnota NEBO
# kodovy bug (nekdy ma primou akci - napr. profil s chybnym popisem
# delky otevre skladovou kartu, jindy jen "nahlasit jako prioritu",
# viz QA_AUDIT_ACTIONS v admin.html).
CHECK_CATEGORY = {
    "ssr_slug_route_without_visibility_filter": "opravit",
    "assembly_rail_above_leg_top": "opravit",
    "assembly_part_missing_transform": "opravit",
    "k_kod_v_zakaznickem_textu": "opravit",
    "interni_poznamka_v_zakaznickem_textu": "opravit",
    "karta_nazvana_jako_jedna_sestava": "opravit",
    "missing_price": "doplnit",
    "missing_image": "doplnit",
    "missing_description": "doplnit",
    "board_missing_material_key": "doplnit",
    "missing_dogus_price_coefficient": "doplnit",
    "zero_weight_profile": "doplnit",
    "category_missing_meta_description": "doplnit",
    "homepage_block_missing_image": "doplnit",
    "profile_wrong_length_claim": "opravit",
    "orphaned_cfg_dily_ref": "opravit",
    "missing_glb_file": "opravit",
    "duplicate_sku": "opravit",
    "admin_modal_missing_close": "opravit",
    "public_page_missing_close_link": "opravit",
    "dead_button": "opravit",
    "duplicate_html_id": "opravit",
    "dangling_get_element_by_id": "opravit",
    "html_comment_stray_close": "opravit",
    "dangling_admin_tab_key": "opravit",
    "broken_fetch_endpoint": "opravit",
    "orphaned_gallery_items": "opravit",
    "duplicate_js_function": "opravit",
    "duplicate_py_function": "opravit",
    "dead_css_selector": "opravit",
    "bare_except": "opravit",
    "mutable_default_arg": "opravit",
    "admin_route_missing_permission": "opravit",
    "auth_input_missing_name": "opravit",
    "broken_static_image_src": "opravit",
    "broken_static_asset_ref": "opravit",
    "dangling_onclick_function": "opravit",
    "duplicate_api_route": "opravit",
    "requests_no_timeout": "opravit",
    "ssr_client_render_drift": "opravit",
    "blocking_alert_call": "opravit",
    "stale_admin_tab_reference": "opravit",
    "missing_link_protocol": "opravit",
    "ssr_sidebar_tree_missing": "opravit",
    "mobile_layout_zero_width": "opravit",
    "email_link_from_request_host": "opravit",
    "qa_registration_incomplete": "opravit",
    "corner_side_missing_geo_faces": "doplnit",
    "remeslo_backlink_domain_self_reference": "opravit",
    "missing_voice_prompt_file": "doplnit",
    "absurd_attach_pose": "opravit",
    "direct_send_email_bypass": "opravit",
    "storefront_brand_mention": "opravit",
    "static_page_brand_leak": "opravit",
    "miniweb_text_brand_leak": "opravit",
    "static_page_font_stale": "opravit",
    "storefront_identifier_leak": "opravit",
    "storefront_nonsense_door_phrasing": "opravit",
    "storefront_full_height_claim": "opravit",
    "storefront_rack_height_exceeds_door": "opravit",
    "order_payment_received_mismatch": "opravit",
    "product_duplicate_unclassified_table": "opravit",
    "board_price_not_per_m2": "opravit",
    "product_slug_not_from_name": "opravit",
    "flung_shape_part": "opravit",
    "lic_peers_neni_spoj": "opravit",
}

# Robert 2026-08-11 ("chci aby se logovalo datum přidání každého nového
# typu kontroly") - datum, kdy KAZDA jednotliva kontrola (ne jednotlivy
# nalez, ten zadnou historii nema, viz komentar u run_checks nize) byla
# poprve zapsana do teto sady. Zpetne dohledano z git historie
# (`git log -S"def check_<jmeno>("  -- api/qa_checks.py`, prvni commit
# kde se dana funkce objevila) pro vsech 35 kontrol existujicich k
# 2026-08-11 - odtud presna data 2026-08-09/10/11 u starsich kontrol
# nize, ne jen "dnes". Zobrazuje se v adminu (QA Dashboard, viz
# api/qa_audit.py) vedle popisku kazde kontroly.
#
# POVINNE u KAZDE nove kontroly pridane podle pravidla #9 (WORKFLOW.md -
# "kazdy bug -> nova kontrola"): pridat sem zaznam se dnesnim datem ve
# stejnem commitu, jako se prida samotna kontrolni funkce + CHECKS/
# CHECK_CATEGORY zaznamy - jinak skonci jako missing_dogus_price_
# coefficient driv (chybela v CHECK_CATEGORY, viz commit cba4a0d) -
# nekompletni registrace kontroly, kterou nikdo hned nezvedne.
CHECK_ADDED = {
    "ssr_slug_route_without_visibility_filter": "2026-09-12",
    "assembly_rail_above_leg_top": "2026-09-05",
    "assembly_part_missing_transform": "2026-09-05",
    "k_kod_v_zakaznickem_textu": "2026-09-11",
    "interni_poznamka_v_zakaznickem_textu": "2026-09-12",
    "karta_nazvana_jako_jedna_sestava": "2026-09-11",
    "missing_price": "2026-08-09",
    "missing_image": "2026-08-09",
    "missing_description": "2026-08-09",
    "board_missing_material_key": "2026-08-09",
    "profile_wrong_length_claim": "2026-08-09",
    "orphaned_cfg_dily_ref": "2026-08-09",
    "missing_glb_file": "2026-08-09",
    "duplicate_sku": "2026-08-09",
    "zero_weight_profile": "2026-08-09",
    "missing_dogus_price_coefficient": "2026-08-10",
    "admin_modal_missing_close": "2026-08-10",
    "public_page_missing_close_link": "2026-08-10",
    "dead_button": "2026-08-10",
    "duplicate_html_id": "2026-08-10",
    "dangling_get_element_by_id": "2026-08-10",
    "html_comment_stray_close": "2026-10-01",
    "dangling_admin_tab_key": "2026-09-03",
    "broken_fetch_endpoint": "2026-08-10",
    "category_missing_meta_description": "2026-08-10",
    "homepage_block_missing_image": "2026-08-10",
    "orphaned_gallery_items": "2026-08-10",
    "duplicate_js_function": "2026-08-10",
    "duplicate_py_function": "2026-08-10",
    "dead_css_selector": "2026-08-10",
    "bare_except": "2026-08-10",
    "mutable_default_arg": "2026-08-10",
    "admin_route_missing_permission": "2026-08-10",
    "broken_static_image_src": "2026-08-10",
    "broken_static_asset_ref": "2026-09-02",
    "dangling_onclick_function": "2026-08-10",
    "duplicate_api_route": "2026-08-10",
    "requests_no_timeout": "2026-08-10",
    "ssr_client_render_drift": "2026-08-10",
    "blocking_alert_call": "2026-08-10",
    "stale_admin_tab_reference": "2026-08-11",
    "missing_link_protocol": "2026-08-11",
    "ssr_sidebar_tree_missing": "2026-08-11",
    "mobile_layout_zero_width": "2026-08-11",
    "email_link_from_request_host": "2026-08-11",
    "qa_registration_incomplete": "2026-08-11",
    "auth_input_missing_name": "2026-08-11",
    "corner_side_missing_geo_faces": "2026-08-18",
    "remeslo_backlink_domain_self_reference": "2026-08-19",
    "missing_voice_prompt_file": "2026-08-19",
    "absurd_attach_pose": "2026-08-19",
    "direct_send_email_bypass": "2026-08-26",
    "storefront_brand_mention": "2026-08-30",
    "static_page_brand_leak": "2026-10-01",
    "miniweb_text_brand_leak": "2026-10-02",
    "static_page_font_stale": "2026-10-01",
    "storefront_identifier_leak": "2026-08-30",
    "storefront_nonsense_door_phrasing": "2026-08-30",
    "storefront_full_height_claim": "2026-08-30",
    "storefront_rack_height_exceeds_door": "2026-08-30",
    "order_payment_received_mismatch": "2026-09-29",
    "product_duplicate_unclassified_table": "2026-09-30",
    "board_price_not_per_m2": "2026-10-01",
    "product_slug_not_from_name": "2026-10-01",
    "flung_shape_part": "2026-10-01",
    "lic_peers_neni_spoj": "2026-10-02",
}


def run_checks(cur, only=None):
    """only: volitelny seznam klicu z CHECKS (None = vsechny). Vraci dict
    {key: {"label":..., "rows":[(id,name,detail), ...]}} - stejny tvar,
    jaky uz pouziva scripts/qa_product_audit.py --json."""
    keys = only if only is not None else list(CHECKS.keys())
    results = {}
    for key in keys:
        label, fn = CHECKS[key]
        try:
            rows = fn(cur)
        except Exception as e:
            # bot23 2026-08-18: jedna rozbita kontrola (napr. zmena
            # schematu, vlastni bug) driv shodila CELY /api/admin/qa-audit
            # (vyjimka nezachycena, 500 na cely endpoint) - admin pak
            # nevidel VUBEC NIC, ne jen tu jednu rozbitou kontrolu. Nekolik
            # kontrol uz mela vlastni try/except (vzor existoval), jen ne
            # na urovni dispatche - sjednoceno sem, ať jedna rozbita
            # kontrola degraduje jen sama sebe, ne cely panel.
            print(f"[qa_checks] kontrola '{key}' selhala: {e}")
            results[key] = {"label": label, "rows": [], "error": str(e)}
            continue
        results[key] = {"label": label, "rows": rows}
    return results
