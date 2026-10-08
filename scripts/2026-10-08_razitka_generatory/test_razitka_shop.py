#!/usr/bin/env python3
"""RAZITKA NA VEREJNEM MODELU GENERATORU (api/stul_shop.py + stul_glb; bot8, 2026-10-08; WORKFLOW pravidlo 61, Robert: "razitka budou na vsech 3D modelech ve vsech generatorech").
SKUTECNE routy pres Flask test_client (verejnost bez prihlaseni, zamestnanec se session admina); DB se jen CTE (ceny karet pri resolve); mapovani produktu (5 systemu) se podstrci do cache modulu.

Hlida pro VSECH 5 systemu (30 / 35 / 40 / 41 SSE / 45): odkaz `model.url` z `resolve` i z `/api/shop/configurator/model/<hash>` (cesta, kterou bere zivy model, kosik a odkaz na konfiguraci) vede na GLB S RAZITKY
(o pocet razitek uzlu vic nez holy model, jeden sdileny mesh loga), obsah = `model_pro_parametry` (vychozi) bajt po bajte; totez po brotli, gzip i bez komprese; cache komprimovanych dat se NEZAMENI s holym
modelem (stejny hash; holy model se zakoduje drive nez verejna routa); hlavicky (Content-Encoding, Vary, Cache-Control, Content-Disposition, noindex) beze zmeny; staff `/api/stul/model.glb` je taky s razitky;
`resolve` je beze zmeny (hash, platnost, cena, vodici znacky).
Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_razitka_generatory/test_razitka_shop.py
  (STUL_API_OVERRIDE=<adresar api> = kandidat; --setenv=STUL_API_OVERRIDE=... pri spusteni pres systemd-run; TEST_STOP_PRVNI=1 = prvni selhani konci)"""
import gzip
import json
import os
import struct
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api")
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi - spust pres systemd-run --property=EnvironmentFile=api/.env (viz hlavicka)")
    sys.exit(2)

_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, API)
sys.path.insert(0, os.path.join(REPO, "scripts"))
try:
    import app as appmod  # noqa: E402
    import stul_shop as SH  # noqa: E402
    import stul_glb as G  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
    import stul_razitka as RZ  # noqa: E402
    import stul_api as _stul_api  # noqa: E402
finally:
    threading.Thread.start = _orig

S.nastav_pravidla({})                                                    # zive Robertovy pravidla (cena vyrezu...) test neovlivni
_stul_api.obnov_pravidla = lambda force=False: None
SH.LIMIT_SCHEMA = (10 ** 6, 60)                                          # test vola verejne API desitky krat z jedne IP: omezeni poctu dotazu (429) by ho shodilo
SH.LIMIT_RESOLVE = (10 ** 6, 60)
SH.LIMIT_GLB = (10 ** 6, 60)
SH.HODINOVY_STROP["schema"] = SH.HODINOVY_STROP["resolve"] = 10 ** 6
for k_ in list(SH.HODINOVY_STROP):
    SH.HODINOVY_STROP[k_] = 10 ** 6

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")
        if os.environ.get("TEST_STOP_PRVNI"):
            sys.exit(1)


PIDS = {30: 9891, 35: 9892, 40: 9893, 41: 9894, 45: 9895}
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(PIDS[30]): SH.RECEPT, str(PIDS[35]): SH.RECEPT_35, str(PIDS[40]): SH.RECEPT_40, str(PIDS[41]): SH.RECEPT_SSE, str(PIDS[45]): SH.RECEPT_45})
anon = appmod.app.test_client()
c_adm = appmod.get_conn()
cu_adm = c_adm.cursor()
cu_adm.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
ADMIN_ID = cu_adm.fetchone()["id"]
c_adm.rollback()
staff = appmod.app.test_client()
with staff.session_transaction() as _s:
    _s["user_id"] = ADMIN_ID


def post(sel, pid, lang="cs"):
    r = anon.post("/api/shop/configurator/resolve", json={"product_id": pid, "selection": sel, "lang": lang})
    return r.status_code, r.get_json()


def gltf(b):
    magic, ver, celkem = struct.unpack_from("<III", b, 0)
    dj, tj = struct.unpack_from("<II", b, 12)
    return json.loads(b[20:20 + dj].decode("utf-8")), (magic == 0x46546C67 and ver == 2 and celkem == len(b) and tj == 0x4E4F534A)


def rozbal(resp):
    kod = resp.headers.get("Content-Encoding")
    if kod == "br":
        return G._brotli.decompress(resp.data)
    if kod == "gzip":
        return gzip.decompress(resp.data)
    return resp.data


