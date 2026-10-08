#!/usr/bin/env python3
"""VYPIS KAROSERII PODLE VYSKY ZADNIHO OTVORU (zadnich dveri).

Robert 2026-09-05: "vypis karoserie kde je zadni otvor do 1300mm".

Zdroj: karoserie_model_reference.official_door_opening_height_mm - OFICIALNI
kota vysky zadniho otvoru z dealerskych/vyrobcovych podkladu (ne mereni z GLB).
Konvence zavedena driv v projektu: vzdy ZADNI dvere (dvoukridle/vyklopne),
nikdy bocni posuvne - u bocnich je samostatny sloupec
official_side_door_height_mm.

POUZITI
    python3 /opt/konfigurator/scripts/2026-09-05_karoserie_podle_otvoru.py
    python3 /opt/konfigurator/scripts/2026-09-05_karoserie_podle_otvoru.py --max 1300
    python3 /opt/konfigurator/scripts/2026-09-05_karoserie_podle_otvoru.py --max 1300 --min 1100
    python3 /opt/konfigurator/scripts/2026-09-05_karoserie_podle_otvoru.py --max 1300 --jen-v-katalogu
    python3 /opt/konfigurator/scripts/2026-09-05_karoserie_podle_otvoru.py --max 1300 --csv > /tmp/x.csv
    python3 /opt/konfigurator/scripts/2026-09-05_karoserie_podle_otvoru.py --bez-hodnoty

Sloupec "katalog" rika, jestli model existuje jako karoserie ve scene
(car_bodies s GLB), "sestava" jestli na nem stoji nejaky eurobox regal.
Model bez hodnoty NENI totez co model nad prahem - proto se pocty vypisuji
zvlast a jde je vylistovat pres --bez-hodnoty.

bot8 2026-09-05. READ-ONLY.
"""
import argparse
import json
import os
import re
import sys

# Skript se sam prespusti venv interpretem (pymysql neni v systemovem python3) -
# stejny duvod i stejna past jako u 2026-09-05_kontrola_orientace.py:
# NEporovnavat sys.executable pres realpath, venv/bin/python3 je symlink na
# systemovy interpret a porovnani by vyslo shodne.
_VENV_PY = "/opt/konfigurator/api/venv/bin/python3"
if not os.environ.get("_KAROSERIE_OTVOR_REEXEC"):
    try:
        import pymysql  # noqa: F401
    except ModuleNotFoundError:
        if os.path.exists(_VENV_PY):
            os.environ["_KAROSERIE_OTVOR_REEXEC"] = "1"
            os.execv(_VENV_PY, [_VENV_PY, os.path.abspath(__file__)] + sys.argv[1:])
        print(f"CHYBA: chybi pymysql.\nSpust:  {_VENV_PY} {os.path.abspath(__file__)}",
              file=sys.stderr)
        sys.exit(2)

