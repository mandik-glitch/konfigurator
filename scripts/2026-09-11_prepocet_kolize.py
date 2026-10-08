#!/usr/bin/env python3
"""CLI k prepoctu priznaku koliznich uhelniku (api/kolize_priznak.py).

Pouziti:
    api/venv/bin/python3 scripts/2026-09-11_prepocet_kolize.py            # cely katalog
    api/venv/bin/python3 scripts/2026-09-11_prepocet_kolize.py 79 116     # jen tyhle
    api/venv/bin/python3 scripts/2026-09-11_prepocet_kolize.py --dry-run  # nic nezapise

Logika je v api/kolize_priznak.py, tady je jen obal - stejny vypocet nesmi
existovat na dvou mistech. Tenhle skript pousti i casovac
`konfigurator-kolize-uhelniky.timer` (pojistka proti tomu, aby priznak
zastaral po zapisu, ktery sel mimo API - boti meni `data` primo v SQL).
"""
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402
import os  # noqa: E402

os.environ.update(_env.load_env())

import app  # noqa: E402,F401 - driv nez kolize_priznak (kruhovy import)
import kolize_priznak  # noqa: E402


def main():
    argv = [a for a in sys.argv[1:]]
    dry = "--dry-run" in argv
    ids = [int(a) for a in argv if a.isdigit()] or None

    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            v = kolize_priznak.prepocti(cur, ids)
            if dry:
                conn.rollback()
                print(f"--dry-run: spocteno {v['zapsano']} sestav "
                      f"(s kolizi {v['s_kolizi']}, cistych {v['cistych']}), NIC NEZAPSANO.")
                return 0
        conn.commit()
    finally:
        conn.close()
    print(f"zapsano {v['zapsano']} sestav: s kolizi {v['s_kolizi']}, cistych {v['cistych']}")

    # Kontrola cerstvym spojenim - zapis se overuje, ne predpoklada.
    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) n, SUM(kolize_pocet IS NULL) nezmereno, "
                        "SUM(kolize_pocet > 0) s_kolizi FROM product_assemblies")
            r = cur.fetchone()
    finally:
        conn.close()
    print(f"kontrola: sestav {r['n']}, nezmerenych {r['nezmereno']}, s kolizi {r['s_kolizi']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
