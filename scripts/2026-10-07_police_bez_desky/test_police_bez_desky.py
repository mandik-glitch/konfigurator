#!/usr/bin/env python3
"""Test volby 'spodni police BEZ DESKY' v jadru generatoru stolu (bot8, 2026-10-07; Robert: "spodni police nech ma volbu byt bez desky, jen profily / ram").

Hermeticky (zadna DB, zadny zapis). Hlida:
  A) parametr `police_deska` (vychozi True, normalizace, dotaz staff API, ucinna hodnota bez polic, SSE ho ignoruje, hash),
  B) VYCHOZI chovani beze zmeny: kazda ctvrta-az-tricata konfigurace mrizky = zlaty otisk PRED zavedenim volby (golden_head.json; uplna mrizka v test_police_bez_desky_zlato.py),
  C) BEZ DESKY na mrizce konfiguraci (system x sirka x hloubka x vyska x police x stredni opora + vyrezy + prislusenstvi): zadna deska spodni police, zadne podpery pod ni, VSE ostatni
     (poloha, otoceni, meritko) beze zmeny, nove rohove spojky jen tam, kde drive prekazela deska, zadny novy problem, kusovnik pro cenu = puvodni bez desek a podper, kotvy kot,
     3D ovladani (cast police, nabidka Odebrat / Vratit desku, tahy vysek polic), vyrobni vypis (texty montaze), GLB,
  D) zive tazeni vysky police bez desky = model ze serveru (operace aplikovane na puvodni GLB),
  E) verejna podoba 3D ovladani (nazev slotu shelfboard, preklady cs / en / sk).
Spusteni: api/venv/bin/python3 scripts/2026-10-07_police_bez_desky/test_police_bez_desky.py     (env STUL_API_OVERRIDE = jiny adresar api; POLICE_TEST_KROK = krok vyberu z mrizky, vychozi 5)"""
import importlib.util
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _spolecne as C  # noqa: E402

S, G, K = C.nacti_generator()
import numpy as np  # noqa: E402
import stul_ovladani_verejne as OV  # noqa: E402

KROK = int(os.environ.get("POLICE_TEST_KROK", "5"))
OK, FAILS = 0, []


def check(cond, msg, detail=""):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg} {detail}")


def tup(k):
    return tuple(tup(x) for x in k) if isinstance(k, (list, tuple)) else k


def klice(r):
    return [tup(k) for k in r["klice"]]


def je_deska_police(k):
    if k == ("t", S.DESKA_POLICE):
        return True
    if isinstance(k, tuple) and len(k) == 2 and k[0] == "kusp":
        return True
    return isinstance(k, tuple) and len(k) == 3 and k[0] == "polic" and (k[2] == ("t", S.DESKA_POLICE) or (isinstance(k[2], tuple) and len(k[2]) == 2 and k[2][0] == "kusp"))


def je_podpera(k):
    return isinstance(k, tuple) and len(k) == 3 and k[0] == "podpera"


def je_spojka(k):
    return isinstance(k, tuple) and len(k) >= 2 and k[0] in ("s", "n", "sk")


def aabb(d):
    return S._aabb(d)


def _podpis(d):
    return (d["part_id"], tuple(round(float(x), 3) for x in d["position"]), tuple(round(float(x), 4) for x in d["quaternion"]))


def stejne(d1, d2, eps=1e-6):
    return (d1["part_id"] == d2["part_id"] and np.allclose(d1["position"], d2["position"], atol=eps) and np.allclose(d1["quaternion"], d2["quaternion"], atol=eps)
            and np.allclose(d1["scale"], d2["scale"], atol=eps))


# ---------------------------------------------------------------------------------------------------------------------
print("A) parametr police_deska")
check(S.VYCHOZI["police_deska"] is True, "A1: vychozi hodnota True (police s deskou)")
check(S._norm_parametry({})["police_deska"] is True, "A2: normalizace bez zadani = True")
check(S._norm_parametry({"police_deska": False})["police_deska"] is False and S._norm_parametry({"police_deska": 0})["police_deska"] is False and S._norm_parametry({"police_deska": 1})["police_deska"] is True,
      "A3: normalizace prijme ano/ne (bool, 0 / 1)")
