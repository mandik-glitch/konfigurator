#!/opt/konfigurator/api/venv/bin/python
# -*- coding: utf-8 -*-
"""Vykresy stran SPOLECNE online nabidky (offer_options.vandr_drawings) PREZIJI uravy nabidky a jsou verejne - SKUTECNE endpointy scene_offers.py nad docasnymi tabulkami
(bot10, 2026-10-06; Robert: "v jedne online nabidce nabidnout dohromady levou stranu, i pravou stranu i prepazku").

Proc: `_sanitize_offer_options` propousti jen znamé klice (u Vandru jen vandr_single_drawing); bez doplneni by kazda uprava nabidky v adminu ("Upravit nabidku") nebo ulozeni rucni
ceny dopravy potichu smazala vandr_drawings a stranka by misto vykresu ke kazde strane ukazala jediny.

  _sanitize_offer_options          -> propusti jen u Vandr nabidky, 2-3 ruzne sloty, kratke popisky; neplatne = klic pryc cely
  PUT /api/admin/scene-offers/<id> -> vykresy se berou z ulozeneho radku (z tela se nastavit nedaji, uprava je nesmaze)
  PUT  /api/public/offers/<token>/manual-shipping (cesta, ktera uloz. volby znovu sanitizuje) -> vykresy zustanou
  GET  /api/public/offers/<token>  -> offer_options.vandr_drawings verejne, bez ID karet

Do ostrych dat se NEZAPISUJE: scene_offers a scene_offer_revisions jsou ve spojeni testu zastineny TEMPORARY tabulkami, audit je vypnuty, testovaci nabidky maji id 900301+; na konci se overi,
ze ostre tabulky jsou beze zmeny. Spusteni (DB prihlaseni pres systemd):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \\
    scripts/2026-10-02_v3d_testy/test_spolecna_nabidka_admin.py
Kandidat pred nasazenim: --setenv=SCENE_OFFERS_PY=/cesta/k/scene_offers.py"""
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

KRESBY2 = [{"slot": "narys", "label": "Levá strana"}, {"slot": "bokorys", "label": "Pravá strana"}]
KRESBY3 = KRESBY2 + [{"slot": "pudorys", "label": "Přepážka"}]
ITEMS = [{"name": "Regál levý (VD-aaa)", "qty": 1, "unit_price": 1000, "total": 1000}, {"name": "Regál pravý (VD-bbb)", "qty": 1, "unit_price": 2000, "total": 2000}]
ADMIN_TOKEN = "admin-tok-%d"


def vloz(id_, token, options, items=None, dni=5):
    with real.cursor() as cur:
        cur.execute("INSERT INTO scene_offers (id, offer_number, items, total_price, view_narys, view_bokorys, view_3d_a, view_3d_b, editable_text_popis, editable_text_patka, view_token_hash, "
                    "admin_view_token_hash, expires_at, is_active, offer_options, revision_number) VALUES (%s,%s,%s,%s,'x','x','x','x','','',%s,%s,%s,1,%s,1)",
                    (id_, "TESTSN%d" % id_, json.dumps(items or ITEMS, ensure_ascii=False), 3000, hashlib.sha256(token.encode()).hexdigest(),
                     hashlib.sha256((ADMIN_TOKEN % id_).encode()).hexdigest(), datetime.datetime.now() + datetime.timedelta(days=dni), json.dumps(options)))
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


def put(id_, options, items=None):
    return admin.put("/api/admin/scene-offers/%d" % id_, json={"items": items or ITEMS, "total_price": 3000, "editable_text": {"popis": "p", "patka": "f"}, "offer_options": options, "change_note": "test"})


