"""Ulozena konfigurace stolu v generatoru (bot16, 2026-10-05; Robert: "Konfigurace ma zmizet, neulozit se po zavreni prohlizece. Nabidneme moznost ulozeni konfigurace po zadani
ICO, email, telefon (overit platnost ICO a emailu pred ulozenim)" - generator stolu na vsech webech: hlavni e-shop, kategorie a karty, mini-shopy).

  POST /api/shop/configurator/ulozit           {product_id, configuration:{selection, rules_version}, ico, email, phone, consent:true, country?, website (honeypot)}
                                                -> 201 {status:"ok", token, kod, firma, odkaz_platnost_dni}; chyby {error, field}: ico_invalid, ico_not_found, registry_unavailable, email_invalid,
                                                email_domain, email_unverifiable, phone_invalid, consent_required, config_invalid, rules_changed, product_not_available, too_many, rate_limited
  GET  /api/shop/configurator/ulozena/<token>  -> 200 {product_id, system, selection, rules_version, kod, saved_at}; 404 not_found (neplatny / vyprseny odkaz)

Cesta je pod /api/shop/configurator/ zamerne: nginx vhosty mini-shopu propousti prave tuhle predponu (a /api/miniweb/), takze endpoint funguje na vsech webech bez zmeny nginx.

Pravidla (nemenit bez Roberta):
  * ICO se pred ulozenim OVERI v registru: CZ = kontrolni cislice + ARES (obchodni jmeno, zanik), SK = registr RPO (Statisticky urad). Registr nedostupny = 503 registry_unavailable a NIC se neuklada.
  * E-MAIL: format + existence domeny, ktera prijima postu (MX; bez MX A/AAAA podle RFC 5321; null MX = ne) pres DNS-over-HTTPS (Cloudflare) se zalohou `dig`. NIKDY se neodesila zadny e-mail
    (WORKFLOW pravidlo 16; mini-shopy nepotvrzuji e-mailem): odkaz pro navrat dostane zakaznik na obrazovce, zamestnanec ho vidi v CRM.
  * Telefon: normalizace + 9 az 15 cislic. Souhlas se zpracovanim udaju je povinny (consent true).
  * Konfigurace se overi na serveru (konfigurace_kosik.vyres = tentyz konfigurator jako kosik); uklada se jen EFEKTIVNI vyber, zadna cena od klienta.
  * Zaznam: tabulka stul_ulozene_konfigurace (DDL SKRIPTEM sql/2026-10-05_stul_ulozene_konfigurace.py, spousti bot3/Robert; modul DDL za behu NEDELA: bez tabulky vraci 503 unavailable a UI se
    vubec neukaze = tabulka je zaroven vypinac, zapnout az po schvaleni textu ochrany osobnich udaju) + lead v crm_leads (source stul_ulozeni, estimated_value = cena konfigurace v Kc BEZ DPH,
    zprava pro zamestnance s kodem, firmou a odkazem). Token se v tabulce drzi jen jako SHA-256 (sloupec token_hash); odkaz plati 90 dni; zaznam v CRM zustava. Sloupec karty se jmenuje
    karta_id (QA kontrola product_duplicate_unclassified_table hlida sloupce product_id / shop_product_id). E-mail, telefon a ICO jsou osobni udaje (doba uchovani k posouzeni pravnika).
  * Mini-shop: karta musi byt jedna z verejnych konfigurovatelnych produktu TOHOTO shopu; shop, ktery neni live (nahled pro staff), jen zvaliduje a NEULOZI (zadna testovaci data v produkci).
  * Ochrany: honeypot, rate limit IP (6 / 10 min), e-mail a ICO za den, delky, token 128 bitu (secrets.token_urlsafe), X-Robots-Tag noindex, Cache-Control no-store.
"""
import hashlib
import json
import os
import re
import secrets
import subprocess
import urllib.error
import urllib.parse
import urllib.request

import pymysql
from flask import jsonify, request

from app import app, get_conn, _client_ip, _rate_limited
import konfigurace_kosik as kk
import miniweb

ODKAZ_DNI = 90
LIMIT_IP = (6, 600)
LIMIT_EMAIL_DEN = 5
LIMIT_ICO_DEN = 10
LIMIT_CTENI = (60, 60)
MAX_BODY = 65536
TIMEOUT_ARES, TIMEOUT_RPO, TIMEOUT_DOH = 4, 5, 3
ARES_URL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/%s"
RPO_URL = "https://api.statistics.sk/rpo/v1/search?identifier=%s"
DOH_URL = "https://cloudflare-dns.com/dns-query?"
COUNTRIES = ("CZ", "SK")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,32}\Z")
_EMAIL_RE = miniweb._EMAIL_RE
TABULKA_CHYBI = 1146                                                    # MySQL: tabulka neexistuje (DDL se jeste nespustil)

