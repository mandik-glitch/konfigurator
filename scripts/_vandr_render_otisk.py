# -*- coding: utf-8 -*-
"""Test "odpovida aktivni render SOUCASNYM razitkum karty?" - sdileno
mezi 2026-09-23_vandr_render_auto_dispatch.py::kandidati() (rozhodne,
jestli kartu zaradit do renderovaci fronty) a
2026-09-22_vandr_card_activate.py (rozhodne, jestli je karta hotova k
aktivaci). Bot3/bot4 2026-09-25, po nalezu na karte #4593 (aktivovana
se STARYMI snimky, protoze aktivace na tohle vubec necekala, jen na
"existuje aktivni snimek") - stejny duvod, proc uz existuje
_vandr_razitka_otisk.py (GLB->razitka) a _render_health_config.py
(teplotni brzda/hlidac) - jeden test, jedno misto, ne treti nezavisla
kopie, ktera by se driv nebo pozdeji rozesla (presne tenhle scenar uz
`vandr_render_auto_dispatch.py` sam jednou zazil, viz komentar tam u
importu `_vandr_razitka_otisk`).

Princip stejny jako `vandr_razitka_glb_otisk`: otisk = sha256 obsahu
VSTUPU v dobe, kdy se z nej neco odvodilo. Tady vstup = RAW retezec
`shop_products.vandr_razitka_json` (ne znovu serializovany JSON - vyhne
se poradi klicu jako zdroji falesne neshody), zapisuje ho
`api/turntable_ingest.py::commit_davku` pri kazdem uspesnem commitu
render davky (`sql/2026-09-23d_shop_products_vandr_render_otisk.sql`).

⚠️ POZOR na smer pouziti: `False` znamena "render NENI (jeste) aktualni
k soucasnym razitkum" - u karet BEZ zadnych razitek, BEZ zadneho
zapsaneho otisku (stary zaznam z doby PRED timhle mechanismem), nebo s
neshodujicim se otiskem vraci VZDY `False` stejne. To je spravne pro
rozhodnuti "zaradit do fronty / (jeste) neaktivovat", ale NIKDY to
nepouzivej jako duvod k DEAKTIVACI uz aktivni karty - stary zaznam s
`render_otisk IS NULL` byl kdysi aktivovan pravem, podle tehdy platnych
pravidel, jen zpetne nejde overit shodu (pravidlo 54: zadny bot
nedeaktivuje kartu sam, natoz kvuli chybejicim historickym datum)."""
import hashlib


def render_odpovida_razitkum(razitka_json, render_otisk):
    """True jen kdyz `render_otisk` byl SPOCITAN ZE SOUCASNYCH
    `razitka_json` (sha256 raw retezce sedi). Chybejici razitka_json
    NEBO chybejici render_otisk vraci False - viz modulovy docstring,
    proc tohle NENI duvod k deaktivaci, jen k "jeste neaktivovat"."""
    if not razitka_json or not render_otisk:
        return False
    return hashlib.sha256(razitka_json.encode("utf-8")).hexdigest() == render_otisk