# ------------------------------------------------------------------------------------------------------------------ S sanitizer
print("== S _sanitize_offer_options")
san = scene_offers._sanitize_offer_options
V = {"vandr_single_drawing": True}
over("S1 dva platne vykresy se propusti beze zmeny", san({**V, "vandr_drawings": KRESBY2}).get("vandr_drawings") == KRESBY2, san({**V, "vandr_drawings": KRESBY2}))
over("S2 tri platne vykresy se propusti", san({**V, "vandr_drawings": KRESBY3}).get("vandr_drawings") == KRESBY3, None)
over("S3 bez vandr_single_drawing se klic zahodi (nativni nabidka)", "vandr_drawings" not in san({"vandr_drawings": KRESBY2}), san({"vandr_drawings": KRESBY2}))
over("S4 vandr_single_drawing neni presne True (1, 'true') -> zahodit", all("vandr_drawings" not in san({"vandr_single_drawing": v, "vandr_drawings": KRESBY2}) for v in (1, "true", False, None)), None)
over("S5a JEDEN vykres je platny (strana bez Vandr vykresu se vynechava, bot5 2026-10-06)", san({**V, "vandr_drawings": KRESBY2[:1]}).get("vandr_drawings") == KRESBY2[:1], san({**V, "vandr_drawings": KRESBY2[:1]}))
spatne = {"ctyri": KRESBY3 + [{"slot": "narys", "label": "x"}], "prazdny": [], "neni seznam": "narys", "dict": {"slot": "narys"}, "None": None,
          "neznamy slot": [KRESBY2[0], {"slot": "../x", "label": "Pravá"}], "duplicitni slot": [KRESBY2[0], {"slot": "narys", "label": "Pravá"}],
          "bez popisku": [KRESBY2[0], {"slot": "bokorys"}], "prazdny popisek": [KRESBY2[0], {"slot": "bokorys", "label": "  "}], "popisek ne text": [KRESBY2[0], {"slot": "bokorys", "label": 5}],
          "polozka neni dict": [KRESBY2[0], "bokorys"], "jedna vadna ze tri": [KRESBY2[0], KRESBY2[1], {"slot": "x", "label": "y"}]}
for nazev, hodnota in spatne.items():
    over("S5 %s -> klic pryc cely (zadny neuplny seznam)" % nazev, "vandr_drawings" not in san({**V, "vandr_drawings": hodnota}), san({**V, "vandr_drawings": hodnota}))
dlouhy = san({**V, "vandr_drawings": [{"slot": "narys", "label": "  " + "A" * 100 + "  "}, KRESBY2[1]]}).get("vandr_drawings") or [None, None]
over("S6 popisek se oreze (strip + 40 znaku), slot zustane", dlouhy[0] == {"slot": "narys", "label": "A" * 40} and dlouhy[1] == KRESBY2[1], dlouhy)
over("S7 vstupni objekt se nemeni a vystup nesdili seznam se vstupem", (lambda i: (san(i), i["vandr_drawings"] == KRESBY2 and san(i).get("vandr_drawings") is not i["vandr_drawings"])[1])({**V, "vandr_drawings": [dict(d) for d in KRESBY2]}), None)
over("S8 vychozi volby (OFFER_OPTIONS_DEFAULT) vandr_drawings nemaji", "vandr_drawings" not in scene_offers.OFFER_OPTIONS_DEFAULT, scene_offers.OFFER_OPTIONS_DEFAULT)

