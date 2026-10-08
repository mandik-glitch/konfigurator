#!/usr/bin/env python3
"""Test FORMATU TABULI LAMINODESKY A DELENI DESEK u stredni opory (bot8, 2026-10-05; Robert: "formaty tabuli lamino desky jako jedno kriterium s tim ze deska musi byt delena v miste stredove
nohy resp. vestaveneho ramu (aby nebyl v kolizi musi byt obe strany desek kratsi" a "zkratit je potreba pouze spodni desky u verze vestaveny ram, neni potreba zkracovat ty, co na sebe prubezne navazuji").

NEZAVISLE na kodu generatoru (vse se meri z AABB dilu):
  A) format tabule: vychozi 2070 x 2800, nastaveni z karty (sanitizace), vejde se v obou orientacich, horni mez prahu sirky = delka tabule, meze polohy stredni nohy z delky desky.
  B) deleni: stul nad prahem sirky ma pracovni desku i kazdou polici ve DVOU deskach (leva / prava cast), stul bez stredni opory v jedne; kazda deska se vejde do tabule.
  C) navazuji bez mezery: pracovni deska (u nohy i u ramu), police u stredni nohy; spodni police u vestaveneho ramu: obe casti kratsi, mezera = profil + 2 x vule, vycentrovana na osu ramu.
  D) vyrezy pres delici spáru: kusy bez prekryvu, plocha = deska minus otvory, cena = cena cele desky (stejna jako bez vyrezu), vyrobni vypis po deskach, loziskove jednotky mimo spáru.
  E) mensi tabule (nastavena z karty): deska, ktera se nevejde, je problem `deska_mimo_tabuli`; hash se zmeni jen pri nevychozi tabuli; nic jineho se nezmeni.
  F) 3D ovladani: police a pracovni deska jsou JEDNA cast pres obe poloviny (obalka), tazeni vysky police.
Spusteni z korene repa (bez DB):  api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_desky_tabule.py
V systemu 40:  api/venv/bin/python3 scripts/2026-10-04_system40/spust_v_systemu.py 40 scripts/2026-10-02_stul_testy/test_stul_desky_tabule.py
Vystup "N kontrol OK", exit 0; jinak radky CHYBA, exit 1."""
import itertools
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


SYS_T = S.VYCHOZI["system"]
P = float(S.SYSTEMY[SYS_T]["profil_mm"])                               # tloustka profilu (30 / 40)
MEZERA_RAM = P + 2 * S.RAM_VULE_VYREZU                                  # mezera mezi castmi spodni police u vestaveneho ramu


def bb(d):
    lo, hi = S._aabb(d)
    return np.array(lo, float), np.array(hi, float)


def desky(r, prefix):
    """[(deska_id, [(index, lo, hi), ...])] desek s `deska_id` zacinajicim prefixem, serazene podle id."""
    out = {}
    for i, d in enumerate(r["dily"]):
        if d["part_id"] == "product_4933" and str(d.get("deska_id") or "").startswith(prefix):
            lo, hi = bb(d)
            out.setdefault(d["deska_id"], []).append((i, lo, hi))
    return sorted(out.items())


def obalka(kusy):
    return np.min([k[1] for k in kusy], axis=0), np.max([k[2] for k in kusy], axis=0)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("A) format tabule, prah sirky, meze polohy stredni nohy")
check(S.tabule() == (2070.0, 2800.0) and S.TABULE_VYCHOZI == (2070.0, 2800.0) and S.max_delka_desky() == 2800.0, f"vychozi tabule 2070 x 2800 ({S.tabule()})")
check(S.deska_se_vejde_do_tabule(2800, 2070) and S.deska_se_vejde_do_tabule(2070, 2800) and S.deska_se_vejde_do_tabule(1000, 2800), "deska se vejde v obou orientacich")
check(not S.deska_se_vejde_do_tabule(2801, 1000) and not S.deska_se_vejde_do_tabule(2071, 2071) and not S.deska_se_vejde_do_tabule(1000, 2900), "vetsi deska se nevejde")
try:
    check(S.nastav_tabuli(2800, 2070) == (2070.0, 2800.0), "nastav_tabuli seradi strany (kratsi, delsi)")
    check(S.nastav_tabuli(None, None) == (2070.0, 2800.0) and S.nastav_tabuli("x", 2800) == (2070.0, 2800.0) and S.nastav_tabuli(0, 2500) == (2070.0, 2800.0)
          and S.nastav_tabuli(100, 200) == (2070.0, 2800.0) and S.nastav_tabuli(1000, 9000) == (2070.0, 2800.0), "neplatny / chybejici format = vychozi")
    check(S.nastav_tabuli(1250, 2500) == (1250.0, 2500.0) and S.tabule() == (1250.0, 2500.0) and S.max_delka_desky() == 2500.0, "format z karty (1250 x 2500)")
