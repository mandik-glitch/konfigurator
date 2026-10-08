#!/opt/konfigurator/api/venv/bin/python
# -*- coding: utf-8 -*-
"""Sleva v online nabidce (offer_options.discount_pct) - SKUTECNE endpointy scene_offers.py nad docasnymi tabulkami (bot16, 2026-10-07).

Robert: "chci v cenovem souhrnu online nabidky nabidnout slevu, i v te 0133 zpetne". Overuje celou cestu: admin PUT /api/admin/scene-offers/<id> (sleva zpetne u uz existujici nabidky,
zrusena prazdnou, zachovana kdyz formular klic neposle), verejny GET /api/public/offers/<token> (discount_pct) a castka v QR platbe (payment-qr, SPAYD) = _offer_gross_total se slevou
(mnozstvi, doprava se neslevnuje, montaz z ceny po sleve).
Do ostrych dat se NEZAPISUJE: scene_offers a scene_offer_revisions jsou zastineny TEMPORARY tabulkami, audit vypnuty, testovaci nabidky maji id 900401+; na konci se overi, ze ostre tabulky jsou
beze zmeny. Spusteni (DB prihlaseni pres systemd):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \\
    scripts/2026-10-07_nabidka_sleva_testy/test_sleva_endpointy.py
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
            for t in ("scene_offers", "scene_offer_revisions", "audit_log"):
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
    for t in ("scene_offers", "scene_offer_revisions"):
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
print("== A verejny payload a QR")
vloz(900401, {"show_qr": True})
sc, d = verejne(900401)
over("A1 nabidka BEZ slevy: payload nese discount_pct 0, cena beze zmeny (total_price 10 000)", sc == 200 and d.get("discount_pct") == 0 and d.get("total_price") == 10000, (sc, d.get("discount_pct"), d.get("total_price")))
sc, c = qr_castka(900401)
over("A2 QR bez slevy: 10 000 x 1,21 = 12 100,00", sc == 200 and c == 12100.0, (sc, c))
vloz(900402, {"show_qr": True, "discount_pct": 10})
sc, d = verejne(900402)
over("A3 nabidka se slevou 10 %: payload nese discount_pct 10.0 (cena zbozi total_price zustava puvodni 10 000 - sleva se pocita v souhrnu)", sc == 200 and d.get("discount_pct") == 10.0 and d.get("total_price") == 10000, (sc, d.get("discount_pct"), d.get("total_price")))
sc, c = qr_castka(900402)
over("A4 QR se slevou 10 %: (10 000 - 1 000) x 1,21 = 10 890,00", sc == 200 and c == 10890.0, (sc, c))
sc, c = qr_castka(900402, "?qty=3")
over("A5 QR se slevou a 3 ks: (30 000 - 3 000) x 1,21 = 32 670,00", sc == 200 and c == 32670.0, (sc, c))
sc, c = qr_castka(900402, "?deposit_pct=50")
over("A6 QR zaloha 50 % ze zlevnene ceny: 10 890 x 0,5 = 5 445,00", sc == 200 and c == 5445.0, (sc, c))

# ------------------------------------------------------------------------------------------------------------------ B zpetne pres admina
print("== B sleva zpetne (admin Upravit nabidku)")
vloz(900403, {"show_qr": True})
r = put(900403, {"show_qr": True, "discount_pct": 15})
over("B1 PUT admin: sleva 15 % se ulozi zpetne k uz existujici nabidce (stav 200, ulozeno 15.0)", r.status_code == 200 and ulozene_volby(900403).get("discount_pct") == 15.0, (r.status_code, ulozene_volby(900403)))
sc, d = verejne(900403)
over("B2 verejny payload hned ukazuje slevu 15.0", d.get("discount_pct") == 15.0, d.get("discount_pct"))
sc, c = qr_castka(900403)
over("B3 QR po zpetne sleve: (10 000 - 1 500) x 1,21 = 10 285,00", c == 10285.0, c)
r = put(900403, {"show_qr": True})
over("B4 formular slevu NEPOSLAL (starsi admin.html v cache) -> sleva 15 zustane", r.status_code == 200 and ulozene_volby(900403).get("discount_pct") == 15.0, ulozene_volby(900403))
r = put(900403, {"show_qr": True, "discount_pct": None})
over("B5 prazdna sleva z formulare = sleva zrusena (None), QR zpet na 12 100", r.status_code == 200 and ulozene_volby(900403).get("discount_pct") is None and qr_castka(900403)[1] == 12100.0, (ulozene_volby(900403), qr_castka(900403)))
r = put(900403, {"show_qr": True, "discount_pct": 250})
over("B6 nesmyslna sleva (250) se neulozi (None = bez slevy)", r.status_code == 200 and ulozene_volby(900403).get("discount_pct") is None, ulozene_volby(900403))

# ------------------------------------------------------------------------------------------------------------------ C montaz z ceny po sleve (sestava do auta)
print("== C montaz a doprava")
vloz(900404, {"show_qr": True, "is_vehicle_assembly": True, "montaz_pct": 20, "discount_pct": 10})
sc, d = verejne(900404)
over("C1 sestava do auta: payload nese montaz_pct 20 i discount_pct 10", d.get("montaz_pct") == 20.0 and d.get("discount_pct") == 10.0, (d.get("montaz_pct"), d.get("discount_pct")))
with real.cursor() as cur:
    cur.execute("SELECT 1")
real.commit()
over("C2 _offer_gross_total pro zvolenou montaz: zbozi 10 000 - 10 % = 9 000, montaz 20 % z 9 000 = 1 800, celkem 10 800 bez DPH = 13 068,00 s DPH",
     scene_offers._offer_gross_total({"total_price": 10000, "offer_options": json.dumps({"is_vehicle_assembly": True, "montaz_pct": 20, "discount_pct": 10})}, {"montaz_zvolena": 1, "qty": 1}, "0") == 13068.0, None)
over("C3 doprava se neslevnuje (Toptrans 1 000 Kc): 9 000 + 1 000 = 10 000 -> 12 100,00",
     scene_offers._offer_gross_total({"total_price": 10000, "offer_options": json.dumps({"discount_pct": 10})}, {"qty": 1, "shipping_method": "toptrans", "toptrans_price_czk": 1000}, "0") == 12100.0, None)

over("C4 pricky do multiboxu (bot8) + sleva: sleva JEN z ceny zbozi (pricky se neslevnuji), montaz z ceny po sleve PLUS pricky: 2 ks, zbozi 20 000 - 10 % = 18 000, pricky 2 x 500 = 1 000, montaz 20 % z 19 000 = 3 800, celkem 22 800 bez DPH = 27 588,00",
     scene_offers._offer_gross_total({"total_price": 10000, "offer_options": json.dumps({"is_vehicle_assembly": True, "montaz_pct": 20, "discount_pct": 10})}, {"montaz_zvolena": 1, "qty": 2, "pricky_net": 500}, "0") == 27588.0,
     scene_offers._offer_gross_total({"total_price": 10000, "offer_options": json.dumps({"is_vehicle_assembly": True, "montaz_pct": 20, "discount_pct": 10})}, {"montaz_zvolena": 1, "qty": 2, "pricky_net": 500}, "0"))

# ------------------------------------------------------------------------------------------------------------------ D priznak podpory slevy pro admin formular
print("== D edit-data nese priznak podpory slevy")
vloz(900405, {"show_qr": True, "discount_pct": 12})
r = admin.get("/api/admin/scene-offers/900405/edit-data")
j = r.get_json() or {}
over("D1 edit-data: priznak sleva {max_pct: 100} (admin formular ukaze pole Sleva JEN s nim - staticky kod je zivy driv nez API)", r.status_code == 200 and j.get("sleva") == {"max_pct": 100}, (r.status_code, j.get("sleva")))
over("D2 edit-data nese ulozenou slevu v offer_options.discount_pct (12)", (j.get("offer_options") or {}).get("discount_pct") == 12, j.get("offer_options"))
vloz(900406, {"show_qr": True})
j = admin.get("/api/admin/scene-offers/900406/edit-data").get_json() or {}
over("D3 nabidka bez slevy: priznak sleva je take (vlastnost backendu), discount_pct v offer_options chybi", j.get("sleva") == {"max_pct": 100} and (j.get("offer_options") or {}).get("discount_pct") is None, (j.get("sleva"), j.get("offer_options")))

# ------------------------------------------------------------------------------------------------------------------ Z uklid
print("== Z uklid")
scene_offers._build_spayd = _puvodni_spayd
po = stav_ostrych()
over("Z ostre tabulky scene_offers / scene_offer_revisions / audit_log beze zmeny", po == pred, (pred, po))
ok = sum(vysl)
print(f"\n{ok}/{len(vysl)} kontrol OK")
sys.exit(0 if ok == len(vysl) else 1)