# ------------------------------------------------------------------------------------------------------------------ P admin PUT
print("== P PUT /api/admin/scene-offers/<id> (Upravit nabidku)")
P1, P2, P3, P4 = 900301, 900302, 900303, 900304
SPOL = {"show_qr": True, "vandr_single_drawing": True, "vandr_drawings": KRESBY3, "hidden_payment_method": "dobirka"}
vloz(P1, "tok-p1", SPOL)
r = put(P1, {"show_qr": True})
over("P1 uprava nabidky bez klice vandr_drawings v tele: 200", r.status_code == 200, (r.status_code, r.get_data(as_text=True)[:200]))
o = ulozene_volby(P1)
over("P2 vykresy stran i priznak Vandr nabidky zustaly (3 sloty, popisky)", o.get("vandr_drawings") == KRESBY3 and o.get("vandr_single_drawing") is True, o)
vloz(P2, "tok-p2", SPOL)
r = put(P2, {"show_qr": True, "vandr_single_drawing": True, "vandr_drawings": [{"slot": "pudorys", "label": "Podvrzeno"}, {"slot": "narys", "label": "Podvrzeno 2"}]})
o = ulozene_volby(P2)
over("P3 z tela pozadavku se vykresy nastavit nedaji: zustavaji ulozene", r.status_code == 200 and o.get("vandr_drawings") == KRESBY3, (r.status_code, o))
vloz(P3, "tok-p3", {"show_qr": True})
r = put(P3, {"show_qr": True, "vandr_single_drawing": True, "vandr_drawings": KRESBY2})
o = ulozene_volby(P3)
over("P4 nabidka bez vykresu v radku: z tela se nezapne ani vandr_single_drawing, ani vandr_drawings", r.status_code == 200 and "vandr_drawings" not in o and "vandr_single_drawing" not in o, (r.status_code, o))
vloz(P4, "tok-p4", {"show_qr": True, "vandr_single_drawing": True, "vandr_drawings": [{"slot": "narys", "label": "Jediny"}]})
r = put(P4, {"show_qr": True})
o = ulozene_volby(P4)
over("P5 ulozeny JEDEN vykres (strana bez Vandr vykresu vynechana) se pri uprave zachova", r.status_code == 200 and o.get("vandr_drawings") == [{"slot": "narys", "label": "Jediny"}] and o.get("vandr_single_drawing") is True, (r.status_code, o))
P5 = 900320
vloz(P5, "tok-p5", {"show_qr": True, "vandr_single_drawing": True, "vandr_drawings": [{"slot": "narys", "label": "A"}, {"slot": "narys", "label": "B"}]})
r = put(P5, {"show_qr": True})
o = ulozene_volby(P5)
over("P5b neplatne ulozene vykresy (duplicitni slot) se pri uprave zahodi, priznak Vandr zustane", r.status_code == 200 and "vandr_drawings" not in o and o.get("vandr_single_drawing") is True, (r.status_code, o))
# Vandr nabidka BEZ 2D vykresu (bot5, 2026-10-06): priznak vandr_bez_vykresu jen z ulozeneho radku
BV = 900321
vloz(BV, "tok-bv", {"show_qr": True, "vandr_single_drawing": True, "vandr_bez_vykresu": True})
r = put(BV, {"show_qr": True, "delivery_term": "do 10 dnu"})
o = ulozene_volby(BV)
over("P7 uprava Vandr nabidky bez vykresu: priznak vandr_bez_vykresu i vandr_single_drawing zustaly, zmena jine volby ulozena", r.status_code == 200 and o.get("vandr_bez_vykresu") is True and o.get("vandr_single_drawing") is True and o.get("delivery_term") == "do 10 dnu", (r.status_code, o))
BV2 = 900322
vloz(BV2, "tok-bv2", {"show_qr": True, "vandr_single_drawing": True})
r = put(BV2, {"show_qr": True, "vandr_single_drawing": True, "vandr_bez_vykresu": True})
o = ulozene_volby(BV2)
over("P8 z tela pozadavku se vandr_bez_vykresu NEDA zapnout (jen ulozeny radek)", r.status_code == 200 and "vandr_bez_vykresu" not in o and o.get("vandr_single_drawing") is True, (r.status_code, o))
BV3 = 900323
vloz(BV3, "tok-bv3", {"show_qr": True, "vandr_bez_vykresu": True})
r = put(BV3, {"show_qr": True})
o = ulozene_volby(BV3)
over("P9 priznak vandr_bez_vykresu bez vandr_single_drawing (nativni nabidka) se zahodi", r.status_code == 200 and "vandr_bez_vykresu" not in o, (r.status_code, o))
over("P10 sanitizer: vandr_bez_vykresu jen u vandr_single_drawing True; s vandr_drawings se vylucuje", san({"vandr_single_drawing": True, "vandr_bez_vykresu": True}).get("vandr_bez_vykresu") is True and "vandr_bez_vykresu" not in san({"vandr_bez_vykresu": True})
     and "vandr_drawings" not in san({"vandr_single_drawing": True, "vandr_bez_vykresu": True, "vandr_drawings": KRESBY2}) and "vandr_bez_vykresu" not in san({"vandr_single_drawing": True, "vandr_bez_vykresu": 1}), None)
