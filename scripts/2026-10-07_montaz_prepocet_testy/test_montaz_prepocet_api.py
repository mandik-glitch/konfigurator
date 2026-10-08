#!/opt/konfigurator/api/venv/bin/python
# -*- coding: utf-8 -*-
"""Prepocet ulozene montaze karet (sestavy AUTO) - SKUTECNE endpointy api/admin_settings.py nad docasnymi tabulkami (bot16, 2026-10-07).

Robert: "chci u tech tlacitek za montaze mit nejen ulozit ale prepocitat vse, aby se vsechny karty prekalkulovaly". Stav ostre DB: 530 sestav AUTO ma v data.price_summary ulozenou montaz pri 20 %
(montaz_pct_applied), nastaveni app_settings.montaz_pct je 10 %. Overuje GET /api/admin/montaz/prepocet (nahled), POST (provedeni), priznak montaz_prepocet v GET /api/admin/settings, zaokrouhleni
pul nahoru (JS Math.round), jen typ AUTO / bez typu, ostatni typy a rozbita data se nedotknou, ostatni klice data zustanou, zaloha starych hodnot v audit_log, idempotence, sazba 0 a desetinna,
neplatna sazba (409), neprihlaseny (401/403).
Do ostrych dat se NEZAPISUJE: product_assemblies, sestava_typ, app_settings a audit_log jsou zastineny TEMPORARY tabulkami (id od 910001); na konci se overi, ze ostre tabulky jsou beze zmeny
(pocty + CRC dat). Spusteni (DB prihlaseni pres systemd):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \\
    scripts/2026-10-07_montaz_prepocet_testy/test_montaz_prepocet_api.py
Kandidat pred nasazenim: --setenv=ADMIN_SETTINGS_PY=/cesta/k/admin_settings.py   (puvodni verze MUSI selhat)"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.abspath(os.path.join(HERE, "..", "..", "api"))
CAND = os.environ.get("ADMIN_SETTINGS_PY")
if CAND:
    tmp_kand = tempfile.mkdtemp(prefix="kand_admin_settings_")
    shutil.copy(CAND, os.path.join(tmp_kand, "admin_settings.py"))
    sys.path.insert(0, tmp_kand)
sys.path.insert(1 if CAND else 0, API)
sys.dont_write_bytecode = True

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import admin_settings  # noqa: E402

if CAND:
    assert os.path.abspath(admin_settings.__file__).startswith(os.path.abspath(tmp_kand)), "nacetl se jiny admin_settings.py: %s" % admin_settings.__file__

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


def ostre_spojeni():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def stav_ostrych():
    c = ostre_spojeni()
    try:
        with c.cursor() as cur:
            out = {}
            cur.execute("SELECT COUNT(*) AS n, COALESCE(SUM(CRC32(data)),0) AS crc, COALESCE(MAX(id),0) AS m FROM product_assemblies"); r = cur.fetchone(); out["product_assemblies"] = (r["n"], int(r["crc"]), r["m"])
            cur.execute("SELECT COUNT(*) AS n, COALESCE(MAX(id),0) AS m FROM audit_log"); r = cur.fetchone(); out["audit_log"] = (r["n"], r["m"])
            cur.execute("SELECT COALESCE(GROUP_CONCAT(setting_key, '=', setting_value ORDER BY setting_key), '') AS s FROM app_settings WHERE setting_key IN ('montaz_pct','vandrawee_montaz_pct','stul_montaz_pct')"); out["sazby"] = cur.fetchone()["s"]
            return out
    finally:
        c.close()


pred = stav_ostrych()
over("0 ostre ID sestav jsou pod 910000", pred["product_assemblies"][2] < 910000, pred)

conn = appmod.get_conn()
real = object.__getattribute__(conn, "_real")
with real.cursor() as cur:
    for t in ("product_assemblies", "sestava_typ", "app_settings", "audit_log"):
        cur.execute("CREATE TEMPORARY TABLE `_tpl_%s` LIKE `%s`" % (t, t))
        cur.execute("CREATE TEMPORARY TABLE `%s` LIKE `_tpl_%s`" % (t, t))
        cur.execute("SELECT COUNT(*) AS n FROM `%s`" % t)
        if cur.fetchone()["n"] != 0:
            raise SystemExit("ABORT: docasna tabulka %s neni prazdna - nestini ostrou, koncim bez zapisu" % t)
    cur.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
    ADMIN = cur.fetchone()["id"]
real.commit()


def vloz_generic(tabulka, hodnoty):
    """INSERT s doplnenim povinnych sloupcu bez vychozi hodnoty (podle SHOW COLUMNS) - test nezavisi na presnem schematu."""
    with real.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM `%s`" % tabulka)
        pole = {}
        for c in cur.fetchall():
            if c["Field"] in hodnoty:
                continue
            if c["Null"] == "NO" and c["Default"] is None and "auto_increment" not in (c["Extra"] or ""):
                t = c["Type"].lower()
                pole[c["Field"]] = 0 if any(x in t for x in ("int", "decimal", "float", "double", "tinyint")) else ("2026-01-01 00:00:00" if any(x in t for x in ("date", "time")) else "")
        pole.update(hodnoty)
        cols = ", ".join("`%s`" % k for k in pole)
        cur.execute("INSERT INTO `%s` (%s) VALUES (%s)" % (tabulka, cols, ", ".join(["%s"] * len(pole))), list(pole.values()))
    real.commit()


vloz_generic("sestava_typ", {"id": 9001, "kod": "AUTO", "nazev": "Auto", "aktivni": 1})
vloz_generic("sestava_typ", {"id": 9002, "kod": "STUL_SKLAD", "nazev": "Stul", "aktivni": 1})


def nastav_sazbu(hodnota):
    with real.cursor() as cur:
        cur.execute("DELETE FROM app_settings WHERE setting_key='montaz_pct'")
        if hodnota is not None:
            cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES ('montaz_pct', %s)", (hodnota,))
    real.commit()


def ps(total, montaz, pct, extra=None):
    d = {"count": 3, "total_czk": total, "montaz_czk": montaz, "montaz_pct_applied": pct, "joint_czk": 123, "packaging_czk": 55}
    d.update(extra or {})
    return {"bom": [{"name": "Profil 40x40 žlutý", "total": 100}], "price_summary": d, "poznamka": "čeština ěščř", "verze": 3}


def vloz_sestavu(id_, typ_id, data, raw=None):
    vloz_generic("product_assemblies", {"id": id_, "name": "TEST-MONTAZ-%d" % id_, "sestava_typ_id": typ_id, "data": raw if raw is not None else json.dumps(data, ensure_ascii=False), "kod_sestavy": "T%d" % id_, "created_by": ADMIN})


def data_sestavy(id_):
    with real.cursor() as cur:
        cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (id_,))
        r = cur.fetchone()
    real.commit()
    return r["data"]


def sestava_json(id_):
    return json.loads(data_sestavy(id_))


def audit_zaznamy():
    with real.cursor() as cur:
        cur.execute("SELECT action, entity_type, detail FROM audit_log ORDER BY id")
        rows = cur.fetchall()
    real.commit()
    return [(r["entity_type"], json.loads(r["detail"])) for r in rows]


def seed():
    with real.cursor() as cur:
        cur.execute("DELETE FROM product_assemblies"); cur.execute("DELETE FROM audit_log")
    real.commit()
    vloz_sestavu(910001, 9001, ps(25905, 5181, 20))                       # pul nahoru: 25905 * 10 % = 2590.5 -> 2591
    vloz_sestavu(910002, None, ps(11827, 2365, 20))                       # starsi sestava ze sceny bez typu = AUTO: 1182.7 -> 1183
    vloz_sestavu(910003, 9002, ps(10000, 2000, 20))                       # jiny typ (stul) - NEDOTKNOUT
    vloz_sestavu(910004, 9001, ps(10000, 1000, 10))                       # uz na 10 % - beze zmeny
    vloz_sestavu(910005, 9001, {"bom": [], "poznamka": "bez price_summary"})
    vloz_sestavu(910006, 9001, None, raw="{rozbite json")
    vloz_sestavu(910007, 9001, None, raw="[]")
    vloz_sestavu(910008, 9001, ps("abc", 1, 20))                          # total neni cislo
    vloz_sestavu(910009, 9001, ps(5000, None, None))                      # montaz zatim neulozena -> 500
    vloz_sestavu(910010, 9001, ps(20000, 4000, 20, {"extra_pole": {"a": [1, 2]}}))   # ostatni klice zustanou


admin = appmod.app.test_client()
with admin.session_transaction() as s:
    s["user_id"] = ADMIN
anon = appmod.app.test_client()

# ---------------------------------------------------------------------------------------------------------------------- A priznak + nahled
print("== A priznak a nahled")
seed(); nastav_sazbu("10.0")
r = admin.get("/api/admin/settings")
over("A1 GET /api/admin/settings nese priznak montaz_prepocet = true (UI podle nej ukaze tlacitko)", r.status_code == 200 and (r.get_json() or {}).get("montaz_prepocet") is True, (r.status_code, (r.get_json() or {}).get("montaz_prepocet")))
pred_data = {i: data_sestavy(i) for i in range(910001, 910011)}
r = admin.get("/api/admin/montaz/prepocet"); j = r.get_json() or {}
over("A2 nahled: sazba 10, 8 sestav AUTO/bez typu, ke zmene 4 (910001, 910002, 910009, 910010), beze zmeny 1, bez ceny 2 (910005, 910008), rozbita data 2 (910006, 910007)",
     r.status_code == 200 and j.get("pct") == 10.0 and j.get("sestav_auto") == 9 and j.get("ke_zmene") == 4 and j.get("bez_zmeny") == 1 and j.get("preskoceno_bez_ceny") == 2 and j.get("preskoceno_rozbita_data") == 2, (r.status_code, j))
uk = j.get("ukazky") or []
over("A3 nahled ukazuje nejvyse 3 ukazky (id, nazev, kod, total, stara a nova castka, stara sazba) - prvni je 910001: 5181 -> 2591 (pul nahoru) pri 20 %",
     len(uk) == 3 and uk[0]["id"] == 910001 and uk[0]["montaz_stara_czk"] == 5181 and uk[0]["montaz_nova_czk"] == 2591 and uk[0]["pct_stara"] == 20 and uk[0]["total_czk"] == 25905 and uk[0]["nazev"] == "TEST-MONTAZ-910001" and uk[0]["kod"] == "T910001", uk)
over("A4 nahled NIC nezapisuje (data vsech sestav i audit jsou beze zmeny)", all(data_sestavy(i) == pred_data[i] for i in pred_data) and audit_zaznamy() == [], audit_zaznamy())
r = admin.get("/api/admin/montaz/prepocet")
over("A5 nahled nesmi cachovat (Cache-Control: no-store)", "no-store" in (r.headers.get("Cache-Control") or ""), r.headers.get("Cache-Control"))

# ---------------------------------------------------------------------------------------------------------------------- B provedeni
print("== B provedeni")
r = admin.post("/api/admin/montaz/prepocet"); j = r.get_json() or {}
over("B1 POST: sazba 10, zmeneno 4, beze zmeny 1, preskoceno 2 + 2", r.status_code == 200 and j.get("pct") == 10.0 and j.get("zmeneno") == 4 and j.get("bez_zmeny") == 1 and j.get("preskoceno_bez_ceny") == 2 and j.get("preskoceno_rozbita_data") == 2, (r.status_code, j))
d1, d2, d9, d10 = (sestava_json(i) for i in (910001, 910002, 910009, 910010))
over("B2 910001: montaz 5181 -> 2591 (pul nahoru, ne bankerske 2590), sazba 10; total_czk beze zmeny", d1["price_summary"]["montaz_czk"] == 2591 and d1["price_summary"]["montaz_pct_applied"] == 10 and d1["price_summary"]["total_czk"] == 25905, d1["price_summary"])
over("B3 910002 (starsi sestava bez typu = AUTO): 2365 -> 1183, sazba 10", d2["price_summary"]["montaz_czk"] == 1183 and d2["price_summary"]["montaz_pct_applied"] == 10, d2["price_summary"])
over("B4 910009 (montaz zatim neulozena): None -> 500, sazba 10", d9["price_summary"]["montaz_czk"] == 500 and d9["price_summary"]["montaz_pct_applied"] == 10, d9["price_summary"])
okr = lambda d: {k: v for k, v in d.items() if k != "price_summary"}
psr = lambda d: {k: v for k, v in d["price_summary"].items() if k not in ("montaz_czk", "montaz_pct_applied")}
over("B5 ostatni klice data (bom, cestina, extra pole, ostatni pole price_summary) zustaly beze zmeny - mění se JEN montaz_czk a montaz_pct_applied", okr(d10) == okr(json.loads(pred_data[910010])) and psr(d10) == psr(json.loads(pred_data[910010])) and d10["price_summary"]["montaz_czk"] == 2000 and okr(d1) == okr(json.loads(pred_data[910001])), [okr(d10), psr(d10)])
over("B6 jiny typ (STUL_SKLAD 910003), bez price_summary (910005), rozbita data (910006, 910007), total neni cislo (910008) a uz spravna (910004) zustaly BYTE-STEJNE", all(data_sestavy(i) == pred_data[i] for i in (910003, 910004, 910005, 910006, 910007, 910008)), [i for i in (910003, 910004, 910005, 910006, 910007, 910008) if data_sestavy(i) != pred_data[i]])
au = audit_zaznamy()
zal = [d for t, d in au if t == "montaz_prepocet_zaloha"]
stare = [x for d in zal for x in d["stare"]]
over("B7 zaloha starych hodnot v audit_log: [id, montaz_czk, montaz_pct_applied] pro vsechny 4 zmenene, vc. None u 910009", sorted(stare, key=lambda x: x[0]) == [[910001, 5181, 20], [910002, 2365, 20], [910009, None, None], [910010, 4000, 20]], stare)
over("B8 jeden souhrnny zaznam montaz_prepocet (pct 10, zmeneno 4)", [d for t, d in au if t == "montaz_prepocet"] == [{"pct": 10.0, "zmeneno": 4, "sestav_auto": 9, "bez_zmeny": 1, "preskoceno_bez_ceny": 2, "preskoceno_rozbita_data": 2}], au)
r = admin.post("/api/admin/montaz/prepocet"); j = r.get_json() or {}
over("B9 idempotence: druhe spusteni nezmeni nic (zmeneno 0, beze zmeny 5) a zaloha se nezapise znovu", r.status_code == 200 and j.get("zmeneno") == 0 and j.get("bez_zmeny") == 5 and len([1 for t, d in audit_zaznamy() if t == "montaz_prepocet_zaloha"]) == len(zal), (j, len(audit_zaznamy())))
r = admin.get("/api/admin/montaz/prepocet"); j = r.get_json() or {}
over("B10 po prepoctu nahled hlasi ke zmene 0", j.get("ke_zmene") == 0 and j.get("ukazky") == [], j)

# ---------------------------------------------------------------------------------------------------------------------- C sazba 0, desetinna, neplatna
print("== C sazby")
seed(); nastav_sazbu("0")
r = admin.post("/api/admin/montaz/prepocet"); j = r.get_json() or {}
d1 = sestava_json(910001)
over("C1 sazba 0 (montaz se nenabizi): montaz_czk = 0 a sazba 0 (jako scena), ne None", r.status_code == 200 and d1["price_summary"]["montaz_czk"] == 0 and d1["price_summary"]["montaz_pct_applied"] == 0 and d1["price_summary"]["montaz_pct_applied"] is not False, (r.status_code, d1["price_summary"]))
seed(); nastav_sazbu("10.5")
r = admin.post("/api/admin/montaz/prepocet"); j = r.get_json() or {}
d1, d10 = sestava_json(910001), sestava_json(910010)
over("C2 desetinna sazba 10.5: 25905 -> 2720 (2720.025), 20000 -> 2100; ulozena sazba je cislo 10.5", d1["price_summary"]["montaz_czk"] == 2720 and d10["price_summary"]["montaz_czk"] == 2100 and d1["price_summary"]["montaz_pct_applied"] == 10.5, (d1["price_summary"], d10["price_summary"]))
for hodnota in ("abc", "-5", "150", ""):
    seed(); nastav_sazbu(hodnota)
    pred2 = {i: data_sestavy(i) for i in range(910001, 910011)}
    g = admin.get("/api/admin/montaz/prepocet"); p = admin.post("/api/admin/montaz/prepocet")
    over("C3 neplatna sazba %r: GET i POST vrati 409 montaz_pct_invalid a nic se nezmeni" % hodnota, g.status_code == 409 and p.status_code == 409 and (p.get_json() or {}).get("error") == "montaz_pct_invalid" and all(data_sestavy(i) == pred2[i] for i in pred2) and audit_zaznamy() == [], (g.status_code, p.status_code, audit_zaznamy()))
seed(); nastav_sazbu(None)
r = admin.get("/api/admin/montaz/prepocet"); j = r.get_json() or {}
over("C4 sazba v nastaveni chybi = 0 (stejne jako GET /api/admin/settings): nahled pocita s 0 %", r.status_code == 200 and j.get("pct") == 0.0, (r.status_code, j))

# ---------------------------------------------------------------------------------------------------------------------- D opravneni, davky auditu
print("== D opravneni a davky")
seed(); nastav_sazbu("10")
pred3 = {i: data_sestavy(i) for i in range(910001, 910011)}
g, p = anon.get("/api/admin/montaz/prepocet"), anon.post("/api/admin/montaz/prepocet")
over("D1 neprihlaseny: GET i POST odmitnuty (401/403) a nic se nezmeni", g.status_code in (401, 403) and p.status_code in (401, 403) and all(data_sestavy(i) == pred3[i] for i in pred3) and audit_zaznamy() == [], (g.status_code, p.status_code))
admin_settings.MONTAZ_PREPOCET_AUDIT_DAVKA = 2
seed(); nastav_sazbu("10")
admin.post("/api/admin/montaz/prepocet")
zal = [d for t, d in audit_zaznamy() if t == "montaz_prepocet_zaloha"]
over("D2 zaloha se do audit_log deli po davkach (davka 2 -> 2 zaznamy po 2), cisla davek 1, 2 a dohromady vsechny 4 stare hodnoty", [d["davka"] for d in zal] == [1, 2] and [len(d["stare"]) for d in zal] == [2, 2], [(d["davka"], len(d["stare"])) for d in zal])
admin_settings.MONTAZ_PREPOCET_AUDIT_DAVKA = 400

# ---------------------------------------------------------------------------------------------------------------------- konec: ostre tabulky beze zmeny
po = stav_ostrych()
over("Z ostre tabulky (product_assemblies pocet + CRC dat, audit_log, sazby) jsou po testu BEZE ZMENY", po == pred, (pred, po))
ok = sum(vysl)
print("\nVYSLEDEK prepocet montaze karet - API: %d/%d OK" % (ok, len(vysl)))
sys.exit(0 if ok == len(vysl) else 1)
