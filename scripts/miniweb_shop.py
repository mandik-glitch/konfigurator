#!/opt/konfigurator/api/venv/bin/python
"""Zalozeni a uprava mini-shopu (storefront + radek miniweb_shops) bez rucniho SQL (bot5, 2026-10-02; Robert pres bot3: nejdriv slovenska verze, anglictina druha).

Shop = storefront (`car_storefronts`: domena a jazyk) + radek v `miniweb_shops` (rodina, mena, locale, barva, zeme, neutralni kontakt). Dalsi jazyk = dalsi storefront na jine domene se stejnou rodinou
(z toho hreflang `alternates`), kod API se nemeni. Storefront se zaklada VZDY jako `draft` (vidi ho jen prihlaseny staff na serveru), do `live` ho nikdy neprepina tenhle skript
(spusteni shopu je rozhodnuti Roberta + infrastruktura: DNS, TLS certifikat, nginx vhost).

  scripts/miniweb_shop.py --slug packstations-sk --host baliace-stoly.top --lang sk --family packstations --currency EUR --locale sk-SK --countries SK --accent "#2dd4bf" \\
                          [--name "Baliace stoly (SK)"] [--phone "+421 ..."] [--hours "Po-Pi 9:00-17:00"] [--price-mode hidden] [--inquiry on|off] [--cert-group SKUPINA] [--apply]
  (telefon a doba jsou volitelne: bez nich se na strance zadny kontakt neukazuje a zakaznik pise jen poptavkovym formularem;
   `--contact-from-company on` vezme jmeno, adresu a telefon z nastaveni spolecnosti na serveru (jeden zdroj, nikdy e-mail ani web), `off` to vrati)

SPUSTENI A VYPNUTI: `--slug X --go-live [--apply]` prepne storefront z draft na live, ale JEN kdyz jsou splnene podminky (jinak vypise, co chybi a nic nezmeni): je nainstalovany nginx vhost
domeny (miniweb_nginx_install.sh), shop ma zeme dodani a prijima poptavky, v jazyce shopu je aspon jedna verejna kategorie a produkt (schvaleny text), identifikace prodejce (legal.seller) je uplna a je schvalena informace o ochrane osobnich udaju (privacy). Dalsi pravni dokumenty (terms, returns,
shipping, cookies) jsou volitelne a spusteni nezadrzuji (Robert 2026-10-03: jen "bezne zakonne prvky"); jde je pozadovat volbou `--require-docs terms,privacy,returns`.
DNS skript neoveri (jen pripomene). `--take-offline [--apply]` vrati storefront do draft (verejne zmizi) bez podminek.
Bez --apply je to NAHLED (nic se nezapise). Storefront, ktery uz existuje, se nemeni (kontroluje se jen shoda hosta a jazyka, jinak chyba); radek shopu se zalozi, a kdyz uz existuje, upravi se JEN
pole zadana v prikazu. Bez znacky (fail closed jako API: nazev, slug, domena, telefon a doba se kontroluji `dealers._brand_hit`). E-mail se do kontaktu NEUKLADA (API zadny e-mail nevydava).
Verejny mini-shop ma vlastni omezeny nginx vhost a sdileny Origin CA certifikat (scripts/gen_miniweb_vhost.py, miniweb_domena.py, miniweb_nginx_install.sh, bot16), proto sloupec `origin_cert_group` storefrontu
nema vyznam (kind miniweb ho generator vhostu autovych mini-webu nebere): zaklada se s hodnotou `miniweb`. Pripojeni domeny skript pri --go-live pozna podle nainstalovaneho vhostu `miniweb-<domena>` v nginx.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/miniweb_shop.py ...
Navratovy kod: 0 v poradku, 2 chyba nebo nesplnene podminky (nic se nezapsalo).
"""
import argparse
import json
import os
import re
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_HOST_RE = re.compile(r"^(?=.{4,200}\Z)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+\Z")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,98}[a-z0-9]\Z")
CERT_GROUP = "miniweb"                                                  # sloupec origin_cert_group se u mini-shopu nepouziva (vlastni vhost a sdileny certifikat)
NGINX_ENABLED = "/etc/nginx/sites-enabled"                              # tady je po miniweb_nginx_install.sh vhost miniweb-<domena>
REQUIRED_DOCS = ("privacy",)                                           # Robert 2026-10-03: jen "bezne zakonne prvky": informace o ochrane osobnich udaju (+ identifikace prodejce z legal.seller); podminky a vraceni jsou volitelne
DOC_LABELS = {"terms": "obchodní podmínky", "privacy": "ochrana osobních údajů", "returns": "reklamace a záruka", "shipping": "doprava", "cookies": "cookies"}


