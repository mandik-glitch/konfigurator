#!/usr/bin/env python3
"""Doplnuje jednu chybejici typologii do obor 1 (Vestavby do dodavek):
kategorie 260 "Kotveni vestaveb do auta" existuje ve zivem strome, ale
nebyla namapovana v puvodnim seedu (scripts/2026-09-27_content_obor_seed.py) -
najdeno pri auditu proti backups/otisk_kategorie_2026-08-10.md (Robert,
2026-09-27: "Uz jsou tam kompletni maximum co se dalo vydolovat ze
zalozních souboru?").

Pouziti:
    python3 scripts/2026-09-27_content_obor_add_kotveni.py            # dry-run
    python3 scripts/2026-09-27_content_obor_add_kotveni.py --apply    # zapis
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

APPLY = "--apply" in sys.argv

POPIS_HTML = (
    "<p>Každý hliníkový profil systému LOGiMAN má po celé délce upínací "
    "drážku, díky které lze kotvit regály, šuplíky, madla i vlastní "
    "doplňky kdekoli na konstrukci – bez nutnosti vrtat znovu do profilu "
    "při každé úpravě. Ukotvení celé konstrukce ke karoserii vozidla ale "
    "obvykle vyžaduje vrtání do jejích zpevněných částí – originálních "
    "kotevních bodů bývá u dodávek jen málo – v souladu s požadavky na "
    "homologaci. Konkrétní kotevní prvky a sety najdete přímo u vestaveb "
    "v katalogu.</p>"
    "<p><strong>Musí se kvůli kotvení vrtat do karoserie auta?</strong> "
    "Ano, ukotvení konstrukce ke karoserii obvykle vyžaduje vrtání do "
    "jejích zpevněných částí – originálních kotevních bodů bývá u "
    "dodávek jen málo. Je to běžné a homologačně v pořádku. Do samotného "
    "hliníkového profilu se naopak znovu nevrtá – využívá se jeho "
    "upínací drážka po celé délce.</p>"
)
# OPRAVENO 2026-09-27 (Robert primo, po nasazeni): puvodni text tvrdil
# "bez nutnosti vrtani do karoserie vozidla" - stejna chyba, kterou uz
# jednou opravil bot20 na kategorii 260 primo v DB (2026-09-05, pravidlo
# 9/9a - vrtani do zpevnenych casti karoserie je u dodavek N1 bezne a
# ocekavane). Zdroj chyby: pouziti stareho backups/otisk_kategorie_
# 2026-08-10.md (predchazi tu opravu) bez krizove kontroly proti zive
# DB. Skutecna oprava zapsana primo do DB skriptem
# scripts/2026-09-27_content_obor_fix_kotveni_karoserie.py - tenhle
# soubor uz jen odpovida vysledku, znovu se nespousti (idempotentni
# strazny SELECT vyse to ostatne i technicky zabrani).


def main():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM content_obor WHERE kod=%s", ("1",))
    row = cur.fetchone()
    if not row:
        print("Obor 1 nenalezen - nejdriv spust hlavni seed skript.")
        return
    obor1_id = row["id"]
    cur.execute("SELECT id FROM content_typologie WHERE obor_id=%s AND klic=%s", (obor1_id, "kotveni"))
    if cur.fetchone():
        print("typologie 'kotveni' uz existuje, nic nedelam")
        return
    if not APPLY:
        print("(dry-run) typologie 'kotveni' (kategorie_ids=260) by se vytvorila v oboru 1")
        return
    cur.execute(
        "INSERT INTO content_typologie (obor_id, klic, nazev, popis_html, kategorie_ids, sort_order) "
        "SELECT %s, %s, %s, %s, %s, COALESCE(MAX(sort_order),0)+10 FROM content_typologie WHERE obor_id=%s",
        (obor1_id, "kotveni", "Kotvení bez vrtání do karoserie", POPIS_HTML, "260", obor1_id),
    )
    conn.commit()
    print("typologie 'kotveni' vytvorena, id=", cur.lastrowid)


if __name__ == "__main__":
    main()
