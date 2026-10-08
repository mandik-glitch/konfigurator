#!/usr/bin/env python3
"""OPRAVA: bot7 pri psani centralniho textu (obor 1) a pri pozdejsim
doplneni typologie 'kotveni' pouzil STAROU, uz jednou opravenou formulaci
"bez vrtani do karoserie" - zdroj byl zastaraly zaloha backups/
otisk_kategorie_2026-08-10.md, ktera predchazi opravu z 2026-09-05
(AGENTS_LOG.md, bot20, pravidlo 9/9a: "u dodavek N1 je vrtani do
zpevnenych casti karoserie bezne a ocekavane, ne vyjimka" - Robert
primo, 2026-09-27, kdyz zjistil tu samou chybu v centralnim textu:
"kotveni bez vrtani do karoserie urcite nedelame!!!! kde si na to
prisel?").

Sprava formulace (uz zive schvalena na kategorii 260, viz AGENTS_LOG.md
2026-09-05): drazka v PROFILU = zadne vrtani pri kazde uprave (pravda),
ale kotveni cele konstrukce KE KAROSERII = obvykle vyzaduje vrtani do
jejich zpevnenych casti, v souladu s pozadavky na homologaci.

Opravuje: content_obor.id=1 (popis_html - 2 mista), content_typologie
'kotveni' (nazev + popis_html). Obe schvaleno=0, takze uprava je v
poradku (nikdy neupravujeme uz SCHVALENY radek).

Pouziti:
    python3 scripts/2026-09-27_content_obor_fix_kotveni_karoserie.py            # dry-run
    python3 scripts/2026-09-27_content_obor_fix_kotveni_karoserie.py --apply    # zapis
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

APPLY = "--apply" in sys.argv

TYP_NAZEV_NOVY = "Kotvení vestaveb do auta"

TYP_POPIS_NOVY = (
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


def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, popis_html FROM content_obor WHERE kod=%s", ("1",))
    obor1 = cur.fetchone()
    if not obor1:
        print("Obor 1 nenalezen.")
        return
    popis = obor1["popis_html"] or ""
    fixes = [
        (
            "Po montáži se provádí zápis do technického průkazu vozidla pod číslem homologace HP-0579. Montáž probíhá",
            "Po montáži se provádí zápis vestavby do technického průkazu vozidla, v souladu s požadavky na homologaci. Montáž probíhá",
        ),
        (
            "Po montáži provedeme zápis vestavby do technického průkazu vozidla – homologace číslo HP-0579.",
            "Po montáži provedeme zápis vestavby do technického průkazu vozidla, v souladu s požadavky na homologaci.",
        ),
        (
            "<h3>Kotvení bez vrtání do karoserie</h3>\n<p>Každý hliníkový profil má po celé délce upínací drážku, díky které lze kotvit regály, šuplíky, madla i vlastní doplňky kdekoli na konstrukci – bez nutnosti vrtání do karoserie vozidla. Kotevní prvky a sety využívají přesně tyhle drážky; příklady konkrétního kotvení najdete přímo u vestaveb v katalogu.</p>",
            "<h3>Kotvení konstrukce ke karoserii</h3>\n<p>Každý hliníkový profil má po celé délce upínací drážku, díky které lze kotvit regály, šuplíky, madla i vlastní doplňky kdekoli na konstrukci bez nutnosti vrtat znovu do profilu při každé úpravě. Ukotvení celé konstrukce ke karoserii vozidla ale obvykle vyžaduje vrtání do jejích zpevněných částí – originálních kotevních bodů bývá u dodávek jen málo – v souladu s požadavky na homologaci. Kotevní prvky a sety využívají upínací drážku profilu; příklady konkrétního kotvení najdete přímo u vestaveb v katalogu.</p>",
        ),
        (
            "<p><strong>Je nutná homologace po montáži vestavby?</strong> Ano, po montáži se provádí zápis do technického průkazu vozidla pod číslem homologace HP-0579.</p>",
            "<p><strong>Je nutná homologace po montáži vestavby?</strong> Ano, po montáži se provádí zápis do technického průkazu vozidla v souladu s požadavky na homologaci.</p>",
        ),
        (
            "<p><strong>Musí se kvůli kotvení vrtat do karoserie auta?</strong> Ne, kotvení využívá upínací drážky v hliníkových profilech po celé jejich délce.</p>",
            "<p><strong>Musí se kvůli kotvení vrtat do karoserie auta?</strong> Do samotného hliníkového profilu ne (využívá se jeho upínací drážka po celé délce), ale ukotvení celé konstrukce ke karoserii obvykle vyžaduje vrtání do jejích zpevněných částí – to je běžné a homologačně v pořádku.</p>",
        ),
    ]
    new_popis = popis
    missing = []
    for old, new in fixes:
        if old not in new_popis:
            missing.append(old[:70])
            continue
        new_popis = new_popis.replace(old, new)

    cur.execute("SELECT id, nazev, popis_html FROM content_typologie WHERE obor_id=%s AND klic=%s", (obor1["id"], "kotveni"))
    typ = cur.fetchone()
    if not typ:
        print("typologie 'kotveni' nenalezena.")
        return

    print(f"obor 1 popis_html: {len(fixes) - len(missing)}/{len(fixes)} vzoru nalezeno a opraveno")
    if missing:
        print("NENALEZENO (uz zmeneno drive, nebo jina formulace):")
        for m in missing:
            print("  -", m)
    print(f"typologie 'kotveni' (id={typ['id']}): nazev '{typ['nazev']}' -> '{TYP_NAZEV_NOVY}'")

    if not APPLY:
        print("(dry-run - nic nezapsano, spust s --apply)")
        return

    cur.execute("UPDATE content_obor SET popis_html=%s WHERE id=%s", (new_popis, obor1["id"]))
    cur.execute(
        "UPDATE content_typologie SET nazev=%s, popis_html=%s WHERE id=%s",
        (TYP_NAZEV_NOVY, TYP_POPIS_NOVY, typ["id"]),
    )
    conn.commit()
    print("Zapsano a commitnuto.")


if __name__ == "__main__":
    main()
