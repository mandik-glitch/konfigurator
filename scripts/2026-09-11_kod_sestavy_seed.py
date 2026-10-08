#!/usr/bin/env python3
"""Naplni ciselniky kodu sestavy a otaguje sestavy slozkami kodu.

Robert pres bot8, 2026-09-11. Schema: sql/2026-09-11_kod_sestavy_ciselniky.sql.
NAHRAZUJE scripts/2026-09-09_boxy_kombinace_seed.py (smazan ve stejnem
commitu, nikdy nebezel s --apply).

Co se proti verzi z 2026-09-09 zmenilo a PROC:

1. DETEKCE HORNIHO BLOKU BYLA SPATNE. Puvodne hledala vyplne (`vypln-`)
   nebo role s "horni" - jenze "horni" v nazvu role znamena DRUHE PASMO,
   ne horni blok jako celek. Jednopasmovy blok je cely z roli
   `podelnik-*-spodni` + `pricka-spodni-*`, takze provedeni 1 a 2 stara
   heuristika MINULA. Overeno nad 269 sestavami: spravny predikat
   `role.startswith("podelnik")` dava 14 sestav s blokem, stara heuristika
   12 - chybely prave sestavy 332 (provedeni 1) a 335 (provedeni 4).
   POZOR take na `pricka-uzavreni-vyrezu` (181 sestav): patri k NOZE pod
   blokem, ne k bloku - proto nikdy siroke startswith("pricka").

2. Kod nese navic TYPOLOGII a PROFIL (Robert 2026-09-11), takze se
   ciselniky rozsirily o regal_typologie + typologie_varianty.

3. Ciselnik horniho bloku ma sest provedeni cislovanych vzestupne (1-6)
   + nulty radek "bez"; drivejsich pet klicu (bez/eko/plne/polo/dvirka)
   pochazelo ze starych dopocitavanych os, ktere Robert 2026-09-10 odmitl.

Co skript ZAMERNE NEDELA:
- Neprejmenovava sestavy ani produkty (WORKFLOW.md pravidlo 23a: sahá se
  jen na vzorek, ktery Robert potvrdi).
- Nehada `profil_mm` z geometrie - Robert: "profil urcuje admin". Kde
  chybi, kod se nevygeneruje a skript to spocita v souhrnu.
- Neprideluje provedeni 1-6 STARYM blokum (sestavy 134/135/182/189/209/
  219/279/289). Robert 2026-09-11: "stare horni bloky neplati, vzorovy
  horni blok delame na Doblu C" - prestavi se podle vzoru, do te doby
  zustava horni_blok_varianta_id NULL a skript je vypise.
- Nedoplnuje car_model_id (WORKFLOW.md pravidlo 25 - shodilo by pojistku
  verejnych storefrontu). Kod karoserie jde do vlastniho pole.

Pouziti:
    python3 scripts/2026-09-11_kod_sestavy_seed.py            # dry-run
    python3 scripts/2026-09-11_kod_sestavy_seed.py --apply    # zapis
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_PATH = os.path.join(REPO_ROOT, "backups", "2026-09-11_kod_sestavy_pred_seedem.json")

APPLY = "--apply" in sys.argv

# Kod karoserie v nazvu sestavy. Pripona "e" je JINE vozidlo, ne varianta
# (WORKFLOW.md pravidlo 25), proto je soucasti zachyceneho kodu.
K_KOD_RE = re.compile(r"\bK-\d{3}e?\b")

# Vzorove sestavy sesti provedeni (shape_geometry_methods.id=9 v12,
# klic varianty_provedeni -> sestava_vzoru). Jine sestavy s blokem jsou
# stare a kod nedostavaji.
VZOR_SESTAVA_KOD = {332: "1", 333: "2", 334: "3", 335: "4", 336: "5", 337: "6"}

# Base36 abeceda pro 2mistny kod varianty typologie (97 hodnot dnes,
# kapacita 36*36 = 1296).
B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def kod_b36(n):
    """0 -> '01', 1 -> '02' ... (zacina od 1, aby '00' zustalo volne)."""
    n += 1
    return B36[n // 36] + B36[n % 36]


def eurobox_height_map(cur):
    """product_id -> vyska boxu (mm). Cte se z katalogu, nehardcoduje se."""
    cur.execute("SELECT id, name FROM shop_products WHERE name REGEXP '^eurobox_400x300x[0-9]+$'")
    return {r["id"]: int(r["name"].rsplit("x", 1)[1]) for r in cur.fetchall()}


def _parts(raw):
    try:
        d = raw if isinstance(raw, dict) else json.loads(raw)
    except (ValueError, TypeError):
        return []
    return [p for p in (d.get("parts") or []) if isinstance(p, dict)]


def spec_from_data(raw, height_by_pid):
    """Kanonicky rozpis boxu z data JSON. (None, {}) kdyz sestava boxy nema."""
    counts = Counter()
    for part in _parts(raw):
        pid = str(part.get("part_id") or "")
        if not pid.startswith("product_"):
            continue
        try:
            num = int(pid.split("_", 1)[1])
        except (ValueError, IndexError):
            continue
        h = height_by_pid.get(num)
        if h:
            counts[h] += 1
    if not counts:
        return None, {}
    spec = "-".join(f"{h}x{counts[h]}" for h in sorted(counts, reverse=True))
    return spec, dict(counts)


def ma_horni_blok(raw):
    """Spolehlivy predikat - viz docstring modulu, bod 1.

    Podelnik se mimo horni blok nevyskytuje, takze staci jeho pritomnost.
    NEPOUZIVAT vyplne ani "horni" v nazvu role."""
    return any(str(p.get("role") or "").startswith("podelnik") for p in _parts(raw))


def main():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            height_by_pid = eurobox_height_map(cur)
            if not height_by_pid:
                sys.exit("CHYBA: v katalogu nejsou produkty eurobox_400x300x* - neco je spatne.")

            cur.execute("SELECT id, name, data FROM product_assemblies ORDER BY id")
            rows = cur.fetchall()
            print(f"Sestav v DB: {len(rows)}")

            per_assembly = {}
            spec_counts = defaultdict(int)
            spec_breakdown = {}
            stare_bloky, bez_k_kodu = [], []

            for r in rows:
                spec, counts = spec_from_data(r["data"], height_by_pid)
                m = K_KOD_RE.search(r["name"] or "")
                k_kod = m.group(0) if m else None
                if not k_kod:
                    bez_k_kodu.append(r["id"])

                if not ma_horni_blok(r["data"]):
                    blok = "0"
                elif r["id"] in VZOR_SESTAVA_KOD:
                    blok = VZOR_SESTAVA_KOD[r["id"]]
                else:
                    blok = None          # stary blok - prestavi se podle vzoru
                    stare_bloky.append(r["id"])

                per_assembly[r["id"]] = {"spec": spec, "k_kod": k_kod, "blok": blok}
                if spec:
                    spec_counts[spec] += 1
                    spec_breakdown[spec] = counts

            print(f"Unikatnich rozpisu boxu: {len(spec_counts)}")
            print(f"Sestav s hornim blokem: {sum(1 for v in per_assembly.values() if v['blok'] != '0')}"
                  f" (z toho vzorovych 1-6: {sum(1 for v in per_assembly.values() if v['blok'] not in ('0', None))})")
            print(f"STARE bloky bez kodu (prestavi se podle vzoru): {stare_bloky}")
            if bez_k_kodu:
                print(f"Sestav bez K-kodu v nazvu: {len(bez_k_kodu)} (id: {bez_k_kodu[:15]})")

            # Poradi kodu: deterministicky podle rozpadu od nejvyssiho boxu,
            # zamerne BEZ semantiky cetnosti (ta se v case meni a kody by se
            # pri pristim behu precislovaly).
            def sort_key(spec):
                b = spec_breakdown[spec]
                return (-b.get(320, 0), -b.get(270, 0), -b.get(220, 0),
                        -b.get(170, 0), -b.get(120, 0), spec)

            ordered = sorted(spec_counts, key=sort_key)
            kod_by_spec = {spec: kod_b36(i) for i, spec in enumerate(ordered)}

            print("\nUkazka prvnich 8 variant typologie E:")
            for spec in ordered[:8]:
                print(f"  {kod_by_spec[spec]}  {spec:38s} ({spec_counts[spec]}x)")

            # Nahled kodu u vzorku (id=134) a u Dobla C (279 + 332-337)
            print("\nNahled kodu (profil chybi -> misto nej '??', urcuje admin):")
            for aid in (134, 279, 332, 333, 337):
                v = per_assembly.get(aid)
                if not v:
                    continue
                var = kod_by_spec.get(v["spec"], "??")
                blok = v["blok"] or "?"
                print(f"  id={aid:<4} {v['k_kod'] or '?????'}-E??{var}{blok}   ({v['spec']})")

            if not APPLY:
                print("\n[DRY-RUN] Nic se nezapsalo. Spust s --apply pro zapis.")
                return

            # ---- ZALOHA PRED ZAPISEM (dokonceny krok PRED zmenou) ----
            cur.execute("SELECT id, name, car_model_id, shop_product_id FROM product_assemblies ORDER BY id")
            backup = {
                "kdy": "2026-09-11",
                "co": "stav pred naplnenim ciselniku kodu sestavy a otagovanim",
                "sestavy": cur.fetchall(),
                "odvozeno": per_assembly,
            }
            os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
            with open(BACKUP_PATH, "w", encoding="utf-8", ) as f:
                json.dump(backup, f, ensure_ascii=False, indent=1, default=str)
            print(f"\nZaloha zapsana: {BACKUP_PATH}")

            cur.execute("SELECT id FROM regal_typologie WHERE kod='E'")
            typ_e = cur.fetchone()["id"]

            # ---- Rozpis boxu + varianty typologie E ----
            for i, spec in enumerate(ordered):
                b = spec_breakdown[spec]
                cur.execute(
                    "INSERT INTO boxy_kombinace (spec_kanonicky, n120, n170, n220, n270, n320, boxu_celkem) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE boxu_celkem=VALUES(boxu_celkem)",
                    (spec, b.get(120, 0), b.get(170, 0), b.get(220, 0), b.get(270, 0), b.get(320, 0),
                     sum(b.values())),
                )
                cur.execute("SELECT id FROM boxy_kombinace WHERE spec_kanonicky=%s", (spec,))
                box_id = cur.fetchone()["id"]
                cur.execute(
                    "INSERT INTO typologie_varianty (typologie_id, kod, nazev, boxy_kombinace_id, sort_order) "
                    "VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE nazev=VALUES(nazev)",
                    (typ_e, kod_by_spec[spec], spec, box_id, (i + 1) * 10),
                )
            print(f"Vlozeno rozpisu boxu / variant typologie E: {len(ordered)}")

            # ---- Otagovani sestav ----
            cur.execute("SELECT id, kod FROM typologie_varianty WHERE typologie_id=%s", (typ_e,))
            varianta_id_by_kod = {r["kod"]: r["id"] for r in cur.fetchall()}
            cur.execute("SELECT id, kod FROM horni_blok_varianty")
            blok_id_by_kod = {r["kod"]: r["id"] for r in cur.fetchall()}

            for aid, v in per_assembly.items():
                var_id = varianta_id_by_kod.get(kod_by_spec.get(v["spec"])) if v["spec"] else None
                cur.execute(
                    "UPDATE product_assemblies SET karoserie_kod=%s, typologie_id=%s, "
                    "typologie_varianta_id=%s, horni_blok_varianta_id=%s WHERE id=%s",
                    (v["k_kod"], typ_e if v["spec"] else None, var_id,
                     blok_id_by_kod.get(v["blok"]) if v["blok"] else None, aid),
                )
            print(f"Otagovano sestav: {len(per_assembly)}")
        conn.commit()
        print("COMMIT hotov.")
    finally:
        conn.close()

    # ---- OVERENI Z NOVEHO SPOJENI (chybejici vyjimka neni dukaz zapisu) ----
    conn2 = get_conn()
    try:
        with conn2.cursor() as cur:
            for t in ("regal_typologie", "boxy_kombinace", "typologie_varianty", "horni_blok_varianty"):
                cur.execute(f"SELECT COUNT(*) AS c FROM {t}")
                print(f"OVERENI {t}:", cur.fetchone()["c"])
            cur.execute("SELECT COUNT(*) AS c FROM product_assemblies WHERE typologie_varianta_id IS NOT NULL")
            print("OVERENI otagovanych sestav:", cur.fetchone()["c"])
            cur.execute(
                "SELECT a.id, a.karoserie_kod, a.profil_mm, t.kod AS typ, v.kod AS varianta, h.kod AS blok "
                "FROM product_assemblies a "
                "LEFT JOIN regal_typologie t ON t.id=a.typologie_id "
                "LEFT JOIN typologie_varianty v ON v.id=a.typologie_varianta_id "
                "LEFT JOIN horni_blok_varianty h ON h.id=a.horni_blok_varianta_id "
                "WHERE a.id IN (134, 279, 333) ORDER BY a.id"
            )
            for r in cur.fetchall():
                print("OVERENI vzorku:", r)
    finally:
        conn2.close()


if __name__ == "__main__":
    main()
