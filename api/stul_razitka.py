"""Razitka (ochranne 3D logo LOGIMAN.CZ) na profilech STOLU z generatoru - NA VSECH 3D modelech generatoru (bot8, 2026-10-06; od 2026-10-08 VYCHOZI, WORKFLOW pravidlo 61).

Robert (pres bot5 / bot9, 2026-10-06): razitka loga v 3D modelu online nabidky maji byt i u stolu z generatoru; do 2026-10-08 platilo pravidlo z 2026-09-06 (razitkovani = stupen 2 = model v nabidce,
verejny generator a kosik bez razitek). WORKFLOW pravidlo 61 (Robert 2026-10-08, doslova: "razitka budou na vsech 3D modelech ve vsech generatorech") ho PREBILO: `stul_glb.model_pro_parametry` ma razitka
VYCHOZI (`RAZITKA_VYCHOZI`; zive 3D, kosik, nabidka, karta), pravidla umisteni nize se nemenila.

PRAVIDLA jsou Robertova pro sestavy (scripts/razitkovac.py, 2026-09-10 / 11 / 17) - tady jen uplatnena na dily stolu:
  * logo LOGIMAN.CZ (222,2 x 28 mm, reliéf 3 mm) lezi na vnejsi sténe profilu, text podel profilu, cte se spravne (svisle = zdola nahoru podle pravidla gravitace z razitkovace),
  * kazda ze 4 sten profilu se posuzuje NEZAVISLE a cisté geometricky: ma souvisly volny usek na cele logo (nic na ni nesedi, 40 mm od konce profilu) a je EXPONOVANA ven (zadny jiny
    dil ji nezakryva) - razitka jsou ze vsech stran stolu,
  * "kazdy treti" (KAZDY_NTY) profil z kandidatu KAZDE steny (razeno vyska / x / z, posun podle hash konfigurace) dostane logo na nahodne misto volneho useku (deterministicky z hash),
  * na jednom profilu nejmene MIN_ROZESTUP_LOG_MM volne mezery mezi logy napric stenami,
  * pod logem je VYPLNENA DRAZKA (vypln licuje se stenou, neni delsi nez logo) - pismena se nad otevrenou T-drazkou nelamou.

Jinak nez u sestav (kde razitkovac pocita s profilem 30x30 a rozmery dilu z DB) tady: profily vsech systemu stolu (30 / 35 / 40 / 41 / 45; 41 a 45 maji profil jako 40; drazka podle profilu, zmereno z GLB profilu), rozmery dilu
z AABB generatoru (`stul_konfigurator._aabb`), sikme vzpery se nerazitkuji. Vystup je cista data (poloha a otoceni loga a vyplne v souradnicich generatoru); geometrii sklada
`stul_glb.poskladej_glb(..., razitka=...)`: logo jako JEDEN sdileny mesh (instance uzlu) s vlastnim materialem, vyplne jako kvadry ve skupine materialu hlinik.
"""
import os
import sys

import numpy as np

import stul_konfigurator as S

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.append(_SCRIPTS)
import razitkovac as R  # noqa: E402  (jedna kopie pravidel a konstant; importuje ho i product_assemblies)

LOGO_PART = R.LOGO_PART_ID                     # "logo_logiman_cz" (GLB v katalogu); po sanitizeru ma uzel jmeno n<i>, nikde se jmeno "logo" nepouziva
LOGO_BARVA = list(R.LOGO_BASE_COLOR) + [1.0]   # LINEARNI (glTF) oranzova eloxovaneho hliniku (#EB8E23); material loga v nabidce je neprusvitny kov, ne sklo jako v Blenderu
LOGO_KOVOVOST, LOGO_DRSNOST = 0.2, 0.35
# Drazka profilu (sirka otvoru, hloubka od povrchu po dno hrdla), ZMERENO z GLB profilu (prurez, 2026-10-06): Object_7 8,2 x 10; profil_35x35 8,2 x 11,667; Object_11 10,2 x 13,332
DRAZKA = {"Object_7": (8.2, 10.0), "profil_35x35": (8.2, 11.667), "Object_11": (10.2, 13.332)}
DOHLED_MM = 4000.0


