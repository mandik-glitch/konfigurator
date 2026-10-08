#!/opt/konfigurator/api/venv/bin/python
# -*- coding: utf-8 -*-
"""Admin: detail online nabidky (GET /api/admin/scene-offers/<id>/stats) - volby klienta nesou i pocet kusu, zvolenou montaz a MISTO montaze Praha / Slavicin (bot16, 2026-10-07).

Robert: "zase tam chybi montaz KDE Praha/Slavicin" - SKUTECNY endpoint scene_offers.py nad docasnymi tabulkami scene_offers a scene_offer_order_prefs (skutecna tabulka montaz_mista jen cte se pro popisky).
Do ostrych dat se NEZAPISUJE: scene_offers a scene_offer_revisions jsou zastineny TEMPORARY tabulkami, audit vypnuty, testovaci nabidky maji id 900401+; na konci se overi, ze ostre tabulky jsou
beze zmeny. Spusteni (DB prihlaseni pres systemd):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \\
    scripts/2026-10-07_nabidka_admin_volby_testy/test_admin_volby_api.py
Kandidat pred nasazenim: --setenv=SCENE_OFFERS_PY=/cesta/k/scene_offers.py   (puvodni verze MUSI selhat)"""
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.abspath(os.path.join(HERE, "..", "..", "api"))
SO = os.environ.get("SCENE_OFFERS_PY")
if SO:
    tmp_kand = tempfile.mkdtemp(prefix="kand_scene_offers_")
    shutil.copy(SO, os.path.join(tmp_kand, "scene_offers.py"))
    sys.path.insert(0, tmp_kand)
sys.path.insert(1 if SO else 0, API)
sys.dont_write_bytecode = True

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import scene_offers  # noqa: E402

if SO:
    assert os.path.abspath(scene_offers.__file__).startswith(os.path.abspath(tmp_kand)), "nacetl se jiny scene_offers.py: %s" % scene_offers.__file__

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def ostre_spojeni():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def stav_ostrych():
    c = ostre_spojeni()
    try:
        with c.cursor() as cur:
            out = {}
            for t in ("scene_offers", "scene_offer_revisions", "scene_offer_order_prefs", "audit_log"):
                cur.execute("SELECT COUNT(*) AS n, COALESCE(MAX(id),0) AS m FROM `%s`" % t)
                r = cur.fetchone()
                out[t] = (r["n"], r["m"])
            return out
    finally:
        c.close()


pred = stav_ostrych()
over("0 ostre ID nabidek jsou pod 900000", pred["scene_offers"][1] < 900000, pred)

conn = appmod.get_conn()
real = object.__getattribute__(conn, "_real")
with real.cursor() as cur:
    for t in ("scene_offers", "scene_offer_order_prefs"):
        cur.execute("CREATE TEMPORARY TABLE `_tpl_%s` LIKE `%s`" % (t, t))
        cur.execute("CREATE TEMPORARY TABLE `%s` LIKE `_tpl_%s`" % (t, t))
        cur.execute("SELECT COUNT(*) AS n FROM `%s`" % t)
        if cur.fetchone()["n"] != 0:
            raise SystemExit("ABORT: docasna tabulka %s neni prazdna - nestini ostrou, koncim bez zapisu" % t)
    cur.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
    ADMIN = cur.fetchone()["id"]
real.commit()
scene_offers.log_audit = lambda *a, **k: None

ITEMS = [{"name": "Regál levý", "qty": 1, "unit_price": 4000, "total": 4000}, {"name": "Regál pravý", "qty": 1, "unit_price": 6000, "total": 6000}]
ADMIN_TOKEN = "admin-tok-%d"
TOK = "klient-tok-%d"


def vloz(id_, options, total=10000):
    with real.cursor() as cur:
        cur.execute("INSERT INTO scene_offers (id, offer_number, items, total_price, view_narys, view_bokorys, view_3d_a, view_3d_b, editable_text_popis, editable_text_patka, view_token_hash, "
                    "admin_view_token_hash, expires_at, is_active, offer_options, revision_number) VALUES (%s,%s,%s,%s,'x','x','x','x','','',%s,%s,%s,1,%s,1)",
                    (id_, "TESTSL%d" % id_, json.dumps(ITEMS, ensure_ascii=False), total, hashlib.sha256((TOK % id_).encode()).hexdigest(),
                     hashlib.sha256((ADMIN_TOKEN % id_).encode()).hexdigest(), datetime.datetime.now() + datetime.timedelta(days=5), json.dumps(options)))
    real.commit()


def ulozene_volby(id_):
    with real.cursor() as cur:
        cur.execute("SELECT offer_options FROM scene_offers WHERE id=%s", (id_,))
        r = cur.fetchone()
    real.commit()
    return json.loads(r["offer_options"])


