#!/usr/bin/env python3
"""
Male API pro konfigurator 3D objektu - cte katalog dilu z MySQL (tabulka cfg_dily)
a servíruje ho jako JSON. GLB soubory se servíruji staticky primo pres nginx
(location /katalog/), tohle API resi jen strukturovana data.
"""
import os
import re
import html as html_lib
import json
import functools
import random
import secrets
import subprocess
import tempfile
import hashlib
import threading
import unicodedata
import urllib.request
from urllib.parse import quote, unquote
import time
from collections import defaultdict, deque
import smtplib
import ssl
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import pymysql
import pymysql.cursors
from flask import Flask, jsonify, request, session, Response, redirect, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
try:
    import fbx_convert  # noqa: F401 - FBX->GLB prevod pro admin upload (bot1, 2026-07-27)
except ImportError:
    fbx_convert = None  # chybejici zavislosti (assimp_py/trimesh) nesmi shodit celou appku
try:
    import step_convert  # noqa: F401 - STEP->GLB prevod (izolovany subprocess, bot1, 2026-07-27)
except ImportError:
    step_convert = None  # tenhle modul sam o sobe nema tezke zavislosti, ale pro jistotu stejny vzor jako fbx_convert

# Bezpecnost (bot11, 2026-08-18, audit AUDIT_SYSTEM_2026-08-18.md nalez
# 1.1): drivejsi hardcoded fallback hesla/uzivatele/DB jmena v kodu -
# navic ZASTARALE, uz neodpovidaly skutecnym produkcnim hodnotam v
# api/.env, takze by pri chybejici env promenne appka tise sahla po
# spatnych/starych credentials misto zjevneho selhani. `EnvironmentFile=
# /opt/konfigurator/api/.env` v konfigurator.service zaruci, ze env
# promenne jsou v produkci VZDY nastavene pred startem gunicornu -
# chybejici hodnota tak znamena skutecne poskozenou konfiguraci, ne
# neco, co ma smysl tise nahradit vychozi hodnotou.
def _require_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Chybí povinná env proměnná {name} (viz api/.env).")
    return value


DB_HOST = _require_env("DB_HOST")
DB_PORT = int(_require_env("DB_PORT"))
DB_USER = _require_env("DB_USER")
DB_PASSWORD = _require_env("DB_PASSWORD")
DB_NAME = _require_env("DB_NAME")

UPLOAD_DIR = os.environ.get("CONTENT_UPLOAD_DIR", "/opt/konfigurator/webapp/content-files")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# FBX modely novych profilu (bot1, 2026-07-27) - Robert nahrava rucne pres
# admin (Ceny profilu), ulozeny per-profil pod nazvem <id>.fbx. Slouzi jako
# vstup pro pozdejsi prevod na GLB (viz convert_fbx_catalog.py) - tenhle
# endpoint sam o sobe zadny prevod nedela, jen bezpecne uklada soubor a
# eviduje vazbu na cfg_dily.id.
FBX_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "profil_fbx")
os.makedirs(FBX_UPLOAD_DIR, exist_ok=True)

# Slozka se skutecnymi GLB soubory pouzivanymi primo ve 3D scene (bot1,
# 2026-07-27) - stejna slozka, ve ktere uz lezi Object_1.glb/Object_7.glb
# atd. (nginx location /katalog/ - viz komentar v hlavicce souboru).
KATALOG_GLB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp", "katalog")

# Auta - karoserie (Robert 2026-08-05: "nasledne vsechny nahrajes do 3D
# sceny, Leve menu, separatni strom Auta rozdeleno podle znacek a
# modelu"). Zdrojove FBX v UPLOAD_DIR (mirror FBX_UPLOAD_DIR/
# PRODUCT_FBX_UPLOAD_DIR vyse), prevedene GLB primo do podslozky
# KATALOG_GLB_DIR/auta/ - nginx /katalog/ alias funguje rekurzivne pro
# libovolnou podslozku, zadna zmena nginx configu netreba.
CAR_FBX_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "car_fbx")
os.makedirs(CAR_FBX_UPLOAD_DIR, exist_ok=True)
CAR_GLB_DIR = os.path.join(KATALOG_GLB_DIR, "auta")
os.makedirs(CAR_GLB_DIR, exist_ok=True)

# Sdileny disk (drive.py) - stejna cesta jako DRIVE_FILES_DIR tam, ale
# definovana i tady, aby zrcadleni jednotlivych tvaru (_mirror_shape_to_drive
# nize) nemuselo importovat z drive.py (ten naopak importuje z app.py -
# import v opacnem smeru pri startu modulu by byl kruhovy).
DRIVE_FILES_DIR = os.path.join(os.environ.get("PRIVATE_FILES_DIR", "/opt/konfigurator/private-files"), "shared-drive")
os.makedirs(DRIVE_FILES_DIR, exist_ok=True)

# --- E-mail (zapomenute heslo) - Gmail SMTP relay uctu mandik@logiman.cz,
# app password vygenerovane v Google uctu (rozhodnuti 2026-07-23). Bez
# techto promennych appka reset-email jen zaloguje, neposle doopravdy. ---
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://80.211.210.103:8090")
# bot14, 2026-09-02 (bot15 nalez pres bot3): canonical/og:url/sitemap.xml/
# JSON-LD hlavniho e-shopu se stavely z request.host_url, ktery se meni
# podle toho, na jaky hostname pozadavek dorazil (puvodne vandrawee.cz vs.
# www.vandrawee.cz vs. IP vhost) - www varianta tak vypadala jako
# DUPLICITNI web se svym vlastnim canonical (kazda URL sama na sebe, ne
# na apex domenu). PUBLIC_BASE_URL je PEVNA verejna domena hlavniho
# e-shopu bez ohledu na to, odkud pozadavek prisel - pouziva se JEN ve
# funkcich specifickych pro hlavni e-shop (_product_page_response,
# _category_page_response, /robots.txt, /sitemap.xml, homepage-block/
# sidebar-block/panel stranky), NIKDY v _render_og_page() samotne (ta je
# sdilena i s mini-eshopy per model auta, viz car_storefronts.py - tam
# MUSI zustat host-aware, jinak by kazdy storefront tvrdil, ze je hlavni
# web). bot9, 2026-09-06: vandrawee.cz DNS zrusena, hlavni domena je ted
# autovestavby.logiman.cz (vandrawee.cz uz patri samostatnemu projektu
# /opt/vandrawee, viz AGENTS_LOG.md). POZOR: novy vhost
# /etc/nginx/sites-available/logiman-autovestavby NEMA zatim www->non-www
# presmerovani (na rozdil od puvodniho vandrawee vhostu) - nekontrolovano,
# jestli je potreba.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://autovestavby.logiman.cz")
RESET_TOKEN_TTL_MIN = 60
EMAIL_VERIFICATION_TTL_MIN = 60 * 24  # 24 hodin (bot13, 2026-08-23, bod 1 bezpecnostniho review Modulu 11)
# Fotoapka (capture.html) bezi na vlastnim HTTPS portu (8091, viz komentar
# v capture.html - getUserMedia vyzaduje secure context) - magic-login
# odkaz musi mirit sem, ne na APP_BASE_URL (ten je http:// 8090 admin/shop).
CAPTURE_BASE_URL = os.environ.get("CAPTURE_BASE_URL", "https://80-211-210-103.sslip.io:8091")


def _get_smtp_config():
    """
    Robert 2026-08-24: SMTP nastaveni editovatelne v adminu (Nastaveni ->
    Obecne), bez nutnosti sahat do .env a restartovat sluzbu. Ulozeny
    override v app_settings (klic 'smtp_config', JSON) ma prednost pred
    hodnotami z .env (SMTP_HOST/PORT/USER/PASSWORD/FROM konstanty vyse) -
    ty zustavaji jako vychozi/fallback, kdyz jeste zadny override neni
    ulozeny. Cte se PRI KAZDEM odeslani (ne jednou pri startu), takze
    zmena v adminu je ucinna okamzite.
    """
    cfg = {
        "host": SMTP_HOST, "port": SMTP_PORT, "user": SMTP_USER,
        "password": SMTP_PASSWORD, "from": SMTP_FROM,
    }
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            override = get_setting(cur, "smtp_config")
    finally:
        conn.close()
    if override:
        try:
            data = json.loads(override)
        except (TypeError, ValueError):
            data = {}
        if data.get("host"):
            cfg["host"] = data["host"]
        if data.get("port"):
            cfg["port"] = int(data["port"])
        if data.get("user"):
            cfg["user"] = data["user"]
        if data.get("password"):
            cfg["password"] = data["password"]
        if data.get("from"):
            cfg["from"] = data["from"]
    return cfg


def send_email(to_email, subject, body_text, cc_email=None, attachments=None):
    """Rozsireno v9 (bot3, 2026-07-25 - "nachystej emailoveho klienta ...")
    o volitelne `cc_email` a `attachments` (seznam trojic
    (filename, bytes, mime_subtype), napr. [("faktura_26070001.pdf", pdf_bytes, "pdf")]) -
    pouziva api/emails.py pro prilohu PDF dokladu k e-mailu. ZPETNE
    KOMPATIBILNI - puvodni volani se 3 pozicnimi argumenty (zapomenute
    heslo, potvrzeni objednavky, zmena stavu - viz auth_forgot_password()
    vyse a orders.py) funguji beze zmeny.

    Robert 2026-07-26 (naslano na testovaci objednavky s vygenerovanymi
    e-maily obsahujicimi ceskou diakritiku primo v adrese, napr.
    "testgen.karel.novotný@example.cz"): smtplib pri odesilani prikazu
    RCPT TO/MAIL FROM vyzaduje cistou ASCII adresu (bez SMTPUTF8
    rozsireni, ktere tento SMTP relay nenabizi) - jinak spadne s
    kryptickym `UnicodeEncodeError`. send_and_log() (api/emails.py) uz
    kazdou vyjimku odsud chyta a uklada do shop_emails.error_message,
    takze appka nepadala, jen se ukladala nesrozumitelna hlaska. Tady
    validace PRED pokusem o odeslani, at je pripadna chyba citelna a
    jasne odlisitelna od realneho vypadku SMTP serveru."""
    for label, addr in (("Příjemce", to_email), ("Kopie (Cc)", cc_email)):
        if addr and not addr.isascii():
            raise ValueError(f"{label} obsahuje nepovolené znaky (e-mailová adresa musí být čistě ASCII): {addr}")
    # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02, KROK 2): isascii()
    # vyse CR/LF (0x0D/0x0A) nezachyti - jsou to platne ASCII znaky.
    # Bez tehle kontroly by \r\n v adrese/predmetu mohlo vlozit dalsi
    # SMTP hlavicku (header injection). Zadna zivá cesta v tomhle
    # repozitari dnes nevede od anonymniho vstupu do subjectu/adresy
    # neosetrena (overeno pri revizi), ale kontrola tu ma zustat jako
    # obecna pojistka pro KAZDE budouci volani.
    for label, value in (("Příjemce", to_email), ("Kopie (Cc)", cc_email), ("Předmět", subject)):
        if value and ("\r" in value or "\n" in value):
            raise ValueError(f"{label} obsahuje nepovolené znaky (nový řádek).")
    smtp = _get_smtp_config()
    if not smtp["host"]:
        print(f"[email disabled - no SMTP_HOST] to={to_email} subject={subject}\n{body_text}")
        return
    if attachments:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        for filename, data, subtype in attachments:
            part = MIMEApplication(data, _subtype=subtype)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(part)
    else:
        msg = MIMEText(body_text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp["from"]
    msg["To"] = to_email
    recipients = [to_email]
    if cc_email:
        msg["Cc"] = cc_email
        # vic adres v Cc (napr. "a@x.cz, b@y.cz"): SMTP potrebuje kazdou adresu zvlast (bot5, 2026-10-06, e-maily ucetni)
        recipients.extend(a.strip() for a in re.split(r"[;,]", cc_email) if a.strip())
    server = smtplib.SMTP(smtp["host"], smtp["port"], timeout=15)
    try:
        server.starttls(context=ssl.create_default_context())
        server.login(smtp["user"], smtp["password"])
        server.sendmail(smtp["from"], recipients, msg.as_string())
    finally:
        server.quit()

# --- AI vrstva (popis -> sestava z katalogu) ---
# Interni nazev pro tuto AI vrstvu: "3Dbot" (jen pro nas, v kodu/komentarich -
# uzivatel v appce vidi jen "AI modul").
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
AI_MAX_STEPS = 40
PROFILE_MAX_LENGTH_MM = 3000
CUSTOM_SHAPE_MAX_PARTS = 1000
# Robert 2026-09-06 (chyba pri ukladani sestavy 189 pres UI, "Vyber obsahuje
# prilis mnoho dilu (max 60)"): produktove SESTAVY (product_assemblies) jsou
# koncepcne jine nez znovupouzitelne "vlastni tvary" (custom_shapes, odkud
# limit 60 pochazi) - jsou to cele nakonfigurovane sestavy pro celou lozmou
# plochu vozidla a BEZNE maji desitky az stovky dilu (zjisteno v DB: 123
# existujicich sestav, max 145 dilu, prumer pres 100 - vsechny vznikly primym
# DB zapisem skriptem, takze tenhle limit u nich nikdy nebyl vynucen). Vlastni,
# vyssi limit jen pro sestavy - PUVODNE custom_shapes limit zustaval 60
# zamerne, na rozdil od PRODUCT_ASSEMBLY_MAX_PARTS.
#
# ZMENENO 2026-09-15 (Robert pres bot3): "ukladani do vlastnich tvaru ve
# scene ma limit 60 dilu zvednout na 1000 dilu" - puvodni zduvodneni vyse
# (60 = male znovupouzitelne kusy, ne cele sestavy) uz NEPLATI jako aktualni
# pravidlo, jen jako historie DUVODU puvodni hodnoty. Overeno pred zmenou:
# `custom_shapes.data` je MySQL JSON sloupec, 1000 dilu (part_id/position/
# quaternion/scale/pripadne color) je radove stovky KB serializovaneho JSON -
# hluboko pod jakymkoli DB/packet limitem, zadne riziko tam. Skutecne
# neoverene je zivy VYKON ve scene.html pri vlozeni tak velkeho vlastniho
# tvaru (connector/spoj-matching a dalsi O(n)/O(n^2) prochazky pres `placed`
# nebyly testovany nad 1000 dily najednou) - nezastavuje to tuhle zmenu
# (Robert limit vyslovne chtel), jen to poznamenavam pro pripad, ze bude
# vkladani znatelne pomalejsi u fakt velkych vlastnich tvaru.
PRODUCT_ASSEMBLY_MAX_PARTS = 300
# Robert 2026-07-24: "potrebujeme pro 3D bota rozsireni o volne pozicovani v prostoru bez spoje" - hranice pro 'position_mm' (viz AI_BUILD_TOOL nize), aby AI nemohla polozit dil nesmyslne daleko od zbytku sestavy.
AI_POSITION_BOUND_MM = 5000

# Limity a podminky potvrzene Robertem (VLASTNOSTI_PROFILU.md), ktere 3Dbot
# musi respektovat - a ktere se navic tvrde vynucuji nize v ai_generate(),
# takze i kdyby se AI splichla, nekompatibilni spoj se v planu nikdy neobjevi.
# Klic je "prurezAxprurezB" (mensi rozmer x vetsi rozmer, viz cross_key()).
# Kazdy profil jde spojit sam se sebou + ctvercovy profil navic se svym
# "dvojnasobnym" protejskem ve stejne drazkove rodine (sloupek + pricka/ram).
PROFILE_JOIN_PAIRS = {
    frozenset({"10x40"}),
    frozenset({"20x20"}),
    frozenset({"20x20", "20x40"}),
    frozenset({"20x40"}),
    frozenset({"20x80"}),
    frozenset({"30x30"}),
    frozenset({"30x30", "30x60"}),
    frozenset({"30x60"}),
    frozenset({"35x35"}),
    frozenset({"40x40"}),
    frozenset({"40x40", "40x80"}),
    frozenset({"40x80"}),
    frozenset({"45x45"}),
    frozenset({"45x45", "45x90"}),
    frozenset({"45x90"}),
}


def cross_key(cross_section_mm):
    """'prurezAxprurezB' retezec z [a,b] rozmeru, napr. [20.0, 40.0] -> '20x40'."""
    if not cross_section_mm or cross_section_mm[0] is None or cross_section_mm[1] is None:
        return None
    a, b = cross_section_mm
    return f"{int(round(a))}x{int(round(b))}"

app = Flask(__name__)
# Bezpecnost (bot11, 2026-08-18, audit AUDIT_SYSTEM_2026-08-18.md nalez
# 1.2): drivejsi fallback "dev-only-insecure-key-change-me" byl VEREJNE
# znamy retezec primo v kodu - pri chybejici env promenne by session
# cookies byly podepsane timhle znamym klicem a utocnik by si mohl
# padelat libovolnou session (vc. role=admin). `.env` uz ma skutecnou
# hodnotu nastavenou, fail-fast misto ticheho slabeho fallbacku.
app.secret_key = _require_env("FLASK_SECRET_KEY")
# Cely konfigurator (3D scena i admin backend) je ted za prihlasenim
# (rozhodnuti 2026-07-23 - "kategorie/strom nad 3D scenou, prihlaseni
# managera/uzivatele aby se dostal do 3D sceny"). SESSION_COOKIE_SECURE
# (bezpecnostni nalez, bot3/revize kodu 2026-09-02, KROK 2): puvodni
# komentar "zatim bez HTTPS" byl zastaraly - hlavni domena (puvodne
# vandrawee.cz, od 2026-09-06 autovestavby.logiman.cz)/remeslnik.pro/
# storefronty uz bezi cistě na HTTPS (http->https redirect + HSTS,
# nasazeno bot15). Bez Secure by cookie sla poslat i pri libovolnem
# downgrade na http (sslstrip-styl MITM). IP vhost 75.119.132.164:8090
# zustava jen pro QA/health (HTTP), login tam po tehle zmene prestane
# fungovat - zamer, ne regrese.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
)


# QA bezpecnostni nalez (2026-09-05): chybely zakladni bezpecnostni
# hlavicky. Pokryva jen odpovedi, ktere jdou pres Flask (proxy_pass na
# konfigurator_api) - staticke soubory servirovane primo nginxem
# (webapp/, content-files/, scene.html a spol.) touhle zmenou hlavicky
# neziskaji, to by chtelo doplnit i do nginx configu (mimo rozsah - neni
# to verzovany kod tohoto repa). HSTS jen na HTTPS vhostech (podle
# X-Forwarded-Proto, nastavovaneho nginxem) - IP vhost 75.119.132.164:8090
# zustava zamerne cistym HTTP (QA/health, viz komentar u SESSION_COOKIE_
# SECURE vyse).
#
# Permissions-Policy (2026-09-05, doplneno po revizi bot3): plosny
# fix_hint z QA (`geolocation=(), microphone=(), camera=()`) by appku
# rozbil - aktivne se pouziva kamera/mikrofon (remeslo-hlas.js,
# capture.html, scene.html, nabidka-online.html, product.html) A
# geolokace (capture.html - navigator.geolocation.watchPosition/
# getCurrentPosition, fleet GPS tracking). Misto uplneho zakazu proto
# `(self)` - povoli VLASTNIMU originu (kryje vsechny stavajici pouziti,
# vsechna same-origin), zakaze jen cizim iframe (obdoba X-Frame-Options
# SAMEORIGIN vyse).
#
# Content-Security-Policy jen jako Report-Only (nikdy nic neblokuje, jen
# by logovala do konzole prohlizece, kdyby byl nastaveny report-uri/
# report-to - zadny tu neni, takze cisty no-op pozorovaci krok) - appka
# ma hodne inline <script>/onclick v sablonach (`unsafe-inline` je nutny,
# skutecne vynucujici CSP s nonce/hash na kazdy inline blok je vetsi
# prace mimo rozsah tehle QA opravy.
@app.after_request
def _security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(self), microphone=(self), camera=(self)")
    resp.headers.setdefault(
        "Content-Security-Policy-Report-Only",
        "default-src 'self' https:; script-src 'self' 'unsafe-inline' https:; style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https:; frame-ancestors 'self'",
    )
    if request.headers.get("X-Forwarded-Proto") == "https":
        resp.headers.setdefault("Strict-Transport-Security", "max-age=15768000; includeSubDomains")
    return resp


class _PooledConn:
    """Proxy vraceny z get_conn() - .close() misto skutecneho zavreni jen
    odrolluje a vrati spojeni do fronty pro dalsi pozadavek. DB_HOST je
    vzdalena adresa (Forpsi Cloud DBaaS), kazde nove pymysql.connect()
    stoji ~130-140ms handshake navic k realnym dotazum - drzime 1 trvale
    spojeni na gunicorn worker (--workers 2, zadne --threads, tedy zadny
    soubezny pristup ke sdilenemu spojeni v ramci jednoho procesu)."""
    __slots__ = ("_real",)

    def __init__(self, real):
        object.__setattr__(self, "_real", real)

    def close(self):
        try:
            object.__getattribute__(self, "_real").rollback()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_real"), name)


# threading.local misto proste globalni promenne (Robert 2026-08-08: "kosik
# nam na konci odeslani obj usnul" - odesilani potvrzovaciho e-mailu bezelo
# SYNCHRONNE v ramci requestu na POST /api/orders, cekani na pomale/malo
# odezvne SMTP tak vypadalo jako "zamrznuti" kosiku, viz _send_order_emails_bg
# v orders.py). Aby sla e-mailova cast presunout do background threadu BEZ
# rizika sdileni jednoho pymysql spojeni mezi dvema thready soucasne (presne
# situace, ktere se puvodni komentar vyse snazil vyhnout), kazdy thread
# (hlavni gunicorn sync worker i kazdy background thread) ted dostane
# VLASTNI spojeni - beze zmeny chovani pro puvodni jednothreadovy pripad
# (stale 1 trvale spojeni na thread, zadne navic pripojovani na kazdy request).
_pooled_conn_local = threading.local()


def get_conn():
    real = getattr(_pooled_conn_local, "conn", None)
    if real is not None:
        try:
            real.ping(reconnect=True)
            return _PooledConn(real)
        except Exception:
            try:
                real.close()
            except Exception:
                pass
            real = None
    real = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        # 2026-08-12: vzdalene spojeni (Forpsi Cloud DBaaS) obcas zdrhne
        # uprostred requestu a cteni ze socketu (napr. rollback() v
        # _PooledConn.close()) bez timeoutu viselo AZ DO gunicorn
        # --timeout 60, kdy obe workery najednou spadly a cely web byl tu
        # dobu nedostupny (Katalog dilu zamrzly na "Nacitam katalog...").
        # Timeouty tady zajisti, ze mrtve spojeni selze rychle a get_conn()
        # ho pri dalsim pozadavku proste znovu navaze.
        connect_timeout=10, read_timeout=25, write_timeout=25,
    )
    _pooled_conn_local.conn = real
    return _PooledConn(real)


@app.teardown_request
def _teardown_pooled_conn(exc):
    """Pojistka pro pripad, ze endpoint zapomene zavolat conn.close()
    (rollback) na vlastnim spojeni z get_conn() - napr. kdyz vyjimka
    proletí mimo try/finally driv, nez se ke conn.close() vubec dostane.
    Bez tohohle by nedokoncena transakce zustala viset na sdilenem
    per-thread spojeni az do dalsiho requestu na stejnem threadu."""
    real = getattr(_pooled_conn_local, "conn", None)
    if real is not None:
        try:
            real.rollback()
        except Exception:
            pass


# --- Stránkování (Robert 2026-07-26: "u všech přehledových tabulek,
# chybí nabídka stránkování a po kolika") - sdíleny vzor pro vsechny
# admin prehledove seznamy (produkty, zakaznici, objednavky, dodavatele,
# nakupni objednavky, doklady, e-maily, galerie, podpora, audit log,
# sestava k objednani, skladove pohyby, uzivatele).
#
# Kontrakt: ?page=1 (1-based), ?page_size=25|50|100|250. Kdyz endpoint
# slouzi i verejnemu eshopu (napr. GET /api/shop/products), stranci se
# JEN pokud je page_size v query explicitne poslan - jinak (stary
# frontend/eshop) se chova jako drive, vrati vsechno bez LIMIT/OFFSET,
# aby se nic nerozbilo.
PAGE_SIZE_CHOICES = (25, 50, 100, 250)
PAGE_SIZE_DEFAULT = 50


def get_pagination_args(default_page_size=None):
    """Vrati (page, page_size) z query stringu. page_size=None znamena
    "nestrankovat" (volajici pak LIMIT/OFFSET vubec neaplikuje) - pouzito
    u endpointu sdilenych s verejnym eshopem. Kdyz default_page_size je
    zadano, pouzije se misto None (endpointy jen pro admin, kde vzdy
    strankujeme)."""
    page = request.args.get("page", type=int) or 1
    if page < 1:
        page = 1
    raw_size = request.args.get("page_size", type=int)
    if raw_size is None:
        page_size = default_page_size
    else:
        page_size = min(max(raw_size, 1), 250)
    return page, page_size


def paginated_query(cur, base_sql, where_sql, params, order_sql, page, page_size):
    """Spusti COUNT(*) + samotny SELECT s LIMIT/OFFSET (pokud je
    page_size zadano) a vrati (rows, total). base_sql je "SELECT ... FROM
    tabulka" bez WHERE/ORDER BY, where_sql uz obsahuje " WHERE ..." (nebo
    prazdny retezec), order_sql je " ORDER BY ..." (nebo prazdny)."""
    if page_size:
        count_sql = "SELECT COUNT(*) AS c FROM (" + base_sql + where_sql + ") _cnt"
        cur.execute(count_sql, params)
        total = cur.fetchone()["c"]
        cur.execute(base_sql + where_sql + order_sql + " LIMIT %s OFFSET %s",
                    params + [page_size, (page - 1) * page_size])
        rows = cur.fetchall()
    else:
        cur.execute(base_sql + where_sql + order_sql, params)
        rows = cur.fetchall()
        total = len(rows)
    return rows, total


# --- Audit log (Robert 2026-07-25: "aplikuj v našem projektu všechny
# funkce jako má skladapp" -> upresneno na "Audit log a správa
# uživatelů" z nabidnutych oblasti). Jednoduchy zapis kdo/co/kdy zmenil -
# volano po uspesnych admin mutacich (kategorie, produkty, sklad. pohyby,
# uzivatele). Vlastni kratke spojeni, aby se nemusela protahovat
# transakce hlavni operace kvuli logovani.
def log_audit(user_id, action, entity_type, entity_id=None, detail=None):
    # detail je TEXT sloupec - dict/list prevest na JSON, jinak pymysql spadne
    # AZ PO commitu hlavni operace (bot4 2026-09-28: tlacitko "pouzit pro
    # render" ulozilo HDRI, ale hlasilo chybu a do audit_log se nic nezapsalo)
    if isinstance(detail, (dict, list)):
        detail = json.dumps(detail, ensure_ascii=False)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                (user_id, action, entity_type, entity_id, detail),
            )
        conn.commit()
    finally:
        conn.close()


# --- Party model, faze 2 (bot18, 2026-09-05, Robert pres bot3, navazuje
# na OFBiz srovnani "Za hranice objednavky" + schvaleny fazovany plan
# "Jedna identita, pet fazi"). `parties` je centralni identita, existujici
# tabulky (app_users/shop_customers/crm_leads/shop_orders, pripadne
# remeslo_craftsmen v jine DB) dostavaji `party_id` jako ROLI napojenou
# na tuhle identitu - zadna z nich se nepreklada ani neruси.
#
# DULEZITE OMEZENI (Robertovo vyslovne rozhodnuti, konkretni prijklad:
# jeho vlastni 2 ucty admin/remeslnik zustavaji ZAMERNE oddelene) - tahle
# funkce NIKDY nedohaduje, jestli dva ruzne app_users/existujici zaznamy
# patri stejne osobe (zadne fuzzy e-mail/jmeno+telefon slucovani pres
# ruzne ucty). Vola se VYHRADNE v okamziku vzniku NOVE identity (novy
# ucet, novy lead bez existujiciho customer_id) - tedy nikdy nejde o
# volbu "slouzit, nebo ne", jen o zalozeni jedne nove party. Propojeni
# mezi existujicimi radky (app_users<->shop_customers<->crm_leads) jde
# VYHRADNE po tvrde, uz existujici FK (shop_customers.user_id,
# crm_leads.customer_id) - viz volajici mista v customers.py/crm.py/
# orders.py.
def create_party(cur, party_type="osoba", full_name=None, primary_email=None,
                  primary_phone=None, ico=None, dic=None):
    cur.execute(
        "INSERT INTO parties (party_type, full_name, primary_email, primary_phone, ico, dic) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (party_type, full_name, primary_email, primary_phone, ico, dic),
    )
    return cur.lastrowid


# --- Hromadne akce - sdilene helpery (V11, bot3, 2026-07-26, viz
# NAVRH_HROMADNE_AKCE.md navrh bot4). Ostatni moduly (orders.py,
# customers.py, purchase_orders.py, gallery.py, support.py) je importuji
# stejnou konvenci jako get_conn/require_permission/log_audit/current_user.
def parse_bulk_ids(body):
    """Validace {"ids":[...]} z request body. Vraci (ids:list[int], error_response|None)."""
    ids = body.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return None, (jsonify({"error": "Vyber alespoň jednu položku."}), 400)
    try:
        return [int(i) for i in ids], None
    except (TypeError, ValueError):
        return None, (jsonify({"error": "Neplatná id."}), 400)


def bulk_update_fields(cur, table, ids, field_updates):
    """field_updates: {sloupec: hodnota}. Vraci pocet updatnutych radku.
    NEPOUZIVAT pro entity, kde zmena pole ma VEDLEJSI UCINKY (napr. zmena
    stavu objednavky odecita/vraci sklad, zmena stavu nakupni objednavky
    generuje pohyby) - tam se musi HROMADNE VOLAT existujici jednopolozkova
    funkce v cyklu, ne primy UPDATE."""
    if not field_updates:
        raise ValueError("bulk_update_fields: prazdne field_updates")
    placeholders = ",".join(["%s"] * len(ids))
    set_clause = ", ".join(f"{col}=%s" for col in field_updates)
    cur.execute(
        f"UPDATE {table} SET {set_clause} WHERE id IN ({placeholders})",
        list(field_updates.values()) + ids,
    )
    return cur.rowcount


def bulk_delete(cur, table, ids):
    placeholders = ",".join(["%s"] * len(ids))
    cur.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
    return cur.rowcount


# --- Pomocne funkce pro CSV import/export produktu a kategorii (Robert
# 2026-07-25: "aplikuj v našem projektu všechny funkce jako má skladapp"
# -> upresneno na "Import/export CSV"). Kategorie se v CSV identifikuji
# citelnou cestou "Elektro > Baterie a osvětlení > Baterie" misto
# numerickych ID, at je export/import prenositelny i mezi ruznymi
# databazemi. Import kategorii je JEN ADITIVNI (chybejici uzly cesty se
# vytvori, nic existujiciho se nemaze/nepresouva) - na rozdil od skladapp,
# kde re-upload stromu cely puvodni strom nahrazoval (rozhodnuti
# 2026-07-25: bezpecnejsi varianta bez rizika ztraty dat).
def resolve_category_path(cur, path_str, cache, created_ids=None):
    parts = [p.strip() for p in (path_str or "").split(">") if p.strip()]
    parent_id = None
    for part in parts:
        key = (parent_id, part.lower())
        if key in cache:
            parent_id = cache[key]
            continue
        cur.execute("SELECT id FROM content_categories WHERE parent_id <=> %s AND name=%s", (parent_id, part))
        row = cur.fetchone()
        if row:
            cid = row["id"]
        else:
            cur.execute("INSERT INTO content_categories (parent_id, name, sort_order) VALUES (%s,%s,0)", (parent_id, part))
            cid = cur.lastrowid
            if created_ids is not None:
                created_ids.append(cid)
        cache[key] = cid
        parent_id = cid
    return parent_id


def build_category_path_fn(categories):
    """categories = list radku se sloupci id/parent_id/name. Vrati funkci
    cat_id -> "A > B > C" (nebo "" pro None/neznamy id)."""
    by_id = {c["id"]: c for c in categories}

    def cat_path(cid):
        if cid is None or cid not in by_id:
            return ""
        parts = []
        current = cid
        seen = set()
        while current is not None and current not in seen:
            seen.add(current)
            c = by_id.get(current)
            if not c:
                break
            parts.insert(0, c["name"])
            current = c["parent_id"]
        return " > ".join(parts)

    return cat_path


# --- Rate limiting (bot11, 2026-08-18, audit AUDIT_SYSTEM_2026-08-18.md
# nalezy 1.3 a 1.5) ---
# Jednoduchy in-memory sliding-window limiter, klicovany podle IP (+
# volitelne dalsi rozliseni jako endpoint/e-mail). ZAMERNE bez
# externich zavislosti (Flask-Limiter/Redis) - projekt zatim nema
# sdilene uloziste mezi gunicorn workery, takze presne globalni limity
# by vyzadovaly novou infrastrukturu navic. In-memory per-worker limit
# je slabsi (2 workery = az 2x vice pokusu, nez cislo rika), ale
# smysluplne brzdi automatizovane zneuziti (brute-force na login,
# skriptovane zahlcovani support chatu) - lepsi nez zadna ochrana.
_rate_limit_buckets = defaultdict(deque)


def _client_ip():
    """X-Real-IP (nginx proxy_set_header, oba vhosty - nastaveno z
    $remote_addr) - NE X-Forwarded-For (bezpecnostni nalez, bot3
    2026-09-02): nginx do XFF hodnotu jen PRIDAVA ($proxy_add_x_forwarded_for),
    takze klient si libovolnou hodnotu na zacatek retezce podvrhne sam a
    obejde vsechny rate limity zalozene na _client_ip() (login,
    resend-verification, support, product_markups...). X-Real-IP je
    vzdy prepsana nginxem na skutecnou IP spojeni, klient ji ovlivnit
    nemuze. Orizuto na 64 znaku (product_markups.py uklada do
    varchar(64), STRICT SQL mode by jinak vratil 500)."""
    ip = request.headers.get("X-Real-IP") or request.remote_addr or "unknown"
    return ip.strip()[:64]


def _rate_limited(key, max_requests, window_seconds):
    """True = limit prekrocen (volajici endpoint ma pozadavek odmitnout
    s HTTP 429). Cisti stare zaznamy z bucketu prubezne (zadny
    samostatny cleanup cron potreba - pametova stopa je omezena poctem
    AKTIVNE zneuzivajicich klicu za posledni okno, ne delkou historie)."""
    now = time.time()
    bucket = _rate_limit_buckets[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= max_requests:
        return True
    bucket.append(now)
    return False


# --- Autentizace (session-based) ---
# Role: admin (instalater/majitel - vidi i backend spravu kategorii/uzivatelu/
# cen), manager a user (stejna prava ve 3D scene, jen oddelene ucty pro
# evidenci - rozhodnuti 2026-07-23).
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, role, active, theme_admin, theme_shop, party_id "
                "FROM app_users WHERE id=%s", (uid,)
            )
            return cur.fetchone()
    finally:
        conn.close()


