#!/opt/konfigurator/api/venv/bin/python
"""Audit: najde regály, jejichž postavené nohy PŘESAHUJÍ oficiální výšku
otvoru zadních dveří (bot16, 2026-09-03, Robert: "udelej script ktery najde
karoserie jejichz nohy presahuji vyskove vstupni otvor zadnich dveri...",
doplněno: "aplikuji pravidlo o vysce nohou versus zadni otvor dveri a
mezera 30 milimetru na vsechny nohy ve scene v produktovych sestavach").

Pravidlo: žádný sloupec regálu by neměl být postaven výš, než oficiální
výška otvoru zadních dveří MÍNUS 30mm bezpečnostní rezerva
(karoserie_model_reference.official_door_opening_height_mm - 30) - jinak
by se horní patra nedala přes tenhle otvor bezpečně naložit/vyložit.

READ-ONLY. Nic v DB nemění. Kontroluje jen řádky, u kterých MÁME oficiální
hodnotu.

MĚŘICÍ ROVINA = KONEC PROFILU (Robert rozhodl 2026-09-03, přes bot3)
--------------------------------------------------------------------------
Doslovně: "měřit ke konci profilu, ne k čelu záslepky (záslepka je jen
kosmetická, nenosná)". Limit `dveře - 30` se tedy porovnává s koncem
hliníkového profilu; 3mm přesah záslepky nad ním se NEPOČÍTÁ. Zapsáno i do
`shape_geometry_methods.id=8` (version 6) - platí pro audit i pro stavbu.

Původní verze skriptu měřila jen `cap.position.y` a hlásila 74/120 řádků
jako porušení. Doměřením skutečné GLB geometrie se ukázalo, že 73 z nich
NENÍ vada, ale konstantní 3mm konvence záslepky:

  - `product_3071.glb` (záslepka) je 30x30x**9mm** deska a v sestavách je
    natočená tak, že její lokální +Z (tloušťka) míří DOLŮ (ověřeno přes
    quaternion na id=91/103/182). Počátek dílu je tedy její HORNÍ plocha:
    záslepka zapadá 6mm do profilu a 3mm přečnívá nad jeho konec.
  - `profil_top` (konec hliníkového profilu Object_7, 30x1000x30 centrovaný
    v Y) sedí u 73 řádků PŘESNĚ na `dveře - 30` - tedy na milimetr přesně
    tak, jak to zapsalo pravidlo `shape_geometry_methods.id=8`.
  - `cap_top` = `profil_top + 3` je skutečný FYZICKÝ vrchol nohy.

Skript reportuje obě hodnoty (`profilTop` je ROZHODUJÍCÍ, `fyzTop` jen
informativně), ale za porušení se počítá VÝHRADNĚ přesah konce profilu.

Použití:
    scripts/2026-09-03_audit_leg_height_vs_door.py              # jen prekrocene
    scripts/2026-09-03_audit_leg_height_vs_door.py --all        # vsechny s hodnotou
    scripts/2026-09-03_audit_leg_height_vs_door.py --json out.json
"""
import argparse
import json
import os
import re
import sys

BASE_UNIT_H = 1000.0  # Object_7 vertikala ma pri scale.y=1 vysku 1000mm (overeno primo z GLB bboxu)
SAFETY_MARGIN_MM = 30


