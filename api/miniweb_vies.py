"""Overeni DIC / IC DPH v EU (VIES) pro mini-shopy (bot5, 2026-10-03; Robert pres bot3: platne VAT cislo zakaznika z jineho clenskeho statu = DPH se neuctuje).

vies_stav(country, vat_id) -> 'valid' | 'invalid' | 'unavailable'
  * 'valid'        VIES potvrdil platne IC DPH
  * 'invalid'      VIES rika, ze cislo neexistuje / neni platne (nebo format nesedi): DPH se uctuje
  * 'unavailable'  VIES neodpovedelo / clensky stat neni dostupny / chyba site: volajici smi pro FORMALNE platne cislo DPH neuctovat, ale objednavku musi oznacit k RUCNI KONTROLE
Nic se nehada a nepouziva starsi vysledek po vyprseni cache: valid/invalid se drzi 1 hodinu, unavailable 2 minuty (nezahlcovat VIES). Vyhledavani jde na verejne REST rozhrani Evropske komise,
bez klice a bez prihlaseni. Telo odpovedi se nikdy nevraci zakaznikovi (jen stav).
"""
import json
import re
import time
import urllib.request

VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-service/check-vat-number"
CACHE_OK_S = 3600
CACHE_CHYBA_S = 120
_cache = {}
_FORMAT_RE = re.compile(r"^[A-Z0-9]{2,12}\Z")


def vies_kod(country):
    c = (country or "").upper()
    return "EL" if c == "GR" else c


def rozdel(country, vat_id):
    """(kod_zeme_VIES, cislo bez prefixu) z vat_id jako 'SK2020202020' nebo '2020202020'. Cislo musi byt A-Z0-9 (2 az 12 znaku)."""
    kod = vies_kod(country)
    v = re.sub(r"[\s.\-/]", "", str(vat_id or "")).upper()
    if v.startswith(kod):
        v = v[len(kod):]
    return (kod, v) if len(kod) == 2 and _FORMAT_RE.match(v) else (kod, None)


def _dotaz(kod, cislo, timeout=6):
    req = urllib.request.Request(VIES_URL, data=json.dumps({"countryCode": kod, "vatNumber": cislo}).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; LogimanMiniShop/1.0)"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", errors="ignore"))


def vies_stav(country, vat_id, fetch=None, now=None):
    kod, cislo = rozdel(country, vat_id)
    if cislo is None:
        return "invalid"
    t = time.time() if now is None else now
    klic = (kod, cislo)
    hit = _cache.get(klic)
    if hit and hit[0] > t:
        return hit[1]
    try:
        r = (fetch or _dotaz)(kod, cislo)
        if not isinstance(r, dict):
            stav = "unavailable"
        elif r.get("valid") is True:
            stav = "valid"
        elif r.get("valid") is False and not r.get("errorWrappers") and str(r.get("userError") or "VALID").upper() in ("VALID", "INVALID", ""):
            stav = "invalid"
        else:
            stav = "unavailable"              # MS_UNAVAILABLE, TIMEOUT, SERVICE_UNAVAILABLE, MS_MAX_CONCURRENT_REQ ... = nelze rozhodnout
    except Exception:
        stav = "unavailable"
    _cache[klic] = (t + (CACHE_CHYBA_S if stav == "unavailable" else CACHE_OK_S), stav)
    return stav
