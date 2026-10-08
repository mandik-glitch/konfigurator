#!/usr/bin/env python3
"""Test ukladani TYPU SESTAVY pri vytvoreni produktove sestavy (bot8, 2026-10-02).

Bot3/bot10: pilotni stul musi jit jako produktova sestava typu STUL_SKLAD. Zjisteno:
POST /api/product-assemblies typ vubec nezapisoval (sestava_typ_id NULL u kazde nove
sestavy ze sceny). Oprava: telo `sestava_typ` (kod, vychozi AUTO) + GET /api/product-
assemblies/typy pro vyber ve scene.

SKUTECNY handler (api/product_assemblies.py) nad DOCASNYMI tabulkami - nic se nezapise
do ostrych dat (Robert: zadna testovaci data v produkci):
  * shop_products, product_assemblies, audit_log jsou v TOMTO spojeni zastinene TEMPORARY
    kopiemi (LIKE); ostatni tabulky se jen CTOU (katalog, sestava_typ, app_users);
  * vsechny get_conn() (app i product_assemblies) vraci PRESNE toto spojeni bez ping/
    reconnect - kdyby spojeni umrelo, test spadne, nikdy se nepripoji znovu k ostrym tabulkam;
  * zrcadli_sestavu_na_disk (zapisuje soubor na Sdileny disk) je nahrazeno stubem;
  * PRED volanim se overi, ze zastineni plati (COUNT(*) docasne tabulky = 0, ostre > 0);
  * po testu DROP TEMPORARY TABLE a porovnani poctu radku ostrych tabulek.

Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\
    --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-02_sestava_typ_testy/test_ulozeni_typu.py
Vystup "N kontrol OK", exit 0; jinak radky CHYBA, exit 1.
"""
import json
import os
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.environ.get("PA_API_OVERRIDE") or os.path.join(REPO, "api")
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi - spust pres systemd-run --property=EnvironmentFile=api/.env (viz hlavicka)")
    sys.exit(2)

import pymysql  # noqa: E402

_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, API)
sys.path.insert(0, os.path.join(REPO, "scripts"))
try:
    import app as appmod  # noqa: E402
    import product_assemblies as pa  # noqa: E402
finally:
    threading.Thread.start = _orig

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")


SHADOW = ("shop_products", "product_assemblies", "audit_log")


def raw_counts():
    c = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                        database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4",
                        cursorclass=pymysql.cursors.DictCursor)
    try:
        with c.cursor() as cur:
            out = {}
            for t in SHADOW + ("shared_drive_files",):
                cur.execute(f"SELECT COUNT(*) n, COALESCE(MAX(id), 0) mx FROM {t}")
                r = cur.fetchone()
                out[t] = (int(r["n"]), int(r["mx"]))
            return out
    finally:
        c.close()


