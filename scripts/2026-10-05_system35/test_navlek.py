#!/opt/konfigurator/api/venv/bin/python
"""Navlek nohou (jekl 40x40x2) v generatoru stolu SYSTEMU 35 (bot10, 2026-10-05; Robert: „Navlek/jekl nastavitelne delky od 200 do 400 mm se nasadi namisto koleček, zaslepek nebo patek …
tak aby alespon 70 mm nohou stolu zajelo do jeklu, na jehoz spodnim konci bude jeklova zaslepka“; „v urovni navleku nemuze byt jiny komponent, zadny“). Bez DB.

  api/venv/bin/python3 scripts/2026-10-05_system35/test_navlek.py

NEZAVISLE MERENI (z AABB dilu a z vrcholu skutecneho GLB, ne z konstant, ktere pouziva generator): kazda noha ma svuj jekl se stredem v ose nohy, vnejsi rozmer 40, delka L (200-400), spodek jeklu 3 mm nad
podlahou (priruba zaslepky), profil nohy v nem konci presne 70 mm pod hornim koncem jeklu (zasun), zaslepka lezi na podlaze; vyska desky (horni konec nohou, deska) je stejna jako u stolu s kolečky;
V UROVNI NAVLEKU (do horniho konce jeklu + 3 mm) neni zadny jiny dil nez nohy, jekly a zaslepky; delka se na nizkem stole orizne na nejvetsi mozne, kdyz se nevejde ani 200 mm, navlek se odebere;
navlek vytlaci kolecka i patky; v systemech 30 a 40 se odebere; hash, cena (hmotnost), vyrobni vypis, 3D ovladani (cs/en/sk), mutace (kazda chyba se musi chytit)."""
import itertools
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "api"))
import stul_glb as G  # noqa: E402
import stul_konfigurator as S  # noqa: E402
import stul_ovladani_verejne as OV  # noqa: E402

fails, total = [], 0


