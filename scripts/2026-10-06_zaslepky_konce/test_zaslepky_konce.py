#!/opt/konfigurator/api/venv/bin/python
"""ZASLEPKY NA VOLNE KONCE PROFILU v generatorech stolu (bot8, 2026-10-06; Robert: "v generatorech ... na volne konce profilu se musi automaticky davat zaslepky").

Generator (api/stul_konfigurator.py, `_volne_konce` + krok 3b v `_sestav_jadro_systemu`) da zaslepku systemu (3071 / 3090 / 3091) na kazdy konec profilu, kterého se nedotyka zadny jiny dil
(konce ramen LED, konce pricky nad LED, horni konce zadnich noh bez LED...). Zaslepky pod nohami (kolecka / patky / navlek) maji vlastni mechanismus a zustavaji beze zmeny; SSE stul (system 41)
ma vlastni jadro.

NEZAVISLE MERENI: dotyk konce se tady zjistuje JINAK nez v kodu - vzorkovanim bodu na koncove plose (mrizka 3x3 v prurezu zmensenem o 2 mm, posunuta 1 mm ven a 0,5 mm dovnitr) proti AABB ostatnich
dilu (bez zaslepek volnych koncu); kod pouziva pas pres cely prurez. Pozn.: nezavisle neznamena "jiny vysledek na hrane" - hrany (dotyk presne na 1,5 mm) mrizka nema, proto se pouzivaji dva ruzne prahy.
Co se overuje (mrizka konfiguraci systemu 30 / 35 / 40; SSE ma vlastni test):
  A  zaslepka je prave na volnych koncich (a nikde jinde), klic ("zasl", klic profilu, "+" | "-") jedinecny, dily se stejnym poradim jako bez zaslepek (zaslepky jsou az na konci seznamu)
  B  poloha a otoceni: dil systemu, stred na ose profilu, koncova plocha profilu = vnitrni plocha prirub (konec + vnejsi smer * zaslepka_vyska), lokalni +Z do profilu (zatka)
  C  zadny vedlejsi ucinek: problemy, rozmery, spoje, pocet spoju, parametry stejne jako bez zaslepek; vyrobni vypis nese zaslepky (pocet = pod nohami + volne konce) a montazni krok 8
  D  GLB: pribude presne geometrie zaslepek (pocet vrcholu), material cerna
  E  pomocne funkce (_q_zaslepky: vsech 6 smeru, +Y = stejna rotace jako zaslepky pod nohami)
Spusteni: api/venv/bin/python3 scripts/2026-10-06_zaslepky_konce/test_zaslepky_konce.py       Mutace: scripts/2026-10-06_zaslepky_konce/mutace.py
"""
import itertools
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.environ.get("STUL_API_DIR") or os.path.abspath(os.path.join(HERE, "..", "..", "api"))
sys.path.insert(0, API)
import numpy as np  # noqa: E402
import stul_konfigurator as S  # noqa: E402
import stul_glb  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:300]))


def je_zasl(k):
    return isinstance(k, (list, tuple)) and len(k) == 3 and k[0] == "zasl"


def klic_t(k):
    return tuple(klic_t(x) for x in k) if isinstance(k, (list, tuple)) else k


def bez_zaslepek(**vstup):
    """Stejny stul s vypnutym pridavanim zaslepek na volne konce (puvodni chovani)."""
    puvodni = S._volne_konce
    S._volne_konce = lambda clenove, spojky: []
    try:
        return S.sestav_stul(**vstup)
    finally:
        S._volne_konce = puvodni


def konce_profilu(r):
    """[(index dilu, znak, bod koncove plochy, vnejsi smer)] pro konce vsech profilu (bez sikmych vzper)."""
    sy = r["parametry"]["system"]
    profil = S.SYSTEMY[sy]["profil"]
    out = []
    for i, d in enumerate(r["dily"]):
        k = klic_t(r["klice"][i])
        if d["part_id"] != profil or (isinstance(k, tuple) and k and k[0] == "vz"):
            continue
        R = S.kvat_na_matici(d["quaternion"])
        osa = R @ np.array([0.0, 1.0, 0.0])
        L = 1000.0 * d["scale"][1]
        for znak in (1, -1):
            out.append((i, znak, np.array(d["position"], float) + osa * znak * L / 2.0, osa * znak))
    return out


