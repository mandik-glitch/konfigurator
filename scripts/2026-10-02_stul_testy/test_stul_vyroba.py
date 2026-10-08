#!/usr/bin/env python3
"""Test VYROBNIHO VYPISU stolu (bot8, 2026-10-03): generator -> kompletni vycet dilu pro vyrobu (Robert: 'generatory maji generovat sestavy, pri objednani
ukladat do DB, obsahovat kompletni vycet dilu aby se dalo vyrobit'; navic: desky s vyrezy, spojovaci material, montazni postup).

Hlida NEZAVISLE na vypisu (z poctu a rozmeru dilu sestavy): rezny plan sedi na profily, desky maji spravne formaty a vyrezy, prislusenstvi a jednotky
sedi na pocty, vsechny dily jsou v montaznim postupu prave jednou, spoje sedi, vypis je JSON, polohy jednotek jsou v desce a mimo vyrezy.
Spusteni: api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_vyroba.py  (STUL_API_OVERRIDE = jina kopie api/)
"""
import json
import os
import sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api"))
import stul_konfigurator as S  # noqa: E402

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")


KONFIGURACE = (
    dict(),
    dict(sirka=2400, hloubka=1000, police=2, suplik=False),
    dict(sirka=2000, hloubka=1000, vyrez1=True, vyrez1_police=True, loz=True, kolecka=False, patky=True, suplik=False),
    dict(vyrez1=True, vyrez2=True, vyrez2_z=500.0, vyrez3=True, vyrez3_z=900.0, vyrez3_w=150.0, loz=True, loz_rozteca=120, loz_okraj=50, kolecka=False),
    dict(sirka=700, hloubka=500, vyska=300, panely=False, led=False, elektrozlab=False, drzak_pet=False, suplik=False),
    dict(presah=100, sirka=1800, police=0, loz=True),
    dict(sirka=1400, vzpery=True, vzpera_delka=420),                                                # sikme vzpery ramen LED: profil + 2 spojky 3254 na vzperu, montazni krok 10
    dict(sirka=2000, panely=False, elektrozlab=False, vzpery=True, vzpera_delka=250, led_rameno=700),
)