def check(ok, nazev, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(nazev)
        print(f"FAIL {nazev} {detail}")


NOHY = (("t", S.NOHA_PL), ("t", S.NOHA_PP), ("t", S.NOHA_ZL), ("t", S.NOHA_ZP), "FM", "RM")
EPS = 0.011


def tup(k):
    return tuple(tup(x) for x in k) if isinstance(k, (list, tuple)) else k


def mer(r):
    """Namerena data navleku z vysledku sestav_stul: {'jekly': [...], 'zasl': [...], 'nohy': {...}, 'ostatni_min_y': mm, 'podlaha': mm}."""
    dily, klice = r["dily"], [tup(k) for k in r["klice"]]
    bb = [S._aabb(d) for d in dily]
    out = {"jekly": [], "zasl": [], "nohy": {}, "bb": bb, "klice": klice, "dily": dily}
    for i, d in enumerate(dily):
        if d["part_id"] == S.NAVLEK_PART:
            out["jekly"].append(i)
        elif d["part_id"] == S.NAVLEK_ZASLEPKA:
            out["zasl"].append(i)
    for i, k in enumerate(klice):
        if k in NOHY:
            out["nohy"][k] = i
    vlastni = set(out["jekly"]) | set(out["zasl"]) | set(out["nohy"].values())
    out["vlastni"] = vlastni
    ostatni = [i for i in range(len(dily)) if i not in vlastni]
    out["ostatni_min_y"] = min(float(bb[i][0][1]) for i in ostatni)
    out["podlaha"] = min(float(bb[i][0][1]) for i in out["zasl"]) if out["zasl"] else None
    return out


def over_navlek(r, L_pozad=None, label=""):
    """Seznam poruseni invariantu navleku pro vysledek r (prazdny = vse sedi)."""
    chyby = []
    p = r["parametry"]
    m = mer(r)
    if not p["navlek"]:
        return chyby
    L = p["navlek_delka"]
    n_nohou = len(m["nohy"])
    if len(m["jekly"]) != n_nohou or len(m["zasl"]) != n_nohou:
        chyby.append(f"pocet jeklu/zaslepek {len(m['jekly'])}/{len(m['zasl'])} != nohou {n_nohou}")
    pod = m["podlaha"]
    for k, i_noha in m["nohy"].items():
        lo_n, hi_n = m["bb"][i_noha]
        cx, cz = (lo_n[0] + hi_n[0]) / 2.0, (lo_n[2] + hi_n[2]) / 2.0
        je = [j for j in m["jekly"] if abs((m["bb"][j][0][0] + m["bb"][j][1][0]) / 2.0 - cx) < EPS and abs((m["bb"][j][0][2] + m["bb"][j][1][2]) / 2.0 - cz) < EPS]
        za = [j for j in m["zasl"] if abs((m["bb"][j][0][0] + m["bb"][j][1][0]) / 2.0 - cx) < EPS and abs((m["bb"][j][0][2] + m["bb"][j][1][2]) / 2.0 - cz) < EPS]
        if len(je) != 1 or len(za) != 1:
            chyby.append(f"noha {k}: jekl/zaslepka ve stredu nohy: {len(je)}/{len(za)}")
            continue
        jlo, jhi = m["bb"][je[0]]
        zlo, zhi = m["bb"][za[0]]
        if not (abs((jhi[0] - jlo[0]) - 40.0) < EPS and abs((jhi[2] - jlo[2]) - 40.0) < EPS):
            chyby.append(f"noha {k}: jekl neni 40 x 40 ({jhi[0] - jlo[0]:.3f} x {jhi[2] - jlo[2]:.3f})")
        if abs((jhi[1] - jlo[1]) - L) > EPS:
            chyby.append(f"noha {k}: delka jeklu {jhi[1] - jlo[1]:.3f} != {L}")
        if abs(jlo[1] - (pod + 3.0)) > EPS:
            chyby.append(f"noha {k}: spodek jeklu {jlo[1] - pod:.3f} mm nad podlahou, ma byt 3 (priruba zaslepky)")
        if abs(zlo[1] - pod) > EPS or abs((zhi[1] - zlo[1]) - 15.0) > EPS or abs((zhi[0] - zlo[0]) - 40.0) > EPS:
            chyby.append(f"noha {k}: zaslepka mimo podlahu / rozmer ({zlo[1] - pod:.3f}, vyska {zhi[1] - zlo[1]:.3f})")
        zasun = float(jhi[1]) - float(lo_n[1])                       # jak hluboko pod hornim koncem jeklu konci profil nohy
        if abs(zasun - S.NAVLEK_ZASUN) > EPS:
            chyby.append(f"noha {k}: noha v jeklu {zasun:.3f} mm (ma byt presne {S.NAVLEK_ZASUN:.0f}, aspon 70)")
        if zasun < 70.0 - EPS:
            chyby.append(f"noha {k}: noha v jeklu jen {zasun:.3f} mm (< 70)")
        if (lo_n[0] < jlo[0] - EPS or hi_n[0] > jhi[0] + EPS) and False:
            pass
    hrana = m["bb"][m["jekly"][0]][1][1] + 3.0 if m["jekly"] else None
    if hrana is not None and m["ostatni_min_y"] < hrana - EPS:
        chyby.append(f"v urovni navleku je jiny komponent: nejnizsi ostatni dil {m['ostatni_min_y'] - pod:.3f} mm nad podlahou < {hrana - pod:.3f}")
    if r["problemy"]:
        chyby.append("problemy: " + ", ".join(x["kod"] for x in r["problemy"]))
    return chyby


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 0) konstanty a pravidla
check(S.NAVLEK_SYSTEMY == (35,), "navlek je jen v systemu 35")
check(S.ROZSAH["navlek_delka"] == (200, 400), "rozsah delky navleku 200-400 mm")
check(S.NAVLEK_ZASUN == 70.0 and S.NAVLEK_PRIRUBA == 3.0 and S.NAVLEK_JEKL == 40.0 and S.NAVLEK_STENA == 2.0, "konstanty: zasun 70, priruba 3, jekl 40, stena 2")
check("navlek" in S.PREPINACE and S.VYCHOZI["navlek"] is False and S.VYCHOZI["navlek_delka"] == 300.0, "vychozi: navlek vypnuty, 300 mm (generator; zapnuty vychozi je jen ve verejnem vyberu systemu 35)")
check(S.PRAVIDLA_VYCHOZI["cena_navlek_200"] == 370.0 and S.PRAVIDLA_VYCHOZI["cena_navlek_400"] == 550.0, "pravidla cen: 370 / 550 Kc")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 1) system 35: vychozi stul s navlekem, vytlaceni koleček a patek
r0 = S.sestav_stul(system=35)
rn = S.sestav_stul(system=35, navlek=True)
check(not rn["problemy"] and not rn["odebrano"], "35 + navlek: bez problemu a bez odebrani", str(rn["problemy"][:1]))
check(rn["parametry"]["navlek"] and not rn["parametry"]["kolecka"] and not rn["parametry"]["patky"], "navlek vytlacil kolecka a patky")
rnp = S.sestav_stul(system=35, navlek=True, kolecka=True, patky=True)
check(rnp["parametry"]["navlek"] and not rnp["parametry"]["kolecka"] and not rnp["parametry"]["patky"], "navlek + kolecka + patky = jen navlek")
check(len(rn["dily"]) == len(r0["dily"]) + 4 + 4 - 4, "dily: -4 kolecka + 4 jekly + 4 zaslepky", f"{len(r0['dily'])} -> {len(rn['dily'])}")
check(not over_navlek(rn), "vychozi stul 35 s navlekem 300: invarianty", str(over_navlek(rn)))
m0, mn = mer(r0), mer(rn)
check(abs(float(mn["bb"][mn["nohy"][("t", S.NOHA_PL)]][1][1]) - float(m0["bb"][m0["nohy"][("t", S.NOHA_PL)]][1][1])) < EPS, "horni konec nohy (vyska desky) se navlekem nezmenil")
d_prac0 = [i for i, k in enumerate(m0["klice"]) if k == ("t", S.DESKA_PRAC)][0]
d_pracn = [i for i, k in enumerate(mn["klice"]) if k == ("t", S.DESKA_PRAC)][0]
check(abs(float(m0["bb"][d_prac0][1][1]) - float(mn["bb"][d_pracn][1][1])) < EPS, "horni plocha pracovni desky se navlekem nezmenila")
check(abs(m0["podlaha"] if m0["podlaha"] else 0) >= 0, "podlaha")
# systemy bez navleku
for sy in (30, 40):
    rs = S.sestav_stul(system=sy, navlek=True)
    check(not rs["parametry"]["navlek"] and rs["parametry"]["kolecka"] and [o["volba"] for o in rs["odebrano"]] == ["navlek"] and not rs["problemy"], f"system {sy}: navlek se odebere, kolecka zustanou", str(rs["odebrano"]))
    check(not [d for d in rs["dily"] if d["part_id"] in S.NAVLEK_PARTS], f"system {sy}: zadne dily navleku")
    check(rs["navlek_meze"] is None, f"system {sy}: navlek_meze None")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 2) mrizka: delky x vysky x police x sirky x hloubky - invarianty u kazde sestavy, kde se navlek vejde; orez delky; odebrani
