"""
Doplneni cross_section_label/groove_family u profilovych produktu
(Robert: navrh vylepseni frontendu -> filtrace v category.html podle
prurezu a drazkove rodiny profilu).

Zdroj hodnot: SKU ma pevnou strukturu "1.1.GG.XXXYYY.NN..." kde GG je
kod drazkove rodiny (06=6mm, 08=8mm, 10=10mm - presne odpovida tabulce
ve VLASTNOSTI_PROFILU.md) a XXXYYY je prurez v mm bez vedoucich nul
zleva (020020 -> 20x20, 030060 -> 30x60). Overeno na vzorku SKU vsech
is_profile_material=1 produktu.

Zamerne NE cfg_dily_id (odkaz na 3D model pro scenu) - jen 22 ze 101
profilovych produktu ho ma vyplneny, jako jediny zdroj by pokryl min
nez ctvrtinu (viz sql/2026-08-09_is_profile_material.sql, kde presne
tenhle duvod uz jednou vedl k zavedeni nezavisleho priznaku).

Idempotentni: aktualizuje jen radky s is_profile_material=1 A
cross_section_label IS NULL, takze opakovane spusteni uz nic nezmeni.
Pred zapisem uklada zalohu puvodniho stavu do backups/. Produkty, jejichz
SKU vzorek neodpovida (zadny match), se vypisou zvlast a NEUPRAVUJI -
potreba rucni kontroly/doplneni jindy.
"""
import json
import re
import sys

import pymysql

from _env import load_env as _load_env

_cfg = _load_env()
DB = dict(
    host=_cfg["DB_HOST"], port=int(_cfg.get("DB_PORT", 3306)), user=_cfg["DB_USER"],
    password=_cfg["DB_PASSWORD"], database=_cfg["DB_NAME"], charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

SKU_RE = re.compile(r"^1\.1\.(\d{2})\.(\d{3})(\d{3})\.")
GROOVE_BY_CODE = {"06": "6", "08": "8", "10": "10"}


def parse_sku(sku):
    m = SKU_RE.match(sku or "")
    if not m:
        return None
    groove_code, dim1, dim2 = m.group(1), m.group(2), m.group(3)
    groove = GROOVE_BY_CODE.get(groove_code)
    if not groove:
        return None
    return f"{int(dim1)}x{int(dim2)}", groove


def main():
    dry_run = "--apply" not in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, sku, name FROM shop_products "
        "WHERE is_profile_material=1 AND cross_section_label IS NULL"
    )
    rows = cur.fetchall()

    to_update = []
    unmatched = []
    for r in rows:
        parsed = parse_sku(r["sku"])
        if parsed:
            to_update.append((r["id"], r["sku"], r["name"], parsed[0], parsed[1]))
        else:
            unmatched.append(r)

    print(f"Kandidatu (is_profile_material=1, dosud bez cross_section_label): {len(rows)}")
    print(f"  -> SKU odpovida vzoru: {len(to_update)}")
    print(f"  -> SKU NEODPOVIDA (preskoceno, nutna rucni kontrola): {len(unmatched)}")
    for r in unmatched:
        print(f"     #{r['id']} sku={r['sku']!r} name={r['name']!r}")

    if not to_update:
        print("Nic k zapisu.")
        return

    backup = [{"id": pid, "sku": sku, "name": name} for pid, sku, name, _, _ in to_update]
    backup_path = "backups/product_cross_section_groove_backfill_20260810.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)
    print(f"Zaloha {len(backup)} radku (puvodni stav pred zapisem, oba sloupce byly NULL) -> {backup_path}")

    if dry_run:
        for pid, sku, name, cross_section, groove in to_update[:15]:
            print(f"  #{pid} {sku} {name!r} -> cross_section={cross_section} groove={groove}")
        if len(to_update) > 15:
            print(f"  ... a dalsich {len(to_update) - 15}")
        print(f"\nDRY RUN - {len(to_update)} pripraveno, 0 zapsano. Spust s --apply pro skutecny zapis.")
        return

    for pid, sku, name, cross_section, groove in to_update:
        cur.execute(
            "UPDATE shop_products SET cross_section_label=%s, groove_family=%s WHERE id=%s",
            (cross_section, groove, pid),
        )
    conn.commit()
    print(f"Zapsano {len(to_update)} produktu.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