def _paprsek_zasahne(pocatek, smer, lo, hi, kandidati):
    """Je mezi AABB `kandidati` (indexy do lo / hi, N x 3) nejaky, ktery protne polopriimka (pocatek, smer) do vzdalenosti DOHLED_MM? (vektorizovane slab test)."""
    if not len(kandidati):
        return False
    o = np.asarray(pocatek, float)
    d = np.asarray(smer, float)
    lo_, hi_ = lo[kandidati], hi[kandidati]
    rovnobezne = np.abs(d) < 1e-9
    uvnitr = (o >= lo_) & (o <= hi_)                                          # N x 3: pocatek v desce teto osy (pro osy rovnobezne s paprskem)
    with np.errstate(divide="ignore", invalid="ignore"):
        t1 = (lo_ - o) / d
        t2 = (hi_ - o) / d
    vstup = np.where(rovnobezne, np.where(uvnitr, -np.inf, np.inf), np.minimum(t1, t2))        # rovnobezna osa mimo desku = paprsek mine (vstup v nekonecnu)
    vystup = np.where(rovnobezne, np.where(uvnitr, np.inf, -np.inf), np.maximum(t1, t2))
    t_od = np.maximum(vstup.max(axis=1), 0.0)
    t_do = np.minimum(vystup.min(axis=1), DOHLED_MM)
    return bool(((t_od <= t_do) & (t_do > 0.0)).any())


def _baze_razitka(osa, normala):
    """(x, y, z) baze razitka: x podel profilu (text), z ven ze steny, y = z x x; otocena o 180 st. kolem normaly, kdyz by se text cetl vzhuru nohama / pozpatku (pravidlo z razitkovace)."""
    z = normala
    y = R._norm(R._cross(z, osa))
    x = R._norm(R._cross(y, z))
    if R._je_text_o_180_stupnu(normala, osa, y):
        x, y = R._neg(x), R._neg(y)
    return x, y, z


