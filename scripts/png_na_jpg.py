#!/usr/bin/env python3
"""Dávkový převod renderů PNG -> JPEG z příkazové řádky.

Robert 2026-09-09: "tak udelej prevadec z png na jpg".

Průhledné pozadí (HDRI mapa skrytá před kamerou, viz PRODUKTOVE_RENDERY.md
pravidlo 11) se podloží zvolenou barvou - JPEG alfu neumí a bez podložení
by z ní udělal černou. Vlastní práci dělá api/png_jpg.py, tohle je jen
obal pro ruční/dávkové použití.

Použití:
    python3 scripts/png_na_jpg.py render.png
    python3 scripts/png_na_jpg.py /cesta/ke/slozce --pozadi "#f5f5f5"
    python3 scripts/png_na_jpg.py /cesta/ke/slozce --kvalita 95 --smazat-png

Barva pozadí: "bílá" (výchozí), "černá", "šedá", "#RRGGBB" nebo "r,g,b".
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))

import png_jpg  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="Převod PNG renderů na JPEG.")
    p.add_argument("cesta", help="soubor .png nebo složka s .png soubory")
    p.add_argument("--pozadi", default="bílá",
                   help='čím podložit průhledná místa: "bílá"/"černá"/"šedá"/"#RRGGBB"/"r,g,b"')
    p.add_argument("--kvalita", type=int, default=png_jpg.VYCHOZI_KVALITA,
                   help=f"JPEG kvalita 1-100 (výchozí {png_jpg.VYCHOZI_KVALITA})")
    p.add_argument("--smazat-png", action="store_true",
                   help="po úspěšném převodu smazat zdrojový PNG")
    args = p.parse_args()

    try:
        pozadi = png_jpg.parse_barva(args.pozadi)
    except ValueError as e:
        print("CHYBA:", e)
        return 2

    if not os.path.exists(args.cesta):
        print("CHYBA: cesta neexistuje:", args.cesta)
        return 2

    if os.path.isdir(args.cesta):
        hotovo = png_jpg.prevod_slozky(args.cesta, pozadi=pozadi,
                                       kvalita=args.kvalita, smazat_png=args.smazat_png)
        if not hotovo:
            print("Ve složce není žádný .png soubor.")
            return 1
        for zdroj, cil in hotovo:
            print(f"  {os.path.basename(zdroj)} -> {os.path.basename(cil)} "
                  f"({os.path.getsize(cil) // 1024} kB)")
        print(f"Hotovo: {len(hotovo)} souborů, pozadí RGB{pozadi}, kvalita {args.kvalita}.")
        return 0

    cil = png_jpg.png_na_jpg(args.cesta, pozadi=pozadi, kvalita=args.kvalita)
    if args.smazat_png:
        os.remove(args.cesta)
    print(f"{args.cesta} -> {cil} ({os.path.getsize(cil) // 1024} kB), "
          f"pozadí RGB{pozadi}, kvalita {args.kvalita}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
