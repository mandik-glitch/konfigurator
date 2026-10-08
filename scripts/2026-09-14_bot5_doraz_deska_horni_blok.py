#!/usr/bin/env python3
"""Rozdeli sdileny katalog horni_blok_varianty tam, kde K-075 ma skutecnou
geometrickou odchylku od generickeho vzoru (dorazova deska u prepazky).

Kontext (bot8, 2026-09-14, shape_geometry_methods.id=13,
"dorazova_deska_odchylka"): Robert primo pozadal, aby varianty BEZ (nebo
jen s castecnymi) vyplnemi dostaly JEDNU vyplen do predni nohy u
prepazky jako dorazovou plochu na tyce/trubky - brani sesmeknuti
predmetu ulozenych primo na profilech ("eko" zpusob ukladani, metoda
id=9) az k prepazce. Tenhle rozdil se tyka DVOU generickych radku:

  kod "02" (id=3, "Jedno pásmo - rám + dna [ZÁKLAD]") - SDILENY s Jumpy
  (348/349/350/351/353/354, 6 z 9 uzivatelu) - NELZE upravit primo,
  vytvarim NOVY vyhrazeny radek jen pro K-075 (344/369/370).

  kod "04" (id=5, "Dvě pásma - police jen příčky") - VYHRADNE K-075
  (343/379/382, 3 z 3 uzivatelu, zadny jiny vuz) - BEZPECNE upravit
  PRIMO na miste, zadne repointovani ani novy radek potreba.

Po vytvoreni noveho radku se repointuji jen ty 3 K-075 sestavy
(344/369/370, NE Jumpy) a znovu spocita jejich kod_sestavy pres
kanonicky _kod_sestavy.py::sestavit_kod_sestavy() (horni_blok_kod se
zmenil, ostatnich 7 segmentu ne).

Zaloha do backups/, idempotentni (prepocitava jen kdyz horni_blok
zjisteni z DB nesouhlasi s cilovym stavem).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-14_bot5_doraz_deska_horni_blok.py
    api/venv/bin/python3 scripts/2026-09-14_bot5_doraz_deska_horni_blok.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402
from _kod_sestavy import sestavit_kod_sestavy  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-14_bot5_doraz_deska_horni_blok",
)

# ---- 1) novy vyhrazeny radek pro K-075 misto sdileneho kod="02" (id=3) ----
NOVY_RADEK_KOD = "07"
NOVY_RADEK = {
    "kod": NOVY_RADEK_KOD,
    "klic": "jedno_pasmo_ram_dna_doraz",
    "nazev": "Jedno pásmo - rám + dna, s dorazovou deskou [ZÁKLAD]",
    "lisi_se": (
        "Jako kod 02 (jedno pásmo, rám + dna), navíc JEDNA výplň v přední "
        "noze u přepážky (role vypln-bok-prepazka, product_3939) jako "
        "dorazová plocha - brání sesmeknutí předmětů uložených přímo na "
        "profilech (\"eko\" způsob ukládání, bez boxu) až k přepážce. "
        "Proti kod 02 tedy o 1 díl víc (9->10 dílů celkem)."
    ),
    "slozeni": json.dumps({
        "vypln-dno-*": 2, "pricka-spodni-*": 3, "podelnik-celni-spodni-*": 2,
        "podelnik-zadni-spodni-*": 2, "vypln-bok-prepazka": 1,
    }, ensure_ascii=False),
    "prepinace": "--jedno-pasmo --doraz-prepazka",
    "sestava_vzoru": 369,  # Doblo K-075 A-01 - prvni overena realizace
    "sort_order": 70,
    "popis_zakaznicky": (
        "Nad euroboxy je jedno patro s pevným dnem z MDF desky, doplněné "
        "dorazovou deskou u přepážky - brání sklouznutí předmětů uložených "
        "přímo na profilech k přepážce."
    ),
}
# K-075 sestavy, ktere se maji repointovat na novy radek (Jumpy NEDOTCEN)
REPOINT_NA_NOVY_RADEK = (344, 369, 370)  # C-01, A-01, B-01

# ---- 2) uprava existujiciho radku kod="04" (id=5) PRIMO NA MISTE -
# vsichni 3 uzivatele jsou K-075, zadne jine auto ho nepouziva ----
ID_KOD_04 = 5
NOVY_LISI_SE_KOD_04 = (
    "Proti kod 03 jsou horní příčky NAHRAZENY příčkami police (v "
    "polovině výšky), s JEDNOU vyjimkou u přepážky: misto generické "
    "pricka-police-0 je tam role vypln-bok-prepazka (product_3939) jako "
    "dorazová deska - brání sesmeknutí předmětů uložených přímo na "
    "profilech (\"eko\" způsob ukládání, bez boxu) až k přepážce. Police "
    "nemá vlastní podélníky ani desku (mimo tuhle jednu výjimku)."
)
NOVY_SLOZENI_KOD_04 = json.dumps({
    "pricka-police-*": 2, "vypln-bok-prepazka": 1, "pricka-spodni-*": 3,
    "podelnik-celni-horni": 1, "podelnik-zadni-horni": 1,
    "podelnik-celni-spodni-*": 2, "podelnik-zadni-spodni-*": 2,
}, ensure_ascii=False)
NOVY_POPIS_ZAKAZNICKY_KOD_04 = (
    "Nad euroboxy jsou dvě patra s policí v polovině výšky - police tvoří "
    "nosné příčky doplněné dorazovou deskou u přepážky, která brání "
    "sklouznutí předmětů uložených přímo na profilech."
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== dorazova deska - novy radek + uprava kod=04 — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = {"novy_radek_id": None, "repointed": [], "kod_04_puvodni": None}
    try:
        with conn.cursor() as cur:
            # --- krok 1: novy radek ---
            cur.execute("SELECT id FROM horni_blok_varianty WHERE kod=%s", (NOVY_RADEK_KOD,))
            existing = cur.fetchone()
            if existing:
                print(f"  Radek kod={NOVY_RADEK_KOD} uz existuje (id={existing['id']}), preskakuji vytvoreni.")
                novy_radek_id = existing["id"]
            else:
                print(f"  Vytvarim novy radek kod={NOVY_RADEK_KOD}: {NOVY_RADEK['nazev']}")
                novy_radek_id = None
                if args.apply:
                    cur.execute(
                        "INSERT INTO horni_blok_varianty "
                        "(kod, klic, nazev, lisi_se, slozeni, prepinace, sestava_vzoru, aktivni, sort_order, popis_zakaznicky) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s,%s)",
                        (NOVY_RADEK["kod"], NOVY_RADEK["klic"], NOVY_RADEK["nazev"], NOVY_RADEK["lisi_se"],
                         NOVY_RADEK["slozeni"], NOVY_RADEK["prepinace"], NOVY_RADEK["sestava_vzoru"],
                         NOVY_RADEK["sort_order"], NOVY_RADEK["popis_zakaznicky"]),
                    )
                    novy_radek_id = cur.lastrowid
            zaloha["novy_radek_id"] = novy_radek_id

            # --- krok 2: repointovat jen K-075 (NE Jumpy) ---
            for aid in REPOINT_NA_NOVY_RADEK:
                cur.execute(
                    "SELECT pa.id, pa.name, pa.horni_blok_varianta_id, "
                    "       pa.karoserie_kod, pa.profil_mm, pa.verze, pa.dodatek, "
                    "       ru.kod AS umisteni_kod, rt.kod AS typologie_kod, tv.kod AS varianta_kod "
                    "FROM product_assemblies pa "
                    "LEFT JOIN regal_umisteni ru ON ru.id = pa.umisteni_id "
                    "LEFT JOIN regal_typologie rt ON rt.id = pa.typologie_id "
                    "LEFT JOIN typologie_varianty tv ON tv.id = pa.typologie_varianta_id "
                    "WHERE pa.id=%s", (aid,),
                )
                r = cur.fetchone()
                if not r:
                    print(f"  id={aid}: sestava neexistuje, preskakuji"); continue
                if r["horni_blok_varianta_id"] == novy_radek_id:
                    print(f"  id={aid} ({r['name']}): uz repointovano, preskakuji")
                    continue
                novy_kod_sestavy = sestavit_kod_sestavy(
                    karoserie_kod=r["karoserie_kod"], umisteni_kod=r["umisteni_kod"],
                    typologie_kod=r["typologie_kod"], profil_mm=r["profil_mm"],
                    verze=r["verze"], varianta_kod=r["varianta_kod"],
                    horni_blok_kod=NOVY_RADEK_KOD, dodatek=r["dodatek"] or 0,
                )
                print(f"  id={aid} ({r['name']}): horni_blok_varianta_id {r['horni_blok_varianta_id']} -> "
                      f"{novy_radek_id or '(bude prirazeno pri apply)'}, kod_sestavy -> {novy_kod_sestavy}")
                zaloha["repointed"].append({
                    "id": aid, "puvodni_horni_blok_varianta_id": r["horni_blok_varianta_id"],
                    "puvodni_kod_sestavy": None,
                })
                if args.apply:
                    cur.execute(
                        "UPDATE product_assemblies SET horni_blok_varianta_id=%s, kod_sestavy=%s WHERE id=%s",
                        (novy_radek_id, novy_kod_sestavy, aid),
                    )

            # --- krok 3: upravit existujici radek kod=04 PRIMO (vsichni 3 uzivatele K-075) ---
            cur.execute("SELECT id, lisi_se, slozeni, popis_zakaznicky FROM horni_blok_varianty WHERE id=%s", (ID_KOD_04,))
            puvodni04 = cur.fetchone()
            if puvodni04 and puvodni04["lisi_se"] != NOVY_LISI_SE_KOD_04:
                print(f"\n  Upravuji radek id={ID_KOD_04} (kod=04) PRIMO - vsichni 3 uzivatele jsou K-075.")
                zaloha["kod_04_puvodni"] = {
                    "lisi_se": puvodni04["lisi_se"], "slozeni": puvodni04["slozeni"],
                    "popis_zakaznicky": puvodni04["popis_zakaznicky"],
                }
                if args.apply:
                    cur.execute(
                        "UPDATE horni_blok_varianty SET lisi_se=%s, slozeni=%s, popis_zakaznicky=%s WHERE id=%s",
                        (NOVY_LISI_SE_KOD_04, NOVY_SLOZENI_KOD_04, NOVY_POPIS_ZAKAZNICKY_KOD_04, ID_KOD_04),
                    )
            else:
                print(f"\n  Radek id={ID_KOD_04} (kod=04) uz ma aktualni text, preskakuji.")

        if args.apply:
            os.makedirs(ZALOHA_DIR, exist_ok=True)
            with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                json.dump(zaloha, f, ensure_ascii=False, indent=2, default=str)
            conn.commit()
            print("\nCOMMIT hotovy.")
        else:
            print("\nDRY-RUN: nic nezapsano.")
    finally:
        conn.close()

    if args.apply:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                print("\n=== OVERENI z noveho spojeni ===")
                cur.execute("SELECT id, kod, nazev FROM horni_blok_varianty WHERE kod=%s", (NOVY_RADEK_KOD,))
                print("Novy radek:", cur.fetchone())
                for aid in REPOINT_NA_NOVY_RADEK:
                    cur.execute("SELECT id, name, horni_blok_varianta_id, kod_sestavy FROM product_assemblies WHERE id=%s", (aid,))
                    print(" ", cur.fetchone())
                # Jumpy MUSI zustat na puvodnim radku (id=3, kod=02) - kontrola, ze se nic neposunulo
                cur.execute("SELECT id, name, horni_blok_varianta_id FROM product_assemblies WHERE id IN (348,349,350,351,353,354)")
                print("Jumpy (musi zustat horni_blok_varianta_id=3):")
                for r in cur.fetchall():
                    znacka = "OK" if r["horni_blok_varianta_id"] == 3 else "CHYBA - ZMENENO!"
                    print(f"   {r['id']} {r['name']}: horni_blok_varianta_id={r['horni_blok_varianta_id']} [{znacka}]")
                cur.execute("SELECT lisi_se, popis_zakaznicky FROM horni_blok_varianty WHERE id=%s", (ID_KOD_04,))
                print("kod=04 po uprave:", cur.fetchone())
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
