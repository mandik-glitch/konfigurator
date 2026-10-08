#!/usr/bin/env python3
"""Postavi plnou DB strukturu centralniho panelu popisu kategorii - obor
(content_obor) -> typologie (content_typologie), viz PROJEKT dokument
(Claude Docs, https://claude.ai/artifact/EEKnzp9rYsz5SvviMCqUrf) a Robert
pres bot3, 2026-09-27: "Postav nekde v adminu panel jako centralni popis
nasich webovych kategorii, rozdeleno podle oboru a typologie."

Kazda urovni (obor i typologie) ma vlastni schvaleno/schvaleno_at pole -
klicovy mechanismus pro Robertovo pravidlo: "Tento text admin musi projit
precist opravit a schvalit, po schvaleni na tento text bot7 nesmi sahnout
nesmi jakkoli zmenit." Jakmile je radek schvaleno=1, bot7 uz na nej NIKDY
nesmi zavolat UPDATE - to je bota7 vlastni disciplina (viz memory
feedback_approved_central_text_hands_off.md), ne DB constraint - Robert
sam smi cokoli upravit dal pres admin panel.

content_typologie.kategorie_ids: volitelny comma-separated seznam
content_categories.id, na ktere se tahle typologie mapuje v ZIVEM stromu -
ulozeno uz teď (z rucniho zkoumani stromu), aby pozdejsi krok "vytahnout
z centralniho textu vytazky do jednotlivych kategorii" nemusel mapovani
delat znovu od nuly.

Pouziti:
    python3 scripts/2026-09-27_content_obor_typologie_tables.py            # dry-run
    python3 scripts/2026-09-27_content_obor_typologie_tables.py --apply    # zapis
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

APPLY = "--apply" in sys.argv


def main():
    conn = get_conn()
    cur = conn.cursor()

    for tbl in ("content_obor", "content_typologie"):
        cur.execute(f"SHOW TABLES LIKE '{tbl}'")
        print(f"[tabulka {tbl} existuje] {cur.fetchone() is not None}")

    if not APPLY:
        print("(dry-run - nic nezapsáno, spusť s --apply pro skutečný zápis)")
        return

    cur.execute("SHOW TABLES LIKE 'content_obor'")
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE content_obor (
              id INT AUTO_INCREMENT PRIMARY KEY,
              kod VARCHAR(16) NOT NULL UNIQUE,
              nazev VARCHAR(255) NOT NULL,
              popis_html MEDIUMTEXT,
              sort_order INT NOT NULL DEFAULT 0,
              aktivni TINYINT(1) NOT NULL DEFAULT 1,
              schvaleno TINYINT(1) NOT NULL DEFAULT 0,
              schvaleno_at DATETIME NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("content_obor -> vytvořeno")

    cur.execute("SHOW TABLES LIKE 'content_typologie'")
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE content_typologie (
              id INT AUTO_INCREMENT PRIMARY KEY,
              obor_id INT NOT NULL,
              klic VARCHAR(64) NOT NULL,
              nazev VARCHAR(255) NOT NULL,
              popis_html MEDIUMTEXT,
              kategorie_ids VARCHAR(255),
              sort_order INT NOT NULL DEFAULT 0,
              aktivni TINYINT(1) NOT NULL DEFAULT 1,
              schvaleno TINYINT(1) NOT NULL DEFAULT 0,
              schvaleno_at DATETIME NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              CONSTRAINT fk_content_typologie_obor FOREIGN KEY (obor_id) REFERENCES content_obor(id) ON DELETE CASCADE,
              UNIQUE KEY uniq_obor_klic (obor_id, klic)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("content_typologie -> vytvořeno")

    conn.commit()


if __name__ == "__main__":
    main()
