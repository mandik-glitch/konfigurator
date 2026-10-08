#!/opt/konfigurator/api/venv/bin/python
"""Test: plastovy KUZEL stavitelne patky je v modelu stolu samostatny kus v cerne (api/stul_glb.py, KUZEL_PATKY; Robert 2026-10-08: "stavitelne patky se skladaji ze dvou casti: sroub s matici
a plastovy kuzel - dat do cerne barvy"). Porovnava model ZIVEHO (nebo kandidatniho) stul_glb.py se stavem PRED zmenou (soubor z `git show <ZAKLAD>:api/stul_glb.py`, vychozi `d1f2950a^` = revize tesne PRED zmenou; HEAD ji uz obsahuje, takze by nic neporovnal).

Hlida: (1) rozdeleni katalogovych patek 3251 / 3283 (kuzel = cast pod rovinou, rozmery, nic neztraceno), (2) GEOMETRIE modelu se nezmenila (multimnozina trojuhelniku vsech uzlu = jako pred
zmenou), jen materialy: kuzel v uzlu "cerna", sroub s maticí v "ocel", (3) stoly BEZ patek jsou bajt po bajtu stejne, (4) rozsahy dilu pro zive tazeni (dil = sroub, extra = kuzel) ukazuji
presne na vrcholy, (5) model projde kontrolou zakaznickeho GLB (v3d_glb.sanitize + final_check), (6) hash konfigurace se nezmenil.

Spusteni (DB pres systemd): systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PRIVATE_FILES_DIR=/tmp/pf_patky \
   --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_patky_kuzel/test_patky_kuzel.py   (kandidat: KUZEL_DIR=<adresar s kandidatnim stul_glb.py>; zaklad: ZAKLAD=<git revize>)"""
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import threading

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
if os.environ.get("KUZEL_DIR"):
    sys.path.insert(0, os.environ["KUZEL_DIR"])
_o = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
try:
    import stul_konfigurator as S  # noqa: E402
    import stul_glb as G  # noqa: E402
    import stul_shop as SH  # noqa: E402
    import v3d_glb  # noqa: E402
    import stul_koty  # noqa: E402
finally:
    threading.Thread.start = _o

ZAKLAD = os.environ.get("ZAKLAD", "d1f2950a^")                    # revize tesne pred zmenou (po commitu zmeny uz HEAD jako zaklad nic neporovna)
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:700]))


def nacti_zaklad():
    """stul_glb.py ze zakladni revize (pred zmenou) jako samostatny modul stul_glb_zaklad; pouziva stejne S / stul_koty."""
    kod = subprocess.run(["git", "-C", REPO, "show", f"{ZAKLAD}:api/stul_glb.py"], capture_output=True, text=True, check=True).stdout
    tmp = os.path.join(tempfile.mkdtemp(prefix="stul_glb_zaklad_"), "stul_glb_zaklad.py")
    open(tmp, "w", encoding="utf-8").write(kod)
    spec = importlib.util.spec_from_file_location("stul_glb_zaklad", tmp)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def cti_glb(raw):
    off, js, binc = 12, None, None
    while off < len(raw):
        ln, typ = struct.unpack("<II", raw[off:off + 8])
        if typ == 0x4E4F534A:
            js = json.loads(raw[off + 8:off + 8 + ln])
        elif typ == 0x004E4942:
            binc = raw[off + 8:off + 8 + ln]
        off += 8 + ln
    return js, binc


def uzly(raw):
    """[(nazev, materialIndex, barva, pozice Nx3, indexy Mx3)] pro kazdy uzel s meshem v poradi nodes."""
    js, binc = cti_glb(raw)

    def acc(i):
        a = js["accessors"][i]; bv = js["bufferViews"][a["bufferView"]]
        dt = {5126: np.float32, 5125: np.uint32}[a["componentType"]]
        n = a["count"] * {"SCALAR": 1, "VEC3": 3}[a["type"]]
        arr = np.frombuffer(binc, dtype=dt, count=n, offset=bv.get("byteOffset", 0) + a.get("byteOffset", 0))
        return arr.reshape(-1, 3) if a["type"] == "VEC3" else arr
    out = []
    for i, nd in enumerate(js["nodes"]):
        if "mesh" not in nd:
            out.append(None); continue
        pr = js["meshes"][nd["mesh"]]["primitives"][0]
        mat = js["materials"][pr["material"]]["pbrMetallicRoughness"]
        out.append((nd["name"], pr["material"], tuple(mat["baseColorFactor"]), acc(pr["attributes"]["POSITION"]), acc(pr["indices"]).reshape(-1, 3)))
    return out


