#!/usr/bin/env python3
"""Postavi ciselnik `regal_umisteni` (osa UMISTENI, viz sql/2026-09-13_regal_umisteni.sql).

Robert primo v chatu, 2026-09-13. Kontext: `regal_typologie` (EB/UN/OS/EV)
popisuje jen SYSTEM/OBSAH regalu. Robert dal navic seznam UMISTENI (regal
bocni strana, regal na prepazce, dvojita podlaha, vysuvne bloky ze
zadnich/bocnich dveri, vysuvna podlaha) - genuinne nova, nezavisla osa
("hrusky s jablkama" - druhy seznam, ktery Robert dal pak, uz jen upresnil
obsah puvodnich placeholderu UN/OS/EV, nejsou to nove polozky).

Idempotentni: kontroluje existenci tabulky/sloupce/radku pred zapisem,
lze spustit vicekrat bez chyby.

Pouziti:
    python3 scripts/2026-09-13_regal_umisteni_zapsat.py            # dry-run
    python3 scripts/2026-09-13_regal_umisteni_zapsat.py --apply    # zapis
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

APPLY = "--apply" in sys.argv

UMISTENI = [
    ("RB", "bocni_strana", "Regál — boční strana (levá/pravá)",
     "Regál podél boční stěny nákladového prostoru. Kombinace RB × EB (euroboxy) "
     "je dnes jediná rozpracovaná - vzor Doblo C. Strana levá/pravá je orientace "
     "konkrétní sestavy, ne samostatný kód číselníku.", 10),
    ("RP", "prepazka", "Regál na přepážce",
     "Regál na přepážce (oddělovací stěna kabina/náklad). Nemá horní blok jako "
     "boční regály - u některých vozidel místo toho spodní blok "
     "(Robert 2026-09-13, koncept zatím nerozpracován).", 20),
    ("DP", "dvojita_podlaha", "Dvojitá podlaha",
     "Úložný prostor pod zvýšenou podlahou nákladového prostoru. "
     "Obsah/detaily zatím neurčeny.", 30),
    ("VZ", "vysuvne_bloky_zadni", "Výsuvné bloky ze zadních dveří",
     "Výsuvný blok přístupný zadními dveřmi vozidla. Obsah/detaily zatím neurčeny.", 40),
    ("VB", "vysuvne_bloky_bocni", "Výsuvné bloky z bočních dveří",
     "Výsuvný blok přístupný bočními dveřmi vozidla. Obsah/detaily zatím neurčeny.", 50),
    ("VP", "vysuvna_podlaha", "Výsuvná podlaha",
     "Celá podlaha nákladového prostoru jako výsuvný díl. Obsah/detaily zatím neurčeny.", 60),
]

UPRESNENI_TYPOLOGIE = [
    ("universal", " Upřesněno 2026-09-13: zahrnuje upínací police, police "
                  "organizéry, police vany, police sklopné dvířka - jednotlivé "
                  "podtypy zatím nemají vlastní rozpad."),
    ("ocelove_supliky", " Upřesněno 2026-09-13: = šuplíková stěna/regál. "
                        "Detaily konstrukce zatím neurčeny."),
    ("euroboxy_vysuvy", " Upřesněno 2026-09-13: = výsuvné euroboxy jako šuplíky. "
                        "Detaily konstrukce zatím neurčeny."),
]


def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SHOW TABLES LIKE 'regal_umisteni'")
    tabulka_existuje = cur.fetchone() is not None
    print(f"[tabulka regal_umisteni existuje] {tabulka_existuje}")

    if not tabulka_existuje:
        if APPLY:
            cur.execute("""
                CREATE TABLE regal_umisteni (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  kod CHAR(2) NOT NULL UNIQUE,
                  klic VARCHAR(32) NOT NULL UNIQUE,
                  nazev VARCHAR(128) NOT NULL,
                  popis TEXT,
                  aktivni TINYINT(1) NOT NULL DEFAULT 1,
                  sort_order INT NOT NULL DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            print("  -> vytvořeno")
        else:
            print("  -> (dry-run) vytvořilo by se")

    if not tabulka_existuje and not APPLY:
        print("[radky] přeskočeno, tabulka v dry-run ještě neexistuje")
    else:
        for kod, klic, nazev, popis, sort_order in UMISTENI:
            existuje = None
            if APPLY or tabulka_existuje:
                cur.execute("SELECT id FROM regal_umisteni WHERE klic=%s", (klic,))
                existuje = cur.fetchone()
            if existuje:
                print(f"  [{kod}] {klic} - už existuje, přeskočeno")
                continue
            print(f"  [{kod}] {klic} - {'zapisuji' if APPLY else '(dry-run) zapsalo by se'}")
            if APPLY:
                cur.execute(
                    "INSERT INTO regal_umisteni (kod, klic, nazev, popis, sort_order) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (kod, klic, nazev, popis, sort_order),
                )

    print("[upřesnění popisů regal_typologie]")
    for klic, dodatek in UPRESNENI_TYPOLOGIE:
        cur.execute("SELECT popis FROM regal_typologie WHERE klic=%s", (klic,))
        row = cur.fetchone()
        if not row:
            print(f"  [{klic}] NENALEZENO v regal_typologie - přeskočeno")
            continue
        popis = row["popis"] if isinstance(row, dict) else row[0]
        if popis and "Upřesněno 2026-09-13" in popis:
            print(f"  [{klic}] už upřesněno, přeskočeno")
            continue
        print(f"  [{klic}] {'zapisuji' if APPLY else '(dry-run) přidalo by se'} upřesnění")
        if APPLY:
            cur.execute("UPDATE regal_typologie SET popis=CONCAT(popis,%s) WHERE klic=%s",
                        (dodatek, klic))

    cur.execute("SHOW COLUMNS FROM product_assemblies LIKE 'umisteni_id'")
    sloupec_existuje = cur.fetchone() is not None
    print(f"[sloupec product_assemblies.umisteni_id existuje] {sloupec_existuje}")
    if not sloupec_existuje:
        if APPLY:
            cur.execute("""
                ALTER TABLE product_assemblies
                  ADD COLUMN umisteni_id INT NULL AFTER typologie_id,
                  ADD CONSTRAINT fk_pa_umisteni FOREIGN KEY (umisteni_id)
                    REFERENCES regal_umisteni(id)
            """)
            print("  -> přidán")
        else:
            print("  -> (dry-run) přidal by se")

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
