#!/usr/bin/env python3
"""Zdrojove retezce serveru k prekladu do dalsiho jazyka mini-shopu (bot16, 2026-10-07; Robert: "kopii shopu v nemcine" + madarstina).

Z KODU (stul_shop, stul_shop_sse, stul_ovladani_verejne, miniweb_objednavky, miniweb) vytahne vsechny zakaznicke retezce, ktere vydava server, a zapise je jako soubory k vyplneni
  docs/jazyky/<jazyk>/01_stul_texty.json  02_stul_zpravy.json  03_stul_info_sablony.json  04_ovladani.json  05_objednavky.json
Kazda polozka: {id, typ (text | plural), placeholdery, cs, en, sk, <jazyk>: ""}. ZNENI pise bot7 (prosty JSON, vyplnit pole <jazyk>). Hotove soubory:
  scripts/miniweb_jazyk_sestav.py --lang <jazyk> [--apply]      overi a zapise api/jazyky/<jazyk>.json
  scripts/miniweb_jazyk_parita.py --lang <jazyk> [--ref sk]      jazykova uplnost napric vrstvami
Znovuspusteni je bezpecne: uz vyplnene hodnoty (z existujicich souboru nebo z hotove sady) zustanou, pridaji se jen nove retezce; zastarale id se vypisou.
Postup a kontrolni seznam: docs/jazyky/README.md.

Pouziti (z korene repa; potrebuje api/.env pro import aplikace, nic se nezapisuje do DB):
  api/venv/bin/python3 scripts/miniweb_jazyk_zdroj.py --lang de
  api/venv/bin/python3 scripts/miniweb_jazyk_zdroj.py --lang hu [--vystup docs/jazyky/hu] [--api /cesta/k/api]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _jazyky_zdroj as Z  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Zdrojove retezce serveru k prekladu (soubory pro bot7).")
    ap.add_argument("--lang", required=True, help="cilovy jazyk (dvoupismenny kod: de, hu, pl ...)")
    ap.add_argument("--vystup", help="slozka souboru (vychozi docs/jazyky/<jazyk>)")
    ap.add_argument("--api", help="kopie API, ze ktere se cte kod (vychozi zive repo)")
    ap.add_argument("--bez-sady", action="store_true", help="nepredvyplnovat z uz hotove sady api/jazyky/<jazyk>.json")
    a = ap.parse_args(argv)
    jz0 = Z.jazyky_modul(a.api)
    if not jz0.KOD_RE.match(a.lang) or a.lang in jz0.VESTAVENE:
        print(f"CHYBA: jazyk {a.lang!r} musi byt dvoupismenny kod jiny nez {', '.join(jz0.VESTAVENE)} (ty jsou v kodu).", file=sys.stderr)
        return 2
    if a.lang not in jz0.ABECEDY:
        print(f"CHYBA: jazyk {a.lang!r} nema abecedu v api/jazyky.py (ABECEDY) - doplnte jeden radek (povolena pismena jazyka) a PLURAL_PRO_JAZYK.", file=sys.stderr)
        return 2
    mods = Z.importuj_api(a.api)
    jz = mods["jazyky"]
    polozky = Z.polozky_z_kodu(mods)
    slozka = os.path.abspath(a.vystup or os.path.join(Z.DOCS, a.lang))
    sada = None if a.bez_sady else jz.nacti(a.lang)
    pocty, zastarale = Z.zapis_zdroj(polozky, a.lang, slozka, jz, sada=sada)
    celkem = sum(pocty.values())
    print(f"Jazyk {a.lang} ({jz.NAZVY_JAZYKU.get(a.lang, a.lang)}), pravidlo plurálu: {jz.PLURAL_PRO_JAZYK.get(a.lang, 'one_other')}")
    for sekce, nazev in Z.SOUBORY_SEKCI.items():
        print(f"  {nazev:30s} {pocty[sekce]:4d} položek")
    print(f"Celkem {celkem} položek -> {slozka}")
    if sada:
        print("Předvyplněno z hotové sady api/jazyky/%s.json (existující hodnoty v souborech mají přednost)." % a.lang)
    if zastarale:
        print(f"POZOR: {len(zastarale)} id v souborech už v kódu není (zastaralé, v nových souborech chybí): " + "; ".join(zastarale[:6]) + (" ..." if len(zastarale) > 6 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
