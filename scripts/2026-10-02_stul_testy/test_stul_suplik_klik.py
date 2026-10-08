#!/opt/konfigurator/api/venv/bin/python
"""SPODNI SUPLIK boxu (s delicimi pricky) NA KLIK v modelu stolu (bot10, 2026-10-05; Robert: "nech se 1 suplik z boxu v 3D nahledu otevira na kliknuti, zavira na dalsi kliknuti a tak dokola", upresneni: "mel jsem na mysli suplik spodni s temi delicimi pricky"). Bez DB.

  api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_suplik_klik.py        (soucasti run_all.sh; skutecny prohlizec: test_stul_suplik_klik.js)

Hlida (nezavisle na kodu, z geometrie katalogovych modelu a vyslednych GLB):
 - v kazdem ze tri modelu skrine (product_4956 1 suplik, 4930 dva, 4957 tri) se najde SPODNI suplik (hluboka korba s 87 delicimi pricky + rukojet + drobne dily), ne telo, ne horni supliky a ne zamek,
 - GLB: suplik je vlastni sit pod prazdnym pivotem `p1`, pivot je v koreni sceny, spec nese jediny pohyb k=drawer (T podel PREDKU skrine, 250-400 mm, 700 ms, pick p1) a prochazi validate_spec,
 - zadne vrcholy nezmizely (telo + suplik = puvodni sit), v zavrenem stavu je celo supliku v rovine cela skrine, otevreny suplik zustava ve skrini aspon 50 mm,
 - pohyb nikam nenarazi: otevreny suplik neprotina zadny jiny dil stolu (mrizka konfiguraci vc. strany boxu, polic, panelu, LED),
 - zive tazeni: rozsah dilu boxu = jen telo, suplik je DALSI rozsah (`zive_rozsahy_extra`), `zive_rozsahy` ma porad rozsah pro kazdy dil,
 - bez boxu: zadny pivot ani pohyb, GLB jako dosud; pocet supliku 1 / 2 / 3 i boxy vlevo (osa pohybu miri vzdy dopredu)."""
import itertools
import json
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "api"))
import stul_glb as G  # noqa: E402
import stul_konfigurator as S  # noqa: E402
import v3d_glb  # noqa: E402

OK, FAILS = 0, []


def check(cond, msg, detail=""):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg} {detail}")


def rozbal(glb):
    off, js, binc = 12, None, None
    while off < len(glb):
        ln, typ = struct.unpack("<II", glb[off:off + 8])
        if typ == 0x4E4F534A:
            js = json.loads(glb[off + 8:off + 8 + ln].decode("utf-8"))
        elif typ == 0x004E4942:
            binc = glb[off + 8:off + 8 + ln]
        off += 8 + ln
    return js, binc


def vrcholy_uzlu(js, binc, i):
    nd = js["nodes"][i]
    prim = js["meshes"][nd["mesh"]]["primitives"][0]
    acc = js["accessors"][prim["attributes"]["POSITION"]]
    bv = js["bufferViews"][acc["bufferView"]]
    return np.frombuffer(binc, dtype="<f4", count=acc["count"] * 3, offset=bv["byteOffset"] + acc.get("byteOffset", 0)).reshape(-1, 3).astype(float)