finally:
    S.nastav_tabuli(None, None)
check(S.tabule() == (2070.0, 2800.0), "tabule vracena na vychozi")
S.nastav_pravidla({"sirka_stredni_noha": 3000})                                      # pravidlo "nikdy": vyssi nez delka tabule se strhne na 2800
try:
    check(S.prah_sirky() == 2800.0, f"prah sirky ma strop = delka tabule ({S.prah_sirky()})")
    r28, r29 = S.sestav_stul(sirka=2800), S.sestav_stul(sirka=2900)
    check(not any(str(d.get("deska_id") or "").endswith("_1") for d in r28["dily"]) and abs(bb(r28["dily"][0])[1][2] - bb(r28["dily"][0])[0][2] - 2800) < 0.1, "2800 mm: jedna deska 2800 (vejde se)")
    check(len(desky(r29, "prac_")) == 2 and not r29["problemy"], "2900 mm: i pri pravidle `nikdy` je stredni opora (a deleni) povinna - deska by se nevesla")
finally:
    S.nastav_pravidla({})
check(S.prah_sirky() == 1500.0, "pravidlo vraceno na vychozi 1500")
for W in (1501, 2000, 2800, 2965, 3000):
    lo, hi = S.stredni_noha_meze(W)
    rozpeti = W - P
    check(abs(lo - max(S.MIN_ODSTUP_STREDNI_NOHY, rozpeti + P / 2 - 2800)) < 1e-6 and abs(hi - min(rozpeti - S.MIN_ODSTUP_STREDNI_NOHY, 2800 - P / 2)) < 1e-6, f"meze polohy stredni nohy u {W} mm: {lo:g}..{hi:g}")
    # obe krajni polohy jdou postavit, jen kousek za nimi ne
    for zm in (lo, hi):
        rr = S.sestav_stul(sirka=W, stredni_noha=zm, stredni_opora="noha", suplik=False, panely=False)               # (bez supliku a panelu: ty by u kraje kolidovaly s nohou i bez desek)
        check(not rr["problemy"] and all(S.deska_se_vejde_do_tabule(*(obalka(k)[1][[0, 2]] - obalka(k)[0][[0, 2]])) for _, k in desky(rr, "pr") + desky(rr, "pol")), f"{W} mm, stredni noha na mezi {zm:g}: bez problemu, desky se vejdou")
    for zm in (lo - 1.0, hi + 1.0):
        try:
            S.sestav_stul(sirka=W, stredni_noha=zm, stredni_opora="noha")
            check(False, f"{W} mm, stredni noha {zm:g} mimo meze se mela odmitnout")
        except S.StulChyba as e:
            check(e.kod == "mimo_rozsah", f"{W} mm, stredni noha {zm:g} mimo meze: StulChyba mimo_rozsah")

# pevna poloha stredni nohy (mm od leve nohy), ktera u sirsiho stolu uz nevyhovuje tabuli (sirka 2830 -> 3000: pravy dil by byl > 2800), nesmi shodit nabidky roztazeni (nahodny vyber ve test_stul_shop)
try:
    nab = S.nabidky_roztazeni(sirka=2830, stredni_noha=168.0, panely=False, suplik=False)
    check(isinstance(nab, dict), "nabidky roztazeni s pevnou polohou stredni nohy u kraje meze nespadnou")
except S.StulChyba as e:
    check(False, f"nabidky roztazeni spadly na StulChyba: {e}")
try:
    S.sestav_stul(sirka=3000, stredni_noha=168.0)
    check(False, "sirka 3000 se stredni nohou 168 mm od leve nohy se mela odmitnout (pravy dil by prekrocil tabuli)")