def dotyk_vzorky(r, i, znak, bod, dvn, bez):
    """Nezavisle: dotyka se konec jineho dilu? mrizka 3x3 bodu v prurezu (zmenseny o 2 mm) ve 2 hladinach (1 mm ven, 0,5 mm dovnitr) proti AABB dilu mimo `bez` (rozsirene o 0,3 mm)."""
    d = r["dily"][i]
    R = S.kvat_na_matici(d["quaternion"])
    a1, a2 = R[:, 0], R[:, 2]
    h = S.SYSTEMY[r["parametry"]["system"]]["profil_mm"] / 2.0 - 2.0
    for t in (1.0, -0.5):
        for u, v in itertools.product((-h, 0.0, h), repeat=2):
            p = bod + dvn * t + a1 * u + a2 * v
            for j, x in enumerate(r["dily"]):
                if j == i or j in bez:
                    continue
                lo, hi = S._aabb(x)
                if np.all(p >= lo - 0.3) and np.all(p <= hi + 0.3):
                    return True
    return False


def konfigurace():
    out = []
    for sy in (30, 35, 40):
        out.append({"system": sy})
        for led, stojky in ((False, True), (True, False), (False, False)):
            out.append({"system": sy, "led": led, "stojky": stojky})
        for sirka, hloubka in ((2400, 800), (2800, 1100), (1600, 1000)):
            out.append({"system": sy, "sirka": sirka, "hloubka": hloubka})
        out.append({"system": sy, "police": 3, "panely": False})
        out.append({"system": sy, "vzpery": True, "stojky_vyska": 1000})
        out.append({"system": sy, "kolecka": False, "patky": True})
        out.append({"system": sy, "kolecka": False, "patky": False})
        out.append({"system": sy, "stredni_opora": "ram", "sirka": 2600})
        out.append({"system": sy, "stredni_opora": "noha", "sirka": 2800, "vyska": 760})
        out.append({"system": sy, "led_rameno": 300, "hloubka": 1000})
        out.append({"system": sy, "stojky_vyska": S.sestav_stul(system=sy)["stojky_meze"]["min"]})          # nejnizsi stojky: spojka u konce ramene nesmi se zaslepkou udelat falesne zanoreni (problemy beze zmeny)
        out.append({"system": sy, "vyrez1": True, "loz": True})
    if 35 in (30, 35, 40):
        out.append({"system": 35, "navlek": True, "navlek_delka": 300})
    return out


