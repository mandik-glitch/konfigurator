#!/usr/bin/env python3
"""Postavi a zpetne naplni registr `karoserie_verze` (auto x verze -> rozpis).

Viz sql/2026-09-13c_karoserie_verze.sql pro plne zduvodneni. Idempotentni.

Pouziti:
    python3 scripts/2026-09-13_karoserie_verze_zapsat.py            # dry-run
    python3 scripts/2026-09-13_karoserie_verze_zapsat.py --apply    # zapis
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

APPLY = "--apply" in sys.argv


def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SHOW TABLES LIKE 'karoserie_verze'")
    existuje = cur.fetchone() is not None
    print(f"[tabulka karoserie_verze existuje] {existuje}")

    # Bezpecnostni kontrola PRED zapisem - nesmi existovat (karoserie,
    # verze) dvojice se dvema RUZNYMI typologie_varianta_id.
    cur.execute("""
        SELECT karoserie_kod, verze, COUNT(DISTINCT typologie_varianta_id) n
        FROM product_assemblies
        WHERE karoserie_kod IS NOT NULL AND verze IS NOT NULL AND typologie_varianta_id IS NOT NULL
        GROUP BY karoserie_kod, verze HAVING n > 1
    """)
    kolize = cur.fetchall()
    if kolize:
        print(f"⛔ ZASTAVENO - {len(kolize)} nekonzistentních dvojic (karoserie,verze), nelze bezpečně naplnit:")
        for k in kolize:
            print("  ", k)
        cur.close()
        conn.close()
        return

    if not existuje:
        if APPLY:
            cur.execute("""
                CREATE TABLE karoserie_verze (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  karoserie_kod VARCHAR(8) NOT NULL,
                  verze CHAR(1) NOT NULL,
                  typologie_varianta_id INT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  UNIQUE KEY uq_karoserie_verze (karoserie_kod, verze),
                  FOREIGN KEY (typologie_varianta_id) REFERENCES typologie_varianty(id)
                )
            """)
            print("  -> vytvořeno")
        else:
            print("  -> (dry-run) vytvořilo by se")

    cur.execute("""
        SELECT DISTINCT karoserie_kod, verze, typologie_varianta_id
        FROM product_assemblies
        WHERE karoserie_kod IS NOT NULL AND verze IS NOT NULL AND typologie_varianta_id IS NOT NULL
    """)
    zdrojove = cur.fetchall()
    print(f"[zdrojových dvojic k naplnění] {len(zdrojove)}")

    zapsano, preskoceno = 0, 0
    for r in zdrojove:
        if APPLY or existuje:
            cur.execute("SELECT id FROM karoserie_verze WHERE karoserie_kod=%s AND verze=%s",
                        (r["karoserie_kod"], r["verze"]))
            if cur.fetchone():
                preskoceno += 1
                continue
        if APPLY:
            cur.execute(
                "INSERT INTO karoserie_verze (karoserie_kod, verze, typologie_varianta_id) VALUES (%s,%s,%s)",
                (r["karoserie_kod"], r["verze"], r["typologie_varianta_id"]),
            )
        zapsano += 1

    print(f"[{'zapsáno' if APPLY else '(dry-run) zapsalo by se'}] {zapsano}, přeskočeno (už existuje) {preskoceno}")

    if APPLY:
        conn.commit()
        print("\nAPLIKOVÁNO.")
    else:
        conn.rollback()
        print("\nDRY-RUN, nic nezapsáno. Spusť s --apply pro zápis.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
