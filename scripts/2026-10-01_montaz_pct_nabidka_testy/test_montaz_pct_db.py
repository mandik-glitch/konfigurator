#!/opt/konfigurator/api/venv/bin/python
"""Sazba montaze pro konkretni nabidku - SKUTECNE endpointy (Flask test client) nad docasnymi tabulkami (bot5, 2026-10-01).

  GET /api/public/offers/<token>              -> payload.montaz_pct = vlastni sazba nabidky, jinak ZIVA vychozi z app_settings
  GET /api/public/offers/<token>/payment-qr   -> castka na QR (zachycena z _build_spayd) = _offer_gross_total s toutez sazbou
Do ostrych dat se NEZAPISUJE: scene_offers, scene_offer_order_prefs a app_settings jsou ve spojeni testu zastineny TEMPORARY tabulkami
(kopie struktury; app_settings i s ostrymi radky), testovaci nabidky maji id 900001+, na konci se overi, ze ostre tabulky jsou beze zmeny.
Endpointy jsou read-only (zadny zapis ani e-mail). Spojeni je to, co vraci app.get_conn() (1 spojeni na vlakno), takze endpointy docasne
tabulky vidi; testovaci data se commitnou jen v techto docasnych tabulkach.

Spusteni (DB prihlaseni pres systemd):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\
    --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \\
    scripts/2026-10-01_montaz_pct_nabidka_testy/test_montaz_pct_db.py
Kandidat pred nasazenim (nic se nezmeni v zivych souborech): --setenv=SCENE_OFFERS_PY=/cesta/k/scene_offers.py
"""
import datetime
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.abspath(os.path.join(HERE, "..", "..", "api"))
SO = os.environ.get("SCENE_OFFERS_PY")
if SO:   # kandidat: slozka s JEDINYM souborem scene_offers.py PRED api/ -> `import app` (konec app.py: import scene_offers) nacte kandidata
    tmp = tempfile.mkdtemp(prefix="kand_scene_offers_")
    shutil.copy(SO, os.path.join(tmp, "scene_offers.py"))
    sys.path.insert(0, tmp)
sys.path.insert(1 if SO else 0, API)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import scene_offers  # noqa: E402

if SO:
    assert os.path.abspath(scene_offers.__file__).startswith(os.path.abspath(tmp)), f"nacetl se jiny scene_offers.py: {scene_offers.__file__}"

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def ostre_spojeni():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                           database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)),
                           charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def stav_ostrych():
    c = ostre_spojeni()
    try:
        with c.cursor() as cur:
            out = {}
            for t in ("scene_offers", "scene_offer_order_prefs", "app_settings"):
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='montaz_pct'")
            r = cur.fetchone()
            out["montaz_pct"] = r["setting_value"] if r else None
            cur.execute("SELECT COALESCE(MAX(id),0) AS m FROM scene_offers")
            out["max_id"] = cur.fetchone()["m"]
            return out
    finally:
        c.close()


pred = stav_ostrych()
over("0 ostre ID nabidek jsou pod 900000 (testovaci id nekoliduji s ostrymi)", pred["max_id"] < 900000, pred)

# ---- docasne tabulky na spojeni, ktere pouziji endpointy
conn = appmod.get_conn()
real = object.__getattribute__(conn, "_real")
with real.cursor() as cur:
    cur.execute("CREATE TEMPORARY TABLE `_tpl_app_settings` LIKE `app_settings`")
    cur.execute("INSERT INTO `_tpl_app_settings` SELECT * FROM `app_settings`")          # kopie ostrych radku (jeste pred stinenim)
    for t in ("scene_offers", "scene_offer_order_prefs", "app_settings"):
        if t != "app_settings":
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
        cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
    cur.execute("INSERT INTO `app_settings` SELECT * FROM `_tpl_app_settings`")
    for t in ("scene_offers", "scene_offer_order_prefs"):
        cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
        if cur.fetchone()["n"] != 0:    # pojistka: docasna tabulka musi stinit ostrou a byt prazdna
            raise SystemExit(f"ABORT: docasna tabulka {t} neni prazdna - nestini ostrou, koncim bez zapisu")