except S.StulChyba as e:
    check(e.kod == "mimo_rozsah" and "tabule" in str(e), f"sirka 3000 se stredni nohou 168: StulChyba mimo_rozsah s duvodem tabule ({e})")
check(not S.sestav_stul(sirka=2830, stredni_noha=168.0, suplik=False, panely=False)["problemy"], "sirka 2830 se stredni nohou 168 je v poradku")

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("B+C) deleni desek, navazovani, mezera u ramu (mrizka)")
n_mr = 0
for W, D, pol, opora, vyr in itertools.product((1400, 1501, 2000, 2400, 2800, 3000), (500, 800, 1000, 1400), (0, 1, 2), ("noha", "ram"), (False, True)):
    kw = dict(sirka=W, hloubka=D, police=pol, vyska=1100, stredni_opora=opora, suplik=False, panely=False, elektrozlab=False)
    if vyr:
        kw.update(vyrez1=True, vyrez1_w=min(300, W - 200), vyrez1_d=min(200, D - 100), vyrez1_x=40.0, vyrez1_z=W / 2.0 - 400.0)           # vyrez zasahuje do stredu (pres delici spáru)
        if D < 300:
            continue
    r = S.sestav_stul(**kw)
    n_mr += 1
    n = f"{W}x{D} police {pol} {opora}{' + vyrez' if vyr else ''}"
    check(not [p for p in r["problemy"] if p["kod"] != "vyrez_prekryv"], f"{n}: bez problemu ({[(p['kod'], p['text'][:50]) for p in r['problemy'][:1]]})")
    ram = r["panely_info"]["rezim"] == "ram"
    deleny = W > S.prah_sirky()
    prac, pols = desky(r, "prac_"), desky(r, "pol")
    pols = [(i, k) for i, k in pols if not i.startswith("polvyr")]
    check(len(prac) == (2 if deleny else 1) and len(pols) == (2 if deleny else 1) * r["parametry"]["police"], f"{n}: pocet desek: pracovni {len(prac)}, police {len(pols)} (deleny={deleny})")
    # kazda deska se vejde do tabule
    for did, kusy in prac + pols:
        lo, hi = obalka(kusy)
        check(S.deska_se_vejde_do_tabule(hi[0] - lo[0], hi[2] - lo[2]), f"{n}: deska {did} {hi[0] - lo[0]:.0f} x {hi[2] - lo[2]:.0f} se vejde do tabule")
    if not deleny:
        continue
    zm_osa = None
    if ram:
        posty = [bb(d) for i, d in enumerate(r["dily"]) if isinstance(r["klice"][i], list) and r["klice"][i][0] == "ram"]
        zm_osa = float(np.mean([(lo[2] + hi[2]) / 2 for lo, hi in posty])) if posty else None
    else:
        fm = [bb(d) for i, d in enumerate(r["dily"]) if r["klice"][i] == "FM"]
        zm_osa = float((fm[0][0][2] + fm[0][1][2]) / 2) if fm else None
    check(zm_osa is not None, f"{n}: ma stredni oporu ({'ram' if ram else 'nohy'})")
    if zm_osa is None:
        continue
    # pracovni deska: leva a prava cast navazuji PRESNE v ose opory, soucet = sirka stolu (bez mezery - pracovni deska se nezkracuje ani u ramu)
    lo_l, hi_l = obalka(prac[0][1])
    lo_p, hi_p = obalka(prac[1][1])
    check(abs(hi_l[2] - lo_p[2]) < 0.05 and abs(hi_l[2] - zm_osa) < 0.05 and abs((hi_p[2] - lo_l[2]) - W) < 0.1, f"{n}: pracovni deska navazuje v ose opory ({hi_l[2]:.2f} / {lo_p[2]:.2f} / osa {zm_osa:.2f}), celkem {hi_p[2] - lo_l[2]:.1f}")
    # police: u nohy navazuji, u ramu mezera = profil + 2 x vule vycentrovana na osu ramu
    for k_ in range(r["parametry"]["police"]):
        l_, p_ = obalka(pols[2 * k_][1]), obalka(pols[2 * k_ + 1][1])
        mezera = p_[0][2] - l_[1][2]
        if ram:
            check(abs(mezera - MEZERA_RAM) < 0.05 and abs(l_[1][2] - (zm_osa - MEZERA_RAM / 2)) < 0.05 and abs(p_[0][2] - (zm_osa + MEZERA_RAM / 2)) < 0.05,
                  f"{n}: police {k_ + 1} u ramu: mezera {mezera:.2f} mm (ma byt {MEZERA_RAM:g}) vycentrovana na osu ramu")
        else:
            check(abs(mezera) < 0.05 and abs(l_[1][2] - zm_osa) < 0.05, f"{n}: police {k_ + 1} u stredni nohy navazuje bez mezery ({mezera:.3f} mm)")
        check(abs(l_[0][0] - p_[0][0]) < 0.05 and abs(l_[1][0] - p_[1][0]) < 0.05 and abs(l_[0][1] - p_[0][1]) < 0.05, f"{n}: police {k_ + 1}: obe casti stejna hloubka a vyska")
    # soucet delek polic = sirka police - (u ramu) mezera
    for k_ in range(r["parametry"]["police"]):
        sirky = [obalka(pols[2 * k_ + j][1])[1][2] - obalka(pols[2 * k_ + j][1])[0][2] for j in (0, 1)]
        sir_cela = W - (2.0 * (P + 1.0) if D > S.prah_hloubky() else 0.0)
        check(abs(sum(sirky) - (sir_cela - (MEZERA_RAM if ram else 0.0))) < 0.2, f"{n}: police {k_ + 1}: soucet delek {sum(sirky):.1f} = {sir_cela - (MEZERA_RAM if ram else 0.0):.1f}")