r = put(P1, {"show_qr": True, "delivery_term": "do 14 dnu"})
o = ulozene_volby(P1)
over("P6 dalsi uprava (zmena jine volby) vykresy znovu nesmaze a zmenu jine volby ulozi", r.status_code == 200 and o.get("vandr_drawings") == KRESBY3 and o.get("delivery_term") == "do 14 dnu", o)

# ------------------------------------------------------------------------------------------------------------------ M rucni cena dopravy (ulozene volby se znovu sanitizuji)
print("== M ulozene volby se znovu sanitizuji (rucni cena dopravy)")
M1 = 900305
vloz(M1, "tok-m1", SPOL)
r = anon.put("/api/public/offers/%s/manual-shipping" % (ADMIN_TOKEN % M1), json={"manual_assembled_shipping_czk": 1500})
o = ulozene_volby(M1)
over("M1 ulozeni rucni ceny dopravy: 200, cena ulozena a vykresy stran zustaly", r.status_code == 200 and o.get("manual_assembled_shipping_czk") == 1500 and o.get("vandr_drawings") == KRESBY3
     and o.get("vandr_single_drawing") is True, (r.status_code, r.get_data(as_text=True)[:200], o))

# ------------------------------------------------------------------------------------------------------------------ R verejne JSON
print("== R GET /api/public/offers/<token>")
R1 = 900306
vloz(R1, "tok-r1", SPOL)
r = anon.get("/api/public/offers/tok-r1")
j = r.get_json() or {}
oo = j.get("offer_options") or {}
over("R1 verejne JSON nese offer_options.vandr_drawings + vandr_single_drawing", r.status_code == 200 and oo.get("vandr_drawings") == KRESBY3 and oo.get("vandr_single_drawing") is True, (r.status_code, oo))
BV4 = 900324
vloz(BV4, "tok-bv4", {"show_qr": True, "vandr_single_drawing": True, "vandr_bez_vykresu": True})
oo4 = ((anon.get("/api/public/offers/tok-bv4").get_json()) or {}).get("offer_options") or {}
over("R1b verejne JSON nese vandr_bez_vykresu (stranka podle nej vynecha Vykresy) a montaz_volba / auto priznak Vandr nabidky", oo4.get("vandr_bez_vykresu") is True and oo4.get("is_vehicle_assembly") is True, oo4)
over("R2 verejne JSON neprozradi ID karet", "vandr_cards" not in oo and "vandr_cards" not in json.dumps(j), None)
for k, slot in (("narys", "narys"), ("bokorys", "bokorys")):
    over("R3 obrazek %s existuje v seznamu verejnych klicu (OFFER_VIEW_KEYS)" % k, slot in scene_offers.OFFER_VIEW_KEYS, list(scene_offers.OFFER_VIEW_KEYS))
over("R4 pudorys je ve verejnych klicich", "pudorys" in scene_offers.OFFER_VIEW_KEYS, None)

# ------------------------------------------------------------------------------------------------------------------ konec: ostre tabulky beze zmeny
po = stav_ostrych()
over("Z ostre tabulky scene_offers / scene_offer_revisions / audit_log beze zmeny", po == pred, (pred, po))
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