check(S.parametry_z_dotazu({"police_deska": "0"})["police_deska"] is False and S.parametry_z_dotazu({"police_deska": "1"})["police_deska"] is True
      and S.parametry_z_dotazu({"police_deska": "false"})["police_deska"] is False and S.parametry_z_dotazu({"police_deska": "true"})["police_deska"] is True, "A4: dotaz staff API (?police_deska=0 / 1 / false / true)")
try:
    S.sestav_stul(police_deska_neexistuje=1)
    check(False, "A5: neznamy parametr se dal odmita")
except S.StulChyba:
    check(True, "A5: neznamy parametr se dal odmita")
r_nic = S.sestav_stul(police=0, police_deska=False)
r_nic0 = S.sestav_stul(police=0)
check(r_nic["parametry"]["police_deska"] is True and C.fp(r_nic["dily"]) == C.fp(r_nic0["dily"]) and G.kanonicky_hash(r_nic["parametry"]) == G.kanonicky_hash(r_nic0["parametry"])
      and G.kanonicky_hash({"police": 0, "police_deska": False}) == G.kanonicky_hash({"police": 0}),
      "A6: bez spodnich polic volba nic nedela (ucinny parametr True, stejne dily a STEJNY hash)")
r_sse = S.sestav_stul(system=41, sirka=2000, police=1, police_deska=False)
r_sse0 = S.sestav_stul(system=41, sirka=2000, police=1)
check(r_sse["parametry"]["police_deska"] is True and C.fp(r_sse["dily"]) == C.fp(r_sse0["dily"]) and G.kanonicky_hash(r_sse["parametry"]) == G.kanonicky_hash(r_sse0["parametry"]),
      "A7: stul SSE (system 41) volbu ignoruje (police lezi primo na spojnicich): stejne dily i hash")
check(G.kanonicky_hash({"police": 1, "police_deska": False}) != G.kanonicky_hash({"police": 1}) and G.kanonicky_hash({"police": 1, "police_deska": True}) == G.kanonicky_hash({"police": 1}),
      "A8: hash: bez desky se lisi, s deskou (vyslovne True i vychozi) je stejny")
check(G.kanonicky_hash({"police": 2, "vyska": 1150, "police_deska": False}) != G.kanonicky_hash({"police": 2, "vyska": 1150, "police_deska": True}),
      "A9: hash rozlisuje i u vice polic")

# ---------------------------------------------------------------------------------------------------------------------
print("B) vychozi chovani beze zmeny (vyber z mrizky proti zlatemu otisku pred zavedenim volby)")
zlato = json.load(open(C.GOLDEN, encoding="utf-8"))
konf = list(C.mrizka())
check(set(C.klic_konfigurace(p) for p in konf) == set(zlato["mrizka"]), "B0: stejna mrizka konfiguraci jako zlaty otisk")
spatne = []
vybrano = konf[::max(1, KROK * 6)]
for p in vybrano:
    ted = C.otisky(S, G, K, C.vysledek(S, p), zlato.get("klice_parametru"))
    z = zlato["mrizka"][C.klic_konfigurace(p)]
    if not C.shoduje(ted, z):
        spatne.append((p, [k for k in set(ted) | set(z) if ted.get(k) != z.get(k)]))
    if not isinstance(C.vysledek(S, p), str):                                                              # vyslovne True = vychozi (stejne dily i hash)
        a = C.vysledek(S, {**p, "police_deska": True})
        b = C.vysledek(S, p)
        if C.fp(a["dily"]) != C.fp(b["dily"]) or G.kanonicky_hash(a["parametry"]) != G.kanonicky_hash(b["parametry"]):
            spatne.append((p, ["police_deska=True se lisi od vychoziho"]))