def _pole(args, mw, dealers):
    """Overena pole shopu z argumentu -> ({sloupec: hodnota}, [chyby]). Jen pole, ktera byla v prikazu zadana."""
    chyby, out = [], {}
    if args.family is not None:
        if not mw._SLUG_RE.match(args.family):
            chyby.append("family: malá písmena, číslice a pomlčky (např. packstations)")
        else:
            out["family"] = args.family
    if args.price_mode is not None:
        out["price_mode"] = args.price_mode
    if args.margin_pct is not None:
        if not (0 <= args.margin_pct <= 500):
            chyby.append("margin-pct: 0 až 500 (marže v % na kurz)")
        else:
            out["margin_pct"] = args.margin_pct
    if args.eur_rate is not None:
        if args.eur_rate == 0:
            out["eur_rate"] = None        # 0 = zpět na živý kurz Fio
        elif args.eur_rate < 0:
            chyby.append("eur-rate: Kč za 1 EUR (kladné), 0 = živý kurz Fio")
        else:
            out["eur_rate"] = args.eur_rate
    if args.currency is not None:
        if not mw._CURRENCY_RE.match(args.currency):
            chyby.append("currency: tři velká písmena (EUR)")
        else:
            out["currency"] = args.currency
    if args.locale is not None:
        if not mw._LOCALE_RE.match(args.locale):
            chyby.append("locale: např. sk-SK, en-IE")
        else:
            out["locale"] = args.locale
    if args.accent is not None:
        if not mw._ACCENT_RE.match(args.accent):
            chyby.append("accent: barva #rrggbb")
        else:
            out["accent"] = args.accent
    if args.countries is not None:
        kody = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
        if not kody or any(not mw._COUNTRY_RE.match(c) for c in kody):
            chyby.append("countries: kódy zemí ISO oddělené čárkou (SK,CZ,AT)")
        else:
            out["countries"] = ",".join(dict.fromkeys(kody))[:100]
    if args.inquiry is not None:
        out["inquiry_enabled"] = 1 if args.inquiry == "on" else 0
    if args.orders is not None:
        out["orders_enabled"] = 1 if args.orders == "on" else 0       # kosik a objednavka (api/miniweb_objednavky.py), vyzaduje sloupec ze sql/2026-10-03_miniweb_orders_enabled.py
    if args.contact_from_company is not None:
        out["_use_company"] = args.contact_from_company == "on"
    if args.phone is not None or args.hours is not None:
        kontakt = {}
        for klic, hodnota, limit in (("phone", args.phone, 40), ("hours", args.hours, 120)):
            if hodnota is None:
                continue
            hodnota = hodnota.strip()
            if not hodnota or len(hodnota) > limit or re.search(r"[<>@\x00-\x1f]", hodnota):
                chyby.append(f"{klic}: neprázdný text bez značek a bez e-mailu, nejvýše {limit} znaků")
            else:
                kontakt[klic] = hodnota
        if kontakt:
            out["_contact"] = kontakt
    return out, chyby