sys.path.insert(0, "/opt/konfigurator/api")
os.chdir("/opt/konfigurator/api")
for _l in open(".env"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
import app as A  # noqa: E402

RE_KOD = re.compile(r"\[([A-Za-z]{2,3}\d{2,3})\]")


def nacti():
    """Vrati {legacy_vendor_code: {...}} spojenim reference + katalogu + sestav."""
    conn = A.get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT legacy_vendor_code, real_name, manufacturer, model_range,
               official_door_opening_height_mm AS vyska,
               official_door_opening_source AS zdroj,
               cargo_length_mm, overall_height_mm
        FROM karoserie_model_reference
    """)
    ref = {r["legacy_vendor_code"]: dict(r) for r in cur.fetchall()}

    # kod -> car_body id (z nazvu modelu, kde je kod v hranatych zavorkach)
    cur.execute("""
        SELECT cb.id, cm.name AS model_name
        FROM car_bodies cb JOIN car_models cm ON cm.id = cb.model_id
        WHERE cb.glb_file IS NOT NULL
    """)
    kod_na_cb = {}
    for r in cur.fetchall():
        m = RE_KOD.search(r["model_name"] or "")
        if m:
            kod_na_cb.setdefault(m.group(1), []).append(r["id"])

    # car_body id -> sestavy
    cur.execute("SELECT id, name, data FROM product_assemblies")
    cb_na_sestavy = {}
    for r in cur.fetchall():
        try:
            d = json.loads(r["data"])
        except Exception:
            continue
        for p in d.get("parts", []):
            pid = str(p.get("part_id", ""))
            if pid.startswith("car_body_"):
                try:
                    cb_na_sestavy.setdefault(int(pid[len("car_body_"):]), set()).add(r["id"])
                except ValueError:
                    pass

    for kod, d in ref.items():
        cb_ids = kod_na_cb.get(kod, [])
        d["v_katalogu"] = bool(cb_ids)
        sest = set()
        for cid in cb_ids:
            sest |= cb_na_sestavy.get(cid, set())
        d["sestavy"] = sorted(sest)
    return ref


def main():
    ap = argparse.ArgumentParser(description="Karoserie podle vysky zadniho otvoru")
    ap.add_argument("--max", type=int, default=1300, help="horni mez v mm vcetne (vychozi 1300)")
    ap.add_argument("--min", type=int, default=None, help="dolni mez v mm vcetne")
    ap.add_argument("--jen-v-katalogu", action="store_true",
                    help="jen modely, ktere jsou jako karoserie ve scene")
    ap.add_argument("--bez-hodnoty", action="store_true",
                    help="misto vypisu ukaz modely BEZ vyplnene kotý")
    ap.add_argument("--csv", action="store_true", help="vystup jako CSV")
    args = ap.parse_args()

    ref = nacti()

    if args.bez_hodnoty:
        chybi = sorted((k, d) for k, d in ref.items() if d["vyska"] is None)
        print(f"Modely BEZ vyplnene vysky zadniho otvoru: {len(chybi)} z {len(ref)}")
        print(f"{'kod':7} {'kat':4} {'nazev':58}")
        print("-" * 72)
        for kod, d in chybi:
            print(f"{kod:7} {'ano' if d['v_katalogu'] else '-':4} {(d['real_name'] or '')[:58]}")
        return 0

    vyber = [(k, d) for k, d in ref.items()
             if d["vyska"] is not None
             and d["vyska"] <= args.max
             and (args.min is None or d["vyska"] >= args.min)
             and (d["v_katalogu"] or not args.jen_v_katalogu)]
    vyber.sort(key=lambda kd: (kd[1]["vyska"], kd[0]))

    if args.csv:
        print("legacy_vendor_code;vyska_zadniho_otvoru_mm;nazev;v_katalogu;sestavy;zdroj")
        for kod, d in vyber:
            print(f"{kod};{d['vyska']};{(d['real_name'] or '').replace(';', ',')};"
                  f"{'ano' if d['v_katalogu'] else 'ne'};"
                  f"{'/'.join(map(str, d['sestavy']))};{(d['zdroj'] or '').replace(';', ',')}")
        return 0

    rozsah = f"do {args.max} mm" if args.min is None else f"{args.min}-{args.max} mm"
    print(f"KAROSERIE SE ZADNIM OTVOREM {rozsah.upper()}")
    if args.jen_v_katalogu:
        print("  (jen modely, ktere jsou jako karoserie ve scene)")
    print()
    print(f"{'kod':6} {'vyska':>6}  {'kat':4} {'sestavy':10} {'nazev':52}")
    print("-" * 84)
    for kod, d in vyber:
        s = "/".join(map(str, d["sestavy"])) if d["sestavy"] else "-"
        print(f"{kod:6} {d['vyska']:>5} mm  {'ano' if d['v_katalogu'] else '-':4} "
              f"{s[:10]:10} {(d['real_name'] or '')[:52]}")

    s_all = len(ref)
    s_val = sum(1 for d in ref.values() if d["vyska"] is not None)
    v_kat = sum(1 for _, d in vyber if d["v_katalogu"])
    print()
    print(f"NALEZENO: {len(vyber)} modelu se zadnim otvorem {rozsah}"
          f" (z toho {v_kat} je jako karoserie ve scene)")
    print(f"  celkem v referenci: {s_all} modelu, vyska vyplnena u {s_val}, "
          f"chybi u {s_all - s_val}")
    if s_all - s_val:
        print(f"  POZOR: {s_all - s_val} modelu nema kotu vyplnenou - NEJSOU v tomhle vypisu,"
              f" ale nemusi byt nad prahem. Seznam: --bez-hodnoty")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"CHYBA SKRIPTU: {e}", file=sys.stderr)
        sys.exit(2)