real.commit()


def nastav_vychozi(pct):
    with real.cursor() as cur:
        cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES ('montaz_pct', %s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s", (str(pct), str(pct)))
    real.commit()


def vloz_nabidku(id_, token, total, options):
    with real.cursor() as cur:
        cur.execute(
            "INSERT INTO scene_offers (id, offer_number, items, total_price, view_narys, view_3d_a, view_3d_b, editable_text_popis, "
            "editable_text_patka, view_token_hash, expires_at, is_active, offer_options) "
            "VALUES (%s,%s,%s,%s,'x','x','x','','',%s,%s,1,%s)",
            (id_, f"TESTMP{id_}", json.dumps([{"name": "Polozka", "dim": "-", "qty": "1 ks", "unit_price": total, "total": total}]),
             total, hashlib.sha256(token.encode()).hexdigest(), datetime.datetime.now() + datetime.timedelta(days=5),
             json.dumps(options) if options is not None else None))
    real.commit()


def vloz_prefs(offer_id, guest, **pole):
    with real.cursor() as cur:
        cur.execute("INSERT INTO scene_offer_order_prefs (offer_id, guest_id, qty, montaz_zvolena, montaz_misto, ip_address) VALUES (%s,%s,%s,%s,%s,'127.0.0.1')",
                    (offer_id, guest, pole.get("qty", 1), pole.get("montaz_zvolena", 0), pole.get("montaz_misto")))
    real.commit()


GUEST = "testguest-montaz"
NABIDKY = {   # token -> (id, total_price, offer_options)
    "tok-stara":    (900001, 10000, None),                                           # starsi nabidka bez offer_options (NULL)
    "tok-vlastni":  (900002, 10000, {"show_qr": True, "montaz_pct": 15.0}),          # vlastni sazba 15 %
    "tok-nula":     (900003, 10000, {"show_qr": True, "montaz_pct": 0.0}),           # bez montaze
    "tok-bez":      (900004, 10000, {"show_qr": True, "montaz_pct": None}),          # nova nabidka, sazba nezvolena -> vychozi
    "tok-auto15":   (900005, 10000, {"is_vehicle_assembly": True, "montaz_pct": 15.0}),   # sestava do auta + vlastni sazba
    "tok-auto":     (900006, 10000, {"is_vehicle_assembly": True}),                  # sestava do auta bez vlastni sazby
    "tok-auto0":    (900007, 10000, {"is_vehicle_assembly": True, "montaz_pct": 0.0}),
}
for tok, (i, total, opt) in NABIDKY.items():
    vloz_nabidku(i, tok, total, opt)
for tok in ("tok-auto15", "tok-auto", "tok-auto0"):
    vloz_prefs(NABIDKY[tok][0], GUEST, qty=1, montaz_zvolena=1, montaz_misto="praha")

# ---- klient + zachyceni castky QR
klient = appmod.app.test_client()
with klient.session_transaction() as s:
    s["quote_guest_id"] = GUEST
zachyceno = []
puvodni_spayd = scene_offers._build_spayd
scene_offers._build_spayd = lambda iban, amount, vs, message="": (zachyceno.append(amount), puvodni_spayd(iban, amount, vs, message))[1]


def payload(tok):
    r = klient.get(f"/api/public/offers/{tok}")
    return r.status_code, (r.get_json(silent=True) or {})


def qr_castka(tok, qty=None):
    zachyceno.clear()
    r = klient.get(f"/api/public/offers/{tok}/payment-qr" + (f"?qty={qty}" if qty else ""))
    return r.status_code, (zachyceno[-1] if zachyceno else None)


try:
    nastav_vychozi(20)
    print("== verejny payload (vychozi sazba v nastaveni = 20 %)")
    for tok, cekano, popis in [("tok-stara", 20.0, "starsi nabidka bez offer_options -> ZIVA vychozi 20"),
                               ("tok-bez", 20.0, "nova nabidka bez zvolene sazby (montaz_pct null) -> vychozi 20"),
                               ("tok-vlastni", 15.0, "vlastni sazba 15 prebije vychozi 20"),
                               ("tok-nula", 0.0, "vlastni sazba 0 = bez montaze (nepadne na vychozi 20)"),
                               ("tok-auto", 20.0, "sestava do auta bez vlastni sazby -> vychozi 20"),
                               ("tok-auto15", 15.0, "sestava do auta s vlastni sazbou 15")]:
        kod, p = payload(tok)
        over(f"P {popis}", kod == 200 and p.get("montaz_pct") == cekano and isinstance(p.get("montaz_pct"), (int, float)), (kod, p.get("montaz_pct")))
    kod, p = payload("tok-vlastni")
    over("P payload nese i offer_options.montaz_pct (15.0) a total_price", p.get("offer_options", {}).get("montaz_pct") == 15.0 and p.get("total_price") == 10000, p.get("offer_options"))
    kod, p = payload("tok-stara")
    over("P starsi nabidka: offer_options z vychozich (montaz_pct None), stranka nespadne", kod == 200 and p["offer_options"].get("montaz_pct") is None, p.get("offer_options"))

    print("== vychozi sazba se zmeni na 25 % (ziva)")
    nastav_vychozi(25)
    over("P2 starsi nabidka i nabidka bez zvolene sazby ctou NOVOU vychozi 25", payload("tok-stara")[1]["montaz_pct"] == 25.0 and payload("tok-bez")[1]["montaz_pct"] == 25.0, None)
    over("P2 nabidky s vlastni sazbou (15 a 0) se zmenou vychozi NEzmeni", payload("tok-vlastni")[1]["montaz_pct"] == 15.0 and payload("tok-nula")[1]["montaz_pct"] == 0.0, None)

    print("== castka na QR platbe a v objednavce (zakaznik zvolil montaz u sestav do auta)")
    nastav_vychozi(20)
    # 10 000 bez DPH; montaz = sazba % z 10 000; s DPH 21 %
    for tok, cekano, popis in [("tok-auto15", 13915.0, "vlastni 15 %: (10 000 + 1 500) x 1,21"),
                               ("tok-auto", 14520.0, "bez vlastni sazby, vychozi 20 %: (10 000 + 2 000) x 1,21"),
                               ("tok-auto0", 12100.0, "vlastni 0 % = bez montaze: 10 000 x 1,21"),
                               ("tok-vlastni", 12100.0, "nabidka, ktera neni sestava do auta, montaz do ceny nepridava: 10 000 x 1,21")]:
        kod, castka = qr_castka(tok)
        over(f"Q {popis} = {cekano}", kod == 200 and castka == cekano, (kod, castka))
    kod, castka = qr_castka("tok-auto15", qty=3)
    over("Q 3 ks, vlastni 15 %: (30 000 + 4 500) x 1,21 = 41 745", kod == 200 and castka == 41745.0, (kod, castka))
    nastav_vychozi(25)
    over("Q po zmene vychozi na 25 %: sestava bez vlastni sazby (10 000 + 2 500) x 1,21 = 15 125, s vlastni 15 % beze zmeny 13 915",
         qr_castka("tok-auto")[1] == 15125.0 and qr_castka("tok-auto15")[1] == 13915.0, (qr_castka("tok-auto"), qr_castka("tok-auto15")))
finally:
    scene_offers._build_spayd = puvodni_spayd
    with real.cursor() as cur:
        for t in ("scene_offers", "scene_offer_order_prefs", "app_settings", "_tpl_scene_offers", "_tpl_scene_offer_order_prefs", "_tpl_app_settings"):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")     # TEMPORARY: ostrou tabulku to nikdy nezahodi
    real.commit()

po = stav_ostrych()
over("Z ostre tabulky (scene_offers, scene_offer_order_prefs, app_settings) i ostra sazba montaze jsou po testu beze zmeny", po == pred, (pred, po))

ok = sum(vysl)
print(f"\nVYSLEDEK sazba montaze pro nabidku - skutecne endpointy: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
