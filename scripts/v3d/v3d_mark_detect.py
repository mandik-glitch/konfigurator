#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3d_mark_detect.py - které nabidce patri unikly 3D model (bot10, 2026-10-02).

Cte neviditelnou forenzni znacku z api/v3d_mark.py (schema v1) z GLB / OBJ / STL
a vypise cislo nabidky (scene_offers.id) + jistotu + radek nabidky z DB.
NIC NEZAPISUJE (DB jen SELECT pres READ ONLY spojeni z build_ctx.konf_conn_ro()).

Pouziti (server):
  api/venv/bin/python3 scripts/v3d/v3d_mark_detect.py SOUBOR.glb
  api/venv/bin/python3 scripts/v3d/v3d_mark_detect.py SOUBOR.obj --original karta_bez_znacky.glb
Volby:
  --original ORIG.glb   NEMARKOVANY model teze karty (vyrobi ho
                        `api/venv/bin/python3 scripts/v3d/offer_model.py <shop_product_id> -o orig.glb`);
                        umozni cist znacku i po POSUNU / libovolnem OTOCENI / zmene MERITKA modelu
                        (bez nej se cte jen v soustave souboru, vc. jednotek a otoceni o 90 st.)
  --ids 12,15,20        kandidati (id nabidek) misto DB; --ids-file soubor (jedno cislo na radek)
  --no-db               nesahat na DB (ani na kandidaty, ani na radek nabidky)
  --secret-hex HEX      klic z prikazove radky (testy); jinak V3D_MARK_SECRET, jinak odvozeny
                        z FLASK_SECRET_KEY - z prostredi nebo z api/.env (hodnota se nikdy nevypisuje)
  --json                vystup jako JSON
Kandidati (id vsech scene_offers z DB) se pouziji JEN kdyz kod nejde potvrdit kontrolnim
HMAC (hodne poskozeny model); platny kod se cte bez nich.
Navratove kody: 0 znacka nalezena, 1 nenalezena, 2 chyba vstupu/pouziti.
Pozn.: tenhle skript je jen CLI nad v3d_mark.detect_points; zadny kod z nej nevola API.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KOREN = os.path.dirname(os.path.dirname(HERE))
KONF_REPO = os.environ.get("KONFIGURATOR_REPO") or "/opt/konfigurator"
sys.dont_write_bytecode = True
for _d in (os.path.join(KOREN, "api"), os.path.join(KONF_REPO, "api"), HERE):
    if os.path.isdir(_d) and _d not in sys.path:
        sys.path.insert(0, _d)

import v3d_mark  # noqa: E402

OFFER_COLS = ("id", "offer_number", "customer_name", "created_at", "expires_at", "is_active", "view_3d_model",
              "drive_model_file_id")


