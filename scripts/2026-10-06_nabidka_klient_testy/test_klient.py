#!/opt/konfigurator/api/venv/bin/python
"""Jmeno klienta v online nabidce se da doplnit dodatecne (bot5, 2026-10-06, Robert: "chci mit moznost doplnit nazev klienta dodatecne v online nabidce"): SKUTECNE endpointy
scene_offers.py (GET .../edit-data, PUT .../scene-offers/<id>, verejny GET, seznam nabidek) nad DOCASNYMI tabulkami (ostre scene_offers / scene_offer_revisions se nemeni).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env [--setenv=SCENE_OFFERS_PY=<kandidat> --setenv=ADMIN_HTML=<kandidat> --setenv=CRM_NABIDKY_JS=<kandidat>] --working-directory=/opt/konfigurator \
          /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-06_nabidka_klient_testy/test_klient.py"""
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
            for t in ("scene_offers", "scene_offer_revisions"):
                cur.execute("SELECT COUNT(*) AS n, COALESCE(MAX(id),0) AS m, COALESCE(SUM(CRC32(COALESCE(customer_name,''))),0) AS h FROM `%s`" % t if t == "scene_offers"
                            else "SELECT COUNT(*) AS n, COALESCE(MAX(id),0) AS m, 0 AS h FROM `%s`" % t)
                r = cur.fetchone()
                out[t] = (r["n"], r["m"], int(r["h"]))
            return out
    finally:
        c.close()


pred = stav_ostrych()
conn = appmod.get_conn()
real = object.__getattribute__(conn, "_real")
with real.cursor() as cur:
    for t in ("scene_offers", "scene_offer_revisions"):
        cur.execute("CREATE TEMPORARY TABLE `_tpl_%s` LIKE `%s`" % (t, t))
        cur.execute("CREATE TEMPORARY TABLE `%s` LIKE `_tpl_%s`" % (t, t))
        cur.execute("SELECT COUNT(*) AS n FROM `%s`" % t)
        if cur.fetchone()["n"] != 0:
            raise SystemExit("ABORT: docasna tabulka %s neni prazdna" % t)
    cur.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
    ADMIN = cur.fetchone()["id"]
real.commit()
AUDIT = []
scene_offers.log_audit = lambda *a, **k: AUDIT.append(a)

ITEMS = [{"name": "Regal (VD-aaa)", "qty": 1, "unit_price": 1000, "total": 1000}]


def vloz(id_, token, jmeno=None):
    with real.cursor() as cur:
        cur.execute("INSERT INTO scene_offers (id, offer_number, customer_name, items, total_price, view_narys, view_bokorys, view_3d_a, view_3d_b, editable_text_popis, editable_text_patka, "
                    "view_token_hash, admin_view_token_hash, expires_at, is_active, offer_options, revision_number) VALUES (%s,%s,%s,%s,%s,'x','x','x','x','','',%s,%s,%s,1,%s,1)",
                    (id_, "TESTKL%d" % id_, jmeno, json.dumps(ITEMS), 1000, hashlib.sha256(token.encode()).hexdigest(), hashlib.sha256(("a" + token).encode()).hexdigest(),
                     datetime.datetime.now() + datetime.timedelta(days=5), json.dumps({"show_qr": True})))
    real.commit()


def radek(id_):
    with real.cursor() as cur:
        cur.execute("SELECT customer_name, revision_number FROM scene_offers WHERE id=%s", (id_,))
        r = cur.fetchone()
    real.commit()
    return r


admin = appmod.app.test_client()
with admin.session_transaction() as s:
    s["user_id"] = ADMIN
anon = appmod.app.test_client()


def put(id_, **pole):
    body = {"items": ITEMS, "total_price": 1000, "editable_text": {"popis": "p", "patka": "f"}, "offer_options": {"show_qr": True}, "change_note": "t"}
    body.update(pole)
    return admin.put("/api/admin/scene-offers/%d" % id_, json=body)


A, B, C, D = 910001, 910002, 910003, 910004
vloz(A, "tok-a")
vloz(B, "tok-b", "Starý klient s.r.o.")
vloz(C, "tok-c", "Zachovat s.r.o.")
vloz(D, "tok-d")