def klice_trojuhelniku(P, T):
    """Kanonicke klice trojuhelniku (bez ohledu na poradi vrcholu a vrstvu): pole (n, 3) serazenych 64bit hashu vrcholu zaokrouhlenych na 0,001 mm."""
    V = np.round(P.astype(np.float64)[T] * 1000).astype(np.int64)                      # (n, 3, 3)
    k = (V[..., 0] * 73856093) ^ (V[..., 1] * 19349663) ^ (V[..., 2] * 83492791)       # (n, 3)
    return np.sort(k, axis=1)


def multimnozina(raw, jen_material=None):
    kl = [klice_trojuhelniku(P, T) for (_n, _m, barva, P, T) in [u for u in uzly(raw) if u] if jen_material is None or barva == jen_material]
    if not kl:
        return np.zeros((0, 3), np.int64)
    K = np.vstack(kl)
    return K[np.lexsort((K[:, 2], K[:, 1], K[:, 0]))]


def poloha_dilu(cast):
    return G._transformuj(cast["part_id"], cast)


def vyber(system, **zmeny):
    sel = dict(SH.vychozi_vyber(system))
    sel.update(zmeny)
    return sel


def sestav(system, sel):
    p, _ = SH.normalizuj(sel, system)
    return S.sestav_stul(**p)


