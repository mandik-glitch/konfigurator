#!/usr/bin/env python3
"""Prepocet prodejni ceny profilu (shop_products.price_czk_placeholder)
primo z autentizovane ceny na doguskalip.com.tr ("List Price"), misto
puvodni domnenky/rucniho zadani.

Robert 2026-08-09 ("oprav ceny v eshopu vcera se to nejak pokazilo,
proste cenu z Dogus x 22 x koeficient = merna cena za 1 m v Kc jako
nase prodejni cena") + UPRESNENO 2026-08-10 ("1x tydne se nacte
kompletne novy cenik z Dogus, ulozi se cena USD u nas aby ji jen admin
videl na kazde karte. Automaticky se okamzite podle koeficientu a podle
rovnice cena dogus x 3 x kurz = cena za 1ks tyce 3m, s kurzem Fio banka
devize prodej. zaokrouhleno na cele koruny"):

    cena_za_m_czk = dogus_list_price_usd * kurz_fio_prodej   # List Price uz JE za 1 m, NEDELIT delkou tyce
                                                              # (L_mm sloupec je jen informativni delka
                                                              # standardni tyce na sklade, ne jednotka ceny -
                                                              # Robert: "ty debile, opakuju ze cena na Dogus
                                                              # je za 1m", puvodni deleni L_mm/1000 bylo chybne)
    cena_final_czk = round(cena_za_m_czk * coefficient * 3)  # nase jednotka "1 ks = 3000 mm",
                                                              # zaokrouhleno na cele koruny (Robert 2026-08-10)

Kurz USD/CZK (`fetch_fio_usd_czk_sell_rate` nize) se stahuje ZIVE pri
kazdem behu z verejne dostupne tabulky "Devizove kurzy" na fio.cz
(sloupec "Prodej" - kurz, za ktery banka USD PRODAVA, presne podle
Robertova zadani "s kurzem Fio banka devize prodej"). Puvodni verze
skriptu mela kurz nastaveny natvrdo na 22.0 (docasne, nez bylo jasne
odkud kurz brat) - ted uz NEexistuje zadny hardcoded fallback: kdyz se
kurz nepodari stahnout, skript rovnou selze (radeji zadna aktualizace
cen nez cena spocitana se spatnym/starym kurzem).

List Price v USD/m i pouzity kurz se navic ukladaji do
shop_products.dogus_list_price_usd / dogus_price_rate_used (viz
sql/2026-08-10_dogus_price_usd_column.sql) - admin je pak vidi primo na
skladove karte produktu (zalozka Cenotvorba, webapp/admin.html), i kdyz
sam s nimi nic nedela - jen transparentnost, at je jasne z čeho se
vysledna cena spocitala.

Koeficient (content_categories.dogus_price_coefficient) - Robert:
"vypln zatim vsude hodnotu 1, potom si to upravim" - tenhle skript sam
koeficient nemeni, jen ho CTE z DB (musi byt uz nastaveny na 1, viz
doprovodny UPDATE pred spustenim skriptu s --apply).

Cena se hleda v prihlasene strance produktu (shop_products.dogus_url)
v radku tabulky, kde "Stock Code" == shop_products.dogus_stock_code
(jedna stranka Dogus muze mit vice variant/kodu v tabulce).

Bez --apply jde o READ-ONLY dry-run (jen vypise, co by se zapsalo) -
kurz se ale i tak stahuje živě (potreba pro vypis nahledu vysledku).

--- Ne-profilove polozky (spojovaci material, kryty, spojky...) ---
Robert 2026-08-10 ("cena se ma prepocitavat i na ne-profily tzn na
kompletni polozky z Dogus" + upresneno "ostatni polozka se nasobi 1x
resp zustanou jak sou, jen x kurz a x koeficient" + "Vzorec pro
ne-profily: zaokrouhleni ceny vzdy nahoru"):

    cena_final_czk = ceil(dogus_list_price_usd_za_ks * kurz_fio_prodej * coefficient)

ZAOKROUHLENI NAHORU (math.ceil), NE matematicke round() jako u profilu
- i cena o 0.01 Kc vyssi nez cele cislo se zaokrouhli na dalsi celou
korunu nahoru.

ZADNE x3 - to plati JEN pro profily (tyc 3000 mm). Dogus u kusoveho
zbozi (matice, spojky, kryty...) uvadi List Price uz RUCNE za 1 kus,
ne za metr (overeno 2026-08-10 na realne strance - "Round Head Washer
Nut" 0,04 USD/ks, "30x30 Plain Corner Joint" 0,64 USD/ks).

Stranka kusoveho zbozi ma JINOU HTML strukturu tabulky nez profily
(sloupce Stock Code/Stock Name/B/D/Material/Weight misto Stock Code/L,
ASP.NET repeater "rptAttributeDataList") - `parse_price_for_code`
(profily) na ni nenajde nic, proto samostatny
`parse_nonprofile_price_for_code` nize, ktery cte
hdnSelectProductMCode_N (kod) + ltrFiyatTutari_N (cena) podle indexu N
- robustnejsi nez parsovani <tr>, protoze nezavisi na presnem stylu
bunky.
"""
import argparse
import http.cookiejar
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, "/opt/konfigurator/api")

