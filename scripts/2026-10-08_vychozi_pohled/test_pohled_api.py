#!/opt/konfigurator/api/venv/bin/python
"""Test VYCHOZIHO UHLU POHLEDU 3D v generatorech - backend (api/stul_pohled.py + pole `view` ve schematu konfiguratoru; bot10, 2026-10-08) pres Flask test_client nad DOCASNYMI tabulkami.

Skutecna aplikace (RBAC dekoratory, cesty, JSON, verejne schema), ale zapisy (app_settings, audit_log) jdou do TEMPORARY tabulek souvisleho spojeni; ostre tabulky se kontroluji PRED a PO.
Admin = session s id skutecneho admina (jen cteni app_users).

Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PRIVATE_FILES_DIR=/tmp/pf_pohled --working-directory=/opt/konfigurator \
            api/venv/bin/python3 scripts/2026-10-08_vychozi_pohled/test_pohled_api.py       (kandidat: POHLED_DIR=<koren prekryvu s api/>; ma prednost pred zivym api)"""
import json
import os
import sys
import threading

import pymysql

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.path.join(os.environ["POHLED_DIR"], "api") if os.environ.get("POHLED_DIR") else os.path.join(REPO, "api")
sys.path.insert(0, API)
sys.path.insert(0, os.path.join(REPO, "scripts"))
_o = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
try:
    import app as appmod  # noqa: E402
    import stul_pohled as P  # noqa: E402
    import stul_shop as SH  # noqa: E402
finally:
    threading.Thread.start = _o

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


def connect():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)),
                           charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


class Sdilene:
    """Atrapa get_conn(): stale TO SAMO spojeni s temp tabulkami; close() = rollback jako u skutecneho sdileneho spojeni."""
    def __init__(self, c):
        self.c = c

    def cursor(self):
        return self.c.cursor()

    def commit(self):
        self.c.commit()

    def rollback(self):
        self.c.rollback()

    def close(self):
        self.c.rollback()


def stav_ostry():
    c = connect()
    try:
        cur = c.cursor()
        cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (P.POHLED_KLIC,))
        a = (cur.fetchone() or {}).get("setting_value")
        cur.execute("SELECT COUNT(*) n, COALESCE(MAX(id),0) m FROM audit_log")
        b = cur.fetchone()
        return {"klic": a, "audit": (b["n"], b["m"])}
    finally:
        c.rollback()
        c.close()