def _json_soubor(cesta):
    try:
        with open(cesta, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _chybejici_klice(ref, cil, cesta=""):
    """Klice (tecka-oddelene cesty) referencniho slovniku, ktere v cilovem chybi (rekurzivne pres slovniky)."""
    out = []
    for k, v in ref.items():
        c = f"{cesta}.{k}" if cesta else k
        if k not in cil:
            out.append(c)
        elif isinstance(v, dict) and isinstance(cil[k], dict):
            out += _chybejici_klice(v, cil[k], c)
    return out


def _paths_jazyka(repo):
    import ast
    try:
        src = open(os.path.join(repo, "api", "miniweb_seo.py"), encoding="utf-8").read()
        for node in ast.parse(src).body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "PATHS":
                return ast.literal_eval(node.value)
    except (OSError, SyntaxError, ValueError):
        pass
    return {}


def _parita_server(base, ref, repo=REPO):
    """[(splneno, popis)] vrstva SERVER paritniho nastroje `scripts/miniweb_jazyk_parita.py` (sada api/jazyky/<jazyk>.json vs. vsechny retezce v kodu serveru): v PODPROCESU, protoze nastroj
    importuje cele API (nezavisle na tomhle procesu; kontrola trva par vterin). Chybejici polozka by se u zakaznika ukazala anglicky (kod se pri pridani nove volby/hlasky meni po vzniku sady).
    Kontrola, ktera se nepodari provest, je NESPLNENA (brana nesmi mlcky propustit)."""
    cmd = [sys.executable, os.path.join(repo, "scripts", "miniweb_jazyk_parita.py"), "--lang", base, "--ref", ref, "--bez-db", "--json"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=repo)
        data = json.loads(r.stdout)
        radky = [k for k in data.get("kontroly", []) if k.get("vrstva") == "server"]
    except Exception as e:                                                                  # noqa: BLE001 - brana: jakakoli chyba = nesplneno
        return [(False, f"úplnost serverové sady (scripts/miniweb_jazyk_parita.py {base}) se nepodařilo ověřit: {str(e)[:120]}")]
    if not radky:
        return [(False, f"úplnost serverové sady (scripts/miniweb_jazyk_parita.py {base}) nevrátila žádnou kontrolu")]
    return [(k.get("stav") != "MEZERA", f"serverová sada {base}: {k.get('kontrola')}" + (f" - {k.get('detail')}" if k.get("stav") == "MEZERA" and k.get("detail") else "")) for k in radky]


def _sada_nasazena(base, repo=REPO):
    """[(splneno, popis)] sada jazyka `api/jazyky/<jazyk>.json` je v BEZICIM API: `scripts/nasazeni.py --stav --json` -> `ceka` = commity, ktere API jeste nenacetlo (planovane nasazeni 0:00 / 12:30);
    pokud mezi nimi je commit se souborem sady, shop by do nasazeni ukazoval u novych voleb anglictinu (sady se ctou pri STARTU API). Kontrola, kterou nejde provest, je NESPLNENA."""
    cesta = f"api/jazyky/{base}.json"
    try:
        r = subprocess.run([sys.executable, os.path.join(repo, "scripts", "nasazeni.py"), "--stav", "--json"], capture_output=True, text=True, timeout=90, cwd=repo)
        ceka = json.loads(r.stdout).get("ceka") or []
        cekajici = []
        for c in ceka:
            g = subprocess.run(["git", "-C", repo, "diff-tree", "--no-commit-id", "--name-only", "-r", str(c.get("hash"))], capture_output=True, text=True, timeout=30)
            if cesta in g.stdout.split():
                cekajici.append(str(c.get("hash")))
    except Exception as e:                                                                  # noqa: BLE001 - brana: jakakoli chyba = nesplneno
        return [(False, f"sada {cesta} je nasazená v běžícím API - nepodařilo se ověřit (scripts/nasazeni.py --stav --json): {str(e)[:120]}")]
    if cekajici:
        return [(False, f"sada {cesta} ještě NENÍ v běžícím API: commit {', '.join(cekajici)} čeká na plánované nasazení 0:00 / 12:30 (nové volby a hlášky z něj půjdou do té doby anglicky; ručně se nerestartuje)")]
    return [(True, f"sada {cesta} je nasazená v běžícím API")]


def _podminky_jazyka(lang, repo=REPO, ref="sk", parita=None):
    """[(splneno, popis)] JAZYKOVE UPLNOSTI shopu (Robert 2026-10-07: dalsi jazykove kopie, nic nesmi mlcky spadnout na jiny jazyk): preklady frontendu (soubor existuje, vsechny klice
    a {placeholdery} jako referencni `ref`), SEO sablony, cesty hezkych adres a serverova jazykova sada konfiguratoru (jazyky mimo cs/en/sk). Bez techto veci by miniweb.js / miniweb_seo.py
    mlcky ukazaly anglictinu (i18n/en.json, sablony en, cesty en) a zakaznik by videl smisenou stranku."""
    base = (lang or "cs").split("-")[0]
    i18n = os.path.join(repo, "webapp", "miniweb", "i18n")
    d, rd = _json_soubor(os.path.join(i18n, base + ".json")), _json_soubor(os.path.join(i18n, ref + ".json"))
    out = [(isinstance(d, dict), f"překladový soubor webapp/miniweb/i18n/{base}.json existuje (bez něj by shop mlčky ukázal angličtinu)")]
    if isinstance(d, dict) and isinstance(rd, dict) and base != ref:
        chybi = [k for k in rd if k not in d]
        out.append((not chybi, f"překlady {base}.json mají všech {len(rd)} klíčů referenčního {ref}.json" + (f" - chybí {len(chybi)}: {', '.join(chybi[:6])}{', …' if len(chybi) > 6 else ''}" if chybi else "")))
        ph = lambda t: sorted(re.findall(r"\{[A-Za-z0-9_]+\}", str(t)))
        rozdil = [k for k in rd if k in d and ph(d[k]) != ph(rd[k])]
        out.append((not rozdil, f"stejné {{placeholdery}} v překladech {base}.json jako v {ref}.json" + (f" - jinak u {len(rozdil)}: {', '.join(rozdil[:6])}" if rozdil else "")))
    sab = _json_soubor(os.path.join(repo, "api", "miniweb_seo_sablony.json")) or {}
    if base not in sab:
        out.append((False, f"SEO šablony pro jazyk {base} jsou v api/miniweb_seo_sablony.json (bez nich by se použily anglické)"))
    elif base != ref and isinstance(sab.get(ref), dict) and isinstance(sab.get(base), dict):
        chybi = _chybejici_klice(sab[ref], sab[base])
        out.append((not chybi, f"SEO šablony {base} mají všechny sekce a klíče jako {ref}" + (f" - chybí {len(chybi)}: {', '.join(chybi[:6])}" if chybi else "")))
    out.append((base in _paths_jazyka(repo), f"cesty hezkých adres jazyka {base} jsou v api/miniweb_seo.py (PATHS; bez nich by shop dostal anglické /category/, /product/)"))
    if base not in ("cs", "en", "sk"):
        sada = os.path.isfile(os.path.join(repo, "api", "jazyky", base + ".json"))
        out.append((sada, f"serverová jazyková sada api/jazyky/{base}.json (štítky a hlášky konfigurátoru; bez ní by se vydávala čeština)"))
        if parita is None and os.path.abspath(repo) == os.path.abspath(REPO):                  # ostry beh; testy nad umelym repem predaji vlastni `parita` nebo ji nepouziji
            parita = _parita_server
        if sada and parita is not None:
            out += parita(base, ref)                                                        # sada je neuplna (nova volba/hlaska v kodu) -> shop by ukazal anglictinu
    return out


def _varovani_jazyka(lang, repo=REPO, nasazeno=None):
    """[text] NEZAVAZNA upozorneni pri go-live jazyka mimo cs/en/sk: sada `api/jazyky/<jazyk>.json` je v repu, ale API ji jeste nenacetlo (commit ceka na planovane nasazeni 0:00 / 12:30; sady se ctou
    pri startu API) - nove volby/hlasky z posledniho commitu by do nasazeni sly anglicky. Neblokuje (rozhodnuti o rychlosti vs. uplnosti je na provozovateli; rucni nasazeni jen na Robertovo slovo)."""
    base = (lang or "cs").split("-")[0]
    if base in ("cs", "en", "sk") or not os.path.isfile(os.path.join(repo, "api", "jazyky", base + ".json")):
        return []
    if nasazeno is None and os.path.abspath(repo) == os.path.abspath(REPO):
        nasazeno = _sada_nasazena
    return [popis for ok, popis in (nasazeno(base) if nasazeno else []) if not ok]


def _podminky_spusteni(cur, sf, shop, mw, pozadovane=REQUIRED_DOCS):
    """[(splneno, popis)] podminek spusteni shopu (viz hlavicka)."""
    lang = mw._clean_lang(sf["lang"]) or "cs"
    langs = [lang] + ([lang.split("-")[0]] if "-" in lang else [])
    ctx = {"shop": {"family": shop["family"], "currency": None, "price_mode": "hidden"}, "langs": langs, "statuses": ["approved"], "include_draft": False}
    produkty, kategorie = mw._visible_products(cur, ctx)
    dokumenty = {d["kind"] for d in mw._documents(cur, ctx)} if hasattr(mw, "_documents") else None
    vhost = os.path.join(NGINX_ENABLED, f"miniweb-{sf['primary_domain']}")
    out = [(os.path.exists(vhost), f"doména je připojená: nginx vhost {vhost} je nainstalovaný (scripts/miniweb_nginx_install.sh {sf['primary_domain']})"),
           (bool((shop["countries"] or "").strip()), "shop má země dodání (--countries)"),
           (bool(shop["inquiry_enabled"]), "shop přijímá poptávky (--inquiry on)"),
           (len(kategorie) >= 1 and len(produkty) >= 1, f"v jazyce {lang} je aspoň jedna veřejná kategorie a produkt, tj. schválený text (teď kategorií {len(kategorie)}, produktů {len(produkty)})")]
    try:
        kontakt = json.loads(shop["contact_json"]) if isinstance(shop["contact_json"], (str, bytes)) else (shop["contact_json"] or {})
    except ValueError:
        kontakt = {}
    if isinstance(kontakt, dict) and kontakt.get("use_company") is True:
        import company_info
        out.append((bool((company_info._get_company_info(cur).get("phone") or "").strip()), "telefon společnosti je vyplněný v nastavení společnosti (kontakt shopu z nastavení společnosti)"))
    s = __import__("documents").SUPPLIER                                           # legal.seller: zakonna identifikace prodejce, stejny zdroj jako GET /api/miniweb/legal
    chybi = [k for k in ("name", "street", "city", "ico", "dic") if not (s.get(k) or "").strip()]
    out.append((not chybi, "identifikace prodejce (legal.seller: název, adresa, IČO, DIČ) je úplná" + (f" - chybí {', '.join(chybi)}" if chybi else "")))
    for kind in pozadovane:
        out.append((dokumenty is not None and kind in dokumenty, f"schválený právní dokument: {DOC_LABELS[kind]} ({kind}, {lang})" + ("" if dokumenty is not None else " - modul zatím dokumenty nepodporuje")))
    return out


def _zmena_stavu(conn, args, mw):
    pozadovane = REQUIRED_DOCS
    if args.require_docs:
        pozadovane = tuple(x.strip() for x in args.require_docs.split(",") if x.strip())
        if not pozadovane or any(x not in DOC_LABELS for x in pozadovane):
            print(f"CHYBA    --require-docs: čárkou oddělené druhy z {', '.join(DOC_LABELS)}")
            return 2
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM car_storefronts WHERE slug=%s", (args.slug,))
        sf = cur.fetchone()
        cur.execute("SELECT * FROM miniweb_shops WHERE storefront_id=%s", (sf["id"],)) if sf else None
        shop = cur.fetchone() if sf else None
        if sf is None or shop is None:
            conn.rollback()
            print(f"CHYBA    shop {args.slug} neexistuje (storefront a řádek shopu se zakládají tímto skriptem bez --go-live)")
            return 2
        cil = "live" if args.go_live else "draft"
        if sf["status"] == cil:
            conn.rollback()
            print(f"== beze změny: {args.slug} je už ve stavu {cil}")
            return 0
        if args.go_live:
            podminky = _podminky_spusteni(cur, sf, shop, mw, pozadovane)
            for ok, popis in podminky:
                print(("  ANO   " if ok else "  NE    ") + popis)
            jazyk = _podminky_jazyka(mw._clean_lang(sf["lang"]) or "cs")                           # jazykova uplnost (preklady, SEO, cesty, serverova sada) - vlastni predpona, aby se nepocitala mezi puvodni podminky
            for ok, popis in jazyk:
                print(("  jazyk ANO   " if ok else "  jazyk NE    ") + popis)
            podminky = podminky + jazyk
            if not all(ok for ok, _ in podminky):
                conn.rollback()
                print("== NESPUŠTĚNO: nejsou splněné podmínky výše (nic se nezměnilo)")
                return 2
            for varovani in _varovani_jazyka(mw._clean_lang(sf["lang"]) or "cs"):
                print("  POZOR " + varovani)
            print(f"  POZOR DNS domény {sf['primary_domain']} (Cloudflare zóna, A záznamy) skript neověří: scripts/miniweb_domena.py overit {sf['primary_domain']}")
        if not args.apply:
            conn.rollback()
            print(f"== NÁHLED (nic se nezapsalo): {args.slug} by přešel ze stavu {sf['status']} do {cil}")
            return 0
        cur.execute("UPDATE car_storefronts SET status=%s WHERE id=%s AND status=%s", (cil, sf["id"], sf["status"]))
        zmeneno = cur.rowcount
    conn.commit()
    print(f"== {'SPUŠTĚNO' if args.go_live else 'VRÁCENO DO KONCEPTU'}: {args.slug} je ve stavu {cil}" if zmeneno == 1 else "== NEZMĚNĚNO (stav se mezitím změnil)")
    return 0 if zmeneno == 1 else 2


def main(argv=None, conn=None):
    ap = argparse.ArgumentParser(description="Založení a úprava mini-shopu (storefront + řádek miniweb_shops)")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--host")
    ap.add_argument("--lang")
    ap.add_argument("--name")
    ap.add_argument("--family")
    ap.add_argument("--price-mode", choices=("hidden", "indicative", "shown"))
    ap.add_argument("--margin-pct", type=float, help="marže v %% k přepočtu Kč→EUR (cena se bez ní nevydává)")
    ap.add_argument("--eur-rate", type=float, help="ruční kurz Kč za 1 EUR, 0 = živý kurz Fio (výchozí)")
    ap.add_argument("--currency")
    ap.add_argument("--locale")
    ap.add_argument("--accent")
    ap.add_argument("--countries")
    ap.add_argument("--phone")
    ap.add_argument("--hours")
    ap.add_argument("--inquiry", choices=("on", "off"))
    ap.add_argument("--orders", choices=("on", "off"), help="kosik a objednavka mini-shopu (vyzaduje migraci orders_enabled)")
    ap.add_argument("--contact-from-company", choices=("on", "off"))
    ap.add_argument("--require-docs")
    ap.add_argument("--go-live", action="store_true")
    ap.add_argument("--take-offline", action="store_true")
    ap.add_argument("--apply", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    if conn is None:
        sys.path.insert(0, os.path.join(REPO, "api"))
        import app  # noqa: E402
        conn = app.get_conn()
    import miniweb as mw
    import dealers
    if args.go_live or args.take_offline:
        if args.go_live and args.take_offline:
            print("CHYBA    --go-live a --take-offline nejde dohromady")
            return 2
        return _zmena_stavu(conn, args, mw)
    chyby = []
    if not _SLUG_RE.match(args.slug):
        chyby.append("slug: malá písmena, číslice a pomlčky, 3 až 100 znaků")
    host = args.host.strip().lower() if args.host else None
    if host and not _HOST_RE.match(host):
        chyby.append("host: název domény malými písmeny bez protokolu a cesty (baliace-stoly.top)")
    lang = mw._clean_lang(args.lang) if args.lang else None
    if args.lang and lang != args.lang:
        chyby.append("lang: kód jazyka malými písmeny (sk, en, de, en-ie)")
    pole, ch = _pole(args, mw, dealers)
    chyby += ch
    for popis, hodnota in (("slug", args.slug), ("host", host), ("name", args.name), ("telefon", args.phone), ("doba", args.hours)):
        if hodnota and dealers._brand_hit(hodnota):
            chyby.append(f"{popis}: obsahuje značku (mini-shop je bez značky)")
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM car_storefronts WHERE slug=%s", (args.slug,))
        sf = cur.fetchone()
        if sf is None:
            if not host or not lang:
                chyby.append("storefront neexistuje: pro jeho založení je potřeba --host a --lang")
            else:
                cur.execute("SELECT slug FROM car_storefronts WHERE primary_domain=%s", (host,))
                jiny = cur.fetchone()
                cur.execute("SELECT storefront_id FROM storefront_hosts WHERE host=%s", (host,))
                alias = cur.fetchone()
                if jiny or alias:
                    chyby.append(f"host {host} už používá jiný storefront")
        else:
            if host and host != sf["primary_domain"]:
                chyby.append(f"storefront {args.slug} má doménu {sf['primary_domain']}, ne {host}")
            if lang and lang != sf["lang"]:
                chyby.append(f"storefront {args.slug} má jazyk {sf['lang']}, ne {lang}")
        radek = None
        if sf is not None:
            cur.execute("SELECT * FROM miniweb_shops WHERE storefront_id=%s", (sf["id"],))
            radek = cur.fetchone()
        if radek is None and "family" not in pole:
            chyby.append("nový shop: --family je povinná (rodina shopu, např. packstations)")
        if chyby:
            conn.rollback()
            print("== CHYBA (nic se nezapsalo)")
            for c in chyby:
                print("CHYBA    " + c)
            return 2
        plan = []
        if sf is None:
            plan.append(f"vytvořit storefront {args.slug}: doména {host}, jazyk {lang}, stav draft")
        sloupce = {k: v for k, v in pole.items() if not k.startswith("_")}
        if "_contact" in pole or "_use_company" in pole:
            stary = {}
            if radek is not None and radek.get("contact_json"):
                try:
                    stary = json.loads(radek["contact_json"]) if isinstance(radek["contact_json"], str) else dict(radek["contact_json"])
                except (TypeError, ValueError):
                    stary = {}
            novy = {**{k: v for k, v in stary.items() if k != "email"}, **pole.get("_contact", {})}
            if "_use_company" in pole:
                novy.pop("use_company", None)
                if pole["_use_company"]:
                    novy["use_company"] = True
            sloupce["contact_json"] = json.dumps(novy, ensure_ascii=False)
        if radek is None:
            plan.append("vytvořit řádek shopu: " + ", ".join(f"{k}={v}" for k, v in sloupce.items()))
        else:
            zmeny = {k: v for k, v in sloupce.items() if str(radek.get(k)) != str(v) and not (k == "contact_json" and json.loads(radek[k] or "null") == json.loads(v))}
            plan.append("upravit řádek shopu: " + (", ".join(f"{k}: {radek.get(k)} → {v}" for k, v in zmeny.items()) if zmeny else "beze změny"))
            sloupce = zmeny
        if not args.apply:
            conn.rollback()
            print("== NÁHLED (nic se nezapsalo)")
            for p_ in plan:
                print("  " + p_)
            return 0
        if sf is None:
            cur.execute("INSERT INTO car_storefronts (name, slug, kind, primary_domain, template_id, origin_cert_group, status, lang) VALUES (%s,%s,'miniweb',%s,'default',%s,'draft',%s)",
                        ((args.name or args.slug)[:150], args.slug, host, CERT_GROUP, lang))
            sf_id = cur.lastrowid
        else:
            sf_id = sf["id"]
        if radek is None:
            cols = ["storefront_id"] + list(sloupce)
            cur.execute(f"INSERT INTO miniweb_shops ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})", [sf_id] + list(sloupce.values()))
        elif sloupce:
            cur.execute(f"UPDATE miniweb_shops SET {', '.join(k + '=%s' for k in sloupce)} WHERE storefront_id=%s", list(sloupce.values()) + [sf_id])
    conn.commit()
    print("== ZAPSÁNO (storefront zůstává ve stavu draft)")
    for p_ in plan:
        print("  " + p_)
    return 0


if __name__ == "__main__":
    sys.exit(main())