def login_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user["active"]:
            return jsonify({"error": "Neprihlaseno.", "code": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user["active"]:
            return jsonify({"error": "Neprihlaseno.", "code": "unauthorized"}), 401
        if user["role"] != "admin":
            return jsonify({"error": "Tato akce vyzaduje roli admin.", "code": "forbidden"}), 403
        return fn(*args, **kwargs)
    return wrapper


def staff_required(fn):
    """Jako @login_required, ale navic vyzaduje STAFF roli (cokoli v
    PERMISSION_ROLES - definovano nize v souboru, proto lookup az za
    behu, ne na modulove urovni). Bezpecnostni nalez (bot3/revize kodu,
    2026-09-02): plain @login_required pousti i role='user' (bezny
    e-shop zakaznik z /api/auth/register - STEJNY login mechanismus/
    session jako staff), coz je spravne pro zakaznicke akce (vlastni
    kosik...), ale ne pro interni nastroje bez vlastniho
    PERMISSION_SECTIONS zaznamu (napr. tymovy chat na Dashboardu -
    videt "kazde prihlasene roli" myslelo STAFF roli, ne doslova
    kazdeho prihlaseneho). POZOR: 3D scena byla puvodne uvedena jako
    priklad OPACNE (customer-facing, ma zustat na login_required) - to
    uz NEPLATI, Robert 2026-09-03 rozhodl "zakaznikum pristup do sceny
    neumoznime, neni to vhodne" - scene-exkluzivni API (katalog,
    custom-shapes, product-assemblies, connector-flags/geo-faces/
    attach-*/uhelnik-pose, join-rules, catalog-thumbnail) je od te
    doby prevedeno na @staff_required (viz api/app.py, custom_shapes.py,
    product_assemblies.py)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user["active"]:
            return jsonify({"error": "Neprihlaseno.", "code": "unauthorized"}), 401
        if user["role"] not in PERMISSION_ROLES:
            return jsonify({"error": "Nemate opravneni k teto akci.", "code": "forbidden"}), 403
        return fn(*args, **kwargs)
    return wrapper


@app.get("/api/kontrola-scena")
def kontrolni_scena_gate():
    """Male, ORESANE (jen prohlizeni, zadne ukladani) mobil-friendly okenko
    pro kontrolu geometrie (Robert 2026-09-19: "vytvoříme vedlejší scénu
    malou ořezanou mobil úplně prázdnou... stejný princip jako je v online
    nabídce 3D, jednoduché prostředí"). Stejna staff-only politika jako
    scene_html_gate() nize (interni nastroj, ne zakaznicka stranka).

    Pod `/api/` prefixem ZAMERNE, ne jako vlastni top-level `/kontrola.html`
    soubor primo servirovany nginxem: `location = /scene.html` v nginx
    konfiguraci (viz komentar u scene_html_gate) je presne tenhle druh
    "gate pred statickym souborem" zavod, ktery vyzaduje novou `location`
    direktivu + `nginx -s reload` - sandbox tenhle reload blokuje (viz
    pamet feedback_sandbox_blocks_system_reload), takze bych zmenu nemohl
    sam nasadit. `location /api/` uz existuje a proxuje VSECHNY metody/
    typy odpovedi na Flask beze zmeny - staci se pod ni schovat, zadny
    infrastrukturni zasah navic."""
    user = current_user()
    if not user or not user["active"] or user["role"] not in PERMISSION_ROLES:
        next_path = request.full_path if request.query_string else request.path
        return redirect(f"/login.html?next={quote(next_path, safe='')}")
    webapp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp")
    return send_from_directory(webapp_dir, "kontrola.html")


KONTROLA_NAVRHY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "private-files", "kontrola-navrhy")


@app.get("/api/kontrola-scena/vd/<int:shop_product_id>")
@staff_required
def kontrolni_scena_vd(shop_product_id):
    """Data pro polozku `vd:<karta>[:<navrh>]` kontrolni sceny (bot10
    2026-09-24; Robert: "v kontrolní scéně je všechno jen pro kontrolu...
    může se tam dávat cokoli co potřebuju"). Vandr karta = monoliticky GLB
    (shop_products.glb_file, webapp/katalog/) + razitkove dily.

    Bez `navrh` = razitka z DB (vandr_razitka_json - to, co se skutecne
    renderuje). S `?navrh=<jmeno>` = razitka ze souboru
    private-files/kontrola-navrhy/navrh_<jmeno>.json = NAVRH ke schvaleni.
    DB se pri nahledu navrhu NEDOTYKA zamerne: vandr-render-dispatch timer
    reaguje na kazdou zmenu vandr_razitka_json ostrym renderem, navrh by
    tak sel do produkce drív, nez ho Robert schvali. Jen cteni, zadny zapis."""
    navrh = (request.args.get("navrh") or "").strip()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT sp.id, sp.sku, sp.name, sp.glb_file, sp.vandr_razitka_json, sp.vandr_predni_azimut_deg, "
                # WORKFLOW.md pravidlo 51/52 (Robert: "postradam stitky v
                # detailu sestavy Vandr") - kontrolni scena JE detail, kde
                # Robert karty realne kontroluje (viz pravidlo 53), stejny
                # kod+tooltip vzor jako v prehledu "Tvorba sestav - Vandr".
                "ru.kod AS umisteni_kod, ru.nazev AS umisteni_nazev "
                "FROM shop_products sp LEFT JOIN regal_umisteni ru ON ru.id = sp.umisteni_id "
                "WHERE sp.id=%s", (shop_product_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row or not row.get("glb_file"):
        return jsonify({"error": "Karta %d neexistuje nebo nema GLB soubor." % shop_product_id}), 404
    out = {"product": {"id": row["id"], "sku": row["sku"], "name": row["name"], "glb_file": row["glb_file"],
                       "umisteni_kod": row["umisteni_kod"], "umisteni_nazev": row["umisteni_nazev"]},
           "souhrn": None, "pravidlo": None}
    if navrh:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", navrh):
            return jsonify({"error": "Neplatny nazev navrhu."}), 400
        path = os.path.join(KONTROLA_NAVRHY_DIR, "navrh_%s.json" % navrh)
        if not os.path.isfile(path):
            return jsonify({"error": "Navrh '%s' neexistuje (cekam soubor kontrola-navrhy/navrh_%s.json)."
                            % (navrh, navrh)}), 404
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            razitka = data.get("razitka") or []
            out["souhrn"] = data.get("souhrn")
            out["pravidlo"] = data.get("pravidlo")
        else:
            razitka = data
        out["zdroj"] = "navrh:%s" % navrh
        # bot10 2026-09-24 (pravidlo 52, nalez 4604 "cok stitek nema
        # razitko"): navrh jeste nebyl zapsan do shop_products, azimut
        # bere ze SVEHO SOUHRNU (stejna hodnota, kterou by zapis pouzil).
        if out["souhrn"] and out["souhrn"].get("predni_azimut_rig") is not None:
            out["front_azimuth_deg"] = out["souhrn"]["predni_azimut_rig"]
    else:
        razitka = json.loads(row["vandr_razitka_json"]) if row.get("vandr_razitka_json") else []
        out["zdroj"] = "db"
        # Geometricky spocitany predni azimut TETO karty (scripts/2026-09-23_
        # vandr_razitka_spocitat.py, Krok 3d) - stejna hodnota, kterou pouziva
        # render (build_job_vandr). Kontrolni scena na ni muze naklonit kameru,
        # aby "co vidis tady" bylo primo overitelne proti "co ukaze render",
        # misto dohadovani ze skryteho vychoziho uhlu (nalez 4604).
        out["front_azimuth_deg"] = row["vandr_predni_azimut_deg"]
    out["razitka"] = razitka if isinstance(razitka, list) else []
    # WORKFLOW.md pravidlo 52 (Robert: "můžeš to simulovat i v kontrolní
    # scéně ty azimuty" - chce projít presne ty uhly, ze kterych render
    # vezme snimky, drive nez GPU spali cas). ŽÁDNÁ nová kopie vzorce
    # (bot3: "kdyby vznikla treti definice, rozejde se to presne jako ta
    # vec s listou v nazvu u cen") - `turntable._azimuths_for_front()`
    # a `turntable.ELEVATIONS`/`STEP_DEG` jsou PŘÍMO ty samé, které
    # pouziva api/blender_render_turntable.py pro skutecny render
    # (turntable.py se importuje uz v api/app.py, viz "import turntable"
    # o par tisic radku vyse).
    if out.get("front_azimuth_deg") is not None:
        out["azimuths"] = list(turntable._azimuths_for_front(int(out["front_azimuth_deg"])))
        out["elevations"] = list(turntable.ELEVATIONS)
        out["step_deg"] = turntable.STEP_DEG
    return jsonify(out)


@app.get("/scene.html")
def scene_html_gate():
    """Vstup do 3D sceny - stejna staff-only politika jako scene-
    exkluzivni API (Robert 2026-09-03: "zakaznikum pristup do sceny
    neumoznime, neni to vhodne", viz komentar u staff_required vyse).
    Doposud servirovano cistě staticky pres nginx (zadna kontrola pri
    samotnem nacteni stranky, jen jednotlive API volani uvnitr sceny
    byla gatovana) - nalez Roberta 2026-09-08 (mobil: "přihlásím se do
    scény bez přihlášení" - staticky shell se nacetl vzdy, i kdyz
    hlubsi funkce pak selhavaly na 401/403). Tenhle route ma prednost
    pred nginx static servirovanim (viz nginx `location = /scene.html`
    proxy_pass) - samotny soubor webapp/scene.html NENI menen, jen
    pridana kontrola pred jeho odeslanim."""
    user = current_user()
    if not user or not user["active"] or user["role"] not in PERMISSION_ROLES:
        next_path = request.full_path if request.query_string else request.path
        return redirect(f"/login.html?next={quote(next_path, safe='')}")
    webapp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp")
    return send_from_directory(webapp_dir, "scene.html")


# --- Role a opravneni (bot3, 2026-07-25, v10). Robert: "az dokoncis
# praci, udelej robustnejsi prihlasovani a kompetence, pristupy, navrhni
# role a s tim souvisejici prava formou zatrzitek napric celym
# systemem." -> navrh (Navrh_roli_a_opravneni.docx) schvalen ("nasadit").
# Viz sql/2026-07-25_rbac.sql pro tabulku role_permissions a seed dat.
#
# admin_required() vyse ZUSTAVA beze zmeny a dal se pouziva tam, kde ma
# smysl jen jedina role (napr. sprava samotnych opravneni nize - at uz
# nikdo neomezi/nezamkne admina zmenou v checkboxech). Vetsina puvodnich
# @admin_required endpointu v app.py/cart.py/customers.py/documents.py/
# emails.py/orders.py/purchase_orders.py se prevadi na jemnejsi
# @require_permission(section, action), ktere navic povoluje pristup
# rolim 'skladnik'/'ucetni' dle tabulky role_permissions.
PERMISSION_SECTIONS = (
    "objednavky", "nakupni_objednavky", "doklady", "emaily_odchozi", "zakaznici",
    "doprava_platba",
    "uzivatele", "nastaveni", "audit_log", "kosiky", "galerie", "emaily_prichozi", "crm",
    "nabidky", "sdileny_disk", "kniha_jizd", "prijate_doklady", "bankovni_vypisy",
    "mini_eshopy", "zakreslene_pripominky", "reklamace", "vyroba_sestav",
    # bot5, 2026-10-03 (bot16 + Robert pres bot3: zalozka "Mini-shopy" se stejnymi ucty a pravy): shopy/poptavky/objednavky mini-shopu a (zvlast) schvalovani jejich textu
    "miniweb", "miniweb_schvalovani",
    # bot16, 2026-09-29 (Robert pres bot3, "rozsekat kategorie_obsah/
    # ceny_prislusenstvi/produkty_sklad na dnesni granularitu zalozek" -
    # tyhle 3 sirokych sekce od zalozeni RBAC pobraly postupne mnoho
    # vzajemne nesouvisejicich zalozek pod jeden checkbox, "zaskrtnout
    # jednu z nich" tak ve skutecnosti znamenalo "zaskrtnout 6-9 ruznych
    # nastroju najednou". Kazdy @require_permission() puvodne pod temito
    # 3 nazvy overeny proti skutecnemu volajicimu JS/zalozce (ne odhadem)
    # a presunut na presne jednu z sekci nize - viz AGENTS_LOG.md pro
    # kompletni mapovani a migraci existujicich grantu v role_permissions.
    "kategorie", "homepage_mozaika", "homepage_carousel", "centralni_texty",
    "hlasky", "postranni_panel",
    "ceny_profilu", "dogus_cena", "prislusenstvi",
    "sklad_karty", "sklad_pohyby", "sklad_doobjednavky", "rezne_plany",
    "eshop_nastaveni", "rozklad_fbx",
    # bot5, 2026-09-29 (Robert primo, po dotazu "proc ma videt mistr
    # chybove hlasky na dashboardu": "toto jsou jen adminovske panely,
    # nema to videt nikdo jiny, dokud nedostane prava" + "okamzite
    # vytvor mechanismus, kterym se dostane kazdy panel adminu do
    # tabulky roli a prav") - jednotlive INTERNI/QA/provozni panely
    # Dashboardu (webapp/admin.html DASHBOARD_PANEL_SECTION) dostavaji
    # KAZDY VLASTNI sekci, ne sdilenou "nastaveni"/"vyroba_sestav" -
    # fail-closed jako "monter"/"kniha_jizd" vyse, dokud Robert
    # nezaskrtne konkretni pravo v Role a opravneni, nikdo krome
    # admina panel nevidi. "Ke schvaleni" a "Tym" zamerne BEZ vlastni
    # sekce - "Ke schvaleni" uz ma vlastni per-polozkove filtrovani
    # podle 'upravit' prava, "Tym" je vyslovne pro vsechny prihlasene
    # staff role (viz staff_required docstring).
    "dash_vyroba_sestav", "dash_vandr_vyroba", "dash_gpu_monitor",
    "dash_qa_bugy", "dash_qa_ukoly", "dash_qa_navrhy", "dash_qa_system", "dash_js_chyby",
    # bot16, 2026-10-01 (Robert pres bot3: "uz me nebavi delat restart"): panel "Nasazeni serveru"
    # (api/deploy_runs.py, scripts/nasazeni.py). TUHLE SEKCI MUSI znat PERMISSION_SECTIONS DRIV, nez se
    # naimportuje deploy_runs - require_permission() ji kontroluje uz pri importu a neznama sekce by
    # shodila start vsech workeru.
    "dash_nasazeni",
    # bot5, 2026-10-02 (Robert pres bot3, dealersky program etapa 1, TASKS.md): sprava dealeru + sazeb, provize a vyuctovani, klice dealeru.
    # Fail-closed jako predchozi nove sekce (nikdo krome admina, dokud Robert nezaskrtne prava). MUSI byt zde DRIV nez se naimportuje
    # dealers.py (require_permission() kontroluje sekci uz pri importu).
    "dealeri", "dealer_provize", "dealer_klice",
    # bot16, 2026-10-06 (Robert pres bot9: "chci Johnovu praci videt primo v adminu v nejakem panelu"): zalozka Prehledy > John (webapp/admin.html TAB_SECTION john,
    # webapp/admin/js/prehledy-john.js, api/john_stav.py). Fail-closed jako predchozi nove sekce (nikdo krome admina, dokud Robert nezaskrtne pravo v Role a opravneni).
    # MUSI byt zde DRIV nez se naimportuje john_stav.py (require_permission() kontroluje sekci uz pri importu).
    "prehledy_john",
    # bot16, 2026-10-06 (Robert: "schvalene doklady automaticky posilat na emaily ucetni, ruzne emaily podle typu dokladu, postav nato tabulku v adminu"): zalozka Prodej > E-maily ucetni
    # (api/ucetni_emaily.py), jen adresy podle typu dokladu, nic se neodesila (pravidlo 16). TUHLE SEKCI MUSI znat PERMISSION_SECTIONS driv, nez se ucetni_emaily naimportuje.
    "ucetni_emaily",
)
# bot10, 2026-08-22 (Robert pres bot3): UI uz dlouho ukazuje "Emaily
# prichozi" (drivejsi "Podpora"/zivy chat) a "Emaily odchozi" ("E-maily"),
# ale RBAC sekce se porad jmenovaly "podpora"/"emaily" - matouci vuci
# UI i vuci sobe navzajem ("emaily" a "emaily_prichozi" znely podobne).
# Prejmenovano na "emaily_prichozi"/"emaily_odchozi" - SOUCASNE s touhle
# zmenou MUSI probehnout `UPDATE role_permissions SET section=...`
# migrace (viz nasazovaci prikaz v AGENTS_LOG.md) - role_permissions
# uklada section jako STRING DATA, ne enum, takze stary nazev by tise
# osiretl a existujici granty pro manager/skladnik/ucetni by zmizely
# (admin ma bypass, takze by si toho nikdo nemusel vsimnout hned).
# DB tabulky (shop_support_*), nazvy souboru (support.py) a JS
# identifikatory (supportModalLog apod.) VEDOME ponechany beze zmeny -
# rozsah zasahu by neunesl pomer k prinosu (cistě kosmeticke), viz
# TASKS.md pro rozepsane duvody a co zbyva, pokud se bude chtit pokracovat.
PERMISSION_ACTIONS = ("zobrazit", "vytvorit", "upravit", "smazat", "foceni_mobil")
# Robert 2026-07-31: "ve sprave roli... u vsech pridat sloupec pravo na
# foceni v mobilu" - novy sloupec v existujici matici (kazda sekce X
# kazda role uz ma checkbox pro zobrazit/vytvorit/upravit/smazat, ted i
# pro foceni_mobil). POZOR: tenhle checkbox se zatim NEVYNUCUJE - mobilni
# fotoaparat (webapp/capture.html, api/gallery_items.py INBOX_ROLES)
# ma vlastni pevny seznam roli (admin/manager/skladnik/ucetni/monter),
# ne tenhle radek matice. Nechano zamerne netknute (bot5, jen ted
# otestovana produkcni funkce) - jen pridan sloupec, jak bylo pozadano;
# propojeni na skutecne vynucovani je dalsi krok, pokud ho Robert bude
# chtit.
# Robert 2026-07-26: "role a opravneni, pridej managera a odstran
# zakaznika, na sekce pridej vsechno relevantni". Manager je od tohoto
# bodu skutecna spravovatelna role v matici (predtim byl jen popiskovy
# rozdil od "user" bez realneho admin pristupu - viz hint v zalozce
# Uzivatele). "zakaznik" (drivejsi klic pro roli 'user', bezny e-shop
# zakaznik) z matice zcela odstranen - zakaznici nemaji do administrace
# pristup a nemely by tam mit ani teoreticky nastavitelna prava, proto
# has_permission() nize nyni takovou roli zamitne rovnou, bez dotazu do
# DB (viz "role not in PERMISSION_ROLES" nize). Diky tomu uz neni
# potreba zadne preklizeni klicu (_permission_role_key) - vsechny
# zbyvajici role (manager/skladnik/ucetni) maji svuj app_users.role
# retezec totozny s klicem v teto tabulce.
# Robert 2026-08 ("chybi role monter"): monter pridan do matice - do te
# doby existoval jen jako app_users.role (vyber u uzivatele, pristup do
# fotoapky pres INBOX_ROLES), ale nesel mu priradit zadny admin pristup
# a nevidel ani schvalovaci sekce na dashboardu. Fail-closed: dokud mu
# Robert nezaskrtne konkretni prava v Role a opravneni, nema nic.
# Robert 2026-08-05 ("mala kniha jizd, 3 firemni auta"): sekce
# "kniha_jizd" pridana pro admin spravu vozidel + prehled jizd (viz
# api/fleet.py). Fail-closed jako u sekce "monter" vyse - dokud Robert
# nezaskrtne prava v Role a opravneni, nikdo krome admina nic nevidi.
# Mobilni tlacitko "Jizda" v capture.html na tuhle matici NENAVAZUJE -
# ma vlastni pevny seznam roli (FLEET_ROLES v api/fleet.py), stejny
# vzor jako INBOX_ROLES pro fotoapku.
# Robert 2026-08-17 (pres bot3, "doklady, ktere musime zavadet do
# ucetnictvi"): sekce "prijate_doklady" pridana pro schvalovaci frontu
# faktur/dokladu prijatych e-mailem (viz api/incoming_documents.py) -
# ZAMERNE odlisna od stavajici "doklady" (ta je pro doklady VYSTAVENE
# eshopem, api/documents.py). Fail-closed jako "monter"/"kniha_jizd"
# vyse - dokud Robert nezaskrtne prava v Role a opravneni, nikdo krome
# admina nic nevidi.
# Robert 2026-08-21 (pres bot3): sekce "bankovni_vypisy" pridana pro
# panel prijatych bankovnich plateb z FIO (viz api/bank_statements.py) -
# fail-closed jako predchozi nove sekce vyse.
PERMISSION_ROLES = ("admin", "manager", "skladnik", "ucetni", "monter", "sklad")


def has_permission(user, section, action):
    """True pro roli admin vzdy (bezpecnostni pojistka proti zamknuti
    systemu chybnou konfiguraci checkboxu). Role mimo PERMISSION_ROLES
    (typicky bezny e-shop zakaznik, app_users.role='user') nemaji do
    admin API pristup nikdy, bez ohledu na obsah role_permissions -
    fail-closed uz na urovni Pythonu, ne jen chybejicim radkem v DB.
    Pro zbyvajici role dotaz do role_permissions - chybejici radek =
    tez fail-closed (zadny pristup)."""
    if not user:
        return False
    if user["role"] == "admin":
        return True
    if user["role"] not in PERMISSION_ROLES:
        return False
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT allowed FROM role_permissions WHERE role=%s AND section=%s AND action=%s",
                (user["role"], section, action),
            )
            row = cur.fetchone()
            return bool(row and row["allowed"])
    finally:
        conn.close()


def zobrazit_permissions_map(user):
    """Mapa {section: True/False} pro pravo 'zobrazit' AKTUALNIHO uzivatele
    napric vsemi PERMISSION_SECTIONS - vraceno v /api/auth/me, aby si
    admin.html mohl sam skryt zalozky, na ktere role nema pravo (bot4,
    2026-08-05: "otevreni admin.html pro manager/mistr/asistent", drive
    do te doby pustilo jen roli admin). Skutecne vynuceni zustava na
    require_permission u kazdeho endpointu - tohle je jen UX filtr, co
    se v levem menu vubec zobrazi. None pro role mimo PERMISSION_ROLES
    (bezny zakaznik) - ty se do administrace stejne nedostanou."""
    if user["role"] == "admin":
        return {s: True for s in PERMISSION_SECTIONS}
    if user["role"] not in PERMISSION_ROLES:
        return None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT section, allowed FROM role_permissions WHERE role=%s AND action='zobrazit'",
                (user["role"],),
            )
            allowed = {r["section"]: bool(r["allowed"]) for r in cur.fetchall()}
    finally:
        conn.close()
    return {s: allowed.get(s, False) for s in PERMISSION_SECTIONS}


def require_permission(section, action):
    if section not in PERMISSION_SECTIONS or action not in PERMISSION_ACTIONS:
        raise ValueError(f"Neznama sekce/akce pro require_permission: {section}/{action}")

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user or not user["active"]:
                return jsonify({"error": "Neprihlaseno.", "code": "unauthorized"}), 401
            if not has_permission(user, section, action):
                return jsonify({"error": "Nemate opravneni k teto akci.", "code": "forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@app.get("/api/admin/role-permissions")
@admin_required
def admin_role_permissions_list():
    """Cely maticovy prehled pro checkbox UI. Zamerne jen @admin_required
    (ne @require_permission) - sprava opravneni ostatnich roli je citliva
    operace, kterou nechavame vyhradne na roli admin."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role, section, action, allowed FROM role_permissions ORDER BY role, section, action")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({
        "sections": list(PERMISSION_SECTIONS),
        "actions": list(PERMISSION_ACTIONS),
        "roles": list(PERMISSION_ROLES),
        "permissions": [
            {"role": r["role"], "section": r["section"], "action": r["action"], "allowed": bool(r["allowed"])}
            for r in rows
        ],
    })


@app.put("/api/admin/role-permissions")
@admin_required
def admin_role_permissions_update():
    """Body: {"permissions": [{"role","section","action","allowed"}, ...]}.
    Role 'admin' se preskakuje (natvrdo plny pristup v kodu, checkboxy pro
    ni jsou v UI jen informativni) - stejne tak neznama role/sekce/akce se
    ignoruje, at chybny pozadavek nezpusobi 500 ani castecny zapis nesmyslu."""
    body = request.get_json(silent=True) or {}
    items = body.get("permissions")
    if not isinstance(items, list):
        return jsonify({"error": "Ocekavam pole 'permissions'."}), 400
    to_write = []
    for it in items:
        role = it.get("role")
        section = it.get("section")
        action = it.get("action")
        allowed = 1 if it.get("allowed") else 0
        if role == "admin":
            continue
        if role not in PERMISSION_ROLES or section not in PERMISSION_SECTIONS or action not in PERMISSION_ACTIONS:
            continue
        to_write.append((role, section, action, allowed))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for role, section, action, allowed in to_write:
                cur.execute(
                    "INSERT INTO role_permissions (role, section, action, allowed) VALUES (%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE allowed=VALUES(allowed)",
                    (role, section, action, allowed),
                )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "role_permissions", None, f"{len(to_write)} zaznamu")
    return jsonify({"updated": len(to_write)})


# Bezpecnostni review verejne registrace Remesla (bot14, 2026-08-20,
# AGENTS_LOG.md "BEZPECNOSTNI REVIEW verejne registrace Remesla", nalez
# N3) - puvodne jen delka >= 8, projelo "password"/"12345678"/"11111111".
# Robert 2026-08-23 (pres bot3 koordinaci): zprisnit pro OBE verejne
# registrace (e-shop i Remeslo). Seznam je zamerne kratky/rucni (ne cely
# externi "top 10000 hesel" soubor) - cilem je odchytit holé triviality,
# ne nahradit skutecny password-strength audit.
_WEAK_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789",
    "1234567890", "11111111", "00000000", "aaaaaaaa", "qwertyui",
    "qwerty123", "letmein1", "iloveyou", "admin123", "abc12345",
    "1q2w3e4r", "trustno1", "welcome1", "monkey12", "dragon12",
}


def validate_password_strength(password):
    """Vraci chybovou hlasku (str), kdyz heslo nevyhovuje, jinak None.
    Pravidlo: delka >= 8 (beze zmeny) + kombinace aspon 2 druhu znaku
    (mala/velka pismena, cislice, symboly) + neni na seznamu trivialnich
    hesel (case-insensitive, bez ohledu na kombinaci znaku - "Password1"
    by jinak prošlo pouhou kombinaci znaku)."""
    if len(password) < 8:
        return "Heslo musí mít alespoň 8 znaků."
    if password.lower() in _WEAK_PASSWORDS:
        return "Tohle heslo je příliš snadné uhodnout, zvol prosím jiné."
    classes = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if classes < 2:
        return "Heslo musí kombinovat alespoň dva druhy znaků (velká/malá písmena, číslice, symboly)."
    return None


# Overeni e-mailu pri registraci (bod 1 stejneho review, nalez N4) - novy
# ucet zustava neaktivni (app_users.active=0, email_verified=0), dokud
# nepotvrdi e-mail kliknutim na odkaz s tokenem (email_verification_tokens,
# viz sql/2026-08-23_email_verification.sql). POUZE tenhle helper generuje
# token a sklada text e-mailu - SAMOTNE odeslani jde VZDY pres frontu
# system_emails ('pending' -> admin schvaluje v adminu), NIKDY primo
# send_email() - WORKFLOW.md bod 16 (Robert 2026-08-22, plosny zakaz
# automatickeho odesilani bez schvaleni) nema pro overovaci e-mail
# vyjimku (viz AGENTS_LOG.md, dotaz na bota3 pred timhle commitem).
def issue_email_verification(cur, user_id, email, name, base_url):
    token = secrets.token_urlsafe(32)
    # V DB jen SHA256 hash, ne plaintext (bezpecnostni nalez, bot3/revize
    # kodu 2026-09-02 - stejny princip jako magic_token_hash: pri uniku DB
    # by nikdo nezískal pouzitelny token). Uzivatel dostane plaintext v
    # odkazu, appka pri overeni hashuje prichozi token a porovnava.
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=EMAIL_VERIFICATION_TTL_MIN)
    cur.execute(
        "INSERT INTO email_verification_tokens (user_id, token, expires_at) VALUES (%s,%s,%s)",
        (user_id, token_hash, expires_at),
    )
    link = f"{base_url}/verify-email.html?token={token}"
    first = (name or "").split(" ")[0] if name else ""
    greeting = "Dobrý den," if not first else f"Dobrý den, {first},"
    subject = "Potvrzení e-mailu — LOGIMAN"
    body = (
        f"{greeting}\n\ndíky za registraci. Pro dokončení a aktivaci účtu prosím potvrď "
        f"svou e-mailovou adresu kliknutím na odkaz níže (platí {EMAIL_VERIFICATION_TTL_MIN // 60} hodin):\n\n"
        f"{link}\n\nPokud jsi o registraci nežádal, tenhle e-mail můžeš ignorovat - bez potvrzení "
        "účet zůstane neaktivní.\n\nS pozdravem,\nLOGIMAN s.r.o."
    )
    cur.execute(
        "INSERT INTO system_emails (user_id, kind, recipient_email, subject, body_text, status, trigger_type) "
        "VALUES (%s,'email_verification',%s,%s,%s,'pending','auto')",
        (user_id, email, subject, body),
    )


@app.post("/api/auth/login")
def auth_login():
    # Bezpecnost (bot11, 2026-08-18, nalez 1.3): 10 pokusu / 5 minut na
    # IP - dost na bezne preklepy, ale zastavi automatizovany
    # brute-force. Limit je na IP, ne na e-mail - primo brani i
    # "zkousej hodne ruznych e-mailu z jedne IP" varianty utoku.
    if _rate_limited(f"login:{_client_ip()}", max_requests=10, window_seconds=300):
        return jsonify({"error": "Příliš mnoho pokusů o přihlášení, zkuste to prosím za pár minut znovu."}), 429
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"error": "Vyplň e-mail i heslo."}), 400
    # V3 (bezpecnostni nalez, bot3/revize kodu 2026-09-02): limit per IP
    # nebrani distribuovanemu utoku (botnet/proxy rotace) na JEDEN ucet -
    # doplnen limit i per e-mail (klic vznika i pro neexistujici e-mail,
    # neprozrazuje existenci uctu).
    if _rate_limited(f"login_user:{email}", max_requests=10, window_seconds=900):
        return jsonify({"error": "Příliš mnoho pokusů o přihlášení, zkuste to prosím za pár minut znovu."}), 429

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, role, active, email_verified, password_hash FROM app_users WHERE email=%s",
                (email,),
            )
            user = cur.fetchone()
    finally:
        conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Špatný e-mail nebo heslo."}), 401
    if not user["active"]:
        # email_verified rozlisuje "jeste nikdy nepotvrdil registraci" od
        # "admin ucet rucne deaktivoval" (obojí sdili active=0) - jina
        # hlaska/navazujici akce (znovuodeslat vs. kontaktovat admina).
        if not user["email_verified"]:
            return jsonify({
                "error": "Účet ještě není potvrzený. Zkontroluj prosím e-mail a klikni na potvrzovací odkaz.",
                "code": "email_not_verified",
            }), 403
        return jsonify({"error": "Účet je deaktivovaný."}), 403

    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"status": "ok", "user": {
        "id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"],
    }})


@app.post("/api/auth/register")
def auth_register():
    # Verejna samoobsluzna registrace zakazniku (Robert 2026-07-25: "ano,
    # verejna registrace").
    #
    # ZMENA (bot13, 2026-08-23, bezpecnostni review Modulu 11, body 1+2 -
    # AGENTS_LOG.md "BEZPECNOSTNI REVIEW verejne registrace Remesla",
    # Robertovo rozhodnuti implementovat vsechny 3 body): puvodne rovnou
    # aktivni + rovnou prihlasen (zadne overovani e-mailu) - umoznovalo
    # zalozit ucet na CIZI e-mail (obet pak nema jak si zalozit vlastni).
    # Novy ucet je ted NEAKTIVNI (active=0, email_verified=0), dokud
    # nepotvrdi e-mail (viz issue_email_verification vyse) - zadne
    # rovnou-prihlaseni. Odpoved je navic ZAMERNE STEJNA (stejny status
    # kod, stejne telo) bez ohledu na to, jestli e-mail uz ma ucet, nebo
    # ne (user enumeration, nalez N2 - drive "Účet s tímto e-mailem už
    # existuje" 400 vs. 201 prozrazovalo registrovane adresy).
    #
    # QA bezpecnostni nalez (2026-09-05): chybel rate-limit, na rozdil od
    # skoro identickeho sourozeneckeho remeslo_register (remeslo.py) - tam
    # bez brzdy "zivym testem se podarilo zalozit 12 uctu z jedne IP za
    # 7,2 s", stejne hodnoty prevzaty odtud.
    if _rate_limited(f"register:{_client_ip()}", max_requests=5, window_seconds=600):
        return jsonify({"error": "Příliš mnoho pokusů o registraci. Zkuste to prosím za chvíli."}), 429
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()
    password = body.get("password") or ""

    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"error": "Zadej platnou e-mailovou adresu."}), 400
    pw_err = validate_password_strength(password)
    if pw_err:
        return jsonify({"error": pw_err}), 400

    generic = {
        "status": "ok",
        "message": "Pokud e-mail ještě není zaregistrovaný, poslali jsme na něj potvrzovací odkaz.",
    }
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM app_users WHERE email=%s", (email,))
            if cur.fetchone():
                return jsonify(generic)
            party_id = create_party(cur, full_name=name, primary_email=email)
            cur.execute(
                "INSERT INTO app_users (email, password_hash, name, role, active, email_verified, party_id) "
                "VALUES (%s,%s,%s,'user',0,0,%s)",
                (email, generate_password_hash(password), name, party_id),
            )
            new_id = cur.lastrowid
            issue_email_verification(cur, new_id, email, name, APP_BASE_URL)
        conn.commit()
    finally:
        conn.close()

    return jsonify(generic)


# Znovuodeslani potvrzovaciho e-mailu (bot13, 2026-08-23) - doplnek k
# auth_register vyse, pro pripad ztraceneho/vyprseleho odkazu (24h TTL).
# Stejny "vzdy stejna odpoved" princip jako auth_register/auth_forgot_password
# (neprozrazuje, jestli e-mail existuje/je uz overeny). Rate-limit sdili
# vzor s ostatnimi verejnymi auth endpointy.
@app.post("/api/auth/resend-verification")
def auth_resend_verification():
    if _rate_limited(f"resend_verification:{_client_ip()}", max_requests=5, window_seconds=600):
        return jsonify({"error": "Příliš mnoho pokusů, zkuste to prosím za chvíli."}), 429
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    generic = {"status": "ok", "message": "Pokud e-mail existuje a čeká na potvrzení, poslali jsme na něj nový odkaz."}
    if not email:
        return jsonify(generic)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, name FROM app_users WHERE email=%s AND email_verified=0", (email,))
            user = cur.fetchone()
            if user:
                issue_email_verification(cur, user["id"], user["email"], user["name"], APP_BASE_URL)
                conn.commit()
    finally:
        conn.close()
    return jsonify(generic)


@app.post("/api/auth/verify-email")
def auth_verify_email():
    body = request.get_json(silent=True) or {}
    token = (body.get("token") or "").strip()
    if not token:
        return jsonify({"error": "Chybí token."}), 400
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, user_id, expires_at, used FROM email_verification_tokens WHERE token=%s", (token_hash,))
            row = cur.fetchone()
            if not row or row["used"]:
                return jsonify({"error": "Odkaz je neplatný nebo už byl použitý."}), 400
            if row["expires_at"] < datetime.datetime.utcnow():
                return jsonify({"error": "Odkaz vypršel - vyžádej si prosím nový.", "code": "expired"}), 400
            cur.execute("UPDATE app_users SET active=1, email_verified=1 WHERE id=%s", (row["user_id"],))
            cur.execute("UPDATE email_verification_tokens SET used=1 WHERE id=%s", (row["id"],))
            cur.execute("SELECT id, email, name, role FROM app_users WHERE id=%s", (row["user_id"],))
            user = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"status": "ok", "user": {
        "id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"],
    }})


@app.post("/api/auth/logout")
def auth_logout():
    session.clear()
    return jsonify({"status": "ok"})


@app.get("/api/auth/me")
def auth_me():
    user = current_user()
    if not user:
        return jsonify({"user": None}), 401
    return jsonify({"user": {
        "id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"],
        "theme_admin": user["theme_admin"], "theme_shop": user["theme_shop"],
        "permissions": zobrazit_permissions_map(user),
    }})


@app.put("/api/auth/theme")
@login_required
def auth_update_theme():
    # Uzivatelsky nastavitelne barevne schema (task #66, Robert 2026-07-26) -
    # admin panel a zakaznicky web se nastavuji NEZAVISLE (kazdy ma vlastni
    # sloupec), scope urcuje, ktery se meni.
    body = request.get_json(silent=True) or {}
    scope = body.get("scope")
    theme = body.get("theme")
    if scope not in ("admin", "shop"):
        return jsonify({"error": "scope musi byt 'admin' nebo 'shop'."}), 400
    if theme not in ("dark", "light"):
        return jsonify({"error": "theme musi byt 'dark' nebo 'light'."}), 400
    column = "theme_admin" if scope == "admin" else "theme_shop"
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE app_users SET {column}=%s WHERE id=%s", (theme, user["id"]))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "scope": scope, "theme": theme})


def _auth_recovery_rate_limited(email):
    """Sdileny rate limit pro OBA endpointy obnovy pristupu (forgot-password
    i send-temp-password) - bezpecnostni nalez, bot3/revize kodu 2026-09-02:
    puvodne bez jakehokoli limitu, anonym mohl opakovane prepisovat heslo
    libovolneho uctu (vc. adminu) nebo spamovat existujici uzivatele resetem.
    Per IP (obecna brzda proti hromadnemu zkouseni ruznych emailu) A per
    cilovy e-mail (chrani KONKRETNI ucet bez ohledu na to, ze utocnik strida
    IP) - obe cesty sdileji stejny klic 'tmp_pw:<email>', protoze obe vedou
    ke stejnemu dopadu (zmena/reset hesla ciloveho uctu)."""
    if _rate_limited(f"auth_recovery_ip:{_client_ip()}", max_requests=5, window_seconds=600):
        return True
    if email and _rate_limited(f"tmp_pw:{email}", max_requests=3, window_seconds=3600):
        return True
    return False


@app.post("/api/auth/forgot-password")
def auth_forgot_password():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    # Vzdy stejna odpoved bez ohledu na to, jestli email v systemu existuje -
    # appka nesmi prozradit, ktere adresy maji ucet (stejny princip jako v
    # referencnim sklad-projektu, accounts/views.py forgot_password()).
    generic = {"status": "ok", "message": "Pokud e-mail v systému existuje, byl na něj odeslán odkaz pro nastavení nového hesla."}
    if not email or _auth_recovery_rate_limited(email):
        return jsonify(generic)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, active FROM app_users WHERE email=%s", (email,))
            user = cur.fetchone()
            if user and user["active"]:
                token = secrets.token_urlsafe(32)
                # V DB jen SHA256 hash, ne plaintext - stejny princip jako
                # magic_token_hash/email_verification_tokens (bezpecnostni
                # nalez, bot3/revize kodu 2026-09-02).
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=RESET_TOKEN_TTL_MIN)
                cur.execute(
                    "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (%s,%s,%s)",
                    (user["id"], token_hash, expires_at),
                )
                conn.commit()
                link = f"{APP_BASE_URL}/reset-password.html?token={token}"
                # VYJIMKA Z WORKFLOW.md bodu 16 (Robert, 2026-08-27, po
                # nalezu z AUDIT_OPTIMALIZACE_2026-08-26.md/qa_checks.py::
                # check_direct_send_email_bypass) - VEDOME ponechano jako
                # primy send_email(), NE fronta pres emails.send_and_log/
                # system_emails. Duvod: bezpecnostni/casove kriticky
                # e-mail (odkaz na reset hesla plati jen RESET_TOKEN_TTL_
                # MIN minut) - cekani na schvaleni admina by tu skodilo
                # vic nez pomahalo. Znama/schvalena vyjimka, ne bug k
                # oprave - allowlistovano v qa_checks.py.
                #
                # try/except (bot3/revize kodu, 2026-09-02): vypadek SMTP
                # drive vratil 500 JEN pro existujici ucty (neexistujici
                # se vubec nedostaly k send_email) - rozdil v HTTP statusu
                # tak prozrazoval, ktere e-maily maji ucet (enumerace).
                # Ted vzdy stejna 200 odpoved, chyba jen do logu.
                try:
                    send_email(
                        user["email"],
                        "Nastavení nového hesla — Hliníkový konstrukční stavebnicový systém s drážkami",
                        f"Ahoj,\n\npožádal jsi o nastavení nového hesla. Klikni na odkaz níže (platí {RESET_TOKEN_TTL_MIN} minut):\n\n{link}\n\nPokud jsi o reset nežádal, tenhle e-mail můžeš ignorovat.",
                    )
                except Exception as e:
                    app.logger.warning("auth_forgot_password: send_email selhalo pro %s: %s", user["email"], e)
    finally:
        conn.close()
    return jsonify(generic)


