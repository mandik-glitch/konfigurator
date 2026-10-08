#!/usr/bin/env python3
"""KONTROLA ORIENTACE KAROSERII - jeden prikaz, jasny verdikt, porovnani pred/po.

Robert 2026-09-05: "to nemas script na porovnavani? script je nutny."

Odpovida na otazku "jsou vsechny karoserie spravnym smerem?" MERENIM ze
skutecnych GLB souboru na disku - necte zadny ulozeny seznam, ktery by mohl
byt zastaraly.

POUZITI
    python3 /opt/konfigurator/scripts/2026-09-05_kontrola_orientace.py                # kontrola + verdikt
    python3 /opt/konfigurator/scripts/2026-09-05_kontrola_orientace.py --seznam       # + vypis vsech vadnych
    python3 /opt/konfigurator/scripts/2026-09-05_kontrola_orientace.py --json         # strojove citelne
    python3 /opt/konfigurator/scripts/2026-09-05_kontrola_orientace.py --snapshot X   # uloz stav do X
    python3 /opt/konfigurator/scripts/2026-09-05_kontrola_orientace.py --porovnej X   # porovnej stav proti X

POROVNANI PRED/PO (kvuli tomuhle skript vznikl):
    # pred opravou
    python3 /opt/konfigurator/scripts/2026-09-05_kontrola_orientace.py --snapshot /tmp/pred.json
    ! bash /opt/konfigurator/scripts/2026-09-05_orientace_vse.sh
    # po oprave - ukaze presne, co se zmenilo a jestli neco necekane
    python3 /opt/konfigurator/scripts/2026-09-05_kontrola_orientace.py --porovnej /tmp/pred.json

EXIT KOD: 0 = vsechny karoserie spravne, 1 = nejaka je opacne / nezmerena,
2 = chyba skriptu. Diky tomu se da poustet i z QA nebo z CI.

KRITERIUM (KAROSERIE_UMISTENI.md, Robert: "kdyz se vlozi do sceny, musim se
divat do zadnich dveri auta"): B_midZ = stred bounding boxu prepazky "B"
v ose Z. B_midZ < -50 = OK, > +50 = OPACNE.

bot8 2026-09-05. READ-ONLY - nic nemeni, jen meri.
"""
import argparse
import json
import os
import re
import struct
import sys

# Robert 2026-09-05 narazil na "ModuleNotFoundError: No module named 'pymysql'" -
# spustil skript SYSTEMOVYM python3, jenze pymysql je jen ve venv projektu.
# Misto poznamky v navodu (tu nikdo necte, kdyz kopiruje prikaz) se skript
# radeji sam prespusti spravnym interpretem. Bez tohohle je to past, do ktere
# spadne kazdy, kdo prikaz zkopiruje.
_VENV_PY = "/opt/konfigurator/api/venv/bin/python3"
if not os.environ.get("_KONTROLA_ORIENTACE_REEXEC"):
    try:
        import pymysql  # noqa: F401
    except ModuleNotFoundError:
        # POZOR: neporovnavat sys.executable pres realpath - venv/bin/python3 je
        # symlink na systemovy interpret, takze by realpath vysel shodne a
        # prespusteni by se nikdy neprovedlo. Proti zacykleni staci promenna
        # prostredi nastavena vyse.
        if os.path.exists(_VENV_PY):
            os.environ["_KONTROLA_ORIENTACE_REEXEC"] = "1"
            os.execv(_VENV_PY, [_VENV_PY, os.path.abspath(__file__)] + sys.argv[1:])
        print("CHYBA: chybi modul pymysql a nenasel jsem venv projektu.\n"
              f"Spust skript takhle:  {_VENV_PY} {os.path.abspath(__file__)}", file=sys.stderr)
        sys.exit(2)