print(f"   mrizka: {n_mr} konfiguraci")

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("D) vyrezy pres delici spáru, cena, vyrobni vypis, loziskove jednotky")
kw = dict(sirka=2400, hloubka=1000, vyrez1=True, vyrez1_w=600, vyrez1_d=400, vyrez1_x=300, vyrez1_z=900, stredni_opora="noha", loz=True, loz_rozteca=150, loz_okraj=60, suplik=False)
r = S.sestav_stul(**kw)
check(not r["problemy"], f"vyrez pres spáru: bez problemu ({[p['text'][:60] for p in r['problemy']]})")
prac = desky(r, "prac_")
p_ = r["parametry"]
plocha_cela = (p_["hloubka"] + p_["presah"] - 30.0 - S.SYSTEMY[SYS_T]["deska_zkraceni"]) * p_["sirka"]
ot = sum((v["x1"] - v["x0"]) * (v["z1"] - v["z0"]) for v in r["vyrezy"])
plocha = sum(float((k[2] - k[1])[0] * (k[2] - k[1])[2]) for _, kusy in prac for k in kusy)
check(abs(plocha - (plocha_cela - ot)) < 5.0, f"vyrez pres spáru: kusy obou desek vyplnuji plochu minus otvor ({plocha:.0f} vs {plocha_cela - ot:.0f})")
for v in r["vyrezy"]:
    uvnitr = [k for _, kusy in prac for k in kusy if min(k[2][0], v["x1"]) - max(k[1][0], v["x0"]) > 0.5 and min(k[2][2], v["z1"]) - max(k[1][2], v["z0"]) > 0.5]
    check(not uvnitr, "vyrez pres spáru: pod otvorem neni zadny kus")
for (ida, ka), (idb, kb) in itertools.combinations([(i, k) for i, kusy in prac for k in kusy], 2):
    pr_ = np.minimum(ka[2], kb[2]) - np.maximum(ka[1], kb[1])
    check(not np.all(pr_ > 0.5), f"vyrez pres spáru: kusy {ka[0]} a {kb[0]} se neprekryvaji")
for did, kusy in prac:
    dily_d = [r["dily"][i] for i, _, _ in kusy]
    check(sum(1 for d in dily_d if d.get("deska_celek")) == 1 and sum(1 for d in dily_d if not d.get("deska_celek") and not d.get("deska_kus")) == 0, f"vyrez pres spáru: deska {did} ma prave jeden kus s rozmerem cele desky")