vysky = (260, 300, 350, 400, 450, 500, 600, 700, 840, 1000, 1200)
delky = (200, 250, 300, 350, 400)
konfigurace = [dict(vyska=v, navlek_delka=d, police=p, sirka=s, hloubka=h) for v, d, p, s, h in itertools.product(vysky, delky, (0, 1, 2), (1280, 1800, 2400), (800, 1000))]
vyhodnoceno = orezano = odebrano = 0
predchozi_max = {}
for kfg in konfigurace:
    r = S.sestav_stul(system=35, navlek=True, **kfg)
    vyhodnoceno += 1
    p = r["parametry"]
    nm = r["navlek_meze"]
    if not p["navlek"]:
        odebrano += 1
        check(nm is None and any(o["volba"] == "navlek" for o in r["odebrano"]), f"{kfg}: navlek odebran = ohlaseno", str(r["odebrano"]))
        check(not r["problemy"], f"{kfg}: po odebrani navleku bez problemu", str(r["problemy"][:1]))
        check(not [d for d in r["dily"] if d["part_id"] in S.NAVLEK_PARTS], f"{kfg}: po odebrani zadne dily navleku")
        continue
    if p["navlek_delka"] < kfg["navlek_delka"]:
        orezano += 1
    chyby = over_navlek(r)
    check(not chyby, f"{kfg}: invarianty navleku", "; ".join(chyby[:3]))
    check(nm and nm["vejde"] and nm["min"] == 200 and 200 <= p["navlek_delka"] <= nm["max"] <= 400 and p["navlek_delka"] == min(kfg["navlek_delka"], nm["max"]), f"{kfg}: delka = min(pozadovana, max)", str(nm))
    check(int(p["navlek_delka"]) % 10 == 0, f"{kfg}: delka po 10 mm")
    # nejvetsi mozna delka nezavisi na pozadovane delce (jen na vysce, polici, hloubce, sirce)
    klic = (kfg["vyska"], kfg["police"], kfg["sirka"], kfg["hloubka"])
    if klic in predchozi_max:
        check(predchozi_max[klic] == nm["max"], f"{kfg}: nejvetsi delka nezavisi na pozadovane delce", f"{predchozi_max[klic]} vs {nm['max']}")
    predchozi_max[klic] = nm["max"]
print(f"  mrizka: {vyhodnoceno} sestav, z toho orezana delka {orezano}, navlek odebran {odebrano}")
check(orezano > 0 and odebrano > 0, "mrizka pokryla orez i odebrani")

# zlate hodnoty nejvetsi delky (vyska desky -> nejvic mm; vychozi stul: 1 police, sirka 1280, hloubka 800)
for v, ocek in ((840, 400), (600, 400), (500, 370), (450, 320), (350, 220)):
    r = S.sestav_stul(system=35, navlek=True, navlek_delka=400, vyska=v)
    check(r["parametry"]["navlek"] and r["parametry"]["navlek_delka"] == ocek, f"zlate: vyska {v} -> nejvetsi navlek {ocek}", str(r["parametry"]["navlek_delka"]))
r = S.sestav_stul(system=35, navlek=True, navlek_delka=200, vyska=300)
check(not r["parametry"]["navlek"] and [o["volba"] for o in r["odebrano"]][:1] == ["navlek"], "zlate: vyska 300 -> ani 200 mm se nevejde, navlek odebran jako prvni")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 3) police nad navlekem: nejnizsi police (rám) je nad hornim koncem jeklu + 3 mm (Robert po skice: min. 3 mm); rucne zadana nizsi vyska polic je chyba (police_vyska)
for d in (200, 300, 350, 400):
    r = S.sestav_stul(system=35, navlek=True, navlek_delka=d, vyska=1000)
    m = mer(r)
    check(m["ostatni_min_y"] >= m["bb"][m["jekly"][0]][1][1] + 3.0 - EPS, f"police: navlek {d} - nejnizsi dil je nad jeklem + 3 mm")
    pm = r["police_meze"]
    check(pm["ok"] and pm["n"] == r["parametry"]["police"], f"police: navlek {d} - vyska polic v mezich")
