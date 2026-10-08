"""Řemeslo - jednorázové doplnění adresy/lat/lon u remeslo_price_sources
(bot13, 2026-08-20). Viz REMESLO_KONCEPT.md "UI srovnávače pro
řemeslníka + vzdálenostní filtr" - vzdálenostní filtr byl 2026-08-17
zahozen kvůli chybějícímu geokódování bez API klíče, Robert 2026-08-20
rozhodnutí zvrátil ("vzdálenostní filtr je klíčová hodnota konceptu").
Blocker mezitím vyřešen - api/remeslo_weather.py má funkční Nominatim/
OSM geokódování (geocode(), cache remeslo_geo_cache), znovupoužito
beze změny.

Adresy sídel dohledány veřejně (ARES/firemní weby) 2026-08-20 - jde o
SÍDLO firmy, ne nutně nejbližší pobočku (všech 5 jsou řetězce s
pobočkami napříč ČR - vzdálenost k sídlu je orientační proxy, ne
přesná vzdálenost k nejbližšímu výdejnímu místu, vědomé zjednodušení
pro v1, viz koncept). Geokóduje se na úrovni MĚSTA (stejná přesnost
jako u počasí), ne přesné ulice - Nominatim usage policy + dostatečná
přesnost pro "je dodavatel X blíž než Y" účel.

"Ruční zadání (admin)" zdroj (pseudo-dodavatel bez fyzické adresy) se
záměrně VYNECHÁVÁ - zůstává latitude IS NULL, vzdálenost se u něj
nikdy nepočítá/nezobrazuje.

Použití:
    api/venv/bin/python3 scripts/2026-08-20_remeslo_geocode_sources.py --kontrola
    api/venv/bin/python3 scripts/2026-08-20_remeslo_geocode_sources.py --apply
"""
import argparse
import os
import sys

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "api", ".env")
for _line in open(_ENV_PATH, encoding="utf-8"):
    _line = _line.strip()
    if not _line or _line.startswith("#") or "=" not in _line:
        continue
    _k, _v = _line.split("=", 1)
    os.environ.setdefault(_k, _v)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from remeslo import get_remeslo_conn as get_conn  # noqa: E402
from remeslo_weather import geocode  # noqa: E402

# supplier_name (musi presne sedet s remeslo_price_sources.supplier_name)
# -> (cely text adresy pro zobrazeni, mesto pro geokodovani)
SOURCE_ADDRESSES = {
    "Ptáček-shop.cz": ("Mostecká 58/2, 118 00 Praha - Malá Strana", "Praha"),
    "Aquatopshop.cz": ("Záryby 260, 277 13 Záryby", "Záryby"),
    "HECKL": ("Přemyslova 153, 278 01 Kralupy nad Vltavou", "Kralupy nad Vltavou"),
    "TZBeshop.cz": ("Souběžná 67/19, 636 00 Brno", "Brno"),
    "DEK.cz": ("Tiskařská 10/257, 108 00 Praha 10", "Praha"),
}


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--kontrola", action="store_true", help="jen vypsat, nic nezapisovat")
    grp.add_argument("--apply", action="store_true", help="skutecne zapsat do DB")
    args = ap.parse_args()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, supplier_name, address, latitude, longitude FROM remeslo_price_sources")
            sources = {r["supplier_name"]: r for r in cur.fetchall()}

        for name, row in sources.items():
            if name not in SOURCE_ADDRESSES:
                print(f"PŘESKOČENO (bez známé adresy): {name}")
                continue
            address, city = SOURCE_ADDRESSES[name]
            coords = geocode(conn, city)
            if not coords:
                print(f"CHYBA: geokódování selhalo pro {name} ({city})")
                continue
            lat, lon = coords
            print(f"{name}: {address} -> ({city}) lat={lat} lon={lon}")
            if args.apply:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE remeslo_price_sources SET address=%s, latitude=%s, longitude=%s WHERE id=%s",
                        (address, lat, lon, row["id"]),
                    )
        if args.apply:
            conn.commit()
            print("\nOK - zapsáno.")
        else:
            print("\n[kontrola] Nic nezapsáno (dry-run). Spusť s --apply pro skutečný zápis.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