KONF = konfigurace()
pocty_volnych = []
chyby_A, chyby_B, chyby_C = [], [], []
for vstup in KONF:
    try:
        r = S.sestav_stul(**vstup)
    except Exception as e:                       # noqa: BLE001
        chyby_A.append((vstup, "vyjimka " + type(e).__name__ + ": " + str(e)[:80]))
        continue
    r0 = bez_zaslepek(**vstup)
    sy = r["parametry"]["system"]
    sd = S.SYSTEMY[sy]
    n0 = len(r0["dily"])
    klice = [klic_t(k) for k in r["klice"]]
    zi = [i for i, k in enumerate(klice) if je_zasl(k)]
    # A: poradi, jedinecnost, stejne dily na zacatku
    if zi != list(range(n0, len(r["dily"]))):
        chyby_A.append((vstup, "zaslepky nejsou na konci", zi[:4], n0))
    if len(set(klice[i] for i in zi)) != len(zi):
        chyby_A.append((vstup, "klic zaslepky neni jedinecny"))
    if r["dily"][:n0] != r0["dily"] or klice[:n0] != [klic_t(k) for k in r0["klice"]]:
        chyby_A.append((vstup, "puvodni dily nebo klice se zmenily"))
    # zaslepky muzou byt jen na koncich profilu; konec je volny <=> ma zaslepku
    zaslepene = {(klice[i][1], klice[i][2]) for i in zi}
    bez = set(zi)
    for i, znak, bod, dvn in konce_profilu(r0):
        k = klice[i]
        ma = (k, "+" if znak > 0 else "-") in zaslepene
        dotyka = dotyk_vzorky(r0, i, znak, bod, dvn, set())
        if ma == dotyka:
            chyby_A.append((vstup, "konec " + str(k) + ("+" if znak > 0 else "-"), "zaslepka" if ma else "bez zaslepky", "dotyk" if dotyka else "volny"))
    kb = {(k, "+" if z > 0 else "-") for i, z, b, d in konce_profilu(r0) for k in [klice[i]]}
    if not zaslepene <= kb:
        chyby_A.append((vstup, "zaslepka na neexistujicim konci", zaslepene - kb))
    pocty_volnych.append(len(zi))
    # B: poloha a otoceni
    for i in zi:
        d = r["dily"][i]
        k = klice[i]
        ip = klice.index(k[1])
        dp = r["dily"][ip]
        R = S.kvat_na_matici(dp["quaternion"])
        osa = R @ np.array([0.0, 1.0, 0.0])
        znak = 1 if k[2] == "+" else -1
        konec = np.array(dp["position"], float) + osa * znak * 1000.0 * dp["scale"][1] / 2.0
        dvn = osa * znak
        Rz = S.kvat_na_matici(d["quaternion"])
        pos = np.array(d["position"], float)
        if d["part_id"] != sd["zaslepka"] or d["scale"] != [1.0, 1.0, 1.0]:
            chyby_B.append((vstup, "dil/meritko", d["part_id"], d["scale"]))
        if np.linalg.norm(pos - (konec + dvn * sd["zaslepka_vyska"])) > 0.01:
            chyby_B.append((vstup, "poloha", k, np.round(pos - (konec + dvn * sd["zaslepka_vyska"]), 3).tolist()))
        if np.linalg.norm(Rz @ np.array([0.0, 0.0, 1.0]) + dvn) > 1e-5:
            chyby_B.append((vstup, "zatka nejde do profilu", k))
        pr = pos - np.array(dp["position"], float)
        if np.linalg.norm(pr - osa * np.dot(pr, osa)) > 0.01:
            chyby_B.append((vstup, "stred mimo osu profilu", k))
    # C: zadny vedlejsi ucinek
    for pole in ("problemy", "rozmery", "spoje", "pocet_spoju", "odebrano"):
        if r[pole] != r0[pole]:
            chyby_C.append((vstup, pole))
    if r["parametry"] != r0["parametry"]:
        chyby_C.append((vstup, "parametry"))
    v, v0 = S.vyrobni_vypis(r), S.vyrobni_vypis(r0)
    q = next((x for x in v["prislusenstvi"] if x["karta_id"] == int(sd["zaslepka"].split("_")[1])), None)
    q0 = next((x for x in v0["prislusenstvi"] if x["karta_id"] == int(sd["zaslepka"].split("_")[1])), None)
    if (q["pocet"] if q else 0) != (q0["pocet"] if q0 else 0) + len(zi):
        chyby_C.append((vstup, "pocet zaslepek ve vypisu", q and q["pocet"], q0 and q0["pocet"], len(zi)))
    krok8 = next((x for x in v["montazni_postup"] if x["krok"] == 8), None)
    if zi and not (krok8 and set(zi) <= set(krok8["dily"])):
        chyby_C.append((vstup, "zaslepky nejsou v kroku 8"))

