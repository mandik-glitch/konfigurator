#!/usr/bin/env python3
"""Prevede ciselnik na Robertuv presny tvar kodu a vygeneruje kody u vzoru.

Robert 2026-09-11 (pres bot8) urcil doslovny tvar:

    K-075-EB-30-A-0001-2-0
    karoserie - typologie(2) - profil - VERZE - rozpis boxu(4) - blok - dodatek

Navazuje na sql/2026-09-11b_kod_sestavy_format_roberta.sql.

CO SKRIPT DELA:
 1. Precisluje kody variant typologie z base36 (1R) na ctyri cislice
    (0001-0097). Poradi zustava totozne s prvnim seedem - radi se podle
    stejneho klice, takze se kody nezamichaji.
 2. Naplni novy sloupec `verze` (A-E).
 3. Zapise profil 30 u SEDMI sestav vzoru (279 + 332-337). Robert
    2026-09-11: "Doblo C = 30, doplnte." Na zbytek katalogu NESAHA -
    profily tam urcuje admin.
 4. Vygeneruje `kod_sestavy` u kazde sestavy, kde jsou VSECHNY slozky
    znamé. Kde chybi profil (zbytek katalogu), kod se nevygeneruje.
 5. Prejmenuje SEST variant vzoru (332-337) podle vygenerovaneho kodu.
    Sestavu 279 zamerne NEPREJMENOVAVA - odvozuje se od ni nazev produktu
    a to je otevrena otazka na Roberta (bot8).

JAK SE ZJISTUJE VERZE (bod 2) - overeno, nehadano:
  a) uzky vzor  `K-XXX[e] <PISMENO>`      -> 180 sestav
  b) siroky vzor `<PISMENO> - boxyNN`     -> 262 sestav
  Oba vzory se na spolecnem prunniku shoduji v 100 % pripadu (0 konfliktu),
  siroky navic zachyti Proace ("Proace Compact 16- A - boxy43-..."), kde
  pismeno nestoji za K-kodem. Pouziva se tedy siroky.
  c) sest variant vzoru (332-337) nema v nazvu nic - zdedi verzi od
     ZAKLADNI sestavy na tomtez produktu (279 = "Doblo K-075 C" -> C).
     Vede se zvlast, at je videt, co je odecet a co dedeni.
  Kde ani jedno, zustava NULL (dnes jediny pripad: id=189).

Pouziti:
    python3 scripts/2026-09-11_kod_sestavy_format.py            # dry-run
    python3 scripts/2026-09-11_kod_sestavy_format.py --apply    # zapis
"""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_PATH = os.path.join(REPO_ROOT, "backups", "2026-09-11_kod_sestavy_format_pred_zmenou.json")

APPLY = "--apply" in sys.argv

VZOR_SESTAVY = [279, 332, 333, 334, 335, 336, 337]   # Doblo C - vzor, profil 30
PREJMENOVAT = [332, 333, 334, 335, 336, 337]         # 279 NE (viz docstring)
PROFIL_VZORU = 30

VERZE_UZKY = re.compile(r"\bK-\d{3}e?\s+([A-E])\b")
VERZE_SIROKY = re.compile(r"(?:^|[\s-])([A-E])\s+-\s+boxy\d+")


def zjisti_verze(rows):
    """Vraci (verze_by_id, zdroj_by_id). Zdroj: 'nazev' / 'dedeno' / None."""
    verze, zdroj = {}, {}
    for r in rows:
        m = VERZE_SIROKY.search(r["name"] or "") or VERZE_UZKY.search(r["name"] or "")
        if m:
            verze[r["id"]] = m.group(1)
            zdroj[r["id"]] = "nazev"

    # Dedeni od sourozence na tomtez produktu - jen kdyz je jednoznacne
    podle_produktu = {}
    for r in rows:
        if r["id"] in verze and r["shop_product_id"]:
            podle_produktu.setdefault(r["shop_product_id"], set()).add(verze[r["id"]])
    for r in rows:
        if r["id"] in verze or not r["shop_product_id"]:
            continue
        kandidati = podle_produktu.get(r["shop_product_id"], set())
        if len(kandidati) == 1:
            verze[r["id"]] = next(iter(kandidati))
            zdroj[r["id"]] = "dedeno"
    return verze, zdroj


