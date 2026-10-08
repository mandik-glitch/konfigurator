"""
Import NOVYCH produktu z dogus kategorie 237 "Dynamic Shelving Systems"
(3 subkategorie 238/239/240) - bot8, 2026-08-11.

Robert: "natáhneme další produkty z DOgus, stejným způsobem jako ty
předešlé importy, tuto kategorii:
https://en.doguskalip.com.tr/Products/237/dynamic-shelving-systems" +
"mame ji tady https://vandrawee.cz/kategorie/hlinikove-profily-dynamic"
(cilova kategorie u nas uz existuje, predem zalozena, prazdna).

Na rozdil od 2026-08-08_dogus_pairing_crawl.py (ktery jen PARUJE
existujici shop_products podle SKU shody) tahle vetev katalogu u nas
JESTE VUBEC NEEXISTUJE - misto UPDATE dela INSERT novych radku.
Duvod, proc NENI proste rozsireni puvodniho skriptu: ten je zamerne
cisty read-only-match nastroj (viz jeho docstring/plan schvaleny
Robertem 2026-08-08), pridani INSERT vetve by zmenilo jeho zavazany
kontrakt pro VSECHNY dalsi pouziti (i pro puvodni 3 kategorie, kde
insert nikdy nebyl chtenej).

Mapovani dogus subkategorie (breadcrumb ID) -> nase content_categories.id
(overeno rucne 2026-08-11 - 237 ma presne tyto 3 subkategorie, zadne dalsi):
  238 aluminium-profiles      -> 192 (Hlinikove profily Dynamic)       is_profile_material=1
  239 connection-equipments   -> 157 (Spojovaci prvky systemu Dynamic)  is_profile_material=0
  240 connection-accessories  -> 191 (Prislusenstvi systemu Dynamic)   is_profile_material=0

Regexy/SpecTableParser/fetch() OKOPIROVANY z 2026-08-08_dogus_pairing_crawl.py
(ne importovany), aby ten skript zustal nezavisly a nemenil se
retroaktivne zmenou tady.

NAME_CS mapa (stock_code -> cesky nazev) je RUCNE prelozena z realnych
anglickych "Stock Name" hodnot ziskanych --report behem 2026-08-11 (viz
/tmp/dogus_237_catalog.json toho behu) - NE strojovy preklad za behu.
description se generuje sablonou stejnou jako u predchoziho Dogus importu
(overeno na produktech id=3564/3571/3572): "{nazev} (z materialu {material},
hmotnost cca {hmotnost}). {ucelova veta podle klicoveho slova}."

Rezimy:
  --report      jen stahne+zparsuje, ulozi JSON, NIC nezapisuje.
  (bez --apply) dry-run vuci DB - vypise, co by se vytvorilo, nic nezapise.
  --apply       skutecne zapise nove shop_products + stahne 2 obrazky
                (render/schema) do shop_product_images.

Vuci dogus je skript VZDY jen READ-ONLY (jen GET, zadne prihlaseni).
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://en.doguskalip.com.tr"
SUBCATEGORY_HREFS = {
    "238": "/Urunler/238/aluminium-profiles",
    "239": "/Urunler/239/connection-equipments",
    "240": "/Urunler/240/connection-accessories",
}
CATEGORY_MAP = {
    "238": {"category_id": 192, "is_profile_material": 1},
    "239": {"category_id": 157, "is_profile_material": 0},
    "240": {"category_id": 191, "is_profile_material": 0},
}
UA = "Mozilla/5.0 (compatible; LogimanKonfiguratorDynamicShelvingImport/1.0; +https://logiman.cz)"
REQUEST_DELAY_S = 0.4

PRODUCT_HREF_RE = re.compile(r'href="(/Urun/(\d+)/[^"]+)"')


def _first_carousel_image_re(container_id):
    return re.compile(
        r'id="' + re.escape(container_id) + r'"[\s\S]{0,3000}?<img class="imgin" src=[\'"]([^\'"]+)[\'"]'
    )


IMAGE_RENDER_RE = _first_carousel_image_re("ContentPlaceHolder1_dvProductImageList")
IMAGE_SCHEMA_RE = _first_carousel_image_re("ContentPlaceHolder1_dvProductUrunList")
IMAGE_COMBINED_RE = re.compile(
    r'id="ContentPlaceHolder1_dvIkiliResimler"[\s\S]{0,1500}?<img src="([^"]+)"'
)


class SpecTableParser(HTMLParser):
    """Okopirovano z 2026-08-08_dogus_pairing_crawl.py - viz tamni
    docstring pro vysvetleni."""

    TARGET_DIV_ID = "ContentPlaceHolder1_dvProductListWithParent"
    NOISE_HEADERS = {"stock", "quantity", "basket", "cad", "filter", "uzunluk (mm)"}

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

    def as_records(self):
        records = []
        for row in self.rows:
            n = min(len(self.headers), len(row))
            records.append({
                self.headers[i]: row[i] for i in range(n)
                if self.headers[i] and self.headers[i].strip().lower() not in self.NOISE_HEADERS
            })
        return records


def fetch(url):
    parts = urllib.parse.urlsplit(url)
    safe_path = urllib.parse.quote(parts.path, safe="/-_.~")
    url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, safe_path, parts.query, parts.fragment))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    time.sleep(REQUEST_DELAY_S)
    return html


def _find_col(headers, *candidates):
    low = [h.strip().lower() for h in headers]
    for cand in candidates:
        if cand in low:
            return low.index(cand)
    return None


def discover_products(category_href):
    html = fetch(BASE + category_href)
    seen = {}
    for href, pid in PRODUCT_HREF_RE.findall(html):
        seen[pid] = href
    return [(pid, href) for pid, href in seen.items()]


def parse_product(product_href):
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
        variants.append({"stock_code": code, "stock_name": name, "specs": rec})

    render_m = IMAGE_RENDER_RE.search(html)
    schema_m = IMAGE_SCHEMA_RE.search(html)
    render_url = render_m.group(1) if render_m else None
    schema_url = schema_m.group(1) if schema_m else None
    if not render_url and not schema_url:
        combined_m = IMAGE_COMBINED_RE.search(html)
        if combined_m:
            render_url = schema_url = combined_m.group(1)
    return variants, render_url, schema_url


def crawl():
    catalog = []
    for sub_id, sub_href in SUBCATEGORY_HREFS.items():
        products = discover_products(sub_href)
        print(f"[{sub_id}] {sub_href} - {len(products)} produktu", file=sys.stderr)
        for pid, p_href in products:
            try:
                variants, render_url, schema_url = parse_product(p_href)
            except Exception as e:
                print(f"  CHYBA produkt {p_href}: {e}", file=sys.stderr)
                continue
            for v in variants:
                catalog.append({
                    "sub_id": sub_id,
                    "product_id": pid,
                    "product_url": BASE + p_href,
                    "stock_code": v["stock_code"],
                    "stock_name": v["stock_name"],
                    "specs": v["specs"],
                    "image_render_url": render_url,
                    "image_schema_url": schema_url,
                })
    return catalog


# ---------------------------------------------------------------------------
# Cesky nazev (rucne prelozeno z realnych "Stock Name" hodnot, viz docstring)
# ---------------------------------------------------------------------------
NAME_CS = {
    # 238 - Aluminium Profiles (trubkove profily Ø28)
    "1.6.28.01.17.00": "Trubkový profil Ø28 - 1,7 mm",
    "1.6.28.02.17.00": "Profil s T-drážkou Ø28",
    "1.6.28.03.17.00": "Trubkový profil Ø28 - 1,7 mm (těžká série)",
    "1.6.28.04.17.00": "Trubkový profil L Ø28 - 1,7 mm",
    "1.6.28.05.17.00": "Trubkový profil T Ø28 - 1,7 mm",
    "1.6.28.06.17.00": "Dvojitý trubkový profil Ø28 - 1,7 mm",
    # 239 - Connection Equipments (spojovaci prvky)
    "2.2.050.28.03.008.000": "Spojovací díl profilu K8",
    "2.2.050.28.01.001.01": "Vícenásobná spojka - vnější",
    "2.2.050.28.01.001.07": "Vícenásobná spojka zesílená - vnější",
    "2.2.050.28.02.001.01": "Vícenásobná spojka - vnitřní",
    "2.2.050.28.02.001.02": "Vícenásobná otočná spojka - vnitřní",
    "2.2.050.28.02.001.07": "Vícenásobná spojka zesílená - vnitřní",
    "2.2.050.28.00.002.01": "Křížová spojka",
    "2.2.050.28.01.003.045": "Spojka 45° - vnější",
    "2.2.050.28.02.003.045": "Spojka 45° - vnitřní",
    "2.2.050.28.11.004.090": "Rohová spojka 90° - vnější",
    "2.2.050.28.22.004.090": "Rohová spojka 90° - vnitřní",
    "2.2.050.28.11.004.135": "Rohová spojka 135° - vnější",
    "2.2.050.28.22.004.135": "Rohová spojka 135° - vnitřní",
    "2.2.050.28.01.005.01": "Dvojitá vícenásobná spojka",
    "2.2.050.28.01.006.01": "Dvoucestná spojka",
    "2.2.050.28.11.007.01": "Třícestná spojka",
    "2.2.050.28.11.008.01": "Čtyřcestná spojka",
    "2.2.050.28.00.009.03": "Rohová podpěrná spojka - krátká",
    "2.2.050.28.00.009.04": "Rohová podpěrná spojka - dlouhá",
    "2.2.050.28.01.010.180": "Úhlová spojka 180° - vnější",
    "2.2.050.28.01.010.090": "Úhlová spojka 90° - vnější",
    "2.2.010.28.000845.01": "Dvojitá úhlová spojka 180° - vnější",
    "2.2.050.28.02.010.180": "Úhlová spojka 180° - vnitřní",
    "2.2.050.28.01.011.01": "Kotvicí spojka k podlaze",
    "2.2.050.28.22.012.01": "Přímá spojka - vnitřní",
    "2.2.050.28.00.013.01": "Můstková spojka",
    "2.2.050.28.00.014.06": "Paralelní spojovací díl - vnitřní",
    "2.2.050.28.00.014.01": "Paralelní spojovací díl - vnější",
    "2.2.050.28.00.015.01": "Rohová spojka 90°",
    "2.2.050.28.0.016.01": "Závěsný úchyt",
    "2.2.050.28.00.017.180": "Kloubová spojka",
    "2.2.050.28.22.017.180": "Sklopná spojka",
    "2.2.050.28.02.018.01": "Spojka do T-drážky",
    "2.2.050.28.0.019.01": "Spojka rukojeti",
    "2.2.050.28.0.020.01": "Montážní konzola",
    "2.2.050.28.0.020.08": "Montážní konzola typ A",
    "2.2.050.28.0.020.09": "Montážní konzola typ B",
    "2.2.050.28.02.021.02": "Čepová spojka",
    # 240 - Connection Accessories (prislusenstvi)
    "2.3.050.28.01.01.00": "Koncová krytka trubkového profilu",
    "2.3.050.28.01.02.00": "Koncová krytka T profilu",
    "2.3.050.28.12.01.00": "Plastová patka Ø28",
    "2.3.050.28.03.02.00": "Plastová spojka patky Ø28",
    "2.3.050.28.05.02.28.45": "Upevňovací deska Ø28",
    "2.3.050.28.05.01.20.24": "Držák desky Ø28",
    "2.3.050.28.02.01.02": "Kovový pant Ø28 - pravý",
    "2.3.050.28.02.01.01": "Kovový pant Ø28 - levý",
    "2.3.050.28.04.01.43.43": "Polohovací kroužek Ø28 - horizontální",
    "2.3.050.28.04.02.55.43": "Polohovací kroužek Ø28 - vertikální",
    "2.3.050.28.07.01.055": "Posuvná spojka Ø28, 55 mm",
    "2.3.050.28.07.02.055": "Otočná posuvná spojka Ø28, 55 mm",
    "2.3.050.28.20.01.05": "Protizávaží 0,5 kg",
    "2.3.050.28.20.01.10": "Protizávaží 1,0 kg",
    "2.3.050.28.14.01.01.30.77": "Jednosměrná zarážka",
    "2.3.050.28.09.01": "Otočná spojka",
    "2.3.050.28.09.02": "Zajišťovaná otočná spojka",
    "2.3.050.28.27.43.63": "Výškový nastavovač",
    "2.3.050.28.10.01.08": "Hydraulický tlumič, zdvih 8 mm",
    "2.3.050.28.25.01": "Zámek vertikálního zdvihu",
    "2.3.050.28.11.134.116": "Podlahová brzda-zvedák 134x116 mm",
    "2.3.050.28.26.02.70.70": "Spojka kolečka Ø28",
    "2.3.050.28.26.01.30.70": "Podpěra kolečka Ø28, 30x70 mm",
    "2.3.050.28.21.130.215": "Nožní pedál",
    "2.3.050.28.08.02.30.1": "Plastová kladka s U-drážkou Ø30",
    "2.3.050.28.08.01.33.2": "Kovová kladka s V-drážkou Ø33",
    "2.3.050.28.08.02.38.1": "Plastová kladka s U-drážkou Ø38",
    "2.3.050.28.22.01.33.48": "Posuvný váleček",
    "2.3.050.28.22.02.33.48": "Sada kladek s U-drážkou Ø30 - dvojitý otvor",
    "2.3.050.28.23.88.150": "Válečkový posuvník 150 mm",
    "2.3.050.28.24.01.100": "Lineární posuvník Ø28, 100 mm",
    "2.3.050.28.06.02.40": "Plastová ochrana proti otěru Ø28, 40 mm",
    "2.3.050.28.06.01.20.38": "Klip na visačku Ø28",
    "2.3.050.28.17.01.02": "Nerezové lanko v plastovém opletu",
    "2.3.050.28.18.01": "Sada spojovacích klipů lanka",
    "2.3.050.28.28.01.06.023.1": "Šroub s okem M6x23",
    "2.3.050.28.28.01.06.020.2": "Šroub s okem M6x20",
    "2.3.050.28.28.02.24.036": "Závěsný D-kroužek",
    "2.3.050.28.19.01.02.10.17": "Polohovací destička lanka",
    "2.3.050.28.16.06.15.25.16": "Navíjecí pružina",
    "2.3.050.28.16.15.30.25.16": "Navíjecí pružina",
    "2.3.050.28.16.30.50.32.15": "Navíjecí pružina",
}

# Preklad materialu (Dogus katalog mixuje EN/TR/FR nazvy nahodne) na
# cestinu - substring nahrady, case-insensitive, delsi retezce prvni.
MATERIAL_REPLACEMENTS = [
    ("aluminum casting", "litý hliník"),
    ("alüminyum döküm", "litý hliník"),
    ("moulage d'aluminium", "litý hliník"),
    ("aluminum", "hliník"),
    ("aluminium", "hliník"),
    ("carbon steel", "uhlíková ocel"),
    ("karbon çelik", "uhlíková ocel"),
    ("acier au carbone", "uhlíková ocel"),
    ("acier carbone", "uhlíková ocel"),
    ("stainless steel", "nerezová ocel"),
    ("polypropylene", "polypropylen"),
    ("polypropylène", "polypropylen"),
    ("polipropileno", "polypropylen"),
    ("polipropilen", "polypropylen"),
    ("delrin", "Delrin (POM)"),
]


def translate_material(raw):
    if not raw or raw.strip() in ("-", ""):
        return None
    parts = re.split(r"\s*\+\s*", raw.strip())
    out_parts = []
    for part in parts:
        translated = part
        for src, dst in MATERIAL_REPLACEMENTS:
            translated = re.sub(re.escape(src), dst, translated, flags=re.IGNORECASE)
        out_parts.append(translated.strip())
    return " + ".join(out_parts)


PURPOSE_RULES = [
    (("multi connector",), "Vícenásobná spojka pro spojení více trubkových profilů Ø28 v jednom uzlu."),
    (("elbow", "angled", "angle fitting", "corner connector"), "Rohová spojka pro spojení profilů Ø28 pod úhlem."),
    (("way connector",), "Rozbočovací spojka pro spojení více profilů Ø28 v jednom bodě."),
    (("bracket",), "Montážní konzola pro uchycení profilu Ø28 systému Dynamic."),
    (("end cap",), "Plastová krytka pro zakrytí konce profilu Ø28."),
    (("plastic foot", "foot connector"), "Plastová patka pro spodní zakončení konstrukce ze systému Dynamic."),
    (("caster", "wheel"), "Kolečko/podpěra pro pojízdné provedení konstrukce ze systému Dynamic."),
    (("hinge", "folding"), "Kloubový/sklopný prvek pro pohyblivé spojení profilů Ø28."),
    (("pulley", "roller", "slider"), "Vodicí/posuvný prvek pro pojezdové a posuvné mechanismy regálového systému Dynamic."),
    (("counterweight",), "Protizávaží pro vyvážení pohyblivých částí regálového systému Dynamic."),
    (("rope", "eye bolt", "hanger", "hangtag"), "Závěsný/upínací prvek pro lankový mechanismus regálu Dynamic."),
    (("spring",), "Navíjecí pružina pro pohyblivé díly regálového systému Dynamic."),
    (("damper",), "Hydraulický tlumič pro plynulý pohyb pohyblivých částí regálu."),
    (("lift lock", "height adjuster"), "Aretační/nastavovací prvek pro výškově nastavitelné regálové systémy Dynamic."),
    (("floor brake",), "Podlahová brzda se zvedákem pro stabilizaci mobilní konstrukce."),
    (("positioning ring", "plate fixing", "board holder"), "Upevňovací/polohovací prvek pro montáž desek a panelů na profil Ø28."),
    (("pedal",), "Nožní pedál pro ovládání pohyblivého mechanismu regálu."),
    (("abrasion",), "Ochranný plastový prvek proti otěru profilu Ø28."),
    (("t slot",), "Spojka do T-drážky profilu systému Dynamic."),
    (("handle",), "Spojka rukojeti pro ovládání pohyblivé části konstrukce."),
    (("connector", "connection", "fitting"), "Spojovací prvek pro trubkové profily Ø28 systému Dynamic."),
]


def purpose_sentence(stock_name):
    low = stock_name.lower()
    for keywords, sentence in PURPOSE_RULES:
        if any(k in low for k in keywords):
            return sentence
    return "Doplňkový prvek stavebnicového regálového systému Dynamic."


def build_description(name_cs, stock_name, specs, is_profile):
    material_raw = specs.get("Material")
    material_cs = translate_material(material_raw)
    if is_profile:
        mass = specs.get("Mass")
        weight_txt = None
        if mass:
            m = re.search(r"([\d.,]+)\s*Kg/m", mass, re.I)
            if m:
                weight_txt = f"{m.group(1).replace(',', '.')} kg/m"
        purpose = "Hliníkový profil pro konstrukci regálových a montážních systémů Dynamic."
    else:
        weight_raw = specs.get("Weight (gr)")
        weight_txt = None
        if weight_raw and weight_raw.strip() not in ("-", ""):
            weight_txt = f"{weight_raw.strip()} g"
        purpose = purpose_sentence(stock_name)

    prefix = name_cs
    detail_bits = []
    if material_cs:
        detail_bits.append(f"z materiálu {material_cs}")
    if weight_txt:
        detail_bits.append(f"hmotnost cca {weight_txt}")
    if detail_bits:
        prefix += f" ({', '.join(detail_bits)})"
    return f"{prefix}. {purpose}"


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

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


def _slugify(text):
    import unicodedata
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "produkt"


def _unique_product_slug(cur, base, taken):
    candidate = base
    n = 2
    while True:
        if candidate not in taken:
            cur.execute("SELECT id FROM shop_products WHERE slug=%s", (candidate,))
            if not cur.fetchone():
                taken.add(candidate)
                return candidate
        candidate = f"{base}-{n}"
        n += 1


IMG_DIR_TPL = "/opt/konfigurator/webapp/content-files/gallery/products/{id}"


def download_image(url, dest_path):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    with open(dest_path, "wb") as f:
        f.write(data)
    time.sleep(REQUEST_DELAY_S)


def build_rows(catalog):
    rows = []
    skipped_no_name = []
    for r in catalog:
        code = r["stock_code"]
        name_cs = NAME_CS.get(code)
        if not name_cs:
            skipped_no_name.append(code)
            continue
        cat_info = CATEGORY_MAP[r["sub_id"]]
        desc = build_description(name_cs, r["stock_name"], r["specs"], bool(cat_info["is_profile_material"]))
        rows.append({
            "sku": code,
            "name": name_cs,
            "category_id": cat_info["category_id"],
            "is_profile_material": cat_info["is_profile_material"],
            "description": desc,
            "dogus_url": r["product_url"],
            "dogus_stock_code": code,
            "dogus_image_render_url": r["image_render_url"],
            "dogus_image_schema_url": r["image_schema_url"],
            "product_specs_json": r["specs"],
        })
    return rows, skipped_no_name


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true", help="Jen crawl+parse, ulozi JSON, nic v DB.")
    ap.add_argument("--catalog-in", default=None, help="Preskocit crawl, pouzit ulozeny JSON z --report.")
    ap.add_argument("--out", default="/tmp/dogus_237_catalog.json")
    ap.add_argument("--apply", action="store_true", help="Skutecne zapsat do DB + stahnout obrazky.")
    ap.add_argument("--limit", type=int, default=None, help="Omezit pocet produktu (test).")
    args = ap.parse_args()

    if args.catalog_in:
        catalog = json.load(open(args.catalog_in))
    else:
        catalog = crawl()
        with open(args.out, "w") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
        print(f"Crawl hotovy, {len(catalog)} radku ulozeno do {args.out}", file=sys.stderr)

    if args.report:
        return

    if args.limit:
        catalog = catalog[:args.limit]

    rows, skipped = build_rows(catalog)
    if skipped:
        print(f"POZOR: {len(skipped)} stock_code bez cesk. nazvu v NAME_CS, VYNECHANY: {skipped}", file=sys.stderr)

    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sku FROM shop_products WHERE sku IN %s", (tuple(r["sku"] for r in rows),)) \
                if rows else None
            existing = {r["sku"] for r in cur.fetchall()} if rows else set()
    finally:
        conn.close()

    to_create = [r for r in rows if r["sku"] not in existing]
    already = [r for r in rows if r["sku"] in existing]

    print(f"\n=== Souhrn ===", file=sys.stderr)
    print(f"Celkem naparsovano: {len(catalog)}", file=sys.stderr)
    print(f"S ceskym nazvem: {len(rows)}", file=sys.stderr)
    print(f"Jiz existuji v DB (preskoceno): {len(already)}", file=sys.stderr)
    print(f"K vytvoreni: {len(to_create)}", file=sys.stderr)
    for r in to_create[:10]:
        print(f"  [{r['category_id']}] {r['sku']} - {r['name']}", file=sys.stderr)
    if len(to_create) > 10:
        print(f"  ... a dalsich {len(to_create) - 10}", file=sys.stderr)

    if not args.apply:
        print("\n(dry-run - nic nezapsano, spust s --apply pro skutecny zapis)", file=sys.stderr)
        return

    conn = get_db_conn()
    created_ids = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT slug FROM shop_products WHERE slug IS NOT NULL")
            taken_slugs = {r["slug"] for r in cur.fetchall()}
            for r in to_create:
                slug = _unique_product_slug(cur, _slugify(r["name"]), taken_slugs)
                cur.execute(
                    """INSERT INTO shop_products
                       (category_id, sku, name, slug, description, unit, active, manufacturer,
                        is_profile_material, dogus_url, dogus_stock_code, dogus_image_render_url,
                        dogus_image_schema_url, product_specs_json, dogus_matched_at, price_visible_default)
                       VALUES (%s,%s,%s,%s,%s,'ks',1,'Dogus',%s,%s,%s,%s,%s,%s,NOW(),0)""",
                    (
                        r["category_id"], r["sku"], r["name"], slug, r["description"],
                        r["is_profile_material"], r["dogus_url"], r["dogus_stock_code"],
                        r["dogus_image_render_url"], r["dogus_image_schema_url"],
                        json.dumps(r["product_specs_json"], ensure_ascii=False),
                    ),
                )
                new_id = cur.lastrowid
                created_ids.append((new_id, r))
        conn.commit()
    finally:
        conn.close()
    print(f"\nVytvoreno {len(created_ids)} novych produktu.", file=sys.stderr)

    img_ok, img_fail = 0, 0
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            for new_id, r in created_ids:
                img_dir = IMG_DIR_TPL.format(id=new_id)
                os.makedirs(img_dir, exist_ok=True)
                sort_order = 0
                # bot5, 2026-09-17 (Robert pres bot3 - nalez duplicitnich
                # fotek v galerii): kdyz dodavatel uvede pro schema_url i
                # render_url STEJNOU URL, drivejsi kod ji stahl a vlozil
                # 2x (36 zivych + 27 archivovanych produktu s bajtove
                # identickou fotkou 2x). Skript uz znovu neposleze (jednorazovy
                # import), oprava je jen pro pripad dalsi davky se stejnym
                # vzorem dat.
                seen_urls = set()
                for key, url in (("dogus_image_schema_url", r["dogus_image_schema_url"]),
                                  ("dogus_image_render_url", r["dogus_image_render_url"])):
                    if url and url in seen_urls:
                        continue
                    seen_urls.add(url)
                    if not url:
                        continue
                    ext = os.path.splitext(urllib.parse.urlsplit(url).path)[1] or ".jpg"
                    fname = f"{sort_order + 1}{ext}"
                    dest = os.path.join(img_dir, fname)
                    try:
                        download_image(url, dest)
                    except Exception as e:
                        print(f"  CHYBA obrazek produkt {new_id} ({key}): {e}", file=sys.stderr)
                        img_fail += 1
                        continue
                    cur.execute(
                        "INSERT INTO shop_product_images (product_id, filename, source_url, sort_order) "
                        "VALUES (%s,%s,%s,%s)",
                        (new_id, f"products/{new_id}/{fname}", url, sort_order),
                    )
                    img_ok += 1
                    sort_order += 1
        conn.commit()
    finally:
        conn.close()
    print(f"Obrazky: {img_ok} stazeno, {img_fail} chyb.", file=sys.stderr)

    import pwd, grp
    uid, gid = pwd.getpwnam("www-data").pw_uid, grp.getgrnam("www-data").gr_gid
    for new_id, _r in created_ids:
        img_dir = IMG_DIR_TPL.format(id=new_id)
        if os.path.isdir(img_dir):
            os.chown(img_dir, uid, gid)
            for fname in os.listdir(img_dir):
                os.chown(os.path.join(img_dir, fname), uid, gid)


if __name__ == "__main__":
    main()
