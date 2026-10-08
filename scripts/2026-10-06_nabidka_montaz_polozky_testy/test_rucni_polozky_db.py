#!/opt/konfigurator/api/venv/bin/python
"""RUCNI POLOZKY v online nabidce - SKUTECNE endpointy (Flask test client) nad docasnymi tabulkami (bot8, 2026-10-06; Robert: admin pripise do nabidky polozku z katalogu s 3D modelem /
volny text s 1-2 obrazky a cenou).

  PUT  /api/admin/scene-offers/<id>                       -> rucni polozky se overi a jdou na konec; obycejne radky se nesmi pridat / smazat / prejmenovat; revize +1
  POST /api/admin/scene-offers/<id>/item-images           -> nahrani obrazku (jen skutecny png / jpeg, strop velikosti a poctu, jen pro existujici nabidku, jen s pravem)
  GET  /api/admin/scene-offers/<id>/item-images/<key>     -> nahled v adminu (jen vlastni klic nabidky)
  GET  /api/admin/scene-offers/<id>/edit-data             -> priznak `rucni_polozky` (admin formular podle nej ukaze tlacitka)
  GET  /api/public/offers/<token>/item-image/<key>        -> jen kdyz ho nabidka (items) odkazuje, jen za spravnym tokenem, aktivni nabidka
  GET  /api/public/offers/<token>/item-model/<product_id> -> GLB z katalogu jen kdyz nabidka obsahuje polozku s timto produktem a manual.model; ETag / 304

Do ostrych dat se NEZAPISUJE: scene_offers a scene_offer_revisions jsou ve spojeni testu zastineny TEMPORARY tabulkami (struktura bez cizich klicu), obrazky jdou do docasne slozky,
audit_log je vypnuty (scene_offers.log_audit), testovaci nabidky maji id 900101+; na konci se overi, ze ostre tabulky jsou beze zmeny. Katalog (shop_products, GLB) se jen CTE.
Spusteni (DB prihlaseni pres systemd):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \\
    scripts/2026-10-06_nabidka_montaz_polozky_testy/test_rucni_polozky_db.py
Kandidat pred nasazenim: --setenv=SCENE_OFFERS_PY=/cesta/k/scene_offers.py
"""
import base64
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
    tmp_kand = tempfile.mkdtemp(prefix="kand_scene_offers_")
    shutil.copy(SO, os.path.join(tmp_kand, "scene_offers.py"))
    sys.path.insert(0, tmp_kand)
sys.path.insert(1 if SO else 0, API)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import scene_offers  # noqa: E402

if SO:
    assert os.path.abspath(scene_offers.__file__).startswith(os.path.abspath(tmp_kand)), f"nacetl se jiny scene_offers.py: {scene_offers.__file__}"

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
                cur.execute(f"SELECT COUNT(*) AS n, COALESCE(MAX(id),0) AS m FROM `{t}`")
                r = cur.fetchone()
                out[t] = (r["n"], r["m"])
            return out
    finally:
        c.close()


pred = stav_ostrych()
over("0 ostre ID nabidek jsou pod 900000", pred["scene_offers"][1] < 900000, pred)

# ---- docasne tabulky + docasna slozka obrazku + vypnuty audit
conn = appmod.get_conn()
real = object.__getattribute__(conn, "_real")
with real.cursor() as cur:
    for t in ("scene_offers", "scene_offer_revisions"):
        cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
        cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
        cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
        if cur.fetchone()["n"] != 0:
            raise SystemExit(f"ABORT: docasna tabulka {t} neni prazdna - nestini ostrou, koncim bez zapisu")
    cur.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
    ADMIN = cur.fetchone()["id"]
    cur.execute("SELECT id, role FROM app_users WHERE role<>'admin' AND COALESCE(active, 1)=1 ORDER BY id")
    JINI = cur.fetchall()
    cur.execute("SELECT id FROM shop_products WHERE glb_file IS NOT NULL AND is_archived=0 ORDER BY id LIMIT 1")
    P_GLB = cur.fetchone()["id"]
    cur.execute("SELECT id FROM shop_products WHERE glb_file IS NULL AND is_archived=0 ORDER BY id LIMIT 1")
    P_BEZ = cur.fetchone()["id"]
    cur.execute("SELECT id FROM shop_products WHERE glb_file IS NOT NULL AND is_archived=0 AND id<>%s ORDER BY id LIMIT 1", (P_GLB,))
    P_GLB2 = cur.fetchone()["id"]