# Robert 2026-07-31: odkaz+formular na nastaveni hesla (forgot-password
# vyse) mu delal problemy s navrhovanim/kopirovanim hesla v prohlizeci
# ("navrhovane heslo nelze nakopirovat"). Tahle cesta obchazi cely
# problem - vygeneruje NOVE HESLO ROVNOU, nastavi ho a posle ho
# prostym textem v e-mailu, ktery si uzivatel muze normalne oznacit a
# zkopirovat (zadny prohlizecovy "navrh hesla" dialog, zadne dve pole na
# potvrzeni). VEDOMY KOMPROMIS (stejny princip jako magic login a
# ?email=&pass= v URL vyse) - heslo prochazi e-mailem prostym textem,
# Robertovo vyslovne rozhodnuti prioritizovat pohodlnost. Doporuceno
# uzivateli po prihlaseni zmenit na vlastni (appka to zatim neresi
# vynucene, jen doporucenim v e-mailu).
@app.post("/api/auth/send-temp-password")
def auth_send_temp_password():
    # NAMET (bot3/revize kodu, 2026-09-02, NEIMPLEMENTOVANO - vyzaduje
    # migraci): stare heslo by moho zustat platne az do prvniho pouziti
    # noveho, aby vypadek SMTP po UPDATE nize nezamkl uzivatele mimo
    # ucet. Zapsano jako namet do STAV.md/handover, ne provedeno tady.
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    generic = {"status": "ok", "message": "Pokud e-mail v systému existuje, bylo na něj odesláno nové heslo."}
    if not email or _auth_recovery_rate_limited(email):
        return jsonify(generic)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, active FROM app_users WHERE email=%s", (email,))
            user = cur.fetchone()
            if user and user["active"]:
                new_password = secrets.token_urlsafe(12)
                cur.execute("UPDATE app_users SET password_hash=%s WHERE id=%s", (generate_password_hash(new_password), user["id"]))
                conn.commit()
                # VYJIMKA Z WORKFLOW.md bodu 16 (Robert, 2026-08-27) - viz
                # stejna poznamka u auth_forgot_password vyse. Tady navic
                # heslo uz JE v DB aktivni (predchozi UPDATE) - kdyby
                # e-mail cekal na schvaleni, uzivatel by mel nove heslo
                # nastavene, ale nikde by ho nevidel.
                #
                # try/except (bot3/revize kodu, 2026-09-02): stejny duvod
                # jako auth_forgot_password - vzdy stejna 200 odpoved,
                # chyba jen do logu (heslo uz je zmenene, viz namet vyse).
                try:
                    send_email(
                        user["email"],
                        "Nové heslo — Hliníkový konstrukční stavebnicový systém s drážkami",
                        f"Ahoj,\n\nvyžádal jsi si nové heslo. Tvoje nové heslo (zkopíruj a vlož při přihlášení):\n\n{new_password}\n\nPo přihlášení doporučujeme si ho v appce změnit na vlastní.\nPokud jsi o něj nežádal, tenhle e-mail můžeš ignorovat - tvoje staré heslo přestalo platit, kontaktuj prosím administrátora.",
                    )
                except Exception as e:
                    app.logger.warning("auth_send_temp_password: send_email selhalo pro %s: %s", user["email"], e)
    finally:
        conn.close()
    return jsonify(generic)


# Robert 2026-07-31 (reset hesla za jizdy autem): po nastaveni noveho
# hesla si ho telefon/prohlizec ulozi, ale na login.html pak nedoplni
# e-mail spolu s heslem - protoze reset-password.html samo o sobe zadny
# e-mail nezobrazuje (jen skryty token v URL), prohlizec pri ukladani
# hesla nema, k jakemu uzivatelskemu jmenu ho privazat. Tenhle endpoint
# dovoli reset-password.html zobrazit (needitovatelny) e-mail vedle
# hesla, aby si to prohlizec spravne spojil - vraci JEN e-mail, zadne
# jine udaje, a jen pro platny/nepouzity/nevyprsely token.
@app.get("/api/auth/reset-password-info")
def auth_reset_password_info():
    token = (request.args.get("token") or "").strip()
    if not token:
        return jsonify({"error": "Chybí token."}), 400
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT prt.expires_at, prt.used, u.email FROM password_reset_tokens prt "
                "JOIN app_users u ON u.id = prt.user_id WHERE prt.token=%s",
                (token_hash,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row or row["used"] or row["expires_at"] < datetime.datetime.utcnow():
        return jsonify({"error": "Odkaz je neplatný, použitý nebo vypršel."}), 400
    return jsonify({"email": row["email"]})


@app.post("/api/auth/reset-password")
def auth_reset_password():
    body = request.get_json(silent=True) or {}
    token = (body.get("token") or "").strip()
    password = body.get("password") or ""
    if not token or not password:
        return jsonify({"error": "Chybí token nebo heslo."}), 400
    # Stejna sila hesla jako u registrace (bot13, 2026-08-23) - jinak by
    # reset hesla byl obchazeni policy zavedene v auth_register/remeslo_register.
    pw_err = validate_password_strength(password)
    if pw_err:
        return jsonify({"error": pw_err}), 400

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, user_id, expires_at, used FROM password_reset_tokens WHERE token=%s", (token_hash,))
            row = cur.fetchone()
            if not row or row["used"]:
                return jsonify({"error": "Odkaz je neplatný nebo už byl použitý."}), 400
            if row["expires_at"] < datetime.datetime.utcnow():
                return jsonify({"error": "Odkaz vypršel - vyžádej si prosím nový."}), 400
            cur.execute("UPDATE app_users SET password_hash=%s WHERE id=%s", (generate_password_hash(password), row["user_id"]))
            # K1b (bezpecnostni nalez, bot3/revize kodu 2026-09-02): oznacit
            # VSECHNY nevyuzite reset tokeny uzivatele jako pouzite, ne jen
            # ten prave uplatneny - jinak by starsi nevyprsely token (z
            # predchoziho pozadavku na reset) zustal dal platny.
            cur.execute("UPDATE password_reset_tokens SET used=1 WHERE user_id=%s AND used=0", (row["user_id"],))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


# Robert 2026-07-31 (fotoapka na telefonu, "porad zapominam heslo, chci
# magic prostě přístup bez hesla"): trvaly prihlasovaci odkaz jako
# alternativa k heslu - vygeneruje ho SAM prihlaseny uzivatel pro SVUJ
# ucet (`/api/auth/magic-generate`), ulozi se do domovske obrazovky
# telefonu jako zaloha, kdyz si zapomene/nemuze si prihlasit normalne.
# Token se v DB uklada jen jako SHA256 HASH (stejny princip jako
# password_hash) - i pri uniku DB by nikdo neziskal pouzitelny token.
# VEDOMY KOMPROMIS (jako drive u ?email=&pass= v URL, viz komentar u
# tryUrlLogin v capture.html): odkaz NEVYPRSI, dokud si uzivatel
# nevygeneruje novy (ten stary tim zneplatni) - Robertovo vyslovne
# rozhodnuti prioritizovat pohodlnost, kdyz je na telefonu bez ulozenych
# hesel. Kdokoli se znenim odkazu se prihlasi jako dany uzivatel - proto
# se generuje jen pro AKTUALNE prihlaseneho (nelze vygenerovat pro cizi
# ucet) a zobrazi se jen JEDNOU (znovunacteni stranky uz starý token
# nezobrazi, jen umozni vygenerovat novy).
@app.post("/api/auth/magic-generate")
@login_required
def auth_magic_generate():
    user = current_user()
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE app_users SET magic_token_hash=%s WHERE id=%s", (token_hash, user["id"]))
        conn.commit()
    finally:
        conn.close()
    link = f"{CAPTURE_BASE_URL}/capture.html?magic={token}"
    # Robert 2026-08-08 ("problémy s tím přihlašováním pořád dokola" ->
    # misto vypnuti hesla pro CELY verejne dostupny system radeji trvaly
    # odkaz jen pro jeho ucet): puvodne vraceno jen `link` (pevne
    # smerovany na capture.html) - `token` navic, aby si i jine stranky
    # (admin.html) mohly poskladat vlastni odkaz na sebe
    # (/login.html?magic=<token>&next=...), beze zmeny puvodniho pouziti
    # v capture.html (to porad cte jen `link`).
    return jsonify({"status": "ok", "link": link, "token": token})


@app.post("/api/auth/magic-login")
def auth_magic_login():
    body = request.get_json(silent=True) or {}
    token = (body.get("token") or "").strip()
    if not token:
        return jsonify({"error": "Chybí token."}), 400
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, role, active FROM app_users WHERE magic_token_hash=%s",
                (token_hash,),
            )
            user = cur.fetchone()
    finally:
        conn.close()
    if not user or not user["active"]:
        return jsonify({"error": "Neplatný nebo zneplatněný odkaz."}), 401

    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"status": "ok", "user": {
        "id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"],
    }})


# Robert 2026-08-02 ("pridej do sceny tlacitko na vyexportovani oznacenych
# objektu do fbx pro ulozeni na PC"): scena posle vybrane dily jako
# Wavefront OBJ text (jednoducha, v prohlizeci snadno sestavitelna
# reprezentace trojuhelnikove geometrie ve svetovych souradnicich, mm -
# viz buildObjFromEntries v scene.html), tady se prevede na binarni
# Autodesk FBX; three.js totiz zadny FBX exporter nema, jen loader.
# Vysledek jde zpet jako priloha ke stazeni - ulozi se uzivateli na PC do
# Stazenych. Bezstavove, zadny zapis na disk mimo docasny adresar.
#
# bot2, 2026-08-02 ("export do fbx nefunguje, resp po otevreni je ve scene
# prazdno (pouzivam Rhino)"): puvodni verze prevadela pres CLI `assimp
# export -ffbx` - technicky vratila platny soubor (assimp ho sam bez
# problemu znovu nacetl), ale Rhino (postavene na prisnejsim oficialnim
# Autodesk FBX SDK) v nem nevidelo zadnou geometrii. Znamy, dlouhodobe
# hlaseny nedostatek Assimp FBX EXPORTERU (na rozdil od FBX IMPORTU, ktery
# je zraly a pouziva se jinde v teto appce pro OPACNY smer - nahravani FBX
# profilu/produktu, viz fbx_convert.py). Nahrazeno Blenderem (headless,
# `blender -b --python obj_to_fbx_blender.py -- <obj> <fbx>`) - jeho FBX
# exporter je oborovy standard pro interoperabilitu s Rhino/Unity/Unreal.
# Vyzaduje system balicek `blender` (apt) + `numpy` v systemovem
# python3.12 (`python3.12 -m pip install numpy --break-system-packages`) -
# Blenderuv bpy modul je na Ubuntu sestaveny proti systemovemu pythonu, ne
# proti venv appky, numpy tam proto chybelo a export padal.
BLENDER_OBJ_TO_FBX_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "obj_to_fbx_blender.py"
)


@app.post("/api/export-fbx")
def export_fbx_scene():
    data = request.get_json(force=True, silent=True) or {}
    obj_text = data.get("obj") or ""
    if not obj_text.strip():
        return jsonify({"error": "Prazdny export - zadna geometrie."}), 400
    if len(obj_text) > 50 * 1024 * 1024:
        return jsonify({"error": "Export je prilis velky (limit 50 MB)."}), 413
    try:
        # bot8 2026-09-14: holy prikaz "blender" spolehal na PATH - fungovalo,
        # dokud existoval /usr/local/bin/blender (nebo /usr/bin/blender).
        # Po uklidu "dilny" (2026-09-10, commit d074baea) uz zadny takovy
        # symlink neni, jen versovane /opt/blender-<verze>/blender - presne
        # tohle uz resi blender_render.py::_najdi_blender() (bere nejnovejsi
        # nainstalovanou verzi), export-fbx svou vlastni kopii nemel a tise
        # selhaval na FileNotFoundError. Import az TADY (ne na zacatku
        # souboru) schvalne - blender_render importuje `app` zpet, modulovy
        # import nahore by byl cirkularni; tady uz je blender_render davno
        # nacteny (viz `import blender_render` pozdeji v tomhle souboru).
        from blender_render import BLENDER_BIN
        with tempfile.TemporaryDirectory(prefix="fbx_export_") as td:
            obj_path = os.path.join(td, "export.obj")
            fbx_path = os.path.join(td, "export.fbx")
            with open(obj_path, "w", encoding="utf-8") as f:
                f.write(obj_text)
            proc = subprocess.run(
                [BLENDER_BIN, "-b", "--python", BLENDER_OBJ_TO_FBX_SCRIPT,
                 "--", obj_path, fbx_path],
                capture_output=True, timeout=120)
            if proc.returncode != 0 or not os.path.exists(fbx_path):
                detail = (proc.stdout or proc.stderr or b"").decode("utf-8", "replace")[-800:]
                return jsonify({"error": "Prevod na FBX selhal.", "detail": detail}), 500
            with open(fbx_path, "rb") as f:
                fbx_bytes = f.read()
        fname = "konfigurator_export_" + datetime.date.today().isoformat() + ".fbx"
        return Response(fbx_bytes, mimetype="application/octet-stream",
                        headers={"Content-Disposition": "attachment; filename=" + fname})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Prevod na FBX vyprsel (timeout)."}), 500
    except Exception as e:
        return jsonify({"error": "Prevod na FBX selhal.", "detail": str(e)}), 500


@app.get("/api/health")
def health():
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        finally:
            conn.close()
        return jsonify({"status": "ok", "db": "connected"})
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500


# Ctecka stavu DEPLOY_LOCK.json (koordinace mezi dvema AI agenty na serveru,
# viz /opt/konfigurator/WORKFLOW.md) - jen precte a vrati obsah, nic
# nezapisuje. Pouziva se pro "majak" ve scene.html (LED indikator, ktery
# svити, kdyz prave probiha nasazeni zmen na produkci).
DEPLOY_LOCK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "DEPLOY_LOCK.json")

# Robert 2026-07-24: "pridavej mu tam automaticky geometricka pravidla vse
# co uz znas, a dej mu pristup ke vsem tvarum a souborum, aby mohl ve scene
# s profily plnohodnotne pracovat" - VLASTNOSTI_PROFILU.md je nas "zdroj
# pravdy" pro vsechna potvrzena vyrobni/geometricka pravidla (kompatibilita
# prurezu, definice spoje, oba zpusoby "obraceni" spoje, atd.), prubezne
# doplnovany pri dalsi praci na appce. Misto rucniho prepisovani/kopirovani
# jednotlivych pravidel do system_promptu (nachylne na to, ze se casem
# rozejdou - presne to se stalo, nez byl tenhle nacitac pridan) se cely
# dokument cte PRIMO ZE SOUBORU při KAZDEM pozadavku na /api/ai/generate -
# jakakoli buduci aktualizace dokumentu se tak automaticky projevi ve
# znalostech 3Dbota, bez nutnosti rucne synchronizovat system prompt nebo
# restartovat server.
PROFILE_RULES_DOC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
# 2026-08-31: VLASTNOSTI_PROFILU.md byl rozdelen na rozcestnik + 8
# tematickych souboru (Robert: "je to format vhodny pro dalsi rust?").
# Nacitame ROZCESTNIK + VSECHNY tematicke soubory dohromady, aby 3Dbot
# mel stejny rozsah znalosti jako pred rozdelenim - jeden chybejici
# soubor v tomhle seznamu = tise ochuzeny system prompt, bez chyby.
PROFILE_RULES_DOC_FILES = [
    "VLASTNOSTI_PROFILU.md",
    "PRAVIDLA_SPOJU.md",
    "PROFILY_KATALOG.md",
    "PRISLUSENSTVI_PRIPOJENI.md",
    "TVARY_PREDNASTAVENE.md",
    "TVARY_VLASTNI.md",
    "NASTROJE_SCENY.md",
    "KAROSERIE_UMISTENI.md",
    "KOMPONENTY_EUROBOXY.md",
]


def load_profile_rules_doc():
    parts = []
    for name in PROFILE_RULES_DOC_FILES:
        try:
            with open(os.path.join(PROFILE_RULES_DOC_DIR, name), "r", encoding="utf-8") as f:
                parts.append(f.read())
        except OSError:
            # Jeden chybejici soubor nesmi shodit cely endpoint - 3Dbot
            # dostane aspon zbytek + "zavazna pravidla" primo v promptu.
            continue
    return "\n\n".join(parts)


@app.get("/api/deploy-status")
def deploy_status():
    try:
        with open(DEPLOY_LOCK_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({
            "held_by": data.get("held_by"),
            "since": data.get("since"),
            "note": data.get("note"),
        })
    except Exception:
        # soubor chybi/nejde precist -> ber to jako "zadny deploy neprobiha",
        # nikdy kvuli tomu neshazovat cely endpoint/appku
        return jsonify({"held_by": None, "since": None, "note": None})


def fetch_katalog_parts():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.name, d.layer, d.material_label,
                       d.dim_x_mm, d.dim_y_mm, d.dim_z_mm,
                       d.weight_kg_approx, d.price_czk_approx,
                       d.glb_file, d.thumbnail_file, d.price_source_url, d.price_per_cut_czk,
                       d.color_hex,
                       d.visible_in_scene, spm.shop_product_id, sp.stock_qty,
                       sp.dogus_image_schema_url, sp.visible_in_scene AS sp_visible_in_scene,
                       sp.glb_file AS sp_glb_file, sp.price_czk_placeholder,
                       sp.dogus_url AS sp_dogus_url, sp.is_profile_material AS sp_is_profile_material
                FROM cfg_dily d
                LEFT JOIN (
                    -- Robert: "aktivni linky kusovniku na eshop" - vazba je
                    -- shop_products.cfg_dily_id -> cfg_dily.id (obracene, nez
                    -- potrebujeme), a NENI vynucena UNIQUE v DB - MIN(id)
                    -- je defenzivni pojistka proti pripadnym budoucim
                    -- duplicitam (dnes zadne nejsou, ale schema je nehlida).
                    SELECT cfg_dily_id, MIN(id) AS shop_product_id
                    FROM shop_products
                    WHERE active=1 AND is_archived=0 AND cfg_dily_id IS NOT NULL
                    GROUP BY cfg_dily_id
                ) spm ON spm.cfg_dily_id = d.id
                -- Robert 2026-08-05 ("necht se u produktu ve scene zobrazuje
                -- pocet ks skladem"): druhy JOIN jen kvuli stock_qty KONKRETNI
                -- (MIN(id)) navazane karty - agregacni dotaz vyse nemuze
                -- vratit sloupec z nevybrane radky primo.
                LEFT JOIN shop_products sp ON sp.id = spm.shop_product_id
                ORDER BY d.layer, d.name;
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    parts = []
    for r in rows:
        # bot7, 2026-08-08 (Robert: "je duplicitni... jak vznikla?" -
        # PR10/nova deska se objevovaly v katalogu 2x): kdyz ma cfg_dily
        # radek navazany shop_products dvojnik, KTERY SE SAM O SOBE TAKY
        # ukaze v katalogu (viz "source":"product" smycka nize, stejna
        # podminka visible_in_scene=1 AND glb_file IS NOT NULL), je tenhle
        # cfg_dily "profil" zaznam cisty duplikat s neuplnymi/zastaralymi
        # daty (napr. null rozmery, jina placeholder cena) - vynechat ho.
        # Kdyby dvojnik NEBYL viditelny (deaktivovany produkt apod.),
        # cfg_dily zaznam zustava jedinym zdrojem a musi se ukazat dal.
        if r.get("shop_product_id") and r.get("sp_visible_in_scene") and r.get("sp_glb_file"):
            continue
        dims = [
            float(r["dim_x_mm"]) if r["dim_x_mm"] is not None else None,
            float(r["dim_y_mm"]) if r["dim_y_mm"] is not None else None,
            float(r["dim_z_mm"]) if r["dim_z_mm"] is not None else None,
        ]
        # Delka vs prurez: delsi rozmer objektu je vzdy delka (stejna konvence
        # jako pouziva frontend pro vyber osy konektoru - nejdelsi osa = konce
        # profilu). Zbyle dva rozmery jsou prurez, vzestupne serazene.
        if all(d is not None for d in dims):
            dims_sorted = sorted(dims)
            length_mm = dims_sorted[2]
            cross_section_mm = [dims_sorted[0], dims_sorted[1]]
        else:
            length_mm = None
            cross_section_mm = [None, None]
        parts.append({
            "id": r["id"],
            "name": r["name"],
            "layer": r["layer"],
            "material_label": r["material_label"],
            "dims_mm": dims,
            "length_mm": length_mm,
            "cross_section_mm": cross_section_mm,
            "weight_kg_approx": float(r["weight_kg_approx"]) if r["weight_kg_approx"] is not None else None,
            # Robert 2026-08-29 ("proč se má dělat přepočet cen ve 3D
            # timerem? prostě ať se čte ze stejné tabulky v DB jen se
            # přidá koeficient") - živý výpočet z shop_products.price_
            # czk_placeholder (1 ks e-shop profilu = 3000 mm, cena/1m
            # pro scénu = cena_eshop/3, čistě délkový převod, žádný
            # obchodní koeficient navíc). cfg_dily.price_czk_approx
            # zůstává jen fallback pro budoucí profil bez napárovaného
            # shop_products řádku (dnes napárováno všech 24).
            "price_czk_approx_PLACEHOLDER": round(float(r["price_czk_placeholder"]) / 3.0, 2) if r.get("price_czk_placeholder") is not None else (float(r["price_czk_approx"]) if r["price_czk_approx"] is not None else None),
            # Robert 2026-08-11 ("obarvil jsem ale nebylo to trvale, novy se
            # objevil neobarveny") - vychozi barva pro scenu i u profilu
            # (produkty ji mely uz drive), viz sql/2026-08-11_cfg_dily_color_hex.sql
            "color_hex": r.get("color_hex"),
            "file": r["glb_file"],
            # Robert 2026-08-08 ("obrazky jako tlacitka" - novy obrazkovy
            # panel katalogu): auto-generovany 3D nahled (viz katalog_
            # thumbnail_upload nize), relativni cesta pod /katalog/ (stejny
            # nginx alias jako GLB soubory) - None dokud jeste nevygenerovano.
            "thumbnail_file": r.get("thumbnail_file"),
            "price_source_url": r.get("price_source_url"),
            "price_per_cut_czk": float(r["price_per_cut_czk"]) if r.get("price_per_cut_czk") is not None else None,
            # bot1, 2026-07-27: nahrazuje pevne zadratovany VISIBLE_CATALOG_IDS
            # Set v scene.html - viditelnost dilu ve 3D scene je ted rizena z
            # DB (admin FBX upload ji nastavi na 1 pri uspesnem prevodu).
            "visible_in_scene": bool(r.get("visible_in_scene")),
            # Robert: "aktivni linky kusovniku na eshop" - vyplneno jen kdyz
            # existuje odpovidajici aktivni shop_products radek (viz JOIN
            # vyse); frontend (scene.html/nabidka-online.html) na null
            # jednoduse nevykresli odkaz, zadna specialni obsluha netreba.
            "shop_product_id": r.get("shop_product_id"),
            # Robert 2026-08-05: pocet ks skladem - jen kdyz je dil navazany
            # na aktivni shop_products kartu (viz JOIN vyse), jinak None
            # (interni/pomocny profil bez skladove evidence).
            "stock_qty": r.get("stock_qty"),
            # bot7, 2026-08-08 ("toto není realný řez, ale zejdodušený model,
            # reálné fotky jsou přece stažené z Dogusu"): skutecny technicky
            # nakres prurezu (leva polovina obrazku, viz dogus_image_schema_url
            # v shop_products - pro profily je to "combined" obrazek: schema
            # vlevo + foto vpravo, vytazeno crawlerem v
            # scripts/2026-08-08_dogus_pairing_crawl.py) pro panel realnych
            # prurezu ve scene.html - nahrazuje drivejsi vypocitanou GLB
            # siluetu (ta zustava jen jako fallback pro profily bez parovani).
            "dogus_image_schema_url": r.get("dogus_image_schema_url"),
            # bot2, 2026-07-28: rozliseni profil/produkt pro strom kategorii
            # ve scene.html (viz nize) - profily zustavaji ve sve puvodni
            # "layer" skupine (alu/black/zinc), produkty se radi podle
            # content_categories (category_id).
            "source": "profil",
            "category_id": None,
            # Robert 2026-10-01: "koeficient pro scenu se tyka jen profilu a
            # produktu, ktere se nacitaji z dogusu" - /api/katalog nasobi
            # scene_price_coefficient JEN dily s timto priznakem. cfg_dily:
            # napárovaná karta je profil nebo z Dogusu; bez karty profil
            # podle nazvu (cena z price_czk_approx, vzorek "Profil ...").
            "scene_coef": bool(r.get("sp_is_profile_material")) or bool(r.get("sp_dogus_url"))
                          or (not r.get("shop_product_id") and str(r.get("name") or "").lower().startswith("profil")),
        })

    # bot2, 2026-07-28 (Robert: "nekterym produktum budeme pridavat fbx
    # model k uploadu (obdobne jako pro profily), polozka(produkt) ktery
    # bude mit fbx model, se nasledne pusti do 3D sceny do katalogu, ten
    # tam musime zaroven s tim zacit rozvetvovat do kategorii at je v tom
    # prehled") - produkty (shop_products) s nahranym+prevedenym FBX
    # modelem (visible_in_scene=1) se pridaji do stejneho katalogu jako
    # profily, ale se zdrojem "product" a category_id navazanym na
    # content_categories, aby je scene.html mohla zaradit do stromu
    # kategorii (viz /api/categories) misto ploche "layer" skupiny.
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, sku, category_id, category_path,
                       weight_g, price_czk_placeholder, glb_file, thumbnail_file, color_hex,
                       unit,
                       is_board_material, board_sheet_width_mm, board_sheet_height_mm,
                       accessory_conn_enabled, uhelnik_pose, stock_qty, place_vertical,
                       attach_mode, attach_offset_mm, geo_faces_json, attach_pose,
                       dogus_url, is_profile_material
                FROM shop_products
                WHERE visible_in_scene=1 AND glb_file IS NOT NULL
                ORDER BY name;
            """)
            product_rows = cur.fetchall()
    finally:
        conn.close()

    for r in product_rows:
        # bot1, 2026-07-28 (Robert: "nachystej abych mohl odklikat, ktere
        # spoje jsou funkcni, ostatni zrusis") - accessory_conn_enabled je
        # JSON pole indexu (0-6) konektoru z computeConnectorsLocal, ktere
        # Robert v pripadove revizi ve scene oznacil jako SKUTECNE pouzitelne
        # rovne montazni plochy. None/chybi = jeste nezkontrolovano, scene.html
        # pak nabizi vsech 6 (puvodni chovani).
        accessory_conn_enabled = None
        raw_flags = r.get("accessory_conn_enabled")
        if raw_flags:
            try:
                accessory_conn_enabled = raw_flags if isinstance(raw_flags, list) else json.loads(raw_flags)
            except Exception:
                accessory_conn_enabled = None
        # bot1, 2026-08-04 (Robert: "musi to jit napevno na server, vzdy -
        # ja ucim konfigurator pro uzivatele"): uhelnik_pose = naucena
        # poloha uhelniku pro UhelnikAut (face + kvaternion relativne k
        # ramci rohu), odklikana v panelu Pozice uhelniku - sdilena pro
        # vsechny uzivatele/prohlizece, stejny princip jako
        # accessory_conn_enabled vyse.
        attach_pose = None
        raw_apose = r.get("attach_pose")
        if raw_apose:
            try:
                attach_pose = raw_apose if isinstance(raw_apose, dict) else json.loads(raw_apose)
            except Exception:
                attach_pose = None
        uhelnik_pose = None
        raw_pose = r.get("uhelnik_pose")
        if raw_pose:
            try:
                uhelnik_pose = raw_pose if isinstance(raw_pose, dict) else json.loads(raw_pose)
            except Exception:
                uhelnik_pose = None
        # CENA DESKY MUSI JIT DO SCENY V Kc/m2. Robert 2026-08-07: "u
        # deskovych materialu se cena zadava za 1m2" - scena to tak i pocita
        # (currentWeightPrice v scene.html: `part.price_czk * areaM2`).
        # Jenze v katalogu jsou desky ULOZENE ruzne: MDF (3939) ma unit='m2',
        # ale PR10 (3539) a laminovana (3671) maji unit='ks' a cenu za CELOU
        # TABULI. Scena o jednotce nevedela (sloupec se sem ani nedotazoval)
        # a nasobila plochou i cenu tabule.
        #
        # Zmereno 2026-09-10:
        #   PR10        3093,75 Kc/tabuli 1250x2500 (3,125 m2)
        #               -> scena uctovala 3093,75 Kc/m2 misto 990,00 = 3,1x vic
        #   laminovana  4062,50 Kc/tabuli 2070x2800 (5,796 m2)
        #               -> scena uctovala 4062,50 Kc/m2 misto 700,91 = 5,8x vic
        #
        # Prepocet se dela TADY, ne ve scene: scena uz spravnou jednotku
        # ocekava, jen ji nedostavala. `price_basis` rika, co se stalo, aby
        # to slo poznat i zvenci.
        cena = float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None
        jednotka = (r.get("unit") or "").strip().lower() or None
        zaklad_ceny = jednotka
        if r["is_board_material"] and cena is not None and jednotka != "m2":
            sirka, vyska = r.get("board_sheet_width_mm"), r.get("board_sheet_height_mm")
            plocha_m2 = (float(sirka) * float(vyska) / 1e6) if (sirka and vyska) else None
            if plocha_m2 and plocha_m2 > 0:
                cena = round(cena / plocha_m2, 4)
                zaklad_ceny = "m2_z_tabule"
            else:
                # Bez rozmeru tabule prepocet nejde. Nechavame cenu, jak je,
                # ale rekneme to nahlas - scena by jinak tise uctovala cenu
                # kusu za kazdy metr.
                zaklad_ceny = "neznamy_prepocet_nelze"
        parts.append({
            "id": f"product_{r['id']}",
            "name": r["name"],
            "layer": "produkt",
            "material_label": None,
            "dims_mm": [None, None, None],
            "length_mm": None,
            "cross_section_mm": [None, None],
            "weight_kg_approx": float(r["weight_g"]) / 1000 if r["weight_g"] is not None else None,
            "price_czk_approx_PLACEHOLDER": cena,
            "unit": jednotka,
            "price_basis": zaklad_ceny,
            "file": r["glb_file"],
            "thumbnail_file": r.get("thumbnail_file"),
            "price_source_url": None,
            "price_per_cut_czk": None,
            "visible_in_scene": True,
            # Robert 2026-08-07 ("potřebuji dát produktu barvu ve scéně, aby
            # se objevil rovnou zbarvený", jen konkretni produkty): vychozi
            # barva pro 3D scenu, nastavitelna v adminu u karty produktu -
            # NULL = beze zmeny (dnesni chovani, barva podle "layer").
            "color_hex": r.get("color_hex"),
            # bot7, 2026-08-07 ("postavit 2D protahovani pro desky"): rika
            # scene.html, ze ma pro tenhle dil pouzit computeBoardEdgeConnectors()
            # (4 hranove konektory, 2 nezavisle protahovaci osy sirka+vyska)
            # misto bezneho computeConnectorsLocal() (1 delkova osa jako profil).
            "is_board_material": bool(r.get("is_board_material")),
            # Robert 2026-08-08 ("dej do skladových karet deskový materiálů
            # ten formát tabule k vyplňování"): referencni rozmer CELE
            # tabule, ze ktere se rezou kusy - informativni/pro budouci
            # vypocet odpadu, scene.html ho zatim jen posle dal (nepocita
            # s nim, viz currentBoardDimsMm - to je rozmer VYREZANEHO kusu).
            "board_sheet_width_mm": r.get("board_sheet_width_mm"),
            "board_sheet_height_mm": r.get("board_sheet_height_mm"),
            "source": "product",
            # koeficient sceny jen profily a produkty z Dogusu (Robert
            # 2026-10-01) - ne desky/euroboxy/Vandr/DIL-* z importu apod.
            "scene_coef": bool(r.get("is_profile_material")) or bool(r.get("dogus_url")),
            "category_id": r["category_id"],
            "category_path": r["category_path"],
            "accessory_conn_enabled": accessory_conn_enabled,
            "uhelnik_pose": uhelnik_pose,
            # Robert 2026-08-15: plna poza pro corner_side (viz
            # /attach-pose endpoint nize).
            "attach_pose": attach_pose,
            # bot1 2026-08-04 (Robert: "proc nema rozek ve scene SKU a
            # uhelnik ano?") - SKU se dosud do sceny vubec neposilalo;
            # u nekterych produktu bylo jen nahodou soucasti nazvu.
            "sku": r.get("sku"),
            # Robert: "aktivni linky kusovniku na eshop" - tenhle dil UZ JE
            # primo shop_products radek (na rozdil od profilu vyse, kde se
            # hledalo pres cfg_dily_id) - odkaz je proste jeho vlastni id.
            "shop_product_id": r["id"],
            # Robert 2026-08-05: pocet ks skladem - tenhle dil UZ JE primo
            # shop_products radek, takze stock_qty je primo z dotazu vyse.
            "stock_qty": r.get("stock_qty"),
            # Robert 2026-08-09 ("toto bych potreboval natocit kulatinou
            # nahoru" - napr. "Kovová patka M8x50"): vychozi orientace pri
            # vlozeni ze sceny (placeAtOrigin) je jinak vzdy "horizontal"
            # (lezi na zemi) - pro nektere male dily (paticky, sroubovaci
            # patky) davaji vetsi smysl "svisle" tak, jak byly exportovany
            # z CAD. Nastavitelne per-produkt v adminu (checkbox u karty).
            "place_vertical": bool(r.get("place_vertical")),
            # Robert 2026-08-12 ("musim te naucit osazovat profily
            # prislusenstvim... pripravit klikaci prostredi pro odklikavani
            # spravnych postupu"): explicitni rezim napojeni pro Place All -
            # 'corner' | 'corner3' | 'endcap' | 'wall' | 'none' | None (jeste
            # nenauceno, padne zpet na drivejsi hadani podle nazvu, viz
            # isEndCapPart ve scene.html).
            "attach_mode": r.get("attach_mode"),
            # Robert 2026-08-12 ("cep potrebuje byt zanoreny castecne do
            # profilu, protoze tam je zasroubovany... tyto pozice
            # potrebuji tlacitkem potvrdit"): signed odsazeni (mm) podel
            # osy pripojeni, aplikuje se az PO standardnim osazeni.
            "attach_offset_mm": float(r["attach_offset_mm"]) if r.get("attach_offset_mm") is not None else 0.0,
            # Robert 2026-08-12 ("tlacitko ktere oznaci plochy objektu
            # podle geometrie a ja to levym klikem jen potvrdim"): rovinne
            # plochy zjistene ze skutecne mesh geometrie (ne z 6 pevnych
            # smeru obalky) - pole {x,y,z,nx,ny,nz} v lokalnim prostoru dilu.
            "geo_faces": json.loads(r["geo_faces_json"]) if r.get("geo_faces_json") else None,
        })

    # bot8, 2026-08-21 (Robert: "do tvaru sceny" / "ok nebo do katalogu, to
    # je jedno" - strom Znacka->Model->Karoserie z 2026-08-05, viz
    # sql/2026-08-05_car_bodies.sql, mel do dneska jen backend/DB, nikdy
    # nebyl napojeny do /api/katalog, takze karoserie NESLY vubec vlozit
    # do sceny ani do Vlastnich tvaru). id prefix "car_body_" odlisuje od
    # "product_"/cfg_dily profilu - source "car_body" pro pripadne
    # rozliseni ve scene.html (zatim se chova jako obycejny produkt).
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cb.id, cb.name AS body_name, cb.glb_file, cb.model_id,
                       cm.name AS model_name, mk.name AS make_name
                FROM car_bodies cb
                JOIN car_models cm ON cm.id = cb.model_id
                JOIN car_makes mk ON mk.id = cm.make_id
                WHERE cb.glb_file IS NOT NULL
                ORDER BY mk.sort_order, mk.name, cm.sort_order, cm.name, cb.sort_order, cb.name;
            """)
            body_rows = cur.fetchall()
    finally:
        conn.close()

    # bot8, 2026-08-21: NEpridavat tu vlastni ?v= cache-buster - frontend uz
    # kazdemu p.file jednotne pripojuje "?v=" + CACHE_BUST (Date.now() pri
    # nacteni stranky, viz scene.html ~radek 2669), pridani DRUHEHO ?v() by
    # jen vyrobilo zdvojeny query string. Puvodni podezreni na chybejici
    # cache-busting u car_bodies bylo mylne - frontend cache-bustuje VSECHNY
    # katalogove soubory uz dneska.
    for r in body_rows:
        parts.append({
            "id": f"car_body_{r['id']}",
            "name": f"{r['make_name']} {r['model_name']} - {r['body_name']}",
            # bot8 2026-09-06 (URGENTNI regrese): koty karoserie v
            # webapp/js/scene/hdri-panels-ui.js (groupCarBodyEntriesByBase
            # a navazane funkce) drive ziskavaly kod karoserie parsovanim
            # "[XXNN]" z tohoto "name" retezce - vendor kod uz neni
            # stabilni (prejmenovan na vlastni K-0XX schema), misto
            # parsovani textu se pouziva primo tenhle sloupec.
            "car_model_id": r["model_id"],
            "layer": "auto",
            "material_label": None,
            "dims_mm": [None, None, None],
            "length_mm": None,
            "cross_section_mm": [None, None],
            "weight_kg_approx": None,
            "price_czk_approx_PLACEHOLDER": None,
            "file": r["glb_file"],
            "thumbnail_file": None,
            "price_source_url": None,
            "price_per_cut_czk": None,
            "visible_in_scene": True,
            "color_hex": None,
            "is_board_material": False,
            "board_sheet_width_mm": None,
            "board_sheet_height_mm": None,
            "source": "car_body",
            "scene_coef": False,
            "category_id": None,
            "category_path": None,
            "accessory_conn_enabled": None,
            "uhelnik_pose": None,
            "attach_pose": None,
            "sku": None,
            "shop_product_id": None,
            "stock_qty": None,
            "place_vertical": False,
            "attach_mode": None,
            "attach_offset_mm": 0.0,
            "geo_faces": None,
        })

    return parts


# Koeficient navyseni cen v KONFIGURATORU oproti webovym cenam (Robert
# 2026-08-19: "potrebuji novy specialni koeficient, ktery navysi ceny v
# konfiguratoru oproti cenam s webu"). SAMOSTATNY od
# dogus_price_coefficient - ten prepocitava nakupni USD ceny Doguskalip
# na nase prodejni a je per-kategorie; tenhle je JEDEN GLOBALNI a resi
# neco jineho: stejny dil vyjde ve 3D scene draz nez na e-shopu.
#
# Rozhodnuti Roberta 2026-08-19 (na muj dotaz pred implementaci):
#   1. JEDEN globalni koeficient (ne per-kategorie).
#   2. Nasobi se JEN ceny dilu (materialu). Priplatky - cena rezu
#      (price_per_cut_czk), pausal za profil, cena spoju a spojovaci
#      material - zustavaji BEZE ZMENY: nastavuji se zvlast v Cenotvorbe
#      a nemaji obdobu na webu, takze neni vuci cemu je navysovat.
#   3. Projevi se v souhrnu ve scene I ve vygenerovane nabidce (aby
#      zakaznik nevidel jinou castku na obrazovce a jinou v nabidce).
#   4. (Robert 2026-10-01) "koeficient pro scenu se tyka jen profilu a
#      produktu, ktere se nacitaji z dogusu" - nasobi se jen dily s
#      priznakem scene_coef (profil / karta s dogus_url), viz katalog().
#      Desky, euroboxy, Vandr dily, DIL-* karty z importu apod. jdou do
#      sceny v zakladni cene. Hodnota je dnes 1,25 (od 2026-09-25, driv 1,4).
#      Pri ZMENE ROZSAHU (scene_coef) uprav i SCENE_PRICE_COEF_SCOPE v
#      api/admin_settings.py a texty v admin.html / admin/js/ceny.js (bot16)
#      a ulozene ceny prepocitej (scripts/2026-10-01_bot8_prepocet_koef_
#      profily_dogus.py - vzor; price_summary.scene_price_coefficient_scope).
SCENE_PRICE_COEF_KEY = "scene_price_coefficient"


def get_scene_price_coefficient(cur):
    """Koeficient pro ceny dilu ve 3D scene. 1.0 = zadne navyseni
    (vychozi). Nesmyslna/nectena hodnota se schvalne chova jako 1.0 -
    cenotvorba nikdy nesmi spadnout na tom, ze v nastaveni je preklep."""
    raw = get_setting(cur, SCENE_PRICE_COEF_KEY, "1")
    try:
        coef = float(raw)
    except (TypeError, ValueError):
        return 1.0
    return coef if coef > 0 else 1.0


@app.get("/api/katalog")
@staff_required
def katalog():
    # Koeficient se aplikuje TADY, ne uvnitr fetch_katalog_parts() -
    # tu sdili i /api/admin/profily (tabulka cen, kde admin ZADAVA
    # zakladni cenu; navysena hodnota by se pri ulozeni zafixovala a
    # navyseni by se pak nascitavalo) a support_ai.py (chatbot rika
    # zakaznikovi bezne ceny). /api/katalog konzumuje VYHRADNE
    # webapp/scene.html (CATALOG_URL), takze je to presne to jedno
    # misto, kde cena vstupuje do konfiguratoru.
    parts = fetch_katalog_parts()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            coef = get_scene_price_coefficient(cur)
    finally:
        conn.close()
    if coef != 1.0:
        for p in parts:
            base = p.get("price_czk_approx_PLACEHOLDER")
            # Robert 2026-10-01: "koeficient pro scenu se tyka jen profilu a
            # produktu, ktere se nacitaji z dogusu" (priznak scene_coef z
            # fetch_katalog_parts) - ostatni dily jdou do sceny v zakladni cene
            if base is not None and p.get("scene_coef"):
                p["price_czk_approx_PLACEHOLDER"] = round(base * coef, 2)
            # price_per_cut_czk (cena rezu) se ZAMERNE nenasobi - je to
            # priplatek za praci, ne cena materialu (rozhodnuti vyse).
    # koeficient se vraci i klientovi, aby sel zobrazit v prehledu ceny
    # (scene.html) - ne kvuli vypoctu, ten uz je hotovy vyse
    return jsonify({"parts": parts, "count": len(parts), "price_coefficient": coef})


KATALOG_THUMBNAIL_DIR = os.path.join(KATALOG_GLB_DIR, "thumbnails")
os.makedirs(KATALOG_THUMBNAIL_DIR, exist_ok=True)
CATALOG_THUMBNAIL_MAX_BYTES = 5 * 1024 * 1024


# Robert 2026-08-08 ("obrazky jako tlacitka" - novy obrazkovy plovouci
# panel katalogu vedle stavajiciho stromu): jeden auto-generovany 3D nahled
# na dil (screenshot ze sceny, viz scene.html generateCatalogThumbnails),
# NE plnohodnotna fotogalerie - proto samostatny jednoduchy endpoint mimo
# api/gallery_items.py. Duvod, proc nejde pouzit gallery_items.py beze
# zmeny: jeho owner_id se parsuje jako `int(...)` (gallery_items.py:242),
# ale cfg_dily.id je VARCHAR (napr. "alu_40x40") - novy endpoint tak misto
# owner_type/owner_id bere primo `part_id` (stejny format jako CATALOG[].id
# v scene.html - "product_<int>" pro shop_products, jinak cfg_dily.id) a
# sam rozhodne cilovou tabulku/sloupec. Soubory jdou do stejne slozky/nginx
# aliasu jako GLB modely (KATALOG_GLB_DIR/thumbnails/), zadna zmena
# nginx configu netreba - presne stejny vzor jako CAR_GLB_DIR vyse.
@app.post("/api/catalog-thumbnail")
@staff_required
def catalog_thumbnail_upload():
    part_id = (request.form.get("part_id") or "").strip()
    if not part_id:
        return jsonify({"error": "Chybí part_id."}), 400
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    # QA nalez (2026-09-05): chybel limit velikosti (nginx client_max_body_size
    # 50M je jen hruby sdileny strop pro cely vhost, ne specificky pro tenhle
    # maly nahled).
    if request.content_length and request.content_length > CATALOG_THUMBNAIL_MAX_BYTES:
        return jsonify({"error": "Soubor je příliš velký."}), 413
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png"):
        ext = ".jpg"

    if part_id.startswith("product_"):
        try:
            real_id = int(part_id[len("product_"):])
        except ValueError:
            return jsonify({"error": "Neplatné part_id."}), 400
        table, id_col, id_val = "shop_products", "id", real_id
    else:
        table, id_col, id_val = "cfg_dily", "id", part_id

    stored_name = f"{_slugify(part_id)}{ext}"
    f.save(os.path.join(KATALOG_THUMBNAIL_DIR, stored_name))
    # Konzistentni s glb_file konvenci - relativni cesta UVNITR KATALOG_GLB_DIR,
    # BEZ "katalog/" prefixu (ten si pridava az klient, viz CATALOG map ve
    # scene.html: "katalog/" + p.thumbnail_file).
    rel_path = f"thumbnails/{stored_name}"

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {id_col} FROM {table} WHERE {id_col}=%s", (id_val,))
            if not cur.fetchone():
                return jsonify({"error": f"Díl {part_id} neexistuje."}), 404
            cur.execute(f"UPDATE {table} SET thumbnail_file=%s WHERE {id_col}=%s", (rel_path, id_val))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "thumbnail_file": rel_path})