over(f"A mrizka {len(KONF)} konfiguraci: zaslepka je prave na volnych koncich (nezavisle vzorkovani), jedinecny klic, zaslepky az na konci, ostatni dily a klice stejne", not chyby_A, chyby_A[:4])
over("A2 aspon v nekterych konfiguracich volne konce jsou (test neni prazdny) a ve vychozim stolu jsou prave 4 (konce ramen LED a pricky nad LED)", max(pocty_volnych) >= 4 and len(S.sestav_stul(system=30)["dily"]) - len(bez_zaslepek(system=30)["dily"]) == 4, pocty_volnych)
over("B poloha a otoceni: dil systemu, stred na ose profilu, koncova plocha profilu = vnitrni plocha prirub (konec + smer * vyska), zatka do profilu", not chyby_B, chyby_B[:4])
over("C zadny vedlejsi ucinek: problemy, rozmery, spoje, pocet spoju, odebrano a parametry beze zmeny; vyrobni vypis nese zaslepky a krok 8", not chyby_C, chyby_C[:4])

# D: GLB - pribude presne geometrie zaslepek
chyby_D = []
for vstup in ({"system": 30}, {"system": 35}, {"system": 40}, {"system": 40, "sirka": 2800, "hloubka": 1100}):
    r = S.sestav_stul(**vstup)
    zi = [i for i, k in enumerate(r["klice"]) if je_zasl(klic_t(k))]
    puvodni = S._volne_konce
    S._volne_konce = lambda c, s: []
    try:
        stul_glb._GLB_CACHE.clear()
        g0 = stul_glb.model_pro_parametry(r["parametry"])[1]
    finally:
        S._volne_konce = puvodni
    stul_glb._GLB_CACHE.clear()
    stul_glb._META_CACHE.clear()
    g1 = stul_glb.model_pro_parametry(r["parametry"])[1]
    import json
    import struct

    def vrcholu(glb):
        n = struct.unpack("<I", glb[12:16])[0]
        js = json.loads(glb[20:20 + n])
        return sum(a["count"] for a in js["accessors"] if a["type"] == "VEC3" and "min" in a)
    ocek = len(zi) * len(stul_glb.nacti_mesh(S.SYSTEMY[r["parametry"]["system"]]["zaslepka"])[0])
    if vrcholu(g1) - vrcholu(g0) != ocek:
        chyby_D.append((vstup, vrcholu(g1) - vrcholu(g0), ocek))
over("D GLB: pribude presne geometrie zaslepek (pocet vrcholu), vzdy stejny material cerna (uzel materialu uz existuje)", not chyby_D, chyby_D)

# E: _q_zaslepky
chyby_E = []
for smer in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
    q = S._q_zaslepky(smer)
    Rq = S.kvat_na_matici(q)
    if np.linalg.norm(Rq @ np.array([0.0, 0.0, 1.0]) - np.array(smer, float)) > 1e-6 or abs(np.linalg.det(Rq) - 1.0) > 1e-6 or abs(sum(v * v for v in q) - 1.0) > 1e-9:
        chyby_E.append(smer)
over("E _q_zaslepky: lokalni +Z do zadaneho smeru (vsech 6 os), rotace (det +1), jednotkovy kvaternion", not chyby_E, chyby_E)
qn = S._q_zaslepky((0, 1, 0))
over("E2 smer +Y = stejna rotace jako u zaslepek pod nohami (-90 st. kolem X)", np.allclose(qn, (-0.70710678, 0.0, 0.0, 0.70710678), atol=1e-6), qn)
over("E4 verze pravidel zvysena (zaslepky meni cenu a kusovnik): RULES_VERSION je novejsi nez 2026-10-05.2", stul_glb.RULES_VERSION > "2026-10-05.2", stul_glb.RULES_VERSION)
r = S.sestav_stul(system=41)
over("E3 SSE stul (system 41) ma vlastni jadro: zadne zaslepky volnych koncu navic", not any(je_zasl(klic_t(k)) for k in r["klice"]), None)

ok = sum(vysl)
print(f"\nVYSLEDEK zaslepky na volne konce profilu: {ok}/{len(vysl)} OK  (konfiguraci: {len(KONF)})")
sys.exit(0 if ok == len(vysl) else 1)