def main():
    before = raw_counts()
    real = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                           database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4",
                           cursorclass=pymysql.cursors.DictCursor)
    cur = real.cursor()
    # --- vstupni data (jen cteni) ---
    cur.execute("SELECT id, kod FROM sestava_typ WHERE aktivni=1")
    typy = {r["kod"]: r["id"] for r in cur.fetchall()}
    check({"AUTO", "STUL_SKLAD"} <= set(typy), f"v sestava_typ jsou aktivni AUTO i STUL_SKLAD ({sorted(typy)})")
    cur.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
    admin_id = cur.fetchone()["id"]
    cur.execute("SELECT data FROM custom_shapes WHERE id=577")
    row = cur.fetchone()
    stul = json.loads(row["data"]) if row else None
    cur.execute("SELECT data FROM product_assemblies WHERE id=128")
    vzor = json.loads(cur.fetchone()["data"])
    parts = (stul or vzor)["parts"]
    payload_base = {
        "name": "TEST sestava typ (docasna tabulka)", "category_id": None,
        "parts": parts, "join_groups": (stul or vzor).get("join_groups") or [],
        "frame_groups": (stul or vzor).get("frame_groups") or [],
        "bom": vzor["bom"], "price_summary": vzor["price_summary"],
    }

    # katalog dilu predem (ostre cteni): jeho SQL odkazuje na shop_products 2x v jednom dotazu, coz MySQL u
    # docasne tabulky nepovoli (1137) - handler dostane hotovy snimek
    katalog_snimek = appmod.fetch_katalog_parts()

    # --- stineni: docasne kopie, jedno pevne spojeni ---
    for t in SHADOW:
        # "CREATE TEMPORARY TABLE x LIKE x" MySQL nepovoli (1066) - pres pomocnou docasnou sablonu
        cur.execute(f"CREATE TEMPORARY TABLE _tpl_{t} LIKE {t}")
        cur.execute(f"CREATE TEMPORARY TABLE {t} LIKE _tpl_{t}")
        cur.execute(f"DROP TEMPORARY TABLE _tpl_{t}")
    pooled = appmod._PooledConn(real)
    appmod.get_conn = lambda: pooled
    pa.get_conn = lambda: pooled
    for modname in ("kolize_priznak", "products", "orders", "cart"):
        m = sys.modules.get(modname)
        if m is not None and hasattr(m, "get_conn"):
            m.get_conn = lambda: pooled
    pa.fetch_katalog_parts = lambda: katalog_snimek
    zrcadleno = []
    pa.zrcadli_sestavu_na_disk = lambda *a, **k: zrcadleno.append(a[1] if len(a) > 1 else None)
    try:
        # zastineni plati? (ostre tabulky maji radky, docasne ne)
        for t in SHADOW:
            cur.execute(f"SELECT COUNT(*) n FROM {t}")
            n_docasna = cur.fetchone()["n"]
            check(n_docasna == 0, f"{t}: zastineno prazdnou docasnou tabulkou (je {n_docasna})")
            if n_docasna != 0:
                raise SystemExit("CHYBA: zastineni neplati - KONEC, nic se nevolalo")
        client = appmod.app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = admin_id

        # 1) STUL_SKLAD
        r = client.post("/api/product-assemblies", json=dict(payload_base, sestava_typ="STUL_SKLAD"))
        d = r.get_json() or {}
        check(r.status_code == 200 and d.get("status") == "ok", f"POST s typem STUL_SKLAD -> 200 ok (je {r.status_code} {d})")
        check(d.get("sestava_typ") == "STUL_SKLAD", f"odpoved nese sestava_typ STUL_SKLAD ({d.get('sestava_typ')})")
        cur.execute("SELECT sestava_typ_id, is_public, shop_product_id FROM product_assemblies WHERE id=%s", (d.get("id"),))
        row = cur.fetchone() or {}
        check(row.get("sestava_typ_id") == typy["STUL_SKLAD"], f"v DB sestava_typ_id = id STUL_SKLAD ({row})")
        check(row.get("is_public") == 1, "admin: is_public = 1 (technicky_ok/live_3d zustavaji NULL/0 - jen Robert)")
        cur.execute("SELECT technicky_ok, live_3d FROM product_assemblies WHERE id=%s", (d.get("id"),))
        row2 = cur.fetchone() or {}
        check(not row2.get("technicky_ok") and not row2.get("live_3d"), f"technicky_ok/live_3d se nenastavuji ({row2})")
        cur.execute("SELECT detail FROM audit_log ORDER BY id DESC LIMIT 1")
        check("STUL_SKLAD" in str((cur.fetchone() or {}).get("detail")), "audit_log zaznam nese typ")

        # 2) bez typu -> vychozi AUTO
        p2 = dict(payload_base)
        p2["name"] = "TEST sestava bez typu"
        r = client.post("/api/product-assemblies", json=p2)
        d2 = r.get_json() or {}
        cur.execute("SELECT sestava_typ_id FROM product_assemblies WHERE id=%s", (d2.get("id"),))
        check(r.status_code == 200 and (cur.fetchone() or {}).get("sestava_typ_id") == typy["AUTO"],
              f"bez `sestava_typ` plati vychozi AUTO (stavajicich 530 sestav = AUTO) ({r.status_code})")
        check(d2.get("sestava_typ") == "AUTO", "odpoved: sestava_typ AUTO")

        # 3) neznamy typ -> 400, nic se nevlozi
        cur.execute("SELECT COUNT(*) n FROM product_assemblies")
        n_pred = cur.fetchone()["n"]
        p3 = dict(payload_base, sestava_typ="NEEXISTUJE", name="TEST neznamy typ")
        r = client.post("/api/product-assemblies", json=p3)
        cur.execute("SELECT COUNT(*) n FROM product_assemblies")
        check(r.status_code == 400 and "typ sestavy" in str((r.get_json() or {}).get("error")),
              f"neznamy typ -> 400 s hlaskou ({r.status_code} {(r.get_json() or {}).get('error')})")
        check(cur.fetchone()["n"] == n_pred, "neznamy typ: zadna sestava ani navrh karty se nevlozi")
        cur.execute("SELECT COUNT(*) n FROM shop_products")
        check(cur.fetchone()["n"] == 2, "docasne shop_products: jen 2 navrhy karet z prvnich dvou ukladani")

        # 4) seznam typu pro scenu
        r = client.get("/api/product-assemblies/typy")
        dt = r.get_json() or {}
        kody = [t["kod"] for t in dt.get("typy", [])]
        check(r.status_code == 200 and "AUTO" in kody and "STUL_SKLAD" in kody and dt.get("vychozi") == "AUTO",
              f"GET /typy: AUTO + STUL_SKLAD, vychozi AUTO ({r.status_code} {dt})")
        # 5) bez prihlaseni
        anon = appmod.app.test_client()
        r = anon.get("/api/product-assemblies/typy")
        check(r.status_code in (401, 403), f"GET /typy bez prihlaseni odmitnuto ({r.status_code})")
        # 6) hledani typu filtruje jen aktivni
        sql = []

        class FakeCur:
            def execute(self, q, a=None):
                sql.append(q)

            def fetchone(self):
                return None
        check(pa._sestava_typ_podle_kodu(FakeCur(), "X") is None and "aktivni=1" in sql[0].replace(" ", ""),
              "_sestava_typ_podle_kodu hleda jen AKTIVNI typy")
        check(not zrcadleno or len(zrcadleno) == 2, f"zrcadleni na disk bylo jen stubem ({len(zrcadleno)}x)")
    finally:
        try:
            real.rollback()
            for t in SHADOW:
                cur.execute(f"DROP TEMPORARY TABLE IF EXISTS {t}")
        finally:
            real.close()
    after = raw_counts()
    check(after == before, f"ostre tabulky beze zmeny (pred {before}, po {after})")


main()
if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"\n{OK} kontrol OK")