BASE = "https://en.doguskalip.com.tr"
UA = "Mozilla/5.0 (compatible; LogimanKonfiguratorPairingSync/1.0; +https://logiman.cz)"
VIEWSTATE_RE = re.compile(r'id="__VIEWSTATE" value="([^"]*)"')
VIEWSTATEGEN_RE = re.compile(r'id="__VIEWSTATEGENERATOR" value="([^"]*)"')
REQUEST_DELAY_S = 0.6

# Robert 2026-08-10 ("s kurzem Fio banka devize prodej") - verejna
# tabulka "Devizove kurzy" (sloupce Nakup/Prodej), zadne prihlaseni
# netreba. Overeno rucne 2026-08-10 (curl), stejna tabulka je i v
# paticce vetsiny stranek fio.cz jako HTML fragment "barbox-listek".
#
# Vytazeno do api/fio_rate.py (bot16, 2026-09-24, pravidlo 52 - Robert
# pres bot3, "prepocitanou cenu USD s aktualnim kurzem FIO devize
# prodej" pro novy admin sloupec v Cenach profilu) - JEDNO misto pravdy
# pro definici "devize prodej", sdilene timhle tydennim skriptem i novym
# admin live-rate endpointem (api/admin_profily.py), aby se nikdy
# nerozjely dve nezavisle implementace parsovani fio.cz stranky.
from fio_rate import FIO_RATE_URL, fetch_fio_usd_czk_sell_rate  # noqa: F401


REQUIRED_ENV_KEYS = ("DOGUS_LOGIN_EMAIL", "DOGUS_LOGIN_PASSWORD", "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME")


def load_env():
    """Nejdriv os.environ (systemd EnvironmentFile= uz .env nacte jako
    root PRED dropnutim na User=www-data, takze www-data samo o sobe
    .env citat nepotrebuje/nemuze - je 0600 root). Rucni spusteni (root
    v terminalu) fallbackuje na primy parse souboru."""
    if all(k in os.environ for k in REQUIRED_ENV_KEYS):
        return dict(os.environ)
    env = {}
    for line in open("/opt/konfigurator/api/.env"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    return env


def make_session(email, password):
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    req = urllib.request.Request(f"{BASE}/giris-yap", headers={"User-Agent": UA})
    html = opener.open(req, timeout=20).read().decode("utf-8", errors="ignore")
    viewstate = VIEWSTATE_RE.search(html).group(1)
    viewstategen = VIEWSTATEGEN_RE.search(html).group(1)
    form = {
        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$lnkLogin", "__EVENTARGUMENT": "", "__LASTFOCUS": "",
        "__VIEWSTATE": viewstate, "__VIEWSTATEGENERATOR": viewstategen,
        "ctl00$ContentPlaceHolder1$txtEposta": email,
        "ctl00$ContentPlaceHolder1$txtPass": password,
    }
    data = urllib.parse.urlencode(form).encode()
    req2 = urllib.request.Request(f"{BASE}/giris-yap", data=data, headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": f"{BASE}/giris-yap",
    })
    opener.open(req2, timeout=20).read()
    time.sleep(REQUEST_DELAY_S)
    if not any(c.name == "_famname" for c in cj):
        raise RuntimeError("Přihlášení na doguskalip se nezdařilo (chybí cookie _famname).")
    return opener


