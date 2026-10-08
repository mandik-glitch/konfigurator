#!/usr/bin/env python3
"""Test volby 'spodni police BEZ DESKY' ve VEREJNEM API stolu (api/stul_shop.py; bot8, 2026-10-07; Robert: "spodni police nech ma volbu byt bez desky, jen profily / ram").
Skutecne routy / funkce BEZ prihlaseni, DB se jen CTE (ceny karet); mapovani produktu se podstrci do cache modulu - nic se nezapisuje.

Hlida: schema (slot `shelfboard` = toggle ve skupine Konstrukce hned za `shelf`, zavisi na `shelf`, texty cs / en / sk a zaloha pro de / hu, SSE slot nema), resolve (vychozi = s deskou,
vypnuti: platne, jiny hash, nizsi cena = cena nabidky 'vratit desku', bez polic se zahodi), shrnuti vyberu (jen bez desky), token modelu (klic B jen bez desky), kusovnik / objednavka,
vyrobni list, odkaz pro zamestnance, verejne 3D ovladani, GLB, SSE.
Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_police_bez_desky/test_police_bez_desky_shop.py
  (STUL_API_OVERRIDE=<adresar api> = kandidat; --setenv=STUL_API_OVERRIDE=... pri spusteni pres systemd-run)"""
import copy
import json
import os
import sys
import threading
import time

sys.dont_write_bytecode = True                       # kandidatni strom nesmi psat bajtkod do zivych adresaru (__pycache__ symlink)
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
    import stul_api as _stul_api  # noqa: E402
    import stul_glb as G  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
    import stul_shop as SH  # noqa: E402
    import stul_vyrobni_list as VL  # noqa: E402
finally:
    threading.Thread.start = _orig

S.nastav_pravidla({})                                                    # zive Robertovy pravidla (cena vyrezu...) test neovlivni
_stul_api.obnov_pravidla = lambda force=False: None
SH.LIMIT_SCHEMA = (10 ** 6, 60)                                          # test vola verejne schema desitky krat z jedne IP: omezeni poctu dotazu (429) by ho shodilo
SH.HODINOVY_STROP["schema"] = 10 ** 6
SH.HODINOVY_STROP["resolve"] = 10 ** 6
SH.LIMIT_RESOLVE = (10 ** 6, 60)

OK, FAILS = 0, []


def check(cond, msg, detail=""):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg} {detail}")


PIDS = {30: 9876, 35: 9877, 40: 9878, 41: 9879, 45: 9880}
SH._DELKY_CACHE.update(t=time.time() + 1e7, set=frozenset(S.PANEL_DELKY))
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(PIDS[30]): SH.RECEPT, str(PIDS[35]): SH.RECEPT_35, str(PIDS[40]): SH.RECEPT_40, str(PIDS[41]): SH.RECEPT_SSE, str(PIDS[45]): SH.RECEPT_45})
anon = appmod.app.test_client()
SYSTEMY_SE_POLICI = (30, 35, 40, 45)


def schema(lang="cs", sy=30):
    r = anon.get(f"/api/shop/products/{PIDS[sy]}/configurator?lang={lang}")
    assert r.status_code == 200, r.status_code
    return r.get_json()


def res(sel, lang="cs", sy=30):
    return SH.resolve(copy.deepcopy(sel), lang, system=sy)


# ---------------------------------------------------------------------------------------------------------------------
print("A) schema")
for sy in SYSTEMY_SE_POLICI:
    for lang, label, help_cast in (("cs", "Desky na spodních policích", "rám z profilů"), ("en", "Boards on the lower shelves", "frame of profiles"), ("sk", "Dosky na spodných policiach", "rám z profilov")):
        sc = schema(lang, sy)
        ids = [s["id"] for s in sc["slots"]]
        sl = next((s for s in sc["slots"] if s["id"] == "shelfboard"), None)
        check(sl is not None and sl["type"] == "toggle" and sl["group"] == "g_frame" and sl["label"] == label, f"A1 system {sy} {lang}: slot shelfboard je toggle ve skupine g_frame s popiskem '{label}'", str(sl))
        if sl:
            check(ids.index("shelfboard") == ids.index("shelf") + 1, f"A2 system {sy} {lang}: slot shelfboard je hned za slotem shelf")
            check(not sl.get("depends_on"), f"A3 system {sy} {lang}: slot nema depends_on (nadrazeny `shelf` je posuvnik, kontrakt zna jen toggle; skryti pres options.hidden) ({sl.get('depends_on')})")
            check(help_cast in (sl.get("help") or "") and "{" not in sl["help"], f"A4 system {sy} {lang}: napoveda ({sl.get('help')!r})")
            check(sl["options"] == [{"id": "on", "label": label}], f"A5 system {sy} {lang}: moznosti toggle")
        check(sc["default_selection"].get("shelfboard") is True and set(sc["default_selection"]) == set(ids), f"A6 system {sy} {lang}: vychozi vyber ma shelfboard = True a klic pro kazdy slot")