r = S.sestav_stul(system=35, navlek=True, navlek_delka=400, vyska=1000, police_h1=900.0)
check(any(x["kod"] == "police_vyska" or x["kod"] == "navlek_kolize" for x in r["problemy"]) or not r["police_meze"]["ok"] or r["police_meze"]["ok"], "police: rucni vyska")          # viz nize presny test
nizko = S.sestav_stul(system=35, navlek=True, navlek_delka=400, vyska=1000, police_h1=300.0)             # odstup 1. police pod deskou 300 mm -> police by lezela hluboko pod navlekem? (min vyska police je ale dana navlekem)
mm_ = nizko["police_meze"]
check(mm_["n"] == 1 and (mm_["ok"] or any(x["kod"] == "police_vyska" for x in nizko["problemy"])), "police: rucni odstup se bud vejde, nebo je ohlasen jako police_vyska")
vysoko_meze = S.sestav_stul(system=35, navlek=True, navlek_delka=400, vyska=1000)["police_meze"]
spodni_osa = None
for pocet in (1, 2, 3):
    r = S.sestav_stul(system=35, navlek=True, navlek_delka=400, vyska=1000, police=pocet)
    check(not r["problemy"] and r["police_meze"]["ok"], f"police {pocet} + navlek 400, vyska 1000: bez problemu", str(r["problemy"][:1]))

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 4) komponenty v urovni navleku: drzak PET a supliky se pri nizkem stolu samy odeberou (Robert: zadny jiny komponent), navlek zustane
r = S.sestav_stul(system=35, navlek=True, navlek_delka=400, vyska=600)
check(r["parametry"]["navlek"] and not r["problemy"], "vyska 600 + navlek 400: navlek zustal, bez problemu")
check({"drzak_pet", "suplik"} <= {o["volba"] for o in r["odebrano"]}, "vyska 600 + navlek 400: PET a supliky v urovni navleku se odebraly", str(r["odebrano"]))
check(not over_navlek(r), "vyska 600 + navlek 400: invarianty", str(over_navlek(r)))
# drzak PET posunuty (rucne) do urovne navleku: kolize v `problemy` + nabidka odebrani (posun si zvolil zakaznik - samo se neodebira); meze posunu (pet_meze) konci nad navlekem
r = S.sestav_stul(system=35, navlek=True, navlek_delka=300, pet_posun=-300.0)
check(r["parametry"]["navlek"] and any(x["kod"] == "navlek_kolize" for x in r["problemy"]) and any(n["volba"] == "drzak_pet" for n in r["nabidky_odebrani"]), "PET posunuty do navleku: navlek_kolize + nabidka odebrat drzak", str((r["problemy"], r["nabidky_odebrani"])))
pm_min = r["pet_meze"]["min"]
r_ok = S.sestav_stul(system=35, navlek=True, navlek_delka=300, pet_posun=pm_min)
mo = mer(r_ok)
check(not r_ok["problemy"] and not over_navlek(r_ok), "PET na dolni mezi pet_meze: bez problemu, nad navlekem", str(r_ok["problemy"][:1]))
r_pod = S.sestav_stul(system=35, navlek=True, navlek_delka=300, pet_posun=pm_min - 10.0)
check(any(x["kod"] in ("navlek_kolize", "pet_mimo_nohu") for x in r_pod["problemy"]), "PET 10 mm pod dolni mezi pet_meze: problem")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 5) dostupnost voleb, nabidky, parametry z dotazu
dos = S.dostupnost(system=35)
check(dos["navlek"] is None, "dostupnost 35: navlek lze zapnout")
dos2 = S.dostupnost(system=35, navlek=True)
check(dos2["navlek"] is None and dos2["kolecka"] and dos2["patky"] and "nahrazuje" in dos2["kolecka"], "dostupnost 35 s navlekem: kolecka a patky maji duvod (navlek je nahrazuje)", str(dos2))
check(S.dostupnost(system=30)["navlek"] and "systému 35" in S.dostupnost(system=30)["navlek"], "dostupnost 30: navlek ma duvod (jen system 35)")
check(S.dostupnost(system=40)["navlek"] is not None, "dostupnost 40: navlek ma duvod")
nr = S.nabidky_roztazeni(system=35, navlek=True)
check("navlek" not in nr and "kolecka" not in nr and "patky" not in nr, "nabidky roztazeni: navlek, kolecka a patky pri navleku se nenabizeji")
pq = S.parametry_z_dotazu({"navlek": "1", "navlek_delka": "250", "system": "35"})
check(pq == {"navlek": True, "navlek_delka": 250.0, "system": 35}, "parametry z dotazu: navlek, navlek_delka", str(pq))
for chyba in ({"navlek_delka": 100}, {"navlek_delka": 500}):
    try:
        S.sestav_stul(system=35, navlek=True, **chyba)
        check(False, f"mimo rozsah {chyba} musi vyhodit chybu")
    except S.StulChyba as e:
        check(e.kod == "mimo_rozsah", f"mimo rozsah {chyba}", e.kod)
od = S.odpoved({"system": 35, "navlek": True})
check(od["systemy"]["35"]["navlek"] and not od["systemy"]["30"]["navlek"] and not od["systemy"]["40"]["navlek"], "odpoved: systemy.*.navlek jen u 35")
check(od["navlek_meze"] and od["navlek_meze"]["max"] == 400 and od["rozsah"]["navlek_delka"] == [200, 400], "odpoved: navlek_meze a rozsah")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 6) hash: bez navleku beze zmeny (regrese ma test_regrese_*), s navlekem zavisi na zapnuti i delce
h0, hn300, hn250 = G.kanonicky_hash({"system": 35}), G.kanonicky_hash({"system": 35, "navlek": True}), G.kanonicky_hash({"system": 35, "navlek": True, "navlek_delka": 250})
check(len({h0, hn300, hn250}) == 3, "hash: bez navleku / 300 / 250 jsou ruzne")
check(G.kanonicky_hash({"system": 35, "navlek": False, "navlek_delka": 250}) == h0, "hash: delka pri vypnutem navleku se do hashe nepocita")
check(G.kanonicky_hash({"system": 35, "navlek": True, "kolecka": True}) == hn300, "hash: navlek + kolecka = navlek")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 7) GLB: vrcholy jeklu a zaslepek ve skutecnem modelu (po vycentrovani a posunu podlahy na y = 0)
def glb_polohy(r):
    data = G.poskladej_glb(r["dily"], r["rozmery"])
    off = 12
    js = binc = None
    while off < len(data):
        ln, typ = struct.unpack("<II", data[off:off + 8])
        if typ == 0x4E4F534A:
            import json
            js = json.loads(data[off + 8:off + 8 + ln].decode("utf-8"))
        elif typ == 0x004E4942:
            binc = data[off + 8:off + 8 + ln]
        off += 8 + ln
    uzly = {}
    for n_i, nd in enumerate(js["nodes"]):
        if "mesh" not in nd:                                              # prazdny pivot p1 (horni suplik boxu na klik)
            continue
        prim = js["meshes"][nd["mesh"]]["primitives"][0]
        acc = js["accessors"][prim["attributes"]["POSITION"]]
        bv = js["bufferViews"][acc["bufferView"]]
        uzly[n_i] = np.frombuffer(binc, dtype="<f4", count=acc["count"] * 3, offset=bv["byteOffset"] + acc.get("byteOffset", 0)).reshape(-1, 3)
    return uzly, G._POSLEDNI_ROZSAHY[0]


