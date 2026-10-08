#!/usr/bin/env python3
"""Test ODEBRANI JEN SVITIDLA LED (bot8, 2026-10-04; Robert: "pridat moznost odejmout jen samotne LED, profily zustanou").
Generator: led_svetlo=False odebere JEN svitidla (product_4929, 1-3 ks podle sirky); ramena (XRAIL_TOP_L/P), pricny profil nad svetlem (ZRAIL_TOP), vzpery a jejich spojky zustavaji, VSECHNY ostatni
dily maji presne stejne polohy a rozmery; zadny problem; cena nizsi. Hash: vychozi beze zmeny, svitidlo pryc = jiny hash, bez led/stojek se priznak do hashe nepocita.
Verejne API (DB): slot `ledlight` (toggle, zavisi na posts+led), resolve, cena, token modelu, souhrn, 3D menu, preklady.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_led_svetlo.py"""
import os
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "api"))
import numpy as np  # noqa: E402
import stul_glb as G  # noqa: E402
import stul_konfigurator as S  # noqa: E402

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        if len(FAILS) <= 30:
            print(f"  CHYBA: {msg}")


def klic(k):
    return tuple(klic(x) for x in k) if isinstance(k, list) else k


for kw in (dict(), dict(sirka=1000), dict(sirka=1840), dict(sirka=2400), dict(sirka=3000), dict(vzpery=True, sirka=1400, panely=False, elektrozlab=False), dict(led_rameno=300), dict(led_rameno=900, hloubka=1100)):
    a = S.sestav_stul(**kw)
    if not a["parametry"]["led"]:
        continue
    b = S.sestav_stul(**{**kw, "led_svetlo": False})
    n = f"[{kw}]"
    ka = {klic(k): i for i, k in enumerate(a["klice"])}
    kb = {klic(k): i for i, k in enumerate(b["klice"])}
    svit = [k for k, i in ka.items() if a["dily"][i]["part_id"] == "product_4929"]
    check(svit and not any(d["part_id"] == "product_4929" for d in b["dily"]), f"{n}: svitidlo ({len(svit)} ks) je pryc")
    check(set(ka) - set(kb) == set(svit) and not (set(kb) - set(ka)), f"{n}: odebrano PRAVE svitidlo, nic nepribylo ({sorted(map(str, set(ka) - set(kb)))[:4]})")
    shodne = all(a["dily"][ka[k]]["position"] == b["dily"][kb[k]]["position"] and a["dily"][ka[k]]["scale"] == b["dily"][kb[k]]["scale"] and a["dily"][ka[k]]["quaternion"] == b["dily"][kb[k]]["quaternion"] for k in kb)
    check(shodne, f"{n}: vsechny ostatni dily maji stejnou polohu, otoceni i rozmer")
    for ram in (("t", S.XRAIL_TOP_L), ("t", S.XRAIL_TOP_P), ("t", S.ZRAIL_TOP)):
        check(ram in kb, f"{n}: {ram} zustava")
    check(b["problemy"] == [] and b["parametry"]["led"] and b["parametry"]["led_svetlo"] is False, f"{n}: bez problemu ({[x['kod'] for x in b['problemy']]})")
    check(len(b["dily"]) == len(a["dily"]) - len(svit), f"{n}: o {len(svit)} dilu mene")
    check(S.ovladani_3d(b)["casti"] is not None and any(c["id"] == "led" for c in S.ovladani_3d(b)["casti"]), f"{n}: cast LED (ramena) je ve 3D ovladani porad")

h0 = G.kanonicky_hash({})
check(G.kanonicky_hash({"led_svetlo": True}) == h0, "vychozi svitidlo zapnute: hash beze zmeny")
check(G.kanonicky_hash({"led_svetlo": False}) != h0, "svitidlo pryc = jiny hash")
check(G.kanonicky_hash({"led": False, "led_svetlo": False}) == G.kanonicky_hash({"led": False}) and G.kanonicky_hash({"stojky": False, "panely": False, "led": False, "led_svetlo": False}) == G.kanonicky_hash({"stojky": False, "panely": False, "led": False}),
      "bez LED / stojek se priznak svitidla do hashe nepocita")