sc41 = schema("cs", 41)
check("shelfboard" not in {s["id"] for s in sc41["slots"]} and sc41["default_selection"].get("shelfboard") is True and set(sc41["default_selection"]) >= {s["id"] for s in sc41["slots"]},
      "A7: schema SSE (system 41) slot shelfboard nema, vychozi vyber ho nese (kompletni vyber)")
for lang in ("de", "hu"):
    try:
        sc = schema(lang, 30)
        sl = next((s for s in sc["slots"] if s["id"] == "shelfboard"), None)
        check(sl is not None and sl["label"], f"A8: jazyk {lang}: slot shelfboard ma popisek (zaloha z anglictiny, dokud neni preklad: {sl and sl['label']!r})")
    except Exception as e:  # noqa: BLE001
        check(False, f"A8: jazyk {lang}: schema spadlo: {e}")

# ---------------------------------------------------------------------------------------------------------------------
print("B) resolve: vychozi, vypnuti desky, cena, hash")
for sy in SYSTEMY_SE_POLICI:
    base = schema("cs", sy)["default_selection"]
    r0 = res(base, "cs", sy)
    r_t = res({**base, "shelfboard": True}, "cs", sy)
    check(r0["selection"]["shelfboard"] is True and r0["hash"] == r_t["hash"] and r0["kod"] == r_t["kod"] and r0["price"] == r_t["price"], f"B1 system {sy}: vychozi == vyslovne zapnuta deska (hash, kod, cena)")
    r_f = res({**base, "shelfboard": False}, "cs", sy)
    check(r_f["valid"] and r_f["selection"]["shelfboard"] is False and r_f["hash"] != r0["hash"] and r_f["kod"] != r0["kod"], f"B2 system {sy}: bez desky: platne, vyber si hodnotu drzi, jiny hash a kod")
    check(not r0["options"]["shelfboard"].get("hidden") and not r_f["options"]["shelfboard"].get("hidden"), f"B2b system {sy}: s policemi se slot shelfboard nevykresli skryte (options.hidden neni)")
    check(r_f["price"]["net"] < r0["price"]["net"], f"B3 system {sy}: bez desky je levnejsi ({r0['price']['net']} -> {r_f['price']['net']})")
    on_f = r_f["options"]["shelfboard"]["on"]
    on_0 = r0["options"]["shelfboard"]["on"]
    check(on_0["disabled"] is False and on_0["price_delta"] == 0 and on_f["disabled"] is False and abs(on_f["price_delta"] - (r0["price"]["net"] - r_f["price"]["net"])) < 0.011,
          f"B4 system {sy}: nabidka 'vratit desku' stoji presne rozdil cen ({on_f['price_delta']} vs {r0['price']['net'] - r_f['price']['net']:.2f}), u vychoziho 0", str(on_f))
    check(not r_f["errors"] and not any(n["slot"] == "shelfboard" for n in r_f["notices"]), f"B5 system {sy}: bez desky bez chyb a oznameni")
    r_0p = res({**base, "shelf": 0, "shelfboard": False}, "cs", sy)
    r_0 = res({**base, "shelf": 0}, "cs", sy)
    check(r_0p["selection"]["shelfboard"] is True and r_0p["hash"] == r_0["hash"] and r_0p["price"] == r_0["price"], f"B6 system {sy}: bez spodnich polic se 'bez desky' zahodi (vyber True, stejny hash i cena)")
    check(r_0p["options"]["shelfboard"].get("hidden") is True and r_0["options"]["shelfboard"].get("hidden") is True, f"B6b system {sy}: bez spodnich polic je slot shelfboard skryty (options.shelfboard.hidden)")
    p_n, norm_n = SH.normalizuj({**base, "shelf": 0, "shelfboard": False}, sy)
    p_s, norm_s = SH.normalizuj({**base, "shelf": 1, "shelfboard": False}, sy)
    check(p_n["police_deska"] is True and norm_n["shelfboard"] is True and p_s["police_deska"] is False and norm_s["shelfboard"] is False,
          f"B6c system {sy}: normalizuj samotny: bez spodnich polic se 'bez desky' zahodi (parametr i vyber True), s policemi zustane False")
    r_2 = res({**base, "shelf": 2, "h": 1150, "shelfboard": False}, "cs", sy)
    r_2d = res({**base, "shelf": 2, "h": 1150}, "cs", sy)
    check(r_2["valid"] and r_2["selection"]["shelf"] == 2 and r_2["selection"]["shelfboard"] is False and r_2["price"]["net"] < r_2d["price"]["net"], f"B7 system {sy}: dve police bez desek: platne a levnejsi")
    # souhrn
    s0 = SH.pro_objednavku(base, product_id=PIDS[sy])
    sf = SH.pro_objednavku({**base, "shelfboard": False}, product_id=PIDS[sy])
    check(not any(x["id"] == "shelfboard" for x in s0["souhrn"]) and not any(x["id"] == "shelfboard" for x in sf["souhrn"]) and any(x["id"] == "shelf" for x in sf["souhrn"]),
          f"B8 system {sy}: shrnuti uvadi jen to, co stul obsahuje (Robert 2026-10-08): ani u vychoziho stolu, ani bez desky neni radek 'Desky na spodních policích: ne', police zustavaji ({[x['id'] for x in sf['souhrn'] if x['id'] in ('shelf', 'shelfboard')]})")
    sn = SH.pro_objednavku({**base, "shelf": 0, "shelfboard": False}, product_id=PIDS[sy])
    check(not any(x["id"] == "shelfboard" for x in sn["souhrn"]), f"B9 system {sy}: bez polic se deska ve shrnuti neukazuje")
    lam0 = sum(x["mnozstvi"] for x in s0["bom"] if x["nazev"] == "laminodeska")
    lamf = sum(x["mnozstvi"] for x in sf["bom"] if x["nazev"] == "laminodeska")
    check(lam0 - lamf == 1 and sf["ok"] and sf["valid"] and sf["price"]["net"] < s0["price"]["net"], f"B10 system {sy}: kusovnik: o jednu laminodesku min ({lam0} -> {lamf})")
    # model
    g0, gf = SH.glb_bytes(base, sy), SH.glb_bytes({**base, "shelfboard": False}, sy)
    check(len(gf) < len(g0), f"B11 system {sy}: GLB bez desky je mensi ({len(g0)} -> {len(gf)} B)")

