"""Cena v EUR pro mini-shop (bot5, 2026-10-03; Robert: "žádná cena se skrývat nebude", SK shop ukazuje EUR bez DPH, B2B).

Cista vrstva nad cenami v Kc (stul_shop: `price.net`, `options.*.on.price_delta`), BEZ Flasku a bez zapisu do DB:
  cena_eur = Kc / kurz * (1 + marze_pct/100), zaokrouhleno na CELE EUR (pulky nahoru).
Kurz a marze se NIKDY nedavaji do kodu (WORKFLOW pravidlo 9):
  * marze = `miniweb_shops.margin_pct` (admin / `scripts/miniweb_shop.py --margin-pct`), bez nastavene marze = ZADNA cena,
  * kurz = `miniweb_shops.eur_rate` (Kc za 1 EUR, rucne nastaveny v adminu), a kdyz neni nastaven, zivy kurz Fio "Devizove kurzy / Prodej" (EUR),
    cache jen na kratkou dobu, ZADNY fallback na starou hodnotu: kurz neni = cena neni (`None`), nikdy odhad.
Mini-shop se pozna podle hostu (`primary_domain` storefrontu) a `price_mode = 'shown'`, `currency = 'EUR'`.
"""
import re
import time
import urllib.request
from decimal import Decimal, ROUND_HALF_UP

import fio_rate

CACHE_OK_S = 1800
CACHE_CHYBA_S = 60
_cache = {}  # mena -> (platne_do, kurz | None)


def _fio_prodej(mena):
    """Zivy kurz Kc za 1 jednotku meny, sloupec Prodej (stejna tabulka jako fio_rate pro USD). Vyhodi vyjimku, kdyz se nenajde."""
    req = urllib.request.Request(fio_rate.FIO_RATE_URL, headers={"User-Agent": fio_rate.UA})
    html = urllib.request.urlopen(req, timeout=5).read().decode("utf-8", errors="ignore")
    rx = re.compile(r'<td class="tleft"><strong>%s</strong></td>\s*<td class="tright">[\d,]+</td>\s*<td class="tright">([\d,]+)</td>' % re.escape(mena))
    m = rx.search(html)
    if not m:
        raise RuntimeError("Kurz %s/CZK se na fio.cz nenasel" % mena)
    return float(m.group(1).replace(",", "."))


def zivy_kurz(mena="EUR", fetch=None, now=None):
    """Kc za 1 EUR z Fio, nebo None. Uspech se drzi CACHE_OK_S, neuspech CACHE_CHYBA_S (nezahlcovat Fio); zadna starsi hodnota se po vyprseni nepouzije."""
    t = time.time() if now is None else now
    hit = _cache.get(mena)
    if hit and hit[0] > t:
        return hit[1]
    try:
        k = (fetch or _fio_prodej)(mena)
        k = float(k) if k and float(k) > 0 else None
    except Exception:
        k = None
    _cache[mena] = (t + (CACHE_OK_S if k else CACHE_CHYBA_S), k)
    return k


def _kladne(v):
    try:
        d = Decimal(str(v))
    except Exception:
        return None
    return d if d.is_finite() and d > 0 else None


def nastaveni(shop, fetch=None):
    """{currency, rate, margin_pct} pro shop s price_mode 'shown' a menou EUR, jinak None. None i kdyz chybi marze nebo kurz (cena se pak nevydava)."""
    if not shop or shop.get("price_mode") != "shown" or shop.get("currency") != "EUR":
        return None
    marze = shop.get("margin_pct")
    if marze is None:
        return None
    try:
        marze = Decimal(str(marze))
    except Exception:
        return None
    if not marze.is_finite() or marze < 0 or marze > 500:
        return None
    kurz = _kladne(shop.get("eur_rate")) or _kladne(zivy_kurz("EUR", fetch=fetch))
    if kurz is None:
        return None
    return {"currency": "EUR", "rate": kurz, "margin_pct": marze}


def cena_eur(czk, cfg):
    """Cele EUR (int) z Kc bez DPH, nebo None (bez ceny / bez nastaveni). Zaporne castky (sleva v price_delta) se prevadeji se znamenkem."""
    if czk is None or cfg is None or isinstance(czk, bool):
        return None
    try:
        d = Decimal(str(czk))
    except Exception:
        return None
    if not d.is_finite():
        return None
    eur = d / cfg["rate"] * (1 + cfg["margin_pct"] / 100)
    return int(eur.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def na_eur(out, cfg):
    """Odpoved resolve v Kc -> v EUR (kopie neni potreba, volajici ma vlastni deepcopy). Bez nastaveni se cena odstrani (nikdy se nevrati Kc pod hlavickou EUR):
    `price` -> {net, vat_rate: 0, gross: net, currency: 'EUR', rate, margin_pct}, `options.*.on.price_delta` -> EUR, jinde (alt, offers) se Kc nemeni, jen kdyz tam cena je."""
    price = out.get("price")
    if cfg is None:                                       # bez nastaveni zadna cena ani priplatek (a nikdy neprevedena Kc): price_delta pryc u VSECH voleb, ne jen u 'on' (externi revize 2026-10-03, #7)
        out.pop("price", None)
        for o in (out.get("options") or {}).values():
            if isinstance(o, dict):
                for v in o.values():
                    if isinstance(v, dict):
                        v.pop("price_delta", None)
        return out
    if isinstance(price, dict) and price.get("net") is not None:
        net = cena_eur(price["net"], cfg)
        out["price"] = {"net": net, "vat_rate": 0, "gross": net, "currency": "EUR"} if net is not None else None
    for o in (out.get("options") or {}).values():
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, dict) and "price_delta" in v:
                    v["price_delta"] = cena_eur(v["price_delta"], cfg) or 0
    return out


# ---------------------------------------------------------------------------------------------------------------- vyhledani shopu podle hostu
_SHOPY = {}  # host -> (platne_do, radek miniweb_shops | None)
CACHE_SHOP_S = 60


def radek_shopu(host, get_conn, now=None):
    """Radek miniweb_shops pro host (primary_domain nebo alias z storefront_hosts), nebo None. Cache 60 s (resolve se vola casto)."""
    host = (host or "").split(":")[0].strip().lower()
    t = time.time() if now is None else now
    hit = _SHOPY.get(host)
    if hit and hit[0] > t:
        return hit[1]
    row = None
    try:
        cur = get_conn().cursor()
        cur.execute("SELECT m.price_mode, m.currency, m.margin_pct, m.eur_rate FROM miniweb_shops m JOIN car_storefronts s ON s.id = m.storefront_id WHERE s.primary_domain=%s", (host,))
        row = cur.fetchone()
        if row is None:
            cur.execute("SELECT m.price_mode, m.currency, m.margin_pct, m.eur_rate FROM storefront_hosts h JOIN miniweb_shops m ON m.storefront_id = h.storefront_id WHERE h.host=%s", (host,))
            row = cur.fetchone()
    except Exception:
        row = None
    _SHOPY[host] = (t + CACHE_SHOP_S, row)
    return row


def pro_host(host, get_conn, fetch=None, now=None):
    """(aktivni, cfg): aktivni = host je mini-shop s price_mode 'shown' (odpoved resolve se ma prepocitat do EUR),
    cfg = nastaveni, nebo None kdyz chybi marze/kurz (pak se cena odstrani). Jiny host / shop se skrytou cenou = (False, None), nic se nemeni."""
    row = radek_shopu(host, get_conn, now=now)
    if not row or row.get("price_mode") != "shown":
        return False, None
    return True, nastaveni(row, fetch=fetch)