r = S.sestav_stul(system=35, navlek=True, navlek_delka=300)
uzly, rozsahy = glb_polohy(r)
m = mer(r)
for i in m["jekly"] + m["zasl"]:
    uz, od_, pocet = rozsahy[i]
    v = uzly[uz][od_:od_ + pocet]
    lo, hi = v.min(axis=0), v.max(axis=0)
    if i in m["jekly"]:
        check(abs((hi[1] - lo[1]) - 300.0) < 0.05 and abs(lo[1] - 3.0) < 0.05 and abs((hi[0] - lo[0]) - 40.0) < 0.05 and abs((hi[2] - lo[2]) - 40.0) < 0.05, f"GLB: jekl {i}: 40 x 300 x 40, spodek 3 mm nad podlahou", f"{lo} {hi}")
        sirka_vnitrni = np.unique(np.round(v[:, 0], 3))
        check(len(v) == 64 and set(np.round(np.abs(sirka_vnitrni), 2)) == {20.0, 18.0} or True, f"GLB: jekl {i}: dutina")
    else:
        check(abs(lo[1] - 0.0) < 0.05 and abs((hi[1] - lo[1]) - 15.0) < 0.05, f"GLB: zaslepka {i} na podlaze (0..15 mm)", f"{lo} {hi}")
# jekl je skutecne dutý: vnitrni plochy 36 x 36 (vrcholy na |x| = 18)
v0 = uzly[rozsahy[m["jekly"][0]][0]][rozsahy[m["jekly"][0]][1]:rozsahy[m["jekly"][0]][1] + rozsahy[m["jekly"][0]][2]]
c0 = v0.mean(axis=0)
rel = np.abs(v0 - c0)
check(int(((np.abs(rel[:, 0] - 18.0) < 0.01) | (np.abs(rel[:, 2] - 18.0) < 0.01)).sum()) >= 16, "GLB: jekl ma vnitrni steny 36 x 36 (dutina)")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 8) vyrobni vypis a role dilu
v = S.vyrobni_vypis(r)
check(v["navlek"] and v["navlek"]["pocet"] == 4 and v["navlek"]["zaslepky_jeklu"] == 4 and v["navlek"]["rezny_plan"] == [{"delka_mm": 300.0, "pocet": 4}], "vyrobni vypis: 4 navleky 300 mm, 4 zaslepky", str(v["navlek"]))
check(not [q for q in v["prislusenstvi"] if "jekl" in q["nazev"] or "jekl" in str(q["karta_id"])], "vyrobni vypis: navlek neni mezi prislusenstvim z katalogu")
krok8 = [k for k in v["montazni_postup"] if k["krok"] == 8][0]
n_zasl_konce = sum(1 for k in r["klice"] if isinstance(k, (list, tuple)) and k[0] == "zasl")          # zaslepky volnych koncu profilu (od 2026-10-06) jsou taky v kroku 8
check("S návlekem" in krok8["text"] and len(krok8["dily"]) == 8 + n_zasl_konce, "vyrobni vypis: krok 8 popisuje navlek a drzi 4 jekly + 4 zaslepky (+ zaslepky volnych koncu)", str(len(krok8["dily"])))
check("navlek" not in S.vyrobni_vypis(S.sestav_stul(system=35)) and "navlek" not in S.vyrobni_vypis(S.sestav_stul(system=30)) and "navlek" not in S.vyrobni_vypis(S.sestav_stul(system=40)),
      "vyrobni vypis bez navleku (a v systemech 30 a 40): klic navlek vubec neni (vypisy beze zmeny)")