check(not spatne, f"B1: {len(spatne)} z {len(vybrano)} vybranych konfiguraci se lisi od stavu pred zavedenim volby", str(spatne[:2]))
print(f"   ({len(vybrano)} konfiguraci)")
for kl, h in zlato["glb"].items():
    p = json.loads(kl)
    if p.get("system") == 41 or p.get("vyrez1"):
        continue
    import hashlib  # noqa: E402
    r = C.vysledek(S, p)
    check(hashlib.sha256(G.model_pro_parametry(r["parametry"], razitka=False)[1]).hexdigest()[:20] == h, f"B2: GLB vychoziho stolu {kl} beze zmeny")

# ---------------------------------------------------------------------------------------------------------------------
print("C) police BEZ DESKY na mrizce konfiguraci")
chyby_c = []
nove_spojky = 0
zruzene_podpery = 0
zruzene_spojky = 0
pocet = 0
uvolnene = []
UVOLNITELNE = {"suplik", "suplik_pocet", "police", "drzak_pet", "pet_posun", "suplik_posun"}
vyber = [p for i, p in enumerate(konf) if i % KROK == 0] + [p for p in konf[1152:]]
def kontrola(p):
    """Vsechny kontroly sekce C pro jednu konfiguraci p (s deskou vs. police_deska=False)."""
    global pocet, nove_spojky, zruzene_podpery, zruzene_spojky
    a = C.vysledek(S, p)
    if isinstance(a, str) or not a["parametry"]["police"] or a["parametry"]["system"] == 41:
        return
    ja = f"{json.dumps(p, sort_keys=True)}"
    try:
        b = S.sestav_stul(**{**C.stary_pocet(S), **p, "police_deska": False})
    except S.StulChyba as e:
        chyby_c.append((ja, f"bez desky StulChyba: {e}"))
        return
    pocet += 1
    ka, kb = klice(a), klice(b)
    ia, ib = {k: i for i, k in enumerate(ka)}, {k: i for i, k in enumerate(kb)}
    desky_a = [k for k in ka if je_deska_police(k)]
    podpery_a = [k for k in ka if je_podpera(k)]
    if not desky_a:
        chyby_c.append((ja, "vychozi stul nema desku police"))
        return
    # 1) zadna deska spodni police, zadne podpery pod ni; ostatni desky (pracovni, police pod vyrezem) zustavaji
    if any(je_deska_police(k) for k in kb) or any(je_podpera(k) for k in kb):
        chyby_c.append((ja, "stul bez desky ma desku / podpery police"))
    if any(str(d.get("deska_id") or "").startswith("pol") and not str(d.get("deska_id")).startswith("polvyr") for d in b["dily"]):
        chyby_c.append((ja, "deska_id spodni police v dilech bez desky"))
    # 2) UVOLNENI: deska police (18 mm) mohla branit prislusenstvi (vyssi suplikovy box, drzak PET) - bez desky se vejde vic a ucinne parametry se lisi; tehdy se dily neporovnavaji po jednom
    dif = {k for k in a["parametry"] if k != "police_deska" and a["parametry"][k] != b["parametry"][k]}
    if dif - UVOLNITELNE:
        chyby_c.append((ja, f"bez desky se zmenily i jine ucinne parametry: {sorted(dif - UVOLNITELNE)}"))
    if dif:
        uvolnene.append(sorted(dif))
    if "police" in dif and not ({"suplik", "suplik_pocet"} & dif):
        chyby_c.append((ja, "pocet polic se zmenil bez zmeny supliku"))
    # 2b) kazdy NE-spojkovy dil, ktery nebyl odebran, je beze zmeny; spojky se porovnavaji podle dilu / polohy / otoceni (klic ("n", index) se muze posunout)
    if not dif:
        odebrane = set(desky_a) | set(podpery_a)
        for k in ka:
            if k in odebrane or je_spojka(k):
                continue
            if k not in ib:
                chyby_c.append((ja, f"dil {k} zmizel"))
            elif not stejne(a["dily"][ia[k]], b["dily"][ib[k]]):
                chyby_c.append((ja, f"dil {k} se zmenil"))
        for k in kb:
            if k not in ia and not je_spojka(k):
                chyby_c.append((ja, f"pribyl dil {k}, ktery neni spojka"))
        sa = {}
        for k in ka:
            if je_spojka(k):
                sa.setdefault(_podpis(a["dily"][ia[k]]), []).append(k)
        sb = {}
        for k in kb:
            if je_spojka(k):
                sb.setdefault(_podpis(b["dily"][ib[k]]), []).append(k)
        podpery_bb = [aabb(a["dily"][ia[q]]) for q in podpery_a]
        desky_bb = [aabb(a["dily"][ia[q]]) for q in desky_a]
        for pod, kl in sa.items():                                  # spojka puvodniho stolu, ktera v novem chybi: musi se dotykat odebrane podpery
            for _ in range(len(kl) - len(sb.get(pod, []))):
                lo, hi = aabb(a["dily"][ia[kl[0]]])
                if not any(np.all(np.minimum(hi, h2) - np.maximum(lo, l2) > -3.0) for l2, h2 in podpery_bb):
                    chyby_c.append((ja, f"spojka {kl[0]} zmizela mimo odebranou podperu"))
                zruzene_spojky += 1
        zruzene_podpery += len(podpery_a)
        for pod, kl in sb.items():                                  # NOVA spojka: drive ji vynechala deska police (prekryva se s drivejsi deskou) a nezanori se do zadneho prislusenstvi / desky
            for _ in range(len(kl) - len(sa.get(pod, []))):
                k = kl[0]
                nove_spojky += 1
                lo, hi = aabb(b["dily"][ib[k]])
                if not any(np.all(np.minimum(hi, h2) - np.maximum(lo, l2) > S.TOL_PRUNIK_MM) for l2, h2 in desky_bb):
                    chyby_c.append((ja, f"nova spojka {k} se neprekryva s drivejsi deskou police"))
                for k2, d2 in zip(kb, b["dily"]):
                    if k2 == k or d2["part_id"] in S.PROFIL_PARTS or d2["part_id"] in S.SPOJKY_PARTS or k2[0] == "zasl":
                        continue
                    lo2, hi2 = aabb(d2)
                    pr = np.minimum(hi, hi2) - np.maximum(lo, lo2)
                    if np.all(pr > 0) and float(pr.min()) > S.TOL_PRUNIK_MM:
                        chyby_c.append((ja, f"nova spojka {k} se zanori do {k2}"))
    # 3) zadny novy problem
    kody_a, kody_b = {x["kod"] for x in a["problemy"]}, {x["kod"] for x in b["problemy"]}
    if not kody_b <= kody_a:
        chyby_c.append((ja, f"novy problem: {kody_b - kody_a}"))
    # 4) kusovnik pro cenu: puvodni bez desek polic a podper; spoje profil-profil ne vic
    ea, eb = S.entries_pro_cenu(a["dily"]), S.entries_pro_cenu(b["dily"])
    lamina_a = sum(1 for e in ea if e["part_id"] == "product_4933")
    lamina_b = sum(1 for e in eb if e["part_id"] == "product_4933")
    desek_polic = sum(1 for k in desky_a if not a["dily"][ia[k]].get("deska_kus"))                  # kazda deska (leva / prava cast u opory zvlast) je jedna polozka kusovniku
    if lamina_a - lamina_b != desek_polic and not dif:
        chyby_c.append((ja, f"kusovnik: desek {lamina_a} -> {lamina_b}, odebrano mela byt {desek_polic}"))
    profily_a = sorted(round(1000 * a["dily"][ia[k]]["scale"][1], 3) for k in ka if a["dily"][ia[k]]["part_id"] in S.PROFIL_PARTS)
    profily_b = sorted(round(1000 * b["dily"][ib[k]]["scale"][1], 3) for k in kb if b["dily"][ib[k]]["part_id"] in S.PROFIL_PARTS)
    delky_podper = sorted(round(1000 * a["dily"][ia[k]]["scale"][1], 3) for k in podpery_a)
    zbytek = list(profily_a)
    for x in delky_podper:
        zbytek.remove(x)
    if zbytek != profily_b and not dif:
        chyby_c.append((ja, "rezny plan profilu bez desky != puvodni bez podper"))
    if b["pocet_spoju"] > a["pocet_spoju"] and not dif:
        chyby_c.append((ja, f"spoju profil-profil je vic ({a['pocet_spoju']} -> {b['pocet_spoju']})"))
    # 5) ucinne parametry a hash
    if b["parametry"]["police_deska"] is not False or G.kanonicky_hash(b["parametry"]) == G.kanonicky_hash(a["parametry"]):
        chyby_c.append((ja, "ucinny parametr / hash bez desky"))
    # 6) 3D ovladani: cast police, nabidka Odebrat / Vratit desku, stejne tahy jako s deskou
    oa, ob = S.ovladani_3d(a), S.ovladani_3d(b)
    ca, cb = {c["id"]: c for c in oa["casti"]}, {c["id"]: c for c in ob["casti"]}
    police_a = sorted(i for i in ca if i.startswith("police_"))
    police_b = sorted(i for i in cb if i.startswith("police_"))
    if (police_a != police_b and not dif) or not police_b:
        chyby_c.append((ja, f"casti police: {police_a} / {police_b}"))
    for cid in police_b:
        if cid not in ca:
            continue
        m_a = [m for m in ca[cid]["menu"] if "police_deska" in (m.get("nastav") or {})]
        m_b = [m for m in cb[cid]["menu"] if "police_deska" in (m.get("nastav") or {})]
        if len(m_a) != 1 or m_a[0]["nastav"] != {"police_deska": False} or not m_a[0]["text"].startswith("Odebrat desk"):
            chyby_c.append((ja, f"nabidka s deskou: {m_a}"))
        if len(m_b) != 1 or m_b[0]["nastav"] != {"police_deska": True} or not m_b[0]["text"].startswith("Vrátit desk"):
            chyby_c.append((ja, f"nabidka bez desky: {m_b}"))
        if "police_deska" not in cb[cid]["param"] or "police_deska" not in ca[cid]["param"]:
            chyby_c.append((ja, "param casti police nema police_deska"))
        lo_b, hi_b = np.array(cb[cid]["aabb"][0]), np.array(cb[cid]["aabb"][1])
        if not (float((hi_b - lo_b)[0]) > 100.0 and float((hi_b - lo_b)[2]) > 100.0 and float((hi_b - lo_b)[1]) < 100.0):
            chyby_c.append((ja, f"AABB casti police bez desky ({cid}) nevypada jako ram: {cb[cid]['aabb']}"))
    if not dif and sorted(t["id"] for t in oa["tahy"]) != sorted(t["id"] for t in ob["tahy"]):
        chyby_c.append((ja, "jine tahy bez desky"))
    if not dif and not all(("zive" in t) == ("zive" in next(x for x in ob["tahy"] if x["id"] == t["id"])) for t in oa["tahy"] if not t["id"].startswith("police_h")):
        chyby_c.append((ja, "zive operace tahu bez desky"))                       # (tahy vysek polic: sonda zive operace muze bez desky uspet i tam, kde s deskou selhala - rozdil je v poradku, spravnost hlida sekce D)
    # 7) koty: stejny pocet, kota vysky horniho lica ramu kazde police a mezery nad ni
    ka_, kb_ = K.koty(a), K.koty(b)
    if len(ka_) != len(kb_) and not dif:
        chyby_c.append((ja, f"pocet kot {len(ka_)} -> {len(kb_)}"))
    P = float(S.SYSTEMY[int(b["parametry"]["system"])]["profil_mm"])
    podlaha = float(b["rozmery"]["y_min"])
    patra = {}
    for k in kb:
        pk = S._patro_ramu_police(k)
        if pk is not None:
            lo, hi = aabb(b["dily"][ib[k]])
            patra.setdefault(pk, []).append((float(lo[1]), float(hi[1])))
    texty_b = {kota["t"] for kota in kb_}
    for pk, lst in patra.items():
        vrch = max(h for _, h in lst)
        if K._cislo(vrch - podlaha) not in texty_b:
            chyby_c.append((ja, f"kota vysky ramu police {pk}: {K._cislo(vrch - podlaha)} chybi"))
    # 8) vyrobni vypis: desky bez spodni police, montaz bez zminky o deskach
    va, vb = S.vyrobni_vypis(a), S.vyrobni_vypis(b)
    if any(q["deska_id"].startswith("pol") and not q["deska_id"].startswith("polvyr") for q in vb["desky"]) or not any(q["deska_id"].startswith("pol") and not q["deska_id"].startswith("polvyr") for q in va["desky"]):
        chyby_c.append((ja, "vyrobni vypis: desky police"))
    t3 = next(x["text"] for x in vb["montazni_postup"] if x["krok"] == 3)
    if "BEZ DESEK" not in t3 or "jejich desky" in t3 or "levá a pravá část" in t3:
        chyby_c.append((ja, f"montaz krok 3: {t3[:80]}"))
    if "desky polic jsou u rámu" in next(x["text"] for x in vb["montazni_postup"] if x["krok"] == 2):
        chyby_c.append((ja, "montaz krok 2 zminuje desky polic"))
    if "BEZ DESEK" in next(x["text"] for x in va["montazni_postup"] if x["krok"] == 3):
        chyby_c.append((ja, "montaz s deskou obsahuje text bez desek"))
