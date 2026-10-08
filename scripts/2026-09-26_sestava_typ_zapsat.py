#!/usr/bin/env python3
"""Postavi novou osu "typ sestavy" (viz sql/2026-09-26_sestava_typ_tabulka.sql).

Robert pres bot3, 2026-09-26 (PLAN_TVORBY_SESTAV.md). Konzultovano pred
navrhem: bot8 (product_assemblies), bot5 (volitelne sluzby/pricing),
bot10 (stolova linie). Schema+UI schvalil bot3 bez podminek jako "cistě
aditivni a nic neriskuje" - NEOBSAHUJE migraci existujicich ~530
product_assemblies radku na sestava_typ_id=AUTO ani presun Vandr textu -
to jsou SAMOSTATNE kroky s povinnym dry-run pred spustenim.

Idempotentni: kontroluje existenci tabulek/sloupce/radku pred zapisem,
lze spustit vicekrat bez chyby.

Pouziti:
    python3 scripts/2026-09-26_sestava_typ_zapsat.py            # dry-run
    python3 scripts/2026-09-26_sestava_typ_zapsat.py --apply    # zapis
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

APPLY = "--apply" in sys.argv

SESTAVA_TYP = [
    ("AUTO", "Vestavby do vozidel", 10),
    ("STUL_SKLAD", "Stolové a skladové sestavy", 20),
]


def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SHOW TABLES LIKE 'sestava_typ'")
    tabulka_existuje = cur.fetchone() is not None
    print(f"[tabulka sestava_typ existuje] {tabulka_existuje}")

    if not tabulka_existuje:
        if APPLY:
            cur.execute("""
                CREATE TABLE sestava_typ (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  kod VARCHAR(32) NOT NULL UNIQUE,
                  nazev VARCHAR(128) NOT NULL,
                  popis_sablona TEXT,
                  aktivni TINYINT(1) NOT NULL DEFAULT 1,
                  sort_order INT NOT NULL DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            print("  -> vytvořeno")
        else:
            print("  -> (dry-run) vytvořilo by se")

    if not tabulka_existuje and not APPLY:
        print("[řádky sestava_typ] přeskočeno, tabulka v dry-run ještě neexistuje")
    else:
        for kod, nazev, sort_order in SESTAVA_TYP:
            existuje = None
            if APPLY or tabulka_existuje:
                cur.execute("SELECT id FROM sestava_typ WHERE kod=%s", (kod,))
                existuje = cur.fetchone()
            if existuje:
                print(f"  [{kod}] už existuje, přeskočeno")
                continue
            print(f"  [{kod}] {'zapisuji' if APPLY else '(dry-run) zapsalo by se'}")
            if APPLY:
                cur.execute(
                    "INSERT INTO sestava_typ (kod, nazev, sort_order) VALUES (%s,%s,%s)",
                    (kod, nazev, sort_order),
                )

    cur.execute("SHOW COLUMNS FROM product_assemblies LIKE 'sestava_typ_id'")
    sloupec_existuje = cur.fetchone() is not None
    print(f"[sloupec product_assemblies.sestava_typ_id existuje] {sloupec_existuje}")
    if not sloupec_existuje:
        if APPLY:
            cur.execute("""
                ALTER TABLE product_assemblies
                  ADD COLUMN sestava_typ_id INT NULL AFTER car_model_id,
                  ADD CONSTRAINT fk_pa_sestava_typ FOREIGN KEY (sestava_typ_id)
                    REFERENCES sestava_typ(id)
            """)
            print("  -> přidán")
        else:
            print("  -> (dry-run) přidal by se")

    cur.execute("SHOW TABLES LIKE 'sestava_typ_sluzba'")
    sluzby_existuje = cur.fetchone() is not None
    print(f"[tabulka sestava_typ_sluzba existuje] {sluzby_existuje}")
    if not sluzby_existuje:
        if APPLY:
            cur.execute("""
                CREATE TABLE sestava_typ_sluzba (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  sestava_typ_id INT NULL,
                  klic VARCHAR(32) NOT NULL,
                  nazev VARCHAR(128) NOT NULL,
                  pricing_mode ENUM('informativni','procento_z_ceny','pevna_castka') NOT NULL DEFAULT 'informativni',
                  hodnota DECIMAL(10,2) NULL,
                  vyzaduje_dalsi_pole TINYINT(1) NOT NULL DEFAULT 0,
                  aktivni TINYINT(1) NOT NULL DEFAULT 1,
                  sort_order INT NOT NULL DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  UNIQUE KEY uq_sts_typ_klic (sestava_typ_id, klic),
                  CONSTRAINT fk_sts_typ FOREIGN KEY (sestava_typ_id) REFERENCES sestava_typ(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            print("  -> vytvořeno")
        else:
            print("  -> (dry-run) vytvořilo by se")

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
