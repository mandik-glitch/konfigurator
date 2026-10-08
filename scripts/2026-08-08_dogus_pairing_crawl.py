"""
Priprava parovani naseho katalogu (shop_products) s dodavatelskym
katalogem doguskalip.com.tr - bot4, 2026-08-08.

Robert: "vymeníme vazby z logiman na doguskalip" + "nachystej strukturu
pro parovani z dogus vsech produktu, ano SKU jsou stejne protoze
nakjupujeme v doguskalip" + "zatim to neaplikuj, just prepare the
solution".

Kontext: logiman.cz je nas SOUCASNY ostry e-shop (bude nahrazen timhle
projektem, az bude hotovy pro zakazniky). doguskalip.com.tr je nas
SKUTECNY DODAVATEL - nakupujeme u nej pod jeho vlastnimi kody, takze
shop_products.sku uz DNES odpovida jeho "Stock Code" (napr. nase SKU
"2.2.001.08.3030.08" / jejich kod "2.1.011.06.25" - stejne schema).

Robert upresnil rozsah co se ma tahat (2026-08-08, druhe kolo):
  - JEN 2 hlavni obrazky z hlavni ("General Specifications") zalozky:
    render/foto (#ContentPlaceHolder1_dvProductImageList, prvni polozka
    carouselu) a schema/technicky vykres
    (#ContentPlaceHolder1_dvProductUrunList, prvni polozka) - ZADNE
    dalsi obrazky (casto duplicitni, zbytecne misto) - sdilene
    fotogalerie mezi produkty jsou budouci tema, ted NEreseno.
  - Tabulka ve spodni casti hlavni zalozky (Stock Code/Name + u profilu
    navic External Dimensions/Material/L/Ix/Iy/Wx/Wy/Area/Mass, u
    spojovacich prvku jen Material/Weight) - DULEZITA technicka data,
    parsovana OBECNE (podle hlaviček sloupcu, ne pevnych pozic), aby
    fungovala na oba typy produktu beze zmeny kodu.
  - Popisny text (pokud se v budoucnu bude tahat) MUSI byt cisty text
    bez HTML/inline stylu - viz drivejsi bug s font-size z legacy
    Shoptet importu (category.html, "stanovili jsme pravidlo typu a
    velikosti pisma"). Tenhle skript zatim zadny popisny text netaha
    (jen kod/nazev/rozmerova tabulka/2 obrazky), takze riziko rovnou
    odpada - az pribude, MUSI jit pres HTMLParser-based extrakci textu
    (jako tabulka nize), NIKDY ulozit syrove <p style="font-size:...">.

OPRAVA 2026-08-08 (Robert: "dostal na samém začátku pouze 3 URL
adresy, proč hrabeš jinam? jde nám v teto fazi pouze o tyto 3 sekce"):
puvodni discover_categories() vytahovala VSECHNY /Urunler/ odkazy ze
sitewide navigace (ta je na kazde strance webu a obsahuje UPLNE VSECHNY
produktove rodiny dogus - motory, dopravniky, CNC frezky, robotiku...),
ne jen podstrom 3 zadanych koreni (aluminium-profiles/fasteners/
fastener-accessories). Prvni plny beh tak omylem zapsal i produkty z
kategorii MIMO zadany rozsah. Oprava: BREADCRUMB_HREF_RE/is_in_scope()
overuje u KAZDE kategorie (breadcrumb je na kategorii i produktu
stejny format), ze skutecne patri pod ID 9/10/11 - viz
ALLOWED_ROOT_IDS. discover_products() vraci (products, in_scope) a
crawl_catalog() kategorie mimo rozsah preskoci (0 produktu, 0
dalsich requestu na jejich produkty). Chybne zapsane radky z prvniho
behu byly dohledany (per-produkt breadcrumb check) a vraceny zpet na
NULL (viz AGENTS_LOG.md).

Cena na doguskalip NENI verejne videt (potreba prihlaseni - Robert
slibil dodat login/heslo) - tenhle skript proto NEresi cenu, jen
STRUKTURU parovani (nas produkt <-> jejich URL/kod/obrazky/tabulka).
Az bude prihlaseni k dispozici, pujde postavit samostatny
scrape_doguskalip_price(url, code, session) analogicky k existujicimu
scrape_logiman_product_price() v api/app.py. Koeficient pro prepocet
Dogus ceny (USD) na nasi prodejni cenu (Kc) - zvlast pro kazdou
kategorii - je samostatny navrh, viz sql/2026-08-08_dogus_pairing.sql.

Vuci doguskalip.com.tr je skript VZDY jen READ-ONLY (jen GET, zadne
prihlaseni, zadny kosik). Vuci nasi DB je READ-ONLY (jen SELECT),
DOKUD neni zadana volba --apply - pak zapise jen presne SKU-matchnute
radky (dogus_url/dogus_stock_code/dogus_image_*/product_specs_json/
dogus_matched_at), nic jineho (zadny zasah do price_czk_placeholder/
active/stock_qty). Plan schvaleny Robertem 2026-08-08, viz
/root/.claude/plans/witty-gliding-pudding.md. Dalsi kroky (mimo tenhle
skript):
  1) SQL migrace - nove sloupce (viz sql/2026-08-08_dogus_pairing.sql),
     musi bezet PRED prvnim --apply behem.
  2) az po dodani loginu: scraper ceny z doguskalip, STP download u
     ne-profilovych produktu (bez auto-prevodu na GLB), prepocet pres
     kurz USD/CZK (fio.cz, verejne) a kategorijni
     koeficient

Pouziti (test na par kategoriich, NEPOUSTI cely web):
    api/venv/bin/python3 scripts/2026-08-08_dogus_pairing_crawl.py --limit-categories 3

Plny beh (~139 kategorii, radove tisice HTTP requestu, jede radove
desitky minut kvuli zdvorilemu rate-limitu mezi requesty):
    api/venv/bin/python3 scripts/2026-08-08_dogus_pairing_crawl.py --out /tmp/dogus_catalog_report.json
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

sys.path.insert(0, "/opt/konfigurator/api")

BASE = "https://en.doguskalip.com.tr"
# Robert zadal na zacatku VYSLOVNE jen tyto 3 URL - zadny jiny strom
# dogus katalogu (motory, dopravniky, CNC, robotika...) NENI v teto
# fazi v rozsahu, i kdyz je "jen 1 klik dal" v jejich navigaci.
SEED_URLS = [
    f"{BASE}/Products/9/aluminium-profiles",
    f"{BASE}/Products/10/fasteners",
    f"{BASE}/Products/11/fastener-accessories",
]
# ID+slug z breadcrumbu (viz IN_SCOPE_ROOT_RE nize) - PREFIX stranky se
# lisi (/Products/ na uvodni strance rootu, /Urunler/ v breadcrumbu a
# v kategoriich), proto se kontroluje jen /<id>/<slug> cast.
ALLOWED_ROOT_IDS = {"9", "10", "11"}
UA = "Mozilla/5.0 (compatible; LogimanKonfiguratorPairingSync/1.0; +https://logiman.cz)"
REQUEST_DELAY_S = 0.4  # zdvorilostni prodleva mezi requesty na cizi web

CATEGORY_HREF_RE = re.compile(r'href="(/Urunler/(\d+)/[a-z0-9-]+)"')
# Puvodni [a-z0-9-]+ ticho preskocelo produkty se specialnimi znaky ve
# slugu ("45x45-45°-graded-corner-bracket", "ø28---17-mm-...", "30x30-–-
# 40x40-k8-120°-connecting-piece", "(domestic)") - 8 z 16 kategorii, ktere
# 2026-08-10 nahlasily "0 produktu", ve skutecnosti produkty MELY, jen se
# nenamatchovaly (zjisteno pri dohledavani, proc produkt 2.2.006.4545.10
# chybel). Slug muze obsahovat prakticky cokoli krome uvozovky, proto
# [^"]+ misto vyctu povolenych znaku.
PRODUCT_HREF_RE = re.compile(r'href="(/Urun/(\d+)/[^"]+)"')
# Breadcrumb (kategorie i produkt stranky) - "/Urunler/<id>/<slug>" -
# pouzito k OVERENI, ze kategorie/produkt skutecne patri pod jeden ze
# 3 povolenych korenu (9/aluminium-profiles, 10/fasteners,
# 11/fastener-accessories), NE jen ze je nekde v sitewide navigaci
# (ta obsahuje UPLNE VSECHNY produktove rodiny dogus - motory,
# dopravniky, CNC, robotiku... coz NENI v rozsahu).
BREADCRUMB_HREF_RE = re.compile(r"<li><a href='(/Urunler/(\d+)/[a-z0-9-]+)'")


def breadcrumb_root_ids(html):
    """Vraci mnozinu kategorie-ID z breadcrumbu dane stranky (kategorie
    i produkt maji stejny format breadcrumbu)."""
    return {cat_id for _href, cat_id in BREADCRUMB_HREF_RE.findall(html)}


def is_in_scope(html):
    return bool(breadcrumb_root_ids(html) & ALLOWED_ROOT_IDS)

# Renderovaci/schema obrazek - vzdy prvni polozka daneho carouselu na
# hlavni zalozce produktu (viz #ContentPlaceHolder1_dvProductImageList /
# #ContentPlaceHolder1_dvProductUrunList). Quote-agnostic (dogus pouziva
# na ruznych mistech ' i ").
def _first_carousel_image_re(container_id):
    return re.compile(
        r'id="' + re.escape(container_id) + r'"[\s\S]{0,3000}?<img class="imgin" src=[\'"]([^\'"]+)[\'"]'
    )


IMAGE_RENDER_RE = _first_carousel_image_re("ContentPlaceHolder1_dvProductImageList")
IMAGE_SCHEMA_RE = _first_carousel_image_re("ContentPlaceHolder1_dvProductUrunList")
# Objeveno pri testu na profilech (na rozdil od spojovacich prvku): misto
# 2 samostatnych carouselu maji profilove stranky JEDEN spolecny obrazek
# v #ContentPlaceHolder1_dvIkiliResimler ("ikili" = turecky "dvojity") -
# render+schema uz kombinovane v jednom souboru. Fallback, kdyz vyse
# nic nenajde.
IMAGE_COMBINED_RE = re.compile(
    r'id="ContentPlaceHolder1_dvIkiliResimler"[\s\S]{0,1500}?<img src="([^"]+)"'
)


class SpecTableParser(HTMLParser):
    """Obecny parser tabulky "General Specifications" (hlavni zalozka,
    div #ContentPlaceHolder1_dvProductListWithParent) - NEpredpoklada
    pevny pocet/poradi sloupcu, protoze profily maji vic sloupcu
    (External Dimensions/Material/L/Ix/Iy/Wx/Wy/Area/Mass) nez spojovaci
    prvky (jen Material/Weight). Bunky se parsuji podle skutecneho
    textoveho obsahu (vnorene <input>/<span> bez textu se automaticky
    neprojevi - HTMLParser.handle_data dostava jen skutecne textove
    uzly, ne atributy)."""

    TARGET_DIV_ID = "ContentPlaceHolder1_dvProductListWithParent"

    def __init__(self):
        super().__init__()
        self.in_target = False
        self.div_depth = 0
        self.in_thead = False
        self.in_tbody = False
        self.in_cell = False
        self.headers = []
        self.rows = []
        self._row = []
        self._cell_chunks = []

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        if not self.in_target:
            if tag == "div" and attrs_d.get("id") == self.TARGET_DIV_ID:
                self.in_target = True
                self.div_depth = 1
            return
        if tag == "div":
            self.div_depth += 1
        elif tag == "thead":
            self.in_thead = True
        elif tag == "tbody":
            self.in_tbody = True
        elif tag == "tr":
            self._row = []
        elif tag in ("th", "td"):
            self.in_cell = True
            self._cell_chunks = []

    def handle_endtag(self, tag):
        if not self.in_target:
            return
        if tag == "div":
            self.div_depth -= 1
            if self.div_depth == 0:
                self.in_target = False
            return
        if tag == "thead":
            self.in_thead = False
        elif tag == "tbody":
            self.in_tbody = False
        elif tag in ("th", "td"):
            text = " ".join("".join(self._cell_chunks).split())
            self._row.append(text)
            self.in_cell = False
        elif tag == "tr":
            if self.in_thead and self._row and not self.headers:
                self.headers = self._row
            elif self.in_tbody and self._row:
                self.rows.append(self._row)

    def handle_data(self, data):
        if self.in_cell:
            self._cell_chunks.append(data)

    # Kosikove/UI sloupce bez technicke hodnoty pro nas (stav skladu,
    # mnozstvi do kosiku, tlacitko kosiku, CAD-stahovaci prompt, filtr) -
    # "Cad"/"Filter" bunky navic obcas obsahuji nechtene "prosakle" texty
    # z vnorenych promptu ("Dosya yükleme işlemi..." atd.), proto se
    # zahazuji cele, ne jen prazdne.
    NOISE_HEADERS = {"stock", "quantity", "basket", "cad", "filter", "uzunluk (mm)"}

    def as_records(self):
        """[{header: value, ...}, ...] - orezano na kratsi z headers/row,
        aby nesouhlasici pocet sloupcu (napr. skryty "Stock" sloupec bez
        <th>) nespadl na IndexError."""
        records = []
        for row in self.rows:
            n = min(len(self.headers), len(row))
            records.append({
                self.headers[i]: row[i] for i in range(n)
                if self.headers[i] and self.headers[i].strip().lower() not in self.NOISE_HEADERS
            })
        return records


def fetch(url):
    # Nektere produktove slugy obsahuji ne-ASCII znaky ("45°", "ø28") -
    # http.client vyzaduje ciste ASCII request-line, jinak spadne na
    # UnicodeEncodeError (zjisteno 2026-08-10 - 41 produktu, vcetne
    # presne toho, ktery Robert nahlasil jako chybejici, timhle tise
    # selhalo a match_against_db je nikdy nevidel). Cesta se proto pred
    # requestem percent-enkoduje, zbytek URL (schema/host) beze zmeny.
    parts = urllib.parse.urlsplit(url)
    safe_path = urllib.parse.quote(parts.path, safe="/-_.~")
    url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, safe_path, parts.query, parts.fragment))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    time.sleep(REQUEST_DELAY_S)
    return html


def discover_categories():
    """Sitewide navigace (vsechny urovne stromu) je pritomna na KAZDE
    strance webu, staci tedy nacist jednu ze seed stranek a vytahnout
    vsechny /Urunler/<id>/<slug> odkazy - neni potreba rekurzivne lozit
    kategorie po urovnich."""
    seen = {}
    for seed in SEED_URLS:
        html = fetch(seed)
        for href, cat_id in CATEGORY_HREF_RE.findall(html):
            seen[cat_id] = href
    return [(cid, href) for cid, href in seen.items()]


def discover_products(category_href):
    """Vraci (products, in_scope). in_scope = False znamena, ze kategorie
    NEPATRI pod jeden ze 3 povolenych korenu (viz ALLOWED_ROOT_IDS) - i
    kdyz se objevila v sitewide navigaci (ta zahrnuje UPLNE VSECHNY
    produktove rodiny dogus, ne jen tyto 3). V tom pripade se produkty
    teto kategorie VUBEC neparsuji/nezapocitavaji."""
    html = fetch(BASE + category_href)
    if not is_in_scope(html):
        return [], False
    seen = {}
    for href, pid in PRODUCT_HREF_RE.findall(html):
        seen[pid] = href
    return [(pid, href) for pid, href in seen.items()], True


def _find_col(headers, *candidates):
    low = [h.strip().lower() for h in headers]
    for cand in candidates:
        if cand in low:
            return low.index(cand)
    return None


def parse_product(product_href):
    """Vraci (variants, render_url, schema_url). variants = list radku ze
    spec tabulky (jeden produkt muze mit vice variant/kodu), kazdy dict
    obsahuje aspon stock_code/stock_name + vsechny dalsi sloupce, ktere
    dana stranka ma (External Dimensions/Material/L/Ix/Iy/Wx/Wy/Area/Mass
    u profilu, Material/Weight u spojovacich prvku)."""
    html = fetch(BASE + product_href)

    parser = SpecTableParser()
    parser.feed(html)
    records = parser.as_records()

    code_idx = _find_col(parser.headers, "stock code")
    name_idx = _find_col(parser.headers, "stock name")
    variants = []
    for rec, row in zip(records, parser.rows):
        code = (row[code_idx].strip() if code_idx is not None and code_idx < len(row) else "")
        name = (row[name_idx].strip() if name_idx is not None and name_idx < len(row) else "")
        if not code:
            continue
        variant = {"stock_code": code, "stock_name": name, "specs": rec}
        variants.append(variant)

    render_m = IMAGE_RENDER_RE.search(html)
    schema_m = IMAGE_SCHEMA_RE.search(html)
    render_url = render_m.group(1) if render_m else None
    schema_url = schema_m.group(1) if schema_m else None
    if not render_url and not schema_url:
        combined_m = IMAGE_COMBINED_RE.search(html)
        if combined_m:
            # "ikili" layout (typicky u profilu) - jeden obrazek uz
            # kombinuje render+schema, viz komentar u IMAGE_COMBINED_RE.
            render_url = schema_url = combined_m.group(1)
    return variants, render_url, schema_url


def crawl_catalog(limit_categories=None, verbose=True):
    categories = discover_categories()
    if verbose:
        print(f"Nalezeno {len(categories)} kategorii v navigaci.", file=sys.stderr)
    if limit_categories:
        categories = categories[:limit_categories]
        if verbose:
            print(f"(testovaci beh - omezeno na prvnich {limit_categories})", file=sys.stderr)

    catalog = []
    skipped_out_of_scope = 0
    for i, (cat_id, cat_href) in enumerate(categories, 1):
        try:
            products, in_scope = discover_products(cat_href)
        except Exception as e:
            print(f"[{i}/{len(categories)}] CHYBA kategorie {cat_href}: {e}", file=sys.stderr)
            continue
        if not in_scope:
            skipped_out_of_scope += 1
            continue
        if verbose:
            print(f"[{i}/{len(categories)}] kategorie {cat_href} (v rozsahu, {len(products)} produktu)", file=sys.stderr)
        for pid, p_href in products:
            try:
                variants, render_url, schema_url = parse_product(p_href)
            except Exception as e:
                print(f"  CHYBA produkt {p_href}: {e}", file=sys.stderr)
                continue
            for v in variants:
                catalog.append({
                    "category_href": cat_href,
                    "product_id": pid,
                    "product_url": BASE + p_href,
                    "stock_code": v["stock_code"],
                    "stock_name": v["stock_name"],
                    "specs": v["specs"],
                    "image_render_url": render_url,
                    "image_schema_url": schema_url,
                })
    if verbose:
        print(f"Mimo rozsah (ne pod aluminium-profiles/fasteners/fastener-accessories) - preskoceno {skipped_out_of_scope} kategorii.", file=sys.stderr)
    return catalog


def get_db_conn():
    import pymysql

    env = {}
    for line in open("/opt/konfigurator/api/.env"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v

    return pymysql.connect(
        host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
        password=env["DB_PASSWORD"], database=env["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def match_against_db(catalog):
    """READ-ONLY match - jen SELECT, nikdy UPDATE. Vraci report dict."""
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sku, name FROM shop_products WHERE sku IS NOT NULL AND sku != ''")
            our_products = {row["sku"].strip(): row for row in cur.fetchall()}
    finally:
        conn.close()

    dogus_by_code = {}
    for row in catalog:
        dogus_by_code.setdefault(row["stock_code"], row)

    matched, unmatched_ours, unmatched_dogus = [], [], []
    for sku, our in our_products.items():
        d = dogus_by_code.get(sku)
        if d:
            matched.append({"shop_product_id": our["id"], "sku": sku, "our_name": our["name"],
                             "dogus_name": d["stock_name"], "dogus_url": d["product_url"],
                             "dogus_image_render_url": d.get("image_render_url"),
                             "dogus_image_schema_url": d.get("image_schema_url"),
                             "dogus_specs": d.get("specs")})
        else:
            unmatched_ours.append({"shop_product_id": our["id"], "sku": sku, "our_name": our["name"]})
    matched_codes = {m["sku"] for m in matched}
    for code, d in dogus_by_code.items():
        if code not in our_products:
            unmatched_dogus.append({"stock_code": code, "dogus_name": d["stock_name"], "dogus_url": d["product_url"]})

    return {
        "summary": {
            "dogus_catalog_rows": len(catalog),
            "dogus_unique_codes": len(dogus_by_code),
            "our_products_with_sku": len(our_products),
            "matched": len(matched),
            "unmatched_ours_no_dogus_code": len(unmatched_ours),
            "unmatched_dogus_not_in_our_catalog": len(unmatched_dogus),
        },
        "matched": matched,
        "unmatched_ours": unmatched_ours,
        "unmatched_dogus": unmatched_dogus,
    }


def apply_matches(matched):
    """Jedine misto, ktere skutecne ZAPISUJE do DB - jen presne SKU
    shody z match_against_db(). Nedotyka se price_czk_placeholder,
    active, stock_qty ani jinych provoznich poli (viz plan schvaleny
    Robertem 2026-08-08)."""
    conn = get_db_conn()
    updated = 0
    try:
        with conn.cursor() as cur:
            for m in matched:
                cur.execute(
                    "UPDATE shop_products SET dogus_url=%s, dogus_stock_code=%s, "
                    "dogus_image_render_url=%s, dogus_image_schema_url=%s, "
                    "product_specs_json=%s, dogus_matched_at=NOW() WHERE id=%s",
                    (
                        m["dogus_url"], m["sku"],
                        m["dogus_image_render_url"], m["dogus_image_schema_url"],
                        json.dumps(m["dogus_specs"], ensure_ascii=False),
                        m["shop_product_id"],
                    ),
                )
                updated += cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return updated


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit-categories", type=int, default=None,
                     help="Omezit na prvnich N kategorii (pro rychly test).")
    ap.add_argument("--out", default="/tmp/dogus_catalog_report.json",
                     help="Kam ulozit JSON report.")
    ap.add_argument("--catalog-in", default=None,
                     help="Preskocit crawl, nacist drive ulozeny surovy katalog (--out z predchoziho behu s --raw-out) a jen znovu spustit matchovani.")
    ap.add_argument("--raw-out", default=None,
                     help="Volitelne ulozit i surovy katalog (pred matchovanim) - uzitecne pro opakovane matchovani bez re-crawlu.")
    ap.add_argument("--apply", action="store_true",
                     help="Zapsat matchnute radky do shop_products (dogus_url/dogus_stock_code/"
                          "dogus_image_render_url/dogus_image_schema_url/product_specs_json/dogus_matched_at). "
                          "Bez teto volby skript jen ctel/reportuje (READ-ONLY), nic nezapisuje.")
    args = ap.parse_args()

    if args.catalog_in:
        with open(args.catalog_in) as f:
            catalog = json.load(f)
        print(f"Nacten ulozeny katalog: {len(catalog)} radku.", file=sys.stderr)
    else:
        catalog = crawl_catalog(limit_categories=args.limit_categories)
        if args.raw_out:
            with open(args.raw_out, "w") as f:
                json.dump(catalog, f, ensure_ascii=False, indent=2)
            print(f"Surovy katalog ulozen do {args.raw_out}", file=sys.stderr)

    report = match_against_db(catalog)
    with open(args.out, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"\nPlny report: {args.out}", file=sys.stderr)

    if args.apply:
        print(f"\n--apply: zapisuji {len(report['matched'])} matchnutych produktu do shop_products...", file=sys.stderr)
        updated = apply_matches(report["matched"])
        print(f"Hotovo, aktualizovano {updated} radku.", file=sys.stderr)
    else:
        print("\n(READ-ONLY beh - pro skutecny zapis pridej --apply)", file=sys.stderr)


if __name__ == "__main__":
    main()
