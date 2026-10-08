#!/usr/bin/env python3
"""Postavi tabulku homepage_carousel_slides (Robert pres bot3, 2026-09-27:
"na nas homepage chceme stejny carousel jako je na homepage logimanu").

Samostatna, jednodussi tabulka nez homepage_blocks/sidebar_blocks - slide
karuselu NEMA vlastni SEO stranku (zadny slug/meta_description/body_html),
je to jen obrazek + volitelny odkaz + volitelny popisek + poradi + aktivni,
presne jak to ma i puvodni Shoptet carousel (5x cisty <div><img></div>).

Pouziti:
    python3 scripts/2026-09-27_homepage_carousel_table.py            # dry-run
    python3 scripts/2026-09-27_homepage_carousel_table.py --apply    # zapis
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

APPLY = "--apply" in sys.argv


def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SHOW TABLES LIKE 'homepage_carousel_slides'")
    existuje = cur.fetchone() is not None
    print(f"[tabulka homepage_carousel_slides existuje] {existuje}")

    if existuje:
        print("  -> nic k udelani")
        return

    if not APPLY:
        print("  -> (dry-run) vytvorilo by se")
        return

    cur.execute("""
        CREATE TABLE homepage_carousel_slides (
          id INT AUTO_INCREMENT PRIMARY KEY,
          image_filename VARCHAR(255) NOT NULL,
          caption_text VARCHAR(255),
          link_url VARCHAR(500),
          sort_order INT NOT NULL DEFAULT 0,
          is_visible TINYINT(1) NOT NULL DEFAULT 1,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    conn.commit()
    print("  -> vytvořeno")


if __name__ == "__main__":
    main()
