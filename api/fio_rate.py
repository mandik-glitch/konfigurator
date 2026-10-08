"""Sdilený zdroj živého kurzu USD/CZK "Fio banka, Devizové kurzy, Prodej".

Vytaženo z `scripts/2026-08-09_dogus_price_recompute.py` (bot16,
2026-09-24, Robert přes bot3 - "přidat sloupec hned u Dogus, přepočítanou
cenu USD s aktuálním kurzem FIO devize prodej", WORKFLOW.md pravidlo 52
"nic se neodkládá"). Nový admin sloupec "Cena v Kč (živý kurz)" v
záložce Ceny profilů (`webapp/admin/js/ceny.js`, endpoint
`GET /api/admin/profily/fio-rate` v `api/admin_profily.py`) potřebuje
PŘESNĚ stejnou definici "devize prodej" jako týdenní přepočet cen
(`scripts/2026-08-09_dogus_price_recompute.py`) - jedno místo pravdy pro
obě volající strany, aby se definice nikdy nerozjela.

WORKFLOW.md pravidlo 9 - kurz je VŽDY živě stažený, NIKDY hardcoded a
NIKDY nepadá zpátky na starou/odhadnutou hodnotu: když se kurz nepodaří
najít/stáhnout, `fetch_fio_usd_czk_sell_rate()` vyhodí `RuntimeError` a
KAŽDÝ volající (týdenní skript i admin endpoint) to musí respektovat -
žádná cena/přepočet se špatným kurzem, misto toho se má zobrazit
explicitní stav "nedostupné".
"""
import re
import urllib.request

UA = "Mozilla/5.0 (compatible; LogimanKonfiguratorPairingSync/1.0; +https://logiman.cz)"

# Veřejná tabulka "Devizové kurzy" (sloupce Nákup/Prodej) na fio.cz,
# žádné přihlášení netřeba. Ověřeno ručně 2026-08-10 (curl), stejná
# tabulka je i v patičce většiny stránek fio.cz jako HTML fragment
# "barbox-listek".
FIO_RATE_URL = "https://www.fio.cz/akcie-investice/dalsi-sluzby-fio/devizove-konverze"
FIO_USD_ROW_RE = re.compile(
    r'<td class="tleft"><strong>USD</strong></td>\s*'
    r'<td class="tright">[\d,]+</td>\s*<td class="tright">([\d,]+)</td>'
)


def fetch_fio_usd_czk_sell_rate(timeout=20):
    """Stáhne aktuální kurz USD/CZK "Prodej" (kolik Kč bance zaplatíme za
    1 USD) z veřejně dostupné tabulky na fio.cz. ŽÁDNÝ fallback na
    hardcoded/starou hodnotu (WORKFLOW.md pravidlo 9) - když se kurz
    nenajde/nestáhne, vyhodí výjimku; volající kód to MUSÍ zobrazit/
    zpracovat jako "nedostupné", nikdy nepoužít starý/odhadnutý kurz
    místo něj."""
    req = urllib.request.Request(FIO_RATE_URL, headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", errors="ignore")
    m = FIO_USD_ROW_RE.search(html)
    if not m:
        raise RuntimeError(
            "Kurz USD/CZK se na fio.cz nepodařilo najít (změnila se struktura stránky "
            f"na {FIO_RATE_URL}?)."
        )
    return float(m.group(1).replace(",", "."))