for kw in KONFIGURACE:
    r = S.sestav_stul(**kw)
    p = r["parametry"]
    v = S.vyrobni_vypis(r)
    dily = r["dily"]
    n = f"{kw}"
    json.dumps(v)                                                    # musi byt cisty JSON
    check(len(v["role_dilu"]) == len(dily), f"{n}: role pro kazdy dil")
    # --- rezny plan
    prof = [d for d in dily if d["part_id"] in S.PROFIL_PARTS]
    check(sum(q["pocet"] for q in v["rezny_plan"]) == len(prof) and len(v["profily"]) == len(prof), f"{n}: rezny plan obsahuje vsechny profily ({len(prof)})")
    check(abs(sum(q["delka_mm"] * q["pocet"] for q in v["rezny_plan"]) - sum(1000.0 * d["scale"][1] for d in prof)) < 0.05 * len(prof), f"{n}: soucet delek rezneho planu = soucet delek profilu")
    ids = sorted(i for q in v["rezny_plan"] for i in q["id_dilu"])
    check(ids == sorted(i for i, d in enumerate(dily) if d["part_id"] in S.PROFIL_PARTS), f"{n}: kazdy profil je v reznem planu prave jednou")
    check(all(abs(1000.0 * dily[i]["scale"][1] - q["delka_mm"]) < 0.06 for q in v["rezny_plan"] for i in q["id_dilu"]), f"{n}: delky v planu odpovidaji dilum")
    # --- desky: format pracovni desky, vyrezy, spodni police, police pod vyrezem
    hl_ocek, sk_ocek = p["hloubka"] + p["presah"] - 30.0 - S.SYSTEMY[p["system"]]["deska_zkraceni"], p["sirka"]          # system 40: desky o 10 mm kratsi
    # (Robert 2026-10-05: formaty tabuli) sirsi stul (nad prahem) ma pracovni desku DELENOU u stredni opory na dve desky (leva / prava cast), ktere na sebe navazuji bez mezery a obe se vejdou do tabule
    prac = [d for d in v["desky"] if d["deska_id"].startswith("prac_")]
    deleny = p["sirka"] > S.prah_sirky()
    check(len(prac) == (2 if deleny else 1) and all(abs(b["hloubka_mm"] - hl_ocek) < 0.2 for b in prac) and abs(sum(b["sirka_mm"] for b in prac) - sk_ocek) < 0.3,
          f"{n}: pracovni deska {sk_ocek:.0f} x {hl_ocek:.0f} ve {2 if deleny else 1} kusech (ma {[(b['sirka_mm'], b['hloubka_mm']) for b in prac]})")
    check(all(S.deska_se_vejde_do_tabule(b["hloubka_mm"], b["sirka_mm"]) for b in v["desky"]), f"{n}: kazda deska se vejde do tabule {S.tabule()}")
    check([b["role"] for b in prac] == (["pracovní deska – levá část", "pracovní deska – pravá část"] if deleny else ["pracovní deska"]), f"{n}: nazvy desek ({[b['role'] for b in prac]})")
    aktivni_vyrezy = [k for k in range(1, S.MAX_VYREZU + 1) if p[f"vyrez{k}"]]
    vyr_vypis = [q for b in prac for q in b["vyrezy"]]
    check(sorted({q["n"] for q in vyr_vypis}) == aktivni_vyrezy and all(q["od_predniho_okraje_mm"] == p[f"vyrez{q['n']}_x"] and q["hloubka_mm"] == p[f"vyrez{q['n']}_d"] for q in vyr_vypis)
          and all(abs(sum(q["sirka_mm"] for q in vyr_vypis if q["n"] == k) - p[f"vyrez{k}_w"]) < 0.3 and 1 <= sum(1 for q in vyr_vypis if q["n"] == k) <= 2 for k in aktivni_vyrezy),
          f"{n}: vyrezy ve vypisu = parametry ({aktivni_vyrezy}; vyrez pres delici spáru je ve dvou castech, souctem sirka vyrezu)")
    n_desek_dily = sum(1 for d in dily if d["part_id"] == "product_4933") - sum(1 for d in dily if d.get("deska_kus"))
    check(len(v["desky"]) == n_desek_dily, f"{n}: pocet desek ve vypisu = pocet fyzickych desek ({n_desek_dily}), kusy kolem vyrezu se nepocitaji zvlast")
    for k in aktivni_vyrezy:
        if p[f"vyrez{k}_police"]:
            pol = [d for d in v["desky"] if d["role"] == f"police pod výřezem {k}"]
            check(len(pol) == 1 and abs(pol[0]["sirka_mm"] - (p[f"vyrez{k}_w"] + 80.0)) < 0.2 and abs(pol[0]["hloubka_mm"] - (p[f"vyrez{k}_d"] + 80.0)) < 0.2, f"{n}: police pod vyrezem {k} je o 80 mm vetsi nez otvor")
    # --- prislusenstvi: pocty podle dilu sestavy, jednotky na desce a mimo vyrezy
    pocet_dilu = Counter(d["part_id"] for d in dily)
    for q in v["prislusenstvi"]:
        check(q["pocet"] == pocet_dilu["product_%d" % q["karta_id"]] == len(q["id_dilu"]), f"{n}: prislusenstvi {q['nazev']} {q['pocet']} ks")
    check({q["karta_id"] for q in v["prislusenstvi"]} == {int(k.split("_")[1]) for k in pocet_dilu if k not in S.PROFIL_PARTS + ("product_4933",) + S.SPOJKY_PARTS + S.NAVLEK_PARTS}, f"{n}: zadna karta prislusenstvi nechybi ani nepribyva")          # navlek (jekl) a jeho zaslepka nejsou karty katalogu: vypis je ma zvlast (`navlek`)
    loz = [q for q in v["prislusenstvi"] if q["karta_id"] == 3025]
    check(bool(loz) == p["loz"] and (not loz or loz[0]["pocet"] == r["loz"]["pocet"]), f"{n}: loziskove jednotky ve vypisu = {r['loz'] and r['loz']['pocet']}")
    if loz:
        q = loz[0]
        pol = q["polohy_stredu_mm"]
        okraj = p["loz_okraj"]
        check(all(okraj - 0.2 <= x <= hl_ocek - okraj + 0.2 and okraj - 0.2 <= z <= sk_ocek - okraj + 0.2 for x, z in pol), f"{n}: polohy jednotek jsou v desce aspon {okraj:.0f} mm od okraje")
        r_j = S.LOZ_PRUMER / 2.0
        uvnitr = [1 for x, z in pol for k in aktivni_vyrezy
                  if p[f"vyrez{k}_x"] < x + r_j and x - r_j < p[f"vyrez{k}_x"] + p[f"vyrez{k}_d"] and p[f"vyrez{k}_z"] < z + r_j and z - r_j < p[f"vyrez{k}_z"] + p[f"vyrez{k}_w"]]
        check(not uvnitr, f"{n}: zadna jednotka neni v miste vyrezu")
        if deleny:                                                       # jednotka se nevrta pres delici spáru desek
            spara = prac[1]["pocatek_mm"][1]
            check(all(abs(z - spara) >= r_j - 0.01 for x, z in pol), f"{n}: zadna jednotka nelezi na delici spáre desek (z = {spara})")
    # --- spoje a spojovaci material
    check(v["spojovaci_material"]["spoje_profil_profil"] == r["pocet_spoju"] == len(v["spoje"]) and v["spojovaci_material"]["pocet_rohovych_spojek"] == sum(pocet_dilu[x_] for x_ in S.SPOJKY_PARTS), f"{n}: spoje a rohove spojky")
    check(all(dily[a]["part_id"] in S.PROFIL_PARTS and dily[b]["part_id"] in S.PROFIL_PARTS for a, b in v["spoje"]), f"{n}: spoje spojuji profily")
    check(v["spojovaci_material"]["typ_sroubu_a_matic"] is None, f"{n}: typ spojovaciho materialu je poctive oznacen jako neurceny")
    # --- montazni postup: kroky 2-9 deli VSECHNY dily na prave jednou, krok 1 = nareznout profily a pripravit desky
    cisla = [k["krok"] for k in v["montazni_postup"]]
    check(cisla == sorted(cisla) and cisla[0] == 1, f"{n}: kroky jsou serazene od 1")
    pokryti = [i for k in v["montazni_postup"] if k["krok"] > 1 for i in k["dily"]]
    check(sorted(pokryti) == list(range(len(dily))), f"{n}: kazdy z {len(dily)} dilu je v montaznim postupu (kroky 2-9) prave jednou")
    k1 = set(next(k for k in v["montazni_postup"] if k["krok"] == 1)["dily"])
    check(set(ids) <= k1 and all(i in k1 for d in v["desky"] for i in d["id_dilu"]), f"{n}: krok 1 = vsechny profily a desky")
    check(all(k["text"] for k in v["montazni_postup"]), f"{n}: kazdy krok ma text")
    # --- uplnost proti cene: stejne dily jako v polozkach ceny (kromě kusu desky kolem vyrezu, ktere jsou jedna deska)
    ent = Counter(e["part_id"] for e in S.entries_pro_cenu(dily))
    vyp = Counter()
    for q in v["prislusenstvi"]:
        vyp["product_%d" % q["karta_id"]] += q["pocet"]
    for d_ in prof:
        vyp[d_["part_id"]] += 1
    vyp[S.SYSTEMY[r["parametry"]["system"]]["spojka"]] += v["rohove_spojky"]["pocet"]
    vyp["product_4933"] += len(v["desky"])
    check(ent == vyp, f"{n}: vypis obsahuje presne tytez dily jako polozky ceny ({dict(ent - vyp)} / {dict(vyp - ent)})")