real.commit()
OBR_DIR = tempfile.mkdtemp(prefix="test_rucni_obr_")
scene_offers.OFFER_IMAGES_DIR = OBR_DIR
scene_offers.log_audit = lambda *a, **k: None

# ---- testovaci nabidky
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 40
DU_PNG = "data:image/png;base64," + base64.b64encode(PNG).decode()
DU_JPG = "data:image/jpeg;base64," + base64.b64encode(JPG).decode()
REG = [{"name": "Řádek konfigurace stolu", "dim": "-", "qty": "1 ks", "unit_price": 20000, "total": 20000, "configuration_code": "STL-ABCDEF"},
       {"name": "Profil 40x40mm", "dim": "1000 mm", "qty": "4 ks", "unit_price": 350, "total": 1400, "mesh_group": 1, "product_id": 3468}]


def vloz(id_, token, items, aktivni=1, dni=5):
    with real.cursor() as cur:
        cur.execute("INSERT INTO scene_offers (id, offer_number, items, total_price, view_narys, view_3d_a, view_3d_b, editable_text_popis, editable_text_patka, view_token_hash, "
                    "expires_at, is_active, offer_options, revision_number) VALUES (%s,%s,%s,%s,'x','x','x','','',%s,%s,%s,%s,1)",
                    (id_, f"TESTRP{id_}", json.dumps(items, ensure_ascii=False), 21400, hashlib.sha256(token.encode()).hexdigest(),
                     datetime.datetime.now() + datetime.timedelta(days=dni), aktivni, json.dumps({"show_qr": True})))
    real.commit()


A, B = 900101, 900102
vloz(A, "tok-a", REG)
vloz(B, "tok-b", REG)
admin = appmod.app.test_client()
with admin.session_transaction() as s:
    s["user_id"] = ADMIN
anon = appmod.app.test_client()


def ulozene(id_):
    with real.cursor() as cur:
        cur.execute("SELECT items, total_price, revision_number FROM scene_offers WHERE id=%s", (id_,))
        r = cur.fetchone()
    real.commit()
    return json.loads(r["items"]), r["total_price"], r["revision_number"]


def revizi(id_):
    with real.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM scene_offer_revisions WHERE offer_id=%s", (id_,))
        n = cur.fetchone()["n"]
    real.commit()
    return n


def put(id_, items, total=None, klient=None):
    return (klient or admin).put(f"/api/admin/scene-offers/{id_}", json={"items": items, "total_price": 21400 if total is None else total, "editable_text": {"popis": "p", "patka": "f"},
                                                                          "offer_options": {"show_qr": True}, "change_note": "test"})


def nahraj(id_, uri=DU_PNG, klient=None):
    return (klient or admin).post(f"/api/admin/scene-offers/{id_}/item-images", json={"image": uri})


# ------------------------------------------------------------------------------------------------------------------ A
print("== A edit-data a nahravani obrazku")
r = admin.get(f"/api/admin/scene-offers/{A}/edit-data")
over("A1 edit-data nese priznak rucni_polozky (max 20 polozek, 2 obrazky)", r.status_code == 200 and r.get_json().get("rucni_polozky") == {"max": 20, "obrazky_max": 2}, r.get_json())
r = nahraj(A)
j = r.get_json() or {}
over("A2 nahrani PNG: 201, klic polozka_<id>_<16 hex>.png, soubor ve slozce", r.status_code == 201 and scene_offers.MANUAL_IMAGE_KEY_RE.match(j.get("key", "")) and j["key"].endswith(".png")
     and os.path.isfile(os.path.join(OBR_DIR, j["key"])) and f"/{A}/item-images/{j['key']}" in j["url"], (r.status_code, j))
