"""Řemeslo Srovnávač - import poboček řetězcových dodavatelů (bot13,
2026-08-20). Navazuje na scripts/2026-08-20_remeslo_geocode_sources.py
(ten dal každému dodavateli JEDNU souřadnici - sídlo). Robertovo
zadání: u DEK.cz/OBI.cz/HORNBACH.cz je vzdálenost k sídlu zavádějící,
mají desítky poboček po celé ČR - řemeslník v Ostravě viděl vzdálenost
do Prahy, i když má pobočku za rohem. Řešení: `remeslo_supplier_
branches` tabulka (viz sql/2026-08-20_remeslo_supplier_branches.sql),
`GET /api/remeslo/compare` počítá vzdálenost k NEJBLIŽŠÍ pobočce, když
dodavatel nějaké má.

Zdroje dat (ověřeno živě 2026-08-20):
- **DEK.cz** (101 poboček) - stránka /kontakty embedduje kompletní
  JS proměnnou `const storeList = JSON.parse("...")` se VŠEMI
  pobočkami (id/název/ulice/město/PSČ/lat/lon), čistý HTTP GET stačí,
  žádné přihlášení/JS potřeba.
- **OBI.cz** (32 poboček) - stránka /prodejna má Nuxt SSR payload
  (`<script id="__NUXT_DATA__" type="application/json">`) - devalue-
  flattened JSON pole, taky čistý HTTP GET.
- **HORNBACH.cz** (10 poboček) - VĚDOMĚ RUČNĚ KURÁTOVANÝ seznam, ne
  automatizovaný scraper. Celá doména hornbach.cz je za JS bot-
  challenge stránkou ("Client Challenge") - živě ověřeno, že to
  neobejde ani headless Playwright (stejná třída problému jako u
  `api/remeslo_price_search.py`, který HORNBACH.cz ze stejného důvodu
  vědomě nepodporuje). Seznam sestaven křížovou kontrolou DVOU
  nezávislých agregátorů (mapaobchodu.cz, sysloun.cz) - první měl jen
  9 poboček a jednu špatně pojmenovanou (Chlumecká 2398 = Praha Černý
  Most, ne "Horní Počernice"), druhý (sysloun.cz, "10 poboček") odhalil
  chybějící Praha-Velká Chuchle. Finálních 10 odpovídá druhému zdroji,
  Velká Chuchle dogeokódována přes Nominatim (stejný nástroj jako
  zbytek projektu). Pobočky se otvírají řádově jednou za rok - tenhle
  seznam čeká na PŘÍLEŽITOSTNOU ruční revizi, ne pravidelný cron.

Bezpečnost importu: DEK.cz/OBI.cz se dají kdykoliv znovu stáhnout
(živá data), ale špatný parse (web změnil strukturu, timeout uprostřed
apod.) NESMÍ tiše smazat funkční tabulku - `_validate()` kontroluje
minimální očekávaný počet poboček A že všechny souřadnice padají do
rozumného rozsahu ČR, než se cokoliv v DB smaže/zapíše. Delete+insert
per dodavatel je v JEDNÉ transakci (buď obojí, nebo nic).

Použití:
    api/venv/bin/python3 scripts/2026-08-20_remeslo_supplier_branches_import.py --kontrola
    api/venv/bin/python3 scripts/2026-08-20_remeslo_supplier_branches_import.py --apply
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "api", ".env")
for _line in open(_ENV_PATH, encoding="utf-8"):
    _line = _line.strip()
    if not _line or _line.startswith("#") or "=" not in _line:
        continue
    _k, _v = _line.split("=", 1)
    os.environ.setdefault(_k, _v)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from remeslo import get_remeslo_conn as get_conn  # noqa: E402

USER_AGENT = "Mozilla/5.0 (compatible; KonfiguratorRemesloSearchBot/1.0)"
FETCH_TIMEOUT_S = 15

# Rozumny rozsah souradnic pro Ceskou republiku (s malou rezervou) -
# stejny princip jako zbytek modulu, pobocka mimo tenhle box je znamka
# rozbiteho parsovani, ne skutecna data.
CZ_LAT_RANGE = (48.4, 51.2)
CZ_LON_RANGE = (11.8, 19.1)

# supplier_name (musi presne sedet s remeslo_price_sources.supplier_name)
# -> (URL, min. ocekavany pocet pobocek - konzervativni rezerva pod
# skutecne namerenym poctem, ochrana proti castecnemu parsu)
DEK_URL = "https://www.dek.cz/kontakty"
DEK_MIN_COUNT = 80  # zive namereno 101, 2026-08-20

OBI_URL = "https://www.obi.cz/prodejna"
OBI_MIN_COUNT = 25  # zive namereno 32, 2026-08-20

# Rucne kurátovaný seznam (viz docstring vyse) - zdroj: sysloun.cz
# ("HORNBACH.cz - 10 poboček"), krizove overeno proti mapaobchodu.cz,
# Velka Chuchle dogeokodovana Nominatim (2026-08-20).
HORNBACH_MANUAL = [
    {"branch_name": "Brno", "address": "Heršpická 3, 639 00 Brno - Štýřice", "city": "Brno", "latitude": 49.1790303, "longitude": 16.6053791},
    {"branch_name": "Čestlice", "address": "Lipová 281, 251 01 Čestlice", "city": "Čestlice", "latitude": 49.9995870, "longitude": 14.5847329},
    {"branch_name": "Hradec Králové", "address": "Rovná 1697, 500 02 Hradec Králové", "city": "Hradec Králové", "latitude": 50.1820843, "longitude": 15.8017828},
    {"branch_name": "Olomouc", "address": "Rolsberská 10, 779 00 Olomouc", "city": "Olomouc", "latitude": 49.5869754, "longitude": 17.2870958},
    {"branch_name": "Ostrava - Svinov", "address": "Bílovecká 3, 721 00 Ostrava - Svinov", "city": "Ostrava", "latitude": 49.8264289, "longitude": 18.2105361},
    {"branch_name": "Ostrava - Vítkovice", "address": "Rudná 2978/11, 703 00 Ostrava - Vítkovice", "city": "Ostrava", "latitude": 49.8052686, "longitude": 18.2775680},
    {"branch_name": "Plzeň", "address": "U Prazdroje 2750/24, 301 00 Plzeň", "city": "Plzeň", "latitude": 49.7466120, "longitude": 13.3954528},
    {"branch_name": "Praha - Černý Most", "address": "Chlumecká 2398, 198 00 Praha 9", "city": "Praha", "latitude": 50.1115338, "longitude": 14.5816686},
    {"branch_name": "Praha - Řepy", "address": "Slánská 1706, 163 00 Praha 17 - Řepy", "city": "Praha", "latitude": 50.0751638, "longitude": 14.3078476},
    {"branch_name": "Praha - Velká Chuchle", "address": "Strakonická 62, 159 00 Praha 5 - Velká Chuchle", "city": "Praha", "latitude": 50.0310776, "longitude": 14.3993986},
]
HORNBACH_MIN_COUNT = 10


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_dek(html):
    """`const storeList = JSON.parse("...")` na /kontakty - JS string
    literal obsahujici JSON objekt {storeId: {...}}. Dvojite json.loads
    - poprve rozbali escapovany JS string, podruhe naparsuje JSON."""
    m = re.search(r'const storeList = JSON\.parse\("(.*?)"\);', html, re.S)
    if not m:
        raise ValueError("DEK.cz: 'const storeList' nenalezen - web zmenil strukturu stranky.")
    decoded = json.loads('"' + m.group(1) + '"')
    stores = json.loads(decoded)
    branches = []
    for s in stores.values():
        branches.append({
            "branch_name": s["name"],
            "address": f'{s["street"]}, {s["zip"]} {s["city"]}',
            "city": s["city"],
            "latitude": float(s["latitude"]),
            "longitude": float(s["longitude"]),
        })
    return branches


def parse_obi(html):
    """Nuxt SSR payload `<script id="__NUXT_DATA__">` - devalue-
    flattened JSON pole (cisla jsou indexy zpet do stejneho pole).
    Resolvujeme jen dicty obsahujici klic "storeName" (jedna pobocka),
    1 uroven zanoreni staci - kazdy klic uz vede primo na finalni
    hodnotu (text/cislo)."""
    m = re.search(
        r'<script type="application/json" data-nuxt-data="nuxt-app" data-ssr="true" id="__NUXT_DATA__">(.*?)</script>',
        html, re.S,
    )
    if not m:
        raise ValueError("OBI.cz: __NUXT_DATA__ nenalezen - web zmenil strukturu stranky.")
    data = json.loads(m.group(1))

    def resolve(idx):
        v = data[idx]
        if isinstance(v, dict):
            return {k: resolve(vv) if isinstance(vv, int) else vv for k, vv in v.items()}
        return v

    branches = []
    for i, v in enumerate(data):
        if not (isinstance(v, dict) and "storeName" in v and "geo" in v and "address" in v):
            continue
        store = resolve(i)
        name = store["storeName"]["content"]["text"]
        addr_text = store["address"]["content"]["text"].replace("\n", ", ")
        geo = store["geo"]["content"]
        branches.append({
            "branch_name": name,
            "address": addr_text,
            "city": name,
            "latitude": float(geo["latitude"]),
            "longitude": float(geo["longitude"]),
        })
    return branches


def _validate(supplier_name, branches, min_count):
    warnings = []
    if len(branches) < min_count:
        raise ValueError(
            f"{supplier_name}: jen {len(branches)} poboček, čekalo se aspoň {min_count} "
            "- vypadá to na neúplný/rozbitý parse, DB se NEMĚNÍ."
        )
    for b in branches:
        lat, lon = b["latitude"], b["longitude"]
        if not (CZ_LAT_RANGE[0] <= lat <= CZ_LAT_RANGE[1] and CZ_LON_RANGE[0] <= lon <= CZ_LON_RANGE[1]):
            raise ValueError(
                f"{supplier_name}: pobočka '{b['branch_name']}' má souřadnice mimo ČR "
                f"({lat}, {lon}) - vypadá to na chybu parsování, DB se NEMĚNÍ."
            )
    # Kontrola duplicit (stejny nazev vic nez jednou) - jen varovani,
    # ne blokujici chyba, nektere retezce maji legitimne 2 pobocky ve
    # stejnem meste s jinym doplnkem nazvu.
    names = [b["branch_name"] for b in branches]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        warnings.append(f"{supplier_name}: opakující se název poboček: {sorted(dupes)}")
    return warnings


def _upsert(conn, supplier_name, branches, origin):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM remeslo_price_sources WHERE supplier_name=%s", (supplier_name,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"{supplier_name}: v remeslo_price_sources neexistuje.")
        source_id = row["id"]
        cur.execute("DELETE FROM remeslo_supplier_branches WHERE source_id=%s", (source_id,))
        cur.executemany(
            "INSERT INTO remeslo_supplier_branches "
            "(source_id, branch_name, address, city, latitude, longitude, origin) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            [
                (source_id, b["branch_name"], b["address"], b["city"], b["latitude"], b["longitude"], origin)
                for b in branches
            ],
        )
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--kontrola", action="store_true", help="jen stáhnout/ověřit, nic nezapisovat")
    group.add_argument("--apply", action="store_true", help="stáhnout, ověřit a zapsat do DB")
    args = parser.parse_args()

    tasks = [
        ("DEK.cz", lambda: parse_dek(_fetch(DEK_URL)), DEK_MIN_COUNT, "own_site_scrape"),
        ("OBI.cz", lambda: parse_obi(_fetch(OBI_URL)), OBI_MIN_COUNT, "own_site_scrape"),
        ("HORNBACH.cz", lambda: HORNBACH_MANUAL, HORNBACH_MIN_COUNT, "manual_curated"),
    ]

    conn = get_conn() if args.apply else None
    try:
        for supplier_name, fetch_fn, min_count, origin in tasks:
            print(f"=== {supplier_name} ===")
            try:
                branches = fetch_fn()
            except (urllib.error.URLError, ValueError) as e:
                print(f"  CHYBA při stahování/parsování: {e}")
                continue
            try:
                warnings = _validate(supplier_name, branches, min_count)
            except ValueError as e:
                print(f"  CHYBA validace: {e}")
                continue
            print(f"  OK: {len(branches)} poboček, ukázka: {branches[0]}")
            for w in warnings:
                print(f"  VAROVÁNÍ: {w}")
            if args.apply:
                _upsert(conn, supplier_name, branches, origin)
                print(f"  Zapsáno do remeslo_supplier_branches ({origin}).")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