def razitka(r, seed, ladeni=None):
    """Razitka stolu (vysledek `stul_konfigurator.sestav_stul`) jako seznam dict: {"klic": klic profilu, "lok": index steny 0-3, "stena": "horni" | ..., "t": poloha podel profilu (mm od stredu),
    "logo": {"pos": [x, y, z], "q": [x, y, z, w]}, "vypln": {"pos", "q", "rozmer": [delka, sirka, hloubka]}, "dil": index dilu (v `r["dily"]`), na kterem razitko sedi}; souradnice generatoru. `seed` = retezec (hash konfigurace): stejna konfigurace
    dava stejna razitka. Stolu bez profilu (nebo bez dostatecne dlouheho) vraci []. `ladeni` (dict, jen testy): doplni se `kandidati` = pocty kandidatu podle steny a `vybrane` = pocty vybranych."""
    sy = r["parametry"]["system"]
    sd = S.SYSTEMY[sy]
    profil = sd["profil"]
    drazka_w, drazka_d = DRAZKA[profil]
    h = sd["profil_mm"] / 2.0
    dily = r["dily"]
    klice = [tuple(tuple(x) if isinstance(x, list) else x for x in k) if isinstance(k, (list, tuple)) else k for k in r["klice"]]
    n = len(dily)
    boxy = np.array([S._aabb(d) for d in dily], float)                      # N x 2 x 3
    lo, hi = boxy[:, 0, :], boxy[:, 1, :]
    rohy_vsech = np.array([[[x, y, z] for x in (lo[i][0], hi[i][0]) for y in (lo[i][1], hi[i][1]) for z in (lo[i][2], hi[i][2])] for i in range(n)], float)       # N x 8 x 3
    kandidati = []
    for i, d in enumerate(dily):
        k = klice[i]
        if d["part_id"] != profil or (isinstance(k, tuple) and len(k) and k[0] == "vz") or R.je_razitko(d.get("role")):
            continue
        L = 1000.0 * d["scale"][1]
        if L < R.MIN_DELKA_MM:
            continue
        Rm = S.kvat_na_matici(d["quaternion"])
        osa = Rm[:, 1]
        stred = np.array(d["position"], float)
        volnost_pul = (L - 2.0 * R.OKRAJ_MM) / 2.0
        for lok_idx, lok in enumerate(R.KANDIDATNI_STENY_LOK):
            normala = Rm @ np.array(lok, float)
            bok = np.cross(normala, osa)
            dd = rohy_vsech - stred
            us, vs, ws = dd @ osa, dd @ bok, dd @ normala                    # N x 8: souradnice rohu AABB ostatnich dilu v bazi steny
            # usek steny je zablokovany, kdyz PRED nim (od 0,5 mm nad rovinou steny az do DOHLED_MM) lezi neco v pasu loga: jednim pruchodem se tak resi obsazeni steny (spojky, prícky) i
            # exponovani ven (deska, jina noha, kolecko... pred stenou) - misto samostatneho paprsku z jednoho bodu (ten minul dil, ktery zakryval jen cast loga)
            w_min, v_mez = h + 0.5, R.LOGO_VYSKA_MM / 2.0 + 2.0
            blok = (ws.max(axis=1) >= w_min) & (ws.min(axis=1) <= DOHLED_MM) & (vs.max(axis=1) >= -v_mez) & (vs.min(axis=1) <= v_mez)
            blok[i] = False
            useky = [(float(us[j].min() - R.BLOK_REZERVA_MM), float(us[j].max() + R.BLOK_REZERVA_MM)) for j in np.nonzero(blok)[0]]
            volne = [(od, do) for od, do in R._volne_useky(volnost_pul, useky) if do - od >= R.LOGO_DELKA_MM]
            if not volne:
                continue
            od, do = max(volne, key=lambda u: (u[1] - u[0], -u[0]))                  # nejdelsi volny usek (shoda: levejsi)
            t_mid = (od + do) / 2.0
            kandidati.append({"i": i, "lok": lok_idx, "osa": osa, "normala": normala, "stred": stred, "volne": volne, "t_mid": float(t_mid)})
    if not kandidati:
        return []

    vybrane = []
    for lok_idx in range(len(R.KANDIDATNI_STENY_LOK)):
        skupina = [c for c in kandidati if c["lok"] == lok_idx]
        if not skupina:
            continue
        skupina.sort(key=lambda c: (round(float(c["stred"][1]), 1), round(float(c["stred"][0]), 1), round(float(c["stred"][2]), 1), c["i"]))
        posun = int(R._nahodne_0_1("posun", seed, lok_idx) * R.KAZDY_NTY)
        vybrane.extend(c for kk, c in enumerate(skupina) if kk % R.KAZDY_NTY == posun)

    if ladeni is not None:
        ladeni["kandidati"] = {lok: sum(1 for c in kandidati if c["lok"] == lok) for lok in range(len(R.KANDIDATNI_STENY_LOK))}
        ladeni["vybrane"] = {lok: sum(1 for c in vybrane if c["lok"] == lok) for lok in range(len(R.KANDIDATNI_STENY_LOK))}
    out = []
    stredy_na_profilu = {}
    for c in vybrane:
        i = c["i"]
        klic_dilu = tuple(round(float(v), 1) for v in c["stred"])
        rr = R._nahodne_0_1("pozice", seed, klic_dilu, c["lok"])
        pouzitelne = c["volne"]
        od, do = max(pouzitelne, key=lambda u: (u[1] - u[0], -u[0]))
        s_od, s_do = od + R.LOGO_DELKA_MM / 2.0, do - R.LOGO_DELKA_MM / 2.0
        t = s_od + rr * (s_do - s_od)
        stredove = [(u_od + R.LOGO_DELKA_MM / 2.0, u_do - R.LOGO_DELKA_MM / 2.0) for u_od, u_do in pouzitelne]
        zakazane = stredy_na_profilu.get(i, ())
        if any(abs(t - s) < R.LOGO_DELKA_MM + R.MIN_ROZESTUP_LOG_MM - 1e-6 for s in zakazane):
            povolene = [u for u in R._povolene_useky(stredove, zakazane) if u[1] - u[0] >= 0.0]
            if not povolene:
                continue
            u_od, u_do = max(povolene, key=lambda u: (u[1] - u[0], -u[0]))
            t = u_od + rr * (u_do - u_od)
        stredy_na_profilu.setdefault(i, []).append(float(t))
        x, y, z = _baze_razitka(c["osa"], c["normala"])
        q = R._kvaternion_z_baze(x, y, z)
        bod = lambda vzdal: [float(c["stred"][m] + c["osa"][m] * t + c["normala"][m] * vzdal) for m in range(3)]      # noqa: E731
        out.append({"klic": klice[i], "dil": int(i), "lok": c["lok"], "stena": R._stena_popis(tuple(c["normala"]), 270.0), "t": float(t),
                    "logo": {"pos": bod(h + R.LOGO_ODSAZENI_PIVOTU_MM), "q": [float(v) for v in q]},
                    "vypln": {"pos": bod(h - drazka_d / 2.0), "q": [float(v) for v in q], "rozmer": [R.LOGO_DELKA_MM, drazka_w, drazka_d]}})
    return out