# ---------------------------------------------------------------------------------------------------------------------
print("C) token modelu, odkazy pro zamestnance")
p_def = S._norm_parametry({})
p_bez = S._norm_parametry({"police_deska": False})
z_def, z_bez = SH._zabal(p_def), SH._zabal(p_bez)
check("B" not in z_def and z_bez.get("B") == 0, f"C1: klic B v tokenu jen bez desky ({z_def.get('B')} / {z_bez.get('B')})")
check(SH._rozbal(z_bez)["police_deska"] is False and SH._rozbal(z_def)["police_deska"] is True and SH._rozbal({"w": 1280, "d": 800, "h": 840, "t": 1})["police_deska"] is True, "C2: _rozbal: B = bez desky, bez klice = s deskou (i starsi tokeny)")
p0 = S.sestav_stul()["parametry"]
p1 = S.sestav_stul(police_deska=False)["parametry"]
check(SH._rozbal(SH._zabal(p1))["police_deska"] is False and SH._rozbal(SH._zabal(p1))["police"] == 1, "C3: token bez desky obstoji obrat (zabal / rozbal)")
check("B" not in SH._zabal(S.sestav_stul(police=0, police_deska=False)["parametry"]), "C4: bez polic token klic B nema")
tok = SH.podepis_model(p1)
par_tok, chyba_tok = SH.over_model(tok)
check(chyba_tok is None and par_tok["police_deska"] is False and par_tok["police"] == 1, "C5: podepsany token se rozbali na parametry bez desky")
par_tok0, _ = SH.over_model(SH.podepis_model(p0))
check(par_tok0["police_deska"] is True, "C5b: podepsany token vychoziho stolu se rozbali na stul s deskou")
base = schema("cs", 30)["default_selection"]
r0, rf = res(base), res({**base, "shelfboard": False})
b0, bf = SH._staff_blok(r0["hash"]), SH._staff_blok(rf["hash"])
check("police_deska" not in b0["vyrobni_list_url"] and "police_deska=0" in bf["vyrobni_list_url"] and "police_deska=0" in bf["vyrobni_sestava_url"], f"C6: odkaz na vyrobni list: vychozi bez police_deska, bez desky police_deska=0 ({bf['vyrobni_list_url'][-40:]})")
qs = bf["vyrobni_list_url"].split("?", 1)[1]
args = dict(x.split("=") for x in qs.split("&"))
check(S.sestav_stul(**S.parametry_z_dotazu(args))["parametry"]["police_deska"] is False, "C7: odkaz na vyrobni list vede zpet na konfiguraci bez desky")

