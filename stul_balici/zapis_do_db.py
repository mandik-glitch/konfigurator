#!/usr/bin/env python3
"""Zápis sestavy "Stůl balení LIDL (prototyp II)" do DB jako Vlastní tvar (řádek `custom_shapes`) - NESPOUŠTĚNO v cloudu (tam DB není).

Pro bota s přístupem k DB (viz README.md). VÝCHOZÍ REŽIM JE DRY-RUN: nic se nezapíše, vypíše se jen, co by se stalo, a zkontrolují se
vstupy proti živé DB (existence karet part_id, duplicitní jméno, schéma). Zápis jen s `--apply` a jen na výslovný pokyn.

Co skript dělá (read-only část):
  1. načte vystup/custom_shape_data.json (jen díly s kartou v katalogu), nebo s `--zastupny-kvadr <part_id>` vystup/custom_shape_data_se_zastupnymi.json
     (zástupné díly = jednotkový kvádr katalogu `kvadr_plny_1x1x1.glb`; part_id jeho karty se zjistí dotazem níže a zadá se na příkazové řádce),
  2. zkontroluje tytéž věci jako `_validate_custom_shape_parts()` v api/app.py (číselná pole, role <= 120 znaků, unikátní role, rozsah lic_peers, limit dílů),
  3. dotáže se DB (jen SELECT): které part_id v `cfg_dily` neexistují / nemají GLB, kandidáti na kartu zástupného kvádru, zda už neexistuje tvar stejného jména,
  4. u `--apply`: jedna transakce `INSERT INTO custom_shapes (name, category_id, data, created_by, is_public)`, po zápisu zpětné přečtení a kontrola počtu dílů.

Spuštění (příklady; přístupové údaje z api/.env, klíč je DB_PASSWORD - ne DB_PASS):
  api/venv/bin/python3 stul_balici/zapis_do_db.py                       # dry-run
  api/venv/bin/python3 stul_balici/zapis_do_db.py --zastupny-kvadr product_NNNN   # dry-run i se zástupnými díly
  api/venv/bin/python3 stul_balici/zapis_do_db.py --apply [--category-id N] [--zastupny-kvadr product_NNNN]   # JEN na výslovný pokyn
Skript nepíše žádné soubory (pravidlo WORKFLOW 47 o spouštění jako www-data se ho netýká). Nezapisuje do `product_assemblies` (WORKFLOW 23: zkoumané
sestavy se neukládají jako produktové), jen do `custom_shapes`, a pouze s --apply.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VYSTUP = os.path.join(HERE, "vystup")
CUSTOM_SHAPE_MAX_PARTS = 1000          # api/app.py
NAZEV_VYCHOZI = "Stůl balení LIDL - prototyp II (z výkresu)"
KVADR_GLB = "kvadr_plny_1x1x1.glb"
PLACEHOLDER = "__KVADR_1x1x1__"


def nacti_env(cesta):
    env = {}
    with open(cesta, encoding="utf-8") as f:
        for radek in f:
            radek = radek.strip()
            if not radek or radek.startswith("#") or "=" not in radek:
                continue
            k, v = radek.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def over_schema(parts):
    """Stejné kontroly jako api/app.py::_validate_custom_shape_parts + _najdi_duplicitni_role + relace (bez katalogu)."""
    chyby = []
    if not isinstance(parts, list) or not parts:
        return ["prázdný seznam dílů"]
    if len(parts) > CUSTOM_SHAPE_MAX_PARTS:
        chyby.append(f"víc než {CUSTOM_SHAPE_MAX_PARTS} dílů ({len(parts)})")
    role = {}
    for i, p in enumerate(parts):
        for klic, delka in (("position", 3), ("quaternion", 4), ("scale", 3)):
            v = p.get(klic)
            if not (isinstance(v, list) and len(v) == delka and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)):
                chyby.append(f"díl {i}: neplatné pole {klic}")
        r = p.get("role")
        if not (isinstance(r, str) and r and len(r) <= 120):
            chyby.append(f"díl {i}: chybí/neplatná role")
        else:
            role[r] = role.get(r, 0) + 1
        c = p.get("color")
        if c is not None and not re.match(r"^#[0-9a-fA-F]{6}$", str(c)):
            chyby.append(f"díl {i}: neplatná barva {c}")
        for j in p.get("lic_peers", []) or []:
            if not (isinstance(j, int) and 0 <= j < len(parts) and j != i):
                chyby.append(f"díl {i}: lic_peers odkazuje na neplatný index {j}")
            elif i not in (parts[j].get("lic_peers") or []):
                chyby.append(f"díl {i}: lic_peers nesymetrické vůči {j}")
        for j in p.get("used_conn", []) or []:
            if not isinstance(j, int) or j < 0:
                chyby.append(f"díl {i}: neplatný used_conn")
    for r, n in role.items():
        if n > 1:
            chyby.append(f"duplicitní role {r} ({n}x)")
    return chyby


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="skutečně zapsat (výchozí je dry-run)")
    ap.add_argument("--name", default=NAZEV_VYCHOZI, help="název vlastního tvaru")
    ap.add_argument("--category-id", type=int, default=None, help="custom_shape_categories.id (výchozí: bez kategorie = Nezařazené)")
    ap.add_argument("--created-by", type=int, default=None, help="users.id autora (výchozí NULL)")
    ap.add_argument("--zastupny-kvadr", default=None, help="part_id karty s kvadr_plny_1x1x1.glb; zahrne zástupné díly (válečky, kování, rameno monitoru...)")
    ap.add_argument("--env", default=os.path.join(ROOT, "api", ".env"))
    args = ap.parse_args()

    soubor = "custom_shape_data_se_zastupnymi.json" if args.zastupny_kvadr else "custom_shape_data.json"
    with open(os.path.join(VYSTUP, soubor), encoding="utf-8") as f:
        data = json.load(f)
    parts = data["parts"]
    if args.zastupny_kvadr:
        n = 0
        for p in parts:
            if p["part_id"] == PLACEHOLDER:
                p["part_id"] = args.zastupny_kvadr
                n += 1
        print(f"zástupné díly: {n} (part_id {PLACEHOLDER} -> {args.zastupny_kvadr})")
    elif any(p["part_id"] == PLACEHOLDER for p in parts):
        print("CHYBA: v datech zůstal zástupný part_id", file=sys.stderr)
        return 2
    data = {"parts": parts, "join_groups": data.get("join_groups", []), "frame_groups": data.get("frame_groups", [])}

    chyby = over_schema(parts)
    print(f"dílů: {len(parts)}; lokální kontrola schématu: {'OK' if not chyby else str(len(chyby)) + ' chyb'}")
    for c in chyby:
        print("  CHYBA", c)
    if chyby:
        return 2
    ids = sorted({p["part_id"] for p in parts})
    print("použité part_id:", ", ".join(ids))

    try:
        import pymysql
    except ImportError:
        print("CHYBA: chybí PyMySQL - spusť přes api/venv/bin/python3", file=sys.stderr)
        return 2
    env = nacti_env(args.env)
    conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)), user=env["DB_USER"], password=env["DB_PASSWORD"],
                           database=env["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            # Karty dílů: part_id `product_<N>` = řádek shop_products (id=N); ostatní (např. Object_11) = cfg_dily (api/app.py: product_ → shop_products)
            ids_prod = [i for i in ids if i.startswith("product_")]
            ids_cfg = [i for i in ids if not i.startswith("product_")]
            nalez = {}
            if ids_cfg:
                fmt = ",".join(["%s"] * len(ids_cfg))
                cur.execute(f"SELECT id, name, glb_file FROM cfg_dily WHERE id IN ({fmt})", ids_cfg)
                nalez.update({r["id"]: dict(r, zdroj="cfg_dily") for r in cur.fetchall()})
            if ids_prod:
                nums = [int(i[len("product_"):]) for i in ids_prod]
                fmt = ",".join(["%s"] * len(nums))
                cur.execute(f"SELECT id, glb_file FROM shop_products WHERE id IN ({fmt})", nums)
                nalez.update({f"product_{r['id']}": dict(r, name="", zdroj="shop_products") for r in cur.fetchall()})
            problem = False
            for pid in ids:
                r = nalez.get(pid)
                if not r:
                    print(f"  CHYBÍ karta ({'shop_products' if pid.startswith('product_') else 'cfg_dily'}): {pid}")
                    problem = True
                elif not r["glb_file"]:
                    print(f"  {pid}: karta nemá glb_file")
                    problem = True
                else:
                    print(f"  OK {pid}: {r['glb_file']} [{r['zdroj']}] {r.get('name') or ''}")
            cur.execute("SELECT id, name, glb_file FROM cfg_dily WHERE glb_file=%s", (KVADR_GLB,))
            kvadr = cur.fetchall()
            print(f"kandidáti na kartu zástupného kvádru ({KVADR_GLB}):", [(k['id'], k['name']) for k in kvadr] or "žádný - zástupné díly zatím nejdou vložit")
            cur.execute("SELECT id FROM custom_shapes WHERE name=%s", (args.name,))
            existuje = cur.fetchall()
            if existuje:
                print(f"  tvar '{args.name}' už existuje: id {[r['id'] for r in existuje]} - nic se nepřepisuje")
                problem = True
            cur.execute("SHOW COLUMNS FROM custom_shapes")
            sloupce = {r["Field"] for r in cur.fetchall()}
            for s in ("name", "category_id", "data", "created_by", "is_public"):
                if s not in sloupce:
                    print(f"  CHYBA: custom_shapes nemá sloupec {s}")
                    problem = True
            if args.category_id is not None:
                cur.execute("SELECT id FROM custom_shape_categories WHERE id=%s", (args.category_id,))
                if not cur.fetchone():
                    print(f"  CHYBA: kategorie {args.category_id} neexistuje")
                    problem = True
        if not args.apply:
            print("\nDRY-RUN: nic nezapsáno. K zápisu přidej --apply (jen na výslovný pokyn).")
            return 1 if problem else 0
        if problem:
            print("\nZápis zastaven kvůli problémům výše.")
            return 1
        payload = json.dumps(data, ensure_ascii=False)
        with conn.cursor() as cur:
            cur.execute("INSERT INTO custom_shapes (name, category_id, data, created_by, is_public) VALUES (%s, %s, %s, %s, %s)",
                        (args.name, args.category_id, payload, args.created_by, 1))
            novy = cur.lastrowid
            cur.execute("SELECT data FROM custom_shapes WHERE id=%s", (novy,))
            zpet = json.loads(cur.fetchone()["data"])
            if len(zpet["parts"]) != len(parts):
                conn.rollback()
                print("CHYBA: po zápisu nesedí počet dílů, zápis vrácen")
                return 1
        conn.commit()
        print(f"\nZAPSÁNO: custom_shapes.id = {novy} ({len(parts)} dílů)")
        print(f"Kontrolní scéna: https://autovestavby.logiman.cz/api/kontrola-scena?items=cs:{novy}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