celek = [d["deska_celek"] for d in r["dily"] if d.get("deska_celek")]
check(sorted(round(c[1]) for c in celek) == [1200, 1200] and all(abs(c[0] - (p_["hloubka"] + p_["presah"] - 30.0 - S.SYSTEMY[SYS_T]["deska_zkraceni"])) < 0.01 for c in celek), f"vyrez pres spáru: rozmery cele desky obou casti ({celek})")
e_vyr = [e for e in S.entries_pro_cenu(r["dily"]) if e["part_id"] == "product_4933"]
e_zakl = [e for e in S.entries_pro_cenu(S.sestav_stul(**{k: v for k, v in kw.items() if not k.startswith("vyrez")})["dily"]) if e["part_id"] == "product_4933"]
check(e_vyr == e_zakl, f"cena desek s vyrezem pres spáru = cena desek bez vyrezu ({e_vyr} vs {e_zakl})")
check(sum(d.get("deska_vyrezu", 0) for d in r["dily"]) == 1, "vyrez se pocita prave jednou (u desky, v niz lezi jeho stred)")
v = S.vyrobni_vypis(r)
vp = [d for d in v["desky"] if d["deska_id"].startswith("prac_")]
check([d["role"] for d in vp] == ["pracovní deska – levá část", "pracovní deska – pravá část"] and [d["deska_id"] for d in v["desky"]][:2] == ["prac_0", "prac_1"], f"vypis: nazvy a poradi desek ({[d['role'] for d in v['desky']]})")
vyr_v = [q for d in vp for q in d["vyrezy"]]
check(len(vyr_v) == 2 and abs(sum(q["sirka_mm"] for q in vyr_v) - 600) < 0.1 and all(q["hloubka_mm"] == 400 and q["od_predniho_okraje_mm"] == 300 for q in vyr_v) and all("pozn" in q for q in vyr_v), f"vypis: vyrez rozdeleny mezi obe desky ({vyr_v})")
check(vp[0]["pocatek_mm"] == [0.0, 0.0] and vp[1]["pocatek_mm"][0] == 0.0 and abs(vp[1]["pocatek_mm"][1] - 1200) < 0.1, f"vypis: pocatek prave desky vuci cele ploše ({vp[1]['pocatek_mm']})")
check(sorted(x["deska_id"] for x in v["desky"]) == sorted(set(d["deska_id"] for d in r["dily"] if d.get("deska_id"))), "vypis: kazda deska prave jednou")
vyp_ids = sorted(i for d in v["desky"] for i in d["id_dilu"])
check(vyp_ids == sorted(i for i, d in enumerate(r["dily"]) if d["part_id"] == "product_4933"), "vypis: vsechny kusy desek jsou v nejake desce")
loz = next(q for q in v["prislusenstvi"] if q["karta_id"] == 3025)
spara = vp[1]["pocatek_mm"][1]
check(all(abs(z - spara) >= S.LOZ_PRUMER / 2.0 + S.LOZ_MEZERA_OTVOR - 0.05 for x, z in loz["polohy_stredu_mm"]), f"loziskove jednotky: zadna na delici spáre (z = {spara:.1f}) ani u ni")
check(loz["vynechano"] > 0 and loz["pocet"] == r["loz"]["pocet"], f"loziskove jednotky: nektere vynechany u vyrezu a spáry ({loz['vynechano']})")
import stul_vyrobni_list as VL  # noqa: E402
html = VL.html_list({"kod": "STL-TEST", "hash": "x", "parametry": r["parametry"], "vypis": v, "rules_version": "x", "problemy": [], "valid": True, "kusovnik_katalog": [], "cena_celkem_czk": None,
                     "hmotnost_kg": None, "hmotnost_uplna": True, "hmotnost_chybi": [], "cenovy_souhrn": None, "dily": r["dily"]})
