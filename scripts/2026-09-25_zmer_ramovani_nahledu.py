#!/usr/bin/env python3
"""Změří, jak velkou část rámu zabírá sestava na náhledech karet.

Robert 2026-09-25: "musí mít ty rendery všechny stejně velké stejný formát".
Tenhle skript je MĚŘÍTKO té podmínky - pouští se PŘED opravou i PO ní a
porovnává se stejnou metodou, aby "je to opravené" nebylo jen dojem z oka.

Metoda detekce obsahu: pozadí renderu je čistě SVISLÝ přechod (doloženo v
PRODUKTOVE_RENDERY.md - levá a pravá hrana se v žádném řádku neliší víc než
o 4/255). Proto je medián každého řádku roven pozadí toho řádku a všechno,
co se od něj dost liší, je sestava. Nepotřebuje tedy znát barvu pozadí ani
alfa kanál.

POZOR na past: `_na_kanonicky_pomer()` rozšiřuje čtverec na 4:3 roztažením
KRAJNÍCH SLOUPCŮ. Když se sestava dotýká hrany čtverce, rozmázne se přes
celý dopočítaný pruh až k hraně rámu - a vyjde šířka 100 %. Taková hodnota
znamená "oříznuto/rozmazáno", ne "pěkně vyplněný rám".

Spouštět na serveru:
    /opt/konfigurator/api/venv/bin/python3 scripts/2026-09-25_zmer_ramovani_nahledu.py
"""
import glob
import os
import sys

import numpy as np
from PIL import Image

THUMB_DIR = "/opt/konfigurator/webapp/katalog/thumbnails"
PRAH_ODLISNOSTI = 18  # součet |RGB - medián řádku|, nad tím je to sestava


def bbox_obsahu(cesta):
    """Vrátí (x0, x1, y0, y1, w, h) obalového obdélníku sestavy, nebo None."""
    with Image.open(cesta) as im:
        a = np.asarray(im.convert("RGB")).astype(np.int16)
    h, w, _ = a.shape
    pozadi = np.median(a, axis=1, keepdims=True)
    maska = np.abs(a - pozadi).sum(axis=2) > PRAH_ODLISNOSTI
    ys, xs = np.where(maska)
    if len(xs) == 0:
        return None
    return xs.min(), xs.max(), ys.min(), ys.max(), w, h


def main():
    soubory = sorted(glob.glob(os.path.join(THUMB_DIR, "product-*.jpg")))
    if not soubory:
        print("Žádné náhledy v %s" % THUMB_DIR)
        return 1

    formaty = {}
    mereni = []
    for f in soubory:
        try:
            with Image.open(f) as im:
                formaty[im.size] = formaty.get(im.size, 0) + 1
            r = bbox_obsahu(f)
        except Exception as e:  # poškozený soubor nesmí shodit celé měření
            print("  ! %s: %s" % (os.path.basename(f), e))
            continue
        if r is None:
            continue
        x0, x1, y0, y1, w, h = r
        mereni.append(
            {
                "soubor": os.path.basename(f),
                "sirka_pct": 100.0 * (x1 - x0 + 1) / w,
                "vyska_pct": 100.0 * (y1 - y0 + 1) / h,
                "u_kraje": bool(x0 <= 1 or x1 >= w - 2 or y0 <= 1 or y1 >= h - 2),
            }
        )

    print("=== FORMÁTY SOUBORŮ ===")
    for velikost, pocet in sorted(formaty.items(), key=lambda kv: -kv[1]):
        print("  %4dx%-4d  %3d souborů" % (velikost[0], velikost[1], pocet))
    print("  -> podmínka 'stejný formát' splněna, jen když je řádek JEDEN\n")

    sirky = [m["sirka_pct"] for m in mereni]
    u_kraje = [m for m in mereni if m["u_kraje"]]
    print("=== VELIKOST SESTAVY V RÁMU (%d náhledů) ===" % len(mereni))
    print("  min %.1f %%   max %.1f %%   průměr %.1f %%   rozptyl %.1f p.b."
          % (min(sirky), max(sirky), sum(sirky) / len(sirky), max(sirky) - min(sirky)))
    print("  -> podmínka 'stejně velké' splněna, jen když je rozptyl malý\n")

    print("=== DOTÝKÁ SE HRANY RÁMU (oříznuté/rozmazané): %d z %d ==="
          % (len(u_kraje), len(mereni)))
    for m in sorted(u_kraje, key=lambda x: -x["sirka_pct"])[:10]:
        print("  %-22s šířka %5.1f %%  výška %5.1f %%"
              % (m["soubor"], m["sirka_pct"], m["vyska_pct"]))
    if not u_kraje:
        print("  žádné - v pořádku")

    print("\n=== NEJMENŠÍ V RÁMU ===")
    for m in sorted(mereni, key=lambda x: x["sirka_pct"])[:5]:
        print("  %-22s šířka %5.1f %%" % (m["soubor"], m["sirka_pct"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
