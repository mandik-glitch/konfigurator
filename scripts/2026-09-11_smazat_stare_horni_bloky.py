#!/usr/bin/env python3
"""Smaze STARE HORNI BLOKY z osmi produktovych sestav.

Robert 2026-09-11 (pres bot8): "stare horni bloky neplati, vzorovy horni
blok delame na Doblu C." Novy vzor sesti provedeni vznika na produktu 3942
(sestavy 332-337). Starsi horni bloky vznikly jinak, nebudou se cislovat
ani renderovat a maji zmizet, aby se podle nich nic nestavelo.

MAZE SE JEN HORNI BLOK, ne cela sestava - regal, boxy, nohy a
prislusenstvi zustavaji, aby sestava zustala pouzitelna a horni blok se do
ni dal pozdeji postavit podle vzoru.

=== PREDIKAT ROLI (nejsnaze se splete, proto vypsany cely) ===
SMAZAT:
  podelnik*        podelnik je VYHRADNE v hornim bloku
  vypln-*          vyplne a dna horniho bloku
  pricka-horni*, pricka-police*, pricka-spodni*
NEMAZAT:
  pricka-uzavreni-vyrezu   <- soucast NOHY pod blokem, ne horniho bloku.
                              Proto se NESMI pouzit siroke startsWith("pricka").
  cokoli dalsiho (nosnik*, spojnice*, eurobox*, uhelnik*, cap, predni-/
  zadni-svislice, zaslepka*, sloupek*, logo-ochrana*, dily bez role)

POZOR: "horni" v nazvu role NEZNAMENA horni blok - znamena DRUHE PASMO.
Jednopasmovy blok je cely z roli `podelnik-*-spodni` a `pricka-spodni-*`.
Spolehlivy test "ma horni blok" je role zacinajici na "podelnik" (overeno
bot8 nad vsemi 269 sestavami: 14 s blokem, 255 bez).

NESAHAT: 332-337 (sest provedeni vzoru). Skript je ma natvrdo mimo seznam
a po zapisu overuje, ze se jim nezmenila delka `data`.
POZOR: 279 (Doblo K-075 C) uz mezi nedotknutelne NEPATRI - viz CILE nize.
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402

os.environ.update(_env.load_env())

import app  # noqa: E402,F401 - drive nez product_assemblies (kruhovy import)
import product_assemblies  # noqa: E402

# 279 pribylo 2026-09-11 (bot8): Robert *"hole C jako 0/6 nema obsahovat
# zadny dil horniho bloku"*. Overeno v datech - 279 mela 9 dilu bloku
# (podelnik-*-spodni x4, pricka-spodni-0/1/2, vypln-dno-0/1), tedy fakticky
# kopii provedeni 2, proto ji vysel identicky kusovnik jako sestave 333.
# Puvodne byla na seznamu nedotknutelnych, to uz NEPLATI.
# Pravidlo je zapsane v receptu shape_geometry_methods.id=9 verze 13,
# sekce varianty_provedeni.kod_0.
CILE = [134, 135, 182, 189, 209, 219, 279, 289]
NEDOTYKAT = [332, 333, 334, 335, 336, 337]
ZALOHA = "/opt/konfigurator/backups/2026-09-11_stare_horni_bloky_pred_smazanim.json"
CHRANENE_PREFIXY = ("nosnik", "spojnice", "eurobox", "uhelnik")


def patri_do_horniho_bloku(role):
    r = role or ""
    return (
        r.startswith("podelnik")
        or r.startswith("vypln-")
        or r.startswith("pricka-horni")
        or r.startswith("pricka-police")
        or r.startswith("pricka-spodni")
    )


def _conn():
    return app.get_conn()


def main():
    dry = "--dry-run" in sys.argv
    ted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = _conn()
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(CILE))
            cur.execute(
                f"SELECT id, name, data FROM product_assemblies WHERE id IN ({fmt}) ORDER BY id",
                CILE,
            )
            radky = cur.fetchall()
    finally:
        conn.close()

    if len(radky) != len(CILE):
        print(f"CHYBA: ocekaval jsem {len(CILE)} sestav, nasel {len(radky)}.", file=sys.stderr)
        return 1

    # Baseline nedotcenych se bere ZA BEHU, ne z natvrdo zapsanych cisel.
    # Duvod (zmereno 2026-09-11): bot8 na provedenich 332-337 prave pracuje ve
    # scene, takze se jim delka `data` behem dne meni - 332 slo z 17456 na
    # 19516 behem jedine hodiny. Pevna baseline by proto hlasila falesnou
    # zmenu, a kdyby se cislo nahodou trefilo, tise by prehledla skutecnou.
    # Snimek tesne pred zapisem a porovnani po nem je jediny test, ktery
    # doopravdy dokazuje "nesahal jsem na ne".
    conn = _conn()
    try:
        with conn.cursor() as cur:
            fmt_n = ",".join(["%s"] * len(NEDOTYKAT))
            cur.execute(
                f"SELECT id, CHAR_LENGTH(data) dl FROM product_assemblies "
                f"WHERE id IN ({fmt_n})", NEDOTYKAT)
            baseline = {r["id"]: r["dl"] for r in cur.fetchall()}
    finally:
        conn.close()

    plan = []
    print(f"[{ted}] {'DRY-RUN' if dry else 'ZAPIS'} - smazani starych hornich bloku\n")
    for r in radky:
        d = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
        parts = d.get("parts", [])
        mazane = [p for p in parts if patri_do_horniho_bloku(p.get("role"))]
        zbyle = [p for p in parts if not patri_do_horniho_bloku(p.get("role"))]

        # POJISTKA: nic chraneneho se nesmi ocitnout v mazane mnozine
        chybne = [p.get("role") for p in mazane
                  if (p.get("role") or "").startswith(CHRANENE_PREFIXY)
                  or (p.get("role") or "") == "pricka-uzavreni-vyrezu"]
        if chybne:
            print(f"CHYBA: #{r['id']} by smazal chranene role: {chybne}", file=sys.stderr)
            return 1

        print(f"#{r['id']} {r['name'][:55]}")
        if not mazane:
            # PRESKOCIT, ne "smazat 0 dilu". Neni to kosmetika: dal by se
            # jinak vyprazdnil bom/price_summary sestave, ktera uz je cista -
            # a tim znicil CERSTVE PREPOCITANY kusovnik. Presne to hrozilo
            # u 279: nez se skript stihl spustit, vycistil ji nekdo jiny a
            # nechal ji prepocitat (92 dilu, 16 radku BOM, 9 167 Kc).
            print("   uz je cista (0 dilu horniho bloku) - PRESKAKUJI, nesaham na ni")
            continue
        print(f"   dilu {len(parts)} -> smazat {len(mazane)}, zustane {len(zbyle)}")
        print(f"   maze: {dict(sorted(Counter(p.get('role') for p in mazane).items()))}")
        plan.append((r, d, zbyle, len(mazane)))

    celkem = sum(p[3] for p in plan)
    print(f"\nCELKEM ke smazani: {celkem} dilu z {len(plan)} sestav "
          f"(z {len(radky)} na seznamu; zbytek uz byl cisty)")

    if not plan:
        print("Neni co delat - vsechny sestavy na seznamu uz jsou bez horniho bloku.")
        return 0

    if dry:
        print("\n--dry-run: nic se nezapisuje.")
        return 0

    # --- ZALOHA PRED ZAPISEM, jako dokonceny krok ---
    os.makedirs(os.path.dirname(ZALOHA), exist_ok=True)
    zaloha = {
        "vytvoreno": datetime.now().isoformat(),
        "duvod": "smazani starych hornich bloku (Robert 2026-09-11 pres bot8)",
        "sestavy": [{"id": r["id"], "name": r["name"], "data": d} for r, d, _z, _n in plan],
    }
    with open(ZALOHA, "w", encoding="utf-8") as f:
        json.dump(zaloha, f, ensure_ascii=False, indent=1, default=str)
        f.flush()
        os.fsync(f.fileno())
    velikost = os.path.getsize(ZALOHA)
    if velikost < 1000:
        print(f"CHYBA: zaloha {ZALOHA} je podezrele mala ({velikost} B) - NEZAPISUJI.",
              file=sys.stderr)
        return 1
    print(f"\nZaloha PRED zapisem: {ZALOHA} ({velikost} B, {len(plan)} sestav)")

    # --- ZAPIS ---
    conn = _conn()
    try:
        with conn.cursor() as cur:
            mapy = product_assemblies.nacti_mapy_znacek(cur)
            for r, d, zbyle, n in plan:
                d["parts"] = zbyle
                # bom/price_summary jsou snimky ze sceny z okamziku ulozeni -
                # po odebrani dilu uz nesedi. Vyprazdnit je cistsi nez
                # dopocitavat: kusovnik se stejne pocita znovu pri dalsim
                # ulozeni ze sceny a skladova karta si ho v zalozce 3D model
                # dopocita ziva.
                if d.get("bom"):
                    d["bom"] = []
                if d.get("price_summary"):
                    d["price_summary"] = None
                # join_groups/frame_groups jsou u vsech osmi PRAZDNE (overeno),
                # takze neni co odpojovat - kdyby nekdy nebyly, tohle je misto,
                # kde by se odkazy na zmizele dily musely vycistit.
                for klic in ("join_groups", "frame_groups"):
                    if d.get(klic):
                        print(f"   POZOR: #{r['id']} ma neprazdne {klic} - "
                              f"zkontroluj odkazy rucne!", file=sys.stderr)
                novy = json.dumps(d, ensure_ascii=False)
                cur.execute(
                    "UPDATE product_assemblies SET data=%s WHERE id=%s", (novy, r["id"])
                )
                file_id = product_assemblies.zrcadli_sestavu_na_disk(
                    cur, r["id"], r["name"], d, None, mapy=mapy
                )
                print(f"   #{r['id']}: -{n} dilu, zrcadlo na disku file_id={file_id}")
        conn.commit()
    finally:
        conn.close()

    # --- KONTROLA CERSTVYM SPOJENIM ---
    conn = _conn()
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(CILE))
            cur.execute(
                f"SELECT id, data FROM product_assemblies WHERE id IN ({fmt}) ORDER BY id", CILE)
            print("\nKontrola cerstvym spojenim (cile):")
            for r in cur.fetchall():
                d = json.loads(r["data"])
                zbylo_bloku = [p.get("role") for p in d["parts"]
                               if patri_do_horniho_bloku(p.get("role"))]
                uzavreni = sum(1 for p in d["parts"]
                               if (p.get("role") or "") == "pricka-uzavreni-vyrezu")
                print(f"  #{r['id']}: dilu {len(d['parts'])}, zbytky horniho bloku "
                      f"{zbylo_bloku or 'zadne OK'}, pricka-uzavreni-vyrezu {uzavreni}")
            fmt2 = ",".join(["%s"] * len(NEDOTYKAT))
            cur.execute(
                f"SELECT id, CHAR_LENGTH(data) dl FROM product_assemblies "
                f"WHERE id IN ({fmt2}) ORDER BY id", NEDOTYKAT)
            print("\nKontrola NEDOTCENYCH (provedeni vzoru 332-337):")
            zmenene = []
            for r in cur.fetchall():
                pred = baseline.get(r["id"])
                shoda = (pred == r["dl"])
                if not shoda:
                    zmenene.append((r["id"], pred, r["dl"]))
                print(f"  #{r['id']}: delka data {r['dl']} (pred zapisem {pred}) "
                      f"{'OK' if shoda else '<<< ZMENA!'}")
    finally:
        conn.close()

    if zmenene:
        # Pozor: nemusi to nutne znamenat moji chybu - na 332-337 muze
        # soubezne pracovat bot8 ve scene. Ale hlasi se to jako selhani,
        # protoze "nekdo jiny to zmenil behem meho behu" je stav, ktery ma
        # clovek videt, ne prehlednout.
        print(f"\nCHYBA: nedotcene sestavy zmenily delku behem behu: {zmenene}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