DDL = """CREATE TABLE IF NOT EXISTS stul_ulozene_konfigurace (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  token_hash CHAR(64) NOT NULL,
  karta_id INT NOT NULL,
  system_profilu TINYINT NULL,
  config_hash VARCHAR(64) NULL,
  config_kod VARCHAR(24) NULL,
  rules_version VARCHAR(64) NULL,
  selection_json MEDIUMTEXT NOT NULL,
  net_czk DECIMAL(12,2) NULL,
  ico CHAR(8) NOT NULL,
  country CHAR(2) NOT NULL,
  firma VARCHAR(255) NULL,
  email VARCHAR(255) NOT NULL,
  phone VARCHAR(40) NOT NULL,
  shop_host VARCHAR(255) NULL,
  ip_hash CHAR(64) NULL,
  crm_lead_id INT NULL,
  consent_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NOT NULL,
  UNIQUE KEY uq_token (token_hash),
  KEY ix_email (email),
  KEY ix_ico (ico),
  KEY ix_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


class UlozChyba(Exception):
    def __init__(self, status, code, field=None, extra=None):
        super().__init__(code)
        self.status, self.code, self.field, self.extra = status, code, field, extra or {}


def _resp(payload, status=200):
    r = jsonify(payload)
    r.status_code = status
    r.headers["X-Robots-Tag"] = "noindex, nofollow"
    r.headers["Cache-Control"] = "no-store"
    return r


def _hash_tokenu(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _tabulka_chybi(e):
    return e.args and e.args[0] == TABULKA_CHYBI


# ------------------------------------------------------------------ overeni udaju (cista logika; sit se vola jen pres _http_json / _dig, v testech podstrcene)
def _http_json(url, timeout, headers=None):
    """GET JSON; (status, data|None). Sitova chyba / nevalidni JSON = (None, None)."""
    req = urllib.request.Request(url, headers=dict({"Accept": "application/json", "User-Agent": "konfigurator-ulozeni/1.0"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return e.code, None
    except Exception:
        return None, None


def norm_ico(raw):
    s = re.sub(r"\s+", "", raw or "")
    if not re.fullmatch(r"[0-9]{6,8}", s) or not s.strip("0"):
        return None
    return s.zfill(8)


def ico_checksum_ok(ico8):
    """Kontrolni cislice ICO (modulo 11, vahy 8..2) - plati pro ceska ICO; slovenska se overuji v registru."""
    a = sum(int(ico8[i]) * (8 - i) for i in range(7)) % 11
    c = 11 - a
    c = 0 if c == 10 else (1 if c == 11 else c)
    return int(ico8[7]) == c


def overit_ico(ico, country, http=None):
    """-> {firma, adresa, dic, zdroj}; UlozChyba ico_invalid (400) / ico_not_found (422) / registry_unavailable (503)."""
    http = http or _http_json
    if country == "CZ":
        if not ico_checksum_ok(ico):
            raise UlozChyba(400, "ico_invalid", "ico")
        st, d = http(ARES_URL % ico, TIMEOUT_ARES)
        if st == 404:
            raise UlozChyba(422, "ico_not_found", "ico")
        if st != 200 or not isinstance(d, dict):
            raise UlozChyba(503, "registry_unavailable", "ico")
        if d.get("datumZaniku"):
            raise UlozChyba(422, "ico_not_found", "ico")
        return {"firma": (d.get("obchodniJmeno") or "")[:255], "adresa": ((d.get("sidlo") or {}).get("textovaAdresa") or "")[:500], "dic": (d.get("dic") or "")[:20], "zdroj": "ARES"}
    st, d = http(RPO_URL % ico, TIMEOUT_RPO)
    if st != 200 or not isinstance(d, dict):
        raise UlozChyba(503, "registry_unavailable", "ico")
    res = [r for r in (d.get("results") or []) if any(i.get("value") == ico for i in (r.get("identifiers") or []))]
    if not res:
        raise UlozChyba(422, "ico_not_found", "ico")
    r = res[0]
    names = sorted((r.get("fullNames") or []), key=lambda n: (n.get("validTo") is None, n.get("validFrom") or ""))
    return {"firma": ((names[-1].get("value") if names else "") or "")[:255], "adresa": "", "dic": "", "zdroj": "RPO"}


def norm_email(raw):
    e = (raw or "").strip().lower()
    if len(e) > 254 or not _EMAIL_RE.match(e) or ".." in e:
        raise UlozChyba(400, "email_invalid", "email")
    return e


def _mx_doh(domain, http=None):
    """'ok' | 'none' | 'unknown' pres DNS-over-HTTPS (Cloudflare)."""
    http = http or _http_json

    def q(typ):
        return http(DOH_URL + urllib.parse.urlencode({"name": domain, "type": typ}), TIMEOUT_DOH, {"Accept": "application/dns-json"})
    st, d = q("MX")
    if st != 200 or not isinstance(d, dict):
        return "unknown"
    if d.get("Status") == 3:
        return "none"
    if d.get("Status") != 0:
        return "unknown"
    mx = [a for a in (d.get("Answer") or []) if a.get("type") == 15]
    if mx:
        return "none" if all(str(a.get("data", "")).strip() in ("0 .", "0 ") for a in mx) else "ok"
    for typ in ("A", "AAAA"):                                           # bez MX plati implicitni MX = A/AAAA domeny (RFC 5321)
        st, d = q(typ)
        if st == 200 and isinstance(d, dict) and d.get("Status") == 0 and any(a.get("type") in (1, 28) for a in (d.get("Answer") or [])):
            return "ok"
    return "none"


def _mx_dig(domain):
    try:
        out = subprocess.run(["dig", "+short", "+time=3", "+tries=1", "MX", domain], capture_output=True, text=True, timeout=8)
    except Exception:
        return "unknown"
    if out.returncode != 0:
        return "unknown"
    lines = [x.strip() for x in out.stdout.splitlines() if x.strip()]
    if not lines:
        return "unknown"                                                # prazdny vystup nerozlisi "bez MX" od "DNS neodpovedelo"
    return "none" if all(x in ("0 .", "0") for x in lines) else "ok"


def overit_domenu_emailu(email, doh=None, dig=None):
    """UlozChyba email_domain (422) / email_unverifiable (503); jinak None."""
    domain = email.rsplit("@", 1)[1]
    st = (doh or _mx_doh)(domain)
    if st == "unknown":
        st = (dig or _mx_dig)(domain)
    if st == "none":
        raise UlozChyba(422, "email_domain", "email")
    if st != "ok":
        raise UlozChyba(503, "email_unverifiable", "email")


def norm_phone(raw, country):
    """Telefon -> +<predvolba><cislo> (9 az 15 cislic). Bez predvolby: 9 cislic = vnitrostatni cislo zeme (CZ +420, SK +421), slovenske 0XXXXXXXXX se nulou na zacatku bere bez ni,
    delsi retezec cislic uz predvolbu obsahuje. Cokoli jineho (pismena, kratke cislo) = phone_invalid."""
    s = re.sub(r"[\s().\-/]", "", raw or "")
    if s.startswith("00"):
        s = "+" + s[2:]
    if not re.fullmatch(r"\+?[0-9]{9,15}", s):
        raise UlozChyba(400, "phone_invalid", "phone")
    cc = "+420" if country == "CZ" else "+421"
    if not s.startswith("+"):
        if len(s) == 10 and s.startswith("0") and country == "SK":
            s = cc + s[1:]                                              # SK vnitrostatni zapis 0903 123 456
        elif len(s) == 9:
            s = cc + s
        else:
            s = "+" + s                                                 # uz s predvolbou (420603230059)
    if not re.fullmatch(r"\+[1-9][0-9]{9,14}", s):
        raise UlozChyba(400, "phone_invalid", "phone")
    return s


# ------------------------------------------------------------------ endpointy
def _vstup():
    if request.content_length is not None and request.content_length > MAX_BODY:
        raise UlozChyba(413, "payload_too_large")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise UlozChyba(400, "invalid_json")
    return body


def _zeme(body, ctx):
    """Zeme pro overeni ICO: z tela (CZ|SK), jinak podle shopu s jedinou zemi, jinak CZ (hlavni e-shop)."""
    c = body.get("country")
    if isinstance(c, str) and c.strip().upper() in COUNTRIES:
        return c.strip().upper()
    if ctx:
        zeme = [x.strip().upper() for x in (ctx["shop"].get("countries") or "").split(",") if x.strip()]
        if len(zeme) == 1 and zeme[0] in COUNTRIES:
            return zeme[0]
        if "SK" in zeme and "CZ" not in zeme:
            return "SK"
    return "CZ"


def _karta_povolena(cur, ctx, product_id):
    if not kk.je_konfigurovatelny(product_id):
        return False
    if ctx is None:                                                     # hlavni e-shop: aktivni neslozena karta
        cur.execute("SELECT active, is_archived FROM shop_products WHERE id=%s", (product_id,))
        r = cur.fetchone()
        return bool(r and r["active"] and not r["is_archived"])
    produkty, _ = miniweb._visible_products(cur, ctx)                   # mini-shop: jen verejne konfigurovatelne produkty TOHOTO shopu
    return any((p.get("configurator") or {}).get("available") and int((p.get("configurator") or {}).get("product_id") or 0) == product_id for p in produkty)


def _lead_text(host, kod, system, net, firma, ico, zdroj, email, phone, summary, token, product_id):
    radky = [f"Zákazník uložil konfiguraci stolu (web {host}).",
             f"Kód konfigurace: {kod} · systém profilu {system or '?'} · orientační cena {int(net):,} Kč bez DPH".replace(",", " ") if net is not None else f"Kód konfigurace: {kod}",
             f"Firma: {firma or '?'} · IČO {ico} (ověřeno v {zdroj})", f"E-mail: {email} · telefon: {phone}",
             f"Odkaz pro návrat ke konfiguraci: https://{host}/embed/stul.html?p={product_id}&ulozena={token}", "", "--- Volby ---"]
    radky += [f"{s['label']}: {s['value']}" for s in (summary or [])[:60]]
    return "\n".join(radky)


@app.post("/api/shop/configurator/ulozit")
def stul_ulozit():
    try:
        if _rate_limited(f"stul_ulozit:{_client_ip()}", *LIMIT_IP):
            raise UlozChyba(429, "rate_limited")
        body = _vstup()
        if body.get("website"):                                         # honeypot: clovek ho nevidi, bot ano; tvarime se, ze se povedlo, a nic neukladame
            return _resp({"status": "ok"}, 201)
        pid = miniweb._as_int(body.get("product_id"))
        conf = body.get("configuration")
        if pid is None or not isinstance(conf, dict) or not isinstance(conf.get("selection"), dict) or miniweb._too_deep(conf):
            raise UlozChyba(400, "configuration_required", "configuration")
        rv = conf.get("rules_version")
        rv = rv if isinstance(rv, str) and len(rv) <= 64 else None
        if body.get("consent") is not True:
            raise UlozChyba(400, "consent_required", "consent")
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                try:
                    ctx = miniweb._shop_context(cur)                    # mini-shop podle hosta; hlavni e-shop = ShopError -> bez kontextu
                except miniweb.ShopError:
                    ctx = None
                zeme = _zeme(body, ctx)
                ico = norm_ico(miniweb._str_only(body.get("ico")))
                if not ico:
                    raise UlozChyba(400, "ico_invalid", "ico")
                email = norm_email(miniweb._str_only(body.get("email")))
                phone = norm_phone(miniweb._str_only(body.get("phone")), zeme)
                if not _karta_povolena(cur, ctx, pid):
                    raise UlozChyba(422, "product_not_available", "configuration")
                try:
                    res = kk.vyres(cur, pid, conf["selection"], "cs", rv)
                except kk.KonfiguraceChyba as e:
                    raise UlozChyba(409 if e.code in ("rules_changed", "price_on_request") else (422 if e.code == "invalid_configuration" else e.status),
                                    "rules_changed" if e.code == "rules_changed" else ("config_invalid" if e.code in ("invalid_configuration", "invalid_selection", "price_on_request") else "product_not_available"), "configuration")
                if ctx is not None and not ctx["live"]:                 # nahled konceptu pro staff: jen validace, nic se neuklada
                    return _resp({"status": "ok", "preview": True}, 201)
                try:
                    cur.execute("SELECT COUNT(*) AS n FROM stul_ulozene_konfigurace WHERE email=%s AND created_at > NOW() - INTERVAL 1 DAY", (email,))
                except pymysql.err.ProgrammingError as e:
                    if _tabulka_chybi(e):
                        raise UlozChyba(503, "unavailable")           # DDL jeste nebezel: ukladani neni zapnute
                    raise
                if cur.fetchone()["n"] >= LIMIT_EMAIL_DEN:
                    raise UlozChyba(429, "too_many")
                cur.execute("SELECT COUNT(*) AS n FROM stul_ulozene_konfigurace WHERE ico=%s AND created_at > NOW() - INTERVAL 1 DAY", (ico,))
                if cur.fetchone()["n"] >= LIMIT_ICO_DEN:
                    raise UlozChyba(429, "too_many")
                info = overit_ico(ico, zeme)                            # registr, az kdyz je zbytek v poradku (sit je drahá): ICO a e-mail se overuji PRED ulozenim
                overit_domenu_emailu(email)
                host = (request.host or "").split(":")[0][:255]
                system = res["selection"].get("system") if isinstance(res.get("selection"), dict) else None
                try:
                    import stul_shop
                    system = stul_shop.system_pro_produkt(pid)
                except Exception:                                       # noqa: BLE001 - system je jen popisek; neznamy nesmi shodit ulozeni
                    system = system if isinstance(system, int) else None
                token = secrets.token_urlsafe(16)[:22]
                ip_hash = hashlib.sha256((_client_ip() + "|" + (os.environ.get("SECRET_KEY") or "stul")).encode()).hexdigest()
                cur.execute("SELECT id FROM shop_customers WHERE email=%s LIMIT 1", (email,))
                cust = cur.fetchone()
                cur.execute("INSERT INTO crm_leads (customer_id, contact_name, contact_email, contact_phone, company_name, estimated_value, subject, source, unread_by_admin) VALUES (%s,%s,%s,%s,%s,%s,%s,'stul_ulozeni',1)",
                            (cust["id"] if cust else None, info["firma"] or ico, email, phone, info["firma"] or None, res["net_czk"], f"Uložená konfigurace stolu {res['kod']} ({host})"[:500]))
                lead_id = cur.lastrowid
                cur.execute("INSERT INTO crm_lead_messages (lead_id, sender_type, sender_name, body) VALUES (%s,'contact',%s,%s)",
                            (lead_id, info["firma"] or ico, _lead_text(host, res["kod"], system, res["net_czk"], info["firma"], ico, info["zdroj"], email, phone, res["summary"], token, pid)))
                cur.execute("INSERT INTO stul_ulozene_konfigurace (token_hash, karta_id, system_profilu, config_hash, config_kod, rules_version, selection_json, net_czk, ico, country, firma, email, phone, shop_host, ip_hash, crm_lead_id, consent_at, expires_at) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(), NOW() + INTERVAL %s DAY)",
                            (_hash_tokenu(token), pid, system, res["hash"], res["kod"], res["rules_version"], json.dumps(res["selection"], ensure_ascii=False, sort_keys=True), res["net_czk"], ico, zeme, info["firma"] or None,
                             email, phone, host, ip_hash, lead_id, ODKAZ_DNI))
            conn.commit()
        finally:
            conn.close()
        return _resp({"status": "ok", "token": token, "kod": res["kod"], "firma": info["firma"], "odkaz_platnost_dni": ODKAZ_DNI}, 201)
    except UlozChyba as e:
        out = {"error": e.code}
        if e.field:
            out["field"] = e.field
        out.update(e.extra)
        return _resp(out, e.status)


@app.get("/api/shop/configurator/ulozena/<token>")
def stul_ulozena(token):
    if _rate_limited(f"stul_ulozena:{_client_ip()}", *LIMIT_CTENI):
        return _resp({"error": "rate_limited"}, 429)
    if not _TOKEN_RE.match(token or ""):
        return _resp({"error": "not_found", "ulozeni": 1}, 404)          # "ulozeni": 1 = znacka tohoto endpointu (UI podle ni pozna, ze funkce existuje, a ne obecne 404 starsiho serveru)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT karta_id, system_profilu, selection_json, rules_version, config_kod, created_at FROM stul_ulozene_konfigurace WHERE token_hash=%s AND expires_at > NOW()", (_hash_tokenu(token),))
            except pymysql.err.ProgrammingError as e:
                if _tabulka_chybi(e):
                    return _resp({"error": "unavailable"}, 503)
                raise
            r = cur.fetchone()
    finally:
        conn.close()
    if not r:
        return _resp({"error": "not_found", "ulozeni": 1}, 404)
    try:
        sel = json.loads(r["selection_json"])
    except Exception:
        return _resp({"error": "not_found", "ulozeni": 1}, 404)
    return _resp({"product_id": r["karta_id"], "system": r["system_profilu"], "selection": sel, "rules_version": r["rules_version"], "kod": r["config_kod"], "saved_at": str(r["created_at"])})