def main():
    pred = stav_ostry()
    test = connect()
    tc = test.cursor()
    for t in ("app_settings", "audit_log"):                     # stinove tabulky (LIKE sama sebe MySQL nepusti, chyba 1066 -> pres sablonu)
        tc.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
        tc.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
    test.commit()
    puv_gc = P.get_conn
    P.get_conn = lambda: Sdilene(test)
    P._CACHE.update(t=0.0, view=None)
    client = appmod.app.test_client()
    pc = connect(); cu = pc.cursor()
    cu.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
    admin_id = cu.fetchone()["id"]; pc.rollback(); pc.close()
    cur = test.cursor()
    URL = "/api/shop/configurator/view"
    SCHEMA = "/api/shop/products/4954/configurator?lang=cs"

    def put(body, raw=None):
        r = client.put(URL, data=raw if raw is not None else json.dumps(body), content_type="application/json")
        return r.status_code, (r.get_json(silent=True) or {})

    def ulozeno():
        cur.execute("SELECT setting_value v FROM app_settings WHERE setting_key=%s", (P.POHLED_KLIC,))
        r = cur.fetchone()
        return json.loads(r["v"]) if r else None

    def schema_view():
        r = client.get(SCHEMA)
        d = r.get_json(silent=True) or {}
        return r.status_code, d.get("view", "CHYBI"), d

    try:
        # ---------------------------------------------------------------- 0) cista validace
        print("\n## 0) pohled_over: meze, zaokrouhleni, zabaleni")
        over("0.1 platny pohled: zaokrouhleni na 0,1", P.pohled_over({"az": 35, "el": 25}) == {"az": 35.0, "el": 25.0} and P.pohled_over({"az": -40.26, "el": 17.04}) == {"az": -40.3, "el": 17.0})
        over("0.2 az se zabali do (-180, 180]: 190 -> -170, -190 -> 170, 360 -> 0, 540 -> 180, -180 -> 180, 180 -> 180",
             [P.pohled_over({"az": a, "el": 10})["az"] for a in (190, -190, 360, 540, -180, 180)] == [-170.0, 170.0, 0.0, 180.0, 180.0, 180.0], [P.pohled_over({"az": a, "el": 10})["az"] for a in (190, -190, 360, 540, -180, 180)])
        over("0.3 meze elevace: -15 a 85 platne, -15,1 a 85,1 chyba", P.pohled_over({"az": 0, "el": -15})["el"] == -15.0 and P.pohled_over({"az": 0, "el": 85})["el"] == 85.0
             and all(_chyba({"az": 0, "el": e}) for e in (-15.1, 85.1, -90, 90)), None)
        over("0.4 spatny tvar je chyba: ne objekt, chybi / navic klic, text, bool, NaN / Infinity",
             all(_chyba(x) for x in (None, [], "35", 5, {"az": 1}, {"el": 1}, {"az": 1, "el": 2, "zoom": 3}, {"az": "1", "el": 2}, {"az": True, "el": 2}, {"az": 1, "el": None}, {"az": float("nan"), "el": 2}, {"az": 1, "el": float("inf")})))

        # ---------------------------------------------------------------- 1) pristup
        print("\n## 1) pristup (RBAC)")
        r = client.put(URL, data="{}", content_type="application/json"); r2 = client.delete(URL)
        over("1.1 anonym: PUT i DELETE = 401 a nic se nezapsalo", r.status_code == 401 and r2.status_code == 401 and ulozeno() is None, (r.status_code, r2.status_code))
        puv_cu = appmod.current_user
        appmod.current_user = lambda: {"id": 4242, "role": "user", "active": 1, "email": "z@example.test", "name": "Zakaznik"}
        try:
            r = client.put(URL, data=json.dumps({"az": 10, "el": 10}), content_type="application/json"); r2 = client.delete(URL)
        finally:
            appmod.current_user = puv_cu
        over("1.2 bezny zakaznik (role user): PUT i DELETE = 403 a nic se nezapsalo", r.status_code == 403 and r2.status_code == 403 and ulozeno() is None, (r.status_code, r2.status_code))
        with client.session_transaction() as s:
            s["user_id"] = admin_id

        # ---------------------------------------------------------------- 2) schema a ulozeni
        print("\n## 2) verejne schema nese `view`; ulozeni, smazani, audit")
        st, v, d = schema_view()
        over("2.1 bez ulozeneho pohledu: schema ma klic `view` = null (probe pro UI: klic existuje)", st == 200 and v is None and "view" in d, (st, v))
        st, j = put({"az": -40.26, "el": 17.04})
        over("2.2 PUT {az, el}: 200 a normalizovana hodnota {az -40,3, el 17,0}", st == 200 and j == {"view": {"az": -40.3, "el": 17.0}}, (st, j))
        over("2.3 ulozeno v app_settings jako JSON (razene klice) a okamzite videt ve schematu (cache se obnovila)", ulozeno() == {"az": -40.3, "el": 17.0} and schema_view()[1] == {"az": -40.3, "el": 17.0}, (ulozeno(), schema_view()[1]))
        cur.execute("SELECT * FROM audit_log WHERE entity_type='configurator_view' ORDER BY id DESC LIMIT 1")
        au = cur.fetchone()
        over("2.4 audit_log: update / configurator_view, bez entity_id, detail s hodnotou", au and au["action"] == "update" and au["entity_id"] is None and "-40.3" in au["detail"], au)
        P._CACHE.update(t=0.0, view=None)                          # jiny worker: cache prazdna -> cte z DB
        over("2.5 jiny worker (prazdna cache) cte ulozenou hodnotu z DB", P.nacti_pohled() == {"az": -40.3, "el": 17.0})
        st, j = put({"az": 200, "el": 90})
        over("2.6 neplatny pohled (el 90) = 400 s textem a NIC se nezmenilo", st == 400 and "el" in j.get("error", "") and ulozeno() == {"az": -40.3, "el": 17.0}, (st, j))
        for nazev, raw in (("neplatny JSON", "not json"), ("pole", "[1,2]"), ("text", '"x"'), ("prazdne telo", "")):
            st, j = put(None, raw=raw)
            over(f"2.7 {nazev} = 400 a nic se nezmenilo", st == 400 and ulozeno() == {"az": -40.3, "el": 17.0}, (st, j))
        st, j = put({"az": 200, "el": 5.55})
        over("2.8 dalsi PUT prepise: az 200 -> -160, el 5,55 -> 5,5 / 5,6", st == 200 and j["view"]["az"] == -160.0 and j["view"]["el"] in (5.5, 5.6) and ulozeno() == j["view"], (st, j))
        st, j = put(None, raw="null")
        over("2.9 PUT null maze ulozeny pohled (zpet na puvodni) a schema ma zase null", st == 200 and j == {"view": None} and ulozeno() is None and schema_view()[1] is None, (st, j))
        put({"az": 12, "el": 34})
        r = client.delete(URL)
        over("2.10 DELETE: 200 {view: null}, smazano, schema null, audit delete", r.status_code == 200 and r.get_json() == {"view": None} and ulozeno() is None and schema_view()[1] is None, (r.status_code, r.get_json()))
        cur.execute("SELECT action FROM audit_log WHERE entity_type='configurator_view' ORDER BY id")
        over("2.11 audit ma postupne update, update, delete (PUT null), update, delete", [x["action"] for x in cur.fetchall()] == ["update", "update", "delete", "update", "delete"])
        # poskozena ulozena hodnota nesmi shodit schema
        cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s)", (P.POHLED_KLIC, '{"az": "x", "el": 1}'))
        P._CACHE.update(t=0.0, view=None)
        st, v, d = schema_view()
        over("2.12 poskozena ulozena hodnota = schema se vrati normalne s view null (nikdy 500)", st == 200 and v is None, (st, v))
        cur.execute("UPDATE app_settings SET setting_value=%s WHERE setting_key=%s", ("not json", P.POHLED_KLIC))
        P._CACHE.update(t=0.0, view=None)
        over("2.13 hodnota, ktera neni JSON = totez", schema_view()[:2] == (200, None))
        cur.execute("DELETE FROM app_settings WHERE setting_key=%s", (P.POHLED_KLIC,))
        P._CACHE.update(t=0.0, view=None)

        # ---------------------------------------------------------------- 3) schema ostatnich produktu a dopravniku
        print("\n## 3) schema: ostatni pole beze zmeny")
        put({"az": -30, "el": 20})
        r = client.get(SCHEMA)
        d = r.get_json(silent=True) or {}
        over("3.1 schema stale ma env, default_saved, systems, slots a navic view", r.status_code == 200 and all(k in d for k in ("env", "default_saved", "systems", "slots", "view", "default_selection")) and d["view"] == {"az": -30.0, "el": 20.0}, sorted(d)[:12])
        r2 = client.get("/api/shop/products/5353/configurator?lang=cs")
        d2 = r2.get_json(silent=True) or {}
        over("3.2 stejny pohled pro vsechny generatory (system 45, karta 5353) - jedno nastaveni", r2.status_code == 200 and d2.get("view") == {"az": -30.0, "el": 20.0}, (r2.status_code, d2.get("view")))
    finally:
        P.get_conn = puv_gc
        P._CACHE.update(t=0.0, view=None)
        test.rollback()
        test.close()

    po = stav_ostry()
    print("\n## 9) ostre tabulky se nezmenily")
    over("9.1 ostry klic configurator_view_default a audit_log beze zmeny", pred == po, (pred, po))
    print("\n%d/%d OK" % (sum(vysl), len(vysl)))
    sys.exit(0 if all(vysl) else 1)


def _chyba(x):
    try:
        P.pohled_over(x)
    except ValueError:
        return True
    return False


main()