print("== K jmeno klienta dodatecne")
ed = admin.get("/api/admin/scene-offers/%d/edit-data" % A).get_json()
over("K1 edit-data nese customer_name (u nabidky bez klienta null)", "customer_name" in ed and ed["customer_name"] is None, ed.keys())
r = put(A, customer_name="  Novák s.r.o.  ")
over("K2 PUT s customer_name: 200, jmeno ulozeno bez okolnich mezer, revize +1", r.status_code == 200 and radek(A) == {"customer_name": "Novák s.r.o.", "revision_number": 2}, (r.status_code, radek(A), r.get_data(as_text=True)[:150]))
ed = admin.get("/api/admin/scene-offers/%d/edit-data" % A).get_json()
over("K3 edit-data vraci ulozene jmeno", ed["customer_name"] == "Novák s.r.o.", ed.get("customer_name"))
pub = anon.get("/api/public/offers/tok-a").get_json() or {}
over("K4 verejny JSON nabidky nese jmeno klienta (titulni strana ho ukaze)", pub.get("customer_name") == "Novák s.r.o.", pub.get("customer_name"))
lst = admin.get("/api/admin/scene-offers?q=Nov%C3%A1k")
polozky = (lst.get_json() or {}).get("offers") if lst.status_code == 200 else None
over("K5 seznam nabidek v adminu jmeno ukaze a da se podle nej hledat", lst.status_code == 200 and any(o.get("customer_name") == "Novák s.r.o." for o in (polozky or [])), (lst.status_code, str(lst.get_data(as_text=True))[:200]))
r = put(B, customer_name="Nový klient a.s.")
over("K6 prepsani existujiciho jmena", r.status_code == 200 and radek(B)["customer_name"] == "Nový klient a.s.", (r.status_code, radek(B)))
r = put(C)
over("K7 klic customer_name v tele CHYBI (starsi admin.html): jmeno zustane, uprava probehne", r.status_code == 200 and radek(C)["customer_name"] == "Zachovat s.r.o." and radek(C)["revision_number"] == 2, (r.status_code, radek(C)))
r = put(B, customer_name="")
over("K8 prazdne jmeno = smazat (NULL)", r.status_code == 200 and radek(B)["customer_name"] is None, (r.status_code, radek(B)))
r = put(B, customer_name=None)
over("K9 null = bez jmena (NULL), 200", r.status_code == 200 and radek(B)["customer_name"] is None, (r.status_code, radek(B)))
r = put(D, customer_name="x" * 256)
over("K10 jmeno delsi nez 255 znaku = 400, nic se nezmeni (ani revize)", r.status_code == 400 and radek(D) == {"customer_name": None, "revision_number": 1}, (r.status_code, radek(D)))
r = put(D, customer_name=12345)
over("K11 jmeno, ktere neni text = 400", r.status_code == 400 and radek(D)["revision_number"] == 1, (r.status_code, radek(D)))
r = put(D, customer_name="y" * 255)
over("K12 presne 255 znaku projde", r.status_code == 200 and radek(D)["customer_name"] == "y" * 255, (r.status_code, len(radek(D)["customer_name"] or "")))
vloz(910005, "tok-e", "<b>Evil</b> \"klient\" & spol.")
over("K13 jmeno se na verejne strance nedava jako HTML (JSON ho vraci jako text; stranka ho escapuje)", (anon.get("/api/public/offers/tok-e").get_json() or {}).get("customer_name") == "<b>Evil</b> \"klient\" & spol.", None)
over("K14 audit zaznam nese zmenu klienta (stary -> novy)", any("klient:" in str(a[-1]) and "Novák s.r.o." in str(a[-1]) for a in AUDIT), AUDIT[:3])
r = anon.put("/api/admin/scene-offers/%d" % A, json={"items": ITEMS, "total_price": 1000, "customer_name": "Hacker"})
over("K15 bez prihlaseni nejde (401/403) a jmeno se nezmeni", r.status_code in (401, 403) and radek(A)["customer_name"] == "Novák s.r.o.", (r.status_code, radek(A)))
with open(os.environ.get("ADMIN_HTML") or os.path.join(HERE, "..", "..", "webapp", "admin.html"), encoding="utf-8") as f:
    html = f.read()
with open(os.environ.get("CRM_NABIDKY_JS") or os.path.join(HERE, "..", "..", "webapp", "admin", "js", "crm-nabidky.js"), encoding="utf-8") as f:
    js = f.read()
over("K16 admin formular ma pole Klient (offerEditCustomerName), nacita ho z edit-data a posila customer_name", 'id="offerEditCustomerName"' in html and 'data.customer_name' in js and "customer_name: document.getElementById(\"offerEditCustomerName\").value" in js, None)

po = stav_ostrych()
over("Z ostre tabulky scene_offers / scene_offer_revisions beze zmeny", po == pred, (pred, po))
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
