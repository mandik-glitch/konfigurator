"""Oprava 3 poruseni TEXT_FILTR.md v content_pages (viditelny text stranky:
intro_html/body_html/bottom_body_html), stejny typ chyby jako uz opraveny
content_categories.meta_description (bot15, 2026-09-05, viz scripts/2026-09-05_
text_filtr_category_fixes.py a AGENTS_LOG.md zapis bot15 tehoz dne).

Nalezy (puvodne zapsany jako "mimo rozsah", ted Robert rozsah rozsiril i sem):
- id=13 (category_id=221, "kotevni prvky a sety"): tvrdilo "neni nutne vrtat
  do karoserie vozidla" - podle referencnich faktu 9a (TEXT_FILTR.md) je tohle
  u dodavek N1 TYPICKY NEPRAVDIVE. Sesterska kategorie id=54 (category_id=260,
  "Kotveni vestaveb do auta") ma uz spravnou formulaci - pouzita jako vzor
  (parafraze, ne 1:1 kopie - zabranuje near-duplicate obsahu mezi dvema
  zivymi strankami).
- id=15 (category_id=184, "Vestavby do dodavek, aut"): tvrdilo konkretni
  homologacni cislo "HP-0579" pro celou sirokou flotilu znacek (Ford,
  Mercedes, VW, Fiat, Citroen, Renault, Opel, MAN, Iveco, Toyota) - cislo
  bylo 2026-08-30 overeno VYHRADNE pro Fiat Ducato/Doblo. Stejna oprava jako
  uz hotova content_categories.id=184 (nahrazeno obecnym pravdivym tvrzenim
  bez konkretniho cisla).
- id=31 (category_id=251, "Vestavby pro Toyota ProAce"): FAQ tvrdilo cislo
  HP-0579 konkretne pro Toyota ProAce - stejny problem, stejna oprava jako
  uz hotova content_categories.id=251.

id=11 (category_id=188) a id=55 (category_id=233) VEDOME BEZE ZMENY - podle
puvodniho auditu (AGENTS_LOG.md, bot15 tehoz dne) jsou tohle prave ty
kategorie/stranky, kde je HP-0579 pouzito uzce scopovane (jen Ducato/Jumper/
Boxer stejna platforma), ne overeno jako chybne - mimo rozsah teto opravy.

Zaloha PRED zapisem do
backups/2026-09-05_text_filtr_pages_fixes_backup.json - zapsana na disk jako
KOMPLETNI dokoncenej krok PRED jakymkoli UPDATE (zprisnena disciplina,
AGENTS_LOG.md bot15 2026-09-05: "nejdriv kompletni zapis backup souboru na
disk jako samostatny dokonceny krok, teprve pak UPDATE/commit").

Pouziti: --dry-run (vypise diff, nic nezapise), bez flagu provede UPDATE.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_PATH = os.path.join(REPO_ROOT, "backups", "2026-09-05_text_filtr_pages_fixes_backup.json")

# id -> {column: (needle, replacement)} - needle musí být přesná podřetězec
# aktuální hodnoty sloupce (substring patch, ne celopolní náhrada - id=15
# body_html má za opravovanou větou ještě galerii obrázků, kterou nechceme
# přepisovat/riskovat překlep).
FIXES = {
    13: {
        "body_html": (
            "<p>Kotevní prvky a sety slouží k pevnému ukotvení celé vestavby ve vozidle — využívají "
            "upínací drážky po celé délce hliníkových profilů stavebnice, takže není nutné vrtat do "
            "karoserie vozidla. Konkrétní příklady kotvení najdete na stránce Kotvení vestaveb do auta, "
            "kde je princip vysvětlený i vizuálně.</p>",
            "<p>Kotevní prvky a sety slouží k pevnému ukotvení celé vestavby ve vozidle — upínací drážka "
            "po celé délce hliníkových profilů stavebnice umožňuje kotvit regály, šuplíky i doplňky "
            "kdekoli na konstrukci bez dalšího vrtání do profilu. Ukotvení samotné konstrukce ke "
            "karoserii vozidla se řeší vrtáním do jejích zpevněných částí, v souladu s požadavky na "
            "homologaci. Konkrétní příklady kotvení najdete na stránce Kotvení vestaveb do auta, kde je "
            "princip vysvětlený i vizuálně.</p>",
        ),
        "bottom_body_html": (
            '<div class="seo-faq"><h3>Časté dotazy</h3>\n'
            "<p><strong>Je nutné kvůli kotvení vrtat do karoserie?</strong><br>Ne, kotevní prvky "
            "využívají upínací drážky v hliníkových profilech po celé jejich délce.</p>\n"
            "</div>\n"
            '<p class="seo-related"><strong>Související stránky:</strong> '
            '<a href="/kategorie/kotveni-vestaveb-do-auta">Kotvení vestaveb do auta</a>, '
            '<a href="/kategorie/system-30-supliky-do-auta">Systém 30</a></p>',
            '<div class="seo-faq"><h3>Časté dotazy</h3>\n'
            "<p><strong>Je nutné kvůli kotvení vrtat do karoserie?</strong><br>Ano, ukotvení konstrukce "
            "ke karoserii auta vyžaduje vrtání do jejích zpevněných částí (bočnice, podlaha) — je to "
            "běžný postup, který koresponduje s požadavky na homologaci. Upínací drážka v profilu ale "
            "umožňuje samotné kotevní prvky, regály i šuplíky umístit a přemístit kdekoli na konstrukci "
            "bez dalšího vrtání.</p>\n"
            "</div>\n"
            '<p class="seo-related"><strong>Související stránky:</strong> '
            '<a href="/kategorie/kotveni-vestaveb-do-auta">Kotvení vestaveb do auta</a>, '
            '<a href="/kategorie/system-30-supliky-do-auta">Systém 30</a></p>',
        ),
    },
    15: {
        "body_html": (
            "Po montáži se provádí zápis do technického průkazu vozidla pod číslem homologace HP-0579. "
            "Montáž probíhá v Praze",
            "Po montáži se provádí zápis do technického průkazu vozidla, vestavba splňuje požadavky na "
            "homologaci pro instalaci do užitkových vozidel. Montáž probíhá v Praze",
        ),
        "bottom_body_html": (
            '<div class="seo-faq"><h3>Časté dotazy</h3>\n'
            "<p><strong>Je nutná homologace po montáži vestavby?</strong><br>Ano, po montáži se provádí "
            "zápis do technického průkazu vozidla pod číslem homologace HP-0579.</p>\n"
            "<p><strong>Pro jaké modely dodávek vestavby vyrábíte?</strong><br>Mercedes Sprinter, "
            "Mercedes Vito, Ford Transit, Ford Transit Custom, Fiat Ducato, Fiat Doblo, Citroën Jumper, "
            "Citroën Jumpy, Renault Master, Renault Trafic, Opel Movano, Opel Vivaro, VW Crafter, VW "
            "Transporter, VW Caddy, MAN, Iveco Daily a Toyota ProAce.</p>\n"
            "<p><strong>Jaký je rozdíl mezi vestavbou a stavebnicí do auta?</strong><br>Vestavba je "
            "řešení na míru konkrétnímu modelu vozidla nebo profesi. Stavebnice do aut je univerzální "
            "komponentní systém organizovaný podle výšky vozidla, který si skládáte sami.</p>\n"
            "</div>\n"
            '<p class="seo-related"><strong>Související stránky:</strong> '
            '<a href="/kategorie/stavebnice-do-aut">Stavebnice do aut — přehled</a>, '
            '<a href="/kategorie/vestavba-dodavky-ford-custom">Ford Transit Custom</a>, '
            '<a href="/kategorie/vestavby-pro-ducato-jumper-boxer">Fiat Ducato</a>, '
            '<a href="/kategorie/vestavby-pro-toyota-proace">Toyota ProAce</a>, '
            '<a href="/kategorie/vestavby-dodavek-pro-elektrikare">pro elektrikáře</a>, '
            '<a href="/kategorie/vestavby-dodavek-pro-instalatera">pro instalatéry</a></p>',
            '<div class="seo-faq"><h3>Časté dotazy</h3>\n'
            "<p><strong>Je nutná homologace po montáži vestavby?</strong><br>Ano, po montáži se provádí "
            "zápis do technického průkazu vozidla, vestavba splňuje požadavky na homologaci pro instalaci "
            "do užitkových vozidel.</p>\n"
            "<p><strong>Pro jaké modely dodávek vestavby vyrábíte?</strong><br>Mercedes Sprinter, "
            "Mercedes Vito, Ford Transit, Ford Transit Custom, Fiat Ducato, Fiat Doblo, Citroën Jumper, "
            "Citroën Jumpy, Renault Master, Renault Trafic, Opel Movano, Opel Vivaro, VW Crafter, VW "
            "Transporter, VW Caddy, MAN, Iveco Daily a Toyota ProAce.</p>\n"
            "<p><strong>Jaký je rozdíl mezi vestavbou a stavebnicí do auta?</strong><br>Vestavba je "
            "řešení na míru konkrétnímu modelu vozidla nebo profesi. Stavebnice do aut je univerzální "
            "komponentní systém organizovaný podle výšky vozidla, který si skládáte sami.</p>\n"
            "</div>\n"
            '<p class="seo-related"><strong>Související stránky:</strong> '
            '<a href="/kategorie/stavebnice-do-aut">Stavebnice do aut — přehled</a>, '
            '<a href="/kategorie/vestavba-dodavky-ford-custom">Ford Transit Custom</a>, '
            '<a href="/kategorie/vestavby-pro-ducato-jumper-boxer">Fiat Ducato</a>, '
            '<a href="/kategorie/vestavby-pro-toyota-proace">Toyota ProAce</a>, '
            '<a href="/kategorie/vestavby-dodavek-pro-elektrikare">pro elektrikáře</a>, '
            '<a href="/kategorie/vestavby-dodavek-pro-instalatera">pro instalatéry</a></p>',
        ),
    },
    31: {
        "bottom_body_html": (
            '<div class="seo-faq"><h3>Časté dotazy</h3>\n'
            "<p><strong>Je i pro Toyota ProAce nutná homologace?</strong><br>Ano, montáž se zapisuje do "
            "technického průkazu pod číslem HP-0579.</p>\n"
            "</div>\n"
            '<p class="seo-related"><strong>Související stránky:</strong> '
            '<a href="/kategorie/vestavby-do-dodavek-aut">Vestavby do dodávek — přehled</a>, '
            '<a href="/kategorie/regaly-do-auta">Regály do auta</a></p>',
            '<div class="seo-faq"><h3>Časté dotazy</h3>\n'
            "<p><strong>Je i pro Toyota ProAce nutná homologace?</strong><br>Ano, montáž se zapisuje do "
            "technického průkazu vozidla, vestavba splňuje požadavky na homologaci pro instalaci do "
            "užitkových vozidel.</p>\n"
            "</div>\n"
            '<p class="seo-related"><strong>Související stránky:</strong> '
            '<a href="/kategorie/vestavby-do-dodavek-aut">Vestavby do dodávek — přehled</a>, '
            '<a href="/kategorie/regaly-do-auta">Regály do auta</a></p>',
        ),
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    ids = list(FIXES)
    cur.execute(
        "SELECT id, category_id, intro_html, body_html, bottom_body_html FROM content_pages WHERE id IN (%s)"
        % ",".join(str(i) for i in ids)
    )
    rows = {r["id"]: r for r in cur.fetchall()}

    backup = []
    planned = []  # (page_id, column, new_val)
    ok = True
    for page_id, cols in FIXES.items():
        row = rows.get(page_id)
        if row is None:
            print(f"CHYBA: id={page_id} v content_pages neexistuje, přeskakuji")
            ok = False
            continue
        backup_row = {"id": page_id, "category_id": row["category_id"]}
        for col, (needle, replacement) in cols.items():
            current = row[col]
            count = current.count(needle) if current else 0
            if count != 1:
                print(f"VAROVÁNÍ: id={page_id} col={col} - očekávaný text (needle) se v DB nenašel "
                      f"přesně 1x (nalezeno {count}x) - mezitím upraveno jiným botem? Přeskakuji, "
                      f"ověřit ručně.")
                print(f"  needle: {needle!r}")
                ok = False
                continue
            new_full = current.replace(needle, replacement, 1)
            backup_row[col] = current
            planned.append((page_id, col, new_full))
            print(f"id={page_id} ({col}):")
            print(f"  PŘED (needle): {needle}")
            print(f"  PO   (needle): {replacement}")
        if len(backup_row) > 2:
            backup.append(backup_row)

    if args.dry_run:
        print("\n--dry-run: nic nezapsáno.")
        return

    if not ok:
        print("\nAlespoň jedna kontrola selhala - nic nezapisuji (ověřit ručně a spustit znovu).")
        sys.exit(1)

    if not backup:
        print("Nic k zápisu.")
        return

    os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
    with open(BACKUP_PATH, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)
    print(f"\nZáloha původních hodnot zapsána: {BACKUP_PATH}")

    for page_id, col, new_val in planned:
        cur.execute(f"UPDATE content_pages SET {col}=%s WHERE id=%s", (new_val, page_id))

    conn.commit()
    print(f"Zapsáno {len(planned)} oprav polí ({len(backup)} stránek).")


if __name__ == "__main__":
    main()