def main():
    H = nacti_zaklad()
    print(f"zaklad: git {ZAKLAD}:api/stul_glb.py; kandidat/zivy modul: {G.__file__}")
    over("0.1 zaklad nema KUZEL_PATKY (je to stav PRED zmenou), testovany modul ano", not hasattr(H, "KUZEL_PATKY") and set(G.KUZEL_PATKY) == {"product_3251", "product_3283"}, sorted(getattr(G, "KUZEL_PATKY", {})))
    over("0.2 patky v systemech: 30 / 35 = 3251, 40 / 45 = 3283 (S.SYSTEMY) a oba dily maji rovinu", {S.SYSTEMY[s_]["patka"] for s_ in (30, 35, 40, 45)} <= set(G.KUZEL_PATKY) and S.SYSTEMY[30]["patka"] == S.SYSTEMY[35]["patka"] == "product_3251"
         and S.SYSTEMY[40]["patka"] == S.SYSTEMY[45]["patka"] == "product_3283", {s_: S.SYSTEMY[s_]["patka"] for s_ in S.SYSTEMY})

    # ---------------------------------------------------------------- 1) rozdeleni katalogovych patek
    print("\n## 1) rozdeleni katalogovych patek (maska kuzele)")
    for pid, rovina, vyska_kuzele, polomer in (("product_3251", -50.0, 25.0, 20.5), ("product_3283", -48.0, 31.0, 30.0)):
        pos, nrm, tri = G.nacti_mesh(pid)
        m = G._kuzel_patky(pid)
        over(f"1.{pid[-4:]}a maska existuje, neni prazdna ani plna ({int(m.sum())} z {len(m)} trojuhelniku)", m is not None and m.any() and not m.all())
        (p_s, n_s, t_s), (p_k, n_k, t_k) = G._rozdel_podle_masky(pos, nrm, tri, m)
        over(f"1.{pid[-4:]}b nic se neztratilo ani nezdvojilo: trojuhelniky sroub + kuzel = puvodni ({len(t_s)} + {len(t_k)} = {len(tri)})", len(t_s) + len(t_k) == len(tri))
        over(f"1.{pid[-4:]}c kuzel: vyska {vyska_kuzele} mm (od podlahy po rovinu), polomer {polomer} mm, nad rovinou nic", abs(p_k[:, 1].max() - rovina) < 0.05 and abs(p_k[:, 1].min() - (rovina - vyska_kuzele)) < 0.05
             and abs(np.sqrt(p_k[:, 0] ** 2 + p_k[:, 2] ** 2).max() - polomer) < 0.05, (p_k[:, 1].min(), p_k[:, 1].max(), np.sqrt(p_k[:, 0] ** 2 + p_k[:, 2] ** 2).max()))
        over(f"1.{pid[-4:]}d sroub s maticí: od roviny po horni konec zavitu (y 0), polomer matice (sestihran) < 12 mm, pod rovinou jen vrcholy hrany", abs(p_s[:, 1].max()) < 0.05 and p_s[:, 1].min() >= rovina - 1e-3
             and np.sqrt(p_s[:, 0] ** 2 + p_s[:, 2] ** 2).max() < 12.0, (p_s[:, 1].min(), p_s[:, 1].max(), np.sqrt(p_s[:, 0] ** 2 + p_s[:, 2] ** 2).max()))
        over(f"1.{pid[-4:]}e ostatni dily kuzel nemaji (maska None): profil, rohova spojka, zaslepka", all(G._kuzel_patky(x) is None for x in ("Object_11", "product_3176", "product_3091", "product_3071", "product_3158")))

    # ---------------------------------------------------------------- 2) modely konfiguraci
    print("\n## 2) modely: geometrie beze zmeny, kuzel cerny, sroub s maticí ocel")
    konfigurace = [
        ("30 s patkami", 30, vyber(30, wheels=False, feet=True)),
        ("35 s patkami (bez navleku)", 35, vyber(35, wheels=False, feet=True, sleeve=False)),
        ("40 s patkami", 40, vyber(40, wheels=False, feet=True)),
        ("45 s patkami (hluboky stul, stredni nohy)", 45, vyber(45, wheels=False, feet=True, d=2000)),
        ("40 siroky stul se stredni nohou", 40, vyber(40, wheels=False, feet=True, w=2000)),
        ("40 s patkami + police + supliky + LED", 40, vyber(40, wheels=False, feet=True, shelf=2)),
        ("30 bez patek (kolecka)", 30, vyber(30, wheels=True, feet=False)),
        ("40 bez patek (kolecka)", 40, vyber(40, wheels=True, feet=False)),
        ("35 s navlekem", 35, vyber(35, wheels=False, feet=False)),
    ]
    cerna, ocel = G.MATERIALY["cerna"]["baseColorFactor"], G.MATERIALY["ocel"]["baseColorFactor"]
    for nazev, sy, sel in konfigurace:
        gen = sestav(sy, sel)
        dily = gen["dily"]
        nohy = [i for i, c in enumerate(dily) if c["part_id"] in G.KUZEL_PATKY]
        raw_h = H.poskladej_glb(dily, gen["rozmery"], stul_koty.koty(gen))
        rozsahy_h, extra_h = H._POSLEDNI_ROZSAHY[0], H._POSLEDNI_EXTRA[0]
        raw_n = G.poskladej_glb(dily, gen["rozmery"], stul_koty.koty(gen))
        rozsahy_n, extra_n = G._POSLEDNI_ROZSAHY[0], G._POSLEDNI_EXTRA[0]
        if not nohy:
            over(f"2 {nazev}: bez patek je model BAJT PO BAJTU stejny jako pred zmenou a bez extra rozsahu kuzelu", raw_n == raw_h and (extra_n or {}) == (extra_h or {}), (len(raw_n), len(raw_h)))
            continue
        over(f"2 {nazev}: geometrie (multimnozina vsech trojuhelniku vsech uzlu) je STEJNA jako pred zmenou ({len(nohy)} patek)", np.array_equal(multimnozina(raw_n), multimnozina(raw_h)))
        cerna_h = multimnozina(raw_h, tuple(cerna)); cerna_n = multimnozina(raw_n, tuple(cerna))
        ocel_h = multimnozina(raw_h, tuple(ocel)); ocel_n = multimnozina(raw_n, tuple(ocel))
        n_kuzel = sum(int(G._kuzel_patky(dily[i]["part_id"]).sum()) for i in nohy)
        over(f"2 {nazev}: v \"cerna\" pribylo {n_kuzel} trojuhelniku kuzelu ({len(cerna_n) - len(cerna_h)}), v \"ocel\" o tolik ubylo ({len(ocel_h) - len(ocel_n)})", len(cerna_n) - len(cerna_h) == n_kuzel == len(ocel_h) - len(ocel_n), (len(cerna_h), len(cerna_n), len(ocel_h), len(ocel_n), n_kuzel))
        # rozsahy: dil = sroub s maticí (uzel materialu dilu), extra = kuzel (uzel "cerna"); presne na vrcholy
        u_n = uzly(raw_n)
        posun = G._POSLEDNI_POSUN[0]
        ok_roz, ok_extra, detail = True, True, None
        for i in nohy:
            pos_t, nrm_t, tri_t = G._transformuj(dily[i]["part_id"], dily[i])
            m = G._kuzel_patky(dily[i]["part_id"])
            (p_s, _a, _b), (p_k, _c, _d) = G._rozdel_podle_masky(pos_t, nrm_t, tri_t, m)
            uz, od, pocet = rozsahy_n[i]
            node = u_n[uz]
            ok_roz &= bool(np.allclose(node[3][od:od + pocet], (p_s + posun).astype(np.float32), atol=1e-3)) and pocet == len(p_s) and node[2] == tuple(ocel)
            ex = (extra_n or {}).get(i)
            if not ex or len(ex) != 1:
                ok_extra, detail = False, ("extra", i, ex); continue
            uzk, odk, pk = ex[0]
            nodek = u_n[uzk]
            ok_extra &= bool(np.allclose(nodek[3][odk:odk + pk], (p_k + posun).astype(np.float32), atol=1e-3)) and pk == len(p_k) and nodek[2] == tuple(cerna)
        over(f"2 {nazev}: rozsah dilu (zive tazeni) ukazuje presne na vrcholy sroubu s maticí v uzlu \"ocel\"", ok_roz)
        over(f"2 {nazev}: extra rozsah ukazuje presne na vrcholy kuzele v uzlu \"cerna\" (cerny plast), u kazde patky prave jeden", ok_extra, detail)
        over(f"2 {nazev}: cerny plast je prave v JEDNOM uzlu (kuzely vsech patek spolu s ostatnimi cernymi dily), pocet uzlu <= pocet materialu + supliky", sum(1 for u in u_n if u and u[2] == tuple(cerna)) == 1 and len([u for u in u_n if u]) <= len(G.POREDI_MATERIALU) + 1)
        # vyska kuzele nad podlahou: kuzel zacina na podlaze (y 0) a konci v rovine 25 / 31 mm; sroub s maticí nad ni
        pid0 = dily[nohy[0]]["part_id"]
        cone_h = {"product_3251": 25.0, "product_3283": 31.0}[pid0]
        ex0 = extra_n[nohy[0]][0]
        pk_ = u_n[ex0[0]][3][ex0[1]:ex0[1] + ex0[2]]
        over(f"2 {nazev}: kuzel patky stoji na podlaze (min y = 0) a je {cone_h:g} mm vysoky", abs(pk_[:, 1].min()) < 0.01 and abs(pk_[:, 1].max() - cone_h) < 0.05, (pk_[:, 1].min(), pk_[:, 1].max()))
        # kontrola zakaznickeho GLB (nabidka / karta)
        try:
            spec = v3d_glb.embedded_spec(raw_n)
            out = v3d_glb.sanitize(raw_n, spec)
            gltf, _bin = v3d_glb.read_glb(out)
            v3d_glb.final_check(gltf)
            kontrola = True
        except Exception as e:                                       # noqa: BLE001
            kontrola = repr(e)
        over(f"2 {nazev}: model projde v3d_glb.sanitize + final_check (zakaznicka nabidka / karta)", kontrola is True, kontrola)

    # ---------------------------------------------------------------- 3) hash a verejne funkce
    print("\n## 3) hash, cache, razitka")
    sel = vyber(40, wheels=False, feet=True)
    p, _ = SH.normalizuj(sel, 40)
    h_new = G.kanonicky_hash(p)
    puv_kuzel = dict(G.KUZEL_PATKY)
    try:
        G.KUZEL_PATKY.clear()                                                                       # hash nesmi zalezet na existenci kuzelu: zmena je jen v modelu (pozdejsi zmeny hashe od jinych botu zaklad uz neporovnava)
        h_bez = G.kanonicky_hash(p)
    finally:
        G.KUZEL_PATKY.update(puv_kuzel)
    over("3.1 kanonicky hash konfigurace NEZAVISI na kuzelu patek (zmena je jen v modelu; karty STUL-S* a hashe zustavaji) a RULES_VERSION je jako pred zmenou", h_new == h_bez and G.RULES_VERSION == H.RULES_VERSION, (h_new, h_bez, G.RULES_VERSION, H.RULES_VERSION))
    h1, d1 = G.model_pro_parametry(S.sestav_stul(**p)["parametry"])
    h2, d2 = G.model_pro_parametry(S.sestav_stul(**p)["parametry"])
    over("3.2 model_pro_parametry: stejny hash a stejne bajty pri opakovani (cache) a rozsahy v cache", h1 == h2 == h_new and d1 == d2 and h1 in G._ROZSAHY_CACHE and G._EXTRA_CACHE.get(h1), (h1, h_new))
    hr, dr = G.model_pro_parametry(S.sestav_stul(**p)["parametry"], razitka=True)
    hb, db = G.model_pro_parametry(S.sestav_stul(**p)["parametry"], razitka=False)
    over("3.3 model s razitky (od pravidla 61 / 2026-10-08 i VYCHOZI model generatoru) se stavi, ma kuzel v cerne i logo (vetsi nez holy model); razitka=False = holy model, taky s cernym kuzelem",
         hr == hb == h_new and dr == d1 and db != dr and len(dr) > len(db) and any(u and u[2] == tuple(cerna) for u in uzly(dr)) and any(u and u[2] == tuple(cerna) for u in uzly(db)),
         (len(dr), len(db), dr == d1))
    print("\n%d/%d OK" % (sum(vysl), len(vysl)))
    sys.exit(0 if all(vysl) else 1)


main()
