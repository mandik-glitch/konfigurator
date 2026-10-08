"""Oprava 4 poruseni TEXT_FILTR.md v content_categories.meta_description,
nalezenych rucnim auditem pri rozsireni rozsahu filtru na hlavni kategorie
(bot15, 2026-09-05, zadani pres bot3).

Nalezy (detail v AGENTS_LOG.md zapisu bot15 tehoz dne):
- id=184, 250, 251: konkretni homologacni cislo "HP-0579" pouzite sirs,
  nez bylo overeno (2026-08-30, AGENTS_LOG.md "HP-0579 pripad") - overeno
  VYHRADNE pro Fiat Ducato/Doblo, tady se ale tvrdi i pro Ford/Toyota
  (250/251) a obecne "Ford, Mercedes, VW, Fiat a dalsi" (184). Pravidlo 3
  (zadna fabrikace certifikaci/technickych specifikaci bez overeni).
- id=221: "montaz bez vrtani do karoserie vozidla" - podle referencnich
  faktu 9a (TEXT_FILTR.md, Robert 2026-09-05) je tohle u dodavek N1
  TYPICKY NEPRAVDIVE (vrtani do zpevnenych casti karoserie je bezne a
  ocekavane). Sesterska kategorie id=260 (STEJNY den) uz ma opravenou
  bezpecnou formulaci bez teto tvrzeni - id=221 zustalo pozadu.

READ-ONLY neni potreba (jde o zapis), pouziva scripts/_env.py::get_conn
(normalni spojeni, ne QA read-only). Zaloha PRED zapisem do
backups/2026-09-05_text_filtr_category_fixes_backup.json.

Pouziti: --dry-run (vypise diff, nic nezapise), bez flagu provede UPDATE.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_PATH = os.path.join(REPO_ROOT, "backups", "2026-09-05_text_filtr_category_fixes_backup.json")

FIXES = {
    184: (
        "Vestavby do dodávek na míru pro Ford, Mercedes, VW, Fiat a další. Hliníkové i ocelové regály, "
        "šuplíky a boxy s homologací HP-0579. Montáž na klíč v Praze i Slavičíně.",
        "Vestavby do dodávek na míru pro Ford, Mercedes, VW, Fiat a další. Hliníkové i ocelové regály, "
        "šuplíky a boxy splňující požadavky na homologaci pro instalaci do užitkových vozidel. Montáž na "
        "klíč v Praze i Slavičíně.",
    ),
    250: (
        "Vestavba (regálový systém) do Ford Transit a Transit Custom na míru – hliníkové upínací drážky, "
        "výsuvy s aretací na euroboxy i systainery, homologace HP-0579.",
        "Vestavba (regálový systém) do Ford Transit a Transit Custom na míru – hliníkové upínací drážky, "
        "výsuvy s aretací na euroboxy i systainery. Splňuje požadavky na homologaci pro instalaci do "
        "užitkových vozidel.",
    ),
    251: (
        "Vestavba (regálová zástavba) do Toyota ProAce na míru – hliníkové upínací drážky, výsuvy s "
        "aretací pro euroboxy i systainery, homologace HP-0579.",
        "Vestavba (regálová zástavba) do Toyota ProAce na míru – hliníkové upínací drážky, výsuvy s "
        "aretací pro euroboxy i systainery. Splňuje požadavky na homologaci pro instalaci do užitkových "
        "vozidel.",
    ),
    221: (
        "Kotevní prvky a sety pro ukotvení vestavby do dodávky — využívají upínací drážky hliníkových "
        "profilů LOGiMAN, montáž bez vrtání do karoserie vozidla.",
        "Kotevní prvky a sety pro ukotvení vestavby do dodávky — upínací drážka v hliníkových profilech "
        "LOGiMAN umožňuje ukotvit regál, šuplík i vlastní doplněk podle potřeby.",
    ),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, slug, meta_description FROM content_categories WHERE id IN (%s)"
        % ",".join(str(i) for i in FIXES)
    )
    rows = {r["id"]: r for r in cur.fetchall()}

    backup = []
    for cat_id, (expected_old, new_val) in FIXES.items():
        row = rows.get(cat_id)
        if row is None:
            print(f"CHYBA: id={cat_id} v content_categories neexistuje, přeskakuji")
            continue
        current = row["meta_description"]
        if current != expected_old:
            print(f"VAROVÁNÍ: id={cat_id} ({row['slug']}) - text v DB se neshoduje s očekávaným "
                  f"(mezitím upraveno jiným botem?). Přeskakuji, ověřit ručně.")
            print(f"  DB:       {current!r}")
            print(f"  Očekáváno: {expected_old!r}")
            continue
        backup.append({"id": cat_id, "slug": row["slug"], "meta_description": current})
        print(f"id={cat_id} ({row['slug']}):")
        print(f"  PŘED: {current}")
        print(f"  PO:   {new_val}")
        if not args.dry_run:
            cur.execute("UPDATE content_categories SET meta_description=%s WHERE id=%s", (new_val, cat_id))

    if args.dry_run:
        print("\n--dry-run: nic nezapsáno.")
        return

    if backup:
        os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
        with open(BACKUP_PATH, "w", encoding="utf-8") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)
        print(f"\nZáloha původních hodnot: {BACKUP_PATH}")

    conn.commit()
    print(f"Zapsáno {len(backup)} oprav.")


if __name__ == "__main__":
    main()