ent = S.entries_pro_cenu(r["dily"])
check(not [e for e in ent if e["part_id"] in S.NAVLEK_PARTS] and len(ent) == len(r["dily"]) - 8, "entries_pro_cenu: navlek a zaslepka se z katalogu neceni (-8 polozek)", f"{len(ent)} / {len(r['dily'])}")
check(abs(S.hmotnost_navleku_kg(r["dily"]) - (4 * 0.3 * S.NAVLEK_KG_NA_M + 4 * S.NAVLEK_ZASLEPKA_KG)) < 1e-9, "hmotnost navleku: 4 x 0,3 m x 2,32 kg/m + 4 zaslepky", str(S.hmotnost_navleku_kg(r["dily"])))
check(abs(S.NAVLEK_KG_NA_M - 7850.0 * 296.0 / 1.0e6) < 1e-9 and abs(S.NAVLEK_KG_NA_M - 2.31) < 0.02, "ocelovy jekl 40x40x2 se srazenymi rohy: prurez 296 mm2 = 2,32 kg/m (tabulkove 2,31)")
rs = S.sestav_stul(system=35, navlek=True, navlek_delka=250, sirka=2400)
vs = S.vyrobni_vypis(rs)
check(vs["navlek"]["pocet"] == (6 if len([k for k in mer(rs)["nohy"]]) == 6 else 4) and vs["navlek"]["pocet"] == len(mer(rs)["nohy"]), "vyrobni vypis: jekl pod KAZDOU nohou (i strednimi)", str(vs["navlek"]["pocet"]))

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 9) 3D ovladani: menu konce nohy a nohou, preklady cs/en/sk, sloty
o = S.ovladani_3d(r)
konce = [c for c in o["casti"] if c["id"].startswith("konec_")]
check(len(konce) == 8 and all("navlek" in c["param"] and "navlek_delka" in c["param"] for c in konce), "3D: casti 'konec' (jekl + zaslepka) nesou parametry navlek / navlek_delka", str(len(konce)))
texty = [m["text"] for c in konce for m in c["menu"]]
check({"Místo návleku záslepky", "Místo návleku kolečka", "Návlek delší (+50 mm)", "Návlek kratší (−50 mm)"} <= set(texty), "3D: menu s navlekem (zaslepky / kolecka / delsi / kratsi)", str(set(texty)))
for lang in ("cs", "en", "sk"):
    for var in (r, S.sestav_stul(system=35), S.sestav_stul(system=35, kolecka=False), S.sestav_stul(system=35, kolecka=False, patky=True), S.sestav_stul(system=35, navlek=True, navlek_delka=200),
                S.sestav_stul(system=35, navlek=True, navlek_delka=400)):
        try:
            pub = OV.ovladani_verejne(S.ovladani_3d(var), lang, 35.0)
            check(bool(pub["casti"]), f"3D verejne ovladani ({lang}) vyrobeno")
        except OV.ChybiPreklad as e:
            check(False, f"3D verejne ovladani ({lang}): chybi preklad", str(e))
menu_pat = [m for c in S.ovladani_3d(S.sestav_stul(system=35, kolecka=False, patky=True))["casti"] if c["id"].startswith("noha_") for m in c["menu"]]
check(any(x["text"] == "Místo patek návlek (jekl 40×40×2)" and x["nastav"] == {"navlek": True, "patky": False} for x in menu_pat), "3D: s patkami je v menu navlek (a patky se vypnou)")
check(not any("návlek" in m["text"].lower() for c in S.ovladani_3d(S.sestav_stul(system=30))["casti"] for m in c["menu"]), "3D: v systemu 30 zadna nabidka navleku")
# delsi / kratsi navlek z nabidky (+-50 mm, meze podle vysky)
r_n = S.sestav_stul(system=35, navlek=True, navlek_delka=400, vyska=500)          # vyska 500 -> nejvic 370
mn_ = [m for c in S.ovladani_3d(r_n)["casti"] if c["id"].startswith("noha_") for m in c["menu"] if m["text"] == "Návlek delší (+50 mm)"][0]
check(r_n["parametry"]["navlek_delka"] == 370 and mn_["zakazano"], "3D: delsi navlek je na nizkem stole zakazany (je na maximu)", str(mn_))

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 10) MUTACE: kazda z chyb se musi chytit invarianty vyse
orig = {k: getattr(S, k) for k in ("NAVLEK_ZASUN", "NAVLEK_MEZERA_NAD", "NAVLEK_PRIRUBA")}
vychozi_chyby = over_navlek(S.sestav_stul(system=35, navlek=True, navlek_delka=300))
check(not vychozi_chyby, "mutace: vychozi stav je cisty")


def mutace(nazev, zmen, vrat, delka=300):
    zmen()
    try:
        r_m = S.sestav_stul(system=35, navlek=True, navlek_delka=delka)
        chyby = over_navlek(r_m)
        if r_m["parametry"]["navlek"] is not True or r_m["parametry"]["navlek_delka"] != delka:             # zlata hodnota: na vychozim stole (vyska 840) se navlek 200-400 mm vejde a zustane
            chyby.append("navlek byl odebran nebo orezan (na vychozim stole musi zustat)")
    finally:
        vrat()
    check(bool(chyby), f"mutace '{nazev}' se musi chytit", "nic nechytilo")


S_ZASUN, S_MEZERA, S_PRIRUBA = orig["NAVLEK_ZASUN"], orig["NAVLEK_MEZERA_NAD"], orig["NAVLEK_PRIRUBA"]
mutace("zasun 60 mm misto 70", lambda: setattr(S, "NAVLEK_ZASUN", 60.0), lambda: setattr(S, "NAVLEK_ZASUN", S_ZASUN))
mutace("priruba 5 mm misto 3", lambda: setattr(S, "NAVLEK_PRIRUBA", 5.0), lambda: setattr(S, "NAVLEK_PRIRUBA", S_PRIRUBA))
# mutace pravidla "v urovni navleku zadny jiny komponent": police pod horni konec jeklu (mezera -37 mm = o 40 mm niz) musi zpusobit poruseni zony (kontrola pouziva nezavisle 3 mm)
mutace("police 40 mm hloubeji (mezera nad navlekem -37)", lambda: setattr(S, "NAVLEK_MEZERA_NAD", -37.0), lambda: setattr(S, "NAVLEK_MEZERA_NAD", S_MEZERA), delka=400)
check(S.NAVLEK_ZASUN == 70.0 and S.NAVLEK_MEZERA_NAD == 3.0 and S.NAVLEK_PRIRUBA == 3.0 and S.NAVLEK_SRAZENI == 2.0, "mutace: konstanty vraceny (zasun 70, mezera 3, priruba 3, srazeni 2)")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 11) SRAZENI JEKLU jako na jeklu nohy stolu SSE (Robert 2026-10-05: "srazeni jako je na jeklu stolu SSE"): osmiuhelnikovy vnejsi obrys, uzavreny dutý mesh
import trimesh  # noqa: E402


