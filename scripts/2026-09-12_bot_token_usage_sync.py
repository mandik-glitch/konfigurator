#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scrapuje bot-telemetry OTel collector (viz /opt/bot-telemetry) a
akumuluje spotřebu tokenů/nákladů podle `bot.id` do MySQL
(`bot_token_usage`, viz sql/2026-09-12_bot_token_usage.sql). Navíc
(2026-09-17, Robert primo) zapisuje "skutecne aktualni model/effort"
do `bots.current_model`/`current_effort` (sql/2026-09-17_bots_current_
model_effort.sql) - viz komentar u `UPDATE bots` v sync() nize - a
plni jemnozrnnou historii `bot_token_usage_history` (sql/2026-09-17b_
bot_token_usage_history_intraday.sql, viz snapshot_historie()) pro
graf v Prehledy > Boti s meritky 5min az 1 mesic (api/bots.py
RANGE_CONFIG).

Robert (pres bot3, 2026-09-12): sloupec "Tokeny" v administraci
(Přehledy > Boti). Skutecná data zacnou chodit az po cutover
2026-09-16 22:00 (viz /opt/bot-telemetry/RUNBOOK_CUTOVER.md) - do te
doby tenhle skript bezi (spousti se cron/systemd timer kazde 2 min),
jen nema co scrapovat (collector nema zadne aktivni serie) a je to
naprosto v poradku - vypise "0 serii nalezeno" a skonci.

PROC DELTY, NE PRIMY PREPIS: Prometheus Counter kazde bot session
zacina znovu od 0 pri KAZDEM restartu `claude` procesu (novy
session.id = nova casova rada). Naivni "prepsat bot_token_usage.
tokens_total scrapovanou hodnotou" by po kazdem restartu session
ZTRATILA historii pred restartem. Misto toho: pro kazdou JEDNOTLIVOU
casovou radu (identifikovanou presnym otiskem vsech jejich labelu,
`series_key`) se pamatuje POSLEDNI VIDENA hodnota
(`bot_token_usage_series`); pri kazdem scrape se spocita delta = nova
hodnota - posledni znama, a POKUD JE KLADNA (normalni pripad, counter
jen roste), prictem se k bezicimu souctu za bota. Zapornou deltu
(counter spadl - session s TIMTO presnym session.id znovu bezela od
nuly, coz je nezvykle ale teoreticky mozne) beru jako "novy zacatek
teto rady" - pricte se cela NOVA hodnota (ne delta), zadna historie se
tim neztrati, jen se nezapocita neexistujici "zaporny render".

POUZITI
-------
    api/venv/bin/python3 scripts/2026-09-12_bot_token_usage_sync.py         # bezny beh
    api/venv/bin/python3 scripts/2026-09-12_bot_token_usage_sync.py -v      # + vypis vsech videnych metrik (diagnostika prvniho realneho behu)
