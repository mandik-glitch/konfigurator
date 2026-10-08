#!/opt/konfigurator/api/venv/bin/python
"""Test: BEZ zadnich stojek pracovni deska pokracuje dozadu a prekryva zadni svisle profily (api/stul_konfigurator.py `deska_zadni_pokracovani`; bot10, 2026-10-08;
Robert: "stoly generator, kdyz se odejmou zadni stojky (zkrati), deska musi pokracovat dozadu prekryt svisle profily").

Porovnava KANDIDATA (DESKA_DIR=<koren prekryvu s api/>, jinak zive api/) se stavem PRED zmenou (ZAKLAD=<git revize>, vychozi `d7dde610^` = revize tesne PRED zmenou; HEAD ji uz obsahuje, takze by nic neporovnal) NA STEJNYCH VYBERECH: obe varianty pocita samostatny proces
(`--dump`), ktery nacte svuj adresar api/ (baseline = symlinky na kandidata + soubory stul_konfigurator.py / stul_shop.py / stul_glb.py z `git show`). Vybery: pseudonahodny vzorek (pevny seed) pres
systemy 30 / 35 / 40 / 45 (sirka vc. stredni nohy a deleni desky, hloubka vc. > 900 a 2500, vyska, presah, kolecka / patky / navlek, supliky, police, drzak PET na vsech nohach a stranach, vyrezy,
loziska); kazdy v teto trojici: A = BEZ stojek (panely, LED, elektrozlab, horni police, vzpery vypnuty - bez stojek nelze), B = SE stojkami stejny vyber bez prislusenstvi na stojkach, C = SE stojkami
vc. nahodneho prislusenstvi.
Hlida: (1) SE stojkami (B, C) je VSE shodne s puvodnim stavem (dily, cena, kusovnik, problemy, rozmery); (2) BEZ stojek (A): vsechny dily krome pracovni desky, zaslepek a loziskovych jednotek (ty se rozmistuji podle obrysu desky) shodne, z dilu zmizely JEN
zaslepky na horni konce zadnich noh a nic nepribylo, predni hrana desky a jeji vyska / sirka beze zmeny, zadni hrana v rovine zadniho lice zadnich noh (nezavisle z AABB svislych profilu), plocha desky
o tloustku profilu x sirka vetsi, vyrezy a deleni u stredni nohy dal sedi, zadne nove problemy; (3) vyrezy: meze polohy v desce o tloustku profilu vetsi (jadro i mezi posuvniku v obchode), (4) SSE a stul se
stojkami beze zmeny, (5) RULES_VERSION se nemeni, hash stolu SE stojkami je beze zmeny a hash stolu BEZ stojek je jiny (znacka `_deska_zad`), (6) GLB se stavi a projde kontrolou zakaznickeho modelu.

Spusteni (DB pro cenu pres systemd-run): systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PRIVATE_FILES_DIR=/tmp/pf_deska \\
   --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_deska_pres_nohy/test_deska_pres_nohy.py     (N=<vybery na system>, SEED=<seed>, DESKA_DIR=<koren prekryvu>, ZAKLAD=<revize>)"""
import json
import os
import random
import subprocess
import sys
import tempfile
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def api_dir(kandidat_koren=None):
    return os.path.join(kandidat_koren or REPO, "api")


# --------------------------------------------------------------------------------------------------------- rezim --dump <api> <vystup.json> <N> <SEED>
def _nacti(api):
    sys.path.insert(0, api)
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    _o = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
    try:
        import stul_konfigurator as S  # noqa: E402
        import stul_shop as SH  # noqa: E402
        import stul_api  # noqa: E402
        import stul_glb as G  # noqa: E402
    finally:
        threading.Thread.start = _o
    assert os.path.dirname(os.path.abspath(S.__file__)) == os.path.abspath(api), (S.__file__, api)
    return S, SH, stul_api, G


