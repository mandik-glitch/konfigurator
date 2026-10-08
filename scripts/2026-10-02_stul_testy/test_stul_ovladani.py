#!/usr/bin/env python3
"""Test popisu OVLADANI VE 3D (bot8, 2026-10-03): casti (nabidka pravym tlacitkem, propojeni s panelem) a tahy (drag and drop) - viz docs/OVLADANI_3D.md.

Hlida NEZAVISLE na popisu: kazda polozka nabidky je generatorem pripustna a meni to, co slibuje; meze tahu jsou v rozsahu; FAKTOR tahu odpovida skutecnemu posunu
uchopovaciho bodu v souradnicich GLB (zmena parametru o d => bod se posune po ose o d / faktor); zakazana pasma stredni nohy odpovidaji starsimu vodici.stredni_noha.
Spusteni: api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_ovladani.py  (STUL_API_OVERRIDE = jina kopie api/)
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api"))
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
        print(f"  CHYBA: {msg}")


def ovl(par):
    r = S.odpoved(par)
    return r, G.vodici(par, r)["ovladani"], G.vodici(par, r)


KONF = (dict(), dict(sirka=2000, hloubka=1000, vyrez1=True, vyrez1_police=True, loz=True, stredni_opora="noha"), dict(sirka=2400, vyrez1=True, vyrez2=True, vyrez2_z=600.0, kolecka=False, patky=True, stredni_opora="noha"),
        dict(sirka=2000), dict(sirka=S.panel_limity()["min_sirka_nohy"] + 6, panely_pocet=2, stredni_opora="noha"), dict(panely_pocet=2, panely_posun=40, elzlab_y=50, elzlab_z=60, stojky_vyska=1200), dict(sirka=2200, police=2, hloubka=1000, stredni_opora="ram"),
        dict(sirka=1400, vzpery=True), dict(sirka=2000, panely=False, elektrozlab=False, vzpery=True, vzpera_delka=680, led_rameno=700), dict(sirka=1400, vzpery=True, vzpera_delka=150),
        dict(panely=False, led=False, elektrozlab=False, suplik=False, drzak_pet=False, police=0), dict(sirka=1700, hloubka=950, police=1, suplik=False, stojky=False, panely=False, led=False, elektrozlab=False))

for kw in KONF:
    r, o, v = ovl(kw)
    p = r["parametry"]
    n = str(kw)
    json.dumps(o)
    ids = [c["id"] for c in o["casti"]] + [t["id"] for t in o["tahy"]]
    check(len(ids) == len({*(c["id"] for c in o["casti"])}) + len({*(t["id"] for t in o["tahy"])}) and len({c["id"] for c in o["casti"]}) == len(o["casti"]), f"{n}: id casti jsou jedinecna")
    for c in o["casti"]:
        lo, hi = c["aabb"]
        check(all(a < b for a, b in zip(lo, hi)), f"{n}: {c['id']} ma platny AABB")
        check(all(k in S.VYCHOZI for k in c["param"]), f"{n}: {c['id']} propojeni s panelem jen na existujici parametry ({c['param']})")
        check(c["menu"] and all(m["text"] for m in c["menu"]), f"{n}: {c['id']} ma nabidku s texty")
        for m in c["menu"]:
            if m.get("zakazano"):
                check(m.get("duvod"), f"{n}: {c['id']} zakazana polozka '{m['text']}' ma duvod")
                continue
            if m.get("nastav"):
                novy = {**p, **m["nastav"]}
                try:
                    rr = S.sestav_stul(**novy)
                except Exception as e:                               # noqa: BLE001
                    check(False, f"{n}: {c['id']} / '{m['text']}' vyhodi {e}")
                    continue
                zmena = {k: v for k, v in m["nastav"].items() if rr["parametry"].get(k) != p.get(k)}
                check(zmena or all(p.get(k) == v for k, v in m["nastav"].items()) is False, f"{n}: {c['id']} / '{m['text']}' neco zmeni")
                check(all(k in S.VYCHOZI for k in m["nastav"]), f"{n}: {c['id']} / '{m['text']}' meni jen existujici parametry")
    # --- tahy: meze, rozsah, faktor
    for t in o["tahy"]:
        if t["typ"] == "osa":
            check(t["min"] <= t["hodnota"] <= t["max"] and t["param"] in S.VYCHOZI, f"{n}: tah {t['id']} hodnota {t['hodnota']} v mezich {t['min']}..{t['max']}")
        else:
            check(t["min_x"] <= t["hodnota_x"] <= t["max_x"] and t["min_z"] <= t["hodnota_z"] <= t["max_z"], f"{n}: tah {t['id']} hodnoty v mezich")
        check(t["bod"] and all(abs(c) < 4000 for c in t["bod"]) and t["krok"] > 0 and t["mereni"], f"{n}: tah {t['id']} ma bod, krok a mereni")
        check(all(c in {x["id"] for x in o["casti"]} for c in t.get("casti", [])), f"{n}: tah {t['id']} odkazuje na existujici casti")
    # faktor: zmena parametru o d => bod se v GLB posune po ose o d / faktor
    for t in o["tahy"]:
        if t["typ"] == "osa" and t["id"] != "stredni_noha":
            d = 20.0 if t["hodnota"] + 20.0 <= t["max"] else -20.0
            if not (t["min"] <= t["hodnota"] + d <= t["max"]):                      # uzky rozsah (panely do stran: par mm mezi nohama): nejvetsi krok 10 / 5 / 2 / 1 mm, ktery se do rozsahu vejde
                d = next((sg * dd for dd in (10.0, 5.0, 2.0, 1.0) for sg in (1.0, -1.0) if t["min"] <= t["hodnota"] + sg * dd <= t["max"]), 0.0)
                if d == 0.0:
                    continue
            rr2 = S.odpoved({**p, t["param"]: t["hodnota"] + d})
            v2 = G.vodici({**p, t["param"]: t["hodnota"] + d}, rr2)["ovladani"]
            t2 = next(x for x in v2["tahy"] if x["id"] == t["id"])
            posun = np.array(t2["bod"]) - np.array(t["bod"])
            podel = float(np.dot(posun, np.array(t["osa"])))
            check(abs(podel - d / t["faktor"]) <= (1.5 if abs(d) >= 20.0 else 0.5), f"{n}: tah {t['id']}: zmena {t['param']} o {d:+.0f} posune bod po ose o {podel:.1f} mm (faktor {t['faktor']} => {d / t['faktor']:.1f})")
        elif t["typ"] == "rovina":
            dx = 20.0 if t["hodnota_x"] + 20.0 <= t["max_x"] else -20.0
            dz = 20.0 if t["hodnota_z"] + 20.0 <= t["max_z"] else -20.0
            nov = {**p, t["param_x"]: t["hodnota_x"] + dx, t["param_z"]: t["hodnota_z"] + dz}
            v2 = G.vodici(nov, S.odpoved(nov))["ovladani"]
            t2 = next(x for x in v2["tahy"] if x["id"] == t["id"])
            posun = np.array(t2["bod"]) - np.array(t["bod"])
            check(abs(posun[0] - dx / t["faktor_x"]) <= 1.5 and abs(posun[2] - dz / t["faktor_z"]) <= 1.5, f"{n}: tah {t['id']}: posun bodu ({posun[0]:.1f}, {posun[2]:.1f}) = ({dx / t['faktor_x']:.1f}, {dz / t['faktor_z']:.1f})")
    # stredni noha: zakazana pasma shodna se starsim vodici.stredni_noha
    sn = next((t for t in o["tahy"] if t["id"] == "stredni_noha"), None)
    if sn:
        starsi = v["stredni_noha"]
        check(len(sn["zakazano"]) == len(starsi["zakazano"]) and all(abs(a[0] - (b[0] - starsi["z_levy"])) < 0.2 and abs(a[1] - (b[1] - starsi["z_levy"])) < 0.2 for a, b in zip(sn["zakazano"], starsi["zakazano"])),
              f"{n}: zakazana pasma tahu stredni nohy = vodici.stredni_noha v mm od leve nohy")
        check(abs(sn["mereni"][0]["add"] + sn["mereni"][1]["add"] * 0 - 0) < 1e-9 and sn["mereni"][1]["mul"] == -1.0 and abs(sn["mereni"][1]["add"] - (starsi["z_pravy"] - starsi["z_levy"])) < 0.2, f"{n}: mereni stredni nohy od leve a od prave nohy")
        check(len(sn["casti"]) == (1 if starsi.get("rezim") == "ram" else 2), f"{n}: tah stredni nohy patri ke dvema strednim nohám (u vestavěného rámu k jednomu dílu `ram`)")
    else:
        check(p["sirka"] <= S.SIRKA_STREDNI_NOHY, f"{n}: tah stredni nohy je jen u siroke desky")

# sikme vzpery: cast "vzpery" (jen kdyz jsou zapnute) s nabidkou odebrat / delsi / kratsi; v nabidce LED lze vzpery pridat
if S.SYSTEMY[S.VYCHOZI["system"]]["vzpery"]:
    r, o, v = ovl(dict(sirka=1400, vzpery=True, vzpera_delka=300))
    cv = next((c for c in o["casti"] if c["id"] == "vzpery"), None)
    check(cv and cv["param"] == ["vzpery", "vzpera_delka"] and [m["text"] for m in cv["menu"]] == ["Odebrat vzpěry ramen LED", "Vzpěry delší (+50 mm)", "Vzpěry kratší (−50 mm)"], f"vzpery: cast a nabidka ({cv and [m['text'] for m in cv['menu']]})")
    check(cv["menu"][1]["nastav"] == {"vzpera_delka": 350.0} and cv["menu"][2]["nastav"] == {"vzpera_delka": 250.0} and cv["menu"][0]["nastav"] == {"vzpery": False}, "vzpery: nabidka meni delku o 50 mm / odebira")
    MX30 = S.vzpera_meze(sirka=1400, vzpery=True, vzpera_delka=600)["max"]                  # nejdelsi vzpera pri rameni 560 (system 30: 630 mm, system 40 jina, podle spojky 3220)
    for kw_v, mx in ((dict(sirka=2000, panely=False, elektrozlab=False, vzpery=True, vzpera_delka=1000, led_rameno=1000), 1000.0), (dict(sirka=1400, vzpery=True, vzpera_delka=MX30), MX30)):
        r, o, v = ovl(kw_v)
        cv = next((c for c in o["casti"] if c["id"] == "vzpery"), None)
        check(r["vzpera_meze"]["max"] == mx and cv and cv["menu"][1]["zakazano"] and cv["menu"][1]["duvod"] and not cv["menu"][2]["zakazano"], f"vzpery: nejdelsi vzpera {mx:g} mm (podle ramene) - polozka 'delsi' je zakazana s duvodem")
    r, o, v = ovl(dict(sirka=1400, vzpery=True, vzpera_delka=MX30 - 30.0))
    cv = next((c for c in o["casti"] if c["id"] == "vzpery"), None)
    check(cv["menu"][1]["nastav"] == {"vzpera_delka": MX30} and not cv["menu"][1]["zakazano"], f"vzpery: '+50 mm' 30 mm pod mezi se zastavi na skutecne mezi {MX30:g} (rameno 560; system 30: u 600 na 630)")
    r, o, v = ovl(dict(sirka=1400, vzpery=True, vzpera_delka=100))
    cv = next((c for c in o["casti"] if c["id"] == "vzpery"), None)
    check(cv["menu"][2]["zakazano"] and not cv["menu"][1]["zakazano"], "vzpery: nejkratsi vzpera 100 mm - polozka 'kratsi' je zakazana")
    r, o, v = ovl(dict(sirka=1400))
    check(not any(c["id"] == "vzpery" for c in o["casti"]) and any(m["text"] == "Přidat vzpěry ramen LED" and m["nastav"] == {"vzpery": True} for c in o["casti"] if c["id"] == "led" for m in c["menu"]),
          "bez vzper: zadna cast 'vzpery', v nabidce LED lze vzpery pridat")
else:                                                       # system bez sikmych vzper (40): zapnute vzpery se odeberou, cast ani nabidka neexistuji
    r, o, v = ovl(dict(sirka=1400, vzpery=True, vzpera_delka=300))
    check(not any(c["id"] == "vzpery" for c in o["casti"]) and not r["parametry"]["vzpery"] and any(x_["volba"] == "vzpery" for x_ in r["odebrano"]), "system bez vzper: zapnute vzpery se odeberou a zadna cast vzpery neni")
    r, o, v = ovl(dict(sirka=1400))
    check(not any(m["text"] == "Přidat vzpěry ramen LED" for c in o["casti"] if c["id"] == "led" for m in c["menu"]), "system bez vzper: v nabidce LED neni pridani vzper")
# pokryti casti podle zapnuteho prislusenstvi
r, o, v = ovl(dict(sirka=S.panel_limity()["min_sirka_nohy"] + 6, stredni_opora="noha"))
ic = {c["id"] for c in o["casti"]}
check({"deska", "suplik", "panely", "led", "elektrozlab", "pet", "police_1"} <= ic and sum(1 for i in ic if i.startswith("noha_")) == 6 and "ram" not in ic, f"vse zapnute (stredni nohy, panel v kazdem useku): ma deska, suplik, panely, led, elektrozlab, pet, police a 6 noh ({sorted(ic)[:8]}...)")
r, o, v = ovl(dict(sirka=2000))
ic = {c["id"] for c in o["casti"]}
check({"deska", "suplik", "panely", "led", "elektrozlab", "pet", "police_1", "ram"} <= ic and sum(1 for i in ic if i.startswith("noha_")) == 4, f"sirka 2000 s panelem: vestaveny ram misto strednich noh (cast ram, 4 krajni nohy) ({sorted(ic)[:9]}...)")
r, o, v = ovl(dict(panely=False, led=False, elektrozlab=False, suplik=False, drzak_pet=False, police=0))
ic = {c["id"] for c in o["casti"]}
check(not ({"suplik", "panely", "led", "elektrozlab", "pet", "police_1"} & ic), "vypnute prislusenstvi nema casti")
# menu desky: pridat vyrez sem vybere prvni volny, po treti uz je zakazano
r, o, v = ovl(dict(vyrez1=True, vyrez2=True, vyrez3=True))
dm = next(c for c in o["casti"] if c["id"] == "deska")["menu"]
check(dm[0]["zakazano"] and "nejvíc" in dm[0]["duvod"], "tri vyrezy: 'Pridat vyrez sem' je zakazano s duvodem")
r, o, v = ovl(dict(vyrez1=True))
dm = next(c for c in o["casti"] if c["id"] == "deska")["menu"]
check(dm[0]["nastav"] == {"vyrez2": True} and dm[0]["bod_na_desce"]["x"] == "vyrez2_x", "jeden vyrez: pridat vyrez sem zapne vyrez 2 a ulozi bod do vyrez2_x / vyrez2_z")

if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"\n{OK} kontrol OK")