# vyrobni list (HTML): vzpery v reznem planu a v prislusenstvi, montazni krok vzper
import stul_vyrobni_list as VL  # noqa: E402
SYS_T = S.VYCHOZI["system"]                                              # system, ve kterem test bezi (spust_v_systemu.py); 30 = vychozi
try:
    if not S.SYSTEMY[SYS_T]["vzpery"]:
        raise StopIteration                                              # system bez sikmych vzper (40): kontrola vyrobniho listu se vzperami se preskoci
    html = VL.html_list({"kod": "STL-TEST", "hash": "x", "parametry": S.sestav_stul(sirka=1400, vzpery=True, vzpera_delka=420)["parametry"], "vypis": S.vyrobni_vypis(S.sestav_stul(sirka=1400, vzpery=True, vzpera_delka=420)),
                          "rules_version": "x", "problemy": [], "valid": True, "kusovnik_katalog": [], "cena_celkem_czk": None, "hmotnost_kg": None, "hmotnost_uplna": True, "hmotnost_chybi": [],
                          "cenovy_souhrn": None, "dily": S.sestav_stul(sirka=1400, vzpery=True, vzpera_delka=420)["dily"]})
    check("vzpěra ramene LED" in html and "420" in html and "Šikmé vzpěry ramen LED" in html and S.SYSTEMY[SYS_T]["vzpera_spojka"].split("_")[1] in html, "vyrobni list: vzpery v reznem planu, v prislusenstvi (karta sikme spojky) a v montaznim postupu")
except StopIteration:
    pass