BEZ_STOJEK = dict(posts=False, panels=False, led=False, ledlight=False, socket=False, upshelf=False, braces=False)
OFF_NA_STOJKACH = dict(panels=False, led=False, ledlight=False, socket=False, upshelf=False, braces=False)


def vzorky(S, SH, system, n, rnd):
    """[(popis, vyber BEZ stojek, vyber SE stojkami bez prislusenstvi, vyber SE stojkami vc. nahodneho prislusenstvi)]"""
    zaklad = SH.vychozi_vyber(system)
    out = []
    for i in range(n):
        v = dict(zaklad)
        v["w"] = rnd.choice([600, 900, 1280, 1500, 1800, 2000, 2400, 2600])
        v["d"] = rnd.choice([500, 600, 800, 900, 1000, 1200, 1500] + ([2000, 2500] if system == 45 else []))
        v["h"] = rnd.choice([600, 760, 840, 950, 1100])
        v["ov"] = rnd.choice([0, 15, 30, 60, 100])
        if "sleeve" in v:
            v["sleeve"] = rnd.random() < 0.4
        v["wheels"] = rnd.random() < 0.5
        v["feet"] = (not v["wheels"]) and rnd.random() < 0.6
        v["drawers"] = rnd.random() < 0.5
        v["drawercount"] = rnd.choice([1, 2, 3])
        v["drawleft"] = rnd.random() < 0.5
        v["shelf"] = rnd.choice([0, 1, 1, 2, 3])
        v["pet"] = rnd.random() < 0.5
        v["petleg"] = rnd.choice(list(S.PET_NOHY))
        v["petface"] = rnd.choice(list(S.PET_STRANY))
        v["bearings"] = rnd.random() < 0.15
        v["midsupport"] = rnd.choice(list(S.STREDNI_OPORY))
        if rnd.random() < 0.5:
            v["cut1"] = True
            v["cut1w"], v["cut1d"] = rnd.choice([100, 200, 400]), rnd.choice([100, 200, 300])
            v["cut1x"], v["cut1z"] = rnd.choice([30, 120, 300, 500, 2000]), rnd.choice([30, 200, 400, 900])      # 2000 = az k zadni hrane (orizne se podle desky)
            v["cut1shelf"] = rnd.random() < 0.4
        a = {**v, **BEZ_STOJEK}
        b = {**v, "posts": True, **OFF_NA_STOJKACH}
        c = {**v, "posts": True}
        for k in ("panels", "led", "socket"):
            c[k] = rnd.random() < 0.7
        out.append((f"s{system}#{i}", a, b, c))
    return out


def vypocet(S, SH, stul_api, G, sel, system):
    """Vysledek jednoho vyberu: parametry, dily, problemy, rozmery, spoje, cena, kusovnik - nebo chyba."""
    try:
        p, _ = SH.normalizuj(sel, system)
        r = S.sestav_stul(**p)
        cena = stul_api.cena_konfigurace(r["dily"], p["system"])
        return {"ok": True, "p_stojky": bool(p["stojky"]), "hash": G.kanonicky_hash(p), "parametry": {k: r["parametry"][k] for k in r["parametry"] if k in ("system", "sirka", "hloubka", "vyska", "presah", "vyrez1_x", "vyrez1_d", "vyrez1_z", "vyrez1_w")},
                "dily": r["dily"], "problemy": [(x["kod"], x.get("text", "")[:80]) for x in r["problemy"]], "rozmery": r["rozmery"], "spoje": r["pocet_spoju"],
                "cena": None if not cena else {"bez_dph": cena["bez_dph"], "kus": [(b["nazev"], b["mnozstvi"], b["rozmer"], b["celkem"]) for b in cena["kusovnik"]["radky"]] if cena.get("kusovnik") and cena["kusovnik"].get("radky") else None}}
    except Exception as e:                                             # noqa: BLE001
        return {"ok": False, "chyba": f"{type(e).__name__}: {str(e)[:160]}"}