def sestav_kod(karoserie, typologie, profil, verze, varianta, blok, dodatek):
    """Robertuv tvar. Vraci None, kdyz kterakoli slozka chybi."""
    if not all([karoserie, typologie, profil, verze, varianta, blok is not None]):
        return None
    return f"{karoserie}-{typologie}-{profil}-{verze}-{varianta}-{blok}-{dodatek}"


def main():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # ---- 1) Precislovani variant na 4 cislice ----
            cur.execute(
                "SELECT v.id, v.kod, v.sort_order, b.spec_kanonicky "
                "FROM typologie_varianty v LEFT JOIN boxy_kombinace b ON b.id=v.boxy_kombinace_id "
                "ORDER BY v.sort_order, v.id"
            )
            varianty = cur.fetchall()
            nove_kody = {v["id"]: f"{i:04d}" for i, v in enumerate(varianty, start=1)}
            print(f"Variant k precislovani: {len(varianty)}")
            for v in varianty[:5]:
                print(f"  {v['kod']} -> {nove_kody[v['id']]}   {v['spec_kanonicky']}")

            # ---- 2) Verze ----
            cur.execute("SELECT id, name, shop_product_id FROM product_assemblies ORDER BY id")
            rows = cur.fetchall()
            verze, zdroj = zjisti_verze(rows)
            bez_verze = [r["id"] for r in rows if r["id"] not in verze]
            print(f"\nVerze: z nazvu {sum(1 for z in zdroj.values() if z == 'nazev')}, "
                  f"dedeno {sum(1 for z in zdroj.values() if z == 'dedeno')}, "
                  f"BEZ VERZE {len(bez_verze)} {bez_verze}")
            print(f"  rozpad: {dict(Counter(verze.values()))}")

            # ---- 3+4) Nahled kodu u vzoru ----
            cur.execute(
                "SELECT a.id, a.name, a.karoserie_kod, a.dodatek, t.kod AS typ, "
                "       v.id AS var_id, h.kod AS blok "
                "FROM product_assemblies a "
                "LEFT JOIN regal_typologie t ON t.id=a.typologie_id "
                "LEFT JOIN typologie_varianty v ON v.id=a.typologie_varianta_id "
                "LEFT JOIN horni_blok_varianty h ON h.id=a.horni_blok_varianta_id "
                "WHERE a.id IN (%s)" % ",".join(str(i) for i in VZOR_SESTAVY)
            )
            print("\nKody vzoru (profil 30 doplni tenhle skript):")
            for r in cur.fetchall():
                kod = sestav_kod(r["karoserie_kod"], "EB", PROFIL_VZORU, verze.get(r["id"]),
                                 nove_kody.get(r["var_id"]), r["blok"], r["dodatek"])
                zmena = " -> PREJMENOVAT" if r["id"] in PREJMENOVAT else ""
                print(f"  {r['id']:>4}  {kod}{zmena}")

            if not APPLY:
                print("\n[DRY-RUN] Nic se nezapsalo. Spust s --apply pro zapis.")
                return

            # ---- ZALOHA PRED ZAPISEM ----
            cur.execute("SELECT id, name, kod_sestavy FROM product_assemblies ORDER BY id")
            backup = {
                "kdy": "2026-09-11",
                "co": "stav pred prevodem na Robertuv tvar kodu (precislovani variant, verze, profil vzoru, prejmenovani 332-337)",
                "sestavy": cur.fetchall(),
                "varianty_stare_kody": [{"id": v["id"], "kod": v["kod"]} for v in varianty],
            }
            os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
            with open(BACKUP_PATH, "w", encoding="utf-8") as f:
                json.dump(backup, f, ensure_ascii=False, indent=1, default=str)
            print(f"\nZaloha zapsana: {BACKUP_PATH}")

            # Precislovani pres docasnou hodnotu, aby se netriskla UNIQUE
            for v in varianty:
                cur.execute("UPDATE typologie_varianty SET kod=%s WHERE id=%s",
                            (f"T{v['id']:03d}"[:4], v["id"]))
            for v in varianty:
                cur.execute("UPDATE typologie_varianty SET kod=%s WHERE id=%s",
                            (nove_kody[v["id"]], v["id"]))
            print(f"Precislovano variant: {len(varianty)}")

            for aid, vz in verze.items():
                cur.execute("UPDATE product_assemblies SET verze=%s WHERE id=%s", (vz, aid))
            print(f"Zapsano verzi: {len(verze)}")

            cur.execute(
                "UPDATE product_assemblies SET profil_mm=%s WHERE id IN (%s)"
                % ("%s", ",".join(str(i) for i in VZOR_SESTAVY)), (PROFIL_VZORU,))
            print(f"Profil {PROFIL_VZORU} zapsan u {len(VZOR_SESTAVY)} sestav vzoru")

            # ---- Generovani kodu ----
            cur.execute(
                "SELECT a.id, a.karoserie_kod, a.profil_mm, a.verze, a.dodatek, "
                "       t.kod AS typ, v.kod AS varianta, h.kod AS blok "
                "FROM product_assemblies a "
                "LEFT JOIN regal_typologie t ON t.id=a.typologie_id "
                "LEFT JOIN typologie_varianty v ON v.id=a.typologie_varianta_id "
                "LEFT JOIN horni_blok_varianty h ON h.id=a.horni_blok_varianta_id"
            )
            vygenerovano = 0
            for r in cur.fetchall():
                kod = sestav_kod(r["karoserie_kod"], r["typ"], r["profil_mm"], r["verze"],
                                 r["varianta"], r["blok"], r["dodatek"])
                if kod:
                    cur.execute("UPDATE product_assemblies SET kod_sestavy=%s WHERE id=%s", (kod, r["id"]))
                    vygenerovano += 1
            print(f"Vygenerovano kodu: {vygenerovano}")

            # ---- Prejmenovani SESTI variant vzoru ----
            cur.execute("SELECT id, name, kod_sestavy FROM product_assemblies WHERE id IN (%s)"
                        % ",".join(str(i) for i in PREJMENOVAT))
            for r in cur.fetchall():
                if not r["kod_sestavy"]:
                    print(f"  POZOR: {r['id']} nema kod, neprejmenovavam")
                    continue
                popis = r["name"].split(" - ", 1)[1] if " - " in r["name"] else ""
                novy = f"{r['kod_sestavy']} - {popis}" if popis else r["kod_sestavy"]
                cur.execute("UPDATE product_assemblies SET name=%s WHERE id=%s", (novy, r["id"]))
                print(f"  {r['id']}: {r['name'][:40]} -> {novy}")
        conn.commit()
        print("COMMIT hotov.")
    finally:
        conn.close()

    # ---- OVERENI Z NOVEHO SPOJENI ----
    conn2 = get_conn()
    try:
        with conn2.cursor() as cur:
            cur.execute("SELECT kod, klic FROM regal_typologie ORDER BY sort_order")
            print("\nOVERENI typologie:", [(r["kod"], r["klic"]) for r in cur.fetchall()])
            cur.execute("SELECT COUNT(*) c FROM typologie_varianty WHERE kod REGEXP '^[0-9]{4}$'")
            print("OVERENI variant se 4mistnym kodem:", cur.fetchone()["c"])
            cur.execute("SELECT COUNT(*) c FROM product_assemblies WHERE verze IS NOT NULL")
            print("OVERENI sestav s verzi:", cur.fetchone()["c"])
            cur.execute("SELECT COUNT(*) c FROM product_assemblies WHERE kod_sestavy IS NOT NULL")
            print("OVERENI sestav s kodem:", cur.fetchone()["c"])
            cur.execute("SELECT id, kod_sestavy, name FROM product_assemblies "
                        "WHERE id IN (279,332,333,334,335,336,337) ORDER BY id")
            for r in cur.fetchall():
                print(f"  {r['id']:>4}  {str(r['kod_sestavy']):<28} {r['name'][:46]}")
    finally:
        conn2.close()


if __name__ == "__main__":
    main()
