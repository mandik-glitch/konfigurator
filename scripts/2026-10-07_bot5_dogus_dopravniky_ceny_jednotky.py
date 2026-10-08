#!/opt/konfigurator/api/venv/bin/python
"""Dogus dopravniky bez pohonu (bot5, 2026-10-07): PRIHLASENE cteni (GET, zadne zmeny) - u vsech dilu z crawlu zjisti List Price (USD) a jednotku prodeje (hdnStockQuantityUnitValue:
0 = kus, 3000 = 3 m tyc, jine = delkova jednotka v mm), at je pred importem jasne, co je kusove zbozi a co ne (cena po nocnim prepoctu pocita jen kus/tyc 3 m/metraz).
Vstup: backups/2026-10-07_dogus_dopravniky_crawl.json; vystup: backups/2026-10-07_dogus_dopravniky_ceny_jednotky.json + prehled po kategoriich.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_bot5_dogus_dopravniky_ceny_jednotky.py"""
import collections
import importlib.util
import re
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("dpr", os.path.join(HERE, "2026-08-09_dogus_price_recompute.py"))
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)


SHOW_RE = re.compile(r'hdnStockQuantityUnit_(\d+)"\s+value="([^"]*)"')
VALUE_RE = re.compile(r'hdnStockQuantityUnitValue_(\d+)"\s+value="([^"]*)"')


def main():
    crawl = json.load(open(os.path.join(REPO, "backups", "2026-10-07_dogus_dopravniky_crawl.json"), encoding="utf-8"))
    env = D.load_env()
    def prihlas():
        for pokus in range(6):
            try:
                return D.make_session(env["DOGUS_LOGIN_EMAIL"], env["DOGUS_LOGIN_PASSWORD"])
            except Exception as e:                                        # noqa: BLE001 - Dogus obcas zavre spojeni
                print("retry login", e, file=sys.stderr)
                time.sleep(8 * (pokus + 1))
        sys.exit("CHYBA: prihlaseni do Dogusu se nepovedlo")
    opener = prihlas()
    out = {}
    for cid, k in crawl.items():
        if cid in ("160", "162", "163", "221"):
            continue
        for s in k["skupiny"]:
            if not s["variants"]:
                continue
            url = "https://en.doguskalip.com.tr" + s["href"]
            for pokus in range(5):
                try:
                    html = D.fetch(opener, url)
                    break
                except Exception as e:                                    # noqa: BLE001
                    print("retry", url, e, file=sys.stderr)
                    time.sleep(4 * (pokus + 1))
                    if pokus >= 1:
                        opener = prihlas()
            else:
                sys.exit("CHYBA " + url)
            codes = dict(D.NONPROFILE_CODE_RE.findall(html))
            prices = dict(D.NONPROFILE_PRICE_RE.findall(html))
            shows = dict(SHOW_RE.findall(html))
            values = dict(VALUE_RE.findall(html))
            by_code = {c.strip(): idx for idx, c in codes.items()}
            for v in s["variants"]:
                idx = by_code.get(v["stock_code"])
                price = None
                if idx is not None and idx in prices:
                    price = float(prices[idx].replace(".", "").replace(",", "."))
                elif idx is None:
                    pr = D.parse_price_for_code(html, v["stock_code"])
                    price = pr[0] if pr else None
                out[v["stock_code"]] = {"kategorie": cid, "skupina": s["group_id"], "cena_usd": price, "unit": values.get(idx) if idx is not None else None, "show": shows.get(idx) if idx is not None else None,
                                        "nalezeno": idx is not None}
    json.dump(out, open(os.path.join(REPO, "backups", "2026-10-07_dogus_dopravniky_ceny_jednotky.json"), "w"), indent=1)
    by = collections.defaultdict(collections.Counter)
    bez_ceny = collections.Counter()
    for c, v in out.items():
        by[v["kategorie"]][str(v["unit"])] += 1
        if v["cena_usd"] is None:
            bez_ceny[v["kategorie"]] += 1
    for cid in sorted(by, key=int):
        print(cid, crawl[cid]["nazev"][:34], "jednotky:", dict(by[cid]), "bez ceny:", bez_ceny.get(cid, 0))
    print("nenulova jednotka / bez ceny:", [(c, v["kategorie"], v["unit"], v["cena_usd"]) for c, v in out.items() if v["unit"] not in ("0",) or v["cena_usd"] is None][:60])


if __name__ == "__main__":
    main()
