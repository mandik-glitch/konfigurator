#!/usr/bin/env python3
"""FAZE 2 generatoru OCHRANNY KRYT A OPLOCENI (bot8, 2026-10-08): kotvene upravy sdilene dokumentace v <docroot>:
  * MAPA_3D_A_GENERATORU.md          - radek tabulky pojmu "Generator 06 - ochranny kryt a oploceni" (pred radek Prijemce stolu),
  * docs/KONTRAKT_KONFIGURATOR_UI.md - jedna veta o dalsich receptech (dopravnik, oploceni) na zacatku.
Kazda kotva musi byt v souboru PRAVE JEDNOU; idempotentni (opakovany beh nic nezmeni; znamka = text "KONTRAKT_OPLOCENI.md"). Novy dokument docs/KONTRAKT_OPLOCENI.md se kopiruje v apply_f2.sh.
  patch_docs_f2.py <docroot>"""
import os
import sys

MAPA_RADEK = ("| **Generátor 06 – ochranný kryt a oplocení strojů z profilů 40×40** (Robert 2026-10-08: „udělej generátor ochranného oplocení a krytování strojů z profilů 40×40“, „nahrát všechno hned“; bot8) "
              "| recept `oploceni_kryt`: obdélníkový půdorys, každá ze 4 stran = stěna / dveře / bez stěny (z jedné strany bez střechy je prosté oplocení), střecha bez / rám / výplň, výplň v drážce (polykarbonát čirý a kouřový, "
              "plexisklo, svařovaná síť, kompozit; i po stranách), křídlové dveře (3 závěsy, ven, západka / zámek), stavitelné patky; **server výběr vždy upraví na proveditelný a oznámí** (`notices`); veřejné meze 4000 × 4000 × 3000 mm, "
              "cena z `price_entries` (výplně jako virtuální desky, dokud nemají karty), montáž se nenabízí; stránka pro zaměstnance „Generátor 06“ | `api/oploceni_konfigurator.py` (jádro), `api/oploceni_glb.py`, `api/oploceni_cena.py`, "
              "`api/oploceni_shop.py` (veřejné API přes `api/konfigurator_registr.py` a `api/stul_shop.py`), `webapp/oploceni-konfigurator.html` + `webapp/js/oploceni-host.js`, `scripts/2026-10-08_oploceni/`; kontrakt `docs/KONTRAKT_OPLOCENI.md` |\n")
MAPA_KOTVA = "| **Příjemce stolu** (ve Scéně)"
KONTRAKT_KOTVA = "UI se přizpůsobí. Všechny texty česky, bez interních názvů, ID voleb neprůhledná.\n"
KONTRAKT_VETA = ("UI se přizpůsobí. Všechny texty česky, bez interních názvů, ID voleb neprůhledná.\n\n"
                 "Stejný tvar schématu a odpovědí mají i další recepty (rozcestník `api/konfigurator_registr.py`): válečkový dopravník (`docs/NAVRH_GENERATOR_DOPRAVNIKU.md`) a ochranný kryt a oplocení z profilů 40×40 "
                 "(`docs/KONTRAKT_OPLOCENI.md`, recept `oploceni_kryt`, sloty `w d h front right back left roof fill fill_* door_* lock feet`).\n")


def nahrad_jednou(s, a, b, label):
    n = s.count(a)
    if n != 1:
        raise AssertionError(f"kotva '{label}': {n} vyskytu (ocekavan 1)")
    return s.replace(a, b)


def hotovo(root):
    out = []
    p = os.path.join(root, "MAPA_3D_A_GENERATORU.md")
    s = open(p, encoding="utf-8").read()
    if "KONTRAKT_OPLOCENI.md" not in s:
        s = nahrad_jednou(s, MAPA_KOTVA, MAPA_RADEK + MAPA_KOTVA, "MAPA Prijemce stolu")
        open(p, "w", encoding="utf-8").write(s)
        out.append("MAPA_3D_A_GENERATORU.md")
    p = os.path.join(root, "docs", "KONTRAKT_KONFIGURATOR_UI.md")
    s = open(p, encoding="utf-8").read()
    if "KONTRAKT_OPLOCENI.md" not in s:
        s = nahrad_jednou(s, KONTRAKT_KOTVA, KONTRAKT_VETA, "KONTRAKT UI uvod")
        open(p, "w", encoding="utf-8").write(s)
        out.append("docs/KONTRAKT_KONFIGURATOR_UI.md")
    return out


if __name__ == "__main__":
    zmeneno = hotovo(os.path.abspath(sys.argv[1]))
    print("dokumentace upravena:", ", ".join(zmeneno) if zmeneno else "beze zmeny (uz je zapsano)")