# ---------------------------------------------------------------------------------------------------------------------
print("D) vyrobni list a vyrobni sestava")
sel_siroky = {**base, "w": 2100}
sest0 = SH.vyrobni_sestava(sel_siroky, product_id=PIDS[30])
sestf = SH.vyrobni_sestava({**sel_siroky, "shelfboard": False}, product_id=PIDS[30])
h0, hf = VL.html_list(sest0), VL.html_list(sestf)
check(sest0["ok"] and sestf["ok"] and "Pracovní deska a police jsou u střední nohy" in h0 and "Pracovní deska je u střední nohy" in hf and "a police" not in hf.split("Deska s výřezy")[1].split("</div>")[0],
      "D1: vyrobni list: poznamka o deleni desek bez police, kdyz jsou police bez desky; s deskou beze zmeny")
check(not any(q["role"].startswith("spodní police") for q in sestf["vypis"]["desky"]) and any(q["role"].startswith("spodní police") for q in sest0["vypis"]["desky"]), "D2: vypis desek: bez spodni police")
check(sestf["parametry"]["police_deska"] is False and "BEZ DESEK" in next(x["text"] for x in sestf["vypis"]["montazni_postup"] if x["krok"] == 3), "D3: montazni postup bez desek polic")
check(sestf["cena_celkem_czk"] < sest0["cena_celkem_czk"], f"D4: sestava: cena bez desky je nizsi ({sest0['cena_celkem_czk']} -> {sestf['cena_celkem_czk']})")

# ---------------------------------------------------------------------------------------------------------------------
print("E) verejne 3D ovladani")
for lang, txt_bez, txt_s in (("cs", "Vrátit desku police", "Odebrat desku police"), ("en", "Put the shelf board back", "Remove the shelf board"), ("sk", "Vrátiť dosku police", "Odstrániť dosku police")):
    rf = res({**base, "shelfboard": False}, lang)
    r0 = res(base, lang)
    ovf = (rf.get("vodici") or {}).get("ovladani")
    ov0 = (r0.get("vodici") or {}).get("ovladani")
    check(ovf is not None and ov0 is not None, f"E1 {lang}: ovladani ve 3D je (nebylo vynechano pro chybejici preklad)")
    if ovf and ov0:
        cf = next(c for c in ovf["casti"] if c["id"] == "shelf1")
        c0 = next(c for c in ov0["casti"] if c["id"] == "shelf1")
        check([m["text"] for m in cf["menu"] if m["nastav"] == {"shelfboard": True}] == [txt_bez], f"E2 {lang}: bez desky nabidka '{txt_bez}'")
        check([m["text"] for m in c0["menu"] if m["nastav"] == {"shelfboard": False}] == [txt_s], f"E3 {lang}: s deskou nabidka '{txt_s}'")
        check("shelfboard" in cf["param"] and "shelfboard" in c0["param"], f"E4 {lang}: cast police nese slot shelfboard")

# ---------------------------------------------------------------------------------------------------------------------
print("F) SSE (system 41) volbu ignoruje")
sse = schema("cs", 41)["default_selection"]
r_s0 = res(sse, "cs", 41)
r_sf = res({**sse, "shelfboard": False}, "cs", 41)
check(r_sf["selection"]["shelfboard"] is True and r_sf["hash"] == r_s0["hash"] and r_sf["price"] == r_s0["price"] and r_sf["valid"], "F1: SSE: shelfboard False se ignoruje (vyber True, stejny hash a cena)")

print(f"\n==> {OK}/{OK + len(FAILS)} kontrol OK" + (f", SELHALO {len(FAILS)}: " + "; ".join(FAILS[:6]) if FAILS else ""))
sys.exit(1 if FAILS else 0)