def fetch(opener, url):
    # Nektere dogus_url obsahuji ne-ASCII znaky ve slugu (napr. "ø28-...")
    # - http.client vyzaduje ciste ASCII request-line, jinak UnicodeEncodeError
    # (stejny bug jako drive v 2026-08-08_dogus_pairing_crawl.py::fetch(),
    # zjisteno 2026-08-11 pri prepoctu ceny nove kategorie "Dynamic Shelving
    # Systems" - vsechny jeji Ø28 produkty timhle tise selhavaly).
    parts = urllib.parse.urlsplit(url)
    safe_path = urllib.parse.quote(parts.path, safe="/-_.~")
    url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, safe_path, parts.query, parts.fragment))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    html = opener.open(req, timeout=20).read().decode("utf-8", errors="ignore")
    time.sleep(REQUEST_DELAY_S)
    return html


ROW_RE = re.compile(
    r"<tr>\s*<td style='text-align: center;'>(?P<code>[^<]+)</td>.*?"
    r"<td style='text-align:center;'>(?P<L>\d+)</td>.*?"
    r'ltrFiyatTutari_\d+">(?P<price>[\d.,]+)\s*USD',
    re.S,
)


def parse_price_for_code(html, stock_code):
    """Vraci (list_price_usd, L_mm) pro dany Stock Code z tabulky variant
    na strance, nebo None kdyz se kod v tabulce nenajde."""
    for m in ROW_RE.finditer(html):
        if m.group("code").strip() == stock_code:
            price_str = m.group("price").replace(".", "").replace(",", ".")
            return float(price_str), int(m.group("L"))
    return None


NONPROFILE_CODE_RE = re.compile(r'hdnSelectProductMCode_(\d+)"\s+value="([^"]*)"')
NONPROFILE_PRICE_RE = re.compile(r'ltrFiyatTutari_(\d+)">([\d.,]+)\s*USD')


def parse_nonprofile_price_for_code(html, stock_code):
    """Vraci list_price_usd (za 1 KS, ne za metr) pro dany Stock Code na
    strance kusoveho zbozi (spojovaci material, kryty...), nebo None kdyz
    se kod na strance nenajde. Jina HTML struktura nez profily (viz
    hlavicka souboru) - parujeme podle stejneho indexu N mezi
    hdnSelectProductMCode_N (kod) a ltrFiyatTutari_N (cena), misto
    parsovani <tr>/<td> struktury (ktera se mezi profily a kusovym
    zbozim lisi)."""
    codes = dict(NONPROFILE_CODE_RE.findall(html))
    prices = dict(NONPROFILE_PRICE_RE.findall(html))
    for idx, code in codes.items():
        if code.strip() == stock_code and idx in prices:
            price_str = prices[idx].replace(".", "").replace(",", ".")
            return float(price_str)
    return None