def dump(api, vystup, n, seed):
    S, SH, stul_api, G = _nacti(api)
    rnd = random.Random(seed)
    data = {"verze": G.RULES_VERSION, "systemy": {}, "vybery": []}
    for system in (30, 35, 40, 45):
        for popis, a, b, c in vzorky(S, SH, system, n, rnd):
            data["vybery"].append({"popis": popis, "system": system,
                                   "A": vypocet(S, SH, stul_api, G, a, system), "B": vypocet(S, SH, stul_api, G, b, system), "C": vypocet(S, SH, stul_api, G, c, system)})
    # hash tehoz vyberu (verze pravidel v hashi)
    p30, _ = SH.normalizuj({**SH.vychozi_vyber(30), **BEZ_STOJEK}, 30)
    data["hash_bez_stojek"] = G.kanonicky_hash(p30)
    p30b, _ = SH.normalizuj(SH.vychozi_vyber(30), 30)
    data["hash_vychozi"] = G.kanonicky_hash(p30b)
    # pomocna funkce a meze posuvniku vyrezu v obchode (resolve = plna cesta)
    data["pokracovani"] = {str(s_): [S.deska_zadni_pokracovani(S.SYSTEMY[s_], True), S.deska_zadni_pokracovani(S.SYSTEMY[s_], False)] for s_ in (30, 35, 40, 45, 41)} if hasattr(S, "deska_zadni_pokracovani") else None
    data["meze_vyrezu"] = {}
    for system in (30, 40):
        for stojky in (True, False):
            sel = {**SH.vychozi_vyber(system), "cut1": True}
            if not stojky:
                sel.update(BEZ_STOJEK)
            r = SH.resolve(sel, "cs", system=system)
            data["meze_vyrezu"][f"{system}_{int(stojky)}"] = {k: r["options"][k] for k in ("cut1d", "cut1x", "cut1w", "cut1z")}
    # staticke maximum posuvniku vyrezu ve schematu karet (system 30 = #4934, system 40 = #4954): horni mez pres vsechny volby
    import app as appmod  # noqa: E402
    cl = appmod.app.test_client()
    data["schema_max"] = {}
    for pid in (4934, 4954):
        sj = cl.get(f"/api/shop/products/{pid}/configurator").get_json()
        data["schema_max"][str(pid)] = {sl["id"]: sl["slider"]["max"] for sl in sj["slots"] if sl["id"] in ("cut1d", "cut1x") and sl.get("slider")}
    # SSE (system 41): jadro se nemeni
    try:
        pss, _ = SH.normalizuj(SH.vychozi_vyber(41), 41)
        rs = S.sestav_stul(**pss)
        data["sse"] = {"dily": rs["dily"], "problemy": [x["kod"] for x in rs["problemy"]]}
    except Exception as e:                                             # noqa: BLE001
        data["sse"] = {"chyba": str(e)[:120]}
    json.dump(data, open(vystup, "w"), default=str)


# --------------------------------------------------------------------------------------------------------- orchestrace a kontroly
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:900]))


def zaklad_api(kandidat_api, zaklad):
    """Adresar api/ ve stavu PRED zmenou: symlinky na kandidata + 3 soubory z `git show <zaklad>`."""
    tmp = tempfile.mkdtemp(prefix="deska_zaklad_")
    os.makedirs(os.path.join(tmp, "api"))
    os.symlink(os.path.join(REPO, "webapp"), os.path.join(tmp, "webapp"))
    nahrazene = ("stul_konfigurator.py", "stul_shop.py", "stul_glb.py")
    for e in os.listdir(kandidat_api):
        if e in nahrazene or e == "__pycache__":
            continue
        os.symlink(os.path.join(kandidat_api, e), os.path.join(tmp, "api", e))
    for f in nahrazene:
        kod = subprocess.run(["git", "-C", REPO, "show", f"{zaklad}:api/{f}"], capture_output=True, text=True, check=True).stdout
        open(os.path.join(tmp, "api", f), "w", encoding="utf-8").write(kod)
    return os.path.join(tmp, "api")


