"""
IP-based geolokace pro anonymni/agregovany tracking (Robert, 2026-08-22,
pres bot3: "totez nasadit na vandrawee.cz" - stejny princip jako geo-
tracking prave postaveny na /opt/toscanaccio, adaptovany na
konfigurator). Poloha (country/region/city) se pocita JEDNOU na serveru
z lokalni GeoIP databaze - NE externi API, protoze by tam jinak IP
navstevnika musela putovat k treti strane. Uklada se jen VYSLEDEK, nikdy
IP ani hash IP u polohy.

GeoIP databaze (DB-IP City Lite) SE SDILI s /opt/toscanaccio - stejny
VPS, zadny duvod stahovat druhou ~130MB kopii stejnych dat. Oba projekty
bezi jako www-data a soubor je world-readable, viz
/opt/toscanaccio/geodata/README.md pro zdroj/obnovu databaze. Pokud by
se toscanaccio nekdy zrusilo/presunulo, tenhle modul jen tise prestane
vracet polohu (fail-safe, viz nize) - nezpusobi vypadek konfiguratoru.
"""
import os

import maxminddb

MMDB_PATH = os.environ.get(
    "GEOIP_MMDB_PATH",
    "/opt/toscanaccio/geodata/dbip-city-lite.mmdb",
)

_reader = None
_reader_load_attempted = False


def _get_reader():
    global _reader, _reader_load_attempted
    if _reader is not None or _reader_load_attempted:
        return _reader
    _reader_load_attempted = True
    try:
        _reader = maxminddb.open_database(MMDB_PATH)
    except (FileNotFoundError, OSError, ValueError):
        _reader = None
    return _reader


def resolve_geo(ip):
    """Vraci (country, region, city) - kazde bud retezec, nebo None
    (chybejici databaze, privatni/neplatna IP, IP mimo databazi).
    country = ISO 3166-1 alpha-2 kod (napr. "CZ"), region/city =
    anglicky nazev (jedina lokalizace, kterou DB-IP City Lite
    spolehlive vyplnuje pro vsechny zeme)."""
    reader = _get_reader()
    if reader is None or not ip or ip == "unknown":
        return None, None, None
    try:
        result = reader.get(ip)
    except (ValueError, TypeError):
        return None, None, None
    if not result:
        return None, None, None
    country = (result.get("country") or {}).get("iso_code")
    subdivisions = result.get("subdivisions") or []
    region = None
    if subdivisions:
        region = (subdivisions[0].get("names") or {}).get("en")
    city = (result.get("city") or {}).get("names", {}).get("en")
    return country, region, city