def aabb_prunik(a_lo, a_hi, b_lo, b_hi, tol=1.0):
    return bool(np.all(np.minimum(a_hi, b_hi) - np.maximum(a_lo, b_lo) > tol))


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("1) spodni suplik (s delicimi pricky) v modelech skrine")
for pid, pocet, ocek_hloubka in (("product_4956", 1, 530.0), ("product_4930", 2, 530.0), ("product_4957", 3, 530.0)):
    pos, nrm, tri = G.nacti_mesh(pid)
    res = G._suplik_spodni(pid)
    check(res is not None, f"{pid}: spodni suplik nalezen")
    if res is None:
        continue
    maska, hloubka = res
    P = np.asarray(pos, float)
    rel = P - P.min(axis=0)
    v = rel[np.unique(tri[maska].ravel())]
    check(abs(hloubka - ocek_hloubka) < 1.0, f"{pid}: hloubka korby {hloubka:.1f} mm (ocekavano {ocek_hloubka:.0f})")
    check(3500 <= int(maska.sum()) <= 4500, f"{pid}: pocet trojuhelniku supliku {int(maska.sum())} (hluboka korba + rukojet + delici pricky + drobne dily)")
    komp = G._souvisle_komponenty(pos, tri)
    clenove = np.unique(komp[maska])
    pricek = sum(1 for r_ in clenove if int((komp == r_).sum()) == 28)
    check(pricek >= 80, f"{pid}: v supliku je {pricek} delicich pricek (87 malych dilu po 28 trojuhelnicich)")
    # spodni = nejnizsi korba: pod nim uz neni zadna dalsi korba (komponenta sirsi nez 400 a hlubsi nez 300 mm)
    vyssi = 0
    for r in np.unique(komp):
        if r in set(np.unique(komp[maska])):
            continue
        vs = np.unique(tri[komp == r].ravel())
        lo, hi = rel[vs].min(axis=0), rel[vs].max(axis=0)
        if (hi[0] - lo[0]) > 400 and (hi[1] - lo[1]) > 300 and (hi[2] - lo[2]) < 150 and lo[2] < v[:, 2].min():
            vyssi += 1
    check(vyssi == 0, f"{pid}: pod vybranym supliku neni dalsi suplik (jsou jen horni, mensi bez pricek)")
    # telo skrine (nejvetsi komponenta) a zamek (u celni hrany) do supliku nepatri
    vyska = {r_: float(np.ptp(rel[np.unique(tri[komp == r_].ravel())][:, 2])) for r_ in np.unique(komp)}
    nej = max(vyska, key=vyska.get)                                    # telo skrine = nejvyssi komponenta (ne ta s nejvic trojuhelniky: u 4930 ma hluboka spodni korba 1148 tri vic nez telo 1054)
    check(not bool(np.any(maska & (komp == nej))), f"{pid}: telo skrine neni v supliku")
    celo_lo_y = rel[:, 1].min()
    check(v[:, 1].min() > celo_lo_y + 2.0 and (v[:, 1].max() - v[:, 1].min()) > 300, f"{pid}: suplik lezi ve skrini (celni hrana skrine je vpredu, y_min supliku {v[:, 1].min() - celo_lo_y:.1f} mm za ni)")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("2) GLB: uzel supliku, pivot p1, pohyb v spec")