# HISTORIE ROZHODOVACIHO PRAVIDLA (zamerne ponechano, at uz to nikdo
# neopakuje - dva ruzne pristupy uz padly):
#
# 1) Robert primo, 2026-09-15, pres bot3: "v nazvu stačí slovo lišta",
#    "zadna dalsi podminka" - VSECHNY produkty s "lišta" v nazvu se
#    pocitaly "za metr" (x3). PADLO 2026-09-24 (bot5): "Krycí lišta
#    drážky 6" (ma "lišta") dostala x3 -> 18 Kc, "Těsnění drážky -
#    drážka 6" (nema "lišta") dostalo x1 -> 7 Kc, PRI IDENTICKE dogusi
#    cene 0,23 USD - jmenna heuristika rozsypala celou kategorii 196.
# 2) bot5/bot3, jeste 2026-09-24, pokus o zivy signal ze stranky
#    (hdnShowStockQuantityUnit/hdnStockQuantityUnitValue). PADLO TAKY
#    (bot3, overeno primo): to pole u casti sortimentu kategorie 196
#    (těsnění na sklo, těsnicí pásky/kanálky, krycí guma) vraci 0 nebo
#    na strance vubec neni (jina sablona), presto je Robert vyslovne
#    oznacil za metraz. Pole je nespolehlive jako OBECNE kriterium -
#    funguje jen u cásti sortimentu, ne u vsech "profile-seals" stranek.
#
# FINALNI PRAVIDLO (Robert pres bot3, 2026-09-24, NEODVOZUJE SE UZ VUBEC
# - "teď si určíme pevně co je na kusy a co je na tyče 3m"): pevna
# klasifikace podle DOGUS SEKCE, ulozena primo u kategorie
# (content_categories.dogus_sale_unit, viz
# sql/2026-09-24e_content_categories_dogus_sale_unit.sql). Skript ji uz
# jen CTE (JOIN v dotazu nize), nikdy nedopocitava.
#   tyc_3m  - Dogus skupina 9 (6/8/10-slot, surface-coating, conveyor,
#             special-series) + 215 Vodici hlinikove profily + 192
#             Hlinikove profily Dynamic (Robert vyslovne potvrdil oba
#             mimo skupinu 9 jako tyce). round(usd x kurz x koef x 3).
#   metraz  - Dogus sekce 84 "profile-seals" (nase kategorie 196).
#             usd x kurz x koef, BEZ x3, unit='m'.
#   kus     - vsechno ostatni (DEFAULT v DB). ceil(usd x kurz x koef).
#
# Parser (ROW_RE profil-tabulka vs. NONPROFILE_*_RE) zustava NEZAVISLY
# na tomhle - je to jen otazka, JAKA HTML struktura ma stranka (viz
# smycka v main(), zkousi se profil-parser prvni, pak nonprofil).
#
# ZAOKROUHLENI - Robert, 2026-09-24, FINALNI ("celé koruny vždy
# nahoru"), PLATI PRO VSECHNY TRI SKUPINY STEJNE (sjednoceno vyslovne
# kvuli necem, co mu vadilo - nekonzistence naprič kategoriemi). Tohle
# NAHRAZUJE puvodni pravidlo z 2026-08-10 (Robert tehdy: profily
# "zaokrouhleno na cele koruny" pres matematicke round(), ne-profily
# math.ceil() - dva RUZNE zpusoby zaokrouhleni vedle sebe). Nikdy
# nevracet round() u profilove vetve zpet - je to zamerna zmena, ne
# chyba. Ponechano jako sdilena funkce (drive kvuli "jeste neni
# rozhodnuto", ted uz jen at je zaokrouhleni na JEDNOM miste pro
# pripad, ze by se PDF/kartova cena nekdy chteli lisit).
def zaokrouhli_cenu(cena_bez_zaokrouhleni):
    return math.ceil(cena_bez_zaokrouhleni)


# TYC JINE DELKY (bot5, 2026-10-07; Robert pres bot9: "prodavat CELOU TYC, cena = USD/m x delka tyce x kurz x koeficient nahoru"): u dilu s dogus_stock_unit_value mimo 0 (kus) a 3000 (tyc 3 m) -
# Dogus uvadi delku tyce v mm (napr. valeckova draha zinkova 6000 / 2500 mm) a List Price je za 1 m, takze cena kusu = USD/m x (delka/1000) x kurz x koeficient, nahoru. Kategorie zustava "kus"
# (smisena kategorie: 8 kusovych dilu + 2 tyce), rozhoduje hodnota u produktu.
def efektivni_jednotka(sale_unit, stock_unit_value):
    if sale_unit == "kus" and stock_unit_value not in (None, 0, 3000):
        return "tyc_delka"
    return sale_unit


def cena_je_platna(usd):
    """True jen pro kladnou cenu v USD; None / 0 / zaporna (u Dogusu 0,00 USD = na dotaz) se nikdy neprepocte na cenu karty."""
    return usd is not None and usd > 0


def spocti_cenu(sale_unit, usd, fio_rate, coef, stock_unit_value=None):
    """-> (cena Kc nahoru, popis jednotky). `sale_unit` uz po efektivni_jednotka()."""
    if sale_unit == "tyc_3m":
        return zaokrouhli_cenu(usd * fio_rate * coef * 3.0), "USD/m (tyč 3m, ×3)"
    if sale_unit == "metraz":
        return zaokrouhli_cenu(usd * fio_rate * coef), "USD/m (metráž)"
    if sale_unit == "tyc_delka":
        return zaokrouhli_cenu(usd * (stock_unit_value / 1000.0) * fio_rate * coef), f"USD/m (tyč {stock_unit_value / 1000.0:g} m, ×{stock_unit_value / 1000.0:g})"
    return zaokrouhli_cenu(usd * fio_rate * coef), "USD/ks"