check(sum(1 for k in S.sestav_stul()["klice"] if k[0] != "zasl") == 50, "vychozi konfigurace: 50 dilu (bez zaslepek volnych koncu rampy LED, od 2026-10-06)")
# led vypnute: led_svetlo nic nemeni
x = S.sestav_stul(led=False); y = S.sestav_stul(led=False, led_svetlo=False)
check([d["position"] for d in x["dily"]] == [d["position"] for d in y["dily"]], "led vypnute: led_svetlo nic nemeni")

# ---- verejne API (potrebuje DB kvuli cenam)
if os.environ.get("DB_HOST"):
    _o = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
    try:
        import app as appmod  # noqa: E402,F401
        import stul_shop as SH  # noqa: E402
    finally:
        threading.Thread.start = _o
    import stul_api as _stul_api  # noqa: E402
    S.nastav_pravidla({})                                                     # ziva pravidla stolu (okno Pravidla) test neovlivni - viz test_stul_api.py
    _stul_api.obnov_pravidla = lambda force=False: None
    for lg in ("cs", "en", "sk"):
        sl = {s_["id"]: s_ for s_ in SH.schema(lg)["slots"]}
        check(sl["ledlight"]["type"] == "toggle" and sl["ledlight"]["depends_on"] == ["posts", "led"] and sl["ledlight"]["label"], f"[{lg}] schema: ledlight (toggle, zavisi na posts + led)")
    check(SH.schema("cs")["default_selection"]["ledlight"] is True, "vychozi vyber: svitidlo zapnute")
    r1 = SH.resolve({}); r0 = SH.resolve({"ledlight": False})
    check(r0["valid"] and r0["selection"]["ledlight"] is False and r0["price"]["net"] < r1["price"]["net"] and r0["hash"] != r1["hash"], f"resolve bez svitidla: platne, nizsi cena ({r1['price']['net']} -> {r0['price']['net']}), jiny hash")
    check(r0["options"]["ledlight"]["on"]["price_delta"] > 0 and r1["options"]["ledlight"]["on"]["price_delta"] == 0 and not r0["options"]["ledlight"]["on"]["disabled"], f"options.ledlight: priplatek za svitidlo ({r0['options']['ledlight']['on']['price_delta']} Kc)")
    pp_, _n = SH.normalizuj({"ledlight": False})
    rb = SH._rozbal(SH._zabal(pp_))
    check(rb["led_svetlo"] is False and "u" in SH._zabal(pp_) and "u" not in SH._zabal(SH.normalizuj({})[0]) and SH._rozbal(SH._zabal(SH.normalizuj({})[0]))["led_svetlo"] is True, "token modelu nese stav svitidla; vychozi token beze zmeny")
    rl = SH.resolve({"led": False, "ledlight": False})
    check(rl["valid"] and all(s_["id"] != "ledlight" for s_ in SH._souhrn_voleb(rl["selection"], "cs")), "bez LED se svitidlo ve shrnuti neukazuje")
    check(any(i["id"] == "ledlight" for i in SH._souhrn_voleb(r0["selection"], "cs")) and SH.pro_objednavku({"ledlight": False})["ok"], "svitidlo pryc: ve shrnuti a objednavka projde")
    vod = (r0.get("vodici") or {}).get("ovladani") or {}
    menu = [m["text"] for c in vod.get("casti", []) if c["id"] == "led" for m in c["menu"]]
    check(any("Vrátit svítidlo LED" in t_ for t_ in menu), f"3D menu LED nabizi vratit svitidlo ({menu})")
    menu1 = [m["text"] for c in (r1.get("vodici") or {}).get("ovladani", {}).get("casti", []) if c["id"] == "led" for m in c["menu"]]
    check(any("jen svítidlo" in t_ for t_ in menu1), f"3D menu LED nabizi odebrat jen svitidlo ({menu1})")
    for lg in ("en", "sk"):
        rr = SH.resolve({"ledlight": False}, lang=lg)
        check(rr["valid"] and (rr.get("vodici") or {}).get("ovladani"), f"[{lg}] resolve bez svitidla: platne a 3D ovladani se preklada")

print(f"\n{OK} kontrol OK" if not FAILS else f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
sys.exit(1 if FAILS else 0)