# Robert 2026-07-28 ("nachystej abych mohl odklikat, ktere spoje jsou
# funkcni, ostatni zrusis"): scene.html dostane novy panel "Kontrola ploch
# prislusenstvi" - pro vybrany produkt (uhelnik/spojka) ukaze vsech 6 jeho
# univerzalnich bbox konektoru (viz computeConnectorsLocal), Robert
# vizualne posoudi ktere jsou skutecne rovne pouzitelne montazni plochy a
# ulozi vyber sem. Pristupne kazdemu prihlasenemu (stejny vzor jako
# /api/custom-shapes) - neni to admin-only akce, resi se primo ze sceny.
@app.post("/api/products/<int:product_id>/connector-flags")
@staff_required
def product_connector_flags(product_id):
    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled")
    if not isinstance(enabled, list) or not all(isinstance(x, int) for x in enabled):
        return jsonify({"error": "Očekávám pole celých čísel 'enabled' (indexy konektorů 0-6)."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE shop_products SET accessory_conn_enabled=%s WHERE id=%s",
                (json.dumps(enabled), product_id),
            )
            if cur.rowcount == 0:
                # rowcount muze byt 0 i kdyz radek existuje a hodnota se
                # nezmenila (MySQL specifikum) - overit existenci zvlast
                cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
                if cur.fetchone() is None:
                    return jsonify({"error": "Produkt nenalezen."}), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": product_id, "enabled": enabled})


# bot1, 2026-08-04 (Robert: "musi to jit napevno na server, vzdy"):
# ulozeni naucene polohy uhelniku pro UhelnikAut - zrcadlo
# connector-flags vyse. pose = {face: int, q: [4 cisla]} (kvaternion
# relativne k ramci rohu, viz scene.html uhelnikCornerFrameQuat).
@app.post("/api/products/<int:product_id>/geo-faces")
@staff_required
def product_geo_faces(product_id):
    """Robert 2026-08-12 ("u nekterych dilu potrebuji tlacitko, ktere
    oznaci plochy objektu podle geometrie a ja to levym klikem jen
    potvrdim - myslim behem uceni [napojeni]"): ulozi seznam skutecnych
    rovinnych ploch zjistenych z mesh geometrie (viz detectGeometricFaces
    ve scene.html) - kazda potvrzena klikem primo na dilu ve scene.
    Prazdne pole/null = zrusit (padne zpet na 6 box-connectoru)."""
    data = request.get_json(silent=True) or {}
    faces = data.get("faces")
    if faces is not None:
        if not isinstance(faces, list) or len(faces) > 64:
            return jsonify({"error": "Očekávám pole ploch (max 64)."}), 400
        for f in faces:
            if not (isinstance(f, dict) and all(k in f for k in ("x", "y", "z", "nx", "ny", "nz"))
                    and all(isinstance(f[k], (int, float)) for k in ("x", "y", "z", "nx", "ny", "nz"))):
                return jsonify({"error": "Neplatný formát plochy (očekávám x,y,z,nx,ny,nz)."}), 400
    payload = json.dumps(faces) if faces else None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE shop_products SET geo_faces_json=%s WHERE id=%s", (payload, product_id))
            if cur.rowcount == 0:
                cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
                if cur.fetchone() is None:
                    return jsonify({"error": "Produkt nenalezen."}), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": product_id, "faces": faces})


@app.post("/api/products/<int:product_id>/attach-offset")
@staff_required
def product_attach_offset(product_id):
    """Robert 2026-08-12 ("cep potrebuje byt zanoreny castecne do
    profilu, protoze tam je zasroubovany - tyto pozice potrebuji
    tlacitkem potvrdit, potom uz je to na tobe"): ulozi PRESNE odsazeni
    (mm) dilu od standardni "naplocho" pozice pri automatickem osazeni
    volneho cela (Place All). Kladne = dal ven, zaporne = zanoreno do
    profilu. Sdilene pro vsechny uzivatele, stejny princip jako
    attach_mode/uhelnik_pose."""
    data = request.get_json(silent=True) or {}
    try:
        offset_mm = float(data.get("offset_mm"))
    except (TypeError, ValueError):
        return jsonify({"error": "Očekávám číslo 'offset_mm'."}), 400
    if not (-200 <= offset_mm <= 200):
        return jsonify({"error": "Odsazení mimo rozumný rozsah (-200 až 200 mm)."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE shop_products SET attach_offset_mm=%s WHERE id=%s", (offset_mm, product_id))
            if cur.rowcount == 0:
                cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
                if cur.fetchone() is None:
                    return jsonify({"error": "Produkt nenalezen."}), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": product_id, "offset_mm": offset_mm})


@app.post("/api/products/<int:product_id>/attach-pose")
@staff_required
def product_attach_pose(product_id):
    """Robert 2026-08-15 ("ta pozice se mela ulozit vuci tem dvema
    profilum"): plna naucena poza pro rezim corner_side - pozice [mm]
    a rotace (quaternion) RELATIVNE k lokalnimu ramu rohu dvou kolmych
    profilu (pocatek = prusecik os, osy = smery profilu + bocni
    normala, viz cornerSideFrame ve scene.html). Place All pak pozu
    prehraje na kazdem takovem rohu. Sdilene pro vsechny uzivatele,
    stejny princip jako uhelnik_pose."""
    data = request.get_json(silent=True) or {}
    pose = data.get("pose")
    if pose is not None:
        ok = (isinstance(pose, dict)
              and isinstance(pose.get("pos"), list) and len(pose["pos"]) == 3
              and all(isinstance(v, (int, float)) for v in pose["pos"])
              and isinstance(pose.get("q"), list) and len(pose["q"]) == 4
              and all(isinstance(v, (int, float)) for v in pose["q"]))
        if not ok:
            return jsonify({"error": "Očekávám pose {pos:[3 čísla mm], q:[4 čísla]} nebo null."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE shop_products SET attach_pose=%s WHERE id=%s",
                        (json.dumps(pose) if pose is not None else None, product_id))
            if cur.rowcount == 0:
                cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
                if cur.fetchone() is None:
                    return jsonify({"error": "Produkt nenalezen."}), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "attach_pose": pose})


@app.post("/api/products/<int:product_id>/attach-mode")
@staff_required
def product_attach_mode(product_id):
    """Robert 2026-08-12 ("klikaci prostredi pro odklikavani spravnych
    postupu, postupne pro vsechny produkty katalogu") - ulozi, JAK se
    ma dil automaticky napojovat (Place All): roh mezi profily, volne
    celo profilu, nebo jen rucne. Sdilene pro vsechny uzivatele/
    prohlizece, stejny princip jako accessory_conn_enabled/uhelnik_pose."""
    data = request.get_json(silent=True) or {}
    mode = data.get("mode")
    # Robert 2026-08-16 (VLASTNOSTI_PROFILU.md 2ao, potvrzeno na testovaci
    # sestave) - "parallel_side" (dva DOTYKAJICI se rovnobezne profily,
    # NE mezera - puvodni "parallel_bridge" s mezerou bylo spatne a
    # vraceno zpet), stejny princip jako corner_side (dil spojuje DVA
    # profily), jen bez spolecneho rohu.
    if mode not in ("corner", "corner_side", "corner3", "endcap", "wall", "parallel_side", "none", None):
        return jsonify({"error": "Neplatný režim (očekávám corner/corner_side/corner3/endcap/wall/parallel_side/none/null)."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE shop_products SET attach_mode=%s WHERE id=%s", (mode, product_id))
            if cur.rowcount == 0:
                cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
                if cur.fetchone() is None:
                    return jsonify({"error": "Produkt nenalezen."}), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": product_id, "mode": mode})


@app.post("/api/products/<int:product_id>/uhelnik-pose")
@staff_required
def product_uhelnik_pose(product_id):
    data = request.get_json(silent=True) or {}
    pose = data.get("pose")
    ok = (
        isinstance(pose, dict)
        and isinstance(pose.get("face"), int)
        and isinstance(pose.get("q"), list)
        and len(pose["q"]) == 4
        and all(isinstance(x, (int, float)) for x in pose["q"])
    )
    if not ok:
        return jsonify({"error": "Očekávám objekt 'pose' {face: int, q: [4 čísla]}."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE shop_products SET uhelnik_pose=%s WHERE id=%s",
                (json.dumps(pose), product_id),
            )
            if cur.rowcount == 0:
                cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
                if cur.fetchone() is None:
                    return jsonify({"error": "Produkt nenalezen."}), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": product_id, "pose": pose})


# Robert 2026-07-24 ("promysli do hloubky moznosti magnetovani..."): klient
# (magnet/snap detekce ve scene.html, viz VLASTNOSTI_PROFILU.md sekce 2k)
# potrebuje ZNAT stejnou tabulku kompatibility prurezu jako AI generator,
# aby mohl zivě filtrovat nabizena napojeni. Vraci syrova data primo z
# PROFILE_JOIN_PAIRS (jediny zdroj pravdy, zadna duplicitni kopie tabulky).
# Robert 2026-08-12 ("dal jsem F5 a scena se rozbila" - cerna plocha):
# scena bezi cela v prohlizeci, takze jeji chyby server normalne vubec
# nevidi a diagnoza vyzadovala rucni otevreni konzole. Tenhle endpoint
# jen zaloguje prvni JS chyby z okna sceny (viz window.onerror ve
# scene.html) - ctitelne pres `journalctl -u konfigurator`.
@app.post("/api/client-error")
def client_error_log():
    b = request.get_json(silent=True) or {}
    app.logger.warning(
        "[scene-js] %s | %s:%s:%s | %s",
        str(b.get("message"))[:300], str(b.get("source"))[:120],
        b.get("line"), b.get("col"), str(b.get("stack"))[:600],
    )
    return jsonify({"status": "ok"})


@app.get("/api/join-rules")
@staff_required
def join_rules():
    pairs = [sorted(pair) for pair in PROFILE_JOIN_PAIRS]
    return jsonify({"pairs": pairs})


# --- Vlastni tvary (custom shapes) - Robert: "na scene si nakreslim nejaky
# objekt, oznacim ho, CTRL+S ulozi tento vyber jako novy prednastaveny tvar,
# system si vyzada jeho nazev a zalozi jej jako nove tlacitko v panelu
# 'Vlastni tvary'; klik na tlacitko vlozi ulozeny objekt do sceny" (2026-07-24).
# Kazdy dil vyberu se uklada jako part_id + position/quaternion/scale (+
# volitelne color/used_conn), viz frontend serializace pri Ctrl+S. Tabulka
# custom_shapes: id, name, data (JSON pole dilu), created_by, created_at.
#
# Robert 2026-07-25 ("musi se prenest veskere vlastnosti a spojitosti, tzn i
# pocet spoju se uklada"): `data` sloupec ted muze obsahovat i pocet
# JIZ ZAPOCITANYCH spoju (joint_count) na kazdem dilu + krizove odkazy MEZI
# dily (lic_peers - Licovani/Najdi-spoje spojeni; join_groups - Join/J
# skupiny; frame_groups - Ctverec/ram metadata pro modre sipky BoxEdit
# skupinoveho resize) - vsechno indexovane podle POZICE dilu v poli `parts`
# (stabilni poradi zachovane od ulozeni po nacteni). Zpetne kompatibilni:
# stary format `data` byl proste pole `parts` bez obalu - cteni (viz
# custom_shapes_list nize) obojí rozliší.
def _validate_custom_shape_parts(parts_in, valid_part_ids, max_parts=CUSTOM_SHAPE_MAX_PARTS):
    if not isinstance(parts_in, list) or not parts_in:
        return None, "Výběr ve scéně je prázdný."
    if len(parts_in) > max_parts:
        return None, f"Výběr obsahuje příliš mnoho dílů (max {max_parts})."
    clean_parts = []
    for p in parts_in:
        if not isinstance(p, dict):
            return None, "Neplatná data dílu."
        part_id = p.get("part_id")
        if part_id not in valid_part_ids:
            return None, f"Neznámý part_id: {part_id}"
        position = p.get("position")
        quaternion = p.get("quaternion")
        scale = p.get("scale")
        if not (isinstance(position, list) and len(position) == 3 and all(isinstance(v, (int, float)) for v in position)):
            return None, "Neplatná pozice dílu."
        if not (isinstance(quaternion, list) and len(quaternion) == 4 and all(isinstance(v, (int, float)) for v in quaternion)):
            return None, "Neplatný kvaternion dílu."
        if not (isinstance(scale, list) and len(scale) == 3 and all(isinstance(v, (int, float)) for v in scale)):
            return None, "Neplatné měřítko dílu."
        clean_part = {
            "part_id": part_id,
            "position": [float(v) for v in position],
            "quaternion": [float(v) for v in quaternion],
            "scale": [float(v) for v in scale],
        }
        # bot8 2026-09-16: SKUTECNA korenova pricina opakovanych incidentu
        # "Uloz oprava" (webapp/scene.html resaveOpenedAssembly) - tenhle
        # validator je SDILENY s Vlastnimi tvary (custom_shapes.py), ktere
        # semanticky "role" popisek dilu (predni-svislice/eurobox-sloupecN-
        # patroM/... - viz KAROSERIE_UMISTENI.md) NIKDY nemely, takze tu
        # nikdy nebyl whitelistovan. Kazde "Uloz opravu" produktove sestavy
        # tak KLIENT poslal spravne s role, ale SERVER ho tise zahodil pri
        # cisteni - zadna klientska oprava (cache, JS verze, kopirovani...)
        # tohle nemohla ovlivnit, protoze bug byl vzdy tady. Bez role
        # nejde spocitat predni azimut (razitkovac.predni_azimut) ani
        # spustit vetsinu geometrickych kontrolnich skriptu nad sestavou.
        role = p.get("role")
        if isinstance(role, str) and role and len(role) <= 120:
            clean_part["role"] = role
        color = p.get("color")
        if isinstance(color, str) and re.match(r"^#[0-9a-fA-F]{6}$", color):
            clean_part["color"] = color
        # Robert 2026-08-09 ("šlo by tu patku přebarvit jen částečně?") -
        # castecne obarveni jednotlivych casti (meshu) vicedilneho dilu, viz
        # scene.html applyPartMaterial/paintEntry (mapa jmeno meshe -> barva).
        mesh_colors = p.get("mesh_colors")
        if isinstance(mesh_colors, dict) and mesh_colors:
            clean_mesh_colors = {
                k: v for k, v in mesh_colors.items()
                if isinstance(k, str) and isinstance(v, str) and re.match(r"^#[0-9a-fA-F]{6}$", v)
            }
            if clean_mesh_colors:
                clean_part["mesh_colors"] = clean_mesh_colors
        used_conn = p.get("used_conn")
        if isinstance(used_conn, list) and all(isinstance(v, int) for v in used_conn):
            clean_part["used_conn"] = used_conn
        joint_count = p.get("joint_count")
        if isinstance(joint_count, (int, float)) and not isinstance(joint_count, bool) and joint_count > 0:
            clean_part["joint_count"] = int(joint_count)
        hidden_end_conn = p.get("hidden_end_conn")
        if isinstance(hidden_end_conn, list) and hidden_end_conn and all(isinstance(v, int) for v in hidden_end_conn):
            clean_part["hidden_end_conn"] = hidden_end_conn
        if p.get("was_through") is True:
            clean_part["was_through"] = True
        if p.get("was_attached") is True:
            clean_part["was_attached"] = True
        if p.get("vertical") is True:
            clean_part["vertical"] = True
        lic_peers = p.get("lic_peers")
        if isinstance(lic_peers, list) and lic_peers and all(isinstance(v, int) for v in lic_peers):
            clean_part["lic_peers"] = lic_peers  # rozsah indexu overen az v _validate_custom_shape_relations
        # Robert 2026-08-02 ("...je nutne aby tam zustala vazba napojenych
        # prislusenstvi"): vazba pripojeni prislusenstvi na profil -
        # indexovy odkaz "prof" na jiny dil tehoz tvaru + dvojice
        # konektoru + natoceni (spin 0-3). Rozsah indexu "prof" se overuje
        # az v _validate_custom_shape_relations (stejne jako lic_peers).
        attached_to = p.get("attached_to")
        if isinstance(attached_to, dict):
            at_prof = attached_to.get("prof")
            at_parent = attached_to.get("parent_conn")
            at_child = attached_to.get("child_conn")
            at_spin = attached_to.get("spin", 0)
            if (isinstance(at_prof, int) and not isinstance(at_prof, bool)
                    and isinstance(at_parent, int) and not isinstance(at_parent, bool)
                    and isinstance(at_child, int) and not isinstance(at_child, bool)
                    and isinstance(at_spin, int) and not isinstance(at_spin, bool)
                    and 0 <= at_spin <= 3 and at_parent >= 0 and at_child >= 0):
                clean_part["attached_to"] = {
                    "prof": at_prof, "parent_conn": at_parent,
                    "child_conn": at_child, "spin": at_spin,
                }
        clean_parts.append(clean_part)
    return clean_parts, None


# bot8 2026-09-18 (druhy vyskyt): puvodni kontrola (viz git historie, commit
# df5e11d9 "[remove-fn]") byla odstranena na Robertuv pokyn, protoze blokovala
# legitimni preulozeni product_assemblies#540 (starsi sestava sdili roli
# "predni-svislice" napric 3 RUZNYMI fyzickymi nohami - zavedena konvence
# tehdy, ne chyba). O par hodin pozdeji se ale presne tenhle druh kontroly
# ukazal potreba jinde: custom_shapes#558 ("dvirka 20 vzory") dostala pri
# rucni editaci + preulozeni 8 duplicitnich kopii role "limit-300-doraz2-b"
# na naprosto ruznych (a spatnych) pozicich, beze zbytku prosla. Rozdil:
# custom_shapes ("vzory") maji roli jako ZAMERNE unikatni identifikator
# slotu (Robertova vlastni konvence), product_assemblies (zejmena starsi,
# skriptem stavene) sdileni role napric fyzickymi dily bezne pouzivaji.
# Kontrola se proto vraci, ale POUZE pro custom_shapes (viz pouziti v
# custom_shapes.py) - NEPOUZIVAT v product_assemblies.py, tam by zase
# blokovala legitimni starsi sestavy.
def _najdi_duplicitni_role(clean_parts):
    counts = {}
    for p in clean_parts:
        role = p.get("role")
        if role:
            counts[role] = counts.get(role, 0) + 1
    return {role: n for role, n in counts.items() if n > 1}


def _validate_custom_shape_relations(join_groups_in, frame_groups_in, num_parts, clean_parts):
    valid_idx = set(range(num_parts))

    clean_join_groups = []
    if join_groups_in is not None:
        if not isinstance(join_groups_in, list):
            return None, None, "Neplatný formát skupin (Join)."
        for g in join_groups_in:
            if not (isinstance(g, list) and len(g) >= 2 and all(isinstance(v, int) for v in g)):
                return None, None, "Neplatná skupina (Join)."
            if not all(v in valid_idx for v in g) or len(set(g)) != len(g):
                return None, None, "Skupina (Join) odkazuje na neplatný díl."
            clean_join_groups.append(g)

    clean_frame_groups = []
    if frame_groups_in is not None:
        if not isinstance(frame_groups_in, list):
            return None, None, "Neplatný formát rámů (frame_groups)."
        for fg in frame_groups_in:
            if not isinstance(fg, dict):
                return None, None, "Neplatný rám (frame_groups)."
            idxs = [fg.get("a"), fg.get("b"), fg.get("c"), fg.get("d")]
            if not all(isinstance(v, int) for v in idxs):
                return None, None, "Neplatné indexy rámu (frame_groups)."
            if not all(v in valid_idx for v in idxs) or len(set(idxs)) != 4:
                return None, None, "Rám (frame_groups) odkazuje na neplatný díl."
            clean_frame_groups.append({"a": idxs[0], "b": idxs[1], "c": idxs[2], "d": idxs[3]})

    # lic_peers indexy (ulozene primo v clean_parts) overit az ted, kdyz uz
    # zname presny pocet dilu num_parts.
    for i, cp in enumerate(clean_parts):
        peers = cp.get("lic_peers")
        if not peers:
            continue
        filtered = [j for j in peers if j in valid_idx and j != i]
        if filtered:
            cp["lic_peers"] = sorted(set(filtered))
        else:
            cp.pop("lic_peers", None)

    # attached_to.prof (indexovy odkaz na dil-profil tehoz tvaru) overit
    # stejne az ted - odkaz mimo rozsah nebo sam na sebe se cely zahodi.
    for i, cp in enumerate(clean_parts):
        at = cp.get("attached_to")
        if not at:
            continue
        if at.get("prof") not in valid_idx or at.get("prof") == i:
            cp.pop("attached_to", None)

    return clean_join_groups, clean_frame_groups, None




# Robert 2026-07-27 (po dokonceni FBX uploadu pro profily i produkty):
# "co kdyz bychom chteli vkladat stp? umime to nejak tu strukturu
# zjednodusit a dat do glb?" -> "potrebujeme tu mesh maximalne
# zjednodusit" -> "osekat radiusy". Sdileny dispatcher pro OBA upload
# endpointy nize (profily i produkty) - rozpozna format podle pripony a
# zavola FBX (in-process, lehke) nebo STEP (izolovany subprocess pres
# step_venv, viz step_convert.py - tezka OCP/OpenCascade zavislost NENI
# v hlavnim app venv, aby nezatezovala uz tak napjatou pamet serveru).
def convert_uploaded_model_to_glb(src_path, glb_dest_path, quality=None):
    """quality (2026-08-04, jen pro STEP - Robert: "vyber kvality 3D
    modelu... nejnizsi ta puvodni kdyz je v modelu logo, stredni... 3
    stupen plne zaobleni") - "low"/"medium"/"high"/None (=automaticka
    detekce, viz step_convert_worker.py). FBX pipeline (fbx_convert.py)
    zadnou volbu kvality nema/nepodporuje - parametr se pro .fbx ignoruje."""
    ext = os.path.splitext(src_path)[1].lower()
    if ext == ".fbx":
        if fbx_convert is None:
            return False, {"error": "Převodní modul (fbx_convert) není na serveru dostupný."}
        return fbx_convert.convert_single_fbx(src_path, glb_dest_path)
    if ext in (".stp", ".step"):
        if step_convert is None:
            return False, {"error": "Převodní modul (step_convert) není na serveru dostupný."}
        return step_convert.convert_single_step(src_path, glb_dest_path, quality=quality)
    return False, {"error": f"Nepodporovaná přípona souboru: {ext or '(žádná)'}"}
























# --- Cena spoju + prislusenstvi (rozhodnuti 2026-07-23) ---
# Kazdy profil ve scene si v realu vyzadal rez (viz price_per_cut_czk vyse,
# nastavuje se per-profil v tabulce cen) a kazdy KONEC profilu, ktery je
# skutecne pripojeny k jinemu dilu, znamena spoj (spojovaci material + praci).
# Cena spoje je jedna spolecna sazba pro vsechny profily (app_settings,
# klic "joint_price_czk"). Prislusenstvi (uhelniky, srouby, T-matice...) jsou
# skutecne katalogove polozky (cfg_accessories) se svou cenou/ks; kazda ma
# "qty_per_joint" - kolik kusu te polozky pripada na 1 spoj v sestave. Celkovy
# pocet spoju v sestave pocita frontend (scene.html) ze skutecneho pripojeni
# konektoru (kazdy pripojeny konec profilu = +1 spoj, tedy profil spojeny na
# obou koncich = 2 spoje, na jednom konci = 1 spoj - viz Robertovo zadani).
# Backend jen posklada nastaveni (sazba + seznam prislusenstvi), samotny vypocet
# celkove ceny pro AKTUALNI sestavu je na frontendu (potrebuje zivou geometrii).
def get_setting(cur, key, default=None):
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (key,))
    row = cur.fetchone()
    return row["setting_value"] if row else default



















THEME_COLOR_KEYS = (
    "bg", "panel_bg", "panel_bg_alt",
    "border", "border_soft", "border_soft2", "border_faint",
    "text", "text2", "text_muted", "text_faint",
    "accent", "accent_focus",
    "btn_bg", "btn_bg_hover", "btn_danger", "btn_danger_hover",
    "error", "success", "warn",
    "row_dirty_bg",
    "support_bubble_bg", "support_ai_bubble_bg", "support_ai_text",
    "thumb_bg",
    # Skladová karta (Robert 2026-07-26: "chybí možnost vybrat barvu
    # různých prvků na ploše") - dřív měly statistické dlaždice/hlavička
    # tabulky pohybů/nadpisy sekcí napevno svázané globální panel_bg_alt/
    # border_soft2/text_muted (sdílené se vším ostatním v adminu). Ted
    # maji vlastni klice, takze je Robert muze prebarvit nezavisle na
    # zbytku administrace, aniz by tim ovlivnil neco jineho.
    "sc_stat_bg", "sc_stat_border", "sc_section_header", "sc_table_header_bg",
    # Online nabídka (Robert 2026-08-06: "dej do nabídky barvítka, uprava
    # barev hlavních prvků") - surface="nabidka". VLASTNI (predponou
    # "offer_" odlisene) klice, ne sdilene s admin/eshop "border"/"accent"
    # atd. - kdyby se pouzily stejne generic nazvy, sdileny
    # THEME_COLOR_DEFAULTS[mode] (viz nize, jeden default slovnik PRO
    # VSECHNY povrchy najednou) by pred prvnim ulozenim ukazoval spatnou
    # (admin/eshop) vychozi barvu misto nabidkove. Nabidka nema
    # tmavy/svetly prepinac (na rozdil od admin/eshop) - pouziva se vzdy
    # jen "light" polovina, "dark" se ukladá jako stejna kopie (viz
    # THEME_COLOR_DEFAULTS nize) jen pro symetrii s existujicim
    # dark/light API tvarem.
    "offer_navy_dark", "offer_navy", "offer_navy_light",
    "offer_orange", "offer_orange_light",
    "offer_card_bg", "offer_ink", "offer_ink_soft", "offer_muted", "offer_border",
    # Kosik (Robert 2026-08-08: "v adminu do Vzhledu novy prvek, zmena barev
    # pro kosik") - surface="cart". Stejny duvod/tvar jako "offer_*" vyse:
    # #cartDrawer v product/category/index.html ma jednu pevnou (ne tmavy/
    # svetly prepinac) branded paletu prevzatou z nabidka-online.html designu
    # (--cn-* CSS promenne), vlastni klice aby se nesdilely s admin/eshop
    # generickymi "border"/"accent" atd.
    "cart_navy_dark", "cart_navy", "cart_navy_light",
    "cart_orange", "cart_orange_light",
    "cart_card_bg", "cart_ink", "cart_ink_soft", "cart_muted", "cart_border",
)


_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")








# ---------------------------------------------------------------------------
# Socialni site (Robert 2026-07-31): "propojeni se socialnimi sitemi... neco
# do administrace, neco na eshop". Rozsah upresnen postupne v konverzaci:
# (2) Open Graph nahledy pri sdileni odkazu, (3) tlacitko Sdilet na e-shopu,
# + planovane prispevky (jen struktura - realne odesilani na Facebook API
# az az bude k dispozici Page Access Token, viz AGENTS_LOG.md).
# ---------------------------------------------------------------------------

OG_DEFAULT_TITLE = "Hliníkový konstrukční stavebnicový systém s drážkami"
OG_DEFAULT_DESCRIPTION = "Navrhněte si konstrukci z hliníkových profilů ve 3D konfigurátoru Logiman."
OG_DEFAULT_IMAGE = "/content-files/gallery/vestavby_dodavek/demo-auto-vandrawee.jpg"
# POZOR (bot15, 2026-09-05, Robert pres bot3): puvodni vychozi obrazek
# ("ergonomicke-police-ke-stolum.jpg") ma VYPALENY poloprusvitny napis
# "LOGIMAN.CZ" pres stred fotky - vraceny jako vychozi OG obrazek i z
# odbrandovanych storefront domen (fiat-ducato-vestavby.top apod.),
# porusovalo TEXT_FILTR.md pravidlo 5 (zadna zminka materske znacky).
# Novy vychozi obrazek NESMI mit zadny vypaleny text/logo, jde totiz
# o SDILENY fallback pouzivany i mimo hlavni branding (viz
# _get_og_site_defaults() nize a jeho volani v api/storefront_pages.py).


def _get_og_site_defaults(cur):
    raw = get_setting(cur, "og_site_defaults", None)
    defaults = {"title": OG_DEFAULT_TITLE, "description": OG_DEFAULT_DESCRIPTION, "image": OG_DEFAULT_IMAGE}
    if not raw:
        return defaults
    try:
        saved = json.loads(raw)
    except (ValueError, TypeError):
        return defaults
    for k in defaults:
        if saved.get(k):
            defaults[k] = saved[k]
    return defaults






def _og_escape(s):
    return (s or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _ld_json_script(obj):
    # </script> v datech (napr. v nazvu produktu) by jinak predcasne
    # ukoncil <script> tag - stejny escape pouziva i Google/MDN priklady.
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"


# bot10 2026-08-28 (SEO/AI-viditelnost audit AUDIT_SEO_AI_VISIBILITY_2026-08-28.md,
# schvaleno bot3) - admin uz rucne pise FAQ blok do content_pages.bottom_body_html
# (27 z 59 kategorii s obsahem, konzistentni format <div class="seo-faq">
# <h3>Caste dotazy</h3><p><strong>Otazka?</strong><br>Odpoved.</p>...</div>),
# ale nikdy se to nestrukturovalo jako schema.org FAQPage - jen technicke
# zabaleni JIZ EXISTUJICIHO/schvaleneho obsahu, zadny novy text.
_FAQ_BLOCK_RE = re.compile(r'<div class="seo-faq">.*?</div>', re.S)
_FAQ_PAIR_RE = re.compile(r'<p><strong>(.*?)</strong><br\s*/?>(.*?)</p>', re.S)


def _extract_faq_pairs(html_text):
    """Vytahne (otazka, odpoved) pary z existujiciho seo-faq bloku.
    Vraci [] kdyz blok chybi/je prazdny - volajici pak FAQPage
    JSON-LD proste nepripoji."""
    if not html_text or "seo-faq" not in html_text:
        return []
    block_m = _FAQ_BLOCK_RE.search(html_text)
    if not block_m:
        return []
    pairs = []
    for q, a in _FAQ_PAIR_RE.findall(block_m.group(0)):
        q_text = html_lib.unescape(re.sub(r'<[^>]+>', '', q)).strip()
        a_text = html_lib.unescape(re.sub(r'<[^>]+>', '', a)).strip()
        if q_text and a_text:
            pairs.append((q_text, a_text))
    return pairs


# Robert pres bot3, 2026-09-26 ("prazdny nadpis Caste dotazy bez niceho pod
# nim... deaktivovat dokud nevzejdou dotazy realne") - vyprazdneni 13
# kategorii (bot7, 2026-09-26) smazalo jen <p><strong>...</strong>...</p>
# pary uvnitr <div class="seo-faq">, ale samotny wrapper s <h3>Caste
# dotazy</h3> zustal zamerne zachovany (kvuli pozdejsimu doplneni). Ten
# wrapper se ale vykresloval VZDY, bez ohledu na to, jestli je uvnitr
# skutecny obsah - odtud prazdny nadpis. Stejna podminka jako uz ma
# _extract_faq_pairs() pro JSON-LD (prazdno -> zadne schema), aplikovana
# ted i na VIDITELNE vykresleni: kdyz par neexistuje, cely blok se ze
# vraceneho HTML vystrihne. Reverzibilni bez dalsiho zasahu - jakmile
# nekdo do bloku vlozi realny par zpet, _extract_faq_pairs ho najde,
# _strip_empty_faq_block prestane strihat a nadpis i JSON-LD se objevi
# same.
def _strip_empty_faq_block(html_text):
    if not html_text or "seo-faq" not in html_text:
        return html_text
    if _extract_faq_pairs(html_text):
        return html_text
    return _FAQ_BLOCK_RE.sub("", html_text)


def _faq_page_ld(pairs):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in pairs
        ],
    }


def _cat_tree_colors_ssr_style_safe():
    # bot16, 2026-09-17 - lazy import (cat_tree_colors.py importuje Z
    # app.py, takze top-level import by byl kruhovy - v dobe, kdy se
    # tahle funkce SKUTECNE VOLA, uz je cat_tree_colors davno nacteny
    # modulem "import cat_tree_colors" dole v tomhle souboru). Volano na
    # KAZDEM vykresleni stranky pres _render_og_page() nize - vlastni
    # kratke spojeni + try/except, at pripadny vypadek DB nespadne celou
    # stranku jen kvuli tomuhle kosmetickemu doplnku.
    try:
        from cat_tree_colors import cat_tree_colors_ssr_style
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                return cat_tree_colors_ssr_style(cur)
        finally:
            conn.close()
    except Exception:
        return ""


def _site_font_ssr_head_safe():
    # bot16, 2026-09-17 - stejny vzor jako _cat_tree_colors_ssr_style_safe()
    # vyse (lazy import, kruhova zavislost, defenzivni try/except).
    try:
        from site_font import site_font_ssr_head
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                return site_font_ssr_head(cur)
        finally:
            conn.close()
    except Exception:
        return ""


def _base_dark_color_ssr_style_safe():
    # bot16, 2026-09-17 - stejny vzor jako predchozi dve funkce vyse.
    try:
        from base_dark_color import base_dark_color_ssr_style
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                return base_dark_color_ssr_style(cur)
        finally:
            conn.close()
    except Exception:
        return ""


def _render_og_page(template_filename, og, extra_head="", body_replacements=None):
    path = os.path.join(os.path.dirname(__file__), "..", "webapp", template_filename)
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    # SSR nahrada placeholderu v tele stranky (napr. "Nacitam..." H1) za
    # skutecny obsah - kvuli robotum/nastrojum, ktere JS nevykonavaji nebo
    # vykonaji az v druhe (opozdene) vlne indexace. Klient si po nacteni JS
    # stejne pretka identickym (nebo aktualnim) obsahem, zadna zmena chovani
    # pro realne uzivatele.
    for old, new in (body_replacements or {}).items():
        html = html.replace(old, new, 1)
    image_url = og["image"]
    # og:image v 1200x630 (bot15, 2026-09-02, viz _og_image_1200x630) - jen
    # pro <meta og:image>; JSON-LD / <img> na strance dal pouzivaji original.
    og_image_dims = ""
    og_variant = _og_image_1200x630(image_url) if image_url else None
    if og_variant:
        image_url = og_variant[0]
        og_image_dims = (
            f'<meta property="og:image:width" content="{og_variant[1]}">\n'
            f'<meta property="og:image:height" content="{og_variant[2]}">\n'
        )
    if image_url and not image_url.startswith("http"):
        image_url = request.host_url.rstrip("/") + image_url
    canonical_url = og.get("canonical") or request.url
    og_html = (
        f'<meta name="description" content="{_og_escape(og["description"])}">\n'
        '<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1">\n'
        f'<link rel="canonical" href="{_og_escape(canonical_url)}">\n'
        '<meta property="og:type" content="website">\n'
        '<meta property="og:site_name" content="Hliníkový konstrukční stavebnicový systém s drážkami">\n'
        f'<meta property="og:title" content="{_og_escape(og["title"])}">\n'
        f'<meta property="og:description" content="{_og_escape(og["description"])}">\n'
        f'<meta property="og:image" content="{_og_escape(image_url)}">\n'
        + og_image_dims +
        f'<meta property="og:url" content="{_og_escape(canonical_url)}">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        # Organization/WebSite JSON-LD (bot10, 2026-08-28, SEO/AI-viditelnost
        # audit AUDIT_SEO_AI_VISIBILITY_2026-08-28.md, schvaleno bot3) -
        # zakladni "kdo jste" strukturovana data, dosud chybela UPLNE. Na
        # KAZDE strance (ne jen homepage) - stejny vzor jako sesterky
        # vybaveni-uzitkovych-vozidel (api/app.py:927-934 tam).
        + _ld_json_script({
            "@context": "https://schema.org", "@type": "Organization",
            "name": "Hliníkový konstrukční stavebnicový systém s drážkami",
            "url": request.host_url.rstrip("/"),
        })
        + _ld_json_script({
            "@context": "https://schema.org", "@type": "WebSite",
            "name": "Hliníkový konstrukční stavebnicový systém s drážkami",
            "url": request.host_url.rstrip("/"),
        })
        + extra_head
        + _cat_tree_colors_ssr_style_safe()
        + _site_font_ssr_head_safe()
        + _base_dark_color_ssr_style_safe()
    )
    html = html.replace("<!-- OG_TAGS_PLACEHOLDER -->", og_html, 1)
    html = re.sub(
        r'(<title id="pageTitleTag">)[^<]*(</title>)',
        lambda m: m.group(1) + _og_escape(og["title"]) + m.group(2),
        html, count=1,
    )
    return Response(html, mimetype="text/html; charset=utf-8")

































# Editovatelne barevne motivy (Robert 2026-07-26: "udelej ty schemata
# barev editovatelne") - drive byly presety (Royal, Moderni, Med a
# grafit, Lesni zelen, Cerno-modra) natvrdo v JS a slo je jen "pouzit"
# (zkopirovat do editovaneho povrchu), ne upravovat/prejmenovat/mazat/
# vytvaret nove. Ted zije cely seznam v app_settings pod "theme_presets"
# jako JSON pole - DEFAULT_THEME_PRESETS jsou jen seed hodnoty pro prvni
# nacteni (dokud Robert seznam poprve needituje/neulozi, nic se
# nezmeni). Zamerne JEDEN endpoint pro cely seznam (ne CRUD na
# jednotlive polozky) - stejny vzor jako u palety povrchu, frontend
# manipuluje polem lokalne a posle ho cele zpet.
DEFAULT_THEME_PRESETS = [
    {
        "id": "royal", "name": "Royal (černo-zlatá)",
        "dark": {
            "bg": "#1a1512", "panel_bg": "#241d18", "panel_bg_alt": "#1f1915",
            "border": "#3a2f22", "border_soft": "#332921", "border_soft2": "#2c2419", "border_faint": "#251f17",
            "text": "#ede4d3", "text2": "#cbbfa8", "text_muted": "#a89882", "text_faint": "#7d7062",
            "accent": "#c9a227", "accent_focus": "#d4af37",
            "btn_bg": "#9c7a28", "btn_bg_hover": "#b38f34", "btn_danger": "#7a3a3a", "btn_danger_hover": "#8a4a4a",
            "error": "#e0776a", "success": "#8fbf7a", "warn": "#d4af37",
            "row_dirty_bg": "#332619",
            "support_bubble_bg": "#332921", "support_ai_bubble_bg": "#3a2e1a", "support_ai_text": "#e8d4a0",
            "thumb_bg": "#120e0b",
            "sc_stat_bg": "#1f1915", "sc_stat_border": "#3a2f22",
            "sc_section_header": "#a89882", "sc_table_header_bg": "#1f1915",
        },
        "light": {
            "bg": "#f7f1e6", "panel_bg": "#ffffff", "panel_bg_alt": "#f3ead8",
            "border": "#ddcba0", "border_soft": "#e8ddc4", "border_soft2": "#e2d4b4", "border_faint": "#ece2cc",
            "text": "#241d15", "text2": "#4a3d2a", "text_muted": "#6d5d45", "text_faint": "#9c8d72",
            "accent": "#a9822a", "accent_focus": "#8a6a1f",
            "btn_bg": "#a9822a", "btn_bg_hover": "#8a6a1f", "btn_danger": "#b23b3b", "btn_danger_hover": "#c24b4b",
            "error": "#b8422f", "success": "#4f8a3d", "warn": "#a06b1c",
            "row_dirty_bg": "#f5e9cc",
            "support_bubble_bg": "#efe4cc", "support_ai_bubble_bg": "#f0e2b8", "support_ai_text": "#6b4f23",
            "thumb_bg": "#e6d8b8",
            "sc_stat_bg": "#f3ead8", "sc_stat_border": "#e2d4b4",
            "sc_section_header": "#6d5d45", "sc_table_header_bg": "#f3ead8",
        },
    },
    {
        "id": "blackblue", "name": "Černo-modrá",
        "dark": {
            "bg": "#000000", "panel_bg": "#1c1c1c", "panel_bg_alt": "#141414",
            "border": "#666666", "border_soft": "#4d4d4d", "border_soft2": "#333333", "border_faint": "#262626",
            "text": "#eeeeee", "text2": "#cfcfcf", "text_muted": "#979797", "text_faint": "#6e6e6e",
            "accent": "#0088cc", "accent_focus": "#1a9ddb",
            "btn_bg": "#0088cc", "btn_bg_hover": "#1a9ddb", "btn_danger": "#7a3a3a", "btn_danger_hover": "#8a4a4a",
            "error": "#e0776a", "success": "#7ed49a", "warn": "#e0a070",
            "row_dirty_bg": "#0d2733",
            "support_bubble_bg": "#333333", "support_ai_bubble_bg": "#0d2733", "support_ai_text": "#bfe3f5",
            "thumb_bg": "#000000",
            "sc_stat_bg": "#141414", "sc_stat_border": "#4d4d4d",
            "sc_section_header": "#979797", "sc_table_header_bg": "#141414",
        },
        "light": {
            "bg": "#eeeeee", "panel_bg": "#ffffff", "panel_bg_alt": "#f5f5f5",
            "border": "#979797", "border_soft": "#cccccc", "border_soft2": "#d9d9d9", "border_faint": "#e2e2e2",
            "text": "#000000", "text2": "#333333", "text_muted": "#666666", "text_faint": "#979797",
            "accent": "#0088cc", "accent_focus": "#006fa8",
            "btn_bg": "#0088cc", "btn_bg_hover": "#006fa8", "btn_danger": "#b23b3b", "btn_danger_hover": "#c24b4b",
            "error": "#b8422f", "success": "#4f8a3d", "warn": "#a06b1c",
            "row_dirty_bg": "#e0f0fa",
            "support_bubble_bg": "#f5f5f5", "support_ai_bubble_bg": "#e0f0fa", "support_ai_text": "#004a70",
            "thumb_bg": "#d9d9d9",
            "sc_stat_bg": "#f5f5f5", "sc_stat_border": "#cccccc",
            "sc_section_header": "#666666", "sc_table_header_bg": "#f5f5f5",
        },
    },
    {
        "id": "modern", "name": "Moderní",
        "dark": {
            "bg": "#14161a", "panel_bg": "#1c1f26", "panel_bg_alt": "#171a20",
            "border": "#2c313a", "border_soft": "#262a32", "border_soft2": "#22262d", "border_faint": "#1e2127",
            "text": "#f0f2f5", "text2": "#c9ced6", "text_muted": "#8b93a1", "text_faint": "#5f6672",
            "accent": "#6d8cff", "accent_focus": "#8aa3ff",
            "btn_bg": "#4f63d2", "btn_bg_hover": "#5f74e0", "btn_danger": "#d1495b", "btn_danger_hover": "#e0596b",
            "error": "#f26d7d", "success": "#4ade9a", "warn": "#f0b429",
            "row_dirty_bg": "#232a3a",
            "support_bubble_bg": "#262a32", "support_ai_bubble_bg": "#262038", "support_ai_text": "#d8ccff",
            "thumb_bg": "#101216",
        },
        "light": {
            "bg": "#f7f8fa", "panel_bg": "#ffffff", "panel_bg_alt": "#f2f4f7",
            "border": "#e2e5eb", "border_soft": "#ebedf1", "border_soft2": "#e6e9ee", "border_faint": "#eef0f3",
            "text": "#16181d", "text2": "#3d4148", "text_muted": "#6b7280", "text_faint": "#9aa0ab",
            "accent": "#4f63d2", "accent_focus": "#3f52c2",
            "btn_bg": "#4f63d2", "btn_bg_hover": "#3f52c2", "btn_danger": "#d1495b", "btn_danger_hover": "#c13a4c",
            "error": "#d1495b", "success": "#16a374", "warn": "#d18f1a",
            "row_dirty_bg": "#eef0fc",
            "support_bubble_bg": "#f2f4f7", "support_ai_bubble_bg": "#ede9fe", "support_ai_text": "#5b3fa8",
            "thumb_bg": "#e9ebef",
        },
    },
    {
        "id": "copper", "name": "Měď a grafit",
        "dark": {
            "bg": "#201d1a", "panel_bg": "#2b2622", "panel_bg_alt": "#221e1b",
            "border": "#4a3f36", "border_soft": "#3a332c", "border_soft2": "#332e28", "border_faint": "#2e2924",
            "text": "#ece6df", "text2": "#cdc3b8", "text_muted": "#a3968a", "text_faint": "#7d7168",
            "accent": "#d68a4c", "accent_focus": "#e2a06a",
            "btn_bg": "#8a5a35", "btn_bg_hover": "#a06a40", "btn_danger": "#7a3a3a", "btn_danger_hover": "#8a4a4a",
            "error": "#e0776a", "success": "#8fbf7a", "warn": "#e0a95c",
            "row_dirty_bg": "#362b1f",
            "support_bubble_bg": "#3a332c", "support_ai_bubble_bg": "#3a2e22", "support_ai_text": "#e8c9a0",
            "thumb_bg": "#17140f",
        },
        "light": {
            "bg": "#f4efe8", "panel_bg": "#ffffff", "panel_bg_alt": "#f7f2ea",
            "border": "#ddd1c0", "border_soft": "#e8dfd1", "border_soft2": "#e2d7c6", "border_faint": "#ece4d8",
            "text": "#241f1a", "text2": "#4a3f34", "text_muted": "#6d6052", "text_faint": "#9c9182",
            "accent": "#b5651f", "accent_focus": "#c9762c",
            "btn_bg": "#9c5f2e", "btn_bg_hover": "#ac6f3c", "btn_danger": "#b23b3b", "btn_danger_hover": "#c24b4b",
            "error": "#b8422f", "success": "#4f8a3d", "warn": "#a06b1c",
            "row_dirty_bg": "#f5e6d3",
            "support_bubble_bg": "#efe6d9", "support_ai_bubble_bg": "#f0e2cc", "support_ai_text": "#6b4423",
            "thumb_bg": "#e6dbc9",
        },
    },
    {
        "id": "forest", "name": "Lesní zeleň",
        "dark": {
            "bg": "#1a1f1c", "panel_bg": "#212823", "panel_bg_alt": "#1b211d",
            "border": "#3a453d", "border_soft": "#313a34", "border_soft2": "#2b332e", "border_faint": "#262d29",
            "text": "#e6ece7", "text2": "#c4d0c6", "text_muted": "#8fa091", "text_faint": "#6f7d71",
            "accent": "#7fbf8a", "accent_focus": "#98d1a2",
            "btn_bg": "#3f6b4d", "btn_bg_hover": "#4d7d5c", "btn_danger": "#7a3a3a", "btn_danger_hover": "#8a4a4a",
            "error": "#e0776a", "success": "#7ed49a", "warn": "#e0c070",
            "row_dirty_bg": "#26312a",
            "support_bubble_bg": "#313a34", "support_ai_bubble_bg": "#2a3830", "support_ai_text": "#cfe8d4",
            "thumb_bg": "#12160f",
        },
        "light": {
            "bg": "#eef3ee", "panel_bg": "#ffffff", "panel_bg_alt": "#f3f7f3",
            "border": "#d3ded5", "border_soft": "#e0e9e1", "border_soft2": "#d9e3da", "border_faint": "#e5ede6",
            "text": "#1c231e", "text2": "#3c463e", "text_muted": "#5e6b60", "text_faint": "#93a196",
            "accent": "#2f7d47", "accent_focus": "#388c52",
            "btn_bg": "#2f6b45", "btn_bg_hover": "#3a7b52", "btn_danger": "#b23b3b", "btn_danger_hover": "#c24b4b",
            "error": "#c23b3b", "success": "#2f9e5c", "warn": "#b8721f",
            "row_dirty_bg": "#e5f0e6",
            "support_bubble_bg": "#eaf1eb", "support_ai_bubble_bg": "#e3f0e5", "support_ai_text": "#234a30",
            "thumb_bg": "#dbe6dc",
        },
    },
    {
        "id": "sage", "name": "Šalvějová (šedozelená)",
        "dark": {
            "bg": "#1a1d1a", "panel_bg": "#22261f", "panel_bg_alt": "#1c1f19",
            "border": "#3a4038", "border_soft": "#31362f", "border_soft2": "#2b2f29", "border_faint": "#262a25",
            "text": "#e6e9e5", "text2": "#c5cac3", "text_muted": "#92998f", "text_faint": "#6e756c",
            "accent": "#8fb89b", "accent_focus": "#a3c7ac",
            "btn_bg": "#5c8a6d", "btn_bg_hover": "#6d9c7e", "btn_danger": "#7a3a3a", "btn_danger_hover": "#8a4a4a",
            "error": "#e0776a", "success": "#7ed49a", "warn": "#e0c070",
            "row_dirty_bg": "#263028",
            "support_bubble_bg": "#31362f", "support_ai_bubble_bg": "#29352b", "support_ai_text": "#cfe3d3",
            "thumb_bg": "#131511",
            "sc_stat_bg": "#1c1f19", "sc_stat_border": "#3a4038",
            "sc_section_header": "#92998f", "sc_table_header_bg": "#1c1f19",
        },
        "light": {
            "bg": "#d6dad5", "panel_bg": "#ffffff", "panel_bg_alt": "#eef1ee",
            "border": "#b9c2ba", "border_soft": "#d3d9d4", "border_soft2": "#c7cfc8", "border_faint": "#dde2de",
            "text": "#1c211d", "text2": "#3d453f", "text_muted": "#6d766f", "text_faint": "#98a099",
            "accent": "#6f9b7c", "accent_focus": "#598567",
            "btn_bg": "#6f9b7c", "btn_bg_hover": "#5f8a6c", "btn_danger": "#b23b3b", "btn_danger_hover": "#c24b4b",
            "error": "#c23b3b", "success": "#2f9e5c", "warn": "#b8721f",
            "row_dirty_bg": "#e6ede7",
            "support_bubble_bg": "#eef1ee", "support_ai_bubble_bg": "#e2ede4", "support_ai_text": "#234a30",
            "thumb_bg": "#d3d9d4",
            "sc_stat_bg": "#eef1ee", "sc_stat_border": "#c7cfc8",
            "sc_section_header": "#6d766f", "sc_table_header_bg": "#eef1ee",
        },
    },
    # Robert 2026-08-07 (screenshot widgetu "Můj počítač" - tmave pozadi,
    # fialovo-purpurove neonove gradienty na merici prstenci, zeleny
    # zvyraznujici text): "udělej nový barevný motiv v tomto duchu pro
    # eshop i administraci". Aplikovan primo na theme_colors_eshop_dark /
    # theme_colors_admin_dark (viz jednorazovy skript pri zavedeni), tady
    # jen jako trvaly preset pro pripad resetu/noveho nasazeni.
    {
        "id": "neon", "name": "Neon (fialovo-purpurová)",
        "dark": {
            "bg": "#0d0b14", "panel_bg": "#1a1626", "panel_bg_alt": "#150f1f",
            "border": "#3d2f52", "border_soft": "#2c2138", "border_soft2": "#241b30", "border_faint": "#1e1628",
            "text": "#f2eef9", "text2": "#d4c9e8", "text_muted": "#9d8bb8", "text_faint": "#6e5c88",
            "accent": "#c04cff", "accent_focus": "#e879f9",
            "btn_bg": "#8b2fd9", "btn_bg_hover": "#a855f7", "btn_danger": "#c2255c", "btn_danger_hover": "#d63384",
            "error": "#ff5c8a", "success": "#39e88f", "warn": "#ffb84d",
            "row_dirty_bg": "#2a1c3d",
            "support_bubble_bg": "#2c2138", "support_ai_bubble_bg": "#3d1f52", "support_ai_text": "#f0d9ff",
            "thumb_bg": "#0a0812",
            "sc_stat_bg": "#1a1626", "sc_stat_border": "#3d2f52",
            "sc_section_header": "#9d8bb8", "sc_table_header_bg": "#1a1626",
        },
        "light": {
            "bg": "#f5f0fb", "panel_bg": "#ffffff", "panel_bg_alt": "#f0e8fa",
            "border": "#d9c2f0", "border_soft": "#e6d7f5", "border_soft2": "#ddc9f2", "border_faint": "#ede0f9",
            "text": "#1e1330", "text2": "#4a3566", "text_muted": "#7a638f", "text_faint": "#a893bd",
            "accent": "#a020c9", "accent_focus": "#8b13ad",
            "btn_bg": "#9333ea", "btn_bg_hover": "#7e22ce", "btn_danger": "#c2255c", "btn_danger_hover": "#a8134a",
            "error": "#c2255c", "success": "#16a34a", "warn": "#c2760a",
            "row_dirty_bg": "#f0e0fa",
            "support_bubble_bg": "#f0e8fa", "support_ai_bubble_bg": "#ecdcfa", "support_ai_text": "#5b2380",
            "thumb_bg": "#e6d7f5",
            "sc_stat_bg": "#f0e8fa", "sc_stat_border": "#ddc9f2",
            "sc_section_header": "#7a638f", "sc_table_header_bg": "#f0e8fa",
        },
    },
]


def _validate_theme_preset_palette(palette):
    if not isinstance(palette, dict):
        return False
    for key, val in palette.items():
        if key not in THEME_COLOR_KEYS:
            return False
        if not isinstance(val, str) or not _HEX_COLOR_RE.match(val):
            return False
    return True


@app.get("/api/admin/theme-presets")
@require_permission("nastaveni", "zobrazit")
def theme_presets_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            raw = get_setting(cur, "theme_presets", None)
    finally:
        conn.close()
    if raw:
        try:
            presets = json.loads(raw)
            if isinstance(presets, list):
                return jsonify({"presets": presets})
        except (ValueError, TypeError):
            pass
    return jsonify({"presets": DEFAULT_THEME_PRESETS})


@app.put("/api/admin/theme-presets")
@require_permission("nastaveni", "upravit")
def theme_presets_set():
    body = request.get_json(silent=True) or {}
    presets = body.get("presets")
    if not isinstance(presets, list):
        return jsonify({"error": "presets musí být pole"}), 400
    seen_ids = set()
    for p in presets:
        if not isinstance(p, dict):
            return jsonify({"error": "každý motiv musí být objekt"}), 400
        pid = p.get("id")
        name = p.get("name")
        if not isinstance(pid, str) or not pid or not isinstance(name, str) or not name:
            return jsonify({"error": "každý motiv potřebuje neprázdné id a name"}), 400
        if pid in seen_ids:
            return jsonify({"error": f"duplicitní id motivu: {pid}"}), 400
        seen_ids.add(pid)
        if not _validate_theme_preset_palette(p.get("dark")):
            return jsonify({"error": f"motiv {pid}: neplatná paleta dark"}), 400
        if not _validate_theme_preset_palette(p.get("light")):
            return jsonify({"error": f"motiv {pid}: neplatná paleta light"}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            val = json.dumps(presets)
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                ("theme_presets", val, val),
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})






CATEGORY_PRODUCT_SORT_SQL = {
    # "sort" query param na /api/categories/<id>/content (Robert 2026-08-08,
    # "seradit produkty v prehledu podle ceny, od nejnizsi") - whitelist,
    # nikdy neinterpolovat "sort" primo do SQL. NULL cena vzdy az na konci
    # (IS NULL v ORDER BY), aby produkty bez ceny nevyskakovaly navrch.
    "price_asc": "(price_czk_placeholder IS NULL), price_czk_placeholder ASC, name",
    "name": "name",
}


# Robert 2026-09-25 (pres bot3, pravidlo 52), doslova: "ve stromu
# kategorii chci aby se sestavy radily do prehledu i v kategoriich
# hlavnich, cim hloubeji se jde do podkategorii tim se vypis produktu/
# sestav zuzuje". Predtim _category_products_with_images filtrovala
# jen primo/sekundarne PRIREZENE produkty teto jedne kategorie - nadrazena
# kategorie tak byla poloprazdna, i kdyz pod ni viselo desitky sestav v
# podkategoriich. Reseni: predem spocitat CELY strom (jedna lehka SELECT
# na celou tabulku, ~130 radku, ne N+1 na kazde urovni zanoreni) a pro
# danou kategorii vratit ID sebe + VSECH potomku (libovolne hloubky).
def _category_descendant_ids(cur, cat_id):
    cur.execute("SELECT id, parent_id FROM content_categories")
    children_by_parent = {}
    for r in cur.fetchall():
        children_by_parent.setdefault(r["parent_id"], []).append(r["id"])
    # BFS z cat_id - `seen` zaroven brani cyklu (i kdyby v datech omylem
    # vznikl, coz by u parent_id FK nemelo jit, ale radeji jistota).
    seen = {cat_id}
    queue = [cat_id]
    while queue:
        current = queue.pop()
        for child_id in children_by_parent.get(current, []):
            if child_id not in seen:
                seen.add(child_id)
                queue.append(child_id)
    return list(seen)


# Robert 2026-09-25 (pres bot3, pravidlo 52): "taky chci kategorii:
# naposled pridane sestavy/produkty na eshop, kde zobrazi poslednich
# 10". Zadne rucni prirazovani - obsah teto JEDNE konkretni kategorie
# (id natvrdo, stejny zavedeny vzor jako napr. CTA "Pracovni stoly na
# miru" id=241 vyse v souboru) je vzdy ZIVE dopocitany, ne ulozeny.
CATEGORY_ID_NAPOSLEDY_PRIDANE = 298

# Robert 2026-09-25 (primo, po zavedeni dedeneho vypisu nize): "myslel
# jsem tu logiku prave na vsechny ostatni hl.kategorie MIMO Hlinikove
# profily" - cela vetev 149 ("Hlinikove stavebnicove profily" - katalog
# materialu/BOM dilu, ne produktove sestavy, viz [[category_149_
# materials_vs_autovestavby]]) zustava u PUVODNIHO chovani (jen primo/
# sekundarne prirazene produkty), bez dedeni z podkategorii - i proto
# mela 600 polozek a zpusobila SSR-strop problem (viz komentare nize
# u products[:100]).
CATEGORY_ID_MATERIALY_ROOT = 149


def _category_products_with_images(cur, cat_id, limit=None, sort="price_asc",
                                    cross_sections=None, groove_families=None):
    # Robert 2026-08-09: vychozi hodnota sjednocena s category_content_get()
    # (verejne API) - pripadny novy volajici bez explicitniho sort= tak
    # dostane stejne poradi jako klient, misto tiseho nesouladu (viz
    # zaznam u volani v _category_page_response o par set radku vys).
    # Sdilena logika pro produkty kategorie + jejich nahledovy obrazek
    # (fotogalerie modul, s fallbackem na Shoptet import) - pouziva
    # category_content_get (API pro klienta) i _category_page_response
    # (SSR pro roboty, viz SEO audit 2026-08-03), aby se nedublovala.
    # price_visible_default/hover_show_price/hover_show_availability
    # (bot4, 2026-08-08, "Hover okno produktu") - stock_qty/
    # availability_text uz predtim SELECT nemel, potreba pro obsah
    # hover panelu na karte (viz webapp/category.html::renderProducts).
    order_sql = CATEGORY_PRODUCT_SORT_SQL.get(sort, CATEGORY_PRODUCT_SORT_SQL["name"])
    # bot5 2026-08-10 (Robert: filtrace v kategorii podle prurezu/drazky
    # profilu) - cross_sections/groove_families jsou volitelne seznamy
    # hodnot pro IN (); prazdne/None = bez filtru (puvodni chovani beze
    # zmeny). Hodnoty se porovnavaji na cross_section_label/groove_family
    # (viz sql/2026-08-10_product_cross_section_groove.sql, doplneno
    # backfillem ze struktury SKU - jen profilove produkty je maji
    # vyplnene, ostatni jsou NULL a filtrem se tedy vzdy vyradi).
    # bot5 2026-09-17 (Robert pres bot7: "kategorie eshopu je potreba
    # osadit sestavama, at je to videt, takze 1 sestava muze byt na vice
    # kategoriich") - product je v kategorii, kdyz je to jeho PRIMARNI
    # `category_id`, NEBO je navazan pres `shop_product_categories`
    # (sekundarni kategorie, viz sql/2026-09-17_shop_product_categories.sql).
    # `category_id` zustava jedina primarni (breadcrumb/canonical URL),
    # tahle podminka jen ROZSIRUJE, co se na strance KATEGORIE zobrazi.
    try:
        cat_id_int = int(cat_id)
    except (TypeError, ValueError):
        cat_id_int = None

    if cat_id_int == CATEGORY_ID_NAPOSLEDY_PRIDANE:
        # Dynamicky obsah (viz komentar u CATEGORY_ID_NAPOSLEDY_PRIDANE
        # vyse) - filtry/sort volane touhle funkci se sem nevztahuji
        # (cross_sections/groove_families/sort jsou pro rucne
        # kategorizovany katalog, tady je poradi VZDY "nejnovejsi
        # zakaznikovi"). Radi se podle COALESCE(activated_at,
        # created_at) - `activated_at` je kdy se karta REALNE stala
        # viditelnou zakaznikovi (aktivace muze prijit klidne tyden po
        # zalozeni karty, zvlast u Vandr davkoveho importu), `created_at`
        # je zaskok jen pro par legacy radku bez activated_at (overeno
        # 2026-09-25: 3 z 661 aktivnich karet, vsechny stare zalozene
        # primym SQL insertem mimo admin aktivacni tlacitko).
        sql = ("SELECT id, sku, name, slug, description, unit, price_czk_placeholder, weight_g, cfg_dily_id, is_board_material, is_profile_material, "
               "cross_section_label, groove_family, umisteni_id, "
               "stock_qty, availability_text, price_visible_default, hover_show_price, hover_show_availability "
               "FROM shop_products WHERE active=1 AND is_archived=0 "
               "ORDER BY COALESCE(activated_at, created_at) DESC LIMIT 10")
        cur.execute(sql)
        products = cur.fetchall()
    else:
        # Robert 2026-09-25 (pres bot3, pravidlo 52): "ve stromu kategorii
        # chci aby se sestavy radily do prehledu i v kategoriich hlavnich,
        # cim hloubeji se jde do podkategorii tim se vypis produktu/sestav
        # zuzuje" - kategorie ukazuje produkty SEBE + VSECH potomku
        # (libovolne hloubky), ne jen primo/sekundarne prirazene sobe.
        #
        # VYJIMKA (Robert 2026-09-25, upresneni): cela vetev materialu
        # (CATEGORY_ID_MATERIALY_ROOT = 149) z tohohle dedeni VYJMUTA -
        # dedeni bylo mireno na produktove/sestavove kategorie (Vestavby,
        # Balici stoly, Ergonomicke stoly, Montazni stoly), ne na katalog
        # jednotlivych materialovych dilu. Test: je cat_id soucasti
        # podstromu 149? Pokud ano, pouzit jen [cat_id] (puvodni chovani).
        materialy_subtree = _category_descendant_ids(cur, CATEGORY_ID_MATERIALY_ROOT)
        if cat_id_int in materialy_subtree:
            descendant_ids = [cat_id]
        else:
            descendant_ids = _category_descendant_ids(cur, cat_id)
        id_placeholders = ",".join(["%s"] * len(descendant_ids))
        sql = ("SELECT id, sku, name, slug, description, unit, price_czk_placeholder, weight_g, cfg_dily_id, is_board_material, is_profile_material, "
               "cross_section_label, groove_family, umisteni_id, "
               "stock_qty, availability_text, price_visible_default, hover_show_price, hover_show_availability "
               f"FROM shop_products WHERE (category_id IN ({id_placeholders}) OR id IN "
               f"(SELECT product_id FROM shop_product_categories WHERE category_id IN ({id_placeholders}))) "
               "AND active=1 AND is_archived=0")
        params = list(descendant_ids) + list(descendant_ids)
        if cross_sections:
            sql += f" AND cross_section_label IN ({','.join(['%s'] * len(cross_sections))})"
            params.extend(cross_sections)
        if groove_families:
            # bot5 2026-08-10 (Robert: "uhelniky nemaji zobaky, takze pasuji
            # na libovolnou drazku, dej jim vsechny 3 ikony") - groove_family
            # muze byt CSV vice hodnot ("6,8,10") u prislusenstvi bez fyzicke
            # vazby na konkretni sirku drazky. FIND_IN_SET misto IN() funguje
            # spravne pro jednu i vice hodnot zaroven (jednohodnotova pole
            # "8" se chovaji jako 1-prvkovy seznam, FIND_IN_SET('8','8')=1).
            sql += " AND (" + " OR ".join(["FIND_IN_SET(%s, groove_family)"] * len(groove_families)) + ")"
            params.extend(groove_families)
        sql += f" ORDER BY {order_sql}"
        if limit:
            sql += " LIMIT %s"
            params.append(limit)
        cur.execute(sql, params)
        products = cur.fetchall()
    image_by_product = {}
    product_ids = [p["id"] for p in products]
    if product_ids:
        placeholders = ",".join(["%s"] * len(product_ids))
        # bot10, 2026-09-12 (stejna dira jako api/categories.py, nalez
        # bot3): chybejici is_public filtr - tahle funkce naplnuje
        # nahledove obrazky na VEREJNE strance kategorie/storefrontu.
        cur.execute(f"""
            SELECT owner_id, filename FROM content_gallery_items
            WHERE owner_type='product' AND owner_id IN ({placeholders}) AND is_public=1
            ORDER BY owner_id, sort_order, id
        """, product_ids)
        for r in cur.fetchall():
            image_by_product.setdefault(r["owner_id"], f"/content-files/gallery-items/{r['filename']}")
        missing_ids = [pid for pid in product_ids if pid not in image_by_product]
        if missing_ids:
            placeholders2 = ",".join(["%s"] * len(missing_ids))
            cur.execute(f"""
                SELECT product_id, filename FROM shop_product_images
                WHERE product_id IN ({placeholders2})
                ORDER BY product_id, sort_order, id
            """, missing_ids)
            for r in cur.fetchall():
                image_by_product.setdefault(r["product_id"], f"/content-files/gallery/{r['filename']}")
        # Robert 2026-08-08 ("hlavni fotky render, hover obrazky schemata") -
        # druhy obrazek (sort_order=1, u Dogus produktu je to schema/vykres)
        # se ukaze jen pri najeti mysi na karte v prehledu - viz
        # webapp/category.html::renderProducts (.cp-image-hover). Bere se
        # VZDY z shop_product_images (ne z content_gallery_items - ta je
        # pro rucne kurátorovanou fotogalerii, nema jasny "hover" slot).
        hover_image_by_product = {}
        placeholders3 = ",".join(["%s"] * len(product_ids))
        cur.execute(f"""
            SELECT product_id, filename FROM shop_product_images
            WHERE product_id IN ({placeholders3}) AND sort_order=1
        """, product_ids)
        for r in cur.fetchall():
            hover_image_by_product[r["product_id"]] = f"/content-files/gallery/{r['filename']}"
    # Stitek umisteni v autě na karte (WORKFLOW.md pravidlo 51, Robert
    # 2026-09-24 pres bot3: "nikoho na prehledu nezajima kod, zrusit,
    # pridat stitek umisteni v aute") - dva zdroje, stejny cilovy tvar
    # jako uz pouziva bot8 v /api/product-assemblies (commit eb0d7650):
    # 1) primo shop_products.umisteni_id (Vandr karty, bot10 2026-09-24,
    #    commit 5afa327a), 2) product_assemblies.umisteni_id pres
    #    shop_product_id (nase sestavy). Kdyz je vyplnene obojí (nemelo by
    #    nastat), vyhrava primy sloupec. Prazdne = NEUKAZOVAT NIC (na
    #    rozdil od cervene "?" ve scene.html pro staff - tady je to
    #    verejna zakaznicka stranka, bot3: "dokud je prazdne, neukazovat
    #    nic, ne prazdny ramecek").
    umisteni_by_product = {}
    if product_ids:
        placeholders4 = ",".join(["%s"] * len(product_ids))
        cur.execute(f"""
            SELECT sp.id AS product_id, ru.kod AS umisteni_kod, ru.nazev AS umisteni_nazev
            FROM shop_products sp JOIN regal_umisteni ru ON ru.id = sp.umisteni_id
            WHERE sp.id IN ({placeholders4})
        """, product_ids)
        for r in cur.fetchall():
            umisteni_by_product[r["product_id"]] = (r["umisteni_kod"], r["umisteni_nazev"])
        missing_umisteni_ids = [pid for pid in product_ids if pid not in umisteni_by_product]
        if missing_umisteni_ids:
            placeholders5 = ",".join(["%s"] * len(missing_umisteni_ids))
            cur.execute(f"""
                SELECT pa.shop_product_id AS product_id, ru.kod AS umisteni_kod, ru.nazev AS umisteni_nazev
                FROM product_assemblies pa JOIN regal_umisteni ru ON ru.id = pa.umisteni_id
                WHERE pa.shop_product_id IN ({placeholders5})
            """, missing_umisteni_ids)
            for r in cur.fetchall():
                umisteni_by_product.setdefault(r["product_id"], (r["umisteni_kod"], r["umisteni_nazev"]))
    # Stitek hlavniho profilu na karte (Robert 2026-09-25 pres bot3,
    # pravidlo 52 - "hlavni profil, strana auta"). Stejny dvouzdrojovy
    # vzor jako umisteni vyse: primo shop_products.vandr_hlavni_prurez_mm
    # (Vandr, bot10), jinak product_assemblies.profil_mm (nase sestavy).
    # Cislo je jednotny rozmer CTVERCOVEHO profilu (30 = "30x30") -
    # format na "NxN" dela az frontend.
    profil_by_product = {}
    if product_ids:
        placeholders6 = ",".join(["%s"] * len(product_ids))
        cur.execute(f"""
            SELECT id AS product_id, vandr_hlavni_prurez_mm AS profil_mm
            FROM shop_products WHERE id IN ({placeholders6}) AND vandr_hlavni_prurez_mm IS NOT NULL
        """, product_ids)
        for r in cur.fetchall():
            profil_by_product[r["product_id"]] = r["profil_mm"]
        missing_profil_ids = [pid for pid in product_ids if pid not in profil_by_product]
        if missing_profil_ids:
            placeholders7 = ",".join(["%s"] * len(missing_profil_ids))
            cur.execute(f"""
                SELECT shop_product_id AS product_id, profil_mm
                FROM product_assemblies WHERE shop_product_id IN ({placeholders7}) AND profil_mm IS NOT NULL
            """, missing_profil_ids)
            for r in cur.fetchall():
                profil_by_product.setdefault(r["product_id"], r["profil_mm"])
    for p in products:
        if p.get("price_czk_placeholder") is not None:
            p["price_czk_placeholder"] = float(p["price_czk_placeholder"])
        p["image_url"] = image_by_product.get(p["id"])
        p["image_url_hover"] = hover_image_by_product.get(p["id"]) if product_ids else None
        # Robert pres bot3, 2026-09-25 ("musí mít ty rendery všechny stejně
        # velké stejný formát", "ty náhledy fotek jsou malé, měly by
        # přesáhnout celou šířku") - zdrojove nahledy maji 3 ruzne pomery
        # stran (480x480, 1024x768, 654x654, viz scripts/2026-09-25_zmer_
        # ramovani_nahledu.py). Ctvercova dlazdice + object-fit:contain
        # nutila 4:3 fotky do prazdnych pruhu nahore/dole ("vypadaly
        # mensi"). Reseni: dlazdice uz nema pevny aspect-ratio, image_width/
        # image_height jdou primo na klientsky <img width height> (CLS
        # ochrana - viz webapp/category.html renderProducts()), kazda fotka
        # se tak vykresli v PLNE sirce a SVE VLASTNI vysce, zadny orez ani
        # prazdny pruh. _content_file_dimensions je @lru_cache(512) - cena
        # navic jen pri prvnim volani pro danou URL v procesu.
        dims = _content_file_dimensions(p["image_url"]) if p["image_url"] else None
        p["image_width"], p["image_height"] = dims if dims else (None, None)
        p["price_visible_default"] = bool(p.get("price_visible_default", 1))
        p["hover_show_price"] = bool(p.get("hover_show_price", 1))
        p["hover_show_availability"] = bool(p.get("hover_show_availability", 0))
        umisteni = umisteni_by_product.get(p["id"])
        p["umisteni_kod"] = umisteni[0] if umisteni else None
        p["umisteni_nazev"] = umisteni[1] if umisteni else None
        p.pop("umisteni_id", None)
        p["profil_mm"] = profil_by_product.get(p["id"])
    return products














ALLOWED_CATEGORY_IMAGE_EXT = {"jpg", "jpeg", "png", "webp", "gif"}


def _slugify(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "kategorie"




def _unique_product_slug(cur, base, exclude_id=None):
    # Stejny vzor jako _unique_category_slug; produktove slugy vznikly
    # jednorazovym backfillem (commit 4e1267d), ale zadna INSERT cesta
    # (navrh sestavy ze sceny, admin karta, CSV import) slug nenastavovala
    # -> nove produkty koncily v sitemape jako product.html?id= (QA seo.py
    # SEO_SITEMAP_QUERY_URL, bot15/bot3 2026-09-02).
    base = base or "produkt"
    candidate = base
    n = 2
    while True:
        if exclude_id is not None:
            cur.execute("SELECT id FROM shop_products WHERE slug=%s AND id<>%s", (candidate, exclude_id))
        else:
            cur.execute("SELECT id FROM shop_products WHERE slug=%s", (candidate,))
        if not cur.fetchone():
            return candidate
        candidate = f"{base}-{n}"
        n += 1


def _product_slug_for_name(cur, name, exclude_id=None):
    """Adresa (slug) produktu z nazvu. Od 2026-10-01 ji tvori JEDINY mechanismus api/product_slug.py
    (bez interniho nazvu dodavatele, nejvys 70 znaku, unikatni i vuci starym presmerovanym adresam) - tady
    jen predani, at vsechny cesty zakladajici produkt (karta, import, sestava, duplikace) tvori adresy stejne."""
    import product_slug
    return product_slug.slug_for_name(cur, name, exclude_id)


# --- Verejny popisek provedeni sestavy -------------------------------------
#
# `product_assemblies.name` je PRACOVNI nazev ze sceny - boti a davkove
# skripty si do nej pripisuji poznamky a kody. Ven k zakaznikovi se z nej
# NESMI dostat:
#   * kod karoserie K-XXX  - WORKFLOW.md pravidlo 25 ("kod patri do DB,
#     NE do produktovych karet sestav regalu"),
#   * [hranata zavorka]    - zavedeny zpusob, jak si pripsat poznamku pro
#     nas ("[10/30mm od kolize]" = kolizni rezerva, "[ZÁKLAD]" = zastupce).
#
# PROC JE TO NA SERVERU (bot5, 2026-09-12, nalezl bot3 pri zapnuti karet):
# tataz logika uz byla v `pdOcistiVerejnyPopisek()` ve `webapp/product.html`,
# jenze ta bezi na KLIENTOVI - cistila jen to, co si vykresli prohlizec.
# Kdokoli zavolal `/api/shop/products/<id>/assemblies` primo (curl, devtools,
# scraper), dostal syrovy text. Klientska pojistka zustava jako DRUHA vrstva,
# ne jedina; tohle je ta prvni.
#
# Plati pro OBA verejne vystupy, ne jen pro ten nalezeny:
#   * `/api/shop/products/<id>/assemblies` (product_assemblies.py)
#   * `/api/storefront/products`           (car_storefronts.py)
# U storefrontu je to o to dulezitejsi, ze bezi na SKRYTE domene: sdileny
# identifikator jako K-075 je presne ten "fingerprint", pred kterym varuje
# TEXT_FILTR.md pravidlo 4 (dva weby jdou spojit pres vygooglovany kod).
#
# Hlidaji to i kontroly `k_kod_v_zakaznickem_textu` a
# `interni_poznamka_v_zakaznickem_textu` v qa_checks.py - ty ukazuji na
# PRICINU (spatny text v DB), tohle je nasledek necha v DB a jen ho nepusti
# ven. Az bude rozhodnuto, kde bydli zakaznicky nazev (samostatne pole,
# k 2026-09-12 otevrena otazka na Roberta), tahle funkce plati dal - kdyby
# se nekdo vratil k pracovnimu nazvu jako fallbacku, porad chrani.
_VEREJNY_POPISEK_ZAVORKA_RE = re.compile(r"\[[^\]]*\]")
_VEREJNY_POPISEK_KKOD_RE = re.compile(r"\bK-\d{3}[a-z]?\b", re.IGNORECASE)
_VEREJNY_POPISEK_PREFIX_RE = re.compile(r"^\s*(NÁHLED|NAHLED)\s+", re.IGNORECASE)
# Robert 2026-09-15 (pres bot3): barevny puntik na zacatku nazvu ("🟠") je
# jen JEHO osobni vizualni znacka ve scene, nikdy nesmi projit ven -
# unikalo to zive na kartu 3947. Python stdlib `re` nema \p{Extended_
# Pictographic} (jen 3rd-party `regex` balicek) - misto toho explicitni
# Unicode rozsahy pokryvajici bezne emoji bloky (barevne kolecko/ctverec,
# starsi symboly, variation selector), at je to odolne i vuci JINYM
# barvam/znackam, ktere Robert casem pouzije, ne jen tomuhle jednomu.
_VEREJNY_POPISEK_EMOJI_RE = re.compile(r"^[☀-➿\U0001F300-\U0001FAFF️\s]+")


def verejny_popisek_sestavy(name):
    """Pracovni nazev sestavy -> popisek, ktery smi videt zakaznik.

    Zrcadli `pdOcistiVerejnyPopisek()` + `pdAssemblyLabel()` ve
    webapp/product.html. Kdyz se meni jedna strana, MUSI se zmenit druha -
    proto ma kazda v komentari odkaz na tu druhou.
    """
    s = str(name or "").strip()
    s = _VEREJNY_POPISEK_EMOJI_RE.sub("", s)      # osobni znacka ze sceny ("🟠" apod.)
    s = re.sub(r"\s*\([^()]*\)\s*$", "", s)      # koncova zavorka s vozidlem
    s = _VEREJNY_POPISEK_PREFIX_RE.sub("", s)    # sluzebni prefix ze sceny
    s = re.sub(r"\s{2,}", " ", s).strip()
    # "<kod bez mezer> - <popis se slovy>" -> vezmi jen popis. Rozhoduje
    # OBSAH (kod nema mezery, popis ma slova), ne tvar kodu - ten se uz
    # dvakrat zmenil.
    m = re.match(r"^(\S+)\s+[-–]\s+(.+)$", s)
    if m and re.search(r"[a-záčďéěíňóřšťúůýž]+\s+\S", m.group(2), re.IGNORECASE):
        s = m.group(2).strip()
    # Cisteni je AZ TADY, jako posledni krok: at se nazev rozparsuje jakkoli,
    # ven projde jen to, co proslo tudy.
    s = _VEREJNY_POPISEK_ZAVORKA_RE.sub(" ", s)
    s = _VEREJNY_POPISEK_KKOD_RE.sub(" ", s)
    s = re.sub(r"^\s*[-–]\s*", "", s)            # osamely oddelovac po orezu
    s = re.sub(r"\s*[-–]\s*$", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    # Kdyz nezbylo nic (nazev byl JEN kod/poznamka), radsi neutralni popisek
    # nez propustit puvodni text zpatky ven.
    return s or "Provedení"


def obsahuje_interni_znaceni(s):
    """Je v textu neco, co k zakaznikovi nesmi (kod karoserie / [poznamka] /
    osobni znacka ze sceny)? Pouziva i `verejny_popisek_galerie()` nize -
    bez emoji tady by tretim kanalem (popisek fotky) mohla znacka unikat
    dal, i kdyz `verejny_popisek_sestavy()` uz ji cisti."""
    s = str(s or "")
    return bool(
        _VEREJNY_POPISEK_ZAVORKA_RE.search(s)
        or _VEREJNY_POPISEK_KKOD_RE.search(s)
        or _VEREJNY_POPISEK_EMOJI_RE.match(s)
    )


def verejny_popisek_galerie(caption):
    """Popisek obrazku v galerii produktu ocisteny pro zakaznika.

    TRETI VYSTUPNI BOD nazvu sestavy (bot5, 2026-09-12, nalezeno pri overovani
    po zapnuti karet; rozdeleni prace domluvil bot3). Popisek se sklada v
    `api/turntable.py` pri commitu otocky jako "<nazev sestavy> - pohled
    zepredu" a `shop_products_get` ho posila anonymnimu navstevnikovi. Kdyz
    jsem cistil nazvy provedeni, tenhle kanal jsem minul - slo ven napr.
    "K-075-EB-30-C-0063-2-0 - jedno pasmo, ram + dna [ZÁKLAD] [10/30mm od
    kolize] - pohled zepredu".

    Oprava na STRANE ZAPISU patri do `turntable.py` a resi ji bot4 - tohle je
    pojistka na VYSTUPU, aby unik prestal okamzite a nezavisle na tom, kdy se
    zdroj opravi. Po obou opravach zustava jako druha vrstva, stejne jako u
    nazvu provedeni.

    ⚠️ ZAMERNE se necisti KAZDY popisek. `verejny_popisek_sestavy()` v sobe ma
    krok "<kod bez mezer> - <popis se slovy>" -> vezmi jen popis, ktery je
    spravny pro nazev sestavy, ale bezny popisek fotky by zmrzacil:
    "Profil 30x30 - detail drazky" by prisel o prvni slovo. Cisti se proto jen
    popisek, ve kterem SKUTECNE neco zakazaneho je - bezne popisky projdou
    beze zmeny a riziko poskozeni spravneho textu je nulove.
    """
    if not caption:
        return caption
    if not obsahuje_interni_znaceni(caption):
        return caption
    return verejny_popisek_sestavy(caption)






# ============================================================
# Homepage mozaika (Robert 2026-08-09: "na homepage vytvoř system
# sudeho poctu oken, ktere lze pridavat a odebirat... mozaika...
# pozitivni vliv na SEO/GEO... funkce jakoby mala web stranka
# zmensena, kde lze menit nazev, meta popis, obrazek, telo textu").
# AskUserQuestion: kazda dlazdice odkazuje na VLASTNI stranku
# (/blok/<slug>) se skutecnym title/meta description - realny SEO
# prinos (vic indexovatelnych stranek), ne jen kosmeticky prvek.
# Robert 2026-08-09 ("zrusme sudost" / "nemusi byt sude") - puvodni
# pozadavek na SUDY pocet viditelnych dlazdic zamerne zruseny, zadne
# omezeni poctu v CRUD endpointech nize.
# ============================================================
# CRUD admin routy /api/admin/homepage-blocks* vycleneny do
# api/cms_blocks.py (bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md
# skupina 2). HOMEPAGE_BLOCK_IMAGE_DIR/_homepage_block_public tamtez.
# Nize zustava jen to, co pouziva verejne SSR renderovani homepage
# (_render_homepage_mosaic_html nize).


@functools.lru_cache(maxsize=512)
def _content_file_dimensions(rel_url):
    """(width, height) obrazku pod /content-files/... pro atributy
    width/height v SSR <img> (CLS), nebo None. Cache podle URL - soubory
    v content-files se nemeni pod stejnym jmenem (upload = novy nazev)."""
    if not rel_url.startswith("/content-files/"):
        return None
    path = os.path.join(UPLOAD_DIR, unquote(rel_url[len("/content-files/"):]))
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


# og:image 1200x630 (bot15/bot3, 2026-09-02, QA seo.py SEO_OG_IMAGE_SMALL na
# 139/147 strankach): fotky produktu/kategorii jsou vetsinou ctvercove
# 1000x1000 nebo mensi, Facebook/LinkedIn/Seznam chteji >=1200x630 (1.91:1)
# a jinak nahled orizou/zmensi. Odvozenina se generuje jednou a cachuje na
# disku v content-files/og/ (mimo git, jako ostatni uploady), klic = hash
# zdrojove cesty + mtime + velikost, takze zmena zdroje = novy soubor.
# Zdroj s pomerem blizkym 1.91 (turntable hero 16:9, site-default) se jen
# oreze (cover), ostatni dostanou rozmazane cover pozadi ze stejne fotky +
# celou fotku uprostred (contain) - stejny postup jako rucne vyrobeny
# content-files/og/site-default.jpg (blok 2). Pri jakekoli chybe (Pillow,
# prava, chybejici soubor) se vraci None a stranka pouzije puvodni URL.
OG_IMAGE_W, OG_IMAGE_H = 1200, 630
OG_IMAGE_DIR = os.path.join(UPLOAD_DIR, "og")


_OG_IMAGE_CACHE = {}


def _og_image_1200x630(rel_url):
    """Vrati (rel_url_1200x630, 1200, 630) pro obrazek pod /content-files/,
    nebo None. Uspech cachovany v pameti (per worker) i na disku; neuspech
    se necachuje (docasna chyba prav/souboru nema zustat viset do restartu)."""
    if not rel_url or not rel_url.startswith("/content-files/"):
        return None
    hit = _OG_IMAGE_CACHE.get(rel_url)
    if hit:
        return hit
    res = _og_image_1200x630_build(rel_url)
    if res and len(_OG_IMAGE_CACHE) < 4096:
        _OG_IMAGE_CACHE[rel_url] = res
    return res


def _og_image_1200x630_build(rel_url):
    if rel_url.startswith("/content-files/og/"):
        dims = _content_file_dimensions(rel_url)
        return (rel_url, dims[0], dims[1]) if dims else None
    src = os.path.join(UPLOAD_DIR, unquote(rel_url[len("/content-files/"):]))
    try:
        st = os.stat(src)
    except OSError:
        return None
    key = hashlib.sha1(f"{src}|{int(st.st_mtime)}|{st.st_size}".encode("utf-8")).hexdigest()[:20]
    out_name = f"{key}.jpg"
    out_path = os.path.join(OG_IMAGE_DIR, out_name)
    out_rel = f"/content-files/og/{out_name}"
    if os.path.exists(out_path):
        return (out_rel, OG_IMAGE_W, OG_IMAGE_H)
    try:
        from PIL import Image, ImageFilter
        os.makedirs(OG_IMAGE_DIR, exist_ok=True)
        with Image.open(src) as im0:
            im = im0.convert("RGB")
        W, H = OG_IMAGE_W, OG_IMAGE_H
        target_ratio = W / H
        ratio = im.width / im.height
        s = max(W / im.width, H / im.height)
        cover = im.resize((max(W, round(im.width * s)), max(H, round(im.height * s))), Image.LANCZOS)
        left, top = (cover.width - W) // 2, (cover.height - H) // 2
        cover = cover.crop((left, top, left + W, top + H))
        if abs(ratio - target_ratio) / target_ratio <= 0.12:
            out = cover
        else:
            out = cover.filter(ImageFilter.GaussianBlur(28))
            s2 = min(W / im.width, H / im.height)
            fg = im.resize((max(1, round(im.width * s2)), max(1, round(im.height * s2))), Image.LANCZOS)
            out.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
        tmp_path = out_path + ".tmp"
        out.save(tmp_path, "JPEG", quality=85, optimize=True, progressive=True)
        os.replace(tmp_path, out_path)
        return (out_rel, W, H)
    except Exception as e:
        app.logger.warning("og:image 1200x630 selhalo pro %s: %s", rel_url, e)
        return None


def _render_homepage_mosaic_html(blocks, gallery_images_by_category=None):
    # Stejny vizualni vzor jako .cat-product-card/.cp-media
    # (category.html) - viz AskUserQuestion 2026-08-09 "Stejný styl
    # jako karty produktů". Vlastni tridy (hp-*) misto sdilenych cp-*,
    # protoze tohle NEJSOU produkty (jina sada CSS v index.html).
    #
    # Vraci (first_card_html, rest_cards_html) - Robert pres bot3,
    # 2026-09-27 ("jednu dlazdici mozaiky dej napravo od carouselu"):
    # prvni dlazdice (podle stejneho sort_order razeni jako predtim) se
    # renderuje SAMA, aby ji volajici mohl umistit vedle #hpCarousel
    # (viz .hp-top-row v _index_page_response), zbytek jde do
    # #hpMosaic jako drive. Jeden pruchod blocks - `first_img` (LCP
    # fetchpriority) se tak nastavi spravne jen jednou pro SKUTECNE
    # prvni obrazek stranky, ne znovu pro kazdy dilci vysledek.
    cards = ""
    first_card_html = ""
    # Prvni obrazek mozaiky = LCP prvek homepage (bot15, 2026-09-02, QA
    # seo.py SEO_HERO_IMG_LAZY/NO_DIMENSIONS): bez loading=lazy a s
    # fetchpriority=high, ostatni zustavaji lazy. width/height ze
    # skutecneho souboru u vsech (CSS .hp-image ma pevnou vysku, atributy
    # jen dodaji pomer stran pro prohlizec/robota, vzhled se nemeni).
    first_img = True

    def _img_attrs(url):
        nonlocal first_img
        attrs = ""
        dims = _content_file_dimensions(url)
        if dims:
            attrs += f' width="{dims[0]}" height="{dims[1]}"'
        if first_img:
            first_img = False
            attrs += ' fetchpriority="high" decoding="async"'
        else:
            attrs += ' loading="lazy"'
        return attrs

    for block_idx, b in enumerate(blocks):
        if b.get("gallery_preview"):
            # Robert 2026-08-10 ("z této dlaždice udeláme fotogalerii...
            # v náhledu tam bude carusel prvních 10ti fotek, po kliknutí
            # se vstupuje rovnou na fotogalerii" + "[Foto realizací]
            # z horní lišty zmizí a bude součástí dlaždice") - misto
            # vlastniho obrazku dlazdice karusel prvnich N fotek z jiz
            # hotove fotogalerie (shop_gallery_images/realizace.html),
            # odkaz vede rovnou tam misto na /blok/<slug>. Cisty CSS
            # crossfade (zadny JS) - mozaika je zamerne 100% SSR (viz
            # komentar u volani teto funkce v _index_page_response).
            # Primy inline animation-delay (misto CSS calc(var(--i))) -
            # zadna zavislost na tom, jak dany prohlizec pocita calc()
            # s vlastni CSS promennou a zapornym zpozdenim (Robert:
            # "carusel se ti netočí" - podezreni na tuto kombinaci).
            #
            # gallery_category (Robert 2026-08-10: "tato nová bude pouze
            # pro stoly, a z predeslé pro vestvaby ty fotky stolů
            # přesuneš") - kazda dlazdice muze mit karusel omezeny jen
            # na jednu kategorii fotogalerie (nebo bez omezeni - None).
            cat = b.get("gallery_category")
            imgs = (gallery_images_by_category or {}).get(cat, [])
            # Robert pres bot3, 2026-09-27 ("necht se spousti po kazdem
            # nacteni prvni fotka nahodne, ne ta ktera je na zacatku") -
            # random.sample (NE random.shuffle in-place) - vraci novy list,
            # nemutuje gallery_images_by_category (sdileny mezi vsemi
            # gallery_preview dlazdicemi v tomhle requestu, viz volani vyse).
            imgs = random.sample(imgs, k=len(imgs))
            img_html = "".join(
                f'<img class="hp-image hp-gallery-img" style="animation-delay:{i * 3}s" '
                f'src="{_og_escape(g["url"])}" alt="{_og_escape(g.get("title") or b["title"])}"{_img_attrs(g["url"])}>'
                for i, g in enumerate(imgs)
            )
            href = f"/realizace.html?category={quote(cat)}" if cat else "/realizace.html"
        else:
            block_img_url = f'/content-files/homepage-blocks/{quote(b["image_filename"])}' if b.get("image_filename") else None
            img_html = (
                f'<img class="hp-image" src="{block_img_url}" '
                f'alt="{_og_escape(b["title"])}"{_img_attrs(block_img_url)}>'
                if block_img_url else ""
            )
            href = f'/blok/{quote(b["slug"])}'
        excerpt = _og_escape((b.get("meta_description") or "").strip()[:160])
        card = (
            '<div class="hp-block-card">'
            f'<a href="{href}" style="text-decoration:none;color:inherit;">'
            f'<div class="hp-media">{img_html}</div>'
            f'<div class="hp-block-title">{_og_escape(b["title"])}</div>'
            + (f'<div class="hp-block-excerpt">{excerpt}</div>' if excerpt else "")
            + '</a></div>'
        )
        if block_idx == 0:
            first_card_html = card
        else:
            cards += card
    return first_card_html, cards


# Robert pres bot3, 2026-09-27 ("na nas homepage chceme stejny carousel
# jako je na homepage logimanu") - CRUD admin routy /api/admin/
# homepage-carousel* v api/cms_blocks.py. Tady jen verejne SSR
# renderovani (stejny vzor jako _render_homepage_mosaic_html vyse -
# 100% SSR, zadny klientsky fetch, JS v index.html jen prida crossfade/
# sipky/puntiky nad uz existujici markup - viz initHomepageCarousel()).
def _render_homepage_carousel_html(slides):
    slides_html = ""
    dots_html = ""
    first_img = True
    for i, s in enumerate(slides):
        img_url = f'/content-files/homepage-carousel/{quote(s["image_filename"])}' if s.get("image_filename") else None
        if not img_url:
            continue
        dims = _content_file_dimensions(img_url)
        dim_attrs = f' width="{dims[0]}" height="{dims[1]}"' if dims else ""
        # Prvni snimek = LCP prvek homepage (stejny duvod jako u mozaiky
        # vyse) - bez loading=lazy, s fetchpriority=high.
        if first_img:
            first_img = False
            load_attrs = ' fetchpriority="high" decoding="async"'
        else:
            load_attrs = ' loading="lazy"'
        caption = _og_escape(s.get("caption_text") or "")
        img_tag = f'<img class="hp-carousel-image" src="{img_url}" alt="{caption}"{dim_attrs}{load_attrs}>'
        caption_html = f'<div class="hp-carousel-caption">{caption}</div>' if caption else ""
        inner = img_tag + caption_html
        if s.get("link_url"):
            inner = f'<a href="{_og_escape(s["link_url"])}" style="display:block;">{inner}</a>'
        active_cls = " active" if i == 0 else ""
        slides_html += f'<div class="hp-carousel-slide{active_cls}" data-index="{i}">{inner}</div>'
        dots_html += f'<span class="hp-carousel-dot{active_cls}" data-index="{i}"></span>'
    if not slides_html:
        return ""
    return (
        '<div class="hp-carousel-viewport">'
        f'{slides_html}'
        '<button type="button" class="hp-carousel-arrow hp-carousel-prev" aria-label="Předchozí">&#10094;</button>'
        '<button type="button" class="hp-carousel-arrow hp-carousel-next" aria-label="Další">&#10095;</button>'
        f'<div class="hp-carousel-dots">{dots_html}</div>'
        '</div>'
    )


# ============================================================
# HLASKY (bot5 2026-08-10/11, Robert: "udelej pro homepage jednoduchý
# typ dlazdice povedle mozaiky, pro ohlašování nových zpráv novinek
# tzn jen text plnohodnotně pro seo... jen s možností menit barvy
# okrajů" -> (po iteraci) "tato dlaždice není o novinkách ale pro
# hlášky, dlaždici pro novinky udeláme extra jinou další" - PUVODNE
# postavena jako "Novinky" s vlastni SEO strankou na polozku
# (news_items), pak zjednodusena na kratke bezodkazovaci "hlasky" (viz
# _render_announcement_preview_html nize - zadna vlastni stranka, zadny
# klik-skrz, odkazy primo v textu zpravy) a nakonec PREJMENOVANA
# (tabulka news_items -> announcement_items, viz
# sql/2026-08-11_news_items_rename_to_announcements.sql), aby nazev
# nekoliduje se skutecnou budouci "Novinky" dlazdici (ta bude
# potrebovat vlastni tabulku/nazvy, az na ni dojde rada). 1 kompaktni
# dlazdice na homepage rotuje (JS crossfade) poslednich az 3 hlasky,
# zadna samostatna verejna stranka.
# ============================================================


# CRUD admin routy /api/admin/announcement-items* vycleneny do
# api/cms_blocks.py (bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md
# skupina 2). _announcement_item_public/_valid_hex_color tamtez. Nize
# zustava jen verejne SSR renderovani (_render_announcement_preview_html).


def _render_announcement_preview_html(items):
    # Homepage dlaždice - rotace poslednich az 3 kratkych hlasek (JS
    # crossfade, viz initAnnouncementPreviewRotator v index.html).
    # Zadna vlastni stranka na polozku, zadny klik-skrz - telo se
    # renderuje jako SKUTECNE HTML (ne oriznuty cisty text), takze kdyz
    # admin v Quillu vlozi odkaz primo do textu, funguje rovnou v
    # naprevu. Delka reseni cistě CSS (-webkit-line-clamp na
    # .announcement-preview-body), zadne oriznuti retezce v Pythonu (to
    # by mohlo useknout HTML tag uprostred a rozbit znacky/odkaz).
    if not items:
        return ""
    cards = "".join(
        '<div class="announcement-preview-item">'
        f'<div class="announcement-preview-title">{_og_escape(n["title"])}</div>'
        f'<div class="announcement-preview-body">{n.get("body_html") or ""}</div>'
        '</div>'
        for n in items
    )
    card_style = f' style="--announcement-border-color:{_og_escape(items[0]["border_color"])}"' if items[0].get("border_color") else ""
    return (
        f'<div class="announcement-preview-card"{card_style}>'
        f'<div class="announcement-preview-stack">{cards}</div>'
        '</div>'
    )


# ============================================================
# POSTRANNI PANEL (bot5 2026-08-10, Robert: "vloz tam nejdrive panel
# ktery bude videt vzdy na vsech url webu jakoby paticka ale je to
# vlevo pod menu" -> "měla by to být v podstatě další dlaždice,
# akorát má jiné umístění" -> "udelej novou sekci v adminu, a dlazdici
# tam prenes, prekopiruj") - SAMOSTATNA obdoba homepage_blocks (vlastni
# tabulka/admin sekce/verejna stranka), ne sdileny mechanismus - jen
# jine umisteni (levy sidebar na VSECH strankach s menu kategorii, ne
# homepage mozaika) a navic video_filename (Robert: "to video tam
# vloží admin" - vlastni upload tlacitko pro video, ne jen pro
# nahledovy obrazek). Verejna stranka /panel/<slug> ze stejneho duvodu
# jako /blok/<slug> - realny SEO prinos (vlastni title/meta), ne jen
# kosmeticky prvek na spolecne URL.
# ============================================================
# CRUD admin routy /api/admin/sidebar-blocks* + verejny
# GET /api/sidebar-blocks vycleneny do api/cms_blocks.py (bot5,
# 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 2). Verejna SSR
# stranka /panel/<slug> nasleduje nize a zustava v app.py.




def _category_representative_image_url(cur, category_id):
    """Kategorie bez vlastniho `image_filename` "prevezme" obrazek od
    zastupce uvnitr (Robert pres bot3, 2026-09-27: "kazda kategorie ma
    prevzit obrazek od nejakeho zastupce uvnitr"). CISTY FALLBACK NA
    CTENI - nic se nezapisuje do `content_categories.image_filename`,
    pocita se znovu pri kazdem volani (jinak by zastaralo, kdyz se
    zastupcuv obrazek pozdeji zmeni/smaze) - admin tak porad pozna
    z prazdneho sloupce, ze kategorie potrebuje vlastni foto.

    Priorita (deterministicka, stejny vysledek pri kazdem loadu):
    1. prvni PRIMA podkategorie (sort_order, name) se svym VLASTNIM
       image_filename - bez kaskadovani do vnuku (jen 1 uroven dolu).
    2. jinak prvni aktivni produkt primo v teto kategorii (id ASC) se
       skutecnym obrazkem - content_gallery_items (verejne, is_public=1)
       prednostne, pak shop_product_images (stejna priorita jako jinde
       v kodu, viz _category_products_with_images).
    3. jinak None (zadny zastupce k mani).
    """
    cur.execute(
        "SELECT image_filename FROM content_categories "
        "WHERE parent_id=%s AND image_filename IS NOT NULL "
        "ORDER BY sort_order, name LIMIT 1",
        (category_id,),
    )
    row = cur.fetchone()
    if row:
        return f"/content-files/categories/{quote(row['image_filename'])}"

    cur.execute(
        "SELECT id FROM shop_products WHERE category_id=%s AND active=1 AND is_archived=0 ORDER BY id",
        (category_id,),
    )
    product_ids = [r["id"] for r in cur.fetchall()]
    if not product_ids:
        return None
    placeholders = ",".join(["%s"] * len(product_ids))

    cur.execute(
        f"SELECT owner_id, filename FROM content_gallery_items "
        f"WHERE owner_type='product' AND owner_id IN ({placeholders}) AND is_public=1 "
        f"ORDER BY owner_id, sort_order, id",
        product_ids,
    )
    gallery_by_product = {}
    for r in cur.fetchall():
        gallery_by_product.setdefault(r["owner_id"], r["filename"])
    for pid in product_ids:
        if pid in gallery_by_product:
            return f"/content-files/gallery-items/{quote(gallery_by_product[pid])}"

    cur.execute(
        f"SELECT product_id, filename FROM shop_product_images "
        f"WHERE product_id IN ({placeholders}) ORDER BY product_id, sort_order, id",
        product_ids,
    )
    spi_by_product = {}
    for r in cur.fetchall():
        spi_by_product.setdefault(r["product_id"], r["filename"])
    for pid in product_ids:
        if pid in spi_by_product:
            return f"/content-files/gallery/{quote(spi_by_product[pid])}"
    return None


def _build_category_tree(cur, show_hidden):
    # Sdilena logika pro /api/categories (JSON pro klienta) i SSR strom
    # v _category_page_response/_render_category_tree_html - aby se
    # nedublovala (Robert: "nasad kategoricky strom strukturalne po
    # vzoru Bazarai").
    cur.execute("""
        SELECT id, parent_id, name, slug, sort_order, nav_label,
               is_visible, menu_expanded, image_filename, menu_group_label, pending_review
        FROM content_categories ORDER BY parent_id IS NULL DESC, sort_order, name
    """)
    rows = cur.fetchall()
    by_parent = {}
    for r in rows:
        by_parent.setdefault(r["parent_id"], []).append(r)

    def build(parent_id):
        out = []
        for r in by_parent.get(parent_id, []):
            if not show_hidden and not r["is_visible"]:
                continue
            image_url = (
                f'/content-files/categories/{quote(r["image_filename"])}' if r["image_filename"]
                else _category_representative_image_url(cur, r["id"])
            )
            out.append({
                "id": r["id"], "name": r["name"], "slug": r["slug"], "sort_order": r["sort_order"],
                "nav_label": r["nav_label"], "is_visible": bool(r["is_visible"]),
                "menu_expanded": bool(r["menu_expanded"]), "image_filename": r["image_filename"],
                "image_url": image_url,
                # bot16, 2026-09-17 (Robert pres bot7): cistě vizualni
                # skupinovy nadpis NAD timhle uzlem v levem menu ("PODLE
                # VOZIDLA" apod.) - NENI to klikatelna kategorie/URL,
                # jen popisek. NULL = zadny nadpis (vetsina uzlu).
                "menu_group_label": r["menu_group_label"],
                # Robert 2026-09-25 ("dej jim jinou barvu textu at to
                # mohu rozeznat a posoudit") - docasny priznak nove
                # pridanych kategorii (viz sql/2026-09-25_content_
                # categories_pending_review.sql), vizualne se ukazuje v
                # levem strome (cat-tree-name-new trida).
                "pending_review": bool(r["pending_review"]),
                "children": build(r["id"]),
            })
        return out

    return build(None)


def _category_tree_show_hidden():
    user = current_user()
    return bool(user) and has_permission(user, "kategorie", "zobrazit")














































# bot4, 2026-07-26 (Robert: "zrušme na eshopu diskuze u produktů a
# kategorií") - POST /api/categories/<id>/comments (pridani komentare)
# ZRUSEN. Puvodni endpoint vkladal do `content_comments` (tabulka
# NEsmazana, jen se do ni uz nezapisuje/necte - viz category_content_get
# vyse). Kdyby se diskuze mely v budoucnu vratit, kod je dohledatelny v
# gitu (git log -p -- api/app.py, hledej "category_comment_add").




# Interni tymovy chat vyclenen do api/internal_chat.py (bot5,
# 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 4).

# --- Sestava k objednani (Robert 2026-07-25: "Sestavu k objednani vyres
# databazove ty" - reorder/shortage list je soucast skladoveho systemu
# (bot2), NEZAVISLE na Nakupnich objednavkach (dodavatel/stav/polozky),
# ktere stavi bot3 samostatne. Trvala DB tabulka shop_reorder_items,
# ktera se prubezne synchronizuje s aktualnim nedostatkem skladu
# (stock_qty vs min_stock, pripadne zaporny stock_qty). Pracovnik si
# rucne oznaci polozky, ktere chce objednat (status "selected") -
# vyber je pripraven k pozdejsimu navazani na Nakupni objednavky od
# bot3, ale tato tabulka s orders.py vubec neinteraguje. ---
def _reorder_sync_from_stock(cur):
    cur.execute("""
        SELECT id AS product_id, GREATEST(COALESCE(min_stock,0) - stock_qty, 0) AS deficit
        FROM shop_products
        WHERE is_archived=0 AND (min_stock IS NOT NULL OR stock_qty < 0)
    """)
    deficits = {r["product_id"]: r["deficit"] for r in cur.fetchall() if r["deficit"] > 0}

    cur.execute("SELECT id, product_id, status FROM shop_reorder_items WHERE source='auto'")
    existing_auto = {r["product_id"]: r for r in cur.fetchall()}

    for product_id, deficit in deficits.items():
        if product_id in existing_auto:
            cur.execute("UPDATE shop_reorder_items SET qty_needed=%s WHERE id=%s",
                        (deficit, existing_auto[product_id]["id"]))
        else:
            cur.execute(
                "INSERT INTO shop_reorder_items (product_id, qty_needed, status, source) "
                "VALUES (%s,%s,'needed','auto')",
                (product_id, deficit),
            )

    # vyresene polozky (dostatek skladu) smazat, jen pokud je jeste nikdo
    # neoznacil k objednani (status "needed") - vybrane ("selected")
    # ponechavame, dokud je admin/pracovnik sam neodstrani
    to_clear = [r["id"] for pid, r in existing_auto.items()
                if pid not in deficits and r["status"] == "needed"]
    if to_clear:
        placeholders = ",".join(["%s"] * len(to_clear))
        cur.execute(f"DELETE FROM shop_reorder_items WHERE id IN ({placeholders})", to_clear)














# Ctecí/mazaci endpointy nad audit_log vycleneny do api/audit_log.py
# (bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 5). log_audit()
# sama (zapis) zustava tady vyse - pouziva ji temer kazdy modul.

# --- Automaticke nacitani cen z logiman.cz (rozhodnuti 2026-07-23,
# CENA prepojena na e-shop 2026-08-08, HMOTNOST prepojena na Dogus
# 2026-08-08 - "z logiman uz nic nebudeme tahat") ---
# Puvodne (do 2026-08-08) se cena/1m i hmotnost/1m stahovaly NEZAVISLE
# z logiman.cz stranky profilu. Robert 2026-08-08 ("tyto ceny profilů
# sice už netahame z logiman nale z Dogus Kalip, ale tak jako tak,
# vycházejme z ceny na eshopu pro 3D scenu"): PRICE se PREBIRA z ceny
# odpovidajiciho e-shopoveho produktu (shop_products.price_czk_placeholder,
# "1 ks = 3000mm tyc" konvence - viz PROFILE_MAX_LENGTH_MM - proto /3 na
# Kc/1m). Duvod: shop_products cena uz smeruje na jiny zdroj (Dogus Kalip
# import + budouci kategorijni koeficient, viz
# sql/2026-08-08_dogus_pairing.sql/content_categories.dogus_price_coefficient)
# - drzet pro cfg_dily SAMOSTATNY nezavisly scrape logiman.cz by vedlo k
# rozjizdejicim se, vzajemne nekonzistentnim cislum pro TENTYZ fyzicky
# profil (potvrzeno 2026-08-08 - 22 z 23 radku melo nesedici pomer mezi
# nezavisle scrapovanou cfg_dily cenou a aktualni eshopovou cenou/3).
# HMOTNOST (weight_kg_approx) - Robert 2026-08-08: "hmotnost máš original
# v tabulkach skladových karet, z importu z Dogus" + "z logiman uz nic
# nebudeme tahat" - takze i hmotnost se ted BERE ze stejneho
# e-shopoveho produktu, konkretne z jeho "Mass" polozky v
# shop_products.product_specs_json (spec tabulka naimportovana ze
# skutecneho dodavatelskeho katalogu Dogus Kalip, viz
# scripts/2026-08-08_dogus_pairing_crawl.py) - zadny externi scrape uz
# se nepouziva vubec.
def _parse_dogus_mass_kg_per_m(specs_json):
    """Hmotnost/1m z Dogus spec tabulky (klic "Mass", format "X.XX Kg/m"
    resp. "X.XX kg/m"). Vraci None kdyz specs chybi/nejdou naparsovat -
    volajici pak pole proste neprepisuje (ponecha predchozi hodnotu)."""
    if not specs_json:
        return None
    try:
        specs = json.loads(specs_json)
    except (TypeError, ValueError):
        return None
    mass = specs.get("Mass")
    if not mass:
        return None
    m = re.search(r'([\d.]+)\s*[Kk]g/m', mass)
    return float(m.group(1)) if m else None


def refresh_price_for_row(cur, pid):
    """Provede jeden refresh + DB update pro dane katalogove ID (cfg_dily).
    Cena/1m i hmotnost/1m se BEROU z odpovidajiciho e-shopoveho produktu
    (shop_products pres cfg_dily_id) - viz komentar vyse. Zadny externi
    scrape logiman.cz. Vraci dict s vysledkem (pouziva ho jak rucni
    /refresh endpoint, tak nocni dávka)."""
    cur.execute(
        "SELECT price_czk_placeholder, product_specs_json FROM shop_products "
        "WHERE cfg_dily_id=%s AND active=1 AND is_archived=0 LIMIT 1",
        (pid,),
    )
    row = cur.fetchone()
    price = None
    weight = None
    if row:
        if row.get("price_czk_placeholder") is not None:
            price = round(float(row["price_czk_placeholder"]) / 3.0, 2)
        weight = _parse_dogus_mass_kg_per_m(row.get("product_specs_json"))

    if price is None and weight is None:
        return {"id": pid, "status": "error", "error": "Nenalezen odpovídající e-shopový produkt s cenou ani hmotností (Dogus)."}

    fields, params = [], []
    if price is not None:
        fields.append("price_czk_approx=%s"); params.append(price)
    if weight is not None:
        fields.append("weight_kg_approx=%s"); params.append(weight)
    params.append(pid)
    cur.execute(f"UPDATE cfg_dily SET {', '.join(fields)} WHERE id=%s", params)
    return {"id": pid, "status": "ok", "price_czk_per_m": price, "weight_kg_per_m": weight}


# --- Automaticke nacitani cen PRODUKTU z logiman.cz (bot2, 2026-07-28) ---
# Robert: "nactes a ulozis k nim automaticky i url aby se cena mohla napr
# 1x tydne obnovit?" (navazuje na import 3 produktu Uhelnikova spojka).
# Na rozdil od profilu (cfg_dily - ty uz od 2026-08-08 zadny scrape
# nemaji vubec, viz refresh_price_for_row vyse) jsou tohle kusove
# produkty (Kc/ks) - cena se najde spolehlivěji v
# gtag/GA4 "view_item" JS bloku na strance, kde je natvrdo parovana s
# kodem produktu ("id": "<kod>" ... "price": <cislo>), nezávisle na
# konkretnim CSS layoutu stranky.
def scrape_logiman_product_price(url, code):
    """Stahne aktualni cenu (Kc/ks, bez DPH) pro produkt s danym kodem ze
    stranky logiman.cz. Vraci cislo, nebo None kdyz se nenajde."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; KonfiguratorBot/1.0)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    # bot3 2026-08-09: 300 znaku bylo malo - dlouhy escapovany "category"
    # retezec (breadcrumb cesta v GA4 bloku) casto sam o sobe presahne
    # 300 znaku a "price" pak zustane mimo okno (9/47 kategorii pri
    # sestaveni tabulky Logiman vs. nase cena selhalo presne timhle
    # zpusobem, overeno primo na strance - vzdalenost byla 324 znaku).
    pattern = re.escape(f'"id": "{code}"') + r'.{1,700}?"price":\s*([\d.]+)'
    m = re.search(pattern, html, re.S)
    if not m:
        return None
    return float(m.group(1))


def refresh_price_for_product(cur, product_id, sku, url):
    """Provede jeden scrape + DB update pro dany produkt (shop_products.id).
    Vraci dict s vysledkem - stejny tvar jako refresh_price_for_row, aby ho
    slo pouzit stejne jak z rucniho endpointu, tak z nocni/tydenni davky."""
    try:
        price = scrape_logiman_product_price(url, sku)
    except Exception as e:
        return {"id": product_id, "status": "error", "error": str(e)}
    if price is None:
        return {"id": product_id, "status": "error", "error": "Na stránce se nepodařilo najít cenu podle kódu produktu."}
    cur.execute(
        "UPDATE shop_products SET price_czk_placeholder=%s, price_last_refreshed_at=NOW() WHERE id=%s",
        (price, product_id),
    )
    return {"id": product_id, "status": "ok", "price_czk": price}












# Definice "nastroje" pro Claude - vynuti strukturovanou odpoved misto volneho textu.
# Zmena oproti puvodni verzi (build_structure): 3Dbot je ted CHAT, ne jednorazovy
# generator. Kazda odpoved MUSI obsahovat "reply" (konverzacni text - odpoved na
# otazku, komentar, vysvetleni), a VOLITELNE "steps" (kompletni novy/upraveny
# seznam dilu pro scenu) - prazdne pole steps znamena "jen povidam si, scenu
# nemenim" (napr. kdyz se uzivatel jen zepta na neco, nebo pozadavek nejde
# splnit a bot to vysvetli v reply).
AI_BUILD_TOOL = {
    "name": "chat_and_build",
    "description": (
        "Odpovi uzivateli v chatu (reply) a volitelne navrhne kompletni 3D sestavu "
        "z katalogu (steps). Pokud uzivatel jen neco vysvetluje/pta se a sestava se "
        "nema menit, necha steps jako prazdne pole - v tom pripade se scena v appce "
        "vubec nedotkne, jen se zobrazi tvoje odpoved."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reply": {
                "type": "string",
                "description": "Prirozena, konverzacni odpoved v cestine - jako bys s uzivatelem normalne mluvil. Vysvetli, co delas nebo proc, komentuj aktualni stav sceny, odpovez na otazku.",
            },
            "steps": {
                "type": "array",
                "description": "Kompletni seznam dilu pro CELOU scenu (ne jen zmena/delta) - pokud neni prazdny, appka scenu prekresli podle tohoto seznamu. Nech prazdne [], pokud sestava zustava beze zmeny.",
                "items": {
                    "type": "object",
                    "properties": {
                        "step": {"type": "integer", "description": "Poradove cislo kroku, zacina 1."},
                        "part_id": {"type": "string", "description": "ID dilu z katalogu (pole 'id')."},
                        "attach_to": {
                            "type": ["integer", "null"],
                            "description": "Cislo drivejsiho kroku, ke kterému se tento dil pripoji na jeho volny konektor. null = polozit na zaklad (prvni dil, nebo samostatny dil bez navaznosti).",
                        },
                        "rotation_deg": {
                            "type": "integer",
                            "description": "ABSOLUTNI natoceni dilu kolem svisle (Y) osy v prostoru - 0, 90, 180 nebo 270. NENI relativni k predchozimu dilu! Viz podrobne vysvetleni a priklad v system promptu.",
                        },
                        "conn_idx": {
                            "type": ["integer", "null"],
                            "description": "Volitelne: vynuti konkretni konektor rodicovskeho kroku (0 nebo 1 = jeho dva konce). Bez tohoto se automaticky pouzije PRVNI konec rodice, coz je spravne pro retezeni, ale NE pro uzavreni smycky (viz priklad 'uzavreny obdelnik' v system promptu, kde prvni navazujici dil MUSI pouzit conn_idx:1).",
                        },
                        "orient": {
                            "type": ["string", "null"],
                            "enum": ["vertical", None],
                            "description": "Volitelne, vychozi null = dil lezi vodorovne (plosna/pudorysna konstrukce). 'vertical' = dil STOJI svisle (sloupek) - pouzij pro cokoli, co ma vyjit z roviny zakladu nahoru (nohy stolu, sloupky regalu, hrany kvadru/krabice). Viz podrobne vysvetleni a priklad v system promptu.",
                        },
                        "length_mm": {
                            "type": ["number", "null"],
                            "description": f"Volitelne, vychozi null = katalogova (nezmenena) delka dilu. Zadej cislo v mm, pokud ma byt dil rezany na konkretni miru (napr. uzivatel rekl '800mm dlouhy sloupek'). Musi byt kladne a nejvyse {PROFILE_MAX_LENGTH_MM} mm - delsi konstrukce rozdel na vice segmentu (viz pravidlo 1 nize). Kdyz je dil pripojeny (attach_to), zkraceni/prodlouzeni se deje na jeho VOLNEM konci - konec, kterym je pripojeny k rodici, zustava na miste.",
                        },
                        "position_mm": {
                            "type": ["array", "null"],
                            "items": {"type": "number"},
                            "description": f"Volitelne, POUZIVAT JEN kdyz je 'attach_to' null (dil NENI pripojeny k zadnemu rodici) - absolutni pozice [x, y, z] v mm, kam se ma tenhle VOLNY dil polozit V PROSTORU, bez jakehokoli spoje/navazani na jiny dil. Bez tohoto pole se volny dil polozi na (0,0,0), jako doteď. Y je smer NAHORU (vyska nad zakladem). Kazda souradnice smi byt nejvyse +-{AI_POSITION_BOUND_MM} mm. POZOR: u dilu, ktery MA 'attach_to' (je pripojeny k rodici), toto pole NEMA zadny efekt - jeho pozici vzdy plne urcuje spoj s rodicem, nikdy tohle pole.",
                        },
                    },
                    "required": ["step", "part_id", "attach_to", "rotation_deg"],
                },
            },
            "shape_calls": {
                "type": "array",
                "description": (
                    "Pouzij MISTO 'steps', kdyz uzivatel chce jeden z overenych "
                    "predpripravenych tvaru z Pruvodce (presnejsi a bezpecnejsi nez "
                    "rucni skladani 'steps' - pouziva stejne funkce jako tlacitka v "
                    "appce, u kterych uz je uzavirani rohu/smycek overene a opravene "
                    "vypoctem, ne jen odhadem). SMI obsahovat NEJVYSE JEDNU polozku "
                    "(kazde volani zacina novou scenu, nelze kombinovat vice tvaru "
                    "ani kombinovat s 'steps' v jedne odpovedi). Necha prazdne [], "
                    "pokud pouzivas misto toho 'steps'."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "shape": {
                            "type": "string",
                            "enum": ["segment", "L", "L_reversed", "L_length", "L_length_reversed", "T", "spatial_L", "spatial_L_reversed", "square", "square_reversed", "kvadr"],
                            "description": "Ktery predpripraveny tvar postavit - viz vysvetleni jednotlivych tvaru v system promptu.",
                        },
                        "part_id": {"type": "string", "description": "ID dilu z katalogu, ze ktereho se cely tvar postavi (stejny prurez pro vsechny casti)."},
                    },
                    "required": ["shape", "part_id"],
                },
            },
        },
        "required": ["reply", "steps", "shape_calls"],
    },
}


@app.post("/api/ai/generate")
@login_required
def ai_generate():
    if not ANTHROPIC_API_KEY:
        return jsonify({
            "error": "AI vrstva zatim neni nakonfigurovana - na serveru chybi ANTHROPIC_API_KEY.",
        }), 501

    body = request.get_json(silent=True) or {}
    # "messages" je cela historie konverzace (chat), ne jen posledni prompt -
    # 3Dbot je ted skutecny chat, ne jednorazovy generator. Kazdy prvek je
    # {role: "user"|"assistant", text: "..."}. Posledni prvek musi byt "user".
    messages_in = body.get("messages") or []
    image = body.get("image") or None  # {media_type, data(base64)} - patri k POSLEDNI user zprave
    dims = body.get("dims") or None  # {width_mm, height_mm, depth_mm, type} - hint k posledni zprave
    scene_state = body.get("scene_state") or []  # strukturovany popis toho, co uz je te ted ve scene

    has_dims = dims and any(dims.get(k) for k in ("width_mm", "height_mm", "depth_mm", "type"))
    if not messages_in:
        return jsonify({"error": "Chybi zprava - napis neco do chatu."}), 400
    last = messages_in[-1]
    if last.get("role") != "user" or (not (last.get("text") or "").strip() and not image and not has_dims):
        return jsonify({"error": "Posledni zprava musi byt od tebe (user) a musi neco obsahovat - text, obrazek nebo rozmery."}), 400

    parts = fetch_katalog_parts()
    cross_key_by_id = {p["id"]: cross_key(p["cross_section_mm"]) for p in parts}

    # DULEZITE: FBX export vytvoril pro nektere prurezy VICE samostatnych
    # katalogovych ID se stejnym prurezem (napr. 30x30 ma az 3 ruzna ID -
    # Object_7/8/9 - jde jen o duplicitni mesh instance z exportu, fyzicky je
    # to porad ten samy typ profilu). Kdyz AI vidi 3 ruzna ID, mysli si, ze ma
    # k dispozici jen 3 KUSY toho prurezu - napr. pri stavbe ctvercoveho ramu
    # ze 4 stran 30x30 mu "dojdou" ID po 3. stranie a ctvrtou proste vynecha
    # (presne tenhle bug nahlasil Robert). Reseni: AI dostane jen JEDNO
    # reprezentativni ID na kazdy prurez (stejna logika jako pruvodce ve
    # frontendu, viz uniqueProfilesForWizard) a vyslovnou instrukci, ze ho
    # smi pouzit vicekrat. Hardware (black/zinc) NEDEDUPLIKUJEME - ruzne
    # konzoly/krytky mohou mit podobne rozmery, ale byt jine kusy.
    seen_alu_cross = set()
    catalog_for_ai = []
    for p in parts:
        pk = cross_key_by_id[p["id"]]
        if p["layer"] == "alu" and pk:
            if pk in seen_alu_cross:
                continue
            seen_alu_cross.add(pk)
        catalog_for_ai.append({
            "id": p["id"],
            "name": p["name"],
            "layer": p["layer"],
            "material": p["material_label"],
            "dims_mm": p["dims_mm"],
            "prurez": pk,
        })

    try:
        import anthropic
    except ImportError:
        return jsonify({"error": "Na serveru chybi balicek 'anthropic' (pip install anthropic)."}), 500

    join_pairs_readable = ", ".join(
        sorted(" = ".join(sorted(pair)) if len(pair) > 1 else next(iter(pair)) + " (jen samo se sebou)"
               for pair in PROFILE_JOIN_PAIRS if len(pair) > 1)
    )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    scene_state_txt = (
        json.dumps(scene_state, ensure_ascii=False) if scene_state
        else "scena je prazdna, zatim v ni nic neni"
    )
    # Robert 2026-07-24: "pridavej mu tam automaticky geometricka pravidla
    # vse co uz znas" - nacteno ze SDILENEHO zdroje pravdy (viz
    # load_profile_rules_doc() vyse), ne rucne prepsano/zkraceno tady.
    profile_rules_doc = load_profile_rules_doc()

    system_prompt = (
        "Jsi 3Dbot - konstrukcni asistent pro 3D konfigurator hlinikovych profilu "
        "a dilu (konzoly, krytky), zabudovany primo v appce. Bavis se s uzivatelem "
        "v BEZICI KONVERZACI (chat) - ne jednorazove, muze se ptat, doladovat, "
        "reagovat na to, co uz je postavene, a ty mu odpovidas prirozene v 'reply', "
        "presne jako v normalnim chatu. NEZNAMENA to ale, ze musis pri kazde zprave "
        "menit scenu - pokud se uzivatel jen na neco pta, necha komentar, nebo jeho "
        "pozadavek nejde splnit, vysvetli to v 'reply' a 'steps' nech prazdne [].\n\n"
        "AKTUALNI STAV SCENY (co uz je te ted postavene v appce, JSON): "
        + scene_state_txt + "\n\n"
        "Pokud uzivatel chce neco pridat/zmenit/postavit, vrat v 'steps' KOMPLETNI "
        "novy seznam dilu pro CELOU scenu (ne jen tu zmenu) - appka scenu vzdy "
        "prekresli od nuly podle tveho seznamu, takze pokud mas zachovat existujici "
        "dily, musis je do steps zase zahrnout. Vyber vhodne dily z dodaneho "
        "katalogu (pouzivej presne 'id' z katalogu) a urci, jak na sebe navazuji "
        "pomoci 'attach_to' (odkaz na cislo drivejsiho kroku v TOMTO seznamu, ne "
        "cisla z minule odpovedi).\n\n"
        "GEOMETRIE - CTI POZORNE, je to nejcastejsi zdroj chyb:\n"
        "Kazdy dil je rovna tyc se 2 koncovymi konektory (0 a 1). 'rotation_deg' "
        "je ABSOLUTNI natoceni v prostoru (ne relativni k predchozimu dilu!): "
        "0 stupnu = tyc smeruje jednim smerem, 90 = smeruje kolmo na to, 180 = "
        "presny opak 0, 270 = kolmo na opacnou stranu nez 90. Kdyz pripojujes dil "
        "k rodici bez 'conn_idx', appka automaticky vybere PRVNI (0.) konec "
        "rodice - to je OK pro retezeni za sebou, ale NESTACI to pro uzavreni "
        "smycky (napr. ctvercovy ram), protoze prvni dil v retezu (ten s "
        "attach_to:null) ma OBA konce volne a bez 'conn_idx' se pouzije jeho "
        "ZACATEK, ne KONEC - a rez by se tak nikdy neuzavrel.\n"
        "PRIKLAD - uzavreny obdelnikovy ram ze 4 kusu profilu 'P' (funkcni, "
        "over si na nem spravny vzor natoceni a conn_idx):\n"
        "steps = [\n"
        '  {"step":1,"part_id":"P","attach_to":null,"rotation_deg":0},\n'
        '  {"step":2,"part_id":"P","attach_to":1,"rotation_deg":90,"conn_idx":1},\n'
        '  {"step":3,"part_id":"P","attach_to":2,"rotation_deg":180},\n'
        '  {"step":4,"part_id":"P","attach_to":3,"rotation_deg":270}\n'
        "]\n"
        "Vsimni si: uhly rostou 0,90,180,270 (KAZDY krok jina hodnota, nikdy "
        "stejna hodnota dvakrat po sobe), a jen krok 2 (prvni navazujici na "
        "korenovy krok 1) ma vyslovne 'conn_idx':1 - dalsi kroky uz auto-vyber "
        "funguje spravne, protoze kazdy predchozi pripojeny dil ma uz jen jeden "
        "volny konec.\n"
        "SVISLE (prostorove) KONSTRUKCE - pole 'orient':'vertical': bez "
        "'orient' umis stavet jen PLOSNE (vodorovne, pudorysne) konstrukce - "
        "retezy, ramy, T a L tvary. Kdyz dil potrebuje VYJIT Z ROVINY ZAKLADU "
        "NAHORU (sloupek stolu/regalu, hrana kvadru/krabice), nastav mu "
        "'orient':'vertical' - appka ho pak postavi na vysku misto naplocho. "
        "U svisleho dilu se navic MENI, kterym koncem se pripojuje k rodici: "
        "misto prvniho (0.) konce se pouzije DRUHY (1.) konec dilu jako bod "
        "pripojeni na konektor rodice - tim sloupek 'stoji' na miste, kam se "
        "pripojil, misto aby z nej trcel opacnym smerem.\n"
        "PRIKLAD - prostorove L (dva vodorovne dily + jeden svisly sloupek "
        "z jejich spolecneho rohu, funkcni vzor):\n"
        "steps = [\n"
        '  {"step":1,"part_id":"P","attach_to":null,"rotation_deg":0},\n'
        '  {"step":2,"part_id":"P","attach_to":1,"rotation_deg":90,"conn_idx":0},\n'
        '  {"step":3,"part_id":"P","attach_to":1,"rotation_deg":0,"conn_idx":0,"orient":"vertical"}\n'
        "]\n"
        "Krok 3 stoji svisle presne v rohu, kde se stykaji kroky 1 a 2 (oba "
        "pripojeny na konektor 0 rodicovskeho kroku 1). Stejnym principem "
        "(4 vodorovne dily jako 'square' + 4 svisle sloupky v jejich rozich) "
        "jde postavit i kvadr/krabici - pokud si uzivatel rekne o slozitejsi "
        "prostorovou konstrukci (regal s vice patry, slozita kostra), muzes to "
        "zkusit rozlozit na vice takovych kroku, nebo (pokud si nejsi jisty "
        "vysledkem) v 'reply' navrhni i Pruvodce (panel vpravo nahore, tvar "
        "'Kvadr (krabice)') jako overenou alternativu.\n\n"
        "VLASTNI DELKA - pole 'length_mm': kdyz uzivatel chce dil rezany na "
        "konkretni miru (napr. '800mm sloupek', 'zkrat prvni profil na 500mm'), "
        "pridej mu do kroku 'length_mm' s pozadovanym cislem v mm. Bez tohoto "
        "pole dil zustava v katalogove (nezmenene) delce. U pripojeneho dilu "
        "(ma 'attach_to') se zmena delky projevi na jeho VOLNEM konci, konec "
        "pripojeny k rodici zustava presne na miste - takze zmena delky nikdy "
        "nerozbije uz existujici spoj.\n\n"
        "VOLNE POZICOVANI V PROSTORU BEZ SPOJE - pole 'position_mm': normalne "
        "kazdy dil bez 'attach_to' skonci na (0,0,0). Kdyz uzivatel chce dil "
        "polozit VOLNE, NIKAM NEPRIPOJENY, na konkretni misto v prostoru "
        "(napr. 'poloz dalsi kus 1 metr vedle', 'chci samostatnou nohu v "
        "rohu mistnosti na danych souradnicich'), nastav mu 'attach_to':null "
        f"a 'position_mm':[x,y,z] (v mm, kazda souradnice max +-{AI_POSITION_BOUND_MM}). Y je "
        "nahoru. Tohle pole ma smysl JEN u volnych dilu (attach_to:null) - u "
        "pripojeneho dilu se ignoruje, protoze jeho pozici uz plne urcuje "
        "spoj s rodicem. Volne umisteny dil MUZE byt pouzit jako 'attach_to' "
        "cil pro dalsi kroky (napr. polozis samostatny sloupek na presne "
        "misto a pak na nej normalne navazes dalsimi kroky pres attach_to) - "
        "spojovaci pravidla (kompatibilita prurezu, kolme spoje) pak plati "
        "stejne jako u kterehokoli jineho rodicovskeho kroku.\n\n"
        "PREDPRIPRAVENE TVARY - pole 'shape_calls' (POUZIJ MISTO 'steps', kdyz "
        "se hodi): appka ma sadu jiz overenych/opravenych konstrukci (stejne "
        "funkce jako tlacitka v Pruvodci), ktere je SPOLEHLIVEJSI zavolat "
        "primo, nez se je snazit znovu poskladat rucne pres 'steps' - hlavne "
        "u uzavrenych smycek (ctvercovy ram, kvadr) je rucni skladani nachylne "
        "na chyby v uzavirani rohu, ktere uz appka jednou resila. Dostupne "
        "tvary: 'segment' (jeden samostatny dil, 0 spoju - pro nejjednodussi "
        "pozadavky jako 'jeden kus profilu'), 'L' (dva dily v pravem uhlu), "
        "'L_reversed' (totez, obraceny "
        "spoj - jiny dil je pruchozi/pripojovany), 'L_length' a "
        "'L_length_reversed' (varianty L spoje reseneho zmenou delek misto "
        "pozice, viz pravidlo 8 nize), 'T' (T-spoj), 'spatial_L' (prostorove "
        "L se svislym sloupkem, presne priklad vyse), 'spatial_L_reversed' "
        "(totez, obraceny spoj - jiny vodorovny dil je pruchozi, sloupek roste "
        "ze stejneho rohu), 'square' (uzavreny "
        "ctvercovy/obdelnikovy ram ze 4 dilu), 'square_reversed' (totez, "
        "prohozeny smer - ktera dvojice stran je pruchozi/pripojovana), "
        "'kvadr' (uzavrena krabice - spodni i horni ram + 4 svisle sloupky). "
        "Kazda polozka v 'shape_calls' potrebuje jen 'shape' a 'part_id' - "
        "appka uz sama vi, kolik dilu a jak presne je poskladat. POZOR: smi "
        "byt v odpovedi nejvyse JEDNA polozka a nelze ji kombinovat se "
        "'steps' (kazde volani zacina uplne novou scenu) - pokud uzivatel "
        "chce vic ruznych tvaru najednou vedle sebe, rekni mu v 'reply', ze "
        "tohle zatim jednim krokem neumis (kazdy 'shape_calls' i kazdy klik "
        "na tvar v Pruvodci prekresli CELOU scenu od nuly, nepridava vedle "
        "existujiciho) - at si je pripadne postavi/porovna jeden po druhem.\n\n"
        "ZAVAZNA PRAVIDLA (potvrzena zakaznikem, server je navic tvrde vynucuje):\n"
        f"1. Delka profilu je libovolna, max {PROFILE_MAX_LENGTH_MM} mm - pokud "
        "konstrukce potrebuje delsi kus, rozdel ho na vice segmentu.\n"
        "2. Zatim se resi jen KOLME (90 stupnu) spoje - zadne 45stupnove ani "
        "libovolne uhly (to je az pro pristi fazi s dilem 'kloub').\n"
        "3. Dva profily lze spojit konec-na-konec JEN pokud jejich prurezy "
        "(pole 'prurez' v katalogu, napr. '30x30') spolu ladi podle tohoto "
        "seznamu: kazdy profil jde spojit sam se sebou, a navic tyto dvojice: "
        f"{join_pairs_readable}. Zadne jine kombinace prurezu spojovat nejdou "
        "(napr. 20x20 se 45x45 NE).\n"
        "4. Hardware dily (vrstva black/zinc - konzoly, krytky) zatim nemaji "
        "definovana presna pravidla pripojeni - pouzivej je jen pokud to popis "
        "vyslovene vyzaduje, a jinak stav pouze z alu profilu.\n"
        "5. DULEZITE: kazde 'id' u alu profilu v katalogu je TYP profilu (jeden "
        "konkretni prurez), NE jeden fyzicky kus na sklade - stejne 'id' klidne "
        "pouzij ve VICE krocich, kolikrat potrebujes (napr. vsechny 4 strany "
        "ctvercoveho ramu mohou mit stejne part_id). Nikdy si nemysli, ze ti "
        "'dojde' material jen proto, ze pro dany prurez existuje v katalogu "
        "jen jedno id.\n"
        "6. CO JE FYZICKY 'SPOJ' (pro pripad, ze se uzivatel zepta, jak spoj "
        "funguje, nebo pocita cenu montaze): celo jednoho profilu (kde je "
        "vyrezany zavit) doleha celou svou plochou na stenu druheho profilu "
        "(kde je vyvrtany otvor). Spojovaci sroub prochazi otvorem a "
        "zasroubuje se do zavitu, dotahuje se imbusem pres otvor; hlava "
        "sroubu musi byt PREDEM nasunuta v T-drazce profilu, do ktereho se "
        "sroubuje. Tahle definice plati stejne pro spoj na konci profilu "
        "(tvar L) i pro spoj uprostred/kdekoli podel delky profilu (tvar T) "
        "- v obou pripadech je to porad jen JEDEN spoj (jeden sroub/zavit/"
        "otvor), i kdyz se na nem fyzicky podili konce/boky obou dilu. Appka "
        "pocita 'cenu spoju' v zivem prehledu presne timhle zpusobem (1 spoj "
        "= 1 uspesne pripojeni dilu k rodici, ne soucet vsech zucastnenych "
        "konektoru).\n"
        "7. POLARITA SPOJE: zavit v bode 6 muze byt v CELE KTEREHOKOLI z "
        "obou profilu (a otvor pak ve stene toho druheho) - jde to udelat "
        "oběma smery. Cenove je to uplne jedno (porad 1 spoj, stejna cena), "
        "ale konstrukcne to NENI libovolne - volba zavisi na tom, (a) aby "
        "sla sestava realne smontovat (pristup imbusem, poradi skladani), a "
        "(b) jestli ma u nektereho profilu zustat volna/otevrena T-drazka "
        "pro neco dalsiho. Appka/3Dbot tohle zatim nemusi resit "
        "konstrukcne (nema vliv na cenu ani pocet spoju v aktualnim "
        "modelu), ale kdyby se uzivatel zeptal, jak spoj vyrobne/montazne "
        "funguje, vysvetli mu tuhle obousmernost.\n"
        "8. DVA ZPUSOBY, JAK 'OBRATIT' SPOJ (kdyz uzivatel chce zmenit, "
        "ktery profil je 'pruchozi' a ktery 'pripojovany' v rohu/T spoji): "
        "existuji 2 ruzne geometricke reseni a NEJSOU zamenitelna:\n"
        "   a) Beze zmeny delky - zadny z profilu nezmeni svou delku, ale "
        "zmeni se POZICE spoje podel podelne osy jednoho z nich (kde presne "
        "podel sve delky se pripoji, podle aktualni potreby ve scene). Tohle "
        "je slozitejsi pripad a zatim se resi/upresnuje.\n"
        "   b) Zmenou delek obou profilu - zadny profil nezmeni svou pozici "
        "vuci vlastni podelne ose (zacatek zustava, kde byl), ale ZMENI SE "
        "DELKY: jeden profil se ZKRATI o rozmer profilu v reze (napr. u "
        "30x30 o 30 mm) a druhy se o STEJNOU delku PRODLOUZI - tim se "
        "dosahne pozadovane skladby profilu v prostoru, aniz by se cokoli "
        "posouvalo mimo svou osu.\n"
        "   Pokud uzivatel chce obraceny spoj a nespecifikuje ktery zpusob, "
        "zepta se ho v 'reply', kterou variantu chce, misto abys hadal.\n\n"
        f"Vrat vysledek VYHRADNE volanim nastroje chat_and_build. "
        f"Maximalne {AI_MAX_STEPS} kroku ve steps. Katalog dostupnych dilu (JSON): "
        + json.dumps(catalog_for_ai, ensure_ascii=False)
        + (
            "\n\nDOPLNKOVA DOKUMENTACE (VLASTNOSTI_PROFILU.md - kompletni interni "
            "zdroj pravdy o vsech potvrzenych vyrobnich/geometrickych pravidlech, "
            "prubezne aktualizovany pri dalsi praci na appce; ZAVAZNA PRAVIDLA vyse "
            "jsou z nej vytazeny/zjednoduseny souhrn pro caste pripady - tohle je "
            "uplny/podrobnejsi zdroj, pouzij ho pro specifictejsi nebo neobvykle "
            "dotazy, napr. presnou kompatibilitu prurezu podle drazky, detaily "
            "fyzickeho spoje/polarity zavitu, nebo historii ruznych zpusobu "
            "'obraceni' spoje):\n\n" + profile_rules_doc
            if profile_rules_doc else ""
        )
    )

    # Cela historie konverzace jde do Anthropic API jako messages - pro Claude
    # je to bezny vicetahovy chat. Obrazek/rozmerovy hint patri jen k POSLEDNI
    # (aktualni) user zprave, stejne jako predtim k jedinemu promptu.
    anthropic_messages = []
    for i, m in enumerate(messages_in):
        role = "assistant" if m.get("role") == "assistant" else "user"
        text = (m.get("text") or "").strip()
        is_last = (i == len(messages_in) - 1)
        if is_last and role == "user":
            text_parts = [text or "(bez textu)"]
            if has_dims:
                hint_bits = []
                if dims.get("width_mm"): hint_bits.append(f"šířka {dims['width_mm']} mm")
                if dims.get("height_mm"): hint_bits.append(f"výška {dims['height_mm']} mm")
                if dims.get("depth_mm"): hint_bits.append(f"hloubka {dims['depth_mm']} mm")
                if dims.get("type"): hint_bits.append(f"typ konstrukce: {dims['type']}")
                text_parts.append("Požadované rozměry/typ (dodrž je co nejpřesněji): " + ", ".join(hint_bits))
            content = []
            if image and image.get("data"):
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image.get("media_type", "image/jpeg"),
                        "data": image["data"],
                    },
                })
            content.append({"type": "text", "text": "\n\n".join(text_parts)})
            anthropic_messages.append({"role": "user", "content": content})
        else:
            anthropic_messages.append({"role": role, "content": text or "(bez textu)"})

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=[AI_BUILD_TOOL],
            tool_choice={"type": "tool", "name": "chat_and_build"},
            messages=anthropic_messages,
        )
    except Exception as e:
        return jsonify({"error": f"Volani AI selhalo: {e}"}), 502

    tool_use = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    if not tool_use:
        return jsonify({"error": "AI nevratila ocekavana strukturovana data."}), 502

    plan = tool_use.input or {}
    steps = plan.get("steps") or []

    # Server-side validace: jen skutecne existujici dily z katalogu, jen odkazy
    # na drivejsi (nebo zadne) kroky, a NAVIC tvrde vynucena kompatibilita
    # spoju podle PROFILE_JOIN_PAIRS - i kdyby AI navrhla neplatnou kombinaci
    # prurezu, attach_to se tu zrusi a dil se v appce jen polozi samostatne
    # (misto aby se pripojil na misto, kam fyzicky nepatri).
    valid_ids = {p["id"] for p in parts}
    layer_by_id = {p["id"]: p["layer"] for p in parts}
    seen_steps = set()
    step_part_by_no = {}
    clean_steps = []
    rejected_joins = []
    for s in steps[:AI_MAX_STEPS]:
        pid = s.get("part_id")
        step_no = s.get("step")
        attach_to = s.get("attach_to")
        if pid not in valid_ids or not isinstance(step_no, int):
            continue
        if attach_to is not None and attach_to not in seen_steps:
            attach_to = None
        if attach_to is not None:
            parent_pid = step_part_by_no.get(attach_to)
            parent_layer = layer_by_id.get(parent_pid)
            child_layer = layer_by_id.get(pid)
            if parent_layer == "alu" and child_layer == "alu":
                pk, ck = cross_key_by_id.get(parent_pid), cross_key_by_id.get(pid)
                if pk and ck and frozenset({pk, ck}) not in PROFILE_JOIN_PAIRS:
                    rejected_joins.append(f"{pk} + {ck}")
                    attach_to = None
        rot = s.get("rotation_deg", 0)
        rot = rot if rot in (0, 90, 180, 270) else 0
        clean_step = {"step": step_no, "part_id": pid, "attach_to": attach_to, "rotation_deg": rot}
        # DULEZITE: conn_idx se sem musi propsat, jinak by ho AI mohla vratit,
        # ale frontend by ho nikdy nedostal (byla by to stejna nevyresena chyba
        # jako u ctverce, jen jinde) - bez conn_idx se smycky/ramy nikdy neuzavrou.
        conn_idx = s.get("conn_idx")
        if attach_to is not None and conn_idx in (0, 1):
            clean_step["conn_idx"] = conn_idx
        # Stejny duvod jako u conn_idx vyse - orient MUSI dojit na frontend,
        # jinak by AI mohla navrhnout svisly dil, ale runAIPlan() by o tom
        # nevedela a postavila by ho naplocho jako vsechno ostatni.
        orient = s.get("orient")
        if orient == "vertical":
            clean_step["orient"] = "vertical"
        # Vlastni delka (viz schema/system prompt "VLASTNI DELKA") - server
        # jen overi rozsah (kladne cislo, nejvyse PROFILE_MAX_LENGTH_MM),
        # samotnou aplikaci resi az frontend (runAIPlan/applyLengthScale).
        length_mm = s.get("length_mm")
        if isinstance(length_mm, (int, float)) and 0 < length_mm <= PROFILE_MAX_LENGTH_MM:
            clean_step["length_mm"] = length_mm
        # Volne pozicovani bez spoje (viz schema/system prompt "VOLNE
        # POZICOVANI V PROSTORU BEZ SPOJE") - dava smysl JEN u dilu bez
        # rodice (attach_to musi byt v tomhle bode uz finalne None, po vsech
        # validacich vyse), jinak by prepisovalo pozici urcenou spojem.
        # Server overi tvar (presne 3 cisla) a rozsah, at AI neposle dil
        # nesmyslne daleko od zbytku sestavy.
        position_mm = s.get("position_mm")
        if (
            attach_to is None
            and isinstance(position_mm, list)
            and len(position_mm) == 3
            and all(isinstance(v, (int, float)) for v in position_mm)
            and all(-AI_POSITION_BOUND_MM <= v <= AI_POSITION_BOUND_MM for v in position_mm)
        ):
            clean_step["position_mm"] = [float(v) for v in position_mm]
        clean_steps.append(clean_step)
        seen_steps.add(step_no)
        step_part_by_no[step_no] = pid

    # Predpripravene tvary (viz schema/system prompt "PREDPRIPRAVENE TVARY") -
    # server jen overi, ze jde o znamy tvar a existujici dil z katalogu;
    # samotnou konstrukci resi frontend (buildNamedShape). Vynucen limit
    # NEJVYSE JEDNA polozka (viz duvod v popisu schematu vyse - kazde volani
    # zacina novou scenu, vic polozek by se jen navzajem prepisovalo).
    KNOWN_SHAPES = {"segment", "L", "L_reversed", "L_length", "L_length_reversed", "T", "spatial_L", "spatial_L_reversed", "square", "square_reversed", "kvadr"}
    clean_shape_calls = []
    for call in (plan.get("shape_calls") or [])[:1]:
        shape = call.get("shape")
        pid = call.get("part_id")
        if shape in KNOWN_SHAPES and pid in valid_ids:
            clean_shape_calls.append({"shape": shape, "part_id": pid})

    reply = plan.get("reply", "")
    if rejected_joins:
        reply += f" (pozn.: {len(rejected_joins)} nekompatibilnich spoju bylo automaticky rozpojeno: {', '.join(rejected_joins)})"

    return jsonify({"reply": reply, "steps": clean_steps, "shape_calls": clean_shape_calls})


def run_price_refresh_cli():
    """Nocni davkove nacteni cen - spoustí systemd timer konfigurator-
    refresh-prices.timer (1x denne v noci, Europe/Prague), NE pres HTTP/
    Flask, aby to nezavisel na behu gunicornu ani na prihlaseni admina.
    Pouziti: python3 app.py refresh-prices"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Robert 2026-08-08: "z logiman uz nic nebudeme tahat" - cena i
            # hmotnost se ted berou z parovaneho e-shopoveho produktu
            # (viz refresh_price_for_row), zadna zavislost na
            # price_source_url - VSECHNY radky, ne jen ty s URL.
            cur.execute("SELECT id FROM cfg_dily")
            rows = cur.fetchall()
            print(f"[refresh-prices] {len(rows)} profilu k refreshi")
            for row in rows:
                result = refresh_price_for_row(cur, row["id"])
                print(f"[refresh-prices] {result}")
        conn.commit()
    finally:
        conn.close()


def run_product_price_refresh_cli():
    """Tydenni davkove nacteni cen PRODUKTU - spousti systemd timer
    konfigurator-refresh-product-prices.timer (bot2, 2026-07-28, Robert:
    "nactes a ulozis k nim automaticky i url aby se cena mohla napr 1x
    tydne obnovit?"). Samostatny (tydenni, ne denni) timer od profilove
    cen - produkty se nemeni tak casto jako hlinikove profily.
    Pouziti: python3 app.py refresh-product-prices"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sku, price_source_url FROM shop_products WHERE price_source_url IS NOT NULL AND price_source_url != ''")
            rows = cur.fetchall()
            print(f"[refresh-product-prices] {len(rows)} produktu ma nastavenou zdrojovou URL")
            for row in rows:
                result = refresh_price_for_product(cur, row["id"], row["sku"], row["price_source_url"])
                print(f"[refresh-product-prices] {result}")
        conn.commit()
    finally:
        conn.close()


# Slozka s FBX modely produktu (bot2, 2026-07-28) - Robert: "nekterym
# produktum budeme pridavat fbx model k uploadu (obdobne jako pro profily),
# polozka(produkt) ktery bude mit fbx model, se nasledne pusti do 3D sceny
# do katalogu, ten tam musime zaroven s tim zacit rozvetvovat do kategorii
# at je v tom prehled". Mirror FBX_UPLOAD_DIR (cfg_dily/profily), jen pro
# shop_products - soubor <id>.fbx, GLB vystup product_<id>.glb (odlisny
# jmenny prostor od cfg_dily.id ve stejne slozce KATALOG_GLB_DIR).
# Zustava v jadru (bot15, revize mergu skupin 11-15) - pouziva ji i
# dimension_match_fbx.py, ne jen shop_api.py.
PRODUCT_FBX_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "product_fbx")
os.makedirs(PRODUCT_FBX_UPLOAD_DIR, exist_ok=True)


def _usage_images_for_products(cur, product_ids, limit=18):
    # bot5 2026-08-10 (Robert: "navrhni kam to na eshop umistime...
    # jsou to ilustracni nahledy pouziti nasich prvku v praxi") -
    # ilustracni obrazky (montaz/spoj v praxi, z Dogus PDF katalogu,
    # viz product_usage_images) pro danou sadu produktu. Pouzito jak
    # PRIMO (detail prislusenstvi - jeho vlastni obrazky), tak
    # ODVOZENE (profil - obrazky vsech jeho kompatibilnich
    # prislusenstvi, viz _compatible_accessories). Jeden fyzicky
    # obrazek muze byt navazany na vice produktu - vraci se jen JEDNOU
    # (dedup podle filename), s seznamem vsech nazvu produktu, ke
    # kterym patri, pro popisek.
    product_ids = [p for p in (product_ids or []) if p]
    if not product_ids:
        return []
    placeholders = ",".join(["%s"] * len(product_ids))
    cur.execute(f"""
        SELECT ui.filename, ui.source_page, p.name AS product_name
        FROM product_usage_images ui
        JOIN shop_products p ON p.id = ui.product_id
        WHERE ui.product_id IN ({placeholders})
        ORDER BY ui.source_page, ui.id
    """, product_ids)
    by_filename = {}
    order = []
    for r in cur.fetchall():
        if r["filename"] not in by_filename:
            by_filename[r["filename"]] = {"filename": r["filename"], "source_page": r["source_page"], "product_names": []}
            order.append(r["filename"])
        names = by_filename[r["filename"]]["product_names"]
        if r["product_name"] not in names:
            names.append(r["product_name"])
    out = []
    for fn in order[:limit]:
        item = by_filename[fn]
        caption = " / ".join(item["product_names"][:3]) + ("…" if len(item["product_names"]) > 3 else "")
        out.append({
            "url": f"/content-files/product-usage/{item['filename']}",
            "caption": caption,
            "source_page": item["source_page"],
        })
    return out


def _compatible_accessories(cur, groove_families, cross_sections=None, limit=24):
    # bot5 2026-08-10 (Robert: "prichozi na eshop mohl velmi rychle
    # pochopit ktere prislusenstvi nebo spojka je kompatibilní se
    # kterym profilem") - sdilena logika pro reverse-lookup profil ->
    # spojky/prislusenstvi, volana z detailu produktu (jeden profil) i
    # z kategorie (vsechny profily v ni, viz _category_product_facets).
    # Prislusenstvi se sku LIKE '2.%' ma cross_section_label/groove_family
    # se stejnymi sloupci jako profily, jen jinou semantikou - viz
    # scripts/2026-08-10_accessory_compatibility_backfill.py. NULL
    # cross_section_label = sedi na JAKYKOLI prurez v dane drazkove
    # rodine (typicky sroubovaci spojky do drazky).
    groove_families = [g for g in (groove_families or []) if g]
    if not groove_families:
        return []
    cross_sections = [c for c in (cross_sections or []) if c]
    # bot5 2026-08-10 - FIND_IN_SET misto IN(), aby spravne matchovalo i
    # prislusenstvi s CSV groove_family ("6,8,10" u kusu bez zobaku, viz
    # _category_products_with_images).
    sql = ("SELECT id, sku, name, slug, price_czk_placeholder, stock_qty, availability_text, "
           "unit, cross_section_label, groove_family "
           "FROM shop_products WHERE sku LIKE '2.%%' AND active=1 AND is_archived=0 "
           "AND (" + " OR ".join(["FIND_IN_SET(%s, groove_family)"] * len(groove_families)) + ")")
    params = list(groove_families)
    if cross_sections:
        sql += f" AND (cross_section_label IS NULL OR cross_section_label IN ({','.join(['%s'] * len(cross_sections))}))"
        params.extend(cross_sections)
    sql += " ORDER BY (cross_section_label IS NULL), name LIMIT %s"
    params.append(limit)
    cur.execute(sql, params)
    rows = cur.fetchall()
    ids = [r["id"] for r in rows]
    image_by_id = {}
    if ids:
        placeholders = ",".join(["%s"] * len(ids))
        # bot10, 2026-09-12 (stejna dira jako api/categories.py, nalez
        # bot3): chybejici is_public filtr - "Vhodne prislusenstvi" na
        # VEREJNE strance kategorie/profilu.
        cur.execute(f"""
            SELECT owner_id, filename FROM content_gallery_items
            WHERE owner_type='product' AND owner_id IN ({placeholders}) AND is_public=1
            ORDER BY owner_id, sort_order, id
        """, ids)
        for r in cur.fetchall():
            image_by_id.setdefault(r["owner_id"], f"/content-files/gallery-items/{r['filename']}")
        missing = [i for i in ids if i not in image_by_id]
        if missing:
            placeholders2 = ",".join(["%s"] * len(missing))
            cur.execute(f"""
                SELECT product_id, filename FROM shop_product_images
                WHERE product_id IN ({placeholders2}) ORDER BY product_id, sort_order, id
            """, missing)
            for r in cur.fetchall():
                image_by_id.setdefault(r["product_id"], f"/content-files/gallery/{r['filename']}")
    out = []
    for r in rows:
        out.append({
            "id": r["id"], "sku": r["sku"], "name": r["name"], "slug": r.get("slug"),
            "price_czk_placeholder": float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None,
            "unit": r["unit"], "stock_qty": r["stock_qty"], "availability_text": r["availability_text"],
            "groove_family": r["groove_family"], "cross_section_label": r["cross_section_label"],
            "image_url": image_by_id.get(r["id"]),
        })
    return out


if __name__ == "__main__":
    import sys
    # OPRAVA (bot10, 2026-08-26, schvaleno bot3) - kdyz nektera z vetvi
    # nize lokalne importuje sourozenecky modul (scene_offers/support/...),
    # ktery dela "from app import ...", Python bez tohohle aliasu NEnajde
    # modul "app" v sys.modules (bezici skript je zapsan pod klicem
    # "__main__", ne "app") a zacne CELY app.py importovat ZNOVU jako
    # samostatny modul "app" - to znovu-spusteni na svem konci znovu
    # importuje remeslo.py, ktery potrebuje jmena ze scene_offers.py (jeste
    # nedokoncene, protoze puvodni import scene_offers je porad na
    # zasobniku, uvazly presne na radku "from app import ...") ->
    # ImportError "partially initialized module". Zivy dukaz: offer-
    # expiry-reminder.service padal presne timhle zpusobem KAZDY den od
    # 20.8. (viz journalctl), zakaznici tak 6+ dni nedostavali upominky
    # na brzy vyprsejici nabidky. Alias resi problem u korene - "from app
    # import X" pak najde uz kompletne nacteny bezici skript misto
    # spousteni druhe kopie.
    sys.modules.setdefault("app", sys.modules[__name__])
    if len(sys.argv) > 1 and sys.argv[1] == "refresh-prices":
        run_price_refresh_cli()
    elif len(sys.argv) > 1 and sys.argv[1] == "refresh-product-prices":
        run_product_price_refresh_cli()
    elif len(sys.argv) > 1 and sys.argv[1] == "support-email-sync":
        # Podpora Faze 2 (bot1, 2026-07-26) - periodicka IMAP synchronizace
        # prichozich e-mailu do Podpory, viz support_email_sync.py a
        # konfigurator-support-email-sync.timer. Lokalni import (ne na
        # konci souboru jako orders/cart/.../gallery/support/cutting) -
        # tento modul neregistruje zadne Flask routy, je to cisty CLI skript.
        import support_email_sync
        support_email_sync.sync_incoming_emails()
    elif len(sys.argv) > 1 and sys.argv[1] == "bank-statements-sync":
        # Periodicka synchronizace bankovnich vypisu FIO (bot10,
        # 2026-08-21) - viz bank_statements.py hlavicka. Az bude
        # FIO_BANK_API_TOKEN k dispozici, zavesit na timer stejnym
        # vzorem jako support-email-sync/offer-expiry-reminder nize.
        import bank_statements
        bank_statements.run_bank_sync_cli()
    elif len(sys.argv) > 1 and sys.argv[1] == "offer-expiry-reminder":
        # Upominka na brzy vyprsejici online nabidky (Robert 2026-08-10),
        # viz konfigurator-offer-expiry-reminder.timer a
        # scene_offers.py::run_offer_expiry_reminder_cli. Lokalni import
        # ze stejneho duvodu jako support_email_sync vyse - v tomto miste
        # souboru (PRED radkem "import scene_offers" na konci) jeste
        # nemusi byt modul nacteny.
        import scene_offers
        scene_offers.run_offer_expiry_reminder_cli()
    elif len(sys.argv) > 1 and sys.argv[1] == "triage-auto-check":
        # Automaticke zalozeni behu trideni Emailu prichozich, kdyz je
        # dost netridenych konverzaci (Robert 2026-08-22, pres bot3),
        # viz konfigurator-triage-auto-check.timer a
        # support.py::run_triage_auto_check_cli. Lokalni import ze
        # stejneho duvodu jako scene_offers vyse.
        import support
        support.run_triage_auto_check_cli()
    else:
        app.run(host="127.0.0.1", port=8001, debug=False)



import customers  # noqa: F401 - registruje /api/customer/profile + /api/admin/customers
import documents  # noqa: F401 - registruje zalohovou fakturu/VDD/fakturu/dodaci list (viz documents.py)
import purchase_orders  # noqa: F401 - registruje nakupni objednavky + dodavatele (viz purchase_orders.py)
import emails  # noqa: F401 - registruje e-mailovy klient + historii (MUSI byt AZ PO documents, viz emails.py)
import system_emails  # noqa: F401 - registruje frontu systemovych (ne-objednavkovych) e-mailu ke schvaleni, napr. overeni e-mailu pri registraci (viz system_emails.py)
import gallery  # noqa: F401 - registruje fotogalerii realizaci (viz gallery.py)
import gallery_items  # noqa: F401 - obecny "pripojitelny" fotogalerie modul kategorie/produkt (viz gallery_items.py)
import products  # noqa: F401 - registruje /api/shop/products + /api/shop/stock/* (bot3, 2026-08-08 - vytazeno z app.py, viz products.py docstring; MUSI byt az po gallery_items)
# orders/cart MUSI byt AZ PO products (bot3, 2026-08-08) - obe si z nej
# importuji helpery (_cut_service_price_czk atd., viz products.py docstring).
import orders  # noqa: F401 - registruje /api/orders + /api/admin/orders
import cart  # noqa: F401 - registruje /api/cart
import car_storefronts  # noqa: F401 - registruje /api/storefront/* + /api/admin/storefronts (mini-eshopy per model auta, viz car_storefronts.py)
import support  # noqa: F401 - registruje zivy chat podpory (viz support.py)
import cutting  # noqa: F401 - registruje /api/admin/cutting/demo (bot4, viz NAVRH_REZNE_PLANY.md)
import crm  # noqa: F401 - registruje CRM/poptavky (viz crm.py) - support_email_sync.py na nej primo vola
import quotes  # noqa: F401 - registruje Nabidky (viz quotes.py) - crm.py a support_email_sync.py na nej primo volaji
import drive  # noqa: F401 - registruje Sdileny disk (viz drive.py) - znovupouziva helpery z quotes.py
import incoming_documents  # noqa: F401 - registruje schvalovaci frontu prijatych dokladu/faktur z e-mailu (viz incoming_documents.py), pouziva helpery z quotes.py/drive.py; support_email_sync.py na nej primo vola
import approvals  # noqa: F401 - registruje "Ke schvaleni" prehled pro dashboard + approve endpointy (viz approvals.py)
import scene_offers  # noqa: F401 - registruje tlacitko "Nabidka" ve scene.html (viz scene_offers.py), pouziva helpery z documents.py/quotes.py/drive.py
import fleet  # noqa: F401 - registruje Knihu jizd (viz fleet.py)
import leg_fbx_import  # noqa: F401 - registruje hromadny import FBX noh s rozkladem na profily (viz leg_fbx_import.py)
import dimension_match_fbx  # noqa: F401 - registruje rozklad FBX na profily podle rozmeru (viz dimension_match_fbx.py)
import universal_import  # noqa: F401 - registruje univerzalni import objektu (FBX -> rozpojena skladba dilu -> Vlastni tvar, panel ve scene; viz universal_import.py)
import stul_api  # noqa: F401 - registruje GET /api/stul/konfigurace (konfigurator stolu system 30, panel ve scene; viz stul_konfigurator.py)
import stul_shop  # noqa: F401 - registruje verejne API konfiguratoru stolu pro e-shop/mini-shop (schema, resolve, model; kontrakt docs/KONTRAKT_KONFIGURATOR_UI.md)
import hdri  # noqa: F401 - registruje spravu HDRI environmentalnich map pro 3D scenu (viz hdri.py)
import rendering_settings  # noqa: F401 - vyber aktivni slozky HDRI/PBR na Sdilenem disku pro nabidky (viz rendering_settings.py)
import blender_render  # noqa: F401 - registruje server-side render sestavy Blenderem/Cycles (viz blender_render.py)
import render_worker  # noqa: F401 - registruje vzdaleny GPU renderovaci worker (Robertuv notebook, viz render_worker.py)
import render_hdri  # noqa: F401 - vyber HDRI mapy pro automaticke rendery (Robert 2026-09-09, viz render_hdri.py)
import render_materialy  # noqa: F401 - ucinna prirazovaci tabulka renderovacich materialu katalogu (Robert 2026-10-01, viz render_materialy.py)
import scene_materials  # noqa: F401 - vychozi vlastnosti materialu sceny, sdilene se scenou i rendery (Robert 2026-09-10, viz scene_materials.py)
import render_gallery  # noqa: F401 - hotovy render -> fotogalerie skladove karty (Robert 2026-09-09, viz render_gallery.py), MUSI byt az po blender_render + gallery_items
import inquiries  # noqa: F401 - registruje verejny formular "Poptavam stul" (viz inquiries.py), pouziva quotes.save_lead_attachment
import qa_audit  # noqa: F401 - registruje /api/admin/qa-audit, panel odchylek na dashboardu (viz qa_audit.py/scripts/qa_product_audit.py)
# Řemeslo (modul 1, srovnávač cen materiálu) - PLNĚ VYČLENĚNO do /opt/remeslo
# (bot3, 2026-09-07, Robert: "remeslo mělo být oddeleno!" - separace Fáze 6
# nginx routing byla hotová 2026-09-05, ale kód/DB pripojeni na Forpsi tu
# zustaly jako zive duplikáty). `import remeslo` (a jim tazenych 12
# remeslo_*.py submodulu) odstranen - vsechny maji plny ekvivalent v
# /opt/remeslo/api/. VYJIMKA (VEDOME NEDOTCENO, viz AGENTS_LOG.md tento
# zapis): api/gallery_items.py stale ma remeslo-specificke owner_type
# vetve (foto-dokumentace zakazek/profilu/faktur) - hluboko provazane s
# historickymi nahranymi fotkami, jejichz migrace neni overena, needitovano
# bez Robertova rozhodnuti.
import bank_statements  # noqa: F401 - registruje panel Bankovní výpisy (FIO), viz bank_statements.py
import tracking  # noqa: F401 - registruje anonymní geo/page-view tracking (viz tracking.py, geoip.py)
import system_pipeline  # noqa: F401 - registruje /api/admin/system-pipeline, živý přehled všech modulů (viz system_pipeline.py, přímý vzor z /opt/toscanaccio)
import product_markups  # noqa: F401 - registruje "Zakreslenou připomínku" na stránce produktu (viz product_markups.py), MUSÍ být až po products/quotes
import offer_markup_requests  # noqa: F401 - registruje POST /api/public/offers/<token>/markup-requests = zakreslené změny v online nabídce z konfigurace stolu / Vandr karty (poptávka v CRM s obrázky; bot16, Robert 2026-10-07, viz offer_markup_requests.py), MUSÍ být až po product_markups (bere z něj validace) a scene_offers/quotes/crm/drive/gallery_items

import turntable  # noqa: F401 - registruje otočný (sférický) náhled produktové sestavy pro e-shop: upload/commit snímků ze scény + veřejné GET /api/shop/products/<id>/turntable (viz turntable.py), až po products
import turntable_ingest  # noqa: F401 - převzetí hotového renderu z GPU do otočného náhledu (volá ho render_worker po rozbalení ZIPu, viz turntable_ingest.py); ŽÁDNÉ routy, importuje se kvůli fail-fast při startu, MUSÍ být až po turntable
import client_errors  # noqa: F401 - registruje JS error beacon z prohlížečů (POST /api/client-errors, veřejné) + GET /api/admin/client-errors (viz client_errors.py), používá tracking._ip_hash - MUSÍ být až po tracking
import social_posts  # noqa: F401 - registruje /api/admin/social-posts (vyčleněno z app.py, bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 1)
import cms_blocks  # noqa: F401 - registruje /api/admin/homepage-blocks*, /api/admin/announcement-items*, /api/(admin/)sidebar-blocks* (vyčleněno z app.py, bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 2)
import content_obor  # noqa: F401 - registruje /api/admin/content-obor* + /api/admin/content-typologie* (centrální panel popisů kategorií obor->typologie, bot7, 2026-09-27, Robert pres bot3)
import accessories  # noqa: F401 - registruje /api/admin/accessories (vyčleněno z app.py, bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 3)
import montaz_mista  # noqa: F401 - registruje /api/montaz-mista + /api/admin/montaz-mista (bot5, 2026-09-13)
import internal_chat  # noqa: F401 - registruje /api/admin/internal-chat/messages (vyčleněno z app.py, bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 4)
import audit_log  # noqa: F401 - registruje /api/admin/audit-log* (vyčleněno z app.py, bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 5)
import price_scraping  # noqa: F401 - registruje /api/admin/logiman-price-check + /api/shop/products/<id>/refresh-price (vyčleněno z app.py, bot13, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 6)
import admin_users  # noqa: F401 - registruje /api/admin/users (vyčleněno z app.py, bot13, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 7)
import custom_shapes  # noqa: F401 - registruje /api/custom-shapes + /api/custom-shape-categories (vyčleněno z app.py, bot13, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 8)
import product_assemblies  # noqa: F401 - registruje /api/product-assemblies* + /api/product-assembly-categories* (vyčleněno z app.py, bot13, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 9)
import cars  # noqa: F401 - registruje /api/karoserie-model-reference + /api/car-makes*/car-models*/car-bodies* (vyčleněno z app.py, bot13, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md skupina 10)
import admin_profily  # noqa: F401 - registruje admin tabulku cen/hmotnosti profilů + upload FBX/STEP + step-quality-preview (vyčleněno z app.py, PLAN_ROZDELENI_BACKENDU.md skupina 11)
import admin_settings  # noqa: F401 - registruje field-labels/options, obecná nastavení, theme-colors, og-settings, pricing-config (vyčleněno z app.py, PLAN_ROZDELENI_BACKENDU.md skupina 12)
import storefront_pages  # noqa: F401 - registruje e-shop SSR stránky + SEO (product/kategorie/index/blok/panel, robots.txt, sitemap.xml) (vyčleněno z app.py, PLAN_ROZDELENI_BACKENDU.md skupina 13)
import categories  # noqa: F401 - registruje /api/categories* (CRUD, obsah, obrázky, bulk-move/reorder, export/import CSV, search) + category-price-coefficients (logiman-price-check zůstal v price_scraping.py, skupina 6 - stejná funkce, vyčleněna dřív) (vyčleněno z app.py, PLAN_ROZDELENI_BACKENDU.md skupina 14)
import shop_api  # noqa: F401 - registruje /api/shop/* (FBX/STEP upload+konverze+stažení STP u produktů, dashboard skladu, sestava k objednání) (refresh-price zůstal v price_scraping.py, skupina 6 - stejná funkce, vyčleněna dřív) (vyčleněno z app.py, PLAN_ROZDELENI_BACKENDU.md skupina 15)
import returns  # noqa: F401 - registruje reklamace/vratky + dobropis (viz returns.py, sql/2026-09-05_shop_returns.sql), MUSÍ být až po orders/documents
import company_info  # noqa: F401 - registruje /api/admin/company-info + /api/contact-email-image + SSR /kontakt.html (viz company_info.py, AGENTS_LOG.md 2026-09-06 "firemni udaje z DB")
import deploy_runs  # noqa: F401 - registruje GET /api/admin/deploy-runs (panel "Nasazení serveru" na Dashboardu, bot16, Robert přes bot3 2026-10-01, viz deploy_runs.py + scripts/nasazeni.py; NE /api/deploy-status výše - to je majáček držitele DEPLOY_LOCK ve scéně), MUSÍ být až po PERMISSION_SECTIONS ("dash_nasazeni")
import john_stav  # noqa: F401 - registruje GET /api/admin/john/stav (zive jednotky john-* pro panel Přehledy > John, bot16, Robert přes bot9 2026-10-06, viz john_stav.py), MUSÍ být až po PERMISSION_SECTIONS ("prehledy_john")
import ucetni_emaily  # noqa: F401 - registruje GET/PUT /api/admin/ucetni-emaily (tabulka adres ucetni podle typu dokladu, jen adresy, NIC neodesila - pravidlo 16; bot16, Robert 2026-10-06, viz ucetni_emaily.py), MUSI byt az po PERMISSION_SECTIONS ("ucetni_emaily") a po documents
import production_overview  # noqa: F401 - registruje /api/admin/vyroba-sestav/* (Přehled postupu v adminu, bot10, zadání bot3 koordinace 2026-09-11, viz PLAN_TVORBY_SESTAV.md)
import vandr_production_overview  # noqa: F401 - registruje /api/admin/vandr-vyroba/* (Vandr obdoba vyroby-sestav, bot5, zadání Robert přes bot3 2026-09-23, SAMOSTATNÝ modul, NENÍ rozšíření production_overview.py)
import vandr_scene_offers  # noqa: F401 - registruje /api/admin/vandr-vyroba/<id>/nabidka (integrace Vandr do online nabídky, bot10, zadání Robert 2026-09-28, SAMOSTATNÝ modul - viz jeho docstring proč)
import v3d_vzhled  # noqa: F401 - registruje GET /api/public/v3d-vzhled + PUT /api/admin/v3d-vzhled (vzhled online nabídek: HDRI, povrch hliníku, AO; bot10, Robert 2026-10-06, SAMOSTATNÝ modul - viz jeho docstring)
import vandr_price_webhook  # noqa: F401 - registruje /api/vandr/price-webhook (bot5, 2026-09-26, Robert: skutečné 1:1 napojení ceny Vandr sestav na vandrawee_work, vanDrawee volá při uložení ceny části)
import bots  # noqa: F401 - registruje /api/admin/bots* (registr botů se specializací, Robert 2026-09-12, viz bots.py + sql/2026-09-12_bots.sql)
import pravidla  # noqa: F401 - registruje /api/admin/pravidla-postupy* (Přehledy > Pravidla/Postupy, živé čtení z .md + Robertův výběr co zobrazit, Robert 2026-09-12, viz pravidla.py + sql/2026-09-12_pravidla_vyber.sql)
import offsite_backup  # noqa: F401 - registruje /api/admin/offsite-backup (Přehledy > Zálohy, stav Contabo S3 zálohy bez nutnosti se tam přihlašovat, Robert pres bot3 2026-09-13, viz offsite_backup.py + sql/2026-09-13_offsite_backup_log.sql)
import regal_osy_prehled  # noqa: F401 - registruje /api/admin/regal-typologie-prehled (Přehledy > Typologie/umístění regálů, živý přehled číselníků regal_typologie/regal_umisteni + počty použití, Robert pres bot9 2026-09-13, viz regal_osy_prehled.py)
import pd_desc_opacity  # noqa: F401 - registruje /api/public/pd-desc-opacity + /api/admin/pd-desc-opacity, self-service posuvník průhlednosti .pd-desc-card v product.html pro přihlášeného admina (Robert pres bot3, 2026-09-15, viz pd_desc_opacity.py)
import hover_sweep_settings  # noqa: F401 - registruje /api/public/hover-sweep-settings + /api/admin/hover-sweep-settings, self-service ovládání hover efektu "jezdící prouzek" v category.html pro přihlášeného admina (Robert pres bot3, 2026-09-15, viz hover_sweep_settings.py)
import cat_tree_colors  # noqa: F401 - registruje /api/public/cat-tree-colors + /api/admin/cat-tree-colors, self-service barva podkladu i písma stromu kategorií (#catTree) pro přihlášeného admina (Robert přímo, 2026-09-17, viz cat_tree_colors.py)
import site_font  # noqa: F401 - registruje /api/public/site-font + /api/admin/site-font, self-service výběr písma (--font-main) napříč CELÝM webem pro přihlášeného admina (Robert přímo, 2026-09-17, viz site_font.py)
import site_brand  # noqa: F401 - registruje GET /api/site-brand (logo znacky na staticke formulare JEN pro hosty Logiman, ostatni domeny zustavaji anonymni; bot16, Robert pres bot3 2026-10-01, viz site_brand.py + TEXT_FILTR.md pravidlo 5), MUSI byt az po site_font (bere z nej FONT_OPTIONS)
import base_dark_color  # noqa: F401 - registruje /api/public/base-dark-color + /api/admin/base-dark-color, self-service "základní černá" (--base-dark) na dlaždicích/náhledech napříč webem pro přihlášeného admina (Robert přímo, 2026-09-17, viz base_dark_color.py)
import sestava_typ  # noqa: F401 - registruje /api/admin/sestava-typ* + /api/admin/sestava-typ-sluzby* (nová osa "typ sestavy" AUTO/STUL_SKLAD, Robert přes bot3 2026-09-26, PLAN_TVORBY_SESTAV.md, viz sestava_typ.py + sql/2026-09-26_sestava_typ_tabulka.sql)
import dealers  # noqa: F401 - registruje dealersky program: /api/admin/dealers*, /api/dealer/* (panel, odkaz /api/dealer/go/<kod>), overeni klicu dealeru (bot5, Robert pres bot3 2026-10-02, viz dealers.py + sql/2026-10-02_dealers.sql)
import dealer_commissions  # noqa: F401 - registruje provize dealeru, krok 2 (jen cteni): /api/dealer/commissions|orders, /api/admin/dealer-commissions (bot5, Robert pres bot3 2026-10-02, viz dealer_commissions.py), MUSI byt az po dealers
import dealer_statements  # noqa: F401 - registruje mesicni vyuctovani provizi dealeru, krok 3: /api/admin/dealer-statements*, /api/dealer/statements* (bot5, Robert pres bot3 2026-10-02, viz dealer_statements.py + sql/2026-10-02_dealer_statements.sql), MUSI byt az po dealer_commissions
import dealer_orders  # noqa: F401 - registruje dealerskou objednavku pres API, krok 4: /api/dealer/v1/quote|orders (bot5, Robert pres bot3 2026-10-02, viz dealer_orders.py + DEALER_API.md), MUSI byt az po orders a dealers
import dealer_feed  # noqa: F401 - registruje feed produktu pro dealery, krok 5: /api/dealer/v1/feed.csv|xml (bot5, Robert pres bot3 2026-10-02, viz dealer_feed.py + DEALER_API.md), MUSI byt az po dealers
import miniweb  # noqa: F401 - registruje mini-shop API /api/miniweb/* (config, categories, products, legal, inquiry; bot5, Robert pres bot3 2026-10-02, viz miniweb.py + sql/2026-10-02_miniweb*.sql), MUSI byt az po dealers (brand filtr), car_storefronts a documents
import miniweb_admin  # noqa: F401 - registruje import a schvalovani textu mini-shopu /api/admin/miniweb/* (jen admin; bot5, Robert pres bot3 2026-10-02, viz miniweb_admin.py + webapp/miniweb-schvaleni.html), MUSI byt az po miniweb
import miniweb_objednavky  # noqa: F401 - registruje kosik a objednavku mini-shopu /api/miniweb/quote|orders|vat-check (faze 3 SK; bot5, Robert pres bot3 2026-10-03, viz miniweb_objednavky.py)
import miniweb_objednavky_admin  # noqa: F401 - registruje schvaleni dopravy objednavky mini-shopu /api/admin/orders/<id>/shipping (krok 2; bot5, 2026-10-03)
import miniweb_shops_admin  # noqa: F401 - registruje admin API Mini-shopy /api/admin/miniweb/shops|inquiries|orders (RBAC miniweb; bot5, 2026-10-03, viz miniweb_shops_admin.py)
import stul_montaz  # noqa: F401 - sazba montaze stolu (app_settings stul_montaz_pct, GET/PUT /api/stul/montaz; bot5, Robert pres bot9 2026-10-04, viz stul_montaz.py)
import stul_objednavka_host  # noqa: F401 - objednavka konfigurovaneho stolu HOSTEM bez registrace /api/shop/stul/quote|order (bot5, 2026-10-04, viz stul_objednavka_host.py)
import ucetni_hak  # noqa: F401 - schvaleny doklad -> e-mail ucetni do FRONTY ke schvaleni (pravidlo 16 beze zmeny; Robert 2026-10-06; bot5), prepne ucetni_emaily.ODESILANI_ZAPOJENO
import stul_ulozeni  # noqa: F401 - Ulozit konfiguraci stolu (ICO + e-mail + telefon, overeni v ARES/RPO a DNS pred ulozenim; POST /api/shop/configurator/ulozit, GET .../ulozena/<token>; bot16, Robert 2026-10-05, viz stul_ulozeni.py; tabulka se zapina DDL skriptem sql/2026-10-05_stul_ulozene_konfigurace.py, bez ni 503), MUSI byt az po miniweb a konfigurace_kosik
import nabidka_z_konfigurace  # noqa: F401 - registruje online nabidku z konfigurace stolu POST /api/admin/konfigurace/nabidka (jen zamestnanec s pravem nabidky/vytvorit; bot5, Robert pres bot9 2026-10-06, docs/KONTRAKT_NABIDKA_Z_KONFIGURACE.md)
import stul_karta  # noqa: F401 - registruje kartu produktu z konfigurace stolu GET/POST /api/admin/konfigurace/karta (tlacitko "Vytvorit kartu" v generatorech; jen s pravem sklad_karty/vytvorit; bot10, Robert 2026-10-07 "tlacitko ktere z aktualni sestavy vytvori aktivni kartu", docs/KONTRAKT_KARTA_Z_KONFIGURACE.md)
import legal_pages  # noqa: F401 - pravni stranky HLAVNIHO webu /ochrana-osobnich-udaju a /obchodni-podminky z miniweb_documents (cs, schvalene; jen hosty se znackou; bot16, Robert 2026-10-05, viz legal_pages.py)
import web_i18n  # noqa: F401 - IT/EN verze hlavniho webu (vandrawee.eu / .it): host -> jazyk, nahled ?jazyk=en|it jen pro zamestnance, preklady verejnych JSON endpointu, ceny EUR, slovnik textu stranek, vlozeni i18n.js, noindex (bot16, Robert 2026-10-08, docs/web_jazyky/README.md); MUSI byt PO storefront_pages a products
import miniweb_seo  # noqa: F401 - server-side SEO verejneho mini-shopu: hezke adresy, title/description/canonical/hreflang/og/JSON-LD, sitemap.xml, robots.txt (bot16, Robert pres bot3 2026-10-03; sablony bot7 v miniweb_seo_sablony.json; indexace jen u live shopu), MUSI byt az po miniweb