"""
import argparse
import hashlib
import os
import re
import sys
import urllib.request
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import _env  # noqa: E402

METRICS_URL = "http://127.0.0.1:9464/metrics"

# Presne nazvy nejsou 100% jiste, dokud nezacne chodit realna data (zadna
# bot session jeste neposilala pri navrhu tehle infrastruktury) - OTel->
# Prometheus prevod pripojuje k Counter metrikam typicky "_total", u
# Gauge ne. Prefix-match je proto schvalne benevolentnejsi nez presna
# shoda, at malá odchylka v presnem nazvu nerozbije sync ticho.
VZORY = {
    "tokens": re.compile(r"^claude_code_token_usage\w*(\{|\s)"),
    "cost": re.compile(r"^claude_code_cost_usage\w*(\{|\s)"),
}

# hodnota v Prometheus expozici muze byt i "NaN"/"+Inf"/"-Inf" - takove
# radky RADEK_RE neodchyti (float() by na nich stejne spadl), coz je v
# poradku, proste se preskoci.
RADEK_RE = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)\{([^}]*)\}\s+([0-9eE.+-]+)\s*$')
LABEL_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"')


def _parsuj_radek(radek):
    """'metric_name{k="v",k2="v2"} 123.45' -> (metric_name, {k:v,...}, 123.45) nebo None."""
    radek = radek.strip()
    if not radek or radek.startswith("#"):
        return None
    m = RADEK_RE.match(radek)
    if not m:
        return None
    nazev, labely_raw, hodnota_raw = m.groups()
    try:
        hodnota = float(hodnota_raw)
    except ValueError:
        return None
    labely = {k: v.replace('\\"', '"').replace("\\\\", "\\") for k, v in LABEL_RE.findall(labely_raw)}
    return nazev, labely, hodnota


def stahni_metriky():
    with urllib.request.urlopen(METRICS_URL, timeout=10) as r:
        return r.read().decode("utf-8", errors="replace")


def zpracuj(text, verbose=False):
    """Vrati [(series_key, bot_id, metrika, hodnota, labely), ...] pro
    vsechny radky, ktere odpovidaji nasim vzorum A maji label bot_id."""
    vysledky = []
    videne_nazvy = set()
    for radek in text.splitlines():
        rozparsovano = _parsuj_radek(radek)
        if not rozparsovano:
            continue
        nazev, labely, hodnota = rozparsovano
        videne_nazvy.add(nazev)
        bot_id = labely.get("bot_id")
        if not bot_id:
            continue
        for metrika, vzor in VZORY.items():
            if vzor.match(radek):
                # Plny retezec nazev+labely muze byt (a s realnymi daty
                # 2026-09-17 skutecne je, ~700 znaku) delsi nez
                # `bot_token_usage_series.series_key` varchar(191) - je to
                # PRIMARY KEY, nejde jen widenout bez rizika (index limit).
                # SHA256 hex (64 znaku) zachova jedinecnost per-casova-rada
                # a bezpecne se vejde.
                syrovy_klic = radek.split(" ", 1)[0]
                series_key = hashlib.sha256(syrovy_klic.encode("utf-8")).hexdigest()
                vysledky.append((series_key, bot_id, metrika, hodnota, labely))
                break
    if verbose:
        print("Vsechny nazvy metrik videne v expozici (%d):" % len(videne_nazvy))
        for n in sorted(videne_nazvy):
            print("  ", n)
    return vysledky


def sync(conn, polozky):
    aktualizovani_boti = set()
    now = datetime.now()
    with conn.cursor() as cur:
        for series_key, bot_id, metrika, hodnota, labely in polozky:
            cur.execute(
                "SELECT last_seen_value FROM bot_token_usage_series WHERE series_key=%s",
                (series_key,),
            )
            row = cur.fetchone()
            # OPRAVA 2026-09-17 (bot9, nalez Robert): "last_seen_value"
            # ted znamena BEZICI MAXIMUM celé série, ne "posledni videnou
            # hodnotu" - puvodni logika ("kdyz hodnota < predtim, counter
            # spadl na nulu, pricti celou hodnotu znovu") predpokladala,
            # ze metrika je vzdy cistě monotonni v ramci jedne session -
            # NENI. Ziva data ukazala poklesy BEZ restartu procesu
            # (stejny session_id, hodnota dolu a pak zas nahoru) - kazdy
            # takovy poklesl byl mylne vyhodnocen jako "nova session" a
            # cela hodnota se pricetla ZNOVA, opakovane pri kazdem 2min
            # tiku - u vsech 7 botu nafouklo tokeny/cenu 10-37x behem
            # jednoho dne. Bezici maximum tohle nemuze udelat: pokles se
            # jen ignoruje (delta=0, ulozena hodnota se NESNIZI), teprve
            # rust NAD dosavadni maximum se pripocte - jedina cena je
            # mala konzervativni podhodnocenost v teoretickem prípade
            # poklesu+opetovneho rustu presne na stejnou uroven, mnohem
            # bezpecnejsi nez puvodni divoke nadhodnocovani.
            if row is None:
                delta = hodnota
                novy_max = hodnota
            else:
                predtim = float(row["last_seen_value"])
                delta = hodnota - predtim if hodnota > predtim else 0
                novy_max = max(predtim, hodnota)
            cur.execute(
                "INSERT INTO bot_token_usage_series (series_key, bot_id, metric, last_seen_value, last_seen_at) "
                "VALUES (%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE last_seen_value=VALUES(last_seen_value), last_seen_at=VALUES(last_seen_at)",
                (series_key, bot_id, metrika, novy_max, now),
            )
            if delta <= 0:
                continue
            # "Skutecne aktualni model/effort" (Robert, 2026-09-17): jen
            # `query_source="main"` (hlavni konverzacni smycka, ne
            # subagenti/auxiliary volani, ktera muzou bezet na uplne
            # jinem, levnejsim modelu - viz tokenova disciplina bod 7).
            # Aktualizuje se JEN pri KLADNE delte (stejna podminka jako
            # u samotneho souctu vyse) - to je zamerne: kdyz bot behem
            # sve session prepne model (/model, /fast), stara serie
            # prestane rust, nova zacne - "posledni serie, ktera fakt
            # jeste roste" je spolehlivejsi signal "co bot POUZIVA TED"
            # nez "posledni videna v expozici" (OTel collector muze
            # stare, uz neaktivni serie drzet v pameti donekonecna).
            if labely.get("query_source") == "main":
                cur.execute(
                    "UPDATE bots SET current_model=%s, current_effort=%s, current_model_updated_at=%s WHERE bot_id=%s",
                    (labely.get("model"), labely.get("effort"), now, bot_id),
                )
            sloupec = "tokens_total" if metrika == "tokens" else "cost_usd_total"
            cur.execute(
                "INSERT INTO bot_token_usage (bot_id, %s, last_synced_at) VALUES (%%s,%%s,%%s) "
                "ON DUPLICATE KEY UPDATE %s = %s + VALUES(%s), last_synced_at=VALUES(last_synced_at)"
                % (sloupec, sloupec, sloupec, sloupec),
                (bot_id, delta, now),
            )
            aktualizovani_boti.add(bot_id)
    conn.commit()
    return aktualizovani_boti


# Kolik dni jemnozrnne historie (bot_token_usage_history) se drzi, nez
# se smazou stare radky (viz snapshot_historie nize) - Robert nezadal
# presne cislo ("30-90 dni" navrhl bot3), 60 je stred rozsahu. Tabulka
# by jinak rostla bez konce (2min interval x N botu x navzdy, viz
# WORKFLOW.md pravidlo 28 "pojistka na vrstve, kde vznika skoda").
RETENCE_DNI = 60


def snapshot_historie(conn):
    """PRIDA (ne prepise) radek v bot_token_usage_history pro KAZDEHO
    bota, ktery ma zaznam v bot_token_usage, pri KAZDEM behu syncu
    (~2min timer) - viz sql/2026-09-17b_bot_token_usage_history_
    intraday.sql. Puvodni verze delala jen UPSERT "dnesniho" radku
    (jedna tecka/den/bota) - Robert po prvnim zivem screenshotu chtel
    vnitrodenni pohyb + meritka 5min az 1 mesic (viz RANGE_CONFIG v
    api/bots.py), coz vyzaduje kazdy tik zvlast', ne jeden prepisovany
    radek. Zaroven maze radky starsi nez RETENCE_DNI - bez toho by
    tabulka rostla bez konce."""
    with conn.cursor() as cur:
        cur.execute("SELECT bot_id, tokens_total, cost_usd_total FROM bot_token_usage")
        radky = cur.fetchall()
        now = datetime.now()
        for r in radky:
            cur.execute(
                "INSERT INTO bot_token_usage_history (bot_id, ts, tokens_total_snapshot, cost_usd_total_snapshot) "
                "VALUES (%s, %s, %s, %s)",
                (r["bot_id"], now, r["tokens_total"], r["cost_usd_total"]),
            )
        cur.execute(
            "DELETE FROM bot_token_usage_history WHERE ts < DATE_SUB(NOW(), INTERVAL %s DAY)",
            (RETENCE_DNI,),
        )
    conn.commit()
    return len(radky)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-v", "--verbose", action="store_true",
                     help="vypsat vsechny videne nazvy metrik (diagnostika)")
    a = ap.parse_args()

    try:
        text = stahni_metriky()
    except Exception as e:
        print("VAROVANI: nelze stahnout %s (%r) - collector nejspis nebezi." % (METRICS_URL, e))
        return 1

    polozky = zpracuj(text, verbose=a.verbose)
    env = _env.load_env()
    conn = _env.get_conn(env)
    try:
        if not polozky:
            print("0 relevantnich casovych rad (zadny bot_id label na claude_code_token_usage/"
                  "claude_code_cost_usage) - pred cutoverem 2026-09-16 22:00 je to ocekavane.")
        else:
            aktualizovano = sync(conn, polozky)
            print("Aktualizovano %d bot(u): %s" % (len(aktualizovano), ", ".join(sorted(aktualizovano))))
        # Jemnozrnna historie (viz snapshot_historie docstring) bezi
        # VZDY, kdyz se collector podarilo stahnout - i v behu bez
        # zadne cerstve delty - kazdy tik ma svuj vlastni radek.
        pocet_snapshotu = snapshot_historie(conn)
        if pocet_snapshotu:
            print("Historie: pridan radek pro %d bot(u)." % pocet_snapshotu)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