for system in (30, 35, 40):
    S._SYSTEM.set(system)
    for pocet in (1, 2, 3):
        for vlevo in (False, True):
            r = S.sestav_stul(system=system, suplik=True, suplik_pocet=pocet, suplik_vlevo=vlevo, sirka=1600)
            glb = G.poskladej_glb(r["dily"], r["rozmery"])
            js, binc = rozbal(glb)
            extra = G._POSLEDNI_EXTRA[0]
            roz = G._POSLEDNI_ROZSAHY[0]
            jm = f"system {system}, {pocet} suplik(y), vlevo={vlevo}"
            piv = [i for i, n in enumerate(js["nodes"]) if n.get("name") == "p1"]
            check(len(piv) == 1 and "mesh" not in js["nodes"][piv[0]] and len(js["nodes"][piv[0]].get("children", [])) == 1, f"{jm}: prazdny pivot p1 s jednim potomkem")
            if len(piv) != 1:
                continue
            dite = js["nodes"][piv[0]]["children"][0]
            check(dite not in js["scenes"][0]["nodes"] and piv[0] in js["scenes"][0]["nodes"], f"{jm}: pivot je v koreni sceny, uzel supliku je jeho potomek")
            check(js["nodes"][dite]["name"] == f"n{dite}" and "mesh" in js["nodes"][dite], f"{jm}: uzel supliku n{dite} ma sit")
            spec = js["scenes"][0]["extras"]["v3d"]
            mo = spec["motions"]
            check(len(mo) == 1 and mo[0]["id"] == "m1" and mo[0]["k"] == "drawer" and mo[0]["n"] == 1 and mo[0]["pick"] == ["p1"] and len(mo[0]["steps"]) == 1, f"{jm}: jediny pohyb m1 (drawer, pick p1)", str(mo))
            st = mo[0]["steps"][0]
            ax = np.array(st["ax"], float)
            check(st["p"] == "p1" and st["op"] == "T" and abs(np.linalg.norm(ax) - 1) < 1e-4 and abs(ax[1]) < 1e-6 and 250 <= st["v"] <= 400 and st["ms"] == 700, f"{jm}: krok T podel vodorovneho jednotkoveho vektoru, 250-400 mm, 700 ms", str(st))
            try:
                v3d_glb.validate_spec(spec)
                platny = True
            except Exception as e:                                               # noqa: BLE001
                platny = str(e)
            check(platny is True, f"{jm}: spec projde validate_spec (kontrakt v3d)", str(platny))
            # extra rozsah a pocty
            idx_box = [i for i, d in enumerate(r["dily"]) if d["part_id"] in S.SUPLIK_PARTY_VSE]
            check(len(idx_box) == 1 and extra is not None and list(extra.keys()) == [idx_box[0]], f"{jm}: extra rozsah je prave pro dil boxu", str(extra))
            if not (len(idx_box) == 1 and extra):
                continue
            ex = extra[idx_box[0]]
            check(len(ex) == 1 and ex[0][0] == dite and ex[0][1] == 0 and ex[0][2] == len(vrcholy_uzlu(js, binc, dite)), f"{jm}: extra rozsah = [uzel supliku, 0, pocet vrcholu uzlu]", str(ex))
            check(len(roz) == len(r["dily"]) and roz[idx_box[0]] is not None, f"{jm}: zive_rozsahy ma stale rozsah pro kazdy dil (telo boxu)")
            p_cele, n_cele, t_cele = G._transformuj(r["dily"][idx_box[0]]["part_id"], r["dily"][idx_box[0]])
            body = roz[idx_box[0]]
            check(body[2] + ex[0][2] == len(p_cele), f"{jm}: telo + suplik = vsechny vrcholy boxu ({body[2]} + {ex[0][2]} = {len(p_cele)})")
            # geometrie: smer = predek skrine; zavreny suplik v rovine cela skrine
            posun = np.array(G._POSLEDNI_POSUN[0], float)
            vs = vrcholy_uzlu(js, binc, dite) - posun                              # svetove souradnice generatoru
            vb = vrcholy_uzlu(js, binc, roz[idx_box[0]][0])[roz[idx_box[0]][1]:roz[idx_box[0]][1] + body[2]] - posun
            u_s, u_b = vs @ ax, vb @ ax
            check(abs(u_s.max() - u_b.max()) < 20.0, f"{jm}: celo zavreneho supliku je v rovine cela skrine (rozdil {u_s.max() - u_b.max():.1f} mm)")
            check(u_s.min() > u_b.min() + 20.0, f"{jm}: suplik zacina uvnitr skrine")
            zbyva = (u_s.min() + st["v"]) - u_b.min()
            check(zbyva >= 50.0, f"{jm}: otevreny suplik zustava ve skrini aspon 50 mm (zbyva {zbyva:.0f} mm)")
            check(abs(ax[0]) > 0.99, f"{jm}: osa miri dopredu / dozadu stolu (X), {np.round(ax, 3).tolist()}")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("3) otevreny suplik nikam nenarazi (mrizka konfiguraci)")


def mrizka_pruniku(smer=1.0, vzorky_max=None, vzdalenost=None, osa_pevna=None):
    """Pro mrizku konfiguraci: otevreny suplik (posun o `vzdalenost` mm, vychozi serverova, podel osy * smer) vs. AABB ostatnich dilu; vraci (pocet sestav, seznam pruniku)."""
    S._SYSTEM.set(30)
    vz, nal = 0, []
    for pocet, vlevo, sirka, police, panely, led in itertools.product((1, 2, 3), (False, True), (1000, 1280, 1800, 2400), (0, 1, 3), (0, 1), (False, True)):
        if vzorky_max and vz >= vzorky_max:
            break
        r = S.sestav_stul(system=30, suplik=True, suplik_pocet=pocet, suplik_vlevo=vlevo, sirka=float(sirka), police=police, panely=panely, led=led, hloubka=800.0)
        idx_box = [i for i, d in enumerate(r["dily"]) if d["part_id"] in S.SUPLIK_PARTY_VSE]
        if not idx_box or not r["parametry"]["suplik"]:
            continue
        cast = r["dily"][idx_box[0]]
        hs = G._suplik_spodni(cast["part_id"])
        p, n, t = G._transformuj(cast["part_id"], cast)
        ps = p[np.unique(t[hs[0]].ravel())]
        Rm = S.kvat_na_matici(cast["quaternion"])
        sc = np.array(cast["scale"], float)
        osa = (np.array([0.0, -1.0, 0.0]) * sc) @ Rm.T
        osa = smer * osa / np.linalg.norm(osa)
        if osa_pevna is not None:
            osa = np.array(osa_pevna, float)
        v_mm = vzdalenost or round(min(G.SUPLIK_OTEVRENI_MAX_MM, G.SUPLIK_OTEVRENI_PODIL * hs[1] * abs(float(sc[1]))), 1)
        lo = np.minimum(ps.min(axis=0), ps.min(axis=0) + osa * v_mm)             # AABB drahy supliku (zavreny + otevreny)
        hi = np.maximum(ps.max(axis=0), ps.max(axis=0) + osa * v_mm)
        vz += 1
        for i, d in enumerate(r["dily"]):
            if i == idx_box[0]:
                continue
            bl, bh = np.array(S._aabb(d)[0], float), np.array(S._aabb(d)[1], float)
            if not aabb_prunik(lo, hi, bl, bh, tol=2.0):
                continue
            for k in range(0, int(v_mm) + 1, 10):                                 # presne: sit supliku posunuty po 10 mm proti AABB dilu
                q = ps + osa * k
                if aabb_prunik(q.min(axis=0), q.max(axis=0), bl, bh, tol=2.0):
                    nal.append((pocet, vlevo, sirka, police, panely, led, d["part_id"], k))
                    break
    return vz, nal