sys.path.insert(0, "/opt/konfigurator/api")
os.chdir("/opt/konfigurator/api")
for _l in open(".env"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
import app as A  # noqa: E402

KAT = "/opt/konfigurator/webapp/katalog/"
PRAH = 50.0
# Prepazka je u vetsiny modelu "_B.glb", u FO30 "_B_wall.glb" - obe varianty
# musi byt v seznamu, jinak by se model tise preskocil (past, ktera uz jednou
# zpusobila, ze by re-audit ohlasil uspech nad rozbitou karoserii).
B_SUFFIXY = ("_B.glb", "_B_wall.glb")
VSECHNY_SUFFIXY = ("_L.glb", "_R_D.glb", "_B.glb", "_B_wall.glb")
RE_KOD = re.compile(r"\[([A-Za-z]{2,3}\d{2,3})\]")


def zmer_b_midz(cesta):
    """Stred bounding boxu v ose Z primo z hlavicky GLB (accessors min/max)."""
    with open(cesta, "rb") as f:
        b = f.read()
    if len(b) < 12 or struct.unpack_from("<I", b, 0)[0] != 0x46546C67:
        raise ValueError("neni GLB")
    off = 12
    while off < len(b):
        ln, ty = struct.unpack_from("<II", b, off)
        if ty == 0x4E4F534A:
            j = json.loads(b[off + 8:off + 8 + ln].decode("utf8"))
            zmin = zmax = None
            for mesh in j.get("meshes", []):
                for prim in mesh.get("primitives", []):
                    ai = (prim.get("attributes") or {}).get("POSITION")
                    if ai is None:
                        continue
                    acc = j["accessors"][ai]
                    if not acc.get("min") or not acc.get("max"):
                        continue
                    zmin = acc["min"][2] if zmin is None else min(zmin, acc["min"][2])
                    zmax = acc["max"][2] if zmax is None else max(zmax, acc["max"][2])
            if zmin is None:
                raise ValueError("zadny POSITION accessor s min/max")
            return (zmin + zmax) / 2.0
        off += 8 + ln
    raise ValueError("chybi JSON chunk")


def nacti_modely():
    """Seskupi car_bodies po modelech (spolecny zaklad cesty bez _L/_R_D/_B)."""
    conn = A.get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT cb.id, cb.glb_file, cm.name AS model_name
        FROM car_bodies cb
        JOIN car_models cm ON cm.id = cb.model_id
        WHERE cb.glb_file IS NOT NULL
        ORDER BY cb.glb_file
    """)
    modely = {}
    for r in cur.fetchall():
        glb = r["glb_file"]
        suf = next((s for s in VSECHNY_SUFFIXY if glb.endswith(s)), None)
        if not suf:
            continue
        base = glb[:-len(suf)]
        m = modely.setdefault(base, {"base": base, "model": r["model_name"] or "",
                                     "ids": [], "soubory": {}})
        m["ids"].append(r["id"])
        m["soubory"][suf] = glb
    return modely


def zmer_vse():
    vysledky = []
    for base, m in sorted(nacti_modely().items()):
        kod_m = RE_KOD.search(m["model"])
        kod = kod_m.group(1) if kod_m else "?"
        bfile = next((m["soubory"][s] for s in B_SUFFIXY if s in m["soubory"]), None)
        zaznam = {"kod": kod, "base": base, "model": m["model"],
                  "ids": sorted(m["ids"]), "b_soubor": bfile,
                  "b_midz": None, "stav": None, "poznamka": None}
        if not bfile:
            zaznam["stav"] = "NEZMERENO"
            zaznam["poznamka"] = "chybi prepazka (_B.glb ani _B_wall.glb)"
        elif not os.path.exists(KAT + bfile):
            zaznam["stav"] = "NEZMERENO"
            zaznam["poznamka"] = f"soubor na disku neexistuje: {bfile}"
        else:
            try:
                mid = zmer_b_midz(KAT + bfile)
                zaznam["b_midz"] = round(mid, 1)
                zaznam["stav"] = ("OPACNE" if mid > PRAH
                                  else "OK" if mid < -PRAH else "NEJASNE")
            except Exception as e:  # poskozeny/nectitelny GLB je taky nalez
                zaznam["stav"] = "NEZMERENO"
                zaznam["poznamka"] = f"chyba cteni: {e}"
        vysledky.append(zaznam)
    return vysledky


def souhrn(v):
    s = {"celkem": len(v)}
    for st in ("OK", "OPACNE", "NEJASNE", "NEZMERENO"):
        s[st.lower()] = sum(1 for r in v if r["stav"] == st)
    s["vse_spravne"] = (s["opacne"] == 0 and s["nejasne"] == 0 and s["nezmereno"] == 0)
    return s


def main():
    ap = argparse.ArgumentParser(description="Kontrola orientace karoserii")
    ap.add_argument("--seznam", action="store_true", help="vypsat vsechny vadne modely")
    ap.add_argument("--json", action="store_true", help="vystup jako JSON")
    ap.add_argument("--snapshot", metavar="SOUBOR", help="ulozit aktualni stav do souboru")
    ap.add_argument("--porovnej", metavar="SOUBOR", help="porovnat aktualni stav proti snapshotu")
    args = ap.parse_args()

    v = zmer_vse()
    s = souhrn(v)

    if args.snapshot:
        with open(args.snapshot, "w", encoding="utf-8") as f:
            json.dump({"souhrn": s, "modely": v}, f, ensure_ascii=False, indent=1)
        print(f"Snapshot ulozen: {args.snapshot}  ({s['celkem']} modelu, "
              f"OK {s['ok']} / opacne {s['opacne']})")
        return 0 if s["vse_spravne"] else 1

    if args.porovnej:
        try:
            with open(args.porovnej, encoding="utf-8") as f:
                stary = json.load(f)
        except Exception as e:
            print(f"CHYBA: nelze precist snapshot {args.porovnej}: {e}", file=sys.stderr)
            return 2
        pred = {r["base"]: r for r in stary.get("modely", [])}
        opraveno, rozbito, beze_zmeny, nove = [], [], 0, []
        for r in v:
            p = pred.get(r["base"])
            if p is None:
                nove.append(r)
                continue
            if p["stav"] == r["stav"]:
                beze_zmeny += 1
            elif p["stav"] != "OK" and r["stav"] == "OK":
                opraveno.append((r, p))
            elif p["stav"] == "OK" and r["stav"] != "OK":
                rozbito.append((r, p))
            else:
                beze_zmeny += 1
        zmizelo = [b for b in pred if not any(r["base"] == b for r in v)]

        print(f"POROVNANI proti {args.porovnej}")
        print(f"  opraveno (bylo spatne -> ted OK): {len(opraveno)}")
        print(f"  ROZBITO  (bylo OK -> ted spatne): {len(rozbito)}")
        print(f"  beze zmeny:                       {beze_zmeny}")
        if nove:
            print(f"  nove modely (nebyly ve snapshotu): {len(nove)}")
        if zmizelo:
            print(f"  zmizele modely: {len(zmizelo)}")
        if rozbito:
            print("\n  !!! REGRESE - tyhle byly spravne a ted nejsou:")
            for r, p in rozbito[:20]:
                print(f"    {r['kod']:6} {r['base'].split('/')[-1][:44]:44} "
                      f"{p['b_midz']} -> {r['b_midz']}")
        if args.seznam and opraveno:
            print("\n  opravene:")
            for r, p in opraveno[:40]:
                print(f"    {r['kod']:6} {r['base'].split('/')[-1][:44]:44} "
                      f"{p['b_midz']} -> {r['b_midz']}")
        print()

    if args.json:
        print(json.dumps({"souhrn": s, "modely": v}, ensure_ascii=False, indent=1))
        return 0 if s["vse_spravne"] else 1

    print("KONTROLA ORIENTACE KAROSERII (mereno z GLB na disku)")
    print(f"  modelu celkem:  {s['celkem']}")
    print(f"  spravne (OK):   {s['ok']}")
    print(f"  OPACNE:         {s['opacne']}")
    if s["nejasne"]:
        print(f"  nejasne:        {s['nejasne']}")
    if s["nezmereno"]:
        print(f"  NEZMERENO:      {s['nezmereno']}")

    vadne = [r for r in v if r["stav"] != "OK"]
    if args.seznam and vadne:
        print("\n  vadne modely:")
        for r in vadne:
            pozn = f"  ({r['poznamka']})" if r["poznamka"] else ""
            print(f"    {r['kod']:6} {r['stav']:10} B_midZ={str(r['b_midz']):>9}  "
                  f"{r['model'][:52]}{pozn}")
    elif vadne:
        print(f"\n  (prvnich 10 vadnych, cely seznam pres --seznam)")
        for r in vadne[:10]:
            print(f"    {r['kod']:6} {r['stav']:10} B_midZ={str(r['b_midz']):>9}  {r['model'][:52]}")

    print()
    if s["vse_spravne"]:
        print("VERDIKT: VSECHNY KAROSERIE JSOU SPRAVNYM SMEREM.")
    else:
        print(f"VERDIKT: NE - {s['opacne'] + s['nejasne'] + s['nezmereno']} z {s['celkem']} "
              f"modelu neni v poradku.")
        print("Oprava: ! bash /opt/konfigurator/scripts/2026-09-05_orientace_vse.sh")
    return 0 if s["vse_spravne"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"CHYBA SKRIPTU: {e}", file=sys.stderr)
        sys.exit(2)