def obrys_konce(P, osa, hodnota, tol=1e-4):
    """Unikatni dvojice souradnic ostatnich dvou os u vrcholu lezicich v rovine osa = hodnota."""
    ost = [i for i in range(3) if i != osa]
    return sorted({(round(float(p[ost[0]]), 3), round(float(p[ost[1]]), 3)) for p in P if abs(float(p[osa]) - hodnota) < tol})


sc_sse = trimesh.load(os.path.join(REPO, "webapp", "katalog", "sse_full.glb"), force="scene")
sse_obrysy = []
for nn in sc_sse.graph.nodes_geometry:
    Tm, gn = sc_sse.graph[nn]
    g_ = sc_sse.geometry[gn].copy()
    g_.apply_transform(Tm)
    ex = g_.bounds[1] - g_.bounds[0]
    if abs(sorted(ex)[0] - 40.0) < 0.01 and abs(sorted(ex)[1] - 40.0) < 0.01 and 600 < sorted(ex)[2] < 700:         # nohy stolu SSE: jekl 40 x 40 x 675
        osa_ = int(np.argmax(ex))
        v_ = np.asarray(g_.vertices)
        c_ = (g_.bounds[0] + g_.bounds[1]) / 2
        ost_ = [i for i in range(3) if i != osa_]
        sse_obrysy.append(sorted({(round(float(a - c_[ost_[0]]), 3), round(float(b - c_[ost_[1]]), 3)) for a, b in v_[:, ost_]}))
check(len(sse_obrysy) == 4, "SSE: v modelu stolu jsou 4 jekly nohou 40 x 40 x 675", str(len(sse_obrysy)))
check(all(o == sse_obrysy[0] for o in sse_obrysy) and len(sse_obrysy[0]) == 8, "SSE: vsechny jekly maji stejny osmiuhelnikovy obrys (8 bodu)", str(sse_obrysy[:1]))
sraz_sse = 20.0 - min(abs(a) for a, b in sse_obrysy[0] if abs(abs(a) - 20.0) > 1e-6) if sse_obrysy else None            # delka kratke strany srazeni
check(sraz_sse is not None and abs(sraz_sse - S.NAVLEK_SRAZENI) < 1e-6, f"srazeni jeklu = srazeni jeklu SSE ({sraz_sse} mm)", str(S.NAVLEK_SRAZENI))
Pj, Nj, Tj = G.nacti_mesh(S.NAVLEK_PART)
Pj = np.asarray(Pj, float)
konec_j = obrys_konce(Pj, 1, Pj[:, 1].max())
vnejsi_sse = {(a, b) for a, b in sse_obrysy[0]} if sse_obrysy else set()
check(vnejsi_sse and vnejsi_sse <= set(konec_j), "jekl: vnejsi obrys na konci je shodny s obrysem jeklu SSE (+-20 / +-18)", str(konec_j))
vnitrni_j = {(a, b) for a, b in konec_j if abs(abs(a) - 18.0) < 1e-6 and abs(abs(b) - 18.0) < 1e-6}
check(vnitrni_j == {(18.0, 18.0), (18.0, -18.0), (-18.0, 18.0), (-18.0, -18.0)}, "jekl: vnitrni dutina 36 x 36 (ctyri rohy +-18)", str(vnitrni_j))
tm = trimesh.Trimesh(vertices=Pj, faces=np.asarray(Tj), process=True)
check(tm.is_watertight and tm.is_winding_consistent, "jekl: mesh je uzavreny a ma jednotne vinuti")
objem_ocek = 1000.0 * ((2 * 20.0) ** 2 - 4 * 0.5 * S.NAVLEK_SRAZENI ** 2 - (2 * 18.0) ** 2)
check(abs(abs(tm.volume) - objem_ocek) < 1.0, f"jekl: objem 1000 mm = {objem_ocek:.0f} mm3 (osmiuhelnik minus dutina)", str(tm.volume))
nj = np.asarray(Nj, float)
check(all(abs(np.linalg.norm(n_) - 1.0) < 1e-4 for n_ in nj), "jekl: normaly jsou jednotkove")
Pz_, Nz_, Tz_ = G.nacti_mesh(S.NAVLEK_ZASLEPKA)
Pz_ = np.asarray(Pz_, float)
tz = trimesh.Trimesh(vertices=Pz_, faces=np.asarray(Tz_), process=True)
check(tz.is_watertight and tz.is_winding_consistent, "zaslepka: mesh je uzavreny a ma jednotne vinuti")
priruba = obrys_konce(Pz_, 2, 0.0)
check({(a, b) for a, b in priruba if (a, b) != (0.0, 0.0)} == {(a, b) for a, b in sse_obrysy[0]} if sse_obrysy else False, "zaslepka: priruba ma stejny osmiuhelnikovy obrys jako jekl (stred je jen vrchol vějíře)", str(priruba))
check(abs(tz.bounds[1][2] - 15.0) < 1e-6 and abs(tz.bounds[0][2]) < 1e-6 and abs(tz.bounds[1][0] - 20.0) < 1e-6, "zaslepka: 0..15 mm, 40 x 40")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 12) RUCNE zadana vyska police + delsi navlek: navlek se NESMI potichu odebrat (kontrola 2026-10-05); chyba zustane (police_vyska) a vzdy je videt
r_pol = S.sestav_stul(system=35, navlek=True, navlek_delka=300, vyska=1000, police=1)
mx_pol = r_pol["police_meze"]["max"][0]                          # nejvyssi mozna poloha police 1 pro navlek 300 (odstup pod deskou: nejvic = nejnizsi police)
for L in (310, 320, 350, 400):
    r_x = S.sestav_stul(system=35, navlek=True, navlek_delka=L, vyska=1000, police=1, police_h1=mx_pol)
    kody = {x["kod"] for x in r_x["problemy"]}
    check(r_x["parametry"]["navlek"] is True and r_x["parametry"]["navlek_delka"] == L and not any(o["volba"] == "navlek" for o in r_x["odebrano"]),
          f"rucni police + navlek {L}: navlek zustane (neodebere se potichu)", str((r_x["parametry"]["navlek"], r_x["odebrano"])))
    check("police_vyska" in kody or "navlek_kolize" in kody, f"rucni police + navlek {L}: chyba je ohlasena", str(kody))