vzorky, nalez = mrizka_pruniku()
check(vzorky >= 150, f"mrizka konfiguraci: {vzorky} sestav s boxem")
check(not nalez, f"otevreny suplik neprotina zadny jiny dil ({len(nalez)} pruniku v mrizce {vzorky} sestav)", str(nalez[:4]))
# mutace: suplik jedouci do STRANY (spatna osa) narazi do nohou a profilu - kontrola pruniku to musi chytit (jinak by nic nehlidala)
_, nal_mut = mrizka_pruniku(osa_pevna=(0.0, 0.0, 1.0), vzorky_max=40)
check(len(nal_mut) > 0, "mutace: suplik jedouci do strany protina jine dily - kontrola pruniku to chyta", str(len(nal_mut)))

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("4) zive tazeni: extra rozsah ve vodicich, bez boxu nic")
for system in (30, 35, 40):
    S._SYSTEM.set(system)
    par = dict(system=system, sirka=1600.0)
    v = G.vodici(par, S.odpoved(par))["ovladani"]
    r = S.odpoved(par)
    check(len(v["zive_rozsahy"]) == len(r["dily"]), f"system {system}: zive_rozsahy ma rozsah pro kazdy dil ({len(v['zive_rozsahy'])})")
    ex = v.get("zive_rozsahy_extra")
    box_i = [i for i, d in enumerate(r["dily"]) if d["part_id"] in S.SUPLIK_PARTY_VSE]
    check(ex is not None and list(ex.keys()) == [str(box_i[0])], f"system {system}: zive_rozsahy_extra je pro dil boxu (klic = index dilu jako text)", str(ex))
    ops_s_boxem = [(t_["id"], op["op"]) for t_ in v["tahy"] for op in t_.get("zive", []) if box_i[0] in op["ix"]]
    check(len(ops_s_boxem) >= 1, f"system {system}: aspon jedna zive operace hybe boxem (jinak by extra rozsah nemel smysl): {ops_s_boxem[:4]}")
    par0 = dict(system=system, sirka=1600.0, suplik=False)
    v0 = G.vodici(par0, S.odpoved(par0))["ovladani"]
    check("zive_rozsahy_extra" not in v0, f"system {system}: bez boxu zadne zive_rozsahy_extra")
    glb0 = G.model_pro_parametry(par0)[1]
    js0, _b0 = rozbal(glb0)
    check(not any(n.get("name") == "p1" for n in js0["nodes"]) and js0["scenes"][0]["extras"]["v3d"]["motions"] == [], f"system {system}: bez boxu zadny pivot ani pohyb")
    h1, glbA = G.model_pro_parametry(par)
    h2, glbB = G.model_pro_parametry(par)
    check(h1 == h2 and glbA == glbB and G._EXTRA_CACHE.get(h1), f"system {system}: cache drzi GLB i extra rozsahy pohromade")

print(f"\n{OK} kontrol OK" + ("" if not FAILS else f"; SELHALO {len(FAILS)}"))
sys.exit(1 if FAILS else 0)
