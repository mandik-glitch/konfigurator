#!/usr/bin/env python3
"""Pridani komponentu do Vandr systemu u nas (bot10, 2026-10-05; docs/VANDR_SYSTEM.md): komponenta z DB Vandru (`components` + kusovnik `components_parts` + ceny dilu / materialu)
+ jeji 3D model z exportu sestavy (FBX -> GLB postupem automatu konverze) -> parametricky GLB v chranene slozce `webapp/katalog/vandr/komponenty/<kod>.glb` + radky v `vd_komponenty`
a `vd_komponenty_dily`. Bez --zapsat jen nahled (GLB do docasne slozky, nic se nezapise do DB ani do repa).

  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
    api/venv/bin/python3 scripts/vandr_system/pridej_komponentu.py --unity-id Kufrik.3x43.vysuv.1057.459 --kod kufrik-3x43-vysuv-d459 --kategorie vysuvy \\
    --zdroj-uuid e1dd5c1b-6c5e-4edf-b9f7-c3f7a6af4a75 --koren Kufrik3x43vysuv1057459 --delka-dil 20x40x --delka-od 300 --delka-do 1530 [--zapsat]

--zdroj-uuid = UUID exportu sestavy z Vandru, ve ktere komponenta je (nebo --zdroj-glb = uz prevedene GLB v mm); --koren = predpona jmena uzlu komponentu v GLB (podstrom bez noh).
Parametr (u 'natazeni podle roviny') = SVETLA sirka jako ve Vandru (`components.min_width` = max_width, tady 967 mm); rozsah z delky protahovaneho dilu (--delka-*)."""
import argparse
import json
import os
import shutil
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, os.path.join(REPO, "scripts", "2026-10-05_vandr_plato"))
import vandr_system as VS  # noqa: E402
import vandr_kusovnik as VK  # noqa: E402
import build_plato as BP  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unity-id", required=True)
    ap.add_argument("--kod", required=True)
    ap.add_argument("--kategorie", default=None)
    ap.add_argument("--zdroj-uuid")
    ap.add_argument("--zdroj-glb")
    ap.add_argument("--koren", required=True)
    ap.add_argument("--delka-dil", required=True)
    ap.add_argument("--delka-od", type=float, required=True)
    ap.add_argument("--delka-do", type=float, required=True)
    ap.add_argument("--zadal", default="Robert 2026-10-05")
    ap.add_argument("--zapsat", action="store_true")
    a = ap.parse_args()
    VS.kod_na_sku(a.kod)
    if not (a.zdroj_uuid or a.zdroj_glb):
        raise SystemExit("zadej --zdroj-uuid nebo --zdroj-glb")
    kus, comp = VK.nacti(a.unity_id)
    svetlost0 = float(comp["min_width"]) if comp["min_width"] is not None and comp["min_width"] == comp["max_width"] else None
    if svetlost0 is None:
        raise SystemExit("komponenta nema pevnou svetlou sirku (min_width == max_width) - parametrizaci ve Vandru nepodporuje tento import")
    scratch = tempfile.mkdtemp(prefix="vd_import_")
    try:
        src = a.zdroj_glb or BP.preved_fbx(a.zdroj_uuid, scratch)
        nazev = comp["name"]
        data, param, n = BP.sestav(open(src, "rb").read(), a.koren, 0.0, 0.0, nazev, kusovnik=kus, rozsah_delky=(a.delka_dil, a.delka_od, a.delka_do), svetlost0=svetlost0)
        w0, svet0 = param["w0"], param["svetlost0"]
        prid = round(w0 - svet0, 3)                                   # vnejsi sirka = svetla + prid (u kufriku 2 x 45 mm koncove pricky)
        smin, smax = svet0 + (param["wmin"] - w0), svet0 + (param["wmax"] - w0)
        parametrizace = {"verze": 1, "typ": "natazeni_podle_roviny", "os": param["os"], "rovina": param["rovina"], "w0_vnejsi_mm": w0,
                         "parametry": [{"id": "sirka_svetla", "nazev_cs": "Světlá šířka mezi nohami", "nazev_en": "Clear width between legs", "jednotka": "mm",
                                        "min": round(smin, 3), "max": round(smax, 3), "vychozi": svet0, "krok": 1, "vnejsi_pricist_mm": prid}],
                         "rozsah_zdroj": dict(param["rozsah"], zadal=a.zadal)}
        dily = [{"dil": r["dil"], "ks": r["ks"], "cena_ks": r["cena"], "vaha_ks_g": r["vaha"], "delka_pravidlo": r.get("delka")} for r in param["kusovnik"]["radky"]]
        reg = {"kod": a.kod, "nazev_cs": comp["name"], "nazev_en": comp["name_en"], "kategorie": a.kategorie, "typ": "parametricky", "hloubka_mm": comp["min_depth"],
               "parametrizace": parametrizace, "glb_soubor": a.kod + ".glb", "mena": kus["mena"], "cena0": kus["cena0"], "vaha0_g": kus["vaha0_g"], "cenik_snimek": kus["snimek"],
               "vandr_unity_id": a.unity_id, "vandr_component_id": comp["id"], "stav": "koncept", "dily": dily,
               "poznamka": "Import z vanDrawee (exportu sestavy %s); natazeni podle roviny, nohy nejsou soucasti komponentu." % (a.zdroj_uuid or a.zdroj_glb)}
        souhrn = {"kod": a.kod, "sku": VS.kod_na_sku(a.kod), "casti_glb": n, "glb_bytes": len(data), "svetla_sirka": [parametrizace["parametry"][0][k] for k in ("min", "vychozi", "max")],
                  "vnejsi_sirka": [param["wmin"], w0, param["wmax"]], "cena0": kus["cena0"], "dily": len(dily), "delkove_zavisle": [d["dil"] for d in dily if d["delka_pravidlo"]]}
        print(json.dumps(souhrn, ensure_ascii=False, indent=1))
        if not a.zapsat:
            print("\n(nahled, nic nezapsano; zapis: --zapsat)")
            return
        import pymysql
        os.makedirs(VS.GLB_DIR, exist_ok=True)
        cil = os.path.join(VS.GLB_DIR, a.kod + ".glb")
        with open(cil, "wb") as fh:
            fh.write(data)
        os.chmod(cil, 0o644)
        conn = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", 3306)), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                               database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
        cur = conn.cursor()
        VS.zaloz_schema(cur)
        kid = VS.zaregistruj(cur, reg)
        conn.commit()
        print("zapsano: vd_komponenty #%d, %d radku kusovniku, model %s" % (kid, len(dily), cil))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