for p in vyber:
    kontrola(p)
n_mrizka = pocet
# nahodne konfigurace (pevny seminko): vice parametru najednou, mimo mrizku - tytez kontroly
import random  # noqa: E402
rng = random.Random(20261007)
nahodnych = 0
N_NAH = int(os.environ.get("POLICE_TEST_NAHODNYCH", "90"))
for _ in range(N_NAH):
    sy = rng.choice((30, 35, 40, 45))
    p = dict(system=sy, sirka=rng.randrange(60, 301) * 10, hloubka=rng.randrange(40, (250 if sy == 45 else 150) + 1) * 10, vyska=rng.randrange(40, 121) * 10,
             police=rng.randrange(1, 5), stredni_opora=rng.choice(("auto", "noha", "ram")), stojky=rng.random() < 0.85, suplik=rng.random() < 0.6, suplik_pocet=rng.choice((1, 2, 3)),
             suplik_vlevo=rng.random() < 0.3, drzak_pet=rng.random() < 0.7, panely=rng.random() < 0.7, panely_pocet=rng.randrange(0, 4), led=rng.random() < 0.8,
             kolecka=rng.random() < 0.7, patky=rng.random() < 0.3, vzpery=rng.random() < 0.3, elektrozlab=rng.random() < 0.5,
             vyrez1=rng.random() < 0.4, vyrez1_police=rng.random() < 0.5, vyrez2=rng.random() < 0.2, vyrez2_police=rng.random() < 0.5, presah=rng.choice((0, 30, 60)))
    if sy == 35:
        p["navlek"] = rng.random() < 0.3
    if rng.random() < 0.3:
        p["police_h1"] = float(rng.randrange(10, 40) * 10)
    before = pocet
    kontrola(p)                                                                   # neplatny vstup (mimo rozsah apod.) i s deskou se preskoci
    nahodnych += pocet - before