except Exception as e:                                                  # noqa: BLE001
    check(False, f"vyrobni list se vzperami selhal: {type(e).__name__}: {e}")

# --- hloubka > 900: podpery spodni police a kratsi deska ve vyrobnim vypisu (Robert 2026-10-03) ---
rP = S.sestav_stul(sirka=2000, hloubka=1000, police=1, stredni_opora="noha")                  # (stredni nohy: desky na sebe navazuji bez mezery; vestaveny ram viz nize)
vP = S.vyrobni_vypis(rP)
dly = [x for x in vP["rezny_plan"]]
dp = [q for q in vP["role_dilu"] if "podpěra spodní police" in q[1]]
check(len(dp) == 2, f"vypis hloubka 1000, sirka 2000: 2 podpery police v rolich ({len(dp)})")
PODPERA_L = {30: 791.5, 35: 784.0, 40: 776.5}[SYS_T]                              # delka podpery police pri hloubce 1000: (x_zad - x_pred) - profil; ve 40 o 5 mm kratsi rozteč pricek a o 10 mm vic profil
check(any(x["delka_mm"] == PODPERA_L and x["pocet"] >= 2 for x in dly), f"vypis: rezny plan ma podpery {PODPERA_L} mm x aspon 2 ({[(x['delka_mm'], x['pocet']) for x in dly][:6]})")
dsk = [q for q in vP["desky"] if q["role"].startswith("spodní police")]
KR2 = 2 * (S.SYSTEMY[SYS_T]["profil_mm"] + 1.0)                          # 62 mm (system 30) / 82 mm (system 40): svisly profil bocnice + 1 mm vule z kazde strany
POL_H = 850.0 - S.SYSTEMY[SYS_T]["deska_zkraceni"]                      # deska police pri hloubce 1000: 850 mm (system 30) / 840 mm (system 40)
check(len(dsk) == 2 and abs(sum(q["sirka_mm"] for q in dsk) - (2000.0 - KR2)) < 0.3 and all(q["hloubka_mm"] == POL_H for q in dsk),
      f"vypis: deska police {2000.0 - KR2:.0f} x {POL_H:.0f} mm (o {KR2:.0f} mm uzsi) ve dvou castech u stredni nohy: {[(q['sirka_mm'], q['hloubka_mm']) for q in dsk]}")
k3 = next(k for k in vP["montazni_postup"] if k["krok"] == 3)
check("podpěrné profily" in k3["text"] and f"{KR2:.0f} mm" in k3["text"] and all(rP["klice"].index(["podpera", 0, j]) in k3["dily"] for j in range(2)), "vypis: montazni krok 3 popisuje podpery a zkraceni desky a ma podpery mezi dily")
GAP = S.SYSTEMY[SYS_T]["profil_mm"] + 2 * S.RAM_VULE_VYREZU                                      # u vestaveneho ramu jsou obe casti spodni police kratsi: mezera = svisly profil ramu + 1 mm vule z kazde strany
vR = S.vyrobni_vypis(S.sestav_stul(sirka=2000, hloubka=1000, police=1, stredni_opora="ram"))
dsr = [q for q in vR["desky"] if q["role"].startswith("spodní police")]
check(len(dsr) == 2 and abs(sum(q["sirka_mm"] for q in dsr) - (2000.0 - KR2 - GAP)) < 0.3 and all(q["hloubka_mm"] == POL_H for q in dsr) and all(not q["vyrezy"] for q in dsr),
      f"vypis vestaveny ram: spodni police ve dvou castech, soucet o mezeru {GAP:.0f} mm mensi nez bez ramu: {[(q['sirka_mm'], q['hloubka_mm']) for q in dsr]}")
pracR = [q for q in vR["desky"] if q["deska_id"].startswith("prac_")]
check(len(pracR) == 2 and abs(sum(q["sirka_mm"] for q in pracR) - 2000.0) < 0.3, "vypis vestaveny ram: pracovni deska se NEZKRACUJE (obe casti na sebe navazuji, soucet = sirka stolu)")
vN = S.vyrobni_vypis(S.sestav_stul(sirka=2000, hloubka=900, police=1, stredni_opora="noha"))
check(not [q for q in vN["role_dilu"] if "podpěra spodní police" in q[1]] and abs(sum(q["sirka_mm"] for q in vN["desky"] if q["role"].startswith("spodní police")) - 2000.0) < 0.3,
      "vypis hloubka 900: zadne podpery, deska police siroka jako stul (u stredni nohy ve dvou castech)")

if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"\n{OK} kontrol OK")
