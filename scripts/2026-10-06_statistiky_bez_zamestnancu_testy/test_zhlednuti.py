#!/opt/konfigurator/api/venv/bin/python
"""Zobrazeni nabidky ZAMESTNANCEM se nepocita do statistik (bot5, 2026-10-06, Robert: "nemuze to pocitat moje pristupy, to se musi hlidat"): SKUTECNY endpoint
POST /api/public/offers/<token>/view (+ /event, statistiky v adminu) nad DOCASNYMI tabulkami (scene_offers, scene_offer_views, scene_offer_page_events); ostre se nemeni.
Zamestnanec = admin odkaz "Zobrazit online" (admin_view_token_hash) NEBO prihlaseny v adminu (session, role z PERMISSION_ROLES, aktivni). Zakaznik (anonym, neprihlaseny, ucet bez role zamestnance) se pocita jako dosud.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env [--setenv=SCENE_OFFERS_PY=<kandidat>] --working-directory=/opt/konfigurator \
          /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-06_statistiky_bez_zamestnancu_testy/test_zhlednuti.py"""
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


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in ("scene_offers", "scene_offer_views", "scene_offer_page_events"):
                cur.execute("SELECT COUNT(*) AS n, COALESCE(MAX(id),0) AS m FROM `%s`" % t)
                r = cur.fetchone()
                out[t] = (r["n"], r["m"])
            return out
    finally:
        c.close()


