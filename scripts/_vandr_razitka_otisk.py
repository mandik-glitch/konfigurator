# -*- coding: utf-8 -*-
"""Otisk Vandr razitek = sha256(GLB) + VERZE PRAVIDLA (bot10 2026-09-24).

Sdileno mezi scripts/2026-09-23_vandr_razitka_spocitat.py (zapis
vandr_razitka_glb_otisk / vandr_razitka_chyba_otisk) a
scripts/2026-09-23_vandr_razitka_auto_dispatch.py (porovnani, co prepocitat).
OBE strany musi pocitat TOTEZ, jinak timer prepocitava donekonecna
(spocitat zapise X, dispatch ceka Y) nebo naopak nikdy.

Proc verze: otisk jen ze souboru znamena, ze zmena PRAVIDLA rozmisteni
(napr. Robertovo pravidlo poctu podle poli, 2026-09-24) sama o sobe zadny
prepocet nevyvola - karty by zustaly s razitky podle stareho pravidla,
dokud by nekdo nenahral novy GLB. Zvednuti PRAVIDLO_VERZE zneplatni otisk
VSECH karet najednou -> razitka-dispatch je prepocita, render-dispatch
prerenderuje. Proto se verze zveda jen VEDOME (po schvaleni Robertem),
ne pri kazdem refaktoru.

Vysledek zustava 64 hex znaku (sloupce jsou char(64)).
"""
import hashlib

PRAVIDLO_VERZE = "2026-09-24-pole-B-okraj20-v13"


def sha256_souboru(cesta):
    h = hashlib.sha256()
    with open(cesta, "rb") as fh:
        for blok in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(blok)
    return h.hexdigest()


def otisk_glb(cesta):
    """sha256( sha256(GLB) | PRAVIDLO_VERZE ) - 64 hex."""
    return hashlib.sha256(("%s|%s" % (sha256_souboru(cesta), PRAVIDLO_VERZE)).encode("ascii")).hexdigest()