def _cti_env(cesta):
    vals = {}
    try:
        with open(cesta, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                if k in ("V3D_MARK_SECRET", "FLASK_SECRET_KEY"):
                    vals[k] = v.strip().strip('"').strip("'")
    except OSError:
        return {}
    return vals


def nacti_secret(secret_hex=None, env=None, env_path=None):
    """--secret-hex > prostredi (V3D_MARK_SECRET, FLASK_SECRET_KEY) > api/.env. Hodnotu nikdy nevypisuje."""
    if secret_hex:
        return bytes.fromhex(secret_hex)
    env = os.environ if env is None else env
    src = {k: env.get(k) for k in ("V3D_MARK_SECRET", "FLASK_SECRET_KEY") if env.get(k)}
    if not src:
        src = _cti_env(env_path or os.path.join(KONF_REPO, "api", ".env"))
    return v3d_mark.get_secret({"V3D_MARK_SECRET": src.get("V3D_MARK_SECRET", "")}, src.get("FLASK_SECRET_KEY"))


def nacti_body(cesta):
    with open(cesta, "rb") as f:
        data = f.read()
    low = cesta.lower()
    if low.endswith(".obj"):
        return v3d_mark.points_from_obj(data)
    if low.endswith(".stl"):
        return v3d_mark.points_from_stl(data)
    if data[:4] == b"glTF":
        return v3d_mark.world_points(data)
    raise ValueError("neznamy format (cekam .glb, .obj nebo binarni .stl)")


def db_kandidati(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM scene_offers ORDER BY id")
        return [int(r["id"]) for r in cur.fetchall()]


def db_nabidka(conn, offer_id):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM scene_offers WHERE id=%s", (offer_id,))
        r = cur.fetchone()
    if not r:
        return None
    return {k: (str(r[k]) if k in ("created_at", "expires_at") and r[k] is not None else r[k])
            for k in OFFER_COLS if k in r}


def _db_factory():
    import build_ctx
    return build_ctx.konf_conn_ro()


def hlavni(argv, conn_factory=None, out=None):
    out = out or sys.stdout
    ap = argparse.ArgumentParser(description="Ktere nabidce patri unikly 3D model (forenzni znacka v3d_mark)")
    ap.add_argument("soubor")
    ap.add_argument("--original")
    ap.add_argument("--ids")
    ap.add_argument("--ids-file")
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--secret-hex")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        secret = nacti_secret(a.secret_hex)
        P = nacti_body(a.soubor)
        Po = nacti_body(a.original) if a.original else None
    except (OSError, ValueError) as e:
        print("CHYBA: %s" % e, file=sys.stderr)
        return 2
    ids = None
    if a.ids:
        ids = [int(x) for x in a.ids.split(",") if x.strip()]
    elif a.ids_file:
        with open(a.ids_file) as f:
            ids = [int(x) for x in f.read().split() if x.strip()]

    res = v3d_mark.detect_points(P, secret, None, Po)
    conn = None
    factory = conn_factory or _db_factory
    try:
        if not a.no_db and ids is None and res["offer_id"] is None:
            conn = factory()
            ids = db_kandidati(conn)
        if res["offer_id"] is None and ids:
            res = v3d_mark.detect_points(P, secret, ids, Po)
        nabidka = None
        if res["offer_id"] is not None and not a.no_db:
            conn = conn or factory()
            nabidka = db_nabidka(conn, res["offer_id"])
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:                                   # noqa: BLE001
                pass
    vysl = {"nalezeno": res["offer_id"] is not None, "offer_id": res["offer_id"],
            "jistota": res["jistota"] if res["offer_id"] is not None else 0.0,
            "p_false": res.get("p_false"), "rezim": res.get("rezim"), "soustava": res.get("soustava"),
            "registrace": res.get("registrace"), "bunek": res.get("cells"), "nabidka": nabidka,
            "kandidat": res.get("kandidat"), "kandidatu": len(ids) if ids else 0}
    if a.json:
        print(json.dumps(vysl, ensure_ascii=False, indent=1, default=str), file=out)
    elif vysl["nalezeno"]:
        print("ZNACKA NALEZENA: nabidka id=%d  jistota %.12f  (%s, %d bunek)" % (
            vysl["offer_id"], vysl["jistota"], vysl["rezim"], vysl["bunek"] or 0), file=out)
        if nabidka:
            print("  cislo nabidky %s, zakaznik %s, vytvoreno %s, platnost do %s, aktivni %s, soubor modelu %s" % (
                nabidka.get("offer_number"), nabidka.get("customer_name"), nabidka.get("created_at"),
                nabidka.get("expires_at"), nabidka.get("is_active"), nabidka.get("view_3d_model")), file=out)
        elif not a.no_db:
            print("  (nabidka s timto id v DB neni - smazana, nebo jine prostredi)", file=out)
    else:
        print("ZNACKA NENALEZENA (%s bunek, kandidatu %d%s). Zkus --original (nemarkovany model teze karty)." % (
            vysl["bunek"], vysl["kandidatu"], ", registrace: %s" % res["registrace"] if res.get("registrace") else ""),
            file=out)
    return 0 if vysl["nalezeno"] else 1


if __name__ == "__main__":
    sys.exit(hlavni(sys.argv[1:]))