check("pracovní deska – levá část" in html and "pracovní deska – pravá část" in html and "dělené na dvě desky" in html and html.count("<svg") == 2 and "přesahuje do druhé desky" in html, "vyrobni list: desky po castech, 2 nakresy, poznamka o deleni")

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("E) mensi tabule z karty, hash")
H0 = G.kanonicky_hash({})
try:
    S.nastav_tabuli(1250, 2500)
    check(G.kanonicky_hash({}) != H0 and G.kanonicky_hash({}) == G.kanonicky_hash({}), "hash: jina tabule = jiny kod konfigurace")
    check(S.prah_sirky() == 1500.0 and S.stredni_noha_meze(3000)[0] > 150, "mensi tabule: prah zustava, meze polohy se zuzi")
    rh = S.sestav_stul(hloubka=1300)
    pr = [p for p in rh["problemy"] if p["kod"] == "deska_mimo_tabuli"]
    check(len(pr) >= 1 and all(p["rozmer"] == "hloubka" for p in pr) and "tabule" in pr[0]["text"], f"hloubka 1300 se do tabule 1250 x 2500 nevejde: problem deska_mimo_tabuli ({[p['text'] for p in pr][:1]})")
    check(not [p for p in S.sestav_stul(hloubka=900)["problemy"] if p["kod"] == "deska_mimo_tabuli"], "hloubka 900 se vejde")
    rs = S.sestav_stul(sirka=2600, stredni_opora="noha")
    check(not [p for p in rs["problemy"] if p["kod"] == "deska_mimo_tabuli"] and len(desky(rs, "prac_")) == 2, "sirka 2600 se do tabule vejde jen deleni na dve desky (kazda 1300 <= 2500)")
finally:
    S.nastav_tabuli(None, None)
check(G.kanonicky_hash({}) == H0 and S.tabule() == (2070.0, 2800.0), "hash a tabule vraceny na vychozi")

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("F) 3D ovladani: police a pracovni deska jsou jedna cast pres obe poloviny")
for opora in ("noha", "ram"):
    rr = S.sestav_stul(sirka=2400, hloubka=1000, vyska=1100, police=2, stredni_opora=opora, suplik=False)
    ov = S.ovladani_3d(rr)
    cast = {c["id"]: c for c in ov["casti"]}
    ps = [c for c in ov["casti"] if c["id"].startswith("police_") and not c["id"].startswith("police_h")]
    check(len(ps) == rr["parametry"]["police"], f"{opora}: {rr['parametry']['police']} casti polic (je {len(ps)})")
    pols = [(i, k) for i, k in desky(rr, "pol") if not i.startswith("polvyr")]
    for j, c in enumerate(sorted(ps, key=lambda c: c["id"])):
        lo, hi = obalka(pols[2 * j][1] + pols[2 * j + 1][1])
        check(np.allclose(c["aabb"][0], lo, atol=0.2) and np.allclose(c["aabb"][1], hi, atol=0.2), f"{opora}: cast {c['id']} je obalka obou polovin police")
    lo, hi = obalka([k for _, kusy in desky(rr, "prac_") for k in kusy])
    check(np.allclose(cast["deska"]["aabb"][0], lo, atol=0.2) and np.allclose(cast["deska"]["aabb"][1], hi, atol=0.2), f"{opora}: cast `deska` je obalka obou casti pracovni desky")
    tah_h = [t for t in ov["tahy"] if t["id"].startswith("police_h")]
    check(len(tah_h) == rr["parametry"]["police"] and all(len(t["casti"]) == 1 for t in tah_h), f"{opora}: tah vysky ma jednu cast na polici")
    st = next(t for t in ov["tahy"] if t["id"] == "stredni_noha")
    ops = st["zive"]
    ids_nat = {(o["op"], o.get("strana")): set(o["ix"]) for o in ops}
    desky_l = {i for i, d in enumerate(rr["dily"]) if d["part_id"] == "product_4933" and str(d.get("deska_id")).endswith("_0") and not d.get("deska_celek") and not d.get("deska_kus")}
    desky_r = {i for i, d in enumerate(rr["dily"]) if d["part_id"] == "product_4933" and str(d.get("deska_id")).endswith("_1") and not d.get("deska_celek") and not d.get("deska_kus")}
    check(desky_l <= ids_nat.get(("natahni", 1), set()) and desky_r <= ids_nat.get(("natahni", -1), set()), f"{opora}: zive tazeni stredni opory natahuje leve desky pravym koncem a prave levym ({len(desky_l)} + {len(desky_r)})")

if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"\n{OK} kontrol OK")