def spust_dump(api, n, seed):
    vystup = tempfile.mktemp(prefix="deska_dump_", suffix=".json")
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "--dump", api, vystup, str(n), str(seed)], capture_output=True, text=True, env={**os.environ, "DESKA_NEZAVOLANO": "1"})
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-3000:])
        raise SystemExit(f"dump {api} selhal rc={r.returncode}")
    return json.load(open(vystup))


def aabb_dilu(S, d):
    lo, hi = S._aabb(d)
    return [float(v) for v in lo], [float(v) for v in hi]


def je_prac(d):
    return str(d.get("deska_id") or "").startswith("prac_")


def klic(d):
    return (d["part_id"], tuple(round(v, 3) for v in d["position"]), tuple(round(v, 4) for v in d["quaternion"]), tuple(round(v, 4) for v in d["scale"]), d.get("deska_id"), json.dumps(d.get("deska_celek")),
            d.get("deska_kus"), d.get("deska_vyrezu"))


def multimnozina(seznam):
    out = {}
    for k in seznam:
        out[k] = out.get(k, 0) + 1
    return out


def main():
    n = int(os.environ.get("N", "18"))
    seed = int(os.environ.get("SEED", "20261008"))
    kandidat_koren = os.environ.get("DESKA_DIR") or None
    zaklad = os.environ.get("ZAKLAD", "d7dde610^")                # revize tesne pred zmenou (po commitu zmeny uz HEAD jako zaklad nic neporovna)
    kand_api = api_dir(kandidat_koren)
    zakl_api = zaklad_api(kand_api, zaklad)
    print(f"kandidat: {kand_api}\nzaklad:   {zakl_api} (git {zaklad}); vyberu na system {n}, seed {seed}")
    nov = spust_dump(kand_api, n, seed)
    puv = spust_dump(zakl_api, n, seed)
    sys.path.insert(0, kand_api)
    _o = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
    try:
        import stul_konfigurator as S  # noqa: E402
    finally:
        threading.Thread.start = _o

    print("\n## 1) verze pravidel, hash, pomocna funkce")
    over("1.1 verze pravidel (RULES_VERSION) se NEMENI a hash vychoziho stolu SE stojkami je beze zmeny; hash stolu BEZ stojek je jiny (znacka _deska_zad: jiny model a cena = jiny kod STL-xxxxxx)",
         nov["verze"] == puv["verze"] and nov["hash_vychozi"] == puv["hash_vychozi"] and nov["hash_bez_stojek"] != puv["hash_bez_stojek"], (nov["verze"], puv["verze"], nov["hash_vychozi"], puv["hash_vychozi"], nov["hash_bez_stojek"], puv["hash_bez_stojek"]))
    over("1.2 deska_zadni_pokracovani: se stojkami 0; bez nich tloustka profilu (30 -> 30, 35 -> 35, 40 -> 40, 45 -> 40); SSE (41) vzdy 0",
         nov["pokracovani"] == {"30": [0.0, 30.0], "35": [0.0, 35.0], "40": [0.0, 40.0], "45": [0.0, 40.0], "41": [0.0, 0.0]}, nov["pokracovani"])
    over("1.3 stul SSE (system 41) je beze zmeny (dily i problemy stejne)", nov["sse"] == puv["sse"], None)

    print("\n## 2) vyberu: %d (trojice A bez stojek / B se stojkami bez prislusenstvi / C se stojkami + prislusenstvi)" % len(nov["vybery"]))
    shoda_bc = shoda_a = 0
    chyby_bc, chyby_a, ruzne_chyby = [], [], []
    pocty = {"A": 0, "chyba_obe": 0}
    for vn, vp in zip(nov["vybery"], puv["vybery"]):
        assert vn["popis"] == vp["popis"]
        for var in ("B", "C"):
            rn, rp = vn[var], vp[var]
            if rn["ok"] != rp["ok"]:
                ruzne_chyby.append((vn["popis"], var, rn.get("chyba"), rp.get("chyba")))
                continue
            if not rn["ok"]:
                continue
            if json.dumps(rn, sort_keys=True) == json.dumps(rp, sort_keys=True):
                shoda_bc += 1
            else:
                chyby_bc.append((vn["popis"], var))
        an, ap = vn["A"], vp["A"]
        if an["ok"] != ap["ok"]:
            ruzne_chyby.append((vn["popis"], "A", an.get("chyba"), ap.get("chyba")))
            continue
        if not an["ok"]:
            pocty["chyba_obe"] += 1
            continue
        pocty["A"] += 1
        chyba = []
        sys_ = vn["system"]
        P = float(S.SYSTEMY[sys_]["profil_mm"])
        dn, dp = an["dily"], ap["dily"]
        # pracovni deska (kusy "prac_*"): obrys pred a po zmene
        deska_n = [aabb_dilu(S, d) for d in dn if je_prac(d)]
        deska_p = [aabb_dilu(S, d) for d in dp if je_prac(d)]

        def sjednot(kusy):
            return [min(k[0][i] for k in kusy) for i in range(3)], [max(k[1][i] for k in kusy) for i in range(3)]

        def plocha(kusy):
            return sum((k[1][0] - k[0][0]) * (k[1][2] - k[0][2]) for k in kusy)
        (lon, hin), (lop, hip) = sjednot(deska_n), sjednot(deska_p)
        sirka = hip[2] - lop[2]
        podspodek = lon[1]                                                 # spodek pracovni desky = horni konce nohou
        # zadni nohy = svisle profily (PROFIL_PARTS, delsi nez 2 P, prurez P x P), jejichz horni konec je pod deskou; zadni lice = nejvetsi x
        nohy = []
        for d in dn:
            if d["part_id"] in S.PROFIL_PARTS:
                lo_, hi_ = aabb_dilu(S, d)
                if hi_[1] - lo_[1] > 2.0 * P and hi_[0] - lo_[0] < P + 1.0 and hi_[2] - lo_[2] < P + 1.0 and abs(hi_[1] - podspodek) < 0.05:
                    nohy.append((lo_, hi_))
        x_zadni_lice = max(h_[0] for _, h_ in nohy) if nohy else None
        zadni_nohy = [(l_, h_) for l_, h_ in nohy if abs(h_[0] - x_zadni_lice) < 0.05] if nohy else []
        # (2a) dily mimo pracovni desku (a loziskove jednotky): stejne, krome zaslepek na hornich koncich zadnich noh; kdyz vyrez po orezu zadni hranou posunul (vyrez1_x o P), jeho police a zavesy se
        #      posunuly s nim (jejich shodu nehlidame, hlida se posun)
        loz_n = [d for d in dn if d["part_id"] == S.LOZ_PART]                      # loziskove jednotky se rozmistuji podle obrysu desky (rozteč, okraj): s vetsi deskou se mrizka prepocita
        ostatni_n = multimnozina(klic(d) for d in dn if not je_prac(d) and d["part_id"] != S.LOZ_PART)
        ostatni_p = multimnozina(klic(d) for d in dp if not je_prac(d) and d["part_id"] != S.LOZ_PART)
        zmizelo = {k: v - ostatni_n.get(k, 0) for k, v in ostatni_p.items() if v - ostatni_n.get(k, 0) > 0}
        pribylo = {k: v - ostatni_p.get(k, 0) for k, v in ostatni_n.items() if v - ostatni_p.get(k, 0) > 0}
        zasl_id = S.SYSTEMY[sys_]["zaslepka"]
        vyrez_posun = [round(an["parametry"][k] - ap["parametry"][k], 3) for k in ("vyrez1_x", "vyrez1_d", "vyrez1_z", "vyrez1_w")]
        if vyrez_posun != [0.0, 0.0, 0.0, 0.0]:
            if not (abs(vyrez_posun[0] - P) < 1e-3 and vyrez_posun[1:] == [0.0, 0.0, 0.0]):
                chyba.append(("vyrez: zmena parametru jina nez posun o P", vyrez_posun))
            pribylo = {}                                                 # police pod vyrezem, jeji zavesy a zaslepky se posunuly s vyrezem: shodu nehlidame, jen zmizeni zaslepek zadnich noh (nize)
        spatne_zmizeni = []
        for k, v in zmizelo.items():
            lo, hi = aabb_dilu(S, {"part_id": k[0], "position": list(k[1]), "quaternion": list(k[2]), "scale": list(k[3])})
            # zmizet smi jen zaslepka na hornim konci zadni nohy (uvnitr zadni nohy v x, kolem spodku desky v y)
            je_zadni_zaslepka = (k[0] == zasl_id and x_zadni_lice is not None and hi[0] <= x_zadni_lice + 0.05 and lo[0] >= x_zadni_lice - P - 0.05
                                 and lo[1] <= podspodek + 0.5 and hi[1] >= podspodek - 0.5)
            if not je_zadni_zaslepka and vyrez_posun == [0.0, 0.0, 0.0, 0.0]:
                spatne_zmizeni.append((k[0], lo, hi))
        if pribylo or spatne_zmizeni:
            chyba.append(("ostatni dily", {"pribylo": [(k[0], k[1]) for k in pribylo][:3], "spatne_zmizeni": spatne_zmizeni[:3]}))
        n_zasl_p = sum(1 for d in dp if d["part_id"] == zasl_id)
        n_zasl_n = sum(1 for d in dn if d["part_id"] == zasl_id)
        if n_zasl_p - n_zasl_n != len(zadni_nohy):
            chyba.append(("pocet zmizelych zaslepek", {"zmizelo": n_zasl_p - n_zasl_n, "zadnich_nohou": len(zadni_nohy)}))
        # (2b) pracovni deska: predni hrana, vyska, sirka beze zmeny; zadni hrana v rovine zadniho lice nohou; plocha o P x sirka vetsi
        if not (abs(lon[0] - lop[0]) < 0.01 and abs(lon[1] - lop[1]) < 0.01 and abs(hin[1] - hip[1]) < 0.01 and abs(lon[2] - lop[2]) < 0.01 and abs(hin[2] - hip[2]) < 0.01):
            chyba.append(("predni hrana / vyska / sirka desky", {"nova": [lon, hin], "puvodni": [lop, hip]}))
        if x_zadni_lice is None or abs(hin[0] - x_zadni_lice) > 0.01 or abs((hin[0] - hip[0]) - P) > 0.01:
            chyba.append(("zadni hrana desky", {"nova": hin[0], "puvodni": hip[0], "zadni_lice_nohou": x_zadni_lice, "P": P}))
        if abs((plocha(deska_n) - plocha(deska_p)) - P * sirka) > 0.5:
            chyba.append(("plocha desky", {"nova": plocha(deska_n), "puvodni": plocha(deska_p), "ocekavano_navic": P * sirka}))
        for d in loz_n:                                                          # kazda jednotka lezi cela v obrysu (nove) desky, na jeji horni plose
            lo_l, hi_l = aabb_dilu(S, d)
            if not (lon[0] - 0.05 <= lo_l[0] and hi_l[0] <= hin[0] + 0.05 and lon[2] - 0.05 <= lo_l[2] and hi_l[2] <= hin[2] + 0.05 and abs(lo_l[1] - hin[1]) < 0.05):
                chyba.append(("loziskova jednotka mimo desku", (lo_l, hi_l, lon, hin)))
                break
        # (2c) vsechny kusy desky lezi v obrysu a nepretinaji se (vyrezy a deleni u stredni nohy)
        for i, k in enumerate(deska_n):
            for j in range(i + 1, len(deska_n)):
                m = deska_n[j]
                pr = [min(k[1][a], m[1][a]) - max(k[0][a], m[0][a]) for a in (0, 2)]
                if pr[0] > 0.05 and pr[1] > 0.05:
                    chyba.append(("kusy desky se pretinaji", (i, j, pr)))
        # (2d) problemy: stejne jako pred zmenou (po posunu vyrezu jen stejne KODY - texty nesou rozmery / cisla dilu posunute police pod vyrezem)
        posunuty = vyrez_posun != [0.0, 0.0, 0.0, 0.0]
        if posunuty:
            if sorted(k_ for k_, _ in an["problemy"]) != sorted(k_ for k_, _ in ap["problemy"]):
                chyba.append(("problemy (kody)", {"nove": an["problemy"], "puvodni": ap["problemy"]}))
        elif sorted(an["problemy"]) != sorted(ap["problemy"]):
            chyba.append(("problemy", {"nove": an["problemy"], "puvodni": ap["problemy"]}))
        if an["hash"] == ap["hash"]:                                              # jiny model a cena = jiny hash (jen stoly BEZ stojek; se stojkami hash nemenny - kontroluje 2.1)
            chyba.append(("hash bez stojek se nezmenil", an["hash"]))
        # (2e) rozmery stolu, spoje: beze zmeny (kromě posunu vyrezu: police pod vyrezem se posunula s nim); cena viz nize
        if not posunuty and (any(abs(an["rozmery"][k] - ap["rozmery"][k]) > 1e-3 for k in ap["rozmery"]) or an["spoje"] != ap["spoje"]):                    # (rozmery: sum ~1e-5 mm z poctu AABB)
            chyba.append(("rozmery / spoje", {"nove": an["rozmery"], "puvodni": ap["rozmery"], "spoje": [an["spoje"], ap["spoje"]]}))
        # cena: vstup ceny desky je `deska_celek` (rozmery cele desky pred rozrezanim): u kazde pracovni desky (cela / leva a prava cast u stredni nohy) o P delsi v hloubce, sirka stejna; celkova cena se muze i snizit
        # (zmizi zaslepky, loziskova mrizka muze mit o jednotku mene), proto jen rozumne meze
        celky_n = sorted((d["deska_id"], d["deska_celek"]) for d in dn if je_prac(d) and d.get("deska_celek"))
        celky_p = sorted((d["deska_id"], d["deska_celek"]) for d in dp if je_prac(d) and d.get("deska_celek"))
        if [c_[0] for c_ in celky_n] != [c_[0] for c_ in celky_p] or not all(abs(cn_[1][0] - cp_[1][0] - P) < 0.01 and abs(cn_[1][1] - cp_[1][1]) < 0.01 for cn_, cp_ in zip(celky_n, celky_p)):
            chyba.append(("deska_celek (vstup ceny desky)", {"nove": celky_n, "puvodni": celky_p, "P": P}))
        if an["cena"] and ap["cena"] and not (abs(an["cena"]["bez_dph"] - ap["cena"]["bez_dph"]) <= 0.2 * ap["cena"]["bez_dph"]):
            chyba.append(("cena mimo rozumne meze", [an["cena"]["bez_dph"], ap["cena"]["bez_dph"]]))
        # (2f) vyrezy: parametry (poloha / rozmer po orezu) jsou stejne nebo vetsi o P (jen kdyz byly orezany zadni hranou)
        for k in ("vyrez1_x", "vyrez1_d", "vyrez1_z", "vyrez1_w"):
            if an["parametry"][k] < ap["parametry"][k] - 1e-6:
                chyba.append(("vyrez parametr zmenseny", (k, an["parametry"][k], ap["parametry"][k])))
        if chyba:
            chyby_a.append((vn["popis"], chyba[:2]))
        else:
            shoda_a += 1
    over(f"2.1 SE stojkami (B i C) je VSE shodne s puvodnim stavem: dily, parametry, problemy, rozmery, spoje, cena i kusovnik ({shoda_bc} vyberu)", not chyby_bc and shoda_bc > 0, chyby_bc[:3])
    over(f"2.2 BEZ stojek (A, {pocty['A']} vyberu; {pocty['chyba_obe']} spolecne odmitnutych): vse mimo desku a zaslepky shodne, deska ma prednim hranu / vysku / sirku stejnou, zadni hranu v rovine zadniho lice nohou "
         "(+ tloustka profilu), plochu o tloustku x sirka vetsi, kusy se nepretinaji, problemy stejne, rozmery a spoje stejne, vstup ceny desky (`deska_celek`) o tloustku profilu delsi", not chyby_a and pocty["A"] >= 2 * n, chyby_a[:3])
    over("2.3 kazdy vyber dopadl pred i po zmene stejne (nikdy jen jedna z variant odmitnuta)", not ruzne_chyby, ruzne_chyby[:3])

    print("\n## 3) meze posuvniku vyrezu a cena")
    mz_n, mz_p = nov["meze_vyrezu"], puv["meze_vyrezu"]
    P30, P40 = 30, 40
    over("3.1 mezi posuvniku vyrezu v obchode: SE stojkami beze zmeny, BEZ stojek hloubka a poloha vyrezu o tloustku profilu vetsi (30: +30, 40: +40), sirka beze zmeny",
         mz_n["30_1"] == mz_p["30_1"] and mz_n["40_1"] == mz_p["40_1"]
         and mz_n["30_0"]["cut1d"]["max"] == mz_p["30_0"]["cut1d"]["max"] + P30 and mz_n["30_0"]["cut1x"]["max"] == mz_p["30_0"]["cut1x"]["max"] + P30
         and mz_n["40_0"]["cut1d"]["max"] == mz_p["40_0"]["cut1d"]["max"] + P40 and mz_n["40_0"]["cut1x"]["max"] == mz_p["40_0"]["cut1x"]["max"] + P40
         and mz_n["30_0"]["cut1w"] == mz_p["30_0"]["cut1w"] and mz_n["30_0"]["cut1z"] == mz_p["30_0"]["cut1z"], {"nove": mz_n, "puvodni": mz_p})

    over("3.2 schema karet (#4934 system 30, #4954 system 40): staticke maximum posuvniku vyrezu cut1d / cut1x je nejvyse mez pres vsechny volby - neni mensi nez mez v options BEZ stojek (30: +30, 40: +40 oproti puvodnimu)",
         nov["schema_max"]["4934"]["cut1d"] >= mz_n["30_0"]["cut1d"]["max"] and nov["schema_max"]["4934"]["cut1x"] >= mz_n["30_0"]["cut1x"]["max"]
         and nov["schema_max"]["4954"]["cut1d"] >= mz_n["40_0"]["cut1d"]["max"] and nov["schema_max"]["4954"]["cut1x"] >= mz_n["40_0"]["cut1x"]["max"]
         and nov["schema_max"]["4934"]["cut1d"] == puv["schema_max"]["4934"]["cut1d"] + 30 and nov["schema_max"]["4954"]["cut1d"] == puv["schema_max"]["4954"]["cut1d"] + 40, {"nove": nov["schema_max"], "puvodni": puv["schema_max"]})

    print("\n## 4) GLB (model) a hrana desky v modelu")
    import stul_shop as SH  # noqa: E402
    import stul_glb as G  # noqa: E402
    import v3d_glb  # noqa: E402
    for system in (30, 40):
        sel = {**SH.vychozi_vyber(system), **BEZ_STOJEK}
        p, _ = SH.normalizuj(sel, system)
        h, raw = G.model_pro_parametry(p)
        spec = v3d_glb.embedded_spec(raw)
        try:
            out = v3d_glb.sanitize(raw, spec)
            v3d_glb.final_check(v3d_glb.read_glb(out)[0])
            kontrola = True
        except Exception as e:                                         # noqa: BLE001
            kontrola = repr(e)
        over(f"4.{system // 10 - 2} system {system} bez stojek: model se stavi a projde kontrolou zakaznickeho GLB", kontrola is True and len(raw) > 100000, kontrola)
    print(f"\n{sum(vysl)}/{len(vysl)} OK")
    sys.exit(0 if all(vysl) else 1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dump":
        dump(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]))
    else:
        main()