def vyber_produktu(cur, ids=None, vcetne_neaktivnich=False):
    """Produkty k prepoctu ceny. Nocni beh: jen aktivni. S ids a vcetne_neaktivnich (nove karty po importu, jeste neaktivni) i neaktivni - cena je pak hotova uz pri aktivaci."""
    podminka = "p.is_archived=0 AND p.dogus_url IS NOT NULL" + ("" if (ids and vcetne_neaktivnich) else " AND p.active=1")
    cur.execute(
        "SELECT p.id, p.sku, p.name, p.category_id, p.dogus_url, p.dogus_stock_code, p.price_czk_placeholder, "
        "p.cfg_dily_id, p.is_profile_material, p.dogus_stock_unit_value, c.dogus_price_coefficient, c.dogus_sale_unit "
        "FROM shop_products p JOIN content_categories c ON c.id = p.category_id "
        f"WHERE {podminka} "
        "ORDER BY c.dogus_sale_unit, p.id"
    )
    products = cur.fetchall()
    if ids:
        wanted = {int(x) for x in str(ids).split(",") if x.strip()}
        products = [p for p in products if p["id"] in wanted]
    return products


def get_db_conn(env):
    import pymysql
    return pymysql.connect(
        host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
        password=env["DB_PASSWORD"], database=env["DB_NAME"], charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--apply", action="store_true", help="Skutecne zapsat do DB. Bez teto volby jen dry-run.")
    ap.add_argument("--backup", default=None, help="Cesta pro JSON zalohu puvodnich cen (jen s --apply).")
    ap.add_argument("--ids", default=None, help="Jen produkty s temito id (carkou oddelene), napr. nove karty hned po importu; bez teto volby vsechny (nocni beh, beze zmeny).")
    ap.add_argument("--vcetne-neaktivnich", action="store_true", help="S --ids: zahrnout i NEAKTIVNI karty (cena se spocita pred aktivaci); nocni beh zustava jen u aktivnich.")
    args = ap.parse_args()

    env = load_env()
    conn = get_db_conn(env)
    cur = conn.cursor()
    # Robert 2026-08-10 ("cena se ma prepocitavat i na ne-profily tzn na
    # kompletni polozky z Dogus") - puvodne jen is_profile_material=1
    # (profily, tyc na 3 m), ted VSECHNY produkty spárované s Dogus.
    # is_profile_material se bere s sebou uz JEN kvuli hlaseni neshody
    # (viz bod 4 nize, mismatch_is_profile_material) - o tom, kterou
    # vetev pouzit, od 2026-09-24 (FINALNI verze) rozhoduje vyhradne
    # c.dogus_sale_unit (viz komentar u zaokrouhli_cenu_za_metr vyse).
    products = vyber_produktu(cur, args.ids, args.vcetne_neaktivnich)
    if args.limit:
        products = products[: args.limit]
    print(f"Produktu ke zpracovani: {len(products)}", file=sys.stderr)

    # Zadny hardcoded fallback (Robert 2026-08-10) - kdyz se kurz nestahne,
    # cely beh selze driv, nez by se cokoli spocitalo/zapsalo se spatnym
    # kurzem.
    fio_rate = fetch_fio_usd_czk_sell_rate()
    print(f"Kurz Fio banka USD/CZK (prodej): {fio_rate}", file=sys.stderr)

    opener = make_session(env["DOGUS_LOGIN_EMAIL"], env["DOGUS_LOGIN_PASSWORD"])
    print("Přihlášení na doguskalip OK.", file=sys.stderr)

    results, errors = [], []
    for i, p in enumerate(products, 1):
        coef = float(p["dogus_price_coefficient"]) if p["dogus_price_coefficient"] is not None else None
        if coef is None:
            errors.append({"id": p["id"], "sku": p["sku"], "error": "kategorie nema dogus_price_coefficient nastaveny"})
            print(f"[{i}/{len(products)}] {p['sku']}: PRESKOCENO (chybi koeficient kategorie)", file=sys.stderr)
            continue
        try:
            html = fetch(opener, p["dogus_url"])
        except Exception as e:
            errors.append({"id": p["id"], "sku": p["sku"], "error": f"fetch: {e}"})
            print(f"[{i}/{len(products)}] {p['sku']}: CHYBA fetch {e}", file=sys.stderr)
            continue

        is_profile = bool(p["is_profile_material"])
        sale_unit = efektivni_jednotka(p["dogus_sale_unit"], p["dogus_stock_unit_value"])  # 'tyc_3m' / 'metraz' / 'kus' (pevne z DB) nebo 'tyc_delka' (tyc 6000/2500 mm podle hodnoty u produktu)
        # Parser je cistě otazka HTML struktury stranky, NEZAVISLA na
        # sale_unit - zkus profilovy ROW_RE prvni (typicky uspeje u
        # tyc_3m), pak ne-profilovy (typicky uspeje u metraz/kus).
        parsed = parse_price_for_code(html, p["dogus_stock_code"])
        if parsed:
            list_price_usd, l_mm = parsed
            matched_via = "profil (ROW_RE)"
        else:
            list_price_usd = parse_nonprofile_price_for_code(html, p["dogus_stock_code"])
            if list_price_usd is None:
                errors.append({"id": p["id"], "sku": p["sku"], "error": "stock code nenalezen v zadnem parseru (profil ani ne-profil)"})
                print(f"[{i}/{len(products)}] {p['sku']}: NENALEZENO v zadnem parseru", file=sys.stderr)
                continue
            l_mm = None
            matched_via = "ne-profil"

        if not cena_je_platna(list_price_usd):
            # Robert 2026-10-07 ("kde nejsou ceny, nebude aktivni produkt"): 0,00 USD = u Dogusu "na dotaz". Nezapisovat 0 Kc do (aktivni) karty - zustane puvodni cena a chyba jde do hlaseni
            # (kartu bot sam nevypina, pravidlo 54).
            errors.append({"id": p["id"], "sku": p["sku"], "error": f"Dogus cena {list_price_usd} USD (na dotaz) - cena karty ponechana ({p['price_czk_placeholder']})"})
            print(f"[{i}/{len(products)}] {p['sku']}: PRESKOCENO (Dogus cena {list_price_usd} USD = na dotaz, ponechana cena {p['price_czk_placeholder']})", file=sys.stderr)
            continue

        new_price_czk, unit = spocti_cenu(sale_unit, list_price_usd, fio_rate, coef, p["dogus_stock_unit_value"])

        # bot3, 2026-09-24, bod 4: is_profile_material se z tohohle skriptu
        # NIKDY nezapisuje (kategorizace neni nase rozhodnuti, dogus_sale_unit
        # se meni jen rucne pres SQL po Robertove schvaleni) - jen se hlasi
        # nesoulad mezi sale_unit a is_profile_material (napr. tyc_3m by mel
        # mit is_profile_material=1, metraz/kus by ho mit NEMELY).
        expect_profile = sale_unit == "tyc_3m"
        mismatch = expect_profile != is_profile

        results.append({
            "id": p["id"], "sku": p["sku"], "name": p["name"], "cfg_dily_id": p["cfg_dily_id"],
            "is_profile_material": is_profile, "dogus_sale_unit": sale_unit, "matched_via": matched_via,
            "mismatch_is_profile_material": mismatch,
            "old_price_czk": float(p["price_czk_placeholder"]) if p["price_czk_placeholder"] is not None else None,
            "list_price_usd": list_price_usd, "L_mm": l_mm, "coefficient": coef,
            "fio_rate": fio_rate, "new_price_czk": new_price_czk,
        })
        znacka_mismatch = " ⚠ NESEDÍ is_profile_material" if mismatch else ""
        print(f"[{i}/{len(products)}] {p['sku']} [{sale_unit}]: {list_price_usd} {unit} x {fio_rate} x koef {coef} "
              f"-> {new_price_czk} Kč (bylo {p['price_czk_placeholder']}) [{matched_via}]{znacka_mismatch}", file=sys.stderr)

    print(json.dumps({"ok": len(results), "errors": len(errors), "error_items": errors}, ensure_ascii=False, indent=2))

    # bot3, 2026-09-24, bod 4: souhrn PRED pripadnym zapisem - kolik cen
    # se meni, nejvetsi skoky, a seznam neshod is_profile_material vs
    # zivy signal (kategorizace se odsud nemeni, jen hlasi).
    changed = [r for r in results if r["old_price_czk"] is not None and round(r["old_price_czk"]) != r["new_price_czk"]]
    changed_sorted = sorted(changed, key=lambda r: r["new_price_czk"] - r["old_price_czk"])
    mismatches = [r for r in results if r["mismatch_is_profile_material"]]
    print(f"\n=== SOUHRN ===", file=sys.stderr)
    print(f"Zpracováno: {len(results)}, chyb: {len(errors)}, cena se mění u: {len(changed)}", file=sys.stderr)
    if changed_sorted:
        print("Největší pokles:", file=sys.stderr)
        for r in changed_sorted[:5]:
            print(f"  [{r['id']}] {r['sku']}: {r['old_price_czk']} -> {r['new_price_czk']} Kč "
                  f"({r['new_price_czk'] - r['old_price_czk']:+.0f})", file=sys.stderr)
        print("Největší nárůst:", file=sys.stderr)
        for r in changed_sorted[-5:]:
            print(f"  [{r['id']}] {r['sku']}: {r['old_price_czk']} -> {r['new_price_czk']} Kč "
                  f"({r['new_price_czk'] - r['old_price_czk']:+.0f})", file=sys.stderr)
    print(f"Neshoda dogus_sale_unit vs. is_profile_material (DB): {len(mismatches)}", file=sys.stderr)
    for r in mismatches:
        print(f"  [{r['id']}] {r['sku']}: DB is_profile_material={r['is_profile_material']}, "
              f"dogus_sale_unit={r['dogus_sale_unit']} ({r['matched_via']}) — {r['name'][:60]}", file=sys.stderr)

    if args.apply and results:
        # Zaloha AZ PO uspesnem DB zapisu, ne pred nim (bot3, 2026-09-15,
        # nalezeno pri hlaseni "cena polozky neodpovida" - viz
        # journalctl -u konfigurator-refresh-dogus-profile-prices.service
        # 2026-09-13: PermissionError pri zapisu zalohy 4x za sebou
        # (kazdy beh znovu strhnul cely ~17min scraping) shodil CELY
        # skript DRIV, nez se stihl spustit jediny UPDATE - vsech 597
        # cerstve spoctenych cen se ztratilo, DB zustala na stare cene.
        # Zaloha je diagnosticky/auditni vystup, ne predpoklad pro zapis -
        # jeji selhani uz nesmi vzit s sebou i legitimni cenovou aktualizaci.
        cfg_dily_synced = 0
        for r in results:
            # dogus_list_price_usd/dogus_price_rate_used (Robert 2026-08-10:
            # "ulozi se cena USD u nas aby ji jen admin videl na kazde
            # karte") - ciste transparentnost vypoctu na skladove karte
            # produktu (webapp/admin.html), s vysledkem samotnym nic nedela.
            cur.execute(
                "UPDATE shop_products SET price_czk_placeholder=%s, dogus_list_price_usd=%s, "
                "dogus_price_rate_used=%s, price_last_refreshed_at=NOW() WHERE id=%s",
                (r["new_price_czk"], r["list_price_usd"], r["fio_rate"], r["id"]),
            )
            # Robert ("cena za metr se ma pocitat z ceny za kus... automaticky
            # sama") - cena za metr pro 3D scenu (cfg_dily.price_czk_approx)
            # se drive prepocitavala az nocnim batchem (run_price_refresh_cli),
            # takze po tomhle zapisu chvili zaostavala. Ted se dopocita HNED,
            # ve stejne transakci - vzdy odvozena z prave zapsane ceny za kus.
            if r["cfg_dily_id"]:
                cur.execute(
                    "UPDATE cfg_dily SET price_czk_approx=%s WHERE id=%s",
                    (round(r["new_price_czk"] / 3.0, 2), r["cfg_dily_id"]),
                )
                cfg_dily_synced += 1
        conn.commit()
        print(f"Zapsáno {len(results)} nových cen do DB ({cfg_dily_synced} z nich i cena/m v cfg_dily).", file=sys.stderr)
        backup_path = args.backup or "/opt/konfigurator/backups/profile_dogus_price_recompute_backup.json"
        try:
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"Záloha zapsána do {backup_path}", file=sys.stderr)
        except OSError as e:
            # DB uz je zapsana a commitnuta (viz vyse) - chybejici zaloha je
            # jen chybejici audit stopa, ne ztraceny beh. Nezhavarovat.
            print(f"POZOR: záloha se nepodařila zapsat ({e}) - DB zápis ale proběhl v pořádku.", file=sys.stderr)
    elif not args.apply:
        print("(dry-run - nic nezapsáno, spusť s --apply pro skutečný zápis)", file=sys.stderr)

    conn.close()


if __name__ == "__main__":
    main()