check(nahodnych >= N_NAH // 3, f"C0b: dost nahodnych platnych konfiguraci ({nahodnych} z {N_NAH})")
pocet = n_mrizka + nahodnych
check(pocet >= 60, f"C0: dost konfiguraci ({pocet})")
check(not chyby_c, f"C1: {len(chyby_c)} chyb v {pocet} konfiguracich bez desky", "\n      ".join(f"{a}: {b}" for a, b in chyby_c[:6]))
print(f"   (uvolneni: v {len(uvolnene)} konfiguracich se bez desky vejde vic - {sorted({tuple(x) for x in uvolnene})[:3]})")
check(nove_spojky >= 1, f"C2: nekde se vraci rohova spojka, kterou drive vynechala deska ({nove_spojky} nových spojek)")
check(zruzene_podpery >= 1, f"C3: u hlubokeho stolu odpadnou podpery pod deskou ({zruzene_podpery} podper)")
print(f"   ({pocet} konfiguraci, {nove_spojky} novych spojek, {zruzene_spojky} zrusenych spojek podper, {zruzene_podpery} zrusenych podper)")

# ---------------------------------------------------------------------------------------------------------------------
print("C') konkretni pripady (nezavisle cislem)")
a = S.sestav_stul()
b = S.sestav_stul(police_deska=False)
check(len(a["dily"]) - len(b["dily"]) == 1 and a["pocet_spoju"] == b["pocet_spoju"], f"C'1: vychozi stul: ubyde prave deska police (dilu {len(a['dily'])} -> {len(b['dily'])})")
b = S.sestav_stul(hloubka=1000, police_deska=False)
a = S.sestav_stul(hloubka=1000)
check(len(a["dily"]) - len(b["dily"]) == 4 and a["pocet_spoju"] - b["pocet_spoju"] == 2, f"C'2: hluboky stul: ubyde deska, podpera a 2 spojky jejiho predniho konce (dilu {len(a['dily'])} -> {len(b['dily'])}, spoju {a['pocet_spoju']} -> {b['pocet_spoju']})")
b = S.sestav_stul(sirka=2100, police_deska=False)
a = S.sestav_stul(sirka=2100)
check(len(a["dily"]) - len(b["dily"]) == 1 and any(isinstance(k, tuple) and k[0] == "n" for k in set(klice(b)) - set(klice(a))), "C'3: siroky stul (delena deska): ubyde deska a pribude jedna spojka, kterou drive blokovala")
a = S.sestav_stul(vyrez1=True, vyrez1_police=True)
b = S.sestav_stul(vyrez1=True, vyrez1_police=True, police_deska=False)
check(any(k[0] == "polvyr" and len(k) == 3 and k[2] == "deska" for k in klice(b)) and not any(je_deska_police(k) for k in klice(b)), "C'4: police pod vyrezem ma vlastni desku i bez desky spodni police")
check(sum(1 for d in a["dily"] if d.get("deska_id") == "polvyr1") == sum(1 for d in b["dily"] if d.get("deska_id") == "polvyr1") == 1, "C'5: deska police pod vyrezem je beze zmeny")
b = S.sestav_stul(police=2, vyska=1150, police_deska=False)
check(b["parametry"]["police"] == 2 and not any(je_deska_police(k) for k in klice(b)) and sum(1 for k in klice(b) if S._patro_ramu_police(k) == 1) == 2, "C'6: dve police bez desky: obe maji ram, zadna deska")

# ---------------------------------------------------------------------------------------------------------------------
print("D) zive tazeni vysky police bez desky = model ze serveru")
spec = importlib.util.spec_from_file_location("test_stul_zive", os.path.join(os.path.dirname(HERE), "2026-10-02_stul_testy", "test_stul_zive.py"))
Z = importlib.util.module_from_spec(spec)
spec.loader.exec_module(Z)
for tid, par, zmeny in (("police_h1", dict(police_deska=False), (+40.0, -30.0)), ("police_h1", dict(police_deska=False, police=3, vyska=1200), (+60.0, -40.0)),
                        ("police_h2", dict(police_deska=False, police=3, vyska=1200), (+30.0, -20.0)), ("police_h2", dict(police_deska=False, police=2, vyska=1000, suplik=False, sirka=2000, hloubka=1000), (+20.0, -20.0))):
    for z in zmeny:
        j = f"{tid} {par} {z:+.0f} mm"
        res = Z.porovnej(par, tid, z, 0.05, j)
        if not res:
            check(False, f"D: {j}: porovnani se nepovedlo")
            continue
        chyby, r0_ = res[0], res[5]
        check(chyby and all(c <= 0.05 for c, i in chyby), f"D: {j}: zive tazeni = model ze serveru (nejvetsi odchylka {max(c for c, _ in chyby):.3f} mm)")

# ---------------------------------------------------------------------------------------------------------------------
print("E) GLB a verejna podoba 3D ovladani")
for p in (dict(), dict(police=2, vyska=1150), dict(hloubka=1000, sirka=2100)):
    a = S.sestav_stul(**p)
    b = S.sestav_stul(**{**p, "police_deska": False})
    ha, ga = G.model_pro_parametry(a["parametry"], razitka=False)
    hb, gb = G.model_pro_parametry(b["parametry"], razitka=False)
    check(ha != hb and len(gb) < len(ga), f"E1: GLB bez desky {p} je mensi a ma jiny hash ({len(ga)} -> {len(gb)} B)")
    r = S.odpoved(p | {"police_deska": False})
    ov = G.vodici(r["parametry"], r)["ovladani"]
    for lang in ("cs", "en", "sk"):
        try:
            ver = OV.ovladani_verejne(ov, lang, 30.0)
        except OV.ChybiPreklad as e:
            check(False, f"E2: preklad {lang}: {e}")
            continue
        c1 = next(c for c in ver["casti"] if c["id"] == "shelf1")
        m = [m_ for m_ in c1["menu"] if m_["nastav"] == {"shelfboard": True}]
        check(len(m) == 1 and "shelfboard" in c1["param"] and "shelf" in c1["param"], f"E2: verejne ovladani {lang} {p}: cast shelf1 ma param shelfboard a nabidku 'vratit desku'")
        if lang == "en":
            check(m[0]["text"] in ("Put the shelf board back", "Put the boards back on all shelves"), f"E3: anglicky text nabidky: {m[0]['text']}")
        if lang == "sk":
            check(m[0]["text"] in ("Vrátiť dosku police", "Vrátiť dosky na všetky police"), f"E3: slovensky text nabidky: {m[0]['text']}")
    r1 = S.odpoved(p)
    ov1 = G.vodici(r1["parametry"], r1)["ovladani"]
    ver1 = OV.ovladani_verejne(ov1, "cs", 30.0)
    m1 = [m_ for m_ in next(c for c in ver1["casti"] if c["id"] == "shelf1")["menu"] if m_["nastav"] == {"shelfboard": False}]
    check(len(m1) == 1 and m1[0]["text"].startswith("Odebrat desk"), f"E4: verejne ovladani s deskou {p}: nabidka 'odebrat desku'")

# E5) vsechny 4 podoby nabidky (1 / vice polic x deska zapnuta / vypnuta) ve vsech trech jazycich (chybejici preklad = ChybiPreklad; plural 'desky vsech polic' se jinde nepouzije)
NABIDKA = {(1, True): ("Odebrat desku police", "Remove the shelf board", "Odstrániť dosku police"),
           (1, False): ("Vrátit desku police", "Put the shelf board back", "Vrátiť dosku police"),
           (2, True): ("Odebrat desky všech polic", "Remove the boards of all shelves", "Odstrániť dosky všetkých políc"),
           (2, False): ("Vrátit desky všech polic", "Put the boards back on all shelves", "Vrátiť dosky na všetky police")}
for (n_pol, deska), texty in NABIDKA.items():
    par = dict(police=n_pol, vyska=1150) if n_pol > 1 else {}
    r = S.odpoved({**par, "police_deska": deska})
    ov = G.vodici(r["parametry"], r)["ovladani"]
    for lang, text in zip(("cs", "en", "sk"), texty):
        popis = f"{n_pol} ks, deska {'zapnuta' if deska else 'vypnuta'}"
        try:
            ver = OV.ovladani_verejne(ov, lang, 30.0)
        except OV.ChybiPreklad as e:
            check(False, f"E5 {lang}: preklad nabidky ({popis}): {e}")
            continue
        cast = next(c for c in ver["casti"] if c["id"] == "shelf1")
        txt = [m_["text"] for m_ in cast["menu"] if m_["nastav"] == {"shelfboard": not deska}]
        check(txt == [text], f"E5 {lang}: nabidka police ({popis}) = '{text}'", str(txt))

print(f"\n==> {OK}/{OK + len(FAILS)} kontrol OK" + (f", SELHALO {len(FAILS)}: " + "; ".join(FAILS[:6]) if FAILS else ""))
sys.exit(1 if FAILS else 0)