VYBERY = {30: {}, 35: {}, 40: {"w": 2400}, 41: {}, 45: {"d": 1800}}
print("verejna routa GLB + resolve, 5 systemu")
for sy, pid in PIDS.items():
    sel = VYBERY[sy]
    st, out = post(sel, pid)
    check(st == 200 and out and out.get("valid"), f"system {sy}: resolve 200 a platna konfigurace")
    if not out:
        continue
    p, _ = SH.normalizuj(sel, sy)
    r = S.sestav_stul(**p)
    par = r["parametry"]
    h = G.kanonicky_hash(par)
    check(out.get("hash") == h, f"system {sy}: hash z resolve = kanonicky hash ({out.get('hash')} vs {h})")
    n = len(RZ.razitka(r, h))
    check(n >= 1, f"system {sy}: stul ma aspon jedno razitko ({n})")
    G._GLB_KOMPR.clear()
    holy = G.model_pro_parametry(par, razitka=False)[1]
    stamped = G.model_pro_parametry(par, razitka=True)[1]
    G.zakoduj_pro_klienta(h, holy, "br")                                  # KOLIZE klice: holy model drive v komprimovane cache pod TYMZ hashem
    G.zakoduj_pro_klienta(h, holy, "gzip")
    jb, _ = gltf(holy)
    adresy = {"resolve": out["model"]["url"]}
    sm = anon.get("/api/shop/configurator/model/" + h)
    check(sm.status_code == 200 and (sm.get_json() or {}).get("model", {}).get("url", "").startswith("/api/shop/configurator/glb/"), f"system {sy}: /model/<hash> vraci odkaz na GLB ({sm.status_code})")
    if sm.status_code == 200:
        adresy["model/<hash>"] = sm.get_json()["model"]["url"]
    for odkud, url in adresy.items():
        check(url.startswith("/api/shop/configurator/glb/"), f"system {sy}: odkaz z {odkud} vede na /glb/<token>")
        for kodovani in ("br", "gzip", "identity"):
            resp = anon.get(url, headers={"Accept-Encoding": kodovani})
            check(resp.status_code == 200, f"system {sy} {odkud} {kodovani}: 200 ({resp.status_code})")
            if resp.status_code != 200:
                continue
            hlav = resp.headers
            check(hlav.get("Content-Encoding") == (None if kodovani == "identity" else kodovani), f"system {sy} {odkud} {kodovani}: Content-Encoding ({hlav.get('Content-Encoding')})")
            check(hlav.get("Vary") == "Accept-Encoding" and hlav.get("Cache-Control") == "private, max-age=600" and hlav.get("X-Robots-Tag") == "noindex" and hlav.get("Content-Type") == "model/gltf-binary",
                  f"system {sy} {odkud} {kodovani}: hlavicky Vary / Cache-Control / noindex / typ beze zmeny")
            raw = rozbal(resp)
            check(raw == stamped, f"system {sy} {odkud} {kodovani}: obsah = model S razitky (bajt po bajte; {len(raw)} vs {len(stamped)})")
            check(raw != holy, f"system {sy} {odkud} {kodovani}: obsah NENI holy model (kolize komprimovane cache)")
            jd, okd = gltf(raw)
            check(okd and len(jd["nodes"]) - len(jb["nodes"]) == n and len(jd["meshes"]) - len(jb["meshes"]) == 1, f"system {sy} {odkud} {kodovani}: platne GLB, o {n} uzlu a 1 mesh (logo) vic nez holy model")
    # cena a platnost se razitky nemeni (razitka jsou jen v GLB)
    st2, out2 = post(sel, pid)
    check(st2 == 200 and out2.get("hash") == h and out2.get("valid") is True, f"system {sy}: druhy resolve stejny hash a platnost")

print("staff trasa /api/stul/model.glb")
for sy, qs in ((30, ""), (40, "system=40&sirka=2200")):
    par = S.sestav_stul(**S.parametry_z_dotazu({k: v for k, v in (x.split("=") for x in qs.split("&") if x)}))["parametry"]
    resp = staff.get("/api/stul/model.glb" + ("?" + qs if qs else ""), headers={"Accept-Encoding": "identity"})
    check(resp.status_code == 200, f"staff system {sy}: model.glb 200 ({resp.status_code})")
    if resp.status_code == 200:
        check(resp.data == G.model_pro_parametry(par, razitka=True)[1], f"staff system {sy}: model.glb = model S razitky")
check(anon.get("/api/stul/model.glb").status_code in (401, 403), "staff trasa model.glb zustava jen pro zamestnance")

print(f"\nvysledek: {OK} OK, {len(FAILS)} chyb")
sys.exit(1 if FAILS else 0)