pred = stav_ostrych()
conn = appmod.get_conn()
real = object.__getattribute__(conn, "_real")
TABULKY = ("scene_offers", "scene_offer_views", "scene_offer_page_events")
with real.cursor() as cur:
    for t in TABULKY:
        cur.execute("CREATE TEMPORARY TABLE `_tpl_%s` LIKE `%s`" % (t, t))
        cur.execute("CREATE TEMPORARY TABLE `%s` LIKE `_tpl_%s`" % (t, t))
    # FK z docasne tabulky na ostre tabulky se pri LIKE nekopiruje; kdyby ano, test by spadl pri vkladu a skoncil bez zapisu
    cur.execute("SELECT id, role FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
    ADMIN = cur.fetchone()["id"]
    PERM = tuple(appmod.PERMISSION_ROLES)
    cur.execute("SELECT id, role FROM app_users WHERE COALESCE(active,1)=1 AND role NOT IN (%s) ORDER BY id LIMIT 1" % ",".join(["%s"] * len(PERM)), PERM)
    ZAKAZNIK = (cur.fetchone() or {}).get("id")
    cur.execute("SELECT id FROM app_users WHERE COALESCE(active,1)=0 AND role IN (%s) ORDER BY id LIMIT 1" % ",".join(["%s"] * len(PERM)), PERM)
    NEAKTIVNI = (cur.fetchone() or {}).get("id")
real.commit()

NOW = datetime.datetime.now()
CUST, ADM = "tok-klient", "tok-admin"
with real.cursor() as cur:
    cur.execute("INSERT INTO scene_offers (id, offer_number, items, total_price, view_narys, view_bokorys, view_3d_a, view_3d_b, editable_text_popis, editable_text_patka, view_token_hash, "
                "admin_view_token_hash, expires_at, is_active, offer_options, revision_number) VALUES (920001,'TESTZH1','[]',1000,'x','x','x','x','','',%s,%s,%s,1,'{}',1)",
                (hashlib.sha256(CUST.encode()).hexdigest(), hashlib.sha256(ADM.encode()).hexdigest(), NOW + datetime.timedelta(days=5)))
real.commit()


def klient(user_id=None, ip="198.51.100.7"):
    c = appmod.app.test_client()
    if user_id:
        with c.session_transaction() as s:
            s["user_id"] = user_id
    c.environ_base["HTTP_X_REAL_IP"] = ip
    return c


def pocet(tabulka="scene_offer_views"):
    with real.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM `%s`" % tabulka)
        n = cur.fetchone()["n"]
    real.commit()
    return n


def view(c, token=CUST):
    appmod._rate_limit_buckets.clear()
    return c.post("/api/public/offers/%s/view" % token)


print("== Z zobrazeni zamestnance se nepocita")
n0 = pocet()
r = view(klient())
j = r.get_json() or {}
over("Z1 anonymni zakaznik (klientsky odkaz): 201, view_id cislo, radek v zhlednutich +1", r.status_code == 201 and isinstance(j.get("view_id"), int) and pocet() == n0 + 1, (r.status_code, j, pocet()))
vid = j.get("view_id")
n1 = pocet()
r = view(klient(ADMIN))
j2 = r.get_json() or {}
over("Z2 prihlaseny zamestnanec (admin) na KLIENTSKEM odkazu: 200, view_id null, nic se nezapsalo", r.status_code == 200 and j2.get("view_id") is None and j2.get("pocitano") is False and pocet() == n1, (r.status_code, j2, pocet(), n1))
r = view(klient(), ADM)
j3 = r.get_json() or {}
over("Z3 admin odkaz 'Zobrazit online' (i bez prihlaseni): 200, view_id null, nic se nezapsalo", r.status_code == 200 and j3.get("view_id") is None and pocet() == n1, (r.status_code, j3, pocet()))
r = view(klient(ADMIN), ADM)
over("Z4 admin odkaz + prihlaseny: view_id null, nic se nezapsalo", r.status_code == 200 and (r.get_json() or {}).get("view_id") is None and pocet() == n1, (r.status_code, pocet()))
if ZAKAZNIK:
    r = view(klient(ZAKAZNIK))
    over("Z5 prihlaseny ucet BEZ role zamestnance (zakaznik) se pocita jako dosud", r.status_code == 201 and isinstance((r.get_json() or {}).get("view_id"), int) and pocet() == n1 + 1, (r.status_code, pocet()))
else:
    over("Z5 (PRESKOCENO: v databazi neni ucet bez role zamestnance)", True)
n2 = pocet()
if NEAKTIVNI:
    r = view(klient(NEAKTIVNI))
    over("Z6 NEAKTIVNI zamestnanec (zablokovany ucet) se pocita jako navstevnik: 201, radek +1", r.status_code == 201 and pocet() == n2 + 1, (r.status_code, pocet(), n2))
else:
    over("Z6 (PRESKOCENO: neni neaktivni zamestnanec)", True)
r = view(klient(), "neznamy-token")
over("Z7 neplatny token: 404 jako dosud", r.status_code == 404, r.status_code)
n3 = pocet()
c_ev = klient()
appmod._rate_limit_buckets.clear()
r = c_ev.post("/api/public/offers/%s/event" % CUST, json={"view_id": vid, "page_index": 0, "page_key": "cover", "dwell_ms": 1500, "event_type": "page_view"})
over("Z8 udalosti zakaznikova zhlednuti se zapisuji dal (201)", r.status_code == 201 and pocet("scene_offer_page_events") == 1, (r.status_code, r.get_data(as_text=True)[:120]))
r = c_ev.post("/api/public/offers/%s/event" % CUST, json={"view_id": None, "page_index": 0, "page_key": "cover", "dwell_ms": 1500, "event_type": "page_view"})
over("Z9 udalost bez view_id (zamestnanec se starou/obchazenou strankou): 400 a nic se nezapise", r.status_code == 400 and pocet("scene_offer_page_events") == 1, (r.status_code, pocet("scene_offer_page_events")))
st = klient(ADMIN).get("/api/admin/scene-offers/920001/stats")
sj = st.get_json() or {}
by_ip = {x["ip_address"]: x["visits"] for x in (sj.get("by_ip") or [])}
ocek = 1 + (1 if ZAKAZNIK else 0) + (1 if NEAKTIVNI else 0)          # zakaznik Z1, ucet bez role Z5, neaktivni Z6; zamestnanec (Z2-Z4) tam NENI
over("Z10 statistika v adminu 'Shlednuti podle IP': stejna IP, ze ktere ale zamestnanec 3x otevrel nabidku, ma jen zhlednuti zakazniku (%d), ne zamestnance" % ocek, st.status_code == 200 and by_ip == {"198.51.100.7": ocek}, (st.status_code, by_ip))
with open(os.path.join(HERE, "..", "..", "webapp", "nabidka-online.html"), encoding="utf-8") as f:
    html = f.read()
over("Z11 stranka nabidky posila udalosti jen s view_id (null od serveru = nic nesleduje)", "if (!viewId || pageIndex < 0 || pageIndex >= PAGES.length) return;" in html and "if (data) viewId = data.view_id;" in html, None)

po = stav_ostrych()
over("Z ostre tabulky scene_offers / scene_offer_views / scene_offer_page_events beze zmeny", po == pred, (pred, po))
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