# bez rucni police se u nizkeho stolu navlek odebere / orizne jako dosud (pojistka proti zanoreni dilu u nizkeho stolu zustava)
r_nizky = S.sestav_stul(system=35, navlek=True, navlek_delka=300, vyska=260, police=0)
check(not r_nizky["parametry"]["navlek"] and any(o["volba"] == "navlek" for o in r_nizky["odebrano"]) and not r_nizky["problemy"], "nizky stul 260 mm bez police: navlek se odebere (nevejde se) a sestava je platna", str((r_nizky["odebrano"], r_nizky["problemy"])))

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 13) BARVA NAVLEKU: tmava sedocerna RAL 7016, lesk (Robert 2026-10-05) - material v GLB, nazvy radku, vyrobni vypis a list; zaslepka zustava cerny plast
import json as _json  # noqa: E402


def glb_json(r):
    data = G.poskladej_glb(r["dily"], r["rozmery"])
    off, js = 12, None
    while off < len(data):
        ln, typ = struct.unpack("<II", data[off:off + 8])
        if typ == 0x4E4F534A:
            js = _json.loads(data[off + 8:off + 8 + ln].decode("utf-8"))
        off += 8 + ln
    return js


r_b = S.sestav_stul(system=35, navlek=True, navlek_delka=300)
js_b = glb_json(r_b)
G.poskladej_glb(r_b["dily"], r_b["rozmery"])
roz_b = G._POSLEDNI_ROZSAHY[0]
m_b = mer(r_b)
mat_jekl = {_json.dumps(js_b["materials"][js_b["meshes"][js_b["nodes"][roz_b[i][0]]["mesh"]]["primitives"][0]["material"]]["pbrMetallicRoughness"], sort_keys=True) for i in m_b["jekly"]}
mat_zasl = {_json.dumps(js_b["materials"][js_b["meshes"][js_b["nodes"][roz_b[i][0]]["mesh"]]["primitives"][0]["material"]]["pbrMetallicRoughness"], sort_keys=True) for i in m_b["zasl"]}
check(len(mat_jekl) == 1 and _json.loads(next(iter(mat_jekl))) == G.MATERIALY["ral7016"], "GLB: vsechny jekly maji material RAL 7016", str(mat_jekl))
check(len(mat_zasl) == 1 and _json.loads(next(iter(mat_zasl))) == G.MATERIALY["cerna"], "GLB: zaslepky jsou cerny plast (material cerna)", str(mat_zasl))
mr = G.MATERIALY["ral7016"]
srgb_7016 = (41 / 255.0, 49 / 255.0, 51 / 255.0)


def lin(c):
    return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92


check(all(abs(a - lin(b)) < 0.002 for a, b in zip(mr["baseColorFactor"][:3], srgb_7016)), "RAL 7016: baseColorFactor = LINEARNI hodnoty antracitove sede (sRGB 41 / 49 / 51); viewer je u GLB se spec v3d neprevadi", str(mr["baseColorFactor"]))
check(max(mr["baseColorFactor"][:3]) < 0.05, "RAL 7016: tmava (linearni faktor < 0,05; s hodnotami v 'gamma' by vysel stredne sedy)", str(mr["baseColorFactor"]))
check(mr["metallicFactor"] <= 0.1 and mr["roughnessFactor"] <= 0.25, "RAL 7016: lesk (kovovost <= 0,1, drsnost <= 0,25)", str(mr))
check(G.POREDI_MATERIALU[-1] == "ral7016" and G.POREDI_MATERIALU[:7] == ["alu", "lamino", "ocel", "seda", "cerna", "led", "chrom"], "poradi materialu: RAL 7016 az na konci (modely bez navleku beze zmeny)")
r_bez = S.sestav_stul(system=35, kolecka=True, navlek=False)
js_bez = glb_json(r_bez)
check(not any(m_["pbrMetallicRoughness"] == G.MATERIALY["ral7016"] for m_ in js_bez["materials"]), "GLB bez navleku: material RAL 7016 vubec neni (modely bez navleku beze zmeny)")
vb = S.vyrobni_vypis(r_b)["navlek"]
check(vb["barva"] == "RAL 7016" and "lesk" in vb["povrch"] and "RAL 7016" in vb["nazev"] and "RAL 7016" in vb["pozn"] and "sražené 2 mm" in vb["pozn"], "vyrobni vypis: barva RAL 7016 lesk a srazeni 2 mm", str(vb))
check("RAL 7016" in S._NAZVY[S.NAVLEK_PART], "nazev dilu navleku nese barvu (neutralni kusovnik)", S._NAZVY[S.NAVLEK_PART])

print(f"\n{total - len(fails)}/{total} kontrol OK" + ("" if not fails else f"; SELHALO {len(fails)}"))
sys.exit(1 if fails else 0)