K1 = j.get("key")
r = nahraj(A, DU_JPG)
j2 = r.get_json() or {}
over("A3 nahrani JPEG: 201, pripona .jpg", r.status_code == 201 and j2["key"].endswith(".jpg"), (r.status_code, j2))
K2 = j2.get("key")
r = admin.get(j["url"])
over("A4 nahled v adminu: 200 image/png s nosniff", r.status_code == 200 and r.mimetype == "image/png" and r.data == PNG and r.headers.get("X-Content-Type-Options") == "nosniff", (r.status_code, r.mimetype))
over("A5 nahled jine nabidky se stejnym klicem: 404 (klic patri nabidce A)", admin.get(f"/api/admin/scene-offers/{B}/item-images/{K1}").status_code == 404, None)
over("A6 neplatne klice (../, jiny format, prazdny): 404", all(admin.get(f"/api/admin/scene-offers/{A}/item-images/{k}").status_code == 404 for k in ("..%2Fapp.py", "polozka_900101_zzzz.png", "render.png", "polozka_900101_0123456789abcdef.gif")), None)
for popis, uri in (("text misto obrazku", "ahoj"), ("PNG s JPEG hlavickou", "data:image/png;base64," + base64.b64encode(JPG).decode()), ("JPEG s PNG hlavickou", "data:image/jpeg;base64," + base64.b64encode(PNG).decode()),
                   ("gif", "data:image/gif;base64," + base64.b64encode(b"GIF89a").decode()), ("neplatny base64", "data:image/png;base64,@@@"),
                   ("nad 6 MB", "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * (6 * 1024 * 1024 + 10)).decode())):
    r = nahraj(A, uri)
    over(f"A7 {popis}: odmitnuto (400 / 413), nic se neulozi", r.status_code in (400, 413), r.status_code)
pocet_souboru = len(os.listdir(OBR_DIR))
over("A8 po odmitnutych nahranich zustaly jen 2 soubory", pocet_souboru == 2, pocet_souboru)
over("A9 nahrani k neexistujici nabidce: 404", nahraj(999999).status_code == 404, None)
over("A10 bez prihlaseni: 401, nic se neulozi", anon.post(f"/api/admin/scene-offers/{A}/item-images", json={"image": DU_PNG}).status_code == 401 and len(os.listdir(OBR_DIR)) == 2, None)
nenalezen = False
for u in JINI:
    k = appmod.app.test_client()
    with k.session_transaction() as s:
        s["user_id"] = u["id"]
    if nahraj(A, klient=k).status_code == 403:
        nenalezen = True
        over(f"A11 uzivatel role {u['role']} bez prava nabidky/upravit: 403 a soubor se neulozi", len(os.listdir(OBR_DIR)) == 2, len(os.listdir(OBR_DIR)))
        break
    for n in os.listdir(OBR_DIR):                         # ten uzivatel pravo ma - uklid jeho souboru, hledame dalsiho
        if n not in (K1, K2):
            os.remove(os.path.join(OBR_DIR, n))
if not nenalezen:
    print("  (v DB neni aktivni uzivatel bez prava nabidky/upravit - kontrola 403 preskocena)")
# strop poctu souboru u jedne nabidky
for i in range(scene_offers.MANUAL_IMAGES_PER_OFFER_MAX):
    open(os.path.join(OBR_DIR, f"polozka_{B}_{i:016x}.png"), "wb").write(PNG)
r = nahraj(B)
over(f"A12 strop {scene_offers.MANUAL_IMAGES_PER_OFFER_MAX} nahranych obrazku u jedne nabidky: dalsi se odmitne (400), jina nabidka (A) neni dotcena",
     r.status_code == 400 and nahraj(A).status_code == 201, r.status_code)
for n in [n for n in os.listdir(OBR_DIR) if n.startswith(f"polozka_{B}_")]:
    os.remove(os.path.join(OBR_DIR, n))
K3 = None
for n in os.listdir(OBR_DIR):
    if n.startswith(f"polozka_{A}_") and n not in (K1, K2):
        K3 = n

# ------------------------------------------------------------------------------------------------------------------ B
print("== B PUT: rucni polozky")
TEXT = {"name": "Doprava a zaměření na místě", "dim": "1× výjezd", "qty": 1, "unit_price": 1500, "total": 1500, "manual": {"typ": "text", "popis": "Zaměření vestavby u zákazníka\nvčetně fotodokumentace", "obrazky": [K1, K2]}}
KAT = {"name": "Šuplíkový box", "dim": "800 × 600 mm", "qty": "2", "unit_price": "1 234,5", "total": 0, "product_id": P_GLB, "manual": {"typ": "katalog", "popis": "SKU a parametry", "model": True}}
rev0 = revizi(A)
r = put(A, REG + [TEXT, KAT], total=21400 + 1500 + 2469)
over("B1 PUT s ruznymi rucnimi polozkami: 200, revize +1, archivovan puvodni stav", r.status_code == 200 and r.get_json().get("revision_number") == 2 and revizi(A) == rev0 + 1, (r.status_code, r.get_json()))
items, total, rev = ulozene(A)
over("B2 obycejne radky beze zmeny a na zacatku (radek konfigurace prvni), rucni na konci v poradi z formulare", items[:2] == REG and [i["name"] for i in items[2:]] == ["Doprava a zaměření na místě", "Šuplíkový box"], [i["name"] for i in items])
t = items[2]
over("B3 volny text: cista pole, qty \"1 ks\" (jako radky ze sceny), total = qty x cena, popis a 2 obrazky ulozeny",
     t == {"name": "Doprava a zaměření na místě", "dim": "1× výjezd", "qty": "1 ks", "unit_price": 1500, "total": 1500, "manual": {"typ": "text", "popis": "Zaměření vestavby u zákazníka\nvčetně fotodokumentace", "obrazky": [K1, K2]}}, t)
k = items[3]
over("B4 z katalogu: cena z textu '1 234,5' = 1234.5, 2 ks -> total 2 469, product_id, vrstva 'produkt', model True",
     k["unit_price"] == 1234.5 and k["qty"] == "2 ks" and k["total"] == 2469 and k["product_id"] == P_GLB and k["layer"] == "produkt" and k["manual"] == {"typ": "katalog", "popis": "SKU a parametry", "model": True}, k)
over("B5 total_price se uklada tak, jak ho poslal formular", total == 25369, total)
# idempotence: dalsi ulozeni stejneho kusovniku nic nemeni
r = put(A, items, total=25369)
over("B6 opakovane ulozeni toho, co vratil server, projde beze zmeny (kolem dokola)", r.status_code == 200 and ulozene(A)[0] == items, r.get_json())
# nepodstatne pole od klienta se zahodi
r = put(A, REG + [{**TEXT, "evil": "<script>", "manual": {**TEXT["manual"], "x": 1}, "mesh_group": 5, "layer": "alu", "drawing_bbox": {"a": 1}}], total=22900)
over("B7 cizi / navic klice u rucni polozky (mesh_group, layer, evil, drawing_bbox, manual.x) se zahodi",
     r.status_code == 200 and set(ulozene(A)[0][2]) == {"name", "dim", "qty", "unit_price", "total", "manual"} and set(ulozene(A)[0][2]["manual"]) == {"typ", "popis", "obrazky"}, ulozene(A)[0][2])

for vstup, ocekavano in ((3, "3 ks"), ("3", "3 ks"), ("3 ks", "3 ks"), (" 12  KS ", "12 ks"), (3.0, "3 ks")):
    r = put(A, REG + [{**TEXT, "qty": vstup, "manual": {"typ": "text", "popis": ""}}], total=21400)
    over(f"B7b mnozstvi {vstup!r} -> uklada se {ocekavano!r}", r.status_code == 200 and ulozene(A)[0][2]["qty"] == ocekavano, (r.status_code, r.get_json(), ulozene(A)[0][2]))
r = put(A, REG + [{**KAT, "manual": {"typ": "katalog", "popis": "x", "model": "ano"}}], total=22000)
over("B8 manual.model musi byt presne true (text 'ano' se nebere jako zapnute a neulozi se)", r.status_code == 200 and "model" not in ulozene(A)[0][2]["manual"], (r.status_code, ulozene(A)[0][2]))

print("== C PUT: odmitnuti (nic se nezmeni, revize se neprida)")
stav = ulozene(A)
rv = revizi(A)


def odmitnuto(popis, items_, ocekavana_hlaska=None, kod=400):
    r = put(A, items_)
    ok = r.status_code == kod and ulozene(A) == stav and revizi(A) == rv and (ocekavana_hlaska is None or ocekavana_hlaska in (r.get_json() or {}).get("error", ""))
    over(f"C {popis}: {kod}, v DB beze zmeny", ok, (r.status_code, r.get_json()))


odmitnuto("smazani obycejneho radku", [REG[0], TEXT], "Řádky kusovníku")
odmitnuto("pridani obycejneho radku (bez manual)", REG + [{"name": "Nový řádek", "qty": "1 ks", "unit_price": 1, "total": 1}], "Řádky kusovníku")
odmitnuto("prejmenovani obycejneho radku", [{**REG[0], "name": "Jiný název"}, REG[1], TEXT], "Řádky kusovníku")
odmitnuto("prohozeni poradi obycejnych radku", [REG[1], REG[0], TEXT], "Řádky kusovníku")
odmitnuto("rucni polozka bez nazvu", REG + [{**TEXT, "name": "  "}], "chybí název")
odmitnuto("nazev nad 200 znaku", REG + [{**TEXT, "name": "x" * 201}], "název je delší")
odmitnuto("popis nad 2000 znaku", REG + [{**TEXT, "manual": {**TEXT["manual"], "popis": "x" * 2001}}], "popis je delší")
odmitnuto("neznamy typ", REG + [{**TEXT, "manual": {"typ": "jiny"}}], "neznámý typ")
odmitnuto("mnozstvi 0", REG + [{**TEXT, "qty": 0}], "množství")
odmitnuto("mnozstvi 1000", REG + [{**TEXT, "qty": 1000}], "množství")
odmitnuto("mnozstvi 1,5 ks", REG + [{**TEXT, "qty": 1.5}], "celé číslo")
odmitnuto("mnozstvi text", REG + [{**TEXT, "qty": "dva"}], "množství")
odmitnuto("mnozstvi '3 kusy'", REG + [{**TEXT, "qty": "3 kusy"}], "množství")
odmitnuto("mnozstvi '1,5'", REG + [{**TEXT, "qty": "1,5"}], "množství")
odmitnuto("mnozstvi '-2 ks'", REG + [{**TEXT, "qty": "-2 ks"}], "množství")
odmitnuto("mnozstvi 7 cislic", REG + [{**TEXT, "qty": "1234567"}], "množství")
odmitnuto("mnozstvi bool", REG + [{**TEXT, "qty": True}], "množství")
odmitnuto("zaporna cena", REG + [{**TEXT, "unit_price": -1}], "cena za kus")
odmitnuto("cena nad 10 000 000", REG + [{**TEXT, "unit_price": 10000001}], "cena za kus")
odmitnuto("cena true (bool)", REG + [{**TEXT, "unit_price": True}], "cena za kus")
odmitnuto("3 obrazky", REG + [{**TEXT, "manual": {**TEXT["manual"], "obrazky": [K1, K2, K3 or K1]}}], "nejvýše 2")
odmitnuto("obrazek jine nabidky", REG + [{**TEXT, "manual": {**TEXT["manual"], "obrazky": [f"polozka_{B}_0000000000000000.png"]}}], "neplatný obrázek")
odmitnuto("neexistujici soubor obrazku", REG + [{**TEXT, "manual": {**TEXT["manual"], "obrazky": [f"polozka_{A}_ffffffffffffffff.png"]}}], "neplatný obrázek")
odmitnuto("cesta misto klice obrazku", REG + [{**TEXT, "manual": {**TEXT["manual"], "obrazky": ["../../etc/passwd"]}}], "neplatný obrázek")
odmitnuto("obrazky nejsou seznam", REG + [{**TEXT, "manual": {**TEXT["manual"], "obrazky": K1}}], "nejvýše 2")
odmitnuto("katalog bez product_id", REG + [{**KAT, "product_id": None}], "chybí produkt")
odmitnuto("katalog s neexistujicim produktem", REG + [{**KAT, "product_id": 99999999}], "neexistuje")
odmitnuto("katalog s modelem u produktu bez GLB", REG + [{**KAT, "product_id": P_BEZ}], "nemá 3D model")
odmitnuto("vic nez 20 rucnich polozek", REG + [dict(TEXT, name=f"P{i}") for i in range(21)], "Nejvýše 20")
r = put(A, REG + [dict(TEXT, name=f"P{i}", manual={"typ": "text", "popis": ""}) for i in range(20)], total=21400)
over("C2 presne 20 rucnich polozek projde", r.status_code == 200 and len(ulozene(A)[0]) == 22, r.status_code)
r = put(A, REG, total=21400)
over("C3 odebrani vsech rucnich polozek (pouze obycejne radky) projde", r.status_code == 200 and ulozene(A)[0] == REG, r.status_code)
r = put(A, REG + [TEXT, KAT], total=25369)
over("C4 znovu pridane (klice obrazku stale existuji): 200", r.status_code == 200, r.get_json())

print("== D verejne obrazky a model")
over("D1 verejny obrazek polozky za spravnym tokenem: 200, image/png", (lambda r: r.status_code == 200 and r.mimetype == "image/png" and r.data == PNG)(anon.get(f"/api/public/offers/tok-a/item-image/{K1}")), None)
over("D2 JPEG: image/jpeg", anon.get(f"/api/public/offers/tok-a/item-image/{K2}").mimetype == "image/jpeg", None)
over("D3 nahrany, ale NEodkazovany obrazek (K3 neni v items): 404", K3 is not None and anon.get(f"/api/public/offers/tok-a/item-image/{K3}").status_code == 404, K3)
over("D4 obrazek nabidky A pres token nabidky B: 404", anon.get(f"/api/public/offers/tok-b/item-image/{K1}").status_code == 404, None)
over("D5 neexistujici token: 404", anon.get(f"/api/public/offers/neexistuje/item-image/{K1}").status_code == 404, None)
over("D6 neplatny klic (../, cizi format): 404", all(anon.get(f"/api/public/offers/tok-a/item-image/{k}").status_code == 404 for k in ("..%2Fapp.py", "x.png", "polozka_900101_zz.png")), None)
r = anon.get(f"/api/public/offers/tok-a/item-model/{P_GLB}")
over("D7 3D model polozky z katalogu: 200 model/gltf-binary, zacina 'glTF', Cache-Control private, ETag", r.status_code == 200 and r.mimetype == "model/gltf-binary" and r.data[:4] == b"glTF"
     and "private" in r.headers.get("Cache-Control", "") and bool(r.headers.get("ETag")), (r.status_code, r.mimetype, dict(r.headers)))
r2 = anon.get(f"/api/public/offers/tok-a/item-model/{P_GLB}", headers={"If-None-Match": r.headers.get("ETag")})
over("D8 podminene stazeni (If-None-Match) = 304", r2.status_code == 304, r2.status_code)
over("D9 produkt, ktery nabidka neobsahuje (nebo bez priznaku model): 404", anon.get(f"/api/public/offers/tok-a/item-model/{P_BEZ}").status_code == 404, None)
over("D9b produkt s GLB, ktery nabidka neobsahuje, model NEvydava (token neotevre cely katalog): 404", anon.get(f"/api/public/offers/tok-a/item-model/{P_GLB2}").status_code == 404, None)
over("D10 model pres token jine nabidky (B nema rucni polozky): 404", anon.get(f"/api/public/offers/tok-b/item-model/{P_GLB}").status_code == 404, None)
put(A, REG + [{**KAT, "manual": {"typ": "katalog", "popis": "bez modelu"}}], total=24000)
over("D11 polozka z katalogu BEZ manual.model: model se nevydava (404)", anon.get(f"/api/public/offers/tok-a/item-model/{P_GLB}").status_code == 404, None)
put(A, REG + [TEXT, KAT], total=25369)
payload = anon.get("/api/public/offers/tok-a").get_json()
rp = [i for i in payload["items"] if i.get("manual")]
over("D12 verejny JSON nabidky nese rucni polozky vcetne manual.obrazky / manual.model (stranka z nich sklada adresy)", len(rp) == 2 and rp[0]["manual"]["obrazky"] == [K1, K2] and rp[1]["manual"]["model"] is True and payload["items"][0] == REG[0], payload["items"][-2:])
with real.cursor() as cur:
    cur.execute("UPDATE scene_offers SET is_active=0 WHERE id=%s", (A,))
real.commit()
over("D13 deaktivovana nabidka: obrazek i model 404", anon.get(f"/api/public/offers/tok-a/item-image/{K1}").status_code == 404 and anon.get(f"/api/public/offers/tok-a/item-model/{P_GLB}").status_code == 404, None)
with real.cursor() as cur:
    cur.execute("UPDATE scene_offers SET is_active=1, expires_at=%s WHERE id=%s", (datetime.datetime.now() - datetime.timedelta(days=1), A))
real.commit()
over("D14 vyprsela nabidka: obrazek i model 404", anon.get(f"/api/public/offers/tok-a/item-image/{K1}").status_code == 404 and anon.get(f"/api/public/offers/tok-a/item-model/{P_GLB}").status_code == 404, None)

# ------------------------------------------------------------------------------------------------------------------ uklid + kontrola ostrych tabulek
shutil.rmtree(OBR_DIR, ignore_errors=True)
po = stav_ostrych()
over("Z ostre tabulky scene_offers / scene_offer_revisions / audit_log jsou beze zmeny", po == pred, (pred, po))
ok = sum(vysl)
print(f"\nVYSLEDEK rucni polozky v online nabidce - skutecne endpointy: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