admin = appmod.app.test_client()
with admin.session_transaction() as s:
    s["user_id"] = ADMIN
anon = appmod.app.test_client()


def put(id_, options, total=10000):
    return admin.put("/api/admin/scene-offers/%d" % id_, json={"items": ITEMS, "total_price": total, "editable_text": {"popis": "p", "patka": "f"}, "offer_options": options, "change_note": "test"})


def verejne(id_):
    r = anon.get("/api/public/offers/%s" % (TOK % id_))
    return r.status_code, (r.get_json() or {})


zachyceno = []
_puvodni_spayd = scene_offers._build_spayd


def _spayd_zachyt(iban, amount, vs, label):
    zachyceno.append(amount)
    return _puvodni_spayd(iban, amount, vs, label)


scene_offers._build_spayd = _spayd_zachyt


def qr_castka(id_, qs=""):
    zachyceno.clear()
    r = anon.get("/api/public/offers/%s/payment-qr%s" % (TOK % id_, qs))
    return r.status_code, (zachyceno[-1] if zachyceno else None)


# ------------------------------------------------------------------------------------------------------------------ A verejny payload
def prefs(offer_id, guest, **k):
    d = dict(shipping_method=None, payment_method=None, deposit_pct=None, delivery_state=None, montaz_zvolena=0, montaz_misto=None, qty=1, delivery_zip=None, toptrans_price_czk=None)
    d.update(k)
    with real.cursor() as cur:
        cur.execute("INSERT INTO scene_offer_order_prefs (offer_id, guest_id, shipping_method, payment_method, deposit_pct, delivery_state, montaz_zvolena, montaz_misto, qty, delivery_zip, "
                    "toptrans_price_czk, ip_address) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'127.0.0.1')",
                    (offer_id, guest, d["shipping_method"], d["payment_method"], d["deposit_pct"], d["delivery_state"], d["montaz_zvolena"], d["montaz_misto"], d["qty"], d["delivery_zip"], d["toptrans_price_czk"]))
    real.commit()


def stats(offer_id):
    r = admin.get("/api/admin/scene-offers/%d/stats" % offer_id)
    return r.status_code, (r.get_json() or {})


print("== A volby klienta v detailu nabidky")
vloz(900501, {"show_qr": True, "is_vehicle_assembly": True, "montaz_pct": 15})
prefs(900501, "g1", shipping_method="vlastni", payment_method="zaloha", deposit_pct=70, montaz_zvolena=1, montaz_misto="slavicin", qty=3)
prefs(900501, "g2", shipping_method="toptrans", payment_method="dobirka", qty=1)
prefs(900501, "g3", montaz_zvolena=1, montaz_misto="neexistuje-misto", qty=2)
sc, d = stats(900501)
op = d.get("order_prefs") or []
over("A1 stats: stav 200 a tri radky voleb (tri navstevnici)", sc == 200 and len(op) == 3, (sc, len(op)))
po = {(p["qty"], p["montaz_misto"]): p for p in op}
p1 = po.get((3, "slavicin"))
over("A2 zvolena montaz ve Slavicine: montaz_zvolena true, montaz_misto slavicin, popisek Slavicin (z tabulky montaz_mista), qty 3", p1 and p1["montaz_zvolena"] is True and p1["montaz_misto_label"] == "Slavičín", p1)
p2 = [p for p in op if p["shipping_method"] == "toptrans"][0]
over("A3 bez montaze: montaz_zvolena false, misto a popisek None, qty 1", p2["montaz_zvolena"] is False and p2["montaz_misto"] is None and p2["montaz_misto_label"] is None and p2["qty"] == 1, p2)
p3 = po.get((2, "neexistuje-misto"))
over("A4 misto, ktere uz v ciselniku neni: popisek = klic (zvolena montaz zustane citelna)", p3 and p3["montaz_misto_label"] == "neexistuje-misto", p3)
over("A5 puvodni pole voleb zustavaji (doprava, platba, zaloha, stav dodani, PSC, cena Toptrans, updated_at)", all(k in p1 for k in ("shipping_method", "payment_method", "deposit_pct", "delivery_state", "delivery_zip", "toptrans_price_czk", "updated_at")) and p1["payment_method"] == "zaloha" and p1["deposit_pct"] == 70, p1)

print("== Z uklid")
po_ = stav_ostrych()
over("Z ostre tabulky scene_offers / scene_offer_revisions / scene_offer_order_prefs / audit_log beze zmeny", po_ == pred, (pred, po_))
ok = sum(vysl)
print(f"\n{ok}/{len(vysl)} kontrol OK")
sys.exit(0 if ok == len(vysl) else 1)