def load_env():
    with open("/opt/konfigurator/api/.env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def column_tops(parts_in_column):
    """Vrati (profil_top, cap_top) - konec profilu a fyzicky vrchol vc. zaslepky.

    Kterakoli z hodnot muze byt None, pokud sloupec dany typ dilu nema.
    """
    cap_ys = []
    for p in parts_in_column:
        role = p.get("role") or ""
        if "zaslepka" in role or role == "cap":
            cap_ys.append(p["position"][1])
    cap_top = max(cap_ys) if cap_ys else None

    profil_top = None
    for p in parts_in_column:
        role = p.get("role") or ""
        if "svislice" in role and p.get("part_id") == "Object_7":
            scale_y = (p.get("scale") or [1, 1, 1])[1]
            top = p["position"][1] + scale_y * BASE_UNIT_H / 2
            if profil_top is None or top > profil_top:
                profil_top = top
    return profil_top, cap_top


def analyze_row(row_id, name, data, door_height, code):
    parts = data.get("parts") or []
    by_z = {}
    for p in parts:
        role = p.get("role") or ""
        if not role:
            continue
        if "svislice" in role or "zaslepka" in role or role == "cap" or "sloupek" in role:
            z = round(p["position"][2])
            by_z.setdefault(z, []).append(p)

    cols = []
    for z, ps in sorted(by_z.items()):
        profil_top, cap_top = column_tops(ps)
        if profil_top is None and cap_top is None:
            continue
        cols.append({
            "z": z,
            "profil_top": round(profil_top, 1) if profil_top is not None else None,
            "cap_top": round(cap_top, 1) if cap_top is not None else None,
        })

    if not cols:
        return None
    limit = door_height - SAFETY_MARGIN_MM
    prof_vals = [c["profil_top"] for c in cols if c["profil_top"] is not None]
    cap_vals = [c["cap_top"] for c in cols if c["cap_top"] is not None]
    max_profil = max(prof_vals) if prof_vals else None
    max_cap = max(cap_vals) if cap_vals else None
    # referencni vrchol pro "fyzicky" pohled = vyssi z obou
    phys_candidates = [v for v in (max_profil, max_cap) if v is not None]
    max_phys = max(phys_candidates)

    exc_profil = round(max_profil - limit, 1) if max_profil is not None else None
    exc_phys = round(max_phys - limit, 1)
    return {
        "id": row_id,
        "name": name,
        "code": code,
        "door_height": door_height,
        "limit_with_margin": limit,
        "max_profil_top": max_profil,
        "max_phys_top": max_phys,
        "exceedance_profil": exc_profil,
        "exceedance_phys": exc_phys,
        # "violates" = prekroceni MERENE NA KONCI PROFILU, tj. proti pravidlu
        # shape_geometry_methods.id=8 tak, jak bylo skutecne aplikovano.
        "violates": (exc_profil is not None and exc_profil > 0),
        "violates_phys": exc_phys > 0,
        "columns": cols,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="vypsat vsechny radky s dostupnou hodnotou, ne jen prekrocene")
    ap.add_argument("--json", help="ulozit plny JSON report")
    a = ap.parse_args()

    load_env()
    sys.path.insert(0, "/opt/konfigurator/api")
    cwd = os.getcwd()
    os.chdir("/opt/konfigurator/api")
    import app as A  # noqa: E402

    conn = A.get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, model_id FROM car_bodies")
        body_to_model = {r["id"]: r["model_id"] for r in cur.fetchall()}
        cur.execute("SELECT id, name FROM car_models")
        model_id_to_name = {r["id"]: r["name"] for r in cur.fetchall()}
        cur.execute(
            "SELECT legacy_vendor_code, official_door_opening_height_mm FROM karoserie_model_reference "
            "WHERE official_door_opening_height_mm IS NOT NULL"
        )
        door_height_by_code = {r["legacy_vendor_code"]: r["official_door_opening_height_mm"] for r in cur.fetchall()}
        cur.execute("SELECT id, name, is_public, data FROM product_assemblies WHERE is_public=1")
        rows = cur.fetchall()
    finally:
        conn.close()
        os.chdir(cwd)

    code_re = re.compile(r"\[([A-Z]{2}\d{2})\]")
    results = []
    skipped = []
    for r in rows:
        d = json.loads(r["data"]) if isinstance(r["data"], (str, bytes)) else (r["data"] or {})
        code = None
        for p in d.get("parts") or []:
            m = re.match(r"car_body_(\d+)", p.get("part_id") or "")
            if m:
                model_id = body_to_model.get(int(m.group(1)))
                name = model_id_to_name.get(model_id, "") or ""
                cm = code_re.search(name)
                if cm:
                    code = cm.group(1)
                    break
        if not code or code not in door_height_by_code:
            skipped.append((r["id"], code))
            continue
        res = analyze_row(r["id"], r["name"], d, door_height_by_code[code], code)
        if res:
            results.append(res)

    if a.json:
        json.dump(results, open(a.json, "w"), ensure_ascii=False, indent=1)

    # porusenim je VYHRADNE presah konce profilu (Robertovo rozhodnuti vyse)
    shown = results if a.all else [r for r in results if r["violates"]]
    shown.sort(key=lambda r: -r["exceedance_phys"])
    print("%-4s %-6s %-42s %7s %7s %8s %8s %8s" % (
        "id", "kod", "nazev", "dvereH", "limit", "profilTop", "fyzTop", "presahP"))
    print("-" * 100)
    for r in shown:
        print("%-4s %-6s %-42s %7.0f %7.0f %9.0f %8.0f %8.0f" % (
            r["id"], r["code"], r["name"][:42], r["door_height"], r["limit_with_margin"],
            r["max_profil_top"] if r["max_profil_top"] is not None else -1,
            r["max_phys_top"], r["exceedance_profil"] if r["exceedance_profil"] is not None else -1))

    n_checked = len(results)
    n_prof = sum(1 for r in results if r["violates"])
    n_phys = sum(1 for r in results if r["violates_phys"])
    print("\nzkontrolovano %d radku (s ofic. vyskou dveri), preskoceno %d (bez kodu/vysky)" % (n_checked, len(skipped)))
    print("PORUSENI (konec profilu nad limitem) - rozhodujici kriterium:  %d" % n_prof)
    print("  (informativne: nad limitem vc. 3mm cela zaslepky by bylo:    %d)" % n_phys)
    if n_phys > n_prof:
        print("\nPOZN.: rozdil %d radku = 3mm konvence zaslepky nad koncem profilu." % (n_phys - n_prof))
        print("       NENI to vada - Robert 2026-09-03 rozhodl merit ke KONCI PROFILU")
        print("       (zaslepka je kosmeticka, nenosna). Viz shape_geometry_methods.id=8 v6.")


if __name__ == "__main__":
    main()
